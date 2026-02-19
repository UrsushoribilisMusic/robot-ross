---
name: robot-ross
description: Robot Ross — AI-powered drawing robot. Takes text, sketches, or Shopify orders, draws on paper with a Huenit arm, narrates in Bob Ross style via Apertus 8B, and records the session to video via OBS.
metadata: {"openclaw": {"emoji": "🎨", "requires": {"os": ["darwin"]}}}
---

# Robot Ross

The robot arm draws on paper while narrating poetically in Bob Ross style. Every job is automatically recorded by OBS and logged to the order ledger.

## Commands

### Write text (calligraphy)
```bash
/usr/bin/python3 bob_ross.py write "Im a movie star"
/usr/bin/python3 bob_ross.py write "Hello\nWorld" --size 15
```

### Quick Draw sketch (preview → approve/cancel)
```bash
/usr/bin/python3 bob_ross.py sketch "a cat sitting on a fence"
# → sends PNG preview to Telegram, waits for "draw" or "cancel"
/usr/bin/python3 bob_ross.py approve
/usr/bin/python3 bob_ross.py cancel
```

### Quick Draw sketch — direct (no preview, for orders)
```bash
/usr/bin/python3 bob_ross.py sketch "a lighthouse" --direct --buyer "Alice"
```

### Draw SVG from the internet
```bash
/usr/bin/python3 bob_ross.py fetch "https://example.com/drawing.svg"
```

### Draw local SVG
```bash
/usr/bin/python3 bob_ross.py svg /path/to/file.svg
```

### Draw from photo (preview → approve)
```bash
/usr/bin/python3 bob_ross.py image ~/.openclaw/media/inbound/photo.jpg
```

### Shapes
```bash
/usr/bin/python3 bob_ross.py draw circle
/usr/bin/python3 bob_ross.py draw square
```

### System
```bash
/usr/bin/python3 bob_ross.py check       # readiness check
/usr/bin/python3 bob_ross.py calibrate   # interactive calibration
```

## Flags
- `--buyer "Name"` — personalises Apertus narration ("Good morning, Alice...")
- `--direct` — sketch only: skips Telegram preview, draws immediately
- `--no-voice` — silent draw (no narration)
- `--size N` — override size in mm

## Job lifecycle (automatic)
1. Readiness check (arm + calibration + Ollama)
2. Job lock acquired (`/tmp/robot_ross_running.lock`)
3. OBS recording starts (Workspace → Artist scene)
4. caffeinate prevents Mac sleep
5. Apertus generates narration
6. Warning beeps — stand clear
7. Arm draws + live commentary in parallel
8. OBS stops, recording saved to `~/Movies/`
9. Order ledger updated (orders.xlsx)
10. Lock released

## Stop the arm
Send `SIGTERM` to the process, or use the Stop Robot Ross desktop shortcut.
The arm lifts the pen and halts safely.

## Notes
- Calibrate at the start of each session: `huenit_draw.py calibrate`
- Delete `/tmp/robot_ross_running.lock` manually if the process crashed
- OBS must be running for recording to work (job proceeds either way)
- Port override: `HUENIT_PORT=/dev/cu.usbserial-XXX python3 bob_ross.py ...`
