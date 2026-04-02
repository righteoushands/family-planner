"""
render_child_profile.py — Per-child profile card

Stores and displays:
  - Clothing & shoe sizes
  - Birthday gift ideas (growing wishlist)
  - Skills / things they want to learn
  - Requested activities & outings
  - Favorite foods & meal requests
  - Dream trips & adventures
  - General interests & notes

All fields are editable inline. Lucy can read and reference this data.
"""
import json, os
from html import escape

PROFILE_DIR = "data/profiles"

CLOTHING_FIELDS = [
    ("shirt",      "Shirt"),
    ("pants",      "Pants"),
    ("jacket",     "Jacket"),
    ("underwear",  "Underwear"),
    ("socks",      "Socks"),
]

LIST_SECTIONS = [
    ("gift_ideas",           "Birthday & Gift Ideas",         "Things they've mentioned wanting or Mom has noticed"),
    ("skills_to_learn",      "Skills to Learn",               "Things they want to learn or get better at"),
    ("activities_requested", "Activities & Outings Requested", "Sports, experiences, or outings they've asked about"),
    ("favorite_foods",       "Favorite Foods",                "Foods they love — meals to plan around"),
    ("meal_requests",        "Meal Requests",                 "Specific dishes they've asked for"),
    ("dream_trips",          "Dream Trips & Adventures",      "Places they want to go or things they want to do"),
    ("interests",            "Interests & Hobbies",           "Current passions, obsessions, or curiosities"),
]


def _profile_path(child: str) -> str:
    return os.path.join(PROFILE_DIR, f"{child.lower()}.json")


def load_child_profile(child: str) -> dict:
    path = _profile_path(child)
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {
            "clothing_sizes": {k: "" for k, _ in CLOTHING_FIELDS},
            "shoe_size": "",
            "gift_ideas": [],
            "skills_to_learn": [],
            "activities_requested": [],
            "favorite_foods": [],
            "meal_requests": [],
            "dream_trips": [],
            "interests": [],
            "other_notes": "",
        }


def save_child_profile(child: str, data: dict) -> None:
    os.makedirs(PROFILE_DIR, exist_ok=True)
    path = _profile_path(child)
    existing = load_child_profile(child)
    existing.update(data)
    with open(path, "w") as f:
        json.dump(existing, f, indent=2)


def profile_summary_for_lucy(child: str) -> str:
    """Return a compact text summary of the child's profile for Lucy's context."""
    p = load_child_profile(child)
    lines = []

    sizes = p.get("clothing_sizes", {})
    size_parts = [f"{label}: {sizes.get(key,'?')}" for key, label in CLOTHING_FIELDS if sizes.get(key)]
    shoe = p.get("shoe_size", "")
    if size_parts:
        lines.append("Clothing sizes — " + ", ".join(size_parts))
    if shoe:
        lines.append(f"Shoe size: {shoe}")

    for key, label, _ in LIST_SECTIONS:
        items = p.get(key, [])
        if items:
            lines.append(f"{label}: " + "; ".join(str(i) for i in items[:10]))

    notes = p.get("other_notes", "").strip()
    if notes:
        lines.append(f"Other notes: {notes}")

    return "\n".join(lines) if lines else "(No profile data recorded yet.)"


def render_child_profile_section(child: str, c_bg: str = "#8b5a3c", c_light: str = "#fdf8f4") -> str:
    """Render the full editable profile card for a child's page."""
    p = load_child_profile(child)
    child_esc = escape(child)
    child_slug = child.lower()

    clothing = p.get("clothing_sizes", {})
    shoe     = escape(p.get("shoe_size", ""))
    notes    = escape(p.get("other_notes", ""))

    clothing_inputs = ""
    for key, label in CLOTHING_FIELDS:
        val = escape(clothing.get(key, ""))
        clothing_inputs += f"""
        <div style="flex:1;min-width:100px;">
          <div style="font-size:0.72em;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
                      color:var(--ink-faint);margin-bottom:4px;">{label}</div>
          <input type="text" id="prof-{child_slug}-sz-{key}" value="{val}" placeholder="e.g. M / 10"
                 oninput="profileMarkDirty('{child_slug}')"
                 style="width:100%;padding:7px 10px;border:1px solid var(--border);border-radius:8px;
                        font-size:0.88em;font-family:inherit;background:white;">
        </div>"""

    list_sections_html = ""
    for key, label, hint in LIST_SECTIONS:
        items = p.get(key, [])
        items_json = json.dumps(items)
        items_html = ""
        for i, item in enumerate(items):
            item_esc = escape(str(item))
            items_html += f"""
            <div class="prof-item-row" id="prof-{child_slug}-{key}-row-{i}"
                 style="display:flex;align-items:center;gap:6px;margin-bottom:5px;">
              <input type="text" value="{item_esc}"
                     oninput="profileMarkDirty('{child_slug}')"
                     onchange="profileUpdateItem('{child_slug}','{key}',{i},this.value)"
                     style="flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:8px;
                            font-size:0.85em;font-family:inherit;background:white;">
              <button onclick="profileRemoveItem('{child_slug}','{key}',{i})"
                      title="Remove"
                      style="padding:4px 8px;background:none;border:1px solid #fca5a5;border-radius:6px;
                             color:#ef4444;cursor:pointer;font-size:0.78em;flex-shrink:0;">&#10005;</button>
            </div>"""

        list_sections_html += f"""
        <div style="margin-bottom:18px;">
          <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                      color:var(--ink-faint);margin-bottom:4px;">{escape(label)}</div>
          <div style="font-size:0.75em;color:#9ca3af;margin-bottom:8px;font-style:italic;">{escape(hint)}</div>
          <div id="prof-{child_slug}-{key}-list" data-items='{items_json}'>
            {items_html if items_html else f'<div style="color:#bbb;font-size:0.82em;font-style:italic;">None yet.</div>'}
          </div>
          <div style="display:flex;gap:6px;margin-top:6px;">
            <input type="text" id="prof-{child_slug}-{key}-new" placeholder="Add item…"
                   onkeydown="if(event.key==='Enter'){{ profileAddItem('{child_slug}','{key}'); }}"
                   style="flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:8px;
                          font-size:0.85em;font-family:inherit;background:white;">
            <button onclick="profileAddItem('{child_slug}','{key}')"
                    style="padding:6px 14px;background:{c_bg};color:white;border:none;border-radius:8px;
                           font-size:0.82em;font-weight:600;font-family:inherit;cursor:pointer;">+ Add</button>
          </div>
        </div>"""

    return f"""
<div class="card" id="prof-card-{child_slug}"
     style="border-left:5px solid {c_bg};background:{c_light};margin-top:14px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex-wrap:wrap;gap:8px;">
    <div>
      <div style="font-size:0.7em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
                  color:{c_bg};margin-bottom:2px;">Profile</div>
      <h3 style="margin:0;font-size:1em;color:var(--ink);">{child_esc}'s Preferences &amp; Sizes</h3>
      <div style="font-size:0.75em;color:#9ca3af;margin-top:2px;">
        Mom's reference for shopping, planning &amp; delighting {child_esc}. Lucy can read this too.
      </div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;">
      <span id="prof-{child_slug}-dirty" style="display:none;font-size:0.75em;color:#f59e0b;font-weight:600;">Unsaved changes</span>
      <button onclick="profileSave('{child_slug}')"
              style="padding:7px 18px;background:{c_bg};color:white;border:none;border-radius:8px;
                     font-size:0.82em;font-weight:700;font-family:inherit;cursor:pointer;">Save</button>
    </div>
  </div>
  <div id="prof-{child_slug}-status" style="font-size:0.8em;color:#22c55e;min-height:16px;margin-bottom:10px;"></div>

  <!-- Clothing & Shoe Sizes -->
  <div style="margin-bottom:20px;">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:10px;">Clothing &amp; Shoe Sizes</div>
    <div style="display:flex;flex-wrap:wrap;gap:10px;">
      {clothing_inputs}
      <div style="flex:1;min-width:100px;">
        <div style="font-size:0.72em;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
                    color:var(--ink-faint);margin-bottom:4px;">Shoe Size</div>
        <input type="text" id="prof-{child_slug}-shoe" value="{shoe}" placeholder="e.g. 8.5"
               oninput="profileMarkDirty('{child_slug}')"
               style="width:100%;padding:7px 10px;border:1px solid var(--border);border-radius:8px;
                      font-size:0.88em;font-family:inherit;background:white;">
      </div>
    </div>
  </div>

  <!-- List sections -->
  {list_sections_html}

  <!-- Other Notes -->
  <div style="margin-bottom:8px;">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:6px;">Other Notes</div>
    <textarea id="prof-{child_slug}-notes" rows="3"
              oninput="profileMarkDirty('{child_slug}')"
              placeholder="Anything else Mom wants to remember about {child_esc}…"
              style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;
                     font-size:0.85em;font-family:inherit;resize:vertical;background:white;">{notes}</textarea>
  </div>
</div>

<script>
(function() {{
  var _profileData = {{}};

  /* Bootstrap in-memory state from the DOM data-items attributes */
  function _initProfile(slug) {{
    if (_profileData[slug]) return;
    _profileData[slug] = {{ clothing_sizes: {{}}, shoe_size: '', gift_ideas: [], skills_to_learn: [],
      activities_requested: [], favorite_foods: [], meal_requests: [], dream_trips: [], interests: [], other_notes: '' }};
    {json.dumps([key for key, _, __ in LIST_SECTIONS])}.forEach(function(key) {{
      var el = document.getElementById('prof-' + slug + '-' + key + '-list');
      if (el) {{
        try {{ _profileData[slug][key] = JSON.parse(el.getAttribute('data-items') || '[]'); }} catch(e) {{}}
      }}
    }});
  }}

  window.profileMarkDirty = function(slug) {{
    var d = document.getElementById('prof-' + slug + '-dirty');
    if (d) d.style.display = 'inline';
  }};

  window.profileUpdateItem = function(slug, key, idx, val) {{
    _initProfile(slug);
    if (!_profileData[slug][key]) _profileData[slug][key] = [];
    _profileData[slug][key][idx] = val;
    profileMarkDirty(slug);
  }};

  window.profileRemoveItem = function(slug, key, idx) {{
    _initProfile(slug);
    if (!_profileData[slug][key]) return;
    _profileData[slug][key].splice(idx, 1);
    _rebuildListHTML(slug, key);
    profileMarkDirty(slug);
  }};

  window.profileAddItem = function(slug, key) {{
    _initProfile(slug);
    var inp = document.getElementById('prof-' + slug + '-' + key + '-new');
    if (!inp) return;
    var val = inp.value.trim();
    if (!val) return;
    if (!_profileData[slug][key]) _profileData[slug][key] = [];
    _profileData[slug][key].push(val);
    inp.value = '';
    _rebuildListHTML(slug, key);
    profileMarkDirty(slug);
  }};

  function _rebuildListHTML(slug, key) {{
    var container = document.getElementById('prof-' + slug + '-' + key + '-list');
    if (!container) return;
    var items = (_profileData[slug][key] || []);
    container.setAttribute('data-items', JSON.stringify(items));
    if (items.length === 0) {{
      container.innerHTML = '<div style="color:#bbb;font-size:0.82em;font-style:italic;">None yet.</div>';
      return;
    }}
    container.innerHTML = items.map(function(item, i) {{
      var esc = String(item).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
      return '<div class="prof-item-row" style="display:flex;align-items:center;gap:6px;margin-bottom:5px;">'
        + '<input type="text" value="' + esc + '" '
        + 'oninput="profileMarkDirty(\\'' + slug + '\\')" '
        + 'onchange="profileUpdateItem(\\'' + slug + '\\',\\'' + key + '\\',' + i + ',this.value)" '
        + 'style="flex:1;padding:6px 10px;border:1px solid var(--border);border-radius:8px;font-size:0.85em;font-family:inherit;background:white;">'
        + '<button onclick="profileRemoveItem(\\'' + slug + '\\',\\'' + key + '\\',' + i + ')" '
        + 'style="padding:4px 8px;background:none;border:1px solid #fca5a5;border-radius:6px;color:#ef4444;cursor:pointer;font-size:0.78em;flex-shrink:0;">&#10005;</button>'
        + '</div>';
    }}).join('');
  }}

  window.profileSave = function(slug) {{
    _initProfile(slug);
    /* Collect current input values */
    {json.dumps([key for key, _ in CLOTHING_FIELDS])}.forEach(function(key) {{
      var el = document.getElementById('prof-' + slug + '-sz-' + key);
      if (el) _profileData[slug].clothing_sizes[key] = el.value.trim();
    }});
    var shoeEl = document.getElementById('prof-' + slug + '-shoe');
    if (shoeEl) _profileData[slug].shoe_size = shoeEl.value.trim();
    var notesEl = document.getElementById('prof-' + slug + '-notes');
    if (notesEl) _profileData[slug].other_notes = notesEl.value.trim();

    /* Collect any list items that were typed but not yet added via button */
    {json.dumps([key for key, _, __ in LIST_SECTIONS])}.forEach(function(key) {{
      var container = document.getElementById('prof-' + slug + '-' + key + '-list');
      if (container) {{
        var inputs = container.querySelectorAll('input[type=text]');
        var arr = [];
        inputs.forEach(function(inp) {{ if (inp.value.trim()) arr.push(inp.value.trim()); }});
        if (arr.length) _profileData[slug][key] = arr;
      }}
    }});

    var statusEl = document.getElementById('prof-' + slug + '-status');
    var dirtyEl  = document.getElementById('prof-' + slug + '-dirty');
    var params = new URLSearchParams();
    params.append('child', slug);
    params.append('profile', JSON.stringify(_profileData[slug]));
    fetch('/save-child-profile', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
      body: params.toString()
    }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
      if (d.ok) {{
        if (statusEl) {{ statusEl.textContent = 'Saved!'; setTimeout(function(){{ statusEl.textContent=''; }}, 2000); }}
        if (dirtyEl) dirtyEl.style.display = 'none';
      }} else {{
        if (statusEl) statusEl.textContent = 'Error saving — try again.';
      }}
    }}).catch(function() {{
      if (statusEl) statusEl.textContent = 'Network error.';
    }});
  }};
}})();
</script>
"""
