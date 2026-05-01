"""
render_misc.py — Dashboard, Mom page, Notes, Tasks, Roadmap, Planner, School, History.
Imports from: config, data_helpers, ui_helpers, and other render_* modules.
"""
import uuid
from datetime import date, timedelta
from html import escape

from daily_schedule_engine import CHILDREN, build_schedule_payload, generate_day_packet
from notes_router import add_note, archive_note, load_notes, route_note_text
from school_pdf_engine import (
    approve_school_preview, extract_pdf_text,
    load_school_preview, load_school_previews, load_school_weeks,
    parse_school_pdf_text, save_school_preview,
)

from config import (
    child_color, parent_color, ASSIGNABLE_TO, ROADMAP_STATUSES, WEEKDAYS, WEEKDAY_ORDER, MONTH_NAMES,
)
from data_helpers import (
    load_manual_tasks, save_manual_tasks, active_manual_tasks,
    load_mom_notes, save_mom_notes,
    load_roadmap, save_roadmap,
    load_monthly_planner,
    count_school_check_items, sort_school_days, is_math_subject, is_math_test_text,
    normalize_date_query, clean_status, list_snapshots,
    load_thankyou_reminders, save_thankyou_reminders,
    pending_thankyou_reminders, due_thankyou_reminders,
)
from ui_helpers import html_page, page_header, render_status_message, top_nav

# Imported from other render modules
from render_schedule import (
    is_day_complete, count_remaining, render_task_list,
    render_day_nav,
)
from render_schedule_support import (
    render_now_next_strip, render_today_timeline, render_litany_block,
)
from render_calendar import render_calendar_today_strip
from render_liturgical import (
    render_liturgical_day_card, get_day_info, get_vestment_color, is_penance_season,
)
from render_chores import render_van_roles_card
from render_daily_bar import render_daily_bar
from render_daily_plan import render_plan_editor, render_add_to_plan_btn, render_dashboard_plan
from render_daily_plan import render_dashboard_grid
from render_ai_planner import render_ai_panel
from render_morning_anchor import render_morning_anchor, render_evening_anchor
from render_settings import load_app_settings, _school_mode_section


def _safe_widget(module_name: str, func_name: str) -> str:
    """Safely call a dashboard widget — returns '' if module not yet uploaded."""
    try:
        mod = __import__(module_name, fromlist=[func_name])
        return getattr(mod, func_name)()
    except Exception:
        return ''


# ── Monthly planner helpers ───────────────────────────────────────────────────
def get_this_month_data() -> dict:
    planner    = load_monthly_planner()
    month_name = date.today().strftime("%B")
    month_data  = planner.get("months", {}).get(month_name, {})
    every_month = planner.get("every_month", {})
    return {
        "month_name":    month_name,
        "month_data":    month_data,
        "every_month":   every_month,
        "penance_chores": planner.get("penance_time_chores", []) if is_penance_season() else [],
        "litany":        planner.get("litany_to_begin_again", []),
    }


def render_month_summary_card() -> str:
    data        = get_this_month_data()
    month_name  = data["month_name"]
    month_data  = data["month_data"]
    every_month = data["every_month"]
    task_count    = len(month_data.get("tasks",[])) + len(every_month.get("tasks",[]))
    garden_count  = len(month_data.get("garden",[]))
    penance_count = len(data["penance_chores"])
    antiphon      = month_data.get("marian_antiphon","")
    von_trapp     = month_data.get("von_trapp","")
    antiphon_html  = f"<p class='small' style='margin-top:6px;'>🎵 {escape(antiphon)}</p>" if antiphon else ""
    von_trapp_html = f"<p class='small'>📖 Von Trapp: {escape(von_trapp)}</p>" if von_trapp else ""
    penance_html   = f"<span class='badge' style='background:#f0e8f5;'>Penance chores: {penance_count}</span>" if penance_count else ""
    return f"""
    <div class="card" style="border-left:4px solid #8b5a3c;">
        <h3>🗓 {escape(month_name)}</h3>
        <div class="summary-row">
            <span class="badge">Tasks: {task_count}</span>
            <span class="badge">Garden: {garden_count}</span>
            {penance_html}
        </div>
        {antiphon_html}{von_trapp_html}
        <div class="link-row"><a class="link-button" href="/planner">Open Planner</a></div>
    </div>"""


def render_planner_page(status_message: str = "") -> str:
    data           = get_this_month_data()
    month_name     = data["month_name"]
    month_data     = data["month_data"]
    every_month    = data["every_month"]
    penance_chores = data["penance_chores"]
    antiphon = month_data.get("marian_antiphon",""); von_trapp = month_data.get("von_trapp",""); lit_notes = month_data.get("liturgical_notes","")
    def add_btn(task, icon=""):
        t = escape(task)
        return f"""
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid #f5f0eb;">
            <span style="font-size:0.95em;">{icon}{t}</span>
            <form method="POST" action="/planner-add-task" style="flex-shrink:0;">
                <input type="hidden" name="text" value="{t}">
                <button type="submit" style="padding:4px 10px;font-size:0.8em;background:#f0ebe4;color:#7c4a2d;border:1px solid #d7cec5;border-radius:6px;cursor:pointer;font-weight:600;">+ Add to Tasks</button>
            </form>
        </div>"""
    tasks_html    = "".join(add_btn(t)         for t in every_month.get("tasks",[]) + month_data.get("tasks",[]))
    garden_html   = "".join(add_btn(t,"🌱 ")   for t in month_data.get("garden",[]))
    penance_html  = "".join(add_btn(t,"✝ ")    for t in penance_chores)
    links_html    = ""
    for link in every_month.get("links",[]):
        n = escape(link.get("name","")); u = link.get("url","")
        links_html += f"<div style='margin-bottom:6px;'><a href='{escape(u)}' target='_blank' class='link-button'>{n} ↗</a></div>" if u else f"<div style='margin-bottom:6px;color:#888;font-size:0.9em;'>{n}</div>"
    lit_html = ""
    if antiphon: lit_html += f"<p><strong>🎵 Marian Antiphon:</strong> {escape(antiphon)}</p>"
    if von_trapp: lit_html += f'<p><strong>📖 Von Trapp:</strong> Listen to "{escape(von_trapp)}" in Around the Year</p>'
    if lit_notes: lit_html += f"<p class='small'>{escape(lit_notes)}</p>"
    month_links = " · ".join(f"<a href='/planner?month={m}'>{m[:3]}</a>" for m in MONTH_NAMES)

    # Pre-compute conditional HTML blocks — no nested f-strings allowed in f"""..."""
    _lit_block     = (
        '<div class="card" style="border-left:4px solid #6b3fa0;">'
        '<h3>\u271d Liturgical Living</h3>' + lit_html + '</div>'
        if lit_html else ""
    )
    _penance_block = (
        '<div class="card" style="border-left:4px solid #6b3fa0;">'
        '<h3>\u271d Penance Time Chores</h3>'
        '<p class="small">These appear during Lent and Advent.</p>'
        + penance_html + '</div>'
        if penance_html else ""
    )
    _garden_block  = (
        '<div class="card" style="border-left:4px solid #27ae60;">'
        '<h3>\U0001f331 Garden</h3>' + garden_html + '</div>'
        if garden_html else ""
    )
    _planner_header = page_header(f"Monthly Planner \u2014 {month_name}")
    _tasks_empty    = "<p class='muted'>No tasks for this month.</p>"

    body = f"""
    {_planner_header}
    {render_status_message(status_message)}
    <p class="small" style="margin-bottom:16px;">{month_links}</p>
    <div class="two-col">
        <div>
            {_lit_block}
            <div class="card">
                <h3>This Month's Reminders</h3>
                <p class="small" style="margin-bottom:10px;">Click "+ Add to Tasks" to send any item to your task list.</p>
                {tasks_html or _tasks_empty}
            </div>
            {_penance_block}
        </div>
        <div>
            {_garden_block}
            <div class="card"><h3>&#128203; Monthly Links to Check</h3>{links_html}</div>
        </div>
    </div>"""
    return html_page(f"Planner — {month_name}", body)


# ── Dashboard ─────────────────────────────────────────────────────────────────
def _render_mom_now_block(iso: str, weekday: str) -> str:
    """
    Compact Mom card showing:
    - What she's scheduled to do right now (family schedule)
    - Current Plan My Day step
    - Next task if schedule block is done
    - Active virtue + intention
    All compact, tap-through links to relevant pages.
    """
    from datetime import date as _date
    c_bg    = parent_color("Lauren", "bg")
    c_light = parent_color("Lauren", "light")

    # ── FROL: what's Mom doing right now ─────────────────────────────────────
    family_now = ""
    try:
        from render_schedule_support import (
            get_eastern_now, _slot_minutes, generate_half_hour_times
        )
        from data_helpers import get_frol_day_slots
        now      = get_eastern_now()
        now_min  = now.hour * 60 + now.minute
        times    = generate_half_hour_times()
        slots    = get_frol_day_slots(weekday, "Mom")
        cur_idx  = -1
        for i, t in enumerate(times):
            if _slot_minutes(t) <= now_min:
                cur_idx = i
        if cur_idx >= 0:
            cur_label  = times[cur_idx]
            family_now = slots.get(cur_label, "")
            if not family_now and cur_idx + 1 < len(times):
                family_now = slots.get(times[cur_idx + 1], "")
    except Exception:
        pass

    # ── Plan My Day: current step ─────────────────────────────────────────────
    current_step_label = ""
    current_step_id    = ""
    step_pct           = 0
    try:
        from render_daily_plan import load_daily_plan
        plan_data  = load_daily_plan(iso)
        anchor     = plan_data.get("anchor", {})
        launch     = anchor.get("launch", {})
        evening    = anchor.get("evening", {})
        eve_done   = sum(1 for k in ["dinner_cleanup","showers","clothes_out",
                                      "evening_prayer","marriage_window"]
                         if evening.get(k, False)) >= 3
        steps_def = [
            ("spiritual", "Spiritual"),
            ("cycle",     "Cycle"),
            ("meals",     "Meals"),
            ("calendar",  "Calendar"),
            ("tasks",     "Tasks"),
            ("kidsday",   "Kids' Day"),
            ("evening",   "Evening"),
            ("grid",      "Done"),
        ]
        # Find first incomplete step
        for sid, slabel in steps_def:
            if sid == "evening" and eve_done:
                continue
            current_step_id    = sid
            current_step_label = slabel
            break
        step_pct = round(
            sum(1 for sid, _ in steps_def
                if (sid == "evening" and eve_done)) / len(steps_def) * 100
        )
    except Exception:
        pass

    # ── Next task from task list ──────────────────────────────────────────────
    next_task_text = ""
    try:
        from data_helpers import active_manual_tasks
        tasks = [t for t in active_manual_tasks()
                 if t.get("assigned_to","").lower() in ("mom","") or not t.get("assigned_to")]
        if tasks:
            tasks.sort(key=lambda t: (t.get("due_date","") or "9999",
                                       {"HIGH":0,"MEDIUM":1,"LOW":2}.get(t.get("priority","MEDIUM"),1)))
            next_task_text = tasks[0].get("text","")
    except Exception:
        pass

    # ── Decide what to show as primary action ─────────────────────────────────
    # Priority: family_now → plan step → next task
    primary_label = ""
    primary_link  = "/mom"
    primary_icon  = "📋"

    if family_now:
        primary_label = family_now
        primary_icon  = "🕐"
        primary_link  = "/mom"
    elif current_step_label:
        primary_label = f"Step: {current_step_label}"
        primary_icon  = "📋"
        primary_link  = f"/mom#{current_step_id}"
    elif next_task_text:
        primary_label = next_task_text
        primary_icon  = "✓"
        primary_link  = "/tasks"

    # ── Virtue ───────────────────────────────────────────────────────────────
    virtue_text    = ""
    intention_text = ""
    try:
        from render_virtues import load_personal_virtue
        pv = load_personal_virtue() or {}
        cur = pv.get("current") or {}
        virtue_text    = cur.get("virtue", "")
        intention_text = cur.get("content", {}).get("daily_prompt", "")
    except Exception:
        pass

    # ── 5AM status ────────────────────────────────────────────────────────────
    club_done = []
    try:
        from render_5am import load_day
        today_rec = load_day(_date.today())
        for sec, lbl in [("move","Move"),("reflect","Reflect"),("grow","Grow")]:
            if today_rec.get(sec, {}).get("done"):
                club_done.append(lbl)
    except Exception:
        pass

    # ── Build card ────────────────────────────────────────────────────────────
    # Plan My Day step chips (compact)
    step_chips = ""
    step_short = [
        ("spiritual","🙏"),("cycle","🌙"),("meals","🍽"),
        ("calendar","📆"),("tasks","✓"),("kidsday","👦"),
        ("evening","🌙"),("grid","✅"),
    ]
    for sid, icon in step_short:
        is_current = (sid == current_step_id)
        is_done    = False
        try:
            if sid == "evening":
                is_done = eve_done
        except Exception:
            pass
        bg  = c_bg if is_current else ("#dcfce7" if is_done else "var(--parchment)")
        col = "white" if is_current else ("#166534" if is_done else "var(--ink-faint)")
        step_chips += (
            f'<a href="/mom#{escape(sid)}" '
            f'style="display:inline-flex;align-items:center;justify-content:center;'
            f'width:26px;height:26px;border-radius:6px;font-size:0.85em;'
            f'background:{bg};color:{col};text-decoration:none;" '
            f'title="{escape(sid.capitalize())}">{icon}</a>'
        )

    # 5AM dots
    club_html = ""
    if club_done or True:
        for sec, lbl in [("Move","💪"),("Reflect","🙏"),("Grow","📖")]:
            done = sec in club_done
            col  = "#22c55e" if done else "#e5e7eb"
            club_html += (
                f'<span title="{lbl}" '
                f'style="font-size:0.75em;opacity:{"1" if done else "0.4"};">{lbl}</span>'
            )

    # Virtue pill
    virtue_html = ""
    if virtue_text:
        intention_html = (
            '<div style="font-size:0.75em;color:var(--ink-muted);'
            'line-height:1.4;font-style:italic;">'
            + escape(intention_text[:80])
            + ('\u2026' if len(intention_text) > 80 else '')
            + '</div>'
        ) if intention_text else ''
        virtue_html = (
            '<div style="margin-top:8px;padding:6px 10px;'
            'background:rgba(139,90,60,0.08);border-radius:8px;'
            'border-left:3px solid var(--brown);">'
            '<div style="font-size:0.68em;font-weight:800;text-transform:uppercase;'
            'letter-spacing:.08em;color:var(--brown);margin-bottom:2px;">'
            '\u271d ' + escape(virtue_text) + '</div>'
            + intention_html
            + '</div>'
        )

    # ── Current capacity from anchor state ───────────────────────────────────
    capacity = ""
    try:
        from render_morning_anchor import _get_anchor_state
        anchor   = _get_anchor_state(iso)
        capacity = anchor.get("capacity", "")
    except Exception:
        pass

    # Check if API key available for AI popup
    api_key = ""
    try:
        settings = load_app_settings()
        api_key  = (settings.get("anthropic_api_key","") or
                    settings.get("family_constraints",{}).get("anthropic_api_key",""))
    except Exception:
        pass

    # ── Build capacity buttons ────────────────────────────────────────────────
    cap_buttons = ""
    for cap, color, emoji in [
        ("High",   "#27ae60", "🟢"),
        ("Medium", "#e67e22", "🟡"),
        ("Low",    "#e74c3c", "🔴"),
    ]:
        is_active = (cap == capacity)
        bg  = color if is_active else "var(--parchment)"
        col = "white" if is_active else "var(--ink-muted)"
        brd = color if is_active else "var(--border)"
        cap_buttons += (
            f'<button onclick="momSetCap(\'{escape(cap)}\',\'{color}\')" '
            f'id="mom-cap-{escape(cap)}" '
            f'style="padding:4px 10px;font-size:0.72em;font-weight:700;'
            f'border:none;border-radius:16px;cursor:pointer;white-space:nowrap;'
            f'font-family:inherit;background:{bg};color:{col};">'
            f'{escape(cap)}</button>'
        )

    # Current capacity label for display
    cap_color_map = {"High":"#27ae60","Medium":"#e67e22","Low":"#e74c3c"}
    cap_display = ""
    if capacity:
        cap_color = cap_color_map.get(capacity, "var(--ink-faint)")
        cap_display = (
            f'<span id="mom-cap-label" style="font-size:0.68em;font-weight:700;color:{cap_color};">'
            f'\u25cf {escape(capacity)} capacity</span>'
        )

    return (
        f'<div style="border-radius:16px;border:1px solid var(--border);'
        f'overflow:hidden;margin-bottom:10px;background:white;">'

        # Card top section
        f'<div style="padding:12px 14px;border-bottom:1px solid var(--border-light);">'

        # Header row
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'margin-bottom:10px;">'
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<div style="width:36px;height:36px;border-radius:50%;'
        f'background:{c_bg};color:white;'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-family:\'Cormorant Garamond\',Georgia,serif;'
        f'font-size:1.15rem;font-weight:600;flex-shrink:0;">L</div>'
        f'<span style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        f'font-size:1.1em;font-weight:600;color:var(--ink);">Lauren</span>'
        f'</div>'
        # Capacity pill selector (High / Med / Low)
        f'<div style="display:flex;align-items:center;gap:2px;padding:3px;'
        f'background:var(--parchment);border:1px solid var(--border);border-radius:20px;">'
        f'{cap_buttons}'
        f'</div>'
        f'</div>'

        # AI confirmation popup (hidden)
        + f'<div id="mom-cap-popup" style="display:none;margin-bottom:10px;'
        f'padding:12px 14px;background:linear-gradient(135deg,#1c1610,#2a1e10);'
        f'border-radius:10px;">'
        f'<div id="mom-cap-loading" style="font-size:0.82em;color:rgba(245,234,216,0.7);">'
        f'✨ Thinking about your day...</div>'
        f'<div id="mom-cap-text" style="display:none;font-size:0.85em;'
        f'color:var(--gold-light);line-height:1.65;"></div>'
        f'<div id="mom-cap-actions" style="display:none;margin-top:10px;gap:8px;">'
        f'<button onclick="momCapConfirm()" '
        f'style="padding:6px 16px;background:#27ae60;color:white;border:none;'
        f'border-radius:8px;font-size:0.82em;font-family:inherit;cursor:pointer;font-weight:700;">'
        f'Apply ✓</button>'
        f'<button onclick="momCapDismiss()" '
        f'style="padding:6px 12px;background:transparent;'
        f'border:1px solid rgba(245,234,216,0.3);color:rgba(245,234,216,0.7);'
        f'border-radius:8px;font-size:0.82em;font-family:inherit;cursor:pointer;">'
        f'Cancel</button>'
        f'</div></div>'

        # Primary action
        + (
            f'<a href="{escape(primary_link)}" style="display:flex;align-items:center;'
            f'gap:8px;padding:8px 10px;background:var(--ink);border-radius:10px;'
            f'text-decoration:none;margin-bottom:8px;">'
            f'<span style="font-size:1em;">{primary_icon}</span>'
            f'<span style="font-size:0.88em;font-weight:600;color:var(--gold-light);">'
            f'{escape(primary_label)}</span>'
            f'</a>'
            if primary_label else
            f'<a href="/mom" style="display:flex;align-items:center;gap:8px;'
            f'padding:8px 10px;background:var(--ink);border-radius:10px;'
            f'text-decoration:none;margin-bottom:8px;">'
            f'<span style="font-size:0.88em;font-weight:600;color:var(--gold-light);">Open Plan My Day &rarr;</span>'
            f'</a>'
        )

        # Plan My Day step strip
        + f'<div style="display:flex;gap:4px;margin-bottom:8px;">{step_chips}</div>'

        # Lorenzo menu planning button
        + f'<a href="/lorenzo" style="display:flex;align-items:center;justify-content:center;gap:6px;'
        f'width:100%;padding:7px;border-radius:10px;font-size:0.75em;font-weight:600;'
        f'background:rgba(139,58,26,0.08);color:#8b3a1a;border:1px solid rgba(139,58,26,0.2);'
        f'text-decoration:none;margin-bottom:6px;box-sizing:border-box;">'
        f'&#128197; Plan this week\'s menu with Lorenzo</a>'

        # Plan Import button
        + f'<a href="/plan-import" style="display:flex;align-items:center;justify-content:center;gap:6px;'
        f'width:100%;padding:7px;border-radius:10px;font-size:0.75em;font-weight:600;'
        f'background:rgba(30,53,102,0.07);color:#1e3566;border:1px solid rgba(30,53,102,0.18);'
        f'text-decoration:none;margin-bottom:6px;box-sizing:border-box;">'
        f'&#128203; Plan Importer</a>'

        # Curriculum Importer button
        + f'<a href="/curriculum" style="display:flex;align-items:center;justify-content:center;gap:6px;'
        f'width:100%;padding:7px;border-radius:10px;font-size:0.75em;font-weight:600;'
        f'background:rgba(124,58,237,0.07);color:#5b21b6;border:1px solid rgba(124,58,237,0.22);'
        f'text-decoration:none;margin-bottom:8px;box-sizing:border-box;">'
        f'&#128218; MODG Curriculum Importer</a>'

        # 5AM + quick links row
        + f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">'
        f'<div style="display:flex;gap:4px;">{club_html}</div>'
        f'<div style="display:flex;gap:8px;">'
        f'<a href="/prayer" style="font-size:0.7em;color:{c_bg};text-decoration:none;font-weight:600;">Prayer</a>'
        f'<a href="/5am" style="font-size:0.7em;color:{c_bg};text-decoration:none;font-weight:600;">5AM</a>'
        f'<a href="/virtues/me" style="font-size:0.7em;color:{c_bg};text-decoration:none;font-weight:600;">Virtue</a>'
        f'</div></div>'

        # AI action buttons — 3-column tile grid
        + (f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:4px;">'
           f'<button onclick="momAiCall(\'schedule\',this)" '
           f'style="display:flex;flex-direction:column;align-items:center;gap:5px;padding:10px 4px;'
           f'border:1px solid var(--border);border-radius:10px;background:var(--parchment);'
           f'color:var(--ink);font-size:0.7em;font-weight:600;font-family:inherit;cursor:pointer;">'
           f'<span style="font-size:1.4em;">📅</span>Plan my day</button>'
           f'<button onclick="momAiCall(\'school\',this)" '
           f'style="display:flex;flex-direction:column;align-items:center;gap:5px;padding:10px 4px;'
           f'border:1px solid var(--border);border-radius:10px;background:var(--parchment);'
           f'color:var(--ink);font-size:0.7em;font-weight:600;font-family:inherit;cursor:pointer;">'
           f'<span style="font-size:1.4em;">📚</span>School</button>'
           f'<button onclick="momAiCall(\'examen\',this)" '
           f'style="display:flex;flex-direction:column;align-items:center;gap:5px;padding:10px 4px;'
           f'border:1px solid var(--border);border-radius:10px;background:var(--parchment);'
           f'color:var(--ink);font-size:0.7em;font-weight:600;font-family:inherit;cursor:pointer;">'
           f'<span style="font-size:1.4em;">🌙</span>Examen</button>'
           f'</div>'
           f'<div id="mom-ai-result" style="display:none;margin-top:8px;padding:10px 12px;'
           f'background:white;border-radius:10px;border:1px solid var(--border-light);"></div>'
           if api_key else '')

        # Close card-top section
        + f'</div>'

        # Virtue footer strip (parchment background, only if virtue set)
        + (
            f'<div style="padding:10px 14px;background:{c_light};'
            f'border-top:1px solid var(--border-light);display:flex;gap:8px;align-items:flex-start;">'
            f'<span style="color:{c_bg};margin-top:1px;">&#8224;</span>'
            f'<div>'
            f'<div style="font-size:0.65em;font-weight:800;text-transform:uppercase;'
            f'letter-spacing:.08em;color:{c_bg};margin-bottom:2px;">{escape(virtue_text)}</div>'
            + (f'<div style="font-size:0.75em;color:var(--ink-muted);font-style:italic;line-height:1.4;">'
               + escape(intention_text[:90]) + ('\u2026' if len(intention_text) > 90 else '')
               + '</div>' if intention_text else '')
            + f'</div></div>'
            if virtue_text else ''
        )

        # Capacity JS
        + f'''<script>
var _momIso     = '{escape(iso)}';
var _momCap     = '{escape(capacity)}';
var _momHasAI   = {'true' if api_key else 'false'};
var _pendingCap = null;

var CAP_MESSAGES = {{
  High:   "You\u2019re at full capacity today \u2014 lean into the full rhythm. Take on school, chores, and your regular responsibilities with confidence.",
  Medium: "Moderate capacity today \u2014 protect your essentials and let the rest flex. Focus on what only you can do and delegate or defer the rest.",
  Low:    "Low capacity today \u2014 give yourself real grace. Simplify to just what truly matters: the kids are fed, loved, and learning something. Everything else can wait."
}};

function momSetCap(cap, color) {{
  _pendingCap = cap;

  // Update button styles immediately
  var colors = {{High:'#27ae60', Medium:'#e67e22', Low:'#e74c3c'}};
  ['High','Medium','Low'].forEach(function(c) {{
    var btn = document.getElementById('mom-cap-' + c);
    if (!btn) return;
    btn.style.background  = (c === cap) ? colors[c] : 'var(--parchment)';
    btn.style.color       = (c === cap) ? 'white'   : 'var(--ink-muted)';
    btn.style.borderColor = (c === cap) ? colors[c] : 'var(--border)';
  }});

  // Always show popup
  var popup   = document.getElementById('mom-cap-popup');
  var loading = document.getElementById('mom-cap-loading');
  var text    = document.getElementById('mom-cap-text');
  var actions = document.getElementById('mom-cap-actions');
  if (!popup) return;

  popup.style.display   = 'block';
  loading.style.display = 'block';
  text.style.display    = 'none';
  text.innerHTML        = '';
  actions.style.display = 'none';

  if (_momHasAI) {{
    fetch('/ai-capacity-preview', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
      body: 'iso=' + encodeURIComponent(_momIso) + '&capacity=' + encodeURIComponent(cap)
    }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
      loading.style.display = 'none';
      text.style.display    = 'block';
      text.innerHTML        = d.preview || CAP_MESSAGES[cap] || ('Capacity set to ' + cap + '.');
      actions.style.display = 'flex';
    }}).catch(function() {{
      loading.style.display = 'none';
      text.style.display    = 'block';
      text.innerHTML        = CAP_MESSAGES[cap] || ('Capacity set to ' + cap + '.');
      actions.style.display = 'flex';
    }});
  }} else {{
    // No API key — show built-in message immediately
    loading.style.display = 'none';
    text.style.display    = 'block';
    text.innerHTML        = CAP_MESSAGES[cap] || ('Capacity set to ' + cap + '.');
    actions.style.display = 'flex';
  }}
}}

function momCapConfirm() {{
  if (!_pendingCap) return;
  fetch('/anchor-save', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'iso=' + encodeURIComponent(_momIso) +
          '&data=' + encodeURIComponent(JSON.stringify({{capacity: _pendingCap}}))
  }}).then(function() {{
    _momCap     = _pendingCap;
    _pendingCap = null;
    // Update header label
    var cap_colors = {{High:'#27ae60', Medium:'#e67e22', Low:'#e74c3c'}};
    var label = document.getElementById('mom-cap-label');
    if (label) {{
      label.textContent = '\u25cf ' + _momCap + ' capacity';
      label.style.color = cap_colors[_momCap] || 'var(--ink-faint)';
    }}
    momCapDismiss();
  }});
}}

function momAiCall(type, btn) {{
  var result = document.getElementById('mom-ai-result');
  if (!result) return;
  btn.disabled = true;
  btn.textContent = '\u2728 Thinking\u2026';
  result.style.display = 'block';
  result.innerHTML = '<div style="font-size:0.82em;color:var(--ink-faint);">\u2728 Asking Claude\u2026</div>';

  var endpoints = {{
    schedule: '/ai-daily-schedule',
    school:   '/ai-school-plan',
    examen:   '/ai-evening-examen'
  }};
  var url = endpoints[type] || '/ai-daily-schedule';
  var now = new Date();
  var wd = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][now.getDay()];
  var body = 'iso=' + encodeURIComponent(_momIso)
           + '&capacity=' + encodeURIComponent(_momCap)
           + '&weekday=' + encodeURIComponent(wd);

  fetch(url, {{method:'POST', headers:{{'Content-Type':'application/x-www-form-urlencoded'}}, body:body}})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      var labels = {{schedule:'\u2728 Plan my day', school:'\u2728 School plan', examen:'\u2728 Evening examen'}};
      btn.disabled = false;
      btn.textContent = labels[type] || '\u2728 Done';
      if (d.html) {{
        result.innerHTML = d.html;
        result.style.display = 'block';
      }} else {{
        result.innerHTML = '<p style="color:#ef4444;font-size:0.85em;">No response \u2014 check that your API key is saved in Settings and that render_ai_daily.py is uploaded to Replit.</p>';
        result.style.display = 'block';
      }}
    }}).catch(function(e) {{
      result.innerHTML = '<p style="color:#ef4444;font-size:0.85em;">Network error \u2014 check connection and API key in Settings.</p>';
      result.style.display = 'block';
      btn.disabled = false;
      btn.textContent = labels[type] || '\u2728 Try again';
    }});
}}
function momCapDismiss() {{
  var popup = document.getElementById('mom-cap-popup');
  if (popup) popup.style.display = 'none';
  if (!_pendingCap) return;
  // Restore buttons to last confirmed state
  var colors = {{High:'#27ae60', Medium:'#e67e22', Low:'#e74c3c'}};
  ['High','Medium','Low'].forEach(function(c) {{
    var btn = document.getElementById('mom-cap-' + c);
    if (!btn) return;
    btn.style.background  = (c === _momCap) ? colors[c] : 'var(--parchment)';
    btn.style.color       = (c === _momCap) ? 'white'   : 'var(--ink-muted)';
    btn.style.borderColor = (c === _momCap) ? colors[c] : 'var(--border)';
  }});
  _pendingCap = null;
}}
</script>'''
        f'</div>'
    )


def _render_boys_now_blocks(iso: str, weekday: str) -> str:
    """
    Per-child dashboard blocks showing what each child should be doing right now,
    with checkboxes for their current tasks. Tapping opens their full schedule.
    """
    try:
        from daily_schedule_engine import build_schedule_payload
        from render_schedule import _item_done
        from data_helpers import load_progress
        from render_schedule_support import get_current_slot, _slot_minutes, get_eastern_now
        from data_helpers import get_frol_day_slots
    except Exception:
        return ""

    try:
        now         = get_eastern_now()
        now_min     = now.hour * 60 + now.minute
        date_label  = now.strftime("%B %-d")
        progress    = load_progress()
        from render_schedule_support import generate_half_hour_times
        times       = generate_half_hour_times()

        # Find current time slot
        cur_idx = -1
        for i, t in enumerate(times):
            if _slot_minutes(t) <= now_min:
                cur_idx = i
        cur_label = times[cur_idx] if cur_idx >= 0 else ""
    except Exception:
        cur_label  = ""
        progress   = {}
        date_label = ""

    cards = ""
    for child in CHILDREN:
        c_bg    = child_color(child, "bg")
        c_light = child_color(child, "light")
        c_id    = escape(child)

        try:
            payload = build_schedule_payload(child, weekday, date_label, iso)
        except Exception:
            payload = {}

        # Gather all tasks for today
        all_items = []
        for block in payload.get("school_blocks", []):
            for item in block.get("items", []):
                item["_block"] = block.get("subject","")
                all_items.append(item)
        all_items.extend(payload.get("chore_items", []))
        all_items.extend(payload.get("manual_task_items", []))
        all_items.extend(payload.get("carryover_items", []))

        total    = len(all_items)
        done_cnt = sum(1 for i in all_items if _item_done(i, progress))
        pct      = round(done_cnt / total * 100) if total else 0
        all_done = (total > 0 and done_cnt == total)

        # Current activity from family schedule
        family_now = ""
        if cur_label and today_slots:
            family_now = today_slots.get(cur_label, "")

        # Build full task list grouped by section
        if all_done:
            status_line = (
                f'<div style="font-size:0.78em;font-weight:700;color:#166534;'
                f'background:#dcfce7;padding:3px 8px;border-radius:8px;display:inline-block;">'
                f'\u2713 All done!</div>'
            )
        elif not all_items:
            status_line = f'<div style="font-size:0.82em;color:var(--ink-faint);">No tasks assigned.</div>'
        else:
            status_line = ""
            # School blocks
            school_blocks = payload.get("school_blocks", [])
            if school_blocks:
                status_line += (
                    f'<div style="font-size:0.65em;font-weight:800;letter-spacing:.08em;'
                    f'text-transform:uppercase;color:{c_bg};margin:6px 0 3px;">School</div>'
                )
                for block in school_blocks:
                    subj  = escape(block.get("subject",""))
                    items = block.get("items", [])
                    if items:
                        status_line += (
                            f'<div style="font-size:0.72em;font-weight:700;color:var(--ink-muted);'
                            f'margin:4px 0 2px 2px;">{subj}</div>'
                        )
                        for item in items:
                            tid_raw  = item.get("task_id","")
                            tid_html = escape(tid_raw, quote=False)
                            tid_js   = tid_html.replace("'", "\\'")
                            is_done  = _item_done(item, progress)
                            checked  = "checked" if is_done else ""
                            txt      = escape(item.get("text","") or subj)
                            done_sty = "opacity:0.45;text-decoration:line-through;" if is_done else ""
                            data_done = "1" if is_done else "0"
                            status_line += (
                                f'<div id="task-{tid_html}" data-done="{data_done}" '
                                f'style="display:flex;align-items:flex-start;gap:6px;'
                                f'padding:2px 0 2px 6px;">'
                                f'<label class="dl-label" style="font-size:0.82em;color:var(--ink);{done_sty};flex:1;">{txt}</label>'
                                f'<input type="checkbox" {checked} '
                                f'onchange="dashBoyToggle(this,\'{tid_js}\',\'{c_id}\')" '
                                f'style="accent-color:{c_bg};flex-shrink:0;margin-left:6px;">'
                                f'</div>'
                            )
                    else:
                        # No items — just the subject as a checkbox
                        status_line += (
                            f'<div style="display:flex;align-items:center;gap:6px;padding:2px 0 2px 2px;">'
                            f'<span style="flex:1;font-size:0.82em;color:var(--ink);">{subj}</span>'
                            f'<input type="checkbox" style="accent-color:{c_bg};flex-shrink:0;">'
                            f'</div>'
                        )

            # Chores + tasks
            other_items = payload.get("chore_items", []) + payload.get("manual_task_items", []) + payload.get("carryover_items", [])
            if other_items:
                status_line += (
                    f'<div style="font-size:0.65em;font-weight:800;letter-spacing:.08em;'
                    f'text-transform:uppercase;color:{c_bg};margin:6px 0 3px;">Chores &amp; Tasks</div>'
                )
                for item in other_items[:8]:
                    _raw_tid  = item.get("task_id","") if isinstance(item,dict) else ""
                    tid_html  = escape(_raw_tid, quote=False)
                    tid_js    = tid_html.replace("'", "\\'")
                    is_done   = _item_done(item, progress)
                    checked   = "checked" if is_done else ""
                    txt       = escape(item.get("text","") if isinstance(item,dict) else str(item))
                    done_sty  = "opacity:0.45;text-decoration:line-through;" if is_done else ""
                    data_done = "1" if is_done else "0"
                    id_attr   = f'id="task-{tid_html}" data-done="{data_done}" ' if tid_html else ""
                    onchange  = (
                        f'onchange="dashBoyToggle(this,\'{tid_js}\',\'{c_id}\')"'
                        if tid_html else ""
                    )
                    status_line += (
                        f'<div {id_attr}style="display:flex;align-items:flex-start;gap:6px;'
                        f'padding:2px 0 2px 2px;">'
                        f'<label class="dl-label" style="font-size:0.82em;color:var(--ink);{done_sty};flex:1;">{txt}</label>'
                        f'<input type="checkbox" {checked} {onchange}'
                        f' style="accent-color:{c_bg};flex-shrink:0;margin-left:6px;">'
                        f'</div>'
                    )

        # Family schedule "now" line
        family_line = ""
        if family_now:
            family_line = (
                f'<div style="font-size:0.75em;color:{c_bg};font-weight:600;'
                f'margin-bottom:4px;">'
                f'Now: {escape(family_now)}</div>'
            )

        # Progress bar
        bar_col = "#22c55e" if all_done else ("#f59e0b" if pct >= 50 else c_bg)
        prog_bar = (
            f'<div style="height:4px;background:var(--border-light);'
            f'border-radius:2px;margin:8px 0 4px;">'
            f'<div style="height:4px;background:{bar_col};border-radius:2px;'
            f'width:{pct}%;transition:width 0.3s;"></div></div>'
            f'<div style="display:flex;justify-content:space-between;">'
            f'<div style="font-size:0.65em;color:var(--ink-faint);">{done_cnt}/{total} tasks</div>'
            f'<div style="font-size:0.65em;color:{bar_col};font-weight:700;">{pct}%</div>'
            f'</div>'
        ) if total > 0 else ""

        cards += (
            f'<div style="border-radius:12px;border:1px solid var(--border);'
            f'border-top:3px solid {c_bg};padding:9px 11px;'
            f'background:white;overflow:hidden;">'
            f'<div style="display:flex;align-items:center;'
            f'justify-content:space-between;margin-bottom:5px;">'
            f'<div style="display:flex;align-items:center;gap:5px;">'
            f'<span style="width:7px;height:7px;border-radius:50%;background:{c_bg};'
            f'display:inline-block;flex-shrink:0;"></span>'
            f'<div style="font-weight:700;font-size:0.88em;color:var(--ink);">{c_id}</div>'
            f'</div>'
            f'<a href="/schedule/{c_id}?date={escape(iso)}" '
            f'style="font-size:0.68em;color:var(--ink-faint);font-weight:600;text-decoration:none;">'
            f'Schedule &rarr;</a>'
            f'</div>'
            f'{family_line}'
            f'{prog_bar}'
            f'{status_line}'
            f'</div>'
        )

    if not cards:
        return ""

    return f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;">{cards}</div>'


def __render_meal_card_safe(target_date=None) -> str:
    try:
        from render_meals import render_meal_today_card
        return render_meal_today_card(target_date)
    except Exception:
        return ""


def _render_mom_messages_inbox() -> str:
    """Show messages from the boys — only for admin users (Lauren/John)."""
    try:
        import auth as _a
        viewer = _a.get_viewer()
        if not viewer or not _a.is_admin(viewer):
            return ""
        msgs = _a.load_messages()
        if not msgs:
            return ""
        msgs = list(reversed(msgs))  # newest first
        unread = [m for m in msgs if not m.get("read", False)]
        rows = ""
        for m in msgs[:10]:
            is_new = not m.get("read", False)
            color  = _a.USERS.get(m.get("from", ""), {}).get("color", "#6b7280")
            name   = escape(m.get("from_name", "?"))
            text   = escape(m.get("text", ""))
            ts     = m.get("timestamp", "")[:16].replace("T", " ")
            dot    = f'<span style="width:8px;height:8px;border-radius:50%;background:{color};display:inline-block;margin-right:6px;flex-shrink:0;"></span>' if is_new else '<span style="width:8px;margin-right:6px;display:inline-block;"></span>'
            rows += (
                f'<div style="display:flex;align-items:flex-start;gap:0;padding:10px 14px;'
                f'border-bottom:1px solid #f3f4f6;background:{"#fef9ff" if is_new else "white"};">'
                f'{dot}'
                f'<div style="flex:1;">'
                f'<div style="font-size:0.82em;font-weight:700;color:{color};">{name}</div>'
                f'<div style="font-size:0.88em;color:#374151;margin:2px 0 4px;">{text}</div>'
                f'<div style="font-size:0.72em;color:#9ca3af;">{ts}</div>'
                f'</div></div>'
            )
        mark_btn = ""
        if unread:
            mark_btn = (
                f'<form method="POST" action="/messages-read" style="display:inline;">'
                f'<button style="background:none;border:none;color:#7c3aed;font-size:0.8em;'
                f'cursor:pointer;font-family:inherit;text-decoration:underline;">Mark all read</button>'
                f'</form>'
            )
        cnt_label = f'{len(unread)} new · ' if unread else ''
        return (
            f'<div id="mom-messages" class="card" style="padding:0;overflow:hidden;margin-bottom:18px;">'
            f'<div style="padding:12px 16px;background:#f9fafb;border-bottom:1px solid #e5e7eb;'
            f'display:flex;align-items:center;justify-content:space-between;">'
            f'<div style="font-size:0.82em;font-weight:700;color:#7c3aed;">&#128140; Messages from the boys</div>'
            f'<span style="font-size:0.75em;color:#9ca3af;">{cnt_label}{len(msgs)} total &nbsp;{mark_btn}</span>'
            f'</div>'
            f'{rows}'
            f'</div>'
        )
    except Exception:
        return ""


def render_dashboard() -> str:
    from render_morning_anchor import (
        SEASON_QUOTES, _get_quote_for_day, fetch_this_day_in_history
    )
    from render_liturgical import get_day_info, get_vestment_color
    from render_schedule_support import get_eastern_now
    from datetime import datetime as _dt

    packet   = generate_day_packet("")
    iso      = packet["iso"]
    weekday  = packet["weekday"]
    today_d  = date.fromisoformat(iso)

    try:
        _now  = get_eastern_now()
    except Exception:
        _now  = _dt.now()
    _hour     = _now.hour
    _greeting = "Good morning" if _hour < 12 else ("Good afternoon" if _hour < 17 else "Good evening")

    # Liturgical info
    info              = get_day_info(today_d)
    season            = info.get("season", "Ordinary Time")
    feast             = info.get("feast_name", "")
    vest_bg, vest_txt = get_vestment_color(info)

    # Quote of the day
    quote, attrib = _get_quote_for_day(season, today_d)

    # Additional rotating scripture quotes for encouragement
    EXTRA_SCRIPTURE = [
        ("Be strong and courageous. Do not be afraid; do not be discouraged, for the Lord your God will be with you wherever you go.", "Joshua 1:9"),
        ("She is clothed with strength and dignity; she can laugh at the days to come.", "Proverbs 31:25"),
        ("I can do all this through him who gives me strength.", "Philippians 4:13"),
        ("Come to me, all you who are weary and burdened, and I will give you rest.", "Matthew 11:28"),
        ("The Lord is my shepherd; I shall not want.", "Psalm 23:1"),
        ("Trust in the Lord with all your heart and lean not on your own understanding.", "Proverbs 3:5"),
        ("For I know the plans I have for you, plans to prosper you and not to harm you.", "Jeremiah 29:11"),
        ("Be still and know that I am God.", "Psalm 46:10"),
        ("Her children arise and call her blessed; her husband also, and he praises her.", "Proverbs 31:28"),
        ("Whatever you do, work at it with all your heart, as working for the Lord.", "Colossians 3:23"),
        ("The fruit of the Spirit is love, joy, peace, patience, kindness, goodness, faithfulness.", "Galatians 5:22"),
        ("Commit to the Lord whatever you do, and he will establish your plans.", "Proverbs 16:3"),
        ("How beautiful is the home built on faith, where the table is a holy altar.", "Maria von Trapp"),
        ("A family is a little Church, a little kingdom of God.", "St. John Chrysostom"),
        ("Educate your children to be holy, that is the greatest gift you can give them.", "St. John Vianney"),
    ]
    extra_idx   = today_d.timetuple().tm_yday % len(EXTRA_SCRIPTURE)
    extra_q, extra_a = EXTRA_SCRIPTURE[extra_idx]

    # Rich saint data from Catholic Readings API
    try:
        from saint_data import get_saint_html_card, fetch_saint_data as _fsd
        _sd = _fsd(today_d)
        if _sd.get("name") and not feast:
            feast = _sd["name"]
        _saint_card  = get_saint_html_card(today_d, dark=True)
        _saint_quote = _sd.get("quote","")
        _saint_name  = _sd.get("name","")
    except Exception:
        _saint_card  = ""
        _saint_quote = ""
        _saint_name  = ""

    # Season badge
    season_badge = (
        f'<span style="display:inline-block;background:{vest_bg};color:{vest_txt};'
        f'border-radius:6px;padding:3px 10px;font-size:0.72em;font-weight:700;'
        f'letter-spacing:.06em;text-transform:uppercase;">{escape(season)}</span>'
    )

    # Feast / saint
    # Only show feast if it's an actual named feast, not just the season
    _feast_is_real = feast and feast.lower() not in (
        "lent", "advent", "christmas", "easter", "ordinary time",
        "holy week", "lenten season", "easter season"
    )
    if _feast_is_real:
        feast_html = (
            f'<div style="margin-top:6px;font-size:0.85em;font-weight:600;'
            f'color:rgba(245,234,216,0.9);">{escape(feast)}</div>'
        )
    else:
        feast_html = ""  # Season badge already shows the season

    # Readings link
    readings_url = (
        f"https://bible.usccb.org/bible/readings/{today_d.strftime('%m%d%y')}.cfm"
    )

    # Calendar events today
    try:
        cal_strip = render_calendar_today_strip(iso)
    except Exception:
        cal_strip = ""

    # Week strip
    from datetime import timedelta
    mon = today_d - timedelta(days=today_d.weekday())
    week_cells = ""
    for i in range(7):
        d = mon + timedelta(days=i)
        is_today = (d == today_d)
        lbl = d.strftime("%a").upper()
        num_style = (
            "background:var(--ink);color:var(--gold-light);border-radius:50%;"
            "width:30px;height:30px;display:flex;align-items:center;"
            "justify-content:center;font-weight:700;font-size:0.85em;"
            if is_today else
            "color:var(--ink-muted);width:30px;height:30px;display:flex;"
            "align-items:center;justify-content:center;font-size:0.85em;"
        )
        week_cells += (
            f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;">'
            f'<div style="font-size:9px;font-weight:700;letter-spacing:.06em;color:var(--ink-faint);">{lbl}</div>'
            f'<div style="{num_style}">{d.day}</div>'
            f'</div>'
        )

    # Family grid (published)
    try:
        _grid_html = render_dashboard_grid(iso)
    except Exception:
        _grid_html = ""

    # My plan
    try:
        plan_html = render_dashboard_plan(iso)
    except Exception:
        plan_html = ""

    # My plan
    try:
        plan_html = render_dashboard_plan(iso)
    except Exception:
        plan_html = ""

    # Pre-compute to avoid backslash-in-fstring
    _dash_saint_label = (
        f'<div style="font-size:0.7em;font-weight:700;letter-spacing:.1em;text-transform:uppercase;'
        f'color:rgba(245,234,216,0.5);margin-bottom:6px;">From {escape(_saint_name)}</div>'
        if _saint_quote else ""
    )

    # Daily Mass: liturgical week + collect prayer
    _mass_week_label = ""
    _collect_html    = ""
    _readings_url    = f"https://bible.usccb.org/bible/readings/{today_d.strftime('%m%d%y')}.cfm"
    try:
        from render_liturgical import get_moveable_feasts as _gmf
        from datetime import timedelta as _tdd
        _mv = _gmf(today_d.year)
        _mv_prev = _gmf(today_d.year - 1)

        def _find_feast(mv, feast_name):
            return next((d for d, v in mv.items() if v[0] == feast_name), None)

        _ash_wed = _find_feast(_mv, "Ash Wednesday")
        _easter  = _find_feast(_mv, "Easter Sunday")
        _advent1 = _find_feast(_mv, "First Sunday of Advent")
        _advent1_prev = _find_feast(_mv_prev, "First Sunday of Advent")

        _season_start = None
        if season == "Lent" and _ash_wed:
            _season_start = _ash_wed
        elif season == "Holy Week" and _easter:
            _season_start = _easter - _tdd(days=7)
        elif season == "Easter" and _easter:
            _season_start = _easter
        elif season == "Advent":
            if _advent1 and today_d >= _advent1:
                _season_start = _advent1
            elif _advent1_prev:
                _season_start = _advent1_prev
        elif season == "Christmas":
            import datetime as _dtt
            _season_start = _dtt.date(today_d.year, 12, 25)
        else:
            # Ordinary Time — approximate from Epiphany
            import datetime as _dtt
            _epiphany = _dtt.date(today_d.year, 1, 6)
            _season_start = _epiphany

        if _season_start and today_d >= _season_start:
            _week_num = (today_d - _season_start).days // 7 + 1
        else:
            _week_num = 1

        _ords = ["","First","Second","Third","Fourth","Fifth","Sixth","Seventh",
                 "Eighth","Ninth","Tenth","Eleventh","Twelfth","Thirteenth",
                 "Fourteenth","Fifteenth","Sixteenth","Seventeenth","Eighteenth",
                 "Nineteenth","Twentieth","Twenty-First","Twenty-Second",
                 "Twenty-Third","Twenty-Fourth","Twenty-Fifth","Twenty-Sixth",
                 "Twenty-Seventh","Twenty-Eighth","Twenty-Ninth","Thirtieth",
                 "Thirty-First","Thirty-Second","Thirty-Third","Thirty-Fourth"]
        _ord = _ords[_week_num] if 0 < _week_num < len(_ords) else str(_week_num)
        _lect_year   = ["C","A","B"][today_d.year % 3]
        _mass_week_label = f"{_ord} Week of {season} \u00b7 Year {_lect_year}"

        COLLECTS = {
            "Lent": (
                "Grant, O Lord, that we may begin with holy fasting this campaign of Christian service, "
                "so that, as we take up battle against spiritual evils, we may be armed with weapons "
                "of self-restraint. Through our Lord Jesus Christ, your Son, who lives and reigns with "
                "you in the unity of the Holy Spirit, God, for ever and ever."
            ),
            "Advent": (
                "Grant your faithful, we pray, almighty God, the resolve to run forth to meet your Christ "
                "with righteous deeds at his coming, so that, gathered at his right hand, they may be "
                "worthy to possess the heavenly Kingdom. Through our Lord Jesus Christ, your Son."
            ),
            "Christmas": (
                "O God, who wonderfully created the dignity of human nature and still more wonderfully "
                "restored it, grant, we pray, that we may share in the divinity of Christ, who humbled "
                "himself to share in our humanity. Who lives and reigns with you."
            ),
            "Easter": (
                "O God, who on this day, through your Only Begotten Son, have conquered death and "
                "unlocked for us the path to eternity, grant, we pray, that we who keep the solemnity "
                "of the Lord's Resurrection may, through the renewal brought by your Spirit, "
                "rise up in the light of life."
            ),
            "Holy Week": (
                "Almighty ever-living God, who as an example of humility for the human race to follow "
                "caused our Savior to take flesh and submit to the Cross, graciously grant that we may "
                "heed his lesson of patient suffering and so merit a share in his Resurrection."
            ),
            "Ordinary Time": (
                "Grant us, O Lord our God, that we may honor you with all our mind, and love everyone "
                "in truth of heart. Through our Lord Jesus Christ, your Son, who lives and reigns with "
                "you in the unity of the Holy Spirit, God, for ever and ever."
            ),
        }
        _collect_text = COLLECTS.get(season, COLLECTS["Ordinary Time"])
        _collect_html = (
            '<div style="font-size:0.68em;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:rgba(201,164,74,0.6);margin-bottom:8px;">Collect</div>'
            '<div style="font-style:italic;font-size:0.88em;color:rgba(245,234,216,0.85);'
            'line-height:1.75;padding:12px 16px;background:rgba(255,255,255,0.05);'
            'border-radius:10px;border-left:3px solid rgba(201,164,74,0.5);">'
            + escape(_collect_text) +
            '</div>'
            '<div style="margin-top:10px;">'
            f'<a href="{_readings_url}" target="_blank" '
            'style="font-size:0.78em;color:rgba(245,234,216,0.65);'
            'border-bottom:1px solid rgba(201,164,74,0.3);text-decoration:none;">'
            'Full Mass readings \u2197</a>'
            '</div>'
        )
    except Exception:
        pass

    # Lucy banner greeting message (precomputed — no backslashes in f-string)
    if quote and attrib:
        _q80 = quote[:100] + ("\u2026" if len(quote) > 100 else "")
        _lucy_msg = f'\u201c{escape(_q80)}\u201d \u2014 {escape(attrib)}'
    elif _feast_is_real and feast:
        _lucy_msg = f'Today is {escape(feast)}. May the Lord bless your day.'
    else:
        _lucy_msg = f'Blessed {escape(weekday)} to the McAdams family. Ready to make today count?'

    body = f"""
    <!-- AI Companions strip -->
    <div style="margin:-4px -4px 0;padding:10px 16px 12px;background:#1C1917;
                border-bottom:1px solid rgba(255,255,255,0.08);">
      <div style="font-size:0.68em;letter-spacing:.04em;
                  color:rgba(245,240,232,0.5);margin-bottom:8px;">Your companions</div>
      <div style="display:flex;gap:6px;margin-bottom:6px;">
        <a href="/lucy"
           style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
                  padding:8px 6px;background:#5b3a8a;
                  color:rgba(245,240,232,1);border-radius:14px;text-decoration:none;">
          <span style="font-size:0.8em;font-weight:700;">✨ Lucy</span>
          <span style="font-size:0.65em;opacity:0.7;font-weight:400;margin-top:1px;">Companion</span>
        </a>
        <a href="/lorenzo"
           style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
                  padding:8px 6px;background:#8b3a1a;
                  color:rgba(245,240,232,1);border-radius:14px;text-decoration:none;">
          <span style="font-size:0.8em;font-weight:700;">&#127860; Lorenzo</span>
          <span style="font-size:0.65em;opacity:0.7;font-weight:400;margin-top:1px;">Chef</span>
        </a>
        <a href="/dev"
           style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
                  padding:8px 6px;background:#1e3a8a;
                  color:rgba(245,240,232,1);border-radius:14px;text-decoration:none;">
          <span style="font-size:0.8em;font-weight:700;">&#128187; Izzy</span>
          <span style="font-size:0.65em;opacity:0.7;font-weight:400;margin-top:1px;">Help Desk</span>
        </a>
      </div>
      <div style="display:flex;gap:6px;">
        <a href="/headmaster"
           style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
                  padding:8px 6px;background:#1e3566;
                  color:rgba(245,240,232,1);border-radius:14px;text-decoration:none;">
          <span style="font-size:0.8em;font-weight:700;">&#128218; Fr. Gregory</span>
          <span style="font-size:0.65em;opacity:0.7;font-weight:400;margin-top:1px;">School</span>
        </a>
        <a href="/coach"
           style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
                  padding:8px 6px;background:#1a6e3e;
                  color:rgba(245,240,232,1);border-radius:14px;text-decoration:none;">
          <span style="font-size:0.8em;font-weight:700;">&#128170; Coach</span>
          <span style="font-size:0.65em;opacity:0.7;font-weight:400;margin-top:1px;">Fitness</span>
        </a>
        <a href="/dr-monica"
           style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
                  padding:8px 6px;background:#8b3a5c;
                  color:rgba(245,240,232,1);border-radius:14px;text-decoration:none;">
          <span style="font-size:0.8em;font-weight:700;">&#127800; Dr. Monica</span>
          <span style="font-size:0.65em;opacity:0.7;font-weight:400;margin-top:1px;">Health</span>
        </a>
      </div>
      <div style="margin-top:6px;">
        <a href="/quest/" target="_blank"
           style="display:flex;align-items:center;justify-content:center;gap:8px;
                  padding:10px 14px;background:linear-gradient(135deg,#7c3a1a 0%,#b85c20 100%);
                  color:rgba(245,240,232,1);border-radius:14px;text-decoration:none;
                  font-weight:700;font-size:0.85em;letter-spacing:.03em;">
          <span style="font-size:1.1em;">&#9876;</span>
          Family Quest
          <span style="font-size:0.7em;opacity:0.75;font-weight:400;">Chores &amp; Rewards &#8599;</span>
        </a>
      </div>
    </div>

    <!-- Lucy Banner -->
    <div style="background:var(--parchment);
                border-bottom:1px solid var(--border-light);
                margin:-4px -4px 12px;padding:14px 16px 14px;">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
        <div style="width:44px;height:44px;border-radius:50%;flex-shrink:0;
                    background:{parent_color('Lauren','bg')};border:2px solid {parent_color('Lauren','bg')};
                    display:flex;align-items:center;justify-content:center;position:relative;">
          <span style="font-family:'Cormorant Garamond',Georgia,serif;
                       font-size:1.25rem;font-weight:600;color:white;">L</span>
          <div style="position:absolute;bottom:-1px;right:-1px;width:13px;height:13px;
                      border-radius:50%;background:#22c55e;
                      border:2px solid var(--bg,#fff);"></div>
        </div>
        <div>
          <div style="font-size:0.63em;font-weight:800;letter-spacing:.13em;
                      text-transform:uppercase;color:{parent_color('Lauren','bg')};margin-bottom:2px;">
            Lucy &middot; AI Family Companion
          </div>
          <h1 style="margin:0;font-family:'Cormorant Garamond',Georgia,serif;
                     font-size:2.25rem;font-weight:600;color:var(--ink);line-height:1.1;">
            {_greeting}.
          </h1>
          <div style="font-size:0.82em;color:var(--ink-muted);margin-top:2px;">
            {escape(weekday)} &middot; {escape(packet["date_label"])}
          </div>
        </div>
      </div>
      <div style="background:white;border:1px solid var(--border);border-radius:12px;
                  padding:12px 14px;position:relative;overflow:hidden;">
        <div style="position:absolute;left:0;top:0;bottom:0;width:3px;
                    background:var(--brown);border-radius:3px 0 0 3px;"></div>
        <div style="font-size:0.85em;color:var(--ink);line-height:1.6;
                    padding-left:10px;margin-bottom:10px;">
          {_lucy_msg}
        </div>
        <div style="display:flex;justify-content:flex-end;padding-left:10px;">
          <a href="/prayer" style="display:inline-flex;align-items:center;gap:4px;
             font-size:0.78em;font-weight:700;color:var(--brown);
             background:rgba(139,90,60,0.1);padding:5px 12px;border-radius:8px;
             text-decoration:none;">Prayer &rarr;</a>
        </div>
      </div>
    </div>

    <!-- Daily bar (weather + liturgy + Prayer link) -->
    {render_daily_bar()}

    <!-- Mom & Boys — Right Now -->
    <div style="font-size:0.68em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
                color:rgba(245,240,232,0.5);background:#1C1917;
                padding:6px 14px;margin:-4px -4px 10px;
                border-bottom:1px solid rgba(255,255,255,0.06);">
      Right Now
    </div>
    {_render_mom_now_block(iso, weekday)}
    {__render_meal_card_safe(today_d)}

    <!-- Calendar events -->
    <div class="section-cap">Today's events</div>
    <div class="card" style="padding:0;overflow:hidden;margin-bottom:16px;">
        <div style="padding:12px 16px;border-bottom:1px solid var(--border-light);">
            <div style="display:flex;gap:4px;">{week_cells}</div>
        </div>
        <div style="padding:4px 4px 8px;">
            {cal_strip}
        </div>
    </div>

    <!-- Virtue widget -->
    {_safe_widget('render_virtues', 'render_virtue_dashboard_widget')}

    <!-- 5AM Club widget -->
    {_safe_widget('render_5am', 'render_5am_dashboard_widget')}

    <!-- Prayer Intentions widget -->
    {_safe_widget('render_prayer', 'render_prayer_dashboard_widget')}

    <!-- Family grid -->
    <div class="section-cap">Family grid &middot; Today</div>
    {_grid_html}

    <!-- My plan -->
    <div class="section-cap">My plan</div>
    {plan_html}

    {render_litany_block()}

    {_render_mom_messages_inbox()}

    <a class="link-button no-print" href="/more"
       style="font-size:0.82em;margin-bottom:8px;display:inline-block;">More &rarr;</a>
    <script>
    window.addEventListener('pageshow', function(e) {{
      if (e.persisted) {{ window.location.reload(); }}
    }});
    /* Hide tasks already marked done on page load */
    (function() {{
      document.querySelectorAll('[data-done="1"]').forEach(function(row) {{
        row.style.display = 'none';
      }});
    }})();
    /* Toggle a checkbox in the Boys Right Now cards and persist to server */
    function dashBoyToggle(cb, tid, childId) {{
      var row    = document.getElementById('task-' + tid);
      var isDone = cb.checked;
      if (row) {{
        row.setAttribute('data-done', isDone ? '1' : '0');
        var lbl = row.querySelector('label, .dl-label');
        if (lbl) {{
          lbl.style.opacity        = isDone ? '0.45' : '1';
          lbl.style.textDecoration = isDone ? 'line-through' : 'none';
        }}
        if (isDone) {{
          setTimeout(function() {{
            row.style.transition = 'opacity .25s';
            row.style.opacity    = '0';
            setTimeout(function() {{ row.style.display = 'none'; }}, 260);
          }}, 320);
        }}
      }}
      fetch('/toggle-task', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: 'task_id=' + encodeURIComponent(tid) +
              '&new_value=' + encodeURIComponent(isDone ? 'true' : 'false') +
              '&return_url=' + encodeURIComponent('/today')
      }}).then(function(r) {{
        if (!r.ok) {{
          cb.checked = !cb.checked;
          if (row) {{
            row.setAttribute('data-done', isDone ? '0' : '1');
            var lbl2 = row.querySelector('label, .dl-label');
            if (lbl2) {{ lbl2.style.opacity = '1'; lbl2.style.textDecoration = 'none'; }}
          }}
        }}
      }}).catch(function() {{
        cb.checked = !cb.checked;
        if (row) {{
          row.setAttribute('data-done', isDone ? '0' : '1');
          var lbl3 = row.querySelector('label, .dl-label');
          if (lbl3) {{ lbl3.style.opacity = '1'; lbl3.style.textDecoration = 'none'; }}
        }}
      }});
    }}
    /* Live progress sync — polls every 15 s so checkboxes stay in sync
       with the plan-of-day pages without needing a manual refresh. */
    (function() {{
      var _iso = '{escape(iso)}';
      function _syncProgress() {{
        fetch('/api/today-progress?date=' + _iso)
          .then(function(r) {{ return r.ok ? r.json() : null; }})
          .then(function(data) {{
            if (!data) return;
            document.querySelectorAll('[id^="task-"]').forEach(function(row) {{
              var tid     = row.id.replace(/^task-/, '');
              var isDone  = data[tid] === true;
              var wasDone = row.getAttribute('data-done') === '1';
              if (isDone === wasDone) return;   // already in sync
              var cb  = row.querySelector('input[type="checkbox"]');
              var lbl = row.querySelector('label, .dl-sub-label, .dl-label');
              if (isDone) {{
                row.setAttribute('data-done', '1');
                if (cb) cb.checked = true;
                if (lbl) {{ lbl.style.opacity = '0.4'; lbl.style.textDecoration = 'line-through'; }}
                /* Fade out dashboard items that just became done */
                if (row.classList.contains('dash-task')) {{
                  row.style.transition = 'opacity .3s';
                  row.style.opacity    = '0';
                  setTimeout(function() {{ row.style.display = 'none'; }}, 320);
                }}
              }} else {{
                row.setAttribute('data-done', '0');
                if (cb) cb.checked = false;
                if (lbl) {{ lbl.style.opacity = '1'; lbl.style.textDecoration = 'none'; }}
                row.style.display = ''; row.style.opacity = '1'; row.style.transition = '';
              }}
            }});
          }}).catch(function() {{}});
      }}
      setInterval(_syncProgress, 15000);
    }})();
    </script>
    """
    return html_page("Dashboard", body)


# ── Family Now page ──────────────────────────────────────────────────────────
def render_now_page() -> str:
    """
    /now — Clean full-page view of what every family member is doing right now.
    Shows the current schedule slot, next slot, and first unchecked task per person.
    """
    from datetime import datetime as _dt
    from render_schedule_support import get_current_slot, get_eastern_now
    from data_helpers import load_progress, get_frol_day_slots
    from daily_schedule_engine import CHILDREN, build_schedule_payload
    from render_schedule import _item_done
    from config import child_color

    now     = get_eastern_now()
    weekday = now.strftime("%A")
    time_str = now.strftime("%-I:%M %p")

    cur_slot, cur_act, nxt_slot, nxt_act = get_current_slot(weekday=weekday)
    all_slots = get_frol_day_slots(weekday, "Mom")
    progress  = load_progress()

    iso = now.strftime("%Y-%m-%d")
    date_label = now.strftime("%B %-d")

    def _person_card(name: str, bg: str, light: str, link: str,
                     now_activity: str, next_activity: str,
                     first_task: str, task_section: str,
                     done_cnt: int, total: int) -> str:
        pct = round(done_cnt / total * 100) if total else 0
        prog = (
            f'<div style="height:3px;background:#e0d8d0;border-radius:2px;margin:6px 0 2px;">'
            f'<div style="height:3px;background:{bg};border-radius:2px;width:{pct}%;transition:width .3s;"></div></div>'
            f'<div style="font-size:.65em;color:#aaa;">{done_cnt}/{total} done</div>'
        ) if total else ""

        now_html = (
            f'<div style="font-size:.82em;font-weight:600;color:{bg};">{escape(now_activity)}</div>'
            if now_activity else
            f'<div style="font-size:.82em;color:#aaa;font-style:italic;">No schedule entry</div>'
        )
        next_html = (
            f'<div style="font-size:.72em;color:#888;margin-top:2px;">Next: {escape(next_activity)}</div>'
            if next_activity else ""
        )
        task_html = (
            f'<div style="margin-top:8px;padding:6px 8px;background:white;border-radius:6px;'
            f'border:1px solid {bg}22;">'
            f'<div style="font-size:.62em;font-weight:800;letter-spacing:.07em;'
            f'text-transform:uppercase;color:{bg};margin-bottom:2px;">{escape(task_section)}</div>'
            f'<div style="font-size:.82em;color:#333;line-height:1.3;">{escape(first_task)}</div>'
            f'</div>'
        ) if first_task else ""

        return (
            f'<a href="{link}" style="text-decoration:none;display:block;">'
            f'<div style="background:{light};border-left:4px solid {bg};border-radius:0 10px 10px 0;'
            f'padding:12px 14px;margin-bottom:10px;">'
            f'<div style="font-weight:700;font-size:1em;color:{bg};margin-bottom:6px;">{escape(name)}</div>'
            f'{now_html}{next_html}'
            f'{prog}'
            f'{task_html}'
            f'</div></a>'
        )

    cards_html = ""

    # Mom card
    mom_bg    = "#7c5a38"
    mom_light = "#fdf8f1"
    try:
        from render_daily_plan import load_daily_plan
        _plan  = load_daily_plan(iso)
        _items = _plan.get("items", [])
        _undone = [i for i in _items if not i.get("done")]
        mom_task = _undone[0].get("text", "") if _undone else ""
        mom_task_sec = "Plan item" if mom_task else ""
        mom_done = sum(1 for i in _items if i.get("done"))
        mom_total = len(_items)
    except Exception:
        mom_task = mom_task_sec = ""
        mom_done = mom_total = 0
    cards_html += _person_card(
        "Mom", mom_bg, mom_light, "/mom",
        cur_act, nxt_act, mom_task, mom_task_sec, mom_done, mom_total
    )

    # Children cards
    for child in CHILDREN:
        c_bg    = child_color(child, "bg")
        c_light = child_color(child, "light")
        try:
            payload = build_schedule_payload(child, weekday, date_label, iso)
        except Exception:
            payload = {}
        # First unchecked task
        first_task = first_sec = ""
        for item in payload.get("carryover_items", []):
            if not _item_done(item, progress):
                first_task = item.get("text", "")
                first_sec  = "Carryover"
                break
        if not first_task:
            for item in payload.get("manual_task_items", []):
                if not _item_done(item, progress):
                    first_task = item.get("text", "")
                    first_sec  = "Task"
                    break
        if not first_task:
            for block in payload.get("school_blocks", []):
                for item in block.get("items", []):
                    if not _item_done(item, progress):
                        first_task = item.get("text", "")
                        first_sec  = block.get("subject", "School")
                        break
                if first_task:
                    break
        if not first_task:
            for item in payload.get("chore_items", []):
                if not _item_done(item, progress):
                    first_task = item.get("text", "")
                    first_sec  = "Chore"
                    break
        # Progress
        all_items = list(payload.get("carryover_items", []))
        all_items += payload.get("manual_task_items", [])
        for block in payload.get("school_blocks", []):
            all_items.extend(block.get("items", []))
        all_items += payload.get("chore_items", [])
        total     = len(all_items)
        done_cnt  = sum(1 for i in all_items if _item_done(i, progress))
        cards_html += _person_card(
            child, c_bg, c_light, f"/schedule/{escape(child)}?date={iso}",
            cur_act, nxt_act, first_task, first_sec, done_cnt, total
        )

    # James card
    james_bg    = child_color("James", "bg")
    james_light = child_color("James", "light")
    try:
        from render_settings import load_app_settings as _las
        _james_sched = _las().get("family_constraints", {}).get("james_schedule", "")
    except Exception:
        _james_sched = ""
    cards_html += _person_card(
        "James", james_bg, james_light, "/settings",
        cur_act, "", _james_sched[:80] if _james_sched else "", "Schedule", 0, 0
    )

    slot_row = (
        f'<div style="background:var(--gold-light);border:1px solid var(--border);'
        f'border-radius:10px;padding:8px 14px;margin-bottom:14px;'
        f'font-size:.85em;font-weight:600;color:var(--ink);">'
        f'🕐 {escape(cur_slot)} — {escape(cur_act) if cur_act else "—"}'
        f'{"  ·  Next: " + escape(nxt_act) if nxt_act else ""}'
        f'</div>'
    ) if cur_slot else ""

    body = (
        f'{page_header("Family — Right Now")}'
        f'<div style="font-size:.82em;color:#888;margin-bottom:12px;">'
        f'{escape(weekday)}, {time_str}'
        f'  <a href="/now" style="margin-left:10px;font-size:.9em;color:var(--brown);">↻ Refresh</a>'
        f'</div>'
        f'{slot_row}'
        f'{cards_html}'
        f'<div style="text-align:center;margin-top:16px;">'
        f'<a href="/today" style="font-size:.82em;color:var(--brown);">← Back to Today</a>'
        f'</div>'
    )
    return html_page("Right Now", body)


def _render_rule_of_life_strip(weekday: str, person: str = "") -> str:
    """
    Compact scrollable strip showing today's Rule of Life time anchors.
    Reads from Mom's FROL day template and exercise_assignments.json on every
    call so edits appear immediately on the next page load.
    Current slot is highlighted in gold; past slots are faded.
    When `person` is provided, exercise slots show only that person's assignment.
    """
    from html import escape as _e
    _EXERCISE_KEYWORDS = ("fortitude", "justice", "exercise", "family run", "family strength")
    try:
        from data_helpers import get_frol_day_slots, load_exercise_assignments
        from render_schedule_support import _slot_minutes, get_eastern_now, generate_half_hour_times

        day_slots = get_frol_day_slots(weekday, "Mom")
        times     = [t for t in generate_half_hour_times() if t in day_slots]
        ex_data   = load_exercise_assignments()
        ex_assign = ex_data.get(weekday, {})
        if not day_slots:
            return ""

        now     = get_eastern_now()
        now_min = now.hour * 60 + now.minute

        # Build ordered list of non-empty slots, merging consecutive duplicates
        entries = []
        prev_label = None
        for t in times:
            label = (day_slots.get(t) or "").strip()
            if not label:
                prev_label = None
                continue
            if label == prev_label:
                continue          # skip consecutive duplicates (merged block)
            entries.append((t, _slot_minutes(t), label))
            prev_label = label

        if not entries:
            return ""

        # Find current slot index
        cur_idx = -1
        for i, (_, sm, _) in enumerate(entries):
            if sm <= now_min:
                cur_idx = i

        chips = ""
        for i, (t, sm, label) in enumerate(entries):
            is_now  = (i == cur_idx)
            is_past = (i < cur_idx)
            if is_now:
                bg = "var(--gold-light)"; border = "2px solid var(--brown)"
                tc = "var(--ink)";        fw = "700"
            elif is_past:
                bg = "transparent";                 border = "1px solid var(--border-light)"
                tc = "var(--ink-faint)";  fw = "400"
            else:
                bg = "var(--warm-white)"; border = "1px solid var(--border)"
                tc = "var(--ink-muted)";  fw = "400"
            # Build chip body — show person-specific exercise note when available
            is_exercise = any(kw in label.lower() for kw in _EXERCISE_KEYWORDS)
            person_note = ""
            if is_exercise and person and ex_assign:
                _pkey = next((k for k in ex_assign if k.lower() == person.lower()), None)
                if _pkey:
                    person_note = (
                        f'<div style="font-size:0.63em;color:{tc};opacity:0.85;'
                        f'line-height:1.3;margin-top:3px;text-align:left;'
                        f'white-space:normal;word-break:break-word;">'
                        f'{_e(ex_assign[_pkey])}</div>'
                    )
            chips += (
                f'<div style="flex-shrink:0;background:{bg};border:{border};'
                f'border-radius:8px;padding:5px 10px;text-align:center;min-width:72px;'
                f'max-width:{"220px" if person_note else "130px"};">'
                f'<div style="font-size:0.62em;color:{tc};opacity:0.75;white-space:nowrap;">{_e(t)}</div>'
                f'<div style="font-size:0.72em;color:{tc};font-weight:{fw};'
                f'line-height:1.2;margin-top:2px;word-break:break-word;">{_e(label)}</div>'
                f'{person_note}'
                f'</div>'
            )

        return (
            f'<div style="margin-bottom:14px;">'
            f'<div style="font-size:0.6em;font-weight:800;letter-spacing:.14em;'
            f'text-transform:uppercase;color:var(--ink-faint);margin-bottom:6px;">'
            f'Rule of Life — {_e(weekday)}</div>'
            f'<div id="rol-strip" style="display:flex;gap:6px;overflow-x:auto;'
            f'scrollbar-width:none;padding-bottom:4px;">'
            f'{chips}'
            f'</div>'
            f'</div>'
            f'<script>'
            f'(function(){{'
            f'  var el=document.getElementById("rol-strip");'
            f'  var now=el&&el.querySelector("[style*=\'var(--gold\']");'
            f'  if(now)now.scrollIntoView({{behavior:"smooth",inline:"center",block:"nearest"}});'
            f'}})();'
            f'</script>'
        )
    except Exception:
        return ""


# ── Mom page (step-by-step pages) ───────────────────────────────────────────
def render_mom_page(status_message: str = "", target_date_str: str = "") -> str:
    """
    Plan My Day — 6 steps rendered as separate pages, navigated via JS.
    No scrolling through all steps — each step is its own screen.
    """
    normalized_date = normalize_date_query(target_date_str)
    packet     = generate_day_packet(normalized_date)
    weekday    = packet["weekday"]
    date_label = packet["date_label"]
    iso        = packet["iso"]

    try:
        target_date = date.fromisoformat(iso)
    except Exception:
        target_date = date.today()

    # ── Build each step's HTML — guard every step individually ───────────────
    def _safe_step(fn, label):
        try:
            return fn()
        except Exception as e:
            return f'<div class="card"><p class="muted">Could not load {label}: {escape(str(e))}</p></div>'

    from render_morning_anchor import render_morning_anchor, render_evening_anchor
    from render_daily_bar import render_daily_bar
    from render_daily_plan import render_plan_editor, render_add_to_plan_btn

    morning_html  = _safe_step(lambda: render_morning_anchor(iso, weekday, date_label, target_date), "Morning Anchor")
    evening_html  = _safe_step(lambda: render_evening_anchor(iso), "Evening Anchor")
    daily_bar     = _safe_step(lambda: render_daily_bar(target_date), "Daily Bar")

    # ── Plan progress bar ────────────────────────────────────────────────────
    try:
        from render_daily_plan import load_daily_plan as _ldp
        _plan_items = _ldp(iso).get("items", [])
        _plan_total = len(_plan_items)
        _plan_done  = sum(1 for i in _plan_items if i.get("done", False))
        _plan_pct   = int(100 * _plan_done / _plan_total) if _plan_total else 0
        _bar_col    = "#22c55e" if _plan_pct == 100 else ("#f59e0b" if _plan_pct >= 50 else "#8b5a3c")
        plan_progress_html = (
            f'<div style="margin-bottom:8px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'margin-bottom:4px;">'
            f'<span style="font-size:0.75em;color:var(--ink-faint);font-weight:600;">'
            f'Plan progress</span>'
            f'<span style="font-size:0.75em;color:var(--ink-faint);">{_plan_done}/{_plan_total} done</span>'
            f'</div>'
            f'<div style="height:6px;background:var(--border-light);border-radius:3px;overflow:hidden;">'
            f'<div style="height:100%;width:{_plan_pct}%;background:{_bar_col};'
            f'border-radius:3px;transition:width 0.4s;"></div>'
            f'</div>'
            f'</div>'
        ) if _plan_total else ""
    except Exception:
        plan_progress_html = ""

    # ── Now / Next strip ────────────────────────────────────────────────────
    try:
        from render_schedule_support import render_now_next_strip as _rnn
        now_next_html = _rnn()
    except Exception:
        now_next_html = ""
    cal_strip     = _safe_step(lambda: render_calendar_today_strip(iso), "Calendar")

    try:
        from render_liturgical import render_liturgical_day_card
        lit_card = render_liturgical_day_card(target_date, compact=True)
    except Exception:
        lit_card = ""

    glance_html = f"""
    <div id="s-glance" class="plan-section">
        <div class="plan-section-label">Step 1 &mdash; Today at a glance</div>
        {daily_bar}
        <div class="card card-tight"><h3 style="margin-bottom:8px;">Calendar events</h3>{cal_strip}</div>
        {f'<div class="card card-tight">{lit_card}</div>' if lit_card else ""}
    </div>"""

    # School section
    from daily_schedule_engine import CHILDREN, build_schedule_payload
    from config import child_color
    school_cards = ""
    for child in CHILDREN:
        payload = build_schedule_payload(child, weekday, date_label, iso)
        blocks  = payload.get("school_blocks", [])
        chores  = payload.get("chore_items", [])
        c_bg    = child_color(child, "bg")
        c_light = child_color(child, "light")
        status  = "On track"
        status_color = "#27ae60"
        # Check for anything needing attention
        for b in blocks:
            if b.get("needs_check"):
                status = b.get("subject","Check needed")
                status_color = "#e74c3c"
                break
        school_cards += (
            f'<div style="flex:1;min-width:130px;border:1.5px solid {c_bg};border-radius:12px;'
            f'padding:12px 14px;background:{c_light};">'
            f'<div style="font-weight:700;color:{c_bg};font-size:0.88em;margin-bottom:6px;">{escape(child)}</div>'
            f'<div style="font-size:0.88em;color:var(--ink);">{escape(status)}</div>'
            f'<div style="font-size:0.78em;color:var(--ink-muted);margin-top:3px;">{len(blocks)} subjects</div>'
            f'</div>'
        )
    school_html = f"""
    <div id="s-school" class="plan-section">
        <div class="plan-section-label">Step 2 &mdash; School review</div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">{school_cards}</div>
    </div>"""

    # Schedule section (just timeline, no now/next)
    from render_schedule_support import render_today_timeline
    schedule_html = f"""
    <div id="s-schedule" class="plan-section">
        <div class="plan-section-label">Step 3 &mdash; Fill in the schedule</div>
        <div class="card card-tight">
            {render_today_timeline(weekday)}
            <div style="margin-top:10px;border-top:1px solid var(--border-light);padding-top:8px;">
                <a class="link-button" href="/settings#s-systems" style="font-size:0.82em;">
                    Edit Rule of Life &rarr;
                </a>
            </div>
        </div>
    </div>"""

    # Tasks sidebar for plan editor
    all_tasks    = load_manual_tasks()
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    active_tasks = [
        (i, t) for i, t in enumerate(all_tasks)
        if isinstance(t, dict) and t.get("status", "active") == "active"
    ]
    active_tasks.sort(key=lambda it: (it[1].get("due_date","") or "9999",
                                       priority_order.get(it[1].get("priority","MEDIUM"),1)))

    tasks_items = ""
    for idx, task in active_tasks[:5]:
        tid   = escape(task.get("id", str(idx)))
        ttext = escape(task.get("text", ""))
        tpri  = task.get("priority","MEDIUM")
        pri_color = {"HIGH":"#e74c3c","MEDIUM":"#e67e22","LOW":"#27ae60"}.get(tpri,"#888")
        add_btn = render_add_to_plan_btn(ttext, "task", "#8b5a3c")
        tasks_items += (
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'gap:8px;padding:6px 0;border-bottom:1px solid var(--border-light);">'
            f'<span style="font-size:0.85em;flex:1;">'
            f'<span style="width:6px;height:6px;border-radius:50%;background:{pri_color};'
            f'display:inline-block;margin-right:5px;"></span>{ttext}</span>'
            f'{add_btn}</div>'
        )
    tasks_sidebar = f"""
    <div class="card card-tight">
        <h4 style="margin-bottom:8px;">Active tasks</h4>
        {tasks_items or '<p class="muted" style="font-size:0.82em;">No active tasks.</p>'}
        <div style="margin-top:8px;"><a class="link-button" href="/tasks" style="font-size:0.78em;">All tasks</a></div>
    </div>"""

    mom_notes = load_mom_notes()
    note_items = "".join(
        f'<div style="font-size:0.82em;padding:4px 0;border-bottom:1px solid var(--border-light);">'
        f'{escape(n.get("text","")[:60])}</div>'
        for n in mom_notes if n.get("status","active") == "active"
    )[:3]
    notes_sidebar = f"""
    <div class="card card-tight">
        <h4 style="margin-bottom:8px;">Notes</h4>
        <form method="POST" action="/mom-add-note">
            <textarea name="text" rows="2" placeholder="Meal plan, prep note..."
                      style="margin-bottom:6px;font-size:0.85em;resize:vertical;"></textarea>
            <button type="submit" style="padding:4px 12px;font-size:0.82em;">Save</button>
        </form>
        {note_items}
    </div>"""

    school_sidebar = f"""
    <div class="card card-tight">
        <h4 style="margin-bottom:8px;">School today</h4>
        <div style="display:flex;flex-direction:column;gap:6px;">{"".join(
            f'<a class="link-button" href="/schedule/{escape(c)}?date={escape(iso)}" style="font-size:0.8em;">{escape(c)}</a>'
            for c in CHILDREN
        )}</div>
    </div>"""

    sidebar_html  = school_sidebar + tasks_sidebar + notes_sidebar
    plan_html     = render_plan_editor(iso, weekday, date_label, sidebar_html)

    # AI panel
    from render_ai_planner import render_ai_panel
    ai_panel_html = render_ai_panel(iso)

    # ── Step definitions ──────────────────────────────────────────────────────
    from render_daily_plan import load_daily_plan
    plan_data   = load_daily_plan(iso)
    anchor      = plan_data.get("anchor", {})
    launch      = anchor.get("launch", {})
    launch_done = all(launch.get(k, False) for k in ["gather","review","goal","prayer","begin"])
    evening     = anchor.get("evening", {})
    eve_done    = sum(1 for k in ["dinner_cleanup","showers","clothes_out",
                                   "evening_prayer","marriage_window"]
                      if evening.get(k, False)) >= 3

    steps = [
        ("spiritual", "1 · Spiritual",   False),
        ("cycle",     "2 · Cycle",       False),
        ("meals",     "3 · Meals",       False),
        ("calendar",  "4 · Calendar",    False),
        ("tasks",     "5 · Tasks",       False),
        ("kidsday",   "6 · Kids' Day",   False),
        ("evening",   "7 · Evening",     eve_done),
        ("grid",      "8 · Grid & Done", False),
    ]

    import json as _json

    # Build step chips
    step_chips = ""
    for step_id, label, done in steps:
        if done:
            chip_style = ("background:#eef7ee;border:1.5px solid #c3ddb0;"
                          "color:#2a5a2a;font-weight:700;")
            chip_label = f"&#10003; {escape(label.split(' · ')[1])}"
        else:
            chip_style = ("background:var(--warm-white);border:1.5px solid var(--border);"
                          "color:var(--ink-muted);font-weight:400;")
            chip_label = escape(label)
        done_attr = ' data-done="1"' if done else ''
        step_chips += (
            '<button onclick="goToStep(\'' + step_id + '\')" '
            'id="chip-' + step_id + '"' + done_attr + ' '
            'style="' + chip_style + 'padding:6px 14px;border-radius:20px;font-size:0.8em;'
            'cursor:pointer;font-family:inherit;white-space:nowrap;'
            'transition:all 0.15s;flex-shrink:0;">'
            + chip_label + '</button>'
        )

    done_steps_js   = _json.dumps([s[0] for s in steps if s[2]])
    steps_js        = _json.dumps([s[0] for s in steps])
    step_labels_js  = _json.dumps({s[0]: s[1].split(' · ')[1] for s in steps})
    mode_label      = escape(anchor.get("capacity","") + " capacity") if anchor.get("capacity") else ""
    mode_mode       = escape(anchor.get("mode","Home") + " mode")
    day_nav         = render_day_nav("/mom", iso)

    body = f"""
    {top_nav()}
    {render_status_message(status_message)}

    <!-- Page header -->
    <div style="display:flex;align-items:flex-start;justify-content:space-between;
                flex-wrap:wrap;gap:8px;margin-bottom:8px;padding-top:4px;">
        <div>
            <div style="font-family:'Cormorant Garamond',Georgia,serif;
                        font-size:2rem;font-weight:600;color:var(--ink);line-height:1.1;">
                Plan My Day
            </div>
            <div style="font-size:0.85em;color:var(--ink-muted);margin-top:2px;">
                <strong>{escape(weekday)}</strong> &middot; {escape(date_label)}
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;margin-top:4px;">
            <div style="font-size:0.82em;color:var(--ink-muted);text-align:right;">
                <div style="font-weight:600;color:var(--brown);">{mode_label}</div>
                <div>{mode_mode}</div>
            </div>
            {day_nav}
        </div>
    </div>

    <!-- Plan progress bar -->
    {plan_progress_html}

    <!-- Now / Next strip -->
    {f'<div style="margin-bottom:12px;">{now_next_html}</div>' if now_next_html else ""}

    <!-- Rule of Life strip — live from family_schedule.json -->
    {_render_rule_of_life_strip(weekday, person="Lauren")}

    <!-- Print & nav row -->
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap;">
        <a href="/print/day/lauren?date={escape(iso)}"
           style="font-size:0.8em;padding:5px 12px;background:var(--parchment);
                  color:var(--brown);border:1.5px solid var(--border);border-radius:8px;
                  font-weight:700;text-decoration:none;white-space:nowrap;">🖨 Print My Day</a>
    </div>

    <!-- Step chips — horizontal scroll -->
    <div style="display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;
                padding-bottom:4px;margin-bottom:16px;">
        {step_chips}
    </div>

    <!-- Step content — loaded via fetch -->
    <div id="step-content" style="min-height:200px;">
        <div class="card" style="text-align:center;padding:32px;">
            <div style="font-size:1.2em;margin-bottom:8px;">Loading...</div>
        </div>
    </div>

    <!-- Continue / back footer -->
    <div id="step-footer"
         style="display:flex;justify-content:space-between;align-items:center;
                margin-top:24px;padding-top:16px;border-top:1px solid var(--border-light);">
        <button id="btn-back" onclick="stepBack()"
                style="padding:10px 20px;background:transparent;color:var(--ink-muted);
                       border:1.5px solid var(--border);border-radius:10px;
                       font-size:0.88em;font-family:inherit;visibility:hidden;">
            &larr; Back
        </button>
        <button onclick="stepNext()" id="btn-continue"
                style="padding:10px 24px;background:var(--ink);color:var(--gold-light);
                       border:none;border-radius:10px;font-size:0.88em;font-weight:700;
                       font-family:inherit;letter-spacing:0.02em;">
            Continue &rarr;
        </button>
    </div>

    <script>
    var _steps   = {steps_js};
    var _labels  = {step_labels_js};
    var _iso     = '{escape(iso)}';
    var _current = 0;
    var _loaded  = {{}};  // cache fetched step HTML

    // Expose cache-invalidation + reload to fragment scripts (e.g. Step 5
    // task-edit panels need to refresh their step after a save/done).
    window._momStepInvalidate = function(sid) {{ delete _loaded[sid]; }};
    window._momStepReload     = function(sid) {{ delete _loaded[sid]; goToStep(sid); }};

    // Read step from URL hash
    (function() {{
        var hash = window.location.hash.replace('#','');
        var idx  = _steps.indexOf(hash);
        if (idx >= 0) _current = idx;
    }})();

    function goToStep(idx_or_id) {{
        if (typeof idx_or_id === 'string') {{
            var i = _steps.indexOf(idx_or_id);
            if (i >= 0) _current = i;
        }} else {{
            _current = idx_or_id;
        }}
        _loadStep();
    }}

    function stepNext() {{
        if (_current < _steps.length - 1) {{ _current++; _loadStep(); }}
        else {{ /* done */ }}
    }}

    function stepBack() {{
        if (_current > 0) {{ _current--; _loadStep(); }}
    }}

    function _loadStep() {{
        var stepId = _steps[_current];
        _updateChips();
        _updateFooter();
        history.replaceState(null, '', '#' + stepId);
        window.scrollTo(0, 0);

        // Use cached version if available
        if (_loaded[stepId]) {{
            document.getElementById('step-content').innerHTML = _loaded[stepId];
            return;
        }}

        // Show loading
        document.getElementById('step-content').innerHTML =
            '<div class="card" style="text-align:center;padding:32px;color:var(--ink-muted);">Loading step...</div>';

        // Fetch from server
        fetch('/mom-step?step=' + encodeURIComponent(stepId) + '&iso=' + encodeURIComponent(_iso))
            .then(function(r) {{ return r.text(); }})
            .then(function(html) {{
                _loaded[stepId] = html;
                document.getElementById('step-content').innerHTML = html;

                // Re-run any inline scripts in the fetched HTML
                var scripts = document.getElementById('step-content').querySelectorAll('script');
                scripts.forEach(function(oldScript) {{
                    var newScript = document.createElement('script');
                    newScript.textContent = oldScript.textContent;
                    oldScript.parentNode.replaceChild(newScript, oldScript);
                }});
                // Re-init swipe on any newly-loaded rows
                if(window._sw) window._sw(document.getElementById('step-content'));
            }})
            .catch(function(e) {{
                document.getElementById('step-content').innerHTML =
                    '<div class="card"><p class="muted">Could not load step. Try refreshing.</p></div>';
            }});
    }}

    function _updateChips() {{
        var doneSteps = {done_steps_js};
        _steps.forEach(function(s, i) {{
            var chip = document.getElementById('chip-' + s);
            if (!chip) return;
            var isDone = doneSteps.indexOf(s) >= 0;
            if (i === _current) {{
                chip.style.background  = 'var(--ink)';
                chip.style.color       = '#f5ead8';
                chip.style.borderColor = 'var(--ink)';
                chip.style.fontWeight  = '700';
            }} else if (isDone) {{
                chip.style.background  = '#eef7ee';
                chip.style.color       = '#2a5a2a';
                chip.style.borderColor = '#c3ddb0';
                chip.style.fontWeight  = '700';
            }} else {{
                chip.style.background  = 'var(--warm-white)';
                chip.style.color       = 'var(--ink-muted)';
                chip.style.borderColor = 'var(--border)';
                chip.style.fontWeight  = '400';
            }}
        }});
    }}

    function _updateFooter() {{
        var btn = document.getElementById('btn-continue');
        if (btn) {{
            if (_current === _steps.length - 1) {{
                btn.textContent = 'Done \u2713';
            }} else {{
                var nextLabel = _labels[_steps[_current + 1]] || _steps[_current + 1];
                btn.textContent = nextLabel + ' \u2192';
            }}
        }}
        var backBtn = document.getElementById('btn-back');
        if (backBtn) {{
            if (_current === 0) {{
                backBtn.style.visibility = 'hidden';
            }} else {{
                backBtn.style.visibility = 'visible';
                var prevLabel = _labels[_steps[_current - 1]] || _steps[_current - 1];
                backBtn.textContent = '\u2190 ' + prevLabel;
            }}
        }}
    }}

    // Init on DOM ready
    document.addEventListener('DOMContentLoaded', function() {{
        _loadStep();
    }});
    </script>
    """
    return html_page("Plan My Day", body)


# ── Print: Lauren's Day ───────────────────────────────────────────────────────
def render_print_lauren_day(target_date_str: str = "") -> str:
    """Print-friendly view of Lauren's daily plan + active tasks."""
    from html import escape as _e
    from render_daily_plan import load_daily_plan
    from data_helpers import load_manual_tasks

    normalized_date = normalize_date_query(target_date_str)
    packet     = generate_day_packet(normalized_date)
    weekday    = packet["weekday"]
    date_label = packet["date_label"]
    iso        = packet["iso"]

    plan_items = load_daily_plan(iso).get("items", [])
    timed      = sorted([i for i in plan_items if i.get("time","")],
                        key=lambda i: i.get("time",""))
    untimed    = [i for i in plan_items if not i.get("time","")]

    def _checkbox(done):
        return (
            '<span style="display:inline-block;width:14px;height:14px;border:1.5px solid #888;'
            'border-radius:3px;margin-right:8px;flex-shrink:0;vertical-align:middle;'
            + ('background:#27ae60;' if done else '') + '"></span>'
        )

    rows_html = ""
    for item in timed + untimed:
        t    = _e(item.get("time","") or "")
        text = _e(item.get("text",""))
        done = item.get("done", False)
        col  = item.get("color","#6b7280")
        text_style = "text-decoration:line-through;color:#aaa;" if done else "color:#222;"
        rows_html += (
            f'<div style="display:flex;align-items:center;gap:10px;padding:7px 0;'
            f'border-bottom:1px solid #f0ebe4;">'
            f'<span style="font-size:11px;color:#999;min-width:60px;flex-shrink:0;">{t}</span>'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{col};flex-shrink:0;"></span>'
            f'{_checkbox(done)}'
            f'<span style="font-size:13px;{text_style}">{text}</span>'
            f'</div>'
        )

    if not rows_html:
        rows_html = '<p style="color:#aaa;font-style:italic;font-size:13px;padding:12px 0;">No plan items for today.</p>'

    # Active tasks
    try:
        tasks = [t for t in load_manual_tasks()
                 if isinstance(t, dict) and t.get("status","active") == "active"]
    except Exception:
        tasks = []

    task_rows = ""
    for t in tasks:
        text = _e(t.get("text",""))
        pri  = t.get("priority","MEDIUM")
        pc   = {"HIGH":"#c0392b","MEDIUM":"#e67e22","LOW":"#27ae60"}.get(pri,"#888")
        task_rows += (
            f'<div style="display:flex;align-items:center;gap:10px;padding:7px 0;'
            f'border-bottom:1px solid #f0ebe4;">'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{pc};flex-shrink:0;"></span>'
            f'{_checkbox(False)}'
            f'<span style="font-size:13px;color:#222;">{text}</span>'
            f'</div>'
        )

    tasks_section = (
        f'<div style="margin-top:20px;">'
        f'<div style="font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;'
        f'color:#888;margin-bottom:10px;padding-bottom:4px;border-bottom:1.5px solid #e0d8cc;">Active Tasks</div>'
        f'{task_rows}'
        f'</div>'
    ) if task_rows else ""

    # Exercise section
    try:
        from render_schedule import _render_exercise_block_print
        lauren_ex_html = _render_exercise_block_print("Lauren", weekday)
    except Exception:
        lauren_ex_html = ""

    # Meals section
    try:
        from render_schedule import _render_meal_print_section
        from datetime import date as _dt2
        meals_html = _render_meal_print_section(_dt2.fromisoformat(iso), weekday)
    except Exception:
        meals_html = ""

    css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600&display=swap');
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:Georgia,serif;background:#fdf8f0;color:#222;padding:20px;max-width:600px;margin:0 auto;}
.no-print{display:block;}
@media print{
  .no-print{display:none!important;}
  body{background:white;padding:12px;}
}
.page-header{margin-bottom:20px;padding-bottom:12px;border-bottom:2px solid #8b5a3c;}
.section-title{font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
  color:#888;margin-bottom:10px;padding-bottom:4px;border-bottom:1.5px solid #e0d8cc;}
.page-footer{margin-top:24px;padding-top:10px;border-top:1px solid #e0d8cc;
  font-size:10px;color:#aaa;text-align:center;}
</style>"""

    body = f"""
<div class="no-print" style="background:#2a2a2a;color:white;padding:10px 18px;
     display:flex;align-items:center;gap:14px;margin:-20px -20px 20px;font-size:13px;">
    <button onclick="setTimeout(function(){{window.print();}},100)"
            style="background:#8b5a3c;color:white;border:none;padding:8px 16px;
                   border-radius:6px;cursor:pointer;font-size:13px;">🖨 Print</button>
    <span style="color:#aaa;font-size:11px;">On iPhone: tap Share ↑ then "Print"</span>
    <a href="/mom?date={_e(iso)}" style="color:#aaa;margin-left:auto;font-size:12px;">← Back</a>
</div>

<div class="page-header">
    <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.8rem;font-weight:600;
                color:#8b5a3c;line-height:1.1;">Lauren</div>
    <div style="font-size:13px;color:#888;margin-top:3px;">{_e(weekday)}, {_e(date_label)}</div>
</div>

<div class="section-title">Today's Plan</div>
{rows_html}
{lauren_ex_html}
{tasks_section}
{meals_html}
<div class="page-footer">McAdams Family &middot; {_e(date_label)}</div>
"""
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>{css}</head><body>{body}</body></html>"


# ── Plan My Day — step fragment endpoint ──────────────────────────────────────
def render_mom_step_fragment(step_id: str, iso: str) -> str:
    """
    Returns bare HTML for a single Plan My Day step.
    Fetched via AJAX — no <html>/<body> wrapper.
    """
    from datetime import date
    try:
        target_date = date.fromisoformat(iso)
    except Exception:
        target_date = date.today()

    packet     = generate_day_packet(iso)
    weekday    = packet["weekday"]
    date_label = packet["date_label"]

    def _safe_step(fn, *args):
        try:
            return fn(*args)
        except Exception as ex:
            import traceback
            tb = traceback.format_exc()
            return (
                f'<div class="card" style="padding:20px;border-left:4px solid #c0392b;">'
                f'<div style="font-weight:700;color:#c0392b;margin-bottom:8px;">Step error</div>'
                f'<pre style="font-size:0.75em;color:#888;white-space:pre-wrap;overflow:auto;">'
                f'{escape(tb[-600:])}</pre>'
                f'<a href="/settings" class="link-button" style="margin-top:10px;">⚙ Settings</a>'
                f'</div>'
            )

    if step_id == "spiritual":
        return _safe_step(_render_spiritual_step, iso, weekday, target_date)
    elif step_id == "cycle":
        return _safe_step(_render_cycle_step, iso, target_date)
    elif step_id == "meals":
        return _safe_step(_render_meals_step, iso, target_date)
    elif step_id == "calendar":
        return _safe_step(_render_calendar_step, iso, target_date)
    elif step_id == "tasks":
        return _safe_step(_render_tasks_step, iso)
    elif step_id == "kidsday":
        return _safe_step(_render_kidsday_step, iso, weekday, date_label)
    elif step_id == "school":
        return _safe_step(_render_kidsday_step, iso, weekday, date_label)
    elif step_id == "evening":
        return _safe_step(_render_evening_step, iso)
    elif step_id == "grid":
        return _safe_step(_render_grid_step, iso, weekday, date_label, target_date)
    else:
        return f'<div class="card"><p class="muted">Unknown step: {escape(step_id)}</p></div>'


# ─────────────────────────────────────────────────────────────────────────────
# STEP HELPERS — each returns a bare HTML string (no page wrapper)
# ─────────────────────────────────────────────────────────────────────────────

_SETTINGS_BTN = (
    '<a href="/settings" style="font-size:0.75em;color:var(--ink-faint);'
    'text-decoration:none;padding:3px 8px;border:1px solid var(--border);'
    'border-radius:6px;white-space:nowrap;">⚙ Settings</a>'
)

def _step_header(title: str, subtitle: str = "", settings_anchor: str = "") -> str:
    settings_link = f'/settings#{settings_anchor}' if settings_anchor else '/settings'
    return (
        '<div style="display:flex;align-items:flex-start;justify-content:space-between;'
        'gap:8px;margin-bottom:16px;">'
        f'<div>'
        f'<div style="font-size:0.68rem;font-weight:800;letter-spacing:.14em;'
        f'text-transform:uppercase;color:var(--ink-faint);margin-bottom:4px;">{escape(title)}</div>'
        + (f'<div style="font-size:0.85em;color:var(--ink-muted);">{escape(subtitle)}</div>' if subtitle else '') +
        '</div>'
        f'<a href="{settings_link}" style="font-size:0.72em;color:var(--ink-faint);'
        f'text-decoration:none;padding:3px 8px;border:1px solid var(--border);'
        f'border-radius:6px;white-space:nowrap;flex-shrink:0;">⚙ Settings</a>'
        '</div>'
    )


def _save_bar(save_id: str = "", extra_html: str = "", show_save: bool = True) -> str:
    """Consistent autosave status bar shown at bottom of each step card."""
    save_btn = (
        f'<button type="button" onclick="if(window._saveStep_{save_id}) window._saveStep_{save_id}();" '
        f'style="padding:6px 16px;font-size:0.82em;background:var(--ink);color:var(--gold-light);'
        f'border:none;border-radius:8px;font-family:inherit;cursor:pointer;font-weight:600;">Save</button>'
    ) if show_save else ''
    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'gap:8px;margin-top:16px;padding-top:12px;border-top:1px solid var(--border-light);">'
        f'<span id="save-status-{save_id}" style="font-size:0.78em;color:#27ae60;min-height:16px;"></span>'
        f'<div style="display:flex;gap:8px;align-items:center;">{extra_html}'
        f'{save_btn}'
        f'</div></div>'
    )


# ── STEP 1: Spiritual ─────────────────────────────────────────────────────────
def _render_spiritual_intentions() -> str:
    """Compact prayer intentions block for the spiritual step."""
    try:
        from render_prayer import load_intentions
        intentions = load_intentions()
        active = [i for i in intentions if not i.get("answered") and i.get("active", True)]
    except Exception:
        return ""

    if not active:
        return (
            '<div class="card" style="margin-bottom:12px;">'
            '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">'
            '<div style="font-size:0.7em;font-weight:700;letter-spacing:.12em;'
            'text-transform:uppercase;color:var(--ink-faint);">Prayer Intentions</div>'
            '<a href="/prayer-intentions" style="font-size:0.72em;color:var(--brown);'
            'font-weight:600;text-decoration:none;">Manage ↗</a>'
            '</div>'
            '<div style="font-size:0.82em;color:var(--ink-faint);font-style:italic;">'
            'No active intentions. <a href="/prayer-intentions" '
            'style="color:var(--brown);">Add one ↗</a></div>'
            '</div>'
        )

    rows = ""
    for intention in active[:5]:
        iid   = escape(intention.get("id",""))
        title = escape(intention.get("title",""))
        photo = intention.get("photo","")
        total = sum(e.get("count",1) for e in intention.get("prayer_log",[]))

        # Photo thumbnail or prayer hands
        if photo:
            from render_prayer import _photo_src
            src = _photo_src(photo)
            thumb = (
                f'<img src="{src}" style="width:36px;height:36px;object-fit:cover;'
                f'border-radius:8px;flex-shrink:0;" alt="">'
                if src else
                '<div style="width:36px;height:36px;border-radius:8px;background:var(--parchment);'
                'display:flex;align-items:center;justify-content:center;font-size:1.1em;">🙏</div>'
            )
        else:
            thumb = (
                '<div style="width:36px;height:36px;border-radius:8px;background:var(--parchment);'
                'display:flex;align-items:center;justify-content:center;font-size:1.1em;">🙏</div>'
            )

        count_badge = (
            f'<span style="font-size:0.65em;background:var(--gold-light);color:var(--brown);'
            f'padding:1px 6px;border-radius:8px;font-weight:600;">{total}</span>'
        ) if total else ""

        rows += (
            f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0;'
            f'border-bottom:1px solid var(--border-light);">'
            + thumb
            + f'<div style="flex:1;min-width:0;">'
            f'<div style="font-size:0.85em;font-weight:600;color:var(--ink);'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{title}</div>'
            f'</div>'
            + count_badge
            + f'<button onclick="logIntentionQuick(\'{iid}\')" '
            f'style="padding:4px 10px;background:var(--brown);color:white;border:none;'
            f'border-radius:8px;font-size:0.72em;font-weight:600;font-family:inherit;cursor:pointer;">'
            f'Pray ✝</button>'
            f'</div>'
        )

    more_link = (
        f'<div style="margin-top:6px;text-align:right;">'
        f'<a href="/prayer-intentions" style="font-size:0.72em;color:var(--brown);'
        f'font-weight:600;text-decoration:none;">All intentions ↗</a></div>'
        if len(active) > 5 else ""
    )

    return (
        '<div class="card" style="margin-bottom:12px;">'
        '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">'
        '<div style="font-size:0.7em;font-weight:700;letter-spacing:.12em;'
        'text-transform:uppercase;color:var(--ink-faint);">Prayer Intentions</div>'
        '<a href="/prayer-intentions" style="font-size:0.72em;color:var(--brown);'
        'font-weight:600;text-decoration:none;">Manage ↗</a>'
        '</div>'
        + rows + more_link
        + '<div id="intention-quick-status" style="font-size:0.75em;color:#166534;'
        'min-height:14px;margin-top:4px;"></div>'
        + '<script>'
        'function logIntentionQuick(iid) {'
        '  fetch("/prayer-intention-log", {'
        '    method:"POST", headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        '    body:"id="+encodeURIComponent(iid)+"&type=rosary&count=1"'
        '  }).then(function() {'
        '    var el=document.getElementById("intention-quick-status");'
        '    if(el){el.textContent="\u2713 Recorded"; setTimeout(function(){el.textContent=""},2000);}'
        '  });'
        '}'
        '</script>'
        '</div>'
    )


def _render_spiritual_step(iso: str, weekday: str, target_date) -> str:
    from html import escape as _e
    from render_liturgical import get_day_info, get_vestment_color
    from render_morning_anchor import (
        SEASON_QUOTES, WEEKDAY_REFLECTIONS, SUNDAY_FAMILY_REFLECTION,
        _get_quote_for_day, _get_anchor_state, fetch_this_day_in_history,
    )

    info          = get_day_info(target_date)
    season        = info.get("season","Ordinary Time")
    feast         = info.get("feast_name","")
    vest_bg, vest_txt = get_vestment_color(info)
    quote, attrib = _get_quote_for_day(season, target_date)
    anchor        = _get_anchor_state(iso)

    # Reflection question — WEEKDAY_REFLECTIONS is keyed by day name
    is_sunday = (target_date.weekday() == 6)
    if is_sunday:
        reflection_q = SUNDAY_FAMILY_REFLECTION
    else:
        reflection_q = WEEKDAY_REFLECTIONS.get(weekday, WEEKDAY_REFLECTIONS.get("Monday",""))

    # Mass readings link
    readings_url = f"https://bible.usccb.org/bible/readings/{target_date.strftime('%m%d%y')}.cfm"

    # Rich saint data from Catholic Readings API
    saint_card_html = ""
    saint_quote_from_saint = None
    saint_quote_attr = None
    try:
        from saint_data import get_saint_html_card, fetch_saint_data as _fsd
        _sd = _fsd(target_date)
        # Upgrade feast name if API knows more
        if _sd.get("name"):
            feast = feast or _sd["name"]
        if _sd.get("usccb_link"):
            readings_url = _sd["usccb_link"]
        if _sd.get("quote"):
            saint_quote_from_saint = _sd["quote"]
            saint_quote_attr = _sd.get("name","")
        saint_card_html = get_saint_html_card(target_date, dark=False)
    except Exception:
        pass

    feast_html = f'<strong>{_e(feast)}</strong>' if feast else "No feast today"

    # Season badge
    season_badge = (
        f'<span style="display:inline-block;background:{vest_bg};color:{vest_txt};'
        f'border-radius:6px;padding:3px 10px;font-size:0.72em;font-weight:700;'
        f'letter-spacing:.06em;text-transform:uppercase;margin-bottom:12px;">{_e(season)}</span>'
    )

    # Morning offering text (traditional)
    morning_offering = (
        "O Jesus, through the Immaculate Heart of Mary, I offer You my prayers, works, joys and sufferings "
        "of this day for all the intentions of Your Sacred Heart, in union with the Holy Sacrifice of the Mass "
        "throughout the world, for the reparation of sins, the intentions of all my relatives and benefactors, "
        "and in particular for the intentions of the Holy Father."
    )

    # Angelus text
    angelus_text = (
        "V. The Angel of the Lord declared unto Mary.\n"
        "R. And she conceived of the Holy Spirit.\n\n"
        "Hail Mary, full of grace…\n\n"
        "V. Behold the handmaid of the Lord.\n"
        "R. Be it done unto me according to Thy Word.\n\n"
        "Hail Mary…\n\n"
        "V. And the Word was made flesh.\n"
        "R. And dwelt among us.\n\n"
        "Hail Mary…\n\n"
        "V. Pray for us, O holy Mother of God.\n"
        "R. That we may be made worthy of the promises of Christ.\n\n"
        "Pour forth, we beseech Thee, O Lord, Thy grace into our hearts…"
    )

    # Saved reflection (from anchor)
    saved_reflection = _e(anchor.get("reflection_note",""))

    # Pre-compute conditionals to avoid backslash-in-fstring issues
    _saint_from_label = (
        f'<div style="font-size:0.82em;font-weight:700;color:var(--brown);margin-bottom:6px;">'
        f'From {_e(saint_quote_attr or "today")}:</div>'
        if saint_quote_from_saint else ""
    )
    _scripture_card = (
        '<div class="card" style="margin-bottom:12px;border-left:3px solid rgba(201,164,74,0.4);padding-left:16px;">'
        '<div style="font-size:0.72em;font-weight:700;letter-spacing:.1em;text-transform:uppercase;'
        'color:var(--ink-faint);margin-bottom:6px;">Scripture</div>'
        f'<div style="font-size:0.92em;font-style:italic;color:var(--ink);line-height:1.6;">{_e(quote)}</div>'
        f'<div style="font-size:0.75em;color:var(--ink-faint);margin-top:5px;">&mdash; {_e(attrib)}</div>'
        '</div>'
        if saint_quote_from_saint else ""
    )

    # Pre-compute all string-with-quotes values to avoid nested f-string errors
    _spiritual_header   = _step_header("Step 1 \u00b7 Spiritual", "", "liturgical")
    _readings_date_label = _e(target_date.strftime('%B %d'))

    # Collect of the day
    _COLLECTS = {
        "Lent":         "Grant, O Lord, that we may begin with holy fasting this campaign of Christian service, so that, as we take up battle against spiritual evils, we may be armed with weapons of self-restraint.",
        "Holy Week":    "Almighty ever-living God, who as an example of humility for the human race to follow caused our Savior to take flesh and submit to the Cross, graciously grant that we may heed his lesson of patient suffering and so merit a share in his Resurrection.",
        "Easter":       "O God, who on this day, through your Only Begotten Son, have conquered death and unlocked for us the path to eternity, grant, we pray, that we who keep the solemnity of the Lord\u2019s Resurrection may rise up in the light of life.",
        "Advent":       "Grant your faithful, we pray, almighty God, the resolve to run forth to meet your Christ with righteous deeds at his coming, so that, gathered at his right hand, they may be worthy to possess the heavenly Kingdom.",
        "Christmas":    "O God, who wonderfully created the dignity of human nature and still more wonderfully restored it, grant, we pray, that we may share in the divinity of Christ, who humbled himself to share in our humanity.",
        "Ordinary Time":"Grant us, O Lord our God, that we may honor you with all our mind, and love everyone in truth of heart. Through our Lord Jesus Christ, your Son, who lives and reigns with you in the unity of the Holy Spirit, God, for ever and ever.",
    }
    _collect_text = _COLLECTS.get(season, _COLLECTS["Ordinary Time"])
    _collect_card = (
        '<div class="card" style="margin-bottom:12px;">'
        '<div style="font-size:0.7em;font-weight:700;letter-spacing:.12em;text-transform:uppercase;'
        'color:var(--ink-faint);margin-bottom:8px;">Collect</div>'
        '<div style="font-size:0.88em;font-style:italic;color:var(--ink);line-height:1.75;'
        'padding:10px 14px;background:var(--parchment);border-radius:10px;'
        'border-left:3px solid var(--gold);">'
        + _e(_collect_text) +
        '</div></div>'
    )

    return f"""
{_spiritual_header}

{season_badge}

<!-- Gospel + Saint -->
<div class="card" style="margin-bottom:12px;">
  <div style="font-size:0.7em;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:8px;">Gospel of the Day</div>
  <a href="{readings_url}" target="_blank"
     style="font-size:1.05em;font-weight:700;color:var(--brown);text-decoration:none;">
     Mass Readings for {_readings_date_label} ↗
  </a>
  <div style="font-size:0.82em;color:var(--ink-muted);margin-top:3px;">
    Full text at USCCB · read aloud before school
  </div>
  <div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border-light);">
    {saint_card_html if saint_card_html else (
        f'<div style="font-size:0.7em;font-weight:700;letter-spacing:.12em;text-transform:uppercase;'
        f'color:var(--ink-faint);margin-bottom:6px;">Saint of the Day</div>'
        f'<div style="font-size:0.9em;font-weight:600;color:var(--ink);">{feast_html}</div>'
    )}
  </div>
</div>

<!-- Quote — seasonal OR from the saint if available -->
<div class="card" style="margin-bottom:12px;border-left:3px solid var(--gold);padding-left:16px;">
  {_saint_from_label}
  <div style="font-size:1em;font-style:italic;color:var(--ink);line-height:1.6;">
    {_e(saint_quote_from_saint if saint_quote_from_saint else quote)}
  </div>
  <div style="font-size:0.78em;color:var(--ink-faint);margin-top:6px;">
    &mdash; {_e(saint_quote_attr if saint_quote_from_saint else attrib)}
  </div>
</div>

<!-- Scripture quote of the day (always show, separate from saint quote) -->
{_scripture_card}

<!-- Collect of the Day -->
{_collect_card}

<!-- Morning Offering -->
<div class="card" style="margin-bottom:12px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <div style="font-size:0.7em;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
                color:var(--ink-faint);">Morning Offering</div>
    <button onclick="togglePrayer('morning-offering')"
            style="font-size:0.75em;color:var(--brown);background:none;border:1px solid var(--border);
                   border-radius:6px;padding:3px 8px;cursor:pointer;font-family:inherit;">
      Show prayer
    </button>
  </div>
  <div id="morning-offering" style="display:none;font-size:0.85em;color:var(--ink-muted);
       line-height:1.7;font-style:italic;">{_e(morning_offering)}</div>
  <label style="display:flex;align-items:center;gap:8px;margin-top:8px;font-size:0.85em;cursor:pointer;">
    <input type="checkbox" id="spiritual-morning-offering"
           {"checked" if anchor.get("morning_offering") else ""}
           onchange="spiritualSave()"
           style="width:16px;height:16px;accent-color:var(--brown);">
    Offered this morning
  </label>
</div>

<!-- Angelus -->
<div class="card" style="margin-bottom:12px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <div>
      <div style="font-size:0.7em;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
                  color:var(--ink-faint);">Angelus</div>
      <div style="font-size:0.75em;color:var(--ink-faint);margin-top:2px;">6am · Noon · 6pm</div>
    </div>
    <button onclick="togglePrayer('angelus-text')"
            style="font-size:0.75em;color:var(--brown);background:none;border:1px solid var(--border);
                   border-radius:6px;padding:3px 8px;cursor:pointer;font-family:inherit;">
      Show prayer
    </button>
  </div>
  <div id="angelus-text" style="display:none;font-size:0.82em;color:var(--ink-muted);
       line-height:1.8;white-space:pre-line;">{_e(angelus_text)}</div>
  <label style="display:flex;align-items:center;gap:8px;margin-top:8px;font-size:0.85em;cursor:pointer;">
    <input type="checkbox" id="spiritual-angelus"
           {"checked" if anchor.get("angelus_prayed") else ""}
           onchange="spiritualSave()"
           style="width:16px;height:16px;accent-color:var(--brown);">
    Prayed this morning
  </label>
</div>

<!-- Reflection -->
<div class="card" style="margin-bottom:4px;">
  <div style="font-size:0.7em;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:10px;">Reflection</div>
  <div style="font-size:0.9em;font-style:italic;color:var(--ink);margin-bottom:12px;
              padding:10px 14px;background:var(--ink);color:var(--gold-light);border-radius:10px;
              line-height:1.6;">
    {_e(reflection_q)}
  </div>
  <textarea id="spiritual-reflection" rows="3"
            placeholder="Your thoughts for today..."
            onchange="spiritualSave()" oninput="spiritualAutoSave()"
            style="width:100%;font-size:0.88em;resize:vertical;padding:10px;
                   border:1.5px solid var(--border);border-radius:10px;font-family:inherit;">
{saved_reflection}</textarea>
  {_save_bar("spiritual")}
</div>

<!-- Liturgy of the Hours -->
{_safe_widget('render_liturgy_hours', 'render_hours_dashboard_widget')}

<!-- Prayer Intentions -->
{_render_spiritual_intentions()}

<script>
var _spiritualIso = '{_e(iso)}';
var _spiritualTimer = null;
function togglePrayer(id) {{
  var el = document.getElementById(id);
  if (!el) return;
  var btn = el.previousElementSibling;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}}
function spiritualAutoSave() {{
  clearTimeout(_spiritualTimer);
  _spiritualTimer = setTimeout(spiritualSave, 1000);
}}
function spiritualSave() {{
  var data = {{
    reflection_note:   (document.getElementById('spiritual-reflection')  || {{}}).value || '',
    morning_offering:  !!(document.getElementById('spiritual-morning-offering') || {{}}).checked,
    angelus_prayed:    !!(document.getElementById('spiritual-angelus') || {{}}).checked,
  }};
  fetch('/anchor-save', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'iso=' + encodeURIComponent(_spiritualIso) + '&data=' + encodeURIComponent(JSON.stringify(data))
  }}).then(function() {{
    var el = document.getElementById('save-status-spiritual');
    if (el) {{ el.textContent = 'Saved ✓'; setTimeout(function() {{ el.textContent = ''; }}, 2000); }}
  }});
}}
window._saveStep_spiritual = spiritualSave;
</script>
"""


# ── STEP 2: Cycle ─────────────────────────────────────────────────────────────
def _render_cycle_step(iso: str, target_date) -> str:
    import json as _json, os as _os
    from html import escape as _e
    from render_settings import load_app_settings as _las

    # Load settings for detail fields toggle
    _settings      = _las()
    _show_detail   = _settings.get("cycle_show_detail_fields", True)
    _api_key       = _settings.get("anthropic_api_key", "") or _settings.get("fc_anthropic_api_key", "")

    CYCLE_DIR  = "data/cycle"
    _os.makedirs(CYCLE_DIR, exist_ok=True)
    month_key  = target_date.strftime("%Y-%m")
    cycle_file = f"{CYCLE_DIR}/{month_key}.json"
    try:
        with open(cycle_file) as f:
            month_data = _json.load(f)
    except Exception:
        month_data = {}

    e = month_data.get(iso, {})
    cur_phase    = e.get("phase","")
    cur_cd_saved = str(e.get("cycle_day",""))
    cur_energy   = e.get("energy","")
    cur_mood     = e.get("mood","")
    cur_symptoms = e.get("symptoms","")
    cur_sleep    = e.get("sleep","")
    cur_cravings = e.get("cravings","")
    cur_stress   = e.get("stress","")

    phases = [
        ("Menstrual",    "CD 1\u20135",    "#c0392b", "LOW",           "Rest \u00b7 warmth \u00b7 simple meals \u00b7 no major decisions",
         "Not fertile \u00b7 avoid scheduling heavy cognitive work or social obligations"),
        ("Follicular",   "CD 6\u201312",   "#27ae60", "MEDIUM \u2192 HIGH", "Start projects \u00b7 plan ahead \u00b7 learn new things",
         "Pre-ovulatory \u00b7 fertility rising \u00b7 Peak days approaching"),
        ("Ovulatory",    "CD 13\u201316",  "#2980b9", "HIGH",          "Teach \u00b7 lead \u00b7 social tasks \u00b7 communication",
         "Peak fertile window \u00b7 highest likelihood of conception \u00b7 NFP: observe signs carefully"),
        ("Early Luteal", "CD 17\u201321",  "#8e44ad", "MEDIUM",        "Execute plans \u00b7 maintain structure",
         "Post-ovulation \u00b7 not fertile \u00b7 energy stable, use it well"),
        ("Late Luteal",  "CD 22\u201328",  "#e67e22", "LOW \u2192 VARIABLE", "Simplify \u00b7 protect emotional bandwidth",
         "Not fertile \u00b7 period approaching \u00b7 plan for lower capacity next week"),
    ]

    nutrition = {
        "Menstrual":    "\U0001f9b8 Iron-rich foods: red meat, lentils, spinach + Vitamin C",
        "Follicular":   "\U0001f957 Lean proteins and fresh vegetables",
        "Ovulatory":    "\u2696\ufe0f Balanced protein and carbs",
        "Early Luteal": "\U0001f35a Consistent structured meals",
        "Late Luteal":  "\U0001f36b Magnesium-rich: dark chocolate, nuts \u00b7 complex carbs for mood",
    }

    # Auto-detect phase from cycle log if not manually set today
    auto_cd       = 0
    auto_phase    = ""
    try:
        CYCLE_LOG = "data/cycle_log.json"
        if _os.path.exists(CYCLE_LOG):
            with open(CYCLE_LOG) as _f:
                _log = _json.load(_f)
            _dates = sorted([en["day1"] for en in _log if en.get("day1")])
            if _dates:
                from datetime import date as _dc
                _last = _dc.fromisoformat(_dates[-1])
                auto_cd = (target_date - _last).days + 1
                if   auto_cd <= 5:  auto_phase = "Menstrual"
                elif auto_cd <= 12: auto_phase = "Follicular"
                elif auto_cd <= 16: auto_phase = "Ovulatory"
                elif auto_cd <= 21: auto_phase = "Early Luteal"
                else:               auto_phase = "Late Luteal"
    except Exception:
        pass

    # Use auto-detected values as defaults if not yet saved today
    effective_phase = cur_phase or auto_phase
    effective_cd    = cur_cd_saved or (str(auto_cd) if auto_cd > 0 else "")

    # Build phase buttons with improved selected state
    phase_btns = ""
    for ph, cd_range, color, cap, guidance, fertility in phases:
        is_sel   = (effective_phase == ph)
        if is_sel:
            btn_style = (
                f"padding:10px 14px;border-radius:12px;cursor:pointer;"
                f"border:2.5px solid {color};background:{color};color:white;"
                f"font-family:inherit;transition:all 0.15s;text-align:left;line-height:1.4;"
                f"box-shadow:0 2px 8px {color}55;width:100%;"
            )
        else:
            btn_style = (
                f"padding:10px 14px;border-radius:12px;cursor:pointer;"
                f"border:1.5px solid {color};background:{color}10;color:{color};"
                f"font-family:inherit;transition:all 0.15s;text-align:left;line-height:1.4;"
                f"width:100%;"
            )
        phase_btns += (
            f'<button type="button" onclick="cycleSetPhase(this,\'{_e(ph)}\',\'{_e(cap)}\')" '
            f'data-phase="{_e(ph)}" data-capacity="{_e(cap)}" data-color="{color}" '
            f'style="{btn_style}">'
            f'<div style="font-weight:700;font-size:0.85em;">{_e(ph)}</div>'
            f'<div style="font-size:0.78em;margin-top:1px;opacity:0.85;">{_e(cd_range)} \u00b7 {_e(cap)}</div>'
            f'</button>'
        )

    # Hint panel
    hint_html = ""
    if effective_phase:
        ph_data = next((p for p in phases if p[0] == effective_phase), None)
        nutr    = nutrition.get(effective_phase, "")
        if ph_data:
            c = ph_data[2]
            hint_html = (
                f'<div class="cycle-hint" style="background:{c}15;border-left:3px solid {c};'
                f'border-radius:0 10px 10px 0;padding:10px 14px;margin-top:12px;">'
                f'<div class="cycle-hint-label" style="font-weight:700;font-size:0.85em;color:{c};'
                f'margin-bottom:3px;">{_e(ph_data[4])}</div>'
                f'<div style="font-size:0.78em;color:{c};opacity:0.8;margin-bottom:4px;">'
                f'\U0001f33a {_e(ph_data[5])}</div>'
                f'<div class="cycle-hint-nutr" style="font-size:0.8em;color:var(--ink-muted);">{_e(nutr)}</div>'
                f'</div>'
            )

    def sel(name, opts, cur):
        out  = f'<select id="cycle-{name}" onchange="cycleAutoSave()" '
        out += 'style="font-size:0.85em;padding:7px 10px;border-radius:8px;'
        out += 'border:1.5px solid var(--border);width:100%;font-family:inherit;">'
        out += '<option value="">—</option>'
        for o in opts:
            out += f'<option value="{_e(o)}" {"selected" if cur==o else ""}>{_e(o)}</option>'
        out += '</select>'
        return out

    # Build prediction panel
    prediction_html = ""
    try:
        CYCLE_LOG = "data/cycle_log.json"
        if _os.path.exists(CYCLE_LOG):
            with open(CYCLE_LOG) as _f2:
                _log2 = _json.load(_f2)
            _dates2 = sorted([en["day1"] for en in _log2 if en.get("day1")])
            if _dates2:
                from datetime import date as _dc2, timedelta as _tdd2
                _last2      = _dc2.fromisoformat(_dates2[-1])
                _lengths2   = []
                for _i2 in range(1, len(_dates2)):
                    try:
                        _lengths2.append((_dc2.fromisoformat(_dates2[_i2]) - _dc2.fromisoformat(_dates2[_i2-1])).days)
                    except Exception:
                        pass
                _avg2       = round(sum(_lengths2) / len(_lengths2)) if _lengths2 else 28
                _cd2        = (target_date - _last2).days + 1
                _next2      = _last2 + _tdd2(days=_avg2)
                _ovul2      = _last2 + _tdd2(days=13)
                _fs2        = _ovul2 - _tdd2(days=5)
                _fe2        = _ovul2 + _tdd2(days=1)
                _fertile2   = _fs2 <= target_date <= _fe2
                if   _cd2 <= 5:  _pp2 = ("Menstrual",    "#c0392b")
                elif _cd2 <= 12: _pp2 = ("Follicular",   "#27ae60")
                elif _cd2 <= 16: _pp2 = ("Ovulatory",    "#2980b9")
                elif _cd2 <= 21: _pp2 = ("Early Luteal", "#8e44ad")
                else:            _pp2 = ("Late Luteal",  "#e67e22")
                _nxt_lbl = _next2.strftime('%b %d, %Y')
                _fs_lbl  = _fs2.strftime('%b %d')
                _fe_lbl  = _fe2.strftime('%b %d')
                _ld_lbl  = _last2.strftime('%b %d, %Y')
                _fert_note = (
                    '<div style="background:#27ae6018;border-radius:8px;padding:8px 12px;'
                    'margin-top:8px;font-size:0.82em;color:#166634;font-weight:600;">'
                    '\U0001f33f Fertile window — est. ' + _fs_lbl + ' to ' + _fe_lbl + '</div>'
                ) if _fertile2 else (
                    '<div style="font-size:0.78em;color:var(--ink-faint);margin-top:6px;">'
                    'Fertile window est. ' + _fs_lbl + ' \u2013 ' + _fe_lbl + '</div>'
                )
                _cycle_count_note = f"(avg {_avg2} days, {len(_lengths2)} cycle{'s' if len(_lengths2)!=1 else ''})"

                # Period countdown warning
                from datetime import date as _dc2
                _days_until = (_next2 - target_date).days
                if _days_until <= 3:
                    _countdown_block = (
                        '<div style="margin-top:10px;padding:12px 14px;'
                        'background:#fef2f2;border:2px solid #fca5a5;border-radius:12px;'
                        'text-align:center;">'
                        '<div style="font-size:2.5rem;font-weight:900;color:#dc2626;line-height:1;">'
                        + str(_days_until) +
                        '</div>'
                        '<div style="font-size:0.78em;font-weight:700;color:#dc2626;margin-top:2px;">'
                        + ('Day of \u00b7 Plan for rest \U0001f534' if _days_until == 0 else
                           f'day{"" if _days_until == 1 else "s"} until your period \u26a0\ufe0f') +
                        '</div>'
                        '<div style="font-size:0.72em;color:#9b1c1c;margin-top:4px;">'
                        'Plan for LOW capacity \u00b7 simple meals \u00b7 rest &amp; warmth'
                        '</div></div>'
                    )
                elif _days_until <= 7:
                    _countdown_block = (
                        '<div style="margin-top:10px;padding:8px 12px;'
                        'background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;">'
                        '<span style="font-size:1.1rem;font-weight:800;color:#ea580c;">'
                        + str(_days_until) +
                        ' days</span>'
                        '<span style="font-size:0.78em;color:#9a3412;margin-left:6px;">'
                        'until period \u00b7 start simplifying plans this week'
                        '</span></div>'
                    )
                else:
                    _countdown_block = ""
                prediction_html = (
                    '<div style="background:#f5f0fa;border:1.5px solid #8e44ad30;border-radius:12px;'
                    'padding:14px;margin-bottom:14px;">'
                    '<div style="font-size:0.68em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;'
                    'color:#8e44ad;margin-bottom:10px;">Cycle Prediction</div>'
                    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">'
                    '<div><div style="font-size:0.72em;color:#888;margin-bottom:2px;">Last Day 1</div>'
                    f'<div style="font-weight:700;font-size:0.88em;">{_ld_lbl}</div></div>'
                    '<div><div style="font-size:0.72em;color:#888;margin-bottom:2px;">Today is cycle day</div>'
                    f'<div style="font-weight:700;font-size:0.88em;color:{_pp2[1]};">Day {_cd2} \u00b7 {_pp2[0]}</div></div>'
                    '<div style="grid-column:1/-1;"><div style="font-size:0.72em;color:#888;margin-bottom:2px;">Next Day 1 (est.)</div>'
                    f'<div style="font-weight:700;font-size:0.88em;">{_nxt_lbl} '
                    f'<span style="font-weight:400;color:#888;font-size:0.85em;">{_cycle_count_note}</span></div></div>'
                    '</div>' + _fert_note + _countdown_block +
                    '<div style="margin-top:10px;padding-top:8px;border-top:1px solid #e8d8f8;">'
                    '<a href="/settings#s-cycle" style="font-size:0.75em;color:#8e44ad;font-weight:600;'
                    'text-decoration:none;">Manage cycle log \u2192</a></div>'
                    '</div>'
                )
    except Exception:
        prediction_html = ""

    # Detail fields section (optional)
    detail_section = ""
    if _show_detail:
        detail_section = f"""
<div class="card" style="margin-bottom:4px;">
  <div style="font-size:0.7em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:12px;">Daily Check-In</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
    <div>
      <label style="font-size:0.75em;font-weight:700;color:var(--ink-faint);">Cycle Day #</label>
      <input type="number" id="cycle-day" min="1" max="35"
             value="{_e(effective_cd)}" onchange="cycleAutoSave()"
             style="width:100%;padding:7px 10px;font-size:0.88em;border-radius:8px;
                    border:1.5px solid var(--border);font-family:inherit;margin-top:4px;">
    </div>
    <div>
      <label style="font-size:0.75em;font-weight:700;color:var(--ink-faint);">Energy</label>
      <div style="margin-top:4px;">{sel("energy", ["High","Medium","Low"], cur_energy)}</div>
    </div>
    <div>
      <label style="font-size:0.75em;font-weight:700;color:var(--ink-faint);">Mood</label>
      <input type="text" id="cycle-mood" value="{_e(cur_mood)}"
             placeholder="e.g. calm, irritable" onchange="cycleAutoSave()"
             style="width:100%;padding:7px 10px;font-size:0.85em;border-radius:8px;
                    border:1.5px solid var(--border);font-family:inherit;margin-top:4px;">
    </div>
    <div>
      <label style="font-size:0.75em;font-weight:700;color:var(--ink-faint);">Sleep</label>
      <div style="margin-top:4px;">{sel("sleep", ["Great","Good","Fair","Poor"], cur_sleep)}</div>
    </div>
    <div>
      <label style="font-size:0.75em;font-weight:700;color:var(--ink-faint);">Symptoms</label>
      <input type="text" id="cycle-symptoms" value="{_e(cur_symptoms)}"
             placeholder="e.g. cramps, fatigue" onchange="cycleAutoSave()"
             style="width:100%;padding:7px 10px;font-size:0.85em;border-radius:8px;
                    border:1.5px solid var(--border);font-family:inherit;margin-top:4px;">
    </div>
    <div>
      <label style="font-size:0.75em;font-weight:700;color:var(--ink-faint);">Stress</label>
      <div style="margin-top:4px;">{sel("stress", ["Low","Medium","High"], cur_stress)}</div>
    </div>
    <div style="grid-column:1/-1;">
      <label style="font-size:0.75em;font-weight:700;color:var(--ink-faint);">Cravings</label>
      <input type="text" id="cycle-cravings" value="{_e(cur_cravings)}"
             placeholder="e.g. chocolate, carbs, salty" onchange="cycleAutoSave()"
             style="width:100%;padding:7px 10px;font-size:0.85em;border-radius:8px;
                    border:1.5px solid var(--border);font-family:inherit;margin-top:4px;">
    </div>
  </div>
  {_save_bar("cycle", show_save=False)}
</div>"""
    else:
        detail_section = f"""
<div style="text-align:right;margin-bottom:8px;">
  <a href="/settings#s-cycle" style="font-size:0.75em;color:var(--ink-faint);text-decoration:none;">
    \u2699 Enable detail tracking
  </a>
</div>
{_save_bar("cycle", show_save=False)}"""

    # AI suggestions button (only if API key set)
    ai_btn = ""
    if _api_key:
        ai_btn = f"""
<div class="card" style="margin-bottom:12px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:8px;">AI Planning Suggestions</div>
  <button onclick="cycleAiSuggest()"
          style="width:100%;padding:11px 16px;background:linear-gradient(135deg,#1c1610,#2a1e10);
                 color:var(--gold-light);border:none;border-radius:10px;font-size:0.88em;
                 font-weight:600;font-family:inherit;cursor:pointer;text-align:left;">
    \u2728 How should I plan today?
  </button>
  <div id="cycle-ai-result" style="display:none;margin-top:12px;padding:12px 14px;
       background:#faf8f5;border-radius:10px;border-left:3px solid var(--gold);
       font-size:0.88em;line-height:1.65;color:var(--ink);"></div>
  <div id="cycle-ai-loading" style="display:none;text-align:center;padding:12px;
       font-size:0.82em;color:var(--ink-faint);">\u231b Thinking...</div>
</div>"""

    hints_js = _json.dumps({p[0]: [p[2], p[4], nutrition.get(p[0], ""), p[5]] for p in phases})
    _cycle_header = _step_header("Step 2 \u00b7 Cycle Check-In", "Private \u00b7 only visible to you", "s-cycle")
    _eff_phase_js = _e(effective_phase)
    _eff_cd_js    = _e(effective_cd)

    return f"""
{_cycle_header}

{prediction_html}

<!-- Phase selector -->
<div class="card" style="margin-bottom:12px;">
  <div style="font-size:0.72em;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:10px;">
    Phase
    {('<span style="font-size:0.85em;font-weight:400;color:#8e44ad;margin-left:6px;">'
      '(auto-detected from your cycle log)</span>') if auto_phase and not cur_phase else ''}
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
    {phase_btns}
  </div>
  {hint_html}
</div>

{ai_btn}

{detail_section}

<script>
var _cycleIso   = '{_e(iso)}';
var _cyclePhase = '{_eff_phase_js}';
var _cycleTimer = null;
var _cycleHints = {hints_js};

// Auto-select phase on load if not already set
(function() {{
  var ph = '{_eff_phase_js}';
  if (ph) {{
    var btn = document.querySelector('[data-phase="' + ph + '"]');
    if (btn) {{
      document.querySelectorAll('[data-phase]').forEach(function(b) {{
        var c = b.dataset.color;
        b.style.background = c + '10';
        b.style.color = c;
        b.style.border = '1.5px solid ' + c;
        b.style.boxShadow = '';
      }});
      btn.style.background = btn.dataset.color;
      btn.style.color = 'white';
      btn.style.border = '2.5px solid ' + btn.dataset.color;
      btn.style.boxShadow = '0 2px 8px ' + btn.dataset.color + '55';
    }}
  }}
}})();

function cycleSetPhase(btn, phase, capacity) {{
  _cyclePhase = phase;
  // Reset all buttons
  document.querySelectorAll('[data-phase]').forEach(function(b) {{
    var c = b.dataset.color;
    b.style.background = c + '10';
    b.style.color = c;
    b.style.border = '1.5px solid ' + c;
    b.style.boxShadow = '';
  }});
  // Highlight selected
  btn.style.background = btn.dataset.color;
  btn.style.color = 'white';
  btn.style.border = '2.5px solid ' + btn.dataset.color;
  btn.style.boxShadow = '0 2px 8px ' + btn.dataset.color + '55';
  // Update hint
  var h = _cycleHints[phase];
  var hintEl = document.querySelector('.cycle-hint');
  if (hintEl && h) {{
    hintEl.style.background = h[0] + '15';
    hintEl.style.borderLeftColor = h[0];
    hintEl.querySelector('.cycle-hint-label').style.color = h[0];
    hintEl.querySelector('.cycle-hint-label').textContent = h[1];
    hintEl.querySelector('.cycle-hint-nutr').textContent  = h[2];
  }}
  cycleAutoSave();
}}

function cycleAutoSave() {{
  clearTimeout(_cycleTimer);
  _cycleTimer = setTimeout(cycleSave, 800);
}}

function cycleSave() {{
  var g = function(id) {{ var el = document.getElementById(id); return el ? el.value : ''; }};
  var data = {{
    phase:     _cyclePhase,
    cycle_day: g('cycle-day'),
    energy:    g('cycle-energy'),
    mood:      g('cycle-mood'),
    symptoms:  g('cycle-symptoms'),
    sleep:     g('cycle-sleep'),
    cravings:  g('cycle-cravings'),
    stress:    g('cycle-stress'),
  }};
  fetch('/cycle-save', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'iso=' + encodeURIComponent(_cycleIso) + '&data=' + encodeURIComponent(JSON.stringify(data))
  }}).then(function() {{
    var el = document.getElementById('save-status-cycle');
    if (el) {{ el.textContent = 'Saved \u2713'; setTimeout(function() {{ el.textContent = ''; }}, 2000); }}
  }});
}}
window._saveStep_cycle = cycleSave;

function cycleAiSuggest() {{
  var g = function(id) {{ var el = document.getElementById(id); return el ? el.value : ''; }};
  var loading = document.getElementById('cycle-ai-loading');
  var result  = document.getElementById('cycle-ai-result');
  if (loading) loading.style.display = 'block';
  if (result)  result.style.display  = 'none';

  var payload = {{
    phase:    _cyclePhase || 'unknown',
    cycle_day: g('cycle-day'),
    energy:   g('cycle-energy'),
    mood:     g('cycle-mood'),
    symptoms: g('cycle-symptoms'),
    stress:   g('cycle-stress'),
    iso:      _cycleIso,
  }};

  fetch('/cycle-ai-suggest', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'data=' + encodeURIComponent(JSON.stringify(payload))
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (loading) loading.style.display = 'none';
    if (result) {{
      result.style.display = 'block';
      result.innerHTML = d.suggestion || d.error || 'No suggestion returned.';
    }}
  }}).catch(function(err) {{
    if (loading) loading.style.display = 'none';
    if (result) {{ result.style.display = 'block'; result.textContent = 'Error — check your API key in Settings.'; }}
  }});
}}
</script>
"""


# ── STEP 3: Meals ─────────────────────────────────────────────────────────────

# ── STEP 3: Meals ─────────────────────────────────────────────────────────────
def _render_meals_step(iso: str, target_date) -> str:
    import json as _json, os as _os
    from html import escape as _e
    from datetime import date as _date

    try:
        from render_meals import load_meal_plan, _week_key, MEAL_SLOT_LABELS
        wk    = _week_key(target_date)
        plan  = load_meal_plan(wk)
        day   = target_date.strftime("%A")
        slots = plan.get("days", {}).get(day, {})
        prep_note = plan.get("prep_notes", {}).get(day, "").strip()
    except Exception:
        slots = {}
        prep_note = ""

    # Cycle nutrition nudge
    nudge = ""
    try:
        month_key  = target_date.strftime("%Y-%m")
        cycle_file = f"data/cycle/{month_key}.json"
        if _os.path.exists(cycle_file):
            with open(cycle_file) as f:
                month_data = _json.load(f)
            entry = month_data.get(iso, {})
            phase = entry.get("phase","")
            nutr  = {
                "Menstrual":    ("🩸","Iron-rich focus","red meat, lentils, spinach + Vitamin C","#c0392b"),
                "Follicular":   ("🥗","Light & fresh","lean proteins, fresh vegetables","#27ae60"),
                "Ovulatory":    ("⚖️","Balanced","adequate protein and carbs","#2980b9"),
                "Early Luteal": ("🍚","Consistent","structured, regular meals","#8e44ad"),
                "Late Luteal":  ("🍫","Magnesium-rich","dark chocolate, nuts — complex carbs for mood","#e67e22"),
            }
            if phase in nutr:
                icon, label, detail, color = nutr[phase]
                nudge = (
                    f'<div style="background:{color}12;border:1px solid {color}30;'
                    f'border-radius:10px;padding:10px 14px;margin-bottom:12px;'
                    f'display:flex;align-items:flex-start;gap:10px;">'
                    f'<span style="font-size:1.2em;flex-shrink:0;">{icon}</span>'
                    f'<div><div style="font-weight:700;font-size:0.82em;color:{color};">{_e(label)}</div>'
                    f'<div style="font-size:0.78em;color:var(--ink-muted);margin-top:2px;">{_e(detail)}</div></div>'
                    f'</div>'
                )
    except Exception:
        pass

    icons = {"breakfast":"☀️","lunch":"🥗","dinner":"🍽","dessert":"🍮","snacks":"🍎","dad_lunch":"💼"}
    labels = {"breakfast":"Breakfast","lunch":"Lunch","dinner":"Dinner","dessert":"Dessert","snacks":"Snacks","dad_lunch":"Dad's Lunch"}

    from render_meals import slot_display_text as _slot_text
    meal_rows = ""
    has_meals = False
    for slot in ["breakfast","lunch","dinner","dessert","snacks","dad_lunch"]:
        val = _slot_text(slots.get(slot))
        if not val: continue
        has_meals = True
        icon  = icons.get(slot,"")
        label = labels.get(slot, slot)
        meal_rows += (
            f'<div style="display:flex;align-items:flex-start;gap:12px;padding:10px 0;'
            f'border-bottom:1px solid var(--border-light);">'
            f'<div style="width:85px;flex-shrink:0;">'
            f'<div style="font-size:0.7em;font-weight:700;color:var(--ink-faint);'
            f'text-transform:uppercase;letter-spacing:.06em;">{icon} {_e(label)}</div></div>'
            f'<div style="flex:1;font-size:0.9em;color:var(--ink);">{_e(val)}</div>'
            f'</div>'
        )

    if not has_meals:
        return (
            f'{_step_header("Step 3 · Meals", "No meal plan for this week yet", "meals")}' +
            '<div class="card" style="text-align:center;padding:32px;">' +
            '<p style="color:var(--ink-muted);margin-bottom:16px;">No meal plan found for this week.</p>' +
            '<div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;">' +
            '<a href="/meals" style="padding:10px 20px;background:var(--ink);color:var(--gold-light);' +
            'border-radius:10px;font-size:0.85em;font-weight:700;text-decoration:none;">🍽 Plan This Week</a>' +
            '<a href="/settings#s-meals" style="padding:10px 16px;background:var(--parchment);color:var(--ink);' +
            'border-radius:10px;font-size:0.85em;border:1.5px solid var(--border);text-decoration:none;">⚙ Meal Rules</a>' +
            '</div></div>'
        )

    # Prep note as individual add-able steps
    prep_items = []
    if prep_note:
        import re as _re
        parts = _re.split(r'[·•\.\n]+', prep_note)
        prep_items = [p.strip() for p in parts if p.strip()]

    prep_html = ""
    if prep_items:
        item_rows = ""
        for i, item in enumerate(prep_items):
            item_rows += (
                f'<div style="display:flex;align-items:center;gap:10px;padding:7px 0;'
                f'border-bottom:1px solid var(--border-light);" id="prep-item-{i}">'
                f'<span style="flex:1;font-size:0.85em;">{_e(item)}</span>'
                f'<button onclick="addPrepToDay({i},\'{_e(item.replace(chr(39),chr(39)))}\',this)" '
                f'style="font-size:0.75em;padding:4px 10px;border-radius:6px;'
                f'background:var(--parchment);color:var(--ink);border:1.5px solid var(--border);'
                f'cursor:pointer;font-family:inherit;white-space:nowrap;flex-shrink:0;">+ Add to day</button>'
                f'</div>'
            )
        prep_html = (
            f'<div style="margin-top:14px;padding:12px 14px;background:#f0fdf4;border-radius:10px;">' +
            f'<div style="font-size:0.7em;font-weight:700;letter-spacing:.1em;text-transform:uppercase;' +
            f'color:#166534;margin-bottom:8px;">Today\'s Prep Steps</div>' +
            item_rows +
            f'<div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;">' +
            f'<button onclick="addAllPrep()" style="font-size:0.78em;padding:6px 14px;border-radius:8px;' +
            f'background:var(--ink);color:var(--gold-light);border:none;cursor:pointer;' +
            f'font-family:inherit;font-weight:600;">+ Add all prep steps to my day</button>' +
            f'</div></div>'
        )

    prep_items_js = _json.dumps(prep_items)
    _meals_header = _step_header(
        "Step 3 \u00b7 Meals",
        target_date.strftime('%A \u00b7 %B %d'),
        "meals"
    )

    return f"""
{_meals_header}

{nudge}

<div class="card" style="margin-bottom:12px;">
  {meal_rows}
  {prep_html}
  <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
    <a href="/meals" style="font-size:0.82em;color:var(--brown);font-weight:700;text-decoration:none;">
      Edit meal plan &rarr;
    </a>
    <span style="color:var(--border);">|</span>
    <a href="/lorenzo" style="font-size:0.82em;color:#8b3a1a;font-weight:700;text-decoration:none;">&#127860; Ask Lorenzo</a>
    <span style="color:var(--border);">|</span>
    <a href="/settings#s-meals" style="font-size:0.78em;color:var(--ink-faint);text-decoration:none;">⚙ Meal rules</a>
  </div>
</div>

<div id="meals-add-status" style="font-size:0.82em;color:#27ae60;min-height:20px;padding:4px 0;"></div>

<script>
var _mealsIso       = '{_e(iso)}';
var _prepItems      = {prep_items_js};
var _mealsAddedIdxs = {{}};

function addPrepToDay(idx, text, btn) {{
  if (_mealsAddedIdxs[idx]) return;
  _mealsAddedIdxs[idx] = true;
  btn.textContent = '✓ Added';
  btn.style.color = '#27ae60';
  btn.style.borderColor = '#27ae60';
  btn.disabled = true;
  _addTaskToDay(text);
}}

function addAllPrep() {{
  _prepItems.forEach(function(item, i) {{
    if (!_mealsAddedIdxs[i]) {{
      _mealsAddedIdxs[i] = true;
      var btn = document.querySelector('#prep-item-' + i + ' button');
      if (btn) {{ btn.textContent='✓ Added'; btn.style.color='#27ae60'; btn.disabled=true; }}
      _addTaskToDay(item);
    }}
  }});
  var st = document.getElementById('meals-add-status');
  if (st) st.textContent = 'All prep steps added to your plan ✓';
}}

function _addTaskToDay(text) {{
  fetch('/add-to-plan-quick', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'iso=' + encodeURIComponent(_mealsIso) + '&text=' + encodeURIComponent(text) + '&source=meal_prep'
  }});
}}
</script>
"""


# ── STEP 4: Calendar ──────────────────────────────────────────────────────────
def _render_calendar_step(iso: str, target_date) -> str:
    from html import escape as _e
    from render_calendar import render_calendar_today_strip

    # Week strip (Mon–Sun)
    mon   = target_date - timedelta(days=target_date.weekday())
    days  = [mon + timedelta(days=i) for i in range(7)]
    day_labels = ["MON","TUE","WED","THU","FRI","SAT","SUN"]

    week_cells = ""
    for i, d in enumerate(days):
        is_today = (d == target_date)
        num_style = (
            "background:var(--ink);color:var(--gold-light);border-radius:50%;width:30px;height:30px;"
            "display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.88em;"
            if is_today else
            "color:var(--ink-muted);width:30px;height:30px;display:flex;align-items:center;"
            "justify-content:center;font-size:0.88em;"
        )
        week_cells += (
            f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;">' +
            f'<div style="font-size:9px;font-weight:700;letter-spacing:.06em;color:var(--ink-faint);">' +
            f'{day_labels[i]}</div>' +
            f'<div style="{num_style}">{d.day}</div>' +
            f'</div>'
        )

    # Today's events — with "Add to plan" buttons
    import json as _json2
    today_events_html = ""
    _raw_today = []
    try:
        from render_calendar import get_all_events as _get_all
        _raw_today = _get_all(iso)
    except Exception:
        pass

    if _raw_today:
        from daily_schedule_engine import fmt_time_12h as _fmt12
        for ev in _raw_today:
            ev_title   = ev.get("title", "(event)")
            ev_start   = ev.get("start", "")
            ev_all_day = ev.get("all_day", False)
            ev_color   = ev.get("color", "#3498db")
            ev_loc     = ev.get("location", "") or ""
            ev_cal_name = _e(ev.get("calendar", ""))
            if not ev_all_day and "T" in ev_start:
                hhmm      = ev_start.split("T")[1][:5]
                time_disp = _fmt12(hhmm)
                time_plan = time_disp
            else:
                time_disp = "All day"
                time_plan = ""
            label_plan = ev_title + (f" \u2022 {ev_loc}" if ev_loc else "")
            btn_id = "eadd-" + str(abs(hash(ev_title + ev_start)))[-6:]
            add_onclick = (
                f"(function(b){{"
                f"if(window.addToPlan){{"
                f"window.addToPlan({_json2.dumps(label_plan)},'calendar',{_json2.dumps(ev_color)},{_json2.dumps(time_plan)});"
                f"b.textContent='\u2713 Added';b.disabled=true;"
                f"b.style.background='#27ae60';b.style.color='white';"
                f"}}}})(document.getElementById('{btn_id}'))"
            )
            today_events_html += (
                f'<div style="display:flex;align-items:center;gap:10px;padding:8px 0;'
                f'border-bottom:1px solid var(--border-light);">'
                f'<span style="width:8px;height:8px;border-radius:50%;background:{ev_color};flex-shrink:0;"></span>'
                f'<div style="flex:1;min-width:0;">'
                f'<div style="font-size:0.88em;font-weight:600;color:var(--ink);">{_e(ev_title)}'
                + (f'<span style="font-size:0.8em;font-weight:400;color:var(--ink-faint);margin-left:6px;">{_e(ev_loc)}</span>' if ev_loc else '') +
                f'</div>'
                f'<div style="font-size:0.75em;color:var(--ink-faint);">{_e(time_disp)}'
                + (f' · {ev_cal_name}' if ev_cal_name else '') +
                f'</div></div>'
                f'<button id="{btn_id}" onclick="{add_onclick}" '
                f'style="flex-shrink:0;font-size:0.75em;padding:4px 10px;border-radius:6px;'
                f'background:var(--parchment);color:var(--brown);font-weight:700;'
                f'border:1.5px solid var(--border);cursor:pointer;font-family:inherit;white-space:nowrap;">'
                f'+ Add to plan</button>'
                f'</div>'
            )
    else:
        try:
            today_events_html = render_calendar_today_strip(iso)
        except Exception:
            today_events_html = '<p class="muted" style="font-size:0.85em;padding:4px 0;">No events today.</p>'

    # Upcoming this week (next 6 days)
    upcoming_html = ""
    try:
        from render_calendar import get_all_events
        all_events  = get_all_events()
        week_end    = target_date + timedelta(days=7)
        upcoming    = [e for e in all_events
                       if target_date.isoformat() < e.get("date","") <= week_end.isoformat()]
        upcoming    = sorted(upcoming, key=lambda e: e.get("date",""))[:8]
        if upcoming:
            rows = ""
            for ev in upcoming:
                ev_date = ev.get("date","")
                try:
                    from datetime import date as _date2
                    ev_d    = _date2.fromisoformat(ev_date)
                    ev_label = ev_d.strftime("%a %b %d")
                except Exception:
                    ev_label = ev_date
                ev_title = _e(ev.get("title","(event)"))
                ev_cal   = _e(ev.get("calendar",""))
                rows += (
                    f'<div style="display:flex;gap:10px;padding:7px 0;' +
                    f'border-bottom:1px solid var(--border-light);">' +
                    f'<div style="font-size:0.75em;color:var(--ink-faint);min-width:72px;">{ev_label}</div>' +
                    f'<div><div style="font-size:0.85em;font-weight:600;color:var(--ink);">{ev_title}</div>' +
                    f'<div style="font-size:0.75em;color:var(--ink-faint);">{ev_cal}</div></div>' +
                    f'</div>'
                )
            upcoming_html = (
                '<div class="card" style="margin-top:12px;">' +
                '<div style="font-size:0.7em;font-weight:700;letter-spacing:.1em;text-transform:uppercase;' +
                'color:var(--ink-faint);margin-bottom:10px;">Coming this week</div>' +
                rows + '</div>'
            )
    except Exception:
        pass

    _calendar_header = _step_header(
        "Step 4 \u00b7 Calendar",
        target_date.strftime('%B %d, %Y'),
        "calendar"
    )

    return f"""
{_calendar_header}

<div class="card" style="padding:12px 16px;margin-bottom:12px;">
  <div style="display:flex;gap:4px;">{week_cells}</div>
</div>

<div class="card" style="margin-bottom:12px;">
  <div style="font-size:0.7em;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:10px;">Today's Events</div>
  {today_events_html}
  <div style="margin-top:10px;border-top:1px solid var(--border-light);padding-top:8px;
              display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
    <a href="/calendar" style="font-size:0.82em;color:var(--brown);font-weight:700;text-decoration:none;">
      Full calendar &rarr;
    </a>
    <span style="color:var(--border);">|</span>
    <a href="/settings#s-integrations" style="font-size:0.78em;color:var(--ink-faint);text-decoration:none;">
      ⚙ Calendar settings
    </a>
  </div>
</div>

<div class="card" style="margin-bottom:12px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <div style="font-size:0.7em;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
                color:var(--ink-faint);">Add Quick Event</div>
    <button onclick="toggleAddEvent()"
            style="font-size:0.75em;padding:4px 10px;border-radius:6px;
                   background:var(--parchment);color:var(--ink);
                   border:1.5px solid var(--border);cursor:pointer;font-family:inherit;">
      + Add event
    </button>
  </div>
  <div id="add-event-form" style="display:none;">
    <form method="POST" action="/calendar-add-event">
      <input type="hidden" name="date" value="{iso}">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;">
        <div style="grid-column:1/-1;">
          <label style="font-size:0.75em;">Event title</label>
          <input type="text" name="title" required placeholder="e.g. Co-op drop-off" style="margin-top:4px;">
        </div>
        <div>
          <label style="font-size:0.75em;">Start time</label>
          <input type="time" name="start_time" style="margin-top:4px;">
        </div>
        <div>
          <label style="font-size:0.75em;">End time</label>
          <input type="time" name="end_time" style="margin-top:4px;">
        </div>
        <div style="grid-column:1/-1;">
          <label style="font-size:0.75em;">Notes (optional)</label>
          <input type="text" name="notes" placeholder="Location, details..." style="margin-top:4px;">
        </div>
      </div>
      <div style="display:flex;gap:8px;">
        <button type="submit"
                style="padding:8px 18px;background:var(--ink);color:var(--gold-light);
                       border:none;border-radius:8px;font-size:0.85em;font-family:inherit;
                       font-weight:600;cursor:pointer;">Save Event</button>
        <button type="button" onclick="toggleAddEvent()"
                style="padding:8px 14px;background:transparent;color:var(--ink-muted);
                       border:1.5px solid var(--border);border-radius:8px;
                       font-size:0.85em;font-family:inherit;cursor:pointer;">Cancel</button>
      </div>
    </form>
  </div>
</div>

{upcoming_html}

<script>
function toggleAddEvent() {{
  var f = document.getElementById('add-event-form');
  if (f) f.style.display = f.style.display === 'none' ? 'block' : 'none';
}}
</script>
"""



# ── STEP 5: Tasks ─────────────────────────────────────────────────────────────
def _render_tasks_step(iso: str) -> str:
    from html import escape as _e
    import json as _json
    from datetime import date as _date, timedelta as _td

    tasks   = load_manual_tasks()
    active  = [t for t in tasks
               if isinstance(t,dict) and t.get("status","active")=="active"
               and t.get("scheduled_for","") != iso]

    if not active:
        return (
            f'{_step_header("Step 5 · Tasks", "No active tasks today")}' +
            '<div class="card" style="text-align:center;padding:28px;">' +
            '<p style="color:var(--ink-muted);margin-bottom:14px;">All clear — no active tasks.</p>' +
            '<a href="/tasks" style="font-size:0.82em;color:var(--brown);font-weight:700;text-decoration:none;">'
            'Manage tasks &rarr;</a></div>'
        )

    # Date anchors for bucketing + due-date labels (anchored to the planned day)
    try:
        target_date = _date.fromisoformat(iso)
    except Exception:
        target_date = _date.today()
    today_iso = target_date.isoformat()  # normalized — safe for string compare
    tomorrow  = target_date + _td(days=1)
    week_out  = target_date + _td(days=7)

    def _norm_pri(p) -> str:
        return (p or "").upper() if isinstance(p, str) else ""

    def _due_label(due_str: str) -> str:
        if not due_str:
            return "no date"
        try:
            d = _date.fromisoformat(due_str)
        except Exception:
            return ""
        if d == target_date:
            return "today"
        if d == tomorrow:
            return "tomorrow"
        if target_date < d <= week_out:
            return d.strftime("%a")
        return f"{d.strftime('%b')} {d.day}"

    # Bucket: Overdue / Someday / Active
    # Someday = undated AND priority is LOW or unset/missing.
    # HIGH/MEDIUM tasks without a due date stay in Active with a "no date" label.
    priority_order = {"HIGH":0,"MEDIUM":1,"LOW":2}
    overdue_list = []
    someday_list = []
    active_list  = []
    for t in active:
        due  = (t.get("due_date") or "").strip()
        if due and due < today_iso:
            overdue_list.append(t)
        elif (not due) and _norm_pri(t.get("priority")) in ("", "LOW"):
            someday_list.append(t)
        else:
            active_list.append(t)

    # Sort: due_date asc first (undated to bottom via "9999" sentinel),
    # then priority (HIGH first) as tiebreaker. Normalize priority case so
    # lowercase/missing values still sort to a sensible bucket.
    def _sort_key(t):
        return (t.get("due_date","") or "9999",
                priority_order.get(_norm_pri(t.get("priority")) or "MEDIUM", 1))
    overdue_list.sort(key=_sort_key)
    active_list.sort(key=_sort_key)
    someday_list.sort(key=lambda t: (t.get("text","") or "").lower())

    pri_colors = {"HIGH":"#c0392b","MEDIUM":"#e67e22","LOW":"#27ae60"}

    # Per-task assignee/priority option builders for the inline edit panel.
    def _assn_opts(cur):
        cur = cur or ""
        out = '<option value=""' + (' selected' if not cur else '') + '>Anyone</option>'
        seen = set()
        for p in ASSIGNABLE_TO:
            ep = _e(p); seen.add(p)
            out += f'<option value="{ep}"' + (' selected' if cur==p else '') + f'>{ep}</option>'
        if cur and cur not in seen:
            out += f'<option value="{_e(cur)}" selected>{_e(cur)}</option>'
        return out

    def _prio_opts(cur):
        cur = (cur or "MEDIUM").upper()
        return "".join(
            f'<option value="{p}"' + (' selected' if p==cur else '') + f'>{p}</option>'
            for p in ("HIGH","MEDIUM","LOW")
        )

    def _recur_summary(t):
        if not t.get("recurring"): return "Does not repeat"
        try:
            from data_helpers import format_recurrence_label as _frl
            lbl = _frl(t) or "Repeats"
        except Exception:
            lbl = "Repeats"
        extra = ""
        if t.get("end_date"):
            extra = f" until {_e(t['end_date'])}"
        elif t.get("occurrences_remaining"):
            extra = f" ({t['occurrences_remaining']} left)"
        return f"\u21bb {_e(lbl)}{extra}"

    def _row(i, t, badge_html=""):
        tid_raw = t.get("id","") or str(i)
        tid   = _e(tid_raw)
        text  = _e(t.get("text",""))
        pri   = _norm_pri(t.get("priority")) or "MEDIUM"
        due   = t.get("due_date","") or ""
        pc    = pri_colors.get(pri,"#888")
        label = _due_label(due)
        label_html = (
            f'<span style="font-size:0.72em;color:var(--ink-faint);'
            f'margin-right:6px;white-space:nowrap;flex-shrink:0;">{_e(label)}</span>'
            if label else ""
        )
        is_rec = bool(t.get("recurring"))
        # Hidden inline edit panel below the row. Mirrors the pi-card visual
        # (white bg, subtle border, rounded). Recurrence area is collapsed
        # behind an "Edit recurrence" reveal to keep the panel small.
        edit_panel_html = (
            f'<div id="step-task-edit-{tid}" data-task-edit="{tid}" '
            f'style="display:none;margin:6px 0 10px;padding:12px;background:#fff;'
            f'border:1px solid var(--border);border-radius:10px;">'
            f'<input type="hidden" name="id" value="{tid}">'
            f'<label style="font-size:0.78em;font-weight:700;color:var(--ink-muted);'
            f'margin:0 0 4px;display:block;">Task</label>'
            f'<input type="text" name="text" value="{text}" style="margin:0 0 8px;width:100%;">'
            f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">'
            f'<div style="flex:1;min-width:120px;">'
            f'<label style="font-size:0.78em;font-weight:700;color:var(--ink-muted);'
            f'margin:0 0 4px;display:block;">Assigned to</label>'
            f'<select name="assigned_to" style="margin:0;width:100%;">{_assn_opts(t.get("assigned_to",""))}</select>'
            f'</div><div style="flex:1;min-width:120px;">'
            f'<label style="font-size:0.78em;font-weight:700;color:var(--ink-muted);'
            f'margin:0 0 4px;display:block;">Due date</label>'
            f'<input type="date" name="due_date" value="{_e(due)}" style="margin:0;width:100%;">'
            f'</div><div style="flex:1;min-width:100px;">'
            f'<label style="font-size:0.78em;font-weight:700;color:var(--ink-muted);'
            f'margin:0 0 4px;display:block;">Priority</label>'
            f'<select name="priority" style="margin:0;width:100%;">{_prio_opts(t.get("priority",""))}</select>'
            f'</div></div>'
            # Recurrence summary + reveal
            f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0;'
            f'font-size:0.82em;color:var(--ink-muted);">'
            f'<span style="flex:1;min-width:0;">{_recur_summary(t)}</span>'
            f'<a href="#" onclick="taskEditRecurToggle(\'{tid}\');return false;" '
            f'style="font-size:0.78em;color:var(--brown);font-weight:700;text-decoration:none;'
            f'flex-shrink:0;">Edit recurrence</a>'
            f'</div>'
            f'<div id="step-task-recur-wrap-{tid}" style="display:none;margin-top:6px;">'
            f'<label style="display:flex;align-items:center;gap:8px;cursor:pointer;margin-bottom:4px;font-size:0.85em;">'
            f'<input type="checkbox" id="recur-toggle-{tid}" name="recurring" value="true"'
            f'{(" checked" if is_rec else "")}'
            f' onchange="(function(cb){{document.getElementById(\'recur-fields-{tid}\').style.display=cb.checked?\'\':\'none\';}})(this)"'
            f' style="width:auto;margin:0;">'
            f'<span>Repeat</span></label>'
            f'{_recur_editor_html(tid_raw, t)}'
            f'</div>'
            f'<div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;">'
            f'<button type="button" onclick="taskEditSaveStep(\'{tid}\',this)" '
            f'style="background:var(--navy,#1e3566);color:#fff;border:none;'
            f'border-radius:8px;padding:8px 14px;font-weight:700;cursor:pointer;font-family:inherit;">'
            f'Save</button>'
            f'<button type="button" onclick="taskEditDoneStep(\'{tid}\',this)" '
            f'style="background:transparent;color:var(--green,#16a34a);'
            f'border:1.5px solid var(--green,#16a34a);'
            f'border-radius:8px;padding:7px 14px;font-weight:700;cursor:pointer;font-family:inherit;">'
            f'\u2713 Mark done</button>'
            f'<button type="button" onclick="taskEditOpenStep(\'{tid}\')" '
            f'style="background:transparent;color:var(--ink-muted);border:1.5px solid var(--border);'
            f'border-radius:8px;padding:7px 14px;font-weight:600;cursor:pointer;font-family:inherit;">'
            f'Cancel</button>'
            f'</div></div>'
        )
        visible_row = (
            f'<div style="display:flex;align-items:center;gap:10px;padding:9px 0;'
            f'border-bottom:1px solid var(--border-light);">'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{pc};'
            f'flex-shrink:0;display:inline-block;"></span>'
            f'<div style="flex:1;min-width:0;display:flex;align-items:center;">'
            f'{label_html}'
            f'<div style="font-size:0.88em;color:var(--ink);flex:1;min-width:0;">{text}</div>'
            f'{badge_html}'
            f'</div>'
            f'<button onclick="taskEditOpenStep(\'{tid}\')" '
            f'style="font-size:0.72em;padding:4px 8px;border-radius:6px;'
            f'background:transparent;color:var(--ink-muted);border:1.5px solid var(--border);'
            f'cursor:pointer;font-family:inherit;white-space:nowrap;flex-shrink:0;">\u270e Edit</button>'
            f'<button onclick="addTaskToDay(\'{tid}\',\'{text.replace(chr(39),"")}\',this)" '
            f'style="font-size:0.75em;padding:4px 10px;border-radius:6px;'
            f'background:var(--parchment);color:var(--ink);border:1.5px solid var(--border);'
            f'cursor:pointer;font-family:inherit;white-space:nowrap;flex-shrink:0;">+ Add to day</button>'
            f'</div>'
        )
        return f'<div data-task-row="{tid}">{visible_row}{edit_panel_html}</div>'

    # ── Section 1: Overdue (no cap, red, always visible when non-empty) ─
    overdue_html = ""
    if overdue_list:
        overdue_badge = (
            '<span style="font-size:0.62em;font-weight:700;color:#fff;background:#c0392b;'
            'padding:2px 6px;border-radius:4px;margin-left:6px;text-transform:uppercase;'
            'letter-spacing:0.04em;flex-shrink:0;">Overdue</span>'
        )
        overdue_rows = "".join(_row(i, t, overdue_badge)
                               for i, t in enumerate(overdue_list))
        overdue_html = (
            '<div style="font-size:0.78em;font-weight:700;color:#c0392b;'
            'margin:4px 0 2px;letter-spacing:.02em;">⚠️ Overdue</div>'
            + overdue_rows
        )

    # ── Section 2: Active (cap of 10) ───────────────────────────────────
    active_capped = active_list[:10]
    active_rows   = "".join(_row(i, t) for i, t in enumerate(active_capped))
    active_margin = "margin:10px 0 2px;" if overdue_html else "margin:4px 0 2px;"
    active_section_html = (
        f'<div style="font-size:0.78em;font-weight:700;color:var(--ink);'
        f'{active_margin}letter-spacing:.02em;">Active tasks</div>'
        + (active_rows or
           '<p class="muted" style="font-size:0.82em;margin:4px 0;">None right now.</p>')
    )

    # ── Section 3: Someday / no date (collapsible, hidden by default) ───
    someday_html = ""
    if someday_list:
        someday_count = len(someday_list)
        someday_rows  = "".join(_row(i, t) for i, t in enumerate(someday_list))
        # Inline toggle — flips display + swaps marker char + aria-expanded.
        # No literal braces in the JS string, so no f-string escaping concerns.
        toggle_js = (
            "var d=document.getElementById('mom-someday-list');"
            "var m=document.getElementById('mom-someday-marker');"
            "var hidden=(d.style.display==''||d.style.display=='none');"
            "d.style.display=hidden?'block':'none';"
            "m.textContent=hidden?'\u25bc':'\u25b6';"
            "this.setAttribute('aria-expanded',hidden?'true':'false');"
        )
        someday_html = (
            f'<button type="button" onclick="{toggle_js}" '
            f'aria-expanded="false" aria-controls="mom-someday-list" '
            f'style="display:block;width:100%;text-align:left;font-size:0.78em;'
            f'font-weight:700;color:var(--ink-muted);background:transparent;border:none;'
            f'padding:0;margin:10px 0 2px;cursor:pointer;user-select:none;'
            f'letter-spacing:.02em;font-family:inherit;">'
            f'<span id="mom-someday-marker">\u25b6</span> Someday / no date '
            f'({someday_count})'
            f'</button>'
            f'<div id="mom-someday-list" style="display:none;">{someday_rows}</div>'
        )

    # Subtitle: e.g. "3 overdue · 7 active · 5 someday"
    parts = []
    if overdue_list:
        parts.append(f"{len(overdue_list)} overdue")
    parts.append(f"{len(active_list)} active")
    if someday_list:
        parts.append(f"{len(someday_list)} someday")
    subtitle = " · ".join(parts)

    return f"""
{_step_header("Step 5 · Tasks", subtitle, "tasks")}

<div class="card" style="margin-bottom:4px;">
  {overdue_html}
  {active_section_html}
  {someday_html}
  <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
    <a href="/tasks" style="font-size:0.82em;color:var(--brown);font-weight:700;text-decoration:none;">
      Manage all tasks &rarr;
    </a>
    <span style="color:var(--border);">|</span>
    <a href="/settings#s-systems" style="font-size:0.78em;color:var(--ink-faint);text-decoration:none;">⚙ Settings</a>
  </div>
</div>

<script>
var _tasksIso = '{_e(iso)}';
function addTaskToDay(tid, text, btn) {{
  btn.textContent = '✓ Added';
  btn.style.color = '#27ae60';
  btn.style.borderColor = '#27ae60';
  btn.disabled = true;
  fetch('/add-to-plan-quick', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'iso=' + encodeURIComponent(_tasksIso) + '&text=' + encodeURIComponent(text) + '&source=task&task_id=' + encodeURIComponent(tid)
  }});
}}
function taskEditOpenStep(tid) {{
  var p = document.getElementById('step-task-edit-' + tid);
  if (!p) return;
  p.style.display = (p.style.display === 'none' || p.style.display === '') ? 'block' : 'none';
}}
function taskEditRecurToggle(tid) {{
  var w = document.getElementById('step-task-recur-wrap-' + tid);
  if (!w) return;
  w.style.display = (w.style.display === 'none' || w.style.display === '') ? 'block' : 'none';
}}
function _stepRefreshTasks() {{
  if (window._momStepReload) {{ window._momStepReload('tasks'); }}
  else {{ window.location.reload(); }}
}}
function _stepCollectFields(tid) {{
  var p = document.getElementById('step-task-edit-' + tid);
  if (!p) return null;
  var fd = new URLSearchParams();
  fd.append('id', tid);
  var els = p.querySelectorAll('input[name], select[name]');
  els.forEach(function(el){{
    var nm = el.name;
    if (!nm || nm === 'id') return;
    if (el.type === 'checkbox') {{
      if (nm === 'recurring') {{
        fd.append('recurring', el.checked ? 'true' : 'false');
      }} else if (nm === 'weekdays_mask') {{
        if (el.checked) fd.append('weekdays_mask', el.value);
      }}
      return;
    }}
    fd.append(nm, el.value);
  }});
  return fd;
}}
function taskEditSaveStep(tid, btn) {{
  var fd = _stepCollectFields(tid);
  if (!fd) return;
  btn.disabled = true;
  fetch('/task-update', {{
    method: 'POST',
    headers: {{'Content-Type':'application/x-www-form-urlencoded'}},
    body: fd.toString()
  }}).then(function(r){{ return r.json(); }})
    .then(function(j){{
      if (j && j.ok) {{ _stepRefreshTasks(); }}
      else {{ btn.disabled = false; alert('Save failed: ' + (j && j.error || 'unknown')); }}
    }})
    .catch(function(){{ btn.disabled = false; _stepRefreshTasks(); }});
}}
function taskEditDoneStep(tid, btn) {{
  btn.disabled = true;
  fetch('/task-done', {{
    method: 'POST',
    headers: {{'Content-Type':'application/x-www-form-urlencoded'}},
    body: 'id=' + encodeURIComponent(tid),
    redirect: 'manual'
  }}).then(function(){{ _stepRefreshTasks(); }})
    .catch(function(){{ _stepRefreshTasks(); }});
}}
</script>
{_recur_editor_js()}
"""


# ── STEP 6: Kids' Day ────────────────────────────────────────────────────────
def _render_kidsday_step(iso: str, weekday: str, date_label: str) -> str:
    from html import escape as _e
    from daily_schedule_engine import CHILDREN, build_schedule_payload
    from config import child_color as _cc

    all_cards = ""
    for child in CHILDREN:
        try:
            payload   = build_schedule_payload(child, weekday, date_label, iso)
            blocks    = payload.get("school_blocks", [])
            chores    = payload.get("chore_items", [])
            carryover = payload.get("carryover_items", [])
            manual    = payload.get("manual_task_items", [])
            c_bg      = _cc(child, "bg")
            c_light   = _cc(child, "light")

            # Status
            needs_check = any(b.get("needs_check") for b in blocks)
            status_txt  = "Needs check" if needs_check else "On track"
            status_c    = "#c0392b" if needs_check else "#27ae60"

            # Carryover section
            carryover_html = ""
            if carryover:
                rows = ""
                from data_helpers import load_progress as _lp_carry
                _prog_carry = _lp_carry()
                for item in carryover[:5]:
                    text    = item.get("text", "") if isinstance(item, dict) else str(item)
                    tid     = item.get("task_id", "") if isinstance(item, dict) else ""
                    val     = _prog_carry.get(tid, False) if tid else False
                    is_done = (val.get("done") if isinstance(val, dict) else bool(val))
                    checked = "checked" if is_done else ""
                    done_sty = "opacity:0.5;text-decoration:line-through;" if is_done else ""
                    cb_url  = f"/schedule/{child}?date={iso}"
                    tid_js  = tid.replace("'", "\\'") if tid else ""
                    onch    = f'onchange="toggleTask(this,\'{tid_js}\',\'{cb_url}\')"' if tid else ""
                    rows += (
                        f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0;'
                        f'border-bottom:1px solid {c_bg}18;">'
                        f'<span style="flex:1;font-size:0.8em;color:var(--ink);{done_sty}">{_e(text)}</span>'
                        f'<input type="checkbox" {checked} {onch} style="accent-color:{c_bg};flex-shrink:0;">'
                        f'</div>'
                    )
                carryover_html = (
                    f'<div style="margin-top:10px;">'
                    f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.12em;'
                    f'text-transform:uppercase;color:{c_bg};margin-bottom:4px;">Carryover</div>'
                    + rows + '</div>'
                )

            # School section — show items within each block
            school_html = ""
            if blocks:
                rows = ""
                from data_helpers import load_progress as _lp2
                _prog2 = _lp2()
                for b in blocks[:8]:
                    subj  = _e(b.get("subject",""))
                    items = b.get("items", [])
                    if items:
                        rows += (
                            f'<div style="margin-bottom:6px;">'
                            f'<div style="font-size:0.72em;font-weight:800;text-transform:uppercase;'
                            f'letter-spacing:.08em;color:{c_bg};margin-bottom:3px;">{subj}</div>'
                        )
                        for item in items:
                            tid      = item.get("task_id","")
                            val      = _prog2.get(tid, False)
                            is_done  = (val.get("done") if isinstance(val,dict) else bool(val))
                            checked  = "checked" if is_done else ""
                            text     = _e(item.get("text","") or item.get("description","") or subj)
                            child_e  = _e(child)
                            iso_e    = _e(iso)
                            tid_js   = escape(tid, quote=False).replace("'", "\\'")
                            done_sty = "opacity:0.5;" if is_done else ""
                            txt_sty  = "text-decoration:line-through;" if is_done else ""
                            cb_url   = f"/schedule/{child_e}?date={iso_e}"
                            rows += (
                                f'<div style="display:flex;align-items:flex-start;gap:8px;'
                                f'padding:3px 0 3px 8px;{done_sty}">'
                                f'<span style="flex:1;font-size:0.8em;color:var(--ink);{txt_sty}">{text}</span>'
                                f'<input type="checkbox" {checked} '
                                f'onchange="toggleTask(this,\'{tid_js}\',\'{cb_url}\')" '
                                f'style="accent-color:{c_bg};flex-shrink:0;margin-left:6px;">'
                                f'</div>'
                            )
                        rows += '</div>'
                    else:
                        rows += (
                            f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0;'
                            f'border-bottom:1px solid {c_bg}18;">'
                            f'<span style="flex:1;font-size:0.8em;color:var(--ink);">{subj}</span>'
                            f'<input type="checkbox" style="accent-color:{c_bg};flex-shrink:0;">'
                            f'</div>'
                        )
                school_html = (
                    f'<div style="margin-top:10px;">'
                    f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.12em;'
                    f'text-transform:uppercase;color:{c_bg};margin-bottom:4px;">School Today</div>'
                    + rows + '</div>'
                )

            # Pending/recurring tasks
            tasks_html = ""
            all_tasks_child = (chores or []) + (manual or [])
            if all_tasks_child:
                rows = ""
                for item in all_tasks_child[:6]:
                    rows += (
                        f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0;'
                        f'border-bottom:1px solid {c_bg}18;">'
                        f'<span style="flex:1;font-size:0.8em;color:var(--ink);">{_e(item.get("text","") if isinstance(item,dict) else str(item))}</span>'
                        f'<input type="checkbox" style="accent-color:{c_bg};flex-shrink:0;">'
                        f'</div>'
                    )
                tasks_html = (
                    f'<div style="margin-top:10px;">'
                    f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.12em;'
                    f'text-transform:uppercase;color:{c_bg};margin-bottom:4px;">Tasks & Chores</div>'
                    + rows + '</div>'
                )

            all_cards += (
                f'<div style="border:1.5px solid {c_bg};border-radius:14px;'
                f'padding:14px;background:{c_light};margin-bottom:14px;">'
                f'<div style="display:flex;align-items:center;justify-content:space-between;'
                f'margin-bottom:4px;">'
                f'<div style="font-weight:700;color:{c_bg};font-size:1em;">{_e(child)}</div>'
                f'<div style="font-size:0.75em;font-weight:700;color:{status_c};">{_e(status_txt)}</div>'
                f'</div>'
                + carryover_html + school_html + tasks_html +
                f'<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">'
                f'<a href="/schedule/{_e(child)}?date={_e(iso)}" '
                f'style="font-size:0.75em;color:{c_bg};font-weight:700;text-decoration:none;">'
                f'Full schedule &rarr;</a>'
                f'<span style="color:var(--border);">|</span>'
                f'<a href="/chores" style="font-size:0.75em;color:var(--ink-faint);text-decoration:none;">'
                f'All chores &rarr;</a>'
                f'</div></div>'
            )
        except Exception as ex:
            all_cards += f'<div class="card"><p class="muted">{_e(child)}: {_e(str(ex))}</p></div>'

    _kids_header = _step_header("Step 6 \u00b7 Kids\u2019 Day", weekday, "s-systems")

    # Get ISO week key for weekly tasks
    try:
        from datetime import date as _dc
        _today = _dc.fromisoformat(iso)
        _wk_key = _today.strftime("%Y-%W")
    except Exception:
        _wk_key = ""

    return f"""
{_kids_header}

<!-- Action buttons at top -->
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;">
  <a href="/kids-week{('?week=' + _e(_wk_key)) if _wk_key else ''}"
     style="padding:9px 18px;background:var(--ink);color:var(--gold-light);
            border-radius:10px;font-size:0.85em;font-weight:700;text-decoration:none;">
    \U0001f4cb Plan Kids\u2019 Week &rarr;
  </a>
  <a href="/school" style="padding:9px 14px;background:var(--parchment);color:var(--ink);
     border:1.5px solid var(--border);border-radius:10px;font-size:0.82em;text-decoration:none;">
    School overview
  </a>
</div>

{all_cards}

<div style="display:flex;gap:8px;flex-wrap:wrap;padding:8px 0;">
  <a href="/tasks" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">
    All task lists &rarr;
  </a>
  <span style="color:var(--border);">|</span>
  <a href="/chores" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">
    Chores &rarr;
  </a>
</div>
"""


# ── STEP 7: Evening ───────────────────────────────────────────────────────────
def _render_evening_step(iso: str) -> str:
    import json as _json
    from html import escape as _e
    from render_morning_anchor import EVENING_CHECKLIST, _get_anchor_state

    anchor  = _get_anchor_state(iso)
    evening = anchor.get("evening", {})

    # Fixed checklist items
    check_rows = ""
    for key, label in EVENING_CHECKLIST:
        checked = evening.get(key, False)
        _checked_attr = "checked" if checked else ""
        check_rows += (
            f'<label style="display:flex;align-items:center;gap:12px;padding:10px 0;'
            f'border-bottom:1px solid var(--border-light);cursor:pointer;">'
            f'<input type="checkbox" id="eve-{_e(key)}" {_checked_attr} '
            f'onchange="eveningSave()" '
            f'style="width:18px;height:18px;accent-color:var(--ink);flex-shrink:0;">'
            f'<span style="font-size:0.88em;color:var(--ink);">{_e(label)}</span>'
            f'</label>'
        )

    # Custom evening tasks (add/check/delete)
    custom_tasks = evening.get("custom_tasks", [])
    custom_rows = ""
    for i, task in enumerate(custom_tasks):
        _task_text    = _e(task.get("text",""))
        _task_checked = "checked" if task.get("done", False) else ""
        _strike       = "text-decoration:line-through;color:var(--ink-faint);" if task.get("done") else ""
        custom_rows += (
            f'<div style="display:flex;align-items:center;gap:10px;padding:9px 0;'
            f'border-bottom:1px solid var(--border-light);" id="eve-custom-{i}">'
            f'<input type="checkbox" {_task_checked} '
            f'onchange="eveToggleCustom({i},this)" '
            f'style="width:18px;height:18px;accent-color:var(--ink);flex-shrink:0;">'
            f'<span style="flex:1;font-size:0.88em;{_strike}">{_task_text}</span>'
            f'<button onclick="eveDeleteCustom({i})" '
            f'style="background:none;border:none;color:var(--ink-faint);cursor:pointer;'
            f'font-size:0.85em;padding:2px 6px;border-radius:4px;" title="Remove">&times;</button>'
            f'</div>'
        )

    custom_tasks_js = _json.dumps(custom_tasks)
    checklist_keys  = _json.dumps([k for k, _ in EVENING_CHECKLIST])
    brain_dump      = _e(anchor.get("brain_dump",""))
    _eve_header     = _step_header("Step 7 \u00b7 Evening", "End of day", "s-systems")

    return f"""
{_eve_header}

<!-- Save bar at TOP -->
{_save_bar("evening")}

<!-- Fixed checklist -->
<div class="card" style="margin-bottom:12px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:6px;">Evening Checklist</div>
  {check_rows}
</div>

<!-- Custom tasks section -->
<div class="card" style="margin-bottom:12px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:8px;">Extra Tasks</div>
  <div id="eve-custom-list">{custom_rows if custom_rows else
    '<p style="font-size:0.82em;color:var(--ink-faint);padding:6px 0;">No extra tasks yet.</p>'}</div>
  <div style="display:flex;gap:8px;margin-top:10px;">
    <input type="text" id="eve-new-task" placeholder="Add a task..."
           onkeydown="if(event.key==='Enter')eveAddCustom()"
           style="flex:1;padding:7px 10px;font-size:0.85em;border-radius:8px;
                  border:1.5px solid var(--border);font-family:inherit;">
    <button onclick="eveAddCustom()"
            style="padding:7px 16px;background:var(--ink);color:var(--gold-light);
                   border:none;border-radius:8px;font-size:0.85em;font-weight:600;
                   font-family:inherit;cursor:pointer;white-space:nowrap;">+ Add</button>
  </div>
</div>

<!-- Brain dump -->
<div class="card">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:8px;">Brain Dump</div>
  <textarea id="eve-brain-dump" rows="4"
            placeholder="Everything on your mind — clear it out before tomorrow..."
            onchange="eveningSave()" oninput="eveningAutoSave()"
            style="width:100%;font-size:0.88em;resize:vertical;padding:10px;
                   border:1.5px solid var(--border);border-radius:10px;
                   font-family:inherit;line-height:1.6;">{brain_dump}</textarea>
</div>

<script>
var _eveningIso    = '{_e(iso)}';
var _eveningTimer  = null;
var _eveningKeys   = {checklist_keys};
var _eveCustom     = {custom_tasks_js};

function eveningAutoSave() {{
  clearTimeout(_eveningTimer);
  _eveningTimer = setTimeout(eveningSave, 800);
}}

function eveningSave() {{
  var data = {{ evening: {{}}, brain_dump: '' }};
  _eveningKeys.forEach(function(k) {{
    var el = document.getElementById('eve-' + k);
    if (el) data.evening[k] = el.checked;
  }});
  data.evening.custom_tasks = _eveCustom;
  var bd = document.getElementById('eve-brain-dump');
  if (bd) data.brain_dump = bd.value;
  fetch('/anchor-save', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'iso=' + encodeURIComponent(_eveningIso) + '&data=' + encodeURIComponent(JSON.stringify(data))
  }}).then(function() {{
    var el = document.getElementById('save-status-evening');
    if (el) {{ el.textContent = 'Saved \u2713'; setTimeout(function(){{ el.textContent=''; }}, 2000); }}
  }});
}}
window._saveStep_evening = eveningSave;

function _eveRebuildCustomList() {{
  var container = document.getElementById('eve-custom-list');
  if (!container) return;
  if (_eveCustom.length === 0) {{
    container.innerHTML = '<p style="font-size:0.82em;color:var(--ink-faint);padding:6px 0;">No extra tasks yet.</p>';
    return;
  }}
  container.innerHTML = _eveCustom.map(function(t,i) {{
    var strike = t.done ? 'text-decoration:line-through;color:var(--ink-faint);' : '';
    var checked = t.done ? 'checked' : '';
    return '<div style="display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--border-light);" id="eve-custom-'+i+'">'
      + '<span style="flex:1;font-size:0.88em;'+strike+'">'+t.text+'</span>'
      + '<input type="checkbox" '+checked+' onchange="eveToggleCustom('+i+',this)" '
      + 'style="width:18px;height:18px;accent-color:var(--ink);flex-shrink:0;">'
      + '<button onclick="eveDeleteCustom('+i+')" style="background:none;border:none;'
      + 'color:var(--ink-faint);cursor:pointer;font-size:0.85em;padding:2px 6px;">&times;</button>'
      + '</div>';
  }}).join('');
}}

function eveAddCustom() {{
  var inp = document.getElementById('eve-new-task');
  if (!inp || !inp.value.trim()) return;
  _eveCustom.push({{ text: inp.value.trim(), done: false }});
  inp.value = '';
  _eveRebuildCustomList();
  eveningSave();
}}

function eveToggleCustom(idx, cb) {{
  if (_eveCustom[idx]) _eveCustom[idx].done = cb.checked;
  _eveRebuildCustomList();
  eveningSave();
}}

function eveDeleteCustom(idx) {{
  _eveCustom.splice(idx, 1);
  _eveRebuildCustomList();
  eveningSave();
}}
</script>
"""


    import json as _json
    from html import escape as _e
    from render_morning_anchor import EVENING_CHECKLIST, _get_anchor_state

    anchor  = _get_anchor_state(iso)
    evening = anchor.get("evening", {})

    check_rows = ""
    for key, label in EVENING_CHECKLIST:
        checked = evening.get(key, False)
        check_rows += (
            f'<label style="display:flex;align-items:center;gap:12px;padding:11px 0;'
            f'border-bottom:1px solid var(--border-light);cursor:pointer;">'
            f'<input type="checkbox" id="eve-{_e(key)}" {"checked" if checked else ""} '
            f'onchange="eveningSave()" '
            f'style="width:20px;height:20px;accent-color:var(--ink);flex-shrink:0;">'
            f'<span style="font-size:0.9em;color:var(--ink);">{_e(label)}</span></label>'
        )

    brain_dump = _e(anchor.get("brain_dump",""))
    checklist_keys = _json.dumps([k for k, _ in EVENING_CHECKLIST])

    return f"""
{_step_header("Step 7 · Evening", "End of day checklist", "evening")}

<div class="card" style="margin-bottom:12px;">
  {check_rows}
  {_save_bar("evening")}
</div>

<div class="card">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:8px;">Brain Dump</div>
  <textarea id="eve-brain-dump" rows="5"
            placeholder="Everything on your mind — clear it out before tomorrow..."
            onchange="eveningSave()" oninput="eveningAutoSave()"
            style="width:100%;font-size:0.88em;resize:vertical;padding:10px;
                   border:1.5px solid var(--border);border-radius:10px;
                   font-family:inherit;line-height:1.6;">{brain_dump}</textarea>
  <div style="font-size:0.75em;color:var(--ink-faint);margin-top:6px;">
    Saves automatically to your notes.
  </div>
</div>

<script>
var _eveningIso   = '{_e(iso)}';
var _eveningTimer = null;
var _eveningKeys  = {checklist_keys};
function eveningAutoSave() {{
  clearTimeout(_eveningTimer);
  _eveningTimer = setTimeout(eveningSave, 800);
}}
function eveningSave() {{
  var data = {{ evening: {{}}, brain_dump: '' }};
  _eveningKeys.forEach(function(k) {{
    var el = document.getElementById('eve-' + k);
    if (el) data.evening[k] = el.checked;
  }});
  var bd = document.getElementById('eve-brain-dump');
  if (bd) data.brain_dump = bd.value;
  fetch('/anchor-save', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'iso=' + encodeURIComponent(_eveningIso) + '&data=' + encodeURIComponent(JSON.stringify(data))
  }}).then(function() {{
    var el = document.getElementById('save-status-evening');
    if (el) {{ el.textContent = 'Saved ✓'; setTimeout(function() {{ el.textContent = ''; }}, 2000); }}
  }});
}}
window._saveStep_evening = eveningSave;
</script>
"""


# ── STEP 8: Grid & Done ───────────────────────────────────────────────────────
def _render_grid_step(iso: str, weekday: str, date_label: str, target_date) -> str:
    from html import escape as _e
    from render_daily_plan import render_plan_editor, publish_day_grid

    try:
        grid_html = render_plan_editor(iso, weekday, date_label, "")
    except Exception as ex:
        grid_html = f'<p class="muted">Could not load grid: {_e(str(ex))}</p>'

    _grid_header = _step_header("Step 8 \u00b7 Grid & Done", "Publish \u00b7 print \u00b7 wrap up", "")

    return f"""
{_grid_header}

<!-- Action buttons at TOP for easy access -->
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;">
  <button onclick="publishAndDone(this)"
          style="padding:10px 20px;background:var(--ink);color:var(--gold-light);
                 border:none;border-radius:10px;font-size:0.85em;font-weight:700;
                 font-family:inherit;cursor:pointer;flex-shrink:0;">
    \u2713 Publish &amp; Go to Dashboard
  </button>
  <a href="/grid-print?iso={_e(iso)}" target="_blank"
     style="padding:10px 16px;background:var(--parchment);color:var(--ink);
            border:1.5px solid var(--border);border-radius:10px;
            font-size:0.82em;font-weight:600;text-decoration:none;">
    \U0001f5a8 Print Grid
  </a>
  <a href="/meal-print" target="_blank"
     style="padding:10px 16px;background:var(--parchment);color:var(--ink);
            border:1.5px solid var(--border);border-radius:10px;
            font-size:0.82em;font-weight:600;text-decoration:none;">
    \U0001f5a8 Meal Card
  </a>
</div>

<div id="publish-status" style="font-size:0.82em;min-height:18px;margin-bottom:10px;
     color:#27ae60;font-weight:600;"></div>

<!-- Family grid editor -->
{grid_html}

<script>
var _gridIso = '{_e(iso)}';
function publishAndDone(btn) {{
  btn.disabled = true;
  btn.textContent = 'Publishing\u2026';
  fetch('/grid-publish', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'iso=' + encodeURIComponent(_gridIso)
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    var el = document.getElementById('publish-status');
    var ts = d.published_at || 'just now';
    if (el) {{
      el.textContent = '\u2713 Published ' + ts + ' \u2014 going to dashboard\u2026';
      el.style.color = '#27ae60';
    }}
    btn.textContent = '\u2713 Published!';
    btn.style.background = '#27ae60';
    setTimeout(function() {{ window.location.href = '/'; }}, 1500);
  }}).catch(function() {{
    var el = document.getElementById('publish-status');
    if (el) {{ el.textContent = 'Error publishing \u2014 try again.'; el.style.color = '#c0392b'; }}
    btn.disabled = false;
    btn.textContent = '\u2713 Publish \u0026 Go to Dashboard';
  }});
}}
</script>
"""


    from html import escape as _e
    from daily_schedule_engine import CHILDREN, build_schedule_payload
    from config import child_color as _cc

    cards = ""
    for child in CHILDREN:
        try:
            payload  = build_schedule_payload(child, weekday, date_label, iso)
            blocks   = payload.get("school_blocks",[])
            chores   = payload.get("chore_items",[])
            c_bg     = _cc(child,"bg")
            c_light  = _cc(child,"light")
            status   = "On track"
            status_c = "#27ae60"
            for b in blocks:
                if b.get("needs_check"):
                    status   = b.get("subject","Needs check")
                    status_c = "#c0392b"
                    break
            subj_html = ""
            for b in blocks[:6]:
                subj = _e(b.get("subject",""))
                subj_html += (
                    f'<div style="font-size:0.78em;padding:3px 0;border-bottom:1px solid {c_bg}18;">' +
                    f'<span style="color:{c_bg};font-weight:700;">{subj}</span></div>'
                )
            chore_html = ""
            for ch in chores[:3]:
                chore_html += (
                    f'<div style="font-size:0.75em;color:var(--ink-muted);padding:2px 0;">' +
                    f'🧹 {_e(str(ch))}</div>'
                )
            cards += (
                f'<div style="border:1.5px solid {c_bg};border-radius:14px;' +
                f'padding:12px 14px;background:{c_light};break-inside:avoid;">' +
                f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">' +
                f'<div style="font-weight:700;color:{c_bg};font-size:0.95em;">{_e(child)}</div>' +
                f'<div style="font-size:0.75em;font-weight:700;color:{status_c};">{_e(status)}</div>' +
                f'</div>' +
                subj_html +
                (f'<div style="margin-top:6px;">{chore_html}</div>' if chore_html else '') +
                f'<div style="margin-top:8px;">' +
                f'<a href="/schedule/{_e(child)}?date={_e(iso)}" ' +
                f'style="font-size:0.75em;color:{c_bg};font-weight:700;text-decoration:none;">'
                f'Full schedule &rarr;</a></div>' +
                f'</div>'
            )
        except Exception:
            pass

    return f"""
{_step_header("Step 6 · School", weekday, "school")}
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:12px;">
  {cards}
</div>
<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:8px 0;">
  <a href="/school" style="font-size:0.82em;color:var(--brown);font-weight:700;text-decoration:none;">
    School overview &rarr;
  </a>
  <span style="color:var(--border);">|</span>
  <a href="/chores" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">Chores &rarr;</a>
  <span style="color:var(--border);">|</span>
  <a href="/settings#s-systems" style="font-size:0.78em;color:var(--ink-faint);text-decoration:none;">⚙ Settings</a>
</div>
"""


# ── Notes ─────────────────────────────────────────────────────────────────────
def render_notes() -> str:
    notes        = load_notes()
    active_notes = [n for n in notes if n.get("status") == "active"]
    note_cards   = ""
    for note in active_notes:
        note_id   = escape(note.get("id",""))
        note_text = escape(note.get("text",""))
        suggestion = route_note_text(note.get("text","")).get("suggested_destination","notes")
        child_options = "".join(f'<option value="{escape(c)}">{escape(c)}</option>' for c in CHILDREN)
        note_cards += f"""
        <div class="card">
            <p>{note_text}</p>
            <p class="small">Suggested destination: {escape(suggestion)}</p>
            <form method="POST" action="/convert-note">
                <input type="hidden" name="id" value="{note_id}">
                <label>Assign to</label>
                <select name="assigned_to"><option value="">Anyone</option>{child_options}</select>
                <label>Due date</label><input type="date" name="due_date">
                <label>Priority</label>
                <select name="priority">
                    <option value="HIGH">HIGH</option>
                    <option value="MEDIUM" selected>MEDIUM</option>
                    <option value="LOW">LOW</option>
                </select>
                <button type="submit">Convert to Task</button>
            </form>
            <form method="POST" action="/archive-note">
                <input type="hidden" name="id" value="{note_id}">
                <button type="submit" class="ghost">Archive</button>
            </form>
        </div>"""
    body = f"""
    {page_header("Notes")}
    <div class="card">
        <h3>Add Note</h3>
        <form method="POST" action="/add-note">
            <label>Note</label>
            <textarea name="text" rows="4"></textarea>
            <button type="submit">Save Note</button>
        </form>
    </div>
    {note_cards or "<div class='card'><p class='muted'>No active notes.</p></div>"}"""
    return html_page("Notes", body)


# ── Tasks: shared recurrence-editor helpers ───────────────────────────────────
# These helpers render the same recurrence sub-panel in two places — the
# Add-Task form on /tasks and every per-task inline edit panel on /tasks and
# /mom Step 5. All DOM ids are suffixed `-{tid}` so multiple instances coexist
# on one page; the JS helpers take a `tid` arg and operate on the matching
# subtree. Add-Task uses tid="add"; each editable row uses tid={task.id}.
def _recur_editor_html(tid: str, task=None) -> str:
    """
    Recurrence sub-panel markup. Renders only the *fields* panel (the part that
    appears once 'Repeat' is checked). The Repeat checkbox itself is rendered
    by the caller. When `task` is provided, fields are pre-filled.
    """
    is_rec = bool(task and task.get("recurring"))
    unit   = ((task or {}).get("interval_unit") or "weeks")
    iv     = (task or {}).get("interval_value") or 1
    wdmask = set((task or {}).get("weekdays_mask") or [])
    mday   = (task or {}).get("month_day") or 1
    mnth   = (task or {}).get("month_nth") or 1
    mwd    = (task or {}).get("month_weekday") or 0
    end    = (task or {}).get("end_date") or ""
    maxocc = (task or {}).get("occurrences_remaining") or 0
    end_mode = "on_date" if end else ("after_n" if maxocc else "never")

    _wd_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    _wd_boxes = "".join(
        f'<label style="display:flex;align-items:center;gap:4px;font-size:0.82em;'
        f'font-weight:400;cursor:pointer;margin:0;">'
        f'<input type="checkbox" name="weekdays_mask" value="{i}"'
        f' style="width:auto;margin:0;accent-color:#8b5a3c;"'
        f'{" checked" if i in wdmask else ""}> {_wd_names[i]}</label>'
        for i in range(7)
    )

    def _sel(val, target):
        return ' selected' if val == target else ''

    _mday_opts = "".join(
        f'<option value="{d}"{_sel(d,mday)}>Day {d}</option>'
        for d in range(1, 32)
    ) + f'<option value="-1"{_sel(-1,mday)}>Last day of month</option>'

    unit_opts = (
        f'<option value="days"{_sel("days",unit)}>Every N days</option>'
        f'<option value="weekdays"{_sel("weekdays",unit)}>Every weekday (Mon\u2013Fri)</option>'
        f'<option value="specific_weekdays"{_sel("specific_weekdays",unit)}>On specific days of the week\u2026</option>'
        f'<option value="weeks"{_sel("weeks",unit)}>Every N weeks</option>'
        f'<option value="monthly_day"{_sel("monthly_day",unit)}>Monthly on day\u2026</option>'
        f'<option value="monthly_nth_weekday"{_sel("monthly_nth_weekday",unit)}>Monthly on Nth weekday\u2026</option>'
        f'<option value="months"{_sel("months",unit)}>Every N months (same date)</option>'
        f'<option value="years"{_sel("years",unit)}>Yearly</option>'
    )
    nth_opts = "".join(
        f'<option value="{n}"{_sel(n,mnth)}>{name}</option>'
        for n, name in [(1,"1st"),(2,"2nd"),(3,"3rd"),(4,"4th"),(5,"5th"),(-1,"Last")]
    )
    wd_opts = "".join(
        f'<option value="{i}"{_sel(i,mwd)}>{name}</option>'
        for i, name in enumerate(["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"])
    )
    end_opts = "".join(
        f'<option value="{v}"{_sel(v,end_mode)}>{label}</option>'
        for v, label in [("never","Never"),("on_date","On date\u2026"),("after_n","After N times\u2026")]
    )

    show_n   = unit in ("days","weeks","months","years","specific_weekdays","monthly_day","monthly_nth_weekday")
    show_wd  = unit == "specific_weekdays"
    show_md  = unit == "monthly_day"
    show_nw  = unit == "monthly_nth_weekday"
    show_end_date = end_mode == "on_date"
    show_end_n    = end_mode == "after_n"

    # Suffix label appropriate to current unit (used on initial render)
    if   unit == "days":   suf_init = "day(s)"
    elif unit == "months" or unit in ("monthly_day","monthly_nth_weekday"): suf_init = "month(s)"
    elif unit == "years":  suf_init = "year(s)"
    else:                  suf_init = "week(s)"

    panel_display = "" if is_rec else "none"
    n_disp        = "flex"  if show_n        else "none"
    wd_disp       = "block" if show_wd       else "none"
    md_disp       = "block" if show_md       else "none"
    nw_disp       = "block" if show_nw       else "none"
    end_d_disp    = "block" if show_end_date else "none"
    end_n_disp    = "block" if show_end_n    else "none"
    max_val       = str(maxocc) if maxocc > 0 else ""

    return (
        f'<div id="recur-fields-{tid}" data-recur-tid="{tid}" '
        f'style="display:{panel_display};padding:10px 0 4px 0;border-left:3px solid #e9d8c8;'
        f'padding-left:14px;margin-bottom:6px;">'
        f'<label style="font-size:0.85em;font-weight:600;margin:0 0 4px;">Frequency</label>'
        f'<select id="recur-unit-{tid}" name="interval_unit" style="margin-bottom:10px;" '
        f'onchange="_recurUpdateUI(\'{tid}\')">{unit_opts}</select>'
        f'<div id="recur-row-n-{tid}" style="display:{n_disp};gap:8px;align-items:center;margin-bottom:10px;">'
        f'<span id="recur-every-label-{tid}" style="white-space:nowrap;font-size:0.88em;">Every</span>'
        f'<input id="recur-n-{tid}" type="number" name="interval_value" value="{iv}" min="1" '
        f'style="width:70px;max-width:70px;margin:0;">'
        f'<span id="recur-n-suffix-{tid}" style="white-space:nowrap;font-size:0.88em;color:#6b7280;">{suf_init}</span>'
        f'</div>'
        f'<div id="recur-row-weekdays-{tid}" style="display:{wd_disp};margin-bottom:10px;">'
        f'<div style="font-size:0.85em;font-weight:600;margin-bottom:4px;">Repeat on</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:6px;">{_wd_boxes}</div>'
        f'</div>'
        f'<div id="recur-row-monthday-{tid}" style="display:{md_disp};margin-bottom:10px;">'
        f'<label style="font-size:0.85em;font-weight:600;margin:0 0 4px;">Day of month</label>'
        f'<select name="month_day" style="margin:0;">{_mday_opts}</select>'
        f'</div>'
        f'<div id="recur-row-nthwd-{tid}" style="display:{nw_disp};margin-bottom:10px;gap:8px;">'
        f'<label style="font-size:0.85em;font-weight:600;margin:0 0 4px;">On the</label>'
        f'<div style="display:flex;gap:8px;">'
        f'<select name="month_nth" style="margin:0;flex:1;">{nth_opts}</select>'
        f'<select name="month_weekday" style="margin:0;flex:1;">{wd_opts}</select>'
        f'</div></div>'
        f'<div style="border-top:1px dashed #e9d8c8;padding-top:8px;margin-top:4px;">'
        f'<label style="font-size:0.85em;font-weight:600;margin:0 0 4px;">Ends</label>'
        f'<select id="recur-end-mode-{tid}" style="margin:0 0 6px;" '
        f'onchange="_recurUpdateEndUI(\'{tid}\')">{end_opts}</select>'
        f'<input id="recur-end-date-{tid}" type="date" name="end_date" value="{end}" '
        f'style="display:{end_d_disp};margin:0 0 6px;width:100%;">'
        f'<input id="recur-max-occ-{tid}" type="number" name="max_occurrences" min="1" placeholder="e.g. 12" '
        f'value="{max_val}" '
        f'style="display:{end_n_disp};margin:0;width:100%;">'
        f'</div>'
        f'<div id="recur-preview-{tid}" '
        f'style="margin-top:10px;padding:8px 10px;background:#fdf6f0;'
        f'border-radius:6px;font-size:0.82em;color:#5b4636;">'
        f'\u21bb <span id="recur-preview-text-{tid}">every week</span>'
        f'</div>'
        f'</div>'
    )


def _recur_editor_js() -> str:
    """
    Shared <script> block defining `_recurUpdateUI(tid)`, `_recurUpdateEndUI(tid)`,
    `_recurPreview(tid)`, plus delegated change/input listeners that walk up to
    the nearest [data-recur-tid] panel and call the right helper. Idempotent —
    re-injecting the script (e.g. after AJAX-refreshing a fragment) does not
    install duplicate listeners.
    """
    return (
        "<script>"
        "if (!window._recurHelpersInstalled) {"
        "  window._recurHelpersInstalled = true;"
        "  window._recurUpdateUI = function(tid) {"
        "    var u = document.getElementById('recur-unit-' + tid);"
        "    if (!u) return;"
        "    var v = u.value;"
        "    var rN  = document.getElementById('recur-row-n-' + tid);"
        "    var rWD = document.getElementById('recur-row-weekdays-' + tid);"
        "    var rMD = document.getElementById('recur-row-monthday-' + tid);"
        "    var rNW = document.getElementById('recur-row-nthwd-' + tid);"
        "    var lbl = document.getElementById('recur-every-label-' + tid);"
        "    var suf = document.getElementById('recur-n-suffix-' + tid);"
        "    if (rN)  rN.style.display='none';"
        "    if (rWD) rWD.style.display='none';"
        "    if (rMD) rMD.style.display='none';"
        "    if (rNW) rNW.style.display='none';"
        "    if (v==='days')      { rN.style.display='flex'; lbl.textContent='Every'; suf.textContent='day(s)'; }"
        "    else if (v==='weeks'){ rN.style.display='flex'; lbl.textContent='Every'; suf.textContent='week(s)'; }"
        "    else if (v==='months'){ rN.style.display='flex'; lbl.textContent='Every'; suf.textContent='month(s)'; }"
        "    else if (v==='years'){ rN.style.display='flex'; lbl.textContent='Every'; suf.textContent='year(s)'; }"
        "    else if (v==='specific_weekdays'){ rWD.style.display='block';"
        "        rN.style.display='flex'; lbl.textContent='Every'; suf.textContent='week(s)'; }"
        "    else if (v==='monthly_day'){ rMD.style.display='block';"
        "        rN.style.display='flex'; lbl.textContent='Every'; suf.textContent='month(s)'; }"
        "    else if (v==='monthly_nth_weekday'){ rNW.style.display='block';"
        "        rN.style.display='flex'; lbl.textContent='Every'; suf.textContent='month(s)'; }"
        "    window._recurPreview(tid);"
        "  };"
        "  window._recurUpdateEndUI = function(tid) {"
        "    var m = document.getElementById('recur-end-mode-' + tid).value;"
        "    var d = document.getElementById('recur-end-date-' + tid);"
        "    var n = document.getElementById('recur-max-occ-' + tid);"
        "    d.style.display = (m==='on_date')?'block':'none';"
        "    n.style.display = (m==='after_n')?'block':'none';"
        "    if (m!=='on_date') d.value='';"
        "    if (m!=='after_n') n.value='';"
        "  };"
        "  window._recurPreview = function(tid) {"
        "    var panel = document.getElementById('recur-fields-' + tid);"
        "    if (!panel) return;"
        "    var u = document.getElementById('recur-unit-' + tid).value;"
        "    var n = parseInt(document.getElementById('recur-n-' + tid).value)||1;"
        "    var WD=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];"
        "    var NW={'1':'1st','2':'2nd','3':'3rd','4':'4th','-1':'last'};"
        "    var s='every week';"
        "    if (u==='days')      s = (n===1?'every day':'every '+n+' days');"
        "    else if (u==='weeks'){ s = (n===1?'every week':'every '+n+' weeks'); }"
        "    else if (u==='months'){ s = (n===1?'every month':'every '+n+' months'); }"
        "    else if (u==='years'){ s = (n===1?'every year':'every '+n+' years'); }"
        "    else if (u==='weekdays'){ s='every weekday (Mon\u2013Fri)'; }"
        "    else if (u==='specific_weekdays'){"
        "        var picked=[];"
        "        panel.querySelectorAll('input[name=\"weekdays_mask\"]:checked').forEach(function(cb){picked.push(parseInt(cb.value));});"
        "        picked.sort(); var names=picked.map(function(i){return WD[i];}).join(', ');"
        "        s = names || 'pick at least one day';"
        "        if (n>1) s += ' every '+n+' weeks';"
        "    } else if (u==='monthly_day'){"
        "        var md=panel.querySelector('select[name=\"month_day\"]').value;"
        "        var d=(md==='-1')?'last day':'day '+md;"
        "        s = d + (n>1?(' of every '+n+' months'):' of each month');"
        "    } else if (u==='monthly_nth_weekday'){"
        "        var nth=panel.querySelector('select[name=\"month_nth\"]').value;"
        "        var wd=parseInt(panel.querySelector('select[name=\"month_weekday\"]').value);"
        "        s = NW[nth]+' '+WD[wd]+(n>1?(' of every '+n+' months'):' of each month');"
        "    }"
        "    document.getElementById('recur-preview-text-' + tid).textContent = s;"
        "  };"
        "  window._recurPanelTid = function(el) {"
        "    var p = el && el.closest && el.closest('[data-recur-tid]');"
        "    return p ? p.getAttribute('data-recur-tid') : null;"
        "  };"
        "  document.addEventListener('change', function(e){"
        "    var t = e.target; if (!t) return;"
        "    var nm = t.name || ''; var id = t.id || '';"
        "    if (nm==='weekdays_mask' || nm==='month_day' || nm==='month_nth' || nm==='month_weekday'"
        "        || id.indexOf('recur-n-')===0 || id.indexOf('recur-unit-')===0) {"
        "      var tid = window._recurPanelTid(t);"
        "      if (tid) window._recurPreview(tid);"
        "    }"
        "  });"
        "  document.addEventListener('input', function(e){"
        "    var t = e.target; if (!t) return;"
        "    if ((t.id || '').indexOf('recur-n-')===0) {"
        "      var tid = window._recurPanelTid(t); if (tid) window._recurPreview(tid);"
        "    }"
        "  });"
        "}"
        "</script>"
    )


# ── Tasks ─────────────────────────────────────────────────────────────────────
def render_tasks() -> str:
    tasks         = load_manual_tasks()
    active_cards  = ""
    inactive_cards = ""
    inactive_count = 0
    for index, task in enumerate(tasks):
        if not isinstance(task, dict): continue
        status      = clean_status(task.get("status","active"))
        text        = escape(task.get("text",""))
        assigned_to = escape(task.get("assigned_to","") or "Anyone")
        due_date    = escape(task.get("due_date","") or "Anytime")
        priority    = escape(task.get("priority","MEDIUM"))
        is_recurring = task.get("recurring", False)
        recur_badge = ""
        if is_recurring:
            try:
                from data_helpers import format_recurrence_label as _frl
                _label = _frl(task)
            except Exception:
                _label = ""
            if _label:
                _end_extra = ""
                if task.get("end_date"):
                    _end_extra = f" until {escape(task['end_date'])}"
                elif task.get("occurrences_remaining"):
                    _end_extra = f" ({task['occurrences_remaining']} left)"
                recur_badge = f" <span class='badge'>↻ {escape(_label)}{_end_extra}</span>"
        if status == "active":
            tid_raw  = task.get("id","") or ""
            tid_e    = escape(tid_raw)
            cur_due  = escape(task.get("due_date","") or "")
            cur_prio = (task.get("priority","MEDIUM") or "MEDIUM").upper()
            cur_assn = task.get("assigned_to","") or ""
            # Per-task assignee <select>: ASSIGNABLE_TO + "" (anyone) + any unknown
            # legacy value so it survives a round-trip without silently mutating.
            _assn_opts_html = '<option value=""' + (' selected' if not cur_assn else '') + '>Anyone</option>'
            _seen = set()
            for _p in ASSIGNABLE_TO:
                _ep = escape(_p); _seen.add(_p)
                _assn_opts_html += f'<option value="{_ep}"' + (' selected' if cur_assn==_p else '') + f'>{_ep}</option>'
            if cur_assn and cur_assn not in _seen:
                _assn_opts_html += f'<option value="{escape(cur_assn)}" selected>{escape(cur_assn)}</option>'
            _prio_opts_html = "".join(
                f'<option value="{p}"' + (' selected' if p==cur_prio else '') + f'>{p}</option>'
                for p in ("HIGH","MEDIUM","LOW")
            )
            _is_rec = bool(task.get("recurring"))
            card_html = f"""
        <div class="card" id="task-card-{index}">
            <h3>{text}{recur_badge}</h3>
            <p class="small">Assigned: {assigned_to} | Due: {due_date} | Priority: {priority}</p>
            <button type="button" onclick="_taskEditToggle('{tid_e}')">&#9998; Edit</button>
            <button type="button" onclick="_taskAction(this,'/task-done','{tid_e}')">&#10003; Done</button>
            <button type="button" class="ghost" onclick="_taskAction(this,'/task-delete','{tid_e}')">Archive</button>
            <div id="task-edit-panel-{tid_e}" style="display:none;margin-top:14px;padding:14px;
                 background:#fff;border:1px solid var(--border);border-radius:10px;">
                <input type="hidden" name="id" value="{tid_e}">
                <label style="font-size:0.85em;font-weight:600;margin:0 0 4px;">Task</label>
                <input type="text" name="text" value="{escape(task.get("text",""))}" style="margin:0 0 10px;">
                <label style="font-size:0.85em;font-weight:600;margin:0 0 4px;">Assigned to</label>
                <select name="assigned_to" style="margin:0 0 10px;">{_assn_opts_html}</select>
                <label style="font-size:0.85em;font-weight:600;margin:0 0 4px;">Due date</label>
                <input type="date" name="due_date" value="{cur_due}" style="margin:0 0 10px;">
                <label style="font-size:0.85em;font-weight:600;margin:0 0 4px;">Priority</label>
                <select name="priority" style="margin:0 0 10px;">{_prio_opts_html}</select>
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;margin-bottom:4px;">
                    <input type="checkbox" id="recur-toggle-{tid_e}" name="recurring" value="true"
                           {("checked" if _is_rec else "")}
                           onchange="(function(cb){{document.getElementById('recur-fields-{tid_e}').style.display=cb.checked?'':'none';}})(this)"
                           style="width:auto;margin:0;">
                    <span>Repeat</span>
                </label>
                {_recur_editor_html(tid_raw, task)}
                <div style="display:flex;gap:8px;margin-top:10px;">
                    <button type="button" onclick="_taskEditSave('{tid_e}',this)"
                            style="background:var(--navy,#1e3566);color:#fff;border:none;
                                   border-radius:8px;padding:9px 18px;font-weight:700;cursor:pointer;">
                        Save changes
                    </button>
                    <button type="button" class="ghost" onclick="_taskEditToggle('{tid_e}')">Cancel</button>
                </div>
            </div>
        </div>"""
            active_cards += card_html
        elif status == "inactive":
            inactive_count += 1
            inactive_cards += f"""
        <div class="card" style="opacity:0.65;background:#f8f6f3;">
            <h3 style="text-decoration:line-through;font-size:0.95em;">{text}</h3>
            <p class="small">Assigned: {assigned_to} | Due: {due_date} | Priority: {priority}</p>
            <form method="POST" action="/task-hard-delete" style="display:inline;">
                <input type="hidden" name="index" value="{index}">
                <button type="submit" class="ghost"
                        style="color:#dc2626;border-color:#dc2626;"
                        onclick="return confirm('Permanently delete this task?')">
                    🗑 Delete permanently
                </button>
            </form>
        </div>"""
    def _assignee_checkboxes() -> str:
        boxes = ""
        for p in ASSIGNABLE_TO:
            ep = escape(p)
            boxes += (
                f'<label style="display:flex;align-items:center;gap:5px;'
                f'font-size:.88em;font-weight:400;cursor:pointer;margin-bottom:0;">'
                f'<input type="checkbox" name="assigned_to" value="{ep}"'
                f' style="width:auto;margin:0;accent-color:#8b5a3c;"> {ep}</label>'
            )
        return (
            f'<div style="display:flex;flex-wrap:wrap;gap:10px 18px;'
            f'padding:6px 0 10px 0;">{boxes}</div>'
            f'<p style="font-size:.78em;color:#999;margin:-6px 0 10px;">'
            f'Leave all unchecked to assign to Anyone.</p>'
        )
    # Build inactive section separately to avoid nested triple-quote conflicts
    if inactive_count:
        _ic = str(inactive_count)
        inactive_section = (
            '<h2 style="margin-top:32px;color:#9ca3af;">Archived / Inactive'
            ' <span style="font-size:0.65em;font-weight:600;background:#f3f4f6;color:#6b7280;'
            'border-radius:10px;padding:2px 8px;margin-left:6px;">' + _ic + '</span></h2>'
            '<div class="card" style="background:#fdf6f0;border:1px solid #e9d8c8;margin-bottom:12px;">'
            '<p style="margin:0 0 10px;font-size:0.88em;color:#6b7280;">'
            'These tasks were archived using the Archive button. '
            'Permanently delete them to clean up your list.</p>'
            '<form method="POST" action="/task-purge-inactive"'
            ' onsubmit="return confirm(\'Permanently delete all ' + _ic + ' archived tasks? This cannot be undone.\');">'
            '<button type="submit"'
            ' style="background:#dc2626;color:white;border:none;border-radius:8px;'
            'padding:9px 18px;font-size:0.88em;font-weight:700;cursor:pointer;">'
            '\U0001f5d1\xa0 Delete all ' + _ic + ' archived tasks</button></form></div>'
            + inactive_cards
        )
    else:
        inactive_section = ""

    # ── Thank-you card due-reminder widget ───────────────────────────────────
    _due_ty = due_thankyou_reminders()
    if _due_ty:
        _ty_cards = ""
        for _r in _due_ty:
            _rid  = escape(_r.get("id",""))
            _ename= escape(_r.get("event_name",""))
            _ppl  = escape(_r.get("people",""))
            _edt  = escape(_r.get("event_date",""))
            _rdt  = escape(_r.get("reminder_date",""))
            _ty_cards += f"""
        <div style="display:flex;align-items:flex-start;justify-content:space-between;
                    gap:12px;padding:10px 0;border-bottom:1px solid #f0e8de;">
            <div>
                <div style="font-weight:600;font-size:0.95em;">{_ename}</div>
                {"<div style='font-size:0.85em;color:#78564b;'>For: " + _ppl + "</div>" if _ppl else ""}
                <div style="font-size:0.8em;color:#9ca3af;">Event: {_edt} &bull; Reminder: {_rdt}</div>
            </div>
            <div style="display:flex;gap:8px;flex-shrink:0;">
                <form method="POST" action="/thankyou-done" style="margin:0;">
                    <input type="hidden" name="id" value="{_rid}">
                    <button type="submit" style="background:#5a7a5a;color:white;border:none;
                            border-radius:7px;padding:6px 12px;font-size:0.82em;cursor:pointer;">
                        &#10003; Done
                    </button>
                </form>
                <form method="POST" action="/thankyou-dismiss" style="margin:0;">
                    <input type="hidden" name="id" value="{_rid}">
                    <button type="submit" style="background:none;border:1px solid #d1b8a8;
                            border-radius:7px;padding:6px 12px;font-size:0.82em;
                            color:#78564b;cursor:pointer;">
                        Skip
                    </button>
                </form>
            </div>
        </div>"""
        _ty_count = len(_due_ty)
        _ty_label = "Thank-You Card" if _ty_count == 1 else "Thank-You Cards"
        _ty_widget = f"""
    <div style="background:#fef3e2;border:1.5px solid #e8c97a;border-radius:12px;
                padding:14px 16px;margin-bottom:18px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
            <span style="font-weight:700;font-size:0.97em;color:#78564b;">
                &#9993; {_ty_count} {_ty_label} Due
            </span>
            <a href="/thankyou-reminders" style="font-size:0.82em;color:#8b5a3c;text-decoration:none;">
                Manage all &rsaquo;
            </a>
        </div>
        {_ty_cards}
    </div>"""
    else:
        _ty_widget = ""

    body = f"""
    {page_header("Tasks")}
    {_ty_widget}
    <div class="card">
        <h3>Add Task</h3>
        <form method="POST" action="/add-task">
            <label>Task</label><input type="text" name="text" required>
            <label>Assign to</label>
            {_assignee_checkboxes()}
            <label>Due date</label><input type="date" name="due_date">
            <label>Priority</label>
            <select name="priority"><option value="HIGH">HIGH</option><option value="MEDIUM" selected>MEDIUM</option><option value="LOW">LOW</option></select>
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer;margin-bottom:4px;">
                <input type="checkbox" id="recur-toggle-add" name="recurring" value="true"
                       onchange="(function(cb){{document.getElementById('recur-fields-add').style.display=cb.checked?'':'none';}})(this)"
                       style="width:auto;margin:0;">
                <span>Repeat</span>
            </label>
            {_recur_editor_html("add")}
            {_recur_editor_js()}
            <button type="submit">Add Task</button>
        </form>
    </div>
    <h2>Active Tasks</h2>{active_cards or "<div class='card'><p class='muted'>No active tasks.</p></div>"}
    {inactive_section}
    <script>
    function _taskAction(btn, url, taskId) {{
      var panel = document.getElementById('task-edit-panel-' + taskId);
      var card = panel ? panel.parentElement : null;
      btn.disabled = true;
      if (card) {{ card.style.transition='opacity .3s'; card.style.opacity='0'; }}
      fetch(url, {{
        method: 'POST',
        headers: {{'Content-Type':'application/x-www-form-urlencoded'}},
        body: 'id=' + encodeURIComponent(taskId),
        redirect: 'manual'
      }}).then(function() {{
        setTimeout(function() {{ window.location.reload(); }}, 200);
      }}).catch(function() {{
        if (card) {{ card.style.opacity='1'; }}
        btn.disabled = false;
        window.location.reload();
      }});
    }}
    function _taskEditToggle(taskId) {{
      var panel = document.getElementById('task-edit-panel-' + taskId);
      if (!panel) return;
      panel.style.display = (panel.style.display === 'none' || panel.style.display === '') ? 'block' : 'none';
    }}
    function _taskEditSave(taskId, btn) {{
      var panel = document.getElementById('task-edit-panel-' + taskId);
      if (!panel) return;
      btn.disabled = true;
      var fd = new URLSearchParams();
      fd.append('id', taskId);
      // Scalar inputs (text, due_date) and selects (assigned_to, priority)
      var inputs = panel.querySelectorAll('input[name], select[name]');
      var hasRecurringField = false;
      inputs.forEach(function(el){{
        var nm = el.name;
        if (!nm) return;
        if (el.type === 'checkbox') {{
          if (nm === 'recurring') {{
            fd.append('recurring', el.checked ? 'true' : 'false');
            hasRecurringField = true;
          }} else if (nm === 'weekdays_mask') {{
            if (el.checked) fd.append('weekdays_mask', el.value);
          }}
          return;
        }}
        if (nm === 'id') return;          // already added
        fd.append(nm, el.value);
      }});
      if (!hasRecurringField) {{
        // Defensive: if the recurring checkbox isn't found in the panel,
        // omit the field entirely so the server doesn't strip recurrence.
      }}
      fetch('/task-update', {{
        method: 'POST',
        headers: {{'Content-Type':'application/x-www-form-urlencoded'}},
        body: fd.toString()
      }}).then(function(r){{ return r.json(); }})
        .then(function(j){{
          if (j && j.ok) {{ window.location.reload(); }}
          else {{ btn.disabled = false; alert('Save failed: ' + (j && j.error || 'unknown')); }}
        }})
        .catch(function(){{ btn.disabled = false; window.location.reload(); }});
    }}
    </script>"""
    return html_page("Tasks", body)


# ── Roadmap ───────────────────────────────────────────────────────────────────
def render_roadmap_page(status_message: str = "") -> str:
    ideas   = load_roadmap()
    grouped = {s: [] for s in ROADMAP_STATUSES}
    for idea in ideas:
        s = idea.get("status","Someday")
        grouped.setdefault(s, []).append(idea)
    status_colors = {"Someday":"#f1ebe4","Ready":"#e4edf1","In Progress":"#eef1e4","Done":"#e4e4e4"}
    sections_html = ""
    for status in ROADMAP_STATUSES:
        cards_html = ""
        for idea in grouped[status]:
            idea_id = escape(str(idea.get("id","")))
            title   = escape(idea.get("title",""))
            notes   = escape(idea.get("notes",""))
            opts    = "".join(f'<option value="{escape(s)}" {"selected" if s==status else ""}>{escape(s)}</option>' for s in ROADMAP_STATUSES)
            cards_html += f"""
            <div class="card card-tight" style="border-left:4px solid #8b5a3c;">
                <form method="POST" action="/roadmap-update">
                    <input type="hidden" name="id" value="{idea_id}">
                    <h3 style="margin-bottom:6px;">{title}</h3>
                    <label>Notes</label><textarea name="notes" rows="3">{notes}</textarea>
                    <label>Status</label><select name="status">{opts}</select>
                    <button type="submit">Save</button>
                </form>
                <form method="POST" action="/roadmap-delete" style="margin-top:6px;">
                    <input type="hidden" name="id" value="{idea_id}">
                    <button type="submit" class="ghost">Remove</button>
                </form>
            </div>"""
        sections_html += f"""
        <div class="card">
            <h2>{escape(status)} <span class="small">({len(grouped[status])})</span></h2>
            {cards_html or "<p class='muted'>No ideas here yet.</p>"}
        </div>"""
    status_opts = "".join(f'<option value="{escape(s)}">{escape(s)}</option>' for s in ROADMAP_STATUSES)
    body = f"""
    {page_header("App Roadmap")}
    {render_status_message(status_message)}
    <div class="card">
        <h2>Capture a New Idea</h2>
        <form method="POST" action="/roadmap-add">
            <label>Idea title</label><input type="text" name="title" placeholder="e.g. Add liturgical calendar">
            <label>Notes (optional)</label><textarea name="notes" rows="3" placeholder="Any details..."></textarea>
            <label>Status</label><select name="status">{status_opts}</select>
            <button type="submit">Add to Roadmap</button>
        </form>
    </div>
    {sections_html}"""
    return html_page("Roadmap", body)


# ── History ───────────────────────────────────────────────────────────────────
SNAPSHOT_FILE_LABELS = {
    "chores":"Chores","manual_tasks":"Manual Tasks","notes":"Notes","mom_notes":"Mom Notes",
    "school_previews":"School Previews","school_weeks":"School Weeks (Approved)",
    "family_schedule":"Family Schedule","roadmap":"Roadmap","liturgical":"Liturgical Calendar",
}

def render_history_page(status_message: str = "") -> str:
    snapshots = list_snapshots()
    grouped   = {}
    for s in snapshots:
        # Group by full original path so same-named files in different
        # sub-dirs (e.g. day_templates/Monday vs day_grids/Monday) don't merge.
        grouped.setdefault(s["original_path"], []).append(s)
    if not grouped:
        body = f"{page_header('Version History')}{render_status_message(status_message)}<div class='card'><p class='muted'>No snapshots yet.</p></div>"
        return html_page("Version History", body)
    sections_html = ""
    for original_path, snaps in sorted(grouped.items()):
        stem  = snaps[0]["stem"]
        label = SNAPSHOT_FILE_LABELS.get(stem, original_path)
        rows  = ""
        for snap in snaps:
            ts    = escape(snap["timestamp"])
            fname = escape(snap["filename"])
            key   = escape(snap["key"])
            rows += f"""
            <div class="card card-tight" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                <div><strong>{ts}</strong><span class="small" style="margin-left:8px;">{fname}</span></div>
                <div class="link-row" style="margin:0;">
                    <a class="link-button" href="/history/preview?key={key}">Preview</a>
                    <form method="POST" action="/history-restore" style="display:inline;">
                        <input type="hidden" name="key" value="{key}">
                        <button type="submit" class="secondary" onclick="return confirm('Restore this snapshot?')">Restore</button>
                    </form>
                </div>
            </div>"""
        sections_html += f'<div class="card"><h2>{escape(label)}</h2><p class="small">{len(snaps)} snapshot{"s" if len(snaps)!=1 else ""} stored</p>{rows}</div>'
    body = f"""
    {page_header("Version History")}
    {render_status_message(status_message)}
    <div class="card"><p>Snapshots are saved automatically before any data change.</p></div>
    {sections_html}"""
    return html_page("Version History", body)


# ── School pages ──────────────────────────────────────────────────────────────
def render_school_preview_card(child: str, preview: dict) -> str:
    parsed      = preview.get("parsed", {})
    filename    = preview.get("filename", "Untitled")
    parsed_days = sort_school_days(parsed.get("parsed_days", []))
    raw_text    = preview.get("raw_text", "")
    day_html    = ""
    for day in parsed_days:
        blocks_html = ""
        for block in day.get("blocks",[]):
            s = escape(block.get("subject",""))
            a = escape(block.get("assignment_text",""))
            blocks_html += f'<div class="subject-card"><h4>{s}</h4><pre>{a}</pre></div>'
        dl = escape(day.get("day_label", day.get("weekday","")))
        wk = escape(day.get("weekday",""))
        no_blocks = "<p class='muted'>No parsed blocks.</p>"
        day_html += f'<div class="card card-tight"><h3>{dl}</h3><p class="small">Weekday key: {wk}</p>{blocks_html or no_blocks}</div>'
    raw_prev = f"<pre>{escape(raw_text[:1200])}{'...' if len(raw_text)>1200 else ''}</pre>" if raw_text else "<p class='muted'>No raw text stored.</p>"
    return f"""
    <div class="card">
        <h2>{escape(child)} Preview</h2>
        <p class="small">Source: {escape(filename)}</p>
        <div class="link-row no-print"><a class="link-button" href="/school/edit?child={escape(child)}">Edit Preview</a></div>
        <form method="POST" action="/approve-school-preview" class="no-print">
            <input type="hidden" name="child" value="{escape(child)}">
            <button type="submit">Approve Preview</button>
        </form>
        <h3>Parsed Days</h3>{day_html or "<p class='muted'>No parsed blocks yet.</p>"}
        <h3>Raw Text</h3>{raw_prev}
    </div>"""


def render_school_page(status_message: str = "") -> str:
    previews = load_school_previews()
    weeks    = load_school_weeks()
    approved = weeks.get("approved", {})
    preview_cards  = "".join(render_school_preview_card(child, previews[child]) for child in CHILDREN if child in previews)
    approved_cards = "".join(
        f'<div class="card"><h3>{escape(child)}</h3><p class="small">Approved days: {len(sort_school_days(approved.get(child,{}).get("parsed_days",[])))}</p></div>'
        for child in CHILDREN
    )
    child_options = "".join(f'<option value="{escape(c)}">{escape(c)}</option>' for c in CHILDREN)
    _s = load_app_settings()
    _school_mode_html = _school_mode_section(_s.get("family_constraints", {}))
    body = f"""
    {page_header("School")}
    {render_status_message(status_message)}

    <!-- Fr Gregory banner -->
    <a href="/headmaster" style="display:flex;align-items:center;gap:16px;
         background:linear-gradient(135deg,#1e3566 0%,#2d4a8a 100%);
         border-radius:14px;padding:18px 22px;margin-bottom:18px;
         text-decoration:none;color:white;box-shadow:0 2px 8px rgba(30,53,102,.18);">
      <span style="font-size:2.4em;line-height:1;">🎓</span>
      <div style="flex:1;">
        <div style="font-weight:800;font-size:1.05em;letter-spacing:.01em;">Father Gregory</div>
        <div style="font-size:0.83em;opacity:.85;margin-top:2px;">
          Headmaster &amp; Academic Director — lesson plans, pacing, subject guidance
        </div>
      </div>
      <span style="font-size:1.4em;opacity:.6;">›</span>
    </a>

    <!-- Analyze Assignment (primary entry) -->
    <a href="/assignment-analyzer" style="display:flex;align-items:center;gap:14px;
         background:linear-gradient(135deg,#fef3c7 0%,#fde68a 100%);
         border:1.5px solid #d4a574;border-radius:12px;padding:14px 18px;
         margin-bottom:12px;text-decoration:none;color:inherit;
         box-shadow:0 1px 3px rgba(180,140,80,.15);">
      <span style="font-size:1.9em;line-height:1;">📥</span>
      <div style="flex:1;">
        <div style="font-weight:800;font-size:0.98em;color:#7c4a1e;">Analyze Assignment</div>
        <div style="font-size:0.78em;color:#8b6f47;margin-top:2px;">
          Snap a photo, upload a PDF, or paste text — AI sorts it for you
        </div>
      </div>
      <span style="font-size:1.3em;color:#b88a4a;">›</span>
    </a>

    <!-- Gradebook (companion to analyzer) -->
    <a href="/gradebook" style="display:flex;align-items:center;gap:14px;
         background:linear-gradient(135deg,#ecfccb 0%,#d9f99d 100%);
         border:1.5px solid #84cc16;border-radius:12px;padding:14px 18px;
         margin-bottom:12px;text-decoration:none;color:inherit;
         box-shadow:0 1px 3px rgba(132,204,22,.15);">
      <span style="font-size:1.9em;line-height:1;">📓</span>
      <div style="flex:1;">
        <div style="font-weight:800;font-size:0.98em;color:#3f6212;">Gradebook</div>
        <div style="font-size:0.78em;color:#4d7c0f;margin-top:2px;">
          Recorded grades by subject &amp; school year — GPA for JP &amp; Joseph
        </div>
      </div>
      <span style="font-size:1.3em;color:#65a30d;">›</span>
    </a>

    <!-- Quick-access row -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:22px;">
      <a href="/curriculum" style="display:flex;align-items:center;gap:12px;
           background:#fff;border:1.5px solid #c4b5fd;border-radius:12px;padding:14px 16px;
           text-decoration:none;color:inherit;">
        <span style="font-size:1.7em;">📚</span>
        <div>
          <div style="font-weight:700;font-size:0.92em;color:#5b21b6;">Curriculum</div>
          <div style="font-size:0.75em;color:#8b7355;margin-top:1px;">Subjects &amp; pacing</div>
        </div>
        <span style="margin-left:auto;color:#c4b5fd;">›</span>
      </a>
      <a href="/week-school" style="display:flex;align-items:center;gap:12px;
           background:#fff;border:1.5px solid #bfdbfe;border-radius:12px;padding:14px 16px;
           text-decoration:none;color:inherit;">
        <span style="font-size:1.7em;">📅</span>
        <div>
          <div style="font-weight:700;font-size:0.92em;color:#1e40af;">Week Progress</div>
          <div style="font-size:0.75em;color:#8b7355;margin-top:1px;">Full week at a glance</div>
        </div>
        <span style="margin-left:auto;color:#bfdbfe;">›</span>
      </a>
    </div>

    <!-- School Mode Settings -->
    <div style="background:#fff;border:1.5px solid #e5e7eb;border-radius:14px;
                padding:18px 20px;margin-bottom:22px;">
      <div style="font-weight:800;font-size:0.95em;color:#374151;margin-bottom:4px;">⚙️ School Mode</div>
      <p style="font-size:0.82em;color:#6b7280;margin:0 0 14px;">
        Temporarily adjust which subjects appear in the boys' daily lists.
        Use <strong>Light week</strong> when sick or traveling; use <strong>Custom pause</strong>
        to hide specific subjects indefinitely.
      </p>
      {_school_mode_html}
      <div style="margin-top:12px;">
        <button type="button" onclick="saveSchoolSettings()"
                id="school-save-btn"
                style="padding:9px 22px;font-size:0.9em;background:#1e3566;color:white;
                       border:none;border-radius:8px;cursor:pointer;font-family:inherit;font-weight:600;">
          Save School Mode
        </button>
        <span id="school-save-status" style="font-size:0.82em;margin-left:12px;color:#6b7280;"></span>
      </div>
    </div>
    <script>
    function saveSchoolSettings() {{
      var mode   = document.getElementById('school-mode-select').value;
      var coreEl = document.querySelector('[name="fc_core_subjects"]');
      var pausEl = document.querySelector('[name="fc_paused_subjects"]');
      var btn    = document.getElementById('school-save-btn');
      var status = document.getElementById('school-save-status');
      btn.disabled = true;
      status.style.color = '#6b7280';
      status.textContent = 'Saving\u2026';
      fetch('/school-settings-save', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: 'fc_school_mode=' + encodeURIComponent(mode)
            + '&fc_core_subjects='  + encodeURIComponent(coreEl ? coreEl.value : '')
            + '&fc_paused_subjects=' + encodeURIComponent(pausEl ? pausEl.value : '')
      }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
        btn.disabled = false;
        if (d.ok) {{
          status.style.color = '#16a34a';
          status.textContent = '\u2713 Saved';
          setTimeout(function() {{ status.textContent = ''; }}, 2500);
        }} else {{
          status.style.color = '#dc2626';
          status.textContent = 'Error saving';
        }}
      }}).catch(function() {{
        btn.disabled = false;
        status.style.color = '#dc2626';
        status.textContent = 'Error saving';
      }});
    }}
    </script>

    <div class="two-col">
        <div class="card">
            <h2>Upload or Paste School List</h2>
            <form id="school-upload-form" method="POST" action="/school-upload" enctype="multipart/form-data">
                <input type="hidden" name="gdrive_file_id" id="gdf-id">
                <input type="hidden" name="gdrive_file_mime" id="gdf-mime">
                <input type="hidden" name="gdrive_file_name" id="gdf-name">
                <input type="hidden" name="gdrive_url" value="">
                <label>Child</label>
                <select name="child">{child_options}</select>

                <!-- Google Drive Browser -->
                <div style="background:#f0f7ff;border:1px solid #bfdbfe;border-radius:10px;
                            padding:14px 16px;margin-bottom:16px;">
                  <div style="font-weight:700;font-size:0.88em;color:#1e40af;margin-bottom:6px;">
                    📁 Import from Google Drive
                  </div>
                  <div id="gd-selected" style="display:none;background:#e0f2fe;border-radius:7px;
                       padding:8px 12px;margin-bottom:10px;font-size:0.85em;color:#0369a1;
                       display:flex;align-items:center;gap:8px;">
                    <span>📄</span><span id="gd-selected-name"></span>
                    <button type="button" onclick="gdClear()"
                            style="margin-left:auto;background:none;border:none;
                                   color:#64748b;cursor:pointer;padding:0;font-size:1em;">✕</button>
                  </div>
                  <button type="button" id="gd-browse-btn"
                          onclick="gdOpen('root')"
                          style="background:#1e40af;color:white;border:none;border-radius:7px;
                                 padding:9px 16px;font-size:0.88em;font-weight:600;cursor:pointer;
                                 width:100%;">Browse Google Drive</button>
                  <div id="gd-browser" style="display:none;margin-top:10px;
                       border:1px solid #bfdbfe;border-radius:8px;overflow:hidden;">
                    <div id="gd-breadcrumb" style="background:#e0f2fe;padding:8px 12px;
                         font-size:0.78em;color:#0369a1;font-weight:600;"></div>
                    <div id="gd-list" style="max-height:280px;overflow-y:auto;"></div>
                  </div>
                </div>

                <label style="color:var(--ink-faint);font-size:0.8em;">— or choose a local file —</label>
                <input type="file" name="file"
                       style="display:block;width:100%;font-size:16px;margin-bottom:16px;cursor:pointer;">
                <label style="color:var(--ink-faint);font-size:0.8em;">— or paste text —</label>
                <textarea name="raw_text" rows="5"
                          placeholder="Paste the school list text here..."></textarea>
                <button type="submit">Import &amp; Create Preview</button>
            </form>
            <script>
            (function(){{
              var stack = [];
              function gdOpen(fid, fname) {{
                stack.push({{id: fid, name: fname || 'My Drive'}});
                gdLoad(fid);
              }}
              function gdUp() {{
                if (stack.length > 1) stack.pop();
                gdLoad(stack[stack.length-1].id);
              }}
              function gdLoad(fid) {{
                var list = document.getElementById('gd-list');
                var browser = document.getElementById('gd-browser');
                browser.style.display = 'block';
                list.innerHTML = '<div style="padding:16px;text-align:center;color:#64748b;font-size:0.85em;">Loading...</div>';
                gdCrumb();
                fetch('/gdrive-files?folder=' + encodeURIComponent(fid))
                  .then(function(r){{ return r.json(); }})
                  .then(function(data) {{
                    if (data.error) {{ list.innerHTML = '<div style="padding:12px;color:#b91c1c;font-size:0.85em;">Error: ' + data.error + '</div>'; return; }}
                    var files = data.files || [];
                    if (!files.length) {{ list.innerHTML = '<div style="padding:12px;color:#64748b;font-size:0.85em;">No files found.</div>'; return; }}
                    list.innerHTML = files.map(function(f) {{
                      var isFolder = f.mimeType === 'application/vnd.google-apps.folder';
                      var readable = ['application/pdf','application/vnd.google-apps.document','text/plain'].indexOf(f.mimeType) >= 0;
                      var icon = isFolder ? '📁' : (f.mimeType === 'application/pdf' ? '📄' : (f.mimeType.indexOf('document') >= 0 ? '📝' : '📃'));
                      var style = 'display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid #e0f2fe;cursor:pointer;font-size:0.88em;';
                      if (!isFolder && !readable) style += 'opacity:0.45;pointer-events:none;';
                      var onclick = isFolder
                        ? 'gdOpen(' + JSON.stringify(f.id) + ',' + JSON.stringify(f.name) + ')'
                        : (readable ? 'gdSelect(' + JSON.stringify(f.id) + ',' + JSON.stringify(f.mimeType) + ',' + JSON.stringify(f.name) + ')' : '');
                      return '<div style="' + style + '" onclick="' + onclick + '">' + icon + ' <span>' + f.name + '</span></div>';
                    }}).join('');
                  }})
                  .catch(function(e) {{ list.innerHTML = '<div style="padding:12px;color:#b91c1c;font-size:0.85em;">Failed to load.</div>'; }});
              }}
              function gdCrumb() {{
                var crumb = document.getElementById('gd-breadcrumb');
                var parts = stack.map(function(s, i) {{
                  if (i === stack.length - 1) return '<b>' + s.name + '</b>';
                  return '<span onclick="gdJump(' + i + ')" style="cursor:pointer;text-decoration:underline;">' + s.name + '</span>';
                }});
                crumb.innerHTML = (stack.length > 1 ? '<span onclick="gdUp()" style="cursor:pointer;margin-right:6px;">&#8592;</span>' : '') + parts.join(' › ');
              }}
              window.gdOpen = gdOpen;
              window.gdUp = gdUp;
              window.gdJump = function(idx) {{
                stack = stack.slice(0, idx + 1);
                gdLoad(stack[stack.length-1].id);
              }};
              window.gdSelect = function(id, mime, name) {{
                document.getElementById('gdf-id').value = id;
                document.getElementById('gdf-mime').value = mime;
                document.getElementById('gdf-name').value = name;
                document.getElementById('gd-selected-name').textContent = name;
                document.getElementById('gd-selected').style.display = 'flex';
                document.getElementById('gd-browser').style.display = 'none';
                document.getElementById('gd-browse-btn').textContent = 'Change file';
              }};
              window.gdClear = function() {{
                document.getElementById('gdf-id').value = '';
                document.getElementById('gdf-mime').value = '';
                document.getElementById('gdf-name').value = '';
                document.getElementById('gd-selected').style.display = 'none';
                document.getElementById('gd-browse-btn').textContent = 'Browse Google Drive';
                stack = [];
              }};
            }})();
            </script>
        </div>
        <div class="card">
            <h2>Approved Weeks</h2>
            {approved_cards or "<p class='muted'>No approved school weeks yet.</p>"}
        </div>
    </div>
    <h2>Preview</h2>
    {preview_cards or "<div class='card'><p class='muted'>No previews yet.</p></div>"}"""
    return html_page("School", body)


def render_school_edit_page(child: str, status_message: str = "") -> str:
    preview = load_school_preview(child)
    if not preview:
        return html_page("Edit School Preview", f"{page_header('Edit School Preview')}<div class='card'><p class='muted'>No preview found for {escape(child)}.</p></div>")
    parsed      = preview.get("parsed", {})
    parsed_days = sort_school_days(parsed.get("parsed_days", []))
    filename    = preview.get("filename","Untitled")
    raw_text    = preview.get("raw_text","")
    raw_text_editor = f"""
    <div class="card"><h2>Edit Raw Text</h2>
        <form method="POST" action="/reparse-school-preview">
            <input type="hidden" name="child" value="{escape(child)}">
            <label>Raw text</label><textarea name="raw_text" rows="18">{escape(raw_text)}</textarea>
            <button type="submit">Reparse Raw Text</button>
        </form>
    </div>"""
    if not parsed_days:
        body = f"{page_header(f'Edit School Preview — {child}')}{render_status_message(status_message)}<div class='card'><p class='small'>Source: {escape(filename)}</p><p class='small'>No parsed day blocks. Edit raw text below.</p></div>{raw_text_editor}"
        return html_page("Edit School Preview", body)
    day_forms = ""
    for day_index, day in enumerate(parsed_days):
        day_label = day.get("day_label",""); weekday = day.get("weekday",""); blocks = day.get("blocks",[])
        block_forms = ""
        for block_index, block in enumerate(blocks):
            subj = escape(block.get("subject","")); asgn = escape(block.get("assignment_text",""))
            block_forms += f"""
            <div class="preview-edit-block">
                <input type="hidden" name="block_count__{day_index}" value="{len(blocks)+1}">
                <div class="block-toolbar">
                    <div><label>Order</label><input type="number" name="order__{day_index}__{block_index}" value="{block_index+1}"></div>
                    <div class="block-remove"><input type="checkbox" name="delete__{day_index}__{block_index}" value="yes"><label>Delete this block</label></div>
                </div>
                <label>Subject</label><input type="text" name="subject__{day_index}__{block_index}" value="{subj}">
                <label>Assignment Text</label><textarea name="assignment__{day_index}__{block_index}" rows="6">{asgn}</textarea>
            </div>"""
        nb = len(blocks)
        block_forms += f"""
        <div class="preview-edit-block">
            <input type="hidden" name="block_count__{day_index}" value="{nb+1}">
            <h4>Add New Block</h4>
            <div class="block-toolbar">
                <div><label>Order</label><input type="number" name="order__{day_index}__{nb}" value="{nb+1}"></div>
                <div></div>
            </div>
            <label>Subject</label><input type="text" name="subject__{day_index}__{nb}" value="">
            <label>Assignment Text</label><textarea name="assignment__{day_index}__{nb}" rows="5"></textarea>
        </div>"""
        wd_opts = "".join(f'<option value="{escape(w)}" {"selected" if w==weekday else ""}>{escape(w)}</option>' for w in WEEKDAYS)
        day_forms += f"""
        <div class="card">
            <h3>{escape(day_label or weekday)}</h3>
            <label>Weekday</label><select name="weekday__{day_index}">{wd_opts}</select>
            <label>Day label</label><input type="text" name="day_label__{day_index}" value="{escape(day_label)}">
            {block_forms}
        </div>"""
    body = f"""
    {page_header(f"Edit School Preview — {child}")}
    {render_status_message(status_message)}
    <div class="card"><p class="small">Source: {escape(filename)}</p><p class="small">Correct weekday placement, reorder or delete blocks, then approve from the School page.</p></div>
    <form method="POST" action="/save-school-preview-edits">
        <input type="hidden" name="child" value="{escape(child)}">
        <input type="hidden" name="day_count" value="{len(parsed_days)}">
        {day_forms}
        <button type="submit">Save Preview Edits</button>
    </form>
    {raw_text_editor}"""
    return html_page("Edit School Preview", body)


# ── Thank-You Card Reminders page ─────────────────────────────────────────────
def render_thankyou_page() -> str:
    from datetime import date as _d, timedelta as _td
    today     = str(_d.today())
    reminders = load_thankyou_reminders()
    pending   = [r for r in reminders if isinstance(r, dict) and r.get("status") == "pending"]
    done_list = [r for r in reminders if isinstance(r, dict) and r.get("status") in ("done", "dismissed")]

    # Sort pending: overdue first, then upcoming
    pending_sorted = sorted(pending, key=lambda r: r.get("reminder_date","9999"))

    def _reminder_card(r: dict) -> str:
        rid      = escape(r.get("id",""))
        ename    = escape(r.get("event_name",""))
        ppl      = escape(r.get("people",""))
        edate    = escape(r.get("event_date",""))
        rdate    = escape(r.get("reminder_date",""))
        note     = escape(r.get("note",""))
        assignee = escape(r.get("assigned_to","Family"))
        is_due   = r.get("reminder_date","9999") <= today
        border   = "#e8c97a" if is_due else "#e9d8c8"
        bg       = "#fef3e2" if is_due else "#fdf8f4"
        badge    = ('<span style="background:#d97706;color:white;font-size:0.75em;'
                    'font-weight:700;border-radius:10px;padding:2px 8px;margin-left:8px;">DUE</span>'
                    if is_due else "")
        return f"""
    <div style="background:{bg};border:1.5px solid {border};border-radius:12px;
                padding:14px 16px;margin-bottom:12px;">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;">
            <div>
                <div style="font-weight:700;font-size:0.97em;">{ename}{badge}</div>
                {"<div style='font-size:0.88em;color:#78564b;margin-top:3px;'>For: " + ppl + "</div>" if ppl else ""}
                <div style="font-size:0.82em;color:#9ca3af;margin-top:4px;">
                    Event: {edate} &bull; Send reminder: {rdate} &bull; &#9993; {assignee}
                </div>
                {"<div style='font-size:0.85em;color:#6b4f3a;margin-top:4px;font-style:italic;'>" + note + "</div>" if note else ""}
            </div>
            <div style="display:flex;flex-direction:column;gap:8px;flex-shrink:0;">
                <form method="POST" action="/thankyou-done">
                    <input type="hidden" name="id" value="{rid}">
                    <button type="submit" style="background:#5a7a5a;color:white;border:none;
                            border-radius:7px;padding:7px 14px;font-size:0.85em;
                            font-weight:600;cursor:pointer;width:100%;">
                        &#10003; Card Sent
                    </button>
                </form>
                <form method="POST" action="/thankyou-dismiss">
                    <input type="hidden" name="id" value="{rid}">
                    <button type="submit" style="background:none;border:1px solid #d1b8a8;
                            border-radius:7px;padding:7px 14px;font-size:0.85em;
                            color:#78564b;cursor:pointer;width:100%;">
                        Skip
                    </button>
                </form>
            </div>
        </div>
    </div>"""

    cards_html = "".join(_reminder_card(r) for r in pending_sorted)
    if not cards_html:
        cards_html = "<div class='card'><p class='muted'>No pending thank-you reminders. You're all caught up.</p></div>"

    # Done/dismissed history
    done_html = ""
    if done_list:
        done_html = "<h2 style='margin-top:32px;color:#9ca3af;'>Sent / Skipped</h2>"
        for r in sorted(done_list, key=lambda x: x.get("reminder_date",""), reverse=True)[:10]:
            st = "Sent" if r.get("status") == "done" else "Skipped"
            done_html += (
                f"<div style='padding:8px 0;border-bottom:1px solid #f0e8de;display:flex;"
                f"justify-content:space-between;align-items:center;font-size:0.88em;'>"
                f"<span style='color:#6b7280;text-decoration:line-through;'>"
                f"{escape(r.get('event_name',''))} — {escape(r.get('people',''))}"
                f"</span><span style='color:#9ca3af;'>{st}</span></div>"
            )

    # Auto-fill reminder date (2 days from today) for the form
    default_reminder = str(_d.today() + _td(days=2))
    default_event    = str(_d.today())

    body = f"""
    {page_header("Thank-You Cards")}
    <div class="card">
        <h3>Add Reminder</h3>
        <p style="font-size:0.88em;color:#78564b;margin-bottom:14px;">
            Flag an event that deserves a thank-you card. The app will remind you when to send it.
        </p>
        <form method="POST" action="/thankyou-add">
            <label>Event or occasion</label>
            <input type="text" name="event_name" placeholder="e.g. Birthday party at the Martins" required>
            <label>People to thank</label>
            <input type="text" name="people" placeholder="e.g. the Martins, Grandma Rose">
            <label>Who is responsible for the card?</label>
            <select name="assigned_to">
                <option value="Family">Family (all)</option>
                <option value="Lauren">Lauren</option>
                <option value="John">John</option>
                <option value="JP">JP</option>
                <option value="Joseph">Joseph</option>
                <option value="Michael">Michael</option>
            </select>
            <label>Date of the event</label>
            <input type="date" name="event_date" value="{default_event}">
            <label>Send reminder on</label>
            <input type="date" name="reminder_date" value="{default_reminder}">
            <label>Note (optional)</label>
            <input type="text" name="note" placeholder="e.g. JP and Joseph should both sign it">
            <button type="submit">Add Reminder</button>
        </form>
    </div>
    <h2>Pending</h2>
    {cards_html}
    {done_html}"""
    return html_page("Thank-You Cards", body)