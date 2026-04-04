"""
render_lorenzo.py — Lorenzo, AI personal chef for the McAdams family.

Named after Saint Lawrence (San Lorenzo), patron saint of cooks — martyred on
a gridiron in 258 AD and reputed to have said "Turn me over, I'm done on this
side." Warm, skilled, and never rattled by the heat.

Lorenzo knows this family's kitchen, schedule, inventory, and constraints
intimately. He plans meals, manages the week, suggests recipes, tracks what's
in the fridge, and adjusts when Lauren's capacity is low. He coordinates with
Lucy to understand the household's rhythm.

API: POST /lorenzo-chat  → Claude response
"""
import json
import os
from datetime import date, timedelta
from html import escape

try:
    from zoneinfo import ZoneInfo
    _EASTERN = ZoneInfo("America/New_York")
except ImportError:
    import pytz
    _EASTERN = pytz.timezone("America/New_York")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _today_eastern() -> date:
    from datetime import datetime
    return datetime.now(_EASTERN).date()

def _hour_eastern() -> int:
    from datetime import datetime
    return datetime.now(_EASTERN).hour

def _escape_js(s: str) -> str:
    return json.dumps(str(s))

def _load_app_settings() -> dict:
    path = "data/app_settings.json"
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _load_lorenzo_history_safe() -> list:
    try:
        from data_helpers import load_lorenzo_history
        return load_lorenzo_history()
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Context builders
# ─────────────────────────────────────────────────────────────────────────────

def _get_current_meal_plan(iso: str) -> str:
    """Load the meal plan whose window contains today, or the most recent one."""
    try:
        from render_meals import load_meal_plan, DAYS
        from datetime import date as _d
        today = _d.fromisoformat(iso)
        plan = load_meal_plan(iso)
        days_data = plan.get("days", {})
        if not days_data:
            return "No meal plan found for this week."
        lines = ["Current week's meal plan:"]
        for day_name, slots in days_data.items():
            if isinstance(slots, dict):
                parts = []
                for slot in ("breakfast", "lunch", "dinner", "snack"):
                    val = slots.get(slot, "").strip()
                    if val:
                        parts.append(f"{slot.capitalize()}: {val}")
                if parts:
                    lines.append(f"  {day_name}: " + " | ".join(parts))
        return "\n".join(lines) if len(lines) > 1 else "Meal plan exists but is mostly empty."
    except Exception as e:
        return f"Could not load meal plan: {e}"

def _get_inventory() -> str:
    try:
        from render_meals import load_inventory
        inv = load_inventory()
        parts = []
        for section in ("fridge", "freezer", "pantry"):
            val = inv.get(section, "").strip()
            if val:
                parts.append(f"{section.capitalize()}: {val}")
        return "\n".join(parts) if parts else "No inventory recorded."
    except Exception:
        return "Inventory unavailable."

def _get_meal_constraints() -> str:
    try:
        settings = _load_app_settings()
        fc = settings.get("family_constraints", {})
        constraints = fc.get("meal_constraints", "").strip()
        return constraints if constraints else "No standing meal constraints recorded."
    except Exception:
        return "Constraints unavailable."

def _get_lucy_capacity(iso: str) -> str:
    """Pull Mom's capacity from Lucy's morning anchor data."""
    try:
        from render_morning_anchor import _get_anchor_state
        anchor = _get_anchor_state(iso)
        cap = anchor.get("capacity", "").strip().lower()
        if cap == "high":
            return "HIGH — full energy today, Lauren can handle more involved cooking."
        elif cap == "medium":
            return "MEDIUM — moderate energy, prefer meals that don't require too much hands-on time."
        elif cap == "low":
            return "LOW — limited energy today. Favor simple, minimal-effort meals: sheet pans, slow cooker, leftovers, or things the boys can help with."
        return "Not set for today."
    except Exception:
        return "Capacity data unavailable."

def _get_john_status(iso: str) -> str:
    try:
        from render_morning_anchor import _get_anchor_state
        anchor = _get_anchor_state(iso)
        status = anchor.get("john_status", "").strip()
        if not status:
            return ""
        if status.lower() in ("wfh", "working from home", "home office", "work from home"):
            return "John is working from home today — he can help with lunch prep or keeping James occupied."
        elif "travel" in status.lower() or "away" in status.lower():
            return "John is traveling — Lauren is solo today. Keep meal complexity low."
        return f"John: {status}"
    except Exception:
        return ""

def _get_liturgical_note(iso: str) -> str:
    """Check for fasting/abstinence days or major feasts."""
    try:
        from datetime import date as _d
        d = _d.fromisoformat(iso)
        notes = []
        if d.weekday() == 4:
            from datetime import datetime as _dt
            easter = _get_easter(d.year)
            lent_start = easter - timedelta(days=46)
            lent_end   = easter - timedelta(days=1)
            if lent_start <= d <= lent_end:
                notes.append("FRIDAY IN LENT — no meat. Fish, eggs, legumes, or meatless dishes only.")
            else:
                notes.append("Friday — encourage a small act of penance (meatless meal preferred, especially during Ordinary Time).")
        if d.weekday() == 2 or d.weekday() == 5:
            from datetime import datetime as _dt
            easter = _get_easter(d.year)
            ash_wed = easter - timedelta(days=46)
            if d == ash_wed:
                notes.append("ASH WEDNESDAY — full fast and abstinence. Simple, small meals only. No meat.")
            good_fri = easter - timedelta(days=2)
            if d == good_fri:
                notes.append("GOOD FRIDAY — strict fast and abstinence. No meat. Very simple meals.")
        return " | ".join(notes) if notes else ""
    except Exception:
        return ""

def _get_easter(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day   = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)

def _get_kitchen_crew() -> str:
    return (
        "JP (14) — Kitchen Role A: can cook full meals, handle the stove unsupervised, "
        "and lead dinner prep. Give him real responsibility.\n"
        "Joseph (12) — Kitchen Role B: skilled helper, can prep ingredients, stir, assemble, "
        "and run simple recipes with guidance.\n"
        "Michael (5) — can wash vegetables, stir, pour, and feel included. Keep tasks safe and fun.\n"
        "James (13 months) — in the high chair or on Lauren's hip. Not cooking."
    )


# ─────────────────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────────────────

def build_lorenzo_context(iso: str, weekday: str, date_label: str) -> str:
    """Build Lorenzo's full system prompt for the Claude API call."""

    meal_plan   = _get_current_meal_plan(iso)
    inventory   = _get_inventory()
    constraints = _get_meal_constraints()
    capacity    = _get_lucy_capacity(iso)
    john_status = _get_john_status(iso)
    liturny     = _get_liturgical_note(iso)

    lines = [
        "You are Lorenzo — the McAdams family's personal AI chef.",
        "",
        "You are named after Saint Lawrence (San Lorenzo), the patron saint of cooks,",
        "who reportedly joked 'Turn me over — I'm done on this side' while being martyred",
        "on a gridiron. You carry his spirit: warmth, good humor, and a calm head in the kitchen.",
        "",
        f"Today is {weekday}, {date_label}.",
        "",
        "== THE McADAMS FAMILY ==",
        "Lauren (Mom) — the one you work for. A homeschooling Catholic wife and mother.",
        "  She manages the household, plans the school days, and coordinates everything.",
        "  She is your partner in the kitchen — you plan, she executes (with the boys' help).",
        "John (Dad) — husband, works outside the home (or occasionally WFH).",
        "JP — 14 years old. Oldest son. Kitchen Role A: your best kitchen asset.",
        "  He can cook full meals, handle the stove unsupervised, and lead dinner prep.",
        "  Give him real ownership of meals. He rises to the challenge.",
        "Joseph — 12 years old. Kitchen Role B: excellent helper and sous chef.",
        "  Can prep, assemble, and run simple recipes with light guidance.",
        "Michael — 5 years old. Loves to help. Assign safe, simple tasks to make him feel included.",
        "  Stirring, washing vegetables, pouring measured ingredients — his specialty.",
        "James — 13 months old. In the high chair during meal prep. Not cooking.",
        "",
        "== KITCHEN CREW ASSIGNMENTS ==",
        _get_kitchen_crew(),
        "",
        "== TODAY'S HOUSEHOLD STATUS ==",
        f"Lauren's capacity today: {capacity}",
    ]

    if john_status:
        lines.append(john_status)

    if liturny:
        lines += ["", f"LITURGICAL NOTE: {liturny}"]

    lines += [
        "",
        "== CURRENT MEAL PLAN ==",
        meal_plan,
        "",
        "== PANTRY / FRIDGE / FREEZER ==",
        inventory,
        "",
        "== STANDING MEAL RULES & CONSTRAINTS ==",
        constraints,
        "",
        "== YOUR CORE MEAL PLANNING PHILOSOPHY ==",
        "These are the rules you always follow. They are non-negotiable.",
        "",
        "SIMPLICITY FIRST:",
        "- Every meal must be achievable by a tired homeschool mom. Sheet pans, one-pot meals,",
        "  and slow cooker recipes are your friends.",
        "- On low-capacity days: meals that take 20 minutes or less hands-on time, or that a",
        "  kid can largely run. Never suggest multi-component meals on low days.",
        "- On medium days: solid home cooking, 30-45 min prep, one main + simple sides.",
        "- On high days: Lauren can handle a more ambitious meal or a new recipe. Still be reasonable.",
        "",
        "KIDS EAT WHAT EVERYONE EATS:",
        "- No short-order cooking. One family meal.",
        "- If a dish has a component a child dislikes, suggest a simple modification (e.g., sauce on the side).",
        "- Introduce variety gradually. Never suggest forcing a child to eat something they hate.",
        "",
        "BATCH COOKING & LEFTOVERS:",
        "- If dinner serves well as next day's lunch, say so explicitly.",
        "- Suggest doubling a recipe when it makes sense.",
        "- Flag 'cook once, eat twice' opportunities proactively.",
        "",
        "USE WHAT'S ON HAND:",
        "- Before suggesting a grocery run, look at the inventory.",
        "- Build meals around what's already in the fridge/freezer first.",
        "- Flag items that need to be used soon (before they go bad).",
        "",
        "BOYS IN THE KITCHEN:",
        "- When suggesting dinner, note who can lead or help with each step.",
        "- JP should have at least 2-3 dinners a week where he is the primary cook.",
        "- Joseph should have regular tasks in most dinners.",
        "- Michael should always have one small safe job.",
        "",
        "CATHOLIC CALENDAR AWARENESS:",
        "- Know the liturgical season and adjust accordingly.",
        "- On Fridays (especially in Lent): no meat. Suggest fish, eggs, or meatless meals.",
        "- On Ash Wednesday and Good Friday: suggest simple, spare, penitential meals.",
        "- Feast days of family saints: suggest a special meal to mark the occasion.",
        "- August 10 (Feast of Saint Lawrence): suggest something cooked on the grill. Obviously.",
        "",
        "GROCERIES & BUDGET:",
        "- Be mindful that feeding 6 people (4 boys, one of whom is a teenager) requires volume.",
        "- Suggest economical proteins: chicken thighs over breasts, ground beef, eggs, beans, tuna.",
        "- When you suggest a new dish, note the ingredients needed so Lauren can shop.",
        "",
        "== YOUR PERSONALITY ==",
        "- Warm, confident, and a little Italian in spirit — you love food and you love this family.",
        "- You address Lauren directly and personally. You know her by name.",
        "- You are practical, never fussy. No precious techniques or hard-to-find ingredients.",
        "- You have a dry sense of humor. You're allowed to be funny about kitchen disasters,",
        "  teenagers who suddenly can cook, and the chaos of feeding a large family.",
        "- You never lecture. If Lauren wants pizza for the third night in a row, you gently",
        "  offer an easy alternative — and if she says no, you make the best pizza possible.",
        "- You celebrate small wins: a kid eating a new vegetable, a successful batch-cook Sunday,",
        "  a dinner that everyone actually liked. These matter.",
        "- You are Saint Lawrence's namesake. You do not panic under pressure.",
        "- FORMATTING: Never use markdown. No ##, no **, no *. Plain text only.",
        "  Use simple dashes or numbers for lists. Keep responses focused and scannable.",
        "- CRITICAL: Ask only ONE question at a time. Never stack multiple questions.",
        "  Say your piece, ask the single most important question, wait for the answer.",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Page renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_lorenzo_page() -> str:
    today      = _today_eastern()
    iso        = today.isoformat()
    weekday    = today.strftime("%A")
    date_label = today.strftime("%B %d, %Y")
    h          = _hour_eastern()

    if h < 11:
        greeting      = "Buongiorno."
        phase_label   = "Morning kitchen"
        phase_color   = "#c49020"
        opener_prompt = f"Good morning, Lorenzo! It's {date_label}. What should we be cooking this week?"
        quick_prompts = [
            ("Plan this week's dinners",       "Plan this week's dinners for the family."),
            ("What can JP cook tonight?",      "What's a good dinner for JP to lead tonight?"),
            ("Low-effort dinner ideas",        "I have low energy today. Give me the easiest possible dinner."),
            ("What's in my fridge?",           "Look at my inventory and tell me what meals I can make without shopping."),
            ("Prep for the week",              "Help me think through Sunday meal prep for the week ahead."),
        ]
    elif h < 17:
        greeting      = "What's for dinner?"
        phase_label   = "Afternoon kitchen"
        phase_color   = "#1a6050"
        opener_prompt = f"Lorenzo, it's {date_label}. I need to figure out dinner. What are we making?"
        quick_prompts = [
            ("Quick dinner for tonight",       "I need dinner in 30 minutes or less. What do we make?"),
            ("JP leads tonight",               "JP is leading dinner tonight. What should he make?"),
            ("Use what's in the fridge",       "Plan dinner using what I already have in the fridge and pantry."),
            ("Grocery run list",               "What should I pick up today to fill out the week's meals?"),
            ("Something new for the family",   "Suggest a new dish the whole family will probably enjoy."),
        ]
    else:
        greeting      = "Planning tomorrow's table."
        phase_label   = "Evening planning"
        phase_color   = "#4a3a8a"
        opener_prompt = f"Lorenzo, let's plan tomorrow's meals and any overnight prep needed."
        quick_prompts = [
            ("Tomorrow's meals",               "Walk me through tomorrow's breakfast, lunch, and dinner."),
            ("Overnight prep I can do now",    "What can I prep tonight to make tomorrow easier?"),
            ("Slow cooker for tomorrow",       "Suggest something I can put in the slow cooker tonight or early tomorrow."),
            ("Leftover plan",                  "What leftovers do I have and how can I use them tomorrow?"),
            ("Shopping list for tomorrow",     "Build me a quick shopping list for tomorrow's meals."),
        ]

    history     = _load_lorenzo_history_safe()
    has_history = bool(history)
    history_js  = json.dumps([
        {"role": m["role"], "content": m.get("content", "")}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content", "")
    ])

    quick_buttons = "".join(
        f'<button onclick="lorenzQuick({_escape_js(prompt)})" '
        f'style="background:#faf8f5;border:1px solid #e4dbd2;border-radius:20px;'
        f'padding:6px 14px;font-size:0.8em;cursor:pointer;color:#555;font-family:inherit;'
        f'white-space:nowrap;transition:background 0.15s;" '
        f'onmouseover="this.style.background=\'#f0ebe4\'" '
        f'onmouseout="this.style.background=\'#faf8f5\'">'
        f'{escape(label)}</button>'
        for label, prompt in quick_prompts
    )

    phase_dot = (
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        f'background:{phase_color};margin-right:6px;"></span>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Lorenzo &middot; McAdams Chef</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#faf8f5;color:#1a1a1a;min-height:100vh;}}
.lz-bubble-user{{
    background:#3b2a1a;color:white;padding:10px 14px;border-radius:16px 16px 4px 16px;
    font-size:0.9em;line-height:1.55;max-width:75%;align-self:flex-end;margin-left:auto;
}}
.lz-bubble-lz{{
    background:white;border:1px solid #e4dbd2;padding:12px 16px;
    border-radius:4px 16px 16px 16px;font-size:0.9em;line-height:1.65;
    max-width:85%;white-space:pre-wrap;color:#1a1a1a;
}}
.lz-bubble-wrap{{display:flex;flex-direction:column;gap:12px;}}
.lz-input{{
    position:fixed;bottom:0;left:0;right:0;background:#faf8f5;
    border-top:1px solid #e4dbd2;padding:12px 16px 20px;
    display:flex;gap:10px;align-items:flex-end;
}}
.lz-textarea{{
    flex:1;border:1px solid #d4c9bb;border-radius:12px;padding:10px 14px;
    font-size:0.95em;font-family:inherit;resize:none;background:white;
    min-height:42px;max-height:120px;line-height:1.5;color:#1a1a1a;
    outline:none;
}}
.lz-send{{
    background:#8b3a1a;color:white;border:none;border-radius:10px;
    padding:10px 18px;font-size:0.9em;cursor:pointer;font-family:inherit;
    white-space:nowrap;transition:background 0.15s;flex-shrink:0;
}}
.lz-send:hover{{background:#a84420;}}
.lz-send:disabled{{background:#ccc;cursor:not-allowed;}}
</style>
</head>
<body>

<div style="max-width:760px;margin:0 auto;padding:20px 16px 160px;">

    <!-- Back + phase label -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
        <a href="/" style="font-size:0.82em;color:#aaa;text-decoration:none;">&larr; Dashboard</a>
        <div style="display:flex;align-items:center;gap:14px;">
            {'<form method="POST" action="/lorenzo-clear-history" style="display:inline;">'
             '<button type="submit" style="background:none;border:none;font-size:0.72em;'
             'color:#bbb;cursor:pointer;font-family:inherit;padding:0;">&#10005; New conversation</button>'
             '</form>' if has_history else ''}
            <a href="/meals" style="font-size:0.78em;color:#8b3a1a;text-decoration:none;">&#127869; Meal Planner</a>
            <span style="font-size:0.78em;color:#aaa;">{phase_dot}{escape(phase_label)}</span>
        </div>
    </div>

    <!-- Lorenzo header -->
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:28px;">
        <div style="width:52px;height:52px;border-radius:50%;
                    background:linear-gradient(135deg,#8b3a1a,#c49020);
                    display:flex;align-items:center;justify-content:center;font-size:1.5em;
                    flex-shrink:0;box-shadow:0 2px 10px rgba(139,58,26,0.25);">
            &#127860;
        </div>
        <div>
            <div style="font-family:Georgia,serif;font-size:1.5em;font-weight:600;color:#1a1a1a;line-height:1.1;">
                {escape(greeting)}
            </div>
            <div style="font-size:0.85em;color:#888;margin-top:2px;">
                Lorenzo &middot; {escape(weekday)}, {escape(date_label)}
            </div>
        </div>
    </div>

    <!-- Quick prompts -->
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px;">
        {quick_buttons}
    </div>

    <!-- Chat area -->
    <div class="lz-bubble-wrap" id="lz-chat"></div>

    <!-- Thinking indicator -->
    <div id="lz-thinking" style="display:none;padding:10px 0;color:#aaa;font-size:0.85em;">
        Lorenzo is thinking&hellip;
    </div>

</div>

<!-- Input bar -->
<div class="lz-input">
    <textarea id="lz-msg" class="lz-textarea" rows="1" placeholder="Ask Lorenzo anything about meals…"
              onkeydown="lzKeydown(event)" oninput="lzResize(this)"></textarea>
    <button class="lz-send" id="lz-btn" onclick="lorenzSend()">Send</button>
</div>

<script>
var _lzHistory = {history_js};
var _lzIso     = {json.dumps(iso)};
var _lzWeekday = {json.dumps(weekday)};

function lzRender(role, text) {{
    var wrap  = document.getElementById("lz-chat");
    var div   = document.createElement("div");
    div.className = role === "user" ? "lz-bubble-user" : "lz-bubble-lz";
    div.textContent = text;
    wrap.appendChild(div);
    window.scrollTo(0, document.body.scrollHeight);
}}

function lzKeydown(e) {{
    if (e.key === "Enter" && !e.shiftKey) {{
        e.preventDefault();
        lorenzSend();
    }}
}}

function lzResize(el) {{
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
}}

function lorenzQuick(prompt) {{
    document.getElementById("lz-msg").value = prompt;
    lorenzSend();
}}

function lorenzSend() {{
    var msgEl  = document.getElementById("lz-msg");
    var btn    = document.getElementById("lz-btn");
    var text   = msgEl.value.trim();
    if (!text) return;

    lzRender("user", text);
    _lzHistory.push({{role:"user", content:text}});
    msgEl.value = "";
    msgEl.style.height = "auto";
    btn.disabled = true;
    document.getElementById("lz-thinking").style.display = "block";

    var params = new URLSearchParams();
    params.append("iso", _lzIso);
    params.append("message", text);

    fetch("/lorenzo-chat", {{
        method: "POST",
        headers: {{"Content-Type": "application/x-www-form-urlencoded"}},
        body: params.toString()
    }})
    .then(function(r) {{ return r.text(); }})
    .then(function(reply) {{
        document.getElementById("lz-thinking").style.display = "none";
        lzRender("assistant", reply);
        _lzHistory.push({{role:"assistant", content:reply}});
        btn.disabled = false;
    }})
    .catch(function(err) {{
        document.getElementById("lz-thinking").style.display = "none";
        lzRender("assistant", "Lorenzo stepped away from the stove for a moment. Try again.");
        btn.disabled = false;
    }});
}}

// Restore history
(function() {{
    for (var i = 0; i < _lzHistory.length; i++) {{
        lzRender(_lzHistory[i].role, _lzHistory[i].content);
    }}
    if (_lzHistory.length === 0) {{
        lorenzQuick({_escape_js(opener_prompt)});
    }}
}})();
</script>
</body>
</html>"""
