import os
import sys
import subprocess
import tempfile

# ── Kokoro TTS (preferred — warm neural voice on Apple Silicon) ───────────────
# Install: pip install kokoro soundfile numpy && brew install espeak
# First run downloads the model (~300MB, cached afterwards).
KOKORO_VOICE = "am_michael"   # warm American male voice
KOKORO_SPEED = 0.92            # slightly slower for a calm, warm feel
KOKORO_LANG  = "a"             # American English

try:
    import warnings
    warnings.filterwarnings("ignore")
    # Ensure Homebrew bin is in PATH so Kokoro can find espeak
    import os as _os
    _brew_bin = "/opt/homebrew/bin"
    if _brew_bin not in _os.environ.get("PATH", ""):
        _os.environ["PATH"] = _brew_bin + ":" + _os.environ.get("PATH", "")
    from kokoro import KPipeline
    import soundfile as sf
    import numpy as np
    _pipeline = None   # lazy-loaded on first use

    def _get_pipeline():
        global _pipeline
        if _pipeline is None:
            _pipeline = KPipeline(lang_code=KOKORO_LANG)
        return _pipeline

    def _speak_kokoro(text):
        pipeline = _get_pipeline()
        chunks = [audio for _, _, audio in
                  pipeline(text, voice=KOKORO_VOICE, speed=KOKORO_SPEED)]
        if not chunks:
            return
        audio = np.concatenate(chunks)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
        try:
            sf.write(tmp, audio, 24000)
            subprocess.run(["afplay", tmp], check=True)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    KOKORO_AVAILABLE = True

except ImportError:
    KOKORO_AVAILABLE = False


# ── Fallback: macOS built-in say ──────────────────────────────────────────────
def _speak_say(text):
    subprocess.run(["say", "-v", "Evan", "-r", "160", text])


# ── Public API ────────────────────────────────────────────────────────────────
def speak(text):
    print(f"Narrating: {text}")
    if KOKORO_AVAILABLE:
        try:
            _speak_kokoro(text)
            return
        except Exception as e:
            print(f"  ⚠ Kokoro TTS failed ({e}) — falling back to say",
                  file=sys.stderr)
    _speak_say(text)


if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
        "Hello, I am Robot Ross, and today we will make some happy little drawings."
    speak(msg)
