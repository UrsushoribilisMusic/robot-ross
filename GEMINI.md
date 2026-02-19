# Robot Ross / OpenClaw — Gemini CLI Instructions

## Before starting any task
1. Read `AGENTS/PROJECT_GOAL.md` and `AGENTS/CONVENTIONS.md`
2. Read `README.md` and `robot-ross-architecture.txt` for full context
3. `git pull origin master`
4. Read the GitHub Issue carefully — implement exactly what's in the acceptance criteria
5. Create your branch: `git checkout -b feature/ISSUE-NUMBER-short-description`

## Your role
You own the **Salesman / Cloud** stream and **Documentation**.

**Salesman stream** (Issues #1, #2, #5):
- VPS setup, Shopify webhook handler, Tailscale config, Gallery Assistant SOUL

**Documentation** (as needed):
- Keep README.md and robot-ross-architecture.txt in sync with reality
- Architecture diagram is plain text — keep it monospace-aligned
- When SOUL.md behaviour changes, describe it in the PR

## Salesman architecture
The Salesman is a second OpenClaw instance on a cloud VPS.
It receives Shopify webhooks and dispatches orders to the Artist (Mac Mini)
via a Tailscale tunnel.

Order format sent to Artist:
```
ORDER #1042 | buyer: Alice | type: sketch | content: a lighthouse on a rocky coast
```

Artist replies when done:
```
DONE #1042 | status: success | video: /path/to/recording.mov
```

The Salesman then notifies the customer (Telegram/email) and updates Shopify.

## Artist gateway (Mac Mini)
- OpenClaw gateway: `localhost:18789` (Tailscale IP when connecting from VPS)
- Auth: token (never `auth:none`)
- Tailscale must be enabled in `openclaw.json` before the VPS can reach it
- Current Tailscale setting: `"mode": "off"` — Issue #1 is to enable this

## Conventions (summary)
- Python: `/usr/bin/python3`, no new deps without checking macOS arm64 compatibility
- Secrets in environment variables, never hardcoded
- Commit format: `[#ISSUE] Short description`
- Branch format: `feature/ISSUE-short-description` or `fix/ISSUE-description`

## After finishing
- Push branch, open PR targeting master
- Write "Closes #N" in the PR description
- Do not merge your own PR — Teddy (UrsushoribilisMusic) reviews and merges
