# Rule 10 — full session-file isolation for the meal-wizard harnesses

**Done.** The three standing meal-wizard harnesses now never read or write the
live `data/meal_wizard_session.json` — not even to snapshot and restore it. A
full run of all three leaves the live file **byte-for-byte identical** (same
mtime, same sha256).

---

## What changed

**1. `config.py` — the override**
`MEAL_WIZARD_SESSION_FILE` now reads from the environment, defaulting to the
live path when unset:
```python
MEAL_WIZARD_SESSION_FILE = os.environ.get("MEAL_WIZARD_SESSION_FILE") or "data/meal_wizard_session.json"
```
Production is unaffected (env unset → live path). Because `data_helpers` binds
this name at import, setting the env var *before* `config` is imported redirects
every session read/write in the process.

**2. `data/mw_test_isolation.py` — new test-only helper (single purpose)**
- On import (which must come *before* `config`), it points
  `MEAL_WIZARD_SESSION_FILE` at a private `tempfile` and registers cleanup at
  process exit. Any value that resolves to the live file (empty, the literal
  default, or a path that normalizes to it) is treated as "no override" and
  replaced — defense-in-depth so a stray env value can't aim tests at live data.
- `assert_isolated()` — a hard guard that raises rather than run if the session
  path is not the isolated temp file.
- `start_server()` — starts an **in-process** HTTP server using the live
  `app.Handler` on an ephemeral loopback port. Running in the same process means
  it shares the redirected session path, so the two HTTP round-trip harnesses no
  longer touch the live `:5000` server at all.

**3. The three harnesses**
- `verify_meal_wizard_step4.py` (pure render), `..._writeloop.py` and
  `..._lock.py` (HTTP) all import `mw_test_isolation` first, call
  `assert_isolated()`, and had their live-session **snapshot/restore removed**.
- The two HTTP harnesses now POST to the in-process `start_server()` instead of
  `http://localhost:5000`.
- `..._lock.py` still snapshots/restores the `meal_plan` **week files** it
  writes — those are a separate concern, out of scope for this fix.

---

## Why in-process (not a second server)

`app.py`'s `__main__` is a hard singleton: it kills any prior PID and owns port
5000. A second `python app.py` would kill the live workflow. Running
`app.Handler` inside the harness process sidesteps the PID/port fight entirely
and — crucially — makes the server share the same env-redirected session path.

---

## Validation

All three run green, and the live session file is untouched:

```
verify_meal_wizard_step4.py           -> exit 0 -> PASS all G1b-1 read-only screen checks passed
verify_meal_wizard_step4_lock.py      -> exit 0 -> PASS all G1 lock checks passed
verify_meal_wizard_step4_writeloop.py -> exit 0 -> PASS all G1b-2a write-loop + guard checks passed

session mtime  before=1782871668 after=1782871668  UNTOUCHED
session sha256 IDENTICAL
stray temp session files: 0
```

Note: while probing the approach *before* the config change existed, an early
in-process test wrote the live session file (the exact Rule 10 hazard this fix
removes). That pollution and some incidental `meal_plan/.backups` rotation were
restored from `HEAD`, so the change set contains only the fix:
`config.py`, the three harnesses, and `data/mw_test_isolation.py`.
