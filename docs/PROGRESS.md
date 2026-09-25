# Progress Log — Backend

Running log. Newest entry on top. Update at the end of every task.

## 2026-09-25 — Session 1: foundation

### Done
- Repo init (`main`), remote `origin` set (not pushed — local-only until a milestone).
- uv project (Python 3.13), Ruff lint+format, mypy strict, pytest (+asyncio).
- Typed settings (`app/core/config.py`, pydantic-settings); `.env.example` documents every variable.
- App factory + `GET /health` + test.
- Dockerfile (python:3.13-slim, uv, non-root) and `docker-compose.yml` (Postgres 17 on host port **5452**, API with hot reload on **8000**).
  Compose project name is `backend-city` to avoid clashing with other local stacks.
- DB layer: async SQLAlchemy 2.1 + asyncpg; 11 models from ideology §15; Alembic initial migration
  (hand-patched: games↔game_versions FK cycle added after both tables; enum types dropped on downgrade). Upgrade/downgrade roundtrip verified.

### Pending (this session)
- Auth, role dependency, rate limits
- Harness + grading sandbox
- Full docs (API.md, DATABASE.md, ARCHITECTURE.md)

### Known issues
- None yet.
