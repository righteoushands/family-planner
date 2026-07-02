"""
render_meal_wizard_step5.py — Meal Planning Wizard, Step 5 (shopping day).

Phase H1 (skeleton): this screen does exactly ONE thing — pick and save the
shopping day. A seven-button day picker (Monday through Sunday) shows the
session's confirmed_shopping_day as selected when already set. Tapping a day
POSTs {"day": "<DayName>"} to /meal-wizard-step5-save via fetch() and swaps the
selected state in place — no full page reload (matching the async s4Keep /
s4Change pattern in render_meal_wizard_step4.py, so Rule 20 scroll-restore is
not needed). OUT OF SCOPE for H1 (future Phase H builds, Rule 17): conflict
detection UI, the John's-note field, and any "Continue" button.

All data access goes through data_helpers (Rule 19); page chrome comes from
ui_helpers.html_page. The inline JS is built as CONCATENATED STRING LITERALS
(not an f-string) like Step 4's _S4_JS, so there are no Python-side brace or
quote conflicts (Rules 1, 2) and no backslash-n ever appears inside a JS string
(Rules 7, 12).
"""
from html import escape
from ui_helpers import html_page
from data_helpers import load_meal_wizard_session

_HEADING_FONT = "'Cormorant Garamond', serif"

_S5_TITLE = "Pick Your Shopping Day"

# Canonical day order — also the server-side allowlist mirror (app.py validates
# against the same seven names before persisting).
_S5_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
            "Sunday"]

# ── Style constants (pulled out of f-strings: Rules 1 & 2; mirror Step 4) ─────
_S5_SUBTITLE = "color:var(--ink-muted);font-size:0.95em;margin:2px 0 22px;"
_S5_CARD = ("background:var(--warm-white,#fff);border:1px solid var(--border,#e6e0d4);"
            "border-radius:var(--radius-md,12px);padding:18px 20px;margin-bottom:14px;")
_S5_HINT = "color:var(--ink);font-size:0.98em;line-height:1.5;margin:0 0 14px;"
_S5_DAY_WRAP = "display:flex;flex-direction:column;gap:8px;"
_S5_DAY_BTN = ("display:block;width:100%;text-align:left;padding:12px 16px;"
               "border:1px solid var(--border,#e6e0d4);"
               "border-radius:var(--radius-md,12px);"
               "background:var(--warm-white,#fff);color:var(--ink);"
               "font-size:1em;cursor:pointer;")
_S5_DAY_BTN_SEL = ("display:block;width:100%;text-align:left;padding:12px 16px;"
                   "border:1px solid var(--gold-mid,#c9a84a);"
                   "border-radius:var(--radius-md,12px);"
                   "background:var(--gold-mid,#c9a84a);color:var(--ink);"
                   "font-size:1em;font-weight:700;cursor:pointer;")
_S5_MSG = "color:var(--ink-muted);font-size:0.9em;margin-top:10px;min-height:1em;"
_S5_NAV_ROW = "display:flex;justify-content:flex-start;align-items:center;margin-top:18px;"
_S5_BACK = "color:var(--ink-muted);font-size:0.95em;text-decoration:none;"

# H1 inline JS — CONCATENATED STRING LITERALS (not an f-string), matching Step
# 4's _S4_JS. On success the picker swaps the selected button style in place
# (no reload). The two style strings are injected below by plain string
# concatenation; they contain no quotes, so the single-quoted JS literals stay
# valid (Rules 1, 2, 7, 12).
_S5_JS = (
    "<script>"
    "(function(){"
    "  var DAYS = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];"
    "  var STYLE_SEL = '" + _S5_DAY_BTN_SEL + "';"
    "  var STYLE_UNSEL = '" + _S5_DAY_BTN + "';"
    "  function elById(id){ return document.getElementById(id); }"
    "  window.s5Pick = function(day){"
    "    var msg = elById('s5-msg');"
    "    if(msg){ msg.textContent = ''; }"
    "    fetch('/meal-wizard-step5-save', { method:'POST',"
    "      headers:{'Content-Type':'application/json'}, body: JSON.stringify({ day: day }) })"
    "      .then(function(r){ return r.json(); })"
    "      .then(function(j){ if(j && j.ok){"
    "          for(var i = 0; i < DAYS.length; i++){"
    "            var b = elById('s5-day--' + DAYS[i]);"
    "            if(b){ b.style.cssText = (DAYS[i] === day ? STYLE_SEL : STYLE_UNSEL);"
    "                   b.setAttribute('aria-pressed', DAYS[i] === day ? 'true' : 'false'); }"
    "          }"
    "          if(msg){ msg.textContent = 'Shopping day saved: ' + day; }"
    "        } else { if(msg){ msg.textContent = 'Could not save. Please try again.'; } } })"
    "      .catch(function(){ if(msg){ msg.textContent = 'Could not save. Please try again.'; } });"
    "  };"
    "})();"
    "</script>"
)


def render_step5(user: str) -> str:
    """Step 5 of the Meal Planning Wizard — shopping day picker (H1 skeleton).
    Reads confirmed_shopping_day from the wizard session to mark the current
    selection; writes nothing (the save happens via /meal-wizard-step5-save)."""
    session = load_meal_wizard_session() or {}
    current = (session.get("confirmed_shopping_day") or "").strip()

    day_buttons = []
    for day in _S5_DAYS:
        selected = (day == current)
        style = _S5_DAY_BTN_SEL if selected else _S5_DAY_BTN
        pressed = "true" if selected else "false"
        day_buttons.append(
            f'<button type="button" id="s5-day--{day}" style="{style}" '
            f'aria-pressed="{pressed}" '
            f'onclick="s5Pick(\u0027{day}\u0027)">{escape(day)}</button>'
        )

    hint = "Which day do you usually shop? One tap saves it \u2014 you can change it any time."
    picker = (
        f'<div style="{_S5_CARD}">'
        f'<p style="{_S5_HINT}">{escape(hint)}</p>'
        f'<div style="{_S5_DAY_WRAP}">'
        f'{"".join(day_buttons)}'
        f'</div>'
        f'<div id="s5-msg" style="{_S5_MSG}"></div>'
        f'</div>'
    )

    nav = (
        f'<div style="{_S5_NAV_ROW}">'
        f'<a href="/meal-wizard-step4" style="{_S5_BACK}">\u2190 Back to your menu</a>'
        f'</div>'
    )

    inner = (
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin:0 0 2px;">{_S5_TITLE}</h1>'
        f'<p style="{_S5_SUBTITLE}">Step 5 of 6 \u2014 Shopping day</p>'
        f'{picker}'
        f'{nav}'
    )
    body = (
        f'<div style="max-width:680px;margin:0 auto;padding:24px 16px 96px;">'
        f'{inner}'
        f'</div>'
        f'{_S5_JS}'
    )
    return html_page(_S5_TITLE, body)
