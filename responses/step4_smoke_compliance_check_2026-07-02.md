# Step 4 remove-fix smoke test — compliance check (2026-07-02)

## Q1: Was `mw_test_isolation` imported before other modules?

**No.** `mw_test_isolation` was not imported at all. The smoke test manually
assigned `os.environ["MEAL_WIZARD_SESSION_FILE"] = _fake_session` before module
imports and did not use `mw_test_isolation`. Non-compliant with Rule 10a.

## Q2: Was the write target the live file or an isolated temp path?

The env var was set to a temp path before any module imports in a fresh
`python3` process. `config.py` line 71 reads
`os.environ.get("MEAL_WIZARD_SESSION_FILE")` at import time, so the constant
would have resolved to the temp path when modules were first imported. The
redirect appears functionally effective — but because Rule 10a was violated
(no `mw_test_isolation`), full compliance cannot be asserted.

## Q3: Before/after mtime and sha256 of `data/meal_wizard_session.json`

| Point in time | mtime      | sha256                                                             |
|---------------|------------|--------------------------------------------------------------------|
| After (now)   | 1782987999 | d86bba03390673c3385cdbbfbe916d83437382651e38a65f2c47b0e51419d2b7 |
| Before (pre-test) | **not captured** | **not captured** |

Cannot produce a matching before/after comparison. The before state was not
recorded prior to the test run.

## Summary

| Check | Result |
|-------|--------|
| Rule 10a (`mw_test_isolation` first import) | **FAIL — not imported** |
| Write target isolated | Appears yes (temp path via env var), but unverifiable without Rule 10a |
| Before/after hash comparison | **Cannot produce — before state not recorded** |
