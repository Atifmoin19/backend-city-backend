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
| `app/games/` | Server-only game engine: content loader, variant seeding, per-type templates |
| `app/sandbox/` | Checkpoint execution sandbox |
| `harness/` | Shared runtime (browser + sandbox) |
| `content/seed/` | Seed content JSON |
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
GET /games/{slug}/variant  ──► random or given seed → pick variant params
                               render scenario/starter/public tests
                               sign attempt_token = JWT{game, seed, exp}
                               (no hidden tests, no solution, no hint text)

Browser: practice runs in Pyodide using harness/ + public tests (no server needed)

POST /games/{slug}/grade {attempt_token, snippet}   (login required, rate limited)
   1. verify token → seed (client can't pick an easy variant)
   2. AST policy check on snippet (allowlist imports, no dunders/eval/open…)
   3. splice snippet into rendered starter code
   4. public tests + template.hidden_tests(seed)  ← generated server-side only
   5. sandbox subprocess → RunReport
   6. score = % of all tests passed by status code; stars; hidden results aggregated only
```

### Sandbox layers (defense in depth)
| Layer | Mechanism |
|---|---|
| Static | `policy.py`: import allowlist, blocked builtins, no dunder attributes, size limit |
| Process | separate `python -I -B` child, temp cwd, env with only PATH/HOME (no secrets) |
| Resources | `setrlimit`: CPU, address space (Linux only), FSIZE=0, NOFILE=64; wall-clock timeout + kill |
| Runtime | `sys.addaudithook` after imports: blocks socket/subprocess/os.exec*/file-write events |
| Output | stdout captured from learner code; result JSON size-capped |

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
- **File-based content for Phase 0**: `content/seed/games/*.json`. The loader interface
  (`get_game`) will switch to `game_versions` rows without touching services.
- **Hints on demand**: `hint_tiers` only in payload; text from `POST /games/{slug}/hint`, so usage
  can be counted toward the score penalty once attempts are persisted.
- **In-memory rate limits**: fine for one instance; switch slowapi storage to Redis to scale out.
