# Meal Wizard — Phase G1a BUILD REPORT (data foundation only)

**Date:** June 28, 2026 · Single-purpose per Rule 17 · Lorenzo-independent · **server-only**

> Built against the corrected `claud.md` (model line, Rule 3, `_repair_and_parse_json` note fixed June 28). All four validation steps below pass. **G1b was NOT started.**

---

## RULE 15 — CLAUD.MD READ-BACK

### Stack / People (context)
- Python 3.11, no framework, raw `http.server` `do_GET`/`do_POST`, data as JSON files in `data/`, no DB, frontend = HTML/CSS/JS rendered as Python strings, Anthropic called directly via `urllib.request` (no SDK).
- People: Lauren/Mom (same person), John, JP (14), Joseph (12), Michael (5), James (13 mo — cannot be assigned tasks, excluded from school renderers/gradebook). Always title-case.

### Python 3.11 hard rules — never violate
1. No backslashes inside f-strings.
2. No nested quotes inside f-strings — use a variable outside the f-string instead.
3. All GET routing uses elif chains in `do_GET`. **POST routing in `do_POST` ALSO uses elif chains** (`elif path == "/route-name": … return`) — verified June 28 2026 against the meal POST handlers + Route patterns. The ONE exception is the multipart recipe routes (`/recipe-save`, `/recipe-import`), which share an `elif path in (...)` outer block with nested `if path == ...` inner blocks ONLY to share upload-parsing setup. Do NOT copy that nested pattern for ordinary JSON/form routes. *(CORRECTED June 28: an earlier note wrongly said `do_POST` used standalone if-blocks; the live code uses elif chains. Code wins.)*
4. Never put import statements inside if blocks or functions. *(KNOWN DEVIATION, not a license: several live `do_POST` handlers use inline `import json as _json`. New code should keep imports at module top.)*
5. All file writes use `safe_save_json` (tmp file + `os.replace`) — never `open(f, 'w')` directly.
6. No walrus operator (`:=`).
7. Never use `'\n'` inside a JS string within a Python string literal — use `'\\n'`.
8. multipart/form-data: sniff Content-Type and parse with `cgi.FieldStorage` for multipart; if a POST handler gets empty data, check Content-Type first.
9. `py_compile` passes ≠ runtime correct. Always run an in-process smoke test after `py_compile`, AND run the relevant existing `verify_*` harness for the area touched. Don't skip the harness for changes to shared data files, save paths, or any function called from more than one place.
10. Test fixtures must never write to live data: harnesses operate on a temp copy; never call write helpers on live data during testing; always restore from backup.
11. Don't double-escape HTML entities (`escape()` once).
12. The JS-newline rule (7) applies to ALL files with JS embedded in Python (render_schedule, render_timeblock, render_lucy, render_lorenzo, etc.).

### Data file patterns
- Most data in `data/*.json`; person keys title-case in progress/chores/events; lowercase in auth/pins + profiles; progress keys `"YYYY-MM-DD::Person::task text"`; date keys `YYYY-MM-DD` (most), `YYYY-Www` (meal_plan), `YYYY-MM` (cycle).

### Route patterns
- GET → `render_*.py` functions returning HTML. POST → `do_POST`, chained as `elif path == "/route-name":`. **JSON POST bodies must be registered in `_JSON_PATHS`** (a LOCAL set inside `do_POST`, ~app.py:3536) or the form-parser silently consumes the payload. New JSON routes must be added there.

### Anchor-tag navigation
- Plain `<a href>` can't POST/mutate state; needed state travels in the query string or is persisted before click; use `<form method="POST">` if a button must trigger persistent state.

### AI calls
- Model NOT uniform. Lorenzo's live call uses `claude-haiku-4-5-20251001` (verified June 28). The previously-documented `claude-sonnet-4-20250514` is stale/unverified for other calls — confirm per call. Called via `urllib.request`, key from `app_settings.json`. **`_repair_and_parse_json()` is NOT universal** — it is a nested local function inside the plan-import handler (~app.py:8412), used only by the plan importer; Lorenzo does not use it. *(CORRECTED June 28: prior "all AI responses go through `_repair_and_parse_json()`" was false.)*

### Change discipline
- All changes additive unless told otherwise; never delete/modify existing behavior unless required; if a task needs editing a file outside stated scope, stop and flag; keep modules under 800 lines where possible.

### Additional rules (13–19)
13. **FROL wizard nested-form addendum** — `_body_has_form` in `_section_chrome` suppresses Save-and-Continue when it sees `action="/frol-wizard"` in the body; forms posting to other routes are safe; confirm action attributes before adding a form to a section body.
14. **Pre-flight checklist** — before any spec: (1) how many files, list them; (2) JS-in-Python f-strings? flag the backslash-n rule; (3) form handling / nested `/frol-wizard` forms?; (4) root cause confirmed or assumed? (diagnose first if assumed); (5) multiple files? split into single-purpose instructions; (6) data shape change/migration? specify before/after explicitly.
15. **Claud.md read-back required** — read it at session start, paste every rule, identify which apply; if you can't paste accurately, stop.
16. **Magnifica Humanitas design principles** — the app is a tool not an authority (suggestions, never prescriptions); companions serve real relationships, never replace them; AI supports thinking, doesn't replace it; be transparent about what AI is (no theological authority; prayer texts from verified Catholic sources only); language of grace not performance (no gamification/streaks/shame; a hard day is never failure); subsidiarity (Lauren is always the authority); formation in digital wisdom (the goal: JP can plan his day without the app).
17. **One fix per instruction** — never bundle unrelated fixes; complex multi-file builds split into sequential single-purpose phases with a compile check + report between each.
18. **August 15th build plan is the priority filter** — Jun 1–Aug 15 2026, check every build against the Aug-15 plan; if not on the must/should list, flag to Lauren; new ideas go post-September unless they enable one of the 14 goals; cut scope first, not quality.
19. **Build for a future second family** — write every feature as if a second family will use it; never hardcode McAdams specifics (keep family identity/config in `app_settings.json`); route all reads/writes through `data_helpers.py` (no direct file access in route handlers). *(KNOWN DEBT, June 28: `build_lorenzo_context` hardcodes the roster; new Step 4/Lorenzo work must not deepen this.)*

### Rules that APPLY to G1a
- **Rule 3** — the two new POST routes are added as plain `elif path == ...` branches in `do_POST` (not the nested recipe pattern).
- **Rule 5** — all writes go through `update_meal_wizard_session` → `safe_save_json` (no direct file writes).
- **Rule 6** — no walrus used.
- **Rule 9 / 10** — compiled, ran a dedicated in-process smoke test on a **temp copy** of the session, and re-ran the nearest existing harness (step3) for regression; live session snapshotted + restored.
- **Route patterns + `_JSON_PATHS`** — both new routes registered in `_JSON_PATHS`; raw body read via `Content-Length` + `self.rfile.read` + `json.loads`.
- **Rule 14** — pre-flight completed (below).
- **Rule 16** — the server only persists what Lauren sends and only removes on her explicit request; it never invents or auto-removes a meal.
- **Rule 17** — this is exactly one phase; G1b / Lorenzo not touched.
- **Rule 19** — no new hardcoded family specifics; all access flows through `data_helpers.py` (new helpers live there; littles' separate food is excluded from `used_proteins` by design, not by family-specific branching).

---

## PRE-FLIGHT (Rule 14)
1. **Files touched:** `data_helpers.py` (two additive helpers) and `app.py` (two `_JSON_PATHS` entries, two import names, two `do_POST` elif branches). Two files, tightly related — within Rule 17.
2. **JS in Python f-strings?** No — G1a is server-only.
3. **Form handling / nested `/frol-wizard` forms?** No.
4. **Root cause confirmed?** N/A — additive new structure, not a fix.
5. **Multiple files?** Two, directly related (a data contract + its routes).
6. **Data shape change?** Yes — additive. See before/after below; missing fields default, so no migration of existing prefill entries is needed.

---

## BEFORE / AFTER SESSION SHAPE

**Before** — `confirmed_meals` entries (as written by step3-save prefill) had:
```json
{ "name": "...", "locked": true, "source": "prefill",
  "skip_shopping": true, "recipe_on_request": true }
```
No top-level `used_proteins` key.

**After (G1a contract)** — a confirmed-meal entry is:
```json
{
  "name":              "<str, required, non-empty>",
  "source":            "manual | lorenzo | prefill",
  "locked":            true,
  "ingredients":       "<str, may be ''>",
  "recipe_id":         "<str or ''>",
  "recipe_on_request": false,
  "skip_shopping":     false,
  "protein":           "<str or '' — MAIN/FAMILY protein only>"
}
```
Plus ONE new top-level session key:
```json
"used_proteins": ["chicken", "beef"]
```
De-duplicated, lowercased, first-seen order; recomputed on every confirm/remove. **Existing prefill entries remain valid** — missing fields (`ingredients`, `recipe_id`, `protein`) are treated as defaults (`""`); missing booleans read as falsy.

**Littles' food:** a separate protein cooked only for James/Michael does NOT go in `protein` and is NOT added to `used_proteins` (it would nag the repeat flag). For G1a it lives in the free-text `ingredients` field (e.g. `"+ chicken nuggets for James"`). `recompute_used_proteins` reads ONLY `protein`, so this exclusion is automatic.

---

## WHAT WAS BUILT

### STEP 1 — `data_helpers.py` (additive, after `update_meal_wizard_session`)
```python
def get_confirmed_meals() -> dict:
    """Return the wizard session's confirmed_meals dict (keyed 'YYYY-MM-DD::slot').
    Returns {} when there is no session or no confirmed meals yet. Read helper
    so route handlers and the (later) Step 4 renderer stay thin."""
    return load_meal_wizard_session().get("confirmed_meals") or {}


def recompute_used_proteins(confirmed_meals: dict) -> list:
    """Recompute the de-duplicated, lowercased used_proteins list from
    confirmed_meals so it can never drift from the meals themselves.

    Reads ONLY each entry's 'protein' field. Separate food cooked just for the
    littles (James/Michael) lives in the free-text 'ingredients' field, never in
    'protein', so it is excluded here automatically and won't trip the repeat
    flag. Strips and lowercases each protein and preserves first-seen order."""
    used = []
    seen = set()
    if isinstance(confirmed_meals, dict):
        for _entry in confirmed_meals.values():
            if not isinstance(_entry, dict):
                continue
            _p = (_entry.get("protein") or "").strip().lower()
            if _p and _p not in seen:
                seen.add(_p)
                used.append(_p)
    return used
```
Both names were also added to the explicit `from data_helpers import (...)` block in `app.py` (alongside `update_meal_wizard_session, load_meal_wizard_session`).

### STEP 2 — `app.py` `_JSON_PATHS` (~3536)
```python
_JSON_PATHS = {"/plan-import-apply", "/plan-import-undo-placement", "/curriculum-save", "/curriculum-minutes", "/poetry-passage-save", "/meal-wizard-step3-save", "/meal-wizard-step4-confirm", "/meal-wizard-step4-remove"}
```

### STEP 2 — `app.py` `do_POST` new elif branch `/meal-wizard-step4-confirm`
```python
            elif path == "/meal-wizard-step4-confirm":
                # JSON body (registered in _JSON_PATHS so the form-parser leaves
                # it alone); read and parse the raw body like step3-save.
                # Writes ONE confirmed meal into the wizard session and keeps
                # used_proteins in sync. Server only persists what Lauren sends;
                # it never invents a meal (Rule 16).
                _s4_cl  = int(self.headers.get("Content-Length","0") or 0)
                _s4_raw = self.rfile.read(_s4_cl).decode("utf-8","ignore") if _s4_cl else ""
                try:    _s4_payload = json.loads(_s4_raw)
                except Exception: _s4_payload = {}
                _S4_SLOTS    = {"breakfast","lunch","dinner","johns_lunch",
                                "snacks","dessert","feast_meal","batch_cook"}
                _S4_SOURCES  = {"manual","lorenzo","prefill"}
                def _s4_valid_iso(_v):
                    try:    date.fromisoformat(_v); return _v
                    except Exception: return ""
                _s4_date = _s4_valid_iso(str(_s4_payload.get("date","")))
                _s4_slot = str(_s4_payload.get("slot","")).strip().lower()
                _s4_name = clean_text(_s4_payload.get("name",""))
                # Reject anything that can't form a valid date::slot entry.
                if (not _s4_date) or (_s4_slot not in _S4_SLOTS) or (not _s4_name):
                    self.send_response(400)
                    self.send_header("Content-Type","application/json")
                    self.end_headers()
                    try: self.wfile.write(b'{"ok":false}')
                    except BrokenPipeError: pass
                    return
                _s4_source = _s4_payload.get("source","manual")
                if _s4_source not in _S4_SOURCES:
                    _s4_source = "manual"
                # Coerce booleans explicitly: a real JSON bool passes through, but
                # string forms ("false"/"0"/"no") must NOT all read as truthy the
                # way bare bool("false") would, or a meal could silently persist
                # the wrong shopping/recipe flag.
                def _s4_as_bool(_v):
                    if isinstance(_v, bool): return _v
                    if isinstance(_v, (int, float)): return _v != 0
                    if isinstance(_v, str): return _v.strip().lower() in ("true","1","yes","on")
                    return False
                _s4_entry = {
                    "name":              _s4_name,
                    "source":            _s4_source,
                    "locked":            True,
                    "ingredients":       clean_text(_s4_payload.get("ingredients","")),
                    "recipe_id":         clean_text(_s4_payload.get("recipe_id","")),
                    "recipe_on_request": _s4_as_bool(_s4_payload.get("recipe_on_request")),
                    "skip_shopping":     _s4_as_bool(_s4_payload.get("skip_shopping")),
                    "protein":           clean_text(_s4_payload.get("protein","")),
                }
                _s4_meals = load_meal_wizard_session().get("confirmed_meals") or {}
                _s4_meals[_s4_date + "::" + _s4_slot] = _s4_entry
                update_meal_wizard_session({
                    "confirmed_meals": _s4_meals,
                    "used_proteins":   recompute_used_proteins(_s4_meals),
                })
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return
```

### STEP 3 — `app.py` `do_POST` new elif branch `/meal-wizard-step4-remove`
```python
            elif path == "/meal-wizard-step4-remove":
                # Idempotent removal of ONE confirmed meal (the "Change this
                # meal" backing op). Only Lauren triggers this from the UI; the
                # server never removes a meal on its own (Rule 16). Responds
                # {"ok":true} even when the slot was already absent.
                _s4r_cl  = int(self.headers.get("Content-Length","0") or 0)
                _s4r_raw = self.rfile.read(_s4r_cl).decode("utf-8","ignore") if _s4r_cl else ""
                try:    _s4r_payload = json.loads(_s4r_raw)
                except Exception: _s4r_payload = {}
                _S4R_SLOTS = {"breakfast","lunch","dinner","johns_lunch",
                              "snacks","dessert","feast_meal","batch_cook"}
                def _s4r_valid_iso(_v):
                    try:    date.fromisoformat(_v); return _v
                    except Exception: return ""
                _s4r_date = _s4r_valid_iso(str(_s4r_payload.get("date","")))
                _s4r_slot = str(_s4r_payload.get("slot","")).strip().lower()
                if (not _s4r_date) or (_s4r_slot not in _S4R_SLOTS):
                    self.send_response(400)
                    self.send_header("Content-Type","application/json")
                    self.end_headers()
                    try: self.wfile.write(b'{"ok":false}')
                    except BrokenPipeError: pass
                    return
                _s4r_meals = load_meal_wizard_session().get("confirmed_meals") or {}
                _s4r_meals.pop(_s4r_date + "::" + _s4r_slot, None)
                update_meal_wizard_session({
                    "confirmed_meals": _s4r_meals,
                    "used_proteins":   recompute_used_proteins(_s4r_meals),
                })
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return
```

> **Validation note (server-side, allowlist style, mirroring step3-save):** date must pass `date.fromisoformat`; slot must be in the 8-slot allowlist; name `clean_text`, non-empty; `source` coerced to `manual` if not in the allowlist; `ingredients`/`recipe_id`/`protein` via `clean_text` (allow `""`); `recipe_on_request`/`skip_shopping` coerced with an explicit `_s4_as_bool` (real JSON bool passes through; string forms `"true"/"1"/"yes"/"on"` are truthy, `"false"/"0"/"no"` are falsy — so a stringified `"false"` is NOT silently stored as `True`). `recipe_id` is NOT verified against the recipe library here (deferred to G1b/lock via `get_recipe_by_id`). Confirm sets `locked=True` and recomputes `used_proteins`; remove pops the slot (idempotent) and recomputes.

---

## OUT OF SCOPE FOR G1a (not built)
- No Step 4 renderer / screen (G1b).
- No Lorenzo generation call (G1c, parked).
- No write to the meal store (`data/meal_plan/{Monday}.json`) and no plan lock — the `date::slot → (Monday week-key, Day name, slot)` mapping happens at the LOCK step later. G1a touches ONLY the wizard session.
- No new render file, no JS, no `_JSON_PATHS` entries other than the two above.

---

## VALIDATION RESULTS (Rule 9 / 10)

**1. `py_compile data_helpers.py app.py`** → **COMPILE OK.**

**2. In-process smoke test on a TEMP copy** (`data/verify_meal_wizard_g1a.py`; snapshots + restores the live session per Rule 10):
```
PASS recompute_used_proteins: deduped/lowercased/first-seen, littles excluded
PASS confirm: entry persisted, locked, correct source
PASS confirm: used_proteins reflects the protein
PASS remove: slot gone and used_proteins updated
PASS remove: idempotent on absent slot
PASS validation: bad slot and bad date both rejected (no write)

PASS all G1a data-foundation checks passed
```

**3. Nearest existing harness re-run for regression** (`data/verify_meal_wizard_step3.py`) — confirms G1a did not regress step3's `confirmed_meals` preservation:
```
PASS complexity persisted
PASS planning_window persisted
PASS prefill keys allowlist-filtered correctly
PASS prefilled meal has correct locked/off-shopping shape
PASS non-prefill (generated) meal preserved across save
PASS prefill entries refreshed (old prefill cleared, new applied)
PASS saved-confirmation view reflects persisted session
PASS Step 2 confirmed_inventory preserved (additive)

PASS all Step 3 session-state checks passed
```

**4. App boot check** — workflow restarted; `app.py` imports and serves cleanly (only the pre-existing `cgi` deprecation warning, unrelated to G1a):
```
Running on http://0.0.0.0:5000
GET / HTTP/1.1 302  →  GET /login?next=/ HTTP/1.1 200
```

---

## SUMMARY
Phase **G1a is complete**: the meal-entry contract is locked in code, and two server routes (`/meal-wizard-step4-confirm`, `/meal-wizard-step4-remove`) write/remove a single confirmed meal in the wizard session, keeping `used_proteins` in sync. A confirmed meal now persists in session state and survives reload. All four validation steps pass. **G1b (the Step 4 screen) was not started — stopping here as instructed.**
