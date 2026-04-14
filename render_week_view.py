"""
render_week_view.py — Family Week at a Glance

A mobile-first weekly overview showing:
  • Horizontally-scrollable 7-day strip with feasts and events
  • Lauren's tasks due this week
  • Day-by-day family event + schedule highlights
  • Kids' school/task snapshot
"""
import json
import os
from datetime import date, timedelta
from html import escape

from ui_helpers import html_page, top_nav

MANUAL_TASKS_FILE = "data/manual_tasks.json"
EVENTS_FILE       = "data/events.json"

CHILDREN_ORDER = ["JP", "Joseph", "Michael"]
CHILD_COLORS   = {
    "JP":      "#DC2626",
    "Joseph":  "#16A34A",
    "Michael": "#EA580C",
    "James":   "#7C3AED",
    "Lauren":  "#7C5C2E",
    "John":    "#1D4ED8",
}
WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_FULL  = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# ── helpers ───────────────────────────────────────────────────────────────────

def _week_key(for_date: date = None) -> str:
    if for_date is None:
        for_date = date.today()
    return for_date.strftime("%Y-%W")


def _week_dates(week_key: str):
    try:
        year, wk = week_key.split("-")
        from datetime import date as _d
        jan4 = _d(int(year), 1, 4)
        mon  = jan4 + timedelta(weeks=int(wk) - jan4.isocalendar()[1],
                                days=-jan4.weekday())
        return [mon + timedelta(days=i) for i in range(7)]
    except Exception:
        today = date.today()
        mon   = today - timedelta(days=today.weekday())
        return [mon + timedelta(days=i) for i in range(7)]


def _load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _week_feasts(wdates):
    result = {d.strftime("%A"): "" for d in wdates}
    season_names = {"lent", "advent", "christmas", "easter", "ordinary time",
                    "holy week", "easter triduum"}
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
        pass
    return result


_REC_WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

def _expand_events(wdates) -> dict:
    """Return {weekday_name: [event_title, ...]} for the given week."""
    result = {d.strftime("%A"): [] for d in wdates}
    mon, sun = wdates[0], wdates[-1]

    raw = _load_json(EVENTS_FILE, {})
    events = raw.get("data", []) if isinstance(raw, dict) else raw

    for ev in events:
        title = ev.get("title", "Event")
        rec   = ev.get("recurrence", {}) or {}
        rtype = rec.get("type", "none")

        try:
            start = date.fromisoformat(str(ev.get("start_date", ""))[:10])
        except Exception:
            continue

        if rtype == "none":
            if mon <= start <= sun:
                result[start.strftime("%A")].append(title)

        elif rtype == "weekly":
            weekdays = [_REC_WEEKDAY_MAP[wd.lower()]
                        for wd in rec.get("by_weekday", [])
                        if wd.lower() in _REC_WEEKDAY_MAP]
            until_raw = rec.get("until")
            until = date.fromisoformat(until_raw[:10]) if until_raw else None
            for d in wdates:
                if d.weekday() in weekdays and d >= start:
                    if until and d > until:
                        continue
                    result[d.strftime("%A")].append(title)

        elif rtype == "monthly":
            for d in wdates:
                if d.day == start.day and d >= start:
                    result[d.strftime("%A")].append(title)

        elif rtype == "yearly":
            for d in wdates:
                if d.month == start.month and d.day == start.day and d >= start:
                    result[d.strftime("%A")].append(title)

    # Also pull ICS-fed events if available
    try:
        from render_settings import load_app_settings
        settings = load_app_settings()
        ical_url = (settings.get("family_constraints", {}).get("ical_url", "")
                    or settings.get("ical_url", ""))
        if ical_url:
            from render_calendar import fetch_ics_events
            for ev in fetch_ics_events(ical_url, "Family"):
                try:
                    ev_date = date.fromisoformat(ev.get("date", "")[:10])
                    if mon <= ev_date <= sun:
                        day_name = ev_date.strftime("%A")
                        t = ev.get("title", ev.get("summary", "Event"))
                        if t not in result[day_name]:
                            result[day_name].append(t)
                except Exception:
                    pass
    except Exception:
        pass

    return result


def _lauren_tasks_this_week(wdates) -> list:
    mon, sun = wdates[0], wdates[-1]
    tasks = _load_json(MANUAL_TASKS_FILE, [])
    out = []
    for t in tasks:
        if str(t.get("status", "active")).upper() != "ACTIVE":
            continue
        assigned = str(t.get("assigned_to", ""))
        if assigned not in ("Lauren", "Mom"):
            continue
        due_raw = str(t.get("due_date", "")).strip()
        if not due_raw:
            continue
        try:
            due = date.fromisoformat(due_raw)
        except Exception:
            continue
        if mon <= due <= sun:
            out.append({
                "text":     t.get("text", ""),
                "due":      due,
                "priority": t.get("priority", "MEDIUM"),
                "subtasks": t.get("subtasks", []),
            })
    out.sort(key=lambda x: x["due"])
    return out


def _all_tasks_by_day(wdates) -> dict:
    """All active tasks assigned to anyone, keyed by due-date weekday name."""
    mon, sun = wdates[0], wdates[-1]
    tasks    = _load_json(MANUAL_TASKS_FILE, [])
    by_day   = {d.strftime("%A"): [] for d in wdates}
    for t in tasks:
        if str(t.get("status", "active")).upper() != "ACTIVE":
            continue
        due_raw = str(t.get("due_date", "")).strip()
        if not due_raw:
            continue
        try:
            due = date.fromisoformat(due_raw)
        except Exception:
            continue
        if mon <= due <= sun:
            by_day[due.strftime("%A")].append({
                "text":     t.get("text", ""),
                "assigned": t.get("assigned_to", ""),
            })
    return by_day


def _family_schedule_highlights(weekday_name: str) -> list:
    """Return 3–5 key time slots from Mom's FROL day template for a given weekday."""
    try:
        from data_helpers import get_frol_day_slots
        day = get_frol_day_slots(weekday_name, "Mom")
    except Exception:
        day = {}
    key_slots = []
    seen_texts = set()
    for time_str, text in day.items():
        if not isinstance(text, str) or not text.strip():
            continue
        t = text.strip()
        if t in seen_texts:
            continue
        seen_texts.add(t)
        if t.lower() in ("free", "—", "-", ""):
            continue
        key_slots.append((time_str, t))
        if len(key_slots) >= 5:
            break
    return key_slots


# ── rendering ─────────────────────────────────────────────────────────────────

def _priority_dot(priority: str) -> str:
    colors = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#6b7280"}
    c = colors.get(str(priority).upper(), "#6b7280")
    return f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{c};margin-right:5px;flex-shrink:0;margin-top:4px;"></span>'


def render_week_view(week_key: str = None) -> str:
    if not week_key:
        week_key = _week_key()

    wdates   = _week_dates(week_key)
    mon, sun = wdates[0], wdates[-1]
    today    = date.today()

    prev_key = _week_key(mon - timedelta(days=7))
    next_key = _week_key(mon + timedelta(days=7))
    prev_mon = (mon - timedelta(days=7)).strftime("%-d %b")
    next_mon = (mon + timedelta(days=7)).strftime("%-d %b")

    # Month label — smart: "April 6–12" or "Mar 30 – Apr 5"
    if mon.month == sun.month:
        week_label = mon.strftime("%B %-d") + "–" + sun.strftime("%-d, %Y")
    else:
        week_label = mon.strftime("%b %-d") + " – " + sun.strftime("%b %-d, %Y")

    feasts     = _week_feasts(wdates)
    events     = _expand_events(wdates)
    tasks_by_day = _all_tasks_by_day(wdates)
    lauren_tasks = _lauren_tasks_this_week(wdates)

    # ── 1. Week strip (horizontal scroll row) ──────────────────────────────────
    strip_cells = ""
    for d in wdates:
        dn       = d.strftime("%A")
        ds       = WEEKDAY_SHORT[d.weekday()]
        is_today = (d == today)
        is_wknd  = d.weekday() >= 5
        feast    = feasts.get(dn, "")
        evs      = events.get(dn, [])
        tasks    = tasks_by_day.get(dn, [])

        today_ring = "box-shadow:0 0 0 2px var(--brown);" if is_today else ""
        today_num_style = "background:var(--brown);color:white;" if is_today else ""
        op = "opacity:0.55;" if is_wknd else ""

        dot_row = ""
        if feast:
            dot_row += '<div style="width:6px;height:6px;border-radius:50%;background:#b45309;margin:2px auto 0;"></div>'
        if evs:
            dot_row += '<div style="width:6px;height:6px;border-radius:50%;background:#7C3AED;margin:2px auto 0;"></div>'
        if tasks:
            dot_row += '<div style="width:6px;height:6px;border-radius:50%;background:#2563eb;margin:2px auto 0;"></div>'

        strip_cells += f"""
<div style="flex-shrink:0;width:46px;text-align:center;{op}">
  <div style="font-size:0.64em;font-weight:700;color:var(--ink-muted);
              letter-spacing:.04em;margin-bottom:4px;">{ds}</div>
  <div style="width:32px;height:32px;border-radius:50%;display:flex;
              align-items:center;justify-content:center;margin:0 auto;
              font-size:0.85em;font-weight:800;{today_num_style}{today_ring}">
    {d.day}
  </div>
  <div style="min-height:12px;margin-top:3px;">{dot_row}</div>
</div>"""

    # ── 2. Legend ──────────────────────────────────────────────────────────────
    legend = """
<div style="display:flex;gap:14px;padding:6px 16px 2px;font-size:0.68em;color:var(--ink-muted);">
  <span><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#b45309;margin-right:3px;vertical-align:middle;"></span>Feast</span>
  <span><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#7C3AED;margin-right:3px;vertical-align:middle;"></span>Event</span>
  <span><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#2563eb;margin-right:3px;vertical-align:middle;"></span>Task due</span>
</div>"""

    # ── 3. Lauren's tasks this week ────────────────────────────────────────────
    if lauren_tasks:
        lauren_rows = ""
        for t in lauren_tasks:
            is_today_task = (t["due"] == today)
            is_overdue    = (t["due"] < today)
            due_label     = (
                "<span style='color:#ef4444;font-weight:700;'>Today</span>" if is_today_task
                else ("<span style='color:#dc2626;'>Overdue</span>" if is_overdue
                      else escape(t["due"].strftime("%a %-d")))
            )
            sub_html = ""
            for s in t.get("subtasks", [])[:4]:
                sub_html += f'<div style="font-size:0.78em;color:var(--ink-muted);padding:1px 0 1px 16px;">· {escape(s)}</div>'
            if len(t.get("subtasks", [])) > 4:
                sub_html += f'<div style="font-size:0.75em;color:var(--ink-faint);padding:1px 0 1px 16px;">+{len(t["subtasks"])-4} more</div>'

            lauren_rows += f"""
<div style="display:flex;align-items:flex-start;gap:10px;padding:9px 0;
            border-bottom:1px solid var(--border-light);">
  {_priority_dot(t["priority"])}
  <div style="flex:1;min-width:0;">
    <div style="font-size:0.9em;font-weight:600;color:var(--ink);">{escape(t["text"])}</div>
    {sub_html}
  </div>
  <div style="font-size:0.75em;white-space:nowrap;margin-top:2px;">{due_label}</div>
</div>"""

        tasks_section = f"""
<div class="card" style="margin-bottom:10px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-muted);margin-bottom:6px;">📌 Your tasks this week</div>
  {lauren_rows}
</div>"""
    else:
        tasks_section = """
<div class="card" style="margin-bottom:10px;text-align:center;color:var(--ink-muted);font-size:0.88em;padding:18px;">
  No tasks due for you this week 🎉
</div>"""

    # ── 4. Day cards ───────────────────────────────────────────────────────────
    day_cards = ""
    for d in wdates:
        dn       = d.strftime("%A")
        is_today = (d == today)
        is_wknd  = d.weekday() >= 5
        feast    = feasts.get(dn, "")
        evs      = events.get(dn, [])
        day_tasks = tasks_by_day.get(dn, [])

        if is_wknd and not evs and not feast and not day_tasks:
            continue  # skip empty weekend days

        brd_color   = "var(--brown)" if is_today else "var(--border)"
        brd_width   = "2px" if is_today else "1px"
        header_bg   = "background:var(--gold-light);" if is_today else ""
        today_badge = ('<span style="font-size:0.68em;background:var(--brown);color:white;'
                       'padding:2px 7px;border-radius:10px;margin-left:6px;font-weight:700;">'
                       'Today</span>') if is_today else ""

        # Feast
        feast_html = (
            f'<div style="font-size:0.78em;color:#b45309;font-weight:600;margin-bottom:5px;">✝ {escape(feast)}</div>'
        ) if feast else ""

        # Events
        ev_html = ""
        for ev in evs:
            ev_html += (
                f'<div style="font-size:0.82em;color:var(--ink);padding:4px 8px;'
                f'background:#f3f0ff;border-radius:7px;margin-bottom:4px;">📅 {escape(ev)}</div>'
            )

        # Tasks due this day
        tasks_html = ""
        for dt in day_tasks:
            person = dt.get("assigned", "")
            color  = CHILD_COLORS.get(person, "#6b7280")
            badge  = (f'<span style="font-size:0.68em;background:{color}20;color:{color};'
                      f'padding:1px 6px;border-radius:8px;font-weight:700;margin-right:5px;">'
                      f'{escape(person)}</span>') if person else ""
            tasks_html += (
                f'<div style="font-size:0.82em;color:var(--ink);display:flex;'
                f'align-items:flex-start;gap:4px;margin-bottom:3px;">'
                f'<span style="color:#2563eb;margin-top:1px;">·</span>'
                f'<span>{badge}{escape(dt["text"])}</span></div>'
            )

        # Family schedule highlights (only for school days)
        sched_html = ""
        if not is_wknd:
            highlights = _family_schedule_highlights(dn)
            if highlights:
                hl_rows = "".join(
                    f'<div style="display:flex;gap:8px;font-size:0.78em;padding:2px 0;">'
                    f'<span style="color:var(--ink-muted);white-space:nowrap;min-width:54px;">{escape(t)}</span>'
                    f'<span style="color:var(--ink);">{escape(v[:45])}</span></div>'
                    for t, v in highlights
                )
                sched_html = f"""
<details style="margin-top:8px;">
  <summary style="font-size:0.75em;font-weight:700;color:var(--ink-muted);
                  letter-spacing:.05em;cursor:pointer;list-style:none;
                  display:flex;align-items:center;gap:4px;">
    ⏱ Schedule highlights
  </summary>
  <div style="margin-top:6px;padding:6px 10px;background:var(--parchment);
              border-radius:8px;">{hl_rows}</div>
</details>"""

        has_content = feast or evs or day_tasks
        if not has_content and is_wknd:
            continue

        day_cards += f"""
<div class="card" style="margin-bottom:8px;border:{brd_width} solid {brd_color};{header_bg}">
  <div style="display:flex;align-items:center;margin-bottom:8px;">
    <span style="font-weight:800;font-size:0.95em;">{escape(dn)}</span>
    <span style="color:var(--ink-muted);font-size:0.82em;margin-left:6px;">
      {d.strftime("%B %-d")}
    </span>
    {today_badge}
  </div>
  {feast_html}
  {ev_html}
  {tasks_html}
  {sched_html}
</div>"""

    # ── 5. Kids quick-link strip ────────────────────────────────────────────────
    kids_strip = ""
    for child in CHILDREN_ORDER:
        color = CHILD_COLORS.get(child, "#6b7280")
        kids_strip += (
            f'<a href="/schedule/{escape(child)}" '
            f'style="flex:1;text-align:center;padding:10px 6px;'
            f'background:white;border:1.5px solid {color}40;border-radius:12px;'
            f'color:{color};font-weight:700;font-size:0.85em;text-decoration:none;">'
            f'<div style="font-size:1.2em;margin-bottom:3px;">📋</div>'
            f'{escape(child)}</a>'
        )

    # ── Assemble ───────────────────────────────────────────────────────────────
    nav = top_nav()

    body = f"""
{nav}
<div style="max-width:600px;margin:0 auto;padding:12px 14px 40px;">

  <div style="display:flex;align-items:center;justify-content:space-between;
              margin-bottom:14px;">
    <a href="/week?week={escape(prev_key)}"
       style="font-size:0.8em;color:var(--brown);text-decoration:none;
              padding:6px 10px;border:1px solid var(--border);border-radius:8px;">
      ← {prev_mon}
    </a>
    <div style="text-align:center;">
      <div style="font-size:1.05em;font-weight:800;">{escape(week_label)}</div>
      <div style="font-size:0.72em;color:var(--ink-muted);margin-top:1px;">Family Week</div>
    </div>
    <a href="/week?week={escape(next_key)}"
       style="font-size:0.8em;color:var(--brown);text-decoration:none;
              padding:6px 10px;border:1px solid var(--border);border-radius:8px;">
      {next_mon} →
    </a>
  </div>

  <div class="card" style="margin-bottom:12px;padding:14px 14px 10px;">
    <div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">
      <div style="display:flex;gap:6px;min-width:min-content;padding-bottom:4px;">
        {strip_cells}
      </div>
    </div>
    {legend}
  </div>

  {tasks_section}

  <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-muted);margin-bottom:8px;">📅 This Week</div>
  {day_cards if day_cards else '<div class="card" style="text-align:center;color:var(--ink-muted);padding:24px;">Nothing scheduled yet this week.</div>'}

  <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-muted);margin:16px 0 8px;">👦 Kids' Day Lists</div>
  <div style="display:flex;gap:8px;margin-bottom:8px;">{kids_strip}</div>
  <div style="text-align:center;margin-top:8px;">
    <a href="/plan-week?week={escape(week_key)}"
       style="font-size:0.85em;color:var(--brown);font-weight:700;">
      Open full week planner →
    </a>
  </div>

</div>"""

    return html_page("Week", body)
