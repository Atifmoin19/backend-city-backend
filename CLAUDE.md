# CLAUDE.md — Backend City backend

Gamified backend-learning platform. This repo = FastAPI API + grading sandbox + shared harness.
Source of truth: [docs/PROJECT_IDEOLOGY.md](docs/PROJECT_IDEOLOGY.md). Read it before big changes;
if a change contradicts it, raise it with the owner first.

## Commands
- `./scripts/dev.sh` (db in Docker, uvicorn --reload :8000) · `make up` (all Docker) · `make check` · `make test-docker` · `make format`
- `make migration m="..."` then review the generated file (autogenerate misses enum drops, FK cycles)
- Never `git push` unless the owner asks. Conventional commits (feat:, fix:, chore:, docs:).

## Layout
- `app/api/routes/` thin routers → `app/services/` business logic → `app/repositories/` data access → `app/models/`
- `app/core/` config, security, cookies, deps (auth/role guards), errors, rate limits
- `app/schemas/` Pydantic request/response models (learner-safe only)
- `app/games/` SERVER-ONLY game logic: content schemas, DB catalog, seed sync, variants, hidden-test generators, validation
- `app/sandbox/` policy (AST allowlist), entry (cold child / warm fork server), executor (runs + scores in the API)
- `harness/` SHARED with frontend Pyodide — public code, pure Python, no app imports
- `content/seed/` curriculum + game JSON, synced to the DB by `python -m app.games.seed` (admins own published versions afterwards)

## Rules
- No business logic in routers. Services own commits.
- Full type hints; mypy strict must pass. Ruff clean.
- Every admin route depends on `AdminUser`/`SuperAdminUser` (server-side role check).
- Hidden tests, reference solutions and hint text never go in public payloads (admin routes excepted). Tests assert this.
- The sandbox never decides pass/fail: send it requests only and score in `executor.score`.
- New game content must pass `tests/test_content.py` (reference 100%, starter below the pass mark).
- Nothing secret or answer-related in `harness/` — it is shipped to browsers.
- `harness/requirements.txt` must match the Pyodide release the frontend uses.
- Errors: raise `AppError` subclasses → `{"error": {"code", "message"}}`.
- Update `docs/PROGRESS.md` (and API/DATABASE docs when relevant) at the end of every task.
