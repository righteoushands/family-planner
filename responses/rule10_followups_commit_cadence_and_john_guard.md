# Rule 10 follow-ups — commit cadence / provenance blind spot, and the `/john` guard

Two honest answers, both backed by commands I actually ran.

---

## Q1 — Is the session file committed on every write? Does a disk-vs-git window exist?

**No, it is not committed per write — and yes, the window you suspected is real.
Right now it is non-empty.** You were correct that my earlier provenance chain
had a blind spot.

### The cadence, precisely
- The app writes `data/meal_wizard_session.json` through `safe_save_json`
  (`data_helpers.save_meal_wizard_session` → `safe_utils.safe_save_json`). That
  write hits disk **immediately**, on every save. Given your "Auto-Save
  Everything" preference, the wizard saves often.
- Git commits happen only at **Replit checkpoints** — the end of an agent
  loop/task — **not per write**. So writes vastly outnumber commits. They are
  **not** 1:1.

### Live proof the window is real *right now*
```
git status --porcelain data/meal_wizard_session.json   ->   M data/meal_wizard_session.json
live sha256:  2bfd92afb9f0690a82452595b88d7f21ac1c1cff56b689fecad539f8ad288aff
HEAD sha256:  83dcfb59740f8918d00304cb11a4133b54148a03ef358ad48367ffa245de9661
```
The on-disk file **differs from git HEAD** at this moment. Since my last
checkpoint, the running app wrote new wizard state to disk that git does not yet
have. It is legit data, not pollution:
```
keys: confirmed_inventory, use_soon_items, confirmed_what_to_plan,
      confirmed_complexity, planning_window, confirmed_meals,
      suggested_meals, used_proteins, plan_locked_at
confirmed_meals: 5    plan_locked_at: '2026-06-30'
grep 'Probe Meal' (live + all history snapshots)  ->  none
```

### The honest admission
My previous provenance proof compared **live disk vs git history only**. Because
writes ≠ commits, that check *cannot* see any legit runtime write that landed
after the last checkpoint but before my probe. The original incident's proof was
stronger precisely because it compared against the **app's own pre-overwrite
snapshot**, which does not depend on git timing.

### The mitigation that closes the blind spot
The app keeps that exact class of evidence, independent of git.
`safe_save_json` calls `snapshot_before_save(path)` **before every overwrite**
(`safe_utils.py:80-81`), archiving the prior content to
`data/history/meal_wizard_session__<timestamp>.json` (up to 30 kept; the session
file is not on the snapshot deny-list). This trail:
- is written by the app at runtime, not by git, so it captures the states that
  live *inside* the disk-vs-git window;
- shows the value I restored to (`83dcfb59…`) appearing as genuine pre-write
  snapshots (`…T07-14-28`, `…T07-14-34`), i.e. it was a real app state, not a
  fabrication;
- shows the app then evolving *forward* from that state
  (`83dcfb59 → 3e2f17ec → 2bfd92af`), which means the git-based restore was a
  valid continuation point — the app picked it up and kept going, no legit write
  was stranded.

**Takeaway for the tracker:** the correct provenance standard for this file is
the `data/history/` snapshot trail, not git HEAD. Git alone is necessary but not
sufficient because of the checkpoint cadence. I have recorded this so future
verification uses the snapshot trail.

**On the current uncommitted diff:** I am deliberately **not** reverting it.
It is legit live-app data; overwriting git-tracked runtime state with an older
committed version is exactly the failure mode the original incident was about.
The next checkpoint will commit it normally.

---

## Q2 — Prove no harness hits `/john`, and make it durable

### Proof (shown, not asserted)
```
rg '/john|render_john'  (all three harness files)   ->   ZERO hits
```
Every "john" string in the harnesses is slot **data** (`johns_lunch`,
`"Leftovers for John"`), never the `/john` route or the `render_john` module.
`render_john` is invoked only at `app.py:1158` for the `/john` route, which no
harness requests. The homepage meal card the lock harness asserts against reads
through `render_meals.load_meal_plan`, which **does** honor `MEAL_PLAN_DIR`.

### Durable loud-fail guard (added)
Both HTTP harnesses now carry a module-level guard, called as the **first line**
of both `_get` and `_post`, so it runs before any request object is built:
```python
_UNISOLATED_ROUTES = ("/john",)

def _forbid_unisolated_routes(path):
    for r in _UNISOLATED_ROUTES:
        if path == r or path.startswith(r + "/") or path.startswith(r + "?"):
            raise AssertionError(
                "Rule 10 guard: harness must not request " + repr(path) + " -- "
                "render_john.py reads the live meal_plan path directly (not "
                "MEAL_PLAN_DIR), so that route is NOT isolated. Redirect "
                "render_john before removing this guard."
            )
```
Files: `data/verify_meal_wizard_step4_lock.py`,
`data/verify_meal_wizard_step4_writeloop.py`. (The third harness,
`verify_meal_wizard_step4.py`, makes **no** HTTP calls at all — it renders
directly — so the route is physically unreachable there.)

### Guard verified
```
legit paths (/meal-wizard-step4, /meal-wizard-step4-confirm, /api/meals,
             /johns-something-else)      -> all pass (no false trigger)
/john, /john/, /john?x=1                 -> guard fired 3/3 in BOTH harnesses
```

---

## Full regression — live data still untouched
```
                         before            after
live session sha    2bfd92afb9f0690a  2bfd92afb9f0690a   (identical)
meal_plan digest    cb01e8cb39d94a73  cb01e8cb39d94a73   (identical, 25 files)

verify_meal_wizard_step4.py            -> PASS
verify_meal_wizard_step4_lock.py       -> PASS
verify_meal_wizard_step4_writeloop.py  -> PASS  (write-loop + guard checks)
```

## Change set (test harnesses only; no production code)
`data/verify_meal_wizard_step4_lock.py`,
`data/verify_meal_wizard_step4_writeloop.py`. Architect review: **PASS** — guard
correctly placed before any I/O, cannot false-trigger, isolation not weakened.
