#!/bin/bash
# Hybrid: Docker infra (Postgres + Qdrant + Redis) + local backend + Gemini
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export DOCKER_HOST="${DOCKER_HOST:-unix://${HOME}/.colima/default/docker.sock}"

echo "=== Hybrid Setup: Docker infra + local backend ==="

# Start Colima if Docker isn't reachable
if ! docker info >/dev/null 2>&1; then
  if command -v colima &>/dev/null; then
    echo "Starting Colima..."
    colima start --cpu 2 --memory 4 --disk 20 2>/dev/null || colima start
  else
    echo "ERROR: Docker not available. Install Docker Desktop or: brew install colima docker docker-compose"
    exit 1
  fi
fi

cp "$ROOT/backend/.env.docker.hybrid" "$ROOT/backend/.env"

echo "Starting Postgres, Qdrant, Redis..."
docker-compose up -d postgres qdrant redis

echo "Waiting for services (15s)..."
sleep 15

if [[ -z "${GEMINI_API_KEY:-}" ]] && grep -q '^GEMINI_API_KEY=$' "$ROOT/backend/.env" 2>/dev/null; then
  echo ""
  echo "NOTE: Add GEMINI_API_KEY to backend/.env for Gemini responses."
  echo "Get key: https://aistudio.google.com/apikey"
  echo ""
fi

cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

[[ -f models/train_metrics.json ]] || PYTHONPATH=. python scripts/train_models.py

echo ""
echo "Starting backend — auto-seeds Postgres on first run (~60s)..."
echo "API: http://localhost:8000/docs"
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
