# BUILD complete — `_WIZARD_GEN_SLOT_CAP` single source of truth (Phase 2 of 2)

**File changed:** `render_meal_wizard_step4.py` only. Refactor, no behavior change.

## What changed
Removed the locally-duplicated constant and its drift-risk comment block; added `_WIZARD_GEN_SLOT_CAP` to the **existing** gen-module import line (no second import created):
```python
from render_meal_wizard_gen import wizard_target_slot_keys, _WIZARD_GEN_SLOT_CAP
```
No logic changed — the three render states (0 / under cap / over cap) behave identically to Build 2, now reading the shared constant. This removes the last duplicate; the cap value `14` now lives in exactly one place (`render_meal_wizard_gen.py`), imported by both `app.py` and Step 4. **The drift risk flagged across the prior builds is fully resolved.**

---

## Validation results (all four pass)

### 1. `py_compile render_meal_wizard_step4.py`
```
py_compile OK
```

### 2. In-process smoke test (5 / 20 / 0 slots + drift-guard)
```
gen cap: 14 | step4 cap: 14 | app cap: 14
drift-guard: all three reference one shared object (no copies)
[5 slots]  -> ENABLED, 'Will generate 5 meal(s).' present
[20 slots] -> DISABLED (attribute), warning '(20)' present, points to Step 3
[0 slots]  -> unchanged (no count line, not disabled)

SMOKE OK: identical to Build 2; constant now shared, single source
```
The drift-guard now passes **trivially**: `s4._WIZARD_GEN_SLOT_CAP is gen._WIZARD_GEN_SLOT_CAP is app._WIZARD_GEN_SLOT_CAP` — all three names resolve to the *same object*, so there is one value, not two that happen to match. Render output is identical to Build 2.

### 3. Meal-wizard harnesses (Build 2 set)
```
verify_meal_wizard_gen.py             → PASS all G1c-1a generation-contract checks passed (exit 0)
verify_meal_wizard_step4.py           → PASS all G1b-1 read-only screen checks passed     (exit 0)
verify_meal_wizard_step4_lock.py      → PASS all G1 lock checks passed                    (exit 0)
verify_meal_wizard_step4_writeloop.py → PASS all G1b-2a write-loop + guard checks passed  (exit 0)
```

### 4. `import app` (circular-import check)
```
app imports OK (no circular import)
```

## Scope confirmation
Only `render_meal_wizard_step4.py` changed. No other files touched.

## Status: drift risk closed
With Phase 1 + Phase 2 complete, `_WIZARD_GEN_SLOT_CAP` is a single source of truth in `render_meal_wizard_gen.py`, imported by `app.py` (server-side enforcement) and `render_meal_wizard_step4.py` (render-time UI state). No remaining duplicates.
