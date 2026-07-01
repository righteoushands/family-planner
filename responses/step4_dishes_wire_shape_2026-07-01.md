# Step 4 confirm — dishes[] wire shape (Phase A) (2026-07-01)

## What changed

Two files, landed together.

### `render_meal_wizard_step4.py`
Added `CATEGORIES` constant (module-level, after `_HEADING_FONT`):
```python
CATEGORIES = ("main", "side", "soup", "bread", "salad", "appetizer", "dessert")
```
Lowercase, matches the existing hardcoded `"main"` string everywhere.

Updated `s4Keep` client payload from flat fields to `dishes[]` (Phase A — one dish
wrapped, no new UI):
```js
// before
var payload = { date: date, slot: slot, name: name, source: 'manual',
  ingredients: ing, protein: prot, recipe_id: '', recipe_on_request: true };

// after
var payload = { date: date, slot: slot,
  dishes: [{category: 'main', name: name, ingredients: ing, protein: prot}],
  source: 'manual', recipe_id: '', recipe_on_request: true };
```

### `app.py`
Updated import to pull in `CATEGORIES`:
```python
from render_meal_wizard_step4 import render_step4_slot_and_lock, CATEGORIES as _S4_CATEGORIES
```

Replaced the flat `_s4_name` read + inline `"dishes":[{...}]` construction with a
`dishes[]`-aware reader and validator in `/meal-wizard-step4-confirm`:
- Reads `dishes` list from payload.
- Validates: list must be non-empty AND every item must be a dict with a non-empty
  `name` — 400 if not (unchanged rejection behaviour, new trigger).
- `category`: if missing or not in `_S4_CATEGORIES`, silently defaults to `"main"`
  (same auto-correct pattern as `recipe_on_request`; never rejects).
- Builds `_s4_dishes` list with the coerced category, then assigns it directly as
  `_s4_entry["dishes"]`. All other fields (`source`, `locked`, `recipe_id`,
  `recipe_on_request`, `skip_shopping`) are unchanged.

`py_compile app.py render_meal_wizard_step4.py` → **OK** (both files).

## Harnesses updated (payload shape change)

Every harness that POST'd to `/meal-wizard-step4-confirm` with flat fields was
updated to `dishes:[{...}]`. Files touched:

| File | Change |
|---|---|
| `data/verify_meal_wizard_step4_writeloop.py` | 3 POST payloads (GUARD 1/2/3) |
| `data/verify_mirror_neighbor_untouched.py` | 1 POST payload |
| `data/verify_generate_wipes_mirror.py` | 1 POST payload |
| `data/verify_generate_midcall_race.py` | 1 POST payload |
| `data/verify_meal_wizard_g1a.py` | `_confirm()` local replica rewritten to read `dishes[]`; Test 2 and Test 4 payloads updated |

## Smoke test — 3 cases (all PASS)

```
CASE 1 (one dish, new wire shape): PASS
  status: 200 | dish0: {'category': 'main', 'name': 'Chicken Parm',
                         'ingredients': 'pasta', 'protein': 'chicken'}

CASE 2 (bad category -> 'main'): PASS
  status: 200 | category stored: main

CASE 3 (empty name -> 400): PASS
  status: 400 | ok: False | session unchanged: True

SMOKE RESULT: PASS (all 3 cases)
```

## `verify_meal_wizard_step4_writeloop.py` — 17/17 PASS

```
PASS confirm POST returns 200 {ok:true}
PASS confirm response returns the confirmed slot fragment (row id + Change)
PASS confirm response reports lock-eligibility True + lock-control HTML
PASS confirmed meal persisted to session
PASS confirmed meal is locked
PASS GUARD 1: recipe_on_request auto-set True (client omitted it)
PASS confirmed meal has empty recipe_id
PASS confirmed entry stored in dishes[] shape (no flat name key)
PASS GET page shows the confirmed meal
PASS confirmed meal shows a 'Change' button
PASS confirmed meal shows 'No recipe needed'
PASS GUARD 2: recipe_id present -> recipe_on_request left False
PASS GUARD 3: recipe_on_request already True -> left True
PASS remove POST clears the slot from the session
PASS remove response reverts to entry state showing the last-confirmed value
PASS removed slot returns to entry state showing the last-confirmed value
PASS prefill (past) meal renders locked with NO 'Change' button

PASS all G1b-2a write-loop + guard checks passed
```

## Files changed
- `render_meal_wizard_step4.py` — `CATEGORIES` constant; `s4Keep` payload
- `app.py` — import `CATEGORIES as _S4_CATEGORIES`; confirm handler reads `dishes[]`
- `data/verify_meal_wizard_step4_writeloop.py` — 3 payload updates
- `data/verify_mirror_neighbor_untouched.py` — 1 payload update
- `data/verify_generate_wipes_mirror.py` — 1 payload update
- `data/verify_generate_midcall_race.py` — 1 payload update
- `data/verify_meal_wizard_g1a.py` — `_confirm()` rewrite + 2 payload updates
