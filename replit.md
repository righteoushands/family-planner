# Sancta Familia
A Catholic family dashboard for managing schedules, tasks, meals, and homeschooling, integrated with AI companions.

## Run & Operate
- **Run:** `PORT=5000 python app.py`
- **Required Env Vars:** `ANTHROPIC_API_KEY` (for AI companions)
- **Timezone:** `America/New_York` (Eastern Time)

## Stack
- **Runtime:** Python 3.11 (HTTP server, no framework)
- **Frontend:** HTML, CSS, JavaScript (no specific framework)
- **Data Storage:** JSON files
- **AI:** Anthropic Claude (Haiku model `claude-haiku-4-5-20251001`)

## Where things live
- `app.py`: Main entry point, HTTP handler, and router.
- `auth.py`: Authentication, session management, and access control.
- `data/`: All application data (JSON files).
  - `data/day_templates/{Weekday}.json`: Source of truth for daily schedules (Family Rule of Life).
  - `data/app_settings.json`: Global application settings and AI API keys.
  - `data/lucy_history.json`: Lucy AI chat history.
  - `data/family_quest/`: Contains all Family Quest RPG application logic and data.
  - `data/family_quest/quests.json`: Family Quest quest definitions.
  - `data/chores.json`: Chore definitions.
- `render_*.py`: Modules responsible for rendering specific HTML views.
- `daily_schedule_engine.py`: Logic for building daily schedules and task management.
- `family_quest/fq_bridge.py`: Bridge between main app and Family Quest.
- `family_quest/fq_api.py`: Family Quest's adapter for main app functionality.
- `static/`: Static assets (JS, CSS, images).
  - `static/js/plan_importer_{core,consult}.js`: JavaScript for the Plan Importer.

## Architecture decisions
- **No Web Framework:** The core application is built as a pure Python HTTP server for maximum control and minimal overhead.
- **JSON for Data Storage:** All persistent application data is stored in simple JSON files, facilitating direct manipulation and version control.
- **AI Ecosystem:** Five specialized AI companions (Lucy, Lorenzo, Father Gregory, Coach, Dr. Monica) provide targeted assistance, integrated via a shared AI backend.
- **Family Quest Isolation:** The Family Quest RPG (`family_quest/` directory) is designed as a highly decoupled sub-application with strict import rules, bridging only through `fq_bridge.py` and `fq_api.py`.
- **FROL as Single Source of Truth:** `data/day_templates/{Weekday}.json` is the sole authoritative source for all scheduling data, simplifying schedule management and consistency.

## Product
- **Personalized Dashboards:** `today` view provides compact, child-specific task cards with progress tracking.
- **AI Companions:**
    - **Lucy:** Catholic friend/integrator AI with persistent conversation history and web fetching.
    - **Lorenzo:** Personal chef AI for meal planning.
    - **Father Gregory:** Homeschool academic headmaster AI.
    - **Coach:** Family fitness AI.
    - **Dr. Monica:** Child development and pediatric health AI.
- **Family Quest RPG:** Gamified task and reward system with dual currency, energy, heroes, bosses, fortress building, and resource mining.
- **Flexible Scheduling:** Day List view built from Rule of Life templates, supporting task classification, carryover, and detailed chronological display.
- **Plan Importer:** Tool to parse external AI plans into actionable events and tasks.
- **Assignment Analyzer:** AI-powered tool to analyze assignment uploads (images, PDFs, text) into structured records for curriculum planning.
- **Parental Controls:** PIN-based authentication, per-user access control, and admin-only settings.
- **Google Drive Integration:** Browse and import files from Google Drive.

## User preferences
- **Auto-Save Everything:** Any form, text input, textarea, or multi-step workflow must persist drafts to `localStorage` (or server-side if an endpoint exists) on `oninput`/`onchange`, auto-restore on page load, and only clear on explicit success or after 24 hours.
- **Companion Undo:** All AI companions must support natural-language "undo" for their most recent data-altering actions.

## Gotchas
- **Routing Structure:** All GET/POST routing must use `elif` chains in `do_GET`/`do_POST` respectively; never use `if` chains or add bare `if request.method == "POST"`. Do not refactor routing structure without explicit instruction.
- **File Responsibility:** `data_helpers.py` is the only file that should read/write JSON. `config.py` owns all file paths. Do not hardcode paths.
- **Family Quest Isolation:** The `family_quest/` directory is isolated; most modules within it (except `fq_api.py` and `fq_bridge.py`) must not import from the parent directory.
- **Python 3.11 Rules:** Strictly no backslashes in f-strings, all imports at the top of files, and no walrus operator (`:=`) in f-strings.

## Pointers
- **Google Drive Connector:** Replit connector documentation for `connection:conn_google-drive_01KNHERVT8AX027AZFJWRZ4H93`.
- **Anthropic Claude API:** [https://docs.anthropic.com/](https://docs.anthropic.com/)
- **Replit Connectors SDK:** [https://www.npmjs.com/package/@replit/connectors-sdk](https://www.npmjs.com/package/@replit/connectors-sdk)
- **Family Quest Data Files:** Refer to `family_quest/data/*.json` for current game data schemas.