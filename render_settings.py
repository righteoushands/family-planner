"""
render_settings.py — Single source of truth for all configuration.
Sections: General · Children · Systems · Integrations
"""
import os
from datetime import date, timedelta
from html import escape

from safe_utils import ensure_file, safe_save_json
from ui_helpers import html_page, page_header, render_status_message
from data_helpers import (
    load_calendar_config, save_calendar_config,
    load_subscribed_calendars, save_subscribed_calendars,
    get_frol_day_slots,
)

APP_SETTINGS_FILE = "data/app_settings.json"

DAILY_MASS_SOURCES = [
    ("ascension_press",  "Ascension Press",   "https://ascensionpress.com/pages/daily-mass"),
    ("little_rose_shop", "Little Rose Shop",  "https://thelittleroseshop.com/blogs/daily-readings"),
    ("word_on_fire",     "Word on Fire",      "https://www.wordonfire.org/daily-mass/"),
    ("ewtn",             "EWTN",              "https://www.ewtn.com/catholicism/daily-readings"),
    ("custom",           "Custom URL",        ""),
]

DAILY_MASS_URL_MAP = {k: u for (k, _, u) in DAILY_MASS_SOURCES}


def resolve_daily_mass_url(settings: dict) -> str:
    src = (settings or {}).get("daily_mass_source", "ascension_press")
    if src == "custom":
        return ((settings or {}).get("daily_mass_custom_url") or "").strip()
    return DAILY_MASS_URL_MAP.get(src, DAILY_MASS_URL_MAP["ascension_press"])


SETTINGS_DEFAULTS = {
    "family_name":              "Our Family",
    "timezone":                 "America/New_York",
    "van_epoch":                "2025-01-06",
    "schedule_start_hour":      6,
    "schedule_end_hour":        22,
    "cycle_show_detail_fields": True,
    "color_theme":              "ivory",
    "daily_mass_source":        "ascension_press",
    "daily_mass_custom_url":    "",
    "sister_mary_family_context": False,
    "child_colors": {
        "JP":      {"bg": "#c0392b", "text": "#fff", "light": "#fdf0ef"},
        "Joseph":  {"bg": "#27ae60", "text": "#fff", "light": "#edfaf3"},
        "Michael": {"bg": "#e67e22", "text": "#fff", "light": "#fef6ed"},
        "James":   {"bg": "#2980b9", "text": "#fff", "light": "#eaf4fb"},
    },
}

COMMON_TIMEZONES = [
    ("America/New_York",    "Eastern Time (ET)"),
    ("America/Chicago",     "Central Time (CT)"),
    ("America/Denver",      "Mountain Time (MT)"),
    ("America/Phoenix",     "Mountain Time – Arizona (no DST)"),
    ("America/Los_Angeles", "Pacific Time (PT)"),
    ("America/Anchorage",   "Alaska Time"),
    ("Pacific/Honolulu",    "Hawaii Time"),
]

COLOR_PRESETS = [
    ("#c0392b", "#fdf0ef", "Red"),
    ("#27ae60", "#edfaf3", "Green"),
    ("#2980b9", "#eaf4fb", "Blue"),
    ("#e67e22", "#fef6ed", "Orange"),
    ("#8e44ad", "#f5eefa", "Purple"),
    ("#16a085", "#eafaf7", "Teal"),
    ("#d35400", "#fef3ea", "Burnt Orange"),
    ("#2c3e50", "#eaecee", "Navy"),
    ("#1abc9c", "#eafaf6", "Mint"),
    ("#c0392b", "#fdf0ef", "Crimson"),
]

SCHEDULE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

CAL_COLOR_OPTIONS = [
    ("#9b59b6","Purple"),("#e74c3c","Red"),("#3498db","Blue"),("#27ae60","Green"),
    ("#e67e22","Orange"),("#1abc9c","Teal"),("#e91e8c","Pink"),("#34495e","Dark"),
]


def load_app_settings() -> dict:
    import os as _os
    stored = ensure_file(APP_SETTINGS_FILE, {})
    settings = dict(SETTINGS_DEFAULTS)
    settings.update({k: v for k, v in stored.items() if k != "child_colors"})
    if "child_colors" in stored:
        merged = dict(SETTINGS_DEFAULTS["child_colors"])
        merged.update(stored["child_colors"])
        settings["child_colors"] = merged
    # Anthropic API key MUST come from the ANTHROPIC_API_KEY environment
    # variable (Replit Secrets). Env always wins; we never fall back to a
    # JSON-stored value. If the env var is unset, the in-memory key is empty
    # and the Settings UI displays a warning banner directing the user to
    # add ANTHROPIC_API_KEY to Replit Secrets.
    _env_key = _os.environ.get("ANTHROPIC_API_KEY", "").strip()
    fc = settings.setdefault("family_constraints", {})
    fc["anthropic_api_key"] = _env_key
    settings["anthropic_api_key"] = _env_key
    return settings


def save_app_settings(settings: dict):
    # Defense in depth: the Anthropic API key is sourced exclusively from the
    # ANTHROPIC_API_KEY Replit secret (see load_app_settings). Strip both the
    # top-level field and the nested family_constraints field before writing
    # so the secret can never be persisted to disk regardless of how this
    # function is called. Operates on a shallow copy so we do not mutate the
    # caller's dict (it may still be used after save).
    settings = dict(settings)
    settings["anthropic_api_key"] = ""
    fc = settings.get("family_constraints")
    if isinstance(fc, dict):
        fc = dict(fc)
        fc["anthropic_api_key"] = ""
        settings["family_constraints"] = fc
    safe_save_json(APP_SETTINGS_FILE, settings)


def _section_general(settings: dict) -> str:
    family_name  = settings.get("family_name", "Our Family")
    timezone     = settings.get("timezone",    "America/New_York")
    location     = settings.get("location",    "")
    current_theme = settings.get("color_theme", "ivory")

    tz_opts = "".join(
        f'<option value="{tz}" {"selected" if tz == timezone else ""}>{escape(label)}</option>'
        for tz, label in COMMON_TIMEZONES
    )

    # Build theme swatches
    from ui_helpers import THEMES, LITURGICAL_PALETTES
    try:
        from datetime import date as _date, timedelta as _tds
        def _easter_s(year):
            a=year%19; b,c=divmod(year,100); d,e=divmod(b,4)
            f=(b+8)//25; g=(b-f+1)//3; h=(19*a+b-d-g+15)%30
            i,k=divmod(c,4); l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
            month,day=divmod(h+l-7*m+114,31)
            return _date(year, month, day+1)
        _td = _date.today(); _y = _td.year
        _ea = _easter_s(_y); _aw = _ea-_tds(days=46); _ps = _ea-_tds(days=7)
        _ad1_base = _date(_y,11,30)
        _ad1 = _ad1_base - _tds(days=_ad1_base.weekday()+1) if _ad1_base.weekday()!=6 else _ad1_base
        if _aw <= _td < _ps: current_season = "Lent"
        elif _ps <= _td <= _ea-_tds(days=1): current_season = "Holy Week"
        elif _ea <= _td < _ea+_tds(days=49): current_season = "Easter"
        elif _ad1 <= _td < _date(_y,12,25): current_season = "Advent"
        elif _td >= _date(_y,12,25) or _td < _date(_y,1,6): current_season = "Christmas"
        else: current_season = "Ordinary Time"
    except Exception:
        current_season = "Ordinary Time"

    # Preview colors for each theme swatch
    SWATCH_COLORS = {
        "ivory":      ("#f7f3ee", "#8b6914", "#8b5a3c"),
        "parchment":  ("#f0e8d8", "#7a5a10", "#7a4a2c"),
        "night":      ("#1e1a14", "#c9a44a", "#c9906a"),
        "minimal":    ("#ffffff", "#2563eb", "#2563eb"),
        "liturgical": (
            LITURGICAL_PALETTES.get(current_season, LITURGICAL_PALETTES["Ordinary Time"]).get("--bg-tint","#f4f9f4"),
            LITURGICAL_PALETTES.get(current_season, LITURGICAL_PALETTES["Ordinary Time"]).get("--gold-mid","#3a8a3a"),
            LITURGICAL_PALETTES.get(current_season, LITURGICAL_PALETTES["Ordinary Time"]).get("--brown","#2d6a2d"),
        ),
    }

    theme_swatches = ""
    for key, (label, desc, _) in THEMES.items():
        bg, accent, brown = SWATCH_COLORS.get(key, ("#fff","#888","#888"))
        is_sel = (key == current_theme)
        sel_ring = "box-shadow:0 0 0 3px var(--ink),0 0 0 5px var(--gold-mid);" if is_sel else ""
        extra_label = f" · {current_season}" if key == "liturgical" else ""

        theme_swatches += (
            f'<label style="cursor:pointer;display:flex;flex-direction:column;'
            f'align-items:center;gap:6px;padding:10px 8px;border-radius:12px;'
            f'border:2px solid {"var(--ink)" if is_sel else "var(--border)"};'
            f'background:{"var(--gold-light)" if is_sel else "var(--warm-white)"};'
            f'min-width:90px;transition:all 0.15s;">'
            f'<input type="radio" name="color_theme" value="{key}" '
            f'{"checked" if is_sel else ""} '
            f'style="display:none;" onchange="selectTheme(\'{key}\')">'
            # Mini preview
            f'<div style="width:56px;height:38px;border-radius:8px;border:1px solid #ccc;'
            f'background:{bg};display:flex;flex-direction:column;overflow:hidden;">'
            # Mock header bar
            f'<div style="height:10px;background:{accent};"></div>'
            # Mock content
            f'<div style="flex:1;padding:3px 4px;display:flex;flex-direction:column;gap:2px;">'
            f'<div style="height:3px;border-radius:2px;background:{brown};width:70%;"></div>'
            f'<div style="height:3px;border-radius:2px;background:{accent}44;width:90%;"></div>'
            f'<div style="height:3px;border-radius:2px;background:{brown}66;width:55%;"></div>'
            f'</div></div>'
            # Label
            f'<div style="font-size:0.72em;font-weight:600;color:var(--ink);text-align:center;'
            f'line-height:1.3;">{escape(label)}{escape(extra_label)}</div>'
            f'</label>'
        )

    return f"""
    <div class="settings-section" id="s-general">
        <h2>General</h2>
        <label>Family name <span class="small">(shown in page titles)</span></label>
        <input type="text" name="family_name" value="{escape(family_name)}"
               placeholder="Our Family" style="max-width:320px;">
        <label>Timezone</label>
        <select name="timezone" style="max-width:320px;">{tz_opts}</select>
        <p class="small" style="margin-top:-10px;">
            Controls the Now/Next strip and schedule highlighting.
        </p>
        <label>Location <span class="small">(city or zip — used for weather on the daily bar)</span></label>
        <input type="text" name="location" value="{escape(location)}"
               placeholder="e.g. Fredericksburg, VA or 22401" style="max-width:320px;">
        <input type="hidden" name="van_epoch" value="{escape(settings.get('van_epoch','2025-01-06'))}">

        <h3 style="margin-top:24px;">App Color Theme</h3>
        <p class="small" style="margin-bottom:14px;">
            Choose how the app looks. <strong>Liturgical Seasons</strong> automatically
            shifts colors with the Church calendar &mdash; purple for Lent and Advent,
            gold for Christmas and Easter, green for Ordinary Time, red for Holy Week.
        </p>
        <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:8px;">
            {theme_swatches}
        </div>
    </div>"""


def _section_children(settings: dict, children: list) -> str:
    child_colors = settings.get("child_colors", SETTINGS_DEFAULTS["child_colors"])

    def hour_options(selected: int) -> str:
        opts = ""
        for h in range(0, 24):
            ampm   = "AM" if h < 12 else "PM"
            disp_h = h if h <= 12 else h - 12
            if disp_h == 0: disp_h = 12
            opts += f'<option value="{h}" {"selected" if h == selected else ""}>{disp_h}:00 {ampm}</option>'
        return opts

    start_hour = int(settings.get("schedule_start_hour", 6))
    end_hour   = int(settings.get("schedule_end_hour",   22))

    color_cards = ""
    for child in children:
        colors = child_colors.get(child, SETTINGS_DEFAULTS["child_colors"].get(child, {"bg":"#888","text":"#fff","light":"#f5f5f5"}))
        bg    = colors.get("bg",    "#888")
        text  = colors.get("text",  "#fff")
        light = colors.get("light", "#f5f5f5")
        swatches = ""
        for pb, pl, pn in COLOR_PRESETS:
            active = "outline:3px solid #333;outline-offset:2px;" if pb == bg else ""
            ce = child.replace(" ","_")
            swatches += (
                f'<span title="{escape(pn)}" '
                f'onclick="applyPreset(\'{ce}\',\'{pb}\',\'{pl}\')" '
                f'style="display:inline-block;width:24px;height:24px;border-radius:50%;'
                f'background:{pb};cursor:pointer;margin:2px;{active}"></span>'
            )
        ce = child.replace(" ","_")
        color_cards += f"""
        <div class="card card-tight" style="border-left:5px solid {bg};background:{light};">
            <h3 style="color:{bg};margin-bottom:10px;">{escape(child)}</h3>
            <div style="margin-bottom:10px;">{swatches}</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">
                <div>
                    <label>Main color</label>
                    <div style="display:flex;align-items:center;gap:6px;">
                        <input type="color" name="color_bg_{ce}" value="{escape(bg)}"
                               id="bg_{ce}" oninput="updatePreview('{ce}')"
                               style="width:44px;height:34px;padding:2px;border:1px solid #ddd;border-radius:6px;cursor:pointer;margin-bottom:0;">
                        <input type="text" name="color_bg_{ce}_hex" value="{escape(bg)}"
                               id="bghex_{ce}" oninput="syncHex('{ce}','bg')"
                               style="width:80px;margin-bottom:0;font-size:0.82em;">
                    </div>
                </div>
                <div>
                    <label>Text color</label>
                    <input type="color" name="color_text_{ce}" value="{escape(text)}"
                           style="width:44px;height:34px;padding:2px;border:1px solid #ddd;border-radius:6px;cursor:pointer;margin-bottom:0;">
                </div>
                <div>
                    <label>Light bg</label>
                    <div style="display:flex;align-items:center;gap:6px;">
                        <input type="color" name="color_light_{ce}" value="{escape(light)}"
                               id="light_{ce}" oninput="updatePreview('{ce}')"
                               style="width:44px;height:34px;padding:2px;border:1px solid #ddd;border-radius:6px;cursor:pointer;margin-bottom:0;">
                        <input type="text" name="color_light_{ce}_hex" value="{escape(light)}"
                               id="lighthex_{ce}" oninput="syncHex('{ce}','light')"
                               style="width:80px;margin-bottom:0;font-size:0.82em;">
                    </div>
                </div>
            </div>
            <div id="preview_{ce}" style="margin-top:10px;padding:8px 12px;border-radius:8px;
                 background:{light};border-left:4px solid {bg};">
                <span style="color:{bg};font-weight:700;font-size:0.88em;">
                    {escape(child)} — schedule card preview
                </span>
            </div>
        </div>"""

    # Build plan-column checkboxes before f-string
    from daily_schedule_engine import CHILDREN as _C2
    plan_columns = settings.get("plan_columns", list(_C2))
    col_html = ""
    for person in (list(_C2) + ["Mom"]):
        checked = "checked" if person in plan_columns else ""
        col_html += (
            f'<label style="display:flex;align-items:center;gap:6px;'
            f'font-weight:500;cursor:pointer;margin-bottom:0;">'
            f'<input type="checkbox" name="plan_columns" value="{escape(person)}" {checked}'
            f' style="width:auto;margin-bottom:0;"> {escape(person)}</label>'
        )

    return f"""
    <div class="settings-section" id="s-children">
        <h2>Children</h2>
        <p class="small" style="margin-bottom:16px;">
            Click a swatch for a quick preset or use the pickers for custom colors.
        </p>
        <div class="grid">{color_cards}</div>

        <h3 style="margin-top:20px;">Schedule Grid Hours</h3>
        <p class="small" style="margin-bottom:12px;">
            Which hours appear in the Family Rule of Life grid and timeline.
        </p>
        <div style="display:flex;gap:24px;flex-wrap:wrap;">
            <div>
                <label>Start time</label>
                <select name="schedule_start_hour" style="max-width:180px;margin-bottom:0;">
                    {hour_options(start_hour)}
                </select>
            </div>
            <div>
                <label>End time</label>
                <select name="schedule_end_hour" style="max-width:180px;margin-bottom:0;">
                    {hour_options(end_hour)}
                </select>
            </div>
        </div>

        <h3 style="margin-top:20px;">Daily Plan Columns</h3>
        <p class="small" style="margin-bottom:12px;">
            Choose whose schedule appears as columns in the Plan editor.
        </p>
        <div style="display:flex;gap:16px;flex-wrap:wrap;">
            {col_html}
        </div>
    </div>"""


def _section_daily(settings: dict, children: list) -> str:
    birthdays      = settings.get("child_birthdays",  {})
    special_events = settings.get("special_events",   [])

    # Birthday fields per child
    bday_fields = ""
    for child in children:
        dob = birthdays.get(child, "")
        bday_fields += f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;flex-wrap:wrap;">
            <label style="min-width:80px;margin-bottom:0;">{escape(child)}</label>
            <input type="date" name="birthday_{escape(child)}" value="{escape(dob)}"
                   style="max-width:180px;margin-bottom:0;">
        </div>"""

    # Special events list — up to 10
    event_rows = ""
    for i in range(max(len(special_events), 5)):
        ev    = special_events[i] if i < len(special_events) else {}
        label = ev.get("label", "")
        edate = ev.get("date",  "")
        event_rows += f"""
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:8px;flex-wrap:wrap;">
            <input type="text" name="event_label_{i}" value="{escape(label)}"
                   placeholder="e.g. Grandma's birthday" style="flex:1;min-width:200px;max-width:340px;margin-bottom:0;">
            <input type="date" name="event_date_{i}" value="{escape(edate)}"
                   style="max-width:160px;margin-bottom:0;">
            <span class="small" style="color:#aaa;">leave date blank = show every day</span>
        </div>"""

    return f"""
    <div class="settings-section" id="s-daily">
        <h2>Daily Bar</h2>
        <p class="small" style="margin-bottom:16px;">
            The daily bar appears at the top of the dashboard, Today page, child schedule pages,
            and print-outs. It shows weather (set location in General), saint/feast of the day,
            mass readings link, and any special events you add here.
        </p>

        <h3>Child Birthdays</h3>
        <p class="small" style="margin-bottom:12px;">
            Used to show each child's age in months, weeks, days, and hours on their schedule page
            and print-out.
        </p>
        {bday_fields}

        <h3 style="margin-top:18px;">Special Events</h3>
        <p class="small" style="margin-bottom:12px;">
            Each event with a date shows only on that date. Leave the date blank to show every day
            (useful for ongoing things like "40-day prayer challenge").
        </p>
        {event_rows}
    </div>"""


def _section_systems(settings: dict) -> str:
    from render_chores import (
        LAUNDRY_WORKFLOW, LAUNDRY_DEFAULTS,
        VAN_ROLE_A_TASKS, VAN_ROLE_B_DESCRIPTION,
        get_van_roles, VACUUM_LABELS, WIPE_LABELS,
        VAN_ROLE_B_VACUUM_WK1, VAN_ROLE_B_VACUUM_WK2,
        VAN_ROLE_B_WIPE_WK1, VAN_ROLE_B_WIPE_WK2,
        VAN_ROLE_B_WIPE_WK3, VAN_ROLE_B_WIPE_WK4,
    )

    van_epoch = settings.get("van_epoch", "2025-01-06")

    # Van status
    try:
        epoch_date    = date.fromisoformat(van_epoch)
        this_monday   = date.today() - timedelta(days=date.today().weekday())
        weeks_elapsed = (this_monday - epoch_date).days // 7
        current_week  = (weeks_elapsed % 3) + 1
        roles         = get_van_roles()
        van_status    = (
            f'Week {current_week} of 3 — '
            f'JP: <strong>{escape(roles["JP"])}</strong> · '
            f'Joseph: <strong>{escape(roles["Joseph"])}</strong>'
        )
    except Exception:
        van_status = "Set epoch date below to activate rotation."

    # Laundry schedule table
    laundry_rows = ""
    for day, person, task in [
        ("Monday",    "JP",             "Mom's laundry"),
        ("Tuesday",   "Mom",            "James + towels"),
        ("Wednesday", "Joseph",         "Own laundry (may be multiple loads; towels → downstairs hamper)"),
        ("Thursday",  "JP",             "Own laundry"),
        ("Friday",    "Joseph + Michael","Michael's laundry — Joseph assists"),
        ("Sat/Sun",   "Anyone",         "Overflow / catch-up as needed"),
    ]:
        laundry_rows += (
            f"<tr><td style='padding:5px 10px;font-weight:600;color:#555;white-space:nowrap;'>{escape(day)}</td>"
            f"<td style='padding:5px 10px;font-weight:600;color:#2471a3;'>{escape(person)}</td>"
            f"<td style='padding:5px 10px;color:#333;font-size:0.9em;'>{escape(task)}</td></tr>"
        )
    wf_items = "".join(f"<li style='margin-bottom:3px;'>{escape(s)}</li>" for s in LAUNDRY_WORKFLOW)

    # Van role descriptions
    role_a = "".join(f"<li>{escape(t.lstrip('  →').strip())}</li>" for t in VAN_ROLE_A_TASKS[1:])
    role_b = "".join(f"<li>{escape(t.lstrip('  →').strip())}</li>" for t in VAN_ROLE_B_DESCRIPTION[1:])

    # Vacuum + wipe-down rotation reference
    vac_ref = ""
    for wk, label in VACUUM_LABELS.items():
        steps = VAN_ROLE_B_VACUUM_WK1 if wk == 1 else VAN_ROLE_B_VACUUM_WK2
        step_html = " ".join(s.lstrip("  →").strip() for s in steps)
        vac_ref += f"<div style='padding:5px 0;border-bottom:1px solid #f0ebe4;font-size:0.86em;'><strong>Wk {wk}:</strong> {escape(step_html)}</div>"

    wipe_ref = ""
    for wk, label in WIPE_LABELS.items():
        steps = {1:VAN_ROLE_B_WIPE_WK1, 2:VAN_ROLE_B_WIPE_WK2, 3:VAN_ROLE_B_WIPE_WK3, 4:VAN_ROLE_B_WIPE_WK4}[wk]
        step_html = " ".join(s.lstrip("  →").strip() for s in steps)
        wipe_ref += f"<div style='padding:5px 0;border-bottom:1px solid #f0ebe4;font-size:0.86em;'><strong>Wk {wk}:</strong> {escape(step_html)}</div>"

    # NOTE: The full FROL editor used to live here as a duplicate half-hour
    # grid. It has been removed in favour of the canonical "Family day grid"
    # on the Mom dashboard (/mom#grid), which is the single editor the More
    # menu's "Family Rule of Life" tile already opens. Both editors wrote to
    # the same day_templates files, so removing this one loses no data — it
    # just eliminates a confusing duplicate UI.
    return f"""
    <div class="settings-section" id="s-systems">
        <h2>Systems</h2>

        <!-- Laundry -->
        <div>
            <h3 style="margin-bottom:14px;">🧺 Laundry System <span class="small" style="font-weight:400;">— locked weekly rotation</span></h3>
            <div>
                <div class="two-col" style="gap:20px;margin-bottom:14px;">
                    <div>
                        <h4>Weekly Schedule</h4>
                        <table style='border-collapse:collapse;width:100%;font-size:0.88em;'>
                            <thead><tr style='background:#dbeef9;'>
                                <th style='padding:4px 10px;text-align:left;'>Day</th>
                                <th style='padding:4px 10px;text-align:left;'>Who</th>
                                <th style='padding:4px 10px;text-align:left;'>What</th>
                            </tr></thead>
                            <tbody>{laundry_rows}</tbody>
                        </table>
                    </div>
                    <div>
                        <h4>Required Workflow (every laundry day)</h4>
                        <ol style='font-size:0.88em;padding-left:18px;margin:0;'>{wf_items}</ol>
                        <div style='margin-top:10px;padding:8px 12px;background:#fff8e1;
                                    border:1px solid #f9ca24;border-radius:8px;font-size:0.85em;'>
                            <strong>Family Fold Block</strong> — fold together with audiobook/read-aloud.
                            Laundry is only done when fully put away.
                        </div>
                    </div>
                </div>
                <form method="POST" action="/apply-laundry" style="display:inline;">
                    <button type="submit">Apply Laundry Schedule to Weekly Chores</button>
                </form>
                <p class="small" style="margin-top:6px;">
                    Writes the step-by-step workflow into each child's weekly chore list.
                    Safe to re-run — only replaces LAUNDRY lines.
                </p>
            </div>
            </div>
        </div>

        <hr style="border:none;border-top:1px solid #f0ebe4;margin:20px 0;">

        <!-- Van Rotation -->
        <div>
            <h3 style="margin-bottom:14px;">🚐 Van Cleaning Rotation <span class="small" style="font-weight:400;">— 3-week auto-cycle</span></h3>
            <div>
                <p class="small" style="margin-bottom:12px;">{van_status}</p>
                <label>Week 1 epoch (must be a Monday)</label>
                <input type="date" name="van_epoch" value="{escape(van_epoch)}"
                       style="max-width:200px;">
                <p class="small" style="margin-top:-10px;margin-bottom:14px;">
                    The 3-week cycle advances automatically from this Monday.
                    Changing it takes effect immediately on save.
                </p>

                <div class="two-col" style="gap:16px;margin-bottom:14px;">
                    <div class="card card-tight" style="background:#fef9c3;border-color:#fde047;">
                        <h4 style="color:#713f12;">Role A — Interior Reset Lead</h4>
                        <ul style='font-size:0.88em;padding-left:18px;margin:0;'>{role_a}</ul>
                    </div>
                    <div class="card card-tight" style="background:#dbeafe;border-color:#93c5fd;">
                        <h4 style="color:#1e3a8a;">Role B — Vacuum &amp; Wipe-down Lead</h4>
                        <ul style='font-size:0.88em;padding-left:18px;margin:0;'>{role_b}</ul>
                    </div>
                </div>
                <div class="two-col" style="gap:16px;margin-bottom:14px;">
                    <div class="card card-tight">
                        <h4>🧹 Vacuum (2-week cycle)</h4>
                        {vac_ref}
                    </div>
                    <div class="card card-tight">
                        <h4>🧽 Wipe-down (4-week cycle)</h4>
                        {wipe_ref}
                    </div>
                </div>

                <form method="POST" action="/apply-van-rotation" style="display:inline;">
                    <button type="submit">Apply This Week's Rotation to Monday Chores</button>
                </form>
                <a class="link-button" href="/van-roles" style="margin-left:8px;">View Upcoming Rotation</a>
            </div>
            </div>
        </div>

        <hr style="border:none;border-top:1px solid #f0ebe4;margin:20px 0;">

        <!-- Family Rule of Life — pointer to the single source of truth -->
        <div>
            <h3 style="margin-bottom:14px;">📅 Family Rule of Life</h3>
            <div class="card card-tight" style="background:#faf8f5;border:1px solid #e4dbd2;">
                <p style="margin:0 0 10px;">
                    The Family Rule of Life now lives in one place — the
                    <strong>Family day grid</strong> on the Mom dashboard.
                    That grid is the single source of truth for everyone's
                    weekly rhythm and is what drives every Day List.
                </p>
                <a class="link-button" href="/mom#grid"
                   style="font-weight:600;">📋✓ Open Family Rule of Life →</a>
            </div>
        </div>
    </div>"""


def _section_integrations() -> str:
    cfg          = load_calendar_config()
    apple_id     = cfg.get("apple_id",     "")
    app_password = cfg.get("app_password", "")
    cache        = ensure_file("data/calendar_cache.json", {"events":[],"fetched_at":""})
    fetched_at   = cache.get("fetched_at", "")
    pw_ph        = "••••••••••••••••" if app_password else "xxxx-xxxx-xxxx-xxxx"
    pw_note      = "Password saved. Leave blank to keep existing." if app_password else "Paste your app-specific password here."
    connected    = (
        '<span style="background:#eef7ee;border:1px solid #c3e0c3;color:#2a5a2a;'
        'padding:2px 8px;border-radius:999px;font-size:0.8em;font-weight:600;">✓ Connected</span>'
        if apple_id else
        '<span style="background:#fef0f0;border:1px solid #f0c0c0;color:#a00;'
        'padding:2px 8px;border-radius:999px;font-size:0.8em;font-weight:600;">Not connected</span>'
    )
    saved_line  = f"<p class='small' style='margin-bottom:8px;'><strong>Saved:</strong> {escape(apple_id)}</p>" if apple_id else ""
    sync_line   = f'<p class="small" style="color:#888;">Last synced: {escape(fetched_at[:16].replace("T"," "))}</p>' if fetched_at else ""

    subs     = load_subscribed_calendars()
    sub_rows = ""

    # Load cached events to show per-calendar status
    try:
        from data_helpers import load_subscribed_calendar_cache
        sub_cache    = load_subscribed_calendar_cache()
        cached_events = sub_cache.get("events", [])
        fetched_at   = sub_cache.get("fetched_at", "")
        # Count events per calendar name
        cal_counts = {}
        for ev in cached_events:
            n = ev.get("calendar","")
            cal_counts[n] = cal_counts.get(n, 0) + 1
        if fetched_at:
            try:
                from datetime import datetime as _dt2
                fa = _dt2.fromisoformat(fetched_at)
                cache_age = _dt2.now() - fa
                mins = int(cache_age.total_seconds() // 60)
                if mins < 60:
                    cache_label = f"{mins}m ago"
                elif mins < 1440:
                    cache_label = f"{mins//60}h ago"
                else:
                    cache_label = fa.strftime("%b %d")
            except Exception:
                cache_label = "unknown"
        else:
            cache_label = "never"
    except Exception:
        cal_counts  = {}
        cache_label = "unknown"

    for i, cal in enumerate(subs):
        cal_color = escape(cal.get("color","#9b59b6"))
        cal_name  = escape(cal.get("name",""))
        cal_url   = escape(cal.get("url","")[:60])
        cal_enabled = cal.get("enabled", True)

        # Live connection test (quick HEAD/GET)
        connection_ok = None
        if cal_enabled and cal.get("url",""):
            try:
                import urllib.request as _ur3
                test_url = cal.get("url","").replace("webcal://","https://").replace("webcal:","https:")
                _req = _ur3.Request(test_url, headers={"User-Agent":"FamilyPlanner/1.0"}, method="HEAD")
                with _ur3.urlopen(_req, timeout=4) as _r:
                    connection_ok = (_r.getcode() < 400)
            except Exception:
                connection_ok = False

        # Status badge
        count = cal_counts.get(cal.get("name",""), None)
        if not cal_enabled:
            status_badge = '<span style="font-size:0.72em;background:#f3f4f6;color:#6b7280;padding:1px 7px;border-radius:8px;font-weight:600;">Disabled</span>'
        elif connection_ok is False:
            status_badge = '<span style="font-size:0.72em;background:#fee2e2;color:#991b1b;padding:1px 7px;border-radius:8px;font-weight:600;">⚠ Connection failed</span>'
        elif count is not None:
            conn_indicator = ' · 🟢 Connected' if connection_ok else ''
            status_badge = f'<span style="font-size:0.72em;background:#dcfce7;color:#166534;padding:1px 7px;border-radius:8px;font-weight:600;">✓ {count} event{"s" if count != 1 else ""}{conn_indicator}</span>'
        elif cache_label == "never":
            status_badge = '<span style="font-size:0.72em;background:#fef3c7;color:#92400e;padding:1px 7px;border-radius:8px;font-weight:600;">Not synced yet</span>'
        else:
            conn_note = ' · ⚠ Check URL' if connection_ok is False else (' · 🟢 URL OK' if connection_ok else '')
            status_badge = f'<span style="font-size:0.72em;background:#fee2e2;color:#991b1b;padding:1px 7px;border-radius:8px;font-weight:600;">0 events in range{conn_note}</span>'

        # Enable/disable toggle
        toggle_label = "Disable" if cal_enabled else "Enable"

        sub_rows += f"""
        <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #f5f0eb;flex-wrap:wrap;">
            <span style="width:12px;height:12px;border-radius:50%;background:{cal_color};flex-shrink:0;"></span>
            <div style="flex:1;min-width:0;">
                <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                    <strong style="font-size:0.88em;">{cal_name}</strong>
                    {status_badge}
                </div>
                <div style="font-size:0.72em;color:#aaa;word-break:break-all;margin-top:2px;">{cal_url}</div>
            </div>
            <div style="display:flex;gap:6px;flex-shrink:0;">
                <form method="POST" action="/subscribed-cal-toggle" style="display:inline;">
                    <input type="hidden" name="index" value="{i}">
                    <button type="submit" class="ghost" style="padding:3px 8px;font-size:0.78em;">{toggle_label}</button>
                </form>
                <form method="POST" action="/subscribed-cal-delete" style="display:inline;">
                    <input type="hidden" name="index" value="{i}">
                    <button type="submit" class="ghost" style="padding:3px 8px;font-size:0.78em;color:#ef4444;border-color:#fecaca;">Remove</button>
                </form>
            </div>
        </div>"""

    if subs and cache_label != "never":
        sub_rows += f'<div style="font-size:0.72em;color:#aaa;padding:4px 0;">Last synced: {cache_label} &middot; <a href="/calendar-refresh" style="color:var(--brown);">Sync now</a></div>'

    color_opts = "".join(f'<option value="{c}">{n}</option>' for c,n in CAL_COLOR_OPTIONS)

    return f"""
    <div class="settings-section" id="s-integrations">
        <h2>Integrations</h2>

        <!-- iCloud Calendar -->
        <div>
            <h3 style="margin-bottom:14px;">📆 iCloud Calendar {connected}</h3>
            <div>
                {saved_line}
                <p class="small" style="margin-bottom:10px;">
                    Get an app-specific password at
                    <a href="https://appleid.apple.com" target="_blank">appleid.apple.com</a>
                    → Sign-In &amp; Security → App-Specific Passwords.
                </p>
                <form method="POST" action="/calendar-save-config">
                    <label>Apple ID</label>
                    <input type="text" name="apple_id" value="{escape(apple_id)}"
                           placeholder="yourname@icloud.com" autocomplete="off" style="max-width:320px;">
                    <label>App-Specific Password</label>
                    <input type="text" name="app_password" value=""
                           placeholder="{pw_ph}" autocomplete="off" style="max-width:280px;">
                    <p class="small" style="margin-top:-10px;margin-bottom:10px;">{pw_note}</p>
                    <button type="submit">Save Calendar Credentials</button>
                </form>
                {sync_line}
                <form method="POST" action="/calendar-refresh" style="margin-top:8px;display:inline;">
                    <button type="submit" class="secondary">↻ Sync Now</button>
                </form>
            </div>
            </div>
        </div>

        <hr style="border:none;border-top:1px solid #f0ebe4;margin:20px 0;">

        <!-- Subscribed Calendars -->
        <div>
            <h3 style="margin-bottom:14px;">📋 Subscribed Calendars (.ics feeds)</h3>
            <div>
                <p class="small" style="margin-bottom:12px;">
                    Paste any public .ics URL — school, church, sports, Proton Calendar. No login required.
                </p>
                {sub_rows or "<p class='muted' style='margin-bottom:12px;'>No subscribed calendars yet.</p>"}
                <form method="POST" action="/subscribed-cal-add">
                    <label>Calendar Name</label>
                    <input type="text" name="name" placeholder="e.g. School Events" style="max-width:280px;">
                    <label>ICS URL</label>
                    <input type="text" name="url" placeholder="https://..." style="max-width:440px;">
                    <label>Color</label>
                    <select name="color" style="max-width:160px;">{color_opts}</select>
                    <button type="submit">Add Calendar</button>
                </form>
            </div>
            </div>
        </div>
    </div>"""


def _lucy_knowledge_summary(settings: dict) -> str:
    """A quick-scan card showing what Lucy currently has access to."""
    c = settings.get("family_constraints", {})
    api_key = c.get("anthropic_api_key", "")

    def _chip(label: str, value: str, color: str = "#27ae60") -> str:
        has = bool(value.strip()) if isinstance(value, str) else bool(value)
        col  = color if has else "#aaa"
        icon = "✓" if has else "○"
        bg   = "#dcfce7" if has else "#f3f4f6"
        txt  = "#166534" if has else "#6b7280"
        return (
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'background:{bg};color:{txt};border-radius:20px;padding:3px 10px;'
            f'font-size:.72em;font-weight:700;margin:3px 3px 3px 0;white-space:nowrap;">'
            f'{icon} {escape(label)}</span>'
        )

    # Build chips
    fields = [
        ("API Key",          api_key),
        ("James schedule",   c.get("james_schedule", "")),
        ("Supervision rules",c.get("supervision_rules", "")),
        ("Independence",     c.get("independence_notes", "")),
        ("School durations", c.get("school_durations", "")),
        ("Mom subjects",     c.get("mom_supervision_subjects", "")),
        ("Meal prep",        c.get("meal_prep", "")),
        ("Exercise",         c.get("family_exercise", "")),
        ("Other notes",      c.get("other_notes", "")),
    ]
    chips = "".join(_chip(label, val) for label, val in fields)

    rules = c.get("lucy_rules", [])
    rules_chip = (
        f'<span style="display:inline-flex;align-items:center;gap:4px;'
        f'background:#dbeafe;color:#1e40af;border-radius:20px;padding:3px 10px;'
        f'font-size:.72em;font-weight:700;margin:3px 3px 3px 0;">'
        f'📋 {len(rules)} standing rule{"s" if len(rules) != 1 else ""}</span>'
    ) if rules else _chip("No Lucy rules yet", "")

    # Build a plain-English "briefing" summary
    summary_parts = []
    if c.get("james_schedule"):
        summary_parts.append(f"James: {c['james_schedule'][:60].rstrip()}")
    if c.get("supervision_rules"):
        summary_parts.append(f"Supervision: {c['supervision_rules'][:60].rstrip()}")
    if c.get("other_notes"):
        summary_parts.append(f"Notes: {c['other_notes'][:80].rstrip()}")
    for rule in rules[:3]:
        summary_parts.append(f"Rule: {rule[:70].rstrip()}")

    preview_html = ""
    if summary_parts:
        items = "".join(
            f'<li style="font-size:.78em;color:var(--ink-muted);line-height:1.5;margin-bottom:2px;">'
            f'{escape(p)}</li>'
            for p in summary_parts
        )
        more = f' <span style="color:#aaa;font-size:.72em;">(+{len(summary_parts)-3} more)</span>' if len(summary_parts) > 3 else ""
        preview_html = f'<ul style="margin:6px 0 0 14px;padding:0;">{items}</ul>{more}'

    key_status = (
        '<span style="font-size:.72em;font-weight:700;color:#166534;background:#dcfce7;'
        'padding:2px 10px;border-radius:10px;">✓ Connected</span>'
        if api_key else
        '<span style="font-size:.72em;font-weight:700;color:#92400e;background:#fef3c7;'
        'padding:2px 10px;border-radius:10px;">⚠ No API key</span>'
    )

    return f"""
<div style="background:var(--gold-light);border:1.5px solid var(--gold-mid);
            border-radius:12px;padding:14px 16px;margin-bottom:18px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;flex-wrap:wrap;gap:6px;">
    <div style="font-weight:700;font-size:.88em;color:var(--ink);">🤖 What Lucy knows right now</div>
    {key_status}
  </div>
  <div style="margin-bottom:6px;">{chips} {rules_chip}</div>
  {preview_html}
  <div style="font-size:.7em;color:#aaa;margin-top:8px;">
    Fill in any ○ fields below — Lucy reads these every time you chat.
  </div>
</div>"""


_DEFAULT_CORE = "Math, Religion, Reading"

def _school_mode_section(c: dict) -> str:
    """Render the school mode controls: dropdown + conditional fields."""
    mode         = c.get("school_mode", "normal")
    core_subs    = c.get("core_subjects", _DEFAULT_CORE)
    paused_subs  = c.get("paused_subjects", "")
    sel_normal   = 'selected' if mode == "normal"       else ''
    sel_light    = 'selected' if mode == "light_week"   else ''
    sel_custom   = 'selected' if mode == "custom_pause" else ''
    show_light   = '' if mode == "light_week"   else 'display:none;'
    show_custom  = '' if mode == "custom_pause" else 'display:none;'
    return f"""
<div style="margin-bottom:12px;">
    <label style="font-size:.85em;font-weight:600;display:block;margin-bottom:6px;">Active mode</label>
    <select name="fc_school_mode" id="school-mode-select"
            style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;
                   font-size:.9em;font-family:inherit;background:#fff;"
            onchange="smToggle(this.value)">
        <option value="normal"       {sel_normal} >Normal week — all subjects</option>
        <option value="light_week"   {sel_light}  >Light week — core subjects only</option>
        <option value="custom_pause" {sel_custom} >Custom — hide specific subjects</option>
    </select>
</div>
<div id="sm-light-block" style="{show_light}margin-bottom:12px;">
    <label style="font-size:.85em;font-weight:600;display:block;margin-bottom:4px;">Core subjects (shown during light week)</label>
    <input type="text" name="fc_core_subjects" value="{escape(core_subs)}"
           placeholder="{_DEFAULT_CORE}"
           style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;
                  font-size:.9em;font-family:inherit;box-sizing:border-box;">
    <p class="small" style="margin-top:4px;">Separate with commas. Partial match is fine (e.g. "Math" matches "Algebra 1/2").</p>
</div>
<div id="sm-pause-block" style="{show_custom}margin-bottom:12px;">
    <label style="font-size:.85em;font-weight:600;display:block;margin-bottom:4px;">Paused subjects (hidden from daily lists)</label>
    <input type="text" name="fc_paused_subjects" value="{escape(paused_subs)}"
           placeholder="e.g. Latin, Spelling, History, Science, Music"
           style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:6px;
                  font-size:.9em;font-family:inherit;box-sizing:border-box;">
    <p class="small" style="margin-top:4px;">Separate with commas. Partial match is fine.</p>
</div>
<script>
function smToggle(v) {{
    document.getElementById('sm-light-block').style.display  = v==='light_week'   ? '' : 'none';
    document.getElementById('sm-pause-block').style.display  = v==='custom_pause' ? '' : 'none';
}}
</script>"""


def _lucy_rules_section(rules: list) -> str:
    """Render the list of Lucy-set standing rules with delete buttons."""
    if not rules:
        return '<p class="small" style="color:#aaa;font-style:italic;">No rules saved yet. Talk to Lucy to create them.</p>'
    items = ""
    for i, rule in enumerate(rules):
        safe = escape(rule)
        items += f"""
        <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:8px;
                    padding:8px 12px;background:#f9f9f4;border:1px solid #e0ddd0;border-radius:6px;">
            <span style="flex:1;font-size:0.88em;line-height:1.4;">{safe}</span>
            <button onclick="lucyDeleteRule({i}, this)"
                    style="background:none;border:none;color:#c0392b;cursor:pointer;
                           font-size:0.82em;padding:0 4px;white-space:nowrap;">✕ Delete</button>
        </div>"""
    return f"""
        {items}
        <script>
        function lucyDeleteRule(idx, btn) {{
            var rules = {rules!r};
            var rule  = rules[idx];
            if (!rule) return;
            btn.disabled = true;
            btn.textContent = '…';
            fetch('/lucy-rule-save', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'action=remove&rule=' + encodeURIComponent(rule)
            }}).then(function(r) {{
                if (r.ok) {{ location.reload(); }}
            }});
        }}
        </script>"""


def _section_constraints(settings: dict) -> str:
    c = settings.get("family_constraints", {})
    def field(label, name, placeholder, value, rows=0):
        val = escape(c.get(name, value))
        if rows:
            return (f'<label>{label}</label>'
                    f'<textarea name="fc_{name}" rows="{rows}" placeholder="{placeholder}"'
                    f' style="margin-bottom:12px;font-size:0.88em;resize:vertical;">{val}</textarea>')
        return (f'<label>{label}</label>'
                f'<input type="text" name="fc_{name}" value="{val}"'
                f' placeholder="{placeholder}" style="max-width:560px;margin-bottom:12px;">')

    api_key = c.get("anthropic_api_key", "")
    key_display = "•" * len(api_key) if api_key else ""

    # The Anthropic key is now sourced exclusively from the ANTHROPIC_API_KEY
    # Replit secret (see load_app_settings). The form input below is shown
    # for visibility only and has no effect — render an explicit warning if
    # the secret is missing so Lauren knows where to add it.
    _env_present = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    if _env_present:
        env_status_html = (
            '<div style="background:#dcfce7;border:1.5px solid #16a34a;'
            'border-radius:8px;padding:10px 14px;margin-bottom:12px;'
            'color:#166534;font-size:0.88em;">'
            '<strong>&#10003; ANTHROPIC_API_KEY loaded from Replit Secrets.</strong> '
            'AI features are active.'
            '</div>'
        )
        env_status_chip = '<span style="font-size:0.82em;color:#27ae60;">&#10003; Key loaded from Replit Secrets</span>'
    else:
        env_status_html = (
            '<div style="background:#fef2f2;border:2px solid #dc2626;'
            'border-radius:8px;padding:12px 16px;margin-bottom:12px;'
            'color:#7f1d1d;font-size:0.92em;line-height:1.5;">'
            '<div style="font-weight:700;margin-bottom:6px;font-size:1.0em;">'
            '&#9888;&#65039; ANTHROPIC_API_KEY is not set in Replit Secrets.'
            '</div>'
            '<div>'
            'AI features (Lucy, Lorenzo, Father Gregory, Coach, Dr. Monica, '
            'plan importer, assignment analyzer, weekly school plan) are '
            'currently disabled. Open the Replit <strong>Secrets</strong> '
            'panel (lock icon in the left sidebar) and add a secret named '
            '<code>ANTHROPIC_API_KEY</code> with your Anthropic key value, '
            'then restart the app.'
            '</div>'
            '</div>'
        )
        env_status_chip = '<span style="font-size:0.82em;color:#dc2626;font-weight:700;">&#9888;&#65039; Not set — add to Replit Secrets</span>'

    return f"""
    <div class="settings-section" id="s-constraints">
        <h2>Family Constraints <span class="small" style="font-weight:400;">— used by the AI scheduling assistant</span></h2>
        {_lucy_knowledge_summary(settings)}

        <h3>Anthropic API Key</h3>
        {env_status_html}
        <p class="small" style="margin-bottom:8px;">
            Required for AI suggestions. The key is loaded from the
            <code>ANTHROPIC_API_KEY</code> Replit secret &mdash; the input
            box below is shown for reference only and is not editable from
            the UI. Get a key at
            <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a>
            &rarr; API Keys.
        </p>
        <div style="display:flex;gap:8px;align-items:center;margin-bottom:20px;">
            <input type="password" name="fc_anthropic_api_key"
                   value="{escape(api_key)}"
                   placeholder="sk-ant-..." readonly
                   style="max-width:380px;margin-bottom:0;font-family:monospace;font-size:0.85em;background:#f3f4f6;color:#6b7280;">
            {env_status_chip}
        </div>

        <h3>James care schedule</h3>
        {field("Nap times, feeding schedule, wake windows",
               "james_schedule",
               "e.g. Nap 12:30–2:30pm. Feed every 3hrs. Wake windows ~2hrs.",
               "", rows=2)}

        <h3 style="margin-top:4px;">Supervision rules</h3>
        {field("Who can supervise James, and under what conditions",
               "supervision_rules",
               "e.g. JP (17) can supervise James alone. Joseph (15) can supervise with a check-in every 30min. Michael (12) cannot supervise alone.",
               "", rows=2)}

        <h3 style="margin-top:4px;">Independent work capacity</h3>
        {field("How long each child can work alone before needing Mom",
               "independence_notes",
               "e.g. JP: 60min independent. Joseph: 45min. Michael: 20min before needs check-in.",
               "", rows=2)}

        <h3 style="margin-top:4px;">School durations</h3>
        {field("Approx. total school time per child per day",
               "school_durations",
               "e.g. JP: ~3hrs. Joseph: ~3.5hrs. Michael: ~2hrs (shorter day).",
               "", rows=1)}

        <h3 style="margin-top:4px;">Subjects needing Mom directly</h3>
        {field("Which subjects require Mom to sit with the child",
               "mom_supervision_subjects",
               "e.g. JP: Latin (30min). Joseph: Math explanations (~15min). Michael: all reading.",
               "", rows=2)}

        <h3 style="margin-top:4px;">Meal prep</h3>
        {field("Standing meal prep rules and who helps",
               "meal_prep",
               "e.g. Lunch prep 11:45am (~20min). Dinner prep 4:30pm (~45min). JP sets table. Joseph helps cook on Mon/Wed.",
               "", rows=2)}

        <h3 style="margin-top:4px;">Family exercise</h3>
        {field("Preferred outdoor/exercise activities",
               "family_exercise",
               "e.g. Walk, park, farm time — include in daily schedule.",
               "", rows=1)}

        <h3 style="margin-top:4px;">Other notes for the AI</h3>
        {field("Anything else the AI should know",
               "other_notes",
               "e.g. Co-op on Thursdays 9–12. No screens before school done. Quiet time 2–3pm.",
               "", rows=2)}

        <h3 style="margin-top:20px;">Standing rules set with Lucy</h3>
        <p class="small" style="margin-bottom:10px;">
            Rules Lucy and you have agreed on during conversation. Lucy can add or remove these as you talk.
            You can also delete them here.
        </p>
        {_lucy_rules_section(c.get("lucy_rules", []))}
    </div>"""


def _section_school(settings: dict) -> str:
    """Render the School section: mode controls + PDF upload per child."""
    c = settings.get("family_constraints", {})
    return f"""
<div style="padding:4px 0 8px;">
    <h3 style="margin-top:4px;">📚 School mode</h3>
    <p class="small" style="margin-bottom:10px;">
        Temporarily adjust which subjects appear in the boys' daily lists.
        Use <strong>Light week</strong> when sick or traveling; use <strong>Custom pause</strong>
        to hide specific subjects indefinitely.
    </p>
    {_school_mode_section(c)}
</div>"""


def _accordion(
    section_id: str,
    number: str,
    title: str,
    summary: str,
    detail: str,
    badge: str = "",
    open_by_default: bool = False,
    color: str = "var(--brown)",
) -> str:
    """
    Renders one collapsible accordion panel.
    summary  — one sentence shown always
    detail   — expanded explanation + links (hidden until "Learn more" is clicked)
    """
    open_attr  = "open" if open_by_default else ""
    detail_id  = f"detail-{section_id}"
    badge_html = (
        f'<span style="font-size:0.68em;background:{color}20;color:{color};'
        f'font-weight:700;padding:2px 8px;border-radius:10px;margin-left:6px;">'
        f'{escape(badge)}</span>'
    ) if badge else ""

    return f"""
<details id="{section_id}-wrap" {open_attr}
  style="border:1.5px solid var(--border);border-radius:14px;margin-bottom:10px;overflow:hidden;">
  <summary style="list-style:none;cursor:pointer;padding:16px 20px;
                  display:flex;align-items:center;gap:12px;
                  background:var(--parchment);user-select:none;"
           onclick="toggleAccordion('{section_id}')">
    <div style="width:28px;height:28px;border-radius:50%;background:{color};
                color:white;display:flex;align-items:center;justify-content:center;
                font-weight:800;font-size:0.78em;flex-shrink:0;">{escape(number)}</div>
    <div style="flex:1;">
      <div style="font-weight:700;font-size:0.95em;color:var(--ink);">
        {escape(title)}{badge_html}
      </div>
      <div style="font-size:0.78em;color:var(--ink-muted);margin-top:2px;">{summary}</div>
    </div>
    <div id="chevron-{section_id}"
         style="font-size:0.85em;color:var(--ink-faint);transition:transform 0.2s;
                {"transform:rotate(180deg)" if open_by_default else ""}">&#9660;</div>
  </summary>

  <div style="padding:0 20px 8px;">
    <!-- Expandable detail -->
    <div id="{detail_id}" style="display:none;margin:10px 0 6px;padding:10px 14px;
         background:var(--gold-light);border-radius:10px;font-size:0.82em;
         line-height:1.7;color:var(--ink-muted);">
      {detail}
      <div style="margin-top:6px;">
        <button onclick="document.getElementById('{detail_id}').style.display='none'"
                style="font-size:0.78em;background:none;border:none;cursor:pointer;
                       color:var(--brown);font-family:inherit;padding:0;">
          &#8593; Collapse
        </button>
      </div>
    </div>
    <div style="margin:8px 0 4px;">
      <button onclick="toggleDetail('{detail_id}')"
              style="font-size:0.75em;background:none;border:none;cursor:pointer;
                     color:var(--brown);font-family:inherit;font-weight:600;padding:0;">
        &#9432; How this works
      </button>
    </div>
  </div>
</details>"""


def _section_pins() -> str:
    """PIN management — admin only."""
    try:
        from auth import USERS, load_pins
        pins = load_pins()
    except Exception:
        return ""
    rows = ""
    order = ["lauren", "john", "jp", "joseph", "michael", "james"]
    for uid in order:
        u = USERS.get(uid, {})
        name  = u.get("name", uid.title())
        color = u.get("color", "#374151")
        no_pin = not u.get("pin_required", True)
        if no_pin:
            rows += (
                f'<div style="display:flex;align-items:center;gap:12px;padding:8px 0;'
                f'border-bottom:1px solid var(--border-light);">'
                f'<div style="width:36px;height:36px;border-radius:50%;background:{color};'
                f'display:flex;align-items:center;justify-content:center;color:white;'
                f'font-weight:800;font-size:0.78em;">{escape(u.get("initials","?"))}</div>'
                f'<div style="flex:1;font-weight:600;color:var(--ink);">{escape(name)}</div>'
                f'<span style="font-size:0.8em;color:#9ca3af;">No PIN needed (tap avatar)</span>'
                f'</div>'
            )
        else:
            cur_pin = pins.get(uid, "0000")
            masked  = "••••" if cur_pin != "0000" else "0000 (default)"
            rows += (
                f'<div style="display:flex;align-items:center;gap:12px;padding:8px 0;'
                f'border-bottom:1px solid var(--border-light);">'
                f'<div style="width:36px;height:36px;border-radius:50%;background:{color};'
                f'display:flex;align-items:center;justify-content:center;color:white;'
                f'font-weight:800;font-size:0.78em;">{escape(u.get("initials","?"))}</div>'
                f'<div style="flex:1;font-weight:600;color:var(--ink);">{escape(name)}</div>'
                f'<input type="text" name="pin_{uid}" inputmode="numeric" maxlength="4" '
                f'pattern="[0-9]{{4}}" placeholder="{escape(masked)}" '
                f'style="width:90px;padding:6px 10px;border:1px solid var(--border-light);'
                f'border-radius:8px;font-family:inherit;font-size:0.9em;letter-spacing:.12em;'
                f'text-align:center;" autocomplete="off">'
                f'</div>'
            )
    return f"""
<details>
  <summary style="font-weight:700;cursor:pointer;padding:6px 0;list-style:none;
    display:flex;align-items:center;gap:6px;">
    &#128274; Login PINs
    <span style="font-size:0.75em;font-weight:400;color:var(--ink-muted);margin-left:6px;">
      4-digit codes (MMDD of birthday recommended)
    </span>
  </summary>
  <div style="padding:12px 0 4px;">
    <p class="small" style="margin-bottom:14px;color:var(--ink-muted);">
      Enter a new 4-digit PIN to change it. Leave blank to keep the current PIN.
      Michael and James have no PIN — they tap their avatar to log in.
    </p>
    <form id="pin-save-form" method="POST" action="/save-pins"
          onsubmit="savePins(event)">
      {rows}
      <div style="margin-top:14px;display:flex;align-items:center;gap:12px;">
        <button class="btn-primary" type="submit">Save PINs</button>
        <span id="pin-save-status" style="font-size:0.82em;display:none;"></span>
      </div>
    </form>
  </div>
</details>
<script>
function savePins(e) {{
  e.preventDefault();
  var form = document.getElementById('pin-save-form');
  var status = document.getElementById('pin-save-status');
  var btn = form.querySelector('button[type="submit"]');
  var data = new URLSearchParams();
  form.querySelectorAll('input[name]').forEach(function(el) {{
    if (el.value.trim()) data.append(el.name, el.value.trim());
  }});
  btn.disabled = true;
  status.style.display = 'inline';
  status.style.color = 'var(--ink-faint)';
  status.textContent = 'Saving\u2026';
  fetch('/save-pins', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: data.toString()
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    btn.disabled = false;
    if (d.ok) {{
      status.style.color = '#22c55e';
      status.textContent = 'PINs saved \u2713';
      setTimeout(function() {{ status.style.display = 'none'; }}, 3000);
    }} else {{
      status.style.color = '#ef4444';
      status.textContent = d.error || 'Save failed';
    }}
  }}).catch(function() {{
    btn.disabled = false;
    status.style.color = '#ef4444';
    status.textContent = 'Connection error \u2014 try again';
  }});
}}
</script>"""


def _section_prayer_sacraments(settings: dict) -> str:
    cur_src = settings.get("daily_mass_source", "ascension_press")
    cur_url = settings.get("daily_mass_custom_url", "")
    sister_mary_ctx = bool(settings.get("sister_mary_family_context", False))

    src_opts = ""
    for key, label, _u in DAILY_MASS_SOURCES:
        sel = " selected" if key == cur_src else ""
        src_opts += f'<option value="{escape(key)}"{sel}>{escape(label)}</option>'

    custom_display = "block" if cur_src == "custom" else "none"
    checked_attr = "checked" if sister_mary_ctx else ""

    # Pope monthly intentions editor
    try:
        from data_helpers import load_pope_intentions as _lpi
        pope_data = _lpi()
    except Exception:
        pope_data = {}
    months_html = ""
    cur_year = date.today().year
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    for m_idx, mname in enumerate(month_names, start=1):
        ym = f"{cur_year}-{m_idx:02d}"
        text = escape(pope_data.get(ym, ""))
        months_html += (
            f'<div style="margin-bottom:10px;">'
            f'<label style="font-size:0.85em;color:var(--ink-muted);font-weight:600;">{mname} {cur_year}</label>'
            f'<textarea name="pope_{ym}" rows="2" '
            f'style="width:100%;font-size:0.88em;padding:6px 8px;'
            f'border:1px solid var(--border);border-radius:6px;resize:vertical;">{text}</textarea>'
            f'</div>'
        )

    # JS toggle for custom-URL field — keep '\\n' (claud rule 7)
    toggle_js = (
        "var sel=document.querySelector('select[name=daily_mass_source]');"
        "var box=document.getElementById('dm-custom-box');"
        "if(sel&&box){sel.addEventListener('change',function(){"
        "box.style.display=(sel.value==='custom')?'block':'none';});}"
    )

    return f"""
    <div class="settings-section" id="s-prayer">
        <h2>Prayer &amp; Sacraments</h2>

        <input type="hidden" name="prayer_section" value="1">

        <h3 style="margin-top:8px;">Daily Mass source</h3>
        <p class="small" style="margin:0 0 8px;">
            Where the &ldquo;Daily Mass&rdquo; link on the homepage opens.
        </p>
        <select name="daily_mass_source" style="max-width:320px;">{src_opts}</select>
        <div id="dm-custom-box" style="display:{custom_display};margin-top:10px;">
            <label>Custom Daily Mass URL</label>
            <input type="url" name="daily_mass_custom_url"
                   value="{escape(cur_url)}"
                   placeholder="https://example.com/daily-mass"
                   style="width:100%;max-width:520px;">
        </div>

        <h3 style="margin-top:24px;">Sister Mary &mdash; family context</h3>
        <label style="display:flex;align-items:center;gap:10px;cursor:pointer;font-weight:normal;">
            <input type="checkbox" name="sister_mary_family_context" value="1" {checked_attr}>
            <span>Allow Sister Mary to reference the family memory store</span>
        </label>
        <p class="small" style="margin:6px 0 0;">
            When on, Sister Mary can reference the family&rsquo;s centralized memory
            (notes about kids, schedules, prayer intentions) in her replies, and may
            silently remember new things you tell her. When off, she answers from
            your conversation alone &mdash; private and contemplative.
        </p>

        <h3 style="margin-top:24px;">Pope&rsquo;s monthly intentions ({cur_year})</h3>
        <p class="small" style="margin:0 0 12px;">
            Edit the Holy Father&rsquo;s monthly prayer intentions here. The current
            month&rsquo;s text appears on the homepage and in Sister Mary&rsquo;s context.
            Source: <a href="https://popesprayerusa.net/popes-intentions/" target="_blank" rel="noopener">popesprayerusa.net</a>.
        </p>
        {months_html}

        <script>{toggle_js}</script>
    </div>"""


def render_settings_page(status_message: str = "") -> str:
    from daily_schedule_engine import CHILDREN
    settings = load_app_settings()

    # ── Determine open section from anchor in URL (handled client-side) ───────
    # Each accordion section wraps its form content inside <details>

    # ── Build each group's accordion content ─────────────────────────────────

    # Group 1 — APP
    grp_app = f"""
<div id="group-app">
  {_section_general(settings)}
  <div style="padding:12px 0;border-top:1px solid var(--border-light);">
    {_section_children(settings, list(CHILDREN))}
  </div>
  <div style="padding:12px 0;border-top:1px solid var(--border-light);">
    {_section_daily(settings, list(CHILDREN))}
  </div>
  <div style="padding:12px 0;border-top:1px solid var(--border-light);">
    {_section_liturgy_hours(settings)}
  </div>
  <div style="padding:12px 0;border-top:1px solid var(--border-light);">
    {_section_prayer_sacraments(settings)}
  </div>
  <div style="padding:12px 0;border-top:1px solid var(--border-light);">
    {_section_pins()}
  </div>
</div>"""

    # Group 2 — AI & PLANNING
    grp_ai = f"""
<div id="group-ai">
  {_section_constraints(settings)}
  <div style="padding:12px 0;border-top:1px solid var(--border-light);">
    {_section_meals()}
  </div>
</div>"""

    # Group 3 — CYCLE
    grp_cycle = f"""
<div id="group-cycle">
  {_section_cycle(settings)}
</div>"""

    # Group 4 — HOUSEHOLD SYSTEMS (schedule grid still needs its own form for slots)
    grp_systems = f"""
<form method="POST" action="/settings-save" id="form-systems">
  <div style="padding:4px 0 16px;">
    {_section_systems(settings)}
  </div>
  <div style="padding:8px 0;border-top:1px solid var(--border-light);">
    <button type="submit" style="padding:9px 22px;font-size:0.95em;">Save Schedule Grid</button>
    <span style="font-size:0.78em;color:var(--ink-faint);margin-left:10px;">
      Auto-saves as you type &mdash; or click to save immediately
    </span>
  </div>
</form>"""

    # Group 5 — SCHOOL (settings moved to /school page)
    grp_school = """
<div style="padding:8px 0 16px;">
  <p style="font-size:0.88em;color:var(--ink-muted);margin:0 0 14px;">
    School mode settings have moved to the School page for easier access.
  </p>
  <a href="/school"
     style="display:inline-flex;align-items:center;gap:10px;
            background:#1e3566;color:white;text-decoration:none;
            padding:10px 20px;border-radius:9px;font-weight:700;font-size:0.92em;">
    &#127891; Go to School Settings
  </a>
</div>"""

    # Group 6 — INTEGRATIONS (own forms inside)
    grp_integrations = f"""
<div style="padding:4px 0 16px;">
  {_section_integrations()}
</div>"""

    # ── Accordion panels ──────────────────────────────────────────────────────
    # Each section is wrapped in a div.settings-panel-outer[data-sid] for ordering.
    panels = ""

    def _panel(sid: str, acc_html: str, content_open: bool, content_html: str) -> str:
        open_attr = "open" if content_open else ""
        return (
            f'<div class="settings-panel-outer" data-sid="{sid}">'
            f'{acc_html}'
            f'<details id="{sid}-wrap" {open_attr}'
            f' style="border:1.5px solid var(--border);border-radius:0 0 14px 14px;'
            f'margin-top:-10px;margin-bottom:10px;overflow:hidden;border-top:none;">'
            f'<div style="padding:20px;">{content_html}</div>'
            f'</details></div>'
        )

    panels += _panel(
        "s-app",
        _accordion(
            section_id="s-app",
            number="1",
            title="App & Display",
            summary="Family name, timezone, location, and color theme.",
            detail=(
                "<strong>General</strong> sets the family name shown in page headers, your timezone "
                "(which controls the Now/Next strip and schedule highlighting), and your city or zip "
                "for weather on the daily bar.<br><br>"
                "<strong>App Color Theme</strong> lets you choose how the app looks. The "
                "<em>Liturgical Seasons</em> option automatically shifts colors with the Church calendar — "
                "violet for Advent, gold for Christmas, purple for Lent, crimson for Holy Week, "
                "bright gold for Easter, and green for Ordinary Time.<br><br>"
                "<strong>Children &amp; Colors</strong> — assign each child a color used throughout "
                "the app (schedules, chores, virtue tracker, school planner).<br><br>"
                "<strong>Daily Bar</strong> — configure what each child's countdown clock tracks "
                "(birthdays, milestones), and set schedule display hours.<br><br>"
                "<strong>Liturgy of the Hours</strong> — enable the dashboard widget showing "
                "which office is due now, and toggle auto-download on Sundays so the week's "
                "prayers are ready offline."
            ),
            open_by_default=True,
            color="var(--brown)",
        ),
        content_open=True,
        content_html=grp_app,
    )

    panels += _panel(
        "s-planning",
        _accordion(
            section_id="s-planning",
            number="2",
            title="AI & Planning",
            summary="Anthropic API key, family constraints for AI scheduling, and meal planning rules.",
            detail=(
                "<strong>Anthropic API Key</strong> — required for all AI features: weekly briefings, "
                "virtue content generation, goal step planning, journal prompts, and the 5AM Club AI. "
                "Get a free key at <a href='https://console.anthropic.com' target='_blank' "
                "style='color:var(--brown);'>console.anthropic.com</a> → API Keys. "
                "The app uses Claude Haiku for most features (very low cost, typically &lt;$1/month "
                "for daily use).<br><br>"
                "<strong>Family Constraints</strong> — fill these in once. Every time you use the AI "
                "scheduling assistant, it reads these fields to make practical suggestions: who can "
                "supervise, how long each child works independently, which subjects need Mom, "
                "meal prep times, and co-op schedules.<br><br>"
                "<strong>Meal Planning Rules</strong> — standing rules the meal planner respects: "
                "dietary restrictions, rotation preferences, prep constraints. The AI reads these "
                "when suggesting weekly menus. See also: "
                "<a href='/meals' style='color:var(--brown);'>Meal Planner</a> · "
                "<a href='/recipes' style='color:var(--brown);'>Recipe Library</a>."
            ),
            color="#2980b9",
        ),
        content_open=False,
        content_html=grp_ai,
    )

    panels += _panel(
        "s-cycle",
        _accordion(
            section_id="s-cycle",
            number="3",
            title="Cycle Tracking",
            summary="Moved to Lauren\u2019s profile page.",
            detail="Cycle tracking now lives on your personal profile page for easier access.",
            color="#8e44ad",
        ),
        content_open=False,
        content_html='<div style="padding:16px;"><p style="color:#888;font-size:0.9em;">Cycle tracking has moved to your profile page.</p><a href="/mom-profile" style="display:inline-block;margin-top:8px;padding:8px 18px;background:#8e44ad;color:white;border-radius:8px;text-decoration:none;font-size:0.9em;font-weight:600;">Go to Lauren\u2019s Profile \u2192</a></div>',
    )

    panels += _panel(
        "s-household",
        _accordion(
            section_id="s-household",
            number="4",
            title="Household Systems",
            summary="Laundry rotation, van cleaning schedule, and a shortcut to the Family Rule of Life.",
            detail=(
                "<strong>Laundry System</strong> — a locked weekly rotation assigns each day's laundry "
                "to a specific person. This section is read-only reference; the rotation is built into "
                "the app. See the chores page for daily assignments.<br><br>"
                "<strong>Van Cleaning Rotation</strong> — a 3-week rotation with Role A (vacuum) and "
                "Role B (wipe-down). Set the epoch date once and the app tracks which week you're in. "
                "Current week and roles are shown live.<br><br>"
                "<strong>Family Rule of Life</strong> — the family's standing weekly rhythm now lives "
                "in one place: the Family day grid on the Mom dashboard. This section is just a "
                "shortcut so you can jump there from Settings.<br><br>"
                "See also: <a href='/chores' style='color:var(--brown);'>Chores</a> · "
                "<a href='/tasks' style='color:var(--brown);'>Tasks</a>"
            ),
            color="#27ae60",
        ),
        content_open=False,
        content_html=grp_systems,
    )

    panels += _panel(
        "s-school",
        _accordion(
            section_id="s-school",
            number="5",
            title="School",
            summary="School mode: normal week, light week, or pause specific subjects.",
            detail=(
                "<strong>School mode</strong> — controls which subjects appear in the boys' "
                "daily task lists. Switch to <strong>Light week</strong> when you're sick, "
                "traveling, or just need a lighter day — only your listed core subjects will "
                "show. Use <strong>Custom pause</strong> to hide specific subjects indefinitely "
                "(e.g. while waiting on curriculum). Switch back to Normal anytime; a banner "
                "on the dashboard lets you tap once to restore the full schedule."
            ),
            color="#c0392b",
        ),
        content_open=False,
        content_html=grp_school,
    )

    panels += _panel(
        "s-integrations",
        _accordion(
            section_id="s-integrations",
            number="6",
            title="Integrations",
            summary="iCloud Calendar connection and .ics feed subscriptions.",
            detail=(
                "<strong>iCloud Calendar</strong> — connect with your Apple ID and an app-specific "
                "password (not your regular Apple password). This pulls your iCloud calendar events "
                "into the app's dashboard, weekly planner, and Plan My Day calendar step.<br><br>"
                "To generate an app-specific password: go to "
                "<a href='https://appleid.apple.com' target='_blank' style='color:var(--brown);'>"
                "appleid.apple.com</a> → Sign-In &amp; Security → App-Specific Passwords → "
                "Generate. Label it 'Sancta Familia' for easy reference.<br><br>"
                "<strong>Subscribed Calendars (.ics)</strong> — paste any public .ics URL: school "
                "calendars, parish events, sports leagues, Proton Calendar, or Google Calendar "
                "(share link → copy ICS URL). No login required. Events appear in the same "
                "calendar views as iCloud events, color-coded by calendar.<br><br>"
                "Compatible sources: Apple Calendar · Google Calendar · Proton Calendar · "
                "school/parish websites that publish .ics feeds."
            ),
            color="#e67e22",
        ),
        content_open=False,
        content_html=grp_integrations,
    )

    # ── Quick links bar ───────────────────────────────────────────────────────
    quick_links = """
<div style="display:flex;gap:8px;flex-wrap:wrap;padding:8px 0 16px;">
  <a href="/plan-quarter" style="padding:7px 14px;background:var(--ink);color:var(--gold-light);
     border-radius:8px;text-decoration:none;font-size:0.82em;font-weight:600;">&#128197; Quarterly Goals</a>
  <a href="/virtues" style="padding:7px 14px;background:var(--ink);color:var(--gold-light);
     border-radius:8px;text-decoration:none;font-size:0.82em;font-weight:600;">&#10013; Virtue Tracker</a>
  <a href="/5am" style="padding:7px 14px;background:var(--ink);color:var(--gold-light);
     border-radius:8px;text-decoration:none;font-size:0.82em;font-weight:600;">&#9728; 5AM Club</a>
  <a href="/kids-week" style="padding:7px 14px;background:var(--ink);color:var(--gold-light);
     border-radius:8px;text-decoration:none;font-size:0.82em;font-weight:600;">&#128203; Kids Week</a>
  <a href="/tasks" style="padding:7px 14px;background:var(--parchment);color:var(--ink);
     border:1.5px solid var(--border);border-radius:8px;text-decoration:none;font-size:0.82em;">Tasks</a>
  <a href="/chores" style="padding:7px 14px;background:var(--parchment);color:var(--ink);
     border:1.5px solid var(--border);border-radius:8px;text-decoration:none;font-size:0.82em;">Chores</a>
  <a href="/recipes" style="padding:7px 14px;background:var(--parchment);color:var(--ink);
     border:1.5px solid var(--border);border-radius:8px;text-decoration:none;font-size:0.82em;">Recipes</a>
</div>"""

    js = """
<script>
// (Rule-of-Life per-cell save helpers were removed — the FROL editor now
//  lives only on /mom#grid, which has its own save wiring.)

// ── Autosave system ────────────────────────────────────────────────────────
var _saveTimer      = null;
var _userHasTouched = false;

function settingsChanged() {
  _userHasTouched = true;
  clearTimeout(_saveTimer);
  _showSaveIndicator('saving');
  _saveTimer = setTimeout(autoSaveSettings, 800);
}

function _showSaveIndicator(state) {
  var el = document.getElementById('save-indicator');
  if (!el) return;
  if (state === 'saving') {
    el.textContent = 'Saving\u2026';
    el.style.color = 'var(--ink-faint)';
    el.style.display = 'block';
  } else if (state === 'saved') {
    el.textContent = 'Saved \u2713';
    el.style.color = '#22c55e';
    el.style.display = 'block';
    setTimeout(function() { el.style.display = 'none'; }, 2500);
  } else if (state === 'error') {
    el.textContent = 'Save failed \u2014 check connection';
    el.style.color = '#ef4444';
    el.style.display = 'block';
  }
}

function autoSaveSettings() {
  if (!_userHasTouched) return;
  var formData = new URLSearchParams();
  document.querySelectorAll('input[name], select[name], textarea[name]').forEach(function(el) {
    /* #form-systems (schedule grid) is now included in autosave */
    if (el.closest('form[action="/calendar-save-config"]')) return;
    if (el.closest('form[action="/subscribed-cal-add"]')) return;
    if (el.closest('form[action="/subscribed-cal-delete"]')) return;
    if (el.closest('form[action="/meal-rule-add"]')) return;
    if (el.closest('form[action="/meal-rule-delete"]')) return;
    if (el.closest('form[action="/save-pins"]')) return;
    if (el.type === 'checkbox') {
      if (el.checked) formData.append(el.name, el.value || 'on');
    } else if (el.type === 'radio') {
      if (el.checked) formData.append(el.name, el.value);
    } else if (el.type === 'password') {
      // Include password field if it has a value — protects saved keys while allowing updates
      if (el.value) formData.append(el.name, el.value);
    } else {
      formData.append(el.name, el.value);
    }
  });

  fetch('/settings-save-ajax', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: formData.toString()
  }).then(function(r) { return r.json(); }).then(function(d) {
    _showSaveIndicator(d.ok ? 'saved' : 'error');
  }).catch(function() {
    _showSaveIndicator('error');
  });
}

function _wireAutosave() {
  document.querySelectorAll('input[name], select[name], textarea[name]').forEach(function(el) {
    /* #form-systems (schedule grid) is now included — autosave covers all fields */
    if (el.closest('form[action="/calendar-save-config"]')) return;
    if (el.closest('form[action="/subscribed-cal-add"]')) return;
    if (el.closest('form[action="/subscribed-cal-delete"]')) return;
    if (el.closest('form[action="/meal-rule-add"]')) return;
    if (el.closest('form[action="/meal-rule-delete"]')) return;
    if (el.closest('form[action="/save-pins"]')) return;
    if (el.type === 'password') {
      // Password fields save when changed like any other field
    }
    el.addEventListener('change', settingsChanged);
    if (el.tagName === 'TEXTAREA' || el.type === 'text' || el.type === 'number' || el.type === 'date') {
      el.addEventListener('input', function() {
        _userHasTouched = true;
        clearTimeout(_saveTimer);
        _showSaveIndicator('saving');
        _saveTimer = setTimeout(autoSaveSettings, 1200);
      });
    }
  });
}

function selectTheme(theme) {
  document.querySelectorAll('input[name="color_theme"]').forEach(function(r) {
    r.checked = (r.value === theme);
  });
  _userHasTouched = true;
  autoSaveSettings();
}

document.addEventListener('DOMContentLoaded', _wireAutosave);

// Accordion functions
function toggleAccordion(id) {
  var chevron = document.getElementById('chevron-' + id);
  var wrap    = document.getElementById(id + '-wrap');
  if (chevron) {
    chevron.style.transform = (wrap && wrap.open) ? '' : 'rotate(180deg)';
  }
}

function toggleDetail(id) {
  var el = document.getElementById(id);
  if (!el) return;
  el.style.display = (el.style.display === 'none' || el.style.display === '') ? 'block' : 'none';
}

// Open the right section if anchor is in URL
(function() {
  var hash = window.location.hash;
  var map  = {
    '#s-general':      's-app',
    '#s-children':     's-app',
    '#s-daily':        's-app',
    '#s-constraints':  's-planning',
    '#s-meals':        's-planning',
    '#s-cycle':        's-cycle',
    '#s-systems':      's-household',
    '#s-school':       's-school',
    '#s-integrations': 's-integrations',
  };
  var target = map[hash];
  if (target) {
    var wrap = document.getElementById(target + '-wrap');
    if (wrap) wrap.open = true;
    setTimeout(function() {
      var el = document.getElementById(target + '-wrap');
      if (el) el.scrollIntoView({behavior:'smooth', block:'start'});
    }, 100);
  }
})();

// Sync chevrons on page load
document.querySelectorAll('details[id$="-wrap"]').forEach(function(d) {
  var id = d.id.replace('-wrap','');
  var chevron = document.getElementById('chevron-' + id);
  if (chevron && d.open) chevron.style.transform = 'rotate(180deg)';
});

// ── Quick-jump nav ────────────────────────────────────────────────────────────
function jumpSection(sid) {
  var panel = document.querySelector('.settings-panel-outer[data-sid="' + sid + '"]');
  if (!panel) return;
  var wraps = panel.querySelectorAll('details');
  wraps.forEach(function(d) { d.open = true; });
  setTimeout(function() {
    panel.scrollIntoView({behavior: 'smooth', block: 'start'});
  }, 80);
}

// ── Section ordering (up/down arrows, saved to localStorage) ─────────────────
var SETTINGS_ORDER_KEY = 'sf-settings-order';
var DEFAULT_ORDER = ['s-app','s-planning','s-cycle','s-household','s-school','s-integrations'];

function _getOrder() {
  try {
    var stored = JSON.parse(localStorage.getItem(SETTINGS_ORDER_KEY) || 'null');
    if (Array.isArray(stored) && stored.length === DEFAULT_ORDER.length) return stored;
  } catch(e) {}
  return DEFAULT_ORDER.slice();
}

function _applyOrder(order) {
  var container = document.getElementById('settings-panels');
  if (!container) return;
  order.forEach(function(sid) {
    var el = container.querySelector('.settings-panel-outer[data-sid="' + sid + '"]');
    if (el) container.appendChild(el);
  });
}

function _moveSection(sid, dir) {
  var order = _getOrder();
  var idx   = order.indexOf(sid);
  if (idx < 0) return;
  var newIdx = idx + dir;
  if (newIdx < 0 || newIdx >= order.length) return;
  var tmp = order[idx]; order[idx] = order[newIdx]; order[newIdx] = tmp;
  localStorage.setItem(SETTINGS_ORDER_KEY, JSON.stringify(order));
  _applyOrder(order);
  _injectOrderButtons();
}

function _injectOrderButtons() {
  var order = _getOrder();
  document.querySelectorAll('.settings-panel-outer').forEach(function(panel) {
    var sid = panel.getAttribute('data-sid');
    var existing = panel.querySelector('.section-order-btns');
    if (existing) existing.remove();
    var idx = order.indexOf(sid);
    var len = order.length;
    var upBtn = idx > 0
      ? '<button onclick="_moveSection(\\'' + sid + '\\',-1)" title="Move up"'
        + ' style="background:none;border:none;cursor:pointer;font-size:.82em;'
        + 'color:var(--brown);padding:0 4px;">&#9650;</button>'
      : '<span style="display:inline-block;width:22px;"></span>';
    var dnBtn = idx < len - 1
      ? '<button onclick="_moveSection(\\'' + sid + '\\',1)" title="Move down"'
        + ' style="background:none;border:none;cursor:pointer;font-size:.82em;'
        + 'color:var(--brown);padding:0 4px;">&#9660;</button>'
      : '<span style="display:inline-block;width:22px;"></span>';
    var btns = document.createElement('div');
    btns.className = 'section-order-btns';
    btns.style.cssText = 'display:inline-flex;align-items:center;gap:2px;margin-left:6px;';
    btns.innerHTML = upBtn + dnBtn;
    var summaryDiv = panel.querySelector('summary > div:first-of-type');
    if (summaryDiv) summaryDiv.appendChild(btns);
  });
}

document.addEventListener('DOMContentLoaded', function() {
  _applyOrder(_getOrder());
  _injectOrderButtons();
});
</script>"""

    # ── Color picker JS (needed by _section_general) ──────────────────────────
    color_js = """
<script>
function updatePreview(ce) {
    var bg    = document.getElementById('bg_'    + ce).value;
    var light = document.getElementById('light_' + ce).value;
    var prev  = document.getElementById('preview_' + ce);
    if (prev) {
        prev.style.background  = light;
        prev.style.borderColor = bg;
        prev.querySelector('span').style.color = bg;
    }
    document.getElementById('bghex_'    + ce).value = bg;
    document.getElementById('lighthex_' + ce).value = light;
}
function syncHex(ce, which) {
    var hex = document.getElementById(which + 'hex_' + ce).value;
    if (/^#[0-9a-fA-F]{6}$/.test(hex)) {
        document.getElementById(which + '_' + ce).value = hex;
        updatePreview(ce);
    }
}
function applyPreset(ce, bg, light) {
    document.getElementById('bg_'       + ce).value = bg;
    document.getElementById('bghex_'    + ce).value = bg;
    document.getElementById('light_'    + ce).value = light;
    document.getElementById('lighthex_' + ce).value = light;
    updatePreview(ce);
}
</script>"""

    body = f"""
<div id="top"></div>
{page_header("Settings")}
{render_status_message(status_message)}
{color_js}

<!-- Autosave indicator -->
<div id="save-indicator"
     style="display:none;position:fixed;top:14px;right:16px;z-index:999;
            font-size:0.82em;font-weight:700;padding:6px 14px;
            background:white;border-radius:20px;
            box-shadow:0 2px 8px rgba(0,0,0,0.12);
            border:1.5px solid var(--border);">
</div>

<!-- Page summary -->
<div style="padding:14px 18px;background:var(--gold-light);border-radius:12px;
            margin-bottom:20px;border:1px solid var(--gold-mid);">
  <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.1rem;
              font-weight:600;color:var(--ink);margin-bottom:4px;">
    Configure Sancta Familia
  </div>
  <div style="font-size:0.82em;color:var(--ink-muted);line-height:1.6;">
    Click any section to expand it. Changes save automatically as you type &mdash;
    look for the <strong>Saved ✓</strong> indicator in the top right corner.
    Click <em>How this works</em> for a full explanation of each feature.
  </div>
</div>

<!-- Quick-jump nav -->
<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;
            display:flex;gap:6px;padding:0 0 12px;margin-bottom:4px;
            scrollbar-width:none;">
  <a href="#" onclick="jumpSection('s-app');return false;"
     style="flex-shrink:0;padding:5px 12px;background:var(--parchment);
            border:1.5px solid var(--border);border-radius:20px;font-size:.75em;
            font-weight:700;text-decoration:none;color:var(--ink);">⚙ App</a>
  <a href="#" onclick="jumpSection('s-planning');return false;"
     style="flex-shrink:0;padding:5px 12px;background:#eaf4fb;
            border:1.5px solid #2980b9;border-radius:20px;font-size:.75em;
            font-weight:700;text-decoration:none;color:#2980b9;">🤖 AI</a>
  <a href="#" onclick="jumpSection('s-cycle');return false;"
     style="flex-shrink:0;padding:5px 12px;background:#f5eefa;
            border:1.5px solid #8e44ad;border-radius:20px;font-size:.75em;
            font-weight:700;text-decoration:none;color:#8e44ad;">🌙 Cycle</a>
  <a href="#" onclick="jumpSection('s-household');return false;"
     style="flex-shrink:0;padding:5px 12px;background:#edfaf3;
            border:1.5px solid #27ae60;border-radius:20px;font-size:.75em;
            font-weight:700;text-decoration:none;color:#27ae60;">🏠 Household</a>
  <a href="#" onclick="jumpSection('s-school');return false;"
     style="flex-shrink:0;padding:5px 12px;background:#fdf0ef;
            border:1.5px solid #c0392b;border-radius:20px;font-size:.75em;
            font-weight:700;text-decoration:none;color:#c0392b;">📚 School</a>
  <a href="#" onclick="jumpSection('s-integrations');return false;"
     style="flex-shrink:0;padding:5px 12px;background:#fef6ed;
            border:1.5px solid #e67e22;border-radius:20px;font-size:.75em;
            font-weight:700;text-decoration:none;color:#e67e22;">📅 Calendars</a>
</div>

{quick_links}
<div id="settings-panels">
{panels}
</div>
{js}
"""
    return html_page("Settings", body)


# ── Liturgy of the Hours settings section ────────────────────────────────────
def _section_liturgy_hours(settings: dict) -> str:
    show_widget  = settings.get("show_liturgy_hours_widget", True)
    show_checked = "checked" if show_widget else ""

    return f"""
<div class="settings-section" id="s-liturgy-hours">
  <input type="hidden" name="liturgy_section" value="1">
  <h2 style="margin-bottom:4px;">Liturgy of the Hours</h2>
  <p class="small" style="margin-bottom:16px;">
    Displays the full
    <a href="https://divineoffice.org" target="_blank">Divine Office</a>
    directly &mdash; the same translation used in the Divine Office app.
    Requires an internet connection. Completion tracking (mark as prayed)
    is saved locally.
  </p>

  <div style="display:flex;flex-direction:column;gap:12px;">

    <label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;">
      <input type="checkbox" name="show_liturgy_hours_widget" {show_checked}
             style="width:18px;height:18px;margin-top:2px;flex-shrink:0;">
      <div>
        <div style="font-size:0.88em;font-weight:600;">Show on dashboard</div>
        <div class="small">Displays a widget on the home page showing which office
        is due now with one-tap access and a daily completion tracker.</div>
      </div>
    </label>

  </div>

  <div style="margin-top:16px;">
    <a href="/liturgy-hours" onclick="event.stopPropagation()"
       style="padding:7px 14px;background:var(--ink);color:var(--gold-light);
              border-radius:8px;text-decoration:none;font-size:0.82em;font-weight:600;">
      Open Hours page &rarr;
    </a>
  </div>
</div>"""


# ── Cycle tracking settings section ──────────────────────────────────────────
def _section_cycle(settings: dict = None, return_url: str = "/settings#s-cycle") -> str:
    """Cycle tracking settings — Day 1 log, cycle length history, predictions."""
    if settings is None:
        settings = load_app_settings()
    show_detail = settings.get("cycle_show_detail_fields", True)
    _checked = "checked" if show_detail else ""
    import json as _json, os as _os
    from html import escape as _e
    from datetime import date as _date, timedelta as _td

    CYCLE_LOG = "data/cycle_log.json"
    try:
        with open(CYCLE_LOG) as f:
            log = _json.load(f)
    except Exception:
        log = []

    # Compute cycle lengths between consecutive Day 1 dates
    def _cycle_lengths(entries):
        sorted_dates = sorted([e["day1"] for e in entries if e.get("day1")])
        lengths = []
        for i in range(1, len(sorted_dates)):
            try:
                d1 = _date.fromisoformat(sorted_dates[i-1])
                d2 = _date.fromisoformat(sorted_dates[i])
                lengths.append((sorted_dates[i-1], sorted_dates[i], (d2-d1).days))
            except Exception:
                pass
        return lengths

    lengths = _cycle_lengths(log)
    avg_len = round(sum(l[2] for l in lengths) / len(lengths)) if lengths else 28

    # Prediction from last Day 1
    prediction_html = ""
    if log:
        last_day1_str = sorted([e["day1"] for e in log if e.get("day1")])[-1]
        try:
            last_day1 = _date.fromisoformat(last_day1_str)
            next_day1 = last_day1 + _td(days=avg_len)
            today     = _date.today()
            days_since = (today - last_day1).days
            current_cd = days_since + 1
            # Phase prediction
            if current_cd <= 5:
                pred_phase = "Menstrual"
            elif current_cd <= 12:
                pred_phase = "Follicular"
            elif current_cd <= 16:
                pred_phase = "Ovulatory"
            elif current_cd <= 21:
                pred_phase = "Early Luteal"
            else:
                pred_phase = "Late Luteal"

            # Fertility window (approx ovulation = day 14 of cycle)
            ovulation_date = last_day1 + _td(days=13)
            fertile_start  = ovulation_date - _td(days=5)
            fertile_end    = ovulation_date + _td(days=1)

            # Pre-compute date labels to avoid strftime-with-quotes in f-string
            _pred_next_day1     = next_day1.strftime('%b %d, %Y')
            _pred_fertile_start = fertile_start.strftime('%b %d')
            _pred_fertile_end   = fertile_end.strftime('%b %d')
            _pred_ovulation     = ovulation_date.strftime('%b %d')

            prediction_html = f"""
<div style="background:#f5f0fa;border:1.5px solid #8e44ad30;border-radius:12px;
            padding:16px;margin-bottom:20px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:#8e44ad;margin-bottom:12px;">Current Cycle Prediction</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
    <div>
      <div style="font-size:0.75em;color:#888;margin-bottom:2px;">Last Day 1</div>
      <div style="font-weight:700;font-size:0.9em;">{_e(last_day1_str)}</div>
    </div>
    <div>
      <div style="font-size:0.75em;color:#888;margin-bottom:2px;">Current cycle day</div>
      <div style="font-weight:700;font-size:0.9em;">Day {current_cd}</div>
    </div>
    <div>
      <div style="font-size:0.75em;color:#888;margin-bottom:2px;">Predicted phase</div>
      <div style="font-weight:700;font-size:0.9em;color:#8e44ad;">{_e(pred_phase)}</div>
    </div>
    <div>
      <div style="font-size:0.75em;color:#888;margin-bottom:2px;">Next Day 1 (est.)</div>
      <div style="font-weight:700;font-size:0.9em;">{_pred_next_day1}</div>
    </div>
    <div style="grid-column:1/-1;">
      <div style="font-size:0.75em;color:#888;margin-bottom:2px;">Fertile window (est.)</div>
      <div style="font-weight:700;font-size:0.9em;color:#27ae60;">
        {_pred_fertile_start} – {_pred_fertile_end}
        <span style="font-weight:400;font-size:0.85em;color:#888;">
          (ovulation est. {_pred_ovulation})
        </span>
      </div>
    </div>
    <div style="grid-column:1/-1;">
      <div style="font-size:0.75em;color:#888;margin-bottom:2px;">Average cycle length</div>
      <div style="font-weight:700;font-size:0.9em;">{avg_len} days
        <span style="font-weight:400;color:#888;font-size:0.85em;">
          (based on {len(lengths)} recorded cycles)
        </span>
      </div>
    </div>
  </div>
</div>"""
        except Exception:
            prediction_html = ""

    # Log entries table
    # Pre-compute all conditional strings to avoid f-string expression issues
    plural_s      = "s" if len(lengths) != 1 else ""
    cycles_label  = f"(based on {len(lengths)} recorded cycle{plural_s})"
    empty_dash    = "—"  # em dash for empty cell

    log_rows = ""
    for entry in sorted(log, key=lambda e: e.get("day1",""), reverse=True)[:12]:
        d1   = _e(entry.get("day1",""))
        note = _e(entry.get("note",""))
        cl_str = ""
        for prev, curr, cl in lengths:
            if curr == entry.get("day1"):
                cl_str = f"{cl} days"
                break
        _ret = return_url
        log_rows += (
            f'<tr>'
            f'<td style="padding:6px 10px;font-size:0.85em;">{d1}</td>'
            f'<td style="padding:6px 10px;font-size:0.85em;">{cl_str or empty_dash}</td>'
            f'<td style="padding:6px 10px;font-size:0.82em;color:#888;">{note}</td>'
            f'<td style="padding:6px 10px;">'
            f'<form method="POST" action="/cycle-log-delete" style="display:inline;">'
            f'<input type="hidden" name="day1" value="{d1}">'
            f'<input type="hidden" name="_return" value="{_ret}">'
            f'<button type="submit" style="font-size:0.75em;color:#c0392b;background:none;'
            f'border:none;cursor:pointer;padding:2px 6px;" '
            f'onclick="return confirm(\'Delete this entry?\')">&#10005;</button>'
            f'</form></td>'
            f'</tr>'
        )

    if not log:
        history_html = '<p class="muted">No cycles logged yet. Add your first Day 1 above.</p>'
    else:
        history_html = (
            '<div style="overflow-x:auto;">'
            '<table style="width:100%;border-collapse:collapse;">'
            '<thead><tr style="background:#f5f0f8;">'
            '<th style="padding:8px 10px;text-align:left;font-size:0.78em;color:#888;font-weight:700;">Day 1</th>'
            '<th style="padding:8px 10px;text-align:left;font-size:0.78em;color:#888;font-weight:700;">Cycle length</th>'
            '<th style="padding:8px 10px;text-align:left;font-size:0.78em;color:#888;font-weight:700;">Note</th>'
            '<th style="padding:8px 10px;"></th>'
            '</tr></thead>'
            f'<tbody style="border:1px solid #f0e8f8;">{log_rows}</tbody>'
            '</table></div>'
        )

    today_val     = _date.today().isoformat()
    log_count     = len(log)
    lengths_count = len(lengths)

    return f"""
    <div class="settings-section" id="s-cycle">
        <h2>Cycle Tracking <span class="small" style="font-weight:400;">— private \u00b7 only visible to you</span></h2>
        <p class="small" style="margin-bottom:16px;">
            Log the first day of each cycle. The app uses this to predict your current phase,
            next cycle start, and fertile window — and to automatically pre-fill the cycle
            check-in in Plan My Day.
        </p>

        <h3>Display Options</h3>
        <form method="POST" action="/settings-save" style="margin-bottom:20px;padding:14px;
              background:var(--parchment);border-radius:10px;border:1px solid var(--border);">
            <input type="hidden" name="cycle_fields_section" value="1">
            <input type="hidden" name="_return" value="{return_url}">
            <label style="display:flex;align-items:center;gap:10px;cursor:pointer;">
                <input type="checkbox" name="cycle_show_detail_fields"
                       {_checked}
                       style="width:18px;height:18px;accent-color:#8e44ad;flex-shrink:0;">
                <div>
                    <div style="font-size:0.9em;font-weight:600;">Show daily detail fields</div>
                    <div style="font-size:0.78em;color:var(--ink-faint);">
                        Energy, mood, sleep, symptoms, cravings, stress.
                        Turn off for a minimal daily check-in.
                    </div>
                </div>
            </label>
            <button type="submit" style="margin-top:12px;padding:7px 18px;font-size:0.85em;
                    background:var(--ink);color:var(--gold-light);border:none;border-radius:8px;
                    font-family:inherit;cursor:pointer;">Save</button>
        </form>

        {prediction_html}

        <h3>Log a Day 1</h3>
        <form method="POST" action="/cycle-log-add" style="margin-bottom:24px;">
            <input type="hidden" name="_return" value="{return_url}">
            <div style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;">
                <div>
                    <label>Day 1 date</label>
                    <input type="date" name="day1" required
                           value="{today_val}"
                           style="margin-bottom:0;">
                </div>
                <div>
                    <label>Note (optional)</label>
                    <input type="text" name="note"
                           placeholder="e.g. heavy flow, late start"
                           style="margin-bottom:0;min-width:220px;">
                </div>
                <button type="submit" style="padding:9px 20px;margin-bottom:1px;">Save Day 1</button>
            </div>
        </form>

        <h3>Cycle history
          <span style="font-weight:400;font-size:0.85em;color:#888;">
            — {log_count} entries · avg {avg_len} days
          </span>
        </h3>
        {history_html}

        <div style="margin-top:16px;padding:12px 14px;background:#fdf8ff;border-radius:10px;
                    font-size:0.82em;color:#888;border:1px solid #f0e8f8;">
            🔒 This data is stored only on your device and is never visible to anyone else.
        </div>
    </div>"""


# ── Meal planning settings section ───────────────────────────────────────────
def _section_meals() -> str:
    """Meal planning rules, preferences, and quick links."""
    import json as _json, os as _os
    from html import escape as _e

    RULES_FILE = "data/meal_rules.json"
    try:
        with open(RULES_FILE) as f:
            rules = _json.load(f)
    except Exception:
        rules = []

    # Render existing rules
    rules_rows = ""
    for i, rule in enumerate(rules):
        rule_text = _e(str(rule.get("rule","")) if isinstance(rule, dict) else str(rule))
        rule_id   = i
        rules_rows += (
            f'<div style="display:flex;align-items:flex-start;gap:10px;padding:8px 0;'
            f'border-bottom:1px solid var(--border-light);" id="meal-rule-{rule_id}">'
            f'<div style="flex:1;font-size:0.88em;color:var(--ink);">{rule_text}</div>'
            f'<form method="POST" action="/meal-rule-delete" style="display:inline;flex-shrink:0;">'
            f'<input type="hidden" name="rule_index" value="{rule_id}">'
            f'<button type="submit" style="font-size:0.75em;color:#c0392b;background:none;'
            f'border:none;cursor:pointer;padding:2px 6px;" '
            f'onclick="return confirm(\'Remove this rule?\')">&#10005;</button>'
            f'</form>'
            f'</div>'
        )

    empty_rules = '<p class="muted">No meal rules yet. Add rules below.</p>' if not rules else ""

    return f"""
    <div class="settings-section" id="s-meals">
        <h2>Meal Planning</h2>
        <p class="small" style="margin-bottom:20px;">
            Rules guide how meals are planned for the week. Add family preferences,
            dietary needs, penance day rules, and anything the AI should know when
            generating your meal plan.
        </p>

        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;">
            <a href="/meals" style="padding:9px 18px;background:var(--ink);color:var(--gold-light);
               border-radius:10px;font-size:0.85em;font-weight:700;text-decoration:none;">
               Open Meal Planner &rarr;
            </a>
            <a href="/recipes" style="padding:9px 18px;background:var(--parchment);color:var(--ink);
               border:1.5px solid var(--border);border-radius:10px;font-size:0.85em;
               font-weight:600;text-decoration:none;">
               Recipe Library &rarr;
            </a>
            <a href="/meal-print" style="padding:9px 18px;background:var(--parchment);color:var(--ink);
               border:1.5px solid var(--border);border-radius:10px;font-size:0.85em;
               font-weight:600;text-decoration:none;">
               Print Meal Card &rarr;
            </a>
        </div>

        <h3>Meal Rules
            <span style="font-weight:400;font-size:0.85em;color:#888;">
                &mdash; {len(rules)} rules
            </span>
        </h3>
        <p class="small" style="margin-bottom:12px;">
            Examples: "No meat on Fridays during Lent", "JP is allergic to tree nuts",
            "One new recipe per week", "Simple meals on heavy school days",
            "Dad likes a hot lunch Tuesday and Thursday".
        </p>

        <div style="margin-bottom:16px;">{empty_rules}{rules_rows}</div>

        <h3>Add a Rule</h3>
        <form method="POST" action="/meal-rule-add" style="margin-bottom:16px;">
            <div style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;">
                <div style="flex:1;min-width:240px;">
                    <label>Rule</label>
                    <input type="text" name="rule" required
                           placeholder="e.g. No meat on Fridays during Lent"
                           style="margin-bottom:0;">
                </div>
                <button type="submit" style="padding:9px 20px;margin-bottom:1px;">Add Rule</button>
            </div>
        </form>

        <h3>Capacity Labels</h3>
        <p class="small" style="margin-bottom:12px;">
            These labels appear in the meal planner when a day has a specific
            capacity level set. The AI uses them to suggest simpler or more
            elaborate meals accordingly.
        </p>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">
            <div style="padding:10px 12px;background:#fdf0ef;border-radius:10px;
                        border-left:3px solid #c0392b;">
                <div style="font-size:0.72em;font-weight:700;color:#c0392b;
                            text-transform:uppercase;letter-spacing:.08em;">Low capacity</div>
                <div style="font-size:0.82em;color:var(--ink);margin-top:4px;">
                    Slow cooker, leftovers, simple assembly meals
                </div>
            </div>
            <div style="padding:10px 12px;background:#fef6ed;border-radius:10px;
                        border-left:3px solid #e67e22;">
                <div style="font-size:0.72em;font-weight:700;color:#e67e22;
                            text-transform:uppercase;letter-spacing:.08em;">Medium capacity</div>
                <div style="font-size:0.82em;color:var(--ink);margin-top:4px;">
                    Standard 30-45 min cook time, familiar recipes
                </div>
            </div>
            <div style="padding:10px 12px;background:#edfaf3;border-radius:10px;
                        border-left:3px solid #27ae60;">
                <div style="font-size:0.72em;font-weight:700;color:#27ae60;
                            text-transform:uppercase;letter-spacing:.08em;">High capacity</div>
                <div style="font-size:0.82em;color:var(--ink);margin-top:4px;">
                    New recipes, batch cooking, elaborate meals
                </div>
            </div>
        </div>
    </div>"""