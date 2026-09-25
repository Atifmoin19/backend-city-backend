#!/usr/bin/env bash
# Start the backend for local development with live logs and auto-reload.
#
#   ./scripts/dev.sh            Postgres in Docker + uvicorn on your machine (default)
#   ./scripts/dev.sh --docker   Postgres + API both in Docker, logs attached to this terminal
#   PORT=8010 ./scripts/dev.sh  use another port
#
# Requires Docker Desktop running and `uv` installed. Ctrl+C stops uvicorn (db keeps running;
# stop it with `docker compose down`).
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8000}"

docker info >/dev/null 2>&1 || { echo "Docker is not running. Open Docker Desktop first."; exit 1; }
[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example (set JWT_SECRET!)"; }

if [ "${1:-}" = "--docker" ]; then
  exec docker compose up --build
fi

# Free the port if the Dockerized API from `make up` is holding it
docker compose stop api >/dev/null 2>&1 || true

if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "✖ Port ${PORT} is already in use by:"
  lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN | awk 'NR>1 {print "   pid " $2 "  " $1}' | sort -u
  echo "  Stop it (kill <pid>) or pick another port: PORT=8010 ./scripts/dev.sh"
  exit 1
fi

echo "▶ Starting Postgres (host port 5452)…"
docker compose up -d db >/dev/null
until docker compose exec -T db pg_isready -U backend_city >/dev/null 2>&1; do sleep 1; done

echo "▶ Syncing Python deps…"
uv sync --quiet

echo "▶ Applying migrations…"
uv run alembic upgrade head

echo "▶ API on http://localhost:${PORT}  (docs: http://localhost:${PORT}/docs)"
exec uv run uvicorn app.main:app --host 127.0.0.1 --port "${PORT}" --reload \
  --reload-dir app --reload-dir harness --reload-dir content
