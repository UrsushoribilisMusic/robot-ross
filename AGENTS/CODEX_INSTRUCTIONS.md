# OpenAI Codex — Agent Instructions

## Your role
You own the **Media Pipeline** stream — YouTube upload automation,
video post-processing, and well-scoped module generation tasks.

## Before every task
1. Read `AGENTS/PROJECT_GOAL.md` and `AGENTS/CONVENTIONS.md`
2. `git pull origin master`
3. Read the GitHub Issue — implement exactly what's in the acceptance criteria
4. Create your branch: `git checkout -b feature/ISSUE-NUMBER-description`

## Key context
- Language: Python 3.9, interpreter `/usr/bin/python3`
- Platform: macOS arm64 (Apple Silicon M4)
- OBS recordings land in `~/Movies/*.mov` — these are your video inputs
- Order ledger is `skills/robot-ross/orders.xlsx` — video URLs go in col 7
- YouTube upload should call `order_log.set_video(row, url)` after upload

## Coding style
- No new classes unless genuinely needed — prefer functions
- No docstrings on private/internal functions
- Subprocess calls use `/usr/bin/python3` or `sys.executable`
- Keep scripts standalone and callable from bob_ross.py as subprocesses

## After finishing
- Push branch, open PR to master
- Write "Closes #N" in the PR description
- Do not merge your own PR
