# Full Stack City: rebrand + 3-act homepage

Living plan for turning Backend City into **Full Stack City**. Tick items as they land and add
notes/decisions at the bottom. Owner decisions (2026-09-26) are recorded in "Decisions".

## Goal

One city, three sides of the web:

1. **Frontend**: the city surface (glass towers, windows, signs) = what users see. Course: coming soon.
2. **Backend**: inside a building (steel frame, brick core, wiring, checkpoint, vault) = the
   engine room. Course: open today (the current curriculum).
3. **Full stack**: both joined: surface windows wired to the structure inside. Course: coming soon.

The learner chooses a side in a gamified way (in the 3D city + one question at signup).
Coming-soon tracks collect **Notify me** interest so we can see demand.

## Decisions

| Topic                | Decision                                                                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Third part           | Full stack (both joined). Camera pulls out, light lines connect surface to structure.                                                                                     |
| Asking what to learn | "Choose your side" over the 3D city at the end of the homepage + one onboarding question saved to the account (`users.learning_goal`).                                    |
| Coming soon          | Card visible; **Notify me** records interest (`track_interests`). No emails yet.                                                                                          |
| Rename scope         | Brand = **Full Stack City** everywhere. Today's map becomes the **Backend District**; its districts (Academy, Signal Tower, Router Station, Gatehouse…) keep their names. |
| URL                  | Not code: Vercel → Settings → Domains (free `*.vercel.app` alias now, custom domain at launch). Old URL set to redirect.                                                  |

## Homepage story (one pinned 3D canvas, scroll-driven)

### Act 1: Frontend (surface)

- Hero: "Full Stack City", build both sides of the web.
- Chapter: **Frontend District** (HTML, CSS, JS, components, state), **Coming soon** badge.

### The dive

(As built: 14 chapters = 14 camera stops; see `city3d/cityScene.ts` STOPS and `story/chapters.ts`.)

- Camera flies to one landmark tower; an X-ray sweep peels the glass facade top to bottom,
  revealing the structure inside.

### Act 2: Backend (inside the building): one floor per district

| Building part                              | Backend idea                           | District                            |
| ------------------------------------------ | -------------------------------------- | ----------------------------------- |
| Brick core walls                           | the language underneath (Python)       | Academy                             |
| Wiring/cables with glowing packets         | HTTP requests                          | Signal Tower                        |
| Junction/switch room                       | routing to handlers                    | Router Station                      |
| Lobby security checkpoint                  | validation                             | Gatehouse                           |
| Steel columns + beams                      | the framework holding it all (FastAPI) | whole frame                         |
| Basement vault, locked rooms (scaffolding) | databases, auth                        | Data Vaults, Citadel (construction) |

Packets (pass / bounce / crash) keep flowing along the wiring.

### Act 3: Full stack (pull-out)

- Camera exits through the roof, facade closes, light lines join windows to the wiring.
- **Choose your side** cards: Frontend (coming soon, Notify me) · Backend (Enter the Backend
  District) · Full stack (coming soon, Notify me).

Rest of the page (You know this end, FAQ, final call) stays with Full Stack City copy.

### Fallbacks

Reduced motion: one still frame per act. No WebGL: 2D skyline + static cutaway illustration.
Mobile / performance mode: lighter building (fewer beams, no reflection).

## In the app

- Onboarding step 1: "Which side of the city?" → `PUT /me/goal`. Backend continues; frontend /
  full stack → interest saved, explain coming soon, offer the Backend District meanwhile.
- Wordmark, metadata, copy → Full Stack City; map title → Backend District.
- Admin content page shows interest per track.

## API (backend)

- `GET /content/tracks` → `[{slug, title, description, status: open|coming_soon}]` (public).
- `PUT /me/goal {track}` → `UserPublic` (+ `learning_goal`); coming-soon choice also records interest.
- `GET /me/interests` / `POST /me/interests {track}` → `{tracks: [slug]}` (Notify me, idempotent).
- Tracks seeded from `curriculum.json` `coming_soon`: `frontend`, `full-stack` (draft = coming soon).
- Admin `GET /admin/content` → `tracks: [{slug, title, status, interested}]`.

## Build order and status

- [x] **Step 1: rename, tracks + interest API, Choose your side picker, coming-soon states** (2026-09-26, branch `feat/full-stack-city`)
  - [x] Backend: `track_interests` table, `users.learning_goal`, migration `b0de7ed0e716`
  - [x] Backend: tracks endpoint, goal, interests, admin counts, tests
  - [x] Frontend: brand rename (wordmark, metadata, copy), map → Backend District
  - [x] Frontend: Choose your side section + Notify me, Frontend District coming-soon chapter
  - [x] Frontend: admin content page shows track interest
- [x] **Step 2: frontend tour + the dive + building interior** (owner feedback applied: longer
      frontend tour; real zoom inside, floor by floor)
  - [x] 5 frontend chapters across the city (surface, HTML, CSS lights the windows,
        JavaScript street traffic, components + state from above), all "Coming soon"
  - [x] Backend Tower: facade cut away roof → ground with a glowing cut line
  - [x] Zoom: steel frame close-up → brick core close-up (Academy)
  - [x] Inside at eye level, rising through a stairwell opening: lobby checkpoint (Gatehouse),
        floor 1 junction room (Router), floor 2 racks + riser + ceiling trays (Signal Tower),
        floor 3 vault being fitted (Data Vaults; Citadel bars on floor 4), roof scaffolding + crane
  - [x] Interior packets: street → door → checkpoint (bounce) → riser → junction → handler
  - [x] Each part powers up as the camera reaches it; night + Daybreak; phone checked
  - [x] Test: one camera stop per chapter (`chapters.test.ts`)
- [ ] **Step 3: pull-out + light lines (Act 3)**, picker composed over the scene
- [ ] **Step 4: onboarding question, copy pass, screenshots (both themes, mobile), docs**

After this: resume content packs (lessons in DB → admin create/clone → YAML/JSON import/export).

## Notes

- Phone pass (all pages): sections use less vertical padding and a 12px gutter, cards tighter,
  code at 0.7-0.76rem; briefing column `min-w-0` (long code lines had widened the whole page
  to ~560px); district steps put the icon beside the text.

- Phones: story chapters are compact bottom cards (title + 3 lines; points and the gate demo
  hidden) so the 3D stays visible; hero trimmed, live legend hidden. Daybreak inside the tower:
  darker materials, bloom -75% and exposure -10% while the camera is inside.

- Step 1: the picker is a section after the 3D tour for now; step 3 moves it over the scene.
  Logged-out "Notify me" / "Start" go to `/signup?goal=<track>`, which saves the goal on signup.

- The backend track slug stays `python-backend` (URLs, progress, admin unchanged).
- Existing production track title stays until edited in the DB; the homepage and picker use their own display copy keyed by slug.
