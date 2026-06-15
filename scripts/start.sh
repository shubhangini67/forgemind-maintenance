#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-local}"

echo "=== SteelPlant Maintenance Wizard ==="

case "$MODE" in
  docker)
    exec "$ROOT/scripts/setup-docker.sh"
    ;;
  hybrid)
    exec "$ROOT/scripts/setup-hybrid.sh"
    ;;
  local)
    "$ROOT/scripts/switch-env.sh" local
    ;;
esac

# --- Local mode below ---
cd "$ROOT/backend"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

if [[ ! -f .env ]]; then
  cp .env.local .env
fi

if grep -q '^LLM_PROVIDER=gemini' .env && grep -q '^GEMINI_API_KEY=$' .env; then
  echo "NOTE: LLM_PROVIDER=gemini but GEMINI_API_KEY is empty."
  echo "Add your key to backend/.env or set LLM_PROVIDER=rule_based"
fi

if [[ ! -f models/train_metrics.json ]]; then
  echo "Training ML models..."
  PYTHONPATH=. python scripts/train_models.py
fi

if [[ ! -f ../data/spmw.db ]]; then
  echo "Seeding database..."
  PYTHONPATH=. python scripts/seed_data.py
fi

echo "Starting backend on :8000..."
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

if command -v npm &>/dev/null; then
  cd "$ROOT/frontend"
  [[ -d node_modules ]] || npm install
  echo "Starting frontend on :3000..."
  npm run dev &
fi

echo ""
echo "Ready! http://localhost:3000"
echo "Login: engineer@steelplant.com / demo1234"
wait $BACKEND_PID
