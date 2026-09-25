# CLAUDE.md — Backend City backend

Gamified backend-learning platform. This repo = FastAPI API + grading sandbox + shared harness.
Source of truth: [docs/PROJECT_IDEOLOGY.md](docs/PROJECT_IDEOLOGY.md). Read it before big changes;
if a change contradicts it, raise it with the owner first.

## Commands
- `make up` (Docker: db :5452, api :8000) · `make check` · `make test-docker` · `make format`
- `make migration m="..."` then review the generated file (autogenerate misses enum drops, FK cycles)
- Never `git push` unless the owner asks. Conventional commits (feat:, fix:, chore:, docs:).

## Layout
- `app/api/routes/` thin routers → `app/services/` business logic → `app/repositories/` data access → `app/models/`
- `app/core/` config, security, cookies, deps (auth/role guards), errors, rate limits
- `app/schemas/` Pydantic request/response models (learner-safe only)
- `app/games/` SERVER-ONLY game logic: content loader, seeded variants, templates (hidden tests)
- `app/sandbox/` policy (AST allowlist), entry (child process), executor (subprocess + rlimits)
- `harness/` SHARED with frontend Pyodide — public code, pure Python, no app imports
- `content/seed/games/*.json` game content (Phase 0; moves to DB `game_versions`)

## Rules
- No business logic in routers. Services own commits.
- Full type hints; mypy strict must pass. Ruff clean.
- Every admin route depends on `AdminUser`/`SuperAdminUser` (server-side role check).
- Hidden tests, reference solutions and hint text never go in public payloads. Tests assert this.
- Nothing secret or answer-related in `harness/` — it is shipped to browsers.
- `harness/requirements.txt` must match the Pyodide release the frontend uses.
- Errors: raise `AppError` subclasses → `{"error": {"code", "message"}}`.
- Update `docs/PROGRESS.md` (and API/DATABASE docs when relevant) at the end of every task.
