# Step 4 Phase C — format_dish_list wired into confirmed-state display

**Date:** 2026-07-01  
**Files changed:** `render_meal_wizard_step4.py` (import + one line in confirmed branch)

---

## Changes made

### 1. Import added (line 38)
```python
from render_meals import format_dish_list
```
No circular import risk: `render_meals.py` imports nothing from `render_meal_wizard*`.

### 2. Confirmed branch: name line replaced (line 406)
**Before:**
```python
name = escape((_entry_dishes[0].get("name", "") if _entry_dishes else "") or "")
```
**After:**
```python
name = escape(format_dish_list(_entry_dishes))
```
Everything else in the confirmed branch (recipe label, source tag, skip_shopping tag, Change button, prefill lock logic) is unchanged.

---

## Compile check

```
COMPILE OK
```

---

## Four smoke cases — confirmed branch

| Case | Input | Rendered name | Result |
|---|---|---|---|
| 1 | Single main dish | `'Chicken Parm'` | **PASS** — identical to old first-dish logic |
| 2 | Main + side + salad | `'Roast Chicken with Roasted Potatoes and Caesar Salad'` | **PASS** — main leads |
| 3 | Soup + bread (no main) | `'Tomato Soup with Crusty Bread'` | **PASS** — soup leads per fallback rule |
| 4 | Side + salad + dessert (no main, no soup) | `'Rice Pilaf, Green Salad and Peach Cobbler'` | **PASS** — plain no-Oxford-comma join, no lead |

Full output:
```
COMPILE OK
Case 1 PASS — single main: 'Chicken Parm'
Case 2 PASS — main leads: 'Roast Chicken with Roasted Potatoes and Caesar Salad'
Case 3 PASS — soup leads (no main): 'Tomato Soup with Crusty Bread'
Case 4 PASS — no lead, plain join: 'Rice Pilaf, Green Salad and Peach Cobbler'

All 4 smoke cases PASS
```

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
