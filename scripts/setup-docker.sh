#!/bin/bash
# Full Docker production deploy: Postgres + Qdrant + Redis + Backend + Gemini
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== SteelPlant Maintenance Wizard — Docker Production ==="

if ! command -v docker &>/dev/null; then
  echo "ERROR: Docker is not installed."
  echo "Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
  exit 1
fi

# Ensure env files exist
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — add your GEMINI_API_KEY before continuing."
fi

if [[ -z "${GEMINI_API_KEY:-}" ]] && grep -q '^GEMINI_API_KEY=$' .env 2>/dev/null; then
  echo ""
  echo "WARNING: GEMINI_API_KEY is not set in .env"
  echo "Get a key at: https://aistudio.google.com/apikey"
  echo "Edit $ROOT/.env and add: GEMINI_API_KEY=your_key"
  echo ""
  read -r -p "Continue without Gemini key? (y/N) " ans
  [[ "${ans,,}" != "y" ]] && exit 1
fi

"$ROOT/scripts/switch-env.sh" docker

echo "Building and starting all services..."
docker compose --profile full up --build -d

echo "Waiting for backend health..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo ""
    curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/health
    echo ""
    echo "=== Ready ==="
    echo "API:      http://localhost:8000/docs"
    echo "Login:    engineer@steelplant.com / demo1234"
    echo "Logs:     docker compose logs -f backend"
    exit 0
  fi
  sleep 5
  echo "  waiting... ($i/60)"
done

echo "Backend did not become healthy in time. Check logs:"
echo "  docker compose logs backend"
exit 1
