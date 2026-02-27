# Robot Ross — Artist-as-a-Service

> A Huenit robot arm that draws, narrates, and sells its work autonomously in the Agent Economy.

**Official Links:**
- **Store**: [https://robotross.art](https://robotross.art)
- **Marketplace**: [Robot Ross on Virtuals](https://app.virtuals.io/acp/agents/auj2pb60mizox9of81hcmyhm)

---

## What Is This?

Robot Ross is an AI-powered drawing robot running on a Mac mini M4. It takes text prompts, SVG files, Shopify orders, or Agent Marketplace bids, draws them on paper using a pen plotter arm, narrates the process in Bob Ross style using a local Swiss AI model, and records the session to video.

The goal is a fully automated **Artist-as-a-Service**: customers or AI agents buy a slot on a **10×10 Wall of Fame**, the robot draws their piece live, and delivers a branded digital receipt (Proof of Work).

---

## Architecture

Full diagram: `~/Downloads/robot-ross-architecture.txt`

```
 🛒 Shopify ──► Salesman VPS ◄── Virtuals Marketplace (ACP)
                     │
                     ▼
              Orders Database ◄── Masterpiece Portal (/proof/:id)
                     │
                     ▼
 📱 Telegram ──► OpenClaw (Artist Poller)
                     │
                     ▼
 Google Quick Draw ◄── quickdraw_compose ◄──────────── bob_ross.py
 Internet URL      ◄── huenit_sketch    ◄────────────── ├── OBS Studio ──► YouTube
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

### Phase 2 — Automated Studio (✅ Complete)

| Feature | File | Status |
|---|---|---|
| Quick Draw compositional sketches | `huenit/quickdraw_compose.py` | ✅ |
| Internet SVG fetch with sanitisation | `huenit/huenit_sketch.py` | ✅ |
| OBS recording + streaming control | `robot-ross/obs_manager.py` | ✅ |
| YouTube Shorts auto-upload | `robot-ross/youtube_upload.py` | ✅ |
| Order ledger (orders.xlsx) | `robot-ross/order_log.py` | ✅ |
| Branded Proof Portal (`/proof/:id`) | Salesman API | ✅ |
| 10x10 Slot Bidding Engine | Salesman API | ✅ |
| Virtuals Protocol ACP Integration | Salesman API | ✅ |
| Shopify Metafield Sync (URL write) | Salesman API | ✅ |

---

## The 10×10 Wall of Fame

The final product is a **100-slot physical installation**. Each slot is a 10×10cm square on a large board. 

### The Overwrite Protocol
- **Bidding**: Slots are competitive. Anyone can bid to own a square.
- **Overwriting**: A slot can be claimed by paying **20% more** than the current resident.
- **Infinite Canvas**: The robot draws over old layers, creating a physical history of the digital zeitgeist.

---

## Running Locally

### Calibration
```bash
/usr/bin/python3 ~/.openclaw/workspace/skills/huenit/huenit_draw.py calibrate
```

### The Artist Poller (Main Loop)
Keep this running to process incoming orders from Shopify and Marketplaces:
```bash
/usr/bin/python3 ~/.openclaw/workspace/skills/robot-ross/artist_poller.py
```

### Integration Tests
```bash
# Test Virtuals ACP intake
python3 ~/robot-ross/test_virtuals.py

# Test Slot Bidding & Overwriting
python3 ~/robot-ross/test_bidding.py
```

---

## AI Stack

| Role | Model | Runtime |
|---|---|---|
| Brain (orders, decisions) | Claude Haiku 4.5 | Anthropic API |
| Narration | Apertus 8B (Swiss) | Ollama local |
| TTS | Kokoro | Local |
| Scene parsing (Quick Draw) | Apertus 8B | Ollama local |

*Apertus is developed by MichelRosselli as part of an Innosuisse-funded project — proudly Swiss AI.*
