# Conventions — Robot Ross / OpenClaw

## Git workflow
```
master              ← stable, always working
feature/N-name      ← one branch per issue
```

1. `git pull origin master`
2. `git checkout -b feature/ISSUE-NUMBER-short-description`
3. Do the work, commit often
4. `git push origin feature/ISSUE-NUMBER-short-description`
5. Open PR → target: master → write "Closes #N" in description
6. Request review — Teddy (owner) merges

**Never** push directly to master.
**Never** use `--force` push.
**Never** skip the readiness check before running the arm.

## Commit messages
```
[#42] Add YouTube upload retry with exponential backoff
[#17] Fix serial timeout on long SVG draws
```

## Branch naming
```
feature/42-youtube-upload
fix/17-serial-timeout
docs/55-update-readme
```

## Python
- Interpreter: `/usr/bin/python3` for all subprocess calls
- No new dependencies without checking they install on macOS arm64
- Secrets (passwords, tokens) go in environment variables, never hardcoded
- Exception: OBS_PASSWORD default in obs_manager.py is acceptable (local only)

## File locations
| Thing | Path |
|---|---|
| Arm orchestrator | `skills/robot-ross/bob_ross.py` |
| Agent brain rules | `SOUL.md` |
| OBS controller | `skills/robot-ross/obs_manager.py` |
| Order ledger | `skills/robot-ross/order_log.py` |
| SVG renderer | `skills/huenit/huenit_svg.py` |
| TTS | `skills/voice/speak.py` |

## Testing
- Always run `bob_ross.py check` before claiming arm-related work is done
- For OBS work: `obs_manager.py status` to verify connection
- For order log: `order_log.py list` to verify writes
