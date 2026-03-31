"""
render_schedule.py — Schedule cards, task lists, print pages, today/week views.
Imports from: config, data_helpers, ui_helpers, render_calendar (for strip)
"""
import hashlib
from datetime import date, timedelta
from html import escape

from daily_schedule_engine import (
    CHILDREN, build_schedule_payload,
    generate_day_packet, generate_week_packet,
)

from config import child_color, WEEKDAYS
from data_helpers import (
    load_progress, count_school_check_items,
    normalize_date_query,
)
from ui_helpers import html_page, page_header
from render_daily_bar import render_daily_bar, render_child_age_strip


# ── Celebration messages ──────────────────────────────────────────────────────
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


# ── Task helpers ──────────────────────────────────────────────────────────────
def _item_done(item: dict, progress: dict) -> bool:
    tid = item.get("task_id", "")
    if tid and tid in progress:
        val = progress[tid]
        # progress[tid] may be a bool (legacy) or a dict {"done": bool}
        if isinstance(val, bool):
            return val
        if isinstance(val, dict):
            return bool(val.get("done", False))
        return bool(val)
    return bool(item.get("done", False))


def is_day_complete(payload: dict) -> bool:
    progress = load_progress()
    all_items = []
    for block in payload.get("school_blocks", []):
        all_items.extend(block.get("items", []))
    all_items.extend(payload.get("chore_items", []))
    all_items.extend(payload.get("manual_task_items", []))
    all_items.extend(payload.get("carryover_items", []))
    if not all_items:
        return False
    return all(_item_done(i, progress) for i in all_items)


def count_remaining(payload: dict) -> int:
    progress = load_progress()
    all_items = []
    for block in payload.get("school_blocks", []):
        all_items.extend(block.get("items", []))
    all_items.extend(payload.get("chore_items", []))
    all_items.extend(payload.get("manual_task_items", []))
    all_items.extend(payload.get("carryover_items", []))
    return sum(1 for i in all_items if not _item_done(i, progress))


def render_task_list(child: str, iso: str, items: list) -> str:
    if not items:
        return "<p class='muted'>None.</p>"
    progress = load_progress()
    html = ""
    for item in items:
        task_id  = item.get("task_id", "")
        is_done  = _item_done(item, progress)
        checked    = "checked" if is_done else ""
        done_class = "done"    if is_done else ""
        new_val    = "false"   if is_done else "true"
        tid_esc    = escape(task_id)
        label_id   = f"lbl-{tid_esc}"
        html += f"""
        <div class="task {done_class}" id="task-{tid_esc}">
            <input type="checkbox" id="{label_id}" {checked}
                   onchange="toggleTask(this,'{tid_esc}','{new_val}','/schedule/{escape(child)}?date={escape(iso)}')">
            <label for="{label_id}">{escape(item.get("text",""))}</label>
        </div>"""
    return html


def render_school_block(child: str, iso: str, block: dict) -> str:
    subject = escape(block.get("subject","") or "Untitled Subject")
    assignment_text = block.get("assignment_text","")
    assignment_html = f"<pre>{escape(assignment_text)}</pre>" if assignment_text else ""
    math_note = ""
    if block.get("is_math_test"):
        math_note = "<p><strong>TEST — bring to Mom for review</strong></p>"
    elif block.get("is_math"):
        math_note = "<p>Do all Lesson Practice and only the Mixed Practice from the last four lessons.</p>"
    return f"""
    <div class="subject-card">
        <h4>{subject}</h4>
        {math_note}{assignment_html}
        {render_task_list(child, iso, block.get("items",[]))}
    </div>"""


def render_confetti_celebration(child: str) -> str:
    c_bg   = child_color(child, "bg")
    c_text = child_color(child, "text")
    idx = int(hashlib.md5(child.encode()).hexdigest(), 16) % len(CELEBRATION_MESSAGES)
    msg = CELEBRATION_MESSAGES[idx]
    return f"""
    <div style="background:{c_bg};color:{c_text};border-radius:16px;padding:20px 24px;
                margin-bottom:18px;text-align:center;position:relative;overflow:hidden;">
        <div style="font-size:2em;margin-bottom:6px;">{msg}</div>
        <div style="font-size:1em;opacity:0.85;">Keep it up, {escape(child)}!</div>
        <canvas id="confetti-{child}" style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;"></canvas>
    </div>
    <script>
    (function(){{
        var canvas=document.getElementById('confetti-{child}');
        var ctx=canvas.getContext('2d');
        canvas.width=canvas.offsetWidth; canvas.height=canvas.offsetHeight;
        var pieces=[]; var colors=['{c_bg}','#f9ca24','#f0932b','#6ab04c','#e056fd','#22a6b3','#ffffff'];
        for(var i=0;i<80;i++){{pieces.push({{x:Math.random()*canvas.width,
            y:Math.random()*canvas.height-canvas.height,r:Math.random()*6+3,
            d:Math.random()*3+1,color:colors[Math.floor(Math.random()*colors.length)],
            tilt:Math.random()*10-5,tiltAngle:0,tiltSpeed:Math.random()*0.1+0.05}});}}
        var frame=0;
        function draw(){{ctx.clearRect(0,0,canvas.width,canvas.height);
            pieces.forEach(function(p){{ctx.beginPath();ctx.lineWidth=p.r;ctx.strokeStyle=p.color;
                ctx.moveTo(p.x+p.tilt+p.r/4,p.y);ctx.lineTo(p.x+p.tilt,p.y+p.tilt+p.r/4);ctx.stroke();}});update();}}
        function update(){{pieces.forEach(function(p){{p.tiltAngle+=p.tiltSpeed;
            p.y+=(Math.cos(frame/10)+p.d);p.x+=Math.sin(frame/10)*0.5;
            p.tilt=Math.sin(p.tiltAngle)*12;
            if(p.y>canvas.height){{p.y=-10;p.x=Math.random()*canvas.width;}}}});frame++;}}
        if(frame<300){{setInterval(draw,16);}}
    }})();
    </script>"""


def render_day_nav(base_url: str, iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except Exception:
        d = date.today()
    prev_iso      = (d - timedelta(days=1)).isoformat()
    next_iso      = (d + timedelta(days=1)).isoformat()
    today_iso_val = date.today().isoformat()
    today_style   = "opacity:0.4;pointer-events:none;" if iso == today_iso_val else ""
    _nav_date_label = escape(d.strftime("%A, %B %d"))
    return f"""
    <div style="display:flex;align-items:center;gap:8px;margin:6px 0;">
        <a class="link-button" href="{base_url}?date={prev_iso}" style="font-size:1.1em;padding:4px 12px;">‹</a>
        <a class="link-button" href="{base_url}?date={today_iso_val}" style="{today_style}">Today</a>
        <a class="link-button" href="{base_url}?date={next_iso}" style="font-size:1.1em;padding:4px 12px;">›</a>
        <span style="font-size:0.85em;color:#888;margin-left:4px;">{_nav_date_label}</span>
    </div>"""


def render_child_schedule_card(child: str, target_date_str: str = "") -> str:
    # These are imported here to avoid circular imports at module level
    from render_calendar import render_calendar_today_strip
    from render_schedule_support import render_now_next_strip

    normalized_date = normalize_date_query(target_date_str)
    packet  = generate_day_packet(normalized_date)
    iso     = packet["iso"]
    weekday = packet["weekday"]
    date_label = packet["date_label"]

    payload = build_schedule_payload(child, weekday, date_label, iso)
    merged_carryover = payload.get("carryover_items", [])

    school_html  = "".join(render_school_block(child, iso, b) for b in payload["school_blocks"])
    school_count = count_school_check_items(payload)
    chore_count  = len(payload.get("chore_items", []))
    carry_count  = len(merged_carryover)
    manual_count = len(payload.get("manual_task_items", []))

    c_bg    = child_color(child, "bg")
    c_light = child_color(child, "light")
    complete       = is_day_complete(payload)
    celebration_html = render_confetti_celebration(child) if complete else ""

    try:
        target_iso = date.fromisoformat(iso)
    except Exception:
        target_iso = date.today()
    age_strip = render_child_age_strip(child, target_iso)

    return f"""
    <div class="card" style="border-left:5px solid {c_bg};background:{c_light};">
        {celebration_html}
        {render_daily_bar(target_iso)}
        <div class="page-header">
            <h2 style="color:{c_bg};">{escape(child)} — {escape(date_label)}</h2>
            {f'<div style="margin-bottom:4px;">{age_strip}</div>' if age_strip else ""}
            <div class="no-print">{render_day_nav(f"/schedule/{child}", iso)}</div>
            <div class="summary-row">
                <span class="badge">Carryover: {carry_count}</span>
                <span class="badge">Manual: {manual_count}</span>
                <span class="badge">School checks: {school_count}</span>
                <span class="badge">Chores: {chore_count}</span>
            </div>
            <div class="link-row no-print">
                <a class="link-button" href="/print/day?date={escape(iso)}">Print This Day</a>
            </div>
            <div style="margin-top:8px;">{render_now_next_strip()}</div>
            <div style="margin-top:8px;">{render_calendar_today_strip(iso)}</div>
        </div>
        <div class="section-stack">
            <div class="card card-tight">
                <h3>Carryover</h3>{render_task_list(child, iso, merged_carryover)}
            </div>
            <div class="card card-tight">
                <h3>Manual Tasks</h3>{render_task_list(child, iso, payload["manual_task_items"])}
            </div>
            <div class="card card-tight">
                <h3>School</h3>{school_html or "<p class='muted'>None.</p>"}
            </div>
            <div class="card card-tight">
                <h3>Chores</h3>{render_task_list(child, iso, payload["chore_items"])}
            </div>
        </div>
    </div>"""


def render_child_schedule(child: str, target_date_str: str = "") -> str:
    normalized_date = normalize_date_query(target_date_str)
    body = f"{page_header(child)}{render_child_schedule_card(child, normalized_date)}"
    return html_page(child, body)


def render_today_all(target_date_str: str = "") -> str:
    normalized_date = normalize_date_query(target_date_str)
    try:
        target_iso = date.fromisoformat(normalized_date)
    except Exception:
        target_iso = date.today()
    bar  = render_daily_bar(target_iso)
    html = "".join(render_child_schedule_card(child, normalized_date) for child in CHILDREN)
    return html_page("Today", f"{page_header('Today')}{bar}{html}")


def render_week() -> str:
    week = generate_week_packet("")
    html = ""
    for day in week["days"]:
        wd  = day["weekday"]
        dl  = day["date_label"]
        iso = day["iso"]
        html += f"""
        <div class="card">
            <h2>{escape(wd)} — {escape(dl)}</h2>
            <div class="link-row no-print">
                <a class="link-button" href="/print/day?date={escape(iso)}">Print This Day</a>
            </div>
            <div class="grid">"""
        for child in CHILDREN:
            preview = day["schedules"][child][:300]
            html += f"""
            <div class="card card-tight">
                <h3>{escape(child)}</h3>
                <div class="link-row">
                    <a class="link-button" href="/schedule/{escape(child)}?date={escape(iso)}">Open This Day</a>
                </div>
                <pre>{escape(preview)}{"..." if len(day["schedules"][child])>300 else ""}</pre>
            </div>"""
        html += "</div></div>"
    return html_page("Week", f"{page_header('Week')}{html}")


# ── Print ─────────────────────────────────────────────────────────────────────
def print_page_html(title: str, body: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{escape(title)}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:Georgia,'Times New Roman',serif;font-size:13pt;color:#111;background:white;}}
  .child-page{{page-break-after:always;padding:0.6in 0.7in 0.5in;min-height:100vh;}}
  .child-page:last-child{{page-break-after:avoid;}}
  .page-header{{border-bottom:4px solid var(--child-color);padding-bottom:10px;margin-bottom:18px;}}
  .child-name{{font-size:28pt;font-weight:bold;color:var(--child-color);letter-spacing:1px;}}
  .date-line{{font-size:13pt;color:#555;margin-top:2px;}}
  .section-title{{font-size:11pt;font-weight:bold;text-transform:uppercase;letter-spacing:2px;color:#777;border-bottom:1px solid #ddd;padding-bottom:3px;margin:16px 0 8px;}}
  .subject-name{{font-size:14pt;font-weight:bold;color:#222;margin:12px 0 4px;}}
  .assignment-text{{font-size:11pt;color:#444;margin:0 0 6px 16px;line-height:1.5;white-space:pre-wrap;}}
  .math-note{{font-size:10.5pt;color:#555;font-style:italic;margin:0 0 6px 16px;}}
  .check-item{{display:flex;align-items:flex-start;gap:10px;margin:5px 0 5px 16px;font-size:12pt;line-height:1.4;}}
  .checkbox{{width:16px;height:16px;border:2px solid #555;border-radius:3px;flex-shrink:0;margin-top:2px;display:inline-block;}}
  .carryover-item{{display:flex;align-items:flex-start;gap:10px;margin:5px 0 5px 16px;font-size:12pt;color:#666;font-style:italic;}}
  .page-footer{{margin-top:24px;border-top:1px solid #ddd;padding-top:8px;font-size:9pt;color:#aaa;text-align:right;}}
  @media print{{body{{background:white;}}.no-print{{display:none!important;}}}}
  @media screen{{body{{background:#f0f0f0;}}.child-page{{background:white;margin:20px auto;max-width:8.5in;box-shadow:0 2px 8px rgba(0,0,0,0.15);}}}}
</style></head><body>
<div class="no-print" style="background:#333;color:white;padding:10px 20px;font-family:sans-serif;font-size:13px;">
    <button onclick="window.print()" style="background:#8b5a3c;color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;margin-right:12px;">🖨 Print</button>
    <a href="/" style="color:#ccc;">← Back to Dashboard</a>
</div>
{body}</body></html>"""


def render_print_child_page(child: str, weekday: str, date_label: str, iso: str) -> str:
    payload = build_schedule_payload(child, weekday, date_label, iso)
    c_color = child_color(child, "bg")

    try:
        target_iso = date.fromisoformat(iso)
    except Exception:
        target_iso = date.today()

    # Compact daily bar for print
    daily_bar = render_daily_bar(target_iso, compact=True)

    # Age strip
    age_strip = render_child_age_strip(child, target_iso)
    age_html  = f'<div style="font-size:9pt;color:#888;margin-top:3px;">{age_strip}</div>' if age_strip else ""
    sections_html = ""
    carryover = payload.get("carryover_items", [])
    if carryover:
        items = "".join(f'<div class="carryover-item"><span class="checkbox"></span>{escape(i["text"])}</div>' for i in carryover)
        sections_html += f'<div class="section-title">Carryover</div>{items}'
    manual = payload.get("manual_task_items", [])
    if manual:
        items = "".join(f'<div class="check-item"><span class="checkbox"></span>{escape(i["text"])}</div>' for i in manual)
        sections_html += f'<div class="section-title">Tasks</div>{items}'
    school_blocks = payload.get("school_blocks", [])
    if school_blocks:
        blocks_html = ""
        for block in school_blocks:
            subject = block.get("subject","")
            at      = block.get("assignment_text","")
            math_note = ""
            if block.get("is_math_test"):
                math_note = '<div class="math-note">TEST — bring to Mom for review</div>'
            elif block.get("is_math"):
                math_note = '<div class="math-note">Do all Lesson Practice and only the Mixed Practice from the last four lessons.</div>'
            checklist = "".join(f'<div class="check-item"><span class="checkbox"></span>{escape(i["text"])}</div>' for i in block.get("items",[]))
            at_html = f'<div class="assignment-text">{escape(at)}</div>' if at else ""
            blocks_html += f'<div class="subject-name">{escape(subject)}</div>{math_note}{at_html}{checklist}'
        sections_html += f'<div class="section-title">School</div>{blocks_html}'
    chores = payload.get("chore_items", [])
    if chores:
        items = "".join(f'<div class="check-item"><span class="checkbox"></span>{escape(i["text"])}</div>' for i in chores)
        sections_html += f'<div class="section-title">Chores</div>{items}'
    return f"""
    <div class="child-page" style="--child-color:{c_color};">
        {daily_bar}
        <div class="page-header">
            <div class="child-name">{escape(child)}</div>
            <div class="date-line">{escape(weekday)}, {escape(date_label)}</div>
            {age_html}
        </div>
        {sections_html or '<p style="color:#aaa;font-style:italic;">Nothing scheduled today.</p>'}
        <div class="page-footer">Family Planner · {escape(date_label)}</div>
    </div>"""


def render_print_day(target_date_str: str = "") -> str:
    normalized_date = normalize_date_query(target_date_str)
    packet     = generate_day_packet(normalized_date)
    weekday    = packet["weekday"]
    date_label = packet["date_label"]
    iso        = packet["iso"]
    pages = "".join(render_print_child_page(child, weekday, date_label, iso) for child in CHILDREN)
    return print_page_html(f"{weekday} — {date_label}", pages)


def render_print_week() -> str:
    week  = generate_week_packet("")
    pages = ""
    for day in week["days"]:
        for child in CHILDREN:
            pages += render_print_child_page(child, day["weekday"], day["date_label"], day["iso"])
    return print_page_html("Week Packet", pages)