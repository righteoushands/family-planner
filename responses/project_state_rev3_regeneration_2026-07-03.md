# PROJECT_STATE.md REGENERATION — rev 3, full live re-scan (2026-07-03)
## Every number below comes from wc -l / grep -n run TODAY. Nothing carried from rev 2.

---

## PART 0 — claud.md READ-BACK (Rule 15): every rule, pasted back

**Python 3.11 hard rules — never violate these**
1. No backslashes inside f-strings
2. No nested quotes inside f-strings — use a variable outside the f-string instead
3. All GET routing uses elif chains in do_GET; POST routing in do_POST ALSO uses
   elif chains (verified June 28 2026). ONE exception: the multipart recipe
   routes (/recipe-save, /recipe-import) share an `elif path in (...)` outer
   block with nested `if` inner blocks only to share upload-parsing setup —
   never copy that pattern for ordinary routes. [CORRECTED June 28 2026: the
   old standalone-if claim was wrong; code wins.]
4. Never put import statements inside if blocks or functions [KNOWN DEVIATION:
   several live do_POST handlers use inline imports; new code = module top]
5. All file writes use safe_save_json (tmp + os.replace) — never open(f,'w')
6. No walrus operator (:=)
7. Never a raw newline escape inside a JS string within a Python string
   literal — the browser must receive the escape sequence, not a raw newline
8. multipart/form-data: sniff Content-Type in do_POST; cgi.FieldStorage for
   multipart; empty POST data → check Content-Type first
9. py_compile is syntax-only: in-process smoke test after it, then run the
   relevant existing verify harness for the area touched and paste the result
10. Test fixtures must never write to live data; temp copies only; restore
    from backup after any test that touches data files
10a. ISOLATION MUST BE STRUCTURAL — mw_test_isolation (or equivalent) as the
    literal FIRST project import; guard raises on live paths;
    snapshot/restore-after is NOT equivalent to never touching live data
11. Never double-escape HTML entities — escape() exactly once
12. Rule 7 applies to ALL files with JS embedded in Python (render_schedule,
    render_timeblock, render_lucy, render_lorenzo, etc.)
13. FROL nested-form addendum — any form in a section body posting to
    /frol-wizard suppresses Save and Continue; confirm every new form's action
14. PRE-FLIGHT CHECKLIST — (1) file count listed, unknown = diagnose first;
    (2) JS-in-f-strings flagged; (3) forms checked against /frol-wizard;
    (4) root cause confirmed, never assumed; (5) multi-file work split into
    single-purpose instructions; (6) data-shape changes confirmed
    before/after explicitly
15. CLAUD.MD READ-BACK REQUIRED — every session: read, paste back every rule,
    identify which apply; if unable, stop and ask Lauren to re-paste
16. MAGNIFICA HUMANITAS DESIGN PRINCIPLES — never an optimization engine;
    persons, not projects. (1) Tool not authority — suggestions never
    prescriptions; (2) companions serve real relationships, never replace
    them; (3) AI supports thinking, never replaces it; (4) transparency about
    what AI is — no theological claims with personal authority; prayer texts
    from verified Catholic sources only; (5) language of grace not
    performance — no gamification, streaks, shaming scores; a hard day is
    never failure; (6) subsidiarity — Lauren is always the authority;
    (7) formation in digital wisdom — JP finishes high school able to plan
    his day without the app. Every feature answers yes to at least one of
    the four questions (truth / learning / closeness / justice and peace)
    and harms none.
17. ONE FIX PER INSTRUCTION — no bundling; sequential single-purpose phases
    with compile check + report between each
18. AUGUST 15TH BUILD PLAN IS THE PRIORITY FILTER — off-plan requests flagged
    first; new ideas post-September; scope cut first, never quality
19. BUILD FOR A FUTURE SECOND FAMILY — no hardcoded family specifics; config
    in app_settings.json; all data I/O through data_helpers.py [KNOWN DEBT:
    build_lorenzo_context roster]
20. PRESERVE SCROLL ON SAME-PAGE RELOADS — sessionStorage scrollY
    save/restore for same-page reload navigations; forward navigations
    exempt; render_meal_wizard_step4.py is the reference implementation
21. SESSION HELPER SHALLOW-MERGE — update_meal_wizard_session merges only at
    top level; nested keys must be read-fresh → merged → written, snapshot
    immediately before the write [KNOWN DEVIATION July 1 2026: step 4
    confirm-mirror; fixed]
22. MERGE-BASED GENERATE NO LONGER PRUNES — stale suggested_meals accumulate,
    render-gated (inert) except the re-entry edge; logged not fixed;
    KI-001/KI-002

**Named sections also read:** People; Data file patterns; Route patterns
(_JSON_PATHS is local to do_POST); Anchor-tag navigation; AI calls (models
not uniform; _repair_and_parse_json is plan-importer-only); Change
discipline (additive only; known-issues tracker lives OUTSIDE the repo);
FROL form-bypass trap; Current major features; DOC CORRECTION LOG.

**Rules that apply to THIS task (PROJECT_STATE.md full re-scan regeneration):**
- **15** — this read-back.
- **14 item 4 (root cause confirmed, never assumed)** — the whole task IS
  this rule: every line count re-run with wc -l, every anchor re-run with
  grep -n, nothing reused from the rev-2 doc or the H1 report.
- **Change discipline** — only PROJECT_STATE.md (documentation) was
  rewritten; zero code files touched; no behavior changed.
- **17 (one fix per instruction)** — one artifact regenerated, nothing else.
- Code rules (1–13, 19–22) not triggered — no code edited. (Rule 3/21/22
  FACTS are re-documented inside the regenerated doc, but no code changed.)

---

## PART 1 — THE SIX CONFIRMATIONS (all against live code, today)

**1. render_meal_wizard_step5.py** — **133 lines** (wc -l).
Signature confirmed at **line 85**: `def render_step5(user: str) -> str:`
`_S5_DAYS` (Monday–Sunday list) at **line 29**.

**2. app.py** — **12,424 lines** total (was 12,386 at rev 2; +38 = the Step 5
additions themselves). The four Step 5 anchors, confirmed by fresh grep -n:
- import `from render_meal_wizard_step5 import render_step5, _S5_DAYS` → **line 258**
- GET `elif path == "/meal-wizard-step5":` → **line 1358**
- `_JSON_PATHS` set containing `/meal-wizard-step5-save` → **line 3582** (11 members)
- POST `elif path == "/meal-wizard-step5-save":` → **line 11036**

Honest note on "they will have shifted": they have NOT shifted — these four
numbers are identical to the H1 report because no app.py edit has landed
since H1 (the header fix touched only render_meal_wizard_step4.py, and the
report files live in responses/). I did not reuse the old numbers — the
grep was run fresh today and happens to agree. What DID shift inside app.py
relative to rev 2's other anchors: do_GET 773→774, do_POST 2268→2279,
_JSON_PATHS 3571→3582, step4-remove handler 10878→10889,
_repair_and_parse_json ~8412→8458.

**3. render_meal_wizard_step4.py** — **801 lines** (was 792 at rev 2; +9).
Day-header color change confirmed present at current line numbers:
- **Line 64**: `_S4_DAY_HEADER = ("font-family:" + _HEADING_FONT + ";font-size:1.15em;font-weight:600;` `"margin:0;padding:12px 16px 2px;")` — **no `color:` property remains** (the old `color:var(--ink);` is gone; verified by reading lines 60–75).
- **Line 499**: `season_color = _s4_safe_color(info.get("season_color"), "#888")`
- **Line 502**: `f'<h3 style="{_S4_DAY_HEADER}color:{season_color};">'` — the h3 interpolates the sanitized season color.

**4. data/meal_wizard_session.json** — `confirmed_shopping_day` **IS present
as a live key**, value `"Saturday"` (from H1 testing). All 10 keys currently
in the file (sorted): `confirmed_complexity`, `confirmed_inventory`,
`confirmed_meals`, `confirmed_shopping_day`, `confirmed_what_to_plan`,
`plan_locked_at`, `planning_window`, `suggested_meals`, `use_soon_items`,
`used_proteins`.

**5. verify_meal_wizard_step5.py** — **does NOT exist**. Checked both repo
root and data/ — `ls` reports no such file in either location. Correct per
H1 scope (standing harness was explicitly deferred; still an offered
follow-up, not built).

**6. Git state** — `git rev-parse main` = **ba20274ab6a60657179511515903ea4468a1da95**
(recorded in the doc header; this is the post-push-confirmation checkpoint).

**Bonus finding from the full scan (this is why full re-scans beat
incremental patching):** two render modules existed on disk but were missing
from BOTH prior PROJECT_STATE revisions — `render_seasons.py` (147 lines,
Phase F season-detection helper, pure module) and `render_companions.py`
(54 lines, the /companions page, routed at app.py line 1277). Both are now
in Section 5.

---

## PART 2 — THE FULL REGENERATED PROJECT_STATE.md (rev 3), verbatim

# PROJECT_STATE.md — Sancta Familia

Technical snapshot of the current codebase. **Full re-scan 2026-07-03 (rev 3)** — every line count
confirmed by running `wc -l` live; every line-number anchor confirmed by live `grep -n`; no number
carried forward from the July 2 rev-2 version.

**Git reference at scan time:** `git rev-parse main` = `ba20274ab6a60657179511515903ea4468a1da95`
(local main; pushed tip verified equal to GitHub main earlier on 2026-07-03 — this HEAD includes
the post-push confirmation-report checkpoint).

---

## Section 1 — GET routes (defined in `app.py do_GET`, starts at line 774)

`do_GET` uses `elif path == "…"` chains with no bare `if`. Static assets, login, and
the Family Quest handoff are handled first; all other routes require auth (via `_require_auth`).

### 1a. Exact-match GET routes

| Route | Handler / notes |
|---|---|
| `/today` | `render_today_all(date)` — compact task cards per child |
| `/programs` | coach programs page |
| `/set-school-mode` | toggle school/summer mode, redirect |
| `/now` | `render_now_page()` — time-block homepage |
| `/week` | family week view |
| `/week-school` | `render_week_school_page(iso)` — school progress grid |
| `/school` | `render_school_page()` — school management |
| `/api/today-progress` | JSON API: today's task progress |
| `/api/boys-tasks` | JSON API: boys' tasks |
| `/api/child-tasks` | JSON API: child task list |
| `/gdrive-files` | Google Drive file browser |
| `/kids-week` | kids' week planning page |
| `/plan-tomorrow` | `render_plan_tomorrow_page()` |
| `/plan-today` | plan-today view |
| `/plan-week` | `render_plan_week_page()` |
| `/plan-month` | `render_plan_month_page()` |
| `/plan-year` | `render_plan_year_page()` |
| `/plan-quarter` | `render_plan_quarter_page()` |
| `/virtues` | virtue tracker landing |
| `/5am` | 5AM Club page |
| `/liturgy-hours` | Liturgy of the Hours (Divine Office iframe) |
| `/prayer-intentions` | prayer intentions list |
| `/virtues/me` | Mom's virtue page |
| `/virtues/family` | family virtue page |
| `/school/edit` | `render_school_edit_page(child)` |
| `/chores` | `render_chores_page()` |
| `/van-roles` | `render_van_roles_page()` |
| `/print/day` | printable day (with date param) |
| `/print/week` | `render_print_week()` |
| `/notes` | `render_notes()` |
| `/tasks` | `render_tasks()` |
| `/thankyou-reminders` | `render_thankyou_page()` |
| `/mom` | `render_mom_page(date)` |
| `/mom-profile` | Mom's personal profile page |
| `/john` | John's profile page |
| `/friends` | friends & families directory |
| `/roadmap` | `render_roadmap_page()` |
| `/signup` | beta waitlist signup |
| `/waitlist` | waitlist admin |
| `/family-schedule` | `render_family_schedule_page()` |
| `/frol-pdf` | `generate_frol_pdf()` — FROL printable PDF |
| `/school-week-pdf` | `generate_school_pdf()` — school week PDF |
| `/calendar` | `render_calendar_page()` |
| `/planner` | `render_planner_page()` |
| `/readings` | `render_readings_page(date)` |
| `/lucy` | `render_lucy_page()` — Lucy AI companion |
| `/lorenzo-plan-state` | JSON: Lorenzo planning session state |
| `/lorenzo` | `render_lorenzo_page()` — Lorenzo AI companion |
| `/headmaster` | `render_gregory_page()` — Father Gregory AI |
| `/coach` | `render_coach_page()` — Coach AI |
| `/dr-monica` | `render_monica_page()` — Dr. Monica AI |
| `/companions` | companions hub (`render_companions_page()`, app.py line 1277) |
| `/wizards` | wizards hub (`render_wizards_page()`) |
| `/pantry-staples` | `render_pantry_staples_page()` — Meal Wizard Phase C |
| `/meal-wizard` | `render_meal_wizard_week_glance()` — Step 1 |
| `/meal-wizard-step2` | `render_meal_wizard_step2()` — Phase E |
| `/meal-wizard-step3` | `render_meal_wizard_step3()` — Phase F |
| `/meal-wizard-step4` | `render_meal_wizard_step4()` — Phase G |
| `/meal-wizard-step5` | `render_step5(user)` — Phase H1 shopping-day skeleton (**app.py line 1358**) |
| `/sister-mary` | `render_sister_mary_page()` — Sister Mary AI |
| `/frol-grid-fragment` | FROL grid fragment (partial render) |
| `/frol-seasonal-view` | `render_seasonal_view_page()` |
| `/frol-wizard` | FROL wizard page |
| `/daily-mass` | redirect to daily Mass video URL |
| `/plan-import-history` | plan-import history page |
| `/grades` | `render_grades_summary_page()` |
| `/subject` | `render_subject_page(child, subject)` |
| `/hour-report` | `render_hour_report()` |
| `/curriculum` | `render_curriculum_page()` |
| `/gradebook` | `render_gradebook_page(child, year)` |
| `/assignment-analyzer` | `render_assignment_analyzer_page()` |
| `/assignment-image` | serves stored assignment image file |
| `/plan-import` | `render_plan_import_page()` |
| `/dev` | `render_dev_page()` — Izzy / Felix diagnostic AI |
| `/dev-logs` | dev logs view |
| `/dev-health` | JSON health check |
| `/dev-diag` | inline diagnostics |
| `/dev-read-file` | inline file reader (dev) |
| `/dev-grep-files` | inline grep (dev) |
| `/dev-git-log` | inline git log (dev) |
| `/dev-git-diff` | inline git diff (dev) |
| `/memory-book` | `render_memory_book_page()` |
| `/liturgical` | `render_liturgical_page()` |
| `/prayer` | `render_liturgical_page()` (alias) |
| `/liturgical/edit` | `render_liturgical_edit_page(date)` |
| `/settings` | `render_settings_page()` |
| `/history` | `render_history_page()` |
| `/history/preview` | inline history snapshot preview |
| `/plan-fragment` | `render_plan_fragment_html()` |
| `/grid-print` | `render_grid_print_page()` |
| `/mom-step` | `render_mom_step_fragment()` |
| `/meals` | `render_meal_planner_page()` |
| `/meal-print` | `render_meal_print_page()` |
| `/recipes` | recipes page |
| `/api-key` | inline API key status |
| `/calendar/refresh` | `refresh_calendar()`, redirect |

### 1b. Prefix GET routes (`path.startswith("…")`)

| Prefix | Purpose |
|---|---|
| `/static/` | serves static assets (JS, CSS, images) |
| `/quest` | Family Quest sub-app handoff |
| `/prayer-photo/` | serves prayer intention photos |
| `/prayer-intention/share/` | shareable prayer intention view |
| `/virtues/child/` | `render_virtue_child_page(child)` |
| `/print/day/` | printable day for a given date |
| `/uploads/recipes/` | serves recipe upload images |
| `/uploads/grades/` or `/uploads/grade_docs/` | serves grade/doc upload files |
| `/schedule/` | `render_child_schedule(child, date)` |
| `/student/` | `render_student_page(child)` |
| `/grades/` | `render_student_grades(child)` |
| `/lucy-child-brief/` | Lucy child brief fragment |
| `/lucy-prayer-brief/` | Lucy prayer brief fragment |

---

## Section 2 — POST routes (defined in `app.py do_POST`, starts at line 2279)

POST routing uses `elif path == "…"` chains. One prefix match (`/quest`). Five
`elif path in (...)` shared blocks for setup sharing:

| Tuple block | Why shared |
|---|---|
| `/recipe-save`, `/recipe-import` | shared multipart upload-parsing (Rule 3's named exception; nested `if path ==` inside) |
| `/subject-upload-image`, `/subject-doc-upload` | shared subject upload-parsing (`if path in` leading block) |
| `/frol-add-activity`, `/frol-edit-activity`, `/frol-delete-activity` | shared FROL activity mutate setup |
| `/calendar-config-save`, `/calendar-save-config` | route alias → same handler |
| `/family-schedule-save`, `/settings-schedule-save` | route alias → same handler |

**`_JSON_PATHS`** — local set in `do_POST` (**line 3582**) that tells the form-parser
to skip urlencoded parsing and leave the body for `json.loads`. Current members (11):
`/plan-import-apply`, `/plan-import-undo-placement`, `/curriculum-save`,
`/curriculum-minutes`, `/poetry-passage-save`, `/meal-wizard-step3-save`,
`/meal-wizard-step4-confirm`, `/meal-wizard-step4-remove`,
`/meal-wizard-step4-lock`, `/meal-wizard-generate`, `/meal-wizard-step5-save`

### POST route groups

**Auth & messaging:** `/login`, `/student-message-read`, `/message-mom`, `/change-pin`, `/messages-read`, `/save-pins`

**Meals & pantry:** `/pantry-staples-save`, `/meal-save-plan`, `/meal-rule-add`, `/meal-rule-delete`, `/meal-save-inventory`, `/meal-wizard-step2-save`, `/meal-wizard-step3-save` (JSON), `/meal-wizard-step4-confirm` (JSON ← Phase G), `/meal-wizard-step4-remove` (JSON ← Phase G), `/meal-wizard-step4-lock` (JSON ← Phase G), `/meal-wizard-generate` (JSON ← Phase G — Lorenzo week generator), `/meal-wizard-step5-save` (JSON ← Phase H1, handler at **app.py line 11036**), `/meal-generate`, `/meal-save-constraints`, `/meal-edit`, `/recipe-save`, `/recipe-import`, `/recipe-delete`

**Plan importer:** `/plan-import-save-session`, `/plan-import-history-delete`, `/plan-import-analyze`, `/plan-import-apply` (JSON), `/plan-import-undo-placement` (JSON), `/plan-import-consult`, `/plan-import-group-consult`, `/api/extract-suggestions`

**School / subjects / gradebook:** `/subject-upload-image`, `/subject-doc-upload`, `/subject-send-to-mom`, `/subject-grade-add`, `/subject-grade-delete`, `/subject-link-add`, `/subject-link-delete`, `/subject-doc-delete`, `/assignment-analyze`, `/assignment-update`, `/assignment-delete`, `/assignment-reply`, `/gradebook-add`, `/gradebook-update`, `/gradebook-delete`, `/school-upload`, `/approve-school-preview`, `/approve-school-week`, `/regenerate-school-week`, `/reparse-school-preview`, `/save-school-preview-edits`, `/school-settings-save`

**Curriculum:** `/curriculum-parse`, `/curriculum-save` (JSON), `/curriculum-minutes` (JSON), `/poetry-passage-save` (JSON), `/curriculum-week`, `/curriculum-subject-week`, `/curriculum-subject-day`, `/curriculum-delete`

**Tasks / notes / plan items:** `/toggle-task`, `/add-note`, `/archive-note`, `/convert-note`, `/add-task`, `/task-update`, `/task-done`, `/task-delete`, `/task-hard-delete`, `/task-purge-inactive`, `/task-override`, `/plan-add-item`, `/plan-toggle-item`, `/plan-item-update`, `/planner-add-task`, `/add-to-plan-quick`, `/plan-ai-suggest`

**Daily grid / anchor:** `/anchor-save`, `/grid-save-template`, `/grid-push-weekly`, `/grid-cell-save`, `/grid-publish`, `/grid-reset`, `/schedule-template-save`

**Chores / van:** `/save-chores`, `/apply-laundry`, `/apply-van-rotation`

**Thank-you notes:** `/thankyou-add`, `/thankyou-done`, `/thankyou-dismiss`, `/thankyou-suggest`

**Companions (chat / rules / history):** `/lucy-tts`, `/lucy-rule-save`, `/lucy-chat`, `/lucy-clear-history`, `/lorenzo-chat`, `/lorenzo-rule-save`, `/lorenzo-plan-start`, `/lorenzo-plan-end`, `/lorenzo-clear-history`, `/headmaster-chat`, `/headmaster-clear-history`, `/coach-chat`, `/coach-clear-history`, `/dr-monica-chat`, `/dr-monica-clear-history`, `/sister-mary-chat`, `/sister-mary-clear-history`, `/dev-chat`, `/dev-apply`, `/dev-write`, `/dev-undo`, `/dev-restart`, `/dev-clear`

**Coach programs / exercise / hours:** `/programs-save`, `/programs-delete`, `/programs-edit`, `/exercise-log`, `/hour-log-add`, `/hour-log-edit`, `/hour-log-delete`

**FROL wizard & seasonal:** `/frol-save-seasonal`, `/frol-seasonal-use`, `/frol-seasonal-delete`, `/frol-overlay-toggle`, `/frol-overlay-set`, `/frol-overlay-clear`, `/pod-dismiss-season`, `/pod-toggle-traveling`, `/frol-wizard`, `/frol-wizard-chat`, `/frol-wizard-finalize`, `/frol-set-variant`, `/frol-rollback-v3`, `/frol-add-activity`, `/frol-edit-activity`, `/frol-delete-activity`

**Prayer / liturgical / memory:** `/prayer-intention-add`, `/prayer-intention-delete`, `/prayer-intention-log`, `/prayer-intention-complete`, `/timeblock-add-intention`, `/timeblock-add-novena`, `/liturgy-hours-save`, `/liturgical-save`, `/liturgical-delete`, `/liturgical-note`, `/memory-book-save`, `/memory-book-delete`, `/memory-update`

**Calendar:** `/calendar-config-save`, `/calendar-save-config`, `/subscribed-cal-add`, `/subscribed-cal-toggle`, `/subscribed-cal-delete`, `/calendar-refresh`, `/calendar-add-event`, `/calendar-event-delete`

**Goals / quarter / children:** `/roadmap-add`, `/roadmap-update`, `/roadmap-delete`, `/child-goal-add`, `/child-goal-archive`, `/child-substep-add`, `/child-substep-toggle`, `/child-substep-delete`, `/quarter-save-goals`, `/quarter-journal-save`, `/quarter-save-step`, `/quarter-checkin`, `/goal-add`, `/save-child-profile`, `/virtue-checkin`

**Cycle:** `/cycle-log-add`, `/cycle-log-delete`, `/cycle-ai-suggest`, `/cycle-save`

**Plan tomorrow / week / month / AI briefs:** `/plan-tomorrow-questions`, `/plan-tomorrow-generate`, `/plan-tomorrow-push`, `/plan-week-save`, `/plan-month-save`, `/kids-week-save`, `/5am-save`, `/ai-daily-schedule`, `/ai-meal-plan`, `/ai-school-plan`, `/ai-evening-examen`, `/ai-weekly-review`, `/ai-chore-adjust`, `/ai-intention-prayer`, `/ai-capacity-preview`, `/ai-week-brief`, `/ai-month-brief`, `/ai-year-brief`, `/ai-suggest-goals`, `/ai-generate-steps`, `/preview-keep`, `/preview-discard`

**Profiles / signup / settings / misc:** `/save-mom-profile`, `/save-john-profile`, `/save-friend`, `/delete-friend`, `/mom-add-note`, `/history-restore`, `/signup-submit`, `/waitlist`, `/settings-save-ajax`, `/settings-save`, `/family-schedule-save`, `/settings-schedule-save`

---

## Section 3 — Core modules (line counts confirmed live 2026-07-03 rev 3)

| File | Lines | Role |
|---|---|---|
| `app.py` | **12,424** | Entry point, HTTP handler (`do_GET` line 774, `do_POST` line 2279), top-level imports end ~line 264 (Step 5 import at line 258) |
| `data_helpers.py` | **3,376** | Only file that reads/writes JSON; every feature area has loaders/savers here |
| `config.py` | **191** | All file paths + domain constants; no imports from render_* or data_helpers |
| `daily_schedule_engine.py` | **2,642** | Schedule logic, `CHILDREN` tuple, task completion |
| `ui_helpers.py` | **1,801** | `html_page()`, form parsers, shared HTML utilities |
| `safe_utils.py` | **504** | `safe_save_json()`, companion turn helpers |
| `companion_handoffs.py` | **315** | Undo instructions for AI companions |
| `auth.py` | **276** | PIN auth, session management, `_require_auth` |
| `notes_router.py` | **58** | Note add/archive/load/save helpers |
| `gdrive.py` | **73** | Google Drive file listing |

---

## Section 4 — config.py constants (all confirmed live; file unchanged at 191 lines)

```
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8000))

# ── File paths (owned exclusively by config.py) ──────────────────────────────
MANUAL_TASKS_FILE    = "data/manual_tasks.json"
CHORES_FILE          = "data/chores.json"
MOM_NOTES_FILE       = "data/mom_notes.json"
ROADMAP_FILE         = "data/roadmap.json"
LITURGICAL_FILE      = "data/liturgical.json"
FAMILY_SCHEDULE_FILE = "data/family_schedule.json"
CALENDAR_CONFIG_FILE = "data/calendar_config.json"
CALENDAR_CACHE_FILE  = "data/calendar_cache.json"
MONTHLY_PLANNER_FILE = "data/monthly_planner.json"
CALENDAR_RULES_FILE  = "data/calendar_rules.json"
SUBSCRIBED_CALS_FILE  = "data/subscribed_calendars.json"
SUBSCRIBED_CACHE_FILE = "data/subscribed_calendar_cache.json"
APP_SETTINGS_FILE    = "data/app_settings.json"
CURRICULUM_FILE      = "data/curriculum.json"
TASK_OVERRIDES_FILE  = "data/task_overrides.json"
COACH_PROGRAMS_FILE  = "data/coach_programs.json"
EXERCISE_LOGS_FILE   = "data/exercise_logs.json"
SCHOOL_WEEK_PLAN_FILE = "data/school_week_plan.json"
FAMILY_MEMORY_FILE   = "data/family_memory.json"
PRAYER_INTENTIONS_FILE   = "data/prayer_intentions.json"
SISTER_MARY_HISTORY_FILE = "data/sister_mary_history.json"
POPE_INTENTIONS_FILE     = "data/pope_intentions.json"
FROL_WIZARD_PROGRESS_FILE = "data/frol_wizard_progress.json"
HOUR_TRACKING_FILE       = "data/hour_tracking.json"
HOUR_REPORTS_DIR         = "data/hour_reports"
FROL_ACTIVITIES_FILE     = "data/frol_activities.json"

DAY_TEMPLATES_DIR         = "data/day_templates"
DAY_TEMPLATES_PREVIEW_DIR = "data/day_templates_preview"
DAY_TEMPLATES_BACKUP_DIR  = "data/day_templates_backups"

SEASONAL_SCHEDULES_FILE   = "data/seasonal_schedules.json"

# ── Meal Planning Wizard ──────────────────────────────────────────────────────
# MEAL_PLAN_DIR env var overrides MEALS_DIR for harness isolation (Rule 10).
MEALS_DIR            = os.environ.get("MEAL_PLAN_DIR") or "data/meal_plan"
MEAL_RULES_FILE      = "data/meal_rules.json"
MEAL_INVENTORY_FILE  = "data/meal_inventory.json"
PANTRY_STAPLES_FILE  = "data/pantry_staples.json"   # lazy — created on first save
MEAL_HISTORY_FILE    = "data/meal_history.json"     # lazy — created on first save
# MEAL_WIZARD_SESSION_FILE env var overrides for harness isolation (Rule 10).
MEAL_WIZARD_SESSION_FILE = os.environ.get("MEAL_WIZARD_SESSION_FILE") \
                           or "data/meal_wizard_session.json"

# Single canonical dish-category allowlist — added 2026-07-02 (G1c-3a cleanup).
# Both render_meal_wizard_step4 (UI <select>) and render_meal_wizard_gen
# (prompt + parser) import from here. Eliminates local copies and the
# circular-import workaround they required.
MEAL_DISH_CATEGORIES = (
    "main", "side", "soup", "bread", "salad", "appetizer", "dessert", "snack"
)

# ── Validation / domain constants ─────────────────────────────────────────────
VALID_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}
VALID_STATUSES   = {"active", "done", "inactive"}

WEEKDAYS      = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_ORDER = {day: i for i, day in enumerate(WEEKDAYS)}
SCHEDULE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
MONTH_NAMES   = ["January", … "December"]
ROADMAP_STATUSES = ["Someday", "Ready", "In Progress", "Done"]
ASSIGNABLE_TO    = ["Mom"] + list(CHILDREN)   # CHILDREN from daily_schedule_engine

# Child/parent colors — defaults overridden at runtime from app_settings.json.
_DEFAULT_CHILD_COLORS  = { JP, Joseph, Michael, James, … }
CHILD_COLORS           = _load_child_colors()
_DEFAULT_PARENT_COLORS = { Lauren, John, … }
# child_color(name), parent_color(name) — helpers below

VAN_ROTATION_EPOCH = _load_van_epoch()   # default date(2025, 1, 6)
VAN_ROLE_A = "Interior Reset Lead"
VAN_ROLE_B = "Bin & Organization Lead"

# App-level settings helpers (all read from app_settings.json at runtime):
# get_app_setting(), get_family_name(), get_timezone(), get_schedule_hours()
```

---

## Section 5 — render_*.py modules (line counts confirmed live 2026-07-03 rev 3)

| File | Lines | Description |
|---|---|---|
| `render_frol_wizard.py` | **7,681** | Rule of Life Wizard — 10-step setup flow; FROL grid, seasonal overlays, FROL wizard chat |
| `render_misc.py` | **5,976** | Dashboard, Mom page, Notes, Tasks, Roadmap, Planner, School, History; large catch-all for pages without their own render_ file |
| `render_lucy.py` | **3,362** | Lucy AI companion — warm day guide; persistent conversation history, web fetch, child brief and prayer brief fragments |
| `render_schedule.py` | **2,922** | Schedule cards, task lists, print pages, today/week views; `render_today_all`, `render_child_schedule`, print helpers |
| `render_settings.py` | **2,291** | Settings page — general, children, systems, integrations sections |
| `render_lorenzo.py` | **2,199** | Lorenzo AI personal chef — meal planning companion; `build_lorenzo_context`, `_get_meal_constraints`, `_get_calendar_this_week`, `_get_saved_recipes` |
| `render_timeblock.py` | **2,134** | Lauren's time-block homepage — five server-time-driven blocks, Morning Anchor entry point |
| `render_meals.py` | **1,777** | Weekly meal planner page, meal display, `format_dish_list(dishes)`, meal-print |
| `render_dev.py` | **1,418** | Izzy/Felix diagnostic AI — dev logs, health, diagnostics, git log/diff, file read/grep (dev-only) |
| `render_subject.py` | **1,402** | Per-subject curriculum review — week/day grid per child × subject, grade upload, links/docs |
| `render_plan_importer.py` | **1,121** | Plan Import Tool — paste external AI plan, extract events/tasks, approve, apply, undo; JS in static/js/ |
| `render_virtues.py` | **1,057** | Virtue tracker — family and per-person views, virtue check-in |
| `render_calendar.py` | **974** | Calendar fetch (CalDAV), event display, calendar page, `write_caldav_event` |
| `render_prayer.py` | **968** | Prayer intentions — list, add, log, share, photo upload |
| `render_plan_week.py` | **920** | Plan My Week — weekly goal/task planning |
| `render_daily_plan.py` | **869** | Daily plan editor, family grid, dashboard views |
| `render_curriculum.py` | **858** | Curriculum management — parse MODG paste, save/edit weeks/days/subjects |
| `render_chores.py` | **836** | Chores page, laundry rotation, van rotation |
| `render_plan_tomorrow.py` | **835** | AI-powered tomorrow planning — questions, generate, push to today |
| `render_meal_wizard_step4.py` | **801** | Meal Wizard Step 4 — day-card display, write loop (s4Keep/s4Change/s4Lock/s4Generate), Lorenzo generation trigger; `CATEGORIES` = `config.MEAL_DISH_CATEGORIES` (G1c-3a); `_WIZARD_GEN_SLOT_CAP` imported from render_meal_wizard_gen; `render_step4_slot_and_lock(date_iso, slot_key, revert_dishes=None)`; **day headers render in the day's liturgical season color** — `_S4_DAY_HEADER` (line 64) no longer sets any `color:`; the h3 f-string (line 502) interpolates `color:{season_color};` from `_s4_safe_color(...)` at line 499 (added 2026-07-03) |
| `render_5am.py` | **720** | 5AM Club — Hour of Victory (3×20 min blocks) |
| `render_student.py` | **678** | Student portal — mobile-first school interface for JP and Joseph |
| `render_assignment_analyzer.py` | **676** | AI Assignment Analyzer — upload photo/paste text → structured assignment record |
| `render_plan_month.py` | **666** | Plan My Month — monthly milestone tracking per quarterly goal |
| `render_morning_anchor.py` | **652** | Morning Anchor (Step 0) and Evening Anchor (Step 5) fragments for Plan My Day |
| `render_mom_profile.py` | **649** | Mom's personal profile — personal notes and record, not just a planning hub |
| `render_plan_quarter.py` | **641** | Quarterly Goal Planning — select 4-5 goals, track through the quarter |
| `render_gregory.py` | **617** | Father Gregory AI — homeschool headmaster and academic director |
| `render_coach.py` | **599** | Coach AI — family fitness guide, exercise assignments, programs |
| `render_meal_wizard.py` | **596** | Meal Planning Wizard hub — Step 1 week glance; re-exports Step 2/3/4 renderers to app.py |
| `render_liturgical.py` | **594** | Liturgical calendar engine — auto-computes Easter, moveable feasts, season colors; `get_day_info` lives HERE (not daily_schedule_engine) |
| `render_monica.py` | **578** | Dr. Monica AI — child development and pediatric health companion |
| `render_friends.py` | **570** | Friends & Families directory — family entries with contact/notes |
| `render_week_school.py` | **567** | Weekly school progress — subject × day grid for JP and Joseph |
| `render_sister_mary.py` | **525** | Sister Mary AI — contemplative Marian companion |
| `render_liturgy_hours.py` | **518** | Liturgy of the Hours — embedded Divine Office iframe |
| `render_week_view.py` | **517** | Family Week at a Glance — mobile-first weekly overview |
| `render_signup.py` | **516** | Beta waitlist signup survey |
| `render_ai_planner.py` | **461** | AI scheduling assistant — daily, weekly, monthly planning modes |
| `render_programs.py` | **458** | Coach's saved programs + weekly exercise assignments, browseable from /today POD cards |
| `render_kids_week.py` | **454** | Kids' Week Planning — child school subjects and tasks for the week |
| `render_meal_wizard_step3.py` | **438** | Meal Wizard Step 3 — "what are we planning this week" (meal-type selection, complexity, planning window) |
| `render_john.py` | **433** | John's (Dad) personal profile — work schedule, notes, preferences |
| `render_gradebook.py` | **428** | Per-child gradebook — recorded assignment scores by child/year |
| `render_daily_bar.py` | **413** | Daily info bar — weather, saint of the day, gospel link, special events; child age helpers |
| `render_ai_daily.py` | **405** | AI-powered daily assistance — daily schedule, meal plan, school plan, evening examen, weekly review, AI briefs |
| `render_meal_wizard_gen.py` | **391** | Meal Wizard generation data contract — `wizard_target_slot_keys`, `parse_wizard_meal_response`, `build_wizard_meal_prompt`, `_parse_valid_dishes`; dishes[] schema (G1c-3a); `_DISH_CATEGORIES` = `config.MEAL_DISH_CATEGORIES`; `_WIZARD_GEN_SLOT_CAP = 14` |
| `render_child_goals.py` | **351** | Per-child goals with substeps, deadlines, review integration |
| `render_school_pdf.py` | **343** | School week printable PDF — 15-page portrait Letter, one page per (child, weekday) |
| `render_child_profile.py` | **329** | Per-child profile card — bio, notes, preferences |
| `render_login.py` | **313** | Family login screen — avatar grid, PIN entry, instant login for littles |
| `render_plan_year.py` | **310** | Plan My Year — annual overview, all 4 quarters, all active goals |
| `render_readings.py` | **248** | Daily Mass readings — fetches citations from Catholic Readings API |
| `render_goals.py` | **237** | Goal system data helpers |
| `render_schedule_support.py` | **226** | Family schedule engine, now/next strip, timeline; split from render_schedule to avoid circular imports |
| `render_memory_book.py` | **210** | Family memory book — memorable moments saved from Lucy conversations |
| `render_frol_pdf.py` | **177** | FROL printable PDF — 7-page landscape Letter, one weekday per page |
| `render_seasons.py` | **147** | Phase F season-detection helper — 11 season labels (8 fixed-date + 3 moveable Catholic feasts), `upcoming_season(today)`; pure module, no I/O *(existed before rev 2 but was missing from prior PROJECT_STATE revisions — added in this re-scan)* |
| `render_meal_wizard_step5.py` | **133** | Meal Wizard Step 5 — Phase H1 shopping-day skeleton; `render_step5(user: str) -> str` (line 85); `_S5_DAYS` Monday–Sunday list (line 29); seven-button day picker, async fetch POST to `/meal-wizard-step5-save`, no-reload selected-state swap; JS as concatenated string literals (not f-string). OUT OF H1 SCOPE: conflict detection, John's-note field, Continue button |
| `render_wizards.py` | **99** | Wizards hub page — static list of family wizards as tappable cards |
| `render_companions.py` | **54** | Standalone `/companions` page — directory of the six AI companions *(existed before rev 2 but was missing from prior PROJECT_STATE revisions — added in this re-scan)* |

---

## Section 6 — Family Quest sub-app (`family_quest/`)

Isolated sub-application. Most modules must not import from the parent directory.
Only `fq_api.py` and `fq_bridge.py` bridge to the main app.

| File | Lines | Role |
|---|---|---|
| `family_quest/fq_data.py` | **2,000** | All game logic and data access (dual currency, energy, heroes, bosses, fortress, mining) |
| `family_quest/fq_views_child.py` | **1,173** | Child-facing game views |
| `family_quest/fq_bridge.py` | **762** | Bridge between main app and Family Quest |
| `family_quest/fq_views_parent.py` | **661** | Parent-facing game views |
| `family_quest/app.py` | **505** | Family Quest's own HTTP handler |
| `family_quest/fq_render.py` | **222** | Shared render helpers for the sub-app |
| `family_quest/fq_api.py` | **68** | Family Quest's adapter for main app functionality |
| `family_quest/fq_auth.py` | **32** | Auth for the sub-app |
| `family_quest/__init__.py` | 0 | Package marker |
| `family_quest/rewards.json` | — | Game reward definitions |

---

## Section 7 — Data files (`data/`)

All persistent data is JSON under `data/`. `config.py` owns all file paths;
`data_helpers.py` is the only module that should read/write these files.

### 7a. Subdirectories

| Path | Contents |
|---|---|
| `data/day_templates/` | 7 files (`Monday.json` … `Sunday.json`) — FROL, single source of truth for daily schedules |
| `data/meal_plan/` | Per-week meal plans; mix of `YYYY-MM-DD` and `YYYY-Www` key formats |
| `data/profiles/` | `james.json`, `john.json`, `joseph.json`, `jp.json`, `michael.json`, `mom.json` |
| `data/auth/` | `pins.json` (person→PIN map), `sessions.json` (active sessions) |

### 7b. `data/*.json` files on disk

| File | Stores |
|---|---|
| `app_settings.json` | Global settings, AI API keys, family identity, child colors, timezone, van rotation epoch |
| `assignment_analyses.json` | AI-analyzed assignment records |
| `calendar_cache.json` | Cached CalDAV events |
| `calendar_config.json` | Calendar connection settings |
| `calendar_rules.json` | Calendar display/filter rules |
| `chores.json` | Chore definitions per person |
| `coach_history.json` | Coach AI conversation history |
| `coach_last_writes.json` | Coach last data-write record (for undo) |
| `coach_programs.json` | Saved Coach fitness programs |
| `curriculum.json` | Curriculum subject/week/day records |
| `cycle_log.json` | Monthly cycle log entries |
| `dev_history.json` | Izzy/Felix dev AI conversation history |
| `events.json` | Family events |
| `exercise_assignments.json` | Coach-assigned weekly exercises |
| `exercise_logs.json` | Exercise completion logs |
| `family_memory.json` | Family memory entries |
| `felix_undo.json` | Dev AI undo history |
| `friends.json` | Friends & families directory entries |
| `frol_activities.json` | FROL activity definitions |
| `frol_wizard_progress.json` | FROL wizard step progress |
| `gradebook.json` | Gradebook assignment scores |
| `grades.json` | Grade records |
| `gregory_history.json` | Father Gregory AI conversation history |
| `gregory_last_writes.json` | Father Gregory last data-write (for undo) |
| `hour_tracking.json` | Hour tracking log entries |
| `kid_messages.json` | Messages between kids and Mom |
| `liturgical.json` | Liturgical calendar customizations |
| `lorenzo_history.json` | Lorenzo AI conversation history |
| `lorenzo_last_writes.json` | Lorenzo last data-write (for undo) |
| `lucy_history.json` | Lucy AI conversation history |
| `lucy_last_writes.json` | Lucy last data-write (for undo) |
| `manual_tasks.json` | Manually added tasks |
| `meal_history.json` | Recent-meals history *(lazy — created on first save)* |
| `meal_inventory.json` | Fridge/freezer/pantry inventory blob + `last_updated` |
| `meal_rules.json` | Meal planning rules/constraints |
| `meal_wizard_session.json` | Wizard session state (see §8 for key schema) |
| `memory_book.json` | Family memory book entries |
| `mom_notes.json` | Mom's personal notes |
| `monica_history.json` | Dr. Monica AI conversation history |
| `monthly_planner.json` | Monthly planner entries |
| `notes.json` | General notes |
| `pantry_staples.json` | Pantry staples checklist *(lazy — created on first save)* |
| `plan_import_history.json` | Plan import history records |
| `planning_session.json` | Planning session state |
| `poetry_passages.json` | Poetry passages for curriculum |
| `pope_intentions.json` | Pope's monthly prayer intentions |
| `prayer_intentions.json` | Family prayer intentions |
| `progress.json` | Task/school completion (`YYYY-MM-DD::Person::task` keys) |
| `recipes.json` | Recipe library |
| `roadmap.json` | Family roadmap items |
| `school_previews.json` | School week preview drafts |
| `school_week_plan.json` | School week plan |
| `school_weeks.json` | School week records |
| `seasonal_schedules.json` | Saved seasonal FROL schedule snapshots |
| `sister_mary_history.json` | Sister Mary AI conversation history |
| `subscribed_calendar_cache.json` | Cached subscribed calendar events |
| `subscribed_calendars.json` | Subscribed external calendar URLs |
| `task_overrides.json` | Per-day task overrides |
| `task_registry.json` | Task registry |
| `thankyou_reminders.json` | Thank-you note reminders |

---

## Section 8 — Meal Wizard session schema and dishes[] contract

### Session file keys (`data/meal_wizard_session.json`)

Shallow-merged via `data_helpers.update_meal_wizard_session()`. Writing a nested
key (e.g. `{"suggested_meals": {…}}`) replaces the whole nested dict — always
read-fresh → merge → write to preserve siblings (claud.md Rule 21).

**Live keys on disk, confirmed 2026-07-03 (all 10):** `confirmed_complexity`,
`confirmed_inventory`, `confirmed_meals`, `confirmed_shopping_day`,
`confirmed_what_to_plan`, `plan_locked_at`, `planning_window`, `suggested_meals`,
`use_soon_items`, `used_proteins`.

| Key | Set by | Meaning |
|---|---|---|
| `confirmed_inventory` | Phase E (Step 2) | Fridge/freezer/pantry text blob |
| `use_soon_items` | Phase E (Step 2) | Items to use soon |
| `confirmed_what_to_plan` | Phase F (Step 3) | List of meal slot types for the week |
| `confirmed_complexity` | Phase F (Step 3) | `simple` / `normal` / `ambitious` |
| `planning_window` | Phase F (Step 3) | `{start_iso, end_iso}` |
| `used_proteins` | Phase F (Step 3) | Proteins already confirmed; recomputed from confirmed_meals on each confirm |
| `confirmed_meals` | Phase G (Step 4) | Per-slot confirmed meals, keyed `"YYYY-MM-DD::slot"` |
| `suggested_meals` | Phase G (`/meal-wizard-generate`) | Lorenzo draft meals, same key format; merged not replaced |
| `plan_locked_at` | Phase G (`/meal-wizard-step4-lock`) | ISO timestamp when plan was locked |
| `confirmed_shopping_day` | **Phase H1 (Step 5, `/meal-wizard-step5-save`)** | Weekday name string (currently `"Saturday"` on disk from H1 testing); validated against `_S5_DAYS` server-side |

### Step 5 wiring (Phase H1, all four app.py anchors confirmed live 2026-07-03)

| Addition | app.py line |
|---|---|
| `from render_meal_wizard_step5 import render_step5, _S5_DAYS` | **258** |
| `elif path == "/meal-wizard-step5":` (GET) | **1358** |
| `/meal-wizard-step5-save` in `_JSON_PATHS` | **3582** |
| `elif path == "/meal-wizard-step5-save":` (POST) | **11036** |

(These happen to match the H1 report's numbers because no app.py edit has landed
since H1 — confirmed by fresh grep, not carried forward.)

### dishes[] slot data contract

Every slot entry in `confirmed_meals` / `suggested_meals`:

```json
{
  "dishes": [
    { "category": "main", "name": "…", "ingredients": "…", "protein": "…" },
    { "category": "side", "name": "…", "ingredients": "…", "protein": "" }
  ],
  "note": "optional slot-level note",
  "source": "lorenzo | manual | prefill",
  "recipe_id": "",
  "recipe_on_request": true,
  "skip_shopping": false
}
```

**Category allowlist:** `config.MEAL_DISH_CATEGORIES` —
`("main", "side", "soup", "bread", "salad", "appetizer", "dessert", "snack")`.
Single source of truth: both `render_meal_wizard_step4` (UI `<select>`) and
`render_meal_wizard_gen` (prompt + parser) import from config as of 2026-07-02.

**Multi-dish slots** (`dinner`, `feast_meal`): Lorenzo returns 2-3 dishes; parser
keeps all valid. **Single-dish slots** (all others): parser enforces a 1-dish cap —
keeps the first valid dish, drops the rest.

**Category validation (G1c-3a):** `_parse_valid_dishes()` in
`render_meal_wizard_gen` drops any dish whose `category` is absent or not in
`MEAL_DISH_CATEGORIES`. Does NOT default to `"main"`. Slots with zero valid dishes
are dropped from the result entirely.

**Generation prompt (G1c-3a):** `build_wizard_meal_prompt` now asks Lorenzo to
return `dishes[]` directly per slot. The parser reads `val.get("dishes")` — no
flat-to-dishes normalization. Old flat-shaped responses produce zero valid dishes
and are dropped (no compat shim).

**Read-time migration — `data_helpers.slot_dishes(entry)`:** the ONLY migrator for
legacy data. A flat entry (`{name, ingredients, protein}`) is synthesized into one
`{category: "main", …}` dish on read only — the stored file is never rewritten.
Always returns a list so callers iterate safely. Every read of slot dishes must go
through `slot_dishes()`.

**Display — `render_meals.format_dish_list(dishes)`:** collapses a slot's dish list
into one human string.

**Protein tracking — `data_helpers.recompute_used_proteins(confirmed_meals)`:**
walks every entry via `slot_dishes()`, collects each dish's `protein` (deduped,
lowercased, first-seen order).

### `/meal-wizard-step4-remove` handler (app.py line 10889 — shifted from 10878 in rev 2)

Idempotent removal of one confirmed meal (the "Change this meal" backing op).
Validates date + slot (400 on bad input). Before popping, captures the prior
confirmed entry's `dishes` list as `_s4r_prior_dishes`. After the pop + session
write, calls `render_step4_slot_and_lock(date, slot, revert_dishes=_s4r_prior_dishes)`.
Returns `{"ok": true, "slot_html": "…", "lock_html": "…", "lockable": bool}`.

The `revert_dishes` parameter ensures that when Lauren manually added dishes beyond
what Lorenzo suggested, those extra dishes pre-fill the reverted entry affordance —
they are not silently dropped because `suggested_meals` only had the original draft.

### `render_meal_wizard_gen.py` exports

| Name | Type | Purpose |
|---|---|---|
| `wizard_target_slot_keys(session)` | function | sorted list of unconfirmed `"YYYY-MM-DD::slot"` keys |
| `parse_wizard_meal_response(text, targets)` | function | parses Lorenzo's dishes[] JSON response into slot entries |
| `build_wizard_meal_prompt(session, targets)` | function | builds the one-pass generation prompt |
| `_parse_valid_dishes(raw_dishes, is_multi)` | helper | validates category, enforces single-dish cap |
| `_WIZARD_GEN_SLOT_CAP` | int (14) | max target slots per generation call; imported by app.py and render_meal_wizard_step4 |
| `_DISH_CATEGORIES` | tuple | `from config import MEAL_DISH_CATEGORIES as _DISH_CATEGORIES` |
| `_MULTI_DISH_SLOTS` | frozenset | `{"dinner", "feast_meal"}` |

---

## Section 9 — Verification harnesses (`data/verify_*.py`)

All harnesses run in-process against an isolated temp session file (Rule 10a).
`mw_test_isolation` must be the **literal first project import** — before
`config`, `data_helpers`, or any `render_*` — or it raises `ImportError` at
import time (mechanical enforcement, not procedural).

**No `verify_meal_wizard_step5.py` exists** — confirmed absent 2026-07-03 (checked
both repo root and `data/`). Correct per H1 scope: a standing Step 5 harness was
explicitly deferred and remains an offered follow-up, not built.

| File | Lines | Covers |
|---|---|---|
| `data/mw_test_isolation.py` | **141** | Isolation guard — raises at import if config/data_helpers loaded first; env-var override for `MEAL_WIZARD_SESSION_FILE` and `MEAL_PLAN_DIR`; `assert_isolated()`, `start_server()` |
| `data/verify_rule10a_badorder_fixture.py` | **50** | Deliberately-broken fixture proving the guard fires on wrong import order |
| `data/verify_phase_a.py` | **290** | Phase A: data layer helpers |
| `data/verify_phase_b.py` | **333** | Phase B: meal plan save/load |
| `data/verify_phase_c.py` | **187** | Phase C: pantry staples |
| `data/verify_phase_d.py` | **240** | Phase D: inventory |
| `data/verify_phase_e.py` | **237** | Phase E: Step 2 (inventory entry) |
| `data/verify_phase_f.py` | **244** | Phase F: Step 3 (planning selection) |
| `data/verify_phase_g.py` | **173** | Phase G: Step 4 integration |
| `data/verify_meal_wizard_g1a.py` | **224** | G1a: confirm/remove/protein logic against session helpers (snapshot+restore pattern — predates mw_test_isolation) |
| `data/verify_meal_wizard_gen.py` | **296** | G1c-1a + G1c-3a: generation data contract, dishes[] schema, truncation/drop tests (63 checks) |
| `data/verify_meal_wizard_step3.py` | **228** | Step 3 render checks |
| `data/verify_meal_wizard_step4.py` | **177** | Step 4 read-only screen checks |
| `data/verify_meal_wizard_step4_lock.py` | **307** | Step 4 lock + homepage gating (authenticated HTTP round-trip via in-process server) |
| `data/verify_meal_wizard_step4_writeloop.py` | **273** | Step 4 write loop: confirm/remove/guards, no-reload DOM contract, prefill lock rendering |
| `data/verify_meal_wizard_step4_remove.py` | **276** | `/meal-wizard-step4-remove` route: bad-input 400s, idempotent absent-slot 200, mixed-origin revert (Lauren-only dish survives), no-reload contract (slot_html + lock_html), sha256 integrity assertion on live session file before+after (added 2026-07-02) |
| `data/verify_meal_wizard_dish_join.py` | **101** | dish join / `format_dish_list` helpers |
| `data/verify_generate_midcall_race.py` | **163** | mid-call race condition guard (session merge) |
| `data/verify_generate_wipes_mirror.py` | **143** | confirms generate no longer wipes mirror entries |
| `data/verify_mirror_neighbor_untouched.py` | **120** | confirms neighbor slots unaffected by confirm |
| `data/verify_task_42.py` | **145** | Task 42 regression |

---

## Section 10 — AI companion notes

**Model in use:** `claude-haiku-4-5-20251001` — verified for all companion calls
(Lorenzo, Lucy, Father Gregory, Coach, Dr. Monica, Sister Mary). All calls via
`urllib.request` directly (no SDK); API key from `data/app_settings.json`.

**`claude-sonnet-4-20250514` is DEAD** — returns 404. Use `claude-sonnet-4-6`
for any Sonnet-class call; probe the model string before wiring.

**`_repair_and_parse_json()` is NOT universal** — it is a nested local function
inside the plan-import POST handler only (app.py line 8458 — shifted from ~8412).
Do not assume a shared JSON-repair helper exists elsewhere.

---

## Section 11 — What changed from the prior PROJECT_STATE.md (2026-07-02 rev 2)

| Item | Rev 2 said | Live scan 2026-07-03 rev 3 |
|---|---|---|
| `app.py` lines | **12,386** | **12,424** (+38: the four Phase H1 Step 5 additions — import, GET route, `_JSON_PATHS` member, POST handler) |
| `do_GET` start | line 773 | **line 774** |
| `do_POST` start | line 2268 | **line 2279** |
| `_JSON_PATHS` location / size | line 3571, 10 members | **line 3582, 11 members** (+`/meal-wizard-step5-save`) |
| `/meal-wizard-step4-remove` handler | line 10878 | **line 10889** |
| `_repair_and_parse_json` | ~line 8412 | **line 8458** |
| `render_meal_wizard_step5.py` | **not present** | **new — 133 lines**; `render_step5(user: str) -> str` (line 85), `_S5_DAYS` (line 29); Phase H1 shopping-day skeleton |
| Step 5 routes | none | GET `/meal-wizard-step5` (app.py 1358), POST `/meal-wizard-step5-save` (app.py 11036) |
| `render_meal_wizard_step4.py` lines | **792** | **801** (+9: day-header season-color change + step4→step5 banner link) |
| Step 4 day-header color | `_S4_DAY_HEADER` included `color:var(--ink);` | `_S4_DAY_HEADER` (line 64) has **no color property**; h3 f-string (line 502) interpolates `color:{season_color};` sanitized via `_s4_safe_color` (line 499) |
| Session keys | 9 documented | **10** — `confirmed_shopping_day` added (live on disk, value `"Saturday"` from H1 testing) |
| `render_seasons.py` (147) / `render_companions.py` (54) | **absent from doc** | **added** — both existed on disk before rev 2 but were missed by prior scans; full-scan gap now closed |
| Git reference | not recorded | `main` = `ba20274ab6a60657179511515903ea4468a1da95` |
| Step 5 harness | n/a | **confirmed NOT built** (`verify_meal_wizard_step5.py` absent — correct per H1 scope) |
