# Sancta Familia — Family Management & Homeschooling Dashboard

## Overview
A Python HTTP server (no framework) running on port 5000. A Catholic family dashboard for the McAdams family: Lauren (Mom), John (Dad), JP (14), Joseph (12), Michael (5), James (13 months). Features Mass readings, weather, meal plans, calendar, chores, and a five-companion AI ecosystem: Lucy (Catholic friend/integrator), Lorenzo (personal chef), Father Gregory (academic headmaster), Coach (family fitness), Dr. Monica (child development + pediatric health). Full authentication with per-user access control.

## Family Quest App (Phase 2 — RPG Battle System)
Lives in `family_quest/` directory, served at `/quest/*` by the main app via `fq_bridge.py`.

- **Bridge**: `family_quest/fq_bridge.py` — imported by the main app; routes `/quest/*` GET/POST into FQ
- **Adapter**: `family_quest/fq_api.py` — the ONLY file in FQ that imports from the main app (auth, daily schedule). All other FQ modules call through this adapter.
- **Auth**: `fq_auth.py` delegates to `fq_api` (no direct parent imports)
- **Data files**: `family_quest/data/` — `quests.json`, `xp.json`, `rewards.json`, `streaks.json`, `redemptions.json`, `characters.json`, `equipment.json`, `inventory.json`, `stamina.json`, `battles.json`, `mines.json`, `boss_settings.json`
- **Modules**: `fq_data.py` (all data/engine logic), `fq_render.py` (HTML shell), `fq_views_parent.py` (parent views), `fq_views_child.py` (child board)
- **Quest types**: daily, side, boss, event; each with XP value, assigned children, date, optional item_reward
- **Level thresholds**: L1=0 (Novice), L2=100 (Apprentice), L3=250 (Knight), L4=500 (Champion), L5=1000 (Legend)
- **Sessions**: Separate cookie `fq_session` (Path=/quest) so it doesn't conflict with main app session
- **Separation rule**: No FQ module (except `fq_api.py` and `fq_bridge.py`) may import from the parent directory

### Phase 2 RPG Features
- **Resources**: Coins (existing), Crystals, Diamonds — all tracked in xp.json per child; shown on board
- **Characters**: Archer (high atk/low def), Fighter (balanced), Defender (high def/low atk) — selectable per child
- **Equipment**: 4 slots (Sword, Shield, Armor, Ring) each 0–5 levels; upgraded using crystals/diamonds; modify attack/defense stats
- **Stamina**: Max 10 ⚡; spent on boss battles/mine runs; refills +3 when all daily quests complete
- **Boss Battle engine**: Quests completed → attack hits → damage vs boss HP; sword level reduces quests/hit; win awards coins+XP; lose adds penalty chores (reduced by defense); Battle Axe item doubles hits
- **Mine Run engine**: Gold/Crystal/Diamond mines; 10-min runs; collect any time; cave-in on 3× overtime; speed bonus; Hammer item gives 1.5× yield
- **Single-use items**: Battle Axe (boss) and Hammer (mine); awarded by parents via Boss Settings or via quest/reward item_reward field; consumed on use
- **Equipment upgrades**: Children spend crystals/diamonds to upgrade slots; costs scale per level
- **Parent controls**: Boss Settings page sets difficulty (easy/medium/hard/legendary) and enables/disables boss daily; parents can directly award items to any child

### Key API Routes (Phase 2 additions)
- `POST /quest/api/set-character` — `{child, character}`
- `POST /quest/api/upgrade-equipment` — `{child, slot}`
- `POST /quest/api/boss-battle` — `{child, difficulty, use_battle_axe}`
- `POST /quest/api/start-mine` — `{child, mine_type, use_hammer}`
- `POST /quest/api/collect-mine` — `{child, mine_id}`
- `GET/POST /quest/boss-settings` — parent boss configuration page
- `POST /quest/boss-settings/save` — saves difficulty/availability
- `POST /quest/boss-settings/award-item` — directly awards item to child(ren)

## Architecture
- **Entry point**: `app.py` — single HTTP handler routing all GET/POST requests
- **Rendering**: each feature area has a `render_*.py` module returning HTML strings
- **Data**: `data/` directory — JSON files for settings, schedule, progress, meals, calendar cache
- **Port**: 5000 (`PORT=5000 python app.py`)
- **Timezone**: Eastern (`America/New_York`), helpers in `render_schedule_support.py`
- **Auth**: `auth.py` — session-based, PIN login, per-user access tables, viewer context
- **Live task snapshot**: `daily_schedule_engine.boys_task_snapshot(iso)` and `boys_task_snapshot_text(iso)` return real-time task state (done/pending) for all four boys; injected into Lucy's system prompt on every message; also available at `GET /api/boys-tasks?date=YYYY-MM-DD`

## Authentication System
- **`auth.py`**: Session store (in-memory), PIN management (`data/auth/pins.json`), access control tables
- **`render_login.py`**: Login page — avatar grid (all 6 members) + PIN pad modal
- **Login rules**: Lauren/John/JP/Joseph → 4-digit PIN (default `0000`); Michael/James → tap avatar (no PIN)
- **Sessions**: Browser-close sessions (no max-age cookie). `set_viewer()`/`get_viewer()` for single-threaded context
- **Child access** — JP & Joseph: home `/`, `/today`, `/week`, `/schedule/{own}`, `/meals`, `/recipes`, `/chores`, `/prayer` (read-only); can POST to `/toggle-task` and `/message-mom`
- **Michael**: Same but no `/recipes`; own schedule page only
- **Admins** (Lauren/John): Full access to everything
- **Message Mom**: Children send messages via modal (any page); Lauren sees inbox on home dashboard with unread count badge in nav
- **PIN management**: Settings page → "Login PINs" section (admin only); `/save-pins` POST route

## Key Files
| File | Purpose |
|------|---------|
| `app.py` | Route handler, all GET/POST paths + auth middleware |
| `auth.py` | Session management, PIN verification, access control, message store |
| `render_login.py` | Login page with avatar grid and PIN pad |
| `render_misc.py` | Dashboard (with mom's message inbox), `/now` page, school, tasks, notes |
| `render_schedule.py` | `/today` (child dash cards) and child schedule full page; Day List renderer |
| `render_lucy.py` | Lucy AI chat — Catholic companion/integrator; rule parsing, memory book |
| `render_lorenzo.py` | Lorenzo AI chat — personal chef, meal planning, streaming |
| `render_gregory.py` | Father Gregory AI chat — homeschool headmaster, academic planning |
| `render_coach.py` | Coach AI chat — family fitness, movement plans |
| `render_monica.py` | Dr. Monica AI chat — child development, pediatric health |
| `render_plan_importer.py` | Plan Import Tool — paste external AI plan, parse to events+tasks, approve+apply |
| `render_dev.py` | Felix (Dev companion) — admin-only AI programmer; reads source files, proposes [FIX:] blocks, applies patches, restarts server |
| `render_settings.py` | All settings including PIN management section |
| `render_schedule_support.py` | `get_current_slot()`, `get_eastern_now()` helpers |
| `data_helpers.py` | Load/save helpers for all JSON data files |
| `ui_helpers.py` | `html_page()`, `page_header()`, nav bar — child-aware (simplified nav for boys) |
| `config.py` | `child_color(child, variant)` — per-child color lookup |
| `daily_schedule_engine.py` | `CHILDREN` list, `build_schedule_payload()` |

## Key Features
- **`/today`**: Compact child dash cards (`render_child_dash_card`) — carryover always visible, first unchecked task auto-advances on check; progress bar; "Full list →" link; "Now: X" strip with link to `/now`
- **`/now`**: Family activity view — each member's current slot, next slot, first unchecked task, progress bar; links to each member's detail page
- **`/schedule/{child}`**: Full child schedule with all tasks
- **`/settings`**: Accordion sections (App, AI/Planning, Cycle, Household, Integrations)
  - Quick-jump pill nav (⚙ App | 🤖 AI | 🌙 Cycle | 🏠 Household | 📅 Calendars)
  - Up/down arrows for section reordering (localStorage-persisted)
  - "What Lucy Knows" summary card at top of AI section (green chips per field)
- **Lucy AI**: `/lucy` — Claude Haiku chat with **persistent conversation history** saved to `data/lucy_history.json` (up to 60 messages / 30 turns). History pre-rendered on page load; "New conversation" button clears via `/lucy-clear-history`. `[RULE:add]...[/RULE]` tags trigger Save button; rules stored in `family_constraints.lucy_rules`
- **Lucy history**: `load_lucy_history()` / `append_lucy_messages()` / `clear_lucy_history()` in `data_helpers.py`. Server history (last 30 msgs) sent to Claude — client no longer needs to send history
- **Lucy web fetch**: `web_fetch.py` — when Mom includes a URL in her message, the server fetches the page, strips it to plain text (up to 5 000 chars), and injects it into Lucy's system prompt context before calling Claude. No extra UI needed — just paste the link
- **Calendar**: 150 events from 6 calendars (`data/subscribed_calendar_cache.json`), 15-day lookahead

## Day List (Core Feature)
The Day List is the primary per-person view — a complete chronological schedule for each person built directly from the Rule of Life templates in `data/day_templates/`.

- **Engine**: `build_day_list(child, weekday, iso)` in `daily_schedule_engine.py` — reads the Rule of Life grid, merges same-label slots, classifies each by kind (prayer/meal/school/chore/exercise/routine/free/task), expands variable slots with real data (school assignments from PDF engine, chores from `data/chores.json`, manual tasks + carryover)
- **Stats**: `day_list_stats(day_list)` → `{total, done, pct}`
- **Day List renderer**: `_render_day_list_html()` in `render_schedule.py` — generates the interactive chronological HTML with color-coded kind indicators and expandable sub-items
- **Print**: `render_print_child_day_list(child, date)` → clean print-ready version; route: `GET /print/day/{child}?date=YYYY-MM-DD`
- **Kind colors**: prayer=#c8a42a, mass=#4a1a6e, meal=#8b3a5c, exercise=#1a6e3e, school=#1e3566, chore=#8b3a1a, task=#5b3a8a
- **Templates**: `data/day_templates/{Weekday}.json` — grid per person; falls back to `Friday.json`

## AI / API
- Claude model: `claude-haiku-4-5-20251001`
- API key stored: `data/app_settings.json` → `family_constraints.anthropic_api_key`
- Lucy context builder: `build_lucy_context()` in `render_lucy.py`

## Data Files
- `data/app_settings.json` — all settings including `family_constraints` dict
- `data/progress.json` — task completion state (task_id → bool)
- `data/family_schedule.json` — weekly schedule grid (days × time slots)
- `data/subscribed_calendar_cache.json` — 150 merged calendar events

## Navigation
- Mobile nav: `position:fixed; bottom:0; height:64px; z-index:2000` (ui_helpers.py)
- iOS input bar fix: `position:fixed; bottom:64px` for chat input

## Active Integrations
- **Google Drive**: Connected via Replit connector (`connection:conn_google-drive_01KNHERVT8AX027AZFJWRZ4H93`). Uses `@replit/connectors-sdk` (Node.js) via `gdrive_helper.js` + Python wrapper `gdrive.py`. School page has a Drive file browser at `/gdrive-files` (GET, admin only). Files are browsable and PDFs/Google Docs import directly. To refresh auth if token expires: call `proposeIntegration("connection:conn_google-drive_01KNHERVT8AX027AZFJWRZ4H93")` then restart.

## Pending Integrations
- **Notion** (`connector:ccfg_notion_01K49R392Z3CSNMXCPWSV67AF4`): User expressed interest in connecting Notion to improve relational data management (linking recipes to meal plans, managing roadmap/recipe book with better UI). OAuth was dismissed — when Lauren is ready to proceed, call `proposeIntegration("connector:ccfg_notion_01K49R392Z3CSNMXCPWSV67AF4")` to restart the OAuth flow, then `addIntegration` once it becomes a connection. Planned use cases: recipe ↔ meal plan linking, roadmap board, family history/memory book archival.

## Standing Rules (Lauren's Preferences)
These apply automatically to every new feature built — no need to ask each time.

### Auto-Save Everything
Whenever a new feature includes any form, text input, textarea, or multi-step workflow, it MUST include draft persistence. Lauren is a mom with young children and gets interrupted constantly — work in progress must never be silently lost.

**Implementation pattern:**
- Save to `localStorage` on every `oninput` or `onchange` event
- Use a descriptive, versioned key (e.g. `featureName_draft_v1`)
- Auto-restore on page load — pre-fill fields and re-open the form/panel if a draft exists
- Show a subtle green "Your draft was restored" notice when a draft is loaded
- Clear the draft **only** on explicit success: successful server save, submit, or deliberate "Start Over" / "Cancel" click
- Expire drafts older than 24 hours
- Prefer server-side auto-save (fetch POST on change) over localStorage when a server endpoint already exists for that data; only use localStorage when there is no immediate server save
- For multi-step AI workflows (like Plan Importer), persist the full result JSON + original input so the user can return to the results phase after any interruption
