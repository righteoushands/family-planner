# BUILD complete — `_WIZARD_GEN_SLOT_CAP` single source of truth (Phase 1 of 2)

**Files changed:** `render_meal_wizard_gen.py` and `app.py` only. Refactor, no behavior change. `render_meal_wizard_step4.py` was **not** touched (that's Phase 2).

## What changed

### 1. `render_meal_wizard_gen.py` — now owns the constant
Added next to `wizard_target_slot_keys` (the natural home — this module has no circular-import conflict with either `app.py` or Step 4):
```python
_WIZARD_GEN_SLOT_CAP = 14  # conservative placeholder (2 meal types x 7 days).
# NOT measured — the known-good point is ~7 slots (1 type/week), the known-bad
# point is 55. Tune this from the gen log once real stop_reason data exists.
# Single source of truth — also imported by app.py and
# render_meal_wizard_step4.py. Change once here. Added 2026-06-30.
```

### 2. `app.py` — imports it instead of defining it
Added to the **existing** gen-module import line (no new import line created):
```python
from render_meal_wizard_gen import wizard_target_slot_keys, parse_wizard_meal_response, build_wizard_meal_prompt, _WIZARD_GEN_SLOT_CAP
```
The local definition was removed, leaving a pointer comment (the `_WIZARD_GEN_LOG` constant beside it is unchanged):
```python
# _WIZARD_GEN_SLOT_CAP is the single source of truth in render_meal_wizard_gen.py
# (imported above) — also imported by render_meal_wizard_step4.py. Do not redefine.
_WIZARD_GEN_LOG = "data/meal_wizard_gen.log"
```
The cap-check logic itself is untouched — only where the constant comes from changed.

This resolves the drift risk flagged in the previous two builds for the app.py↔gen pair. (Phase 2 will point Step 4 at this same constant, removing the last duplicate.)

---

## Validation results (all three pass)

### 1. `py_compile render_meal_wizard_gen.py app.py`
```
py_compile OK (both)
```

### 2. In-process smoke test (behavior unchanged)
```
gen cap: 14 | app cap (imported): 14
20 slots -> {'ok': False, 'generated': 0, 'target': 20} | net calls: 0
5 slots -> {'proceeded_to_api': True} | net calls: 1

SMOKE OK: behavior unchanged; constant now sourced from gen (identity match)
```
- `app._WIZARD_GEN_SLOT_CAP is gen._WIZARD_GEN_SLOT_CAP` → **identity match** (app references gen's object, not a copy).
- 20-slot request still refused (`ok:False`, `target:20`) with **zero network calls**.
- 5-slot request still proceeds to the API path (poisoned `post` fired exactly once).

### 3. Meal-wizard harnesses (Build 1 set)
```
verify_meal_wizard_gen.py             → PASS all G1c-1a generation-contract checks passed (exit 0)
verify_meal_wizard_step4.py           → PASS all G1b-1 read-only screen checks passed     (exit 0)
verify_meal_wizard_step4_lock.py      → PASS all G1 lock checks passed                    (exit 0)
verify_meal_wizard_step4_writeloop.py → PASS all G1b-2a write-loop + guard checks passed  (exit 0)
```

## Scope confirmation
Only `render_meal_wizard_gen.py` and `app.py` changed. `render_meal_wizard_step4.py` left untouched for Phase 2.
