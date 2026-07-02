# Phase H (Step 5, shopping day) pre-spec diagnosis (2026-07-02)

## Part 0 — claud.md read-back (Rule 15)

All rules (compressed but complete):
1. No backslashes inside f-strings
2. No nested quotes inside f-strings — variable outside instead
3. GET routing = elif chains in do_GET; POST also elif chains in do_POST
   (verified Jun 28 2026); only exception is the multipart recipe routes'
   shared outer block — do not copy
4. No imports inside if blocks/functions [KNOWN DEVIATION: inline imports in
   live handlers; new code = module top]
5. All writes via safe_save_json — never open(f,'w')
6. No walrus operator
7. Never a raw \n inside a JS string in a Python string literal
8. multipart: sniff Content-Type, cgi.FieldStorage
9. py_compile is syntax-only: in-process smoke test after, then run the
   relevant verify harness for the area touched and paste the result
10. Test fixtures never write live data; temp copies; restore after
10a. Isolation STRUCTURAL: mw_test_isolation as literal first project import;
   guard raises; snapshot-and-restore-after NOT equivalent
11. Never double-escape HTML entities
12. Rule 7 applies to ALL files with JS in Python
13. FROL nested-form addendum (action="/frol-wizard" suppresses Save/Continue)
14. PRE-FLIGHT CHECKLIST (files touched; JS-in-f-strings; forms; root cause
   confirmed vs assumed; multi-file split; data shape before/after)
15. CLAUD.MD READ-BACK REQUIRED
16. MAGNIFICA HUMANITAS DESIGN PRINCIPLES (tool not authority; real
   relationships; AI supports thinking; transparency; grace not performance;
   subsidiarity; digital wisdom)
17. ONE FIX PER INSTRUCTION; sequential phases with compile check + report
18. AUGUST 15TH BUILD PLAN IS THE PRIORITY FILTER (Jun 1–Aug 15 2026)
19. BUILD FOR A FUTURE SECOND FAMILY (no hardcoded family; all I/O via
   data_helpers.py) [KNOWN DEBT: build_lorenzo_context roster]
20. PRESERVE SCROLL ON SAME-PAGE RELOADS (step4 = reference implementation)
21. SESSION HELPER SHALLOW-MERGE (read fresh -> merge -> write, immediately
   before write)
22. MERGE-BASED GENERATE NO LONGER PRUNES (stale suggested_meals; KI-001/002)
Named sections: stack facts; People; Data file patterns; Route patterns
(_JSON_PATHS is LOCAL inside do_POST ~3536; new JSON routes must be added);
Anchor-tag navigation; AI calls; Change discipline (additive; tracker lives
outside repo; modules <800 lines where possible); FROL form bypass trap;
DOC CORRECTION LOG.

Rules applying to this task / the coming Phase H spec:
- 15 (done), 14 (this IS the pre-flight), 9 + 10/10a (bind the Phase H
  harness), 21 (new scalar session key is safe under shallow-merge; note in
  spec), 3 + Route patterns (new /meal-wizard-step5* = elif; JSON POST into
  _JSON_PATHS), 17/18/19 (spec discipline). Not applicable: 1–2, 5–8, 11–13,
  16, 20, 22.

## 1. Actual keys in data/meal_wizard_session.json (live file read)

KEY COUNT: 9

| Key | Type | Current value/shape |
|---|---|---|
| confirmed_inventory | str | "Fridge:\n2 pounds of cooked ground beef\nrotisserie chicken\nraw bacon\ntwo romaine ..." |
| use_soon_items | str | "" |
| confirmed_what_to_plan | list (2) | ["lunch", "dinner"] |
| confirmed_complexity | str | "normal" |
| planning_window | dict (2) | {start_iso, end_iso} |
| confirmed_meals | dict (10) | keyed "YYYY-MM-DD::slot" |
| suggested_meals | dict (24) | keyed "YYYY-MM-DD::slot" |
| used_proteins | list (4) | ["eggs", "ground beef", "rotisserie chicken", "chicken"] |
| plan_locked_at | str | "2026-07-02" |

There is NO session-init/default dict in code — the session starts {} and keys
accrue only via the 6 update_meal_wizard_session call sites.

## 2. update_meal_wizard_session in full (data_helpers.py 3312–3317)

```python
def update_meal_wizard_session(updates: dict) -> dict:
    """Merge updates into current session state and save. Returns updated session."""
    session = load_meal_wizard_session()
    session.update(updates)
    save_meal_wizard_session(session)
    return session
```

Top-level shallow dict.update — Rule 21 applies to any nested value.

## 3. render_meal_wizard_step5.py

DOES NOT EXIST. Repo-wide glob returns zero files.

## 4. app.py routes containing "step5" or "shopping"

NONE. Case-insensitive grep of all of app.py returns only 3 non-route hits:
- 10745: "skip_shopping": True, "recipe_on_request": True,   (prefill entry, step3-save)
- 10813: # the wrong shopping/recipe flag.                   (comment, step4-confirm)
- 10837: "skip_shopping": _s4_as_bool(...)                   (per-slot field, step4-confirm)

Existing meal-wizard route chains for reference:
GET:  1307 /meal-wizard | 1326 /meal-wizard-step2 | 1336 /meal-wizard-step3 | 1347 /meal-wizard-step4
POST: 10658 step2-save | 10690 step3-save | 10768 step4-confirm | 10878 step4-remove | 10931 step4-lock | 10954 generate

## 5. confirmed_shopping_day / shopping_day / shopping_notes

NONE EXIST. Verified:
- Repo-wide grep: only hit is the prior diagnosis doc itself
  (responses/mw_session_field_diagnosis_2026-07-02.md:51-53) stating absence.
- config.py: zero hits for "shopping".
- data_helpers.py: zero hits for "shopping".
- data/meal_wizard_session.json: 25 hits, ALL the per-slot boolean
  "skip_shopping" inside confirmed_meals/suggested_meals entries — slot-level,
  not session-level, unrelated to a shopping day.

## Plain statement

No shopping-day key, no Step 5 renderer, no step5/shopping route, and no
session default dict exist. Phase H starts from a clean slate on all five
fronts.
