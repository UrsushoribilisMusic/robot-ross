# Robot Ross — Artist-as-a-Service

> A Huenit robot arm that draws, narrates, and sells its work online.

---

## What Is This?

Robot Ross is an AI-powered drawing robot running on a Mac mini M4. It takes text prompts, SVG files, or Shopify orders, draws them on paper using a pen plotter arm, narrates the process in Bob Ross style using a local Swiss AI model, and records the session to video.

The end goal is a fully automated **Artist-as-a-Service**: customers buy a slot on a **10×10 Wall of Fame** via Shopify, the robot draws their piece live on YouTube, and ships the physical artwork.

---

## Architecture

Full diagram: `~/Downloads/robot-ross-architecture.txt`

```
 🛒 Shopify ──► Salesman VPS ──► artist_poller.py (polls every 180s) ──┐
                (api.robotross.art, HTTPS)                              │
 📱 Telegram ───────────────────────────────────────────────────────► OpenClaw (Haiku)
                                                                             │
                                    ┌────────────────────────────────────────┘
                                    ▼
 Google Quick Draw ◄── quickdraw_compose ◄──────────── bob_ross.py
 Internet URL      ◄── huenit_sketch    ◄────────────── ├── OBS ──► ffmpeg ──► YouTube (unlisted)
 Local photo       ◄── image_to_svg     ◄────────────── ├── Apertus 8B (narration)
 Text/calligraphy  ◄── huenit_write     ◄────────────── └── order_log ──► orders.xlsx
                                    │                              │
                               Huenit Arm (≤125mm)                 └──► artist_poller ──► Salesman
                            Paper · 10×10 board                         (proof-of-work URL)
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

### Phase 2 — Automated Studio (✅ Built)

| Feature | File | Status |
|---|---|---|
| Quick Draw compositional sketches | `huenit/quickdraw_compose.py` | ✅ |
| Internet SVG fetch with sanitisation | `huenit/huenit_sketch.py` | ✅ |
| OBS recording + streaming control | `robot-ross/obs_manager.py` | ✅ |
| OBS auto-start/stop per job | `robot-ross/bob_ross.py` | ✅ |
| Trim recording to start after last beep | `robot-ross/bob_ross.py` | ✅ PR #8 |
| Wrap long write-text into multiple lines | `huenit/huenit_write.py` | ✅ PR #10 |
| Drawing area hard-capped at 125mm | `robot-ross/bob_ross.py` | ✅ PR #14 |
| Font digits 0–9 complete | `huenit/huenit_write.py` | ✅ PR #14 |
| Order ledger (orders.xlsx) | `robot-ross/order_log.py` | ✅ |
| YouTube Shorts upload (OAuth2) | `robot-ross/youtube_upload.py` | ✅ PR #7 |
| Buyer name → personalised narration | `robot-ross/bob_ross.py` | ✅ |
| `--direct` flag (no preview for orders) | `robot-ross/bob_ross.py` | ✅ |
| Salesman REST API client | `robot-ross/salesman_client.py` | ✅ |
| Artist order poller (auto-start on login) | `robot-ross/artist_poller.py` | ✅ |
| Tailscale gateway (Artist ↔ Salesman) | `openclaw.json` | 🔧 Needs VPS |
| Salesman: populate type/content/buyer from Shopify (#13) | Cloud | 🔧 agent:gemini |
| YouTube stream key configuration | OBS Settings | 🔧 Pending |

### Explored & Parked
- **Potrace image pipeline** (`huenit/image_to_svg_potrace.py`) — 14× fewer moves than vtracer but visual quality insufficient. Parked until tuning improves.
- **vpype linesort** — converts Bezier paths to dense polygon points, makes output worse. Discarded.

---

## Hardware

| Component | Details |
|---|---|
| Robot arm | Huenit, USB serial `/dev/cu.usbserial-310`, z_up: 6.0mm |
| Drawing area | Hard-capped at 125mm (physical limit confirmed 120–125mm) |
| Computer | Mac mini M4, macOS Sequoia |
| Camera | Reolink 4K, IP `192.168.1.40` |
| Camera stream | `rtsp://admin:****@192.168.1.40:554/Preview_01_sub` |
| Studio software | OBS Studio 32 (Apple Silicon), WebSocket port 4455 |

---

## The 10×10 Wall of Fame

The final product is a **100-slot physical installation**. Each slot is a 10×10cm square on a large board. Customers buy a slot via Shopify and submit a prompt or design. Robot Ross draws it live on YouTube, the piece is mounted in its numbered slot, and the customer receives a photo/video proof and optionally the original paper artwork shipped to them.

- **Revenue model**: sell 100 slots × CHF X per slot
- **Content**: live YouTube drawing sessions, YouTube Shorts from each recording
- **Proof of work**: OBS recording saved per order, URL logged in `orders.xlsx`
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

# Write text (auto-scaled to ≤125mm paper width)
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

### Artist order poller

The poller auto-starts on login via LaunchAgent. To run manually:

```bash
# Start with caffeinate (prevents sleep during draws)
caffeinate -d -i /usr/bin/python3 artist_poller.py

# Check poller log
tail -f ~/.openclaw/workspace/skills/robot-ross/poller.log

# LaunchAgent (auto-start on login, auto-restart on crash)
# ~/Library/LaunchAgents/com.robotross.poller.plist
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

### YouTube Shorts upload

```bash
# First-time setup dependencies
/usr/bin/python3 -m pip install google-api-python-client google-auth-oauthlib google-auth-httplib2

# Upload a local OBS recording (OAuth token stored locally after first login)
/usr/bin/python3 youtube_upload.py ~/Movies/robot-ross.mov --buyer "Alice" --prompt "a lighthouse on a rocky coast"
```

### Order ledger

```bash
/usr/bin/python3 order_log.py list
/usr/bin/python3 order_log.py set-video 5 "https://youtube.com/shorts/abc"
/usr/bin/python3 order_log.py set-posted 5
/usr/bin/python3 order_log.py set-shipped 5
```

---

## Order Ledger (orders.xlsx)

Every order is tracked in `skills/robot-ross/orders.xlsx` with the following columns:

| Column | Set by | Description |
|---|---|---|
| Received At | `order_log.start()` auto | Timestamp when bob_ross.py accepted the order |
| Buyer | `order_log.start()` auto | Customer name from Shopify / Telegram |
| Order Type | `order_log.start()` auto | `write`, `sketch`, `svg`, `fetch`, `draw`, `image` |
| Content | `order_log.start()` auto | The text prompt or file path |
| Produced At | `order_log.end()` auto | Timestamp when the drawing completed |
| Status | `order_log.end()` auto | `success` or `failed` |
| Video URL | `order_log.set_video()` auto | YouTube Shorts URL (set by artist_poller after upload) |
| Posted | `order_log.set-posted` manual | Marked when the YouTube Shorts link has been shared |
| Shipped | `order_log.set-shipped` manual | Marked when physical artwork has been mailed |

The Video URL column is also read back by `artist_poller.py` via `get_last_video_url()` to include the YouTube proof link in the `complete()` call back to Salesman.

### Drawing area test

```bash
# Draws concentric squares at 100–180mm to verify arm travel limits
/usr/bin/python3 draw_size_test.py
```

---

## Automated Shopify Order Flow (Phase 2)

```mermaid
sequenceDiagram
    actor Buyer
    participant Shopify
    participant Salesman as Salesman VPS
    participant Poller as artist_poller.py
    participant BobRoss as bob_ross.py
    participant Arm as Huenit Arm
    participant YouTube
    participant Ledger as orders.xlsx

    Buyer->>Shopify: Purchases slot (type, content, name)
    Shopify->>Salesman: POST /webhook/orders/paid
    Salesman->>Salesman: Adds order to backlog (status=new)

    loop Every 180s
        Poller->>Salesman: GET /salesman/orders/incoming?status=new
        Salesman-->>Poller: order { id, type, content, buyer }
    end

    Poller->>Salesman: POST /orders/:id/claim (idempotency key)
    Poller->>Salesman: POST /orders/:id/ack
    Poller->>Ledger: order_log.start() → row (Received At, Buyer, Type, Content)

    Poller->>BobRoss: bob_ross.py <type> <content> --direct --buyer <name>
    BobRoss->>BobRoss: OBS start recording + warning beep
    BobRoss->>Arm: Draw artwork (≤125mm, G-code over USB serial)
    BobRoss->>BobRoss: Apertus narration (Bob Ross style)
    BobRoss->>BobRoss: OBS stop + ffmpeg trim (cut dead air before beep)
    BobRoss->>YouTube: Upload trimmed .mov as private YouTube Short
    YouTube-->>BobRoss: YouTube URL
    BobRoss->>Ledger: order_log.end() → Status, Produced At, Video URL

    Poller->>Ledger: get_last_video_url()
    Ledger-->>Poller: https://youtu.be/...
    Poller->>Salesman: POST /orders/:id/complete { proofType: youtube, proofUrl }

    Note over Salesman,Shopify: ⚠️ Pending (issue #13 / agent:gemini)
    Salesman-->>Shopify: Update order with proof-of-work video URL
    Salesman-->>Buyer: Notify via Telegram / email with video link
```

### Status of each step

| Step | Status |
|---|---|
| Shopify → Salesman webhook | ✅ Live (Robot Ross store) |
| Salesman order backlog | ✅ `/incoming?status=new` queue |
| Artist polls Salesman | ✅ `artist_poller.py` every 180s, auto-starts on login |
| Atomic claim (prevent double-draw) | ✅ idempotency key + HTTP 409 guard |
| Drawing sequence + OBS recording | ✅ `bob_ross.py` |
| Video trim (remove dead air) | ✅ ffmpeg after last beep |
| YouTube upload + order ledger update | ✅ `youtube_upload.py` + `order_log` |
| Artist → Salesman proof-of-work callback | ✅ `sc.complete(video_url=...)` |
| Salesman → Shopify order update with video | ⚠️ Pending — issue #13 (agent:gemini) |
| Customer notification (Telegram / email) | ⚠️ Pending — issue #13 (agent:gemini) |

---

## Key Files

```
workspace/
├── SOUL.md                         # Agent brain instructions
├── skills/
│   ├── robot-ross/
│   │   ├── bob_ross.py             # Main orchestrator (MAX_DRAW_SIZE=125)
│   │   ├── artist_poller.py        # Shopify order poller (polls Salesman every 180s)
│   │   ├── salesman_client.py      # Salesman REST API client
│   │   ├── obs_manager.py          # OBS WebSocket controller
│   │   ├── order_log.py            # Excel order ledger
│   │   ├── youtube_upload.py       # YouTube Data API v3 uploader (OAuth2)
│   │   ├── draw_size_test.py       # Arm travel limit test (draws squares 100–180mm)
│   │   └── orders.xlsx             # The ledger
│   ├── huenit/
│   │   ├── huenit_svg.py           # SVG → arm (Bezier-aware)
│   │   ├── huenit_write.py         # Text calligraphy (digits 0–9, wraps at 255 chars)
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
