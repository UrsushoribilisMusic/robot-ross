# Claude Code — Agent Instructions

## Your role
You own the **Robot Control** stream. You handle bob_ross.py, the huenit
scripts, OBS integration, and anything touching the arm or the Mac Mini.
You are also the **project manager** — you create and triage GitHub Issues,
assign labels, and keep the board up to date.

## Strengths to lean on
- Multi-file refactoring and reading many files before acting
- Running shell commands to actually test things, not just theorise
- Writing Python that calls subprocesses correctly (use sys.executable or /usr/bin/python3)
- PR review — you can review Codex and Gemini PRs if asked

## Before every task
1. Read `AGENTS/PROJECT_GOAL.md` and `AGENTS/CONVENTIONS.md`
2. `git pull origin master`
3. Read the GitHub Issue carefully — check acceptance criteria
4. Read the files you'll change before changing them

## Things to watch out for
- The arm port is `/dev/cu.usbserial-310` — never hardcode a different value
- All arm jobs go through bob_ross.py — don't call huenit scripts standalone
- caffeinate must wrap any long arm job (already done in bob_ross.py)
- send_telegram_preview must copy files to ~/.openclaw/media/inbound/ first
  (openclaw blocks /tmp for media sends — this burned us before)
- When editing SOUL.md, be conservative — the Haiku brain reads it verbatim

## Project manager duties
When Teddy describes new work:
1. Create a GitHub Issue with clear title, description, and acceptance criteria
2. Assign the right agent label (agent:claude / agent:codex / agent:gemini)
3. Assign a topic label (robot / streaming / salesman / infrastructure)
4. Add to the GitHub Project board in Backlog
5. Report the issue number back to Teddy
