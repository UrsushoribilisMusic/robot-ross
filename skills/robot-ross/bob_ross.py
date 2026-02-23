#!/usr/bin/env python3
"""
bob_ross.py
-----------
Bob Ross mode: the Huenit robot arm draws/writes while narrating poetically.

Usage:
    python3 bob_ross.py write "OpenClaw"
    python3 bob_ross.py write "Hello" --size 15
    python3 bob_ross.py draw square
    python3 bob_ross.py draw circle 20
    python3 bob_ross.py check          # readiness check only

Stop at any time with Ctrl+C or SIGTERM.
"""

import sys
import os
import json
import subprocess
import threading
import time
import signal
import argparse
import urllib.request
import urllib.error
from datetime import datetime
import order_log

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR  = os.path.dirname(SCRIPT_DIR)
HUENIT_DIR  = os.path.join(SKILLS_DIR, "huenit")
VOICE_DIR   = os.path.join(SKILLS_DIR, "voice")

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_URL       = "http://localhost:11434/api/generate"
OLLAMA_MODEL     = "MichelRosselli/apertus:8b-instruct-2509-q4_k_m"
PORT             = os.environ.get("HUENIT_PORT", "/dev/cu.usbserial-310")
CALIBRATION_FILE = os.path.join(HUENIT_DIR, "calibration.json")

# Seconds between live commentary phrases while drawing
COMMENTARY_INTERVAL = 6

# Log file
LOG_FILE = os.path.join(SCRIPT_DIR, "bob_ross.log")

# Telegram preview config
TELEGRAM_CHAT_ID  = "997912895"
PENDING_STATE     = "/tmp/robot_ross_pending.json"
JOB_LOCK          = "/tmp/robot_ross_running.lock"
SEGMENTS_MIN      = 2000
SEGMENTS_MAX      = 8000
SEGMENTS_STEP     = 1000
SEGMENTS_DEFAULT  = 4000


def log(event, detail=""):
    """Append a timestamped log entry."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {event}"
    if detail:
        line += f" — {detail}"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass  # never let logging break the main flow
    print(line)


# ── Telegram preview helpers ──────────────────────────────────────────────────
def svg_to_png(svg_path, png_path):
    """Render SVG to PNG using qlmanage (macOS built-in)."""
    try:
        out_dir = os.path.dirname(png_path)
        result = subprocess.run(
            ["qlmanage", "-t", "-s", "1200", "-o", out_dir, svg_path],
            capture_output=True, timeout=30,
        )
        # qlmanage saves as <filename>.svg.png
        ql_out = svg_path + ".png"
        if os.path.exists(ql_out):
            os.rename(ql_out, png_path)
            return True
        print(f"  ⚠  qlmanage did not produce output")
        return False
    except Exception as e:
        print(f"  ⚠  svg_to_png failed: {e}")
        return False


def send_telegram_preview(png_path, caption):
    """Send a PNG preview to Telegram via openclaw CLI."""
    import shutil
    # openclaw only allows media from its own directories — copy there first
    allowed_dir = os.path.expanduser("~/.openclaw/media/inbound")
    os.makedirs(allowed_dir, exist_ok=True)
    send_path = os.path.join(allowed_dir, os.path.basename(png_path))
    shutil.copy2(png_path, send_path)
    try:
        result = subprocess.run(
            ["openclaw", "message", "send",
             "--channel", "telegram",
             "--target", TELEGRAM_CHAT_ID,
             "--message", caption,
             "--media", send_path],
            capture_output=True, timeout=30,
        )
        if result.returncode == 0:
            print("  ✅ Preview sent to Telegram")
            return True
        else:
            print(f"  ⚠  Telegram send failed: {result.stderr.decode()[:200]}")
            return False
    except Exception as e:
        print(f"  ⚠  Telegram send error: {e}")
        return False


def write_pending(image_path, svg_path, segments, max_px, blur):
    """Save pending draw state to temp file."""
    state = {"image_path": image_path, "svg_path": svg_path,
             "segments": segments, "max_px": max_px, "blur": blur}
    with open(PENDING_STATE, "w") as f:
        json.dump(state, f)
    print(f"  💾 Pending state saved: {segments} segments, max_px={max_px}, blur={blur}")


def read_pending():
    """Load pending draw state. Returns dict or None."""
    if not os.path.exists(PENDING_STATE):
        print("  ❌ No pending drawing found. Send a photo first.")
        return None
    with open(PENDING_STATE) as f:
        return json.load(f)


def preview_image(image_path, target_segments, max_px=800, blur=1.5):
    """Convert image → SVG at target segments → PNG → send to Telegram."""
    svg_path = os.path.splitext(image_path)[0] + "_traced.svg"
    png_path = os.path.splitext(image_path)[0] + "_preview.png"

    print(f"  🖼  Converting image → SVG (target {target_segments} segs, max_px={max_px}, blur={blur})...")
    convert_cmd = [
        sys.executable,
        os.path.join(HUENIT_DIR, "image_to_svg.py"),
        image_path, "--out", svg_path,
        "--edges", "--auto",
        "--max-px", str(max_px),
        "--blur", str(blur),
    ]
    env = os.environ.copy()
    env["IMAGE_SVG_TARGET"] = str(target_segments)
    result = subprocess.run(convert_cmd, capture_output=False, env=env)
    if result.returncode != 0:
        print("  ❌ Image conversion failed")
        return False

    print("  🖼  Rendering SVG preview...")
    if not svg_to_png(svg_path, png_path):
        print("  ⚠  Could not render preview PNG")
        return False

    # Count actual segments from SVG
    try:
        with open(svg_path) as f:
            content = f.read()
        segs = sum(content.count(f' {c}') + content.count(f',{c}') + content.count(f'"{c}')
                   for c in ['L', 'C', 'Q'])
        est_min = segs // 500 + 1
    except Exception:
        segs, est_min = target_segments, "?"

    caption = (
        f"🎨 Preview ready! ~{segs} segments, est. {est_min} min to draw.\n\n"
        f"Reply with:\n"
        f"  draw — start drawing now\n"
        f"  more detail — increase detail (+1000, max {SEGMENTS_MAX})\n"
        f"  less detail — reduce detail (-1000, min {SEGMENTS_MIN})"
    )
    send_telegram_preview(png_path, caption)
    write_pending(image_path, svg_path, segs, max_px, blur)
    return True


# ── Shared state ──────────────────────────────────────────────────────────────
stop_flag = threading.Event()
_draw_proc = None
_draw_proc_lock = threading.Lock()


# ── Voice ─────────────────────────────────────────────────────────────────────
def speak(text):
    """Speak text via speak.py. Blocks until done."""
    if stop_flag.is_set():
        return
    print(f"  🗣  {text}")
    try:
        subprocess.run(
            [sys.executable, os.path.join(VOICE_DIR, "speak.py"), text],
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        print("  ⚠  speak.py timed out")
    except Exception as e:
        print(f"  ⚠  speak.py error: {e}")


def warning_tone():
    """Three Ping beeps to warn humans to step away."""
    ping = "/System/Library/Sounds/Ping.aiff"
    for _ in range(3):
        if stop_flag.is_set():
            return
        try:
            subprocess.run(["afplay", ping], capture_output=True, timeout=3)
        except Exception:
            # Fallback: use say with a short beep word
            subprocess.run(["say", "-v", "Evan", "beep"], capture_output=True, timeout=3)
        time.sleep(0.5)


# ── Readiness check ───────────────────────────────────────────────────────────
def readiness_check():
    """Return a list of issues. Empty list = all good."""
    issues = []

    # Robot arm port
    if not os.path.exists(PORT):
        issues.append(f"Robot arm port not found: {PORT}")

    # Calibration file
    if not os.path.exists(CALIBRATION_FILE):
        issues.append(
            "No calibration file found. "
            "Run: python3 ~/.openclaw/workspace/skills/huenit/huenit_draw.py calibrate"
        )

    # Session ready flag (set by calibrate, cleared on reboot)
    if not os.path.exists("/tmp/huenit_ready.flag"):
        issues.append(
            "Robot not calibrated this session. "
            "Run: python3 ~/.openclaw/workspace/skills/huenit/huenit_draw.py calibrate"
        )

    # Ollama reachable
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            if not any(OLLAMA_MODEL.split(":")[0] in m for m in models):
                issues.append(
                    f"Model '{OLLAMA_MODEL}' not found in Ollama. "
                    f"Available: {', '.join(models) or 'none'}"
                )
    except Exception as e:
        issues.append(f"Ollama not reachable at localhost:11434 — {e}")

    # Huenit scripts exist
    for script in ("huenit_write.py", "huenit_draw.py"):
        if not os.path.exists(os.path.join(HUENIT_DIR, script)):
            issues.append(f"Missing huenit script: {script}")

    # Voice script exists
    if not os.path.exists(os.path.join(VOICE_DIR, "speak.py")):
        issues.append("Missing voice script: speak.py")

    return issues


# ── Ollama narration ──────────────────────────────────────────────────────────
def generate_narration(action, content, buyer=None):
    """Ask Apertus to generate Bob Ross style narration. Returns dict or fallback."""
    buyer_line = f" The customer's name is {buyer}. Address them warmly by name in the intro." if buyer else ""
    # Strip literal \n so it never reaches spoken text as "slash n"
    speakable = content.replace('\\n', ' ').replace('\n', ' ').strip()
    if action == "write":
        text_lines = content.replace('\\n', '\n').split('\n')
        text_lines = [l for l in text_lines if l.strip()]
        if len(text_lines) > 1:
            action_desc = f"write {len(text_lines)} lines of text: {' / '.join(text_lines)}"
        else:
            action_desc = f"write the text '{speakable}'"
    elif action == "image":
        action_desc = "draw a vector illustration from a photo"
    elif action == "svg":
        action_desc = "draw a vector illustration"
    elif action == "fetch":
        action_desc = "draw a vector illustration fetched from the internet"
    else:
        action_desc = f"draw a {speakable}"

    prompt = (
        "You are Bob Ross, the gentle and poetic TV painter. "
        "But today, instead of painting, you are controlling a robot arm that draws on paper.\n\n"
        f"A request has come in to {action_desc}.{buyer_line}\n\n"
        "Generate narration as a JSON object with exactly these keys:\n"
        '- "intro": 1-2 warm sentences welcoming the request. Start with "We got a lovely request..."\n'
        '- "commentary": a list of 5 short, poetic, Bob Ross-style phrases to say WHILE drawing. '
        "They do not need to match specific letters or shapes — just be encouraging and peaceful. "
        "Each phrase is 1 short sentence.\n"
        '- "outro": 1-2 warm sentences for when the drawing is done, '
        "telling the human they can remove their piece.\n\n"
        "Respond with ONLY the JSON object. No explanation, no markdown."
    )

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }).encode()

    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            narration = json.loads(result["response"])
            # Validate expected keys
            if all(k in narration for k in ("intro", "commentary", "outro")):
                return narration
            print("  ⚠  Apertus response missing expected keys, using fallback")
    except Exception as e:
        print(f"  ⚠  Ollama error: {e} — using fallback narration")

    # Fallback narration
    greeting = f"Good morning, {buyer}. " if buyer else ""
    return {
        "intro": (
            f"{greeting}We got a lovely request for {speakable} today. "
            "Let's see what happy little marks we can make together."
        ),
        "commentary": [
            "Every stroke is a happy little decision.",
            "Nice and easy, we're doing beautifully.",
            "Let's add a little something right here.",
            "There are no mistakes, only happy little accidents.",
            "We're almost there. Isn't this something special.",
        ],
        "outro": (
            "And there we have it. Isn't that a lovely piece. "
            "You can remove your artwork now."
        ),
    }


# ── Commentary thread ─────────────────────────────────────────────────────────
def run_commentary(phrases, draw_done):
    """Fire commentary phrases at intervals while drawing. Runs in background thread."""
    time.sleep(3)  # give the arm a moment to start
    for phrase in phrases:
        if stop_flag.is_set() or draw_done.is_set():
            break
        speak(phrase)
        draw_done.wait(timeout=COMMENTARY_INTERVAL)


# ── Drawing ───────────────────────────────────────────────────────────────────
def run_draw(action, content, size=None):
    """
    Launch the appropriate huenit script as a subprocess.
    Monitors stop_flag and terminates + lifts pen if set.
    Returns True on success.
    """
    global _draw_proc

    py = sys.executable  # use same interpreter as bob_ross.py (has all deps)
    if action == "write":
        cmd = [py, os.path.join(HUENIT_DIR, "huenit_write.py"), content]
        if size:
            cmd += ["--size", str(size)]
    elif action == "draw":
        cmd = [py, os.path.join(HUENIT_DIR, "huenit_draw.py"), content]
        if size:
            cmd.append(str(size))
    elif action == "svg":
        # Resolve bare filename → ~/Downloads/filename
        svg_path = content
        if not os.path.dirname(svg_path):
            svg_path = os.path.expanduser(os.path.join("~/Downloads", svg_path))
        cmd = [py, os.path.join(HUENIT_DIR, "huenit_svg.py"), svg_path]
        if size:
            cmd += ["--size", str(size)]
    elif action == "fetch":
        # Download SVG from URL, validate, then draw raw
        svg_path = "/tmp/robot_ross_fetched.svg"
        fetch_cmd = [
            py, os.path.join(HUENIT_DIR, "huenit_sketch.py"),
            content, "--fetch-only", "--out", svg_path,
        ]
        print(f"  Fetching SVG: {content}")
        result = subprocess.run(fetch_cmd, stderr=subprocess.PIPE)
        if result.returncode != 0 or not os.path.exists(svg_path):
            err = (result.stderr or b"").decode(errors="replace").strip()
            print(f"  ❌ SVG fetch failed: {err[:300]}")
            return False
        print(f"  ✅ SVG ready: {svg_path}")
        cmd = [py, os.path.join(HUENIT_DIR, "huenit_svg.py"), svg_path]
        if size:
            cmd += ["--size", str(size)]
    elif action == "image":
        # Convert image → SVG, then draw
        img_path = os.path.expanduser(content)
        svg_path = os.path.splitext(img_path)[0] + "_traced.svg"
        print(f"  🖼  Converting image to SVG: {img_path}")
        convert_cmd = [
            py, os.path.join(HUENIT_DIR, "image_to_svg.py"),
            img_path, "--out", svg_path,
        ]
        result = subprocess.run(convert_cmd, stderr=subprocess.PIPE)
        if result.returncode != 0:
            err = (result.stderr or b"").decode(errors="replace").strip()
            print(f"  ❌ Image conversion failed: {err[:300]}")
            return False
        print(f"  ✅ SVG ready: {svg_path}")
        cmd = [py, os.path.join(HUENIT_DIR, "huenit_svg.py"), svg_path]
        if size:
            cmd += ["--size", str(size)]
    else:
        print(f"  ⚠  Unknown action: {action}")
        return False

    with _draw_proc_lock:
        _draw_proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)

    try:
        while _draw_proc.poll() is None:
            if stop_flag.is_set():
                _emergency_stop()
                return False
            time.sleep(0.1)
        if _draw_proc.returncode != 0:
            err = (_draw_proc.stderr.read() or b"").decode(errors="replace").strip()
            if err:
                log("SUBPROCESS ERROR", err[:500])
        return _draw_proc.returncode == 0
    finally:
        with _draw_proc_lock:
            _draw_proc = None


def _emergency_stop():
    """Terminate the draw process and lift the pen."""
    global _draw_proc
    with _draw_proc_lock:
        proc = _draw_proc
    if proc and proc.poll() is None:
        proc.terminate()
        proc.wait(timeout=3)

    # Lift pen via raw serial
    try:
        import serial
        s = serial.Serial(PORT, 115200, timeout=1)
        time.sleep(0.5)
        s.write(b"G21\nG91\nG1 Z5 F800\nM400\n")
        s.flush()
        time.sleep(1.5)
        s.write(b"G90\n")
        s.flush()
        s.close()
        print("  ✅ Pen lifted — arm safe.")
    except Exception as e:
        print(f"  ⚠  Could not lift pen via serial: {e}")


# ── Signal handler ────────────────────────────────────────────────────────────
def handle_stop(signum, frame):
    log("STOP", "signal received — aborting job")
    stop_flag.set()
    try:
        os.remove(JOB_LOCK)
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Robot Ross mode for the Huenit robot arm")
    parser.add_argument(
        "action",
        choices=["write", "draw", "svg", "image", "sketch", "fetch", "approve", "cancel", "more", "less", "check", "calibrate"],
        help="write TEXT | draw SHAPE | svg FILE | image FILE | sketch PROMPT | fetch URL | approve | cancel | more | less | check | calibrate",
    )
    parser.add_argument(
        "content",
        nargs="?",
        help="Text to write, shape name, or path to SVG file",
    )
    parser.add_argument("--size",   type=float, help="Size in mm (letter height or shape size)")
    parser.add_argument("--no-voice", action="store_true", help="Skip all voice narration")
    parser.add_argument("--direct", action="store_true",
                        help="sketch: skip preview, draw immediately (for automated orders)")
    parser.add_argument("--buyer",  default=None,
                        help="Buyer name for personalised narration (e.g. from Shopify order)")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    # ── SKETCH — generate Quick Draw scene SVG, preview, wait for approve/cancel ─
    if args.action == "sketch":
        if not args.content:
            parser.error("sketch requires a prompt, e.g.: sketch \"a cat on a bench\"")
        prompt = args.content
        svg_path = "/tmp/quickdraw_scene.svg"
        png_path = "/tmp/quickdraw_scene_preview.png"

        log("SKETCH", f"prompt={prompt!r}")
        print(f"  Composing Quick Draw scene for: {prompt!r}")

        compose_cmd = [
            sys.executable,
            os.path.join(HUENIT_DIR, "quickdraw_compose.py"),
            prompt,
            "--out", svg_path,
            "--png-out", png_path,
        ]
        result = subprocess.run(compose_cmd, capture_output=False)
        if result.returncode != 0 or not os.path.exists(svg_path):
            print("  ❌ Scene composition failed")
            sys.exit(1)

        if args.direct:
            # Automated order — skip preview, go straight to arm
            log("SKETCH DIRECT", f"bypassing preview, drawing immediately")
            args._original_action  = "sketch"
            args._original_content = prompt
            args.action  = "svg"
            args.content = svg_path
            # fall through to the arm execution below
        else:
            caption = (
                f"Sketch ready: {prompt}\n\n"
                f"Reply with:\n  draw — send to arm\n  cancel — discard"
            )
            if os.path.exists(png_path):
                send_telegram_preview(png_path, caption)
            else:
                print("  ⚠  PNG not generated — sending text only")
                subprocess.run(
                    ["openclaw", "message", "send",
                     "--channel", "telegram",
                     "--target", TELEGRAM_CHAT_ID,
                     "--message", caption],
                    capture_output=True,
                )

            # Save pending state (type=sketch, no image_path)
            state = {"type": "sketch", "svg_path": svg_path, "prompt": prompt}
            with open(PENDING_STATE, "w") as f:
                json.dump(state, f)
            log("SKETCH PREVIEW", f"pending saved, svg={svg_path}")
            sys.exit(0)

    # ── CANCEL — discard pending sketch or image ───────────────────────────────
    if args.action == "cancel":
        if os.path.exists(PENDING_STATE):
            with open(PENDING_STATE) as f:
                state = json.load(f)
            os.remove(PENDING_STATE)
            what = state.get("prompt") or state.get("image_path", "pending drawing")
            msg = f"Cancelled. Nothing was drawn."
            log("CANCEL", what)
        else:
            msg = "Nothing pending to cancel."
            log("CANCEL", "no pending state")
        print(f"  {msg}")
        subprocess.run(
            ["openclaw", "message", "send",
             "--channel", "telegram",
             "--target", TELEGRAM_CHAT_ID,
             "--message", msg],
            capture_output=True,
        )
        sys.exit(0)

    # ── IMAGE PREVIEW (no arm needed) ─────────────────────────────────────────
    if args.action == "image":
        if not args.content:
            parser.error("image path is required")
        img_path = os.path.expanduser(args.content)
        if not os.path.exists(img_path):
            # Try ~/Downloads fallback
            img_path = os.path.expanduser(os.path.join("~/Downloads", args.content))
        if not os.path.exists(img_path):
            print(f"  ❌ Image not found: {args.content}")
            sys.exit(1)
        log("IMAGE PREVIEW", img_path)
        preview_image(img_path, SEGMENTS_DEFAULT, max_px=1600, blur=0.5)
        sys.exit(0)

    # ── APPROVE — draw the pending SVG ────────────────────────────────────────
    if args.action == "approve":
        state = read_pending()
        if not state:
            sys.exit(1)
        log("APPROVE", f"drawing {state['svg_path']}")
        args.action  = "svg"
        args.content = state["svg_path"]

    # ── MORE / LESS — adjust detail and re-preview ─────────────────────────────
    if args.action in ("more", "less"):
        state = read_pending()
        if not state:
            sys.exit(1)
        current  = state.get("segments", SEGMENTS_DEFAULT)
        max_px   = state.get("max_px", 800)
        blur     = state.get("blur", 1.5)
        if args.action == "more":
            new_target = min(current + SEGMENTS_STEP, SEGMENTS_MAX)
            # Also increase resolution and reduce blur to extract finer edges
            max_px = min(max_px + 200, 2000)
            blur   = max(round(blur - 0.5, 1), 0.5)
        else:
            new_target = max(current - SEGMENTS_STEP, SEGMENTS_MIN)
            max_px = max(max_px - 200, 400)
            blur   = round(blur + 0.5, 1)
        log(f"DETAIL {args.action.upper()}", f"{current} → {new_target} segs, max_px={max_px}, blur={blur}")
        preview_image(state["image_path"], new_target, max_px=max_px, blur=blur)
        sys.exit(0)

    # ── READINESS CHECK (arm actions only) ────────────────────────────────────
    print("[robot-ross] Checking system readiness...")
    issues = readiness_check()

    if args.action == "calibrate":
        log("CALIBRATE", "starting interactive calibration")
        subprocess.run(["python3", os.path.join(HUENIT_DIR, "huenit_draw.py"), "calibrate"])
        log("CALIBRATE", "calibration complete")
        sys.exit(0)

    if args.action == "check":
        if issues:
            log("CHECK", f"not ready — {'; '.join(issues)}")
            print("❌ System not ready:")
            for issue in issues:
                print(f"  · {issue}")
            sys.exit(1)
        else:
            log("CHECK", "all systems ready")
            print("✅ All systems ready.")
            sys.exit(0)

    if issues:
        log("ERROR", f"readiness check failed — {'; '.join(issues)}")
        print("❌ System not ready:")
        for issue in issues:
            print(f"  · {issue}")
        sys.exit(1)

    if not args.content:
        parser.error("content is required for write/draw")

    # ── JOB LOCK — prevent collisions ─────────────────────────────────────────
    if os.path.exists(JOB_LOCK):
        with open(JOB_LOCK) as f:
            lock_info = f.read().strip()
        msg = f"⚠️ Robot Ross is already drawing ({lock_info}). Please wait until it finishes."
        print(msg)
        log("BUSY", lock_info)
        subprocess.run(["openclaw", "message", "send",
                        "--channel", "telegram",
                        "--target", TELEGRAM_CHAT_ID,
                        "--message", msg], capture_output=True)
        sys.exit(1)

    lock_detail = f"action={args.action} content={args.content!r}"
    with open(JOB_LOCK, "w") as f:
        f.write(lock_detail)

    log("JOB START", f"action={args.action} content={args.content!r}" + (f" size={args.size}" if args.size else ""))

    # ── ORDER LOG — record reception ───────────────────────────────────────────
    # Use original_action/original_content (sketch --direct rewrites args.action to "svg")
    _order_row = order_log.start(
        buyer=args.buyer,
        order_type=getattr(args, "_original_action", args.action),
        content=getattr(args, "_original_content", args.content),
    )

    # ── OBS RECORDING ─────────────────────────────────────────────────────────
    _obs_recording = None
    _recording_start = None
    try:
        import obs_manager
        obs_content = getattr(args, "_original_content", args.content)
        obs_manager.start_show(buyer_name=args.buyer, prompt=obs_content, record_only=True)
        _recording_start = time.time()
        log("OBS", "recording started")
    except Exception as e:
        log("OBS", f"not available — {e}")

    # ── PREVENT SLEEP ─────────────────────────────────────────────────────────
    _caffeinate = subprocess.Popen(["caffeinate", "-d", "-i"])  # -d=display, -i=system
    log("CAFFEINATE", f"started (pid {_caffeinate.pid}) — Mac will not sleep during draw")

    # ── GENERATE NARRATION ────────────────────────────────────────────────────
    if not args.no_voice:
        log("NARRATION", "requesting from Apertus")
        narration = generate_narration(args.action, args.content, buyer=args.buyer)
        log("NARRATION", "ready" if narration.get("intro") else "using fallback")
    else:
        narration = {"intro": "", "commentary": [], "outro": ""}
        log("NARRATION", "skipped (--no-voice)")

    if stop_flag.is_set():
        return

    # ── WARNING TONE ──────────────────────────────────────────────────────────
    log("WARNING TONE", "playing — stand clear")
    warning_tone()
    _beep_end = time.time()

    if stop_flag.is_set():
        log("STOP", "aborted during warning tone")
        return

    # ── INTRO ─────────────────────────────────────────────────────────────────
    if not args.no_voice and narration["intro"]:
        log("VOICE INTRO", narration["intro"])
        speak(narration["intro"])

    if stop_flag.is_set():
        log("STOP", "aborted during intro")
        speak("Stopping before we start.")
        return

    # ── DRAW + LIVE COMMENTARY IN PARALLEL ───────────────────────────────────
    log("DRAW START", f"{args.action} {args.content!r}")
    draw_start = time.time()
    draw_done = threading.Event()

    if not args.no_voice and narration["commentary"]:
        t = threading.Thread(
            target=run_commentary,
            args=(narration["commentary"], draw_done),
            daemon=True,
        )
        t.start()

    success = run_draw(args.action, args.content, args.size)
    draw_done.set()
    elapsed = round(time.time() - draw_start, 1)

    if stop_flag.is_set():
        log("STOP", f"arm stopped mid-draw after {elapsed}s")
        speak("The arm has been stopped. Please check the paper.")
        return

    time.sleep(0.5)  # let any in-flight speech wrap up

    # ── OUTRO ─────────────────────────────────────────────────────────────────
    if not args.no_voice:
        if success:
            log("VOICE OUTRO", narration["outro"])
            speak(narration["outro"])
        else:
            log("ERROR", "draw subprocess failed")
            speak("Something went wrong with the arm. Please check the setup and try again.")

    status = "success" if success else "failed"
    log("JOB END", f"status={status} duration={elapsed}s")

    # ── OBS STOP + YOUTUBE SHORTS UPLOAD ─────────────────────────────────────
    video_path = None
    video_url = None
    try:
        import obs_manager
        video_path = obs_manager.stop_show()
        if video_path:
            log("OBS", f"recording saved: {video_path}")
            # ── TRIM — cut everything before the last beep ─────────────────
            if _recording_start is not None:
                trim_offset = max(0.0, _beep_end - _recording_start)
                trimmed = video_path.rsplit(".", 1)
                trimmed = trimmed[0] + "_trimmed." + (trimmed[1] if len(trimmed) > 1 else "mov")
                log("TRIM", f"cutting first {trim_offset:.1f}s (beeps + setup)")
                trim_result = subprocess.run(
                    ["/opt/homebrew/bin/ffmpeg", "-y",
                     "-ss", f"{trim_offset:.2f}",
                     "-i", video_path,
                     "-c", "copy",
                     trimmed],
                    capture_output=True,
                )
                if trim_result.returncode == 0 and os.path.exists(trimmed):
                    os.replace(trimmed, video_path)
                    log("TRIM", "done — recording trimmed in place")
                else:
                    err = trim_result.stderr.decode(errors="replace")[-200:]
                    log("TRIM", f"ffmpeg failed, uploading untrimmed — {err}")
            try:
                import youtube_upload
                prompt_text = getattr(args, "_original_content", args.content)
                upload_title = f"Robot Ross draws for {args.buyer}" if args.buyer else "Robot Ross drawing"
                video_url = youtube_upload.youtube_upload(
                    video_path,
                    title=upload_title,
                    buyer=args.buyer,
                    prompt=prompt_text,
                )
                if video_url:
                    log("YOUTUBE", f"upload success: {video_url}")
                else:
                    log("YOUTUBE", "upload failed (continuing without URL)")
            except Exception as e:
                log("YOUTUBE", f"upload exception — {e}")
    except Exception as e:
        log("OBS", f"stop failed — {e}")

    # ── ORDER LOG — record completion ──────────────────────────────────────────
    try:
        order_log.end(_order_row, status)
        if video_url:
            order_log.set_video(_order_row, video_url)
    except Exception as e:
        log("ORDER LOG ERROR", str(e))

    # ── RELEASE SLEEP PREVENTION ──────────────────────────────────────────────
    try:
        _caffeinate.terminate()
    except Exception:
        pass

    # ── RELEASE JOB LOCK ──────────────────────────────────────────────────────
    try:
        os.remove(JOB_LOCK)
    except Exception:
        pass


if __name__ == "__main__":
    main()
