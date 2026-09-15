# IG Funnel - Instagram content processing and posting

Admin uploads videos via the dashboard. The backend processes them with FFmpeg,
posts them to Instagram Reels on schedule (Celery Beat). All configuration lives in the dashboard UI. The Instagram bio can link to an external Telegram bot.

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env: SECRET_KEY, FERNET_KEY, ADMIN_PASSWORD, DATABASE_URL…
docker compose up --build
```

- Frontend: http://localhost:3000 (or http://localhost:8080 via nginx profile)
- API: http://localhost:8000 — health at `/health`, docs at `/docs`
- Login with `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`.

With the nginx profile (`docker compose --profile nginx up`), the whole stack is
served on `${NGINX_PORT:-8080}`: `/` → frontend, `/api/*` + `/ws` → backend.

## Services

| Service  | Role |
|----------|------|
| backend  | FastAPI + Uvicorn (port 8000) |
| worker   | Celery worker (video queue + posts queue) |
| beat     | Celery Beat (per-minute scheduler, analytics 4h, bio rotation, proxy checks, cleanup) |
| redis    | Broker + result backend + realtime pub/sub + progress keys |
| frontend | Next.js 14 dashboard |
| postgres | Optional — enable with `DATABASE_URL=postgresql+asyncpg://…` and `--profile postgres` |

Default is SQLite (`./data/app.db` via the `appdata` volume) — zero-config.

## Local dev (no Docker)

Backend needs Python 3.11+, FFmpeg, and Redis:

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # or set env vars
uvicorn app.main:app --reload
celery -A app.tasks.celery_app.celery worker --loglevel=info
celery -A app.tasks.celery_app.celery beat --loglevel=info
alembic upgrade head          # optional — app also auto-creates tables on startup
```

Frontend:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## First-run checklist

1. Log in → **Accounts** → add IG accounts (one proxy per account recommended).
2. **Proxies** → add proxies, health-check them.
3. **Effects** → review FFmpeg presets (applied after 720×1280 crop/scale).
4. **Captions / Hashtags** → seed pools (3–5 tags/post auto-rotated).
5. **Bios** - per-account bio + external bot link (e.g. https://t.me/your_external_bot), rotation interval.`n6. **Schedule** → rules (day/hour/minute); beat creates posts every minute with ±5 min jitter.
8. **Videos → Upload** → auto-processes (or trigger manually), then auto-posts at the next due slot.

## Database

Alembic migration `0001_initial` covers all tables. SQLite auto-creates on
startup; for Postgres run `alembic upgrade head`. Models live in
`backend/app/models/`; secrets (IG passwords, proxy passwords) are
Fernet-encrypted at rest — set a persistent `FERNET_KEY` in `.env`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Login fails | Check `ADMIN_USERNAME`/`ADMIN_PASSWORD` in `.env` (backend reads them at startup). |
| Video stuck in processing | Check worker logs; FFmpeg stderr is stored in `failed_reason` + SystemLog. |
| `challenge_required` account | Log in manually in the IG app, then **Accounts → Login** to refresh the session. |
| Throttled / cooldown | Account auto-cools for 24h; post retries with a different account. |
| WS not updating | Frontend falls back to polling (5–15s); check Redis is reachable. |
