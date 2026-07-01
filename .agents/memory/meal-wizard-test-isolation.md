---
name: Meal-wizard session test isolation
description: How to run the meal-wizard harnesses without ever touching live session data (Rule 10), and why in-process servers are required.
---

# Isolating MEAL_WIZARD_SESSION_FILE during tests

`config.MEAL_WIZARD_SESSION_FILE` reads from the env var of the same name
(default = live path). `data_helpers` binds that name at import, so setting the
env var **before** `config`/`data_helpers` are imported redirects every session
read/write for the whole process. `data/mw_test_isolation.py` does this at its
own import time and must be the first project import in a harness (before
`config`); it also exposes `assert_isolated()` (hard guard) and `start_server()`.

**Why HTTP harnesses must use an in-process server, not a subprocess:**
`app.py`'s `__main__` is a hard singleton — it SIGKILLs any prior PID
(`/tmp/family_dashboard.pid`) and owns port 5000 (`allow_reuse_port=False`). A
second `python app.py` would kill the live workflow. Instead run `app.Handler`
in a threaded `HTTPServer` **inside the harness process** so it shares the same
env-redirected session path; the live :5000 server is never contacted.

**Why:** an ad-hoc smoke test once wrote the live session file via
`safe_save_json` and wiped real data. True Rule 10 = never touch the live file,
not snapshot+restore.

**How to apply:** any new meal-wizard harness — import `mw_test_isolation`
first, call `assert_isolated()`, and (for HTTP) use `start_server()`; do NOT
snapshot/restore the session file. `meal_plan` week files are a separate concern
and still need their own snapshot/restore. Beware: probing an in-process server
BEFORE the config env-override exists will write live data (config falls back to
the default path).

## meal_plan store isolation (extends the session-file pattern)
`render_meals.py` keeps its OWN `MEALS_DIR` (does not import config's), and
`render_john.py` hardcodes `data/meal_plan/{wk}.json` inline. To isolate the
lock harness's week-file writes, `MEALS_DIR` in BOTH `config.py` and
`render_meals.py` reads env var `MEAL_PLAN_DIR` (default `data/meal_plan`);
`mw_test_isolation` points it at a temp `mkdtemp` (cleaned via `shutil.rmtree`
at exit) before those modules import. The lock harness then needs NO
snapshot/restore of live week files. `.backups` rotation lands inside the temp
dir and is discarded with it. `render_john` is intentionally left un-redirected:
it's only hit on the `/john` route, which no harness calls (the homepage meal
card reads via `render_meals`, so it honors the redirect). `assert_isolated()`
guards all three sinks: session file, `render_meals.MEALS_DIR`, `config.MEALS_DIR`.
**Why:** the lock harness previously touched live week files then restored them —
same touch-then-restore pattern the session fix eliminated; full Rule 10 = never
touch, not restore-after.

## Provenance standard for JSON data files (git is NOT sufficient)
Writes via `safe_save_json` hit disk immediately; git commits only at Replit
**checkpoints** (end of agent loop), so writes ≠ commits and a disk-vs-git window
always exists (the live file routinely shows ` M` vs HEAD with legit uncommitted
app data). Verifying a restore against **git HEAD only** has a blind spot: it
cannot see legit runtime writes made after the last checkpoint. The correct,
git-independent evidence is the app's own pre-overwrite snapshot trail:
`safe_save_json` calls `snapshot_before_save` before every overwrite, archiving
prior content to `data/history/<mirrored-path>__<ts>.json` (max 30/file; deny-list
in `safe_utils.py` — session file is NOT denied). Use that trail, not git HEAD, to
prove a value was a genuine app state. **Never revert a git-tracked data file to an
older committed version to "clean up" a diff** — that destroys legit runtime state
(the original incident's failure mode).

## Durable /john route guard in the HTTP harnesses
`render_john.py` is the one meal_plan reader NOT covered by `MEAL_PLAN_DIR` (it
hardcodes the live path). Both HTTP harnesses now define
`_forbid_unisolated_routes(path)` (blocks `/john`, `/john/…`, `/john?…`) called as
the first line of `_get`/`_post`, so any future edit that requests `/john` fails
loud instead of silently touching live data. Before ever testing `/john`, add
`MEAL_PLAN_DIR` support to `render_john.py` first, then relax the guard.
