# Meal slots: flat → `dishes[]` data-contract change — complete & verified

## What changed (backend-only, read-time migration)

Meal-wizard slot entries moved from the old flat shape to a nested one:

- **Old:** `{name, ingredients, protein, note}`
- **New:** `{dishes: [{category, name, ingredients, protein}], note, ...meta}`

No data files were rewritten. Old flat entries — and even bare-string legacy
values — migrate **on read** through one helper, `data_helpers.slot_dishes(entry)`.

### Write paths now produce `dishes[]`
- `/meal-wizard-step4-confirm` handler (app.py)
- Step 3 prefill builder (app.py)
- `parse_wizard_meal_response` (generator) wraps AI output into `dishes[]`; `note`
  stays top-level. Prompt builder reads through `slot_dishes`.

### Read paths now migrate via `slot_dishes`
- `recompute_used_proteins` iterates each dish's protein.
- `render_meals.apply_confirmed_meals_to_store` collapses a slot's dishes into one
  display string via the new `format_dish_list` (lead = mains, else soups, else
  none; rest = other dishes in order; lead joined with " and "; rest a
  no-Oxford-comma list; combined "lead with rest"). The day-template store stays a
  single flat string per slot.
- Step 4 confirmed-meal display.

## Code-review fixes (caught two real regressions)

The architect review surfaced that my in-scope write changes had broken two reads in
`render_meal_wizard_step4.py` that still assumed the flat shape:

1. **Lockability gate** ("Set this plan") read `entry.get("name")` — now empty on the
   new dishes-shaped confirmed entries, so the button could be wrongly suppressed.
2. **Lorenzo suggestion prefill** read `suggestion.get("name"/...)` — generated
   suggestions are now dishes-shaped, so the inputs would silently fail to prefill.

Both now read through `slot_dishes`. (The review's other two points — bare-string
handling in `apply_confirmed_meals_to_store` and a "junk → empty dish" contract note
— were not real issues: confirmed entries are never bare strings in any write path,
and `slot_dishes` correctly returns a safe `[]`, as its docstring states.)

### Scope note / deviation
The spec said "don't touch `render_meal_wizard_step4.py`." I had to touch it — first
for the confirmed-display read, and now for the lockability gate and suggestion
prefill — because the **in-scope** write-shape changes broke those reads. The
remaining Step 4 input affordances were already on the new path. This is the
universal read-time-migration rule in action: a data-contract change must sweep every
downstream read.

## Verification — all green

| Harness | Result |
|---|---|
| `verify_meal_wizard_gen.py` (incl. old-flat migration in prompt) | PASS |
| `verify_meal_wizard_dish_join.py` (8 display cases + edges + migration) | PASS |
| `verify_meal_wizard_g1a.py` (recompute + confirm shape) | PASS |
| `verify_meal_wizard_step3.py` (prefill shape) | PASS |
| `verify_meal_wizard_step4.py` (read-only, mixed shapes) | PASS |
| `verify_meal_wizard_step4_writeloop.py` (HTTP round-trip) | PASS |
| `verify_meal_wizard_step4_lock.py` (HTTP, dishes-shaped fixtures) | PASS |

Test fixtures were updated to seed at least one `dishes[]`-shaped entry per harness
(flat-only fixtures pass via migration and would mask a regression back to flat
reads). `py_compile` clean across all source and harness files.

## Rules honored
- Python 3.11: no backslashes in f-strings, imports at top, no walrus in f-strings.
- `data_helpers.py` remains the only JSON reader/writer; `config.py` owns paths.
- Routing `elif` chains untouched.
