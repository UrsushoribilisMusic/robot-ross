"""
test_voices.py -- Play a Bob Ross quote in all 30 Voxtral voices.
French voices get the French translation automatically.

Usage:
    python test_voices.py
    python test_voices.py --no-pause   # no Enter between voices
"""

import argparse
import base64
import os
import sys
import tempfile
import winsound

EN_PHRASE = "There are no mistakes, only happy little accidents."
FR_PHRASE = "Il n'y a pas d'erreurs, seulement de joyeux petits accidents."

VOICES = [
    # (slug, display_name, lang)
    ("en_paul_neutral",    "Paul - Neutral    (US)",  "en"),
    ("en_paul_confident",  "Paul - Confident  (US)",  "en"),
    ("en_paul_cheerful",   "Paul - Cheerful   (US)",  "en"),
    ("en_paul_happy",      "Paul - Happy      (US)",  "en"),
    ("en_paul_excited",    "Paul - Excited    (US)",  "en"),
    ("en_paul_sad",        "Paul - Sad        (US)",  "en"),
    ("en_paul_frustrated", "Paul - Frustrated (US)",  "en"),
    ("en_paul_angry",      "Paul - Angry      (US)",  "en"),
    ("gb_oliver_neutral",  "Oliver - Neutral    (UK)", "en"),
    ("gb_oliver_confident","Oliver - Confident  (UK)", "en"),
    ("gb_oliver_cheerful", "Oliver - Cheerful   (UK)", "en"),
    ("gb_oliver_excited",  "Oliver - Excited    (UK)", "en"),
    ("gb_oliver_curious",  "Oliver - Curious    (UK)", "en"),
    ("gb_oliver_sad",      "Oliver - Sad        (UK)", "en"),
    ("gb_oliver_angry",    "Oliver - Angry      (UK)", "en"),
    ("gb_jane_neutral",    "Jane - Neutral    (UK)",  "en"),
    ("gb_jane_confident",  "Jane - Confident  (UK)",  "en"),
    ("gb_jane_curious",    "Jane - Curious    (UK)",  "en"),
    ("gb_jane_sarcasm",    "Jane - Sarcasm    (UK)",  "en"),
    ("gb_jane_sad",        "Jane - Sad        (UK)",  "en"),
    ("gb_jane_frustrated", "Jane - Frustrated (UK)",  "en"),
    ("gb_jane_confused",   "Jane - Confused   (UK)",  "en"),
    ("gb_jane_jealousy",   "Jane - Jealousy   (UK)",  "en"),
    ("gb_jane_shameful",   "Jane - Shameful   (UK)",  "en"),
    ("fr_marie_neutral",   "Marie - Neutral   (FR)",  "fr"),
    ("fr_marie_happy",     "Marie - Happy     (FR)",  "fr"),
    ("fr_marie_excited",   "Marie - Excited   (FR)",  "fr"),
    ("fr_marie_curious",   "Marie - Curious   (FR)",  "fr"),
    ("fr_marie_sad",       "Marie - Sad       (FR)",  "fr"),
    ("fr_marie_angry",     "Marie - Angry     (FR)",  "fr"),
]


def play_wav(path):
    try:
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_NODEFAULT)
    except Exception:
        import wave, numpy as np, soundfile as sf
        audio, sr = sf.read(path, dtype="float32")
        pcm = (audio * 32767).astype(np.int16)
        pcm_path = path.replace(".wav", "_pcm.wav")
        with wave.open(pcm_path, "w") as wf:
            wf.setnchannels(1 if pcm.ndim == 1 else pcm.shape[1])
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm.tobytes())
        winsound.PlaySound(pcm_path, winsound.SND_FILENAME)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-pause", action="store_true",
                        help="Play all voices without pausing between them")
    parser.add_argument("--voice", default=None,
                        help="Play a single voice slug, e.g. --voice gb_oliver_cheerful")
    args = parser.parse_args()

    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        print("ERROR: MISTRAL_API_KEY not set.")
        sys.exit(1)

    try:
        from mistralai.client.sdk import Mistral
    except ImportError:
        from mistralai import Mistral

    client = Mistral(api_key=api_key)

    print(f"Testing {len(VOICES)} voices\n")
    print(f"  EN: \"{EN_PHRASE}\"")
    print(f"  FR: \"{FR_PHRASE}\"\n")

    voices = [(s, n, l) for s, n, l in VOICES if not args.voice or s == args.voice]
    if not voices:
        print(f"ERROR: voice '{args.voice}' not found. Check the slug list.")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp:
        for i, (slug, name, lang) in enumerate(voices, 1):
            phrase = FR_PHRASE if lang == "fr" else EN_PHRASE
            print(f"[{i:2}/{len(VOICES)}] {name}  ({slug})")

            resp = client.audio.speech.complete(
                model="voxtral-mini-tts-latest",
                input=phrase,
                voice_id=slug,
                response_format="wav",
            )
            wav_path = os.path.join(tmp, f"{slug}.wav")
            with open(wav_path, "wb") as f:
                f.write(base64.b64decode(resp.audio_data))

            play_wav(wav_path)

            if not args.no_pause and i < len(voices):
                input("  Press Enter for next...")

    print("\nAll voices done.")


if __name__ == "__main__":
    main()
