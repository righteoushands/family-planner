"""
make_template.py — Generate a clean, family-agnostic copy of all data files
for use as a starter template (e.g. for a public template branch).

Usage:
    python make_template.py                    # write to ./template_out/
    python make_template.py --out DIR          # write to DIR
    python make_template.py --in-place         # OVERWRITE the live data/ tree

Only data files are touched. No code files are read or modified.
Personal content (names, schedules, history, progress, profiles, caches, etc.)
is replaced with empty containers or sensible defaults. The placeholder
family name is "Family Name".
"""

import argparse
import json
import os
import shutil
import sys


ROOT = os.path.dirname(os.path.abspath(__file__))


EMPTY_DICT_FILES = [
    "data/progress.json",
    "data/task_registry.json",
    "data/task_overrides.json",
    "data/chores.json",
    "data/curriculum.json",
    "data/meal_inventory.json",
    "data/meal_rules.json",
    "data/exercise_assignments.json",
    "data/exercise_logs.json",
    "data/gregory_last_writes.json",
    "data/coach_last_writes.json",
    "data/calendar_cache.json",
    "data/subscribed_calendar_cache.json",
    "data/mom_notes.json",
    "data/notes.json",
    "data/memory_book.json",
    "data/felix_undo.json",
    "data/planning_session.json",
    "data/monthly_planner.json",
    "data/school_previews.json",
    "data/school_weeks.json",
    "data/assignment_analyses.json",
    "data/poetry_passages.json",
    "data/liturgical.json",
    "data/coach_programs.json",
    "data/pope_intentions.json",
    "data/grades.json",
    "data/auth/pins.json",
    "data/auth/sessions.json",
    "family_quest/data/characters.json",
    "family_quest/data/xp.json",
    "family_quest/data/equipment.json",
]


EMPTY_LIST_FILES = [
    "data/family_memory.json",
    "data/manual_tasks.json",
    "data/friends.json",
    "data/kid_messages.json",
    "data/thankyou_reminders.json",
    "data/cycle_log.json",
    "data/roadmap.json",
    "data/lucy_history.json",
    "data/lorenzo_history.json",
    "data/gregory_history.json",
    "data/monica_history.json",
    "data/coach_history.json",
    "data/sister_mary_history.json",
    "data/dev_history.json",
    "data/plan_import_history.json",
    "data/subscribed_calendars.json",
    "data/prayer/intentions.json",
    "family_quest/data/quests.json",
    "family_quest/data/redemptions.json",
]


WRAPPED_FILES = {
    "data/events.json":            {"version": 1, "updated_at": "", "data": []},
    "data/gradebook.json":         {"entries": []},
    "data/prayer_intentions.json": {"daily": [], "repeating": [], "novenas": []},
    "data/goals/master.json":      {"goals": []},
    "data/virtues/personal.json":  {"current": {}, "history": []},
    "data/recipes.json":           {"recipes": []},
    "data/calendar_rules.json":    {"rules": [], "pending": [], "blocked_event_titles": []},
    "data/calendar_config.json":   {"apple_id": "", "app_password": "", "caldav_url": ""},
    "data/school_week_plan.json":  {
        "week_iso": "",
        "status": "",
        "generated_at": "",
        "approved_at": "",
        "plan": {},
    },
    "family_quest/data/boss_settings.json": {
        "available": True,
        "difficulty": 1,
        "boss_type": "",
        "exchange_rate": 1,
    },
}


# Profiles: keep filenames (code references them) but blank out all values.
PROFILE_FILES = [
    "data/profiles/jp.json",
    "data/profiles/joseph.json",
    "data/profiles/michael.json",
    "data/profiles/james.json",
    "data/profiles/mom.json",
    "data/profiles/john.json",
]


# Day templates (Family Rule of Life): keep weekday key, empty the grid.
DAY_TEMPLATE_FILES = [
    "data/day_templates/Sunday.json",
    "data/day_templates/Monday.json",
    "data/day_templates/Tuesday.json",
    "data/day_templates/Wednesday.json",
    "data/day_templates/Thursday.json",
    "data/day_templates/Friday.json",
    "data/day_templates/Saturday.json",
]


# Directories whose JSON contents are runtime-generated per-date data.
# We keep the directory but empty its contents.
PURGE_DIRS = [
    "data/5am",
    "data/cycle",
    "data/daily_plans",
    "data/day_grids",
    "data/history",
    "data/liturgy_hours",
    "data/meal_plan",
    "data/readings_cache",
    "data/saint_cache",
    "data/weekly_intentions",
    "data/weekly_school_plan",
    "data/dev_history.json.archive",
    "data/lorenzo_history.json.archive",
    "data/sister_mary_history.json.archive",
    "data/prayer/photos",
    "data/assignment_uploads",
    "data/goals/children",
    "data/virtues/children",
]


# Backup / log / smoke artifacts that should not appear in the template.
SKIP_FILES = {
    "data/progress.json.bak_before_reopen",
    "data/progress.json.bak_before_reopen2",
    "data/curriculum.json.with-dupes.bak",
    "data/recipes.json.bak_recipes_cleanup",
    "data/server.log",
    "data/_undo_smoke_test.json",
}


# Clean default app_settings — preserves config knobs, scrubs PII / API keys.
APP_SETTINGS_TEMPLATE = {
    "family_name": "Family Name",
    "timezone": "America/New_York",
    "van_epoch": "",
    "schedule_start_hour": 6,
    "schedule_end_hour": 22,
    "cycle_show_detail_fields": False,
    "color_theme": "liturgical",
    "daily_mass_source": "ascension_press",
    "daily_mass_custom_url": "",
    "sister_mary_family_context": False,
    "child_colors": {},
    "location": "",
    "child_birthdays": {},
    "special_events": [],
    "plan_columns": [],
    "family_constraints": "",
    "show_liturgy_hours_widget": True,
    "auto_fetch_hours": False,
    "universalis_country": "",
    "parent_colors": {},
    "anthropic_api_key": "",
}


def write_json(out_root, rel_path, value):
    dest = os.path.join(out_root, rel_path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(value, fh, indent=2, ensure_ascii=False, sort_keys=True)


def blank_value(v):
    """Return an 'empty' version of a value while preserving its type/shape."""
    if isinstance(v, dict):
        return {k: blank_value(sub) for k, sub in v.items()}
    if isinstance(v, list):
        return []
    if isinstance(v, str):
        return ""
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return 0
    return None


def template_profile(src_path):
    """Read a profile file and return a copy with all leaf values blanked."""
    if not os.path.exists(src_path):
        return {}
    try:
        with open(src_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    return blank_value(data) if isinstance(data, dict) else {}


def template_day(weekday):
    return {"weekday": weekday, "grid": {}}


def ensure_empty_dir(out_root, rel_dir):
    dest = os.path.join(out_root, rel_dir)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)
    # Drop a .gitkeep so the empty directory survives in git.
    with open(os.path.join(dest, ".gitkeep"), "w", encoding="utf-8") as fh:
        fh.write("")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=os.path.join(ROOT, "template_out"),
        help="Directory to write the cleaned template tree into "
             "(default: ./template_out/)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the live data/ tree in this project. "
             "Use only on a dedicated template branch.",
    )
    args = parser.parse_args()

    if args.in_place:
        out_root = ROOT
        print(f"WARNING: writing IN PLACE to {out_root}")
    else:
        out_root = args.out
        if os.path.abspath(out_root) == ROOT:
            print("Refusing to write to project root without --in-place.",
                  file=sys.stderr)
            return 2
        if os.path.exists(out_root):
            shutil.rmtree(out_root)
        os.makedirs(out_root, exist_ok=True)
        print(f"Writing template tree to {out_root}")

    written = []

    # Settings (special).
    write_json(out_root, "data/app_settings.json", APP_SETTINGS_TEMPLATE)
    written.append("data/app_settings.json")

    # Empty dicts.
    for rel in EMPTY_DICT_FILES:
        write_json(out_root, rel, {})
        written.append(rel)

    # Empty lists.
    for rel in EMPTY_LIST_FILES:
        write_json(out_root, rel, [])
        written.append(rel)

    # Wrapped / shape-preserving files.
    for rel, value in WRAPPED_FILES.items():
        write_json(out_root, rel, value)
        written.append(rel)

    # Profiles — keep schema, blank values.
    for rel in PROFILE_FILES:
        src = os.path.join(ROOT, rel)
        write_json(out_root, rel, template_profile(src))
        written.append(rel)

    # Day templates — keep weekday key, empty grid.
    for rel in DAY_TEMPLATE_FILES:
        weekday = os.path.splitext(os.path.basename(rel))[0]
        write_json(out_root, rel, template_day(weekday))
        written.append(rel)

    # Empty directories for runtime caches / per-date files.
    purged = []
    for rel in PURGE_DIRS:
        ensure_empty_dir(out_root, rel)
        purged.append(rel)

    # Note: SKIP_FILES are simply never written, so they won't appear in --out
    # mode. In --in-place mode we also unlink them from the live tree.
    skipped = []
    if args.in_place:
        for rel in SKIP_FILES:
            full = os.path.join(out_root, rel)
            if os.path.exists(full):
                os.remove(full)
                skipped.append(rel)

    print()
    print(f"Wrote {len(written)} JSON file(s).")
    print(f"Emptied {len(purged)} runtime directory/ies.")
    if args.in_place and skipped:
        print(f"Removed {len(skipped)} backup/log file(s).")
    print()
    print("Files written:")
    for rel in written:
        print(f"  {rel}")
    print()
    print("Directories emptied (kept with .gitkeep):")
    for rel in purged:
        print(f"  {rel}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
