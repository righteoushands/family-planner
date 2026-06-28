"""
render_meal_wizard_step4.py — Meal Planning Wizard, Step 4 (READ-ONLY screen).

Phase G1b-1: shows the planning week as day cards (liturgical header +
commitments) with each day's selected meal slots, displaying any meals already
confirmed in the wizard session. It is DISPLAY ONLY — no entry, no confirm, no
change/remove, NO JavaScript. The write side (manual entry, confirm/remove
wiring, ingredient checks, recipe attach, server guard) is Phase G1b-2.

All data access goes through data_helpers (Rule 19); page chrome comes from
ui_helpers.html_page. The liturgical color sanitizer and the minimal day-card
header/events markup are REPLICATED here (not imported from render_meal_wizard)
on purpose: render_meal_wizard re-exports this module from the top of the file,
so importing _wg_day_card / _wg_safe_color back would be a circular import that
fails at load time. Keeping the dependency one-way avoids that and respects the
all-imports-at-top rule. Colors still pass through a local allowlist before
landing in any style attribute (Known Issue #2).

No backslash ever appears inside an f-string EXPRESSION (Rules 1 & 2); the only
backslashes are \\u escapes in literal text, matching the existing Step 1/3
renderers.
"""
import re
from datetime import date, timedelta
from html import escape
from ui_helpers import html_page
from data_helpers import load_meal_wizard_session, get_merged_calendar_events
from render_liturgical import get_day_info

_HEADING_FONT = "'Cormorant Garamond', serif"

_S4_TITLE = "Plan This Week\u2019s Meals"

# Canonical slot order + labels (mirrors Step 3's labels; same stable order the
# spec requires). James is never a cook or assignee, so nothing here references
# him.
_S4_SLOT_ORDER = [
    ("breakfast", "Breakfast"),
    ("lunch", "Lunch"),
    ("dinner", "Dinner"),
    ("johns_lunch", "John\u2019s lunch"),
    ("snacks", "Snacks"),
    ("dessert", "Dessert"),
    ("feast_meal", "Feast meal"),
    ("batch_cook", "Batch cook (Sunday)"),
]
_S4_SOURCE_LABELS = {"manual": "manual", "lorenzo": "lorenzo", "prefill": "prefill"}

# ── Style constants (pulled out of f-strings: Rules 1 & 2) ───────────────────
_S4_SUBTITLE = "color:var(--ink-muted);font-size:0.95em;margin:2px 0 22px;"
_S4_DAY_CARD = ("background:var(--warm-white,#fff);border:1px solid var(--border,#e6e0d4);"
                "border-radius:var(--radius-md,12px);padding:0 0 12px;margin-bottom:14px;"
                "overflow:hidden;")
_S4_DAY_HEADER = ("font-family:" + _HEADING_FONT + ";font-size:1.15em;font-weight:600;"
                  "color:var(--ink);margin:0;padding:12px 16px 2px;")
_S4_SEASON_DOT = ("display:inline-block;width:10px;height:10px;border-radius:50%;"
                  "margin-right:8px;vertical-align:middle;")
_S4_SEASON_LABEL = "color:var(--ink-muted);font-size:0.82em;padding:0 16px 8px;"
_S4_CHIP_ROW = "padding:0 16px 4px;display:flex;flex-wrap:wrap;gap:6px;"
_S4_EVENT_ROW = "color:var(--ink);font-size:0.92em;padding:3px 16px;"
_S4_QUIET = "color:var(--ink-muted);font-size:0.9em;font-style:italic;padding:3px 16px;"

_S4_SLOTS_WRAP = ("border-top:1px solid var(--border-light,#ece6d8);"
                  "margin:10px 16px 0;padding:8px 0 0;")
_S4_SLOT_ROW = "padding:8px 0;"
_S4_SLOT_LABEL = "font-weight:600;color:var(--ink);font-size:0.92em;"
_S4_MEAL_NAME = "color:var(--ink);font-size:0.95em;margin-top:2px;"
_S4_META = "color:var(--ink-muted);font-size:0.85em;margin-top:2px;"
_S4_EMPTY = "color:var(--ink-muted);font-size:0.9em;font-style:italic;margin-top:2px;"
_S4_TAG_ROW = "margin-top:5px;display:flex;flex-wrap:wrap;gap:6px;"
_S4_TAG = ("display:inline-block;background:var(--parchment,#faf6ec);"
           "border:1px solid var(--border-light,#ece6d8);border-radius:999px;"
           "padding:2px 9px;font-size:0.78em;color:var(--ink-muted);")

_S4_GATE_BOX = ("background:var(--warm-white,#fff);border:1px solid var(--border,#e6e0d4);"
                "border-radius:var(--radius-md,12px);padding:18px 20px;margin-bottom:14px;")
_S4_GATE_TEXT = "color:var(--ink);font-size:0.98em;line-height:1.5;margin:0 0 14px;"
_S4_LINK_BTN = ("display:inline-block;padding:12px 18px;border-radius:var(--radius-md,12px);"
                "background:var(--gold-mid,#c9a84a);color:var(--ink);font-weight:700;"
                "font-size:1em;text-decoration:none;")
_S4_NAV_ROW = "display:flex;justify-content:flex-start;align-items:center;margin-top:18px;"
_S4_BACK = "color:var(--ink-muted);font-size:0.95em;text-decoration:none;"

# Fixed chip palettes (mirror render_meal_wizard's liturgical markers).
_S4_FEAST_DEFAULT_BG = "#6b4f9e"
_S4_ABSTINENCE_BG = "#b23b3b"
_S4_FAST_BG = "#c98a2e"

# Liturgical colors flow in from user-editable overrides, so they MUST be
# allowlisted before landing in a style attribute (Known Issue #2). escape()
# does not neutralize CSS/attribute-breaking payloads.
_S4_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_S4_NAMED_COLORS = {
    "purple", "violet", "white", "red", "green", "gold", "rose", "pink",
    "blue", "black", "gray", "grey", "amber", "orange", "yellow", "brown",
}


def _s4_safe_color(value, fallback: str) -> str:
    """Return `value` only if it is a hex color or a vetted named color;
    otherwise the safe `fallback`. Prevents style-attribute breakout."""
    v = (value or "").strip()
    if _S4_HEX_RE.match(v):
        return v
    if v.lower() in _S4_NAMED_COLORS:
        return v.lower()
    return fallback


def _s4_marker_chip(label: str, bg: str, fg: str = "#ffffff") -> str:
    """Render a small liturgical marker chip. `label` is escaped once; `bg` is
    already sanitized by the caller via _s4_safe_color."""
    return (f'<span style="display:inline-block;border-radius:999px;'
            f'padding:3px 11px;font-size:0.8em;font-weight:600;'
            f'background:{bg};color:{fg};">{escape(label)}</span>')


def _s4_event_line(ev: dict) -> str:
    """Format one merged calendar event (start/end split on T, all-day guard,
    optional who suffix). Mirrors the Step 1 event line."""
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
    return f'<div style="{_S4_EVENT_ROW}">{escape(time_str)}  {title}{who_str}</div>'


def _s4_recipe_label(entry: dict) -> str:
    """The recipe state for a confirmed meal. The 'not set yet' case is the
    half-confirmed state the G1b-2 recipe default will prevent — surface it
    plainly here, never hide it."""
    if (entry.get("recipe_id") or "").strip():
        return "Recipe attached"
    if entry.get("recipe_on_request"):
        return "No recipe needed"
    return "Recipe: not set yet"


def _s4_slot_block(label: str, entry) -> str:
    """One slot row: the meal (name + recipe state + tags) when confirmed, or a
    quiet 'Not planned yet' placeholder when empty. No inputs, no buttons."""
    label_html = f'<div style="{_S4_SLOT_LABEL}">{escape(label)}</div>'
    if not isinstance(entry, dict):
        return (f'<div style="{_S4_SLOT_ROW}">{label_html}'
                f'<div style="{_S4_EMPTY}">Not planned yet</div></div>')
    name = escape(entry.get("name") or "")
    recipe = escape(_s4_recipe_label(entry))
    source = (entry.get("source") or "").strip().lower()
    tags = []
    if source in _S4_SOURCE_LABELS:
        tags.append(f'<span style="{_S4_TAG}">{escape(_S4_SOURCE_LABELS[source])}</span>')
    if entry.get("skip_shopping"):
        tags.append(f'<span style="{_S4_TAG}">off shopping list</span>')
    tags_html = (f'<div style="{_S4_TAG_ROW}">{"".join(tags)}</div>') if tags else ""
    return (f'<div style="{_S4_SLOT_ROW}">{label_html}'
            f'<div style="{_S4_MEAL_NAME}">{name}</div>'
            f'<div style="{_S4_META}">{recipe}</div>'
            f'{tags_html}</div>')


def _s4_day_card(d: date, day_events: list, to_plan, confirmed: dict) -> str:
    """One day card: replicated liturgical header + commitments, then the meal
    slots selected for this week with any confirmed meals shown."""
    info = get_day_info(d)
    weekday = escape(info.get("weekday", ""))
    date_label = escape(info.get("date_label", ""))
    season = info.get("season", "")
    season_color = _s4_safe_color(info.get("season_color"), "#888")

    header = (
        f'<h3 style="{_S4_DAY_HEADER}">'
        f'<span style="{_S4_SEASON_DOT}background:{season_color};"></span>'
        f'{weekday} \u2014 {date_label}</h3>'
    )
    season_label = (
        f'<div style="{_S4_SEASON_LABEL}">{escape(season)}</div>' if season else ""
    )

    chips = []
    feast_name = info.get("feast_name") or ""
    if feast_name:
        feast_bg = _s4_safe_color(info.get("feast_color"), _S4_FEAST_DEFAULT_BG)
        chips.append(_s4_marker_chip(feast_name, feast_bg))
    if info.get("is_abstinence"):
        chips.append(_s4_marker_chip("Abstinence \u2014 no meat", _S4_ABSTINENCE_BG))
    if info.get("is_fast"):
        chips.append(_s4_marker_chip("Fast day", _S4_FAST_BG))
    chip_row = (
        f'<div style="{_S4_CHIP_ROW}">{"".join(chips)}</div>' if chips else ""
    )

    if day_events:
        events_html = "".join(_s4_event_line(ev) for ev in day_events)
    else:
        events_html = f'<div style="{_S4_QUIET}">No commitments</div>'

    iso = d.isoformat()
    slot_blocks = []
    for (slot_key, slot_label) in _S4_SLOT_ORDER:
        if slot_key not in to_plan:
            continue
        slot_blocks.append(_s4_slot_block(slot_label, confirmed.get(iso + "::" + slot_key)))
    if slot_blocks:
        slots_html = f'<div style="{_S4_SLOTS_WRAP}">{"".join(slot_blocks)}</div>'
    else:
        slots_html = (
            f'<div style="{_S4_SLOTS_WRAP}">'
            f'<div style="{_S4_QUIET}">No meal types selected for this week</div>'
            f'</div>'
        )

    return (
        f'<div style="{_S4_DAY_CARD}">'
        f'{header}{season_label}{chip_row}{events_html}{slots_html}'
        f'</div>'
    )


def _s4_gate_body() -> str:
    """Calm gate state when the session has no planning window yet."""
    msg = "Finish Step 3 first to choose what to plan and the week."
    inner = (
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin:0 0 2px;">{_S4_TITLE}</h1>'
        f'<p style="{_S4_SUBTITLE}">Step 4 of 6 \u2014 Build the menu</p>'
        f'<div style="{_S4_GATE_BOX}">'
        f'<p style="{_S4_GATE_TEXT}">{escape(msg)}</p>'
        f'<a href="/meal-wizard-step3" style="{_S4_LINK_BTN}">Go to Step 3</a>'
        f'</div>'
    )
    return (
        f'<div style="max-width:680px;margin:0 auto;padding:24px 16px 96px;">'
        f'{inner}'
        f'</div>'
    )


def render_meal_wizard_step4(user: str, start_iso: str = None) -> str:
    """Step 4 of the Meal Planning Wizard — READ-ONLY. Reads the wizard session
    (planning_window, confirmed_what_to_plan, confirmed_meals) and renders the
    planning week as day cards with their meal slots. Writes nothing. The
    `start_iso` argument mirrors the Step 1 signature; the window always comes
    from the saved session, which is the source of truth for Step 4."""
    session = load_meal_wizard_session() or {}
    window = session.get("planning_window") or {}
    to_plan = session.get("confirmed_what_to_plan") or []
    confirmed = session.get("confirmed_meals") or {}
    # confirmed_inventory is intentionally read-but-unused here; green/red
    # ingredient parsing is G1b-2.
    _inventory = session.get("confirmed_inventory") or ""

    win_start = window.get("start_iso")
    win_end = window.get("end_iso")
    start_d = None
    end_d = None
    if win_start and win_end:
        try:
            start_d = date.fromisoformat(win_start)
            end_d = date.fromisoformat(win_end)
        except (ValueError, TypeError):
            start_d = None
            end_d = None
    if not start_d or not end_d:
        return html_page(_S4_TITLE, _s4_gate_body())

    if end_d < start_d:
        start_d, end_d = end_d, start_d
    span = (end_d - start_d).days
    if span > 60:
        span = 60

    events_by_date = {}
    try:
        for ev in get_merged_calendar_events(start_d.isoformat(), span + 1):
            key = (ev.get("start") or "")[:10]
            events_by_date.setdefault(key, []).append(ev)
    except Exception:
        events_by_date = {}

    day_cards = []
    for offset in range(span + 1):
        d = start_d + timedelta(days=offset)
        day_cards.append(
            _s4_day_card(d, events_by_date.get(d.isoformat(), []), to_plan, confirmed)
        )

    nav = (
        f'<div style="{_S4_NAV_ROW}">'
        f'<a href="/meal-wizard-step3" style="{_S4_BACK}">\u2190 Back</a>'
        f'</div>'
    )
    inner = (
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin:0 0 2px;">{_S4_TITLE}</h1>'
        f'<p style="{_S4_SUBTITLE}">Step 4 of 6 \u2014 Build the menu</p>'
        f'{"".join(day_cards)}'
        f'{nav}'
    )
    body = (
        f'<div style="max-width:680px;margin:0 auto;padding:24px 16px 96px;">'
        f'{inner}'
        f'</div>'
    )
    return html_page(_S4_TITLE, body)
