import json
from datetime import date, timedelta
from pathlib import Path

from safe_utils import (
    ensure_file,
    safe_save_json,
    debug_log,
)
from school_pdf_engine import get_school_assignments_for_weekday

CHORES_FILE = "data/chores.json"
PROGRESS_FILE = "data/progress.json"
TASK_REGISTRY_FILE = "data/task_registry.json"
MANUAL_TASKS_FILE = "data/manual_tasks.json"
CALENDAR_CACHE_FILE = "data/subscribed_calendar_cache.json"
CALENDAR_RULES_FILE = "data/calendar_rules.json"

CHILDREN = ["JP", "Joseph", "Michael", "James"]

PRIORITY_ORDER = {
    "HIGH": 0,
    "MEDIUM": 1,
    "LOW": 2,
}

# ── Rule of Life: default time anchors for sorting when no explicit time ──────
# These reflect the McAdams family's daily rhythm.
RULE_OF_LIFE_ANCHORS = {
    "carryover":     "06:30",
    "manual_HIGH":   "07:00",
    "school":        "08:30",
    "manual_MEDIUM": "09:00",
    "manual_LOW":    "15:00",
    "chore":         "15:30",
}


# ── Calendar events for the boys ─────────────────────────────────────────────

def get_calendar_events_for_boys(iso: str) -> list:
    """
    Return calendar events on the given date (YYYY-MM-DD) relevant to the boys.
    Filters out events blocked in calendar_rules.json (e.g., Dad's class).
    Returns sorted list of dicts: {title, time (HH:MM|None), end_time, all_day, location}
    """
    try:
        cache = json.loads(Path(CALENDAR_CACHE_FILE).read_text(encoding="utf-8"))
        events = cache.get("events", [])
    except Exception:
        return []
    try:
        rules = json.loads(Path(CALENDAR_RULES_FILE).read_text(encoding="utf-8"))
        blocked = {t.strip().lower() for t in rules.get("blocked_event_titles", [])}
    except Exception:
        blocked = set()

    result = []
    for e in events:
        start = e.get("start", "")
        if not start.startswith(iso):
            continue
        title = str(e.get("title", "")).strip()
        if not title or title.lower() in blocked:
            continue
        time_part = start.split("T")[1][:5] if "T" in start else None
        end       = e.get("end", "")
        end_time  = end.split("T")[1][:5] if "T" in end else None
        result.append({
            "title":    title,
            "time":     time_part,
            "end_time": end_time,
            "all_day":  bool(e.get("all_day", False)),
            "location": str(e.get("location", "") or ""),
        })
    result.sort(key=lambda ev: ("00:00" if ev["all_day"] else (ev["time"] or "23:59")))
    return result


def fmt_time_12h(hhmm: str | None) -> str:
    """Convert 'HH:MM' to '11:30 AM'. Returns '' if None."""
    if not hhmm:
        return ""
    try:
        h, m = int(hhmm[:2]), int(hhmm[3:5])
        suffix = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {suffix}"
    except Exception:
        return hhmm


# -------------------------
# DATE HELPERS
# -------------------------

def normalize_target_date(target_date_str: str = "") -> date:
    if target_date_str:
        try:
            return date.fromisoformat(target_date_str)
        except Exception:
            debug_log("Invalid date string, falling back to today:", target_date_str)
    return date.today()


def date_info(target_date_str: str = ""):
    target = normalize_target_date(target_date_str)
    return (
        target.strftime("%A"),
        target.strftime("%B %d, %Y"),
        target.isoformat(),
        target,
    )


# -------------------------
# PROGRESS
# -------------------------

def load_progress():
    data = ensure_file(PROGRESS_FILE, {})
    return data if isinstance(data, dict) else {}


def save_progress(progress):
    safe_save_json(PROGRESS_FILE, progress)


def make_task_id(child: str, iso: str, text: str) -> str:
    return f"{iso}::{child}::{text.strip()}"


def get_task_done(progress: dict, task_id: str) -> bool:
    return bool(progress.get(task_id, False))


def set_task_done(task_id: str, is_done: bool):
    progress = load_progress()

    if is_done:
        progress[task_id] = True
    else:
        progress.pop(task_id, None)

    save_progress(progress)


# -------------------------
# TASK REGISTRY
# -------------------------

def load_task_registry():
    data = ensure_file(TASK_REGISTRY_FILE, {})
    return data if isinstance(data, dict) else {}


def save_task_registry(registry):
    safe_save_json(TASK_REGISTRY_FILE, registry)


def register_tasks_for_day(child: str, iso: str, task_texts: list[str]):
    registry = load_task_registry()
    registry.setdefault(iso, {})
    registry[iso][child] = sorted(
        set(t.strip() for t in task_texts if t and t.strip())
    )
    save_task_registry(registry)


def get_registered_tasks_for_day(child: str, iso: str) -> list[str]:
    registry = load_task_registry()
    return registry.get(iso, {}).get(child, [])


# -------------------------
# CHORES
# -------------------------

def load_chores():
    data = ensure_file(CHORES_FILE, {"boys": {}})
    return data if isinstance(data, dict) else {"boys": {}}


def weekday_chores_for_child(child: str, weekday: str):
    chores = load_chores()
    # "Mom" / "Lauren" uses the top-level "lauren" section
    if child in ("Mom", "Lauren"):
        section = chores.get("lauren", {})
    else:
        section = chores.get("boys", {}).get(child, {})
    daily  = [t for t in (section.get("daily",  []) or []) if str(t).strip()]
    weekly = [t for t in ((section.get("weekly", {}) or {}).get(weekday, []) or []) if str(t).strip()]
    return daily + weekly


# -------------------------
# MANUAL TASKS
# -------------------------

def load_manual_tasks():
    data = ensure_file(MANUAL_TASKS_FILE, [])
    return data if isinstance(data, list) else []


def normalize_priority(value: str) -> str:
    value = str(value or "").strip().upper()
    if value in PRIORITY_ORDER:
        return value
    return "MEDIUM"


def get_manual_tasks_for_child_and_date(child: str, iso: str):
    tasks = load_manual_tasks()
    results = []

    for task in tasks:
        if not isinstance(task, dict):
            continue

        if str(task.get("status", "active")).strip().upper() != "ACTIVE":
            continue

        task_child = str(task.get("assigned_to", "")).strip()
        task_date = str(task.get("due_date", "")).strip()

        if task_child and task_child != child:
            continue

        if task_date and task_date != iso:
            continue

        text = str(task.get("text", "")).strip()
        if not text:
            continue

        priority = normalize_priority(task.get("priority", "MEDIUM"))

        results.append({
            "text": text,
            "priority": priority,
        })

    results.sort(key=lambda item: (PRIORITY_ORDER.get(item["priority"], 1), item["text"].lower()))
    return results


# -------------------------
# SCHOOL TASKS
# -------------------------

def extract_school_tasks_for_child(child: str, weekday: str):
    assignments = get_school_assignments_for_weekday(weekday)
    day = assignments.get(child, {})
    tasks = []

    for block in day.get("blocks", []):
        subject = block.get("subject", "").strip()
        text = block.get("assignment_text", "").strip()
        is_math = bool(block.get("is_math", False))
        is_math_test = bool(block.get("is_math_test", False))

        checklist = []
        if is_math_test:
            # Tests get a single done checkbox — no peer-checking workflow
            checklist.append("Test completed — given to Mom")
        elif is_math:
            checklist.extend([
                "Assignment completed",
                "Given to checker",
                "Fixed missed problems",
                "Received brother's math",
                "Checked brother's math",
            ])
        else:
            # Every other subject gets at least a simple Done checkbox
            checklist.append("Done")

        tasks.append({
            "subject": subject,
            "assignment_text": text,
            "is_math": is_math,
            "is_math_test": is_math_test,
            "checklist": checklist,
        })

    return tasks


# -------------------------
# CARRYOVER (HUMAN-FRIENDLY)
# -------------------------

def format_task_text(task_text: str) -> str:
    if task_text.startswith("SCHOOL::"):
        parts = task_text.split("::", 2)
        if len(parts) == 3:
            _, subject, item = parts
            subject = subject.strip()
            item = item.strip()
            if subject:
                return f"{subject} — {item}"
            return item

    if task_text.startswith("CHORE::"):
        parts = task_text.split("::", 1)
        if len(parts) == 2:
            return parts[1].strip()

    if task_text.startswith("MANUAL::"):
        parts = task_text.split("::", 2)
        if len(parts) == 3:
            _, priority, text = parts
            priority = normalize_priority(priority)
            text = text.strip()
            return f"[{priority}] {text}"
        if len(parts) == 2:
            return parts[1].strip()

    return task_text


def get_carryover_tasks(child: str, target_day: date):
    progress = load_progress()

    # Look back up to 7 days to find the most recent day that had registered tasks.
    # This ensures Friday's unfinished tasks appear on Monday even after a weekend
    # or holiday with no registered tasks.
    previous_tasks = []
    prev_iso = ""
    for days_back in range(1, 8):
        check_day = target_day - timedelta(days=days_back)
        check_iso = check_day.isoformat()
        found = get_registered_tasks_for_day(child, check_iso)
        if found:
            previous_tasks = found
            prev_iso = check_iso
            break

    if not previous_tasks:
        return []

    carryover = []
    for task_text in previous_tasks:
        previous_task_id = make_task_id(child, prev_iso, task_text)
        if not get_task_done(progress, previous_task_id):
            carryover.append(task_text)

    carryover.sort(key=carryover_sort_key)
    return [format_task_text(item) for item in carryover]


def dismiss_carryover_items(child: str, target_day: date, items_to_keep: list = None) -> int:
    """Mark carryover items as done so they stop carrying over.

    items_to_keep: list of human-readable display strings to KEEP (leave as-is).
                   Items whose display text is NOT in this list are marked done.
                   Pass None (default) to dismiss ALL carryover items.
    Returns the count of items dismissed.
    """
    # Find the source day (same logic as get_carryover_tasks)
    prev_tasks_raw = []
    prev_iso = ""
    for days_back in range(1, 8):
        check_day = target_day - timedelta(days=days_back)
        check_iso = check_day.isoformat()
        found = get_registered_tasks_for_day(child, check_iso)
        if found:
            prev_tasks_raw = found
            prev_iso = check_iso
            break

    if not prev_tasks_raw or not prev_iso:
        return 0

    # Normalise keep-list for case-insensitive matching
    keep_set = None
    if items_to_keep is not None:
        keep_set = {s.strip().lower() for s in items_to_keep if s.strip()}

    progress = load_progress()
    dismissed = 0
    changed = False
    for raw_text in prev_tasks_raw:
        task_id = make_task_id(child, prev_iso, raw_text)
        if get_task_done(progress, task_id):
            continue  # already marked done
        display = format_task_text(raw_text)
        if keep_set is None or display.strip().lower() not in keep_set:
            progress[task_id] = True
            dismissed += 1
            changed = True
    if changed:
        save_progress(progress)
    return dismissed


def carryover_sort_key(task_text: str):
    if task_text.startswith("MANUAL::"):
        parts = task_text.split("::", 2)
        if len(parts) == 3:
            return (0, PRIORITY_ORDER.get(normalize_priority(parts[1]), 1), parts[2].lower())
    if task_text.startswith("SCHOOL::"):
        return (1, 0, task_text.lower())
    if task_text.startswith("CHORE::"):
        return (2, 0, task_text.lower())
    return (3, 0, task_text.lower())


# -------------------------
# INTERNAL TASK BUILDERS
# -------------------------

def build_task_texts_for_day(child: str, weekday: str, iso: str):
    school_tasks = extract_school_tasks_for_child(child, weekday)
    chore_tasks = weekday_chores_for_child(child, weekday)
    manual_tasks = get_manual_tasks_for_child_and_date(child, iso)

    all_task_texts = []

    for block in school_tasks:
        subject = block.get("subject", "").strip()

        for checklist_item in block.get("checklist", []):
            all_task_texts.append(f"SCHOOL::{subject}::{checklist_item}")

    for chore in chore_tasks:
        all_task_texts.append(f"CHORE::{chore}")

    for task in manual_tasks:
        all_task_texts.append(f"MANUAL::{task['priority']}::{task['text']}")

    return {
        "school_tasks": school_tasks,
        "chore_tasks": chore_tasks,
        "manual_tasks": manual_tasks,
        "all_task_texts": all_task_texts,
    }


# -------------------------
# TEXT GENERATION
# -------------------------

def generate_schedule_text(child: str, weekday: str, date_label: str, iso: str):
    built = build_task_texts_for_day(child, weekday, iso)
    school_tasks = built["school_tasks"]
    chore_tasks = built["chore_tasks"]
    manual_tasks = built["manual_tasks"]

    register_tasks_for_day(child, iso, built["all_task_texts"])

    carryover = get_carryover_tasks(child, normalize_target_date(iso))

    return _render_schedule_text(child, weekday, date_label, school_tasks, chore_tasks, manual_tasks, carryover)


def _render_schedule_text(child, weekday, date_label, school_tasks, chore_tasks, manual_tasks, carryover):
    """
    Pure text renderer. Takes already-computed task lists and produces
    the plain-text schedule string. Called by both generate_schedule_text
    and build_schedule_payload so we never compute tasks twice.
    """
    lines = [
        f"{child} — {date_label}",
        "=" * 40,
        "",
        "DAY",
        weekday,
        "",
    ]

    if carryover:
        lines.extend(["CARRYOVER"])
        for item in carryover:
            lines.append(f"☐ {item}")
        lines.extend(["", "-" * 30, ""])

    if manual_tasks:
        lines.extend(["MANUAL TASKS", ""])
        for task in manual_tasks:
            lines.append(f"☐ [{task['priority']}] {task['text']}")
        lines.extend(["", "-" * 30, ""])

    if school_tasks:
        lines.extend(["SCHOOL", ""])
        for block in school_tasks:
            if block["subject"]:
                lines.append(block["subject"].upper())

            if block["is_math_test"]:
                lines.extend(["TEST — bring to Mom for review", ""])
            elif block["is_math"]:
                lines.extend([
                    "Do all Lesson Practice and only the problems from the Mixed Practice from the last four lessons.",
                    "",
                ])

            for checklist_item in block["checklist"]:
                lines.append(f"☐ {checklist_item}")

            if block["checklist"]:
                lines.append("")

            if block["assignment_text"]:
                lines.extend([block["assignment_text"], ""])

            lines.extend(["-" * 30, ""])

    if chore_tasks:
        lines.extend(["CHORES / JOBS", ""])
        for chore in chore_tasks:
            lines.append(f"☐ {chore}")
        lines.extend(["", "-" * 30, ""])

    return "\n".join(lines).strip()


# -------------------------
# PAYLOAD BUILDERS
# -------------------------

_SCHOOL_FILTER_CACHE = None
_SCHOOL_FILTER_TIME  = 0.0
_SCHOOL_FILTER_TTL   = 60.0  # seconds — short enough to pick up Settings changes quickly

def _get_school_filter():
    """
    Return (mode, allowed_set, excluded_set). Cached for 60 seconds to avoid
    reading app_settings.json on every child's build_schedule_payload() call.
    """
    global _SCHOOL_FILTER_CACHE, _SCHOOL_FILTER_TIME
    import time as _t
    if _SCHOOL_FILTER_CACHE is not None and (_t.time() - _SCHOOL_FILTER_TIME) < _SCHOOL_FILTER_TTL:
        return _SCHOOL_FILTER_CACHE
    try:
        import json as _j
        with open("data/app_settings.json") as _f:
            _s = _j.load(_f)
        fc   = _s.get("family_constraints", {})
        mode = fc.get("school_mode", "normal")
        if mode == "light_week":
            core = fc.get("core_subjects", "Math, Religion, Reading")
            allowed = {k.strip().lower() for k in core.split(",") if k.strip()}
            result = (mode, allowed, None)
        elif mode == "custom_pause":
            paused = fc.get("paused_subjects", "")
            excluded = {k.strip().lower() for k in paused.split(",") if k.strip()}
            result = (mode, None, excluded)
        else:
            result = ("normal", None, None)
    except Exception:
        result = ("normal", None, None)
    _SCHOOL_FILTER_CACHE = result
    _SCHOOL_FILTER_TIME  = _t.time()
    return result


def _subject_visible(subject: str, mode: str, allowed: set, excluded: set) -> bool:
    """Return True if a school subject should be shown given the current filter."""
    if mode == "normal":
        return True
    subj_lower = subject.lower()
    if mode == "light_week" and allowed:
        return any(kw in subj_lower for kw in allowed)
    if mode == "custom_pause" and excluded:
        return not any(kw in subj_lower for kw in excluded)
    return True


def build_schedule_payload(child: str, weekday: str, date_label: str, iso: str):
    built = build_task_texts_for_day(child, weekday, iso)
    school_tasks = built["school_tasks"]
    chore_tasks = built["chore_tasks"]
    manual_tasks = built["manual_tasks"]

    register_tasks_for_day(child, iso, built["all_task_texts"])

    carryover = get_carryover_tasks(child, normalize_target_date(iso))
    progress = load_progress()

    carryover_items = []
    for text in carryover:
        task_id = make_task_id(child, iso, text)
        carryover_items.append({
            "text": text,
            "task_id": task_id,
            "done": get_task_done(progress, task_id),
            "priority": "MEDIUM",
        })

    manual_task_items = []
    for task in manual_tasks:
        task_text = f"MANUAL::{task['priority']}::{task['text']}"
        task_id = make_task_id(child, iso, task_text)
        manual_task_items.append({
            "text": task["text"],
            "task_id": task_id,
            "done": get_task_done(progress, task_id),
            "priority": task["priority"],
        })

    _sm_mode, _sm_allowed, _sm_excluded = _get_school_filter()

    school_blocks = []
    for block in school_tasks:
        # Apply school mode filter
        if not _subject_visible(block["subject"], _sm_mode, _sm_allowed, _sm_excluded):
            continue
        items = []
        for checklist_item in block["checklist"]:
            task_text = f"SCHOOL::{block['subject']}::{checklist_item}"
            task_id = make_task_id(child, iso, task_text)
            items.append({
                "text": checklist_item,
                "task_id": task_id,
                "done": get_task_done(progress, task_id),
                "priority": "MEDIUM",
            })

        school_blocks.append({
            "subject": block["subject"],
            "assignment_text": block["assignment_text"],
            "is_math": block["is_math"],
            "is_math_test": block["is_math_test"],
            "items": items,
        })

    chore_items = []
    for text in chore_tasks:
        task_text = f"CHORE::{text}"
        task_id = make_task_id(child, iso, task_text)
        chore_items.append({
            "text": text,
            "task_id": task_id,
            "done": get_task_done(progress, task_id),
            "priority": "MEDIUM",
        })

    # Re-use already-computed data for text — no second pass through the engine
    schedule_text = _render_schedule_text(
        child, weekday, date_label,
        school_tasks, chore_tasks, manual_tasks, carryover
    )

    calendar_items = get_calendar_events_for_boys(iso)

    return {
        "child": child,
        "weekday": weekday,
        "date_label": date_label,
        "iso": iso,
        "text": schedule_text,
        "carryover_items": carryover_items,
        "manual_task_items": manual_task_items,
        "school_blocks": school_blocks,
        "chore_items": chore_items,
        "calendar_items": calendar_items,
    }


# -------------------------
# PACKETS
# -------------------------

def generate_day_packet(target_date_str: str = ""):
    weekday, date_label, iso, _ = date_info(target_date_str)

    schedules = {}
    for child in CHILDREN:
        schedules[child] = generate_schedule_text(child, weekday, date_label, iso)

    return {
        "weekday": weekday,
        "date_label": date_label,
        "iso": iso,
        "schedules": schedules,
    }


def generate_week_packet(target_date_str: str = ""):
    target = normalize_target_date(target_date_str)
    monday = target - timedelta(days=target.weekday())

    days = []

    for offset in range(5):
        current = monday + timedelta(days=offset)
        weekday = current.strftime("%A")
        date_label = current.strftime("%B %d, %Y")
        iso = current.isoformat()

        schedules = {}
        for child in CHILDREN:
            schedules[child] = generate_schedule_text(child, weekday, date_label, iso)

        days.append({
            "weekday": weekday,
            "date_label": date_label,
            "iso": iso,
            "schedules": schedules,
        })

    return {
        "week_of": monday.isoformat(),
        "days": days,
    }


# -------------------------
# LIVE TASK SNAPSHOT
# -------------------------

def boys_task_snapshot(iso: str = "") -> dict:
    """
    Return live task state for all four boys for a given date (defaults to today).
    Each task carries its completion state from progress.json.
    Returns a structured dict with children keyed by name.
    """
    target = normalize_target_date(iso)
    iso_str = target.isoformat()
    weekday = target.strftime("%A")
    date_label = target.strftime("%B %d, %Y")

    children_data = {}
    for child in CHILDREN:
        try:
            payload = build_schedule_payload(child, weekday, date_label, iso_str)
        except Exception:
            children_data[child] = {"error": "could not build payload"}
            continue

        carryover = [
            {"text": i["text"], "done": i["done"], "task_id": i["task_id"]}
            for i in payload.get("carryover_items", [])
        ]
        school = [
            {
                "subject": b["subject"],
                "items": [
                    {"text": ci["text"], "done": ci["done"], "task_id": ci["task_id"]}
                    for ci in b.get("items", [])
                ],
            }
            for b in payload.get("school_blocks", [])
        ]
        chores = [
            {"text": i["text"], "done": i["done"], "task_id": i["task_id"]}
            for i in payload.get("chore_items", [])
        ]
        manual = [
            {"text": i["text"], "done": i["done"], "priority": i["priority"], "task_id": i["task_id"]}
            for i in payload.get("manual_task_items", [])
        ]

        all_items = (
            carryover
            + [ci for b in school for ci in b["items"]]
            + chores
            + manual
        )
        total = len(all_items)
        done  = sum(1 for i in all_items if i["done"])

        children_data[child] = {
            "carryover": carryover,
            "school":    school,
            "chores":    chores,
            "manual":    manual,
            "total":     total,
            "done":      done,
            "pending":   total - done,
        }

    return {
        "iso":        iso_str,
        "weekday":    weekday,
        "date_label": date_label,
        "children":   children_data,
    }


def boys_task_snapshot_text(iso: str = "") -> str:
    """
    Return a formatted text summary of all boys' live task state.
    Suitable for injection directly into an AI system prompt.
    ✓ = done   ○ = still pending
    """
    data = boys_task_snapshot(iso)
    lines = [
        f"== LIVE TASK STATE FOR EACH BOY — {data['weekday']}, {data['date_label']} ==",
        "This is pulled in real time from progress.json at the moment of your response.",
        "✓ = done already   ○ = still pending",
        "",
    ]

    for child, info in data["children"].items():
        if "error" in info:
            lines.append(f"{child}: (could not load — {info['error']})")
            lines.append("")
            continue

        done    = info["done"]
        total   = info["total"]
        pending = info["pending"]
        lines.append(f"{child} — {done}/{total} complete, {pending} remaining:")

        if not total:
            lines.append("  (No tasks today)")

        for item in info["carryover"]:
            mark = "✓" if item["done"] else "○"
            lines.append(f"  [Carryover] {mark} {item['text']}")

        for block in info["school"]:
            subj = block["subject"]
            block_items = block["items"]
            bd = sum(1 for i in block_items if i["done"])
            bt = len(block_items)
            lines.append(f"  [School — {subj}] {bd}/{bt} done:")
            for item in block_items:
                mark = "✓" if item["done"] else "○"
                lines.append(f"    {mark} {item['text']}")

        for item in info["chores"]:
            mark = "✓" if item["done"] else "○"
            lines.append(f"  [Chore] {mark} {item['text']}")

        for item in info["manual"]:
            mark = "✓" if item["done"] else "○"
            lines.append(f"  [Task] {mark} {item['text']} [{item['priority']}]")

        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# DAY LIST — Full chronological schedule built from the Rule of Life
# Each person's entire day in one flat, sortable, expandable list.
# ═══════════════════════════════════════════════════════════════════════════════

_DAY_TEMPLATES_DIR = Path("data/day_templates")

# Slot-kind classification: first match wins
_SLOT_KIND_MAP: list = [
    ("prayer",   ["prayer", "rosary", "angelus", "lauds", "vespers"]),
    ("mass",     ["holy mass", "mass"]),
    ("wakeup",   ["up & moving", "wake", "rising"]),
    ("meal",     ["breakfast", "brunch", "lunch", "dinner", "snack"]),
    ("exercise", ["exercise", "pe ", "physical ed", "workout"]),
    ("school",   ["school", "math", "writing", "reading", "science", "history",
                  "grammar", "latin", "logic", "religion", "english"]),
    ("chore",    ["morning jobs", "weekly job", "weekly jobs", "room clean",
                  "clean the kitchen", "clean the", "prep mass", "prep for sunday",
                  "laundry", "trash", "sweep", "mop"]),
    ("task",     ["lists with mom", "go over lists"]),
    ("routine",  ["showers", "shower", "bath", "hygiene", "groom",
                  "get ready for", "prep mass clothes"]),
    ("free",     ["free time", "video game", "hw or free", "screen",
                  "leisure", "rest", "family time", "week prep",
                  "school or video"]),
]


def _classify_slot(label: str) -> str:
    low = label.lower()
    for kind, kws in _SLOT_KIND_MAP:
        if any(kw in low for kw in kws):
            return kind
    return "routine"


def _slot_checkable(kind: str) -> bool:
    return kind not in ("free", "wakeup")


def _parse_slot_time(time_str: str) -> str:
    try:
        from datetime import datetime as _dt
        return _dt.strptime(time_str.strip(), "%I:%M %p").strftime("%H:%M")
    except Exception:
        return "00:00"


def _split_daily_chores(daily: list) -> dict:
    morning, evening, current = [], [], None
    current = morning
    for line in daily:
        low = line.lower() if isinstance(line, str) else ""
        if "kitchen (morning" in low or "kitchen (am" in low:
            current = morning
            morning.append(line)
        elif "kitchen (evening" in low or "kitchen (pm" in low:
            current = evening
            evening.append(line)
        else:
            current.append(line)
    return {"morning": morning, "evening": evening}


def _lines_to_sub_items(lines: list, child: str, iso: str, prefix: str,
                         progress: dict) -> list:
    items = []
    for line in lines:
        if not isinstance(line, str):
            continue
        stripped = line.strip()
        if not stripped:
            continue
        arrow = stripped.startswith("\u2192") or stripped.startswith("->") or stripped.startswith("  \u2192")
        is_header = stripped.endswith(":") and not arrow
        display = stripped.lstrip("\u2192-> ").strip()
        if not display:
            continue
        if is_header:
            items.append({"text": display, "task_id": None,
                          "done": False, "checkable": False, "is_header": True})
        else:
            tid = f"CHORE::{child}::{iso}::{prefix}::{display}"
            items.append({"text": display, "task_id": tid,
                          "done": bool(progress.get(tid, {}).get("done", False)),
                          "checkable": True, "is_header": False})
    return items


def _school_sub_items(school_raw: list, subjects_used: set,
                      child: str, iso: str, hint: str, progress: dict) -> list:
    items = []
    for block in school_raw:
        subj = block.get("subject", "").strip()
        subj_low = subj.lower()
        hint_low = hint.lower()
        if hint and not (hint_low in subj_low or subj_low in hint_low):
            continue
        if subj_low in subjects_used:
            continue
        subjects_used.add(subj_low)
        assign_text = block.get("assignment_text", "").strip()
        for ci in block.get("checklist", ["Done"]):
            tid = f"SCHOOL::{child}::{iso}::{subj}::{ci}"
            text = f"{ci}" if not assign_text else f"{assign_text} — {ci}"
            if hint == "":
                text = f"{subj}: {text}"
            items.append({"text": text, "task_id": tid,
                          "done": bool(progress.get(tid, {}).get("done", False)),
                          "checkable": True, "is_header": False})
    return items


def build_day_list(child: str, weekday: str, iso: str) -> list:
    """
    Build the full chronological Day List for a person on a given weekday.

    Returns a list of time-block dicts, each with:
      time, time_sort, end_time, label, kind, checkable, task_id, done, sub_items
    """
    # Load Rule of Life template
    person_grid = {}
    for candidate in [f"{weekday}.json", "Friday.json"]:
        try:
            path = _DAY_TEMPLATES_DIR / candidate
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                grid = data.get("grid", {})
                person_grid = (grid.get(child)
                               or grid.get("Mom")
                               or (next(iter(grid.values())) if grid else {}))
                if person_grid:
                    break
        except Exception:
            pass
    if not person_grid:
        return []

    # Parse and sort slots; merge consecutive same-label ones
    raw_slots = sorted(
        [(_parse_slot_time(ts), ts, (lbl or "").strip())
         for ts, lbl in person_grid.items()],
        key=lambda x: x[0]
    )
    merged = []
    for time_sort, time_str, label in raw_slots:
        if not label:
            continue
        if merged and merged[-1]["label"] == label:
            pass   # same block continues; end_time updated next
        else:
            merged.append({"time": time_str, "time_sort": time_sort,
                           "end_time": time_str, "label": label})
    for i, blk in enumerate(merged):
        blk["end_time"] = merged[i + 1]["time"] if i + 1 < len(merged) else blk["time"]

    # Load data sources
    progress = load_progress()

    school_raw = []
    try:
        school_raw = extract_school_tasks_for_child(child, weekday)
    except Exception:
        pass

    chores_data: dict = {}
    try:
        rc = json.loads(Path(CHORES_FILE).read_text(encoding="utf-8"))
        if child in ("JP", "Joseph", "Michael"):
            chores_data = rc.get("boys", {}).get(child, {})
        else:
            chores_data = rc.get("lauren", rc.get(child.lower(), {}))
    except Exception:
        pass
    daily_split  = _split_daily_chores(chores_data.get("daily", []))
    weekly_today = chores_data.get("weekly", {}).get(weekday, [])
    weekly_sat   = chores_data.get("weekly", {}).get("Saturday", [])

    manual_items, carryover_items = [], []
    try:
        for t in get_manual_tasks_for_child_and_date(child, iso):
            tid = f"MANUAL::{child}::{iso}::{t['text']}"
            manual_items.append({"text": t["text"], "task_id": tid,
                                 "done": bool(progress.get(tid, {}).get("done", False)),
                                 "checkable": True, "is_header": False})
        for txt in get_carryover_tasks(child, normalize_target_date(iso)):
            tid = f"CARRY::{child}::{iso}::{txt}"
            carryover_items.append({"text": txt, "task_id": tid,
                                    "done": bool(progress.get(tid, {}).get("done", False)),
                                    "checkable": True, "is_header": False,
                                    "is_carryover": True})
    except Exception:
        pass

    # Build the result list
    subjects_used: set = set()
    has_tasks_slot = any(
        "lists with mom" in b["label"].lower() or "go over lists" in b["label"].lower()
        for b in merged
    )
    result = []

    for blk in merged:
        label     = blk["label"]
        label_low = label.lower()
        kind      = _classify_slot(label)

        item = {
            "time":      blk["time"],
            "time_sort": blk["time_sort"],
            "end_time":  blk["end_time"],
            "label":     label,
            "kind":      kind,
            "checkable": _slot_checkable(kind),
            "task_id":   None,
            "done":      False,
            "sub_items": [],
        }

        # ── School ──────────────────────────────────────────────────────
        if kind == "school" and "or video" not in label_low and "hw or" not in label_low:
            hint = ""
            if "\u2014" in label:
                hint = label.split("\u2014", 1)[1].strip()
            elif "—" in label:
                hint = label.split("—", 1)[1].strip()
            subs = _school_sub_items(school_raw, subjects_used, child, iso, hint, progress)
            item["sub_items"] = subs
            item["checkable"] = False

        # ── Morning Jobs ────────────────────────────────────────────────
        elif "morning jobs" in label_low:
            item["sub_items"] = _lines_to_sub_items(
                daily_split["morning"], child, iso, "morning", progress)
            item["checkable"] = False

        # ── Evening kitchen clean ───────────────────────────────────────
        elif "clean the kitchen" in label_low and blk["time_sort"] >= "17:00":
            item["sub_items"] = _lines_to_sub_items(
                daily_split["evening"], child, iso, "evening", progress)
            item["checkable"] = False

        # ── Midday kitchen clean (simple checkbox) ──────────────────────
        elif "clean the kitchen" in label_low:
            tid = f"CHORE::{child}::{iso}::noon_kitchen"
            item["task_id"] = tid
            item["done"]    = bool(progress.get(tid, {}).get("done", False))

        # ── Weekly Job(s) ────────────────────────────────────────────────
        elif "weekly job" in label_low:
            item["sub_items"] = _lines_to_sub_items(
                weekly_today, child, iso, "weekly", progress)
            item["checkable"] = False

        # ── Saturday Room Clean ─────────────────────────────────────────
        elif "room clean" in label_low:
            item["sub_items"] = _lines_to_sub_items(
                weekly_sat, child, iso, "sat_clean", progress)
            item["checkable"] = False

        # ── Go over Lists with Mom ──────────────────────────────────────
        elif "lists with mom" in label_low or "go over lists" in label_low:
            subs = [dict(i, is_carryover=True) for i in carryover_items] + list(manual_items)
            item["sub_items"] = subs
            item["checkable"] = False

        # ── Free / informational ────────────────────────────────────────
        elif kind in ("free",):
            item["checkable"] = False

        # ── Single-checkbox items: prayer, exercise, routine, wakeup, meal
        else:
            tid = f"ROUTINE::{child}::{iso}::{label}"
            item["task_id"] = tid
            item["done"]    = bool(progress.get(tid, {}).get("done", False))
            if kind in ("meal", "wakeup", "free"):
                item["checkable"] = False

        result.append(item)

    # Append task block if no dedicated slot exists in the template
    if not has_tasks_slot:
        extra = [dict(i, is_carryover=True) for i in carryover_items] + list(manual_items)
        if extra:
            result.append({
                "time": "", "time_sort": "23:00", "end_time": "",
                "label": "Tasks", "kind": "task",
                "checkable": False, "task_id": None, "done": False,
                "sub_items": extra,
            })

    return result


def day_list_stats(day_list: list) -> dict:
    """Return {total, done, pct} for progress tracking."""
    total = done = 0
    for item in day_list:
        if item.get("sub_items"):
            for s in item["sub_items"]:
                if s.get("checkable") and not s.get("is_header"):
                    total += 1
                    if s.get("done"):
                        done += 1
        elif item.get("checkable") and item.get("task_id"):
            total += 1
            if item.get("done"):
                done += 1
    return {"total": total, "done": done,
            "pct": round(done / total * 100) if total else 0}
