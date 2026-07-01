# Step 4 clear/Change split — real session data (2026-07-01)

Follow-up: (1) drop the `to_plan`-gate explanation (slots ARE rendering with
content). (2) Check `data/meal_wizard_session.json` `confirmed_meals` for the
tested days and report the REAL `source` per slot — do not infer. If not
`prefill`, the hypothesis is wrong.

## Real data (read from data/meal_wizard_session.json)

- **planning_window:** 2026-07-01 → 2026-07-02 (the days Step 4 renders)
- **confirmed_what_to_plan:** breakfast, lunch, dinner, johns_lunch, snacks, dessert (all six — nothing gated out, so the `to_plan` explanation is dropped)
- **plan_locked_at:** 2026-06-30
- **used_proteins:** ['eggs']

### confirmed_meals — 1 entry total

| Key | source |
|---|---|
| `2026-06-29::breakfast` | `manual` |

2026-06-29 is OUTSIDE the planning window, so it never renders on the tested days.

### suggested_meals — 9 entries, all source='lorenzo'

| Date | Slots WITH a suggestion | Slots with NO suggestion |
|---|---|---|
| 2026-07-01 | breakfast, lunch, johns_lunch | dinner, snacks, dessert |
| 2026-07-02 | breakfast, lunch, dinner, johns_lunch, snacks, dessert | — |

## Verdict

**The `source == "prefill"` hypothesis is WRONG.** For the tested days there are
zero `prefill` entries — in fact zero `confirmed_meals` entries at all. The only
confirmed meal anywhere is `manual` on a non-rendering date.

## What the data actually shows (matches Lauren's report)

The slots rendering "with content" on 07-01/07-02 are `suggested_meals` (Lorenzo
drafts), NOT confirmed meals. Since `confirmed.get(key)` is None for every
07-01/07-02 slot, each renders via the empty-slot branch of `_s4_slot_block`
(line 290, `if not isinstance(entry, dict)`) — a textarea pre-filled from the
suggestion + a "Keep this meal" button (`s4Keep` → `/meal-wizard-step4-confirm`).
No "Change" button, so `s4Change` / `/meal-wizard-step4-remove` is never involved
for these days.

The split matches 2026-07-01 exactly:
- breakfast / lunch / John's-lunch → have a Lorenzo suggestion → textarea filled
- dinner / snacks / dessert → NO suggestion → empty textarea

## Root cause direction (not a fix)

The difference is **which slots `/meal-wizard-generate` populated into
`suggested_meals`**, not the clearing path and not `source`. On 07-01 only 3 of 6
requested slots got a suggestion; on 07-02 all 6 did. Look upstream at
`wizard_target_slot_keys(session)` and/or `parse_wizard_meal_response(text, targets)`
in the generate handler — that is where the 3-of-6 split originates. Nothing changed.
