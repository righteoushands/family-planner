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
        tid_js     = escape(task_id, quote=False).replace("'", "\\'")
        label_id   = f"lbl-{tid_esc}"
        html += f"""
        <div class="task {done_class}" id="task-{tid_esc}">
            <input type="checkbox" id="{label_id}" {checked}
                   onchange="toggleTask(this,'{tid_js}','/schedule/{escape(child)}?date={escape(iso)}')">
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
            <div class="card card-tight no-print" id="lucy-child-panel-{child.lower()}"
                 style="border-left:4px solid {c_bg};background:{c_light};">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                    <span style="font-size:1.1em;">✦</span>
                    <h3 style="margin:0;font-size:.95em;color:{c_bg};">Lucy's Notes for {escape(child)}</h3>
                </div>
                <div id="lucy-child-brief-{child.lower()}"
                     style="font-size:.88em;line-height:1.6;color:#444;min-height:40px;">
                    <span style="color:#bbb;font-style:italic;">Loading…</span>
                </div>
            </div>
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
        {_render_meal_card_for_child(target_iso)}
        {_render_child_goals_section(child)}
        {_render_child_profile_section(child, c_bg, c_light)}
    </div>
<script>
(function() {{
    var el = document.getElementById('lucy-child-brief-{child.lower()}');
    if (!el) return;
    fetch('/lucy-child-brief/{child.lower()}')
        .then(function(r) {{ return r.json(); }})
        .then(function(d) {{
            el.innerHTML = d.html || '<span style="color:#bbb;font-style:italic;">Not available right now.</span>';
        }})
        .catch(function() {{
            el.innerHTML = "<span style='color:#bbb;font-style:italic;'>Could not load Lucy\u2019s notes.</span>";
        }});
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
    body = f"{page_header(child)}{render_child_schedule_card(child, normalized_date)}"
    return html_page(child, body)


def render_child_dash_card(child: str, target_date_str: str = "") -> str:
    """Compact dashboard card: carryover + first unchecked task, auto-advance on check."""
    normalized_date = normalize_date_query(target_date_str)
    packet     = generate_day_packet(normalized_date)
    iso        = packet["iso"]
    weekday    = packet["weekday"]
    date_label = packet["date_label"]

    payload  = build_schedule_payload(child, weekday, date_label, iso)
    progress = load_progress()

    c_bg    = child_color(child, "bg")
    c_light = child_color(child, "light")
    c_id    = child.lower().replace(" ", "-")

    # ── Gather tasks ────────────────────────────────────────────────────────
    carryover   = payload.get("carryover_items", [])
    chore_items = payload.get("chore_items", [])

    # School/task queue (2-at-a-time advance model)
    queue = []
    for item in payload.get("manual_task_items", []):
        queue.append(dict(item, _section="Task"))
    for block in payload.get("school_blocks", []):
        subj = block.get("subject", "School")
        for item in block.get("items", []):
            queue.append(dict(item, _section=subj))

    total     = (len(carryover) + len(queue) + len(chore_items))
    done_cnt  = (sum(1 for i in carryover   if _item_done(i, progress)) +
                 sum(1 for i in queue       if _item_done(i, progress)) +
                 sum(1 for i in chore_items if _item_done(i, progress)))
    remaining = total - done_cnt
    pct       = round(done_cnt / total * 100) if total else 0
    all_done  = total > 0 and done_cnt == total

    bar_col = "#22c55e" if all_done else ("#f59e0b" if pct >= 50 else c_bg)

    cb_url = f"/today?date={escape(iso)}"

    def _dash_row(item, extra_style="", is_chore=False):
        tid     = escape(item.get("task_id", ""))
        tid_js  = escape(item.get("task_id", ""), quote=False).replace("'", "\\'")
        is_done = _item_done(item, progress)
        checked = "checked" if is_done else ""
        done_st = "opacity:.5;text-decoration:line-through;" if is_done else ""
        done_d  = "1" if is_done else "0"
        section = escape(item.get("_section", ""))
        sec_div = (
            f'<div style="font-size:.62em;font-weight:800;letter-spacing:.07em;'
            f'text-transform:uppercase;color:{c_bg};margin-bottom:1px;">{section}</div>'
            if section else ""
        )
        chore_attr = ' data-chore="1"' if is_chore else ""
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
            f'cursor:pointer;{done_st}">{escape(item.get("text",""))}</label>'
            f'</div></div>'
        )

    # ── Carryover rows (show up to 3; indicate extras) ───────────────────────
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
                f' style="color:#a07040;text-decoration:none;">+{_carry_extra} more carryover →</a>'
                f'</div>'
            )

    # ── School / task queue (next 2 unchecked visible; rest hidden) ──────────
    queue_html    = ""
    pending_shown = 0
    for item in queue:
        is_done = _item_done(item, progress)
        if is_done:
            vis = "display:none;"
        elif pending_shown < 2:
            vis = ""
            pending_shown += 1
        else:
            vis = "display:none;"
        queue_html += _dash_row(item, extra_style=vis)

    # ── Chores section — ALL chores always visible ───────────────────────────
    chore_html = ""
    if chore_items:
        chore_done = sum(1 for i in chore_items if _item_done(i, progress))
        chore_lbl  = f"{chore_done}/{len(chore_items)}"
        chore_html = (
            f'<div style="font-size:0.65em;font-weight:800;letter-spacing:.08em;'
            f'text-transform:uppercase;color:{c_bg};margin:10px 0 3px;">'
            f'Chores <span style="font-weight:500;color:#888;">({chore_lbl})</span></div>'
        )
        for item in chore_items:
            chore_html += _dash_row(item, is_chore=True)

    all_done_badge = (
        '<div style="color:#166534;font-weight:700;font-size:.85em;background:#dcfce7;'
        'padding:6px 12px;border-radius:8px;margin:4px 0;">✓ All done today!</div>'
        if all_done else ""
    )

    return (
        f'<div class="card" id="dash-card-{c_id}"'
        f' style="border-left:4px solid {c_bg};background:{c_light};'
        f'margin-bottom:10px;padding:12px 14px;">'

        # Header
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

        # Progress bar
        f'<div style="height:4px;background:#e0d8d0;border-radius:2px;margin-bottom:8px;">'
        f'<div id="dash-bar-{c_id}" style="height:100%;width:{pct}%;'
        f'background:{bar_col};border-radius:2px;transition:width .3s;"></div></div>'

        f'{all_done_badge}'
        f'{carry_html}'
        f'<div id="dash-queue-{c_id}">{queue_html}</div>'
        f'{chore_html}'
        f'</div>'
    )


_DASH_JS = """
<script>
function toggleDashTask(cb, tid, childId, iso) {
    var row    = document.getElementById('task-' + tid);
    var isDone = cb.checked;
    var newVal = isDone ? 'true' : 'false';
    var isChore = row && row.getAttribute('data-chore') === '1';
    if (row) {
        row.setAttribute('data-done', isDone ? '1' : '0');
        var lbl = row.querySelector('label');
        if (lbl) lbl.style.cssText += isDone
            ? 'opacity:.5;text-decoration:line-through;'
            : 'opacity:1;text-decoration:none;';
        if (isDone && !isChore) setTimeout(function(){ row.style.display='none'; }, 400);
    }
    fetch('/toggle-task', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'task_id=' + encodeURIComponent(tid) +
              '&new_value=' + encodeURIComponent(newVal) +
              '&return_url=' + encodeURIComponent('/today?date=' + iso)
    }).then(function(r) {
        if (!r.ok) {
            cb.checked = !cb.checked;
            if (row) { row.setAttribute('data-done', isDone?'0':'1'); row.style.display=''; }
        } else {
            _dashUpdateProgress(childId);
            if (isDone && !isChore) {
                setTimeout(function(){ _dashAdvance(childId); }, 420);
            }
        }
    }).catch(function() {
        cb.checked = !cb.checked;
        if (row) { row.setAttribute('data-done', isDone?'0':'1'); row.style.display=''; }
    });
}

function _dashAdvance(childId) {
    var queue = document.getElementById('dash-queue-' + childId);
    if (!queue) return;
    var tasks = queue.querySelectorAll('.dash-task[data-dash-child="' + childId + '"]');
    for (var i = 0; i < tasks.length; i++) {
        if (tasks[i].getAttribute('data-done') === '0' &&
            tasks[i].style.display === 'none') {
            tasks[i].style.display = '';
            break;
        }
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
    if (bar) { bar.style.width = pct + '%';
               bar.style.background = pct === 100 ? '#22c55e' : pct >= 50 ? '#f59e0b' : bar.style.background; }
    var cnt = document.getElementById('dash-count-' + childId);
    if (cnt) cnt.textContent = pct === 100 ? '✓ done' : (tot - done) + ' left';
}
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

    body = (
        f'{page_header("Today")}'
        f'{bar}'
        f'{day_nav}'
        f'{now_strip}'
        f'{school_banner}'
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