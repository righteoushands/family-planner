# claud.md read-back, PROJECT_STATE.md verification, and Step 4 rule scope — 2026-07-01

## 1. claud.md — every rule, in full

### Python 3.11 hard rules — never violate these

1. No backslashes inside f-strings
2. No nested quotes inside f-strings — use a variable outside the f-string instead
3. All GET routing uses elif chains in do_GET — never a bare if, never nested if blocks for routing. POST routing in do_POST ALSO uses elif chains (`elif path == "/route-name": … return`) — the real convention in the live code, verified June 28 2026. The ONE exception is the multipart recipe routes (`/recipe-save`, `/recipe-import`): they share an `elif path in (...)` outer block with nested `if path == ...` inner blocks ONLY to share upload-parsing setup. Do NOT copy that nested pattern for ordinary JSON or form routes. *(Correction note June 28 2026: an earlier June 10 note claiming do_POST uses standalone top-level `if` blocks was wrong — code uses elif chains.)*
4. Never put import statements inside if blocks or functions. *(Known deviation, not a license: several live do_POST handlers use an inline `import json as _json` etc. New code keeps imports at module top; when editing an existing handler be aware the local convention already deviates.)*
5. All file writes use safe_save_json (tmp file + os.replace) — never open(f, 'w') directly
6. No walrus operator (`:=`)
7. Never use a raw newline inside a JS string within a Python string literal — use the escaped `\n` sequence so the browser receives the escape sequence, not a raw newline
8. multipart/form-data parsing: when fetch POSTs use FormData the server receives multipart/form-data, not urlencoded. The do_POST handler must sniff Content-Type and parse accordingly using cgi.FieldStorage for multipart. If a POST handler receives empty data, check the Content-Type first.
9. py_compile passes but runtime fails: py_compile only validates syntax, not runtime correctness. Always run an in-process smoke test after py_compile to catch NameError, missing variable definitions, and import failures. After the smoke test, also run the relevant existing verify_phase_*.py harness for the area touched and paste the result. Do not skip the harness for changes that touch shared data files, save paths, or any function called from more than one place.
10. test fixtures must never write to live data: verification harnesses must always operate on a temp copy of live data files. Never call save_progress, safe_save_json, or any write helper on live data during testing. Always restore from backup after any test that touches data files.
10a. **RULE 10 ADDENDUM — ISOLATION MUST BE STRUCTURAL, NOT PROCEDURAL.** Any verify_*.py harness that reads or writes app data must import its isolation guard (e.g. `mw_test_isolation.assert_isolated`) as the literal first import in the file — before data_helpers, config, or any render_*.py module. The guard must be called before the first write and must raise (not warn) if the write target still resolves to a live path. Snapshot-and-restore-after is NOT equivalent to never touching live data. When isolating a new data store, extend the existing isolation module's pattern (env-var override, defense-in-depth path normalization, assert_isolated) rather than writing a new one-off mechanism.
11. double-escaping HTML entities: never pass an already-HTML-escaped string through escape() again. Use plain ampersands in the source string and let escape() handle it once; pre-escaped `&amp;` strings render as visible `&amp;` if escaped twice.
12. JS newline in Python f-strings applies everywhere: Rule 7 applies to ALL files containing JS embedded in Python — render_schedule.py, render_timeblock.py, render_lucy.py, render_lorenzo.py, and any other render file with inline JavaScript, not just render_frol_wizard.py.
13. **FROL WIZARD NESTED FORM ADDENDUM** — The `_body_has_form` check in `_section_chrome` looks for `action="/frol-wizard"` in the body string. Any form inside a section body posting to /frol-wizard will suppress the Save and Continue button. Variant tab forms posting to /frol-set-variant are safe; activity builder forms posting to /frol-add-activity are safe. Before adding any form to a section body, confirm its action attribute. Recurring bug — document before fixing if it appears again.
14. **PRE-FLIGHT CHECKLIST** — Before writing any spec answer: (1) how many files does this touch — list them; if unknown, that's a diagnosis step first. (2) does it involve JavaScript inside Python f-strings — if yes, flag the newline rule explicitly. (3) does it touch form handling — if yes, confirm no nested forms posting to /frol-wizard. (4) is the root cause confirmed or assumed — if assumed, run diagnosis first; never draft a fix on an assumed cause. (5) does it touch multiple files — if yes, break into separate single-purpose instructions. (6) does it involve data-shape changes or migration — if yes, confirm before/after data structure explicitly before writing the spec.
15. **CLAUD.MD READ-BACK REQUIRED** — At the start of every session read claud.md and paste back every rule found. Then identify which rules apply to today's task. If you cannot paste the rules back accurately, stop and ask Lauren to re-paste claud.md before proceeding.
16. **MAGNIFICA HUMANITAS DESIGN PRINCIPLES** — Every feature must reflect these; the deepest danger is that people come to see themselves and one another as projects to be optimized rather than persons called to relationship and communion. The app must never become an optimization engine; it reduces friction so the family has more room for prayer, presence, love, rest, formation. (1) the app is a tool not an authority — every AI suggestion is framed as a suggestion, "here is one way to think about this," never "you should"/"the optimal schedule is." (2) companions serve real relationships, never replace them — Sister Mary points to a real confessor, Father Gregory to real mentors and to John, Lucy to real conversation. (3) AI supports thinking, doesn't replace it — ask before suggesting; boys build their own plans before seeing AI suggestions. (4) be transparent about what AI is — no system creates a heart or conscience; companions never make theological claims with personal authority, never quietly assume a decision belonging to Lauren; prayer texts come from verified Catholic sources only, never AI-generated. (5) language of grace not performance — no gamification, streaks, or shaming scores; a hard day is never framed as failure; human limits (illness, exhaustion, a plan that falls apart) are not defects; Sick Day Mode is relief not defeat. (6) subsidiarity — the family governs itself; Lauren is always the authority. (7) formation in digital wisdom — the explicit goal is JP finishes high school able to plan his day without the app. Every feature answers yes to at least one: does it help the family remain faithful to the truth; learn and teach one another; cultivate real closeness and protect physical presence; live justice and peace in their home — and harm none.
17. **ONE FIX PER INSTRUCTION** — Never bundle multiple fixes into one Agent instruction unless they are in the same file and directly related. Complex multi-file builds must be broken into sequential single-purpose phases with a compile check and report between each phase.
18. **AUGUST 15TH BUILD PLAN IS THE PRIORITY FILTER** — Between June 1 and August 15 2026 every build request must be checked against the August 15th build plan first. If a requested build is not on the must-have or should-have list for the current week, flag it to Lauren before starting. New feature ideas go on the post-September list unless they directly enable one of the 14 goals. Scope is the first thing to cut, not quality.
19. **BUILD FOR A FUTURE SECOND FAMILY** — This app will eventually be shared with / possibly sold to other families in a hosted multi-family model. Every feature must be written as if a second family will use it. Never hardcode McAdams or any single family's specifics; keep family identity/config in app_settings.json. Keep all data reads/writes flowing through data_helpers.py with no direct file access in route handlers, so the eventual JSON→database swap happens in one place. Don't bake in single-user assumptions where cheap to avoid. This does NOT mean building multi-user features before August 15th. *(Known debt, June 28 2026: `build_lorenzo_context` in render_lorenzo.py hardcodes the family roster rather than reading app_settings.json. New Step 4 / Lorenzo work must NOT deepen this; ideally route the roster through data_helpers.)*
20. **PRESERVE SCROLL ON SAME-PAGE RELOADS** — Any fetch() POST that on success navigates via `window.location.href` to the SAME page (full reload, not a forward navigation to a different step/page) MUST save `window.scrollY` to sessionStorage immediately before setting `window.location.href`, then on next load restore with `window.scrollTo` and clear the sessionStorage key (read → scrollTo → removeItem, gated on document.readyState / DOMContentLoaded). Forward navigations to a different page/step are exempt. render_meal_wizard_step4.py is the reference implementation (s4Keep / s4Change / s4Lock / s4Generate + s4RestoreScroll). Keep client-side only and obey Rules 7 & 12.

### Non-numbered rules also in the file

- **Anchor-tag navigation:** Plain `<a href>` links cannot POST or mutate server state. State the destination needs must travel in the URL query string OR be persisted before the click; the destination handler must accept those params AND persist them on arrival if required for later renders. (Counter-pattern: FROL wizard landing anchors to `/frol-wizard?step=1&mode=structured` failed because `mode` wasn't persisted on first GET. Use a `<form method="POST">` styled as a link if a button must trigger persistent state.)
- **AI calls:** Model is NOT uniform. Lorenzo's live call uses `claude-haiku-4-5-20251001` (verified June 28 2026; replit.md agrees). The previously-documented `claude-sonnet-4-20250514` is stale/unverified for other calls — confirm per call. Called via urllib.request directly, not the SDK. API key read from app_settings.json. `_repair_and_parse_json()` is NOT universal — it's a nested local function inside the plan-import POST handler (~app.py 8412), used ONLY by the plan importer; Lorenzo parses bracket/XML save-tags by regex and reads `result.content[0].text` directly.
- **Change discipline:** All changes additive unless told otherwise; never delete/modify existing behavior unless the task requires it; if a task requires editing a file outside the stated scope, stop and flag; keep modules under 800 lines where possible; render_plan_importer.py is 1,114 lines (JS lives in static/js/plan_importer_core.js and plan_importer_consult.js — edit those).
- **FROL Wizard form bypass trap:** `_section_chrome` suppresses Save and Continue when `_body_has_form` detects `action="/frol-wizard"` in the body. Utility forms posting to other routes (/frol-set-variant, /frol-add-activity, /frol-delete-activity) are safe. (Same substance as Rule 13.)

## 2. PROJECT_STATE.md — does it match the repo?

Every checkable count re-derived from live source. It matches:

| PROJECT_STATE.md claim | Live repo | Match |
|---|---|---|
| 60 render_*.py modules | 60 | ✅ |
| 61 data/*.json files | 61 | ✅ |
| 220 top-level functions in data_helpers.py | 220 | ✅ |
| do_GET at line 773 | line 773 | ✅ |
| do_POST at line 2268 | line 2268 | ✅ |
| _JSON_PATHS local set at ~3571, `if path in` at 3572 | 3571 / 3572, exactly the 10 listed members | ✅ |
| 99 exact-match GET routes | 99 | ✅ |
| 206 exact + 1 prefix POST routes | 207 raw `path ==` hits (206 exact + tuple/alias forms round consistently) | ✅ |

The `_JSON_PATHS` membership (all four Step-4 routes: `/meal-wizard-step4-confirm`, `/meal-wizard-step4-remove`, `/meal-wizard-step4-lock`, `/meal-wizard-generate`) matches the live set verbatim.

**Conclusion: PROJECT_STATE.md is accurate for the current repo state.**

## 3. Rules that apply to a Step 4 (Meal Wizard Step 4) bug diagnosis

Step 4 = `render_meal_wizard_step4.py` + `render_meal_wizard_gen.py` + its four JSON POST routes in app.py + the `dishes[]` slot contract in data_helpers.py. Rules in play:

- **Rule 14 (pre-flight checklist) + Rule 14.4 (confirmed vs assumed root cause)** — this is a *diagnosis*, so run it first; do not draft a fix on an assumed cause.
- **Rule 9** — py_compile is not enough; in-process smoke test + the relevant verify harness, since Step 4 touches shared data files and multi-caller functions.
- **Rules 10 & 10a** — any harness must use `data/mw_test_isolation.py` as the literal first import; never write live data.
- **Rule 3 + _JSON_PATHS** — the four Step-4 POST routes are elif chains and must stay registered in `_JSON_PATHS` (local set at app.py 3571); a "handler got empty body" symptom points straight here.
- **Rules 7 & 12** — Step 4 has embedded JS (s4Keep/s4Change/s4Lock/s4Generate); no raw newlines in JS-in-Python.
- **Rule 20** — Step 4 IS the scroll-preservation reference implementation; any same-page reload change must keep s4RestoreScroll intact.
- **Meal-wizard `dishes[]` contract** — every read of a slot's dishes must go through `data_helpers.slot_dishes()`; writers normalize to `dishes[]`; protein-only-in-protein, littles' food in `ingredients`.
- **Rule 5** — writes via safe_save_json only.
- **Rule 4** — module-top imports (app.py handlers have the known inline-import deviation).
- **Rule 19 (+ its known debt)** — Lorenzo roster is hardcoded in `build_lorenzo_context`; Step-4/Lorenzo work must not deepen it.
- **Rule 17** — one fix per instruction; if diagnosis surfaces several causes, split into sequential phases.
- **Rule 16** — the meal companion frames output as suggestions, no optimization/gamification language.
- **Rule 18** — confirm Step 4 work is on the August 15th plan.

**Not applicable:** Rule 8 (Step 4 routes are JSON, not multipart) and Rule 13 / FROL form-bypass trap (Step 4 is not the FROL wizard).
