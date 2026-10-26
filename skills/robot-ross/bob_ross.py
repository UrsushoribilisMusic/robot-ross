#!/usr/bin/env python3
"""
bob_ross.py
-----------
Bob Ross mode: the Huenit robot arm draws/writes while narrating poetically.

Usage:
    python3 bob_ross.py write "OpenClaw"
    python3 bob_ross.py write "Hello" --size 15
    python3 bob_ross.py sketch "a happy little bear"
    python3 bob_ross.py draw square
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
import tempfile
import math
import urllib.request
import urllib.error
from datetime import datetime
import order_log

# â”€â”€ Paths â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR  = os.path.dirname(SCRIPT_DIR)
HUENIT_DIR  = os.path.join(SKILLS_DIR, "huenit")
VOICE_DIR   = os.path.join(SKILLS_DIR, "voice")

# â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
OLLAMA_URL       = "http://localhost:11434/api/generate"
OLLAMA_MODELS    = {
    "mistral": "ministral-3:8b",
    "apertus": "MichelRosselli/apertus:8b-instruct-2509-q4_k_m",
}
OLLAMA_MODEL     = OLLAMA_MODELS["mistral"]  # default brain, overridden by --brain
PORT             = os.environ.get("HUENIT_PORT", "/dev/cu.usbserial-310")
CALIBRATION_FILE = os.path.join(HUENIT_DIR, "calibration.json")

# Seconds between live commentary phrases while drawing
COMMENTARY_INTERVAL = 6

# Log file
LOG_FILE = os.path.join(SCRIPT_DIR, "bob_ross.log")

# Telegram preview config
TELEGRAM_CHAT_ID  = "997912895"
PENDING_STATE     = os.path.join(tempfile.gettempdir(), "robot_ross_pending.json")
JOB_LOCK          = os.path.join(tempfile.gettempdir(), "robot_ross_running.lock")
READY_FLAG        = os.path.join(tempfile.gettempdir(), "huenit_ready.flag")

# Maximum safe drawing area (mm). Arm loses steps beyond this â€” hard cap.
MAX_DRAW_SIZE = 125

# Text wrapping limits for the `write` action
TEXT_MAX_CHARS = 255
TEXT_LINE_CHARS = 35   # soft target; auto-scaler handles the rest

stop_flag = threading.Event()
_draw_proc = None


# â”€â”€ Text wrapping â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _hyphenate_word(word, max_len):
    """
    Split a word that exceeds max_len into hyphenated parts using a VC|CV rule.
    """
    vowels = set("aeiouAEIOU")
    parts = []
    while len(word) > max_len:
        limit = max_len - 1  # leave room for hyphen
        split_at = limit
        # Walk back up to 10 chars looking for a clean syllable boundary
        for i in range(limit, max(1, limit - 10), -1):
            prev, curr = word[i - 1], word[i]
            if curr in vowels and prev not in vowels:
                split_at = i
                break
            if prev in vowels and curr not in vowels:
                split_at = i
                break
        parts.append(word[:split_at] + "-")
        word = word[split_at:]
    parts.append(word)
    return parts


def wrap_text(text, max_chars=TEXT_MAX_CHARS, max_line=TEXT_LINE_CHARS):
    """
    Validate and wrap write-action text.
    """
    if len(text) > max_chars:
        raise ValueError(f"Text too long ({len(text)} chars, max {max_chars}).")

    words = text.split()
    lines = []
    current = []
    current_len = 0

    for word in words:
        gap = 1 if current else 0
        if current_len + gap + len(word) <= max_line:
            current.append(word)
            current_len += gap + len(word)
        else:
            if current:
                lines.append(" ".join(current))
            if len(word) > max_line:
                parts = _hyphenate_word(word, max_line)
                for part in parts[:-1]:
                    lines.append(part)
                current = [parts[-1]]
                current_len = len(parts[-1])
            else:
                current = [word]
                current_len = len(word)

    if current:
        lines.append(" ".join(current))

    return "\\n".join(lines)


def log(event, detail=""):
    """Append a timestamped log entry."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {event}"
    if detail:
        line += f" â€” {detail}"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def handle_stop(signum, frame):
    """Signal handler for Ctrl+C or SIGTERM."""
    print("\n[STOP] Interrupt received. Stopping the drawing process...")
    stop_flag.set()
    if _draw_proc and _draw_proc.poll() is None:
        _draw_proc.terminate()


def readiness_check(require_brain=True):
    """Verify hardware and Ollama status. Returns list of issue strings."""
    issues = []
    # Check port
    from serial.tools import list_ports
    if PORT not in {p.device for p in list_ports.comports()}:
        issues.append(f"Robot arm not found on {PORT}")
    if not os.path.exists(CALIBRATION_FILE) or not os.path.exists(READY_FLAG):
        issues.append("Calibrate for this session before drawing")
    # Check Ollama
    if require_brain:
        try:
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as response:
                models = json.load(response).get('models', [])
            if not any(m.get('name') == OLLAMA_MODEL for m in models):
                issues.append(f"Narration model unavailable: {OLLAMA_MODEL}")
        except Exception:
            issues.append("Ollama not running on localhost:11434")
    return issues


def warning_tone():
    """Play 3 beeps to warn humans near the arm."""
    for _ in range(3):
        if stop_flag.is_set(): break
        if sys.platform == "darwin":
            subprocess.run(["afplay", "/System/Library/Sounds/Ping.aiff"], capture_output=True)
        elif sys.platform == "win32":
            import winsound
            winsound.Beep(1000, 200)
        time.sleep(0.4)


_tts_engine = "voxtral"

def speak(text):
    """Speak text using voice/speak.py."""
    if not text: return
    try:
        subprocess.run([sys.executable, os.path.join(VOICE_DIR, "speak.py"), text,
                        "--engine", _tts_engine], timeout=120)
    except Exception as e:
        log("SPEAK ERROR", str(e))


def _generic_narration(speakable):
    """Fast, non-LLM filler narration — used immediately while the real one generates in the background."""
    return {
        "intro": f"We got a lovely request for {speakable}. Let's get started right away!",
        "commentary": [
            "Just a happy little line here.",
            "Every stroke has its own personality.",
            "There are no mistakes, only happy accidents.",
            "Let's build our confidence with this one.",
            "Isn't it fantastic that you can create anything you want?",
        ],
        "outro": "There we go. All finished and ready for you.",
    }


def generate_narration(action, content, buyer=None):
    """Ask the local Ollama brain (Mistral by default, Apertus optional) to generate Bob Ross style narration."""
    buyer_line = f" The customer's name is {buyer}. Address them warmly by name in the intro." if buyer else ""
    speakable = content.replace('\\n', ' ').replace('\n', ' ').strip()

    if action == "write":
        action_desc = f"write the text '{speakable}'"
    elif action == "image":
        action_desc = "draw a vector illustration from a photo"
    elif action == "svg":
        if os.sep in speakable or speakable.endswith(".svg"):
            name = os.path.splitext(os.path.basename(speakable))[0]
            action_desc = f"sketch a {name}" if name else "draw a vector illustration"
        else:
            action_desc = f"sketch {speakable}"
    elif action == "pyro":
        action_desc = f"burn a wood pyrography of '{speakable}'"
    elif action == "fetch":
        action_desc = "draw a vector illustration fetched from the internet"
    else:
        action_desc = f"draw a {speakable}"

    prompt = (
        "You are Bob Ross, the gentle and poetic TV painter.\n\n"
        f"A request has come in to {action_desc}.{buyer_line}\n\n"
        "Generate narration as a JSON object with exactly these keys:\n"
        '- "intro": 1-2 warm sentences welcoming the request. Start with "We got a lovely request..."\n'
        '- "commentary": a list of 10 short, poetic phrases to say WHILE drawing.\n'
        '- "outro": 1-2 warm sentences for when the drawing is done.\n\n'
        "Respond with ONLY the JSON object. No explanation, no markdown."
    )

    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"}).encode()
    try:
        with urllib.request.urlopen('http://localhost:11434/api/tags', timeout=2) as response:
            available = json.load(response).get('models', [])
        if not any(m.get('name') == OLLAMA_MODEL for m in available):
            log('NARRATION', 'Local model unavailable; using built-in narration.')
            return _generic_narration(speakable)
        req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return json.loads(result["response"])
    except Exception:
        return _generic_narration(speakable)


def run_commentary_dynamic(narration_result, done_event):
    """
    Speak generic filler commentary immediately; once the background LLM
    narration finishes, switch to the real request-specific phrases.
    """
    phrases = _generic_narration("")["commentary"]
    idx = 0
    switched = False
    while not done_event.is_set() and not stop_flag.is_set():
        if not switched and narration_result.get("done"):
            real = narration_result.get("data") or {}
            if real.get("commentary"):
                phrases = real["commentary"]
                idx = 0
            switched = True  # only try the swap once, even if commentary was empty
        speak(phrases[idx % len(phrases)])
        idx += 1
        for _ in range(COMMENTARY_INTERVAL * 10):
            if done_event.is_set() or stop_flag.is_set(): break
            time.sleep(0.1)


def run_draw(action, content, size=None, pyro=False, feed=None):
    """Launch the appropriate huenit script as a subprocess."""
    global _draw_proc
    py = sys.executable

    def _svg_size(requested):
        if requested and requested < MAX_DRAW_SIZE: return requested
        return MAX_DRAW_SIZE

    if action == "write":
        cmd = [py, os.path.join(HUENIT_DIR, "huenit_write.py"), content, "--paper-width", str(MAX_DRAW_SIZE)]
        if size: cmd += ["--size", str(size)]
        if pyro: cmd.append("--pyro")
        if feed: cmd += ["--feed", str(feed)]
    elif action == "draw":
        cmd = [py, os.path.join(HUENIT_DIR, "huenit_draw.py"), content]
        limit = MAX_DRAW_SIZE / 2 if content == 'circle' else 25 if content == 'demo' else MAX_DRAW_SIZE
        if size: cmd.append(str(min(size, limit)))
    elif action == "svg":
        svg_path = content
        if not os.path.dirname(svg_path):
            # Check repo root first (control center serves SVGs from there)
            local = os.path.join(SCRIPT_DIR, "..", "..", svg_path)
            local = os.path.normpath(local)
            if os.path.exists(local):
                svg_path = local
            else:
                svg_path = os.path.expanduser(os.path.join("~/Downloads", svg_path))
        cmd = [py, os.path.join(HUENIT_DIR, "huenit_svg.py"), svg_path, "--size", str(_svg_size(size))]
        if pyro: cmd.append("--pyro")
        if feed: cmd += ["--feed", str(feed)]
    else:
        return False

    _draw_proc = subprocess.Popen(cmd)
    _draw_proc.wait()
    return _draw_proc.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Robot Ross mode for the Huenit robot arm")
    parser.add_argument("action", choices=["write", "draw", "svg", "image", "sketch", "fetch", "check", "calibrate", "approve", "cancel", "more", "less"])
    parser.add_argument("content", nargs="?")
    parser.add_argument("shape_size", nargs="?", type=float)
    parser.add_argument("--size",   type=float)
    parser.add_argument("--pyro",   action="store_true")
    parser.add_argument("--feed",   type=float)
    parser.add_argument("--engine", default="voxtral", choices=["kokoro", "voxtral", "system"])
    parser.add_argument("--brain",  default="mistral", choices=["mistral", "apertus"], help="Ollama model for narration")
    parser.add_argument("--no-voice", action="store_true")
    parser.add_argument("--no-obs", action="store_true")
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--buyer",   default=None)
    parser.add_argument("--subject", default=None, help="Human-readable subject for narration")
    parser.add_argument("--dry-run", action="store_true", help="Prepare/validate only; no arm, ledger, recording or upload")
    parser.add_argument("--calibrate", "--calibrate-before", dest="calibrate_before", action="store_true")
    parser.add_argument("--upload", action="store_true", help="Explicitly enable YouTube upload after recording")
    args = parser.parse_args()
    if args.shape_size is not None:
        if args.action != 'draw': parser.error('Positional size is only valid for draw')
        args.size = args.shape_size
    for name in ('size', 'feed'):
        value = getattr(args, name)
        if value is not None and (not math.isfinite(value) or value <= 0):
            parser.error(name + ' must be a finite positive number')
    global _tts_engine, OLLAMA_MODEL
    _tts_engine = args.engine
    OLLAMA_MODEL = OLLAMA_MODELS[args.brain]

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    if args.action == 'cancel':
        if os.path.exists(PENDING_STATE): os.unlink(PENDING_STATE)
        print('Pending preview cancelled.')
        return

    # Calibration also needs exclusive access to the arm.
    if os.path.exists(JOB_LOCK):
        with open(JOB_LOCK) as f: info = f.read().strip()
        msg = f"Robot Ross is already drawing ({info}). Please wait."
        print(msg)
        sys.exit(1)

    # Readiness
    if args.action == "check":
        issues = readiness_check(require_brain=not args.no_voice)
        if issues: print(f"Not ready: {'; '.join(issues)}"); sys.exit(1)
        print("System ready."); sys.exit(0)

    if args.action == "calibrate" or args.calibrate_before:
        if not args.dry_run:
            try:
                with open(JOB_LOCK, 'x') as f: f.write('calibrating')
            except FileExistsError:
                sys.exit('Another job acquired the arm.')
            try:
                result = subprocess.run([sys.executable, os.path.join(HUENIT_DIR, "huenit_draw.py"), "calibrate"])
            finally:
                os.unlink(JOB_LOCK)
            if result.returncode: sys.exit(result.returncode)
        if args.action == 'calibrate': return

    if args.action in ('approve', 'more', 'less'):
        if not os.path.exists(PENDING_STATE): parser.error('No pending preview')
        with open(PENDING_STATE) as f: pending = json.load(f)
        if args.action in ('more', 'less'):
            if not pending.get('image_path'): parser.error('Detail controls require a photo preview')
            smoothness = max(0.1, pending.get('smoothness', 6.0) + (-1 if args.action == 'more' else 1))
            args.action, args.content = 'image', pending['image_path']
        else:
            args.action, args.content = 'svg', pending['svg_path']
            args.subject = args.subject or pending.get('prompt')

    if not args.content: parser.error(args.action + ' requires content')
    if args.action == 'draw' and args.content not in ('square', 'triangle', 'circle', 'demo'):
        parser.error('Unknown shape')

    if args.action in ('image', 'fetch'):
        svg_path = os.path.join(tempfile.gettempdir(), 'robot_ross_' + args.action + '.svg')
        if args.action == 'image':
            source = os.path.abspath(os.path.expanduser(args.content))
            smoothness = locals().get('smoothness', 6.0)
            convert_cmd = [sys.executable, os.path.join(HUENIT_DIR, 'image_to_svg.py'), source,
                           '--out', svg_path, '--smoothness', str(smoothness)]
        else:
            convert_cmd = [sys.executable, os.path.join(HUENIT_DIR, 'huenit_sketch.py'), args.content,
                           '--out', svg_path, '--fetch-only']
        result = subprocess.run(convert_cmd)
        if result.returncode: sys.exit(result.returncode)
        if not args.direct:
            state = {'svg_path': svg_path, 'prompt': args.subject or args.content}
            if args.action == 'image': state.update(image_path=source, smoothness=smoothness)
            with open(PENDING_STATE, 'w') as f: json.dump(state, f)
            print('Preview ready; approve to draw.')
            return
        args.action, args.content = 'svg', svg_path

    # Sketch handling (composed)
    if args.action == "sketch":
        if not args.content: parser.error("sketch requires a prompt")
        svg_path = os.path.join(tempfile.gettempdir(), "ai_sketch.svg")
        log("SKETCH", f"Requesting Haiku SVG for: {args.content!r}")
        compose_cmd = [sys.executable, os.path.join(HUENIT_DIR, "ai_sketch.py"), args.content, "--out", svg_path]
        if os.path.exists(svg_path): os.unlink(svg_path)
        result = subprocess.run(compose_cmd)
        if result.returncode or not os.path.exists(svg_path):
            log("SKETCH ERROR", "ai_sketch.py did not produce an SVG — aborting")
            sys.exit(1)
        sketch_subject = args.content
        if not args.direct:
            with open(PENDING_STATE, 'w') as f:
                json.dump({'svg_path': svg_path, 'prompt': sketch_subject}, f)
            print('Preview ready; approve to draw.')
            return
        args.action = "svg"
        args.content = svg_path
        args._sketch_subject = sketch_subject

    # Write wrap
    if args.action == "write" and args.content:
        args.content = wrap_text(args.content)

    if args.dry_run:
        print(f'DRY RUN: {args.action} {args.content!r}; no arm commands sent.')
        return

    # Manual jobs already have their geometry. Optional narration must not
    # prevent drawing when the language model was removed or is offline.
    issues = readiness_check(require_brain=False)
    if issues:
        print('Not ready: ' + '; '.join(issues))
        sys.exit(1)

    # Lock
    try:
        with open(JOB_LOCK, "x") as f: f.write(f"action={args.action} content={args.content!r}")
    except FileExistsError:
        sys.exit('Another job acquired the arm. Please wait.')

    try:
        log("JOB START", f"action={args.action} content={args.content!r}")
        order_row = order_log.start(buyer=args.buyer, order_type=args.action, content=args.content)

        # OBS
        if not args.no_obs:
            try:
                import obs_manager
                obs_manager.start_show(buyer_name=args.buyer, prompt=args.content, record_only=True)
                recording_start = time.time()
            except Exception: pass

        if sys.platform == "darwin":
            _caffeinate = subprocess.Popen(["caffeinate", "-d", "-i"])

        # Narration — generate in the background so drawing isn't gated behind
        # 60-90s of local LLM inference. Speak generic filler immediately;
        # run_commentary_dynamic swaps in the real request-specific lines once ready.
        narration_action = "pyro" if args.pyro else args.action
        narration_content = args.subject or getattr(args, "_sketch_subject", None) or args.content
        speakable = narration_content.replace('\\n', ' ').replace('\n', ' ').strip() if narration_content else ""

        narration_result = {"data": None, "done": args.no_voice}
        if not args.no_voice:
            def _fetch_narration():
                narration_result["data"] = generate_narration(narration_action, narration_content, buyer=args.buyer)
                narration_result["done"] = True
            threading.Thread(target=_fetch_narration, daemon=True).start()

        warning_tone()
        beep_end = time.time()

        if not stop_flag.is_set() and not args.no_voice:
            speak(_generic_narration(speakable)["intro"])

        # Draw
        draw_done = threading.Event()
        if not args.no_voice:
            threading.Thread(target=run_commentary_dynamic, args=(narration_result, draw_done), daemon=True).start()

        success = run_draw(args.action, args.content, args.size, pyro=args.pyro, feed=args.feed)
        draw_done.set()

        if not args.no_voice and success:
            # Don't block waiting for slow LLM generation — use it if it landed in time, else generic.
            outro = (narration_result["data"] or _generic_narration(speakable))["outro"]
            speak(outro)

        # YouTube / OBS Stop
        video_url = None
        if not args.no_obs:
            try:
                import obs_manager
                video_path = obs_manager.stop_show()
                if video_path and args.upload:
                    # Simplified YouTube upload for now
                    import youtube_upload
                    video_url = youtube_upload.youtube_upload(video_path, title=f"Robot Ross drawing", buyer=args.buyer, prompt=args.content)
            except Exception: pass

        order_log.end(order_row, "success" if success else "failed")
        if video_url: order_log.set_video(order_row, video_url)
        if not success: sys.exit(1)

    finally:
        if '_caffeinate' in locals(): _caffeinate.terminate()
        if os.path.exists(JOB_LOCK): os.remove(JOB_LOCK)

if __name__ == "__main__":
    main()
