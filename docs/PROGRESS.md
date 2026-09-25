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

- Auth: register/login/logout/refresh/me; httpOnly cookies; refresh rotation + reuse detection;
  `require_role` guard + `/admin/whoami`; slowapi limits; error envelope.
- Phase 0 spike S1: FastAPI + Pydantic v2 run in Pyodide 314.0.7 (see ARCHITECTURE.md). Decision:
  real FastAPI, no mini-framework.
- Harness (`harness/`), sandbox (policy + audit hook + rlimits + scrubbed env), Bouncer template,
  `/games/{slug}/variant|hint|grade`, signed attempt tokens.
- Docker image builds pinned sandbox venv (Pyodide parity). 45 tests pass in the Linux container.
- Docs: README, CLAUDE.md, ARCHITECTURE, API, DATABASE.

- Phase 0 spike 2 verified end to end in Chrome with the frontend: practice in Pyodide, checkpoint
  graded here (100%, 12/12 hidden). Found and fixed: the policy check now dedents snippets
  (the editor sends class-body indentation).
- `scripts/dev.sh`: Postgres in Docker + uvicorn `--reload` on the host (port check included).

### Pending
- Persist attempts + topic_progress on grade; hint usage → score penalty.
- Content from DB (`game_versions`) instead of `content/seed` JSON; admin CRUD.
- Email verify / reset (EmailJS), `lessons` table.
- Render deploy + Neon (at a milestone; owner decides).

### Known issues
- `RLIMIT_AS` not enforced on macOS; memory test runs only in Docker/Linux (`make test-docker`).
- Refresh-cookie path is `/api/auth` (browser path). Direct calls to `:8000/auth/refresh`
  from a browser won't carry it — always go through the Next.js rewrite.
- No kernel network isolation for the sandbox (audit hook only) — acceptable for Phase 0.
