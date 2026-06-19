# PROJECT_STATE.md — Sancta Familia
Technical snapshot of the current codebase. Read at the start of future
sessions for a fast orientation. Generated 2026-06-19.

> Counts as of this snapshot (all derived from the current source, not carried
> forward): **99 exact-match + 16 prefix (`startswith`) GET routes** in `do_GET`;
> **203 exact-match + 1 prefix POST routes** in `do_POST`; **58 `render_*.py`
> modules**; **217 top-level functions in `data_helpers.py`**; 60 `data/*.json`
> files on disk.
>
> **Phase F (Meal Planning Wizard — Step 3) is complete.** New since the Phase E
> snapshot: GET `/meal-wizard-step3`; POST `/meal-wizard-step3-save` (registered
> in `_JSON_PATHS`); new module `render_meal_wizard_step3.py` (435 lines),
> re-exported from `render_meal_wizard.py`; the Step-3 session keys
> `confirmed_what_to_plan`, `confirmed_complexity`, `planning_window`, and
> `confirmed_meals` (prefill entries carry `skip_shopping` + `recipe_on_request`);
> harness `data/verify_meal_wizard_step3.py`.

---

## Section 1 — GET routes (defined in app.py `do_GET`)

Per Rule 3, all GET routing uses `elif` chains in `do_GET`. Auth-gated routes
pass through the global `viewer = _require_auth(path)` gate before rendering.
`do_GET` spans app.py lines ~748–2232.

### 1a. Exact-match routes (`path == "…"`) — 99

| Path | Renders / returns |
|---|---|
| `/login` | (inline) login page |
| `/logout` | redirect /login |
| `/quest-sso` | (inline) Family Quest SSO handoff |
| `/change-pin` | render: change-PIN page |
| `/` | render: render_timeblock_homepage() |
| `/today` | render: render_today_all() |
| `/programs` | render: render_programs_page() |
| `/set-school-mode` | calls clean_text(), redirect |
| `/now` | render: render_now_page() |
| `/week` | render: render_week_view() |
| `/week-school` | render: render_week_school_page() |
| `/school` | render: render_school_page() |
| `/api/today-progress` | JSON response |
| `/api/boys-tasks` | JSON response |
| `/api/child-tasks` | JSON response |
| `/gdrive-files` | JSON response (Google Drive) |
| `/kids-week` | render: render_kids_week_page() |
| `/plan-tomorrow` | render: render_plan_tomorrow_page() |
| `/plan-today` | render: render_plan_tomorrow_page() (today) |
| `/plan-week` | render: render_plan_week_page() |
| `/plan-month` | render: render_plan_month_page() |
| `/plan-year` | render: render_plan_year_page() |
| `/plan-quarter` | render: render_plan_quarter_page() |
| `/virtues` | render: render_virtues_dashboard() |
| `/5am` | render: render_5am_page() |
| `/liturgy-hours` | render: liturgy-of-the-hours page |
| `/prayer-intentions` | render: prayer intentions page |
| `/virtues/me` | render: render_virtue_me_page() |
| `/virtues/family` | render: render_virtue_family_page() |
| `/school/edit` | render: render_school_edit_page() |
| `/chores` | render: render_chores_page() |
| `/van-roles` | render: render_van_roles_page() |
| `/print/day` | (inline) printable day |
| `/print/week` | render: render_print_week() |
| `/notes` | render: render_notes() |
| `/tasks` | render: render_tasks() |
| `/thankyou-reminders` | render: render_thankyou_page() |
| `/mom` | render: render_mom_page() |
| `/mom-profile` | render: mom profile page |
| `/john` | render: John page |
| `/friends` | render: render_friends_page() |
| `/roadmap` | render: render_roadmap_page() |
| `/signup` | render: render_signup_page() |
| `/waitlist` | render: render_waitlist_admin() |
| `/family-schedule` | render: render_family_schedule_page() |
| `/frol-pdf` | generate_frol_pdf() (PDF) |
| `/school-week-pdf` | generate_school_pdf() (PDF) |
| `/calendar` | render: render_calendar_page() |
| `/planner` | render: render_planner_page() |
| `/readings` | render: render_readings_page() |
| `/lucy` | render: render_lucy_page() |
| `/lorenzo-plan-state` | JSON: Lorenzo planning session state |
| `/lorenzo` | render: render_lorenzo_page() |
| `/headmaster` | render: render_gregory_page() |
| `/coach` | render: render_coach_page() |
| `/dr-monica` | render: render_monica_page() |
| `/companions` | render: render_companions_page() |
| `/wizards` | render: render_wizards_page() |
| `/pantry-staples` | render: render_pantry_staples_page() |
| `/meal-wizard` | render: render_meal_wizard_week_glance() |
| `/meal-wizard-step2` | render: render_meal_wizard_step2() ← Phase E |
| `/meal-wizard-step3` | render: render_meal_wizard_step3() ← **Phase F** |
| `/sister-mary` | render: render_sister_mary_page() |
| `/frol-grid-fragment` | render: FROL grid fragment |
| `/frol-seasonal-view` | render: render_seasonal_view_page() |
| `/frol-wizard` | render: FROL wizard |
| `/daily-mass` | redirect: daily Mass video URL |
| `/plan-import-history` | render: plan-import history |
| `/grades` | render: render_grades_summary_page() |
| `/subject` | render: render_subject_page() |
| `/hour-report` | render: render_hour_report() |
| `/curriculum` | render: render_curriculum_page() |
| `/gradebook` | render: render_gradebook_page() |
| `/assignment-analyzer` | render: render_assignment_analyzer_page() |
| `/assignment-image` | serves stored assignment image |
| `/plan-import` | render: render_plan_import_page() |
| `/dev` | render: render_dev_page() (Izzy/Felix) |
| `/dev-logs` | JSON/inline: dev logs |
| `/dev-health` | JSON: health check |
| `/dev-diag` | inline: diagnostics |
| `/dev-read-file` | inline: read a file (dev) |
| `/dev-grep-files` | inline: grep (dev) |
| `/dev-git-log` | inline: git log (dev) |
| `/dev-git-diff` | inline: git diff (dev) |
| `/memory-book` | render: render_memory_book_page() |
| `/liturgical` | render: render_liturgical_page() |
| `/prayer` | render: render_liturgical_page() |
| `/liturgical/edit` | render: render_liturgical_edit_page() |
| `/settings` | render: render_settings_page() |
| `/history` | render: render_history_page() |
| `/history/preview` | inline: history snapshot preview |
| `/plan-fragment` | render: render_plan_fragment_html() |
| `/grid-print` | render: render_grid_print_page() |
| `/mom-step` | render: render_mom_step_fragment() |
| `/meals` | render: render_meal_planner_page() |
| `/meal-print` | render: render_meal_print_page() |
| `/recipes` | render: recipes page |
| `/api-key` | inline: API key status |
| `/calendar/refresh` | refresh_calendar(), redirect |

### 1b. Prefix routes (`path.startswith("…")`) — 16

| Prefix | Purpose |
|---|---|
| `/quest` | Family Quest sub-application handoff |
| `/static/js/` | serves JS assets |
| `/static/images/` | serves image assets |
| `/static/` | serves other static assets |
| `/prayer-photo/` | serves prayer intention photos |
| `/prayer-intention/share/` | shareable prayer intention view |
| `/virtues/child/` | render: render_virtue_child_page() |
| `/print/day/` | printable day for a date |
| `/uploads/recipes/` | serves recipe upload images |
| `/uploads/grades/`, `/uploads/grade_docs/` | serves grade upload files |
| `/schedule/` | render: render_child_schedule() |
| `/student/` | render: render_student_page() |
| `/grades/` | render: render_student_grades() |
| `/lucy-child-brief/` | Lucy child brief fragment |
| `/lucy-prayer-brief/` | Lucy prayer brief fragment |

---

## Section 2 — POST routes (defined in app.py `do_POST`)

Per Rule 3, POST routing matches the codebase convention of top-level
`if/elif path == "…":` blocks. `do_POST` begins at app.py line ~2233. There is
exactly **one** prefix POST match: `path.startswith("/quest")` (Family Quest
handoff); all other POST routes are exact matches (203 total).

**JSON-body routes** must be registered in `_JSON_PATHS` or the form-parser
silently consumes the payload. Current `_JSON_PATHS` (app.py ~line 3536):
`/plan-import-apply`, `/plan-import-undo-placement`, `/curriculum-save`,
`/curriculum-minutes`, `/poetry-passage-save`, **`/meal-wizard-step3-save`**
(← Phase F). All other POST handlers read the urlencoded `data`/form fields
(multipart sniffed per Rule 8).

**Auth & messaging:** `/login`, `/student-message-read`, `/message-mom`, `/change-pin`, `/messages-read`, `/save-pins`

**Meals & pantry:** `/pantry-staples-save`, `/meal-save-plan`, `/meal-rule-add`, `/meal-rule-delete`, `/meal-save-inventory`, `/meal-wizard-step2-save` ← Phase E, `/meal-wizard-step3-save` ← **Phase F (JSON)**, `/meal-generate`, `/meal-save-constraints`, `/meal-edit`, `/recipe-save`, `/recipe-import`, `/recipe-delete`

**Plan importer:** `/plan-import-save-session`, `/plan-import-history-delete`, `/plan-import-analyze`, `/plan-import-apply` (JSON), `/plan-import-undo-placement` (JSON), `/plan-import-consult`, `/plan-import-group-consult`, `/api/extract-suggestions`

**School / subjects / gradebook:** `/subject-upload-image`, `/subject-send-to-mom`, `/subject-grade-add`, `/subject-grade-delete`, `/subject-link-add`, `/subject-link-delete`, `/subject-doc-delete`, `/assignment-analyze`, `/assignment-update`, `/assignment-delete`, `/assignment-reply`, `/gradebook-add`, `/gradebook-update`, `/gradebook-delete`, `/school-upload`, `/approve-school-preview`, `/approve-school-week`, `/regenerate-school-week`, `/reparse-school-preview`, `/save-school-preview-edits`, `/school-settings-save`

**Curriculum:** `/curriculum-parse`, `/curriculum-save` (JSON), `/curriculum-minutes` (JSON), `/poetry-passage-save` (JSON), `/curriculum-week`, `/curriculum-subject-week`, `/curriculum-subject-day`, `/curriculum-delete`

**Tasks / notes / plan items:** `/toggle-task`, `/add-note`, `/archive-note`, `/convert-note`, `/add-task`, `/task-update`, `/task-done`, `/task-delete`, `/task-hard-delete`, `/task-purge-inactive`, `/task-override`, `/plan-add-item`, `/plan-toggle-item`, `/plan-item-update`, `/planner-add-task`, `/add-to-plan-quick`, `/plan-ai-suggest`

**Daily grid / anchor:** `/anchor-save`, `/grid-save-template`, `/grid-push-weekly`, `/grid-cell-save`, `/grid-publish`, `/grid-reset`, `/schedule-template-save`

**Chores / van:** `/save-chores`, `/apply-laundry`, `/apply-van-rotation`

**Thank-you notes:** `/thankyou-add`, `/thankyou-done`, `/thankyou-dismiss`, `/thankyou-suggest`

**Companions (chat / rules / history):** `/lucy-tts`, `/lucy-rule-save`, `/lucy-chat`, `/lucy-clear-history`, `/lorenzo-chat`, `/lorenzo-rule-save`, `/lorenzo-plan-start`, `/lorenzo-plan-end`, `/lorenzo-clear-history`, `/headmaster-chat`, `/headmaster-clear-history`, `/coach-chat`, `/coach-clear-history`, `/dr-monica-chat`, `/dr-monica-clear-history`, `/sister-mary-chat`, `/sister-mary-clear-history`, `/dev-chat`, `/dev-apply`, `/dev-write`, `/dev-undo`, `/dev-restart`, `/dev-clear`

**Coach programs / exercise / hours:** `/programs-save`, `/programs-delete`, `/programs-edit`, `/exercise-log`, `/hour-log-add`, `/hour-log-edit`, `/hour-log-delete`

**FROL wizard & seasonal:** `/frol-save-seasonal`, `/frol-seasonal-use`, `/frol-seasonal-delete`, `/frol-overlay-toggle`, `/frol-overlay-set`, `/frol-overlay-clear`, `/pod-dismiss-season`, `/pod-toggle-traveling`, `/frol-wizard`, `/frol-wizard-chat`, `/frol-wizard-finalize`, `/frol-set-variant`, `/frol-rollback-v3`, `/frol-delete-activity`, `/frol-edit-activity`

**Prayer / liturgical / memory:** `/prayer-intention-add`, `/prayer-intention-delete`, `/prayer-intention-log`, `/prayer-intention-complete`, `/timeblock-add-intention`, `/timeblock-add-novena`, `/liturgy-hours-save`, `/liturgical-save`, `/liturgical-delete`, `/liturgical-note`, `/memory-book-save`, `/memory-book-delete`, `/memory-update`

**Calendar:** `/calendar-config-save`, `/subscribed-cal-add`, `/subscribed-cal-toggle`, `/subscribed-cal-delete`, `/calendar-refresh`, `/calendar-add-event`, `/calendar-event-delete`

**Goals / quarter / children:** `/roadmap-add`, `/roadmap-update`, `/roadmap-delete`, `/child-goal-add`, `/child-goal-archive`, `/child-substep-add`, `/child-substep-toggle`, `/child-substep-delete`, `/quarter-save-goals`, `/quarter-journal-save`, `/quarter-save-step`, `/quarter-checkin`, `/goal-add`, `/save-child-profile`, `/virtue-checkin`

**Cycle:** `/cycle-log-add`, `/cycle-log-delete`, `/cycle-ai-suggest`, `/cycle-save`

**Plan tomorrow / week / month / AI briefs:** `/plan-tomorrow-questions`, `/plan-tomorrow-generate`, `/plan-tomorrow-push`, `/plan-week-save`, `/plan-month-save`, `/kids-week-save`, `/5am-save`, `/ai-daily-schedule`, `/ai-meal-plan`, `/ai-school-plan`, `/ai-evening-examen`, `/ai-weekly-review`, `/ai-chore-adjust`, `/ai-intention-prayer`, `/ai-capacity-preview`, `/ai-week-brief`, `/ai-month-brief`, `/ai-year-brief`, `/ai-suggest-goals`, `/ai-generate-steps`, `/preview-keep`, `/preview-discard`

**Profiles / signup / settings / misc:** `/save-mom-profile`, `/save-john-profile`, `/save-friend`, `/delete-friend`, `/mom-add-note`, `/history-restore`, `/signup-submit`, `/waitlist`, `/settings-save-ajax`, `/settings-save`

---

## Section 3 — Data files (data/)

All persistent data is JSON under `data/`. `config.py` owns all file paths;
`data_helpers.py` is the only module that should read/write these files. 60
`data/*.json` files are currently on disk (sizes are bytes from disk).

> **Lazily-created meal-wizard files:** `pantry_staples.json`, `meal_history.json`,
> and `meal_wizard_session.json` are **not on disk yet** — they are created by
> their `save_*` helpers on first write. Their absence is normal.

### Meal-related
| File | Size | Stores |
|---|---|---|
| `meal_inventory.json` | 917 B | Fridge/freezer/pantry/use-soon inventory blob + `last_updated` |
| `meal_rules.json` | 3.3 KB | Meal planning rules/constraints |
| `meal_plan/` (dir) | — | Per-week meal plans (`YYYY-Www` keys) |
| `recipes.json` | 46 KB | Recipe library |
| `pantry_staples.json` | *absent* | Pantry staples checklist (created on first save) |
| `meal_history.json` | *absent* | Recent-meals history (created on first save) |
| `meal_wizard_session.json` | *absent* | Wizard session state — see keys below (created on first save) |

**`meal_wizard_session.json` keys** (shallow-merged via `update_meal_wizard_session`):
- Phase E (Step 2): `confirmed_inventory`, `use_soon_items`
- Phase F (Step 3): `confirmed_what_to_plan` (list of meal types), `confirmed_complexity`
  (effort: simple/normal/ambitious), `planning_window` (`{start_iso, end_iso}`),
  `confirmed_meals` (per-day prefill entries; pre-filled past meals carry
  `skip_shopping: true` + `recipe_on_request: true` so they stay off the grocery
  list and never auto-generate a recipe card).

### Core app data
| File | Size | Stores |
|---|---|---|
| `app_settings.json` | 2.6 KB | Global settings + AI API keys + family identity |
| `progress.json` | 210 KB | Task/school completion (`YYYY-MM-DD::Person::task`) |
| `manual_tasks.json` | 13 KB | Manually added tasks |
| `task_overrides.json` | 16 KB | Per-day task overrides |
| `task_registry.json` | 58 KB | Task registry |
| `chores.json` | 8.8 KB | Chore definitions per person |
| `curriculum.json` | 413 KB | Curriculum data (per child/subject/week) |
| `monthly_planner.json` | 9.9 KB | Monthly planner |
| `gradebook.json` | 934 B | Gradebook entries |
| `grades.json` | 99 B | Grades summary |
| `assignment_analyses.json` | 17 KB | Assignment analyzer records |
| `events.json` | 30 KB | Local calendar events |
| `roadmap.json` | 1.1 KB | Roadmap ideas |
| `notes.json` | 3.9 KB | Notes |
| `mom_notes.json` | 236 B | Mom notes |
| `thankyou_reminders.json` | 256 B | Thank-you reminders |
| `memory_book.json` | 789 B | Memory book entries |
| `family_memory.json` | 2 B | Family memory store |
| `kid_messages.json` | 2 B | Kid → Mom messages |
| `friends.json` | 1.2 KB | Friends/other families |
| `cycle_log.json` | 236 B | Cycle log |
| `poetry_passages.json` | 152 B | Poetry passages |

### Calendar / liturgical / prayer
| File | Size | Stores |
|---|---|---|
| `calendar_config.json` | 62 B | Calendar config |
| `calendar_cache.json` | 1.2 KB | Cached calendar events |
| `calendar_rules.json` | 64 B | Calendar event filter rules |
| `subscribed_calendars.json` | 1.9 KB | Subscribed ICS calendars |
| `subscribed_calendar_cache.json` | 28 KB | Cached subscribed events |
| `liturgical.json` | 2 B | Custom liturgical overrides |
| `prayer_intentions.json` | 1.1 KB | Prayer intentions |
| `pope_intentions.json` | 1.7 KB | Pope's monthly intentions |

### FROL / scheduling
| File | Size | Stores |
|---|---|---|
| `frol_activities.json` | 16 KB | FROL activities (v3) |
| `frol_activities.v2_backup.json` | 5.4 KB | Pre-v3 activities backup |
| `frol_wizard_progress.json` | 16 KB | FROL wizard progress |
| `frol_wizard_progress.v2_backup.json` | 138 B | Pre-v3 wizard progress backup |
| `seasonal_schedules.json` | 2 B | Saved seasonal schedules |
| `day_templates/` (dir) | — | `{Weekday}.json` — FROL source of truth |
| `day_templates_preview/` (dir) | — | §15 "Preview this week" templates (when present) |
| `day_templates_backups/` (dir) | — | Timestamped backups before destructive writes |
| `day_grids/` (dir) | — | Per-date day grids |
| `daily_plans/` (dir) | — | Per-date daily plans |
| `hour_tracking.json` | 138 B | School hour tracking |
| `hour_reports/` (dir) | — | Hour-report snapshots |

### School (weeks / previews)
| File | Size | Stores |
|---|---|---|
| `school_week_plan.json` | 57 KB | Approved weekly school plan |
| `school_weeks.json` | 97 KB | School weeks data |
| `school_previews.json` | 51 KB | AI school previews |
| `plan_import_history.json` | 189 KB | Plan-import history + undo |

### Companion histories & undo
| File | Size | Stores |
|---|---|---|
| `lucy_history.json` | 28 KB | Lucy chat history |
| `lorenzo_history.json` | 28 KB | Lorenzo chat history |
| `gregory_history.json` | 49 KB | Father Gregory chat history |
| `coach_history.json` | 43 KB | Coach chat history |
| `monica_history.json` | 18 KB | Dr. Monica chat history |
| `sister_mary_history.json` | 9 KB | Sister Mary chat history |
| `dev_history.json` | 16 KB | Dev companion (Izzy/Felix) history |
| `{lucy,lorenzo,coach,gregory}_last_writes.json` | small | Per-companion undo (last data-altering action) |
| `felix_undo.json` | 135 KB | Dev (Felix) file-write undo log |
| `*.json.archive/` (dirs) | — | Rotated history archives (lorenzo, dev, sister_mary) |

### Coach / exercise / planning
| File | Size | Stores |
|---|---|---|
| `coach_programs.json` | 3.5 KB | Coach fitness programs |
| `exercise_logs.json` | 665 B | Exercise logs |
| `exercise_assignments.json` | 2.2 KB | Exercise assignments |
| `planning_session.json` | 21 B | Lorenzo planning session |

### Verification harnesses (data/)
`verify_phase_a.py` … `verify_phase_g.py`, **`verify_meal_wizard_step3.py`**
(← Phase F), `verify_task_42.py` — per Rule 10, all operate on temp copies of
live data and restore from backup; never run against live data. (Transient test
artifacts such as `_undo_smoke_test.json` may also appear on disk.)

---

## Section 4 — Modules and line counts

58 `render_*.py` modules plus the supporting top-level modules below. Line
counts are from disk. **Files over 800 lines are flagged ⚠️** (Rule: keep
modules under 800 lines where possible — many predate that target).

### 4a. Render modules (`render_*.py`)
- **render_frol_wizard.py** — 7681 ⚠️ — multi-phase Family Rule of Life wizard (sections 1–14, variant/schedule generators, finalize, seasonal view)
- **render_misc.py** — 5976 ⚠️ — dashboard, planner, now, mom page/step, notes, tasks, roadmap, history, school page/edit/preview, thank-you page
- **render_lucy.py** — 3362 ⚠️ — Lucy companion page + context builder + child/prayer briefs
- **render_schedule.py** — 2922 ⚠️ — per-child schedule, today-all, week, print day/week/child-day-list
- **render_settings.py** — 2291 ⚠️ — settings page + section builders + app-settings load/save
- **render_lorenzo.py** — 2199 ⚠️ — Lorenzo chef companion page + inventory/recipe/constraint/context helpers
- **render_timeblock.py** — 2134 ⚠️ — homepage time-block view (hours, saint/pope cards, meals/FROL snapshots, intentions widget)
- **render_meals.py** — 1647 ⚠️ — meal planner page, meal print, plan/inventory load+save, prompt builder
- **render_dev.py** — 1418 ⚠️ — Dev (Izzy/Felix) companion page + Felix context builder
- **render_subject.py** — 1402 ⚠️ — subject page, grades summary, hour report, entry/link/doc CRUD, AI image grading
- **render_plan_importer.py** — 1121 ⚠️ — plan-import page + analysis/consult/roundtable prompts (JS in static/js/plan_importer_{core,consult}.js)
- **render_virtues.py** — 1057 ⚠️ — virtue dashboards (me/family/child) + content generation
- **render_calendar.py** — 974 ⚠️ — CalDAV/ICS fetch, refresh, event merge, calendar page
- **render_prayer.py** — 968 ⚠️ — prayer / intentions page + helpers
- **render_plan_week.py** — 920 ⚠️ — weekly plan page + intentions load/save
- **render_daily_plan.py** — 869 ⚠️ — daily plan + day grid (seed/publish/reset, editor, fragment, print)
- **render_curriculum.py** — 858 ⚠️ — curriculum page, MODG paste parser, recent-submissions widget
- **render_chores.py** — 836 ⚠️ — chores page, van-roles card/page, kitchen/laundry/van rotation
- **render_plan_tomorrow.py** — 835 ⚠️ — plan-tomorrow page + AI question/plan generation
- **render_5am.py** — 720 — 5am routine dashboard widget + page
- **render_student.py** — 678 — student page + student grades
- **render_assignment_analyzer.py** — 676 — assignment analyzer page
- **render_plan_month.py** — 666 — monthly plan page
- **render_morning_anchor.py** — 652 — morning/evening anchor blocks + this-day-in-history
- **render_mom_profile.py** — 649 — Mom profile page
- **render_plan_quarter.py** — 641 — quarter plan page
- **render_gregory.py** — 617 — Father Gregory companion page + context builder
- **render_coach.py** — 599 — Coach companion page + context builder
- **render_meal_wizard.py** — 595 — pantry staples page, week-glance, Step 2 (`render_meal_wizard_step2`, `_s2_field`); **re-exports `render_meal_wizard_step3`** ← Phase F
- **render_liturgical.py** — 594 — liturgical engine (moveable feasts, seasons, fast/abstinence, vestment color), day card, page, edit page
- **render_monica.py** — 578 — Dr. Monica companion page + context builder
- **render_friends.py** — 570 — friends page + load/save
- **render_week_school.py** — 567 — week-school page + poetry passages load/save
- **render_sister_mary.py** — 525 — Sister Mary companion page + context builder
- **render_liturgy_hours.py** — 518 — liturgy-of-the-hours page + hour builders
- **render_week_view.py** — 517 — week view (feast/event/task helpers)
- **render_signup.py** — 516 — signup page + waitlist admin
- **render_ai_planner.py** — 461 — AI context packet + AI panel renderer
- **render_programs.py** — 458 — Coach programs page (card/grid)
- **render_kids_week.py** — 454 — kids-week page + week-plan load/save
- **render_meal_wizard_step3.py** — 435 — **Phase F: Meal Wizard Step 3** ("what to plan" — meal-type picker, effort, planning window, past-day prefill rows; inline JS builds the JSON payload)
- **render_john.py** — 433 — John page
- **render_gradebook.py** — 428 — gradebook page
- **render_daily_bar.py** — 413 — daily info bar (weather, birthdays, special events, child ages)
- **render_ai_daily.py** — 405 — AI daily/meal/school/examen/review/chore/intention generators
- **render_child_goals.py** — 351 — child goals + substeps CRUD + section
- **render_school_pdf.py** — 343 — school week PDF generation
- **render_child_profile.py** — 329 — child profile load/save + section + Lucy summary
- **render_login.py** — 313 — login page
- **render_plan_year.py** — 310 — yearly plan page
- **render_readings.py** — 248 — daily Mass readings fetch + page
- **render_goals.py** — 237 — quarter/goal helpers (quarters, master goals, check-ins, progress)
- **render_schedule_support.py** — 226 — now/next strip, timeline, litany block, family schedule page
- **render_memory_book.py** — 210 — memory book load/save/add/delete + page
- **render_frol_pdf.py** — 177 — FROL PDF generation
- **render_seasons.py** — 147 — season label/start/current/upcoming helpers
- **render_wizards.py** — 99 — wizards index page
- **render_companions.py** — 54 — companions index page

### 4b. Non-render modules
- **app.py** — 12092 ⚠️ — HTTP server, `do_GET`/`do_POST` routers, auth gate, AI dispatch
- **data_helpers.py** — 3317 ⚠️ — sole JSON read/write layer (see Section 5)
- **daily_schedule_engine.py** — 2642 ⚠️ — daily schedule building, task classification/carryover, `CHILDREN`
- **ui_helpers.py** — 1801 ⚠️ — shared HTML chrome, nav, `html_page`, escaping helpers
- **safe_utils.py** — 504 — `safe_save_json` (tmp + os.replace) and safe IO utilities
- **make_template.py** — 338 — day-template construction utility
- **school_pdf_engine.py** — 320 — school PDF layout engine
- **companion_handoffs.py** — 315 — cross-companion handoff context
- **father_gregory.py** — 304 — Father Gregory domain logic
- **saint_data.py** — 290 — saint-of-the-day data
- **auth.py** — 276 — authentication, sessions, access control
- **calendar_engine.py** — 230 — calendar computation engine
- **config.py** — 175 — all file paths + constants (see Section 6)
- **plan_history.py** — 165 — plan-import history helpers
- **web_fetch.py** — 141 — URL fetching for Lucy/readings
- **kid_helpers.py** — 80 — kid identity/message helpers
- **gdrive.py** — 73 — Google Drive connector access
- **notes_router.py** — 58 — notes routing helper

> **Stale/backup top-level files present:** `new_render_frol_wizard.py` (1272 ⚠️)
> and `old_render_frol_wizard.py` (1263 ⚠️) appear to be pre-/post-refactor copies
> of the FROL wizard and are not the live `render_frol_wizard.py`. Left in place;
> not imported by the app's active path.

### 4c. Shared static JS
- **static/inventory_input.js** (Phase E shared IIFE) defines `window.toggleMic`,
  `window.parseInventory`, `window.saveInventory` (→ `/meal-save-inventory`),
  `window.clearInventory` (client-side only), `window.saveInventoryWizard`
  (→ `/meal-wizard-step2-save`). Loaded by the meals page (`render_meals.py`) and
  Step 2 (`render_meal_wizard.py`).
- **render_meal_wizard_step3.py** carries its **own inline JS** (Rule 7/12 compliant)
  that builds the `{what_to_plan, complexity, planning_window, prefill}` payload and
  POSTs JSON to `/meal-wizard-step3-save`.
- **static/js/plan_importer_core.js**, **static/js/plan_importer_consult.js** — Plan
  Importer client logic.

---

## Section 5 — data_helpers.py functions (217 top-level)

`data_helpers.py` is the single read/write layer for `data/*.json`. The complete
list of top-level functions, grouped:

### Snapshots / dates
`list_snapshots`, `restore_snapshot`, `load_snapshot_data`, `today_iso`, `tomorrow_iso`, `monday_iso_for`, `normalize_date_query`

### School week plan
`load_school_week_plan`, `save_school_week_plan`, `generate_weekly_school_plan`, `get_approved_school_week_plan`

### Cleaning / parsing
`safe_int`, `clean_priority`, `clean_status`, `clean_child`, `clean_text`, `clean_weekday`, `lines_to_list`, `count_school_check_items`, `is_math_subject`, `is_math_test_text`, `sort_school_days`, `as_text`

### Progress / tasks / recurrence
`load_progress`, `load_manual_tasks`, `save_manual_tasks`, `active_manual_tasks`, `ensure_manual_task_ids`, `_nth_weekday_of_month`, `_add_months`, `_next_specific_weekday`, `_next_monthly_day`, `format_recurrence_label`, `advance_recurring_task`

### Task overrides
`load_task_overrides`, `save_task_overrides`, `set_task_override`, `clear_task_override`, `get_day_overrides`, `get_postponed_for_day`

### Chores / grooming
`_ensure_chore_buckets`, `load_chores_data`, `save_chores_data`, `_resolve_chore_person`, `get_chores_due_today`, `get_due_grooming`

### Hours
`load_hour_tracking`, `save_hour_tracking`, `add_hour_log`, `save_hour_report_snapshot`, `get_hour_totals`

### FROL activities / seasonal
`_activity_new_id`, `_file_has_legacy_activities`, `_ensure_activities_backup`, `_upgrade_activity_v2_to_v3`, `load_frol_activities`, `save_frol_activities`, `load_seasonal_schedules`, `_seasonal_snapshot_day_templates`, `save_seasonal_schedule`, `get_seasonal_schedule`, `find_seasonal_schedule_for`, `_summarize_prior_seasonal_entry`, `delete_seasonal_schedule`, `get_seasonal_context`, `get_companion_seasonal_block`

### Roadmap / notes / liturgical config
`load_roadmap`, `save_roadmap`, `load_mom_notes`, `save_mom_notes`, `load_liturgical_custom`, `save_liturgical_custom`

### Calendar
`load_calendar_config`, `save_calendar_config`, `load_calendar_cache`, `save_calendar_cache`, `load_subscribed_calendar_cache`, `save_subscribed_calendar_cache`, `load_calendar_rules`, `save_calendar_rules`, `load_subscribed_calendars`, `save_subscribed_calendars`, `load_local_events`, `save_local_events`, `expand_local_events_for_range`, `get_merged_calendar_events`

### Schedule / day templates / FROL text
`load_family_schedule`, `save_family_schedule`, `get_frol_day_slots`, `load_day_template`, `get_frol_times`, `get_family_rule_of_life_text`, `get_full_frol_context`

### Coach / exercise
`load_exercise_assignments`, `save_exercise_assignments`, `load_coach_programs`, `save_coach_program`, `load_exercise_logs`, `save_exercise_log`, `delete_coach_program`

### Companion histories (load/save/append/clear)
`_archive_history_file`, `_safe_clear`, and per-companion `load_*_history` / `save_*_history` / `append_*_messages` / `clear_*_history` for Lucy, Lorenzo, Gregory, Coach, Dev, Monica, Sister Mary

### Thank-you reminders
`load_thankyou_reminders`, `save_thankyou_reminders`, `pending_thankyou_reminders`, `due_thankyou_reminders`, `due_thankyou_reminders_for`

### Assignments / gradebook
`load_assignment_analyses`, `save_assignment_analyses`, `add_assignment_analysis`, `update_assignment_analysis`, `delete_assignment_analysis`, `percent_to_letter`, `letter_to_gpa`, `school_year_for_date`, `load_gradebook`, `save_gradebook`, `add_gradebook_entry`, `update_gradebook_entry`, `delete_gradebook_entry`, `gradebook_for_child`

### Recipes
`load_recipes`, `save_recipes`, `get_recipe_by_id`, `save_recipe`, `add_recipe`, `delete_recipe`, `search_recipes`

### Lorenzo planning session
`load_planning_session`, `save_planning_session`, `start_planning_session`, `advance_planning_session`, `clear_planning_session`, `planning_session_summary`

### Curriculum
`load_monthly_planner`, `load_curriculum`, `save_curriculum`, `get_curriculum_week`, `get_curriculum_subjects`, `week_day_segments`, `resolve_week_text`, `get_curriculum_week_assignments`, `subject_meeting_days`, `subject_day_index`, `advance_curriculum_cursor`, `load_curriculum_library`, `save_curriculum_library`, `get_subject_by_id`, `get_assignments_for_student`, `load_student_submissions`, `save_student_submissions`, `add_student_submission`, `get_submissions_for_grading`, `get_submissions_by_student`, `load_grading_history`, `save_grading_history`, `add_grade_record`, `load_curriculum_documents`, `save_curriculum_documents`, `add_curriculum_document`

### Family memory
`load_family_memory`, `save_family_memory`, `_now_ts`, `add_memory`, `update_memory`, `delete_memory`, `_tokenize_memory`, `find_memory_conflicts`, `get_memory_context_block`

### Prayer / pope / novenas
`load_prayer_intentions`, `save_prayer_intentions`, `add_daily_intention`, `add_repeating_intention`, `add_novena`, `get_active_intentions_for_date`, `check_upcoming_novenas`, `load_pope_intentions`, `save_pope_intentions`, `get_pope_intention_for_month`

### Meals (Phase E + Phase F)
`load_pantry_staples`, `save_pantry_staples`, `load_meal_history`, `save_meal_history`, `add_meal_history_entry`, `get_recent_meals`, `load_meal_wizard_session`, `save_meal_wizard_session`, `clear_meal_wizard_session`, **`update_meal_wizard_session`** (shallow-merge; written by both Step 2 and Step 3)

---

## Section 6 — config.py constants (verbatim from disk)

```python
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8000))

# Core data file paths
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

# FROL day-template paths
DAY_TEMPLATES_DIR         = "data/day_templates"
DAY_TEMPLATES_PREVIEW_DIR = "data/day_templates_preview"
DAY_TEMPLATES_BACKUP_DIR  = "data/day_templates_backups"

# Seasonal schedule library
SEASONAL_SCHEDULES_FILE   = "data/seasonal_schedules.json"

# Meal Planning Wizard (six constants)
MEALS_DIR                = "data/meal_plan"
MEAL_RULES_FILE          = "data/meal_rules.json"
MEAL_INVENTORY_FILE      = "data/meal_inventory.json"
PANTRY_STAPLES_FILE      = "data/pantry_staples.json"
MEAL_HISTORY_FILE        = "data/meal_history.json"
MEAL_WIZARD_SESSION_FILE = "data/meal_wizard_session.json"

# Validation sets
VALID_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}
VALID_STATUSES   = {"active", "done", "inactive"}

# Time / calendar
WEEKDAYS      = ["Monday", … "Sunday"]
WEEKDAY_ORDER = {day: i for i, day in enumerate(WEEKDAYS)}
SCHEDULE_DAYS = ["Monday", … "Saturday"]
MONTH_NAMES   = ["January", … "December"]

# Task / roadmap
ROADMAP_STATUSES = ["Someday", "Ready", "In Progress", "Done"]
ASSIGNABLE_TO    = ["Mom"] + list(CHILDREN)   # CHILDREN imported from daily_schedule_engine

# Child / parent identity (defaults; overridden at runtime from app_settings.json)
_DEFAULT_CHILD_COLORS  = { JP, Joseph, Michael, James … }
CHILD_COLORS           = _load_child_colors()
_DEFAULT_PARENT_COLORS = { Lauren, John … }
# functions: child_color(), parent_color()

# Van rotation
VAN_ROTATION_EPOCH = _load_van_epoch()   # default date(2025, 1, 6)
VAN_ROLE_A = "Interior Reset Lead"
VAN_ROLE_B = "Bin & Organization Lead"

# App-level settings helpers
get_app_setting(), get_family_name(), get_timezone(), get_schedule_hours()
```

All six meal-wizard constants are present. `CHILDREN` is imported from
`daily_schedule_engine`, and family identity/colors/timezone/van-epoch are read
at runtime from `app_settings.json` (family specifics stay out of hardcoded
config, per Rule 19).

---

## Section 7 — Current claud.md rules (full text, verbatim from disk)

Reproduced verbatim from `claud.md`. Rules 1–12 are the "Python 3.11 hard
rules"; rules 13–19 are the "Additional rules" section.

```
1. No backslashes inside f-strings
2. No nested quotes inside f-strings — use a variable outside the f-string instead
3. All GET routing uses elif chains in do_GET — never a bare if, never nested
   if blocks for routing. POST routing in do_POST uses standalone
   if path == ...: ... return blocks at the top level — this is the real
   convention in this codebase and must be matched exactly. Never use nested
   if blocks for routing in either handler.
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
```

---

## Phase F confirmation checklist (Meal Wizard Step 3)

- ✅ `render_meal_wizard_step3.py` exists (435 lines) and defines `render_meal_wizard_step3`
- ✅ `render_meal_wizard.py` re-exports it: `from render_meal_wizard_step3 import render_meal_wizard_step3`
- ✅ GET `/meal-wizard-step3` present in `do_GET`; Step 2's "Save and continue" links to it
- ✅ POST `/meal-wizard-step3-save` present in `do_POST` **and registered in `_JSON_PATHS`**
- ✅ Step 3 writes session keys `confirmed_what_to_plan`, `confirmed_complexity`, `planning_window`, `confirmed_meals`
- ✅ Pre-filled past-day entries carry `skip_shopping: true` + `recipe_on_request: true` (locked; off grocery list; no auto recipe card)
- ✅ Harness `data/verify_meal_wizard_step3.py` present (temp-copy, restore-on-finish per Rule 10)

**Phase F landed as reported.** All Phase E deliverables remain in place
(GET `/meal-wizard`, `/meal-wizard-step2`; POST `/pantry-staples-save`,
`/meal-save-inventory`, `/meal-wizard-step2-save`; `static/inventory_input.js`;
the six `config.py` meal constants; the meal-wizard `data_helpers` helpers).
