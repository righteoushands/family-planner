# Diagnosis: does /meal-wizard-generate wipe the confirm-mirror? (2026-07-01)

## Q1 — wholesale replace or merge? WHOLESALE REPLACE (read from source)

`data_helpers.update_meal_wizard_session` (3312–3317):

```python
def update_meal_wizard_session(updates: dict) -> dict:
    """Merge updates into current session state and save. Returns updated session."""
    session = load_meal_wizard_session()
    session.update(updates)          # top-level dict.update ONLY
    save_meal_wizard_session(session)
    return session
```

`session.update(updates)` is a shallow, top-level merge. `suggested_meals` is a
single top-level key, so `update_meal_wizard_session({"suggested_meals":
_g_suggestions})` in the generate handler swaps the ENTIRE `suggested_meals`
value for `_g_suggestions`. The inner `date::slot` entries are NOT merged — any
key not present in `_g_suggestions` is dropped. (Other top-level keys such as
`confirmed_meals` are preserved; only `suggested_meals`' contents are replaced.)

## Q2 — isolated end-to-end test: does the mirror survive generate? FAIL

Harness `data/verify_generate_wipes_mirror.py` (Rule 10a: isolation imported
first, in-process server; Anthropic call / API-key / gen-log stubbed at the
boundary so the run is offline+deterministic — the `suggested_meals` write path
under test runs for real).

```
(1) confirm dinner -> 200 True
    suggested_meals[2026-06-29::dinner] (mirror):
      {"dishes": [{"category":"main","ingredients":"","name":"Chicken Parm","protein":"chicken"}]}
    suggested_meals keys: ['2026-06-29::dinner']
    mirror present after confirm: True

(2) generate -> 200 ok= True generated= 1 target= 1

(3) suggested_meals keys after generate: ['2026-06-29::lunch']
    suggested_meals[2026-06-29::dinner] after generate:
      null
    mirror survived generate: False

RESULT: FAIL (generate wiped the mirror)
```

## Why

`wizard_target_slot_keys` excludes any slot already in `confirmed_meals`, so a
confirmed slot (dinner) is never a generate target. Generate parses suggestions
for its targets only (lunch) and then REPLACES `suggested_meals` wholesale. The
dinner mirror is not in the new dict, so it is discarded as collateral.

## Practical consequence (no fix applied — reporting only)

The confirm-mirror is durable only until the next `/meal-wizard-generate`. Sequence
that loses it:
1. Confirm dinner (mirror written for dinner).
2. Generate other slots (e.g. lunch).
3. Press Change on dinner → `suggested_meals[dinner]` is gone → the slot reverts
   to the EMPTY entry state, not Lauren's last-confirmed "Chicken Parm".

So the "revert to last-seen value" guarantee holds within a generate cycle but is
erased by a subsequent generate. No change made.
