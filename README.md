# Robot Ross

> A Huenit robot arm that draws and narrates, controlled via a local browser UI.

---

## What Is This?

Robot Ross is an AI-powered drawing robot. It takes text prompts, SVG files, or spoken requests, draws them on paper using a pen plotter arm, and narrates the process in Bob Ross style using a local AI model (Mistral by default, Apertus available as a fallback).

## Status Overview (read this first)

- **Active (hackathon build)**: Huenit arm control, Mistral-backed narration/sketch generation/scene parsing, the Windows [Control Center](#windows-control-center-hackathon-build) UI, [ATF](#atf-agentic-technical-file) wiki/ledger Q&A.
- **Dormant, not deleted**: OBS recording + camera capture (proof-of-work video) from the original Mac Mini build. Not used for the hackathon, but still functional — `obs_manager.py` and the Reolink camera setup work if reconnected. Kept because they may come in handy again later.
- **Retired / repurposed**: the Shopify order pipeline, the Salesman VPS commerce flow (`artist_poller.py`, `salesman_client.py`), and the public **8×8 Wall of Fame dashboard**. This was the original Mac Mini "Artist-as-a-Service" business model — customers buy a slot via Shopify, the robot draws it live, artwork ships. The Shopify/Salesman infrastructure was later reused for the **Classical Reels** project, so the dashboard went unused; `api.robotross.art/dashboard` now actually serves the Flotilla fleet-hub app, not the Robot Ross order grid. Not needed for the hackathon. Documented here (rather than deleted outright) so a future session doesn't waste time rediscovering that the live URL doesn't match what the code implies.

---

## Architecture

Full diagram: [`robot-ross-architecture.txt`](robot-ross-architecture.txt) (repo root)

```
 Google Quick Draw ◄── quickdraw_compose ◄──────────── bob_ross.py
 Internet URL      ◄── huenit_sketch    ◄────────────── ├── Mistral (narration, Apertus fallback)
 Local photo       ◄── image_to_svg     ◄────────────── ├── OBS (dormant) ──► ffmpeg ──► video proof
 Text/calligraphy  ◄── huenit_write     ◄────────────── └── order_log ──► orders.xlsx
                                    │
                               Huenit Arm (≤125mm)
                            Paper
```

See [Windows Control Center](#windows-control-center-hackathon-build) below for the browser-based operator UI used for hackathon demos.

---

## What's Built

### Phase 1 — Interactive Drawing (✅ Complete)

| Feature | File | Status |
|---|---|---|
| Write text / calligraphy | `huenit/huenit_write.py` | ✅ |
| Draw shapes (circle, square…) | `huenit/huenit_draw.py` | ✅ |
| Draw local SVG files | `huenit/huenit_svg.py` | ✅ |
| Photo → SVG → draw (vtracer) | `huenit/image_to_svg.py` | ✅ |
| Bob Ross narration via local LLM | `robot-ross/bob_ross.py` | ✅ Mistral default, Apertus fallback |
| Telegram preview → approve/cancel | `robot-ross/bob_ross.py` | ✅ (Mac Mini build) |
| Job lock, caffeinate, SIGTERM stop | `robot-ross/bob_ross.py` | ✅ |
| Desktop .command shortcuts | `~/Desktop/` | ✅ |

### Phase 2 — Automated Studio (✅ Built, 💤 = dormant/retired — see Status Overview)

| Feature | File | Status |
|---|---|---|
| Quick Draw compositional sketches | `huenit/quickdraw_compose.py` | ✅ |
| Internet SVG fetch with sanitisation | `huenit/huenit_sketch.py` | ✅ |
| OBS recording + streaming control | `robot-ross/obs_manager.py` | 💤 Dormant — functional, unused in hackathon build |
| OBS auto-start/stop per job | `robot-ross/bob_ross.py` | 💤 Dormant |
| Trim recording to start after last beep | `robot-ross/bob_ross.py` | 💤 Dormant · PR #8 |
| Wrap long write-text into multiple lines | `huenit/huenit_write.py` | ✅ PR #10 |
| Drawing area hard-capped at 125mm | `robot-ross/bob_ross.py` | ✅ PR #14 |
| Font digits 0–9 complete | `huenit/huenit_write.py` | ✅ PR #14 |
| Order ledger (orders.xlsx) | `robot-ross/order_log.py` | ✅ still used for job history |
| YouTube Shorts upload (OAuth2) | `robot-ross/youtube_upload.py` | 💤 Dormant · PR #7 |
| Buyer name → personalised narration | `robot-ross/bob_ross.py` | ✅ |
| `--direct` flag (no preview for orders) | `robot-ross/bob_ross.py` | ✅ |
| Salesman REST API client | `robot-ross/salesman_client.py` | 🗄️ Retired/repurposed (Shopify pipeline → Classical Reels) |
| Artist order poller (auto-start on login) | `robot-ross/artist_poller.py` | 🗄️ Retired/repurposed |
| Tailscale gateway (Artist ↔ Salesman) | `openclaw.json` | 🗄️ Retired/repurposed |
| Salesman: populate type/content/buyer from Shopify (#13) | Cloud | 🗄️ Retired/repurposed |
| YouTube stream key configuration | OBS Settings | 💤 Dormant |

### Explored & Parked
- **Potrace image pipeline** (`huenit/image_to_svg_potrace.py`) — 14× fewer moves than vtracer but visual quality insufficient. Parked until tuning improves.
- **vpype linesort** — converts Bezier paths to dense polygon points, makes output worse. Discarded.

---

## Hardware

| Component | Details |
|---|---|
| Robot arm | Huenit, USB serial `/dev/cu.usbserial-310` (Mac) or COM3 (Windows), z_up: 6.0mm |
| Drawing area | Hard-capped at 125mm (physical limit confirmed 120–125mm) |
| Computer | Mac mini M4, macOS Sequoia (production/dormant features) or a Windows laptop (hackathon build) |
| Camera 💤 dormant | Reolink 4K, IP `192.168.1.40` — proof-of-work recording, not used in hackathon build |
| Camera stream 💤 dormant | `rtsp://admin:****@192.168.1.40:554/Preview_01_sub` |
| Studio software 💤 dormant | OBS Studio 32 (Apple Silicon), WebSocket port 4455 |

---

## The 8×8 Wall of Fame (retired / repurposed — see Status Overview)

The original commercial model for the Mac Mini build: a **64-slot physical installation**, each slot a 10×10cm square. Customers bought a slot via Shopify, Robot Ross drew it live on YouTube, and the artwork shipped. `orders.xlsx` tracked Received/Produced/Posted/Shipped per order.

This is **not part of the hackathon build** and the automation behind it is dormant/repurposed (see Status Overview above) — kept here for historical/architectural context, not as a current feature.

- **Public dashboard**: there used to be a live status page at `api.robotross.art/dashboard` (source: `dashboard.html` in `salesman-cloud-infra`) showing the 8×8 grid + order pipeline via `GET /salesman/grid` and `GET /salesman/orders/all`. That URL now serves the unrelated Flotilla fleet-hub app instead — the Shopify/Salesman infrastructure was reused for the Classical Reels project. If this ever needs reviving, the dashboard source still exists in the repo; it just isn't deployed/routed anymore.

---

## Windows Control Center (hackathon build)

For the Windows hackathon laptop, `control_center.py` (+ `control_center.html`) serves a local browser UI at `http://localhost:7870` — launched via the **"Robot Ross Control"** desktop shortcut (`launch_control_center.bat`). This is the primary way to operate the arm on this machine; it also starts the ATF Q&A server (below) automatically.

- **Drawing Command** panel: Write / Draw / SVG / Sketch tabs, size slider, TTS engine selector (Kokoro/Voxtral/System).
- **Talk to Ross** panel: a chat box that (a) turns natural-language draw/write/calibrate requests into confirmed arm commands, and (b) answers informational questions ("How does calibration work?", "How many jobs have run?") by querying the local **ATF Q&A server** for a grounded, sourced answer from the wiki + operational ledger — falling back to a generic local-model reply if ATF isn't running. Replies are spoken aloud through the real backend TTS engine, not the browser's built-in voice.
- **Showcase Mode**: unattended voice-loop demo mode (Whisper STT → local brain → TTS → arm).
- Two quick links open the **ATF Wiki** and **Ledger Dashboard** (`localhost:8771`) in new tabs.

### ATF (Agentic Technical File)

A separate local server (`atf_local_server.py`, port 8771, in the `atf-review`/`agentic-fleet-hub` repo) serves a compiled compliance/technical wiki plus a `/api/qa` endpoint backing the chat above. Local-first by default (Ministral 3 8B via Ollama), with hosted Mistral available as an explicit opt-in (`--backend hosted`) and Apertus reachable via `--backend ollama` if ever needed — neither auto-triggers, to avoid loading two large models on the same CPU at once. Launched together with the Control Center via `launch_control_center.bat`, or standalone via the "ATF Q&A Server" shortcut.

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

## Automated Shopify Order Flow (Phase 2) — retired / repurposed

🗄️ **Not part of the hackathon build.** This documents the original Mac Mini commerce pipeline for historical/architectural reference — the Shopify/Salesman infrastructure was later reused for the Classical Reels project (see Status Overview above).

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

| Role | Model (default) | Alternates | Runtime |
|---|---|---|---|
| Brain (orders, decisions) | Claude Haiku 4.5 | — | Anthropic API |
| Narration | Mistral (`ministral-3:8b`) | Apertus 8B (`--brain apertus`) | Ollama local |
| Sketch generation (freeform SVG) | Mistral (`ministral-3:8b`) | Apertus, Claude Haiku (`--brain`) | Ollama local / Anthropic API |
| Scene parsing (Quick Draw) | Mistral (`ministral-3:8b`) | Apertus 8B (`--brain apertus`) | Ollama local |
| ATF wiki/ledger Q&A | Mistral local (Ministral 3 8B) | Hosted Mistral (`--backend hosted`), Apertus (`--backend ollama`) | Ollama local / Mistral API |
| TTS | Voxtral (Mistral) | Kokoro, System | Mistral API / local |

Mistral is the default brain across the board for the Mistral hackathon build. Apertus (Swiss, developed by MichelRosselli as part of an Innosuisse-funded project) remains available everywhere as an explicit fallback — it's just not auto-triggered, since running two large local models at once on a single CPU-only laptop causes contention (see the ATF fallback-chain note in the standups if curious).
