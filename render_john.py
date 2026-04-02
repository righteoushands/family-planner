"""
render_john.py — John's (husband/dad) personal profile page

Stores and displays:
  - Clothing & shoe sizes
  - Birthday
  - Gift ideas
  - Favorite foods & restaurants
  - Hobbies & interests
  - Couple bucket list
  - Love notes from Mom
  - Other notes
"""
import json, os
from html import escape
from ui_helpers import html_page, top_nav

JOHN_PROFILE_PATH = "data/profiles/john.json"

CLOTHING_FIELDS = [
    ("shirt",     "Shirt"),
    ("pants",     "Pants"),
    ("jacket",    "Jacket"),
    ("underwear", "Underwear"),
    ("socks",     "Socks"),
]

LIST_SECTIONS = [
    ("gift_ideas",          "Gift Ideas",                    "Things John has mentioned wanting or you've noticed"),
    ("favorite_foods",      "Favorite Foods",                "His go-to favorites for meal planning"),
    ("favorite_restaurants","Favorite Restaurants",          "Places he loves to eat out"),
    ("hobbies_interests",   "Hobbies & Interests",           "What lights him up — for planning dates and gifts"),
    ("couple_bucket_list",  "Couple Bucket List",            "Things you want to do together"),
]

from config import parent_color as _parent_color
ACCENT       = _parent_color("John", "bg")
ACCENT_LIGHT = _parent_color("John", "light")


def load_john_profile() -> dict:
    try:
        with open(JOHN_PROFILE_PATH) as f:
            return json.load(f)
    except Exception:
        return {
            "birthday": "",
            "clothing_sizes": {k: "" for k, _ in CLOTHING_FIELDS},
            "shoe_size": "",
            "gift_ideas": [],
            "favorite_foods": [],
            "favorite_restaurants": [],
            "hobbies_interests": [],
            "couple_bucket_list": [],
            "love_notes": "",
            "other_notes": "",
        }


def save_john_profile(data: dict) -> None:
    os.makedirs("data/profiles", exist_ok=True)
    existing = load_john_profile()
    existing.update(data)
    with open(JOHN_PROFILE_PATH, "w") as f:
        json.dump(existing, f, indent=2)


def _list_section_html(key: str, label: str, hint: str, items: list) -> str:
    items_json = json.dumps(items)
    items_html = ""
    for i, item in enumerate(items):
        item_esc = escape(str(item))
        items_html += f"""
        <div class="john-item-row" style="display:flex;align-items:center;gap:6px;margin-bottom:5px;">
          <input type="text" value="{item_esc}"
                 oninput="johnMarkDirty()"
                 onchange="johnUpdateItem('{key}',{i},this.value)"
                 style="flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:8px;
                        font-size:0.85em;font-family:inherit;background:white;">
          <button onclick="johnRemoveItem('{key}',{i})"
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
  <div id="john-{key}-list" data-items='{items_json}'>
    {items_html or empty_html}
  </div>
  <div style="display:flex;gap:6px;margin-top:6px;">
    <input type="text" id="john-{key}-new" placeholder="Add item…"
           onkeydown="if(event.key==='Enter'){{ johnAddItem('{key}'); }}"
           style="flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:8px;
                  font-size:0.85em;font-family:inherit;background:white;">
    <button onclick="johnAddItem('{key}')"
            style="padding:6px 14px;background:{ACCENT};color:white;border:none;border-radius:8px;
                   font-size:0.82em;font-weight:600;font-family:inherit;cursor:pointer;">+ Add</button>
  </div>
</div>"""


def render_john_page() -> str:
    p = load_john_profile()
    clothing = p.get("clothing_sizes", {})
    shoe     = escape(p.get("shoe_size", ""))
    birthday = escape(p.get("birthday", ""))
    love_notes = escape(p.get("love_notes", ""))
    other_notes = escape(p.get("other_notes", ""))

    clothing_inputs = ""
    for key, label in CLOTHING_FIELDS:
        val = escape(clothing.get(key, ""))
        clothing_inputs += f"""
        <div style="flex:1;min-width:100px;">
          <div style="font-size:0.72em;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
                      color:var(--ink-faint);margin-bottom:4px;">{label}</div>
          <input type="text" id="john-sz-{key}" value="{val}" placeholder="e.g. L / 32x30"
                 oninput="johnMarkDirty()"
                 style="width:100%;padding:7px 10px;border:1px solid var(--border);border-radius:8px;
                        font-size:0.88em;font-family:inherit;background:white;">
        </div>"""

    list_sections_html = "".join(
        _list_section_html(key, label, hint, p.get(key, []))
        for key, label, hint in LIST_SECTIONS
    )

    all_keys_json = json.dumps([key for key, _, __ in LIST_SECTIONS])
    clothing_keys_json = json.dumps([key for key, _ in CLOTHING_FIELDS])
    all_list_data = {key: p.get(key, []) for key, _, __ in LIST_SECTIONS}

    body = f"""
{top_nav()}
<div style="max-width:680px;margin:0 auto;padding:16px;">
  <div style="margin-bottom:20px;">
    <div style="font-size:0.7em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
                color:{ACCENT};margin-bottom:2px;">Husband &amp; Dad</div>
    <h1 style="margin:0;font-size:1.6em;color:var(--ink);">John</h1>
    <div style="font-size:0.82em;color:#9ca3af;margin-top:2px;">
      Mom's reference page — sizes, gift ideas, couple plans &amp; notes
    </div>
  </div>

  <!-- Save bar -->
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px;flex-wrap:wrap;">
    <button onclick="johnSave()"
            style="padding:8px 22px;background:{ACCENT};color:white;border:none;border-radius:8px;
                   font-size:0.88em;font-weight:700;font-family:inherit;cursor:pointer;">Save Changes</button>
    <span id="john-dirty" style="display:none;font-size:0.78em;color:#f59e0b;font-weight:600;">Unsaved changes</span>
    <span id="john-status" style="font-size:0.82em;color:#22c55e;min-height:18px;"></span>
  </div>

  <!-- Birthday -->
  <div class="card" style="border-left:5px solid {ACCENT};background:{ACCENT_LIGHT};margin-bottom:14px;">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:8px;">Birthday</div>
    <input type="date" id="john-birthday" value="{birthday}"
           oninput="johnMarkDirty()"
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
        <input type="text" id="john-shoe" value="{shoe}" placeholder="e.g. 11"
               oninput="johnMarkDirty()"
               style="width:100%;padding:7px 10px;border:1px solid var(--border);border-radius:8px;
                      font-size:0.88em;font-family:inherit;background:white;">
      </div>
    </div>
  </div>

  <!-- Lists -->
  <div class="card" style="border-left:5px solid {ACCENT};background:{ACCENT_LIGHT};margin-bottom:14px;">
    {list_sections_html}
  </div>

  <!-- Love Notes -->
  <div class="card" style="border-left:5px solid {ACCENT};background:{ACCENT_LIGHT};margin-bottom:14px;">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:6px;">Love Notes</div>
    <div style="font-size:0.75em;color:#9ca3af;margin-bottom:8px;font-style:italic;">
      Things you love about him, prayers for him, or things you want him to know
    </div>
    <textarea id="john-love-notes" rows="4"
              oninput="johnMarkDirty()"
              placeholder="Write freely — this is just for you…"
              style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;
                     font-size:0.85em;font-family:inherit;resize:vertical;background:white;">{love_notes}</textarea>
  </div>

  <!-- Other Notes -->
  <div class="card" style="border-left:5px solid {ACCENT};background:{ACCENT_LIGHT};margin-bottom:14px;">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:6px;">Other Notes</div>
    <textarea id="john-other-notes" rows="3"
              oninput="johnMarkDirty()"
              placeholder="Anything else to remember…"
              style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;
                     font-size:0.85em;font-family:inherit;resize:vertical;background:white;">{other_notes}</textarea>
  </div>
</div>

<script>
(function() {{
  var _data = {json.dumps(all_list_data)};

  window.johnMarkDirty = function() {{
    var d = document.getElementById('john-dirty');
    if (d) d.style.display = 'inline';
  }};

  window.johnUpdateItem = function(key, idx, val) {{
    if (!_data[key]) _data[key] = [];
    _data[key][idx] = val;
    johnMarkDirty();
  }};

  window.johnRemoveItem = function(key, idx) {{
    if (!_data[key]) return;
    _data[key].splice(idx, 1);
    _rebuildList(key);
    johnMarkDirty();
  }};

  window.johnAddItem = function(key) {{
    var inp = document.getElementById('john-' + key + '-new');
    if (!inp) return;
    var val = inp.value.trim();
    if (!val) return;
    if (!_data[key]) _data[key] = [];
    _data[key].push(val);
    inp.value = '';
    _rebuildList(key);
    johnMarkDirty();
  }};

  function _rebuildList(key) {{
    var container = document.getElementById('john-' + key + '-list');
    if (!container) return;
    var items = _data[key] || [];
    container.setAttribute('data-items', JSON.stringify(items));
    if (items.length === 0) {{
      container.innerHTML = '<div style="color:#bbb;font-size:0.82em;font-style:italic;">None yet.</div>';
      return;
    }}
    container.innerHTML = items.map(function(item, i) {{
      var esc = String(item).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
      return '<div class="john-item-row" style="display:flex;align-items:center;gap:6px;margin-bottom:5px;">'
        + '<input type="text" value="' + esc + '" '
        + 'oninput="johnMarkDirty()" '
        + 'onchange="johnUpdateItem(\\'' + key + '\\',' + i + ',this.value)" '
        + 'style="flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:8px;font-size:0.85em;font-family:inherit;background:white;">'
        + '<button onclick="johnRemoveItem(\\'' + key + '\\',' + i + ')" '
        + 'style="padding:4px 8px;background:none;border:1px solid #fca5a5;border-radius:6px;color:#ef4444;cursor:pointer;font-size:0.78em;flex-shrink:0;">&#10005;</button>'
        + '</div>';
    }}).join('');
  }}

  window.johnSave = function() {{
    /* Collect clothing sizes */
    var clothing = {{}};
    {clothing_keys_json}.forEach(function(key) {{
      var el = document.getElementById('john-sz-' + key);
      if (el) clothing[key] = el.value.trim();
    }});

    /* Collect list items from DOM */
    {all_keys_json}.forEach(function(key) {{
      var container = document.getElementById('john-' + key + '-list');
      if (container) {{
        var inputs = container.querySelectorAll('input[type=text]');
        var arr = [];
        inputs.forEach(function(inp) {{ if (inp.value.trim()) arr.push(inp.value.trim()); }});
        if (arr.length) _data[key] = arr;
      }}
    }});

    var profile = {{
      birthday:    (document.getElementById('john-birthday') || {{}}).value || '',
      clothing_sizes: clothing,
      shoe_size:   (document.getElementById('john-shoe') || {{}}).value || '',
      love_notes:  (document.getElementById('john-love-notes') || {{}}).value || '',
      other_notes: (document.getElementById('john-other-notes') || {{}}).value || '',
    }};
    {all_keys_json}.forEach(function(key) {{ profile[key] = _data[key] || []; }});

    var params = new URLSearchParams();
    params.append('profile', JSON.stringify(profile));
    var statusEl = document.getElementById('john-status');
    var dirtyEl  = document.getElementById('john-dirty');
    fetch('/save-john-profile', {{
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
    return html_page("John", body)
