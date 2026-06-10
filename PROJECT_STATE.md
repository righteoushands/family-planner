# PROJECT_STATE.md — Sancta Familia
Technical snapshot of the current codebase. Read at the start of future
sessions for a fast orientation. Generated 2026-06-06.

> Counts as of this snapshot: 96 exact-match GET routes + 15 prefix
> (`startswith`) GET routes in `do_GET`; ~200 POST routes in `do_POST`;
> 57 render modules; 216 functions in `data_helpers.py`.

---

## Section 1 — GET routes (defined in app.py do_GET)

### 1a. Exact-match routes (`path == "…"`)

| Path | Renders / returns |
|---|---|
| `/` | Family dashboard (when authenticated) / login screen (when not) |
| `/login` | Family login screen (PIN entry) |
| `/logout` | Clears session, redirects to login |
| `/quest-sso` | Single sign-on handoff into Family Quest |
| `/change-pin` | Change-PIN form |
| `/today` | Personalized per-child task dashboard for today |
| `/programs` | Coach's saved programs + weekly exercise assignments |
| `/set-school-mode` | Toggles school-mode setting, redirects |
| `/now` | Now/Next strip — current and upcoming schedule item |
| `/week` | Family week-at-a-glance view |
| `/week-school` | Weekly school progress page |
| `/school` | School overview page |
| `/api/today-progress` | JSON: completion ratios per person for today |
| `/api/boys-tasks` | JSON: today's task list for JP/Joseph/Michael |
| `/api/child-tasks` | JSON: today's task list for a single child (?child=…) |
| `/gdrive-files` | Google Drive file browser/import UI |
| `/kids-week` | Kids' week planning page |
| `/plan-tomorrow` | AI-powered tomorrow planning page |
| `/plan-today` | Daily plan editor |
| `/plan-week` | Plan My Week |
| `/plan-month` | Plan My Month |
| `/plan-year` | Plan My Year |
| `/plan-quarter` | Quarterly goal planning |
| `/virtues` | Virtue tracker |
| `/5am` | 5AM Club personal-discipline tracker |
| `/liturgy-hours` | Liturgy of the Hours page |
| `/prayer-intentions` | Prayer intentions list |
| `/virtues/me` | Personal virtue view |
| `/virtues/family` | Family virtue view |
| `/school/edit` | School settings editor |
| `/chores` | Chores, laundry system, van rotation |
| `/van-roles` | Van rotation roles page |
| `/print/day` | Printable day schedule |
| `/print/week` | Printable week schedule |
| `/notes` | Notes page |
| `/tasks` | Tasks page |
| `/thankyou-reminders` | Thank-you reminders page |
| `/mom` | Mom dashboard page |
| `/mom-profile` | Mom's personal profile page |
| `/john` | John's (dad) personal profile page |
| `/friends` | Friends & families directory |
| `/roadmap` | Family roadmap page |
| `/signup` | Beta waitlist signup survey |
| `/waitlist` | Waitlist page |
| `/family-schedule` | Family schedule engine view |
| `/frol-pdf` | FROL printable PDF |
| `/school-week-pdf` | School week printable PDF |
| `/calendar` | Calendar page |
| `/planner` | Planner page |
| `/readings` | Daily Mass readings |
| `/lucy` | Lucy AI companion (day guide) |
| `/lorenzo-plan-state` | JSON: Lorenzo meal-plan session state |
| `/lorenzo` | Lorenzo AI companion (personal chef) |
| `/headmaster` | Father Gregory AI companion (academic headmaster) |
| `/coach` | Coach AI companion (family fitness) |
| `/dr-monica` | Dr. Monica AI companion (child development/health) |
| `/companions` | AI companions hub |
| `/wizards` | Wizards hub page |
| `/pantry-staples` | **NEW** — Pantry Staples setup/management page |
| `/sister-mary` | Sister Mary contemplative Marian companion |
| `/frol-grid-fragment` | HTML fragment: FROL day grid |
| `/frol-seasonal-view` | FROL seasonal schedule view |
| `/frol-wizard` | Rule of Life Wizard |
| `/daily-mass` | Daily Mass readings/video page |
| `/plan-import-history` | Plan import history list |
| `/grades` | Grades overview |
| `/subject` | Per-subject curriculum review |
| `/hour-report` | Homeschool hour report |
| `/curriculum` | Curriculum management system |
| `/gradebook` | Per-child gradebook |
| `/assignment-analyzer` | Assignment Analyzer upload/parse UI |
| `/assignment-image` | Serves uploaded assignment images |
| `/plan-import` | Plan Import tool |
| `/dev` | Izzy dev help-desk assistant |
| `/dev-logs` | Dev: log viewer |
| `/dev-health` | Dev: health check |
| `/dev-diag` | Dev: diagnostics |
| `/dev-read-file` | Dev: read a file |
| `/dev-grep-files` | Dev: grep across files |
| `/dev-git-log` | Dev: git log |
| `/dev-git-diff` | Dev: git diff |
| `/memory-book` | Family memory book |
| `/liturgical` | Liturgical calendar page |
| `/prayer` | Prayer page |
| `/liturgical/edit` | Liturgical calendar editor |
| `/settings` | Settings page (General · Children · Systems · Integrations) |
| `/history` | History page |
| `/history/preview` | History preview |
| `/plan-fragment` | HTML fragment: daily plan |
| `/grid-print` | Printable schedule grid |
| `/mom-step` | Mom morning/evening anchor step |
| `/meals` | Weekly meal planner |
| `/meal-print` | Printable meal card |
| `/recipes` | Recipe library |
| `/api-key` | Anthropic API key settings page |
| `/calendar/refresh` | Forces calendar cache refresh, redirects |

### 1b. Prefix routes (`path.startswith("…")`)

| Prefix | Serves / renders |
|---|---|
| `/quest` | Family Quest sub-application (delegated) |
| `/static/js/*.js` | Static JavaScript assets |
| `/static/images/` | Static image assets |
| `/static/` | Other static assets |
| `/prayer-photo/` | Serves prayer intention photos |
| `/prayer-intention/share/` | Shared prayer intention view |
| `/virtues/child/` | Per-child virtue view |
| `/print/day/` | Printable day schedule for a person/date |
| `/uploads/recipes/` | Serves uploaded recipe/dish photos |
| `/uploads/grades/`, `/uploads/grade_docs/` | Serves uploaded grade documents |
| `/schedule/` | Per-person/date schedule card |
| `/student/` | Student portal |
| `/grades/` | Per-child grade detail |
| `/lucy-child-brief/` | Lucy child brief fragment |
| `/lucy-prayer-brief/` | Lucy prayer brief fragment |

---

## Section 2 — POST routes (defined in app.py do_POST)

> **Routing convention (claud.md Rule 3):** top-level `do_POST` routing uses
> standalone `if path == "…": … return` blocks (not an elif chain). Some
> handlers are nested inside grouped sections (school, subject, gradebook,
> recipes, etc.). `_JSON_PATHS = {"/plan-import-apply",
> "/plan-import-undo-placement", "/curriculum-save", "/curriculum-minutes",
> "/poetry-passage-save"}` — these receive JSON bodies.

### Auth & messaging
| Path | Effect |
|---|---|
| `/login` | Authenticates a PIN, sets session |
| `/change-pin` | Updates a user's PIN |
| `/save-pins` | Admin: saves PINs (JSON) |
| `/messages-read` | Marks admin messages read |
| `/student-message-read` | Marks a student message read |
| `/message-mom` | Sends a message to Mom |
| `/mom-add-note` | Adds a Mom note |

### Pantry / meals / recipes
| Path | Effect |
|---|---|
| `/pantry-staples-save` | **NEW** — saves pantry staples + running-low flags |
| `/meal-rule-add` | Adds a meal rule |
| `/meal-rule-delete` | Deletes a meal rule |
| `/meal-save-constraints` | Saves meal constraints |
| `/meal-save-inventory` | Saves meal inventory |
| `/meal-save-plan` | Saves the weekly meal plan |
| `/meal-edit` | Edits a planned meal |
| `/meal-generate` | AI-generates a meal plan |
| `/recipe-save` | Creates/edits a recipe (multipart, photo upload) |
| `/recipe-import` | Imports a recipe (URL/text/photo/PDF) |
| `/recipe-delete` | Deletes a recipe |

### Lorenzo (chef companion)
| Path | Effect |
|---|---|
| `/lorenzo-chat` | Lorenzo chat turn |
| `/lorenzo-clear-history` | Clears Lorenzo history |
| `/lorenzo-plan-start` | Starts a Lorenzo planning session |
| `/lorenzo-plan-end` | Ends a Lorenzo planning session |
| `/lorenzo-rule-save` | Saves a Lorenzo meal rule |

### Other AI companions
| Path | Effect |
|---|---|
| `/lucy-chat`, `/lucy-clear-history`, `/lucy-rule-save`, `/lucy-tts` | Lucy chat / clear / rule / text-to-speech |
| `/headmaster-chat`, `/headmaster-clear-history` | Father Gregory chat / clear |
| `/coach-chat`, `/coach-clear-history` | Coach chat / clear |
| `/dr-monica-chat`, `/dr-monica-clear-history` | Dr. Monica chat / clear |
| `/sister-mary-chat`, `/sister-mary-clear-history` | Sister Mary chat / clear |
| `/dev-chat`, `/dev-clear`, `/dev-apply`, `/dev-write`, `/dev-undo`, `/dev-restart` | Izzy dev assistant chat / clear / apply / write / undo / restart |

### AI generation endpoints
| Path | Effect |
|---|---|
| `/ai-daily-schedule`, `/ai-capacity-preview`, `/ai-chore-adjust` | AI daily schedule / capacity / chore adjustment |
| `/ai-meal-plan`, `/ai-school-plan`, `/ai-suggest-goals` | AI meal / school / goal suggestions |
| `/ai-week-brief`, `/ai-month-brief`, `/ai-year-brief` | AI period briefs |
| `/ai-weekly-review`, `/ai-evening-examen`, `/ai-intention-prayer` | AI review / examen / intention prayer |
| `/ai-generate-steps`, `/api/extract-suggestions` | AI step generation / suggestion extraction |

### Tasks & notes
| Path | Effect |
|---|---|
| `/add-task`, `/task-update`, `/task-done`, `/task-delete`, `/task-hard-delete`, `/task-override`, `/task-purge-inactive`, `/toggle-task` | Task CRUD, overrides, completion, purge |
| `/add-note`, `/archive-note`, `/convert-note` | Note CRUD |
| `/planner-add-task`, `/add-to-plan-quick` | Quick task/plan additions |

### Daily plan
| Path | Effect |
|---|---|
| `/plan-add-item`, `/plan-item-update`, `/plan-toggle-item`, `/plan-ai-suggest` | Daily plan item CRUD + AI suggest |
| `/anchor-save` | Saves morning/evening anchor |

### Plan / period planning
| Path | Effect |
|---|---|
| `/plan-week-save`, `/plan-month-save` | Save week/month plans |
| `/plan-tomorrow-generate`, `/plan-tomorrow-push`, `/plan-tomorrow-questions` | Tomorrow planning flow |
| `/quarter-checkin`, `/quarter-journal-save`, `/quarter-save-goals`, `/quarter-save-step` | Quarter planning |
| `/kids-week-save` | Saves kids' week plan |

### Plan importer
| Path | Effect |
|---|---|
| `/plan-import-analyze`, `/plan-import-consult`, `/plan-import-group-consult` | Analyze / consult on imported plans |
| `/plan-import-apply` (JSON) | Applies parsed events/tasks/placements |
| `/plan-import-undo-placement` (JSON) | Undoes a placement |
| `/plan-import-save-session`, `/plan-import-history-delete` | Session save / history delete |

### School / curriculum / gradebook
| Path | Effect |
|---|---|
| `/school-upload`, `/school-settings-save` | School file upload / settings |
| `/approve-school-preview`, `/approve-school-week`, `/regenerate-school-week`, `/reparse-school-preview`, `/save-school-preview-edits`, `/preview-keep`, `/preview-discard` | School week preview/approval workflow |
| `/curriculum-save` (JSON), `/curriculum-minutes` (JSON), `/curriculum-parse`, `/curriculum-delete`, `/curriculum-week`, `/curriculum-subject-day`, `/curriculum-subject-week` | Curriculum CRUD & scheduling |
| `/assignment-analyze`, `/assignment-update`, `/assignment-delete`, `/assignment-reply` | Assignment analyzer CRUD |
| `/gradebook-add`, `/gradebook-update`, `/gradebook-delete` | Gradebook CRUD |
| `/subject-grade-add`, `/subject-grade-delete`, `/subject-link-add`, `/subject-link-delete`, `/subject-doc-delete`, `/subject-doc-upload`, `/subject-upload-image`, `/subject-send-to-mom` | Subject page CRUD |
| `/hour-log-add`, `/hour-log-edit`, `/hour-log-delete` | Homeschool hour tracking |
| `/poetry-passage-save` (JSON) | Saves a poetry passage |

### FROL (Rule of Life) wizard & grid
| Path | Effect |
|---|---|
| `/frol-wizard`, `/frol-wizard-chat`, `/frol-wizard-finalize` | Wizard step save / chat / finalize |
| `/frol-add-activity`, `/frol-set-variant`, `/frol-edit-activity`, `/frol-delete-activity` | Activity add/variant/edit/delete |
| `/frol-save-seasonal`, `/frol-seasonal-use`, `/frol-seasonal-delete` | Seasonal schedule CRUD |
| `/frol-overlay-set`, `/frol-overlay-clear`, `/frol-overlay-toggle` | Schedule overlays |
| `/frol-rollback-v3` | Rolls back FROL data version |
| `/grid-cell-save`, `/grid-publish`, `/grid-push-weekly`, `/grid-reset`, `/grid-save-template`, `/schedule-template-save` | Day-grid editing & publishing |
| `/pod-dismiss-season`, `/pod-toggle-traveling` | Plan-of-day controls |

### Chores / van / programs / fitness
| Path | Effect |
|---|---|
| `/save-chores`, `/apply-laundry`, `/apply-van-rotation` | Chores save, laundry, van rotation |
| `/programs-save`, `/programs-edit`, `/programs-delete` | Coach program CRUD |
| `/exercise-log` | Logs an exercise |
| `/5am-save` | Saves 5AM Club tracker entry |

### Goals / virtues / roadmap
| Path | Effect |
|---|---|
| `/goal-add`, `/child-goal-add`, `/child-goal-archive`, `/child-substep-add`, `/child-substep-toggle`, `/child-substep-delete` | Goal & substep CRUD |
| `/virtue-checkin` | Records a virtue check-in |
| `/roadmap-add`, `/roadmap-update`, `/roadmap-delete` | Roadmap CRUD |

### Prayer / liturgical / memory
| Path | Effect |
|---|---|
| `/prayer-intention-add`, `/prayer-intention-complete`, `/prayer-intention-delete`, `/prayer-intention-log` | Prayer intention CRUD/log |
| `/timeblock-add-intention`, `/timeblock-add-novena` | Adds intention/novena to a time block |
| `/liturgical-save`, `/liturgical-note`, `/liturgical-delete` | Liturgical calendar CRUD |
| `/liturgy-hours-save` | Saves Liturgy of the Hours |
| `/memory-book-save`, `/memory-book-delete`, `/memory-update` | Memory book / family memory CRUD |
| `/thankyou-add`, `/thankyou-done`, `/thankyou-dismiss`, `/thankyou-suggest` | Thank-you reminder CRUD |

### Profiles / friends / calendar / settings / cycle / signup
| Path | Effect |
|---|---|
| `/save-child-profile`, `/save-mom-profile`, `/save-john-profile` | Profile saves |
| `/save-friend`, `/delete-friend` | Friends directory CRUD |
| `/calendar-add-event`, `/calendar-event-delete`, `/calendar-refresh` | Local calendar event CRUD + refresh |
| `/calendar-config-save`, `/calendar-save-config` | Saves calendar configuration |
| `/subscribed-cal-add`, `/subscribed-cal-delete`, `/subscribed-cal-toggle` | Subscribed calendar CRUD |
| `/family-schedule-save`, `/settings-schedule-save` | Saves family schedule settings |
| `/settings-save`, `/settings-save-ajax` | Settings save (form / AJAX) |
| `/cycle-save`, `/cycle-log-add`, `/cycle-log-delete`, `/cycle-ai-suggest` | Cycle tracking CRUD + AI |
| `/history-restore` | Restores a history snapshot |
| `/signup-submit`, `/waitlist` | Beta signup / waitlist submission |
| `/quest*` (prefix) | Family Quest POST handlers (delegated) |

---

## Section 3 — Data files (data/)

> All persistent data is JSON. Files of size `2` bytes are empty (`{}` or `[]`).
> Sizes below are bytes at snapshot time.

| File | Size (B) | Stores |
|---|---|---|
| `app_settings.json` | 2,569 | Global settings, AI keys, family identity, colors |
| `assignment_analyses.json` | 17,085 | Analyzed assignment records |
| `calendar_cache.json` | 2,402 | Cached external calendar events |
| `calendar_config.json` | 62 | Calendar configuration |
| `calendar_rules.json` | 64 | Calendar display rules |
| `chores.json` | 9,049 | Chore definitions & buckets |
| `coach_history.json` | 47,809 | Coach chat history |
| `coach_last_writes.json` | 106 | Coach undo state |
| `coach_programs.json` | 3,516 | Saved fitness programs |
| `curriculum.json` | 423,328 | Curriculum data (largest file) |
| `cycle_log.json` | 236 | Cycle tracking log |
| `dev_history.json` | 16,675 | Izzy dev assistant history |
| `events.json` | 30,710 | Local calendar events |
| `exercise_assignments.json` | 2,214 | Weekly exercise assignments |
| `exercise_logs.json` | 665 | Logged exercises |
| `family_memory.json` | 2 | Family memory store (empty) |
| `felix_undo.json` | 137,831 | Undo journal |
| `friends.json` | 1,195 | Friends & families directory |
| `frol_activities.json` | 15,933 | FROL activity definitions (v3) |
| `frol_activities.v2_backup.json` | 5,443 | FROL activities v2 backup |
| `frol_wizard_progress.json` | 16,156 | FROL wizard progress |
| `frol_wizard_progress.v2_backup.json` | 138 | FROL wizard progress backup |
| `gradebook.json` | 934 | Per-child grade entries |
| `grades.json` | 99 | Grades overview |
| `gregory_history.json` | 49,281 | Father Gregory chat history |
| `gregory_last_writes.json` | 272 | Gregory undo state |
| `hour_tracking.json` | 138 | Homeschool hour tracking |
| `kid_messages.json` | 2 | Kid messages (empty) |
| `liturgical.json` | 2 | Custom liturgical entries (empty) |
| `lorenzo_history.json` | 28,919 | Lorenzo chat history |
| `lorenzo_last_writes.json` | 114 | Lorenzo undo state |
| `lucy_history.json` | 38,734 | Lucy chat history |
| `lucy_last_writes.json` | 98 | Lucy undo state |
| `manual_tasks.json` | 32,195 | Manually created tasks |
| `meal_inventory.json` | 917 | Meal/pantry inventory |
| `meal_rules.json` | 3,316 | Meal rules & capacity labels |
| `memory_book.json` | 789 | Family memory book entries |
| `mom_notes.json` | 236 | Mom's notes |
| `monica_history.json` | 18,696 | Dr. Monica chat history |
| `monthly_planner.json` | 10,127 | Monthly planner data |
| `notes.json` | 3,999 | Notes |
| `plan_import_history.json` | 193,577 | Plan import history (large) |
| `planning_session.json` | 21 | Active planning session state |
| `poetry_passages.json` | 152 | Saved poetry passages |
| `pope_intentions.json` | 1,654 | Monthly papal prayer intentions |
| `prayer_intentions.json` | 1,116 | Prayer intentions |
| `progress.json` | 203,939 | Task completion progress (compound keys) |
| `recipes.json` | 44,517 | Recipe library |
| `roadmap.json` | 1,121 | Family roadmap |
| `school_previews.json` | 52,442 | School week previews |
| `school_week_plan.json` | 58,290 | Approved school week plan |
| `school_weeks.json` | 99,033 | School week data |
| `seasonal_schedules.json` | 2 | Seasonal schedule library (empty) |
| `sister_mary_history.json` | 9,298 | Sister Mary chat history |
| `subscribed_calendar_cache.json` | 64 | Subscribed calendar cache |
| `subscribed_calendars.json` | 2 | Subscribed calendars (empty) |
| `task_overrides.json` | 15,844 | Per-day task overrides |
| `task_registry.json` | 11,096 | Task registry |
| `thankyou_reminders.json` | 259 | Thank-you reminders |
| `_undo_smoke_test.json` | 21 | Test fixture (undo smoke test) |

**Not yet created (config paths declared, file absent until first save):**
`pantry_staples.json`, `meal_history.json`, `meal_wizard_session.json`.

**Subdirectories:** `5am/`, `assignment_uploads/`, `auth/`, `cycle/`,
`daily_plans/`, `day_grids/`, `day_templates/`, `day_templates_backups/`,
`dev_history.json.archive/`, `goals/`, `history/`, `hour_reports/`,
`liturgy_hours/`, `lorenzo_history.json.archive/`, `meal_plan/`, `prayer/`,
`profiles/`, `readings_cache/`, `saint_cache/`, `sister_mary_history.json.archive/`,
`virtues/`, `weekly_school_plan/`, `__pycache__/`.

---

## Section 4 — Render modules (render_*.py)

| Module | Renders |
|---|---|
| `render_5am.py` | 5AM Club personal-discipline tracker |
| `render_ai_daily.py` | AI-powered daily assistance features |
| `render_ai_planner.py` | AI scheduling assistant |
| `render_assignment_analyzer.py` | AI Assignment Analyzer |
| `render_calendar.py` | Calendar fetching, event display, calendar page |
| `render_child_goals.py` | Per-child goals with substeps & review |
| `render_child_profile.py` | Per-child profile card |
| `render_chores.py` | Chores page, laundry system, van rotation |
| `render_coach.py` | Coach family fitness companion |
| `render_companions.py` | AI companions hub |
| `render_curriculum.py` | Curriculum management system |
| `render_daily_bar.py` | Daily info bar (weather, saint, gospel, events) |
| `render_daily_plan.py` | Daily plan editor, family grid, dashboard views |
| `render_dev.py` | Izzy (Isidore) dev help-desk diagnostic assistant |
| `render_friends.py` | Friends & families directory |
| `render_frol_pdf.py` | FROL printable PDF generator |
| `render_frol_wizard.py` | Rule of Life Wizard |
| `render_goals.py` | Goal system data helpers |
| `render_gradebook.py` | Per-child gradebook |
| `render_gregory.py` | Father Gregory (headmaster) companion |
| `render_john.py` | John's (dad) personal profile page |
| `render_kids_week.py` | Kids' week planning page |
| `render_liturgical.py` | Liturgical calendar engine + page renderers |
| `render_liturgy_hours.py` | Liturgy of the Hours |
| `render_login.py` | Family login screen |
| `render_lorenzo.py` | Lorenzo AI personal chef |
| `render_lucy.py` | Lucy AI day guide |
| `render_meals.py` | Weekly meal planning system |
| `render_meal_wizard.py` | **NEW** — Meal Planning Wizard (Pantry Staples page) |
| `render_memory_book.py` | Family memory book |
| `render_misc.py` | Dashboard, Mom, Notes, Tasks, Roadmap, Planner, School, History |
| `render_mom_profile.py` | Mom's personal profile page |
| `render_monica.py` | Dr. Monica child development/health companion |
| `render_morning_anchor.py` | Morning Anchor (Step 0) & Evening Anchor (Step 5) |
| `render_plan_importer.py` | Plan Import tool (JS in static/js/plan_importer_*.js) |
| `render_plan_month.py` | Plan My Month |
| `render_plan_quarter.py` | Quarterly goal planning |
| `render_plan_tomorrow.py` | AI-powered tomorrow planning |
| `render_plan_week.py` | Plan My Week |
| `render_plan_year.py` | Plan My Year |
| `render_prayer.py` | Prayer intentions |
| `render_programs.py` | Coach's saved programs + weekly exercise assignments |
| `render_readings.py` | Daily Mass readings |
| `render_schedule.py` | Schedule cards, task lists, print pages, today/week |
| `render_schedule_support.py` | Family schedule engine, now/next strip, timeline |
| `render_school_pdf.py` | School Week printable PDF generator |
| `render_seasons.py` | Phase F season detection helper |
| `render_settings.py` | Single source of truth for all configuration |
| `render_signup.py` | Beta waitlist signup survey |
| `render_sister_mary.py` | Sister Mary contemplative Marian companion |
| `render_student.py` | Student portal |
| `render_subject.py` | Per-subject curriculum review pages |
| `render_timeblock.py` | Lauren's time-block homepage |
| `render_virtues.py` | Virtue tracker |
| `render_week_school.py` | Weekly school progress page (/week-school) |
| `render_week_view.py` | Family week at a glance |
| `render_wizards.py` | Wizards hub page (/wizards) |

---

## Section 5 — data_helpers.py functions (216 total)

> `data_helpers.py` is the only module that reads/writes JSON. Grouped by area.

**Dates & utilities:** `today_iso`, `tomorrow_iso`, `monday_iso_for`,
`normalize_date_query`, `safe_int`, `clean_priority`, `clean_status`,
`clean_child`, `clean_text`, `clean_weekday`, `lines_to_list`, `as_text`,
`_now_ts`.

**Snapshots / history:** `list_snapshots`, `restore_snapshot`,
`load_snapshot_data`, `_archive_history_file`.

**Tasks:** `load_progress`, `load_manual_tasks`, `save_manual_tasks`,
`active_manual_tasks`, `ensure_manual_task_ids`, `format_recurrence_label`,
`advance_recurring_task`, `_nth_weekday_of_month`, `_add_months`,
`_next_specific_weekday`, `_next_monthly_day`, `load_task_overrides`,
`save_task_overrides`, `set_task_override`, `clear_task_override`,
`get_day_overrides`, `get_postponed_for_day`.

**Chores:** `_ensure_chore_buckets`, `load_chores_data`, `save_chores_data`,
`_resolve_chore_person`, `get_chores_due_today`, `get_due_grooming`.

**Hour tracking:** `load_hour_tracking`, `save_hour_tracking`, `add_hour_log`,
`save_hour_report_snapshot`, `get_hour_totals`.

**FROL activities / seasonal:** `_activity_new_id`, `_file_has_legacy_activities`,
`_ensure_activities_backup`, `_upgrade_activity_v2_to_v3`, `load_frol_activities`,
`save_frol_activities`, `load_seasonal_schedules`, `_seasonal_snapshot_day_templates`,
`save_seasonal_schedule`, `get_seasonal_schedule`, `find_seasonal_schedule_for`,
`_summarize_prior_seasonal_entry`, `delete_seasonal_schedule`,
`get_seasonal_context`, `get_companion_seasonal_block`, `get_frol_day_slots`,
`load_day_template`, `get_frol_times`, `get_family_rule_of_life_text`,
`get_full_frol_context`.

**Roadmap / notes / liturgical:** `load_roadmap`, `save_roadmap`,
`load_mom_notes`, `save_mom_notes`, `load_liturgical_custom`,
`save_liturgical_custom`.

**Calendars:** `load_calendar_config`, `save_calendar_config`,
`load_calendar_cache`, `save_calendar_cache`, `load_subscribed_calendar_cache`,
`save_subscribed_calendar_cache`, `load_calendar_rules`, `save_calendar_rules`,
`load_subscribed_calendars`, `save_subscribed_calendars`, `load_family_schedule`,
`save_family_schedule`, `load_local_events`, `save_local_events`,
`expand_local_events_for_range`.

**Exercise / coach:** `load_exercise_assignments`, `save_exercise_assignments`,
`load_coach_programs`, `save_coach_program`, `load_exercise_logs`,
`save_exercise_log`, `delete_coach_program`.

**Companion histories:** `load_lucy_history`/`save_lucy_history`/
`append_lucy_messages`/`clear_lucy_history`, `load_lorenzo_history`/`save…`/
`append…`/`clear…`, `load_gregory_history`/…, `load_coach_history`/…,
`load_dev_history`/…, `load_monica_history`/…, `load_sister_mary_history`/
`save_sister_mary_history`/`append_sister_mary_messages`/`clear_sister_mary_history`,
plus `_safe_clear`.

**Thank-you reminders:** `load_thankyou_reminders`, `save_thankyou_reminders`,
`pending_thankyou_reminders`, `due_thankyou_reminders`,
`due_thankyou_reminders_for`.

**Assignments & gradebook:** `load_assignment_analyses`,
`save_assignment_analyses`, `add_assignment_analysis`,
`update_assignment_analysis`, `delete_assignment_analysis`, `percent_to_letter`,
`letter_to_gpa`, `school_year_for_date`, `load_gradebook`, `save_gradebook`,
`add_gradebook_entry`, `update_gradebook_entry`, `delete_gradebook_entry`,
`gradebook_for_child`.

**Recipes:** `load_recipes`, `save_recipes`, `get_recipe_by_id`, `save_recipe`,
`add_recipe`, `delete_recipe`, `search_recipes`.

**Planning sessions:** `load_planning_session`, `save_planning_session`,
`start_planning_session`, `advance_planning_session`, `clear_planning_session`,
`planning_session_summary`, `load_monthly_planner`.

**Curriculum:** `load_curriculum`, `save_curriculum`, `get_curriculum_week`,
`get_curriculum_subjects`, `week_day_segments`, `resolve_week_text`,
`get_curriculum_week_assignments`, `subject_meeting_days`, `subject_day_index`,
`advance_curriculum_cursor`, `count_school_check_items`, `is_math_subject`,
`is_math_test_text`, `sort_school_days`.

**School week plans:** `load_school_week_plan`, `save_school_week_plan`,
`generate_weekly_school_plan`, `get_approved_school_week_plan`.

**Student portal / curriculum library:** `load_curriculum_library`,
`save_curriculum_library`, `get_subject_by_id`, `get_assignments_for_student`,
`load_student_submissions`, `save_student_submissions`, `add_student_submission`,
`get_submissions_for_grading`, `get_submissions_by_student`,
`load_grading_history`, `save_grading_history`, `add_grade_record`,
`load_curriculum_documents`, `save_curriculum_documents`, `add_curriculum_document`.

**Family memory:** `load_family_memory`, `save_family_memory`, `add_memory`,
`update_memory`, `delete_memory`, `_tokenize_memory`, `find_memory_conflicts`,
`get_memory_context_block`.

**Prayer / intentions:** `load_prayer_intentions`, `save_prayer_intentions`,
`add_daily_intention`, `add_repeating_intention`, `add_novena`,
`get_active_intentions_for_date`, `check_upcoming_novenas`,
`load_pope_intentions`, `save_pope_intentions`, `get_pope_intention_for_month`.

**Meal Planning Wizard:** `load_pantry_staples`, `save_pantry_staples`,
`load_meal_history`, `save_meal_history`, `add_meal_history_entry`,
`get_recent_meals`, `load_meal_wizard_session`, `save_meal_wizard_session`,
`clear_meal_wizard_session`, `update_meal_wizard_session`.

---

## Section 6 — config.py constants

> `config.py` owns all file paths (claud.md gotcha — never hardcode paths).
> Several identity/color/epoch values default here but are overridden at
> runtime from `app_settings.json` (Rule 19 — keep family identity in settings).

**Server:**
- `HOST = "0.0.0.0"`
- `PORT = int(os.environ.get("PORT", 8000))`

**Core data file paths:**
- `MANUAL_TASKS_FILE = "data/manual_tasks.json"`
- `CHORES_FILE = "data/chores.json"`
- `MOM_NOTES_FILE = "data/mom_notes.json"`
- `ROADMAP_FILE = "data/roadmap.json"`
- `LITURGICAL_FILE = "data/liturgical.json"`
- `FAMILY_SCHEDULE_FILE = "data/family_schedule.json"`
- `CALENDAR_CONFIG_FILE = "data/calendar_config.json"`
- `CALENDAR_CACHE_FILE = "data/calendar_cache.json"`
- `MONTHLY_PLANNER_FILE = "data/monthly_planner.json"`
- `CALENDAR_RULES_FILE = "data/calendar_rules.json"`
- `SUBSCRIBED_CALS_FILE = "data/subscribed_calendars.json"`
- `SUBSCRIBED_CACHE_FILE = "data/subscribed_calendar_cache.json"`
- `APP_SETTINGS_FILE = "data/app_settings.json"`
- `CURRICULUM_FILE = "data/curriculum.json"`
- `TASK_OVERRIDES_FILE = "data/task_overrides.json"`
- `COACH_PROGRAMS_FILE = "data/coach_programs.json"`
- `EXERCISE_LOGS_FILE = "data/exercise_logs.json"`
- `SCHOOL_WEEK_PLAN_FILE = "data/school_week_plan.json"`
- `FAMILY_MEMORY_FILE = "data/family_memory.json"`
- `PRAYER_INTENTIONS_FILE = "data/prayer_intentions.json"`
- `SISTER_MARY_HISTORY_FILE = "data/sister_mary_history.json"`
- `POPE_INTENTIONS_FILE = "data/pope_intentions.json"`
- `FROL_WIZARD_PROGRESS_FILE = "data/frol_wizard_progress.json"`
- `HOUR_TRACKING_FILE = "data/hour_tracking.json"`
- `HOUR_REPORTS_DIR = "data/hour_reports"`
- `FROL_ACTIVITIES_FILE = "data/frol_activities.json"`

**FROL day-template paths (Phase E):**
- `DAY_TEMPLATES_DIR = "data/day_templates"`
- `DAY_TEMPLATES_PREVIEW_DIR = "data/day_templates_preview"`
- `DAY_TEMPLATES_BACKUP_DIR = "data/day_templates_backups"`

**Seasonal (Phase F):**
- `SEASONAL_SCHEDULES_FILE = "data/seasonal_schedules.json"`

**Meal Planning Wizard:**
- `MEALS_DIR = "data/meal_plan"`
- `MEAL_RULES_FILE = "data/meal_rules.json"`
- `MEAL_INVENTORY_FILE = "data/meal_inventory.json"`
- `PANTRY_STAPLES_FILE = "data/pantry_staples.json"`
- `MEAL_HISTORY_FILE = "data/meal_history.json"`
- `MEAL_WIZARD_SESSION_FILE = "data/meal_wizard_session.json"`

**Validation sets:**
- `VALID_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}`
- `VALID_STATUSES = {"active", "done", "inactive"}`

**Calendar / scheduling constants:**
- `WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]`
- `WEEKDAY_ORDER = {day: i for i, day in enumerate(WEEKDAYS)}`
- `SCHEDULE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]`
- `MONTH_NAMES = ["January" … "December"]` (12 entries)
- `ROADMAP_STATUSES = ["Someday", "Ready", "In Progress", "Done"]`
- `ASSIGNABLE_TO = ["Mom"] + list(CHILDREN)` → `["Mom", "JP", "Joseph", "Michael", "James"]`
- `CHILDREN = ["JP", "Joseph", "Michael", "James"]` (imported from `daily_schedule_engine`)

**Identity / colors / epoch (defaults; runtime-overridden from app_settings.json):**
- `_DEFAULT_CHILD_COLORS` → JP `#c0392b`, Joseph `#27ae60`, Michael `#e67e22`, James `#2980b9`
- `CHILD_COLORS = _load_child_colors()` (merges settings over defaults; `child_color(child, key)` re-reads each call)
- `_DEFAULT_PARENT_COLORS` → Lauren `#7c3aed`, John `#2563eb`; accessor `parent_color(name, key)`
- `VAN_ROTATION_EPOCH = _load_van_epoch()` (defaults to `date(2025, 1, 6)`; `get_van_epoch()` re-reads)
- `VAN_ROLE_A = "Interior Reset Lead"`
- `VAN_ROLE_B = "Bin & Organization Lead"`
- `get_app_setting(key, default=None)` — reads a single value from app_settings.json

---

## Section 7 — Current claud.md rules (full text, verbatim on disk)

### Python 3.11 hard rules — never violate these

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

### Additional rules (13–19)

13. **FROL WIZARD NESTED FORM ADDENDUM** — The _body_has_form check in
    _section_chrome looks for action="/frol-wizard" in the body string.
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
    apply to today's task. If you cannot paste the rules back accurately
    stop and ask Lauren to re-paste claud.md before proceeding.

16. **MAGNIFICA HUMANITAS DESIGN PRINCIPLES** — Every feature must reflect
    these. The deepest danger to guard against, named by the encyclical:
    that people come to see themselves and one another as projects to be
    optimized rather than persons called to relationship and communion. The
    app must never become an optimization engine; it reduces friction so the
    family has more room for prayer, presence, love, rest, and formation.
    One — the app is a tool not an authority; every AI suggestion is framed
    as a suggestion never a prescription; use "here is one way to think about
    this" never "you should" or "the optimal schedule is." Two — companions
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
    family's discernment. Seven — formation in digital wisdom; the explicit
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
    will use it. Never hardcode McAdams or any single family's specifics
    into code as if it is the only family — keep family identity and config
    in app_settings.json. Keep all data reads and writes flowing through
    data_helpers.py with no direct file access in route handlers, so the
    eventual swap from JSON files to a database happens in one place. Do not
    bake in single-user assumptions in new feature logic where it is cheap
    to avoid them. This is design hygiene that costs nothing now and
    prevents a full rewrite later; it does NOT mean building multi-user
    features before August 15th.

---

## Recent changes (this session — Meal Planning Wizard Phase C)

- **`render_meal_wizard.py`** (new, 257 lines) — Pantry Staples page with
  first-run and returning-user modes.
- **`app.py`** — added GET `/pantry-staples` and POST `/pantry-staples-save`,
  plus imports for `render_pantry_staples_page` and `save_pantry_staples`.
- **`render_settings.py`** — added a Pantry Staples link card in the meal
  rules section.
- **`claud.md`** — clarified Rule 3 (GET = elif chains; POST = standalone
  `if path == …: … return` blocks).
