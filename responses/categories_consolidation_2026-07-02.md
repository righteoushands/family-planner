# CATEGORIES consolidation — single source of truth (2026-07-02)

## All rules pasted back (Rule 15)

**1.** No backslashes inside f-strings.
**2.** No nested quotes inside f-strings — use a variable outside the f-string instead.
**3.** All GET routing uses `elif` chains in `do_GET`; POST routing in `do_POST` also uses `elif` chains. One exception: multipart recipe routes share an `elif path in (...)` outer block.
**4.** Never put import statements inside `if` blocks or functions. [KNOWN DEVIATION: several live handlers use inline `import json as _json`; new code keeps imports at module top.]
**5.** All file writes use `safe_save_json` — never `open(f, 'w')` directly.
**6.** No walrus operator (`:=`).
**7.** Never use `\n` inside a JS string within a Python string literal.
**8.** `multipart/form-data`: sniff `Content-Type`, parse with `cgi.FieldStorage`.
**9.** `py_compile` only validates syntax — always run an in-process smoke test after, then run the relevant `verify_*.py` harness.
**10.** Test fixtures must never write to live data; always restore from backup.
**10a.** Isolation must be structural: any `verify_*.py` harness must import its isolation guard as the literal first import.
**11.** Never pass an already-HTML-escaped string through `escape()` again.
**12.** Rule 7 applies to ALL files with JS embedded in Python.
**13.** FROL WIZARD NESTED FORM ADDENDUM — check `action` attribute before adding any form to a section body.
**14.** PRE-FLIGHT CHECKLIST — (1) files; (2) JS in f-strings; (3) form handling; (4) root cause confirmed; (5) multi-file → single-purpose phases; (6) data shape changes confirmed before/after.
**15.** CLAUD.MD READ-BACK REQUIRED — paste every rule at session start. ✅
**16.** MAGNIFICA HUMANITAS — app is a tool not an authority; companions serve real relationships; AI supports thinking; transparent about AI; language of grace not performance; subsidiarity; formation in digital wisdom.
**17.** ONE FIX PER INSTRUCTION — never bundle multiple fixes unless same file and directly related.
**18.** AUGUST 15TH PRIORITY FILTER — every build request checked against the August 15th plan.
**19.** BUILD FOR A FUTURE SECOND FAMILY — no hardcoded family specifics; family identity in `app_settings.json`; all reads/writes through `data_helpers.py`.
**20.** PRESERVE SCROLL ON SAME-PAGE RELOADS — `fetch()` POST that reloads same page must save/restore `scrollY` via `sessionStorage`.
**21.** SESSION HELPER SHALLOW-MERGE — `update_meal_wizard_session` merges only at top level; read fresh → merge → write; read immediately before write, not before a long AI call.
**22.** MERGE-BASED GENERATE NO LONGER PRUNES — stale `suggested_meals` entries accumulate; inert unless a stale key re-enters window×to_plan unconfirmed.

---

## Pre-flight (Rule 14)

1. **Files touched:** `config.py`, `render_meal_wizard_gen.py`, `render_meal_wizard_step4.py`. `app.py` — **no change** (re-export approach, see below).
2. **JS in f-strings?** None of these files embed JS. Not applicable.
3. **Form handling?** No.
4. **Root cause confirmed?** Yes — mechanical constant move to break circular import.
5. **Multiple files?** Yes — three production files + three harnesses run. All are one cohesive mechanical move; no logic change.
6. **Data shape changes?** No.

---

## What changed

### config.py — new canonical definition

```python
# Single canonical dish-category allowlist — used by render_meal_wizard_step4
# (UI <select> options) and render_meal_wizard_gen (prompt + response parser).
MEAL_DISH_CATEGORIES = (
    "main", "side", "soup", "bread", "salad", "appetizer", "dessert", "snack"
)
```

Added immediately after `MEAL_WIZARD_SESSION_FILE` in the meal-wizard section.

### render_meal_wizard_gen.py

- Removed local `_DISH_CATEGORIES = (...)` definition (lines 38-45 of the old file).
- Added: `from config import MEAL_DISH_CATEGORIES as _DISH_CATEGORIES`
- All 4 internal references to `_DISH_CATEGORIES` are unchanged — they now resolve to `config.MEAL_DISH_CATEGORIES`.
- Updated comment: circular-import issue resolved (no longer a TODO).

### render_meal_wizard_step4.py

- Removed local `CATEGORIES = ("main", ...)` definition (line 41 of the old file).
- Added: `from config import MEAL_DISH_CATEGORIES as CATEGORIES`
- All 4 internal references to `CATEGORIES` (option rendering, category <select>, confirm-POST validation) are unchanged.

### app.py — NO CHANGE (re-export approach)

The existing import `from render_meal_wizard_step4 import render_step4_slot_and_lock, CATEGORIES as _S4_CATEGORIES` continues to work because `CATEGORIES` is still a module-level name in `render_meal_wizard_step4` (imported from config). The re-export is implicit: step4 does `from config import MEAL_DISH_CATEGORIES as CATEGORIES`; that name is a module-level attribute; app.py's existing import of it from step4 works without any change.

**Why re-export instead of direct?** Fewer lines of diff, zero risk to the app.py import line. The name `CATEGORIES` remains a stable API surface of `render_meal_wizard_step4` whether it is defined locally or imported. Direct import from config would work equally but requires touching app.py for no functional gain.

---

## Repo-wide grep — zero remaining local definitions

```
grep -rn "^CATEGORIES\s*=" --include="*.py" .   → (nothing)
grep -rn "^_DISH_CATEGORIES\s*=" --include="*.py" .  → (nothing)
```

The only hits for those names are:
- `config.py:82` — the new canonical definition `MEAL_DISH_CATEGORIES = (...)`
- `render_meal_wizard_gen.py` — `from config import MEAL_DISH_CATEGORIES as _DISH_CATEGORIES` (import, not definition)
- `render_meal_wizard_step4.py` — `from config import MEAL_DISH_CATEGORIES as CATEGORIES` (import, not definition)
- Test-harness fixture variables (`_CATS`, inline string values) — not the old production tuple.

---

## Test results

### py_compile — all 4 files
```
py_compile OK all 4 files
```

### In-process smoke (7/7) — identity + end-to-end
```
PASS config.MEAL_DISH_CATEGORIES has 8 values
PASS gen._DISH_CATEGORIES is config.MEAL_DISH_CATEGORIES (same object)
PASS s4.CATEGORIES is config.MEAL_DISH_CATEGORIES (same object)
PASS re-export: from render_meal_wizard_step4 import CATEGORIES == config.MEAL_DISH_CATEGORIES
PASS parse_wizard_meal_response still works end-to-end
PASS invalid category still rejected (slot dropped)
PASS wizard_target_slot_keys unaffected
```

### verify_meal_wizard_gen — 63/63 PASS
All G1c-1a + G1c-3a checks including truncation and drop tests.

### verify_meal_wizard_step4 — all PASS
```
PASS empty session renders gate state without raising
PASS gate state adds no <script> beyond page chrome (display-only)
PASS seeded render includes the G1b-2a write-loop script (s4Keep/s4Change)
PASS both day labels (Monday, Tuesday) present
PASS selected slot labels (Breakfast, Dinner) present
PASS all three confirmed meal names present
[+7 more] → PASS all G1b-1 read-only screen checks passed
```

### verify_meal_wizard_step4_lock + writeloop — all PASS
```
PASS all G1 lock checks passed
PASS all G1b-2a write-loop + guard checks passed
```

---

## Live generation call — real inventory × real calendar

**Session used:** Lauren's live `meal_wizard_session.json`
**Window:** 2026-07-01 → 2026-07-02
**Target keys (unconfirmed):** `2026-07-02::breakfast`, `2026-07-02::lunch`, `2026-07-02::dinner`, `2026-07-02::snacks`, `2026-07-02::dessert`
**Confirmed on 07-01 (context given to Lorenzo):** Pancakes / Rotisserie Chicken Tacos / Ground Beef Pasta with Spaghetti Sauce / Chocolate Cake / Apple Slices with PB & Grapes

**Model:** `claude-haiku-4-5-20251001` — **stop_reason: end_turn** ✓

### Lorenzo's raw dishes[]

| Slot | # dishes | category | name | protein |
|---|---|---|---|---|
| breakfast | 1 | main | Scrambled Eggs with Toast | eggs |
| lunch | 1 | main | Salmon Salad with Crackers | salmon |
| snacks | 1 | main | Yogurt with Fresh Berries and Granola | — |
| **dinner** | **2** | **main** | **Sheet Pan Chicken Thighs with Roasted Green Beans** | **chicken** |
| | | **side** | **Roasted Sweet Potatoes** | — |

*Note: `dessert` slot was not filled by Lorenzo — the model silently skipped it despite being listed. This is a prompt-compliance gap worth logging.*

### Inventory sanity check

**Dinner main:** raw chicken (2 lbs, fridge ✓), fresh green beans (fridge ✓), carrots (fridge ✓). Calls for olive oil and garlic — not explicitly listed in inventory but pantry staples; acceptable.

**Dinner side:** sweet potatoes (6 small, pantry ✓). Olive oil/salt/pepper — staples.

**Breakfast:** eggs (two dozen, fridge ✓), sourdough bread (fridge ✓). Butter/milk — on hand ✓.

**Lunch:** canned pink salmon (1 can, pantry ✓), romaine lettuce (two heads, fridge ✓). Calls for mayo, lemon, celery, crackers — not in inventory. Minor gap; crackers/mayo are typical pantry staples not always listed.

**Snacks:** whole milk yogurt (fridge ✓), blueberries + strawberries (fridge ✓), rolled oats (pantry ✓), honey (pantry ✓). All on hand.

### Assessment

- **Dish count:** dinner correctly returned 2 dishes (main + side) ✓. All single-dish slots returned exactly 1 dish ✓.
- **Categories:** all valid (`main`, `side`) — no invalid categories in raw output ✓.
- **Ingredient sanity:** very good. Protein rotation from 07-01 (ground beef, rotisserie chicken) honored — 07-02 uses eggs, salmon, chicken (raw, not the rotisserie). No protein repeated.
- **Liturgical / meal rules:** 07-02 is Thursday; no meatless rule applies. Sheet pan chicken is consistent with lower-carb, moderate-effort.
- **Note quality:** the notes reference "John on leave to Fredericksburg" and "counseling appointment" — pulled from the real calendar context, not hallucinated.
- **Gap to flag:** `dessert` slot was silently omitted. Lorenzo did not return a dessert dish for 07-02. The parser correctly returns no entry for `2026-07-02::dessert` (not a crash, just a missing suggestion). The prompt does list it as a target. This is a recurring risk with small-context Haiku — consider adding an explicit "every slot in the list MUST appear in your output" enforcement line to the prompt.

---

## Rules applied

| Rule | How |
|---|---|
| **4** | All imports remain at module top — `from config import MEAL_DISH_CATEGORIES` is a top-level statement in both gen and step4 |
| **9** | py_compile + 7-point in-process smoke + 3 harnesses run and reported |
| **14** | Pre-flight done above |
| **15** | All 22 rules pasted back ✓ |
| **17** | One mechanical move; four files but one cohesive change, no logic touched |
| **19** | `MEAL_DISH_CATEGORIES` in config.py — not family-specific, domain constant |
