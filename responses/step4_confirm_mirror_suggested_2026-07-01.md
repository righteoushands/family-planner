# Step 4 confirm → mirror into suggested_meals (2026-07-01)

## Diagnosis (requested first)

`window.s4Keep` sends **live textarea/input values** (Lauren's current edits/typed
text), NOT the original `suggested_meals` content. Values are read at click time
via `valOf(id)` → `el.value`. Exact JS (render_meal_wizard_step4.py, 211–232):

```javascript
  function valOf(id){ var el = elById(id); return el ? (el.value || '').trim() : ''; }
  ...
  window.s4Keep = function(date, slot){
    var key = date + '--' + slot;
    var name = valOf('s4-name--' + key);
    if(!name){ setMsg(msgId, 'Add a meal name first.'); return; }
    var ing = valOf('s4-ing--' + key);
    var prot = valOf('s4-prot--' + key);
    var payload = { date: date, slot: slot, name: name, source: 'manual',
      ingredients: ing, protein: prot, recipe_id: '', recipe_on_request: true };
    fetch('/meal-wizard-step4-confirm', ...
```

Condition met (live values) → additive write applied.

## Change applied (app.py, /meal-wizard-step4-confirm branch)

Load the session once; in addition to the unchanged `confirmed_meals` write,
mirror the just-saved `dishes[]` into `suggested_meals[date::slot]`:

```python
_s4_session = load_meal_wizard_session()
_s4_meals = _s4_session.get("confirmed_meals") or {}
_s4_meals[_s4_date + "::" + _s4_slot] = _s4_entry
_s4_suggested = _s4_session.get("suggested_meals") or {}
_s4_suggested[_s4_date + "::" + _s4_slot] = {"dishes": _s4_entry["dishes"]}
update_meal_wizard_session({
    "confirmed_meals": _s4_meals,
    "suggested_meals": _s4_suggested,
    "used_proteins":   recompute_used_proteins(_s4_meals),
})
```

## Verification (Rule 9 + Rule 10/10a)

- `py_compile app.py render_meal_wizard_step4.py` → OK.
- `data/verify_meal_wizard_step4_writeloop.py` (isolation-first, in-process
  ephemeral server) → **15 PASS, 2 FAIL**.

### The 2 failures are the intended behavior change, not a bug

Both remove-section checks fail only on their `"Chicken Parm" not in ..." clause:
- L210–214: `"Chicken Parm" not in _rj["slot_html"]`
- L217–219: `"Chicken Parm" not in html`

Before: confirm wrote only confirmed_meals → after remove `suggested.get(full)` was
None → blank slot → passed. After: confirm also mirrors dishes[] into
suggested_meals; remove pops only confirmed_meals, so the reverted slot now
pre-fills the last-seen value ("Chicken Parm"). This is exactly the requested
"revert to last-seen, not empty" behavior. The name-input id is still present in
both fragments; only the "must be blank" clauses fail.

## Open decision (flagged — out-of-scope second file)

Making the harness green requires editing
`data/verify_meal_wizard_step4_writeloop.py` to change those two assertions from
"returns to EMPTY entry state" to "returns to LAST-SEEN value in entry state".
That redefines the harness's guaranteed contract, so it is not done pending
confirmation. app.py change is in place and working.
