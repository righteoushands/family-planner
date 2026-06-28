---
name: Meal store & homepage gating
description: How wizard meals reach the homepage meal card, and why there is no plan-level "locked" flag.
---

The canonical meal store is `data/meal_plan/<Monday-ISO>.json`, shape
`{start, week, generated, days:{WeekdayName:{slot:""}}}`. The homepage meal card
(`render_timeblock._render_meals_snapshot`) reads TODAY's Monday week and gates
**only on non-empty slot text** — NOT on `generated` and NOT on any lock flag.

**Why:** writing a slot's text is sufficient to surface it on the homepage, so a
"Set this plan" lock just needs to write the confirmed meals into the store
(additively, per `days[Weekday][slot]`) and leave `generated` untouched. There is
deliberately **no plan-level "locked" flag** in the store; the wizard session
carries `plan_locked_at` instead and is kept revisitable (not cleared).

**How to apply:** the Meal Wizard "lock" step persists confirmed meals via
`render_meals.apply_confirmed_meals_to_store`. Wizard→store slot mapping lives in
`_WIZARD_TO_STORE_SLOT` (e.g. `johns_lunch → dad_lunch`); `feast_meal`/`batch_cook`
have no store home and are skipped, as are `source=='prefill'` entries. The block
shown on the homepage depends on time of day (`render_timeblock._resolve_block`),
so any round-trip test that asserts homepage visibility must compute the current
block and lock a meal in the slot/date that block surfaces.
