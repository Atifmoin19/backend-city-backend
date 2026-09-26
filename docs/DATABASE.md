# Database — Backend City

Postgres 17 locally (docker-compose, host port 5452; `backend_city` + `backend_city_test`),
Neon in production. Async SQLAlchemy 2.1 + asyncpg. UUID primary keys, `created_at` timestamptz.

## Tables (migrations `26824da404dc_initial_schema`, `987e64920685_progress_and_content_columns`)
```
users ─┬─< refresh_tokens
       ├─< email_tokens
       ├─< attempts >── game_versions >── games >── topics >── chapters >── levels >── tracks
       ├─< topic_progress >── topics
       └─< quiz_results
games.current_version_id ──► game_versions.id   (cycle; FK added after both tables)
game_versions.created_by ──► users.id (SET NULL)
```

| Table | Key columns | Notes |
|---|---|---|
| `users` | email (unique), password_hash, display_name, role enum `user_role`, is_verified, is_blocked, experience_level, last_active_at, onboarded_at, learning_goal, start_district | argon2 hashes; last_active_at set on sign-in/refresh |
| `refresh_tokens` | user_id, token_hash (unique, sha256), expires_at, revoked_at | rotation + reuse detection |
| `email_tokens` | user_id, purpose enum (`verify`/`reset`), token_hash, expires_at, used_at | EmailJS flows (not wired yet) |
| `tracks` | slug (unique), title, description, order, status enum `content_status` | |
| `levels` | track_id, slug, title, district_key, story_intro, order, status | unique (track_id, slug) |
| `chapters` | level_id, slug, title, order, status | unique (level_id, slug) |
| `topics` | chapter_id, slug, pass_threshold (70), required_games_count (3), hints_allowed, retest_cooldown_minutes | unique (chapter_id, slug) |
| `games` | slug (unique), topic_id, game_type, is_checkpoint, order, status, current_version_id | status = visible to learners; current = live version |
| `game_versions` | game_id, version, title, objective, rules, scenario, starter_code, editable_region, public_tests, hidden_test_template, variant_params, reference_solution, visualizer_type, character_key, hints, dialogue (JSONB) | immutable; unique (game_id, version); created_by NULL = from seed files. Server-only fields! |
| `attempts` | user_id, game_version_id, seed, code, score, passed, hints_used, duration_seconds, is_checkpoint | ix (user_id, game_version_id, seed). Checkpoint: one row per submission (score NULL = opened by a hint). Practice: one row per user+game |
| `topic_progress` | PK (user_id, topic_id), status enum, best_score, stars, attempts_count, passed_at, lesson_done_at | summary row, written with each attempt |
| `quiz_results` | user_id, quiz_slug, score, total, best_combo, seconds | one row per finished quiz round (migration `2eda7346d503`); quiz content lives in the frontend |

All FKs `ON DELETE CASCADE` except `current_version_id` / `created_by` (`SET NULL`).
Constraint names follow `app/db/base.py` naming conventions.

Not yet created (ideology §15, later phases): lessons, chapter/level progress, xp_events,
streaks, badges, ai_*, feedback, announcements, audit_logs, usage_counters.

## Content seed
`python -m app.games.seed` (run on every container start and by the tests) syncs
`content/seed/curriculum.json` + `content/seed/games/*.json` into tracks → levels → chapters →
topics → games → game_versions. It creates what is missing and adds a new version when a seed
file changes, but never touches a game whose live version an admin published.

## Migrations
```bash
make migration m="add lessons"   # autogenerate, then REVIEW the file
docker compose exec api alembic upgrade head
uv run alembic downgrade -1
```
Autogenerate gaps to fix by hand: Postgres enum types are not dropped on downgrade; FK cycles
(`use_alter`) must be added with `op.create_foreign_key` after both tables exist.
Tests build the schema with `metadata.create_all` on `backend_city_test` and truncate between tests.
