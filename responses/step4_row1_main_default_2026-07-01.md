# Step 4 — Row 1 category defaults to "main"

**Date:** 2026-07-01  
**File changed:** `render_meal_wizard_step4.py` — `_s4_slot_block` entry-state branch (~10 lines)

---

## What changed

`_cat_opts_main` is computed once before the suggestion branch — a standard
options string with `value="main"` marked `selected`. It is used in two places:

**1. Empty-row fallback** (no suggestion at all):
```python
# before
f'{_S4_CAT_OPTS_HTML}'
# after
f'{_cat_opts_main}'
```

**2. Suggestion loop, index 0 only** — if the stored/suggested category is
blank, default to "main" before building the per-dish `_cat_opts`:
```python
for _i, _d in enumerate(_sug_dishes):
    ...
    _dc = _d.get("category") or ""
    if not _dc and _i == 0:
        _dc = "main"          # default; stored category wins when non-blank
    _cat_opts = (...)         # existing per-dish selection logic
```

**Not changed:**
- `_S4_CAT_OPTS_HTML` itself — still no `selected`; still used in the template
  (`#s4-dish-template`) so rows added via "+ Add a dish" keep the blank placeholder.
- Index 1+ in the suggestion loop — `_dc` applied as-is (blank → blank).
- Revert/Change path — stored category from `_dc` is non-blank → the
  `if not _dc` guard doesn't fire → previous round's per-dish selection wins.

---

## Test results

### Smoke test — 5 cases PASS

```
  PASS  Case 1: empty slot → row 1 main selected
  PASS  Case 2: Lorenzo 2-dish (no cat) → row 1 main, row 2 blank
  PASS  Case 2b: stored category takes priority over main default
  PASS  Case 3: _S4_CAT_OPTS_HTML (used in template/row2+) has no selected
  PASS  Regression: snacks cat still hidden
```

**Case 2b** confirms the priority: a suggestion dish whose `category` is
`"side"` still renders `value="side" selected` on row 1 — the default fires
only for genuinely blank categories.

### writeloop harness — 17/17 PASS

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
```
