#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

export PANEL_HOST=0.0.0.0
export PANEL_PORT=8765

if [ -f "./server-manager" ]; then
  ./server-manager
else
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv
  fi
  source .venv/bin/activate
  python -m pip install -r requirements.txt
  python backend/app.py
fi
