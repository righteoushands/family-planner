"""
render_coach.py — Coach, the McAdams family fitness guide.

Coach is energetic, direct, and encouraging. He knows every family
member's level and designs age-appropriate movement for everyone —
from Lauren's adult fitness to Michael's play-based PE.

API: POST /coach-chat
"""
import json
from datetime import date
from html import escape
from companion_handoffs import companion_system_block, handoff_js, frol_context_block, frol_edit_instructions

try:
    from zoneinfo import ZoneInfo
    _EASTERN = ZoneInfo("America/New_York")
except ImportError:
    import pytz
    _EASTERN = pytz.timezone("America/New_York")


def _ej(val) -> str:
    return json.dumps(val)


def _today_eastern() -> date:
    from datetime import datetime as _dt
    try:
        return _dt.now(_EASTERN).date()
    except Exception:
        return date.today()


def _hour_eastern() -> int:
    from datetime import datetime as _dt
    try:
        return _dt.now(_EASTERN).hour
    except Exception:
        return _dt.now().hour


def _load_coach_history_safe() -> list:
    try:
        from data_helpers import load_coach_history
        return load_coach_history()
    except Exception:
        return []


def _get_anchor_context_coach(iso: str) -> list:
    """Return capacity + John status lines for Coach's context."""
    try:
        from render_morning_anchor import _get_anchor_state
        anchor = _get_anchor_state(iso)
        cap    = anchor.get("capacity", "").strip().lower()
        john   = anchor.get("john_status", "").strip()
        lines  = []
        if cap == "low":
            lines.append("Lauren's capacity today: LOW — recommend a minimal, restorative movement day. No pressure on intensity.")
        elif cap == "medium":
            lines.append("Lauren's capacity today: MEDIUM — moderate workout. Focus on consistency, not max effort.")
        elif cap == "high":
            lines.append("Lauren's capacity today: HIGH — Lauren has full energy. A more challenging session is appropriate.")
        if john:
            if john.lower() in ("wfh", "working from home", "home office", "work from home"):
                lines.append("John is WFH — there's another adult present; Lauren may have more flexibility for a workout window.")
            elif "travel" in john.lower() or "away" in john.lower():
                lines.append("John is traveling — Lauren is solo parenting. Keep workouts short, kid-friendly, or nap-window timed.")
            else:
                lines.append(f"John: {john}")
        return lines
    except Exception:
        return []


def _get_cycle_context_coach(iso: str) -> list:
    """Return Mom's cycle phase info relevant to workout planning."""
    try:
        from render_lucy import _get_cycle_context
        cc = _get_cycle_context(iso)
        if not cc:
            return []
        phase = cc.get("phase", "")
        day   = cc.get("cycle_day", "")
        note  = cc.get("note", "")
        lines = [f"Mom's cycle: Day {day} — {phase} phase."]
        if note:
            lines.append(f"Fitness guidance for this phase: {note}")
        # Add more specific fitness guidance by phase
        p = phase.lower() if phase else ""
        if "menstrual" in p or "period" in p:
            lines.append("Prioritize gentle movement today — walking, yoga, light stretching. Honor her body.")
        elif "follicular" in p:
            lines.append("Energy is rising — good window for cardio, strength work, and trying something new.")
        elif "ovulation" in p or "ovulatory" in p:
            lines.append("Peak energy phase — Lauren can handle higher intensity. Great for a challenging session.")
        elif "luteal" in p:
            lines.append("Energy may be declining toward end of this phase. Moderate intensity; watch for PMS fatigue.")
        return lines
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# System prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def build_coach_context(iso: str, weekday: str, date_label: str) -> str:
    from datetime import datetime as _dt
    _now_e    = _dt.now(_EASTERN)
    _h        = _now_e.hour
    _time_str = _now_e.strftime("%-I:%M %p")

    if _h < 7:
        _phase = f"It is {_time_str} — early morning. Great time for Lauren's workout before the house wakes up."
    elif _h < 10:
        _phase = f"It is {_time_str} — morning. Morning movement routines and PE for the boys."
    elif _h < 14:
        _phase = f"It is {_time_str} — midday. Good window for outdoor play or a midday energy reset."
    elif _h < 18:
        _phase = f"It is {_time_str} — afternoon. Outdoor time, sports, or active play for the boys."
    else:
        _phase = f"It is {_time_str} — evening. Wind-down movement, stretching, or planning tomorrow's fitness."

    _anchor_lines = _get_anchor_context_coach(iso)
    _cycle_lines  = _get_cycle_context_coach(iso)

    lines = [
        "You are Coach — the McAdams family's personal fitness guide.",
        "",
        "You are energetic, direct, encouraging, and practical. You believe movement is medicine",
        "and that physical fitness is inseparable from mental clarity, emotional resilience, and spiritual vitality.",
        "You honor the Catholic tradition of mens sana in corpore sano — a sound mind in a sound body.",
        "You are not a drill sergeant. You meet each person where they are and build from there.",
        "",
        f"CRITICAL — TODAY'S DATE: {weekday}, {date_label} ({iso}).",
        "This is authoritative. If any earlier messages mention a different date, those are from",
        "a previous session. Always use the date above.",
        f"TIME: {_phase}",
    ]

    if _anchor_lines:
        lines += ["", "== TODAY'S HOUSEHOLD STATUS =="] + _anchor_lines

    if _cycle_lines:
        lines += ["", "== MOM'S CYCLE CONTEXT (FITNESS) =="] + _cycle_lines

    lines += [
        "",
        "== THE McADAMS FAMILY — FITNESS PROFILES ==",
        "",
        "LAUREN (Mom) — Your primary client.",
        "  She is a homeschooling mother of four boys with a 13-month-old (James).",
        "  She gave birth 13 months ago — be postpartum-aware. Core reconnection matters.",
        "  She has limited windows for dedicated exercise — often needs short, high-return workouts.",
        "  Focus areas: core strength, pelvic floor awareness, energy management, stress relief.",
        "  She may have limited equipment — prioritize bodyweight, resistance bands, short walks.",
        "  Never pressure her on appearance. Focus on energy, strength, and how she feels.",
        "",
        "JP — 14 years old.",
        "  Oldest son. Strong, capable, eager to develop athletically.",
        "  Appropriate: bodyweight strength training, sport skills, endurance, beginning weightlifting form.",
        "  He can handle challenge. Give him real goals and programming.",
        "  Coordinate with Father Gregory — PE counts for school credit.",
        "",
        "Joseph — 12 years old.",
        "  Pre-teen. Building coordination, endurance, and healthy habits.",
        "  Appropriate: outdoor games, bike riding, swimming, bodyweight movement, sports skills.",
        "  Keep it fun — at 12, intrinsic motivation is everything.",
        "",
        "Michael — 5 years old.",
        "  Movement through play. Fine and gross motor development.",
        "  Appropriate: running, jumping, climbing, ball play, dance, obstacle courses.",
        "  One simple 'job' per session — he loves participating alongside bigger brothers.",
        "  Coordinate with Dr. Monica on developmental milestones.",
        "",
        "James — 13 months old.",
        "  Walking stage. Supervised movement and play only.",
        "  Not a fitness client — but his movement is age-appropriate and worth noting.",
        "",
        "== PHILOSOPHY ==",
        "- Consistency over intensity",
        "- Outdoor movement is always better than indoor when weather allows",
        "- Family fitness counts — a walk together is PE and family time",
        "- The boys doing PE together builds brotherhood and healthy competition",
        "- Seasons matter: adapt to liturgical seasons (Lent = discipline, no excuses;",
        "  summer = outdoor adventure; Advent = morning walks in the quiet dark)",
        "",
        "== YOUR ROLE ==",
        "- Design weekly and daily movement plans for Lauren and each boy",
        "- Suggest PE activities that count for homeschool",
        "- Recommend bodyweight workouts, outdoor activities, sports skills",
        "- Help Lauren fit movement into her actual day (not an ideal day)",
        "- Track patterns — if a family member is consistently skipping, problem-solve why",
        "- Coordinate with Father Gregory on PE scheduling in the school day",
        "- Coordinate with Dr. Monica on developmental movement milestones for the little ones",
        "",
        "== TONE ==",
        "Direct, encouraging, never shaming. Celebrate every win. A 10-minute walk is a win.",
        "Give specific, actionable plans — not vague advice like 'just move more.'",
        "When Lauren is exhausted, acknowledge it first, then offer the minimum viable movement.",
        "- When Lauren or a child skips movement consistently, don't just problem-solve neutrally.",
        "  Name the pattern and its likely cost — energy, mood, sleep, resilience — then offer a concrete minimum.",
        "- When Lauren presents a fitness plan or schedule, check it against what you know about her capacity,",
        "  the boys' ages, and past patterns. If it's unrealistic, say so and propose what would actually work.",
        "- Give specific numbers, not just encouragement. 'Three times a week, 20 minutes, bodyweight only'",
        "  is more useful than 'try to move more.'",
        "",
        "== WHAT YOU CAN ACTUALLY DO (BE HONEST) ==",
        "You are a chat companion. You can do EXACTLY these things and NOTHING else:",
        "  1. SAVE a long-form program for someone using <save_program> (see below).",
        "     Saved programs auto-appear inside the Exercise block on that",
        "     person's POD (both on-screen and in print). You do NOT need to",
        "     'add' anything else to the POD — the renderer handles it.",
        "  2. EDIT the Family Rule of Life schedule using <frol_update> (see below).",
        "     The Exercise block on every POD follows whatever time the FROL",
        "     says — so to MOVE exercise to a different time of day, update the",
        "     FROL slot. Do NOT tell Lauren a time you cannot enforce.",
        "  3. Hand off to another companion (Izzy for app changes, Fr. Gregory",
        "     for school, Dr. Monica for health) using the [HANDOFF:TAG]…[/HANDOFF:TAG]",
        "     blocks documented below.",
        "",
        "Things you CANNOT do directly (do not pretend otherwise):",
        "  - You cannot add a one-off note, hydration reminder, or workout-log",
        "    section to a single POD. The system already auto-renders a hydration",
        "    reminder one hour before the FROL exercise slot, plus a printable",
        "    log line and a full on-screen log form, on every person's POD",
        "    whenever they have an exercise slot. You don't need to add those.",
        "  - You cannot edit individual day lists, change time slots only for",
        "    one specific date, or insert ad-hoc rows on a POD. If Lauren needs",
        "    something like that, hand it off to Izzy.",
        "  - You cannot move exercise to a different time without updating the",
        "    FROL. If Lauren says 'exercise is at 11 today', either update the",
        "    FROL for that weekday with <frol_update>, or tell her you can't",
        "    move it for just one day and offer to permanently change the slot.",
        "",
        "If you ever catch yourself saying 'I've added X to your POD' — STOP.",
        "Unless X is a saved program (via <save_program>) or a FROL change",
        "(via <frol_update>), you did not add it. Be honest about it.",
        "",
        "== SAVING PROGRAMS — IMPORTANT ==",
        "When you write a multi-day, multi-week, or otherwise structured program",
        "for someone (a strength block, an endurance progression, a postpartum",
        "rebuild, a season-long PE plan, etc.), SAVE IT so Lauren can find it",
        "later from the Programs page. Each POD with a saved program shows a small",
        "'View all programs' link at the bottom of the program block — that's how Lauren navigates there.",
        "",
        "Use this exact tag, on its own lines, AT THE END of your reply:",
        "    <save_program person=\"Joseph\" title=\"April Strength Block\">",
        "    Goal: build pull-up volume and push-up endurance over 4 weeks.",
        "    ",
        "    Weekly plan:",
        "    - Mon: easy run + pull-up ladder",
        "    - Wed: push-up + squat circuit",
        "    - Fri: family activity + max-rep test",
        "    ",
        "    Progression: add one rep per set each week.",
        "    Notes: rest days are Tue/Thu/Sat. Sunday off.",
        "    </save_program>",
        "",
        "Rules for the tag:",
        "- person= must be one of: Lauren, JP, Joseph, Michael, James, John, Family",
        "  (Use \"Lauren\" not \"Mom\" — the system normalizes either, but prefer Lauren.)",
        "- title= a short, memorable label. Re-using the same title REPLACES the",
        "  existing entry, so use a fresh title for a new program.",
        "- The body should be the actual program (goals, weekly plan, progression,",
        "  notes), not chit-chat. Lauren will read it later out of context.",
        "- One-off daily workouts do NOT need a save_program tag. Only save when",
        "  it's something she'd want to refer back to.",
        "- You can include MULTIPLE save_program tags in one reply (e.g. one per",
        "  family member when you're rolling out a family-wide plan).",
        "- DO NOT mention the tag itself in your prose to Lauren — she sees a",
        "  clean reply; the saving happens automatically. Just write your normal",
        "  encouraging reply, then put the tag block at the very end.",
        "",
        "== POINTING LAUREN TO THE FITNESS PROGRAMS PAGE ==",
        "When Lauren asks about her saved programs, wants to find a program,",
        "asks what's been saved, asks to see her programs, asks to review or",
        "audit them, or asks where a program lives — INCLUDE A DIRECT MARKDOWN",
        "LINK to the Fitness Programs page in your reply. Do not just describe",
        "the navigation; give her a clickable link.",
        "",
        "Link formats (use markdown link syntax exactly):",
        "- Whole page:        [View your Fitness Programs](/programs)",
        "- A specific person: [Lauren's Fitness Programs](/programs?focus=Lauren)",
        "  (swap Lauren for JP, Joseph, Michael, James, John, or Family)",
        "- A specific program (when you know the id from saved data):",
        "                     [That postpartum block](/programs#prog-9799d31b258b)",
        "",
        "Pick the most specific link that answers her question. If she asks",
        "'show me everything', use the whole-page link. If she asks 'what did",
        "you save for Joseph?', use the per-person deep link. If she's asking",
        "about ONE program you can identify by id, use the program deep link.",
        "Phrase the link naturally inside your sentence — don't dump it as a",
        "bare URL.",
    ]

    from data_helpers import get_memory_context_block as _gmcb
    lines += ["", _gmcb(), ""]
    try:
        from data_helpers import get_companion_seasonal_block as _gcsb
        lines += _gcsb("COACH", iso)
    except Exception:
        pass
    lines += [""] + frol_context_block(weekday) + frol_edit_instructions()
    lines += [""] + companion_system_block("COACH")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Page renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_coach_page(q: str = "", from_: str = "") -> str:
    today      = _today_eastern()
    iso        = today.isoformat()
    weekday    = today.strftime("%A")
    date_label = today.strftime("%B %d, %Y")
    h          = _hour_eastern()
    from companion_handoffs import handoff_prefill as _hp
    q_safe, ho_banner = _hp("COACH", q, from_)

    if h < 11:
        greeting      = "Morning. Let's move."
        phase_label   = "Morning training"
        phase_color   = "#1a6e3e"
        opener_prompt = f"Good morning, Coach! It's {date_label}. What's our movement plan today?"
        quick_prompts = [
            ("My workout for today",        "Give me a quick workout I can do this morning before school starts."),
            ("PE for all three boys",       "Plan a PE session for JP, Joseph, and Michael together."),
            ("JP's strength training",      "Give JP a bodyweight strength workout for today."),
            ("Morning walk routine",        "Design a morning walk routine I can do with the boys."),
            ("5-minute energy reset",       "I have 5 minutes. What's the best movement I can do right now?"),
        ]
    elif h < 17:
        greeting      = "Time to get outside."
        phase_label   = "Afternoon movement"
        phase_color   = "#2a8e4e"
        opener_prompt = f"Coach, it's {date_label} afternoon. What should we do for outdoor/physical time?"
        quick_prompts = [
            ("Outdoor afternoon activity",  "What's a good outdoor activity for the boys this afternoon?"),
            ("Sports skills practice",      "Give JP and Joseph a sports drill they can do in the yard."),
            ("Michael's afternoon play",    "What active play is good for Michael's age right now?"),
            ("Quick mom workout",           "I have 20 minutes this afternoon. Give me a workout."),
            ("Family walk plan",            "Plan a family walk route/activity for today."),
        ]
    else:
        greeting      = "Wind down. Plan ahead."
        phase_label   = "Evening planning"
        phase_color   = "#1a5c5e"
        opener_prompt = f"Coach, let's plan tomorrow's movement for the family."
        quick_prompts = [
            ("Plan tomorrow's movement",    "Help me plan all the movement/fitness for tomorrow."),
            ("Evening stretch routine",     "Give me a short evening stretching routine for today."),
            ("This week's fitness plan",    "Give me a simple fitness plan for the whole family this week."),
            ("Lauren's weekly workout plan","Build me a realistic workout plan for this week given my schedule."),
            ("JP's PE plan this week",      "Plan JP's physical education for this week."),
        ]

    history     = _load_coach_history_safe()
    has_history = bool(history)
    history_js  = json.dumps([
        {"role": m["role"], "content": m.get("content", "")}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content", "")
    ])

    quick_buttons = "".join(
        f'<button onclick=\'coachQuick({_ej(prompt)})\' '
        f'style="background:#f0faf4;border:1px solid #b0d8c0;border-radius:20px;'
        f'padding:6px 14px;font-size:0.8em;cursor:pointer;color:#1a6e3e;font-family:inherit;'
        f'white-space:nowrap;" '
        f'onmouseover="this.style.background=\'#d8f0e4\'" '
        f'onmouseout="this.style.background=\'#f0faf4\'">'
        f'{escape(label)}</button>'
        for label, prompt in quick_prompts
    )

    new_conv_btn = (
        '<form method="POST" action="/coach-clear-history" style="display:inline;">'
        '<button type="submit" style="background:none;border:none;font-size:0.72em;'
        'color:#bbb;cursor:pointer;font-family:inherit;padding:0;">&#10005; New conversation</button>'
        '</form>'
    ) if has_history else ''

    accent = "#1a6e3e"

    # Welcome message
    if h < 11:
        welcome = "Morning! Ready to move? Tell me what you're working with today — time, energy level, and who needs to get moving."
    elif h < 17:
        welcome = "Afternoon. The boys need to burn some energy. What are we working with today?"
    else:
        welcome = "Evening. Good time to plan tomorrow's movement. What does the family's schedule look like?"

    _ho_js = handoff_js("COACH")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Coach &middot; McAdams Fitness</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#f2faf6;color:#1a1a1a;min-height:100vh;}}
.co-bubble-user{{
    background:#1a6e3e;color:white;padding:10px 14px;border-radius:16px 16px 4px 16px;
    font-size:1em;line-height:1.55;max-width:75%;align-self:flex-end;margin-left:auto;
}}
.co-bubble-co{{
    background:white;border:1px solid #b8dcc8;padding:12px 16px;
    border-radius:4px 16px 16px 16px;font-size:1em;line-height:1.65;
    max-width:85%;white-space:pre-wrap;color:#1a1a1a;
}}
.co-bubble-wrap{{display:flex;flex-direction:column;gap:12px;}}
@keyframes co-pulse{{0%,100%{{opacity:1;}}50%{{opacity:0.4;}}}}
</style>
</head>
<body>
<div style="max-width:760px;margin:0 auto;padding:20px 16px 200px;">

    <!-- Nav -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
        <a href="/" style="font-size:0.82em;color:#aaa;text-decoration:none;">&larr; Dashboard</a>
        <div style="display:flex;align-items:center;gap:14px;">
            {new_conv_btn}
            <span style="font-size:0.78em;color:#aaa;">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;
                             background:{phase_color};margin-right:5px;"></span>{escape(phase_label)}
            </span>
        </div>
    </div>

    <!-- Header -->
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:24px;">
        <div style="width:52px;height:52px;border-radius:50%;
                    background:linear-gradient(135deg,{accent},#2aaa5e);
                    display:flex;align-items:center;justify-content:center;font-size:1.5em;
                    flex-shrink:0;box-shadow:0 2px 10px rgba(26,110,62,0.25);">
            &#128170;
        </div>
        <div>
            <div style="font-family:Georgia,serif;font-size:1.4em;font-weight:600;color:#1a1a1a;line-height:1.1;">
                {escape(greeting)}
            </div>
            <div style="font-size:0.85em;color:#888;margin-top:2px;">
                Coach &middot; {escape(weekday)}, {escape(date_label)}
            </div>
        </div>
    </div>

    <!-- Quick prompts -->
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;">
        {quick_buttons}
    </div>

    {ho_banner}

    <!-- Conversation -->
    <div id="co-chat" class="co-bubble-wrap" style="margin-bottom:20px;"></div>

    <!-- Thinking -->
    <div id="co-thinking" style="display:none;padding:10px 0;color:#888;font-size:0.85em;">
        <span style="animation:co-pulse 1.2s ease-in-out infinite;display:inline-block;">
            Coach is drawing up the plan&hellip;
        </span>
    </div>

</div>

<!-- Floating input -->
<div style="position:fixed;bottom:64px;left:0;right:0;background:white;
            border-top:1px solid #b8dcc8;padding:12px 16px;z-index:100;">
    <div style="max-width:760px;margin:0 auto;display:flex;gap:10px;align-items:flex-end;">
        <textarea id="co-input" rows="1" placeholder="Ask Coach…"
            style="flex:1;border:1px solid #b0d8c0;border-radius:12px;
                   padding:10px 14px;font-size:0.95em;font-family:inherit;
                   resize:none;outline:none;background:#f2faf6;max-height:120px;">{q_safe}</textarea>
        <button id="co-send" onclick="coachSend()"
            style="width:44px;height:44px;border-radius:50%;background:{accent};
                   border:none;color:white;font-size:1.1em;cursor:pointer;flex-shrink:0;">
            &#8593;
        </button>
    </div>
</div>

<script>
var _coHistory = {history_js};
var _coIso     = {_ej(iso)};
{_ho_js}

(function() {{
    for (var i = 0; i < _coHistory.length; i++) {{
        var m = _coHistory[i];
        if (m.role === 'user')           _coRenderUser(m.content);
        else if (m.role === 'assistant') _coRenderBubble(m.content);
    }}
    if (_coHistory.length) {{ var msgs = document.querySelectorAll('.co-bubble-user, .co-bubble-co'); if (msgs.length) msgs[msgs.length - 1].scrollIntoView({{behavior: 'smooth', block: 'end'}}); }}
}})();

function _coRenderBubble(text) {{
    var wrap = document.getElementById('co-chat');
    var row  = document.createElement('div');
    var bub  = document.createElement('div');
    bub.className = 'co-bubble-co';
    bub.innerHTML = _linkify(_stripHandoffTags(text));
    row.appendChild(bub);
    _renderHandoffBtns(text, row);
    wrap.appendChild(row);
    var msgs = document.querySelectorAll('.co-bubble-user, .co-bubble-co');
    if (msgs.length) msgs[msgs.length - 1].scrollIntoView({{behavior: 'smooth', block: 'end'}});
    return bub;
}}

function _coRenderUser(text) {{
    var wrap = document.getElementById('co-chat');
    var row  = document.createElement('div');
    row.style.cssText = 'display:flex;justify-content:flex-end;';
    var bub  = document.createElement('div');
    bub.className   = 'co-bubble-user';
    bub.textContent = text;
    row.appendChild(bub);
    wrap.appendChild(row);
    var msgs = document.querySelectorAll('.co-bubble-user, .co-bubble-co');
    if (msgs.length) msgs[msgs.length - 1].scrollIntoView({{behavior: 'smooth', block: 'end'}});
}}

function coachQuick(prompt) {{
    document.getElementById('co-input').value = prompt;
    coachSend();
}}

function coachSend() {{
    var input = document.getElementById('co-input');
    var msg   = input.value.trim();
    if (!msg) return;
    input.value = '';
    input.style.height = 'auto';

    _coHistory.push({{role:'user', content: msg}});
    _coRenderUser(msg);
    document.getElementById('co-thinking').style.display = '';
    var msgs = document.querySelectorAll('.co-bubble-user, .co-bubble-co');
    if (msgs.length) msgs[msgs.length - 1].scrollIntoView({{behavior: 'smooth', block: 'end'}});

    fetch('/coach-chat', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: 'iso=' + encodeURIComponent(new Date().toISOString().split('T')[0])
            + '&message=' + encodeURIComponent(msg)
    }}).then(function(r) {{
        document.getElementById('co-thinking').style.display = 'none';
        if (!r.ok) {{
            _coRenderBubble('Coach is offline. Please check your API key in Settings.');
            return;
        }}
        var bubble  = _coRenderBubble('');
        var full    = '';
        var reader  = r.body.getReader();
        var decoder = new TextDecoder();
        function read() {{
            return reader.read().then(function(res) {{
                if (res.done) {{
                    bubble.innerHTML = _linkify(_stripHandoffTags(full));
                    _renderHandoffBtns(full, bubble.parentNode);
                    _coHistory.push({{role:'assistant', content: full}});
                    return;
                }}
                full += decoder.decode(res.value, {{stream: true}});
                bubble.innerHTML = _linkify(_stripHandoffTags(full));
                var msgs = document.querySelectorAll('.co-bubble-user, .co-bubble-co');
                if (msgs.length) msgs[msgs.length - 1].scrollIntoView({{behavior: 'smooth', block: 'end'}});
                return read();
            }});
        }}
        read().catch(console.error);
    }}).catch(function() {{
        document.getElementById('co-thinking').style.display = 'none';
        _coRenderBubble('Connection error. Please try again.');
    }});
}}

document.getElementById('co-input').addEventListener('input', function() {{
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
}});
document.getElementById('co-input').addEventListener('keydown', function(e) {{
    if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); coachSend(); }}
}});

if (!_coHistory.length) {{
    _coRenderBubble({_ej(welcome)});
}}
</script>
</body>
</html>"""
