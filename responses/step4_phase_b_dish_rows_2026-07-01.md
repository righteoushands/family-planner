# Step 4 Phase B — client-side repeatable dish rows (2026-07-01)

This is a distinct phase from Phase A (not an unfinished A). Phase A wired the
wire shape (flat → `dishes[]`) as a migration step with a hardcoded `category:'main'`.
Phase B replaces that hardcoded default with a real per-row UI: a category `<select>`
that Lauren must fill explicitly on every row, including the pre-filled Lorenzo row.

---

## What changed — `render_meal_wizard_step4.py`

### New style constants (after `_S4_MSG`)
```python
_S4_SELECT       # _S4_INPUT + cursor:pointer  (select looks like the other inputs)
_S4_DISH_ROW_INNER  # top border + padding — visual separator for added rows
_S4_REMOVE_BTN   # small gray "Remove" button
_S4_ADD_BTN      # gold-outlined "+ Add a dish" button
```

### `_S4_CAT_OPTS_HTML` (module-level constant)
Built from `CATEGORIES` once at import time; used identically in the rendered
first row AND the hidden `#s4-dish-template`, so the option list is always in sync:
```python
_S4_CAT_OPTS_HTML = (
    '<option value="">— category —</option>'
    + "".join('<option value="' + c + '">' + c + '</option>' for c in CATEGORIES)
)
```

### `_S4_JS` — `s4Keep` rewritten + two new functions added

**`s4Keep`** now scans `#s4-dishes--{key} .s4dr` rows instead of reading three
named inputs:
- For each row: read name via `[data-role="name"]`; blank name → drop silently
- If name present but `[data-role="cat"]` is empty → set `blocked` message
  `'Pick a category for "…".'` and break — no fetch sent
- If all named rows pass → build `dishes[]` array; if none survive → block with
  `'Add a meal name first.'` (same as before)
- Payload is `{date, slot, dishes:[...], source, recipe_id, recipe_on_request}`

**`s4AddDish(date, slot)`** (new):
- Finds `#s4-dish-template .s4dr`, clones via `cloneNode(true)`
- Clears all `input/textarea/select` values in the clone
- Shows the Remove button (`rm.style.display = ''`)
- Appends to `#s4-dishes--{key}`

**`s4RemoveDish(btn)`** (new):
- Finds the parent `.s4dr` row; removes it only if `≥ 2` rows remain
  (enforces the one-row minimum)

### `_s4_slot_block` — empty-slot branch

The single name/ing/prot trio is replaced by:
```
<div id="s4-row--{key}">
  {label_html}
  <div id="s4-dishes--{key}">
    <div class="s4dr">               ← row 0 (Remove button: display:none)
      <select data-role="cat">…</select>
      <textarea data-role="name">…</textarea>
      <details><summary>Ingredients</summary>
        <textarea data-role="ing">…</textarea>
      </details>
      <input data-role="prot">
      <button data-role="rm" style="display:none">Remove</button>
    </div>
  </div>
  <button onclick="s4AddDish(…)">+ Add a dish</button>
  <button onclick="s4Keep(…)">Keep this meal</button>
  <div id="s4-msg--{key}"></div>
</div>
```

Pre-fill (Lorenzo suggestion): `name_body`, `ing_body`, `prot_val` still filled
from `slot_dishes(suggestion)[0]`; category left at placeholder — Lauren picks it.

### `render_meal_wizard_step4` — `#s4-dish-template` added to body

A hidden `<div id="s4-dish-template">` is appended to the page body (before
`_S4_JS`). It contains one `.s4dr` row with `_S4_DISH_ROW_INNER` styling and the
Remove button **visible** (so every clone shows it; only the rendered first row
has `display:none`).

---

## Harness update — `verify_meal_wizard_step4_writeloop.py`

The remove-path entry-state check used `s4-name--{key}` as its "we're in entry
state" indicator. That ID no longer exists in Phase B (the name field now uses
`data-role="name"`). Updated both checks to use `s4-dishes--{key}` (the dish
container div), which is equally unambiguous: it only appears in the entry
affordance, never in the confirmed-row view.

---

## `py_compile` — OK

```
render_meal_wizard_step4.py — OK
```

---

## Smoke test — 4 cases (all PASS)

```
CASE 1 (one row, category selected): PASS
  status: 200 | dishes stored: [{'category': 'main', 'name': 'Chicken Parm',
                                   'ingredients': 'pasta', 'protein': 'chicken'}]

CASE 2 (three rows, all categorized): PASS
  status: 200 | dishes stored: [('main', 'Roast chicken'),
                                  ('side', 'Roasted broccoli'),
                                  ('bread', 'Sourdough slice')]

CASE 3 (name no category — client blocks; HTML/JS verified): PASS
  has cat select:      True
  has cat options:     True
  has blocking msg:    True   ("Pick a category for …" in _S4_JS)
  has dishes container: True

CASE 4 (blank row dropped silently, valid row kept): PASS
  status: 200 | dishes stored: [{'category': 'main', 'name': 'Turkey wrap',
                                   'ingredients': '', 'protein': 'turkey'}]
```

---

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

---

## Files changed
- `render_meal_wizard_step4.py` — 4 new style constants, `_S4_CAT_OPTS_HTML`,
  `s4Keep` rewrite, `s4AddDish` + `s4RemoveDish` added, `_s4_slot_block` empty
  branch replaced, `#s4-dish-template` added to page body
- `data/verify_meal_wizard_step4_writeloop.py` — entry-state detector updated
  from `s4-name--` to `s4-dishes--` (Phase B ID change)
