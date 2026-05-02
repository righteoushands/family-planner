"""
render_ai_daily.py — AI-powered daily assistance features for Sancta Familia

Features:
  1. /ai-daily-schedule     — time-blocked day plan based on capacity + constraints
  2. /ai-meal-plan          — weekly meal suggestions respecting rules
  3. /ai-school-plan        — subject suggestions based on completion + Mom time
  4. /ai-evening-examen     — personalized reflection prompt from the day
  5. /ai-weekly-review      — Sunday review + next week prep
  6. /ai-chore-adjust       — chore reshuffling for Low capacity days
  7. /ai-intention-prayer   — short prayer for each active intention

All endpoints: POST, return JSON {"html": "...", "text": "..."}
"""
import json
from datetime import date, timedelta
from html import escape


def _api_key() -> str:
    from render_settings import load_app_settings
    s = load_app_settings()
    return s.get("anthropic_api_key","") or s.get("family_constraints",{}).get("anthropic_api_key","")


def _call_claude(prompt: str, max_tokens: int = 600) -> str:
    import urllib.request as _ur
    key = _api_key()
    if not key:
        raise ValueError("No API key found. Add your Anthropic API key in Settings → AI & Planning.")
    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = _ur.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={"Content-Type":"application/json","x-api-key":key,
                 "anthropic-version":"2023-06-01"}
    )
    with _ur.urlopen(req, timeout=25) as resp:
        result = json.loads(resp.read())
    return result["content"][0]["text"].strip()


def _constraints() -> str:
    from render_settings import load_app_settings
    fc = load_app_settings().get("family_constraints", {})
    parts = []
    if fc.get("james_schedule"):        parts.append(f"Baby (James): {fc['james_schedule'][:150]}")
    if fc.get("supervision_rules"):     parts.append(f"Supervision: {fc['supervision_rules'][:150]}")
    if fc.get("independence_notes"):    parts.append(f"Independent work: {fc['independence_notes'][:150]}")
    if fc.get("school_durations"):      parts.append(f"School durations: {fc['school_durations'][:120]}")
    if fc.get("mom_supervision_subjects"): parts.append(f"Mom-required subjects: {fc['mom_supervision_subjects'][:120]}")
    if fc.get("meal_prep"):             parts.append(f"Meal prep: {fc['meal_prep'][:100]}")
    if fc.get("other_notes"):           parts.append(f"Other: {fc['other_notes'][:150]}")
    return "\n".join(parts) if parts else "No specific constraints saved."


def _season() -> str:
    try:
        from render_liturgical import get_liturgical_season
        return get_liturgical_season(date.today())
    except Exception:
        return "Ordinary Time"


def _format_html(text: str) -> str:
    """Convert plain text AI response to clean HTML."""
    lines = text.splitlines()
    html = ""
    for line in lines:
        s = line.strip()
        if not s:
            html += '<div style="height:6px;"></div>'
        elif s.startswith("##"):
            html += f'<div style="font-size:0.78em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--brown);margin:12px 0 4px;">{escape(s.lstrip("#").strip())}</div>'
        elif s.startswith("**") and s.endswith("**"):
            html += f'<div style="font-weight:700;font-size:0.9em;color:var(--ink);margin:4px 0;">{escape(s.strip("*"))}</div>'
        elif s.startswith("- ") or s.startswith("• "):
            html += f'<div style="font-size:0.88em;line-height:1.65;color:var(--ink);padding-left:12px;">• {escape(s[2:])}</div>'
        elif s[0].isdigit() and len(s) > 2 and s[1] in ".):":
            html += f'<div style="font-size:0.88em;line-height:1.65;color:var(--ink);padding-left:4px;font-weight:600;">{escape(s)}</div>'
        else:
            html += f'<div style="font-size:0.88em;line-height:1.7;color:var(--ink);">{escape(s)}</div>'
    return html


# ── 1. Daily Schedule Builder ─────────────────────────────────────────────────

def ai_daily_schedule(iso: str, capacity: str, weekday: str) -> dict:
    """Generate a time-blocked day plan."""
    try:
        from daily_schedule_engine import build_schedule_payload, CHILDREN
        from render_schedule_support import get_eastern_now
        from data_helpers import active_manual_tasks

        now_hour = get_eastern_now().hour

        # Gather school info per child
        school_lines = []
        for child in CHILDREN:
            try:
                payload = build_schedule_payload(child, weekday, iso, iso)
                blocks = payload.get("school_blocks", [])
                subjects = [b.get("subject","") for b in blocks if b.get("subject")]
                if subjects:
                    school_lines.append(f"{child}: {', '.join(subjects[:6])}")
            except Exception:
                pass

        tasks = [t.get("text","") for t in active_manual_tasks()[:5]]

        # Meal rules
        from render_settings import load_app_settings
        meal_rules = load_app_settings().get("meal_rules", [])
        meal_str = "; ".join(r.get("rule","") for r in meal_rules[:3]) if meal_rules else ""

        prompt = (
            f"You are a warm Catholic homeschool family assistant.\n"
            f"Today: {weekday}, {iso}. Liturgical season: {_season()}.\n"
            f"Mom's capacity: {capacity or 'not set'}.\n"
            f"Current time: {now_hour}:00.\n\n"
            f"Family constraints:\n{_constraints()}\n\n"
            f"School subjects today:\n" + ("\n".join(school_lines) or "Not planned yet") + "\n\n"
            f"Active tasks: {', '.join(tasks) or 'None'}\n"
            f"Meal rules: {meal_str or 'None saved'}\n\n"
            f"Create a realistic time-blocked schedule for the rest of today starting at {now_hour}:00. "
            f"Format as time blocks: '9:00 AM — Subject'. "
            f"Account for capacity ({capacity}), baby care, meal prep, and supervision rules. "
            f"Keep it warm and achievable. 8-12 blocks max."
        )
        text = _call_claude(prompt, 500)
        return {"html": _format_html(text), "text": text}
    except Exception as e:
        return {"html": f"<p style='color:#ef4444;'>Error: {e}</p>", "text": ""}


# ── 2. Meal Plan Generator ────────────────────────────────────────────────────

def ai_meal_plan(week_key: str) -> dict:
    """Suggest a full week of meals."""
    try:
        from render_settings import load_app_settings
        settings   = load_app_settings()
        meal_rules = settings.get("meal_rules", [])
        rules_str  = "\n".join(f"- {r.get('rule','')}" for r in meal_rules) if meal_rules else "No specific rules saved."

        try:
            from render_meals import load_meal_plan, slot_display_text
            existing = load_meal_plan(week_key)
            existing_meals = []
            for day, meals in existing.get("days", {}).items():
                dinner = slot_display_text(meals.get("dinner"))
                if dinner:
                    existing_meals.append(f"{day}: {dinner}")
            existing_str = "\n".join(existing_meals) if existing_meals else "None planned yet."
        except Exception:
            existing_str = "None planned yet."

        prompt = (
            f"You are a Catholic homeschool family meal planner.\n"
            f"Liturgical season: {_season()}.\n"
            f"Meal rules:\n{rules_str}\n\n"
            f"Already planned this week:\n{existing_str}\n\n"
            f"Suggest dinners for any unplanned days Monday–Friday (and optionally Sat/Sun). "
            f"Format each as: 'Monday — Meal name (brief note)'. "
            f"Consider the liturgical season (e.g. meatless Fridays in Lent). "
            f"Keep meals practical for a busy homeschool family."
        )
        text = _call_claude(prompt, 400)
        return {"html": _format_html(text), "text": text}
    except Exception as e:
        return {"html": f"<p style='color:#ef4444;'>Error: {e}</p>", "text": ""}


# ── 3. School Plan Suggester ──────────────────────────────────────────────────

def ai_school_plan(iso: str, weekday: str, capacity: str) -> dict:
    """Suggest which subjects to prioritize today per child."""
    try:
        from daily_schedule_engine import build_schedule_payload, CHILDREN
        from data_helpers import load_progress

        progress = load_progress()

        child_summaries = []
        for child in CHILDREN:
            try:
                payload = build_schedule_payload(child, weekday, iso, iso)
                blocks  = payload.get("school_blocks", [])
                done    = []
                todo    = []
                for b in blocks:
                    subject = b.get("subject","")
                    items   = b.get("items", [])
                    n_done  = 0
                    for item in items:
                        tid = item.get("task_id","")
                        val = progress.get(tid, False)
                        if isinstance(val, dict):
                            if val.get("done"):
                                n_done += 1
                        elif val:
                            n_done += 1
                    if n_done == len(items) and items:
                        done.append(subject)
                    else:
                        todo.append(subject)
                child_summaries.append(f"{child}: Done={', '.join(done) or 'none'} | Todo={', '.join(todo) or 'all clear'}")
            except Exception as ex:
                child_summaries.append(f"{child}: (error loading schedule)")

        prompt = (
            f"You are a Catholic classical homeschool advisor.\n"
            f"Today: {weekday}, {iso}. Season: {_season()}.\n"
            f"Mom's capacity: {capacity or 'not set'}.\n\n"
            f"Family constraints:\n{_constraints()}\n\n"
            f"Current school status per child:\n" + "\n".join(child_summaries) + "\n\n"
            f"Given Mom's capacity today, suggest:\n"
            f"1. Which subjects to prioritize for each child\n"
            f"2. Which can be done independently vs need Mom\n"
            f"3. A suggested order to work through them\n"
            f"Be practical and brief. Low capacity = simplify ruthlessly."
        )
        text = _call_claude(prompt, 500)
        return {"html": _format_html(text), "text": text}
    except Exception as e:
        return {"html": f"<p style='color:#ef4444;'>Error: {e}</p>", "text": ""}


# ── 4. Evening Examen ─────────────────────────────────────────────────────────

def ai_evening_examen(iso: str) -> dict:
    """Generate a personalized evening examen prompt."""
    try:
        from render_morning_anchor import _get_anchor_state
        anchor   = _get_anchor_state(iso)
        capacity = anchor.get("capacity", "")
        launch   = anchor.get("launch", {})
        evening  = anchor.get("evening", {})

        morning_done = all(launch.get(k) for k in ["gather","review","goal","prayer","begin"])

        # Goal check-ins today
        try:
            from render_goals import get_active_goals_with_steps, current_quarter, quarter_week_number
            goals = get_active_goals_with_steps()
            today_str = iso
            goal_lines = []
            for g in goals:
                status = g.get("status","")
                goal_lines.append(f"{g['title']}: {status or 'not checked in'}")
            goals_str = "\n".join(goal_lines) or "No active goals"
        except Exception:
            goals_str = "Goals unavailable"

        # Virtue
        try:
            from render_virtues import load_personal_virtue
            pv = load_personal_virtue() or {}
            virtue = (pv.get("current") or {}).get("virtue","")
        except Exception:
            virtue = ""

        prompt = (
            f"You are a warm Catholic spiritual director.\n"
            f"Today: {iso}. Liturgical season: {_season()}.\n"
            f"Mom's capacity today: {capacity or 'not recorded'}.\n"
            f"Morning routine completed: {'Yes' if morning_done else 'No'}.\n"
            f"Current virtue focus: {virtue or 'none set'}.\n"
            f"Goal progress today:\n{goals_str}\n\n"
            f"Write a personal evening examen for this specific day — 3 questions that invite "
            f"honest, gentle self-reflection. Reference the liturgical season, her capacity, "
            f"and virtue if relevant. End with a one-sentence prayer of surrender. "
            f"Tone: warm, not guilt-inducing. Like a wise spiritual director who knows her well."
        )
        text = _call_claude(prompt, 400)
        return {"html": _format_html(text), "text": text}
    except Exception as e:
        return {"html": f"<p style='color:#ef4444;'>Error: {e}</p>", "text": ""}


# ── 5. Weekly Review ──────────────────────────────────────────────────────────

def ai_weekly_review(week_key: str) -> dict:
    """Sunday review: what happened this week, what to carry forward."""
    try:
        from render_goals import get_active_goals_with_steps, current_quarter, quarter_week_number, load_quarter_plan, completion_pct
        from datetime import datetime as _dt

        # Weekly intentions
        try:
            from render_plan_week import load_intentions
            intentions = load_intentions(week_key)
            important  = intentions.get("most_important","")
            tasks      = intentions.get("weekly_tasks",[])
            done_tasks = [t.get("text","") for t in tasks if t.get("done")]
            undone     = [t.get("text","") for t in tasks if not t.get("done")]
        except Exception:
            important = ""; done_tasks = []; undone = []

        # Goal progress
        goals = get_active_goals_with_steps()
        goal_lines = []
        for g in goals:
            status = g.get("status","")
            goal_lines.append(f"{g['title']} ({g['category']}): week check-in = {status or 'none'}")

        # 5AM completion this week
        try:
            from render_5am import load_day, _week_monday, _week_dates
            mon = _week_monday(week_key)  if week_key else date.today() - timedelta(days=date.today().weekday())
            club_days = sum(1 for d in [mon + timedelta(days=i) for i in range(7)]
                           if any(load_day(d).get(s,{}).get("done") for s in ["move","reflect","grow"]))
        except Exception:
            club_days = 0

        prompt = (
            f"You are a warm Catholic homeschool family coach doing a Sunday review.\n"
            f"Week: {week_key}. Season: {_season()}.\n\n"
            f"Most important thing this week: {important or 'not set'}\n"
            f"Tasks completed: {', '.join(done_tasks) or 'none recorded'}\n"
            f"Tasks unfinished: {', '.join(undone) or 'none'}\n"
            f"5AM Club days completed: {club_days}/7\n"
            f"Goal check-ins:\n" + "\n".join(goal_lines or ["No active goals"]) + "\n\n"
            f"Write a warm, honest weekly review (3-4 paragraphs):\n"
            f"1. Celebrate what went well\n"
            f"2. Name gently what didn't happen and why it might be okay\n"
            f"3. One thing to carry into next week\n"
            f"4. A short blessing or prayer for the week ahead\n"
            f"Tone: like a wise, encouraging friend who loves her family."
        )
        text = _call_claude(prompt, 600)
        return {"html": _format_html(text), "text": text}
    except Exception as e:
        return {"html": f"<p style='color:#ef4444;'>Error: {e}</p>", "text": ""}


# ── 6. Chore Adjuster ────────────────────────────────────────────────────────

def ai_chore_adjust(iso: str, capacity: str) -> dict:
    """Suggest chore simplifications for Low/Medium capacity days."""
    try:
        from render_chores import load_chores_data
        from daily_schedule_engine import CHILDREN
        from datetime import datetime as _dt
        weekday = _dt.fromisoformat(iso).strftime("%A")

        chores_data = load_chores_data()
        chore_lines = []
        for child in CHILDREN:
            boy_chores = chores_data.get("boys", {}).get(child, {})
            today_chores = boy_chores.get(weekday, [])
            if today_chores:
                chore_lines.append(f"{child}: {', '.join(str(c) for c in today_chores[:5])}")

        prompt = (
            f"You are a practical Catholic homeschool family organizer.\n"
            f"Today: {weekday}, {iso}. Season: {_season()}.\n"
            f"Mom's capacity: {capacity}.\n\n"
            f"Today's chores:\n" + ("\n".join(chore_lines) or "No chores data available") + "\n\n"
            f"Family constraints:\n{_constraints()}\n\n"
            f"Given {capacity} capacity, suggest:\n"
            f"1. Which chores are essential today (keep)\n"
            f"2. Which can be deferred to tomorrow or this week\n"
            f"3. Any chores boys can take from Mom's plate today\n"
            f"Be specific and practical. Low capacity = radical simplification."
        )
        text = _call_claude(prompt, 400)
        return {"html": _format_html(text), "text": text}
    except Exception as e:
        return {"html": f"<p style='color:#ef4444;'>Error: {e}</p>", "text": ""}


# ── 7. Intention Prayer ───────────────────────────────────────────────────────

def ai_intention_prayer(intention_id: str) -> dict:
    """Write a short prayer for a specific prayer intention."""
    try:
        from render_prayer import load_intentions
        intentions = load_intentions()
        intention  = next((i for i in intentions if i.get("id") == intention_id), None)
        if not intention:
            return {"html": "<p>Intention not found.</p>", "text": ""}

        title  = intention.get("title","")
        desc   = intention.get("description","")
        total  = sum(e.get("count",1) for e in intention.get("prayer_log",[]))

        prompt = (
            f"You are a Catholic spiritual writer.\n"
            f"Prayer intention: {title}\n"
            f"Details: {desc or 'No details provided'}\n"
            f"Prayers already offered: {total}\n"
            f"Liturgical season: {_season()}\n\n"
            f"Write a short, heartfelt Catholic intercessory prayer for this intention. "
            f"2-4 sentences. Reference a relevant saint or scripture if natural. "
            f"End with 'Through Christ our Lord. Amen.' "
            f"Tone: sincere, warm, not overly formal."
        )
        text = _call_claude(prompt, 200)
        return {"html": _format_html(text), "text": text}
    except Exception as e:
        return {"html": f"<p style='color:#ef4444;'>Error: {e}</p>", "text": ""}