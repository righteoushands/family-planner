# PROJECT_STATE.md — Sancta Familia
Technical snapshot of the current codebase. Read at the start of future
sessions for a fast orientation. Generated 2026-06-11.

> Counts as of this snapshot: 97 exact-match + 16 prefix (`startswith`) GET routes in `do_GET`; 207 POST routes in `do_POST`; 57 render modules; 211 functions in `data_helpers.py`.

---

## Section 1 — GET routes (defined in app.py `do_GET`)

Per Rule 3, all GET routing uses `elif` chains in `do_GET`.

### 1a. Exact-match routes (`path == "…"`)

| Path | Renders / returns |
|---|---|
| `/login` | (inline) |
| `/logout` | redirect /login |
| `/quest-sso` | (inline) |
| `/change-pin` | render: _render_change_pin_page() |
| `/` | render: render_timeblock_homepage() |
| `/today` | render: render_today_all() |
| `/programs` | render: render_programs_page() |
| `/set-school-mode` | calls clean_text() |
| `/now` | render: render_now_page() |
| `/week` | render: render_week_view() |
| `/week-school` | render: render_week_school_page() |
| `/school` | render: render_school_page() |
| `/api/today-progress` | calls clean_text() |
| `/api/boys-tasks` | JSON response |
| `/api/child-tasks` | JSON response |
| `/gdrive-files` | JSON response |
| `/kids-week` | render: render_kids_week_page() |
| `/plan-tomorrow` | render: render_plan_tomorrow_page() |
| `/plan-today` | render: render_plan_tomorrow_page() |
| `/plan-week` | render: render_plan_week_page() |
| `/plan-month` | render: render_plan_month_page() |
| `/plan-year` | render: render_plan_year_page() |
| `/plan-quarter` | render: render_plan_quarter_page() |
| `/virtues` | render: render_virtues_dashboard() |
| `/5am` | render: render_5am_page() |
| `/liturgy-hours` | render: render_liturgy_hours_page() |
| `/prayer-intentions` | render: render_prayer_page() |
| `/virtues/me` | render: render_virtue_me_page() |
| `/virtues/family` | render: render_virtue_family_page() |
| `/school/edit` | render: render_school_edit_page() |
| `/chores` | render: render_chores_page() |
| `/van-roles` | render: render_van_roles_page() |
| `/print/day` | (inline) |
| `/print/week` | render: render_print_week() |
| `/notes` | render: render_notes() |
| `/tasks` | render: render_tasks() |
| `/thankyou-reminders` | render: render_thankyou_page() |
| `/mom` | render: render_mom_page() |
| `/mom-profile` | render: render_mom_profile_page() |
| `/john` | render: render_john_page() |
| `/friends` | render: render_friends_page() |
| `/roadmap` | render: render_roadmap_page() |
| `/signup` | render: render_signup_page() |
| `/waitlist` | render: render_waitlist_admin() |
| `/family-schedule` | render: render_family_schedule_page() |
| `/frol-pdf` | calls generate_frol_pdf() |
| `/school-week-pdf` | calls generate_school_pdf() |
| `/calendar` | render: render_calendar_page() |
| `/planner` | render: render_planner_page() |
| `/readings` | render: render_readings_page() |
| `/lucy` | calls render_lucy_page() |
| `/lorenzo-plan-state` | calls load_planning_session() |
| `/lorenzo` | calls render_lorenzo_page() |
| `/headmaster` | calls render_gregory_page() |
| `/coach` | calls render_coach_page() |
| `/dr-monica` | calls render_monica_page() |
| `/companions` | calls render_companions_page() |
| `/wizards` | calls render_wizards_page() |
| `/pantry-staples` | calls render_pantry_staples_page() |
| `/meal-wizard` | calls clean_text() |
| `/sister-mary` | calls render_sister_mary_page() |
| `/frol-grid-fragment` | (inline) |
| `/frol-seasonal-view` | redirect / |
| `/frol-wizard` | redirect / |
| `/daily-mass` | calls resolve_daily_mass_url() |
| `/plan-import-history` | redirect / |
| `/grades` | redirect / |
| `/subject` | redirect / |
| `/hour-report` | calls bool() |
| `/curriculum` | redirect / |
| `/gradebook` | redirect / |
| `/assignment-analyzer` | redirect / |
| `/assignment-image` | redirect / |
| `/plan-import` | redirect / |
| `/dev` | redirect / |
| `/dev-logs` | (inline) |
| `/dev-health` | (inline) |
| `/dev-diag` | (inline) |
| `/dev-read-file` | (inline) |
| `/dev-grep-files` | (inline) |
| `/dev-git-log` | (inline) |
| `/dev-git-diff` | (inline) |
| `/memory-book` | render: render_memory_book_page() |
| `/liturgical` | render: render_liturgical_page() |
| `/prayer` | render: render_liturgical_page() |
| `/liturgical/edit` | render: render_liturgical_edit_page() |
| `/settings` | render: render_settings_page() |
| `/history` | render: render_history_page() |
| `/history/preview` | calls load_snapshot_data() |
| `/plan-fragment` | calls clean_text() |
| `/grid-print` | calls clean_text() |
| `/mom-step` | calls clean_text() |
| `/meals` | calls clean_text() |
| `/meal-print` | calls clean_text() |
| `/recipes` | render: render_recipes_page() |
| `/api-key` | calls load_app_settings() |
| `/calendar/refresh` | redirect /calendar |

### 1b. Prefix routes (`path.startswith("…")`)

| Path prefix | Renders / returns |
|---|---|
| `/quest` | (inline) |
| `/static/js/` | (inline) |
| `/static/images/` | (inline) |
| `/static/` | (inline) |
| `/prayer-photo/` | (inline) |
| `/prayer-intention/share/` | render: render_share_page() |
| `/virtues/child/` | render: render_virtue_child_page() |
| `/print/day/` | render: render_print_lauren_day() |
| `/uploads/recipes/` | (inline) |
| `/uploads/grades/` | (inline) |
| `/uploads/grade_docs/` | (inline) |
| `/schedule/` | render: render_child_schedule() |
| `/student/` | calls next() |
| `/grades/` | calls next() |
| `/lucy-child-brief/` | (inline) |
| `/lucy-prayer-brief/` | (inline) |

New on June 10–11: `/wizards`, `/pantry-staples`, `/meal-wizard` (all present above).

---

## Section 2 — POST routes (defined in app.py `do_POST`)

Per Rule 3, POST routing uses standalone `if path == ...: ... return` blocks at the top level of `do_POST`.

| Path | Effect |
|---|---|
| `/quest` (prefix) | calls int() |
| `/login` | calls int() |
| `/student-message-read` | calls set_viewer() |
| `/message-mom` | calls set_viewer() |
| `/change-pin` | calls set_viewer() |
| `/messages-read` | calls set_viewer() |
| `/save-pins` | calls set_viewer() |
| `/pantry-staples-save` | calls int() |
| `/plan-import-save-session` | calls int() |
| `/plan-import-history-delete` | redirect /plan-import-history |
| `/subject-upload-image` | calls parse_multipart_form() |
| `/subject-doc-upload` | calls parse_multipart_form() |
| `/subject-send-to-mom` | calls parse_urlencoded_body() |
| `/subject-link-add` | calls add_manual_entry() |
| `/subject-grade-add` | calls add_manual_entry() |
| `/subject-grade-delete` | calls delete_entry() |
| `/subject-link-delete` | calls delete_link() |
| `/subject-doc-delete` | calls delete_document() |
| `/assignment-analyze` | (inline) |
| `/assignment-update` | calls update_assignment_analysis() |
| `/assignment-delete` | calls delete_assignment_analysis() |
| `/assignment-reply` | calls clean_text() |
| `/gradebook-add` | (inline) |
| `/gradebook-update` | calls clean_text() |
| `/gradebook-delete` | calls delete_gradebook_entry() |
| `/school-upload` | calls clean_child() |
| `/prayer-intention-add` | calls clean_text() |
| `/recipe-import` | (inline) |
| `/recipe-save` | (inline) |
| `/toggle-task` | calls get_task_done() |
| `/schedule-template-save` | calls clean_child() |
| `/add-note` | redirect /notes#top |
| `/archive-note` | redirect /notes#top |
| `/convert-note` | redirect /notes |
| `/add-task` | calls clean_text() |
| `/task-update` | calls clean_text() |
| `/task-done` | calls clean_text() |
| `/task-delete` | calls clean_text() |
| `/task-hard-delete` | redirect /tasks#top |
| `/task-purge-inactive` | redirect /tasks#top |
| `/task-override` | calls next() |
| `/thankyou-add` | calls clean_text() |
| `/exercise-log` | (inline) |
| `/thankyou-done` | calls save_thankyou_reminders() |
| `/thankyou-dismiss` | calls save_thankyou_reminders() |
| `/thankyou-suggest` | calls clean_text() |
| `/approve-school-preview` | redirect /school#top |
| `/approve-school-week` | calls _aw_load() |
| `/regenerate-school-week` | redirect / |
| `/reparse-school-preview` | calls save_school_preview() |
| `/save-school-preview-edits` | calls clean_child() |
| `/save-chores` | (inline) |
| `/apply-laundry` | redirect /chores?msg=Laundry+schedule+applied+to+weekly+chores#top |
| `/signup-submit` | calls clean_text() |
| `/waitlist` | redirect /van-roles#top |
| `/apply-van-rotation` | redirect /van-roles#top |
| `/mom-add-note` | redirect /mom#top |
| `/history-restore` | redirect /history?msg= |
| `/plan-add-item` | calls add_item_to_plan() |
| `/plan-toggle-item` | calls clean_text() |
| `/plan-item-update` | calls clean_text() |
| `/anchor-save` | calls clean_text() |
| `/grid-save-template` | calls save_day_template() |
| `/grid-push-weekly` | calls save_day_template() |
| `/grid-cell-save` | calls save_day_grid() |
| `/grid-publish` | calls clean_text() |
| `/grid-reset` | calls save_day_grid() |
| `/plan-ai-suggest` | calls clean_text() |
| `/memory-book-save` | calls add_memory_entry() |
| `/memory-book-delete` | calls delete_memory_entry() |
| `/lucy-tts` | calls clean_text() |
| `/lucy-rule-save` | calls clean_text() |
| `/lucy-chat` | calls clean_text() |
| `/lucy-clear-history` | redirect /lucy |
| `/lorenzo-chat` | calls clean_text() |
| `/lorenzo-rule-save` | calls clean_text() |
| `/lorenzo-plan-start` | calls clear_lorenzo_history() |
| `/lorenzo-plan-end` | calls clear_planning_session() |
| `/lorenzo-clear-history` | redirect /lorenzo |
| `/headmaster-chat` | (inline) |
| `/headmaster-clear-history` | redirect /headmaster |
| `/coach-chat` | (inline) |
| `/coach-clear-history` | redirect /coach |
| `/programs-save` | redirect /programs?focus= |
| `/programs-delete` | redirect /programs?focus= |
| `/programs-edit` | calls clean_text() |
| `/dev-chat` | (inline) |
| `/dev-apply` | calls clean_text() |
| `/dev-write` | calls clean_text() |
| `/dev-undo` | (inline) |
| `/dev-restart` | (inline) |
| `/dev-clear` | redirect / |
| `/dr-monica-chat` | (inline) |
| `/dr-monica-clear-history` | redirect /dr-monica |
| `/hour-log-add` | calls bool() |
| `/hour-log-edit` | calls bool() |
| `/hour-log-delete` | calls bool() |
| `/sister-mary-chat` | (inline) |
| `/frol-save-seasonal` | calls int() |
| `/frol-seasonal-use` | (inline) |
| `/frol-seasonal-delete` | redirect /frol-wizard |
| `/frol-overlay-toggle` | calls _lj3() |
| `/frol-overlay-set` | calls _lj4() |
| `/frol-overlay-clear` | calls _lj5() |
| `/pod-dismiss-season` | calls int() |
| `/frol-wizard` | (inline) |
| `/frol-wizard-chat` | calls get_anthropic_key() |
| `/frol-wizard-finalize` | redirect /frol-wizard |
| `/frol-set-variant` | (inline) |
| `/frol-rollback-v3` | (inline) |
| `/frol-add-activity` | calls int() |
| `/frol-edit-activity` | calls int() |
| `/frol-delete-activity` | calls int() |
| `/sister-mary-clear-history` | redirect /sister-mary |
| `/timeblock-add-intention` | calls add_daily_intention() |
| `/timeblock-add-novena` | calls add_novena() |
| `/memory-update` | (inline) |
| `/curriculum-parse` | calls clean_text() |
| `/curriculum-save` | calls str() |
| `/curriculum-minutes` | calls str() |
| `/poetry-passage-save` | calls load_poetry_passages() |
| `/curriculum-week` | calls save_curriculum() |
| `/curriculum-subject-week` | calls clean_text() |
| `/curriculum-subject-day` | calls clean_text() |
| `/curriculum-delete` | calls save_curriculum() |
| `/plan-import-analyze` | (inline) |
| `/plan-import-apply` | calls int() |
| `/plan-import-undo-placement` | calls int() |
| `/plan-import-consult` | calls clean_text() |
| `/plan-import-group-consult` | calls clean_text() |
| `/api/extract-suggestions` | calls clean_text() |
| `/calendar-config-save` | redirect /calendar#top |
| `/calendar-save-config` | redirect /calendar#top |
| `/planner-add-task` | redirect /planner#top |
| `/subscribed-cal-add` | redirect /calendar#top |
| `/subscribed-cal-toggle` | redirect /settings#s-integrations |
| `/subscribed-cal-delete` | redirect /calendar#top |
| `/calendar-refresh` | redirect /calendar#top |
| `/family-schedule-save` | calls clean_text() |
| `/settings-schedule-save` | calls clean_text() |
| `/roadmap-add` | redirect /roadmap#top |
| `/roadmap-update` | redirect /roadmap#top |
| `/roadmap-delete` | redirect /roadmap#top |
| `/liturgical-save` | redirect /liturgical#top |
| `/liturgical-delete` | redirect /liturgical#top |
| `/liturgical-note` | redirect /liturgical#top |
| `/settings-save-ajax` | calls load_app_settings() |
| `/settings-save` | calls load_app_settings() |
| `/school-settings-save` | calls load_app_settings() |
| `/child-goal-add` | calls add_child_goal() |
| `/child-goal-archive` | calls update_child_goal() |
| `/child-substep-add` | calls add_substep() |
| `/child-substep-toggle` | calls clean_text() |
| `/child-substep-delete` | calls delete_substep() |
| `/calendar-add-event` | calls clean_text() |
| `/calendar-event-delete` | calls save_calendar_cache() |
| `/cycle-log-add` | calls clean_text() |
| `/cycle-log-delete` | calls clean_text() |
| `/add-to-plan-quick` | calls add_item_to_plan() |
| `/cycle-ai-suggest` | calls clean_text() |
| `/cycle-save` | calls clean_text() |
| `/meal-save-plan` | calls clean_text() |
| `/kids-week-save` | calls save_week_plan() |
| `/meal-rule-add` | calls clean_text() |
| `/meal-rule-delete` | calls int() |
| `/meal-save-inventory` | calls save_inventory() |
| `/meal-generate` | calls save_inventory() |
| `/meal-save-constraints` | calls save_meal_plan() |
| `/meal-edit` | calls clean_text() |
| `/recipe-delete` | redirect /recipes |
| `/plan-week-save` | calls save_intentions_data() |
| `/plan-month-save` | calls save_month_plan() |
| `/quarter-save-goals` | calls save_quarter_plan() |
| `/save-mom-profile` | calls save_mom_profile() |
| `/save-john-profile` | calls save_john_profile() |
| `/save-friend` | calls clean_text() |
| `/delete-friend` | calls save_friends() |
| `/save-child-profile` | calls save_child_profile() |
| `/quarter-journal-save` | calls clean_text() |
| `/quarter-save-step` | calls update_weekly_step() |
| `/quarter-checkin` | calls clean_text() |
| `/goal-add` | calls add_master_goal() |
| `/virtue-checkin` | calls clean_text() |
| `/prayer-intention-delete` | calls save_intentions() |
| `/prayer-intention-log` | calls clean_text() |
| `/prayer-intention-complete` | calls clean_text() |
| `/liturgy-hours-save` | calls save_day_hours() |
| `/5am-save` | calls clean_text() |
| `/plan-tomorrow-questions` | calls clean_text() |
| `/plan-tomorrow-generate` | calls clean_text() |
| `/plan-tomorrow-push` | calls clean_text() |
| `/ai-daily-schedule` | calls clean_text() |
| `/ai-meal-plan` | calls clean_text() |
| `/ai-school-plan` | calls clean_text() |
| `/ai-evening-examen` | calls clean_text() |
| `/ai-weekly-review` | calls clean_text() |
| `/ai-chore-adjust` | calls clean_text() |
| `/ai-intention-prayer` | calls clean_text() |
| `/ai-capacity-preview` | calls clean_text() |
| `/ai-week-brief` | calls load_app_settings() |
| `/ai-month-brief` | calls load_app_settings() |
| `/ai-year-brief` | calls load_app_settings() |
| `/ai-suggest-goals` | calls load_app_settings() |
| `/ai-generate-steps` | calls clean_text() |
| `/preview-keep` | (inline) |
| `/preview-discard` | (inline) |
| `/pod-toggle-traveling` | calls set_john_traveling() |

New on June 10–11: `/pantry-staples-save` (present above).

---

## Section 3 — Data files (`data/*.json`)

| File | Size (bytes) | Stores |
|---|---|---|
| `_undo_smoke_test.json` | 21 | Test fixture (undo smoke test) |
| `app_settings.json` | 2,570 | Global app settings, family identity, AI API key, theme, location |
| `assignment_analyses.json` | 17,085 | AI assignment-analyzer structured results |
| `calendar_cache.json` | 2,587 | iCloud/CalDAV fetched events cache |
| `calendar_config.json` | 62 | iCloud/CalDAV connection config (Apple ID) |
| `calendar_rules.json` | 64 | Calendar display rules (blocked event titles) |
| `chores.json` | 9,049 | Chore definitions and weekly assignments |
| `coach_history.json` | 43,857 | Coach AI chat history |
| `coach_last_writes.json` | 270 | Coach undo: last data-altering actions |
| `coach_programs.json` | 3,516 | Coach saved fitness programs |
| `curriculum.json` | 423,328 | Homeschool curriculum data (large) |
| `cycle_log.json` | 236 | Cycle/health tracking log |
| `dev_history.json` | 16,675 | Izzy (dev companion) chat history |
| `events.json` | 30,710 | Manual calendar events (local source of truth) |
| `exercise_assignments.json` | 2,214 | Weekly per-person exercise assignments |
| `exercise_logs.json` | 665 | Exercise completion logs |
| `family_memory.json` | 2 | Shared family memory store |
| `felix_undo.json` | 137,831 | Undo snapshots |
| `friends.json` | 1,195 | Friends/contacts records |
| `frol_activities.json` | 15,933 | FROL (Rule of Life) activity library |
| `frol_activities.v2_backup.json` | 5,443 | Backup of FROL activities (v2) |
| `frol_wizard_progress.json` | 16,156 | FROL wizard saved progress/sections |
| `frol_wizard_progress.v2_backup.json` | 138 | Backup of FROL wizard progress (v2) |
| `gradebook.json` | 934 | Gradebook entries |
| `grades.json` | 99 | Grade records |
| `gregory_history.json` | 49,281 | Father Gregory AI chat history |
| `gregory_last_writes.json` | 272 | Gregory undo: last data-altering actions |
| `hour_tracking.json` | 138 | Homeschool hour tracking |
| `kid_messages.json` | 2 | Kid-to-parent messages |
| `liturgical.json` | 2 | Custom liturgical day overrides |
| `lorenzo_history.json` | 28,919 | Lorenzo (chef) AI chat history |
| `lorenzo_last_writes.json` | 114 | Lorenzo undo: last data-altering actions |
| `lucy_history.json` | 28,223 | Lucy AI chat history |
| `lucy_last_writes.json` | 98 | Lucy undo: last data-altering actions |
| `manual_tasks.json` | 32,195 | Manually added tasks |
| `meal_inventory.json` | 917 | Meal/pantry inventory for meal planning |
| `meal_rules.json` | 3,316 | Meal rules (dietary/scheduling constraints) |
| `memory_book.json` | 789 | Memory book entries |
| `mom_notes.json` | 236 | Mom's notes |
| `monica_history.json` | 18,696 | Dr. Monica AI chat history |
| `monthly_planner.json` | 10,127 | Monthly planner data |
| `notes.json` | 3,999 | General notes |
| `plan_import_history.json` | 193,577 | Plan Importer history (large) |
| `planning_session.json` | 21 | Active Lorenzo planning session state |
| `poetry_passages.json` | 152 | Saved poetry passages for curriculum |
| `pope_intentions.json` | 1,654 | Pope's monthly prayer intentions |
| `prayer_intentions.json` | 1,116 | Family prayer intentions |
| `progress.json` | 203,939 | Task completion progress (compound keys) — largest data file |
| `recipes.json` | 44,517 | Recipe library |
| `roadmap.json` | 1,121 | Product/family roadmap items |
| `school_previews.json` | 52,442 | School week preview drafts (pre-approval) |
| `school_week_plan.json` | 58,290 | Current school week plan |
| `school_weeks.json` | 99,033 | Historical school weeks |
| `seasonal_schedules.json` | 2 | Saved seasonal FROL schedules |
| `sister_mary_history.json` | 9,298 | Sister Mary AI chat history |
| `subscribed_calendar_cache.json` | 25,618 | Subscribed iCal feed events cache |
| `subscribed_calendars.json` | 1,933 | Subscribed iCal calendar configs (name/url/color/enabled) |
| `task_overrides.json` | 15,844 | Per-date task overrides |
| `task_registry.json` | 18,949 | Task registry/definitions |
| `thankyou_reminders.json` | 259 | Thank-you note reminders |

**Meal-wizard data files declared in config but not yet written to disk** (created lazily on first save):
- `data/pantry_staples.json` — NOT present on disk yet
- `data/meal_history.json` — NOT present on disk yet
- `data/meal_wizard_session.json` — NOT present on disk yet

(Numerous subdirectories also exist under `data/` — e.g. `day_templates/`, `profiles/`, `meal_plan/`, `goals/`, `virtues/`, `history/`, `auth/`, `assignment_uploads/`, `hour_reports/`, plus `*.archive/` and `*_backups/` dirs.)

---

## Section 4 — Render modules (`render_*.py`)

| Module | Lines | Functions |
|---|---|---|
| `render_5am.py` | 721 | `_ensure_dir`, `load_day`, `save_day`, `_streak`, `_week_dots`, `_journal_prompt`, `_current_virtue`, `_goal_step_for_category`, `_current_book`, `render_5am_dashboard_widget`, `render_5am_page`, `_section_card` |
| `render_ai_daily.py` | 406 | `_api_key`, `_call_claude`, `_constraints`, `_season`, `_format_html`, `ai_daily_schedule`, `ai_meal_plan`, `ai_school_plan`, `ai_evening_examen`, `ai_weekly_review`, `ai_chore_adjust`, `ai_intention_prayer` |
| `render_ai_planner.py` | 461 | `build_context_packet`, `render_ai_panel` |
| `render_assignment_analyzer.py` | 676 | `_fmt_ts`, `_resolved`, `_record_grade_block`, `_render_one_card`, `render_assignment_analyzer_page` |
| `render_calendar.py` | 975 | `fetch_caldav_events`, `get_or_create_family_calendar`, `_ical_escape`, `_parse_app_time`, `_invalidate_family_calendar_cache`, `write_caldav_event`, `_do_refresh_calendar`, `refresh_calendar`, `fetch_ics_events`, `_do_refresh_subscribed`, `_apply_calendar_event_filters`, `refresh_subscribed_calendars`, `events_for_date`, `get_all_events`, `render_event_pill`, `render_calendar_today_strip`, `render_calendar_page` |
| `render_child_goals.py` | 351 | `_child_key`, `_goals_path`, `load_child_goals`, `save_child_goals`, `add_child_goal`, `update_child_goal`, `add_substep`, `toggle_substep`, `delete_substep`, `_deadline_badge`, `_substep_progress_bar`, `render_child_goals_section` |
| `render_child_profile.py` | 329 | `_profile_path`, `load_child_profile`, `save_child_profile`, `profile_summary_for_lucy`, `render_child_profile_section` |
| `render_chores.py` | 837 | `_bucket_lines_to_text`, `_render_extra_chore_buckets`, `get_kitchen_roles`, `apply_canonical_chores`, `apply_laundry_defaults`, `get_vacuum_week`, `get_wipe_week`, `get_van_week_number`, `get_van_roles`, `_role_b_tasks_this_week`, `get_van_chore_lines`, `apply_van_rotation`, `render_van_roles_card`, `render_van_roles_page`, `_render_chore_status_today`, `render_chores_page` |
| `render_coach.py` | 599 | `_ej`, `_today_eastern`, `_hour_eastern`, `_load_coach_history_safe`, `_get_anchor_context_coach`, `_get_cycle_context_coach`, `build_coach_context`, `render_coach_page` |
| `render_companions.py` | 54 | `render_companions_page` |
| `render_curriculum.py` | 858 | `_get_openai_key`, `_recommended_minutes`, `render_recent_submissions_widget`, `_parse_modg_locally`, `_parse_with_ai`, `parse_modg_paste`, `render_curriculum_page` |
| `render_daily_bar.py` | 414 | `_load`, `get_location`, `get_child_birthdays`, `get_special_events`, `_fetch_weather_background`, `_populate_weather_cache`, `fetch_weather`, `get_child_age`, `render_child_age_strip`, `get_todays_special_events`, `render_daily_bar` |
| `render_daily_plan.py` | 870 | `_plan_path`, `load_daily_plan`, `save_daily_plan`, `seed_from_grid`, `get_or_seed_plan`, `add_item_to_plan`, `toggle_plan_item`, `delete_plan_item`, `reorder_plan_items`, `update_item_time`, `sort_plan_chronologically`, `publish_plan`, `reset_plan`, `_grid_path`, `_meta_path`, `load_day_grid`, `save_day_grid`, `is_grid_published`, `publish_day_grid`, `_slots_for_person`, `_build_person_row`, `seed_day_grid`, `get_or_seed_grid`, `_template_path`, `save_day_template`, `_get_plan_column_people`, `render_add_to_plan_btn`, `_dp_row_html`, `_render_family_grid`, `render_plan_editor`, `render_plan_fragment_html`, `render_dashboard_plan`, `render_dashboard_grid`, `render_grid_print_page` |
| `render_dev.py` | 1418 | `_get_relevant_files`, `_app_overview`, `_file_listing`, `build_felix_context`, `render_dev_page`, `_clean_user_history`, `_user_bubble`, `_felix_bubble`, `_welcome_bubble` |
| `render_friends.py` | 570 | `load_friends`, `save_friends`, `_member_html`, `_tag_list_html`, `_plan_list_html`, `_family_card_html`, `render_friends_page` |
| `render_frol_pdf.py` | 177 | `_to_minutes`, `_load_day_grid`, `_all_times`, `_xml_escape`, `generate_frol_pdf` |
| `render_frol_wizard.py` | 7681 | `_empty_progress`, `_seed_v3_activities_from_progress`, `load_progress`, `save_progress`, `reset_progress`, `is_complete`, `is_dismissed`, `save_field`, `advance_step`, `has_anthropic_key`, `get_anthropic_key`, `derive_heuristic_notes`, `_age_bucket`, `_progress_dots`, `render_section_dots`, `render_reflection_card`, `render_companion_intro_card`, `render_lucy_hint_slot`, `render_activity_builder`, `_activity_row_html`, `_step_chrome`, `_render_chat_panel`, `_migrate_v1_to_v2`, `save_section_field`, `advance_section`, `_sv`, `_section_chrome`, `_category_color`, `_safe_color`, `_category_label`, `_activity_persons`, `_fmt_time_12h`, `_render_activity_edit_form`, `_render_activity_card`, `_render_activity_list`, `_grid_time_label`, `_grid_parse_hhmm`, `_grid_activity_placements`, `_grid_visible_persons`, `_grid_chip_html`, `_grid_build_table`, `_seasonal_overlay_state`, `_render_grid_preview`, `_render_grid_preview_fragment`, `_render_activity_builder`, `_v2_members`, `render_section_1`, `render_section_2`, `render_section_3`, `render_section_4`, `render_section_5`, `render_section_6`, `_seed_chores_for_section7`, `_chore_item_text`, `_bucket_textarea`, `render_section_7`, `render_section_8`, `render_section_9`, `render_section_10`, `_holiday_card`, `_rule_card`, `render_section_11_holidays`, `_active_variant`, `_render_variant_tab_bar`, `_render_phase_c_block`, `_timeline_slots`, `_slot_to_label`, `_slugify_activity`, `_collect_duration_targets`, `render_section_11`, `_s12_migrate_per_variant`, `_s12_bucket`, `_s12_filter_activities_by_variant`, `_s12_collect_context`, `_s12_progress_hash`, `_s12_repair_json`, `_s12_call_anthropic_json`, `_s12_generate_questions`, `_s12_generate_schedule`, `s12_persist_kept_to_activities`, `_s15_hhmm24_to_label12`, `_s15_build_grid_from_schedule`, `s15_write_variants_to_dir`, `s15_backup_permanent`, `s15_preview_active`, `s15_discard_preview`, `s15_promote_preview_to_permanent`, `john_traveling_enabled`, `set_john_traveling`, `pod_template_stem`, `pod_template_dir`, `get_pod_day_slots`, `render_section_12`, `_commitments_status`, `render_section_13`, `_parse_textarea_lines`, `_slot_to_label_12h`, `finalize_v2`, `render_section_14`, `_section_renderer`, `_section_placeholder`, `_v`, `_settings_members`, `render_landing`, `_render_save_seasonal_card`, `_render_landing_seasonal_awareness_card`, `_render_seasonal_library_section`, `render_seasonal_view_page`, `render_step_1`, `render_step_2`, `render_step_3`, `_checkbox_group`, `_yesno_opts`, `render_step_4`, `render_step_5`, `render_step_6`, `render_step_7`, `render_step_8`, `render_step_9`, `_row_sort_minutes`, `_fmt_12h`, `_build_person_summaries`, `_missing_step_buckets`, `_missing_steps_prompt`, `render_step_10`, `_detect_gaps`, `render_completion_screen`, `render_frol_wizard_page`, `render_frol_setup_card`, `build_wizard_chat_context`, `finalize_wizard`, `_generate_scheduling_suggestions`, `_to_slot_label` |
| `render_goals.py` | 238 | `current_quarter`, `quarter_start`, `quarter_end`, `quarter_week_number`, `quarter_label`, `all_quarters`, `load_master_goals`, `save_master_goals`, `add_master_goal`, `load_quarter_plan`, `save_quarter_plan`, `get_active_goals_with_steps`, `record_weekly_checkin`, `update_weekly_step`, `completion_pct`, `goal_progress_bars` |
| `render_gradebook.py` | 428 | `_fmt_date`, `_avg`, `_all_school_years_for`, `_entry_row_html`, `_subject_section_html`, `render_gradebook_page` |
| `render_gregory.py` | 617 | `_ej`, `_today_eastern`, `_hour_eastern`, `_load_gregory_history_safe`, `_get_liturgical_note`, `_get_school_context`, `_get_curriculum_context`, `_get_child_academic_context`, `_get_anchor_context_gregory`, `build_gregory_context`, `render_gregory_page` |
| `render_john.py` | 433 | `load_john_profile`, `_week_key`, `_load_week_plan`, `_render_john_quicklook`, `save_john_profile`, `_list_section_html`, `render_john_page` |
| `render_kids_week.py` | 455 | `_week_key`, `_week_dates`, `load_week_plan`, `save_week_plan`, `render_kids_week_page` |
| `render_liturgical.py` | 595 | `_easter`, `get_moveable_feasts`, `get_floating_liturgical_events`, `get_liturgical_season`, `is_fast_day`, `is_abstinence_day`, `get_day_info`, `get_vestment_color`, `is_penance_season`, `render_liturgical_day_card`, `render_liturgical_page`, `render_liturgical_edit_page` |
| `render_liturgy_hours.py` | 519 | `_ensure_dir`, `_day_path`, `load_day_hours`, `save_day_hours`, `cleanup_old_files`, `_week_monday`, `_week_already_fetched`, `_get_universalis_country`, `_fetch_office_text`, `fetch_week`, `_fetch_and_clean`, `_next_week_monday`, `maybe_auto_fetch`, `start_weekly_scheduler`, `_current_office`, `render_hours_dashboard_widget`, `render_liturgy_hours_page` |
| `render_login.py` | 313 | `render_login_page` |
| `render_lorenzo.py` | 2199 | `_today_eastern`, `_hour_eastern`, `_ej`, `_load_app_settings`, `_load_lorenzo_history_safe`, `_get_current_meal_plan`, `_get_inventory`, `_get_saved_recipes`, `_get_meal_constraints`, `_get_lucy_capacity`, `_get_john_status`, `_get_liturgical_note`, `_get_calendar_this_week`, `_get_easter`, `_get_planning_session_block`, `build_lorenzo_context`, `_week_sunday`, `render_lorenzo_page` |
| `render_lucy.py` | 3362 | `_now_eastern`, `_today_eastern`, `_get_phase`, `_get_cycle_context`, `_get_school_week_position`, `_get_time_context`, `build_lucy_context`, `_load_lucy_history_safe`, `_render_history_html`, `render_lucy_page`, `escape_js`, `get_mom_lucy_brief`, `get_child_lucy_brief`, `get_prayer_lucy_brief`, `_get_prayer_intentions_brief` |
| `render_meal_wizard.py` | 452 | `_checkbox_list`, `_custom_chips`, `_custom_field`, `_editable_form`, `_first_run_body`, `_returning_body`, `render_pantry_staples_page`, `_wg_safe_color`, `_wg_marker_chip`, `_wg_rules_panel`, `_wg_event_line`, `_wg_day_card`, `render_meal_wizard_week_glance` |
| `render_meals.py` | 1647 | `slot_display_text`, `slot_recipe_id`, `_plan_path`, `_week_key`, `_planning_week_key`, `_week_start`, `load_meal_plan`, `_backup_meal_plan`, `save_meal_plan`, `parse_duration_minutes`, `get_frol_dinner_time`, `get_cook_start_for_day`, `load_inventory`, `save_inventory`, `load_meal_rules`, `_build_meal_prompt`, `render_meal_today_card`, `render_meal_planner_page`, `_cycle_nutrition_hint`, `render_meal_print_page`, `render_recipe_import_preview`, `_seed_default_recipes`, `render_recipes_page`, `_tag_class` |
| `render_memory_book.py` | 210 | `load_memory_book`, `save_memory_book`, `add_memory_entry`, `delete_memory_entry`, `render_memory_book_page` |
| `render_misc.py` | 5977 | `_safe_widget`, `get_this_month_data`, `render_planner_page`, `_render_mom_now_block`, `_render_boys_now_blocks`, `__render_meal_card_safe`, `_render_mom_messages_inbox`, `_render_school_week_review_card`, `render_dashboard`, `render_now_page`, `_render_rule_of_life_strip`, `render_mom_page`, `render_print_lauren_day`, `render_mom_step_fragment`, `_step_header`, `_save_bar`, `_render_spiritual_intentions`, `_render_spiritual_step`, `_render_cycle_step`, `_render_meals_step`, `_render_calendar_step`, `_render_tasks_step`, `_render_kidsday_step`, `_render_evening_step`, `_render_grid_step`, `render_notes`, `_recur_editor_html`, `_recur_editor_js`, `render_tasks`, `render_roadmap_page`, `render_history_page`, `render_school_preview_card`, `render_school_page`, `render_school_edit_page`, `render_thankyou_page` |
| `render_mom_profile.py` | 649 | `_cycle_fertility_banner`, `load_mom_profile`, `save_mom_profile`, `_list_section_html`, `render_lauren_schedule_card`, `render_mom_profile_page` |
| `render_monica.py` | 578 | `_ej`, `_today_eastern`, `_hour_eastern`, `_load_monica_history_safe`, `_get_anchor_context_monica`, `build_monica_context`, `_render_grooming_reminders`, `render_monica_page` |
| `render_morning_anchor.py` | 652 | `fetch_this_day_in_history`, `_get_quote_for_day`, `_get_anchor_state`, `save_anchor_state`, `render_morning_anchor`, `render_evening_anchor` |
| `render_plan_importer.py` | 1121 | `_load_upcoming_events`, `_format_events_summary`, `build_analysis_system_prompt`, `detect_relevant_companions`, `build_consult_system_prompt`, `build_roundtable_prompt`, `render_plan_import_page` |
| `render_plan_month.py` | 667 | `_month_key`, `load_month_plan`, `save_month_plan`, `_month_dates`, `_cycle_forecast`, `render_plan_month_page` |
| `render_plan_quarter.py` | 642 | `render_plan_quarter_page`, `_render_step_grid` |
| `render_plan_tomorrow.py` | 836 | `_gather_tomorrow_data`, `_api_key`, `_call_claude`, `_data_summary_text`, `_last_social_date`, `_save_social_date`, `_days_since_social`, `ai_generate_questions`, `ai_generate_plan`, `_render_data_card`, `_format_plan_html`, `render_plan_tomorrow_page` |
| `render_plan_week.py` | 921 | `_week_key`, `_week_monday`, `_week_dates`, `load_intentions`, `save_intentions_data`, `_cycle_phase`, `_week_feasts`, `_week_events`, `_checkin_btns_html`, `render_plan_week_page` |
| `render_plan_year.py` | 311 | `render_plan_year_page` |
| `render_prayer.py` | 969 | `_ensure_dirs`, `load_intentions`, `save_intentions`, `_update_intention`, `add_intention`, `log_prayer`, `_photo_src`, `_photo_data_uri`, `_prayer_summary`, `_total_prayers`, `_intention_card_small`, `_intention_detail_html`, `render_share_page`, `render_prayer_page`, `render_prayer_dashboard_widget` |
| `render_programs.py` | 458 | `_parse_saved_at`, `_status_for`, `_norm_title`, `_duplicate_title_set`, `_weekly_grid_html`, `_program_card_html`, `_person_section_html`, `_debug_panel_html`, `render_programs_page` |
| `render_readings.py` | 248 | `_readings_cache_path`, `_load_readings_cache`, `_save_readings_cache`, `_clean_reference`, `_fetch_scripture_text`, `fetch_readings_for_date`, `_reading_block`, `render_readings_page` |
| `render_schedule.py` | 2923 | `_js_attr`, `_latest_coach_program_for`, `_slot_time_to_minutes`, `_minutes_to_slot_time`, `_get_exercise_assignment`, `_render_hydration_row_html`, `_post_workout_log_print_line`, `_render_post_workout_log_form`, `_render_exercise_block_screen`, `_render_exercise_block_print`, `_ty_pod_strip`, `_ty_suggested_tasks_widget`, `_collapsible_wrap`, `_item_done`, `is_day_complete`, `count_remaining`, `render_task_list`, `_latin_week_from_text`, `render_confetti_celebration`, `render_day_nav`, `_render_schedule_events_section`, `_dl_kind_color`, `_get_poetry_passage`, `_dl_sub_items_html`, `_render_day_list_html`, `_render_template_editor`, `render_child_schedule_card`, `_render_meal_card_for_child`, `_render_child_goals_section`, `_render_child_profile_section`, `render_child_schedule`, `render_child_dash_card`, `render_today_all`, `render_week`, `print_page_html`, `render_print_child_page`, `_render_meal_print_section`, `render_print_child_day_list`, `render_print_day`, `render_print_week` |
| `render_schedule_support.py` | 226 | `get_eastern_now`, `generate_half_hour_times`, `_slot_minutes`, `get_current_slot`, `render_now_next_strip`, `render_today_timeline`, `render_litany_block`, `render_family_schedule_page` |
| `render_school_pdf.py` | 343 | `_parse_target_date`, `_monday_of_week`, `_week_dates`, `_assignment_text`, `_child_blocks_safe`, `_curriculum_blocks_for_day`, `_build_styles`, `_xml_escape`, `_checklist_row`, `generate_school_pdf` |
| `render_seasons.py` | 147 | `migrate_label`, `_moveable_start`, `season_start`, `_all_starts_for_year`, `upcoming_season`, `current_season` |
| `render_settings.py` | 2292 | `resolve_daily_mass_url`, `load_app_settings`, `save_app_settings`, `_section_general`, `_section_children`, `_section_daily`, `_section_systems`, `_section_integrations`, `_lucy_knowledge_summary`, `_school_mode_section`, `_lucy_rules_section`, `_section_constraints`, `_section_school`, `_accordion`, `_section_pins`, `_section_prayer_sacraments`, `render_settings_page`, `_section_liturgy_hours`, `_section_cycle`, `_section_meals` |
| `render_signup.py` | 516 | `load_waitlist`, `save_signup`, `render_signup_page`, `_render_thankyou`, `render_waitlist_admin` |
| `render_sister_mary.py` | 525 | `_ej`, `_today_eastern`, `_hour_eastern`, `_load_sister_mary_history_safe`, `build_sister_mary_context`, `render_sister_mary_page` |
| `render_student.py` | 678 | `_render_messages_from_mom`, `_recent_school_work`, `_letter_grade_local`, `_render_school_work_section`, `render_student_page`, `_gp4_fmt_date`, `_gp4_pct_to_letter`, `_gp4_norm_gb`, `_gp4_norm_grades`, `_gp4_subject_section`, `render_student_grades` |
| `render_subject.py` | 1402 | `_ensure_dirs`, `load_grades`, `save_grades`, `_node`, `safe_slug`, `_rel_upload`, `_is_music_url`, `_load_curriculum`, `subject_weeks`, `subject_current_week`, `list_subjects`, `_avg`, `subject_averages`, `letter_grade`, `ai_grade_image_gregory`, `_subj_url`, `subject_link`, `render_subject_page`, `_entry_card`, `_render_assignments_tab`, `_render_resources_tab`, `_render_grades_tab`, `_hour_tracking_enabled`, `_render_hours_tab`, `_render_subject_tabs_html`, `render_hour_report`, `render_grades_summary_page`, `add_image_entry`, `mark_entry_sent_to_mom`, `apply_mom_grade`, `add_manual_entry`, `delete_entry`, `add_link`, `delete_link`, `add_document`, `delete_document` |
| `render_timeblock.py` | 2134 | `_now_eastern`, `_resolve_block`, `_unsplash_url`, `_feast_art_url`, `_slugify`, `_is_marian`, `_file_exists`, `_pexels_search`, `_resolve_image`, `_rosary_for`, `_novena_prayer_for`, `_compline_marian_antiphon`, `_accent`, `_card`, `_prose`, `_hour_part`, `_collapsible_card`, `_hour_details`, `_lauds_full_html`, `_terce_full_html`, `_sext_full_html`, `_none_full_html`, `_vespers_full_html`, `_compline_full_html`, `_render_block_prayers`, `_render_intentions_widget`, `_render_novena_prompt`, `_render_frol_snapshot`, `_meal_keys_for_block`, `_week_key_for`, `_meal_prep_bullets`, `_render_meal_row`, `_render_meals_snapshot`, `_upcoming_feast_dates`, `_render_upcoming_feast_notice`, `_get_feast_ai_summary`, `_render_saint_card`, `_render_pope_card`, `_render_daily_mass_link`, `_render_seven_commitments_card`, `_render_seasonal_prompt_card`, `render_timeblock_homepage` |
| `render_virtues.py` | 1058 | `age_band`, `child_age`, `_ensure_dirs`, `load_personal_virtue`, `save_personal_virtue`, `load_family_virtue`, `save_family_virtue`, `load_child_virtue`, `save_child_virtue`, `_current_season`, `_api_key`, `_call_claude`, `generate_virtue_content`, `_fallback_content`, `_virtue_card`, `render_virtue_dashboard_widget`, `render_virtues_dashboard`, `render_virtue_me_page`, `render_virtue_family_page`, `_family_practices`, `render_virtue_child_page` |
| `render_week_school.py` | 567 | `load_poetry_passages`, `save_poetry_passages`, `_week_monday`, `_days_in_week`, `_school_subjects_for_day`, `_registered_school_subjects`, `_subject_marked_done_legacy`, `_progress_done`, `_cell_status`, `_build_child_week`, `_week_stats`, `_child_block_html`, `_render_poetry_passages_card`, `render_week_school_page` |
| `render_week_view.py` | 517 | `_week_key`, `_week_dates`, `_load_json`, `_week_feasts`, `_expand_events`, `_lauren_tasks_this_week`, `_all_tasks_by_day`, `_family_schedule_highlights`, `_priority_dot`, `render_week_view` |
| `render_wizards.py` | 99 | `_active_card`, `_soon_card`, `_wizard_card`, `render_wizards_page` |

New on June 10–11: `render_wizards.py` (`render_wizards_page`) and `render_meal_wizard.py` (`render_pantry_staples_page`, `render_meal_wizard_week_glance`) — present above.

---

## Section 5 — `data_helpers.py` functions (211 total)

Per Rule 19, all data reads/writes flow through `data_helpers.py`.

| Function | Description |
|---|---|
| `list_snapshots` |  |
| `restore_snapshot` |  |
| `load_snapshot_data` |  |
| `today_iso` |  |
| `tomorrow_iso` |  |
| `monday_iso_for` | Return the ISO date of the Monday of the week containing `iso`. |
| `load_school_week_plan` | Return the current weekly school plan blob. {} when file is empty. |
| `save_school_week_plan` |  |
| `generate_weekly_school_plan` | Generate a draft weekly school plan for JP and Joseph. |
| `get_approved_school_week_plan` | Return the plan blob ONLY when it's approved AND for the given week. |
| `normalize_date_query` |  |
| `safe_int` |  |
| `clean_priority` |  |
| `clean_status` |  |
| `clean_child` |  |
| `clean_text` |  |
| `clean_weekday` |  |
| `lines_to_list` |  |
| `count_school_check_items` |  |
| `is_math_subject` |  |
| `is_math_test_text` |  |
| `sort_school_days` |  |
| `load_progress` | Load progress.json — maps task_id -> {done: bool}. |
| `load_manual_tasks` |  |
| `save_manual_tasks` |  |
| `active_manual_tasks` |  |
| `ensure_manual_task_ids` | One-time/idempotent backfill: assign uuid4().hex[:8] to any manual task |
| `_nth_weekday_of_month` | Return the date of the Nth `weekday` (0=Mon..6=Sun) in given month/year. |
| `_add_months` | Add `n` calendar months, clamping the day if the target month is shorter. |
| `_next_specific_weekday` | Find the next date strictly after `base` whose weekday is in |
| `_next_monthly_day` | Next occurrence on day `month_day` of the month (or -1 = last day), |
| `format_recurrence_label` | Human-readable one-line summary of a task's recurrence. |
| `advance_recurring_task` | Given a completed recurring task, return it reset with the next due date. |
| `_ensure_chore_buckets` | Idempotently add daily/weekly/monthly/seasonal/annual buckets to every |
| `load_chores_data` |  |
| `save_chores_data` |  |
| `_resolve_chore_person` | Return the chore bucket for `person` (case-insensitive for Lauren), |
| `get_chores_due_today` | Return the list of chore entries due for `person` on the given date. |
| `get_due_grooming` | Scan every person's chore buckets for entries flagged is_grooming |
| `load_hour_tracking` |  |
| `save_hour_tracking` |  |
| `get_hour_totals` | Return totals + categories for a given person/subject: |
| `_activity_new_id` | Stable-ish short id for a new activity. Seed is only used to keep |
| `_file_has_legacy_activities` | True iff the on-disk activities file contains at least one entry |
| `_ensure_activities_backup` | Write a one-shot backup of the on-disk activities file iff it |
| `_upgrade_activity_v2_to_v3` | Convert one legacy activity dict to the v3 shape. Idempotent — if |
| `load_frol_activities` | Return the activities list in v3 shape. Upgrades legacy v2 entries |
| `save_frol_activities` | Persist activities in v3 shape via safe_save_json. Any legacy |
| `load_seasonal_schedules` | Return all saved seasonal schedule snapshots (list of dicts). |
| `_seasonal_snapshot_day_templates` | Read all current day_templates JSON files into a dict keyed by |
| `get_seasonal_schedule` | Return one entry by id, or None. |
| `find_seasonal_schedule_for` | Return the most recent saved seasonal schedule entry for the given |
| `_summarize_prior_seasonal_entry` | Compact one-line summary of a prior seasonal entry's notes. |
| `delete_seasonal_schedule` | Remove an entry by id; return True if anything was deleted. |
| `get_seasonal_context` | Return a small dict the companions can consume to be season-aware. |
| `get_companion_seasonal_block` | Return a list of lines forming the role-specific seasonal context block. |
| `load_roadmap` |  |
| `save_roadmap` |  |
| `load_mom_notes` |  |
| `save_mom_notes` |  |
| `load_liturgical_custom` |  |
| `save_liturgical_custom` |  |
| `load_calendar_config` |  |
| `save_calendar_config` |  |
| `load_calendar_cache` |  |
| `save_calendar_cache` |  |
| `load_subscribed_calendar_cache` |  |
| `save_subscribed_calendar_cache` |  |
| `load_calendar_rules` |  |
| `save_calendar_rules` |  |
| `load_subscribed_calendars` |  |
| `save_subscribed_calendars` |  |
| `load_family_schedule` |  |
| `save_family_schedule` |  |
| `get_frol_day_slots` | Return the FROL time slots {time: label} for a person on a given weekday. |
| `load_day_template` | Load a single day-template JSON from `base_dir` (defaults to the |
| `get_frol_times` | Return the canonical ordered half-hour time slots used by the FROL. |
| `load_exercise_assignments` |  |
| `save_exercise_assignments` |  |
| `load_coach_programs` |  |
| `save_coach_program` | Append a new program for `person`.  Returns the saved entry (with id). |
| `load_exercise_logs` |  |
| `delete_coach_program` |  |
| `get_family_rule_of_life_text` | Return the Family Rule of Life template for a given weekday as plain text. |
| `get_full_frol_context` | Return a complete, formatted view of the Family Rule of Life for all 7 days: |
| `_archive_history_file` | Copy `history_path` into <history_path>.archive/<timestamp>.json. |
| `load_lucy_history` | Return list of {role, content, ts} dicts, oldest first. |
| `save_lucy_history` | Persist the full message list, capped to LUCY_HISTORY_MAX. |
| `append_lucy_messages` | Append one or more {role, content, ts} dicts and save. |
| `_safe_clear` | Archive then wipe a history file. FAIL-CLOSED: if the file exists and |
| `clear_lucy_history` | Archive then wipe the history file. Returns False if archive failed. |
| `load_lorenzo_history` |  |
| `save_lorenzo_history` |  |
| `append_lorenzo_messages` |  |
| `clear_lorenzo_history` |  |
| `load_gregory_history` |  |
| `save_gregory_history` |  |
| `append_gregory_messages` |  |
| `clear_gregory_history` |  |
| `load_coach_history` |  |
| `save_coach_history` |  |
| `append_coach_messages` |  |
| `clear_coach_history` |  |
| `load_dev_history` |  |
| `save_dev_history` |  |
| `append_dev_messages` |  |
| `clear_dev_history` |  |
| `load_monica_history` |  |
| `save_monica_history` |  |
| `append_monica_messages` |  |
| `clear_monica_history` |  |
| `load_thankyou_reminders` |  |
| `save_thankyou_reminders` |  |
| `pending_thankyou_reminders` | Return reminders with status 'pending', sorted by reminder_date ascending. |
| `due_thankyou_reminders` | Return pending reminders whose reminder_date is today or in the past. |
| `due_thankyou_reminders_for` | Return due reminders assigned to a specific person OR to 'Family'. |
| `load_assignment_analyses` | Return list of analyzed assignments (newest first by ts). |
| `save_assignment_analyses` |  |
| `add_assignment_analysis` | Insert a new analysis record. Returns the saved record. |
| `update_assignment_analysis` |  |
| `delete_assignment_analysis` |  |
| `percent_to_letter` |  |
| `letter_to_gpa` |  |
| `school_year_for_date` | McAdams homeschool year runs Aug 1 – Jul 31. '2026-09-15' -> '2026-2027'. |
| `load_gradebook` | Returns {'entries': [...]}. Each entry is a dict — see add_gradebook_entry. |
| `save_gradebook` |  |
| `add_gradebook_entry` | Insert a new gradebook entry. Returns the saved entry (with id). |
| `update_gradebook_entry` |  |
| `delete_gradebook_entry` |  |
| `gradebook_for_child` | Entries for a child, optionally filtered to a school year. Sorted newest first. |
| `as_text` | Normalize a recipe ingredients/instructions field to a single string. |
| `load_recipes` |  |
| `save_recipes` |  |
| `get_recipe_by_id` | Return the recipe dict whose id equals rid, or None. |
| `add_recipe` | Add or update a recipe (match by name, case-insensitive). Returns saved recipe. |
| `delete_recipe` |  |
| `search_recipes` | Return recipes whose name or ingredients contain the query (case-insensitive). |
| `load_planning_session` |  |
| `save_planning_session` |  |
| `start_planning_session` |  |
| `advance_planning_session` | Advance the session to the slot after the one just filled. |
| `clear_planning_session` |  |
| `planning_session_summary` | Return a dict suitable for sending to the client. |
| `load_monthly_planner` |  |
| `load_curriculum` | Returns the curriculum store.  Shape: |
| `save_curriculum` |  |
| `get_curriculum_week` | Return the current school week number (1-indexed). |
| `get_curriculum_subjects` | Return {subject: {week_str: assignment_text}} for a child. |
| `week_day_segments` | Return the per-day breakdown for a week's stored value. |
| `resolve_week_text` | Return the assignment text for a (week, day) within a subject node. |
| `get_curriculum_week_assignments` | Return {subject: assignment_text} for a child on a specific week. |
| `subject_meeting_days` | Return the list of weekday names (e.g. ['Monday','Wednesday','Friday']) |
| `subject_day_index` | Return the 1-based position of today_name within meeting_days after |
| `advance_curriculum_cursor` | Advance _current_day for a subject; roll over weeks when the day cursor |
| `load_local_events` | Return the raw list of events from data/events.json. |
| `save_local_events` |  |
| `expand_local_events_for_range` | Expand data/events.json entries into calendar-compatible dicts |
| `get_merged_calendar_events` | Merge calendar sources into one structured, deduped, sorted event list. |
| `load_task_overrides` | Load {child: {iso: {task_id: {action, ...}}}} override map. |
| `save_task_overrides` |  |
| `set_task_override` | Store an override for a task on a given day. |
| `clear_task_override` |  |
| `get_day_overrides` | Return {task_id: override_dict} for a given person on a given day. |
| `get_postponed_for_day` | Return task labels that were postponed TO this day from a previous day. |
| `load_curriculum_library` | Load curriculum subjects, units, and assignments. |
| `save_curriculum_library` | Save curriculum library data. |
| `get_subject_by_id` | Get a specific subject by ID. |
| `get_assignments_for_student` | Get all assignments for a specific student across all subjects. |
| `load_student_submissions` | Load student work submissions. |
| `save_student_submissions` | Save student submissions data. |
| `add_student_submission` | Add a new student submission. |
| `get_submissions_for_grading` | Get all submissions pending review. |
| `get_submissions_by_student` | Get all submissions for a specific student. |
| `load_grading_history` | Load completed grading records. |
| `save_grading_history` | Save grading history data. |
| `add_grade_record` | Add a completed grade record and update submission status. |
| `load_curriculum_documents` | Load curriculum reference documents. |
| `save_curriculum_documents` | Save curriculum documents data. |
| `add_curriculum_document` | Add a new curriculum reference document. |
| `load_family_memory` | Return the family memory list. Empty list if file missing/empty. |
| `save_family_memory` | Persist the full memory list. |
| `_now_ts` |  |
| `add_memory` | Append a new memory. Returns the saved record. |
| `update_memory` | Replace the text of an existing memory in place. Returns the updated |
| `delete_memory` | Remove a memory by id. Returns True if something was deleted. |
| `_tokenize_memory` | Lowercase alphanumeric tokens >= 2 chars, stopwords removed. |
| `find_memory_conflicts` | Return existing memories whose Jaccard token-overlap with new_text |
| `get_memory_context_block` | Return the FAMILY MEMORY system-prompt section — current memories |
| `load_prayer_intentions` |  |
| `save_prayer_intentions` |  |
| `add_daily_intention` |  |
| `add_novena` |  |
| `get_active_intentions_for_date` |  |
| `check_upcoming_novenas` | Return feasts in the next 9 days that don't already have an active novena. |
| `load_pope_intentions` |  |
| `save_pope_intentions` |  |
| `get_pope_intention_for_month` |  |
| `load_sister_mary_history` |  |
| `save_sister_mary_history` |  |
| `append_sister_mary_messages` |  |
| `clear_sister_mary_history` |  |
| `load_pantry_staples` | Load pantry staples from PANTRY_STAPLES_FILE. Returns {} if missing. |
| `save_pantry_staples` | Persist pantry staples via safe_save_json. |
| `load_meal_history` | Load meal history from MEAL_HISTORY_FILE. Returns [] if missing. |
| `save_meal_history` | Persist meal history via safe_save_json. |
| `add_meal_history_entry` | Append one entry to meal history and save. Entry shape: |
| `get_recent_meals` | Return meal history entries from the last N weeks, newest first. |
| `load_meal_wizard_session` | Load current meal wizard session state. Returns {} if no active session. |
| `save_meal_wizard_session` | Persist meal wizard session state via safe_save_json. |
| `clear_meal_wizard_session` | Wipe the meal wizard session file (called when plan is locked or abandoned). |
| `update_meal_wizard_session` | Merge updates into current session state and save. Returns updated session. |

Meal-wizard helpers + calendar merge added June 10–11: `get_merged_calendar_events`, `load_pantry_staples`, `save_pantry_staples`, `load_meal_history`, `save_meal_history`, `add_meal_history_entry`, `get_recent_meals`, `load_meal_wizard_session`, `save_meal_wizard_session`, `clear_meal_wizard_session`, `update_meal_wizard_session` — present above.

---

## Section 6 — `config.py` constants

| Constant | Value |
|---|---|
| `HOST` | `"0.0.0.0"` |
| `PORT` | `int(os.environ.get("PORT", 8000))` |
| `MANUAL_TASKS_FILE` | `"data/manual_tasks.json"` |
| `CHORES_FILE` | `"data/chores.json"` |
| `MOM_NOTES_FILE` | `"data/mom_notes.json"` |
| `ROADMAP_FILE` | `"data/roadmap.json"` |
| `LITURGICAL_FILE` | `"data/liturgical.json"` |
| `FAMILY_SCHEDULE_FILE` | `"data/family_schedule.json"` |
| `CALENDAR_CONFIG_FILE` | `"data/calendar_config.json"` |
| `CALENDAR_CACHE_FILE` | `"data/calendar_cache.json"` |
| `MONTHLY_PLANNER_FILE` | `"data/monthly_planner.json"` |
| `CALENDAR_RULES_FILE` | `"data/calendar_rules.json"` |
| `SUBSCRIBED_CALS_FILE` | `"data/subscribed_calendars.json"` |
| `SUBSCRIBED_CACHE_FILE` | `"data/subscribed_calendar_cache.json"` |
| `APP_SETTINGS_FILE` | `"data/app_settings.json"` |
| `CURRICULUM_FILE` | `"data/curriculum.json"` |
| `TASK_OVERRIDES_FILE` | `"data/task_overrides.json"` |
| `COACH_PROGRAMS_FILE` | `"data/coach_programs.json"` |
| `EXERCISE_LOGS_FILE` | `"data/exercise_logs.json"` |
| `SCHOOL_WEEK_PLAN_FILE` | `"data/school_week_plan.json"` |
| `FAMILY_MEMORY_FILE` | `"data/family_memory.json"` |
| `PRAYER_INTENTIONS_FILE` | `"data/prayer_intentions.json"` |
| `SISTER_MARY_HISTORY_FILE` | `"data/sister_mary_history.json"` |
| `POPE_INTENTIONS_FILE` | `"data/pope_intentions.json"` |
| `FROL_WIZARD_PROGRESS_FILE` | `"data/frol_wizard_progress.json"` |
| `HOUR_TRACKING_FILE` | `"data/hour_tracking.json"` |
| `HOUR_REPORTS_DIR` | `"data/hour_reports"` |
| `FROL_ACTIVITIES_FILE` | `"data/frol_activities.json"` |
| `DAY_TEMPLATES_DIR` | `"data/day_templates"` |
| `DAY_TEMPLATES_PREVIEW_DIR` | `"data/day_templates_preview"` |
| `DAY_TEMPLATES_BACKUP_DIR` | `"data/day_templates_backups"` |
| `SEASONAL_SCHEDULES_FILE` | `"data/seasonal_schedules.json"` |
| `MEALS_DIR` | `"data/meal_plan"` |
| `MEAL_RULES_FILE` | `"data/meal_rules.json"` |
| `MEAL_INVENTORY_FILE` | `"data/meal_inventory.json"` |
| `PANTRY_STAPLES_FILE` | `"data/pantry_staples.json"` |
| `MEAL_HISTORY_FILE` | `"data/meal_history.json"` |
| `MEAL_WIZARD_SESSION_FILE` | `"data/meal_wizard_session.json"` |
| `VALID_PRIORITIES` | `{"HIGH", "MEDIUM", "LOW"}` |
| `VALID_STATUSES` | `{"active", "done", "inactive"}` |
| `WEEKDAYS` | `["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]` |
| `WEEKDAY_ORDER` | `{day: i for i, day in enumerate(WEEKDAYS)}` |
| `SCHEDULE_DAYS` | `["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]` |
| `MONTH_NAMES` | `[` |
| `ROADMAP_STATUSES` | `["Someday", "Ready", "In Progress", "Done"]` |
| `ASSIGNABLE_TO` | `["Mom"] + list(CHILDREN)` |
| `CHILD_COLORS` | `_load_child_colors()` |
| `VAN_ROTATION_EPOCH` | `_load_van_epoch()` |
| `VAN_ROLE_A` | `"Interior Reset Lead"` |
| `VAN_ROLE_B` | `"Bin & Organization Lead"` |

Meal-wizard constants (June 10–11): `MEALS_DIR`, `MEAL_RULES_FILE`, `MEAL_INVENTORY_FILE`, `PANTRY_STAPLES_FILE`, `MEAL_HISTORY_FILE`, `MEAL_WIZARD_SESSION_FILE` — present above.

---

## Section 7 — Current `claud.md` rules (full text, as on disk)

The 19 numbered rules below are reproduced verbatim from `claud.md`.

```text
## Python 3.11 hard rules — never violate these
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

```

