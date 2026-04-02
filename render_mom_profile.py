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

ACCENT       = "#8b5a3c"
ACCENT_LIGHT = "#fdf8f4"


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


def render_mom_profile_page() -> str:
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

    body = f"""
{top_nav()}
<div style="max-width:680px;margin:0 auto;padding:16px;">

  <div style="margin-bottom:20px;">
    <div style="font-size:0.7em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
                color:{ACCENT};margin-bottom:2px;">Wife &amp; Mother</div>
    <h1 style="margin:0;font-size:1.6em;color:var(--ink);">Mom</h1>
    <div style="font-size:0.82em;color:#9ca3af;margin-top:2px;">
      Your own page — sizes, wishes, dreams &amp; everything that's just for you
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
    return html_page("Mom", body)
