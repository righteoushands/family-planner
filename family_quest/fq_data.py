"""
fq_data.py — Data models and engine for Family Quest (GDD v2).

JSON flat-file storage:
  family_quest/data/quests.json        — quest records
  family_quest/data/xp.json            — per-child currencies + resources
  family_quest/data/heroes.json        — hero roster + levels per child
  family_quest/data/boss_progress.json — sequential boss progression per child
  family_quest/data/fortress.json      — per-child fortress levels
  family_quest/data/equipment.json     — 4 slot levels per child
  family_quest/data/inventory.json     — single-use item counts
  family_quest/data/rewards.json       — parent-defined real-coin rewards
  family_quest/data/streaks.json       — per-child streak tracking
  family_quest/data/redemptions.json   — reward redemption records
  family_quest/data/battles.json       — recent battle records
  family_quest/data/mines.json         — active/recent mine run records
  family_quest/data/boss_settings.json — parent configuration
"""
import json
import os
import uuid
import random
from datetime import date

# ── Paths ─────────────────────────────────────────────────────────────────────
_DIR = os.path.join(os.path.dirname(__file__), "data")
QUESTS_FILE        = os.path.join(_DIR, "quests.json")
XP_FILE            = os.path.join(_DIR, "xp.json")
HEROES_FILE        = os.path.join(_DIR, "heroes.json")
BOSS_PROGRESS_FILE = os.path.join(_DIR, "boss_progress.json")
FORTRESS_FILE      = os.path.join(_DIR, "fortress.json")
REWARDS_FILE       = os.path.join(_DIR, "rewards.json")
STREAKS_FILE       = os.path.join(_DIR, "streaks.json")
REDEMPTIONS_FILE   = os.path.join(_DIR, "redemptions.json")
EQUIPMENT_FILE     = os.path.join(_DIR, "equipment.json")
INVENTORY_FILE     = os.path.join(_DIR, "inventory.json")
BATTLES_FILE       = os.path.join(_DIR, "battles.json")
MINES_FILE         = os.path.join(_DIR, "mines.json")
BOSS_SETTINGS_FILE = os.path.join(_DIR, "boss_settings.json")

# ── Children ──────────────────────────────────────────────────────────────────
CHILDREN_KEYS  = ["jp", "joseph", "michael", "james"]
CHILDREN_NAMES = {"jp": "JP", "joseph": "Joseph", "michael": "Michael", "james": "James"}
CHILD_NAME_TO_KEY = {"JP": "jp", "Joseph": "joseph", "Michael": "michael", "James": "james"}

# ── Quest types ───────────────────────────────────────────────────────────────
QUEST_TYPES = ["daily", "side", "boss", "event"]

# ── Streak milestone bonus game_coins ─────────────────────────────────────────
STREAK_MILESTONES = {3: 10, 7: 25, 14: 50, 30: 100}

# ═══════════════════════════════════════════════════════════════════════════════
# HERO DEFINITIONS (GDD v2)
# ═══════════════════════════════════════════════════════════════════════════════
HEROES = {
    "link": {
        "name":        "Link",
        "emoji":       "🗡️",
        "description": "Hero of Hyrule. Skyward Sword form attacks 3 times per turn.",
        "unlock_boss":  0,  # 0 = starter hero, unlocked for all
        "forms": {
            1: {
                "label":       "Skyward Sword Link",
                "emoji":       "🗡️",
                "hits_per_turn": 3,
                "base_hp":     100,
                "hp_per_level": 10,
                "base_def":    55,
                "def_per_level": 5,
                "base_dmg":    250,
                "dmg_per_level": 20,
                "evolve_at":   50,
            },
            2: {
                "label":         "Tears of the Kingdom Link",
                "emoji":         "⚔️",
                "hits_per_turn": 9,
                "stat_bonus":    500,  # one-time boost on evolution
                "base_hp":     100,    # same base, +500 bonus applied on top at evolution
                "hp_per_level": 10,
                "base_def":    55,
                "def_per_level": 5,
                "base_dmg":    250,
                "dmg_per_level": 20,
            },
        },
        "evolution_cost": {
            "copper":     30,
            "game_coins": 80,
            "crystals":   30,
            "diamonds":   15,
            "iron":       60,
        },
    },
    "zelda": {
        "name":        "Zelda",
        "emoji":       "👑",
        "description": "Princess of Hyrule. Powerful magic — 2 hits but bonus XP per win.",
        "unlock_boss":  5,
        "forms": {
            1: {
                "label":       "Princess Zelda",
                "emoji":       "👑",
                "hits_per_turn": 2,
                "base_hp":     120,
                "hp_per_level": 12,
                "base_def":    60,
                "def_per_level": 6,
                "base_dmg":    320,
                "dmg_per_level": 25,
                "evolve_at":   None,
            },
        },
        "evolution_cost": None,
    },
    "ganondorf": {
        "name":        "Ganondorf",
        "emoji":       "😈",
        "description": "King of Evil. 5 hits per turn — overwhelming power, lower defense.",
        "unlock_boss":  15,
        "forms": {
            1: {
                "label":       "Ganondorf",
                "emoji":       "😈",
                "hits_per_turn": 5,
                "base_hp":     90,
                "hp_per_level": 8,
                "base_def":    40,
                "def_per_level": 3,
                "base_dmg":    300,
                "dmg_per_level": 30,
                "evolve_at":   None,
            },
        },
        "evolution_cost": None,
    },
    "samus": {
        "name":        "Samus",
        "emoji":       "🚀",
        "description": "Bounty Hunter. 4 hits. Earns extra crystals and diamonds from mines.",
        "unlock_boss":  25,
        "forms": {
            1: {
                "label":       "Samus Aran",
                "emoji":       "🚀",
                "hits_per_turn": 4,
                "base_hp":     150,
                "hp_per_level": 15,
                "base_def":    70,
                "def_per_level": 7,
                "base_dmg":    280,
                "dmg_per_level": 22,
                "evolve_at":   None,
            },
        },
        "evolution_cost": None,
    },
    "mario": {
        "name":        "Mario",
        "emoji":       "🍄",
        "description": "Super Mario. 4 hits. Earns bonus real coins from chores.",
        "unlock_boss":  40,
        "forms": {
            1: {
                "label":       "Super Mario",
                "emoji":       "🍄",
                "hits_per_turn": 4,
                "base_hp":     110,
                "hp_per_level": 11,
                "base_def":    50,
                "def_per_level": 5,
                "base_dmg":    270,
                "dmg_per_level": 22,
                "evolve_at":   None,
            },
        },
        "evolution_cost": None,
    },
    "fox": {
        "name":        "Fox McCloud",
        "emoji":       "🦊",
        "description": "Star Fox. 6 hits per turn. Big Boss specialist.",
        "unlock_boss":  60,
        "forms": {
            1: {
                "label":       "Fox McCloud",
                "emoji":       "🦊",
                "hits_per_turn": 6,
                "base_hp":     100,
                "hp_per_level": 10,
                "base_def":    45,
                "def_per_level": 4,
                "base_dmg":    260,
                "dmg_per_level": 20,
                "evolve_at":   None,
            },
        },
        "evolution_cost": None,
    },
}

DEFAULT_HERO = "link"

# Hero XP thresholds for leveling
HERO_LEVEL_XP = [0, 500, 1200, 2200, 3500, 5500, 8000, 11500, 16000, 22000, 30000]
# L1=0, L2=500, L3=1200, L4=2200, L5=3500, L6=5500, L7=8000, L8=11500, L9=16000, L10=22000, L11+...
MAX_HERO_LEVEL = 50  # Link can reach level 50 for Form 2


# ═══════════════════════════════════════════════════════════════════════════════
# BOSS PROGRESSION (GDD v2)
# ═══════════════════════════════════════════════════════════════════════════════

def boss_hp(boss_num: int) -> int:
    """HP for boss number N. Boss 1=500, each +500 per boss."""
    return boss_num * 500


def boss_rewards(boss_num: int) -> dict:
    """Rewards for defeating boss N. Scales with boss number."""
    return {
        "game_coins": boss_num * 10,
        "real_coins": boss_num * 10,
        "hero_xp":    boss_num * 50,
    }


BIG_BOSS_TABLE = [
    {
        "id": "bb1", "name": "Shadow Ganon",   "emoji": "👻",
        "hp": 50000, "game_coins": 500, "real_coins": 500, "hero_xp": 2500,
        "unlock_hero": None,
        "description": "The shadow of Ganon — a massive spectral beast.",
    },
    {
        "id": "bb2", "name": "Malice Titan",   "emoji": "🌑",
        "hp": 100000, "game_coins": 1000, "real_coins": 1000, "hero_xp": 5000,
        "unlock_hero": "zelda",
        "description": "A creature born of pure malice. Defeating it frees Princess Zelda.",
    },
    {
        "id": "bb3", "name": "Demon Dragon",   "emoji": "🐲",
        "hp": 200000, "game_coins": 2000, "real_coins": 2000, "hero_xp": 10000,
        "unlock_hero": "ganondorf",
        "description": "The Demon Dragon — Ganondorf's ultimate form.",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# FORTRESS (GDD v2)
# ═══════════════════════════════════════════════════════════════════════════════

FORTRESS_LEVELS = {
    1:  {"label": "Wooden Fort",     "emoji": "🪵", "passive_income": 10,  "defenders": 2,  "upgrade_cost_gc": 100},
    2:  {"label": "Stone Fort",      "emoji": "🧱", "passive_income": 15,  "defenders": 4,  "upgrade_cost_gc": 200},
    3:  {"label": "Iron Fort",       "emoji": "⚙️", "passive_income": 20,  "defenders": 6,  "upgrade_cost_gc": 400},
    4:  {"label": "Steel Bastion",   "emoji": "🛡️", "passive_income": 28,  "defenders": 8,  "upgrade_cost_gc": 700},
    5:  {"label": "Crystal Citadel", "emoji": "💎", "passive_income": 38,  "defenders": 12, "upgrade_cost_gc": 1200},
    6:  {"label": "Diamond Keep",    "emoji": "💠", "passive_income": 50,  "defenders": 16, "upgrade_cost_gc": 2000},
    7:  {"label": "Mithril Tower",   "emoji": "✨", "passive_income": 63,  "defenders": 22, "upgrade_cost_gc": 3500},
    8:  {"label": "Arcane Fortress", "emoji": "🏰", "passive_income": 77,  "defenders": 30, "upgrade_cost_gc": 6000},
    9:  {"label": "Sky Citadel",     "emoji": "☁️", "passive_income": 90,  "defenders": 40, "upgrade_cost_gc": 10000},
    10: {"label": "Divine Sanctum",  "emoji": "⭐", "passive_income": 100, "defenders": 50, "upgrade_cost_gc": None},
}


# ═══════════════════════════════════════════════════════════════════════════════
# EQUIPMENT (GDD v2 — sword=crystals, shield/armor=diamonds)
# ═══════════════════════════════════════════════════════════════════════════════

EQUIPMENT_SLOTS = {
    "sword": {
        "label": "Sword",
        "emoji": "⚔️",
        "description": "Better sword = fewer chores needed per boss hit",
        "upgrade_costs": [
            {"crystals": 15},
            {"crystals": 35},
            {"crystals": 75},
            {"crystals": 150},
            {"crystals": 300},
        ],
        "max_level": 5,
    },
    "shield": {
        "label": "Shield",
        "emoji": "🛡️",
        "description": "Better shield = less penalty from boss hits",
        "upgrade_costs": [
            {"diamonds": 10},
            {"diamonds": 25},
            {"diamonds": 60},
            {"diamonds": 120},
            {"diamonds": 250},
        ],
        "max_level": 5,
    },
    "armor": {
        "label": "Armor",
        "emoji": "🧥",
        "description": "Better armor = less damage from enemy fortress attacks",
        "upgrade_costs": [
            {"diamonds": 8},
            {"diamonds": 20},
            {"diamonds": 50},
            {"diamonds": 100},
            {"diamonds": 200},
        ],
        "max_level": 5,
    },
    "other": {
        "label": "Ring",
        "emoji": "💍",
        "description": "Bonus item slot for special enchantments",
        "upgrade_costs": [
            {"crystals": 10, "diamonds": 5},
            {"crystals": 25, "diamonds": 12},
            {"crystals": 60, "diamonds": 30},
            {"crystals": 120, "diamonds": 60},
            {"crystals": 250, "diamonds": 120},
        ],
        "max_level": 5,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# MINE TYPES (GDD v2)
# ═══════════════════════════════════════════════════════════════════════════════

MINE_TYPES = {
    "gold": {
        "label":        "Gold Mine",
        "emoji":        "🪙",
        "resource":     "real_coins",
        "base_rate":    10,       # 10 real_coins/min
        "duration_min": 10,       # 10 min = 100 real_coins
        "description":  "Earn Real Coins redeemable for real money and prizes.",
    },
    "crystal": {
        "label":        "Crystal Mine",
        "emoji":        "💎",
        "resource":     "crystals",
        "base_rate":    2,        # 2 crystals/min
        "duration_min": 15,       # 15 min = 30 crystals
        "description":  "Crystals used for sword upgrades.",
    },
    "diamond": {
        "label":        "Diamond Mine",
        "emoji":        "💠",
        "resource":     "diamonds",
        "base_rate":    2,        # 2 diamonds/min
        "duration_min": 15,       # 15 min = 30 diamonds
        "description":  "Diamonds used for shield and armor upgrades.",
    },
    "copper": {
        "label":        "Copper Mine",
        "emoji":        "🟤",
        "resource":     "copper",
        "base_rate":    3,        # 3 copper/min
        "duration_min": 10,       # 10 min = 30 copper
        "description":  "Copper used for hero evolution.",
    },
    "iron": {
        "label":        "Iron Mine",
        "emoji":        "⚙️",
        "resource":     "iron",
        "base_rate":    2,        # 2 iron/min
        "duration_min": 15,       # 15 min = 30 iron
        "description":  "Iron used for hero evolution.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE-USE ITEMS
# ═══════════════════════════════════════════════════════════════════════════════

ITEMS = {
    "battle_axe": {
        "label":       "Battle Axe",
        "emoji":       "🪓",
        "description": "Equip before a boss fight for bonus damage. Breaks after one use.",
        "use_in":      "boss",
    },
    "hammer": {
        "label":       "Hammer",
        "emoji":       "🔨",
        "description": "Equip before any mine run for 1.5× rewards. Breaks after one use.",
        "use_in":      "mine",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# I/O HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

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


def _now_ts() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


# ═══════════════════════════════════════════════════════════════════════════════
# QUESTS
# ═══════════════════════════════════════════════════════════════════════════════

def load_quests() -> list:
    data = _load(QUESTS_FILE, [])
    return data if isinstance(data, list) else []


def save_quests(quests: list):
    _save(QUESTS_FILE, quests)


def get_quests_for_child(child_key: str, iso_date: str = "") -> list:
    if not iso_date:
        iso_date = date.today().isoformat()
    return [
        q for q in load_quests()
        if child_key in q.get("assigned_to", [])
        and q.get("date") == iso_date
        and q.get("active", True)
    ]


def create_quest(title: str, quest_type: str, assigned_to: list,
                 xp_value: int = 5,           # kept for compatibility
                 energy_value: int = 1,
                 real_coin_value: int = 1,
                 game_coin_value: int = 2,
                 iso_date: str = "") -> dict:
    if not iso_date:
        iso_date = date.today().isoformat()
    quest = {
        "id":               str(uuid.uuid4())[:8],
        "title":            title.strip(),
        "type":             quest_type if quest_type in QUEST_TYPES else "daily",
        "assigned_to":      [c for c in assigned_to if c in CHILDREN_KEYS],
        "xp_value":         max(1, int(xp_value)),
        "energy_value":     max(0, int(energy_value)),
        "real_coin_value":  max(0, int(real_coin_value)),
        "game_coin_value":  max(0, int(game_coin_value)),
        "date":             iso_date,
        "active":           True,
        "completions":      {},
        "synced":           False,
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


# ═══════════════════════════════════════════════════════════════════════════════
# CURRENCIES & RESOURCES (GDD v2)
# Three currency tracks: real_coins, game_coins, energy
# Four resources: crystals, diamonds, copper, iron
# ═══════════════════════════════════════════════════════════════════════════════

_CURRENCY_FIELDS  = ["real_coins", "game_coins", "energy"]
_RESOURCE_FIELDS  = ["crystals", "diamonds", "copper", "iron"]
_ALL_XP_FIELDS    = _CURRENCY_FIELDS + _RESOURCE_FIELDS


def load_xp() -> dict:
    data = _load(XP_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for key in CHILDREN_KEYS:
        data.setdefault(key, {})
        child = data[key]
        # Migrate legacy "coins" field to real_coins+game_coins if present
        if "coins" in child and "real_coins" not in child:
            old = child.pop("coins", 0)
            child["real_coins"]  = old
            child["game_coins"]  = old
        # Ensure all v2 fields exist
        for f in _ALL_XP_FIELDS:
            child.setdefault(f, 0)
        child.setdefault("history", [])
    return data


def save_xp(xp_data: dict):
    _save(XP_FILE, xp_data)


def get_child_state(child_key: str) -> dict:
    """Return all currency/resource balances for a child."""
    xp = load_xp()
    child = xp.get(child_key, {})
    return {f: child.get(f, 0) for f in _ALL_XP_FIELDS}


def award_currency(child_key: str, field: str, amount: int, label: str = "", iso: str = "") -> int:
    """Award real_coins, game_coins, energy, or any resource. Returns new balance."""
    if field not in _ALL_XP_FIELDS or amount <= 0:
        return load_xp().get(child_key, {}).get(field, 0)
    xp = load_xp()
    child = xp.setdefault(child_key, {f: 0 for f in _ALL_XP_FIELDS})
    for f in _ALL_XP_FIELDS:
        child.setdefault(f, 0)
    child[field] += amount
    child.setdefault("history", []).append({
        "type": "earned", "field": field, "amount": amount,
        "from": label, "date": iso or date.today().isoformat(), "ts": _now_ts(),
    })
    save_xp(xp)
    return child[field]


def spend_currency(child_key: str, field: str, amount: int, label: str = "") -> bool:
    """Spend real_coins, game_coins, energy, or any resource. Returns True if ok."""
    if field not in _ALL_XP_FIELDS:
        return False
    xp = load_xp()
    child = xp.setdefault(child_key, {f: 0 for f in _ALL_XP_FIELDS})
    for f in _ALL_XP_FIELDS:
        child.setdefault(f, 0)
    if child[field] < amount:
        return False
    child[field] -= amount
    child.setdefault("history", []).append({
        "type": "spent", "field": field, "amount": -amount,
        "from": label, "date": date.today().isoformat(), "ts": _now_ts(),
    })
    save_xp(xp)
    return True


# Legacy shims so existing call sites still work
def get_coins(child_key: str) -> int:
    return load_xp().get(child_key, {}).get("real_coins", 0)


def get_game_coins(child_key: str) -> int:
    return load_xp().get(child_key, {}).get("game_coins", 0)


def get_energy(child_key: str) -> int:
    return load_xp().get(child_key, {}).get("energy", 0)


def get_crystals(child_key: str) -> int:
    return load_xp().get(child_key, {}).get("crystals", 0)


def get_diamonds(child_key: str) -> int:
    return load_xp().get(child_key, {}).get("diamonds", 0)


def get_copper(child_key: str) -> int:
    return load_xp().get(child_key, {}).get("copper", 0)


def get_iron(child_key: str) -> int:
    return load_xp().get(child_key, {}).get("iron", 0)


def award_resource(child_key: str, resource: str, amount: int, label: str = "") -> int:
    """Generic award helper used by mine engine."""
    return award_currency(child_key, resource, amount, label)


def spend_resource(child_key: str, resource: str, amount: int, label: str = "") -> bool:
    return spend_currency(child_key, resource, amount, label)


# ═══════════════════════════════════════════════════════════════════════════════
# HEROES (GDD v2)
# ═══════════════════════════════════════════════════════════════════════════════

def load_heroes() -> dict:
    data = _load(HEROES_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for key in CHILDREN_KEYS:
        data.setdefault(key, {
            "active": DEFAULT_HERO,
            "roster": {DEFAULT_HERO: {"level": 1, "xp": 0, "form": 1}},
        })
        child = data[key]
        child.setdefault("active", DEFAULT_HERO)
        child.setdefault("roster", {})
        # Ensure link is always in roster
        child["roster"].setdefault(DEFAULT_HERO, {"level": 1, "xp": 0, "form": 1})
    return data


def save_heroes(heroes: dict):
    _save(HEROES_FILE, heroes)


def get_hero_roster(child_key: str) -> dict:
    return load_heroes().get(child_key, {})


def get_active_hero_key(child_key: str) -> str:
    return load_heroes().get(child_key, {}).get("active", DEFAULT_HERO)


def get_active_hero(child_key: str) -> dict:
    heroes = load_heroes()
    child = heroes.get(child_key, {})
    hero_key = child.get("active", DEFAULT_HERO)
    if hero_key not in HEROES:
        hero_key = DEFAULT_HERO
    hero_def   = HEROES[hero_key]
    hero_state = child.get("roster", {}).get(hero_key, {"level": 1, "xp": 0, "form": 1})
    level      = hero_state.get("level", 1)
    form       = hero_state.get("form", 1)
    if form not in hero_def["forms"]:
        form = 1
    form_def = hero_def["forms"][form]
    return {
        "key":         hero_key,
        "name":        hero_def["name"],
        "emoji":       form_def["emoji"],
        "form":        form,
        "form_label":  form_def["label"],
        "level":       level,
        "xp":          hero_state.get("xp", 0),
        "hits_per_turn": form_def["hits_per_turn"],
        "hp":          _hero_hp(form_def, level, form),
        "defense":     _hero_def(form_def, level, form),
        "damage":      _hero_dmg(form_def, level, form),
        "can_evolve":  _can_evolve(hero_key, level, form),
        "evolution_cost": hero_def.get("evolution_cost"),
        "xp_to_next":  _hero_xp_to_next(level),
    }


def _hero_bonus(form_def: dict, form: int) -> int:
    """One-time stat bonus applied when form == 2."""
    return form_def.get("stat_bonus", 0) if form >= 2 else 0


def _hero_hp(form_def: dict, level: int, form: int) -> int:
    bonus = _hero_bonus(form_def, form)
    return form_def["base_hp"] + form_def["hp_per_level"] * (level - 1) + bonus


def _hero_def(form_def: dict, level: int, form: int) -> int:
    bonus = _hero_bonus(form_def, form)
    return form_def["base_def"] + form_def["def_per_level"] * (level - 1) + bonus


def _hero_dmg(form_def: dict, level: int, form: int) -> int:
    bonus = _hero_bonus(form_def, form)
    return form_def["base_dmg"] + form_def["dmg_per_level"] * (level - 1) + bonus


def _can_evolve(hero_key: str, level: int, form: int) -> bool:
    hero_def = HEROES.get(hero_key, {})
    form1_def = hero_def.get("forms", {}).get(1, {})
    evolve_at = form1_def.get("evolve_at")
    return evolve_at is not None and form == 1 and level >= evolve_at


def _hero_xp_to_next(level: int) -> int | None:
    thresholds = HERO_LEVEL_XP
    if level >= len(thresholds):
        # Above defined table — linear extrapolation
        gap = thresholds[-1] - thresholds[-2] if len(thresholds) >= 2 else 10000
        return gap
    cur_min = thresholds[level - 1] if level <= len(thresholds) else thresholds[-1]
    nxt_min = thresholds[level]     if level < len(thresholds)  else None
    if nxt_min is None:
        return None
    return nxt_min - cur_min


def award_hero_xp(child_key: str, amount: int, hero_key: str = None) -> dict:
    """Award XP to the active (or specified) hero. Returns level-up info."""
    heroes = load_heroes()
    child = heroes.setdefault(child_key, {
        "active": DEFAULT_HERO,
        "roster": {DEFAULT_HERO: {"level": 1, "xp": 0, "form": 1}},
    })
    if hero_key is None:
        hero_key = child.get("active", DEFAULT_HERO)
    if hero_key not in HEROES:
        hero_key = DEFAULT_HERO
    child["roster"].setdefault(hero_key, {"level": 1, "xp": 0, "form": 1})
    state     = child["roster"][hero_key]
    old_level = state["level"]
    state["xp"] = state.get("xp", 0) + amount

    # Level up loop
    leveled_up = False
    while True:
        xp_needed = _hero_xp_to_next(state["level"])
        if xp_needed is None or state["xp"] < xp_needed:
            break
        state["xp"]   -= xp_needed
        state["level"] = min(MAX_HERO_LEVEL, state["level"] + 1)
        leveled_up = True

    save_heroes(heroes)
    return {
        "hero_key":   hero_key,
        "new_level":  state["level"],
        "old_level":  old_level,
        "leveled_up": leveled_up,
        "xp":         state["xp"],
    }


def unlock_hero(child_key: str, hero_key: str) -> bool:
    if hero_key not in HEROES:
        return False
    heroes = load_heroes()
    child = heroes.setdefault(child_key, {
        "active": DEFAULT_HERO,
        "roster": {DEFAULT_HERO: {"level": 1, "xp": 0, "form": 1}},
    })
    if hero_key not in child["roster"]:
        child["roster"][hero_key] = {"level": 1, "xp": 0, "form": 1}
    save_heroes(heroes)
    return True


def set_active_hero(child_key: str, hero_key: str) -> bool:
    heroes = load_heroes()
    child = heroes.get(child_key, {})
    if hero_key not in child.get("roster", {}):
        return False
    child["active"] = hero_key
    save_heroes(heroes)
    return True


def evolve_hero(child_key: str, hero_key: str = None) -> dict:
    """Attempt hero evolution. Deducts resources. Returns result dict."""
    heroes = load_heroes()
    child = heroes.setdefault(child_key, {
        "active": DEFAULT_HERO,
        "roster": {DEFAULT_HERO: {"level": 1, "xp": 0, "form": 1}},
    })
    if hero_key is None:
        hero_key = child.get("active", DEFAULT_HERO)
    state = child["roster"].get(hero_key)
    if not state:
        return {"error": "Hero not in roster"}
    if not _can_evolve(hero_key, state["level"], state.get("form", 1)):
        return {"error": "Hero cannot evolve yet (must be level 50, form 1)"}
    hero_def = HEROES[hero_key]
    cost = hero_def.get("evolution_cost")
    if not cost:
        return {"error": "This hero has no evolution"}
    # Check resources
    xp = load_xp().get(child_key, {})
    for field, needed in cost.items():
        if xp.get(field, 0) < needed:
            label = field.replace("_", " ").title()
            return {"error": f"Need {needed} {label} (have {xp.get(field, 0)})"}
    # Deduct
    for field, needed in cost.items():
        spend_currency(child_key, field, needed, f"Evolve {hero_def['name']}")
    state["form"] = 2
    save_heroes(heroes)
    return {"ok": True, "hero": hero_key, "new_form": 2}


def get_unlockable_heroes(child_key: str, total_bosses_defeated: int) -> list:
    """Return list of hero keys the child has just unlocked."""
    heroes = load_heroes()
    child = heroes.get(child_key, {})
    roster = child.get("roster", {})
    unlocked = []
    for hkey, hdef in HEROES.items():
        needed = hdef.get("unlock_boss", 999)
        if needed > 0 and total_bosses_defeated >= needed and hkey not in roster:
            unlock_hero(child_key, hkey)
            unlocked.append(hkey)
    return unlocked


# ═══════════════════════════════════════════════════════════════════════════════
# BOSS PROGRESSION (GDD v2)
# ═══════════════════════════════════════════════════════════════════════════════

def load_boss_progress() -> dict:
    data = _load(BOSS_PROGRESS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for key in CHILDREN_KEYS:
        data.setdefault(key, {
            "current_boss_num": 1,
            "current_hp_remaining": boss_hp(1),
            "total_defeated": 0,
            "history": [],
            "big_boss_progress": {bb["id"]: bb["hp"] for bb in BIG_BOSS_TABLE},
        })
    return data


def save_boss_progress(bp: dict):
    _save(BOSS_PROGRESS_FILE, bp)


def get_boss_state(child_key: str) -> dict:
    bp = load_boss_progress()
    child = bp.get(child_key, {})
    num = child.get("current_boss_num", 1)
    hp_total = boss_hp(num)
    hp_rem   = child.get("current_hp_remaining", hp_total)
    rewards  = boss_rewards(num)
    return {
        "boss_num":         num,
        "boss_hp_total":    hp_total,
        "boss_hp_remaining": hp_rem,
        "boss_pct":         max(0, int(hp_rem * 100 / hp_total)) if hp_total else 0,
        "rewards":          rewards,
        "total_defeated":   child.get("total_defeated", 0),
    }


def attack_boss(child_key: str, use_battle_axe: bool = False) -> dict:
    """
    Spend 1 energy per swing to attack the current boss.
    Link Form 1 = 3 swings/turn = 3 energy. Form 2 = 9 swings/turn = 9 energy.
    Battle Axe = double damage for this attack.
    Returns result with damage dealt, possible boss defeat, rewards.
    """
    hero = get_active_hero(child_key)
    energy = get_energy(child_key)
    hits   = hero["hits_per_turn"]
    energy_cost = hits  # 1 energy per swing

    if energy < energy_cost:
        return {"error": f"Not enough energy (need {energy_cost}, have {energy})"}

    # Check boss settings availability
    settings = load_boss_settings()
    if not settings.get("available", True):
        return {"error": "Boss area is closed right now. Check back later!"}

    # Battle Axe — bonus damage
    axe_used = False
    if use_battle_axe and get_inventory(child_key).get("battle_axe", 0) > 0:
        consume_item(child_key, "battle_axe")
        axe_used = True

    damage_per_hit = hero["damage"]
    if axe_used:
        damage_per_hit = int(damage_per_hit * 1.5)

    total_damage = hits * damage_per_hit

    # Spend energy
    spend_currency(child_key, "energy", energy_cost, f"Boss {get_boss_state(child_key)['boss_num']} attack")

    # Apply damage
    bp = load_boss_progress()
    child = bp.setdefault(child_key, {
        "current_boss_num": 1,
        "current_hp_remaining": boss_hp(1),
        "total_defeated": 0,
        "history": [],
        "big_boss_progress": {bb["id"]: bb["hp"] for bb in BIG_BOSS_TABLE},
    })
    num    = child.get("current_boss_num", 1)
    hp_rem = child.get("current_hp_remaining", boss_hp(num))
    hp_rem = max(0, hp_rem - total_damage)
    child["current_hp_remaining"] = hp_rem

    boss_defeated = (hp_rem <= 0)
    rewards_earned = {}
    level_up_info  = None
    new_heroes     = []

    if boss_defeated:
        rewards = boss_rewards(num)
        child["total_defeated"] = child.get("total_defeated", 0) + 1
        child["history"].append({
            "boss_num": num, "date": date.today().isoformat(), "ts": _now_ts()
        })
        if len(child["history"]) > 100:
            child["history"] = child["history"][-100:]

        # Advance to next boss
        child["current_boss_num"] = num + 1
        child["current_hp_remaining"] = boss_hp(num + 1)

        # Award currencies
        award_currency(child_key, "game_coins", rewards["game_coins"], f"Boss {num} victory")
        award_currency(child_key, "real_coins", rewards["real_coins"], f"Boss {num} victory")
        rewards_earned = rewards

        # Award hero XP
        level_up_info = award_hero_xp(child_key, rewards["hero_xp"])

        # Unlock heroes if thresholds reached
        total_d = child["total_defeated"]
        new_heroes = get_unlockable_heroes(child_key, total_d)

    save_boss_progress(bp)

    return {
        "ok":            True,
        "hits":          hits,
        "damage":        total_damage,
        "axe_used":      axe_used,
        "energy_spent":  energy_cost,
        "boss_num":      num,
        "hp_remaining":  hp_rem,
        "boss_defeated": boss_defeated,
        "rewards":       rewards_earned,
        "level_up":      level_up_info,
        "new_heroes":    new_heroes,
    }


def attack_big_boss(child_key: str, big_boss_id: str, use_battle_axe: bool = False) -> dict:
    """Attack a Big Boss. Costs same energy as regular boss attack."""
    bb_def = next((b for b in BIG_BOSS_TABLE if b["id"] == big_boss_id), None)
    if not bb_def:
        return {"error": "Big Boss not found"}

    hero = get_active_hero(child_key)
    hits = hero["hits_per_turn"]
    energy_cost = hits
    energy = get_energy(child_key)

    if energy < energy_cost:
        return {"error": f"Not enough energy (need {energy_cost}, have {energy})"}

    axe_used = False
    if use_battle_axe and get_inventory(child_key).get("battle_axe", 0) > 0:
        consume_item(child_key, "battle_axe")
        axe_used = True

    dmg = hero["damage"] * hits
    if axe_used:
        dmg = int(dmg * 1.5)

    spend_currency(child_key, "energy", energy_cost, f"Big Boss {bb_def['name']}")

    bp = load_boss_progress()
    child = bp.setdefault(child_key, {
        "current_boss_num": 1, "current_hp_remaining": boss_hp(1),
        "total_defeated": 0, "history": [],
        "big_boss_progress": {b["id"]: b["hp"] for b in BIG_BOSS_TABLE},
    })
    child.setdefault("big_boss_progress", {bb["id"]: bb["hp"] for bb in BIG_BOSS_TABLE})
    child["big_boss_progress"].setdefault(big_boss_id, bb_def["hp"])

    hp_rem = max(0, child["big_boss_progress"][big_boss_id] - dmg)
    child["big_boss_progress"][big_boss_id] = hp_rem

    boss_defeated = (hp_rem <= 0)
    rewards_earned = {}
    new_heroes = []
    level_up_info = None

    if boss_defeated:
        child["big_boss_progress"][big_boss_id] = 0  # stays at 0 (permanently defeated)
        award_currency(child_key, "game_coins", bb_def["game_coins"], f"Big Boss {bb_def['name']}")
        award_currency(child_key, "real_coins", bb_def["real_coins"], f"Big Boss {bb_def['name']}")
        rewards_earned = {
            "game_coins": bb_def["game_coins"],
            "real_coins": bb_def["real_coins"],
            "hero_xp":    bb_def["hero_xp"],
        }
        level_up_info = award_hero_xp(child_key, bb_def["hero_xp"])
        if bb_def.get("unlock_hero"):
            unlock_hero(child_key, bb_def["unlock_hero"])
            new_heroes = [bb_def["unlock_hero"]]

    save_boss_progress(bp)

    return {
        "ok":            True,
        "hits":          hits,
        "damage":        dmg,
        "axe_used":      axe_used,
        "energy_spent":  energy_cost,
        "big_boss_id":   big_boss_id,
        "big_boss_name": bb_def["name"],
        "hp_remaining":  hp_rem,
        "hp_total":      bb_def["hp"],
        "boss_defeated": boss_defeated,
        "rewards":       rewards_earned,
        "level_up":      level_up_info,
        "new_heroes":    new_heroes,
    }


def get_big_boss_states(child_key: str) -> list:
    bp = load_boss_progress()
    child = bp.get(child_key, {})
    bb_progress = child.get("big_boss_progress", {bb["id"]: bb["hp"] for bb in BIG_BOSS_TABLE})
    result = []
    for bb in BIG_BOSS_TABLE:
        hp_rem = bb_progress.get(bb["id"], bb["hp"])
        defeated = (hp_rem <= 0)
        result.append({
            **bb,
            "hp_remaining": hp_rem,
            "hp_pct":       max(0, int(hp_rem * 100 / bb["hp"])) if bb["hp"] else 0,
            "defeated":     defeated,
        })
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# FORTRESS (GDD v2)
# ═══════════════════════════════════════════════════════════════════════════════

def load_fortress() -> dict:
    data = _load(FORTRESS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for key in CHILDREN_KEYS:
        data.setdefault(key, {"level": 1, "last_passive_date": ""})
    return data


def save_fortress(ft: dict):
    _save(FORTRESS_FILE, ft)


def get_fortress_state(child_key: str) -> dict:
    ft = load_fortress()
    child = ft.get(child_key, {"level": 1, "last_passive_date": ""})
    level = child.get("level", 1)
    lvl_def = FORTRESS_LEVELS.get(level, FORTRESS_LEVELS[1])
    next_lvl_def = FORTRESS_LEVELS.get(level + 1)
    return {
        "level":          level,
        "label":          lvl_def["label"],
        "emoji":          lvl_def["emoji"],
        "passive_income": lvl_def["passive_income"],
        "defenders":      lvl_def["defenders"],
        "upgrade_cost":   lvl_def.get("upgrade_cost_gc"),
        "next_label":     next_lvl_def["label"] if next_lvl_def else None,
        "max_level":      level >= max(FORTRESS_LEVELS.keys()),
    }


def collect_fortress_income(child_key: str) -> dict:
    """Collect daily passive game_coin income from fortress. Once per day."""
    ft = load_fortress()
    child = ft.setdefault(child_key, {"level": 1, "last_passive_date": ""})
    today = date.today().isoformat()
    last  = child.get("last_passive_date", "")
    if last == today:
        return {"ok": False, "message": "Already collected today"}
    level = child.get("level", 1)
    income = FORTRESS_LEVELS.get(level, FORTRESS_LEVELS[1])["passive_income"]
    award_currency(child_key, "game_coins", income, "Fortress passive income")
    child["last_passive_date"] = today
    save_fortress(ft)
    return {"ok": True, "game_coins": income, "level": level}


def upgrade_fortress(child_key: str) -> dict:
    """Upgrade fortress by 1 level. Costs game_coins."""
    ft = load_fortress()
    child = ft.setdefault(child_key, {"level": 1, "last_passive_date": ""})
    level = child.get("level", 1)
    if level >= max(FORTRESS_LEVELS.keys()):
        return {"error": "Fortress is already at max level!"}
    cost = FORTRESS_LEVELS[level]["upgrade_cost_gc"]
    gc = get_game_coins(child_key)
    if gc < cost:
        return {"error": f"Need {cost} Game Coins (have {gc})"}
    spend_currency(child_key, "game_coins", cost, f"Fortress upgrade to level {level+1}")
    child["level"] = level + 1
    save_fortress(ft)
    new_def = FORTRESS_LEVELS[level + 1]
    return {"ok": True, "new_level": level + 1, "new_label": new_def["label"]}


# ═══════════════════════════════════════════════════════════════════════════════
# EQUIPMENT
# ═══════════════════════════════════════════════════════════════════════════════

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
    for slot in EQUIPMENT_SLOTS:
        child_eq.setdefault(slot, 0)
    return child_eq


def upgrade_equipment(child_key: str, slot_key: str) -> dict:
    if slot_key not in EQUIPMENT_SLOTS:
        return {"error": "Invalid slot"}
    slot_def = EQUIPMENT_SLOTS[slot_key]
    eq = load_equipment()
    child_eq = eq.setdefault(child_key, {s: 0 for s in EQUIPMENT_SLOTS})
    current_level = child_eq.get(slot_key, 0)
    if current_level >= slot_def["max_level"]:
        return {"error": "Already at max level"}
    cost = slot_def["upgrade_costs"][current_level]
    xp   = load_xp().get(child_key, {})
    for resource, needed in cost.items():
        if xp.get(resource, 0) < needed:
            label = resource.title()
            return {"error": f"Need {needed} {label} (have {xp.get(resource, 0)})"}
    label = f"Upgrade {slot_def['label']} to level {current_level + 1}"
    for resource, needed in cost.items():
        spend_resource(child_key, resource, needed, label)
    eq = load_equipment()
    eq.setdefault(child_key, {s: 0 for s in EQUIPMENT_SLOTS})
    eq[child_key][slot_key] = current_level + 1
    save_equipment(eq)
    return {"ok": True, "new_level": current_level + 1, "slot": slot_key}


# ═══════════════════════════════════════════════════════════════════════════════
# INVENTORY (single-use items)
# ═══════════════════════════════════════════════════════════════════════════════

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
    inv = load_inventory()
    inv.setdefault(child_key, {item: 0 for item in ITEMS})
    current = inv[child_key].get(item_key, 0)
    if current <= 0:
        return False
    inv[child_key][item_key] = current - 1
    save_inventory(inv)
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# MINE RUN ENGINE (GDD v2)
# ═══════════════════════════════════════════════════════════════════════════════

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
    """Start a mine run. Requires at least 1 completed quest today."""
    if mine_type not in MINE_TYPES:
        return {"error": "Invalid mine type"}
    if get_active_mine(child_key):
        return {"error": "You already have an active mine run! Collect it first."}

    today = date.today().isoformat()
    quests = get_quests_for_child(child_key, today)
    completed_today = sum(1 for q in quests if is_completed(q, child_key))
    if completed_today == 0:
        return {"error": "Complete at least one quest before starting a mine run!"}

    mine_def = MINE_TYPES[mine_type]

    hammer_used = False
    if use_hammer and get_inventory(child_key).get("hammer", 0) > 0:
        consume_item(child_key, "hammer")
        hammer_used = True

    from datetime import datetime
    start_ts = datetime.now().timestamp()
    mine_id  = str(uuid.uuid4())[:8]
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
        "date":             today,
        "ts":               _now_ts(),
    }
    mines = load_mines()
    mines.append(run)
    save_mines(mines)
    return run


def collect_mine_run(child_key: str, mine_id: str) -> dict:
    """Resolve a mine run and award resources (GDD v2 cave-in rules)."""
    mines = load_mines()
    run = next((m for m in mines if m.get("id") == mine_id and m.get("child") == child_key), None)
    if not run:
        return {"error": "Mine run not found"}
    if run.get("status") != "active":
        return {"error": "Mine already collected"}

    from datetime import datetime
    now_ts       = datetime.now().timestamp()
    start_ts     = run.get("start_ts", now_ts)
    elapsed_min  = (now_ts - start_ts) / 60.0

    duration_min = run.get("duration_min", 10)
    base_rate    = run.get("base_rate", 1)
    resource     = run.get("resource", "real_coins")
    hammer_used  = run.get("hammer_used", False)
    mine_type    = run.get("mine_type", "gold")

    cave_in      = False
    consolation  = None
    final_yield  = 0
    speed_bonus_pct = 0

    # GDD v2 cave-in: took too long (> 2× target for gold, > 3× for crystal/diamond)
    cave_multiplier = 2.0 if mine_type == "gold" else 3.0

    if elapsed_min >= duration_min * cave_multiplier:
        # Cave-in! Consolation loot per GDD:
        # 50% → 5 diamonds or crystals
        # 25% → 20 diamonds or crystals
        # 5%  → 100 diamonds or crystals
        # Remainder → nothing
        cave_in = True
        roll = random.random()
        res = random.choice(["crystals", "diamonds"])
        if roll < 0.05:
            consolation = {"resource": res, "amount": 100}
        elif roll < 0.30:
            consolation = {"resource": res, "amount": 20}
        elif roll < 0.80:
            consolation = {"resource": res, "amount": 5}
    elif elapsed_min >= duration_min:
        # Collected in time — full yield
        # GDD v2 Gold Mine: "finishing chores faster increases rate"
        # Speed bonus based on how fast above target
        base_yield = int(base_rate * min(elapsed_min, duration_min))
        final_yield = base_yield
        ratio = elapsed_min / duration_min
        if ratio <= 1.1:
            speed_bonus_pct = 50
        elif ratio <= 1.25:
            speed_bonus_pct = 25
        elif ratio <= 1.5:
            speed_bonus_pct = 10
        if speed_bonus_pct:
            final_yield = int(final_yield * (1 + speed_bonus_pct / 100))
    else:
        # Collected early — proportional yield with speed bonus
        base_yield = int(base_rate * elapsed_min)
        final_yield = max(1, base_yield)
        early_pct = elapsed_min / duration_min
        if early_pct >= 0.75:
            speed_bonus_pct = 20
        elif early_pct >= 0.5:
            speed_bonus_pct = 40
        elif early_pct >= 0.25:
            speed_bonus_pct = 60
        else:
            speed_bonus_pct = 80
        final_yield = int(final_yield * (1 + speed_bonus_pct / 100))

    if hammer_used and not cave_in:
        final_yield = int(final_yield * 1.5)

    # Award resources
    if cave_in:
        if consolation:
            award_resource(child_key, consolation["resource"], consolation["amount"],
                           f"{MINE_TYPES[mine_type]['label']} Consolation")
    else:
        if final_yield > 0:
            award_resource(child_key, resource, final_yield,
                           f"{MINE_TYPES[mine_type]['label']} Yield")

    run["status"]          = "complete"
    run["elapsed_min"]     = round(elapsed_min, 2)
    run["cave_in"]         = cave_in
    run["consolation"]     = consolation
    run["final_yield"]     = final_yield
    run["speed_bonus_pct"] = speed_bonus_pct
    run["collect_ts"]      = now_ts
    save_mines(mines)

    state = get_child_state(child_key)
    result = {
        "id":              mine_id,
        "mine_type":       mine_type,
        "resource":        resource,
        "cave_in":         cave_in,
        "final_yield":     final_yield,
        "elapsed_min":     round(elapsed_min, 2),
        "hammer_used":     hammer_used,
        "consolation":     consolation,
        "speed_bonus_pct": speed_bonus_pct,
        **{f: state[f] for f in _ALL_XP_FIELDS},
    }
    if cave_in:
        if consolation:
            cres = consolation["resource"]
            cemoji = "💠" if cres == "diamonds" else "💎"
            result["message"] = (
                f"💥 Cave-in! But you found hidden treasure — "
                f"{cemoji} {consolation['amount']} {cres.title()}!"
            )
        else:
            result["message"] = "💥 Cave-in! Nothing salvaged — better luck next time."
    else:
        bonus_str  = f" (+{speed_bonus_pct}% speed bonus)" if speed_bonus_pct else ""
        hammer_str = " 🔨×1.5" if hammer_used else ""
        res_emoji  = {"real_coins": "🪙", "crystals": "💎", "diamonds": "💠",
                      "copper": "🟤", "iron": "⚙️"}.get(resource, "📦")
        result["message"] = (
            f"Mine complete! You earned {res_emoji} {final_yield} "
            f"{resource.replace('_', ' ').title()}{bonus_str}{hammer_str}!"
        )
    return result


def get_recent_mines(child_key: str, limit: int = 5) -> list:
    mines = load_mines()
    child_mines = [m for m in mines if m.get("child") == child_key]
    return list(reversed(child_mines[-limit:]))


# ═══════════════════════════════════════════════════════════════════════════════
# BOSS SETTINGS (parent config)
# ═══════════════════════════════════════════════════════════════════════════════

def load_boss_settings() -> dict:
    data = _load(BOSS_SETTINGS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("available", True)
    data.setdefault("exchange_rate", 1)  # cents per real_coin
    data.setdefault("default_energy_per_quest", 1)
    data.setdefault("default_real_coins_per_quest", 1)
    data.setdefault("default_game_coins_per_quest", 2)
    return data


def save_boss_settings(settings: dict):
    _save(BOSS_SETTINGS_FILE, settings)


def get_exchange_rate() -> int:
    return int(load_boss_settings().get("exchange_rate", 1))


# ═══════════════════════════════════════════════════════════════════════════════
# QUEST COMPLETION (GDD v2 — awards real_coins, game_coins, energy, hero XP)
# ═══════════════════════════════════════════════════════════════════════════════

def complete_quest(quest_id: str, child_key: str) -> dict:
    """
    Mark a quest complete. Awards energy, real_coins, game_coins from quest values.
    Idempotent. Includes streak tracking.
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
        return _build_completion_state(child_key, 0, 0, 0)

    quest.setdefault("completions", {})[child_key] = True
    save_quests(quests)

    # Determine rewards
    settings = load_boss_settings()
    energy_val    = int(quest.get("energy_value", settings.get("default_energy_per_quest", 1)))
    rc_val        = int(quest.get("real_coin_value", settings.get("default_real_coins_per_quest", 1)))
    gc_val        = int(quest.get("game_coin_value", settings.get("default_game_coins_per_quest", 2)))

    award_currency(child_key, "energy",     energy_val, quest["title"], today)
    award_currency(child_key, "real_coins", rc_val,     quest["title"], today)
    award_currency(child_key, "game_coins", gc_val,     quest["title"], today)

    # Streak check
    streak = _update_streak_for_child(child_key, today)
    streak_bonus_gc = 0
    if streak.get("just_hit_milestone"):
        streak_bonus_gc = STREAK_MILESTONES.get(streak["current"], 0)
        if streak_bonus_gc:
            award_currency(child_key, "game_coins", streak_bonus_gc, f"🔥 {streak['current']}-Day Streak!")

    # Bonus quest auto-complete
    bonus_rc = _try_auto_complete_bonus(child_key, today)

    state = _build_completion_state(child_key, energy_val, rc_val, gc_val)
    state["streak"]          = streak
    state["streak_bonus_gc"] = streak_bonus_gc
    state["bonus_rc"]        = bonus_rc
    return state


def _build_completion_state(child_key: str, energy_earned: int, rc_earned: int, gc_earned: int) -> dict:
    st = get_child_state(child_key)
    hero = get_active_hero(child_key)
    return {
        "child":          child_key,
        "energy_earned":  energy_earned,
        "rc_earned":      rc_earned,
        "gc_earned":      gc_earned,
        **st,
        "hero_level":     hero["level"],
        "hero_name":      hero["name"],
        "hero_emoji":     hero["emoji"],
    }


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
                  if _is_bonus_quest(q) and not q.get("completions", {}).get(child_key)]
    if not bonus_list:
        return 0

    total_rc = 0
    for bq in bonus_list:
        bq.setdefault("completions", {})[child_key] = True
        rc = int(bq.get("real_coin_value", 1))
        gc = int(bq.get("game_coin_value", 2))
        award_currency(child_key, "real_coins", rc, bq["title"])
        award_currency(child_key, "game_coins", gc, bq["title"])
        total_rc += rc
    save_quests(quests)
    return total_rc


# ═══════════════════════════════════════════════════════════════════════════════
# STREAKS
# ═══════════════════════════════════════════════════════════════════════════════

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
        today     = _d.today().isoformat()
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
    if last_date == today_iso:
        s["just_hit_milestone"] = False
        return s

    from datetime import date as _d, timedelta
    yesterday = (_d.fromisoformat(today_iso) - timedelta(days=1)).isoformat()
    s["current"] = (s.get("current", 0) + 1) if last_date == yesterday else 1
    s["best"]    = max(s.get("best", 0), s["current"])
    s["last_date"] = today_iso
    just_hit = s["current"] in STREAK_MILESTONES
    streaks[child_key] = s
    save_streaks(streaks)
    s = dict(s)
    s["just_hit_milestone"] = just_hit
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# REWARDS & REDEMPTIONS (real_coins)
# ═══════════════════════════════════════════════════════════════════════════════

def load_rewards() -> list:
    data = _load(REWARDS_FILE, [])
    return data if isinstance(data, list) else []


def save_rewards(rewards: list):
    _save(REWARDS_FILE, rewards)


def create_reward(label: str, coin_price: int = 10, item_reward: str = "") -> dict:
    reward = {
        "id":         str(uuid.uuid4())[:8],
        "label":      label.strip(),
        "coin_price": max(1, int(coin_price)),  # real_coins required
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
    if not spend_currency(child_key, "real_coins", coin_price, r.get("reward_label", "")):
        return {"error": "insufficient_real_coins"}
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


# ═══════════════════════════════════════════════════════════════════════════════
# CHORE SYNC FROM SANCTA FAMILIA
# ═══════════════════════════════════════════════════════════════════════════════

def sync_chores_from_daily_schedule(today_iso: str = "") -> dict:
    if not today_iso:
        today_iso = date.today().isoformat()
    import fq_api as _api
    from datetime import date as _d
    today_d = _d.fromisoformat(today_iso)
    weekday = today_d.strftime("%A")
    settings = load_boss_settings()
    created, skipped, errors = [], [], []

    for child_key in CHILDREN_KEYS:
        child_name = CHILDREN_NAMES[child_key]
        try:
            day_list = _api.get_day_list(child_name, weekday, today_iso)
            existing = get_quests_for_child(child_key, today_iso)
            existing_titles = {q.get("title", "").strip().lower() for q in existing}
            for item in day_list:
                if item.get("kind") != "chore":
                    continue
                title = (item.get("label") or "").strip()
                if not title or title.lower() in existing_titles:
                    skipped.append(f"{child_name}: {title}")
                    continue
                e_val  = settings.get("default_energy_per_quest", 1)
                rc_val = settings.get("default_real_coins_per_quest", 1)
                gc_val = settings.get("default_game_coins_per_quest", 2)
                q = create_quest(title, "daily", [child_key],
                                 energy_value=e_val, real_coin_value=rc_val,
                                 game_coin_value=gc_val, iso_date=today_iso)
                _mark_synced(q["id"])
                created.append(f"{child_name}: {title}")
                existing_titles.add(title.lower())
        except Exception as exc:
            errors.append(f"{child_name}: {exc}")
    return {"created": created, "skipped": skipped, "errors": errors}


def sync_all_quests_for_child(child_name: str, iso_date: str = "") -> dict:
    if not iso_date:
        iso_date = date.today().isoformat()
    import fq_api as _api
    child_key = CHILD_NAME_TO_KEY.get(child_name)
    if not child_key:
        return {"created": [], "skipped": [], "errors": [f"Unknown child: {child_name}"]}

    today_d = date.fromisoformat(iso_date)
    weekday = today_d.strftime("%A")
    settings = load_boss_settings()
    created, skipped, errors = [], [], []

    try:
        existing        = get_quests_for_child(child_key, iso_date)
        existing_titles = {q.get("title", "").strip().lower() for q in existing}
        FULL_DAY_TITLE  = "Complete Your Entire School Day"
        school_count    = 0

        subjects = _api.get_school_tasks(child_name, weekday)
        for block in subjects:
            subj   = block.get("subject", "").strip()
            assign = block.get("assignment_text", "").strip()
            if not subj:
                continue
            brief = assign[:45].rstrip() + ("…" if len(assign) > 45 else "") if assign else ""
            title = f"{subj} — {brief}" if brief else subj
            if title.lower() in existing_titles:
                skipped.append(f"{child_name}: {title}")
                continue
            e_val  = settings.get("default_energy_per_quest", 1)
            rc_val = settings.get("default_real_coins_per_quest", 1)
            gc_val = settings.get("default_game_coins_per_quest", 2)
            q = create_quest(title, "daily", [child_key],
                             energy_value=e_val, real_coin_value=rc_val,
                             game_coin_value=gc_val, iso_date=iso_date)
            _mark_synced(q["id"], from_print=True)
            created.append(f"{child_name}: {title}")
            existing_titles.add(title.lower())
            school_count += 1

        day_list = _api.get_day_list(child_name, weekday, iso_date)
        for item in day_list:
            if item.get("kind") != "chore":
                continue
            title = (item.get("label") or "").strip()
            if not title or title.lower() in existing_titles:
                skipped.append(f"{child_name}: {title}")
                continue
            e_val  = settings.get("default_energy_per_quest", 1)
            rc_val = settings.get("default_real_coins_per_quest", 1)
            gc_val = settings.get("default_game_coins_per_quest", 2)
            q = create_quest(title, "daily", [child_key],
                             energy_value=e_val, real_coin_value=rc_val,
                             game_coin_value=gc_val, iso_date=iso_date)
            _mark_synced(q["id"], from_print=True)
            created.append(f"{child_name}: {title}")
            existing_titles.add(title.lower())

        if school_count > 0 and FULL_DAY_TITLE.lower() not in existing_titles:
            q = create_quest(FULL_DAY_TITLE, "daily", [child_key],
                             energy_value=3, real_coin_value=5, game_coin_value=10,
                             iso_date=iso_date)
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


# ═══════════════════════════════════════════════════════════════════════════════
# PARTIAL XP AWARD (compatibility shim — now awards energy+real_coins+game_coins)
# ═══════════════════════════════════════════════════════════════════════════════

def award_partial_xp(child_key: str, amount: int, label: str, iso_date: str = "") -> dict:
    """Legacy compatibility — awards game_coins and real_coins equally."""
    if amount <= 0 or child_key not in CHILDREN_KEYS:
        return {}
    iso = iso_date or date.today().isoformat()
    award_currency(child_key, "real_coins",  amount, label, iso)
    award_currency(child_key, "game_coins",  amount, label, iso)
    award_currency(child_key, "energy",      1,      label, iso)
    return _build_completion_state(child_key, 1, amount, amount)


def award_school_step(child_key: str, quest: dict, n_steps: int,
                      label: str, iso_date: str = "") -> dict:
    """
    Award proportional energy/real_coins/game_coins for one school step.
    Uses the quest's actual v2 reward values, divided evenly across all steps.
    """
    if child_key not in CHILDREN_KEYS:
        return {}
    iso = iso_date or date.today().isoformat()
    settings   = load_boss_settings()
    e_total    = int(quest.get("energy_value",    settings.get("default_energy_per_quest",    1)))
    rc_total   = int(quest.get("real_coin_value", settings.get("default_real_coins_per_quest", 1)))
    gc_total   = int(quest.get("game_coin_value", settings.get("default_game_coins_per_quest", 2)))
    n          = max(1, n_steps)
    e_step     = max(1, round(e_total  / n))
    rc_step    = max(1, round(rc_total / n))
    gc_step    = max(1, round(gc_total / n))
    award_currency(child_key, "energy",     e_step,  label, iso)
    award_currency(child_key, "real_coins", rc_step, label, iso)
    award_currency(child_key, "game_coins", gc_step, label, iso)
    return _build_completion_state(child_key, e_step, rc_step, gc_step)


def finalize_quest_no_reward(quest_id: str, child_key: str) -> dict:
    """
    Mark a quest as complete WITHOUT re-awarding its coins (used when partial
    rewards have already been distributed step-by-step).  Still triggers streak
    tracking and bonus-quest auto-complete logic.
    """
    quests = load_quests()
    quest  = next((q for q in quests if q.get("id") == quest_id), None)
    if quest is None or quest.get("completions", {}).get(child_key):
        return {}
    quest.setdefault("completions", {})[child_key] = True
    save_quests(quests)
    today            = date.today().isoformat()
    streak           = _update_streak_for_child(child_key, today)
    streak_bonus_gc  = 0
    if streak.get("just_hit_milestone"):
        streak_bonus_gc = STREAK_MILESTONES.get(streak["current"], 0)
        if streak_bonus_gc:
            award_currency(child_key, "game_coins", streak_bonus_gc,
                           f"🔥 {streak['current']}-Day Streak!")
    bonus_rc = _try_auto_complete_bonus(child_key, today)
    state = _build_completion_state(child_key, 0, 0, 0)
    state["streak"]          = streak
    state["streak_bonus_gc"] = streak_bonus_gc
    state["bonus_rc"]        = bonus_rc
    return state


# ═══════════════════════════════════════════════════════════════════════════════
# LEGACY SHIMS for old API routes (boss battle, stamina, characters)
# ═══════════════════════════════════════════════════════════════════════════════

# Old stamina shim — energy is now stored in xp.json
MAX_STAMINA = 20  # kept for any UI that references it; represents max energy display

def get_stamina(child_key: str) -> int:
    return get_energy(child_key)


def refill_stamina(child_key: str, amount: int = 3) -> int:
    award_currency(child_key, "energy", amount, "Quest bonus energy")
    return get_energy(child_key)


def spend_stamina(child_key: str, amount: int) -> bool:
    return spend_currency(child_key, "energy", amount, "Boss attack")


# Old character shim — heroes replace characters
CHARACTERS = {
    "link":      {"name": "Link",     "emoji": "🗡️", "description": "Hero of Hyrule", "base_attack": 8,  "base_defense": 5,  "base_health": 100, "special": "3 hits/turn"},
    "zelda":     {"name": "Zelda",    "emoji": "👑", "description": "Princess",       "base_attack": 9,  "base_defense": 6,  "base_health": 120, "special": "2 hits, bonus XP"},
    "ganondorf": {"name": "Ganondorf","emoji": "😈", "description": "King of Evil",   "base_attack": 12, "base_defense": 3,  "base_health": 90,  "special": "5 hits/turn"},
    "samus":     {"name": "Samus",    "emoji": "🚀", "description": "Bounty Hunter",  "base_attack": 10, "base_defense": 7,  "base_health": 150, "special": "4 hits, mine bonus"},
    "mario":     {"name": "Mario",    "emoji": "🍄", "description": "Super Mario",    "base_attack": 9,  "base_defense": 5,  "base_health": 110, "special": "4 hits, coin bonus"},
    "fox":       {"name": "Fox",      "emoji": "🦊", "description": "Star Fox",       "base_attack": 11, "base_defense": 4,  "base_health": 100, "special": "6 hits/turn"},
}
DEFAULT_CHARACTER = "link"


def get_character(child_key: str) -> dict:
    hero = get_active_hero(child_key)
    return {
        "key":          hero["key"],
        "name":         hero["name"],
        "emoji":        hero["emoji"],
        "description":  f"Level {hero['level']} — {hero['form_label']}",
        "base_attack":  hero["damage"] // 100,
        "base_defense": hero["defense"] // 100,
        "base_health":  hero["hp"],
        "special":      f"{hero['hits_per_turn']} hits/turn",
    }


def get_attack_stat(child_key: str) -> int:
    return get_active_hero(child_key)["damage"] // 100


def get_defense_stat(child_key: str) -> int:
    return get_active_hero(child_key)["defense"] // 100


def get_health_stat(child_key: str) -> int:
    return get_active_hero(child_key)["hp"]


# Old XP state shim — for any views still reading level/total_xp
def _xp_state(xp_data: dict, child_key: str) -> dict:
    child = xp_data.get(child_key, {})
    rc = child.get("real_coins", child.get("coins", 0))
    gc = child.get("game_coins", 0)
    return {
        "child":        child_key,
        "total_xp":     rc + gc,
        "real_coins":   rc,
        "game_coins":   gc,
        "energy":       child.get("energy", 0),
        "crystals":     child.get("crystals", 0),
        "diamonds":     child.get("diamonds", 0),
        "copper":       child.get("copper", 0),
        "iron":         child.get("iron", 0),
        "level":        {"level": 1, "label": "Adventurer"},
        "next_level":   None,
        "progress_pct": 50,
    }


def get_child_xp_state(child_key: str) -> dict:
    xp_data = load_xp()
    return _xp_state(xp_data, child_key)


# Old battle shims for views that reference start_boss_battle
def start_boss_battle(child_key: str, difficulty: str = "", use_battle_axe: bool = False) -> dict:
    """Legacy shim — redirects to new attack_boss."""
    return attack_boss(child_key, use_battle_axe=use_battle_axe)


def get_recent_battles(child_key: str, limit: int = 5) -> list:
    bp = load_boss_progress()
    history = bp.get(child_key, {}).get("history", [])
    return list(reversed(history[-limit:]))


def get_active_battle(child_key: str) -> dict | None:
    return None  # v2 uses persistent boss progress, no "active" battles


# Old boss difficulty table (kept for admin panel compatibility)
BOSS_DIFFICULTIES = {
    "easy":      {"label": "Easy",      "emoji": "🟢", "hp": 500,   "stamina_cost": 1, "win_coins": 10,  "win_xp": 10,  "lose_chores": 0, "description": "Casual"},
    "medium":    {"label": "Medium",    "emoji": "🟡", "hp": 2500,  "stamina_cost": 2, "win_coins": 30,  "win_xp": 30,  "lose_chores": 1, "description": "Standard"},
    "hard":      {"label": "Hard",      "emoji": "🟠", "hp": 7500,  "stamina_cost": 3, "win_coins": 75,  "win_xp": 75,  "lose_chores": 2, "description": "Challenging"},
    "legendary": {"label": "Legendary", "emoji": "🔴", "hp": 20000, "stamina_cost": 5, "win_coins": 200, "win_xp": 200, "lose_chores": 3, "description": "Epic"},
}

# v1 boss type table — replaced by sequential bosses in v2; kept as shim for the
# parent boss-settings UI (which still shows these for the award-item workflow).
BOSS_TYPES = {
    "orc":    {"label": "Orc",    "emoji": "👹", "description": "Basic enemy",    "hp_mult": 1.0},
    "troll":  {"label": "Troll",  "emoji": "👺", "description": "Tough and mean", "hp_mult": 1.5},
    "dragon": {"label": "Dragon", "emoji": "🐉", "description": "Final boss",     "hp_mult": 2.0},
}
