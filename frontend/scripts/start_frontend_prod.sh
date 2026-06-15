#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
PORT=3000

if lsof -ti :$PORT >/dev/null 2>&1; then
  echo "Stopping existing process on port $PORT..."
  lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
  sleep 1
fi

echo "Building frontend (production)..."
npm run build

echo "Starting frontend on http://127.0.0.1:$PORT (production — faster navigation)"
exec npm run start -- --port $PORT --hostname 0.0.0.0
