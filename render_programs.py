"""
render_programs.py — Coach's saved programs + the weekly exercise assignments,
all in one browseable page reachable from each person's POD card on /today.

Layout:
  - Top section: weekly exercise assignment grid (from exercise_assignments.json),
    one row per weekday × one column per person.
  - Per-person sections: each saved long-form program (title, body, saved date,
    delete button). Anchored so /programs#person-Joseph deep-links work.
  - Manual save form per person, in case Lauren wants to paste in something
    Coach wrote in chat.

Coach also auto-saves into here via the <save_program> tag (see
render_coach.py system prompt + _apply_coach_program_saves in app.py).
"""
from html import escape

from data_helpers import load_exercise_assignments, load_coach_programs
from ui_helpers import html_page

# Order matters — this is the order people appear on the page and in dropdowns
PEOPLE = ["Lauren", "JP", "Joseph", "Michael", "James"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

ACCENT = "#1a6e3e"


def _weekly_grid_html() -> str:
    """Render the per-day-per-person exercise assignment table."""
    assignments = load_exercise_assignments() or {}
    # Only show days that actually have any assignment, to keep it tight
    days_with_data = [d for d in WEEKDAYS if assignments.get(d)]
    if not days_with_data:
        return (
            '<div style="padding:14px;background:#f5f5f0;border-radius:10px;'
            'color:#666;font-size:.9em;">'
            "No weekly exercise assignments saved yet. Ask Coach to set them up."
            "</div>"
        )

    rows = []
    for day in days_with_data:
        day_data = assignments.get(day, {}) or {}
        cells = "".join(
            f'<td style="padding:8px 10px;vertical-align:top;border-top:1px solid #eee;'
            f'font-size:.82em;line-height:1.45;color:#333;">'
            f'{escape(day_data.get(p, "") or "—")}'
            f'</td>'
            for p in PEOPLE
        )
        rows.append(
            f'<tr><th style="padding:8px 10px;text-align:left;vertical-align:top;'
            f'border-top:1px solid #eee;font-size:.82em;color:{ACCENT};white-space:nowrap;">'
            f'{escape(day)}</th>{cells}</tr>'
        )

    headers = "".join(
        f'<th style="padding:8px 10px;text-align:left;font-size:.78em;'
        f'color:#666;font-weight:700;text-transform:uppercase;letter-spacing:.04em;">'
        f'{escape(p)}</th>'
        for p in PEOPLE
    )
    return (
        '<div style="overflow-x:auto;background:#fff;border:1px solid #e0e0d8;'
        'border-radius:10px;">'
        '<table style="width:100%;border-collapse:collapse;min-width:640px;">'
        '<thead><tr><th style="padding:8px 10px;font-size:.78em;color:#666;'
        'text-align:left;text-transform:uppercase;letter-spacing:.04em;">Day</th>'
        f'{headers}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table></div>'
    )


def _program_card_html(person: str, prog: dict) -> str:
    title    = escape(prog.get("title", "Untitled program"))
    body     = escape(prog.get("body", ""))
    saved_at = escape((prog.get("saved_at", "") or "").replace("T", " ")[:16])
    pid      = escape(prog.get("id", ""))
    return (
        f'<div style="background:#fff;border:1px solid #d8e8de;border-radius:10px;'
        f'padding:14px 16px;margin-bottom:10px;">'
        f'  <div style="display:flex;align-items:baseline;justify-content:space-between;'
        f'gap:10px;margin-bottom:6px;">'
        f'    <div style="font-weight:700;color:{ACCENT};font-size:.98em;">{title}</div>'
        f'    <div style="font-size:.7em;color:#999;white-space:nowrap;">{saved_at}</div>'
        f'  </div>'
        f'  <pre style="white-space:pre-wrap;font-family:inherit;font-size:.85em;'
        f'line-height:1.55;color:#222;margin:0 0 8px;">{body}</pre>'
        f'  <form method="POST" action="/programs-delete" style="text-align:right;margin:0;" '
        f'onsubmit="return confirm(\'Delete this program?\');">'
        f'    <input type="hidden" name="person" value="{escape(person)}">'
        f'    <input type="hidden" name="id" value="{pid}">'
        f'    <button type="submit" style="background:none;border:none;color:#b91c1c;'
        f'font-size:.74em;cursor:pointer;font-family:inherit;padding:0;">Delete</button>'
        f'  </form>'
        f'</div>'
    )


def _person_section_html(person: str, programs: list) -> str:
    if programs:
        body = "".join(_program_card_html(person, p) for p in programs)
    else:
        body = (
            '<div style="padding:12px 14px;background:#f5f5f0;border-radius:10px;'
            'color:#888;font-size:.85em;font-style:italic;margin-bottom:10px;">'
            f"No saved programs for {escape(person)} yet. Ask Coach to write one."
            "</div>"
        )

    save_form = (
        f'<details style="margin-top:6px;">'
        f'  <summary style="cursor:pointer;font-size:.78em;color:#666;">+ Save a program manually</summary>'
        f'  <form method="POST" action="/programs-save" style="margin-top:8px;'
        f'background:#f9faf7;border:1px solid #e4ecde;border-radius:10px;padding:12px;">'
        f'    <input type="hidden" name="person" value="{escape(person)}">'
        f'    <input name="title" placeholder="Title (e.g. April strength block)" required '
        f'style="width:100%;padding:8px 10px;border:1px solid #d4d8c8;border-radius:6px;'
        f'font-size:.85em;font-family:inherit;margin-bottom:8px;box-sizing:border-box;">'
        f'    <textarea name="body" rows="6" placeholder="Goals, weekly plan, progression notes…" required '
        f'style="width:100%;padding:8px 10px;border:1px solid #d4d8c8;border-radius:6px;'
        f'font-size:.85em;font-family:inherit;line-height:1.5;box-sizing:border-box;'
        f'resize:vertical;"></textarea>'
        f'    <button type="submit" style="margin-top:8px;background:{ACCENT};color:#fff;'
        f'border:none;border-radius:6px;padding:7px 16px;font-size:.85em;font-weight:600;'
        f'cursor:pointer;font-family:inherit;">Save</button>'
        f'  </form>'
        f'</details>'
    )

    return (
        f'<section id="person-{escape(person)}" style="margin-bottom:28px;scroll-margin-top:80px;">'
        f'  <h2 style="font-size:1.05em;color:{ACCENT};margin-bottom:10px;'
        f'border-bottom:1px solid #d8e8de;padding-bottom:6px;">{escape(person)}</h2>'
        f'  {body}'
        f'  {save_form}'
        f'</section>'
    )


def render_programs_page(focus: str = "", flash: str = "") -> str:
    programs_data = load_coach_programs() or {}

    flash_html = ""
    if flash:
        flash_html = (
            f'<div style="background:#dcfce7;border:1px solid #86efac;color:#166534;'
            f'border-radius:8px;padding:10px 14px;margin-bottom:14px;font-size:.88em;">'
            f'{escape(flash)}</div>'
        )

    sections = "".join(
        _person_section_html(p, programs_data.get(p, []))
        for p in PEOPLE
    )

    # Auto-scroll to focused person.
    # Whitelist against PEOPLE so a hostile ?focus= can't break out of the
    # JS string context (escape() is for HTML, not JavaScript).
    scroll_js = ""
    if focus and focus in PEOPLE:
        scroll_js = (
            "<script>"
            f"var el = document.getElementById('person-{focus}');"
            "if (el) el.scrollIntoView({behavior:'smooth', block:'start'});"
            "</script>"
        )

    body = f"""
    <div style="max-width:860px;margin:0 auto;padding:20px 16px 80px;">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;">
        <a href="/today" style="font-size:.82em;color:#888;text-decoration:none;">&larr; Today</a>
        <a href="/coach" style="font-size:.82em;color:{ACCENT};text-decoration:none;font-weight:600;">
          Ask Coach &rarr;
        </a>
      </div>

      <h1 style="font-size:1.4em;color:{ACCENT};margin-bottom:4px;">Coach's programs</h1>
      <div style="color:#777;font-size:.86em;margin-bottom:20px;">
        Long-form fitness plans Coach has written for the family, plus the weekly
        exercise schedule.
      </div>

      {flash_html}

      <h2 style="font-size:.95em;color:#444;margin:0 0 8px;text-transform:uppercase;
                 letter-spacing:.05em;">Weekly exercise schedule</h2>
      <div style="margin-bottom:32px;">
        {_weekly_grid_html()}
      </div>

      <h2 style="font-size:.95em;color:#444;margin:0 0 12px;text-transform:uppercase;
                 letter-spacing:.05em;">Saved programs</h2>
      {sections}
    </div>
    {scroll_js}
    """

    return html_page("Programs", body)
