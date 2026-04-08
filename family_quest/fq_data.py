"""
fq_data.py — Data models and I/O for Family Quest.

JSON flat-file storage:
  family_quest/data/quests.json   — quest records
  family_quest/data/xp.json       — per-child XP and history
  family_quest/data/rewards.json  — parent-defined rewards
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

# ── Children (canonical display names, lowercase key) ─────────────────────────
CHILDREN_KEYS  = ["jp", "joseph", "michael", "james"]
CHILDREN_NAMES = {"jp": "JP", "joseph": "Joseph", "michael": "Michael", "james": "James"}

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
        return state

    # Mark complete
    quest.setdefault("completions", {})[child_key] = True
    save_quests(quests)

    # Award XP
    xp_data = load_xp()
    child_xp = xp_data.setdefault(child_key, {"total_xp": 0, "history": []})
    child_xp["total_xp"] = child_xp.get("total_xp", 0) + quest["xp_value"]
    child_xp.setdefault("history", []).append({
        "quest_id":    quest_id,
        "quest_title": quest["title"],
        "xp":          quest["xp_value"],
        "date":        quest.get("date", date.today().isoformat()),
        "ts":          _now_ts(),
    })
    save_xp(xp_data)
    return _xp_state(xp_data, child_key)


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
