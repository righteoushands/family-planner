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
    RULE_OF_LIFE_ANCHORS, fmt_time_12h,
    build_day_list, day_list_stats,
    get_calendar_events_for_boys,
)

from config import child_color, WEEKDAYS
from data_helpers import (
    load_progress, count_school_check_items,
    normalize_date_query, due_thankyou_reminders_for,
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


# ── Thank-you card POD strip ──────────────────────────────────────────────────
def _ty_pod_strip(due_list: list, accent: str = "#8b5a3c", return_url: str = "/today") -> str:
    """
    Compact inline strip shown inside a person's POD when they have due
    thank-you card reminders.  Each row has event name + quick Done button.
    """
    if not due_list:
        return ""
    rows = ""
    for r in due_list:
        rid   = escape(r.get("id", ""))
        ename = escape(r.get("event_name", ""))
        ppl   = escape(r.get("people", ""))
        rows += (
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'gap:8px;padding:4px 0;border-bottom:1px solid rgba(0,0,0,0.06);">'
            f'<div style="min-width:0;">'
            f'<div style="font-size:.82em;font-weight:600;color:#6b4f3a;white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis;">{ename}</div>'
            + (f'<div style="font-size:.72em;color:#9ca3af;">For: {ppl}</div>' if ppl else "")
            + f'</div>'
            f'<form method="POST" action="/thankyou-done" style="margin:0;flex-shrink:0;">'
            f'<input type="hidden" name="id" value="{rid}">'
            f'<input type="hidden" name="return_url" value="{escape(return_url)}">'
            f'<button type="submit"'
            f' style="background:#5a7a5a;color:white;border:none;border-radius:6px;'
            f'padding:3px 10px;font-size:.75em;cursor:pointer;white-space:nowrap;">'
            f'&#10003; Sent</button>'
            f'</form>'
            f'</div>'
        )
    n    = len(due_list)
    lbl  = "thank-you card" if n == 1 else "thank-you cards"
    return (
        f'<div style="background:#fef3e2;border:1px solid #e8c97a;border-radius:8px;'
        f'padding:8px 10px;margin-top:8px;">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'margin-bottom:4px;">'
        f'<span style="font-size:.72em;font-weight:800;letter-spacing:.06em;'
        f'text-transform:uppercase;color:#92400e;">&#9993; {n} {lbl} due</span>'
        f'<a href="/thankyou-reminders" style="font-size:.7em;color:#8b5a3c;'
        f'text-decoration:none;white-space:nowrap;">Manage →</a>'
        f'</div>'
        f'{rows}'
        f'</div>'
    )


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
        tid_js     = escape(task_id, quote=False).replace("'", "\\'")
        label_id   = f"lbl-{tid_esc}"
        html += f"""
        <div class="task {done_class}" id="task-{tid_esc}">
            <input type="checkbox" id="{label_id}" {checked}
                   onchange="toggleTask(this,'{tid_js}','/schedule/{escape(child)}?date={escape(iso)}')">
            <label for="{label_id}">{escape(item.get("text",""))}</label>
        </div>"""
    return html


def _latin_week_from_text(assignment_text: str) -> int:
    """Extract the 'Week: N' number from a Latin assignment text. Returns 0 if not found."""
    import re as _re
    m = _re.search(r'Week:\s*(\d+)', assignment_text or "")
    return int(m.group(1)) if m else 0


def render_school_block(child: str, iso: str, block: dict) -> str:
    subject = escape(block.get("subject","") or "Untitled Subject")
    assignment_text = block.get("assignment_text","")
    assignment_html = f"<pre>{escape(assignment_text)}</pre>" if assignment_text else ""
    math_note = ""
    if block.get("is_math_test"):
        math_note = "<p><strong>TEST — bring to Mom for review</strong></p>"
    elif block.get("is_math"):
        math_note = "<p>Do all Lesson Practice and only the Mixed Practice from the last four lessons.</p>"

    # ── Latin notes ───────────────────────────────────────────────────────────
    latin_note = ""
    _raw_subject = (block.get("subject") or "").lower()
    if "latin" in _raw_subject:
        _latin_week = _latin_week_from_text(block.get("assignment_text", ""))
        # Joseph: show whenever Latin appears (week 0 = week unknown → still show)
        # JP: show only while current week ≤ 25
        _show = False
        if child == "Joseph":
            _show = True
        elif child in ("JP", "John Paul"):
            _show = (_latin_week == 0 or _latin_week <= 25)

        if _show:
            # JP note is the same curriculum reminder; tailor for who is reading it
            if child == "Joseph":
                _note_body = (
                    "Continue your Latin <strong>assignments</strong> until you finish <strong>Week 25</strong>. "
                    "Continue Latin <strong>quizzes</strong> until you earn <strong>85% or better</strong> "
                    "(all quizzes through Week 25). Mom will let you know what comes next."
                )
            else:
                _note_body = (
                    "Continue Latin <strong>assignments and quizzes</strong> through <strong>Week 25</strong>. "
                    "Quizzes: aim for <strong>85% or better</strong>. Mom will follow up once you reach Week 25."
                )
            latin_note = (
                f'<div style="background:#fffbeb;border-left:3px solid #d97706;border-radius:6px;'
                f'padding:8px 12px;margin:6px 0;font-size:.88em;color:#78350f;line-height:1.5;">'
                f'📌 {_note_body}</div>'
            )

    return f"""
    <div class="subject-card">
        <h4>{subject}</h4>
        {math_note}{latin_note}{assignment_html}
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
    base_esc      = escape(base_url, quote=False)
    return f"""
    <div style="display:flex;align-items:center;gap:8px;margin:6px 0;flex-wrap:wrap;">
        <a class="link-button" href="{base_url}?date={prev_iso}" style="font-size:1.1em;padding:4px 12px;">&#8249;</a>
        <a class="link-button" href="{base_url}?date={today_iso_val}" style="{today_style}">Today</a>
        <a class="link-button" href="{base_url}?date={next_iso}" style="font-size:1.1em;padding:4px 12px;">&#8250;</a>
        <input type="date" value="{iso}"
               onchange="window.location.href='{base_esc}?date='+this.value"
               style="font-size:0.82em;padding:4px 8px;border:1px solid #d1d5db;border-radius:8px;
                      background:#fff;color:#333;cursor:pointer;max-width:140px;">
    </div>"""


def _render_schedule_events_section(cal_items: list) -> str:
    """Render a 'Today's Events' card for the full schedule page. Hidden if no events."""
    if not cal_items:
        return ""
    rows = ""
    for ev in cal_items:
        tl    = fmt_time_12h(ev["time"]) if ev["time"] else "All day"
        loc   = f'<span style="color:#6b7280;"> · {escape(ev["location"])}</span>' if ev.get("location") else ""
        rows += (
            f'<div style="display:flex;align-items:baseline;gap:10px;'
            f'padding:6px 0;border-bottom:1px solid #ede9fe;">'
            f'<span style="font-size:.78em;font-weight:700;color:#7c3aed;'
            f'min-width:68px;flex-shrink:0;">{escape(tl)}</span>'
            f'<span style="font-size:.9em;color:#1e1b4b;">{escape(ev["title"])}{loc}</span>'
            f'</div>'
        )
    return (
        f'<div class="card card-tight" style="border-left:4px solid #7c3aed;background:#faf5ff;">'
        f'<h3 style="color:#7c3aed;margin-bottom:8px;">📅 Today\'s Events</h3>'
        f'{rows}'
        f'</div>'
    )


# ── Day List rendering helpers ────────────────────────────────────────────────

_DL_KIND_COLORS = {
    "wakeup":   "#aaaaaa",
    "prayer":   "#c8a42a",
    "mass":     "#4a1a6e",
    "meal":     "#8b3a5c",
    "cook":     "#c25c1a",
    "exercise": "#1a6e3e",
    "school":   "#1e3566",
    "chore":    "#8b3a1a",
    "task":     "#5b3a8a",
    "routine":  "#666666",
    "free":     "#cccccc",
}

_DL_KIND_LABELS = {
    "wakeup":   "☀",
    "prayer":   "✝",
    "mass":     "✝",
    "meal":     "🍽",
    "cook":     "🍳",
    "exercise": "💪",
    "school":   "📚",
    "chore":    "🧹",
    "task":     "✓",
    "routine":  "•",
    "free":     "◦",
}

_DL_CSS = """<style>
.day-list{display:flex;flex-direction:column;gap:0;}
.dl-block{border-radius:6px;overflow:hidden;margin-bottom:4px;}
.dl-header-row{display:flex;align-items:center;gap:8px;padding:6px 10px;background:rgba(0,0,0,0.03);}
.dl-row{display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:6px;margin-bottom:3px;}
.dl-row.dl-info{opacity:.7;}
.dl-time{font-size:.72em;font-weight:700;letter-spacing:.03em;color:#888;white-space:nowrap;min-width:80px;}
.dl-kind-icon{font-size:.85em;min-width:16px;text-align:center;}
.dl-label{flex:1;font-size:.9em;line-height:1.3;font-weight:500;}
.dl-label.done{opacity:.45;text-decoration:line-through;}
.dl-check{display:flex;align-items:center;}
.dl-subitems{padding:2px 10px 6px 26px;display:flex;flex-direction:column;gap:3px;}
.dl-sub-row{display:flex;align-items:flex-start;gap:7px;padding:3px 0;}
.dl-sub-header{font-size:.72em;font-weight:800;letter-spacing:.07em;text-transform:uppercase;
               color:#888;padding:5px 0 2px;margin-top:3px;}
.dl-sub-label{flex:1;font-size:.85em;line-height:1.35;}
.dl-sub-label.done{opacity:.45;text-decoration:line-through;}
.dl-carry-badge{font-size:.7em;background:#f59e0b;color:#fff;border-radius:3px;
                padding:1px 4px;margin-right:4px;font-weight:700;}
.dl-progress-bar{height:4px;border-radius:2px;background:#e5e7eb;margin-bottom:12px;}
.dl-progress-fill{height:100%;border-radius:2px;transition:width .3s;}
.task-ov-btn{background:none;border:none;color:#bbb;cursor:pointer;padding:0 3px;
             font-size:.8em;opacity:0;transition:opacity .15s;line-height:1;}
.dl-row:hover .task-ov-btn{opacity:1;}
.task-ov-panel{display:none;flex-wrap:wrap;align-items:center;gap:6px;
               padding:6px 12px 8px 28px;background:#f8f4ef;
               border-top:1px solid #e5ddd4;margin-bottom:3px;border-radius:0 0 6px 6px;}
.task-ov-panel button{background:#fff;border:1.5px solid #c5b9a8;border-radius:6px;
                      padding:5px 10px;font-size:.78em;cursor:pointer;color:#5a3d26;}
.task-ov-panel button:hover{background:#ede6dc;}
.tov-dismiss{border-color:#d4756b!important;color:#a33!important;}
.tov-dismiss:hover{background:#fde8e8!important;}
.tov-time-row{display:flex;align-items:center;gap:4px;font-size:.82em;}
.tov-time-row input[type=time]{border:1.5px solid #c5b9a8;border-radius:5px;
                                padding:4px 5px;font-size:.85em;color:#3d2b1f;}
.tov-close{background:none!important;border:none!important;color:#aaa!important;
           padding:0 3px!important;font-size:.85em!important;}
@media print {
  .dl-row,.dl-block{break-inside:avoid;}
  .dl-time{color:#555;}
  .no-print{display:none!important;}
}
</style>"""


def _dl_kind_color(kind: str) -> str:
    return _DL_KIND_COLORS.get(kind, "#888888")


def _get_poetry_passage(child: str) -> dict:
    """Return {title, text} for this child's current memorization passage, or {}."""
    try:
        from render_week_school import load_poetry_passages
        return load_poetry_passages().get(child, {})
    except Exception:
        return {}


def _dl_sub_items_html(sub_items: list, c_id: str, iso: str, c_bg: str,
                       child: str = "", _day_ovs: dict = None) -> str:
    _day_ovs   = _day_ovs or {}
    _child_esc = escape(child)
    _iso_esc   = escape(iso)
    rows = []
    _poetry_passage_injected = False   # only inject once per block
    for sub in sub_items:
        if sub.get("is_header"):
            rows.append(
                f'<div class="dl-sub-header">{escape(sub.get("text",""))}</div>'
            )
        elif sub.get("checkable") and sub.get("task_id"):
            raw_tid = sub["task_id"]
            tid     = escape(raw_tid)
            tid_j   = raw_tid.replace("'", "\\'")
            # Check for override on this sub-item
            _ov      = _day_ovs.get(raw_tid, {})
            _ov_act  = _ov.get("action", "")
            if _ov_act == "dismiss":
                continue   # skip dismissed sub-items
            done  = sub.get("done", False)
            chk   = "checked" if done else ""
            dst   = "done" if done else ""
            dnv   = "1" if done else "0"
            carry = '<span class="dl-carry-badge">↩</span>' if sub.get("is_carryover") else ""
            # Due-soon badge
            due_badge = ""
            if sub.get("is_due_soon") and sub.get("due_date"):
                try:
                    from datetime import date as _d2
                    _due_d = _d2.fromisoformat(sub["due_date"])
                    _days_away = (_due_d - _d2.today()).days
                    if _days_away == 0:
                        _due_lbl = "due today"
                    elif _days_away == 1:
                        _due_lbl = "due tomorrow"
                    else:
                        _due_lbl = f"due {_due_d.strftime('%a')}"
                    due_badge = (
                        f'<span style="font-size:.72em;font-weight:700;'
                        f'color:#f59e0b;background:#fffbeb;border:1px solid #fde68a;'
                        f'border-radius:4px;padding:1px 5px;margin-left:6px;white-space:nowrap;">'
                        f'{escape(_due_lbl)}</span>'
                    )
                except Exception:
                    pass
            # Timed override badge
            _time_badge = ""
            if _ov_act == "timed" and _ov.get("time"):
                _t = _ov["time"]
                _time_badge = (
                    f'<span style="font-size:.68em;font-weight:700;color:#0369a1;'
                    f'background:#eff6ff;border-radius:4px;padding:1px 5px;margin-right:4px;'
                    f'white-space:nowrap;cursor:pointer;" '
                    f'onclick="_tovClear(\'{tid_j}\',\'{c_id}\',\'{escape(iso)}\')" '
                    f'title="Clear time">⏰ {_t} ×</span>'
                )
            _lbl_raw = sub.get("text", "")
            _lbl_js  = _lbl_raw.replace("'", "\\'").replace('"', '\\"')
            try:
                from datetime import date as _d3, timedelta as _td3
                _tmr = (_d3.fromisoformat(iso) + _td3(days=1)).isoformat()
            except Exception:
                _tmr = ""
            row_html = (
                f'<div class="dl-sub-row" id="task-{tid}"'
                f' data-dash-child="{c_id}" data-done="{dnv}">'
                f'{_time_badge}'
                f'<input type="checkbox" {chk}'
                f' style="width:15px;height:15px;flex-shrink:0;margin-top:2px;accent-color:{c_bg};"'
                f' onchange="toggleDashTask(this,\'{tid_j}\',\'{c_id}\',\'{escape(iso)}\')">'
                f'<span class="dl-sub-label {dst}">{carry}{escape(_lbl_raw)}{due_badge}</span>'
                f'</div>'
            )
            tray_html = (
                f'<div class="sw-del sw-ov-tray no-print">'
                f'<button class="sw-ov-btn sw-ov-dismiss" '
                f'onclick="_tovAct(\'{tid_j}\',\'{c_id}\',\'{escape(iso)}\',\'{_lbl_js}\',\'dismiss\')">'
                f'&#10005; Dismiss</button>'
                f'<button class="sw-ov-btn sw-ov-tmr" '
                f'onclick="_tovAct(\'{tid_j}\',\'{c_id}\',\'{escape(iso)}\',\'{_lbl_js}\',\'postpone\',\'{_tmr}\')">'
                f'&#8594; Tomorrow</button>'
                f'<button class="sw-ov-btn sw-ov-time" '
                f'onclick="_tovTimePrompt(\'{tid_j}\',\'{c_id}\',\'{escape(iso)}\',\'{_lbl_js}\')">'
                f'&#9200; Time</button>'
                f'<button class="sw-ov-btn sw-ov-hide" onclick="_swDel(this)">'
                f'&#8942; Hide</button>'
                f'</div>'
            )
            rows.append(
                f'<div class="sw-wrap" data-child="{_child_esc}" data-iso="{_iso_esc}">'
                f'<div class="sw-inner">{row_html}</div>'
                f'{tray_html}'
                f'</div>'
            )
            # If this is a poetry memorization step, inject the saved passage once
            task_id  = raw_tid
            text_low = sub.get("text", "").lower()
            is_poetry_memorize = (
                "poetry" in task_id.lower() and
                "memorize" in text_low and
                not _poetry_passage_injected and
                child
            )
            if is_poetry_memorize:
                passage = _get_poetry_passage(child)
                if passage.get("text"):
                    _poetry_passage_injected = True
                    p_title = escape(passage.get("title", ""))
                    p_text  = escape(passage.get("text", ""))
                    title_html = (
                        f'<div style="font-size:.72em;font-weight:700;color:#7c3aed;'
                        f'margin-bottom:4px;">{p_title}</div>'
                        if p_title else ""
                    )
                    p_text_html = p_text.replace("&#10;", "<br>").replace("\n", "<br>")
                    rows.append(
                        f'<div style="margin:5px 0 3px 22px;padding:8px 12px;'
                        f'background:#faf5ff;border-left:3px solid #7c3aed;'
                        f'border-radius:0 6px 6px 0;">'
                        f'{title_html}'
                        f'<div style="font-family:Georgia,serif;font-size:.82em;'
                        f'line-height:1.6;color:#4a1a6e;white-space:pre-wrap;">'
                        f'{p_text_html}</div></div>'
                    )
        else:
            rows.append(
                f'<div class="dl-sub-row" style="padding-left:22px;">'
                f'<span class="dl-sub-label" style="opacity:.7;">'
                f'{escape(sub.get("text",""))}</span></div>'
            )
    return "".join(rows)


def _render_day_list_html(day_list: list, child: str, iso: str,
                           c_bg: str, meals: dict = None) -> str:
    c_id = child.lower().replace(" ", "-")
    # Load any dismiss/postpone/timed overrides for this person on this day
    try:
        from data_helpers import get_day_overrides as _gdo
        _day_ovs = _gdo(child, iso)
    except Exception:
        _day_ovs = {}
    _meal_slot_map = {
        "breakfast": "breakfast", "brunch": "breakfast",
        "lunch": "lunch", "dinner": "dinner", "snack": "snacks", "snacks": "snacks",
    }
    rows = []
    rows_del = []   # parallel — None means use default "Hide" button
    seen_sub_texts: set = set()   # dedup: tracks sub-item texts already rendered
    seen_single_labels: set = set()  # dedup: tracks single-row labels already rendered
    for item in day_list:
        kind  = item.get("kind", "routine")
        color = _dl_kind_color(kind)
        icon  = _DL_KIND_LABELS.get(kind, "•")
        t_st  = item.get("time", "")
        t_en  = item.get("end_time", "")
        t_disp = f"{t_st} – {t_en}" if t_en and t_en != t_st else t_st
        label  = escape(item.get("label", ""))
        subs   = item.get("sub_items", [])
        # Deduplicate sub-items against texts already rendered in earlier blocks
        if subs:
            deduped_subs = []
            for s in subs:
                if s.get("is_header"):
                    deduped_subs.append(s)
                    continue
                txt_key = (s.get("text") or "").strip().lower()
                if txt_key and txt_key in seen_sub_texts:
                    continue  # skip — already shown in a previous block
                deduped_subs.append(s)
                if txt_key:
                    seen_sub_texts.add(txt_key)
            subs = deduped_subs

        # ── Calendar event row ───────────────────────────────────────────────
        if kind == "event":
            ev_id  = item.get("event_id", "")
            is_man = item.get("event_calendar", "") == "Manual"
            del_btn = ""
            if is_man and ev_id:
                ev_id_esc = escape(ev_id)
                iso_esc   = escape(iso)
                ch_esc    = escape(child)
                del_btn = (
                    f'<form method="POST" action="/calendar-event-delete"'
                    f' style="display:inline;margin-left:auto;">'
                    f'<input type="hidden" name="id" value="{ev_id_esc}">'
                    f'<input type="hidden" name="return_url"'
                    f' value="/schedule/{ch_esc}?date={iso_esc}">'
                    f'<button type="submit" title="Delete event"'
                    f' style="background:none;border:none;color:#ccc;cursor:pointer;'
                    f'font-size:.85em;padding:0 4px;line-height:1;">&times;</button>'
                    f'</form>'
                )
            rows.append(
                f'<div class="dl-row" style="border-left:3px solid #7c3aed;">'
                f'<span class="dl-time">{t_disp}</span>'
                f'<span class="dl-kind-icon">&#128197;</span>'
                f'<span class="dl-label" style="color:#7c3aed;flex:1;">{label}</span>'
                f'{del_btn}'
                f'</div>'
            )
            rows_del.append(None)
            continue

        if subs:
            # Expanded block — header row + sub-items
            checkable_subs = [s for s in subs if s.get("checkable") and not s.get("is_header")]
            done_cnt = sum(1 for s in checkable_subs if s.get("done"))
            tot_cnt  = len(checkable_subs)
            prog_label = f" ({done_cnt}/{tot_cnt})" if tot_cnt else ""
            rows.append(
                f'<div class="dl-block" style="border-left:3px solid {color};">'
                f'<div class="dl-header-row">'
                f'<span class="dl-time">{t_disp}</span>'
                f'<span class="dl-kind-icon">{icon}</span>'
                f'<span class="dl-label" style="color:{color};font-weight:700;">'
                f'{label}<span style="font-weight:400;font-size:.85em;color:#999;">'
                f'{prog_label}</span></span>'
                f'</div>'
                f'<div class="dl-subitems">'
                f'{_dl_sub_items_html(subs, c_id, iso, c_bg, child, _day_ovs)}'
                f'</div></div>'
            )
            rows_del.append(False)  # expanded blocks: no outer sw-wrap (sub-items have their own)
        elif item.get("task_id") and item.get("checkable"):
            # Single-checkbox item — apply any override
            raw_tid = item["task_id"]
            tid  = escape(raw_tid)
            tidj = raw_tid.replace("'", "\\'")
            _ov = _day_ovs.get(raw_tid, {})
            _ov_act = _ov.get("action", "")
            # Skip dismissed items entirely
            if _ov_act == "dismiss":
                continue
            # Timed override: update time display
            if _ov_act == "timed" and _ov.get("time"):
                t_disp = _ov["time"]
            done = item.get("done", False)
            chk  = "checked" if done else ""
            dst  = "done" if done else ""
            dnv  = "1" if done else "0"
            # Build tomorrow ISO for postpone button
            try:
                from datetime import date as _d, timedelta as _td2
                _tmr = (_d.fromisoformat(iso) + _td2(days=1)).isoformat()
            except Exception:
                _tmr = ""
            _lbl_raw = item.get("label", "")
            _lbl_js  = _lbl_raw.replace("'", "\\'").replace('"', '\\"')
            _ov_indicator = ""
            if _ov_act == "timed":
                _ov_indicator = (
                    f' <span style="font-size:.7em;color:#b45309;cursor:pointer;" '
                    f'onclick="_tovClear(\'{tidj}\',\'{c_id}\',\'{escape(iso)}\')"'
                    f' title="Clear time override">⏰×</span>'
                )
            _time_val = t_disp if len(t_disp) == 5 else ""
            rows.append(
                f'<div class="dl-row" style="border-left:3px solid {color};"'
                f' id="task-{tid}" data-dash-child="{c_id}" data-done="{dnv}">'
                f'<span class="dl-time">{t_disp}</span>'
                f'<span class="dl-kind-icon">{icon}</span>'
                f'<span class="dl-label {dst}">{label}{_ov_indicator}</span>'
                f'<div class="dl-check">'
                f'<input type="checkbox" {chk}'
                f' style="width:16px;height:16px;accent-color:{c_bg};"'
                f' onchange="toggleDashTask(this,\'{tidj}\',\'{c_id}\',\'{escape(iso)}\')">'
                f'</div></div>'
            )
            rows_del.append(
                f'<div class="sw-del sw-ov-tray no-print">'
                f'<button class="sw-ov-btn sw-ov-dismiss" '
                f'onclick="_tovAct(\'{tidj}\',\'{c_id}\',\'{escape(iso)}\',\'{_lbl_js}\',\'dismiss\')">'
                f'&#10005; Dismiss</button>'
                f'<button class="sw-ov-btn sw-ov-tmr" '
                f'onclick="_tovAct(\'{tidj}\',\'{c_id}\',\'{escape(iso)}\',\'{_lbl_js}\',\'postpone\',\'{_tmr}\')">'
                f'&#8594; Tomorrow</button>'
                f'<button class="sw-ov-btn sw-ov-time" '
                f'onclick="_tovTimePrompt(\'{tidj}\',\'{c_id}\',\'{escape(iso)}\',\'{_lbl_js}\')">'
                f'&#9200; Time</button>'
                f'<button class="sw-ov-btn sw-ov-hide" onclick="_swDel(this)">'
                f'&#8942; Hide</button>'
                f'</div>'
            )
        else:
            # Informational / free / meal slot
            # For meal slots: inject the menu if available
            meal_note = ""
            if kind == "meal" and meals:
                label_low = item.get("label", "").lower()
                for keyword, slot_key in _meal_slot_map.items():
                    if keyword in label_low:
                        meal_text = (meals.get(slot_key) or "").strip()
                        if meal_text:
                            meal_note = (
                                f'<span style="font-size:.75em;color:#8b3a5c;'
                                f'margin-left:6px;font-style:italic;">'
                                f'&#8212; {escape(meal_text)}</span>'
                            )
                        break
            lbl_color = "#999" if kind in ("free", "wakeup") else color
            rows.append(
                f'<div class="dl-row dl-info" style="border-left:3px solid {color};">'
                f'<span class="dl-time">{t_disp}</span>'
                f'<span class="dl-kind-icon">{icon}</span>'
                f'<span class="dl-label" style="color:{lbl_color};">{label}{meal_note}</span>'
                f'</div>'
            )
            rows_del.append(None)
    _child_esc = escape(child)
    _iso_esc   = escape(iso)
    _std_del   = '<button class="sw-del no-print" onclick="_swDel(this)" aria-label="Hide">&#10005; Hide</button>'
    wrapped = []
    for r, d in zip(rows, rows_del):
        if d is False:
            # Expanded blocks: render raw — sub-items have their own sw-wrap
            wrapped.append(r)
        else:
            wrapped.append(
                f'<div class="sw-wrap" data-child="{_child_esc}" data-iso="{_iso_esc}">'
                '<button class="sw-add no-print" onclick="_swAdd(this)" aria-label="Add task below">+ Add</button>'
                '<div class="sw-inner">' + r + '</div>'
                + (d if d is not None else _std_del) +
                '</div>'
            )
    return "".join(wrapped)


def _render_template_editor(child: str, weekday: str, c_bg: str) -> str:
    """Collapsible in-page editor for a child's Rule of Life time slots on a given weekday."""
    import json as _json
    from pathlib import Path as _Path

    tmpl_path = _Path(f"data/day_templates/{weekday}.json")
    try:
        tmpl = _json.loads(tmpl_path.read_text(encoding="utf-8"))
        grid = tmpl.get("grid", {})
        child_slots = dict(grid.get(child, {}))
    except Exception:
        child_slots = {}

    # Sort by time
    def _sort_key(ts):
        try:
            from datetime import datetime as _dt
            return _dt.strptime(ts.strip(), "%I:%M %p").strftime("%H:%M")
        except Exception:
            return ts
    sorted_slots = sorted(child_slots.items(), key=lambda kv: _sort_key(kv[0]))

    slot_rows = ""
    for i, (ts, lbl) in enumerate(sorted_slots):
        ts_esc  = escape(ts)
        lbl_esc = escape(lbl)
        slot_rows += (
            f'<div class="tmpl-row" id="tmpl-row-{i}">'
            f'<input name="slot_time_{i}" value="{ts_esc}" placeholder="9:00 AM"'
            f' style="width:95px;font-size:.82em;padding:4px 6px;border:1px solid #ddd;border-radius:6px;">'
            f'<input name="slot_label_{i}" value="{lbl_esc}" placeholder="Label"'
            f' style="flex:1;font-size:.82em;padding:4px 6px;border:1px solid #ddd;border-radius:6px;">'
            f'<button type="button" onclick="this.closest(\'.tmpl-row\').remove();_tmplRecount()"'
            f' style="background:none;border:none;color:#ccc;cursor:pointer;font-size:1em;'
            f'padding:2px 6px;">&times;</button>'
            f'</div>'
        )

    n = len(sorted_slots)
    child_esc   = escape(child)
    weekday_esc = escape(weekday)
    editor_id   = f"tmpl-editor-{escape(child).lower()}"
    return f"""
<style>
#{editor_id}{{display:none;}}
#{editor_id}.open{{display:block;}}
.tmpl-row{{display:flex;align-items:center;gap:6px;margin-bottom:6px;}}
</style>
<div id="{editor_id}" class="card card-tight no-print"
     style="border-left:4px solid {c_bg};margin-top:8px;">
  <h3 style="color:{c_bg};margin-bottom:10px;">&#9965; Edit {child_esc}'s {weekday_esc} Template</h3>
  <form method="POST" action="/schedule-template-save" id="tmpl-form-{child_esc.lower()}">
    <input type="hidden" name="child"   value="{child_esc}">
    <input type="hidden" name="weekday" value="{weekday_esc}">
    <input type="hidden" name="slot_count" id="tmpl-count-{child_esc.lower()}" value="{n}">
    <div id="tmpl-rows-{child_esc.lower()}">
      {slot_rows}
    </div>
    <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">
      <button type="button"
              onclick="_tmplAddRow('{child_esc.lower()}')"
              style="font-size:.82em;padding:5px 14px;background:#f3f4f6;border:1px solid #ddd;
                     border-radius:8px;cursor:pointer;">+ Add Slot</button>
      <button type="submit"
              style="font-size:.82em;padding:5px 14px;background:{c_bg};color:#fff;
                     border:none;border-radius:8px;cursor:pointer;font-weight:700;">
        &#10003; Save to Template</button>
    </div>
  </form>
</div>
<script>
function _tmplRecount(){{
  var rows=document.querySelectorAll('.tmpl-row');
  rows.forEach(function(r,i){{
    r.querySelectorAll('input').forEach(function(inp){{
      var nm=inp.name;
      if(nm.startsWith('slot_time_')||nm.startsWith('slot_label_')){{
        inp.name=nm.replace(/\\d+$/,i);
      }}
    }});
  }});
  var cc=document.querySelector('[id^="tmpl-count-"]');
  if(cc)cc.value=rows.length;
}}
function _tmplAddRow(childKey){{
  var cont=document.getElementById('tmpl-rows-'+childKey);
  var n=cont.querySelectorAll('.tmpl-row').length;
  var d=document.createElement('div');
  d.className='tmpl-row';
  d.id='tmpl-row-'+n;
  d.innerHTML='<input name="slot_time_'+n+'" value="" placeholder="9:00 AM"'
    +' style="width:95px;font-size:.82em;padding:4px 6px;border:1px solid #ddd;border-radius:6px;">'
    +'<input name="slot_label_'+n+'" value="" placeholder="Label"'
    +' style="flex:1;font-size:.82em;padding:4px 6px;border:1px solid #ddd;border-radius:6px;">'
    +'<button type="button" onclick="this.closest(\\'.tmpl-row\\').remove();_tmplRecount()"'
    +' style="background:none;border:none;color:#ccc;cursor:pointer;font-size:1em;padding:2px 6px;">&times;</button>';
  cont.appendChild(d);
  var cc=document.querySelector('[id^="tmpl-count-"]');
  if(cc)cc.value=n+1;
}}
</script>"""


def render_child_schedule_card(child: str, target_date_str: str = "") -> str:
    from render_calendar import render_calendar_today_strip
    from render_schedule_support import render_now_next_strip

    normalized_date = normalize_date_query(target_date_str)
    packet     = generate_day_packet(normalized_date)
    iso        = packet["iso"]
    weekday    = packet["weekday"]
    date_label = packet["date_label"]

    # Build the Day List (Rule-of-Life-anchored chronological schedule)
    day_list = build_day_list(child, weekday, iso)

    # Load calendar events and merge into the Day List chronologically
    try:
        cal_items = get_calendar_events_for_boys(iso)
    except Exception:
        cal_items = []
    for ev in cal_items:
        ev_time    = ev.get("time")          # "HH:MM" or None
        time_sort  = ev_time or "00:00"      # all-day events sort to top
        from daily_schedule_engine import fmt_time_12h as _fmt12
        disp_time  = _fmt12(ev_time) if ev_time else "All day"
        loc        = ev.get("location", "")
        lbl        = ev["title"] + (f" \u2022 {loc}" if loc else "")
        day_list.append({
            "time":      disp_time,
            "time_sort": time_sort,
            "end_time":  _fmt12(ev.get("end_time")) if ev.get("end_time") else disp_time,
            "label":     lbl,
            "kind":      "event",
            "checkable": False,
            "task_id":   None,
            "done":      False,
            "sub_items": [],
            "is_event":  True,
            "event_id":  ev.get("id", ""),
            "event_calendar": ev.get("calendar", ""),
        })
    day_list.sort(key=lambda x: x.get("time_sort", "00:00"))

    stats    = day_list_stats(day_list)
    total    = stats["total"]
    done_cnt = stats["done"]
    pct      = stats["pct"]

    # Load meal plan for inline display
    meals = {}
    try:
        from render_meals import load_meal_plan, _week_key
        from datetime import date as _date2
        _td = _date2.fromisoformat(iso)
        _plan = load_meal_plan(_week_key(_td))
        meals = _plan.get("days", {}).get(weekday, {})
    except Exception:
        meals = {}

    c_bg    = child_color(child, "bg")
    c_light = child_color(child, "light")

    try:
        target_iso = date.fromisoformat(iso)
    except Exception:
        target_iso = date.today()

    age_strip = render_child_age_strip(child, target_iso)
    bar_col   = "#22c55e" if pct == 100 else ("#f59e0b" if pct >= 50 else c_bg)
    all_done  = total > 0 and pct == 100
    celebration_html = render_confetti_celebration(child) if all_done else ""

    day_list_html = _render_day_list_html(day_list, child, iso, c_bg, meals)
    template_html = _render_template_editor(child, weekday, c_bg)

    return f"""{_DL_CSS}
    <div class="card" style="border-left:5px solid {c_bg};background:{c_light};">
        {celebration_html}
        {render_daily_bar(target_iso)}
        <div class="page-header">
            <h2 style="color:{c_bg};">{escape(child)}'s Day — {escape(date_label)}</h2>
            {f'<div style="margin-bottom:4px;">{age_strip}</div>' if age_strip else ""}
            <div class="no-print">{render_day_nav(f"/schedule/{child}", iso)}</div>
            <div class="dl-progress-bar no-print">
                <div class="dl-progress-fill"
                     style="width:{pct}%;background:{bar_col};"></div>
            </div>
            <div class="summary-row no-print">
                <span class="badge" style="background:{bar_col};color:#fff;">
                    {done_cnt}/{total} done
                </span>
                <span class="badge">{escape(weekday)}</span>
            </div>
            <div class="link-row no-print">
                <a class="link-button" href="/print/day/{escape(child)}?date={escape(iso)}">Print Day List</a>
                <button onclick="document.getElementById('tmpl-editor-{escape(child).lower()}').classList.toggle('open')"
                        class="link-button" style="background:{c_bg};color:#fff;">&#9965; Edit Template</button>
                {(
                    f'<a class="link-button" href="/quest-sso"'
                    f' style="background:#7c3aed;color:#fff;">&#9876; Family Quest</a>'
                ) if child in ("JP", "Joseph", "Michael", "James") else ""}
            </div>
            <div style="margin-top:8px;">{render_now_next_strip()}</div>
            <div style="margin-top:8px;">{render_calendar_today_strip(iso)}</div>
        </div>
        <div class="card card-tight no-print" id="lucy-child-panel-{child.lower()}"
             style="border-left:4px solid {c_bg};background:{c_light};margin-bottom:8px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                <span style="font-size:1em;">&#10022;</span>
                <span style="font-size:.85em;font-weight:700;color:{c_bg};">
                    Lucy's notes for {escape(child)}</span>
            </div>
            <div id="lucy-child-brief-{child.lower()}"
                 style="font-size:.85em;line-height:1.55;color:#444;min-height:32px;">
                <span style="color:#bbb;font-style:italic;">Loading&#8230;</span>
            </div>
        </div>
        <div class="day-list">
            {day_list_html}
        </div>
        {_render_child_goals_section(child)}
        {_render_child_profile_section(child, c_bg, c_light)}
        {template_html}
    </div>
<script>
/* Hide tasks already marked done on page load so they don't reappear as visible checked items */
(function() {{
    document.querySelectorAll('[data-done="1"]').forEach(function(row) {{
        row.style.display = 'none';
    }});
}})();
(function() {{
    var el = document.getElementById('lucy-child-brief-{child.lower()}');
    if (!el) return;
    fetch('/lucy-child-brief/{child.lower()}')
        .then(function(r) {{ return r.json(); }})
        .then(function(d) {{
            el.innerHTML = d.html ||
                '<span style="color:#bbb;font-style:italic;">Not available.</span>';
        }})
        .catch(function() {{
            el.innerHTML =
                "<span style='color:#bbb;font-style:italic;'>Could not load.</span>";
        }});
}})();
/* Live progress sync: keeps this page in step with other open pages */
(function() {{
    var _iso = '{escape(iso)}';
    function _syncPlan() {{
        fetch('/api/today-progress?date=' + _iso)
            .then(function(r) {{ return r.ok ? r.json() : null; }})
            .then(function(data) {{
                if (!data) return;
                document.querySelectorAll('[id^="task-"]').forEach(function(row) {{
                    var tid    = row.id.replace(/^task-/, '');
                    var isDone = data[tid] === true;
                    var wasDone= row.getAttribute('data-done') === '1';
                    if (isDone === wasDone) return;
                    var cb  = row.querySelector('input[type="checkbox"]');
                    var lbl = row.querySelector('label,.dl-sub-label,.dl-label');
                    if (isDone) {{
                        row.setAttribute('data-done','1');
                        row.classList.add('done');
                        if (cb) cb.checked = true;
                        if (lbl) {{ lbl.style.opacity='0.4';lbl.style.textDecoration='line-through'; }}
                    }} else {{
                        row.setAttribute('data-done','0');
                        row.classList.remove('done');
                        if (cb) cb.checked = false;
                        if (lbl) {{ lbl.style.opacity='1';lbl.style.textDecoration='none'; }}
                    }}
                }});
            }}).catch(function() {{}});
    }}
    setInterval(_syncPlan, 15000);
}})();
</script>"""


def _render_meal_card_for_child(target_date=None) -> str:
    try:
        from render_meals import render_meal_today_card
        return render_meal_today_card(target_date)
    except Exception:
        return ""


def _render_child_goals_section(child: str) -> str:
    """Render the goals section for a child's page (imported here to avoid circular imports)."""
    try:
        from render_child_goals import render_child_goals_section
        return render_child_goals_section(child)
    except Exception:
        return ""


def _render_child_profile_section(child: str, c_bg: str, c_light: str) -> str:
    """Render the editable profile card for a child's page."""
    try:
        from render_child_profile import render_child_profile_section
        return render_child_profile_section(child, c_bg, c_light)
    except Exception:
        return ""


def render_child_schedule(child: str, target_date_str: str = "") -> str:
    normalized_date = normalize_date_query(target_date_str)
    body = f"{page_header(child)}{render_child_schedule_card(child, normalized_date)}{_DASH_JS}"
    return html_page(child, body)


def render_child_dash_card(child: str, target_date_str: str = "") -> str:
    """
    Compact dashboard card — uses build_day_list (same source as the full Day
    List page) so task IDs are identical and check-offs synchronise instantly.
    Shows: carryover ↩, then school/manual tasks (2-at-a-time), then chores.
    """
    normalized_date = normalize_date_query(target_date_str)
    packet     = generate_day_packet(normalized_date)
    iso        = packet["iso"]
    weekday    = packet["weekday"]
    date_label = packet["date_label"]

    day_list = build_day_list(child, weekday, iso)

    # Merge calendar events into the day list (same approach as schedule page)
    try:
        from daily_schedule_engine import get_calendar_events_for_boys as _gcal, fmt_time_12h as _fmt12
        for _ev in _gcal(iso):
            _ev_time   = _ev.get("time")
            _time_sort = _ev_time or "00:00"
            _disp_time = _fmt12(_ev_time) if _ev_time else "All day"
            _loc       = _ev.get("location", "")
            _lbl       = _ev["title"] + (f" \u2022 {_loc}" if _loc else "")
            day_list.append({
                "time":      _disp_time,
                "time_sort": _time_sort,
                "end_time":  _fmt12(_ev.get("end_time")) if _ev.get("end_time") else _disp_time,
                "label":     _lbl,
                "kind":      "event",
                "checkable": False,
                "task_id":   None,
                "done":      False,
                "sub_items": [],
                "is_event":  True,
            })
    except Exception:
        pass

    progress = load_progress()

    c_bg    = child_color(child, "bg")
    c_light = child_color(child, "light")
    c_id    = child.lower().replace(" ", "-")

    # ── Extract task groups from the Day List ──────────────────────────────
    carryover:  list = []   # sub_items from "task" block with CARRY:: IDs
    queue:      list = []   # school steps + manual tasks (non-carry)
    chore_items:list = []   # flat list of all chore sub_items

    # Calendar events from day_list blocks (kind="event")
    cal_events: list = []

    _dash_seen_texts: set = set()  # dedup across all blocks on the dash card
    for blk in day_list:
        kind  = blk.get("kind", "")
        subs  = blk.get("sub_items") or []

        if kind == "event" or blk.get("is_event"):
            cal_events.append(blk)
            continue

        if kind == "task":
            # sub_items are carry-over tasks and/or manual tasks
            for sub in subs:
                if not isinstance(sub, dict):
                    continue
                if sub.get("is_header"):
                    continue
                txt_key = (sub.get("text") or "").strip().lower()
                if txt_key and txt_key in _dash_seen_texts:
                    continue
                if txt_key:
                    _dash_seen_texts.add(txt_key)
                tid = sub.get("task_id", "")
                if tid.startswith("CARRY::"):
                    carryover.append(sub)
                else:
                    queue.append(dict(sub, _section="Task"))

        elif kind == "school":
            # sub_items are individual school steps; label is the subject block
            subj = blk.get("label", "School")
            for sub in subs:
                if not isinstance(sub, dict) or sub.get("is_header"):
                    continue
                txt_key = (sub.get("text") or "").strip().lower()
                if txt_key and txt_key in _dash_seen_texts:
                    continue
                if txt_key:
                    _dash_seen_texts.add(txt_key)
                queue.append(dict(sub, _section=subj, _time_sort=blk.get("time_sort", "10:00")))

        elif kind == "chore":
            for sub in subs:
                if not isinstance(sub, dict) or sub.get("is_header"):
                    continue
                if sub.get("task_id"):
                    txt_key = (sub.get("text") or "").strip().lower()
                    if txt_key and txt_key in _dash_seen_texts:
                        continue
                    if txt_key:
                        _dash_seen_texts.add(txt_key)
                    chore_items.append(sub)

    # ── Counts ─────────────────────────────────────────────────────────────
    all_tasks  = carryover + queue + chore_items
    total      = len(all_tasks)
    done_cnt   = sum(1 for i in all_tasks if _item_done(i, progress))
    remaining  = total - done_cnt
    pct        = round(done_cnt / total * 100) if total else 0
    all_done   = total > 0 and done_cnt == total
    bar_col    = "#22c55e" if all_done else ("#f59e0b" if pct >= 50 else c_bg)

    def _dash_row(item, extra_style="", is_chore=False, section=""):
        tid     = escape(item.get("task_id", ""))
        tid_js  = escape(item.get("task_id", ""), quote=False).replace("'", "\\'")
        is_done = _item_done(item, progress)
        checked = "checked" if is_done else ""
        done_st = "opacity:.5;text-decoration:line-through;" if is_done else ""
        done_d  = "1" if is_done else "0"
        sec     = section or item.get("_section", "")
        sec_div = (
            f'<div style="font-size:.62em;font-weight:800;letter-spacing:.07em;'
            f'text-transform:uppercase;color:{c_bg};margin-bottom:1px;">{escape(sec)}</div>'
            if sec else ""
        )
        chore_attr = ' data-chore="1"' if is_chore else ""
        lbl_text = item.get("text") or item.get("label") or ""
        return (
            f'<div class="dash-task" data-dash-child="{c_id}" data-done="{done_d}"{chore_attr}'
            f' id="task-{tid}" style="display:flex;align-items:flex-start;gap:8px;'
            f'padding:5px 0;border-bottom:1px solid rgba(0,0,0,0.05);{extra_style}">'
            f'<input type="checkbox" id="lbl-{tid}" {checked}'
            f' style="margin-top:3px;width:16px;height:16px;flex-shrink:0;accent-color:{c_bg};"'
            f' onchange="toggleDashTask(this,\'{tid_js}\',\'{c_id}\',\'{escape(iso)}\')">'
            f'<div style="flex:1;min-width:0;">'
            f'{sec_div}'
            f'<label for="lbl-{tid}" style="font-size:.88em;line-height:1.3;'
            f'cursor:pointer;{done_st}">{escape(lbl_text)}</label>'
            f'</div></div>'
        )

    # ── Carryover rows (up to 3; extras linked) ─────────────────────────────
    _CARRY_MAX = 3
    carry_html = ""
    if carryover:
        carry_html = (
            f'<div style="font-size:0.65em;font-weight:800;letter-spacing:.08em;'
            f'text-transform:uppercase;color:#a07040;margin:8px 0 3px;">↩ Carryover</div>'
        )
        for item in carryover[:_CARRY_MAX]:
            carry_html += _dash_row(item)
        _carry_extra = len(carryover) - _CARRY_MAX
        if _carry_extra > 0:
            carry_html += (
                f'<div style="font-size:.75em;color:#a07040;padding:3px 0 4px;">'
                f'<a href="/schedule/{escape(child)}?date={escape(iso)}"'
                f' style="color:#a07040;text-decoration:none;">+{_carry_extra} more →</a>'
                f'</div>'
            )

    # ── Calendar event rows ──────────────────────────────────────────────────
    def _event_row(blk):
        tl  = blk.get("time", "All day")
        loc_raw = blk.get("label", "")
        # strip the " • location" suffix from the label if present
        title = blk.get("label", "")
        loc   = ""
        if " \u2022 " in title:
            title, loc = title.split(" \u2022 ", 1)
        loc_html = f' · <em>{escape(loc)}</em>' if loc else ""
        return (
            f'<div style="display:flex;align-items:center;gap:8px;'
            f'padding:5px 0;border-bottom:1px solid rgba(0,0,0,0.05);">'
            f'<span style="font-size:.9em;flex-shrink:0;margin-top:1px;">📅</span>'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-size:.62em;font-weight:800;letter-spacing:.07em;'
            f'text-transform:uppercase;color:#7c3aed;margin-bottom:1px;">'
            f'{escape(tl)}</div>'
            f'<div style="font-size:.88em;line-height:1.3;color:#1e1b4b;">'
            f'{escape(title)}{loc_html}</div>'
            f'</div></div>'
        )

    # ── Combined chronological list ──────────────────────────────────────────
    combined = []
    for blk in cal_events:
        combined.append({"kind": "event", "sort_time": blk.get("time_sort", "00:00"), "data": blk})
    for item in queue:
        t = item.get("_time_sort") or RULE_OF_LIFE_ANCHORS.get("school", "10:00")
        combined.append({"kind": "task",  "sort_time": t, "data": item})
    for item in chore_items:
        combined.append({"kind": "chore", "sort_time": RULE_OF_LIFE_ANCHORS.get("chore", "07:30"), "data": item})
    combined.sort(key=lambda x: x["sort_time"])

    # ── Render combined (2-at-a-time reveal for tasks; chores always shown) ──
    combined_html = ""
    pending_shown = 0
    chore_done    = sum(1 for i in chore_items if _item_done(i, progress))
    chore_shown   = False

    for entry in combined:
        kind = entry["kind"]
        if kind == "event":
            combined_html += _event_row(entry["data"])

        elif kind == "task":
            item    = entry["data"]
            is_done = _item_done(item, progress)
            if is_done:
                vis = "display:none;"
            elif pending_shown < 2:
                vis = ""; pending_shown += 1
            else:
                vis = "display:none;"
            combined_html += _dash_row(item, extra_style=vis,
                                       section=item.get("_section", ""))

        elif kind == "chore":
            if not chore_shown and chore_items:
                chore_lbl = f"{chore_done}/{len(chore_items)}"
                combined_html += (
                    f'<div id="dash-chore-hdr-{c_id}"'
                    f' style="font-size:0.65em;font-weight:800;letter-spacing:.08em;'
                    f'text-transform:uppercase;color:{c_bg};margin:10px 0 3px;">'
                    f'Chores <span id="dash-chore-cnt-{c_id}"'
                    f' style="font-weight:500;color:#888;">({chore_lbl})</span></div>'
                )
                chore_shown = True
            combined_html += _dash_row(entry["data"], is_chore=True)

    all_done_badge = (
        '<div style="color:#166534;font-weight:700;font-size:.85em;background:#dcfce7;'
        'padding:6px 12px;border-radius:8px;margin:4px 0;">✓ All done today!</div>'
        if all_done else ""
    )

    return (
        f'<div class="card" id="dash-card-{c_id}"'
        f' style="border-left:4px solid {c_bg};background:{c_light};'
        f'margin-bottom:10px;padding:12px 14px;">'

        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">'
        f'<a href="/schedule/{escape(child)}?date={escape(iso)}"'
        f' style="font-weight:700;color:{c_bg};font-size:1.05em;text-decoration:none;">'
        f'{escape(child)}</a>'
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'<span id="dash-count-{c_id}" style="font-size:.75em;color:#888;">'
        f'{"✓ done" if all_done else str(remaining)+" left"}</span>'
        f'<a href="/schedule/{escape(child)}?date={escape(iso)}"'
        f' style="font-size:.72em;color:var(--brown);font-weight:600;white-space:nowrap;">'
        f'Full list →</a>'
        f'</div></div>'

        f'<div style="height:4px;background:#e0d8d0;border-radius:2px;margin-bottom:8px;">'
        f'<div id="dash-bar-{c_id}" style="height:100%;width:{pct}%;'
        f'background:{bar_col};border-radius:2px;transition:width .3s;"></div></div>'

        f'{all_done_badge}'
        f'{carry_html}'
        f'<div id="dash-queue-{c_id}">{combined_html}</div>'
        + _ty_pod_strip(due_thankyou_reminders_for(child), c_bg, "/today")
        + f'</div>'
    )


_DASH_JS = """
<script>
/* Hide tasks already marked done so they don't reappear as visible checked items on reload */
(function() {
    document.querySelectorAll('[data-done="1"]').forEach(function(row) {
        row.style.display = 'none';
    });
    /* Inject undo snackbar once */
    if (!document.getElementById('undo-snack')) {
        var s = document.createElement('div');
        s.id = 'undo-snack';
        s.innerHTML = '<span id="undo-snack-label" style="flex:1;font-size:.88em;overflow:hidden;'
            + 'white-space:nowrap;text-overflow:ellipsis;"></span>'
            + '<button onclick="_undoCheck()" style="background:rgba(255,255,255,.18);border:none;'
            + 'color:#fff;font-weight:700;border-radius:6px;padding:5px 12px;cursor:pointer;'
            + 'font-size:.85em;white-space:nowrap;font-family:inherit;flex-shrink:0;">Undo</button>';
        s.style.cssText = 'display:none;position:fixed;bottom:28px;left:50%;'
            + 'transform:translateX(-50%);background:#1e293b;color:#fff;border-radius:12px;'
            + 'padding:12px 10px 12px 16px;display:none;align-items:center;gap:12px;z-index:9999;'
            + 'box-shadow:0 4px 24px rgba(0,0,0,.35);transition:opacity .25s;'
            + 'min-width:220px;max-width:88vw;';
        document.body.appendChild(s);
    }
})();
var _undoTask = null;
function _showUndoSnack(cb, tid, childId, iso, row, isChore) {
    /* If a previous undo is pending, commit it (hide old row now) */
    if (_undoTask) {
        clearTimeout(_undoTask.timer);
        if (_undoTask.row) { _undoTask.row.style.display = 'none'; }
        _undoTask = null;
    }
    var snack = document.getElementById('undo-snack');
    if (!snack) return;
    var lbl = row ? row.querySelector('.dl-label,.dl-sub-label,label') : null;
    var txt  = lbl ? lbl.textContent.trim().slice(0, 35) : 'Task';
    var el = document.getElementById('undo-snack-label');
    if (el) el.textContent = '\u2713 ' + txt;
    snack.style.display = 'flex';
    snack.style.opacity = '1';
    var timer = setTimeout(function() {
        /* Time up — commit: hide the row for real */
        if (row) {
            row.style.transition = 'opacity .25s';
            row.style.opacity    = '0';
            setTimeout(function() { row.style.display = 'none'; }, 260);
        }
        snack.style.opacity = '0';
        setTimeout(function() { snack.style.display = 'none'; }, 280);
        _undoTask = null;
    }, 4500);
    _undoTask = {cb:cb, tid:tid, childId:childId, iso:iso, row:row, isChore:isChore, timer:timer};
}
function _undoCheck() {
    if (!_undoTask) return;
    clearTimeout(_undoTask.timer);
    var t = _undoTask; _undoTask = null;
    /* Restore checkbox and row */
    t.cb.checked = false;
    if (t.row) {
        t.row.setAttribute('data-done', '0');
        t.row.style.display    = '';
        t.row.style.opacity    = '1';
        t.row.style.transition = '';
        var lbl = t.row.querySelector('.dl-label,.dl-sub-label,label');
        if (lbl) { lbl.style.opacity = '1'; lbl.style.textDecoration = 'none'; }
    }
    var snack = document.getElementById('undo-snack');
    if (snack) { snack.style.opacity='0'; setTimeout(function(){ snack.style.display='none'; },280); }
    /* Revert on server */
    fetch('/toggle-task', {
        method:'POST',
        headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body:'task_id='+encodeURIComponent(t.tid)+'&new_value=false&return_url='
             +encodeURIComponent('/today?date='+t.iso)
    }).then(function() { _dashUpdateProgress(t.childId); });
}
function toggleDashTask(cb, tid, childId, iso) {
    var row     = document.getElementById('task-' + tid);
    var isDone  = cb.checked;
    var newVal  = isDone ? 'true' : 'false';
    var isChore = row && row.getAttribute('data-chore') === '1';
    if (row) {
        row.setAttribute('data-done', isDone ? '1' : '0');
        var lbl = row.querySelector('label, .dl-sub-label, .dl-label');
        if (lbl) {
            lbl.style.opacity        = isDone ? '0.4' : '1';
            lbl.style.textDecoration = isDone ? 'line-through' : 'none';
        }
        if (!isDone) {
            row.style.display    = '';
            row.style.opacity    = '1';
            row.style.transition = '';
        }
    }
    /* On check: show undo snack for 4.5s before hiding the row */
    if (isDone) { _showUndoSnack(cb, tid, childId, iso, row, isChore); }
    fetch('/toggle-task', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'task_id=' + encodeURIComponent(tid) +
              '&new_value=' + encodeURIComponent(newVal) +
              '&return_url=' + encodeURIComponent('/today?date=' + iso)
    }).then(function(r) {
        if (!r.ok) {
            cb.checked = !cb.checked;
            if (row) {
                row.setAttribute('data-done', isDone ? '0' : '1');
                row.style.display    = '';
                row.style.opacity    = '1';
                row.style.transition = '';
            }
        } else {
            _dashUpdateProgress(childId);
            if (isDone && !isChore) {
                setTimeout(function() { _dashAdvance(childId); }, 600);
            }
            _dashMaybeHideChoreHeader(childId);
        }
    }).catch(function() {
        cb.checked = !cb.checked;
        if (row) {
            row.setAttribute('data-done', isDone ? '0' : '1');
            row.style.display    = '';
            row.style.opacity    = '1';
            row.style.transition = '';
        }
    });
}

function _dashAdvance(childId) {
    /* Show the next hidden-but-pending task in the queue */
    var queue = document.getElementById('dash-queue-' + childId);
    if (!queue) return;
    var tasks = queue.querySelectorAll('.dash-task[data-dash-child="' + childId + '"]');
    for (var i = 0; i < tasks.length; i++) {
        var t = tasks[i];
        if (t.getAttribute('data-done') === '0' && t.getAttribute('data-chore') !== '1'
                && (t.style.display === 'none' || t.style.opacity === '0')) {
            t.style.display    = '';
            t.style.opacity    = '1';
            t.style.transition = '';
            break;
        }
    }
}

function _dashMaybeHideChoreHeader(childId) {
    var card = document.getElementById('dash-card-' + childId);
    if (!card) return;
    var chores  = card.querySelectorAll('.dash-task[data-chore="1"]');
    var hdr     = document.getElementById('dash-chore-hdr-' + childId);
    var cntEl   = document.getElementById('dash-chore-cnt-' + childId);
    var total   = chores.length, done = 0;
    for (var i = 0; i < chores.length; i++) {
        if (chores[i].getAttribute('data-done') === '1') done++;
    }
    if (cntEl) cntEl.textContent = '(' + done + '/' + total + ')';
    if (hdr && done === total && total > 0) {
        hdr.style.transition = 'opacity .3s';
        hdr.style.opacity    = '0';
        setTimeout(function() { hdr.style.display = 'none'; }, 320);
    }
}

function _dashUpdateProgress(childId) {
    var card = document.getElementById('dash-card-' + childId);
    if (!card) return;
    var all  = card.querySelectorAll('.dash-task');
    var tot  = all.length, done = 0;
    for (var i = 0; i < all.length; i++) {
        if (all[i].getAttribute('data-done') === '1') done++;
    }
    var pct = tot > 0 ? Math.round(done / tot * 100) : 0;
    var bar = document.getElementById('dash-bar-' + childId);
    if (bar) {
        bar.style.width      = pct + '%';
        bar.style.background = pct === 100 ? '#22c55e' : pct >= 50 ? '#f59e0b' : bar.style.background;
    }
    var cnt = document.getElementById('dash-count-' + childId);
    if (cnt) cnt.textContent = pct === 100 ? '\\u2713 done' : (tot - done) + ' left';
}

/* ── Task Overrides (dismiss / postpone / set time) ──────────────────── */
function _tovToggle(id) {
    document.querySelectorAll('.task-ov-panel').forEach(function(p) {
        if (p.id !== 'tov-' + id) p.style.display = 'none';
    });
    var el = document.getElementById('tov-' + id);
    if (el) el.style.display = el.style.display === 'none' ? 'flex' : 'none';
}
function _tovClose(id) {
    var el = document.getElementById('tov-' + id);
    if (el) el.style.display = 'none';
}
function _tovAct(tid, child, iso, label, action, postponeTo) {
    var fd = new FormData();
    fd.append('task_id', tid); fd.append('child', child);
    fd.append('iso', iso);     fd.append('label', label);
    fd.append('action', action); fd.append('json', '1');
    if (postponeTo) fd.append('postpone_to', postponeTo);
    fetch('/task-override', {method:'POST', body:fd}).then(function() { location.reload(); });
}
function _tovActTime(tid, child, iso, label) {
    var t = document.getElementById('tov-t-' + tid);
    if (!t || !t.value) return;
    var fd = new FormData();
    fd.append('task_id', tid); fd.append('child', child);
    fd.append('iso', iso);     fd.append('label', label);
    fd.append('action', 'timed'); fd.append('time', t.value); fd.append('json', '1');
    fetch('/task-override', {method:'POST', body:fd}).then(function() { location.reload(); });
}
function _tovClear(tid, child, iso) {
    var fd = new FormData();
    fd.append('task_id', tid); fd.append('child', child);
    fd.append('iso', iso);     fd.append('action', 'clear'); fd.append('json', '1');
    fetch('/task-override', {method:'POST', body:fd}).then(function() { location.reload(); });
}
var _tovTimeCtx = {};
function _tovTimePrompt(tid, child, iso, label) {
    _tovTimeCtx = {tid:tid, child:child, iso:iso, label:label};
    var m = document.getElementById('tov-time-modal');
    if (!m) return;
    var inp = document.getElementById('tov-time-input');
    if (inp) {
        var now = new Date();
        inp.value = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');
    }
    m.classList.add('open');
}
function _tovTimeModalCancel() {
    var m = document.getElementById('tov-time-modal');
    if (m) m.classList.remove('open');
}
function _tovTimeModalConfirm() {
    var inp = document.getElementById('tov-time-input');
    if (!inp || !inp.value) return;
    var fd = new FormData();
    fd.append('task_id', _tovTimeCtx.tid); fd.append('child', _tovTimeCtx.child);
    fd.append('iso', _tovTimeCtx.iso);     fd.append('label', _tovTimeCtx.label);
    fd.append('action', 'timed'); fd.append('time', inp.value); fd.append('json', '1');
    fetch('/task-override', {method:'POST', body:fd}).then(function() { location.reload(); });
}
// Inject time-picker modal once into DOM
(function(){
  if (document.getElementById('tov-time-modal')) return;
  var m = document.createElement('div');
  m.id = 'tov-time-modal';
  m.innerHTML = '<div class="tov-tm-box">'
    + '<div class="tov-tm-title">&#9200; Set task time</div>'
    + '<input id="tov-time-input" type="time">'
    + '<div class="tov-tm-btns">'
    + '<button class="tov-tm-cancel" onclick="_tovTimeModalCancel()">Cancel</button>'
    + '<button class="tov-tm-confirm" onclick="_tovTimeModalConfirm()">Set Time</button>'
    + '</div></div>';
  m.addEventListener('click', function(e){ if(e.target===m) _tovTimeModalCancel(); });
  document.body.appendChild(m);
})();
</script>"""


def render_today_all(target_date_str: str = "") -> str:
    normalized_date = normalize_date_query(target_date_str)
    try:
        target_iso = date.fromisoformat(normalized_date)
    except Exception:
        target_iso = date.today()

    bar       = render_daily_bar(target_iso)
    day_nav   = render_day_nav("/today", normalized_date)
    cards_html = "".join(
        render_child_dash_card(child, normalized_date) for child in CHILDREN
    )

    # "What's happening now" quick strip
    try:
        from render_schedule_support import get_current_slot
        from data_helpers import load_family_schedule
        _sched = load_family_schedule()
        _cur_label, _now_label, _next_label, _next_act = get_current_slot(_sched)
    except Exception:
        _now_label = ""

    now_strip = (
        f'<div style="background:var(--gold-light);border:1px solid var(--border);'
        f'border-radius:10px;padding:8px 14px;margin-bottom:12px;'
        f'font-size:.85em;font-weight:600;color:var(--ink);">'
        f'🕐 Now: {escape(_now_label)}'
        f'&nbsp;&nbsp;<a href="/now" style="font-size:.78em;font-weight:400;'
        f'color:var(--brown);">Family view →</a></div>'
        if _now_label else
        f'<div style="text-align:right;margin-bottom:8px;">'
        f'<a href="/now" style="font-size:.78em;color:var(--brown);">Family now →</a></div>'
    )

    # School mode banner
    school_banner = ""
    try:
        from render_settings import load_app_settings as _las
        _fc   = _las().get("family_constraints", {})
        _sm   = _fc.get("school_mode", "normal")
        if _sm == "light_week":
            _core = _fc.get("core_subjects", "Math, Religion, Reading")
            school_banner = (
                f'<div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:10px;'
                f'padding:9px 14px;margin-bottom:12px;display:flex;align-items:center;'
                f'justify-content:space-between;gap:12px;">'
                f'<span style="font-size:.85em;font-weight:600;color:#92400e;">'
                f'📚 Light week — showing: {escape(_core)}</span>'
                f'<a href="/set-school-mode?mode=normal" style="font-size:.75em;'
                f'color:#b45309;font-weight:700;white-space:nowrap;text-decoration:none;">'
                f'Back to normal ×</a>'
                f'</div>'
            )
        elif _sm == "custom_pause":
            _paused = _fc.get("paused_subjects", "")
            school_banner = (
                f'<div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:10px;'
                f'padding:9px 14px;margin-bottom:12px;display:flex;align-items:center;'
                f'justify-content:space-between;gap:12px;">'
                f'<span style="font-size:.85em;font-weight:600;color:#92400e;">'
                f'⏸ Paused: {escape(_paused)}</span>'
                f'<a href="/set-school-mode?mode=normal" style="font-size:.75em;'
                f'color:#b45309;font-weight:700;white-space:nowrap;text-decoration:none;">'
                f'Resume all ×</a>'
                f'</div>'
            )
    except Exception:
        pass

    _family_ty_strip = _ty_pod_strip(due_thankyou_reminders_for("Family"), "#8b5a3c", "/today")

    # Lauren's cycle fertility warning — shown on the dashboard for her awareness
    try:
        from render_mom_profile import _cycle_fertility_banner as _cfb
        _cycle_warn = _cfb(normalized_date)
    except Exception:
        _cycle_warn = ""

    body = (
        f'{page_header("Today")}'
        f'{bar}'
        f'{day_nav}'
        f'{now_strip}'
        f'{school_banner}'
        f'{_cycle_warn}'
        f'{_family_ty_strip}'
        f'{cards_html}'
        f'{_DASH_JS}'
    )
    return html_page("Today", body)


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
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:'Helvetica Neue',Arial,sans-serif;font-size:10pt;color:#111;background:white;}}
  .child-page{{page-break-after:always;padding:0.5in 0.6in 0.4in;min-height:100vh;}}
  .child-page:last-child{{page-break-after:avoid;}}
  .page-header{{border-bottom:2px solid var(--child-color);padding-bottom:6px;margin-bottom:10px;}}
  .child-name{{font-size:18pt;font-weight:700;color:var(--child-color);}}
  .date-line{{font-size:8.5pt;color:#666;margin-top:1px;}}
  .page-footer{{margin-top:16px;border-top:1px solid #e0e0e0;padding-top:4px;font-size:7pt;color:#bbb;text-align:right;}}
  /* Block header: just a colored left rule, no background band */
  .blk-header{{display:flex;align-items:baseline;gap:8px;border-left:3px solid var(--blk-color,#333);padding:5px 0 3px 8px;margin:10px 0 0;}}
  .blk-time{{font-size:7.5pt;color:#aaa;min-width:60px;white-space:nowrap;flex-shrink:0;}}
  .blk-label{{font-size:10.5pt;font-weight:700;color:var(--blk-color,#222);}}
  .blk-count{{font-size:7pt;color:#bbb;margin-left:3px;}}
  /* Sub-items: clearly indented under the block header */
  .sub-sect{{font-size:7pt;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
             color:#bbb;margin:4px 0 1px 72px;}}
  .sub-item{{display:flex;align-items:flex-start;gap:7px;padding:3px 0 3px 72px;
             font-size:9.5pt;line-height:1.45;color:#222;border-bottom:1px solid #f0f0f0;}}
  .sub-box{{width:12px;height:12px;border:1.5px solid #888;border-radius:2px;
            flex-shrink:0;display:inline-block;margin-top:2px;}}
  .sub-note{{padding-left:84px;font-size:8pt;color:#999;margin:1px 0;font-style:italic;}}
  /* Info-only rows (meals, breaks) — clearly secondary */
  .info-row{{display:flex;align-items:baseline;gap:8px;padding:2px 0 2px 8px;
             margin:4px 0;color:#999;}}
  .info-time{{font-size:7.5pt;min-width:60px;white-space:nowrap;flex-shrink:0;}}
  .info-label{{font-size:8.5pt;font-style:italic;}}
  @media print{{
    body{{background:white;font-size:10pt;}}
    .no-print{{display:none!important;}}
    .sub-item{{border-bottom:none;}}
  }}
  @media screen{{
    body{{background:#d0d0d0;}}
    .child-page{{background:white;margin:0 auto;max-width:8.5in;
      box-shadow:0 2px 12px rgba(0,0,0,0.2);}}
  }}
  @media screen and (max-width:700px){{
    body{{font-size:14px;}}
    .child-page{{padding:20px 18px 24px;box-shadow:none;margin:0;}}
    .child-name{{font-size:24px;}}
    .date-line{{font-size:13px;}}
    .blk-header{{padding:6px 0 4px 10px;margin:14px 0 0;}}
    .blk-time{{font-size:11px;min-width:72px;}}
    .blk-label{{font-size:15px;}}
    .blk-count{{font-size:11px;}}
    .sub-item{{padding:5px 0 5px 82px;font-size:13px;}}
    .sub-box{{width:14px;height:14px;margin-top:3px;}}
    .sub-sect{{margin-left:82px;font-size:10px;}}
    .sub-note{{padding-left:96px;font-size:11px;}}
    .info-row{{padding:3px 0 3px 10px;margin:5px 0;}}
    .info-time{{font-size:11px;min-width:72px;}}
    .info-label{{font-size:13px;}}
  }}
</style></head><body>
<div class="no-print" style="background:#2a2a2a;color:white;padding:10px 18px;font-family:sans-serif;font-size:13px;display:flex;align-items:center;gap:14px;">
    <button onclick="setTimeout(function(){{window.print();}},100)" style="background:#8b5a3c;color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;">🖨 Print</button>
    <span style="color:#aaa;font-size:11px;">On iPhone: tap the Share button ↑ then "Print"</span>
    <a href="/" style="color:#aaa;margin-left:auto;font-size:12px;">← Dashboard</a>
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
    _pr_chores  = payload.get("chore_items", [])
    _pr_manual  = payload.get("manual_task_items", [])
    _pr_ctexts  = {i.get("text", "").lower().strip() for i in _pr_chores}
    _pr_mdeduped = [i for i in _pr_manual if i.get("text", "").lower().strip() not in _pr_ctexts]
    _pr_combined = _pr_mdeduped + _pr_chores
    if _pr_combined:
        items = "".join(f'<div class="check-item"><span class="checkbox"></span>{escape(i["text"])}</div>' for i in _pr_combined)
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
            # Latin note (print view)
            _print_latin_note = ""
            if "latin" in subject.lower():
                _plw = _latin_week_from_text(at)
                _pshow = False
                if child == "Joseph":
                    _pshow = True
                elif child in ("JP", "John Paul"):
                    _pshow = (_plw == 0 or _plw <= 25)
                if _pshow:
                    if child == "Joseph":
                        _pnb = "Continue Latin assignments through Week 25. Quizzes: 85% or better through Week 25. Mom will let you know what comes next."
                    else:
                        _pnb = "Continue Latin assignments and quizzes through Week 25. Quizzes: 85% or better. Mom will follow up once you reach Week 25."
                    _print_latin_note = f'<div class="math-note">📌 {_pnb}</div>'
            checklist = "".join(f'<div class="check-item"><span class="checkbox"></span>{escape(i["text"])}</div>' for i in block.get("items",[]))
            at_html = f'<div class="assignment-text">{escape(at)}</div>' if at else ""
            blocks_html += f'<div class="subject-name">{escape(subject)}</div>{math_note}{_print_latin_note}{at_html}{checklist}'
        sections_html += f'<div class="section-title">School</div>{blocks_html}'

    # Meals section for print
    meal_print_html = _render_meal_print_section(target_iso, weekday)

    return f"""
    <div class="child-page" style="--child-color:{c_color};">
        {daily_bar}
        <div class="page-header">
            <div class="child-name">{escape(child)}</div>
            <div class="date-line">{escape(weekday)}, {escape(date_label)}</div>
            {age_html}
        </div>
        {sections_html or '<p style="color:#aaa;font-style:italic;">Nothing scheduled today.</p>'}
        {meal_print_html}
        <div class="page-footer">Family Planner · {escape(date_label)}</div>
    </div>"""


def _render_meal_print_section(target_date, weekday: str) -> str:
    """Compact print-friendly meal block for daily printouts."""
    try:
        from render_meals import load_meal_plan, _week_key
        plan  = load_meal_plan(_week_key(target_date))
        slots = plan.get("days", {}).get(weekday, {})
        prep  = plan.get("prep_notes", {}).get(weekday, "").strip()
    except Exception:
        return ""

    meal_icons  = {"breakfast": "☀", "lunch": "▸", "dinner": "●", "snacks": "◆"}
    meal_labels = {"breakfast": "Breakfast", "lunch": "Lunch",
                   "dinner": "Dinner", "snacks": "Snacks"}
    boys_help   = (slots.get("boys_help") or "").strip()

    rows = ""
    for slot in ["breakfast", "lunch", "dinner", "snacks"]:
        val = (slots.get(slot) or "").strip()
        if not val:
            continue
        icon  = meal_icons[slot]
        label = meal_labels[slot]
        rows += (
            f'<div style="display:flex;gap:6pt;padding:2pt 0;font-size:8pt;">'
            f'<span style="font-weight:700;width:60pt;flex-shrink:0;color:#555;">'
            f'{icon} {escape(label)}</span>'
            f'<span>{escape(val)}</span>'
            f'</div>'
        )

    if not rows:
        return ""

    extra = ""
    if prep:
        extra += (
            f'<div style="margin-top:4pt;font-size:7.5pt;color:#166534;">'
            f'<strong>Prep:</strong> {escape(prep)}</div>'
        )
    if boys_help:
        extra += (
            f'<div style="margin-top:3pt;font-size:7.5pt;color:#92400e;">'
            f'<strong>Boys help:</strong> {escape(boys_help)}</div>'
        )

    return (
        f'<div class="section-title">Today\'s Meals</div>'
        f'<div style="padding:4pt 0;">'
        f'{rows}'
        f'{extra}'
        f'</div>'
    )

def render_print_child_day_list(child: str, target_date_str: str = "") -> str:
    """Print a single child's complete chronological Day List — clean, checkable."""
    normalized_date = normalize_date_query(target_date_str)
    packet     = generate_day_packet(normalized_date)
    iso        = packet["iso"]
    weekday    = packet["weekday"]
    date_label = packet["date_label"]

    day_list = build_day_list(child, weekday, iso)
    stats    = day_list_stats(day_list)
    c_color  = child_color(child, "bg")

    # ── Approval via print: auto-create school + chore quests ─────────────────
    # Printing the day list IS the parent's approval. Quests are created here
    # (idempotent — duplicates are skipped if already approved).
    _QUEST_CHILDREN = {"JP", "Joseph", "Michael", "James"}
    if child in _QUEST_CHILDREN:
        try:
            import sys as _sys, os as _os
            _fq_root = _os.path.join(_os.path.dirname(os.path.abspath(__file__)), "family_quest")
            if _fq_root not in _sys.path:
                _sys.path.insert(0, _fq_root)
            from fq_data import sync_all_quests_for_child
            sync_all_quests_for_child(child, iso)
        except Exception:
            pass

    try:
        target_iso = date.fromisoformat(iso)
    except Exception:
        target_iso = date.today()

    age_strip = render_child_age_strip(child, target_iso)
    age_html  = (f'<div style="font-size:8pt;color:#888;margin-top:2px;">{age_strip}</div>'
                 if age_strip else "")

    _kind_icons_print = {
        "wakeup": "☀", "prayer": "✝", "mass": "✝", "meal": "🍽",
        "exercise": "💪", "school": "📚", "chore": "🧹",
        "task": "✎", "routine": "•", "free": "◦",
    }
    _kind_colors_print = {
        "prayer": "#7a6a00", "mass": "#2d0a5f", "school": "#0a2266",
        "chore": "#5a2000", "task": "#3a1a6e", "exercise": "#0a4a28",
        "meal": "#5a1a3a",
    }

    def _is_print_done(s: dict) -> bool:
        return bool(s.get("done", False))

    # Only show pending (unchecked) items on the printout.
    # If everything is already done, show all items so the sheet isn't blank.
    _has_any_pending = any(
        not _is_print_done(s)
        for item in day_list
        for s in ([item] + item.get("sub_items", []))
        if s.get("checkable") and s.get("task_id")
    )

    rows_html = ""
    for item in day_list:
        kind   = item.get("kind", "routine")
        t_st   = item.get("time", "")
        t_en   = item.get("end_time", "")
        t_disp = f"{t_st}\u2013{t_en}" if t_en and t_en != t_st else t_st
        label  = escape(item.get("label", ""))
        icon   = _kind_icons_print.get(kind, "")
        kcolor = _kind_colors_print.get(kind, "#444")
        subs   = item.get("sub_items", [])

        if subs:
            checkable_subs = [s for s in subs if s.get("checkable") and not s.get("is_header")]
            pending_subs   = [s for s in checkable_subs if not _is_print_done(s)]
            # Skip entire block if all its checkable sub-items are done
            if _has_any_pending and not pending_subs:
                continue
            tot = len(pending_subs)
            rows_html += (
                f'<div class="blk-header" style="--blk-color:{kcolor};">'
                f'<span class="blk-time">{escape(t_disp)}</span>'
                f'<span class="blk-label">{icon} {label}</span>'
                f'<span class="blk-count">— {tot} item{"s" if tot != 1 else ""}</span>'
                f'</div>'
            )
            for sub in subs:
                if sub.get("is_header"):
                    rows_html += f'<div class="sub-sect">{escape(sub.get("text",""))}</div>'
                elif sub.get("checkable") and sub.get("task_id"):
                    if _has_any_pending and _is_print_done(sub):
                        continue
                    carry_mark = "↩ " if sub.get("is_carryover") else ""
                    rows_html += (
                        f'<div class="sub-item">'
                        f'<span class="sub-box"></span>'
                        f'<span>{carry_mark}{escape(sub.get("text",""))}</span>'
                        f'</div>'
                    )
                else:
                    rows_html += f'<div class="sub-note">• {escape(sub.get("text",""))}</div>'
        elif item.get("task_id") and item.get("checkable"):
            if _has_any_pending and _is_print_done(item):
                continue
            rows_html += (
                f'<div class="blk-header" style="--blk-color:{kcolor};">'
                f'<span class="blk-time">{escape(t_disp)}</span>'
                f'<span class="sub-box" style="margin-right:4px;margin-top:1px;"></span>'
                f'<span class="blk-label">{icon} {label}</span>'
                f'</div>'
            )
        else:
            rows_html += (
                f'<div class="info-row">'
                f'<span class="info-time">{escape(t_disp)}</span>'
                f'<span class="info-label">{icon} {label}</span>'
                f'</div>'
            )

    meal_print = _render_meal_print_section(target_iso, weekday)
    body = f"""
    <div class="child-page" style="--child-color:{c_color};">
        <div class="page-header">
            <div class="child-name">{escape(child)}</div>
            <div class="date-line">{escape(weekday)}, {escape(date_label)}</div>
        </div>
        {rows_html or '<p style="color:#aaa;font-style:italic;">No schedule data for today.</p>'}
        {meal_print}
        <div class="page-footer">McAdams Family · {escape(date_label)}</div>
    </div>"""
    return print_page_html(f"{escape(child)} — {escape(date_label)}", body)


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