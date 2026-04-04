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

MEAL_SLOTS = ["breakfast","lunch","dinner","snacks","dad_lunch"]

MEAL_SLOT_LABELS = {
    "breakfast": "Breakfast",
    "lunch":     "Lunch",
    "dinner":    "Dinner",
    "snacks":    "Snacks",
    "dad_lunch": "Dad's Lunch",
}

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
    # ISO week: YYYY-WW
    return d.strftime("%Y-W%W")

def _week_start(for_date: date = None) -> date:
    d = for_date or date.today()
    return d - timedelta(days=d.weekday())  # Monday

def load_meal_plan(week_key: str = None) -> dict:
    key = week_key or _week_key()
    default = {
        "week": key,
        "generated": False,
        "days": {day: {slot: "" for slot in MEAL_SLOTS} for day in DAYS}
    }
    return ensure_file(_plan_path(key), default)

def save_meal_plan(plan: dict):
    safe_save_json(_plan_path(plan["week"]), plan)

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
                tags: list = None, prep_time: str = "") -> dict:
    recipes = load_recipes()
    recipe = {
        "id": str(uuid.uuid4())[:8],
        "name": name.strip(),
        "ingredients": ingredients.strip(),
        "instructions": instructions.strip(),
        "tags": tags or [],
        "prep_time": prep_time.strip(),
        "created": date.today().isoformat(),
    }
    recipes.append(recipe)
    save_recipes(recipes)
    return recipe

# ---------------------------------------------------------------------------
# AI generation prompt builder
# ---------------------------------------------------------------------------

def _build_meal_prompt(inventory: dict, cycle_phase: str = "",
                        capacity: str = "", week_start: date = None) -> str:
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

CRITICAL RULES REMINDER:
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

    meal_icons  = {"breakfast": "☀️", "lunch": "🥗", "dinner": "🍽️", "snacks": "🍎"}
    meal_labels = {"breakfast": "Breakfast", "lunch": "Lunch",
                   "dinner": "Dinner", "snacks": "Snacks"}
    boys_help   = (slots.get("boys_help") or "").strip()

    rows_html = ""
    for slot in ["breakfast", "lunch", "dinner", "snacks"]:
        val = (slots.get(slot) or "").strip()
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

    wk     = week_key or _week_key()
    plan   = load_meal_plan(wk)
    inv    = load_inventory()
    days_data = plan.get("days", {})

    # Parse the displayed week's Monday from the week_key so navigation
    # arrows move relative to the page being viewed, not today.
    try:
        from datetime import datetime as _dtp
        ws = _dtp.strptime(wk + "-1", "%Y-W%W-%w").date()
    except Exception:
        ws = _week_start()

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

    # Week navigation — relative to the displayed week, not today
    prev_week = (ws - timedelta(weeks=1)).strftime("%Y-W%W")
    next_week = (ws + timedelta(weeks=1)).strftime("%Y-W%W")

    week_label = ws.strftime("Week of %B %d, %Y")

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

        # Quick-paste block
        '<div style="background:#faf8f5;border-radius:10px;border:1.5px dashed var(--border);'
        'padding:12px 14px;margin-bottom:14px;">'
        '<div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;'
        'color:var(--ink-faint);margin-bottom:8px;">&#9998; Paste everything at once</div>'
        '<textarea id="inv-paste-raw" rows="5" '
        'placeholder="Here\'s what\'s in the fridge: eggs, chicken thighs, leftover rice&#10;'
        'Freezer: ground beef, flounder fillets, frozen peas&#10;'
        'Pantry: rice, lentils, olive oil, canned tomatoes&#10;'
        'Use soon: open sour cream, wilting spinach" '
        'style="font-size:0.85em;resize:vertical;margin-bottom:8px;background:white;"></textarea>'
        '<div style="display:flex;align-items:center;gap:10px;">'
        '<button onclick="parseInventory()" '
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
    for day in DAYS:
        day_date = ws + timedelta(days=DAYS.index(day))
        is_today = (day_date == date.today())
        day_color = CHILD_COLORS.get(day, "#555")
        bg = "var(--ink)" if is_today else "var(--parchment)"
        fg = "var(--gold-light)" if is_today else day_color
        header_cells += (
            f'<td style="text-align:center;background:{bg};padding:8px 4px;min-width:120px;">'
            f'<div style="font-weight:700;font-size:0.82em;color:{fg};">{escape(day)}</div>'
            f'<div style="font-size:0.72em;color:{"rgba(245,234,216,0.6)" if is_today else "var(--ink-faint)"};">'
            f'{day_date.strftime("%b %d")}</div>'
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
            "snacks":    "white",
            "dad_lunch": "#f5f0f8",
        }.get(slot, "white")
        cells = (
            f'<td style="background:var(--parchment);padding:6px 8px;'
            f'font-size:0.72em;font-weight:700;color:var(--ink-faint);'
            f'white-space:nowrap;border-right:2px solid var(--border);">'
            f'{escape(slot_label)}</td>'
        )
        for day in DAYS:
            val = days_data.get(day, {}).get(slot, "")
            safe_day  = day.replace("'","")
            safe_slot = slot.replace("'","")
            cells += (
                f'<td style="padding:3px;background:{slot_bg};border-bottom:1px solid var(--border-light);">'
                f'<textarea data-day="{escape(safe_day)}" data-slot="{escape(safe_slot)}"'
                f' oninput="cellChanged(this)"'
                f' style="width:100%;min-height:52px;border:none;outline:none;'
                f'background:transparent;font-size:0.78em;font-family:inherit;'
                f'resize:vertical;padding:4px;color:var(--ink);">'
                f'{escape(val)}'
                f'</textarea></td>'
            )
        grid_rows += f'<tr>{cells}</tr>'

    # Boys Help row (separate from MEAL_SLOTS — stores in days[day]["boys_help"])
    help_cells = (
        f'<td style="background:var(--parchment);padding:6px 8px;'
        f'font-size:0.72em;font-weight:700;color:#92400e;'
        f'white-space:nowrap;border-right:2px solid var(--border);">'
        f'👦 Boys Help</td>'
    )
    for day in DAYS:
        val = days_data.get(day, {}).get("boys_help", "")
        safe_day = day.replace("'", "")
        help_cells += (
            f'<td style="padding:3px;background:#fefce8;border-bottom:1px solid var(--border-light);">'
            f'<textarea data-day="{escape(safe_day)}" data-slot="boys_help"'
            f' oninput="cellChanged(this)"'
            f' style="width:100%;min-height:52px;border:none;outline:none;'
            f'background:transparent;font-size:0.78em;font-family:inherit;'
            f'resize:vertical;padding:4px;color:#78350f;"'
            f' placeholder="e.g. JP: chop veg · Joseph: set table · Michael: fill water">'
            f'{escape(val)}'
            f'</textarea></td>'
        )
    grid_rows += f'<tr>{help_cells}</tr>'

    grocery_raw    = json.dumps(plan.get("grocery_gaps", []))
    prep_notes_raw = json.dumps(plan.get("prep_notes", {}))

    body = (
        top_nav() +
        render_status_message(status) +

        # Header
        '<div style="display:flex;align-items:flex-start;justify-content:space-between;'
        'flex-wrap:wrap;gap:8px;margin-bottom:8px;padding-top:4px;">'
        '<div>'
        '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        'font-size:2rem;font-weight:600;color:var(--ink);line-height:1.1;">Meal Planner</div>'
        '<div style="font-size:0.85em;color:var(--ink-muted);margin-top:2px;">'
        + escape(week_label) +
        '</div></div>'

        # Week nav + outputs
        '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:6px;">'
        f'<a href="/meals?week={escape(prev_week)}" class="link-button" style="font-size:0.82em;">&larr;</a>'
        f'<a href="/meals?week={escape(next_week)}" class="link-button" style="font-size:0.82em;">&rarr;</a>'
        '<button onclick="savePlan()" style="padding:7px 14px;font-size:0.82em;">Save plan</button>'
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
        '</div></div>' +

        # Modals placeholder
        '<div id="modal-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:3000;">'
        '<div id="modal-content" style="background:white;border-radius:16px;max-width:680px;'
        'width:90%;max-height:80vh;overflow-y:auto;margin:5vh auto;padding:24px;">'
        '<div id="modal-body"></div>'
        '<div style="margin-top:16px;text-align:right;">'
        '<button onclick="document.getElementById(\'modal-overlay\').style.display=\'none\'" '
        'style="padding:8px 16px;font-size:0.85em;background:var(--parchment);color:var(--ink);border:1.5px solid var(--border);">Close</button>'
        '</div></div></div>' +

        # JS
        f'<script>'
        f'var _mealWeek = "{escape(wk)}";'
        f'var _mealChanges = {{}};'
        f'var _mealTimer = null;'
        f'var _groceryGaps = {grocery_raw};'
        f'var _prepNotes = {prep_notes_raw};'
        f'var _apiKey = "";'

        # Try to load API key from settings
        f'try {{ fetch("/api-key").then(r=>r.json()).then(d=>{{if(d.key)_apiKey=d.key;}}); }} catch(e) {{}}'

        # Cell changed
        'function cellChanged(ta) {'
        '  var day=ta.dataset.day, slot=ta.dataset.slot, val=ta.value;'
        '  if(!_mealChanges[day]) _mealChanges[day]={};'
        '  _mealChanges[day][slot]=val;'
        '  clearTimeout(_mealTimer);'
        '  _mealTimer=setTimeout(autoSavePlan,900);'
        '  var el=document.getElementById("grid-status");'
        '  if(el) el.textContent="Unsaved changes...";'
        '}'

        # Auto save
        'function autoSavePlan() {'
        '  savePlan();'
        '}'
        'window.addEventListener("beforeunload", function() { if(Object.keys(_mealChanges).length) savePlan(); });'

        # Save plan
        'function savePlan() {'
        '  var cells = document.querySelectorAll("#meal-grid textarea");'
        '  var days = {};'
        '  cells.forEach(function(ta) {'
        '    var d=ta.dataset.day, s=ta.dataset.slot;'
        '    if(!days[d]) days[d]={};'
        '    days[d][s]=ta.value;'
        '  });'
        '  fetch("/meal-save-plan", {method:"POST",'
        '    headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        '    body:"week="+encodeURIComponent(_mealWeek)+"&days="+encodeURIComponent(JSON.stringify(days))})'
        '  .then(function() {'
        '    _mealChanges={};'
        '    var el=document.getElementById("grid-status");'
        '    if(el){el.textContent="Saved \u2713";setTimeout(function(){el.textContent="";},1800);}'
        '  });'
        '}'

        # Parse free-text inventory
        'function parseInventory() {'
        '  var raw = document.getElementById("inv-paste-raw").value;'
        '  if (!raw.trim()) return;'
        '  var chunks = { fridge: [], freezer: [], pantry: [], use_soon: [] };'
        '  var current = "pantry";'
        '  var lines = raw.split(/\\r?\\n/);'
        '  lines.forEach(function(line) {'
        '    var l = line.trim();'
        '    if (!l) return;'
        '    var isFridge   = /fridge|refrigerat/i.test(l);'
        '    var isFreezer  = /freezer|frozen/i.test(l);'
        '    var isPantry   = /pantry|cabinet|shelf|shelves|cupboard/i.test(l);'
        '    var isUseSoon  = /use.?soon|priority|urgent/i.test(l);'
        '    if (isFridge || isFreezer || isPantry || isUseSoon) {'
        '      if (isFridge)  current = "fridge";'
        '      else if (isFreezer) current = "freezer";'
        '      else if (isPantry)  current = "pantry";'
        '      else if (isUseSoon) current = "use_soon";'
        '      var colon = l.indexOf(":");'
        '      if (colon >= 0) {'
        '        var after = l.slice(colon + 1).trim();'
        '        if (after) chunks[current].push(after);'
        '      }'
        '      return;'
        '    }'
        '    chunks[current].push(l);'
        '  });'
        '  if (chunks.fridge.length)    document.getElementById("inv-fridge").value   = chunks.fridge.join("\\n");'
        '  if (chunks.freezer.length)   document.getElementById("inv-freezer").value  = chunks.freezer.join("\\n");'
        '  if (chunks.pantry.length)    document.getElementById("inv-pantry").value   = chunks.pantry.join("\\n");'
        '  if (chunks.use_soon.length)  document.getElementById("inv-use-soon").value = chunks.use_soon.join(", ");'
        '  var st = document.getElementById("inv-parse-status");'
        '  if (st) { st.textContent = "Sections filled \u2713 \u2014 review and save.";'
        '    setTimeout(function(){st.textContent="";}, 3000); }'
        '}'

        # Save inventory
        'function saveInventory() {'
        '  var data = {'
        '    fridge:   document.getElementById("inv-fridge").value,'
        '    freezer:  document.getElementById("inv-freezer").value,'
        '    pantry:   document.getElementById("inv-pantry").value,'
        '    use_soon: document.getElementById("inv-use-soon").value,'
        '  };'
        '  fetch("/meal-save-inventory", {method:"POST",'
        '    headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        '    body:"data="+encodeURIComponent(JSON.stringify(data))})'
        '  .then(function() {'
        '    var el=document.getElementById("inv-status");'
        '    if(el){el.textContent="Inventory saved \u2713";setTimeout(function(){el.textContent="";},2000);}'
        '  });'
        '}'

        # Generate plan via AI
        'function generatePlan() {'
        '  saveInventory();'
        '  var st = document.getElementById("ai-status");'
        '  if(st) st.textContent = "\u2728 Generating your meal plan... (this takes 15-30 seconds)";'
        '  var inv = {'
        '    fridge:   document.getElementById("inv-fridge").value,'
        '    freezer:  document.getElementById("inv-freezer").value,'
        '    pantry:   document.getElementById("inv-pantry").value,'
        '    use_soon: document.getElementById("inv-use-soon").value,'
        '  };'
        '  fetch("/meal-generate", {method:"POST",'
        '    headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        '    body:"week="+encodeURIComponent(_mealWeek)+"&inventory="+encodeURIComponent(JSON.stringify(inv))})'
        '  .then(r=>r.json())'
        '  .then(function(d) {'
        '    if(d.error){if(st)st.textContent="Error: "+d.error;return;}'
        '    if(st) st.textContent = "\u2713 Plan generated! Review and edit below.";'
        '    _groceryGaps = d.grocery_gaps || [];'
        '    _prepNotes = d.prep_notes || {};'
        '    // Populate grid cells'
        '    var days = d.days || {};'
        '    Object.keys(days).forEach(function(day) {'
        '      Object.keys(days[day]).forEach(function(slot) {'
        '        var ta = document.querySelector("#meal-grid textarea[data-day=\'"+day+"\'][data-slot=\'"+slot+"\']");'
        '        if(ta) ta.value = days[day][slot];'
        '      });'
        '    });'
        '    savePlan();'
        '  })'
        '  .catch(function(e) {'
        '    if(st) st.textContent = "Generation failed. Check API key in Settings.";'
        '  });'
        '}'

        # View grocery list
        'function viewGrocery() {'
        '  var html = "<h3 style=\'margin-bottom:14px;\'>Grocery list</h3>";'
        '  if(!_groceryGaps || !_groceryGaps.length) {'
        '    html += "<p style=\'color:#888;\'>Generate a meal plan first to see the grocery list.</p>";'
        '  } else {'
        '    html += "<p style=\'font-size:0.85em;color:#888;margin-bottom:12px;\'>Items not in your inventory that are needed:</p>";'
        '    html += "<ul style=\'padding-left:20px;\'>";'
        '    _groceryGaps.forEach(function(item) { html += "<li style=\'padding:4px 0;font-size:0.9em;\'>" + item + "</li>"; });'
        '    html += "</ul>";'
        '  }'
        '  document.getElementById("modal-body").innerHTML = html;'
        '  document.getElementById("modal-overlay").style.display = "block";'
        '}'

        # View prep schedule
        'function viewPrepSchedule() {'
        '  var html = "<h3 style=\'margin-bottom:14px;\'>Daily prep schedule</h3>";'
        '  var days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];'
        '  days.forEach(function(day) {'
        '    var note = _prepNotes[day] || "";'
        '    if(note) {'
        '      html += "<div style=\'padding:8px 0;border-bottom:1px solid #f0ebe4;\'>";'
        '      html += "<div style=\'font-weight:700;font-size:0.85em;color:#1a3870;margin-bottom:3px;\'>" + day + "</div>";'
        '      html += "<div style=\'font-size:0.85em;\'>" + note + "</div></div>";'
        '    }'
        '  });'
        '  if(html === "<h3 style=\'margin-bottom:14px;\'>Daily prep schedule</h3>") {'
        '    html += "<p style=\'color:#888;\'>Generate a meal plan first to see the prep schedule.</p>";'
        '  }'
        '  document.getElementById("modal-body").innerHTML = html;'
        '  document.getElementById("modal-overlay").style.display = "block";'
        '}'

        # Print fridge card
        'function printFridge() {'
        '  savePlan();'
        '  setTimeout(function() {'
        '    window.open("/meal-print?week="+encodeURIComponent(_mealWeek), "_blank");'
        '  }, 500);'
        '}'

        '</script>'
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
    wk   = week_key or _week_key()
    plan = load_meal_plan(wk)
    ws   = _week_start()
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
            val = days_data.get(day, {}).get(slot, "").strip()
            is_fri = (day == "Friday")
            bg = "#fdf0ef" if is_fri else "white"
            cells += f"<td style='border:1px solid #ddd;padding:4pt 5pt;font-size:8pt;background:{bg};vertical-align:top;'>{escape(val)}</td>"
        rows += f"<tr>{cells}</tr>"

    # Dad's lunches row
    dad_cells = "<td style='border:1px solid #ddd;padding:4pt 5pt;font-size:8pt;font-weight:700;color:#6b1a8a;background:#faf5ff;white-space:nowrap;'>Dad's Lunch</td>"
    for day in DAYS:
        val = days_data.get(day, {}).get("dad_lunch", "").strip()
        dad_cells += f"<td style='border:1px solid #ddd;padding:4pt 5pt;font-size:8pt;background:{'#faf5ff' if val else 'white'};vertical-align:top;color:#6b1a8a;'>{escape(val)}</td>"
    rows += f"<tr>{dad_cells}</tr>"

    prep_notes = plan.get("prep_notes", {})
    if prep_notes:
        prep_cells = "<td style='border:1px solid #ddd;padding:4pt 5pt;font-size:8pt;font-weight:700;color:#1a6050;background:#f0fdf9;white-space:nowrap;'>Prep</td>"
        for day in DAYS:
            note = prep_notes.get(day, "").strip()
            prep_cells += f"<td style='border:1px solid #ddd;padding:3pt 5pt;font-size:7.5pt;background:#f0fdf9;vertical-align:top;color:#1a6050;'>{escape(note)}</td>"
        rows += f"<tr>{prep_cells}</tr>"

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
        f"<title>Meal Plan \u2014 {escape(week_label)}</title>"
        "<style>"
        "*{box-sizing:border-box;margin:0;padding:0;}"
        "body{font-family:Georgia,'Times New Roman',serif;background:white;color:#111;}"
        ".no-print{display:none;}"
        "@media screen{body{padding:20px;}.no-print{display:block;}}"
        "@media print{@page{margin:0.4in;size:landscape;}.no-print{display:none;}}"
        "</style></head><body>"
        "<div class='no-print' style='background:#1c1610;color:#f5ead8;padding:10px 20px;"
        "font-family:sans-serif;font-size:13px;margin-bottom:16px;display:flex;gap:12px;align-items:center;'>"
        "<button onclick='window.print()' style='background:#c49020;color:#1c1610;border:none;"
        "padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:700;'>&#128438; Print / Save PDF</button>"
        "<a href='/meals' style='color:#f5ead8;'>Back to Meal Planner</a>"
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

    # Collect all unique tags for filter chips
    all_tags = sorted(set(t for r in recipes for t in r.get("tags", [])))

    # Recipe cards
    cards = ""
    for r in recipes:
        rid   = escape(r.get("id",""))
        name  = escape(r.get("name",""))
        ingr  = escape(r.get("ingredients",""))
        instr = escape(r.get("instructions",""))
        prep  = escape(r.get("prep_time",""))
        tags  = r.get("tags", [])
        tag_pills = "".join(
            f'<span class="pill pill-{_tag_class(t)}" style="font-size:0.7em;margin-right:4px;">{escape(t)}</span>'
            for t in tags[:6]
        )
        cards += (
            f'<div class="card" data-tags="{escape(",".join(tags))}" style="margin-bottom:14px;">'
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
            f'<form method="POST" action="/recipe-save">'
            f'<input type="hidden" name="id" value="{rid}">'
            f'<label style="font-size:0.75em;">Name</label>'
            f'<input type="text" name="name" value="{name}" style="margin-bottom:8px;">'
            f'<label style="font-size:0.75em;">Prep time</label>'
            f'<input type="text" name="prep_time" value="{prep}" style="margin-bottom:8px;">'
            f'<label style="font-size:0.75em;">Tags (comma-separated)</label>'
            f'<input type="text" name="tags" value="{escape(",".join(tags))}" style="margin-bottom:8px;" '
            f'placeholder="chicken, easy, Friday, Lent-safe">'
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
        '<form method="POST" action="/recipe-save">'
        '<label>Name</label>'
        '<input type="text" name="name" required placeholder="Recipe name" style="margin-bottom:10px;">'
        '<label>Prep time</label>'
        '<input type="text" name="prep_time" placeholder="20 min" style="margin-bottom:10px;">'
        '<label>Tags <span style="font-weight:400;font-size:0.85em;color:#888;">(comma-separated)</span></label>'
        '<input type="text" name="tags" placeholder="chicken, easy, Friday, Lent-safe" style="margin-bottom:10px;">'
        '<label>Ingredients</label>'
        '<textarea name="ingredients" rows="4" placeholder="List all ingredients..." style="margin-bottom:10px;"></textarea>'
        '<label>Instructions</label>'
        '<textarea name="instructions" rows="5" placeholder="Step-by-step instructions..." style="margin-bottom:12px;"></textarea>'
        '<div style="display:flex;gap:8px;">'
        '<button type="submit" style="padding:8px 18px;background:var(--ink);color:var(--gold-light);'
        'border:none;border-radius:8px;font-family:inherit;font-size:0.85em;cursor:pointer;">Save recipe</button>'
        '<button type="button" onclick="document.getElementById(\'add-recipe-card\').style.display=\'none\';'
        'document.getElementById(\'show-add-btn\').style.display=\'inline-block\'" '
        'style="padding:8px 14px;background:transparent;border:1.5px solid var(--border);'
        'border-radius:8px;font-family:inherit;font-size:0.85em;cursor:pointer;color:var(--ink-muted);">Cancel</button>'
        '</div></form></div>'
        # Import tab
        '<div id="recipe-import-tab" style="display:none;">'
        '<form method="POST" action="/recipe-import" enctype="multipart/form-data">'
        '<div style="margin-bottom:14px;">'
        '<label>\U0001f4f8 Photo of recipe card or cookbook page</label>'
        '<input type="file" name="recipe_photo" accept="image/*" capture="environment" '
        'style="margin-bottom:6px;font-size:0.85em;">'
        '<p style="font-size:0.78em;color:var(--ink-faint);margin-top:2px;">Take or upload a photo — '
        'AI will read the ingredients and instructions automatically.</p>'
        '</div>'
        '<div style="margin-bottom:4px;font-size:0.72em;font-weight:700;color:var(--ink-faint);'
        'text-transform:uppercase;letter-spacing:.08em;">Or</div>'
        '<div style="margin-bottom:14px;">'
        '<label>Recipe URL</label>'
        '<input type="url" name="url" placeholder="https://www.seriouseats.com/..." style="margin-bottom:8px;">'
        '</div>'
        '<div style="margin-bottom:14px;">'
        '<label>Or paste recipe text</label>'
        '<textarea name="text" rows="5" placeholder="Paste any recipe text, ingredients list, or instructions..." '
        'style="margin-bottom:8px;"></textarea>'
        '</div>'
        '<div style="margin-bottom:14px;">'
        '<label>Recipe name <span style="font-weight:400;font-size:0.85em;color:#888;">(required)</span></label>'
        '<input type="text" name="name" required placeholder="Name this recipe" style="margin-bottom:8px;">'
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