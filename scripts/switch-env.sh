#!/bin/bash
# Switch backend environment: local | docker | hybrid
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-}"

usage() {
  echo "Usage: $0 <local|docker|hybrid>"
  echo ""
  echo "  local   — SQLite + local vectors (no Docker)"
  echo "  docker  — Postgres + Qdrant via Docker (backend in container)"
  echo "  hybrid  — Docker infra, backend runs on host"
  exit 1
}

[[ -z "$MODE" ]] && usage

case "$MODE" in
  local)
    cp "$ROOT/backend/.env.local" "$ROOT/backend/.env"
    echo "Switched to LOCAL mode (SQLite)"
    ;;
  docker)
    cp "$ROOT/backend/.env.docker" "$ROOT/backend/.env"
    echo "Switched to DOCKER mode (Postgres + Qdrant + Gemini)"
    echo "Add GEMINI_API_KEY to $ROOT/.env then run:"
    echo "  docker compose --profile full up --build"
    ;;
  hybrid)
    cp "$ROOT/backend/.env.docker.hybrid" "$ROOT/backend/.env"
    echo "Switched to HYBRID mode (Docker infra, local backend)"
    echo "Start infra: docker compose up -d postgres qdrant redis"
    echo "Add GEMINI_API_KEY to backend/.env"
    ;;
  *)
    usage
    ;;
esac
