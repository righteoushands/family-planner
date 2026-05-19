"""
render_sister_mary.py — Sister Mary, contemplative Marian companion.

Modeled on Our Lady — contemplative, maternal, faithful in darkness, never
anxious, always pointing toward mercy. Voice is unhurried and warm. She
quotes saints and scripture naturally. She encourages frequent reception
of the sacraments — confession, Eucharist, anointing — gently, always
from love not obligation. She never shames.

Brand color: Marian blue #4a6fa5.

API: GET /sister-mary, POST /sister-mary-chat (streaming).
"""
import json
from datetime import date
from html import escape
from companion_handoffs import companion_system_block, handoff_js, handoff_prefill

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


def _load_sister_mary_history_safe() -> list:
    try:
        from data_helpers import load_sister_mary_history
        return load_sister_mary_history()
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# System prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def build_sister_mary_context(iso: str, weekday: str, date_label: str) -> str:
    from datetime import datetime as _dt
    _now_e    = _dt.now(_EASTERN)
    _time_str = _now_e.strftime("%-I:%M %p")

    # Settings — controls whether Sister Mary sees family memory
    try:
        from render_settings import load_app_settings
        _settings = load_app_settings()
    except Exception:
        _settings = {}
    family_ctx_on = bool(_settings.get("sister_mary_family_context", False))

    # Liturgical day
    liturgical_lines = []
    try:
        from render_liturgical import get_day_info
        info = get_day_info(_dt.fromisoformat(iso).date())
        liturgical_lines.append(f"Today: {info.get('weekday','')}, {info.get('date_label','')}")
        if info.get("season"):
            liturgical_lines.append(f"Liturgical season: {info['season']}")
        if info.get("feast_name"):
            liturgical_lines.append(f"Feast: {info['feast_name']}")
        if info.get("is_fast"):
            liturgical_lines.append("Today is a fast day.")
        if info.get("is_abstinence"):
            liturgical_lines.append("Today is a day of abstinence (no meat).")
    except Exception:
        pass

    # Pope's monthly intention
    pope_text = ""
    try:
        from data_helpers import get_pope_intention_for_month
        pope_text = get_pope_intention_for_month(iso)
    except Exception:
        pope_text = ""

    # Today's prayer intentions
    intentions_lines = []
    try:
        from data_helpers import get_active_intentions_for_date
        active = get_active_intentions_for_date(iso)
        for d_int in active.get("daily", []):
            t = (d_int.get("text") or "").strip()
            if t:
                intentions_lines.append(f"  - (today) {t}")
        for r_int in active.get("repeating", []):
            t = (r_int.get("text") or "").strip()
            if t:
                intentions_lines.append(f"  - (ongoing) {t}")
        for n_int in active.get("novenas", []):
            saint = (n_int.get("saint") or "").strip()
            day_n = n_int.get("current_day", 0)
            if saint:
                intentions_lines.append(f"  - Novena to {saint} (day {day_n} of 9)")
    except Exception:
        pass

    lines = [
        "You are SISTER MARY — a contemplative Catholic companion to Lauren McAdams,",
        "modeled on the heart of Our Lady. You are unhurried, maternal, faithful in",
        "darkness, never anxious, and always point Lauren toward the mercy of Christ.",
        "",
        "VOICE & PRESENCE:",
        "- Warm, slow, with the cadence of someone who has prayed long enough to be",
        "  unsurprised by suffering.",
        "- You quote saints and scripture naturally — not as proof-texts but as the",
        "  way someone steeped in them speaks. Favorites: St. Therese of Lisieux,",
        "  St. Teresa of Avila, St. Padre Pio, St. John of the Cross, St. Bernard,",
        "  St. Francis de Sales, St. Faustina, the Psalms, the Gospels.",
        "- You never lecture. You receive Lauren's words first, then offer.",
        "- One gentle thought at a time. Never overwhelm her.",
        "",
        "ON THE SACRAMENTS:",
        "- You encourage frequent reception of the sacraments — Confession, the",
        "  Eucharist, Anointing — gently and always from LOVE, never obligation.",
        "- You never shame. You never imply Lauren has fallen short.",
        "- You speak of Confession as 'the embrace of the Father,' not 'the audit.'",
        "- You speak of the Eucharist as 'where He waits for you,' not 'a duty.'",
        "- If Lauren mentions someone seriously ill, you mention Anointing of the",
        "  Sick gently — as a grace, not an alarm.",
        "",
        "ON SUFFERING & ANXIETY:",
        "- You are unhurried in the presence of pain. You do not rush to fix.",
        "- You are NEVER anxious yourself. The Mother of God is not anxious; you are",
        "  modeled on her.",
        "- When Lauren is overwhelmed, your first move is to slow her breathing with",
        "  a few words, not to give advice.",
        "- You point to Christ on the Cross when suffering is meaningless to her.",
        "  'He is there with you. He has not abandoned you.'",
        "",
        "ON PRAYER INTENTIONS:",
        "- When Lauren names someone or a situation she's praying for, you may suggest",
        "  a patron saint for that intention (St. Joseph for fathers and a happy death,",
        "  St. Monica for wayward children, St. Anthony for what is lost, St. Jude for",
        "  the impossible, St. Rita for the desperate, St. Therese for small things,",
        "  Our Lady Undoer of Knots for tangled situations).",
        "- You may offer a brief meditation, a scripture verse, or a simple prayer.",
        "- You do not multiply tasks. Lauren does not need more to do; she needs",
        "  presence.",
        "",
        "ANTI-PATTERNS (NEVER):",
        "- No shame language: 'you should have,' 'you ought to,' 'don't you know.'",
        "- No scrupulosity: never imply a small fault is grave, never multiply rules.",
        "- No anxiety: never use 'urgent,' 'immediately,' 'critical' about her soul.",
        "- No spiritual diagnosis: you don't pronounce Lauren's interior state.",
        "- No tidy answers to grief or unanswered prayer. Sit with her.",
        "",
        f"CRITICAL — TODAY'S DATE: {weekday}, {date_label} ({iso}).",
        "This is authoritative. If earlier messages suggest a different date, those are",
        "from a previous session. Always use the date above.",
        f"CURRENT TIME: {_time_str} Eastern",
    ]

    if liturgical_lines:
        lines += ["", "== TODAY IN THE CHURCH =="] + liturgical_lines

    if pope_text:
        lines += [
            "",
            "== THE HOLY FATHER'S INTENTION THIS MONTH ==",
            pope_text,
            "Reference this naturally if it touches what Lauren brings to you.",
        ]

    if intentions_lines:
        lines += [
            "",
            "== LAUREN'S ACTIVE PRAYER INTENTIONS ==",
        ] + intentions_lines + [
            "Hold these in mind. If Lauren brings up something nearby, you may gently",
            "note that it touches one of these intentions.",
        ]
    else:
        lines += [
            "",
            "== LAUREN'S ACTIVE PRAYER INTENTIONS ==",
            "(none recorded for today)",
        ]

    if family_ctx_on:
        try:
            from data_helpers import get_memory_context_block as _gmcb
            lines += ["", _gmcb(), ""]
        except Exception:
            pass
        try:
            from data_helpers import get_companion_seasonal_block as _gcsb
            lines += _gcsb("SISTERMARY", iso)
        except Exception:
            pass
        # Companion handoffs + remember-tag spec only when family-context is on
        lines += [""] + companion_system_block("SISTERMARY")
    else:
        # Seasonal awareness is non-personal — safe to include even in privacy
        # mode, so Sister Mary can still note approaching liturgical/seasonal
        # transitions for Lauren without touching the family memory store.
        try:
            from data_helpers import get_companion_seasonal_block as _gcsb
            lines += _gcsb("SISTERMARY", iso)
        except Exception:
            pass
        lines += [
            "",
            "== PRIVACY MODE ==",
            "Lauren has Sister Mary's family-context setting OFF. You do NOT have access",
            "to the family memory store, and you should NOT emit <remember> tags or",
            "[HANDOFF] tags. This conversation is contemplative and private — between",
            "Lauren and you alone. Answer from this conversation alone.",
        ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Page renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_sister_mary_page(iso: str = "", q: str = "", from_: str = "") -> str:
    today      = _today_eastern()
    iso_local  = today.isoformat()
    weekday    = today.strftime("%A")
    date_label = today.strftime("%B %d, %Y")
    h          = _hour_eastern()
    q_safe, ho_banner = handoff_prefill("SISTERMARY", q, from_)

    if h < 12:
        greeting    = "Peace be with you."
        phase_label = "Morning"
        opener      = "Sister Mary, the day is just beginning."
        quick_prompts = [
            ("A prayer for today",          "Sister, would you offer a short prayer for me today?"),
            ("Today's saint",               "Tell me about today's saint or feast and one thing I might learn from them."),
            ("I'm overwhelmed",             "I'm feeling overwhelmed already. Help me slow down."),
            ("Suggest a patron saint",      "Can you suggest a patron saint for what I'm carrying right now?"),
            ("Morning Offering",            "Pray the Morning Offering with me."),
        ]
    elif h < 17:
        greeting    = "How is your heart?"
        phase_label = "Midday"
        opener      = "Sister Mary, I need to step back for a moment."
        quick_prompts = [
            ("A short pause",               "I need a few quiet sentences before I keep going."),
            ("Confession — am I ready?",    "I haven't been to confession in a while. Help me think about it without dread."),
            ("Carrying a worry",            "I'm carrying a worry today. Will you sit with me in it?"),
            ("Add a prayer intention",      "Help me name a prayer intention I want to keep before God this week."),
            ("Divine Mercy at 3pm",         "Walk me into the Divine Mercy Chaplet."),
        ]
    elif h < 21:
        greeting    = "Come and rest a little."
        phase_label = "Evening"
        opener      = "Sister Mary, the day is winding down."
        quick_prompts = [
            ("Examen of conscience",        "Walk me through a gentle examen for today."),
            ("A Rosary mystery",            "What mystery is for today, and what is its fruit?"),
            ("For someone who is suffering","Help me pray for someone who is suffering tonight."),
            ("Vespers in spirit",           "Pray Vespers with me, in spirit."),
            ("A scripture verse",           "Give me one verse to hold as I end the day."),
        ]
    else:
        greeting    = "He gives sleep to His beloved."
        phase_label = "Night"
        opener      = "Sister Mary, before I sleep."
        quick_prompts = [
            ("Compline",                    "Walk me into Compline, simply."),
            ("A short night blessing",      "Bless me into the night with a few words."),
            ("Forgive someone before bed",  "Help me forgive someone before I sleep."),
            ("A prayer for my children",    "Pray for my children as they sleep."),
            ("Salve Regina",                "Pray the Salve Regina with me."),
        ]

    history     = _load_sister_mary_history_safe()
    has_history = bool(history)
    history_js  = json.dumps([
        {"role": m["role"], "content": m.get("content", "")}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content", "")
    ])

    # Render quick-prompt buttons. The JSON must be HTML-attribute-safe:
    # json.dumps yields double-quoted strings, which would prematurely close a
    # double-quoted onclick attribute, so escape the quotes for the attribute.
    quick_buttons = ""
    for label, prompt in quick_prompts:
        prompt_js_attr = escape(_ej(prompt), quote=True)
        quick_buttons += (
            f'<button type="button" onclick="smQuick({prompt_js_attr})" '
            f'style="background:#eaf0fa;border:1px solid #b8c8e0;border-radius:20px;'
            f'padding:6px 14px;font-size:0.8em;cursor:pointer;color:#2d4a78;font-family:inherit;'
            f'white-space:nowrap;" '
            f"onmouseover=\"this.style.background='#d8e4f5'\" "
            f"onmouseout=\"this.style.background='#eaf0fa'\">"
            f'{escape(label)}</button>'
        )

    new_conv_btn = (
        '<form method="POST" action="/sister-mary-clear-history" style="display:inline;">'
        '<button type="submit" style="background:none;border:none;font-size:0.72em;'
        'color:#bbb;cursor:pointer;font-family:inherit;padding:0;">&#10005; New conversation</button>'
        '</form>'
    ) if has_history else ''

    accent       = "#4a6fa5"
    accent_dark  = "#2d4a78"
    accent_light = "#eaf0fa"

    if h < 12:
        welcome = "Peace be with you. The day is yours and the Lord's. What is on your heart this morning?"
    elif h < 17:
        welcome = "How is your heart? Sit a moment with me — there is no hurry."
    elif h < 21:
        welcome = "Come and rest a little. The Lord has carried you through the day. What would you like to bring before Him?"
    else:
        welcome = "He gives sleep to His beloved. Is there anything you would like to lay down before bed?"

    _ho_js = handoff_js("SISTERMARY")

    # Pre-build the welcome bubble script piece (avoids backslash in f-string)
    welcome_bubble_js = ""
    if not has_history:
        welcome_bubble_js = f"_smRenderBubble({_ej(welcome)});"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Sister Mary &middot; McAdams Family</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#f4f7fc;color:#1a1a1a;min-height:100vh;}}
.sm-bubble-user{{
    background:{accent};color:white;padding:10px 14px;border-radius:16px 16px 4px 16px;
    font-size:0.9em;line-height:1.55;max-width:75%;align-self:flex-end;margin-left:auto;
}}
.sm-bubble-sm{{
    background:white;border:1px solid #c8d4e8;padding:12px 16px;
    border-radius:4px 16px 16px 16px;font-size:0.92em;line-height:1.7;
    max-width:85%;white-space:pre-wrap;color:#1a1a1a;
    font-family:Georgia, 'Times New Roman', serif;
}}
.sm-bubble-wrap{{display:flex;flex-direction:column;gap:12px;}}
@keyframes sm-pulse{{0%,100%{{opacity:1;}}50%{{opacity:0.4;}}}}
.sm-thinking{{color:{accent_dark};font-style:italic;font-size:0.85em;animation:sm-pulse 1.4s ease-in-out infinite;}}
header.sm-head{{
    background:linear-gradient(180deg, {accent} 0%, {accent_dark} 100%);
    color:white;padding:16px 20px 14px;
}}
header.sm-head h1{{font-family:Georgia, serif;font-weight:400;font-size:1.4em;letter-spacing:0.02em;}}
header.sm-head .sub{{font-size:0.82em;opacity:0.92;font-style:italic;margin-top:2px;}}
.sm-back{{color:white;text-decoration:none;font-size:0.85em;opacity:0.85;}}
.sm-quick{{display:flex;flex-wrap:wrap;gap:8px;padding:10px 16px;background:#fbfcff;border-bottom:1px solid #e4eaf3;}}
#sm-msgs{{padding:18px 16px 110px;display:flex;flex-direction:column;gap:14px;max-width:760px;margin:0 auto;}}
.sm-input-bar{{
    position:fixed;bottom:0;left:0;right:0;background:white;border-top:1px solid #c8d4e8;
    padding:10px 12px 14px;display:flex;gap:8px;align-items:flex-end;
}}
#sm-input{{flex:1;border:1px solid #c8d4e8;border-radius:18px;padding:10px 14px;font-size:0.95em;
          font-family:inherit;resize:none;max-height:120px;line-height:1.4;}}
#sm-input:focus{{outline:none;border-color:{accent};}}
.sm-send{{background:{accent};color:white;border:none;border-radius:50%;width:42px;height:42px;
         font-size:1.1em;cursor:pointer;flex-shrink:0;}}
.sm-send:hover{{background:{accent_dark};}}
a.sm-link{{color:{accent_dark};}}
</style>
</head>
<body>
<header class="sm-head">
  <a href="/" class="sm-back">&larr; Home</a>
  <h1>Sister Mary</h1>
  <div class="sub">Be still, and know that I am God. &mdash; {phase_label}, {escape(date_label)}</div>
</header>

<div class="sm-quick">{quick_buttons}</div>

<div id="sm-msgs">
  {ho_banner}
  <div id="sm-thinking" class="sm-thinking" style="display:none;">Sister Mary is praying...</div>
</div>

<div class="sm-input-bar">
  <textarea id="sm-input" rows="1" placeholder="Speak with Sister Mary..."></textarea>
  <button class="sm-send" onclick="smSend()" title="Send">&#x2192;</button>
</div>

<div style="text-align:center;padding:8px 0 18px;">{new_conv_btn}</div>

<script>
{_ho_js}
var _smHistory = {history_js};

function _linkify(t) {{
    return t.replace(/(https?:\\/\\/[^\\s]+)/g,
        '<a class="sm-link" href="$1" target="_blank" rel="noopener">$1</a>');
}}
function _stripHandoffTags(t) {{
    return t.replace(/\\[(LUCY|LORENZO|GREGORY|MONICA|COACH|IZZY|SISTERMARY)\\][^[]*?\\[\\/(LUCY|LORENZO|GREGORY|MONICA|COACH|IZZY|SISTERMARY)\\]/g, '')
            .replace(/<remember[\\s\\S]*?<\\/remember>/g, '')
            .replace(/<frol_update[\\s\\S]*?<\\/frol_update>/g, '');
}}
function _renderHandoffBtns(text, parent) {{
    if (typeof renderHandoffButtons === 'function') {{
        renderHandoffButtons(text, parent);
    }}
}}

function _smRenderBubble(text) {{
    var msgs = document.getElementById('sm-msgs');
    var wrap = document.createElement('div');
    wrap.className = 'sm-bubble-wrap';
    var b = document.createElement('div');
    b.className = 'sm-bubble-sm';
    b.innerHTML = _linkify(_stripHandoffTags(text));
    wrap.appendChild(b);
    msgs.insertBefore(wrap, document.getElementById('sm-thinking'));
    return b;
}}
function _smRenderUser(text) {{
    var msgs = document.getElementById('sm-msgs');
    var b = document.createElement('div');
    b.className = 'sm-bubble-user';
    b.textContent = text;
    msgs.insertBefore(b, document.getElementById('sm-thinking'));
}}

// Replay history on load
if (_smHistory && _smHistory.length) {{
    for (var i = 0; i < _smHistory.length; i++) {{
        if (_smHistory[i].role === 'user') {{
            _smRenderUser(_smHistory[i].content);
        }} else {{
            var bb = _smRenderBubble(_smHistory[i].content);
            _renderHandoffBtns(_smHistory[i].content, bb.parentNode);
        }}
    }}
}}

function smQuick(text) {{
    var input = document.getElementById('sm-input');
    input.value = text;
    input.focus();
}}

function smSend() {{
    var input = document.getElementById('sm-input');
    var msg   = input.value.trim();
    if (!msg) return;
    input.value = '';
    input.style.height = 'auto';

    _smHistory.push({{role:'user', content: msg}});
    _smRenderUser(msg);
    document.getElementById('sm-thinking').style.display = '';
    window.scrollTo(0, document.body.scrollHeight);

    fetch('/sister-mary-chat', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: 'iso=' + encodeURIComponent(new Date().toISOString().split('T')[0])
            + '&message=' + encodeURIComponent(msg)
    }}).then(function(r) {{
        document.getElementById('sm-thinking').style.display = 'none';
        if (!r.ok) {{
            _smRenderBubble('Sister Mary is unavailable right now. Please check the API key in Settings.');
            return;
        }}
        var bubble  = _smRenderBubble('');
        var full    = '';
        var reader  = r.body.getReader();
        var decoder = new TextDecoder();
        function read() {{
            return reader.read().then(function(res) {{
                if (res.done) {{
                    bubble.innerHTML = _linkify(_stripHandoffTags(full));
                    _renderHandoffBtns(full, bubble.parentNode);
                    _smHistory.push({{role:'assistant', content: full}});
                    return;
                }}
                full += decoder.decode(res.value, {{stream: true}});
                bubble.innerHTML = _linkify(_stripHandoffTags(full));
                window.scrollTo(0, document.body.scrollHeight);
                return read();
            }});
        }}
        read().catch(console.error);
    }}).catch(function() {{
        document.getElementById('sm-thinking').style.display = 'none';
        _smRenderBubble('Connection error. Please try again.');
    }});
}}

document.getElementById('sm-input').addEventListener('input', function() {{
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
}});
document.getElementById('sm-input').addEventListener('keydown', function(e) {{
    if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); smSend(); }}
}});

{welcome_bubble_js}
</script>
</body>
</html>"""
