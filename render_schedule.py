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


def _js_attr(s: str) -> str:
    """Encode a string for safe use as a single-quoted JS string literal
    that lives inside a double-quoted HTML attribute.
    Order matters: backslash → JS-escape quotes → HTML-escape attribute chars."""
    if s is None:
        return ""
    s = str(s).replace("\\", "\\\\").replace("'", "\\'")
    return escape(s, quote=True)


# ── Exercise assignment helper ────────────────────────────────────────────────
_EXERCISE_PERSON_ALIAS = {"mom": "Lauren", "lauren": "Lauren", "jp": "JP",
                          "joseph": "Joseph", "michael": "Michael", "james": "James"}


def _latest_coach_program_for(person: str) -> tuple:
    """Returns (title, body) of the most recently-saved Coach program for
    `person`, or ("","") if none. Resolves Mom→Lauren alias."""
    try:
        from data_helpers import load_coach_programs
        data = load_coach_programs() or {}
        key  = _EXERCISE_PERSON_ALIAS.get((person or "").lower(), person)
        bucket = data.get(key) or []
        if not bucket and key == "Lauren":
            bucket = data.get("Mom") or []
        if not bucket:
            return ("", "")
        # Pick most recent by saved_at (string ISO sorts correctly)
        latest = max(bucket, key=lambda p: p.get("saved_at", ""))
        return (latest.get("title", ""), latest.get("body", ""))
    except Exception:
        return ("", "")


def _slot_time_to_minutes(t: str) -> int:
    """Parse a '9:00 AM' style time to minutes-since-midnight; -1 if not parseable."""
    try:
        from datetime import datetime as _dt
        d = _dt.strptime((t or "").strip(), "%I:%M %p")
        return d.hour * 60 + d.minute
    except Exception:
        return -1


def _minutes_to_slot_time(m: int) -> str:
    """Inverse of _slot_time_to_minutes — '9:00 AM' style."""
    try:
        m = max(0, m) % (24 * 60)
        h, mm = divmod(m, 60)
        ampm = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{mm:02d} {ampm}"
    except Exception:
        return ""


def _get_exercise_assignment(child: str, weekday: str) -> tuple:
    """
    Returns (slot_time, slot_label, assignment_text) for the exercise slot on
    `weekday` for `child`, or ("", "", "") if there is no exercise scheduled.
    The slot_time follows whatever the FROL says — never hard-coded.
    Resolves 'Lauren'/'Mom' alias automatically.
    """
    from data_helpers import get_frol_day_slots, load_exercise_assignments
    _EXERCISE_KEYWORDS = ("fortitude", "justice", "exercise", "family run", "family strength")
    # exercise_assignments.json uses "Lauren" (not "Mom") as the key
    _ex_alias = {"mom": "Lauren", "lauren": "Lauren", "jp": "JP", "joseph": "Joseph",
                 "michael": "Michael", "james": "James"}
    person_key = _ex_alias.get(child.lower(), child)
    try:
        day_slots  = get_frol_day_slots(weekday, "Mom")
        ex_assigns = load_exercise_assignments().get(weekday, {})
        slot_time  = ""
        slot_label = ""
        for t, v in day_slots.items():
            if v and any(kw in v.lower() for kw in _EXERCISE_KEYWORDS):
                slot_time  = t
                slot_label = v
                break
        if not slot_label:
            return ("", "", "")
        assignment = ex_assigns.get(person_key, "")
        return (slot_time, slot_label, assignment)
    except Exception:
        return ("", "", "")


def _render_hydration_row_html(slot_time: str, c_bg: str) -> str:
    """Small pre-workout hydration reminder row — chronological in the day list,
    automatically scheduled 1 hour before the FROL exercise slot."""
    ex_min = _slot_time_to_minutes(slot_time)
    if ex_min < 0:
        return ""
    hyd_time = _minutes_to_slot_time(ex_min - 60)
    if not hyd_time:
        return ""
    from html import escape as _e
    return (
        f'<div class="dl-row dl-info" style="border-left:3px solid {c_bg}aa;'
        f'background:#f0f9ff;">'
        f'<span class="dl-time">{_e(hyd_time)}</span>'
        f'<span class="dl-kind-icon">&#128166;</span>'
        f'<span class="dl-label" style="color:#0369a1;">'
        f'Hydrate &mdash; water + electrolytes (1 hour before workout)</span>'
        f'</div>'
    )


def _post_workout_log_print_line() -> str:
    """Tiny one-line printable post-workout log — rendered under the exercise
    block in BOTH screen and print POD views."""
    return (
        '<div style="margin-top:6px;font-size:0.78em;color:#555;line-height:1.4;'
        'border-top:1px dotted #999;padding-top:5px;">'
        '<strong>Log:</strong> Duration ______ &nbsp; Reps/Notes ______________ '
        '&nbsp; Felt ______'
        '</div>'
    )


def _render_post_workout_log_form(child: str, iso: str, c_bg: str) -> str:
    """Full post-workout log form — visible on-screen only (no-print).

    Three fields (Duration, Reps/Notes, How I Felt) with a Save button that
    posts to /exercise-log. Pre-fills with any previously-saved entry.
    """
    from html import escape as _e
    try:
        from data_helpers import load_exercise_logs
        existing = load_exercise_logs().get(f"{iso}::{child}", {})
    except Exception:
        existing = {}
    dur  = _e(existing.get("duration", ""))
    reps = _e(existing.get("reps", ""))
    felt = _e(existing.get("felt", ""))
    saved_at = _e(existing.get("saved_at", ""))
    saved_note = (
        f'<span style="font-size:.7em;color:#16a34a;margin-left:8px;">'
        f'&#10003; saved {saved_at}</span>'
    ) if saved_at else ""
    return (
        f'<div class="no-print" style="margin-top:8px;background:#fff;'
        f'border:1px solid {c_bg}55;border-radius:8px;padding:10px 12px;">'
        f'<div style="font-size:.72em;font-weight:800;letter-spacing:.08em;'
        f'text-transform:uppercase;color:{c_bg};margin-bottom:8px;">'
        f'&#128221; Post-Workout Log{saved_note}</div>'
        f'<form method="POST" action="/exercise-log"'
        f' style="display:flex;flex-direction:column;gap:6px;">'
        f'<input type="hidden" name="person" value="{_e(child)}">'
        f'<input type="hidden" name="iso" value="{_e(iso)}">'
        f'<input type="hidden" name="return_url" value="/schedule/{_e(child)}?date={_e(iso)}">'
        f'<label style="font-size:.78em;color:#555;">Duration'
        f'<input type="text" name="duration" value="{dur}" placeholder="e.g. 30 min"'
        f' style="width:100%;border:1px solid #ddd;border-radius:6px;'
        f'padding:6px 8px;font-size:.88em;font-family:inherit;margin-top:2px;"></label>'
        f'<label style="font-size:.78em;color:#555;">Reps / Notes'
        f'<input type="text" name="reps" value="{reps}" placeholder="e.g. 3x10 push-ups"'
        f' style="width:100%;border:1px solid #ddd;border-radius:6px;'
        f'padding:6px 8px;font-size:.88em;font-family:inherit;margin-top:2px;"></label>'
        f'<label style="font-size:.78em;color:#555;">How I Felt'
        f'<input type="text" name="felt" value="{felt}" placeholder="e.g. strong / tired / energized"'
        f' style="width:100%;border:1px solid #ddd;border-radius:6px;'
        f'padding:6px 8px;font-size:.88em;font-family:inherit;margin-top:2px;"></label>'
        f'<button type="submit"'
        f' style="background:{c_bg};color:#fff;border:none;border-radius:6px;'
        f'padding:7px 14px;font-size:.85em;font-weight:600;cursor:pointer;'
        f'align-self:flex-start;margin-top:4px;">Save log</button>'
        f'</form></div>'
    )


def _render_exercise_block_screen(child: str, weekday: str, c_bg: str, c_light: str,
                                   iso: str = "") -> str:
    """Colored exercise block for the live POD card (visible on-screen and in print).

    Inlines the latest Coach-saved program body for this person so the actual
    workout is visible right here — no need to click through to /programs.
    Uses the FROL slot time (never hard-coded). Includes a small printable
    log line, plus a full no-print log form when iso is provided.
    """
    slot_time, slot_label, assignment = _get_exercise_assignment(child, weekday)
    if not slot_label:
        return ""
    from html import escape as _e
    prog_title, prog_body = _latest_coach_program_for(child)
    program_html = ""
    if prog_body:
        body_html = _e(prog_body).replace("\n", "<br>")
        title_html = _e(prog_title) if prog_title else "Coach&rsquo;s program"
        program_html = (
            f'<div style="margin-top:8px;padding-top:8px;border-top:1px dashed {c_bg}55;">'
            f'<div style="font-size:0.7em;font-weight:700;color:{c_bg};margin-bottom:4px;">'
            f'&#128221; {title_html}</div>'
            f'<div style="font-size:0.85em;color:#333;line-height:1.55;'
            f'white-space:normal;word-break:break-word;">{body_html}</div>'
            f'<div style="margin-top:6px;text-align:right;">'
            f'<a href="/programs" style="font-size:0.72em;color:{c_bg};'
            f'text-decoration:none;font-weight:600;">View all programs &rarr;</a>'
            f'</div>'
            f'</div>'
        )
    log_form_html = _render_post_workout_log_form(child, iso, c_bg) if iso else ""
    time_disp = _e(slot_time) if slot_time else "Exercise"
    return (
        f'<div style="border-left:4px solid {c_bg};background:{c_light};'
        f'padding:10px 14px;margin-bottom:10px;border-radius:0 8px 8px 0;">'
        f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;'
        f'text-transform:uppercase;color:{c_bg};margin-bottom:4px;">'
        f'&#128170; {time_disp} &middot; {_e(slot_label)}</div>'
        f'<div style="font-size:0.88em;color:#333;line-height:1.5;">'
        f'{_e(assignment) if assignment else _e(slot_label)}</div>'
        f'{program_html}'
        f'{_post_workout_log_print_line()}'
        f'{log_form_html}'
        f'</div>'
    )


def _render_exercise_block_print(child: str, weekday: str) -> str:
    """Print-friendly exercise section for the child print page.

    Includes the latest Coach-saved program body so the printout stands alone,
    plus a small post-workout log line. Time follows the FROL.
    """
    slot_time, slot_label, assignment = _get_exercise_assignment(child, weekday)
    if not slot_label:
        return ""
    from html import escape as _e
    text = assignment if assignment else slot_label
    prog_title, prog_body = _latest_coach_program_for(child)
    program_html = ""
    if prog_body:
        body_html = _e(prog_body).replace("\n", "<br>")
        program_html = (
            f'<div style="margin-top:4pt;padding-top:4pt;border-top:1px dashed #999;">'
            f'<div style="font-size:8.5pt;font-weight:700;color:#444;margin-bottom:2pt;">'
            f'{_e(prog_title) if prog_title else "Coach&rsquo;s program"}</div>'
            f'<div style="font-size:9pt;line-height:1.5;color:#222;">{body_html}</div>'
            f'<div style="margin-top:3pt;text-align:right;font-size:8pt;color:#666;">'
            f'<a href="/programs" style="color:#666;text-decoration:none;">'
            f'View all programs &rarr;</a>'
            f'</div>'
            f'</div>'
        )
    time_disp = _e(slot_time) if slot_time else "Exercise"
    log_print = (
        '<div style="margin-top:4pt;padding-top:4pt;border-top:1px dotted #999;'
        'font-size:8.5pt;color:#444;">'
        '<strong>Log:</strong> Duration ______ &nbsp; Reps/Notes ______________ '
        '&nbsp; Felt ______'
        '</div>'
    )
    return (
        f'<div class="section-title">Exercise &mdash; {time_disp}</div>'
        f'<div style="padding:4pt 0 8pt;font-size:9pt;line-height:1.5;color:#222;">'
        f'<strong>{_e(slot_label)}</strong><br>{_e(text)}'
        f'{program_html}'
        f'{log_print}'
        f'</div>'
    )


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


# ── Thank-you card Suggested-Tasks widget (Lauren's /today POD) ───────────────
def _ty_suggested_tasks_widget(due_list: list, return_url: str = "/today") -> str:
    """Prominent widget shown on Lauren's dashboard for each due thank-you card.

    Lets her pick which family members should get a 'Send thank-you card' task
    added to their POD, and separately mark the card as already sent.
    """
    if not due_list:
        return ""

    MEMBERS = [("Mom", "Mom"), ("JP", "JP"), ("Joseph", "Joseph"),
               ("Michael", "Michael"), ("James", "James")]

    cards_html = ""
    for r in due_list:
        rid    = escape(r.get("id", ""))
        ename  = escape(r.get("event_name", ""))
        ppl    = escape(r.get("people", ""))
        task_text = f"Send thank-you card: {r.get('event_name','')} (for {r.get('people','')})" if r.get('people') else f"Send thank-you card: {r.get('event_name','')}"

        checkboxes = "".join(
            f'<label style="display:flex;align-items:center;gap:5px;'
            f'font-size:.83em;color:#5a3e2b;cursor:pointer;white-space:nowrap;">'
            f'<input type="checkbox" name="assign_to" value="{v}" '
            f'style="accent-color:#8b5a3c;width:15px;height:15px;">'
            f'{label}</label>'
            for label, v in MEMBERS
        )

        cards_html += (
            f'<div style="background:#fffdf5;border:1px solid #e5d9a0;border-radius:8px;'
            f'padding:10px 12px;margin-bottom:8px;">'

            # Event header
            f'<div style="font-size:.82em;font-weight:700;color:#7c4f1e;'
            f'margin-bottom:1px;">{ename}</div>'
            + (f'<div style="font-size:.74em;color:#9c8060;margin-bottom:8px;">For: {ppl}</div>' if ppl else '<div style="margin-bottom:8px;"></div>')

            # Add-to-POD form
            + f'<form method="POST" action="/thankyou-suggest" style="margin:0;">'
            f'<input type="hidden" name="reminder_id" value="{rid}">'
            f'<input type="hidden" name="task_text" value="{escape(task_text)}">'
            f'<input type="hidden" name="return_url" value="{escape(return_url)}">'
            f'<div style="font-size:.72em;font-weight:800;letter-spacing:.04em;'
            f'text-transform:uppercase;color:#92400e;margin-bottom:5px;">Add \'Send thank-you\' task to:</div>'
            f'<div style="display:flex;flex-wrap:wrap;gap:8px 14px;margin-bottom:9px;">{checkboxes}</div>'
            f'<div style="display:flex;gap:6px;flex-wrap:wrap;">'
            f'<button type="submit" name="action" value="add"'
            f' style="background:#8b5a3c;color:white;border:none;border-radius:7px;'
            f'padding:6px 14px;font-size:.8em;font-weight:700;cursor:pointer;">+ Add to POD(s)</button>'
            f'<button type="submit" name="action" value="sent"'
            f' style="background:#5a7a5a;color:white;border:none;border-radius:7px;'
            f'padding:6px 14px;font-size:.8em;font-weight:700;cursor:pointer;">&#10003; Already Sent</button>'
            f'<button type="submit" name="action" value="skip"'
            f' style="background:transparent;color:#9c8060;border:1px solid #d1c4a8;'
            f'border-radius:7px;padding:6px 12px;font-size:.8em;cursor:pointer;">Skip</button>'
            f'</div>'
            f'</form>'
            f'</div>'
        )

    n   = len(due_list)
    lbl = "Thank-You Card Due" if n == 1 else "Thank-You Cards Due"
    return (
        f'<div style="background:#fef3e2;border:1.5px solid #e8c97a;border-radius:10px;'
        f'padding:10px 12px;margin-bottom:12px;">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'margin-bottom:6px;">'
        f'<span style="font-size:.72em;font-weight:800;letter-spacing:.06em;'
        f'text-transform:uppercase;color:#92400e;">&#9993; {n} {lbl}</span>'
        f'<a href="/thankyou-reminders" style="font-size:.72em;color:#8b5a3c;'
        f'text-decoration:none;white-space:nowrap;">Manage all ›</a>'
        f'</div>'
        f'{cards_html}'
        f'</div>'
    )


# ── Collapsible section wrapper ───────────────────────────────────────────────
def _collapsible_wrap(section_id: str, title: str, inner_html: str,
                      accent: str = "#8b7355", default_open: bool = True) -> str:
    """Wrap a block in a collapsible panel with a show/hide toggle button.

    The toggle state is persisted in localStorage keyed by section_id so the
    user's preference survives page reloads.  Returns inner_html unchanged when
    it is empty so callers don't need to guard.
    """
    if not inner_html or not inner_html.strip():
        return inner_html
    caret      = "▾" if default_open else "▸"
    body_style = "" if default_open else ' style="display:none;"'
    return (
        f'<div class="pod-section no-print" id="pod-sec-{section_id}">'
        f'<div class="pod-sec-hdr" onclick="_podToggle(\'{section_id}\')"'
        f' style="display:flex;align-items:center;justify-content:space-between;'
        f'cursor:pointer;padding:4px 2px 2px;user-select:none;">'
        f'<span style="font-size:.7em;font-weight:800;letter-spacing:.07em;'
        f'text-transform:uppercase;color:{accent};">{title}</span>'
        f'<span id="pod-sec-caret-{section_id}"'
        f' style="font-size:.85em;color:{accent};margin-left:6px;">{caret}</span>'
        f'</div>'
        f'<div id="pod-sec-body-{section_id}"{body_style}>'
        f'{inner_html}'
        f'</div>'
        f'</div>'
    )


_COLLAPSIBLE_JS = """
<script>
(function(){
function _podToggle(id){
    var body=document.getElementById('pod-sec-body-'+id);
    var caret=document.getElementById('pod-sec-caret-'+id);
    if(!body)return;
    var hidden=body.style.display==='none';
    body.style.display=hidden?'':'none';
    if(caret)caret.textContent=hidden?'\u25be':'\u25b8';
    try{localStorage.setItem('pod-sec-'+id,hidden?'1':'0');}catch(e){}
}
window._podToggle=_podToggle;
document.querySelectorAll('.pod-section').forEach(function(sec){
    var id=sec.id.replace('pod-sec-','');
    try{
        var st=localStorage.getItem('pod-sec-'+id);
        if(st==='0'){
            var b=document.getElementById('pod-sec-body-'+id);
            var c=document.getElementById('pod-sec-caret-'+id);
            if(b)b.style.display='none';
            if(c)c.textContent='\u25b8';
        }
    }catch(e){}
});
})();
</script>
"""


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
        tid_js     = _js_attr(task_id)
        label_id   = f"lbl-{tid_esc}"
        html += f"""
        <div class="task {done_class}" id="task-{tid_esc}">
            <input type="checkbox" id="{label_id}" {checked}
                   onchange="toggleTask(this,'{tid_js}','/schedule/{_js_attr(child)}?date={_js_attr(iso)}')">
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
            tid_j   = _js_attr(raw_tid)
            # Check for override on this sub-item
            _ov      = _day_ovs.get(raw_tid, {})
            _ov_act  = _ov.get("action", "")
            if _ov_act == "dismiss":
                continue   # skip dismissed sub-items
            if _ov_act == "postpone":
                continue   # skip postponed sub-items (moved to another day)
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
            _lbl_js  = _js_attr(_lbl_raw)
            try:
                from datetime import date as _d3, timedelta as _td3
                _tmr = (_d3.fromisoformat(iso) + _td3(days=1)).isoformat()
            except Exception:
                _tmr = ""
            row_html = (
                f'<div class="dl-sub-row" id="task-{tid}"'
                f' data-dash-child="{c_id}" data-done="{dnv}">'
                f'{_time_badge}'
                f'<span class="dl-sub-label {dst}">{carry}{escape(_lbl_raw)}{due_badge}</span>'
                f'<input type="checkbox" {chk}'
                f' style="width:15px;height:15px;flex-shrink:0;accent-color:{c_bg};margin-left:8px;"'
                f' onchange="toggleDashTask(this,\'{tid_j}\',\'{c_id}\',\'{escape(iso)}\')">'
                f'</div>'
            )
            tray_html = (
                f'<div class="sw-del sw-ov-tray no-print">'
                f'<button class="sw-ov-btn sw-ov-dismiss" '
                f'onclick="_tovAct(\'{tid_j}\',\'{c_id}\',\'{escape(iso)}\',\'{_lbl_js}\',\'dismiss\')">'
                f'&#10005; Dismiss</button>'
                f'<button class="sw-ov-btn sw-ov-sched" '
                f'onclick="_schedOpen(\'{tid_j}\',\'{c_id}\',\'{escape(iso)}\',\'{_lbl_js}\')">'
                f'&#128197; Schedule</button>'
                f'<button class="sw-ov-btn sw-ov-hide" onclick="_swDel(this)">'
                f'&#8942; Hide</button>'
                f'</div>'
            )
            rows.append(
                f'<div class="sw-wrap" data-child="{_child_esc}" data-iso="{_iso_esc}">'
                f'<button class="sw-add no-print" onclick="_swAdd(this)" aria-label="Add task below">+ Add</button>'
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
                           c_bg: str, meals: dict = None,
                           inline_exercise_html: str = "",
                           exercise_slot_time: str = "",
                           inline_hydration_html: str = "") -> str:
    if not day_list:
        from datetime import date as _date
        try:
            _d = _date.fromisoformat(iso)
            _weekday = _d.strftime("%A")
        except Exception:
            _weekday = "this day"
        return (
            f'<div style="padding:24px 20px;text-align:center;color:#9ca3af;'
            f'background:#f9fafb;border-radius:12px;margin:12px 0;">'
            f'<div style="font-size:1.5em;margin-bottom:8px;">📋</div>'
            f'<div style="font-weight:600;color:#6b7280;margin-bottom:4px;">'
            f'No schedule set up for {escape(child)} on {_weekday}.</div>'
            f'<div style="font-size:0.85em;">Ask Mom to build the {_weekday} template in Settings → Rule of Life.</div>'
            f'</div>'
        )
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
    _exercise_injected = False  # ensure inline exercise block is added once
    _hydration_injected = False  # ensure hydration row is added once

    # Compute injection thresholds from the actual FROL exercise slot.
    # If no valid slot was provided, skip in-loop injection entirely — the
    # exercise/hydration HTML (if any) will be tail-appended after the loop.
    _EX_THRESHOLD = _slot_time_to_minutes(exercise_slot_time)
    _HYD_THRESHOLD = (_EX_THRESHOLD - 60) if _EX_THRESHOLD >= 60 else -1

    for item in day_list:
        kind  = item.get("kind", "routine")
        color = _dl_kind_color(kind)
        icon  = _DL_KIND_LABELS.get(kind, "•")
        t_st  = item.get("time", "")
        t_en  = item.get("end_time", "")
        t_disp = f"{t_st} – {t_en}" if t_en and t_en != t_st else t_st
        _t_min = _slot_time_to_minutes(t_st)

        # Inject hydration reminder at the first row whose time reaches
        # exercise-time minus 1 hour (printed + screen).
        if (inline_hydration_html and not _hydration_injected
                and _t_min >= _HYD_THRESHOLD):
            rows.append(inline_hydration_html)
            rows_del.append(False)
            _hydration_injected = True

        # Inject the exercise block at the first row whose time reaches the
        # FROL exercise slot.
        if (inline_exercise_html and not _exercise_injected
                and _t_min >= _EX_THRESHOLD):
            rows.append(inline_exercise_html)
            rows_del.append(False)  # raw render — no swipe wrapper
            _exercise_injected = True
        # Allow callers (e.g. the cook task carrying a recipe link) to
        # pass pre-escaped HTML via `label_html` that bypasses the
        # escape() default. Caller is responsible for sanitizing.
        if item.get("label_html") is not None:
            label = item["label_html"]
        else:
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
            tidj = _js_attr(raw_tid)
            _ov = _day_ovs.get(raw_tid, {})
            _ov_act = _ov.get("action", "")
            # Skip dismissed or postponed items entirely
            if _ov_act in ("dismiss", "postpone"):
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
            _lbl_js  = _js_attr(_lbl_raw)
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
                f'<button class="sw-ov-btn sw-ov-sched" '
                f'onclick="_schedOpen(\'{tidj}\',\'{c_id}\',\'{escape(iso)}\',\'{_lbl_js}\')">'
                f'&#128197; Schedule</button>'
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
                        from render_meals import slot_display_text as _sdt
                        meal_text = _sdt(meals.get(slot_key))
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
    # Tail-inject hydration + exercise block if the day list never reached
    # the FROL exercise slot.
    if inline_hydration_html and not _hydration_injected:
        rows.append(inline_hydration_html)
        rows_del.append(False)
    if inline_exercise_html and not _exercise_injected:
        rows.append(inline_exercise_html)
        rows_del.append(False)
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
    _frol_missing = (len(day_list) == 0)   # true when no FROL template exists for this day

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

    _ex_slot_time, _ex_slot_label, _ = _get_exercise_assignment(child, weekday)
    day_list_html = _render_day_list_html(
        day_list, child, iso, c_bg, meals,
        inline_exercise_html=_render_exercise_block_screen(child, weekday, c_bg, c_light, iso),
        exercise_slot_time=_ex_slot_time,
        inline_hydration_html=(_render_hydration_row_html(_ex_slot_time, c_bg) if _ex_slot_label else ""),
    )
    template_html = _render_template_editor(child, weekday, c_bg)

    # Pre-compute collapsible section bodies
    c_id = child.lower().replace(" ", "-")
    _daily_bar_html = render_daily_bar(target_iso)
    _lucy_inner = (
        f'<div class="card card-tight" id="lucy-child-panel-{child.lower()}"'
        f' style="border-left:4px solid {c_bg};background:{c_light};margin-bottom:4px;">'
        f'<div id="lucy-child-brief-{child.lower()}"'
        f' style="font-size:.85em;line-height:1.55;color:#444;">'
        f'<div style="text-align:center;padding:6px 0 2px;">'
        f'<button id="lucy-load-btn-{child.lower()}"'
        f' onclick="loadLucyBrief(\'{child.lower()}\')"'
        f' style="background:{c_bg};color:#fff;border:none;border-radius:8px;'
        f'padding:8px 22px;font-size:.88em;font-weight:600;cursor:pointer;">'
        f'&#10022; Ask Lucy</button>'
        f'</div>'
        f'</div></div>'
    )
    _daily_bar_sec  = _collapsible_wrap(f"{c_id}-dailybar",  "&#128197; Liturgical Calendar", _daily_bar_html,                              accent=c_bg)
    _lucy_sec       = _collapsible_wrap(f"{c_id}-lucy",      "&#10022; Lucy's Notes",         _lucy_inner,                                  accent=c_bg)
    _goals_sec      = _collapsible_wrap(f"{c_id}-goals",     "&#127919; Goals",               _render_child_goals_section(child),           accent=c_bg)
    _profile_sec    = _collapsible_wrap(f"{c_id}-profile",   "&#128203; Profile",             _render_child_profile_section(child, c_bg, c_light), accent=c_bg)
    _ty_sec         = _collapsible_wrap(f"{c_id}-thankyou",  "&#9993; Thank-You Cards",       _ty_pod_strip(due_thankyou_reminders_for(child), c_bg, f"/schedule/{child}"), accent="#92400e")

    return f"""{_DL_CSS}
    <div class="card" style="border-left:5px solid {c_bg};background:{c_light};">
        {celebration_html}
        {_daily_bar_sec}
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
        {_lucy_sec}
        {'<div style="background:#fef9c3;border:1px solid #fde047;border-radius:10px;padding:12px 16px;margin-bottom:10px;font-size:0.88em;color:#854d0e;">&#128197; <strong>No ' + escape(weekday) + ' schedule yet</strong> for ' + escape(child) + '. Ask Mom to build the ' + escape(weekday) + ' template in <a href="/settings#s-systems" style="color:#92400e;font-weight:600;">Settings → Rule of Life</a>.</div>' if _frol_missing else ''}
        <div class="day-list">
            {day_list_html}
        </div>
        <div id="tasks" class="no-print"
             style="padding:8px 0 4px;">
            <form method="POST" action="/add-task"
                  style="display:flex;gap:8px;align-items:center;">
                <input type="hidden" name="assigned_to" value="{escape(child)}">
                <input type="hidden" name="return_url"
                       value="/schedule/{escape(child)}">
                <input type="text" name="text"
                       placeholder="+ Quick note or task for {escape(child)}&#8230;"
                       autocomplete="off"
                       style="flex:1;border:1.5px solid {c_bg}44;border-radius:8px;
                              padding:9px 12px;font-size:.88em;font-family:inherit;
                              color:#3d2b1f;background:#fff;">
                <button type="submit"
                        style="background:{c_bg};color:#fff;border:none;border-radius:8px;
                               padding:9px 16px;font-size:.88em;font-weight:600;
                               cursor:pointer;white-space:nowrap;flex-shrink:0;">
                    &#43; Add
                </button>
            </form>
        </div>
        {_ty_sec}
        {_goals_sec}
        {_profile_sec}
        {template_html}
    </div>
<script>
/* Hide tasks already marked done on page load so they don't reappear as visible checked items */
(function() {{
    document.querySelectorAll('[data-done="1"]').forEach(function(row) {{
        row.style.display = 'none';
    }});
}})();
function loadLucyBrief(child) {{
    var btn = document.getElementById('lucy-load-btn-' + child);
    var el  = document.getElementById('lucy-child-brief-' + child);
    if (btn) btn.style.display = 'none';
    if (el)  el.innerHTML = '<span style="color:#bbb;font-style:italic;">Loading&#8230;</span>';
    fetch('/lucy-child-brief/' + child)
        .then(function(r) {{ return r.json(); }})
        .then(function(d) {{
            if (el) el.innerHTML = d.html ||
                '<span style="color:#bbb;font-style:italic;">Not available.</span>';
        }})
        .catch(function() {{
            if (el) el.innerHTML =
                '<span style="color:#bbb;font-style:italic;">Could not load.</span>';
        }});
}}
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
</script>
{_COLLAPSIBLE_JS}"""


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


def render_child_dash_card(child: str, target_date_str: str = "", max_pending: int = 4) -> str:
    """
    Compact dashboard card — uses build_day_list (same source as the full Day
    List page) so task IDs are identical and check-offs synchronise instantly.
    Shows: carryover ↩, then school/manual tasks (up to max_pending at a time),
    then chores.

    For Lauren (parent), the card shows only her manual tasks — no chores,
    school steps, calendar events, or carryover — and bypasses the FROL
    day_list path entirely (Task #32).
    """
    normalized_date = normalize_date_query(target_date_str)
    packet     = generate_day_packet(normalized_date)
    iso        = packet["iso"]
    weekday    = packet["weekday"]
    date_label = packet["date_label"]

    _is_lauren = (child == "Lauren")

    # Lauren: skip FROL day_list (would be [] on most weekdays anyway).
    day_list = [] if _is_lauren else build_day_list(child, weekday, iso)

    # Merge calendar events into the day list (boys only — _gcal is boys-only).
    if not _is_lauren:
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

    if _is_lauren:
        try:
            from config import parent_color as _pcolor
            c_bg    = _pcolor("Lauren", "bg")
            c_light = _pcolor("Lauren", "light")
        except Exception:
            c_bg    = child_color(child, "bg")
            c_light = child_color(child, "light")
    else:
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

    # ── Lauren: populate queue directly from manual tasks (bypasses FROL) ──
    # Spec (Task #32): Lauren's card shows only her manual tasks. Wrap each
    # manual_tasks.json entry into the same shape `_dash_row` expects.
    if _is_lauren:
        try:
            from daily_schedule_engine import (
                get_manual_tasks_for_child_and_date as _gmt_l,
                _dl_done as _gd_l,
            )
            for _t in _gmt_l("Lauren", iso):
                _txt = (_t.get("text") or "").strip()
                if not _txt:
                    continue
                _tid = f"MANUAL::Lauren::{iso}::{_txt}"
                queue.append({
                    "text": _txt, "task_id": _tid,
                    "manual_id": _t.get("id", ""),
                    "done": _gd_l(progress, _tid),
                    "checkable": True, "is_header": False,
                    "due_date": _t.get("due_date", ""),
                    "is_due_soon": _t.get("is_due_soon", False),
                    "priority": _t.get("priority", "MEDIUM"),
                    "_section": "Task",
                })
        except Exception:
            pass

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
        tid_js  = _js_attr(item.get("task_id", ""))
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
        lbl_text   = item.get("text") or item.get("label") or ""
        # Pencil edit affordance — manual tasks only (not chores/school/events/carryover/done).
        # Uses pure HTML attribute escaping + a delegated click listener
        # (registered once in _DASH_JS) so that user text — which may contain
        # apostrophes, quotes, backslashes, or `<script>` payloads — is never
        # interpolated into a JS source context. Browser HTML-attribute parsing
        # handles all escaping; the listener reads raw values from dataset.
        manual_id_raw = item.get("manual_id", "")
        manual_id_e   = escape(manual_id_raw)
        lbl_e         = escape(lbl_text)
        due_e         = escape(item.get("due_date", ""))
        edit_btn = ""
        if manual_id_raw and not is_chore and not is_done:
            edit_btn = (
                f'<button type="button" aria-label="Edit task" data-dash-edit="1"'
                f' data-edit-tid="{tid}" data-edit-mid="{manual_id_e}"'
                f' data-edit-text="{lbl_e}" data-edit-due="{due_e}"'
                f' style="background:transparent;border:1px solid rgba(0,0,0,0.15);'
                f'color:#666;font-size:12px;line-height:1;padding:3px 6px;'
                f'border-radius:5px;cursor:pointer;font-family:inherit;flex-shrink:0;'
                f'margin-top:1px;">\u270f\ufe0f</button>'
            )
        add_btn = ""
        if not is_chore and not is_done:
            add_btn = (
                f'<button type="button" aria-label="Add to day" data-dash-add="1"'
                f' data-add-text="{lbl_e}" data-add-mid="{manual_id_e}"'
                f' data-add-iso="{escape(iso)}"'
                f' style="background:transparent;border:1px solid rgba(0,0,0,0.15);'
                f'color:#666;font-size:11px;line-height:1;padding:3px 6px;'
                f'border-radius:5px;cursor:pointer;font-family:inherit;flex-shrink:0;'
                f'margin-top:1px;white-space:nowrap;">+ Add</button>'
            )
        return (
            f'<div class="dash-task" data-dash-child="{c_id}" data-done="{done_d}"{chore_attr}'
            f' data-manual-id="{manual_id_e}"'
            f' id="task-{tid}" style="display:flex;align-items:flex-start;gap:8px;'
            f'padding:5px 0;border-bottom:1px solid rgba(0,0,0,0.05);{extra_style}">'
            f'<div style="flex:1;min-width:0;">'
            f'{sec_div}'
            f'<label for="lbl-{tid}" style="font-size:.88em;line-height:1.3;'
            f'cursor:pointer;{done_st}">{escape(lbl_text)}</label>'
            f'</div>'
            f'{edit_btn}'
            f'{add_btn}'
            f'<input type="checkbox" id="lbl-{tid}" {checked}'
            f' style="margin-top:3px;width:16px;height:16px;flex-shrink:0;accent-color:{c_bg};"'
            f' onchange="toggleDashTask(this,\'{tid_js}\',\'{c_id}\',\'{escape(iso)}\')">'
            f'</div>'
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

    # ── Secondary sort: due-date-aware for manual tasks (Task #32) ──────────
    # Tuple key (not is_manual, due_date_or_9999, priority_order). Manuals get
    # `not True == False == 0` and cluster FIRST, sorted among themselves by
    # due_date asc (overdue → today → future → undated "9999") then HIGH <
    # MEDIUM < LOW. Non-manuals all share key (True=1, "", 0); stable sort
    # preserves their existing relative order from the sort_time pass above
    # and they appear after the manual cluster. Putting manuals first ensures
    # the most-urgent ones win the `pending_shown < max_pending` visibility
    # slots before school steps consume the budget.
    _PRIO_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    def _due_sort_key(entry):
        item = entry.get("data") or {}
        # Detect manual tasks by task_id prefix (robust even when manual_id
        # is empty — e.g. older manual_tasks.json entries that pre-date the
        # `id` field). School/chore/carryover/event use SCHOOL::/CHORE::/
        # CARRY:: prefixes or are non-task kinds.
        _tid = str(item.get("task_id") or "")
        is_manual = (entry.get("kind") == "task"
                     and _tid.startswith("MANUAL::"))
        due = item.get("due_date") or "9999"
        pri = _PRIO_ORDER.get(item.get("priority", "MEDIUM"), 1)
        return (not is_manual, due, pri)
    combined.sort(key=_due_sort_key)

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
            elif pending_shown < max_pending:
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
var _TOV_HDR = {'Content-Type':'application/x-www-form-urlencoded'};
function _tovPost(params, cb) {
    fetch('/task-override', {method:'POST', headers:_TOV_HDR, body:params})
      .then(cb || function() { location.reload(); });
}
function _tovAct(tid, child, iso, label, action, postponeTo) {
    var p = 'task_id='+encodeURIComponent(tid)
          +'&child='+encodeURIComponent(child)
          +'&iso='+encodeURIComponent(iso)
          +'&label='+encodeURIComponent(label)
          +'&action='+encodeURIComponent(action)
          +'&json=1';
    if (postponeTo) p += '&postpone_to='+encodeURIComponent(postponeTo);
    _tovPost(p);
}
function _tovActTime(tid, child, iso, label) {
    var t = document.getElementById('tov-t-' + tid);
    if (!t || !t.value) return;
    _tovPost('task_id='+encodeURIComponent(tid)
           +'&child='+encodeURIComponent(child)
           +'&iso='+encodeURIComponent(iso)
           +'&label='+encodeURIComponent(label)
           +'&action=timed&time='+encodeURIComponent(t.value)+'&json=1');
}
function _tovClear(tid, child, iso) {
    _tovPost('task_id='+encodeURIComponent(tid)
           +'&child='+encodeURIComponent(child)
           +'&iso='+encodeURIComponent(iso)
           +'&action=clear&json=1');
}
/* ── Schedule modal (combines Time Today + Move Date + Recurring) ─── */
var _schedCtx = {};
function _schedOpen(tid, child, iso, label) {
    _schedCtx = {tid:tid, child:child, iso:iso, label:label};
    var m = document.getElementById('sched-modal');
    if (!m) return;
    var lbl = document.getElementById('sched-task-name');
    if (lbl) lbl.textContent = label;
    // Pre-fill time input with current time
    var ti = document.getElementById('sched-time-inp');
    if (ti) {
        var n = new Date();
        ti.value = n.getHours().toString().padStart(2,'0') + ':' + n.getMinutes().toString().padStart(2,'0');
    }
    // Pre-fill date input with tomorrow
    var di = document.getElementById('sched-date-inp');
    if (di) {
        try {
            var base = new Date(iso + 'T00:00:00');
            base.setDate(base.getDate() + 1);
            di.min = base.toISOString().split('T')[0];
            di.value = base.toISOString().split('T')[0];
        } catch(e) {}
    }
    m.classList.add('open');
}
function _schedClose() {
    var m = document.getElementById('sched-modal');
    if (m) m.classList.remove('open');
}
function _schedSetTime() {
    var ti = document.getElementById('sched-time-inp');
    if (!ti || !ti.value) return;
    _tovPost('task_id='+encodeURIComponent(_schedCtx.tid)
           +'&child='+encodeURIComponent(_schedCtx.child)
           +'&iso='+encodeURIComponent(_schedCtx.iso)
           +'&label='+encodeURIComponent(_schedCtx.label)
           +'&action=timed&time='+encodeURIComponent(ti.value)+'&json=1',
           function() { _schedClose(); location.reload(); });
}
function _schedMoveDate() {
    var di = document.getElementById('sched-date-inp');
    if (!di || !di.value) return;
    _tovPost('task_id='+encodeURIComponent(_schedCtx.tid)
           +'&child='+encodeURIComponent(_schedCtx.child)
           +'&iso='+encodeURIComponent(_schedCtx.iso)
           +'&label='+encodeURIComponent(_schedCtx.label)
           +'&action=postpone&postpone_to='+encodeURIComponent(di.value)+'&json=1',
           function() { _schedClose(); location.reload(); });
}
function _schedSetRecurring() {
    var freq = document.querySelector('input[name="sched-freq"]:checked');
    if (!freq) { alert('Pick a frequency first.'); return; }
    _tovPost('task_id='+encodeURIComponent(_schedCtx.tid)
           +'&child='+encodeURIComponent(_schedCtx.child)
           +'&iso='+encodeURIComponent(_schedCtx.iso)
           +'&label='+encodeURIComponent(_schedCtx.label)
           +'&action=recurring&frequency='+encodeURIComponent(freq.value)+'&json=1',
           function() { _schedClose(); location.reload(); });
}
/* ── Dash card inline edit (manual tasks only) ───────────────────────
   All DOM is built with createElement + addEventListener (NEVER innerHTML
   with string-concatenated event attrs) because `tid` is the composite
   `MANUAL::{child}::{iso}::{text}` and may contain apostrophes / quotes
   that would break inline handlers and open an XSS sink. */
function _dashEditClose(tid) {
    var p = document.getElementById('dash-edit-' + tid);
    if (p && p.parentNode) p.parentNode.removeChild(p);
}
function _dashEditMkBtn(label, bg, color, border, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    b.style.cssText = 'padding:5px 10px;font-size:.8em;background:' + bg
        + ';color:' + color + ';border:1px solid ' + border
        + ';border-radius:6px;cursor:pointer;font-family:inherit;font-weight:600;';
    b.addEventListener('click', onClick);
    return b;
}
function _dashEditOpen(tid, manualId, text, dueDate) {
    var row = document.getElementById('task-' + tid);
    if (!row) return;
    _dashEditClose(tid);
    var p = document.createElement('div');
    p.id = 'dash-edit-' + tid;
    p.dataset.tid = tid;
    p.dataset.manualId = manualId;
    p.style.cssText = 'background:#fff;border:1px solid #d7cec5;border-radius:8px;'
        + 'padding:8px;margin:2px 0 8px;display:flex;flex-direction:column;gap:6px;'
        + 'box-shadow:0 1px 4px rgba(0,0,0,.06);';
    var ti = document.createElement('input');
    ti.type = 'text';
    ti.className = 'de-text';
    ti.value = text || '';
    ti.style.cssText = 'width:100%;padding:6px 8px;border:1px solid #d7cec5;'
        + 'border-radius:6px;font-family:inherit;font-size:.92em;box-sizing:border-box;';
    var dr = document.createElement('div');
    dr.style.cssText = 'display:flex;align-items:center;gap:6px;flex-wrap:wrap;';
    var dlbl = document.createElement('label');
    dlbl.textContent = 'Due:';
    dlbl.style.cssText = 'font-size:.75em;color:#7c4a2d;font-weight:600;';
    var di = document.createElement('input');
    di.type = 'date';
    di.className = 'de-date';
    di.value = dueDate || '';
    di.style.cssText = 'padding:4px 6px;border:1px solid #d7cec5;border-radius:6px;'
        + 'font-family:inherit;font-size:.85em;';
    dr.appendChild(dlbl); dr.appendChild(di);
    var br = document.createElement('div');
    br.style.cssText = 'display:flex;gap:6px;justify-content:flex-end;';
    br.appendChild(_dashEditMkBtn('Cancel', '#f5f5f5', '#666', '#e0d8d0',
        function() { _dashEditClose(tid); }));
    br.appendChild(_dashEditMkBtn('Done', '#dcfce7', '#166534', '#86efac',
        function() { _dashEditDone(p); }));
    br.appendChild(_dashEditMkBtn('Save', '#7c4a2d', '#fff', '#7c4a2d',
        function() { _dashEditSave(p); }));
    p.appendChild(ti); p.appendChild(dr); p.appendChild(br);
    row.parentNode.insertBefore(p, row.nextSibling);
    ti.focus(); ti.select();
}
function _dashEditSave(p) {
    if (!p) return;
    var mid = p.dataset.manualId || '';
    if (!mid) { alert('Missing task id'); return; }
    var ti = p.querySelector('.de-text');
    var di = p.querySelector('.de-date');
    var newText = ti ? ti.value.trim() : '';
    var newDate = di ? di.value : '';
    if (!newText) { alert('Text cannot be blank'); return; }
    fetch('/task-update', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'id=' + encodeURIComponent(mid)
            + '&text=' + encodeURIComponent(newText)
            + '&due_date=' + encodeURIComponent(newDate)
    }).then(function(r) { return r.json(); })
      .then(function(j) {
        if (j && j.ok) { location.reload(); }
        else { alert((j && j.error) || 'Save failed'); }
      })
      .catch(function() { alert('Save failed'); });
}
/* Done: programmatically tick the existing checkbox so we reuse the
   proven /toggle-task + undo-snack flow. /task-done returns a 303
   redirect, not JSON, so we cannot fetch it from JS reliably. */
function _dashEditDone(p) {
    if (!p) return;
    var tid = p.dataset.tid || '';
    var row = tid ? document.getElementById('task-' + tid) : null;
    var cb  = row ? row.querySelector('input[type="checkbox"]') : null;
    _dashEditClose(tid);
    if (cb && !cb.checked) {
        cb.checked = true;
        cb.dispatchEvent(new Event('change'));
    }
}
/* Delegated listener: pencil buttons render with data-* attrs only
   (no inline onclick), so user-controlled text never enters a JS
   source context. The browser's HTML-attribute parser handles all
   escaping. We bind once on document for full event delegation. */
(function() {
    if (document._dashEditDelegated) return;
    document._dashEditDelegated = true;
    document.addEventListener('click', function(ev) {
        var b = ev.target.closest && ev.target.closest('[data-dash-edit]');
        if (!b) return;
        ev.preventDefault();
        ev.stopPropagation();
        _dashEditOpen(b.dataset.editTid || '', b.dataset.editMid || '',
                      b.dataset.editText || '', b.dataset.editDue || '');
    });
})();
// Inject Schedule modal once into DOM
(function(){
  if (document.getElementById('sched-modal')) return;
  var m = document.createElement('div');
  m.id = 'sched-modal';
  m.innerHTML = '<div class="sched-box">'
    + '<div class="sched-title">&#128197; Schedule Task</div>'
    + '<div class="sched-task-name" id="sched-task-name"></div>'
    + '<div class="sched-sect">&#9200; Time today</div>'
    + '<div class="sched-row">'
    +   '<input id="sched-time-inp" type="time" class="sched-inp">'
    +   '<button class="sched-sub-btn" onclick="_schedSetTime()">Set Time</button>'
    + '</div>'
    + '<hr class="sched-divider">'
    + '<div class="sched-sect">&#128197; Move to date</div>'
    + '<div class="sched-row">'
    +   '<input id="sched-date-inp" type="date" class="sched-inp">'
    +   '<button class="sched-sub-btn" onclick="_schedMoveDate()">Move</button>'
    + '</div>'
    + '<hr class="sched-divider">'
    + '<div class="sched-sect">&#128260; Make recurring</div>'
    + '<div class="sched-freq">'
    +   '<label><input type="radio" name="sched-freq" value="daily"> Daily</label>'
    +   '<label><input type="radio" name="sched-freq" value="weekdays"> Weekdays</label>'
    +   '<label><input type="radio" name="sched-freq" value="weekly"> Weekly</label>'
    + '</div>'
    + '<div style="margin-top:10px;">'
    +   '<button class="sched-sub-btn" style="width:100%;" onclick="_schedSetRecurring()">&#10003; Set Recurring</button>'
    + '</div>'
    + '<button class="sched-cancel" onclick="_schedClose()">Cancel</button>'
    + '</div>';
  m.addEventListener('click', function(e){ if(e.target===m) _schedClose(); });
  document.body.appendChild(m);
})();

/* ── Dash row + Add to day (delegated click → time-picker → POST) ──── */
document.addEventListener('click', function(e) {
    var t = e.target;
    if (t && t.matches && t.matches('[data-dash-add="1"]')) {
        e.preventDefault();
        _dashAddToDay(
            t.getAttribute('data-add-text') || '',
            t.getAttribute('data-add-mid')  || '',
            t.getAttribute('data-add-iso')  || '',
            t
        );
    }
});

function _dashAddToDay(text, manualId, iso, btn) {
    _apqOpenPicker(btn, function(time) {
        btn.textContent = '\u2713 Added';
        btn.style.color = '#27ae60';
        btn.style.borderColor = '#27ae60';
        btn.disabled = true;
        var body = 'iso=' + encodeURIComponent(iso)
                 + '&text=' + encodeURIComponent(text)
                 + '&source=task'
                 + '&task_id=' + encodeURIComponent(manualId || '');
        if (time) body += '&time=' + encodeURIComponent(time);
        fetch('/add-to-plan-quick', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: body
        });
    });
}

/* Shared inline time-picker popover (idempotent — safe to redeclare) */
function _apqOpenPicker(btn, onPick) {
    if (window._apqCurrent) {
        try { window._apqCurrent.remove(); } catch (e) {}
        window._apqCurrent = null;
    }
    var now = new Date();
    var mins = now.getMinutes();
    var rounded = Math.round(mins / 30) * 30;
    if (rounded === 60) { now.setHours(now.getHours() + 1); rounded = 0; }
    var hh = String(now.getHours()).padStart(2, '0');
    var mm = String(rounded).padStart(2, '0');
    var defaultTime = hh + ':' + mm;

    var pop = document.createElement('div');
    pop.style.cssText = 'position:absolute;background:#fff;border:1px solid #ccc;'
        + 'border-radius:8px;padding:8px;z-index:9998;'
        + 'box-shadow:0 4px 12px rgba(0,0,0,.15);display:flex;align-items:center;'
        + 'gap:6px;font-family:inherit;';

    var input = document.createElement('input');
    input.type = 'time';
    input.value = defaultTime;
    input.style.cssText = 'font-size:0.85em;padding:3px 5px;border:1px solid #ccc;'
        + 'border-radius:4px;font-family:inherit;';

    var confirmBtn = document.createElement('button');
    confirmBtn.type = 'button';
    confirmBtn.textContent = 'Confirm';
    confirmBtn.style.cssText = 'font-size:0.78em;padding:4px 10px;border-radius:5px;'
        + 'background:#27ae60;color:#fff;border:none;cursor:pointer;font-family:inherit;';

    var skipBtn = document.createElement('button');
    skipBtn.type = 'button';
    skipBtn.textContent = 'Skip';
    skipBtn.style.cssText = 'font-size:0.78em;padding:4px 10px;border-radius:5px;'
        + 'background:#eee;color:#333;border:1px solid #ccc;cursor:pointer;font-family:inherit;';

    pop.appendChild(input);
    pop.appendChild(confirmBtn);
    pop.appendChild(skipBtn);

    var rect = btn.getBoundingClientRect();
    pop.style.left = (rect.left + window.scrollX) + 'px';
    pop.style.top  = (rect.bottom + window.scrollY + 4) + 'px';
    document.body.appendChild(pop);
    window._apqCurrent = pop;

    function _close() {
        try { pop.remove(); } catch (e) {}
        if (window._apqCurrent === pop) window._apqCurrent = null;
    }
    confirmBtn.addEventListener('click', function() {
        var t = (input.value || '').trim();
        _close();
        onPick(t);
    });
    skipBtn.addEventListener('click', function() {
        _close();
        onPick('');
    });
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

    # ── Viewer-scoping: child viewers see only their own dash card ───────────
    import auth as _auth
    _viewer = _auth.get_viewer()
    if _viewer and not _auth.is_admin(_viewer):
        _my_name = next((c for c in CHILDREN if c.lower() == _viewer.lower()), None)
        cards_html = render_child_dash_card(_my_name, normalized_date) if _my_name else ""
    else:
        cards_html = "".join(
            render_child_dash_card(child, normalized_date) for child in CHILDREN
        )
        # Task #32: Lauren's dash card (manual-tasks-only, 10-item limit).
        cards_html += render_child_dash_card("Lauren", normalized_date, max_pending=10)

    # "What's happening now" quick strip
    try:
        from render_schedule_support import get_current_slot
        _cur_label, _now_label, _next_label, _next_act = get_current_slot()
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

    # Show due thank-you card reminders as a prominent suggested-task widget
    # (replaces the old compact strip — the widget lets Lauren assign to any POD)
    _family_ty_strip = _ty_suggested_tasks_widget(due_thankyou_reminders_for("Family"), "/today")

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
    exercise_print_html = _render_exercise_block_print(child, weekday)
    if exercise_print_html:
        sections_html += exercise_print_html

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

    meal_icons  = {"breakfast": "☀", "lunch": "▸", "dinner": "●", "dessert": "◇", "snacks": "◆"}
    meal_labels = {"breakfast": "Breakfast", "lunch": "Lunch",
                   "dinner": "Dinner", "dessert": "Dessert", "snacks": "Snacks"}
    from render_meals import slot_display_text as _slot_text
    boys_help   = _slot_text(slots.get("boys_help"))

    rows = ""
    for slot in ["breakfast", "lunch", "dinner", "dessert", "snacks"]:
        val = _slot_text(slots.get(slot))
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