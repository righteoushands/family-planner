"""
render_wizards.py — Renders the Wizards hub page at /wizards.

A static list of family wizards shown as tappable cards. Only the Meal
Planning Wizard and the Rule of Life Wizard are launchable today; the rest
display a "Coming Soon" badge and are not tappable. No data is read here.
"""
from html import escape
from ui_helpers import html_page

# Heading font pulled out of the f-string to avoid nested quotes (Rule 2)
# and backslash escapes (Rule 1).
_HEADING_FONT = "'Cormorant Garamond', serif"
_WAND = "&#129668;"  # 🪄

# Order matters — displayed top to bottom exactly as listed.
_WIZARDS = [
    {"name": "Meal Planning Wizard",
     "desc": "Plan the week's meals with Lorenzo",
     "status": "active", "href": "/meal-wizard"},
    {"name": "Rule of Life Wizard",
     "desc": "Build your family's daily rhythm",
     "status": "active", "href": "/frol-wizard"},
    {"name": "Plan My Day Wizard",
     "desc": "Plan your day, step by step",
     "status": "soon", "href": ""},
    {"name": "Weekly Planning Wizard",
     "desc": "Plan the week ahead",
     "status": "soon", "href": ""},
    {"name": "End of Day Debrief",
     "desc": "Close out the day",
     "status": "soon", "href": ""},
    {"name": "School Year Setup",
     "desc": "Set up the new school year",
     "status": "soon", "href": ""},
    {"name": "Event Planning Wizard",
     "desc": "Plan a feast day or gathering",
     "status": "soon", "href": ""},
]


def _active_card(name: str, desc: str, href: str) -> str:
    """A tappable wizard card linking to its launch route."""
    return (
        f'<a href="{href}" '
        f'style="display:flex;align-items:center;gap:14px;text-decoration:none;'
        f'background:var(--warm-white);border:1px solid var(--border);'
        f'border-radius:var(--radius-md);padding:16px 18px;margin-bottom:14px;'
        f'box-shadow:var(--shadow-sm);">'
        f'<span style="font-size:1.8em;flex-shrink:0;line-height:1;">{_WAND}</span>'
        f'<span style="flex:1;min-width:0;">'
        f'<span style="display:block;font-weight:600;color:var(--ink);font-size:1.05em;">{name}</span>'
        f'<span style="display:block;color:var(--ink-muted);font-size:0.88em;margin-top:2px;">{desc}</span>'
        f'</span>'
        f'<span style="flex-shrink:0;background:var(--gold-mid);color:var(--ink);'
        f'font-weight:600;font-size:0.82em;padding:8px 16px;border-radius:var(--radius-sm);">Launch</span>'
        f'</a>'
    )


def _soon_card(name: str, desc: str) -> str:
    """A greyed-out, non-tappable card with a Coming Soon badge."""
    return (
        f'<div style="display:flex;align-items:center;gap:14px;'
        f'background:var(--parchment);border:1px solid var(--border-light);'
        f'border-radius:var(--radius-md);padding:16px 18px;margin-bottom:14px;opacity:0.6;">'
        f'<span style="font-size:1.8em;flex-shrink:0;line-height:1;filter:grayscale(1);">{_WAND}</span>'
        f'<span style="flex:1;min-width:0;">'
        f'<span style="display:block;font-weight:600;color:var(--ink-muted);font-size:1.05em;">{name}</span>'
        f'<span style="display:block;color:var(--ink-faint);font-size:0.88em;margin-top:2px;">{desc}</span>'
        f'</span>'
        f'<span style="flex-shrink:0;background:var(--border);color:var(--ink-muted);'
        f'font-weight:600;font-size:0.72em;padding:6px 12px;border-radius:var(--radius-sm);'
        f'text-transform:uppercase;letter-spacing:0.05em;white-space:nowrap;">Coming Soon</span>'
        f'</div>'
    )


def _wizard_card(w: dict) -> str:
    name = escape(w["name"])
    desc = escape(w["desc"])
    if w["status"] == "active":
        return _active_card(name, desc, escape(w["href"]))
    return _soon_card(name, desc)


def render_wizards_page(user: str) -> str:
    """Render the static Wizards hub page wrapped in standard page chrome."""
    cards = "\n".join(_wizard_card(w) for w in _WIZARDS)
    body = (
        f'<div style="max-width:640px;margin:0 auto;padding:24px 16px 96px;">'
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin-bottom:4px;">Wizards</h1>'
        f'<p style="color:var(--ink-muted);font-size:0.95em;margin-bottom:24px;">'
        f'Step-by-step helpers for planning family life.</p>'
        f'{cards}'
        f'</div>'
    )
    return html_page("Wizards", body)
