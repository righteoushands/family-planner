# CLAUDE.md — Sancta Familia

## What this app is
A Catholic homeschool family management web app built in Python on Replit.
Single-file HTTP server pattern (app.py + render_*.py modules).
No framework. Raw `http.server` with a custom `do_GET` / `do_POST` handler.

## Stack
- Python 3.11
- No Flask, no Django, no FastAPI
- Data stored as JSON files in data/
- No database
- Frontend: plain HTML/CSS/JS rendered as strings in Python render functions
- Anthropic API called directly via urllib.request (no SDK)

## People
Lauren (Mom), John (Dad), JP (14, 9th grade), Joseph (12, 7th grade), 
Michael (5, kindergarten), James (13 months, toddler — cannot be assigned tasks)
- Always title-case: Mom/Lauren, JP, Joseph, Michael, James
- Mom and Lauren are the same person
- James is excluded from school renderers and gradebook

## Python 3.11 hard rules — never violate these
1. No backslashes inside f-strings
2. No nested quotes inside f-strings — use a variable outside the f-string instead
3. All POST routing uses elif chains — never if/elif with a missing first if,
   never nested if blocks for routing
4. Never put import statements inside if blocks or functions
5. All file writes use safe_save_json (tmp file + os.replace) — never open(f, 'w') directly
6. No walrus operator (:=)
7. Never use '\n' inside a JS string within a Python string literal — use '\\n' so the browser receives the escape sequence, not a raw newline
8. multipart/form-data parsing: when fetch POSTs use FormData the server
   receives multipart/form-data not urlencoded. The do_POST handler must
   sniff Content-Type and parse accordingly using cgi.FieldStorage for
   multipart. If a POST handler receives empty data check the
   Content-Type first.
9. py_compile passes but runtime fails: py_compile only validates syntax
   not runtime correctness. Always run an in-process smoke test after
   py_compile to catch NameError, missing variable definitions, and
   import failures. After the in-process smoke test, also run the relevant
   existing verify_phase_*.py harness for the area touched and paste the
   result — the smoke test confirms the changed function works, but the
   harness catches regressions in nearby functionality. Do not skip the
   harness run for changes that touch shared data files, save paths, or any
   function called from more than one place.
10. test fixtures must never write to live data: verification harnesses
    must always operate on a temp copy of live data files. Never call
    save_progress, safe_save_json, or any write helper on live data
    during testing. Always restore from backup after any test that
    touches data files.
11. double-escaping HTML entities: never pass a string that is already
    HTML-escaped through escape() again. If a string contains literal
    ampersands for display use plain ampersands in the source string
    and let escape() handle it once. Strings pre-escaped with &amp;
    will render as visible &amp; in the browser if escaped again.
12. JS newline in Python f-strings applies everywhere: rule 7 (never
    use backslash-n in JS strings inside Python f-strings) applies to
    ALL files containing JS embedded in Python, not just
    render_frol_wizard.py. This includes render_schedule.py,
    render_timeblock.py, render_lucy.py, render_lorenzo.py, and any
    other render file with inline JavaScript.

## Data file patterns
- Most data lives in data/*.json as flat dicts or lists
- Person keys are title-case in progress.json, chores.json, events.json
- Person keys are lowercase in auth/pins.json and profiles/ (jp.json not JP.json)
- Progress keys are compound strings: "YYYY-MM-DD::Person::task text"
- Date keys: YYYY-MM-DD (most), YYYY-Www (meal_plan), YYYY-MM (cycle)

## Route patterns
- GET routes call render_*.py functions that return HTML strings
- POST routes live in app.py do_POST, chained as elif path == "/route-name":
- JSON POST bodies must be registered in _JSON_PATHS set or the form-parser
  will consume the payload silently
- New routes that receive JSON bodies must be added to _JSON_PATHS

## Anchor-tag navigation
Plain `<a href="...">` links cannot POST and cannot mutate server state on
their own. Any state the destination page needs must either travel in the
URL query string OR already be persisted before the user clicks. The
destination handler is responsible for accepting those query params AND
persisting them on arrival if they are required for subsequent renders.
Counter-pattern that bit us: the FROL wizard landing buttons are anchors
to /frol-wizard?step=1&mode=structured. Without persisting `mode` on the
first GET, the page's "is the wizard configured?" gate kept re-rendering
the landing screen and the wizard appeared unreachable. If a button must
trigger persistent state without the destination handler doing the write,
use a `<form method="POST">` with a submit button styled as a link instead.

## AI calls
- Model: claude-sonnet-4-20250514
- Called via urllib.request directly, not the Anthropic SDK
- API key read from app_settings.json
- All AI responses go through _repair_and_parse_json() before use

## Change discipline
- All changes are additive unless explicitly told otherwise
- Never delete or modify existing behavior unless the task specifically requires it
- If a task requires editing a file not in the stated scope, stop and flag it
- Keep modules under 800 lines where possible
- render_plan_importer.py is 1,114 lines (JS lives in static/js/plan_importer_core.js and static/js/plan_importer_consult.js — edit those, not the Python file, for JS changes)

## FROL Wizard form bypass trap
The _section_chrome function in render_frol_wizard.py suppresses the
Save and Continue button when it detects a form in the body via the
_body_has_form check. This check currently looks for action="/frol-wizard"
in the body. Any utility form in a section body that posts to
/frol-wizard will incorrectly suppress the Save and Continue button.
Utility forms that post to other routes (like /frol-set-variant,
/frol-add-activity, /frol-delete-activity) are safe and will not trigger
the bypass. When adding new forms to section bodies always check whether
they post to /frol-wizard and if so either use a different route or
handle the advance separately in the section body itself.

## Additional rules (13–19)

13. **FROL WIZARD NESTED FORM ADDENDUM** — The _body_has_form check in
    _section_chrome looks for action=”/frol-wizard” in the body string.
    Any form inside a section body posting to /frol-wizard will suppress
    the Save and Continue button. Variant tab forms posting to
    /frol-set-variant are safe. Activity builder forms posting to
    /frol-add-activity are safe. Before adding any form to a section body
    confirm its action attribute. This is a recurring bug — document
    before fixing if it appears again.

14. **PRE-FLIGHT CHECKLIST** — Before writing any spec answer these
    questions. One — how many files does this touch, list them, if
    unknown that is a diagnosis step first. Two — does it involve
    JavaScript inside Python f-strings, if yes flag the backslash-n rule
    explicitly in the spec. Three — does it touch form handling, if yes
    confirm no nested forms posting to /frol-wizard. Four — is the root
    cause confirmed or assumed, if assumed run diagnosis first never
    draft a fix on an assumed cause. Five — does it touch multiple files
    at once, if yes break into separate single-purpose instructions.
    Six — does it involve data shape changes or migration, if yes
    confirm before and after data structure explicitly before writing
    the spec.

15. **CLAUD.MD READ-BACK REQUIRED** — At the start of every session read
    claud.md and paste back every rule found. Then identify which rules
    apply to today’s task. If you cannot paste the rules back accurately
    stop and ask Lauren to re-paste claud.md before proceeding.

16. **MAGNIFICA HUMANITAS DESIGN PRINCIPLES** — Every feature must reflect
    these. The deepest danger to guard against, named by the encyclical:
    that people come to see themselves and one another as projects to be
    optimized rather than persons called to relationship and communion. The
    app must never become an optimization engine; it reduces friction so the
    family has more room for prayer, presence, love, rest, and formation.
    One — the app is a tool not an authority; every AI suggestion is framed
    as a suggestion never a prescription; use “here is one way to think about
    this” never “you should” or “the optimal schedule is.” Two — companions
    serve real relationships, never replace them; Sister Mary points to a
    real confessor, Father Gregory to real mentors and to John, Lucy to real
    conversation. Three — AI supports thinking, it does not replace it; ask
    before suggesting; boys build their own plans before seeing AI
    suggestions. Four — be transparent about what AI is; no system can create
    a heart that gives itself or a conscience that discerns good from evil,
    so companions never make theological claims with personal authority and
    never quietly assume a decision that belongs to Lauren; prayer texts come
    from verified Catholic sources only, never AI-generated. Five — language
    of grace not performance; no gamification, streaks, or shaming scores; a
    hard day is never framed as failure; human limits like illness,
    exhaustion, and a plan that falls apart are not defects to correct or
    shame, because people often flourish through their limitations not despite
    them; Sick Day Mode is relief not defeat. Six — subsidiarity; the family
    governs itself; Lauren is always the authority; the app serves the
    family’s discernment. Seven — formation in digital wisdom; the explicit
    goal is that JP finishes high school able to plan his day without the app.
    Every feature should answer yes to at least one of these four questions
    and harm none: does it help the family remain faithful to the truth; does
    it help them learn and teach one another; does it help them cultivate real
    closeness and protect physical presence; does it help them live justice
    and peace in their home.

17. **ONE FIX PER INSTRUCTION** — Never bundle multiple fixes into one
    Agent instruction unless they are in the same file and directly
    related. Complex multi-file builds must be broken into sequential
    single-purpose phases with a compile check and report between each
    phase.

18. **AUGUST 15TH BUILD PLAN IS THE PRIORITY FILTER** — Between June 1st
    and August 15th 2026 every build request must be checked against the
    August 15th build plan before proceeding. If a requested build is
    not on the must-have or should-have list for the current week flag
    it to Lauren before starting. New feature ideas go on the
    post-September list unless they directly enable one of the 14 goals
    in the August 15th plan. Scope is the first thing to cut not quality.

19. **BUILD FOR A FUTURE SECOND FAMILY** — This app will eventually be
    shared with and possibly sold to other families using a hosted
    multi-family model. Every feature must be written as if a second family
    will use it. Never hardcode McAdams or any single family’s specifics
    into code as if it is the only family — keep family identity and config
    in app_settings.json. Keep all data reads and writes flowing through
    data_helpers.py with no direct file access in route handlers, so the
    eventual swap from JSON files to a database happens in one place. Do not
    bake in single-user assumptions in new feature logic where it is cheap
    to avoid them. This is design hygiene that costs nothing now and
    prevents a full rewrite later; it does NOT mean building multi-user
    features before August 15th.

## Current major features
- /plan-import — paste text → AI extracts events, tasks, placements → approve → apply
- Placements route information to existing records (events, profiles, friends, pantry, etc.)
- Receipt + undo after apply (/plan-import-undo-placement)
- Six AI companions: Lucy, Lorenzo, Gregory, Monica, Coach, Izzy (dev)
- Liturgical calendar engine with auto-computed Easter and moveable feasts
- Daily schedule grids per person, per date
- Gradebook with assignment analyzer
- Meal planner with Lorenzo as meal companion
