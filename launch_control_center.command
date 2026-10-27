#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export HUENIT_PORT="${HUENIT_PORT:-/dev/cu.usbserial-310}"
export PYTHONIOENCODING=utf-8
if [[ -x .venv/bin/python ]]; then
  exec "${ROSS_PYTHON:-$PWD/.venv/bin/python}" control_center.py
fi
exec "${ROSS_PYTHON:-/usr/bin/python3}" control_center.py
