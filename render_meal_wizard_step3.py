"""
render_meal_wizard_step3.py — Meal Planning Wizard, Step 3.

"What are we planning this week" — meal-type selection, complexity, the
planning window, and pre-fill of any past days inside the window. Split out of
render_meal_wizard.py to keep that file under 800 lines (claud.md change
discipline); render_meal_wizard re-exports render_meal_wizard_step3 so the
public surface stays "in render_meal_wizard".

All data access goes through data_helpers (Rule 19); file chrome comes from
ui_helpers.html_page. Inline JS lives in a plain (non-f) string so no
backslash-n is ever needed inside an f-string (Rules 7 & 12).
"""
from datetime import date, timedelta
from html import escape
from ui_helpers import html_page
from data_helpers import load_meal_wizard_session
from render_liturgical import get_day_info
from render_meals import load_meal_rules

_HEADING_FONT = "'Cormorant Garamond', serif"

# Canonical meal-type options: (key, label, prefill_eligible). Snacks and
# dessert are FLAGS ONLY here (no per-day content) so they are not prefill
# eligible. Feast meal and batch cook are appended conditionally below.
_S3_BASE_OPTIONS = [
    ("breakfast", "Breakfast", True),
    ("lunch", "Lunch", True),
    ("dinner", "Dinner", True),
    ("johns_lunch", "John\u2019s lunch", True),
    ("snacks", "Snacks", False),
    ("dessert", "Dessert", False),
]
_S3_FEAST_OPTION = ("feast_meal", "Feast meal", False)
_S3_BATCH_OPTION = ("batch_cook", "Batch cook (Sunday)", False)

_S3_COMPLEXITY = [
    ("full_effort", "Full effort"),
    ("normal", "Normal"),
    ("simple", "Simple"),
]

# First-run defaults (no saved selection yet). Minor, sensible default: the
# three core meals; everything else is opt-in.
_S3_DEFAULT_PLAN = {"breakfast", "lunch", "dinner"}

# Display labels for the saved-confirmation view (key -> label).
_S3_LABELS = {
    "breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner",
    "johns_lunch": "John\u2019s lunch", "snacks": "Snacks",
    "dessert": "Dessert", "feast_meal": "Feast meal",
    "batch_cook": "Batch cook (Sunday)",
}
_S3_CX_LABELS = {"full_effort": "Full effort", "normal": "Normal", "simple": "Simple"}

# ── Style constants (pulled out of f-strings: Rules 1 & 2) ───────────────────
_S3_SUBTITLE = "color:var(--ink-muted);font-size:0.95em;margin:2px 0 22px;"
_S3_BOX = ("background:var(--warm-white,#fff);border:1px solid var(--border,#e6e0d4);"
           "border-radius:var(--radius-md,12px);padding:14px 16px;margin-bottom:14px;")
_S3_TITLE = ("font-family:" + _HEADING_FONT + ";font-size:1.15em;font-weight:600;"
             "color:var(--ink);margin:0 0 10px;")
_S3_HINT = "color:var(--ink-muted);font-size:0.9em;line-height:1.5;margin:0 0 12px;"
_S3_ITEM_LABEL = ("display:inline-flex;align-items:center;gap:8px;background:var(--parchment,#faf6ec);"
                  "border:1px solid var(--border-light,#ece6d8);border-radius:999px;"
                  "padding:6px 12px;margin:0 8px 8px 0;font-size:0.92em;color:var(--ink);"
                  "cursor:pointer;")
_S3_CX_BTN = ("flex:1;min-width:110px;padding:13px 10px;border:1px solid var(--border,#e6e0d4);"
              "border-radius:var(--radius-sm,8px);color:var(--ink);font-weight:600;"
              "font-size:0.98em;cursor:pointer;text-align:center;")
_S3_WIN_LABEL = ("display:flex;flex-direction:column;gap:6px;font-size:0.9em;"
                 "color:var(--ink-muted);font-weight:600;")
_S3_DATE_INPUT = ("padding:10px 12px;border:1px solid var(--border,#e6e0d4);"
                  "border-radius:var(--radius-sm,8px);font-size:0.95em;color:var(--ink);")
_S3_SAVE_BTN = ("display:block;width:100%;box-sizing:border-box;margin-top:8px;"
                "padding:15px 18px;border:none;border-radius:var(--radius-md,12px);"
                "background:var(--gold-mid,#c9a84a);color:var(--ink);font-weight:700;"
                "font-size:1.05em;cursor:pointer;")
_S3_STATUS = "color:var(--accent-red,#c0392b);font-size:0.9em;margin:8px 0 0;min-height:1.2em;"
_S3_NAV_ROW = "display:flex;justify-content:flex-start;align-items:center;margin-top:18px;"
_S3_BACK = "color:var(--ink-muted);font-size:0.95em;text-decoration:none;"
_S3_PF_CARD = ("border-top:1px solid var(--border-light,#ece6d8);padding:12px 0 4px;")
_S3_PF_H = "font-weight:600;color:var(--ink);margin:0 0 8px;font-size:0.98em;"
_S3_PF_ROW = "display:flex;align-items:center;gap:10px;margin:0 0 8px;"
_S3_PF_LAB = "min-width:90px;color:var(--ink-muted);font-size:0.9em;"
_S3_PF_INPUT = ("flex:1;padding:9px 12px;border:1px solid var(--border,#e6e0d4);"
                "border-radius:var(--radius-sm,8px);font-size:0.95em;color:var(--ink);")
_S3_SUMMARY_BOX = ("background:var(--parchment,#faf6ec);border:1px solid var(--border-light,#ece6d8);"
                   "border-radius:var(--radius-md,12px);padding:16px 18px;margin-bottom:14px;")
_S3_SUMMARY_ROW = "color:var(--ink);font-size:0.98em;margin:0 0 8px;line-height:1.5;"
_S3_LINK_BTN = ("display:block;width:100%;box-sizing:border-box;margin-top:10px;"
                "padding:14px 18px;border-radius:var(--radius-md,12px);"
                "background:var(--gold-mid,#c9a84a);color:var(--ink);font-weight:700;"
                "font-size:1.02em;text-align:center;text-decoration:none;")
_S3_LINK_GHOST = ("display:block;width:100%;box-sizing:border-box;margin-top:10px;"
                  "padding:13px 18px;border:1px solid var(--border,#e6e0d4);"
                  "border-radius:var(--radius-md,12px);background:var(--warm-white,#fff);"
                  "color:var(--ink);font-weight:600;font-size:0.98em;text-align:center;"
                  "text-decoration:none;")

# Inline JS kept in a plain (non-f) string: literal braces, no backslash-n,
# no nested-quote conflict (Rules 1, 2, 7, 12). DOM is built with createElement.
_S3_JS = (
    "<script>"
    "(function(){"
    "  function byId(id){ return document.getElementById(id); }"
    "  window.s3SelectComplexity = function(key){"
    "    var h = byId('s3-complexity'); if(h){ h.value = key; }"
    "    var btns = document.querySelectorAll('.s3-cx');"
    "    for(var i=0;i<btns.length;i++){"
    "      var b = btns[i];"
    "      if(b.getAttribute('data-key') === key){"
    "        b.style.background = 'var(--gold-mid,#c9a84a)';"
    "        b.setAttribute('aria-pressed','true');"
    "      } else {"
    "        b.style.background = 'var(--warm-white,#fff)';"
    "        b.setAttribute('aria-pressed','false');"
    "      }"
    "    }"
    "  };"
    "  function parseISO(s){ var p = (s||'').split('-'); if(p.length !== 3){ return null; }"
    "    return new Date(parseInt(p[0],10), parseInt(p[1],10)-1, parseInt(p[2],10)); }"
    "  function toISO(d){ var m = d.getMonth()+1; var day = d.getDate();"
    "    var mm = (m<10?'0':'')+m; var dd = (day<10?'0':'')+day;"
    "    return d.getFullYear()+'-'+mm+'-'+dd; }"
    "  function fmt(d){ try { return d.toLocaleDateString(undefined,"
    "    {weekday:'long', month:'long', day:'numeric'}); } catch(e){ return toISO(d); } }"
    "  window.s3RebuildPrefill = function(){"
    "    var wrap = byId('s3-prefill'); if(!wrap){ return; }"
    "    var host = byId('s3-prefill-days'); if(!host){ return; }"
    "    host.innerHTML = '';"
    "    var today = parseISO(wrap.getAttribute('data-today'));"
    "    var start = parseISO(byId('s3-start').value);"
    "    var end = parseISO(byId('s3-end').value);"
    "    if(!start || !today){ wrap.style.display='none'; return; }"
    "    var dayBeforeToday = new Date(today.getTime() - 86400000);"
    "    var lastEnd = (end && end < dayBeforeToday) ? end : dayBeforeToday;"
    "    var slots = [];"
    "    var checks = document.querySelectorAll('.mt-check');"
    "    for(var i=0;i<checks.length;i++){ var c = checks[i];"
    "      if(c.checked && c.getAttribute('data-prefill')==='1'){"
    "        slots.push({key:c.value, label:c.getAttribute('data-label')||c.value}); } }"
    "    var any = false;"
    "    var cur = new Date(start.getTime());"
    "    var guard = 0;"
    "    while(cur <= lastEnd && guard < 60){"
    "      guard++; any = true;"
    "      var dISO = toISO(cur);"
    "      var card = document.createElement('div'); card.className='s3-pf-card';"
    "      var h = document.createElement('div'); h.className='s3-pf-h';"
    "      h.textContent = fmt(cur); card.appendChild(h);"
    "      for(var j=0;j<slots.length;j++){"
    "        var row = document.createElement('div'); row.className='s3-pf-row';"
    "        var lab = document.createElement('span'); lab.className='s3-pf-lab';"
    "        lab.textContent = slots[j].label; row.appendChild(lab);"
    "        var inp = document.createElement('input'); inp.type='text';"
    "        inp.className='pf-input'; inp.placeholder='What did you make?';"
    "        inp.setAttribute('data-date', dISO); inp.setAttribute('data-slot', slots[j].key);"
    "        row.appendChild(inp); card.appendChild(row); }"
    "      host.appendChild(card);"
    "      cur = new Date(cur.getTime() + 86400000); }"
    "    wrap.style.display = (any && slots.length) ? 'block' : 'none';"
    "  };"
    "  window.s3Save = function(){"
    "    var status = byId('s3-status'); if(status){ status.textContent = ''; }"
    "    var wtp = [];"
    "    var checks = document.querySelectorAll('.mt-check');"
    "    for(var i=0;i<checks.length;i++){ if(checks[i].checked){ wtp.push(checks[i].value); } }"
    "    var cx = byId('s3-complexity') ? byId('s3-complexity').value : '';"
    "    var win = { start_iso: byId('s3-start').value, end_iso: byId('s3-end').value };"
    "    var prefill = {};"
    "    var inputs = document.querySelectorAll('.pf-input');"
    "    for(var k=0;k<inputs.length;k++){ var v = (inputs[k].value||'').trim();"
    "      if(v){ prefill[inputs[k].getAttribute('data-date')+'::'+inputs[k].getAttribute('data-slot')] = v; } }"
    "    var payload = { what_to_plan: wtp, complexity: cx, planning_window: win, prefill: prefill };"
    "    fetch('/meal-wizard-step3-save', { method:'POST',"
    "      headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) })"
    "      .then(function(r){ return r.json(); })"
    "      .then(function(j){ if(j && j.ok){ sessionStorage.setItem('s3ScrollY', String(window.scrollY)); window.location.href = '/meal-wizard-step3?saved=1'; }"
    "        else if(status){ status.textContent = 'Could not save. Please try again.'; } })"
    "      .catch(function(){ if(status){ status.textContent = 'Could not save. Please try again.'; } });"
    "  };"
    "  document.addEventListener('DOMContentLoaded', function(){"
    "    var s = byId('s3-start'); var e = byId('s3-end');"
    "    if(s){ s.addEventListener('change', window.s3RebuildPrefill); }"
    "    if(e){ e.addEventListener('change', window.s3RebuildPrefill); }"
    "    var cx = document.querySelectorAll('.s3-cx');"
    "    for(var c=0;c<cx.length;c++){ cx[c].addEventListener('click', function(){"
    "      window.s3SelectComplexity(this.getAttribute('data-key')); }); }"
    "    var checks = document.querySelectorAll('.mt-check');"
    "    for(var i=0;i<checks.length;i++){ checks[i].addEventListener('change', window.s3RebuildPrefill); }"
    "    window.s3RebuildPrefill();"
    "  });"
    "  function s3RestoreScroll(){ var y = sessionStorage.getItem('s3ScrollY'); if(y !== null){ window.scrollTo(0, parseInt(y, 10)); sessionStorage.removeItem('s3ScrollY'); } }"
    "  if(document.readyState === 'loading'){ document.addEventListener('DOMContentLoaded', s3RestoreScroll); } else { s3RestoreScroll(); }"
    "})();"
    "</script>"
)


def _default_window():
    """Default planning window: today through the upcoming Saturday. If today
    is Saturday, span a full week so the window is never a single day."""
    today = date.today()
    days_ahead = (5 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today.isoformat(), (today + timedelta(days=days_ahead)).isoformat()


def _feast_in_window(start_iso, end_iso):
    """True if any day in [start, end] carries a liturgical feast name."""
    try:
        start_d = date.fromisoformat(start_iso)
        end_d = date.fromisoformat(end_iso)
    except (ValueError, TypeError):
        return False
    if end_d < start_d:
        start_d, end_d = end_d, start_d
    span = (end_d - start_d).days
    if span > 60:
        span = 60
    for offset in range(span + 1):
        d = start_d + timedelta(days=offset)
        try:
            if (get_day_info(d).get("feast_name") or "").strip():
                return True
        except Exception:
            continue
    return False


def _has_sunday_batch():
    """True if any meal rule mentions batch cooking (a Sunday batch rule)."""
    raw = load_meal_rules()
    rules = raw if isinstance(raw, list) else []
    for r in rules:
        if isinstance(r, dict) and "batch" in (r.get("rule", "") or "").lower():
            return True
    return False


def _meal_type_options(feast, batch):
    options = list(_S3_BASE_OPTIONS)
    if feast:
        options.append(_S3_FEAST_OPTION)
    if batch:
        options.append(_S3_BATCH_OPTION)
    return options


def _mt_checkbox(key, label, prefill, checked):
    ev_key = escape(key)
    ev_label = escape(label)
    pf = "1" if prefill else "0"
    ck = " checked" if checked else ""
    return (
        f'<label style="{_S3_ITEM_LABEL}">'
        f'<input type="checkbox" class="mt-check" value="{ev_key}" '
        f'data-prefill="{pf}" data-label="{ev_label}"{ck}> {ev_label}'
        f'</label>'
    )


def _cx_button(key, label, current):
    ev = escape(key)
    on = (key == current)
    bg = "var(--gold-mid,#c9a84a)" if on else "var(--warm-white,#fff)"
    pressed = "true" if on else "false"
    return (
        f'<button type="button" class="s3-cx" data-key="{ev}" aria-pressed="{pressed}" '
        f'style="{_S3_CX_BTN}background:{bg};">{escape(label)}</button>'
    )


def _build_form(user):
    session = load_meal_wizard_session() or {}

    start_iso, end_iso = _default_window()
    win = session.get("planning_window") or {}
    saved_start = win.get("start_iso")
    saved_end = win.get("end_iso")
    if saved_start:
        try:
            date.fromisoformat(saved_start)
            start_iso = saved_start
        except (ValueError, TypeError):
            pass
    if saved_end:
        try:
            date.fromisoformat(saved_end)
            end_iso = saved_end
        except (ValueError, TypeError):
            pass

    feast = _feast_in_window(start_iso, end_iso)
    batch = _has_sunday_batch()
    options = _meal_type_options(feast, batch)

    if "confirmed_what_to_plan" in session:
        selected = set(session.get("confirmed_what_to_plan") or [])
    else:
        selected = set(_S3_DEFAULT_PLAN)

    current_cx = session.get("confirmed_complexity") or "normal"
    today_iso = date.today().isoformat()

    checkboxes = "".join(
        _mt_checkbox(k, lbl, pf, k in selected) for (k, lbl, pf) in options
    )
    meal_types_box = (
        f'<div style="{_S3_BOX}">'
        f'<h3 style="{_S3_TITLE}">What are we planning?</h3>'
        f'<div>{checkboxes}</div>'
        f'</div>'
    )

    cx_buttons = "".join(_cx_button(k, lbl, current_cx) for (k, lbl) in _S3_COMPLEXITY)
    complexity_box = (
        f'<div style="{_S3_BOX}">'
        f'<h3 style="{_S3_TITLE}">How much effort this week?</h3>'
        f'<input type="hidden" id="s3-complexity" value="{escape(current_cx)}">'
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;">{cx_buttons}</div>'
        f'</div>'
    )

    window_box = (
        f'<div style="{_S3_BOX}">'
        f'<h3 style="{_S3_TITLE}">Planning window</h3>'
        f'<div style="display:flex;gap:14px;flex-wrap:wrap;">'
        f'<label style="{_S3_WIN_LABEL}">Start'
        f'<input type="date" id="s3-start" value="{escape(start_iso)}" style="{_S3_DATE_INPUT}"></label>'
        f'<label style="{_S3_WIN_LABEL}">End'
        f'<input type="date" id="s3-end" value="{escape(end_iso)}" style="{_S3_DATE_INPUT}"></label>'
        f'</div>'
        f'</div>'
    )

    prefill_hint = ("For any day before today in your window, type what you actually "
                    "made. These get locked in, stay off your grocery list, and never "
                    "turn into recipe cards \u2014 you can still pull a recipe later if "
                    "you want one.")
    prefill_box = (
        f'<div id="s3-prefill" data-today="{escape(today_iso)}" '
        f'style="display:none;{_S3_BOX}">'
        f'<h3 style="{_S3_TITLE}">Already eaten this window?</h3>'
        f'<p style="{_S3_HINT}">{escape(prefill_hint)}</p>'
        f'<div id="s3-prefill-days"></div>'
        f'</div>'
    )

    save_block = (
        f'<button type="button" id="s3-save-btn" onclick="s3Save()" '
        f'style="{_S3_SAVE_BTN}">Save and continue</button>'
        f'<p id="s3-status" style="{_S3_STATUS}"></p>'
    )

    nav = (
        f'<div style="{_S3_NAV_ROW}">'
        f'<a href="/meal-wizard-step2" style="{_S3_BACK}">\u2190 Back</a>'
        f'</div>'
    )

    inner = (
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin:0 0 2px;">Plan This Week\u2019s Meals</h1>'
        f'<p style="{_S3_SUBTITLE}">Step 3 of 6 \u2014 What are we planning this week</p>'
        f'{meal_types_box}{complexity_box}{window_box}{prefill_box}{save_block}{nav}'
    )
    body = (
        f'<div style="max-width:680px;margin:0 auto;padding:24px 16px 96px;">'
        f'{inner}'
        f'</div>'
        f'{_S3_JS}'
    )
    return body


def _saved_confirmation_body(user):
    session = load_meal_wizard_session() or {}
    plan = session.get("confirmed_what_to_plan") or []
    plan_labels = [_S3_LABELS.get(k, k) for k in plan]
    plan_text = ", ".join(plan_labels) if plan_labels else "Nothing selected yet"

    cx = session.get("confirmed_complexity") or ""
    cx_text = _S3_CX_LABELS.get(cx, "Not set")

    win = session.get("planning_window") or {}
    start_iso = win.get("start_iso") or "?"
    end_iso = win.get("end_iso") or "?"
    win_text = f"{start_iso} to {end_iso}"

    meals = session.get("confirmed_meals") or {}
    prefill_count = sum(
        1 for v in meals.values()
        if isinstance(v, dict) and v.get("source") == "prefill"
    )
    if prefill_count == 1:
        prefill_text = "1 past meal pre-filled (locked, off the grocery list)"
    elif prefill_count:
        prefill_text = (f"{prefill_count} past meals pre-filled "
                        "(locked, off the grocery list)")
    else:
        prefill_text = "No past meals pre-filled"

    summary = (
        f'<div style="{_S3_SUMMARY_BOX}">'
        f'<p style="{_S3_SUMMARY_ROW}"><strong>Planning:</strong> {escape(plan_text)}</p>'
        f'<p style="{_S3_SUMMARY_ROW}"><strong>Effort:</strong> {escape(cx_text)}</p>'
        f'<p style="{_S3_SUMMARY_ROW}"><strong>Window:</strong> {escape(win_text)}</p>'
        f'<p style="{_S3_SUMMARY_ROW}">{escape(prefill_text)}</p>'
        f'</div>'
    )

    note = ("Saved. You can come back and adjust any of this before the rest of the "
            "week is planned.")
    inner = (
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin:0 0 2px;">Saved \u2713</h1>'
        f'<p style="{_S3_SUBTITLE}">Step 3 of 6 \u2014 What are we planning this week</p>'
        f'<p style="{_S3_HINT}">{escape(note)}</p>'
        f'{summary}'
        f'<a href="/meal-wizard-step3" style="{_S3_LINK_GHOST}">Edit these choices</a>'
        f'<a href="/meal-wizard-step4" style="{_S3_LINK_BTN}">Continue to Step 4</a>'
        f'<a href="/meal-wizard" style="{_S3_LINK_GHOST}">Back to the wizard</a>'
    )
    body = (
        f'<div style="max-width:680px;margin:0 auto;padding:24px 16px 96px;">'
        f'{inner}'
        f'</div>'
    )
    return body


def render_meal_wizard_step3(user: str, saved: bool = False) -> str:
    """Step 3 of the Meal Planning Wizard. When `saved` is True, render the
    saved-confirmation view instead of the editable form."""
    body = _saved_confirmation_body(user) if saved else _build_form(user)
    return html_page("Plan This Week\u2019s Meals", body)
