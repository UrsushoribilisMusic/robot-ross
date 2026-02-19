# Robot Ross — Artist-as-a-Service

> A Huenit robot arm that draws, narrates, and one day sells its work online.

---

## What Is This?

Robot Ross is an AI-powered drawing robot running on a Mac mini M4. It takes text prompts, SVG files, or Shopify orders, draws them on paper using a pen plotter arm, narrates the process in Bob Ross style using a local Swiss AI model, and records the session to video.

The end goal is a fully automated **Artist-as-a-Service**: customers buy a slot on a **10×10 Wall of Fame** via Shopify, the robot draws their piece live on YouTube, and ships the physical artwork.

---

## Architecture

Full diagram: `~/Downloads/robot-ross-architecture.txt`

```
 🛒 Shopify ──► Salesman VPS ──► Tailscale ──────────────────────┐
                                                                  │
 📱 Telegram ───────────────────────────────────────────────────► OpenClaw (Haiku)
                                                                       │
                                    ┌──────────────────────────────────┘
                                    ▼
 Google Quick Draw ◄── quickdraw_compose ◄──────────── bob_ross.py
 Internet URL      ◄── huenit_sketch    ◄────────────── ├── OBS Studio ──► ~/Movies/ ──► YouTube
 Local photo       ◄── image_to_svg     ◄────────────── ├── Apertus 8B (narration)
 Text/calligraphy  ◄── huenit_write     ◄────────────── └── order_log ──► orders.xlsx
                                    │
                               Huenit Arm
                            Paper · 10×10 board
```

---

## What's Built

### Phase 1 — Interactive Drawing (✅ Complete)

| Feature | File | Status |
|---|---|---|
| Write text / calligraphy | `huenit/huenit_write.py` | ✅ |
| Draw shapes (circle, square…) | `huenit/huenit_draw.py` | ✅ |
| Draw local SVG files | `huenit/huenit_svg.py` | ✅ |
| Photo → SVG → draw (vtracer) | `huenit/image_to_svg.py` | ✅ |
| Bob Ross narration via Apertus 8B | `robot-ross/bob_ross.py` | ✅ |
| Telegram preview → approve/cancel | `robot-ross/bob_ross.py` | ✅ |
| Job lock, caffeinate, SIGTERM stop | `robot-ross/bob_ross.py` | ✅ |
| Desktop .command shortcuts | `~/Desktop/` | ✅ |

### Phase 2 — Automated Studio (✅ Built, 🔧 Wiring in Progress)

| Feature | File | Status |
|---|---|---|
| Quick Draw compositional sketches | `huenit/quickdraw_compose.py` | ✅ |
| Internet SVG fetch with sanitisation | `huenit/huenit_sketch.py` | ✅ |
| OBS recording + streaming control | `robot-ross/obs_manager.py` | ✅ |
| OBS auto-start/stop per job | `robot-ross/bob_ross.py` | ✅ |
| Order ledger (orders.xlsx) | `robot-ross/order_log.py` | ✅ |
| Shopify order parsing in SOUL.md | `SOUL.md` | ✅ |
| Buyer name → personalised narration | `robot-ross/bob_ross.py` | ✅ |
| `--direct` flag (no preview for orders) | `robot-ross/bob_ross.py` | ✅ |
| Tailscale gateway (Artist ↔ Salesman) | `openclaw.json` | 🔧 Needs VPS |
| Salesman VPS + Shopify webhook | Cloud | 🔧 Pending |
| YouTube stream key configuration | OBS Settings | 🔧 Pending |

### Explored & Parked
- **Potrace image pipeline** (`huenit/image_to_svg_potrace.py`) — 14× fewer moves than vtracer but visual quality insufficient. Parked until tuning improves.
- **vpype linesort** — converts Bezier paths to dense polygon points, makes output worse. Discarded.

---

## Hardware

| Component | Details |
|---|---|
| Robot arm | Huenit, USB serial `/dev/cu.usbserial-310` |
| Computer | Mac mini M4, macOS Sequoia |
| Camera | Reolink 4K, IP `192.168.1.40` |
| Camera stream | `rtsp://admin:****@192.168.1.40:554/Preview_01_sub` |
| Studio software | OBS Studio 32 (Apple Silicon), WebSocket port 4455 |

---

## The 10×10 Wall of Fame

The final product is a **100-slot physical installation**. Each slot is a 10×10cm square on a large board. Customers buy a slot via Shopify and submit a prompt or design. Robot Ross draws it live on YouTube, the piece is mounted in its numbered slot, and the customer receives a photo/video proof and optionally the original paper artwork shipped to them.

- **Revenue model**: sell 100 slots × CHF X per slot
- **Content**: live YouTube drawing sessions, YouTube Shorts from each recording
- **Proof of work**: OBS recording saved per order, path logged in `orders.xlsx`
- **Physical fulfilment**: `orders.xlsx` tracks Posted and Shipped per order

---

## Running Locally

### Prerequisites

```bash
# Python deps
pip3 install pyserial vtracer pillow pillow-heif obsws-python openpyxl

# System
brew install potrace    # optional, for potrace pipeline
```

### Calibrate the arm

```bash
/usr/bin/python3 ~/.openclaw/workspace/skills/huenit/huenit_draw.py calibrate
```

### Interactive commands (via Telegram or terminal)

```bash
cd ~/.openclaw/workspace/skills/robot-ross

# Write text
/usr/bin/python3 bob_ross.py write "Hello World"

# Quick Draw sketch (preview first)
/usr/bin/python3 bob_ross.py sketch "a lighthouse on a rocky coast"

# Sketch direct (no preview — for automated orders)
/usr/bin/python3 bob_ross.py sketch "a cat on a fence" --direct --buyer "Alice"

# Draw SVG from internet
/usr/bin/python3 bob_ross.py fetch "https://example.com/drawing.svg"

# Approve / cancel pending preview
/usr/bin/python3 bob_ross.py approve
/usr/bin/python3 bob_ross.py cancel

# System check
/usr/bin/python3 bob_ross.py check
```

### OBS recording

```bash
# Status
/usr/bin/python3 obs_manager.py status

# Record only (no YouTube stream)
/usr/bin/python3 obs_manager.py start_show --record-only
/usr/bin/python3 obs_manager.py stop_show

# Update status overlay
/usr/bin/python3 obs_manager.py set-status "Drawing for Alice"
```

### Order ledger

```bash
/usr/bin/python3 order_log.py list
/usr/bin/python3 order_log.py set-video 5 "https://youtube.com/shorts/abc"
/usr/bin/python3 order_log.py set-posted 5
/usr/bin/python3 order_log.py set-shipped 5
```

---

## Automated Shopify Order Flow (Phase 2)

When fully wired, each order follows this sequence automatically:

```
1. Customer buys slot on Shopify
2. Shopify → webhook → Salesman VPS
3. Salesman → Tailscale → Artist gateway
4. Artist brain receives:
   ORDER #1042 | buyer: Alice | type: sketch | content: a lighthouse
5. bob_ross.py sketch "a lighthouse" --direct --buyer "Alice"
   → OBS starts recording
   → Apertus: "Good morning, Alice. Let's draw some happy little lines..."
   → Arm draws
   → OBS stops, .mov saved
   → order_log updated (received, produced, video path)
6. Artist replies: DONE #1042 | status: success | video: /path/to.mov
7. Salesman notifies customer via Telegram/email
```

---

## Key Files

```
workspace/
├── SOUL.md                         # Agent brain instructions
├── skills/
│   ├── robot-ross/
│   │   ├── bob_ross.py             # Main orchestrator
│   │   ├── obs_manager.py          # OBS WebSocket controller
│   │   ├── order_log.py            # Excel order ledger
│   │   └── orders.xlsx             # The ledger
│   ├── huenit/
│   │   ├── huenit_svg.py           # SVG → arm (Bezier-aware)
│   │   ├── huenit_write.py         # Text calligraphy
│   │   ├── huenit_draw.py          # Shapes + calibration
│   │   ├── huenit_sketch.py        # Internet SVG fetch + draw
│   │   ├── quickdraw_compose.py    # Ollama + Quick Draw scene composer
│   │   ├── quickdraw_to_svg.py     # Google Quick Draw → SVG
│   │   └── image_to_svg.py         # Photo → SVG (vtracer)
│   └── voice/
│       └── speak.py                # Kokoro TTS + fallback
```

---

## AI Stack

| Role | Model | Runtime |
|---|---|---|
| Brain (orders, decisions) | Claude Haiku 4.5 | Anthropic API |
| Narration | Apertus 8B (Swiss) | Ollama local |
| TTS | Kokoro | Local, espeak fallback |
| Scene parsing (Quick Draw) | Apertus 8B | Ollama local |

*Apertus is developed by MichelRosselli as part of an Innosuisse-funded project — proudly Swiss AI.*
