# API — Backend City

Base URL local: `http://localhost:8000` (browser: `/api/*` via Next.js rewrite).
Interactive docs: `/docs` (disabled in production).

Errors always use:
```json
{ "error": { "code": "machine_code", "message": "Human text", "details": [] } }
```
`details` only for `validation_error` (422): `[{ "loc": ["body","password"], "msg": "...", "type": "..." }]`.
Rate-limited requests → 429 `rate_limited`.

## Health
### `GET /health` → 200 `{"status": "ok"}`
No DB call; keep-alive target.

## Auth
Cookies: `bc_access` (path `/`, 15 min) and `bc_refresh` (path `/api/auth`, 14 days); both httpOnly.

### `POST /auth/register` → 201
Body `{ "email": "a@b.com", "password": "8..128 chars", "display_name": "2..32 chars" }`
Response `{ "user": UserPublic }` + sets cookies. Errors: 409 `email_taken`, 422.

### `POST /auth/login` → 200
Body `{ "email", "password" }` → `{ "user": UserPublic }` + cookies.
Errors: 401 `invalid_credentials`, 403 `account_blocked`.

### `POST /auth/refresh` → 200
Uses `bc_refresh` cookie; rotates tokens. Errors (cookies cleared): 401 `refresh_missing`,
`refresh_invalid`, `refresh_expired`, `refresh_reused` (all sessions revoked).

### `POST /auth/logout` → 204
Revokes the current refresh token, clears cookies.

### `GET /auth/me` → 200 `UserPublic` · 401 `not_authenticated`

`UserPublic = { id: uuid, email, display_name, role: "user"|"content_editor"|"super_admin", is_verified }`

## Games
### `GET /games/{slug}/variant?seed=<1..2^31-1>` → 200 `GameVariantPublic`
Public, no auth. Random seed if omitted.
```json
{
  "slug": "signup-gate", "game_type": "bouncer", "title": "...", "district": "gatehouse",
  "character": "bouncer", "visualizer": "request_flow", "is_checkpoint": true, "pass_threshold": 70,
  "scenario": { "intro": "...", "goal": "..." },
  "objective": "Real recruits get in (201). Anyone with bad papers bounces (422).",
  "rules": ["`username` is 3 to 12 characters long.", "..."],
  "starter_code": "...", "editable_region": { "start_marker": "...", "end_marker": "..." },
  "public_tests": [{ "name": "...", "request": { "method": "POST", "path": "/signup", "json": {} }, "expect_status": 201 }],
  "hint_tiers": [1, 2, 3], "dialogue": { "start": "...", "success": "...", "fail": "..." },
  "seed": 42, "attempt_token": "<signed JWT>", "harness_version": "0.1.0"
}
```
404 `game_not_found`.

### `POST /games/{slug}/hint` → 200 `{ "tier": 1, "text": "..." }`
Body `{ "attempt_token", "tier": 1..3 }`. 400 `attempt_invalid`, 404 `hint_not_found`.

### `POST /games/{slug}/grade` → 200 `GradeResponse` (login required, rate limited)
Body `{ "attempt_token": "...", "snippet": "..." }`
```json
{
  "verdict": "graded" | "rejected" | "load_error" | "timeout" | "crashed",
  "score": 83, "passed": true, "stars": 1, "pass_threshold": 70,
  "public_results": [{ "name": "...", "expect_status": 201, "status": 201, "passed": true }],
  "hidden_passed": 10, "hidden_total": 12,
  "violations": [{ "line": 1, "message": "Import not allowed: os" }],
  "error": null
}
```
Hidden test details are never returned, only counts. 400 `attempt_invalid`, 401.

## Admin (role: content_editor or super_admin)
### `GET /admin/whoami` → 200 `UserPublic` · 401 · 403 `forbidden_role`
Placeholder proving the guard; content CRUD comes in Phase 1.
