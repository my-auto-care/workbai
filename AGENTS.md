# AGENTS.md — Workbay AI

## Cursor Cloud specific instructions

### System dependencies (one-time on fresh VMs)

PostgreSQL 16 and `python3.12-venv` are required for the backend. If missing:

```bash
sudo apt-get update && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql postgresql-contrib python3.12-venv
sudo pg_ctlcluster 16 main start
```

Local dev DB (if not already created):

```bash
sudo -u postgres psql -c "CREATE DATABASE workbay;" 2>/dev/null || true
sudo -u postgres psql -c "CREATE USER workbay WITH PASSWORD 'workbay_dev';" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE workbay TO workbay;"
sudo -u postgres psql -d workbay -c "GRANT ALL ON SCHEMA public TO workbay;"
```

Copy `.env.example` → `backend/.env` with at minimum:

`DATABASE_URL=postgresql://workbay:workbay_dev@localhost/workbay`

Run migrations (Alembic does not load `.env` automatically):

```bash
cd backend
export DATABASE_URL=postgresql://workbay:workbay_dev@localhost/workbay
.venv/bin/alembic upgrade head
```

### Starting services (use tmux)

| Service | Directory | Command | Port |
|---------|-----------|---------|------|
| API | `backend/` | `export DATABASE_URL=... && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000` | 8000 |
| Dashboard | `dashboard/` | `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 npm run dev -- -p 3001` | 3001 |

Voice agent (optional): `python -m app.voice.agent start` in `backend/` with LiveKit + AI keys in `.env`.

### Lint / verify

- Dashboard: `cd dashboard && npm run lint` (pre-existing `any` lint errors in admin pages)
- Backend: `curl http://localhost:8000/health`

### Secrets

Voice E2E needs `LIVEKIT_*`, `ANTHROPIC_API_KEY`, `ASSEMBLYAI_API_KEY`, `ELEVENLABS_*` in `backend/.env`. Flutter mobile (`mobile/`) is not pre-installed on Cloud VMs.

### API note

`POST /sessions` requires existing `shops` and `users` rows (FK). Seed dev data in Postgres or use production/staging credentials.
