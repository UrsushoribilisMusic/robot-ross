import os
import sys
import subprocess
import tempfile
import platform

# ── Kokoro TTS (preferred — warm neural voice) ────────────────────────────────
# Install: pip install kokoro soundfile "numpy<2.0" espeakng-loader
# First run downloads the model (~300MB, cached afterwards).
KOKORO_VOICE = "am_michael"   # warm American male voice
KOKORO_SPEED = 0.92            # slightly slower for a calm, warm feel
KOKORO_LANG  = "a"             # American English

_IS_WINDOWS = platform.system() == "Windows"
_IS_MAC     = platform.system() == "Darwin"

try:
    import warnings
    warnings.filterwarnings("ignore")
    if _IS_MAC:
        # Ensure Homebrew bin is in PATH so Kokoro can find espeak
        _brew_bin = "/opt/homebrew/bin"
        if _brew_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = _brew_bin + ":" + os.environ.get("PATH", "")
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
            _play_wav(tmp)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    KOKORO_AVAILABLE = True

except ImportError:
    KOKORO_AVAILABLE = False


# ── Platform audio player ─────────────────────────────────────────────────────
def _play_wav(path):
    """Play a WAV file using the best available method for this OS."""
    if _IS_WINDOWS:
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME)
    elif _IS_MAC:
        subprocess.run(["afplay", path], check=True)
    else:
        # Linux fallback
        subprocess.run(["aplay", path], check=True)


# ── Fallback TTS (no Kokoro) ──────────────────────────────────────────────────
def _speak_fallback(text):
    if _IS_WINDOWS:
        # Windows built-in speech synthesis via PowerShell — no extra install needed
        safe = text.replace("'", "\\'")
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Add-Type -AssemblyName System.Speech; "
             f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
             f"$s.Rate = 1; $s.Speak('{safe}')"],
            check=False,
        )
    elif _IS_MAC:
        subprocess.run(["say", "-v", "Evan", "-r", "160", text])
    else:
        # Linux: espeak fallback
        subprocess.run(["espeak", "-s", "150", text], check=False)


# ── Public API ────────────────────────────────────────────────────────────────
def speak(text):
    print(f"Narrating: {text}")
    if KOKORO_AVAILABLE:
        try:
            _speak_kokoro(text)
            return
        except Exception as e:
            print(f"  Kokoro TTS failed ({e}) — falling back to system TTS",
                  file=sys.stderr)
    _speak_fallback(text)


if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
        "Hello, I am Robot Ross, and today we will make some happy little drawings."
    speak(msg)
