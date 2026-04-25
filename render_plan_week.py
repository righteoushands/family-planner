"""
render_plan_week.py — Plan My Week
"""
import json, os
from datetime import date, timedelta
from html import escape

from config import CHILDREN
from render_goals import (
    get_active_goals_with_steps, current_quarter, quarter_week_number,
    CATEGORY_ICONS, CHECK_COLORS, goal_progress_bars,
    load_quarter_plan, save_quarter_plan,
)
from render_settings import load_app_settings
from ui_helpers import html_page, top_nav, render_status_message

INTENTIONS_DIR = "data/weekly_intentions"


def _week_key(for_date=None):
    if for_date is None:
        for_date = date.today()
    return for_date.strftime("%Y-%W")


def _week_monday(week_key):
    try:
        year, wk = week_key.split("-")
        jan4  = date(int(year), 1, 4)
        delta = timedelta(weeks=int(wk) - jan4.isocalendar()[1],
                          days=-jan4.weekday())
        return jan4 + delta
    except Exception:
        today = date.today()
        return today - timedelta(days=today.weekday())


def _week_dates(week_key):
    mon = _week_monday(week_key)
    return [mon + timedelta(days=i) for i in range(7)]


EXAM_QUESTIONS = [
    ("stewardship", "Stewardship", "Were you a good steward of God's gifts?"),
    ("gods_will",   "God's Will",  "Did you do God's will or your own?"),
    ("prayer",      "Prayer",      "Did you say your prayers with care?"),
    ("gratitude",   "Gratitude",   "Were you grateful to God for His gifts?"),
    ("duties",      "Duties",      "Did you do your duties in work, family life, community, and to God?"),
]

QUADRANT_LABELS = [
    ("domestic",    "Domestic",    "Home, hospitality, order, meals"),
    ("vocation",    "Vocation",    "Marriage, motherhood, homeschool"),
    ("spiritual",   "Spiritual",   "Prayer, formation, sacraments"),
    ("recreation",  "Recreation",  "Rest, leisure, friendship, beauty"),
]


def load_intentions(week_key):
    os.makedirs(INTENTIONS_DIR, exist_ok=True)
    path = f"{INTENTIONS_DIR}/{week_key}.json"
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {
            "week": week_key, "most_important": "", "protect": "",
            "let_go": "", "weekly_tasks": [], "ai_briefing": "", "plan_items": [],
            "examination": {}, "mass_intention": "",
            "weekly_3": ["", "", ""],
            "quadrants": {"domestic": "", "vocation": "", "spiritual": "", "recreation": ""},
            "blessings": "", "improvements": "",
        }


def save_intentions_data(data):
    os.makedirs(INTENTIONS_DIR, exist_ok=True)
    path = f"{INTENTIONS_DIR}/{data['week']}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _cycle_phase(d):
    try:
        with open("data/cycle_log.json") as f:
            log = json.load(f)
        dates = sorted([e["day1"] for e in log if e.get("day1")])
        if not dates:
            return ("", "#ccc")
        last = date.fromisoformat(dates[-1])
        cd = (d - last).days + 1
        if cd <= 0 or cd > 35: return ("", "#ccc")
        if cd <= 5:    return ("Menstrual",    "#c0392b")
        elif cd <= 12: return ("Follicular",   "#27ae60")
        elif cd <= 16: return ("Ovulatory",    "#2980b9")
        elif cd <= 21: return ("Early Luteal", "#8e44ad")
        else:          return ("Late Luteal",  "#e67e22")
    except Exception:
        return ("", "#ccc")


def _week_feasts(wdates):
    result = {}
    season_names = {"lent","advent","christmas","easter","ordinary time","holy week"}
    try:
        from render_liturgical import get_moveable_feasts, FIXED_FEASTS
        mv = get_moveable_feasts(wdates[0].year)
        mv.update(get_moveable_feasts(wdates[-1].year))
        for d in wdates:
            feast = ""
            if d in mv:
                nm = mv[d][0]
                if nm.lower() not in season_names:
                    feast = nm
            elif (d.month, d.day) in FIXED_FEASTS:
                nm = FIXED_FEASTS[(d.month, d.day)][0]
                if nm.lower() not in season_names:
                    feast = nm
            result[d.strftime("%A")] = feast
    except Exception:
        result = {d.strftime("%A"): "" for d in wdates}
    return result


def _week_events(wdates):
    result = {d.strftime("%A"): [] for d in wdates}
    try:
        settings = load_app_settings()
        ical_url = (settings.get("family_constraints", {}).get("ical_url", "")
                    or settings.get("ical_url", ""))
        if not ical_url:
            return result
        from render_calendar import fetch_ics_events
        events = fetch_ics_events(ical_url, "Family")
        mon, sun = wdates[0], wdates[-1]
        for ev in events:
            try:
                ev_date = date.fromisoformat(ev.get("date", "")[:10])
                if mon <= ev_date <= sun:
                    result[ev_date.strftime("%A")].append(
                        ev.get("title", ev.get("summary", "Event")))
            except Exception:
                pass
    except Exception:
        pass
    return result


def _checkin_btns_html(gid, current_status):
    """Pre-compute checkin button HTML outside any f-string."""
    parts = []
    for s, lbl in [("done","\u2713 Done"), ("partial","\u223c Partial"), ("skip","\u2715 Skip")]:
        active = current_status == s
        bg     = CHECK_COLORS[s] if active else "var(--parchment)"
        col    = "white" if active else "var(--ink-muted)"
        brd    = CHECK_COLORS[s] if active else "var(--border)"
        onclick_val = "goalCheckin('" + gid + "','" + s + "')"
        parts.append(
            '<button onclick="' + onclick_val + '" '
            'style="padding:5px 12px;font-size:0.78em;border-radius:8px;'
            'font-family:inherit;cursor:pointer;'
            'background:' + bg + ';color:' + col + ';'
            'border:1.5px solid ' + brd + ';">'
            + lbl + '</button>'
        )
    return "".join(parts)


def render_plan_week_page(week_key=None, status=""):
    if not week_key:
        week_key = _week_key()

    wdates      = _week_dates(week_key)
    mon, sun    = wdates[0], wdates[6]
    prev_key    = _week_key(mon - timedelta(days=7))
    next_key    = _week_key(mon + timedelta(days=7))
    week_label  = mon.strftime("%B %d") + " \u2013 " + sun.strftime("%B %d, %Y")
    intentions  = load_intentions(week_key)
    settings    = load_app_settings()
    api_key     = (settings.get("anthropic_api_key", "") or
                   settings.get("family_constraints", {}).get("anthropic_api_key", ""))
    quarter_key = current_quarter(mon)
    wk_num      = quarter_week_number(mon, quarter_key)
    feasts      = _week_feasts(wdates)
    events      = _week_events(wdates)

    # 1. Week at a glance
    day_cols = ""
    for d in wdates:
        dn         = d.strftime("%A")
        dl         = d.strftime("%a %-d")
        feast      = feasts.get(dn, "")
        evs        = events.get(dn, [])
        phase, pc  = _cycle_phase(d)
        is_today   = (d == date.today())
        is_wknd    = d.weekday() >= 5
        brd        = "2px solid var(--gold-mid)" if is_today else "1px solid var(--border)"
        bg         = "background:var(--gold-light);" if is_today else ""
        op         = "0.6" if is_wknd else "1"
        phase_pill = (
            '<div style="font-size:0.62em;padding:2px 5px;border-radius:8px;'
            'background:' + pc + '20;color:' + pc + ';font-weight:700;margin-top:3px;'
            'display:inline-block;">' + phase + '</div>'
        ) if phase else ""
        feast_line = (
            '<div style="font-size:0.68em;color:var(--brown);font-weight:600;'
            'margin-top:3px;">\u271d ' + escape(feast) + '</div>'
        ) if feast else ""
        ev_lines = "".join(
            '<div style="font-size:0.64em;color:var(--ink-muted);margin-top:2px;'
            'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
            '\U0001f4cc ' + escape(ev) + '</div>'
            for ev in evs[:2]
        )
        day_cols += (
            '<div style="flex:1;min-width:72px;border:' + brd + ';border-radius:9px;'
            'padding:7px 6px;' + bg + 'opacity:' + op + ';">'
            '<div style="font-size:0.78em;font-weight:700;">' + dl + '</div>'
            + phase_pill + feast_line + ev_lines +
            '</div>'
        )

    # 2. Goal steps — pre-compute all HTML before any f-string
    active_goals = get_active_goals_with_steps(quarter_key)
    goal_rows    = ""
    for g in active_goals:
        gid       = g["id"]
        gid_esc   = escape(gid)
        title     = escape(g["title"])
        cat       = g["category"]
        icon      = CATEGORY_ICONS.get(cat, "\u2b50")
        step      = escape(g.get("step", ""))
        status_v  = g.get("status", "")
        bars      = goal_progress_bars(g["g_plan"], quarter_key)
        checkins  = g["g_plan"].get("checkins", {})
        wk_now    = g["wk_num"]
        done_cnt  = sum(1 for w in range(1, wk_now) if checkins.get(str(w)) in ("done","partial"))
        pct       = str(round(done_cnt / (wk_now - 1) * 100)) + "%" if wk_now > 1 else ""

        cb_html   = _checkin_btns_html(gid_esc, status_v)
        recur_onclick = "makeRecurring('" + gid_esc + "')"
        gstep_id  = "gstep-" + gid_esc
        gstep_onblur = "saveGoalStep('" + gid_esc + "')"
        grow_id   = "grow-" + gid_esc

        goal_rows += (
            '<div style="border:1.5px solid var(--border);border-radius:12px;'
            'padding:12px;margin-bottom:10px;background:white;" id="' + grow_id + '">'
            '<div style="display:flex;align-items:flex-start;justify-content:space-between;">'
            '<div style="flex:1;">'
            '<div style="font-size:0.68em;color:var(--ink-faint);">' + icon + ' ' + escape(cat) + '</div>'
            '<div style="font-weight:700;font-size:0.9em;">' + title + '</div>'
            '<div style="margin-top:6px;">' + bars + '</div>'
            '</div>'
            + ('<div style="font-size:0.72em;font-weight:700;color:#22c55e;">' + pct + '</div>' if pct else '')
            + '</div>'
            '<div style="margin-top:10px;">'
            '<label style="font-size:0.72em;font-weight:700;color:var(--ink-faint);">Week ' + str(wk_num) + ' step</label>'
            '<input type="text" id="' + gstep_id + '" value="' + step + '" '
            'placeholder="What will you do this week?" '
            'onblur="' + gstep_onblur + '" '
            'style="width:100%;margin-top:4px;padding:7px 10px;font-size:0.85em;'
            'border-radius:8px;border:1.5px solid var(--border);font-family:inherit;">'
            '</div>'
            '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">'
            + cb_html
            + '<button onclick="' + recur_onclick + '" '
            'style="padding:5px 12px;font-size:0.72em;border-radius:8px;'
            'background:var(--parchment);color:var(--brown);border:1px solid var(--border);'
            'font-family:inherit;cursor:pointer;">\u21bb Make recurring task</button>'
            '</div></div>'
        )

    if not goal_rows:
        goal_rows = (
            '<div class="card" style="text-align:center;padding:16px;">'
            '<p style="color:var(--ink-faint);font-size:0.88em;">No active goals this quarter.</p>'
            '<a href="/plan-quarter" style="font-size:0.85em;color:var(--brown);font-weight:700;">'
            'Set quarterly goals \u2192</a></div>'
        )

    # 3. Intentions
    mi = escape(intentions.get("most_important", ""))
    pt = escape(intentions.get("protect", ""))
    lg = escape(intentions.get("let_go", ""))

    # 4. Weekly tasks
    wtasks    = intentions.get("weekly_tasks", [])
    task_rows = ""
    for i, t in enumerate(wtasks):
        txt    = escape(t.get("text",""))
        done   = t.get("done", False)
        due    = escape(t.get("due",""))
        recur  = t.get("recurring", False)
        strike = "text-decoration:line-through;color:var(--ink-faint);" if done else ""
        rb     = (
            '<span style="font-size:0.65em;background:#fef3c7;color:#92400e;'
            'padding:1px 5px;border-radius:6px;margin-left:4px;">\u21bb</span>'
        ) if recur else ""
        task_rows += (
            '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;'
            'border-bottom:1px solid var(--border-light);">'
            '<input type="checkbox" ' + ("checked " if done else "") +
            'onchange="toggleWeekTask(' + str(i) + ',this)" '
            'style="width:16px;height:16px;flex-shrink:0;">'
            '<span style="flex:1;font-size:0.85em;' + strike + '">' + txt + rb + '</span>'
            '<span style="font-size:0.72em;color:var(--brown);font-weight:600;">' + due + '</span>'
            '<button onclick="makeTaskRecurring(' + str(i) + ')" title="Make recurring" '
            'style="background:none;border:none;color:var(--ink-faint);cursor:pointer;font-size:0.82em;">\u21bb</button>'
            '<button onclick="deleteWeekTask(' + str(i) + ')" '
            'style="background:none;border:none;color:var(--ink-faint);cursor:pointer;">&times;</button>'
            '</div>'
        )

    # 5. School + Meals
    school_html = ""
    try:
        from render_kids_week import load_week_plan
        from config import child_color as _cc
        kplan = load_week_plan(week_key)
        for child in CHILDREN:
            c_bg  = _cc(child, "bg")
            cdata = kplan.get("children", {}).get(child, {})
            total = sum(len(cdata.get("days", {}).get(d, {}).get("subjects", []))
                        for d in ["Monday","Tuesday","Wednesday","Thursday","Friday"])
            school_html += (
                '<div style="display:flex;justify-content:space-between;align-items:center;'
                'padding:4px 0;border-bottom:1px solid var(--border-light);">'
                '<span style="font-size:0.85em;font-weight:600;color:' + c_bg + ';">' + escape(child) + '</span>'
                '<span style="font-size:0.78em;color:var(--ink-muted);">'
                + ("Not planned" if total == 0 else str(total) + " subject-days") +
                '</span>'
                '<a href="/kids-week?week=' + escape(week_key) + '" '
                'style="font-size:0.72em;color:var(--brown);font-weight:600;text-decoration:none;">'
                + ("Plan \u2192" if total == 0 else "Edit \u2192") + '</a>'
                '</div>'
            )
    except Exception:
        school_html = '<p style="font-size:0.82em;color:var(--ink-faint);">School plan unavailable.</p>'

    meal_html = ""
    try:
        from render_meals import load_meal_plan, slot_display_text
        mplan = load_meal_plan(week_key)
        for d in wdates[:5]:
            dn     = d.strftime("%A")
            meals  = mplan.get("days", {}).get(dn, {})
            dinner = slot_display_text(meals.get("Dinner") or meals.get("dinner"))
            col    = "var(--ink)" if dinner else "var(--ink-faint)"
            meal_html += (
                '<div style="display:flex;gap:8px;align-items:baseline;padding:4px 0;'
                'border-bottom:1px solid var(--border-light);">'
                '<span style="font-size:0.72em;font-weight:700;color:var(--ink-faint);width:32px;">'
                + d.strftime("%a") + '</span>'
                '<span style="font-size:0.82em;color:' + col + ';">'
                + (escape(dinner) if dinner else "not planned") + '</span>'
                '</div>'
            )
    except Exception:
        meal_html = '<p style="font-size:0.82em;color:var(--ink-faint);">Meal plan unavailable.</p>'

    # 6. Plan items
    saved_briefing = intentions.get("ai_briefing", "")
    saved_items    = intentions.get("plan_items", [])
    plan_items_html = ""
    for pi, item in enumerate(saved_items):
        txt      = escape(item.get("text",""))
        included = item.get("included", True)
        cat_tag  = escape(item.get("category",""))
        plan_items_html += (
            '<div id="pitem-' + str(pi) + '" '
            'style="display:flex;align-items:flex-start;gap:8px;padding:7px 10px;'
            'border-radius:8px;margin-bottom:5px;'
            'background:' + ('#f0fdf4' if included else '#fafafa') + ';'
            'border:1px solid ' + ('#bbf7d0' if included else 'var(--border-light)') + ';">'
            '<input type="checkbox" ' + ("checked " if included else "") +
            'onchange="togglePlanItem(' + str(pi) + ',this)" '
            'style="width:16px;height:16px;accent-color:#22c55e;flex-shrink:0;margin-top:2px;">'
            '<div style="flex:1;">'
            '<div style="font-size:0.85em;' +
            ('color:var(--ink)' if included else 'color:var(--ink-faint);text-decoration:line-through') +
            ';">' + txt + '</div>'
            + ('<div style="font-size:0.68em;color:var(--ink-faint);margin-top:2px;">' + cat_tag + '</div>' if cat_tag else '')
            + '</div>'
            '<button onclick="deletePlanItem(' + str(pi) + ')" '
            'style="background:none;border:none;color:var(--ink-faint);cursor:pointer;">&times;</button>'
            '</div>'
        )

    ai_section = ""
    if api_key:
        brief_btn_text = "Regenerate briefing \u21bb" if saved_briefing else "\u2728 Brief me on this week"
        saved_brief_html = ""
        if saved_briefing and not plan_items_html:
            saved_brief_html = (
                '<div style="margin-top:10px;padding:10px 12px;background:#faf8f5;'
                'border-radius:8px;font-size:0.82em;line-height:1.65;color:var(--ink);">'
                + escape(saved_briefing) + '</div>'
            )
        ai_section = (
            '<div class="card" style="margin-bottom:16px;">'
            '<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;'
            'text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;">'
            '\u2728 AI Weekly Briefing</div>'
            + ('<div style="margin-bottom:12px;">' + plan_items_html + '</div>' if plan_items_html else "")
            + '<button onclick="aiBrief()" '
            'style="width:100%;padding:11px;'
            'background:linear-gradient(135deg,#1c1610,#2a1e10);'
            'color:var(--gold-light);border:none;border-radius:10px;font-size:0.88em;'
            'font-weight:600;font-family:inherit;cursor:pointer;">'
            + brief_btn_text + '</button>'
            '<div id="ai-brief-loading" style="display:none;text-align:center;'
            'padding:12px;font-size:0.82em;color:var(--ink-faint);">'
            '\u231b Generating your briefing...</div>'
            '<div id="ai-brief-result" style="display:none;"></div>'
            + saved_brief_html +
            '</div>'
        )

    # Children options for recurring modal
    child_opts = "\n".join(
        '<option value="' + escape(c) + '">' + escape(c) + '</option>'
        for c in CHILDREN
    )

    intentions_js   = json.dumps(intentions)
    active_goals_js = json.dumps([
        {"id": g["id"], "title": g["title"], "step": g.get("step","")}
        for g in active_goals
    ])

    # ── SaintMaker: Weekly Examination ───────────────────────────────────────
    exam_data = intentions.get("examination", {})
    exam_rows = ""
    for key, label, question in EXAM_QUESTIONS:
        val  = escape(exam_data.get(key, ""))
        opts = "".join(
            '<option value="{v}"{s}>{v}</option>'.format(
                v=v, s=' selected' if val == v else ''
            ) for v in ["", "Yes", "Mostly", "Sometimes", "No"]
        )
        exam_rows += (
            '<div style="padding:9px 0;border-bottom:1px solid var(--border-light);">'
            '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
            '<div style="flex:1;min-width:160px;">'
            '<div style="font-size:0.72em;font-weight:700;color:var(--brown);">' + escape(label) + '</div>'
            '<div style="font-size:0.82em;color:var(--ink);margin-top:1px;">' + escape(question) + '</div>'
            '</div>'
            '<select onchange="saveExam(\'' + key + '\',this.value)" '
            'style="padding:5px 8px;border:1.5px solid var(--border);border-radius:8px;'
            'font-size:0.82em;font-family:inherit;min-width:100px;">'
            + opts + '</select></div></div>'
        )
    mass_int = escape(intentions.get("mass_intention", ""))
    exam_html = (
        '<div class="card" style="margin-bottom:14px;">'
        '<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;'
        'color:var(--ink-faint);margin-bottom:4px;">✦ Weekly Examination</div>'
        '<div style="font-size:0.75em;color:var(--ink-faint);font-style:italic;margin-bottom:10px;">'
        'Stewardship of God\'s gifts this past week</div>'
        + exam_rows +
        '<div style="margin-top:12px;">'
        '<label style="font-size:0.75em;font-weight:700;color:var(--brown);">Sunday Mass Intention</label>'
        '<input type="text" id="mass-intention" value="' + mass_int + '" '
        'placeholder="Whom or what will you offer this Mass for?" '
        'onchange="autoSave()" '
        'style="margin-top:4px;padding:7px 10px;font-size:0.85em;border-radius:8px;'
        'border:1.5px solid var(--border);font-family:inherit;width:100%;box-sizing:border-box;">'
        '</div></div>'
    )

    # ── SaintMaker: Weekly 3 ─────────────────────────────────────────────────
    w3_data = intentions.get("weekly_3", ["", "", ""])
    if not isinstance(w3_data, list) or len(w3_data) < 3:
        w3_data = ["", "", ""]
    w3_rows = ""
    for i in range(3):
        w3_rows += (
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
            '<div style="width:22px;height:22px;border-radius:50%;background:var(--ink);'
            'color:var(--gold-light);display:flex;align-items:center;justify-content:center;'
            'font-size:0.78em;font-weight:700;flex-shrink:0;">' + str(i + 1) + '</div>'
            '<input type="text" id="w3-' + str(i) + '" value="' + escape(w3_data[i]) + '" '
            'placeholder="Priority ' + str(i + 1) + '..." onchange="autoSave()" '
            'style="flex:1;padding:7px 10px;font-size:0.85em;border-radius:8px;'
            'border:1.5px solid var(--border);font-family:inherit;">'
            '</div>'
        )

    # ── SaintMaker: Four Quadrants ───────────────────────────────────────────
    quad_data = intentions.get("quadrants", {})
    quad_html_inner = ""
    for key, label, hint in QUADRANT_LABELS:
        val = escape(quad_data.get(key, ""))
        quad_html_inner += (
            '<div>'
            '<div style="font-size:0.72em;font-weight:700;color:var(--brown);margin-bottom:3px;">'
            + escape(label) +
            '<span style="font-weight:400;color:var(--ink-faint);margin-left:4px;">' + escape(hint) + '</span>'
            '</div>'
            '<textarea id="quad-' + key + '" rows="3" onchange="autoSave()" '
            'placeholder="What matters here this week?" '
            'style="width:100%;padding:7px 10px;font-size:0.82em;border-radius:8px;'
            'border:1.5px solid var(--border);font-family:inherit;resize:vertical;box-sizing:border-box;">'
            + val + '</textarea>'
            '</div>'
        )

    weekly3_quadrants_html = (
        '<div class="card" style="margin-bottom:14px;">'
        '<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;'
        'color:var(--ink-faint);margin-bottom:10px;">✦ Weekly 3 — This Week\'s Priorities</div>'
        + w3_rows +
        '</div>'
        '<div class="card" style="margin-bottom:14px;">'
        '<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;'
        'color:var(--ink-faint);margin-bottom:10px;">✦ Four Quadrants</div>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">'
        + quad_html_inner +
        '</div></div>'
    )

    # ── SaintMaker: Blessings + Improvements ─────────────────────────────────
    blessings_val    = escape(intentions.get("blessings", ""))
    improvements_val = escape(intentions.get("improvements", ""))
    blessings_html = (
        '<div class="card" style="margin-bottom:14px;">'
        '<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;'
        'color:var(--ink-faint);margin-bottom:10px;">✦ Blessings &amp; Improvements</div>'
        '<label style="font-size:0.75em;">In what ways did God bless your life and work this week?</label>'
        '<textarea id="week-blessings" rows="3" onchange="autoSave()" '
        'style="width:100%;padding:7px 10px;font-size:0.85em;border-radius:8px;'
        'border:1.5px solid var(--border);font-family:inherit;resize:vertical;box-sizing:border-box;margin-bottom:10px;">'
        + blessings_val + '</textarea>'
        '<label style="font-size:0.75em;">Improvements — How could you grow next week? (Review Weekly 3 and goals)</label>'
        '<textarea id="week-improvements" rows="3" onchange="autoSave()" '
        'style="width:100%;padding:7px 10px;font-size:0.85em;border-radius:8px;'
        'border:1.5px solid var(--border);font-family:inherit;resize:vertical;box-sizing:border-box;">'
        + improvements_val + '</textarea>'
        '</div>'
    )

    # ── Pre-computed one-liners to avoid backslash-in-f-string issues ─────────
    review_btn_html = (
        '<button onclick="aiWeeklyReview(this)" style="padding:7px 14px;background:var(--parchment);'
        'border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;font-weight:600;'
        'font-family:inherit;cursor:pointer;">\u2728 Weekly review</button>'
        if api_key else ''
    )
    ai_review_div = (
        '<div id="ai-review-result" style="display:none;margin-bottom:16px;padding:14px;'
        'background:white;border-radius:12px;border:1px solid var(--border-light);"></div>'
        if api_key else ''
    )

    # ── Weeks remaining in quarter ────────────────────────────────────────────
    weeks_left = max(0, 13 - wk_num)
    wk_color = "#22c55e" if weeks_left >= 8 else "#f59e0b" if weeks_left >= 4 else "#ef4444"
    weeks_remaining_html = (
        '<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;'
        'background:var(--parchment);border-radius:10px;margin-bottom:14px;">'
        '<div style="font-size:1.8rem;font-weight:700;color:' + wk_color + ';">' + str(weeks_left) + '</div>'
        '<div>'
        '<div style="font-size:0.78em;font-weight:700;color:var(--ink);">Weeks remaining in this season</div>'
        '<div style="font-size:0.7em;color:var(--ink-faint);">Week ' + str(wk_num) + ' of 13 · '
        + ('Make them count.' if weeks_left <= 4 else 'Steady and faithful.') + '</div>'
        '</div>'
        '<div style="flex:1;height:6px;background:#e5e7eb;border-radius:3px;margin-left:8px;">'
        '<div style="width:' + str(round(wk_num / 13 * 100)) + '%;height:100%;'
        'background:' + wk_color + ';border-radius:3px;"></div>'
        '</div>'
        '</div>'
    )

    body = top_nav() + render_status_message(status) + f"""
<div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:8px;padding-top:4px;margin-bottom:16px;">
  <div>
    <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:2rem;font-weight:600;color:var(--ink);">Plan My Week</div>
    <div style="font-size:0.85em;color:var(--ink-muted);margin-top:2px;">{escape(week_label)} &middot; Q-Week {wk_num}</div>
  </div>
  <div style="display:flex;gap:6px;flex-wrap:wrap;">
    <a href="/plan-week?week={escape(prev_key)}" style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);">&larr;</a>
    <a href="/plan-week" style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);">This week</a>
    <a href="/plan-week?week={escape(next_key)}" style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);">&rarr;</a>
    <button onclick="saveAll()" style="padding:7px 16px;background:var(--ink);color:var(--gold-light);border:none;border-radius:8px;font-size:0.82em;font-weight:700;font-family:inherit;cursor:pointer;">Save</button>
    {review_btn_html}
  </div>
</div>
<div id="save-status" style="font-size:0.82em;color:#22c55e;min-height:16px;margin-bottom:8px;"></div>
{ai_review_div}

{weeks_remaining_html}

<div class="card" style="margin-bottom:14px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;">Week at a Glance</div>
  <div style="display:flex;gap:6px;overflow-x:auto;">{day_cols}</div>
</div>

{exam_html}

<div style="margin-bottom:14px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:10px;display:flex;justify-content:space-between;">
    <span>Goal Steps This Week</span>
    <a href="/plan-quarter" style="font-size:0.9em;font-weight:600;color:var(--brown);text-decoration:none;text-transform:none;">Manage goals &rarr;</a>
  </div>
  {goal_rows}
</div>

<div class="card" style="margin-bottom:14px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:12px;">Intentions &amp; Mindset</div>
  <label style="font-size:0.75em;">Most important thing this week</label>
  <input type="text" id="int-important" value="{mi}" placeholder="The one thing that matters most..." onchange="autoSave()" style="margin-bottom:10px;">
  <label style="font-size:0.75em;">What I will protect</label>
  <input type="text" id="int-protect" value="{pt}" placeholder="Morning prayer, quiet time..." onchange="autoSave()" style="margin-bottom:10px;">
  <label style="font-size:0.75em;">What I can let go</label>
  <input type="text" id="int-letgo" value="{lg}" placeholder="What doesn't have to be perfect..." onchange="autoSave()">
</div>

{weekly3_quadrants_html}

<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px;">
  <div class="card">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;">School</div>
    {school_html}
    <a href="/kids-week?week={escape(week_key)}" style="font-size:0.75em;color:var(--brown);font-weight:600;text-decoration:none;display:block;margin-top:8px;">Full planner &rarr;</a>
  </div>
  <div class="card">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;">Meals</div>
    {meal_html}
    <a href="/meals" style="font-size:0.75em;color:var(--brown);font-weight:600;text-decoration:none;display:block;margin-top:8px;">Meal planner &rarr;</a>
  </div>
</div>

<div class="card" style="margin-bottom:14px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;">Weekly Tasks</div>
  <div id="wtask-list">{task_rows if task_rows else '<p style="font-size:0.82em;color:var(--ink-faint);">No tasks yet.</p>'}</div>
  <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;">
    <input type="text" id="new-wtask" placeholder="Add a task..." onkeydown="if(event.key==='Enter')addWeekTask()" style="flex:1;min-width:160px;padding:7px 10px;font-size:0.85em;border-radius:8px;border:1.5px solid var(--border);font-family:inherit;">
    <select id="new-wtask-due" style="padding:7px 10px;font-size:0.82em;border-radius:8px;border:1.5px solid var(--border);font-family:inherit;">
      <option value="">Any day</option>
      <option>Monday</option><option>Tuesday</option><option>Wednesday</option>
      <option>Thursday</option><option>Friday</option><option>Saturday</option>
    </select>
    <button onclick="addWeekTask()" style="padding:7px 14px;background:var(--ink);color:var(--gold-light);border:none;border-radius:8px;font-size:0.82em;font-family:inherit;cursor:pointer;font-weight:600;">+ Add</button>
  </div>
</div>

{blessings_html}

{ai_section}

<div id="recur-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:1000;align-items:center;justify-content:center;padding:20px;">
  <div style="background:white;border-radius:14px;padding:22px;max-width:360px;width:100%;">
    <div style="font-weight:700;margin-bottom:14px;">&#8635; Make Recurring Task</div>
    <div id="recur-task-name" style="font-size:0.88em;color:var(--ink-muted);margin-bottom:12px;padding:8px 10px;background:var(--parchment);border-radius:8px;"></div>
    <label style="font-size:0.75em;">First due date</label>
    <input type="date" id="recur-due" style="margin-bottom:10px;">
    <label style="font-size:0.75em;">Repeat</label>
    <div style="display:flex;gap:8px;margin-bottom:10px;align-items:center;">
      <span id="recur-every-lbl" style="font-size:0.82em;white-space:nowrap;">every</span>
      <input type="number" id="recur-iv" value="1" min="1" style="width:60px;margin-bottom:0;font-size:0.85em;">
      <select id="recur-iu" style="flex:1;margin-bottom:0;font-size:0.85em;"
              onchange="(function(s){{var n=document.getElementById('recur-iv'),lbl=document.getElementById('recur-every-lbl');var p=['monthly_last_sat','monthly_last_sun','monthly_last_fri','monthly_first_sat','monthly_first_sun','monthly_first_fri'].includes(s.value);n.style.display=p?'none':'';lbl.style.display=p?'none':'';}})(this)">
        <option value="days">Days</option>
        <option value="weeks" selected>Weeks</option>
        <option value="months">Months (same date)</option>
        <optgroup label="── Monthly patterns ──">
        <option value="monthly_last_sat">Last Saturday of each month</option>
        <option value="monthly_last_sun">Last Sunday of each month</option>
        <option value="monthly_last_fri">Last Friday of each month</option>
        <option value="monthly_first_sat">First Saturday of each month</option>
        <option value="monthly_first_sun">First Sunday of each month</option>
        <option value="monthly_first_fri">First Friday of each month</option>
        </optgroup>
      </select>
    </div>
    <label style="font-size:0.75em;">Assign to</label>
    <select id="recur-assign" style="margin-bottom:14px;font-size:0.85em;">
      <option value="">Anyone</option><option value="Mom">Mom</option>
      {child_opts}
    </select>
    <div style="display:flex;gap:8px;">
      <button onclick="confirmRecurring()" style="flex:1;padding:9px;background:var(--ink);color:var(--gold-light);border:none;border-radius:8px;font-family:inherit;font-weight:600;cursor:pointer;">Create task</button>
      <button onclick="closeRecurModal()" style="padding:9px 16px;background:transparent;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;cursor:pointer;">Cancel</button>
    </div>
  </div>
</div>

<div style="display:flex;gap:8px;flex-wrap:wrap;padding:8px 0;">
  <a href="/plan-month" style="font-size:0.82em;color:var(--brown);font-weight:700;text-decoration:none;">Monthly plan &rarr;</a>
  <span style="color:var(--border);">|</span>
  <a href="/plan-year" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">Annual overview &rarr;</a>
  <span style="color:var(--border);">|</span>
  <a href="/plan-quarter" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">Quarterly goals &rarr;</a>
</div>

<script>
var _wk = '{escape(week_key)}';
var _qk = '{escape(quarter_key)}';
var _qwk = {wk_num};
var _intentions = {intentions_js};
var _aGoals = {active_goals_js};
var _saveTimer = null;
var _recurTarget = null;
if (!_intentions.weekly_tasks)  _intentions.weekly_tasks  = [];
if (!_intentions.plan_items)    _intentions.plan_items    = [];
if (!_intentions.examination)   _intentions.examination   = {{}};
if (!_intentions.weekly_3)      _intentions.weekly_3      = ['','',''];
if (!_intentions.quadrants)     _intentions.quadrants     = {{}};
if (!_intentions.blessings)     _intentions.blessings     = '';
if (!_intentions.improvements)  _intentions.improvements  = '';
if (!_intentions.mass_intention) _intentions.mass_intention = '';

function autoSave() {{ clearTimeout(_saveTimer); _saveTimer = setTimeout(saveAll, 1200); }}

function saveExam(key, val) {{
  _intentions.examination[key] = val;
  autoSave();
}}

function saveAll() {{
  _intentions.most_important  = document.getElementById('int-important') ? document.getElementById('int-important').value || '' : _intentions.most_important;
  _intentions.protect         = document.getElementById('int-protect')   ? document.getElementById('int-protect').value   || '' : _intentions.protect;
  _intentions.let_go          = document.getElementById('int-letgo')     ? document.getElementById('int-letgo').value     || '' : _intentions.let_go;
  _intentions.mass_intention  = document.getElementById('mass-intention') ? document.getElementById('mass-intention').value || '' : _intentions.mass_intention;
  var w3 = [];
  for (var i = 0; i < 3; i++) {{
    var el = document.getElementById('w3-' + i);
    w3.push(el ? el.value || '' : (_intentions.weekly_3[i] || ''));
  }}
  _intentions.weekly_3 = w3;
  ['domestic','vocation','spiritual','recreation'].forEach(function(q) {{
    var el = document.getElementById('quad-' + q);
    if (el) _intentions.quadrants[q] = el.value || '';
  }});
  var bl = document.getElementById('week-blessings');
  var im = document.getElementById('week-improvements');
  if (bl) _intentions.blessings    = bl.value || '';
  if (im) _intentions.improvements = im.value || '';
  fetch('/plan-week-save', {{
    method:'POST', headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'week='+encodeURIComponent(_wk)+'&data='+encodeURIComponent(JSON.stringify(_intentions))
  }}).then(function() {{
    var el=document.getElementById('save-status');
    if(el){{el.textContent='Saved \u2713';setTimeout(function(){{el.textContent=''}},2000);}}
  }});
}}

function saveGoalStep(gid) {{
  var inp=document.getElementById('gstep-'+gid);
  if(!inp)return;
  fetch('/quarter-save-step',{{
    method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'quarter='+encodeURIComponent(_qk)+'&goal_id='+encodeURIComponent(gid)+'&week='+_qwk+'&step='+encodeURIComponent(inp.value)
  }});
}}

function goalCheckin(gid,status) {{
  fetch('/quarter-checkin',{{
    method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'quarter='+encodeURIComponent(_qk)+'&goal_id='+encodeURIComponent(gid)+'&week='+_qwk+'&status='+encodeURIComponent(status)
  }}).then(function() {{
    var colors={{done:'#22c55e',partial:'#f59e0b',skip:'#ef4444'}};
    var row=document.getElementById('grow-'+gid);
    if(!row)return;
    row.querySelectorAll('button[onclick*="goalCheckin"]').forEach(function(btn) {{
      var m=btn.getAttribute('onclick').match(new RegExp("'([^']+)'\\)"));
      if(m){{var isA=(m[1]===status);btn.style.background=isA?(colors[m[1]]||'var(--parchment)'):'var(--parchment)';btn.style.color=isA?'white':'var(--ink-muted)';}}
    }});
  }});
}}

function addWeekTask() {{
  var inp=document.getElementById('new-wtask');
  var due=document.getElementById('new-wtask-due');
  if(!inp||!inp.value.trim())return;
  _intentions.weekly_tasks.push({{text:inp.value.trim(),due:due?due.value:'',done:false,recurring:false}});
  inp.value='';
  rebuildTaskList();autoSave();
}}

function toggleWeekTask(idx,cb) {{
  if(_intentions.weekly_tasks[idx])_intentions.weekly_tasks[idx].done=cb.checked;
  rebuildTaskList();autoSave();
}}

function deleteWeekTask(idx) {{
  _intentions.weekly_tasks.splice(idx,1);
  rebuildTaskList();autoSave();
}}

function rebuildTaskList() {{
  var el=document.getElementById('wtask-list');
  if(!el)return;
  var tasks=_intentions.weekly_tasks;
  if(tasks.length===0){{el.innerHTML='<p style="font-size:0.82em;color:var(--ink-faint);">No tasks yet.</p>';return;}}
  el.innerHTML=tasks.map(function(t,i){{
    var strike=t.done?'text-decoration:line-through;color:var(--ink-faint);':'';
    var rb=t.recurring?'<span style="font-size:0.65em;background:#fef3c7;color:#92400e;padding:1px 5px;border-radius:6px;margin-left:4px;">&#8635;</span>':'';
    return '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border-light);">'
      +'<input type="checkbox"'+(t.done?' checked':'')+' onchange="toggleWeekTask('+i+',this)" style="width:16px;height:16px;flex-shrink:0;">'
      +'<span style="flex:1;font-size:0.85em;'+strike+'">'+t.text+rb+'</span>'
      +'<span style="font-size:0.72em;color:var(--brown);font-weight:600;">'+(t.due||'')+'</span>'
      +'<button onclick="makeTaskRecurring('+i+')" style="background:none;border:none;color:var(--ink-faint);cursor:pointer;font-size:0.82em;">&#8635;</button>'
      +'<button onclick="deleteWeekTask('+i+')" style="background:none;border:none;color:var(--ink-faint);cursor:pointer;">&times;</button>'
      +'</div>';
  }}).join('');
}}

function togglePlanItem(idx,cb) {{
  if(_intentions.plan_items[idx])_intentions.plan_items[idx].included=cb.checked;
  autoSave();
}}

function deletePlanItem(idx) {{
  _intentions.plan_items.splice(idx,1);autoSave();location.reload();
}}

function aiBrief() {{
  var loading=document.getElementById('ai-brief-loading');
  var result=document.getElementById('ai-brief-result');
  if(loading)loading.style.display='block';
  if(result)result.style.display='none';
  var payload={{week:_wk,quarter:_qk,quarter_week:_qwk,goals:_aGoals,
    important:document.getElementById('int-important').value||'',
    protect:document.getElementById('int-protect').value||'',
    let_go:document.getElementById('int-letgo').value||''}};
  fetch('/ai-week-brief',{{
    method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'data='+encodeURIComponent(JSON.stringify(payload))
  }}).then(function(r){{return r.json();}}).then(function(d){{
    if(loading)loading.style.display='none';
    if(d.items&&Array.isArray(d.items)){{
      _intentions.ai_briefing=d.briefing||'';
      _intentions.plan_items=d.items.map(function(it){{return {{text:it.text,category:it.category||'',included:true}};}});
      autoSave();
    }}
    if(result){{
      result.style.display='block';
      var html='';
      if(d.briefing)html+='<div style="padding:10px 12px;background:#faf8f5;border-radius:8px;font-size:0.85em;line-height:1.65;color:var(--ink);margin-bottom:10px;">'+d.briefing.replace(/\n/g,'<br>')+'</div>';
      if(d.items&&d.items.length>0){{
        html+='<div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:6px;">Select items to add to your plan</div>';
        d.items.forEach(function(item,i){{
          html+='<div style="display:flex;align-items:flex-start;gap:8px;padding:7px 10px;border-radius:8px;margin-bottom:5px;background:#f0fdf4;border:1px solid #bbf7d0;">'
            +'<input type="checkbox" checked onchange="togglePlanItem('+i+',this)" style="width:16px;height:16px;accent-color:#22c55e;margin-top:2px;flex-shrink:0;">'
            +'<div><div style="font-size:0.85em;color:var(--ink);">'+item.text+'</div>'
            +(item.category?'<div style="font-size:0.68em;color:var(--ink-faint);margin-top:1px;">'+item.category+'</div>':'')
            +'</div></div>';
        }});
      }}
      result.innerHTML=html;
    }}
  }}).catch(function(){{
    if(loading)loading.style.display='none';
    if(result){{result.style.display='block';result.textContent='Error \u2014 check API key.';}}
  }});
}}

function makeRecurring(goalId) {{
  var goal=_aGoals.find(function(g){{return g.id===goalId;}});
  var step=document.getElementById('gstep-'+goalId);
  _recurTarget={{type:'goal',id:goalId,text:step?step.value:(goal?goal.title:'')}};
  _openRecurModal(_recurTarget.text);
}}
function makeTaskRecurring(idx) {{
  var task=_intentions.weekly_tasks[idx];
  if(!task)return;
  _recurTarget={{type:'task',idx:idx,text:task.text}};
  _openRecurModal(task.text);
}}
function _openRecurModal(text) {{
  var modal=document.getElementById('recur-modal');
  var name=document.getElementById('recur-task-name');
  if(name)name.textContent=text;
  var due=document.getElementById('recur-due');
  if(due){{var next=new Date();next.setDate(next.getDate()+(8-next.getDay())%7||7);due.value=next.toISOString().split('T')[0];}}
  if(modal)modal.style.display='flex';
}}
function closeRecurModal() {{
  var modal=document.getElementById('recur-modal');
  if(modal)modal.style.display='none';
  _recurTarget=null;
}}
function confirmRecurring() {{
  if(!_recurTarget)return;
  var text=_recurTarget.text;
  var due=document.getElementById('recur-due').value;
  var iv=document.getElementById('recur-iv').value;
  var iu=document.getElementById('recur-iu').value;
  var assign=document.getElementById('recur-assign').value;
  fetch('/add-task',{{
    method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'text='+encodeURIComponent(text)+'&recurring=true&due_date='+encodeURIComponent(due)
      +'&interval_value='+encodeURIComponent(iv)+'&interval_unit='+encodeURIComponent(iu)
      +'&assigned_to='+encodeURIComponent(assign)+'&priority=MEDIUM&return_url=/plan-week'
  }}).then(function(){{
    closeRecurModal();
    var el=document.getElementById('save-status');
    if(el){{el.textContent='Recurring task created \u2713';setTimeout(function(){{el.textContent=''}},2500);}}
  }});
}}
function aiWeeklyReview(btn) {{
  var result = document.getElementById('ai-review-result');
  if (!result) return;
  btn.disabled = true; btn.textContent = '\u2728 Thinking\u2026';
  result.style.display = 'block';
  result.innerHTML = '<div style="font-size:0.85em;color:var(--ink-faint);">\u2728 Asking Claude to review your week\u2026</div>';
  fetch('/ai-weekly-review', {{
    method:'POST', headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'week_key={escape(week_key)}'
  }}).then(function(r){{return r.json();}}).then(function(d){{
    result.innerHTML = d.html || '<p>No response.</p>';
    btn.disabled = false; btn.textContent = '\u2728 Weekly review';
  }}).catch(function(){{
    result.innerHTML = '<p style="color:#ef4444;">Error \u2014 check connection.</p>';
    btn.disabled = false;
  }});
}}
</script>
"""
    return html_page("Plan My Week \u00b7 " + week_label, body)