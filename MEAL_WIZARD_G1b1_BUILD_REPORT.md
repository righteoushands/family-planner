# Meal Wizard — Phase G1b-1 BUILD REPORT (read-only Step 4 screen)

**Date:** June 28, 2026 · Single-purpose per Rule 17 · **NO JavaScript** · runs after G1a (complete)

> The Step 4 page as a **display-only** screen: the planning week as day cards (liturgical header + commitments) with each day's selected meal slots, showing any meals already confirmed in the wizard session. No entry, no confirm/change/remove, no recipe-attach, no Step 3→4 nav wiring — those are G1b-2. All validation below passes, including an **authenticated HTTP 200**. **G1b-2 was NOT started.**

---

## RULE 15 — CLAUD.MD READ-BACK

### Stack / People (context)
- Python 3.11, no framework, raw `http.server` `do_GET`/`do_POST`, JSON files in `data/`, no DB, frontend = HTML/CSS/JS rendered as Python strings, Anthropic via `urllib.request`.
- People: Lauren/Mom, John, JP (14), Joseph (12), Michael (5), James (13 mo — never a cook/assignee, excluded from school renderers). Title-case in display.

### Python 3.11 hard rules
1. No backslashes inside f-strings. *(Practical form, matching the codebase: no backslash inside an f-string EXPRESSION `{...}`. `\u` escapes in f-string literal TEXT are used throughout the existing Step 1/3 renderers and are safe; this file follows that same convention.)*
2. No nested quotes inside f-strings — pull the value into a variable outside the f-string.
3. GET routing uses `elif` chains in `do_GET`; POST routing also uses `elif` chains in `do_POST` (the one exception is the multipart recipe routes' shared-setup nested block — do not copy it). *(Corrected June 28; code wins.)*
4. No imports inside if-blocks or functions — all imports at module top. *(Known live deviation: some `do_POST` handlers use inline `import json as _json`; new code keeps imports at top — this file does.)*
5. All file writes go through `safe_save_json` (tmp + `os.replace`).
6. No walrus operator.
7. Never put a literal `'\n'` inside a JS string embedded in a Python string — use `'\\n'`.
8. multipart/form-data: sniff Content-Type, parse with `cgi.FieldStorage`.
9. `py_compile` passing ≠ runtime correct — run an in-process smoke test AND the nearest existing `verify_*` harness.
10. Test fixtures never touch live data — operate on a temp copy, snapshot + restore.
11. Escape HTML once (no double-escaping).
12. The JS-newline rule (7) applies to every file embedding JS in Python.

### Data / routes / nav / AI / change discipline (unchanged from prior read-backs)
- Data in `data/*.json`; session reads via `data_helpers`.
- GET → `render_*.py` returning HTML; routes chained as `elif path == "/route"`. JSON POST bodies must be registered in `_JSON_PATHS` (not relevant to G1b-1 — this is a GET screen).
- Plain `<a href>` cannot mutate state.
- AI model not uniform; Lorenzo uses `claude-haiku-4-5-20251001`; `_repair_and_parse_json` is plan-importer-only. *(Not exercised by G1b-1 — no AI here.)*
- All changes additive; modules kept under ~800 lines (Step 4 split into its own file).

### Additional rules 13–19
13. FROL nested-form addendum (`_body_has_form` / `action="/frol-wizard"`) — N/A (no forms here).
14. Pre-flight checklist (below).
15. This read-back.
16. Magnifica Humanitas — the app is a tool, not an authority; present the plan as **Lauren's**, no prescriptive/streak/shame language.
17. One fix per instruction — display-only; the write side is untouched.
18. Aug-15 build plan is the priority filter — the Meal Wizard is on the must-build path.
19. Build for a future second family — read family/window data via `data_helpers`; no hardcoded specifics in this screen.

### Rules that APPLY to G1b-1
- **Rule 1 & 2** — f-string discipline in the new render file (no backslash in any expression; nested quotes avoided via style constants).
- **Rule 3** — the new GET route is a plain `elif` branch in `do_GET`.
- **Rule 11** — every dynamic value (meal name, event text, weekday/date, season, feast name) escaped exactly once.
- **Known Issue #2** — every liturgical color (`season_color`, `feast_color`) passes through a color allowlist before being interpolated into a `style=""` attribute (stored-XSS guard).
- **Route patterns** — route mirrors `/meal-wizard-step3` exactly for auth + send shape.
- **Rule 14** — pre-flight done (below).
- **Rule 16** — neutral, non-prescriptive copy; the plan is presented as Lauren's.
- **Rule 17** — display only; zero write side.
- **Rule 19** — reads via `data_helpers`; no hardcoded family specifics.
- **Rules 7 & 12 DO NOT APPLY** — G1b-1 adds **no JavaScript** (verified below). If JS were needed it would belong in G1b-2.

---

## PRE-FLIGHT (Rule 14)
1. **Files touched:** NEW `render_meal_wizard_step4.py`; `render_meal_wizard.py` (one re-export line, mirroring the Step 3 re-export); `app.py` (one new `elif` GET route **and** the function added to the existing `from render_meal_wizard import ...` line). Three files, tightly related.
2. **JS in Python f-strings?** NO — and it stays no for G1b-1.
3. **Form handling / nested `/frol-wizard` forms?** NO.
4. **Root cause confirmed/assumed?** N/A — additive new screen.
5. **Multiple files?** Three, directly related (render file + re-export + route + its import).
6. **Data shape change?** NO — only READS existing session keys (`planning_window`, `confirmed_what_to_plan`, `confirmed_meals`, `confirmed_inventory`). Writes nothing.

---

## DESIGN DECISION — replicated, did NOT reuse `_wg_day_card`

The instruction allowed either reusing `render_meal_wizard._wg_day_card` or replicating the minimal header+events markup, and asked which I did.

**I replicated** the minimal liturgical header + event-line markup, and replicated the color sanitizer locally (`_s4_safe_color`, same hex regex + named-color allowlist as `_wg_safe_color`).

**Why:** the re-export must sit at the **top** of `render_meal_wizard.py` next to the Step 3 re-export (per the instruction). `_wg_day_card` and `_wg_safe_color` are defined far below that line. If `render_meal_wizard_step4` imported them back from `render_meal_wizard`, the import chain would be:

```
import render_meal_wizard
  -> (top) from render_meal_wizard_step4 import render_meal_wizard_step4
       -> from render_meal_wizard import _wg_day_card   # NOT YET DEFINED
       -> ImportError: cannot import name '_wg_day_card'
```

Replicating keeps the dependency strictly one-way (`render_meal_wizard` → `render_meal_wizard_step4`), avoids the circular import, and respects Rule 4 (no function-local imports). The replicated sanitizer is the security-critical piece and is a byte-for-byte behavioral copy of `_wg_safe_color`. The architect review confirmed this choice is "justified and architecturally sound."

Additionally, replication lets each day card hold the liturgical header, the commitments, **and** the meal-slots section in ONE cohesive card, which `_wg_day_card` (header+chips+events only, wrapped in its own closed div) could not have produced without a second sibling card.

---

## WHAT WAS BUILT

### STEP 1 — NEW `render_meal_wizard_step4.py`
`def render_meal_wizard_step4(user: str, start_iso: str = None) -> str` (the `start_iso` arg mirrors the Step 1 signature; the window always comes from the saved session, the source of truth for Step 4).

Reads (all via existing helpers — no direct file access):
- `session = load_meal_wizard_session()`
- `window = session.get("planning_window") or {}`
- `to_plan = session.get("confirmed_what_to_plan") or []`
- `confirmed = session.get("confirmed_meals") or {}`
- `confirmed_inventory` — read but intentionally **unused** (green/red parsing is G1b-2).

**Gate state:** if the window has no valid `start_iso`/`end_iso` (missing or unparseable), render a calm message — *"Finish Step 3 first to choose what to plan and the week."* — with a link to `/meal-wizard-step3`, and return. Never crashes on an empty session.

**Normal render:** iterate each date from `start_iso` through `end_iso` inclusive (span capped at 60 days; start/end swapped if reversed — defensive). One merged events fetch grouped by ISO date, degrading quietly to "No commitments". For each date, a **day card**:
- **(a) Liturgical header + events** — replicated from `get_day_info`: season dot (color via `_s4_safe_color`), weekday — date label, season label, feast/abstinence/fast marker chips (feast color via `_s4_safe_color`), then the day's event lines (or "No commitments").
- **(b) Meal slots** — for each slot in `to_plan`, in the stable order `breakfast, lunch, dinner, johns_lunch, snacks, dessert, feast_meal, batch_cook`, look up `confirmed["YYYY-MM-DD::slot"]`:
  - **Present:** meal name (escaped once); recipe state — `recipe_id` non-empty → **"Recipe attached"** (plain label; the `/recipes` link is G1b-2); else `recipe_on_request` truthy → **"No recipe needed"**; else a quiet **"Recipe: not set yet"** (the half-confirmed state the G1b-2 recipe default will prevent — surfaced plainly, not hidden). Plus a muted source tag (`manual`/`lorenzo`/`prefill`) and, when `skip_shopping`, a muted **"off shopping list"** note.
  - **Absent:** the slot label and a muted **"Not planned yet"** placeholder. No input, no button.
- James is never rendered as a cook/assignee (nothing here references him).

Page chrome: title **"Plan This Week's Meals"**, subtitle **"Step 4 of 6 — Build the menu"**, max-width 680px container (consistent with Step 1/2/3), a plain **← Back** link to `/meal-wizard-step3`. No forward "continue" action (locking is a later phase). Wrapped with `html_page(...)`.

Security/correctness specifics: `_s4_safe_color(value, fallback)` returns the value only if it matches `^#(?:[0-9a-fA-F]{3}|{6}|{8})$` or is in the named-color allowlist; otherwise the safe fallback — so user-editable liturgical colors can't break out of the `style=""` attribute. All text goes through `escape()` exactly once.

### STEP 2 — `render_meal_wizard.py` re-export (next to Step 3)
```python
from render_meal_wizard_step3 import render_meal_wizard_step3  # noqa: F401
from render_meal_wizard_step4 import render_meal_wizard_step4  # noqa: F401
```

### STEP 3 — `app.py` `do_GET` new `elif` route (mirrors `/meal-wizard-step3`)
```python
        elif path == "/meal-wizard-step4":
            html = render_meal_wizard_step4(viewer)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma","no-cache")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
```
The central `viewer = self._require_auth(path)` gate (already at the top of `do_GET`) protects this route exactly as it does its neighbors — unauthenticated requests get a 302 to `/login` before the route body runs.

**Import wiring (caught in code review):** `render_meal_wizard_step4` was also added to the existing `from render_meal_wizard import ...` line in `app.py`. The re-export alone is not enough — `app.py` must import the name it calls, or an authenticated request would raise `NameError` (the unauth 302 hides this because the route body never executes). Now imported:
```python
from render_meal_wizard import render_pantry_staples_page, render_meal_wizard_week_glance, render_meal_wizard_step2, render_meal_wizard_step3, render_meal_wizard_step4
```

---

## EXPLICITLY OUT OF SCOPE FOR G1b-1 (not built)
- No JavaScript of any kind.
- No manual meal entry inputs, no confirm/change/remove buttons.
- No `fetch` to `/meal-wizard-step4-confirm` or `/meal-wizard-step4-remove`.
- No green/red parsing of `confirmed_inventory`.
- No recipe-attach link/flow, no cook assignment, no cook-conflict hint.
- No change to the G1a confirm/remove handlers (the server-side recipe-default guard is G1b-2).
- No write to the meal store, no plan lock, no Step 3→4 nav wiring.

> **Recorded for G1b-2 (approved by Lauren, intentionally NOT built here):** confirm-payload recipe default (`recipe_on_request = true` when no `recipe_id`); a one-line server guard in `/meal-wizard-step4-confirm` to auto-set `recipe_on_request` true when `recipe_id` is empty and it wasn't sent true; ingredient green/red check; manual entry; recipe attach.

---

## VALIDATION RESULTS (Rule 9 / 10)

**1. `py_compile render_meal_wizard_step4.py render_meal_wizard.py app.py`** → **COMPILE OK.**

**2. In-process smoke test on a TEMP session** (`data/verify_meal_wizard_step4.py`; snapshots + restores the live session per Rule 10):
```
PASS empty session renders gate state without raising
PASS gate state adds no <script> beyond page chrome (display-only)
PASS seeded render adds no <script> beyond page chrome (zero JavaScript)
PASS both day labels (Monday, Tuesday) present
PASS selected slot labels (Breakfast, Dinner) present
PASS all three confirmed meal names present
PASS recipe_id meal shows 'Recipe attached'
PASS recipe_on_request meal shows 'No recipe needed'
PASS half-confirmed meal shows 'Recipe: not set yet'
PASS source tags (manual/lorenzo/prefill) present
PASS skip_shopping meal shows 'off shopping list'
PASS back link to Step 3 present

PASS all G1b-1 read-only screen checks passed
```
*(The "no JavaScript" check compares the `<script` count of the rendered page against an empty-body `html_page("x","")` baseline. The only scripts present are the global site chrome injected by `html_page`; the Step 4 content adds zero — confirming NO JavaScript was added.)*

**3. Step 3 regression harness** (`data/verify_meal_wizard_step3.py`) — confirms no regression to session reads:
```
PASS all Step 3 session-state checks passed
```

**4. App boot + route checks (live server, restarted):**
- Unauthenticated `GET /meal-wizard-step4` → **302** → `/login?next=/meal-wizard-step4` (auth gate fires first).
- Authenticated `GET /meal-wizard-step4` (valid Lauren session, empty window) → **HTTP 200, 47,736 bytes**, contains the gate message, **no traceback**.
- App boots cleanly (only the pre-existing `cgi` deprecation warning).

**5. Report items:**
- claud.md rules that applied: 1, 2, 3, 11, 14, 16, 17, 19, Known Issue #2, Route patterns. Rules 7 & 12 did NOT apply (no JS).
- Reused vs replicated: **replicated** the header+events markup and the color sanitizer (circular-import reason above).
- **NO JavaScript was added** to Step 4 content (verified against the chrome baseline).

---

## CODE REVIEW (architect)
A review was run on the diff. It flagged **one blocking bug** — the route called `render_meal_wizard_step4` but `app.py` did not import it (the re-export lived only in `render_meal_wizard.py`), which would `NameError` on an *authenticated* request (the unauth 302 masked it). **Fixed** by adding the name to `app.py`'s `from render_meal_wizard import ...` line, then re-verified with the authenticated HTTP 200 above. The review confirmed the replication design decision is sound, the screen is read-only with no out-of-scope behavior, colors are sanitized before style attributes, and escaping is correct.

---

## SUMMARY
Phase **G1b-1 is complete**: a read-only Step 4 screen that shows the planning week as day cards (liturgical header + commitments) with each day's selected meal slots and any confirmed meals, gracefully gating an empty session. Zero JavaScript. All validation passes, including an authenticated HTTP 200. **G1b-2 (the write side: entry, confirm/remove wiring, recipe default + server guard, ingredient checks, nav wiring) was not started — stopping here as instructed.**
