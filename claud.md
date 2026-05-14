# CLAUDE.md — Sancta Familia

## What this app is
A Catholic homeschool family management web app built in Python on Replit.
Single-file HTTP server pattern (app.py + render_*.py modules).
No framework. Raw `http.server` with a custom `do_GET` / `do_POST` handler.

## Stack
- Python 3.11
- No Flask, no Django, no FastAPI
- Data stored as JSON files in data/
- No database
- Frontend: plain HTML/CSS/JS rendered as strings in Python render functions
- Anthropic API called directly via urllib.request (no SDK)

## People
Lauren (Mom), John (Dad), JP (14, 9th grade), Joseph (12, 7th grade), 
Michael (5, kindergarten), James (13 months, toddler — cannot be assigned tasks)
- Always title-case: Mom/Lauren, JP, Joseph, Michael, James
- Mom and Lauren are the same person
- James is excluded from school renderers and gradebook

## Python 3.11 hard rules — never violate these
1. No backslashes inside f-strings
2. No nested quotes inside f-strings — use a variable outside the f-string instead
3. All POST routing uses elif chains — never if/elif with a missing first if,
   never nested if blocks for routing
4. Never put import statements inside if blocks or functions
5. All file writes use safe_save_json (tmp file + os.replace) — never open(f, 'w') directly
6. No walrus operator (:=)
7. Never use '\n' inside a JS string within a Python string literal — use '\\n' so the browser receives the escape sequence, not a raw newline

## Data file patterns
- Most data lives in data/*.json as flat dicts or lists
- Person keys are title-case in progress.json, chores.json, events.json
- Person keys are lowercase in auth/pins.json and profiles/ (jp.json not JP.json)
- Progress keys are compound strings: "YYYY-MM-DD::Person::task text"
- Date keys: YYYY-MM-DD (most), YYYY-Www (meal_plan), YYYY-MM (cycle)

## Route patterns
- GET routes call render_*.py functions that return HTML strings
- POST routes live in app.py do_POST, chained as elif path == "/route-name":
- JSON POST bodies must be registered in _JSON_PATHS set or the form-parser
  will consume the payload silently
- New routes that receive JSON bodies must be added to _JSON_PATHS

## Anchor-tag navigation
Plain `<a href="...">` links cannot POST and cannot mutate server state on
their own. Any state the destination page needs must either travel in the
URL query string OR already be persisted before the user clicks. The
destination handler is responsible for accepting those query params AND
persisting them on arrival if they are required for subsequent renders.
Counter-pattern that bit us: the FROL wizard landing buttons are anchors
to /frol-wizard?step=1&mode=structured. Without persisting `mode` on the
first GET, the page's "is the wizard configured?" gate kept re-rendering
the landing screen and the wizard appeared unreachable. If a button must
trigger persistent state without the destination handler doing the write,
use a `<form method="POST">` with a submit button styled as a link instead.

## AI calls
- Model: claude-sonnet-4-20250514
- Called via urllib.request directly, not the Anthropic SDK
- API key read from app_settings.json
- All AI responses go through _repair_and_parse_json() before use

## Change discipline
- All changes are additive unless explicitly told otherwise
- Never delete or modify existing behavior unless the task specifically requires it
- If a task requires editing a file not in the stated scope, stop and flag it
- Keep modules under 800 lines where possible
- render_plan_importer.py is 1,114 lines (JS lives in static/js/plan_importer_core.js and static/js/plan_importer_consult.js — edit those, not the Python file, for JS changes)

## Current major features
- /plan-import — paste text → AI extracts events, tasks, placements → approve → apply
- Placements route information to existing records (events, profiles, friends, pantry, etc.)
- Receipt + undo after apply (/plan-import-undo-placement)
- Six AI companions: Lucy, Lorenzo, Gregory, Monica, Coach, Izzy (dev)
- Liturgical calendar engine with auto-computed Easter and moveable feasts
- Daily schedule grids per person, per date
- Gradebook with assignment analyzer
- Meal planner with Lorenzo as meal companion
