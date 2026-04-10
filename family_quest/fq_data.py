"""
fq_data.py — Data models and I/O for Family Quest.

JSON flat-file storage:
  family_quest/data/quests.json      — quest records
  family_quest/data/xp.json         — per-child XP, coins, crystals, diamonds
  family_quest/data/rewards.json     — parent-defined rewards
  family_quest/data/streaks.json     — per-child streak tracking
  family_quest/data/characters.json  — selected character + roster per child
  family_quest/data/equipment.json   — 4 slot levels per child
  family_quest/data/inventory.json   — single-use item counts per child
  family_quest/data/stamina.json     — stamina per child
  family_quest/data/battles.json     — active/recent battle records
  family_quest/data/mines.json       — active/recent mine run records
  family_quest/data/boss_settings.json — parent-configured boss availability
"""
import json
import os
import uuid
import random
from datetime import date

# ── Paths ─────────────────────────────────────────────────────────────────────
_DIR = os.path.join(os.path.dirname(__file__), "data")
QUESTS_FILE       = os.path.join(_DIR, "quests.json")
XP_FILE           = os.path.join(_DIR, "xp.json")
REWARDS_FILE      = os.path.join(_DIR, "rewards.json")
STREAKS_FILE      = os.path.join(_DIR, "streaks.json")
REDEMPTIONS_FILE  = os.path.join(_DIR, "redemptions.json")
CHARACTERS_FILE   = os.path.join(_DIR, "characters.json")
EQUIPMENT_FILE    = os.path.join(_DIR, "equipment.json")
INVENTORY_FILE    = os.path.join(_DIR, "inventory.json")
STAMINA_FILE      = os.path.join(_DIR, "stamina.json")
BATTLES_FILE      = os.path.join(_DIR, "battles.json")
MINES_FILE        = os.path.join(_DIR, "mines.json")
BOSS_SETTINGS_FILE = os.path.join(_DIR, "boss_settings.json")

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

# ── Character definitions ─────────────────────────────────────────────────────
# Stats scale with equipment; these are BASE values at level 0 equipment
CHARACTERS = {
    "archer": {
        "name":        "Archer",
        "emoji":       "🏹",
        "description": "High attack, low defense. Hits hard but needs armor.",
        "base_attack":  8,
        "base_defense": 3,
        "base_health":  80,
        "special":     "Precision Shot — every 3rd hit deals double damage",
    },
    "fighter": {
        "name":        "Fighter",
        "emoji":       "⚔️",
        "description": "Balanced stats with a combo bonus on chains.",
        "base_attack":  6,
        "base_defense": 6,
        "base_health":  100,
        "special":     "Combo Strike — bonus attack when 3+ quests done in a row",
    },
    "defender": {
        "name":        "Defender",
        "emoji":       "🛡️",
        "description": "Low attack, high shield multiplier. Takes less damage.",
        "base_attack":  4,
        "base_defense": 10,
        "base_health":  120,
        "special":     "Iron Wall — shield absorbs 50% more penalty chores",
    },
}
DEFAULT_CHARACTER = "fighter"

# ── Equipment slot definitions ─────────────────────────────────────────────────
# Each slot has a max level and per-level bonuses
EQUIPMENT_SLOTS = {
    "sword": {
        "label": "Sword",
        "emoji": "⚔️",
        "stat":  "attack",
        # attack bonus per level (cumulative from 0)
        "bonuses": [0, 2, 4, 7, 11, 16],
        "upgrade_costs": [
            {"crystals": 10,  "diamonds": 0},
            {"crystals": 25,  "diamonds": 5},
            {"crystals": 50,  "diamonds": 15},
            {"crystals": 100, "diamonds": 30},
            {"crystals": 200, "diamonds": 60},
        ],
        "max_level": 5,
    },
    "shield": {
        "label": "Shield",
        "emoji": "🛡️",
        "stat":  "defense",
        "bonuses": [0, 2, 4, 7, 11, 16],
        "upgrade_costs": [
            {"crystals": 10,  "diamonds": 0},
            {"crystals": 25,  "diamonds": 5},
            {"crystals": 50,  "diamonds": 15},
            {"crystals": 100, "diamonds": 30},
            {"crystals": 200, "diamonds": 60},
        ],
        "max_level": 5,
    },
    "armor": {
        "label": "Armor",
        "emoji": "🧥",
        "stat":  "defense",
        "bonuses": [0, 1, 3, 6, 10, 15],
        "upgrade_costs": [
            {"crystals": 8,   "diamonds": 0},
            {"crystals": 20,  "diamonds": 3},
            {"crystals": 40,  "diamonds": 10},
            {"crystals": 80,  "diamonds": 25},
            {"crystals": 160, "diamonds": 50},
        ],
        "max_level": 5,
    },
    "other": {
        "label": "Ring",
        "emoji": "💍",
        "stat":  "attack",
        "bonuses": [0, 1, 2, 4, 7, 11],
        "upgrade_costs": [
            {"crystals": 5,   "diamonds": 0},
            {"crystals": 15,  "diamonds": 2},
            {"crystals": 30,  "diamonds": 8},
            {"crystals": 60,  "diamonds": 20},
            {"crystals": 120, "diamonds": 40},
        ],
        "max_level": 5,
    },
}

# ── Boss difficulty table ─────────────────────────────────────────────────────
BOSS_DIFFICULTIES = {
    "easy": {
        "label": "Easy",
        "emoji": "🟢",
        "hp": 30,
        "stamina_cost": 1,
        "chores_per_hit": 1,
        "win_coins": 20,
        "win_xp": 15,
        "lose_chores": 2,
        "description": "Goblin — 30 HP, 1 quest = 1 hit",
    },
    "medium": {
        "label": "Medium",
        "emoji": "🟡",
        "hp": 50,
        "stamina_cost": 2,
        "chores_per_hit": 1,
        "win_coins": 40,
        "win_xp": 25,
        "lose_chores": 4,
        "description": "Orc — 50 HP, 1 quest = 1 hit",
    },
    "hard": {
        "label": "Hard",
        "emoji": "🟠",
        "hp": 80,
        "stamina_cost": 3,
        "chores_per_hit": 2,
        "win_coins": 70,
        "win_xp": 40,
        "lose_chores": 6,
        "description": "Dragon — 80 HP, 2 quests = 1 hit",
    },
    "legendary": {
        "label": "Legendary",
        "emoji": "🔴",
        "hp": 150,
        "stamina_cost": 5,
        "chores_per_hit": 3,
        "win_coins": 150,
        "win_xp": 75,
        "lose_chores": 10,
        "description": "Demon Lord — 150 HP, 3 quests = 1 hit",
    },
}

# ── Boss type definitions ─────────────────────────────────────────────────────
BOSS_TYPES = {
    "goblin":    {"label": "Goblin",    "emoji": "👺", "description": "A sneaky green menace"},
    "orc":       {"label": "Orc",       "emoji": "👹", "description": "A hulking brutish warrior"},
    "troll":     {"label": "Troll",     "emoji": "🧌", "description": "A massive cave-dwelling beast"},
    "dragon":    {"label": "Dragon",    "emoji": "🐉", "description": "An ancient fire-breathing terror"},
    "demon_lord":{"label": "Demon Lord","emoji": "😈", "description": "The ultimate evil overlord"},
    "skeleton":  {"label": "Skeleton",  "emoji": "💀", "description": "An undead warrior risen from the grave"},
    "witch":     {"label": "Witch",     "emoji": "🧙", "description": "A dark sorceress with powerful magic"},
}

# ── Mine type definitions ─────────────────────────────────────────────────────
MINE_TYPES = {
    "gold": {
        "label":        "Gold Mine",
        "emoji":        "🪙",
        "resource":     "coins",
        "base_rate":    10,
        "duration_min": 10,
        "stamina_cost": 1,
    },
    "crystal": {
        "label":        "Crystal Mine",
        "emoji":        "💎",
        "resource":     "crystals",
        "base_rate":    1,
        "duration_min": 10,
        "stamina_cost": 1,
    },
    "diamond": {
        "label":        "Diamond Mine",
        "emoji":        "💠",
        "resource":     "diamonds",
        "base_rate":    1,
        "duration_min": 10,
        "stamina_cost": 2,
    },
}

# ── Stamina config ─────────────────────────────────────────────────────────────
MAX_STAMINA = 10

# ── Single-use items ──────────────────────────────────────────────────────────
ITEMS = {
    "battle_axe": {
        "label":       "Battle Axe",
        "emoji":       "🪓",
        "description": "Doubles boss damage for one battle",
        "use_in":      "boss",
    },
    "hammer": {
        "label":       "Hammer",
        "emoji":       "🔨",
        "description": "1.5× mine yield for one run",
        "use_in":      "mine",
    },
}


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
        "completions": {},
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
    """Returns {child_key: {total_xp, coins, crystals, diamonds, history, coin_history}}."""
    data = _load(XP_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for key in CHILDREN_KEYS:
        data.setdefault(key, {"total_xp": 0, "history": []})
        # Ensure resource fields exist
        data[key].setdefault("coins", 0)
        data[key].setdefault("crystals", 0)
        data[key].setdefault("diamonds", 0)
    return data


def save_xp(xp_data: dict):
    _save(XP_FILE, xp_data)


def award_partial_xp(child_key: str, amount: int, label: str,
                     iso_date: str = "") -> dict:
    """
    Award XP directly (not via quest completion) — used for per-step school awards.
    Returns the updated XP state dict (same shape as complete_quest).
    """
    if amount <= 0 or child_key not in CHILDREN_KEYS:
        return {}
    today = iso_date or date.today().isoformat()
    xp_data = load_xp()
    child_xp = xp_data.setdefault(child_key, {"total_xp": 0, "coins": 0, "history": []})
    child_xp["total_xp"] = child_xp.get("total_xp", 0) + amount
    child_xp["coins"]    = child_xp.get("coins", 0) + amount
    child_xp.setdefault("coin_history", []).append({
        "type": "earned", "amount": amount,
        "from": label, "date": today, "ts": _now_ts(),
    })
    child_xp.setdefault("history", []).append({
        "quest_id":    "schedule_step",
        "quest_title": label,
        "xp":          amount,
        "date":        today,
        "ts":          _now_ts(),
    })
    save_xp(xp_data)
    state = _xp_state(xp_data, child_key)
    state["xp_earned"]    = amount
    state["streak_bonus"] = 0
    state["bonus_xp"]     = 0
    state["stamina"]      = get_stamina(child_key)
    return state


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


# ── Coins ─────────────────────────────────────────────────────────────────────

def get_coins(child_key: str) -> int:
    xp_data = load_xp()
    return xp_data.get(child_key, {}).get("coins", 0)


def award_coins(child_key: str, amount: int, quest_title: str = "", iso: str = "") -> int:
    if amount <= 0:
        return get_coins(child_key)
    xp_data = load_xp()
    child_xp = xp_data.setdefault(child_key, {"total_xp": 0, "coins": 0, "history": []})
    child_xp["coins"] = child_xp.get("coins", 0) + amount
    child_xp.setdefault("coin_history", []).append({
        "type":   "earned",
        "amount": amount,
        "from":   quest_title,
        "date":   iso or date.today().isoformat(),
        "ts":     _now_ts(),
    })
    save_xp(xp_data)
    return child_xp["coins"]


def spend_coins(child_key: str, amount: int, label: str = "") -> bool:
    xp_data = load_xp()
    child_xp = xp_data.setdefault(child_key, {"total_xp": 0, "coins": 0, "history": []})
    current = child_xp.get("coins", 0)
    if current < amount:
        return False
    child_xp["coins"] = current - amount
    child_xp.setdefault("coin_history", []).append({
        "type":   "spent",
        "amount": -amount,
        "from":   label,
        "date":   date.today().isoformat(),
        "ts":     _now_ts(),
    })
    save_xp(xp_data)
    return True


# ── Crystals & Diamonds ────────────────────────────────────────────────────────

def get_crystals(child_key: str) -> int:
    return load_xp().get(child_key, {}).get("crystals", 0)


def get_diamonds(child_key: str) -> int:
    return load_xp().get(child_key, {}).get("diamonds", 0)


def award_resource(child_key: str, resource: str, amount: int, label: str = "") -> int:
    """Award coins, crystals, or diamonds. Returns new balance."""
    if resource == "coins":
        return award_coins(child_key, amount, label)
    if resource not in ("crystals", "diamonds"):
        return 0
    if amount <= 0:
        return load_xp().get(child_key, {}).get(resource, 0)
    xp_data = load_xp()
    child_xp = xp_data.setdefault(child_key, {"total_xp": 0, "coins": 0, "crystals": 0, "diamonds": 0, "history": []})
    child_xp[resource] = child_xp.get(resource, 0) + amount
    child_xp.setdefault(f"{resource}_history", []).append({
        "type": "earned", "amount": amount,
        "from": label, "date": date.today().isoformat(), "ts": _now_ts(),
    })
    save_xp(xp_data)
    return child_xp[resource]


def spend_resource(child_key: str, resource: str, amount: int, label: str = "") -> bool:
    """Spend coins, crystals, or diamonds. Returns True if successful."""
    if resource == "coins":
        return spend_coins(child_key, amount, label)
    if resource not in ("crystals", "diamonds"):
        return False
    xp_data = load_xp()
    child_xp = xp_data.setdefault(child_key, {"total_xp": 0, "coins": 0, "crystals": 0, "diamonds": 0, "history": []})
    current = child_xp.get(resource, 0)
    if current < amount:
        return False
    child_xp[resource] = current - amount
    child_xp.setdefault(f"{resource}_history", []).append({
        "type": "spent", "amount": -amount,
        "from": label, "date": date.today().isoformat(), "ts": _now_ts(),
    })
    save_xp(xp_data)
    return True


# ── Characters ────────────────────────────────────────────────────────────────

def load_characters() -> dict:
    data = _load(CHARACTERS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for key in CHILDREN_KEYS:
        data.setdefault(key, {
            "selected": DEFAULT_CHARACTER,
            "unlocked": list(CHARACTERS.keys()),
        })
    return data


def save_characters(chars: dict):
    _save(CHARACTERS_FILE, chars)


def get_character(child_key: str) -> dict:
    chars = load_characters()
    selected = chars.get(child_key, {}).get("selected", DEFAULT_CHARACTER)
    if selected not in CHARACTERS:
        selected = DEFAULT_CHARACTER
    return {"key": selected, **CHARACTERS[selected]}


def set_character(child_key: str, char_key: str) -> bool:
    if char_key not in CHARACTERS:
        return False
    chars = load_characters()
    chars.setdefault(child_key, {"selected": DEFAULT_CHARACTER, "unlocked": list(CHARACTERS.keys())})
    chars[child_key]["selected"] = char_key
    save_characters(chars)
    return True


# ── Equipment ─────────────────────────────────────────────────────────────────

def load_equipment() -> dict:
    data = _load(EQUIPMENT_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for key in CHILDREN_KEYS:
        data.setdefault(key, {slot: 0 for slot in EQUIPMENT_SLOTS})
    return data


def save_equipment(eq: dict):
    _save(EQUIPMENT_FILE, eq)


def get_equipment(child_key: str) -> dict:
    eq = load_equipment()
    child_eq = eq.get(child_key, {slot: 0 for slot in EQUIPMENT_SLOTS})
    # Ensure all slots present
    for slot in EQUIPMENT_SLOTS:
        child_eq.setdefault(slot, 0)
    return child_eq


def get_attack_stat(child_key: str) -> int:
    """Total attack = character base + equipment bonuses."""
    char = get_character(child_key)
    eq   = get_equipment(child_key)
    attack = char["base_attack"]
    for slot_key, slot_def in EQUIPMENT_SLOTS.items():
        if slot_def["stat"] == "attack":
            lvl = eq.get(slot_key, 0)
            attack += slot_def["bonuses"][lvl]
    return attack


def get_defense_stat(child_key: str) -> int:
    """Total defense = character base + equipment bonuses."""
    char = get_character(child_key)
    eq   = get_equipment(child_key)
    defense = char["base_defense"]
    for slot_key, slot_def in EQUIPMENT_SLOTS.items():
        if slot_def["stat"] == "defense":
            lvl = eq.get(slot_key, 0)
            defense += slot_def["bonuses"][lvl]
    return defense


def get_health_stat(child_key: str) -> int:
    """Total health = character base health (armor level boosts it slightly)."""
    char = get_character(child_key)
    eq   = get_equipment(child_key)
    health = char.get("base_health", 100)
    armor_lvl = eq.get("armor", 0)
    health += armor_lvl * 10
    return health


def upgrade_equipment(child_key: str, slot_key: str) -> dict:
    """
    Upgrade one equipment slot by 1 level.
    Deducts crystal/diamond cost.
    Returns {"ok": True, "new_level": N} or {"error": "..."}.
    """
    if slot_key not in EQUIPMENT_SLOTS:
        return {"error": "invalid slot"}
    slot_def = EQUIPMENT_SLOTS[slot_key]
    eq = load_equipment()
    child_eq = eq.setdefault(child_key, {s: 0 for s in EQUIPMENT_SLOTS})
    current_level = child_eq.get(slot_key, 0)
    if current_level >= slot_def["max_level"]:
        return {"error": "Already at max level"}
    cost = slot_def["upgrade_costs"][current_level]
    # Check resources
    xp_data = load_xp()
    child_xp = xp_data.get(child_key, {})
    crystals_needed = cost.get("crystals", 0)
    diamonds_needed = cost.get("diamonds", 0)
    if child_xp.get("crystals", 0) < crystals_needed:
        return {"error": f"Need {crystals_needed} crystals (you have {child_xp.get('crystals',0)})"}
    if child_xp.get("diamonds", 0) < diamonds_needed:
        return {"error": f"Need {diamonds_needed} diamonds (you have {child_xp.get('diamonds',0)})"}
    # Deduct
    label = f"Upgrade {slot_def['label']} to level {current_level + 1}"
    spend_resource(child_key, "crystals", crystals_needed, label)
    if diamonds_needed:
        spend_resource(child_key, "diamonds", diamonds_needed, label)
    # Increment
    eq = load_equipment()
    eq.setdefault(child_key, {s: 0 for s in EQUIPMENT_SLOTS})
    eq[child_key][slot_key] = current_level + 1
    save_equipment(eq)
    return {"ok": True, "new_level": current_level + 1, "slot": slot_key}


# ── Inventory (single-use items) ──────────────────────────────────────────────

def load_inventory() -> dict:
    data = _load(INVENTORY_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for key in CHILDREN_KEYS:
        data.setdefault(key, {item: 0 for item in ITEMS})
    return data


def save_inventory(inv: dict):
    _save(INVENTORY_FILE, inv)


def get_inventory(child_key: str) -> dict:
    inv = load_inventory()
    child_inv = inv.get(child_key, {})
    for item in ITEMS:
        child_inv.setdefault(item, 0)
    return child_inv


def award_item(child_key: str, item_key: str, amount: int = 1) -> bool:
    if item_key not in ITEMS:
        return False
    inv = load_inventory()
    inv.setdefault(child_key, {item: 0 for item in ITEMS})
    inv[child_key][item_key] = inv[child_key].get(item_key, 0) + amount
    save_inventory(inv)
    return True


def consume_item(child_key: str, item_key: str) -> bool:
    """Consume 1 of the given item. Returns True if successful."""
    inv = load_inventory()
    inv.setdefault(child_key, {item: 0 for item in ITEMS})
    current = inv[child_key].get(item_key, 0)
    if current <= 0:
        return False
    inv[child_key][item_key] = current - 1
    save_inventory(inv)
    return True


# ── Stamina ───────────────────────────────────────────────────────────────────

def load_stamina() -> dict:
    data = _load(STAMINA_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for key in CHILDREN_KEYS:
        data.setdefault(key, {"current": MAX_STAMINA, "last_refill_date": ""})
    return data


def save_stamina(st: dict):
    _save(STAMINA_FILE, st)


def get_stamina(child_key: str) -> int:
    st = load_stamina()
    return st.get(child_key, {}).get("current", MAX_STAMINA)


def refill_stamina(child_key: str, amount: int = MAX_STAMINA) -> int:
    """Award stamina up to MAX. Returns new value."""
    st = load_stamina()
    child_st = st.setdefault(child_key, {"current": MAX_STAMINA, "last_refill_date": ""})
    child_st["current"] = min(MAX_STAMINA, child_st.get("current", 0) + amount)
    child_st["last_refill_date"] = date.today().isoformat()
    save_stamina(st)
    return child_st["current"]


def spend_stamina(child_key: str, amount: int) -> bool:
    """Spend stamina. Returns True if successful."""
    st = load_stamina()
    child_st = st.setdefault(child_key, {"current": MAX_STAMINA, "last_refill_date": ""})
    current = child_st.get("current", 0)
    if current < amount:
        return False
    child_st["current"] = current - amount
    save_stamina(st)
    return True


def _auto_refill_stamina_if_needed(child_key: str):
    """Called on daily quest completion; refill stamina when all dailies complete."""
    pass  # Called after quests complete check below


# ── Boss Settings (parent-configured) ─────────────────────────────────────────

def load_boss_settings() -> dict:
    data = _load(BOSS_SETTINGS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("available", True)
    data.setdefault("difficulty", "medium")
    data.setdefault("boss_type", "orc")
    data.setdefault("exchange_rate", 1)
    return data


def get_exchange_rate() -> int:
    """Return cents per coin for parent tracking (e.g. 1 = 1¢ per coin)."""
    return int(load_boss_settings().get("exchange_rate", 1))


def save_boss_settings(settings: dict):
    _save(BOSS_SETTINGS_FILE, settings)


def get_active_difficulty() -> str:
    return load_boss_settings().get("difficulty", "medium")


# ── Boss Battle Engine ─────────────────────────────────────────────────────────

def load_battles() -> list:
    data = _load(BATTLES_FILE, [])
    return data if isinstance(data, list) else []


def save_battles(battles: list):
    _save(BATTLES_FILE, battles)


def get_active_battle(child_key: str) -> dict | None:
    battles = load_battles()
    for b in battles:
        if b.get("child") == child_key and b.get("status") == "active":
            return b
    return None


def start_boss_battle(child_key: str, difficulty: str = "", use_battle_axe: bool = False) -> dict:
    """
    Begin a boss battle for this child based on today's completed quests.
    Returns the battle result immediately (battles are resolved instantly
    based on quest count at time of starting).
    """
    if not difficulty:
        difficulty = get_active_difficulty()
    if difficulty not in BOSS_DIFFICULTIES:
        difficulty = "medium"

    diff = BOSS_DIFFICULTIES[difficulty]

    # Check stamina
    stamina_cost = diff["stamina_cost"]
    if get_stamina(child_key) < stamina_cost:
        return {"error": f"Not enough stamina (need {stamina_cost}, have {get_stamina(child_key)})"}

    # Check boss settings
    settings = load_boss_settings()
    if not settings.get("available", True):
        return {"error": "No boss available today — check back later!"}

    # Count today's completed quests
    today = date.today().isoformat()
    quests = get_quests_for_child(child_key, today)
    completed_count = sum(1 for q in quests if is_completed(q, child_key) and not _is_bonus_quest(q))

    if completed_count == 0:
        return {"error": "Complete at least one quest first!"}

    # Calculate attack hits
    chores_per_hit = diff["chores_per_hit"]
    # Sword level reduces quests needed per hit
    eq = get_equipment(child_key)
    sword_lvl = eq.get("sword", 0)
    # Each sword level reduces chores_per_hit by 0.2 (floored at 1)
    effective_chores_per_hit = max(1, chores_per_hit - int(sword_lvl * 0.5))

    base_hits = completed_count // effective_chores_per_hit
    extra_hits_remainder = 1 if (completed_count % effective_chores_per_hit) > 0 else 0
    total_hits = base_hits + extra_hits_remainder

    char = get_character(child_key)
    attack = get_attack_stat(child_key)

    # Battle axe doubles first hit
    axe_used = False
    if use_battle_axe and get_inventory(child_key).get("battle_axe", 0) > 0:
        consume_item(child_key, "battle_axe")
        axe_used = True
        total_hits = total_hits * 2  # axe effectively doubles all hits

    # Each hit deals attack damage
    total_damage = total_hits * attack
    boss_hp = diff["hp"]
    won = total_damage >= boss_hp

    # Spend stamina
    spend_stamina(child_key, stamina_cost)

    # Apply outcome
    battle_id = str(uuid.uuid4())[:8]
    result = {
        "id":             battle_id,
        "child":          child_key,
        "difficulty":     difficulty,
        "boss_hp":        boss_hp,
        "total_damage":   total_damage,
        "total_hits":     total_hits,
        "completed_quests": completed_count,
        "attack_stat":    attack,
        "axe_used":       axe_used,
        "won":            won,
        "status":         "complete",
        "date":           today,
        "ts":             _now_ts(),
    }

    if won:
        # Award coins and XP
        win_coins = diff["win_coins"]
        win_xp    = diff["win_xp"]
        award_coins(child_key, win_coins, f"Boss Victory ({difficulty})")
        xp_data = load_xp()
        child_xp = xp_data.setdefault(child_key, {"total_xp": 0, "coins": 0, "history": []})
        child_xp["total_xp"] = child_xp.get("total_xp", 0) + win_xp
        child_xp.setdefault("history", []).append({
            "quest_id":    f"boss_{battle_id}",
            "quest_title": f"⚔️ Boss Victory ({difficulty.title()})!",
            "xp":          win_xp,
            "date":        today,
            "ts":          _now_ts(),
        })
        save_xp(xp_data)
        result["win_coins"]    = win_coins
        result["win_xp"]       = win_xp
        result["message"]      = f"Victory! You defeated the boss and earned 🪙{win_coins} coins + {win_xp} XP!"
    else:
        # Penalty chores — reduced by armor+shield
        base_penalty = diff["lose_chores"]
        defense = get_defense_stat(child_key)
        # Each point of defense reduces penalty by 0.2 (min 1)
        penalty_reduction = int(defense * 0.2)
        penalty_chores    = max(1, base_penalty - penalty_reduction)

        # Defender special: extra 50% reduction
        if char.get("key") == "defender":
            penalty_chores = max(1, int(penalty_chores * 0.5))

        # Create real penalty quests assigned to the child (persist them)
        for i in range(penalty_chores):
            create_quest(
                title      = f"⚔️ Penalty Chore #{i + 1} (Boss Defeat)",
                quest_type = "side",
                assigned_to = [child_key],
                xp_value   = 3,
                iso_date   = today,
            )

        result["penalty_chores"] = penalty_chores
        result["message"] = (
            f"Defeated! The boss had too much HP. "
            f"{penalty_chores} penalty chore{'s have' if penalty_chores != 1 else ' has'} been added to your quest list!"
        )

    # Record battle
    battles = load_battles()
    battles.append(result)
    # Keep last 50 battles
    if len(battles) > 50:
        battles = battles[-50:]
    save_battles(battles)

    return result


def get_recent_battles(child_key: str, limit: int = 5) -> list:
    battles = load_battles()
    child_battles = [b for b in battles if b.get("child") == child_key]
    return list(reversed(child_battles[-limit:]))


# ── Mine Run Engine ────────────────────────────────────────────────────────────

def load_mines() -> list:
    data = _load(MINES_FILE, [])
    return data if isinstance(data, list) else []


def save_mines(mines: list):
    _save(MINES_FILE, mines)


def get_active_mine(child_key: str) -> dict | None:
    mines = load_mines()
    for m in mines:
        if m.get("child") == child_key and m.get("status") == "active":
            return m
    return None


def start_mine_run(child_key: str, mine_type: str, use_hammer: bool = False) -> dict:
    """
    Start a mine run. Returns the mine run record with start_ts.
    Mine runs resolve when the child clicks 'Collect'.
    Requires at least 1 completed quest today (chore-driven mechanic).
    """
    if mine_type not in MINE_TYPES:
        return {"error": "Invalid mine type"}

    mine_def = MINE_TYPES[mine_type]
    stamina_cost = mine_def["stamina_cost"]

    # Require at least 1 completed quest — mine runs are powered by chores
    today = date.today().isoformat()
    quests = get_quests_for_child(child_key, today)
    completed_today = sum(1 for q in quests if is_completed(q, child_key))
    if completed_today == 0:
        return {"error": "Complete at least one quest before starting a mine run!"}

    if get_stamina(child_key) < stamina_cost:
        return {"error": f"Not enough stamina (need {stamina_cost}, have {get_stamina(child_key)})"}

    # Can't start if already mining
    if get_active_mine(child_key):
        return {"error": "You already have an active mine run! Collect it first."}

    # Use hammer?
    hammer_used = False
    if use_hammer and get_inventory(child_key).get("hammer", 0) > 0:
        consume_item(child_key, "hammer")
        hammer_used = True

    spend_stamina(child_key, stamina_cost)

    from datetime import datetime
    start_ts = datetime.now().timestamp()

    mine_id = str(uuid.uuid4())[:8]
    run = {
        "id":               mine_id,
        "child":            child_key,
        "mine_type":        mine_type,
        "resource":         mine_def["resource"],
        "base_rate":        mine_def["base_rate"],
        "duration_min":     mine_def["duration_min"],
        "hammer_used":      hammer_used,
        "start_ts":         start_ts,
        "quests_at_start":  completed_today,
        "status":           "active",
        "date":             date.today().isoformat(),
        "ts":               _now_ts(),
    }

    mines = load_mines()
    mines.append(run)
    save_mines(mines)

    return run


def collect_mine_run(child_key: str, mine_id: str) -> dict:
    """
    Resolve a mine run and award resources.
    Returns the result with yield, cave_in flag, consolation loot.
    """
    mines = load_mines()
    run = next((m for m in mines if m.get("id") == mine_id and m.get("child") == child_key), None)
    if not run:
        return {"error": "Mine run not found"}
    if run.get("status") != "active":
        return {"error": "Mine already collected"}

    from datetime import datetime
    now_ts = datetime.now().timestamp()
    start_ts = run.get("start_ts", now_ts)
    elapsed_min = (now_ts - start_ts) / 60.0

    duration_min = run.get("duration_min", 10)
    base_rate    = run.get("base_rate", 1)
    resource     = run.get("resource", "coins")
    hammer_used  = run.get("hammer_used", False)

    cave_in = False
    consolation = None
    final_yield = 0
    speed_bonus_pct = 0

    if elapsed_min >= duration_min * 3:
        # Took 3× too long — cave in!
        # Consolation loot roll (crystals/diamonds only — spec: 5%→100, 25%→20, 50%→5):
        #   5%  → 100 crystals or diamonds (jackpot!)
        #   25% → 20 crystals or diamonds
        #   50% → 5 crystals or diamonds
        #   20% → nothing (no payout)
        cave_in = True
        roll = random.random()
        res = random.choice(["crystals", "diamonds"])
        if roll < 0.05:
            consolation = {"resource": res, "amount": 100}
        elif roll < 0.30:
            consolation = {"resource": res, "amount": 20}
        elif roll < 0.80:
            consolation = {"resource": res, "amount": 5}
        else:
            consolation = None
    elif elapsed_min >= duration_min * 1.5:
        # Took between 1.5× and 3× — partial yield (50%)
        base_yield = int(base_rate * elapsed_min)
        final_yield = max(1, base_yield // 2)
    elif elapsed_min >= duration_min:
        # Collected in the target window — full yield with possible speed bonus
        base_yield = int(base_rate * elapsed_min)
        final_yield = base_yield
        # Speed bonus tiers based on how quickly above target:
        #   ≤1.1× target (within 10% of optimal) — lightning fast: +50%
        #   ≤1.25× target — fast: +25%
        #   ≤1.5× target — on time: +10%
        if elapsed_min <= duration_min * 1.1:
            speed_bonus_pct = 50
        elif elapsed_min <= duration_min * 1.25:
            speed_bonus_pct = 25
        else:
            speed_bonus_pct = 10
        final_yield = int(final_yield * (1 + speed_bonus_pct / 100))
    else:
        # Collected early — partial yield proportional to time elapsed
        base_yield = int(base_rate * elapsed_min)
        final_yield = max(1, base_yield)
        # Early collect speed bonus: the faster you collect after starting, the higher the bonus
        # (encourages completing quests quickly to run back and collect)
        early_pct = elapsed_min / duration_min  # 0.0 to 1.0
        if early_pct >= 0.75:
            speed_bonus_pct = 20
        elif early_pct >= 0.5:
            speed_bonus_pct = 40
        else:
            speed_bonus_pct = 60
        final_yield = int(final_yield * (1 + speed_bonus_pct / 100))

    # Apply hammer multiplier
    if hammer_used and not cave_in:
        final_yield = int(final_yield * 1.5)

    # Award resources
    if cave_in:
        if consolation:
            award_resource(child_key, consolation["resource"], consolation["amount"],
                           f"{MINE_TYPES.get(run['mine_type'],{}).get('label','Mine')} Consolation")
    else:
        if final_yield > 0:
            award_resource(child_key, resource, final_yield,
                           f"{MINE_TYPES.get(run['mine_type'],{}).get('label','Mine')} Yield")

    # Mark run complete
    run["status"]         = "complete"
    run["elapsed_min"]    = round(elapsed_min, 2)
    run["cave_in"]        = cave_in
    run["consolation"]    = consolation
    run["final_yield"]    = final_yield
    run["speed_bonus_pct"] = speed_bonus_pct
    run["collect_ts"]     = now_ts

    save_mines(mines)

    # Build resource totals for UI update
    xp_snap = load_xp().get(child_key, {})

    result = {
        "id":              mine_id,
        "mine_type":       run["mine_type"],
        "resource":        resource,
        "cave_in":         cave_in,
        "final_yield":     final_yield,
        "elapsed_min":     round(elapsed_min, 2),
        "hammer_used":     hammer_used,
        "consolation":     consolation,
        "speed_bonus_pct": speed_bonus_pct,
        "coins":           xp_snap.get("coins", 0),
        "crystals":        xp_snap.get("crystals", 0),
        "diamonds":        xp_snap.get("diamonds", 0),
    }

    if cave_in:
        if consolation:
            cons_label = consolation["resource"].title()
            cons_emoji = "💠" if consolation["resource"] == "diamonds" else "💎"
            result["message"] = (
                f"💥 Cave-in! But you found hidden treasure — "
                f"{cons_emoji} {consolation['amount']} {cons_label}!"
            )
        else:
            result["message"] = "💥 Cave-in! Nothing salvaged — better luck next time."
    else:
        bonus_str = f" (+{speed_bonus_pct}% speed bonus)" if speed_bonus_pct else ""
        hammer_str = " 🔨×1.5" if hammer_used else ""
        result["message"] = f"Mine complete! You earned {final_yield} {resource.title()}{bonus_str}{hammer_str}!"

    return result


def get_recent_mines(child_key: str, limit: int = 5) -> list:
    mines = load_mines()
    child_mines = [m for m in mines if m.get("child") == child_key]
    return list(reversed(child_mines[-limit:]))


# ── Redemptions ───────────────────────────────────────────────────────────────

def load_redemptions() -> list:
    data = _load(REDEMPTIONS_FILE, [])
    return data if isinstance(data, list) else []


def save_redemptions(redemptions: list):
    _save(REDEMPTIONS_FILE, redemptions)


def create_redemption(child_key: str, reward_id: str,
                      reward_label: str, coin_price: int) -> dict:
    r = {
        "id":           str(uuid.uuid4())[:8],
        "child":        child_key,
        "reward_id":    reward_id,
        "reward_label": reward_label,
        "coin_price":   coin_price,
        "status":       "pending",
        "created_at":   date.today().isoformat(),
    }
    redemptions = load_redemptions()
    redemptions.append(r)
    save_redemptions(redemptions)
    return r


def approve_redemption(redemption_id: str) -> dict:
    redemptions = load_redemptions()
    r = next((x for x in redemptions if x.get("id") == redemption_id), None)
    if not r:
        return {"error": "not_found"}
    if r.get("status") != "pending":
        return {"error": "already_resolved"}
    child_key  = r["child"]
    coin_price = r.get("coin_price", 0)
    if not spend_coins(child_key, coin_price, r.get("reward_label", "")):
        return {"error": "insufficient_coins"}
    r["status"] = "approved"
    save_redemptions(redemptions)
    return {"ok": True, "reward_label": r.get("reward_label", ""), "child": child_key}


def reject_redemption(redemption_id: str) -> dict:
    redemptions = load_redemptions()
    r = next((x for x in redemptions if x.get("id") == redemption_id), None)
    if not r:
        return {"error": "not_found"}
    r["status"] = "rejected"
    save_redemptions(redemptions)
    return {"ok": True}


def get_pending_redemptions() -> list:
    return [r for r in load_redemptions() if r.get("status") == "pending"]


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
        xp_data = load_xp()
        state = _xp_state(xp_data, child_key)
        state["xp_earned"] = 0
        state["streak_bonus"] = 0
        state["streak"] = get_streak(child_key)
        return state

    # Mark complete
    quest.setdefault("completions", {})[child_key] = True
    save_quests(quests)

    # Award base XP + coins (1 coin per XP point)
    xp_data = load_xp()
    child_xp = xp_data.setdefault(child_key, {"total_xp": 0, "coins": 0, "history": []})
    child_xp["total_xp"] = child_xp.get("total_xp", 0) + quest["xp_value"]
    child_xp["coins"]    = child_xp.get("coins", 0) + quest["xp_value"]
    child_xp.setdefault("coin_history", []).append({
        "type": "earned", "amount": quest["xp_value"],
        "from": quest["title"], "date": quest.get("date", today), "ts": _now_ts(),
    })
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

    # ── Check if all daily quests done → refill 3 stamina (once per day) ─────
    quests_today = get_quests_for_child(child_key, today)
    daily_quests = [q for q in quests_today if q.get("type") == "daily" and not _is_bonus_quest(q)]
    all_daily_done = daily_quests and all(is_completed(q, child_key) for q in daily_quests)
    # Only refill once per calendar day
    st_data = load_stamina()
    child_st = st_data.get(child_key, {})
    already_refilled_today = child_st.get("last_refill_date") == today
    if all_daily_done and not already_refilled_today:
        new_stamina = refill_stamina(child_key, 3)
        state["stamina_refilled"] = 3
        state["stamina"] = new_stamina
    else:
        state["stamina"] = get_stamina(child_key)

    return state


def _is_bonus_quest(q: dict) -> bool:
    return bool(q.get("is_bonus")) or "complete your entire school day" in q.get("title", "").lower()


def _try_auto_complete_bonus(child_key: str, today: str) -> int:
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
        child_xp = xp_data.setdefault(child_key, {"total_xp": 0, "coins": 0, "history": []})
        child_xp["total_xp"] = child_xp.get("total_xp", 0) + bq["xp_value"]
        child_xp["coins"]    = child_xp.get("coins", 0) + bq["xp_value"]
        child_xp.setdefault("coin_history", []).append({
            "type": "earned", "amount": bq["xp_value"],
            "from": bq["title"], "date": today, "ts": _now_ts(),
        })
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
    child = xp_data.get(child_key, {})
    total    = child.get("total_xp", 0)
    coins    = child.get("coins", 0)
    crystals = child.get("crystals", 0)
    diamonds = child.get("diamonds", 0)
    return {
        "child":        child_key,
        "total_xp":     total,
        "coins":        coins,
        "crystals":     crystals,
        "diamonds":     diamonds,
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
    last = s.get("last_date", "")
    if last:
        from datetime import date as _d, timedelta
        today = _d.today().isoformat()
        yesterday = (_d.today() - timedelta(days=1)).isoformat()
        if last < yesterday and last != today:
            s = dict(s)
            s["current"] = 0
    s.setdefault("just_hit_milestone", False)
    return s


def _update_streak_for_child(child_key: str, today_iso: str) -> dict:
    quests_today = get_quests_for_child(child_key, today_iso)
    daily_quests = [q for q in quests_today if q.get("type") == "daily"]

    if not daily_quests:
        streak = get_streak(child_key)
        streak["just_hit_milestone"] = False
        return streak

    all_done = all(q.get("completions", {}).get(child_key) for q in daily_quests)
    if not all_done:
        streak = get_streak(child_key)
        streak["just_hit_milestone"] = False
        return streak

    streaks = load_streaks()
    s = streaks.get(child_key, {"current": 0, "best": 0, "last_date": ""})

    last_date = s.get("last_date", "")
    just_hit_milestone = False

    if last_date == today_iso:
        s["just_hit_milestone"] = False
        return s

    from datetime import date as _d, timedelta
    today_d   = _d.fromisoformat(today_iso)
    yesterday = (today_d - timedelta(days=1)).isoformat()

    if last_date == yesterday:
        s["current"] = s.get("current", 0) + 1
    else:
        s["current"] = 1

    s["best"]      = max(s.get("best", 0), s["current"])
    s["last_date"] = today_iso

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


def create_reward(label: str, xp_threshold: int = 0,
                  level_threshold: int = 0, coin_price: int = 10,
                  item_reward: str = "") -> dict:
    reward = {
        "id":              str(uuid.uuid4())[:8],
        "label":           label.strip(),
        "coin_price":      max(1, int(coin_price)),
        "xp_threshold":    max(0, int(xp_threshold)),
        "level_threshold": max(0, int(level_threshold)),
    }
    if item_reward and item_reward in ITEMS:
        reward["item_reward"] = item_reward
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
    if not today_iso:
        today_iso = date.today().isoformat()

    import fq_api as _api

    from datetime import date as _d
    today_d = _d.fromisoformat(today_iso)
    weekday = today_d.strftime("%A")

    created = []
    skipped = []
    errors  = []

    for child_key in CHILDREN_KEYS:
        child_name = CHILDREN_NAMES[child_key]
        try:
            day_list = _api.get_day_list(child_name, weekday, today_iso)

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
    t = title.lower()
    if any(w in t for w in ("clean", "scrub", "mop", "vacuum", "dishes", "laundry")):
        return 15
    if any(w in t for w in ("bed", "tidy", "pick up", "sweep", "trash", "wipe")):
        return 10
    return 10


def sync_all_quests_for_child(child_name: str, iso_date: str = "") -> dict:
    if not iso_date:
        iso_date = date.today().isoformat()

    import fq_api as _api

    child_key = CHILD_NAME_TO_KEY.get(child_name)
    if not child_key:
        return {"created": [], "skipped": [], "errors": [f"Unknown child: {child_name}"]}

    today_d = date.fromisoformat(iso_date)
    weekday = today_d.strftime("%A")

    created, skipped, errors = [], [], []

    try:
        existing        = get_quests_for_child(child_key, iso_date)
        existing_titles = {q.get("title", "").strip().lower() for q in existing}

        FULL_DAY_TITLE = "Complete Your Entire School Day"
        school_quests_created = 0

        subjects = _api.get_school_tasks(child_name, weekday)
        for block in subjects:
            subj = block.get("subject", "").strip()
            assign = block.get("assignment_text", "").strip()
            if not subj:
                continue
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

        day_list = _api.get_day_list(child_name, weekday, iso_date)
        for item in day_list:
            if item.get("kind") != "chore":
                continue
            title = (item.get("label") or "").strip()
            if not title or title.lower() in existing_titles:
                skipped.append(f"{child_name}: {title}")
                continue
            q = create_quest(title, "daily", [child_key], xp_value=_chore_xp(title), iso_date=iso_date)
            _mark_synced(q["id"], from_print=True)
            created.append(f"{child_name}: {title}")
            existing_titles.add(title.lower())

        if school_quests_created > 0 and FULL_DAY_TITLE.lower() not in existing_titles:
            q = create_quest(FULL_DAY_TITLE, "daily", [child_key],
                             xp_value=50, iso_date=iso_date)
            _mark_synced(q["id"], from_print=True, is_bonus=True)
            created.append(f"{child_name}: {FULL_DAY_TITLE}")

    except Exception as exc:
        errors.append(str(exc))

    return {"created": created, "skipped": skipped, "errors": errors}


def _mark_synced(quest_id: str, from_print: bool = False, is_bonus: bool = False):
    quests = load_quests()
    for q in quests:
        if q.get("id") == quest_id:
            q["synced"]     = True
            q["from_print"] = from_print
            if is_bonus:
                q["is_bonus"] = True
            break
    save_quests(quests)
