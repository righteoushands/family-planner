# Live session file hash check (2026-07-02)

## Result

| Field | Value |
|-------|-------|
| sha256 | `d86bba03390673c3385cdbbfbe916d83437382651e38a65f2c47b0e51419d2b7` |
| mtime (unix) | `1782987999` |
| mtime (human) | 2026-07-02 10:26:39 UTC |

## Does this match Lauren's current confirmed meals?

**Cannot confirm.** Reasons:

1. The before-hash was not recorded prior to the smoke test — no authoritative
   baseline exists for this session.
2. The smoke test was non-compliant (no `mw_test_isolation`), so whether writes
   reached the temp file or the live file cannot be proven, only inferred.
3. The mtime predates this session's work, which is consistent with the file
   being untouched by the smoke test — but that is not proof.

## Recommended action if integrity is in question

Inspect the file contents directly, or restore `data/meal_wizard_session.json`
from the checkpoint made immediately before this session's smoke tests
(`0e046e212e73634aeeb77e56713ba22a4dd08bc7`).
