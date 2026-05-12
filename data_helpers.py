"""
data_helpers.py — All data loading, saving, and utility functions.
Imports from: config, safe_utils, daily_schedule_engine, notes_router
"""
from datetime import date, timedelta
from safe_utils import (
    ensure_file, safe_save_json, debug_log,
    list_snapshots as _su_list_snapshots,
    restore_snapshot as _su_restore_snapshot,
    load_snapshot_data as _su_load_snapshot_data,
)
from daily_schedule_engine import CHILDREN

from config import (
    MANUAL_TASKS_FILE, CHORES_FILE, MOM_NOTES_FILE, ROADMAP_FILE,
    LITURGICAL_FILE, FAMILY_SCHEDULE_FILE, CALENDAR_CONFIG_FILE,
    CALENDAR_CACHE_FILE, MONTHLY_PLANNER_FILE, CALENDAR_RULES_FILE,
    SUBSCRIBED_CALS_FILE, SUBSCRIBED_CACHE_FILE, VALID_PRIORITIES, VALID_STATUSES, WEEKDAYS,
    WEEKDAY_ORDER, CURRICULUM_FILE, TASK_OVERRIDES_FILE,
    SCHOOL_WEEK_PLAN_FILE, FAMILY_MEMORY_FILE,
    PRAYER_INTENTIONS_FILE, SISTER_MARY_HISTORY_FILE, POPE_INTENTIONS_FILE,
)


# ── Snapshot system (re-exported from safe_utils) ───────────────────────────
def list_snapshots(original_path: str = None) -> list:
    return _su_list_snapshots(original_path)

def restore_snapshot(snapshot_key: str) -> tuple:
    return _su_restore_snapshot(snapshot_key)

def load_snapshot_data(snapshot_key: str):
    return _su_load_snapshot_data(snapshot_key)


# ── Date helpers ─────────────────────────────────────────────────────────────
def today_iso() -> str:
    return date.today().isoformat()

def tomorrow_iso() -> str:
    return (date.today() + timedelta(days=1)).isoformat()

def monday_iso_for(iso: str) -> str:
    """Return the ISO date of the Monday of the week containing `iso`.
    Monday=0…Sunday=6 per `date.weekday()`. Saturday/Sunday roll back
    to the previous Monday."""
    d = date.fromisoformat(iso)
    return (d - timedelta(days=d.weekday())).isoformat()


def load_school_week_plan() -> dict:
    """Return the current weekly school plan blob. {} when file is empty."""
    return ensure_file(SCHOOL_WEEK_PLAN_FILE, {})


def save_school_week_plan(data: dict) -> None:
    safe_save_json(SCHOOL_WEEK_PLAN_FILE, data)


_WEEKDAY_INDEX = {"Monday": 0, "Tuesday": 1, "Wednesday": 2,
                  "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}


def generate_weekly_school_plan(week_iso: str) -> dict:
    """Generate a draft weekly school plan for JP and Joseph.

    For each child × each weekday Mon-Fri, calls the live-cursor extractor
    and freezes the result.  Saves with status="draft", clears any prior
    approval.  Returns the saved blob.

    Each subject's day position is determined by its `_weekdays` list
    via `subject_meeting_days` / `subject_day_index` inside the live
    extractor — D1 is NOT necessarily Monday.
    """
    from datetime import datetime as _dt
    from daily_schedule_engine import _extract_school_tasks_live
    monday = date.fromisoformat(week_iso)
    plan: dict = {}
    for child in ("JP", "Joseph"):
        plan[child] = {}
        for wd in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"):
            iso = (monday + timedelta(days=_WEEKDAY_INDEX[wd])).isoformat()
            try:
                blocks = _extract_school_tasks_live(child, wd, iso) or []
            except Exception:
                blocks = []
            # Strip pending_approval from any block (live extractor does
            # not stamp it, but defensive in case future callers do).
            cleaned = []
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                bb = dict(b)
                bb.pop("pending_approval", None)
                cleaned.append(bb)
            plan[child][wd] = cleaned
    blob = {
        "week_iso":     week_iso,
        "status":       "draft",
        "generated_at": _dt.utcnow().isoformat() + "Z",
        "approved_at":  None,
        "plan":         plan,
    }
    save_school_week_plan(blob)
    return blob


def get_approved_school_week_plan(week_iso: str) -> dict | None:
    """Return the plan blob ONLY when it's approved AND for the given week.
    Returns None for: missing file, draft status, mismatched week_iso."""
    data = load_school_week_plan()
    if not isinstance(data, dict):
        return None
    if data.get("week_iso") != week_iso:
        return None
    if data.get("status") != "approved":
        return None
    return data


def normalize_date_query(value: str) -> str:
    value = str(value or "").strip().lower()
    if value == "tomorrow":
        return tomorrow_iso()
    if value == "today":
        return today_iso()
    return str(value or "").strip()


# ── Input sanitisers ─────────────────────────────────────────────────────────
def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default

def clean_priority(value):
    value = str(value or "").strip().upper()
    return value if value in VALID_PRIORITIES else "MEDIUM"

def clean_status(value):
    value = str(value or "").strip().lower()
    return value if value in VALID_STATUSES else "active"

def clean_child(value):
    value = str(value or "").strip()
    return value if value in CHILDREN else ""

def clean_text(value):
    return str(value or "").strip()

def clean_weekday(value):
    value = str(value or "").strip()
    return value  # caller validates against WEEKDAYS if needed

def lines_to_list(text: str):
    return [line.strip() for line in str(text).splitlines() if line.strip()]


# ── School helpers ───────────────────────────────────────────────────────────
def count_school_check_items(payload) -> int:
    total = 0
    for block in payload.get("school_blocks", []):
        total += len(block.get("items", []))
    return total

def is_math_subject(subject: str) -> bool:
    s = str(subject or "").upper()
    return "ALGEBRA" in s or s.startswith("MATH ")

def is_math_test_text(subject: str, assignment_text: str) -> bool:
    combined = f"{subject} {assignment_text}".upper()
    return "TEST" in combined or "QUARTERLY ASSESSMENT" in combined

def sort_school_days(parsed_days):
    return sorted(
        parsed_days,
        key=lambda day: (
            WEEKDAY_ORDER.get(str(day.get("weekday", "")).strip(), 999),
            str(day.get("day_label", "")).strip(),
        ),
    )


# ── Progress ─────────────────────────────────────────────────────────────────
def load_progress() -> dict:
    """Load progress.json — maps task_id -> {done: bool}."""
    return ensure_file("data/progress.json", {})


# ── Manual tasks ─────────────────────────────────────────────────────────────
def load_manual_tasks():
    data = ensure_file(MANUAL_TASKS_FILE, [])
    return data if isinstance(data, list) else []

def save_manual_tasks(tasks):
    safe_save_json(MANUAL_TASKS_FILE, tasks)

def active_manual_tasks():
    return [
        t for t in load_manual_tasks()
        if isinstance(t, dict) and t.get("status", "active") == "active"
    ]

def ensure_manual_task_ids():
    """One-time/idempotent backfill: assign uuid4().hex[:8] to any manual task
    missing or with empty 'id'. Saves only when something changed. Caller is
    responsible for serializing concurrent access (e.g. _MANUAL_TASKS_LOCK).
    Returns the number of ids assigned this call (0 if everything was already
    backfilled)."""
    import uuid as _uuid
    tasks = load_manual_tasks()
    seen = set()
    for t in tasks:
        if isinstance(t, dict):
            tid = t.get("id")
            if isinstance(tid, str) and tid:
                seen.add(tid)
    assigned = 0
    for t in tasks:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        if isinstance(tid, str) and tid:
            continue
        new_id = _uuid.uuid4().hex[:8]
        while new_id in seen:
            new_id = _uuid.uuid4().hex[:8]
        seen.add(new_id)
        t["id"] = new_id
        assigned += 1
    if assigned:
        save_manual_tasks(tasks)
    return assigned

_LEGACY_PATTERN_TO_NTH_WD = {
    "monthly_last_sat":  (-1, 5),
    "monthly_last_sun":  (-1, 6),
    "monthly_last_fri":  (-1, 4),
    "monthly_first_sat": (1, 5),
    "monthly_first_sun": (1, 6),
    "monthly_first_fri": (1, 4),
}

def _nth_weekday_of_month(year: int, month: int, nth: int, weekday: int):
    """Return the date of the Nth `weekday` (0=Mon..6=Sun) in given month/year.
    `nth` is 1..4 for first..fourth, or -1 for the last occurrence.
    Returns None if 5th-style nth doesn't exist that month."""
    import calendar as _cal
    if nth == -1:
        last_day = _cal.monthrange(year, month)[1]
        d = date(year, month, last_day)
        while d.weekday() != weekday:
            d -= timedelta(days=1)
        return d
    # Walk from day 1 forward
    d = date(year, month, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    d = d + timedelta(weeks=nth - 1)
    if d.month != month:
        return None
    return d


def _add_months(d: date, n: int) -> date:
    """Add `n` calendar months, clamping the day if the target month is shorter."""
    import calendar as _cal
    month = d.month - 1 + n
    year  = d.year + month // 12
    month = month % 12 + 1
    day   = min(d.day, _cal.monthrange(year, month)[1])
    return date(year, month, day)


def _next_specific_weekday(base: date, weekdays_set, week_step: int = 1) -> date:
    """Find the next date strictly after `base` whose weekday is in
    `weekdays_set` (set of 0..6). `week_step`: 1=every week, 2=every other, etc.
    Within a 'week_step' window, all selected weekdays are fired; week boundaries
    are Monday."""
    if not weekdays_set:
        return base + timedelta(days=7 * max(week_step, 1))
    # Walk forward day by day; honor week_step by anchoring on the Monday of base's week
    base_monday = base - timedelta(days=base.weekday())
    cand = base + timedelta(days=1)
    for _ in range(7 * max(week_step, 1) + 7):
        cand_monday = cand - timedelta(days=cand.weekday())
        weeks_since_anchor = (cand_monday - base_monday).days // 7
        in_active_week = (weeks_since_anchor % max(week_step, 1)) == 0
        if in_active_week and cand.weekday() in weekdays_set:
            return cand
        cand += timedelta(days=1)
    return base + timedelta(days=7)


def _next_monthly_day(base: date, month_day: int, month_step: int = 1) -> date:
    """Next occurrence on day `month_day` of the month (or -1 = last day),
    advancing by `month_step` months from base's month."""
    import calendar as _cal
    target = _add_months(base.replace(day=1), max(month_step, 1))
    last = _cal.monthrange(target.year, target.month)[1]
    if month_day == -1:
        d = last
    else:
        d = min(max(1, month_day), last)
    return date(target.year, target.month, d)


def format_recurrence_label(task: dict) -> str:
    """Human-readable one-line summary of a task's recurrence."""
    if not task.get("recurring"):
        return ""
    unit = task.get("interval_unit", "weeks")
    val  = safe_int(task.get("interval_value", 1), 1) or 1
    _wd_short = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    _nth_word = {1:"1st", 2:"2nd", 3:"3rd", 4:"4th", 5:"5th", -1:"last"}
    if unit in _LEGACY_PATTERN_TO_NTH_WD:
        nth, wd = _LEGACY_PATTERN_TO_NTH_WD[unit]
        return f"{_nth_word.get(nth,'?')} {_wd_short[wd]} of each month"
    if unit == "specific_weekdays":
        days = sorted(set(safe_int(d, -1) for d in task.get("weekdays_mask", []) if str(d).strip() != ""))
        days = [d for d in days if 0 <= d <= 6]
        if not days:
            return "every week"
        names = ", ".join(_wd_short[d] for d in days)
        if val > 1:
            return f"{names} every {val} weeks"
        return names
    if unit == "monthly_day":
        d = safe_int(task.get("month_day", 1), 1)
        d_label = "last day" if d == -1 else f"day {d}"
        if val > 1:
            return f"{d_label} of every {val} months"
        return f"{d_label} of each month"
    if unit == "monthly_nth_weekday":
        nth = safe_int(task.get("month_nth", 1), 1)
        wd  = safe_int(task.get("month_weekday", 0), 0) % 7
        base = f"{_nth_word.get(nth, str(nth))} {_wd_short[wd]} of each month"
        if val > 1:
            return base.replace("each", f"every {val}")
        return base
    if unit == "weekdays":
        return "every weekday (Mon–Fri)"
    if unit == "years":
        return "every year" if val == 1 else f"every {val} years"
    # days/weeks/months
    unit_word = {"days":"day","weeks":"week","months":"month"}.get(unit, unit)
    if val == 1:
        return f"every {unit_word}"
    return f"every {val} {unit_word}s"


def advance_recurring_task(task: dict) -> dict:
    """Given a completed recurring task, return it reset with the next due date.
    Honors end_date and max_occurrences — when exhausted, status becomes 'inactive'.
    """
    unit  = task.get("interval_unit", "weeks")
    value = safe_int(task.get("interval_value", 1), 1) or 1
    if value < 1:
        value = 1
    base_str = task.get("due_date", "") or date.today().isoformat()
    try:
        base = date.fromisoformat(base_str)
    except Exception:
        base = date.today()

    # Legacy patterns → translate to monthly_nth_weekday on the fly
    if unit in _LEGACY_PATTERN_TO_NTH_WD:
        nth, wd = _LEGACY_PATTERN_TO_NTH_WD[unit]
        # Walk forward month by month until a valid Nth weekday exists
        cand = base
        for _ in range(24):
            cand = _add_months(cand.replace(day=1), 1)
            d = _nth_weekday_of_month(cand.year, cand.month, nth, wd)
            if d and d > base:
                next_due = d
                break
        else:
            next_due = base + timedelta(days=30)
    elif unit == "specific_weekdays":
        raw = task.get("weekdays_mask", [])
        wd_set = {safe_int(d, -1) for d in raw if str(d).strip() != ""}
        wd_set = {d for d in wd_set if 0 <= d <= 6}
        next_due = _next_specific_weekday(base, wd_set, week_step=value)
    elif unit == "monthly_day":
        md = safe_int(task.get("month_day", 1), 1)
        next_due = _next_monthly_day(base, md, month_step=value)
    elif unit == "monthly_nth_weekday":
        nth = safe_int(task.get("month_nth", 1), 1)
        wd  = safe_int(task.get("month_weekday", 0), 0) % 7
        cand = base
        for _ in range(36):
            cand = _add_months(cand.replace(day=1), max(value, 1))
            d = _nth_weekday_of_month(cand.year, cand.month, nth, wd)
            if d and d > base:
                next_due = d
                break
        else:
            next_due = base + timedelta(days=30)
    elif unit == "weekdays":
        next_due = base + timedelta(days=1)
        while next_due.weekday() >= 5:
            next_due += timedelta(days=1)
    elif unit == "days":
        next_due = base + timedelta(days=value)
    elif unit == "months":
        next_due = _add_months(base, value)
    elif unit == "years":
        try:
            next_due = base.replace(year=base.year + value)
        except ValueError:
            # Feb 29 in non-leap year
            next_due = base.replace(year=base.year + value, day=28)
    else:
        next_due = base + timedelta(weeks=value)

    task = dict(task)
    task["due_date"] = next_due.isoformat()
    task["status"]   = "active"

    # End conditions
    end_date = task.get("end_date", "")
    if end_date:
        try:
            if next_due > date.fromisoformat(end_date):
                task["status"] = "inactive"
        except Exception:
            pass
    if "occurrences_remaining" in task:
        try:
            remaining = int(task["occurrences_remaining"]) - 1
            task["occurrences_remaining"] = max(0, remaining)
            if remaining <= 0:
                task["status"] = "inactive"
        except Exception:
            pass
    return task


# ── Chores ───────────────────────────────────────────────────────────────────
def load_chores_data():
    data = ensure_file(CHORES_FILE, {"boys": {}})
    return data if isinstance(data, dict) else {"boys": {}}

def save_chores_data(data):
    return safe_save_json(CHORES_FILE, data)


# ── Roadmap ──────────────────────────────────────────────────────────────────
def load_roadmap():
    data = ensure_file(ROADMAP_FILE, [])
    return data if isinstance(data, list) else []

def save_roadmap(ideas):
    safe_save_json(ROADMAP_FILE, ideas)


# ── Mom notes ────────────────────────────────────────────────────────────────
def load_mom_notes():
    data = ensure_file(MOM_NOTES_FILE, [])
    return data if isinstance(data, list) else []

def save_mom_notes(notes):
    safe_save_json(MOM_NOTES_FILE, notes)


# ── Liturgical ───────────────────────────────────────────────────────────────
def load_liturgical_custom() -> dict:
    data = ensure_file(LITURGICAL_FILE, {})
    return data if isinstance(data, dict) else {}

def save_liturgical_custom(data: dict):
    safe_save_json(LITURGICAL_FILE, data)


# ── Calendar ─────────────────────────────────────────────────────────────────
def load_calendar_config() -> dict:
    return ensure_file(CALENDAR_CONFIG_FILE, {})

def save_calendar_config(cfg: dict):
    safe_save_json(CALENDAR_CONFIG_FILE, cfg)

def load_calendar_cache() -> dict:
    return ensure_file(CALENDAR_CACHE_FILE, {"events": [], "fetched_at": ""})

def save_calendar_cache(data: dict):
    safe_save_json(CALENDAR_CACHE_FILE, data)

def load_subscribed_calendar_cache() -> dict:
    return ensure_file(SUBSCRIBED_CACHE_FILE, {"events": [], "fetched_at": ""})

def save_subscribed_calendar_cache(data: dict):
    safe_save_json(SUBSCRIBED_CACHE_FILE, data)

def load_calendar_rules() -> dict:
    return ensure_file(CALENDAR_RULES_FILE, {"rules": {}})

def save_calendar_rules(data: dict):
    safe_save_json(CALENDAR_RULES_FILE, data)

def load_subscribed_calendars() -> list:
    data = ensure_file(SUBSCRIBED_CALS_FILE, [])
    return data if isinstance(data, list) else []

def save_subscribed_calendars(cals: list):
    safe_save_json(SUBSCRIBED_CALS_FILE, cals)


# ── Family schedule (legacy — kept for backward compat during transition) ────
def load_family_schedule() -> dict:
    return ensure_file(FAMILY_SCHEDULE_FILE, {"times": [], "days": {}})

def save_family_schedule(data: dict):
    safe_save_json(FAMILY_SCHEDULE_FILE, data)


# ── FROL (day templates) ──────────────────────────────────────────────────────
def get_frol_day_slots(weekday: str, person: str = "Mom") -> dict:
    """
    Return the FROL time slots {time: label} for a person on a given weekday.
    Reads from data/day_templates/{weekday}.json (the per-person Rule of Life).

    Lauren and Mom are the same person.  When asked for either, this function
    returns the UNION of slots stored under both keys — the Mom baseline plus
    any Lauren-only personal additions — so a sparse "Lauren" entry can never
    accidentally hide the full daily rhythm stored under "Mom" (or vice versa).
    Same-time conflicts are resolved in favor of the requested name.

    For children (JP, Joseph, Michael, James), only their own grid is returned;
    no fallback to another person's template, so a missing child template
    yields an empty dict instead of accidentally inheriting Mom's day.
    """
    import json as _json
    from pathlib import Path as _Path
    p = _Path(f"data/day_templates/{weekday}.json")
    if not p.exists():
        return {}
    grid = _json.loads(p.read_text(encoding="utf-8")).get("grid", {})
    if person in ("Lauren", "Mom"):
        mom_grid    = dict(grid.get("Mom", {})    or {})
        lauren_grid = dict(grid.get("Lauren", {}) or {})
        # Union of both keys; the requested name wins on time-slot conflicts.
        if person == "Mom":
            merged = {**lauren_grid, **mom_grid}
        else:
            merged = {**mom_grid, **lauren_grid}
        return {t: v for t, v in merged.items() if (v or "").strip()}
    # Children: own grid only.  Do NOT fall through to another person's
    # template — that would give JP or Joseph Lauren's tasks when their
    # day is missing.
    own = grid.get(person, {}) or {}
    return {t: v for t, v in dict(own).items() if (v or "").strip()}


def get_frol_times() -> list:
    """Return the canonical ordered half-hour time slots used by the FROL."""
    from render_schedule_support import generate_half_hour_times
    return generate_half_hour_times()


# ── Exercise assignments ──────────────────────────────────────────────────────
_EXERCISE_FILE = "data/exercise_assignments.json"

def load_exercise_assignments() -> dict:
    return ensure_file(_EXERCISE_FILE, {})

def save_exercise_assignments(data: dict):
    safe_save_json(_EXERCISE_FILE, data)


# ── Coach saved programs ─────────────────────────────────────────────────────
# Long-form fitness program write-ups Coach (or Lauren) saves so they can be
# referenced from each person's POD.  Schema:
#   { "Lauren": [ {id, title, body, saved_at}, ... ], "JP": [...], ... }
from config import COACH_PROGRAMS_FILE as _COACH_PROGRAMS_FILE

def load_coach_programs() -> dict:
    return ensure_file(_COACH_PROGRAMS_FILE, {})

def save_coach_program(person: str, title: str, body: str) -> dict:
    """
    Append a new program for `person`.  Returns the saved entry (with id).
    De-dupes: if an entry with the same case-insensitive title already exists
    for this person, REPLACE it rather than create a duplicate.
    """
    import uuid as _uuid
    from datetime import datetime as _dt
    person = (person or "").strip()
    title  = (title  or "Untitled program").strip()
    body   = (body   or "").strip()
    if not person or not body:
        return {}
    data = load_coach_programs()
    bucket = data.setdefault(person, [])
    entry = {
        "id":       _uuid.uuid4().hex[:12],
        "title":    title,
        "body":     body,
        "saved_at": _dt.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    # Replace same-title entry if present
    for i, p in enumerate(bucket):
        if (p.get("title","") or "").strip().lower() == title.lower():
            entry["id"] = p.get("id", entry["id"])  # preserve id for stable links
            bucket[i] = entry
            safe_save_json(_COACH_PROGRAMS_FILE, data)
            return entry
    bucket.append(entry)
    safe_save_json(_COACH_PROGRAMS_FILE, data)
    return entry

# ── Exercise logs ────────────────────────────────────────────────────────────
# Per-person, per-day post-workout journals. Schema:
#   { "<iso>::<Person>": {"duration":..., "reps":..., "felt":..., "saved_at":...} }
from config import EXERCISE_LOGS_FILE as _EXERCISE_LOGS_FILE

def load_exercise_logs() -> dict:
    return ensure_file(_EXERCISE_LOGS_FILE, {})

def save_exercise_log(person: str, iso: str, duration: str = "",
                      reps: str = "", felt: str = "") -> dict:
    """Save (or replace) a post-workout log for `person` on `iso`."""
    from datetime import datetime as _dt
    person = (person or "").strip()
    iso    = (iso or "").strip()
    if not person or not iso:
        return {}
    data = load_exercise_logs()
    key  = f"{iso}::{person}"
    entry = {
        "duration": (duration or "").strip(),
        "reps":     (reps or "").strip(),
        "felt":     (felt or "").strip(),
        "saved_at": _dt.now().strftime("%Y-%m-%d %H:%M"),
    }
    data[key] = entry
    safe_save_json(_EXERCISE_LOGS_FILE, data)
    return entry


def delete_coach_program(person: str, program_id: str) -> bool:
    data   = load_coach_programs()
    bucket = data.get(person, [])
    new    = [p for p in bucket if p.get("id") != program_id]
    if len(new) == len(bucket):
        return False
    if new:
        data[person] = new
    else:
        data.pop(person, None)
    safe_save_json(_COACH_PROGRAMS_FILE, data)
    return True


def get_family_rule_of_life_text(weekday: str) -> str:
    """
    Return the Family Rule of Life template for a given weekday as plain text.
    Reads from data/day_templates/{Weekday}.json — the per-person daily rhythm.
    Used to give Lucy context so she can structure and print task lists in order.
    """
    import json as _json
    from pathlib import Path as _Path
    try:
        path = _Path(f"data/day_templates/{weekday}.json")
        if not path.exists():
            return ""
        data = _json.loads(path.read_text(encoding="utf-8"))
        grid = data.get("grid", {})
        if not grid:
            return ""
        lines = [f"Daily Schedule Template — {weekday}", ""]
        for person, schedule in grid.items():
            active = [(t, a) for t, a in schedule.items() if a and str(a).strip()]
            if not active:
                continue
            lines.append(f"{person}:")
            for time_slot, activity in active:
                lines.append(f"  {time_slot}: {activity}")
            lines.append("")
        return "\n".join(lines).strip()
    except Exception:
        return ""


def get_full_frol_context(current_weekday: str) -> str:
    """
    Return a complete, formatted view of the Family Rule of Life for all 7 days:
      - family_schedule.json  (the family-wide time structure)
      - day_templates/{Day}.json  (per-person overrides, if any)

    Used to give ALL AI companions full visibility into the family's schedule.
    """
    import json as _json
    from pathlib import Path as _Path

    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    lines = []

    # ── Per-person FROL (day templates — sole source of truth) ───────────────
    lines.append("FAMILY RULE OF LIFE — per-person daily schedules:")
    try:
        for day in DAYS:
            path = _Path(f"data/day_templates/{day}.json")
            if not path.exists():
                continue
            data = _json.loads(path.read_text(encoding="utf-8"))
            grid = data.get("grid", {})
            if not grid:
                continue
            marker = " ← TODAY" if day == current_weekday else ""
            lines.append(f"\n  {day}{marker}:")
            for person, slots in grid.items():
                active = [(t, v) for t, v in slots.items() if str(v).strip()]
                if not active:
                    continue
                lines.append(f"    {person}:")
                for t, v in active:
                    lines.append(f"      {t}: {v}")
    except Exception as _e:
        lines.append(f"  (Could not load day templates: {_e})")

    return "\n".join(lines)


# ── Companion-history archival (safety net for accidental "clear") ────────────
# Whenever a user clicks "Clear chat", we never actually delete — we copy the
# current history into a timestamped archive file so the conversation (and any
# unsaved planning context) can be recovered.
def _archive_history_file(history_path: str) -> str | None:
    """Copy `history_path` into <history_path>.archive/<timestamp>.json.
    Returns the archive path on success, None if there was nothing to archive."""
    try:
        import os, shutil, datetime as _dt
        if not os.path.exists(history_path):
            return None
        # Skip empty/just-{messages:[]} files
        try:
            with open(history_path) as _f:
                _data = json.load(_f)
            if not _data.get("messages"):
                return None
        except Exception:
            pass  # archive anyway if we can't parse
        archive_dir = history_path + ".archive"
        os.makedirs(archive_dir, exist_ok=True)
        # Microseconds + random suffix → collision-proof even on rapid clears
        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        import uuid as _uuid
        dst = f"{archive_dir}/{ts}-{_uuid.uuid4().hex[:6]}.json"
        shutil.copy2(history_path, dst)
        # Rotate: keep last 30 archives per companion
        try:
            entries = sorted(
                [f for f in os.listdir(archive_dir) if f.endswith(".json")],
                reverse=True,
            )
            for old in entries[30:]:
                try:
                    os.remove(os.path.join(archive_dir, old))
                except Exception:
                    pass
        except Exception:
            pass
        return dst
    except Exception as _e:
        print(f"[archive_history] failed for {history_path}: {_e}")
        return None


# ── Lucy conversation history ─────────────────────────────────────────────────
LUCY_HISTORY_FILE = "data/lucy_history.json"
LUCY_HISTORY_MAX  = 60   # max messages stored (30 back-and-forth turns)
LUCY_CONTEXT_MAX  = 30   # messages sent to Claude per request

def load_lucy_history() -> list:
    """Return list of {role, content, ts} dicts, oldest first."""
    data = ensure_file(LUCY_HISTORY_FILE, {"messages": []})
    return data.get("messages", [])

def save_lucy_history(messages: list):
    """Persist the full message list, capped to LUCY_HISTORY_MAX."""
    trimmed = messages[-LUCY_HISTORY_MAX:]
    safe_save_json(LUCY_HISTORY_FILE, {"messages": trimmed})

def append_lucy_messages(new_msgs: list):
    """Append one or more {role, content, ts} dicts and save."""
    history = load_lucy_history()
    history.extend(new_msgs)
    save_lucy_history(history)

def _safe_clear(history_path: str) -> bool:
    """Archive then wipe a history file. FAIL-CLOSED: if the file exists and
    has messages but archival fails, refuse to clear so we never silently
    erase Lauren's conversation. Returns True if cleared, False if blocked."""
    import os as _os
    if _os.path.exists(history_path):
        try:
            with open(history_path) as _f:
                _data = json.load(_f)
            _has_msgs = bool(_data.get("messages"))
        except Exception:
            _has_msgs = True  # treat unparseable as "has data" → must archive
        if _has_msgs:
            arch = _archive_history_file(history_path)
            if not arch:
                print(f"[safe_clear] REFUSING to clear {history_path} — archive failed")
                return False
    safe_save_json(history_path, {"messages": []})
    return True


def clear_lucy_history() -> bool:
    """Archive then wipe the history file. Returns False if archive failed."""
    return _safe_clear(LUCY_HISTORY_FILE)


# ── Lorenzo conversation history ──────────────────────────────────────────────
LORENZO_HISTORY_FILE = "data/lorenzo_history.json"
LORENZO_HISTORY_MAX  = 60
LORENZO_CONTEXT_MAX  = 30

def load_lorenzo_history() -> list:
    data = ensure_file(LORENZO_HISTORY_FILE, {"messages": []})
    return data.get("messages", [])

def save_lorenzo_history(messages: list):
    trimmed = messages[-LORENZO_HISTORY_MAX:]
    safe_save_json(LORENZO_HISTORY_FILE, {"messages": trimmed})

def append_lorenzo_messages(new_msgs: list):
    history = load_lorenzo_history()
    history.extend(new_msgs)
    save_lorenzo_history(history)

def clear_lorenzo_history() -> bool:
    return _safe_clear(LORENZO_HISTORY_FILE)


# ── Father Gregory (Headmaster) conversation history ──────────────────────────
GREGORY_HISTORY_FILE = "data/gregory_history.json"
GREGORY_HISTORY_MAX  = 60
GREGORY_CONTEXT_MAX  = 30

def load_gregory_history() -> list:
    data = ensure_file(GREGORY_HISTORY_FILE, {"messages": []})
    return data.get("messages", [])

def save_gregory_history(messages: list):
    trimmed = messages[-GREGORY_HISTORY_MAX:]
    safe_save_json(GREGORY_HISTORY_FILE, {"messages": trimmed})

def append_gregory_messages(new_msgs: list):
    history = load_gregory_history()
    history.extend(new_msgs)
    save_gregory_history(history)

def clear_gregory_history() -> bool:
    return _safe_clear(GREGORY_HISTORY_FILE)


# ── Coach conversation history ────────────────────────────────────────────────
COACH_HISTORY_FILE = "data/coach_history.json"
COACH_HISTORY_MAX  = 60
COACH_CONTEXT_MAX  = 30

def load_coach_history() -> list:
    data = ensure_file(COACH_HISTORY_FILE, {"messages": []})
    return data.get("messages", [])

def save_coach_history(messages: list):
    trimmed = messages[-COACH_HISTORY_MAX:]
    safe_save_json(COACH_HISTORY_FILE, {"messages": trimmed})

def append_coach_messages(new_msgs: list):
    history = load_coach_history()
    history.extend(new_msgs)
    save_coach_history(history)

def clear_coach_history() -> bool:
    return _safe_clear(COACH_HISTORY_FILE)


# ── Felix (Dev) history ───────────────────────────────────────────────────────
DEV_HISTORY_FILE = "data/dev_history.json"
DEV_HISTORY_MAX  = 40   # keep last 40 turns in file
DEV_CONTEXT_MAX  = 20   # messages sent to Claude per request (file reads now persist, need more room)

def load_dev_history() -> list:
    data = ensure_file(DEV_HISTORY_FILE, {"messages": []})
    return data.get("messages", [])

def save_dev_history(messages: list):
    trimmed = messages[-DEV_HISTORY_MAX:]
    safe_save_json(DEV_HISTORY_FILE, {"messages": trimmed})

def append_dev_messages(new_msgs: list):
    history = load_dev_history()
    history.extend(new_msgs)
    save_dev_history(history)

def clear_dev_history() -> bool:
    return _safe_clear(DEV_HISTORY_FILE)


# ── Dr. Monica conversation history ───────────────────────────────────────────
MONICA_HISTORY_FILE = "data/monica_history.json"
MONICA_HISTORY_MAX  = 60
MONICA_CONTEXT_MAX  = 30

def load_monica_history() -> list:
    data = ensure_file(MONICA_HISTORY_FILE, {"messages": []})
    return data.get("messages", [])

def save_monica_history(messages: list):
    trimmed = messages[-MONICA_HISTORY_MAX:]
    safe_save_json(MONICA_HISTORY_FILE, {"messages": trimmed})

def append_monica_messages(new_msgs: list):
    history = load_monica_history()
    history.extend(new_msgs)
    save_monica_history(history)

def clear_monica_history() -> bool:
    return _safe_clear(MONICA_HISTORY_FILE)


# ── Thank-you card reminders ──────────────────────────────────────────────────
THANKYOU_FILE = "data/thankyou_reminders.json"

def load_thankyou_reminders() -> list:
    data = ensure_file(THANKYOU_FILE, [])
    return data if isinstance(data, list) else []

def save_thankyou_reminders(reminders: list):
    safe_save_json(THANKYOU_FILE, reminders)

def pending_thankyou_reminders() -> list:
    """Return reminders with status 'pending', sorted by reminder_date ascending."""
    from datetime import date as _d
    today = str(_d.today())
    reminders = load_thankyou_reminders()
    pending = [r for r in reminders if isinstance(r, dict) and r.get("status") == "pending"]
    return sorted(pending, key=lambda r: r.get("reminder_date", "9999-12-31"))

def due_thankyou_reminders() -> list:
    """Return pending reminders whose reminder_date is today or in the past."""
    from datetime import date as _d
    today = str(_d.today())
    return [r for r in pending_thankyou_reminders() if r.get("reminder_date", "9999") <= today]

def due_thankyou_reminders_for(person: str) -> list:
    """
    Return due reminders assigned to a specific person OR to 'Family'.
    Pass person='Family' to get only Family-level (unassigned or assigned to Family).
    """
    due = due_thankyou_reminders()
    person_lower = person.strip().lower()
    if person_lower == "family":
        return [r for r in due if r.get("assigned_to", "Family").strip().lower() == "family"]
    return [r for r in due if r.get("assigned_to", "Family").strip().lower() == person_lower]


# ── Assignment analyses (AI-parsed assignments) ─────────────────────────────
ASSIGNMENT_ANALYSES_FILE = "data/assignment_analyses.json"
ASSIGNMENT_UPLOADS_DIR = "data/assignment_uploads"

def load_assignment_analyses() -> list:
    """Return list of analyzed assignments (newest first by ts)."""
    data = ensure_file(ASSIGNMENT_ANALYSES_FILE, {"items": []})
    items = data.get("items", []) if isinstance(data, dict) else []
    return sorted(items, key=lambda x: x.get("ts", ""), reverse=True)

def save_assignment_analyses(items: list):
    safe_save_json(ASSIGNMENT_ANALYSES_FILE, {"items": items})

def add_assignment_analysis(record: dict) -> dict:
    """Insert a new analysis record. Returns the saved record."""
    import uuid
    from datetime import datetime as _dt
    items = load_assignment_analyses()
    record.setdefault("id", "a-" + _dt.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    record.setdefault("ts", _dt.now().isoformat(timespec="seconds"))
    record.setdefault("status", "pending_curriculum_placement")
    record.setdefault("user_edits", {})
    items.append(record)
    save_assignment_analyses(items)
    return record

def update_assignment_analysis(analysis_id: str, edits: dict) -> bool:
    items = load_assignment_analyses()
    changed = False
    for it in items:
        if it.get("id") == analysis_id:
            it.setdefault("user_edits", {}).update(edits or {})
            changed = True
            break
    if changed:
        save_assignment_analyses(items)
    return changed

def delete_assignment_analysis(analysis_id: str) -> bool:
    import os as _os
    items = load_assignment_analyses()
    before = len(items)
    keep = []
    for it in items:
        if it.get("id") == analysis_id:
            # Best-effort delete the stored upload, if any
            up = it.get("upload_path", "")
            if up and _os.path.exists(up):
                try: _os.remove(up)
                except OSError: pass
        else:
            keep.append(it)
    save_assignment_analyses(keep)
    return len(keep) < before


# ── Gradebook (per-child recorded scores) ──────────────────────────────────
GRADEBOOK_FILE = "data/gradebook.json"

# Standard 4.0 scale (A+ same as A — common US homeschool convention).
GRADE_LETTER_SCALE = [
    ("A+", 97, 4.0),
    ("A",  93, 4.0),
    ("A-", 90, 3.7),
    ("B+", 87, 3.3),
    ("B",  83, 3.0),
    ("B-", 80, 2.7),
    ("C+", 77, 2.3),
    ("C",  73, 2.0),
    ("C-", 70, 1.7),
    ("D",  60, 1.0),
    ("F",   0, 0.0),
]
GRADE_LETTERS = [row[0] for row in GRADE_LETTER_SCALE]
# Younger-child encouragement marks (Michael, James not in school yet)
ENCOURAGEMENT_MARKS = ["✦ Excellent", "✓ Good work", "↻ Try again"]
# Children who get GPA-style scoring (older boys). Michael/James do not.
GPA_CHILDREN = ["JP", "Joseph"]

def percent_to_letter(pct) -> str:
    try: p = float(pct)
    except (TypeError, ValueError): return ""
    for letter, cutoff, _gpa in GRADE_LETTER_SCALE:
        if p >= cutoff:
            return letter
    return "F"

def letter_to_gpa(letter: str):
    if not letter: return None
    for l, _c, g in GRADE_LETTER_SCALE:
        if l == letter:
            return g
    return None

def school_year_for_date(iso_date: str) -> str:
    """McAdams homeschool year runs Aug 1 – Jul 31. '2026-09-15' -> '2026-2027'."""
    from datetime import date as _d
    try:
        d = _d.fromisoformat(iso_date[:10])
    except Exception:
        d = _d.today()
    if d.month >= 8:
        return f"{d.year}-{d.year + 1}"
    return f"{d.year - 1}-{d.year}"

def load_gradebook() -> dict:
    """Returns {'entries': [...]}. Each entry is a dict — see add_gradebook_entry."""
    data = ensure_file(GRADEBOOK_FILE, {"entries": []})
    if not isinstance(data, dict):
        data = {"entries": []}
    data.setdefault("entries", [])
    return data

def save_gradebook(data: dict):
    safe_save_json(GRADEBOOK_FILE, data)

def add_gradebook_entry(entry: dict) -> dict:
    """Insert a new gradebook entry. Returns the saved entry (with id)."""
    import uuid
    from datetime import datetime as _dt, date as _d
    data = load_gradebook()
    today = _d.today().isoformat()
    entry.setdefault("id", "g-" + _dt.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    entry.setdefault("ts", _dt.now().isoformat(timespec="seconds"))
    entry.setdefault("date", today)
    entry.setdefault("school_year", school_year_for_date(entry["date"]))
    entry.setdefault("extras", {})  # reserved for future rubrics / MODG bricks
    data["entries"].append(entry)
    save_gradebook(data)
    return entry

def update_gradebook_entry(entry_id: str, edits: dict) -> bool:
    data = load_gradebook()
    changed = False
    for e in data["entries"]:
        if e.get("id") == entry_id:
            for k, v in (edits or {}).items():
                e[k] = v
            # Recompute school_year if date changed
            if "date" in (edits or {}):
                e["school_year"] = school_year_for_date(e["date"])
            changed = True
            break
    if changed:
        save_gradebook(data)
    return changed

def delete_gradebook_entry(entry_id: str) -> bool:
    data = load_gradebook()
    before = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e.get("id") != entry_id]
    if len(data["entries"]) < before:
        save_gradebook(data)
        return True
    return False

def gradebook_for_child(child: str, school_year: str = "") -> list:
    """Entries for a child, optionally filtered to a school year. Sorted newest first."""
    entries = [e for e in load_gradebook()["entries"] if e.get("child") == child]
    if school_year:
        entries = [e for e in entries if e.get("school_year") == school_year]
    return sorted(entries, key=lambda e: (e.get("date",""), e.get("ts","")), reverse=True)


RECIPES_FILE = "data/recipes.json"

def as_text(value) -> str:
    """Normalize a recipe ingredients/instructions field to a single string.

    Recipes carry these fields as either a single string (legacy curated
    cards) or a list of strings (newer structured cards). Returning a
    line-joined string in both cases lets renderers and text-search code
    treat the value uniformly without each caller re-implementing the check.
    """
    if isinstance(value, list):
        return "\n".join(str(x) for x in value)
    return str(value or "")

def load_recipes() -> list:
    data = ensure_file(RECIPES_FILE, {"recipes": []})
    # Legacy format: top-level list
    if isinstance(data, list):
        return data
    return data.get("recipes", [])

def save_recipes(recipes: list):
    safe_save_json(RECIPES_FILE, {"recipes": recipes})

def get_recipe_by_id(rid: str) -> dict | None:
    """Return the recipe dict whose id equals rid, or None.

    Used by Lorenzo's recipe-link feature so a meal slot carrying
    {"display": "...", "recipe_id": "rNNN"} can resolve back to the
    saved card without a fuzzy-name search.
    """
    if not rid:
        return None
    rid = str(rid).strip()
    if not rid:
        return None
    for r in load_recipes():
        if str(r.get("id", "")).strip() == rid:
            return r
    return None

def save_recipe(name: str, ingredients: str, instructions: str,
                tags: list = None, prep_time: str = "", image: str = "") -> dict:
    """Append a new recipe to the library. Always creates a new id; does NOT
    dedupe by name (use add_recipe for dedup-by-name behavior). Preserved as
    the form-input wrapper for /recipe-save."""
    import uuid
    from datetime import date as _d
    recipes = load_recipes()
    recipe = {
        "id": str(uuid.uuid4())[:8],
        "name": name.strip(),
        "ingredients": ingredients.strip(),
        "instructions": instructions.strip(),
        "tags": tags or [],
        "prep_time": prep_time.strip(),
        "image": (image or "").strip(),
        "created": _d.today().isoformat(),
    }
    recipes.append(recipe)
    save_recipes(recipes)
    return recipe

def add_recipe(recipe: dict) -> dict:
    """Add or update a recipe (match by name, case-insensitive). Returns saved recipe."""
    import uuid
    from datetime import date as _d
    recipes = load_recipes()
    name = recipe.get("name", "").strip()
    # Dedup: replace if same name already exists
    recipes = [r for r in recipes if r.get("name", "").lower() != name.lower()]
    recipe.setdefault("id", str(uuid.uuid4())[:8])
    recipe.setdefault("date_added", _d.today().isoformat())
    recipes.append(recipe)
    save_recipes(recipes)
    return recipe

def delete_recipe(recipe_id: str) -> bool:
    recipes = load_recipes()
    before = len(recipes)
    recipes = [r for r in recipes if r.get("id") != recipe_id]
    save_recipes(recipes)
    return len(recipes) < before

def search_recipes(query: str) -> list:
    """Return recipes whose name or ingredients contain the query (case-insensitive)."""
    q = query.lower().strip()
    if not q:
        return load_recipes()
    results = []
    for r in load_recipes():
        haystack = (r.get("name","") + " " +
                    as_text(r.get("ingredients", "")) + " " +
                    " ".join(r.get("tags", []))).lower()
        if q in haystack:
            results.append(r)
    return results


# ── Guided planning session ──────────────────────────────────────────────────
PLANNING_SESSION_FILE = "data/planning_session.json"
PLAN_DAYS  = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
PLAN_SLOTS = ["breakfast","lunch","dinner"]

def load_planning_session() -> dict:
    return ensure_file(PLANNING_SESSION_FILE, {"active": False})

def save_planning_session(session: dict):
    safe_save_json(PLANNING_SESSION_FILE, session)

def start_planning_session(week_iso: str) -> dict:
    from datetime import datetime as _dt
    session = {
        "active": True,
        "week_iso": week_iso,
        "days":  PLAN_DAYS,
        "slots": PLAN_SLOTS,
        "current_day_idx":  0,
        "current_slot_idx": 0,
        "started_at": _dt.now().isoformat(),
    }
    save_planning_session(session)
    return session

def advance_planning_session(matched_day: str, matched_slot: str) -> dict:
    """Advance the session to the slot after the one just filled.
    Only advances if the filled slot is at or after the current position."""
    session = load_planning_session()
    if not session.get("active"):
        return session
    days  = session.get("days",  PLAN_DAYS)
    slots = session.get("slots", PLAN_SLOTS)
    mday  = matched_day.strip().capitalize()
    mslot = matched_slot.strip().lower()
    if mday not in days or mslot not in slots:
        return session
    total        = len(days) * len(slots)
    current_pos  = session.get("current_day_idx", 0) * len(slots) + session.get("current_slot_idx", 0)
    saved_pos    = days.index(mday) * len(slots) + slots.index(mslot)
    if saved_pos >= current_pos:
        next_pos = saved_pos + 1
        if next_pos >= total:
            from datetime import datetime as _dt
            session["active"] = False
            session["completed_at"] = _dt.now().isoformat()
        else:
            session["current_day_idx"]  = next_pos // len(slots)
            session["current_slot_idx"] = next_pos %  len(slots)
        save_planning_session(session)
    return session

def clear_planning_session():
    save_planning_session({"active": False})

def planning_session_summary(session: dict) -> dict:
    """Return a dict suitable for sending to the client."""
    if not session.get("active"):
        return {"active": False}
    days  = session.get("days",  PLAN_DAYS)
    slots = session.get("slots", PLAN_SLOTS)
    di    = session.get("current_day_idx",  0)
    si    = session.get("current_slot_idx", 0)
    total = len(days) * len(slots)
    pos   = di * len(slots) + si
    return {
        "active":       True,
        "week_iso":     session.get("week_iso",""),
        "current_day":  days[di]  if di  < len(days)  else "",
        "current_slot": slots[si] if si  < len(slots) else "",
        "day_idx":      di,
        "slot_idx":     si,
        "total_slots":  total,
        "slots_done":   pos,
        "days":         days,
        "slots":        slots,
    }


# ── Monthly planner ──────────────────────────────────────────────────────────
def load_monthly_planner() -> dict:
    return ensure_file(MONTHLY_PLANNER_FILE, {})


# ── Curriculum (full-year MODG subject plans) ─────────────────────────────────
def load_curriculum() -> dict:
    """
    Returns the curriculum store.  Shape:
    {
      "current_week": 1,          # school week number (int)
      "JP":    { "Latin": {"1": "...", "2": "..."}, ... },
      "Joseph": { ... },
      ...
    }
    """
    return ensure_file(CURRICULUM_FILE, {"current_week": 1})


def save_curriculum(data: dict):
    safe_save_json(CURRICULUM_FILE, data)


def get_curriculum_week() -> int:
    """Return the current school week number (1-indexed)."""
    try:
        return int(load_curriculum().get("current_week", 1))
    except (TypeError, ValueError):
        return 1


def get_curriculum_subjects(child: str) -> dict:
    """
    Return {subject: {week_str: assignment_text}} for a child.
    Returns empty dict if no curriculum exists.
    """
    cur = load_curriculum()
    return cur.get(child, {})


def week_day_segments(val) -> list[tuple[int, str]]:
    """Return the per-day breakdown for a week's stored value.

    A week value can be either:
      - a {day_str: text} dict (per-day MODG format), or
      - a plain string. If the string contains `;`-separated segments
        (the MODG default for "Lesson A; Lesson B; Lesson C…"), each
        segment is treated as a day. A single-segment string returns [].

    Returns ordered [(day_num, text), …] starting at Day 1.
    Empty list means "no day-level breakdown — treat as a whole-week string".
    """
    if isinstance(val, dict):
        out = []
        for k, v in val.items():
            if not str(k).isdigit():
                continue
            t = str(v or "").strip()
            if t:
                out.append((int(k), t))
        out.sort(key=lambda t: t[0])
        return out
    if isinstance(val, str):
        import re as _re
        # Explicit "Day N:" markers — strongest signal, split on those.
        marker = _re.compile(r'(?:^|\n|;|\.)\s*Day\s*(\d+)\s*[:\-\.]\s*',
                             _re.IGNORECASE)
        marks = list(marker.finditer(val))
        if len(marks) >= 2:
            out = []
            for i, m in enumerate(marks):
                start = m.end()
                end   = marks[i+1].start() if i+1 < len(marks) else len(val)
                body  = val[start:end].strip().rstrip(";").strip()
                if body:
                    out.append((int(m.group(1)), body))
            if out:
                return out
        # No explicit markers — only treat semicolons as day delimiters when
        # there are at least 4 segments (a typical school week). Fewer than
        # that is almost always prose punctuation, not days.
        parts = [p.strip() for p in val.split(";")]
        parts = [p for p in parts if p]
        if len(parts) >= 4:
            return list(enumerate(parts, start=1))
    return []


def resolve_week_text(subject_node: dict, week: int, day_pref: int | None = None) -> str:
    """Return the assignment text for a (week, day) within a subject node.

    Handles three shapes for a week's value:
      - {day_str: text} dict (per-day MODG format),
      - `;`-separated string (each segment is a day, in order),
      - plain string (whole-week assignment — `day_pref` is ignored).

    For multi-day shapes: prefer `day_pref`, then subject_node's
    `_current_day`, then Day 1.
    """
    if not isinstance(subject_node, dict):
        return ""
    val = subject_node.get(str(week))
    days = week_day_segments(val)
    if days:
        day_nums = [d for d, _ in days]
        d = day_pref
        if d is None:
            try:    d = int(subject_node.get("_current_day") or day_nums[0])
            except (TypeError, ValueError): d = day_nums[0]
        if d not in day_nums:
            d = day_nums[0]
        for dn, txt in days:
            if dn == d:
                return txt
        return ""
    if isinstance(val, str):
        return val.strip()
    return ""


def get_curriculum_week_assignments(child: str, week: int) -> dict:
    """
    Return {subject: assignment_text} for a child on a specific week.
    Only includes subjects that have an assignment for that week.
    Handles both plain-string and {day:text} dict week values.
    """
    subjects = get_curriculum_subjects(child)
    result = {}
    for subject, weeks in subjects.items():
        text = resolve_week_text(weeks, week)
        if text:
            result[subject] = text
    return result


def subject_meeting_days(child: str, subject: str, subject_node=None) -> list:
    """Return the list of weekday names (e.g. ['Monday','Wednesday','Friday'])
    on which a subject meets for the given child.

    Matching is three-pass (in order of preference):
      0. **Subject-node `_weekdays` fast path** — if `subject_node` is a dict
         and contains a non-empty list under the `_weekdays` key, that list
         is returned directly without consulting school_weeks.json. This
         makes curriculum self-contained when `_weekdays` is populated and
         decouples scheduling from PDF imports.
      1. Exact (case-sensitive, stripped) match against
         school_weeks.json's parsed_days — preferred when `_weekdays` is
         absent or empty.
      2. Fuzzy fallback (case-insensitive) — succeeds when the curriculum
         subject name starts with the school_weeks subject name, or when
         the school_weeks subject name is contained within the curriculum
         subject name. Bridges long syllabus names in curriculum.json
         (e.g. "Music 8 (Top 100 Classical Music ...) Syllabus") to the
         short names used in school_weeks.json (e.g. "Music 8").

    Returns [] if not found or on any error."""
    # Pass 0 — subject-node `_weekdays` fast path.
    # Only short-circuits when the list contains at least one valid (non-empty
    # string) weekday entry.  Malformed inputs (None, non-list, list of
    # non-strings, list of empty strings, etc.) fall through to the
    # school_weeks lookup below, so we never silently return [] when
    # school_weeks could still answer.
    if isinstance(subject_node, dict):
        wd = subject_node.get("_weekdays")
        if isinstance(wd, list):
            valid = [d for d in wd if isinstance(d, str) and d]
            if valid:
                return valid
    try:
        from school_pdf_engine import load_school_weeks
        weeks = load_school_weeks() or {}
        approved = weeks.get("approved", {}) or {}
        child_node = approved.get(child) or {}
        days = child_node.get("parsed_days", []) or []

        # Pass 1 — exact match.
        out = []
        subj_stripped = subject.strip()
        for day in days:
            if not isinstance(day, dict):
                continue
            wd = day.get("weekday", "")
            for blk in (day.get("blocks") or []):
                if isinstance(blk, dict) and blk.get("subject", "").strip() == subj_stripped:
                    if wd and wd not in out:
                        out.append(wd)
                    break
        if out:
            return out

        # Pass 2 — fuzzy fallback (case-insensitive prefix / containment).
        subj_lower = subj_stripped.lower()
        for day in days:
            if not isinstance(day, dict):
                continue
            wd = day.get("weekday", "")
            for blk in (day.get("blocks") or []):
                if not isinstance(blk, dict):
                    continue
                blk_subj = (blk.get("subject") or "").strip()
                if not blk_subj:
                    continue
                blk_lower = blk_subj.lower()
                if subj_lower.startswith(blk_lower) or blk_lower in subj_lower:
                    if wd and wd not in out:
                        out.append(wd)
                    break
        return out
    except Exception:
        return []


def subject_day_index(meeting_days: list, today_name: str):
    """Return the 1-based position of today_name within meeting_days after
    sorting by WEEKDAY_ORDER. Returns None when today_name is not in the list."""
    try:
        if not meeting_days or not today_name:
            return None
        ordered = sorted(meeting_days, key=lambda d: WEEKDAY_ORDER.get(d, 99))
        if today_name not in ordered:
            return None
        return ordered.index(today_name) + 1
    except Exception:
        return None


def advance_curriculum_cursor(child: str, subject: str) -> None:
    """Advance _current_day for a subject; roll over weeks when the day cursor
    passes the last segment; when the week cursor passes the last week mark the
    subject complete (sentinel _current_week=999) and append a note to
    data/notes.json with suggested_destination=/curriculum."""
    try:
        cur = load_curriculum()
        if not isinstance(cur, dict):
            return
        child_node = cur.get(child)
        if not isinstance(child_node, dict):
            return
        subj_node = child_node.get(subject)
        if not isinstance(subj_node, dict):
            return

        try:    cur_week = int(subj_node.get("_current_week", 1))
        except (TypeError, ValueError): cur_week = 1
        try:    cur_day  = int(subj_node.get("_current_day", 1))
        except (TypeError, ValueError): cur_day = 1

        # Already complete — nothing to do.
        if cur_week >= 999:
            return

        # Determine current week's segment day-numbers.
        this_week_val = subj_node.get(str(cur_week), "")
        segs = week_day_segments(this_week_val)
        day_nums = [d for d, _ in segs]

        # Pick next day_num after cur_day.
        next_day = None
        if day_nums:
            for d in day_nums:
                if d > cur_day:
                    next_day = d
                    break

        if next_day is not None:
            # Stay in same week, advance day cursor.
            subj_node["_current_day"] = next_day
            save_curriculum(cur)
            return

        # Day cursor exhausted for this week — roll to next week.
        next_week = cur_week + 1

        # Find max numeric week key on this subject node.
        try:
            max_week = max(int(k) for k in subj_node.keys()
                           if not str(k).startswith("_") and str(k).isdigit())
        except ValueError:
            max_week = 0

        if next_week > max_week:
            # Subject fully complete — set sentinel and append a note.
            subj_node["_current_week"] = 999
            subj_node["_current_day"] = 1
            save_curriculum(cur)
            try:
                import json as _cnj, uuid as _cnu
                from datetime import datetime as _cndt
                notes_path = "data/notes.json"
                today_iso = _cndt.now().date().isoformat()
                try:
                    with open(notes_path) as _nf:
                        notes_data = _cnj.load(_nf)
                except Exception:
                    notes_data = {"version": 1, "updated_at": today_iso, "data": []}
                if not isinstance(notes_data, dict):
                    notes_data = {"version": 1, "updated_at": today_iso, "data": []}
                notes_data.setdefault("data", [])
                notes_data["data"].append({
                    "id": "note_" + _cnu.uuid4().hex[:8],
                    "text": f"{child} has completed {subject} — all weeks are done.",
                    "created_at": _cndt.now().isoformat(timespec="seconds"),
                    "status": "open",
                    "tags": [],
                    "suggested_destination": "/curriculum",
                    "archived_at": None,
                })
                notes_data["updated_at"] = today_iso
                safe_save_json(notes_path, notes_data)
            except Exception:
                pass
            return

        # Roll forward into next_week — pick first segment-day of that week.
        next_week_val = subj_node.get(str(next_week), "")
        next_segs = week_day_segments(next_week_val)
        if next_segs:
            subj_node["_current_day"] = next_segs[0][0]
        else:
            subj_node["_current_day"] = 1
        subj_node["_current_week"] = next_week
        save_curriculum(cur)
    except Exception:
        return


# ── Local events (data/events.json) ─────────────────────────────────────────
EVENTS_FILE = "data/events.json"

def load_local_events() -> list:
    """Return the raw list of events from data/events.json."""
    try:
        import json as _j
        with open(EVENTS_FILE) as _f:
            d = _j.load(_f)
        return d.get("data", d) if isinstance(d, dict) else d
    except Exception:
        return []

def save_local_events(events: list):
    safe_save_json(EVENTS_FILE, {"version": 1, "data": events})

_WEEKDAY_NAMES = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]

def expand_local_events_for_range(start_iso: str, end_iso: str) -> list:
    """
    Expand data/events.json entries into calendar-compatible dicts
    {title, start (ISO datetime or date), all_day, start_time, end_time}
    for every date in [start_iso .. end_iso] (inclusive).
    Handles recurrence types: none / daily / weekly.
    """
    from datetime import date as _dt, timedelta as _td
    events = load_local_events()
    out = []
    start_d = _dt.fromisoformat(start_iso)
    end_d   = _dt.fromisoformat(end_iso)

    def _add(ev, d):
        st = ev.get("start_time", "")
        et = ev.get("end_time", "")
        iso_start = f"{d.isoformat()}T{st}" if st else d.isoformat()
        out.append({
            "title":      ev.get("title", ""),
            "start":      iso_start,
            "end":        f"{d.isoformat()}T{et}" if et else d.isoformat(),
            "all_day":    not bool(st),
            "start_time": st,
            "end_time":   et,
            "notes":      ev.get("notes", ""),
            "assigned_to": ev.get("assigned_to", []),
            "source":     "local",
        })

    for ev in events:
        if ev.get("archived"):
            continue
        rec  = ev.get("recurrence", {}) or {}
        rtype = rec.get("type", "none") or "none"
        ev_start = ev.get("start_date", "")
        if not ev_start:
            continue
        try:
            ev_start_d = _dt.fromisoformat(ev_start)
        except ValueError:
            continue

        if rtype == "none":
            if start_d <= ev_start_d <= end_d:
                _add(ev, ev_start_d)

        elif rtype == "daily":
            cur = max(start_d, ev_start_d)
            until = rec.get("until")
            while cur <= end_d:
                if until and cur.isoformat() > until:
                    break
                _add(ev, cur)
                cur += _td(days=1)

        elif rtype == "weekly":
            by_day = [w.lower() for w in (rec.get("by_weekday") or [])]
            interval = max(1, int(rec.get("interval", 1)))
            until    = rec.get("until")
            cur = max(start_d, ev_start_d)
            while cur <= end_d:
                if until and cur.isoformat() > until:
                    break
                dow = _WEEKDAY_NAMES[cur.weekday()]
                if not by_day or dow in by_day:
                    _add(ev, cur)
                cur += _td(days=interval if not by_day else 1)

    out.sort(key=lambda e: e["start"])
    return out


# ── Task Overrides (dismiss / postpone / set time) ───────────────────────────

def load_task_overrides() -> dict:
    """Load {child: {iso: {task_id: {action, ...}}}} override map."""
    return ensure_file(TASK_OVERRIDES_FILE, {})

def save_task_overrides(data: dict):
    safe_save_json(TASK_OVERRIDES_FILE, data)

def set_task_override(child: str, iso: str, task_id: str, override: dict):
    """
    Store an override for a task on a given day.
    override = {"action": "dismiss"|"postpone"|"timed",
                "postpone_to": "YYYY-MM-DD",   # for postpone
                "time": "HH:MM"}               # for timed
    """
    data = load_task_overrides()
    data.setdefault(child, {}).setdefault(iso, {})[task_id] = override
    save_task_overrides(data)

def clear_task_override(child: str, iso: str, task_id: str):
    data = load_task_overrides()
    data.get(child, {}).get(iso, {}).pop(task_id, None)
    save_task_overrides(data)

def get_day_overrides(child: str, iso: str) -> dict:
    """Return {task_id: override_dict} for a given person on a given day."""
    return load_task_overrides().get(child, {}).get(iso, {})

def get_postponed_for_day(child: str, iso: str) -> list:
    """
    Return task labels that were postponed TO this day from a previous day.
    Used to inject them back as manual-task-like items.
    """
    data = load_task_overrides()
    results = []
    for src_iso, tasks in data.get(child, {}).items():
        if src_iso >= iso:
            continue  # only look at past days
        for task_id, ov in tasks.items():
            if ov.get("action") == "postpone" and ov.get("postpone_to") == iso:
                results.append(ov.get("label", task_id))
# ── Curriculum Management System ─────────────────────────────────────────────

# Curriculum Library
def load_curriculum_library():
    """Load curriculum subjects, units, and assignments."""
    return ensure_file("data/curriculum_library.json", {
        "subjects": {},
        "next_subject_id": 1,
        "next_unit_id": 1,
        "next_assignment_id": 1
    })

def save_curriculum_library(data):
    """Save curriculum library data."""
    safe_save_json("data/curriculum_library.json", data)

def get_subject_by_id(subject_id: str):
    """Get a specific subject by ID."""
    library = load_curriculum_library()
    return library["subjects"].get(subject_id)

def get_assignments_for_student(student: str):
    """Get all assignments for a specific student across all subjects."""
    library = load_curriculum_library()
    assignments = []
    for subject in library["subjects"].values():
        if subject.get("student") == student:
            for unit in subject.get("units", []):
                for assignment in unit.get("assignments", []):
                    assignments.append({
                        "subject_name": subject["name"],
                        "subject_id": subject["id"],
                        "unit_name": unit["name"],
                        "assignment": assignment
                    })
    return assignments

# Student Submissions
def load_student_submissions():
    """Load student work submissions."""
    return ensure_file("data/student_submissions.json", {
        "submissions": [],
        "next_submission_id": 1
    })

def save_student_submissions(data):
    """Save student submissions data."""
    safe_save_json("data/student_submissions.json", data)

def add_student_submission(student: str, subject_id: str, assignment_id: str, file_path: str, notes: str = ""):
    """Add a new student submission."""
    data = load_student_submissions()
    submission = {
        "id": f"sub_{data['next_submission_id']:03d}",
        "student": student,
        "subject_id": subject_id,
        "assignment_id": assignment_id,
        "submitted_date": today_iso(),
        "file_path": file_path,
        "status": "pending_review",
        "notes": notes
    }
    data["submissions"].append(submission)
    data["next_submission_id"] += 1
    save_student_submissions(data)
    return submission

def get_submissions_for_grading():
    """Get all submissions pending review."""
    data = load_student_submissions()
    return [s for s in data["submissions"] if s["status"] == "pending_review"]

def get_submissions_by_student(student: str):
    """Get all submissions for a specific student."""
    data = load_student_submissions()
    return [s for s in data["submissions"] if s["student"] == student]

# Grading & Feedback
def load_grading_history():
    """Load completed grading records."""
    return ensure_file("data/grading_history.json", {
        "grades": [],
        "next_grade_id": 1
    })

def save_grading_history(data):
    """Save grading history data."""
    safe_save_json("data/grading_history.json", data)

def add_grade_record(submission_id: str, points_earned: int, points_possible: int, feedback: str, rubric_scores: dict = None):
    """Add a completed grade record and update submission status."""
    # Add to grading history
    history_data = load_grading_history()
    grade_record = {
        "id": f"grade_{history_data['next_grade_id']:03d}",
        "submission_id": submission_id,
        "graded_date": today_iso(),
        "points_earned": points_earned,
        "points_possible": points_possible,
        "percentage": round((points_earned / points_possible) * 100, 1) if points_possible > 0 else 0,
        "feedback": feedback,
        "rubric_scores": rubric_scores or {}
    }
    history_data["grades"].append(grade_record)
    history_data["next_grade_id"] += 1
    save_grading_history(history_data)
    
    # Update submission status
    submissions_data = load_student_submissions()
    for submission in submissions_data["submissions"]:
        if submission["id"] == submission_id:
            submission["status"] = "graded"
            submission["graded_date"] = today_iso()
            submission["points_earned"] = points_earned
            submission["points_possible"] = points_possible
            break
    save_student_submissions(submissions_data)
    
    return grade_record

# Reference Documents
def load_curriculum_documents():
    """Load curriculum reference documents."""
    return ensure_file("data/curriculum_documents.json", {
        "documents": [],
        "next_doc_id": 1
    })

def save_curriculum_documents(data):
    """Save curriculum documents data."""
    safe_save_json("data/curriculum_documents.json", data)

def add_curriculum_document(name: str, file_path: str, doc_type: str, subject_ids: list = None, description: str = ""):
    """Add a new curriculum reference document."""
    data = load_curriculum_documents()
    document = {
        "id": f"doc_{data['next_doc_id']:03d}",
        "name": name,
        "file_path": file_path,
        "doc_type": doc_type,  # syllabus, rubric, answer_key, resource
        "subject_ids": subject_ids or [],
        "description": description,
        "uploaded_date": today_iso()
    }
    data["documents"].append(document)
    data["next_doc_id"] += 1
    save_curriculum_documents(data)
    return document


# ─────────────────────────────────────────────────────────────────────────────
# Family Memory — shared cross-companion long-term memory store
# ─────────────────────────────────────────────────────────────────────────────
import re as _re_mem
import uuid as _uuid_mem
from datetime import datetime as _dt_mem

_MEM_STOPWORDS = {
    "a","an","the","is","are","was","were","be","been","being","am",
    "and","or","but","of","in","on","to","for","with","that","this",
    "it","its","i","you","he","she","they","we","my","your","their",
    "our","at","by","from","as","do","don","dont","not","no","yes",
    "have","has","had","will","would","could","should","can","may",
}


def load_family_memory() -> list:
    """Return the family memory list. Empty list if file missing/empty."""
    data = ensure_file(FAMILY_MEMORY_FILE, [])
    if isinstance(data, list):
        return data
    return []


def save_family_memory(memories: list) -> None:
    """Persist the full memory list."""
    safe_save_json(FAMILY_MEMORY_FILE, memories or [])


def _now_ts() -> str:
    return _dt_mem.now().strftime("%Y-%m-%dT%H:%M:%S")


def add_memory(text: str, category: str = "general") -> dict:
    """Append a new memory. Returns the saved record."""
    text = (text or "").strip()
    if not text:
        return {}
    cat = (category or "general").strip() or "general"
    now = _now_ts()
    rec = {
        "id":         _uuid_mem.uuid4().hex[:8],
        "text":       text,
        "category":   cat,
        "created_at": now,
        "updated_at": now,
    }
    mems = load_family_memory()
    mems.append(rec)
    save_family_memory(mems)
    return rec


def update_memory(memory_id: str, new_text: str) -> dict:
    """Replace the text of an existing memory in place. Returns the updated
    record, or {} if no memory matched."""
    memory_id = (memory_id or "").strip()
    new_text  = (new_text or "").strip()
    if not memory_id or not new_text:
        return {}
    mems = load_family_memory()
    for m in mems:
        if str(m.get("id","")).strip() == memory_id:
            m["text"]       = new_text
            m["updated_at"] = _now_ts()
            save_family_memory(mems)
            return m
    return {}


def delete_memory(memory_id: str) -> bool:
    """Remove a memory by id. Returns True if something was deleted."""
    memory_id = (memory_id or "").strip()
    if not memory_id:
        return False
    mems = load_family_memory()
    new  = [m for m in mems if str(m.get("id","")).strip() != memory_id]
    if len(new) != len(mems):
        save_family_memory(new)
        return True
    return False


def _tokenize_memory(text: str) -> set:
    """Lowercase alphanumeric tokens >= 2 chars, stopwords removed.
    Min length is 2 (not 3) so short proper-noun nicknames like 'JP' are
    retained for conflict detection — the _MEM_STOPWORDS set covers the
    common 2-char English noise words (am, an, as, at, be, by, do, he,
    in, it, my, no, of, on, or, to, we)."""
    if not text:
        return set()
    toks = _re_mem.findall(r"[a-z0-9]+", text.lower())
    return {t for t in toks if len(t) >= 2 and t not in _MEM_STOPWORDS}


def find_memory_conflicts(new_text: str, threshold: float = 0.5) -> list:
    """Return existing memories whose Jaccard token-overlap with new_text
    meets or exceeds `threshold`. Used to flag potential contradictions
    before silently saving a new memory."""
    new_toks = _tokenize_memory(new_text)
    if not new_toks:
        return []
    out = []
    for m in load_family_memory():
        old_toks = _tokenize_memory(m.get("text",""))
        if not old_toks:
            continue
        inter = new_toks & old_toks
        union = new_toks | old_toks
        if union and (len(inter) / len(union)) >= threshold:
            out.append(m)
    return out


def get_memory_context_block() -> str:
    """Return the FAMILY MEMORY system-prompt section — current memories
    grouped by category, plus the <remember> tag instructions. Designed
    to be appended verbatim to every companion's system prompt."""
    mems  = load_family_memory()
    lines = ["== FAMILY MEMORY (shared across all companions) =="]
    if mems:
        by_cat = {}
        for m in mems:
            by_cat.setdefault(str(m.get("category","general")), []).append(m)
        for cat in sorted(by_cat):
            lines.append("")
            lines.append(f"[{cat}]")
            for m in by_cat[cat]:
                _id  = str(m.get("id","?"))
                _txt = (m.get("text","") or "").strip()
                lines.append(f"  - ({_id}) {_txt}")
    else:
        lines.append("(No family memories saved yet.)")
    lines += [
        "",
        "REMEMBERING NEW THINGS:",
        "When Lauren says 'remember that...', 'note that...', 'don't forget...',",
        "'for the record...', or otherwise asks you to commit a fact to long-term",
        "memory, emit this tag at the end of your reply:",
        '    <remember category="family|food|school|health|faith|schedule|general">the fact</remember>',
        "The server saves it silently and strips the tag from what Lauren sees.",
        "Confirm naturally in plain English ('Got it — I will remember that.').",
        "",
        "CONFLICT HANDLING:",
        "If your <remember> contradicts something already in the FAMILY MEMORY",
        "above (similar keywords, different meaning), the server will block the",
        "silent save and prepend a yes/replace/keep-both/ignore question to your",
        "reply. When Lauren resolves the conflict in her next message:",
        '  - "replace" or "overwrite" --> emit  <remember replaces="OLD_ID">new text</remember>',
        '  - "keep both"              --> emit  <remember force="true" category="CAT">new text</remember>',
        '  - "ignore" / "never mind"  --> emit no tag.',
        "Use the parenthesized id (e.g. (a1b2c3d4)) shown above to reference an",
        "existing memory.",
        "",
        "USING MEMORIES:",
        "Treat the memory store as durable, cross-companion truth. Reference it",
        "naturally when relevant ('I see Joseph is gluten-intolerant, so let us",
        "swap pasta for rice'), but do not recite the whole list unless Lauren",
        "asks 'what do you remember about us?'.",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Prayer intentions + novenas (lightweight daily/repeating/novena ledger)
# Companion to the richer data/prayer/intentions.json store; used by the
# Lauren-only time-block homepage and the Sister Mary companion.
# ─────────────────────────────────────────────────────────────────────────────

_PI_DEFAULT = {"daily": [], "repeating": [], "novenas": []}


def load_prayer_intentions() -> dict:
    ensure_file(PRAYER_INTENTIONS_FILE, _PI_DEFAULT)
    import json as _json
    try:
        with open(PRAYER_INTENTIONS_FILE, "r") as f:
            d = _json.load(f)
    except Exception:
        d = dict(_PI_DEFAULT)
    if not isinstance(d, dict):
        d = dict(_PI_DEFAULT)
    d.setdefault("daily", [])
    d.setdefault("repeating", [])
    d.setdefault("novenas", [])
    return d


def save_prayer_intentions(d: dict) -> None:
    if not isinstance(d, dict):
        return
    d.setdefault("daily", [])
    d.setdefault("repeating", [])
    d.setdefault("novenas", [])
    safe_save_json(PRAYER_INTENTIONS_FILE, d)


def add_daily_intention(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty"}
    d = load_prayer_intentions()
    today_iso = date.today().isoformat()
    d["daily"].append({"text": text, "added_iso": today_iso})
    save_prayer_intentions(d)
    return {"ok": True, "text": text, "added_iso": today_iso}


def add_repeating_intention(text: str, start_date: str = "",
                            end_date: str = "", repeat_days=None) -> dict:
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty"}
    if not start_date:
        start_date = date.today().isoformat()
    if repeat_days is None or not isinstance(repeat_days, list):
        repeat_days = list(WEEKDAYS)
    d = load_prayer_intentions()
    entry = {
        "text": text,
        "start_date": start_date,
        "end_date": end_date or "",
        "repeat_days": repeat_days,
    }
    d["repeating"].append(entry)
    save_prayer_intentions(d)
    return {"ok": True, **entry}


def add_novena(saint: str, feast_date: str) -> dict:
    saint = (saint or "").strip()
    feast_date = (feast_date or "").strip()
    if not saint or not feast_date:
        return {"ok": False, "error": "missing saint or feast_date"}
    try:
        fd = date.fromisoformat(feast_date)
    except Exception:
        return {"ok": False, "error": "bad feast_date"}
    start = fd - timedelta(days=9)
    today = date.today()
    current_day = (today - start).days + 1
    if current_day < 1:
        current_day = 0  # not yet started
    elif current_day > 9:
        current_day = 9
    d = load_prayer_intentions()
    # Avoid duplicate novena for same saint/feast
    for n in d["novenas"]:
        if n.get("saint", "").lower() == saint.lower() and n.get("feast_date") == feast_date:
            return {"ok": False, "error": "duplicate", "novena": n}
    entry = {
        "saint": saint,
        "feast_date": feast_date,
        "start_date": start.isoformat(),
        "current_day": current_day,
        "total_days": 9,
    }
    d["novenas"].append(entry)
    save_prayer_intentions(d)
    return {"ok": True, **entry}


def get_active_intentions_for_date(iso: str) -> dict:
    try:
        target = date.fromisoformat(iso)
    except Exception:
        target = date.today()
        iso = target.isoformat()
    target_weekday = target.strftime("%A")
    d = load_prayer_intentions()

    daily = [e for e in d.get("daily", [])
             if isinstance(e, dict) and e.get("added_iso") == iso]

    repeating = []
    for e in d.get("repeating", []):
        if not isinstance(e, dict):
            continue
        sd = e.get("start_date", "")
        ed = e.get("end_date", "")
        days = e.get("repeat_days") or list(WEEKDAYS)
        try:
            if sd and date.fromisoformat(sd) > target:
                continue
            if ed and date.fromisoformat(ed) < target:
                continue
        except Exception:
            continue
        if target_weekday not in days:
            continue
        repeating.append(e)

    novenas = []
    for n in d.get("novenas", []):
        if not isinstance(n, dict):
            continue
        try:
            sd = date.fromisoformat(n.get("start_date", ""))
        except Exception:
            continue
        end = sd + timedelta(days=9)
        if sd <= target <= end:
            day_num = (target - sd).days + 1
            if day_num < 1:
                day_num = 1
            if day_num > 9:
                day_num = 9
            row = dict(n)
            row["current_day"] = day_num
            novenas.append(row)

    return {"daily": daily, "repeating": repeating, "novenas": novenas}


def check_upcoming_novenas() -> list:
    """Return feasts in the next 9 days that don't already have an active novena.

    Each entry: {"saint": str, "feast_date": "YYYY-MM-DD", "days_away": int}.
    """
    try:
        from render_liturgical import get_day_info
    except Exception:
        return []
    today = date.today()
    d = load_prayer_intentions()
    existing_keys = set()
    for n in d.get("novenas", []):
        if not isinstance(n, dict):
            continue
        existing_keys.add((n.get("saint", "").strip().lower(), n.get("feast_date", "")))

    out = []
    for offset in range(1, 10):
        day = today + timedelta(days=offset)
        try:
            info = get_day_info(day)
        except Exception:
            continue
        feast = (info.get("feast_name") or "").strip()
        if not feast:
            continue
        iso = day.isoformat()
        if (feast.lower(), iso) in existing_keys:
            continue
        out.append({"saint": feast, "feast_date": iso, "days_away": offset})
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Pope's monthly intentions
# ─────────────────────────────────────────────────────────────────────────────

def load_pope_intentions() -> dict:
    ensure_file(POPE_INTENTIONS_FILE, {})
    import json as _json
    try:
        with open(POPE_INTENTIONS_FILE, "r") as f:
            d = _json.load(f)
    except Exception:
        d = {}
    if not isinstance(d, dict):
        d = {}
    return d


def save_pope_intentions(d: dict) -> None:
    if not isinstance(d, dict):
        return
    safe_save_json(POPE_INTENTIONS_FILE, d)


def get_pope_intention_for_month(iso: str = "") -> str:
    if not iso:
        iso = date.today().isoformat()
    try:
        ym = iso[:7]
    except Exception:
        ym = date.today().isoformat()[:7]
    d = load_pope_intentions()
    return (d.get(ym) or "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Sister Mary chat history
# ─────────────────────────────────────────────────────────────────────────────

SISTER_MARY_CONTEXT_MAX = 30


def load_sister_mary_history() -> list:
    ensure_file(SISTER_MARY_HISTORY_FILE, [])
    import json as _json
    try:
        with open(SISTER_MARY_HISTORY_FILE, "r") as f:
            d = _json.load(f)
    except Exception:
        d = []
    if not isinstance(d, list):
        d = []
    return d


def save_sister_mary_history(history: list) -> None:
    if not isinstance(history, list):
        return
    safe_save_json(SISTER_MARY_HISTORY_FILE, history)


def append_sister_mary_messages(msgs: list) -> list:
    if not isinstance(msgs, list) or not msgs:
        return load_sister_mary_history()
    history = load_sister_mary_history()
    history.extend(msgs)
    # Cap retained history to avoid unbounded growth (keep last 200 turns)
    if len(history) > 400:
        history = history[-400:]
    save_sister_mary_history(history)
    return history


def clear_sister_mary_history() -> bool:
    return _safe_clear(SISTER_MARY_HISTORY_FILE)
