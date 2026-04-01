# Sancta Familia — Family Management & Homeschooling Dashboard

## Overview
A Python HTTP server (no framework) running on port 5000. A Catholic family dashboard for the McAdams family (JP, Joseph, Michael, James/toddler, Mom). Features Mass readings, weather, meal plans, calendar, and "Lucy" — a Claude-powered AI companion.

## Architecture
- **Entry point**: `app.py` — single HTTP handler routing all GET/POST requests
- **Rendering**: each feature area has a `render_*.py` module returning HTML strings
- **Data**: `data/` directory — JSON files for settings, schedule, progress, meals, calendar cache
- **Port**: 5000 (`PORT=5000 python app.py`)
- **Timezone**: Eastern (`America/New_York`), helpers in `render_schedule_support.py`

## Key Files
| File | Purpose |
|------|---------|
| `app.py` | Route handler, all GET/POST paths |
| `render_misc.py` | Dashboard, `/now` page, Mom's plan page, school, tasks, notes |
| `render_schedule.py` | `/today` (child dash cards) and child schedule full page |
| `render_lucy.py` | Lucy AI chat, rule parsing, memory book integration |
| `render_settings.py` | All settings — general, AI/constraints, cycle, household, integrations |
| `render_schedule_support.py` | `get_current_slot()`, `get_eastern_now()` helpers |
| `data_helpers.py` | Load/save helpers for all JSON data files |
| `ui_helpers.py` | `html_page()`, `page_header()`, nav bar (fixed bottom, 64px) |
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
- **Calendar**: 150 events from 6 calendars (`data/subscribed_calendar_cache.json`), 15-day lookahead

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
