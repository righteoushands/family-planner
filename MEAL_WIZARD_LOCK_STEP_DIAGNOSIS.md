# Meal Wizard — LOCK STEP DIAGNOSIS  ***READ-ONLY · NOTHING CHANGED***

Scoping the future "lock the plan → it shows on the homepage" step. This is a **diagnosis only** — no files were modified. Everything below is pasted **verbatim** from the live code (the `read` tool was used for accuracy; note that the shell `rg` view in this environment masks several tokens such as `load_meal_plan`, `save_meal_plan`, `generated`, and `locked` as the letter `n` — those grep lines are NOT trustworthy and were re-read directly).

---

## 1. CLAUD.MD READ-BACK (Rule 15) + WHICH RULES APPLY TO THE LOCK STEP

### Full rule set, pasted back

**Stack:** Python 3.11; no Flask/Django/FastAPI; data as JSON files in `data/`; no database; frontend = plain HTML/CSS/JS rendered as strings in Python render functions; Anthropic API called directly via `urllib.request` (no SDK).

**People:** Lauren (Mom), John (Dad), JP (14, 9th), Joseph (12, 7th), Michael (5, K), James (13 mo, toddler — cannot be assigned tasks). Always title-case; Mom and Lauren are the same person; James is excluded from school renderers and gradebook.

**Python 3.11 hard rules — never violate:**
1. No backslashes inside f-strings.
2. No nested quotes inside f-strings — use a variable outside the f-string instead.
3. All GET routing uses `elif` chains in `do_GET` — never a bare `if`, never nested if blocks for routing. POST routing in `do_POST` ALSO uses `elif` chains (`elif path == "/route-name": … return`) — verified June 28 2026 against the meal POST handlers and the Route patterns section. The ONE exception is the multipart recipe routes (`/recipe-save`, `/recipe-import`): they share an `elif path in (...)` outer block with nested `if path == ...` inner blocks ONLY to share upload-parsing setup. Do NOT copy that nested pattern for ordinary JSON or form routes. *(CORRECTED June 28 2026: a June 10 note had claimed do_POST uses standalone-if; the live code uses elif chains. Code wins.)*
4. Never put import statements inside if blocks or functions. *(KNOWN DEVIATION, not a license: several live do_POST handlers use an inline `import json as _json`; new code should keep imports at module top.)*
5. All file writes use `safe_save_json` (tmp file + `os.replace`) — never `open(f, 'w')` directly.
6. No walrus operator (`:=`).
7. Never use a raw newline inside a JS string within a Python string literal — use the escaped form so the browser receives the escape sequence, not a raw newline.
8. multipart/form-data parsing: when fetch POSTs use FormData the server receives multipart/form-data not urlencoded. The handler must sniff Content-Type and parse with `cgi.FieldStorage` for multipart. If a POST handler receives empty data, check the Content-Type first.
9. py_compile passes but runtime fails: py_compile only validates syntax. Always run an in-process smoke test after py_compile (catches NameError, missing vars, import failures). After the smoke test, also run the relevant existing `verify_phase_*.py` harness for the area touched and paste the result. Do NOT skip the harness for changes that touch shared data files, save paths, or any function called from more than one place.
10. Test fixtures must never write to live data: harnesses must operate on a temp copy; never call `save_progress`, `safe_save_json`, or any write helper on live data during testing; always restore from backup after any test that touches data files.
11. Double-escaping HTML entities: never pass an already-escaped string through `escape()` again. Use plain ampersands in source and let `escape()` handle it once.
12. JS-newline rule (7) applies to ALL files containing JS embedded in Python — `render_schedule.py`, `render_timeblock.py`, `render_lucy.py`, `render_lorenzo.py`, and any other render file with inline JavaScript.

**Data file patterns:** most data in `data/*.json` as flat dicts/lists; person keys title-case in `progress.json`, `chores.json`, `events.json`; lowercase in `auth/pins.json` and `profiles/`; progress keys compound `"YYYY-MM-DD::Person::task text"`; date keys `YYYY-MM-DD` (most), **`YYYY-Www` (meal_plan)**, `YYYY-MM` (cycle).

**Route patterns:** GET routes call `render_*.py` returning HTML strings; POST routes live in `app.py do_POST`, chained as `elif path == "/route-name":`; JSON POST bodies must be registered in the `_JSON_PATHS` set or the form-parser will consume the payload silently — **`_JSON_PATHS` is a LOCAL set defined inside `do_POST` (app.py ~3536)**, not module-level; new JSON-body routes must be added to it.

**Anchor-tag navigation:** plain `<a href>` cannot POST or mutate server state; state must travel in the query string OR be persisted before the click; if a button must trigger persistent state, use a `<form method="POST">` styled as a link.

**AI calls:** model NOT uniform; Lorenzo uses `claude-haiku-4-5-20251001`; the old `claude-sonnet-4-20250514` is stale/unverified — confirm per call. Called via `urllib.request`, key from `app_settings.json`. `_repair_and_parse_json()` is a nested local in the plan-import handler ONLY; Lorenzo does not use it.

**Change discipline:** all changes additive unless told otherwise; never delete/modify existing behavior unless the task requires it; if a task needs editing an out-of-scope file, stop and flag; keep modules under 800 lines where possible; `render_plan_importer.py` JS lives in `static/js/plan_importer_*.js`.

**FROL Wizard form-bypass trap:** `_section_chrome` suppresses Save&Continue when `_body_has_form` detects `action="/frol-wizard"` in the body; utility forms posting to other routes are safe.

**Additional rules 13–19:**
13. FROL wizard nested-form addendum — confirm a section-body form's `action` before adding; forms posting to `/frol-wizard` suppress Save&Continue; `/frol-set-variant` and `/frol-add-activity` are safe.
14. PRE-FLIGHT CHECKLIST — before writing any spec answer: (1) how many files does this touch, list them (if unknown, diagnose first); (2) does it involve JS inside Python f-strings (if yes, flag the backslash-n rule); (3) does it touch form handling (if yes, confirm no nested forms posting to `/frol-wizard`); (4) is the root cause confirmed or assumed (if assumed, diagnose first); (5) does it touch multiple files (if yes, break into single-purpose instructions); (6) does it involve data-shape changes/migration (if yes, confirm before/after shape explicitly).
15. CLAUD.MD READ-BACK REQUIRED — at session start read claud.md and paste back every rule, then identify which apply; if you can't paste accurately, stop and ask Lauren to re-paste.
16. MAGNIFICA HUMANITAS DESIGN PRINCIPLES — the app is a tool not an authority (suggestions never prescriptions; "here is one way to think about this," never "you should"/"optimal"); companions serve real relationships, never replace them; AI supports thinking, doesn't replace it (ask before suggesting); be transparent about what AI is; never quietly assume a decision that belongs to Lauren; prayer texts from verified Catholic sources only; language of grace not performance — no gamification, streaks, or shaming scores; a hard day is never failure; subsidiarity — the family governs itself, Lauren is always the authority; formation in digital wisdom (JP should finish high school able to plan his day without the app).
17. ONE FIX PER INSTRUCTION — never bundle multiple fixes unless same file and directly related; complex multi-file builds broken into sequential single-purpose phases with a compile check and report between each.
18. AUGUST 15TH BUILD PLAN IS THE PRIORITY FILTER — between June 1 and Aug 15 2026 every build is checked against the Aug-15 plan; off-plan ideas get flagged to Lauren / deferred; scope is the first thing to cut, not quality.
19. BUILD FOR A FUTURE SECOND FAMILY — write every feature as if a second family will use it; never hardcode the family's specifics (keep identity/config in `app_settings.json`); keep all reads/writes flowing through `data_helpers.py` with no direct file access in route handlers. *(KNOWN DEBT June 28 2026: `build_lorenzo_context` hardcodes the roster; new Step 4 / Lorenzo work must not deepen this.)*

### Which rules APPLY to a step that writes confirmed wizard meals into the meal store and surfaces them on the homepage

- **Rule 5 (safe writes)** — the lock MUST persist via `save_meal_plan` → `safe_save_json`; never write the plan file directly.
- **Rule 3 + Route patterns + `_JSON_PATHS`** — the lock is a state-mutating POST, so it must be an `elif path == "/…": … return` branch in `do_POST`, and if its body is JSON it must be added to the LOCAL `_JSON_PATHS` set (~app.py 3536). A plain `<a href>` cannot perform the lock (Anchor-tag rule).
- **Rule 6 (data-shape change)** — the lock copies session `confirmed_meals` (keyed `"YYYY-MM-DD::slot"`) INTO the plan's `days[Weekday][slot]` shape; the before/after shapes (and the slot-name mapping, see §4) must be stated explicitly before building.
- **Rule 9 + 10 (test discipline)** — the meal plan is read from MANY call sites (§6) and written through a shared save path, so an in-process smoke test PLUS the meal-plan/homepage harness are mandatory, on temp copies only, restored after.
- **Rule 1/2/7/11/12 (render hygiene)** — only if the lock step renders any HTML/JS (e.g. a confirmation card on the homepage); the homepage meal card already embeds JS, so Rule 7/12 apply to any edit there, and every dynamic meal name must be escaped exactly once (Rule 11).
- **Rule 16 (Magnifica Humanitas)** — the locked plan is Lauren's committed plan, not an optimizer's verdict; copy must read as her choice ("Your plan is set"), no streaks/scores, and the lock must not silently overwrite an existing hand-edited plan without her say-so (don't assume a decision that's hers).
- **Rule 17 (one fix)** — "lock writes the store" and "homepage surfaces it" are directly related and may be one phase, but anything beyond that (e.g. un-lock, edit-after-lock) is a separate phase.
- **Rule 18 (Aug-15 filter)** — the Meal Wizard is on the must-build path, so this is in-scope.
- **Rule 19 (second family)** — reads/writes flow through `render_meals` helpers / `data_helpers`; no hardcoded family specifics in the lock or the card.
- **Rule 14 (pre-flight)** — must be answered when the lock spec is written.
- **Rules that do NOT apply:** 8 (no multipart — this is a JSON/form POST), 13 (no FROL section-body form), 4 inline-import deviation (new code keeps imports at top).

---

## 2. STORE SHAPE / CONSTANTS (verbatim)

### `MEAL_SLOTS` and `DAYS` — they live in **`render_meals.py`**, NOT `config.py`

> `config.py` line 74 defines only `SCHEDULE_DAYS = ["Monday", … "Saturday"]` (Mon–Sat) — that is the **schedule** day list, **not** the meal-store day list. The meal store's `DAYS`/`MEAL_SLOTS` are defined exclusively in `render_meals.py`:

```python
# render_meals.py
DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

MEAL_SLOTS = ["breakfast","lunch","dinner","dessert","snacks","dad_lunch"]
MEAL_SLOT_SET = set(MEAL_SLOTS)

MEAL_SLOT_LABELS = {
    "breakfast": "Breakfast",
    "lunch":     "Lunch",
    "dinner":    "Dinner",
    "dessert":   "Dessert",
    "snacks":    "Snacks",
    "dad_lunch": "Dad's Lunch",
}
```

### `_plan_path`, `_week_key`, `_planning_week_key`, `_week_start` (all verbatim)

```python
# render_meals.py
def _plan_path(week_key: str) -> str:
    os.makedirs(MEALS_DIR, exist_ok=True)
    return f"{MEALS_DIR}/{week_key}.json"

def _week_key(for_date: date = None) -> str:
    d = for_date or date.today()
    # Use Monday of the week as canonical key (e.g. 2026-04-06)
    monday = d - timedelta(days=d.weekday())
    return monday.isoformat()

def _planning_week_key(for_date: date = None) -> str:
    """The Monday key Lauren is most likely actively PLANNING right now.
    Mon–Thu → this week's Monday.  Fri/Sat/Sun → next week's Monday.
    This must mirror the default in render_meal_print_page so that Lorenzo's
    saved edits land on the same file the fridge card displays."""
    d = for_date or date.today()
    if d.weekday() >= 4:  # Fri=4, Sat=5, Sun=6
        return (d + timedelta(days=(7 - d.weekday()))).isoformat()
    return _week_key(d)

def _week_start(for_date: date = None) -> date:
    d = for_date or date.today()
    return d - timedelta(days=d.weekday())  # Monday
```

> `MEALS_DIR = "data/meal_plan"`. So a plan file is `data/meal_plan/<week_key>.json`.

### `_backup_meal_plan` (verbatim)

```python
# render_meals.py
def _backup_meal_plan(week_key: str) -> None:
    """Snapshot the existing plan file (if any) into data/meal_plan/.backups/
    before it gets overwritten. Keeps the last 30 versions per week so we can
    recover from a bad save (Lorenzo wiping a slot, accidental clear, etc.)."""
    try:
        import shutil, datetime as _dt
        src = _plan_path(week_key)
        if not os.path.exists(src):
            return
        backup_dir = f"{MEALS_DIR}/.backups"
        os.makedirs(backup_dir, exist_ok=True)
        # Microseconds + random suffix → collision-proof when Lorenzo emits
        # multiple [MEAL_UPDATE] tags in one reply (each triggers a save).
        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        import uuid as _uuid
        dst = f"{backup_dir}/{week_key}__{ts}-{_uuid.uuid4().hex[:6]}.json"
        shutil.copy2(src, dst)
        # Rotate per-week: keep last 30 backups for this week_key
        try:
            prefix = f"{week_key}__"
            entries = sorted(
                [f for f in os.listdir(backup_dir) if f.startswith(prefix) and f.endswith(".json")],
                reverse=True,
            )
            for old in entries[30:]:
                try:
                    os.remove(os.path.join(backup_dir, old))
                except Exception:
                    pass
        except Exception:
            pass
    except Exception as _e:
        print(f"[backup_meal_plan] failed for {week_key}: {_e}")
```

### Confirmation: keying & day-key scheme

**YES — the meal plan is keyed ONLY by the Monday-of-week ISO date, with day sub-keys by weekday NAME ("Monday".."Sunday").** Evidence (all verbatim):

- The canonical key is the Monday ISO date — `_week_key` returns `monday.isoformat()` (e.g. `2026-04-06`), and `_plan_path` makes the filename `data/meal_plan/<that-Monday>.json`.
- The default plan shape and day keys (`load_meal_plan`, verbatim):

```python
# render_meals.py — load_meal_plan
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
    # Plans are saved keyed on the Monday ISO date, so any other day in the
    # same week should resolve to the same plan.
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

**Date-keyed variant?** There is **no `YYYY-MM-DD`-per-day plan file**. The store is always one file per **week** named by the Monday ISO date, and the days inside are keyed by weekday NAME. There are TWO legacy/compat key *forms* the loader will still resolve (but does NOT newly write):
1. A non-Monday ISO date passed as the key → resolved to that week's Monday file.
2. The old `"%Y-W%W"` form (e.g. `2026-W14`) — matches claud.md's note that meal_plan date keys are `YYYY-Www`. The loader still reads these if present; new saves use the **Monday ISO date** (see §7).

So: **canonical = Monday-ISO-date file → `days[<WeekdayName>][<slot>]`.** A lock step should follow exactly this.

---

## 3. SLOT VALUE FORMAT (relevant to what the homepage renders)

A slot value can be a plain string OR a dict `{"display": ..., "recipe_id": ...}`. Every reader goes through these accessors (verbatim):

```python
# render_meals.py
def slot_display_text(value) -> str:
    """Return the user-facing meal text for a slot value.
    Accepts plain string, dict {'display','recipe_id'}, None, or anything
    else.  Always returns a stripped str ('' if there's nothing to show)."""
    if isinstance(value, dict):
        return str(value.get("display", "") or "").strip()
    if value is None:
        return ""
    return str(value).strip()

def slot_recipe_id(value):
    """Return the linked recipe_id (str) for a slot value, or None."""
    if isinstance(value, dict):
        rid = value.get("recipe_id")
        if rid:
            rid = str(rid).strip()
            return rid or None
    return None
```

---

## 4. WHICH WIZARD SESSION SLOTS HAVE A STORE HOME

The store's slot vocabulary is fixed: **`MEAL_SLOTS = ["breakfast","lunch","dinner","dessert","snacks","dad_lunch"]`**. Mapping the wizard's requested slots against it:

| Wizard slot   | Exists in store `MEAL_SLOTS`? | Note |
|---------------|-------------------------------|------|
| `breakfast`   | **YES** (`breakfast`)         | direct |
| `lunch`       | **YES** (`lunch`)             | direct |
| `dinner`      | **YES** (`dinner`)            | direct |
| `snacks`      | **YES** (`snacks`)            | direct |
| `dessert`     | **YES** (`dessert`)           | direct |
| `johns_lunch` | **NO** (no `johns_lunch` key) | Store has **`dad_lunch`** (labeled "Dad's Lunch"). `johns_lunch` is *conceptually* the same thing but is **NOT** a store key — a lock step must map `johns_lunch → dad_lunch` (decision belongs to Lauren / the spec). |
| `feast_meal`  | **NO**                        | No store slot. Has no home in `days[…]`. The store cannot hold it as a slot today. |
| `batch_cook`  | **NO**                        | No store slot. Has no home in `days[…]`. The store cannot hold it as a slot today. |

**Plain statement:** five wizard slots (`breakfast`, `lunch`, `dinner`, `snacks`, `dessert`) map 1:1 to store slots. `johns_lunch` has **no identical key** — the nearest store slot is `dad_lunch` and would require an explicit mapping decision. `feast_meal` and `batch_cook` have **NO store home at all** — the current `MEAL_SLOTS`/`days` shape cannot hold them as slots, so a lock step must either (a) drop them, (b) fold them into an existing slot, or (c) store them outside `days[…]` (e.g. a separate plan key). That is a decision for the lock spec, not an assumption.

---

## 5. HOMEPAGE DISPLAY — what "shows on the homepage" actually requires

The homepage meal card is built by `_render_meals_snapshot` (which calls `_render_meal_row`) in **`render_timeblock.py`**.

### `_render_meals_snapshot` (verbatim) — the loader, week key, and slot selection

```python
# render_timeblock.py
def _render_meals_snapshot(weekday: str, today: date, block: str) -> str:
    try:
        from render_meals import load_meal_plan
        monday = today - timedelta(days=today.weekday())
        wk = monday.isoformat()
        plan = load_meal_plan(wk) or {}
        if block == "late_evening":
            tomorrow = today + timedelta(days=1)
            day_meals = (plan.get("days", {}) or {}).get(tomorrow.strftime("%A"), {}) or {}
        else:
            day_meals = (plan.get("days", {}) or {}).get(weekday, {}) or {}
    except Exception:
        day_meals = {}
    rows = []
    for key, label in _meal_keys_for_block(block):
        rows.append(_render_meal_row(label, day_meals.get(key)))
    return _card(f"Meals — {_BLOCK_LABELS.get(block, block)}",
                 "".join(rows) +
                 '<div style="text-align:right;margin-top:10px;">'
                 '<a href="/lorenzo" style="color:#2d4a78;font-size:0.85em;'
                 'text-decoration:none;">Talk to Lorenzo &rarr;</a></div>')
```

**Which week key:** **TODAY's week** — `monday = today - timedelta(days=today.weekday())` → `wk = monday.isoformat()`. **NOT `_planning_week_key`** (so on Fri/Sat/Sun the homepage shows the *current* week, while the planner default points at *next* week). **A lock step that wants its plan to appear on the homepage immediately must write to the file for TODAY's Monday** (or the user must be viewing the week that was locked).

**What it shows:** only the slots returned by `_meal_keys_for_block(block)` — i.e. a small, time-of-day subset (verbatim):

```python
# render_timeblock.py
def _meal_keys_for_block(block: str) -> list:
    ...
        return [("breakfast", "Breakfast"), ("lunch", "Lunch (prep)")]
    ...
        return [("lunch", "Lunch"), ("dinner", "Dinner (prep)")]
    ...
        return [("dinner", "Dinner")]
    return [("breakfast", "Tomorrow's breakfast (prep)")]
```

So the card is **per-day and per-block** (today's relevant meals; `late_evening` shows *tomorrow's* day), NOT the whole week, and it only surfaces `breakfast`/`lunch`/`dinner` (never `dessert`/`snacks`/`dad_lunch` on this card).

### `_render_meal_row` (verbatim) — the gate, and the empty state

```python
# render_timeblock.py
def _render_meal_row(label: str, slot_value) -> str:
    try:
        from render_meals import slot_display_text, slot_recipe_id
        from data_helpers import get_recipe_by_id
    except Exception:
        slot_display_text = lambda v: (str(v).strip() if isinstance(v, str) else "")
        slot_recipe_id    = lambda v: None
        get_recipe_by_id  = lambda r: None

    name = slot_display_text(slot_value)
    if not name:
        return (
            f'<div style="padding:8px 0;border-bottom:1px dashed #e4eaf3;">'
            f'<div style="font-size:0.78em;text-transform:uppercase;'
            f'letter-spacing:0.06em;color:{_accent()};font-weight:700;">'
            f'{escape(label)}</div>'
            f'<div style="font-size:0.88em;color:#999;font-style:italic;'
            f'margin-top:4px;">No meal planned &middot; '
            f'<a href="/lorenzo" style="color:#2d4a78;text-decoration:none;'
            f'font-style:normal;">ask Lorenzo to plan one &rarr;</a></div>'
            f'</div>'
        )
    ...
```

**Does it gate on `generated` or any `locked` flag?** **NO.** `_render_meals_snapshot` and `_render_meal_row` read `plan["days"][weekday][slot]` and branch ONLY on whether `slot_display_text(value)` is non-empty. An un-`generated` plan renders **identically** — if a slot has text it shows; if not it shows "No meal planned." **Therefore: for the wizard's locked meals to appear on the homepage, the lock only needs to write the meal NAME (string or `{"display":…}`) into `plan["days"][<Weekday>][<store_slot>]` for the right week file. Setting `generated`/any lock flag is NOT required for the card to render.** (The card never reads those flags.)

---

## 6. LOCK / GENERATED SEMANTICS + `load_meal_plan` CALL SITES

### `generated` — where written, where read, who branches

- **Default:** set `False` on a fresh plan — `"generated": False` in `load_meal_plan`'s `default` (see §2).
- **Written `True` in exactly one place:** the `/meal-generate` POST handler (the AI generator), verbatim:

```python
# app.py — /meal-generate handler
                    # Save plan
                    plan = load_meal_plan(wk)
                    plan["days"]          = days_out
                    plan["grocery_gaps"]  = grocery_gaps
                    plan["prep_notes"]    = prep_notes
                    plan["use_soon_used"] = use_soon_used
                    plan["generated"]     = True
                    plan["week"]          = wk
                    plan["start"]         = wk
                    save_meal_plan(plan)
```

- **One other write of the flag** is in an unrelated builder that initializes a plan dict with `"generated": False` (app.py ~5563): `_mpdata = {"week": _mpweek, "generated": False, "days": { …`.
- **Read / branched on:** only by **Lorenzo's context builder** for informational text (verbatim):

```python
# render_lorenzo.py
        _was_generated = "YES — by the AI generator" if plan.get("generated") else "no — manually edited or empty"
        ...
        f"  Last saved to disk: {_saved}.  AI-generated: {_was_generated}.",
```

**Net:** `generated` means "this plan was produced by the AI generator." It is **purely informational** — nothing in rendering or scheduling gates on it. The manual editor save path (`/meal-save-plan`, §7) does **NOT** set it, so manually-saved plans keep `generated=False`.

### `locked` — there is NO meal-plan `locked` flag

A repo scan for `locked` in meal context returns **only** Meal-Wizard *session* entries (each confirmed meal carries a per-entry `locked: true` in `meal_wizard_session.json`) and the masked grep noise. **The meal *plan* store has no `locked` key anywhere** — not in the default shape, not written, not read. So "lock the plan" is a NEW concept at the plan level; if the spec wants a persisted lock flag on the plan, it would be a new key (Rule 6 data-shape change) and a new reader would be needed for anything to branch on it. Today, nothing does.

### Every `load_meal_plan` call site (so a lock write is seen consistently)

The store is read from many views. A lock that writes `days[…]` into the canonical week file will be picked up by ALL of these (they all go through `load_meal_plan`):

- **app.py** — inside `/meal-save-plan`, `/meal-generate`, `/meal-save-constraints`, `/meal-edit`, and other meal POST handlers (multiple call sites).
- **render_meals.py** — its own page renderers (planner/print/today card).
- **render_timeblock.py** — `_render_meals_snapshot` (the homepage card, §5).
- **render_lorenzo.py** — Lorenzo's context + meal-edit flows.
- **render_ai_daily.py** — daily AI summary.
- **render_lucy.py** — Lucy's meal awareness (current week).
- **render_plan_tomorrow.py** — tomorrow's plan.
- **render_plan_week.py** — the week plan view.
- **render_misc.py** — a meal listing.
- **render_schedule.py** — schedule integration (today + target date).
- **render_mom_profile.py** — Mom profile meal card.
- **daily_schedule_engine.py** — schedule build, cook-start, and prep-notes lookups (uses the Monday `.isoformat()` key directly).

**Implication for the lock:** because every consumer resolves through `load_meal_plan` and the Monday-ISO week file, a single correct write to `days[<Weekday>][<store_slot>]` in the right week file is **automatically consistent** across all of them. The only divergence to watch is the **week key**: the homepage card uses **today's** Monday, while the planner/Lorenzo often default to **`_planning_week_key`** (next week on Fri–Sun). The lock spec must pick the week deliberately so "shows on the homepage" is true for the week Lauren expects.

---

## 7. CANONICAL WRITE PATH (so the lock matches convention)

There are **two** existing writers, both ending in `save_meal_plan` → `safe_save_json`. The lock should mirror these.

### `save_meal_plan` (verbatim) — the single persistence function

```python
# render_meals.py
def save_meal_plan(plan: dict):
    # Use "start" (ISO date) as primary key; fall back to "week" for old plans
    key = plan.get("start") or plan.get("week", date.today().isoformat())
    _backup_meal_plan(key)  # snapshot prior version BEFORE overwriting
    safe_save_json(_plan_path(key), plan)
```

> The save key is `plan["start"]` (then `plan["week"]`). So a writer should set BOTH `plan["start"]` and `plan["week"]` to the Monday-ISO week key before calling `save_meal_plan`, exactly as the existing handlers do.

### The existing MANUAL editor save — `/meal-save-plan` POST handler (verbatim)

> NOTE: `render_meal_planner_page` (render_meals.py line 584) only **renders** the editor grid (the form/inputs); it does **not** save. The actual `days{Day}{slot}=name` write lives in `app.py`'s `/meal-save-plan` POST handler:

```python
# app.py — /meal-save-plan
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

### Confirmation for the lock step

- **Same shape, same path: YES.** A lock should `plan = load_meal_plan(<week>)`, write each confirmed meal into `plan["days"][<WeekdayName>][<store_slot>] = <name>` (plain string, or `{"display":…, "recipe_id":…}` if a recipe is attached — both are valid per the slot accessors in §3), set `plan["week"]` and `plan["start"]` to the Monday-ISO key, then call **`save_meal_plan(plan)`** (which auto-backs-up). This is exactly the `/meal-save-plan` convention.
- **Should it set `generated=True`?** Convention says **no** — the manual editor (`/meal-save-plan`) does NOT set `generated`; only the AI generator does. A wizard lock is a *manual/confirmed* plan, so leaving `generated=False` matches convention, and (per §5) it is irrelevant to the homepage card anyway. Setting `generated=True` would mislabel a human-built plan as AI-generated in Lorenzo's context (§6). **Recommendation to surface in the spec: do NOT set `generated`.**
- **Should it set a `locked` flag?** Today there is **no plan-level `locked`** key and nothing reads one (§6). The homepage does not need it. If Lauren wants a persisted "this week is locked" marker (e.g. to show a badge or prevent overwrite), that is a **new data-shape addition (Rule 6)** plus a **new reader** — a deliberate decision for the spec, not required for "it shows on the homepage."
- **Week-key choice (the real correctness risk):** to satisfy "shows on the homepage," write to the **homepage's** week = **today's Monday** (`today - weekday`), since `_render_meals_snapshot` ignores `_planning_week_key`. If the wizard is planning *next* week, the homepage won't show it until that week is current — the spec must state which week the wizard is locking and confirm it matches what Lauren expects to see on the homepage.
- **Slot vocabulary (the other risk):** only the five direct slots + a `johns_lunch → dad_lunch` mapping land cleanly; `feast_meal` and `batch_cook` have no `days[…]` home (§4) and need an explicit decision.

---

## SUMMARY (one-paragraph map for the future lock spec)

The meal store is **one JSON file per week** at `data/meal_plan/<Monday-ISO>.json`, shaped `{start, week, generated, days: {<WeekdayName>: {<slot>: ""}}}` with `MEAL_SLOTS = breakfast, lunch, dinner, dessert, snacks, dad_lunch` and `DAYS = Monday…Sunday` (both defined in `render_meals.py`, **not** `config.py`). The canonical write is `load_meal_plan(week) → mutate plan["days"][Weekday][slot] → set plan["start"]=plan["week"]=Monday-ISO → save_meal_plan(plan)` (which backs up + `safe_save_json`), exactly as the manual `/meal-save-plan` handler does. The homepage card (`render_timeblock._render_meals_snapshot`/`_render_meal_row`) reads **today's-Monday** week file and shows only the block's `breakfast`/`lunch`/`dinner` for the day, **gating on nothing but non-empty slot text** — so a lock only needs to write meal names into the right week's `days[Weekday][slot]`; it does **not** need `generated` or a `locked` flag (no such plan-level `locked` exists, and `generated` is informational, set only by the AI generator). The risks to nail down in the spec: (1) write to the **week the homepage shows** (today's Monday, not `_planning_week_key`); (2) map `johns_lunch → dad_lunch` and decide what to do with `feast_meal`/`batch_cook` (no store home); (3) leave `generated=False` to match manual-save convention; (4) follow Rules 5, 3/`_JSON_PATHS`, 6, 9/10, 16, 19 when building. **Nothing was changed by this diagnosis.**
