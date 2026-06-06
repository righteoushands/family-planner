"""
render_meal_wizard.py — Meal Planning Wizard pages.

Phase C, Part 1: the Pantry Staples page only. More wizard steps are added
in later phases. All data access goes through data_helpers (Rule 19); all
file chrome comes from ui_helpers.html_page (matches render_wizards.py).
"""
from html import escape
from ui_helpers import html_page
from data_helpers import load_pantry_staples

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
