# Step 4 — Snacks: category requirement exemption

**Date:** 2026-07-01  
**Files changed:** `render_meal_wizard_step4.py` (5 targeted edits)

---

## What changed and why

### Stored category: `'snack'`

`'main'` would lie about what the item is. `'snack'` is semantically correct
and now accepted server-side. `CATEGORIES` was extended to include it, so the
server coercion (`if _dcat not in _S4_CATEGORIES: _dcat = "main"`) passes it
through cleanly instead of silently flattening it.

### Category `<select>` for snacks: hidden (`display:none`), not omitted

The select is still present in the DOM — the JS reads `.value` from it,
gets `''`, and triggers the snacks-default path. But it's invisible to Lauren.
Leaving a required-looking dropdown on screen that validation then silently
ignores is confusing; hiding it is the minimum-diff fix that's consistent with
the template sharing all slot types.

---

## The five edits

**1. `CATEGORIES` tuple** — added `'snack'`:

```python
CATEGORIES = ("main", "side", "soup", "bread", "salad", "appetizer", "dessert", "snack")
```

**2. `_s4_slot_block`** — compute `_cat_display` once per call:

```python
_cat_display = "display:none;" if slot_key == "snacks" else ""
```

Applied to both the suggestion-prefill dish-row loop and the empty-row fallback:

```python
f'<select data-role="cat" style="{_cat_display}{_S4_SELECT}">'
```

**3. JS `s4Keep` validation** — snacks-exempt branch inside the `if(!cat)` test:

```javascript
if(!cat){
  if(slot === 'snacks'){ cat = 'snack'; }
  else { blocked = 'Pick a category for "' + n + '".'; break; }
}
```

Dinner, breakfast, John's Lunch, dessert, and all other non-snacks slots hit
the `else` branch unchanged.

**4. JS `s4AddDish`** — hide the cat select in cloned rows for snacks:

```javascript
if(slot === 'snacks'){
  var catSel = newRow.querySelector('[data-role="cat"]');
  if(catSel){ catSel.style.display = 'none'; }
}
```

Runs after `rm.style.display = ''` and before `container.appendChild(newRow)`,
so every row Lauren adds via "+ Add a dish" on the snacks slot is also select-free.

---

## Test results

### CSS/JS structural checks (5/5 PASS)

```
  PASS  CATEGORIES contains snack
  PASS  s4Keep: snacks-exempt before non-snacks blocked path
  PASS  s4AddDish: hides cat select for snacks
  PASS  snacks slot: cat select hidden in rendered HTML
  PASS  dinner slot: cat select NOT hidden
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

### Note on server smoke test

A bare ad-hoc POST (no session cookie) returned `302` as expected — the auth
guard fires before the handler. The writeloop harness covers the endpoint
end-to-end with proper auth; separate bare-POST checks are redundant here.
