# Step 4 — Suggestion-prefill multi-row fix

**Date:** 2026-07-01  
**File changed:** `render_meal_wizard_step4.py` (empty-branch prefill block, lines ~351–430)

---

## What changed

`_s4_slot_block`'s empty-branch previously read all dishes from the suggestion
via `slot_dishes()` but immediately discarded everything after `_sug_dishes[0]`,
rendering exactly one `<div class="s4dr">` regardless of how many dishes were
stored.

Now it loops over all dishes and emits one `.s4dr` per dish:

```python
_sug_dishes = slot_dishes(suggestion) if isinstance(suggestion, dict) else []
_multi = len(_sug_dishes) > 1
_rm_hide = "" if _multi else "display:none;"

if _sug_dishes:
    for _d in _sug_dishes:
        _nb = escape(_d.get("name") or "")
        _ib = escape(_d.get("ingredients") or "")
        _sp = escape(_d.get("protein") or "")
        _pv = ' value="' + _sp + '"'
        _io = " open" if _ib else ""
        _dishes_html += (
            f'<div class="s4dr">...'
            f'<button data-role="rm" style="{_rm_hide}{_S4_REMOVE_BTN}" ...'
            ...)
else:
    # no suggestion → one blank row, Remove hidden (unchanged)
```

**Remove-button rule** (mirrors Add-a-dish's live behavior):
- 1 dish in suggestion → Remove hidden on row 0 (single-row floor, same as before)
- 2+ dishes → Remove visible on ALL rows including row 0, so a reverted multi-dish meal is immediately editable identically to a manually-built one

**Category select** stays on the placeholder `— category —` for every row, per Lauren's rule.

**`<details>` open** only when the dish actually has ingredients; closed when empty (better UX than always-open for every row).

Empty-row path (no suggestion at all): unchanged — one blank row, Remove hidden.

---

## Compile check

```
COMPILE OK
```

---

## Three smoke cases

### Case 1 — 1-dish suggestion (regression)
Input: `[{category:main, name:"Chicken Parm", ingredients:"chicken, marinara, mozzarella", protein:"chicken"}]`

```
count=1 .s4dr rows  ✓
"Chicken Parm" present  ✓
ingredients present  ✓
value="chicken" (protein)  ✓
<details open  ✓  (has ingredients)
display:none; on Remove  ✓  (1-row floor)
Case 1 PASS
```

### Case 2 — 2-dish suggestion (main + bread)
Input: `[{main, "Leftover Ground Beef Pasta Thermos", ingredients…}, {bread, "Garlic bread", ingredients:""}]`

```
count=2 .s4dr rows  ✓
"Leftover Ground Beef Pasta Thermos" present  ✓
"Garlic bread" present  ✓
pasta ingredients present  ✓
value="ground beef" (pasta protein)  ✓
value="" (bread protein attr)  ✓
<details open for pasta row  ✓
<details closed for bread row (empty ingredients)  ✓
display:none absent — both Remove buttons visible  ✓
Case 2 PASS
```

### Case 3 — 3-dish suggestion (main + side + salad)
Input: `[{main,"Roast Chicken",ingredients}, {side,"Roasted Potatoes",ingredients}, {salad,"Caesar Salad",ingredients:""}]`

```
count=3 .s4dr rows  ✓
All three names present  ✓
Chicken + potato ingredients present  ✓
open_details=2 (chicken + potato; caesar closed — no ingredients)  ✓
display:none absent — all 3 Remove buttons visible  ✓
Case 3 PASS
```

---

## Lauren's exact sequence — 2-dish John's Lunch confirm → Change

Isolated in-process harness: `2026-07-02::johns_lunch`, dishes = Pasta Thermos (main) + Garlic bread (bread).

```
PASS Step 1: Keep 2-dish POST ok
PASS Step 1: confirmed_meals has 2 dishes (got 2)
PASS Step 1: dish[0] name correct
PASS Step 1: dish[1] name correct
PASS Step 1: suggested_meals mirror has 2 dishes (got 2)

PASS Step 2: Change POST ok
PASS Step 2: slot_html has 2 .s4dr rows (got 2)
PASS Step 2: pasta name in reverted HTML
PASS Step 2: bread name in reverted HTML
PASS Step 2: pasta ingredients in reverted HTML
PASS Step 2: pasta details open
PASS Step 2: no hidden Remove (both visible in 2-row state)
PASS Step 2: dish container id present

PASS Step 3: GET /meal-wizard-step4 200
PASS Step 3: pasta name on full page
PASS Step 3: bread name on full page
PASS Step 3: full page shows 2 rows for slot (got 2)

PASS Lauren's 2-dish John's Lunch confirm→Change sequence: all checks passed
```

After Change, the reverted slot shows **2 rows** — pasta pre-filled with name + ingredients (details open), bread pre-filled with name (details closed, empty ingredients), both Remove buttons visible. This matches exactly what a manually-built 2-dish meal looks like.

---

## verify_meal_wizard_step4_writeloop.py — 17/17 PASS

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
