# Robot Ross — Command Cheat Sheet

## Setup (run once per session)

```cmd
cd C:\Users\migue\robot-ross
launch_local.bat
set PYTHONIOENCODING=utf-8
```

---

## Step 1 — Calibrate (required before drawing)

```cmd
python skills\huenit\huenit_draw.py calibrate
```

Interactive. Jogs the pen to find Z_UP and Z_DOWN.
Must run once each time you power on the arm or change paper height.

---

## Step 2 — Readiness Check

```cmd
python skills\robot-ross\bob_ross.py check
```

Verifies: arm port, calibration file, Ollama reachable, Apertus model loaded.

---

## bob_ross.py — Full Drawing Commands (with narration)

```
python skills\robot-ross\bob_ross.py <action> [content] [options]

Actions:
  write TEXT       Write text on paper
  draw SHAPE       Draw a shape
  svg FILE         Draw from an SVG file
  image FILE       Convert photo to SVG and draw
  sketch PROMPT    Generate AI Quick Draw sketch and draw
  fetch URL        Download SVG from internet and draw
  approve          Confirm and draw the last image/sketch preview
  cancel           Discard the pending preview
  more             Re-preview image with +1000 more segments (more detail)
  less             Re-preview image with -1000 fewer segments (less detail)
  check            Readiness check (no arm movement)
  calibrate        Run interactive Z calibration

Options:
  --size N         Size in mm (letter height for write, max dimension for svg/image)
  --no-voice       Skip Apertus narration and Kokoro TTS
  --buyer NAME     Personalised narration ("Good morning, Miguel...")
  --direct         sketch only: skip preview, draw immediately
```

---

## write — Text on paper

```cmd
python skills\robot-ross\bob_ross.py write "Hello World"
python skills\robot-ross\bob_ross.py write "Hello World" --size 15
python skills\robot-ross\bob_ross.py write "Hello World" --no-voice
python skills\robot-ross\bob_ross.py write "Hello World" --buyer Miguel
```

- Default letter height: 10mm
- Max 255 characters — long text auto-wraps at ~35 chars per line
- `--size` sets letter height in mm

---

## draw — Basic shapes

```cmd
python skills\robot-ross\bob_ross.py draw square
python skills\robot-ross\bob_ross.py draw square 50
python skills\robot-ross\bob_ross.py draw circle
python skills\robot-ross\bob_ross.py draw circle 20
python skills\robot-ross\bob_ross.py draw triangle
python skills\robot-ross\bob_ross.py draw triangle 40
```

Available shapes:

| Shape    | Size argument  | Default |
|----------|---------------|---------|
| square   | side in mm    | 30mm    |
| circle   | radius in mm  | 15mm    |
| triangle | side in mm    | 30mm    |

---

## svg — Draw from SVG file

```cmd
python skills\robot-ross\bob_ross.py svg mydesign.svg
python skills\robot-ross\bob_ross.py svg mydesign.svg --size 80
python skills\robot-ross\bob_ross.py svg C:\Users\migue\Downloads\logo.svg --size 100
```

- `--size N` — scales SVG so max dimension = N mm (default 125mm)
- Bare filename automatically looks in `~/Downloads/`

---

## image — Photo to drawing

```cmd
python skills\robot-ross\bob_ross.py image photo.jpg
python skills\robot-ross\bob_ross.py image photo.jpg --size 100
```

Converts image → vector outline → sends Telegram preview → waits for your reply:

```cmd
python skills\robot-ross\bob_ross.py approve     # draw it
python skills\robot-ross\bob_ross.py more        # more detail
python skills\robot-ross\bob_ross.py less        # less detail
python skills\robot-ross\bob_ross.py cancel      # discard
```

---

## sketch — AI Quick Draw sketch

```cmd
python skills\robot-ross\bob_ross.py sketch "a cat on a bench"
python skills\robot-ross\bob_ross.py sketch "a rocket ship" --direct
```

- Without `--direct`: sends preview to Telegram, waits for `approve` or `cancel`
- `--direct`: skips preview, draws immediately

---

## fetch — Draw SVG from URL

```cmd
python skills\robot-ross\bob_ross.py fetch https://example.com/design.svg
python skills\robot-ross\bob_ross.py fetch https://example.com/design.svg --size 80
```

---

## Direct Scripts — No narration

Use these for quick tests without Ollama running.

### huenit_write.py — Write text directly

```
python skills\huenit\huenit_write.py TEXT [options]

Options:
  --size N            Letter height in mm (default 10)
  --spacing N         Space between letters in mm (default 2)
  --feed N            Draw speed mm/min (default 400, lower = cleaner lines)
  --line-spacing N    Line height multiplier (default 1.5x letter height)
  --paper-width N     Usable paper width in mm — font auto-scales to fit (default 180)
  --margin N          Left+right margin in mm each side (default 10)
  --min-size N        Minimum font size mm — wraps to more lines rather than go smaller (default 5)
  --sound FILE        Play an MP3 before drawing starts
```

Examples:
```cmd
python skills\huenit\huenit_write.py "Hello World"
python skills\huenit\huenit_write.py "Hello" --size 12
python skills\huenit\huenit_write.py "Hello" --size 8 --feed 300
```

### huenit_draw.py — Draw shapes directly

```
python skills\huenit\huenit_draw.py SHAPE [size]

Shapes:
  calibrate           Interactive Z calibration (pen-down finder)
  square [size_mm]    Draw a square (default 30mm side)
  triangle [size_mm]  Draw a triangle (default 30mm side)
  circle [radius_mm]  Draw a circle (default 15mm radius)
  demo                Draw all three shapes in a row
```

Examples:
```cmd
python skills\huenit\huenit_draw.py calibrate
python skills\huenit\huenit_draw.py square
python skills\huenit\huenit_draw.py square 50
python skills\huenit\huenit_draw.py circle 20
python skills\huenit\huenit_draw.py triangle 40
python skills\huenit\huenit_draw.py demo
```

### huenit_svg.py — Draw SVG directly

```
python skills\huenit\huenit_svg.py FILE [options]

Options:
  --size N    Max dimension in mm (default 80)
  --feed N    Drawing speed mm/min (default 250)
  --dry-run   Parse SVG and print moves — no arm connection needed
```

Examples:
```cmd
python skills\huenit\huenit_svg.py mydesign.svg
python skills\huenit\huenit_svg.py mydesign.svg --size 100
python skills\huenit\huenit_svg.py mydesign.svg --feed 200
python skills\huenit\huenit_svg.py mydesign.svg --dry-run
```

### image_to_svg.py — Convert image to SVG (without drawing)

```
python skills\huenit\image_to_svg.py IMAGE [options]

Options:
  --out FILE          Output SVG path (default: same folder as input)
  --threshold N       B&W threshold 0-255 (default 128 — lower = more black)
  --contrast N        Contrast boost before threshold (default 2.0)
  --max-px N          Resize to max N pixels on longest side (default 800)
  --blur N            Gaussian blur radius (default 1.5)
  --speckle N         Ignore islands smaller than N px (default 8)
  --corner N          Corner threshold in degrees (default 60)
  --smoothness N      Path smoothness — higher = fewer nodes (default 6.0)
  --edges             Edge detection mode — outlines/silhouette only (best for portraits)
  --auto              Auto-tune smoothness/speckle to reach ~4000 segments
  --preview           Open the SVG when done
```

Examples:
```cmd
python skills\huenit\image_to_svg.py photo.jpg
python skills\huenit\image_to_svg.py photo.jpg --edges --auto
python skills\huenit\image_to_svg.py photo.jpg --out logo.svg --max-px 1200
```

Then draw the result:
```cmd
python skills\huenit\huenit_svg.py photo.svg --size 100
```

### huenit_jog_control.py — Manual jog

```cmd
python skills\huenit\huenit_jog_control.py
```

| Key         | Action          |
|-------------|-----------------|
| Arrow keys  | Move X / Y      |
| W / S       | Move Z up / down|
| + / -       | Change jog speed|
| A           | Vacuum ON       |
| D           | Vacuum OFF      |
| Q / ESC     | Quit            |

### speak.py — Test TTS only

```cmd
python skills\voice\speak.py "Hello, I am Robot Ross"
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `HUENIT_PORT not found` | `set HUENIT_PORT=COM3` |
| `UnicodeEncodeError` | `set PYTHONIOENCODING=utf-8` |
| `Robot not calibrated` | `python skills\huenit\huenit_draw.py calibrate` |
| `Ollama not reachable` | Start Ollama, then `ollama serve` |
| `Apertus model not found` | `ollama pull MichelRosselli/apertus:8b-instruct-2509-q4_k_m` |
| `pyserial not found` | `pip install pyserial` |
| Arm moves wrong | Power cycle arm, re-calibrate |
| Pen too light | Adjust Z_DOWN lower in calibration |
| Lines wobbly | Reduce `--feed` to 200-300 |

---

## Install Checklist (first time only)

```cmd
pip install pyserial vtracer pillow kokoro soundfile "numpy<2.0" espeakng-loader
ollama pull MichelRosselli/apertus:8b-instruct-2509-q4_k_m
```
