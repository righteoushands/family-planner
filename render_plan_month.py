"""
render_plan_month.py — Plan My Month
Shows active quarterly goals with monthly milestone tracking,
liturgical season overview, cycle forecast, and monthly intentions.
"""
import json, os
from datetime import date, timedelta
from html import escape

from render_goals import (
    load_master_goals, load_quarter_plan, current_quarter,
    quarter_week_number, completion_pct, goal_progress_bars,
    CATEGORY_ICONS, CHECK_COLORS,
)
from render_settings import load_app_settings
from ui_helpers import html_page, top_nav, render_status_message

MONTH_DIR = "data/monthly_intentions"


def _month_key(d=None):
    if d is None:
        d = date.today()
    return d.strftime("%Y-%m")


AAR_DIMENSIONS = [
    ("prayer",    "Prayer Life",      "Daily prayer, Mass, devotions, Liturgy of the Hours"),
    ("vocation",  "Vocation / Family","Marriage, motherhood, homeschool faithfulness"),
    ("goals",     "Goals / Growth",   "Progress on your quarterly commitments"),
    ("home",      "Home & Order",     "Domestic life, hospitality, rhythm, meals"),
    ("spiritual", "Spiritual Depth",  "Formation, reading, spiritual direction, virtue"),
]

MONTH_CHECKLIST_ITEMS = [
    ("confession",     "Went to Confession"),
    ("first_friday",   "Observed First Friday"),
    ("first_saturday", "Observed First Saturday"),
    ("lectio",         "Prayed Lectio Divina at least once"),
    ("adoration",      "Made a Holy Hour of Adoration"),
    ("family_rosary",  "Led Family Rosary at least once"),
]


def load_month_plan(month_key):
    os.makedirs(MONTH_DIR, exist_ok=True)
    path = f"{MONTH_DIR}/{month_key}.json"
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {
            "month": month_key,
            "focus": "",
            "protect": "",
            "theme": "",
            "goal_milestones": {},
            "ai_briefing": "",
            "aar": {},
            "prayer_plan": {"morning": "", "afternoon": "", "evening": ""},
            "feast_plan": [{"name": "", "date": "", "devotion": ""} for _ in range(3)],
            "discernment": "",
            "blessings_month": "",
            "shortcomings": "",
            "lessons": "",
            "month_checklist": {},
        }


def save_month_plan(data):
    os.makedirs(MONTH_DIR, exist_ok=True)
    path = f"{MONTH_DIR}/{data['month']}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _month_dates(month_key):
    try:
        year, month = month_key.split("-")
        import calendar
        _, days = calendar.monthrange(int(year), int(month))
        start = date(int(year), int(month), 1)
        return [start + timedelta(days=i) for i in range(days)]
    except Exception:
        today = date.today()
        return [today]


def _cycle_forecast(month_dates_list):
    """Returns list of (date, phase, color) for cycle phase by day."""
    result = []
    try:
        with open("data/cycle_log.json") as f:
            log = json.load(f)
        dates = sorted([e["day1"] for e in log if e.get("day1")])
        if not dates:
            return result
        last = date.fromisoformat(dates[-1])
        lengths = []
        for i in range(1, len(dates)):
            try:
                d1 = date.fromisoformat(dates[i-1])
                d2 = date.fromisoformat(dates[i])
                lengths.append((d2-d1).days)
            except Exception:
                pass
        avg_len = round(sum(lengths)/len(lengths)) if lengths else 28
        for d in month_dates_list:
            cd = (d - last).days + 1
            # Advance to correct cycle position
            while cd > avg_len:
                cd -= avg_len
            if cd <= 0:
                result.append((d, "", "#e5e7eb"))
            elif cd <= 5:   result.append((d, "M", "#c0392b"))
            elif cd <= 12:  result.append((d, "F", "#27ae60"))
            elif cd <= 16:  result.append((d, "O", "#2980b9"))
            elif cd <= 21:  result.append((d, "EL","#8e44ad"))
            else:           result.append((d, "LL","#e67e22"))
    except Exception:
        pass
    return result


def render_plan_month_page(month_key=None, status=""):
    if not month_key:
        month_key = _month_key()

    try:
        year_int, month_int = (int(x) for x in month_key.split("-"))
        import calendar as cal
        month_name = date(year_int, month_int, 1).strftime("%B %Y")
        prev_month_date = date(year_int, month_int, 1) - timedelta(days=1)
        next_month_date = date(year_int, month_int, cal.monthrange(year_int, month_int)[1]) + timedelta(days=1)
        prev_key = _month_key(prev_month_date)
        next_key = _month_key(next_month_date)
    except Exception:
        month_name = month_key
        prev_key = next_key = month_key

    month_plan   = load_month_plan(month_key)
    settings     = load_app_settings()
    api_key      = (settings.get("anthropic_api_key", "") or
                    settings.get("family_constraints", {}).get("anthropic_api_key", ""))
    quarter_key  = current_quarter(date(year_int, month_int, 1))
    qplan        = load_quarter_plan(quarter_key)
    master       = {g["id"]: g for g in load_master_goals()}
    active_ids   = qplan.get("active_goal_ids", [])

    # Liturgical season
    try:
        from render_liturgical import get_liturgical_season, get_moveable_feasts, FIXED_FEASTS
        season = get_liturgical_season(date(year_int, month_int, 1))
        season_names = {"lent","advent","christmas","easter","ordinary time","holy week"}
        mv = get_moveable_feasts(year_int)
        month_feasts = []
        for d in _month_dates(month_key):
            feast = ""
            if d in mv:
                nm = mv[d][0]
                if nm.lower() not in season_names:
                    feast = nm
            elif (d.month, d.day) in FIXED_FEASTS:
                nm = FIXED_FEASTS[(d.month, d.day)][0]
                if nm.lower() not in season_names:
                    feast = nm
            if feast:
                month_feasts.append((d, feast))
    except Exception:
        season = "Ordinary Time"
        month_feasts = []

    # Cycle mini-calendar
    mdates    = _month_dates(month_key)
    cycle_map = {d: (ph, col) for d, ph, col in _cycle_forecast(mdates)}

    # Build mini calendar
    try:
        import calendar as cal
        first_weekday = date(year_int, month_int, 1).weekday()  # 0=Mon
        cal_cells = []
        for _ in range(first_weekday):
            cal_cells.append("")
        for d in mdates:
            ph, col = cycle_map.get(d, ("","#e5e7eb"))
            is_today = d == date.today()
            cal_cells.append((d.day, ph, col, is_today))
    except Exception:
        cal_cells = []

    cal_headers = "".join(
        f'<div style="font-size:0.65em;font-weight:700;color:var(--ink-faint);'
        f'text-align:center;">{h}</div>'
        for h in ["M","T","W","T","F","S","S"]
    )
    cal_days = ""
    for cell in cal_cells:
        if cell == "":
            cal_days += '<div></div>'
        else:
            day_num, ph, col, is_today = cell
            border  = "2px solid var(--ink)" if is_today else "none"
            bg_val  = (col + "25") if ph else ""
            dot_html = (
                '<span style="position:absolute;bottom:1px;right:1px;width:4px;'
                'height:4px;border-radius:50%;background:' + col + ';"></span>'
            ) if ph else ""
            cal_days += (
                '<div style="aspect-ratio:1;border-radius:50%;display:flex;'
                'align-items:center;justify-content:center;'
                'background:' + bg_val + ';'
                'border:' + border + ';position:relative;" title="' + (ph or "") + '">'
                '<span style="font-size:0.7em;color:var(--ink);">' + str(day_num) + '</span>'
                + dot_html +
                '</div>'
            )

    # Build goal milestone cards
    goal_cards = ""
    for gid in active_ids:
        g      = master.get(gid, {})
        g_plan = qplan.get("goals", {}).get(gid, {})
        if not g:
            continue
        title    = escape(g.get("title", ""))
        cat      = g.get("category", "")
        icon     = CATEGORY_ICONS.get(cat, "\u2b50")
        wk_num   = quarter_week_number(date(year_int, month_int, 1), quarter_key)
        pct      = completion_pct(g_plan, wk_num)
        bars     = goal_progress_bars(g_plan, quarter_key)

        # Monthly milestone (user-editable)
        milestone = escape(
            month_plan.get("goal_milestones", {}).get(gid, {}).get("milestone", "")
        )
        milestone_done = month_plan.get("goal_milestones", {}).get(gid, {}).get("done", False)

        goal_cards += f"""
<div style="border:1.5px solid var(--border);border-radius:12px;padding:12px;margin-bottom:10px;">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:8px;">
    <div>
      <div style="font-size:0.68em;color:var(--ink-faint);">{icon} {escape(cat)}</div>
      <div style="font-weight:700;font-size:0.9em;color:var(--ink);">{title}</div>
    </div>
    <div style="font-size:0.72em;font-weight:700;color:#22c55e;">{pct}%</div>
  </div>
  <div style="margin-bottom:8px;">{bars}</div>
  <label style="font-size:0.72em;font-weight:700;color:var(--ink-faint);">
    This month's milestone
  </label>
  <div style="display:flex;align-items:center;gap:8px;margin-top:4px;">
    <input type="checkbox" {"checked" if milestone_done else ""}
           onchange="toggleMilestone('{escape(gid)}',this)"
           style="width:16px;height:16px;accent-color:#22c55e;flex-shrink:0;">
    <input type="text" id="ms-{escape(gid)}" value="{milestone}"
           placeholder="What does progress look like this month?"
           onblur="saveMilestone('{escape(gid)}')"
           style="flex:1;padding:6px 10px;font-size:0.82em;border-radius:8px;
                  border:1.5px solid var(--border);font-family:inherit;
                  {"text-decoration:line-through;color:var(--ink-faint);" if milestone_done else ""}">
  </div>
</div>"""

    if not goal_cards:
        goal_cards = (
            '<div class="card" style="text-align:center;padding:16px;">'
            '<p style="color:var(--ink-faint);font-size:0.88em;">No active goals this quarter.</p>'
            '<a href="/plan-quarter" style="font-size:0.85em;color:var(--brown);font-weight:700;">'
            'Set quarterly goals \u2192</a></div>'
        )

    # Feast list
    feast_list = ""
    if month_feasts:
        for d, feast in month_feasts[:8]:
            feast_list += (
                f'<div style="display:flex;gap:8px;align-items:baseline;padding:4px 0;'
                f'border-bottom:1px solid var(--border-light);">'
                f'<span style="font-size:0.72em;font-weight:700;color:var(--ink-faint);'
                f'width:32px;">{d.strftime("%b %-d")}</span>'
                f'<span style="font-size:0.82em;color:var(--brown);">\u271d {escape(feast)}</span>'
                f'</div>'
            )
    else:
        feast_list = '<p style="font-size:0.82em;color:var(--ink-faint);">No major feasts this month.</p>'

    focus   = escape(month_plan.get("focus", ""))
    protect = escape(month_plan.get("protect", ""))
    theme   = escape(month_plan.get("theme", ""))

    saved_briefing = escape(month_plan.get("ai_briefing", ""))

    ai_btn = ""
    if api_key:
        ai_btn = (
            f'<button onclick="aiBriefMonth()" '
            f'style="width:100%;padding:10px;background:linear-gradient(135deg,#1c1610,#2a1e10);'
            f'color:var(--gold-light);border:none;border-radius:10px;font-size:0.88em;'
            f'font-weight:600;font-family:inherit;cursor:pointer;margin-top:10px;">'
            f'\u2728 {"Refresh" if saved_briefing else "Generate"} monthly overview</button>'
            f'<div id="ai-month-loading" style="display:none;text-align:center;padding:12px;'
            f'font-size:0.82em;color:var(--ink-faint);">\u231b Thinking...</div>'
            f'<div id="ai-month-result" style="display:none;margin-top:10px;padding:10px 12px;'
            f'background:#faf8f5;border-radius:8px;font-size:0.85em;line-height:1.65;'
            f'color:var(--ink);"></div>'
        )

    month_plan_js = json.dumps(month_plan)
    active_goals_js = json.dumps([
        {"id": gid, "title": master.get(gid, {}).get("title", "")}
        for gid in active_ids
    ])

    # ── SaintMaker: After Action Review ──────────────────────────────────────
    aar_data = month_plan.get("aar", {})
    aar_rows = ""
    for key, label, hint in AAR_DIMENSIONS:
        score = int(aar_data.get(key, 0))
        stars = ""
        for n in range(1, 11):
            checked = "checked" if n <= score else ""
            stars += (
                '<input type="radio" name="aar-' + key + '" value="' + str(n) + '" '
                + checked + ' onchange="saveAAR(\'' + key + '\',' + str(n) + ')" '
                'style="display:none;" id="aar-' + key + '-' + str(n) + '">'
                '<label for="aar-' + key + '-' + str(n) + '" style="cursor:pointer;'
                'font-size:1.1em;color:' + ('#f59e0b' if n <= score else '#e5e7eb') + ';">&#9733;</label>'
            )
        aar_rows += (
            '<div style="padding:8px 0;border-bottom:1px solid var(--border-light);">'
            '<div style="font-size:0.78em;font-weight:700;color:var(--ink);margin-bottom:2px;">' + escape(label) + '</div>'
            '<div style="font-size:0.7em;color:var(--ink-faint);margin-bottom:5px;">' + escape(hint) + '</div>'
            '<div id="aar-stars-' + key + '" style="display:flex;gap:2px;">' + stars + '</div>'
            '</div>'
        )
    aar_html = (
        '<div class="card" style="margin-bottom:14px;">'
        '<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;'
        'color:var(--ink-faint);margin-bottom:4px;">✦ After Action Review</div>'
        '<div style="font-size:0.75em;color:var(--ink-faint);font-style:italic;margin-bottom:10px;">'
        'How did this month go? Rate each area 1–10</div>'
        + aar_rows + '</div>'
    )

    # ── SaintMaker: Prayer Plan ───────────────────────────────────────────────
    pp_data = month_plan.get("prayer_plan", {})
    pp_m = escape(pp_data.get("morning",   ""))
    pp_a = escape(pp_data.get("afternoon", ""))
    pp_e = escape(pp_data.get("evening",   ""))
    prayer_plan_html = (
        '<div class="card" style="margin-bottom:14px;">'
        '<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;'
        'color:var(--ink-faint);margin-bottom:10px;">✦ Monthly Prayer Plan</div>'
        '<label style="font-size:0.75em;">Morning prayer rhythm</label>'
        '<input type="text" id="pp-morning" value="' + pp_m + '" '
        'placeholder="Lauds, Rosary, meditation, Mass..." onchange="autoSave()" '
        'style="margin-bottom:10px;padding:7px 10px;font-size:0.85em;border-radius:8px;'
        'border:1.5px solid var(--border);font-family:inherit;width:100%;box-sizing:border-box;">'
        '<label style="font-size:0.75em;">Afternoon / midday</label>'
        '<input type="text" id="pp-afternoon" value="' + pp_a + '" '
        'placeholder="Angelus, brief examen, intentions..." onchange="autoSave()" '
        'style="margin-bottom:10px;padding:7px 10px;font-size:0.85em;border-radius:8px;'
        'border:1.5px solid var(--border);font-family:inherit;width:100%;box-sizing:border-box;">'
        '<label style="font-size:0.75em;">Evening prayer rhythm</label>'
        '<input type="text" id="pp-evening" value="' + pp_e + '" '
        'placeholder="Vespers, Examen, night prayers, Compline..." onchange="autoSave()" '
        'style="padding:7px 10px;font-size:0.85em;border-radius:8px;'
        'border:1.5px solid var(--border);font-family:inherit;width:100%;box-sizing:border-box;">'
        '</div>'
    )

    # ── SaintMaker: Feast Plan ────────────────────────────────────────────────
    fp_data = month_plan.get("feast_plan", [{} for _ in range(3)])
    if not isinstance(fp_data, list) or len(fp_data) < 3:
        fp_data = (fp_data + [{}, {}, {}])[:3]
    fp_rows = ""
    for i in range(3):
        fp_name    = escape(fp_data[i].get("name",    ""))
        fp_date    = escape(fp_data[i].get("date",    ""))
        fp_dev     = escape(fp_data[i].get("devotion",""))
        fp_rows += (
            '<div style="border:1px solid var(--border);border-radius:10px;padding:10px;margin-bottom:8px;">'
            '<div style="display:grid;grid-template-columns:1fr 120px;gap:8px;margin-bottom:6px;">'
            '<input type="text" id="fp-name-' + str(i) + '" value="' + fp_name + '" '
            'placeholder="Feast or celebration..." onchange="autoSave()" '
            'style="padding:6px 10px;font-size:0.82em;border-radius:8px;border:1.5px solid var(--border);font-family:inherit;">'
            '<input type="date" id="fp-date-' + str(i) + '" value="' + fp_date + '" '
            'onchange="autoSave()" '
            'style="padding:6px 8px;font-size:0.82em;border-radius:8px;border:1.5px solid var(--border);font-family:inherit;">'
            '</div>'
            '<input type="text" id="fp-devotion-' + str(i) + '" value="' + fp_dev + '" '
            'placeholder="How will you celebrate or observe?" onchange="autoSave()" '
            'style="width:100%;padding:6px 10px;font-size:0.82em;border-radius:8px;border:1.5px solid var(--border);font-family:inherit;box-sizing:border-box;">'
            '</div>'
        )
    feast_plan_html = (
        '<div class="card" style="margin-bottom:14px;">'
        '<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;'
        'color:var(--ink-faint);margin-bottom:10px;">✦ Feast Plan</div>'
        '<div style="font-size:0.75em;color:var(--ink-faint);font-style:italic;margin-bottom:10px;">'
        'Plan how you\'ll mark three key feasts or celebrations this month</div>'
        + fp_rows + '</div>'
    )

    # ── SaintMaker: Discernment + Reflection ─────────────────────────────────
    disc_val  = escape(month_plan.get("discernment",     ""))
    bless_val = escape(month_plan.get("blessings_month", ""))
    short_val = escape(month_plan.get("shortcomings",    ""))
    less_val  = escape(month_plan.get("lessons",         ""))
    discernment_html = (
        '<div class="card" style="margin-bottom:14px;">'
        '<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;'
        'color:var(--ink-faint);margin-bottom:10px;">✦ Monthly Discernment &amp; Reflection</div>'
        '<label style="font-size:0.75em;">Blessings — Where did God show up this month?</label>'
        '<textarea id="m-blessings" rows="2" onchange="autoSave()" '
        'style="width:100%;padding:7px 10px;font-size:0.85em;border-radius:8px;'
        'border:1.5px solid var(--border);font-family:inherit;resize:vertical;box-sizing:border-box;margin-bottom:10px;">'
        + bless_val + '</textarea>'
        '<label style="font-size:0.75em;">Shortcomings — Where did you fall short?</label>'
        '<textarea id="m-shortcomings" rows="2" onchange="autoSave()" '
        'style="width:100%;padding:7px 10px;font-size:0.85em;border-radius:8px;'
        'border:1.5px solid var(--border);font-family:inherit;resize:vertical;box-sizing:border-box;margin-bottom:10px;">'
        + short_val + '</textarea>'
        '<label style="font-size:0.75em;">Lessons — What is God teaching you?</label>'
        '<textarea id="m-lessons" rows="2" onchange="autoSave()" '
        'style="width:100%;padding:7px 10px;font-size:0.85em;border-radius:8px;'
        'border:1.5px solid var(--border);font-family:inherit;resize:vertical;box-sizing:border-box;margin-bottom:10px;">'
        + less_val + '</textarea>'
        '<label style="font-size:0.75em;">Discernment — What is God calling you to next month?</label>'
        '<textarea id="m-discernment" rows="3" onchange="autoSave()" '
        'style="width:100%;padding:7px 10px;font-size:0.85em;border-radius:8px;'
        'border:1.5px solid var(--border);font-family:inherit;resize:vertical;box-sizing:border-box;">'
        + disc_val + '</textarea>'
        '</div>'
    )

    # ── SaintMaker: Month Checklist ───────────────────────────────────────────
    mc_data = month_plan.get("month_checklist", {})
    mc_rows = ""
    for key, label in MONTH_CHECKLIST_ITEMS:
        checked = 'checked' if mc_data.get(key, False) else ''
        mc_rows += (
            '<div style="display:flex;align-items:center;gap:8px;padding:7px 0;'
            'border-bottom:1px solid var(--border-light);">'
            '<input type="checkbox" id="mc-' + key + '" ' + checked + ' '
            'onchange="saveMC(\'' + key + '\',this.checked)" '
            'style="width:18px;height:18px;accent-color:var(--brown);flex-shrink:0;">'
            '<label for="mc-' + key + '" style="font-size:0.85em;cursor:pointer;">' + escape(label) + '</label>'
            '</div>'
        )
    checklist_html = (
        '<div class="card" style="margin-bottom:14px;">'
        '<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;'
        'color:var(--ink-faint);margin-bottom:10px;">✦ Month Checklist</div>'
        + mc_rows + '</div>'
    )

    body = top_nav() + render_status_message(status) + f"""
<div style="display:flex;align-items:flex-start;justify-content:space-between;
            flex-wrap:wrap;gap:8px;padding-top:4px;margin-bottom:16px;">
  <div>
    <div style="font-family:'Cormorant Garamond',Georgia,serif;
                font-size:2rem;font-weight:600;color:var(--ink);">Plan My Month</div>
    <div style="font-size:0.85em;color:var(--ink-muted);margin-top:2px;">
      {escape(month_name)} &middot; {escape(season)}
    </div>
  </div>
  <div style="display:flex;gap:6px;flex-wrap:wrap;">
    <a href="/plan-month?month={escape(prev_key)}"
       style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);">&larr;</a>
    <a href="/plan-month"
       style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);">This month</a>
    <a href="/plan-month?month={escape(next_key)}"
       style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);">&rarr;</a>
    <button onclick="saveMonth()"
            style="padding:7px 16px;background:var(--ink);color:var(--gold-light);border:none;border-radius:8px;font-size:0.82em;font-weight:700;font-family:inherit;cursor:pointer;">Save</button>
  </div>
</div>
<div id="save-status" style="font-size:0.82em;color:#22c55e;min-height:16px;margin-bottom:8px;"></div>

<!-- Two column top: calendar + feasts -->
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px;">
  <div class="card">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;">
      Cycle Overview
    </div>
    <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-bottom:6px;">
      {cal_headers}
    </div>
    <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;">
      {cal_days}
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">
      <span style="font-size:0.62em;color:#c0392b;">&#9632; Menstrual</span>
      <span style="font-size:0.62em;color:#27ae60;">&#9632; Follicular</span>
      <span style="font-size:0.62em;color:#2980b9;">&#9632; Ovulatory</span>
      <span style="font-size:0.62em;color:#8e44ad;">&#9632; Early Luteal</span>
      <span style="font-size:0.62em;color:#e67e22;">&#9632; Late Luteal</span>
    </div>
  </div>
  <div class="card">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;">
      Feasts &amp; Celebrations
    </div>
    {feast_list}
  </div>
</div>

<!-- Monthly intentions -->
<div class="card" style="margin-bottom:14px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:12px;">Monthly Intentions</div>
  <label style="font-size:0.75em;">Monthly theme or word</label>
  <input type="text" id="m-theme" value="{theme}"
         placeholder="e.g. Simplicity, Presence, Order..."
         onchange="autoSave()" style="margin-bottom:10px;">
  <label style="font-size:0.75em;">Main focus this month</label>
  <input type="text" id="m-focus" value="{focus}"
         placeholder="What matters most this month?"
         onchange="autoSave()" style="margin-bottom:10px;">
  <label style="font-size:0.75em;">What I will protect</label>
  <input type="text" id="m-protect" value="{protect}"
         placeholder="Morning prayer, school rhythm, date night..."
         onchange="autoSave()">
  {ai_btn}
</div>

{aar_html}

{prayer_plan_html}

{feast_plan_html}

<!-- Goal milestones -->
<div style="margin-bottom:14px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:10px;display:flex;justify-content:space-between;">
    <span>Goal Milestones This Month</span>
    <a href="/plan-quarter" style="font-size:0.9em;color:var(--brown);font-weight:600;text-decoration:none;text-transform:none;">
      Manage goals &rarr;
    </a>
  </div>
  {goal_cards}
</div>

{discernment_html}

{checklist_html}

<!-- Navigation -->
<div style="display:flex;gap:8px;flex-wrap:wrap;padding:8px 0;">
  <a href="/plan-week" style="font-size:0.82em;color:var(--brown);font-weight:700;text-decoration:none;">This week &rarr;</a>
  <span style="color:var(--border);">|</span>
  <a href="/plan-year" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">Annual overview &rarr;</a>
  <span style="color:var(--border);">|</span>
  <a href="/plan-quarter" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">Quarterly goals &rarr;</a>
</div>

<script>
var _mk        = '{escape(month_key)}';
var _mPlan     = {month_plan_js};
var _aGoals    = {active_goals_js};
var _saveTimer = null;
if (!_mPlan.aar)             _mPlan.aar             = {{}};
if (!_mPlan.prayer_plan)     _mPlan.prayer_plan     = {{}};
if (!_mPlan.feast_plan)      _mPlan.feast_plan      = [{{name:'',date:'',devotion:''}},{{name:'',date:'',devotion:''}},{{name:'',date:'',devotion:''}}];
if (!_mPlan.month_checklist) _mPlan.month_checklist = {{}};

function autoSave() {{ clearTimeout(_saveTimer); _saveTimer = setTimeout(saveMonth, 1200); }}

function saveAAR(key, val) {{
  _mPlan.aar[key] = val;
  var labels = document.querySelectorAll('label[for^="aar-' + key + '-"]');
  labels.forEach(function(lbl) {{
    var n = parseInt(lbl.getAttribute('for').split('-').pop());
    lbl.style.color = n <= val ? '#f59e0b' : '#e5e7eb';
  }});
  autoSave();
}}

function saveMC(key, val) {{
  if (!_mPlan.month_checklist) _mPlan.month_checklist = {{}};
  _mPlan.month_checklist[key] = val;
  autoSave();
}}

function saveMonth() {{
  _mPlan.theme   = document.getElementById('m-theme')   ? document.getElementById('m-theme').value   || '' : _mPlan.theme;
  _mPlan.focus   = document.getElementById('m-focus')   ? document.getElementById('m-focus').value   || '' : _mPlan.focus;
  _mPlan.protect = document.getElementById('m-protect') ? document.getElementById('m-protect').value || '' : _mPlan.protect;
  var ppM = document.getElementById('pp-morning'),
      ppA = document.getElementById('pp-afternoon'),
      ppE = document.getElementById('pp-evening');
  if (ppM || ppA || ppE) {{
    if (!_mPlan.prayer_plan) _mPlan.prayer_plan = {{}};
    if (ppM) _mPlan.prayer_plan.morning   = ppM.value || '';
    if (ppA) _mPlan.prayer_plan.afternoon = ppA.value || '';
    if (ppE) _mPlan.prayer_plan.evening   = ppE.value || '';
  }}
  var fp = [];
  for (var i = 0; i < 3; i++) {{
    var fn = document.getElementById('fp-name-'    + i);
    var fd = document.getElementById('fp-date-'    + i);
    var fv = document.getElementById('fp-devotion-'+ i);
    fp.push({{name: fn?fn.value:'', date: fd?fd.value:'', devotion: fv?fv.value:''}});
  }}
  _mPlan.feast_plan = fp;
  var bl = document.getElementById('m-blessings'),
      sh = document.getElementById('m-shortcomings'),
      le = document.getElementById('m-lessons'),
      di = document.getElementById('m-discernment');
  if (bl) _mPlan.blessings_month = bl.value || '';
  if (sh) _mPlan.shortcomings    = sh.value || '';
  if (le) _mPlan.lessons         = le.value || '';
  if (di) _mPlan.discernment     = di.value || '';
  fetch('/plan-month-save', {{
    method: 'POST', headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'month=' + encodeURIComponent(_mk) + '&data=' + encodeURIComponent(JSON.stringify(_mPlan))
  }}).then(function() {{
    var el = document.getElementById('save-status');
    if (el) {{ el.textContent = 'Saved \u2713'; setTimeout(function(){{ el.textContent=''; }}, 2000); }}
  }});
}}

function saveMilestone(gid) {{
  var inp = document.getElementById('ms-' + gid);
  if (!inp) return;
  if (!_mPlan.goal_milestones) _mPlan.goal_milestones = {{}};
  if (!_mPlan.goal_milestones[gid]) _mPlan.goal_milestones[gid] = {{}};
  _mPlan.goal_milestones[gid].milestone = inp.value;
  autoSave();
}}

function toggleMilestone(gid, cb) {{
  if (!_mPlan.goal_milestones) _mPlan.goal_milestones = {{}};
  if (!_mPlan.goal_milestones[gid]) _mPlan.goal_milestones[gid] = {{}};
  _mPlan.goal_milestones[gid].done = cb.checked;
  autoSave();
}}

function aiBriefMonth() {{
  var loading = document.getElementById('ai-month-loading');
  var result  = document.getElementById('ai-month-result');
  if (loading) loading.style.display = 'block';
  if (result)  result.style.display  = 'none';
  var payload = {{
    month: _mk, goals: _aGoals,
    focus:   document.getElementById('m-focus').value   || '',
    protect: document.getElementById('m-protect').value || '',
    theme:   document.getElementById('m-theme').value   || '',
  }};
  fetch('/ai-month-brief', {{
    method: 'POST', headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'data=' + encodeURIComponent(JSON.stringify(payload))
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (loading) loading.style.display = 'none';
    if (result) {{
      result.style.display = 'block';
      result.innerHTML = (d.briefing || d.text || 'No briefing returned.').replace(/\\n/g,'<br>');
    }}
    if (d.briefing) {{ _mPlan.ai_briefing = d.briefing; autoSave(); }}
  }}).catch(function() {{
    if (loading) loading.style.display = 'none';
    if (result) {{ result.style.display='block'; result.textContent='Error \u2014 check API key.'; }}
  }});
}}
</script>
"""
    return html_page(f"Plan My Month \u00b7 {month_name}", body)