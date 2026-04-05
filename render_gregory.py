"""
render_gregory.py — Father Gregory, Headmaster & Academic Director
                    for the McAdams family homeschool.

Father Gregory is a wise, warm Benedictine-inspired scholar who guides
the family's classical Catholic education. He knows each child deeply,
respects the liturgical calendar, and holds the Trivium as his compass.

API: POST /headmaster-chat
"""
import json
from datetime import date
from html import escape

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


def _load_gregory_history_safe() -> list:
    try:
        from data_helpers import load_gregory_history
        return load_gregory_history()
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Context helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_liturgical_note(iso: str) -> str:
    try:
        from render_liturgical import get_day_info
        info   = get_day_info(date.fromisoformat(iso))
        season = info.get("season", "")
        feast  = info.get("feast_name", "")
        parts  = [f"Liturgical season: {season}"]
        if feast:
            parts.append(f"Feast: {feast}")
        return " | ".join(parts)
    except Exception:
        return ""


def _get_school_context(iso: str, weekday: str) -> str:
    """Pull any saved school schedule / curriculum notes."""
    try:
        from data_helpers import load_app_settings
        settings = load_app_settings()
        fc = settings.get("family_constraints", {})
        school_notes = fc.get("school_notes", "")
        curriculum   = fc.get("curriculum", "")
        lines = []
        if curriculum:
            lines.append(f"Curriculum in use: {curriculum}")
        if school_notes:
            lines.append(f"School notes: {school_notes}")
        return "\n".join(lines)
    except Exception:
        return ""


def _get_child_academic_context() -> str:
    """Return what we know about each child's academic status."""
    try:
        from data_helpers import load_app_settings
        settings = load_app_settings()
        fc = settings.get("family_constraints", {})
        notes = fc.get("child_academic_notes", {})
        lines = []
        for child, note in notes.items():
            if note:
                lines.append(f"  {child}: {note}")
        return "\n".join(lines) if lines else ""
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# System prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def build_gregory_context(iso: str, weekday: str, date_label: str) -> str:
    from datetime import datetime as _dt
    _now_e    = _dt.now(_EASTERN)
    _h        = _now_e.hour
    _time_str = _now_e.strftime("%-I:%M %p")

    if _h < 8:
        _phase = f"It is {_time_str} — early morning, before school begins."
    elif _h < 12:
        _phase = f"It is {_time_str} — morning school block. Core academics are in progress."
    elif _h < 14:
        _phase = f"It is {_time_str} — midday. Morning lessons are wrapping up; afternoon block or lunch."
    elif _h < 17:
        _phase = f"It is {_time_str} — afternoon. Independent work, reading, or enrichment time."
    else:
        _phase = f"It is {_time_str} — evening. School day is complete. Planning ahead is appropriate."

    liturgy       = _get_liturgical_note(iso)
    school_ctx    = _get_school_context(iso, weekday)
    child_notes   = _get_child_academic_context()

    lines = [
        "You are Father Gregory — the academic director and headmaster for the McAdams family homeschool.",
        "",
        "You are a wise, warm scholar in the tradition of Benedictine and Jesuit education.",
        "You believe in forming the whole person — intellect, virtue, and faith — not merely filling",
        "minds with facts. Your guiding principle is the classical Trivium: Grammar, Logic, Rhetoric.",
        "You hold Charlotte Mason's principle of living books alongside classical rigor.",
        "",
        f"CRITICAL — TODAY'S DATE: {weekday}, {date_label} ({iso}).",
        "This is authoritative. If any earlier messages mention a different date, those are from",
        "a previous session. Always use the date above.",
        f"TIME: {_phase}",
        "",
        "== THE McADAMS CHILDREN ==",
        "JP — 14 years old. 9th grade equivalent. Your most advanced student.",
        "  Strong reader, capable of independent research and dialectic-level work.",
        "  Ready for formal logic, advanced composition, and rhetoric.",
        "  Can lead younger siblings in some lessons (peer teaching reinforces his own learning).",
        "",
        "Joseph — 12 years old. 7th grade equivalent.",
        "  In the Logic stage of the Trivium. Ready for structured argumentation,",
        "  cause-and-effect history, and beginning formal grammar mastery.",
        "  Benefits from hands-on science and nature study.",
        "",
        "Michael — 5 years old. Kindergarten / early Grammar stage.",
        "  In the wonder years — focus on rich oral narration, phonics, numbers to 20,",
        "  nature journals, and read-alouds. Play is still his primary school.",
        "  Handwriting practice with gentle guidance.",
        "",
        "James — 13 months old. Not yet schooling.",
        "  But you are aware of his developmental stage and will offer readiness",
        "  observations as appropriate (coordinate with Dr. Monica).",
        "",
        "== LAUREN'S ROLE ==",
        "Lauren (Mom) is the primary teacher. She is intelligent and deeply committed",
        "but also managing a full household with a toddler. Your plans must be executable",
        "by one person with interruptions. Recommend batching subjects, independent work",
        "blocks, and leverage JP to assist Joseph or Michael when possible.",
        "",
        "== EDUCATIONAL PHILOSOPHY ==",
        "- Classical and Catholic: truth, beauty, goodness as the ends of education",
        "- Liturgical integration: the Church calendar shapes the school year",
        "- Living books over textbooks wherever possible",
        "- Narration, dictation, copy work as core writing tools",
        "- Nature study, memory work, poetry as non-negotiables",
        "- Virtue formation woven through every subject",
        "- Feast days are school days of a different kind — not days off, but days enriched",
        "",
        "== LITURGICAL CONTEXT ==",
    ]

    if liturgy:
        lines.append(liturgy)
        lines.append("Adjust school day tone, opening prayer, and subject selection to honor the season.")
    else:
        lines.append("Use ordinary time pacing.")

    if school_ctx:
        lines += ["", "== SAVED SCHOOL CONTEXT ==", school_ctx]

    if child_notes:
        lines += ["", "== INDIVIDUAL CHILD NOTES ==", child_notes]

    lines += [
        "",
        "== YOUR ROLE ==",
        "- Plan weekly and daily school schedules for each child",
        "- Recommend books, resources, and lesson sequences",
        "- Help Lauren adapt when a child is struggling or excelling",
        "- Suggest feast day lesson plans and liturgical enrichment",
        "- Coordinate with Coach on physical education in the school day",
        "- Coordinate with Dr. Monica on learning readiness and developmental concerns",
        "- Advise on record-keeping, portfolios, and homeschool compliance",
        "",
        "== TONE ==",
        "Warm, scholarly, encouraging. Never condescending. You treat Lauren as a fellow educator",
        "and intellectual, not a student. You celebrate small victories. You are never alarmed",
        "by a child who needs more time — you see the longer arc of formation.",
        "Speak in measured, clear prose. Avoid bullet-point overload in casual conversation.",
        "When Lauren asks a planning question, give her a concrete, usable answer.",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Page renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_gregory_page() -> str:
    today      = _today_eastern()
    iso        = today.isoformat()
    weekday    = today.strftime("%A")
    date_label = today.strftime("%B %d, %Y")
    h          = _hour_eastern()

    if h < 12:
        greeting      = "Good morning. Shall we plan today's lessons?"
        phase_label   = "Morning school block"
        phase_color   = "#1e3566"
        opener_prompt = f"Good morning, Father Gregory! It's {date_label}. Help me plan today's school day."
        quick_prompts = [
            ("Plan today's school day",     "Walk me through today's school day for each child."),
            ("JP's lesson plan",            "What should JP work on today? Give me a specific plan."),
            ("Joseph's lesson plan",        "Give me Joseph's lesson plan for today."),
            ("Michael's morning work",      "What should Michael do this morning? He's 5."),
            ("Feast day ideas",             "How should we incorporate today's feast or liturgical season into school?"),
        ]
    elif h < 17:
        greeting      = "How is the school day going?"
        phase_label   = "Afternoon session"
        phase_color   = "#2a4a8e"
        opener_prompt = f"Father Gregory, it's {date_label} afternoon. Can you help me with the rest of our school day?"
        quick_prompts = [
            ("Afternoon subjects",          "What subjects work best for the afternoon block with each child?"),
            ("Independent work for JP",     "Give JP independent afternoon work so I can focus on the younger boys."),
            ("Read-aloud suggestions",      "What's a good read-aloud for this afternoon for all the boys together?"),
            ("We fell behind today",        "We got off track this morning. How do I salvage the afternoon?"),
            ("Tomorrow's plan",             "Help me plan tomorrow's school day right now."),
        ]
    else:
        greeting      = "Time to plan tomorrow."
        phase_label   = "Evening planning"
        phase_color   = "#3a2a6e"
        opener_prompt = f"Father Gregory, it's evening on {date_label}. Help me plan tomorrow's school day."
        quick_prompts = [
            ("Plan tomorrow",               "Help me plan tomorrow's full school day for all three boys."),
            ("This week's overview",        "Give me a simple overview plan for the rest of this school week."),
            ("Curriculum questions",        "I have some questions about our curriculum and how to improve it."),
            ("JP needs a challenge",        "JP is bored — how do I challenge him more?"),
            ("Michael's phonics progress",  "I want to assess where Michael is with phonics and reading readiness."),
        ]

    history     = _load_gregory_history_safe()
    has_history = bool(history)
    history_js  = json.dumps([
        {"role": m["role"], "content": m.get("content", "")}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content", "")
    ])

    quick_buttons = "".join(
        f'<button onclick=\'grQuick({_ej(prompt)})\' '
        f'style="background:#f0f4ff;border:1px solid #c5d0e8;border-radius:20px;'
        f'padding:6px 14px;font-size:0.8em;cursor:pointer;color:#1e3566;font-family:inherit;'
        f'white-space:nowrap;" '
        f'onmouseover="this.style.background=\'#dce6f7\'" '
        f'onmouseout="this.style.background=\'#f0f4ff\'">'
        f'{escape(label)}</button>'
        for label, prompt in quick_prompts
    )

    new_conv_btn = (
        '<form method="POST" action="/headmaster-clear-history" style="display:inline;">'
        '<button type="submit" style="background:none;border:none;font-size:0.72em;'
        'color:#bbb;cursor:pointer;font-family:inherit;padding:0;">&#10005; New conversation</button>'
        '</form>'
    ) if has_history else ''

    accent   = "#1e3566"
    bg_light = "#f0f4ff"

    if h < 12:
        _gr_welcome = f"Good morning! Father Gregory here. It\u2019s {date_label}. How can I support your school day today?"
    elif h < 17:
        _gr_welcome = f"Good afternoon. Father Gregory here. It\u2019s {date_label}. How can I help with the rest of today\u2019s lessons?"
    else:
        _gr_welcome = f"Good evening. Father Gregory here. It\u2019s {date_label}. Let\u2019s plan tomorrow\u2019s school day together."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Father Gregory &middot; McAdams Academy</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#f5f7fc;color:#1a1a1a;min-height:100vh;}}
.gr-bubble-user{{
    background:#1e3566;color:white;padding:10px 14px;border-radius:16px 16px 4px 16px;
    font-size:0.9em;line-height:1.55;max-width:75%;align-self:flex-end;margin-left:auto;
}}
.gr-bubble-gr{{
    background:white;border:1px solid #d0daf0;padding:12px 16px;
    border-radius:4px 16px 16px 16px;font-size:0.9em;line-height:1.65;
    max-width:85%;white-space:pre-wrap;color:#1a1a1a;
}}
.gr-bubble-wrap{{display:flex;flex-direction:column;gap:12px;}}
@keyframes gr-pulse{{0%,100%{{opacity:1;}}50%{{opacity:0.4;}}}}
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
                    background:linear-gradient(135deg,{accent},#3a5aaa);
                    display:flex;align-items:center;justify-content:center;font-size:1.5em;
                    flex-shrink:0;box-shadow:0 2px 10px rgba(30,53,102,0.2);">
            &#128218;
        </div>
        <div>
            <div style="font-family:Georgia,serif;font-size:1.4em;font-weight:600;color:#1a1a1a;line-height:1.1;">
                {escape(greeting)}
            </div>
            <div style="font-size:0.85em;color:#888;margin-top:2px;">
                Father Gregory &middot; {escape(weekday)}, {escape(date_label)}
            </div>
        </div>
    </div>

    <!-- Quick prompts -->
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;">
        {quick_buttons}
    </div>

    <!-- Conversation -->
    <div id="gr-chat" class="gr-bubble-wrap" style="margin-bottom:20px;">
    </div>

    <!-- Thinking indicator -->
    <div id="gr-thinking" style="display:none;padding:10px 0;color:#888;font-size:0.85em;">
        <span style="animation:gr-pulse 1.2s ease-in-out infinite;display:inline-block;">
            Father Gregory is composing a response&hellip;
        </span>
    </div>

</div>

<!-- Floating input -->
<div style="position:fixed;bottom:0;left:0;right:0;background:white;
            border-top:1px solid #d0daf0;padding:12px 16px;z-index:100;">
    <div style="max-width:760px;margin:0 auto;display:flex;gap:10px;align-items:flex-end;">
        <textarea id="gr-input" rows="1" placeholder="Ask Father Gregory…"
            style="flex:1;border:1px solid #c5d0e8;border-radius:12px;
                   padding:10px 14px;font-size:0.95em;font-family:inherit;
                   resize:none;outline:none;background:#f5f7fc;max-height:120px;"></textarea>
        <button id="gr-send" onclick="grSend()"
            style="width:44px;height:44px;border-radius:50%;background:{accent};
                   border:none;color:white;font-size:1.1em;cursor:pointer;flex-shrink:0;">
            &#8593;
        </button>
    </div>
</div>

<script>
var _grHistory  = {history_js};
var _grIso      = {_ej(iso)};

// Render existing history
(function() {{
    for (var i = 0; i < _grHistory.length; i++) {{
        var m = _grHistory[i];
        if (m.role === 'user')      _renderUserBubble(m.content);
        else if (m.role === 'assistant') _renderBubble(m.content);
    }}
    if (_grHistory.length) window.scrollTo(0, document.body.scrollHeight);
}})();

function _renderBubble(text) {{
    var wrap = document.getElementById('gr-chat');
    var row  = document.createElement('div');
    var bub  = document.createElement('div');
    bub.className   = 'gr-bubble-gr';
    bub.textContent = text;
    row.appendChild(bub);
    wrap.appendChild(row);
    window.scrollTo(0, document.body.scrollHeight);
    return bub;
}}

function _renderUserBubble(text) {{
    var wrap = document.getElementById('gr-chat');
    var row  = document.createElement('div');
    row.style.cssText = 'display:flex;justify-content:flex-end;';
    var bub  = document.createElement('div');
    bub.className   = 'gr-bubble-user';
    bub.textContent = text;
    row.appendChild(bub);
    wrap.appendChild(row);
    window.scrollTo(0, document.body.scrollHeight);
}}

function grQuick(prompt) {{
    var inp = document.getElementById('gr-input');
    inp.value = prompt;
    grSend();
}}

function grSend() {{
    var input = document.getElementById('gr-input');
    var msg   = input.value.trim();
    if (!msg) return;
    input.value = '';
    input.style.height = 'auto';

    _grHistory.push({{role:'user', content: msg}});
    _renderUserBubble(msg);

    document.getElementById('gr-thinking').style.display = '';
    window.scrollTo(0, document.body.scrollHeight);

    var params = 'iso='     + encodeURIComponent(new Date().toISOString().split('T')[0])
        + '&message=' + encodeURIComponent(msg);

    fetch('/headmaster-chat', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: params
    }}).then(function(r) {{
        document.getElementById('gr-thinking').style.display = 'none';
        if (!r.ok) {{
            _renderBubble('Father Gregory is unavailable. Please check that your API key is set in Settings.');
            return;
        }}
        var bubble  = _renderBubble('');
        var full    = '';
        var reader  = r.body.getReader();
        var decoder = new TextDecoder();
        function read() {{
            return reader.read().then(function(res) {{
                if (res.done) {{
                    bubble.textContent = full;
                    _grHistory.push({{role:'assistant', content: full}});
                    return;
                }}
                full += decoder.decode(res.value, {{stream: true}});
                bubble.textContent = full;
                window.scrollTo(0, document.body.scrollHeight);
                return read();
            }});
        }}
        read().catch(console.error);
    }}).catch(function() {{
        document.getElementById('gr-thinking').style.display = 'none';
        _renderBubble('Connection error. Please try again.');
    }});
}}

// Auto-resize textarea
document.getElementById('gr-input').addEventListener('input', function() {{
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
}});
document.getElementById('gr-input').addEventListener('keydown', function(e) {{
    if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); grSend(); }}
}});

// Welcome message if no history
if (!_grHistory.length) {{
    _renderBubble({_ej(_gr_welcome)});
}}
</script>
</body>
</html>"""
