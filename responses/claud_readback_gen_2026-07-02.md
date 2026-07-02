# Rule 15 read-back + render_meal_wizard_gen.py (2026-07-02)

---

## claud.md — all rules, pasted back verbatim

### Python 3.11 hard rules

**1.** No backslashes inside f-strings.

**2.** No nested quotes inside f-strings — use a variable outside the f-string instead.

**3.** All GET routing uses `elif` chains in `do_GET` — never a bare `if`, never nested
`if` blocks for routing. POST routing in `do_POST` ALSO uses `elif` chains
(`elif path == "/route-name": … return`) — verified June 28 2026 against the meal
POST handlers and the Route patterns section. The ONE exception is the multipart recipe
routes (`/recipe-save`, `/recipe-import`): they share an `elif path in (...)` outer
block with nested `if path == ...` inner blocks ONLY to share upload-parsing setup. Do
NOT copy that nested pattern for ordinary JSON or form routes — match the plain `elif`
chain.
[CORRECTED June 28 2026: a June 10 note had claimed `do_POST` uses "standalone `if`
blocks at the top level." The live code uses `elif` chains.]

**4.** Never put import statements inside `if` blocks or functions.
[KNOWN DEVIATION, not a license: several live `do_POST` handlers use an inline
`import json as _json` etc. New code should keep imports at module top; when editing an
existing handler, be aware the local convention already deviates.]

**5.** All file writes use `safe_save_json` (tmp file + `os.replace`) — never
`open(f, 'w')` directly.

**6.** No walrus operator (`:=`).

**7.** Never use `'\n'` inside a JS string within a Python string literal — use `'\n'`
so the browser receives the escape sequence, not a raw newline.

**8.** multipart/form-data parsing: when `fetch` POSTs use `FormData` the server
receives `multipart/form-data` not urlencoded. The `do_POST` handler must sniff
`Content-Type` and parse accordingly using `cgi.FieldStorage` for multipart. If a POST
handler receives empty data check the `Content-Type` first.

**9.** `py_compile` passes but runtime fails: always run an in-process smoke test after
`py_compile` to catch `NameError`, missing variable definitions, and import failures.
After the in-process smoke test, also run the relevant existing `verify_phase_*.py`
harness for the area touched and paste the result — the smoke test confirms the changed
function works, but the harness catches regressions in nearby functionality. Do not skip
the harness run for changes that touch shared data files, save paths, or any function
called from more than one place.

**10.** Test fixtures must never write to live data: verification harnesses must always
operate on a temp copy of live data files. Never call `save_progress`, `safe_save_json`,
or any write helper on live data during testing. Always restore from backup after any
test that touches data files.

**10a.** RULE 10 ADDENDUM — ISOLATION MUST BE STRUCTURAL, NOT PROCEDURAL. Any
`verify_*.py` harness that reads or writes app data must import its isolation guard
(`e.g. mw_test_isolation.assert_isolated`) as the literal first import in the file —
before `data_helpers`, `config`, or any `render_*.py` module. The guard must be called
before the first write, and must raise (not warn) if the write target still resolves to a
live path. A harness that skips this ordering is non-compliant with Rule 10 regardless of
whether it happens to include snapshot/restore logic — snapshot-and-restore-after is not
equivalent to never touching live data. When isolating a new data store beyond the meal
wizard, extend the existing isolation module's pattern (env-var override, defense-in-depth
path normalization, `assert_isolated`) rather than writing a new one-off mechanism per
feature.

**11.** Double-escaping HTML entities: never pass a string that is already HTML-escaped
through `escape()` again. If a string contains literal ampersands for display use plain
ampersands in the source string and let `escape()` handle it once. Strings pre-escaped
with `&amp;` will render as visible `&amp;` in the browser if escaped again.

**12.** JS newline in Python f-strings applies everywhere: Rule 7 (never use `\n` in JS
strings inside Python f-strings) applies to ALL files containing JS embedded in Python,
not just `render_frol_wizard.py`. This includes `render_schedule.py`,
`render_timeblock.py`, `render_lucy.py`, `render_lorenzo.py`, and any other render file
with inline JavaScript.

---

### Additional rules (13–22)

**13.** FROL WIZARD NESTED FORM ADDENDUM — The `_body_has_form` check in
`_section_chrome` looks for `action="/frol-wizard"` in the body string. Any form inside
a section body posting to `/frol-wizard` will suppress the Save and Continue button.
Variant tab forms posting to `/frol-set-variant` are safe. Activity builder forms posting
to `/frol-add-activity` are safe. Before adding any form to a section body confirm its
`action` attribute. This is a recurring bug — document before fixing if it appears again.

**14.** PRE-FLIGHT CHECKLIST — Before writing any spec answer these questions.
1. How many files does this touch, list them; if unknown that is a diagnosis step first.
2. Does it involve JavaScript inside Python f-strings — if yes flag the `\n` rule
   explicitly in the spec.
3. Does it touch form handling — if yes confirm no nested forms posting to `/frol-wizard`.
4. Is the root cause confirmed or assumed — if assumed run diagnosis first, never draft a
   fix on an assumed cause.
5. Does it touch multiple files at once — if yes break into separate single-purpose
   instructions.
6. Does it involve data shape changes or migration — if yes confirm before and after data
   structure explicitly before writing the spec.

**15.** CLAUD.MD READ-BACK REQUIRED — At the start of every session read `claud.md` and
paste back every rule found. Then identify which rules apply to today's task. If you
cannot paste the rules back accurately stop and ask Lauren to re-paste `claud.md` before
proceeding.

**16.** MAGNIFICA HUMANITAS DESIGN PRINCIPLES — Every feature must reflect these. The
app is a tool not an authority; companions serve real relationships, never replace them;
AI supports thinking, it does not replace it; be transparent about what AI is; language
of grace not performance (no gamification, streaks, or shaming); subsidiarity — Lauren is
always the authority; formation in digital wisdom (JP finishes high school able to plan
his day without the app). Every feature must answer yes to at least one: does it help the
family remain faithful to the truth; does it help them learn and teach one another; does
it help them cultivate real closeness; does it help them live justice and peace in their
home.

**17.** ONE FIX PER INSTRUCTION — Never bundle multiple fixes into one Agent instruction
unless they are in the same file and directly related. Complex multi-file builds must be
broken into sequential single-purpose phases with a compile check and report between each
phase.

**18.** AUGUST 15TH BUILD PLAN IS THE PRIORITY FILTER — Between June 1 and August 15
2026 every build request must be checked against the August 15th build plan before
proceeding. If a requested build is not on the must-have or should-have list for the
current week, flag it to Lauren before starting. New feature ideas go on the
post-September list unless they directly enable one of the 14 goals. Scope is the first
thing to cut, not quality.

**19.** BUILD FOR A FUTURE SECOND FAMILY — Never hardcode McAdams or any single
family's specifics into code. Keep family identity and config in `app_settings.json`.
Keep all data reads and writes flowing through `data_helpers.py` with no direct file
access in route handlers. Do not bake in single-user assumptions in new feature logic
where it is cheap to avoid them.
[KNOWN DEBT, flagged June 28 2026: `build_lorenzo_context` in `render_lorenzo.py`
hardcodes the family roster. New Step 4 / Lorenzo work must NOT deepen this; ideally
route the roster through `data_helpers`.]

**20.** PRESERVE SCROLL ON SAME-PAGE RELOADS — Any `fetch()` POST that on success
navigates via `window.location.href` to the SAME page MUST save `window.scrollY` to
`sessionStorage` immediately before setting `window.location.href`, then on the next page
load restore the position with `window.scrollTo` and clear the `sessionStorage` key.
Forward navigations to a different page/step are exempt. `render_meal_wizard_step4.py` is
the reference implementation. Keep this client-side only; obey Rules 7 & 12.

**21.** SESSION HELPER SHALLOW-MERGE — `update_meal_wizard_session` (and any
`load → dict.update → save` session helper) merges ONLY at the top level. Passing a whole
nested key such as `{"suggested_meals": {...}}` REPLACES that entire nested dict, silently
dropping sibling inner keys. To preserve siblings: read the current value FRESH,
`.update()` the new keys onto it, then write the merged dict. Read that snapshot
immediately before the write — not before a long-running step (e.g. a ~90s AI call) — or
a concurrent write landing mid-call is clobbered by the stale snapshot.
[KNOWN DEVIATION, logged July 1 2026: this bit the Step 4 confirm-mirror —
`/meal-wizard-generate` wrote `{"suggested_meals": _g_suggestions}` and wiped the mirror
entries for confirmed slots. Fixed by fresh-read + merge in the generate handler.]

**22.** MERGE-BASED GENERATE NO LONGER PRUNES — Because `/meal-wizard-generate` now
merges into `suggested_meals` instead of replacing it, stale entries (slots dropped from
`confirmed_what_to_plan`, or past-date keys) are never pruned and accumulate in the
session file. Render is gated — readers look up `suggested[date::slot]` only for dates in
the planning window × slots in `confirmed_what_to_plan`, so stale entries are inert —
EXCEPT a stale `date::slot` that later re-enters window×to_plan while unconfirmed will
resurface its old suggestion as a prefill. Low severity; logged not fixed. If addressed,
prune keys outside window×to_plan in the generate handler rather than reverting to
wholesale replace.

---

### Other claud.md sections of note

**AI calls:** Model is NOT uniform. Lorenzo's live call uses `claude-haiku-4-5-20251001`
(verified June 28 2026). `claude-sonnet-4-20250514` is STALE/UNVERIFIED — confirm per
call. Called via `urllib.request` directly; API key from `app_settings.json`.

**`_repair_and_parse_json()` is NOT universal** — nested local function inside
plan-import handler only (`app.py ~8412`). Lorenzo does not use it.

**Anchor-tag navigation:** plain `<a href>` cannot POST or mutate state. State must
travel in the URL or be persisted before the click; use `<form method="POST">` styled as
a link if mutation is needed.

**Change discipline:** all changes are additive unless explicitly told otherwise. Never
delete or modify existing behavior unless the task specifically requires it. If a task
requires editing a file not in the stated scope, stop and flag it. Known-issues tracking
lives OUTSIDE the repo in Lauren's dated `TRACKER_Known_Issues_YYYY-MM-DD.txt`.

---

## Which rules apply to today's task

*(You haven't stated today's specific task yet — these are the rules that activate for
any work touching `render_meal_wizard_gen.py` or the Lorenzo generation system.)*

| Rule | Why it applies |
|---|---|
| **1** | `build_wizard_meal_prompt` builds a big multi-line string — any f-string in it must obey |
| **2** | Same — nested quote hazard in prompt lines if f-strings are added |
| **4** | Module-level imports only; no imports inside functions |
| **5** | Any new file write (new harness, new session write) must use `safe_save_json` |
| **6** | No `:=` anywhere |
| **9** | Compile check + in-process smoke test required after any edit |
| **10 / 10a** | Any new harness touching `meal_wizard_session.json` must use `mw_test_isolation` as first import |
| **14** | Pre-flight checklist before writing a spec |
| **17** | One fix per instruction; no multi-file bundles |
| **18** | August 15 priority filter — confirm the work is on the must-have/should-have list |
| **19** | No hardcoded family specifics; family facts stay in `app_settings.json` / `data_helpers` |
| **21** | Any write to `suggested_meals` must read-fresh + merge, not wholesale replace |
| **22** | Awareness that stale suggested_meals entries accumulate; prune in the generate handler if addressed |

Rules **13** (FROL form bypass), **15** (read-back — done ✅), **16** (Magnifica — design
review), **20** (scroll preservation — client-side JS only) are standing rules;
**13** / **20** are dormant for pure gen-module / prompt work.

---

## render_meal_wizard_gen.py — complete file (241 lines)

```python
"""Meal Wizard — Lorenzo week-generation data contract (G1c-1a / G1c-1b).

Pure, deterministic logic plus the generation prompt builder:
  1. wizard_target_slot_keys  — which empty "YYYY-MM-DD::slot" keys the
     generator should fill, never touching an already-confirmed meal (Rule 4).
  2. parse_wizard_meal_response — map a model's JSON week into clean suggestion
     entries, restricted to the target keys.
  3. build_wizard_meal_prompt — assemble the one-pass generation prompt from the
     wizard session (G1c-1b). Built as a list of lines joined with newline
     (Rule 1/2/7). Family facts come from app_settings / the meal rules via the
     Lorenzo helpers — NEVER hardcoded here (Rule 19).

This module makes no network call and no file writes; the live Sonnet call and
the session write live in app.py's /meal-wizard-generate route (G1c-1b).
"""

from datetime import date, timedelta
import json
import re

from render_lorenzo import (
    _get_meal_constraints,
    _get_calendar_this_week,
    _get_saved_recipes,
)
from data_helpers import slot_dishes


_WIZARD_GEN_SLOT_CAP = 14  # conservative placeholder (2 meal types x 7 days).
# NOT measured — the known-good point is ~7 slots (1 type/week), the known-bad
# point is 55. Tune this from the gen log once real stop_reason data exists.
# Single source of truth — also imported by app.py and
# render_meal_wizard_step4.py. Change once here. Added 2026-06-30.


def wizard_target_slot_keys(session: dict) -> list:
    """Return the "YYYY-MM-DD::slot" keys the generator should fill:
    every date in the planning window x every slot kind being planned,
    MINUS any key already present in confirmed_meals (never overwrite a
    confirmed/locked meal — Rule 4). Returns a sorted list; [] if the
    window or slot kinds are missing."""
    win = session.get("planning_window") or {}
    start = win.get("start_iso")
    end = win.get("end_iso")
    slots = session.get("confirmed_what_to_plan") or []
    confirmed = session.get("confirmed_meals") or {}
    if not (start and end and slots):
        return []
    try:
        d0 = date.fromisoformat(start)
        d1 = date.fromisoformat(end)
    except Exception:
        return []
    if d1 < d0:
        return []
    keys = set()
    d = d0
    while d <= d1:
        for slot in slots:
            k = d.isoformat() + "::" + str(slot)
            if k not in confirmed:
                keys.add(k)
        d = d + timedelta(days=1)
    return sorted(keys)


def parse_wizard_meal_response(text: str, target_keys) -> dict:
    """Parse the model's JSON week and map it into suggestion entries,
    keyed "YYYY-MM-DD::slot". Includes ONLY keys in target_keys (never a
    confirmed slot, never an out-of-window date, never an unrequested slot
    kind). Returns {} if nothing parses. Each entry mirrors a confirmed
    entry minus the lock, tagged source 'lorenzo'."""
    candidates = []
    fence = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if fence:
        candidates.append(fence.group(1))
    brace = re.search(r'\{[\s\S]*\}', text)
    if brace:
        candidates.append(brace.group())
    parsed = {}
    for cand in candidates:
        try:
            parsed = json.loads(cand)
            break
        except json.JSONDecodeError:
            cleaned = re.sub(r',\s*([}\]])', r'\1', cand)
            try:
                parsed = json.loads(cleaned)
                break
            except Exception:
                pass
    if not isinstance(parsed, dict) or not parsed:
        return {}
    meals = parsed.get("meals") if isinstance(parsed.get("meals"), dict) else parsed
    target = set(target_keys or [])
    out = {}
    for day_key, slots in meals.items():
        if not isinstance(slots, dict):
            continue
        for slot_key, val in slots.items():
            key = str(day_key) + "::" + str(slot_key)
            if key not in target:
                continue
            if isinstance(val, dict):
                name = str(val.get("name", "") or "").strip()
                protein = str(val.get("protein", "") or "").strip()
                ingredients = str(val.get("ingredients", "") or "").strip()
                note = str(val.get("note", "") or "").strip()
            else:
                name = str(val or "").strip()
                protein = ""
                ingredients = ""
                note = ""
            if not name:
                continue
            out[key] = {
                "dishes": [{
                    "category": "main",
                    "name": name,
                    "ingredients": ingredients,
                    "protein": protein,
                }],
                "note": note,
                "source": "lorenzo",
                "recipe_id": "",
                "recipe_on_request": True,
                "skip_shopping": False,
            }
    return out


def build_wizard_meal_prompt(session: dict, target_keys: list) -> str:
    """Assemble the one-pass generation prompt from the wizard session.
    Returns a single string. Built as a list of lines joined with newline
    (Rule 1/2/7 — no f-string backslash/quote hazards). Family-agnostic: any
    family facts come from app_settings / the meal rules via the Lorenzo
    helpers, never hardcoded (Rule 19). All inputs are fail-soft."""
    session = session or {}
    keys = list(target_keys or [])

    # Grouped "YYYY-MM-DD — slot" list. Keep the slot token RAW (not humanized)
    # so the model echoes the exact slot key the parser matches against.
    slot_lines = []
    for k in keys:
        if "::" in k:
            d_part, s_part = k.split("::", 1)
        else:
            d_part, s_part = k, ""
        slot_lines.append("  - " + d_part + " — " + s_part)
    targets_block = "\n".join(slot_lines) if slot_lines else "  (none)"

    inventory = str(session.get("confirmed_inventory", "") or "").strip()
    use_soon = str(session.get("use_soon_items", "") or "").strip()
    used = session.get("used_proteins", []) or []
    if isinstance(used, list):
        used_str = ", ".join(str(p) for p in used if str(p).strip())
    else:
        used_str = str(used).strip()
    complexity = str(session.get("confirmed_complexity", "normal") or "normal").strip()

    # In-window confirmed meals — already decided by the mother; the model must
    # plan a coherent week AROUND them, never fill or change them.
    win = session.get("planning_window") or {}
    start = win.get("start_iso")
    end = win.get("end_iso")
    confirmed = session.get("confirmed_meals") or {}
    confirmed_lines = []
    if isinstance(confirmed, dict):
        for ck in sorted(confirmed.keys()):
            cv = confirmed[ck]
            if "::" in ck:
                c_date, c_slot = ck.split("::", 1)
            else:
                c_date, c_slot = ck, ""
            if start and end and not (start <= c_date <= end):
                continue
            _cv_dishes = slot_dishes(cv)
            c_name = str((_cv_dishes[0].get("name", "") if _cv_dishes else "") or "").strip()
            if c_name:
                confirmed_lines.append("  - " + c_date + " — " + c_slot + ": " + c_name)
    confirmed_block = "\n".join(confirmed_lines) if confirmed_lines else "  (none yet)"

    # Family-aware context, pulled (never hardcoded) via the Lorenzo helpers.
    rules_str = _get_meal_constraints()
    if keys:
        win_start = start or keys[0].split("::", 1)[0]
    else:
        win_start = start or date.today().isoformat()
    calendar_str = _get_calendar_this_week(win_start)
    recipes_str = _get_saved_recipes()

    has_dad_lunch = any(k.endswith("::dad_lunch") for k in keys)

    lines = []
    lines.append("You are the meal planner for a Catholic homeschool family.")
    lines.append("You are producing a DRAFT week of meals that the mother will review and edit. These are suggestions, not decisions — she has the final say.")
    lines.append("")
    lines.append("Fill EXACTLY these meal cells, and ONLY these:")
    lines.append(targets_block)
    lines.append("Do not add any day or meal type that is not in this list.")
    lines.append("")
    lines.append("These meals are ALREADY decided — do NOT propose or change them; plan a coherent week around them:")
    lines.append(confirmed_block)
    lines.append("")
    lines.append("USE-SOON items — each MUST be used in at least one meal this week:")
    lines.append("  " + (use_soon if use_soon else "(none)"))
    lines.append("Do not ignore them.")
    lines.append("")
    lines.append("On-hand inventory (note the FORM — fresh / canned / frozen / dried):")
    lines.append("  " + (inventory if inventory else "(none recorded)"))
    lines.append("Respect the form exactly: if an item is canned, do not plan a dish that needs it fresh, and vice versa; treat the canned/frozen form as usable as-is.")
    # TEMPORARY soft-guard, prompt-only — no real inventory depletion exists yet.
    # Revisit/remove when structured inventory lands (TRACKER 40/44). Added 2026-06-30.
    lines.append("The already-decided meals above draw from this same on-hand list.")
    lines.append("Some on-hand items are a single package or a small fresh amount. Do not propose a new dish that relies on a limited fresh or perishable item that an already-decided meal already uses — treat that item as spent.")
    lines.append("")
    lines.append("Do NOT repeat a main protein already used this week:")
    lines.append("  " + (used_str if used_str else "(none yet)"))
    lines.append("Rotate proteins across the days you plan (no protein twice unless unavoidable).")
    lines.append("")
    lines.append("Standing meal rules — follow exactly, including any meatless-Friday / liturgical rules:")
    lines.append(rules_str)
    lines.append("")
    lines.append("Calendar for the week (keep meals quick on busy days):")
    lines.append(calendar_str)
    lines.append("")
    lines.append("Effort level for this week: " + complexity + " — match it.")
    if recipes_str:
        lines.append("")
        lines.append("Recipes already on hand (prefer dishes the family already has a recipe for):")
        lines.append(recipes_str)
    if has_dad_lunch:
        lines.append("")
        lines.append("The dad-lunch slot must NEVER be the same as that day's family dinner; he prefers meat over salad or rice.")
    lines.append("")
    lines.append("Suggest real, makeable dishes. You may include meals that need a few shopping items, but never claim an ingredient is on hand unless it is in the inventory above.")
    lines.append("")
    lines.append("Return ONLY a JSON object, no prose before or after, in EXACTLY this shape:")
    lines.append('{"meals": {"YYYY-MM-DD": {"slot": {"name": "...", "protein": "...", "ingredients": "...", "note": "..."}}}}')
    lines.append("Include only the date/slot cells listed above. protein = the single main protein, or empty string if meatless. ingredients = brief comma-separated list. note = optional, <= 8 words.")
    return "\n".join(lines)
```

---

## Prompt location answer

The Lorenzo generation prompt is **entirely inline** in `render_meal_wizard_gen.py` —
built inside `build_wizard_meal_prompt()` as a `lines = []` list, joined at the end.
There is no separate string constant, template file, or external `.txt`/`.md` source.

Three **data helpers** from `render_lorenzo.py` are called to inject live context:
- `_get_meal_constraints()` — standing meal rules (meatless-Friday, etc.)
- `_get_calendar_this_week(win_start)` — calendar for the week
- `_get_saved_recipes()` — recipe library titles

Those are data-fetching functions, not prompt templates — the prompt wording itself lives
only in `build_wizard_meal_prompt`.
