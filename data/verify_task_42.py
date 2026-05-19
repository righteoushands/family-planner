"""verify_task_42.py — Prior-year seasonal lookup verification.

Confirms find_seasonal_schedule_for() returns the most recent matching entry
and that each companion's seasonal block surfaces a brief excerpt when an
entry exists for the upcoming season.
"""
import os, sys, json, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date

import config
from data_helpers import (
    find_seasonal_schedule_for,
    get_companion_seasonal_block,
    get_seasonal_context,
    load_seasonal_schedules,
    safe_save_json,
)


def _assert(cond, msg):
    print(("PASS" if cond else "FAIL") + ": " + msg)
    if not cond:
        raise SystemExit(1)


def main():
    ref = date(2026, 5, 19)
    ctx = get_seasonal_context(ref)
    upcoming = ctx.get("upcoming_label")
    upcoming_year = ctx.get("upcoming_year")
    _assert(bool(upcoming), f"upcoming season label resolved for {ref}")
    _assert(isinstance(upcoming_year, int) and upcoming_year > 0,
            f"upcoming season year resolved for {ref}")
    prior_year = upcoming_year - 1

    backup_path = str(config.SEASONAL_SCHEDULES_FILE) + ".bak_task42"
    had_backup = False
    try:
        if os.path.exists(config.SEASONAL_SCHEDULES_FILE):
            shutil.copy(config.SEASONAL_SCHEDULES_FILE, backup_path)
            had_backup = True

        OLDER_NOTES = "Two-years-ago entry that should NEVER be quoted as last year."
        PRIOR_NOTES = (
            "Last year we leaned on the pool every afternoon, kept "
            "Lorenzo's grill rotation on repeat, and Gregory shifted "
            "to living-books reading instead of formal lessons. "
            "Coach moved workouts outdoors and Monica flagged earlier "
            "bedtimes during the heat wave."
        )
        CURRENT_NOTES = "Current-year entry that should NEVER be quoted as last year."
        fixture = [
            {
                "id": "ss_fixture_older",
                "season_label": upcoming,
                "year": prior_year - 1,
                "saved_at": f"{prior_year - 1}-06-01T10:00:00",
                "activities_snapshot": [],
                "day_templates_snapshot": {},
                "notes": OLDER_NOTES,
                "narrative_answers": {},
            },
            {
                "id": "ss_fixture_prior",
                "season_label": upcoming,
                "year": prior_year,
                "saved_at": f"{prior_year}-06-01T10:00:00",
                "activities_snapshot": [],
                "day_templates_snapshot": {},
                "notes": PRIOR_NOTES,
                "narrative_answers": {"q1": "a", "q2": "b", "q3": "c"},
            },
            {
                "id": "ss_fixture_current",
                "season_label": upcoming,
                "year": upcoming_year,
                "saved_at": f"{upcoming_year}-05-01T10:00:00",
                "activities_snapshot": [],
                "day_templates_snapshot": {},
                "notes": CURRENT_NOTES,
                "narrative_answers": {},
            },
        ]
        safe_save_json(config.SEASONAL_SCHEDULES_FILE, fixture)

        all_entries = load_seasonal_schedules()
        _assert(len(all_entries) == 3, "fixture loaded (3 entries)")

        latest = find_seasonal_schedule_for(upcoming)
        _assert(latest is not None and latest.get("id") == "ss_fixture_current",
                "find_seasonal_schedule_for (no year) returns most recent by saved_at")

        prior = find_seasonal_schedule_for(upcoming, year=prior_year)
        _assert(prior is not None and prior.get("id") == "ss_fixture_prior",
                "find_seasonal_schedule_for honors year filter (prior year)")

        older = find_seasonal_schedule_for(upcoming, year=prior_year - 1)
        _assert(older is not None and older.get("id") == "ss_fixture_older",
                "find_seasonal_schedule_for honors year filter (two years ago)")

        none = find_seasonal_schedule_for("DefinitelyNotASeason")
        _assert(none is None, "find_seasonal_schedule_for returns None when missing")

        none_year = find_seasonal_schedule_for(upcoming, year=1999)
        _assert(none_year is None, "find_seasonal_schedule_for returns None when year missing")

        for role in ("LUCY", "LORENZO", "SISTERMARY", "GREGORY", "COACH", "MONICA"):
            block = get_companion_seasonal_block(role, iso=ref.isoformat())
            joined = "\n".join(block)
            _assert(f"Last year ({prior_year}) '{upcoming}' saved notes:" in joined,
                    f"{role} block surfaces prior-year header for year {prior_year}")
            _assert("leaned on the pool" in joined,
                    f"{role} block contains the prior-year notes excerpt")
            _assert("Plus 3 narrative answer" in joined,
                    f"{role} block reports narrative-answer count")
            _assert(OLDER_NOTES not in joined,
                    f"{role} block does NOT quote the two-years-ago entry")
            _assert(CURRENT_NOTES not in joined,
                    f"{role} block does NOT quote the current-year entry as last year")

        lucy = "\n".join(get_companion_seasonal_block("LUCY", iso=ref.isoformat()))
        _assert("If Lauren asks what we did during this season last year" in lucy,
                "LUCY gets explicit instruction to quote prior-year notes")

        lorenzo = "\n".join(get_companion_seasonal_block("LORENZO", iso=ref.isoformat()))
        _assert("any meal, food, or hospitality cues" in lorenzo,
                "LORENZO gets role-specific framing line")
    finally:
        if had_backup:
            shutil.move(backup_path, config.SEASONAL_SCHEDULES_FILE)
        else:
            try:
                os.remove(config.SEASONAL_SCHEDULES_FILE)
            except Exception:
                pass
            safe_save_json(config.SEASONAL_SCHEDULES_FILE, [])

    print()
    print("ALL TASK-42 VERIFICATIONS PASSED")


if __name__ == "__main__":
    main()
