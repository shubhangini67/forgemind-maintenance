#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
PORT=3000

if lsof -ti :$PORT >/dev/null 2>&1; then
  echo "Stopping existing process on port $PORT..."
  lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
  sleep 1
  # Avoid stale webpack chunks after mixed build/dev runs
  rm -rf .next
fi

echo "Starting frontend on http://127.0.0.1:$PORT (Turbopack — faster page loads)"
exec npm run dev -- --port $PORT --hostname 0.0.0.0
