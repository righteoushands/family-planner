import cgi
from datetime import date, timedelta
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from daily_schedule_engine import (
    CHILDREN,
    build_schedule_payload,
    generate_day_packet,
    generate_week_packet,
    set_task_done,
)
from notes_router import add_note, archive_note, load_notes, save_notes, route_note_text
from school_pdf_engine import (
    approve_school_preview,
    extract_pdf_text,
    load_school_preview,
    load_school_previews,
    load_school_weeks,
    parse_school_pdf_text,
    save_school_preview,
)
from safe_utils import ensure_file, safe_save_json, debug_log


import os
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8000))

MANUAL_TASKS_FILE = "data/manual_tasks.json"
CHORES_FILE = "data/chores.json"
MOM_NOTES_FILE = "data/mom_notes.json"
ROADMAP_FILE = "data/roadmap.json"
LITURGICAL_FILE = "data/liturgical.json"
FAMILY_SCHEDULE_FILE = "data/family_schedule.json"
CALENDAR_CONFIG_FILE = "data/calendar_config.json"
CALENDAR_CACHE_FILE  = "data/calendar_cache.json"
MONTHLY_PLANNER_FILE = "data/monthly_planner.json"
CALENDAR_RULES_FILE   = "data/calendar_rules.json"
SUBSCRIBED_CALS_FILE  = "data/subscribed_calendars.json"
VALID_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}
VALID_STATUSES = {"active", "done", "inactive"}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_ORDER = {day: index for index, day in enumerate(WEEKDAYS)}

ROADMAP_STATUSES = ["Someday", "Ready", "In Progress", "Done"]

# Everyone who can be assigned a task (Mom first, then children)
ASSIGNABLE_TO = ["Mom"] + list(CHILDREN)

# Each child's color for visual identification
CHILD_COLORS = {
    "JP":      {"bg": "#c0392b", "text": "#fff", "light": "#fdf0ef"},
    "Joseph":  {"bg": "#27ae60", "text": "#fff", "light": "#edfaf3"},
    "Michael": {"bg": "#e67e22", "text": "#fff", "light": "#fef6ed"},
    "James":   {"bg": "#2980b9", "text": "#fff", "light": "#eaf4fb"},
}

def child_color(child: str, key: str = "bg") -> str:
    return CHILD_COLORS.get(child, {}).get(key, "#888")



# -------------------------
# STUB HELPERS (removed systems)
# -------------------------

def list_snapshots() -> list:
    return []

def restore_snapshot(filename: str) -> tuple:
    return False, "Snapshot system not available"

def load_calendar_rules() -> dict:
    return ensure_file(CALENDAR_RULES_FILE, {"rules": {}})

def save_calendar_rules(data: dict):
    safe_save_json(CALENDAR_RULES_FILE, data)

# -------------------------
# DATE HELPERS
# -------------------------

def today_iso():
    return date.today().isoformat()


def tomorrow_iso():
    return (date.today() + timedelta(days=1)).isoformat()


def normalize_date_query(value: str) -> str:
    value = str(value or "").strip().lower()
    if value == "tomorrow":
        return tomorrow_iso()
    if value == "today":
        return today_iso()
    return str(value or "").strip()


# -------------------------
# DATA HELPERS
# -------------------------

def load_manual_tasks():
    data = ensure_file(MANUAL_TASKS_FILE, [])
    return data if isinstance(data, list) else []


def save_manual_tasks(tasks):
    safe_save_json(MANUAL_TASKS_FILE, tasks)


def active_manual_tasks():
    tasks = load_manual_tasks()
    return [
        t for t in tasks
        if isinstance(t, dict) and t.get("status", "active") == "active"
    ]


def load_chores_data():
    data = ensure_file(CHORES_FILE, {"boys": {}})
    return data if isinstance(data, dict) else {"boys": {}}


def save_chores_data(data):
    safe_save_json(CHORES_FILE, data)


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def clean_priority(value):
    value = str(value or "").strip().upper()
    if value in VALID_PRIORITIES:
        return value
    return "MEDIUM"


def clean_status(value):
    value = str(value or "").strip().lower()
    if value in VALID_STATUSES:
        return value
    return "active"


def clean_child(value):
    value = str(value or "").strip()
    if value in CHILDREN:
        return value
    return ""


def clean_text(value):
    return str(value or "").strip()


def clean_weekday(value):
    value = str(value or "").strip()
    if value in WEEKDAYS:
        return value
    return value


def lines_to_list(text: str):
    return [line.strip() for line in str(text).splitlines() if line.strip()]


def count_school_check_items(payload):
    total = 0
    for block in payload.get("school_blocks", []):
        total += len(block.get("items", []))
    return total


def is_math_subject(subject: str) -> bool:
    subject_upper = str(subject or "").upper()
    return "ALGEBRA" in subject_upper or subject_upper.startswith("MATH ")


def is_math_test_text(subject: str, assignment_text: str) -> bool:
    combined = f"{subject} {assignment_text}".upper()
    return "TEST" in combined or "QUARTERLY ASSESSMENT" in combined


def sort_school_days(parsed_days):
    return sorted(
        parsed_days,
        key=lambda day: (
            WEEKDAY_ORDER.get(str(day.get("weekday", "")).strip(), 999),
            str(day.get("day_label", "")).strip(),
        ),
    )


# -------------------------
# HTML BASE
# -------------------------

def html_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
/* ── Reset & base ── */
*, *::before, *::after {{ box-sizing: border-box; }}

body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 15px;
    line-height: 1.5;
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 16px 56px;
    background: #f5f0eb;
    color: #1a1a1a;
}}

/* ── Typography ── */
h1 {{ font-size: 2rem;   font-weight: 700; margin: 0 0 18px; color: #1a1a1a; }}
h2 {{ font-size: 1.35rem; font-weight: 600; margin: 0 0 12px; color: #2c2c2c; }}
h3 {{ font-size: 1.1rem;  font-weight: 600; margin: 0 0 8px;  color: #333; }}
h4 {{ font-size: 0.95rem; font-weight: 600; margin: 0 0 6px;  color: #444; }}

a {{ color: #7c4a2d; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

/* ── Navigation ── */
.nav-shell {{
    background: #fff;
    border-bottom: 1px solid #e8e0d8;
    margin: 0 -16px 24px;
    padding: 0 16px;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}}

.nav-primary {{
    display: flex;
    align-items: center;
    gap: 2px;
    height: 48px;
    flex-wrap: nowrap;
    overflow-x: auto;
}}

.nav-primary a {{
    white-space: nowrap;
    padding: 6px 12px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.88rem;
    color: #555;
    transition: background 0.15s;
}}

.nav-primary a:hover {{
    background: #f5f0eb;
    text-decoration: none;
}}

.nav-primary a.active {{
    background: #f5f0eb;
    color: #1a1a1a;
}}

.nav-divider {{
    width: 1px;
    height: 24px;
    background: #e0d8d0;
    margin: 0 6px;
    flex-shrink: 0;
}}

.nav-secondary {{
    display: flex;
    align-items: center;
    gap: 2px;
    height: 36px;
    border-top: 1px solid #f0ebe4;
    flex-wrap: nowrap;
    overflow-x: auto;
}}

.nav-secondary a {{
    white-space: nowrap;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.8rem;
    color: #777;
    font-weight: 500;
}}

.nav-secondary a:hover {{
    background: #f5f0eb;
    color: #333;
    text-decoration: none;
}}

/* Print dropdown */
.print-menu {{
    position: relative;
    display: inline-block;
}}

.print-menu-btn {{
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.8rem;
    color: #777;
    font-weight: 500;
    cursor: pointer;
    background: none;
    border: none;
    font-family: inherit;
}}

.print-menu-btn:hover {{
    background: #f5f0eb;
    color: #333;
}}

.print-dropdown {{
    display: none;
    position: absolute;
    top: 100%;
    right: 0;
    background: white;
    border: 1px solid #e0d8d0;
    border-radius: 10px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.12);
    min-width: 160px;
    z-index: 200;
    overflow: hidden;
}}

.print-dropdown a {{
    display: block;
    padding: 10px 16px;
    font-size: 0.85rem;
    color: #333;
    border-bottom: 1px solid #f5f0eb;
}}

.print-dropdown a:last-child {{ border-bottom: none; }}
.print-dropdown a:hover {{ background: #f5f0eb; text-decoration: none; }}
.print-menu:hover .print-dropdown {{ display: block; }}

/* Hamburger (mobile) */
.hamburger {{
    display: none;
    background: none;
    border: none;
    cursor: pointer;
    padding: 8px;
    margin-left: auto;
    color: #555;
    font-size: 1.3rem;
}}

/* ── Cards ── */
.card {{
    background: white;
    border: 1px solid #e4dbd2;
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05), 0 0 0 0 transparent;
    transition: box-shadow 0.2s;
}}

.card:hover {{
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}}

.card-tight {{ padding: 14px 18px; }}
.card-flat  {{ box-shadow: none; border-color: #eee; }}

/* ── Grid ── */
.grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 14px;
}}

/* ── Badges & tags ── */
.badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    background: #f0ebe4;
    border: 1px solid #dfd7ce;
    font-size: 0.82em;
    color: #555;
    font-weight: 500;
}}

.summary-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}}

/* ── Forms ── */
label {{
    display: block;
    margin-bottom: 4px;
    font-weight: 600;
    font-size: 0.88em;
    color: #444;
}}

input[type="text"],
input[type="number"],
input[type="date"],
input[type="file"],
select,
textarea {{
    width: 100%;
    max-width: 680px;
    margin-bottom: 14px;
    padding: 9px 12px;
    box-sizing: border-box;
    border: 1px solid #d7cec5;
    border-radius: 8px;
    background: white;
    font-size: 0.95em;
    font-family: inherit;
    color: #1a1a1a;
    transition: border-color 0.15s;
}}

input:focus, select:focus, textarea:focus {{
    outline: none;
    border-color: #8b5a3c;
    box-shadow: 0 0 0 3px rgba(139,90,60,0.1);
}}

button {{
    padding: 8px 16px;
    margin-right: 8px;
    border: none;
    border-radius: 8px;
    background: #8b5a3c;
    color: white;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.9em;
    font-family: inherit;
    transition: background 0.15s;
}}

button:hover {{ background: #7a4f35; }}
button.secondary {{ background: #75835f; }}
button.secondary:hover {{ background: #64724f; }}
button.ghost {{ background: #9a9a9a; }}
button.ghost:hover {{ background: #888; }}

/* ── Tasks ── */
.task {{ margin-bottom: 8px; }}
.task form {{ display: flex; align-items: flex-start; gap: 10px; }}
.task.done label {{ text-decoration: line-through; color: #999; }}
.task label {{ line-height: 1.4; font-weight: 400; font-size: 0.95em; }}

/* ── Misc ── */
.muted {{ color: #888; font-size: 0.92em; }}
.small {{ font-size: 0.85em; color: #888; }}

.page-header {{ margin-bottom: 16px; }}

.link-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
    margin-bottom: 8px;
}}

.link-button {{
    display: inline-block;
    background: #fff;
    border: 1px solid #d7cec5;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 0.85em;
    color: #555;
    font-weight: 500;
}}

.link-button:hover {{
    background: #f5f0eb;
    text-decoration: none;
}}

.two-col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}}

.section-stack > .card {{ margin-bottom: 12px; }}

.subject-card {{
    border-top: 1px solid #f0ebe4;
    padding-top: 12px;
    margin-top: 12px;
}}

.preview-edit-block {{
    border: 1px solid #eadfd4;
    border-radius: 10px;
    background: #fcfaf8;
    padding: 14px;
    margin-bottom: 10px;
}}

.block-toolbar {{
    display: grid;
    grid-template-columns: 140px 1fr;
    gap: 12px;
}}

.block-remove {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 4px;
}}

.success {{
    background: #eef7ee;
    border: 1px solid #c3e0c3;
    color: #2a5a2a;
    padding: 10px 14px;
    border-radius: 10px;
    margin-bottom: 14px;
    font-weight: 500;
}}

pre {{
    white-space: pre-wrap;
    background: #faf8f5;
    border: 1px solid #e7dfd6;
    border-radius: 10px;
    padding: 12px 14px;
    overflow-x: auto;
    font-size: 0.88em;
}}

/* ── Responsive ── */
@media (max-width: 700px) {{
    .two-col {{ grid-template-columns: 1fr; }}
    .block-toolbar {{ grid-template-columns: 1fr; }}
    h1 {{ font-size: 1.6rem; }}
    h2 {{ font-size: 1.2rem; }}

    .nav-secondary {{ display: none; }}
    .nav-secondary.open {{ display: flex; flex-direction: column; height: auto; padding: 8px 0; }}
    .hamburger {{ display: block; }}
    .nav-primary {{ overflow-x: auto; }}
}}

/* ── Print ── */
@media print {{
    .nav-shell, .no-print, button, form {{ display: none !important; }}
    body {{ background: white; padding: 0; max-width: none; }}
    .card {{ border: none; box-shadow: none; padding: 0; margin-bottom: 14px; }}
    pre {{ background: white; border: none; padding: 0; }}
}}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def top_nav():
    child_links = "".join(
        f'<a href="/schedule/{child}" style="color:{child_color(child, "bg")}; font-weight:700;">{child}</a>'
        for child in CHILDREN
    )
    return f"""
    <nav class="nav-shell no-print">

      <!-- Primary row -->
      <div class="nav-primary">
        <a href="/">🏠 Home</a>
        <div class="nav-divider"></div>
        <a href="/today">Today</a>
        <a href="/week">Week</a>
        <div class="nav-divider"></div>
        {child_links}
        <div class="nav-divider"></div>
        <a href="/mom">Mom</a>
        <a href="/liturgical">✝ Liturgy</a>
        <button class="hamburger" onclick="document.querySelector('.nav-secondary').classList.toggle('open')">☰</button>
      </div>

      <!-- Secondary row -->
      <div class="nav-secondary">
        <a href="/family-schedule">📅 Schedule</a>
        <a href="/planner">🗓 Planner</a>
        <a href="/calendar">📆 Calendar</a>
        <a href="/school">📚 School</a>
        <a href="/chores">🧹 Chores</a>
        <a href="/tasks">✅ Tasks</a>
        <a href="/notes">📝 Notes</a>
        <a href="/roadmap">🗺 Roadmap</a>
        <div class="nav-divider"></div>
        <div class="print-menu">
          <button class="print-menu-btn">🖨 Print ▾</button>
          <div class="print-dropdown">
            <a href="/print/day">Print Today</a>
            <a href="/print/day?date=tomorrow">Print Tomorrow</a>
            <a href="/print/week">Print Week</a>
          </div>
        </div>
      </div>

    </nav>
    """


def page_header(title: str) -> str:
    return f"{top_nav()}<h1>{escape(title)}</h1>"


def render_status_message(message: str):
    if not message:
        return ""
    return f"<div class='success'>{escape(message)}</div>"


# -------------------------
# FORM PARSING
# -------------------------

def parse_urlencoded_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode()
    return parse_qs(raw)


def parse_multipart_form(handler):
    form = cgi.FieldStorage(
        fp=handler.rfile,
        headers=handler.headers,
        environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": handler.headers.get("Content-Type", ""),
        },
    )
    return form


# -------------------------
# SCHEDULE UI HELPERS
# -------------------------

def render_task_list(child, iso, items):
    if not items:
        return "<p class='muted'>None.</p>"

    html = ""
    for item in items:
        checked = "checked" if item.get("done") else ""
        done_class = "done" if item.get("done") else ""

        html += f"""
        <div class="task {done_class}">
            <form method="POST" action="/toggle-task">
                <input type="hidden" name="task_id" value="{escape(item.get("task_id", ""))}">
                <input type="hidden" name="return_url" value="/schedule/{escape(child)}?date={escape(iso)}">
                <input type="hidden" name="new_value" value={"false" if item.get("done") else "true"}>
                <input type="checkbox" onchange="this.form.submit()" {checked}>
                <label>{escape(item.get("text", ""))}</label>
            </form>
        </div>
        """
    return html


def render_school_block(child, iso, block):
    subject = escape(block.get("subject", "") or "Untitled Subject")
    assignment_text = block.get("assignment_text", "")
    assignment_html = f"<pre>{escape(assignment_text)}</pre>" if assignment_text else ""

    math_note = ""
    if block.get("is_math_test"):
        math_note = "<p><strong>TEST — bring to Mom for review</strong></p>"
    elif block.get("is_math"):
        math_note = "<p>Do all Lesson Practice and only the problems from the Mixed Practice from the last four lessons.</p>"

    return f"""
    <div class="subject-card">
        <h4>{subject}</h4>
        {math_note}
        {assignment_html}
        {render_task_list(child, iso, block.get("items", []))}
    </div>
    """


CELEBRATION_MESSAGES = [
    "🎉 All done! Amazing work today!",
    "⭐ Everything checked off — you crushed it!",
    "🏆 Complete! Outstanding effort today!",
    "🌟 All finished! You're on a roll!",
    "✨ Done and done! Excellent work!",
    "🎊 List complete! Way to go!",
    "💪 All checked off! Fantastic job today!",
    "🥇 Everything done! You're a champion!",
]

def is_day_complete(payload: dict) -> bool:
    """True if every school, chore, and manual task item is checked done."""
    all_items = []
    for block in payload.get("school_blocks", []):
        all_items.extend(block.get("items", []))
    all_items.extend(payload.get("chore_items", []))
    all_items.extend(payload.get("manual_task_items", []))
    all_items.extend(payload.get("carryover_items", []))
    if not all_items:
        return False
    return all(item.get("done", False) for item in all_items)


def count_remaining(payload: dict) -> int:
    """Count unchecked items across school, chores, and manual tasks."""
    all_items = []
    for block in payload.get("school_blocks", []):
        all_items.extend(block.get("items", []))
    all_items.extend(payload.get("chore_items", []))
    all_items.extend(payload.get("manual_task_items", []))
    all_items.extend(payload.get("carryover_items", []))
    return sum(1 for item in all_items if not item.get("done", False))


def render_confetti_celebration(child: str, message: str) -> str:
    """Render a confetti animation + celebration banner in the child's color."""
    import hashlib
    c_bg = child_color(child, "bg")
    c_text = child_color(child, "text")
    # Pick a stable message based on child name so it doesn't flicker on reload
    idx = int(hashlib.md5(child.encode()).hexdigest(), 16) % len(CELEBRATION_MESSAGES)
    msg = CELEBRATION_MESSAGES[idx]
    return f"""
    <div id="celebration-{child}" style="
        background:{c_bg}; color:{c_text};
        border-radius:16px; padding:20px 24px;
        margin-bottom:18px; text-align:center;
        position:relative; overflow:hidden;
    ">
        <div style="font-size:2em; margin-bottom:6px;">{msg}</div>
        <div style="font-size:1em; opacity:0.85;">Keep it up, {escape(child)}!</div>
        <canvas id="confetti-{child}" style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;"></canvas>
    </div>
    <script>
    (function() {{
        var canvas = document.getElementById('confetti-{child}');
        var ctx = canvas.getContext('2d');
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
        var pieces = [];
        var colors = ['{c_bg}','#f9ca24','#f0932b','#6ab04c','#e056fd','#22a6b3','#ffffff'];
        for (var i = 0; i < 80; i++) {{
            pieces.push({{
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height - canvas.height,
                r: Math.random() * 6 + 3,
                d: Math.random() * 3 + 1,
                color: colors[Math.floor(Math.random() * colors.length)],
                tilt: Math.random() * 10 - 5,
                tiltAngle: 0,
                tiltSpeed: Math.random() * 0.1 + 0.05,
            }});
        }}
        var frame = 0;
        function draw() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            pieces.forEach(function(p) {{
                ctx.beginPath();
                ctx.lineWidth = p.r;
                ctx.strokeStyle = p.color;
                ctx.moveTo(p.x + p.tilt + p.r / 4, p.y);
                ctx.lineTo(p.x + p.tilt, p.y + p.tilt + p.r / 4);
                ctx.stroke();
            }});
            update();
        }}
        function update() {{
            pieces.forEach(function(p) {{
                p.tiltAngle += p.tiltSpeed;
                p.y += (Math.cos(frame / 10) + p.d);
                p.x += Math.sin(frame / 10) * 0.5;
                p.tilt = Math.sin(p.tiltAngle) * 12;
                if (p.y > canvas.height) {{
                    p.y = -10;
                    p.x = Math.random() * canvas.width;
                }}
            }});
            frame++;
        }}
        if (frame < 300) {{ setInterval(draw, 16); }}
    }})();
    </script>
    """


def render_child_schedule_card(child, target_date_str=""):
    normalized_date = normalize_date_query(target_date_str)
    packet = generate_day_packet(normalized_date)
    iso = packet["iso"]
    weekday = packet["weekday"]
    date_label = packet["date_label"]

    payload = build_schedule_payload(child, weekday, date_label, iso)

    school_html = "".join(
        render_school_block(child, iso, block)
        for block in payload["school_blocks"]
    )

    school_count = count_school_check_items(payload)
    chore_count = len(payload.get("chore_items", []))
    carry_count = len(payload.get("carryover_items", []))
    manual_count = len(payload.get("manual_task_items", []))

    c_bg = child_color(child, "bg")
    c_light = child_color(child, "light")
    complete = is_day_complete(payload)
    celebration_html = render_confetti_celebration(child, "") if complete else ""

    return f"""
    <div class="card" style="border-left: 5px solid {c_bg}; background:{c_light};">
        {celebration_html}
        <div class="page-header">
            <h2 style="color:{c_bg};">{escape(child)} — {escape(date_label)}</h2>
            <div class="summary-row">
                <span class="badge">Carryover: {carry_count}</span>
                <span class="badge">Manual: {manual_count}</span>
                <span class="badge">School checks: {school_count}</span>
                <span class="badge">Chores: {chore_count}</span>
            </div>

            <div class="link-row no-print">
                <a class="link-button" href="/print/day?date={escape(iso)}">Print This Day</a>
            </div>

            <div style="margin-top:8px;">
                {render_now_next_strip()}
            </div>

            <div style="margin-top:8px;">
                {render_calendar_today_strip(iso)}
            </div>
        </div>

        <div class="section-stack">
            <div class="card card-tight">
                <h3>Carryover</h3>
                {render_task_list(child, iso, payload["carryover_items"])}
            </div>

            <div class="card card-tight">
                <h3>Manual Tasks</h3>
                {render_task_list(child, iso, payload["manual_task_items"])}
            </div>

            <div class="card card-tight">
                <h3>School</h3>
                {school_html or "<p class='muted'>None.</p>"}
            </div>

            <div class="card card-tight">
                <h3>Chores</h3>
                {render_task_list(child, iso, payload["chore_items"])}
            </div>
        </div>
    </div>
    """


# -------------------------
# LITURGICAL CALENDAR ENGINE
# -------------------------

# Fixed feast days (month, day) -> (name, color, notes)
FIXED_FEASTS = {
    (1,  1):  ("Solemnity of Mary, Mother of God", "white", "Holy Day of Obligation"),
    (1,  6):  ("Epiphany of the Lord", "white", ""),
    (2,  2):  ("Presentation of the Lord", "white", "Candlemas"),
    (2, 14):  ("Valentine's Day", "", ""),
    (3, 17):  ("St. Patrick's Day", "green", ""),
    (3, 19):  ("St. Joseph, Spouse of the Blessed Virgin Mary", "white", "Solemnity"),
    (3, 25):  ("Annunciation of the Lord", "white", "Solemnity"),
    (4, 23):  ("St. George, Martyr", "red", ""),
    (5,  1):  ("St. Joseph the Worker", "white", ""),
    (5, 13):  ("Our Lady of Fatima", "white", ""),
    (5, 31):  ("Visitation of the Blessed Virgin Mary", "white", ""),
    (6, 13):  ("St. Anthony of Padua", "white", ""),
    (6, 24):  ("Birth of St. John the Baptist", "white", "Solemnity"),
    (6, 29):  ("Sts. Peter and Paul, Apostles", "red", "Solemnity"),
    (7, 22):  ("St. Mary Magdalene", "white", ""),
    (7, 25):  ("St. James, Apostle", "red", ""),
    (7, 26):  ("Sts. Joachim and Anne", "white", "Parents of the Virgin Mary"),
    (8,  6):  ("Transfiguration of the Lord", "white", "Feast"),
    (8, 10):  ("St. Lawrence, Deacon and Martyr", "red", ""),
    (8, 14):  ("St. Maximilian Kolbe", "red", ""),
    (8, 15):  ("Assumption of the Blessed Virgin Mary", "white", "Holy Day of Obligation"),
    (8, 22):  ("Queenship of the Blessed Virgin Mary", "white", ""),
    (8, 28):  ("St. Augustine of Hippo", "white", ""),
    (8, 29):  ("Passion of St. John the Baptist", "red", ""),
    (9,  8):  ("Birth of the Blessed Virgin Mary", "white", ""),
    (9, 14):  ("Exaltation of the Holy Cross", "red", "Feast"),
    (9, 15):  ("Our Lady of Sorrows", "white", ""),
    (9, 29):  ("Sts. Michael, Gabriel, and Raphael", "white", "Archangels"),
    (10,  2): ("Guardian Angels", "white", ""),
    (10,  4): ("St. Francis of Assisi", "white", ""),
    (10,  7): ("Our Lady of the Rosary", "white", ""),
    (10, 18): ("St. Luke, Evangelist", "red", ""),
    (10, 28): ("Sts. Simon and Jude, Apostles", "red", ""),
    (11,  1): ("All Saints Day", "white", "Holy Day of Obligation"),
    (11,  2): ("All Souls Day", "purple", "Day of Prayer for the Dead"),
    (11,  9): ("Dedication of the Lateran Basilica", "white", ""),
    (11, 11): ("St. Martin of Tours", "white", ""),
    (11, 21): ("Presentation of the Blessed Virgin Mary", "white", ""),
    (11, 22): ("St. Cecilia", "red", "Patron of Musicians"),
    (11, 30): ("St. Andrew, Apostle", "red", ""),
    (12,  6): ("St. Nicholas of Myra", "white", ""),
    (12,  8): ("Immaculate Conception", "white", "Holy Day of Obligation"),
    (12, 12): ("Our Lady of Guadalupe", "white", ""),
    (12, 13): ("St. Lucy", "red", ""),
    (12, 25): ("Christmas — Nativity of the Lord", "white", "Holy Day of Obligation"),
    (12, 26): ("St. Stephen, First Martyr", "red", ""),
    (12, 27): ("St. John, Apostle and Evangelist", "white", ""),
    (12, 28): ("Holy Innocents, Martyrs", "red", ""),
    (12, 29): ("St. Thomas Becket", "red", ""),
    (12, 31): ("St. Sylvester I, Pope", "white", ""),
}

SEASON_COLORS = {
    "Advent":        "#4a235a",
    "Christmas":     "#d4af37",
    "Ordinary Time": "#5d7a3e",
    "Lent":          "#6b3fa0",
    "Holy Week":     "#8b0000",
    "Easter":        "#d4af37",
}

SEASON_TEXT_COLORS = {
    "Advent":        "white",
    "Christmas":     "#222",
    "Ordinary Time": "white",
    "Lent":          "white",
    "Holy Week":     "white",
    "Easter":        "#222",
}


def _easter(year: int):
    """Computus algorithm — returns Easter Sunday date."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_moveable_feasts(year: int) -> dict:
    """Return dict of date -> (name, color, notes) for moveable feasts."""
    easter = _easter(year)
    feasts = {}

    def add(delta, name, color, notes=""):
        d = easter + timedelta(days=delta)
        feasts[d] = (name, color, notes)

    # Easter season
    add(-46, "Ash Wednesday", "purple", "Fast and abstinence")
    add(-7,  "Palm Sunday", "red", "Holy Week begins")
    add(-3,  "Holy Thursday", "white", "Mass of the Lord's Supper")
    add(-2,  "Good Friday", "red", "Fast and abstinence — no Mass")
    add(-1,  "Holy Saturday", "white", "Easter Vigil")
    add(0,   "Easter Sunday", "gold", "Solemnity of solemnities")
    add(1,   "Easter Monday", "white", "Octave of Easter")
    add(7,   "Divine Mercy Sunday", "white", "Second Sunday of Easter")
    add(39,  "Ascension of the Lord", "white", "Holy Day of Obligation")
    add(49,  "Pentecost Sunday", "red", "")
    add(56,  "Trinity Sunday", "white", "")
    add(60,  "Corpus Christi", "white", "Body and Blood of Christ")
    add(68,  "Sacred Heart of Jesus", "red", "")

    # Advent: 4 Sundays before Christmas
    christmas = date(year, 12, 25)
    days_to_sunday = (christmas.weekday() + 1) % 7
    advent_start = christmas - timedelta(days=days_to_sunday + 21)
    feasts[advent_start] = ("First Sunday of Advent", "purple", "Advent begins")

    return feasts


def get_liturgical_season(d: date) -> str:
    """Return the liturgical season name for a given date."""
    year = d.year
    easter = _easter(year)
    ash_wednesday = easter - timedelta(days=46)
    palm_sunday = easter - timedelta(days=7)
    pentecost = easter + timedelta(days=49)
    christmas = date(year, 12, 25)
    days_to_sunday = (christmas.weekday() + 1) % 7
    advent_start = christmas - timedelta(days=days_to_sunday + 21)

    # Previous year Christmas season
    prev_christmas = date(year - 1, 12, 25)
    prev_easter = _easter(year - 1)
    prev_pentecost = prev_easter + timedelta(days=49)
    prev_days_to_sunday = (prev_christmas.weekday() + 1) % 7
    prev_advent_start = prev_christmas - timedelta(days=prev_days_to_sunday + 21)
    baptism_of_lord = prev_christmas + timedelta(days=(7 - prev_christmas.weekday()) % 7 + 7)

    if d >= advent_start:
        return "Advent"
    if d >= pentecost:
        return "Ordinary Time"
    if d >= easter:
        return "Easter"
    if d >= palm_sunday:
        return "Holy Week"
    if d >= ash_wednesday:
        return "Lent"
    if d >= date(year, 1, 9):
        return "Ordinary Time"
    if d >= date(year, 1, 1):
        return "Christmas"
    return "Ordinary Time"


def is_fast_day(d: date) -> bool:
    """True on Ash Wednesday and Good Friday."""
    easter = _easter(d.year)
    return d == easter - timedelta(days=46) or d == easter - timedelta(days=2)


def is_abstinence_day(d: date) -> bool:
    """True on all Fridays of Lent and Good Friday."""
    easter = _easter(d.year)
    ash_wednesday = easter - timedelta(days=46)
    good_friday = easter - timedelta(days=2)
    in_lent = ash_wednesday <= d <= good_friday
    return d.weekday() == 4 and in_lent  # Friday


def get_day_info(d: date) -> dict:
    """Return full liturgical info for a date."""
    year = d.year
    moveable = get_moveable_feasts(year)
    key = (d.month, d.day)

    feast_name = ""
    feast_color = ""
    feast_notes = ""

    if d in moveable:
        feast_name, feast_color, feast_notes = moveable[d]
    elif key in FIXED_FEASTS:
        feast_name, feast_color, feast_notes = FIXED_FEASTS[key]

    # Load user overrides/additions
    custom = load_liturgical_custom()
    iso = d.isoformat()
    if iso in custom:
        entry = custom[iso]
        if entry.get("name"):
            feast_name = entry["name"]
        if entry.get("color"):
            feast_color = entry["color"]
        if entry.get("notes"):
            feast_notes = entry["notes"]

    season = get_liturgical_season(d)
    fasting = is_fast_day(d)
    abstinence = is_abstinence_day(d)

    observances = []
    if fasting:
        observances.append("Fast day")
    if abstinence:
        observances.append("Abstinence (no meat)")
    if feast_notes:
        observances.append(feast_notes)

    return {
        "date": iso,
        "weekday": d.strftime("%A"),
        "date_label": d.strftime("%B %d, %Y"),
        "season": season,
        "season_color": SEASON_COLORS.get(season, "#888"),
        "season_text_color": SEASON_TEXT_COLORS.get(season, "white"),
        "feast_name": feast_name,
        "feast_color": feast_color,
        "observances": observances,
        "is_fast": fasting,
        "is_abstinence": abstinence,
    }


# -------------------------
# LITURGICAL DATA STORAGE
# -------------------------

def load_liturgical_custom() -> dict:
    data = ensure_file(LITURGICAL_FILE, {})
    return data if isinstance(data, dict) else {}


def save_liturgical_custom(data: dict):
    safe_save_json(LITURGICAL_FILE, data)


# -------------------------
# LITURGICAL CONTENT DATA
# -------------------------

SEASON_PRAYERS = {
    "Advent": [
        "O Antiphons (Dec 17-23) — great for evening prayer",
        "Rorate Caeli — ancient Advent hymn",
        "Advent wreath prayers at dinner",
        "Daily Rosary intention: Come, Lord Jesus",
    ],
    "Christmas": [
        "Gloria in Excelsis Deo",
        "Angelus at noon",
        "Prayer before the nativity scene",
        "Te Deum — thanksgiving prayer",
    ],
    "Ordinary Time": [
        "Daily Rosary",
        "Angelus at noon",
        "Liturgy of the Hours — Morning and Evening Prayer",
        "Act of Consecration to the Sacred Heart",
    ],
    "Lent": [
        "Stations of the Cross (especially Fridays)",
        "Divine Mercy Chaplet at 3pm",
        "Examine of conscience each evening",
        "Miserere — Psalm 51",
    ],
    "Holy Week": [
        "Attend all Holy Week liturgies",
        "Tenebrae (if available locally)",
        "Veneration of the Cross on Good Friday",
        "Easter Vigil — the mother of all vigils",
    ],
    "Easter": [
        "Regina Caeli (replaces Angelus during Easter)",
        "Divine Mercy Novena (starts Good Friday)",
        "Alleluia — sing it as much as possible",
        "Rosary: Glorious Mysteries",
    ],
}

SEASON_ACTIVITIES = {
    "Advent": [
        "Make or set up the Advent wreath",
        "Jesse Tree — add a new ornament each day",
        "St. Nicholas Day preparations (Dec 5 evening)",
        "Read aloud from a Christmas book as a family",
        "Write letters to be read at Christmas",
    ],
    "Christmas": [
        "Visit the nativity scene at your parish",
        "Sing Christmas carols as a family",
        "Feast of the Holy Innocents — honor children",
        "Epiphany: chalk the door (20+C+M+B+26)",
        "Bake a King Cake for Epiphany",
    ],
    "Ordinary Time": [
        "Learn about this week's saint",
        "Work on a saint lapbook or notebook",
        "Read a saint biography aloud",
        "Nature study and journaling",
    ],
    "Lent": [
        "Choose a family Lenten sacrifice",
        "Rice bowl or almsgiving jar",
        "Make a paper chain — remove a link each day",
        "Attend Friday Stations of the Cross",
        "Holy Week basket preparations",
    ],
    "Holy Week": [
        "Palm Sunday: save palms for next Ash Wednesday",
        "Holy Thursday: visit seven churches",
        "Good Friday: fast, silence, no screens 12-3pm",
        "Holy Saturday: prepare Easter baskets for blessing",
        "Dye Easter eggs with natural dyes",
    ],
    "Easter": [
        "Easter basket blessing at the Vigil or Easter morning",
        "Paschal candle — keep it lit at meals",
        "Learn the Regina Caeli",
        "Make Paschal bread or Paska",
        "Ascension: fly a kite to represent Jesus ascending",
    ],
}

FEAST_ACTIVITIES = {
    "Ash Wednesday": ["Attend Mass and receive ashes", "Begin your Lenten sacrifices today", "Family Lenten commitment jar"],
    "St. Patrick's Day": ["Read about St. Patrick's life", "Make soda bread", "Learn the Breastplate of St. Patrick"],
    "St. Joseph, Spouse of the Blessed Virgin Mary": ["St. Joseph's Table — share food with the poor", "Honor fathers and father figures", "Make zeppole (traditional St. Joseph's Day pastry)"],
    "Annunciation of the Lord": ["Pray the Angelus", "Read Luke 1:26-38 together", "Make a paper lily for Mary"],
    "Easter Sunday": ["Easter basket blessing", "Easter egg hunt", "Special Easter meal as a family"],
    "Ascension of the Lord": ["Fly a kite", "Read Acts 1:1-11 together", "Make cloud cookies"],
    "Pentecost Sunday": ["Wear red", "Make a birthday cake for the Church", "Learn about the gifts of the Holy Spirit"],
    "Assumption of the Blessed Virgin Mary": ["Bring flowers to Mary's altar", "Make a flower crown", "Pray the Rosary as a family"],
    "All Saints Day": ["Make saint costumes", "Saint hunt — match clues to saints", "Holy card collection"],
    "All Souls Day": ["Visit a cemetery", "Pray for the souls of deceased family members", "Light a candle for each departed loved one"],
    "St. Nicholas of Myra": ["Put out shoes the night before", "Learn about St. Nicholas giving in secret", "Do a secret act of kindness"],
    "Immaculate Conception": ["Make a blue and white Mary crown", "Pray the Miraculous Medal novena prayer", "Special dessert — white and blue"],
    "Our Lady of Guadalupe": ["Make a rose centerpiece", "Read the story of Juan Diego", "Tamales or Mexican food for dinner"],
    "Christmas — Nativity of the Lord": ["Midnight Mass or Christmas morning Mass", "Place the Christ Child in the nativity", "Read Luke 2 before opening gifts"],
    "Corpus Christi": ["Attend procession if available", "Make a floral carpet or altar at home", "Pray before the Blessed Sacrament"],
    "Sacred Heart of Jesus": ["Enthrone the Sacred Heart image in your home", "First Friday Mass and Communion", "Act of Consecration to the Sacred Heart"],
    "Palm Sunday": ["Bring palms home and make crosses", "Read the Passion narrative together", "Begin Holy Week preparations"],
    "Holy Thursday": ["Wash each other's feet", "Visit the altar of repose", "Read John 13 together"],
    "Good Friday": ["Fast and abstain from meat", "Stations of the Cross", "Silence from noon to 3pm"],
}

VESTMENT_COLORS = {
    "white":  ("#ffffff", "#333"),
    "red":    ("#c0392b", "#fff"),
    "purple": ("#6b3fa0", "#fff"),
    "green":  ("#27ae60", "#fff"),
    "rose":   ("#e91e8c", "#fff"),
    "gold":   ("#d4af37", "#333"),
    "black":  ("#222222", "#fff"),
}

def get_vestment_color(info: dict) -> tuple:
    """Return (bg, text) hex colors for the day's vestment."""
    color_key = info.get("feast_color", "").lower()
    if not color_key:
        season = info.get("season", "")
        season_to_color = {
            "Advent": "purple",
            "Christmas": "white",
            "Ordinary Time": "green",
            "Lent": "purple",
            "Holy Week": "red",
            "Easter": "white",
        }
        color_key = season_to_color.get(season, "green")
    return VESTMENT_COLORS.get(color_key, ("#888", "#fff"))


# -------------------------
# LITURGICAL UI HELPERS
# -------------------------

def render_liturgical_day_card(d: date, compact=False) -> str:
    info = get_day_info(d)
    season = info["season"]
    feast_name = info["feast_name"]

    vest_bg, vest_text = get_vestment_color(info)
    color_banner = (
        f'<div style="background:{vest_bg}; color:{vest_text}; border-radius:10px; '
        f'padding:8px 14px; margin-bottom:10px; font-weight:bold; font-size:0.95em;">'
        f'{escape(season)}'
        f'{(" — " + escape(feast_name)) if feast_name else ""}'
        f'</div>'
    )

    observances_html = "".join(
        f"<span class='badge'>{escape(o)}</span> "
        for o in info["observances"]
    )

    info_date = info["date"]
    edit_link = f"<a class='link-button' href='/liturgical/edit?date={escape(info_date)}'>Add / Edit</a>"

    if compact:
        return f"""
        <div>
            {color_banner}
            <div class="summary-row">{observances_html}</div>
            <div class="link-row no-print">{edit_link}</div>
        </div>
        """

    # Prayers for the season
    prayers = SEASON_PRAYERS.get(season, [])
    prayers_html = "".join(f"<li>{escape(p)}</li>" for p in prayers)

    # Activities — feast-specific first, then season
    activities = FEAST_ACTIVITIES.get(feast_name, []) + SEASON_ACTIVITIES.get(season, [])
    activities_html = "".join(f"<li>{escape(a)}</li>" for a in activities[:6])

    # Family notes for this date
    custom = load_liturgical_custom()
    family_note = custom.get(info_date, {}).get("family_note", "")
    family_note_html = f"""
    <div class="card card-tight" style="margin-top:10px;">
        <h4>Family Notes</h4>
        <form method="POST" action="/liturgical-note">
            <input type="hidden" name="date" value="{escape(info_date)}">
            <textarea name="family_note" rows="3" placeholder="Record your family's traditions, observations, or memories for this day...">{escape(family_note)}</textarea>
            <button type="submit">Save Note</button>
        </form>
    </div>
    """ if not compact else ""

    # USCCB readings link — format: https://bible.usccb.org/bible/readings/MMDDYY.cfm
    readings_url = f"https://bible.usccb.org/bible/readings/{d.strftime('%m%d%y')}.cfm"
    readings_link = f"<a class='link-button' href='{readings_url}' target='_blank'>Mass Readings (USCCB) ↗</a>"

    return f"""
    <div class="card">
        <h3>{escape(info["weekday"])} — {escape(info["date_label"])}</h3>
        {color_banner}
        <div class="summary-row" style="margin-bottom:10px;">{observances_html}</div>

        <div class="link-row no-print">
            {readings_link}
            {edit_link}
        </div>

        {"<h4>Prayers &amp; Devotions</h4><ul>" + prayers_html + "</ul>" if prayers_html else ""}
        {"<h4>Family Activities</h4><ul>" + activities_html + "</ul>" if activities_html else ""}

        {family_note_html}
    </div>
    """


# -------------------------
# LITURGICAL PAGE
# -------------------------

def render_liturgical_page(status_message=""):
    today = date.today()
    today_card = render_liturgical_day_card(today)

    # Week view — next 6 days compact
    week_html = ""
    for offset in range(1, 7):
        d = today + timedelta(days=offset)
        info = get_day_info(d)
        vest_bg, vest_text = get_vestment_color(info)
        color_dot = f'<span style="background:{vest_bg};color:{vest_text};border-radius:6px;padding:2px 8px;font-size:0.8em;font-weight:bold;">{escape(info["season"])}</span>'
        feast = f" — {escape(info['feast_name'])}" if info["feast_name"] else ""
        obs = "".join(f"<span class='badge'>{escape(o)}</span> " for o in info["observances"])
        info_d = info["date"]
        week_html += f"""
        <div class="card card-tight">
            <strong>{escape(info["weekday"])}, {escape(info["date_label"])}</strong>
            {color_dot}{feast}
            <div class="summary-row" style="margin-top:4px;">{obs}</div>
            <div class="link-row" style="margin-top:4px;">
                <a class="link-button" href="/liturgical/edit?date={escape(info_d)}">Add / Edit</a>
            </div>
        </div>
        """

    # Upcoming major feasts in next 60 days
    upcoming = []
    for offset in range(1, 61):
        d = today + timedelta(days=offset)
        info = get_day_info(d)
        if info["feast_name"] or info["is_fast"] or info["is_abstinence"]:
            upcoming.append(info)

    upcoming_html = ""
    for info in upcoming[:12]:
        tags = "".join(f"<span class='badge'>{escape(o)}</span> " for o in info["observances"])
        vest_bg, vest_text = get_vestment_color(info)
        dot = f'<span style="background:{vest_bg};color:{vest_text};border-radius:4px;padding:1px 6px;font-size:0.78em;margin-left:6px;">{escape(info["season"])}</span>'
        upcoming_html += f"""
        <div class="card card-tight">
            <strong>{escape(info["date_label"])}</strong>{dot} — {escape(info["feast_name"] or "Observance")}
            <div class="summary-row" style="margin-top:4px;">{tags}</div>
        </div>
        """

    body = f"""
    {page_header("Liturgical Calendar")}
    {render_status_message(status_message)}

    <div class="two-col">
        <div>
            <h2>Today</h2>
            {today_card}

            <h2>This Week</h2>
            {week_html}
        </div>

        <div>
            <h2>Upcoming (next 60 days)</h2>
            {upcoming_html or "<div class='card'><p class='muted'>No major feasts upcoming.</p></div>"}

            <div class="card">
                <h2>Add or Override a Day</h2>
                <p class="small">Add a custom feast, note, or override for any date.</p>
                <form method="POST" action="/liturgical-save">
                    <label>Date</label>
                    <input type="date" name="date" value="{today.isoformat()}">

                    <label>Feast / Saint name</label>
                    <input type="text" name="name" placeholder="e.g. St. Therese of Lisieux">

                    <label>Notes</label>
                    <input type="text" name="notes" placeholder="e.g. Family feast day, special prayer">

                    <label>Vestment color (optional)</label>
                    <select name="color">
                        <option value="">— auto —</option>
                        <option value="white">White</option>
                        <option value="red">Red</option>
                        <option value="purple">Purple / Violet</option>
                        <option value="green">Green</option>
                        <option value="rose">Rose</option>
                        <option value="gold">Gold</option>
                        <option value="black">Black</option>
                    </select>

                    <button type="submit">Save</button>
                </form>
            </div>
        </div>
    </div>
    """
    return html_page("Liturgical Calendar", body)


def render_liturgical_edit_page(date_str: str, status_message=""):
    try:
        d = date.fromisoformat(date_str)
    except Exception:
        d = date.today()

    info = get_day_info(d)
    custom = load_liturgical_custom()
    existing = custom.get(d.isoformat(), {})
    d_iso = d.isoformat()

    color_options = "".join(
        f'<option value="{c}" {"selected" if existing.get("color") == c else ""}>{c.capitalize()}</option>'
        for c in ["white", "red", "purple", "green", "rose", "gold", "black"]
    )

    delete_btn = (
        f"<form method='POST' action='/liturgical-delete'>"
        f"<input type='hidden' name='date' value='{escape(d_iso)}'>"
        f"<button type='submit' class='ghost'>Remove Custom Entry</button></form>"
        if existing else ""
    )

    body = f"""
    {page_header(f"Edit — {info['date_label']}")}
    {render_status_message(status_message)}

    <div class="card">
        <h2>Auto-detected info</h2>
        <p><strong>Season:</strong> {escape(info["season"])}</p>
        <p><strong>Feast:</strong> {escape(info["feast_name"] or "None")}</p>
        <p><strong>Observances:</strong> {escape(", ".join(info["observances"]) or "None")}</p>
    </div>

    <div class="card">
        <h2>Your Custom Entry</h2>
        <form method="POST" action="/liturgical-save">
            <input type="hidden" name="date" value="{escape(d_iso)}">

            <label>Feast / Saint name</label>
            <input type="text" name="name" value="{escape(existing.get("name", ""))}">

            <label>Notes</label>
            <input type="text" name="notes" value="{escape(existing.get("notes", ""))}">

            <label>Vestment color (optional)</label>
            <select name="color">
                <option value="">— auto —</option>
                {color_options}
            </select>

            <button type="submit">Save</button>
        </form>
        {delete_btn}
    </div>

    <div class="link-row">
        <a class="link-button" href="/liturgical">Back to Calendar</a>
    </div>
    """
    return html_page(f"Edit Liturgical — {info['date_label']}", body)


# -------------------------
# MONTHLY PLANNER
# -------------------------

MONTH_NAMES = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

def load_monthly_planner() -> dict:
    return ensure_file(MONTHLY_PLANNER_FILE, {})

def is_penance_season() -> bool:
    """True during Lent and Advent."""
    season = get_liturgical_season(date.today())
    return season in ("Lent", "Advent", "Holy Week")

def get_this_month_data() -> dict:
    """Return planner data for current month."""
    planner = load_monthly_planner()
    month_name = date.today().strftime("%B")
    month_data = planner.get("months", {}).get(month_name, {})
    every_month = planner.get("every_month", {})
    return {
        "month_name": month_name,
        "month_data": month_data,
        "every_month": every_month,
        "penance_chores": planner.get("penance_time_chores", []) if is_penance_season() else [],
        "litany": planner.get("litany_to_begin_again", []),
    }


def render_litany_block() -> str:
    """Collapsible Litany to Begin Again for the dashboard."""
    planner = load_monthly_planner()
    lines = planner.get("litany_to_begin_again", [])
    if not lines:
        return ""

    lines_html = "".join(
        f"<div style='margin:3px 0;font-size:0.92em;color:#444;'>{escape(line)}</div>"
        for line in lines
    )

    return f"""
    <div class="card" style="border-left:4px solid #7c4a2d; background:#fdfaf7;">
        <details>
            <summary style="cursor:pointer;font-weight:600;color:#7c4a2d;
                            font-size:0.95em;list-style:none;display:flex;
                            align-items:center;gap:8px;">
                <span>✝</span>
                <span>Litany to Begin Again</span>
                <span style="margin-left:auto;font-size:0.8em;color:#aaa;">tap to open</span>
            </summary>
            <div style="margin-top:12px;padding-top:10px;border-top:1px solid #f0e8e0;">
                <p style="font-size:0.8em;color:#aaa;margin-bottom:8px;font-style:italic;">
                    Compiled from the words of Venerable Bruno Lanteri, OMV
                </p>
                {lines_html}
            </div>
        </details>
    </div>
    """


def render_month_summary_card() -> str:
    """Compact this-month card for dashboard and Mom page."""
    data = get_this_month_data()
    month_name = data["month_name"]
    month_data = data["month_data"]
    every_month = data["every_month"]

    task_count = len(month_data.get("tasks", [])) + len(every_month.get("tasks", []))
    garden_count = len(month_data.get("garden", []))
    penance_count = len(data["penance_chores"])
    antiphon = month_data.get("marian_antiphon", "")
    von_trapp = month_data.get("von_trapp", "")

    antiphon_html = f"<p class='small' style='margin-top:6px;'>🎵 {escape(antiphon)}</p>" if antiphon else ""
    von_trapp_html = f"<p class='small'>📖 Von Trapp: {escape(von_trapp)}</p>" if von_trapp else ""
    penance_html = f"<span class='badge' style='background:#f0e8f5;'>Penance chores: {penance_count}</span>" if penance_count else ""

    return f"""
    <div class="card" style="border-left:4px solid #8b5a3c;">
        <h3>🗓 {escape(month_name)}</h3>
        <div class="summary-row">
            <span class="badge">Tasks: {task_count}</span>
            <span class="badge">Garden: {garden_count}</span>
            {penance_html}
        </div>
        {antiphon_html}
        {von_trapp_html}
        <div class="link-row">
            <a class="link-button" href="/planner">Open Planner</a>
        </div>
    </div>
    """


def render_planner_page(status_message="") -> str:
    data = get_this_month_data()
    month_name = data["month_name"]
    month_data = data["month_data"]
    every_month = data["every_month"]
    penance_chores = data["penance_chores"]

    antiphon = month_data.get("marian_antiphon", "")
    von_trapp = month_data.get("von_trapp", "")
    lit_notes = month_data.get("liturgical_notes", "")

    # Monthly tasks (this month + every month)
    all_tasks = every_month.get("tasks", []) + month_data.get("tasks", [])

    tasks_html = ""
    for task in all_tasks:
        tasks_html += f"""
        <div style="display:flex;align-items:flex-start;justify-content:space-between;
                    gap:12px;padding:8px 0;border-bottom:1px solid #f5f0eb;">
            <span style="font-size:0.95em;">{escape(task)}</span>
            <form method="POST" action="/planner-add-task" style="flex-shrink:0;">
                <input type="hidden" name="text" value="{escape(task)}">
                <button type="submit" style="padding:4px 10px;font-size:0.8em;
                        background:#f0ebe4;color:#7c4a2d;border:1px solid #d7cec5;
                        border-radius:6px;cursor:pointer;font-weight:600;">
                    + Add to Tasks
                </button>
            </form>
        </div>
        """

    # Garden tasks
    garden_tasks = month_data.get("garden", [])
    garden_html = ""
    for task in garden_tasks:
        garden_html += f"""
        <div style="display:flex;align-items:flex-start;justify-content:space-between;
                    gap:12px;padding:8px 0;border-bottom:1px solid #f5f0eb;">
            <span style="font-size:0.95em;">🌱 {escape(task)}</span>
            <form method="POST" action="/planner-add-task" style="flex-shrink:0;">
                <input type="hidden" name="text" value="{escape(task)}">
                <button type="submit" style="padding:4px 10px;font-size:0.8em;
                        background:#f0ebe4;color:#7c4a2d;border:1px solid #d7cec5;
                        border-radius:6px;cursor:pointer;font-weight:600;">
                    + Add to Tasks
                </button>
            </form>
        </div>
        """

    # Penance time chores
    penance_html = ""
    if penance_chores:
        for chore in penance_chores:
            penance_html += f"""
            <div style="display:flex;align-items:flex-start;justify-content:space-between;
                        gap:12px;padding:8px 0;border-bottom:1px solid #f5f0eb;">
                <span style="font-size:0.95em;">✝ {escape(chore)}</span>
                <form method="POST" action="/planner-add-task" style="flex-shrink:0;">
                    <input type="hidden" name="text" value="{escape(chore)}">
                    <button type="submit" style="padding:4px 10px;font-size:0.8em;
                            background:#f0ebe4;color:#7c4a2d;border:1px solid #d7cec5;
                            border-radius:6px;cursor:pointer;font-weight:600;">
                        + Add to Tasks
                    </button>
                </form>
            </div>
            """

    # External links
    links_html = ""
    for link in every_month.get("links", []):
        name = escape(link.get("name", ""))
        url = link.get("url", "")
        if url:
            links_html += f"<div style='margin-bottom:6px;'><a href='{escape(url)}' target='_blank' class='link-button'>{name} ↗</a></div>"
        else:
            links_html += f"<div style='margin-bottom:6px;color:#888;font-size:0.9em;'>{name}</div>"

    # Liturgical section
    liturgical_html = ""
    if antiphon:
        liturgical_html += f"<p><strong>🎵 Marian Antiphon:</strong> {escape(antiphon)}</p>"
    if von_trapp:
        vt = escape(von_trapp)
        liturgical_html += f"<p><strong>📖 Von Trapp:</strong> Listen to \"{vt}\" in Around the Year</p>"
    if lit_notes:
        liturgical_html += f"<p class='small'>{escape(lit_notes)}</p>"

    # Month selector
    month_links = " · ".join(
        f"<a href='/planner?month={m}'>{m[:3]}</a>" for m in MONTH_NAMES
    )

    body = f"""
    {page_header(f"Monthly Planner — {month_name}")}
    {render_status_message(status_message)}

    <p class="small" style="margin-bottom:16px;">{month_links}</p>

    <div class="two-col">
        <div>
            {"<div class='card' style='border-left:4px solid #6b3fa0;'><h3>✝ Liturgical Living</h3>" + liturgical_html + "</div>" if liturgical_html else ""}

            <div class="card">
                <h3>This Month's Reminders</h3>
                <p class="small" style="margin-bottom:10px;">
                    Click "+ Add to Tasks" to send any item to your task list.
                </p>
                {tasks_html or "<p class='muted'>No tasks for this month.</p>"}
            </div>

            {f'<div class="card" style="border-left:4px solid #6b3fa0;"><h3>✝ Penance Time Chores</h3><p class="small">These appear during Lent and Advent.</p>' + penance_html + "</div>" if penance_html else ""}
        </div>

        <div>
            {f'<div class="card" style="border-left:4px solid #27ae60;"><h3>🌱 Garden</h3>' + garden_html + "</div>" if garden_html else ""}

            <div class="card">
                <h3>📋 Monthly Links to Check</h3>
                {links_html}
            </div>
        </div>
    </div>
    """

    return html_page(f"Planner — {month_name}", body)


# -------------------------
# APPLE CALENDAR (CalDAV)
# -------------------------

def load_calendar_config() -> dict:
    return ensure_file(CALENDAR_CONFIG_FILE, {})

def save_calendar_config(cfg: dict):
    safe_save_json(CALENDAR_CONFIG_FILE, cfg)

def load_calendar_cache() -> dict:
    return ensure_file(CALENDAR_CACHE_FILE, {"events": [], "fetched_at": ""})

def save_calendar_cache(data: dict):
    safe_save_json(CALENDAR_CACHE_FILE, data)


def fetch_caldav_events(apple_id: str, app_password: str, days_ahead: int = 14) -> list:
    """
    Fetch events from iCloud CalDAV.
    Returns list of event dicts: {title, start, end, all_day, calendar, location, notes}
    """
    try:
        import urllib.request, urllib.error, base64, re
        from datetime import datetime, timezone

        # iCloud CalDAV base URL
        base_url = f"https://caldav.icloud.com"

        # Auth header
        credentials = base64.b64encode(f"{apple_id}:{app_password}".encode()).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/xml; charset=utf-8",
            "Depth": "1",
        }

        # Date range for query
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        def fmt_ical(d):
            return d.strftime("%Y%m%dT000000Z")

        # REPORT query to find events in range
        report_body = f"""<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop>
    <D:getetag/>
    <C:calendar-data/>
  </D:prop>
  <C:filter>
    <C:comp-filter name="VCALENDAR">
      <C:comp-filter name="VEVENT">
        <C:time-range start="{fmt_ical(today)}" end="{fmt_ical(end_date)}"/>
      </C:comp-filter>
    </C:comp-filter>
  </C:filter>
</C:calendar-query>""".encode()

        # First discover the principal URL
        disc_req = urllib.request.Request(
            f"{base_url}/",
            data=b'<?xml version="1.0"?><D:propfind xmlns:D="DAV:"><D:prop><D:current-user-principal/></D:prop></D:propfind>',
            headers={**headers, "Content-Type": "application/xml", "Depth": "0"},
            method="PROPFIND"
        )
        with urllib.request.urlopen(disc_req, timeout=10) as resp:
            principal_xml = resp.read().decode()

        # Extract principal href
        principal_match = re.search(r"<D:href>(/[^<]+)</D:href>", principal_xml)
        if not principal_match:
            return []
        principal_path = principal_match.group(1)

        # Get calendar home
        home_req = urllib.request.Request(
            f"{base_url}{principal_path}",
            data=b'<?xml version="1.0"?><D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"><D:prop><C:calendar-home-set/></D:prop></D:propfind>',
            headers={**headers, "Content-Type": "application/xml", "Depth": "0"},
            method="PROPFIND"
        )
        with urllib.request.urlopen(home_req, timeout=10) as resp:
            home_xml = resp.read().decode()

        home_match = re.search(r"calendar-home-set.*?<D:href>(/[^<]+)</D:href>", home_xml, re.DOTALL)
        if not home_match:
            return []
        home_path = home_match.group(1)

        # List calendars
        cal_req = urllib.request.Request(
            f"{base_url}{home_path}",
            data=b'<?xml version="1.0"?><D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"><D:prop><D:displayname/><C:supported-calendar-component-set/></D:prop></D:propfind>',
            headers={**headers, "Content-Type": "application/xml", "Depth": "1"},
            method="PROPFIND"
        )
        with urllib.request.urlopen(cal_req, timeout=10) as resp:
            cal_xml = resp.read().decode()

        # Extract calendar paths
        cal_paths = re.findall(r"<D:href>(/[^<]*calendar[^<]*)</D:href>", cal_xml)
        if not cal_paths:
            cal_paths = re.findall(r"<D:href>(/[^<]+/)</D:href>", cal_xml)

        # Fetch events from each calendar
        all_events = []
        for cal_path in set(cal_paths):
            try:
                ev_req = urllib.request.Request(
                    f"{base_url}{cal_path}",
                    data=report_body,
                    headers=headers,
                    method="REPORT"
                )
                with urllib.request.urlopen(ev_req, timeout=10) as resp:
                    ev_xml = resp.read().decode()

                # Parse VCALENDAR/VEVENT blocks
                for vevent in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ev_xml, re.DOTALL):
                    def prop(name):
                        m = re.search(rf"{name}[^:]*:(.*?)\r?\n", vevent)
                        return m.group(1).strip() if m else ""

                    title    = prop("SUMMARY")
                    dtstart  = prop("DTSTART")
                    dtend    = prop("DTEND")
                    location = prop("LOCATION")
                    notes    = prop("DESCRIPTION")

                    # Parse date
                    all_day = False
                    start_iso = ""
                    end_iso   = ""
                    try:
                        if "T" in dtstart:
                            # datetime
                            dt_clean = re.sub(r"[TZ]", lambda m: " " if m.group()=="T" else "", dtstart).strip()
                            dt_clean = dt_clean[:15]
                            from datetime import datetime as _dt
                            parsed = _dt.strptime(dt_clean, "%Y%m%d %H%M%S")
                            start_iso = parsed.strftime("%Y-%m-%dT%H:%M")
                            if dtend and "T" in dtend:
                                dt2 = re.sub(r"[TZ]", lambda m: " " if m.group()=="T" else "", dtend).strip()[:15]
                                parsed2 = _dt.strptime(dt2, "%Y%m%d %H%M%S")
                                end_iso = parsed2.strftime("%Y-%m-%dT%H:%M")
                        else:
                            all_day = True
                            from datetime import datetime as _dt
                            parsed = _dt.strptime(dtstart[:8], "%Y%m%d")
                            start_iso = parsed.strftime("%Y-%m-%d")
                            end_iso = start_iso
                    except Exception:
                        continue

                    if title and start_iso:
                        all_events.append({
                            "title":    title,
                            "start":    start_iso,
                            "end":      end_iso,
                            "all_day":  all_day,
                            "location": location,
                            "notes":    notes,
                        })
            except Exception:
                continue

        # Sort by start
        all_events.sort(key=lambda e: e["start"])
        return all_events

    except Exception as e:
        debug_log("CalDAV fetch failed:", str(e))
        return []


def refresh_calendar(force: bool = False) -> list:
    """Return events from cache, refreshing if stale (>30 min) or forced."""
    from datetime import datetime as _dt
    cache = load_calendar_cache()
    fetched_at = cache.get("fetched_at", "")
    events = cache.get("events", [])

    stale = True
    if fetched_at and not force:
        try:
            last = _dt.fromisoformat(fetched_at)
            stale = (_dt.now() - last).total_seconds() > 1800  # 30 min
        except Exception:
            stale = True

    if stale:
        cfg = load_calendar_config()
        apple_id = cfg.get("apple_id", "")
        app_password = cfg.get("app_password", "")
        if apple_id and app_password:
            events = fetch_caldav_events(apple_id, app_password)
            save_calendar_cache({
                "events": events,
                "fetched_at": _dt.now().isoformat(),
            })

    return events


def events_for_date(events: list, iso: str) -> list:
    """Filter events to those occurring on a given date."""
    return [e for e in events if e["start"].startswith(iso) or
            (e["all_day"] and e["start"] <= iso <= (e["end"] or e["start"]))]


def render_event_pill(event: dict) -> str:
    """A single compact event pill."""
    title    = escape(event.get("title", ""))
    location = event.get("location", "")
    start    = event.get("start", "")
    all_day  = event.get("all_day", False)
    color    = event.get("color", "#4a90d9")
    cal_name = event.get("calendar", "")

    time_str = ""
    if not all_day and "T" in start:
        try:
            from datetime import datetime as _dt
            t = _dt.fromisoformat(start)
            time_str = t.strftime("%-I:%M %p")
        except Exception:
            time_str = ""

    loc_str  = f" · {escape(location)}" if location else ""
    time_html = f"<span style='color:#888;font-size:0.8em;margin-right:4px;'>{escape(time_str)}</span>" if time_str else ""
    cal_html  = f"<span style='font-size:0.75em;color:#aaa;margin-left:4px;'>{escape(cal_name)}</span>" if cal_name else ""

    return f"""
    <div style="display:flex;align-items:center;gap:6px;padding:5px 0;
                border-bottom:1px solid #f0ebe4;">
        <span style="width:8px;height:8px;border-radius:50%;
                     background:{color};flex-shrink:0;"></span>
        {time_html}
        <span style="font-size:0.9em;">{title}{loc_str}</span>
        {cal_html}
    </div>
    """


# -------------------------
# SUBSCRIBED CALENDARS (.ics feeds)
# -------------------------

def load_subscribed_calendars() -> list:
    data = ensure_file(SUBSCRIBED_CALS_FILE, [])
    return data if isinstance(data, list) else []

def save_subscribed_calendars(cals: list):
    safe_save_json(SUBSCRIBED_CALS_FILE, cals)

def fetch_ics_events(url: str, name: str, color: str = "#9b59b6") -> list:
    """Fetch and parse a .ics subscription URL. Returns list of event dicts."""
    try:
        import urllib.request, re
        from datetime import datetime as _dt

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "FamilyPlanner/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        events = []
        today = date.today()
        lookahead = today + timedelta(days=60)

        for vevent in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", raw, re.DOTALL):
            def prop(p):
                m = re.search(r"^" + re.escape(p) + r"[;:][^\r\n]+", vevent, re.MULTILINE)
                if not m:
                    return ""
                val = m.group(0).split(":", 1)[-1].strip()
                # Handle line folding
                val = re.sub(r"\r?\n[ \t]", "", val)
                return val

            summary  = prop("SUMMARY").replace("\\,", ",").replace("\\n", " ")
            dtstart  = prop("DTSTART")
            dtend    = prop("DTEND")
            location = prop("LOCATION").replace("\\,", ",")
            desc     = prop("DESCRIPTION").replace("\\n", " ").replace("\\,", ",")

            if not summary or not dtstart:
                continue

            # Parse start date/time
            all_day = False
            start_iso = ""
            end_iso = ""
            try:
                clean = re.sub(r"[TZ]", lambda m: " " if m.group() == "T" else "", dtstart).strip()
                if len(clean) >= 15:
                    parsed = _dt.strptime(clean[:15], "%Y%m%d %H%M%S")
                    start_iso = parsed.strftime("%Y-%m-%dT%H:%M")
                else:
                    all_day = True
                    parsed = _dt.strptime(clean[:8], "%Y%m%d")
                    start_iso = parsed.strftime("%Y-%m-%d")
                    end_iso = start_iso

                # Filter to relevant date range
                event_date = parsed.date() if hasattr(parsed, "date") else parsed
                if not (today <= event_date <= lookahead):
                    continue

                if dtend and not all_day:
                    clean2 = re.sub(r"[TZ]", lambda m: " " if m.group() == "T" else "", dtend).strip()
                    if len(clean2) >= 15:
                        parsed2 = _dt.strptime(clean2[:15], "%Y%m%d %H%M%S")
                        end_iso = parsed2.strftime("%Y-%m-%dT%H:%M")

            except Exception:
                continue

            events.append({
                "title":    summary,
                "start":    start_iso,
                "end":      end_iso,
                "all_day":  all_day,
                "location": location,
                "notes":    desc[:200] if desc else "",
                "calendar": name,
                "color":    color,
                "source":   "subscribed",
            })

        events.sort(key=lambda e: e["start"])
        return events

    except Exception as e:
        debug_log(f"ICS fetch failed for {name}:", str(e))
        return []


def refresh_subscribed_calendars() -> list:
    """Fetch all subscribed .ics calendars and return merged event list."""
    cals = load_subscribed_calendars()
    all_events = []
    for cal in cals:
        if not cal.get("url") or not cal.get("enabled", True):
            continue
        events = fetch_ics_events(
            cal["url"],
            cal.get("name", "Calendar"),
            cal.get("color", "#9b59b6"),
        )
        all_events.extend(events)
    all_events.sort(key=lambda e: e["start"])
    return all_events


def get_all_events(iso: str = "") -> list:
    """Merge iCloud + subscribed calendar events for a given date."""
    if not iso:
        iso = date.today().isoformat()
    ical_events = refresh_calendar()
    sub_events   = refresh_subscribed_calendars()
    all_events   = ical_events + sub_events
    all_events.sort(key=lambda e: e["start"])
    return events_for_date(all_events, iso)


def render_calendar_today_strip(iso: str = "") -> str:
    """Compact strip of today's events — merges iCloud + subscribed calendars."""
    if not iso:
        iso = date.today().isoformat()

    today_events = get_all_events(iso)
    cfg = load_calendar_config()
    subs = load_subscribed_calendars()

    if not cfg.get("apple_id") and not subs:
        return f"""
        <div style="color:#aaa;font-size:0.85em;padding:4px 0;">
            <a href="/calendar" style="color:#7c4a2d;">Set up calendars →</a>
        </div>
        """

    if not today_events:
        return "<p class='muted' style='font-size:0.88em;'>No events today.</p>"

    pills = "".join(render_event_pill(e) for e in today_events)
    return f"""
    <div>
        {pills}
        <div style="margin-top:6px;">
            <a class="link-button" href="/calendar" style="font-size:0.8em;">Full Calendar</a>
        </div>
    </div>
    """


# -------------------------
# CALENDAR PAGE
# -------------------------

def render_calendar_page(status_message="") -> str:
    cfg = load_calendar_config()
    apple_id = cfg.get("apple_id", "")
    app_password = cfg.get("app_password", "")
    cache = load_calendar_cache()
    fetched_at = cache.get("fetched_at", "")
    events = cache.get("events", [])

    # Settings card
    password_placeholder = "••••••••••••••••" if app_password else "xxxx-xxxx-xxxx-xxxx"
    connected_badge = f'<span style="background:#eef7ee;border:1px solid #c3e0c3;color:#2a5a2a;padding:3px 10px;border-radius:999px;font-size:0.82em;font-weight:600;">✓ Connected</span>' if apple_id else '<span style="background:#fef0f0;border:1px solid #f0c0c0;color:#a00;padding:3px 10px;border-radius:999px;font-size:0.82em;font-weight:600;">Not connected</span>'

    settings_html = f"""
    <div class="card">
        <h2>iCloud Calendar Setup {connected_badge}</h2>

        {"<p class='small' style='margin-bottom:10px;'><strong>Currently saved:</strong> " + escape(apple_id) + "</p>" if apple_id else ""}

        <p class="small" style="margin-bottom:12px;">
            To get an app-specific password: go to
            <a href="https://appleid.apple.com" target="_blank">appleid.apple.com</a>
            → Sign-In &amp; Security → App-Specific Passwords → click ＋ → name it
            "Family Planner" → copy the password shown (looks like <code>abcd-efgh-ijkl-mnop</code>).
        </p>

        <form method="POST" action="/calendar-save-config">
            <label>Apple ID (your iCloud email)</label>
            <input type="text" name="apple_id" value="{escape(apple_id)}"
                   placeholder="yourname@icloud.com" autocomplete="off">

            <label>App-Specific Password</label>
            <input type="text" name="app_password" value=""
                   placeholder="{password_placeholder}" autocomplete="off">
            <p class="small" style="margin-top:-10px;margin-bottom:12px;">
                {"Password saved. Leave blank to keep existing password." if app_password else "Paste your app-specific password here."}
            </p>

            <button type="submit">Save Credentials</button>
        </form>

        {f'<p class="small" style="margin-top:8px;color:#888;">Last synced: {escape(fetched_at[:16].replace("T"," "))}</p>' if fetched_at else ""}

        <form method="POST" action="/calendar-refresh" style="margin-top:8px;">
            <button type="submit" class="secondary">↻ Sync Now</button>
        </form>
    </div>
    """

    # Build subscribed calendars section early so it shows even with no iCloud events
    subs = load_subscribed_calendars()
    sub_rows = ""
    for i, cal in enumerate(subs):
        sub_rows += f"""
        <div style="display:flex;align-items:center;gap:10px;padding:8px 0;
                    border-bottom:1px solid #f5f0eb;">
            <span style="width:12px;height:12px;border-radius:50%;
                         background:{escape(cal.get("color","#9b59b6"))};flex-shrink:0;"></span>
            <div style="flex:1;">
                <strong style="font-size:0.9em;">{escape(cal.get("name",""))}</strong>
                <div style="font-size:0.78em;color:#aaa;word-break:break-all;">{escape(cal.get("url","")[:70])}</div>
            </div>
            <form method="POST" action="/subscribed-cal-delete">
                <input type="hidden" name="index" value="{i}">
                <button type="submit" class="ghost" style="padding:4px 8px;font-size:0.8em;">Remove</button>
            </form>
        </div>
        """

    COLOR_OPTIONS = [
        ("#9b59b6","Purple"),("#e74c3c","Red"),("#3498db","Blue"),
        ("#27ae60","Green"),("#e67e22","Orange"),("#1abc9c","Teal"),
        ("#e91e8c","Pink"),("#34495e","Dark"),
    ]
    color_opts = "".join(
        f'<option value="{c}">{n}</option>' for c, n in COLOR_OPTIONS
    )

    subscribed_html = f"""
    <div class="card">
        <h2>Subscribed Calendars</h2>
        <p class="small" style="margin-bottom:12px;">
            Paste any public .ics URL — school calendar, church, sports, or
            your Proton Calendar share link. No login required.
        </p>

        {sub_rows or "<p class='muted' style='margin-bottom:12px;'>No subscribed calendars yet.</p>"}

        <form method="POST" action="/subscribed-cal-add">
            <label>Calendar Name</label>
            <input type="text" name="name" placeholder="e.g. Proton Calendar, School Events">

            <label>ICS URL</label>
            <input type="text" name="url" placeholder="https://...">

            <label>Color</label>
            <select name="color">{color_opts}</select>

            <button type="submit">Add Calendar</button>
        </form>
    </div>
    """

    if not events:
        body = f"""
        {page_header("Calendar")}
        {render_status_message(status_message)}
        {settings_html}
        {subscribed_html}
        <div class="card card-flat">
            <p class="muted">No iCloud events loaded yet. Enter your credentials above and click ↻ Sync Now.</p>
        </div>
        """
        return html_page("Calendar", body)

    # Week view — merge iCloud + subscribed
    today = date.today()
    week_days = [today + timedelta(days=i) for i in range(7)]
    sub_events_all = refresh_subscribed_calendars()
    all_cal_events = events + sub_events_all
    all_cal_events.sort(key=lambda e: e["start"])

    week_html = ""
    for d in week_days:
        iso = d.isoformat()
        day_events = events_for_date(all_cal_events, iso)
        is_today = (d == today)
        header_style = "font-weight:700;color:#7c4a2d;" if is_today else "font-weight:600;"
        today_badge = " <span class='badge' style='background:#7c4a2d;color:white;font-size:0.75em;'>Today</span>" if is_today else ""

        events_html = "".join(render_event_pill(e) for e in day_events) if day_events else "<p class='muted' style='font-size:0.85em;'>No events.</p>"

        week_html += f"""
        <div class="card card-tight">
            <div style="{header_style}margin-bottom:8px;">
                {escape(d.strftime("%A, %B %d"))}{today_badge}
            </div>
            {events_html}
        </div>
        """

    # Upcoming 14 days
    upcoming_html = ""
    for e in all_cal_events[:20]:
        start = e.get("start","")
        try:
            from datetime import datetime as _dt
            if "T" in start:
                dt = _dt.fromisoformat(start)
                date_label = dt.strftime("%a %b %d · %-I:%M %p")
            else:
                dt = _dt.strptime(start[:10], "%Y-%m-%d")
                date_label = dt.strftime("%a %b %d · All day")
        except Exception:
            date_label = start

        location = f" · {escape(e['location'])}" if e.get("location") else ""
        upcoming_html += f"""
        <div class="card card-tight">
            <div style="font-size:0.82em;color:#888;margin-bottom:2px;">{escape(date_label)}</div>
            <div style="font-weight:600;">{escape(e.get("title",""))}{location}</div>
            {f'<div class="small">{escape(e["notes"][:120])}</div>' if e.get("notes") else ""}
        </div>
        """

    body = f"""
    {page_header("Calendar")}
    {render_status_message(status_message)}

    <div class="two-col">
        <div>
            <h2>This Week</h2>
            {week_html}
        </div>

        <div>
            <h2>Upcoming 14 Days</h2>
            {upcoming_html or "<div class='card'><p class='muted'>No upcoming events.</p></div>"}

            {settings_html}
            {subscribed_html}
        </div>
    </div>
    """
    return html_page("Calendar", body)


# -------------------------
# FAMILY SCHEDULE ENGINE
# -------------------------

SCHEDULE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

def load_family_schedule() -> dict:
    return ensure_file(FAMILY_SCHEDULE_FILE, {"times": [], "days": {}})

def save_family_schedule(data: dict):
    safe_save_json(FAMILY_SCHEDULE_FILE, data)

def get_current_slot(schedule: dict) -> tuple:
    """Return (current_slot_label, next_slot_label) based on time of day."""
    from datetime import datetime
    now = datetime.now()
    hour = now.hour
    minute = now.minute

    times = schedule.get("times", [])
    today_name = now.strftime("%A")
    today_slots = schedule.get("days", {}).get(today_name, {})

    def slot_hour(label: str) -> int:
        try:
            t = label.strip()
            h, rest = t.split(":")
            m_part, ampm = rest.split(" ")
            h = int(h)
            if ampm == "PM" and h != 12:
                h += 12
            if ampm == "AM" and h == 12:
                h = 0
            return h
        except Exception:
            return -1

    current_idx = -1
    for i, t in enumerate(times):
        sh = slot_hour(t)
        if sh <= hour:
            current_idx = i

    current_label = ""
    current_activity = ""
    next_label = ""
    next_activity = ""

    if current_idx >= 0:
        current_label = times[current_idx]
        current_activity = today_slots.get(current_label, "")
        if current_idx + 1 < len(times):
            next_label = times[current_idx + 1]
            next_activity = today_slots.get(next_label, "")

    return current_label, current_activity, next_label, next_activity


def render_now_next_strip() -> str:
    """Compact 'Now / Next' strip for dashboard and Mom page."""
    from datetime import datetime
    schedule = load_family_schedule()
    cur_label, cur_activity, next_label, next_activity = get_current_slot(schedule)

    if not cur_label and not next_label:
        return ""

    now_html = f"""
    <div style="display:flex; gap:16px; flex-wrap:wrap; align-items:stretch;">
        <div style="flex:1; min-width:180px; background:#fff7ed; border:1px solid #f0d9c0;
                    border-left:5px solid #e67e22; border-radius:10px; padding:12px 14px;">
            <div style="font-size:0.78em; font-weight:bold; color:#e67e22;
                        text-transform:uppercase; letter-spacing:1px; margin-bottom:4px;">
                Now · {escape(cur_label)}
            </div>
            <div style="font-size:1.05em; font-weight:bold; color:#333;">
                {escape(cur_activity) if cur_activity else "<span style='color:#aaa;'>Free time</span>"}
            </div>
        </div>
    """

    if next_label:
        now_html += f"""
        <div style="flex:1; min-width:180px; background:#f9f9f9; border:1px solid #e0e0e0;
                    border-left:5px solid #aaa; border-radius:10px; padding:12px 14px;">
            <div style="font-size:0.78em; font-weight:bold; color:#888;
                        text-transform:uppercase; letter-spacing:1px; margin-bottom:4px;">
                Next · {escape(next_label)}
            </div>
            <div style="font-size:1.05em; color:#555;">
                {escape(next_activity) if next_activity else "<span style='color:#aaa;'>Free time</span>"}
            </div>
        </div>
        """

    now_html += f"""
        <div style="flex:0 0 auto; display:flex; align-items:center;">
            <a class="link-button" href="/family-schedule">Full Schedule</a>
        </div>
    </div>
    """
    return now_html


def render_today_timeline() -> str:
    """Full today timeline for Mom page."""
    from datetime import datetime
    schedule = load_family_schedule()
    times = schedule.get("times", [])
    now = datetime.now()
    today_name = now.strftime("%A")
    today_slots = schedule.get("days", {}).get(today_name, {})
    _, _, _, _ = get_current_slot(schedule)
    cur_label, _, _, _ = get_current_slot(schedule)

    if not times:
        return "<p class='muted'>No schedule loaded.</p>"

    rows = ""
    for t in times:
        activity = today_slots.get(t, "")
        is_now = (t == cur_label)
        bg = "#fff7ed" if is_now else "transparent"
        border = "border-left:4px solid #e67e22;" if is_now else "border-left:4px solid transparent;"
        now_dot = " 🟠" if is_now else ""
        rows += f"""
        <div style="display:grid; grid-template-columns:80px 1fr; gap:8px;
                    padding:6px 10px; background:{bg}; {border} border-radius:6px; margin-bottom:2px;">
            <div style="font-size:0.85em; color:#888; font-weight:bold; padding-top:1px;">
                {escape(t)}{now_dot}
            </div>
            <div style="font-size:0.95em; color:{"#333" if activity else "#ccc"};">
                {escape(activity) if activity else "—"}
            </div>
        </div>
        """

    return f"""
    <div style="margin-top:4px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <strong>{escape(today_name)}'s Timeline</strong>
            <a class="link-button" href="/family-schedule">Edit</a>
        </div>
        {rows}
    </div>
    """


# -------------------------
# FAMILY SCHEDULE PAGE
# -------------------------

def render_family_schedule_page(status_message="") -> str:
    schedule = load_family_schedule()
    times = schedule.get("times", [])
    days_data = schedule.get("days", {})

    # --- Weekly grid ---
    header_cells = "<th style='width:80px;background:#f5f0eb;'>Time</th>" + "".join(
        f"<th style='background:#f5f0eb;font-size:0.9em;padding:8px 6px;'>{escape(d)}</th>"
        for d in SCHEDULE_DAYS
    )

    grid_rows = ""
    for t in times:
        cells = f"<td style='font-size:0.8em;color:#888;font-weight:bold;padding:6px 8px;white-space:nowrap;background:#faf8f5;'>{escape(t)}</td>"
        for d in SCHEDULE_DAYS:
            val = days_data.get(d, {}).get(t, "")
            cells += f"""
            <td style='padding:4px 2px;'>
                <input type='text' name='slot__{escape(d)}__{escape(t)}'
                       value='{escape(val)}'
                       style='width:100%;font-size:0.82em;padding:4px 6px;
                              border:1px solid #ddd;border-radius:6px;
                              background:white;margin:0;'>
            </td>"""
        grid_rows += f"<tr>{cells}</tr>"

    grid_html = f"""
    <div style='overflow-x:auto;'>
        <form method='POST' action='/family-schedule-save'>
            <table style='border-collapse:collapse;width:100%;min-width:700px;'>
                <thead><tr>{header_cells}</tr></thead>
                <tbody>{grid_rows}</tbody>
            </table>
            <div style='margin-top:14px;'>
                <button type='submit'>Save Schedule</button>
            </div>
        </form>
    </div>
    """

    # --- Today timeline preview ---
    timeline_html = render_today_timeline()

    body = f"""
    {page_header("Family Schedule")}
    {render_status_message(status_message)}

    <div class="two-col">
        <div>
            <h2>Today's Timeline</h2>
            <div class="card">{timeline_html}</div>
        </div>
        <div>
            <h2>Now &amp; Next</h2>
            <div class="card">{render_now_next_strip()}</div>
        </div>
    </div>

    <h2>Weekly Grid</h2>
    <div class="card">
        <p class="small">Edit any cell and click Save Schedule. Changes apply immediately.</p>
        {grid_html}
    </div>
    """

    return html_page("Family Schedule", body)


# -------------------------
# HISTORY / SNAPSHOT PAGE
# -------------------------

SNAPSHOT_FILE_LABELS = {
    "chores":           "Chores",
    "manual_tasks":     "Manual Tasks",
    "notes":            "Notes",
    "mom_notes":        "Mom Notes",
    "school_previews":  "School Previews",
    "school_weeks":     "School Weeks (Approved)",
    "family_schedule":  "Family Schedule",
    "roadmap":          "Roadmap",
    "liturgical":       "Liturgical Calendar",
}


def render_history_page(status_message="", filter_stem="") -> str:
    snapshots = list_snapshots()

    # Group by file stem
    grouped = {}
    for s in snapshots:
        stem = s["stem"]
        grouped.setdefault(stem, []).append(s)

    if not grouped:
        no_history = "<div class='card'><p class='muted'>No snapshots yet. They are created automatically whenever you save data.</p></div>"
        return html_page("Version History", f"{page_header('Version History')}{render_status_message(status_message)}{no_history}")

    sections_html = ""
    for stem, snaps in sorted(grouped.items()):
        label = SNAPSHOT_FILE_LABELS.get(stem, stem)
        rows = ""
        for snap in snaps:
            ts = escape(snap["timestamp"])
            fname = escape(snap["filename"])
            rows += f"""
            <div class="card card-tight" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                <div>
                    <strong>{ts}</strong>
                    <span class="small" style="margin-left:8px;">{fname}</span>
                </div>
                <div class="link-row" style="margin:0;">
                    <a class="link-button" href="/history/preview?file={fname}">Preview</a>
                    <form method="POST" action="/history-restore" style="display:inline;">
                        <input type="hidden" name="filename" value="{fname}">
                        <button type="submit" class="secondary" onclick="return confirm('Restore this snapshot? The current file will itself be snapshotted first so you can undo.')">Restore</button>
                    </form>
                </div>
            </div>
            """

        sections_html += f"""
        <div class="card">
            <h2>{escape(label)}</h2>
            <p class="small">{len(snaps)} snapshot{"s" if len(snaps) != 1 else ""} stored (max {10})</p>
            {rows}
        </div>
        """

    body = f"""
    {page_header("Version History")}
    {render_status_message(status_message)}

    <div class="card">
        <p>Snapshots are saved automatically before any data change. Restoring a snapshot
        also snapshots the current state first, so every restore is reversible.</p>
    </div>

    {sections_html}
    """
    return html_page("Version History", body)


def load_roadmap():
    data = ensure_file(ROADMAP_FILE, [])
    return data if isinstance(data, list) else []

def save_roadmap(ideas):
    safe_save_json(ROADMAP_FILE, ideas)


# -------------------------
# ROADMAP PAGE
# -------------------------

def render_roadmap_page(status_message=""):
    import uuid
    ideas = load_roadmap()

    # Group ideas by status
    grouped = {s: [] for s in ROADMAP_STATUSES}
    for idea in ideas:
        s = idea.get("status", "Someday")
        if s not in grouped:
            s = "Someday"
        grouped[s].append(idea)

    status_colors = {
        "Someday":    "#f1ebe4",
        "Ready":      "#e4edf1",
        "In Progress":"#eef1e4",
        "Done":       "#e4e4e4",
    }

    sections_html = ""
    for status in ROADMAP_STATUSES:
        ideas_in_group = grouped[status]
        color = status_colors.get(status, "#f1ebe4")

        cards_html = ""
        for idea in ideas_in_group:
            idea_id = escape(str(idea.get("id", "")))
            title = escape(idea.get("title", ""))
            notes = escape(idea.get("notes", ""))

            status_options = "".join(
                f'<option value="{escape(s)}" {"selected" if s == status else ""}>{escape(s)}</option>'
                for s in ROADMAP_STATUSES
            )

            cards_html += f"""
            <div class="card card-tight" style="border-left: 4px solid {color}; border-left-color: #8b5a3c;">
                <form method="POST" action="/roadmap-update">
                    <input type="hidden" name="id" value="{idea_id}">

                    <h3 style="margin-bottom: 6px;">{title}</h3>

                    <label>Notes</label>
                    <textarea name="notes" rows="3">{notes}</textarea>

                    <label>Status</label>
                    <select name="status">
                        {status_options}
                    </select>

                    <button type="submit">Save</button>
                </form>

                <form method="POST" action="/roadmap-delete" style="margin-top: 6px;">
                    <input type="hidden" name="id" value="{idea_id}">
                    <button type="submit" class="ghost">Remove</button>
                </form>
            </div>
            """

        count = len(ideas_in_group)
        sections_html += f"""
        <div class="card">
            <h2>{escape(status)} <span class="small">({count})</span></h2>
            {cards_html or f"<p class='muted'>No ideas here yet.</p>"}
        </div>
        """

    body = f"""
    {page_header("App Roadmap")}
    {render_status_message(status_message)}

    <div class="card">
        <h2>Capture a New Idea</h2>
        <form method="POST" action="/roadmap-add">
            <label>Idea title</label>
            <input type="text" name="title" placeholder="e.g. Add liturgical calendar">

            <label>Notes (optional)</label>
            <textarea name="notes" rows="3" placeholder="Any details, questions, or context..."></textarea>

            <label>Status</label>
            <select name="status">
                {"".join(f'<option value="{escape(s)}">{escape(s)}</option>' for s in ROADMAP_STATUSES)}
            </select>

            <button type="submit">Add to Roadmap</button>
        </form>
    </div>

    {sections_html}
    """

    return html_page("Roadmap", body)


# -------------------------
# MOM NOTES HELPERS
# -------------------------

def load_mom_notes():
    data = ensure_file(MOM_NOTES_FILE, [])
    return data if isinstance(data, list) else []


def save_mom_notes(notes):
    safe_save_json(MOM_NOTES_FILE, notes)


# -------------------------
# MOM PAGE
# -------------------------

def render_mom_page(status_message=""):
    packet = generate_day_packet("")
    weekday = packet["weekday"]
    date_label = packet["date_label"]
    iso = packet["iso"]

    boy_cards = ""
    for child in CHILDREN:
        payload = build_schedule_payload(child, weekday, date_label, iso)
        school_blocks = payload.get("school_blocks", [])
        chore_count = len(payload.get("chore_items", []))
        carry_count = len(payload.get("carryover_items", []))
        manual_count = len(payload.get("manual_task_items", []))
        school_count = count_school_check_items(payload)

        checklist_html = ""
        for block in school_blocks:
            subject = block.get("subject", "")
            if block.get("is_math") and not block.get("is_math_test"):
                checklist_html += f"""
                <div class="task">
                    <label>&#9744; Check {escape(child)}'s {escape(subject)}</label>
                </div>
                """

        complete = is_day_complete(payload)
        remaining = count_remaining(payload)
        c_bg = child_color(child, "bg")
        c_text = child_color(child, "text")
        c_light = child_color(child, "light")

        if complete:
            status_line = f'<div style="background:{c_bg};color:{c_text};border-radius:8px;padding:6px 12px;margin-bottom:8px;font-weight:bold;">🎉 All done!</div>'
        else:
            status_line = f'<div style="background:#f9f3ee;border:1px solid #e0d5c8;border-radius:8px;padding:6px 12px;margin-bottom:8px;color:#555;">{remaining} item{"s" if remaining != 1 else ""} remaining</div>'

        boy_cards += f"""
        <div class="card" style="border-left:5px solid {c_bg}; background:{c_light};">
            {status_line}
            <h3 style="color:{c_bg};">{escape(child)}</h3>
            <div class="summary-row">
                <span class="badge">Subjects: {len(school_blocks)}</span>
                <span class="badge">School checks: {school_count}</span>
                <span class="badge">Chores: {chore_count}</span>
                <span class="badge">Carryover: {carry_count}</span>
                <span class="badge">Manual: {manual_count}</span>
            </div>
            <div class="link-row">
                <a class="link-button" href="/schedule/{escape(child)}">Open {escape(child)}'s Day</a>
                <a class="link-button" href="/schedule/{escape(child)}?date=tomorrow">Tomorrow</a>
            </div>
            {('<h4>Mom Checklist</h4>' + checklist_html) if checklist_html else ''}
        </div>
        """

    all_tasks = load_manual_tasks()
    mom_task_cards = ""
    for task in all_tasks:
        if not isinstance(task, dict):
            continue
        if task.get("assigned_to", "") != "Mom":
            continue
        if task.get("status", "active") != "active":
            continue
        task_index = all_tasks.index(task)
        mom_task_cards += f"""
        <div class="card card-tight">
            <p><strong>{escape(task.get("text", ""))}</strong></p>
            <p class="small">Due: {escape(task.get("due_date", "") or "Anytime")} | Priority: {escape(task.get("priority", "MEDIUM"))}</p>
            <form method="POST" action="/task-done">
                <input type="hidden" name="index" value="{task_index}">
                <button type="submit">Mark Done</button>
            </form>
        </div>
        """

    mom_notes = load_mom_notes()
    active_mom_notes = [n for n in mom_notes if n.get("status", "active") == "active"]

    note_cards = ""
    for note in active_mom_notes:
        note_cards += f"""
        <div class="card card-tight">
            <p>{escape(note.get("text", ""))}</p>
            <form method="POST" action="/mom-archive-note">
                <input type="hidden" name="id" value="{escape(str(note.get("id", "")))}">
                <button type="submit" class="ghost">Archive</button>
            </form>
        </div>
        """

    assignable_options = "".join(
        f'<option value="{escape(p)}">{escape(p)}</option>'
        for p in ASSIGNABLE_TO
    )

    month_summary = render_month_summary_card()

    body = f"""
    {page_header("Mom's Command Center")}
    {render_status_message(status_message)}
    {month_summary}

    <div class="grid">
        <div class="card">
            <h3>Today</h3>
            <p><strong>{escape(weekday)}</strong></p>
            <p>{escape(date_label)}</p>
        </div>

        <div class="card">
            <h3>Liturgical Calendar</h3>
            {render_liturgical_day_card(date.today(), compact=True)}
        </div>
    </div>

    <div class="card" style="margin-bottom:16px;">
        <h3 style="margin-bottom:10px;">Today's Timeline</h3>
        {render_today_timeline()}
    </div>

    <div class="card" style="margin-bottom:16px;">
        <h3 style="margin-bottom:10px;">📆 Today's Events</h3>
        {render_calendar_today_strip(iso)}
    </div>

    <h2>The Boys Today</h2>
    <div class="grid">
        {boy_cards}
    </div>

    <div class="two-col">
        <div>
            <h2>My Tasks</h2>
            {mom_task_cards or "<div class='card'><p class='muted'>No tasks assigned to Mom.</p></div>"}

            <div class="card">
                <h3>Add a Task</h3>
                <form method="POST" action="/add-task">
                    <label>Task</label>
                    <input type="text" name="text">

                    <label>Assign to</label>
                    <select name="assigned_to">
                        {assignable_options}
                    </select>

                    <label>Due date</label>
                    <input type="date" name="due_date">

                    <label>Priority</label>
                    <select name="priority">
                        <option value="HIGH">HIGH</option>
                        <option value="MEDIUM" selected>MEDIUM</option>
                        <option value="LOW">LOW</option>
                    </select>

                    <button type="submit">Add Task</button>
                </form>
            </div>
        </div>

        <div>
            <h2>My Notes</h2>
            {note_cards or "<div class='card'><p class='muted'>No active notes.</p></div>"}

            <div class="card">
                <h3>Add a Note</h3>
                <form method="POST" action="/mom-add-note">
                    <label>Note</label>
                    <textarea name="text" rows="4"></textarea>
                    <button type="submit">Save Note</button>
                </form>
            </div>
        </div>
    </div>
    """

    return html_page("Mom", body)


# -------------------------
# DASHBOARD / TODAY / WEEK
# -------------------------

def render_dashboard():
    packet = generate_day_packet("")
    notes = load_notes()
    active_notes = [n for n in notes if n.get("status") == "active"]
    tasks = active_manual_tasks()

    cards = ""
    for child in CHILDREN:
        payload = build_schedule_payload(child, packet["weekday"], packet["date_label"], packet["iso"])
        school_subjects = len(payload.get("school_blocks", []))
        chore_count = len(payload.get("chore_items", []))
        carry_count = len(payload.get("carryover_items", []))
        manual_count = len(payload.get("manual_task_items", []))

        c_bg = child_color(child, "bg")
        c_light = child_color(child, "light")
        complete = is_day_complete(payload)
        completion_banner = f'<div style="background:{c_bg};color:{child_color(child,"text")};border-radius:8px;padding:6px 12px;margin-bottom:8px;font-weight:bold;font-size:0.9em;">🎉 All done today!</div>' if complete else ""
        cards += f"""
        <div class="card" style="border-left: 5px solid {c_bg}; background: {c_light};">
            {completion_banner}
            <h3 style="color:{c_bg};">{escape(child)}</h3>
            <div class="summary-row">
                <span class="badge">Subjects: {school_subjects}</span>
                <span class="badge">Chores: {chore_count}</span>
                <span class="badge">Carryover: {carry_count}</span>
                <span class="badge">Manual: {manual_count}</span>
            </div>
            <div class="link-row">
                <a class="link-button" href="/schedule/{escape(child)}">Open Schedule</a>
                <a class="link-button" href="/schedule/{escape(child)}?date=tomorrow">Tomorrow</a>
            </div>
        </div>
        """

    litany_html = render_litany_block()
    month_card = render_month_summary_card()

    body = f"""
    {page_header("Family Planner")}

    {litany_html}

    <div class="link-row no-print">
        <a class="link-button" href="/print/day">Print Today</a>
        <a class="link-button" href="/print/day?date=tomorrow">Print Tomorrow</a>
        <a class="link-button" href="/print/week">Print Week</a>
    </div>

    <div class="card" style="margin-bottom:16px;">
        <h3 style="margin-bottom:10px;">Now &amp; Next</h3>
        {render_now_next_strip()}
    </div>

    <div class="grid">
        <div class="card">
            <h3>Today</h3>
            <p><strong>{escape(packet["weekday"])}</strong></p>
            <p>{escape(packet["date_label"])}</p>
        </div>

        <div class="card">
            <h3>📆 Today's Events</h3>
            {render_calendar_today_strip(packet["iso"])}
        </div>

        <div class="card">
            <h3>System Snapshot</h3>
            <p>Active notes: {len(active_notes)}</p>
            <p>Active manual tasks: {len(tasks)}</p>
        </div>
    </div>
    """

    mom_tasks = [t for t in active_manual_tasks() if t.get("assigned_to") == "Mom"]
    mom_notes_count = len([n for n in load_mom_notes() if n.get("status", "active") == "active"])

    mom_card = f"""
    <div class="card">
        <h3>Mom</h3>
        <div class="summary-row">
            <span class="badge">My tasks: {len(mom_tasks)}</span>
            <span class="badge">My notes: {mom_notes_count}</span>
        </div>
        <div class="link-row">
            <a class="link-button" href="/mom">Open Command Center</a>
        </div>
    </div>
    """

    # Liturgical card for dashboard
    from datetime import date as _date_cls
    today_d = _date_cls.today()
    lit_info = get_day_info(today_d)
    lit_vest_bg, lit_vest_text = get_vestment_color(lit_info)
    lit_color_bar = (
        f'<div style="background:{lit_vest_bg}; color:{lit_vest_text}; border-radius:8px; '
        f'padding:6px 12px; margin-bottom:8px; font-weight:bold; font-size:0.9em;">'
        f'{escape(lit_info["season"])}'
        f'</div>'
    )
    lit_feast = f"<p><strong>{escape(lit_info['feast_name'])}</strong></p>" if lit_info["feast_name"] else "<p class='muted'>No feast today</p>"
    lit_obs = "".join(f"<span class='badge'>{escape(o)}</span> " for o in lit_info["observances"])
    lit_readings_url = f"https://bible.usccb.org/bible/readings/{today_d.strftime('%m%d%y')}.cfm"

    liturgical_card = f"""
    <div class="card">
        <h3>Liturgy</h3>
        {lit_color_bar}
        {lit_feast}
        <div class="summary-row" style="margin-bottom:8px;">{lit_obs}</div>
        <div class="link-row">
            <a class="link-button" href="{lit_readings_url}" target="_blank">Mass Readings ↗</a>
            <a class="link-button" href="/liturgical">Full Calendar</a>
        </div>
    </div>
    """

    # Calendar events for dashboard
    calendar_card = f"""
    <div class="card">
        <h3>📆 Today's Events</h3>
        {render_calendar_today_strip(packet["iso"])}
    </div>
    """

    body += f"""
    <h2>Today's Overview</h2>
    <div class="grid">
        {liturgical_card}
        {calendar_card}
        {mom_card}
        {cards}
    </div>
    """

    return html_page("Dashboard", body)


def render_today_all(target_date_str=""):
    normalized_date = normalize_date_query(target_date_str)
    html = "".join(render_child_schedule_card(child, normalized_date) for child in CHILDREN)
    return html_page("Today", f"{page_header('Today')}{html}")


def render_week():
    week = generate_week_packet("")
    html = ""

    for day in week["days"]:
        html += f"""
        <div class="card">
            <h2>{escape(day["weekday"])} — {escape(day["date_label"])}</h2>
            <div class="link-row no-print">
                <a class="link-button" href="/print/day?date={escape(day["iso"])}">Print This Day</a>
            </div>
            <div class="grid">
        """

        for child in CHILDREN:
            preview = day["schedules"][child][:300]
            html += f"""
            <div class="card card-tight">
                <h3>{escape(child)}</h3>
                <div class="link-row">
                    <a class="link-button" href="/schedule/{escape(child)}?date={escape(day["iso"])}">Open This Day</a>
                </div>
                <pre>{escape(preview)}{"..." if len(day["schedules"][child]) > 300 else ""}</pre>
            </div>
            """

        html += """
            </div>
        </div>
        """

    return html_page("Week", f"{page_header('Week')}{html}")


# -------------------------
# PRINT
# -------------------------

def print_page_html(title: str, body: str) -> str:
    """Standalone print-optimized HTML page with its own clean stylesheet."""
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 13pt;
      color: #111;
      background: white;
      padding: 0;
  }}

  /* Each boy's section fills one page */
  .child-page {{
      page-break-after: always;
      padding: 0.6in 0.7in 0.5in;
      min-height: 100vh;
  }}
  .child-page:last-child {{
      page-break-after: avoid;
  }}

  /* Header stripe in child's color */
  .page-header {{
      border-bottom: 4px solid var(--child-color);
      padding-bottom: 10px;
      margin-bottom: 18px;
  }}
  .child-name {{
      font-size: 28pt;
      font-weight: bold;
      color: var(--child-color);
      letter-spacing: 1px;
  }}
  .date-line {{
      font-size: 13pt;
      color: #555;
      margin-top: 2px;
  }}

  /* Section headers */
  .section-title {{
      font-size: 11pt;
      font-weight: bold;
      text-transform: uppercase;
      letter-spacing: 2px;
      color: #777;
      border-bottom: 1px solid #ddd;
      padding-bottom: 3px;
      margin: 16px 0 8px;
  }}

  /* Subject blocks */
  .subject-name {{
      font-size: 14pt;
      font-weight: bold;
      color: #222;
      margin: 12px 0 4px;
  }}
  .assignment-text {{
      font-size: 11pt;
      color: #444;
      margin: 0 0 6px 16px;
      line-height: 1.5;
      white-space: pre-wrap;
  }}
  .math-note {{
      font-size: 10.5pt;
      color: #555;
      font-style: italic;
      margin: 0 0 6px 16px;
  }}

  /* Checkbox items */
  .check-item {{
      display: flex;
      align-items: flex-start;
      gap: 10px;
      margin: 5px 0 5px 16px;
      font-size: 12pt;
      line-height: 1.4;
  }}
  .checkbox {{
      width: 16px;
      height: 16px;
      border: 2px solid #555;
      border-radius: 3px;
      flex-shrink: 0;
      margin-top: 2px;
      display: inline-block;
  }}

  /* Carryover section */
  .carryover-item {{
      display: flex;
      align-items: flex-start;
      gap: 10px;
      margin: 5px 0 5px 16px;
      font-size: 12pt;
      color: #666;
      font-style: italic;
  }}

  /* Footer */
  .page-footer {{
      margin-top: 24px;
      border-top: 1px solid #ddd;
      padding-top: 8px;
      font-size: 9pt;
      color: #aaa;
      text-align: right;
  }}

  @media print {{
      body {{ background: white; }}
      .no-print {{ display: none !important; }}
  }}

  @media screen {{
      body {{ background: #f0f0f0; }}
      .child-page {{
          background: white;
          margin: 20px auto;
          max-width: 8.5in;
          box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      }}
  }}
</style>
</head>
<body>
<div class="no-print" style="background:#333;color:white;padding:10px 20px;font-family:sans-serif;font-size:13px;">
    <button onclick="window.print()" style="background:#8b5a3c;color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;margin-right:12px;">🖨 Print</button>
    <a href="/" style="color:#ccc;">← Back to Dashboard</a>
</div>
{body}
</body>
</html>"""


def render_print_child_page(child: str, weekday: str, date_label: str, iso: str) -> str:
    """Render one child's full print page."""
    payload = build_schedule_payload(child, weekday, date_label, iso)
    c_color = child_color(child, "bg")

    sections_html = ""

    # --- Carryover ---
    carryover = payload.get("carryover_items", [])
    if carryover:
        items_html = "".join(
            f'<div class="carryover-item"><span class="checkbox"></span>{escape(item["text"])}</div>'
            for item in carryover
        )
        sections_html += f'<div class="section-title">Carryover</div>{items_html}'

    # --- Manual Tasks ---
    manual = payload.get("manual_task_items", [])
    if manual:
        items_html = "".join(
            f'<div class="check-item"><span class="checkbox"></span>{escape(item["text"])}</div>'
            for item in manual
        )
        sections_html += f'<div class="section-title">Tasks</div>{items_html}'

    # --- School ---
    school_blocks = payload.get("school_blocks", [])
    if school_blocks:
        blocks_html = ""
        for block in school_blocks:
            subject = block.get("subject", "")
            assignment_text = block.get("assignment_text", "")
            is_math = block.get("is_math", False)
            is_math_test = block.get("is_math_test", False)
            items = block.get("items", [])

            math_note = ""
            if is_math_test:
                math_note = '<div class="math-note">TEST — bring to Mom for review</div>'
            elif is_math:
                math_note = '<div class="math-note">Do all Lesson Practice and only the Mixed Practice from the last four lessons.</div>'

            assignment_html = f'<div class="assignment-text">{escape(assignment_text)}</div>' if assignment_text else ""

            checklist_html = "".join(
                f'<div class="check-item"><span class="checkbox"></span>{escape(item["text"])}</div>'
                for item in items
            )

            blocks_html += f"""
            <div class="subject-name">{escape(subject)}</div>
            {math_note}
            {assignment_html}
            {checklist_html}
            """

        sections_html += f'<div class="section-title">School</div>{blocks_html}'

    # --- Chores ---
    chores = payload.get("chore_items", [])
    if chores:
        items_html = "".join(
            f'<div class="check-item"><span class="checkbox"></span>{escape(item["text"])}</div>'
            for item in chores
        )
        sections_html += f'<div class="section-title">Chores</div>{items_html}'

    return f"""
    <div class="child-page" style="--child-color:{c_color};">
        <div class="page-header">
            <div class="child-name">{escape(child)}</div>
            <div class="date-line">{escape(weekday)}, {escape(date_label)}</div>
        </div>
        {sections_html or '<p style="color:#aaa;font-style:italic;">Nothing scheduled today.</p>'}
        <div class="page-footer">Family Planner · {escape(date_label)}</div>
    </div>
    """


def render_print_day(target_date_str=""):
    normalized_date = normalize_date_query(target_date_str)
    packet = generate_day_packet(normalized_date)
    weekday = packet["weekday"]
    date_label = packet["date_label"]
    iso = packet["iso"]

    pages = "".join(
        render_print_child_page(child, weekday, date_label, iso)
        for child in CHILDREN
    )

    return print_page_html(f"{weekday} — {date_label}", pages)


def render_print_week():
    week = generate_week_packet("")
    pages = ""

    for day in week["days"]:
        weekday = day["weekday"]
        date_label = day["date_label"]
        iso = day["iso"]
        for child in CHILDREN:
            pages += render_print_child_page(child, weekday, date_label, iso)

    return print_page_html("Week Packet", pages)


# -------------------------
# CHILD SCHEDULE
# -------------------------

def render_child_schedule(child, target_date_str=""):
    normalized_date = normalize_date_query(target_date_str)
    body = f"""
    {page_header(child)}
    {render_child_schedule_card(child, normalized_date)}
    """
    return html_page(child, body)


# -------------------------
# SCHOOL PAGE
# -------------------------

def render_school_preview_card(child, preview):
    parsed = preview.get("parsed", {})
    filename = preview.get("filename", "Untitled")
    parsed_days = sort_school_days(parsed.get("parsed_days", []))
    raw_text = preview.get("raw_text", "")

    day_html = ""
    for day in parsed_days:
        blocks_html = ""
        for block in day.get("blocks", []):
            blocks_html += f"""
            <div class="subject-card">
                <h4>{escape(block.get("subject", ""))}</h4>
                <pre>{escape(block.get("assignment_text", ""))}</pre>
            </div>
            """

        day_html += f"""
        <div class="card card-tight">
            <h3>{escape(day.get("day_label", day.get("weekday", "")))}</h3>
            <p class="small">Weekday key: {escape(day.get("weekday", ""))}</p>
            {blocks_html or "<p class='muted'>No parsed blocks.</p>"}
        </div>
        """

    raw_text_preview = f"<pre>{escape(raw_text[:1200])}{'...' if len(raw_text) > 1200 else ''}</pre>" if raw_text else "<p class='muted'>No raw text stored.</p>"

    return f"""
    <div class="card">
        <h2>{escape(child)} Preview</h2>
        <p class="small">Source: {escape(filename)}</p>

        <div class="link-row no-print">
            <a class="link-button" href="/school/edit?child={escape(child)}">Edit Preview</a>
        </div>

        <form method="POST" action="/approve-school-preview" class="no-print">
            <input type="hidden" name="child" value="{escape(child)}">
            <button type="submit">Approve Preview</button>
        </form>

        <h3>Parsed Days</h3>
        {day_html or "<p class='muted'>No parsed blocks yet.</p>"}

        <h3>Raw Text</h3>
        {raw_text_preview}
    </div>
    """


def render_school_page(status_message=""):
    previews = load_school_previews()
    weeks = load_school_weeks()
    approved = weeks.get("approved", {})

    preview_cards = ""
    for child in CHILDREN:
        if child in previews:
            preview_cards += render_school_preview_card(child, previews[child])

    approved_cards = ""
    for child in CHILDREN:
        parsed = approved.get(child, {})
        parsed_days = sort_school_days(parsed.get("parsed_days", []))
        approved_cards += f"""
        <div class="card">
            <h3>{escape(child)}</h3>
            <p class="small">Approved days: {len(parsed_days)}</p>
        </div>
        """

    child_options = "".join(
        f'<option value="{escape(child)}">{escape(child)}</option>'
        for child in CHILDREN
    )

    body = f"""
    {page_header("School")}
    {render_status_message(status_message)}

    <div class="two-col">
        <div class="card">
            <h2>Upload or Paste School List</h2>
            <form method="POST" action="/school-upload" enctype="multipart/form-data">
                <label>Child</label>
                <select name="child">
                    {child_options}
                </select>

                <label>PDF or text file</label>
                <input type="file" name="file">

                <label>Or paste text</label>
                <textarea name="raw_text" rows="10"></textarea>

                <button type="submit">Create Preview</button>
            </form>
        </div>

        <div class="card">
            <h2>Approved Weeks</h2>
            {approved_cards or "<p class='muted'>No approved school weeks yet.</p>"}
        </div>
    </div>

    <h2>Preview</h2>
    {preview_cards or "<div class='card'><p class='muted'>No previews yet.</p></div>"}
    """

    return html_page("School", body)


def render_school_edit_page(child, status_message=""):
    preview = load_school_preview(child)

    if not preview:
        body = f"""
        {page_header("Edit School Preview")}
        <div class="card"><p class="muted">No preview found for {escape(child)}.</p></div>
        """
        return html_page("Edit School Preview", body)

    parsed = preview.get("parsed", {})
    parsed_days = sort_school_days(parsed.get("parsed_days", []))
    filename = preview.get("filename", "Untitled")
    raw_text = preview.get("raw_text", "")

    raw_text_editor = f"""
    <div class="card">
        <h2>Edit Raw Text</h2>
        <p class="small">Edit the text here, then click Reparse Raw Text to rebuild the preview blocks.</p>

        <form method="POST" action="/reparse-school-preview">
            <input type="hidden" name="child" value="{escape(child)}">

            <label>Raw text</label>
            <textarea name="raw_text" rows="18">{escape(raw_text)}</textarea>

            <button type="submit">Reparse Raw Text</button>
        </form>
    </div>
    """

    if not parsed_days:
        body = f"""
        {page_header(f"Edit School Preview — {child}")}
        {render_status_message(status_message)}

        <div class="card">
            <p class="small">Source: {escape(filename)}</p>
            <p class="small">No parsed day blocks currently exist. Edit the raw text below and click Reparse Raw Text.</p>
        </div>

        {raw_text_editor}
        """
        return html_page("Edit School Preview", body)

    day_forms = ""
    for day_index, day in enumerate(parsed_days):
        day_label = day.get("day_label", "")
        weekday = day.get("weekday", "")
        blocks = day.get("blocks", [])

        block_forms = ""
        for block_index, block in enumerate(blocks):
            block_forms += f"""
            <div class="preview-edit-block">
                <input type="hidden" name="block_count__{day_index}" value="{len(blocks) + 1}">

                <div class="block-toolbar">
                    <div>
                        <label>Order</label>
                        <input type="number" name="order__{day_index}__{block_index}" value="{block_index + 1}">
                    </div>
                    <div class="block-remove">
                        <input type="checkbox" name="delete__{day_index}__{block_index}" value="yes">
                        <label>Delete this block</label>
                    </div>
                </div>

                <label>Subject</label>
                <input type="text" name="subject__{day_index}__{block_index}" value="{escape(block.get("subject", ""))}">

                <label>Assignment Text</label>
                <textarea name="assignment__{day_index}__{block_index}" rows="6">{escape(block.get("assignment_text", ""))}</textarea>
            </div>
            """

        new_block_index = len(blocks)
        block_forms += f"""
        <div class="preview-edit-block">
            <input type="hidden" name="block_count__{day_index}" value="{len(blocks) + 1}">
            <h4>Add New Block</h4>

            <div class="block-toolbar">
                <div>
                    <label>Order</label>
                    <input type="number" name="order__{day_index}__{new_block_index}" value="{len(blocks) + 1}">
                </div>
                <div></div>
            </div>

            <label>Subject</label>
            <input type="text" name="subject__{day_index}__{new_block_index}" value="">

            <label>Assignment Text</label>
            <textarea name="assignment__{day_index}__{new_block_index}" rows="5"></textarea>
        </div>
        """

        day_forms += f"""
        <div class="card">
            <h3>{escape(day_label or weekday)}</h3>

            <label>Weekday</label>
            <select name="weekday__{day_index}">
                {''.join(
                    f'<option value="{escape(day_name)}" {"selected" if day_name == weekday else ""}>{escape(day_name)}</option>'
                    for day_name in WEEKDAYS
                )}
            </select>

            <label>Day label</label>
            <input type="text" name="day_label__{day_index}" value="{escape(day_label)}">

            {block_forms}
        </div>
        """

    body = f"""
    {page_header(f"Edit School Preview — {child}")}
    {render_status_message(status_message)}

    <div class="card">
        <p class="small">Source: {escape(filename)}</p>
        <p class="small">Correct weekday placement, reorder or delete blocks, and add new ones. Save first, then approve from the School page.</p>
    </div>

    <form method="POST" action="/save-school-preview-edits">
        <input type="hidden" name="child" value="{escape(child)}">
        <input type="hidden" name="day_count" value="{len(parsed_days)}">

        {day_forms}

        <button type="submit">Save Preview Edits</button>
    </form>

    {raw_text_editor}
    """

    return html_page("Edit School Preview", body)


# -------------------------
# CHORES PAGE
# -------------------------

def render_chores_page():
    chores = load_chores_data()
    boys = chores.get("boys", {})

    sections = ""
    for child in CHILDREN:
        child_data = boys.get(child, {})
        daily_text = "\n".join(child_data.get("daily", []))
        weekly = child_data.get("weekly", {})

        weekday_fields = ""
        for weekday in WEEKDAYS:
            value = "\n".join(weekly.get(weekday, []))
            weekday_fields += f"""
            <label>{escape(weekday)}</label>
            <textarea name="weekly__{escape(child)}__{escape(weekday)}" rows="3">{escape(value)}</textarea>
            """

        c_bg = child_color(child, "bg")
        c_light = child_color(child, "light")
        sections += f"""
        <div class="card" style="border-left: 5px solid {c_bg}; background:{c_light};">
            <h2 style="color:{c_bg};">{escape(child)}</h2>

            <label>Daily chores/jobs</label>
            <textarea name="daily__{escape(child)}" rows="5">{escape(daily_text)}</textarea>

            <h3>Weekly chores/jobs</h3>
            {weekday_fields}
        </div>
        """

    body = f"""
    {page_header("Chores")}

    <form method="POST" action="/save-chores">
        {sections}
        <button type="submit">Save Chores</button>
    </form>
    """

    return html_page("Chores", body)


# -------------------------
# NOTES
# -------------------------

def render_notes():
    notes = load_notes()
    active_notes = [n for n in notes if n.get("status") == "active"]

    note_cards = ""
    for note in active_notes:
        note_id = escape(note.get("id", ""))
        note_text = escape(note.get("text", ""))
        suggestion = route_note_text(note.get("text", "")).get("suggested_destination", "notes")

        child_options = "".join(
            f'<option value="{escape(child)}">{escape(child)}</option>'
            for child in CHILDREN
        )

        note_cards += f"""
        <div class="card">
            <p>{note_text}</p>
            <p class="small">Suggested destination: {escape(suggestion)}</p>

            <form method="POST" action="/convert-note">
                <input type="hidden" name="id" value="{note_id}">

                <label>Assign to</label>
                <select name="assigned_to">
                    <option value="">Anyone</option>
                    {child_options}
                </select>

                <label>Due date</label>
                <input type="date" name="due_date">

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
        </div>
        """

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

    {note_cards or "<div class='card'><p class='muted'>No active notes.</p></div>"}
    """
    return html_page("Notes", body)


# -------------------------
# RECURRING TASK HELPERS
# -------------------------

def advance_recurring_task(task: dict) -> dict:
    """Given a completed recurring task, reset it with the next due date."""
    from datetime import date as _date
    unit = task.get("interval_unit", "weeks")
    value = safe_int(task.get("interval_value", 1), 1)
    if value < 1:
        value = 1

    base_str = task.get("due_date", "") or _date.today().isoformat()
    try:
        base = _date.fromisoformat(base_str)
    except Exception:
        base = _date.today()

    if unit == "days":
        next_due = base + timedelta(days=value)
    elif unit == "months":
        month = base.month - 1 + value
        year = base.year + month // 12
        month = month % 12 + 1
        import calendar
        day = min(base.day, calendar.monthrange(year, month)[1])
        next_due = base.replace(year=year, month=month, day=day)
    else:  # weeks default
        next_due = base + timedelta(weeks=value)

    task = dict(task)
    task["due_date"] = next_due.isoformat()
    task["status"] = "active"
    return task


# -------------------------
# TASKS
# -------------------------

def render_tasks():
    tasks = load_manual_tasks()

    active_cards = ""
    done_cards = ""

    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue

        status = clean_status(task.get("status", "active"))
        text = escape(task.get("text", ""))
        assigned_to = escape(task.get("assigned_to", "") or "Anyone")
        due_date = escape(task.get("due_date", "") or "Anytime")
        priority = escape(task.get("priority", "MEDIUM"))
        is_recurring = task.get("recurring", False)

        recur_badge = ""
        if is_recurring:
            unit = escape(task.get("interval_unit", "weeks"))
            value = escape(str(task.get("interval_value", 1)))
            recur_badge = f" <span class='badge'>↻ every {value} {unit}</span>"

        card_html = f"""
        <div class="card">
            <h3>{text}{recur_badge}</h3>
            <p class="small">Assigned: {assigned_to} | Due: {due_date} | Priority: {priority}</p>

            <form method="POST" action="/task-done">
                <input type="hidden" name="index" value="{index}">
                <button type="submit">Mark Done</button>
            </form>

            <form method="POST" action="/task-delete">
                <input type="hidden" name="index" value="{index}">
                <button type="submit" class="ghost">Remove</button>
            </form>
        </div>
        """

        if status == "done":
            done_cards += card_html
        elif status == "active":
            active_cards += card_html

    assignable_options = "".join(
        f'<option value="{escape(p)}">{escape(p)}</option>'
        for p in ASSIGNABLE_TO
    )

    body = f"""
    {page_header("Tasks")}

    <div class="two-col">
        <div class="card">
            <h3>Add a One-Time Task</h3>
            <form method="POST" action="/add-task">
                <label>Task</label>
                <input type="text" name="text">

                <label>Assign to</label>
                <select name="assigned_to">
                    <option value="">Anyone</option>
                    {assignable_options}
                </select>

                <label>Due date</label>
                <input type="date" name="due_date">

                <label>Priority</label>
                <select name="priority">
                    <option value="HIGH">HIGH</option>
                    <option value="MEDIUM" selected>MEDIUM</option>
                    <option value="LOW">LOW</option>
                </select>

                <button type="submit">Add Task</button>
            </form>
        </div>

        <div class="card">
            <h3>Add a Recurring Task</h3>
            <form method="POST" action="/add-task">
                <input type="hidden" name="recurring" value="true">

                <label>Task</label>
                <input type="text" name="text">

                <label>Assign to</label>
                <select name="assigned_to">
                    <option value="">Anyone</option>
                    {assignable_options}
                </select>

                <label>First due date</label>
                <input type="date" name="due_date">

                <label>Priority</label>
                <select name="priority">
                    <option value="HIGH">HIGH</option>
                    <option value="MEDIUM" selected>MEDIUM</option>
                    <option value="LOW">LOW</option>
                </select>

                <label>Repeat every</label>
                <div style="display:flex; gap:10px; align-items:center; margin-bottom:12px;">
                    <input type="number" name="interval_value" value="1" min="1"
                           style="width:80px; max-width:80px; margin-bottom:0;">
                    <select name="interval_unit" style="margin-bottom:0;">
                        <option value="days">Days</option>
                        <option value="weeks" selected>Weeks</option>
                        <option value="months">Months</option>
                    </select>
                </div>

                <button type="submit">Add Recurring Task</button>
            </form>
        </div>
    </div>

    <h2>Active Tasks</h2>
    {active_cards or "<div class='card'><p class='muted'>No active tasks.</p></div>"}

    <h2>Done Tasks</h2>
    {done_cards or "<div class='card'><p class='muted'>No done tasks yet.</p></div>"}
    """
    return html_page("Tasks", body)


# -------------------------
# ROUTER
# -------------------------

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        route = urlparse(self.path)
        path = route.path
        query = parse_qs(route.query)

        if path == "/":
            body = render_dashboard()
        elif path == "/today":
            body = render_today_all(query.get("date", [""])[0])
        elif path == "/week":
            body = render_week()
        elif path == "/school":
            body = render_school_page()
        elif path == "/school/edit":
            child = clean_child(query.get("child", [""])[0])
            body = render_school_edit_page(child)
        elif path == "/chores":
            body = render_chores_page()
        elif path == "/print/day":
            body = render_print_day(query.get("date", [""])[0])
        elif path == "/print/week":
            body = render_print_week()
        elif path.startswith("/schedule/"):
            child = path.split("/")[-1]
            if child not in CHILDREN:
                self.send_response(404)
                self.end_headers()
                return
            body = render_child_schedule(child, query.get("date", [""])[0])
        elif path == "/notes":
            body = render_notes()
        elif path == "/tasks":
            body = render_tasks()
        elif path == "/mom":
            body = render_mom_page()
        elif path == "/roadmap":
            body = render_roadmap_page()
        elif path == "/family-schedule":
            body = render_family_schedule_page()
        elif path == "/calendar":
            body = render_calendar_page()
        elif path == "/planner":
            body = render_planner_page()
        elif path == "/calendar/refresh":
            refresh_calendar(force=True)
            self.send_response(303)
            self.send_header("Location", "/calendar")
            self.end_headers()
            return

        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_POST(self):
        path = urlparse(self.path).path
        data = parse_urlencoded_body(self)
        redirect = "/"

        if path == "/planner-add-task":
            text = clean_text(data.get("text", [""])[0])
            if text:
                tasks = load_manual_tasks()
                tasks.append({
                    "text": text,
                    "assigned_to": "Mom",
                    "due_date": "",
                    "priority": "MEDIUM",
                    "status": "active",
                    "recurring": False,
                })
                save_manual_tasks(tasks)
                redirect = "/planner"

            elif path == "/subscribed-cal-add":
                import uuid
                name  = clean_text(data.get("name",  [""])[0])
                url   = clean_text(data.get("url",   [""])[0])
                color = clean_text(data.get("color", ["#9b59b6"])[0])
                if name and url:
                    cals = load_subscribed_calendars()
                    cals.append({
                        "id":      str(uuid.uuid4()),
                        "name":    name,
                        "url":     url,
                        "color":   color,
                        "enabled": True,
                    })
                    save_subscribed_calendars(cals)
                redirect = "/calendar"

            elif path == "/subscribed-cal-delete":
                idx = safe_int(data.get("index", ["0"])[0], 0)
                cals = load_subscribed_calendars()
                if 0 <= idx < len(cals):
                    cals.pop(idx)
                    save_subscribed_calendars(cals)
                redirect = "/calendar"

            elif path == "/calendar-save-config":
                apple_id = clean_text(data.get("apple_id", [""])[0])
                app_password = clean_text(data.get("app_password", [""])[0])
                cfg = load_calendar_config()
                # Always update Apple ID
                if apple_id:
                    cfg["apple_id"] = apple_id
                # Only update password if a new one was entered
                if app_password:
                    cfg["app_password"] = app_password
                save_calendar_config(cfg)
                # Don't auto-refresh — let user click Sync Now
                redirect = "/calendar"

            elif path == "/calendar-refresh":
                refresh_calendar(force=True)
                redirect = "/calendar"

            elif path == "/family-schedule-save":
                schedule = load_family_schedule()
                days_data = schedule.get("days", {})
                for key, val_list in data.items():
                    if key.startswith("slot__"):
                        parts = key.split("__", 2)
                        if len(parts) == 3:
                            _, day, time_slot = parts
                            if day not in days_data:
                                days_data[day] = {}
                            days_data[day][time_slot] = clean_text(val_list[0])
                schedule["days"] = days_data
                save_family_schedule(schedule)
                redirect = "/family-schedule"

            elif path == "/roadmap-add":
                import uuid
                title = clean_text(data.get("title", [""])[0])
                notes_text = clean_text(data.get("notes", [""])[0])
                status = clean_text(data.get("status", ["Someday"])[0])
                if status not in ROADMAP_STATUSES:
                    status = "Someday"
                if title:
                    ideas = load_roadmap()
                    ideas.append({
                        "id": str(uuid.uuid4()),
                        "title": title,
                        "notes": notes_text,
                        "status": status,
                    })
                    save_roadmap(ideas)
                redirect = "/roadmap"

            elif path == "/roadmap-update":
                idea_id = clean_text(data.get("id", [""])[0])
                notes_text = clean_text(data.get("notes", [""])[0])
                status = clean_text(data.get("status", ["Someday"])[0])
                if status not in ROADMAP_STATUSES:
                    status = "Someday"
                ideas = load_roadmap()
                for idea in ideas:
                    if str(idea.get("id", "")) == idea_id:
                        idea["notes"] = notes_text
                        idea["status"] = status
                        break
                save_roadmap(ideas)
                redirect = "/roadmap"

            elif path == "/roadmap-delete":
                idea_id = clean_text(data.get("id", [""])[0])
                ideas = load_roadmap()
                ideas = [i for i in ideas if str(i.get("id", "")) != idea_id]
                save_roadmap(ideas)
                redirect = "/roadmap"

            elif path == "/liturgical-save":
                date_str = clean_text(data.get("date", [""])[0])
                name = clean_text(data.get("name", [""])[0])
                notes = clean_text(data.get("notes", [""])[0])
                color = clean_text(data.get("color", [""])[0])
                try:
                    date.fromisoformat(date_str)
                    valid_date = True
                except Exception:
                    valid_date = False
                if valid_date and (name or notes or color):
                    custom = load_liturgical_custom()
                    custom[date_str] = {
                        "name": name,
                        "notes": notes,
                        "color": color,
                    }
                    save_liturgical_custom(custom)
                redirect = "/liturgical"

            elif path == "/liturgical-delete":
                date_str = clean_text(data.get("date", [""])[0])
                custom = load_liturgical_custom()
                custom.pop(date_str, None)
                save_liturgical_custom(custom)
                redirect = "/liturgical"

            elif path == "/liturgical-note":
                date_str = clean_text(data.get("date", [""])[0])
                family_note = clean_text(data.get("family_note", [""])[0])
                try:
                    date.fromisoformat(date_str)
                    valid_date = True
                except Exception:
                    valid_date = False
                if valid_date:
                    custom = load_liturgical_custom()
                    if date_str not in custom:
                        custom[date_str] = {}
                    custom[date_str]["family_note"] = family_note
                    save_liturgical_custom(custom)
                redirect = "/liturgical"

            else:
                redirect = "/"

        self.send_response(303)
        self.send_header("Location", redirect)
        self.end_headers()


if __name__ == "__main__":
    print(f"Running on http://{HOST}:{PORT}")
    server = HTTPServer((HOST, PORT), Handler)
    server.serve_forever()
