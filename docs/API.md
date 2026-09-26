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

`UserPublic = { id: uuid, email, display_name, role: "user"|"content_editor"|"super_admin", is_verified, onboarded, learning_goal, start_district }`

### Account emails (EmailJS; links point at `APP_URL`)
Tokens are random, stored as SHA-256, single use; a new link retires older ones of that kind.
Registering sends a verification link in the background.
- `POST /auth/verify-email {token}` → 200 `UserPublic` · 400 `invalid_token` (used, expired, wrong kind)
- `POST /auth/verify-email/resend` → 204 (login required; nothing sent if already verified) · 429
- `POST /auth/forgot-password {email}` → **always 204** (no account enumeration) · 429 (`EMAIL_RATE_LIMIT`, 5/hour per IP)
- `POST /auth/reset-password {token, password (8-128)}` → 204, revokes every refresh token and
  marks the email verified · 400 `invalid_token` · 422
Links: verify 24 h (`VERIFY_TOKEN_TTL_HOURS`), reset 60 min (`RESET_TOKEN_TTL_MINUTES`).

## Games
### `GET /games/{slug}/variant?mode=practice|checkpoint&seed=<1..2^31-1>` → 200 `GameVariantPublic`
Public, no auth. Random seed if omitted; `mode` defaults to `practice`. The signed
`attempt_token` carries game, seed, **version** and mode: an attempt is always graded against
the version it started on. `mode=checkpoint` on a practice-only game → 400 `not_a_checkpoint`.
Draft (hidden) games → 404.
```json
{
  "slug": "signup-gate", "mode": "checkpoint", "version": 1, "topic": "validate-signups",
  "game_type": "bouncer", "title": "...", "district": "gatehouse",
  "character": "bouncer", "visualizer": "request_flow", "is_checkpoint": true, "pass_threshold": 70,
  "scenario": { "intro": "...", "goal": "..." },
  "objective": "Real recruits get in (201). Anyone with bad papers bounces (422).",
  "rules": ["`username` is 3 to 12 characters long.", "..."],
  "starter_code": "...", "editable_region": { "start_marker": "...", "end_marker": "..." },
  "public_tests": [{ "name": "...", "request": { "method": "POST", "path": "/signup", "json": {} },
                    "expect_status": 201, "expect_body": null }],
  "hint_tiers": [1, 2, 3], "dialogue": { "start": "...", "success": "...", "fail": "..." },
  "seed": 42, "attempt_token": "<signed JWT>", "harness_version": "0.1.0"
}
```
404 `game_not_found`.

`expect_body` (optional): keys/values the response JSON must contain (subset match), used by
routing games to check which handler answered. `hint_tiers` is `[]` when the topic turns hints off.

### `POST /games/{slug}/hint` → 200 `{ "tier": 1, "text": "..." }`
Body `{ "attempt_token", "tier": 1..3 }`. Checkpoint tokens need a login: the tier is counted on
the attempt and lowers its score. 400 `attempt_invalid`, 401 (checkpoint, logged out),
403 `hints_disabled`, 404 `hint_not_found`.

### `POST /games/{slug}/practice` → 200 `TopicProgress` (login required)
Body `{ "attempt_token", "passed": bool, "score": 0..100 }`. Practice runs in the browser, so this
is self-reported: one row per user and game, and a pass is never taken back.

### `POST /games/{slug}/grade` → 200 `GradeResponse` (login required, rate limited)
Body `{ "attempt_token": "...", "snippet": "..." }` (checkpoint token only). Saves the attempt and
updates `topic_progress` (verdicts `graded`, `load_error`, `timeout` count as attempts).
```json
{
  "verdict": "graded" | "rejected" | "load_error" | "timeout" | "crashed",
  "score": 83, "raw_score": 88, "hints_used": 1, "hint_penalty": 5,
  "passed": true, "stars": 1, "pass_threshold": 70, "retry_at": null,
  "public_results": [{ "name": "...", "expect_status": 201, "status": 201, "passed": true }],
  "hidden_passed": 10, "hidden_total": 12,
  "violations": [{ "line": 1, "message": "Import not allowed: os" }],
  "error": null
}
```
Hidden test details are never returned, only counts. `score = raw_score − hints_used × 5`
(`HINT_PENALTY_PER_TIER`); 3 stars need ≥95% with no hints. 400 `attempt_invalid`, 401,
429 `retest_cooldown` while the topic's cooldown (default off) runs after a failed attempt.

## Progress (login required)
`TopicProgress = { topic, track, status: "locked"|"unlocked"|"passed", complete, lesson_done,
practice_games: [slug], checkpoint_game: slug|null, practice_passed: [slug],
checkpoint: { best_score, stars, attempts, passed, passed_at } | null, consecutive_fails, retry_at }`

A topic is complete when its checkpoint is passed, or (lesson-only topic) its briefing is done.

### `GET /me/progress?track=python-backend` → 200 `{ onboarded, topics: [TopicProgress] }`
Every published topic in curriculum order. `track` limits it to one city (track slug).
### `POST /me/progress/lessons/{topic_slug}` → 200 `TopicProgress` · 404 `topic_not_found`
### `POST /me/onboarded` → 204
### `POST /me/progress/import` → 200 `{ onboarded, topics }`
Body `{ "onboarded": bool, "lessons_done": [topic slug] }`: one-time move of browser-kept progress.
Checkpoints are never imported (they only count when graded on the server).

### `GET /me/quiz-results` → 200 `{ results: [{ quiz, best_score, total, best_combo, plays, last_played_at }] }`
Best round per quiz (highest share correct, then combo).
### `POST /me/quiz-results` → 201 `{ results }` · 422 score/combo above total, bad slug
Body `{ quiz: slug, score, total (1-100), best_combo?, seconds? }`. Quizzes (Speed Round, Pick the
Line, placement) are graded in the browser like lesson checks and never gate progress.
### `POST /me/feedback` → 204 · 422 · 429 (10/hour per learner)
Body `{ kind: "bug"|"idea"|"content"|"other", message (3-2000), page?, game_slug? }`.
### `GET /me/stats?tz=Asia/Kolkata` → 200 `{ xp, level: { level, xp_into, xp_needed }, streak: { current, best, active_today }, badges: [{ key, title, description, earned_at|null }] }`
Derived from attempts, topic progress and quiz rounds (nothing stored; rules in
`app/services/rewards.py`): briefing 20 XP, practice game 30, checkpoint 100 + 25/star, quiz
2/right answer (first 3 rounds per quiz per day; the `daily` quiz counts its first round per
day only, plus 20). Level 1 = 100 XP, each next +50. `tz` sets the
day boundary for streaks (unknown → UTC).
### `PUT /me/placement` → 200 `UserPublic` · 404 `district_not_found`
Body `{ start_district: district_key }`: where the placement quiz suggests starting. Only a
suggestion (`UserPublic.start_district`); nothing is unlocked.

## Admin (role: content_editor or super_admin; 403 `forbidden_role` otherwise)
Admin payloads include server-only content (hidden tests, reference solutions).

### `GET /admin/whoami` → 200 `UserPublic`
### `GET /admin/content` → levels → topics (settings) → games (`current_version`, `latest_version`)
### `PATCH /admin/topics/{slug}` `{ pass_threshold?, hints_allowed?, retest_cooldown_minutes? }`
### `GET /admin/games/{slug}?version=N` → `AdminGame` (default: the live version)
`{ slug, topic, district, game_type, is_checkpoint, status, pass_threshold, version, is_current,
body: GameBody, versions: [{ version, created_at, created_by, is_current }] }`.
`GameBody` = the seed-file game shape (title, character, visualizer, scenario, objective, rules,
variant_params, starter_code, editable_region, public_tests, hidden_tests, reference_solution,
hints, dialogue).
### `POST /admin/games/{slug}/versions` body `GameBody` → 201 `AdminGame`
Saves a new **draft** version (learners keep the live one). 400 `invalid_game` lists problems
(edit markers, unknown `{{placeholders}}`, malformed tests, hint tiers...).
### `POST /admin/games/{slug}/test-run` `{ version, seed?, snippet? }` → `TestRunResult`
Runs the reference solution (or `snippet`) on one variant: every case (public + hidden) with
status, the untouched starter's score, and `issues` that would block publishing.
### `POST /admin/games/{slug}/publish` `{ version }` → `AdminGame`
Re-runs the test on seeds 1–3; any issue → 400 `publish_blocked`. Otherwise the version goes live.
### `PATCH /admin/games/{slug}` `{ status: "draft"|"published" }` → hide / show the game
### `GET /admin/users?q=&limit=25&offset=0` → `{ total, users: [AdminUserRow] }`
### `GET /admin/users/{id}` → `{ user, progress, attempts }` (50 newest attempts)
### super_admin only: `POST /admin/users/{id}/block {blocked}`, `/role {role}`, `/reset`
Acting on your own account → 403 `self_action`.

### `GET /admin/analytics` → 200 `AdminAnalytics`
`{ learners: { total, active_7d, active_30d, signups_14d: [{ day, count }] }, funnel: [{ topic,
title, district, briefed, practiced, attempted|null, passed|null }], games: [{ slug, title, topic,
is_checkpoint, players, attempts, pass_rate, avg_score|null, avg_hints|null }] (hardest first),
quizzes: [{ quiz, rounds, players, avg_pct }] }`. Lesson-only topics have null checkpoint columns.
### `GET /admin/feedback?status=new|seen|done` → 200 `{ items: [AdminFeedback], counts }`
### `PATCH /admin/feedback/{id}` → 200 `AdminFeedback` · 404 `feedback_not_found`
Body `{ status: "new"|"seen"|"done" }`.

## Rate limits
Auth routes: 10/min per client IP. Games routes: 20/min per signed-in user (per IP for visitors).
Behind Vercel the IP comes from `X-BC-Client-IP`, trusted only with the matching
`X-BC-Proxy-Secret` (`PROXY_SHARED_SECRET`); otherwise the socket peer.
