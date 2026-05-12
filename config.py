"""
config.py — All application-wide constants.
No logic, no imports from other app modules.
Runtime-overridable values (child colors, van epoch, timezone) are
loaded from data/app_settings.json if it exists.
"""
import os
from datetime import date
from daily_schedule_engine import CHILDREN

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8000))

# ── Data file paths ──────────────────────────────────────────────────────────
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

# ── Validation sets ──────────────────────────────────────────────────────────
VALID_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}
VALID_STATUSES   = {"active", "done", "inactive"}

# ── Time / calendar ──────────────────────────────────────────────────────────
WEEKDAYS      = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_ORDER = {day: i for i, day in enumerate(WEEKDAYS)}
SCHEDULE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
MONTH_NAMES   = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December",
]

# ── Task / roadmap ───────────────────────────────────────────────────────────
ROADMAP_STATUSES = ["Someday", "Ready", "In Progress", "Done"]
ASSIGNABLE_TO    = ["Mom"] + list(CHILDREN)

# ── Child identity (defaults — overridden at runtime from app_settings.json) ─
_DEFAULT_CHILD_COLORS = {
    "JP":      {"bg": "#c0392b", "text": "#fff", "light": "#fdf0ef"},
    "Joseph":  {"bg": "#27ae60", "text": "#fff", "light": "#edfaf3"},
    "Michael": {"bg": "#e67e22", "text": "#fff", "light": "#fef6ed"},
    "James":   {"bg": "#2980b9", "text": "#fff", "light": "#eaf4fb"},
}

def _load_child_colors() -> dict:
    """Read child colors from app_settings.json, fall back to defaults."""
    try:
        import json
        if os.path.exists(APP_SETTINGS_FILE):
            data = json.load(open(APP_SETTINGS_FILE))
            stored = data.get("child_colors", {})
            if stored:
                merged = dict(_DEFAULT_CHILD_COLORS)
                merged.update(stored)
                return merged
    except Exception:
        pass
    return dict(_DEFAULT_CHILD_COLORS)

CHILD_COLORS = _load_child_colors()

def child_color(child: str, key: str = "bg") -> str:
    # Re-read each call so settings changes take effect without restart
    colors = _load_child_colors()
    return colors.get(child, {}).get(key, "#888")

_DEFAULT_PARENT_COLORS = {
    "Lauren": {"bg": "#7c3aed", "light": "#f5f3ff"},
    "John":   {"bg": "#2563eb", "light": "#eff6ff"},
}

def parent_color(name: str, key: str = "bg") -> str:
    """Return Lauren's or John's accent color from settings (or defaults)."""
    try:
        import json
        if os.path.exists(APP_SETTINGS_FILE):
            data = json.load(open(APP_SETTINGS_FILE))
            stored = data.get("parent_colors", {})
            if name in stored:
                return stored[name].get(key, _DEFAULT_PARENT_COLORS.get(name, {}).get(key, "#888"))
    except Exception:
        pass
    return _DEFAULT_PARENT_COLORS.get(name, {}).get(key, "#888")

# ── Van rotation ─────────────────────────────────────────────────────────────
def _load_van_epoch() -> date:
    """Read van epoch from app_settings.json, fall back to default."""
    try:
        import json
        if os.path.exists(APP_SETTINGS_FILE):
            data = json.load(open(APP_SETTINGS_FILE))
            ep = data.get("van_epoch", "")
            if ep:
                return date.fromisoformat(ep)
    except Exception:
        pass
    return date(2025, 1, 6)

def get_van_epoch() -> date:
    return _load_van_epoch()

# Keep module-level name for backwards compatibility
VAN_ROTATION_EPOCH = _load_van_epoch()
VAN_ROLE_A = "Interior Reset Lead"
VAN_ROLE_B = "Bin & Organization Lead"

# ── App-level settings helpers ───────────────────────────────────────────────
def get_app_setting(key: str, default=None):
    """Read a single value from app_settings.json."""
    try:
        import json
        if os.path.exists(APP_SETTINGS_FILE):
            data = json.load(open(APP_SETTINGS_FILE))
            return data.get(key, default)
    except Exception:
        pass
    return default

def get_family_name() -> str:
    return get_app_setting("family_name", "Our Family")

def get_timezone() -> str:
    return get_app_setting("timezone", "America/New_York")

def get_schedule_hours() -> tuple:
    """Return (start_hour, end_hour) as ints."""
    start = int(get_app_setting("schedule_start_hour", 6))
    end   = int(get_app_setting("schedule_end_hour",   22))
    return start, end