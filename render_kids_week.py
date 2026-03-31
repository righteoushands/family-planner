"""
render_kids_week.py — Kids' Week Planning Page

A dedicated page for planning each child's school subjects and tasks
for the upcoming week. Data stored in data/weekly_school_plan/YYYY-WW.json

Structure per week:
{
  "week": "2026-13",
  "children": {
    "JP": {
      "days": {
        "Monday":    {"subjects": ["Math", "English"], "notes": "Math test"},
        "Tuesday":   {"subjects": ["Math", "Latin"], "notes": ""},
        ...
      },
      "weekly_tasks": [
        {"text": "Finish science fair board", "due": "Friday", "done": false},
        ...
      ],
      "notes": "Light week — co-op Wednesday"
    },
    ...
  }
}
"""
import json
import os
from datetime import date, timedelta
from html import escape

from config import CHILDREN, child_color, WEEKDAYS
from ui_helpers import html_page, page_header, render_status_message, top_nav

PLAN_DIR = "data/weekly_school_plan"

SCHOOL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

DEFAULT_SUBJECTS = [
    "Math", "English / Writing", "Latin", "Science", "History",
    "Reading", "Art", "Music", "Physical Education", "Religion / Faith Formation",
]


def _week_key(for_date: date = None) -> str:
    if for_date is None:
        for_date = date.today()
    return for_date.strftime("%Y-%W")


def _week_dates(week_key: str):
    """Return Mon–Sun date objects for a given YYYY-WW key."""
    try:
        year, wk = week_key.split("-")
        # ISO: find the Monday of that week
        jan4 = date(int(year), 1, 4)
        week_start = jan4 + timedelta(weeks=int(wk) - jan4.isocalendar()[1],
                                      days=-jan4.weekday())
        return [week_start + timedelta(days=i) for i in range(7)]
    except Exception:
        today = date.today()
        mon   = today - timedelta(days=today.weekday())
        return [mon + timedelta(days=i) for i in range(7)]


def load_week_plan(week_key: str) -> dict:
    os.makedirs(PLAN_DIR, exist_ok=True)
    path = f"{PLAN_DIR}/{week_key}.json"
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"week": week_key, "children": {}}


def save_week_plan(plan: dict):
    os.makedirs(PLAN_DIR, exist_ok=True)
    path = f"{PLAN_DIR}/{plan['week']}.json"
    try:
        with open(path, "w") as f:
            json.dump(plan, f, indent=2)
    except Exception:
        pass


def render_kids_week_page(week_key: str = None, status: str = "") -> str:
    if not week_key:
        week_key = _week_key()

    plan      = load_week_plan(week_key)
    week_days = _week_dates(week_key)
    mon       = week_days[0]
    sun       = week_days[6]
    week_label = f"{mon.strftime('%B %d')} – {sun.strftime('%B %d, %Y')}"

    # Nav: prev / next week
    prev_key = _week_key(mon - timedelta(days=7))
    next_key = _week_key(mon + timedelta(days=7))

    # Build per-child panels
    child_panels = ""
    for child in CHILDREN:
        c_bg    = child_color(child, "bg")
        c_light = child_color(child, "light")
        c_data  = plan.get("children", {}).get(child, {})
        c_notes = escape(c_data.get("notes", ""))
        c_tasks = c_data.get("weekly_tasks", [])

        # Day columns
        day_cols = ""
        for day in SCHOOL_DAYS:
            day_data = c_data.get("days", {}).get(day, {})
            subj_list = day_data.get("subjects", [])
            day_notes = escape(day_data.get("notes", ""))
            day_date  = next((d for d in week_days if d.strftime("%A") == day), None)
            day_label = f"{day[:3]} {day_date.day}" if day_date else day[:3]

            # Subject chips
            subj_html = ""
            for subj in subj_list:
                subj_html += (
                    f'<div style="display:flex;align-items:center;justify-content:space-between;'
                    f'padding:4px 8px;background:{c_bg}15;border-radius:6px;margin-bottom:4px;gap:6px;">'
                    f'<span style="font-size:0.78em;color:var(--ink);">{escape(subj)}</span>'
                    f'<button onclick="removeSubj(\'{escape(child)}\',\'{day}\',\'{escape(subj)}\')"'
                    f' style="background:none;border:none;color:{c_bg};cursor:pointer;font-size:0.75em;'
                    f'padding:0 2px;line-height:1;">&times;</button>'
                    f'</div>'
                )

            day_cols += (
                f'<div style="flex:1;min-width:120px;">'
                f'<div style="font-size:0.7em;font-weight:800;letter-spacing:.08em;'
                f'text-transform:uppercase;color:{c_bg};margin-bottom:6px;padding:4px 8px;'
                f'background:{c_bg}12;border-radius:6px;">{escape(day_label)}</div>'
                f'<div id="subj-{escape(child)}-{day}">{subj_html}</div>'
                # Subject add button
                f'<button onclick="showAddSubj(\'{escape(child)}\',\'{day}\')" '
                f'style="width:100%;padding:5px 8px;background:transparent;border:1.5px dashed {c_bg}50;'
                f'border-radius:6px;font-size:0.72em;color:{c_bg};cursor:pointer;'
                f'font-family:inherit;margin-top:4px;">+ subject</button>'
                # Notes
                f'<input type="text" placeholder="Notes..." value="{day_notes}" '
                f'onchange="saveDayNotes(\'{escape(child)}\',\'{day}\',this.value)" '
                f'style="width:100%;margin-top:6px;padding:4px 6px;font-size:0.72em;'
                f'border:1px solid var(--border-light);border-radius:6px;font-family:inherit;">'
                f'</div>'
            )

        # Weekly tasks
        _no_tasks_msg = '<p style="font-size:0.82em;color:var(--ink-faint);padding:4px 0;">No tasks yet.</p>'
        task_rows = ""
        for ti, task in enumerate(c_tasks):
            txt    = escape(task.get("text",""))
            due    = escape(task.get("due",""))
            done   = task.get("done", False)
            strike = "text-decoration:line-through;color:var(--ink-faint);" if done else ""
            chkd   = "checked" if done else ""
            task_rows += (
                f'<div style="display:flex;align-items:center;gap:8px;padding:6px 0;'
                f'border-bottom:1px solid var(--border-light);">'
                f'<input type="checkbox" {chkd} onchange="toggleTask(\'{escape(child)}\',{ti},this)" '
                f'style="accent-color:{c_bg};width:16px;height:16px;flex-shrink:0;">'
                f'<span style="flex:1;font-size:0.85em;{strike}">{txt}</span>'
                f'<span style="font-size:0.72em;color:{c_bg};font-weight:600;">{due}</span>'
                f'<button onclick="deleteTask(\'{escape(child)}\',{ti})" '
                f'style="background:none;border:none;color:var(--ink-faint);cursor:pointer;'
                f'font-size:0.82em;padding:0 4px;">&times;</button>'
                f'</div>'
            )

        # Day options for task due date
        due_opts = "".join(f'<option value="{d}">{d[:3]}</option>' for d in SCHOOL_DAYS)
        due_opts += '<option value="This week">This week</option>'

        child_panels += f"""
<div style="border:1.5px solid {c_bg};border-radius:14px;overflow:hidden;margin-bottom:20px;">
  <!-- Child header -->
  <div style="background:{c_bg};padding:12px 16px;display:flex;align-items:center;
              justify-content:space-between;">
    <div style="font-weight:700;font-size:1.05em;color:white;">{escape(child)}</div>
    <div style="display:flex;gap:8px;">
      <button onclick="addAllSubjects('{escape(child)}')"
              style="padding:5px 12px;font-size:0.75em;background:rgba(255,255,255,0.2);
                     color:white;border:1px solid rgba(255,255,255,0.4);border-radius:6px;
                     cursor:pointer;font-family:inherit;">Fill week</button>
      <button onclick="clearWeek('{escape(child)}')"
              style="padding:5px 12px;font-size:0.75em;background:rgba(255,255,255,0.1);
                     color:rgba(255,255,255,0.8);border:1px solid rgba(255,255,255,0.3);
                     border-radius:6px;cursor:pointer;font-family:inherit;">Clear</button>
    </div>
  </div>

  <div style="padding:14px;background:{c_light};">
    <!-- Week notes -->
    <div style="margin-bottom:12px;">
      <label style="font-size:0.72em;font-weight:700;color:{c_bg};text-transform:uppercase;
                    letter-spacing:.08em;">Week notes</label>
      <input type="text" value="{c_notes}" placeholder="e.g. Light week — co-op Wednesday"
             onchange="saveChildNotes('{escape(child)}',this.value)"
             style="width:100%;margin-top:4px;padding:7px 10px;font-size:0.85em;
                    border:1.5px solid {c_bg}30;border-radius:8px;font-family:inherit;
                    background:white;">
    </div>

    <!-- Day columns -->
    <div style="display:flex;gap:10px;overflow-x:auto;padding-bottom:4px;">
      {day_cols}
    </div>

    <!-- Weekly tasks -->
    <div style="margin-top:14px;border-top:1px solid {c_bg}20;padding-top:12px;">
      <div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
                  color:{c_bg};margin-bottom:8px;">Weekly Tasks</div>
      <div id="tasks-{escape(child)}">{task_rows or _no_tasks_msg}</div>
      <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;">
        <input type="text" id="new-task-{escape(child)}" placeholder="Add a task..."
               onkeydown="if(event.key==='Enter')addTask('{escape(child)}')"
               style="flex:1;min-width:140px;padding:6px 10px;font-size:0.82em;
                      border:1.5px solid {c_bg}40;border-radius:8px;font-family:inherit;">
        <select id="task-due-{escape(child)}"
                style="padding:6px 10px;font-size:0.82em;border:1.5px solid {c_bg}40;
                       border-radius:8px;font-family:inherit;">
          {due_opts}
        </select>
        <button onclick="addTask('{escape(child)}')"
                style="padding:6px 14px;background:{c_bg};color:white;border:none;
                       border-radius:8px;font-size:0.82em;font-family:inherit;
                       cursor:pointer;font-weight:600;">+ Add</button>
      </div>
    </div>
  </div>
</div>"""

    # Subject picker modal
    subj_options = "".join(
        f'<button onclick="pickSubj(\'{escape(s)}\')" '
        f'style="padding:6px 12px;border-radius:8px;border:1.5px solid var(--border);'
        f'background:var(--parchment);color:var(--ink);cursor:pointer;font-size:0.82em;'
        f'font-family:inherit;">{escape(s)}</button>'
        for s in DEFAULT_SUBJECTS
    )

    # Serialize current plan for JS
    plan_js = json.dumps(plan)

    body = (
        top_nav() +
        render_status_message(status) + f"""
<div style="display:flex;align-items:flex-start;justify-content:space-between;
            flex-wrap:wrap;gap:8px;padding-top:4px;margin-bottom:16px;">
  <div>
    <div style="font-family:'Cormorant Garamond',Georgia,serif;
                font-size:2rem;font-weight:600;color:var(--ink);">Kids' Week</div>
    <div style="font-size:0.85em;color:var(--ink-muted);margin-top:2px;">{escape(week_label)}</div>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
    <a href="/kids-week?week={escape(prev_key)}"
       style="padding:8px 14px;border:1.5px solid var(--border);border-radius:8px;
              font-size:0.85em;text-decoration:none;color:var(--ink);">&larr; Prev</a>
    <a href="/kids-week"
       style="padding:8px 14px;border:1.5px solid var(--border);border-radius:8px;
              font-size:0.85em;text-decoration:none;color:var(--ink);">This week</a>
    <a href="/kids-week?week={escape(next_key)}"
       style="padding:8px 14px;border:1.5px solid var(--border);border-radius:8px;
              font-size:0.85em;text-decoration:none;color:var(--ink);">Next &rarr;</a>
    <button onclick="saveAll()"
            style="padding:8px 18px;background:var(--ink);color:var(--gold-light);
                   border:none;border-radius:8px;font-size:0.85em;font-weight:700;
                   font-family:inherit;cursor:pointer;">Save week</button>
  </div>
</div>

<div id="save-status" style="font-size:0.82em;color:#27ae60;min-height:18px;
     margin-bottom:8px;font-weight:600;"></div>

{child_panels}

<!-- Subject picker modal -->
<div id="subj-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);
     z-index:1000;padding:20px;overflow-y:auto;">
  <div style="background:white;border-radius:14px;padding:20px;max-width:420px;margin:0 auto;">
    <div style="font-weight:700;font-size:1.05em;margin-bottom:12px;">Add Subject</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">
      {subj_options}
    </div>
    <div style="display:flex;gap:8px;">
      <input type="text" id="custom-subj" placeholder="Or type a custom subject..."
             style="flex:1;padding:7px 10px;font-size:0.85em;border-radius:8px;
                    border:1.5px solid var(--border);font-family:inherit;"
             onkeydown="if(event.key==='Enter')pickSubj(document.getElementById('custom-subj').value)">
      <button onclick="pickSubj(document.getElementById('custom-subj').value)"
              style="padding:7px 14px;background:var(--ink);color:var(--gold-light);
                     border:none;border-radius:8px;font-size:0.85em;font-family:inherit;
                     cursor:pointer;">Add</button>
    </div>
    <button onclick="closeSubjModal()"
            style="margin-top:12px;width:100%;padding:8px;background:transparent;
                   color:var(--ink-muted);border:1.5px solid var(--border);border-radius:8px;
                   font-family:inherit;cursor:pointer;">Cancel</button>
  </div>
</div>

<script>
var _wk    = '{escape(week_key)}';
var _plan  = {plan_js};
var _activeChild = '';
var _activeDay   = '';

if (!_plan.children) _plan.children = {{}};

function _getChild(child) {{
  if (!_plan.children[child]) _plan.children[child] = {{days:{{}}, weekly_tasks:[], notes:''}};
  return _plan.children[child];
}}
function _getDay(child, day) {{
  var c = _getChild(child);
  if (!c.days[day]) c.days[day] = {{subjects:[], notes:''}};
  return c.days[day];
}}

// ── Subjects ────────────────────────────────────────────────────────────────
function showAddSubj(child, day) {{
  _activeChild = child; _activeDay = day;
  document.getElementById('subj-modal').style.display = 'block';
  document.getElementById('custom-subj').value = '';
}}
function closeSubjModal() {{
  document.getElementById('subj-modal').style.display = 'none';
}}
function pickSubj(subj) {{
  if (!subj || !subj.trim()) return;
  subj = subj.trim();
  var day = _getDay(_activeChild, _activeDay);
  if (!day.subjects.includes(subj)) {{
    day.subjects.push(subj);
    _rebuildDaySubjects(_activeChild, _activeDay);
    autoSave();
  }}
  closeSubjModal();
}}
function removeSubj(child, day, subj) {{
  var d = _getDay(child, day);
  d.subjects = d.subjects.filter(function(s){{ return s !== subj; }});
  _rebuildDaySubjects(child, day);
  autoSave();
}}
function _rebuildDaySubjects(child, day) {{
  var el = document.getElementById('subj-' + child + '-' + day);
  if (!el) return;
  var d = _getDay(child, day);
  var c = _plan.children[child];
  var color = document.querySelector('[data-child="'+child+'"]') ?
    document.querySelector('[data-child="'+child+'"]').dataset.color : '#888';
  el.innerHTML = d.subjects.map(function(s) {{
    return '<div style="display:flex;align-items:center;justify-content:space-between;'
      +'padding:4px 8px;background:'+color+'15;border-radius:6px;margin-bottom:4px;gap:6px;">'
      +'<span style="font-size:0.78em;color:var(--ink);">'+s+'</span>'
      +'<button onclick="removeSubj(\\''+child+'\\',\\''+day+'\\',\\''+s+'\\')" '
      +'style="background:none;border:none;color:'+color+';cursor:pointer;font-size:0.75em;">&times;</button>'
      +'</div>';
  }}).join('');
}}

// Fill entire week with default subjects
function addAllSubjects(child) {{
  var defaults = {json.dumps(DEFAULT_SUBJECTS)};
  ['Monday','Tuesday','Wednesday','Thursday','Friday'].forEach(function(day) {{
    var d = _getDay(child, day);
    defaults.forEach(function(s) {{
      if (!d.subjects.includes(s)) d.subjects.push(s);
    }});
    _rebuildDaySubjects(child, day);
  }});
  autoSave();
}}
function clearWeek(child) {{
  if (!confirm('Clear all subjects for ' + child + ' this week?')) return;
  ['Monday','Tuesday','Wednesday','Thursday','Friday'].forEach(function(day) {{
    _getDay(child, day).subjects = [];
    _rebuildDaySubjects(child, day);
  }});
  autoSave();
}}

// ── Notes ────────────────────────────────────────────────────────────────────
function saveDayNotes(child, day, val) {{
  _getDay(child, day).notes = val;
  autoSave();
}}
function saveChildNotes(child, val) {{
  _getChild(child).notes = val;
  autoSave();
}}

// ── Tasks ─────────────────────────────────────────────────────────────────────
function addTask(child) {{
  var inp = document.getElementById('new-task-' + child);
  var due = document.getElementById('task-due-' + child);
  if (!inp || !inp.value.trim()) return;
  _getChild(child).weekly_tasks.push({{text: inp.value.trim(), due: due ? due.value : '', done: false}});
  inp.value = '';
  _rebuildTasks(child);
  autoSave();
}}
function toggleTask(child, idx, cb) {{
  var tasks = _getChild(child).weekly_tasks;
  if (tasks[idx]) tasks[idx].done = cb.checked;
  _rebuildTasks(child);
  autoSave();
}}
function deleteTask(child, idx) {{
  var tasks = _getChild(child).weekly_tasks;
  tasks.splice(idx, 1);
  _rebuildTasks(child);
  autoSave();
}}
function _rebuildTasks(child) {{
  var el = document.getElementById('tasks-' + child);
  if (!el) return;
  var tasks = _getChild(child).weekly_tasks;
  if (tasks.length === 0) {{
    el.innerHTML = '<p style="font-size:0.82em;color:var(--ink-faint);padding:4px 0;">No tasks yet.</p>';
    return;
  }}
  el.innerHTML = tasks.map(function(t, i) {{
    var strike = t.done ? 'text-decoration:line-through;color:var(--ink-faint);' : '';
    return '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border-light);">'
      + '<input type="checkbox" ' + (t.done?'checked':'') + ' onchange="toggleTask(\\''+child+'\\','+i+',this)" '
      + 'style="width:16px;height:16px;flex-shrink:0;">'
      + '<span style="flex:1;font-size:0.85em;'+strike+'">'+t.text+'</span>'
      + '<span style="font-size:0.72em;font-weight:600;color:var(--brown);">'+t.due+'</span>'
      + '<button onclick="deleteTask(\\''+child+'\\','+i+')" '
      + 'style="background:none;border:none;color:var(--ink-faint);cursor:pointer;">&times;</button>'
      + '</div>';
  }}).join('');
}}

// ── Save ──────────────────────────────────────────────────────────────────────
var _saveTimer = null;
function autoSave() {{
  clearTimeout(_saveTimer);
  _saveTimer = setTimeout(saveAll, 1200);
}}
function saveAll() {{
  clearTimeout(_saveTimer);
  fetch('/kids-week-save', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'week=' + encodeURIComponent(_wk) + '&data=' + encodeURIComponent(JSON.stringify(_plan))
  }}).then(function() {{
    var el = document.getElementById('save-status');
    if (el) {{ el.textContent = 'Saved \u2713'; setTimeout(function(){{ el.textContent=''; }}, 2000); }}
  }});
}}
</script>
""")

    return html_page("Kids' Week", body)