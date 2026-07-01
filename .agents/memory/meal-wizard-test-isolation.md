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
