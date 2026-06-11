"""
render_meal_wizard.py — Meal Planning Wizard pages.

Phase C, Part 1: the Pantry Staples page only. More wizard steps are added
in later phases. All data access goes through data_helpers (Rule 19); all
file chrome comes from ui_helpers.html_page (matches render_wizards.py).
"""
import re
from datetime import date, timedelta
from html import escape
from ui_helpers import html_page
from data_helpers import load_pantry_staples, get_merged_calendar_events
from render_liturgical import get_day_info
from render_meals import load_meal_rules

# Pulled out of f-strings to avoid nested quotes (Rule 2) / backslashes (Rule 1).
_HEADING_FONT = "'Cormorant Garamond', serif"

# Canonical staple groups, displayed top to bottom exactly as listed.
_GROUPS = [
    ("Oils and fats", ["olive oil", "vegetable oil", "butter", "coconut oil"]),
    ("Seasonings", ["salt", "pepper", "garlic powder", "onion powder", "paprika",
                    "cumin", "oregano", "basil", "bay leaves", "red pepper flakes",
                    "cinnamon"]),
    ("Baking", ["flour", "sugar", "brown sugar", "baking powder", "baking soda",
                "vanilla extract", "cornstarch"]),
    ("Grains and pasta", ["rice", "pasta", "oats", "breadcrumbs"]),
    ("Canned and jarred", ["canned tomatoes", "tomato paste", "chicken broth",
                           "beef broth", "soy sauce", "Worcestershire sauce",
                           "vinegar", "honey"]),
    ("Produce staples", ["onions", "garlic", "lemons"]),
    ("Dairy", ["eggs"]),
]

# JS kept in a plain (non-f) string so its braces are literal and no
# backslash-n is ever needed (Rules 7 & 12). Custom items become chips with
# a hidden input so they submit with the form.
_PAGE_JS = (
    "<script>"
    "function addCustomStaple(){"
    "  var inp = document.getElementById('custom-staple-input');"
    "  var val = (inp.value || '').trim();"
    "  if(!val){ return; }"
    "  var wrap = document.getElementById('custom-chips');"
    "  var chip = document.createElement('span');"
    "  chip.style.cssText = 'display:inline-flex;align-items:center;gap:6px;"
    "background:var(--gold-light,#f3ead2);color:var(--ink);border-radius:999px;"
    "padding:5px 12px;margin:0 6px 6px 0;font-size:0.9em;';"
    "  var hid = document.createElement('input');"
    "  hid.type='hidden'; hid.name='custom_item'; hid.value=val;"
    "  var txt = document.createElement('span'); txt.textContent = val;"
    "  var x = document.createElement('span');"
    "  x.textContent = '\\u00d7'; x.style.cssText='cursor:pointer;font-weight:700;';"
    "  x.onclick = function(){ chip.parentNode.removeChild(chip); };"
    "  chip.appendChild(hid); chip.appendChild(txt); chip.appendChild(x);"
    "  wrap.appendChild(chip); inp.value=''; inp.focus();"
    "}"
    "function pantryAddKey(e){ if(e.key==='Enter'){ e.preventDefault(); addCustomStaple(); } }"
    "function pantryShowEdit(){"
    "  var v=document.getElementById('pantry-view');"
    "  var ed=document.getElementById('pantry-edit');"
    "  if(v){ v.style.display='none'; } if(ed){ ed.style.display='block'; }"
    "}"
    "</script>"
)

_GROUP_BOX = ("background:var(--warm-white,#fff);border:1px solid var(--border,#e6e0d4);"
              "border-radius:var(--radius-md,12px);padding:14px 16px;margin-bottom:14px;")
_GROUP_TITLE = ("font-family:" + _HEADING_FONT + ";font-size:1.15em;font-weight:600;"
                "color:var(--ink);margin:0 0 10px;")
_ITEM_LABEL = ("display:inline-flex;align-items:center;gap:8px;background:var(--parchment,#faf6ec);"
               "border:1px solid var(--border-light,#ece6d8);border-radius:999px;"
               "padding:6px 12px;margin:0 8px 8px 0;font-size:0.92em;color:var(--ink);"
               "cursor:pointer;")
_BTN_PRIMARY = ("display:block;width:100%;margin-top:8px;padding:15px 18px;border:none;"
                "border-radius:var(--radius-md,12px);background:var(--gold-mid,#c9a84a);"
                "color:var(--ink);font-weight:700;font-size:1.05em;cursor:pointer;")
_BTN_GHOST = ("display:inline-block;margin-bottom:18px;padding:9px 16px;"
              "border:1px solid var(--border,#e6e0d4);border-radius:var(--radius-sm,8px);"
              "background:var(--warm-white,#fff);color:var(--ink);font-weight:600;"
              "font-size:0.9em;cursor:pointer;")


def _checkbox_list(field, checked):
    """Render every group as labelled checkboxes named `field`.

    `checked` is either a set of item names that should be pre-checked, or
    None meaning pre-check everything (first-run default).
    """
    blocks = []
    for group, items in _GROUPS:
        rows = []
        for it in items:
            ev = escape(it)
            on = (checked is None) or (it in checked)
            ck = " checked" if on else ""
            rows.append(
                f'<label style="{_ITEM_LABEL}">'
                f'<input type="checkbox" name="{field}" value="{ev}"{ck}> {ev}'
                f'</label>'
            )
        rows_html = "".join(rows)
        blocks.append(
            f'<div style="{_GROUP_BOX}">'
            f'<h3 style="{_GROUP_TITLE}">{escape(group)}</h3>'
            f'<div>{rows_html}</div>'
            f'</div>'
        )
    return "".join(blocks)


def _custom_chips(customs):
    """Render already-saved custom items as removable chips."""
    chips = []
    for c in customs:
        ec = escape(c)
        chips.append(
            f'<span style="display:inline-flex;align-items:center;gap:6px;'
            f'background:var(--gold-light,#f3ead2);color:var(--ink);border-radius:999px;'
            f'padding:5px 12px;margin:0 6px 6px 0;font-size:0.9em;">'
            f'<input type="hidden" name="custom_item" value="{ec}">{ec} '
            f'<span onclick="this.parentNode.remove()" style="cursor:pointer;font-weight:700;">'
            f'&times;</span></span>'
        )
    return "".join(chips)


def _custom_field():
    """The free-text custom-staple input + Add button + chip tray."""
    return (
        f'<div style="{_GROUP_BOX}">'
        f'<h3 style="{_GROUP_TITLE}">Anything else you always keep on hand?</h3>'
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">'
        f'<input type="text" id="custom-staple-input" onkeydown="pantryAddKey(event)" '
        f'placeholder="e.g. maple syrup" '
        f'style="flex:1;min-width:200px;padding:10px 12px;border:1px solid var(--border,#e6e0d4);'
        f'border-radius:var(--radius-sm,8px);font-size:0.95em;">'
        f'<button type="button" onclick="addCustomStaple()" '
        f'style="padding:10px 18px;border:none;border-radius:var(--radius-sm,8px);'
        f'background:var(--ink,#3a3324);color:#fff;font-weight:600;cursor:pointer;">Add</button>'
        f'</div>'
        f'<div id="custom-chips" style="margin-top:12px;">{{chips}}</div>'
        f'</div>'
    )


def _editable_form(checked, customs, save_label):
    """The first-run / edit checklist form. POSTs to /pantry-staples-save."""
    custom_block = _custom_field().replace("{chips}", _custom_chips(customs))
    return (
        f'<form method="POST" action="/pantry-staples-save">'
        f'<input type="hidden" name="setup_complete" value="true">'
        f'{_checkbox_list("staple", checked)}'
        f'{custom_block}'
        f'<button type="submit" style="{_BTN_PRIMARY}">{escape(save_label)}</button>'
        f'</form>'
    )


def _first_run_body():
    intro = ("Tell Lorenzo what you always keep on hand. These items will never "
             "appear on your grocery list unless you flag them as running low.")
    return (
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">'
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin:0 0 4px;">Pantry Staples Setup</h1>'
        f'<a href="/meal-wizard" style="flex-shrink:0;color:var(--ink-muted);'
        f'font-size:0.9em;text-decoration:none;margin-top:8px;">Skip for now</a>'
        f'</div>'
        f'<p style="color:var(--ink-muted);font-size:0.95em;margin:0 0 22px;">{escape(intro)}</p>'
        f'{_editable_form(None, [], "Save My Staples")}'
    )


def _returning_body(data):
    items = set(data.get("items") or [])
    customs = list(data.get("custom") or [])
    running_low = set(data.get("running_low") or [])

    # View mode: a running-low form over the staples she currently keeps.
    view_groups = []
    for group, group_items in _GROUPS:
        present = [it for it in group_items if it in items]
        if not present:
            continue
        rows = []
        for it in present:
            ev = escape(it)
            ck = " checked" if it in running_low else ""
            rows.append(
                f'<label style="{_ITEM_LABEL}">'
                f'<input type="checkbox" name="running_low" value="{ev}"{ck}> {ev}'
                f'</label>'
            )
        view_groups.append(
            f'<div style="{_GROUP_BOX}">'
            f'<h3 style="{_GROUP_TITLE}">{escape(group)}</h3>'
            f'<div>{"".join(rows)}</div></div>'
        )
    if customs:
        rows = []
        for it in customs:
            ev = escape(it)
            ck = " checked" if it in running_low else ""
            rows.append(
                f'<label style="{_ITEM_LABEL}">'
                f'<input type="checkbox" name="running_low" value="{ev}"{ck}> {ev}'
                f'</label>'
            )
        view_groups.append(
            f'<div style="{_GROUP_BOX}">'
            f'<h3 style="{_GROUP_TITLE}">Other</h3>'
            f'<div>{"".join(rows)}</div></div>'
        )
    view_html = "".join(view_groups) or (
        f'<p style="color:var(--ink-muted);">No staples saved yet.</p>'
    )

    hint = ("Check anything you are running low on to add it to the next grocery "
            "list. Everything else stays off the list automatically.")

    view_mode = (
        f'<div id="pantry-view">'
        f'<button type="button" onclick="pantryShowEdit()" style="{_BTN_GHOST}">Edit Staples</button>'
        f'<p style="color:var(--ink-muted);font-size:0.95em;margin:0 0 18px;">{escape(hint)}</p>'
        f'<form method="POST" action="/pantry-staples-save">'
        f'<input type="hidden" name="setup_complete" value="true">'
        f'{view_html}'
        f'<button type="submit" style="{_BTN_PRIMARY}">Save Changes</button>'
        f'</form>'
        f'</div>'
    )

    # Edit mode: hidden until the user taps Edit Staples; reuses the checklist.
    edit_mode = (
        f'<div id="pantry-edit" style="display:none;">'
        f'<p style="color:var(--ink-muted);font-size:0.95em;margin:0 0 18px;">'
        f'Add or remove anything you keep on hand, then save.</p>'
        f'{_editable_form(items, customs, "Save Changes")}'
        f'</div>'
    )

    return (
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin:0 0 18px;">Pantry Staples</h1>'
        f'{view_mode}{edit_mode}'
    )


def render_pantry_staples_page(user: str) -> str:
    """Render the Pantry Staples page in first-run or returning mode."""
    data = load_pantry_staples() or {}
    setup_complete = bool(data.get("setup_complete"))
    inner = _returning_body(data) if setup_complete else _first_run_body()
    body = (
        f'<div style="max-width:680px;margin:0 auto;padding:24px 16px 96px;">'
        f'{inner}'
        f'</div>'
        f'{_PAGE_JS}'
    )
    return html_page("Pantry Staples", body)


# ── Step 1: Week at a Glance ────────────────────────────────────────────────
# Style strings pulled out of f-strings to keep Rules 1 & 2 satisfied.
_WG_SUBTITLE = "color:var(--ink-muted);font-size:0.95em;margin:2px 0 22px;"
_WG_DAY_CARD = ("background:var(--warm-white,#fff);border:1px solid var(--border,#e6e0d4);"
                "border-radius:var(--radius-md,12px);padding:0 0 12px;margin-bottom:14px;"
                "overflow:hidden;")
_WG_DAY_HEADER = ("font-family:" + _HEADING_FONT + ";font-size:1.15em;font-weight:600;"
                  "color:var(--ink);margin:0;padding:12px 16px 2px;")
_WG_SEASON_DOT = ("display:inline-block;width:10px;height:10px;border-radius:50%;"
                  "margin-right:8px;vertical-align:middle;")
_WG_SEASON_LABEL = "color:var(--ink-muted);font-size:0.82em;padding:0 16px 8px;"
_WG_CHIP_ROW = "padding:0 16px 4px;display:flex;flex-wrap:wrap;gap:6px;"
_WG_EVENT_ROW = "color:var(--ink);font-size:0.92em;padding:3px 16px;"
_WG_QUIET = "color:var(--ink-muted);font-size:0.9em;font-style:italic;padding:3px 16px;"
_WG_RULE_CHIP = ("display:inline-block;background:var(--parchment,#faf6ec);"
                 "border:1px solid var(--border-light,#ece6d8);border-radius:999px;"
                 "padding:6px 12px;margin:0 6px 6px 0;font-size:0.9em;color:var(--ink);")
_WG_BTN_LINK = ("display:block;width:100%;box-sizing:border-box;margin-top:20px;"
                "padding:15px 18px;border-radius:var(--radius-md,12px);"
                "background:var(--gold-mid,#c9a84a);color:var(--ink);font-weight:700;"
                "font-size:1.05em;text-align:center;text-decoration:none;")

# Fixed chip palettes (label/background/foreground) for the liturgical markers.
_WG_FEAST_DEFAULT_BG = "#6b4f9e"
_WG_ABSTINENCE_BG = "#b23b3b"
_WG_FAST_BG = "#c98a2e"

# Colors flow in from liturgical data INCLUDING user-editable custom overrides
# (/liturgical/edit), so they must be allowlisted before going into a style
# attribute — escape() does not neutralize CSS/attribute-breaking payloads.
_WG_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_WG_NAMED_COLORS = {
    "purple", "violet", "white", "red", "green", "gold", "rose", "pink",
    "blue", "black", "gray", "grey", "amber", "orange", "yellow", "brown",
}


def _wg_safe_color(value, fallback: str) -> str:
    """Return `value` only if it is a hex color or a vetted named color;
    otherwise the safe `fallback`. Prevents style-attribute breakout."""
    v = (value or "").strip()
    if _WG_HEX_RE.match(v):
        return v
    if v.lower() in _WG_NAMED_COLORS:
        return v.lower()
    return fallback


def _wg_marker_chip(label: str, bg: str, fg: str = "#ffffff") -> str:
    """Render a small liturgical marker chip. `label` is escaped once."""
    return (f'<span style="display:inline-block;border-radius:999px;'
            f'padding:3px 11px;font-size:0.8em;font-weight:600;'
            f'background:{bg};color:{fg};">{escape(label)}</span>')


def _wg_rules_panel() -> str:
    """Week-level meal rules panel. Rules have no day field, so they live once
    at the top. Guards the loader returning a non-list (Rule: defensive shape)."""
    raw = load_meal_rules()
    rules = raw if isinstance(raw, list) else []
    texts = [
        r.get("rule", "").strip()
        for r in rules
        if isinstance(r, dict) and r.get("rule", "").strip()
    ]
    if texts:
        chips = "".join(
            f'<span style="{_WG_RULE_CHIP}">{escape(t)}</span>' for t in texts
        )
        inner = f'<div style="display:flex;flex-wrap:wrap;">{chips}</div>'
    else:
        inner = f'<p style="color:var(--ink-muted);margin:0;">No meal rules set yet.</p>'
    return (
        f'<div style="{_GROUP_BOX}">'
        f'<h3 style="{_GROUP_TITLE}">This week\u2019s meal rules</h3>'
        f'{inner}'
        f'</div>'
    )


def _wg_event_line(ev: dict) -> str:
    """Format one merged calendar event like Lorenzo's formatter: split start/end
    on the T, guard the all-day no-T case, append the who suffix when present."""
    title = escape(ev.get("title") or "(untitled)")
    start = ev.get("start") or ""
    end = ev.get("end") or ""
    st = start.split("T", 1)[1][:5] if "T" in start else ""
    et = end.split("T", 1)[1][:5] if "T" in end else ""
    if st and et:
        time_str = f"{st}-{et}"
    elif st:
        time_str = st
    else:
        time_str = "All day"
    who = (ev.get("who") or "").strip()
    who_str = f" \u2014 {escape(who)}" if who else ""
    return f'<div style="{_WG_EVENT_ROW}">{escape(time_str)}  {title}{who_str}</div>'


def _wg_day_card(d: date, day_events: list) -> str:
    """Render one day card: liturgical header + marker chips + commitments."""
    info = get_day_info(d)
    weekday = escape(info.get("weekday", ""))
    date_label = escape(info.get("date_label", ""))
    season = info.get("season", "")
    season_color = _wg_safe_color(info.get("season_color"), "#888")

    header = (
        f'<h3 style="{_WG_DAY_HEADER}">'
        f'<span style="{_WG_SEASON_DOT}background:{season_color};"></span>'
        f'{weekday} \u2014 {date_label}</h3>'
    )
    season_label = (
        f'<div style="{_WG_SEASON_LABEL}">{escape(season)}</div>' if season else ""
    )

    chips = []
    feast_name = info.get("feast_name") or ""
    if feast_name:
        feast_bg = _wg_safe_color(info.get("feast_color"), _WG_FEAST_DEFAULT_BG)
        chips.append(_wg_marker_chip(feast_name, feast_bg))
    if info.get("is_abstinence"):
        chips.append(_wg_marker_chip("Abstinence \u2014 no meat", _WG_ABSTINENCE_BG))
    if info.get("is_fast"):
        chips.append(_wg_marker_chip("Fast day", _WG_FAST_BG))
    chip_row = (
        f'<div style="{_WG_CHIP_ROW}">{"".join(chips)}</div>' if chips else ""
    )

    if day_events:
        events_html = "".join(_wg_event_line(ev) for ev in day_events)
    else:
        events_html = f'<div style="{_WG_QUIET}">No commitments</div>'

    return (
        f'<div style="{_WG_DAY_CARD}">'
        f'{header}{season_label}{chip_row}{events_html}'
        f'</div>'
    )


def render_meal_wizard_week_glance(user: str, start_iso: str = None) -> str:
    """Step 1 of the Meal Planning Wizard — a read-only orientation view of the
    coming week: this week's meal rules, then 7 day cards each showing the
    liturgical season/feast/fast/abstinence markers and that day's commitments."""
    if not start_iso:
        start_iso = date.today().isoformat()
    start_d = date.fromisoformat(start_iso)

    # One merged fetch for the whole week, grouped by ISO date. Degrade quietly
    # to "no commitments" if the calendar sources are unavailable.
    events_by_date = {}
    try:
        for ev in get_merged_calendar_events(start_iso, 7):
            key = (ev.get("start") or "")[:10]
            events_by_date.setdefault(key, []).append(ev)
    except Exception:
        events_by_date = {}

    day_cards = []
    for offset in range(7):
        d = start_d + timedelta(days=offset)
        day_cards.append(_wg_day_card(d, events_by_date.get(d.isoformat(), [])))

    inner = (
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin:0 0 2px;">Plan This Week\u2019s Meals</h1>'
        f'<p style="{_WG_SUBTITLE}">Step 1 of 6 \u2014 Your week at a glance</p>'
        f'{_wg_rules_panel()}'
        f'{"".join(day_cards)}'
        f'<a href="/meal-wizard-step2" style="{_WG_BTN_LINK}">Continue</a>'
    )
    body = (
        f'<div style="max-width:680px;margin:0 auto;padding:24px 16px 96px;">'
        f'{inner}'
        f'</div>'
    )
    return html_page("Plan This Week\u2019s Meals", body)
