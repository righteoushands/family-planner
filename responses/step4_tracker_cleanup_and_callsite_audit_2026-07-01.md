# Tracker cleanup + session-helper call-site audit + harness live-data proof (2026-07-01)

## 1. Deleted duplicate tracker; recorded the convention

- **Deleted** `TRACKER_Known_Issues.md` (the file I created last turn). Confirmed gone.
- The canonical `TRACKER_Known_Issues_2026-07-01.txt` is **not in the repo** — that's the outside-repo convention Lauren manages, so nothing to reconcile there.
- **Added to `claud.md`** (Change discipline section) so it doesn't recur:

  > Known-issues tracking is Lauren's, and lives OUTSIDE the repo: the canonical
  > file is the dated `TRACKER_Known_Issues_YYYY-MM-DD.txt` she maintains (numbered
  > entries, Working Agreement convention). NEVER create a tracker or known-issues
  > file inside the repo (no `TRACKER_Known_Issues.md` etc.). If something needs
  > logging, say so in the response and let Lauren add it to her canonical file
  > herself.

**For your canonical .txt** (your call to add, not mine) — the two items I logged last turn are:
- Session helper shallow-merge wipes sibling keys (Rule 21). *Fixed at the one exposed call site.*
- Merge-based generate no longer prunes stale `suggested_meals` (Rule 22). *Logged, not fixed.*

## 2. Call-site audit — `update_meal_wizard_session` (report only, no fixes)

`update_meal_wizard_session` is the **only** load→`dict.update`→save session helper (`data_helpers.py:3315`, `session.update(updates)`). The planning-session helpers (`save/start/advance/clear_planning_session`, `data_helpers.py:2070–2118`) write/replace the **whole** session object (`save_planning_session(session)`; `advance` mutates the fully-loaded dict then saves it all) — no partial-nested-key shallow-merge, so **no Rule 21 exposure**.

All six `update_meal_wizard_session(...)` call sites (all in `app.py`):

| Line | Route | Value(s) passed | Nested map? | Reads fresh right before write? | Rule 21 exposure |
|---|---|---|---|---|---|
| 10679 | `/meal-wizard-step2-save` | `confirmed_inventory` (str), `use_soon_items` (str) | No — scalars | n/a | **None** — full-value scalar writes |
| 10755 | `/meal-wizard-step3-save` | `confirmed_what_to_plan` (list), `confirmed_complexity` (str), `planning_window` (complete 2-key dict), `confirmed_meals` (map) | Yes (`confirmed_meals`) | **Yes** — reads `confirmed_meals` fresh at 10749, rebuilds the full map, writes immediately | **None** — read-merge-write, no long op between |
| 10837 | `/meal-wizard-step4-confirm` | `confirmed_meals` (map), `suggested_meals` (map), `used_proteins` | Yes (both maps) | **Yes** — reads both fresh at 10829, adds one entry each, writes immediately | **None** — read-merge-write |
| 10884 | `/meal-wizard-step4-remove` | `confirmed_meals` (map), `used_proteins` | Yes (`confirmed_meals`) | **Yes** — reads fresh at 10882, pops one, writes; does **not** pass `suggested_meals` so that key is left untouched | **None** |
| 10919 | `/meal-wizard-step4-lock` | `plan_locked_at` (str) | No — scalar | n/a | **None** |
| 10986 | `/meal-wizard-generate` | `suggested_meals` (map) | Yes | **Yes — now** (this turn's fix; previously read the map from `_g_session`, a snapshot captured **before** the ~90s Anthropic call) | **Was the only exposure; now fixed** |

### Conclusion
- **`/meal-wizard-generate` was the sole call site with the Rule 21 sibling-wipe exposure**, and uniquely so: it was the only one that sourced the nested map from a **stale snapshot taken before a long-running (~90s) operation**. That's the exact amplification Rule 21 warns about — now fixed.
- Every other nested-map writer (**step3-save, step4-confirm, step4-remove**) already reads the map **fresh immediately before** the write and merges, with **no long-running op** between read and write. They comply with Rule 21 as written.
- **Residual note (out of Rule 21's scope, no fix requested/made):** all of these share the generic file read-modify-write race — `update_meal_wizard_session` has no lock/CAS, so two concurrent requests could still lose an update in the microsecond window between read and save. This is the general no-lock JSON race the architect flagged, **not** the stale-snapshot-across-a-long-call problem Rule 21 targets. None of the other sites has the ~90s amplification generate had. Flagging only; nothing changed.

## 3. Harness live-data proof — `verify_generate_midcall_race.py`

Measured `data/meal_wizard_session.json` (the live session file — Rule 10a target) immediately before and after running the harness:

```
=== BEFORE ===
mtime=2026-07-01 13:48:28.587794022 +0000  size=7094
82c37fa7c6f0e8204b08bdbf2da00d8c9a1a47468c9ce6ea414207a3b9c80177  data/meal_wizard_session.json

=== run: verify_generate_midcall_race.py -> EXIT=0, RESULT: PASS ===

=== AFTER ===
mtime=2026-07-01 13:48:28.587794022 +0000  size=7094
82c37fa7c6f0e8204b08bdbf2da00d8c9a1a47468c9ce6ea414207a3b9c80177  data/meal_wizard_session.json
```

**mtime, size, and sha256 all identical** → the live session file was not touched (not even opened for write). The harness's `mw_test_isolation` env-redirect (Rule 10a structural isolation) held — the run wrote only to the isolated temp path.

## Files touched this turn
- `TRACKER_Known_Issues.md` — **deleted**.
- `claud.md` — added the outside-repo known-issues convention (Change discipline).
- No application code changed; no fixes applied to any call site (report only, as requested).
