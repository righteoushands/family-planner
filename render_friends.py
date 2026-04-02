"""
render_friends.py — Friends & Families directory

Each family entry stores:
  - Family name & address
  - Members (name, birthday, role)
  - Gift ideas
  - Food allergies
  - Plans together (upcoming & past)
  - Favorite things / notes
  - General notes
"""
import json, os, uuid
from html import escape
from ui_helpers import html_page, top_nav

FRIENDS_PATH = "data/friends.json"
ACCENT = "#2d6a4f"
ACCENT_LIGHT = "#f0faf4"


def load_friends() -> list:
    try:
        with open(FRIENDS_PATH) as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_friends(data: list) -> None:
    os.makedirs("data", exist_ok=True)
    with open(FRIENDS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _member_html(fid: str, idx: int, m: dict) -> str:
    name     = escape(m.get("name", ""))
    birthday = escape(m.get("birthday", ""))
    role     = escape(m.get("role", ""))
    return f"""
<div class="member-row" id="member-{fid}-{idx}"
     style="display:flex;flex-wrap:wrap;gap:6px;align-items:flex-end;
            padding:8px;background:#f9fafb;border-radius:8px;margin-bottom:6px;">
  <div style="flex:2;min-width:100px;">
    <div style="font-size:0.68em;color:#9ca3af;margin-bottom:2px;">Name</div>
    <input type="text" value="{name}" placeholder="First name"
           oninput="friendMarkDirty('{fid}')"
           onchange="memberUpdate('{fid}',{idx},'name',this.value)"
           style="width:100%;padding:5px 8px;border:1px solid var(--border);border-radius:6px;
                  font-size:0.85em;font-family:inherit;background:white;">
  </div>
  <div style="flex:1;min-width:90px;">
    <div style="font-size:0.68em;color:#9ca3af;margin-bottom:2px;">Role</div>
    <input type="text" value="{role}" placeholder="e.g. Dad, Mom, Age 8"
           oninput="friendMarkDirty('{fid}')"
           onchange="memberUpdate('{fid}',{idx},'role',this.value)"
           style="width:100%;padding:5px 8px;border:1px solid var(--border);border-radius:6px;
                  font-size:0.85em;font-family:inherit;background:white;">
  </div>
  <div style="flex:1;min-width:120px;">
    <div style="font-size:0.68em;color:#9ca3af;margin-bottom:2px;">Birthday</div>
    <input type="date" value="{birthday}"
           oninput="friendMarkDirty('{fid}')"
           onchange="memberUpdate('{fid}',{idx},'birthday',this.value)"
           style="width:100%;padding:5px 8px;border:1px solid var(--border);border-radius:6px;
                  font-size:0.85em;font-family:inherit;background:white;">
  </div>
  <button onclick="memberRemove('{fid}',{idx})"
          style="padding:5px 10px;background:none;border:1px solid #fca5a5;border-radius:6px;
                 color:#ef4444;cursor:pointer;font-size:0.78em;align-self:flex-end;">&#10005;</button>
</div>"""


def _tag_list_html(fid: str, key: str, label: str, items: list) -> str:
    items_json = json.dumps(items)
    pills = ""
    for i, item in enumerate(items):
        item_esc = escape(str(item))
        pills += (
            f'<span style="display:inline-flex;align-items:center;gap:4px;background:white;'
            f'border:1px solid var(--border);border-radius:20px;padding:3px 10px;font-size:0.82em;">'
            f'{item_esc}'
            f'<button onclick="tagRemove(\'{fid}\',\'{key}\',{i})" '
            f'style="background:none;border:none;color:#9ca3af;cursor:pointer;'
            f'font-size:0.88em;padding:0;line-height:1;">&#10005;</button></span>'
        )
    empty = '<span style="color:#bbb;font-size:0.82em;font-style:italic;">None yet.</span>' if not pills else ""
    return f"""
<div style="margin-bottom:14px;">
  <div style="font-size:0.7em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:6px;">{escape(label)}</div>
  <div id="tags-{fid}-{key}" data-items='{items_json}'
       style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:6px;min-height:24px;">
    {pills or empty}
  </div>
  <div style="display:flex;gap:6px;">
    <input type="text" id="tag-inp-{fid}-{key}" placeholder="Type and press Enter or + Add…"
           onkeydown="if(event.key==='Enter'){{ tagAdd('{fid}','{key}'); }}"
           style="flex:1;padding:5px 10px;border:1px solid var(--border);border-radius:8px;
                  font-size:0.83em;font-family:inherit;background:white;">
    <button onclick="tagAdd('{fid}','{key}')"
            style="padding:5px 14px;background:{ACCENT};color:white;border:none;border-radius:8px;
                   font-size:0.8em;font-weight:600;font-family:inherit;cursor:pointer;">+ Add</button>
  </div>
</div>"""


def _plan_list_html(fid: str, items: list) -> str:
    items_json = json.dumps(items)
    rows = ""
    for i, item in enumerate(items):
        text_esc = escape(str(item.get("text", item) if isinstance(item, dict) else item))
        done = item.get("done", False) if isinstance(item, dict) else False
        done_style = "opacity:0.55;text-decoration:line-through;" if done else ""
        done_val = "true" if done else "false"
        rows += f"""
<div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">
  <input type="checkbox" {'checked' if done else ''}
         onchange="planToggle('{fid}',{i},this.checked)"
         style="width:17px;height:17px;accent-color:{ACCENT};flex-shrink:0;">
  <input type="text" value="{text_esc}" data-done="{done_val}"
         oninput="friendMarkDirty('{fid}')"
         onchange="planUpdate('{fid}',{i},'text',this.value)"
         style="flex:1;padding:5px 8px;border:1px solid var(--border);border-radius:6px;
                font-size:0.85em;font-family:inherit;background:white;{done_style}">
  <button onclick="planRemove('{fid}',{i})"
          style="padding:4px 8px;background:none;border:1px solid #fca5a5;border-radius:6px;
                 color:#ef4444;cursor:pointer;font-size:0.78em;flex-shrink:0;">&#10005;</button>
</div>"""
    empty = '<div style="color:#bbb;font-size:0.82em;font-style:italic;">None yet.</div>' if not rows else ""
    return f"""
<div style="margin-bottom:14px;">
  <div style="font-size:0.7em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:6px;">Plans Together</div>
  <div id="plans-{fid}" data-items='{items_json}'>
    {rows or empty}
  </div>
  <div style="display:flex;gap:6px;margin-top:6px;">
    <input type="text" id="plan-inp-{fid}" placeholder="Add a plan or outing…"
           onkeydown="if(event.key==='Enter'){{ planAdd('{fid}'); }}"
           style="flex:1;padding:5px 10px;border:1px solid var(--border);border-radius:8px;
                  font-size:0.83em;font-family:inherit;background:white;">
    <button onclick="planAdd('{fid}')"
            style="padding:5px 14px;background:{ACCENT};color:white;border:none;border-radius:8px;
                   font-size:0.8em;font-weight:600;font-family:inherit;cursor:pointer;">+ Add</button>
  </div>
</div>"""


def _family_card_html(fam: dict) -> str:
    fid   = fam.get("id", "")
    name  = escape(fam.get("family_name", "Unnamed Family"))
    addr  = escape(fam.get("address", ""))
    notes = escape(fam.get("notes", ""))
    members = fam.get("members", [])
    members_json = json.dumps(members)

    member_rows = "".join(_member_html(fid, i, m) for i, m in enumerate(members))
    member_empty = '<div style="color:#bbb;font-size:0.82em;font-style:italic;">No members yet.</div>' if not members else ""

    tag_sections = "".join([
        _tag_list_html(fid, "gift_ideas",    "Gift Ideas",     fam.get("gift_ideas", [])),
        _tag_list_html(fid, "food_allergies","Food Allergies", fam.get("food_allergies", [])),
        _tag_list_html(fid, "favorite_things","Favorite Things", fam.get("favorite_things", [])),
    ])

    plans_html = _plan_list_html(fid, fam.get("plans_together", []))

    return f"""
<div id="fam-card-{fid}" class="card"
     style="border-left:5px solid {ACCENT};background:{ACCENT_LIGHT};margin-bottom:14px;">

  <!-- Header row -->
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
    <div style="flex:1;">
      <input type="text" id="fam-name-{fid}" value="{name}"
             oninput="friendMarkDirty('{fid}')"
             style="font-size:1.05em;font-weight:700;color:var(--ink);padding:4px 8px;
                    border:1.5px solid var(--border);border-radius:8px;font-family:inherit;
                    background:white;width:100%;max-width:340px;">
    </div>
    <div style="display:flex;gap:6px;flex-shrink:0;">
      <span id="fam-dirty-{fid}" style="display:none;font-size:0.75em;color:#f59e0b;font-weight:600;align-self:center;">Unsaved</span>
      <button onclick="friendSave('{fid}')"
              style="padding:6px 16px;background:{ACCENT};color:white;border:none;border-radius:8px;
                     font-size:0.82em;font-weight:700;font-family:inherit;cursor:pointer;">Save</button>
      <button onclick="friendDelete('{fid}','{name}')"
              style="padding:6px 10px;background:none;border:1px solid #fca5a5;border-radius:8px;
                     color:#ef4444;font-size:0.82em;font-family:inherit;cursor:pointer;">Delete</button>
    </div>
  </div>
  <div id="fam-status-{fid}" style="font-size:0.8em;color:#22c55e;min-height:16px;margin-bottom:8px;"></div>

  <!-- Address -->
  <div style="margin-bottom:16px;">
    <div style="font-size:0.7em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:4px;">Address</div>
    <textarea id="fam-addr-{fid}" rows="2"
              oninput="friendMarkDirty('{fid}')"
              placeholder="Street, City, State ZIP"
              style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;
                     font-size:0.85em;font-family:inherit;resize:vertical;background:white;">{addr}</textarea>
  </div>

  <!-- Family Members -->
  <div style="margin-bottom:16px;">
    <div style="font-size:0.7em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:8px;">Family Members</div>
    <div id="members-{fid}" data-members='{members_json}'>
      {member_rows or member_empty}
    </div>
    <button onclick="memberAdd('{fid}')"
            style="margin-top:4px;padding:6px 14px;background:white;border:1.5px dashed var(--border);
                   border-radius:8px;font-size:0.82em;font-family:inherit;cursor:pointer;color:{ACCENT};
                   font-weight:600;">+ Add Member</button>
  </div>

  <!-- Tag sections: gift ideas, allergies, favorites -->
  {tag_sections}

  <!-- Plans Together -->
  {plans_html}

  <!-- Notes -->
  <div>
    <div style="font-size:0.7em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:6px;">Notes</div>
    <textarea id="fam-notes-{fid}" rows="3"
              oninput="friendMarkDirty('{fid}')"
              placeholder="Anything to remember about this family…"
              style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;
                     font-size:0.85em;font-family:inherit;resize:vertical;background:white;">{notes}</textarea>
  </div>
</div>"""


def render_friends_page() -> str:
    friends = load_friends()

    all_cards = "".join(_family_card_html(f) for f in friends)
    empty_msg = ""
    if not friends:
        empty_msg = """
<div style="text-align:center;padding:40px 20px;color:#9ca3af;">
  <div style="font-size:2em;margin-bottom:8px;">&#128106;</div>
  <div style="font-size:0.9em;">No families yet. Add your first one below!</div>
</div>"""

    body = f"""
{top_nav()}
<div style="max-width:720px;margin:0 auto;padding:16px;">
  <div style="display:flex;align-items:flex-end;justify-content:space-between;
              margin-bottom:20px;flex-wrap:wrap;gap:10px;">
    <div>
      <div style="font-size:0.7em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
                  color:{ACCENT};margin-bottom:2px;">People</div>
      <h1 style="margin:0;font-size:1.6em;color:var(--ink);">Friends &amp; Families</h1>
      <div style="font-size:0.82em;color:#9ca3af;margin-top:2px;">
        Names, birthdays, addresses, gift ideas, allergies &amp; plans together
      </div>
    </div>
    <button onclick="newFamily()"
            style="padding:9px 20px;background:{ACCENT};color:white;border:none;border-radius:10px;
                   font-size:0.88em;font-weight:700;font-family:inherit;cursor:pointer;">
      + Add Family
    </button>
  </div>

  <div id="friends-list">
    {empty_msg}
    {all_cards}
  </div>
</div>

<script>
(function() {{
  /* In-memory store: fid -> {{ members, gift_ideas, food_allergies, favorite_things, plans_together }} */
  var _store = {{}};

  function _ensureStore(fid) {{
    if (_store[fid]) return;
    _store[fid] = {{ members: [], gift_ideas: [], food_allergies: [], favorite_things: [], plans_together: [] }};
    /* Bootstrap from DOM */
    var mc = document.getElementById('members-' + fid);
    if (mc) {{
      try {{ _store[fid].members = JSON.parse(mc.getAttribute('data-members') || '[]'); }} catch(e) {{}}
    }}
    ['gift_ideas','food_allergies','favorite_things'].forEach(function(key) {{
      var tc = document.getElementById('tags-' + fid + '-' + key);
      if (tc) {{
        try {{ _store[fid][key] = JSON.parse(tc.getAttribute('data-items') || '[]'); }} catch(e) {{}}
      }}
    }});
    var pc = document.getElementById('plans-' + fid);
    if (pc) {{
      try {{ _store[fid].plans_together = JSON.parse(pc.getAttribute('data-items') || '[]'); }} catch(e) {{}}
    }}
  }}

  window.friendMarkDirty = function(fid) {{
    var el = document.getElementById('fam-dirty-' + fid);
    if (el) el.style.display = 'inline';
  }};

  /* ── Members ── */
  window.memberUpdate = function(fid, idx, field, val) {{
    _ensureStore(fid);
    if (!_store[fid].members[idx]) _store[fid].members[idx] = {{}};
    _store[fid].members[idx][field] = val;
    friendMarkDirty(fid);
  }};

  window.memberRemove = function(fid, idx) {{
    _ensureStore(fid);
    _store[fid].members.splice(idx, 1);
    _rebuildMembers(fid);
    friendMarkDirty(fid);
  }};

  window.memberAdd = function(fid) {{
    _ensureStore(fid);
    _store[fid].members.push({{ name: '', role: '', birthday: '' }});
    _rebuildMembers(fid);
    friendMarkDirty(fid);
  }};

  function _rebuildMembers(fid) {{
    var container = document.getElementById('members-' + fid);
    if (!container) return;
    var members = _store[fid].members || [];
    container.setAttribute('data-members', JSON.stringify(members));
    container.innerHTML = members.length === 0
      ? '<div style="color:#bbb;font-size:0.82em;font-style:italic;">No members yet.</div>'
      : members.map(function(m, i) {{
          var name = (m.name||'').replace(/"/g,'&quot;');
          var role = (m.role||'').replace(/"/g,'&quot;');
          var bday = (m.birthday||'');
          return '<div class="member-row" style="display:flex;flex-wrap:wrap;gap:6px;align-items:flex-end;'
            + 'padding:8px;background:#f9fafb;border-radius:8px;margin-bottom:6px;">'
            + '<div style="flex:2;min-width:100px;">'
            + '<div style="font-size:0.68em;color:#9ca3af;margin-bottom:2px;">Name</div>'
            + '<input type="text" value="' + name + '" placeholder="First name" '
            + 'oninput="friendMarkDirty(\\'' + fid + '\\')" '
            + 'onchange="memberUpdate(\\'' + fid + '\\',' + i + ',\\'name\\',this.value)" '
            + 'style="width:100%;padding:5px 8px;border:1px solid var(--border);border-radius:6px;font-size:0.85em;font-family:inherit;background:white;"></div>'
            + '<div style="flex:1;min-width:90px;">'
            + '<div style="font-size:0.68em;color:#9ca3af;margin-bottom:2px;">Role</div>'
            + '<input type="text" value="' + role + '" placeholder="e.g. Dad, Age 8" '
            + 'oninput="friendMarkDirty(\\'' + fid + '\\')" '
            + 'onchange="memberUpdate(\\'' + fid + '\\',' + i + ',\\'role\\',this.value)" '
            + 'style="width:100%;padding:5px 8px;border:1px solid var(--border);border-radius:6px;font-size:0.85em;font-family:inherit;background:white;"></div>'
            + '<div style="flex:1;min-width:120px;">'
            + '<div style="font-size:0.68em;color:#9ca3af;margin-bottom:2px;">Birthday</div>'
            + '<input type="date" value="' + bday + '" '
            + 'oninput="friendMarkDirty(\\'' + fid + '\\')" '
            + 'onchange="memberUpdate(\\'' + fid + '\\',' + i + ',\\'birthday\\',this.value)" '
            + 'style="width:100%;padding:5px 8px;border:1px solid var(--border);border-radius:6px;font-size:0.85em;font-family:inherit;background:white;"></div>'
            + '<button onclick="memberRemove(\\'' + fid + '\\',' + i + ')" '
            + 'style="padding:5px 10px;background:none;border:1px solid #fca5a5;border-radius:6px;color:#ef4444;cursor:pointer;font-size:0.78em;align-self:flex-end;">&#10005;</button>'
            + '</div>';
        }}).join('');
  }}

  /* ── Tags (gift_ideas, food_allergies, favorite_things) ── */
  window.tagAdd = function(fid, key) {{
    _ensureStore(fid);
    var inp = document.getElementById('tag-inp-' + fid + '-' + key);
    if (!inp) return;
    var val = inp.value.trim();
    if (!val) return;
    _store[fid][key].push(val);
    inp.value = '';
    _rebuildTags(fid, key);
    friendMarkDirty(fid);
  }};

  window.tagRemove = function(fid, key, idx) {{
    _ensureStore(fid);
    _store[fid][key].splice(idx, 1);
    _rebuildTags(fid, key);
    friendMarkDirty(fid);
  }};

  function _rebuildTags(fid, key) {{
    var container = document.getElementById('tags-' + fid + '-' + key);
    if (!container) return;
    var items = _store[fid][key] || [];
    container.setAttribute('data-items', JSON.stringify(items));
    if (items.length === 0) {{
      container.innerHTML = '<span style="color:#bbb;font-size:0.82em;font-style:italic;">None yet.</span>';
      return;
    }}
    container.innerHTML = items.map(function(item, i) {{
      var esc = String(item).replace(/&/g,'&amp;').replace(/</g,'&lt;');
      return '<span style="display:inline-flex;align-items:center;gap:4px;background:white;'
        + 'border:1px solid var(--border);border-radius:20px;padding:3px 10px;font-size:0.82em;">'
        + esc
        + '<button onclick="tagRemove(\\'' + fid + '\\',\\'' + key + '\\',' + i + ')" '
        + 'style="background:none;border:none;color:#9ca3af;cursor:pointer;font-size:0.88em;padding:0;line-height:1;">&#10005;</button></span>';
    }}).join(' ');
  }}

  /* ── Plans Together ── */
  window.planAdd = function(fid) {{
    _ensureStore(fid);
    var inp = document.getElementById('plan-inp-' + fid);
    if (!inp) return;
    var val = inp.value.trim();
    if (!val) return;
    _store[fid].plans_together.push({{ text: val, done: false }});
    inp.value = '';
    _rebuildPlans(fid);
    friendMarkDirty(fid);
  }};

  window.planRemove = function(fid, idx) {{
    _ensureStore(fid);
    _store[fid].plans_together.splice(idx, 1);
    _rebuildPlans(fid);
    friendMarkDirty(fid);
  }};

  window.planToggle = function(fid, idx, done) {{
    _ensureStore(fid);
    if (_store[fid].plans_together[idx]) _store[fid].plans_together[idx].done = done;
    friendMarkDirty(fid);
  }};

  window.planUpdate = function(fid, idx, field, val) {{
    _ensureStore(fid);
    if (_store[fid].plans_together[idx]) _store[fid].plans_together[idx][field] = val;
    friendMarkDirty(fid);
  }};

  function _rebuildPlans(fid) {{
    var container = document.getElementById('plans-' + fid);
    if (!container) return;
    var plans = _store[fid].plans_together || [];
    container.setAttribute('data-items', JSON.stringify(plans));
    if (plans.length === 0) {{
      container.innerHTML = '<div style="color:#bbb;font-size:0.82em;font-style:italic;">None yet.</div>';
      return;
    }}
    container.innerHTML = plans.map(function(p, i) {{
      var text = (typeof p === 'string' ? p : (p.text||'')).replace(/"/g,'&quot;');
      var done = typeof p === 'object' && p.done;
      var ds = done ? 'opacity:0.55;text-decoration:line-through;' : '';
      return '<div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">'
        + '<input type="checkbox" ' + (done?'checked':'') + ' '
        + 'onchange="planToggle(\\'' + fid + '\\',' + i + ',this.checked)" '
        + 'style="width:17px;height:17px;accent-color:{ACCENT};flex-shrink:0;">'
        + '<input type="text" value="' + text + '" '
        + 'oninput="friendMarkDirty(\\'' + fid + '\\')" '
        + 'onchange="planUpdate(\\'' + fid + '\\',' + i + ',\\'text\\',this.value)" '
        + 'style="flex:1;padding:5px 8px;border:1px solid var(--border);border-radius:6px;font-size:0.85em;font-family:inherit;background:white;' + ds + '">'
        + '<button onclick="planRemove(\\'' + fid + '\\',' + i + ')" '
        + 'style="padding:4px 8px;background:none;border:1px solid #fca5a5;border-radius:6px;color:#ef4444;cursor:pointer;font-size:0.78em;flex-shrink:0;">&#10005;</button>'
        + '</div>';
    }}).join('');
  }}

  /* ── Save / Delete ── */
  window.friendSave = function(fid) {{
    _ensureStore(fid);

    /* Collect current DOM values before rebuilding */
    var nameEl  = document.getElementById('fam-name-' + fid);
    var addrEl  = document.getElementById('fam-addr-' + fid);
    var notesEl = document.getElementById('fam-notes-' + fid);

    /* Collect members from DOM */
    var mContainer = document.getElementById('members-' + fid);
    if (mContainer) {{
      var mRows = mContainer.querySelectorAll('.member-row');
      var freshMembers = [];
      mRows.forEach(function(row) {{
        var inputs = row.querySelectorAll('input');
        freshMembers.push({{
          name:     (inputs[0] ? inputs[0].value.trim() : ''),
          role:     (inputs[1] ? inputs[1].value.trim() : ''),
          birthday: (inputs[2] ? inputs[2].value : ''),
        }});
      }});
      _store[fid].members = freshMembers;
    }}

    /* Collect tags from DOM */
    ['gift_ideas','food_allergies','favorite_things'].forEach(function(key) {{
      var tc = document.getElementById('tags-' + fid + '-' + key);
      if (tc) {{
        try {{ _store[fid][key] = JSON.parse(tc.getAttribute('data-items')||'[]'); }} catch(e) {{}}
      }}
    }});

    /* Collect plans from DOM */
    var pc = document.getElementById('plans-' + fid);
    if (pc) {{
      try {{ _store[fid].plans_together = JSON.parse(pc.getAttribute('data-items')||'[]'); }} catch(e) {{}}
      /* Also sync any typed-but-not-saved plan text */
      var planInputs = pc.querySelectorAll('input[type=text]');
      planInputs.forEach(function(inp, i) {{
        if (_store[fid].plans_together[i]) _store[fid].plans_together[i].text = inp.value;
      }});
    }}

    var payload = {{
      id: fid,
      family_name: nameEl ? nameEl.value.trim() : '',
      address:     addrEl ? addrEl.value.trim() : '',
      notes:       notesEl ? notesEl.value.trim() : '',
      members:              _store[fid].members,
      gift_ideas:           _store[fid].gift_ideas,
      food_allergies:       _store[fid].food_allergies,
      favorite_things:      _store[fid].favorite_things,
      plans_together:       _store[fid].plans_together,
    }};

    var params = new URLSearchParams();
    params.append('family', JSON.stringify(payload));
    var statusEl = document.getElementById('fam-status-' + fid);
    var dirtyEl  = document.getElementById('fam-dirty-' + fid);
    fetch('/save-friend', {{
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

  window.friendDelete = function(fid, name) {{
    if (!confirm('Remove ' + name + ' from your friends list?')) return;
    var params = new URLSearchParams();
    params.append('id', fid);
    fetch('/delete-friend', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
      body: params.toString()
    }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
      if (d.ok) {{
        var card = document.getElementById('fam-card-' + fid);
        if (card) card.remove();
      }}
    }});
  }};

  window.newFamily = function() {{
    var params = new URLSearchParams();
    params.append('family', JSON.stringify({{ family_name: 'New Family' }}));
    fetch('/save-friend', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
      body: params.toString()
    }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
      if (d.ok && d.id) {{
        window.location.reload();
      }}
    }});
  }};
}})();
</script>
"""
    return html_page("Friends & Families", body)
