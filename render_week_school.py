"""
Weekly school progress page — /week-school
Shows a subject × day grid for JP and Joseph for the current week,
with done/missed/upcoming status per cell.
Missed subjects carry forward via the existing carryover engine.
"""

from html import escape as _e
from datetime import date, timedelta

CHILDREN_SCHOOL = ["JP", "Joseph"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# Per-child color palette  (same as config.py child_color)
CHILD_COLORS = {
    "JP":     {"bg": "#1e3566", "light": "#eef1f8"},
    "Joseph": {"bg": "#14532d", "light": "#edf5f0"},
}


# ── Data helpers ──────────────────────────────────────────────────────────────

def _week_monday(iso: str) -> date:
    d = date.fromisoformat(iso)
    return d - timedelta(days=d.weekday())


def _days_in_week(monday: date):
    return [(monday + timedelta(days=i), WEEKDAYS[i]) for i in range(5)]


def _school_subjects_for_day(child: str, weekday: str):
    """
    Return ordered list of (subject, [checklist_items]) for a child on a weekday.
    """
    try:
        from daily_schedule_engine import extract_school_tasks_for_child
        blocks = extract_school_tasks_for_child(child, weekday)
        return [(b["subject"], b.get("checklist", [])) for b in blocks]
    except Exception:
        return []


def _registered_school_subjects(child: str, iso: str):
    """
    From task_registry, return {subject: [items]} that were actually planned
    for this child on this date.
    """
    try:
        from daily_schedule_engine import load_task_registry
        registry = load_task_registry()
        tasks = registry.get(iso, {}).get(child, [])
        subjects = {}
        for t in tasks:
            if t.startswith("SCHOOL::"):
                parts = t.split("::", 2)
                if len(parts) == 3:
                    subj, item = parts[1], parts[2]
                    subjects.setdefault(subj, []).append(item)
        return subjects
    except Exception:
        return {}


def _cell_status(child: str, iso: str, subject: str, items: list,
                 progress: dict, is_future: bool, is_today: bool = False):
    """
    Return 'done' | 'partial' | 'missed' | 'pending' | 'skip' | 'future'
    for a single (child, day, subject) cell.

    Task IDs for school are stored as SCHOOL::{child}::{iso}::{subject}::{item}
    (NOT via make_task_id which produces the old {iso}::{child}:: prefix order).
    """
    if is_future:
        return "future"
    if not items:
        return "skip"
    done = sum(
        1 for item in items
        if progress.get(f"SCHOOL::{child}::{iso}::{subject}::{item}", False)
    )
    if done == len(items):
        return "done"
    if done > 0:
        return "partial"
    # If today's class hasn't been checked yet — show as in-progress, not missed
    return "pending" if is_today else "missed"


def _build_child_week(child: str, days: list, today: date):
    """
    Build a dict describing this child's week:
      {
        "subjects":  [subj_name, ...],          # ordered union
        "day_cells": {weekday_iso: {subj: status}},
      }
    """
    try:
        from daily_schedule_engine import load_progress
        progress = load_progress()
    except Exception:
        progress = {}

    # Build ordered subject list across the whole week (curriculum order first)
    subject_order = {}
    for _, weekday in days:
        for subj, _ in _school_subjects_for_day(child, weekday):
            if subj not in subject_order:
                subject_order[subj] = len(subject_order)

    day_cells = {}
    for d, weekday in days:
        iso = d.isoformat()
        is_past   = d < today
        is_today  = d == today
        is_future = d > today

        if is_future:
            # Just mark what's expected
            scheduled = {s: items for s, items in _school_subjects_for_day(child, weekday)}
            cells = {}
            for subj in subject_order:
                cells[subj] = "future" if subj in scheduled else "skip"
            day_cells[iso] = cells
            continue

        # Past or today: use task_registry to see what was actually planned
        reg = _registered_school_subjects(child, iso)

        if not reg and is_past:
            # Nothing registered — either no school or page never loaded
            day_cells[iso] = {subj: "skip" for subj in subject_order}
            continue

        if not reg and is_today:
            # Today but schedule page not yet loaded — fall back to curriculum
            reg = {s: items for s, items in _school_subjects_for_day(child, weekday)}

        # Add any subjects from registry that weren't in the curriculum order
        for subj in reg:
            if subj not in subject_order:
                subject_order[subj] = len(subject_order)

        cells = {}
        for subj in subject_order:
            if subj in reg:
                cells[subj] = _cell_status(child, iso, subj, reg[subj],
                                            progress, is_future=False,
                                            is_today=is_today)
            else:
                cells[subj] = "skip"
        day_cells[iso] = cells

    # Re-derive final sorted subject list (may have grown from registry)
    subjects = sorted(subject_order.keys(), key=lambda s: subject_order[s])
    return {"subjects": subjects, "day_cells": day_cells}


# ── Stats ─────────────────────────────────────────────────────────────────────

def _week_stats(child_data: dict, days: list):
    done = missed = 0
    for d, _ in days:
        cells = child_data["day_cells"].get(d.isoformat(), {})
        for status in cells.values():
            if status == "done":
                done += 1
            elif status in ("missed", "partial"):
                # "pending" (today's not-yet-done) is excluded from missed count
                missed += 1
    return done, missed


# ── HTML helpers ──────────────────────────────────────────────────────────────

_STATUS_CELL = {
    "done":    ('<div style="width:22px;height:22px;border-radius:50%;'
                'background:#dcfce7;display:flex;align-items:center;justify-content:center;">'
                '<span style="font-size:0.65em;color:#15803d;font-weight:800;">✓</span></div>'),
    "partial": ('<div style="width:22px;height:22px;border-radius:50%;'
                'background:#fef9c3;display:flex;align-items:center;justify-content:center;">'
                '<span style="font-size:0.65em;color:#a16207;font-weight:800;">½</span></div>'),
    "missed":  ('<div style="width:22px;height:22px;border-radius:50%;'
                'background:#fef2f2;display:flex;align-items:center;justify-content:center;">'
                '<span style="font-size:0.65em;color:#ef4444;font-weight:700;">✗</span></div>'),
    "pending": ('<div style="width:22px;height:22px;border-radius:50%;'
                'background:#f0f4ff;display:flex;align-items:center;justify-content:center;">'
                '<span style="font-size:0.65em;color:#6b7280;font-weight:700;">○</span></div>'),
    "skip":    '<span style="font-size:0.72em;color:#d1d5db;">—</span>',
    "future":  '<span style="font-size:0.65em;color:#e5e7eb;">·</span>',
}


def _child_block_html(child: str, child_data: dict, days: list, today: date) -> str:
    colors  = CHILD_COLORS.get(child, {"bg": "#555", "light": "#f5f5f5"})
    bg      = colors["bg"]
    light   = colors["light"]
    done, missed = _week_stats(child_data, days)
    total   = done + missed + sum(
        1 for d, _ in days
        for status in child_data["day_cells"].get(d.isoformat(), {}).values()
        if status == "partial"
    )
    pct     = round(done / (done + missed) * 100) if (done + missed) else 0
    subjects = child_data["subjects"]

    # Grade label
    grade = {"JP": "Grade 8", "Joseph": "Grade 7"}.get(child, "")

    # Header
    bar_width = f"{pct}%"
    html = f'''
<div style="margin-bottom:16px;">
  <div style="font-size:0.62em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
              color:#9ca3af;margin-bottom:6px;">{_e(child)} &middot; {_e(grade)}</div>
  <div style="background:white;border-radius:12px;border:1px solid #e5e0d8;
              overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.05);">

    <!-- Block header -->
    <div style="background:{light};padding:10px 14px;display:flex;
                align-items:center;justify-content:space-between;
                border-bottom:1px solid rgba(0,0,0,.06);">
      <div style="display:flex;align-items:center;gap:6px;">
        <div style="width:8px;height:8px;border-radius:50%;background:{bg};"></div>
        <span style="font-size:0.88em;font-weight:800;color:{bg};">{_e(child)}</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <div style="height:5px;width:80px;background:rgba(0,0,0,.1);border-radius:3px;overflow:hidden;">
          <div style="height:100%;width:{bar_width};background:{bg};border-radius:3px;opacity:.75;"></div>
        </div>
        <span style="font-size:0.72em;font-weight:700;color:{bg};">
          {done}/{done+missed} done this week
        </span>
      </div>
    </div>

    <!-- Day header row -->
    <div style="display:flex;align-items:center;padding:5px 12px 3px;
                border-bottom:1px solid #f3f4f6;">
      <div style="flex:1;font-size:0.6em;font-weight:700;letter-spacing:.06em;
                  text-transform:uppercase;color:#9ca3af;">Subject</div>'''

    for d, wday in days:
        is_today_cell = d == today
        col = "#b45309" if is_today_cell else "#9ca3af"
        weight = "800" if is_today_cell else "600"
        initial = wday[0]
        html += f'''
      <div style="width:28px;text-align:center;font-size:0.65em;font-weight:{weight};color:{col};">
        {initial}
        {"<div style='width:4px;height:4px;border-radius:50%;background:#b45309;margin:1px auto 0;'></div>" if is_today_cell else ""}
      </div>'''

    html += '\n    </div>'

    # Subject rows
    for ri, subj in enumerate(subjects):
        border = "1px solid #fafafa" if ri < len(subjects) - 1 else "none"
        html += f'''
    <div style="display:flex;align-items:center;padding:5px 12px;
                border-bottom:{border};">
      <div style="flex:1;font-size:0.78em;color:#374151;white-space:nowrap;
                  overflow:hidden;text-overflow:ellipsis;padding-right:6px;
                  " title="{_e(subj)}">{_e(subj)}</div>'''

        for d, _ in days:
            iso = d.isoformat()
            status = child_data["day_cells"].get(iso, {}).get(subj, "skip")
            cell_html = _STATUS_CELL.get(status, _STATUS_CELL["skip"])
            html += f'''
      <div style="width:28px;display:flex;justify-content:center;align-items:center;">
        {cell_html}
      </div>'''

        html += '\n    </div>'

    html += '\n  </div>\n</div>'
    return html


# ── Page renderer ─────────────────────────────────────────────────────────────

def render_week_school_page(iso: str = None) -> str:
    today  = date.today()
    if iso:
        try:
            today = date.fromisoformat(iso)
        except ValueError:
            pass

    actual_today = date.today()
    monday = _week_monday(today.isoformat())
    days   = _days_in_week(monday)

    week_label = f"{monday.strftime('%b %-d')} – {(monday + timedelta(days=4)).strftime('%b %-d, %Y')}"

    prev_monday = monday - timedelta(weeks=1)
    next_monday = monday + timedelta(weeks=1)

    # Build data for each child
    child_blocks_html = ""
    for child in CHILDREN_SCHOOL:
        child_data = _build_child_week(child, days, actual_today)
        child_blocks_html += _child_block_html(child, child_data, days, actual_today)

    # Legend
    legend_items = [
        ("✓", "#15803d", "#dcfce7", "Done"),
        ("½", "#a16207", "#fef9c3", "Partial"),
        ("✗", "#ef4444", "#fef2f2", "Missed"),
        ("○", "#6b7280", "#f0f4ff", "Today/pending"),
        ("—", "#d1d5db", "transparent", "No class"),
        ("·", "#e5e7eb", "transparent", "Upcoming"),
    ]
    legend_html = ""
    for sym, col, bg, label in legend_items:
        bg_style = f"background:{bg};" if bg != "transparent" else ""
        legend_html += (
            f'<span style="display:inline-flex;align-items:center;gap:3px;">'
            f'<span style="display:inline-flex;align-items:center;justify-content:center;'
            f'width:18px;height:18px;border-radius:50%;{bg_style}font-size:0.7em;color:{col};font-weight:700;">'
            f'{sym}</span>'
            f'<span style="font-size:0.7em;color:#6b7280;">{label}</span>'
            f'</span>'
        )

    # Gregory quick-link
    gregory_btn = (
        '<a href="/gregory" style="display:inline-flex;align-items:center;gap:5px;'
        'font-size:0.78em;font-weight:700;color:#1e3566;text-decoration:none;'
        'background:#eef1f8;padding:7px 14px;border-radius:20px;'
        'border:1px solid #c5d0e8;">'
        '📚 Ask Father Gregory</a>'
    )

    # Week nav
    week_nav = f'''
<div style="display:flex;align-items:center;justify-content:space-between;
            padding:8px 14px;background:white;border-bottom:1px solid #e5e0d8;">
  <a href="/week-school?date={prev_monday.isoformat()}"
     style="font-size:0.8em;color:#9ca3af;text-decoration:none;padding:4px 8px;
            border-radius:8px;background:#f9fafb;">← Prev</a>
  <span style="font-size:0.82em;font-weight:700;color:#374151;">{_e(week_label)}</span>
  <a href="/week-school?date={next_monday.isoformat()}"
     style="font-size:0.8em;color:#9ca3af;text-decoration:none;padding:4px 8px;
            border-radius:8px;background:#f9fafb;">Next →</a>
</div>'''

    from ui_helpers import html_page, top_nav

    body = f"""
{top_nav()}

<!-- Page header -->
<div style="background:#1C1917;padding:14px 16px 12px;margin:-4px -4px 0;">
  <div style="font-size:0.62em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
              color:rgba(245,240,232,.45);margin-bottom:3px;">Father Gregory &middot; Headmaster</div>
  <div style="font-size:1.08em;font-weight:700;color:#faf7f2;">Weekly School Progress</div>
</div>

{week_nav}

<div style="padding:12px 12px 80px;">

  <!-- Legend + Gregory button -->
  <div style="display:flex;align-items:center;justify-content:space-between;
              flex-wrap:wrap;gap:8px;margin-bottom:14px;
              background:white;border-radius:10px;border:1px solid #e5e0d8;
              padding:8px 12px;">
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
      <span style="font-size:0.62em;font-weight:700;letter-spacing:.06em;
                   text-transform:uppercase;color:#9ca3af;">Key:</span>
      {legend_html}
    </div>
    {gregory_btn}
  </div>

  <!-- Child blocks -->
  {child_blocks_html}

  <!-- Carryover note -->
  <div style="background:white;border-radius:10px;border:1px solid #e5e0d8;
              padding:10px 14px;font-size:0.75em;color:#6b7280;line-height:1.5;
              border-left:3px solid #f59e0b;">
    <strong style="color:#92400e;">Missed subjects carry forward.</strong>
    Any subject marked ✗ will appear as a carryover task on the next school day's
    plan page until it is checked off.
  </div>

</div>
"""
    return html_page("Weekly School Progress", body)
