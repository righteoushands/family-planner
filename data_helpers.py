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
    WEEKDAY_ORDER,
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
    if unit == "days":
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
    safe_save_json(CHORES_FILE, data)


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


# ── Family schedule ──────────────────────────────────────────────────────────
def load_family_schedule() -> dict:
    return ensure_file(FAMILY_SCHEDULE_FILE, {"times": [], "days": {}})

def save_family_schedule(data: dict):
    safe_save_json(FAMILY_SCHEDULE_FILE, data)


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