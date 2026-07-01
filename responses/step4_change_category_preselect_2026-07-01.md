# Step 4 — Change revert: category pre-selection fix

**Date:** 2026-07-01  
**File changed:** `render_meal_wizard_step4.py` — prefill loop inside `_s4_slot_block` (~10 lines)

---

## What changed

In the suggestion-prefill `for _d in _sug_dishes` loop, the raw `_S4_CAT_OPTS_HTML`
(no selection) is replaced with a per-dish option string that marks the stored
category as `selected`:

```python
_dc = _d.get("category") or ""
_cat_opts = (
    '<option value="">\u2014 category \u2014</option>'
    + "".join(
        '<option value="' + c + '"'
        + (' selected' if c == _dc else '')
        + '>' + c + '</option>'
        for c in CATEGORIES
    )
)
```

The f-string then references `{_cat_opts}` instead of `{_S4_CAT_OPTS_HTML}`.

The empty-row fallback (no dish data) and the hidden template still use
`_S4_CAT_OPTS_HTML` unchanged — no pre-selection for a blank row is correct.

---

## Tests

### Structural checks (8/8 PASS)

```
  PASS  _dc / _cat_opts / selected marker present in source
  PASS  3 .s4dr rows rendered
  PASS  1x value="main" selected
  PASS  2x value="side" selected
  PASS  no other category selected
  PASS  empty-row fallback: no selected option
  PASS  all 3 dish names present
  PASS  snacks cat still hidden (regression guard)
```

### End-to-end 3-dish smoke test (6/6 PASS)

Scenario: confirm main+side+side, hit Change, verify HTML, re-Keep immediately.

```
  PASS  1. Confirm 3-dish meal (main/side/side): 200 ok
  PASS  2. Change → 3 entry rows rendered
  PASS  3. All 3 dish names present in reverted HTML
  PASS  4. Categories pre-selected: 1x main, 2x side
  PASS  5. Re-Keep immediately: 200 ok
  PASS  6. Stored categories: ['main', 'side', 'side'] — all 3 unchanged
```

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
