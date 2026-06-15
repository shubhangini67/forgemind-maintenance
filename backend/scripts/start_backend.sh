#!/usr/bin/env bash
# Start backend — kills any existing process on port 8000 first
set -e
cd "$(dirname "$0")/.."
PORT=8000

if lsof -ti :$PORT >/dev/null 2>&1; then
  echo "Stopping existing process on port $PORT..."
  lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
  sleep 1
fi

source .venv/bin/activate
export PYTHONPATH=.
echo "Starting backend on http://0.0.0.0:$PORT"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port $PORT
