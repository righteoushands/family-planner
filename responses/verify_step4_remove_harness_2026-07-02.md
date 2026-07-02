# verify_meal_wizard_step4_remove.py — new harness (2026-07-02)

## What was wrong

The 2026-07-02 smoke test for the `/meal-wizard-step4-remove` fix used a
manual `os.environ["MEAL_WIZARD_SESSION_FILE"] = _fake_session` before module
imports instead of importing `mw_test_isolation` — violating Rule 10a. It also
captured no before/after hash, so file integrity was never asserted as part of
the test itself.

## What was built

**New file:** `data/verify_meal_wizard_step4_remove.py`

- `import mw_test_isolation` is the literal first project import (Rule 10a),
  matching the pattern in `verify_meal_wizard_step4_writeloop.py` and
  `verify_meal_wizard_step4_lock.py`.
- `mw_test_isolation.assert_isolated()` called at the top of `main()`.
- In-process server via `mw_test_isolation.start_server()` — live `:5000` never
  contacted.
- `_sha256_live()` hashes `data/meal_wizard_session.json` (the actual live path,
  not the temp redirect) **before** any test work and **after** all test work;
  the assertion `hash_before == hash_after` is a test check, not a manual
  post-run step.

## Checks covered

| # | Check |
|---|-------|
| 1 | bad date → 400 {ok:false} |
| 2 | bad slot → 400 {ok:false} |
| 3 | absent slot → 200 {ok:true} (idempotent) |
| 4 | **mixed-origin case**: confirmed_meals has MAIN + SIDE (Lauren added the side manually); suggested_meals has only the MAIN. After remove, reverted HTML contains **both** dishes — the Lauren-only side is NOT dropped (came from `revert_dishes`, not the suggested fallback) |
| 5 | no-reload contract: `slot_html` + `lock_html` in response |
| 6 | confirmed slot gone from session after remove |
| 7 | INTEGRITY: sha256 of live `data/meal_wizard_session.json` identical before/after |

## py_compile + run result

```
py_compile: PASS
sha256 BEFORE: d86bba03390673c3385cdbbfbe916d83437382651e38a65f2c47b0e51419d2b7
PASS bad date -> 400 {ok:false}
PASS bad slot -> 400 {ok:false}
PASS absent slot -> 200 {ok:true} (idempotent)
PASS fixture: Roasted Sweet Potatoes absent from suggested_meals (confirms it can only come from confirmed entry, not fallback)
PASS mixed-origin remove -> 200 {ok:true}
PASS response contains slot_html and lock_html (no-reload contract)
PASS confirmed slot removed from session after remove
PASS reverted HTML contains the main dish (Brined Roast Chicken)
PASS reverted HTML contains the Lauren-only side (Roasted Sweet Potatoes) -- came from revert_dishes, not suggested
sha256 AFTER:  d86bba03390673c3385cdbbfbe916d83437382651e38a65f2c47b0e51419d2b7
PASS INTEGRITY: live session file hash identical before/after (before=d86bba03390673c3... after=d86bba03390673c3...)

PASS all step4-remove checks passed
```

10/10 checks passed. Before and after hash are identical
(`d86bba03390673c3385cdbbfbe916d83437382651e38a65f2c47b0e51419d2b7`).
