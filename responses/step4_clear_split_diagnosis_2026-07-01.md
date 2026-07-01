# Step 4 "Change/clear" split diagnosis — dinner/dessert/snack vs breakfast/lunch/John's-lunch (2026-07-01)

**Question:** Is the dinner/dessert/snack vs breakfast/lunch/John's-lunch clearing
difference in the `/meal-wizard-step4-remove` handler (app.py) or in the client-side
`s4Change` JS — show the exact branch (line numbers). Do NOT fix yet.

## Short answer

The split is in **neither** location. Both `/meal-wizard-step4-remove` and
`s4Change` are completely slot-agnostic — all six slots take the identical path.
There is no branch in either that separates the two groups.

## Client side — `s4Change` (render_meal_wizard_step4.py, lines 233–246)

```
233  window.s4Change = function(date, slot){
234    var key = date + '--' + slot;
237    var payload = { date: date, slot: slot };
238    fetch('/meal-wizard-step4-remove', { method:'POST', ...
```

`slot` is passed straight through from the onclick wired at line 352
(`change_call = "s4Change('" + date_iso + "','" + slot_key + "')"`), where
`slot_key` comes from the fixed `_S4_SLOT_ORDER` list (lines 45–51). No slot name
is inspected or special-cased. All six behave identically.

## Server side — `/meal-wizard-step4-remove` (app.py, lines 10852–10896)

The only place slot names appear is the validation allowlist:

```
10861  _S4R_SLOTS = {"breakfast","lunch","dinner","johns_lunch",
10862                "snacks","dessert","feast_meal","batch_cook"}
```

This is a membership gate only (line 10868: reject with 400 if
`_s4r_slot not in _S4R_SLOTS`). After that the removal is uniform for any slot:

```
10875  _s4r_meals = load_meal_wizard_session().get("confirmed_meals") or {}
10876  _s4r_meals.pop(_s4r_date + "::" + _s4r_slot, None)
10877  update_meal_wizard_session({... recompute_used_proteins(_s4r_meals) ...})
10884  _s4r_frag = render_step4_slot_and_lock(_s4r_date, _s4r_slot)
```

No `if slot == "dinner"` / `elif slot in (...)` anywhere in the handler.

## Where a slot-related difference actually could originate (lead only — not a fix)

Since neither clearing path branches by slot, an observed difference almost
certainly comes from **render time**, not the clear op. The two conditionals that
decide whether a slot even shows a "Change" button:

1. `_s4_slot_block`, line 349 — `if source == "prefill": change_html = ""`.
   Prefilled (past) meals render locked with NO Change button; every other
   confirmed meal gets one. This split is by `source`, NOT slot type — but if
   breakfast/lunch/John's-lunch are the slots carrying past/prefilled entries this
   week, they'd look "unclearable" while dinner/dessert/snacks show a Change button.
2. `_s4_day_card`, lines 403–404 — `for (slot_key, slot_label) in _S4_SLOT_ORDER:
   if slot_key not in to_plan: continue`. A slot appears only if it's in `to_plan`
   (Step 3's `confirmed_what_to_plan`).

**Conclusion:** The divergence is a render-time presence-of-control difference
(driven by `source == "prefill"` at line 349 and/or the `to_plan` gate at line 404),
not a clearing-logic difference. The remove operation itself is uniform across all
six slots. Nothing was changed.
