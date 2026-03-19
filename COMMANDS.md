# Robot Ross — Command Cheat Sheet

## Setup (run once per session)

```cmd
cd C:\Users\migue\robot-ross
launch_local.bat
```

This opens a cmd shell with `HUENIT_PORT=COM3` already set.
Add this to every command window you open:
```cmd
set PYTHONIOENCODING=utf-8
```

---

## Step 1 — Calibrate (required before drawing)

```cmd
python skills\huenit\huenit_draw.py calibrate
```

Interactive. Jogs the pen to paper level so the arm knows Z_UP and Z_DOWN.
Must run once each time you power on the arm or change paper.

---

## Step 2 — Readiness Check

```cmd
python skills\robot-ross\bob_ross.py check
```

Verifies: arm port, calibration file, Ollama reachable, Apertus model loaded.
All green = ready to draw.

---

## Drawing Commands

All commands below go through `bob_ross.py` (narration + arm together).

### Write text

```cmd
python skills\robot-ross\bob_ross.py write "Hello World"
python skills\robot-ross\bob_ross.py write "OpenClaw" --size 15
python skills\robot-ross\bob_ross.py write "Hello World" --no-voice
```

- `--size N` — letter height in mm (default 10)
- `--no-voice` — skip narration, draw silently
- Max 255 characters. Long text auto-wraps at ~35 chars per line.

### Draw shapes

```cmd
python skills\robot-ross\bob_ross.py draw square
python skills\robot-ross\bob_ross.py draw circle
python skills\robot-ross\bob_ross.py draw triangle
python skills\robot-ross\bob_ross.py draw square 50
python skills\robot-ross\bob_ross.py draw circle 20
```

- Size argument is in mm (square/triangle = side length, circle = radius)
- Default size: 30mm square/triangle, 15mm circle radius

### Draw from SVG file

```cmd
python skills\robot-ross\bob_ross.py svg mydesign.svg
python skills\robot-ross\bob_ross.py svg mydesign.svg --size 80
```

- `--size N` — scales SVG so max dimension = N mm (default 125mm)
- SVG file can be in any folder — use full path if not in robot-ross dir
- Bare filename looks in `~/Downloads/` automatically

### Draw from image (photo → SVG → arm)

```cmd
python skills\robot-ross\bob_ross.py image photo.jpg
python skills\robot-ross\bob_ross.py image photo.jpg --size 100
```

Converts image to vector outline, sends preview to Telegram, waits for approval.

Then reply with:
```cmd
python skills\robot-ross\bob_ross.py approve     # draw it
python skills\robot-ross\bob_ross.py more        # more detail (+1000 segments)
python skills\robot-ross\bob_ross.py less        # less detail (-1000 segments)
python skills\robot-ross\bob_ross.py cancel      # discard
```

### AI sketch (Quick Draw style)

```cmd
python skills\robot-ross\bob_ross.py sketch "a cat on a bench"
python skills\robot-ross\bob_ross.py sketch "a rocket ship" --direct
```

- Without `--direct`: generates SVG, sends preview to Telegram, waits for approve/cancel
- `--direct`: skips preview, draws immediately

### Draw SVG from URL

```cmd
python skills\robot-ross\bob_ross.py fetch https://example.com/design.svg
```

Downloads and validates SVG, then draws it.

---

## Direct Scripts (no narration)

Use these for quick tests or when Ollama isn't running.

### Write text directly

```cmd
python skills\huenit\huenit_write.py "Hello World"
python skills\huenit\huenit_write.py "Hello" --size 8
python skills\huenit\huenit_write.py "Hello" --size 12 --feed 300
```

- `--size N` — letter height in mm (default 10)
- `--spacing N` — space between letters in mm (default 2)
- `--feed N` — drawing speed mm/min (default 400, lower = cleaner)

### Draw shapes directly

```cmd
python skills\huenit\huenit_draw.py square
python skills\huenit\huenit_draw.py square 40
python skills\huenit\huenit_draw.py circle 20
python skills\huenit\huenit_draw.py triangle 30
```

### Draw SVG directly

```cmd
python skills\huenit\huenit_svg.py mydesign.svg
python skills\huenit\huenit_svg.py mydesign.svg --size 80
python skills\huenit\huenit_svg.py mydesign.svg --dry-run
```

- `--size N` — max dimension in mm (default 125)
- `--dry-run` — parse SVG and print moves without connecting to arm

### Jog control (manual movement)

```cmd
python skills\huenit\huenit_jog_control.py
```

Arrow keys to jog XY, PgUp/PgDn for Z. Good for positioning the arm manually.

---

## Narration Only

Test TTS without the arm:
```cmd
python skills\voice\speak.py "Hello, I am Robot Ross"
```

---

## Common Options (bob_ross.py)

| Flag | Effect |
|------|--------|
| `--no-voice` | Skip Apertus + Kokoro narration |
| `--size N` | Drawing size in mm |
| `--buyer NAME` | Personalised narration ("Good morning, Miguel...") |
| `--direct` | Skip preview approval (sketch only) |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `HUENIT_PORT not found` | Run `launch_local.bat` or `set HUENIT_PORT=COM3` |
| `UnicodeEncodeError` | `set PYTHONIOENCODING=utf-8` |
| `Robot not calibrated` | Run `python skills\huenit\huenit_draw.py calibrate` |
| `Ollama not reachable` | Start Ollama app, then `ollama serve` |
| `Apertus model not found` | `ollama pull MichelRosselli/apertus:8b-instruct-2509-q4_k_m` |
| `pyserial not found` | `pip install pyserial` |
| Arm moves wrong | Power cycle arm, re-calibrate |

---

## Install Checklist (first time only)

```cmd
pip install pyserial vtracer pillow kokoro soundfile "numpy<2.0" espeakng-loader
ollama pull MichelRosselli/apertus:8b-instruct-2509-q4_k_m
```
