"""
render_schedule_support.py — Family schedule engine, now/next strip, timeline.
Kept separate from render_schedule.py to avoid circular imports
(render_schedule imports this, not the other way around).
"""
from datetime import date, timedelta
from html import escape

from config import SCHEDULE_DAYS
from data_helpers import (
    load_family_schedule, save_family_schedule,
    load_monthly_planner,
)
from ui_helpers import html_page, page_header, render_status_message


# ── Eastern time ──────────────────────────────────────────────────────────────
def get_eastern_now():
    """Return current datetime in the configured timezone, falling back to Eastern then local."""
    from datetime import datetime
    from config import get_timezone
    tz_name = get_timezone()
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        try:
            import pytz
            return datetime.now(pytz.timezone(tz_name))
        except Exception:
            return datetime.now()


# ── Half-hour grid ────────────────────────────────────────────────────────────
def generate_half_hour_times() -> list:
    """Generate half-hour time slots using hours from app settings."""
    from config import get_schedule_hours
    start, end = get_schedule_hours()
    # Clamp to sane range
    start = max(0,  min(start, 22))
    end   = max(start + 1, min(end, 24))
    slots = []
    for h in range(start, end):
        for m in (0, 30):
            ampm   = "AM" if h < 12 else "PM"
            disp_h = h if h <= 12 else h - 12
            if disp_h == 0: disp_h = 12
            slots.append(f"{disp_h}:{m:02d} {ampm}")
    return slots


def _slot_minutes(label: str) -> int:
    try:
        h_part, rest = label.strip().split(":")
        m_part, ampm = rest.split(" ")
        h = int(h_part); m = int(m_part)
        if ampm == "PM" and h != 12: h += 12
        if ampm == "AM" and h == 12: h = 0
        return h * 60 + m
    except Exception:
        return -1


# ── Current slot ──────────────────────────────────────────────────────────────
def get_current_slot(schedule: dict) -> tuple:
    now        = get_eastern_now()
    now_minutes = now.hour * 60 + now.minute
    times      = schedule.get("times", []) or generate_half_hour_times()
    today_name = now.strftime("%A")
    today_slots = schedule.get("days", {}).get(today_name, {})

    current_idx = -1
    for i, t in enumerate(times):
        if _slot_minutes(t) <= now_minutes:
            current_idx = i

    current_label = current_activity = next_label = next_activity = ""
    if current_idx >= 0:
        current_label    = times[current_idx]
        current_activity = today_slots.get(current_label, "")
        if not current_activity and ":30 " in current_label:
            current_activity = today_slots.get(current_label.replace(":30 ", ":00 "), "")
        if current_idx + 1 < len(times):
            next_label    = times[current_idx + 1]
            next_activity = today_slots.get(next_label, "")
            if not next_activity and ":30 " in next_label:
                next_activity = today_slots.get(next_label.replace(":30 ", ":00 "), "")
    return current_label, current_activity, next_label, next_activity


# ── Now / Next strip ──────────────────────────────────────────────────────────
def render_now_next_strip() -> str:
    schedule = load_family_schedule()
    cur_label, cur_activity, next_label, next_activity = get_current_slot(schedule)
    if not cur_label and not next_label:
        return ""
    cur_act_html  = escape(cur_activity)  if cur_activity  else "<span style='color:#aaa;'>Free time</span>"
    next_act_html = escape(next_activity) if next_activity else "<span style='color:#aaa;'>Free time</span>"
    next_block = f"""
        <div style="flex:1;min-width:180px;background:#f9f9f9;border:1px solid #e0e0e0;
                    border-left:5px solid #aaa;border-radius:10px;padding:12px 14px;">
            <div style="font-size:0.78em;font-weight:bold;color:#888;text-transform:uppercase;
                        letter-spacing:1px;margin-bottom:4px;">Next · {escape(next_label)}</div>
            <div style="font-size:1.05em;color:#555;">{next_act_html}</div>
        </div>""" if next_label else ""
    return f"""
    <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:stretch;">
        <div style="flex:1;min-width:180px;background:#fff7ed;border:1px solid #f0d9c0;
                    border-left:5px solid #e67e22;border-radius:10px;padding:12px 14px;">
            <div style="font-size:0.78em;font-weight:bold;color:#e67e22;text-transform:uppercase;
                        letter-spacing:1px;margin-bottom:4px;">Now · {escape(cur_label)}</div>
            <div style="font-size:1.05em;font-weight:bold;color:#333;">{cur_act_html}</div>
        </div>
        {next_block}
        <div style="flex:0 0 auto;display:flex;align-items:center;">
            <a class="link-button" href="/family-schedule">Full Schedule</a>
        </div>
    </div>"""


# ── Today timeline ────────────────────────────────────────────────────────────
def render_today_timeline(weekday: str = "") -> str:
    schedule   = load_family_schedule()
    times      = schedule.get("times", []) or generate_half_hour_times()
    now        = get_eastern_now()
    # Use the supplied weekday (planned day) if given; fall back to actual today.
    today_name  = weekday if weekday else now.strftime("%A")
    is_today    = (today_name == now.strftime("%A"))
    today_slots = schedule.get("days", {}).get(today_name, {})
    cur_label, _, _, _ = get_current_slot(schedule)
    if not times:
        return "<p class='muted'>No schedule loaded.</p>"
    now_minutes = now.hour * 60 + now.minute
    rows = ""
    for t in times:
        activity = today_slots.get(t, "")
        if not activity and ":30 " in t:
            activity = today_slots.get(t.replace(":30 ", ":00 "), "")
        sm      = _slot_minutes(t)
        # Only show "now" indicators when actually viewing today
        is_now  = is_today and (t == cur_label)
        is_half = t.endswith(":30 AM") or t.endswith(":30 PM")
        in_near_future = is_today and (now_minutes <= sm <= now_minutes + 60)
        if not activity and not is_now and not in_near_future:
            continue
        if is_now:
            bg="#fff7ed"; border="border-left:4px solid #e67e22;"; time_color="#e67e22"; time_fw="bold"; now_dot=" 🟠"; padding="7px 10px"
        elif is_half:
            bg="transparent"; border="border-left:4px solid transparent;"; time_color="#bbb"; time_fw="normal"; now_dot=""; padding="3px 10px"
        else:
            bg="transparent"; border="border-left:4px solid transparent;"; time_color="#999"; time_fw="600"; now_dot=""; padding="5px 10px"
        act_color = "#333" if activity else "#ccc"
        act_text  = escape(activity) if activity else "—"
        font_size = "0.88em" if is_half else "0.95em"
        rows += f"""
        <div style="display:grid;grid-template-columns:76px 1fr;gap:8px;padding:{padding};background:{bg};{border}border-radius:6px;margin-bottom:1px;">
            <div style="font-size:0.82em;color:{time_color};font-weight:{time_fw};padding-top:1px;white-space:nowrap;">{escape(t)}{now_dot}</div>
            <div style="font-size:{font_size};color:{act_color};">{act_text}</div>
        </div>"""
    if not rows:
        rows = f"<p class='muted' style='padding:8px 10px;'>No schedule entries for {escape(today_name)}.</p>"
    return f"""
    <div style="margin-top:4px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <strong>{escape(today_name)}'s Timeline</strong>
            <a class="link-button" href="/settings#s-systems">Edit schedule</a>
        </div>
        <div style="max-height:420px;overflow-y:auto;padding-right:4px;">{rows}</div>
    </div>"""


# ── Litany block ──────────────────────────────────────────────────────────────
def render_litany_block() -> str:
    planner = load_monthly_planner()
    lines   = planner.get("litany_to_begin_again", [])
    if not lines:
        return ""
    lines_html = "".join(f"<div style='margin:3px 0;font-size:0.92em;color:#444;'>{escape(l)}</div>" for l in lines)
    return f"""
    <div class="card" style="border-left:4px solid #7c4a2d;background:#fdfaf7;">
        <details>
            <summary style="cursor:pointer;font-weight:600;color:#7c4a2d;font-size:0.95em;
                            list-style:none;display:flex;align-items:center;gap:8px;">
                <span>✝</span><span>Litany to Begin Again</span>
                <span style="margin-left:auto;font-size:0.8em;color:#aaa;">tap to open</span>
            </summary>
            <div style="margin-top:12px;padding-top:10px;border-top:1px solid #f0e8e0;">
                <p style="font-size:0.8em;color:#aaa;margin-bottom:8px;font-style:italic;">
                    Compiled from the words of Venerable Bruno Lanteri, OMV</p>
                {lines_html}
            </div>
        </details>
    </div>"""


# ── Family schedule page (read-only) ─────────────────────────────────────────
def render_family_schedule_page(status_message: str = "") -> str:
    body = f"""
    {page_header("Family Schedule")}
    {render_status_message(status_message)}

    <div class="two-col">
        <div>
            <h2>Today's Timeline</h2>
            <div class="card">{render_today_timeline()}</div>
        </div>
        <div>
            <h2>Now &amp; Next</h2>
            <div class="card">{render_now_next_strip()}</div>

            <div class="card" style="margin-top:4px;">
                <p class="small" style="margin-bottom:8px;">
                    To edit the Family Rule of Life, go to Settings.
                </p>
                <a class="link-button" href="/settings#s-systems">Edit Rule of Life →</a>
            </div>
        </div>
    </div>"""
    return html_page("Family Schedule", body)
