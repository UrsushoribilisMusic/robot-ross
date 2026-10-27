import os
import sys
import subprocess
import tempfile
import platform
import base64

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

    os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
    import warnings as _warnings
    _warnings.filterwarnings("ignore", message=".*unauthenticated.*", category=UserWarning)
    _warnings.filterwarnings("ignore", message=".*HF_TOKEN.*")

    def _get_pipeline():
        global _pipeline
        if _pipeline is None:
            _pipeline = KPipeline(lang_code=KOKORO_LANG, repo_id='hexgrad/Kokoro-82M')
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


# ── Voxtral TTS (Mistral API) ─────────────────────────────────────────────────
VOXTRAL_VOICE = "fr_marie_neutral"
VOXTRAL_MODEL = "voxtral-mini-tts-latest"

# Whisper language name → Voxtral voice slug
# Available voices: fr_marie_* (French), gb_jane_* (British EN), en_paul_* (US EN)
# Voxtral is multilingual — fr_marie speaks German/Spanish/Italian natively
VOXTRAL_LANG_VOICES = {
    "french":     "fr_marie_neutral",
    "german":     "fr_marie_neutral",   # fr_marie speaks German natively
    "spanish":    "fr_marie_neutral",   # fr_marie speaks Spanish natively
    "english":    "gb_jane_neutral",
    "italian":    "fr_marie_neutral",   # fr_marie speaks Italian natively
    "portuguese": "fr_marie_neutral",
}


def _speak_voxtral(text, voice=None):
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        print("  Voxtral: no API key; using system speech", file=sys.stderr)
        _speak_fallback(text)
        return
    try:
        try:
            from mistralai.client.sdk import Mistral
        except ImportError:
            from mistralai import Mistral
    except ImportError:
        print("  Voxtral: SDK unavailable; using system speech", file=sys.stderr)
        _speak_fallback(text)
        return
    client = Mistral(api_key=api_key)
    try:
        speech = client.audio.speech
    except AttributeError:
        print("  Voxtral: audio.speech not available in this SDK version — falling back", file=sys.stderr)
        _speak_fallback(text)
        return
    response = speech.complete(
        model=VOXTRAL_MODEL,
        input=text,
        voice_id=voice or VOXTRAL_VOICE,
        response_format="wav",
    )
    audio_bytes = base64.b64decode(response.audio_data)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        with open(tmp, "wb") as f:
            f.write(audio_bytes)
        _play_wav(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# ── Beeps ─────────────────────────────────────────────────────────────────────
def _three_beeps():
    import time
    for _ in range(3):
        if _IS_WINDOWS:
            import winsound
            winsound.Beep(1000, 200)
        elif _IS_MAC:
            subprocess.run(["afplay", "/System/Library/Sounds/Ping.aiff"],
                           capture_output=True, timeout=3)
        else:
            subprocess.run(["beep"], capture_output=True, timeout=3)
        time.sleep(0.4)


# ── Public API ────────────────────────────────────────────────────────────────
def speak(text, dual=False, engine="kokoro", voice=None):
    """
    Speak text.
    engine: 'kokoro' (local), 'voxtral' (Mistral API), 'system' (OS fallback)
    dual: 3 beeps → Kokoro → Voxtral (A/B demo mode)
    """
    print(f"Narrating: {text}")
    if dual:
        _three_beeps()
        if KOKORO_AVAILABLE:
            try:
                print("  [Kokoro]")
                _speak_kokoro(text)
            except Exception as e:
                print(f"  Kokoro failed ({e})", file=sys.stderr)
        print("  [Voxtral]")
        _speak_voxtral(text)
        return

    if engine == "voxtral":
        _speak_voxtral(text, voice=voice)
    elif engine == "kokoro":
        if KOKORO_AVAILABLE:
            try:
                _speak_kokoro(text)
                return
            except Exception as e:
                print(f"  Kokoro TTS failed ({e}) — falling back to system TTS",
                      file=sys.stderr)
        _speak_fallback(text)
    else:
        _speak_fallback(text)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="?",
                        default="Hello, I am Robot Ross, and today we will make some happy little drawings.")
    parser.add_argument("--dual",   action="store_true",
                        help="Play beeps, then Kokoro, then Voxtral for the same phrase")
    parser.add_argument("--engine", default="kokoro", choices=["kokoro", "voxtral", "system"],
                        help="TTS engine (default: kokoro)")
    parser.add_argument("--voice",  default=None,
                        help="Voxtral voice ID override (e.g. fr_marie_neutral, de_anna_neutral)")
    args = parser.parse_args()
    speak(args.text, dual=args.dual, engine=args.engine, voice=args.voice)
