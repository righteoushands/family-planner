# Diagnosis: how the "standing set" of Step 4 verify harnesses actually gets run (2026-07-02)

## Part 0 — claud.md read-back (Rule 15)

All rules found (compressed but complete):

1. No backslashes inside f-strings
2. No nested quotes inside f-strings — use a variable outside
3. GET routing = elif chains in do_GET; POST routing in do_POST ALSO elif chains
   (verified Jun 28 2026). One exception: multipart recipe routes share an outer
   elif-in block with nested ifs only for upload-parsing setup — do not copy.
4. No imports inside if blocks/functions [KNOWN DEVIATION: inline imports exist
   in live do_POST handlers; new code keeps imports at module top]
5. All file writes via safe_save_json — never open(f,'w')
6. No walrus operator
7. Never a raw \n inside a JS string within a Python string literal
8. multipart/form-data: sniff Content-Type, parse via cgi.FieldStorage
9. py_compile is syntax-only: run in-process smoke test after it, THEN run the
   relevant existing verify_phase_*.py harness for the area touched and paste
   the result; never skip for shared data files / save paths / multi-caller fns
10. Test fixtures never write live data; temp copies; restore after
10a. Isolation must be STRUCTURAL: mw_test_isolation-style guard as literal
   first project import, guard raises (not warns) on live path; snapshot-and-
   restore-after is NOT equivalent
11. Never double-escape HTML entities
12. Rule 7 applies to ALL files with JS embedded in Python
13. FROL nested-form addendum (action="/frol-wizard" suppresses Save/Continue)
14. PRE-FLIGHT CHECKLIST (files touched; JS-in-f-strings; forms; root cause
   confirmed vs assumed — if assumed, diagnose first; multi-file split; data
   shape before/after)
15. CLAUD.MD READ-BACK REQUIRED at session start
16. MAGNIFICA HUMANITAS DESIGN PRINCIPLES (tool not authority; companions serve
   real relationships; AI supports thinking; transparency; grace not
   performance; subsidiarity; digital wisdom)
17. ONE FIX PER INSTRUCTION; multi-file builds in sequential phases
18. AUGUST 15TH BUILD PLAN IS THE PRIORITY FILTER (Jun 1–Aug 15 2026)
19. BUILD FOR A FUTURE SECOND FAMILY (no hardcoded family; all I/O via
   data_helpers.py) [KNOWN DEBT: build_lorenzo_context roster]
20. PRESERVE SCROLL ON SAME-PAGE RELOADS (sessionStorage scrollY pattern;
   step4 is reference implementation)
21. SESSION HELPER SHALLOW-MERGE (read fresh -> merge -> write, immediately
   before the write)
22. MERGE-BASED GENERATE NO LONGER PRUNES (stale suggested_meals accumulate;
   logged not fixed; KI-001/KI-002)

Named sections: stack facts; People; Data file patterns; Route patterns
(_JSON_PATHS is LOCAL inside do_POST); Anchor-tag navigation; AI calls (models
not uniform; no universal JSON-repair helper); Change discipline (additive
changes; known-issues tracking is Lauren's, OUTSIDE the repo — never create
tracker/checklist files in the repo); FROL form bypass trap; DOC CORRECTION LOG.

Rules applying to THIS task (diagnosis-only):
- Rule 15 (read-back — done)
- Rule 14 item 4 (this prompt IS the confirm-root-cause diagnosis step)
- Rule 9 (the ONLY written "run the harness" obligation — per-area, singular;
  defines no standing set and no runner)
- Rules 10/10a (context on what the harnesses are)
- Change discipline (constrains any future fix: a runner SCRIPT is fine; a
  checklist/tracker DOC in the repo is not)
- Not applicable (no code changes): 1–8, 11–13, 16, 18–22

## Part 1 — Runner/checklist mechanism search

**No runner exists.** Evidence:

| Checked | Result |
|---|---|
| Makefile / makefile | does not exist |
| run_tests*, run_verify*, any runner | do not exist |
| Shell scripts (excl. .local/) | only scripts/post-merge.sh — 9 lines, echo-only, runs nothing |
| .replit | 0 references to verify_ |
| Workflows | app servers only; no verify refs |
| Harness cross-imports | none — no verify file references another |
| PROJECT_STATE.md §9 (lines 558–587) | inventory TABLE (path, lines, description); no run commands, no ordering |
| claud.md | Rule 9: "the relevant existing verify_phase_*.py harness for the area touched" — singular, judgment-based; no set defined |
| README | none in repo root |

scripts/post-merge.sh in full:

```bash
#!/bin/bash
set -e

# Post-merge setup for Sancta Familia family dashboard.
# This is a pure-Python app with no build step or package manager —
# no dependencies to install. This script is intentionally minimal.

echo "Post-merge setup complete."
```

Closest thing to "run together": responses/categories_consolidation_2026-07-02.md:124
`### verify_meal_wizard_step4_lock + writeloop — all PASS` — a one-time ad-hoc
run recorded in a report. Informal practice, not a mechanism.

Harness population (21 files, all in data/): verify_phase_{a–g}.py,
verify_meal_wizard_{g1a,gen,step3,step4,step4_lock,step4_writeloop,step4_remove,
dish_join}.py, verify_generate_{midcall_race,wipes_mirror}.py,
verify_mirror_neighbor_untouched.py, verify_rule10a_badorder_fixture.py,
verify_task_42.py; plus guard module mw_test_isolation.py.

## Part 2 — Every file containing "verify_meal_wizard_step4_remove" (besides its own)

Exactly 4:

1. PROJECT_STATE.md — line 582 (§9 inventory row) and line 614 (rev-2 change
   log row). Documentation only.
2. responses/verify_step4_remove_harness_2026-07-02.md — the build-session
   response doc reporting the 10 PASS checks.
3. responses/project_state_regen_rev2_2026-07-02.md — the PROJECT_STATE rev-2
   regeneration response doc (lines 10, 20, 49).
4. data/server.log — lines 3689, 3692: traceback frames from an actual run
   (runtime residue, not a reference mechanism).

No .py, .sh, .replit, workflow, Makefile, or checklist file references it.

## Part 3 — Plain statement

**No runner or checklist mechanism exists anywhere in the repo.** The
"standing set" is not a system: it is 21 standalone scripts run manually, one
at a time, via `PYTHONPATH=. python3 data/verify_*.py`, with selection governed
only by claud.md Rule 9's per-area judgment call and the current session's
instruction. PROJECT_STATE.md §9 is a descriptive inventory that nothing
executes. Any impression of a standing suite comes from past response documents
reporting which harnesses a given session happened to run.
