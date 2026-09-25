# Backend City — Project Ideology & Technical Specification

> **Working title:** Backend City (final name not decided yet)
> **Document purpose:** The single source of truth for this project. It captures the idea, the learning philosophy, the full curriculum, game design, UI/UX direction, admin module, technical stack, architecture, data model, deployment plan, challenges, and roadmap.
> **Status:** Planning / brainstorming complete, pre-development.
> **Last updated:** 2026-09-25 (two-repo structure, Phase 0 spike results)

---

## 0. How to Use This Document (for AI assistants and new collaborators)

If you are an AI assistant (or a developer) reading this for the first time:

1. This document describes a **gamified backend-learning platform** built with **Next.js (frontend)** and **FastAPI (backend)**.
2. The owner wants the platform to run on a **100% free stack** (Vercel, Render, Neon, EmailJS, free-tier AI).
3. Decisions marked **[DECIDED]** are final unless the owner changes them. Items marked **[OPEN]** still need a decision. Items marked **[VERIFY]** depend on third-party free-tier limits that change over time and must be re-checked before relying on them.
4. When helping, stay consistent with the **principles in Section 2**, the **stack in Section 12**, and the **data model in Section 15**. If you suggest a change, explain which section it affects.
5. Section 22 lists open decisions; Section 21 is the build roadmap.

---

## 1. The Idea

### 1.1 The problem
- Frontend learners have many playground games (Flexbox Froggy, CSS Diner, Grid Garden, JS games) that teach concepts by playing.
- **Backend has almost nothing similar.** Backend concepts (routing, validation, databases, ORM, caching, auth, queues) are *invisible* — there is no button that turns blue when you get it right. That makes backend harder and more boring to learn for beginners.

### 1.2 The solution
A web platform where a user with **zero knowledge** progresses to a **job-ready backend developer level** through:
- Short concept lessons, followed by
- **Mini-games** for every topic (minimum 2–3 games per topic, with optional extra variants),
- Where the user **does not write full backend code** — the backend is pre-written, and the user **adds small snippets** (a validation rule, a route, a model field, an ORM query, a cache decision, etc.),
- And then **watches the result visually** (animated requests hitting their server, passing, failing, crashing).
- **Score gating:** the user must reach a pass score to unlock the next chapter; otherwise they retest with a new variant.
- **AI support** at any stage for hints and explanations, without giving away answers during scored attempts.

### 1.3 The core insight
> **Make the invisible visible.** Every backend concept must be shown as something the user can *see* happen: requests flying, guards blocking, queries walking through tables, caches short-cutting, queues moving.

---

## 2. Guiding Principles [DECIDED]

1. **Learn by doing, not by reading.** Lessons are short; games are the main learning tool.
2. **Snippets, not full apps.** The user edits a small, clearly marked region inside a working backend.
3. **Visual feedback over text feedback.** "Request #14 bounced with 422" shown as an animation beats "Test 3 failed".
4. **Mastery before progress.** Chapters unlock only after a pass score. Retests use *variants*, never the same question.
5. **AI as a tutor, not an answer machine.** Hints are tiered, cost score, and never output the full solution during a scored attempt.
6. **Fun is a feature.** Game feel, story, characters, and rewards are core — not decoration.
7. **The code area stays calm.** Excitement lives around the editor, never behind the code.
8. **Everything must scale through configuration.** A new game = a config entry in the admin panel, not new code or new art.
9. **Free-stack first, portable always.** Run on free tiers now; keep code standard (Postgres, Docker) so moving to paid hosting is trivial.
10. **Accessible and performant.** Works on low-end devices, respects reduced-motion, never uses color alone for meaning.

---

## 3. Target Users [OPEN]

Two candidate audiences (owner still to decide the primary one):

| Audience | Needs |
|---|---|
| **A. Complete beginners** (never coded) | Need basic Python first (variables, functions, dicts, lists) before backend. |
| **B. Programmers new to backend** (e.g., frontend devs) | Can skip Python basics, start at "How the web works". |

**Current plan:** support both via an **onboarding placement** step (quick quiz). Beginners get an optional **Level -1: Python Survival Kit** (see Section 5). Everyone else starts at Level 0 or can test out of early levels.

---

## 4. Learning System Design

### 4.1 Content hierarchy
```
Track (e.g., "Python Backend")
 └── Level (a district of Backend City, e.g., "The Gatehouse")
      └── Chapter (e.g., "Request Validation")
           └── Topic (e.g., "Pydantic field constraints")
                ├── Lesson (short concept + animated diagram + character dialogue)
                ├── Games (min 2–3 required; more optional variants)
                └── Checkpoint Game (the scored gate)
```

### 4.2 Flow of one topic
1. **Lesson** (2–4 minutes): concept explained with an animated diagram and a character.
2. **Practice games** (2–3 required): low stakes, instant feedback, unlimited retries.
3. **Checkpoint game**: scored; must meet the pass threshold.
4. **Result screen**: score, stars, XP, "Play another variant" or "Next topic".
5. **Extra practice** (optional): unlimited new variants for users who want more.

### 4.3 Scoring & gating rules [DECIDED — values configurable in admin]
- **Pass threshold:** default **70%** on the checkpoint game (configurable per topic).
- **Score components:**
  - Test cases passed (main component)
  - Hint penalty (each hint tier used reduces max score slightly)
  - Optional time bonus (only in speed-round games)
- **Stars:** 1★ = passed, 2★ = ≥85%, 3★ = ≥95% with no hints.
- **Chapter unlock:** all topics in the chapter passed.
- **Level unlock:** all chapters passed + level boss fight passed.
- **Retest:** always a **new variant** (different fields, data, bug, scenario) generated from the game template with a new seed.
- **Soft-fail support:** after 2 failed checkpoint attempts, suggest a lesson recap or AI explanation before the next retry. Optional short cooldown (configurable, default off).
- **Test-out:** experienced users can take a level's placement test to skip it.

### 4.4 Variant system (anti-memorization)
- Each game is a **template** with **parameters** (e.g., field names, value ranges, which bug is injected, dataset).
- Each attempt gets a **seed**; the seed determines the generated scenario and hidden tests.
- The seed is stored in the attempt record so the backend can regenerate the exact hidden tests for grading.

### 4.5 Spaced repetition
- New chapters mix in short **review challenges** from earlier topics.
- A "Daily Review" mode picks topics the user is weakest in or hasn't seen recently.

---

## 5. Full Curriculum (Zero → Backend Developer)

Each level is a **district** of Backend City (see Section 8). Topics listed are the planned chapters/topics; the exact split can be refined in the admin panel.

### Level -1 — Python Survival Kit (optional, for complete beginners)
- Variables, types, strings, f-strings
- Lists, dicts, loops
- Functions, parameters, return values
- Conditionals, exceptions (try/except)
- Classes and objects (just enough for Pydantic/SQLAlchemy)
- Async basics (`async`/`await`, conceptually)

### Level 0 — The Signal Tower: How the Web Works
- Client vs server
- What happens when you type a URL (DNS → request → response, simplified)
- HTTP request anatomy: method, URL, headers, body
- HTTP methods: GET, POST, PUT, PATCH, DELETE
- Status codes: 2xx, 3xx, 4xx, 5xx (the most important ones)
- JSON format
- APIs and REST basics
- Stateless requests

### Level 1 — The Router Station: Routing & Request Handling
- Creating routes/endpoints
- Path parameters (`/users/{id}`)
- Query parameters (`?page=2&status=paid`)
- Request body
- Returning responses and status codes
- REST resource naming conventions
- Route ordering and conflicts
- Routers/grouping (APIRouter), API versioning basics

### Level 2 — The Gatehouse: Validation & Errors
- Why never trust user input
- Pydantic models
- Field types, required vs optional, defaults
- Constraints (min/max length, ranges, regex, email)
- Nested models and lists
- Custom validators
- Error handling and custom exceptions
- Correct error status codes (400, 404, 409, 422)
- Consistent error response format
- Response models (hiding sensitive fields)

### Level 3 — The Data Vaults: Databases, Modeling & ORM
- What a database is; SQL vs NoSQL (overview)
- Tables, rows, columns, primary keys
- SQL: SELECT, WHERE, ORDER BY, LIMIT
- INSERT, UPDATE, DELETE
- Aggregations: COUNT, SUM, GROUP BY
- JOINs (inner, left)
- Data modeling: one-to-one, one-to-many, many-to-many
- Foreign keys and constraints
- Normalization (basic)
- ORM concepts (SQLAlchemy models, sessions)
- CRUD with ORM
- Relationships in ORM
- The N+1 problem and eager loading
- Transactions and rollbacks
- Migrations (Alembic concepts)
- Indexes (what and why)

### Level 4 — The Citadel: Authentication & Authorization
- Authentication vs authorization
- Password hashing (why never store plain passwords)
- Sessions vs tokens
- JWT: structure, signing, expiry
- Access + refresh tokens
- Protecting routes (dependencies)
- Roles and permissions (RBAC)
- Ownership checks ("can this user edit THIS item?")
- OAuth (conceptual overview)
- Common auth mistakes

### Level 5 — The Speedway: Performance
- Pagination (offset vs cursor)
- Filtering and sorting
- Query optimization basics
- Caching concepts: cache hit/miss, TTL
- Cache strategies: cache-aside, invalidation
- Redis concepts
- Rate limiting
- Compression, response size

### Level 6 — The Factory: Async & Background Work
- Sync vs async in web servers
- Background tasks
- Message queues and workers
- Retries and exponential backoff
- Idempotency
- Webhooks (sending and receiving)
- Scheduled jobs (cron)
- Events and event-driven basics

### Level 7 — The Control Room: Production Skills
- Reading stack traces and logs
- Structured logging
- Testing: unit vs integration, pytest basics, testing endpoints
- Environment variables and config
- Secrets management
- Security: SQL injection, XSS (backend side), CORS, CSRF basics, OWASP Top 10 overview
- Input sanitization
- Monitoring and health checks
- Docker basics (containers, Dockerfile)
- Deployment basics

### Level 8 — The Skyline: Architecture & Scaling
- Monolith vs microservices
- Horizontal vs vertical scaling
- Load balancers
- Stateless services
- Database replication and read replicas (concept)
- CDNs
- API gateways
- File storage (object storage)
- Real-time: WebSockets basics
- System design fundamentals (boss levels: design a URL shortener, a chat app, etc.)

### Capstone — "You Built This"
- Throughout the track, snippets the user writes are assembled into **one real project** (e.g., a mini e-commerce API).
- At the end, the user **downloads the full working codebase** — a portfolio piece.

---

## 6. Game Design

### 6.1 The core mechanic [DECIDED]
> The user writes a snippet inside a pre-built backend → a **traffic simulation** sends many requests at it → each request visibly **passes, bounces (4xx), or crashes the server (5xx)**.

This **Request Flow Visualizer** is the most important and most polished component. Most games reuse it.

### 6.2 Game type catalog (reusable templates)

| Game type | Used for | How it plays |
|---|---|---|
| **The Bouncer** | Validation | Requests queue at a gate; user writes rules; wrong rules let bad requests in or block good ones. |
| **Route Dispatcher** | Routing | Incoming URLs must reach the right handler; user writes route definitions. |
| **Query the Dungeon** | SQL | Treasure hidden in tables; user writes queries to find it; later rooms need JOINs. |
| **Model Architect** | Data modeling | Drag entities and relationships to satisfy a business requirement. |
| **N+1 Detective** | ORM performance | A page fires 101 queries; user fixes it; live query counter drops. |
| **Cache Keeper** | Caching | Slow DB (turtle) vs cache; user decides what/how long to cache; scored on speed vs stale data. |
| **Key Master** | Auth | Issue/verify tokens, protect routes, catch expired or forged tokens. |
| **Permission Maze** | Authorization | Users with different roles try actions; user writes permission checks. |
| **Conveyor Chaos** | Queues/jobs | Jobs on conveyor belts; handle retries, failures, idempotency. |
| **Status Code Speed Round** | HTTP basics, revision | Fast-paced matching/quiz. |
| **Fix the Bug** | Any topic | Highlighted broken snippet; find and fix. |
| **Fill the Blank / Pick the Line** | Any topic (mobile-friendly) | Choose or drag the correct code line. |
| **3 AM Incident (Boss Fight)** | Debugging, end of level | Server is on fire; user reads logs and stack trace, finds and patches the bug. |
| **Break It Mode** | Security | Attack a deliberately vulnerable sandboxed API (e.g., SQL injection), then patch it. |
| **System Builder** | Architecture | Drag components (LB, cache, DB, queue) to handle a traffic scenario. |

### 6.3 Game rules
- Minimum **2–3 required games per topic** plus a checkpoint.
- **Unlimited optional variants** for extra practice (grant XP, not required).
- Every game has: scenario text, starter code, editable region, public tests, hidden tests, visualizer type, character, hint set.

### 6.4 Rewards & progression
- **XP** for every game; more XP for checkpoints and boss fights.
- **Stars** (1–3) per checkpoint.
- **Streaks** (daily activity).
- **Combos** (consecutive correct answers in speed games).
- **Badges** (e.g., "First 200 OK", "N+1 Slayer", "No-Hint Hero").
- **City restoration:** each completed topic lights up part of the district — the user's personal city is their progress map.
- **Weekly leaderboard** (XP-based).
- **Certificates** per level (shareable).

---

## 7. AI Support

### 7.1 Modes
1. **Tiered hints** (during games):
   - Tier 1: gentle nudge ("Look at what happens when age is negative.")
   - Tier 2: concept explanation
   - Tier 3: partial snippet / pseudocode
   - Each tier used reduces the attempt's max score.
2. **Failure explainer:** after a failed run, AI reads the user's code + failing public test names/output and explains *why* in plain language.
3. **Concept chat ("Ask the Robot"):** free Q&A about concepts ("Explain JWT like I'm 10").
4. **Lesson simplifier:** "Explain this differently" button on lessons.

### 7.2 Guardrails [DECIDED]
- AI is delivered through the **mascot character**, not a generic chatbot.
- During scored attempts the AI **never outputs the full solution** (enforced by server-side system prompt + limited context).
- AI receives: topic, lesson summary, user's code, public test output, hint tier. It **never receives hidden test contents**.
- **Per-user daily AI limits** (configurable in admin).
- **Caching** of common questions per topic.
- Short prompts, cheap/fast model.
- All AI calls go through the backend (API key never in the browser).

### 7.3 Provider [OPEN / VERIFY]
- Use a **provider-agnostic wrapper** in the backend so the model can be swapped.
- Candidates with free tiers (verify current limits before building): Google Gemini API, Groq, others.

---

## 8. World, Story & Characters

### 8.1 World: Backend City [DECIDED concept]
A dark neon cyberpunk city that runs on servers. The user is a newly hired engineer bringing the broken city back online. Each level is a district that lights up as the user progresses.

| Level | District | Metaphor |
|---|---|---|
| -1 | The Academy | Training ground |
| 0 | The Signal Tower | Messages travel between towers |
| 1 | The Router Station | Train station sending requests to platforms |
| 2 | The Gatehouse | Guards checking everyone entering |
| 3 | The Data Vaults | Underground archives with glowing tables |
| 4 | The Citadel | Security fortress, keys and badges |
| 5 | The Speedway | Speed, racing, shortcuts |
| 6 | The Factory | Conveyor belts and workers |
| 7 | The Control Room | Screens, logs, alarms |
| 8 | The Skyline | The whole city from above |

The metaphors **teach**: a cache is a shortcut, a queue is a conveyor belt, validation is a gate guard.

### 8.2 Characters
- **Mascot (name TBD):** small glowing robot companion. Guide, cheerleader, and the face of AI hints. States: idle, happy, sad, thinking, worried, celebrating.
- **Packet:** tiny courier carrying requests; appears in all traffic simulations.
- **The Bouncer:** big guard; validation levels.
- **The Librarian:** old archivist; database levels.
- **Squirrel the Cacher:** hoards frequently used data; caching levels.
- **Glitch (villain):** causes bugs, attacks, and outages; boss fights and security levels.

### 8.3 Story delivery
- Short dialogue bubbles at lesson start, game start, success, and failure.
- Story text is **editable in the admin panel** (no code change needed).
- Each level ends with a boss fight tied to the story (Glitch attacks the district).

---

## 9. UI / UX & Visual Direction

### 9.1 Style [DECIDED]
- **Dark theme** base: deep navy / near-black (e.g., `#0a0e1a`), never pure black.
- **Neon accents with consistent meaning:**
  - Cyan → requests / data flow
  - Green → success / 2xx
  - Amber → warnings / 4xx
  - Red → errors / 5xx
  - Purple → AI / magic moments
- **Glow** on active elements, **gradient** headings, **glass panels** (use blur sparingly — it's expensive).
- **Fonts:** a bold modern UI font (e.g., Space Grotesk or Sora); monospace for code (JetBrains Mono or Fira Code).
- **Animated backgrounds** per district (slow grids, particles, data streams) — subtle and slow.
- **Admin panel:** same dark theme but calmer — less glow, more data clarity.

### 9.2 Game feel ("juice")
- Success: particle burst, character celebration, XP bar fill with sound, district lights up.
- Failure: server sparks, light screen shake, Glitch reacts — dramatic but never humiliating.
- Sound effects with an always-visible mute toggle.
- Keyboard shortcuts: `Ctrl/Cmd+Enter` run code, arrow keys in quiz games, WASD/arrows to walk the robot on the world map.

### 9.3 Screens
1. **Landing page** — animated skyline lighting up, "Start your first shift" CTA.
2. **Auth** — sign up, login, verify email, forgot/reset password.
3. **Onboarding** — robot intro, experience placement quiz.
4. **World map** — districts (locked = dark, done = glowing, current = pulsing); walkable with keyboard.
5. **Level/chapter view** — topics list with progress and stars.
6. **Lesson screen** — concept + animated diagram + character dialogue.
7. **Game screen** — code editor (left), live visualizer (right), character (corner), score/hint bar.
8. **Result screen** — score, stars, XP, next actions.
9. **Profile** — stats, badges, personal lit-up city, certificates.
10. **Leaderboard** — weekly XP.
11. **Settings** — sound, performance mode, reduced motion, account.
12. **Admin panel** — see Section 10.

### 9.4 Layout rules
- The **code editor panel is calm**: solid background, no animation behind code, high contrast.
- Never use **color alone**: pair with icons (✓ ✕ ⚠) and text.
- Respect `prefers-reduced-motion`.
- **Performance mode** toggle: disables particles, blur, and heavy backgrounds.

### 9.5 Mobile strategy
- Coding on phones is painful → mobile favors **drag-and-drop, pick-the-line, fix-the-highlighted-bug** game types.
- Full coding games show a **"Best on desktop"** tag but still work.

### 9.6 Loading moments
- Cold starts and Pyodide loading become content: robot tips, mini-facts, or a tiny "catch the packets" mini-game.
- Themed message: "Booting the server… this is literally what a cold start is!"

---

## 10. Admin Module

### 10.1 Content management (highest priority)
- CRUD for Tracks → Levels → Chapters → Topics → Lessons → Games, with **drag-and-drop reordering**.
- **Game builder form:** scenario text, starter code, editable region markers, public tests, hidden tests, variant parameters, visualizer type, district, character, hint tiers, dialogue lines.
- **Test-run / preview:** admin plays the game inside the admin panel before publishing and confirms a reference solution passes.
- **Reference solution** stored per game (never sent to users).
- **Draft / Published** status.
- **Per-topic settings:** pass threshold, required game count, hints allowed, retest cooldown.
- **Versioning:** editing a live game creates a new version; users mid-attempt keep the old version.
- **Visual kit selection** via dropdowns (district background, character, visualizer) — no new art per game.

### 10.2 User tracking
- User list: search, filter; shows level, XP, streak, last active, signup date.
- User detail: full journey — every topic's score, attempts, hints used, time spent, where stuck.
- Actions: reset progress, manually unlock a chapter, block/unblock accounts, change role.

### 10.3 Learning analytics
- **Drop-off funnel** by chapter (where users quit).
- **Hardest games:** failure rate, average attempts, average hints (a game most people fail is probably badly designed).
- **AI usage:** most-asked questions per topic (signals where lessons need improvement).
- DAU/WAU, completion rates, average time per topic.

### 10.4 Platform management
- **Roles:** `super_admin` (everything), `content_editor` (content only), `user`. Enforced **server-side on every admin route**.
- **Feedback inbox:** user reports per game ("broken", "confusing"), attached to the game.
- **Announcements** (e.g., "New chapter: Caching is live!").
- **Audit log:** which admin changed what, and when.
- **Usage monitor:** AI calls today, emails sent this month vs limit, DB size vs free limit.
- **AI settings:** daily limits per user, model choice, hint penalty values.

### 10.5 Admin MVP scope
Phase 1: content management + test-run + basic user list/detail.
Later: analytics, feedback inbox, announcements, audit log, usage monitor.

---

## 11. Code Execution & Grading

### 11.1 Where code runs [DECIDED]
- **Practice games:** user code runs **in the browser**.
  - Python via **Pyodide** (Python compiled to WebAssembly).
  - SQL via **PGlite** (Postgres in WASM) for realism; **sql.js** (SQLite) as a lighter fallback.
  - Benefits: zero server cost, instant runs, no server security risk, works even when backend is asleep.
- **Checkpoint games (the scored gates):** final submission is **re-graded on the backend** with hidden tests (see 11.3).

### 11.2 The backend harness
- Games don't run a real web server in the browser. A **harness** loads the pre-written backend code + the user's snippet and sends simulated requests **in-process** (ASGI-style call), then returns results to the visualizer.
- Simulated infrastructure (Python mocks inside the harness):
  - Fake Redis (dict with TTL)
  - Fake queue/worker
  - Fake email/webhook endpoints
  - Query counter (for N+1 games)
  - Clock control (for TTL/expiry games)
- **[DECIDED — Phase 0 spike, 2026-09-25]:** real FastAPI + Pydantic v2 run in Pyodide 314.0.7. Measured: core boot ~1.4 s, FastAPI stack load ~0.5 s + import ~0.9 s, in-process request ~0.13 ms; extra download ~2.2 MB gzipped on top of ~6 MB Pyodide core (cached after first visit). No mini-framework needed. Pyodide bundles fastapi 0.136.1 / pydantic 2.12.5, so the server sandbox is pinned to the same versions.

### 11.3 Grading
- **Grade by behavior, not string matching** — many correct answers exist.
- **Public tests:** shipped to the browser, shown to the user.
- **Hidden tests:** **never sent to the browser** (would leak answers via DevTools). Generated server-side from the game template + attempt seed.
- **Checkpoint flow:**
  1. User submits snippet.
  2. Backend regenerates hidden tests from `game_version + seed`.
  3. Backend runs snippet + tests in a **sandboxed subprocess**.
  4. Score is computed and saved; progress unlocks if passed.
- **Server sandbox rules:** separate subprocess, hard timeout (e.g., 3–5 s), memory limit, no network, no filesystem writes, restricted imports (AST check + allowlist). Only small snippets are accepted (size limit).
- **Risk note:** executing untrusted Python on the server is the biggest security surface. Keep the sandbox strict; if abuse appears, move checkpoint grading to an isolated worker service or a hosted sandbox later.

---

## 12. Technical Stack [DECIDED unless marked]

### 12.1 Frontend
| Purpose | Choice |
|---|---|
| Framework | **Next.js** (App Router) + **TypeScript** |
| Styling | **Tailwind CSS** + **shadcn/ui** (restyled to neon theme) |
| UI animation | **Framer Motion (Motion)** |
| Characters | **Rive** (interactive state machines); **Lottie** for simple loops |
| Game scenes / visualizer | **PixiJS** (canvas); Phaser only if more engine features are needed |
| Particles | **tsParticles** or small custom canvas |
| Code editor | **CodeMirror 6** (lighter than Monaco, better on mobile) |
| Python in browser | **Pyodide** (loaded in a Web Worker) |
| SQL in browser | **PGlite** (fallback: sql.js) |
| Server state | **TanStack Query** |
| Client state | **Zustand** |
| Sound | **Howler.js** + free assets (Kenney.nl, freesound.org) |
| Admin charts | **Recharts** |
| Forms/validation | React Hook Form + Zod |

### 12.2 Backend
| Purpose | Choice |
|---|---|
| Framework | **FastAPI** (Python) |
| Validation | **Pydantic v2** |
| ORM | **SQLAlchemy 2.x** (async) + **asyncpg** |
| Migrations | **Alembic** |
| Password hashing | **Argon2** (argon2-cffi) or bcrypt |
| JWT | **PyJWT** |
| Rate limiting | **slowapi** (or simple DB/in-memory limiter) |
| HTTP client | **httpx** (AI + EmailJS REST calls) |
| Sandbox | Python subprocess with resource limits + AST import allowlist |
| Testing | **pytest** |

### 12.3 Infrastructure (free tier) [VERIFY limits periodically]
| Purpose | Service | Notes |
|---|---|---|
| Frontend hosting | **Vercel (Hobby)** | Hobby plan is for **non-commercial use**; upgrade to Pro if the project is monetized. |
| Backend hosting | **Render (Free web service)** | Spins down after ~15 min idle; 30–60 s cold start; 750 free instance hours/month (covers one service 24/7). |
| Database | **Neon (Free Postgres)** | ~0.5 GB storage, scale-to-zero (~0.5 s resume). Do **not** use Render's free Postgres (it expires). |
| Email | **EmailJS (Free)** | ~200 requests/month, 2 templates. Backup: Brevo or Resend free tiers. |
| AI | Free-tier LLM API | See Section 7.3. |
| Keep-alive | **cron-job.org** or **UptimeRobot** | Ping backend health endpoint every 10–14 min. |
| Code repo / CI | **GitHub** + GitHub Actions | Free for public/private repos within limits. |

---

## 13. System Architecture

### 13.1 High-level
```
┌──────────────────────── Browser ────────────────────────┐
│ Next.js app (from Vercel)                               │
│  • UI, world map, lessons, games                        │
│  • Pyodide + PGlite in Web Workers (practice runs)      │
│  • Request Flow Visualizer (PixiJS)                     │
└───────────────┬─────────────────────────────────────────┘
                │ /api/* (same-origin via Next.js rewrites)
                ▼
┌──────────── Vercel (Next.js server) ────────────┐
│ • Serves pages + cached content (ISR)           │
│ • Rewrites /api/* → Render backend              │
│ • On-demand revalidation webhook for content    │
└───────────────┬─────────────────────────────────┘
                ▼
┌──────────── Render (FastAPI) ───────────────────┐
│ • Auth, progress, attempts, scoring             │
│ • Checkpoint grading sandbox                    │
│ • AI proxy + limits                             │
│ • Admin API                                     │
│ • EmailJS REST calls                            │
└───────┬───────────────────────┬─────────────────┘
        ▼                       ▼
   Neon Postgres          AI provider / EmailJS
```

### 13.2 Key architecture decisions
1. **Same-origin API via Next.js rewrites** (`/api/*` → Render). Avoids CORS headaches and lets auth cookies work as first-party cookies.
2. **Content served from Vercel's cache.** Published content (lessons, game configs minus hidden tests/solutions) is fetched from FastAPI by Next.js with **ISR**, then cached at Vercel. When an admin publishes, the backend calls a Next.js **on-demand revalidation** route. Result: games load instantly even if Render is asleep.
3. **Games playable without the backend.** Practice runs happen in the browser. Backend only needed for login, saving, checkpoints, AI, and admin.
4. **Optimistic saving.** Practice results show immediately; sync to backend in the background with retry (handles cold starts).
5. **Pyodide in a Web Worker**, preloaded in the background while the user reads the lesson.

### 13.3 Handling Render cold starts
- Keep-alive ping every 10–14 minutes.
- Content from Vercel cache (no backend needed to browse/play).
- Optimistic, queued saves.
- Friendly themed "waking up the server" loader as last resort.
- **[VERIFY]** Vercel external rewrites have a proxy timeout; a 30–60 s Render cold start may exceed it. The frontend API client must retry the first failed call after a cold start.

---

## 14. Auth & Email Flows

### 14.1 Auth [DECIDED]
- Email + password signup; password hashed with Argon2/bcrypt.
- **Access token** (short-lived, ~15 min) + **refresh token** (longer, rotated), both in **httpOnly, Secure cookies**.
- Refresh tokens stored hashed in DB; revocable (logout, admin block).
- Role stored on the user; admin routes check role server-side.
- Optional later: Google/GitHub OAuth.

### 14.2 Email via EmailJS [DECIDED]
- Used for: email verification, password reset, (optional) important announcements.
- **Tokens/OTPs are generated on the backend**, stored **hashed** with expiry, and emails are sent via **EmailJS REST API from the backend** using the private key (enable non-browser API access in EmailJS settings). **Never generate OTPs in the browser.**
- Track monthly email count in DB; show it in the admin usage monitor; fall back or throttle near the limit.

---

## 15. Data Model (initial schema)

> Postgres on Neon. Names are indicative; refine during implementation.

**Users & auth**
- `users` — id, email (unique), password_hash, display_name, role (`user` | `content_editor` | `super_admin`), is_verified, is_blocked, experience_level, created_at, last_active_at
- `refresh_tokens` — id, user_id, token_hash, expires_at, revoked_at, created_at
- `email_tokens` — id, user_id, purpose (`verify` | `reset`), token_hash, expires_at, used_at

**Content**
- `tracks` — id, slug, title, description, order, status
- `levels` — id, track_id, slug, title, district_key, story_intro, order, status
- `chapters` — id, level_id, slug, title, order, status
- `topics` — id, chapter_id, slug, title, order, status, pass_threshold, required_games_count, hints_allowed, retest_cooldown_minutes
- `lessons` — id, topic_id, content (JSON/markdown blocks), diagram_key, dialogue (JSON), version, status
- `games` — id, topic_id, game_type, is_checkpoint, order, status, current_version_id
- `game_versions` — id, game_id, version, scenario (JSON), starter_code, editable_region (JSON), public_tests (JSON), hidden_test_template (JSON/code), variant_params (JSON), reference_solution, visualizer_type, character_key, hints (JSON, tiered), dialogue (JSON), created_by, created_at

**Progress & attempts**
- `attempts` — id, user_id, game_version_id, seed, code (latest/best only kept long-term), score, passed, hints_used, duration_seconds, is_checkpoint, created_at
- `topic_progress` — user_id, topic_id, status (`locked` | `unlocked` | `passed`), best_score, stars, attempts_count, passed_at
- `chapter_progress`, `level_progress` — similar summary rows
- `xp_events` — id, user_id, source, amount, created_at
- `streaks` — user_id, current_streak, longest_streak, last_activity_date
- `badges`, `user_badges`

**AI**
- `ai_interactions` — id, user_id, topic_id, mode (`hint` | `explain` | `chat`), hint_tier, prompt_tokens, completion_tokens, created_at (store summaries, not full logs, to save space)
- `ai_cache` — key (topic + normalized question hash), response, hits, created_at

**Platform**
- `feedback_reports` — id, user_id, game_id, type, message, status, created_at
- `announcements` — id, title, body, published_at, created_by
- `audit_logs` — id, admin_id, action, entity_type, entity_id, diff (JSON), created_at
- `usage_counters` — period, emails_sent, ai_calls

**Storage-saving rules (0.5 GB budget):**
- Keep only best/last code per user per game long-term; prune old raw attempts periodically (keep aggregates).
- Store AI interaction metadata, not full transcripts.
- Monitor DB size in admin.

---

## 16. Game Config Format (example)

```json
{
  "game_type": "bouncer",
  "title": "Guard the Signup Gate",
  "district": "gatehouse",
  "character": "bouncer",
  "visualizer": "request_flow",
  "is_checkpoint": false,
  "scenario": {
    "intro": "Glitch is sending fake signups! Only let real users through.",
    "goal": "Validate the signup request: {field_email} must be a valid email, {field_age} must be between {min_age} and {max_age}."
  },
  "variant_params": {
    "field_email": ["email", "contact_email", "user_email"],
    "field_age": ["age", "user_age"],
    "min_age": [13, 16, 18],
    "max_age": [100, 120]
  },
  "starter_code": "from pydantic import BaseModel, EmailStr, Field\n\nclass SignupRequest(BaseModel):\n    # >>> EDIT START\n    pass\n    # <<< EDIT END\n",
  "editable_region": { "start_marker": "# >>> EDIT START", "end_marker": "# <<< EDIT END" },
  "public_tests": [
    { "request": { "{field_email}": "ana@example.com", "{field_age}": 25 }, "expect_status": 200 },
    { "request": { "{field_email}": "not-an-email", "{field_age}": 25 }, "expect_status": 422 }
  ],
  "hidden_test_template": "generated server-side from variant_params + seed (never shipped to browser)",
  "hints": [
    { "tier": 1, "text": "What should happen when the age is below the minimum?" },
    { "tier": 2, "text": "Pydantic's Field() accepts ge= and le= to set numeric limits." },
    { "tier": 3, "text": "Something like: age: int = Field(ge=..., le=...)" }
  ],
  "dialogue": {
    "start": "Nobody gets in without the right papers!",
    "success": "Clean gate! Glitch's fakes bounced right off.",
    "fail": "Uh-oh, some fakes slipped through. Check the logs."
  }
}
```
> `reference_solution` and hidden tests live only in the database/backend and are stripped from the public content payload.

---

## 17. API Outline (FastAPI)

**Public / auth**
- `POST /auth/register` · `POST /auth/login` · `POST /auth/logout` · `POST /auth/refresh`
- `POST /auth/verify-email` · `POST /auth/forgot-password` · `POST /auth/reset-password`
- `GET /health` (keep-alive target)

**Content (public, cached by Next.js)**
- `GET /content/tracks` · `GET /content/levels/{slug}` · `GET /content/topics/{slug}` (public fields only)

**Learner**
- `GET /me` · `PATCH /me` · `GET /me/progress`
- `POST /attempts/practice` (save practice result, batched/optimistic)
- `POST /attempts/checkpoint/start` (returns seed + public tests)
- `POST /attempts/checkpoint/submit` (server-graded)
- `POST /ai/hint` · `POST /ai/explain` · `POST /ai/ask`
- `GET /leaderboard/weekly` · `GET /me/badges`
- `POST /feedback`

**Admin (role-protected)**
- CRUD: `/admin/tracks`, `/admin/levels`, `/admin/chapters`, `/admin/topics`, `/admin/lessons`, `/admin/games`, `/admin/games/{id}/versions`
- `POST /admin/games/{id}/test-run` · `POST /admin/content/publish`
- `GET /admin/users` · `GET /admin/users/{id}` · `POST /admin/users/{id}/reset|unlock|block|role`
- `GET /admin/analytics/funnel|hardest-games|ai-usage|activity`
- `GET/PATCH /admin/feedback` · CRUD `/admin/announcements`
- `GET /admin/audit-logs` · `GET /admin/usage` · `GET/PATCH /admin/settings`

---

## 18. Repository Structure [DECIDED — two repos]

The project uses **two separate git repositories** instead of one monorepo:
`backend-city-frontend` (Vercel) and `backend-city-backend` (Render). Locally they sit side by side:

```
backend-city/                 # plain folder, NOT a git repo
├── frontend/                 # repo: backend-city-frontend (Next.js, deployed to Vercel)
│   ├── src/
│   │   ├── app/              # routes: (marketing), (auth), (game), admin/, api/revalidate/
│   │   ├── features/         # feature modules: landing, auth, world-map, game, ...
│   │   ├── components/       # ui/ (design system), characters/, effects/
│   │   ├── engine/           # game engine: config types, harness bridge, visualizer, scoring
│   │   ├── workers/          # pyodide.worker.ts (sql.worker.ts later)
│   │   ├── stores/ lib/ styles/
│   ├── public/harness/       # GENERATED copy of backend/harness (git-ignored)
│   ├── scripts/sync-harness.mjs
│   ├── harness.lock          # pinned backend commit for CI/Vercel builds
│   └── next.config.ts        # /api/* rewrites to the backend
└── backend/                  # repo: backend-city-backend (FastAPI, deployed to Render)
    ├── app/
    │   ├── api/routes/       # thin routers
    │   ├── core/             # config, security, deps, errors, rate limits
    │   ├── db/ models/ repositories/ schemas/ services/
    │   ├── games/            # SERVER-ONLY: variants, templates, hidden tests
    │   └── sandbox/          # checkpoint execution sandbox
    ├── harness/              # SHARED Python harness (canonical copy lives here)
    ├── content/seed/         # initial level/game JSON
    ├── alembic/ tests/ Dockerfile docker-compose.yml
    └── docs/
```

**Why the harness lives in the backend repo:** its security-critical consumer is the checkpoint
grading sandbox, and it must never contain answers (it is public). The frontend runs
`scripts/sync-harness.mjs` before `dev`/`build`:
1. If `../backend/harness` exists (local dev) → copy it into `public/harness/`.
2. Otherwise (Vercel/CI) → download the backend repo at the commit pinned in `harness.lock`.

Result: browser (Pyodide) and server (sandbox) run identical harness code, and a harness change
reaches the frontend only when `harness.lock` is bumped deliberately. `harness/requirements.txt`
pins fastapi/pydantic to the versions bundled with the Pyodide release, and the sandbox runs in a
venv built from it, so grading behaves exactly like the browser.

> **Rule:** nothing in `harness/` may contain hidden tests, reference solutions, or variant logic.
> That code lives in `backend/app/games/` and never leaves the server.

## 19. Security, Performance & Accessibility Checklist

**Security**
- Hidden tests and reference solutions never leave the backend.
- Server sandbox: timeout, memory limit, no network, import allowlist, snippet size limit.
- Argon2/bcrypt hashing; httpOnly Secure cookies; refresh token rotation.
- Role checks on every admin endpoint (server-side).
- Rate limits on auth, AI, and checkpoint endpoints.
- EmailJS and AI keys only on the backend.
- Audit log for admin actions.
- Input validation everywhere (the platform should practice what it teaches).

**Performance**
- Lazy-load per screen; code-split heavy libs (PixiJS, Rive, Pyodide).
- Preload Pyodide in a Web Worker during the lesson.
- Pause background animations while the user is typing.
- Performance mode toggle; minimal blur.
- Content from Vercel ISR cache.

**Accessibility**
- Respect `prefers-reduced-motion`.
- Color never the only signal (icons + text).
- Keyboard navigable; visible focus states.
- High-contrast code editor theme.
- Mute toggle always visible.

---

## 20. Challenges & Solutions Summary

| Challenge | Solution |
|---|---|
| Backend concepts are invisible | Request Flow Visualizer + district metaphors |
| Running user code safely | Browser execution (Pyodide/PGlite) for practice; strict server sandbox for checkpoints |
| Grading many valid answers | Behavior-based tests, not string matching |
| Answer leakage via DevTools | Hidden tests server-side only, generated from seed |
| Memorizing retests | Variant templates + seeds |
| Content creation at scale (200+ games) | Config-driven level engine + admin game builder + reusable visual kits; AI-assisted variant drafting with human review |
| Art for every game | Reusable per-district visual kits; Rive characters |
| Render cold starts | Keep-alive ping, Vercel-cached content, browser execution, optimistic saves, themed loader |
| Free DB storage limit | Neon; prune raw attempts; store aggregates |
| EmailJS 200/month | Only essential emails; usage monitor; backup provider ready |
| AI cost / abuse | Free-tier provider, per-user limits, caching, short prompts, backend proxy |
| Heavy visuals on weak devices | Lazy loading, performance mode, pause animations while typing |
| Flashy vs readable | Calm editor zone |
| Mobile coding is hard | Mobile-friendly game types; "best on desktop" tags |
| Users forget old topics | Spaced repetition + daily review |
| Gating frustration | Soft-fail support, recap suggestions, AI explainer |
| Admin panel scope creep | Build content management first; analytics later |
| FastAPI-in-Pyodide uncertainty | Phase 0 spike; fallback mini-framework harness |
| Free tiers change | Portable code (standard Postgres, Dockerfile); re-verify limits |
| Vercel Hobby is non-commercial | Upgrade to Pro before monetizing |

---

## 21. Roadmap

### Phase 0 — Technical spikes (1–2 weeks)
- Pyodide + FastAPI/Pydantic feasibility and load time.
- Request Flow Visualizer prototype (PixiJS) with one Bouncer game.
- PGlite query game prototype.
- Server sandbox prototype on Render free tier.
- Decide harness approach (real FastAPI vs mini framework).

### Phase 1 — MVP
- Auth (signup, login, verify email, reset password).
- Levels 0–2 (Signal Tower, Router Station, Gatehouse), each topic with 3 games + checkpoint.
- Scoring, gating, variants, retest.
- World map (basic), lesson screen, game screen, result screen.
- Dark neon theme, mascot with basic states, one district's visual kit.
- Admin: content CRUD, game builder, test-run, publish, basic user list/detail.
- Deployment on Vercel + Render + Neon, keep-alive ping.

### Phase 2 — Engagement & AI
- AI tiered hints, failure explainer, concept chat.
- XP, stars, streaks, badges.
- Levels 3–4 (Data Vaults, Citadel).
- Admin analytics (funnel, hardest games), feedback inbox.
- Sound effects, more characters, performance mode.

### Phase 3 — Depth
- Levels 5–6 (Speedway, Factory).
- Boss fights (3 AM Incident), Break It Mode.
- Leaderboards, spaced repetition / daily review.
- Audit logs, announcements, usage monitor.

### Phase 4 — Mastery & growth
- Levels 7–8 (Control Room, Skyline), System Builder game.
- Capstone "You Built This" codebase export.
- Certificates, shareable profiles.
- Community-created levels (moderated).
- Additional tracks (e.g., Node.js/Express) using the same engine.

---

## 22. Open Decisions [OPEN]

1. **Primary target audience** — complete beginners vs programmers new to backend (plan currently supports both via placement).
2. **Final project name** and mascot name.
3. **AI provider** (verify current free-tier limits).
4. **Monetization** (affects Vercel plan and possibly other services).
5. **Language(s)** — English only at launch, or also Hindi/other languages (i18n affects content model; add a `locale` field early if likely).
6. ~~**Harness approach**~~ — **decided:** real FastAPI in Pyodide (Phase 0 spike, see §11.2).
7. **PGlite vs sql.js** for browser SQL (decided after Phase 0 based on load size).
8. **OAuth login** (Google/GitHub) — now or later.
9. **Leaderboard privacy** — public display names, opt-out option.

---

## 23. Glossary

- **Snippet:** the small code region the user edits inside a pre-written backend.
- **Harness:** the code that loads backend + snippet and sends simulated requests to it.
- **Visualizer:** the animated view of requests/queries/jobs reacting to the user's code.
- **Variant:** a generated version of a game from its template and a seed.
- **Checkpoint:** the scored game that gates progress.
- **Public tests / hidden tests:** tests the user can see vs tests only the backend runs.
- **District:** a themed area of Backend City representing a level.
- **Visual kit:** reusable background, character, and visualizer theme for a district.
- **ISR:** Incremental Static Regeneration (Next.js cached pages refreshed on demand).
- **Cold start:** delay when a sleeping free-tier server wakes up.
