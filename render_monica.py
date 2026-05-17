"""
render_monica.py — Dr. Monica, Child Development Expert & Pediatric Health Companion
                   for the McAdams family.

Named after Saint Monica, patron of mothers. Dr. Monica combines the warmth
of a trusted family friend with the knowledge of a physician — specifically,
"a friend whose sister is a doctor." She knows pediatric development, CDC/AAP
guidelines, evidence-based care, and current illness patterns. She is never
alarmist but always clear about when to call the real doctor.

API: POST /dr-monica-chat
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


def _load_monica_history_safe() -> list:
    try:
        from data_helpers import load_monica_history
        return load_monica_history()
    except Exception:
        return []


def _get_anchor_context_monica(iso: str) -> list:
    """Return capacity + John status lines for Monica's context."""
    try:
        from render_morning_anchor import _get_anchor_state
        anchor = _get_anchor_state(iso)
        cap    = anchor.get("capacity", "").strip().lower()
        john   = anchor.get("john_status", "").strip()
        james  = anchor.get("james_note", "").strip()
        lines  = []
        if cap == "low":
            lines.append("Lauren's capacity today: LOW — she may be more anxious or overwhelmed. Be especially warm and reassuring.")
        elif cap == "medium":
            lines.append("Lauren's capacity today: MEDIUM — a solid day, normal bandwidth.")
        elif cap == "high":
            lines.append("Lauren's capacity today: HIGH — Lauren is in a good place today.")
        if john:
            if john.lower() in ("wfh", "working from home", "home office", "work from home"):
                lines.append("John is WFH — another adult is present to help if a child needs extra attention.")
            elif "travel" in john.lower() or "away" in john.lower():
                lines.append("John is traveling — Lauren is the only adult today. Factor this into your advice.")
            else:
                lines.append(f"John: {john}")
        if james:
            lines.append(f"James update: {james}")
        return lines
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# System prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def build_monica_context(iso: str, weekday: str, date_label: str) -> str:
    from datetime import datetime as _dt
    _now_e    = _dt.now(_EASTERN)
    _time_str = _now_e.strftime("%-I:%M %p")

    _anchor_lines = _get_anchor_context_monica(iso)

    lines = [
        "You are Dr. Monica — a child development expert and pediatric health companion",
        "for the McAdams family. You are named in honor of Saint Monica, patron of mothers.",
        "",
        "YOUR PERSONA: You are like a brilliant, warm friend who happens to have a sister",
        "who is a pediatrician. You speak plainly, with warmth and confidence, not clinical",
        "distance. You share what you know freely. You are never alarmist, but you are",
        "always honest about when something warrants a real doctor's attention.",
        "",
        "CRITICAL DISCLAIMER YOU HOLD INTERNALLY:",
        "You are not a doctor. You do not diagnose or prescribe. You share evidence-based",
        "information, dosing guidelines from AAP/CDC/manufacturer recommendations,",
        "and help Lauren think through what she's seeing. You ALWAYS recommend calling",
        "the pediatrician when symptoms are concerning, escalating, or in a child under 3 months.",
        "You say things like 'Based on what I know from AAP guidelines...' or",
        "'My sister would say...' — not 'I diagnose your child with...'",
        "",
        f"CRITICAL — TODAY'S DATE: {weekday}, {date_label} ({iso}).",
        "This is authoritative. If any earlier messages mention a different date, those are from",
        "a previous session. Always use the date above.",
        f"CURRENT TIME: {_time_str} Eastern",
    ]

    if _anchor_lines:
        lines += ["", "== TODAY'S HOUSEHOLD STATUS =="] + _anchor_lines

    lines += [
        "",
        "== THE McADAMS CHILDREN — DEVELOPMENT PROFILES ==",
        "",
        "JAMES — 13 months old.",
        "  Stage: Late infancy / early toddlerhood.",
        "  Expected milestones (12-15 months per AAP/CDC):",
        "    Motor: Walking with support or independently, pulling to stand, cruising furniture.",
        "    Language: 1-3 words with meaning (mama, dada, no), responsive to name, points.",
        "    Social: Waves bye-bye, plays peek-a-boo, separation anxiety is normal.",
        "    Feeding: Transitioning to table foods, sippy cup, whole milk (12+ months).",
        "  Red flags to watch: Not standing with support, no words by 16 months,",
        "    not pointing by 12 months, not responding to name.",
        "  Next well-child visit: 15 months (check with their pediatrician).",
        "  Vaccines due at 12 months: MMR, Varicella, Hep A (1st), Hep B (3rd if not given).",
        "",
        "MICHAEL — 5 years old.",
        "  Stage: Preschool/early kindergarten development.",
        "  Expected milestones (5-year-old per AAP):",
        "    Motor: Hops, skips, catches a bounced ball, writes some letters, draws person with 6 parts.",
        "    Language: Speaks in full sentences, tells stories, asks 'why' constantly.",
        "    Social: Plays cooperatively, understands rules, beginning reading readiness.",
        "    Cognitive: Counts to 10+, knows colors/shapes, beginning letter sounds.",
        "  Developmental considerations: He has a 13-month-old brother — regression behaviors",
        "    (thumb sucking, baby talk) are normal during sibling transitions.",
        "  Well-child visit: 5-year checkup (kindergarten physical), vision/hearing screening.",
        "",
        "JP — 14 years old.",
        "  Stage: Mid-adolescence.",
        "  Health considerations: Pubescent development, sleep needs 8-10 hours, sports safety.",
        "  Mental health: Adolescent identity formation, peer relationships, academic pressure.",
        "  Appropriate health conversations: nutrition for growth, screen time, sleep hygiene.",
        "",
        "JOSEPH — 12 years old.",
        "  Stage: Early adolescence / pre-pubescent.",
        "  Health considerations: Growth spurts, emotional regulation, beginning puberty awareness.",
        "  Sleep needs: 9-11 hours. Appetite increases. Coordination may temporarily decrease.",
        "",
        "== PEDIATRIC HEALTH KNOWLEDGE BASE ==",
        "",
        "MEDICATION DOSING (always by weight when possible — ask Lauren for current weight):",
        "  Acetaminophen (Tylenol): 10-15 mg/kg/dose every 4-6 hours. Max 5 doses/24 hours.",
        "    Example: 22 lb (10 kg) child → 100-150 mg per dose.",
        "  Ibuprofen (Motrin/Advil): 5-10 mg/kg/dose every 6-8 hours. Only 6+ months.",
        "    Do NOT give with stomach problems, dehydration, or kidney concerns.",
        "  Benadryl (diphenhydramine): NOT recommended under 2 years. 2+: 1 mg/kg/dose.",
        "  Claritin (loratadine): 2-5 years: 5 mg/day. 6+ years: 10 mg/day.",
        "  Saline nasal spray: Safe for all ages, anytime.",
        "  Honey for cough: 1 tsp for kids 1+. NEVER under 1 year (botulism risk).",
        "  Probiotics: Safe for most ages; helpful during/after antibiotics.",
        "",
        "FEVER GUIDELINES (AAP):",
        "  Under 3 months: ANY fever (100.4°F / 38°C) → call doctor or go to ER immediately.",
        "  3-6 months: Fever >100.4°F → call doctor.",
        "  6 months - 2 years: Fever >104°F or lasting >24-48 hours → call doctor.",
        "  2+ years: Fever with stiff neck, rash, severe headache, trouble breathing → ER.",
        "  Fever itself is not harmful — it's the body fighting infection.",
        "  Treat discomfort, not the number. Alternate Tylenol and Motrin for comfort.",
        "",
        "WHEN TO CALL THE DOCTOR — ALWAYS:",
        "  - Any sick child under 3 months with fever",
        "  - Difficulty breathing, blue lips",
        "  - Severe dehydration (no wet diaper 8+ hours, no tears, sunken eyes)",
        "  - Seizure (even brief febrile seizure — call after child is stable)",
        "  - Rash with fever and stiff neck",
        "  - Child is inconsolable for 2+ hours",
        "  - Symptoms getting worse after 48-72 hours instead of improving",
        "  - Ear pain with fever >3 days",
        "  - Sore throat with fever, no cough (could be strep)",
        "",
        "COMMON ILLNESSES — EVIDENCE-BASED CARE:",
        "  RSV: Highly contagious, peaks Oct-March. Most dangerous in infants under 2.",
        "    Care: Saline, suction, humidifier, keep hydrated. No specific treatment.",
        "    Watch: Fast breathing, chest retractions, poor feeding in infants.",
        "  Hand Foot Mouth (HFMD): Common in kids under 5. Blisters in mouth, hands, feet.",
        "    Care: Pain relief (Tylenol/Motrin), cold foods, hydration. Contagious 7-10 days.",
        "  Strep throat: Bacterial — needs antibiotics. Fever, sore throat, no runny nose.",
        "    Test before treating. Penicillin/amoxicillin is standard.",
        "  Croup: Barky cough worse at night. Cool night air or steam often helps immediately.",
        "    Steroid (dexamethasone) from doctor for moderate-severe cases.",
        "  Ear infections: Often viral (no antibiotic needed), especially in older kids.",
        "    AAP: Watchful waiting 48-72 hours for mild cases in 2+ year olds.",
        "  COVID-19: Treat symptoms. Isolate. Test. Contact pediatrician if high risk or severe.",
        "  Flu: Tamiflu most effective within 48 hours of symptoms. Annual flu vaccine recommended.",
        "  Norovirus: Stomach bug. Hydration is key. BRAT diet. Contagious 48 hours after recovery.",
        "",
        "== HOLISTIC DEVELOPMENT — YOUR BROADER VIEW ==",
        "You watch the whole child — how sleep, nutrition, stress, screen time, physical activity,",
        "and family dynamics affect development. You coordinate with:",
        "  - Father Gregory: Is a learning difficulty actually a developmental delay?",
        "    Is James showing appropriate language readiness for future learning?",
        "  - Coach: Is Michael's motor development on track? Is JP's growth affecting his athletic training?",
        "",
        "== SAINT MONICA — YOUR PATRON ==",
        "Saint Monica prayed for her son Augustine for 17 years before his conversion.",
        "She teaches that a mother's patient, persistent love — even through worry — is sacred.",
        "When Lauren is anxious about a child, you hold that truth: love and patience, not panic.",
        "",
        "== TONE ==",
        "Warm, clear, confident, never alarmist. You acknowledge Lauren's worry first.",
        "You give her concrete information. You tell her when something is serious.",
        "You never minimize ('it's probably nothing') OR catastrophize.",
        "You always end sick-child conversations with: 'Trust your instincts — you know your child.'",
        "You note when something is outside your knowledge and should go to her real pediatrician.",
        "- When you have enough information to give a clear recommendation, give it. Don't hide behind",
        "  'it depends' or 'every child is different' when Lauren has given you specifics.",
        "- If Lauren's plan for a sick child or a developmental concern misses something important,",
        "  name it before confirming the plan.",
        "- After answering, always offer one concrete next step Lauren hasn't mentioned —",
        "  a follow-up sign to watch for, a timing consideration, or a question to ask at the next pediatrician visit.",
    ]

    from data_helpers import get_memory_context_block as _gmcb
    lines += ["", _gmcb(), ""]
    lines += [""] + frol_context_block(weekday) + frol_edit_instructions()
    lines += [""] + companion_system_block("MONICA")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Page renderer
# ─────────────────────────────────────────────────────────────────────────────

def _render_grooming_reminders(iso: str) -> str:
    """Surface due grooming chores (haircuts, nail trims, shoe-size, dental,
    eye exams) on Monica's page. Honors notification_prefs.channels —
    when channels is set and explicitly excludes 'dashboard' the card is
    suppressed; otherwise shown (default-on)."""
    try:
        from data_helpers import get_due_grooming, load_app_settings
        prefs = (load_app_settings() or {}).get("notification_prefs") or {}
        chans = prefs.get("channels")
        if isinstance(chans, list) and chans and "dashboard" not in chans:
            return ""
        due = get_due_grooming(iso) or []
    except Exception:
        return ""
    if not due:
        return ""
    rows = []
    for d in due:
        item = d.get("item") or {}
        text = item.get("text") if isinstance(item, dict) else str(item)
        person = d.get("person", "")
        bucket = d.get("bucket", "")
        rows.append(
            f'<li style="margin:4px 0;font-size:0.88em;">'
            f'<strong style="color:#8b3a5c;">{escape(person)}</strong> '
            f'&middot; {escape(text or "")} '
            f'<span style="color:#a88;font-size:0.82em;">({escape(bucket)})</span></li>'
        )
    return (
        '<div style="background:#fff;border:1px solid #e0b8cc;border-left:4px solid #8b3a5c;'
        'border-radius:10px;padding:12px 16px;margin:0 0 16px;">'
        '<div style="font-weight:700;color:#8b3a5c;font-size:0.86em;text-transform:uppercase;'
        'letter-spacing:0.05em;margin-bottom:6px;">&#9986; Grooming reminders &mdash; due today</div>'
        f'<ul style="margin:0;padding-left:20px;color:#5a3a48;">{"".join(rows)}</ul>'
        '</div>'
    )


def render_monica_page(q: str = "", from_: str = "") -> str:
    today      = _today_eastern()
    iso        = today.isoformat()
    weekday    = today.strftime("%A")
    date_label = today.strftime("%B %d, %Y")
    h          = _hour_eastern()
    from companion_handoffs import handoff_prefill as _hp
    q_safe, ho_banner = _hp("MONICA", q, from_)

    if h < 12:
        greeting    = "Good morning. How are the children?"
        phase_label = "Morning check-in"
        phase_color = "#8b3a5c"
        opener      = "Good morning, Dr. Monica! I wanted to check in about the kids this morning."
        quick_prompts = [
            ("James's milestones",          "Walk me through what James should be doing at 13 months. Is he on track?"),
            ("Michael's development",       "What should I be watching for in Michael's development at age 5?"),
            ("Someone is sick",             "One of my kids isn't feeling well. Can I describe the symptoms?"),
            ("Fever guidance",              "Can you walk me through when I should worry about a fever?"),
            ("Medication dosing",           "Help me figure out the right dose of Tylenol/Motrin for my child."),
        ]
    elif h < 17:
        greeting    = "How are the little ones?"
        phase_label = "Midday check-in"
        phase_color = "#7a2a5c"
        opener      = "Dr. Monica, I wanted to talk through something about one of the kids."
        quick_prompts = [
            ("Sick child — describe symptoms", "My child is sick. Let me describe what I'm seeing."),
            ("Is this normal?",             "I've noticed something about one of my kids and want to know if it's normal."),
            ("James is not walking yet",    "James is 13 months and not walking independently yet. Should I be concerned?"),
            ("Michael's behavior",          "Michael is doing something I'm not sure is developmental or behavioral."),
            ("When to call the doctor",     "Walk me through when I should call the pediatrician vs. wait and watch."),
        ]
    else:
        greeting    = "Evening. Everything okay with the kids?"
        phase_label = "Evening check-in"
        phase_color = "#6a1a4c"
        opener      = "Dr. Monica, I wanted to check in about the kids before we head into the night."
        quick_prompts = [
            ("Sick child overnight plan",   "One of my kids is sick. Walk me through how to manage it overnight."),
            ("Sleep concerns",              "I have some concerns about one of my children's sleep."),
            ("Illness tomorrow — school?",  "My child has been sick. When is it safe to restart school at home?"),
            ("James's evening routine",     "What does a good bedtime routine look like for a 13-month-old?"),
            ("Weekly development check",    "Give me a quick weekly check on where James and Michael are developmentally."),
        ]

    history     = _load_monica_history_safe()
    has_history = bool(history)
    history_js  = json.dumps([
        {"role": m["role"], "content": m.get("content", "")}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content", "")
    ])

    quick_buttons = "".join(
        f'<button onclick=\'monicaQuick({_ej(prompt)})\' '
        f'style="background:#fdf0f6;border:1px solid #e0b0c8;border-radius:20px;'
        f'padding:6px 14px;font-size:0.8em;cursor:pointer;color:#8b3a5c;font-family:inherit;'
        f'white-space:nowrap;" '
        f'onmouseover="this.style.background=\'#f5d8e8\'" '
        f'onmouseout="this.style.background=\'#fdf0f6\'">'
        f'{escape(label)}</button>'
        for label, prompt in quick_prompts
    )

    new_conv_btn = (
        '<form method="POST" action="/dr-monica-clear-history" style="display:inline;">'
        '<button type="submit" style="background:none;border:none;font-size:0.72em;'
        'color:#bbb;cursor:pointer;font-family:inherit;padding:0;">&#10005; New conversation</button>'
        '</form>'
    ) if has_history else ''

    accent = "#8b3a5c"

    if h < 12:
        welcome = "Good morning! I'm here for whatever you need — development questions, a sick kiddo, milestone worries, or just a check-in. What's on your mind?"
    elif h < 17:
        welcome = "Hi! How are James and Michael doing today? And are JP and Joseph doing alright? Tell me what's going on."
    else:
        welcome = "Evening. How did the day go with the kids? Any health or development concerns before the night?"

    _ho_js = handoff_js("MONICA")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Dr. Monica &middot; McAdams Family</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#fdf5f9;color:#1a1a1a;min-height:100vh;}}
.mo-bubble-user{{
    background:#8b3a5c;color:white;padding:10px 14px;border-radius:16px 16px 4px 16px;
    font-size:0.9em;line-height:1.55;max-width:75%;align-self:flex-end;margin-left:auto;
}}
.mo-bubble-mo{{
    background:white;border:1px solid #e0b8cc;padding:12px 16px;
    border-radius:4px 16px 16px 16px;font-size:0.9em;line-height:1.65;
    max-width:85%;white-space:pre-wrap;color:#1a1a1a;
}}
.mo-bubble-wrap{{display:flex;flex-direction:column;gap:12px;}}
@keyframes mo-pulse{{0%,100%{{opacity:1;}}50%{{opacity:0.4;}}}}
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
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:16px;">
        <div style="width:52px;height:52px;border-radius:50%;
                    background:linear-gradient(135deg,{accent},#c05a8c);
                    display:flex;align-items:center;justify-content:center;font-size:1.5em;
                    flex-shrink:0;box-shadow:0 2px 10px rgba(139,58,92,0.25);">
            &#127800;
        </div>
        <div>
            <div style="font-family:Georgia,serif;font-size:1.4em;font-weight:600;color:#1a1a1a;line-height:1.1;">
                {escape(greeting)}
            </div>
            <div style="font-size:0.85em;color:#888;margin-top:2px;">
                Dr. Monica &middot; {escape(weekday)}, {escape(date_label)}
            </div>
        </div>
    </div>

    <!-- Disclaimer banner -->
    <div style="background:#fdf0f6;border:1px solid #e0b8cc;border-radius:10px;
                padding:8px 14px;margin-bottom:16px;font-size:0.76em;color:#8b5a70;line-height:1.5;">
        &#9432; Dr. Monica shares evidence-based information as a knowledgeable friend, not as your child's physician.
        Always consult your real pediatrician for diagnosis and treatment decisions.
    </div>

    {_render_grooming_reminders(iso)}

    <!-- Quick prompts -->
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;">
        {quick_buttons}
    </div>

    {ho_banner}

    <!-- Conversation -->
    <div id="mo-chat" class="mo-bubble-wrap" style="margin-bottom:20px;"></div>

    <!-- Thinking -->
    <div id="mo-thinking" style="display:none;padding:10px 0;color:#888;font-size:0.85em;">
        <span style="animation:mo-pulse 1.2s ease-in-out infinite;display:inline-block;">
            Dr. Monica is thinking&hellip;
        </span>
    </div>

</div>

<!-- Floating input -->
<div style="position:fixed;bottom:0;left:0;right:0;background:white;
            border-top:1px solid #e0b8cc;padding:12px 16px;z-index:100;">
    <div style="max-width:760px;margin:0 auto;display:flex;gap:10px;align-items:flex-end;">
        <textarea id="mo-input" rows="1" placeholder="Ask Dr. Monica…"
            style="flex:1;border:1px solid #e0b0c8;border-radius:12px;
                   padding:10px 14px;font-size:0.95em;font-family:inherit;
                   resize:none;outline:none;background:#fdf5f9;max-height:120px;">{q_safe}</textarea>
        <button id="mo-send" onclick="monicaSend()"
            style="width:44px;height:44px;border-radius:50%;background:{accent};
                   border:none;color:white;font-size:1.1em;cursor:pointer;flex-shrink:0;">
            &#8593;
        </button>
    </div>
</div>

<script>
var _moHistory = {history_js};
var _moIso     = {_ej(iso)};
{_ho_js}

(function() {{
    for (var i = 0; i < _moHistory.length; i++) {{
        var m = _moHistory[i];
        if (m.role === 'user')           _moRenderUser(m.content);
        else if (m.role === 'assistant') _moRenderBubble(m.content);
    }}
    if (_moHistory.length) window.scrollTo(0, document.body.scrollHeight);
}})();

function _moRenderBubble(text) {{
    var wrap = document.getElementById('mo-chat');
    var row  = document.createElement('div');
    var bub  = document.createElement('div');
    bub.className = 'mo-bubble-mo';
    bub.innerHTML = _linkify(_stripHandoffTags(text));
    row.appendChild(bub);
    _renderHandoffBtns(text, row);
    wrap.appendChild(row);
    window.scrollTo(0, document.body.scrollHeight);
    return bub;
}}

function _moRenderUser(text) {{
    var wrap = document.getElementById('mo-chat');
    var row  = document.createElement('div');
    row.style.cssText = 'display:flex;justify-content:flex-end;';
    var bub  = document.createElement('div');
    bub.className   = 'mo-bubble-user';
    bub.textContent = text;
    row.appendChild(bub);
    wrap.appendChild(row);
    window.scrollTo(0, document.body.scrollHeight);
}}

function monicaQuick(prompt) {{
    document.getElementById('mo-input').value = prompt;
    monicaSend();
}}

function monicaSend() {{
    var input = document.getElementById('mo-input');
    var msg   = input.value.trim();
    if (!msg) return;
    input.value = '';
    input.style.height = 'auto';

    _moHistory.push({{role:'user', content: msg}});
    _moRenderUser(msg);
    document.getElementById('mo-thinking').style.display = '';
    window.scrollTo(0, document.body.scrollHeight);

    fetch('/dr-monica-chat', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: 'iso=' + encodeURIComponent(new Date().toISOString().split('T')[0])
            + '&message=' + encodeURIComponent(msg)
    }}).then(function(r) {{
        document.getElementById('mo-thinking').style.display = 'none';
        if (!r.ok) {{
            _moRenderBubble('Dr. Monica is unavailable. Please check your API key in Settings.');
            return;
        }}
        var bubble  = _moRenderBubble('');
        var full    = '';
        var reader  = r.body.getReader();
        var decoder = new TextDecoder();
        function read() {{
            return reader.read().then(function(res) {{
                if (res.done) {{
                    bubble.innerHTML = _linkify(_stripHandoffTags(full));
                    _renderHandoffBtns(full, bubble.parentNode);
                    _moHistory.push({{role:'assistant', content: full}});
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
        document.getElementById('mo-thinking').style.display = 'none';
        _moRenderBubble('Connection error. Please try again.');
    }});
}}

document.getElementById('mo-input').addEventListener('input', function() {{
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
}});
document.getElementById('mo-input').addEventListener('keydown', function(e) {{
    if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); monicaSend(); }}
}});

if (!_moHistory.length) {{
    _moRenderBubble({_ej(welcome)});
}}
</script>
</body>
</html>"""
