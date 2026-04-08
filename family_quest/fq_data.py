"""
fq_data.py — Data models and I/O for Family Quest.

JSON flat-file storage:
  family_quest/data/quests.json   — quest records
  family_quest/data/xp.json       — per-child XP and history
  family_quest/data/rewards.json  — parent-defined rewards
  family_quest/data/streaks.json  — per-child streak tracking
"""
import json
import os
import uuid
from datetime import date

# ── Paths ─────────────────────────────────────────────────────────────────────
_DIR = os.path.join(os.path.dirname(__file__), "data")
QUESTS_FILE  = os.path.join(_DIR, "quests.json")
XP_FILE      = os.path.join(_DIR, "xp.json")
REWARDS_FILE = os.path.join(_DIR, "rewards.json")
STREAKS_FILE = os.path.join(_DIR, "streaks.json")

# ── Children (canonical display names, lowercase key) ─────────────────────────
CHILDREN_KEYS  = ["jp", "joseph", "michael", "james"]
CHILDREN_NAMES = {"jp": "JP", "joseph": "Joseph", "michael": "Michael", "james": "James"}

# ── Child name → key mapping (for sync from main app) ─────────────────────────
CHILD_NAME_TO_KEY = {"JP": "jp", "Joseph": "joseph", "Michael": "michael", "James": "james"}

# ── Quest types ───────────────────────────────────────────────────────────────
QUEST_TYPES = ["daily", "side", "boss", "event"]

# ── Level thresholds ──────────────────────────────────────────────────────────
LEVELS = [
    {"level": 1, "xp_min": 0,    "label": "Novice"},
    {"level": 2, "xp_min": 100,  "label": "Apprentice"},
    {"level": 3, "xp_min": 250,  "label": "Knight"},
    {"level": 4, "xp_min": 500,  "label": "Champion"},
    {"level": 5, "xp_min": 1000, "label": "Legend"},
]

# ── Streak milestone bonus XP ─────────────────────────────────────────────────
STREAK_MILESTONES = {3: 10, 7: 25, 14: 50, 30: 100}


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _load(path: str, default):
    os.makedirs(_DIR, exist_ok=True)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(path: str, data):
    os.makedirs(_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Quests ────────────────────────────────────────────────────────────────────

def load_quests() -> list:
    data = _load(QUESTS_FILE, [])
    return data if isinstance(data, list) else []


def save_quests(quests: list):
    _save(QUESTS_FILE, quests)


def get_quests_for_child(child_key: str, iso_date: str = "") -> list:
    """Return quests assigned to this child for the given date (or today)."""
    if not iso_date:
        iso_date = date.today().isoformat()
    return [
        q for q in load_quests()
        if child_key in q.get("assigned_to", [])
        and q.get("date") == iso_date
        and q.get("active", True)
    ]


def create_quest(title: str, quest_type: str, assigned_to: list,
                 xp_value: int, iso_date: str = "") -> dict:
    if not iso_date:
        iso_date = date.today().isoformat()
    quest = {
        "id":          str(uuid.uuid4())[:8],
        "title":       title.strip(),
        "type":        quest_type if quest_type in QUEST_TYPES else "daily",
        "assigned_to": [c for c in assigned_to if c in CHILDREN_KEYS],
        "xp_value":    max(1, int(xp_value)),
        "date":        iso_date,
        "active":      True,
        "completions": {},   # child_key -> True if done
        "synced":      False,
    }
    quests = load_quests()
    quests.append(quest)
    save_quests(quests)
    return quest


def delete_quest(quest_id: str) -> bool:
    quests = load_quests()
    before = len(quests)
    quests = [q for q in quests if q.get("id") != quest_id]
    save_quests(quests)
    return len(quests) < before


def deactivate_quest(quest_id: str) -> bool:
    quests = load_quests()
    for q in quests:
        if q.get("id") == quest_id:
            q["active"] = False
            save_quests(quests)
            return True
    return False


def is_completed(quest: dict, child_key: str) -> bool:
    return bool(quest.get("completions", {}).get(child_key))


# ── XP & Leveling ─────────────────────────────────────────────────────────────

def load_xp() -> dict:
    """Returns {child_key: {total_xp, history: [{quest_id, xp, ts, date}]}}."""
    data = _load(XP_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for key in CHILDREN_KEYS:
        data.setdefault(key, {"total_xp": 0, "history": []})
    return data


def save_xp(xp_data: dict):
    _save(XP_FILE, xp_data)


def get_level(total_xp: int) -> dict:
    """Return the level dict for the given XP total."""
    current = LEVELS[0]
    for lvl in LEVELS:
        if total_xp >= lvl["xp_min"]:
            current = lvl
    return current


def get_next_level(total_xp: int) -> dict | None:
    """Return next level dict, or None if already at max."""
    cur = get_level(total_xp)
    for lvl in LEVELS:
        if lvl["level"] == cur["level"] + 1:
            return lvl
    return None


def level_progress_pct(total_xp: int) -> int:
    """Return 0-100 progress toward next level."""
    cur  = get_level(total_xp)
    nxt  = get_next_level(total_xp)
    if nxt is None:
        return 100
    span = nxt["xp_min"] - cur["xp_min"]
    done = total_xp - cur["xp_min"]
    return min(100, int(done * 100 / span)) if span > 0 else 100


def complete_quest(quest_id: str, child_key: str) -> dict:
    """
    Mark a quest complete for this child, award XP, return updated XP state.
    Idempotent: calling again returns current state without double-awarding.
    Only allows completion of active quests dated today.
    Includes streak tracking and milestone bonus XP.
    """
    quests = load_quests()
    quest  = next((q for q in quests if q.get("id") == quest_id), None)
    if quest is None:
        return {"error": "quest_not_found"}
    if child_key not in quest.get("assigned_to", []):
        return {"error": "not_assigned"}
    if not quest.get("active", True):
        return {"error": "quest_inactive"}
    today = date.today().isoformat()
    if quest.get("date") and quest.get("date") != today:
        return {"error": "quest_not_today"}
    if quest.get("completions", {}).get(child_key):
        # Already done — return current state without re-awarding; xp_earned=0
        xp_data = load_xp()
        state = _xp_state(xp_data, child_key)
        state["xp_earned"] = 0
        state["streak_bonus"] = 0
        state["streak"] = get_streak(child_key)
        return state

    # Mark complete
    quest.setdefault("completions", {})[child_key] = True
    save_quests(quests)

    # Award base XP
    xp_data = load_xp()
    child_xp = xp_data.setdefault(child_key, {"total_xp": 0, "history": []})
    child_xp["total_xp"] = child_xp.get("total_xp", 0) + quest["xp_value"]
    child_xp.setdefault("history", []).append({
        "quest_id":    quest_id,
        "quest_title": quest["title"],
        "xp":          quest["xp_value"],
        "date":        quest.get("date", today),
        "ts":          _now_ts(),
    })
    save_xp(xp_data)

    # ── Check & update streak ─────────────────────────────────────────────────
    streak = _update_streak_for_child(child_key, today)
    streak_bonus = 0
    if streak.get("just_hit_milestone"):
        streak_bonus = STREAK_MILESTONES.get(streak["current"], 0)
        if streak_bonus:
            xp_data = load_xp()
            child_xp = xp_data[child_key]
            child_xp["total_xp"] += streak_bonus
            child_xp["history"].append({
                "quest_id":    "streak_bonus",
                "quest_title": f"🔥 {streak['current']}-Day Streak Bonus!",
                "xp":          streak_bonus,
                "date":        today,
                "ts":          _now_ts(),
            })
            save_xp(xp_data)

    state = _xp_state(xp_data, child_key)
    state["xp_earned"]    = quest["xp_value"]
    state["streak_bonus"] = streak_bonus
    state["streak"]       = streak

    # ── Auto-complete the full-day bonus if all other quests are now done ─────
    bonus_xp = _try_auto_complete_bonus(child_key, today)
    state["bonus_xp"] = bonus_xp

    return state


def _is_bonus_quest(q: dict) -> bool:
    return bool(q.get("is_bonus")) or "complete your entire school day" in q.get("title", "").lower()


def _try_auto_complete_bonus(child_key: str, today: str) -> int:
    """
    If every non-bonus active quest for this child today is completed,
    auto-award the 'Complete Your Entire School Day' bonus quest.
    Returns the XP awarded (0 if not triggered or already done).
    """
    quests = load_quests()
    today_quests = [q for q in quests
                    if child_key in q.get("assigned_to", [])
                    and q.get("date") == today
                    and q.get("active", True)]

    non_bonus = [q for q in today_quests if not _is_bonus_quest(q)]
    if not non_bonus:
        return 0

    all_done = all(q.get("completions", {}).get(child_key) for q in non_bonus)
    if not all_done:
        return 0

    bonus_list = [q for q in today_quests
                  if _is_bonus_quest(q)
                  and not q.get("completions", {}).get(child_key)]
    if not bonus_list:
        return 0

    total_bonus_xp = 0
    xp_data = load_xp()
    for bq in bonus_list:
        bq.setdefault("completions", {})[child_key] = True
        child_xp = xp_data.setdefault(child_key, {"total_xp": 0, "history": []})
        child_xp["total_xp"] = child_xp.get("total_xp", 0) + bq["xp_value"]
        child_xp.setdefault("history", []).append({
            "quest_id":    bq["id"],
            "quest_title": bq["title"],
            "xp":          bq["xp_value"],
            "date":        today,
            "ts":          _now_ts(),
        })
        total_bonus_xp += bq["xp_value"]
    save_quests(quests)
    save_xp(xp_data)
    return total_bonus_xp


def _xp_state(xp_data: dict, child_key: str) -> dict:
    total = xp_data[child_key].get("total_xp", 0)
    return {
        "child":        child_key,
        "total_xp":     total,
        "level":        get_level(total),
        "next_level":   get_next_level(total),
        "progress_pct": level_progress_pct(total),
    }


def get_child_xp_state(child_key: str) -> dict:
    xp_data = load_xp()
    return _xp_state(xp_data, child_key)


def _now_ts() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


# ── Streaks ───────────────────────────────────────────────────────────────────

def load_streaks() -> dict:
    data = _load(STREAKS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for key in CHILDREN_KEYS:
        data.setdefault(key, {"current": 0, "best": 0, "last_date": ""})
    return data


def save_streaks(streaks: dict):
    _save(STREAKS_FILE, streaks)


def get_streak(child_key: str) -> dict:
    streaks = load_streaks()
    s = streaks.get(child_key, {"current": 0, "best": 0, "last_date": ""})
    # Decay streak if last_date was before yesterday (missed a day)
    last = s.get("last_date", "")
    if last:
        from datetime import date as _d, timedelta
        today = _d.today().isoformat()
        yesterday = (_d.today() - timedelta(days=1)).isoformat()
        if last < yesterday and last != today:
            # Streak is broken — reset current (but preserve best)
            s = dict(s)
            s["current"] = 0
    s.setdefault("just_hit_milestone", False)
    return s


def _update_streak_for_child(child_key: str, today_iso: str) -> dict:
    """
    Called after a quest completion. If ALL daily quests for today are now
    done, increment the streak. Returns updated streak dict (with
    just_hit_milestone flag set if a bonus milestone was reached).
    """
    quests_today = get_quests_for_child(child_key, today_iso)
    daily_quests = [q for q in quests_today if q.get("type") == "daily"]

    # If no daily quests exist today, don't change streak
    if not daily_quests:
        streak = get_streak(child_key)
        streak["just_hit_milestone"] = False
        return streak

    all_done = all(q.get("completions", {}).get(child_key) for q in daily_quests)
    if not all_done:
        streak = get_streak(child_key)
        streak["just_hit_milestone"] = False
        return streak

    # All daily quests done — update streak
    streaks = load_streaks()
    s = streaks.get(child_key, {"current": 0, "best": 0, "last_date": ""})

    last_date = s.get("last_date", "")
    just_hit_milestone = False

    if last_date == today_iso:
        # Already counted today — idempotent
        s["just_hit_milestone"] = False
        return s

    from datetime import date as _d, timedelta
    today_d   = _d.fromisoformat(today_iso)
    yesterday = (today_d - timedelta(days=1)).isoformat()

    if last_date == yesterday:
        s["current"] = s.get("current", 0) + 1
    else:
        s["current"] = 1   # reset (new streak or gap)

    s["best"]      = max(s.get("best", 0), s["current"])
    s["last_date"] = today_iso

    # Check if we just hit a milestone
    if s["current"] in STREAK_MILESTONES:
        just_hit_milestone = True

    streaks[child_key] = s
    save_streaks(streaks)

    s = dict(s)
    s["just_hit_milestone"] = just_hit_milestone
    return s


# ── Rewards ───────────────────────────────────────────────────────────────────

def load_rewards() -> list:
    data = _load(REWARDS_FILE, [])
    return data if isinstance(data, list) else []


def save_rewards(rewards: list):
    _save(REWARDS_FILE, rewards)


def create_reward(label: str, xp_threshold: int = 0, level_threshold: int = 0) -> dict:
    reward = {
        "id":              str(uuid.uuid4())[:8],
        "label":           label.strip(),
        "xp_threshold":    max(0, int(xp_threshold)),
        "level_threshold": max(0, int(level_threshold)),
    }
    rewards = load_rewards()
    rewards.append(reward)
    save_rewards(rewards)
    return reward


def delete_reward(reward_id: str) -> bool:
    rewards = load_rewards()
    before  = len(rewards)
    rewards = [r for r in rewards if r.get("id") != reward_id]
    save_rewards(rewards)
    return len(rewards) < before


# ── Chore sync from Sancta Familia ────────────────────────────────────────────

def sync_chores_from_daily_schedule(today_iso: str = "") -> dict:
    """
    Pull today's chores from the main app's Day List for each child and
    create daily quests for any chores not already on the board.
    Returns {"created": [...], "skipped": [...], "errors": [...]}.
    """
    if not today_iso:
        today_iso = date.today().isoformat()

    import sys as _sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in _sys.path:
        _sys.path.insert(0, _root)

    from datetime import date as _d
    today_d = _d.fromisoformat(today_iso)
    weekday = today_d.strftime("%A")

    created = []
    skipped = []
    errors  = []

    for child_key in CHILDREN_KEYS:
        child_name = CHILDREN_NAMES[child_key]
        try:
            from daily_schedule_engine import build_day_list
            day_list = build_day_list(child_name, weekday, today_iso)

            existing        = get_quests_for_child(child_key, today_iso)
            existing_titles = {q.get("title", "").strip().lower() for q in existing}

            for item in day_list:
                if item.get("kind") != "chore":
                    continue
                title = (item.get("label") or "").strip()
                if not title:
                    continue
                if title.lower() in existing_titles:
                    skipped.append(f"{child_name}: {title}")
                    continue
                xp_val = _chore_xp(title)
                create_quest(title, "daily", [child_key], xp_value=xp_val,
                             iso_date=today_iso)
                # Mark synced flag so parent can see it came from Sancta Familia
                quests = load_quests()
                for q in quests:
                    if q.get("title") == title and child_key in q.get("assigned_to", []) \
                            and q.get("date") == today_iso:
                        q["synced"] = True
                save_quests(quests)
                created.append(f"{child_name}: {title}")
                existing_titles.add(title.lower())

        except Exception as exc:
            errors.append(f"{child_name}: {exc}")

    return {"created": created, "skipped": skipped, "errors": errors}


def _chore_xp(title: str) -> int:
    """Assign XP based on rough chore complexity keywords."""
    t = title.lower()
    if any(w in t for w in ("clean", "scrub", "mop", "vacuum", "dishes", "laundry")):
        return 15
    if any(w in t for w in ("bed", "tidy", "pick up", "sweep", "trash", "wipe")):
        return 10
    return 10


def sync_all_quests_for_child(child_name: str, iso_date: str = "") -> dict:
    """
    Called when a parent prints (approves) a child's day list.
    Creates daily quests for every school subject and chore block
    not already on the board for that child/day.
    Returns {"created": [...], "skipped": [...], "errors": [...]}.
    """
    if not iso_date:
        iso_date = date.today().isoformat()

    import sys as _sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in _sys.path:
        _sys.path.insert(0, _root)

    child_key = CHILD_NAME_TO_KEY.get(child_name)
    if not child_key:
        return {"created": [], "skipped": [], "errors": [f"Unknown child: {child_name}"]}

    today_d = date.fromisoformat(iso_date)
    weekday = today_d.strftime("%A")

    created, skipped, errors = [], [], []

    try:
        from daily_schedule_engine import build_day_list, extract_school_tasks_for_child
        existing        = get_quests_for_child(child_key, iso_date)
        existing_titles = {q.get("title", "").strip().lower() for q in existing}

        FULL_DAY_TITLE = "Complete Your Entire School Day"
        school_quests_created = 0

        # ── School subjects (one quest per subject) ──────────────────────────
        subjects = extract_school_tasks_for_child(child_name, weekday)
        for block in subjects:
            subj = block.get("subject", "").strip()
            assign = block.get("assignment_text", "").strip()
            if not subj:
                continue
            # Build a concise title
            if assign:
                brief = assign[:45].rstrip()
                if len(assign) > 45:
                    brief += "…"
                title = f"{subj} — {brief}"
            else:
                title = subj
            if title.lower() in existing_titles:
                skipped.append(f"{child_name}: {title}")
                continue
            q = create_quest(title, "daily", [child_key], xp_value=5, iso_date=iso_date)
            _mark_synced(q["id"], from_print=True)
            created.append(f"{child_name}: {title}")
            existing_titles.add(title.lower())
            school_quests_created += 1

        # ── Chore blocks (one quest per chore slot) ──────────────────────────
        day_list = build_day_list(child_name, weekday, iso_date)
        for item in day_list:
            if item.get("kind") != "chore":
                continue
            title = (item.get("label") or "").strip()
            if not title or title.lower() in existing_titles:
                skipped.append(f"{child_name}: {title}")
                continue
            q = create_quest(title, "daily", [child_key], xp_value=5, iso_date=iso_date)
            _mark_synced(q["id"], from_print=True)
            created.append(f"{child_name}: {title}")
            existing_titles.add(title.lower())

        # ── Full-day bonus ───────────────────────────────────────────────────
        if school_quests_created > 0 and FULL_DAY_TITLE.lower() not in existing_titles:
            q = create_quest(FULL_DAY_TITLE, "daily", [child_key],
                             xp_value=50, iso_date=iso_date)
            _mark_synced(q["id"], from_print=True, is_bonus=True)
            created.append(f"{child_name}: {FULL_DAY_TITLE}")

    except Exception as exc:
        errors.append(str(exc))

    return {"created": created, "skipped": skipped, "errors": errors}


def _mark_synced(quest_id: str, from_print: bool = False, is_bonus: bool = False):
    """Set synced/from_print/is_bonus flags on a just-created quest."""
    quests = load_quests()
    for q in quests:
        if q.get("id") == quest_id:
            q["synced"]     = True
            q["from_print"] = from_print
            if is_bonus:
                q["is_bonus"] = True
            break
    save_quests(quests)
