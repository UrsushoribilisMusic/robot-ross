#!/usr/bin/env python3
"""
control_center.py — Robot Ross Control Center HTTP server

Serves the web UI and executes bob_ross.py commands.
Run via launch_control_center.bat
"""

import sys, os, json, subprocess, threading, time, webbrowser, random, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PORT        = 7870
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
HUENIT_DIR  = os.path.join(SCRIPT_DIR, "skills", "huenit")
BOB_ROSS    = os.path.join(SCRIPT_DIR, "skills", "robot-ross", "bob_ross.py")
CHAT_ROSS   = os.path.join(SCRIPT_DIR, "skills", "robot-ross", "chat_ross.py")
CAL_FILE      = os.path.join(HUENIT_DIR, "calibration.json")
PENDING_STATE = os.path.join(tempfile.gettempdir(), "robot_ross_pending.json")
SKETCH_STATUS = os.path.join(tempfile.gettempdir(), "robot_ross_sketch_status.json")
OLLAMA_URL  = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "MichelRosselli/apertus:8b-instruct-2509-q4_k_m"


SKETCH_BRAIN = "mistral"  # brain ai_sketch.py generates with — keep in sync with its own --brain default
SKETCH_TIMEOUT = 130  # ai_sketch.py's own Ollama call times out at 120s; give it a little headroom

def _write_sketch_status(status, message=None, prompt=None, brain=None):
    """Persist sketch-preview progress so the UI can show real status instead of spinning forever."""
    try:
        data = {"status": status}
        if message is not None: data["message"] = message
        if prompt is not None: data["prompt"] = prompt
        if brain is not None: data["brain"] = brain
        with open(SKETCH_STATUS, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

FALLBACK_RESPONSES = [
    "Oh, what a wonderful idea! You know, every drawing starts with a vision. "
    "Just tell me what you'd like and we'll make something beautiful together!",
    "Fantastic! In our happy little world, every request is a new adventure. "
    "Let me think about the best way to bring that to life for you!",
    "Oh my goodness, I love that idea! You know, there are no mistakes — only happy accidents. "
    "Shall we begin our creative journey?",
    "That sounds absolutely delightful! Like a happy little tree waiting to be born on paper. "
    "I'm ready when you are!",
]

job_lock = threading.Lock()
running_job = None
running_proc = None   # the bob_ross.py Popen object for the current job
showcase_lock = threading.Lock()
showcase_proc = None

JOB_LOCK_PATH = os.path.join("C:\\", "tmp", "robot_ross_running.lock")


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # suppress per-request noise; real output goes via bob_ross

    # ── helpers ──────────────────────────────────────────────────────────────

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, mime):
        try:
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_error(404)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    # ── routing ──────────────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            self._send_file(os.path.join(SCRIPT_DIR, "control_center.html"),
                            "text/html; charset=utf-8")

        elif path == "/api/status":
            self._get_status()

        elif path == "/api/pending":
            self._get_pending()

        elif path == "/api/sketch-status":
            self._get_sketch_status()

        elif path == "/pending-svg":
            self._get_pending_svg()

        elif path == "/api/svgs":
            svgs = []
            for name in sorted(os.listdir(SCRIPT_DIR)):
                if name.lower().endswith(".svg"):
                    sz = os.path.getsize(os.path.join(SCRIPT_DIR, name))
                    svgs.append({"name": name, "size_kb": round(sz / 1024, 1)})
            self._send_json({"svgs": svgs})

        elif path.startswith("/svg/"):
            name = path[5:]
            if "/" not in name and "\\" not in name and name.lower().endswith(".svg"):
                self._send_file(os.path.join(SCRIPT_DIR, name), "image/svg+xml")
            else:
                self.send_error(403)

        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        data = self._read_body()

        if path == "/api/execute":
            self._post_execute(data)
        elif path == "/api/chat":
            self._post_chat(data)
        elif path == "/api/sketch-preview":
            self._post_sketch_preview(data)
        elif path == "/api/calibrate":
            self._post_calibrate()
        elif path == "/api/approve":
            self._run_simple(["approve"])
        elif path == "/api/cancel":
            self._post_cancel()
        elif path == "/api/showcase/start":
            self._post_showcase_start(data)
        elif path == "/api/showcase/stop":
            self._post_showcase_stop()
        else:
            self.send_error(404)

    # ── API handlers ─────────────────────────────────────────────────────────

    def _get_pending(self):
        """Return the current pending sketch/image state, if any."""
        if not os.path.exists(PENDING_STATE):
            self._send_json({"pending": False})
            return
        try:
            with open(PENDING_STATE) as f:
                state = json.load(f)
            self._send_json({"pending": True, **state})
        except Exception:
            self._send_json({"pending": False})

    def _get_pending_svg(self):
        """Serve the SVG file referenced in the pending state."""
        if not os.path.exists(PENDING_STATE):
            self.send_error(404)
            return
        try:
            with open(PENDING_STATE) as f:
                state = json.load(f)
            svg_path = state.get("svg_path", "")
            if svg_path and os.path.exists(svg_path):
                self._send_file(svg_path, "image/svg+xml")
            else:
                self.send_error(404)
        except Exception:
            self.send_error(500)

    def _get_sketch_status(self):
        """Live progress for the current/last sketch-preview generation (generating/ready/error)."""
        if not os.path.exists(SKETCH_STATUS):
            self._send_json({"status": "idle"})
            return
        try:
            with open(SKETCH_STATUS) as f:
                self._send_json(json.load(f))
        except Exception:
            self._send_json({"status": "idle"})

    def _get_status(self):
        import tempfile
        READY_FLAG = os.path.join(tempfile.gettempdir(), "huenit_ready.flag")
        session_ready = os.path.exists(READY_FLAG)
        cal = {"calibrated": False, "session_ready": session_ready, "z_up": None, "tilt_slope": None}
        if os.path.exists(CAL_FILE):
            try:
                with open(CAL_FILE) as f:
                    d = json.load(f)
                cal = {"calibrated": True, "session_ready": session_ready,
                       "z_up": d.get("z_up"),
                       "tilt_slope": d.get("tilt_slope")}
            except Exception:
                pass

        with showcase_lock:
            sc_running = showcase_proc is not None and showcase_proc.poll() is None

        self._send_json({
            "calibration": cal,
            "arm_port": os.environ.get("HUENIT_PORT", "COM3"),
            "ollama": self._check_ollama(),
            "job_running": running_job is not None and running_job.is_alive(),
            "showcase_running": sc_running,
        })

    def _post_execute(self, data):
        global running_job
        args = data.get("args", [])
        if not args:
            self._send_json({"error": "No args"}, 400)
            return

        # Validate: first token must be a known safe action
        SAFE = {"write", "draw", "svg", "sketch", "image", "fetch",
                "check", "calibrate", "approve", "cancel", "more", "less"}
        if args[0] not in SAFE:
            self._send_json({"error": "Unknown action"}, 400)
            return

        if sys.platform != "darwin" and "--no-obs" not in args:
            args = args + ["--no-obs"]
        cmd = [sys.executable, BOB_ROSS] + args
        env  = {**os.environ, "HUENIT_PORT": os.environ.get("HUENIT_PORT", "COM3")}

        print(f"\n{'='*52}")
        print(f"  >> {' '.join(args)}")
        print(f"{'='*52}\n", flush=True)

        def _run():
            global running_job, running_proc
            try:
                proc = subprocess.Popen(cmd, cwd=SCRIPT_DIR, env=env)
                with job_lock:
                    running_proc = proc
                proc.wait()
                print(f"\n[Control Center] Job finished.\n", flush=True)
            finally:
                with job_lock:
                    running_job = None
                    running_proc = None

        with job_lock:
            running_job = threading.Thread(target=_run, daemon=True)
            running_job.start()

        self._send_json({"ok": True, "command": " ".join(args)})

    def _post_sketch_preview(self, data):
        prompt = data.get("prompt", "").strip()
        if not prompt:
            self._send_json({"error": "No prompt"}, 400)
            return
        try:
            if os.path.exists(PENDING_STATE):
                os.unlink(PENDING_STATE)
        except Exception:
            pass
        _write_sketch_status("generating", prompt=prompt, brain=SKETCH_BRAIN)

        def _generate():
            svg_path = os.path.join(tempfile.gettempdir(), "ai_sketch.svg")
            ai_sketch = os.path.join(HUENIT_DIR, "ai_sketch.py")
            try:
                result = subprocess.run(
                    [sys.executable, ai_sketch, prompt, "--out", svg_path, "--brain", SKETCH_BRAIN],
                    timeout=SKETCH_TIMEOUT, capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                )
                if result.returncode == 0 and os.path.exists(svg_path):
                    with open(PENDING_STATE, "w") as f:
                        json.dump({"svg_path": svg_path, "prompt": prompt}, f)
                    _write_sketch_status("ready", prompt=prompt, brain=SKETCH_BRAIN)
                    print(f"[sketch-preview] SVG ready: {svg_path}", flush=True)
                else:
                    err = (result.stderr or result.stdout or "ai_sketch.py produced no SVG").strip()
                    _write_sketch_status("error", message=err[-400:], prompt=prompt, brain=SKETCH_BRAIN)
                    print(f"[sketch-preview] ai_sketch.py failed: {err}", flush=True)
            except subprocess.TimeoutExpired:
                _write_sketch_status("error", message=f"Timed out after {SKETCH_TIMEOUT}s — the model didn't respond in time.", prompt=prompt, brain=SKETCH_BRAIN)
                print(f"[sketch-preview] Timed out after {SKETCH_TIMEOUT}s", flush=True)
            except Exception as e:
                _write_sketch_status("error", message=str(e), prompt=prompt, brain=SKETCH_BRAIN)
                print(f"[sketch-preview] Error: {e}", flush=True)

        threading.Thread(target=_generate, daemon=True).start()
        self._send_json({"ok": True, "msg": "Generating sketch…"})

    def _post_calibrate(self):
        try:
            env = {**os.environ, "HUENIT_PORT": os.environ.get("HUENIT_PORT", "COM3")}
            bat = os.path.normpath(os.path.join(SCRIPT_DIR, "calibrate.bat"))
            if sys.platform == "win32":
                subprocess.Popen(
                    ['cmd', '/k', bat],
                    cwd=SCRIPT_DIR, env=env,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                subprocess.Popen(["open", "-a", "Terminal", "--args", "bash", "-c",
                                   f'"{sys.executable}" "{BOB_ROSS}" calibrate'],
                                 cwd=SCRIPT_DIR, env=env)
        except Exception as e:
            print(f"[Calibrate] Error: {e}", flush=True)
        self._send_json({"ok": True, "msg": "Calibration window opened"})

    def _post_cancel(self):
        global running_proc
        killed = False
        with job_lock:
            proc = running_proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                try: proc.wait(timeout=3)
                except subprocess.TimeoutExpired: proc.kill()
                killed = True
                print("\n[Control Center] Job cancelled by user.\n", flush=True)
            except Exception as e:
                print(f"[Cancel] Error: {e}", flush=True)
        # Clean up stale lock file
        try:
            if os.path.exists(JOB_LOCK_PATH):
                os.remove(JOB_LOCK_PATH)
        except Exception:
            pass
        self._send_json({"ok": True, "killed": killed})

    def _run_simple(self, args):
        cmd = [sys.executable, BOB_ROSS] + args
        subprocess.Popen(cmd, cwd=SCRIPT_DIR,
                         env={**os.environ, "HUENIT_PORT": os.environ.get("HUENIT_PORT", "COM3")})
        self._send_json({"ok": True})

    def _post_showcase_start(self, data):
        global showcase_proc
        with showcase_lock:
            if showcase_proc is not None and showcase_proc.poll() is None:
                self._send_json({"ok": True, "status": "already_running"})
                return
            args = [sys.executable, CHAT_ROSS]
            voice = data.get("voice", "voxtral")
            if voice in ("kokoro", "voxtral", "system"):
                args += ["--engine", voice]
            pyro = data.get("pyro", False)
            if pyro:
                args.append("--pyro")
            no_arm = data.get("no_arm", False)
            if no_arm:
                args.append("--no-arm")
            env = {**os.environ, "HUENIT_PORT": os.environ.get("HUENIT_PORT", "COM3")}
            showcase_proc = subprocess.Popen(args, cwd=SCRIPT_DIR, env=env)
        print(f"\n[Showcase] Started (pid {showcase_proc.pid})\n", flush=True)
        self._send_json({"ok": True, "status": "started", "pid": showcase_proc.pid})

    def _post_showcase_stop(self):
        global showcase_proc
        with showcase_lock:
            if showcase_proc is None or showcase_proc.poll() is not None:
                self._send_json({"ok": True, "status": "not_running"})
                return
            showcase_proc.terminate()
            try:
                showcase_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                showcase_proc.kill()
            showcase_proc = None
        print("\n[Showcase] Stopped.\n", flush=True)
        self._send_json({"ok": True, "status": "stopped"})

    def _post_chat(self, data):
        message = data.get("message", "").strip()
        if not message:
            self._send_json({"error": "No message"}, 400)
            return

        response = self._ask_ross(message)
        self._send_json({"response": response})

    # ── Apertus / Ollama ─────────────────────────────────────────────────────

    def _check_ollama(self):
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=2) as r:
                return r.status == 200
        except Exception:
            return False

    def _load_ledger(self):
        """Load LEDGER.md if it exists. Returns the content as a string, or empty string."""
        ledger_path = os.path.join(SCRIPT_DIR, "LEDGER.md")
        try:
            with open(ledger_path, encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _ask_ross(self, message):
        ledger = self._load_ledger()
        ledger_section = (
            f"\n\n---\nOPERATIONAL LEDGER (live data from orders.xlsx):\n{ledger}\n---"
            if ledger else ""
        )
        system = (
            "You are Robot Ross, a friendly AI-powered drawing robot inspired by Bob Ross. "
            "Speak warmly and enthusiastically. Keep replies to 2–3 sentences. "
            "If the user asks you to draw or write something specific, end your reply with a "
            "JSON block on its own line: {\"cmd\": \"sketch\", \"arg\": \"<subject>\"} "
            "or {\"cmd\": \"write\", \"arg\": \"<text>\"} etc. "
            "If asked about job history, statistics, past orders, turnaround times, MTBF, "
            "or any operational data, answer using the ledger below."
            + ledger_section
        )
        try:
            payload = json.dumps({
                "model": OLLAMA_MODEL,
                "prompt": message,
                "system": system,
                "stream": False,
            }).encode()
            req = urllib.request.Request(
                OLLAMA_URL, data=payload,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=120) as r:
                result = json.loads(r.read())
                return result.get("response", random.choice(FALLBACK_RESPONSES))
        except Exception:
            return random.choice(FALLBACK_RESPONSES)


# ── Entry point ───────────────────────────────────────────────────────────────

class _QuietServer(HTTPServer):
    def handle_error(self, request, client_address):
        import traceback
        exc = traceback.format_exc()
        if "ConnectionAbortedError" in exc or "BrokenPipeError" in exc:
            return  # browser closed connection early — harmless
        super().handle_error(request, client_address)

def main():
    server = _QuietServer(("localhost", PORT), Handler)
    banner = f"""
========================================
  Robot Ross Control Center
========================================

  Server : http://localhost:{PORT}
  Arm    : {os.environ.get("HUENIT_PORT", "COM3")}
  Python : {sys.executable}

  Your browser will open automatically.
  Keep this window open while drawing.
  Press Ctrl+C to stop.

========================================
"""
    print(banner, flush=True)

    def _open():
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{PORT}")

    threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Control Center] Stopped.\n")


if __name__ == "__main__":
    main()
