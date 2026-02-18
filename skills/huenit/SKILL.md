---
name: huenit
description: Low-level Huenit robot arm control — calibration, manual jogging, and teach/replay. For writing text or drawing shapes, always use the robot-ross skill instead.
metadata: {"openclaw": {"emoji": "🦾", "requires": {"os": ["darwin"]}}}
---

# Huenit Robot Arm — Low-Level Control

> **For writing text or drawing shapes, use the `robot-ross` skill.** It handles safety warnings, voice narration, and proper pen homing automatically.
>
> Use this skill only for: calibration, manual jogging, or teach/replay.

The robot arm is connected at `/dev/cu.usbserial-310` (auto-detected).

## Calibration

If the pen height needs adjustment:

```bash
python3 huenit_draw.py calibrate
```

## Manual Control (interactive, requires terminal)

```bash
python3 huenit_jog_control.py     # keyboard jog: arrows=XY, W/S=Z, Q=quit
python3 huenit_teach_replay.py    # record positions and replay them
```

## Notes

- Calibration is saved to `calibration.json`.
- The `HUENIT_PORT` environment variable overrides the auto-detected port.
