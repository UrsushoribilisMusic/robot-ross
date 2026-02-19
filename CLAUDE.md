# Robot Ross / OpenClaw — Claude Code Instructions

## Before starting any task
1. `git pull origin master` — always start from latest
2. Check your assigned GitHub Issue for acceptance criteria
3. Create a branch: `git checkout -b feature/ISSUE-NUMBER-short-description`
4. Never commit directly to master

## Project summary
Robot Ross is a Huenit robot arm controlled by an OpenClaw agent (Claude Haiku brain)
running on a Mac Mini M4. It draws on paper, narrates via Apertus 8B (Swiss LLM),
records via OBS, and will eventually fulfil Shopify orders live on YouTube.

Full architecture: `robot-ross-architecture.txt`
Full README: `README.md`

## Repo layout
```
skills/robot-ross/    bob_ross.py (orchestrator), obs_manager.py, order_log.py
skills/huenit/        arm scripts: huenit_svg.py, huenit_write.py, huenit_draw.py,
                      huenit_sketch.py, quickdraw_compose.py, quickdraw_to_svg.py
skills/voice/         speak.py (Kokoro TTS)
SOUL.md               OpenClaw agent brain instructions
AGENTS/               cross-agent coordination (read before working)
```

## Key conventions
- Python interpreter: always `/usr/bin/python3` for subprocesses
- Serial port: `/dev/cu.usbserial-310`
- No auto-commits — user reviews all PRs before merge
- Commit format: `[#ISSUE] Short description of what changed`
- All arm jobs go through `bob_ross.py` — do not call huenit scripts directly from agent

## Running things locally
```bash
cd ~/.openclaw/workspace/skills/robot-ross
/usr/bin/python3 bob_ross.py check          # readiness check (no arm)
/usr/bin/python3 bob_ross.py write "test"   # full job
```

## After finishing
- Push branch, open PR targeting master
- Write "Closes #ISSUE" in the PR description
- Do not merge your own PR
