# Architecture — Backend

## Layers
```
HTTP ─► app/api/routes/*      thin: parse, call service, shape response
          │  Depends(): SessionDep, CurrentUser, AdminUser (app/core/deps.py)
          ▼
        app/services/*        business rules, owns transaction commit
          ▼
        app/repositories/*    SQLAlchemy queries only
          ▼
        app/models/*          ORM tables (Postgres)
```
Cross-cutting in `app/core/`: typed settings, security (argon2, JWT, token hashing),
cookies, error envelope, rate limiting.

## Folder map
| Path | Responsibility |
|---|---|
| `app/main.py` | App factory: middleware, error handlers, limiter, routers |
| `app/api/router.py` | The only place routers are registered |
| `app/db/` | Declarative base (naming conventions, mixins), async engine/session |
| `app/games/` | Server-only game engine: content schemas, DB catalog, seed sync, variants, hidden-test generators, validation |
| `app/sandbox/` | Checkpoint execution sandbox |
| `harness/` | Shared runtime (browser + sandbox) |
| `content/seed/` | Seed content: `curriculum.json` (tracks → topics → games) + `games/*.json` |
| `alembic/` | Migrations |

## Auth flow
1. `POST /auth/register|login` → argon2 verify → access JWT (15 min) + opaque refresh token.
2. Both set as **httpOnly, SameSite=Lax** cookies (`Secure` in prod). Refresh cookie path is
   `/api/auth` because the browser reaches the backend through the Next.js `/api/*` rewrite.
3. Refresh tokens stored as SHA-256 hashes. `POST /auth/refresh` revokes the old token and
   issues a new pair (rotation). Presenting an already-revoked token = theft signal → all of the
   user's refresh tokens are revoked.
4. Role guard reads the role from the DB user, not from the JWT claim.
5. Unknown-email logins still run an argon2 verify (constant-ish timing, no enumeration).

## Game + grading flow (Bouncer prototype)
```
GET /games/{slug}/variant  ──► live game_version from the DB, random or given seed
                               render scenario/starter/public tests
                               sign attempt_token = JWT{game, seed, version, mode, exp}
                               (no hidden tests, no solution, no hint text)

Browser: practice runs in Pyodide using harness/ + public tests (no server needed)

POST /games/{slug}/grade {attempt_token, snippet}   (login required, rate limited per user)
   1. verify token → version + seed (client can't pick an easy variant); checkpoint mode only
   2. retest cooldown check; hints used on this variant (from the open attempt)
   3. AST policy check on snippet (allowlist imports, no dunders/eval/open…)
   4. splice snippet into rendered starter code
   5. public tests + hidden tests (templated list or a named generator) ← server-side only
   6. sandbox gets the REQUESTS only → statuses + bodies; the API decides pass/fail
   7. score = % passed − 5 per hint tier; stars; attempt + topic_progress saved
```

### Sandbox layers (defense in depth)
| Layer | Mechanism |
|---|---|
| Static | `policy.py`: import allowlist, blocked builtins, no dunder attributes, size limit |
| Process | separate `python -I -B` child, temp cwd, env with only PATH/HOME (no secrets) |
| Resources | `setrlimit`: CPU, address space (Linux only), FSIZE=0, NOFILE=64; wall-clock timeout + kill |
| Runtime | `sys.addaudithook` after imports: blocks socket/subprocess/os.exec*/file-write events |
| Output | stdout captured from learner code; result JSON size-capped |
| Scoring | children never see expected results; the API scores their raw statuses/bodies |
| Descriptors | warm children get /dev/null for 0-2 and only their own result pipe |

**Why scoring moved out of the sandbox (2026-09-26):** allowed modules expose `os`
(`uuid.os`, `dataclasses.sys`), so learner code could write a forged "all passed" report to
stdout and `_exit(0)`. With expectations kept in the API, a forged report can only claim
statuses, which is the same as solving the game. `tests/test_sandbox.py` keeps that attack.

### Warm sandbox (fork server)
`entry.py --serve` imports FastAPI/Pydantic once, then forks one child per job; the child
drops to its own session, rlimits (CPU, FSIZE=0, NOFILE, address space on top of what it
inherited), audit hook and timer, runs, and writes its report to a private pipe. The server
kills it after timeout + 1 s. The API talks to the server over stdin/stdout, one job at a time,
restarts it on any failure, and falls back to a cold interpreter if it can't start. Measured
in Docker at `--cpus=0.1`: 11 s cold → ~0.7 s warm. Started at app startup (lifespan).

Known limit: no kernel-level network namespace on Render free tier. Audit hook + allowlist cover
it for now; if abuse appears, move grading to an isolated worker (ideology §11.3).

## Key decisions
- **Real FastAPI in Pyodide** (Phase 0 spike): viable — ~0.13 ms/request in-process, ~2.2 MB gz
  extra download. No mini-framework needed.
- **Pinned sandbox venv**: Pyodide 314.0.7 bundles fastapi 0.136.1 / pydantic 2.12.5 while the
  API uses newer versions. The Docker image builds `/opt/harness-venv` from
  `harness/requirements.txt` so grading matches the browser exactly.
- **Two repos, harness lives here**: the sandbox is its primary consumer; the frontend syncs a
  pinned copy (see frontend `scripts/sync-harness.mjs`).
- **Content lives in the DB** (`games` + immutable `game_versions`), seeded from
  `content/seed/`. Admins save drafts and publish; attempts pin their version.
- **Tracks are cities**: everything (auth, progress, admin, grading) is per track, so another
  city (e.g. a frontend track) is new content plus, if needed, a new code runner.
- **Hints on demand**: `hint_tiers` only in payload; text from `POST /games/{slug}/hint`; on a
  checkpoint each tier is recorded on the attempt and costs 5 points.
- **In-memory rate limits**: fine for one instance; switch slowapi storage to Redis to scale out.
- **SQL engine for the Data Vaults (spike, 2026-09-26): Python `sqlite3` in the existing
  harness, not PGlite or sql.js.** Measured (Node, same wasm the browser loads):

  | Option | Download (brotli) | Start | Postgres dialect | Runs in the grader too |
  |---|---|---|---|---|
  | PGlite 0.5.8 | ~3.8 MB (wasm 2.6 + data 1.1 + initdb 0.1) | ~930 ms | yes (ILIKE, JSONB, real EXPLAIN) | no: a second engine next to Python |
  | sql.js 1.14 | ~0.28 MB | ~12 ms | no (no ILIKE; SQLite EXPLAIN) | no: JS only |
  | Pyodide stdlib `sqlite3` (SQLite 3.39) | 0 extra (in `python_stdlib.zip`) | ~13 ms incl. schema + join | no | yes: same Python, same harness |

  The Data Vaults games are FastAPI handlers that query a database (SQL, then SQLAlchemy, then
  N+1), so the database has to live where the handler runs. `sqlite3` is already in Pyodide and
  in the server sandbox, so practice and grading stay identical. ORM games add SQLAlchemy
  2.0.48 (Pyodide wheel ~2 MB, `loadPackage("sqlalchemy")`; pin the same in
  `harness/requirements.txt`). Briefings should note where Postgres differs (SERIAL, ILIKE,
  JSONB). Revisit PGlite only if a pure-SQL game needs Postgres-only features.
  **Before shipping:** allow `sqlite3` / `sqlalchemy` in the policy allowlist and make the audit
  hook reject any `sqlite3.connect` target other than `":memory:"` (a file path would give
  learner code file access).
