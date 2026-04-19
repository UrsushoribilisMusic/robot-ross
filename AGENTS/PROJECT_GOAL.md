# Project Goal — Robot Ross / OpenClaw

## What this is
A Mac Mini M4 runs OpenClaw connected to a Huenit robot arm ("Robot Ross").
Users send drawing prompts via Telegram or Shopify. The arm draws on paper,
narrated in Bob Ross style by Apertus 8B (Swiss AI, Innosuisse-funded).
Every session is recorded by OBS Studio. The end goal is selling 100 slots
on a 10×10 Wall of Fame — drawn live on YouTube, artwork shipped to buyers.

## The four work streams

| Stream | Owner agent | Description |
|---|---|---|
| Robot Control | Claude Code | Serial/USB, arm scripts, bob_ross.py, OBS integration |
| Salesman / Cloud | Gemini CLI | VPS setup, Shopify webhook, Tailscale, Gallery Assistant |
| Media Pipeline | Codex | YouTube upload automation, video post-processing |
| Documentation | Gemini CLI | README, architecture diagram, PR reviews |

## Non-negotiables
- All code runs with `/usr/bin/python3` (has pyserial, pillow, etc.)
- No direct commits to master — branch + PR always
- The arm never runs without a readiness check first
- `SOUL.md` is the agent brain's source of truth — keep it in sync with code

## Definition of Done (per issue)
- [ ] Code works on the Mac Mini (tested, not just linted)
- [ ] Commit message references the issue number
- [ ] PR opened and description includes "Closes #N"
- [ ] SOUL.md updated if agent behaviour changed
- [ ] README updated if user-facing behaviour changed

## Session Checkpoint (February 25, 2026)

- Salesman/cloud pipeline is functioning end-to-end in production:
  - webhook ingest
  - queue claim/ack/complete
  - proof URL write-back to Shopify metafield `custom.proof_of_work`.
- Verified working order example from production:
  - `shopify_7440989946193`
  - `status=complete`
  - proof URL persisted
  - `shopifySync.status=ok`.
- Field-mapping bug and diagnostics were fixed on Salesman side and merged.
- Artist-side fix was implemented and merged by Claude:
  - route prompt-like `type=svg` to `sketch --direct`
  - send `proofOfWorkUrl` in completion payload.

## Session Checkpoint (February 27, 2026)

- Public dashboard at `https://api.robotross.art/` now shows the order prompt text in the pipeline.
- UI behavior:
  - desktop: explicit `Prompt` column
  - mobile: prompt preview inline under `Type`
  - full prompt available via hover tooltip
- Dashboard client now HTML-escapes user-provided prompt/buyer/origin values before rendering.
- Deployment source of truth for this UI is:
  - [dashboard.html](/Users/miguelrodriguez/salesman-cloud-infra/opt/salesman-api/dashboard.html)
