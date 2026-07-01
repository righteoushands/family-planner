# Step 4 — Change revert: diagnosis

**Date:** 2026-07-01  
**Method:** Authenticated in-process HTTP test (same pattern as writeloop harness — `auth.create_session("lauren")` + `mw_test_isolation.start_server()`). No browser access.

---

## Reproduction result

**All 3 dishes DO reappear as entry rows — none are lost in the HTML.**

```
Rows in reverted slot_html: 3  (expected 3)
  'Roast chicken' in slot_html: True
  'Roasted potatoes' in slot_html: True
  'Green beans' in slot_html: True
```

The Phase C2 fix (iterate all `_sug_dishes`) is working. The row count is correct.

---

## What the code actually does (step by step)

### 1. Confirm (POST /meal-wizard-step4-confirm)

The handler builds `_s4_entry["dishes"]` = full 3-dish list and stores it in two places:

```python
# confirmed_meals (the source of truth)
_s4_meals[date + "::" + slot] = _s4_entry

# suggested_meals mirror (so Change can pre-fill from it)
_s4_suggested[date + "::" + slot] = {"dishes": _s4_entry["dishes"]}
```

After confirm:
- `confirmed_meals["2026-07-07::dinner"]["dishes"]` = 3 dicts ✓  
- `suggested_meals["2026-07-07::dinner"]["dishes"]` = same 3 dicts ✓

### 2. Change → remove (POST /meal-wizard-step4-remove)

```python
_s4r_meals.pop(date + "::" + slot, None)          # pops confirmed entry
_s4r_frag = render_step4_slot_and_lock(date, slot) # re-renders entry state
```

`render_step4_slot_and_lock` reads the session fresh:  
- `confirmed.get(full)` → `None` (just popped)  
- `suggested.get(full)` → `{"dishes": [3 dicts]}` (mirror still intact)

Calls `_s4_slot_block(date, slot, label, None, {"dishes": [3 dicts]})`.

### 3. _s4_slot_block entry-state render

```python
_sug_dishes = slot_dishes(suggestion)   # returns list of 3 dicts
_multi = len(_sug_dishes) > 1           # True
_rm_hide = ""                           # Remove visible on all rows
for _d in _sug_dishes:                  # loops 3 times → 3 .s4dr rows
    _nb = escape(_d.get("name") or "")  # name pre-filled ✓
    _ib = ...                           # ingredients pre-filled ✓
    _sp = ...                           # protein pre-filled ✓
    # <select data-role="cat">          # NO option pre-selected ← HERE
    f'{_S4_CAT_OPTS_HTML}'
```

`_S4_CAT_OPTS_HTML` starts with `<option value="">— category —</option>`.  
No code selects the stored `_d.get("category")` value in the rendered `<select>`.

---

## The actual remaining bug: categories are blank on revert

### What Lauren sees

All 3 rows appear with names filled in. The category dropdown on every row shows `— category —` (value `""`).

### What happens when she hits Keep

`s4Keep` reads:
```javascript
var cat = (catEl ? (catEl.value||'').trim() : '');
if(!cat){ ... blocked = 'Pick a category for "Roast chicken".'; break; }
```

Fires immediately on row 1. She must re-select a category for each of the 3 dishes before she can Keep.

### Why this might look like "dishes lost"

- She expects Change to let her "tweak and re-Keep" — instead it blocks.
- The error message mentions only dish 1 ("Roast chicken"), so it's not obvious that rows 2 and 3 also need categories.
- Under the D7 jsdom diagnostic there was scroll-shift too; if the blocked row jumps out of view, rows 2-3 may not be visible at the moment of the error.

### The code comment that locked in this behavior

```python
# line 365–366
# category is intentionally left unselected per Lauren's rule —
# she always picks category explicitly, even on revert (not an exception).
```

This was recorded as a design decision at Phase C2 time. The diagnostic reveals it is the root of the remaining friction.

---

## What Phase C2 fixed vs. what it left

| | Before C2 | After C2 |
|---|---|---|
| Row count on revert | 1 (only `_sug_dishes[0]`) | 3 ✓ |
| Names pre-filled | row 1 only | all 3 ✓ |
| Categories pre-selected | no | no ← still missing |
| Immediate re-Keep possible | no (only 1 row) | no (all blank cats) |

---

## Recommended fix (not implemented — awaiting instruction)

In the prefill loop, emit `selected` on the matching `<option>` for each dish's stored category:

```python
_dc = escape(_d.get("category") or "")
# Instead of a raw _S4_CAT_OPTS_HTML, build options with selected:
# <option value="main" selected>main</option>  (if _dc == "main")
```

This would make Change a true "edit in place" — all fields (name, ingredients, protein, **category**) restored — and re-Keep would work without re-selecting anything.
