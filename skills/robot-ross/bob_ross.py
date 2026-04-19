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
    print("\n[STOP] Interrupt received. Lifting pen and halting...")
    stop_flag.set()
    if _draw_proc and _draw_proc.poll() is None:
        _draw_proc.terminate()


def readiness_check():
    """Verify hardware and Ollama status. Returns list of issue strings."""
    issues = []
    # Check port
    if not os.path.exists(PORT) and sys.platform != "linux":
        issues.append(f"Robot arm not found on {PORT}")
    # Check Ollama
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
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


def speak(text):
    """Speak text using voice/speak.py."""
    if not text: return
    try:
        subprocess.run([sys.executable, os.path.join(VOICE_DIR, "speak.py"), text], timeout=120)
    except Exception as e:
        log("SPEAK ERROR", str(e))


def generate_narration(action, content, buyer=None):
    """Ask Apertus to generate Bob Ross style narration."""
    buyer_line = f" The customer's name is {buyer}. Address them warmly by name in the intro." if buyer else ""
    speakable = content.replace('\\n', ' ').replace('\n', ' ').strip()

    if action == "write":
        action_desc = f"write the text '{speakable}'"
    elif action == "image":
        action_desc = "draw a vector illustration from a photo"
    elif action == "svg":
        action_desc = "draw a vector illustration"
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
        '- "commentary": a list of 5 short, poetic phrases to say WHILE drawing.\n'
        '- "outro": 1-2 warm sentences for when the drawing is done.\n\n'
        "Respond with ONLY the JSON object. No explanation, no markdown."
    )

    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"}).encode()
    try:
        req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return json.loads(result["response"])
    except Exception:
        return {"intro": f"We got a lovely request for {speakable}.", "commentary": ["Just a happy little line here.", "Every stroke has its own personality."], "outro": "There we go. All finished and ready for you."}


def run_commentary(phrases, done_event):
    """Speak commentary phrases at intervals until the drawing is done."""
    for p in phrases:
        if done_event.is_set() or stop_flag.is_set(): break
        speak(p)
        # Sleep in small increments to remain responsive to done_event
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
        if size: cmd.append(str(min(size, MAX_DRAW_SIZE)))
    elif action == "svg":
        svg_path = content
        if not os.path.dirname(svg_path):
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
    parser.add_argument("action", choices=["write", "draw", "svg", "image", "sketch", "fetch", "check", "calibrate"])
    parser.add_argument("content", nargs="?")
    parser.add_argument("--size",   type=float)
    parser.add_argument("--pyro",   action="store_true")
    parser.add_argument("--feed",   type=float)
    parser.add_argument("--engine", default="kokoro", choices=["kokoro", "voxtral", "system"])
    parser.add_argument("--no-voice", action="store_true")
    parser.add_argument("--no-obs", action="store_true")
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--buyer",  default=None)
    args = parser.parse_args()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    # Busy Check
    if os.path.exists(JOB_LOCK):
        with open(JOB_LOCK) as f: info = f.read().strip()
        msg = f"Robot Ross is already drawing ({info}). Please wait."
        print(msg)
        subprocess.run(["openclaw", "message", "send", "--channel", "telegram", "--target", TELEGRAM_CHAT_ID, "--message", msg], capture_output=True)
        sys.exit(1)

    # Readiness
    issues = readiness_check()
    if args.action == "check":
        if issues: print(f"Not ready: {'; '.join(issues)}"); sys.exit(1)
        print("System ready."); sys.exit(0)

    if args.action == "calibrate":
        subprocess.run([sys.executable, os.path.join(HUENIT_DIR, "huenit_draw.py"), "calibrate"])
        sys.exit(0)

    # Sketch handling (composed)
    if args.action == "sketch":
        if not args.content: parser.error("sketch requires a prompt")
        svg_path = "/tmp/quickdraw_scene.svg"
        compose_cmd = [sys.executable, os.path.join(HUENIT_DIR, "quickdraw_compose.py"), args.content, "--out", svg_path]
        subprocess.run(compose_cmd)
        args.action = "svg"
        args.content = svg_path

    # Write wrap
    if args.action == "write" and args.content:
        args.content = wrap_text(args.content)

    # Lock
    with open(JOB_LOCK, "w") as f: f.write(f"action={args.action} content={args.content!r}")

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

        # Narration
        narration_action = "pyro" if args.pyro else args.action
        narration = generate_narration(narration_action, args.content, buyer=args.buyer) if not args.no_voice else {"intro":"", "commentary":[], "outro":""}

        warning_tone()
        beep_end = time.time()

        if not stop_flag.is_set() and narration["intro"]:
            speak(narration["intro"])

        # Draw
        draw_done = threading.Event()
        if narration["commentary"]:
            threading.Thread(target=run_commentary, args=(narration["commentary"], draw_done), daemon=True).start()

        success = run_draw(args.action, args.content, args.size, pyro=args.pyro, feed=args.feed)
        draw_done.set()

        if not args.no_voice and success:
            speak(narration["outro"])

        # YouTube / OBS Stop
        video_url = None
        if not args.no_obs:
            try:
                import obs_manager
                video_path = obs_manager.stop_show()
                if video_path:
                    # Simplified YouTube upload for now
                    import youtube_upload
                    video_url = youtube_upload.youtube_upload(video_path, title=f"Robot Ross drawing", buyer=args.buyer, prompt=args.content)
            except Exception: pass

        order_log.end(order_row, "success" if success else "failed")
        if video_url: order_log.set_video(order_row, video_url)

    finally:
        if '_caffeinate' in locals(): _caffeinate.terminate()
        if os.path.exists(JOB_LOCK): os.remove(JOB_LOCK)

if __name__ == "__main__":
    main()
