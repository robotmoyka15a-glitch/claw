#!/usr/bin/env bash
# Linux/macOS helper (PTY terminal will use bash instead of pywinpty).
set -e

cd "$(dirname "$0")"

# backend
(
  cd backend
  if [ ! -d .venv ]; then python3 -m venv .venv; fi
  source .venv/bin/activate
  pip install -q -r requirements.txt
  [ -f .env ] || cp .env.example .env
  uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload &
) &

# frontend
(
  cd frontend
  [ -d node_modules ] || npm install
  npm run dev
)
