# WORKLOG - Task qc5xcwi15n54pea

## Objective
Merge Mexico-era features from `bobrossskill` into `robot-ross` (the canonical demonstrator).

## Plan
1.  **Sync `huenit/huenit_write.py`**:
    -   Add `TILT_SLOPE_X` and related `z_hover`/`z_feed` improvements.
    -   Synchronize `PYRO` config constants (slower `PYRO_Z_FEED` and `PYRO_TRAVEL`).
    -   Include `word_wrap` functionality and `min-size` auto-scaling improvements.
2.  **Sync `huenit/huenit_draw.py`**:
    -   Merge improved calibration logic (X/Y tilt, custom size).
    -   Add `_log` to `huenit_draw.log`.
    -   Sync serial port handling (boot wait, buffer clear).
3.  **Sync `chat_ross.py`**:
    -   Ensure `robot-ross/chat_ross.py` matches the refined version from `bobrossskill`.
    -   Correctly map paths for `SKILLS_DIR` (`voice/` and `huenit/` subdirectories).
4.  **Sync `bob_ross.py`**:
    -   Review `pyro` flag orchestration and `narration_action` mapping.
    -   Ensure all `bob_ross.py` features from `robot-ross` (OBS, Ledger) are preserved.
5.  **Git Cleanup**:
    -   Add `voice/listen.py` (currently untracked).
    -   Add `robot-ross/chat_ross.py` (currently untracked).
    -   Commit all changes with clear messages.

## Progress
- [x] Merge `huenit_write.py`
- [x] Merge `huenit_draw.py`
- [x] Merge `chat_ross.py`
- [x] Merge `bob_ross.py` (review and fix corruption)
- [x] Git commit & push
