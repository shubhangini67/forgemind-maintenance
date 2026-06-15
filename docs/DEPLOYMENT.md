# Deployment Guide

## Three modes

| Mode | Database | Vectors | LLM | Command |
|------|----------|---------|-----|---------|
| **Local** | SQLite | Local file | Rule-based / Gemini | `./scripts/start.sh local` |
| **Hybrid** | Postgres (Docker) | Qdrant (Docker) | Gemini | `./scripts/setup-hybrid.sh` |
| **Docker Full** | Postgres (Docker) | Qdrant (Docker) | Gemini | `./scripts/setup-docker.sh` |

---

## 1. Gemini LLM setup

1. Get an API key: https://aistudio.google.com/apikey
2. Add to **project root** `.env` (for Docker):
   ```
   GEMINI_API_KEY=your_key_here
   LLM_PROVIDER=gemini
   ```
3. Or add to **backend/.env** (for local/hybrid):
   ```
   GEMINI_API_KEY=your_key_here
   LLM_PROVIDER=gemini
   ```

Without a key, the system falls back to rule-based responses automatically.

Verify at: `GET http://localhost:8000/health` → `"gemini_configured": true`

---

## 2. Docker full production deploy

**Requires:** Docker Desktop

```bash
# 1. Add Gemini key to .env at project root
echo "GEMINI_API_KEY=your_key" >> .env

# 2. One-command deploy
chmod +x scripts/*.sh
./scripts/setup-docker.sh
```

This starts:
- `spmw-postgres` — PostgreSQL 16 on port 5432
- `spmw-qdrant` — Qdrant vector DB on port 6333
- `spmw-redis` — Redis on port 6379
- `spmw-backend` — FastAPI on port 8000

Auto-seeds database on first startup.

```bash
# View logs
docker compose logs -f backend

# Stop everything
docker compose --profile full down

# Stop but keep data
docker compose --profile full stop
```

---

## 3. Hybrid (recommended for development)

Docker for databases, backend runs locally (faster reload):

```bash
# Add key to backend/.env
./scripts/setup-hybrid.sh
```

Or manually:
```bash
docker compose up -d postgres qdrant redis
cp backend/.env.docker.hybrid backend/.env
# edit backend/.env → add GEMINI_API_KEY
cd backend && source .venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --reload
```

---

## 4. Local (no Docker)

```bash
./scripts/start.sh local
```

Uses SQLite + local vector store. Works offline.

---

## Environment file reference

| File | Purpose |
|------|---------|
| `.env` | Root — Gemini key for Docker Compose |
| `backend/.env.local` | SQLite local dev template |
| `backend/.env.docker` | Full Docker backend (service hostnames) |
| `backend/.env.docker.hybrid` | Docker infra + local backend (localhost) |

Switch configs:
```bash
./scripts/switch-env.sh local    # SQLite
./scripts/switch-env.sh hybrid   # Postgres + Qdrant local
./scripts/switch-env.sh docker     # Full container config
```

---

## Production checklist

- [ ] Set strong `SECRET_KEY` and `JWT_SECRET_KEY`
- [ ] Add `GEMINI_API_KEY`
- [ ] Run `docker compose --profile full up --build -d`
- [ ] Verify `/health` shows `postgres`, `qdrant`, `gemini_configured: true`
- [ ] Run `python scripts/verify_system.py`
- [ ] Deploy frontend to Vercel with `NEXT_PUBLIC_API_URL`
