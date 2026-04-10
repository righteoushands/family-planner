"""
render_morning_anchor.py — Morning Anchor (Step 0) and Evening Anchor (Step 5)
for the Plan My Day page.

Morning Anchor:
  - Mode selector: Home / Travel / Modified
  - Capacity tag: High / Medium / Low
  - This Day in History (Wikipedia On This Day API)
  - Gospel of the Day (USCCB link + date label)
  - Saint of the Day (structured from liturgical data)
  - Quote of the Day (curated by liturgical season)
  - Gospel Reflection Question (weekday-based)
  - Sunday Family Reflection Question
  - School Launch Ritual checklist

Evening Anchor:
  - 11-item checklist (from Family OS document)
  - Brain Dump textarea → feeds mom notes
  - Marriage Connection Window reminder
  - Persists checkboxes in daily plan JSON

Both sections store state in the daily plan JSON under "anchor" key.
"""
import json
from datetime import date
from html import escape


# ── Curated quotes by liturgical season ───────────────────────────────────────
SEASON_QUOTES = {
    "Advent": [
        ("\"Come, Lord Jesus.\"", "Rev 22:20"),
        ("\"Prepare the way of the Lord, make his paths straight.\"", "Mt 3:3"),
        ("\"Be patient, brothers, until the coming of the Lord.\"", "Jas 5:7"),
    ],
    "Christmas": [
        ("\"The Word became flesh and dwelt among us.\"", "Jn 1:14"),
        ("\"For to us a child is born, to us a son is given.\"", "Is 9:6"),
        ("\"Glory to God in the highest, and on earth peace.\"", "Lk 2:14"),
    ],
    "Lent": [
        ("\"Rend your hearts, not your garments.\"", "Joel 2:13"),
        ("\"Man does not live on bread alone.\"", "Mt 4:4"),
        ("\"Return to me with all your heart.\"", "Joel 2:12"),
        ("\"Behold, I am doing a new thing.\"", "Is 43:19"),
    ],
    "Holy Week": [
        ("\"Father, into your hands I commend my spirit.\"", "Lk 23:46"),
        ("\"Not my will, but yours, be done.\"", "Lk 22:42"),
    ],
    "Easter": [
        ("\"I am the resurrection and the life.\"", "Jn 11:25"),
        ("\"Do not be afraid; I know that you seek Jesus who was crucified. He is not here; he has risen.\"", "Mt 28:5-6"),
        ("\"Peace be with you.\"", "Jn 20:19"),
    ],
    "Ordinary Time": [
        ("\"Be still and know that I am God.\"", "Ps 46:10"),
        ("\"You shall love the Lord your God with all your heart.\"", "Mk 12:30"),
        ("\"Ask, and it will be given to you.\"", "Mt 7:7"),
        ("\"I can do all things through him who strengthens me.\"", "Phil 4:13"),
        ("\"The Lord is my shepherd; I shall not want.\"", "Ps 23:1"),
        ("\"Have no anxiety at all, but in everything, by prayer and petition... make your requests known to God.\"", "Phil 4:6"),
    ],
}

# Default for unknown seasons
SEASON_QUOTES["default"] = SEASON_QUOTES["Ordinary Time"]

# ── Reflection questions by weekday ───────────────────────────────────────────
WEEKDAY_REFLECTIONS = {
    "Monday":    "What is one thing from Sunday's Mass that I want to carry into this week?",
    "Tuesday":   "Where did I see God's hand yesterday, and where might I miss it today?",
    "Wednesday": "What is one concrete way I can serve someone in my home today?",
    "Thursday":  "Am I living today as if it matters eternally? What needs to change?",
    "Friday":    "In what area of my life am I being called to sacrifice or let go?",
    "Saturday":  "How has God been faithful to me this week? What am I grateful for?",
    "Sunday":    "As a family: what is one thing we want to offer to God this week?",
}

SUNDAY_FAMILY_REFLECTION = (
    "As a family, what is one thing we want to offer to God this week? "
    "What area of our life together needs the most prayer right now?"
)

# ── Evening checklist items ────────────────────────────────────────────────────
EVENING_CHECKLIST = [
    ("dinner_cleanup",   "Dinner cleanup complete"),
    ("kitchen_jobs",     "Kitchen jobs completed (JP + Joseph)"),
    ("showers",          "Showers done"),
    ("clothes_out",      "Clothes laid out for tomorrow"),
    ("bags_ready",       "Bags / materials ready"),
    ("devices_charging", "Devices charging"),
    ("review_tomorrow",  "Reviewed tomorrow briefly"),
    ("evening_prayer",   "Evening prayer"),
    ("marriage_window",  "Marriage Connection Window (10 min) — check-in · appreciation · logistics · prayer"),
]


# ── External data helpers ─────────────────────────────────────────────────────
def fetch_this_day_in_history(for_date: date) -> list:
    """
    Fetch up to 3 'On This Day' events from Wikipedia.
    Returns list of {'year': str, 'text': str} dicts.
    Falls back to empty list on any failure.
    """
    try:
        import urllib.request
        month = for_date.month
        day   = for_date.day
        url   = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{month}/{day}"
        req   = urllib.request.Request(url, headers={"User-Agent": "FamilyPlanner/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data   = json.loads(resp.read().decode())
        events = data.get("events", [])
        # Pick 3 spread across history: one ancient/medieval, one modern, one recent
        if len(events) >= 3:
            third  = len(events) // 3
            picked = [events[0], events[third], events[-1]]
        else:
            picked = events[:3]
        return [
            {"year": str(e.get("year", "?")), "text": e.get("text", "")}
            for e in picked
        ]
    except Exception:
        return []


def _get_quote_for_day(season: str, for_date: date) -> tuple:
    """Return (quote_text, attribution) for today, cycling by day-of-year."""
    quotes = SEASON_QUOTES.get(season, SEASON_QUOTES["default"])
    idx    = for_date.timetuple().tm_yday % len(quotes)
    return quotes[idx]


def _get_anchor_state(iso: str) -> dict:
    """Load anchor state (mode, capacity, evening checks) from daily plan JSON."""
    try:
        from render_daily_plan import load_daily_plan
        plan = load_daily_plan(iso)
        return plan.get("anchor", {})
    except Exception:
        return {}


def save_anchor_state(iso: str, updates: dict):
    """Merge updates into the anchor dict in the daily plan JSON."""
    try:
        from render_daily_plan import load_daily_plan, save_daily_plan
        plan   = load_daily_plan(iso)
        anchor = plan.get("anchor", {})
        anchor.update(updates)
        plan["anchor"] = anchor
        save_daily_plan(plan)
    except Exception:
        pass


# ── Morning Anchor ────────────────────────────────────────────────────────────
def render_morning_anchor(iso: str, weekday: str, date_label: str,
                          for_date: date) -> str:
    """
    Step 0 on Plan My Day: the full Morning Anchor card.
    """
    from render_liturgical import get_day_info

    anchor      = _get_anchor_state(iso)
    mode        = anchor.get("mode", "Home")
    capacity    = anchor.get("capacity", "")
    john_status = anchor.get("john_status", "")
    james_note  = anchor.get("james_note", "")

    lit       = get_day_info(for_date)
    season    = lit.get("season", "Ordinary Time")
    feast     = lit.get("feast_name", "")
    is_sunday = (weekday == "Sunday")

    # ── Mode selector ────────────────────────────────────────────────────────
    mode_buttons = ""
    for m, icon in [("Home","🏠"), ("Travel","🚗"), ("Modified","⚡")]:
        active = "background:#8b5a3c;color:white;" if m == mode else "background:#f0ebe4;color:#555;"
        mode_buttons += (
            f'<button onclick="anchorSetMode(\'{m}\')" id="mode-btn-{m}" '
            f'style="{active}padding:5px 14px;font-size:0.82em;font-weight:600;'
            f'border:none;border-radius:6px;cursor:pointer;font-family:inherit;">'
            f'{icon} {m}</button>'
        )

    # ── Capacity tag ─────────────────────────────────────────────────────────
    cap_buttons = ""
    for cap, color, label in [
        ("High",   "#27ae60", "🟢 High"),
        ("Medium", "#e67e22", "🟡 Medium"),
        ("Low",    "#e74c3c", "🔴 Low"),
    ]:
        active = f"background:{color};color:white;" if cap == capacity else "background:#f0ebe4;color:#555;"
        cap_buttons += (
            f'<button onclick="anchorSetCap(\'{cap}\')" id="cap-btn-{cap}" '
            f'style="{active}padding:5px 14px;font-size:0.82em;font-weight:600;'
            f'border:none;border-radius:6px;cursor:pointer;font-family:inherit;">'
            f'{label}</button>'
        )

    # ── John status ───────────────────────────────────────────────────────────
    john_opts = [
        ("At office",   "\U0001f3e2"),
        ("WFH",         "\U0001f4bb"),
        ("Traveling",   "\u2708\ufe0f"),
        ("Day off",     "\u2600\ufe0f"),
    ]
    john_buttons = ""
    for jval, jico in john_opts:
        active  = "background:#2563eb;color:white;" if jval == john_status else "background:#f0ebe4;color:#555;"
        jval_id = jval.replace(" ", "-")
        john_buttons += (
            f'<button onclick="anchorSetJohn(\'{jval}\')" id="john-btn-{jval_id}" '
            f'style="{active}padding:5px 12px;font-size:0.82em;font-weight:600;'
            f'border:none;border-radius:6px;cursor:pointer;font-family:inherit;">'
            f'{jico} {jval}</button>'
        )

    # ── James note ────────────────────────────────────────────────────────────
    james_note_esc = escape(james_note)

    # ── This Day in History ───────────────────────────────────────────────────
    history_items = fetch_this_day_in_history(for_date)
    if history_items:
        history_html = "".join(
            f'<div style="padding:5px 0;border-bottom:1px solid #f5f0eb;">'
            f'<span style="font-size:0.75em;font-weight:700;color:#8b5a3c;'
            f'min-width:36px;display:inline-block;">{escape(h["year"])}</span>'
            f'<span style="font-size:0.85em;">{escape(h["text"][:140])}</span>'
            f'</div>'
            for h in history_items
        )
    else:
        history_html = '<p class="muted" style="font-size:0.85em;">Unavailable offline.</p>'

    # ── Gospel + Saint ────────────────────────────────────────────────────────
    readings_url = f"https://bible.usccb.org/bible/readings/{for_date.strftime('%m%d%y')}.cfm"

    # Try rich saint data first
    try:
        from saint_data import get_saint_html_card, fetch_saint_data as _fsd
        _sd = _fsd(for_date)
        if _sd.get("name"):
            feast = feast or _sd["name"]
        if _sd.get("usccb_link"):
            readings_url = _sd["usccb_link"]
        saint_html = get_saint_html_card(for_date, dark=False)
    except Exception:
        saint_name = feast if feast else "See USCCB calendar"
        saint_url  = "https://mycatholic.life/saints/saints-of-the-liturgical-year/"
        saint_html = f"""
    <div style="padding:10px 0;border-bottom:1px solid #f5f0eb;">
        <div style="font-size:0.75em;font-weight:700;text-transform:uppercase;
                    letter-spacing:0.08em;color:#aaa;margin-bottom:4px;">Saint of the day</div>
        <div style="font-size:0.92em;font-weight:600;">
            {escape(saint_name) if feast else '<span style="color:#aaa;">No feast today</span>'}
        </div>
        <a href="{saint_url}" target="_blank"
           style="font-size:0.78em;color:#7c4a2d;margin-top:2px;display:inline-block;">
            Full biography ↗
        </a>
    </div>"""

    # ── Quote of the day ──────────────────────────────────────────────────────
    quote_text, quote_attr = _get_quote_for_day(season, for_date)
    quote_html = f"""
    <div style="padding:10px 0;border-bottom:1px solid #f5f0eb;">
        <div style="font-size:0.75em;font-weight:700;text-transform:uppercase;
                    letter-spacing:0.08em;color:#aaa;margin-bottom:6px;">Quote of the day</div>
        <div style="font-size:0.9em;font-style:italic;color:#333;line-height:1.5;
                    border-left:3px solid #8b5a3c;padding-left:10px;">
            {escape(quote_text)}
        </div>
        <div style="font-size:0.75em;color:#888;margin-top:4px;padding-left:13px;">
            — {escape(quote_attr)}
        </div>
    </div>"""

    # ── Reflection question ───────────────────────────────────────────────────
    reflection = WEEKDAY_REFLECTIONS.get(weekday, WEEKDAY_REFLECTIONS["Monday"])
    family_q   = f'<div style="margin-top:8px;padding:8px 10px;background:#fef9c3;border-radius:7px;font-size:0.85em;"><strong>Family question:</strong> {escape(SUNDAY_FAMILY_REFLECTION)}</div>' if is_sunday else ""

    reflection_html = f"""
    <div style="padding:10px 0;border-bottom:1px solid #f5f0eb;">
        <div style="font-size:0.75em;font-weight:700;text-transform:uppercase;
                    letter-spacing:0.08em;color:#aaa;margin-bottom:6px;">
            Gospel reflection
        </div>
        <div style="font-size:0.88em;color:#333;line-height:1.5;font-style:italic;">
            {escape(reflection)}
        </div>
        {family_q}
    </div>"""

    # ── School Launch Ritual ──────────────────────────────────────────────────
    launch_checks = anchor.get("launch", {})
    launch_items  = [
        ("gather",  "Gather boys at the table"),
        ("review",  "Review today's plan together"),
        ("goal",    "State the school goal for today"),
        ("prayer",  "Short prayer or scripture verse"),
        ("begin",   "Begin — Math first"),
    ]
    launch_rows = ""
    for key, label in launch_items:
        checked   = launch_checks.get(key, False)
        chk_style = "color:#27ae60;" if checked else "color:#ccc;"
        icon      = "☑" if checked else "☐"
        done_style = "text-decoration:line-through;opacity:0.5;" if checked else ""
        launch_rows += (
            f'<div style="display:flex;align-items:center;gap:8px;padding:4px 0;">'
            f'<button onclick="anchorLaunch(\'{key}\')" '
            f'style="background:none;border:none;cursor:pointer;font-size:1em;'
            f'{chk_style}padding:0;font-family:inherit;">{icon}</button>'
            f'<span style="font-size:0.88em;{done_style}">{escape(label)}</span>'
            f'</div>'
        )
    all_launched = all(launch_checks.get(k, False) for k, _ in launch_items)
    launch_badge = (
        '<span style="background:#eef7ee;border:1px solid #c3e0c3;color:#2a5a2a;'
        'font-size:0.72em;padding:2px 8px;border-radius:999px;font-weight:700;">✓ Launched</span>'
        if all_launched else ""
    )

    launch_html = f"""
    <div style="padding:10px 0;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            <div style="font-size:0.75em;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.08em;color:#aaa;">School launch ritual</div>
            {launch_badge}
        </div>
        {launch_rows}
    </div>"""

    # Pre-compute to avoid strftime-with-quotes inside triple-quoted f-string
    _anchor_date_label = escape(for_date.strftime('%B %d'))

    _anchor_date_label = escape(for_date.strftime('%B %d'))

    return f"""
    <div id="s-morning" class="plan-section">
        <div class="plan-section-label">Step 0 — Morning anchor</div>

        <!-- Mode + Capacity + John + James row -->
        <div class="card card-tight" style="padding:14px 16px;margin-bottom:10px;">
            <div style="display:flex;align-items:flex-start;flex-wrap:wrap;gap:20px;">
                <div style="flex:1;min-width:140px;">
                    <div style="font-size:0.68em;font-weight:800;text-transform:uppercase;
                                letter-spacing:0.1em;color:var(--gold);margin-bottom:8px;">Mode</div>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;">{mode_buttons}</div>
                </div>
                <div style="flex:1;min-width:180px;">
                    <div style="font-size:0.68em;font-weight:800;text-transform:uppercase;
                                letter-spacing:0.1em;color:var(--gold);margin-bottom:8px;">Capacity today</div>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;">{cap_buttons}</div>
                </div>
            </div>
            <!-- John status row -->
            <div style="margin-top:14px;padding-top:12px;border-top:1px solid #f5f0eb;">
                <div style="font-size:0.68em;font-weight:800;text-transform:uppercase;
                            letter-spacing:0.1em;color:var(--gold);margin-bottom:8px;">John today</div>
                <div style="display:flex;gap:6px;flex-wrap:wrap;">{john_buttons}</div>
            </div>
            <!-- James note row -->
            <div style="margin-top:14px;padding-top:12px;border-top:1px solid #f5f0eb;">
                <div style="font-size:0.68em;font-weight:800;text-transform:uppercase;
                            letter-spacing:0.1em;color:var(--gold);margin-bottom:8px;">James update</div>
                <textarea id="james-note-input"
                    placeholder="How was his night? Any feeding notes, fussiness, sleep stretch..."
                    onblur="anchorSaveJamesNote(this.value)"
                    style="width:100%;box-sizing:border-box;padding:8px 10px;font-size:0.85em;
                           font-family:inherit;border:1px solid #e8e0d8;border-radius:8px;
                           resize:none;height:56px;color:#333;background:#fdfaf7;
                           outline:none;line-height:1.4;">{james_note_esc}</textarea>
            </div>
        </div>

        <!-- Gospel reflection — dark card like mockup -->
        <div style="background:var(--ink);border-radius:14px;padding:16px 18px;margin-bottom:10px;">
            <div style="font-size:0.68em;font-weight:800;text-transform:uppercase;
                        letter-spacing:0.1em;color:rgba(245,234,216,0.45);margin-bottom:8px;">
                Gospel reflection · {escape(weekday)}
            </div>
            <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.1em;
                        font-style:italic;color:var(--gold-light);line-height:1.55;">
                {escape(reflection)}
            </div>
            {f'<div style="margin-top:10px;padding:10px 12px;background:rgba(245,234,216,0.07);border-radius:8px;font-size:0.85em;color:rgba(245,234,216,0.65);line-height:1.5;">{escape(SUNDAY_FAMILY_REFLECTION)}</div>' if is_sunday else ""}
        </div>

        <!-- Faith content row: Gospel + Saint + Quote stacked -->
        <div class="card card-tight" style="margin-bottom:10px;">
            <div style="padding:10px 0;border-bottom:1px solid #f5f0eb;">
                <div style="font-size:0.75em;font-weight:700;text-transform:uppercase;
                            letter-spacing:0.08em;color:#aaa;margin-bottom:4px;">Gospel of the day</div>
                <a href="{readings_url}" target="_blank"
                   style="font-size:0.92em;font-weight:600;color:#7c4a2d;">
                    Mass Readings for {_anchor_date_label} &#8599;
                </a>
                <div style="font-size:0.78em;color:#aaa;margin-top:2px;">
                    Full text at USCCB &middot; read aloud before school
                </div>
            </div>
            {saint_html}
            {quote_html}
        </div>

        <!-- This Day in History -->
        <div class="card card-tight" style="margin-bottom:10px;">
            <div style="font-size:0.68em;font-weight:800;text-transform:uppercase;
                        letter-spacing:0.1em;color:var(--gold);margin-bottom:10px;">
                This day in history &middot; {_anchor_date_label}
            </div>
            {history_html}
        </div>

        <!-- School launch ritual -->
        <div class="card card-tight">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                <div style="font-size:0.68em;font-weight:800;text-transform:uppercase;
                            letter-spacing:0.1em;color:var(--gold);">School launch ritual</div>
                {launch_badge}
            </div>
            {launch_rows}
        </div>
    </div>

    <script>
    var _anchorIso = '{escape(iso)}';

    function _anchorSave(data) {{
        fetch('/anchor-save', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
            body: 'iso=' + encodeURIComponent(_anchorIso) + '&data=' + encodeURIComponent(JSON.stringify(data))
        }});
    }}

    function anchorSetMode(mode) {{
        ['Home','Travel','Modified'].forEach(function(m) {{
            var btn = document.getElementById('mode-btn-' + m);
            if (btn) btn.style.background = (m === mode) ? '#8b5a3c' : '#f0ebe4';
            if (btn) btn.style.color      = (m === mode) ? 'white'   : '#555';
        }});
        _anchorSave({{mode: mode}});
    }}

    function anchorSetCap(cap) {{
        var colors = {{High:'#27ae60', Medium:'#e67e22', Low:'#e74c3c'}};
        ['High','Medium','Low'].forEach(function(c) {{
            var btn = document.getElementById('cap-btn-' + c);
            if (!btn) return;
            btn.style.background = (c === cap) ? colors[c] : '#f0ebe4';
            btn.style.color      = (c === cap) ? 'white'   : '#555';
        }});
        _anchorSave({{capacity: cap}});
    }}

    function anchorLaunch(key) {{
        var btn  = document.querySelector('#s-morning button[onclick="anchorLaunch(\\''+key+'\\')"]');
        var done = btn ? btn.textContent.trim() === '☑' : false;
        var newDone = !done;
        if (btn) {{
            btn.textContent  = newDone ? '☑' : '☐';
            btn.style.color  = newDone ? '#27ae60' : '#ccc';
            var span = btn.nextElementSibling;
            if (span) span.style.textDecoration = newDone ? 'line-through' : '';
            if (span) span.style.opacity = newDone ? '0.5' : '';
        }}
        var launchData = {{}};
        launchData['launch.' + key] = newDone;
        _anchorSave(launchData);
    }}

    function anchorSetJohn(val) {{
        var opts = ['At office','WFH','Traveling','Day off'];
        opts.forEach(function(o) {{
            var btn = document.getElementById('john-btn-' + o.replace(/ /g, '-'));
            if (!btn) return;
            btn.style.background = (o === val) ? '#2563eb' : '#f0ebe4';
            btn.style.color      = (o === val) ? 'white'   : '#555';
        }});
        _anchorSave({{john_status: val}});
    }}

    function anchorSaveJamesNote(val) {{
        _anchorSave({{james_note: val}});
    }}
    </script>"""


# ── Evening Anchor ────────────────────────────────────────────────────────────
def render_evening_anchor(iso: str) -> str:
    """
    Step 5 on Plan My Day: the Evening Anchor checklist.
    """
    anchor   = _get_anchor_state(iso)
    evening  = anchor.get("evening", {})
    done_count = sum(1 for key, _ in EVENING_CHECKLIST if evening.get(key, False))
    total      = len(EVENING_CHECKLIST)
    pct        = int(done_count / total * 100) if total else 0

    check_rows = ""
    for key, label in EVENING_CHECKLIST:
        checked    = evening.get(key, False)
        chk_color  = "#27ae60" if checked else "#ccc"
        done_style = "text-decoration:line-through;opacity:0.5;" if checked else ""
        icon       = "☑" if checked else "☐"
        check_rows += f"""
        <div style="display:flex;align-items:flex-start;gap:10px;padding:7px 0;
                    border-bottom:1px solid #f5f0eb;">
            <button onclick="eveningCheck('{key}')"
                    id="eve-{key}"
                    style="background:none;border:none;cursor:pointer;font-size:1.1em;
                           color:{chk_color};padding:0;flex-shrink:0;font-family:inherit;
                           line-height:1.4;">
                {icon}
            </button>
            <span style="font-size:0.9em;{done_style}">{escape(label)}</span>
        </div>"""

    # Brain dump
    brain_dump_val = escape(anchor.get("brain_dump", ""))

    return f"""
    <div id="s-evening" class="plan-section">
        <div class="plan-section-label">Step 5 — Evening anchor</div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">

            <!-- Checklist -->
            <div class="card card-tight">
                <div style="display:flex;align-items:center;justify-content:space-between;
                            margin-bottom:12px;flex-wrap:wrap;gap:8px;">
                    <h3 style="margin:0;">Evening checklist</h3>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="font-size:0.82em;color:#888;">{done_count}/{total}</span>
                        <div style="width:60px;height:6px;background:#f0ebe4;border-radius:3px;overflow:hidden;">
                            <div id="eve-progress-bar"
                                 style="width:{pct}%;height:100%;background:#27ae60;
                                        border-radius:3px;transition:width 0.3s;"></div>
                        </div>
                    </div>
                </div>
                <div id="eve-checklist">{check_rows}</div>
            </div>

            <!-- Brain dump + Marriage window -->
            <div style="display:flex;flex-direction:column;gap:12px;">
                <div class="card card-tight">
                    <h4 style="margin-bottom:8px;">🧠 Mom brain dump</h4>
                    <p class="small" style="margin-bottom:8px;">
                        What do you not want to hold in your head overnight?
                    </p>
                    <textarea id="eve-brain-dump" rows="4"
                              placeholder="Tasks, worries, to-remember, follow-ups…"
                              style="font-size:0.85em;resize:vertical;margin-bottom:8px;"
                              onblur="eveningSaveBrainDump()">{brain_dump_val}</textarea>
                    <button onclick="eveningSaveBrainDump(true)"
                            style="padding:5px 12px;font-size:0.82em;">
                        Save as note →
                    </button>
                </div>

                <div class="card card-tight"
                     style="background:#fef9f5;border-color:#f0ddd0;">
                    <h4 style="margin-bottom:6px;color:#8b5a3c;">💑 Marriage connection window</h4>
                    <p style="font-size:0.85em;color:#555;margin:0;line-height:1.6;">
                        <strong>10 minutes.</strong> Check in · share one appreciation ·
                        quick logistics · close with prayer or a moment of connection.
                    </p>
                    <div style="margin-top:8px;">
                        <button onclick="eveningCheck('marriage_done')"
                                id="eve-marriage_done"
                                style="padding:4px 12px;font-size:0.82em;
                                       background:{'#27ae60' if evening.get('marriage_done') else '#f0ebe4'};
                                       color:{'white' if evening.get('marriage_done') else '#555'};
                                       border:none;border-radius:6px;cursor:pointer;font-family:inherit;">
                            {'✓ Done' if evening.get('marriage_done') else 'Mark done'}
                        </button>
                    </div>
                </div>
            </div>

        </div>
    </div>

    <script>
    var _eveIso = '{escape(iso)}';

    function _eveSave(data) {{
        fetch('/anchor-save', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
            body: 'iso=' + encodeURIComponent(_eveIso) + '&data=' + encodeURIComponent(JSON.stringify(data))
        }});
    }}

    function eveningCheck(key) {{
        var btn     = document.getElementById('eve-' + key);
        if (!btn) return;
        var isDone  = btn.textContent.trim() === '☑';
        var newDone = !isDone;

        if (key === 'marriage_done') {{
            btn.textContent  = newDone ? '✓ Done' : 'Mark done';
            btn.style.background = newDone ? '#27ae60' : '#f0ebe4';
            btn.style.color      = newDone ? 'white'   : '#555';
        }} else {{
            btn.textContent = newDone ? '☑' : '☐';
            btn.style.color = newDone ? '#27ae60' : '#ccc';
            var span = btn.nextElementSibling;
            if (span) {{
                span.style.textDecoration = newDone ? 'line-through' : '';
                span.style.opacity        = newDone ? '0.5' : '';
            }}
        }}

        /* Update progress bar */
        var btns  = document.querySelectorAll('#eve-checklist button');
        var done  = 0;
        btns.forEach(function(b) {{ if (b.textContent.trim() === '☑') done++; }});
        var total = btns.length;
        var pct   = total ? Math.round(done / total * 100) : 0;
        var bar   = document.getElementById('eve-progress-bar');
        if (bar) bar.style.width = pct + '%';

        var saveKey = 'evening.' + key;
        var payload = {{}};
        payload[saveKey] = newDone;
        _eveSave(payload);
    }}

    function eveningSaveBrainDump(asNote) {{
        var text = document.getElementById('eve-brain-dump').value.trim();
        if (!text) return;
        _eveSave({{'evening.brain_dump': text}});
        if (asNote) {{
            fetch('/mom-add-note', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'text=' + encodeURIComponent('🌙 Brain dump: ' + text)
            }}).then(function() {{
                var ta = document.getElementById('eve-brain-dump');
                if (ta) {{ ta.value = ''; ta.placeholder = 'Saved to notes ✓'; }}
            }});
        }}
    }}
    </script>"""
