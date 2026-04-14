"""
render_plan_tomorrow.py — AI-powered tomorrow planning page.

Flow:
  1. Gather all data for tomorrow (school, chores, calendar, meals, liturgy, tasks, baby)
  2. AI asks 3-5 targeted questions based on what it finds
  3. User answers, hits Generate
  4. AI produces 5 chronological lists: Mom, JP, Joseph, Michael, James
  5. User can refine with follow-up
  6. Push to Grid saves to tomorrow's family grid
"""
import json
from datetime import date, timedelta
from html import escape
from ui_helpers import html_page, top_nav, render_status_message
from daily_schedule_engine import CHILDREN, build_schedule_payload, generate_day_packet


# ── Data gatherer ─────────────────────────────────────────────────────────────

def _gather_tomorrow_data(tomorrow: date) -> dict:
    """Collect everything known about tomorrow into a structured dict."""
    iso     = tomorrow.isoformat()
    weekday = tomorrow.strftime("%A")
    result  = {"iso": iso, "weekday": weekday, "date_label": tomorrow.strftime("%A, %B %-d")}

    # ── Liturgical ────────────────────────────────────────────────────────────
    try:
        from render_liturgical import get_day_info
        info = get_day_info(tomorrow)
        result["liturgy"] = {
            "season":  info.get("season",""),
            "feast":   info.get("feast_name",""),
            "is_fast": info.get("is_fast", False),
            "is_abstinence": info.get("is_abstinence", False),
        }
    except Exception:
        result["liturgy"] = {}

    # ── Calendar events ───────────────────────────────────────────────────────
    try:
        from render_calendar import get_all_events
        events = get_all_events(iso)
        result["events"] = [
            {"title": e.get("title",""), "start": e.get("start",""),
             "end": e.get("end",""), "all_day": e.get("all_day", False)}
            for e in events
        ]
    except Exception:
        result["events"] = []

    # ── Meals ─────────────────────────────────────────────────────────────────
    try:
        from render_meals import load_meal_plan, _week_key
        plan = load_meal_plan(_week_key(tomorrow))
        day_meals = plan.get("days", {}).get(weekday, {})
        result["meals"] = {
            "breakfast": day_meals.get("breakfast",""),
            "lunch":     day_meals.get("lunch",""),
            "dinner":    day_meals.get("dinner",""),
        }
    except Exception:
        result["meals"] = {}

    # ── School subjects per child ─────────────────────────────────────────────
    result["school"] = {}
    for child in CHILDREN:
        try:
            payload  = build_schedule_payload(child, weekday, result["date_label"], iso)
            subjects = [b.get("subject","") for b in payload.get("school_blocks",[]) if b.get("subject")]
            result["school"][child] = subjects
        except Exception:
            result["school"][child] = []

    # ── Chores per child ──────────────────────────────────────────────────────
    try:
        from data_helpers import load_chores_data
        chores_data = load_chores_data()
        result["chores"] = {}
        for child in CHILDREN:
            boy_chores  = chores_data.get("boys", {}).get(child, {})
            daily       = boy_chores.get("daily", [])
            weekly_day  = boy_chores.get("weekly", {}).get(weekday, [])
            result["chores"][child] = daily + weekly_day
    except Exception:
        result["chores"] = {}

    # ── Mom's tasks ───────────────────────────────────────────────────────────
    try:
        from data_helpers import active_manual_tasks
        tasks = [t for t in active_manual_tasks()
                 if t.get("assigned_to","").lower() in ("mom","") or not t.get("assigned_to")]
        tasks.sort(key=lambda t: (t.get("due_date","") or "9999",
                                   {"HIGH":0,"MEDIUM":1,"LOW":2}.get(t.get("priority","MEDIUM"),1)))
        result["mom_tasks"] = [t.get("text","") for t in tasks[:8]]
    except Exception:
        result["mom_tasks"] = []

    # ── Prayer intentions (top 3 active) ─────────────────────────────────────
    try:
        from render_prayer import load_intentions
        intentions = [i for i in load_intentions() if not i.get("answered")]
        result["intentions"] = [i.get("title","") for i in intentions[:3]]
    except Exception:
        result["intentions"] = []

    # ── Family constraints (baby + supervision + exercise) ───────────────────
    try:
        from render_settings import load_app_settings
        settings = load_app_settings()
        fc = settings.get("family_constraints", {})
        result["constraints"] = {
            "james_schedule":    fc.get("james_schedule",""),
            "supervision_rules": fc.get("supervision_rules",""),
            "independence":      fc.get("independence_notes",""),
            "school_durations":  fc.get("school_durations",""),
            "mom_needed":        fc.get("mom_supervision_subjects",""),
            "exercise":          fc.get("family_exercise","walk, park, or farm time"),
        }
        result["schedule_start"] = settings.get("schedule_start_hour", 6)
        result["schedule_end"]   = settings.get("schedule_end_hour", 21)
    except Exception:
        result["constraints"] = {}
        result["schedule_start"] = 6
        result["schedule_end"]   = 21

    # ── Family Rule of Life (Mom's day template) ──────────────────────────────
    try:
        from data_helpers import get_frol_day_slots
        day_slots  = get_frol_day_slots(weekday, "Mom")
        rol_items  = []
        seen_text  = set()
        for t, text in day_slots.items():
            text = text.strip()
            if text and text not in seen_text:
                seen_text.add(text)
                rol_items.append({"time": t, "text": text})
        result["rol_schedule"] = rol_items
    except Exception:
        result["rol_schedule"] = []

    return result


# ── AI helpers ────────────────────────────────────────────────────────────────

def _api_key() -> str:
    try:
        from render_settings import load_app_settings
        s = load_app_settings()
        return s.get("anthropic_api_key","") or s.get("family_constraints",{}).get("anthropic_api_key","")
    except Exception:
        return ""


def _call_claude(prompt: str, max_tokens: int = 1200) -> str:
    import urllib.request as _ur
    key = _api_key()
    if not key:
        raise ValueError("No API key. Add it in Settings → AI & Planning.")
    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = _ur.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={"Content-Type":"application/json","x-api-key":key,
                 "anthropic-version":"2023-06-01"}
    )
    with _ur.urlopen(req, timeout=45) as resp:
        result = json.loads(resp.read())
    return result["content"][0]["text"].strip()


def _data_summary_text(data: dict) -> str:
    """Convert gathered data to a readable text summary for the AI."""
    lines = [f"Planning for: {data['date_label']}"]

    lit = data.get("liturgy", {})
    if lit.get("feast"):
        lines.append(f"Liturgy: {lit['feast']} ({lit.get('season','')})")
    else:
        lines.append(f"Liturgy: {lit.get('season','Ordinary Time')}")
    if lit.get("is_abstinence"):
        lines.append("  → Day of abstinence (no meat)")
    if lit.get("is_fast"):
        lines.append("  → Day of fasting")

    events = data.get("events", [])
    if events:
        lines.append("Calendar events:")
        for e in events:
            t = e.get("start","")
            time_str = ""
            if "T" in t:
                try:
                    from datetime import datetime as _dt
                    time_str = _dt.fromisoformat(t).strftime("%-I:%M %p") + " "
                except Exception:
                    pass
            lines.append(f"  • {time_str}{e['title']}")
    else:
        lines.append("Calendar events: None")

    meals = data.get("meals", {})
    if any(meals.values()):
        lines.append("Meals planned:")
        for m, v in meals.items():
            if v: lines.append(f"  {m.capitalize()}: {v}")
    else:
        lines.append("Meals: Not planned yet")

    lines.append("School subjects:")
    for child, subjects in data.get("school", {}).items():
        s = ", ".join(subjects) if subjects else "not assigned"
        lines.append(f"  {child}: {s}")

    lines.append("Chores:")
    for child, chores in data.get("chores", {}).items():
        if chores:
            lines.append(f"  {child}: {', '.join(str(c) for c in chores[:5])}")

    if data.get("mom_tasks"):
        lines.append("Mom's tasks: " + "; ".join(data["mom_tasks"][:5]))

    if data.get("intentions"):
        lines.append("Prayer intentions: " + ", ".join(data["intentions"]))

    fc = data.get("constraints", {})
    if fc.get("james_schedule"):
        lines.append(f"Baby (James): {fc['james_schedule'][:150]}")
    if fc.get("supervision_rules"):
        lines.append(f"Supervision: {fc['supervision_rules'][:120]}")
    if fc.get("independence"):
        lines.append(f"Independent work: {fc['independence'][:100]}")
    if fc.get("school_durations"):
        lines.append(f"School durations: {fc['school_durations'][:100]}")
    if fc.get("mom_needed"):
        lines.append(f"Mom-needed subjects: {fc['mom_needed'][:100]}")
    if fc.get("exercise"):
        lines.append(f"Family exercise: {fc['exercise']}")

    rol = data.get("rol_schedule", [])
    if rol:
        lines.append("Family Rule of Life schedule for this day:")
        for item in rol:
            lines.append(f"  {item['time']}: {item['text']}")

    lines.append(f"Day runs: {data.get('schedule_start',6)}am – {data.get('schedule_end',21) - 12}pm")

    return "\n".join(lines)


def _last_social_date() -> str:
    """Return ISO date of last recorded social/friend event, or empty string."""
    try:
        from render_settings import load_app_settings
        s = load_app_settings()
        return s.get("last_social_date", "")
    except Exception:
        return ""


def _save_social_date(iso: str):
    """Save a social date to settings when user confirms one."""
    try:
        from render_settings import load_app_settings, save_app_settings
        s = load_app_settings()
        s["last_social_date"] = iso
        save_app_settings(s)
    except Exception:
        pass


def _days_since_social() -> int:
    """Return days since last social event, or 999 if unknown."""
    last = _last_social_date()
    if not last:
        return 999
    try:
        from datetime import date as _d
        return (_d.today() - _d.fromisoformat(last)).days
    except Exception:
        return 999


def ai_generate_questions(data: dict) -> str:
    """Generate smart, contextual questions about tomorrow."""
    summary = _data_summary_text(data)
    days_social = _days_since_social()

    social_note = ""
    if days_social >= 10:
        social_note = (
            f"\nNote: It has been {days_social} days since the last recorded time with friends "
            f"or extended family. Consider whether to suggest getting together with someone tomorrow."
        )
    elif days_social >= 7:
        social_note = "\nNote: It's been about a week since the last social time. A light nudge about friends may be appropriate."

    prompt = (
        "You are a warm, practical Catholic homeschool family assistant. "
        "You know this family well and think ahead like a trusted household manager.\n\n"
        "Here is everything I know about tomorrow:\n"
        f"{summary}"
        f"{social_note}\n\n"
        "Your job is to ask the 4-6 most important questions that will help you "
        "build the most realistic, useful schedule for tomorrow. Think like a thoughtful "
        "friend who knows the household:\n\n"
        "ALWAYS ask:\n"
        "1. Is anyone sick or not feeling well? (This changes everything — meals, school, plans)\n"
        "2. What time does the day need to start and what's the hardest deadline?\n"
        f"{'3. It has been ' + str(days_social) + ' days since a friend or family visit — would tomorrow work for getting together with someone? If so, who and roughly when?' if days_social >= 7 else ''}\n"
        "Then ask 2-3 more based on what you see in the data:\n"
        "- If meals aren't planned, ask about dinner\n"
        "- If there's a calendar event, ask how long it will take and if prep is needed\n"
        "- If it's a feast day, ask if they want any special observance\n"
        "- If capacity isn't set, ask\n"
        "- If school subjects seem heavy for the day, ask what to prioritize\n"
        "- If chores overlap with appointments, flag it\n\n"
        "Format: numbered list, one question per line, plain language, warm tone. "
        "No preamble. Just the questions."
    )
    return _call_claude(prompt, 500)


def ai_generate_plan(data: dict, capacity: str, answers: str, refine: str = "") -> str:
    """Generate the full 5-person chronological plan with deep sequencing intelligence."""
    summary = _data_summary_text(data)
    refine_block = f"\n\nRevision request from Mom: {refine}" if refine else ""

    # Extract illness signals from answers
    illness_note = ""
    answers_lower = answers.lower() if answers else ""
    sick_words = ["sick","ill","fever","cold","not feeling","unwell","tired","exhausted","migraine","headache"]
    who_sick = []
    for word in sick_words:
        if word in answers_lower:
            illness_note = "\n⚠ Someone may be sick — adjust plans accordingly: simplify school, offer easy comfort meals, reduce Mom's load, keep the sick person's schedule very light."
            break
    # Check for named people
    for name in ["jp","joseph","michael","james","mom","i am","i'm"]:
        if name in answers_lower and any(w in answers_lower for w in sick_words):
            who_sick.append(name)
    if who_sick:
        illness_note += f" Sick person(s) mentioned: {', '.join(who_sick)}."

    # Social note
    days_social = _days_since_social()
    social_instruction = ""
    if days_social >= 7 and any(w in answers_lower for w in ["friend","visit","together","playdate","have over","come over","neighbor"]):
        social_instruction = "\n- A friend visit is planned — block a window of 2-3 hours and lighten the school/chore load around it. Suggest a simple shareable meal if it spans mealtime."
        _save_social_date(data.get("iso", ""))

    prompt = (
        "You are a warm, deeply practical Catholic homeschool family assistant. "
        "You think like a trusted household manager who has memorized every constraint, "
        "every child's learning style, and every family rhythm.\n\n"
        "Tomorrow's complete picture:\n"
        f"{summary}\n\n"
        f"Mom's capacity tomorrow: {capacity or 'not set — assume Medium'}\n\n"
        f"Answers to your questions:\n{answers or 'No answers provided.'}"
        f"{illness_note}"
        f"{social_instruction}"
        f"{refine_block}\n\n"
        "NOW BUILD THE PLAN. Think through this carefully before writing:\n\n"
        "SEQUENCING RULES — apply these in order:\n"
        "1. FIXED ANCHORS FIRST: Place all calendar events, appointments, and Mass times first. "
        "Everything else must work around them.\n"
        "2. JAMES's WINDOWS: Map out baby nap/feed windows from the constraints. Mom is most "
        "available during James's nap. Schedule Mom-intensive school subjects (Latin, logic, "
        "anything needing her full attention) during those windows.\n"
        "3. INDEPENDENT FIRST: Give older boys their independent subjects before Mom is needed. "
        "This front-loads their day and frees Mom for James.\n"
        "4. CAPACITY CALIBRATION:\n"
        "   - High: Full school for all boys, all chores, Mom's tasks included\n"
        "   - Medium: Core subjects only (math + one language subject per boy), essential chores, "
        "defer Mom's tasks unless urgent\n"
        "   - Low: Math only or nothing, minimal chores, rest and simple meals, Mom protects her "
        "energy — this is not a failure, this is wisdom\n"
        "5. MEALS SHAPE THE DAY: Place meal prep time 30-45 min before each meal. "
        "If no dinner is planned and capacity is Low, suggest a simple meal explicitly. "
        "If it's a day of abstinence, confirm no meat.\n"
        "6. PRAYER RHYTHM: Include Morning Offering at day start, Angelus at noon, "
        "Rosary or Divine Mercy Chaplet in the late afternoon, and evening prayer before bed. "
        "On feast days, name the feast and include a brief observance suggestion.\n"
        "7. SOCIAL: If a friend visit is happening, protect that time fully — "
        "don't schedule school during it. If no visit but it's been 7+ days, "
        "add a gentle note at the end: 'Consider texting [a friend] — it's been a while.'\n"
        "8. REALISTIC TRANSITIONS: Add 10-15 min buffers between major blocks. "
        "Children need transition time. Don't schedule back-to-back sessions without breaks.\n\n"
        "ILLNESS PROTOCOL (if someone is sick):\n"
        "- Sick child: No school. Quiet rest. Simple food. Minimal demands.\n"
        "- Sick Mom: Bare minimum only. Boys do independent work. Simple cold meals. "
        "Older boys step up with James supervision.\n\n"
        "OUTPUT FORMAT — use these EXACT headers, nothing else:\n"
        "## MOM\n## JP\n## JOSEPH\n## MICHAEL\n## JAMES\n\n"
        "Under each header:\n"
        "  7:00 AM — Task description\n"
        "  7:30 AM — Next task\n\n"
        "Rules for the output:\n"
        "- Every entry must have a time and a dash and a task\n"
        "- Be specific: 'Math — Saxon 7/6 Lesson 84' not just 'Math'\n"
        "- Show where Mom's attention is split: note '(James awake)' or '(James napping)'\n"
        "- James's list should mirror his actual day: wake, feed, play, nap, repeat\n"
        "- End each person's list at a natural stopping point, not at midnight\n"
        "- The whole plan should feel achievable, not heroic"
    )
    return _call_claude(prompt, 2000)


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _render_data_card(label: str, items: list, color: str = "var(--ink-faint)") -> str:
    if not items:
        return ""
    rows = "".join(
        f'<div style="font-size:0.82em;padding:3px 0;border-bottom:1px solid var(--border-light);">'
        f'{escape(str(i))}</div>'
        for i in items
    )
    return (
        f'<div style="margin-bottom:12px;">'
        f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;'
        f'text-transform:uppercase;color:{color};margin-bottom:6px;">{escape(label)}</div>'
        f'{rows}</div>'
    )


def _format_plan_html(raw: str) -> str:
    """Convert the AI plan text to styled HTML with person sections."""
    colors = {"MOM":"var(--brown)","JP":"#c0392b","JOSEPH":"#27ae60",
              "MICHAEL":"#e67e22","JAMES":"#2980b9"}
    html  = ""
    current_person = None
    buffer = []

    def _flush(person, lines):
        if not person or not lines:
            return ""
        color = colors.get(person, "var(--ink)")
        rows  = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Split "7:00 AM — Task"
            if " \u2014 " in line or " - " in line:
                sep  = " \u2014 " if " \u2014 " in line else " - "
                time_part, task_part = line.split(sep, 1)
                rows += (
                    f'<div style="display:flex;gap:10px;padding:5px 0;'
                    f'border-bottom:1px solid var(--border-light);">'
                    f'<div style="font-size:0.75em;color:var(--ink-faint);white-space:nowrap;'
                    f'min-width:70px;padding-top:2px;">{escape(time_part.strip())}</div>'
                    f'<div style="font-size:0.85em;color:var(--ink);">{escape(task_part.strip())}</div>'
                    f'</div>'
                )
            else:
                rows += (
                    f'<div style="font-size:0.85em;color:var(--ink);padding:4px 0;">'
                    f'{escape(line)}</div>'
                )
        return (
            f'<div style="margin-bottom:16px;border-left:4px solid {color};'
            f'padding-left:12px;">'
            f'<div style="font-weight:800;font-size:0.82em;letter-spacing:.08em;'
            f'text-transform:uppercase;color:{color};margin-bottom:8px;">{person}</div>'
            f'{rows}</div>'
        )

    for line in raw.splitlines():
        if line.startswith("## "):
            html += _flush(current_person, buffer)
            current_person = line[3:].strip().upper()
            buffer = []
        else:
            buffer.append(line)
    html += _flush(current_person, buffer)
    return html


# ── Main page renderer ────────────────────────────────────────────────────────

def render_plan_tomorrow_page(status: str = "", for_date: date = None) -> str:
    if for_date is None:
        for_date = date.today() + timedelta(days=1)
    is_today    = (for_date == date.today())
    page_title  = "Plan Today" if is_today else "Plan Tomorrow"
    tomorrow    = for_date
    has_api_key = bool(_api_key())
    data        = _gather_tomorrow_data(tomorrow)
    data_json   = json.dumps(data)

    lit   = data.get("liturgy", {})
    feast = lit.get("feast","") or lit.get("season","")

    # ── Data summary cards ────────────────────────────────────────────────────
    events_list = [
        (e.get("start","").split("T")[-1][:5] + " " if "T" in e.get("start","") else "All day — ")
        + e.get("title","")
        for e in data.get("events",[])
    ]

    meals   = data.get("meals",{})
    meal_list = [f"{k.capitalize()}: {v}" for k,v in meals.items() if v]

    school_items = []
    for child in CHILDREN:
        subjs = data["school"].get(child,[])
        if subjs:
            school_items.append(f"{child}: {', '.join(subjs)}")
        else:
            school_items.append(f"{child}: —")

    chore_items = []
    for child in CHILDREN:
        chores = data["chores"].get(child,[])
        if chores:
            chore_items.append(f"{child}: {', '.join(str(c) for c in chores[:4])}")

    rol_items_disp = [f"{r['time']} — {r['text']}" for r in data.get("rol_schedule", [])]

    summary_cards = (
        _render_data_card("Family Rule of Life", rol_items_disp or ["No schedule set for this day"], "#c0392b") +
        _render_data_card("Calendar events", events_list or ["None"], "#4a6a9e") +
        _render_data_card("Meals", meal_list or ["Not planned"], "#27ae60") +
        _render_data_card("School", school_items, "#8b5a3c") +
        _render_data_card("Chores", chore_items, "#e67e22") +
        _render_data_card("Mom's tasks", data.get("mom_tasks",[])[:5], "var(--brown)") +
        _render_data_card("Prayer intentions", data.get("intentions",[]), "#7c3aed")
    )

    # ── James schedule snippet ────────────────────────────────────────────────
    james_text = data.get("constraints",{}).get("james_schedule","")
    james_card = (
        f'<div style="margin-bottom:12px;padding:8px 10px;background:#eff6ff;'
        f'border-radius:8px;border-left:3px solid #2980b9;">'
        f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;'
        f'text-transform:uppercase;color:#2980b9;margin-bottom:4px;">Baby — James</div>'
        f'<div style="font-size:0.82em;color:var(--ink);">{escape(james_text)}</div>'
        f'</div>'
    ) if james_text else ""

    no_key_banner = (
        f'<div style="padding:10px 14px;background:#fef3c7;border-radius:10px;'
        f'margin-bottom:16px;font-size:0.85em;color:#92400e;">'
        f'<strong>No API key saved.</strong> Add your Anthropic API key in '
        f'<a href="/settings" style="color:#92400e;">Settings → AI & Planning</a> to use this feature.'
        f'</div>'
    ) if not has_api_key else ""

    cap_buttons_html = "".join(
        '<button onclick="setCapacity(this,' + "'" + cap + "'" + ')" id="cap-btn-' + cap + '" '
        'style="padding:6px 14px;font-size:0.78em;font-weight:700;font-family:inherit;'
        'background:var(--parchment);border:1.5px solid var(--border);'
        'border-radius:8px;cursor:pointer;">' + emoji + ' ' + cap + '</button>'
        for cap, emoji in [("High","🟢"),("Medium","🟡"),("Low","🔴")]
    )

    _nav_btn_style = "padding:7px 14px;background:var(--parchment);border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);"
    _today_btn    = "" if is_today else f'<a href="/plan-today" style="{_nav_btn_style}">Plan Today</a>'
    _tomorrow_btn = "" if not is_today else f'<a href="/plan-tomorrow" style="{_nav_btn_style}">Plan Tomorrow</a>'

    body = top_nav() + render_status_message(status) + f"""
<div style="display:flex;align-items:flex-start;justify-content:space-between;
            flex-wrap:wrap;gap:8px;padding-top:4px;margin-bottom:16px;">
  <div>
    <div style="font-family:'Cormorant Garamond',Georgia,serif;
                font-size:2rem;font-weight:600;color:var(--ink);">{page_title}</div>
    <div style="font-size:0.85em;color:var(--ink-muted);margin-top:2px;">
      {escape(data["date_label"])}
      {(" &middot; " + escape(feast)) if feast else ""}
    </div>
  </div>
  <div style="display:flex;gap:8px;">
    {_today_btn}
    {_tomorrow_btn}
    <a href="/" style="padding:7px 14px;background:var(--parchment);
       border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;
       text-decoration:none;color:var(--ink);">&larr; Dashboard</a>
  </div>
</div>

{no_key_banner}

<!-- Step 1: Data summary -->
<div id="step-data" style="margin-bottom:20px;">
  <div style="font-size:0.68em;font-weight:800;letter-spacing:.12em;
              text-transform:uppercase;color:var(--ink-faint);margin-bottom:12px;">
    Step 1 &middot; Here's what I found for tomorrow
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
    <div>{summary_cards}</div>
    <div>{james_card}</div>
  </div>
  <div style="padding:10px 14px;background:var(--gold-light);border-radius:10px;
              margin-bottom:14px;border:1px solid var(--gold-mid);">
    <label style="font-size:0.82em;font-weight:700;color:var(--ink);display:block;margin-bottom:8px;">
      What is your capacity for tomorrow?
    </label>
    <div style="display:flex;gap:8px;">
      {cap_buttons_html}
    </div>
  </div>
  {'<button onclick="getQuestions()" id="btn-questions" ' +
   'style="padding:9px 22px;background:var(--ink);color:var(--gold-light);border:none;' +
   'border-radius:10px;font-size:0.88em;font-weight:700;font-family:inherit;cursor:pointer;">' +
   '✨ Ask me some questions &rarr;</button>'
   if has_api_key else ''}
  <div id="questions-loading" style="display:none;margin-top:12px;font-size:0.85em;
       color:var(--ink-faint);">✨ Looking at your day and thinking of questions…</div>
</div>

<!-- Step 2: Questions -->
<div id="step-questions" style="display:none;margin-bottom:20px;">
  <div style="font-size:0.68em;font-weight:800;letter-spacing:.12em;
              text-transform:uppercase;color:var(--ink-faint);margin-bottom:12px;">
    Step 2 &middot; A few questions
  </div>
  <div id="questions-text" style="margin-bottom:14px;padding:14px;
       background:white;border-radius:12px;border:1px solid var(--border-light);
       font-size:0.88em;line-height:1.8;color:var(--ink);white-space:pre-line;"></div>
  <label style="font-size:0.82em;font-weight:700;color:var(--ink);display:block;margin-bottom:6px;">
    Your answers:
  </label>
  <textarea id="answers-input" rows="5"
            placeholder="Answer each question briefly — one answer per line is fine…"
            style="width:100%;font-size:0.85em;padding:10px;border:1.5px solid var(--border);
                   border-radius:10px;font-family:inherit;resize:vertical;margin-bottom:12px;">
  </textarea>
  <button onclick="generatePlan()" id="btn-generate"
          style="padding:9px 22px;background:var(--ink);color:var(--gold-light);border:none;
                 border-radius:10px;font-size:0.88em;font-weight:700;font-family:inherit;cursor:pointer;">
    ✨ Generate tomorrow's plan &rarr;
  </button>
  <div id="plan-loading" style="display:none;margin-top:12px;font-size:0.85em;
       color:var(--ink-faint);">✨ Building your plan — this takes about 15 seconds…</div>
</div>

<!-- Step 3: Generated plan -->
<div id="step-plan" style="display:none;margin-bottom:20px;">
  <div style="display:flex;align-items:center;justify-content:space-between;
              flex-wrap:wrap;gap:8px;margin-bottom:12px;">
    <div style="font-size:0.68em;font-weight:800;letter-spacing:.12em;
                text-transform:uppercase;color:var(--ink-faint);">
      Step 3 &middot; Tomorrow's plan
    </div>
    <div style="display:flex;gap:8px;">
      <button onclick="showRefine()"
              style="padding:6px 14px;background:var(--parchment);border:1.5px solid var(--border);
                     border-radius:8px;font-size:0.78em;font-weight:600;font-family:inherit;cursor:pointer;">
        ✏ Refine
      </button>
      <button onclick="pushToGrid()" id="btn-push"
              style="padding:6px 14px;background:#27ae60;color:white;border:none;
                     border-radius:8px;font-size:0.78em;font-weight:700;font-family:inherit;cursor:pointer;">
        → Push to Grid
      </button>
    </div>
  </div>
  <div id="plan-output" style="padding:16px;background:white;border-radius:12px;
       border:1px solid var(--border-light);margin-bottom:14px;"></div>
  <div id="push-status" style="font-size:0.82em;color:#27ae60;min-height:18px;"></div>
</div>

<!-- Refine panel -->
<div id="step-refine" style="display:none;margin-bottom:20px;">
  <div style="font-size:0.68em;font-weight:800;letter-spacing:.12em;
              text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;">
    Refine the plan
  </div>
  <textarea id="refine-input" rows="3"
            placeholder="e.g. Move school earlier, add rosary at 8am, JP has a dentist at 2pm…"
            style="width:100%;font-size:0.85em;padding:10px;border:1.5px solid var(--border);
                   border-radius:10px;font-family:inherit;resize:vertical;margin-bottom:10px;">
  </textarea>
  <div style="display:flex;gap:8px;">
    <button onclick="applyRefinement()" id="btn-refine"
            style="padding:8px 18px;background:var(--ink);color:var(--gold-light);border:none;
                   border-radius:8px;font-size:0.85em;font-weight:700;font-family:inherit;cursor:pointer;">
      ✨ Update plan
    </button>
    <button onclick="document.getElementById('step-refine').style.display='none'"
            style="padding:8px 14px;background:transparent;border:1.5px solid var(--border);
                   border-radius:8px;font-size:0.85em;font-family:inherit;cursor:pointer;">
      Cancel
    </button>
  </div>
  <div id="refine-loading" style="display:none;margin-top:10px;font-size:0.85em;
       color:var(--ink-faint);">✨ Updating your plan…</div>
</div>

<script>
var _tomorrow     = '{escape(data["iso"])}';
var _weekday      = '{escape(data["weekday"])}';
var _selectedCap  = '';
var _planRaw      = '';
var _questionsRaw = '';

function setCapacity(btn, cap) {{
  _selectedCap = cap;
  var cols = {{High:'#27ae60', Medium:'#e67e22', Low:'#e74c3c'}};
  ['High','Medium','Low'].forEach(function(c) {{
    var b = document.getElementById('cap-btn-' + c);
    if (!b) return;
    b.style.background   = (c === cap) ? cols[c] : 'var(--parchment)';
    b.style.color        = (c === cap) ? 'white'  : 'var(--ink)';
    b.style.borderColor  = (c === cap) ? cols[c]  : 'var(--border)';
  }});
}}

function getQuestions() {{
  var btn = document.getElementById('btn-questions');
  if (btn) {{ btn.disabled = true; btn.textContent = '✨ Thinking…'; }}
  document.getElementById('questions-loading').style.display = 'block';
  fetch('/plan-tomorrow-questions', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'iso=' + encodeURIComponent(_tomorrow)
        + '&capacity=' + encodeURIComponent(_selectedCap)
        + '&weekday='  + encodeURIComponent(_weekday)
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    document.getElementById('questions-loading').style.display = 'none';
    if (btn) {{ btn.disabled = false; btn.textContent = '✨ Ask me some questions →'; }}
    if (d.questions) {{
      _questionsRaw = d.questions;
      document.getElementById('questions-text').textContent = d.questions;
      document.getElementById('step-questions').style.display = 'block';
      document.getElementById('step-questions').scrollIntoView({{behavior:'smooth'}});
    }} else {{
      alert(d.error || 'Could not get questions. Check API key.');
    }}
  }}).catch(function() {{
    document.getElementById('questions-loading').style.display = 'none';
    if (btn) {{ btn.disabled = false; }}
    alert('Network error. Check connection.');
  }});
}}

function generatePlan() {{
  var btn = document.getElementById('btn-generate');
  if (btn) {{ btn.disabled = true; btn.textContent = '✨ Generating…'; }}
  document.getElementById('plan-loading').style.display = 'block';
  var answers = document.getElementById('answers-input').value;
  fetch('/plan-tomorrow-generate', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'iso='      + encodeURIComponent(_tomorrow)
        + '&capacity='+ encodeURIComponent(_selectedCap)
        + '&weekday=' + encodeURIComponent(_weekday)
        + '&answers=' + encodeURIComponent(answers)
        + '&questions='+ encodeURIComponent(_questionsRaw)
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    document.getElementById('plan-loading').style.display = 'none';
    if (btn) {{ btn.disabled = false; btn.textContent = '✨ Generate tomorrow\'s plan →'; }}
    if (d.plan_html) {{
      _planRaw = d.plan_raw || '';
      document.getElementById('plan-output').innerHTML = d.plan_html;
      document.getElementById('step-plan').style.display = 'block';
      document.getElementById('step-plan').scrollIntoView({{behavior:'smooth'}});
    }} else {{
      alert(d.error || 'Could not generate plan. Check API key.');
    }}
  }}).catch(function() {{
    document.getElementById('plan-loading').style.display = 'none';
    if (btn) {{ btn.disabled = false; }}
    alert('Network error. Check connection.');
  }});
}}

function showRefine() {{
  document.getElementById('step-refine').style.display = 'block';
  document.getElementById('step-refine').scrollIntoView({{behavior:'smooth'}});
}}

function applyRefinement() {{
  var refineText = document.getElementById('refine-input').value.trim();
  if (!refineText) return;
  var btn = document.getElementById('btn-refine');
  if (btn) {{ btn.disabled = true; btn.textContent = '✨ Updating…'; }}
  document.getElementById('refine-loading').style.display = 'block';
  var answers = document.getElementById('answers-input').value;
  fetch('/plan-tomorrow-generate', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'iso='      + encodeURIComponent(_tomorrow)
        + '&capacity='+ encodeURIComponent(_selectedCap)
        + '&weekday=' + encodeURIComponent(_weekday)
        + '&answers=' + encodeURIComponent(answers)
        + '&questions='+ encodeURIComponent(_questionsRaw)
        + '&refine='  + encodeURIComponent(refineText)
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    document.getElementById('refine-loading').style.display = 'none';
    if (btn) {{ btn.disabled = false; btn.textContent = '✨ Update plan'; }}
    if (d.plan_html) {{
      _planRaw = d.plan_raw || '';
      document.getElementById('plan-output').innerHTML = d.plan_html;
      document.getElementById('step-refine').style.display = 'none';
      document.getElementById('refine-input').value = '';
      document.getElementById('step-plan').scrollIntoView({{behavior:'smooth'}});
    }} else {{
      alert(d.error || 'Could not refine plan.');
    }}
  }}).catch(function() {{
    document.getElementById('refine-loading').style.display = 'none';
    if (btn) {{ btn.disabled = false; }}
  }});
}}

function pushToGrid() {{
  if (!_planRaw) {{ alert('No plan to push yet.'); return; }}
  var btn = document.getElementById('btn-push');
  if (btn) {{ btn.disabled = true; btn.textContent = 'Pushing…'; }}
  fetch('/plan-tomorrow-push', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'iso='     + encodeURIComponent(_tomorrow)
        + '&weekday='+ encodeURIComponent(_weekday)
        + '&plan='   + encodeURIComponent(_planRaw)
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    var el = document.getElementById('push-status');
    if (d.ok) {{
      if (el) el.textContent = '\u2713 Pushed to grid! View it on /grid or each boy\'s schedule page.';
      if (btn) {{ btn.textContent = '\u2713 Pushed!'; btn.style.background = '#166534'; }}
    }} else {{
      if (el) el.textContent = 'Error: ' + (d.error || 'unknown');
      if (btn) {{ btn.disabled = false; btn.textContent = '\u2192 Push to Grid'; }}
    }}
  }}).catch(function() {{
    if (btn) {{ btn.disabled = false; btn.textContent = '\u2192 Push to Grid'; }}
  }});
}}
</script>
"""
    return html_page(f"{page_title} · {data['date_label']}", body)