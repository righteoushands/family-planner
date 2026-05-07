import json
import re
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


def _hhmm_to_min(hhmm: str) -> int:
    """Convert 'HH:MM' string to total minutes since midnight. Returns 0 on error."""
    try:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


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
        # Remove legacy-format keys so old checked state doesn't ghost back
        parts = task_id.split("::")
        if len(parts) == 5 and parts[0] == "CHORE":
            _, child, iso, _prefix, display = parts
            for old_key in (
                f"{iso}::{child}::CHORE::  \u2192 {display}",
                f"{iso}::{child}::CHORE::\u2192 {display}",
                f"{iso}::{child}::CHORE::{display}",
                f"{iso}::{child}::  \u2192 {display}",
                f"{iso}::{child}::\u2192 {display}",
            ):
                progress.pop(old_key, None)
        elif len(parts) == 4 and parts[0] == "ROUTINE":
            _, child, iso, label = parts
            label_l = label.lower()
            old_pfx = f"{iso}::{child}::"
            stale = []
            for k, v in progress.items():
                if not v or not k.startswith(old_pfx): continue
                tail = k[len(old_pfx):]
                if "::" in tail: tail = tail.split("::", 1)[1]
                tail_clean = tail.lstrip("\u2192 ->").strip().lower()
                if tail_clean.startswith(label_l) or label_l.startswith(tail_clean):
                    stale.append(k)
            for k in stale:
                progress.pop(k, None)
        elif len(parts) == 5 and parts[0] == "SCHOOL":
            _, child, iso, subject, item_label = parts
            progress.pop(f"{iso}::{child}::SCHOOL::{subject}::{item_label}", None)
        elif len(parts) == 4 and parts[0] in ("MANUAL", "CARRY"):
            _, child, iso, text = parts
            for old_key in (
                f"{iso}::{child}::MANUAL::MEDIUM::{text}",
                f"{iso}::{child}::MANUAL::HIGH::{text}",
                f"{iso}::{child}::MANUAL::LOW::{text}",
                f"{iso}::{child}::[MEDIUM] {text}",
                f"{iso}::{child}::[HIGH] {text}",
                f"{iso}::{child}::[LOW] {text}",
                f"{iso}::{child}::{text}",
            ):
                progress.pop(old_key, None)

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


def get_meal_helper_task_for_child(child: str, weekday: str, iso: str):
    """
    Return a chore-text string like "Dinner helper: Brown the meat, lead sauce"
    for this child on this day, pulled from the meal plan's helpers/boys_help field.
    Returns None if no helper entry exists for this child today.
    """
    try:
        from render_meals import load_meal_plan, slot_display_text as _sdt
        from datetime import date as _date, timedelta as _td
        d      = _date.fromisoformat(iso)
        monday = d - _td(days=d.weekday())          # load by Monday ISO date so the
        plan   = load_meal_plan(monday.isoformat())  # filename-based lookup hits the right file
        day    = plan.get("days", {}).get(weekday, {})
        raw    = (_sdt(day.get("helpers")) or _sdt(day.get("boys_help"))).strip()
        if not raw:
            return None
        sep   = "|" if "|" in raw else "\u00b7"
        parts = [p.strip() for p in raw.split(sep) if p.strip()]
        for part in parts:
            if ":" in part:
                name, _, task = part.partition(":")
                if name.strip().lower() == child.lower():
                    task = task.strip()
                    if task:
                        return f"Dinner helper: {task}"
        return None
    except Exception:
        return None


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

    try:
        _view_date = date.fromisoformat(iso)
    except Exception:
        _view_date = date.today()
    _due_soon_cutoff = (_view_date + timedelta(days=7)).isoformat()

    for task in tasks:
        if not isinstance(task, dict):
            continue

        task_child = str(task.get("assigned_to", "")).strip()
        task_date  = str(task.get("due_date", "")).strip()
        status     = str(task.get("status", "active")).strip().upper()

        # "Mom" and "Lauren" are the same person — normalize both sides so tasks
        # created with either name always appear on Lauren's day list.
        _LAUREN_ALIASES = {"Lauren", "Mom"}
        _effective_child = "Lauren" if child in _LAUREN_ALIASES else child
        _effective_task_child = "Lauren" if task_child in _LAUREN_ALIASES else task_child

        if _effective_task_child and _effective_task_child != _effective_child:
            continue

        # Tasks due today or within the next 7 days always surface, regardless of
        # active/inactive status — so nothing overdue or upcoming is ever hidden.
        is_due_soon = bool(task_date) and iso <= task_date <= _due_soon_cutoff

        if not is_due_soon:
            if status != "ACTIVE":
                continue
            if task_date and task_date > iso:
                continue  # future-dated, outside 7-day window: hold until due

        text = str(task.get("text", "")).strip()
        if not text:
            continue

        priority = normalize_priority(task.get("priority", "MEDIUM"))

        results.append({
            "id":         str(task.get("id", "")),
            "text":       text,
            "priority":   priority,
            "due_date":   task_date,
            "is_due_soon": is_due_soon and task_date > iso,  # True only for future-dated upcoming
        })

    results.sort(key=lambda item: (
        PRIORITY_ORDER.get(item["priority"], 1),
        item.get("due_date") or "9999",
        item["text"].lower()
    ))
    return results


# -------------------------
# SCHOOL TASKS
# -------------------------

# JP ↔ Joseph cross-check each other's math
_MATH_CHECK_PAIRS: dict = {"JP": "Joseph", "Joseph": "JP"}


def _get_brother_math_label(child: str, weekday: str) -> str:
    """Return a short label for the math-exchange brother's current lesson.

    e.g. for JP checking Joseph → 'Math 7 Lesson 43'
         for Joseph checking JP → 'Algebra 1/2 Lesson 75'
    Returns '' if no brother or no math assignment found.
    """
    brother = _MATH_CHECK_PAIRS.get(child)
    if not brother:
        return ""
    try:
        bro_assignments = get_school_assignments_for_weekday(weekday)
        bro_day = bro_assignments.get(brother, {})
        for blk in bro_day.get("blocks", []):
            if blk.get("is_math") and not blk.get("is_math_test"):
                bro_subj   = blk.get("subject", "").strip()
                bro_assign = blk.get("assignment_text", "").strip()
                if bro_subj and bro_assign:
                    return f"{bro_subj} {bro_assign}"
                return bro_subj or bro_assign
    except Exception:
        pass
    return ""


def extract_school_tasks_for_child(child: str, weekday: str, iso: str = None):
    # NOTE: snapshot read fast-path was removed — this function always
    # regenerates from the live curriculum cursor.  The snapshot WRITE at
    # the bottom of this function is preserved so the week-school grid and
    # other historical-view consumers continue to work.  Cursor advancement
    # now happens at toggle-time in app.py /toggle-task (not here).
    # `_today_iso` / `_eff_iso` are still consumed by the snapshot WRITE
    # gate below ("today and future only — don't snapshot past dates").
    _today_iso = date.today().isoformat()
    _eff_iso   = iso if iso else _today_iso
    assignments = get_school_assignments_for_weekday(weekday)
    day = assignments.get(child, {})
    tasks = []
    seen_subjects = set()

    # ── Curriculum merge (PRIMARY source) ────────────────────────────────────
    # Curriculum is the source-of-truth for which subjects meet today and
    # what their lesson text is.  The PDF loop (below) acts as a fallback
    # for subjects not covered by the curriculum (e.g. Reading 7, which is
    # parsed from PDF but is not in Joseph's curriculum).
    # Frequency-aware via the subject's `_weekdays` list (preferred) or
    # subject_meeting_days's school_weeks fallback.  Day-aware: picks the
    # lesson text for today's position within the subject's meeting days.
    try:
        from data_helpers import (
            load_curriculum, get_curriculum_week, resolve_week_text,
            week_day_segments, subject_meeting_days, subject_day_index,
        )
        _cur_data = load_curriculum() or {}
        _cur_week_global = get_curriculum_week()
        _child_subjects = _cur_data.get(child, {}) or {}
        for _subject, _subj_node in _child_subjects.items():
            if not isinstance(_subj_node, dict):
                continue
            try:    _subj_week = int(_subj_node.get("_current_week", _cur_week_global))
            except (TypeError, ValueError): _subj_week = _cur_week_global
            # Sentinel — subject completed.
            if _subj_week >= 999:
                continue
            # Pass the subject node so subject_meeting_days's pass-0 fast
            # path can use `_weekdays` directly without consulting
            # school_weeks.json.  Falls through to school_weeks lookup only
            # when `_weekdays` is absent or empty.
            _meeting = subject_meeting_days(child, _subject, _subj_node)
            _day_idx = subject_day_index(_meeting, weekday)
            if _day_idx is None:
                # Subject does not meet today.
                continue
            # day_pref is driven by the subject's stored `_current_day` cursor,
            # not the weekday-relative position.  `_current_day` already tracks
            # which lesson within the week should be shown today; using it
            # directly lets manual cursor advances (e.g. "skip ahead to Day 5")
            # take effect.  `_day_idx` is still used above purely for the
            # frequency gate (does the subject meet today at all).
            try:    _subj_day = int(_subj_node.get("_current_day", 1))
            except (TypeError, ValueError): _subj_day = 1
            _text = resolve_week_text(_subj_node, _subj_week, day_pref=_subj_day)
            if not _text:
                continue
            # Normalize checklist text: collapse all whitespace (newlines,
            # carriage returns, tabs, multi-space) to single spaces.  task_ids
            # built from these checklist items must never contain literal
            # newline characters — they round-trip through HTML attributes,
            # JS fetch payloads, and urlencode/decode, any of which can
            # silently re-shape \n vs \r\n vs spaces and produce a stored
            # progress key that doesn't match the next render's regenerated
            # task_id.  `assignment_text` keeps the original formatting for
            # display.
            _text_oneline = re.sub(r"\s+", " ", _text).strip()
            _is_math = ("algebra" in _subject.lower()) or ("math" in _subject.lower())
            if _is_math:
                _pfx = f"{_text_oneline} — " if _text_oneline else ""
                _bro_label = _get_brother_math_label(child, weekday)
                _bro_sfx   = f" ({_bro_label})" if _bro_label else ""
                _checklist = [
                    f"{_pfx}Assignment completed",
                    f"{_pfx}Given to checker",
                    f"{_pfx}Fixed missed problems",
                    f"{_pfx}Received brother's math{_bro_sfx}",
                    f"{_pfx}Checked brother's math{_bro_sfx}",
                ]
            else:
                _checklist = [_text_oneline]
            # Poetry-memorize signal: only flag the day when the lesson is
            # actually a memorization step (assignment text leads with
            # "memorize…").  Substring-only matching falsely fired on
            # continuation/recitation days whose text contained
            # parenthetical phrases like "have not already memorized".
            # Cap at the first 60 chars so only prominent leading-verb
            # use of "memorize" qualifies.
            _is_poetry_memo = (
                "poetry" in _subject.lower()
                and "memorize" in (_text[:60].lower() if _text else "")
            )
            tasks.append({
                "subject": _subject,
                "assignment_text": _text,
                "is_math": _is_math,
                "is_math_test": False,
                "checklist": _checklist,
                "from_curriculum": True,
                "week": _subj_week,
                "day":  _subj_day,
                "is_poetry_memorize": _is_poetry_memo,
            })
            # Curriculum claims this subject — PDF loop below will skip any
            # PDF block whose lowercase short subject name is a substring of
            # (or starts with) this curriculum subject name.
            seen_subjects.add(_subject.lower())
    except Exception:
        pass

    # ── PDF fallback ─────────────────────────────────────────────────────────
    # Emits PDF-parsed tasks for any subject NOT already claimed by curriculum.
    # Bidirectional fuzzy de-dup: skip when this PDF subject's lowercase name
    # is a substring of a curriculum subject already in seen_subjects (the
    # common case — short PDF "Religion 8" collapsing onto long curriculum
    # "Religion 8 (Our Life in the Church) Syllabus") OR when a curriculum
    # subject is a substring of this PDF name (defensive — covers a future
    # case where curriculum uses a short label and PDF uses a longer one).
    # Mirrors subject_meeting_days's case-insensitive containment logic.
    for block in day.get("blocks", []):
        subject = block.get("subject", "").strip()
        if subject:
            _sl = subject.lower()
            if any(_sl in s or s in _sl for s in seen_subjects):
                continue
        text = block.get("assignment_text", "").strip()
        is_math = bool(block.get("is_math", False))
        is_math_test = bool(block.get("is_math_test", False))
        # Normalize for use inside checklist items / task_ids — see the
        # analogous comment in the curriculum branch above.
        text_oneline = re.sub(r"\s+", " ", text).strip() if text else ""

        checklist = []
        if is_math_test:
            checklist.append("Test completed — given to Mom")
        elif is_math:
            # Prefix each step with the lesson/assignment text so carryover
            # shows which specific lesson needs checking (e.g. "Lesson 76 — Fixed missed problems")
            _pfx = f"{text_oneline} — " if text_oneline else ""
            # For the cross-checking steps, also name the brother's lesson so
            # each boy knows exactly which assignment he is checking.
            _bro_label = _get_brother_math_label(child, weekday)
            _bro_sfx   = f" ({_bro_label})" if _bro_label else ""
            checklist.extend([
                f"{_pfx}Assignment completed",
                f"{_pfx}Given to checker",
                f"{_pfx}Fixed missed problems",
                f"{_pfx}Received brother's math{_bro_sfx}",
                f"{_pfx}Checked brother's math{_bro_sfx}",
            ])
        else:
            # Use the full assignment text so carryover shows what was actually assigned,
            # not just a generic "Done". Fall back to "Done" if there's no text.
            checklist.append(text_oneline if text_oneline else "Done")

        tasks.append({
            "subject": subject,
            "assignment_text": text,
            "is_math": is_math,
            "is_math_test": is_math_test,
            "checklist": checklist,
        })
        if subject:
            seen_subjects.add(subject.lower())

    # ── Snapshot on render ───────────────────────────────────────────────────
    # Persist today's (and future-date) school task IDs into the registry so
    # later historical reads of the same date can reconstruct what was
    # actually planned, even after cursor advances move the live curriculum
    # past this content.  Skipped for past dates so we never overwrite an
    # already-frozen snapshot with cursor-projected content.
    # Format matches build_task_texts_for_day's legacy contract
    # (`SCHOOL::{subject}::{item}`) so render_week_school's reader
    # parses it correctly.  Merge-not-replace because
    # register_tasks_for_day overwrites the bucket wholesale —
    # without merging, this call would wipe any chores/manual that
    # build_task_texts_for_day previously wrote (or vice versa, depending
    # on call order across renderers).
    if _eff_iso >= _today_iso:
        try:
            _ids = []
            for _blk in tasks:
                _bsubj = (_blk.get("subject") or "").strip()
                if not _bsubj: continue
                for _ci in (_blk.get("checklist") or []):
                    if not isinstance(_ci, str): continue
                    _ci_clean = _ci.strip()
                    if not _ci_clean: continue
                    _ids.append(f"SCHOOL::{_bsubj}::{_ci_clean}")
            if _ids:
                _existing = get_registered_tasks_for_day(child, _eff_iso) or []
                _merged   = sorted(set(list(_existing) + _ids))
                _existing_sorted = sorted(set(_existing))
                if _merged != _existing_sorted:
                    register_tasks_for_day(child, _eff_iso, _merged)
        except Exception:
            pass

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


def _carry_completion_exists(progress: dict, child: str, display: str) -> bool:
    """
    Has the user EVER checked off a CARRY:: copy of this task on any later day?

    When a task carries forward and the user checks it off, the click writes
    `CARRY::child::TODAY::display` (today's iso, not the original day).  Without
    this check, _is_prev_task_done would only ever look at the original key
    (e.g. SCHOOL::JP::2026-04-13::…) — which never flips to True — and the task
    would carry forever.

    `display` should be the user-visible text (format_task_text output), which
    is what the CARRY:: keys store.  We also tolerate a leading [PRIORITY]
    marker because manual carryover keys keep that prefix.
    """
    if not display:
        return False
    import re as _re
    target  = display.strip()
    target2 = _re.sub(r"^\[(HIGH|MEDIUM|LOW)\]\s*", "", target).strip()
    pfx = f"CARRY::{child}::"
    for k, v in progress.items():
        if not v or not k.startswith(pfx):
            continue
        # k = CARRY::child::iso::display
        parts = k.split("::", 3)
        if len(parts) != 4:
            continue
        ktext = parts[3].strip()
        if ktext == target or ktext == target2:
            return True
        # Also tolerate the same priority-prefix asymmetry the other way
        ktext2 = _re.sub(r"^\[(HIGH|MEDIUM|LOW)\]\s*", "", ktext).strip()
        if ktext2 == target or ktext2 == target2:
            return True
    return False


def _is_prev_task_done(progress: dict, child: str, iso: str, raw: str) -> bool:
    """Check whether a registered task was completed, handling all key formats.

    Progress keys use: TYPE::child::iso::... (new format)
    make_task_id() used: iso::child::raw (old/legacy format)
    Both are checked so old data still works.

    A CARRY:: completion on ANY later day also counts — see
    _carry_completion_exists for why.
    """
    raw = raw.strip()

    # 0. Universal carry-completion check — if the user ever checked this off
    #    while it was showing as a carryover item, treat it as done regardless
    #    of which key family it belongs to.
    try:
        if _carry_completion_exists(progress, child, format_task_text(raw)):
            return True
    except Exception:
        pass

    # 1. Legacy format (old make_task_id)
    if progress.get(f"{iso}::{child}::{raw}"):
        return True

    # 2. SCHOOL:: — registry stores the full progress key already
    #    e.g. SCHOOL::JP::2026-04-08::Algebra 1/2::Assignment completed
    if raw.startswith("SCHOOL::"):
        if progress.get(raw):
            return True
        # Also try without child/iso prefix if the key was registered differently
        parts = raw.split("::")
        if len(parts) >= 5 and parts[1] == child and parts[2] == iso:
            if progress.get(raw):
                return True
        # Build canonical new-format key
        subject = ""
        if len(parts) >= 3:
            # SCHOOL::subject::item  (short form)
            _, subject, *rest = parts
            key = f"SCHOOL::{child}::{iso}::{subject}::{'::'.join(rest)}"
            if progress.get(key):
                return True
        # Subject-level satisfaction: the registry is rebuilt every page-load
        # from the current curriculum, so the exact checklist text can drift
        # day-to-day (e.g. today says "Memorize.", but the user originally
        # checked off the generic "Done" button).  If ANY progress entry exists
        # for SCHOOL::child::iso::subject::*, the subject was done that day.
        # Also matches CARRY::child::iso::* entries when the key text contains
        # the subject name — handles the case where the kid checked off the
        # subject while it was rendered as a carryover (CARRY:: prefix) on the
        # same day, leaving today's freshly-rebuilt SCHOOL:: task orphaned.
        if subject:
            subj_pfx  = f"SCHOOL::{child}::{iso}::{subject}::"
            carry_pfx = f"CARRY::{child}::{iso}::"
            for k, v in progress.items():
                if not v:
                    continue
                if k.startswith(subj_pfx):
                    return True
                if k.startswith(carry_pfx):
                    return True
        return False

    # 3. MANUAL:: — raw is MANUAL::MEDIUM::text or MANUAL::HIGH::text or MANUAL::text
    if raw.startswith("MANUAL::"):
        parts = raw.split("::", 2)
        text = ""
        if len(parts) == 3:
            _, second, text = parts
            if second.upper() in ("HIGH", "MEDIUM", "LOW"):
                text = text.strip()
            else:
                text = f"{second}::{text}".strip()
            key = f"MANUAL::{child}::{iso}::{text}"
            if progress.get(key):
                return True
            # Also check CARRY:: format: task was checked off as a carryover item
            carry_disp = format_task_text(raw)
            if progress.get(f"CARRY::{child}::{iso}::{carry_disp}"):
                return True
        elif len(parts) == 2:
            text = parts[1].strip()
            for key in (
                f"MANUAL::{child}::{iso}::{text}",
                f"MANUAL::{child}::{iso}::MEDIUM::{text}",
            ):
                if progress.get(key):
                    return True
        # Mirror the SCHOOL subject-level scan: a MANUAL task completed on
        # any LATER day under the same display text counts as done.  Without
        # this, ticking a manual task on today's POD writes
        # MANUAL::child::TODAY::text but the carryover walk-back only checks
        # MANUAL::child::CHECK_ISO::text (the prior day the task was
        # registered), stays False, and the task ghosts back as a CARRY::
        # entry on the next refresh.  See _carry_completion_exists for the
        # equivalent CARRY::-key safety net.
        if text:
            _suffix = f"::{text}"
            _mpfx   = f"MANUAL::{child}::"
            for _k, _v in progress.items():
                if not _v or not _k.startswith(_mpfx) or not _k.endswith(_suffix):
                    continue
                # _k = MANUAL::child::iso::text  → extract iso (split into 4)
                _kparts = _k.split("::", 3)
                if len(_kparts) != 4:
                    continue
                _kiso = _kparts[2]
                if _kiso > iso:
                    return True
        # Cross-type fallback: task may have been saved as CHORE in progress
        if text:
            text_l = text.lower().strip()
            # Extract first sentence (before first colon or newline)
            core = text_l.split(":")[0].strip() if ":" in text_l else text_l
            pfx = f"CHORE::{child}::{iso}::"
            for k, v in progress.items():
                if not v or not k.startswith(pfx):
                    continue
                tail = k[len(pfx):]
                slot = ""
                task_text = tail
                if "::" in tail:
                    slot, task_text = tail.split("::", 1)
                task_l = task_text.strip().lower().lstrip("→ ").strip()
                # Exact match on core description
                if task_l == text_l.lstrip("→ ").strip():
                    return True
                # Slot-based match for block summaries (KITCHEN, LAUNDRY, VAN)
                slot_hints = []
                for word in ("morning", "evening", "night", "weekly",
                             "afternoon", "laundry", "kitchen", "van"):
                    if word in text_l:
                        slot_hints.append(word)
                if slot_hints:
                    for hint in slot_hints:
                        if hint in slot.lower() or hint in task_l:
                            return True
        return False

    # 4. ROUTINE:: — raw is ROUTINE::label
    if raw.startswith("ROUTINE::"):
        parts = raw.split("::", 1)
        label = parts[1] if len(parts) == 2 else raw
        if progress.get(f"ROUTINE::{child}::{iso}::{label}"):
            return True
        # Fuzzy: progress key label might differ slightly
        label_l = label.strip().lower()
        pfx = f"ROUTINE::{child}::{iso}::"
        for k, v in progress.items():
            if v and k.startswith(pfx):
                if k[len(pfx):].strip().lower() == label_l:
                    return True
        return False

    # 5. CARRY:: — raw is CARRY::child::iso::text
    if raw.startswith("CARRY::"):
        parts = raw.split("::", 3)
        if len(parts) == 4:
            _, c, d, text = parts
            if progress.get(f"CARRY::{c}::{d}::{text}"):
                return True
        return False

    # 6. CHORE:: — raw is CHORE::display or CHORE::  → display
    if raw.startswith("CHORE::"):
        display = raw.split("::", 1)[1].strip().lstrip("→ ").strip()
        if not display:
            return False
        # Section headers end with ':' — treat as done if ANY sub-task in the
        # same named slot was completed (e.g. "KITCHEN (Morning — Role A):")
        is_header = display.endswith(":")
        display_l = display.rstrip(":").strip().lower()
        pfx = f"CHORE::{child}::{iso}::"
        for k, v in progress.items():
            if v and k.startswith(pfx):
                # key format: CHORE::child::iso::slot::display
                tail = k[len(pfx):]
                slot = ""
                task_text = tail
                if "::" in tail:
                    slot, task_text = tail.split("::", 1)
                if is_header:
                    # Match if this slot had any completed sub-task.
                    # Extract slot keywords from the header (e.g. "morning",
                    # "evening" from "KITCHEN (Morning — Role A):")
                    slot_hints = []
                    for word in ("morning", "evening", "night", "weekly",
                                 "afternoon", "laundry", "kitchen"):
                        if word in display_l:
                            slot_hints.append(word)
                    if not slot_hints:
                        # No hint — if any CHORE sub-task was done, mark done
                        return True
                    for hint in slot_hints:
                        if hint in slot.lower() or hint in task_text.lower():
                            return True
                else:
                    task_l = task_text.strip().lower().lstrip("→ ").strip()
                    if task_l == display_l:
                        return True
        return False

    # 7. Unknown prefix — fall back to exact key lookup only
    return bool(progress.get(raw))


_CARRYOVER_LOOKBACK_DAYS = 7


def _collect_undone_history(child: str, target_day: date, progress: dict):
    """
    Walk back up to _CARRYOVER_LOOKBACK_DAYS and collect every registered task
    that was never marked done.  Dedupes by raw task text so a weekly chore
    registered on multiple days doesn't appear twice — the OLDEST occurrence
    wins (so the "from Mon Apr 13" label points at the original assignment
    date, not the most recent re-registration).

    Returns list of (raw_text, prev_iso) sorted oldest-first.

    Why 7 days, not 1: previously this looked at yesterday only, so a task
    that wasn't done yesterday-or-the-day-before would silently disappear on
    day 3.  School & chores need to nag until they're checked off.
    """
    seen: dict = {}  # raw_text -> earliest prev_iso it appeared on
    for days_back in range(1, _CARRYOVER_LOOKBACK_DAYS + 1):
        check_iso = (target_day - timedelta(days=days_back)).isoformat()
        for raw in get_registered_tasks_for_day(child, check_iso) or []:
            # SCHOOL:: tasks use a strict registry+canonical check so a
            # previous school day with no toggle activity at all still
            # carries its undone work forward.  _is_prev_task_done has
            # permissive subject-level / CARRY-prefix heuristics that
            # falsely mark school items "done" when no SCHOOL progress
            # entry actually exists for them.  Strict rule: if the
            # canonical progress key (SCHOOL::child::iso::subject::item)
            # is missing or False — and no later carry-completion of
            # this exact display text exists — it is undone.  Friday →
            # Monday carry works automatically because the 7-day window
            # includes Fri when target_day is Mon.
            if raw.startswith("SCHOOL::"):
                _canonical = raw.replace(
                    "SCHOOL::", f"SCHOOL::{child}::{check_iso}::", 1
                )
                if progress.get(_canonical) or progress.get(raw):
                    continue
                if progress.get(f"{check_iso}::{child}::{raw}"):
                    continue
                # Universal carry-completion safety net: if the user
                # already checked off a CARRY:: copy of this display on
                # any later day, don't re-carry it.
                try:
                    if _carry_completion_exists(progress, child, format_task_text(raw)):
                        continue
                except Exception:
                    pass
                seen[raw] = check_iso
                continue
            if _is_prev_task_done(progress, child, check_iso, raw):
                continue
            # Older days are visited later in this loop, so an earlier
            # appearance (newer day) is overwritten only if the task was
            # found again on an OLDER day → we keep the older prev_iso.
            seen[raw] = check_iso
    return list(seen.items())  # [(raw, prev_iso), ...]


def get_carryover_tasks(child: str, target_day: date):
    progress = load_progress()
    items = _collect_undone_history(child, target_day, progress)
    if not items:
        return []
    items.sort(key=lambda t: carryover_sort_key(t[0]))
    return [format_task_text(raw) for raw, _ in items]


def get_carryover_tasks_raw(child: str, target_day: date):
    """Like get_carryover_tasks but returns (raw_key, formatted_text, prev_iso) tuples.

    Used by build_day_list to group school carryover by subject before rendering.
    """
    progress = load_progress()
    items = _collect_undone_history(child, target_day, progress)
    if not items:
        return []
    result = [(raw, format_task_text(raw), prev_iso) for raw, prev_iso in items]
    result.sort(key=lambda t: carryover_sort_key(t[0]))
    return result


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
    school_tasks = extract_school_tasks_for_child(child, weekday, iso)
    chore_tasks = list(weekday_chores_for_child(child, weekday))
    manual_tasks = get_manual_tasks_for_child_and_date(child, iso)

    # Append meal helper role if the meal plan has one for this child today
    meal_helper = get_meal_helper_task_for_child(child, weekday, iso)
    if meal_helper:
        chore_tasks.append(meal_helper)

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

# ---------------------------------------------------------------------------
# Time-hint extraction — scans task/chore text for time-of-day language and
# returns a "HH:MM" 24-hour sort key, or None if no hint is found.
# ---------------------------------------------------------------------------
import re as _re_hint

_TIME_CLOCK_RE = _re_hint.compile(
    r'(?:^|[\s(,;@])'               # word boundary / opening paren
    r'(\d{1,2})(?::(\d{2}))?'       # hour, optional :minute
    r'\s*([AaPp][Mm])',             # am/pm (case-insensitive)
    _re_hint.IGNORECASE,
)

_TIME_RANGE_RE = _re_hint.compile(
    r'(\d{1,2})(?::(\d{2}))?\s*([AaPp][Mm])'
    r'\s*[–\-–to]+\s*'
    r'(\d{1,2})(?::(\d{2}))?\s*([AaPp][Mm])',
    _re_hint.IGNORECASE,
)

_TIME_PHRASE_MAP: list = [
    (_re_hint.compile(r'before\s+breakfast',           _re_hint.I), "07:00"),
    (_re_hint.compile(r'after\s+breakfast',            _re_hint.I), "08:30"),
    (_re_hint.compile(r'around\s+breakfast',           _re_hint.I), "08:00"),
    (_re_hint.compile(r'before\s+lunch|pre.?lunch',    _re_hint.I), "11:30"),
    (_re_hint.compile(r'around\s+lunch(?:time)?|lunchtime', _re_hint.I), "12:00"),
    (_re_hint.compile(r'after\s+lunch',                _re_hint.I), "13:00"),
    (_re_hint.compile(r'before\s+dinner',              _re_hint.I), "16:30"),
    (_re_hint.compile(r'around\s+dinner(?:time)?',     _re_hint.I), "17:00"),
    (_re_hint.compile(r'after\s+dinner',               _re_hint.I), "18:30"),
    (_re_hint.compile(r'before\s+school',              _re_hint.I), "07:30"),
    (_re_hint.compile(r'after\s+school',               _re_hint.I), "15:30"),
    (_re_hint.compile(r'before\s+bed(?:time)?',        _re_hint.I), "20:30"),
    (_re_hint.compile(r'\bbedtime\b',                  _re_hint.I), "20:30"),
    (_re_hint.compile(r'in\s+the\s+morning|this\s+morning', _re_hint.I), "09:00"),
    (_re_hint.compile(r'this\s+afternoon|in\s+the\s+afternoon', _re_hint.I), "14:00"),
    # ── Deadline phrases must come before "this evening" / "tonight" rules ──────
    # "for tonight's meeting", "for this evening" = have it READY by tonight,
    # so the task should start in the morning, not be done at 7 PM.
    (_re_hint.compile(r'for\s+tonight|ready.*tonight',   _re_hint.I), "09:00"),
    (_re_hint.compile(r'for\s+this\s+evening',           _re_hint.I), "09:00"),
    # ── Action phrases: the thing IS done in the evening / tonight ────────────
    (_re_hint.compile(r'in\s+the\s+evening|this\s+evening', _re_hint.I), "19:00"),
    (_re_hint.compile(r'\btonight\b',                    _re_hint.I), "19:00"),
    (_re_hint.compile(r'\bnoon\b',                       _re_hint.I), "12:00"),
]


def _parse_time_hint(text: str) -> str | None:
    """
    Scan task/chore text for a time-of-day indicator.
    Returns "HH:MM" (24-hour) or None.

    Examples
    --------
    "Mind Michael (10:00 AM–12:00 PM)"  → "10:00"
    "Switch laundry around lunchtime"   → "12:00"
    "Clean up after breakfast"          → "08:30"
    "Doctor at 3:30pm"                  → "15:30"
    """
    def _to_hhmm(h: str, m: str | None, meridiem: str) -> str:
        hh = int(h)
        mm = int(m) if m else 0
        mer = meridiem.lower()
        if mer == "pm" and hh != 12:
            hh += 12
        elif mer == "am" and hh == 12:
            hh = 0
        return f"{hh:02d}:{mm:02d}"

    # 1. Time range "(10:00 AM–12:00 PM)" — use the start time
    m = _TIME_RANGE_RE.search(text)
    if m:
        return _to_hhmm(m.group(1), m.group(2), m.group(3))

    # 2. Single clock time "at 8am", "9:30 PM", etc.
    m = _TIME_CLOCK_RE.search(text)
    if m:
        return _to_hhmm(m.group(1), m.group(2), m.group(3))

    # 3. Named anchors (phrase matching)
    for pattern, hhmm in _TIME_PHRASE_MAP:
        if pattern.search(text):
            return hhmm

    return None


def _hint_to_display(hhmm: str) -> str:
    """Convert "HH:MM" to "h:MM AM/PM" for display."""
    try:
        h, m = int(hhmm[:2]), int(hhmm[3:])
        meridiem = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {meridiem}" if m else f"{h12}:{m:02d} {meridiem}"
    except Exception:
        return ""


def _dl_done(progress: dict, tid: str) -> bool:
    """Read a Day List progress flag safely.

    progress.json stores values as plain True (legacy) or {"done": True} (new).
    Calling .get("done") on a bool raises AttributeError — this helper handles both.
    """
    val = progress.get(tid)
    if val is not None:
        if isinstance(val, dict):
            return bool(val.get("done", False))
        return bool(val)   # handles plain True / False / int

    # ── Backward-compat: multiple old key formats existed before the Day List.
    # We silently accept any of them so already-checked items stay checked.
    #
    # Old formats seen in the wild:
    #   {iso}::{child}::→ {text}                   (arrow, no type)
    #   {iso}::{child}::CHORE::(  →|→|){text}      (CHORE + optional arrow)
    #   {iso}::{child}::{text}                      (plain, no type)
    #   {iso}::{child}::SCHOOL::{subj}::{item}      (SCHOOL, old field order)
    #   {iso}::{child}::MANUAL::MEDIUM::{text}      (MANUAL + priority)
    #   {iso}::{child}::[MEDIUM] {text}             (MANUAL with inline priority)

    parts = tid.split("::")

    # ── CHORE items ────────────────────────────────────────────────────────────
    if len(parts) == 5 and parts[0] == "CHORE":
        _, child, iso, _prefix, display = parts
        for old_key in (
            f"{iso}::{child}::CHORE::  \u2192 {display}",
            f"{iso}::{child}::CHORE::\u2192 {display}",
            f"{iso}::{child}::CHORE::{display}",
            f"{iso}::{child}::  \u2192 {display}",        # no type keyword
            f"{iso}::{child}::\u2192 {display}",
        ):
            if progress.get(old_key):
                return True

    # ── ROUTINE items ──────────────────────────────────────────────────────────
    elif len(parts) == 4 and parts[0] == "ROUTINE":
        _, child, iso, label = parts
        label_l = label.lower().strip()
        old_prefix2 = f"{iso}::{child}::"
        for k, v in progress.items():
            if not v or not k.startswith(old_prefix2):
                continue
            tail = k[len(old_prefix2):]
            # Strip type keyword if present: "CHORE::→ text" → "→ text" → "text"
            if "::" in tail:
                tail = tail.split("::", 1)[1]
            tail_clean = tail.lstrip("\u2192 ->").strip().lower()
            # Fuzzy-prefix: "Exercise" ↔ "Exercise (non-PE days)"
            if tail_clean.startswith(label_l) or label_l.startswith(tail_clean):
                return True

    # ── SCHOOL items ───────────────────────────────────────────────────────────
    elif len(parts) == 5 and parts[0] == "SCHOOL":
        _, child, iso, subject, item_label = parts
        old_key = f"{iso}::{child}::SCHOOL::{subject}::{item_label}"
        if progress.get(old_key):
            return True

    # ── MANUAL / CARRY items ───────────────────────────────────────────────────
    elif len(parts) == 4 and parts[0] in ("MANUAL", "CARRY"):
        _, child, iso, text = parts
        for old_key in (
            f"{iso}::{child}::MANUAL::MEDIUM::{text}",
            f"{iso}::{child}::MANUAL::HIGH::{text}",
            f"{iso}::{child}::MANUAL::LOW::{text}",
            f"{iso}::{child}::[MEDIUM] {text}",
            f"{iso}::{child}::[HIGH] {text}",
            f"{iso}::{child}::[LOW] {text}",
            f"{iso}::{child}::{text}",
        ):
            if progress.get(old_key):
                return True

    return False


# Slot-kind classification: first match wins
_SLOT_KIND_MAP: list = [
    ("prayer",   ["prayer", "rosary", "angelus", "lauds", "vespers"]),
    ("mass",     ["holy mass", "mass"]),
    ("wakeup",   ["up & moving", "wake", "rising"]),
    ("meal",     ["breakfast", "brunch", "lunch", "dinner", "snack",
                  "bible study / lunch"]),
    ("exercise", ["exercise", "pe ", "physical ed", "workout", "hspe"]),
    # travel/prep phrases come BEFORE school so "prepare to leave for..." doesn't
    # match "school" buried later in the sentence
    ("routine",  ["prepare to leave", "leave for", "travel /", "travel time",
                  "showers", "shower", "bath", "hygiene", "groom",
                  "get ready for", "prep mass clothes", "bible study / play",
                  "buffer"]),
    ("school",   ["school", "math", "writing", "reading", "science", "history",
                  "grammar", "latin", "logic", "religion", "english",
                  "bible study / school"]),
    ("chore",    ["morning jobs", "weekly job", "weekly jobs", "jobs — weekly",
                  "room clean", "clean the kitchen", "clean the",
                  "prep mass", "prep for sunday",
                  "laundry", "trash", "sweep", "mop"]),
    ("task",     ["lists with mom", "go over lists"]),
    ("free",     ["free time", "video game", "hw or free", "screen",
                  "leisure", "rest", "family time", "week prep",
                  "school or video", "hw"]),
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
    general, morning, evening = [], [], []
    current = None   # start outside any kitchen section
    for line in daily:
        low = line.lower() if isinstance(line, str) else ""
        if "kitchen (morning" in low or "kitchen (am" in low:
            current = morning
            morning.append(line)
        elif "kitchen (evening" in low or "kitchen (pm" in low:
            current = evening
            evening.append(line)
        elif current is not None:
            # Empty line ends the current kitchen section
            if not (isinstance(line, str) and line.strip()):
                current = None
            else:
                current.append(line)
        else:
            # Pre-kitchen general daily items (email checks, room reset, etc.)
            if isinstance(line, str) and line.strip():
                general.append(line)
    return {"general": general, "morning": morning, "evening": evening}


def _split_laundry_lines(lines: list):
    """
    Split a list of weekly-chore lines into (laundry_lines, other_lines).
    A laundry section begins at any line whose stripped text starts with
    'laundry' (case-insensitive) and includes all immediately-following
    sub-item lines (lines starting with → / -> / two leading spaces+→).
    """
    laundry_lines: list = []
    other_lines:   list = []
    in_laundry = False
    for line in lines:
        if not isinstance(line, str):
            other_lines.append(line)
            in_laundry = False
            continue
        stripped = line.strip()
        is_sub   = (stripped.startswith("\u2192") or stripped.startswith("->")
                    or line.startswith("  \u2192") or line.startswith("  ->"))
        if stripped.lower().startswith("laundry"):
            in_laundry = True
            laundry_lines.append(line)
        elif in_laundry and is_sub:
            laundry_lines.append(line)
        else:
            in_laundry = False
            other_lines.append(line)
    return laundry_lines, other_lines


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
                          "done": _dl_done(progress, tid),
                          "checkable": True, "is_header": False})
    return items


def _school_sub_items(school_raw: list, subjects_used: set,
                      child: str, iso: str, hint: str, progress: dict,
                      carry_by_subj: dict = None) -> list:
    """Build school sub-items for a day-list slot.

    carry_by_subj: optional dict mapping subject_lower -> list of carryover
                   dicts (pre-built with text/task_id/done/is_carryover) that
                   should be appended under their matching subject.
    """
    items = []
    for block in school_raw:
        subj = block.get("subject", "").strip()
        subj_low = subj.lower()
        hint_low = hint.lower()
        if hint:
            name_match = (hint_low in subj_low or subj_low in hint_low)
            # "School — Math" slots should capture subjects flagged is_math even
            # when the subject name (e.g. "Algebra 1/2") doesn't contain "math"
            math_hint  = "math" in hint_low
            is_math    = bool(block.get("is_math") or block.get("is_math_test"))
            if not name_match and not (math_hint and is_math):
                continue
        if subj_low in subjects_used:
            continue
        subjects_used.add(subj_low)
        assign_text = block.get("assignment_text", "").strip()
        # Normalized variants used ONLY for the equality / startswith checks
        # below — assign_text and ci themselves stay raw so the displayed
        # text and task_id values keep their original whitespace.  Fix 2
        # collapsed `\s+` → ` ` inside checklist items but left
        # assignment_text untouched, so a curriculum text containing any
        # double-space / tab / newline silently failed `ci == assign_text`
        # and got rendered as the doubled `assign_text — ci` form.
        assign_text_norm = re.sub(r"\s+", " ", assign_text).strip()
        _pfx_check_norm  = f"{assign_text_norm} — " if assign_text_norm else ""
        for ci in block.get("checklist", ["Done"]):
            tid = f"SCHOOL::{child}::{iso}::{subj}::{ci}"
            ci_norm = re.sub(r"\s+", " ", ci).strip()
            # Avoid duplicating text when:
            # - the checklist item IS the assignment text (non-math subjects), OR
            # - the checklist item already starts with "assign_text — " (math subjects
            #   now embed the lesson number in each checklist item)
            if not assign_text_norm or ci_norm == assign_text_norm or ci_norm.startswith(_pfx_check_norm):
                text = f"{ci}"
            else:
                text = f"{assign_text} — {ci}"
            if hint == "":
                text = f"{subj}: {text}"
            items.append({"text": text, "task_id": tid,
                          "done": _dl_done(progress, tid),
                          "checkable": True, "is_header": False,
                          "week":    block.get("week"),
                          "day":     block.get("day"),
                          "is_math": bool(block.get("is_math") or block.get("is_math_test")),
                          "is_poetry_memorize": bool(block.get("is_poetry_memorize"))})
        # Inject any carryover items for this subject (grouped here, chronological)
        if carry_by_subj:
            for carry_item in carry_by_subj.get(subj_low, []):
                items.append(carry_item)
    return items


def build_day_list(child: str, weekday: str, iso: str) -> list:
    """
    Build the full chronological Day List for a person on a given weekday.

    Returns a list of time-block dicts, each with:
      time, time_sort, end_time, label, kind, checkable, task_id, done, sub_items

    Source: the per-person FROL day template (data/day_templates/{weekday}.json).
    The family_schedule.json is no longer used — the day template is the sole
    source of truth.  Returns [] when no template exists for this person/day.
    """
    # ── Step 1: FROL day template (sole source of truth) ─────────────────────
    # The per-person day template is the Family Rule of Life.  It is the only
    # source used to build the day list — the old shared family_schedule.json
    # is no longer consulted.
    person_grid: dict = {}
    try:
        from data_helpers import get_frol_day_slots
        _tmpl = get_frol_day_slots(weekday, child)
        person_grid = {t: v for t, v in _tmpl.items() if (v or "").strip()}
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
            pass   # same block continues; end_time updated by next iteration
        else:
            merged.append({"time": time_str, "time_sort": time_sort,
                           "end_time": time_str, "label": label})
    for i, blk in enumerate(merged):
        blk["end_time"] = merged[i + 1]["time"] if i + 1 < len(merged) else blk["time"]

    # Load data sources
    progress = load_progress()

    school_raw = []
    try:
        school_raw = extract_school_tasks_for_child(child, weekday, iso)
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

    # Build a set of chore texts already covered by the structured chore sections,
    # so we can filter manual tasks that duplicate them.
    def _chore_line_texts(lines: list) -> set:
        texts = set()
        for ln in lines:
            if not isinstance(ln, str):
                continue
            t = ln.strip().lstrip("\u2192-> ").strip()
            if t and not t.endswith(":"):
                texts.add(t.lower())
        return texts

    known_chore_texts: set = (
        _chore_line_texts(daily_split["morning"])
        | _chore_line_texts(daily_split["evening"])
        | _chore_line_texts(weekly_today)
        | _chore_line_texts(weekly_sat)
        | _chore_line_texts(chores_data.get("daily", []))
    )

    import re as _re

    # Normalize text for robust deduplication (strip, lowercase, normalize apostrophes/quotes,
    # and remove leading [PRIORITY] brackets so "[MEDIUM] Trim nails" == "Trim nails")
    _priority_bracket_pat = _re.compile(r'^\[(?:HIGH|MEDIUM|LOW|URGENT)\]\s*', _re.IGNORECASE)
    _time_prefix_pat      = _re.compile(r'^\d{1,2}:\d{2} (?:AM|PM)\b')
    _school_progress_pat  = _re.compile(
        r' — (?:Done|Assignment completed|Given to checker|Fixed missed problems'
        r'|Received brother\'s math|Checked brother\'s math|Test completed)\s*$'
    )

    def _norm(s: str) -> str:
        s = _priority_bracket_pat.sub("", s.strip())
        return (s.lower()
                .replace("\u2019", "'")   # curly right single quote → straight
                .replace("\u2018", "'")   # curly left single quote → straight
                .replace("\u201c", '"')   # curly left double quote → straight
                .replace("\u201d", '"'))  # curly right double quote → straight

    def _is_schedule_export(text: str) -> bool:
        """Return True if this text is a schedule slot or sub-item, not a genuine task."""
        if _time_prefix_pat.match(text):        # "7:30 AM Morning Jobs …"
            return True
        if text.startswith(("\u2192", "->")):   # "→ Clean sink", "-> Load dishwasher"
            return True
        if text.rstrip().endswith(":"):          # "KITCHEN (Morning — Role A):"
            return True
        if _school_progress_pat.search(text):   # "Math 87 — Assignment completed"
            return True
        return False

    # Patterns that should NEVER appear as manual tasks (they live in their own Day List slots)
    _rol_skip_prefixes = (
        "kitchen (morning", "kitchen (evening", "kitchen (am", "kitchen (pm",
        "laundry —", "laundry --", "van —", "van --",
    )
    _rol_skip_exact = {
        "check cap email", "check sea cadet email",
        "daily room reset", "exercise (non-pe days)",
        "morning prayer", "breakfast", "lunch", "dinner",
        "clean the kitchen", "evening kitchen",
        "wakeup", "up & moving",
    }

    # Register today's tasks so they are eligible for tomorrow's carryover.
    # build_day_list is the primary rendering path (POD page), so registration
    # MUST happen here — not just in generate_schedule_text / build_schedule_payload.
    try:
        _reg_built = build_task_texts_for_day(child, weekday, iso)
        register_tasks_for_day(child, iso, _reg_built["all_task_texts"])
    except Exception:
        pass

    manual_items, carryover_items = [], []
    # school_carry_by_subj: subject_lower -> [carry item dicts] (in assignment order)
    school_carry_by_subj: dict = {}
    _seen_manual_texts: set = set()   # deduplicate within manual list itself (normalised)
    try:
        for t in get_manual_tasks_for_child_and_date(child, iso):
            txt = t.get("text", "").strip()
            if not txt:
                continue
            # Reject schedule exports (time-prefixed lines, sub-step arrows, etc.)
            if _is_schedule_export(txt):
                continue
            norm = _norm(txt)
            # Skip if it duplicates a chore already shown elsewhere
            if norm in known_chore_texts:
                continue
            # Skip chore-section summary lines (e.g. "KITCHEN (Morning — Role A): ...")
            if any(norm.startswith(p) for p in _rol_skip_prefixes):
                continue
            # Skip Rule-of-Life anchor items
            if any(skip in norm for skip in _rol_skip_exact):
                continue
            # Deduplicate within the manual list by normalised text
            if norm in _seen_manual_texts:
                continue
            _seen_manual_texts.add(norm)
            tid = f"MANUAL::{child}::{iso}::{txt}"
            _t_due    = t.get("due_date", "")
            _due_soon = t.get("is_due_soon", False)
            manual_items.append({"text": txt, "task_id": tid,
                                 "manual_id": t.get("id", ""),
                                 "done": _dl_done(progress, tid),
                                 "checkable": True, "is_header": False,
                                 "due_date": _t_due,
                                 "is_due_soon": _due_soon,
                                 "priority": t.get("priority", "MEDIUM")})
        _seen_carry_texts: set = _seen_manual_texts.copy()
        # Use raw carryover so we can route school items to their subject block.
        for raw, txt, _prev_iso in get_carryover_tasks_raw(child, normalize_target_date(iso)):
            if not txt:
                continue
            # Filter out chore sub-step artifacts and time-slot headers.
            if (_time_prefix_pat.match(txt)
                    or txt.startswith(("\u2192", "->"))
                    or txt.rstrip().endswith(":")):
                continue
            norm = _norm(txt)
            if norm in _seen_carry_texts:
                continue
            # Apply the same chore/RoL filters as manual tasks
            if any(norm.startswith(p) for p in _rol_skip_prefixes):
                continue
            if any(skip in norm for skip in _rol_skip_exact):
                continue
            _seen_carry_texts.add(norm)
            tid = f"CARRY::{child}::{iso}::{txt}"
            # Format "from Mon Apr 13" date label for the carryover source day
            try:
                from datetime import date as _carry_date
                _cd = _carry_date.fromisoformat(_prev_iso)
                _from_label = _cd.strftime("%-d %b")   # "13 Apr"
                _from_label = f"from {_cd.strftime('%a')} {_from_label}"  # "from Mon 13 Apr"
            except Exception:
                _from_label = f"from {_prev_iso}"
            # Build the display text: keep subject name + add date
            _disp = f"{txt} ({_from_label})"
            carry_item = {"text": _disp, "task_id": tid,
                          "done": _dl_done(progress, tid),
                          "checkable": True, "is_header": False,
                          "is_carryover": True}
            if raw.startswith("SCHOOL::"):
                # Route to the matching subject block so it appears grouped.
                _parts = raw.split("::", 2)
                _subj_key = _parts[1].strip().lower() if len(_parts) >= 2 else ""
                if _subj_key:
                    school_carry_by_subj.setdefault(_subj_key, []).append(carry_item)
                    continue  # Don't add to flat carryover list
            # For CHORE:: and MANUAL:: carryover — skip if today already has that chore
            if raw.startswith("CHORE::") and norm in known_chore_texts:
                continue
            carryover_items.append(carry_item)
    except Exception:
        pass

    # ── Inject tasks postponed TO this day from a previous day ───────────────
    try:
        from data_helpers import get_postponed_for_day as _get_postponed
        _postponed_labels = _get_postponed(child, iso)
        _seen_carry_norms = {_norm(it["text"]) for it in carryover_items}
        for _plabel in _postponed_labels:
            _pnorm = _norm(_plabel)
            if _pnorm in _seen_carry_norms:
                continue  # already in carryover from yesterday
            _seen_carry_norms.add(_pnorm)
            _ptid = f"CARRY::{child}::{iso}::{_plabel}"
            carryover_items.append({
                "text": _plabel,
                "task_id": _ptid,
                "done": _dl_done(progress, _ptid),
                "priority": "MEDIUM",
                "checkable": True,
                "is_header": False,
                "is_carryover": True,
                "is_postponed": True,
            })
    except Exception:
        pass

    # Compute which subjects from school_carry_by_subj are NOT in today's schedule.
    # These "orphaned" carryover subjects will be injected into a school block
    # post-loop instead of the flat Tasks/carryover section.
    _today_subjects = {b.get("subject", "").strip().lower() for b in school_raw}
    _orphan_school_carry: list = []
    for _osubj, _oitems in school_carry_by_subj.items():
        if _osubj not in _today_subjects:
            _orphan_school_carry.extend(_oitems)

    # ── Split tasks into timed (have explicit time hint) vs untimed ──────────
    # Timed tasks are placed at their hinted time position in the day list;
    # untimed tasks continue to use the "Lists with Mom" / Tasks-fallback slot.
    timed_task_groups: dict = {}   # "HH:MM" -> [item, ...]
    untimed_manual:    list = []
    for _it in manual_items:
        _hint = _parse_time_hint(_it["text"])
        if _hint:
            timed_task_groups.setdefault(_hint, []).append(_it)
        else:
            untimed_manual.append(_it)
    manual_items = untimed_manual

    timed_carry_groups: dict = {}  # same idea for carryover items
    untimed_carry:      list = []
    for _it in carryover_items:
        _hint = _parse_time_hint(_it["text"])
        if _hint:
            timed_carry_groups.setdefault(_hint, []).append(_it)
        else:
            untimed_carry.append(_it)
    carryover_items = untimed_carry

    # ── Pre-distribute school subjects across generic "School" slots ──────────
    import math as _math

    def _is_generic_school_slot(lbl: str) -> bool:
        """True only for slots like 'School', 'School / HW' — not 'Latin Class' etc."""
        lbl_low = lbl.strip().lower()
        # Must begin with the word "school" to qualify as a generic school block
        if not lbl_low.startswith("school"):
            return False
        return (_classify_slot(lbl) == "school"
                and "or video" not in lbl_low
                and "hw or"   not in lbl_low
                and "\u2014"  not in lbl
                and "—"       not in lbl)

    # Find subjects that will be claimed by hinted slots (e.g. "School — Math")
    _hinted_subjs: set = set()
    for _blk in merged:
        _lbl = _blk["label"]
        # Only hinted slots — those that start with "School" AND have "—" separator
        if (_classify_slot(_lbl) == "school"
                and not _is_generic_school_slot(_lbl)
                and ("\u2014" in _lbl or "—" in _lbl)):
            _hint = (_lbl.split("\u2014", 1)[1] if "\u2014" in _lbl
                     else _lbl.split("—", 1)[1]).strip()
            _hint_low = _hint.lower()
            for _b in school_raw:
                _s = _b.get("subject", "").strip()
                _s_low = _s.lower()
                if _hint_low in _s_low or _s_low in _hint_low:
                    _hinted_subjs.add(_s_low)
                if "math" in _hint_low and (_b.get("is_math") or _b.get("is_math_test")):
                    _hinted_subjs.add(_s_low)

    # Remaining blocks destined for generic School slots
    _generic_blocks = [b for b in school_raw
                       if b.get("subject", "").strip().lower() not in _hinted_subjs]

    def _subject_priority(block: dict) -> int:
        """
        Lower number = higher priority = goes into earlier School slots.
          1 — Core/first: Religion, Latin, Math (including all math work)
          2 — Demanding:  tests/quizzes/assessments in any subject,
                          essays and heavy writing assignments,
                          Science and History
          3 — Everything else (reading, art, music, poetry, memory work…)
        Schedule order within priority: Religion → Latin → Math → Science/History,
        then tests/essays, then lighter enrichment subjects.
        """
        subj = block.get("subject", "").lower()
        text = block.get("assignment_text", "").lower()
        _test_kws  = ("test", "quiz", "assessment", "exam")
        _write_kws = ("essay", "composition", "write out", "written assignment",
                      "writing assignment", "written report")
        # Priority 1 — non-negotiable morning subjects
        if "religion" in subj or "latin" in subj:
            return 1
        if block.get("is_math") or block.get("is_math_test") or "math" in subj:
            return 1
        # Priority 2 — mentally demanding; do while fresh
        if (block.get("is_math_test")
                or any(kw in text for kw in _test_kws)
                or any(kw in text for kw in _write_kws)):
            return 2
        if "science" in subj or "history" in subj or "grammar" in subj:
            return 2
        # Priority 3 — lighter enrichment
        return 3

    # Sort generic blocks: core first → difficult → other
    _generic_blocks.sort(key=_subject_priority)

    # Identify generic School slot positions by index
    _generic_school_idxs = [
        i for i, b in enumerate(merged) if _is_generic_school_slot(b["label"])]

    # ── Time-aware distribution of subjects across generic School slots ──────
    # Load today's calendar events so we can see what cuts into school time.
    _day_cal_events: list = []
    try:
        _day_cal_events = get_calendar_events_for_boys(iso)
    except Exception:
        pass
    # Also consider the cook-start constraint (relevant for afternoon school slots)
    try:
        from render_meals import load_meal_plan, _week_key, get_cook_start_for_day
        from datetime import date as _date_for_cook
        _cook_iso  = _date_for_cook.fromisoformat(iso)
        _cook_wk   = _week_key(_cook_iso)
        _cook_day  = _cook_iso.strftime("%A")
        _cook_plan = load_meal_plan(_cook_wk)
        _cook_data = _cook_plan.get("days", {}).get(_cook_day, {})
        _cook_entry = get_cook_start_for_day(_cook_data, weekday=_cook_day)
    except Exception:
        _cook_entry = None

    _SUBJECT_MINUTES = 45   # assumed minutes per school subject

    def _slot_available_minutes(slot_idx: int) -> int:
        """Compute school-usable minutes for the given merged[] slot index."""
        blk   = merged[slot_idx]
        start = blk["time_sort"]
        # End of this slot = start of the next block in the schedule
        end   = merged[slot_idx + 1]["time_sort"] if slot_idx + 1 < len(merged) else "15:00"
        start_m = _hhmm_to_min(start)
        end_m   = _hhmm_to_min(end)
        avail   = max(end_m - start_m, 0)
        # Subtract interruptions from calendar events that fall in this window
        for ev in _day_cal_events:
            et = ev.get("time")
            if not et or ev.get("all_day"):
                continue
            ee = ev.get("end_time") or et
            if start <= et < end:
                avail -= max(_hhmm_to_min(ee) - _hhmm_to_min(et), 0)
        # Subtract cook-start constraint if it falls in this window
        if _cook_entry:
            ct = _cook_entry["hhmm"]
            if start <= ct < end:
                avail -= max(_hhmm_to_min(end) - _hhmm_to_min(ct), 0)
        return max(avail, 0)

    _generic_slot_map: dict = {}   # merged-list index -> [school_raw blocks]
    if _generic_school_idxs and _generic_blocks:
        _slot_mins = [_slot_available_minutes(i) for i in _generic_school_idxs]
        _total_mins = sum(_slot_mins) or 1
        _remaining  = list(_generic_blocks)
        _total_subjs = len(_remaining)
        for _i, _idx in enumerate(_generic_school_idxs):
            if not _remaining:
                break
            _avail = _slot_mins[_i]
            # How many subjects fit in this window?  Pro-rate by share of total time.
            # Always give the first slot at least ceil(half the subjects) to keep
            # heavy work morning-weighted.
            if _i == 0:
                _share = max(
                    1,
                    _math.ceil(_total_subjs * (_avail / _total_mins))
                    if _total_mins > 0 else _math.ceil(_total_subjs / 2),
                )
                # First slot gets at least half regardless
                _share = max(_share, _math.ceil(_total_subjs / 2))
            else:
                _share = max(1, _avail // _SUBJECT_MINUTES) if _avail > 0 else 1
            # Cap so we don't exceed what's left
            _share = min(_share, len(_remaining))
            # On the last slot, absorb everything remaining
            if _i == len(_generic_school_idxs) - 1:
                _share = len(_remaining)
            _generic_slot_map[_idx] = _remaining[:_share]
            _remaining = _remaining[_share:]

    # Build the result list
    subjects_used: set = set()
    weekly_expanded: bool = False        # prevent double-expansion of weekly chores
    has_tasks_slot = any(
        "lists with mom" in b["label"].lower() or "go over lists" in b["label"].lower()
        for b in merged
    )
    result = []
    _laundry_extra_blocks: list = []     # laundry blocks to inject at 8:00 AM

    for blk_idx, blk in enumerate(merged):
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
            if hint == "":
                # Generic slot — use pre-assigned slice so subjects are
                # distributed evenly across all generic School slots.
                assigned = _generic_slot_map.get(blk_idx, [])
                subs = _school_sub_items(assigned, subjects_used, child, iso, "", progress,
                                         carry_by_subj=school_carry_by_subj)
            else:
                subs = _school_sub_items(school_raw, subjects_used, child, iso, hint, progress,
                                         carry_by_subj=school_carry_by_subj)
            item["sub_items"] = subs
            item["checkable"] = False

        # ── Morning Jobs ────────────────────────────────────────────────
        elif "morning jobs" in label_low:
            all_morning = daily_split.get("general", []) + daily_split["morning"]
            item["sub_items"] = _lines_to_sub_items(
                all_morning, child, iso, "morning", progress)
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
            item["done"]    = _dl_done(progress, tid)

        # ── Weekly Job(s) — expand only the FIRST occurrence ────────────
        elif "weekly job" in label_low or "jobs — weekly" in label_low or "jobs--weekly" in label_low:
            if not weekly_expanded:
                weekly_expanded = True
                _laundry_lines, _other_lines = _split_laundry_lines(weekly_today)
                if _laundry_lines:
                    # ── Break laundry into three timed blocks ────────────
                    # Step keywords → which timed block they belong to
                    # Morning  (08:00): start/load lines + the header line
                    # Midday   (12:00): switch/move lines
                    # Afternoon(15:00): bring up/fold/put away lines
                    _L_MORNING   = {"start", "load", "towels"}
                    _L_MIDDAY    = {"switch", "move"}
                    _L_AFTERNOON = {"bring", "fold", "put away", "put", "family fold"}
                    _lmorn = []   # morning sub-item lines
                    _lmid  = []   # midday sub-item lines
                    _laftn = []   # afternoon sub-item lines
                    for _ll in _laundry_lines:
                        _ls = _ll.strip().lstrip("\u2192-> ").lower()
                        if _ls.startswith("laundry"):
                            # header line goes in morning
                            _lmorn.append(_ll)
                        elif any(_ls.startswith(kw) for kw in _L_MIDDAY):
                            _lmid.append(_ll)
                        elif any(_ls.startswith(kw) for kw in _L_AFTERNOON) or "fold" in _ls:
                            _laftn.append(_ll)
                        else:
                            _lmorn.append(_ll)  # default → morning
                    def _laundry_block(subs_lines, hhmm, display_time, label):
                        subs = _lines_to_sub_items(subs_lines, child, iso, "laundry", progress)
                        if not subs:
                            return None
                        return {
                            "time":      display_time,
                            "time_sort": hhmm,
                            "end_time":  "",
                            "label":     label,
                            "kind":      "chore",
                            "checkable": False,
                            "task_id":   None,
                            "done":      False,
                            "sub_items": subs,
                        }
                    for _lb in (
                        _laundry_block(_lmorn, "08:15", "8:15 AM",  "Laundry — Start"),
                        _laundry_block(_lmid,  "12:00", "12:00 PM", "Laundry — Switch"),
                        _laundry_block(_laftn, "15:30", "3:30 PM",  "Laundry — Fold & Put Away"),
                    ):
                        if _lb:
                            _laundry_extra_blocks.append(_lb)
                    item["sub_items"] = _lines_to_sub_items(
                        _other_lines, child, iso, "weekly", progress)
                else:
                    item["sub_items"] = _lines_to_sub_items(
                        weekly_today, child, iso, "weekly", progress)
            else:
                # Second occurrence: simple informational row, no duplication
                item["sub_items"] = []
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
            item["done"]    = _dl_done(progress, tid)
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

    # ── Insert timed task groups at their correct time positions ─────────────
    # Tasks/chores whose text contained a time indicator (e.g. "at 10:00 AM",
    # "after breakfast") are placed as their own block at that time, so they
    # appear in the right spot in the chronological day list rather than being
    # lumped into the generic "Lists with Mom" / Tasks slot.
    all_hint_times = set(timed_task_groups) | set(timed_carry_groups)
    for _hint in sorted(all_hint_times):
        _carry  = [dict(i, is_carryover=True) for i in timed_carry_groups.get(_hint, [])]
        _manual = list(timed_task_groups.get(_hint, []))
        result.append({
            "time":      _hint_to_display(_hint),
            "time_sort": _hint,
            "end_time":  "",
            "label":     "Tasks",
            "kind":      "task",
            "checkable": False,
            "task_id":   None,
            "done":      False,
            "sub_items": _carry + _manual,
        })
    if _laundry_extra_blocks:
        result.extend(_laundry_extra_blocks)
        result.sort(key=lambda b: b["time_sort"])
    elif all_hint_times:
        result.sort(key=lambda b: b["time_sort"])

    # ── Orphaned school carryover → inject into last school block ────────────
    # Subjects that had carryover but aren't assigned today must still appear
    # in a school block (per user requirement), not in the flat Tasks section.
    if _orphan_school_carry:
        # Find the last school-kind block in result
        _last_school_idx = None
        for _ri, _rb in enumerate(result):
            if _rb.get("kind") == "school":
                _last_school_idx = _ri
        if _last_school_idx is not None:
            result[_last_school_idx]["sub_items"].extend(_orphan_school_carry)
        else:
            # No school block at all today — fall back to flat carryover
            carryover_items.extend(_orphan_school_carry)

    # ── Meal Prep reminder block (Lauren only) ────────────────────────────────
    # If the meal plan has a prep_notes entry for today, inject a checkable
    # "🍳 Meal Prep" task block.  Time = 30 min after the evening kitchen-clean
    # slot; falls back to 8:00 PM if that slot isn't found.
    if child in ("Lauren", "Mom"):
        try:
            from render_meals import load_meal_plan, _week_key
            from datetime import date as _prep_date
            _prep_dt   = _prep_date.fromisoformat(iso)
            _prep_note = (
                (load_meal_plan(_week_key(_prep_dt)).get("prep_notes") or {})
                .get(weekday, "")
                .strip()
            )
            if _prep_note:
                # Find the evening kitchen-clean slot to anchor the time
                _prep_hhmm = "20:00"
                for _rb in result:
                    if ("clean the kitchen" in (_rb.get("label") or "").lower()
                            and (_rb.get("time_sort") or "") >= "17:00"):
                        _kh = int(_rb["time_sort"].split(":")[0])
                        _km = int(_rb["time_sort"].split(":")[1])
                        _pm_total  = _kh * 60 + _km + 60
                        _prep_hhmm = f"{_pm_total // 60:02d}:{_pm_total % 60:02d}"
                        break
                _ph   = int(_prep_hhmm.split(":")[0])
                _pmin = int(_prep_hhmm.split(":")[1])
                _ampm = "AM" if _ph < 12 else "PM"
                _dh   = _ph if _ph <= 12 else _ph - 12
                _prep_tid = f"MEALPREP::Lauren::{iso}::meal_prep"
                result.append({
                    "time":      f"{_dh}:{_pmin:02d} {_ampm}",
                    "time_sort": _prep_hhmm,
                    "end_time":  "",
                    "label":     "🍳 Meal Prep",
                    "kind":      "task",
                    "checkable": False,
                    "task_id":   None,
                    "done":      False,
                    "sub_items": [
                        {
                            "text":      _prep_note,
                            "task_id":   None,
                            "done":      False,
                            "checkable": False,
                            "is_header": True,
                        },
                        {
                            "text":      "Done",
                            "task_id":   _prep_tid,
                            "done":      _dl_done(progress, _prep_tid),
                            "checkable": True,
                            "is_header": False,
                        },
                    ],
                })
                result.sort(key=lambda b: b["time_sort"])
        except Exception:
            pass

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
