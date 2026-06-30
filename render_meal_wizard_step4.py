"""
render_meal_wizard_step4.py — Meal Planning Wizard, Step 4 (READ-ONLY screen).

Phase G1b-1: shows the planning week as day cards (liturgical header +
commitments) with each day's selected meal slots, displaying any meals already
confirmed in the wizard session.

Phase G1b-2a (current): the manual WRITE LOOP. Each empty, non-prefill slot
gets an entry affordance (meal name + optional ingredients + optional main
protein) and a "Keep this meal" button that confirms it into the wizard session
via /meal-wizard-step4-confirm; each confirmed non-prefill meal gets a "Change"
button that removes it via /meal-wizard-step4-remove so Lauren can re-enter.
Prefill (past) meals stay locked with no button. On success the page reloads so
the session remains the single source of truth. Still OUT OF SCOPE here:
ingredient green/red checks and the recipe-attach flow (both G1b-2b).

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
from data_helpers import load_meal_wizard_session, get_merged_calendar_events, slot_dishes
from render_liturgical import get_day_info
from render_meal_wizard_gen import wizard_target_slot_keys, _WIZARD_GEN_SLOT_CAP

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

# G1b-2a: entry-affordance / write-loop styling.
_S4_INPUT = ("width:100%;box-sizing:border-box;padding:8px 10px;margin-top:6px;"
             "border:1px solid var(--border,#e6e0d4);border-radius:8px;"
             "font-size:0.92em;color:var(--ink);background:var(--warm-white,#fff);")
# Meal NAME field is a wrapping textarea (not a single-line input) so long names
# like "Ground Beef Pasta with Spaghetti Sauce" show in full with no horizontal
# scroll. Reuses _S4_INPUT, adds wrapping + vertical resize. No JS auto-grow.
_S4_NAME_AREA = (_S4_INPUT + "resize:vertical;overflow-wrap:break-word;"
                 "white-space:pre-wrap;font-family:inherit;line-height:1.3;")
# Ingredients box is a native <details> (no JS). It renders <details open> when a
# Lorenzo suggestion is present (so Lauren reviews it) and closed otherwise (calm,
# compact). The input stays in the DOM either way so s4Keep can read it.
_S4_DETAILS = "margin-top:6px;"
_S4_SUMMARY = ("cursor:pointer;font-size:0.85em;color:var(--ink-muted);"
               "user-select:none;")
_S4_KEEP_BTN = ("margin-top:8px;padding:8px 14px;border:none;border-radius:8px;"
                "background:var(--gold-mid,#c9a84a);color:var(--ink);font-weight:700;"
                "font-size:0.9em;cursor:pointer;")
_S4_CHANGE_BTN = ("margin-top:6px;padding:6px 12px;border:1px solid var(--border,#e6e0d4);"
                  "border-radius:8px;background:var(--warm-white,#fff);"
                  "color:var(--ink-muted);font-size:0.85em;cursor:pointer;")
_S4_MSG = "color:#b23b3b;font-size:0.85em;margin-top:6px;min-height:1em;"

# G1 lock ("Set this plan"): banner + button styling.
_S4_BANNER = ("background:var(--parchment,#faf6ec);"
              "border:1px solid var(--border-light,#ece6d8);"
              "border-radius:var(--radius-md,12px);padding:12px 16px;margin:0 0 16px;"
              "color:var(--ink);font-size:0.95em;line-height:1.5;")
_S4_LOCK_WRAP = "margin-top:20px;text-align:center;"
_S4_LOCK_BTN = ("padding:12px 22px;border:none;border-radius:var(--radius-md,12px);"
                "background:var(--gold-mid,#c9a84a);color:var(--ink);font-weight:700;"
                "font-size:1em;cursor:pointer;")
_S4_LOCK_HINT = "color:var(--ink-muted);font-size:0.9em;font-style:italic;"
_S4_LOCK_MSG = ("color:#b23b3b;font-size:0.85em;margin-top:8px;min-height:1em;"
                "text-align:center;")

# Wizard slots that have a store home (mirror render_meals._WIZARD_TO_STORE_SLOT):
# only these count toward "there is something to set". feast_meal / batch_cook
# are wizard-only (no store slot) so they do NOT enable the button on their own.
_S4_LOCKABLE_SLOTS = {"breakfast", "lunch", "dinner", "snacks", "dessert", "johns_lunch"}

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


# G1b-2a inline JS — the manual write loop. Built as CONCATENATED STRING
# LITERALS (not an f-string) like render_meal_wizard_step3.py's s3Save, so there
# are no Python-side brace or quote conflicts (Rules 1, 2). No backslash-n ever
# appears inside a JS string here (Rules 7, 12). Inputs/buttons are addressed by
# unique element id (s4-<field>--<date>--<slot>). Keep (s4Keep) and Change
# (s4Change) do NOT reload: on success they inject the server-rendered slot row
# (s4-row--<key>) and lock control (s4-lock-control) returned by the handler, so
# the session stays the single source of truth with no client-side markup
# rebuild and no full-page flash (Rule 20 scroll-restore is therefore not needed
# for them). Set this plan (s4Lock) and Generate (s4Generate) still RELOAD on
# success and keep their scroll-save (Rule 20).
_S4_JS = (
    "<script>"
    "(function(){"
    "  function elById(id){ return document.getElementById(id); }"
    "  function valOf(id){ var el = elById(id); return el ? (el.value || '').trim() : ''; }"
    "  function setMsg(id, text){ var el = elById(id); if(el){ el.textContent = text; } }"
    "  window.s4Keep = function(date, slot){"
    "    var key = date + '--' + slot;"
    "    var msgId = 's4-msg--' + key;"
    "    setMsg(msgId, '');"
    "    var name = valOf('s4-name--' + key);"
    "    if(!name){ setMsg(msgId, 'Add a meal name first.'); return; }"
    "    var ing = valOf('s4-ing--' + key);"
    "    var prot = valOf('s4-prot--' + key);"
    "    var payload = { date: date, slot: slot, name: name, source: 'manual',"
    "      ingredients: ing, protein: prot, recipe_id: '', recipe_on_request: true };"
    "    fetch('/meal-wizard-step4-confirm', { method:'POST',"
    "      headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) })"
    "      .then(function(r){ return r.json(); })"
    "      .then(function(j){ if(j && j.ok && j.slot_html){"
    "          var row = elById('s4-row--' + key); if(row){ row.outerHTML = j.slot_html; }"
    "          var lock = elById('s4-lock-control'); if(lock && j.lock_html){ lock.outerHTML = j.lock_html; } }"
    "        else { setMsg(msgId, 'Could not save. Please try again.'); } })"
    "      .catch(function(){ setMsg(msgId, 'Could not save. Please try again.'); });"
    "  };"
    "  window.s4Change = function(date, slot){"
    "    var key = date + '--' + slot;"
    "    var msgId = 's4-msg--' + key;"
    "    setMsg(msgId, '');"
    "    var payload = { date: date, slot: slot };"
    "    fetch('/meal-wizard-step4-remove', { method:'POST',"
    "      headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) })"
    "      .then(function(r){ return r.json(); })"
    "      .then(function(j){ if(j && j.ok && j.slot_html){"
    "          var row = elById('s4-row--' + key); if(row){ row.outerHTML = j.slot_html; }"
    "          var lock = elById('s4-lock-control'); if(lock && j.lock_html){ lock.outerHTML = j.lock_html; } }"
    "        else { setMsg(msgId, 'Could not change. Please try again.'); } })"
    "      .catch(function(){ setMsg(msgId, 'Could not change. Please try again.'); });"
    "  };"
    "  window.s4Lock = function(){"
    "    var msg = elById('s4-lock-msg');"
    "    if(msg){ msg.textContent = ''; }"
    "    fetch('/meal-wizard-step4-lock', { method:'POST',"
    "      headers:{'Content-Type':'application/json'}, body: '{}' })"
    "      .then(function(r){ return r.json(); })"
    "      .then(function(j){ if(j && j.ok){ sessionStorage.setItem('s4ScrollY', String(window.scrollY)); window.location.href = '/meal-wizard-step4'; }"
    "        else if(msg){ msg.textContent = 'Could not set your plan. Please try again.'; } })"
    "      .catch(function(){ if(msg){ msg.textContent = 'Could not set your plan. Please try again.'; } });"
    "  };"
    "  window.s4Generate = function(btn){"
    "    var msg = elById('s4-gen-msg');"
    "    if(msg){ msg.textContent = ''; }"
    "    var origLabel = btn ? btn.textContent : '';"
    "    if(btn){ btn.disabled = true; btn.textContent = 'Generating... this can take up to a minute'; }"
    "    fetch('/meal-wizard-generate', { method:'POST',"
    "      headers:{'Content-Type':'application/json'}, body: '{}' })"
    "      .then(function(r){ return r.json(); })"
    "      .then(function(j){ var n = (j && j.generated) ? j.generated : 0;"
    "        if(j && j.ok && n > 0){ sessionStorage.setItem('s4ScrollY', String(window.scrollY)); window.location.href = '/meal-wizard-step4'; return; }"
    "        if(btn){ btn.disabled = false; btn.textContent = origLabel; }"
    "        var em = (j && j.error) ? String(j.error) : 'Lorenzo could not generate this week - please try again.';"
    "        if(msg){ msg.textContent = em; } })"
    "      .catch(function(){ if(btn){ btn.disabled = false; btn.textContent = origLabel; } if(msg){ msg.textContent = 'Lorenzo could not generate this week - please try again.'; } });"
    "  };"
    "  function s4RestoreScroll(){ var y = sessionStorage.getItem('s4ScrollY'); if(y !== null){ window.scrollTo(0, parseInt(y, 10)); sessionStorage.removeItem('s4ScrollY'); } }"
    "  if(document.readyState === 'loading'){ document.addEventListener('DOMContentLoaded', s4RestoreScroll); } else { s4RestoreScroll(); }"
    "})();"
    "</script>"
)


def _s4_slot_block(date_iso: str, slot_key: str, label: str, entry,
                   suggestion=None) -> str:
    """One slot row. EMPTY (non-prefill by definition — an empty slot has no
    source) gets an entry affordance: meal name (required) + optional ingredients
    + optional main-protein inputs and a 'Keep this meal' button. A CONFIRMED,
    non-prefill meal keeps the G1b-1 display plus a 'Change' button (Change =
    remove for now). A CONFIRMED PREFILL (past) meal is locked: G1b-1 display
    only, NO button. Inputs/buttons are keyed by date::slot via unique ids."""
    label_html = f'<div style="{_S4_SLOT_LABEL}">{escape(label)}</div>'
    key = date_iso + "--" + slot_key
    msg_id = "s4-msg--" + key
    if not isinstance(entry, dict):
        name_id = "s4-name--" + key
        ing_id = "s4-ing--" + key
        prot_id = "s4-prot--" + key
        # onclick value pulled into a variable to avoid nested quotes in the
        # f-string (Rule 2). date_iso is a validated ISO date and slot_key comes
        # from the fixed _S4_SLOT_ORDER allowlist, so both are safe to inline.
        keep_call = "s4Keep('" + date_iso + "','" + slot_key + "')"
        ing_ph = "Ingredients (optional) \u2014 e.g. + chicken nuggets for James"
        # Pre-fill from a Lorenzo draft suggestion when one exists for this slot.
        # Built outside the f-string (Rule 2) and escaped exactly once (Rule 11).
        # name and ingredients go BETWEEN textarea tags (no value= attr) so long
        # text wraps in full; protein stays a single-line input with a
        # double-quoted value= attr, where escape() covering the double-quote
        # prevents attribute breakout.
        name_body = ""
        ing_body = ""
        prot_val = ""
        ing_open = ""
        if isinstance(suggestion, dict):
            # Suggestions now carry the dishes[] shape (older drafts may still be
            # flat); read the lead dish through the migration helper so prefill
            # works for both. Step 4's single-name input maps to the first dish.
            _sug_dishes = slot_dishes(suggestion)
            _sug0 = _sug_dishes[0] if _sug_dishes else {}
            name_body = escape(_sug0.get("name") or "")
            ing_body = escape(_sug0.get("ingredients") or "")
            sug_prot = escape(_sug0.get("protein") or "")
            prot_val = ' value="' + sug_prot + '"'
            # A fresh Lorenzo suggestion: open the ingredients box for review.
            ing_open = " open"
        return (
            f'<div id="s4-row--{key}" style="{_S4_SLOT_ROW}">{label_html}'
            f'<textarea id="{name_id}" rows="2" style="{_S4_NAME_AREA}" '
            f'placeholder="Meal name">{name_body}</textarea>'
            f'<details{ing_open} style="{_S4_DETAILS}">'
            f'<summary style="{_S4_SUMMARY}">Ingredients</summary>'
            f'<textarea id="{ing_id}" rows="2" style="{_S4_NAME_AREA}" '
            f'placeholder="{ing_ph}">{ing_body}</textarea>'
            f'</details>'
            f'<input type="text" id="{prot_id}"{prot_val} style="{_S4_INPUT}" '
            f'placeholder="Main protein (optional)">'
            f'<div><button type="button" style="{_S4_KEEP_BTN}" '
            f'onclick="{keep_call}">Keep this meal</button></div>'
            f'<div id="{msg_id}" style="{_S4_MSG}"></div>'
            f'</div>'
        )
    _entry_dishes = slot_dishes(entry)
    name = escape((_entry_dishes[0].get("name", "") if _entry_dishes else "") or "")
    recipe = escape(_s4_recipe_label(entry))
    source = (entry.get("source") or "").strip().lower()
    tags = []
    if source in _S4_SOURCE_LABELS:
        tags.append(f'<span style="{_S4_TAG}">{escape(_S4_SOURCE_LABELS[source])}</span>')
    if entry.get("skip_shopping"):
        tags.append(f'<span style="{_S4_TAG}">off shopping list</span>')
    tags_html = (f'<div style="{_S4_TAG_ROW}">{"".join(tags)}</div>') if tags else ""
    # Prefill (past) meals are locked: no Change button. Every other confirmed
    # meal gets one.
    if source == "prefill":
        change_html = ""
    else:
        change_call = "s4Change('" + date_iso + "','" + slot_key + "')"
        change_html = (
            f'<div><button type="button" style="{_S4_CHANGE_BTN}" '
            f'onclick="{change_call}">Change</button></div>'
            f'<div id="{msg_id}" style="{_S4_MSG}"></div>'
        )
    return (f'<div id="s4-row--{key}" style="{_S4_SLOT_ROW}">{label_html}'
            f'<div style="{_S4_MEAL_NAME}">{name}</div>'
            f'<div style="{_S4_META}">{recipe}</div>'
            f'{tags_html}{change_html}</div>')


def _s4_day_card(d: date, day_events: list, to_plan, confirmed: dict,
                 suggested: dict) -> str:
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
        slot_key_full = iso + "::" + slot_key
        slot_blocks.append(
            _s4_slot_block(iso, slot_key, slot_label,
                           confirmed.get(slot_key_full),
                           suggested.get(slot_key_full))
        )
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


def _s4_has_lockable(confirmed: dict) -> bool:
    """True when at least one non-prefill confirmed meal sits in a slot that has
    a store home (feast_meal / batch_cook do not count) and its lead dish has a
    name. Drives the 'Set this plan' button vs. the calm hint. Confirmed entries
    are dishes[]-shaped (flat legacy entries migrate on read)."""
    for _ck, _ce in (confirmed or {}).items():
        if not isinstance(_ce, dict):
            continue
        if (_ce.get("source") or "").strip().lower() == "prefill":
            continue
        _cslot = _ck.partition("::")[2]
        if _cslot in _S4_LOCKABLE_SLOTS:
            _cd = slot_dishes(_ce)
            if _cd and (_cd[0].get("name") or "").strip():
                return True
    return False


def _s4_lock_control_html(has_lockable: bool) -> str:
    """The 'Set this plan' control region. Carries a stable id (s4-lock-control)
    so Keep/Change can swap it in place — without a page reload — when
    lock-eligibility flips."""
    if has_lockable:
        inner = (
            f'<button type="button" style="{_S4_LOCK_BTN}" '
            f'onclick="s4Lock()">Set this plan</button>'
            f'<div id="s4-lock-msg" style="{_S4_LOCK_MSG}"></div>'
        )
    else:
        hint = "Confirm at least one meal to set your plan"
        inner = f'<div style="{_S4_LOCK_HINT}">{escape(hint)}</div>'
    return (
        f'<div id="s4-lock-control" style="{_S4_LOCK_WRAP}">'
        f'{inner}'
        f'</div>'
    )


def render_step4_slot_and_lock(date_iso: str, slot_key: str) -> dict:
    """Re-render ONE slot row plus the lock control from the CURRENT session, so
    Keep/Change can patch just that row (and the lock button) in place — no full
    page reload. The session stays the single source of truth: this reuses
    _s4_slot_block / _s4_lock_control_html and never reconstructs markup in JS.
    On a reverted (Change) slot the entry affordance carries any standing Lorenzo
    suggestion, exactly as a full page load would render it."""
    session = load_meal_wizard_session() or {}
    confirmed = session.get("confirmed_meals") or {}
    suggested = session.get("suggested_meals") or {}
    label = dict(_S4_SLOT_ORDER).get(slot_key, slot_key)
    full = date_iso + "::" + slot_key
    slot_html = _s4_slot_block(date_iso, slot_key, label,
                               confirmed.get(full), suggested.get(full))
    lockable = _s4_has_lockable(confirmed)
    return {
        "slot_html": slot_html,
        "lock_html": _s4_lock_control_html(lockable),
        "lockable": lockable,
    }


def render_meal_wizard_step4(user: str, start_iso: str = None) -> str:
    """Step 4 of the Meal Planning Wizard — READ-ONLY. Reads the wizard session
    (planning_window, confirmed_what_to_plan, confirmed_meals) and renders the
    planning week as day cards with their meal slots. Writes nothing. The
    `start_iso` argument mirrors the Step 1 signature; the window always comes
    from the saved session, which is the source of truth for Step 4."""
    session = load_meal_wizard_session() or {}
    _s4_targets = wizard_target_slot_keys(session)
    _s4_target_count = len(_s4_targets)
    window = session.get("planning_window") or {}
    to_plan = session.get("confirmed_what_to_plan") or []
    confirmed = session.get("confirmed_meals") or {}
    suggested = session.get("suggested_meals") or {}
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
            _s4_day_card(d, events_by_date.get(d.isoformat(), []), to_plan,
                         confirmed, suggested)
        )

    # G1 lock state. The banner shows once Lauren has set her plan (revisitable —
    # meals stay editable below it). The "Set this plan" button appears only when
    # at least one non-prefill confirmed meal sits in a slot that has a store home
    # (feast_meal / batch_cook do not count); otherwise a calm hint shows instead.
    locked_at = (session.get("plan_locked_at") or "").strip()
    has_lockable = _s4_has_lockable(confirmed)

    if locked_at:
        banner_text = "Your plan is set \u2014 showing on your homepage for this week."
        banner_html = f'<div style="{_S4_BANNER}">{escape(banner_text)}</div>'
    else:
        banner_html = ""

    lock_html = _s4_lock_control_html(has_lockable)

    nav = (
        f'<div style="{_S4_NAV_ROW}">'
        f'<a href="/meal-wizard-step3" style="{_S4_BACK}">\u2190 Back</a>'
        f'</div>'
    )
    # Draft generator: kicks off /meal-wizard-generate (G1c-1b) then reloads so the
    # empty slots come back pre-filled with Lorenzo's editable suggestions (Rule 16
    # \u2014 a draft to edit, never auto-confirmed).
    _s4_btn_label = "Generate my week with Lorenzo"
    if _s4_target_count > _WIZARD_GEN_SLOT_CAP:
        _s4_gen_line = (
            "Too many meals selected (" + escape(str(_s4_target_count)) +
            ") \u2014 Lorenzo plans best a couple of meal types at a time. "
            "Go back to Step 3 and select fewer, or shorten the window.")
        generate_html = (
            f'<div style="{_S4_LOCK_WRAP}">'
            f'<button type="button" id="s4-gen-btn" disabled '
            f'style="{_S4_LOCK_BTN};opacity:0.5;cursor:not-allowed" '
            f'onclick="s4Generate(this)">{_s4_btn_label}</button>'
            f'<div id="s4-gen-msg" style="{_S4_LOCK_MSG}">{_s4_gen_line}</div>'
            f'</div>'
        )
    elif _s4_target_count > 0:
        _s4_gen_line = "Will generate " + escape(str(_s4_target_count)) + " meal(s)."
        generate_html = (
            f'<div style="{_S4_LOCK_WRAP}">'
            f'<button type="button" id="s4-gen-btn" style="{_S4_LOCK_BTN}" '
            f'onclick="s4Generate(this)">{_s4_btn_label}</button>'
            f'<div id="s4-gen-msg" style="{_S4_LOCK_MSG}">{_s4_gen_line}</div>'
            f'</div>'
        )
    else:
        generate_html = (
            f'<div style="{_S4_LOCK_WRAP}">'
            f'<button type="button" id="s4-gen-btn" style="{_S4_LOCK_BTN}" '
            f'onclick="s4Generate(this)">{_s4_btn_label}</button>'
            f'<div id="s4-gen-msg" style="{_S4_LOCK_MSG}"></div>'
            f'</div>'
        )
    inner = (
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin:0 0 2px;">{_S4_TITLE}</h1>'
        f'<p style="{_S4_SUBTITLE}">Step 4 of 6 \u2014 Build the menu</p>'
        f'{banner_html}'
        f'{generate_html}'
        f'{"".join(day_cards)}'
        f'{lock_html}'
        f'{nav}'
    )
    body = (
        f'<div style="max-width:680px;margin:0 auto;padding:24px 16px 96px;">'
        f'{inner}'
        f'</div>'
        f'{_S4_JS}'
    )
    return html_page(_S4_TITLE, body)
