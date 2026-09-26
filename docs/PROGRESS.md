# Progress Log — Backend

Running log. Newest entry on top. Update at the end of every task.

## 2026-09-26 — Session 5: growth + account emails

### Done
- Daily challenge rewards (`daily` quiz: first round per day + 20 XP; badge *Daily regular*);
  quiz bests carry `last_played_at`.
- Account emails: `/auth/verify-email`, `/verify-email/resend`, `/forgot-password`,
  `/reset-password` on the existing `email_tokens` table (no migration). EmailJS REST from the
  server via httpx; unconfigured = link logged (never in production). 191 tests pass.
- **Data Vaults (Level 3)**: harness 0.3.0 adds `harness/vault.py` (in-memory SQLite with an
  ATTACH-blocking authorizer, opened by starter code only). Sandbox: audit hook refuses any
  non-`:memory:` connection and extension loading; policy blocks `set_authorizer`, `setlimit`,
  `load_extension`; `sqlite3` is not importable by learners. Games: shelf-search, item-floors,
  vault-ledger (checkpoint, SQL-injection hidden test). 226 tests pass.
  Residual risk (documented): a policy escape could only open existing SQLite files or create
  empty ones; writes are capped at 0 bytes by RLIMIT_FSIZE.
- **Data Vaults topic 2** (v1.14.0): `write-the-vault` in new chapter `sql-writes` with
  stock-room (INSERT, `lastrowid`, 404), vault-census (GROUP BY, LEFT JOIN, HAVING) and
  vault-transfer (checkpoint: `with db:` transaction, CHECK constraint → `IntegrityError` →
  409, `rowcount` → 404; hidden tests check nothing is half done and a `'--` trick). Harness
  0.3.1 re-exports `IntegrityError` (learners still can't import sqlite3). References pass in
  the Linux sandbox; 244 tests pass.

## 2026-09-26 — Session 4: Academy games, quizzes, rewards, analytics, parallel sandbox

### Done
- Two Academy practice games (`game_type: python_basics`), graded on the JSON body:
  **Front Desk** (dict access, f-strings, `len`, `in`) and **Score Board** (comprehension,
  `sorted(key=...)`, `None` when empty). Placed on `python-for-js` as practice only: the topic
  stays lesson-completed (no checkpoint) so learners who already cleared the Academy keep it.
- Quizzes: `quiz_results` table + `GET/POST /me/quiz-results` (best round per quiz), and
  `users.start_district` + `PUT /me/placement` (placement suggestion only). Migration
  `2eda7346d503`.
- **Admin analytics** (`GET /admin/analytics`): accounts, active 7/30 days, 14-day signups,
  per-topic funnel (briefed → practiced → attempted → passed), games by pass rate (hardest
  first, all versions counted), quiz stats. **Feedback inbox**: `POST /me/feedback` (10/hour),
  `GET/PATCH /admin/feedback`. Migration `37d08d8cd287`.
- **XP, levels, streaks, badges**: `GET /me/stats` derives them from existing records (so past
  work counts; nothing new is stored). 11 badges with earned dates; lesson-only topics never
  count as checkpoint passes.
- **Parallel warm sandbox**: the fork server runs `SANDBOX_PARALLEL` (default 2) grades at once;
  replies are matched by job id. Verified in the Linux image (memory test included).
- Spike (PGlite vs sql.js): neither. Data Vaults games use Python `sqlite3` inside the harness
  (0 extra download, same engine in browser and grader); numbers + sandbox caveats in
  ARCHITECTURE.md "Key decisions".
- API title is now "Full Stack City API". 183 tests pass.
- Released to production (Render + Neon, head `37d08d8cd287`).

### Next up (owner decides)
1. ~~Email flows~~ done in v1.12.0 (EmailJS keys still to be set on Render).
2. Admin: create games/topics from the panel, audit log (the topic → game list is served
   since v1.12.1: `TopicProgress.games`).
3. Data Vaults topic 2: SQLAlchemy models + the N+1 problem (Pyodide wheel 2.0.48; pin it in
   `harness/requirements.txt`).
4. Phase 3 and 4 (owner will pick).

## 2026-09-26 — Session 3: Full Stack City (tracks + interest)

### Done
- Brand is now **Full Stack City** (plan: docs/FULL_STACK_CITY.md). Tracks are the sides of the
  city: `python-backend` (open), `frontend` and `full-stack` (seeded as coming soon).
- `GET /content/tracks`, `PUT /me/goal` (signup question; a coming-soon goal also records
  interest), `GET/POST /me/interests` (Notify me, idempotent), admin content shows interest
  per track. Migration `b0de7ed0e716`: `track_interests`, `users.learning_goal`.
- 156 tests pass.

### Next up
- Step 3 of the plan: pull-out + Choose your side over the 3D scene; step 4: onboarding question.

## 2026-09-26 — Session 2: progress API, content depth, ops, admin MVP

### Done
- **Content in the DB.** `content/seed/curriculum.json` + `games/*.json` sync into tracks →
  levels → chapters → topics → games → versions (`python -m app.games.seed`, run on every
  start). Games are read from `game_versions`; attempt tokens pin the version + mode.
- **Progress API**: `GET /me/progress` (per track), lessons, practice passes, onboarding,
  one-time import of browser progress (never checkpoints). Checkpoint grades save an attempt
  and `topic_progress`; hint tiers cost 5 points each and block 3 stars; optional retest
  cooldown (429 `retest_cooldown`); consecutive-fail count for the soft-fail recap.
- **8 new games** (all pass `tests/test_content.py`: reference 100% on 4 seeds, starter below
  the pass mark): Signal Tower *Signal Codes*, *Method Lanes*, checkpoint *Tower Relay*;
  Router Station *Platform Paths*, *Query Filters*, checkpoint *Route Dispatcher*; Gatehouse
  practice *Ticket Booth*, *Badge Check*. Hidden tests can be templated lists in content.
- Harness 0.2.0: optional `expect_body` (subset match) so routing games check the handler.
  `render_json` now keeps a placeholder's type (`"{{n}}"` → number).
- **Security fix:** learner code could forge a 100% checkpoint (`uuid.os.write(1, fake)` +
  `_exit(0)`; the AST policy can't see it). The sandbox now gets requests only; the API scores.
- **Warm sandbox**: pre-imported fork server; grading at `--cpus=0.1` 11 s → ~0.7 s.
  Cold interpreter stays as fallback. Both engines run every sandbox defense test.
- **Ops**: keep-alive GitHub Action (every 10 min); rate limits key on the real client IP
  via `X-BC-Client-IP` + shared secret from the frontend proxy; games routes per user.
- **Admin MVP**: content tree, topic settings, game versions (save draft → test-run with every
  hidden case → publish, blocked unless the reference passes on seeds 1-3), hide/show,
  learner list/search/detail, block/role/reset (super admin). `last_active_at` now tracked.
- 151 tests pass locally; 138 of the pre-admin suite also verified in the Linux image.

### Next up (owner decides)
1. Release: set `PROXY_SHARED_SECRET` on Render + Vercel, push backend, bump frontend
   `harness.lock`, push frontend (DEPLOY.md, "Releasing the progress / content / admin update").
2. Email flows: verify email, forgot/reset password (EmailJS).
3. Admin: create new games/topics from the panel (today: edit existing ones), audit log.
4. Academy practice games (Python basics); Status Code Speed Round (needs a quiz game UI).
5. Phase 2: AI hints (Byte), XP/streaks/badges, Data Vaults.

### Known issues

## 2026-09-26 — Session 1d: hardening

### Done
- `/openapi.json` hidden in production (docs were already off).
- Full-history secret scan: only placeholder credentials (`XXXX`, `u:p@ep-x`); `.env` ignored.

### Next up (owner decides; full list in the frontend `docs/PROGRESS.md` status snapshot)
1. Progress API: persist `attempts` + `topic_progress` on grade, `GET/PUT /me/progress`,
   hint penalty + retest cooldown.
2. Email flows: verify email, forgot/reset password.
3. Admin MVP: content CRUD from `game_versions`, test-run with the reference solution,
   draft/publish, user list/detail (routes already guarded by `require_role`).
4. Warm sandbox (pre-imported worker) to cut grading from ~7–11 s to ~1 s on the free CPU;
   rate limits keyed on the real client IP.
5. More game templates: Route Dispatcher (Level 1), Status Code Speed Round, Pick the Line.

## 2026-09-25 — Session 1c: first production deploy

### Done
- Deployed: Neon (Postgres 17, Singapore) + Render free (Docker) + Vercel. Guide: docs/DEPLOY.md.
- Settings accept Neon connection strings as pasted (`sslmode`/`channel_binding` translated).
- Found in production: Render's 0.1 CPU needs several seconds just to start the sandbox Python
  and import FastAPI/Pydantic, so every checkpoint timed out. The sandbox now has two budgets:
  `SANDBOX_STARTUP_SECONDS` (interpreter + imports, default 20) and `SANDBOX_TIMEOUT_SECONDS`
  (learner code, 4, enforced in-child by `setitimer` with a BaseException the code can't
  swallow). The parent keeps a hard wall-clock kill (startup + code) as backstop.
  Verified in Docker at `--cpus=0.1`: old budget timed out in 4.2 s, new one grades in 11 s.
- 50 tests pass.

### Next up
- Warm sandbox (pre-imported fork server) to bring grading from ~10 s to ~1 s on small CPUs.

## 2026-09-25 — Session 1b: clearer missions

### Done
- Game content gains `objective` (one-sentence win condition) and `rules` (templated, one per
  requirement); both are rendered per variant and returned by `GET /games/{slug}/variant`.
  The frontend mission brief shows them. Test: rules are rendered with no `{{` left.
- `signup-gate`: third rule shortened.
- 46 tests pass (45 + 1).

### Next up
- Persist attempts + `topic_progress` on grade and expose a progress API (frontend's next big need).
- Hint usage → score penalty (needs the persisted attempt).
- Then deploy: Render (API) + Neon (Postgres), at the owner's call.

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
