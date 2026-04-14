"""
data_helpers.py — All data loading, saving, and utility functions.
Imports from: config, safe_utils, daily_schedule_engine, notes_router
"""
from datetime import date, timedelta
from safe_utils import ensure_file, safe_save_json, debug_log
from daily_schedule_engine import CHILDREN

from config import (
    MANUAL_TASKS_FILE, CHORES_FILE, MOM_NOTES_FILE, ROADMAP_FILE,
    LITURGICAL_FILE, FAMILY_SCHEDULE_FILE, CALENDAR_CONFIG_FILE,
    CALENDAR_CACHE_FILE, MONTHLY_PLANNER_FILE, CALENDAR_RULES_FILE,
    SUBSCRIBED_CALS_FILE, SUBSCRIBED_CACHE_FILE, VALID_PRIORITIES, VALID_STATUSES, WEEKDAYS,
    WEEKDAY_ORDER, CURRICULUM_FILE, TASK_OVERRIDES_FILE,
)


# ── Snapshot stubs (system removed) ─────────────────────────────────────────
def list_snapshots() -> list:
    return []

def restore_snapshot(filename: str) -> tuple:
    return False, "Snapshot system not available"


# ── Date helpers ─────────────────────────────────────────────────────────────
def today_iso() -> str:
    return date.today().isoformat()

def tomorrow_iso() -> str:
    return (date.today() + timedelta(days=1)).isoformat()

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

def advance_recurring_task(task: dict) -> dict:
    """Given a completed recurring task, return it reset with the next due date."""
    import calendar as _cal
    unit  = task.get("interval_unit", "weeks")
    value = safe_int(task.get("interval_value", 1), 1)
    if value < 1:
        value = 1
    base_str = task.get("due_date", "") or date.today().isoformat()
    try:
        base = date.fromisoformat(base_str)
    except Exception:
        base = date.today()

    # ── Monthly "Nth weekday" patterns ─────────────────────────────────────
    _weekday_patterns = {
        "monthly_last_sat": (5, -1),  # Saturday, last occurrence
        "monthly_last_sun": (6, -1),  # Sunday, last occurrence
        "monthly_last_fri": (4, -1),  # Friday, last occurrence
        "monthly_first_sat": (5, 1),  # Saturday, first occurrence
        "monthly_first_sun": (6, 1),  # Sunday, first occurrence
        "monthly_first_fri": (4, 1),  # Friday, first occurrence
    }
    if unit in _weekday_patterns:
        wd, nth = _weekday_patterns[unit]
        # Advance to the next calendar month
        nm = base.month + 1
        ny = base.year + (nm - 1) // 12
        nm = (nm - 1) % 12 + 1
        last_day = _cal.monthrange(ny, nm)[1]
        if nth == -1:
            # Last occurrence: start from end of month, walk back
            d = date(ny, nm, last_day)
            while d.weekday() != wd:
                d -= timedelta(days=1)
        else:
            # First occurrence: start from day 1, walk forward
            d = date(ny, nm, 1)
            while d.weekday() != wd:
                d += timedelta(days=1)
        next_due = d
    elif unit == "weekdays":
        # Advance 1 day at a time, skipping Saturday (5) and Sunday (6)
        next_due = base + timedelta(days=1)
        while next_due.weekday() >= 5:
            next_due += timedelta(days=1)
    elif unit == "days":
        next_due = base + timedelta(days=value)
    elif unit == "months":
        month = base.month - 1 + value
        year  = base.year + month // 12
        month = month % 12 + 1
        day   = min(base.day, _cal.monthrange(year, month)[1])
        next_due = base.replace(year=year, month=month, day=day)
    else:
        next_due = base + timedelta(weeks=value)

    task = dict(task)
    task["due_date"] = next_due.isoformat()
    task["status"]   = "active"
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
    Falls back to 'Mom' or the first available person if the requested one is
    not found.  Returns an empty dict when no template exists for that day.
    """
    import json as _json
    from pathlib import Path as _Path
    p = _Path(f"data/day_templates/{weekday}.json")
    if not p.exists():
        return {}
    grid = _json.loads(p.read_text(encoding="utf-8")).get("grid", {})
    # Lauren / Mom are the same person
    aliases = {"Lauren": "Mom", "Mom": "Lauren"}
    for candidate in [person, aliases.get(person, ""), "Mom", "JP"]:
        if candidate and candidate in grid and grid[candidate]:
            return dict(grid[candidate])
    return {}


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

def clear_lucy_history():
    """Wipe the history file."""
    safe_save_json(LUCY_HISTORY_FILE, {"messages": []})


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

def clear_lorenzo_history():
    safe_save_json(LORENZO_HISTORY_FILE, {"messages": []})


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

def clear_gregory_history():
    safe_save_json(GREGORY_HISTORY_FILE, {"messages": []})


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

def clear_coach_history():
    safe_save_json(COACH_HISTORY_FILE, {"messages": []})


# ── Felix (Dev) history ───────────────────────────────────────────────────────
DEV_HISTORY_FILE = "data/dev_history.json"
DEV_HISTORY_MAX  = 20   # keep last 20 turns in file
DEV_CONTEXT_MAX  = 12   # messages sent to Claude per request (file reads now persist, need more room)

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

def clear_dev_history():
    safe_save_json(DEV_HISTORY_FILE, {"messages": []})


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

def clear_monica_history():
    safe_save_json(MONICA_HISTORY_FILE, {"messages": []})


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


# ── Recipe cards ─────────────────────────────────────────────────────────────
RECIPES_FILE = "data/recipes.json"

def load_recipes() -> list:
    data = ensure_file(RECIPES_FILE, {"recipes": []})
    # Legacy format: top-level list
    if isinstance(data, list):
        return data
    return data.get("recipes", [])

def save_recipes(recipes: list):
    safe_save_json(RECIPES_FILE, {"recipes": recipes})

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
                    " ".join(r.get("ingredients", [])) + " " +
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


def get_curriculum_week_assignments(child: str, week: int) -> dict:
    """
    Return {subject: assignment_text} for a child on a specific week.
    Only includes subjects that have an assignment for that week.
    """
    subjects = get_curriculum_subjects(child)
    result = {}
    week_str = str(week)
    for subject, weeks in subjects.items():
        text = weeks.get(week_str, "").strip()
        if text:
            result[subject] = text
    return result

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
    return results
