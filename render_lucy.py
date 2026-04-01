"""
render_lucy.py — Lucy, your AI day guide.

Lucy is a warm, knowledgeable companion who guides Mom through:
  - Morning: Setting up and planning the day
  - Midday:  Checking in and adjusting
  - Evening: Closing out and planning tomorrow

She knows everything: school lists, calendar events, nap schedules,
meal prep, fixed + unscheduled tasks, and capacity level.

API: POST /lucy-chat  → streams Claude response as plain text
"""
from datetime import date, datetime
from html import escape
try:
    from zoneinfo import ZoneInfo
    _EASTERN = ZoneInfo("America/New_York")
except ImportError:
    import pytz
    _EASTERN = pytz.timezone("America/New_York")

def _now_eastern() -> datetime:
    return datetime.now(_EASTERN)

def _today_eastern() -> date:
    return _now_eastern().date()


# ─────────────────────────────────────────────────────────────────────────────
# Phase detection
# ─────────────────────────────────────────────────────────────────────────────

def _get_phase() -> str:
    """Return 'morning', 'midday', or 'evening' based on Eastern time."""
    h = _now_eastern().hour
    if h < 11:
        return "morning"
    elif h < 17:
        return "midday"
    else:
        return "evening"


# ─────────────────────────────────────────────────────────────────────────────
# Lucy system prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def build_lucy_context(iso: str, weekday: str, date_label: str, capacity: str = "") -> str:
    """
    Build Lucy's full system prompt — she knows the whole household.
    capacity: "high", "medium", "low", or ""
    """
    phase = _get_phase()

    capacity_note = ""
    if capacity:
        cap = capacity.lower()
        if cap == "high":
            capacity_note = "Mom has HIGH capacity today — full energy, can handle a lot."
        elif cap == "medium":
            capacity_note = "Mom has MEDIUM capacity today — moderate energy, plan thoughtfully."
        elif cap == "low":
            capacity_note = "Mom has LOW capacity today — conserve energy, simplify and prioritize ruthlessly."

    lines = [
        "You are Lucy — a warm, smart, and practical AI companion for a Catholic homeschooling family.",
        "You are not a generic assistant. You know this family deeply and speak to Mom personally.",
        f"Today is {weekday}, {date_label} ({iso}).",
        f"Current phase of day: {phase.upper()}.",
    ]

    if capacity_note:
        lines.append(capacity_note)

    lines += [
        "",
        "== YOUR PERSONALITY ==",
        "- Warm, direct, and encouraging — like a trusted friend who happens to know everything",
        "- Always address Mom directly (use 'you', not 'she')",
        "- Be specific: use real names, real times, real subjects from the data",
        "- Keep responses focused — bullet points and short paragraphs over walls of text",
        "- For LOW capacity days: suggest trimming, not adding; protect margins; validate rest",
        "- For HIGH capacity days: encourage tackling harder or delayed tasks",
        "- Never be preachy or lecture; just help",
        "- CRITICAL: Ask only ONE question at a time. Never stack multiple questions in one message.",
        "  Say what you need to say, then ask the single most important question. Wait for the answer.",
        "  If you have several things to ask, pick the most useful one and save the rest for later.",
        "- FORMATTING: Never use markdown. No ##, no **, no *, no ---, no backticks.",
        "  Use plain text only. For lists, use a simple dash or number at the start of a line.",
        "",
        "== FAMILY ==",
    ]

    # Children
    try:
        from daily_schedule_engine import CHILDREN
        from render_daily_bar import get_child_age
        for child in CHILDREN:
            age = get_child_age(child)
            age_str = f"{age['years']} years old" if age else "age unknown"
            lines.append(f"- {child}: {age_str}")
        lines.append("- James: baby/toddler, needs direct supervision at all times")
        lines.append("- Mom: the planner, primary teacher, and household manager")
    except Exception:
        lines.append("- JP, Joseph, Michael, James (toddler), Mom")

    lines += ["", "== FAMILY CONSTRAINTS & RULES =="]
    try:
        from render_settings import load_app_settings
        settings = load_app_settings()
        constraints = settings.get("family_constraints", {})
        fields = [
            ("supervision_rules",        "Supervision rules"),
            ("james_schedule",           "James care schedule"),
            ("school_durations",         "School duration per child"),
            ("meal_prep",                "Meal prep notes"),
            ("independence_notes",       "Independent work capacity"),
            ("mom_supervision_subjects", "Subjects needing Mom directly"),
            ("other_notes",              "Other notes"),
        ]
        any_found = False
        for key, label in fields:
            val = constraints.get(key, "")
            if val:
                lines.append(f"- {label}: {val}")
                any_found = True
        if not any_found:
            lines.append("(No constraints set yet — suggest Mom adds them in Settings)")
    except Exception:
        lines.append("(Could not load constraints)")

    lines += ["", "== TODAY'S CALENDAR EVENTS =="]
    try:
        from render_calendar import load_calendar_cache, events_for_date
        cache = load_calendar_cache()
        all_events = cache.get("events", [])
        today_events = events_for_date(all_events, iso)
        if today_events:
            for ev in today_events:
                t = ev.get("start", "")[-5:] if "T" in ev.get("start", "") else "all day"
                lines.append(f"- {ev.get('title','?')} at {t}")
        else:
            lines.append("No calendar events today.")
    except Exception:
        lines.append("(Calendar not available)")

    lines += ["", "== TODAY'S MEAL PLAN =="]
    try:
        from render_meals import load_meal_plan, _week_key
        plan = load_meal_plan(_week_key())
        days_data = plan.get("days", {})
        day_meals = days_data.get(weekday, {})
        prep_notes = plan.get("prep_notes", {}).get(weekday, "")
        if day_meals:
            for slot, label in [("breakfast","Breakfast"),("lunch","Lunch"),
                                  ("dinner","Dinner"),("snacks","Snacks")]:
                val = day_meals.get(slot, "")
                if val:
                    lines.append(f"- {label}: {val}")
        else:
            lines.append("No meal plan entries for today.")
        if prep_notes:
            lines.append(f"- Prep note: {prep_notes}")
    except Exception:
        lines.append("(Meal plan not available)")

    lines += ["", "== FAMILY SCHEDULE GRID =="]
    try:
        from data_helpers import load_family_schedule
        from render_schedule_support import generate_half_hour_times
        schedule = load_family_schedule()
        times = schedule.get("times", []) or generate_half_hour_times()
        day_slots = schedule.get("days", {}).get(weekday, {})
        populated = [(t, day_slots.get(t, "")) for t in times if day_slots.get(t, "")]
        if populated:
            for t, activity in populated:
                lines.append(f"  {t}: {activity}")
        else:
            lines.append("(No schedule grid entries for today)")
    except Exception:
        lines.append("(Schedule grid not available)")

    lines += ["", "== EACH CHILD'S SCHOOL & CHORES TODAY =="]
    try:
        from daily_schedule_engine import CHILDREN, build_schedule_payload
        for child in CHILDREN:
            payload = build_schedule_payload(child, weekday, date_label, iso)
            school_blocks = payload.get("school_blocks", [])
            chore_items   = payload.get("chore_items", [])
            lines.append(f"\n{child}:")
            if school_blocks:
                subjects = [b.get("subject", "?") for b in school_blocks]
                lines.append(f"  School: {', '.join(subjects)}")
            else:
                lines.append("  No school today")
            if chore_items:
                chores = [c.get("text", "?") for c in chore_items[:5]]
                lines.append(f"  Chores: {', '.join(chores)}")
    except Exception:
        lines.append("(Could not load child schedules)")

    lines += ["", "== CURRENT DAILY PLAN (MOM'S TASKS) =="]
    try:
        from render_daily_plan import load_daily_plan
        plan = load_daily_plan(iso)
        items = plan.get("items", [])
        if items:
            done_count = sum(1 for i in items if i.get("done"))
            lines.append(f"({done_count}/{len(items)} tasks completed so far)")
            for item in items:
                t    = item.get("time", "—")
                text = item.get("text", "")
                done = "✓" if item.get("done") else "○"
                lines.append(f"  [{done}] {t}: {text}")
        else:
            lines.append("(No plan items yet)")
    except Exception:
        lines.append("(Could not load daily plan)")

    lines += ["", "== UNSCHEDULED TASKS =="]
    try:
        from data_helpers import load_manual_tasks, active_manual_tasks
        all_tasks = load_manual_tasks()
        active    = active_manual_tasks(all_tasks)
        if active:
            for t in active[:8]:
                pri = t.get("priority", "")
                lines.append(f"- [{pri}] {t.get('text','')}")
        else:
            lines.append("No active unscheduled tasks.")
    except Exception:
        lines.append("(Could not load manual tasks)")

    lines += ["", "== LITURGICAL CONTEXT =="]
    try:
        from saint_data import fetch_saint_data
        from render_liturgical import get_day_info
        lit     = get_day_info(date.fromisoformat(iso))
        season  = lit.get("season", "")
        feast   = lit.get("feast_name", "")
        sd      = fetch_saint_data(date.fromisoformat(iso))
        saint   = sd.get("name", "")
        readings = sd.get("readings", {})
        gospel  = readings.get("gospel", "")
        if season: lines.append(f"- Liturgical season: {season}")
        if feast:  lines.append(f"- Feast: {feast}")
        if saint:  lines.append(f"- Saint of the day: {saint}")
        if gospel: lines.append(f"- Gospel: {gospel}")
    except Exception:
        pass

    # Phase-specific instructions
    lines += ["", "== GUIDANCE BY PHASE =="]
    if phase == "morning":
        lines += [
            "It is morning. Help Mom set up her day.",
            "Open by summarizing the key things she needs to know: any calendar events, meal prep needed, each child's main focus.",
            "Then suggest a practical order for the morning.",
            "If capacity is LOW, proactively suggest what to drop or simplify.",
            "Ask if she wants a full plan built out.",
        ]
    elif phase == "midday":
        lines += [
            "It is midday. Check in on how the day is going.",
            "Reference what should have happened this morning and what's coming up.",
            "Help adjust if something ran long or was skipped.",
            "Identify what still needs to happen before dinner.",
        ]
    else:
        lines += [
            "It is evening. Help Mom close out the day and plan tomorrow.",
            "Acknowledge what was accomplished today.",
            "Look at tomorrow's calendar, meals, and school to help her prepare.",
            "Keep it gentle — the day is winding down.",
            "At some natural point in the conversation, ask: 'Was there anything memorable that happened today",
            " — something you'd want to remember?' If she shares something, let her know she can save it",
            " to the Memory Book using the button that appears below your response.",
        ]

    # Memory book entries
    lines += ["", "== MEMORY BOOK (recent entries) =="]
    try:
        from render_memory_book import load_memory_book
        book    = load_memory_book()
        entries = book.get("entries", [])[:5]
        if entries:
            for e in entries:
                lines.append(f"- [{e.get('date','')}] {e.get('text','')}")
        else:
            lines.append("(No memories saved yet)")
    except Exception:
        lines.append("(Memory book not available)")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Lucy page renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_lucy_page(iso: str = "") -> str:
    today    = _today_eastern()
    iso      = iso or today.isoformat()
    weekday  = today.strftime("%A")
    date_label = today.strftime("%B %d, %Y")
    phase    = _get_phase()

    # Greeting and subtitle by phase
    if phase == "morning":
        greeting      = "Good morning."
        phase_label   = "Morning planning"
        phase_color   = "#c49020"
        opener_prompt = f"Good morning, Lucy! It's {date_label}. What do I need to know to start my day?"
        quick_prompts = [
            ("What's my morning look like?",       "What's my morning look like?"),
            ("Who needs what today?",               "Walk me through each child's day."),
            ("What needs prep for dinner?",         "What needs to be done for dinner today?"),
            ("Help me plan around low energy",      "I have low capacity today. Help me simplify."),
            ("What's first?",                       "What's the single most important thing to do first?"),
        ]
    elif phase == "midday":
        greeting      = "How's your day going?"
        phase_label   = "Midday check-in"
        phase_color   = "#1a6050"
        opener_prompt = f"Lucy, I'm checking in midday. How are we doing and what still needs to happen?"
        quick_prompts = [
            ("What's left for today?",              "What still needs to happen before the end of the day?"),
            ("Something fell behind — help me",     "Something fell behind this morning. Help me adjust."),
            ("Who needs me right now?",             "Who most needs my attention right now?"),
            ("Quick afternoon plan",                "Give me a simple afternoon plan."),
            ("Am I on track?",                      "Am I on track? Flag anything I might be forgetting."),
        ]
    else:
        greeting      = "Let's wind down."
        phase_label   = "Evening review"
        phase_color   = "#4a3a8a"
        opener_prompt = f"Good evening, Lucy. Help me close out today and think about tomorrow."
        quick_prompts = [
            ("What did we accomplish today?",       "Summarize what we accomplished today."),
            ("What do I need to prep for tomorrow?","What do I need to prep tonight for tomorrow?"),
            ("Walk me through tomorrow",            "Walk me through tomorrow's schedule and what to expect."),
            ("What didn't happen today?",           "What didn't get done today that I should carry forward?"),
            ("Keep it simple for tomorrow",         "Keep tomorrow simple. What are the 3 most important things?"),
        ]

    quick_buttons = "".join(
        f'<button onclick="lucyQuick({escape_js(prompt)})" '
        f'style="background:#faf8f5;border:1px solid #e4dbd2;border-radius:20px;'
        f'padding:6px 14px;font-size:0.8em;cursor:pointer;color:#555;font-family:inherit;'
        f'white-space:nowrap;transition:background 0.15s;" '
        f'onmouseover="this.style.background=\'#f0ebe4\'" '
        f'onmouseout="this.style.background=\'#faf8f5\'">'
        f'{escape(label)}</button>'
        for label, prompt in quick_prompts
    )

    # Phase dot color
    phase_dot = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{phase_color};margin-right:6px;"></span>'

    body = f"""
<style>
.lucy-bubble-user {{
    background:#3b2a1a;color:white;padding:10px 14px;border-radius:16px 16px 4px 16px;
    font-size:0.9em;line-height:1.55;max-width:75%;align-self:flex-end;margin-left:auto;
}}
.lucy-bubble-lucy {{
    background:white;border:1px solid #e4dbd2;padding:12px 16px;
    border-radius:4px 16px 16px 16px;font-size:0.9em;line-height:1.65;
    max-width:85%;white-space:pre-wrap;color:#1a1a1a;
}}
.lucy-bubble-wrap {{ display:flex;flex-direction:column;gap:12px; }}
</style>

<div style="max-width:760px;margin:0 auto;padding:20px 16px 24px;">

    <!-- Back + phase label -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
        <a href="/" style="font-size:0.82em;color:#aaa;text-decoration:none;">&larr; Dashboard</a>
        <div style="display:flex;align-items:center;gap:14px;">
            <a href="/memory-book" style="font-size:0.78em;color:#c49020;text-decoration:none;">📖 Memory Book</a>
            <span style="font-size:0.78em;color:#aaa;">{phase_dot}{escape(phase_label)}</span>
        </div>
    </div>

    <!-- Lucy header -->
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:28px;">
        <div style="width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,#8b5a3c,#c49020);
                    display:flex;align-items:center;justify-content:center;font-size:1.5em;
                    flex-shrink:0;box-shadow:0 2px 10px rgba(139,90,60,0.25);">
            🌿
        </div>
        <div>
            <div style="font-family:Georgia,serif;font-size:1.5em;font-weight:600;color:#1a1a1a;line-height:1.1;">
                {escape(greeting)}
            </div>
            <div style="font-size:0.85em;color:#888;margin-top:2px;">
                Lucy &middot; {escape(weekday)}, {escape(date_label)}
            </div>
        </div>
    </div>

    <!-- Quick prompts -->
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px;">
        {quick_buttons}
    </div>

    <!-- Capacity selector -->
    <div style="background:#fdfaf7;border:1px solid #ede7e0;border-radius:10px;
                padding:10px 14px;margin-bottom:24px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span style="font-size:0.8em;color:#888;font-weight:600;white-space:nowrap;">My capacity today:</span>
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
    <div id="lucy-history" class="lucy-bubble-wrap"
         style="min-height:120px;margin-bottom:20px;">
    </div>

    <!-- Typing indicator -->
    <div id="lucy-typing"
         style="display:none;font-size:0.82em;color:#aaa;font-style:italic;padding:4px 0;margin-bottom:12px;">
        Lucy is thinking&hellip;
    </div>

    <!-- Input bar — inline (not fixed) so iOS keyboard doesn't cover it -->
    <div id="lucy-input-bar"
         style="background:white;border:1px solid #e4dbd2;border-radius:16px;
                padding:10px 12px;display:flex;gap:8px;align-items:flex-end;
                margin-top:16px;">
        <textarea id="lucy-input" rows="1"
                  placeholder="Ask Lucy anything about today…"
                  onkeydown="if(event.key==='Enter'&&!event.shiftKey){{event.preventDefault();lucySend();}}"
                  oninput="this.style.height='auto';this.style.height=Math.min(this.scrollHeight,120)+'px';"
                  style="flex:1;resize:none;overflow:hidden;font-family:inherit;font-size:16px;
                         padding:8px 12px;border:1.5px solid #e4dbd2;border-radius:10px;
                         outline:none;line-height:1.5;max-height:120px;background:#fdfaf7;">
        </textarea>
        <button onclick="lucySend()"
                style="padding:10px 16px;background:#3b2a1a;color:white;border:none;
                       border-radius:10px;cursor:pointer;font-size:0.88em;font-weight:600;
                       font-family:inherit;flex-shrink:0;align-self:flex-end;">
            Send
        </button>
    </div>
    <!-- Extra space so input clears the keyboard when scrolled into view -->
    <div style="height:320px;"></div>

</div>

<script>
var _lucyIso      = '{escape(iso)}';
var _lucyCapacity = '';
var _lucyHistory  = []; // {{role, content}}

function setCapacity(level) {{
    _lucyCapacity = level;
    ['high','medium','low'].forEach(function(l) {{
        var btn = document.getElementById('cap-' + l);
        btn.style.fontWeight = (l === level) ? '700' : '600';
        btn.style.opacity    = (l === level) ? '1' : '0.5';
    }});
    var notes = {{high:"Full energy \u2014 let\u2019s make the most of it.",
                  medium:"Moderate energy \u2014 plan thoughtfully.",
                  low:"Low energy \u2014 let\u2019s keep it simple."}};
    document.getElementById('cap-note').textContent = notes[level] || '';
}}

function lucyQuick(prompt) {{
    var input = document.getElementById('lucy-input');
    input.value = prompt;
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    input.focus();
}}

function lucySend() {{
    var input = document.getElementById('lucy-input');
    var msg   = input.value.trim();
    if (!msg) return;
    input.value = '';
    input.style.height = 'auto';

    // Add user bubble
    _lucyHistory.push({{role:'user', content: msg}});
    _renderBubble('user', msg);

    // Show typing
    document.getElementById('lucy-typing').style.display = '';
    _scrollToInput();

    fetch('/lucy-chat', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: 'iso='       + encodeURIComponent(_lucyIso)
            + '&capacity=' + encodeURIComponent(_lucyCapacity)
            + '&message='  + encodeURIComponent(msg)
            + '&history='  + encodeURIComponent(JSON.stringify(_lucyHistory.slice(-10)))
    }}).then(function(r) {{
        document.getElementById('lucy-typing').style.display = 'none';
        if (!r.ok) {{
            _renderBubble('lucy', 'Sorry, I couldn\\'t connect. Please check that your API key is set in Settings.');
            return;
        }}
        var bubble = _renderBubble('lucy', '');
        var full   = '';
        var reader = r.body.getReader();
        var decoder = new TextDecoder();
        function read() {{
            return reader.read().then(function(res) {{
                if (res.done) {{
                    _lucyHistory.push({{role:'assistant', content: full}});
                    _scrollToInput();
                    return;
                }}
                full += decoder.decode(res.value, {{stream: true}});
                bubble.textContent = full;
                return read();
            }});
        }}
        read().catch(function(e) {{
            bubble.textContent = 'Stream error: ' + e.message;
        }});
    }}).catch(function(e) {{
        document.getElementById('lucy-typing').style.display = 'none';
        _renderBubble('lucy', 'Network error: ' + e.message);
    }});
}}

function _renderBubble(role, text) {{
    var hist = document.getElementById('lucy-history');
    var wrap = document.createElement('div');
    var div  = document.createElement('div');
    div.className = (role === 'user') ? 'lucy-bubble-user' : 'lucy-bubble-lucy';
    div.textContent = text;
    wrap.appendChild(div);

    if (role === 'lucy') {{
        var saveRow = document.createElement('div');
        saveRow.style.cssText = 'display:flex;justify-content:flex-start;margin-top:4px;';
        var saveBtn = document.createElement('button');
        saveBtn.textContent = '📖 Save to memory book';
        saveBtn.style.cssText = 'background:none;border:none;color:#c49020;font-size:0.72em;' +
            'cursor:pointer;padding:2px 0;font-family:inherit;opacity:0.7;';
        saveBtn.onmouseover = function() {{ this.style.opacity = '1'; }};
        saveBtn.onmouseout  = function() {{ this.style.opacity = '0.7'; }};
        saveBtn.onclick = function() {{
            var lastUser = '';
            for (var i = _lucyHistory.length - 1; i >= 0; i--) {{
                if (_lucyHistory[i].role === 'user') {{ lastUser = _lucyHistory[i].content; break; }}
            }}
            var toSave = lastUser || text;
            fetch('/memory-book-save', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'text=' + encodeURIComponent(toSave) + '&date=' + encodeURIComponent(_lucyIso)
            }}).then(function(r) {{
                if (r.ok) {{
                    saveBtn.textContent = '✓ Saved to memory book';
                    saveBtn.style.color = '#2d5016';
                    saveBtn.disabled = true;
                }}
            }});
        }};
        saveRow.appendChild(saveBtn);
        wrap.appendChild(saveRow);
    }}

    hist.appendChild(wrap);
    return div;
}}

// Pre-fill a suggested opener — user taps Send when ready
window.addEventListener('load', function() {{
    var openerPrompt = {escape_js(opener_prompt)};
    var input = document.getElementById('lucy-input');
    input.value = openerPrompt;
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
}});

// Scroll input into view whenever keyboard opens or after each message
function _scrollToInput() {{
    var bar = document.getElementById('lucy-input-bar');
    if (bar) bar.scrollIntoView({{block: 'start', behavior: 'smooth'}});
}}
document.getElementById('lucy-input').addEventListener('focus', function() {{
    setTimeout(_scrollToInput, 350);
}});
</script>"""

    from ui_helpers import html_page
    return html_page("Lucy", body)


def escape_js(s: str) -> str:
    """Escape a string for safe embedding in a JS string literal (single-quoted)."""
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"
