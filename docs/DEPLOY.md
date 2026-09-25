# Deploying Backend City (from scratch)

Three free services, deployed in this order:

| # | Service          | Runs                        | Free tier notes                                   |
| - | ---------------- | --------------------------- | ------------------------------------------------- |
| 1 | **Neon**   | Postgres 17                 | 0.5 GB; compute sleeps when idle, wakes in ~1 s   |
| 2 | **Render** | FastAPI API (this repo)     | Docker web service; sleeps after 15 min idle      |
| 3 | **Vercel** | Next.js app (frontend repo) | Hobby plan; the browser only ever talks to Vercel |

```
Browser ──► Vercel (Next.js) ──/api/* rewrite──► Render (FastAPI) ──► Neon (Postgres)
            same origin: httpOnly cookies are first-party, no CORS needed
```

Pick **one region** for Neon and Render so the database is close to the API
(for India: Render **Singapore** + Neon **AWS Asia Pacific (Singapore)**).

---

## 0. Before you start

- Both repos pushed to GitHub `main` (they must be public, or the frontend build can't download
  the harness; see step 3).
- Sign in to [neon.tech](https://neon.tech), [render.com](https://render.com) and
  [vercel.com](https://vercel.com) with GitHub.
- Generate a JWT secret locally and keep it somewhere private:

  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(64))"
  ```

---

## 1. Neon: the database

1. **New Project** → name `backend-city`, Postgres **17**, region as above → **Create**.
2. On the project dashboard click **Connect**.

   - Branch `main`, database `neondb`, role `neondb_owner`.
   - **Turn “Connection pooling” OFF** (pooled URLs contain `-pooler`; asyncpg's prepared
     statements break behind PgBouncer).
3. Copy the connection string. It looks like:

   ```
   postgresql://neondb_owner:XXXX@ep-cool-name-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   ```

   Paste it into Render **exactly as copied**. The backend converts it for asyncpg
   (`postgresql+asyncpg://…?ssl=require`, drops `channel_binding`).

You don't create tables by hand: the API runs `alembic upgrade head` every time it starts.

---

## 2. Render: the API

1. **New → Web Service** → connect GitHub → pick **backend-city-backend**.
2. Settings:

   | Field          | Value                                                |
   | -------------- | ---------------------------------------------------- |
   | Name           | `backend-city-api` (becomes the URL)               |
   | Region         | same as Neon (e.g. Singapore)                        |
   | Branch         | `main`                                             |
   | Language       | **Docker** (auto-detected from `Dockerfile`) |
   | Root Directory | _(empty)_                                          |
   | Instance Type  | **Free**                                       |
3. **Environment Variables** (Add from .env is fine; values below):

   | Key                     | Value                                                     |
   | ----------------------- | --------------------------------------------------------- |
   | `ENVIRONMENT`         | `production`                                            |
   | `DATABASE_URL`        | the Neon string from step 1                               |
   | `JWT_SECRET`          | the secret you generated                                  |
   | `COOKIE_SECURE`       | `true`                                                  |
   | `REFRESH_COOKIE_PATH` | `/api/auth`                                             |
   | `CORS_ORIGINS`        | `["http://localhost:3000"]` for now (step 4 updates it) |
   | `PROXY_SHARED_SECRET` | a second random secret (same value on Vercel, step 3); lets rate limits see each learner's real IP |

   Do **not** set `PORT` (Render injects it) or `SANDBOX_PYTHON` (the image sets it).
   Leave `COOKIE_DOMAIN` unset.
4. **Advanced** → Health Check Path: `/health` · Auto-Deploy: **On Commit**.
5. **Create Web Service**. First build takes ~5–8 min (two Python environments are built:
   the API and the pinned grading sandbox). A good log ends with:

   ```
   INFO  [alembic.runtime.migration] Running upgrade  -> 26824da404dc, initial schema
   INFO:     Uvicorn running on http://0.0.0.0:10000
   ```
6. Check it (replace the name if yours differs):

   ```bash
   curl https://backend-city-api.onrender.com/health
   # {"status":"ok"}
   curl "https://backend-city-api.onrender.com/games/signup-gate/variant?seed=1" | head -c 200
   ```

Free instances sleep after 15 minutes without traffic; the first request then takes
~30–60 s. The frontend retries and shows "Waking up the server…".

---

## 3. Vercel: the frontend

1. **Add New → Project** → import **backend-city-frontend**.
2. Framework preset **Next.js** (auto). Root directory `./`. Leave build/install commands as
   default (`npm run build` runs `prebuild`, which downloads the harness from the backend commit
   pinned in `harness.lock`).
3. **Environment Variables**, set **before** the first deploy (the `/api/*` rewrite is
   baked in at build time):

   | Key                         | Value                                                         |
   | --------------------------- | ------------------------------------------------------------- |
   | `BACKEND_URL`             | `https://backend-city-api.onrender.com` (no trailing `/`) |
   | `NEXT_PUBLIC_PYODIDE_URL` | `https://cdn.jsdelivr.net/pyodide/v314.0.7/full/`           |
   | `PROXY_SHARED_SECRET`     | the same value as on Render |

   Do **not** set `HARNESS_LOCAL_PATH` (its absence is what triggers the GitHub download).
4. **Deploy**. The build log should contain:

   ```
   [sync-harness] downloading Atifmoin19/backend-city-backend@f39873a
   [sync-harness] 4 files (v0.1.0, f39873a…) -> public/harness/
   ```
5. Note your URL, e.g. `https://backend-city-frontend.vercel.app`.

---

## 4. Connect and smoke-test

1. Render → your service → **Environment** → set
   `CORS_ORIGINS` = `["https://backend-city-frontend.vercel.app"]` → **Save** (redeploys).
   (Same-origin rewrites don't need CORS; this only allows direct calls from the real site.)
2. Open the Vercel URL and walk the whole flow:
   - [ ] Preloader runs, 3D city appears; Settings → City lighting → Day works.
   - [ ] Sign up → orientation → map.
   - [ ] Gatehouse → briefing (answer the checks) → practice: "Starting your server" finishes
     in 5–10 s the first time, then **Run requests** works.
   - [ ] Pass practice → checkpoint → **Submit checkpoint** → result overlay (graded on Render).
   - [ ] Reload the page: still signed in. Log out → log in again.
3. DevTools → Application → Cookies → your Vercel domain: `bc_access` (path `/`) and
   `bc_refresh` (path `/api/auth`), both **HttpOnly** and **Secure**.

---

## 5. Day-to-day

- Push to `main` → Render and Vercel redeploy automatically. Deploy the **backend first**
  when an API change and a UI change depend on each other.
- Changed anything in `backend/harness/`? Push the backend, then set `commit` in the frontend
  `harness.lock` to that backend commit and push the frontend.
- Vercel preview deploys (branches/PRs) use the same `BACKEND_URL`; they work because the API
  is reached through the same-origin rewrite.
- Keep-warm: `.github/workflows/keep-alive.yml` in the backend repo pings `/health` every
  10 min (set the repo variable `API_HEALTH_URL` if the URL changes). GitHub pauses scheduled
  workflows after 60 days without commits: re-enable it under **Actions**. One always-on
  free Render service fits the monthly free hours.
- Content: every deploy runs `python -m app.games.seed`, which adds new seed games and new
  seed versions but never overwrites a version an admin published.
- First admin: sign up, then in the Neon SQL editor run
  `update users set role = 'super_admin' where email = 'you@example.com';` and sign in again.
- Custom domain later: add it in Vercel; nothing changes on Render (cookies stay first-party).

---

## Releasing the progress / content / admin update (2026-09-26)

Both repos changed together and the shared harness changed (v0.2.0: `expect_body`), so order
matters:

1. Generate a secret (`openssl rand -hex 32`) and add `PROXY_SHARED_SECRET` to **Render** and
   **Vercel** (same value). Nothing breaks if you skip it; rate limits just stay per-Vercel-IP.
2. Merge and push the **backend**. Render runs the migration and the content seed on start;
   the log shows `[seed] created ...`.
3. Set `commit` in the frontend `harness.lock` to that backend commit, then push the
   **frontend**.
4. Smoke test: sign in → Signal Tower → *Signal Codes* practice → the district page shows it
   done after a reload on another device.

Existing learners keep their onboarding and finished briefings (moved from the browser on
their next visit). Checkpoint results kept only in the browser are not moved: they only count
when graded on the server, so those learners retake one checkpoint.

---

## Troubleshooting

| Symptom                                                       | Cause → fix                                                                                                           |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Render build fails at`uv sync --frozen`                     | `uv.lock` out of date → run `uv lock` locally, commit, push                                                       |
| Log:`unexpected keyword argument 'sslmode'`                 | Old code without URL normalization → push latest backend                                                              |
| Log:`prepared statement "__asyncpg_stmt_…" already exists` | Pooled Neon URL → use the direct (non-pooler) string                                                                  |
| Render deploy fails health check                              | App crashed on start → read the log (usually`DATABASE_URL` or `JWT_SECRET` missing)                               |
| Vercel:`/api/...` returns 404                               | `BACKEND_URL` was missing at build time → set it, **Redeploy**                                                |
| First click after a while gives 504 / "waking up"             | Render cold start → wait ~60 s; the app retries                                                                       |
| Signed in, then instantly signed out on reload                | `COOKIE_SECURE` / `REFRESH_COOKIE_PATH` wrong, or `BACKEND_URL` ends in `/api`                                 |
| Practice stuck on "Starting your server"                      | Open`/harness/manifest.json` on the site; if 404 the harness download failed → check the build log                  |
| Checkpoint says "Your code took too long" for a correct answer | Sandbox startup was counted against the learner on the slow free CPU → fixed with `SANDBOX_STARTUP_SECONDS` (default 20); with the warm sandbox (default) a grade takes about 1 s after the server starts |
| Everyone gets 429 at once                                     | Rate limiter sees one shared IP → check client IPs in the Render log; tell Claude to key limits on `X-Forwarded-For` |
