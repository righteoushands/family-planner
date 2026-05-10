"""
render_programs.py — Coach's saved programs + the weekly exercise assignments,
all in one browseable page reachable from each person's POD card on /today.

Layout:
  - Top section: weekly exercise assignment grid (from exercise_assignments.json),
    one row per weekday × one column per person.
  - Per-person sections: each saved long-form program (title, body, saved date,
    status badge, view/edit/delete controls). Anchored so /programs#person-Joseph
    deep-links work.
  - Manual save form per person, in case Lauren wants to paste in something
    Coach wrote in chat.
  - Debug panel at the bottom: lists every program by id with the fields that
    feed into other surfaces (calendar/exercise grid), so duplicates and
    routing issues are easy to spot.

Coach also auto-saves into here via the <save_program> tag (see
render_coach.py system prompt + _apply_coach_program_saves in app.py).
"""
from html import escape
from datetime import datetime, date
from collections import Counter

from data_helpers import load_exercise_assignments, load_coach_programs
from ui_helpers import html_page
from config import COACH_PROGRAMS_FILE

EXERCISE_ASSIGNMENTS_PATH_DISPLAY = "data/exercise_assignments.json"

PEOPLE = ["Lauren", "JP", "Joseph", "Michael", "James"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

ACCENT = "#1a6e3e"

NEWLINE = "\n"


def _parse_saved_at(saved_at_raw):
    s = (saved_at_raw or "").strip()
    if not s:
        return None
    s = s.replace("T", " ")[:19]
    for fmt, length in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(s[:length], fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _status_for(saved_dt):
    if saved_dt is None:
        return ("Unknown", "#888", "#f3f4f6")
    age_days = (datetime.now() - saved_dt).days
    if age_days <= 30:
        return ("Active", "#166534", "#dcfce7")
    if age_days <= 90:
        return ("Aging", "#92400e", "#fef3c7")
    return ("Stale", "#991b1b", "#fee2e2")


def _norm_title(t):
    return " ".join((t or "").lower().split())


def _duplicate_title_set(programs):
    counts = Counter(_norm_title(p.get("title", "")) for p in (programs or []))
    return {t for t, n in counts.items() if n > 1 and t}


def _weekly_grid_html() -> str:
    """Render the per-day-per-person exercise assignment table."""
    assignments = load_exercise_assignments() or {}
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


def _program_card_html(person: str, prog: dict, dup_titles: set) -> str:
    title_raw = prog.get("title", "Untitled program")
    body_raw  = prog.get("body", "")
    saved_raw = prog.get("saved_at", "") or ""
    pid_raw   = prog.get("id", "")

    title    = escape(title_raw)
    body     = escape(body_raw)
    saved_dt = _parse_saved_at(saved_raw)
    saved_disp = escape(saved_raw.replace("T", " ")[:16] if saved_raw else "—")
    pid      = escape(pid_raw)

    status_label, status_fg, status_bg = _status_for(saved_dt)
    is_dup = _norm_title(title_raw) in dup_titles
    body_chars = len(body_raw)

    badge = (
        f'<span style="background:{status_bg};color:{status_fg};border-radius:999px;'
        f'padding:2px 9px;font-size:.68em;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.04em;">{status_label}</span>'
    )
    dup_badge = ""
    if is_dup:
        dup_badge = (
            '<span style="background:#fee2e2;color:#991b1b;border-radius:999px;'
            'padding:2px 9px;font-size:.68em;font-weight:700;text-transform:uppercase;'
            'letter-spacing:.04em;margin-left:6px;">Duplicate title</span>'
        )

    meta_row = (
        f'<div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;'
        f'font-size:.7em;color:#888;margin-bottom:8px;">'
        f'  <span><strong style="color:#555;">id</strong> <code>{pid}</code></span>'
        f'  <span>·</span>'
        f'  <span><strong style="color:#555;">created</strong> {saved_disp}</span>'
        f'  <span>·</span>'
        f'  <span><strong style="color:#555;">length</strong> {body_chars} chars</span>'
        f'  <span style="margin-left:auto;">{badge}{dup_badge}</span>'
        f'</div>'
    )

    edit_form = (
        f'<details style="margin-top:8px;">'
        f'  <summary style="cursor:pointer;font-size:.74em;color:#555;'
        f'display:inline-block;">Edit</summary>'
        f'  <form method="POST" action="/programs-edit" style="margin-top:8px;'
        f'background:#f9faf7;border:1px solid #e4ecde;border-radius:10px;padding:12px;">'
        f'    <input type="hidden" name="person" value="{escape(person)}">'
        f'    <input type="hidden" name="id" value="{pid}">'
        f'    <label style="display:block;font-size:.72em;color:#666;margin-bottom:4px;">Title</label>'
        f'    <input name="title" value="{title}" required '
        f'style="width:100%;padding:8px 10px;border:1px solid #d4d8c8;border-radius:6px;'
        f'font-size:.85em;font-family:inherit;margin-bottom:8px;box-sizing:border-box;">'
        f'    <label style="display:block;font-size:.72em;color:#666;margin-bottom:4px;">Body</label>'
        f'    <textarea name="body" rows="10" required '
        f'style="width:100%;padding:8px 10px;border:1px solid #d4d8c8;border-radius:6px;'
        f'font-size:.85em;font-family:inherit;line-height:1.5;box-sizing:border-box;'
        f'resize:vertical;">{body}</textarea>'
        f'    <div style="margin-top:8px;display:flex;gap:8px;">'
        f'      <button type="submit" style="background:{ACCENT};color:#fff;'
        f'border:none;border-radius:6px;padding:7px 16px;font-size:.85em;font-weight:600;'
        f'cursor:pointer;font-family:inherit;">Save changes</button>'
        f'    </div>'
        f'  </form>'
        f'</details>'
    )

    confirm_msg = "Delete this program?"
    delete_form = (
        f'<form method="POST" action="/programs-delete" style="display:inline;margin:0;" '
        f'onsubmit="return confirm({confirm_msg!r});">'
        f'  <input type="hidden" name="person" value="{escape(person)}">'
        f'  <input type="hidden" name="id" value="{pid}">'
        f'  <button type="submit" style="background:none;border:none;color:#b91c1c;'
        f'font-size:.74em;cursor:pointer;font-family:inherit;padding:0;">Delete</button>'
        f'</form>'
    )

    return (
        f'<div id="prog-{pid}" style="background:#fff;border:1px solid #d8e8de;'
        f'border-radius:10px;padding:14px 16px;margin-bottom:10px;scroll-margin-top:80px;">'
        f'  <div style="display:flex;align-items:baseline;justify-content:space-between;'
        f'gap:10px;margin-bottom:6px;">'
        f'    <div style="font-weight:700;color:{ACCENT};font-size:.98em;">{title}</div>'
        f'  </div>'
        f'  {meta_row}'
        f'  <pre style="white-space:pre-wrap;font-family:inherit;font-size:.85em;'
        f'line-height:1.55;color:#222;margin:0 0 8px;max-height:280px;overflow:auto;'
        f'background:#fafaf6;border:1px solid #eee;border-radius:6px;padding:10px;">{body}</pre>'
        f'  <div style="display:flex;gap:14px;align-items:center;">'
        f'    {edit_form}'
        f'    <span style="margin-left:auto;">{delete_form}</span>'
        f'  </div>'
        f'</div>'
    )


def _person_section_html(person: str, programs: list) -> str:
    progs = list(programs or [])
    dup_titles = _duplicate_title_set(progs)
    if progs:
        body = "".join(_program_card_html(person, p, dup_titles) for p in progs)
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

    count_label = f"{len(progs)} program{'s' if len(progs) != 1 else ''}"
    return (
        f'<section id="person-{escape(person)}" style="margin-bottom:28px;scroll-margin-top:80px;">'
        f'  <div style="display:flex;align-items:baseline;justify-content:space-between;'
        f'border-bottom:1px solid #d8e8de;padding-bottom:6px;margin-bottom:10px;">'
        f'    <h2 style="font-size:1.05em;color:{ACCENT};margin:0;">{escape(person)}</h2>'
        f'    <span style="font-size:.74em;color:#888;">{count_label}</span>'
        f'  </div>'
        f'  {body}'
        f'  {save_form}'
        f'</section>'
    )


def _debug_panel_html(programs_data: dict, assignments: dict) -> str:
    """
    Collapsible debug panel: lists every program by id with the fields that
    other surfaces (calendar / exercise grid / Coach prompt) read, so it's
    easy to spot duplicates and trace which record drives a given display.
    """
    rows = []
    for person in PEOPLE:
        bucket = programs_data.get(person, []) or []
        if not bucket:
            continue
        for p in bucket:
            pid_raw    = p.get("id", "")
            title_raw  = p.get("title", "")
            saved_raw  = p.get("saved_at", "")
            saved_dt   = _parse_saved_at(saved_raw)
            status_label, _fg, _bg = _status_for(saved_dt)
            body_chars = len(p.get("body", "") or "")
            dup_titles = _duplicate_title_set(bucket)
            is_dup     = _norm_title(title_raw) in dup_titles
            anchor     = f'/programs#prog-{escape(pid_raw)}'
            dup_cell   = '<span style="color:#b91c1c;font-weight:700;">YES</span>' if is_dup else '—'
            rows.append(
                f'<tr style="border-top:1px solid #eee;">'
                f'  <td style="padding:6px 8px;font-size:.78em;color:#444;">{escape(person)}</td>'
                f'  <td style="padding:6px 8px;font-size:.78em;"><code>{escape(pid_raw)}</code></td>'
                f'  <td style="padding:6px 8px;font-size:.78em;color:#222;">'
                f'<a href="{anchor}" style="color:{ACCENT};text-decoration:none;">'
                f'{escape((title_raw or "Untitled")[:80])}</a></td>'
                f'  <td style="padding:6px 8px;font-size:.78em;color:#666;white-space:nowrap;">'
                f'{escape(saved_raw[:16] if saved_raw else "—")}</td>'
                f'  <td style="padding:6px 8px;font-size:.78em;color:#666;">{status_label}</td>'
                f'  <td style="padding:6px 8px;font-size:.78em;color:#666;text-align:right;">{body_chars}</td>'
                f'  <td style="padding:6px 8px;font-size:.78em;text-align:center;">{dup_cell}</td>'
                f'</tr>'
            )

    if not rows:
        prog_table = (
            '<div style="padding:10px;color:#888;font-size:.82em;font-style:italic;">'
            "No programs to inspect."
            "</div>"
        )
    else:
        prog_table = (
            '<div style="overflow-x:auto;">'
            '<table style="width:100%;border-collapse:collapse;background:#fff;'
            'border:1px solid #e0e0d8;border-radius:8px;overflow:hidden;">'
            '<thead style="background:#f5f5f0;">'
            '<tr>'
            '  <th style="padding:8px;text-align:left;font-size:.72em;color:#555;'
            'text-transform:uppercase;letter-spacing:.04em;">Person</th>'
            '  <th style="padding:8px;text-align:left;font-size:.72em;color:#555;'
            'text-transform:uppercase;letter-spacing:.04em;">ID</th>'
            '  <th style="padding:8px;text-align:left;font-size:.72em;color:#555;'
            'text-transform:uppercase;letter-spacing:.04em;">Title</th>'
            '  <th style="padding:8px;text-align:left;font-size:.72em;color:#555;'
            'text-transform:uppercase;letter-spacing:.04em;">Saved</th>'
            '  <th style="padding:8px;text-align:left;font-size:.72em;color:#555;'
            'text-transform:uppercase;letter-spacing:.04em;">Status</th>'
            '  <th style="padding:8px;text-align:right;font-size:.72em;color:#555;'
            'text-transform:uppercase;letter-spacing:.04em;">Chars</th>'
            '  <th style="padding:8px;text-align:center;font-size:.72em;color:#555;'
            'text-transform:uppercase;letter-spacing:.04em;">Dup?</th>'
            '</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            '</table></div>'
        )

    days_present = [d for d in WEEKDAYS if (assignments or {}).get(d)]
    grid_summary = (
        f'<div style="font-size:.82em;color:#444;line-height:1.6;">'
        f'  <strong>Source file:</strong> <code>{escape(EXERCISE_ASSIGNMENTS_PATH_DISPLAY)}</code><br>'
        f'  <strong>Days populated:</strong> {escape(", ".join(days_present) or "(none)")}<br>'
        f'  <strong>People rendered as columns:</strong> {escape(", ".join(PEOPLE))}'
        f'</div>'
    )

    total_progs = sum(len(programs_data.get(p, []) or []) for p in PEOPLE)
    note_lines = [
        "Programs storage and the calendar/grid display are separate stores.",
        "The weekly exercise grid above reads from EXERCISE_ASSIGNMENTS_FILE,",
        "not from saved programs. Saved programs feed Coach's chat context",
        "and this page only.",
        "If a program appears in the family calendar, it was placed there as",
        "an event (data/events.json) by the plan-importer or by hand — not",
        "by saving the program here.",
    ]
    note_html = "<br>".join(escape(line) for line in note_lines)

    return (
        f'<details style="margin-top:32px;background:#fafaf6;border:1px solid #e0e0d8;'
        f'border-radius:10px;padding:14px 16px;">'
        f'  <summary style="cursor:pointer;font-weight:700;color:#444;font-size:.92em;">'
        f'Debug — what each surface reads ({total_progs} program{"s" if total_progs != 1 else ""} total)</summary>'
        f'  <div style="margin-top:14px;">'
        f'    <div style="font-size:.82em;color:#666;margin-bottom:6px;">'
        f'      <strong>Programs source:</strong> <code>{escape(COACH_PROGRAMS_FILE)}</code>'
        f'    </div>'
        f'    {prog_table}'
        f'    <div style="margin-top:18px;font-size:.82em;color:#444;">'
        f'      <strong style="display:block;margin-bottom:4px;">Weekly exercise grid</strong>'
        f'      {grid_summary}'
        f'    </div>'
        f'    <div style="margin-top:18px;padding:10px 12px;background:#fff;border:1px dashed #d0d0c0;'
        f'border-radius:6px;font-size:.78em;color:#555;line-height:1.55;">{note_html}</div>'
        f'  </div>'
        f'</details>'
    )


def render_programs_page(focus: str = "", flash: str = "") -> str:
    programs_data = load_coach_programs() or {}
    assignments   = load_exercise_assignments() or {}

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

    person_nav_links = []
    for p in PEOPLE:
        n = len(programs_data.get(p, []) or [])
        person_nav_links.append(
            f'<a href="#person-{escape(p)}" style="color:{ACCENT};text-decoration:none;'
            f'font-size:.82em;font-weight:600;padding:4px 10px;background:#fff;'
            f'border:1px solid #d8e8de;border-radius:999px;">'
            f'{escape(p)} <span style="color:#999;font-weight:400;">({n})</span></a>'
        )
    person_nav = (
        '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:18px;">'
        + "".join(person_nav_links) +
        '</div>'
    )

    debug_html = _debug_panel_html(programs_data, assignments)

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
        <div style="display:flex;gap:14px;">
          <a href="/calendar" style="font-size:.82em;color:#888;text-decoration:none;">Calendar</a>
          <a href="/coach" style="font-size:.82em;color:{ACCENT};text-decoration:none;font-weight:600;">
            Ask Coach &rarr;
          </a>
        </div>
      </div>

      <h1 style="font-size:1.4em;color:{ACCENT};margin-bottom:4px;">Coach's programs</h1>
      <div style="color:#777;font-size:.86em;margin-bottom:20px;">
        Long-form fitness plans Coach has written for the family, plus the weekly
        exercise schedule. Use the badges below to spot stale or duplicate programs.
      </div>

      {flash_html}

      {person_nav}

      <h2 style="font-size:.95em;color:#444;margin:0 0 8px;text-transform:uppercase;
                 letter-spacing:.05em;">Weekly exercise schedule</h2>
      <div style="margin-bottom:32px;">
        {_weekly_grid_html()}
      </div>

      <h2 style="font-size:.95em;color:#444;margin:0 0 12px;text-transform:uppercase;
                 letter-spacing:.05em;">Saved programs</h2>
      {sections}

      {debug_html}
    </div>
    {scroll_js}
    """

    return html_page("Programs", body)
