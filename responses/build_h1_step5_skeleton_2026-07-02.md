# H1 build report — Step 5 skeleton (shopping day) + Step 4→5 link (2026-07-02)

## Part 0 — claud.md read-back (Rule 15)

All rules (compressed but complete):
1. No backslashes inside f-strings
2. No nested quotes inside f-strings — variable outside instead
3. GET routing = elif chains in do_GET; POST also elif in do_POST (verified
   Jun 28 2026); only exception the multipart recipe routes — do not copy
4. No imports inside if blocks/functions [known deviation in old handlers;
   new code = module top]
5. All writes via safe_save_json — never open(f,'w')
6. No walrus operator
7. Never a raw \n inside a JS string in a Python string literal
8. multipart: sniff Content-Type, cgi.FieldStorage
9. py_compile is syntax-only: in-process smoke test after, then run the
   relevant verify harness for the area touched and paste the result
10. Test fixtures never write live data
10a. Isolation STRUCTURAL: mw_test_isolation as literal first project import;
   guard raises; snapshot-and-restore-after NOT equivalent
11. Never double-escape HTML entities
12. Rule 7 applies to ALL files with JS in Python
13. FROL nested-form addendum (action="/frol-wizard" suppresses Save/Continue)
14. PRE-FLIGHT CHECKLIST (files; JS-in-f-strings; forms; root cause; multi-file
   split; data shape)
15. CLAUD.MD READ-BACK REQUIRED
16. MAGNIFICA HUMANITAS (tool not authority; real relationships; AI supports
   thinking; transparency; grace not performance; subsidiarity; digital wisdom)
17. ONE FIX PER INSTRUCTION; sequential phases
18. AUGUST 15TH BUILD PLAN IS THE PRIORITY FILTER
19. BUILD FOR A FUTURE SECOND FAMILY (no hardcoded family; I/O via
   data_helpers.py)
20. PRESERVE SCROLL ON SAME-PAGE RELOADS (step4 = reference; forward
   navigations exempt)
21. SESSION HELPER SHALLOW-MERGE (scalar top-level key safe; nested = read
   fresh -> merge -> write)
22. MERGE-BASED GENERATE NO LONGER PRUNES (KI-001/002)
Named sections: Route patterns (_JSON_PATHS is LOCAL in do_POST — new JSON
routes must be added); Change discipline (additive; tracker outside repo);
AI calls; Anchor-tag navigation; FROL trap; Data file patterns; People.

Rules applied to THIS build: 15 (read-back), 14 (pre-flight was in the spec),
1/2 (style constants outside f-strings), 3 (both new routes are elif in the
existing chains), 4 (render_step5 + _S5_DAYS imported at app.py module top),
5 (write goes through update_meal_wizard_session -> safe_save_json),
7/12 (Step 5 JS is concatenated string literals, zero raw newline escapes),
9 (py_compile + isolated in-process smoke test, results below),
10/10a (smoke test imports mw_test_isolation as literal first project import;
sha256 proof), 16 (one-tap, changeable any time, no pressure language),
17 (H1 only — no conflict detection, no notes field, no Continue button),
19 (no family specifics; day list is a module constant; all session I/O via
data_helpers), 20 (forward nav Step4->Step5 = plain link, correctly exempt;
Step 5 save itself never reloads so no scroll issue exists), 21 (new key is a
top-level scalar — safe under the shallow merge).

## What was built (3 files, exactly per spec)

1. **render_meal_wizard_step5.py — NEW, 133 lines.** render_step5(user):
   Monday–Sunday picker (7 buttons, ids s5-day--<Day>), selected state read
   from confirmed_shopping_day; s5Pick(day) fetch()-POSTs {"day": d} to
   /meal-wizard-step5-save and swaps button styles in place (no reload,
   matching the s4Keep/s4Change async pattern). aria-pressed tracks selection.
   No conflict UI, no notes field, no Continue button.
2. **app.py — 4 edits:**
   - line 258: `from render_meal_wizard_step5 import render_step5, _S5_DAYS`
   - line 1358: `elif path == "/meal-wizard-step5":` (GET, matches the
     step4 block byte-for-byte in headers/auth/cache pattern)
   - line 3582: `/meal-wizard-step5-save` added to the local _JSON_PATHS set
   - line 11036: `elif path == "/meal-wizard-step5-save":` (POST) — parses raw
     JSON body, allowlists day against _S5_DAYS (400 {ok:false} otherwise),
     then `update_meal_wizard_session({"confirmed_shopping_day": day})`,
     returns {"ok":true}
3. **render_meal_wizard_step4.py — lines 707–718:** locked-plan banner now
   carries "Next: pick your shopping day →" linking to /meal-wizard-step5
   (forward navigation — Rule 20 exempt, as the spec noted).

## Validation results (Rule 9 — none skipped)

- **py_compile:** `python3 -m py_compile render_meal_wizard_step5.py
  render_meal_wizard_step4.py app.py` → **OK, all three files.**
- **Isolated smoke test** (ad-hoc per spec, mw_test_isolation as the literal
  FIRST project import, in-process server, deleted after the run) — **7/7 PASS**:
  1. PASS valid day -> 200 {ok:true}
  2. PASS confirmed_shopping_day == 'Wednesday'
  3. PASS no other session key changed (exact dict compare minus the new key)
  4. PASS bad day ("Blursday") -> 400 {ok:false}
  5. PASS session unchanged after bad day
  6. PASS GET /meal-wizard-step5 renders with Wednesday selected (exactly one
     aria-pressed="true")
  7. PASS live session file untouched — sha256 identical before/after:
     9088a81511e120e6096d3cd5be4f1ac04fbe5bc16a0462f8dbc36bf734b73e98
- **Live server:** restarted; GET /meal-wizard-step5 responds 302
  (auth redirect) exactly like /meal-wizard-step4 for an unauthenticated
  request — route live and gated identically.

## Exact new route line numbers (current app.py)

| Line | Route |
|---|---|
| 258 | module-top import of render_step5 + _S5_DAYS |
| 1358 | `elif path == "/meal-wizard-step5":` (GET) |
| 3582 | `/meal-wizard-step5-save` registered in _JSON_PATHS |
| 11036 | `elif path == "/meal-wizard-step5-save":` (POST) |

## Code review (architect): PASS

No blocking defects. Confirmed: JS concatenation of the CSS constants into
single-quoted JS literals is safe (no quotes in those constants); the
onclick unicode-escape pattern renders valid s5Pick('Day'); elif placement
non-disruptive; XSS surface low (fixed server-side day list + escaping +
server allowlist); no Step 4 regression.

Deferred (out of H1 scope per the spec, for future Phase H instructions):
- a standing verify_meal_wizard_step5.py harness (spec: not required for H1)
- optional: move the day allowlist to a shared non-render module constant

## Session key note (for the H2/H3 specs)

confirmed_shopping_day is now the 10th session key — a top-level scalar string
(one of the seven English day names), written only by /meal-wizard-step5-save.
PROJECT_STATE.md §8 not yet updated (that regen is its own instruction).
