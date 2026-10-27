"""
test_tts.py — Compare Kokoro vs Voxtral TTS for Robot Ross narration.

Generates the same three Bob Ross phrases with both engines and plays them
back-to-back so you can A/B compare without running the full robot pipeline.

Usage:
    python test_tts.py                  # both engines
    python test_tts.py --kokoro         # Kokoro only
    python test_tts.py --voxtral        # Voxtral only
    python test_tts.py --voice gb_oliver_neutral  # different Voxtral voice (UK Oliver)
"""

import argparse
import os
import sys
import tempfile
import platform
if sys.platform == 'win32':
    import winsound

# ── Sample phrases (typical Robot Ross intro / commentary / outro) ────────────

SAMPLES = [
    ("Intro",      "Hello friends. Today we are going to paint something beautiful together."),
    ("Commentary", "See how the brush glides — just like a happy little river finding its way home."),
    ("Outro",      "And just like that, we have a finished painting. I hope it brought you joy."),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def play_wav(path):
    """Play WAV via winsound — converts to int16 PCM first if needed."""
    if sys.platform == 'darwin':
        import subprocess
        subprocess.run(['afplay', path], check=True)
        return
    import wave, struct
    try:
        # Try direct play first (works if already int16 PCM)
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_NODEFAULT)
        print("  [played]")
    except Exception as e:
        print(f"  [winsound direct failed: {e}] — trying soundfile playback...")
        try:
            import soundfile as sf
            import numpy as np
            audio, sr = sf.read(path, dtype="float32")
            # Convert to int16 PCM
            pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
            pcm_path = path.replace(".wav", "_pcm.wav")
            with wave.open(pcm_path, "w") as wf:
                wf.setnchannels(1 if pcm.ndim == 1 else pcm.shape[1])
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(pcm.tobytes())
            winsound.PlaySound(pcm_path, winsound.SND_FILENAME)
            print("  [played via PCM conversion]")
        except Exception as e2:
            print(f"  [ERROR] Could not play audio: {e2}")


def speak_kokoro(text, tmp_dir):
    try:
        import warnings
        warnings.filterwarnings("ignore")
        from kokoro import KPipeline
        import soundfile as sf
        import numpy as np
    except ImportError:
        print("  [ERROR] Kokoro not installed. Run: pip install kokoro soundfile numpy espeakng-loader")
        return

    global _kokoro_pipeline
    if "_kokoro_pipeline" not in globals():
        print("  Loading Kokoro pipeline (first run may take a moment)...")
        _kokoro_pipeline = KPipeline(lang_code="a")

    chunks = [audio for _, _, audio in _kokoro_pipeline(text, voice="am_michael", speed=0.92)]
    if not chunks:
        print("  [ERROR] Kokoro returned no audio.")
        return
    audio = np.concatenate(chunks)
    path = os.path.join(tmp_dir, "kokoro_sample.wav")
    sf.write(path, audio, 24000)
    play_wav(path)


def speak_voxtral(text, tmp_dir, voice="narrative_male"):
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        print("  [ERROR] MISTRAL_API_KEY not set. Run: set MISTRAL_API_KEY=your-key")
        return
    try:
        try:
            from mistralai.client.sdk import Mistral
        except ImportError:
            from mistralai import Mistral
    except ImportError:
        print("  [ERROR] mistralai not installed. Run: pip install mistralai")
        return

    client = Mistral(api_key=api_key)
    print(f"  Calling Voxtral API (voice={voice})...")
    response = client.audio.speech.complete(
        model="voxtral-mini-tts-latest",
        input=text,
        voice_id=voice,
        response_format="wav",
    )
    import base64
    audio_bytes = base64.b64decode(response.audio_data)
    path = os.path.join(tmp_dir, "voxtral_sample.wav")
    with open(path, "wb") as f:
        f.write(audio_bytes)
    play_wav(path)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kokoro",  action="store_true", help="Run Kokoro only")
    parser.add_argument("--voxtral", action="store_true", help="Run Voxtral only")
    parser.add_argument("--voice",   default="en_paul_neutral",
                        help="Voxtral voice slug (default: en_paul_neutral). "
                             "US male: en_paul_neutral/confident/cheerful/happy/excited/sad/frustrated/angry. "
                             "UK male: gb_oliver_neutral/confident/cheerful/excited/curious/sad/angry. "
                             "UK female: gb_jane_neutral/confident/curious/sarcasm/sad/frustrated/confused/jealousy/shameful. "
                             "French female: fr_marie_neutral/happy/excited/curious/sad/angry.")
    args = parser.parse_args()

    run_kokoro  = args.kokoro  or not args.voxtral
    run_voxtral = args.voxtral or not args.kokoro

    with tempfile.TemporaryDirectory() as tmp:
        for label, text in SAMPLES:
            print(f"\n-- {label} ------------------------------------------")
            print(f'   "{text}"')

            if run_kokoro:
                print("\n  [Kokoro]")
                speak_kokoro(text, tmp)
                input("  Press Enter for next...")

            if run_voxtral:
                print(f"\n  [Voxtral / {args.voice}]")
                speak_voxtral(text, tmp, voice=args.voice)
                if run_kokoro or label != SAMPLES[-1][0]:
                    input("  Press Enter for next...")

    print("\nDone.")


if __name__ == "__main__":
    main()
