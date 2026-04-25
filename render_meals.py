# -*- coding: utf-8 -*-
"""
render_meals.py - Weekly meal planning system.

Data files:
  data/meal_rules.json          - The 25-rule system (master config)
  data/meal_plan/YYYY-WW.json   - Weekly plan {day: {breakfast, lunch, dinner, snacks, dad_lunch}}
  data/meal_inventory.json      - Current inventory (fridge/freezer/pantry)
  data/recipes.json             - Saved recipe library
"""
import os, json, uuid
from datetime import date, timedelta
from html import escape
from safe_utils import ensure_file, safe_save_json

MEALS_DIR     = "data/meal_plan"
RULES_FILE    = "data/meal_rules.json"
INVENTORY_FILE = "data/meal_inventory.json"
RECIPES_FILE  = "data/recipes.json"

DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

MEAL_SLOTS = ["breakfast","lunch","dinner","dessert","snacks","dad_lunch"]
MEAL_SLOT_SET = set(MEAL_SLOTS)

MEAL_SLOT_LABELS = {
    "breakfast": "Breakfast",
    "lunch":     "Lunch",
    "dinner":    "Dinner",
    "dessert":   "Dessert",
    "snacks":    "Snacks",
    "dad_lunch": "Dad's Lunch",
}

# ---------------------------------------------------------------------------
# Slot value accessors — Lorenzo can save a slot as a plain string (legacy)
# OR as a dict {"display": "Chicken Chili", "recipe_id": "r004"} when she
# links it to a saved recipe card.  Every reader in the codebase MUST go
# through these two helpers so the UI never accidentally renders {...} or
# crashes on `.strip()`.
# ---------------------------------------------------------------------------

def slot_display_text(value) -> str:
    """Return the user-facing meal text for a slot value.
    Accepts plain string, dict {'display','recipe_id'}, None, or anything
    else.  Always returns a stripped str ('' if there's nothing to show)."""
    if isinstance(value, dict):
        return str(value.get("display", "") or "").strip()
    if value is None:
        return ""
    return str(value).strip()

def slot_recipe_id(value):
    """Return the linked recipe_id (str) for a slot value, or None."""
    if isinstance(value, dict):
        rid = value.get("recipe_id")
        if rid:
            rid = str(rid).strip()
            return rid or None
    return None

# Child colors for grid headers
CHILD_COLORS = {
    "Monday":    "#1a3870",
    "Tuesday":   "#2d5016",
    "Wednesday": "#8a6318",
    "Thursday":  "#8b3a10",
    "Friday":    "#4a2070",
    "Saturday":  "#1a5050",
    "Sunday":    "#6b1a1a",
}

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _plan_path(week_key: str) -> str:
    os.makedirs(MEALS_DIR, exist_ok=True)
    return f"{MEALS_DIR}/{week_key}.json"

def _week_key(for_date: date = None) -> str:
    d = for_date or date.today()
    # Use Monday of the week as canonical key (e.g. 2026-04-06)
    monday = d - timedelta(days=d.weekday())
    return monday.isoformat()

def _planning_week_key(for_date: date = None) -> str:
    """The Monday key Lauren is most likely actively PLANNING right now.
    Mon–Thu → this week's Monday.  Fri/Sat/Sun → next week's Monday.
    This must mirror the default in render_meal_print_page so that Lorenzo's
    saved edits land on the same file the fridge card displays."""
    d = for_date or date.today()
    if d.weekday() >= 4:  # Fri=4, Sat=5, Sun=6
        return (d + timedelta(days=(7 - d.weekday()))).isoformat()
    return _week_key(d)

def _week_start(for_date: date = None) -> date:
    d = for_date or date.today()
    return d - timedelta(days=d.weekday())  # Monday

def load_meal_plan(week_key: str = None) -> dict:
    import re as _re
    key = week_key or date.today().isoformat()
    default = {
        "start": key,
        "week":  key,  # backward compat
        "generated": False,
        "days": {day: {slot: "" for slot in MEAL_SLOTS} for day in DAYS}
    }
    path = _plan_path(key)
    # Fast path: file exists under given key
    if os.path.exists(path):
        return ensure_file(path, default)
    # If key is an ISO date but not a Monday, try the Monday-of-that-week key.
    # Plans are saved keyed on the Monday ISO date, so any other day in the
    # same week should resolve to the same plan.
    if _re.match(r'\d{4}-\d{2}-\d{2}', key):
        try:
            d = date.fromisoformat(key)
            monday = d - timedelta(days=d.weekday())
            mon_key = monday.isoformat()
            if mon_key != key:
                mon_path = _plan_path(mon_key)
                if os.path.exists(mon_path):
                    plan = ensure_file(mon_path, default)
                    plan.setdefault("start", mon_key)
                    return plan
            # Backward compat: also try the old YYYY-WNN week key
            old_key  = d.strftime("%Y-W%W")
            old_path = _plan_path(old_key)
            if os.path.exists(old_path):
                plan = ensure_file(old_path, default)
                plan.setdefault("start", key)
                return plan
        except Exception:
            pass
    return ensure_file(path, default)

def _backup_meal_plan(week_key: str) -> None:
    """Snapshot the existing plan file (if any) into data/meal_plan/.backups/
    before it gets overwritten. Keeps the last 30 versions per week so we can
    recover from a bad save (Lorenzo wiping a slot, accidental clear, etc.)."""
    try:
        import shutil, datetime as _dt
        src = _plan_path(week_key)
        if not os.path.exists(src):
            return
        backup_dir = f"{MEALS_DIR}/.backups"
        os.makedirs(backup_dir, exist_ok=True)
        # Microseconds + random suffix → collision-proof when Lorenzo emits
        # multiple [MEAL_UPDATE] tags in one reply (each triggers a save).
        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        import uuid as _uuid
        dst = f"{backup_dir}/{week_key}__{ts}-{_uuid.uuid4().hex[:6]}.json"
        shutil.copy2(src, dst)
        # Rotate per-week: keep last 30 backups for this week_key
        try:
            prefix = f"{week_key}__"
            entries = sorted(
                [f for f in os.listdir(backup_dir) if f.startswith(prefix) and f.endswith(".json")],
                reverse=True,
            )
            for old in entries[30:]:
                try:
                    os.remove(os.path.join(backup_dir, old))
                except Exception:
                    pass
        except Exception:
            pass
    except Exception as _e:
        print(f"[backup_meal_plan] failed for {week_key}: {_e}")


def save_meal_plan(plan: dict):
    # Use "start" (ISO date) as primary key; fall back to "week" for old plans
    key = plan.get("start") or plan.get("week", date.today().isoformat())
    _backup_meal_plan(key)  # snapshot prior version BEFORE overwriting
    safe_save_json(_plan_path(key), plan)


# ---------------------------------------------------------------------------
# Cook-start calculation
# ---------------------------------------------------------------------------

def parse_duration_minutes(text: str) -> int:
    """
    Parse a human-readable duration string into total minutes.
    Examples: "15 minutes", "1 hour 30 minutes", "2 hrs", "45 min", "1h30m"
    Returns 0 if unparseable.
    """
    import re as _re
    if not text:
        return 0
    t = text.lower().strip()
    total = 0
    # Hours
    m = _re.search(r'(\d+(?:\.\d+)?)\s*h(?:our|r)?s?', t)
    if m:
        total += int(float(m.group(1)) * 60)
    # Minutes
    m = _re.search(r'(\d+(?:\.\d+)?)\s*m(?:in(?:ute)?s?)?(?!\s*in)', t)
    if m:
        total += int(float(m.group(1)))
    # Fallback: bare number
    if total == 0:
        m = _re.match(r'^(\d+)$', t)
        if m:
            total = int(m.group(1))
    return total


def get_frol_dinner_time(weekday: str) -> str:
    """Return the dinner serve time (HH:MM 24-h) for the given weekday from the FROL.

    Looks for the earliest slot in Mom's day template whose label contains
    'dinner'.  Falls back to '18:00' if nothing is found.
    """
    import re as _re3
    try:
        from data_helpers import get_frol_day_slots
        _slots = get_frol_day_slots(weekday, "Mom")
        for _t, _label in _slots.items():
            if "dinner" in str(_label).lower():
                # parse _t: "5:00 PM", "17:00", etc.
                _pm = _re3.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)?', _t.strip(), _re3.I)
                if _pm:
                    _h = int(_pm.group(1)); _m = int(_pm.group(2))
                    _mer = (_pm.group(3) or "").upper()
                    if _mer == "PM" and _h != 12:
                        _h += 12
                    elif _mer == "AM" and _h == 12:
                        _h = 0
                    return f"{_h:02d}:{_m:02d}"
    except Exception:
        pass
    return "18:00"  # safe fallback


def get_cook_start_for_day(day_data: dict, fallback_recipes: bool = True, weekday: str = "") -> dict | None:
    """
    Given a meal plan day dict, compute when cooking should start.
    Returns a dict:
        { hhmm: "17:00", serve_hhmm: "18:00",
          label: "Start cooking: Beef stew (1 hr)", total_minutes: 60 }
    or None if there is no dinner or no timing info.

    Pass weekday (e.g. "Monday") so the serve time is looked up from the
    FROL instead of defaulting to 6:00 PM for every day.
    """
    import re as _re

    _dinner_raw = day_data.get("dinner")
    dinner = slot_display_text(_dinner_raw)
    if not dinner or dinner.lower().startswith("tbd") or dinner.lower().startswith("leftover"):
        return None

    # Prefer explicit per-day timing fields set by Lorenzo
    prep_str  = day_data.get("prep_time", "")
    cook_str  = day_data.get("cook_time", "")
    serve_str = day_data.get("serve_time", "")  # "18:00" or "6:00 PM"

    # ── Recipe lookup for missing timing fields ───────────────────────────
    # Priority order:
    #   1. Direct lookup by recipe_id (Phase-2 dict-shape slot) — exact, no cap.
    #      When Lorenzo links a saved card we trust its declared prep/cook
    #      times verbatim; if a recipe really takes 4 h prep, we honour it.
    #   2. Fuzzy name search — legacy fallback for plain-string slots.
    #      Capped at 90 min prep because fuzzy hits often pull in recipes
    #      whose "prep" includes brining/marinating/rising — inactive time
    #      that isn't really "start cooking" time.
    _recipe_fallback_prep = 0
    _recipe_fallback_cook = 0
    if fallback_recipes and (not prep_str or not cook_str):
        _rid = slot_recipe_id(_dinner_raw)
        r = None
        try:
            if _rid:
                from data_helpers import get_recipe_by_id
                r = get_recipe_by_id(_rid)
        except Exception:
            r = None

        if r is not None:
            # Tier 1: exact match via recipe_id — no cap
            if not prep_str:
                _recipe_fallback_prep = parse_duration_minutes(r.get("prep_time", "")) or 0
            if not cook_str:
                _recipe_fallback_cook = parse_duration_minutes(r.get("cook_time", "")) or 0
        else:
            # Tier 2: fuzzy name search — keep the 90-min cap
            try:
                import re as _re2
                from data_helpers import search_recipes
                # Try the full dinner string first, then progressively shorter candidates
                # (dinner entries often have sides appended: "Beef stew + sourdough bread")
                _search_candidates = [dinner]
                _primary = _re2.split(r'\s*[+/]\s*|\s+with\s+|\s+and\s+', dinner, maxsplit=1)[0].strip()
                if _primary and _primary.lower() != dinner.lower():
                    _search_candidates.append(_primary)
                hits = []
                for _cand in _search_candidates:
                    hits = search_recipes(_cand)
                    if hits:
                        break
                if hits:
                    r = hits[0]
                    if not prep_str:
                        _rp = parse_duration_minutes(r.get("prep_time", ""))
                        _recipe_fallback_prep = min(_rp, 90) if _rp else 0
                    if not cook_str:
                        _recipe_fallback_cook = parse_duration_minutes(r.get("cook_time", ""))
            except Exception:
                pass

    prep_min  = parse_duration_minutes(prep_str) if prep_str else _recipe_fallback_prep
    cook_min  = parse_duration_minutes(cook_str) if cook_str else _recipe_fallback_cook
    total_min = prep_min + cook_min

    if total_min == 0:
        return None

    # Parse serve time — prefer explicit field, then FROL, then 6 PM hard fallback
    serve_hhmm = get_frol_dinner_time(weekday) if weekday else "18:00"
    if serve_str:
        sv = serve_str.strip()
        # already HH:MM
        if _re.match(r'^\d{1,2}:\d{2}$', sv):
            h, m = sv.split(":")
            serve_hhmm = f"{int(h):02d}:{m}"
        else:
            # "6:00 PM", "6 PM", etc.
            pm = _re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', sv, _re.I)
            if pm:
                hh = int(pm.group(1)); mm = int(pm.group(2) or 0)
                meridiem = pm.group(3).lower()
                if meridiem == "pm" and hh != 12:
                    hh += 12
                elif meridiem == "am" and hh == 12:
                    hh = 0
                serve_hhmm = f"{hh:02d}:{mm:02d}"

    # Subtract total cooking time + 15-min buffer from serve time.
    # The buffer absorbs little real-world losses (kitchen wandering, an oven
    # that hasn't quite hit temperature, a knock at the door) so dinner still
    # lands on the table at serve_hhmm.  The buffer is invisible in the label
    # — Lauren just sees an earlier "Start cooking" time.
    COOK_BUFFER_MIN = 15
    sh, sm = [int(x) for x in serve_hhmm.split(":")]
    serve_total_min = sh * 60 + sm
    start_total_min = serve_total_min - total_min - COOK_BUFFER_MIN

    if start_total_min < 0:
        return None  # sanity check

    start_h = start_total_min // 60
    start_m = start_total_min % 60
    start_hhmm = f"{start_h:02d}:{start_m:02d}"

    # Build duration label
    parts = []
    if prep_min:
        parts.append(f"{prep_min} min prep")
    if cook_min:
        if cook_min >= 60:
            h2 = cook_min // 60; m2 = cook_min % 60
            parts.append(f"{h2}h{m2:02d}m cook" if m2 else f"{h2} hr cook")
        else:
            parts.append(f"{cook_min} min cook")
    duration_label = " + ".join(parts) if parts else f"{total_min} min"

    # Short dinner name for the label (max ~35 chars)
    short_dinner = dinner if len(dinner) <= 35 else dinner[:32].rstrip() + "…"

    return {
        "hhmm": start_hhmm,
        "serve_hhmm": serve_hhmm,
        "label": f"🍳 Start cooking: {short_dinner}  ({duration_label})",
        "total_minutes": total_min,
    }


def load_inventory() -> dict:
    return ensure_file(INVENTORY_FILE, {
        "fridge": "", "freezer": "", "pantry": "",
        "use_soon": "", "last_updated": ""
    })

def save_inventory(inv: dict):
    safe_save_json(INVENTORY_FILE, inv)

def load_meal_rules() -> dict:
    try:
        if os.path.exists(RULES_FILE):
            with open(RULES_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def load_recipes() -> list:
    return ensure_file(RECIPES_FILE, [])

def save_recipes(recipes: list):
    safe_save_json(RECIPES_FILE, recipes)

def save_recipe(name: str, ingredients: str, instructions: str,
                tags: list = None, prep_time: str = "", image: str = "") -> dict:
    recipes = load_recipes()
    recipe = {
        "id": str(uuid.uuid4())[:8],
        "name": name.strip(),
        "ingredients": ingredients.strip(),
        "instructions": instructions.strip(),
        "tags": tags or [],
        "prep_time": prep_time.strip(),
        "image": (image or "").strip(),
        "created": date.today().isoformat(),
    }
    recipes.append(recipe)
    save_recipes(recipes)
    return recipe

# ---------------------------------------------------------------------------
# AI generation prompt builder
# ---------------------------------------------------------------------------

def _build_meal_prompt(inventory: dict, cycle_phase: str = "",
                        capacity: str = "", week_start: date = None,
                        constraints: str = "") -> str:
    rules = load_meal_rules()
    ws = week_start or _week_start()

    # Pull calendar events for the week if possible
    week_events = []
    try:
        from data_helpers import load_subscribed_calendars
        # Just note it's available; actual fetch happens at runtime
        week_events_note = "Check calendar for busy days this week."
    except Exception:
        week_events_note = ""

    prompt = """You are a meal planning assistant for a large Catholic homeschool family.
Generate a complete 7-day meal plan for the week starting """ + ws.strftime("%B %d, %Y") + """.

FAMILY MEAL RULES (follow strictly):
""" + json.dumps(rules, indent=2) + """

CURRENT INVENTORY:
Fridge: """ + (inventory.get("fridge","") or "not specified") + """
Freezer: """ + (inventory.get("freezer","") or "not specified") + """
Pantry: """ + (inventory.get("pantry","") or "not specified") + """
USE SOON (priority): """ + (inventory.get("use_soon","") or "none flagged") + """

CURRENT CONTEXT:
Cycle phase: """ + (cycle_phase or "not specified") + """
Capacity: """ + (capacity or "not specified") + """
""" + week_events_note + """

""" + (f"STANDING CONSTRAINTS (Lauren's notes — follow strictly):\n{constraints}\n\n" if constraints.strip() else "") + """CRITICAL RULES REMINDER:
- Tuesday = leftovers day (no cooking)
- Friday = meatless (fish or vegetarian)
- Use-soon items MUST appear in meals early in the week
- Inventory-first: use what you have before adding to grocery list
- Anchor meals required: brined roast chicken, roast beef, fish fry (Friday)
- Keep batch soup available (make one at start of week)
- Dad needs packable lunch every weekday
- Include simple/familiar options for Michael; soft/easy for James
- Cycle phase nutrition: """ + (cycle_phase or "standard balanced meals") + """

BOYS DINNER PREP TASKS:
Each boy gets exactly ONE specific dinner-related task every day. Assign by age:
- JP (age 14): Real cooking tasks — browning meat, stirring soups on the stove, chopping with a chef's knife, draining pasta, managing timers, operating appliances independently.
- Joseph (age 12): Active prep — washing and peeling vegetables, measuring ingredients, mixing batters or doughs, tearing, slicing with a paring knife, setting out all mise en place.
- Michael (age 5): Simple confidence-building tasks — rinsing produce under the tap, tearing bread, fetching named pantry items, stirring cold salads, placing rolls in a basket.
TASK TIMING RULES:
- Tasks that involve the stove, cutting, or advanced prep MUST be doable before 4PM.
- "Set the table," "fill water glasses," "put napkins out" are dinner-time tasks — assign these only as a secondary note if a boy has no real prep task that day.
- On leftover/Ziplock Buffet days, assign reheating, labeling, or organizing tasks.
- Be SPECIFIC: "JP: brown the ground beef for chili" not "JP: help with dinner."

OUTPUT FORMAT (JSON only, no other text):
{
  "Monday":    { "breakfast": "...", "lunch": "...", "dinner": "...", "snacks": "...", "dad_lunch": "...", "boys_help": "JP: [task] · Joseph: [task] · Michael: [task]" },
  "Tuesday":   { "breakfast": "...", "lunch": "leftovers from [specify]", "dinner": "...", "snacks": "...", "dad_lunch": "...", "boys_help": "JP: [task] · Joseph: [task] · Michael: [task]" },
  "Wednesday": { "breakfast": "...", "lunch": "...", "dinner": "...", "snacks": "...", "dad_lunch": "...", "boys_help": "JP: [task] · Joseph: [task] · Michael: [task]" },
  "Thursday":  { "breakfast": "...", "lunch": "...", "dinner": "...", "snacks": "...", "dad_lunch": "...", "boys_help": "JP: [task] · Joseph: [task] · Michael: [task]" },
  "Friday":    { "breakfast": "...", "lunch": "sardine sandwiches or soup", "dinner": "Fish fry", "snacks": "...", "dad_lunch": "...", "boys_help": "JP: [task] · Joseph: [task] · Michael: [task]" },
  "Saturday":  { "breakfast": "...", "lunch": "...", "dinner": "...", "snacks": "...", "dad_lunch": "N/A", "boys_help": "JP: [task] · Joseph: [task] · Michael: [task]" },
  "Sunday":    { "breakfast": "...", "lunch": "...", "dinner": "Ziplock Buffet (leftovers)", "snacks": "...", "dad_lunch": "N/A", "boys_help": "JP: [task] · Joseph: [task] · Michael: [task]" }
}

Also include a "grocery_gaps" array listing ingredients NOT in the inventory that are needed,
and a "use_soon_used" array listing which use-soon items you incorporated and when.
And a "prep_notes" object with one prep note per day (what to defrost/start early).
"""
    return prompt


# ---------------------------------------------------------------------------
# Shared meal-day card (dashboard · child pages · printouts)
# ---------------------------------------------------------------------------

def render_meal_today_card(target_date=None, compact: bool = False) -> str:
    """
    Returns an HTML card showing today's meals, prep notes, and boys' help
    ideas.  Returns "" when no meals are planned (safe to inline anywhere).
    """
    from html import escape as _e
    from datetime import date as _date

    td      = target_date if target_date is not None else _date.today()
    weekday = td.strftime("%A")
    try:
        plan  = load_meal_plan(_week_key(td))
        slots = plan.get("days", {}).get(weekday, {})
        prep  = plan.get("prep_notes", {}).get(weekday, "").strip()
    except Exception:
        slots = {}
        prep  = ""

    meal_icons  = {"breakfast": "☀️", "lunch": "🥗", "dinner": "🍽️", "dessert": "🍮", "snacks": "🍎"}
    meal_labels = {"breakfast": "Breakfast", "lunch": "Lunch",
                   "dinner": "Dinner", "dessert": "Dessert", "snacks": "Snacks"}
    boys_help   = slot_display_text(slots.get("boys_help"))

    rows_html = ""
    for slot in ["breakfast", "lunch", "dinner", "dessert", "snacks"]:
        val = slot_display_text(slots.get(slot))
        if not val:
            continue
        icon  = meal_icons[slot]
        label = meal_labels[slot]
        fs    = "0.78em" if compact else "0.85em"
        rows_html += (
            f'<div style="display:flex;align-items:flex-start;gap:10px;'
            f'padding:6px 0;border-bottom:1px solid var(--border-light);">'
            f'<div style="width:80px;flex-shrink:0;font-size:0.68em;font-weight:700;'
            f'color:var(--ink-faint);text-transform:uppercase;letter-spacing:.05em;'
            f'padding-top:3px;">{icon} {_e(label)}</div>'
            f'<div style="flex:1;font-size:{fs};color:var(--ink);line-height:1.4;">'
            f'{_e(val)}</div>'
            f'</div>'
        )

    if not rows_html:
        return ""

    prep_html = ""
    if prep:
        prep_html = (
            f'<div style="margin-top:10px;padding:8px 12px;background:#f0fdf4;'
            f'border-radius:8px;border-left:3px solid #22c55e;">'
            f'<div style="font-size:0.67em;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.08em;color:#166534;margin-bottom:3px;">📋 Prep</div>'
            f'<div style="font-size:0.82em;color:#15803d;line-height:1.4;">{_e(prep)}</div>'
            f'</div>'
        )

    help_html = ""
    if boys_help:
        help_html = (
            f'<div style="margin-top:8px;padding:8px 12px;background:#fefce8;'
            f'border-radius:8px;border-left:3px solid #eab308;">'
            f'<div style="font-size:0.67em;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.08em;color:#92400e;margin-bottom:3px;">👦 Boys can help</div>'
            f'<div style="font-size:0.82em;color:#78350f;line-height:1.4;">{_e(boys_help)}</div>'
            f'</div>'
        )

    pad = "12px 14px" if compact else "14px 16px"
    return (
        f'<div class="card" style="padding:{pad};margin-bottom:12px;">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
        f'<span style="font-size:0.68em;font-weight:800;letter-spacing:.1em;'
        f'text-transform:uppercase;color:var(--ink-faint);">🍽️ Today\'s Meals</span>'
        f'<a href="/meals" style="margin-left:auto;font-size:0.72em;color:var(--ink-faint);'
        f'text-decoration:none;opacity:0.55;">edit →</a>'
        f'</div>'
        f'{rows_html}'
        f'{prep_html}'
        f'{help_html}'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Page renderers
# ---------------------------------------------------------------------------

def render_meal_planner_page(status: str = "", week_key: str = None) -> str:
    from ui_helpers import html_page, page_header, render_status_message, top_nav
    from render_daily_plan import load_daily_plan
    from render_morning_anchor import _get_anchor_state
    import re as _re

    # Parse start date — accepts YYYY-MM-DD (new) or YYYY-WNN (legacy)
    raw_key = week_key or ""
    try:
        if _re.match(r'\d{4}-\d{2}-\d{2}', raw_key):
            ws = date.fromisoformat(raw_key)
        elif raw_key:
            from datetime import datetime as _dtp
            ws = _dtp.strptime(raw_key + "-1", "%Y-W%W-%w").date()
        else:
            ws = _week_start()  # default: Monday of current week
    except Exception:
        ws = _week_start()

    # Canonical key is always the ISO start date
    wk = ws.isoformat()

    plan   = load_meal_plan(wk)
    inv    = load_inventory()
    days_data = plan.get("days", {})

    # Ordered day names for this specific 7-day period
    ordered_days = [(ws + timedelta(days=i)).strftime("%A") for i in range(7)]

    # API key for AI features
    try:
        from render_settings import load_app_settings as _las
        _s = _las()
        _api_key = _s.get("anthropic_api_key","") or _s.get("family_constraints",{}).get("anthropic_api_key","")
    except Exception:
        _api_key = ""

    # Get current cycle phase and capacity from today's anchor
    iso    = date.today().isoformat()
    anchor = _get_anchor_state(iso)
    cycle_phase = anchor.get("cycle_phase", "")
    capacity    = anchor.get("capacity", "")

    # Navigation — step exactly 7 days in either direction
    prev_week = (ws - timedelta(weeks=1)).isoformat()
    next_week = (ws + timedelta(weeks=1)).isoformat()

    last_day  = ws + timedelta(days=6)
    week_label = ws.strftime("%B %d") + " – " + last_day.strftime("%B %d, %Y")

    # ── Inventory input section ───────────────────────────────────────────────
    inv_section = (
        '<div class="card" id="inventory-card">'
        '<div style="display:flex;align-items:center;justify-content:space-between;'
        'flex-wrap:wrap;gap:8px;margin-bottom:14px;">'
        '<h3 style="margin:0;">Pantry inventory</h3>'
        '<div style="display:flex;gap:8px;">'
        '<button onclick="saveInventory()" style="padding:6px 14px;font-size:0.82em;">Save inventory</button>'
        '<button onclick="generatePlan()" style="padding:6px 14px;font-size:0.82em;'
        'background:var(--ink);color:var(--gold-light);border:none;font-weight:700;">'
        '&#10024; Generate meal plan</button>'
        '</div></div>'

        # Quick-paste / dictate block
        '<div style="background:#faf8f5;border-radius:10px;border:1.5px dashed var(--border);'
        'padding:12px 14px;margin-bottom:14px;">'
        '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">'
        '<div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;'
        'color:var(--ink-faint);">&#9998; Paste or speak your inventory</div>'
        '<button id="mic-btn" onclick="toggleMic()" type="button" '
        'style="padding:5px 12px;font-size:0.82em;background:#1c3d6e;color:white;border:none;'
        'border-radius:8px;cursor:pointer;font-family:inherit;display:flex;align-items:center;gap:5px;">'
        '&#127908; Dictate</button>'
        '</div>'
        '<textarea id="inv-paste-raw" rows="5" '
        'placeholder="Just talk: In the fridge I have eggs, chicken thighs, and leftover rice. '
        'In the freezer ground beef and flounder. Pantry has rice, lentils, olive oil. '
        'Use soon: open sour cream and wilting spinach." '
        'style="font-size:0.85em;resize:vertical;margin-bottom:8px;background:white;"></textarea>'
        '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">'
        '<button onclick="parseInventory()" type="button" '
        'style="padding:6px 16px;font-size:0.82em;background:var(--brown,#8b4513);'
        'color:white;border:none;border-radius:8px;cursor:pointer;font-family:inherit;">'
        '&#10003; Parse &amp; fill sections</button>'
        '<div id="inv-parse-status" style="font-size:0.78em;color:#27ae60;min-height:14px;"></div>'
        '</div></div>'

        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">'
        '<div>'
        '<label>Fridge</label>'
        '<textarea id="inv-fridge" rows="5" placeholder="chicken thighs, eggs, milk, leftover rice..."'
        ' style="font-size:0.85em;resize:vertical;">'
        + escape(inv.get("fridge","")) + '</textarea></div>'
        '<div>'
        '<label>Freezer</label>'
        '<textarea id="inv-freezer" rows="5" placeholder="ground beef, flounder, frozen peas..."'
        ' style="font-size:0.85em;resize:vertical;">'
        + escape(inv.get("freezer","")) + '</textarea></div>'
        '<div>'
        '<label>Pantry</label>'
        '<textarea id="inv-pantry" rows="5" placeholder="rice, lentils, olive oil, canned tomatoes..."'
        ' style="font-size:0.85em;resize:vertical;">'
        + escape(inv.get("pantry","")) + '</textarea></div>'
        '</div>'
        '<div style="margin-top:10px;">'
        '<label style="color:var(--crimson,#8b1a1a);">&#9650; Use soon (priority ingredients)</label>'
        '<input type="text" id="inv-use-soon" placeholder="spinach, ground beef in fridge, open sour cream..."'
        ' value="' + escape(inv.get("use_soon","")) + '" style="max-width:100%;">'
        '</div>'
        '<div id="inv-status" style="font-size:0.78em;color:#27ae60;margin-top:6px;min-height:16px;"></div>'
        '</div>'
    )

    # ── 7-day grid ────────────────────────────────────────────────────────────
    grid_rows = ""
    # Header row
    header_cells = "<td style='width:90px;background:var(--parchment);font-size:0.72em;font-weight:700;color:var(--ink-faint);padding:8px;'></td>"
    for i, day in enumerate(ordered_days):
        day_date = ws + timedelta(days=i)
        is_today = (day_date == date.today())
        day_color = CHILD_COLORS.get(day, "#555")
        bg = "var(--ink)" if is_today else "var(--parchment)"
        fg = "var(--gold-light)" if is_today else day_color
        header_cells += (
            f'<td style="text-align:center;background:{bg};padding:8px 4px;min-width:120px;">'
            f'<div style="font-weight:700;font-size:0.82em;color:{fg};">{escape(day)}</div>'
            f'<div style="font-size:0.72em;color:{"rgba(245,234,216,0.6)" if is_today else "var(--ink-faint)"};">'
            f'{day_date.strftime("%b %d")}</div>'
            f'<button id="swap-btn-{escape(day)}" onclick="activateSwap(\'{escape(day)}\')"'
            f' title="Swap {escape(day)} with another day"'
            f' style="margin-top:4px;font-size:0.65em;padding:2px 6px;border-radius:4px;'
            f'border:1px solid {"rgba(245,234,216,0.3)" if is_today else "var(--border)"};'
            f'background:transparent;color:{"rgba(245,234,216,0.7)" if is_today else "var(--ink-faint)"};'
            f'cursor:pointer;">&#8644;</button>'
            f'</td>'
        )
    grid_rows += f'<tr>{header_cells}</tr>'

    # Meal slot rows
    for slot in MEAL_SLOTS:
        slot_label = MEAL_SLOT_LABELS[slot]
        slot_bg = {
            "breakfast": "#fafaf7",
            "lunch":     "white",
            "dinner":    "#fafaf7",
            "dessert":   "#fff8f0",
            "snacks":    "white",
            "dad_lunch": "#f5f0f8",
        }.get(slot, "white")
        cells = (
            f'<td style="background:var(--parchment);padding:6px 8px;'
            f'font-size:0.72em;font-weight:700;color:var(--ink-faint);'
            f'white-space:nowrap;border-right:2px solid var(--border);">'
            f'{escape(slot_label)}</td>'
        )
        for day in ordered_days:
            # Editor saves plain strings via /meal-save-plan (recipe links are
            # set by Lorenzo, not the grid).  Show only the display text — if
            # Lauren manually edits a linked slot here it'll drop the recipe
            # link on save, which is the documented Phase-2 trade-off.
            val = slot_display_text(days_data.get(day, {}).get(slot, ""))
            cells += (
                f'<td style="padding:3px;background:{slot_bg};border-bottom:1px solid var(--border-light);">'
                f'<textarea data-day="{escape(day)}" data-slot="{escape(slot)}"'
                f' oninput="cellChanged(this)"'
                f' style="width:100%;min-height:52px;border:none;outline:none;'
                f'background:transparent;font-size:0.78em;font-family:inherit;'
                f'resize:vertical;padding:4px;color:var(--ink);">'
                f'{escape(val)}'
                f'</textarea></td>'
            )
        grid_rows += f'<tr>{cells}</tr>'

    # Boys Help row
    help_cells = (
        f'<td style="background:var(--parchment);padding:6px 8px;'
        f'font-size:0.72em;font-weight:700;color:#92400e;'
        f'white-space:nowrap;border-right:2px solid var(--border);">'
        f'👦 Boys Help</td>'
    )
    for day in ordered_days:
        val = days_data.get(day, {}).get("boys_help", "")
        help_cells += (
            f'<td style="padding:3px;background:#fefce8;border-bottom:1px solid var(--border-light);">'
            f'<textarea data-day="{escape(day)}" data-slot="boys_help"'
            f' oninput="cellChanged(this)"'
            f' style="width:100%;min-height:52px;border:none;outline:none;'
            f'background:transparent;font-size:0.78em;font-family:inherit;'
            f'resize:vertical;padding:4px;color:#78350f;"'
            f' placeholder="e.g. JP: chop veg · Joseph: set table · Michael: fill water">'
            f'{escape(val)}'
            f'</textarea></td>'
        )
    grid_rows += f'<tr>{help_cells}</tr>'

    grocery_raw      = json.dumps(plan.get("grocery_gaps", []))
    prep_notes_raw   = json.dumps(plan.get("prep_notes", {}))
    constraints_val  = plan.get("constraints", "")

    body = (
        top_nav() +
        render_status_message(status) +

        # Header
        '<div style="display:flex;align-items:flex-start;justify-content:space-between;'
        'flex-wrap:wrap;gap:8px;margin-bottom:8px;padding-top:4px;">'
        '<div>'
        '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        'font-size:2rem;font-weight:600;color:var(--ink);line-height:1.1;">Meal Planner</div>'
        '<div style="display:flex;align-items:center;gap:8px;margin-top:4px;flex-wrap:wrap;">'
        f'<input type="date" id="week-date-picker" value="{ws.isoformat()}"'
        f' onchange="jumpToWeek(this.value)"'
        f' style="font-size:0.82em;padding:4px 8px;border:1.5px solid var(--border);'
        f'border-radius:8px;background:var(--parchment);color:var(--ink);font-family:inherit;'
        f'cursor:pointer;">'
        f'<span style="font-size:0.75em;color:var(--ink-faint);">{escape(week_label)}</span>'
        '</div>'
        '</div>'

        # Week nav + outputs
        '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:6px;">'
        f'<a href="/meals?week={escape(prev_week)}" class="link-button" style="font-size:0.82em;">&larr;</a>'
        f'<a href="/meals?week={escape(next_week)}" class="link-button" style="font-size:0.82em;">&rarr;</a>'
        '<button onclick="savePlan()" style="padding:7px 14px;font-size:0.82em;">Save plan</button>'
        '<a href="/lorenzo" style="padding:7px 14px;font-size:0.82em;background:#8b3a1a;color:white;border-radius:8px;text-decoration:none;font-weight:600;white-space:nowrap;">&#127860; Ask Lorenzo</a>'
        '<button onclick="printFridge()" style="padding:7px 14px;font-size:0.82em;background:var(--parchment);color:var(--ink);border:1.5px solid var(--border);">&#128438; Fridge card</button>'
        '<button onclick="viewGrocery()" style="padding:7px 14px;font-size:0.82em;background:var(--parchment);color:var(--ink);border:1.5px solid var(--border);">&#128722; Grocery list</button>'
        '<button onclick="viewPrepSchedule()" style="padding:7px 14px;font-size:0.82em;background:var(--parchment);color:var(--ink);border:1.5px solid var(--border);">&#9200; Prep schedule</button>'
        + (f'<button onclick="aiMealPlan(this,\'{escape(wk)}\')" style="padding:7px 14px;font-size:0.82em;background:var(--parchment);color:var(--ink);border:1.5px solid var(--border);">✨ AI meal plan</button>'
           f'<div id="ai-meal-result" style="display:none;width:100%;margin-top:8px;padding:12px;background:white;border-radius:10px;border:1px solid var(--border-light);"></div>'
           f'<script>function aiMealPlan(btn,wk){{btn.disabled=true;btn.textContent="\u2728 Thinking\u2026";'
           f'var r=document.getElementById("ai-meal-result");r.style.display="block";'
           f'r.innerHTML="<span style=\'color:var(--ink-faint);font-size:0.85em;\'>Asking Claude for meal ideas\u2026</span>";'
           f'fetch("/ai-meal-plan",{{method:"POST",headers:{{"Content-Type":"application/x-www-form-urlencoded"}},'
           f'body:"week_key="+encodeURIComponent(wk)}}).then(function(x){{return x.json();}}).then(function(d){{'
           f'r.innerHTML=d.html||"<p>No response.</p>";btn.disabled=false;btn.textContent="\u2728 AI meal plan";}}).catch(function(){{'
           f'r.innerHTML="<p style=\'color:#ef4444;\'>Error.</p>";btn.disabled=false;}});}}'
           f'</script>'
           if _api_key else '')
        + '</div></div>'

        # Cycle phase context strip (if available)
        + (f'<div style="background:var(--ink);border-radius:10px;padding:10px 14px;'
           f'margin-bottom:12px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">'
           f'<span style="font-size:0.78em;color:var(--gold-light);">Cycle phase: <strong>{escape(cycle_phase)}</strong></span>'
           f'<span style="font-size:0.78em;color:rgba(245,234,216,0.5);">|</span>'
           f'<span style="font-size:0.78em;color:rgba(245,234,216,0.65);">Capacity: {escape(capacity) or "not set"}</span>'
           f'<span style="font-size:0.78em;color:rgba(245,234,216,0.5);">|</span>'
           f'<span style="font-size:0.78em;color:rgba(245,234,216,0.5);">Nutrition suggestion: {_cycle_nutrition_hint(cycle_phase)}</span>'
           f'</div>'
           if cycle_phase else "") +

        # AI status
        '<div id="ai-status" style="font-size:0.82em;color:var(--gold);min-height:20px;margin-bottom:8px;"></div>' +

        # Inventory section
        inv_section +

        # Grid
        '<div class="section-cap" style="margin-top:20px;">Weekly meal plan</div>'
        '<div class="card" style="padding:0;overflow:hidden;">'
        '<div style="overflow-x:auto;">'
        f'<table style="border-collapse:collapse;width:100%;min-width:{90 + 7*130}px;" id="meal-grid">'
        f'<tbody>{grid_rows}</tbody>'
        '</table></div>'
        '<div style="padding:8px 14px;background:var(--parchment);border-top:1px solid var(--border);'
        'display:flex;align-items:center;gap:10px;">'
        '<span id="grid-status" style="font-size:0.78em;color:#27ae60;"></span>'
        '<span style="font-size:0.72em;color:var(--ink-faint);margin-left:auto;">Changes save automatically</span>'
        '</div></div>'

        # ── AI Edit Chat panel ────────────────────────────────────────────────
        + (
        '<div class="section-cap" style="margin-top:20px;">✦ Tell Claude what to change</div>'
        '<div class="card" style="padding:14px 16px;">'
        '<div style="font-size:0.78em;color:var(--ink-faint);margin-bottom:10px;line-height:1.5;">'
        'Type any instruction — move meals, set constraints, request a specific dish, note a shopping day, flag prep requirements. Claude will update the plan.'
        '</div>'
        '<div style="display:flex;gap:8px;align-items:flex-end;">'
        '<textarea id="meal-chat-input" rows="2"'
        ' placeholder="e.g. \'Move Monday dinner to Wednesday\' · \'I won\'t have chicken until Saturday\' · \'Put the brine reminder on Tuesday for Wednesday\'s chicken\'"'
        ' style="flex:1;padding:10px;border:1.5px solid var(--border);border-radius:8px;'
        'font-size:0.85em;font-family:inherit;resize:vertical;background:white;color:var(--ink);"></textarea>'
        '<button onclick="sendMealChat()" style="padding:10px 16px;font-size:0.85em;white-space:nowrap;">Send ✦</button>'
        '</div>'
        '<div id="meal-chat-status" style="font-size:0.78em;color:var(--gold);min-height:18px;margin-top:6px;"></div>'
        '</div>'
        if _api_key else '') +

        # ── Constraints / standing notes ──────────────────────────────────────
        '<div class="section-cap" style="margin-top:16px;">Standing notes for AI</div>'
        '<div class="card" style="padding:14px 16px;">'
        '<div style="font-size:0.78em;color:var(--ink-faint);margin-bottom:8px;">'
        'Saved notes included in every AI meal plan and edit. Examples: shopping day, prep requirements, family constraints.'
        '</div>'
        f'<textarea id="meal-constraints" rows="3"'
        f' placeholder="e.g. Shopping day: Saturday (chicken, beef not available until then). Brined chicken: start brine 24h before serving. No nuts — Michael allergy."'
        f' oninput="constraintsChanged()"'
        f' style="width:100%;padding:10px;border:1.5px solid var(--border);border-radius:8px;'
        f'font-size:0.82em;font-family:inherit;resize:vertical;background:white;color:var(--ink);box-sizing:border-box;">'
        f'{escape(constraints_val)}'
        f'</textarea>'
        '<div style="display:flex;align-items:center;gap:10px;margin-top:8px;">'
        '<button onclick="saveConstraints()" style="padding:7px 14px;font-size:0.82em;background:var(--parchment);color:var(--ink);border:1.5px solid var(--border);">Save notes</button>'
        '<span id="constraints-status" style="font-size:0.78em;color:#27ae60;"></span>'
        '</div>'
        '</div>' +

        # Modals placeholder
        '<div id="modal-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:3000;">'
        '<div id="modal-content" style="background:white;border-radius:16px;max-width:680px;'
        'width:90%;max-height:80vh;overflow-y:auto;margin:5vh auto;padding:24px;">'
        '<div id="modal-body"></div>'
        '<div style="margin-top:16px;text-align:right;">'
        '<button onclick="document.getElementById(\'modal-overlay\').style.display=\'none\'" '
        'style="padding:8px 16px;font-size:0.85em;background:var(--parchment);color:var(--ink);border:1.5px solid var(--border);">Close</button>'
        '</div></div></div>' +

        # JS — data block + external static file (avoids Python string escaping nightmares)
        f'<script id="meal-data" type="application/json">'
        f'{{"week":{json.dumps(wk)},"grocery_gaps":{grocery_raw},"prep_notes":{prep_notes_raw},"constraints":{json.dumps(constraints_val)}}}'
        f'</script>'

        # External JS — all logic lives in static/meals.js
        '<script src="/static/meals.js"></script>'

    )

    return html_page("Meal Planner", body)


def _cycle_nutrition_hint(phase: str) -> str:
    hints = {
        "Menstrual":    "iron-rich meals (red meat, lentils, spinach)",
        "Follicular":   "lean proteins, fresh vegetables",
        "Ovulatory":    "balanced protein + carbs",
        "Early Luteal": "maintain structure, consistent meals",
        "Late Luteal":  "magnesium (dark chocolate, nuts), complex carbs",
    }
    return hints.get(phase, "balanced whole foods")


# ---------------------------------------------------------------------------
# Print page — landscape fridge card
# ---------------------------------------------------------------------------

def render_meal_print_page(week_key: str = None) -> str:
    wk = week_key or _planning_week_key()
    plan = load_meal_plan(wk)
    ws   = date.fromisoformat(wk) if len(wk) == 10 else _week_start()
    days_data = plan.get("days", {})

    week_label = ws.strftime("Week of %B %d, %Y")

    header_row = "<th style='width:80pt;border:1px solid #ccc;padding:5pt;background:#f5ead8;font-size:8pt;color:#888;'>Meal</th>"
    for day in DAYS:
        day_date = ws + timedelta(days=DAYS.index(day))
        is_fri = (day == "Friday")
        bg = "#fdf0ef" if is_fri else "#f9f7f4"
        header_row += f"<th style='border:1px solid #ccc;padding:5pt;background:{bg};font-size:8.5pt;color:#1a3870;'>{day}<br><span style='font-weight:400;font-size:7pt;color:#aaa;'>{day_date.strftime('%b %d')}</span></th>"

    rows = ""
    for slot in ["breakfast","lunch","dinner","snacks"]:
        label = MEAL_SLOT_LABELS[slot]
        cells = f"<td style='border:1px solid #ddd;padding:4pt 5pt;font-size:8pt;font-weight:700;color:#888;background:#fafaf7;white-space:nowrap;'>{label}</td>"
        for day in DAYS:
            val = slot_display_text(days_data.get(day, {}).get(slot, ""))
            is_fri = (day == "Friday")
            bg = "#fdf0ef" if is_fri else "white"
            cells += f"<td style='border:1px solid #ddd;padding:4pt 5pt;font-size:8pt;background:{bg};vertical-align:top;'>{escape(val)}</td>"
        rows += f"<tr>{cells}</tr>"

    # Dessert row
    dessert_vals = {day: slot_display_text(days_data.get(day, {}).get("dessert", "")) for day in DAYS}
    if any(dessert_vals.values()):
        dessert_cells = "<td style='border:1px solid #ddd;padding:4pt 5pt;font-size:8pt;font-weight:700;color:#8b4513;background:#fff8f0;white-space:nowrap;'>Dessert</td>"
        for day in DAYS:
            val = dessert_vals[day]
            is_fri = (day == "Friday")
            bg = "#fdf0ef" if is_fri else ("#fff8f0" if val else "white")
            dessert_cells += f"<td style='border:1px solid #ddd;padding:4pt 5pt;font-size:8pt;background:{bg};vertical-align:top;color:#8b4513;font-style:italic;'>{escape(val)}</td>"
        rows += f"<tr>{dessert_cells}</tr>"

    # Dad's lunches row
    dad_cells = "<td style='border:1px solid #ddd;padding:4pt 5pt;font-size:8pt;font-weight:700;color:#6b1a8a;background:#faf5ff;white-space:nowrap;'>Dad's Lunch</td>"
    for day in DAYS:
        val = slot_display_text(days_data.get(day, {}).get("dad_lunch", ""))
        dad_cells += f"<td style='border:1px solid #ddd;padding:4pt 5pt;font-size:8pt;background:{'#faf5ff' if val else 'white'};vertical-align:top;color:#6b1a8a;'>{escape(val)}</td>"
    rows += f"<tr>{dad_cells}</tr>"

    prep_notes = plan.get("prep_notes", {})
    if prep_notes:
        prep_cells = "<td style='border:1px solid #ddd;padding:4pt 5pt;font-size:8pt;font-weight:700;color:#1a6050;background:#f0fdf9;white-space:nowrap;'>Prep</td>"
        for day in DAYS:
            note = prep_notes.get(day, "").strip()
            prep_cells += f"<td style='border:1px solid #ddd;padding:3pt 5pt;font-size:7.5pt;background:#f0fdf9;vertical-align:top;color:#1a6050;'>{escape(note)}</td>"
        rows += f"<tr>{prep_cells}</tr>"

    # Helper job assignments row (JP, Joseph, Michael kitchen roles per day)
    helper_vals = {day: days_data.get(day, {}).get("helpers", "").strip() for day in DAYS}
    if any(helper_vals.values()):
        helper_cells = "<td style='border:1px solid #ddd;padding:4pt 5pt;font-size:8pt;font-weight:700;color:#92400e;background:#fffbeb;white-space:nowrap;'>Helpers</td>"
        for day in DAYS:
            val = helper_vals[day]
            bg = "#fffbeb" if val else "white"
            helper_cells += f"<td style='border:1px solid #ddd;padding:3pt 5pt;font-size:7.5pt;background:{bg};vertical-align:top;color:#92400e;'>{escape(val)}</td>"
        rows += f"<tr>{helper_cells}</tr>"

    # Grocery list section — shown below the table
    grocery_gaps = plan.get("grocery_gaps", [])
    grocery_html = ""
    if grocery_gaps:
        items_html = "".join(
            f"<div style='display:inline-flex;align-items:center;gap:5pt;margin:3pt 6pt 3pt 0;'>"
            f"<span style='display:inline-block;width:10pt;height:10pt;border:1pt solid #888;"
            f"border-radius:2pt;flex-shrink:0;'></span>"
            f"<span style='font-size:8pt;'>{escape(item)}</span>"
            f"</div>"
            for item in grocery_gaps
        )
        grocery_html = (
            "<div style='margin-top:18pt;border-top:2pt solid #1a3870;padding-top:10pt;page-break-inside:avoid;'>"
            "<div style='font-family:Georgia,serif;font-size:10pt;font-weight:600;color:#1a3870;"
            "margin-bottom:8pt;'>Grocery List</div>"
            f"<div style='display:flex;flex-wrap:wrap;'>{items_html}</div>"
            "</div>"
        )

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Meal Plan \u2014 {escape(week_label)}</title>"
        "<style>"
        "*{box-sizing:border-box;margin:0;padding:0;}"
        "body{font-family:Georgia,'Times New Roman',serif;background:white;color:#111;}"
        ".no-print{display:none;}"
        "@media screen{body{padding:16px;}.no-print{display:block;}}"
        "@media print{"
        "  @page{margin:0.4in;size:landscape;}"
        "  .no-print{display:none !important;}"
        "  body{-webkit-print-color-adjust:exact;print-color-adjust:exact;}"
        "}"
        "</style>"
        "<script>"
        "function doPrint(){"
        "  try{ window.print(); }"
        "  catch(e){ try{ document.execCommand('print'); }catch(e2){} }"
        "}"
        "var _iOS = /iPad|iPhone|iPod/.test(navigator.userAgent);"
        "window.onload = function(){"
        "  if(_iOS){"
        "    document.getElementById('ios-tip').style.display='flex';"
        "    document.getElementById('print-btn-row').style.display='none';"
        "  }"
        "};"
        "</script>"
        "</head><body>"
        "<div class='no-print' style='background:#1c1610;color:#f5ead8;padding:10px 16px;"
        "font-family:sans-serif;font-size:13px;margin-bottom:16px;border-radius:0 0 8px 8px;'>"
        "  <div id='print-btn-row' style='display:flex;gap:12px;align-items:center;flex-wrap:wrap;'>"
        "    <button onclick='doPrint()' style='background:#c49020;color:#1c1610;border:none;"
        "    padding:10px 20px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:700;'>&#128438; Print / Save PDF</button>"
        "    <a href='/meals' style='color:#f5ead8;font-size:13px;'>&#8592; Meal Planner</a>"
        "  </div>"
        "  <div id='ios-tip' style='display:none;flex-direction:column;gap:8px;'>"
        "    <div style='font-size:14px;font-weight:700;color:#c49020;'>&#128247; iPhone printing steps:</div>"
        "    <ol style='margin:0 0 0 18px;line-height:1.8;font-size:13px;'>"
        "      <li>Rotate your phone to <strong>landscape</strong> &#8635;</li>"
        "      <li>Tap the <strong>Share</strong> button &#8679; at the bottom</li>"
        "      <li>Tap <strong>Print</strong></li>"
        "    </ol>"
        "    <a href='/meals' style='color:#f5ead8;font-size:12px;margin-top:4px;'>&#8592; Back to Meal Planner</a>"
        "  </div>"
        "</div>"
        "<div style='display:flex;align-items:baseline;justify-content:space-between;padding:0 0 10pt;'>"
        "<div style='font-family:Georgia,serif;font-size:14pt;font-weight:600;color:#1a3870;font-style:italic;'>Sancta Familia</div>"
        f"<div style='font-size:10pt;color:#888;'>{escape(week_label)}</div>"
        "</div>"
        "<table style='border-collapse:collapse;width:100%;'>"
        f"<thead><tr>{header_row}</tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
        f"{grocery_html}"
        "</body></html>"
    )


# ---------------------------------------------------------------------------
# Pre-loaded recipe library
# ---------------------------------------------------------------------------

DEFAULT_RECIPES = [
    {
        "id": "r001",
        "name": "Brined Roast Chicken",
        "ingredients": "Whole chicken (4-5 lb), 1/4 cup kosher salt, 1/4 cup sugar, water, garlic cloves, fresh herbs (thyme, rosemary), butter, lemon",
        "instructions": "Brine chicken in salt/sugar/water 8-24 hrs. Pat dry. Rub with butter and herbs. Roast at 425°F 1-1.5 hrs until internal temp 165°F. Rest 10 min before carving.",
        "tags": ["chicken", "anchor-meal", "family-favorite", "Lent-free"],
        "prep_time": "20 min + 8 hr brine",
        "created": "2026-01-01",
    },
    {
        "id": "r002",
        "name": "Sunday Roast Beef",
        "ingredients": "3-4 lb chuck or rump roast, olive oil, salt, pepper, garlic, onion, carrots, potatoes, beef broth, fresh rosemary",
        "instructions": "Sear roast on all sides in hot oil. Transfer to roasting pan with vegetables and broth. Roast at 325°F 3-4 hrs until fork-tender. Rest 15 min. Use drippings for gravy.",
        "tags": ["red-meat", "anchor-meal", "Sunday", "high-carb"],
        "prep_time": "20 min",
        "created": "2026-01-01",
    },
    {
        "id": "r003",
        "name": "Friday Fish Fry (Fried Flounder)",
        "ingredients": "Flounder fillets, buttermilk, cornmeal, flour, Old Bay seasoning, salt, pepper, oil for frying, lemon wedges, tartar sauce",
        "instructions": "Soak fillets in buttermilk 30 min. Mix cornmeal, flour, Old Bay. Dredge fish. Fry in 350°F oil 3-4 min per side until golden. Drain on paper towels.",
        "tags": ["fish", "Friday", "Lent-safe", "anchor-meal"],
        "prep_time": "15 min + 30 min soak",
        "created": "2026-01-01",
    },
    {
        "id": "r004",
        "name": "Chicken Chili (Batch Soup)",
        "ingredients": "2 lbs ground or shredded chicken, 2 cans white beans, 1 can green chiles, chicken broth, onion, garlic, cumin, chili powder, sour cream, shredded cheese",
        "instructions": "Sauté onion and garlic. Add chicken, cook through. Add beans, chiles, broth, and spices. Simmer 30 min. Serve with sour cream and cheese. Freezes well.",
        "tags": ["chicken", "soup", "batch-cook", "easy"],
        "prep_time": "15 min",
        "created": "2026-01-01",
    },
    {
        "id": "r005",
        "name": "Tomato Soup",
        "ingredients": "2 cans crushed tomatoes, 1 cup chicken or vegetable broth, 1/2 cup cream, onion, garlic, butter, fresh basil, salt, pepper, sugar (pinch)",
        "instructions": "Sauté onion and garlic in butter. Add tomatoes and broth, simmer 20 min. Blend smooth. Add cream and basil. Season to taste. Serve with grilled cheese.",
        "tags": ["vegetarian", "soup", "batch-cook", "Friday", "Lent-safe", "Michael-friendly"],
        "prep_time": "10 min",
        "created": "2026-01-01",
    },
    {
        "id": "r006",
        "name": "Lentil Soup",
        "ingredients": "1.5 cups red lentils, 1 can diced tomatoes, onion, garlic, carrots, celery, cumin, turmeric, smoked paprika, lemon juice, chicken or vegetable broth",
        "instructions": "Sauté onion, garlic, carrots, celery. Add spices, cook 1 min. Add lentils, tomatoes, broth. Simmer 25-30 min until lentils dissolve. Finish with lemon juice.",
        "tags": ["legume", "soup", "batch-cook", "Friday", "Lent-safe", "iron-rich"],
        "prep_time": "15 min",
        "created": "2026-01-01",
    },
    {
        "id": "r007",
        "name": "Beef Stew (Batch)",
        "ingredients": "2 lbs stew beef, potatoes, carrots, celery, onion, garlic, beef broth, tomato paste, Worcestershire, flour, rosemary, thyme",
        "instructions": "Coat beef in flour, brown in batches. Sauté vegetables. Add beef, broth, tomato paste, herbs. Simmer 2-3 hrs low and slow until beef is tender. Thickens as it cools.",
        "tags": ["red-meat", "soup", "batch-cook", "high-carb", "Sunday"],
        "prep_time": "30 min",
        "cook_time": "2 hr 30 min",
        "created": "2026-01-01",
    },
    {
        "id": "r008",
        "name": "Black-Eyed Pea Jambalaya",
        "ingredients": "2 cans black-eyed peas, 1 lb andouille or chicken sausage, rice, onion, bell pepper, celery, garlic, diced tomatoes, chicken broth, Cajun seasoning, bay leaf",
        "instructions": "Brown sausage. Sauté the holy trinity (onion, bell pepper, celery). Add garlic, tomatoes, peas, broth, rice. Season generously. Simmer covered 20 min until rice is cooked.",
        "tags": ["legume", "poultry", "high-carb", "one-pot"],
        "prep_time": "20 min",
        "created": "2026-01-01",
    },
    {
        "id": "r009",
        "name": "Sardine Sandwiches (Friday Lunch)",
        "ingredients": "1 can sardines in olive oil, mayo, Dijon mustard, lemon juice, celery, red onion, salt, pepper, bread or crackers",
        "instructions": "Drain sardines. Mix with mayo, mustard, lemon, celery, onion. Season. Serve on good bread or with crackers. Michael version: just butter and sardines, no mix-ins.",
        "tags": ["fish", "Friday", "Lent-safe", "quick", "dad-lunch"],
        "prep_time": "5 min",
        "created": "2026-01-01",
    },
    {
        "id": "r010",
        "name": "Sheet Pan Chicken Thighs with Vegetables",
        "ingredients": "6-8 bone-in chicken thighs, potatoes or sweet potatoes, broccoli or green beans, olive oil, garlic powder, paprika, Italian seasoning, salt, pepper",
        "instructions": "Toss vegetables in oil and seasoning. Season chicken. Arrange on sheet pan, chicken skin-up. Roast at 425°F 35-40 min until chicken is golden and cooked through.",
        "tags": ["chicken", "easy", "one-pan", "high-carb", "family-favorite"],
        "prep_time": "15 min",
        "created": "2026-01-01",
    },
    {
        "id": "r011",
        "name": "Grilled Cheese + Tomato Soup",
        "ingredients": "Good bread, American or cheddar cheese, butter. Serve with tomato soup.",
        "instructions": "Butter outside of bread. Fill with cheese. Cook in skillet over medium heat until golden and melted, 3-4 min per side. Cut diagonally. Serve with soup.",
        "tags": ["vegetarian", "Friday", "Lent-safe", "Michael-friendly", "James-friendly", "quick"],
        "prep_time": "10 min",
        "created": "2026-01-01",
    },
    {
        "id": "r012",
        "name": "Scrambled Eggs with Toast",
        "ingredients": "Eggs, butter, salt, pepper, milk (splash), bread for toast",
        "instructions": "Beat eggs with milk. Melt butter in pan over medium-low. Add eggs, stir constantly until just set. Remove from heat slightly early — carryover cooks them. Serve with buttered toast.",
        "tags": ["breakfast", "quick", "James-friendly", "Michael-friendly", "low-carb"],
        "prep_time": "8 min",
        "created": "2026-01-01",
    },
    {
        "id": "r013",
        "name": "Overnight Oats / Morning Oatmeal",
        "ingredients": "Rolled oats, milk or water, honey or maple syrup, cinnamon, fruit (banana, berries, apple)",
        "instructions": "Hot: simmer oats in milk/water 5 min. Overnight: combine oats and milk in jar, refrigerate. Top with fruit and honey. James version: soft, with mashed banana.",
        "tags": ["breakfast", "James-friendly", "batch-prep", "low-effort"],
        "prep_time": "5 min (or overnight)",
        "created": "2026-01-01",
    },
    {
        "id": "r014",
        "name": "Roast Chicken Tacos (Leftover Night)",
        "ingredients": "Leftover roast chicken, corn or flour tortillas, shredded cheese, sour cream, salsa, lettuce or cabbage, lime, cilantro (optional)",
        "instructions": "Shred leftover chicken. Warm tortillas. Set up taco bar. Michael version: plain chicken in tortilla with cheese only.",
        "tags": ["chicken", "leftover", "Tuesday", "quick", "Michael-friendly"],
        "prep_time": "10 min",
        "created": "2026-01-01",
    },
    {
        "id": "r015",
        "name": "Baked Salmon with Rice",
        "ingredients": "Salmon fillets, olive oil, garlic, lemon, dill or parsley, salt, pepper. Serve with white rice and steamed broccoli.",
        "instructions": "Season salmon with oil, garlic, lemon, dill. Bake at 400°F 12-15 min until flakes easily. Serve over rice with a vegetable.",
        "tags": ["fish", "Friday", "Lent-safe", "high-carb", "healthy"],
        "prep_time": "10 min",
        "created": "2026-01-01",
    },
]


def render_recipe_import_preview(name: str, ingredients: str, instructions: str,
                                 tags: list, prep_time: str, image_url: str = "",
                                 source_note: str = "") -> str:
    """Show parsed-recipe preview after import — user can review/edit then Save or Cancel."""
    from ui_helpers import html_page, top_nav
    tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags or "")
    img_block = (
        f'<div style="margin:0 0 14px;"><img src="{escape(image_url)}" alt="" '
        f'style="width:100%;max-height:300px;object-fit:cover;border-radius:8px;"></div>'
    ) if image_url else ""
    note_block = (
        f'<p style="font-size:0.78em;color:var(--ink-faint);margin:0 0 12px;">{escape(source_note)}</p>'
    ) if source_note else ""
    body = (
        top_nav() +
        '<div style="max-width:640px;margin:0 auto;">'
        '<h2 style="font-family:\'Cormorant Garamond\',Georgia,serif;font-size:1.6rem;font-weight:600;'
        'color:var(--ink);margin-bottom:6px;">Review imported recipe</h2>'
        '<p style="font-size:0.85em;color:var(--ink-muted);margin-bottom:16px;">'
        'Edit anything that looks wrong, then save it to your library. '
        'Nothing is saved until you click <b>Save recipe</b>.</p>'
        + note_block +
        '<div class="card">'
        + img_block +
        '<form method="POST" action="/recipe-save" enctype="multipart/form-data">'
        f'<input type="hidden" name="image_url" value="{escape(image_url)}">'
        '<label>Name</label>'
        f'<input type="text" name="name" required value="{escape(name)}" style="margin-bottom:10px;">'
        '<label>Prep time</label>'
        f'<input type="text" name="prep_time" value="{escape(prep_time)}" style="margin-bottom:10px;">'
        '<label>Tags <span style="font-weight:400;font-size:0.85em;color:#888;">(comma-separated)</span></label>'
        f'<input type="text" name="tags" value="{escape(tags_str)}" style="margin-bottom:10px;">'
        '<label>Replace dish photo <span style="font-weight:400;font-size:0.85em;color:#888;">(optional)</span></label>'
        '<input type="file" name="dish_photo" accept="image/*" style="margin-bottom:10px;font-size:0.85em;">'
        '<label>Ingredients</label>'
        f'<textarea name="ingredients" rows="8" style="margin-bottom:10px;font-family:inherit;">{escape(ingredients)}</textarea>'
        '<label>Instructions</label>'
        f'<textarea name="instructions" rows="10" style="margin-bottom:14px;font-family:inherit;">{escape(instructions)}</textarea>'
        '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
        '<button type="submit" style="padding:10px 22px;background:var(--ink);color:var(--gold-light);'
        'border:none;border-radius:8px;font-family:inherit;font-size:0.9em;cursor:pointer;font-weight:600;">Save recipe</button>'
        '<a href="/recipes" style="padding:10px 18px;background:transparent;border:1.5px solid var(--border);'
        'border-radius:8px;font-family:inherit;font-size:0.9em;color:var(--ink-muted);text-decoration:none;'
        'display:inline-block;">Cancel</a>'
        '</div></form>'
        '</div></div>'
    )
    return html_page("Review recipe", body)


def _seed_default_recipes():
    """Only seed if the recipe file is empty or missing."""
    recipes = load_recipes()
    if not recipes:
        save_recipes(DEFAULT_RECIPES)


# ---------------------------------------------------------------------------
# Recipes page
# ---------------------------------------------------------------------------

def render_recipes_page(status: str = "") -> str:
    from ui_helpers import html_page, render_status_message, top_nav
    _seed_default_recipes()
    recipes = load_recipes()
    # Defensive: silently drop any malformed (non-dict) entries so a single
    # corrupt row can't blank-page the entire library.
    recipes = [r for r in recipes if isinstance(r, dict)]

    # Collect all unique tags for filter chips
    all_tags = sorted(set(t for r in recipes for t in r.get("tags", []) if isinstance(t, str)))

    # Recipe cards
    cards = ""
    for r in recipes:
        rid   = escape(r.get("id",""))
        name  = escape(r.get("name",""))
        ingr  = escape(r.get("ingredients",""))
        instr = escape(r.get("instructions",""))
        prep  = escape(r.get("prep_time",""))
        tags  = r.get("tags", [])
        img   = escape(r.get("image","") or "")
        tag_pills = "".join(
            f'<span class="pill pill-{_tag_class(t)}" style="font-size:0.7em;margin-right:4px;">{escape(t)}</span>'
            for t in tags[:6]
        )
        thumb = (
            f'<div style="margin:-14px -14px 10px;height:160px;background:#f3eee4 center/cover no-repeat;'
            f'background-image:url(\'{img}\');border-radius:10px 10px 0 0;"></div>'
        ) if img else ""
        big_img = (
            f'<div style="margin:0 0 12px;"><img src="{img}" alt="" '
            f'style="width:100%;max-height:340px;object-fit:cover;border-radius:8px;"></div>'
        ) if img else ""
        cards += (
            f'<div class="card" data-tags="{escape(",".join(tags))}" style="margin-bottom:14px;">'
            f'{thumb}'
            f'<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:8px;">'
            f'<div style="font-weight:700;font-size:1.05em;color:var(--ink);">{name}</div>'
            f'<div style="display:flex;gap:6px;flex-shrink:0;">'
            f'<button onclick="toggleRecipe(\'{rid}\')" '
            f'style="padding:5px 12px;font-size:0.78em;border-radius:8px;border:1.5px solid var(--border);'
            f'background:var(--parchment);color:var(--ink);cursor:pointer;font-family:inherit;">Details</button>'
            f'<button onclick="editRecipe(\'{rid}\')" '
            f'style="padding:5px 12px;font-size:0.78em;border-radius:8px;border:1.5px solid var(--border);'
            f'background:var(--parchment);color:var(--brown);cursor:pointer;font-family:inherit;">Edit</button>'
            f'<form method="POST" action="/recipe-delete" style="display:inline;">'
            f'<input type="hidden" name="id" value="{rid}">'
            f'<button type="submit" '
            f'style="padding:5px 12px;font-size:0.78em;border-radius:8px;border:1.5px solid #e8d0d0;'
            f'background:#fff5f5;color:#8b1a1a;cursor:pointer;font-family:inherit;" '
            f'onclick="return confirm(\'Delete this recipe?\')">Delete</button>'
            f'</form></div></div>'
            f'<div style="margin-bottom:8px;">{tag_pills}</div>'
            f'<div style="font-size:0.78em;color:var(--ink-faint);">Prep: {prep}</div>'
            f'<div id="recipe-detail-{rid}" style="display:none;margin-top:12px;border-top:1px solid var(--border-light);padding-top:12px;">'
            f'{big_img}'
            f'<div style="font-size:0.82em;margin-bottom:8px;">'
            f'<div style="font-weight:700;margin-bottom:4px;">Ingredients</div>'
            f'<div style="color:var(--ink-muted);white-space:pre-wrap;">{ingr}</div>'
            f'</div>'
            f'<div style="font-size:0.82em;margin-bottom:12px;">'
            f'<div style="font-weight:700;margin-bottom:4px;">Instructions</div>'
            f'<div style="color:var(--ink-muted);white-space:pre-wrap;">{instr}</div>'
            f'</div>'
            f'</div>'
            # Inline edit form (hidden by default)
            f'<div id="recipe-edit-{rid}" style="display:none;margin-top:12px;border-top:1px solid var(--border-light);padding-top:12px;">'
            f'<form method="POST" action="/recipe-save" enctype="multipart/form-data">'
            f'<input type="hidden" name="id" value="{rid}">'
            f'<label style="font-size:0.75em;">Name</label>'
            f'<input type="text" name="name" value="{name}" style="margin-bottom:8px;">'
            f'<label style="font-size:0.75em;">Prep time</label>'
            f'<input type="text" name="prep_time" value="{prep}" style="margin-bottom:8px;">'
            f'<label style="font-size:0.75em;">Tags (comma-separated)</label>'
            f'<input type="text" name="tags" value="{escape(",".join(tags))}" style="margin-bottom:8px;" '
            f'placeholder="chicken, easy, Friday, Lent-safe">'
            f'<label style="font-size:0.75em;">Dish photo {("(replace current)" if img else "(optional)")}</label>'
            f'<input type="file" name="dish_photo" accept="image/*" style="margin-bottom:4px;font-size:0.8em;">'
            + (f'<label style="display:block;font-size:0.72em;color:var(--ink-faint);margin-bottom:8px;">'
               f'<input type="checkbox" name="remove_image" value="1"> Remove current photo</label>'
               if img else '<div style="margin-bottom:8px;"></div>')
            +
            f'<label style="font-size:0.75em;">Ingredients</label>'
            f'<textarea name="ingredients" rows="4" style="margin-bottom:8px;">{ingr}</textarea>'
            f'<label style="font-size:0.75em;">Instructions</label>'
            f'<textarea name="instructions" rows="5" style="margin-bottom:10px;">{instr}</textarea>'
            f'<div style="display:flex;gap:8px;">'
            f'<button type="submit" '
            f'style="padding:8px 18px;background:var(--ink);color:var(--gold-light);border:none;'
            f'border-radius:8px;font-size:0.85em;font-family:inherit;cursor:pointer;">Save changes</button>'
            f'<button type="button" onclick="editRecipe(\'{rid}\')" '
            f'style="padding:8px 14px;background:transparent;color:var(--ink-muted);border:1.5px solid var(--border);'
            f'border-radius:8px;font-size:0.85em;font-family:inherit;cursor:pointer;">Cancel</button>'
            f'</div></form></div>'
            f'</div>'
        )

    # Add + Import form
    add_form = (
        '<div class="card" id="add-recipe-card" style="margin-bottom:20px;display:none;">'
        '<h3 style="margin-bottom:14px;">Add recipe</h3>'
        # Tabs: Manual / Import
        '<div style="display:flex;gap:0;margin-bottom:16px;border-bottom:2px solid var(--border-light);">'
        '<button onclick="recipeTab(\'manual\')" id="tab-manual" '
        'style="padding:8px 16px;font-size:0.85em;border:none;background:none;'
        'border-bottom:2px solid var(--ink);margin-bottom:-2px;font-family:inherit;'
        'font-weight:700;cursor:pointer;color:var(--ink);">Type it in</button>'
        '<button onclick="recipeTab(\'import\')" id="tab-import" '
        'style="padding:8px 16px;font-size:0.85em;border:none;background:none;'
        'border-bottom:2px solid transparent;margin-bottom:-2px;font-family:inherit;'
        'cursor:pointer;color:var(--ink-muted);">Import</button>'
        '</div>'
        # Manual entry tab
        '<div id="recipe-manual-tab">'
        '<form method="POST" action="/recipe-save" enctype="multipart/form-data" onsubmit="recipeDraftClear()">'
        '<label>Name</label>'
        '<input type="text" id="rc-name" name="name" required placeholder="Recipe name" style="margin-bottom:10px;" oninput="recipeDraftSave()">'
        '<label>Prep time</label>'
        '<input type="text" id="rc-prep" name="prep_time" placeholder="20 min" style="margin-bottom:10px;" oninput="recipeDraftSave()">'
        '<label>Tags <span style="font-weight:400;font-size:0.85em;color:#888;">(comma-separated)</span></label>'
        '<input type="text" id="rc-tags" name="tags" placeholder="chicken, easy, Friday, Lent-safe" style="margin-bottom:10px;" oninput="recipeDraftSave()">'
        '<label>Dish photo <span style="font-weight:400;font-size:0.85em;color:#888;">(optional)</span></label>'
        '<input type="file" name="dish_photo" accept="image/*" style="margin-bottom:10px;font-size:0.85em;">'
        '<label>Ingredients</label>'
        '<textarea id="rc-ingr" name="ingredients" rows="4" placeholder="List all ingredients..." style="margin-bottom:10px;" oninput="recipeDraftSave()"></textarea>'
        '<label>Instructions</label>'
        '<textarea id="rc-inst" name="instructions" rows="5" placeholder="Step-by-step instructions..." style="margin-bottom:12px;" oninput="recipeDraftSave()"></textarea>'
        '<div style="display:flex;gap:8px;">'
        '<button type="submit" style="padding:8px 18px;background:var(--ink);color:var(--gold-light);'
        'border:none;border-radius:8px;font-family:inherit;font-size:0.85em;cursor:pointer;">Save recipe</button>'
        '<button type="button" onclick="recipeDraftClear();document.getElementById(\'add-recipe-card\').style.display=\'none\';'
        'document.getElementById(\'show-add-btn\').style.display=\'inline-block\'" '
        'style="padding:8px 14px;background:transparent;border:1.5px solid var(--border);'
        'border-radius:8px;font-family:inherit;font-size:0.85em;cursor:pointer;color:var(--ink-muted);">Cancel</button>'
        '</div></form></div>'
        # Import tab
        '<div id="recipe-import-tab" style="display:none;">'
        '<form method="POST" action="/recipe-import" enctype="multipart/form-data">'
        '<div style="margin-bottom:14px;">'
        '<label>\U0001f4f8 Photo or PDF of recipe <span style="font-weight:400;font-size:0.85em;color:#888;">(source)</span></label>'
        '<input type="file" name="recipe_photo" accept="image/*,application/pdf,.pdf" '
        'style="margin-bottom:6px;font-size:0.85em;">'
        '<p style="font-size:0.78em;color:var(--ink-faint);margin-top:2px;">Pick from your files, photo library, '
        'or take a new photo — AI will read the ingredients and instructions. PDFs work too.</p>'
        '</div>'
        '<div style="margin-bottom:14px;">'
        '<label>\U0001f37d Dish photo <span style="font-weight:400;font-size:0.85em;color:#888;">(optional, separate from source)</span></label>'
        '<input type="file" name="dish_photo" accept="image/*" '
        'style="margin-bottom:4px;font-size:0.85em;">'
        '<p style="font-size:0.78em;color:var(--ink-faint);margin-top:2px;">A pretty picture of the finished dish to show on the recipe card.</p>'
        '</div>'
        '<div style="margin-bottom:4px;font-size:0.72em;font-weight:700;color:var(--ink-faint);'
        'text-transform:uppercase;letter-spacing:.08em;">Or</div>'
        '<div style="margin-bottom:14px;">'
        '<label>Recipe URL</label>'
        '<input type="url" name="url" placeholder="https://www.seriouseats.com/..." style="margin-bottom:8px;">'
        '<p style="font-size:0.78em;color:var(--ink-faint);margin-top:2px;">Paste any recipe link — '
        'works with Serious Eats, NYT Cooking, AllRecipes, and most blogs.</p>'
        '</div>'
        '<div style="margin-bottom:14px;">'
        '<label>Or paste recipe text</label>'
        '<textarea name="text" rows="5" placeholder="Paste any recipe text, ingredients list, or instructions..." '
        'style="margin-bottom:8px;"></textarea>'
        '</div>'
        '<div style="margin-bottom:14px;">'
        '<label>Recipe name <span style="font-weight:400;font-size:0.85em;color:#888;">(optional — we\'ll grab it from the source if blank)</span></label>'
        '<input type="text" name="name" placeholder="Leave blank to auto-detect" style="margin-bottom:8px;">'
        '</div>'
        '<div id="recipe-import-status" style="font-size:0.82em;color:var(--brown);min-height:18px;margin-bottom:8px;"></div>'
        '<div style="display:flex;gap:8px;">'
        '<button type="submit" style="padding:8px 18px;background:var(--ink);color:var(--gold-light);'
        'border:none;border-radius:8px;font-family:inherit;font-size:0.85em;cursor:pointer;">Import recipe</button>'
        '<button type="button" onclick="document.getElementById(\'add-recipe-card\').style.display=\'none\';'
        'document.getElementById(\'show-add-btn\').style.display=\'inline-block\'" '
        'style="padding:8px 14px;background:transparent;border:1.5px solid var(--border);'
        'border-radius:8px;font-family:inherit;font-size:0.85em;cursor:pointer;color:var(--ink-muted);">Cancel</button>'
        '</div></form>'
        '</div>'
        '</div>'
        # JS for tabs and edit
        '<script>'
        'function recipeTab(tab) {'
        '  document.getElementById("recipe-manual-tab").style.display = tab==="manual"?"block":"none";'
        '  document.getElementById("recipe-import-tab").style.display = tab==="import"?"block":"none";'
        '  document.getElementById("tab-manual").style.borderBottomColor = tab==="manual"?"var(--ink)":"transparent";'
        '  document.getElementById("tab-manual").style.fontWeight = tab==="manual"?"700":"400";'
        '  document.getElementById("tab-manual").style.color = tab==="manual"?"var(--ink)":"var(--ink-muted)";'
        '  document.getElementById("tab-import").style.borderBottomColor = tab==="import"?"var(--ink)":"transparent";'
        '  document.getElementById("tab-import").style.fontWeight = tab==="import"?"700":"400";'
        '  document.getElementById("tab-import").style.color = tab==="import"?"var(--ink)":"var(--ink-muted)";'
        '}'
        'function editRecipe(rid) {'
        '  var ed = document.getElementById("recipe-edit-"+rid);'
        '  var det = document.getElementById("recipe-detail-"+rid);'
        '  if (!ed) return;'
        '  var showing = ed.style.display !== "none";'
        '  ed.style.display = showing ? "none" : "block";'
        '  if (det) det.style.display = "none";'
        '}'
        'function toggleRecipe(rid) {'
        '  var det = document.getElementById("recipe-detail-"+rid);'
        '  var ed = document.getElementById("recipe-edit-"+rid);'
        '  if (!det) return;'
        '  var showing = det.style.display !== "none";'
        '  det.style.display = showing ? "none" : "block";'
        '  if (ed && !showing) ed.style.display = "none";'
        '}'
        '</script>'
    )

    tag_filters = "".join(
        f'<button onclick="filterTag(\'{escape(t)}\')" class="chip" data-tag="{escape(t)}" '
        f'style="padding:4px 10px;border-radius:16px;font-size:0.75em;border:1.5px solid var(--border);'
        f'background:var(--warm-white);color:var(--ink);cursor:pointer;font-family:inherit;">{escape(t)}</button>'
        for t in all_tags
    )

    body = (
        top_nav() +
        render_status_message(status) +
        '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:12px;padding-top:4px;">'
        '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;font-size:2rem;font-weight:600;color:var(--ink);">Recipes</div>'
        '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
        '<a href="/meal-print" target="_blank" '
        'style="padding:8px 14px;font-size:0.82em;border-radius:8px;border:1.5px solid var(--border);'
        'background:var(--parchment);color:var(--ink);text-decoration:none;font-weight:600;">🖨 Print week</a>'
        '<button id="show-add-btn" '
        'onclick="document.getElementById(\'add-recipe-card\').style.display=\'block\';this.style.display=\'none\'" '
        'style="padding:8px 16px;font-size:0.85em;background:var(--ink);color:var(--gold-light);'
        'border:none;border-radius:8px;font-family:inherit;cursor:pointer;font-weight:600;">+ Add recipe</button>'
        '</div>'
        '</div>' +
        add_form +
        (f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;">{tag_filters}</div>' if tag_filters else "") +
        '<div id="recipe-list">' + cards + '</div>' +
        ('<p class="muted">No recipes yet. Add one above.</p>' if not recipes else "") +
        '<script>'
        'var _activeTag = null;'
        'function filterTag(tag) {'
        '  var chips = document.querySelectorAll(".chip");'
        '  chips.forEach(function(c) {'
        '    c.style.background = c.dataset.tag === tag && _activeTag !== tag ? "var(--ink)" : "var(--warm-white)";'
        '    c.style.color = c.dataset.tag === tag && _activeTag !== tag ? "white" : "var(--ink)";'
        '  });'
        '  if(_activeTag === tag) { _activeTag = null; }'
        '  else { _activeTag = tag; }'
        '  var cards = document.querySelectorAll("#recipe-list .card");'
        '  cards.forEach(function(card) {'
        '    if(!_activeTag) { card.style.display = ""; return; }'
        '    var tags = card.dataset.tags ? card.dataset.tags.split(",") : [];'
        '    card.style.display = tags.includes(_activeTag) ? "" : "none";'
        '  });'
        '}'
        'var _RC_DRAFT = "recipeDraft_v1";'
        'function recipeDraftSave() {'
        '  try {'
        '    localStorage.setItem(_RC_DRAFT, JSON.stringify({'
        '      name: (document.getElementById("rc-name")||{}).value||"",'
        '      prep: (document.getElementById("rc-prep")||{}).value||"",'
        '      tags: (document.getElementById("rc-tags")||{}).value||"",'
        '      ingr: (document.getElementById("rc-ingr")||{}).value||"",'
        '      inst: (document.getElementById("rc-inst")||{}).value||"",'
        '      savedAt: Date.now()'
        '    }));'
        '  } catch(e) {}'
        '}'
        'function recipeDraftClear() {'
        '  try { localStorage.removeItem(_RC_DRAFT); } catch(e) {}'
        '}'
        '(function recipeDraftRestore() {'
        '  try {'
        '    var raw = localStorage.getItem(_RC_DRAFT);'
        '    if (!raw) return;'
        '    var d = JSON.parse(raw);'
        '    if (!d || !d.name || (Date.now() - (d.savedAt||0)) > 86400000) { recipeDraftClear(); return; }'
        '    var setVal = function(id, v) { var el=document.getElementById(id); if(el) el.value=v; };'
        '    setVal("rc-name", d.name); setVal("rc-prep", d.prep);'
        '    setVal("rc-tags", d.tags); setVal("rc-ingr", d.ingr); setVal("rc-inst", d.inst);'
        '    var card = document.getElementById("add-recipe-card");'
        '    var btn  = document.getElementById("show-add-btn");'
        '    if (card) card.style.display = "block";'
        '    if (btn)  btn.style.display  = "none";'
        '  } catch(e) { recipeDraftClear(); }'
        '})();'
        '</script>'
    )
    return html_page("Recipes", body)


def _tag_class(tag: str) -> str:
    if any(x in tag.lower() for x in ["school","math","latin","reading"]): return "school"
    if any(x in tag.lower() for x in ["chore","kitchen","clean"]): return "chores"
    if any(x in tag.lower() for x in ["friday","lent","fish"]): return "default"
    if any(x in tag.lower() for x in ["free","easy","quick"]): return "free"
    if any(x in tag.lower() for x in ["sunday","anchor","batch"]): return "kitchen"
    return "default"