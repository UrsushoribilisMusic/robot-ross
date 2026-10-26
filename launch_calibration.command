#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export HUENIT_PORT="${HUENIT_PORT:-/dev/cu.usbserial-310}"
if [[ -x .venv/bin/python ]]; then
  exec "${ROSS_PYTHON:-$PWD/.venv/bin/python}" skills/robot-ross/bob_ross.py calibrate
fi
exec "${ROSS_PYTHON:-/usr/bin/python3}" skills/robot-ross/bob_ross.py calibrate
