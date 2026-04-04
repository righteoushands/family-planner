"""
render_lorenzo.py — Lorenzo, AI personal chef for the McAdams family.

Named after Saint Lawrence (San Lorenzo), patron saint of cooks — martyred on
a gridiron in 258 AD and reputed to have said "Turn me over, I'm done on this
side." Warm, skilled, and never rattled by the heat.

Lorenzo knows this family's kitchen, schedule, inventory, and constraints.
Full features: voice input, read-aloud TTS, image attachment, rule saving,
temp vs. permanent adjustment distinction, and "Hey Lorenzo" wake word.

API: POST /lorenzo-chat     → Claude response
     POST /lorenzo-rule-save → save permanent rule to meal_constraints
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

def _ej(s: str) -> str:
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
    try:
        from render_meals import load_meal_plan
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
        lr = fc.get("lorenzo_rules", [])
        if isinstance(lr, list) and lr:
            constraints += ("\n\nPermanent rules saved by Lorenzo:\n" +
                            "\n".join(f"- {r}" for r in lr))
        return constraints if constraints else "No standing meal constraints recorded."
    except Exception:
        return "Constraints unavailable."

def _get_lucy_capacity(iso: str) -> str:
    try:
        from render_morning_anchor import _get_anchor_state
        anchor = _get_anchor_state(iso)
        cap = anchor.get("capacity", "").strip().lower()
        if cap == "high":
            return "HIGH — full energy, Lauren can handle more involved cooking."
        elif cap == "medium":
            return "MEDIUM — moderate energy, prefer meals that don't require too much hands-on time."
        elif cap == "low":
            return "LOW — limited energy. Favor simple, minimal-effort meals."
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
            return "John is WFH today — he can help with lunch prep or keeping James occupied."
        elif "travel" in status.lower() or "away" in status.lower():
            return "John is traveling — Lauren is solo today. Keep meal complexity low."
        return f"John: {status}"
    except Exception:
        return ""

def _get_liturgical_note(iso: str) -> str:
    try:
        from datetime import date as _d
        d = _d.fromisoformat(iso)
        notes = []
        if d.weekday() == 4:
            easter = _get_easter(d.year)
            lent_start = easter - timedelta(days=46)
            lent_end   = easter - timedelta(days=1)
            if lent_start <= d <= lent_end:
                notes.append("FRIDAY IN LENT — no meat. Fish, eggs, legumes, or meatless dishes only.")
            else:
                notes.append("Friday — encourage a small act of penance (meatless meal preferred).")
        easter = _get_easter(d.year)
        ash_wed  = easter - timedelta(days=46)
        good_fri = easter - timedelta(days=2)
        if d == ash_wed:
            notes.append("ASH WEDNESDAY — full fast and abstinence. No meat, very simple meals only.")
        if d == good_fri:
            notes.append("GOOD FRIDAY — strict fast and abstinence. No meat. Very simple meals.")
        return " | ".join(notes) if notes else ""
    except Exception:
        return ""

def _get_easter(year: int) -> date:
    a = year % 19; b = year // 100; c = year % 100
    d = b // 4;    e = b % 4;       f = (b + 8) // 25
    g = (b - f + 1) // 3;           h = (19 * a + b - d - g + 15) % 30
    i = c // 4;    k = c % 4;       l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day   = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


# ─────────────────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────────────────

def build_lorenzo_context(iso: str, weekday: str, date_label: str) -> str:
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
        "on a gridiron. You carry his spirit: warmth, good humor, and calm under pressure.",
        "",
        f"Today is {weekday}, {date_label}.",
        "",
        "== THE McADAMS FAMILY ==",
        "Lauren (Mom) — the one you work for. A homeschooling Catholic wife and mother.",
        "  She manages the household, plans school days, and coordinates everything.",
        "  She is your partner in the kitchen — you plan, she executes (with the boys' help).",
        "John (Dad) — husband, works outside the home (or occasionally WFH).",
        "JP — 14 years old. Oldest son. Kitchen Role A: your best kitchen asset.",
        "  He can cook full meals, handle the stove unsupervised, and lead dinner prep.",
        "  Give him real ownership of meals. He rises to the challenge.",
        "Joseph — 12 years old. Kitchen Role B: excellent helper and sous chef.",
        "  Can prep, assemble, and run simple recipes with light guidance.",
        "Michael — 5 years old. Loves to help. Assign safe, simple tasks.",
        "  Stirring, washing vegetables, pouring measured ingredients — his specialty.",
        "James — 13 months old. In the high chair during meal prep. Not cooking.",
        "",
        "== KITCHEN CREW ==",
        "JP (14) — Role A: can lead full meals, unsupervised on stove. Give him real responsibility.",
        "Joseph (12) — Role B: skilled helper, can run simple recipes with light guidance.",
        "Michael (5) — one safe small job per meal. Stirring, washing, pouring.",
        "James (13 months) — high chair only.",
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
        "== DISTINGUISHING TEMPORARY ADJUSTMENTS FROM PERMANENT RULES ==",
        "This is CRITICAL. You must listen for cues about whether Lauren means something",
        "just for now, or as a new permanent household rule.",
        "",
        "TEMPORARY adjustments (handle in conversation only, do NOT save):",
        '- "Just for tonight", "this week", "I don\'t have X today", "skip it this time"',
        '- "Something easy today", "I forgot to defrost", "we\'re out of Y"',
        '- "Can we do something lighter?", "I\'m too tired for that today"",',
        "- Respond naturally: 'Got it — just for tonight, let's do...' or 'Easy week it is.'",
        "- Do NOT output a [RULE] tag for these. They live only in the conversation.",
        "",
        "PERMANENT rules (save with [RULE] tag and ask Lauren to confirm):",
        '- "Always", "never again", "from now on", "add this to our rules", "we never eat X"',
        '- "Joseph won\'t touch Y", "make a rule that...", "can you remember that..."',
        '- "This is a hard rule", "permanently", "going forward always"',
        "- When you detect a permanent rule, output it as: [RULE:add]the rule text[/RULE]",
        "  A button will appear for Lauren to save it with one tap.",
        "- If Lauren asks to REMOVE a rule: [RULE:remove]the rule text[/RULE]",
        "",
        "GRAY AREA: When unclear, ask: 'Is this just for now, or should I add it as a",
        "permanent rule?' Then act on her answer.",
        "",
        "MEAL PLAN UPDATES: When Lauren tells you what to put in specific slots,",
        "you can output: [MEAL_UPDATE:DayName:slot]meal name[/MEAL_UPDATE]",
        "This will save directly to the meal plan. Example:",
        "[MEAL_UPDATE:Monday:dinner]Sheet pan chicken thighs with roasted broccoli[/MEAL_UPDATE]",
        "Slots are: breakfast, lunch, dinner, snack.",
        "",
        "== YOUR CORE MEAL PLANNING PHILOSOPHY ==",
        "SIMPLICITY FIRST:",
        "- Every meal must be achievable by a tired homeschool mom.",
        "- LOW capacity: 20 min or less hands-on, or a kid can lead. No multi-component meals.",
        "- MEDIUM: solid home cooking, 30-45 min prep, one main + simple sides.",
        "- HIGH: Lauren can handle something more ambitious. Still be reasonable.",
        "",
        "ONE FAMILY MEAL — no short-order cooking.",
        "If a component a child dislikes, suggest a simple modification (e.g., sauce on the side).",
        "",
        "BATCH COOKING & LEFTOVERS: If dinner works as next day's lunch, say so.",
        "Suggest doubling recipes. Flag 'cook once, eat twice' opportunities proactively.",
        "",
        "USE WHAT'S ON HAND: Build meals around existing inventory before suggesting shopping.",
        "Flag items that need to be used soon before they go bad.",
        "",
        "BOYS IN THE KITCHEN:",
        "JP leads 2-3 dinners per week. Joseph has regular tasks most dinners.",
        "Michael always has one small safe job. Note who leads or helps each step.",
        "",
        "GROCERIES: Feed 6 people (4 boys, one a teenager — volume matters).",
        "Economical proteins: chicken thighs, ground beef, eggs, beans, tuna.",
        "When suggesting a new dish, note ingredients needed for shopping.",
        "",
        "AUGUST 10 — Feast of Saint Lawrence: suggest something grilled. Obviously.",
        "",
        "== YOUR PERSONALITY ==",
        "- Warm, confident, a little Italian in spirit. You love food and this family.",
        "- Address Lauren directly and personally by name.",
        "- Practical, never fussy. No precious techniques or hard-to-find ingredients.",
        "- Dry sense of humor. Allowed to be funny about kitchen disasters, teenagers who",
        "  can suddenly cook, and the chaos of feeding a large family.",
        "- Never lecture. Offer alternatives gently — if she says no, help her execute her plan.",
        "- Celebrate small wins: a kid eating a new vegetable, a good batch-cook Sunday.",
        "- You are Saint Lawrence's namesake. You do not panic under pressure.",
        "- FORMATTING: Never use markdown. No ##, no **, no *. Plain text only.",
        "  Use simple dashes or numbers for lists. Keep responses focused and scannable.",
        "- CRITICAL: Ask only ONE question at a time. Never stack questions.",
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
        opener_prompt = f"Good morning, Lorenzo! It's {date_label}. What should we cook this week?"
        quick_prompts = [
            ("Plan this week's dinners",   "Plan this week's dinners for the family."),
            ("What can JP cook tonight?",  "What's a good dinner for JP to lead tonight?"),
            ("Low-effort dinner ideas",    "I have low energy today. Give me the easiest possible dinner."),
            ("Use what's in my fridge",    "Look at my inventory and tell me what meals I can make without shopping."),
            ("Prep for the week",          "Help me think through Sunday meal prep for the week ahead."),
        ]
    elif h < 17:
        greeting      = "What's for dinner?"
        phase_label   = "Afternoon kitchen"
        phase_color   = "#1a6050"
        opener_prompt = f"Lorenzo, it's {date_label}. I need to figure out dinner. What are we making?"
        quick_prompts = [
            ("Quick dinner for tonight",   "I need dinner in 30 minutes or less. What do we make?"),
            ("JP leads tonight",           "JP is leading dinner tonight. What should he make?"),
            ("Use what's in the fridge",   "Plan dinner using what I already have in the fridge and pantry."),
            ("Grocery run list",           "What should I pick up today to fill out the week's meals?"),
            ("Something new",              "Suggest a new dish the whole family will probably enjoy."),
        ]
    else:
        greeting      = "Planning tomorrow's table."
        phase_label   = "Evening planning"
        phase_color   = "#4a3a8a"
        opener_prompt = f"Lorenzo, let's plan tomorrow's meals and any overnight prep needed."
        quick_prompts = [
            ("Tomorrow's meals",           "Walk me through tomorrow's breakfast, lunch, and dinner."),
            ("Overnight prep",             "What can I prep tonight to make tomorrow easier?"),
            ("Slow cooker idea",           "Suggest something I can put in the slow cooker tonight or early tomorrow."),
            ("Leftover plan",              "What leftovers do I have and how can I use them tomorrow?"),
            ("Shopping list",              "Build me a quick shopping list for tomorrow's meals."),
        ]

    history     = _load_lorenzo_history_safe()
    has_history = bool(history)
    history_js  = json.dumps([
        {"role": m["role"], "content": m.get("content", "")}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content", "")
    ])

    quick_buttons = "".join(
        f'<button onclick="lzQuick({_ej(prompt)})" '
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

    new_conv_btn = (
        '<form method="POST" action="/lorenzo-clear-history" style="display:inline;">'
        '<button type="submit" style="background:none;border:none;font-size:0.72em;'
        'color:#bbb;cursor:pointer;font-family:inherit;padding:0;">&#10005; New conversation</button>'
        '</form>'
    ) if has_history else ''

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
@keyframes lz-pulse{{
  0%,100%{{transform:scale(1);opacity:1;}}
  50%{{transform:scale(1.18);opacity:0.8;}}
}}
</style>
</head>
<body>

<div style="max-width:760px;margin:0 auto;padding:20px 16px 200px;">

    <!-- Back + phase label -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
        <a href="/" style="font-size:0.82em;color:#aaa;text-decoration:none;">&larr; Dashboard</a>
        <div style="display:flex;align-items:center;gap:14px;">
            {new_conv_btn}
            <a href="/meals" style="font-size:0.78em;color:#8b3a1a;text-decoration:none;">&#127869; Meal Planner</a>
            <span style="font-size:0.78em;color:#aaa;">{phase_dot}{escape(phase_label)}</span>
        </div>
    </div>

    <!-- Lorenzo header -->
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:24px;">
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
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;">
        {quick_buttons}
    </div>

    <!-- Capacity selector -->
    <div style="background:#fdfaf7;border:1px solid #ede7e0;border-radius:10px;
                padding:10px 14px;margin-bottom:20px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span style="font-size:0.8em;color:#888;font-weight:600;white-space:nowrap;">My energy today:</span>
        <div style="display:flex;gap:6px;">
            <button id="cap-high"   onclick="setCapacity('high')"
                    style="padding:4px 12px;border-radius:20px;font-size:0.78em;font-weight:600;
                           border:1.5px solid #2d5016;background:white;color:#2d5016;cursor:pointer;font-family:inherit;">
                High
            </button>
            <button id="cap-medium" onclick="setCapacity('medium')"
                    style="padding:4px 12px;border-radius:20px;font-size:0.78em;font-weight:600;
                           border:1.5px solid #c49020;background:white;color:#c49020;cursor:pointer;font-family:inherit;">
                Medium
            </button>
            <button id="cap-low"    onclick="setCapacity('low')"
                    style="padding:4px 12px;border-radius:20px;font-size:0.78em;font-weight:600;
                           border:1.5px solid #c0392b;background:white;color:#c0392b;cursor:pointer;font-family:inherit;">
                Low
            </button>
        </div>
        <span id="cap-note" style="font-size:0.78em;color:#aaa;font-style:italic;"></span>
    </div>

    <!-- Chat history -->
    <div id="lz-history" class="lz-bubble-wrap" style="min-height:40px;margin-bottom:20px;"></div>

    <!-- Thinking indicator -->
    <div id="lz-thinking" style="display:none;font-size:0.82em;color:#aaa;font-style:italic;padding:4px 0;margin-bottom:12px;">
        Lorenzo is thinking&hellip;
    </div>

</div>

<!-- Attachment preview -->
<div id="lz-attach-preview"
     style="display:none;position:fixed;bottom:152px;left:0;right:0;
            background:#fffbf5;border-top:1px solid #e4dbd2;padding:8px 14px;z-index:498;">
    <div style="display:flex;align-items:center;gap:10px;">
        <img id="lz-attach-img" src="" alt="attachment"
             style="max-height:60px;max-width:72px;border-radius:8px;object-fit:cover;border:1px solid #e4dbd2;">
        <span style="font-size:0.82em;color:#888;flex:1;">Image ready to send</span>
        <button onclick="lzClearAttach()"
                style="background:#fee2e2;border:none;color:#ef4444;border-radius:8px;
                       padding:4px 10px;cursor:pointer;font-size:0.8em;font-family:inherit;">
            &#10005; Remove
        </button>
    </div>
</div>

<!-- Listening overlay -->
<div id="lz-listening-overlay"
     style="display:none;position:fixed;bottom:170px;left:0;right:0;z-index:499;
            flex-direction:column;align-items:center;justify-content:center;gap:4px;
            background:rgba(255,255,255,0.97);border-top:1px solid #f0ebe4;padding:10px 0;">
    <div style="width:52px;height:52px;border-radius:50%;background:#ef4444;
                display:flex;align-items:center;justify-content:center;
                font-size:1.5em;animation:lz-pulse 1.2s ease-in-out infinite;">&#127908;</div>
    <div style="font-size:0.82em;color:#ef4444;font-weight:600;">Listening&hellip;</div>
    <div style="font-size:0.72em;color:#aaa;">Tap mic to stop</div>
</div>

<!-- Input bar -->
<div id="lz-input-bar"
     style="position:fixed;bottom:64px;left:0;right:0;
            background:white;border-top:1px solid #e4dbd2;
            padding:6px 14px 10px;z-index:500;display:flex;flex-direction:column;gap:6px;">
    <!-- Voice toggle strip -->
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <button id="lz-voice-btn" onclick="lzToggleVoice()" title="Toggle read-aloud"
                style="padding:4px 12px;border-radius:20px;font-size:0.76em;font-weight:600;
                       border:1.5px solid #e4dbd2;background:white;color:#888;cursor:pointer;
                       font-family:inherit;transition:all 0.2s;white-space:nowrap;">
            &#128266; Read aloud: OFF
        </button>
        <button id="lz-wake-btn" onclick="lzToggleWake()" title="Toggle Hey Lorenzo wake word"
                style="padding:4px 12px;border-radius:20px;font-size:0.76em;font-weight:600;
                       border:1.5px solid #e4dbd2;background:white;color:#888;cursor:pointer;
                       font-family:inherit;transition:all 0.2s;white-space:nowrap;">
            &#127908; Hey Lorenzo: OFF
        </button>
        <button id="lz-voice-pick-btn" onclick="lzOpenVoicePanel()" title="Choose Lorenzo's voice"
                style="padding:4px 12px;border-radius:20px;font-size:0.76em;font-weight:600;
                       border:1.5px solid #e4dbd2;background:white;color:#888;cursor:pointer;
                       font-family:inherit;transition:all 0.2s;white-space:nowrap;">
            &#127897; Voice
        </button>
    </div>
    <!-- Voice picker panel -->
    <div id="lz-voice-panel"
         style="display:none;position:fixed;inset:0;z-index:900;
                flex-direction:column;justify-content:flex-end;
                background:rgba(0,0,0,0.45);"
         onclick="if(event.target===this)lzCloseVoicePanel()">
        <div style="background:white;border-radius:18px 18px 0 0;
                    max-height:72vh;display:flex;flex-direction:column;
                    padding:0 0 env(safe-area-inset-bottom) 0;">
            <div style="display:flex;align-items:center;justify-content:space-between;
                        padding:14px 18px 10px;border-bottom:1px solid #f0ebe4;">
                <span style="font-weight:700;font-size:1em;color:#3d2b1f;">Choose Lorenzo's Voice</span>
                <button onclick="lzCloseVoicePanel()"
                        style="background:none;border:none;font-size:1.4em;cursor:pointer;
                               color:#888;line-height:1;padding:0 4px;">&#10005;</button>
            </div>
            <p style="font-size:0.75em;color:#999;margin:6px 18px 4px;line-height:1.4;">
                AI voices from OpenAI. Hit <b>&#9654; Sample</b> to hear, then <b>Use</b> to select.
            </p>
            <div id="lz-voice-list" style="overflow-y:auto;padding:4px 18px 20px;flex:1;"></div>
        </div>
    </div>
    <!-- Text / mic / send row -->
    <div style="display:flex;gap:8px;align-items:flex-end;">
        <input type="file" id="lz-file-input" accept="image/*"
               style="display:none;" onchange="lzAttachChange(this)">
        <button onclick="document.getElementById('lz-file-input').click()" title="Attach a photo"
                style="padding:9px 11px;background:#faf8f5;border:1.5px solid #e4dbd2;
                       border-radius:12px;cursor:pointer;font-size:1.05em;flex-shrink:0;
                       align-self:flex-end;line-height:1;">
            &#128206;
        </button>
        <button onclick="lzMicToggle()" title="Voice input" id="lz-mic-btn"
                style="padding:9px 11px;background:#faf8f5;border:1.5px solid #e4dbd2;
                       border-radius:12px;cursor:pointer;font-size:1.05em;flex-shrink:0;
                       align-self:flex-end;line-height:1;transition:all 0.15s;">
            &#127908;
        </button>
        <button id="lz-stop-btn" onclick="lzStop()" title="Stop Lorenzo talking"
                style="display:none;padding:9px 13px;background:#fee2e2;border:1.5px solid #ef4444;
                       border-radius:12px;cursor:pointer;font-size:1em;font-weight:700;flex-shrink:0;
                       align-self:flex-end;line-height:1;color:#dc2626;">
            &#9209;
        </button>
        <textarea id="lz-input" rows="1"
                  placeholder="Ask Lorenzo about meals, cooking, groceries&hellip;"
                  onkeydown="if(event.key==='Enter'&&!event.shiftKey){{event.preventDefault();lzSend();}}"
                  oninput="this.style.height='auto';this.style.height=Math.min(this.scrollHeight,120)+'px';"
                  style="flex:1;resize:none;overflow:hidden;font-family:inherit;font-size:16px;
                         padding:10px 14px;border:1.5px solid #e4dbd2;border-radius:12px;
                         outline:none;line-height:1.5;max-height:120px;background:white;">
        </textarea>
        <button onclick="lzSend()"
                style="padding:10px 18px;background:#8b3a1a;color:white;border:none;
                       border-radius:12px;cursor:pointer;font-size:0.88em;font-weight:600;
                       font-family:inherit;flex-shrink:0;align-self:flex-end;">
            Send
        </button>
    </div>
</div>

<script>
var _lzIso       = {_ej(iso)};
var _lzHistory   = {history_js};
var _lzCapacity  = '';
var _lzAttached  = null;

// ── Voice state ──────────────────────────────────────────────────────────────
var _lzVoiceEnabled = localStorage.getItem('lz_voice') === 'true';
var _lzWakeEnabled  = localStorage.getItem('lz_wake')  === 'true';
var _lzIsRecording  = false;
var _lzLastWasVoice = false;
var _lzMainRecog    = null;
var _lzWakeRecog    = null;
var _lzTtsFirstFired  = false;
var _lzTtsFull        = null;
var _lzTtsFirstEndPos = 0;
var _lzAudioEl = new Audio();
var _lzVoiceName = localStorage.getItem('lz_voice_name') || 'onyx';

var _LZ_VOICES = [
    {{id:'alloy',   label:'Alloy',   desc:'Neutral, balanced'}},
    {{id:'echo',    label:'Echo',    desc:'Warm, conversational'}},
    {{id:'fable',   label:'Fable',   desc:'Expressive storyteller'}},
    {{id:'onyx',    label:'Onyx',    desc:'Deep, authoritative (default)'}},
    {{id:'nova',    label:'Nova',    desc:'Bright, friendly'}},
    {{id:'shimmer', label:'Shimmer', desc:'Clear, warm'}},
    {{id:'coral',   label:'Coral',   desc:'Warm, natural'}},
    {{id:'sage',    label:'Sage',    desc:'Calm, measured'}},
    {{id:'ash',     label:'Ash',     desc:'Gentle, steady'}},
];

// ── Capacity ─────────────────────────────────────────────────────────────────
function setCapacity(level) {{
    _lzCapacity = level;
    ['high','medium','low'].forEach(function(l) {{
        var btn = document.getElementById('cap-' + l);
        btn.style.opacity = (l === level) ? '1' : '0.5';
        btn.style.fontWeight = (l === level) ? '800' : '600';
    }});
    var notes = {{
        high:   'Full energy \u2014 Lorenzo will plan accordingly.',
        medium: 'Moderate energy \u2014 straightforward meals.',
        low:    'Low energy \u2014 keeping it simple and easy.'
    }};
    document.getElementById('cap-note').textContent = notes[level] || '';
}}

// ── Image attachment ─────────────────────────────────────────────────────────
function lzAttachChange(input) {{
    if (!input.files || !input.files[0]) return;
    var file = input.files[0];
    var reader = new FileReader();
    reader.onload = function(e) {{
        var img = new Image();
        img.onload = function() {{
            var MAX = 1024;
            var w = img.width, h = img.height;
            if (w > MAX || h > MAX) {{
                if (w > h) {{ h = Math.round(h * MAX / w); w = MAX; }}
                else {{ w = Math.round(w * MAX / h); h = MAX; }}
            }}
            var canvas = document.createElement('canvas');
            canvas.width = w; canvas.height = h;
            canvas.getContext('2d').drawImage(img, 0, 0, w, h);
            var dataUrl = canvas.toDataURL('image/jpeg', 0.82);
            _lzAttached = {{b64: dataUrl.split(',')[1], mediaType: 'image/jpeg', dataUrl: dataUrl}};
            document.getElementById('lz-attach-img').src = dataUrl;
            document.getElementById('lz-attach-preview').style.display = '';
            input.value = '';
        }};
        img.src = e.target.result;
    }};
    reader.readAsDataURL(file);
}}

function lzClearAttach() {{
    _lzAttached = null;
    document.getElementById('lz-attach-preview').style.display = 'none';
    document.getElementById('lz-attach-img').src = '';
}}

// ── Bubble rendering ─────────────────────────────────────────────────────────
function _lzRenderUserBubble(text, imageDataUrl) {{
    var hist = document.getElementById('lz-history');
    var wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;align-items:flex-end;margin-bottom:0;';
    if (imageDataUrl) {{
        var imgEl = document.createElement('img');
        imgEl.src = imageDataUrl;
        imgEl.style.cssText = 'max-width:200px;max-height:140px;border-radius:10px;margin-bottom:4px;border:1px solid #ddd;';
        wrap.appendChild(imgEl);
    }}
    if (text) {{
        var div = document.createElement('div');
        div.className = 'lz-bubble-user';
        div.textContent = text;
        wrap.appendChild(div);
    }}
    hist.appendChild(wrap);
}}

function _lzRenderBubble(role, text) {{
    var hist = document.getElementById('lz-history');
    var wrap = document.createElement('div');
    var div  = document.createElement('div');
    div.className = (role === 'user') ? 'lz-bubble-user' : 'lz-bubble-lz';
    div.textContent = text;
    div._wrap = wrap;
    wrap.appendChild(div);
    hist.appendChild(wrap);
    return div;
}}

// ── Strip hidden tags from display text ──────────────────────────────────────
function _lzStrip(text) {{
    return text
        .replace(/\[RULE:(add|remove)\][\s\S]*?\[\/RULE\]/g, '')
        .replace(/\[MEAL_UPDATE:[^\]]+\][\s\S]*?\[\/MEAL_UPDATE\]/g, '')
        .replace(/\s+$/, '');
}}

// ── TTS helpers ───────────────────────────────────────────────────────────────
function _lzUnlockAudio() {{
    try {{
        if (_lzAudioEl.src) return;
        _lzAudioEl.volume = 0;
        _lzAudioEl.play().catch(function(){{}});
        _lzAudioEl.pause();
        _lzAudioEl.volume = 1;
    }} catch(e) {{}}
}}

function _lzCleanForTts(t) {{
    return t.replace(/\\*/g,'').replace(/^[-•]\s/gm,'').replace(/\n+/g,' ').trim();
}}

function _lzFetchAndPlay(text, onEnd) {{
    fetch('/lucy-tts', {{
        method:'POST',
        headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
        body:'text=' + encodeURIComponent(text.substring(0,4096))
           + '&voice=' + encodeURIComponent(_lzVoiceName)
    }})
    .then(function(r) {{ return r.ok ? r.blob() : null; }})
    .then(function(blob) {{
        if (!blob) return;
        var url = URL.createObjectURL(blob);
        _lzAudioEl.src = url;
        _lzAudioEl.onended = function() {{
            URL.revokeObjectURL(url);
            _lzUpdateStopBtn(false);
            if (onEnd) onEnd();
        }};
        _lzAudioEl.play().then(function() {{
            _lzUpdateStopBtn(true);
        }}).catch(function(){{}});
    }}).catch(function(){{}});
}}

function lzSpeak(text) {{
    if (!_lzVoiceEnabled && !_lzLastWasVoice) return;
    var clean = _lzCleanForTts(text);
    if (clean.length < 5) return;
    _lzFetchAndPlay(clean.substring(0,3000), null);
}}

function lzSpeakTap(text, btn) {{
    if (btn) btn.disabled = true;
    var clean = _lzCleanForTts(text);
    _lzFetchAndPlay(clean.substring(0,3000), function() {{
        if (btn) btn.disabled = false;
    }});
}}

function _lzUpdateStopBtn(show) {{
    var sb = document.getElementById('lz-stop-btn');
    if (sb) sb.style.display = show ? '' : 'none';
}}

function lzStop() {{
    _lzAudioEl.pause();
    _lzAudioEl.src = '';
    _lzUpdateStopBtn(false);
    _lzTtsFull = null;
    if (_lzVoiceEnabled || _lzLastWasVoice) {{
        _lzLastWasVoice = false;
        _lzUnlockAudio();
        lzStartListening();
    }}
}}

// ── Voice read-aloud toggle ───────────────────────────────────────────────────
function _lzUpdateVoiceBtn() {{
    var btn = document.getElementById('lz-voice-btn');
    if (!btn) return;
    if (_lzVoiceEnabled) {{
        btn.textContent = '\U0001F50A Read aloud: ON';
        btn.style.background  = '#f0f8e8';
        btn.style.borderColor = '#8ab870';
        btn.style.color       = '#2d5016';
    }} else {{
        btn.textContent = '\U0001F50A Read aloud: OFF';
        btn.style.background  = 'white';
        btn.style.borderColor = '#e4dbd2';
        btn.style.color       = '#888';
    }}
}}

function lzToggleVoice() {{
    _lzVoiceEnabled = !_lzVoiceEnabled;
    localStorage.setItem('lz_voice', _lzVoiceEnabled);
    _lzUpdateVoiceBtn();
}}

// ── Wake word ─────────────────────────────────────────────────────────────────
function _lzUpdateWakeBtn() {{
    var btn = document.getElementById('lz-wake-btn');
    if (!btn) return;
    if (_lzWakeEnabled) {{
        btn.textContent = '\U0001F3A4 Hey Lorenzo: ON';
        btn.style.background  = '#fef9e8';
        btn.style.borderColor = '#d4af37';
        btn.style.color       = '#7a5c00';
    }} else {{
        btn.textContent = '\U0001F3A4 Hey Lorenzo: OFF';
        btn.style.background  = 'white';
        btn.style.borderColor = '#e4dbd2';
        btn.style.color       = '#888';
    }}
}}

function lzToggleWake() {{
    _lzWakeEnabled = !_lzWakeEnabled;
    localStorage.setItem('lz_wake', _lzWakeEnabled);
    _lzUpdateWakeBtn();
    if (_lzWakeEnabled) {{ lzStartWakeWord(); }}
    else {{ lzStopWakeWord(); }}
}}

function _lzSetMicState(active) {{
    _lzIsRecording = active;
    var btn = document.getElementById('lz-mic-btn');
    var ol  = document.getElementById('lz-listening-overlay');
    if (btn) {{
        btn.textContent       = active ? '\u23F9' : '\U0001F3A4';
        btn.style.background  = active ? '#fee2e2' : '#faf8f5';
        btn.style.borderColor = active ? '#ef4444' : '#e4dbd2';
        btn.style.color       = active ? '#ef4444' : 'inherit';
    }}
    if (ol) ol.style.display = active ? 'flex' : 'none';
}}

function lzMicToggle() {{
    if (!_lzAudioEl.paused) {{
        _lzAudioEl.pause(); _lzAudioEl.src = ''; _lzTtsFull = null;
        _lzUpdateStopBtn(false);
        _lzUnlockAudio();
        lzStartListening();
        return;
    }}
    if (window.speechSynthesis && window.speechSynthesis.speaking) {{
        window.speechSynthesis.cancel();
        lzStartListening();
        return;
    }}
    _lzUnlockAudio();
    if ('speechSynthesis' in window && !_lzIsRecording) {{
        var unlock = new SpeechSynthesisUtterance(' ');
        unlock.volume = 0; unlock.rate = 10;
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(unlock);
    }}
    if (_lzIsRecording) {{ lzStopListening(); }}
    else {{ lzStartListening(); }}
}}

function lzStartListening() {{
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {{ alert('Voice input not supported on this browser.'); return; }}
    lzStopWakeWord();
    if (_lzMainRecog) {{ try {{ _lzMainRecog.stop(); }} catch(e) {{}} _lzMainRecog = null; }}
    _lzMainRecog = new SR();
    _lzMainRecog.continuous = false;
    _lzMainRecog.interimResults = true;
    _lzMainRecog.lang = 'en-US';
    _lzSetMicState(true);
    var input = document.getElementById('lz-input');
    var _sentFromResult = false;
    _lzMainRecog.onresult = function(e) {{
        var transcript = '';
        for (var i = 0; i < e.results.length; i++) transcript += e.results[i][0].transcript;
        if (input) input.value = transcript;
        if (e.results[e.results.length - 1].isFinal) {{
            _sentFromResult = true;
            _lzSetMicState(false);
            if (_lzWakeEnabled) setTimeout(lzStartWakeWord, 1200);
            _lzLastWasVoice = true;
            lzSend();
        }}
    }};
    _lzMainRecog.onerror = function(e) {{
        _lzSetMicState(false);
        if (_lzWakeEnabled && !_lzIsRecording) setTimeout(lzStartWakeWord, 1500);
    }};
    _lzMainRecog.onend = function() {{
        if (_lzIsRecording && !_sentFromResult) {{
            _lzSetMicState(false);
            var pending = document.getElementById('lz-input');
            if (pending && pending.value.trim()) {{ _lzLastWasVoice = true; lzSend(); return; }}
        }} else if (_lzIsRecording) {{ _lzSetMicState(false); }}
        if (_lzWakeEnabled && !_lzIsRecording) setTimeout(lzStartWakeWord, 1000);
    }};
    try {{ _lzMainRecog.start(); }} catch(e) {{ _lzSetMicState(false); }}
}}

function lzStopListening() {{
    if (_lzMainRecog) {{ try {{ _lzMainRecog.stop(); }} catch(e) {{}} _lzMainRecog = null; }}
    _lzSetMicState(false);
    if (_lzWakeEnabled) setTimeout(lzStartWakeWord, 800);
}}

function lzStartWakeWord() {{
    if (!_lzWakeEnabled || _lzIsRecording) return;
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    lzStopWakeWord();
    _lzWakeRecog = new SR();
    _lzWakeRecog.continuous = false;
    _lzWakeRecog.interimResults = false;
    _lzWakeRecog.lang = 'en-US';
    _lzWakeRecog.onresult = function(e) {{
        var raw = e.results[0][0].transcript.toLowerCase().replace(/[^a-z ]/g, ' ');
        var detected = (raw.indexOf('hey lorenzo') >= 0 || raw.indexOf('hey lorenso') >= 0 ||
                        raw.indexOf('hey lorenz')  >= 0 || raw.indexOf('a lorenzo')   >= 0);
        if (detected) {{
            _lzPlayBeep();
            setTimeout(lzStartListening, 450);
        }} else {{
            if (_lzWakeEnabled && !_lzIsRecording) setTimeout(lzStartWakeWord, 250);
        }}
    }};
    _lzWakeRecog.onerror = function() {{
        if (_lzWakeEnabled && !_lzIsRecording) setTimeout(lzStartWakeWord, 2000);
    }};
    _lzWakeRecog.onend = function() {{
        if (_lzWakeEnabled && !_lzIsRecording) setTimeout(lzStartWakeWord, 350);
    }};
    try {{ _lzWakeRecog.start(); }} catch(e) {{}}
}}

function lzStopWakeWord() {{
    if (_lzWakeRecog) {{ try {{ _lzWakeRecog.stop(); }} catch(e) {{}} _lzWakeRecog = null; }}
}}

function _lzPlayBeep() {{
    try {{
        var ctx = new (window.AudioContext || window.webkitAudioContext)();
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        osc.type = 'sine'; osc.frequency.value = 880;
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
        osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.3);
    }} catch(e) {{}}
}}

// ── Voice picker panel ────────────────────────────────────────────────────────
function lzOpenVoicePanel() {{
    var panel = document.getElementById('lz-voice-panel');
    panel.style.display = 'flex';
    var list = document.getElementById('lz-voice-list');
    list.innerHTML = '';
    _LZ_VOICES.forEach(function(v) {{
        var row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #f0ebe4;';
        var info = document.createElement('div');
        info.style.cssText = 'flex:1;';
        info.innerHTML = '<div style="font-weight:700;font-size:0.9em;color:#3d2b1f;">' + v.label + '</div>'
            + '<div style="font-size:0.75em;color:#999;">' + v.desc + '</div>';
        var sampleBtn = document.createElement('button');
        sampleBtn.textContent = '\u25B6 Sample';
        sampleBtn.style.cssText = 'padding:5px 10px;font-size:0.78em;border-radius:7px;border:1px solid #e4dbd2;'
            + 'background:#faf8f5;cursor:pointer;font-family:inherit;color:#555;white-space:nowrap;';
        (function(vid) {{
            sampleBtn.onclick = function() {{
                fetch('/lucy-tts', {{
                    method:'POST',
                    headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
                    body:'text=' + encodeURIComponent('Buongiorno! I am Lorenzo, your personal chef.') + '&voice=' + encodeURIComponent(vid)
                }}).then(function(r) {{ return r.blob(); }}).then(function(blob) {{
                    var url = URL.createObjectURL(blob);
                    var a = new Audio(url);
                    a.play();
                    a.onended = function() {{ URL.revokeObjectURL(url); }};
                }});
            }};
        }})(v.id);
        var useBtn = document.createElement('button');
        useBtn.textContent = (v.id === _lzVoiceName) ? '\u2713 Selected' : 'Use';
        useBtn.style.cssText = 'padding:5px 12px;font-size:0.78em;border-radius:7px;border:none;cursor:pointer;'
            + 'font-family:inherit;font-weight:700;white-space:nowrap;'
            + (v.id === _lzVoiceName ? 'background:#8b3a1a;color:white;' : 'background:#3b2a1a;color:white;');
        (function(vid, vLabel, btn) {{
            btn.onclick = function() {{
                _lzVoiceName = vid;
                localStorage.setItem('lz_voice_name', vid);
                var pb = document.getElementById('lz-voice-pick-btn');
                if (pb) pb.textContent = '\U0001F3A4 ' + vLabel;
                lzCloseVoicePanel();
            }};
        }})(v.id, v.label, useBtn);
        row.appendChild(info);
        row.appendChild(sampleBtn);
        row.appendChild(useBtn);
        list.appendChild(row);
    }});
}}

function lzCloseVoicePanel() {{
    document.getElementById('lz-voice-panel').style.display = 'none';
}}

// ── Quick prompt ──────────────────────────────────────────────────────────────
function lzQuick(prompt) {{
    var input = document.getElementById('lz-input');
    input.value = prompt;
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    input.focus();
}}

// ── Send ──────────────────────────────────────────────────────────────────────
function lzSend() {{
    var input = document.getElementById('lz-input');
    var msg   = input.value.trim();
    var img   = _lzAttached;
    if (!msg && !img) return;
    _lzUnlockAudio();
    _lzTtsFirstFired  = false;
    _lzTtsFull        = null;
    _lzTtsFirstEndPos = 0;
    _lzAudioEl.pause();
    _lzUpdateStopBtn(false);
    input.value = '';
    input.style.height = 'auto';

    _lzHistory.push({{role:'user', content: msg || '(image)'}});
    _lzRenderUserBubble(msg, img ? img.dataUrl : null);
    lzClearAttach();

    document.getElementById('lz-thinking').style.display = '';
    window.scrollTo(0, document.body.scrollHeight);

    var params = 'iso=' + encodeURIComponent(_lzIso)
        + '&capacity='   + encodeURIComponent(_lzCapacity)
        + '&message='    + encodeURIComponent(msg)
        + '&image_b64='  + encodeURIComponent(img ? img.b64 : '')
        + '&image_type=' + encodeURIComponent(img ? img.mediaType : '');

    fetch('/lorenzo-chat', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: params
    }}).then(function(r) {{
        document.getElementById('lz-thinking').style.display = 'none';
        if (!r.ok) {{
            _lzRenderBubble('lz', 'Lorenzo stepped away. Check that your API key is set in Settings.');
            return;
        }}
        var bubble  = _lzRenderBubble('lz', '');
        var full    = '';
        var reader  = r.body.getReader();
        var decoder = new TextDecoder();
        function read() {{
            return reader.read().then(function(res) {{
                if (res.done) {{
                    var clean = _lzStrip(full);
                    bubble.textContent = clean;
                    _lzHistory.push({{role:'assistant', content: clean}});
                    _lzTtsFull = clean;
                    if (!_lzTtsFirstFired) {{
                        lzSpeak(clean);
                    }} else {{
                        _lzLastWasVoice = false;
                    }}

                    // ── Tap-to-hear button ────────────────────────────────
                    if ('speechSynthesis' in window && bubble._wrap) {{
                        var spkRow = document.createElement('div');
                        spkRow.style.cssText = 'display:flex;justify-content:flex-start;margin-top:2px;';
                        var spkBtn = document.createElement('button');
                        spkBtn.textContent = '\U0001F50A Hear Lorenzo';
                        spkBtn.style.cssText = 'background:none;border:none;color:#8b3a1a;'
                            + 'font-size:0.75em;cursor:pointer;padding:2px 0;font-family:inherit;'
                            + 'text-decoration:underline;text-underline-offset:2px;opacity:0.8;';
                        (function(btn, txt) {{
                            btn.onclick = function() {{ lzSpeakTap(txt, btn); }};
                        }})(spkBtn, clean);
                        spkRow.appendChild(spkBtn);
                        if (bubble._wrap.firstChild && bubble._wrap.firstChild.nextSibling) {{
                            bubble._wrap.insertBefore(spkRow, bubble._wrap.firstChild.nextSibling);
                        }} else {{
                            bubble._wrap.appendChild(spkRow);
                        }}
                    }}

                    // ── Parse [RULE:add/remove]...[/RULE] — permanent rule buttons ──
                    var ruleRx = /\[RULE:(add|remove)\]([\s\S]*?)\[\/RULE\]/g;
                    var m;
                    while ((m = ruleRx.exec(full)) !== null) {{
                        (function(action, ruleText) {{
                            ruleText = ruleText.trim();
                            var ruleRow = document.createElement('div');
                            ruleRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-top:8px;'
                                + 'padding:8px 12px;background:#fff8f0;border:1px solid #e6b870;border-radius:8px;';
                            var ruleIcon = document.createElement('span');
                            ruleIcon.textContent = action === 'add' ? '\U0001F4CB' : '\U0001F5D1';
                            ruleIcon.style.cssText = 'font-size:1em;flex-shrink:0;';
                            var ruleMsg = document.createElement('span');
                            var preview = ruleText.length > 60 ? ruleText.substring(0,60)+'\u2026' : ruleText;
                            ruleMsg.textContent = (action === 'add' ? 'Permanent rule: ' : 'Remove rule: ') + preview;
                            ruleMsg.style.cssText = 'font-size:0.82em;color:#7a4500;flex:1;';
                            var ruleBtn = document.createElement('button');
                            ruleBtn.textContent = action === 'add' ? '\u2713 Save to meal rules' : '\u2713 Remove rule';
                            ruleBtn.style.cssText = 'padding:5px 12px;background:#8b3a1a;color:white;'
                                + 'border:none;border-radius:6px;font-size:0.78em;cursor:pointer;'
                                + 'font-family:inherit;font-weight:700;white-space:nowrap;flex-shrink:0;';
                            ruleBtn.onclick = function() {{
                                fetch('/lorenzo-rule-save', {{
                                    method: 'POST',
                                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                                    body: 'action=' + encodeURIComponent(action)
                                        + '&rule=' + encodeURIComponent(ruleText)
                                }}).then(function(r) {{
                                    if (r.ok) {{
                                        ruleBtn.textContent = '\u2713 Saved';
                                        ruleBtn.style.background = '#2d5016';
                                        ruleBtn.disabled = true;
                                    }}
                                }});
                            }};
                            ruleRow.appendChild(ruleIcon);
                            ruleRow.appendChild(ruleMsg);
                            ruleRow.appendChild(ruleBtn);
                            if (bubble._wrap) bubble._wrap.appendChild(ruleRow);
                        }})(m[1], m[2]);
                    }}

                    // ── Parse [MEAL_UPDATE:Day:slot]meal[/MEAL_UPDATE] ──────
                    var mealRx = /\[MEAL_UPDATE:([^:]+):([^\]]+)\]([\s\S]*?)\[\/MEAL_UPDATE\]/g;
                    while ((m = mealRx.exec(full)) !== null) {{
                        (function(mDay, mSlot, mMeal) {{
                            mMeal = mMeal.trim();
                            var mRow = document.createElement('div');
                            mRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-top:6px;'
                                + 'padding:7px 10px;background:#fffbea;border:1px solid #e6c84a;border-radius:8px;';
                            var mIcon = document.createElement('span');
                            mIcon.textContent = '\U0001F37D\uFE0F';
                            mIcon.style.cssText = 'font-size:1em;flex-shrink:0;';
                            var mMsg = document.createElement('span');
                            mMsg.textContent = mDay + ' ' + mSlot + ': ' + mMeal;
                            mMsg.style.cssText = 'font-size:0.82em;color:#7a5a00;flex:1;';
                            var mBtn = document.createElement('a');
                            mBtn.textContent = '\U0001F35D Meal Plan';
                            mBtn.href = '/meals';
                            mBtn.target = '_blank';
                            mBtn.style.cssText = 'padding:4px 12px;background:#b07d10;color:white;'
                                + 'text-decoration:none;border-radius:6px;font-size:0.8em;font-weight:700;'
                                + 'font-family:inherit;flex-shrink:0;';
                            mRow.appendChild(mIcon); mRow.appendChild(mMsg); mRow.appendChild(mBtn);
                            if (bubble._wrap) bubble._wrap.appendChild(mRow);
                        }})(m[1], m[2], m[3]);
                    }}

                    window.scrollTo(0, document.body.scrollHeight);
                    return;
                }}
                full += decoder.decode(res.value, {{stream:true}});
                bubble.textContent = _lzStrip(full);
                // Early TTS on first complete sentence
                if (!_lzTtsFirstFired && (_lzVoiceEnabled || _lzLastWasVoice)) {{
                    var s2 = _lzStrip(full);
                    var si = s2.search(/[.!?](?:\s|$)/);
                    if (si > 40) {{
                        _lzTtsFirstFired  = true;
                        _lzTtsFirstEndPos = si + 1;
                        var fc = _lzCleanForTts(s2.substring(0, si + 1));
                        if (fc.length > 20) {{
                            _lzFetchAndPlay(fc, function() {{
                                function _playRest() {{
                                    if (!_lzTtsFull) {{ setTimeout(_playRest, 150); return; }}
                                    if (_lzAudioEl.paused) {{
                                        var rt = _lzCleanForTts(_lzTtsFull.substring(_lzTtsFirstEndPos));
                                        if (rt.length > 20) _lzFetchAndPlay(rt.substring(0,3000), null);
                                    }}
                                }}
                                _playRest();
                            }});
                        }}
                    }}
                }}
                window.scrollTo(0, document.body.scrollHeight);
                return read();
            }});
        }}
        read().catch(function(e) {{ bubble.textContent = 'Stream error: ' + e.message; }});
    }}).catch(function(e) {{
        document.getElementById('lz-thinking').style.display = 'none';
        _lzRenderBubble('lz', 'Network error: ' + e.message);
    }});
}}

// ── Init ──────────────────────────────────────────────────────────────────────
window.addEventListener('load', function() {{
    _lzUpdateVoiceBtn();
    _lzUpdateWakeBtn();
    if (_lzWakeEnabled) {{ lzStartWakeWord(); }}
    // Show saved voice name on picker button
    var pb = document.getElementById('lz-voice-pick-btn');
    if (pb) {{
        _LZ_VOICES.forEach(function(v) {{
            if (v.id === _lzVoiceName) pb.textContent = '\U0001F3A4 ' + v.label;
        }});
    }}
    // Restore history or send opener
    var input = document.getElementById('lz-input');
    if ({json.dumps(has_history)}) {{
        for (var i = 0; i < _lzHistory.length; i++) {{
            var role = _lzHistory[i].role;
            var content = _lzHistory[i].content;
            if (role === 'user') {{
                _lzRenderUserBubble(content, null);
            }} else {{
                _lzRenderBubble('lz', content);
            }}
        }}
        window.scrollTo(0, document.body.scrollHeight);
    }} else {{
        input.value = {_ej(opener_prompt)};
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    }}
}});
</script>
</body>
</html>"""
