# Gemini CLI — Agent Instructions

## Your role
You own the **Salesman / Cloud** stream and **Documentation**.
- Salesman: VPS setup, Shopify webhook handler, Tailscale config, Gallery Assistant SOUL
- Docs: README updates, architecture diagram, PR review for other agents

## Before every task
1. Read `AGENTS/PROJECT_GOAL.md` and `AGENTS/CONVENTIONS.md`
2. Read `README.md` and `robot-ross-architecture.txt` for full context
3. `git pull origin master`
4. Read the GitHub Issue carefully before writing a single line

## Salesman context
The Salesman is a second OpenClaw instance running on a cloud VPS.
It receives Shopify webhooks and dispatches orders to the Artist (Mac Mini)
via a Tailscale tunnel.

Order format the Salesman sends to the Artist:
```
ORDER #1042 | buyer: Alice | type: sketch | content: a lighthouse on a rocky coast
```

After the Artist completes the job it replies:
```
DONE #1042 | status: success | video: /path/to/recording.mov
```

The Salesman then notifies the customer (Telegram/email) and updates Shopify.

## Artist gateway (Mac Mini)
- OpenClaw gateway: `localhost:18789`
- Auth: token (never auth:none)
- Tailscale must be enabled in openclaw.json before the VPS can reach it
- Current tailscale setting: `"mode": "off"` — enabling this is a task for you

## Documentation standards
- Keep README.md and robot-ross-architecture.txt in sync with reality
- When you change SOUL.md behaviour, describe it in the PR
- Architecture diagram is plain text — keep it monospace-aligned

## After finishing
- Push branch, open PR to master
- Write "Closes #N" in the PR description
- Do not merge your own PR
