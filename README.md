# Full Stack City — Backend

FastAPI backend for **Full Stack City** (formerly Backend City), a gamified platform that takes learners from zero to
job-ready backend developer. This repo owns auth, progress, checkpoint grading (sandboxed),
content APIs, and the shared Python **harness** that also runs in the browser via Pyodide.

Frontend repo: `backend-city-frontend` · Product spec: [docs/PROJECT_IDEOLOGY.md](docs/PROJECT_IDEOLOGY.md)

## Stack
Python 3.13 · FastAPI 0.141 · Pydantic 2.13 · SQLAlchemy 2.1 (async) + asyncpg · Alembic 1.20 ·
argon2-cffi · PyJWT · slowapi · pytest · Ruff · mypy (strict) · uv · Docker.

## Quick start (your terminal, live logs + auto-reload)
Docker Desktop open, then:
```bash
./scripts/dev.sh              # Postgres in Docker + uvicorn --reload on http://localhost:8000
PORT=8010 ./scripts/dev.sh    # another port
./scripts/dev.sh --docker     # everything in Docker, logs attached
```
Ctrl+C stops the API; `docker compose down` stops Postgres.

## Run fully in Docker (detached)
```bash
cp .env.example .env          # then set JWT_SECRET
make up                       # Postgres 17 (host :5452) + API with hot reload (:8000)
curl localhost:8000/health    # {"status":"ok"}
open http://localhost:8000/docs
```
Migrations run automatically on container start (`alembic upgrade head`).

## Tooling on the host
```bash
make install     # uv sync -> .venv (editor support, tests)
make check       # ruff + mypy + pytest (needs the db container running)
make test-docker # full suite inside the Linux image (includes the memory-limit test)
make format
make migration m="describe change"
```

## Environment variables
All documented in [.env.example](.env.example); loaded through typed settings in
`app/core/config.py`. Never commit `.env`.

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `local` / `test` / `production` (production hides `/docs`) |
| `DATABASE_URL` | asyncpg URL (local compose or Neon with `?ssl=require`) |
| `JWT_SECRET` | Signs access + attempt tokens. Long random string |
| `ACCESS_TOKEN_TTL_MINUTES` / `REFRESH_TOKEN_TTL_DAYS` | Token lifetimes |
| `COOKIE_SECURE` / `COOKIE_DOMAIN` / `REFRESH_COOKIE_PATH` | Auth cookie attributes |
| `RATE_LIMIT_ENABLED`, `AUTH_RATE_LIMIT`, `CHECKPOINT_RATE_LIMIT`, `FEEDBACK_RATE_LIMIT` | slowapi limits |
| `PROXY_SHARED_SECRET` | Lets the frontend proxy pass the real client IP for rate limits |
| `CORS_ORIGINS` | Only for direct browser calls; prod is same-origin via Next.js rewrites |
| `SANDBOX_*` | Grading sandbox timeout, memory, snippet size, interpreter; `SANDBOX_PARALLEL` = grades the warm server runs at once (default 2) |

## Deployment
Live at **https://backend-city-api.onrender.com** (Render free web service from the
`Dockerfile`: reads `$PORT`, runs `alembic upgrade head` on boot), database on **Neon**
(Postgres 17). Pushing `main` redeploys. Step-by-step: [docs/DEPLOY.md](docs/DEPLOY.md).

## Docs
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — layers, data flow, decisions
- [docs/API.md](docs/API.md) — endpoints and shapes
- [docs/DATABASE.md](docs/DATABASE.md) — tables and migrations
- [docs/PROGRESS.md](docs/PROGRESS.md) — running log
- Release notes (both repos, versioned): `FEATURES.md` in the frontend repo
- [CLAUDE.md](CLAUDE.md) — guide for AI sessions
