"""
render_chores.py — Chores page, laundry system, van rotation.
Imports from: config, data_helpers, ui_helpers
"""
from datetime import date, timedelta
from html import escape

from config import child_color, WEEKDAYS, VAN_ROLE_A, VAN_ROLE_B
from data_helpers import load_chores_data, save_chores_data
from ui_helpers import html_page, page_header, render_status_message

# ── Canonical chore defaults (from Family Operating System) ──────────────────
CANONICAL_CHORES = {
    "JP": {
        "daily": [
            "Check CAP email",
            "Check Sea Cadet email",
            "Daily Room Reset (after breakfast): make bed, pick up clothes, return items, trash",
            "Exercise (non-PE days)",
            "",
            "KITCHEN (Morning — Role A):",
            "  → Put food away",
            "  → Clear table + counters",
            "  → Spray + wipe table and counters",
            "  → Take out trash + recycling",
            "  → Sweep kitchen / dining room / foyer",
            "",
            "KITCHEN (Evening — Role A):",
            "  → Unload dishwasher",
            "  → Load dishwasher",
            "  → Clean sink",
        ],
        "weekly": {
            "Monday":    ["Trim nails", "Sweep indoor stairs"],
            "Tuesday":   ["Clean half bath", "Clean basement full bath"],
            "Wednesday": ["Switch basement zone (TV/Game + guest room)"],
            "Thursday":  ["Tidy garage (10 min)", "Collect trash"],
            "Friday":    ["Bring back trash can"],
            "Saturday":  ["Weekly room clean (~90 min): full clean, vacuum, laundry check",
                          "Prepare Mass clothes (with Mom approval)"],
        },
    },
    "Joseph": {
        "daily": [
            "Check Sea Cadet email",
            "Daily Room Reset (after breakfast): make bed, pick up clothes, return items, trash",
            "Exercise (non-PE days)",
            "Review irregular verbs",
            "",
            "KITCHEN (Morning — Role B):",
            "  → Unload dishwasher",
            "  → Load dishwasher",
            "  → Clean sink",
            "",
            "KITCHEN (Evening — Role B):",
            "  → Put food away",
            "  → Clear table + counters",
            "  → Spray + wipe table and counters",
            "  → Take out trash + recycling",
            "  → Sweep kitchen / dining room / foyer",
        ],
        "weekly": {
            "Monday":    ["Trim nails"],
            "Tuesday":   ["Clean kids bathroom"],
            "Wednesday": ["Switch basement zone (toy floor)"],
            "Thursday":  ["Tidy garage (10 min)", "Collect trash"],
            "Friday":    ["Bring back recycling"],
            "Saturday":  ["Weekly room clean (~90 min): full clean, vacuum, laundry check",
                          "Prepare Mass clothes (with Mom approval)"],
        },
    },
    "Michael": {
        "daily": [
            "Daily Room Reset (after breakfast): make bed, pick up clothes, return items, trash",
        ],
        "weekly": {
            "Wednesday": ["Basement: collect trash", "Assist toy floor zone"],
            "Saturday":  ["Weekly room clean", "Prepare Mass clothes"],
        },
    },
}

# Kitchen job rotation — JP and Joseph switch morning↔evening roles
# Both boys have kitchen jobs; they switch each week (same epoch as van rotation)
KITCHEN_ROLE_A_MORNING = [
    "KITCHEN (Morning — Role A):",
    "  → Put food away",
    "  → Clear table + counters",
    "  → Spray + wipe table and counters",
    "  → Take out trash + recycling",
    "  → Sweep kitchen / dining room / foyer",
]
KITCHEN_ROLE_A_EVENING = [
    "KITCHEN (Evening — Role A):",
    "  → Unload dishwasher",
    "  → Load dishwasher",
    "  → Clean sink",
]
KITCHEN_ROLE_B_MORNING = [
    "KITCHEN (Morning — Role B):",
    "  → Unload dishwasher",
    "  → Load dishwasher",
    "  → Clean sink",
]
KITCHEN_ROLE_B_EVENING = [
    "KITCHEN (Evening — Role B):",
    "  → Put food away",
    "  → Clear table + counters",
    "  → Spray + wipe table and counters",
    "  → Take out trash + recycling",
    "  → Sweep kitchen / dining room / foyer",
]


def get_kitchen_roles(for_date: date = None) -> dict:
    """Return fixed kitchen roles: JP is always Role A, Joseph is always Role B."""
    return {"JP": "A", "Joseph": "B"}


def apply_canonical_chores(chores: dict) -> dict:
    """
    Write the canonical chore defaults into the chores data.
    Preserves any existing LAUNDRY and VAN lines.
    Does NOT touch James (no chores assigned).
    """
    boys = chores.get("boys", {})
    for child, defaults in CANONICAL_CHORES.items():
        boys.setdefault(child, {"daily": [], "weekly": {}})
        # Daily — replace entirely (keep no stale defaults)
        boys[child]["daily"] = list(defaults.get("daily", []))
        # Weekly — merge in, preserving LAUNDRY and VAN lines
        for weekday, lines in defaults.get("weekly", {}).items():
            existing    = boys[child].setdefault("weekly", {}).get(weekday, [])
            laundry_van = [l for l in existing if l.startswith("LAUNDRY") or l.startswith("VAN") or l.startswith("  →")]
            boys[child]["weekly"][weekday] = lines + ([""] + laundry_van if laundry_van else [])
    chores["boys"] = boys
    return chores
LAUNDRY_WORKFLOW = [
    "Start load immediately after breakfast kitchen jobs",
    "Switch load before lunch",
    "Bring laundry upstairs after lunch — ready to fold",
    "Family fold block: fold together with audiobook/read-aloud",
    "Put away completely — no piles, no baskets, no 'later'",
]

LAUNDRY_DEFAULTS = {
    "JP": {
        "Monday":   ["LAUNDRY — Mom's laundry","  → Start load after breakfast kitchen jobs","  → Switch load before lunch","  → Bring upstairs after lunch","  → Family fold block (audiobook/read-aloud)","  → Put away completely before evening"],
        "Thursday": ["LAUNDRY — JP's own laundry","  → Start load after breakfast kitchen jobs","  → Switch load before lunch","  → Bring upstairs after lunch","  → Family fold block (audiobook/read-aloud)","  → Put away completely before evening"],
    },
    "Joseph": {
        "Wednesday": ["LAUNDRY — Joseph's own laundry (may be multiple loads)","  → Towels go to downstairs hamper first","  → Start load after breakfast kitchen jobs","  → Switch load before lunch","  → Bring upstairs after lunch","  → Family fold block (audiobook/read-aloud)","  → Put away completely before evening"],
        "Friday":    ["LAUNDRY — Assist Michael with his laundry","  → Start load after breakfast kitchen jobs","  → Switch load before lunch","  → Bring upstairs after lunch","  → Family fold block (audiobook/read-aloud)","  → Put away completely before evening"],
    },
    "Michael": {
        "Friday": ["LAUNDRY — Michael's laundry (Joseph assists)","  → Start load after breakfast kitchen jobs","  → Switch load before lunch","  → Bring upstairs after lunch","  → Family fold block (audiobook/read-aloud)","  → Put away completely before evening"],
    },
    "James": {},
}

def apply_laundry_defaults(chores: dict) -> dict:
    boys = chores.get("boys", {})
    for child, day_map in LAUNDRY_DEFAULTS.items():
        boys.setdefault(child, {"daily": [], "weekly": {}})
        for weekday, laundry_lines in day_map.items():
            existing    = boys[child].setdefault("weekly", {}).get(weekday, [])
            non_laundry = [l for l in existing if not l.startswith("LAUNDRY") and not l.startswith("  →")]
            boys[child]["weekly"][weekday] = laundry_lines + ([""] + non_laundry if non_laundry else [])
    chores["boys"] = boys
    return chores

# ── Van rotation ──────────────────────────────────────────────────────────────

VAN_ROLE_A_TASKS = [
    "VAN — Role A: Interior Reset Lead",
    "  → Clear all trash from van",
    "  → Remove all loose items",
    "  → Check under all seats",
    "  → Gather everything into a sorting pile",
    "  → Sort items: trash / return to house / keep in bin",
]

# Role B vacuum sub-tasks — 2-week cycle tracked from van epoch
VAN_ROLE_B_VACUUM_WK1 = [
    "  → VACUUM — front seats (driver + passenger) and trunk/cargo area",
]
VAN_ROLE_B_VACUUM_WK2 = [
    "  → VACUUM — floor around all kids seats: 2nd row floor + floor under 3rd row bench",
    "  → VACUUM — 3rd row bench and around car seats",
]

# Role B wipe-down sub-tasks — 4-week cycle tracked from van epoch
VAN_ROLE_B_WIPE_WK1 = ["  → WIPE-DOWN — dashboard, steering wheel, all seats, center console, door panels"]
VAN_ROLE_B_WIPE_WK2 = ["  → WIPE-DOWN — vacuum and wipe down all car seats (remove and reset)"]
VAN_ROLE_B_WIPE_WK3 = ["  → WIPE-DOWN — seats and walls in back section, center console between middle seats"]
VAN_ROLE_B_WIPE_WK4 = ["  → WIPE-DOWN — spray and wipe all windows inside and outside"]

# Static description for reference (used in settings/van-roles page)
VAN_ROLE_B_DESCRIPTION = [
    "VAN — Role B: Vacuum & Wipe-down Lead",
    "  → Sort items: trash / return to house / keep in bin",
    "  → Complete this week's vacuum task (alternates every 2 weeks)",
    "  → Complete this week's wipe-down task (rotates every 4 weeks)",
]

VAN_CYCLE = [
    (VAN_ROLE_A, VAN_ROLE_B),   # Cycle week 1: JP=A, Joseph=B
    (VAN_ROLE_B, VAN_ROLE_A),   # Cycle week 2: JP=B, Joseph=A
    (VAN_ROLE_A, VAN_ROLE_B),   # Cycle week 3: JP=A, Joseph=B
]

VACUUM_LABELS = {
    1: "Vacuum wk 1 of 2 — front seats + trunk",
    2: "Vacuum wk 2 of 2 — middle section (kids seats & floor)",
}
WIPE_LABELS = {
    1: "Wipe-down wk 1 of 4 — dashboard, wheel, seats, console, doors",
    2: "Wipe-down wk 2 of 4 — car seats (vacuum & wipe, remove & reset)",
    3: "Wipe-down wk 3 of 4 — back walls, rear seats, middle console",
    4: "Wipe-down wk 4 of 4 — all windows inside and outside",
}


def get_vacuum_week(for_date: date = None) -> int:
    """Return 1 or 2 — which vacuum sub-task is due this week."""
    from config import get_van_epoch
    if for_date is None:
        for_date = date.today()
    epoch = get_van_epoch()
    this_monday   = for_date - timedelta(days=for_date.weekday())
    weeks_elapsed = (this_monday - epoch).days // 7
    return (weeks_elapsed % 2) + 1


def get_wipe_week(for_date: date = None) -> int:
    """Return 1-4 — which wipe-down sub-task is due this week."""
    from config import get_van_epoch
    if for_date is None:
        for_date = date.today()
    epoch = get_van_epoch()
    this_monday   = for_date - timedelta(days=for_date.weekday())
    weeks_elapsed = (this_monday - epoch).days // 7
    return (weeks_elapsed % 4) + 1


def get_van_week_number(for_date: date = None) -> int:
    from config import get_van_epoch
    if for_date is None:
        for_date = date.today()
    epoch         = get_van_epoch()
    this_monday   = for_date - timedelta(days=for_date.weekday())
    weeks_elapsed = (this_monday - epoch).days // 7
    return (weeks_elapsed % 3) + 1


def get_van_roles(for_date: date = None) -> dict:
    week    = get_van_week_number(for_date)
    jp_role, joseph_role = VAN_CYCLE[week - 1]
    return {
        "JP":      jp_role,
        "Joseph":  joseph_role,
        "week":    week,
        "vac_wk":  get_vacuum_week(for_date),
        "wipe_wk": get_wipe_week(for_date),
    }


def _role_b_tasks_this_week(for_date: date = None) -> list:
    """Build Role B task list with the correct vacuum + wipe-down steps for this week."""
    vac_wk  = get_vacuum_week(for_date)
    wipe_wk = get_wipe_week(for_date)
    vacuum_steps = VAN_ROLE_B_VACUUM_WK1 if vac_wk == 1 else VAN_ROLE_B_VACUUM_WK2
    wipe_steps   = {1: VAN_ROLE_B_WIPE_WK1, 2: VAN_ROLE_B_WIPE_WK2,
                    3: VAN_ROLE_B_WIPE_WK3, 4: VAN_ROLE_B_WIPE_WK4}[wipe_wk]
    return (
        ["VAN — Role B: Vacuum & Wipe-down Lead",
         "  → Sort items: trash / return to house / keep in bin",
         "  → " + VACUUM_LABELS[vac_wk]]
        + vacuum_steps
        + ["  → " + WIPE_LABELS[wipe_wk]]
        + wipe_steps
    )


def get_van_chore_lines(child: str, for_date: date = None) -> list:
    role = get_van_roles(for_date).get(child, "")
    if not role:
        return []
    return VAN_ROLE_A_TASKS if role == VAN_ROLE_A else _role_b_tasks_this_week(for_date)


def apply_van_rotation(chores: dict, for_date: date = None) -> dict:
    boys = chores.get("boys", {})
    for child in ("JP", "Joseph"):
        boys.setdefault(child, {"daily": [], "weekly": {}})
        existing  = boys[child].setdefault("weekly", {}).get("Monday", [])
        non_van   = [l for l in existing if not l.startswith("VAN") and not l.startswith("  →")]
        van_lines = get_van_chore_lines(child, for_date)
        boys[child]["weekly"]["Monday"] = van_lines + ([""] + non_van if non_van else [])
    chores["boys"] = boys
    return chores

def render_van_roles_card(for_date: date = None) -> str:
    roles      = get_van_roles(for_date)
    week       = roles["week"]
    jp_role    = roles["JP"]
    joe_role   = roles["Joseph"]
    vac_wk     = roles["vac_wk"]
    wipe_wk    = roles["wipe_wk"]
    jp_color   = child_color("JP",     "bg")
    joe_color  = child_color("Joseph", "bg")

    def role_badge(role):
        if role == VAN_ROLE_A:
            return "<span style='background:#fef9c3;border:1px solid #fde047;color:#713f12;padding:2px 9px;border-radius:999px;font-size:0.82em;font-weight:700;'>Role A — Interior Reset</span>"
        return "<span style='background:#dbeafe;border:1px solid #93c5fd;color:#1e3a8a;padding:2px 9px;border-radius:999px;font-size:0.82em;font-weight:700;'>Role B — Vacuum &amp; Wipe-down</span>"

    vac_note  = escape(VACUUM_LABELS[vac_wk])
    wipe_note = escape(WIPE_LABELS[wipe_wk])

    return f"""
    <div class="card" style="border-left:5px solid #6b7280;background:#f9fafb;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <h3 style="margin:0;">🚐 Van Cleaning — Cycle week {week} of 3</h3>
            <a class="link-button" href="/van-roles">Full schedule</a>
        </div>
        <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px;">
            <div style="flex:1;min-width:140px;padding:10px 14px;background:white;border-radius:10px;border:1px solid #e5e7eb;">
                <div style="font-size:0.78em;font-weight:700;color:{jp_color};text-transform:uppercase;margin-bottom:4px;">JP</div>
                {role_badge(jp_role)}
            </div>
            <div style="flex:1;min-width:140px;padding:10px 14px;background:white;border-radius:10px;border:1px solid #e5e7eb;">
                <div style="font-size:0.78em;font-weight:700;color:{joe_color};text-transform:uppercase;margin-bottom:4px;">Joseph</div>
                {role_badge(joe_role)}
            </div>
        </div>
        <div style="font-size:0.85em;color:#555;border-top:1px solid #e5e7eb;padding-top:10px;">
            <div style="margin-bottom:3px;">🧹 {vac_note}</div>
            <div>🧽 {wipe_note}</div>
        </div>
    </div>"""

def render_van_roles_page() -> str:
    today = date.today()
    check_dates = [today - timedelta(days=today.weekday())]
    for i in range(1, 9):
        check_dates.append(check_dates[0] + timedelta(weeks=i))

    rows = ""
    for d in check_dates:
        roles    = get_van_roles(d)
        w        = roles["week"]
        vac_wk   = roles["vac_wk"]
        wipe_wk  = roles["wipe_wk"]
        is_current = (d <= today < d + timedelta(days=7))
        bg    = "background:#f0fdf4;" if is_current else ""
        badge = " <span style='background:#16a34a;color:white;font-size:0.72em;padding:1px 6px;border-radius:999px;'>Now</span>" if is_current else ""
        jp_c  = child_color("JP",     "bg")
        joe_c = child_color("Joseph", "bg")
        vac_short  = {1:"Front + trunk", 2:"Middle section"}[vac_wk]
        wipe_short = {1:"Dash/seats/doors", 2:"Car seats", 3:"Back walls/console", 4:"Windows"}[wipe_wk]
        _d_label = d.strftime("%b %d")
        rows += f"""
        <tr style="{bg}">
            <td style='padding:6px 10px;font-weight:600;white-space:nowrap;'>{_d_label}{badge}</td>
            <td style='padding:6px 10px;color:#666;font-size:0.88em;'>Cycle {w}</td>
            <td style='padding:6px 10px;'><span style='color:{jp_c};font-weight:700;'>JP</span> — {escape(roles["JP"].split(":")[0].replace("Role ","R"))}</td>
            <td style='padding:6px 10px;'><span style='color:{joe_c};font-weight:700;'>Joseph</span> — {escape(roles["Joseph"].split(":")[0].replace("Role ","R"))}</td>
            <td style='padding:6px 10px;font-size:0.85em;color:#555;'>🧹 {escape(vac_short)}</td>
            <td style='padding:6px 10px;font-size:0.85em;color:#555;'>🧽 {escape(wipe_short)}</td>
        </tr>"""

    role_a_items = "".join(f"<li style='margin-bottom:3px;'>{escape(t.lstrip('  →').strip())}</li>" for t in VAN_ROLE_A_TASKS[1:])
    role_b_items = "".join(f"<li style='margin-bottom:3px;'>{escape(t.lstrip('  →').strip())}</li>" for t in VAN_ROLE_B_DESCRIPTION[1:])

    # Full vacuum + wipe-down reference tables
    vac_rows = ""
    for wk, label in VACUUM_LABELS.items():
        steps = VAN_ROLE_B_VACUUM_WK1 if wk == 1 else VAN_ROLE_B_VACUUM_WK2
        step_html = "".join(f"<div style='font-size:0.82em;color:#555;margin-top:2px;'>{escape(s.lstrip('  →').strip())}</div>" for s in steps)
        vac_rows += f"<div style='padding:8px 0;border-bottom:1px solid #f0ebe4;'><strong style='font-size:0.88em;'>Week {wk}:</strong> {escape(label.split('—')[1].strip())}{step_html}</div>"

    wipe_rows = ""
    for wk, label in WIPE_LABELS.items():
        steps = {1: VAN_ROLE_B_WIPE_WK1, 2: VAN_ROLE_B_WIPE_WK2, 3: VAN_ROLE_B_WIPE_WK3, 4: VAN_ROLE_B_WIPE_WK4}[wk]
        step_html = "".join(f"<div style='font-size:0.82em;color:#555;margin-top:2px;'>{escape(s.lstrip('  →').strip())}</div>" for s in steps)
        wipe_rows += f"<div style='padding:8px 0;border-bottom:1px solid #f0ebe4;'><strong style='font-size:0.88em;'>Week {wk}:</strong> {escape(label.split('—')[1].strip())}{step_html}</div>"

    body = f"""
    {page_header("Van Cleaning Rotation")}
    {render_van_roles_card(today)}

    <h2 style="margin-top:20px;">Upcoming 8 Mondays</h2>
    <div class="card" style="padding:0;overflow:hidden;overflow-x:auto;">
        <table style='border-collapse:collapse;width:100%;font-size:0.9em;min-width:600px;'>
            <thead><tr style='background:#f3f4f6;'>
                <th style='padding:7px 10px;text-align:left;'>Monday</th>
                <th style='padding:7px 10px;text-align:left;'>Cycle</th>
                <th style='padding:7px 10px;text-align:left;'>JP</th>
                <th style='padding:7px 10px;text-align:left;'>Joseph</th>
                <th style='padding:7px 10px;text-align:left;'>🧹 Vacuum</th>
                <th style='padding:7px 10px;text-align:left;'>🧽 Wipe-down</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>

    <div class="two-col" style="margin-top:16px;">
        <div>
            <h2>Role A — Interior Reset Lead</h2>
            <div class="card" style="background:#fef9c3;border-color:#fde047;">
                <ul style='font-size:0.9em;padding-left:18px;margin:0;'>{role_a_items}</ul>
            </div>

            <h2>Role B — Vacuum &amp; Wipe-down Lead</h2>
            <div class="card" style="background:#dbeafe;border-color:#93c5fd;">
                <ul style='font-size:0.9em;padding-left:18px;margin:0;'>{role_b_items}</ul>
            </div>
        </div>
        <div>
            <h2>Vacuum rotation (2-week cycle)</h2>
            <div class="card" style="padding:0 18px;">{vac_rows}</div>

            <h2 style="margin-top:16px;">Wipe-down rotation (4-week cycle)</h2>
            <div class="card" style="padding:0 18px;">{wipe_rows}</div>
        </div>
    </div>

    <div class="card" style="margin-top:4px;">
        <h3>Apply This Week's Rotation to Monday Chores</h3>
        <p class="small" style="margin-bottom:10px;">
            Writes each boy's exact tasks — including this week's vacuum and wipe-down steps — into their Monday chore list.
        </p>
        <form method="POST" action="/apply-van-rotation" style="display:inline;">
            <button type="submit">Apply Van Rotation to Monday Chores</button>
        </form>
    </div>"""
    return html_page("Van Cleaning Rotation", body)

# ── Today's chore completion status ──────────────────────────────────────────
def _render_chore_status_today() -> str:
    """Compact overview of each boy's daily chore completion today."""
    from data_helpers import load_progress
    today   = date.today()
    iso     = today.isoformat()
    weekday = today.strftime("%A")
    chores  = load_chores_data()
    boys    = chores.get("boys", {})
    progress = load_progress()

    def _done(child, text):
        val = progress.get(f"{iso}::{child}::CHORE::{text}", False)
        if isinstance(val, bool):   return val
        if isinstance(val, dict):   return bool(val.get("done", False))
        return bool(val)

    cards_html = ""
    for child in ("JP", "Joseph", "Michael"):
        data    = boys.get(child, {})
        # Fall back to canonical defaults if stored data is empty
        canon   = CANONICAL_CHORES.get(child, {})
        stored_daily  = data.get("daily", [])
        stored_weekly = data.get("weekly", {}).get(weekday, [])
        daily  = [t for t in (stored_daily  or canon.get("daily",  [])) if t.strip() and not t.startswith("\u2192")]
        weekly = [t for t in (stored_weekly or canon.get("weekly", {}).get(weekday, [])) if t.strip() and not t.startswith("\u2192")]
        all_t   = daily + weekly
        if not all_t:
            continue
        done_n  = sum(1 for t in all_t if _done(child, t))
        total   = len(all_t)
        pct     = int(done_n / total * 100) if total else 0
        c_bg    = child_color(child, "bg")
        c_light = child_color(child, "light")
        bar_col = "#16a34a" if pct == 100 else c_bg
        rows    = ""
        for t in all_t:
            ok = _done(child, t)
            icon_s = "color:#16a34a;font-weight:700;" if ok else "color:#d1d5db;"
            text_s = "text-decoration:line-through;color:#9ca3af;" if ok else ""
            rows += (
                f"<div style='display:flex;align-items:center;gap:7px;padding:3px 0;"
                f"border-bottom:1px solid {c_light};'>"
                f"<span style='font-size:0.85em;{icon_s}'>{'✓' if ok else '○'}</span>"
                f"<span style='font-size:0.81em;{text_s}'>{escape(t)}</span></div>"
            )
        cards_html += (
            f"<div style='flex:1;min-width:190px;background:white;border-radius:12px;"
            f"border:2px solid {c_light};overflow:hidden;'>"
            f"<div style='background:{c_bg};padding:7px 12px;display:flex;align-items:center;"
            f"justify-content:space-between;'>"
            f"<span style='font-size:0.88em;font-weight:800;color:white;'>{escape(child)}</span>"
            f"<span style='font-size:0.75em;color:rgba(255,255,255,.8);'>{done_n}/{total}</span></div>"
            f"<div style='height:4px;background:#f3f4f6;'>"
            f"<div style='height:100%;width:{pct}%;background:{bar_col};'></div></div>"
            f"<div style='padding:8px 12px;'>{rows}</div></div>"
        )

    return (
        f"<div class='card' style='margin-bottom:16px;'>"
        f"<div style='display:flex;align-items:center;justify-content:space-between;"
        f"margin-bottom:12px;flex-wrap:wrap;gap:8px;'>"
        f"<h3 style='margin:0;'>Today\u2019s Chores \u2014 {escape(weekday)}, {today.strftime('%B %-d')}</h3>"
        f"<a href='/chores' style='font-size:0.78em;color:#9ca3af;text-decoration:none;'>\u21bb refresh</a>"
        f"</div>"
        f"<div style='display:flex;gap:12px;flex-wrap:wrap;'>{cards_html}</div>"
        f"<div style='font-size:0.73em;color:#9ca3af;margin-top:10px;font-style:italic;'>"
        f"Boys mark tasks done on their own schedule page.</div></div>"
    )


# ── Chores page ───────────────────────────────────────────────────────────────
def render_chores_page(status_message: str = "") -> str:
    from daily_schedule_engine import CHILDREN
    from config import parent_color
    chores = load_chores_data()
    boys   = chores.get("boys", {})

    # ── Lauren's chores section ───────────────────────────────────────────────
    lauren_data    = chores.get("lauren", {})
    lauren_daily   = "\n".join(lauren_data.get("daily", []))
    lauren_weekly  = lauren_data.get("weekly", {})
    l_bg    = parent_color("Lauren", "bg")
    l_light = parent_color("Lauren", "light")
    lauren_weekday_fields = ""
    for weekday in WEEKDAYS:
        existing_lines = lauren_weekly.get(weekday, [])
        value = "\n".join(existing_lines)
        lauren_weekday_fields += f"""
            <label>{escape(weekday)}</label>
            <textarea name="weekly__Lauren__{escape(weekday)}" rows="3">{escape(value)}</textarea>"""
    lauren_section = f"""
        <div class="card" style="border-left:5px solid {l_bg};background:{l_light};margin-bottom:16px;">
            <h2 style="color:{l_bg};">Lauren</h2>
            <div style="font-size:0.8em;color:#9ca3af;margin-bottom:8px;font-style:italic;">
                Tasks here appear on your profile page with checkboxes — just like the boys.
            </div>
            <label>Daily chores / tasks</label>
            <textarea name="daily__Lauren" rows="4">{escape(lauren_daily)}</textarea>
            <h3>Weekly chores / tasks</h3>
            {lauren_weekday_fields}
        </div>"""

    sections = ""
    for child in CHILDREN:
        child_data = boys.get(child, {})
        daily_text = "\n".join(child_data.get("daily", []))
        weekly     = child_data.get("weekly", {})
        weekday_fields = ""
        for weekday in WEEKDAYS:
            existing_lines = weekly.get(weekday, [])
            value = "\n".join(existing_lines)
            badges = ""
            if any(l.startswith("LAUNDRY") for l in existing_lines):
                badges += " <span style='background:#e8f4fd;border:1px solid #b8d9f0;color:#2471a3;font-size:0.72em;padding:1px 6px;border-radius:999px;font-weight:600;margin-left:5px;'>🧺</span>"
            if any(l.startswith("VAN") for l in existing_lines):
                badges += " <span style='background:#f3f4f6;border:1px solid #d1d5db;color:#374151;font-size:0.72em;padding:1px 6px;border-radius:999px;font-weight:600;margin-left:3px;'>🚐</span>"
            weekday_fields += f"""
            <label>{escape(weekday)}{badges}</label>
            <textarea name="weekly__{escape(child)}__{escape(weekday)}" rows="3">{escape(value)}</textarea>"""
        c_bg    = child_color(child, "bg")
        c_light = child_color(child, "light")
        sections += f"""
        <div class="card" style="border-left:5px solid {c_bg};background:{c_light};">
            <h2 style="color:{c_bg};">{escape(child)}</h2>
            <label>Daily chores/jobs</label>
            <textarea name="daily__{escape(child)}" rows="4">{escape(daily_text)}</textarea>
            <h3>Weekly chores/jobs</h3>
            {weekday_fields}
        </div>"""

    roles     = get_van_roles()
    week      = roles["week"]
    jp_r      = roles["JP"]
    joe_r     = roles["Joseph"]
    vac_wk    = roles["vac_wk"]
    wipe_wk   = roles["wipe_wk"]
    van_badge = f"""
    <div class="card" style="border-left:4px solid #6b7280;background:#f9fafb;padding:12px 16px;margin-bottom:16px;">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
            <div>
                <span style="font-weight:600;">🚐 Van — Cycle week {week} of 3</span>
                <span style="margin:0 8px;color:#ccc;">|</span>
                <span style="font-size:0.88em;color:#555;">JP: <strong>{escape(jp_r.split(":")[0])}</strong></span>
                <span style="margin:0 6px;color:#ccc;">·</span>
                <span style="font-size:0.88em;color:#555;">Joseph: <strong>{escape(joe_r.split(":")[0])}</strong></span>
                <div style="font-size:0.82em;color:#777;margin-top:3px;">
                    🧹 {escape(VACUUM_LABELS[vac_wk])} &nbsp;·&nbsp; 🧽 {escape(WIPE_LABELS[wipe_wk])}
                </div>
            </div>
            <div class="link-row" style="margin:0;">
                <a class="link-button" href="/van-roles">Rotation schedule</a>
                <a class="link-button" href="/settings#s-systems">Configure in Settings</a>
            </div>
        </div>
    </div>"""

    # Kitchen job rotation card
    kitchen_roles = get_kitchen_roles()
    jp_k  = kitchen_roles["JP"]
    joe_k = kitchen_roles["Joseph"]
    jp_morning  = KITCHEN_ROLE_A_MORNING  if jp_k == "A" else KITCHEN_ROLE_B_MORNING
    jp_evening  = KITCHEN_ROLE_A_EVENING  if jp_k == "A" else KITCHEN_ROLE_B_EVENING
    joe_morning = KITCHEN_ROLE_A_MORNING  if joe_k == "A" else KITCHEN_ROLE_B_MORNING
    joe_evening = KITCHEN_ROLE_A_EVENING  if joe_k == "A" else KITCHEN_ROLE_B_EVENING
    def _fmt(lines): return "".join(f"<div style='font-size:0.85em;padding:1px 0;'>{escape(l)}</div>" for l in lines)
    jp_color  = child_color("JP",     "bg")
    joe_color = child_color("Joseph", "bg")
    kitchen_card = f"""
    <div class="card" style="border-left:4px solid #e67e22;background:#fef6ed;margin-bottom:16px;">
        <h3 style="margin:0 0 10px;">🍽 Kitchen Jobs — This week</h3>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
            <div>
                <div style="font-weight:700;color:{jp_color};margin-bottom:6px;">JP</div>
                {_fmt(jp_morning)}
                <div style="margin-top:6px;">{_fmt(jp_evening)}</div>
            </div>
            <div>
                <div style="font-weight:700;color:{joe_color};margin-bottom:6px;">Joseph</div>
                {_fmt(joe_morning)}
                <div style="margin-top:6px;">{_fmt(joe_evening)}</div>
            </div>
        </div>
    </div>"""

    # AI chore adjuster
    from render_settings import load_app_settings as _las
    _api_key = (_las().get("anthropic_api_key","") or _las().get("family_constraints",{}).get("anthropic_api_key",""))
    today_iso = date.today().isoformat()
    ai_chore_btn = f"""
<div style="margin-bottom:16px;">
  <button onclick="aiChoreAdjust(this)"
    style="padding:7px 16px;background:#7c3aed;color:#fff;border:none;
           border-radius:10px;font-size:0.85em;font-weight:600;font-family:inherit;cursor:pointer;">
    ✨ AI — Adjust chores for today's capacity
  </button>
  <div id="ai-chore-result" style="display:none;margin-top:10px;padding:12px;
       background:white;border-radius:10px;border:1px solid var(--border-light);"></div>
  <script>
  function aiChoreAdjust(btn) {{
    btn.disabled = true; btn.textContent = '✨ Thinking…';
    var result = document.getElementById('ai-chore-result');
    result.style.display = 'block';
    result.innerHTML = '<span style="color:var(--ink-faint);font-size:0.85em;">Asking Claude about today\u2019s chores\u2026</span>';
    fetch('/ai-chore-adjust', {{
      method:'POST', headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
      body:'iso={today_iso}&capacity='
    }}).then(function(r){{return r.json();}}).then(function(d){{
      result.innerHTML = d.html || '<p>No response.</p>';
      btn.disabled=false; btn.textContent='\u2728 AI \u2014 Adjust chores for today\u2019s capacity';
    }}).catch(function(){{
      result.innerHTML='<p style="color:#ef4444;">Error \u2014 check connection.</p>';
      btn.disabled=false;
    }});
  }}
  </script>
</div>""" if _api_key else ""

    status_today = _render_chore_status_today()

    body = f"""
    {page_header("Chores")}
    {render_status_message(status_message)}
    {status_today}
    {ai_chore_btn}
    {van_badge}
    {kitchen_card}
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:12px;">
        <h2 style="margin:0;">Weekly chore lists</h2>
        <form method="POST" action="/apply-canonical-chores" style="display:inline;">
            <button type="submit" class="ghost" style="font-size:0.82em;padding:5px 12px;">
                ↺ Reset to Family OS defaults
            </button>
        </form>
    </div>
    <form method="POST" action="/save-chores">
        {lauren_section}
        {sections}
        <button type="submit">Save Chores</button>
    </form>"""
    return html_page("Chores", body)