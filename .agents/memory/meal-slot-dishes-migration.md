---
name: Meal-wizard slot dishes[] read-time migration
description: The single read-time migration helper for meal-wizard slot entries, and which read paths must use it.
---

Meal-wizard `confirmed_meals` / suggestion slot entries carry the nested shape
`{dishes:[{category,name,ingredients,protein}], note, ...meta}`. Older entries on
disk are flat (`{name,ingredients,protein,note}`) or even bare strings.

`data_helpers.slot_dishes(entry)` is the SINGLE read-time migration helper:
dict-with-`dishes` → returns it; flat dict → one `main` dish; bare string → one
`main` dish; anything else → `[]` (always a list, safe to iterate). Stored data is
NEVER rewritten — migration is on read only.

**Rule:** every read of a slot entry's name/ingredients/protein must go through
`slot_dishes(...)`, never `entry.get("name")`. `render_meals.format_dish_list`
collapses a slot's dishes into one display string (lead = mains else soups else
none; rest = others in order; lead joined " and "; rest no-Oxford-comma; "lead
with rest"); the canonical day-template store stays a single flat string per slot.

**Why:** when the WRITE paths switched to `dishes[]` (the `/meal-wizard-step4-confirm`
handler, step3 prefill builder, and `parse_wizard_meal_response`), several reads in
`render_meal_wizard_step4.py` still did `entry.get("name")` and silently broke even
though that file was nominally out of scope — the lockability gate (suppressed "Set
this plan") and the Lorenzo suggestion prefill (empty inputs). A data-contract change
must sweep ALL downstream read paths, including ones in "don't touch" files.

**How to apply:** after changing any slot write shape, grep for `.get("name")` /
`.get("ingredients")` / `.get("protein")` on slot entries across app.py and every
render_meal_*.py and route them through `slot_dishes`. Test fixtures must seed at
least one `dishes[]`-shaped entry — flat-only fixtures still pass via migration and
will mask a regression back to flat reads.
