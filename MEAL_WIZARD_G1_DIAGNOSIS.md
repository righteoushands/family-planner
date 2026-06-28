# Meal Wizard Phase G1 (Step 4 / Lorenzo-generation) — DIAGNOSIS ONLY

> Read-only scoping pass. **No files were changed.** Generated against the current source.

---

# PART 1 — `claud.md` READ-BACK (Rule 15)

## Python 3.11 hard rules (1–12)
1. No backslashes inside f-strings
2. No nested quotes inside f-strings — use a variable outside the f-string instead
3. All GET routing uses elif chains in do_GET — never a bare if, never nested if blocks for routing. POST routing in do_POST uses standalone `if path == ...: ... return` blocks at the top level — this is the real convention in this codebase and must be matched exactly. Never use nested if blocks for routing in either handler.
4. Never put import statements inside if blocks or functions
5. All file writes use safe_save_json (tmp file + os.replace) — never open(f, 'w') directly
6. No walrus operator (`:=`)
7. Never use `'\n'` inside a JS string within a Python string literal — use `'\\n'` so the browser receives the escape sequence, not a raw newline
8. multipart/form-data parsing: when fetch POSTs use FormData the server receives multipart/form-data not urlencoded. The do_POST handler must sniff Content-Type and parse accordingly using cgi.FieldStorage for multipart. If a POST handler receives empty data check the Content-Type first.
9. py_compile passes but runtime fails: py_compile only validates syntax not runtime correctness. Always run an in-process smoke test after py_compile to catch NameError, missing variable definitions, and import failures. After the in-process smoke test, also run the relevant existing verify_phase_*.py harness for the area touched and paste the result — the smoke test confirms the changed function works, but the harness catches regressions in nearby functionality. Do not skip the harness run for changes that touch shared data files, save paths, or any function called from more than one place.
10. test fixtures must never write to live data: verification harnesses must always operate on a temp copy of live data files. Never call save_progress, safe_save_json, or any write helper on live data during testing. Always restore from backup after any test that touches data files.
11. double-escaping HTML entities: never pass a string that is already HTML-escaped through escape() again. If a string contains literal ampersands for display use plain ampersands in the source string and let escape() handle it once. Strings pre-escaped with `&amp;` will render as visible `&amp;` in the browser if escaped again.
12. JS newline in Python f-strings applies everywhere: rule 7 applies to ALL files containing JS embedded in Python, not just render_frol_wizard.py. This includes render_schedule.py, render_timeblock.py, render_lucy.py, render_lorenzo.py, and any other render file with inline JavaScript.

## Additional rules (13–19)
13. **FROL WIZARD NESTED FORM ADDENDUM** — The `_body_has_form` check in `_section_chrome` looks for `action="/frol-wizard"` in the body string. Any form inside a section body posting to /frol-wizard will suppress the Save and Continue button. Variant tab forms posting to /frol-set-variant are safe. Activity builder forms posting to /frol-add-activity are safe. Before adding any form to a section body confirm its action attribute. This is a recurring bug — document before fixing if it appears again.
14. **PRE-FLIGHT CHECKLIST** — Before writing any spec answer these: (1) how many files does this touch, list them, if unknown that is a diagnosis step first; (2) does it involve JavaScript inside Python f-strings, if yes flag the backslash-n rule explicitly in the spec; (3) does it touch form handling, if yes confirm no nested forms posting to /frol-wizard; (4) is the root cause confirmed or assumed, if assumed run diagnosis first never draft a fix on an assumed cause; (5) does it touch multiple files at once, if yes break into separate single-purpose instructions; (6) does it involve data shape changes or migration, if yes confirm before and after data structure explicitly before writing the spec.
15. **CLAUD.MD READ-BACK REQUIRED** — At the start of every session read claud.md and paste back every rule found. Then identify which rules apply to today's task. If you cannot paste the rules back accurately stop and ask Lauren to re-paste claud.md before proceeding.
16. **MAGNIFICA HUMANITAS DESIGN PRINCIPLES** — Every feature must reflect these. The deepest danger: that people come to see themselves and one another as projects to be optimized rather than persons called to relationship and communion. The app must never become an optimization engine; it reduces friction so the family has more room for prayer, presence, love, rest, and formation. (1) the app is a tool not an authority; every AI suggestion is framed as a suggestion never a prescription — "here is one way to think about this" never "you should" or "the optimal schedule is." (2) companions serve real relationships, never replace them. (3) AI supports thinking, it does not replace it; ask before suggesting; boys build their own plans before seeing AI suggestions. (4) be transparent about what AI is; companions never make theological claims with personal authority and never quietly assume a decision that belongs to Lauren; prayer texts come from verified Catholic sources only, never AI-generated. (5) language of grace not performance; no gamification, streaks, or shaming scores; a hard day is never framed as failure; Sick Day Mode is relief not defeat. (6) subsidiarity; the family governs itself; Lauren is always the authority. (7) formation in digital wisdom; the goal is that JP finishes high school able to plan his day without the app. Every feature should answer yes to at least one of these and harm none.
17. **ONE FIX PER INSTRUCTION** — Never bundle multiple fixes into one Agent instruction unless they are in the same file and directly related. Complex multi-file builds must be broken into sequential single-purpose phases with a compile check and report between each phase.
18. **AUGUST 15TH BUILD PLAN IS THE PRIORITY FILTER** — Between June 1st and August 15th 2026 every build request must be checked against the August 15th build plan before proceeding. If a requested build is not on the must-have or should-have list for the current week flag it to Lauren before starting. New feature ideas go on the post-September list unless they directly enable one of the 14 goals in the August 15th plan. Scope is the first thing to cut not quality.
19. **BUILD FOR A FUTURE SECOND FAMILY** — This app will eventually be shared with/sold to other families using a hosted multi-family model. Every feature must be written as if a second family will use it. Never hardcode McAdams or any single family's specifics into code. Keep family identity and config in app_settings.json. Keep all data reads and writes flowing through data_helpers.py with no direct file access in route handlers, so the eventual swap from JSON files to a database happens in one place. Do not bake in single-user assumptions where it is cheap to avoid them. This does NOT mean building multi-user features before August 15th.

## Other binding config sections in claud.md
- **AI calls:** Model `claude-sonnet-4-20250514`; called via urllib.request directly (no SDK); API key read from app_settings.json; **all AI responses go through `_repair_and_parse_json()` before use.**
- **Route patterns:** GET routes call render_*.py functions returning HTML; POST routes live in app.py do_POST chained as `elif path == "/route-name":`; **JSON POST bodies must be registered in `_JSON_PATHS`** or the form-parser consumes the payload silently.
- **Anchor-tag navigation:** plain `<a href>` can't POST/mutate state; needed state must travel in the query string or be persisted before the click; use `<form method="POST">` if a button must trigger persistent state.
- **Change discipline:** all changes additive unless told otherwise; keep modules under 800 lines where possible.
- **People:** Lauren/Mom (same person), John, JP (14), Joseph (12), Michael (5), James (13 mo — never assigned tasks, excluded from school renderers/gradebook). Always title-case.

> ⚠️ **Note:** claud.md rule 3 and the "Route patterns" section **contradict each other** — rule 3 says POST routing uses "standalone `if path == ...: return` blocks at the top level," while "Route patterns" says POST routes are "chained as `elif path == ...`". The **actual code uses `elif` chains** (see the meal handlers below), matching the "Route patterns" wording.

---

# PART 2 — RULES THAT APPLY TO A STEP 4 / LORENZO-GENERATION BUILD

**Hard rules in play:** 1, 2 (f-string discipline in any render_*.py changes), 4 (imports at top — note existing handlers violate this with inline `import json as _json`; match the file's local convention but be aware), 5 (all writes via `safe_save_json`), 6 (no walrus), 7 & 12 (JS-in-Python newline rule — Step 3's JS uses concatenated string literals, no f-strings; match that), 8 (Content-Type sniff — but Step 4 should be a JSON route like step3-save, not multipart), 9 & 10 (smoke test + verify harness on a **temp copy** of data), 11 (escape once).

**Process/route rules in play:**
- **Route patterns + `_JSON_PATHS`** — a new `/meal-wizard-step4-*` route that receives a JSON body MUST be added to the `_JSON_PATHS` set, and must read `Content-Length`/`self.rfile.read(...)` directly (the form-parser is bypassed for those paths). Match the `elif path == ...:` chain convention.
- **AI calls section** — model/urllib/api-key-from-app_settings conventions (⚠️ but see the model discrepancy flagged below); decide deliberately whether Step 4 routes Lorenzo's JSON through `_repair_and_parse_json` (the plan-importer does; the live Lorenzo chat does **not** — see findings).
- **14 (pre-flight checklist)** — Step 4 touches multiple files (render + app.py handler + session schema) and involves JS-in-Python and a data-shape change to the session (`confirmed_meals`), so all six pre-flight questions are live.
- **15** — this read-back. **17** — Step 4 must be split into single-purpose phases (renderer, save route, generation call, persistence) with a compile/report between each. **18** — confirm Step 4 is on the August-15 must/should list before building.
- **16 (Magnifica)** — Lorenzo's generated plan must be framed as a **suggestion not a prescription**; no optimization language; Lauren confirms before anything is saved as permanent.
- **19 (second family)** — no hardcoded "McAdams"/family specifics in new Step 4 logic (⚠️ note `build_lorenzo_context` currently hardcodes the McAdams family roster — see findings); route all reads/writes through data_helpers.

---

# PART 3 — CODE ITEMS (VERBATIM)

## ⚠️ KEY FINDINGS UP FRONT (where reality differs from the guesses)

1. **`data/meal_wizard_session.json` does NOT exist on disk** — it is created lazily on first write (`save_/update_meal_wizard_session` → `safe_save_json`). `load_meal_wizard_session()` returns `{}` when absent.
2. **Lorenzo's Anthropic API call is NOT in `render_lorenzo.py`.** `render_lorenzo.py` only *assembles the context* (`build_lorenzo_context` + the `_get_*` helpers). The actual urllib call + response parse is **inline in `app.py` inside the `/lorenzo-chat` POST handler** (call at lines 5867–5888).
3. **Model discrepancy:** claud.md's "AI calls" says `claude-sonnet-4-20250514`, but the live Lorenzo call uses **`claude-haiku-4-5-20251001`** (app.py:5868). `replit.md` also documents Haiku. claud.md is stale here.
4. **`_repair_and_parse_json` is a NESTED local function**, defined **once**, inside the plan-import POST handler (app.py:8412) — it is **not** a module-level shared helper. **Lorenzo's chat handler does NOT use it** (it just does `result.get("content",[{}])[0].get("text","")`). claud.md's claim that "all AI responses go through `_repair_and_parse_json()`" is **not** true in code — only the plan importer uses it.
5. **`_JSON_PATHS` is a local set** defined *inside* `do_POST` (app.py:3536), not module-level.

---

## SESSION STATE

### `data_helpers.py` — meal wizard session functions (lines 3293–3317)
```python
def load_meal_wizard_session() -> dict:
    """Load current meal wizard session state. Returns {} if no active session."""
    try:
        with open(MEAL_WIZARD_SESSION_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_meal_wizard_session(session: dict) -> None:
    """Persist meal wizard session state via safe_save_json."""
    safe_save_json(MEAL_WIZARD_SESSION_FILE, session)


def clear_meal_wizard_session() -> None:
    """Wipe the meal wizard session file (called when plan is locked or abandoned)."""
    safe_save_json(MEAL_WIZARD_SESSION_FILE, {})


def update_meal_wizard_session(updates: dict) -> dict:
    """Merge updates into current session state and save. Returns updated session."""
    session = load_meal_wizard_session()
    session.update(updates)
    save_meal_wizard_session(session)
    return session
```
> ⚠️ `load_meal_wizard_session` reads with a **bare `open(...)`** (not via a data_helpers loader) — fine for a read, but note it's the only meal-wizard read not going through `ensure_file`. `MEAL_WIZARD_SESSION_FILE` is owned by `config.py`.

### `app.py` — `/meal-wizard-step3-save` handler (lines 10655–10725+)
```python
            elif path == "/meal-wizard-step3-save":
                # JSON body (registered in _JSON_PATHS so the form-parser leaves
                # it alone); read and parse the raw body like /plan-import-apply.
                _s3_cl  = int(self.headers.get("Content-Length","0") or 0)
                _s3_raw = self.rfile.read(_s3_cl).decode("utf-8","ignore") if _s3_cl else ""
                try:    _s3_payload = json.loads(_s3_raw)
                except Exception: _s3_payload = {}
                _S3_PLAN_KEYS  = {"breakfast","lunch","dinner","johns_lunch",
                                  "snacks","dessert","feast_meal","batch_cook"}
                _S3_SLOTS      = {"breakfast","lunch","dinner","johns_lunch"}
                _S3_CX_KEYS    = {"full_effort","normal","simple"}
                # Meal types — allowlist filtered (the UI gates which appear).
                _wtp_in = _s3_payload.get("what_to_plan") or []
                _what_to_plan = [k for k in _wtp_in if k in _S3_PLAN_KEYS] \
                    if isinstance(_wtp_in, list) else []
                # Complexity — allowlisted single value.
                _cx_in = _s3_payload.get("complexity","")
                _complexity = _cx_in if _cx_in in _S3_CX_KEYS else ""
                # Planning window — each end validated via fromisoformat.
                def _s3_valid_iso(_v):
                    try:    date.fromisoformat(_v); return _v
                    except Exception: return ""
                _win_in    = _s3_payload.get("planning_window") or {}
                _start_iso = _s3_valid_iso(str(_win_in.get("start_iso","")))
                _end_iso   = _s3_valid_iso(str(_win_in.get("end_iso","")))
                _planning_window = {"start_iso": _start_iso, "end_iso": _end_iso}
                # Server-side enforce the conditional meal types so they cannot
                # be persisted out of context via a crafted request: feast_meal
                # only with a feast in the window, batch_cook only when a meal
                # rule mentions batching (mirrors the UI gating).
                if "feast_meal" in _what_to_plan and not _s3_feast_in_window(_start_iso, _end_iso):
                    _what_to_plan = [_k for _k in _what_to_plan if _k != "feast_meal"]
                if "batch_cook" in _what_to_plan and not _s3_has_sunday_batch():
                    _what_to_plan = [_k for _k in _what_to_plan if _k != "batch_cook"]
                # Pre-filled past meals -> confirmed_meals. These are locked,
                # kept off the grocery list, and never generate recipe cards.
                _prefill_in = _s3_payload.get("prefill") or {}
                _new_prefill = {}
                if isinstance(_prefill_in, dict):
                    for _pk, _pv in _prefill_in.items():
                        _name = clean_text(_pv)
                        if not _name:
                            continue
                        _parts = str(_pk).split("::")
                        if len(_parts) != 2:
                            continue
                        _pd, _pslot = _parts[0], _parts[1]
                        if _pslot not in _S3_SLOTS:
                            continue
                        if not _s3_valid_iso(_pd):
                            continue
                        _new_prefill[_pd + "::" + _pslot] = {
                            "name": _name, "locked": True, "source": "prefill",
                            "skip_shopping": True, "recipe_on_request": True,
                        }
                # Preserve any non-prefill confirmed meals (future steps); refresh
                # the prefill-sourced entries from this save.
                _existing_meals = load_meal_wizard_session().get("confirmed_meals") or {}
                _confirmed_meals = {
                    _ek: _ev for _ek, _ev in _existing_meals.items()
                    if not (isinstance(_ev, dict) and _ev.get("source") == "prefill")
                }
                _confirmed_meals.update(_new_prefill)
                update_meal_wizard_session({
                    "confirmed_what_to_plan": _what_to_plan,
                    "confirmed_complexity": _complexity,
                    "planning_window": _planning_window,
                    "confirmed_meals": _confirmed_meals,
                })
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                # (writes b'{"ok":true}' and returns — same pattern as the others)
```
**Session keys this writes:** `confirmed_what_to_plan` (list), `confirmed_complexity` (str), `planning_window` ({start_iso,end_iso}), `confirmed_meals` (dict keyed `"YYYY-MM-DD::slot"` → `{name, locked, source:"prefill", skip_shopping, recipe_on_request}`). Also relies on two helpers `_s3_feast_in_window(...)` and `_s3_has_sunday_batch()` (defined elsewhere in app.py — referenced here, not shown).

### `render_meal_wizard_step3.py` — the code that builds the saved payload (lines 163–181)
This is the **client-side** builder that POSTs to `/meal-wizard-step3-save` (the `confirmed_meals`/`what_to_plan` shaping is done server-side, above). Note: JS is built as **concatenated string literals**, not f-strings (Rule 7/12-safe).
```javascript
  window.s3Save = function(){
    var status = byId('s3-status'); if(status){ status.textContent = ''; }
    var wtp = [];
    var checks = document.querySelectorAll('.mt-check');
    for(var i=0;i<checks.length;i++){ if(checks[i].checked){ wtp.push(checks[i].value); } }
    var cx = byId('s3-complexity') ? byId('s3-complexity').value : '';
    var win = { start_iso: byId('s3-start').value, end_iso: byId('s3-end').value };
    var prefill = {};
    var inputs = document.querySelectorAll('.pf-input');
    for(var k=0;k<inputs.length;k++){ var v = (inputs[k].value||'').trim();
      if(v){ prefill[inputs[k].getAttribute('data-date')+'::'+inputs[k].getAttribute('data-slot')] = v; } }
    var payload = { what_to_plan: wtp, complexity: cx, planning_window: win, prefill: prefill };
    fetch('/meal-wizard-step3-save', { method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) })
      .then(function(r){ return r.json(); })
      .then(function(j){ if(j && j.ok){ window.location.href = '/meal-wizard-step3?saved=1'; }
        else if(status){ status.textContent = 'Could not save. Please try again.'; } })
      .catch(function(){ if(status){ status.textContent = 'Could not save. Please try again.'; } });
  };
```
The server-side reader of these session keys (for the Step 3 confirmation summary) lives in the same file at lines ~378–408 (`session.get("confirmed_what_to_plan")`, `confirmed_complexity`, `confirmed_meals`, counting `source == "prefill"`).

### `data/meal_wizard_session.json`
> ⚠️ **Does not exist.** No file on disk. It is created on the first `save_/update_meal_wizard_session` call and wiped to `{}` by `clear_meal_wizard_session`.

---

## MEAL STORE

### `render_meals.py` — `_week_key`, `load_meal_plan`, `save_meal_plan` (lines 82–179)
```python
def _week_key(for_date: date = None) -> str:
    d = for_date or date.today()
    # Use Monday of the week as canonical key (e.g. 2026-04-06)
    monday = d - timedelta(days=d.weekday())
    return monday.isoformat()
```
```python
def load_meal_plan(week_key: str = None) -> dict:
    import re as _re
    key = week_key or date.today().isoformat()
    default = {
        "start": key,
        "week":  key,  # backward compat
        "generated": False,
        "days": {day: {slot: "" for slot in MEAL_SLOTS} for day in DAYS}
    }
    path = _plan_path(key)
    # Fast path: file exists under given key
    if os.path.exists(path):
        return ensure_file(path, default)
    # If key is an ISO date but not a Monday, try the Monday-of-that-week key.
    if _re.match(r'\d{4}-\d{2}-\d{2}', key):
        try:
            d = date.fromisoformat(key)
            monday = d - timedelta(days=d.weekday())
            mon_key = monday.isoformat()
            if mon_key != key:
                mon_path = _plan_path(mon_key)
                if os.path.exists(mon_path):
                    plan = ensure_file(mon_path, default)
                    plan.setdefault("start", mon_key)
                    return plan
            # Backward compat: also try the old YYYY-WNN week key
            old_key  = d.strftime("%Y-W%W")
            old_path = _plan_path(old_key)
            if os.path.exists(old_path):
                plan = ensure_file(old_path, default)
                plan.setdefault("start", key)
                return plan
        except Exception:
            pass
    return ensure_file(path, default)
```
```python
def save_meal_plan(plan: dict):
    # Use "start" (ISO date) as primary key; fall back to "week" for old plans
    key = plan.get("start") or plan.get("week", date.today().isoformat())
    _backup_meal_plan(key)  # snapshot prior version BEFORE overwriting
    safe_save_json(_plan_path(key), plan)
```
> ⚠️ Note for Step 4: `save_meal_plan` auto-snapshots via `_backup_meal_plan` (keeps last 30 per week in `data/meal_plan/.backups/`) before every overwrite — relevant if Lorenzo-generation writes the plan. Plan shape: `{start, week, generated(bool), days:{Day:{slot:""}}}`. There are also `_planning_week_key` (Mon–Thu→this Monday, Fri–Sun→next Monday) and `_week_start` helpers adjacent.

### `app.py` — `/meal-save-plan` handler (lines 10536–10555)
```python
            elif path == "/meal-save-plan":
                import json as _json
                wk    = clean_text(data.get("week",[""])[0]) or _week_key()
                raw   = data.get("days",["{}"])[0]
                try:   days_in = _json.loads(raw)
                except: days_in = {}
                plan = load_meal_plan(wk)
                for day, slots in days_in.items():
                    if day not in plan["days"]: plan["days"][day] = {}
                    for slot, val in slots.items():
                        plan["days"][day][slot] = clean_text(val)
                plan["week"]  = wk
                plan["start"] = wk
                save_meal_plan(plan)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return
```
> ⚠️ This route reads from `data` (the urlencoded/form dict) with `data.get("week")[0]` — it is **NOT** in `_JSON_PATHS`; the `days` payload travels as a JSON-encoded **string field** inside a form post, parsed with `_json.loads`. A new Step 4 route sending a raw JSON body would instead follow the **step3-save** pattern (`_JSON_PATHS` + `self.rfile.read`).

---

## RECIPES

### `data_helpers.py` — `load_recipes`, `save_recipes`, `add_recipe`, `save_recipe` (lines 1980–2041)
```python
def load_recipes() -> list:
    data = ensure_file(RECIPES_FILE, {"recipes": []})
    # Legacy format: top-level list
    if isinstance(data, list):
        return data
    return data.get("recipes", [])

def save_recipes(recipes: list):
    safe_save_json(RECIPES_FILE, {"recipes": recipes})
```
```python
def save_recipe(name: str, ingredients: str, instructions: str,
                tags: list = None, prep_time: str = "", image: str = "") -> dict:
    """Append a new recipe to the library. Always creates a new id; does NOT
    dedupe by name (use add_recipe for dedup-by-name behavior). Preserved as
    the form-input wrapper for /recipe-save."""
    import uuid
    from datetime import date as _d
    recipes = load_recipes()
    recipe = {
        "id": str(uuid.uuid4())[:8],
        "name": name.strip(),
        "ingredients": ingredients.strip(),
        "instructions": instructions.strip(),
        "tags": tags or [],
        "prep_time": prep_time.strip(),
        "image": (image or "").strip(),
        "created": _d.today().isoformat(),
    }
    recipes.append(recipe)
    save_recipes(recipes)
    return recipe

def add_recipe(recipe: dict) -> dict:
    """Add or update a recipe (match by name, case-insensitive). Returns saved recipe."""
    import uuid
    from datetime import date as _d
    recipes = load_recipes()
    name = recipe.get("name", "").strip()
    # Dedup: replace if same name already exists
    recipes = [r for r in recipes if r.get("name", "").lower() != name.lower()]
    recipe.setdefault("id", str(uuid.uuid4())[:8])
    recipe.setdefault("date_added", _d.today().isoformat())
    recipes.append(recipe)
    save_recipes(recipes)
    return recipe
```
> ⚠️ Two id/date conventions coexist: `save_recipe` writes `"created"`; `add_recipe` writes `"date_added"`. There is also `get_recipe_by_id(rid)` (line 1990) used by Lorenzo's `|recipe=` linking, plus `delete_recipe` and `search_recipes`.

### `app.py` — `/recipe-save` and `/recipe-import` handlers (dispatch at 3212; bodies at 3241 & 3275)
These are **multipart** routes (registered for FieldStorage parsing at app.py:2546–2547), dispatched via a shared `elif path in ("/recipe-import","/recipe-save"):` block (line 3212) that defines `_read_upload`/`_save_dish_photo`, then **nested `if path == ...:` blocks** select the body:
```python
            elif path in ("/recipe-import", "/recipe-save"):
                import json as _rj, base64 as _b64, re as _rre, os as _ros, uuid as _ruuid
                def _read_upload(field_name):
                    ...
                def _save_dish_photo(raw, name_hint):
                    ...

            if path == "/recipe-save":
                # Manual create OR inline edit (now multipart so dish_photo can be uploaded)
                rid_edit = clean_text(form.getfirst("id", ""))
                name     = clean_text(form.getfirst("name", ""))
                ingr     = clean_text(form.getfirst("ingredients", ""))
                instr    = clean_text(form.getfirst("instructions", ""))
                tags_raw = clean_text(form.getfirst("tags", ""))
                tags     = [t.strip() for t in tags_raw.split(",") if t.strip()]
                prep     = clean_text(form.getfirst("prep_time", ""))
                remove_image  = clean_text(form.getfirst("remove_image", "")) == "1"
                hidden_image  = clean_text(form.getfirst("image_url", ""))  # from import-preview flow
                _, dish_raw, _dm, _dn = _read_upload("dish_photo")
                new_image_url = _save_dish_photo(dish_raw, _dn) if dish_raw else ""
                effective_image = new_image_url or hidden_image
                if name:
                    if rid_edit:
                        recipes = load_recipes()
                        for r in recipes:
                            if isinstance(r, dict) and r.get("id") == rid_edit:
                                r["name"] = name; r["ingredients"] = ingr
                                r["instructions"] = instr; r["tags"] = tags
                                r["prep_time"] = prep
                                if new_image_url:
                                    r["image"] = new_image_url
                                elif remove_image:
                                    r["image"] = ""
                        save_recipes(recipes)
                    else:
                        save_recipe(name, ingr, instr, tags, prep, image=effective_image)
                self.send_response(302)
                self.send_header("Location", "/recipes?msg=Recipe+saved")
                self.end_headers(); return

            if path == "/recipe-import":
                name_in    = clean_text(form.getfirst("name", ""))
                url_in     = clean_text(form.getfirst("url", ""))
                text_in    = clean_text(form.getfirst("text", ""))
                _, photo_bytes_tmp, photo_mime, photo_name = _read_upload("recipe_photo")
                photo_bytes = photo_bytes_tmp if photo_bytes_tmp else None
                _, dish_raw, _dpm, _dpn = _read_upload("dish_photo")
                dish_image_url = _save_dish_photo(dish_raw, _dpn) if dish_raw else ""
                _is_pdf = ("pdf" in photo_mime) or photo_name.endswith(".pdf") or (
                    photo_bytes and photo_bytes[:4] == b"%PDF")
                ... # PDF text extraction (PyPDF2), URL fetch (urllib JSON-LD scrape),
                    # then a vision/text AI extraction follows (continues past line 3324)
```
> ⚠️ **Convention nuance relevant to Step 4:** `/recipe-save` and `/recipe-import` are an **exception** to the "JSON route" pattern — they are multipart (FieldStorage), use a `elif path in (...)` outer + nested `if path == ...` inner, and end with a **302 redirect**, not a JSON `{"ok":true}`. Don't copy this for a JSON Step 4 route — copy `/meal-wizard-step3-save` instead.

---

## CALENDAR

### `data_helpers.py` — `expand_local_events_for_range` (lines 2488–2557)
```python
def expand_local_events_for_range(start_iso: str, end_iso: str) -> list:
    """
    Expand data/events.json entries into calendar-compatible dicts
    {title, start (ISO datetime or date), all_day, start_time, end_time}
    for every date in [start_iso .. end_iso] (inclusive).
    Handles recurrence types: none / daily / weekly.
    """
    from datetime import date as _dt, timedelta as _td
    events = load_local_events()
    out = []
    start_d = _dt.fromisoformat(start_iso)
    end_d   = _dt.fromisoformat(end_iso)

    def _add(ev, d):
        st = ev.get("start_time", "")
        et = ev.get("end_time", "")
        iso_start = f"{d.isoformat()}T{st}" if st else d.isoformat()
        out.append({
            "title":      ev.get("title", ""),
            "start":      iso_start,
            "end":        f"{d.isoformat()}T{et}" if et else d.isoformat(),
            "all_day":    not bool(st),
            "start_time": st,
            "end_time":   et,
            "notes":      ev.get("notes", ""),
            "assigned_to": ev.get("assigned_to", []),
            "source":     "local",
        })

    for ev in events:
        if ev.get("archived"):
            continue
        rec  = ev.get("recurrence", {}) or {}
        rtype = rec.get("type", "none") or "none"
        ev_start = ev.get("start_date", "")
        if not ev_start:
            continue
        try:
            ev_start_d = _dt.fromisoformat(ev_start)
        except ValueError:
            continue

        if rtype == "none":
            if start_d <= ev_start_d <= end_d:
                _add(ev, ev_start_d)
        elif rtype == "daily":
            cur = max(start_d, ev_start_d)
            until = rec.get("until")
            while cur <= end_d:
                if until and cur.isoformat() > until:
                    break
                _add(ev, cur)
                cur += _td(days=1)
        elif rtype == "weekly":
            by_day = [w.lower() for w in (rec.get("by_weekday") or [])]
            interval = max(1, int(rec.get("interval", 1)))
            until    = rec.get("until")
            cur = max(start_d, ev_start_d)
            while cur <= end_d:
                if until and cur.isoformat() > until:
                    break
                dow = _WEEKDAY_NAMES[cur.weekday()]
                if not by_day or dow in by_day:
                    _add(ev, cur)
                cur += _td(days=interval if not by_day else 1)

    out.sort(key=lambda e: e["start"])
    return out
```

### `data_helpers.py` — `get_merged_calendar_events` (lines 2560–2628)
```python
def get_merged_calendar_events(start_iso: str, days: int = 7) -> list:
    """Merge calendar sources into one structured, deduped, sorted event list.
    Sources merged:
      1. Local events.json (via expand_local_events_for_range), carrying the
         assigned_to -> who string.
      2. The Google / CalDAV cache (load_calendar_cache) — no people field.
      3. Subscribed iCal feeds (load_subscribed_calendar_cache) — no people field.
    Each returned dict has exactly: {"title", "start", "end", "who"}.
    ...
    This function does NOT swallow errors: malformed input or a loader failure
    raises, so an empty list never masks a real failure. ..."""
    _today = date.fromisoformat(start_iso)
    _end   = _today + timedelta(days=days - 1)
    _window = {(_today + timedelta(days=o)).isoformat() for o in range(days)}

    def _norm(ev, who):
        return {
            "title": (ev.get("title") or "").strip(),
            "start": ev.get("start", "") or "",
            "end":   ev.get("end", "") or "",
            "who":   who or "",
        }

    merged = []
    for e in (expand_local_events_for_range(_today.isoformat(), _end.isoformat()) or []):
        _assigned = e.get("assigned_to") or []
        if isinstance(_assigned, list):
            _who = ", ".join(str(x) for x in _assigned if str(x).strip())
        else:
            _who = str(_assigned).strip()
        merged.append(_norm(e, _who))
    for _loader in (load_calendar_cache, load_subscribed_calendar_cache):
        _cache = _loader() or {}
        _cache_evs = _cache.get("events") if isinstance(_cache, dict) else []
        if not isinstance(_cache_evs, list):
            _cache_evs = []
        for e in _cache_evs:
            if isinstance(e, dict):
                merged.append(_norm(e, ""))

    merged = [m for m in merged if m["start"][:10] in _window]
    if not merged:
        return []

    _seen = set()
    _deduped = []
    for m in merged:
        _key = (m["title"], m["start"])
        if _key in _seen:
            continue
        _seen.add(_key)
        _deduped.append(m)

    _deduped.sort(key=lambda m: m["start"])
    return _deduped
```
> ⚠️ `get_merged_calendar_events` **intentionally raises** on loader failure (callers wrap their own try/except). The Step-1 week-glance renderer already wraps it.

### `render_meal_wizard.py` — Step 1 "week at a glance" per-day commitments (lines 359–456)
The per-day commitment rendering is `_wg_event_line` (one event) + `_wg_day_card` (one day's card incl. liturgical header/chips + commitments), composed by `render_meal_wizard_week_glance`.
```python
def _wg_event_line(ev: dict) -> str:
    """Format one merged calendar event ...: split start/end on the T, guard the
    all-day no-T case, append the who suffix when present."""
    title = escape(ev.get("title") or "(untitled)")
    start = ev.get("start") or ""
    end = ev.get("end") or ""
    st = start.split("T", 1)[1][:5] if "T" in start else ""
    et = end.split("T", 1)[1][:5] if "T" in end else ""
    if st and et:
        time_str = f"{st}-{et}"
    elif st:
        time_str = st
    else:
        time_str = "All day"
    who = (ev.get("who") or "").strip()
    who_str = f" \u2014 {escape(who)}" if who else ""
    return f'<div style="{_WG_EVENT_ROW}">{escape(time_str)}  {title}{who_str}</div>'


def _wg_day_card(d: date, day_events: list) -> str:
    """Render one day card: liturgical header + marker chips + commitments."""
    info = get_day_info(d)
    weekday = escape(info.get("weekday", ""))
    date_label = escape(info.get("date_label", ""))
    season = info.get("season", "")
    season_color = _wg_safe_color(info.get("season_color"), "#888")
    header = (
        f'<h3 style="{_WG_DAY_HEADER}">'
        f'<span style="{_WG_SEASON_DOT}background:{season_color};"></span>'
        f'{weekday} \u2014 {date_label}</h3>'
    )
    season_label = (
        f'<div style="{_WG_SEASON_LABEL}">{escape(season)}</div>' if season else ""
    )
    chips = []
    feast_name = info.get("feast_name") or ""
    if feast_name:
        feast_bg = _wg_safe_color(info.get("feast_color"), _WG_FEAST_DEFAULT_BG)
        chips.append(_wg_marker_chip(feast_name, feast_bg))
    if info.get("is_abstinence"):
        chips.append(_wg_marker_chip("Abstinence \u2014 no meat", _WG_ABSTINENCE_BG))
    if info.get("is_fast"):
        chips.append(_wg_marker_chip("Fast day", _WG_FAST_BG))
    chip_row = (
        f'<div style="{_WG_CHIP_ROW}">{"".join(chips)}</div>' if chips else ""
    )
    if day_events:
        events_html = "".join(_wg_event_line(ev) for ev in day_events)
    else:
        events_html = f'<div style="{_WG_QUIET}">No commitments</div>'
    return (
        f'<div style="{_WG_DAY_CARD}">'
        f'{header}{season_label}{chip_row}{events_html}'
        f'</div>'
    )


def render_meal_wizard_week_glance(user: str, start_iso: str = None) -> str:
    """Step 1 ... a read-only orientation view of the coming week ..."""
    if not start_iso:
        start_iso = date.today().isoformat()
    start_d = date.fromisoformat(start_iso)
    events_by_date = {}
    try:
        for ev in get_merged_calendar_events(start_iso, 7):
            key = (ev.get("start") or "")[:10]
            events_by_date.setdefault(key, []).append(ev)
    except Exception:
        events_by_date = {}
    day_cards = []
    for offset in range(7):
        d = start_d + timedelta(days=offset)
        day_cards.append(_wg_day_card(d, events_by_date.get(d.isoformat(), [])))
    inner = (
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin:0 0 2px;">Plan This Week\u2019s Meals</h1>'
        f'<p style="{_WG_SUBTITLE}">Step 1 of 6 \u2014 Your week at a glance</p>'
        f'{_wg_rules_panel()}'
        f'{"".join(day_cards)}'
        f'<a href="/meal-wizard-step2" style="{_WG_BTN_LINK}">Continue</a>'
    )
    body = (
        f'<div style="max-width:680px;margin:0 auto;padding:24px 16px 96px;">'
        f'{inner}'
        f'</div>'
    )
    return html_page("Plan This Week\u2019s Meals", body)
```
> ⚠️ Note: subtitle says **"Step 1 of 6"** — the wizard is scoped as a 6-step flow (relevant context for where Step 4 fits). `season_color`/`feast_color` pass through `_wg_safe_color` before being inlined into `style="..."`.

---

## LORENZO GENERATION

### `render_lorenzo.py` — context / knowledge-stack assembler
The "knowledge stack" is assembled by **`build_lorenzo_context(iso, weekday, date_label)`** (lines 475–929), which pulls from these **`_get_*` helper functions** (each reads one live data source via data_helpers):

| Helper | Line | Supplies |
|---|---|---|
| `_get_current_meal_plan(iso)` | 66 | `== CURRENT MEAL PLAN ==` |
| `_get_inventory()` | 197 | `== PANTRY / FRIDGE / FREEZER ==` |
| `_get_saved_recipes()` | 210 | `== SAVED RECIPE CARDS ==` |
| `_get_meal_constraints()` | 248 | `== STANDING MEAL RULES & CONSTRAINTS ==` |
| `_get_lucy_capacity(iso)` | 282 | Lauren's capacity today |
| `_get_john_status(iso)` | 297 | John's status |
| `_get_liturgical_note(iso)` | 312 | Liturgical note |
| `_get_calendar_this_week(iso)` | 336 | `== CALENDAR THIS WEEK ==` |
| `_get_planning_session_block()` | 399 | guided-planning block |

The head of the assembler (the part that calls every helper and builds the `lines` list — the reusable knowledge-stack scaffold a Step 4 generation call would lean on):
```python
def build_lorenzo_context(iso: str, weekday: str, date_label: str) -> str:
    from datetime import datetime as _dt
    meal_plan   = _get_current_meal_plan(iso)
    inventory   = _get_inventory()
    constraints = _get_meal_constraints()
    capacity    = _get_lucy_capacity(iso)
    john_status = _get_john_status(iso)
    liturny     = _get_liturgical_note(iso)
    saved_recipes = _get_saved_recipes()
    calendar_week = _get_calendar_this_week(iso)

    _now_e = _dt.now(_EASTERN)
    _h     = _now_e.hour
    _time_str = _now_e.strftime("%-I:%M %p")   # e.g. "4:35 PM"
    # ... time-of-day _phase string (early morning / morning / midday / ... / evening) ...

    lines = [
        "You are Lorenzo — the McAdams family's personal AI chef.",
        ...
        f"CRITICAL — TODAY'S DATE: {weekday}, {date_label} ({iso}).",
        ...
        f"CURRENT TIME: {_phase}",
        "== THE McADAMS FAMILY ==", ...
        "== KITCHEN CREW ==", ...
        f"Lauren's capacity today: {capacity}",
    ]
    if john_status: lines.append(john_status)
    if liturny:     lines += ["", f"LITURGICAL NOTE: {liturny}"]
    lines += [
        ... "== CURRENT MEAL PLAN ==", meal_plan,
        ... "== PANTRY / FRIDGE / FREEZER ==", inventory,
        ... "== STANDING MEAL RULES & CONSTRAINTS ==", constraints,
        ... "== CALENDAR THIS WEEK ==", calendar_week,
        ... "== SAVED RECIPE CARDS ==", saved_recipes,
        ... # then a large literal system-prompt body: write-tag protocol
            # ([MEAL_UPDATE], [RECIPE_CARD:add], [RULE:add], <meal_constraint_update>,
            # <frol_update>), forbidden fake patterns, never-fake-a-save guard,
            # temporary-vs-permanent rule detection, and the 5 HARD RULES
            # (leftover rule, date-range rule, kid-helper rule, ...).
    ]
    # (returns "\n".join(lines) at the end, ~line 929)
```
> ⚠️ **Findings for Step 4:**
> - **Rule 19 violation already present:** the family roster ("McAdams family", JP/Joseph/Michael/James with ages and kitchen roles) is **hardcoded** into `build_lorenzo_context` rather than read from `app_settings.json`. A second-family-safe Step 4 should not deepen this; ideally route the roster through data_helpers.
> - The "5 HARD RULES" embedded in the prompt (leftover rule, date-range rule, kid-helper rule, etc.) are exactly the generation constraints a Step 4 batch-generation call must honor.

### The function that makes the Anthropic API call + parses the response
> ⚠️ **This is NOT in `render_lorenzo.py`.** It is **inline in `app.py`'s `/lorenzo-chat` POST handler** (call/parse at lines 5867–5888):
```python
                payload = _json.dumps({
                    "model":      "claude-haiku-4-5-20251001",
                    "max_tokens": 1500,
                    "system":     lorenzo_context + _AI_GUARDRAILS,
                    "messages":   messages,
                }).encode()
                req = _req.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={
                        "Content-Type":      "application/json",
                        "x-api-key":         api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    method="POST"
                )
                try:
                    with _req.urlopen(req, timeout=45) as resp:
                        result = _json.loads(resp.read().decode())
                    text = result.get("content",[{}])[0].get("text","").strip()
                except Exception as e:
                    text = f"Lorenzo is away from the stove. ({e})"
```
> ⚠️ Lorenzo's parse is a **plain `result.get("content")[0].get("text")`** — it does **NOT** route through `_repair_and_parse_json` (Lorenzo doesn't ask for JSON; it emits bracket/XML save-tags that a regex `_meal_rx` extracts afterward, lines 5896+). Model is **Haiku** (`claude-haiku-4-5-20251001`), `max_tokens=1500`, `timeout=45`, vision supported via base64 image blocks, `system = build_lorenzo_context(...) + _UNDO_BLOCK + _AI_GUARDRAILS`, conversation history capped at `LORENZO_CONTEXT_MAX`.

### `_repair_and_parse_json` — definition (app.py:8412, nested inside the plan-import handler)
```python
                def _repair_and_parse_json(raw_str):
                    """Try to parse JSON, repairing common LLM mistakes."""
                    # Attempt 1: as-is
                    try: return _pij.loads(raw_str)
                    except Exception: pass
                    # Attempt 2: remove trailing commas before } or ]
                    import re as _re2
                    fixed = _re2.sub(r',(\s*[}\]])', r'\1', raw_str)
                    try: return _pij.loads(fixed)
                    except Exception: pass
                    # Attempt 3: escape literal newlines inside string values
                    def _fix_newlines(s):
                        result, in_str, i = [], False, 0
                        while i < len(s):
                            c = s[i]
                            if c == '"' and (i == 0 or s[i-1] != '\\'):
                                in_str = not in_str
                                result.append(c)
                            elif in_str and c == '\n':
                                result.append('\\n')
                            elif in_str and c == '\r':
                                result.append('\\r')
                            elif in_str and c == '\t':
                                result.append('\\t')
                            else:
                                result.append(c)
                            i += 1
                        return ''.join(result)
                    fixed2 = _fix_newlines(fixed)
                    try: return _pij.loads(fixed2)
                    except Exception: pass
                    # Attempt 4: strip trailing commas again after newline fix
                    fixed3 = _re2.sub(r',(\s*[}\]])', r'\1', fixed2)
                    try: return _pij.loads(fixed3)
                    except Exception: pass
                    # Attempt 5: add missing commas between adjacent string/object/array values
                    fixed4 = _re2.sub(r'("|\d|true|false|null|}|])\s*\n(\s*)("|\{|\[)', r'\1,\n\2\3', fixed3)
                    try: return _pij.loads(fixed4)
                    except Exception: pass
                    # Attempt 6: combined
                    fixed5 = _re2.sub(r',(\s*[}\]])', r'\1', fixed4)
                    return _pij.loads(fixed5)  # raise if still broken
```
> ⚠️ Because it's **nested**, `_repair_and_parse_json` is **only callable inside the plan-import handler**. If Step 4 wants Lorenzo to return structured JSON (a whole-week plan), you cannot call this directly — you'd either (a) promote it to a module-level helper (a refactor, requires explicit sign-off per change-discipline/Rule 17), or (b) keep Lorenzo's existing bracket-tag protocol and parse with regex like the live chat does. It depends on closure-local names `_pij` (json) defined in that handler.

---

## ROUTING CONVENTION

### `app.py` — `_JSON_PATHS` (line 3536, local to `do_POST`)
```python
            _JSON_PATHS = {"/plan-import-apply", "/plan-import-undo-placement", "/curriculum-save", "/curriculum-minutes", "/poetry-passage-save", "/meal-wizard-step3-save"}
            if path in _JSON_PATHS:
                # (raw JSON body read via Content-Length / self.rfile.read in each handler)
```

### The `do_POST` block convention for the existing meal routes
All three are `elif path == ...:` branches in the `do_POST` chain:
- `/meal-save-plan` → **10536** — reads `data.get(...)` (form field carrying a JSON string `days`); **not** in `_JSON_PATHS`; responds `{"ok":true}`.
- `/meal-wizard-step2-save` → **10623** — reads `data.get("data")[0]` (form field JSON string); **not** in `_JSON_PATHS`; writes inventory + `update_meal_wizard_session({confirmed_inventory, use_soon_items})`; responds `{"ok":true}`.
- `/meal-wizard-step3-save` → **10655** — **IS** in `_JSON_PATHS`; reads raw body via `Content-Length` + `self.rfile.read(...)` + `json.loads`; responds `{"ok":true}`.

```python
            elif path == "/meal-wizard-step2-save":
                import json as _json
                raw = data.get("data",["{}"])[0]
                try:   inv_in = _json.loads(raw)
                except: inv_in = {}
                inv = load_inventory()
                for k in ("fridge","freezer","pantry","use_soon"):
                    if k in inv_in: inv[k] = clean_text(inv_in[k])
                from datetime import date as _date
                inv["last_updated"] = _date.today().isoformat()
                save_inventory(inv)
                _nl = "\n"
                _fridge  = inv.get("fridge","")
                _freezer = inv.get("freezer","")
                _pantry  = inv.get("pantry","")
                _combined = ("Fridge:" + _nl + _fridge + _nl + _nl
                             + "Freezer:" + _nl + _freezer + _nl + _nl
                             + "Pantry:" + _nl + _pantry)
                update_meal_wizard_session({
                    "confirmed_inventory": _combined,
                    "use_soon_items": inv.get("use_soon",""),
                })
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return
```

**Convention for a new Step 4 route, derived from the above:**
1. Add a `elif path == "/meal-wizard-step4-save":` branch in the `do_POST` chain (alongside 10655).
2. If it takes a raw JSON body → **add its path to `_JSON_PATHS`** (line 3536) and read via `Content-Length` + `self.rfile.read(...).decode(...)` + `json.loads` (copy the step3-save pattern). If instead it submits via a form field carrying a JSON string, read `data.get(...)` like step2-save (no `_JSON_PATHS` entry).
3. Persist via `update_meal_wizard_session({...})` (and `save_meal_plan(...)` if it writes the actual plan).
4. Respond with `self.wfile.write(b'{"ok":true}')` guarded by `except BrokenPipeError`.
5. Allowlist-filter every incoming field server-side (step3-save is the model: `_S3_PLAN_KEYS`/`_S3_CX_KEYS` allowlists, `date.fromisoformat` validation, `clean_text` on free text) — don't trust the client.

---

## SUMMARY OF "DOESN'T EXIST / LIVES ELSEWHERE" FLAGS
- **`data/meal_wizard_session.json`** — does not exist (lazily created on first write).
- **Lorenzo Anthropic API call** — in `app.py` (`/lorenzo-chat` handler, ~5867–5888), **not** `render_lorenzo.py`.
- **`_repair_and_parse_json`** — nested/local inside the plan-import handler (app.py:8412), single definition, **unused by Lorenzo**.
- **Model name** — live Lorenzo uses **`claude-haiku-4-5-20251001`**, not the `claude-sonnet-4-20250514` claud.md states.
- **`_JSON_PATHS`** — local to `do_POST` (app.py:3536), not module-level.

_This was diagnosis only — no application files were changed._
