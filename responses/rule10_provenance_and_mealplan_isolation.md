# Rule 10 — provenance proof + meal_plan store isolation

Answering all three before you close this out.

---

## 1. Provenance of the restored session file (same standard as the original incident)

**Exact source commit:** `5b6197e` — *"Diagnose UI blinking issue caused by full
page reloads"*. That is the last commit that changed the session file's content;
its git blob is `b3774e453b3c7cb91bf450d3433f34a9ff8ac437`.

**Proof it's byte-complete right now (not a statement — actual comparison):**

```
git show HEAD:data/meal_wizard_session.json | cmp  -> IDENTICAL (no differences)
live  sha256: 83dcfb59740f8918d00304cb11a4133b54148a03ef358ad48367ffa245de9661
HEAD  sha256: 83dcfb59740f8918d00304cb11a4133b54148a03ef358ad48367ffa245de9661
git status --porcelain data/meal_wizard_session.json  ->  (empty == matches HEAD)
```

**Proof nothing between that commit and now is missing** — the session blob hash
across every intervening commit:

| commit | subject | session blob |
|---|---|---|
| `5b6197e` | Diagnose UI blinking issue | `b3774e45…` |
| `9f7936a` (HEAD~1) | Confirm smoke test incident / restoration | `b3774e45…` |
| `c83c66e` (HEAD) | Improve meal wizard test isolation | `b3774e45…` |
| **live working tree** | (uncommitted) | **`b3774e45…`** |

Every hash is identical. Concretely this proves:
- The content came from `5b6197e` (the latest *legitimate* edit).
- My checkpoint `c83c66e` committed the **same** blob as its parent — i.e. it did
  **not** commit any of my earlier probe pollution.
- There is no legitimate session-file change between `5b6197e` and now that could
  have been dropped by the restore. The chain is unbroken.

(The blob `9b3121a…`, `9246123…`, `39e80ce…` seen on older commits `d3fd694`/
`45e9e5e`/`9c36b9f` are prior legit content that `5b6197e` superseded — all before
the restore point, none lost.)

---

## 2. The lock harness's live meal_plan touch — **fixed now** (not left alone)

You were right: `verify_meal_wizard_step4_lock.py` was still snapshotting and
restoring the live `data/meal_plan/*` week files — the same touch-then-restore
pattern the session fix eliminated. I applied the **same treatment** to the
meal_plan store instead of justifying the gap:

- **New env override `MEAL_PLAN_DIR`**, read by `MEALS_DIR` in **both** `config.py`
  and `render_meals.py` (the latter keeps its own `MEALS_DIR` and does not import
  config's, so both had to be updated). Unset in production → `data/meal_plan`,
  so runtime is unchanged.
- **`mw_test_isolation`** now redirects `MEAL_PLAN_DIR` to a private temp
  directory (via `mkdtemp`), cleaned up wholesale with `shutil.rmtree` at exit —
  its `.backups` rotation stays inside the temp dir and is discarded with it (this
  also ends the `.backups` churn the previous task had to hand-clean).
- **All week-file snapshot/restore was removed** from the lock harness — both the
  unit-test block and the round-trip block. It now writes into the throwaway temp
  store.
- **`assert_isolated()`** was extended to guard all three sinks:
  session file, `render_meals.MEALS_DIR`, **and** `config.MEALS_DIR` (realpath
  comparisons, so a path that merely resolves to the live dir still trips it).

**Why `render_john.py` is genuinely different (not just "out of scope"):** it
hardcodes `data/meal_plan/...` inline, but it is only invoked on the `/john`
route (`app.py:1158`). None of the three harnesses ever request `/john` — the
homepage meal card the lock harness asserts against reads through
`render_meals.load_meal_plan`, which honors the redirect. So `render_john` is
never on the harness's code path; leaving it is correct, not a loophole. (It is
noted in memory for whenever a `/john` harness is written.)

**Proof of full isolation** — a complete run of all three harnesses:

```
verify_meal_wizard_step4.py           -> PASS
verify_meal_wizard_step4_lock.py      -> PASS
verify_meal_wizard_step4_writeloop.py -> PASS

meal_plan store (all 325 files, combined digest)  -> UNTOUCHED
data/meal_wizard_session.json                     -> UNTOUCHED
stray temp: session=0  mealplan=0
```

The entire live meal_plan store is now byte-identical before/after, with no
snapshot/restore involved at all.

---

## 3. `assert_isolated()` runs before any write — confirmed by line order

In all three harnesses `assert_isolated()` is the **first executable statement**
in `main()`, before `start_server()` and before the first data write:

| harness | `assert_isolated()` | first write |
|---|---|---|
| `verify_meal_wizard_step4.py` | line 55 | `dh.clear_meal_wizard_session()` — line 59 |
| `verify_meal_wizard_step4_writeloop.py` | line 89 | `dh.clear_meal_wizard_session()` — line 97 |
| `verify_meal_wizard_step4_lock.py` | line 94 | `rm.apply_confirmed_meals_to_store(...)` — line 135 |

And it is defence-in-depth, not just ordering: if the env override didn't take
(e.g. a future edit imports `config`/`render_meals` before `mw_test_isolation`),
the guard **raises** rather than letting a live write happen.

---

## Change set (only these)

`config.py`, `render_meals.py`, `data/mw_test_isolation.py`,
`data/verify_meal_wizard_step4.py`, `data/verify_meal_wizard_step4_lock.py`,
`data/verify_meal_wizard_step4_writeloop.py`. Architect review: **PASS**.
