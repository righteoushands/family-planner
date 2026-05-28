# PROJECT_STATE.md — Sancta Familia
Technical snapshot of the current codebase. Read at the start of future
sessions for a fast orientation. Generated 2026-05-27.

---

## Section 1 — GET routes (defined in app.py do_GET)

110 routes total.

| Path | Renders / returns |
|---|---|
| `/` | Login screen (when unauthenticated) or family dashboard |
| `/5am` | 5AM Club personal-discipline tracker page |
| `/api/boys-tasks` | JSON: today's task list for JP/Joseph/Michael |
| `/api/child-tasks` | JSON: today's task list for a single child (?child=…) |
| `/api/today-progress` | JSON: completion ratios per person for today |
| `/api-key` | Settings page for entering Anthropic API key |
| `/assignment-analyzer` | Assignment Analyzer upload/parse UI |
| `/assignment-image` | Serves uploaded assignment images from data/assignment_uploads/ |
| `/calendar` | Family calendar page (events + liturgical overlay) |
| `/calendar/refresh` | Force-refresh subscribed calendar caches, redirect back |
| `/chores` | Chores + laundry + van rotation page |
| `/coach` | Coach (family fitness companion) page |
| `/companions` | Directory of the six AI companions |
| `/curriculum` | Curriculum library + subject-by-subject planner |
| `/daily-mass` | Today's daily Mass readings page |
| `/dev` | Isidore (Izzy) dev help-desk console |
| `/dev-diag` | Detailed diagnostics (system, processes, ports) |
| `/dev-git-diff` | Git diff viewer |
| `/dev-git-log` | Git log viewer |
| `/dev-grep-files` | Grep across project files (dev tool) |
| `/dev-health` | Workflow health-check summary |
| `/dev-logs` | Recent workflow + console logs |
| `/dev-read-file` | Read a project file (dev tool, path-restricted) |
| `/dr-monica` | Dr. Monica (pediatric / child-development companion) page |
| `/family-schedule` | Editable family Rule-of-Life schedule by weekday |
| `/friends` | Friends & Families directory page |
| `/frol-grid-fragment` | HTMX-style fragment: just the FROL grid table |
| `/frol-pdf` | Printable PDF of the Family Rule of Life |
| `/frol-seasonal-view` | Read-only view of a saved seasonal schedule snapshot |
| `/frol-wizard` | Rule-of-Life Wizard (multi-section guided builder) |
| `/gdrive-files` | Google Drive file browser (lists + import) |
| `/gradebook` | Per-child gradebook of recorded assignment scores |
| `/grades` | Grades index / overview page |
| `/grid-print` | Printable view of a day's family schedule grid |
| `/headmaster` | Father Gregory (academic headmaster) companion page |
| `/history` | History page with restore points |
| `/history/preview` | Preview of a historic state before restore |
| `/hour-report` | Generated hour-tracking report for a person/subject |
| `/john` | John's personal profile page |
| `/kids-week` | Kids' weekly planning page |
| `/liturgical` | Liturgical calendar page |
| `/liturgical/edit` | Editor for a single liturgical-day entry |
| `/liturgy-hours` | Liturgy of the Hours page |
| `/lorenzo` | Lorenzo (personal chef) companion page |
| `/lorenzo-plan-state` | JSON: current Lorenzo meal-planning session state |
| `/lucy` | Lucy (Catholic day-guide) companion page |
| `/meal-print` | Printable weekly meal plan |
| `/meals` | Weekly meal planning page |
| `/memory-book` | Family memory book page |
| `/mom` | Lauren's mom dashboard for a given date |
| `/mom-profile` | Lauren's personal profile page |
| `/mom-step` | One step of Lauren's morning anchor workflow |
| `/notes` | Notes page |
| `/now` | "What's now / what's next" strip |
| `/plan-fragment` | HTMX-style fragment: a sub-section of the planner |
| `/plan-import` | Plan-Importer tool (paste text → AI extract) |
| `/plan-import-history` | History of past Plan-Importer applies, with undo |
| `/plan-month` | Plan-My-Month tool |
| `/plan-quarter` | Plan-My-Quarter tool |
| `/plan-today` | AI-powered plan-today tool |
| `/plan-tomorrow` | AI-powered plan-tomorrow tool |
| `/plan-week` | Plan-My-Week tool |
| `/plan-year` | Plan-My-Year tool |
| `/planner` | Single-day planner page |
| `/prayer` | Liturgical / prayer page (alias of /liturgical) |
| `/prayer-intention/share/` | Public share URL for a prayer intention |
| `/prayer-intentions` | Prayer intentions list page |
| `/prayer-photo/` | Serves uploaded prayer-intention photos |
| `/print/day` | Printable single-day schedule |
| `/print/day/` | Printable single-day schedule (with trailing path arg) |
| `/print/week` | Printable weekly schedule |
| `/programs` | Coach's saved exercise programs + weekly assignments |
| `/quest` | Family Quest landing (proxied via fq_bridge) |
| `/quest/` | Family Quest sub-paths (proxied) |
| `/quest-sso` | Single-sign-on bridge into Family Quest |
| `/readings` | Daily Mass readings for a given date |
| `/recipes` | Recipe library page |
| `/roadmap` | Project roadmap page |
| `/schedule/` | Per-person schedule pages |
| `/school` | School/homeschool dashboard |
| `/school/edit` | Editor for a single child's school assignment |
| `/school-week-pdf` | Printable PDF of the weekly school plan |
| `/set-school-mode` | Toggle "school mode" flag for today |
| `/settings` | Settings page (single source of truth UI) |
| `/signup` | Beta waitlist signup survey |
| `/sister-mary` | Sister Mary (contemplative Marian companion) page |
| `/static/` | Static asset server (CSS, JS, images) |
| `/static/images/` | Static-image server |
| `/static/js/` | Static-JS server |
| `/student/` | Student portal (per-child read-only view) |
| `/subject` | Per-subject curriculum review page |
| `/subscribed-cal-…` | (covered under POST) |
| `/tasks` | Tasks page |
| `/thankyou-reminders` | Thank-you-note reminder page |
| `/today` | "Today" dashboard — compact per-child task cards |
| `/uploads/grade_docs/` | Serves uploaded gradebook documents |
| `/uploads/grades/` | Serves uploaded grade-related files |
| `/uploads/recipes/` | Serves uploaded recipe images |
| `/van-roles` | Van-rotation role assignments page |
| `/virtues` | Virtue tracker landing |
| `/virtues/child/` | Per-child virtue tracker |
| `/virtues/family` | Family virtue tracker |
| `/virtues/me` | Personal virtue tracker (current viewer) |
| `/waitlist` | Beta waitlist admin viewer |
| `/week` | Family weekly schedule grid |
| `/week-school` | Weekly school progress page |

---

## Section 2 — POST routes (defined in app.py do_POST)

227 routes total. Path → effect.

| Path | Effect |
|---|---|
| `/5am-save` | Save a 5AM-Club entry for today |
| `/add-note` | Add a new note |
| `/add-task` | Add a new manual task |
| `/add-to-plan-quick` | Quick-add an item to today's daily plan |
| `/ai-capacity-preview` | Preview AI capacity estimate for a workload |
| `/ai-chore-adjust` | AI-adjust chore distribution |
| `/ai-daily-schedule` | AI-generate today's family schedule |
| `/ai-evening-examen` | AI-generate the evening examen prompt |
| `/ai-generate-steps` | AI-generate substeps for a goal |
| `/ai-intention-prayer` | AI-generate a written prayer for an intention |
| `/ai-meal-plan` | AI-generate a weekly meal plan |
| `/ai-month-brief` | AI-generate a month-ahead brief |
| `/ai-school-plan` | AI-generate a weekly school plan |
| `/ai-suggest-goals` | AI-suggest goals for a child or person |
| `/ai-week-brief` | AI-generate a week-ahead brief |
| `/ai-weekly-review` | AI-generate a weekly review summary |
| `/ai-year-brief` | AI-generate a year-ahead brief |
| `/anchor-save` | Save morning-anchor or evening-anchor responses |
| `/api/extract-suggestions` | JSON API: AI-extract suggestion items from text |
| `/apply-laundry` | Apply laundry rotation for the week |
| `/apply-van-rotation` | Apply van rotation for the week |
| `/approve-school-preview` | Approve a generated school-preview into school_weeks |
| `/approve-school-week` | Mark a school-week plan as approved |
| `/archive-note` | Archive a note |
| `/assignment-analyze` | Run AI assignment analyzer on uploaded content |
| `/assignment-analyzer` | (POST upload entry) Upload + analyze assignment |
| `/assignment-delete` | Delete an assignment record |
| `/assignment-reply` | Submit a reply on an assignment |
| `/assignment-update` | Update an assignment record |
| `/calendar-add-event` | Add a local calendar event |
| `/calendar-config-save` | Save calendar configuration |
| `/calendar-event-delete` | Delete a local calendar event |
| `/calendar-refresh` | Force-refresh calendar caches |
| `/calendar-save-config` | (alias) Save calendar configuration |
| `/change-pin` | Change a user's auth PIN |
| `/child-goal-add` | Add a child-level goal |
| `/child-goal-archive` | Archive a child-level goal |
| `/child-substep-add` | Add a substep under a child goal |
| `/child-substep-delete` | Delete a substep |
| `/child-substep-toggle` | Toggle substep completion |
| `/coach` | (POST entry) Coach companion form post |
| `/coach-chat` | Send a chat message to Coach |
| `/coach-clear-history` | Wipe Coach chat history (with archive) |
| `/convert-note` | Convert a note into a task |
| `/curriculum` | (POST entry) Curriculum form post |
| `/curriculum-delete` | Delete a curriculum entry |
| `/curriculum-minutes` | Save curriculum minutes-per-week target |
| `/curriculum-parse` | AI-parse a pasted curriculum syllabus |
| `/curriculum-save` | Save curriculum edits |
| `/curriculum-subject-day` | Save per-day curriculum cell |
| `/curriculum-subject-week` | Save a week's curriculum text for a subject |
| `/curriculum-week` | Save curriculum week pointer |
| `/cycle-ai-suggest` | AI-suggest cycle-tracking insights |
| `/cycle-log-add` | Add a cycle-log entry |
| `/cycle-log-delete` | Delete a cycle-log entry |
| `/cycle-save` | Save cycle-tracking data |
| `/delete-friend` | Delete a friend record |
| `/dev` | (POST entry) Izzy dev-console form post |
| `/dev-apply` | Apply a dev-suggested change |
| `/dev-chat` | Send a chat message to Izzy |
| `/dev-clear` | Wipe Izzy chat history |
| `/dev-restart` | Restart the app workflow |
| `/dev-undo` | Undo the most recent dev write |
| `/dev-write` | Write a file via the dev tool |
| `/dr-monica` | (POST entry) Dr. Monica form post |
| `/dr-monica-chat` | Send a chat message to Dr. Monica |
| `/dr-monica-clear-history` | Wipe Dr. Monica chat history |
| `/exercise-log` | Save a post-workout log |
| `/family-schedule-save` | Save the family Rule-of-Life schedule |
| `/frol-add-activity` | Add a FROL activity (wizard or settings) |
| `/frol-delete-activity` | Delete a FROL activity |
| `/frol-edit-activity` | Edit a FROL activity |
| `/frol-overlay-clear` | Clear the year-over-year overlay state |
| `/frol-overlay-set` | Set overlay source for the grid preview |
| `/frol-overlay-toggle` | Toggle overlay visibility |
| `/frol-rollback-v3` | Roll back FROL data from v3 backup |
| `/frol-save-seasonal` | Save current schedule to seasonal library (Phase F) |
| `/frol-seasonal-delete` | Delete a saved seasonal schedule entry |
| `/frol-seasonal-use` | Load saved seasonal entry as starting point |
| `/frol-set-variant` | Switch FROL variant tab (weekday/weekend/etc.) |
| `/frol-wizard` | Wizard "Save & Continue" handler (advance step) |
| `/frol-wizard-chat` | Send a chat message inside the wizard |
| `/frol-wizard-finalize` | Finalize the wizard → write live templates |
| `/goal-add` | Add a personal/family goal |
| `/gradebook-add` | Add a gradebook entry |
| `/gradebook-delete` | Delete a gradebook entry |
| `/gradebook-update` | Update a gradebook entry |
| `/grid-cell-save` | Save a single cell of the schedule grid |
| `/grid-publish` | Publish a previewed grid as live templates |
| `/grid-push-weekly` | Push grid edits to weekly templates |
| `/grid-reset` | Reset grid to template defaults |
| `/grid-save-template` | Save a grid as a reusable template |
| `/headmaster` | (POST entry) Father Gregory form post |
| `/headmaster-chat` | Send a chat message to Father Gregory |
| `/headmaster-clear-history` | Wipe Father Gregory chat history |
| `/history-restore` | Restore a historic snapshot |
| `/hour-log-add` | Add an hour-tracking log entry |
| `/hour-log-delete` | Delete an hour-tracking log entry |
| `/hour-log-edit` | Edit an hour-tracking log entry |
| `/john` | (POST entry) John profile form post |
| `/kids-week-save` | Save the kids' weekly plan |
| `/liturgical-delete` | Delete a liturgical-day custom entry |
| `/liturgical-note` | Save a note on a liturgical day |
| `/liturgical-save` | Save liturgical-day customisation |
| `/liturgy-hours-save` | Save Liturgy-of-the-Hours entry |
| `/login` | Submit login PIN |
| `/lorenzo` | (POST entry) Lorenzo form post |
| `/lorenzo-chat` | Send a chat message to Lorenzo |
| `/lorenzo-clear-history` | Wipe Lorenzo chat history |
| `/lorenzo-plan-end` | End the current Lorenzo meal-plan session |
| `/lorenzo-plan-start` | Start a Lorenzo meal-plan session |
| `/lorenzo-rule-save` | Save a Lorenzo system-rule edit |
| `/lucy` | (POST entry) Lucy form post |
| `/lucy-chat` | Send a chat message to Lucy |
| `/lucy-clear-history` | Wipe Lucy chat history |
| `/lucy-rule-save` | Save a Lucy system-rule edit |
| `/lucy-tts` | Generate text-to-speech audio via Lucy |
| `/meal-edit` | Edit a meal-plan cell |
| `/meal-generate` | Generate a meal plan (non-AI helper) |
| `/meal-rule-add` | Add a meal-planning rule |
| `/meal-rule-delete` | Delete a meal-planning rule |
| `/meal-save-constraints` | Save meal-plan dietary constraints |
| `/meal-save-inventory` | Save pantry inventory |
| `/meal-save-plan` | Save the current meal plan |
| `/memory-book-delete` | Delete a memory-book entry |
| `/memory-book-save` | Save a memory-book entry |
| `/memory-update` | Update a family-memory item |
| `/message-mom` | Send a message to Mom |
| `/messages-read` | Mark mom-inbox messages as read |
| `/mom` | (POST entry) Mom dashboard form post |
| `/mom-add-note` | Add a quick note from the mom dashboard |
| `/mom-profile` | (POST entry) Mom profile form post |
| `/notes` | (POST entry) Notes form post |
| `/plan-add-item` | Add an item to a daily plan |
| `/plan-ai-suggest` | AI-suggest items for a daily plan |
| `/plan-import-analyze` | Plan-Importer step 1: AI analyze pasted text |
| `/plan-import-apply` | Plan-Importer step 3: apply approved placements |
| `/plan-import-consult` | Plan-Importer: consult AI about one placement |
| `/plan-import-group-consult` | Plan-Importer: consult AI about a placement group |
| `/plan-import-history` | (POST entry) Plan-Importer history form post |
| `/plan-import-history-delete` | Delete a Plan-Importer history entry |
| `/plan-import-save-session` | Save current Plan-Importer session draft |
| `/plan-import-undo-placement` | Undo a single applied placement |
| `/plan-item-update` | Update an item in a daily plan |
| `/plan-month-save` | Save monthly-plan edits |
| `/planner-add-task` | Add a task from the planner page |
| `/plan-quarter` | (POST entry) Plan-quarter form post |
| `/plan-toggle-item` | Toggle a daily-plan item complete |
| `/plan-tomorrow-generate` | AI-generate tomorrow's plan |
| `/plan-tomorrow-push` | Push tomorrow's plan into the schedule |
| `/plan-tomorrow-questions` | Generate clarifying questions for plan-tomorrow |
| `/plan-week-save` | Save weekly-plan edits |
| `/pod-dismiss-season` | Dismiss the POD seasonal-prompt card (Phase F) |
| `/pod-toggle-traveling` | Toggle "John traveling" flag on the POD |
| `/poetry-passage-save` | Save a poetry passage |
| `/prayer-intention-add` | Add a prayer intention |
| `/prayer-intention-complete` | Mark a prayer intention complete |
| `/prayer-intention-delete` | Delete a prayer intention |
| `/prayer-intention-log` | Log a prayer event against an intention |
| `/preview-discard` | Discard a generated preview |
| `/preview-keep` | Keep / promote a generated preview |
| `/programs-delete` | Delete a Coach program |
| `/programs-edit` | Edit a Coach program |
| `/programs-save` | Save a Coach program |
| `/quarter-checkin` | Submit a quarter check-in |
| `/quarter-journal-save` | Save a quarter-journal entry |
| `/quarter-save-goals` | Save quarter goals |
| `/quarter-save-step` | Save a quarter-step record |
| `/quest` | (POST entry) Family Quest bridge POST |
| `/recipe-delete` | Delete a recipe |
| `/recipe-import` | Import a recipe (URL or paste) |
| `/recipes` | (POST entry) Recipe form post |
| `/recipe-save` | Save a recipe |
| `/regenerate-school-week` | Regenerate the weekly school plan |
| `/reparse-school-preview` | Re-parse a school-week preview |
| `/roadmap-add` | Add a roadmap item |
| `/roadmap-delete` | Delete a roadmap item |
| `/roadmap-update` | Update a roadmap item |
| `/save-child-profile` | Save a child profile |
| `/save-chores` | Save chores |
| `/save-friend` | Save a friend record |
| `/save-john-profile` | Save John's profile |
| `/save-mom-profile` | Save Lauren's profile |
| `/save-pins` | Save / rotate auth PINs |
| `/save-school-preview-edits` | Save edits to a school-week preview |
| `/schedule/` | Per-person schedule POST handler |
| `/schedule-template-save` | Save a schedule template |
| `/school-settings-save` | Save school-related settings |
| `/school-upload` | Upload school-related document |
| `/settings-save` | Save settings (full reload) |
| `/settings-save-ajax` | Save settings (XHR, no reload) |
| `/settings-schedule-save` | Save schedule-related settings |
| `/signup-submit` | Submit beta waitlist signup |
| `/sister-mary` | (POST entry) Sister Mary form post |
| `/sister-mary-chat` | Send a chat message to Sister Mary |
| `/sister-mary-clear-history` | Wipe Sister Mary chat history |
| `/student-message-read` | Mark student-portal message as read |
| `/subject-doc-delete` | Delete a subject reference document |
| `/subject-doc-upload` | Upload a subject reference document |
| `/subject-grade-add` | Add a grade for a subject |
| `/subject-grade-delete` | Delete a grade |
| `/subject-link-add` | Add a reference link to a subject |
| `/subject-link-delete` | Delete a reference link |
| `/subject-send-to-mom` | Send subject info to Mom inbox |
| `/subject-upload-image` | Upload an image to a subject |
| `/subscribed-cal-add` | Add a subscribed iCal calendar |
| `/subscribed-cal-delete` | Delete a subscribed calendar |
| `/subscribed-cal-toggle` | Enable/disable a subscribed calendar |
| `/task-delete` | Soft-delete a task (mark inactive) |
| `/task-done` | Mark a task done |
| `/task-hard-delete` | Hard-delete a task |
| `/task-override` | Apply an override (skip/postpone/edit) to a task on a day |
| `/task-purge-inactive` | Purge inactive tasks |
| `/tasks` | (POST entry) Tasks form post |
| `/task-update` | Update task fields |
| `/thankyou-add` | Add a thank-you reminder |
| `/thankyou-dismiss` | Dismiss a thank-you reminder |
| `/thankyou-done` | Mark thank-you reminder done |
| `/thankyou-reminders` | (POST entry) Thank-you form post |
| `/thankyou-suggest` | AI-suggest thank-you reminders |
| `/timeblock-add-intention` | Add an intention from the POD time-block view |
| `/timeblock-add-novena` | Start a novena from the POD time-block view |
| `/today` | (POST entry) Today dashboard form post |
| `/toggle-task` | Toggle a task done/undone |
| `/v1/audio/speech` | OpenAI-compatible TTS endpoint (used by Lucy) |
| `/virtue-checkin` | Submit a virtue-tracker check-in |
| `/waitlist` | (POST entry) Waitlist form post |

---

## Section 3 — Data files (data/)

Sizes in bytes as of generation time. Files of size 2 are empty JSON `[]` or `{}`.

### Top-level data/*.json

| Path | Size | Stores |
|---|---:|---|
| data/app_settings.json | 2,485 | Global app settings (child colors, van epoch, API keys, timezone) |
| data/assignment_analyses.json | 12,381 | Assignment-Analyzer AI parse results |
| data/calendar_cache.json | 2,193 | Cached events from Google Calendar |
| data/calendar_config.json | 62 | iCal/Google-Calendar source configuration |
| data/calendar_rules.json | 64 | Calendar event-filter / recoloring rules |
| data/chores.json | 9,049 | Chore definitions per person, with buckets (daily/weekly/…) |
| data/coach_history.json | 47,217 | Coach chat history |
| data/coach_last_writes.json | 106 | Most-recent Coach data-altering action (for undo) |
| data/coach_programs.json | 3,516 | Coach's saved exercise programs |
| data/curriculum.json | 423,328 | Full curriculum store (subjects, units, assignments) |
| data/cycle_log.json | 236 | Cycle-tracking log entries |
| data/dev_history.json | 13,958 | Izzy (dev assistant) chat history |
| data/events.json | 30,710 | Local-calendar events |
| data/exercise_assignments.json | 2,214 | Per-week per-person exercise assignments |
| data/exercise_logs.json | 665 | Post-workout logs |
| data/family_memory.json | 2 | Family memory items (currently empty) |
| data/felix_undo.json | 137,831 | Lucy/companion undo journal |
| data/friends.json | 390 | Friends & families directory |
| data/frol_activities.json | 19,535 | FROL activities in v3 shape |
| data/frol_activities.v2_backup.json | 5,443 | One-shot backup of legacy v2 activities |
| data/frol_wizard_progress.json | 1,483 | FROL wizard saved progress (per-section answers) |
| data/frol_wizard_progress.v2_backup.json | 138 | Backup of legacy wizard progress |
| data/gradebook.json | 934 | Gradebook entries |
| data/grades.json | 99 | Per-child grade summary |
| data/gregory_history.json | 49,281 | Father Gregory chat history |
| data/gregory_last_writes.json | 272 | Most-recent Gregory data-altering action |
| data/hour_tracking.json | 138 | Hour-tracking logs |
| data/kid_messages.json | 2 | Kids' inter-family messages (empty) |
| data/liturgical.json | 2 | Custom liturgical-day overrides (empty) |
| data/lorenzo_history.json | 34,203 | Lorenzo chat history |
| data/lorenzo_last_writes.json | 101 | Most-recent Lorenzo data-altering action |
| data/lucy_history.json | 42,287 | Lucy chat history |
| data/manual_tasks.json | 25,474 | Manually-entered tasks |
| data/meal_inventory.json | 917 | Pantry / fridge inventory for meal planning |
| data/meal_rules.json | 3,316 | Meal-planning rules and constraints |
| data/memory_book.json | 789 | Family memory-book entries |
| data/mom_notes.json | 236 | Mom's quick notes |
| data/monica_history.json | 18,696 | Dr. Monica chat history |
| data/monthly_planner.json | 10,127 | Monthly-planner entries |
| data/notes.json | 3,999 | Notes |
| data/plan_import_history.json | 156,252 | Past Plan-Importer apply records (with undo data) |
| data/planning_session.json | 21 | Current Plan-Importer / planning session state |
| data/poetry_passages.json | 152 | Saved poetry passages |
| data/pope_intentions.json | 1,654 | Pope's monthly prayer intentions |
| data/prayer_intentions.json | 1,116 | Family prayer intentions |
| data/progress.json | 201,581 | Task-completion map keyed "YYYY-MM-DD::Person::task text" |
| data/recipes.json | 44,517 | Recipe library |
| data/roadmap.json | 1,121 | Project roadmap items |
| data/school_previews.json | 52,442 | Pending school-week AI previews |
| data/school_week_plan.json | 58,290 | Currently-approved weekly school plan |
| data/school_weeks.json | 99,033 | Historical approved school-week plans |
| data/seasonal_schedules.json | 2 | Phase F: saved seasonal schedule snapshots (currently empty) |
| data/sister_mary_history.json | 9,298 | Sister Mary chat history |
| data/subscribed_calendar_cache.json | 64 | Cached iCal events from subscribed feeds |
| data/subscribed_calendars.json | 2 | Subscribed iCal sources (empty) |
| data/task_overrides.json | 15,639 | Per-day task overrides (skip/postpone/edit) |
| data/task_registry.json | 195,883 | Stable task-id registry (FROL + manual) |
| data/thankyou_reminders.json | 259 | Thank-you-note reminders |
| data/_undo_smoke_test.json | 21 | Test fixture for undo system |

### Verification harnesses (data/*.py)

| Path | Size | Stores |
|---|---:|---|
| data/verify_phase_a.py | 13,400 | Phase A regression checks |
| data/verify_phase_b.py | 16,606 | Phase B regression checks |
| data/verify_phase_c.py | 7,287 | Phase C regression checks |
| data/verify_phase_d.py | 10,093 | Phase D regression checks |
| data/verify_phase_e.py | 11,295 | Phase E regression checks |
| data/verify_phase_f.py | 8,722 | Phase F (seasonal library) regression checks |
| data/verify_phase_g.py | 7,901 | Phase G (companion seasonal awareness) regression checks |
| data/verify_task_42.py | 6,034 | Task-42 follow-up regression checks |

### Subdirectories (one-line summaries)

| Path | Stores |
|---|---|
| data/5am/ | Per-date 5AM-Club entries (`YYYY-MM-DD.json`) |
| data/assignment_uploads/ | Uploaded assignment images / PDFs |
| data/auth/ | `pins.json` (per-user PINs) + `sessions.json` (active sessions) |
| data/cycle/ | Per-month cycle-tracking JSON (`YYYY-MM.json`) |
| data/daily_plans/ | Per-date daily plan blobs (`YYYY-MM-DD.json`) |
| data/day_grids/ | Per-date materialised schedule grids + `_meta.json` siblings |
| data/day_templates/ | Live FROL weekday templates (`Monday.json`…`Sunday.json`, `JohnTraveling.json`) — single source of truth |
| data/day_templates_preview/ | Wizard "Preview this week" temp templates (consumed when present) |
| data/day_templates_backups/ | Timestamped backups created before destructive writes to day_templates |
| data/hour_reports/ | Saved hour-tracking report snapshots |
| data/prayer/ | `intentions.json` (alternate prayer-intentions store) |
| data/profiles/ | Per-person profile JSON (`jp.json`, `joseph.json`, etc. — lowercase keys) |
| data/readings_cache/ | Cached daily Mass readings by date |
| data/saint_cache/ | Cached saint-of-the-day blobs by date |
| data/sister_mary_history.json.archive/ | Archived Sister Mary conversation rollovers |
| data/virtues/ | `personal.json` (virtue tracker data) |
| data/weekly_school_plan/ | Per-week approved school plan (`YYYY-WW.json`) |
| data/__pycache__/ | Python bytecode cache (auto-managed) |

---

## Section 4 — Render modules (render_*.py)

| Path | Renders |
|---|---|
| render_5am.py | 5AM Club page (personal discipline tracker) |
| render_ai_daily.py | AI-powered daily assistance fragments |
| render_ai_planner.py | AI scheduling-assistant page |
| render_assignment_analyzer.py | AI Assignment Analyzer page |
| render_calendar.py | Calendar fetching, event display, calendar page |
| render_child_goals.py | Per-child goals with substeps and deadlines |
| render_child_profile.py | Per-child profile card |
| render_chores.py | Chores page, laundry system, van rotation |
| render_coach.py | Coach (McAdams family fitness guide) page |
| render_companions.py | Standalone /companions directory of the six AI companions |
| render_curriculum.py | Curriculum management system |
| render_daily_bar.py | Daily info bar (weather, saint, gospel, events) |
| render_daily_plan.py | Daily plan editor, family grid, dashboard views |
| render_dev.py | Isidore (Izzy) help-desk diagnostic assistant |
| render_friends.py | Friends & Families directory |
| render_frol_pdf.py | FROL printable PDF generator |
| render_frol_wizard.py | Rule of Life Wizard (Phase 1) — the §1–§16 wizard |
| render_goals.py | Goal-system data helpers |
| render_gradebook.py | Per-child gradebook of recorded assignment scores |
| render_gregory.py | Father Gregory (Headmaster & Academic Director) |
| render_john.py | John's (husband/dad) personal profile page |
| render_kids_week.py | Kids' weekly planning page |
| render_liturgical.py | Liturgical-calendar engine and page renderers |
| render_liturgy_hours.py | Liturgy of the Hours page |
| render_login.py | Family login screen |
| render_lorenzo.py | Lorenzo (AI personal chef) |
| render_lucy.py | Lucy (AI day guide) |
| render_meals.py | Weekly meal planning system |
| render_memory_book.py | Family memory book |
| render_misc.py | Dashboard, Mom, Notes, Tasks, Roadmap, Planner, School, History |
| render_mom_profile.py | Mom's personal profile page |
| render_monica.py | Dr. Monica (Child Development & Pediatric Health) |
| render_morning_anchor.py | Morning Anchor (Step 0) and Evening Anchor (Step 5) |
| render_plan_importer.py | Plan-Import tool (paste→AI extract→approve→apply) |
| render_plan_month.py | Plan-My-Month |
| render_plan_quarter.py | Quarterly goal planning |
| render_plan_tomorrow.py | AI-powered tomorrow planning page |
| render_plan_week.py | Plan-My-Week |
| render_plan_year.py | Plan-My-Year |
| render_prayer.py | Prayer Intentions page |
| render_programs.py | Coach's saved programs + weekly exercise assignments |
| render_readings.py | Daily Mass readings page |
| render_schedule.py | Schedule cards, task lists, print pages, today/week views |
| render_schedule_support.py | Family schedule engine, now/next strip, timeline |
| render_school_pdf.py | School-week printable PDF generator |
| render_seasons.py | Phase F season detection helper (11 labels + upcoming_season) |
| render_settings.py | Settings page — single source of truth UI |
| render_signup.py | Beta waitlist signup survey |
| render_sister_mary.py | Sister Mary (contemplative Marian companion) |
| render_student.py | Student Portal (Phase 1) |
| render_subject.py | Per-subject curriculum review pages |
| render_timeblock.py | Lauren's time-block homepage (POD) |
| render_virtues.py | Virtue Tracker |
| render_week_school.py | Weekly school progress page (/week-school) |
| render_week_view.py | Family Week at a Glance |

Notable size: `render_frol_wizard.py` 372KB, `render_misc.py` 287KB, `render_lucy.py` 180KB, `render_schedule.py` 136KB — the four largest renderers.

---

## Section 5 — data_helpers.py functions

| Name | One-liner |
|---|---|
| list_snapshots | List restore-snapshot names |
| restore_snapshot | Restore a named snapshot |
| load_snapshot_data | Load raw snapshot contents |
| today_iso | Return today's date as ISO string |
| tomorrow_iso | Return tomorrow's date as ISO string |
| monday_iso_for | Return the ISO Monday of the week containing `iso` |
| load_school_week_plan | Return current weekly school plan blob ({} if empty) |
| save_school_week_plan | Persist the weekly school plan |
| generate_weekly_school_plan | Generate a draft weekly school plan for JP/Joseph |
| get_approved_school_week_plan | Return plan only when approved AND for given week |
| normalize_date_query | Normalize a ?date= query string |
| safe_int | Coerce to int with default fallback |
| clean_priority | Validate/clean a task-priority string |
| clean_status | Validate/clean a task-status string |
| clean_child | Validate/clean a child name |
| clean_text | Strip/escape user-entered text |
| clean_weekday | Validate/clean a weekday name |
| lines_to_list | Split textarea contents into list of lines |
| count_school_check_items | Count school checklist items in a string |
| is_math_subject | True if subject name is a math subject |
| is_math_test_text | True if assignment text reads as a math test |
| sort_school_days | Sort school-day strings into weekday order |
| load_progress | Load progress.json → maps task_id → {done: bool} |
| load_manual_tasks | Load manually-entered tasks |
| save_manual_tasks | Persist manual tasks |
| active_manual_tasks | Filter manual tasks to status='active' |
| ensure_manual_task_ids | Idempotent backfill of uuid4 ids on manual tasks |
| _nth_weekday_of_month | Return date of Nth weekday in given month/year |
| _add_months | Add N calendar months, clamping day |
| _next_specific_weekday | Next date strictly after `base` matching given weekdays |
| _next_monthly_day | Next occurrence on day `month_day` of the month |
| format_recurrence_label | Human-readable one-line recurrence summary |
| advance_recurring_task | Reset a completed recurring task to its next due date |
| _ensure_chore_buckets | Idempotent backfill of daily/weekly/monthly buckets per person |
| load_chores_data | Load chores.json |
| save_chores_data | Persist chores.json |
| _resolve_chore_person | Case-insensitive chore-bucket lookup for a person |
| get_chores_due_today | Chore entries due for `person` on the given date |
| get_due_grooming | Per-person grooming entries due |
| load_hour_tracking | Load hour-tracking logs |
| save_hour_tracking | Persist hour-tracking logs |
| add_hour_log | Append a single hour-log entry; return saved record |
| save_hour_report_snapshot | Persist an hour-report snapshot under HOUR_REPORTS_DIR |
| get_hour_totals | Return totals + categories for a person/subject |
| _activity_new_id | Stable-ish short id for a new FROL activity |
| _file_has_legacy_activities | True iff on-disk activities file has v2 entries |
| _ensure_activities_backup | Write one-shot backup of activities file (guard) |
| _upgrade_activity_v2_to_v3 | Convert one legacy activity dict to v3 shape (idempotent) |
| load_frol_activities | Return activities list in v3 shape (auto-upgrades v2) |
| save_frol_activities | Persist activities in v3 shape (auto-migrates legacy) |
| load_seasonal_schedules | Return all saved seasonal-schedule snapshots (Phase F) |
| _seasonal_snapshot_day_templates | Snapshot every day_templates JSON keyed by stem |
| save_seasonal_schedule | Persist current activities + day_templates under a season label |
| get_seasonal_schedule | Return one seasonal entry by id (or None) |
| find_seasonal_schedule_for | Most recent saved entry for (label, year) |
| _summarize_prior_seasonal_entry | One-line summary of a prior seasonal entry's notes |
| delete_seasonal_schedule | Remove a seasonal entry by id |
| get_seasonal_context | Season-aware dict the companions consume |
| get_companion_seasonal_block | Role-specific seasonal context block (list of lines) |
| load_roadmap | Load roadmap items |
| save_roadmap | Persist roadmap |
| load_mom_notes | Load Lauren's quick notes |
| save_mom_notes | Persist Lauren's quick notes |
| load_liturgical_custom | Load liturgical-day customisations |
| save_liturgical_custom | Persist liturgical customisations |
| load_calendar_config | Load calendar source config |
| save_calendar_config | Persist calendar config |
| load_calendar_cache | Load cached calendar events |
| save_calendar_cache | Persist calendar cache |
| load_subscribed_calendar_cache | Load cached iCal-subscribed events |
| save_subscribed_calendar_cache | Persist subscribed-calendar cache |
| load_calendar_rules | Load calendar filter / recolor rules |
| save_calendar_rules | Persist calendar rules |
| load_subscribed_calendars | Load subscribed iCal sources |
| save_subscribed_calendars | Persist subscribed calendars |
| load_family_schedule | Load family Rule-of-Life schedule (legacy) |
| save_family_schedule | Persist family schedule |
| get_frol_day_slots | Return FROL time slots {time:label} for person/weekday |
| load_day_template | Load a single day-template JSON from `base_dir` |
| get_frol_times | Canonical ordered half-hour FROL slots |
| load_exercise_assignments | Load per-week exercise assignments |
| save_exercise_assignments | Persist exercise assignments |
| load_coach_programs | Load Coach programs |
| save_coach_program | Append a Coach program; return saved entry with id |
| load_exercise_logs | Load post-workout logs |
| save_exercise_log | Save (or replace) post-workout log for (person, iso) |
| delete_coach_program | Delete a Coach program by id |
| get_family_rule_of_life_text | Plain-text FROL for given weekday |
| get_full_frol_context | Complete formatted FROL view for all 7 days |
| _archive_history_file | Copy a history file into <path>.archive/<ts>.json |
| load_lucy_history | Return list of Lucy {role, content, ts} dicts |
| save_lucy_history | Persist full Lucy history (capped) |
| append_lucy_messages | Append one or more Lucy messages and save |
| _safe_clear | Archive then wipe a history file (fail-closed) |
| clear_lucy_history | Archive + wipe Lucy history (False on failure) |
| load_lorenzo_history | Lorenzo chat history list |
| save_lorenzo_history | Persist Lorenzo history |
| append_lorenzo_messages | Append + save Lorenzo messages |
| clear_lorenzo_history | Archive + wipe Lorenzo history |
| load_gregory_history | Gregory chat history list |
| save_gregory_history | Persist Gregory history |
| append_gregory_messages | Append + save Gregory messages |
| clear_gregory_history | Archive + wipe Gregory history |
| load_coach_history | Coach chat history |
| save_coach_history | Persist Coach history |
| append_coach_messages | Append + save Coach messages |
| clear_coach_history | Archive + wipe Coach history |
| load_dev_history | Izzy chat history |
| save_dev_history | Persist Izzy history |
| append_dev_messages | Append + save Izzy messages |
| clear_dev_history | Archive + wipe Izzy history |
| load_monica_history | Dr. Monica chat history |
| save_monica_history | Persist Dr. Monica history |
| append_monica_messages | Append + save Dr. Monica messages |
| clear_monica_history | Archive + wipe Dr. Monica history |
| load_thankyou_reminders | Load thank-you-note reminders |
| save_thankyou_reminders | Persist thank-you reminders |
| pending_thankyou_reminders | Pending reminders sorted by date |
| due_thankyou_reminders | Pending reminders due today or earlier |
| due_thankyou_reminders_for | Due reminders for a specific person or 'Family' |
| load_assignment_analyses | List of analyzed assignments (newest first) |
| save_assignment_analyses | Persist analyses |
| add_assignment_analysis | Insert new analysis; return saved record |
| update_assignment_analysis | Update an analysis by id |
| delete_assignment_analysis | Delete an analysis by id |
| percent_to_letter | Convert numeric % to letter grade |
| letter_to_gpa | Convert letter grade to GPA points |
| school_year_for_date | McAdams homeschool year (Aug 1–Jul 31) for ISO date |
| load_gradebook | Load gradebook entries list |
| save_gradebook | Persist gradebook |
| add_gradebook_entry | Insert new gradebook entry with id |
| update_gradebook_entry | Update a gradebook entry |
| delete_gradebook_entry | Delete a gradebook entry |
| gradebook_for_child | Entries for a child (optional year filter), newest first |
| as_text | Normalize ingredients/instructions to single string |
| load_recipes | Load recipe library |
| save_recipes | Persist recipes |
| get_recipe_by_id | Return recipe dict by id (or None) |
| save_recipe | Append a new recipe (always new id, no replace) |
| add_recipe | Add or update recipe by case-insensitive name match |
| delete_recipe | Delete recipe by id |
| search_recipes | Find recipes by name/ingredient substring |
| load_planning_session | Load current planning-session state |
| save_planning_session | Persist planning-session state |
| start_planning_session | Initialise a new planning session |
| advance_planning_session | Advance to the next slot after the one just filled |
| clear_planning_session | Wipe planning-session state |
| planning_session_summary | Client-facing summary dict |
| load_monthly_planner | Load monthly planner |
| load_curriculum | Load curriculum store |
| save_curriculum | Persist curriculum |
| get_curriculum_week | Current school-week number (1-indexed) |
| get_curriculum_subjects | {subject: {week_str: assignment}} for a child |
| week_day_segments | Per-day breakdown for a week's stored value |
| resolve_week_text | Assignment text for (week, day) in subject |
| get_curriculum_week_assignments | {subject: assignment_text} for child on a week |
| subject_meeting_days | Weekday names this subject meets on |
| subject_day_index | 1-based position of today within meeting_days |
| advance_curriculum_cursor | Advance a subject's _current_day cursor |
| load_local_events | Raw events from data/events.json |
| save_local_events | Persist events |
| expand_local_events_for_range | Expand events into calendar-shape dicts for a date range |
| load_task_overrides | {child:{iso:{task_id:override}}} map |
| save_task_overrides | Persist task overrides |
| set_task_override | Store an override for a task on a day |
| clear_task_override | Remove an override |
| get_day_overrides | {task_id:override} for a (person, iso) |
| get_postponed_for_day | Task labels postponed TO this day from earlier |
| load_curriculum_library | Load subjects/units/assignments library |
| save_curriculum_library | Persist curriculum library |
| get_subject_by_id | Return a subject by id |
| get_assignments_for_student | All assignments for a student across subjects |
| load_student_submissions | Load student-work submissions |
| save_student_submissions | Persist submissions |
| add_student_submission | Add a new submission |
| get_submissions_for_grading | Submissions pending review |
| get_submissions_by_student | All submissions for a student |
| load_grading_history | Load completed grading records |
| save_grading_history | Persist grading history |
| add_grade_record | Add a completed grade + update submission status |
| load_curriculum_documents | Load curriculum reference docs |
| save_curriculum_documents | Persist curriculum documents |
| add_curriculum_document | Add a curriculum reference document |
| load_family_memory | Family memory list (empty if missing) |
| save_family_memory | Persist family memory list |
| _now_ts | Current ISO timestamp helper |
| add_memory | Append a new memory; return saved record |
| update_memory | Replace text of an existing memory |
| delete_memory | Remove a memory by id |
| _tokenize_memory | Lowercase alphanumeric tokens (≥2 chars, stopwords removed) |
| find_memory_conflicts | Memories whose Jaccard token overlap exceeds threshold |
| get_memory_context_block | FAMILY MEMORY system-prompt section |
| load_prayer_intentions | Load prayer intentions |
| save_prayer_intentions | Persist prayer intentions |
| add_daily_intention | Add a one-time daily intention |
| add_repeating_intention | Add a repeating intention |
| add_novena | Start a 9-day novena |
| get_active_intentions_for_date | Intentions active on a given date |
| check_upcoming_novenas | Feasts in next 9 days without an active novena |
| load_pope_intentions | Pope's monthly intentions cache |
| save_pope_intentions | Persist Pope's intentions |
| get_pope_intention_for_month | Pope intention for a given (year, month) |
| load_sister_mary_history | Sister Mary chat history |
| save_sister_mary_history | Persist Sister Mary history |
| append_sister_mary_messages | Append + save Sister Mary messages |
| clear_sister_mary_history | Archive + wipe Sister Mary history |

---

## Section 6 — config.py constants

| Name | Value |
|---|---|
| HOST | `"0.0.0.0"` |
| PORT | `int(os.environ.get("PORT", 8000))` |
| MANUAL_TASKS_FILE | `"data/manual_tasks.json"` |
| CHORES_FILE | `"data/chores.json"` |
| MOM_NOTES_FILE | `"data/mom_notes.json"` |
| ROADMAP_FILE | `"data/roadmap.json"` |
| LITURGICAL_FILE | `"data/liturgical.json"` |
| FAMILY_SCHEDULE_FILE | `"data/family_schedule.json"` |
| CALENDAR_CONFIG_FILE | `"data/calendar_config.json"` |
| CALENDAR_CACHE_FILE | `"data/calendar_cache.json"` |
| MONTHLY_PLANNER_FILE | `"data/monthly_planner.json"` |
| CALENDAR_RULES_FILE | `"data/calendar_rules.json"` |
| SUBSCRIBED_CALS_FILE | `"data/subscribed_calendars.json"` |
| SUBSCRIBED_CACHE_FILE | `"data/subscribed_calendar_cache.json"` |
| APP_SETTINGS_FILE | `"data/app_settings.json"` |
| CURRICULUM_FILE | `"data/curriculum.json"` |
| TASK_OVERRIDES_FILE | `"data/task_overrides.json"` |
| COACH_PROGRAMS_FILE | `"data/coach_programs.json"` |
| EXERCISE_LOGS_FILE | `"data/exercise_logs.json"` |
| SCHOOL_WEEK_PLAN_FILE | `"data/school_week_plan.json"` |
| FAMILY_MEMORY_FILE | `"data/family_memory.json"` |
| PRAYER_INTENTIONS_FILE | `"data/prayer_intentions.json"` |
| SISTER_MARY_HISTORY_FILE | `"data/sister_mary_history.json"` |
| POPE_INTENTIONS_FILE | `"data/pope_intentions.json"` |
| FROL_WIZARD_PROGRESS_FILE | `"data/frol_wizard_progress.json"` |
| HOUR_TRACKING_FILE | `"data/hour_tracking.json"` |
| HOUR_REPORTS_DIR | `"data/hour_reports"` |
| FROL_ACTIVITIES_FILE | `"data/frol_activities.json"` |
| DAY_TEMPLATES_DIR | `"data/day_templates"` |
| DAY_TEMPLATES_PREVIEW_DIR | `"data/day_templates_preview"` |
| DAY_TEMPLATES_BACKUP_DIR | `"data/day_templates_backups"` |
| SEASONAL_SCHEDULES_FILE | `"data/seasonal_schedules.json"` |
| VALID_PRIORITIES | `{"HIGH", "MEDIUM", "LOW"}` |
| VALID_STATUSES | `{"active", "done", "inactive"}` |
| WEEKDAYS | `["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]` |
| WEEKDAY_ORDER | `{day: i for i,day in enumerate(WEEKDAYS)}` |
| SCHEDULE_DAYS | `["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]` |
| MONTH_NAMES | `["January","February",…,"December"]` (12 items) |
| ROADMAP_STATUSES | `["Someday","Ready","In Progress","Done"]` |
| ASSIGNABLE_TO | `["Mom"] + list(CHILDREN)` |
| _DEFAULT_CHILD_COLORS | `{JP:{bg:#c0392b,text:#fff,light:#fdf0ef}, Joseph:{bg:#27ae60,…}, Michael:{bg:#e67e22,…}, James:{bg:#2980b9,…}}` |
| CHILD_COLORS | `_load_child_colors()` (merged from app_settings.json) |
| _DEFAULT_PARENT_COLORS | `{Lauren:{bg:#7c3aed,light:#f5f3ff}, John:{bg:#2563eb,light:#eff6ff}}` |
| VAN_ROTATION_EPOCH | `_load_van_epoch()` (default `date(2025,1,6)`) |
| VAN_ROLE_A | `"Interior Reset Lead"` |
| VAN_ROLE_B | `"Bin & Organization Lead"` |

Module-level helper functions in config.py (not strictly constants but exposed at module scope): `_load_child_colors`, `child_color`, `parent_color`, `_load_van_epoch`, `get_van_epoch`, `get_app_setting`, `get_family_name`, `get_timezone`, `get_schedule_hours`.

---

## Section 7 — Current claud.md rules (full text)

### Python 3.11 hard rules — never violate these

1. No backslashes inside f-strings
2. No nested quotes inside f-strings — use a variable outside the f-string instead
3. All POST routing uses elif chains — never if/elif with a missing first if, never nested if blocks for routing
4. Never put import statements inside if blocks or functions
5. All file writes use safe_save_json (tmp file + os.replace) — never open(f, 'w') directly
6. No walrus operator (`:=`)
7. Never use `'\n'` inside a JS string within a Python string literal — use `'\\n'` so the browser receives the escape sequence, not a raw newline
8. **multipart/form-data parsing** — when fetch POSTs use FormData the server receives multipart/form-data not urlencoded. The do_POST handler must sniff Content-Type and parse accordingly using cgi.FieldStorage for multipart. If a POST handler receives empty data check the Content-Type first.
9. **py_compile passes but runtime fails** — py_compile only validates syntax not runtime correctness. Always run an in-process smoke test after py_compile to catch NameError, missing variable definitions, and import failures.
10. **test fixtures must never write to live data** — verification harnesses must always operate on a temp copy of live data files. Never call save_progress, safe_save_json, or any write helper on live data during testing. Always restore from backup after any test that touches data files.
11. **double-escaping HTML entities** — never pass a string that is already HTML-escaped through escape() again. If a string contains literal ampersands for display use plain ampersands in the source string and let escape() handle it once. Strings pre-escaped with `&amp;` will render as visible `&amp;` in the browser if escaped again.
12. **JS newline in Python f-strings applies everywhere** — rule 7 applies to ALL files containing JS embedded in Python, not just render_frol_wizard.py. This includes render_schedule.py, render_timeblock.py, render_lucy.py, render_lorenzo.py, and any other render file with inline JavaScript.

### Additional rules (13–18)

13. **FROL WIZARD NESTED FORM ADDENDUM** — The _body_has_form check in _section_chrome looks for `action="/frol-wizard"` in the body string. Any form inside a section body posting to /frol-wizard will suppress the Save and Continue button. Variant tab forms posting to /frol-set-variant are safe. Activity builder forms posting to /frol-add-activity are safe. Before adding any form to a section body confirm its action attribute. This is a recurring bug — document before fixing if it appears again.

14. **PRE-FLIGHT CHECKLIST** — Before writing any spec answer these questions. One — how many files does this touch, list them, if unknown that is a diagnosis step first. Two — does it involve JavaScript inside Python f-strings, if yes flag the backslash-n rule explicitly in the spec. Three — does it touch form handling, if yes confirm no nested forms posting to /frol-wizard. Four — is the root cause confirmed or assumed, if assumed run diagnosis first never draft a fix on an assumed cause. Five — does it touch multiple files at once, if yes break into separate single-purpose instructions. Six — does it involve data shape changes or migration, if yes confirm before and after data structure explicitly before writing the spec.

15. **CLAUD.MD READ-BACK REQUIRED** — At the start of every session read claud.md and paste back every rule found. Then identify which rules apply to today's task. If you cannot paste the rules back accurately stop and ask Lauren to re-paste claud.md before proceeding.

16. **MAGNIFICA HUMANITAS DESIGN PRINCIPLES** — Every feature built must reflect these principles. One — the app is a tool not an authority. Every AI suggestion is framed as a suggestion never a prescription. Language uses "here is one way to think about this" never "you should" or "the optimal schedule is." Two — companions serve real relationships they do not replace them. Every companion orients toward real people, real community, and real pastoral support. Sister Mary never replaces a confessor. Father Gregory never replaces real mentors. Lucy regularly suggests real conversations over app conversations. Three — AI supports thinking it does not replace it. Ask before suggesting. Boys build their own plans before seeing AI suggestions. Father Gregory asks questions more than he gives answers. Four — be transparent about what AI is. Companions never make theological claims with personal authority. Prayer texts come from verified Catholic sources only never AI generated. Five — language of grace not performance. No gamification no streaks no scores that shame. A hard day is never framed as failure. Sick Day Mode is relief not defeat. Six — subsidiarity. The family governs itself. Lauren is always the authority. The app serves the family's discernment it does not replace it. Seven — formation in digital wisdom. Father Gregory teaches the boys to think critically about AI. The explicit goal is that JP finishes high school able to plan his day without the app.

17. **ONE FIX PER INSTRUCTION** — Never bundle multiple fixes into one Agent instruction unless they are in the same file and directly related. Complex multi-file builds must be broken into sequential single-purpose phases with a compile check and report between each phase.

18. **AUGUST 15TH BUILD PLAN IS THE PRIORITY FILTER** — Between June 1st and August 15th 2026 every build request must be checked against the August 15th build plan before proceeding. If a requested build is not on the must-have or should-have list for the current week flag it to Lauren before starting. New feature ideas go on the post-September list unless they directly enable one of the 14 goals in the August 15th plan. Scope is the first thing to cut not quality.

### Additional sections of claud.md (not numbered as rules but binding context)

- **What this app is** — Catholic homeschool family management web app, Python on Replit, single-file HTTP server pattern (app.py + render_*.py), no framework.
- **Stack** — Python 3.11; no Flask/Django/FastAPI; JSON files only; plain HTML/CSS/JS rendered as strings; Anthropic via urllib (no SDK).
- **People** — Lauren (Mom), John (Dad), JP (14, 9th), Joseph (12, 7th), Michael (5, K), James (13 months, excluded from school/gradebook). Title-case names; Lauren/Mom same person; lowercase keys in auth/pins.json and profiles/.
- **Data file patterns** — Most data in data/*.json; person keys title-case in progress/chores/events, lowercase in auth/profiles; progress keys `YYYY-MM-DD::Person::task text`; date keys YYYY-MM-DD (most), YYYY-Www (meal_plan), YYYY-MM (cycle).
- **Route patterns** — GET routes call render_*.py functions; POST routes chained as `elif path == "/route":` in do_POST; JSON POST bodies must be in `_JSON_PATHS` set or the form-parser eats them.
- **Anchor-tag navigation** — Plain `<a href>` can't POST; state must travel in query string OR be persisted before click; destination handler must accept those params AND persist them on arrival. Counter-pattern that bit us: FROL wizard landing anchors `/frol-wizard?step=1&mode=structured`. If a button must trigger persistent state, use `<form method="POST">` styled as a link.
- **AI calls** — Model `claude-sonnet-4-20250514`, urllib.request (no SDK), API key from app_settings.json, all responses through `_repair_and_parse_json()`.
- **Change discipline** — Additive unless told otherwise; don't modify existing behavior beyond task scope; if a task requires editing out-of-scope files, stop and flag; modules under 800 lines where possible; `render_plan_importer.py` is 1,114 lines (JS lives in `static/js/plan_importer_core.js` / `plan_importer_consult.js`).
- **FROL Wizard form bypass trap** — `_section_chrome` suppresses "Save and Continue" when `_body_has_form` detects a form with `action="/frol-wizard"`. Utility forms posting to other routes (`/frol-set-variant`, `/frol-add-activity`, `/frol-delete-activity`) are safe. When adding new forms to section bodies, check the action — if it's `/frol-wizard`, use a different route or handle the advance separately.
- **Current major features** — `/plan-import` paste→AI→approve→apply with receipt and per-placement undo; six AI companions (Lucy, Lorenzo, Gregory, Monica, Coach, Izzy); liturgical calendar engine with auto-computed Easter and moveable feasts; per-person daily schedule grids; gradebook with assignment analyzer; meal planner with Lorenzo.
