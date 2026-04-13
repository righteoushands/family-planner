"""
render_mom_profile.py — Mom's personal profile page

Her own space — not just a planning hub, but a record of
who she is, what she loves, and what she's dreaming about.

Stores:
  - Clothing & shoe sizes
  - Birthday
  - Gift ideas (the things she never asks for)
  - Favorite foods & restaurants
  - Just for me (self-care, hobbies, interests)
  - Dream trips
  - Bucket list
  - Notes for John
  - Other notes
"""
import json, os
from html import escape
from ui_helpers import html_page, top_nav

MOM_PROFILE_PATH = "data/profiles/mom.json"

CLOTHING_FIELDS = [
    ("shirt",     "Top / Shirt"),
    ("pants",     "Pants"),
    ("dress",     "Dress / Skirt"),
    ("jacket",    "Jacket"),
    ("underwear", "Underwear"),
    ("socks",     "Socks"),
]

LIST_SECTIONS = [
    ("gift_ideas",          "Gift Ideas",            "The things you'd love but never ask for"),
    ("favorite_foods",      "Favorite Foods",        "What you love to eat"),
    ("favorite_restaurants","Favorite Restaurants",  "Places you enjoy going out"),
    ("just_for_me",         "Just for Me",           "Self-care, hobbies, interests — things that fill your cup"),
    ("dream_trips",         "Dream Trips",           "Places you want to go someday"),
    ("bucket_list",         "Bucket List",           "Experiences and adventures you're hoping for"),
]

from config import parent_color as _parent_color
from render_settings import _section_cycle
ACCENT       = _parent_color("Lauren", "bg")
ACCENT_LIGHT = _parent_color("Lauren", "light")


def _cycle_fertility_banner(iso: str = "") -> str:
    """Return an HTML warning banner for Lauren's fertility/cycle status.

    Shows:
      • Days 10–19 of her cycle → Ovulation Window warning (prominent red-rose)
      • ~4 days before period    → Period Approaching warning (amber)
      • Otherwise               → empty string
    """
    try:
        from render_lucy import _get_cycle_context
        from datetime import date as _d
        _iso = iso or _d.today().isoformat()
        cc = _get_cycle_context(_iso)
        if not cc:
            return ""
        day     = cc.get("cycle_day", 0)
        avg_len = cc.get("avg_len", 28)

        # ── Ovulation Window ─────────────────────────────────────────────────
        if 10 <= day <= 19:
            days_in_window = day - 10 + 1
            return (
                f'<div style="background:#fef2f2;border:2px solid #dc2626;border-radius:12px;'
                f'padding:14px 16px;margin-bottom:14px;display:flex;align-items:center;gap:14px;">'
                f'<span style="font-size:1.8em;flex-shrink:0;">🌕</span>'
                f'<div>'
                f'<div style="font-size:.75em;font-weight:800;letter-spacing:.09em;'
                f'text-transform:uppercase;color:#dc2626;margin-bottom:3px;">⚠ Fertility Alert</div>'
                f'<div style="font-size:1.05em;font-weight:700;color:#991b1b;line-height:1.3;">'
                f'Ovulation Window — Day {day} of {avg_len}</div>'
                f'<div style="font-size:.82em;color:#b91c1c;margin-top:3px;line-height:1.4;">'
                f'Day {days_in_window} of 10 in peak fertility window. NFP attention required.</div>'
                f'</div></div>'
            )

        # ── Period Approaching ────────────────────────────────────────────────
        days_until = avg_len - day
        if 0 <= days_until <= 4:
            if days_until == 0:
                _when = "today"
            elif days_until == 1:
                _when = "in ~1 day"
            else:
                _when = f"in ~{days_until} days"
            return (
                f'<div style="background:#fff7ed;border:2px solid #f59e0b;border-radius:12px;'
                f'padding:14px 16px;margin-bottom:14px;display:flex;align-items:center;gap:14px;">'
                f'<span style="font-size:1.8em;flex-shrink:0;">🩸</span>'
                f'<div>'
                f'<div style="font-size:.75em;font-weight:800;letter-spacing:.09em;'
                f'text-transform:uppercase;color:#d97706;margin-bottom:3px;">Cycle Notice</div>'
                f'<div style="font-size:1.05em;font-weight:700;color:#92400e;line-height:1.3;">'
                f'Period approaching — Day {day} of {avg_len}</div>'
                f'<div style="font-size:.82em;color:#b45309;margin-top:3px;line-height:1.4;">'
                f'Estimated {_when}. Plan for rest and grace.</div>'
                f'</div></div>'
            )

        return ""
    except Exception:
        return ""


def load_mom_profile() -> dict:
    try:
        with open(MOM_PROFILE_PATH) as f:
            return json.load(f)
    except Exception:
        return {
            "birthday": "",
            "clothing_sizes": {k: "" for k, _ in CLOTHING_FIELDS},
            "shoe_size": "",
            "gift_ideas": [],
            "favorite_foods": [],
            "favorite_restaurants": [],
            "just_for_me": [],
            "dream_trips": [],
            "bucket_list": [],
            "notes_for_john": "",
            "other_notes": "",
        }


def save_mom_profile(data: dict) -> None:
    os.makedirs("data/profiles", exist_ok=True)
    existing = load_mom_profile()
    existing.update(data)
    with open(MOM_PROFILE_PATH, "w") as f:
        json.dump(existing, f, indent=2)


def _list_section_html(key: str, label: str, hint: str, items: list) -> str:
    items_json = json.dumps(items)
    items_html = ""
    for i, item in enumerate(items):
        item_esc = escape(str(item))
        items_html += f"""
        <div class="mom-item-row" style="display:flex;align-items:center;gap:6px;margin-bottom:5px;">
          <input type="text" value="{item_esc}"
                 oninput="momMarkDirty()"
                 onchange="momUpdateItem('{key}',{i},this.value)"
                 style="flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:8px;
                        font-size:0.85em;font-family:inherit;background:white;">
          <button onclick="momRemoveItem('{key}',{i})"
                  title="Remove"
                  style="padding:4px 8px;background:none;border:1px solid #fca5a5;border-radius:6px;
                         color:#ef4444;cursor:pointer;font-size:0.78em;flex-shrink:0;">&#10005;</button>
        </div>"""
    empty_html = '<div style="color:#bbb;font-size:0.82em;font-style:italic;">None yet.</div>' if not items else ""

    return f"""
<div style="margin-bottom:20px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:4px;">{escape(label)}</div>
  <div style="font-size:0.75em;color:#9ca3af;margin-bottom:8px;font-style:italic;">{escape(hint)}</div>
  <div id="mom-{key}-list" data-items='{items_json}'>
    {items_html or empty_html}
  </div>
  <div style="display:flex;gap:6px;margin-top:6px;">
    <input type="text" id="mom-{key}-new" placeholder="Add item…"
           onkeydown="if(event.key==='Enter'){{ momAddItem('{key}'); }}"
           style="flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:8px;
                  font-size:0.85em;font-family:inherit;background:white;">
    <button onclick="momAddItem('{key}')"
            style="padding:6px 14px;background:{ACCENT};color:white;border:none;border-radius:8px;
                   font-size:0.82em;font-weight:600;font-family:inherit;cursor:pointer;">+ Add</button>
  </div>
</div>"""


def render_lauren_schedule_card(target_date_str: str = "") -> str:
    """
    Full daily schedule card for Lauren — time-blocked Day List from the Family
    Rule of Life (same source as Now/Next cards and the boys' day lists).
    """
    from datetime import date as _date
    from html import escape as _e
    from daily_schedule_engine import (
        build_day_list, day_list_stats, generate_day_packet,
        load_progress, fmt_time_12h,
    )
    from data_helpers import normalize_date_query
    from config import parent_color
    from render_schedule import render_day_nav, _render_day_list_html, _DL_CSS, _DASH_JS, _ty_pod_strip
    from data_helpers import due_thankyou_reminders_for as _due_ty_for

    normalized_date = normalize_date_query(target_date_str)
    packet     = generate_day_packet(normalized_date)
    iso        = packet["iso"]
    weekday    = packet["weekday"]
    date_label = packet["date_label"]

    try:
        target_iso = _date.fromisoformat(iso)
    except Exception:
        target_iso = _date.today()

    # Build the Day List from the Family Rule of Life schedule
    day_list = build_day_list("Lauren", weekday, iso)

    # Merge in calendar events
    try:
        from daily_schedule_engine import get_calendar_events_for_boys
        from render_calendar import render_calendar_today_strip
        cal_items = get_calendar_events_for_boys(iso)
        for ev in cal_items:
            ev_time   = ev.get("time")
            time_sort = ev_time or "00:00"
            disp_time = fmt_time_12h(ev_time) if ev_time else "All day"
            loc       = ev.get("location", "")
            lbl       = ev["title"] + (f" \u2022 {loc}" if loc else "")
            day_list.append({
                "time": disp_time, "time_sort": time_sort,
                "end_time": fmt_time_12h(ev.get("end_time")) if ev.get("end_time") else disp_time,
                "label": lbl, "kind": "event",
                "checkable": False, "task_id": None,
                "done": False, "sub_items": [],
                "is_event": True,
                "event_id": ev.get("id", ""),
                "event_calendar": ev.get("calendar", ""),
            })
        day_list.sort(key=lambda x: x.get("time_sort", "00:00"))
        cal_strip_html = render_calendar_today_strip(iso)
    except Exception:
        cal_strip_html = ""

    stats    = day_list_stats(day_list)
    total    = stats["total"]
    done_cnt = stats["done"]
    pct      = stats["pct"]

    # Meals
    meals = {}
    try:
        from render_meals import load_meal_plan, _week_key, render_meal_today_card, get_cook_start_for_day
        _plan = load_meal_plan(_week_key(target_iso))
        meals = _plan.get("days", {}).get(weekday, {})
        meal_html = render_meal_today_card(target_iso)
        # ── Inject "Start cooking" into the day list ──────────────────────
        _cook = get_cook_start_for_day(meals, weekday=weekday)
        if _cook:
            day_list.append({
                "time":      fmt_time_12h(_cook["hhmm"]),
                "time_sort": _cook["hhmm"],
                "end_time":  fmt_time_12h(_cook["serve_hhmm"]),
                "label":     _cook["label"],
                "kind":      "cook",
                "checkable": True,
                "task_id":   f"cook__{iso}",
                "done":      False,
                "sub_items": [],
                "is_event":  False,
            })
            day_list.sort(key=lambda x: x.get("time_sort", "00:00"))
    except Exception:
        meal_html = ""

    c_bg    = parent_color("Lauren", "bg")
    c_light = parent_color("Lauren", "light")

    try:
        from render_daily_bar import render_daily_bar
        daily_bar = render_daily_bar(target_iso)
    except Exception:
        daily_bar = ""

    try:
        from render_schedule_support import render_now_next_strip
        now_next_html = render_now_next_strip()
    except Exception:
        now_next_html = ""

    day_nav  = render_day_nav("/mom-profile", iso)
    bar_col  = "#22c55e" if pct == 100 else ("#f59e0b" if pct >= 50 else c_bg)

    day_list_html = _render_day_list_html(day_list, "Lauren", iso, c_bg, meals)

    lucy_panel = (
        f'<div class="card card-tight no-print"'
        f' style="border-left:4px solid {c_bg};background:{c_light};">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">'
        f'<span style="font-size:1.1em;">✦</span>'
        f'<h3 style="margin:0;font-size:.95em;color:{c_bg};">Lucy\'s Notes for Lauren</h3>'
        f'</div>'
        f'<div id="lucy-lauren-brief"'
        f' style="font-size:.88em;line-height:1.6;color:#444;min-height:40px;">'
        f'<span style="color:#bbb;font-style:italic;">Loading…</span>'
        f'</div></div>'
    )

    _lauren_ty_strip = _ty_pod_strip(
        _due_ty_for("Lauren") + _due_ty_for("Family"), c_bg, "/mom-profile"
    )
    return f"""{_DL_CSS}
{_DASH_JS}
<div class="card" style="border-left:5px solid {c_bg};background:{c_light};margin-bottom:18px;">
    {daily_bar}
    <div class="page-header">
        <h2 style="color:{c_bg};margin:0 0 4px;">Lauren — {_e(date_label)}</h2>
        <div class="no-print">{day_nav}</div>
        <div class="dl-progress-bar no-print">
            <div class="dl-progress-fill" style="width:{pct}%;background:{bar_col};"></div>
        </div>
        <div class="summary-row no-print">
            <span class="badge" style="background:{bar_col};color:#fff;">{done_cnt}/{total} done</span>
            <span class="badge">{_e(weekday)}</span>
        </div>
        <div class="link-row no-print">
            <a class="link-button" href="/print/day/Lauren?date={_e(iso)}">Print Day List</a>
        </div>
        <div style="margin-top:8px;">{now_next_html}</div>
        <div style="margin-top:8px;">{cal_strip_html}</div>
    </div>
    {_cycle_fertility_banner(iso)}
    {lucy_panel}
    <div class="day-list">
        {day_list_html}
    </div>
    {meal_html}
    {_lauren_ty_strip}
</div>
<script>
(function() {{
    var el = document.getElementById('lucy-lauren-brief');
    if (!el) return;
    var fallback = '<span style="color:#bbb;font-style:italic;">Not available right now.</span>';
    var timer = setTimeout(function() {{ el.innerHTML = fallback; }}, 18000);
    fetch('/lucy-child-brief/lauren')
        .then(function(r) {{ return r.json(); }})
        .then(function(d) {{
            clearTimeout(timer);
            el.innerHTML = d.html || fallback;
        }})
        .catch(function() {{
            clearTimeout(timer);
            el.innerHTML = fallback;
        }});
}})();
</script>"""


def render_mom_profile_page(target_date_str: str = "") -> str:
    p = load_mom_profile()
    clothing    = p.get("clothing_sizes", {})
    shoe        = escape(p.get("shoe_size", ""))
    birthday    = escape(p.get("birthday", ""))
    notes_john  = escape(p.get("notes_for_john", ""))
    other_notes = escape(p.get("other_notes", ""))

    clothing_inputs = ""
    for key, label in CLOTHING_FIELDS:
        val = escape(clothing.get(key, ""))
        clothing_inputs += f"""
        <div style="flex:1;min-width:110px;">
          <div style="font-size:0.72em;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
                      color:var(--ink-faint);margin-bottom:4px;">{label}</div>
          <input type="text" id="mom-sz-{key}" value="{val}" placeholder="e.g. M / 8"
                 oninput="momMarkDirty()"
                 style="width:100%;padding:7px 10px;border:1px solid var(--border);border-radius:8px;
                        font-size:0.88em;font-family:inherit;background:white;">
        </div>"""

    list_sections_html = "".join(
        _list_section_html(key, label, hint, p.get(key, []))
        for key, label, hint in LIST_SECTIONS
    )

    all_keys_json      = json.dumps([key for key, _, __ in LIST_SECTIONS])
    clothing_keys_json = json.dumps([key for key, _ in CLOTHING_FIELDS])
    all_list_data      = {key: p.get(key, []) for key, _, __ in LIST_SECTIONS}

    schedule_card = render_lauren_schedule_card(target_date_str)

    body = f"""
{top_nav()}
<div style="max-width:680px;margin:0 auto;padding:16px;">

  <!-- Schedule card — same logic as the boys' pages -->
  {schedule_card}

  <div style="margin-bottom:16px;">
    <div style="font-size:0.7em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
                color:{ACCENT};margin-bottom:2px;">Wife &amp; Mother</div>
    <div style="font-size:0.82em;color:#9ca3af;">
      Sizes, wishes, dreams &amp; everything that's just for you
    </div>
  </div>

  <!-- Save bar -->
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px;flex-wrap:wrap;">
    <button onclick="momSave()"
            style="padding:8px 22px;background:{ACCENT};color:white;border:none;border-radius:8px;
                   font-size:0.88em;font-weight:700;font-family:inherit;cursor:pointer;">Save Changes</button>
    <span id="mom-dirty" style="display:none;font-size:0.78em;color:#f59e0b;font-weight:600;">Unsaved changes</span>
    <span id="mom-status" style="font-size:0.82em;color:#22c55e;min-height:18px;"></span>
  </div>

  <!-- Birthday -->
  <div class="card" style="border-left:5px solid {ACCENT};background:{ACCENT_LIGHT};margin-bottom:14px;">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:8px;">Birthday</div>
    <input type="date" id="mom-birthday" value="{birthday}"
           oninput="momMarkDirty()"
           style="padding:8px 12px;border:1px solid var(--border);border-radius:8px;
                  font-size:0.9em;font-family:inherit;background:white;max-width:220px;">
  </div>

  <!-- Clothing & Shoe Sizes -->
  <div class="card" style="border-left:5px solid {ACCENT};background:{ACCENT_LIGHT};margin-bottom:14px;">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:10px;">Clothing &amp; Shoe Sizes</div>
    <div style="display:flex;flex-wrap:wrap;gap:10px;">
      {clothing_inputs}
      <div style="flex:1;min-width:100px;">
        <div style="font-size:0.72em;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
                    color:var(--ink-faint);margin-bottom:4px;">Shoe Size</div>
        <input type="text" id="mom-shoe" value="{shoe}" placeholder="e.g. 8"
               oninput="momMarkDirty()"
               style="width:100%;padding:7px 10px;border:1px solid var(--border);border-radius:8px;
                      font-size:0.88em;font-family:inherit;background:white;">
      </div>
    </div>
  </div>

  <!-- Lists -->
  <div class="card" style="border-left:5px solid {ACCENT};background:{ACCENT_LIGHT};margin-bottom:14px;">
    {list_sections_html}
  </div>

  <!-- Notes for John -->
  <div class="card" style="border-left:5px solid {ACCENT};background:{ACCENT_LIGHT};margin-bottom:14px;">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:6px;">Notes for John</div>
    <div style="font-size:0.75em;color:#9ca3af;margin-bottom:8px;font-style:italic;">
      Things you want him to know, remember, or notice — your heart for him
    </div>
    <textarea id="mom-notes-john" rows="4"
              oninput="momMarkDirty()"
              placeholder="Write freely…"
              style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;
                     font-size:0.85em;font-family:inherit;resize:vertical;background:white;">{notes_john}</textarea>
  </div>

  <!-- Other Notes -->
  <div class="card" style="border-left:5px solid {ACCENT};background:{ACCENT_LIGHT};margin-bottom:14px;">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:6px;">Other Notes</div>
    <textarea id="mom-other-notes" rows="3"
              oninput="momMarkDirty()"
              placeholder="Anything else worth keeping…"
              style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;
                     font-size:0.85em;font-family:inherit;resize:vertical;background:white;">{other_notes}</textarea>
  </div>

</div>

<!-- Cycle Tracking Section -->
<div style="margin-top:24px;">
  <div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
              color:{ACCENT};margin-bottom:12px;">🌙 Cycle Tracking
    <span style="font-weight:400;font-size:0.85em;letter-spacing:0;text-transform:none;
                 color:#9ca3af;margin-left:6px;">private &middot; only visible to you</span>
  </div>
  {_section_cycle(return_url="/mom-profile")}
</div>

<script>
(function() {{
  var _data = {json.dumps(all_list_data)};

  window.momMarkDirty = function() {{
    var d = document.getElementById('mom-dirty');
    if (d) d.style.display = 'inline';
  }};

  window.momUpdateItem = function(key, idx, val) {{
    if (!_data[key]) _data[key] = [];
    _data[key][idx] = val;
    momMarkDirty();
  }};

  window.momRemoveItem = function(key, idx) {{
    if (!_data[key]) return;
    _data[key].splice(idx, 1);
    _rebuildList(key);
    momMarkDirty();
  }};

  window.momAddItem = function(key) {{
    var inp = document.getElementById('mom-' + key + '-new');
    if (!inp) return;
    var val = inp.value.trim();
    if (!val) return;
    if (!_data[key]) _data[key] = [];
    _data[key].push(val);
    inp.value = '';
    _rebuildList(key);
    momMarkDirty();
  }};

  function _rebuildList(key) {{
    var container = document.getElementById('mom-' + key + '-list');
    if (!container) return;
    var items = _data[key] || [];
    container.setAttribute('data-items', JSON.stringify(items));
    if (items.length === 0) {{
      container.innerHTML = '<div style="color:#bbb;font-size:0.82em;font-style:italic;">None yet.</div>';
      return;
    }}
    container.innerHTML = items.map(function(item, i) {{
      var esc = String(item).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
      return '<div class="mom-item-row" style="display:flex;align-items:center;gap:6px;margin-bottom:5px;">'
        + '<input type="text" value="' + esc + '" '
        + 'oninput="momMarkDirty()" '
        + 'onchange="momUpdateItem(\\'' + key + '\\',' + i + ',this.value)" '
        + 'style="flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:8px;font-size:0.85em;font-family:inherit;background:white;">'
        + '<button onclick="momRemoveItem(\\'' + key + '\\',' + i + ')" '
        + 'style="padding:4px 8px;background:none;border:1px solid #fca5a5;border-radius:6px;color:#ef4444;cursor:pointer;font-size:0.78em;flex-shrink:0;">&#10005;</button>'
        + '</div>';
    }}).join('');
  }}

  window.momSave = function() {{
    var clothing = {{}};
    {clothing_keys_json}.forEach(function(key) {{
      var el = document.getElementById('mom-sz-' + key);
      if (el) clothing[key] = el.value.trim();
    }});

    {all_keys_json}.forEach(function(key) {{
      var container = document.getElementById('mom-' + key + '-list');
      if (container) {{
        var inputs = container.querySelectorAll('input[type=text]');
        var arr = [];
        inputs.forEach(function(inp) {{ if (inp.value.trim()) arr.push(inp.value.trim()); }});
        if (arr.length) _data[key] = arr;
      }}
    }});

    var profile = {{
      birthday:      (document.getElementById('mom-birthday') || {{}}).value || '',
      clothing_sizes: clothing,
      shoe_size:     (document.getElementById('mom-shoe') || {{}}).value || '',
      notes_for_john:(document.getElementById('mom-notes-john') || {{}}).value || '',
      other_notes:   (document.getElementById('mom-other-notes') || {{}}).value || '',
    }};
    {all_keys_json}.forEach(function(key) {{ profile[key] = _data[key] || []; }});

    var params = new URLSearchParams();
    params.append('profile', JSON.stringify(profile));
    var statusEl = document.getElementById('mom-status');
    var dirtyEl  = document.getElementById('mom-dirty');
    fetch('/save-mom-profile', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
      body: params.toString()
    }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
      if (d.ok) {{
        if (statusEl) {{ statusEl.textContent = 'Saved!'; setTimeout(function(){{statusEl.textContent='';}},2000); }}
        if (dirtyEl) dirtyEl.style.display = 'none';
      }} else {{
        if (statusEl) statusEl.textContent = 'Error — try again.';
      }}
    }}).catch(function() {{
      if (statusEl) statusEl.textContent = 'Network error.';
    }});
  }};
}})();
</script>
"""
    return html_page("Lauren", body)
