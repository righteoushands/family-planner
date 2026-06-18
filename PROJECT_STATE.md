# PROJECT_STATE.md — Sancta Familia
Technical snapshot of the current codebase. Read at the start of future
sessions for a fast orientation. Generated 2026-06-18.

> Counts as of this snapshot: 98 exact-match + 16 prefix (`startswith`) GET routes in `do_GET`; ~207 POST routes in `do_POST`; 57 render modules; 217 functions in `data_helpers.py`.
>
> **Phase E (Meal Planning Wizard) is complete.** New since the June 11 snapshot: GET `/meal-wizard-step2`; POST `/meal-wizard-step2-save`; new shared static file `static/inventory_input.js`; `render_meal_wizard_step2` + `_s2_field` in `render_meal_wizard.py`; `update_meal_wizard_session` and the meal-wizard session/history/pantry helpers in `data_helpers.py`.

---

## Section 1 — GET routes (defined in app.py `do_GET`)

Per Rule 3, all GET routing uses `elif` chains in `do_GET`. Auth-gated routes
pass through the global `viewer = _require_auth(path)` gate before rendering.

### 1a. Exact-match routes (`path == "…"`)

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
| `/meal-wizard-step2` | render: render_meal_wizard_step2()  ← **Phase E** |
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

### 1b. Prefix routes (`path.startswith("…")`)

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

Per Rule 3, POST routing matches the codebase convention of `elif path == "…":`
blocks. JSON-body routes must be registered in `_JSON_PATHS`
(`/plan-import-apply`, `/plan-import-undo-placement`, `/curriculum-save`,
`/curriculum-minutes`, `/poetry-passage-save`); all others read the urlencoded
`data`/form fields.

**Auth & messaging:** `/login`, `/student-message-read`, `/message-mom`, `/change-pin`, `/messages-read`, `/save-pins`

**Meals & pantry:** `/pantry-staples-save`, `/meal-save-plan`, `/meal-rule-add`, `/meal-rule-delete`, `/meal-save-inventory`, `/meal-wizard-step2-save` ← **Phase E**, `/meal-generate`, `/meal-save-constraints`, `/meal-edit`, `/recipe-save`, `/recipe-import`, `/recipe-delete`, `/ai-meal-plan`

**Plan importer:** `/plan-import-save-session`, `/plan-import-history-delete`, `/plan-import-analyze`, `/plan-import-apply`, `/plan-import-undo-placement`, `/plan-import-consult`, `/plan-import-group-consult`, `/api/extract-suggestions`

**School / subjects / gradebook:** `/subject-upload-image`, `/subject-send-to-mom`, `/subject-grade-add`, `/subject-grade-delete`, `/subject-link-add`, `/subject-link-delete`, `/subject-doc-delete`, `/assignment-analyze`, `/assignment-update`, `/assignment-delete`, `/assignment-reply`, `/gradebook-add`, `/gradebook-update`, `/gradebook-delete`, `/school-upload`, `/approve-school-preview`, `/approve-school-week`, `/regenerate-school-week`, `/reparse-school-preview`, `/save-school-preview-edits`, `/school-settings-save`

**Curriculum:** `/curriculum-parse`, `/curriculum-save`, `/curriculum-minutes`, `/poetry-passage-save`, `/curriculum-week`, `/curriculum-subject-week`, `/curriculum-subject-day`, `/curriculum-delete`

**Tasks / notes / plan items:** `/toggle-task`, `/add-note`, `/archive-note`, `/convert-note`, `/add-task`, `/task-update`, `/task-done`, `/task-delete`, `/task-hard-delete`, `/task-purge-inactive`, `/task-override`, `/plan-add-item`, `/plan-toggle-item`, `/plan-item-update`, `/planner-add-task`, `/add-to-plan-quick`

**Daily grid / anchor:** `/anchor-save`, `/grid-save-template`, `/grid-push-weekly`, `/grid-cell-save`, `/grid-publish`, `/grid-reset`, `/schedule-template-save`

**Chores / van:** `/save-chores`, `/apply-laundry`, `/apply-van-rotation`

**Thank-you notes:** `/thankyou-add`, `/thankyou-done`, `/thankyou-dismiss`, `/thankyou-suggest`

**Companions (chat / rules / history):** `/lucy-tts`, `/lucy-rule-save`, `/lucy-chat`, `/lucy-clear-history`, `/lorenzo-chat`, `/lorenzo-rule-save`, `/lorenzo-plan-start`, `/lorenzo-plan-end`, `/lorenzo-clear-history`, `/headmaster-chat`, `/headmaster-clear-history`, `/coach-chat`, `/coach-clear-history`, `/dr-monica-chat`, `/dr-monica-clear-history`, `/sister-mary-chat`, `/sister-mary-clear-history`, `/dev-chat`, `/dev-apply`, `/dev-write`, `/dev-undo`, `/dev-restart`, `/dev-clear`

**Coach programs:** `/programs-save`, `/programs-delete`, `/programs-edit`, `/exercise-log`, `/hour-log-add`, `/hour-log-edit`, `/hour-log-delete`

**FROL wizard & seasonal:** `/frol-save-seasonal`, `/frol-seasonal-use`, `/frol-seasonal-delete`, `/frol-overlay-toggle`, `/frol-overlay-set`, `/frol-overlay-clear`, `/pod-dismiss-season`, `/pod-toggle-traveling`, `/frol-wizard`, `/frol-wizard-chat`, `/frol-wizard-finalize`, `/frol-set-variant`, `/frol-rollback-v3`, `/frol-delete-activity`, `/frol-edit-activity`

**Prayer / liturgical / memory:** `/prayer-intention-add`, `/prayer-intention-delete`, `/prayer-intention-log`, `/prayer-intention-complete`, `/timeblock-add-intention`, `/timeblock-add-novena`, `/liturgy-hours-save`, `/liturgical-save`, `/liturgical-delete`, `/liturgical-note`, `/memory-book-save`, `/memory-book-delete`, `/memory-update`

**Calendar:** `/subscribed-cal-add`, `/subscribed-cal-toggle`, `/subscribed-cal-delete`, `/calendar-refresh`, `/calendar-add-event`, `/calendar-event-delete`

**Goals / quarter / children:** `/roadmap-add`, `/roadmap-update`, `/roadmap-delete`, `/child-goal-add`, `/child-goal-archive`, `/child-substep-add`, `/child-substep-toggle`, `/child-substep-delete`, `/quarter-save-goals`, `/quarter-journal-save`, `/quarter-save-step`, `/quarter-checkin`, `/goal-add`, `/save-child-profile`, `/virtue-checkin`

**Cycle:** `/cycle-log-add`, `/cycle-log-delete`, `/cycle-ai-suggest`, `/cycle-save`

**Plan tomorrow / week / month / AI briefs:** `/plan-tomorrow-questions`, `/plan-tomorrow-generate`, `/plan-tomorrow-push`, `/plan-week-save`, `/plan-month-save`, `/kids-week-save`, `/5am-save`, `/ai-daily-schedule`, `/ai-school-plan`, `/ai-evening-examen`, `/ai-weekly-review`, `/ai-chore-adjust`, `/ai-intention-prayer`, `/ai-capacity-preview`, `/ai-week-brief`, `/ai-month-brief`, `/ai-year-brief`, `/ai-suggest-goals`, `/ai-generate-steps`, `/plan-ai-suggest`, `/preview-keep`, `/preview-discard`

**Profiles / signup / misc:** `/save-mom-profile`, `/save-john-profile`, `/save-friend`, `/delete-friend`, `/mom-add-note`, `/history-restore`, `/signup-submit`, `/waitlist`, `/settings-save-ajax`, `/settings-save`

---

## Section 3 — Data files (data/)

All persistent data is JSON under `data/`. `config.py` owns all file paths;
`data_helpers.py` is the only module that should read/write these files.

> **Phase E note:** of the six meal-wizard files, `meal_inventory.json` and
> `meal_rules.json` and the `meal_plan/` dir exist on disk. **`pantry_staples.json`,
> `meal_history.json`, and `meal_wizard_session.json` do NOT exist yet** — they are
> created lazily by their `save_*` helpers on first write. Their absence is normal.

### Meal-related
| File | Size | Stores |
|---|---|---|
| `meal_inventory.json` | 917 B | Fridge/freezer/pantry/use-soon inventory blob + `last_updated` |
| `meal_rules.json` | 3.3 KB | Meal planning rules/constraints |
| `meal_plan/` (dir) | — | Per-week meal plans (`YYYY-Www` keys) |
| `pantry_staples.json` | *absent* | Pantry staples checklist (created on first save) |
| `meal_history.json` | *absent* | Recent-meals history (created on first save) |
| `meal_wizard_session.json` | *absent* | Wizard session state: `confirmed_inventory`, `use_soon_items`, etc. (created on first save) |
| `recipes.json` | 46 KB | Recipe library |

### Core app data
| File | Size | Stores |
|---|---|---|
| `app_settings.json` | 2.6 KB | Global settings + AI API keys + family identity |
| `progress.json` | 215 KB | Task/school completion (`YYYY-MM-DD::Person::task`) |
| `manual_tasks.json` | 13 KB | Manually added tasks |
| `task_overrides.json` | 16 KB | Per-day task overrides |
| `task_registry.json` | 53 KB | Task registry |
| `chores.json` | 9 KB | Chore definitions per person |
| `curriculum.json` | 423 KB | Curriculum data (per child/subject/week) |
| `gradebook.json` | 934 B | Gradebook entries |
| `grades.json` | 99 B | Grades summary |
| `assignment_analyses.json` | 17 KB | Assignment analyzer records |
| `events.json` | 31 KB | Local calendar events |
| `monthly_planner.json` | 10 KB | Monthly planner |
| `roadmap.json` | 1.1 KB | Roadmap ideas |
| `notes.json` | 4 KB | Notes |
| `mom_notes.json` | 236 B | Mom notes |
| `thankyou_reminders.json` | 256 B | Thank-you reminders |
| `memory_book.json` | 789 B | Memory book entries |
| `family_memory.json` | 2 B | Family memory store |

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
| `frol_wizard_progress.json` | 16 KB | FROL wizard progress |
| `seasonal_schedules.json` | 2 B | Saved seasonal schedules |
| `day_templates/` (dir) | — | `{Weekday}.json` — FROL source of truth |
| `day_grids/` (dir) | — | Per-date day grids |
| `daily_plans/` (dir) | — | Per-date daily plans |
| `family_schedule.json` | (n/a) | Family schedule |
| `hour_tracking.json` | 138 B | School hour tracking |

### Companion histories
| File | Size | Stores |
|---|---|---|
| `lucy_history.json` | 28 KB | Lucy chat history |
| `lorenzo_history.json` | 28 KB | Lorenzo chat history |
| `gregory_history.json` | 49 KB | Father Gregory chat history |
| `coach_history.json` | 44 KB | Coach chat history |
| `monica_history.json` | 19 KB | Dr. Monica chat history |
| `sister_mary_history.json` | 9 KB | Sister Mary chat history |
| `dev_history.json` | 17 KB | Dev companion (Izzy/Felix) history |
| `*_last_writes.json` | small | Per-companion undo (last data-altering action) |

### Coach / exercise / misc
| File | Size | Stores |
|---|---|---|
| `coach_programs.json` | 3.5 KB | Coach fitness programs |
| `exercise_logs.json` | 665 B | Exercise logs |
| `exercise_assignments.json` | 2.2 KB | Exercise assignments |
| `school_week_plan.json` | 58 KB | Approved weekly school plan |
| `school_weeks.json` | 99 KB | School weeks data |
| `school_previews.json` | 52 KB | AI school previews |
| `plan_import_history.json` | 194 KB | Plan-import history + undo |
| `cycle_log.json` | 236 B | Cycle log |
| `poetry_passages.json` | 152 B | Poetry passages |
| `friends.json` | 1.2 KB | Friends/other families |
| `planning_session.json` | 21 B | Lorenzo planning session |

### Verification harnesses (data/)
`verify_phase_a.py` … `verify_phase_g.py`, `verify_task_42.py` — per Rule 10,
these operate on temp copies and restore from backup; never run against live data.

---

## Section 4 — Render modules (render_*.py) and their functions

57 render modules. Public (page/builder) functions listed; leading-underscore
helpers omitted for brevity unless central.

- **render_5am.py** (12): load_day, save_day, render_5am_dashboard_widget, render_5am_page
- **render_ai_daily.py** (12): ai_daily_schedule, ai_meal_plan, ai_school_plan, ai_evening_examen, ai_weekly_review, ai_chore_adjust, ai_intention_prayer
- **render_ai_planner.py** (2): build_context_packet, render_ai_panel
- **render_assignment_analyzer.py** (5): render_assignment_analyzer_page
- **render_calendar.py** (17): fetch_caldav_events, get_or_create_family_calendar, write_caldav_event, refresh_calendar, fetch_ics_events, refresh_subscribed_calendars, events_for_date, get_all_events, render_event_pill, render_calendar_today_strip, render_calendar_page
- **render_child_goals.py** (12): load_child_goals, save_child_goals, add_child_goal, update_child_goal, add_substep, toggle_substep, delete_substep, render_child_goals_section
- **render_child_profile.py** (5): load_child_profile, save_child_profile, profile_summary_for_lucy, render_child_profile_section
- **render_chores.py** (16): get_kitchen_roles, apply_canonical_chores, apply_laundry_defaults, get_vacuum_week, get_wipe_week, get_van_week_number, get_van_roles, get_van_chore_lines, apply_van_rotation, render_van_roles_card, render_van_roles_page, render_chores_page
- **render_coach.py** (8): build_coach_context, render_coach_page
- **render_companions.py** (1): render_companions_page
- **render_curriculum.py** (7): render_recent_submissions_widget, parse_modg_paste, render_curriculum_page
- **render_daily_bar.py** (11): get_location, get_child_birthdays, get_special_events, fetch_weather, get_child_age, render_child_age_strip, get_todays_special_events, render_daily_bar
- **render_daily_plan.py** (34): load_daily_plan, save_daily_plan, seed_from_grid, get_or_seed_plan, add_item_to_plan, toggle_plan_item, delete_plan_item, reorder_plan_items, update_item_time, sort_plan_chronologically, publish_plan, reset_plan, load_day_grid, save_day_grid, is_grid_published, publish_day_grid, seed_day_grid, get_or_seed_grid, save_day_template, render_add_to_plan_btn, render_plan_editor, render_plan_fragment_html, render_dashboard_plan, render_dashboard_grid, render_grid_print_page
- **render_dev.py** (9): build_felix_context, render_dev_page
- **render_friends.py** (7): load_friends, save_friends, render_friends_page
- **render_frol_pdf.py** (5): generate_frol_pdf
- **render_frol_wizard.py** (133): load_progress, save_progress, reset_progress, is_complete, is_dismissed, save_field, advance_step, save_section_field, advance_section, render_section_1…render_section_14, render_section_11_holidays, render_landing, render_seasonal_view_page, render_step_1…render_step_5, s12_*/s15_* schedule+variant generators, finalize_v2, john_traveling_enabled, set_john_traveling, get_pod_day_slots (large multi-phase wizard)
- **render_goals.py** (16): current_quarter, quarter_start, quarter_end, quarter_week_number, all_quarters, load_master_goals, save_master_goals, add_master_goal, load_quarter_plan, save_quarter_plan, get_active_goals_with_steps, record_weekly_checkin, update_weekly_step, completion_pct, goal_progress_bars
- **render_gradebook.py** (6): render_gradebook_page
- **render_gregory.py** (11): build_gregory_context, render_gregory_page (+ helpers)
- **render_john.py** (7): John page renderer + helpers
- **render_kids_week.py** (5): load_week_plan, save_week_plan, render_kids_week_page
- **render_liturgical.py** (12): get_moveable_feasts, get_floating_liturgical_events, get_liturgical_season, is_fast_day, is_abstinence_day, get_day_info, get_vestment_color, is_penance_season, render_liturgical_day_card, render_liturgical_page, render_liturgical_edit_page
- **render_liturgy_hours.py** (17): liturgy-of-the-hours page + hour builders
- **render_login.py** (1): login page
- **render_lorenzo.py** (18): build_lorenzo_context, render_lorenzo_page (+ inventory/recipe/constraint/context helpers)
- **render_lucy.py** (15): build_lucy_context, render_lucy_page, escape_js, get_mom_lucy_brief, get_child_lucy_brief, get_prayer_lucy_brief
- **render_meals.py** (24): render_meal_planner_page, render_meal_print_page, load_meal_plan, save_meal_plan, load_inventory, save_inventory, _build_meal_prompt, _week_key, _planning_week_key (+ helpers)
- **render_meal_wizard.py** (15): render_pantry_staples_page, render_meal_wizard_week_glance, **render_meal_wizard_step2** (+ `_s2_field`, `_S2_*` style constants, week-glance/pantry helpers)  ← **Phase E**
- **render_memory_book.py** (5): load_memory_book, save_memory_book, add_memory_entry, delete_memory_entry, render_memory_book_page
- **render_misc.py** (35): render_dashboard, render_planner_page, render_now_page, render_mom_page, render_print_lauren_day, render_mom_step_fragment, render_notes, render_tasks, render_roadmap_page, render_history_page, render_school_preview_card, render_school_page, render_school_edit_page, render_thankyou_page (+ mom-step/now-block helpers)
- **render_mom_profile.py** (6): mom profile page + helpers
- **render_monica.py** (8): build_monica_context, render_monica_page
- **render_morning_anchor.py** (6): fetch_this_day_in_history, save_anchor_state, render_morning_anchor, render_evening_anchor
- **render_plan_importer.py** (7): _load_upcoming_events, _format_events_summary, build_analysis_system_prompt, detect_relevant_companions, build_consult_system_prompt, build_roundtable_prompt, render_plan_import_page (JS in static/js/plan_importer_{core,consult}.js)
- **render_plan_month.py** (6): render_plan_month_page + helpers
- **render_plan_quarter.py** (2): render_plan_quarter_page + helper
- **render_plan_tomorrow.py** (12): ai_generate_questions, ai_generate_plan, render_plan_tomorrow_page (+ data-gather helpers)
- **render_plan_week.py** (10): load_intentions, save_intentions_data, render_plan_week_page
- **render_plan_year.py** (1): render_plan_year_page
- **render_prayer.py** (15): prayer/intentions page + helpers
- **render_programs.py** (9): render_programs_page (+ card/grid helpers)
- **render_readings.py** (8): fetch_readings_for_date, render_readings_page
- **render_schedule.py** (40): render_child_schedule, render_today_all, render_week, render_print_day, render_print_week, render_print_child_day_list (+ many helpers)
- **render_schedule_support.py** (8): generate_half_hour_times, get_current_slot, render_now_next_strip, render_today_timeline, render_litany_block, render_family_schedule_page
- **render_school_pdf.py** (10): generate_school_pdf
- **render_seasons.py** (6): migrate_label, season_start, upcoming_season, current_season
- **render_settings.py** (20): load_app_settings, save_app_settings, resolve_daily_mass_url, render_settings_page (+ section builders)
- **render_signup.py** (5): load_waitlist, save_signup, render_signup_page, render_waitlist_admin
- **render_sister_mary.py** (6): build_sister_mary_context, render_sister_mary_page
- **render_student.py** (11): render_student_page, render_student_grades (+ helpers)
- **render_subject.py** (36): render_subject_page, render_grades_summary_page, render_hour_report, add_image_entry, add_manual_entry, delete_entry, add_link, delete_link, add_document, delete_document, mark_entry_sent_to_mom, apply_mom_grade, subject_weeks, subject_averages, letter_grade, ai_grade_image_gregory (+ tab renderers)
- **render_timeblock.py** (42): render_timeblock_homepage (+ hours, saint/pope cards, meals/FROL snapshots, feast art, intentions widget)
- **render_virtues.py** (21): generate_virtue_content, render_virtue_dashboard_widget, render_virtues_dashboard, render_virtue_me_page, render_virtue_family_page, render_virtue_child_page
- **render_week_school.py** (14): load_poetry_passages, save_poetry_passages, render_week_school_page (+ week-build helpers)
- **render_week_view.py** (10): render_week_view (+ feast/event/task helpers)
- **render_wizards.py** (4): render_wizards_page (+ card helpers)

### Shared static JS
- **static/inventory_input.js** (Phase E shared IIFE) defines: `window.toggleMic`, `window.parseInventory`, `window.saveInventory` (→ `/meal-save-inventory`), `window.clearInventory` (client-side only), `window.saveInventoryWizard` (→ `/meal-wizard-step2-save`). Loaded by both the meals page (`render_meals.py`) and Step 2 (`render_meal_wizard.py`). The Step 2 Save button calls `saveInventoryWizard()`; the meals page still uses `saveInventory()`.
- **static/js/plan_importer_core.js**, **static/js/plan_importer_consult.js**: Plan Importer client logic.

---

## Section 5 — data_helpers.py functions (217)

`data_helpers.py` is the single read/write layer for `data/*.json`. One-liners:

### Snapshots / dates
- `list_snapshots`, `restore_snapshot`, `load_snapshot_data` — checkpoint snapshots
- `today_iso`, `tomorrow_iso`, `monday_iso_for`, `normalize_date_query` — date helpers

### School week plan
- `load_school_week_plan`, `save_school_week_plan`, `generate_weekly_school_plan`, `get_approved_school_week_plan`

### Cleaning / parsing
- `safe_int`, `clean_priority`, `clean_status`, `clean_child`, `clean_text`, `clean_weekday`, `lines_to_list`, `count_school_check_items`, `is_math_subject`, `is_math_test_text`, `sort_school_days`, `as_text`

### Progress / tasks
- `load_progress`, `load_manual_tasks`, `save_manual_tasks`, `active_manual_tasks`, `ensure_manual_task_ids`
- `format_recurrence_label`, `advance_recurring_task` — recurrence
- `load_task_overrides`, `save_task_overrides`, `set_task_override`, `clear_task_override`, `get_day_overrides`, `get_postponed_for_day`

### Chores / grooming
- `load_chores_data`, `save_chores_data`, `get_chores_due_today`, `get_due_grooming`

### Hours
- `load_hour_tracking`, `save_hour_tracking`, `add_hour_log`, `save_hour_report_snapshot`, `get_hour_totals`

### FROL activities / seasonal
- `load_frol_activities`, `save_frol_activities`, `_activity_new_id`
- `load_seasonal_schedules`, `save_seasonal_schedule`, `get_seasonal_schedule`, `find_seasonal_schedule_for`, `delete_seasonal_schedule`, `get_seasonal_context`, `get_companion_seasonal_block`

### Roadmap / notes / liturgical config
- `load_roadmap`, `save_roadmap`, `load_mom_notes`, `save_mom_notes`, `load_liturgical_custom`, `save_liturgical_custom`

### Calendar
- `load_calendar_config`, `save_calendar_config`, `load_calendar_cache`, `save_calendar_cache`, `load_subscribed_calendar_cache`, `save_subscribed_calendar_cache`, `load_calendar_rules`, `save_calendar_rules`, `load_subscribed_calendars`, `save_subscribed_calendars`
- `load_local_events`, `save_local_events`, `expand_local_events_for_range`, **`get_merged_calendar_events`** — merge local + subscribed for a range

### Schedule / day templates
- `load_family_schedule`, `save_family_schedule`, `get_frol_day_slots`, `load_day_template`, `get_frol_times`

### Coach / exercise
- `load_exercise_assignments`, `save_exercise_assignments`, `load_coach_programs`, `save_coach_program`, `load_exercise_logs`, `save_exercise_log`, `delete_coach_program`

### FROL text context
- `get_family_rule_of_life_text`, `get_full_frol_context`

### Companion histories (load/save/append/clear)
- Lucy, Lorenzo, Gregory, Coach, Dev, Monica, Sister Mary: `load_*_history`, `save_*_history`, `append_*_messages`, `clear_*_history`; `_archive_history_file`, `_safe_clear`

### Thank-you reminders
- `load_thankyou_reminders`, `save_thankyou_reminders`, `pending_thankyou_reminders`, `due_thankyou_reminders`, `due_thankyou_reminders_for`

### Assignments / gradebook
- `load_assignment_analyses`, `save_assignment_analyses`, `add_assignment_analysis`, `update_assignment_analysis`, `delete_assignment_analysis`
- `percent_to_letter`, `letter_to_gpa`, `school_year_for_date`, `load_gradebook`, `save_gradebook`, `add_gradebook_entry`, `update_gradebook_entry`, `delete_gradebook_entry`, `gradebook_for_child`

### Recipes
- `load_recipes`, `save_recipes`, `get_recipe_by_id`, `save_recipe`, `add_recipe`, `delete_recipe`, `search_recipes`

### Lorenzo planning session
- `load_planning_session`, `save_planning_session`, `start_planning_session`, `advance_planning_session`, `clear_planning_session`, `planning_session_summary`

### Curriculum
- `load_monthly_planner`, `load_curriculum`, `save_curriculum`, `get_curriculum_week`, `get_curriculum_subjects`, `week_day_segments`, `resolve_week_text`, `get_curriculum_week_assignments`, `subject_meeting_days`, `subject_day_index`, `advance_curriculum_cursor`
- `load_curriculum_library`, `save_curriculum_library`, `get_subject_by_id`, `get_assignments_for_student`
- `load_student_submissions`, `save_student_submissions`, `add_student_submission`, `get_submissions_for_grading`, `get_submissions_by_student`
- `load_grading_history`, `save_grading_history`, `add_grade_record`
- `load_curriculum_documents`, `save_curriculum_documents`, `add_curriculum_document`

### Family memory
- `load_family_memory`, `save_family_memory`, `add_memory`, `update_memory`, `delete_memory`, `find_memory_conflicts`, `get_memory_context_block`

### Prayer / pope / novenas
- `load_prayer_intentions`, `save_prayer_intentions`, `add_daily_intention`, `add_repeating_intention`, `add_novena`, `get_active_intentions_for_date`, `check_upcoming_novenas`
- `load_pope_intentions`, `save_pope_intentions`, `get_pope_intention_for_month`

### Meals (Phase E + existing)
- `load_pantry_staples`, `save_pantry_staples` — pantry staples
- `load_meal_history`, `save_meal_history`, `add_meal_history_entry`, `get_recent_meals` — meal history
- `load_meal_wizard_session`, `save_meal_wizard_session`, `clear_meal_wizard_session`, **`update_meal_wizard_session`** — wizard session state (shallow-merge)  ← **Phase E**

---

## Section 6 — config.py constants

```
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8000))

# Core data files
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

# Day templates
DAY_TEMPLATES_DIR         = "data/day_templates"
DAY_TEMPLATES_PREVIEW_DIR = "data/day_templates_preview"
DAY_TEMPLATES_BACKUP_DIR  = "data/day_templates_backups"
SEASONAL_SCHEDULES_FILE   = "data/seasonal_schedules.json"

# Meal-wizard (six constants)
MEALS_DIR                = "data/meal_plan"
MEAL_RULES_FILE          = "data/meal_rules.json"
MEAL_INVENTORY_FILE      = "data/meal_inventory.json"
PANTRY_STAPLES_FILE      = "data/pantry_staples.json"
MEAL_HISTORY_FILE        = "data/meal_history.json"
MEAL_WIZARD_SESSION_FILE = "data/meal_wizard_session.json"

# Enums / ordering
VALID_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}
VALID_STATUSES   = {"active", "done", "inactive"}
WEEKDAYS      = ["Monday", … "Sunday"]
WEEKDAY_ORDER = {day: i for i, day in enumerate(WEEKDAYS)}
SCHEDULE_DAYS = ["Monday", … "Saturday"]
MONTH_NAMES   = [ … ]
ROADMAP_STATUSES = ["Someday", "Ready", "In Progress", "Done"]
ASSIGNABLE_TO    = ["Mom"] + list(CHILDREN)   # CHILDREN imported from daily_schedule_engine

# Colors (loaded from app_settings.json with defaults)
CHILD_COLORS  = _load_child_colors()
_DEFAULT_CHILD_COLORS  = { … }
_DEFAULT_PARENT_COLORS = { … }

# Van rotation
VAN_ROTATION_EPOCH = _load_van_epoch()
VAN_ROLE_A = "Interior Reset Lead"
VAN_ROLE_B = "Bin & Organization Lead"
```

All six meal-wizard constants are present (`MEALS_DIR`, `MEAL_RULES_FILE`,
`MEAL_INVENTORY_FILE`, `PANTRY_STAPLES_FILE`, `MEAL_HISTORY_FILE`,
`MEAL_WIZARD_SESSION_FILE`). `CHILDREN` is imported from
`daily_schedule_engine` (family identity stays out of hardcoded config per Rule 19).

---

## Section 7 — Current claud.md rules (full text, verbatim from disk)

Reproduced verbatim (byte-for-byte) from `claud.md`. Rules 1–12 are the "Python 3.11 hard rules"; rules 13–19 are the "Additional rules" section.

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

## Phase E confirmation checklist

- ✅ GET `/meal-wizard` and `/meal-wizard-step2` both present in `do_GET`
- ✅ POST `/pantry-staples-save`, `/meal-save-inventory`, `/meal-wizard-step2-save` all present in `do_POST`
- ✅ `pantry_staples.json`, `meal_history.json`, `meal_wizard_session.json` not yet on disk (lazily created on first save) — `meal_inventory.json` exists
- ✅ `render_meal_wizard.py` includes `render_pantry_staples_page`, `render_meal_wizard_week_glance`, `render_meal_wizard_step2`
- ✅ `data_helpers.py` includes `get_merged_calendar_events` and the meal-wizard session/history/pantry helpers (incl. `update_meal_wizard_session`)
- ✅ All six meal-wizard constants present in `config.py`
- ✅ `static/inventory_input.js` defines `window.toggleMic`, `window.parseInventory`, `window.saveInventory`, `window.clearInventory`, `window.saveInventoryWizard`
- ✅ Step 2 Save button → `saveInventoryWizard()` (POSTs `/meal-wizard-step2-save`); meals page → `saveInventory()` (POSTs `/meal-save-inventory`)
