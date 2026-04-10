# -*- coding: utf-8 -*-
"""
render_daily_plan.py - Daily plan editor, family grid, dashboard views.

NOTE: All HTML-heavy strings use triple-single-quotes (f-triple-single)
to avoid Python 3.11 f-string conflicts with HTML double-quoted attributes.

Data files:
  data/daily_plans/YYYY-MM-DD.json  - Mom's draggable plan items
  data/day_grids/YYYY-MM-DD.json    - Editable family grid {person: {time: text}}
  data/day_grids/YYYY-MM-DD_meta.json - Grid metadata (published flag)
  data/day_templates/Weekday.json   - Saved day templates
"""
import os, uuid, json as _json
from datetime import date
from html import escape

from safe_utils import ensure_file, safe_save_json, debug_log
from data_helpers import load_family_schedule
from render_schedule_support import generate_half_hour_times, get_eastern_now, _slot_minutes

PLANS_DIR    = "data/daily_plans"
GRIDS_DIR    = "data/day_grids"
TEMPLATES_DIR = "data/day_templates"


# ---------------------------------------------------------------------------
# Plan load / save
# ---------------------------------------------------------------------------
def _plan_path(iso):
    os.makedirs(PLANS_DIR, exist_ok=True)
    return f"{PLANS_DIR}/{iso}.json"

def load_daily_plan(iso):
    return ensure_file(_plan_path(iso), {"iso": iso, "published": False, "items": []})

def save_daily_plan(plan):
    safe_save_json(_plan_path(plan["iso"]), plan)

def seed_from_grid(iso):
    try:
        d = date.fromisoformat(iso)
        weekday = d.strftime("%A")
    except Exception:
        weekday = get_eastern_now().strftime("%A")
    schedule  = load_family_schedule()
    times     = schedule.get("times", []) or generate_half_hour_times()
    day_slots = schedule.get("days", {}).get(weekday, {})
    items    = []
    last_text = ""
    for t in times:
        text = day_slots.get(t, "").strip()
        if not text:
            last_text = ""
            continue
        # Skip if this slot's text is identical to the previous slot's text
        # (avoids duplicating hour-long blocks that only have a :00 entry)
        if text == last_text:
            continue
        last_text = text
        items.append({"id": str(uuid.uuid4())[:8], "time": t,
                      "text": text, "source": "grid",
                      "color": "#6b7280", "done": False})
    return {"iso": iso, "published": False, "items": items}

def get_or_seed_plan(iso):
    plan = load_daily_plan(iso)
    if not plan.get("items"):
        plan = seed_from_grid(iso)
        save_daily_plan(plan)
    return plan


# ---------------------------------------------------------------------------
# Plan item manipulation
# ---------------------------------------------------------------------------
def add_item_to_plan(iso, text, source="manual", color="#888", time=""):
    plan = get_or_seed_plan(iso)
    plan["items"].append({"id": str(uuid.uuid4())[:8], "time": time,
                          "text": text.strip(), "source": source,
                          "color": color, "done": False})
    save_daily_plan(plan)
    return plan

def toggle_plan_item(iso, item_id):
    plan = load_daily_plan(iso)
    for item in plan["items"]:
        if item["id"] == item_id:
            item["done"] = not item.get("done", False)
            save_daily_plan(plan)
            return item["done"]
    return False

def delete_plan_item(iso, item_id):
    plan = load_daily_plan(iso)
    plan["items"] = [i for i in plan["items"] if i["id"] != item_id]
    save_daily_plan(plan)

def reorder_plan_items(iso, ordered_ids):
    plan  = load_daily_plan(iso)
    id_map = {i["id"]: i for i in plan["items"]}
    reordered = [id_map[oid] for oid in ordered_ids if oid in id_map]
    seen = set(ordered_ids)
    for item in plan["items"]:
        if item["id"] not in seen:
            reordered.append(item)
    plan["items"] = reordered
    save_daily_plan(plan)

def update_item_time(iso, item_id, time):
    plan = load_daily_plan(iso)
    for item in plan["items"]:
        if item["id"] == item_id:
            item["time"] = time
            break
    save_daily_plan(plan)

def sort_plan_chronologically(iso):
    plan  = load_daily_plan(iso)
    items = plan.get("items", [])
    timed = [i for i in items if i.get("time", "")]
    unsched = [i for i in items if not i.get("time", "")]
    timed.sort(key=lambda i: _slot_minutes(i.get("time", "")))
    plan["items"] = timed + unsched
    save_daily_plan(plan)

def publish_plan(iso):
    plan = load_daily_plan(iso)
    plan["published"] = True
    save_daily_plan(plan)

def reset_plan(iso):
    save_daily_plan(seed_from_grid(iso))


# ---------------------------------------------------------------------------
# Day grid load / save
# ---------------------------------------------------------------------------
def _grid_path(iso):
    os.makedirs(GRIDS_DIR, exist_ok=True)
    return f"{GRIDS_DIR}/{iso}.json"

def _meta_path(iso):
    os.makedirs(GRIDS_DIR, exist_ok=True)
    return f"{GRIDS_DIR}/{iso}_meta.json"

def load_day_grid(iso):
    return ensure_file(_grid_path(iso), {})

def save_day_grid(iso, grid):
    safe_save_json(_grid_path(iso), grid)

def is_grid_published(iso):
    import os as _os2
    path = _meta_path(iso)
    if not _os2.path.exists(path):
        return False
    try:
        with open(path) as f:
            import json as _j2
            return _j2.load(f).get("published", False)
    except Exception:
        return False

def publish_day_grid(iso):
    safe_save_json(_meta_path(iso), {"published": True})

def seed_day_grid(iso, weekday, people):
    schedule  = load_family_schedule()
    times     = schedule.get("times", []) or generate_half_hour_times()
    mom_slots = schedule.get("days", {}).get(weekday, {})
    grid = {}
    for person in people:
        grid[person] = {}
        for t in times:
            text = mom_slots.get(t, "") or mom_slots.get(t.replace(":30 ", ":00 "), "")
            grid[person][t] = text
    return grid

def get_or_seed_grid(iso, weekday, people):
    grid = load_day_grid(iso)
    if not grid:
        grid = seed_day_grid(iso, weekday, people)
        save_day_grid(iso, grid)
    else:
        # Add any new people not yet in grid
        schedule  = load_family_schedule()
        times     = schedule.get("times", []) or generate_half_hour_times()
        mom_slots = schedule.get("days", {}).get(weekday, {})
        changed = False
        for person in people:
            if person not in grid:
                grid[person] = {t: (mom_slots.get(t, "") or mom_slots.get(t.replace(":30 ", ":00 "), ""))
                                for t in times}
                changed = True
        if changed:
            save_day_grid(iso, grid)
    return grid


# ---------------------------------------------------------------------------
# Day template load / save
# ---------------------------------------------------------------------------
def _template_path(weekday):
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    return f"{TEMPLATES_DIR}/{weekday}.json"

def load_day_template(weekday):
    return ensure_file(_template_path(weekday), {})

def save_day_template(weekday, data):
    safe_save_json(_template_path(weekday), data)


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------
def _get_plan_column_people():
    try:
        from render_settings import load_app_settings
        return load_app_settings().get("plan_columns", [])
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Add-to-plan button (used throughout Plan My Day page)
# ---------------------------------------------------------------------------
def render_add_to_plan_btn(text, source, color="#6b7280", time="", label="+ plan"):
    safe_text  = text.replace("\\", "").replace("'", "\\'").replace('"', "")[:120]
    safe_color = color.replace("'", "")
    safe_time  = time.replace("'", "")
    return (
        f'<button onclick="addToPlan(\'{safe_text}\',\'{source}\','
        f'\'{safe_color}\',\'{safe_time}\')" '
        f'style="padding:2px 8px;font-size:0.75em;background:#f0ebe4;color:#7c4a2d;'
        f'border:1px solid #d7cec5;border-radius:6px;cursor:pointer;'
        f'font-family:inherit;font-weight:600;white-space:nowrap;flex-shrink:0;">'
        f'{label}</button>'
    )


# ---------------------------------------------------------------------------
# Draggable row HTML builder
# Uses string concatenation (not f-strings) to avoid Python 3.11
# triple-double-quote + HTML double-quote conflict.
# ---------------------------------------------------------------------------
def _dp_row_html(iid, text, itime, color, done, src, times):
    ds  = "text-decoration:line-through;color:#bbb;" if done else ""
    dot = {
        "grid":     "background:#9ca3af",
        "calendar": "background:#3498db",
        "task":     "background:#8b5a3c",
        "school":   "background:#6b3fa0",
        "note":     "background:#27ae60",
        "manual":   "background:#e67e22",
    }.get(src, "background:#9ca3af")
    sel = '<option value=""' + (" selected" if not itime else "") + ">--</option>"
    sel += "".join(
        '<option value="' + escape(t) + '"' + (" selected" if t == itime else "") + ">" + escape(t) + "</option>"
        for t in times
    )
    iid_js = iid.replace("'", "\\'")
    inner_row = (
        '<div class="dp-row" draggable="true" data-id="' + iid + '"'
        ' style="display:flex;align-items:center;gap:6px;padding:5px 6px;'
        "border:1px solid #e4dbd2;border-left:3px solid " + color +
        ";border-radius:7px;background:white;cursor:grab;user-select:none;\">"
        '<span style="color:#ccc;font-size:0.9em;flex-shrink:0;cursor:grab;">&#9783;</span>'
        '<span style="width:6px;height:6px;border-radius:50%;' + dot + ';flex-shrink:0;"></span>'
        '<div style="flex:1;min-width:0;overflow:hidden;">'
        '<div style="font-size:0.85em;font-weight:600;' + ds +
        ';white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + text + "</div>"
        '<select onchange="dpSetTime(this.closest(\'[data-id]\').dataset.id,this.value)"'
        ' style="font-size:0.72em;padding:1px 4px;border:1px solid #e0d8d0;'
        'border-radius:4px;background:#fafaf9;max-width:110px;margin-bottom:0;margin-top:1px;">'
        + sel +
        "</select></div>"
        '<button onclick="dpDelete(this.closest(\'[data-id]\').dataset.id)"'
        ' style="flex-shrink:0;padding:2px 6px;font-size:0.72em;background:#f5f5f5;'
        'color:#aaa;border:1px solid #e0d8d0;border-radius:5px;cursor:pointer;font-family:inherit;">x</button>'
        "</div>"
    )
    return (
        '<div class="sw-wrap" style="margin-bottom:4px;">'
        '<div class="sw-inner">' + inner_row + '</div>'
        '<button class="sw-del" onclick="_swDel(this,function(){dpDelete(\'' + iid_js + '\');})"'
        ' aria-label="Delete">&#10005; Delete</button>'
        '</div>'
    )


# ---------------------------------------------------------------------------
# Family grid renderer (editable, full-width)
# ---------------------------------------------------------------------------
def _render_family_grid(iso, weekday, date_label):
    from daily_schedule_engine import CHILDREN
    from config import child_color

    people = _get_plan_column_people() or list(CHILDREN)
    people_with_mom = ["Mom"] + [p for p in people if p != "Mom"]

    schedule = load_family_schedule()
    times    = schedule.get("times", []) or generate_half_hour_times()

    # Get schedule hours from settings
    start_h, end_h = 6, 22
    try:
        from render_settings import load_app_settings
        s = load_app_settings()
        start_h = int(s.get("schedule_start_hour", 6))
        end_h   = int(s.get("schedule_end_hour", 22))
    except Exception:
        pass

    grid      = get_or_seed_grid(iso, weekday, people_with_mom)
    published = is_grid_published(iso)

    now         = get_eastern_now()
    now_minutes = now.hour * 60 + now.minute

    active_times = [t for t in times if start_h * 60 <= _slot_minutes(t) <= end_h * 60]
    if not active_times:
        active_times = times

    col_w = 140  # px per column

    # Build header
    th_style = "background:#f5f0eb;padding:8px;text-align:center;border-left:1px solid #e4dbd2;min-width:" + str(col_w) + "px;"
    header = "<th style='width:68px;min-width:68px;background:#f5f0eb;position:sticky;left:0;z-index:3;border-right:2px solid #e4dbd2;font-size:0.72em;color:#888;padding:6px;text-align:center;'>Time</th>"
    for person in people_with_mom:
        if person == "Mom":
            clr = "#7c4a2d"
        elif person in CHILDREN:
            clr = child_color(person, "bg")
        else:
            clr = "#555"
        header += "<th style='" + th_style + "'><span style='color:" + clr + ";font-weight:700;font-size:0.85em;'>" + escape(person) + "</span></th>"

    # Build rows
    rows = ""
    for t in active_times:
        sm         = _slot_minutes(t)
        is_half    = t.endswith(":30 AM") or t.endswith(":30 PM")
        is_now     = (sm <= now_minutes < sm + 30)
        row_bg     = "#fffbf5" if is_now else ("white" if not is_half else "#fafafa")
        time_color = "#e67e22" if is_now else ("#ccc" if is_half else "#888")
        time_fw    = "bold" if is_now else ("normal" if is_half else "500")
        now_dot    = " &#x1F7E0;" if is_now else ""

        time_cell = (
            "<td style='font-size:0.72em;color:" + time_color + ";font-weight:" + time_fw + ";"
            "padding:2px 6px;white-space:nowrap;position:sticky;left:0;z-index:1;"
            "background:" + ("#fff3e0" if is_now else "#f5f0eb") + ";"
            "border-right:2px solid #e4dbd2;text-align:right;'>"
            + escape(t) + now_dot + "</td>"
        )

        person_cells = ""
        for person in people_with_mom:
            val = grid.get(person, {}).get(t, "")
            if person == "Mom":
                input_bg = "#fdf8f5"
            elif person in CHILDREN:
                input_bg = child_color(person, "light") if not is_now else "#fffbf5"
            else:
                input_bg = "#fafafa"

            # Input uses data attributes; JS reads them for saving
            p_esc = person.replace("'", "\\'").replace('"', "&quot;")
            t_esc = t.replace("'", "\\'").replace('"', "&quot;")
            person_cells += (
                "<td style='padding:1px 2px;border-left:1px solid #e8e0d8;border-bottom:1px solid #f0ebe4;background:" + row_bg + ";'>"
                "<input type='text'"
                " data-person='" + p_esc + "' data-time='" + t_esc + "'"
                " value='" + escape(val).replace("'", "&#39;") + "'"
                " onchange='gridCellChanged(this)'"
                " style='width:100%;border:none;outline:none;background:" + input_bg + ";"
                "font-size:0.78em;padding:4px 6px;font-family:inherit;color:#333;min-width:" + str(col_w - 6) + "px;'>"
                "</td>"
            )

        rows += "<tr>" + time_cell + person_cells + "</tr>"

    pub_badge = ""
    if published:
        pub_badge = "<span style='background:#eef7ee;border:1px solid #c3e0c3;color:#2a5a2a;font-size:0.75em;font-weight:700;padding:2px 8px;border-radius:999px;'>Published to dashboard</span>"

    pub_btn_style = "background:#27ae60;" if not published else "background:#6b7280;"
    pub_btn_label = "Publish to dashboard" if not published else "Re-publish"

    total_min = 68 + len(people_with_mom) * col_w

    # Build people JS list for copy-column UI
    people_js = str(people_with_mom).replace("'", '"')

    return (
        '<div class="card" style="padding:0;overflow:hidden;" id="family-grid-card">'
        '<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:#f9f8f6;border-bottom:1px solid #e4dbd2;flex-wrap:wrap;gap:8px;">'
        '<div style="display:flex;align-items:center;gap:10px;">'
        '<h4 style="margin:0;font-size:0.9rem;">Family day grid &mdash; ' + escape(weekday) + '</h4>'
        + pub_badge +
        '</div>'
        '<div style="display:flex;gap:6px;flex-wrap:wrap;">'
        '<button onclick="gridPublish()" style="padding:4px 12px;font-size:0.78em;' + pub_btn_style + 'color:white;border:none;border-radius:6px;cursor:pointer;font-family:inherit;font-weight:600;">' + pub_btn_label + '</button>'
        '<button onclick="gridCopyColumn()" style="padding:4px 10px;font-size:0.78em;background:#e8f0fe;color:#1a56db;border:1px solid #c3d3fc;border-radius:6px;cursor:pointer;font-family:inherit;font-weight:600;">⇉ Copy column</button>'
        '<button onclick="gridPrint()" style="padding:4px 10px;font-size:0.78em;background:#f0ebe4;color:#555;border:1px solid #d7cec5;border-radius:6px;cursor:pointer;font-family:inherit;">Print grid</button>'
        '<button onclick="gridSaveTemplate(\'' + escape(weekday) + '\')" style="padding:4px 10px;font-size:0.78em;background:#f0ebe4;color:#555;border:1px solid #d7cec5;border-radius:6px;cursor:pointer;font-family:inherit;">Save as template</button>'
        '<button onclick="gridPushToWeekly(\'' + escape(weekday) + '\')" style="padding:4px 10px;font-size:0.78em;background:#f0ebe4;color:#555;border:1px solid #d7cec5;border-radius:6px;cursor:pointer;font-family:inherit;">Push to weekly grid</button>'
        '<button onclick="gridReset()" style="padding:4px 10px;font-size:0.78em;background:#f0ebe4;color:#888;border:1px solid #d7cec5;border-radius:6px;cursor:pointer;font-family:inherit;">Reset</button>'
        '</div></div>'
        # Copy column modal
        '<div id="grid-copy-modal" style="display:none;padding:14px 16px;background:#f0f4ff;'
        'border-bottom:1px solid #c3d3fc;">'
        '<div style="font-size:0.82em;font-weight:700;color:#1a56db;margin-bottom:10px;">⇉ Copy column to another column</div>'
        '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">'
        '<div><label style="font-size:0.75em;color:#555;display:block;margin-bottom:3px;">Copy FROM</label>'
        '<select id="copy-from-col" style="font-size:0.82em;padding:5px 8px;border-radius:6px;border:1px solid #c3d3fc;">'
        + "".join(f'<option value="{escape(p)}">{escape(p)}</option>' for p in people_with_mom) +
        '</select></div>'
        '<div style="font-size:1.2em;color:#1a56db;padding-top:14px;">→</div>'
        '<div><label style="font-size:0.75em;color:#555;display:block;margin-bottom:3px;">Copy TO</label>'
        '<select id="copy-to-col" style="font-size:0.82em;padding:5px 8px;border-radius:6px;border:1px solid #c3d3fc;">'
        + "".join(f'<option value="{escape(p)}">{escape(p)}</option>' for p in people_with_mom) +
        '<option value="__ALL__">— All columns —</option>'
        '</select></div>'
        '<button onclick="gridCopyColumnApply()" '
        'style="padding:6px 14px;font-size:0.82em;background:#1a56db;color:white;border:none;'
        'border-radius:6px;cursor:pointer;font-family:inherit;font-weight:600;margin-top:14px;">Apply</button>'
        '<button onclick="document.getElementById(\'grid-copy-modal\').style.display=\'none\'" '
        'style="padding:6px 10px;font-size:0.82em;background:transparent;border:1px solid #c3d3fc;'
        'border-radius:6px;cursor:pointer;font-family:inherit;margin-top:14px;">Cancel</button>'
        '</div></div>'
        '<div style="overflow-x:auto;max-height:520px;overflow-y:auto;" id="grid-scroll">'
        '<table style="border-collapse:collapse;width:100%;min-width:' + str(total_min) + 'px;" id="family-grid-table">'
        '<thead style="position:sticky;top:0;z-index:4;box-shadow:0 1px 3px rgba(0,0,0,0.08);"><tr>' + header + '</tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table></div>'
        '<div style="padding:6px 14px;background:#faf8f6;border-top:1px solid #f0ebe4;display:flex;align-items:center;gap:10px;">'
        '<span id="grid-status" style="font-size:0.78em;color:#27ae60;flex:1;"></span>'
        '<span style="font-size:0.72em;color:#ccc;">Changes save automatically as you type</span>'
        '</div></div>'
        '<script>'
        'var _gridChanges={};var _gridTimer=null;'
        'var _gridPeople=' + people_js + ';'
        'function gridCellChanged(input){'
        'var p=input.dataset.person,t=input.dataset.time,v=input.value;'
        'if(!_gridChanges[p])_gridChanges[p]={};'
        '_gridChanges[p][t]=v;'
        'clearTimeout(_gridTimer);_gridTimer=setTimeout(gridAutoSave,800);'
        'var el=document.getElementById("grid-status");if(el)el.textContent="Saving...";}'
        'function gridAutoSave(){'
        'if(!Object.keys(_gridChanges).length)return;'
        'fetch("/grid-cell-save",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        'body:"iso="+encodeURIComponent(dpIso)+"&changes="+encodeURIComponent(JSON.stringify(_gridChanges))})'
        '.then(function(){_gridChanges={};var el=document.getElementById("grid-status");'
        'if(el){el.textContent="Saved";setTimeout(function(){el.textContent="";},1800);}});}'
        'function gridFlash(msg){var el=document.getElementById("grid-status");'
        'if(el){el.textContent=msg;setTimeout(function(){el.textContent="";},2500);}}'
        'function gridPublish(){'
        'gridAutoSave();'
        'fetch("/grid-publish",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        'body:"iso="+encodeURIComponent(dpIso)})'
        '.then(function(){gridFlash("Published to dashboard");});}'
        'function gridSaveTemplate(wd){'
        'gridAutoSave();'
        'fetch("/grid-save-template",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        'body:"iso="+encodeURIComponent(dpIso)+"&weekday="+encodeURIComponent(wd)})'
        '.then(function(){gridFlash(wd+" template saved");});}'
        'function gridPushToWeekly(wd){'
        'if(!confirm("Push this grid to the "+wd+" weekly schedule? This overwrites the Mom column for that day."))return;'
        'gridAutoSave();'
        'fetch("/grid-push-weekly",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        'body:"iso="+encodeURIComponent(dpIso)+"&weekday="+encodeURIComponent(wd)})'
        '.then(function(){gridFlash(wd+" weekly grid updated");});}'
        'function gridReset(){'
        'if(!confirm("Reset grid to family schedule template? All edits will be lost."))return;'
        'fetch("/grid-reset",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        'body:"iso="+encodeURIComponent(dpIso)})'
        '.then(function(){location.reload();});}'
        'function gridPrint(){'
        'gridAutoSave();'
        'setTimeout(function(){window.open("/grid-print?iso="+encodeURIComponent(dpIso),"_blank");},600);}'
        # Copy column functions
        'function gridCopyColumn(){'
        'var modal=document.getElementById("grid-copy-modal");'
        'modal.style.display=modal.style.display==="none"?"block":"none";}'
        'function gridCopyColumnApply(){'
        'var fromPerson=document.getElementById("copy-from-col").value;'
        'var toPerson=document.getElementById("copy-to-col").value;'
        'if(fromPerson===toPerson&&toPerson!=="__ALL__"){gridFlash("From and To are the same column.");return;}'
        # Collect all values from the source column
        'var inputs=document.querySelectorAll("#family-grid-table input[data-person]");'
        'var sourceVals={};'
        'inputs.forEach(function(inp){'
        'if(inp.dataset.person===fromPerson)sourceVals[inp.dataset.time]=inp.value;});'
        # Determine target columns
        'var targets=toPerson==="__ALL__"?_gridPeople.filter(function(p){return p!==fromPerson;}):[toPerson];'
        'var confirmMsg=toPerson==="__ALL__"'
        '?"Copy "+fromPerson+"\'s column to ALL other columns? This overwrites them."'
        ':"Copy "+fromPerson+"\'s column to "+toPerson+"? This overwrites that column.";'
        'if(!confirm(confirmMsg))return;'
        # Apply values to target inputs and mark as changed
        'inputs.forEach(function(inp){'
        'if(targets.indexOf(inp.dataset.person)>=0){'
        'var newVal=sourceVals[inp.dataset.time]||"";'
        'inp.value=newVal;'
        'if(!_gridChanges[inp.dataset.person])_gridChanges[inp.dataset.person]={};'
        '_gridChanges[inp.dataset.person][inp.dataset.time]=newVal;}});'
        'gridAutoSave();'
        'document.getElementById("grid-copy-modal").style.display="none";'
        'gridFlash("Column copied \u2713");}'
        '</script>'
    )


# ---------------------------------------------------------------------------
# Plan editor (Mom's draggable list + family grid)
# ---------------------------------------------------------------------------
def render_plan_editor(iso, weekday="", date_label="", sidebar_html=""):
    family_grid = _render_family_grid(iso, weekday, date_label)
    # dpIso must be defined BEFORE the family grid's inline JS runs
    js = (
        "<script>"
        "var dpIso='" + escape(iso) + "';"
        "window.addToPlan=function(text,source,color,time){"
        "color=color||'#6b7280';time=time||'';"
        "fetch('/plan-add-item',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},"
        "body:'iso='+encodeURIComponent(dpIso)"
        "+'&text='+encodeURIComponent(text)+'&time='+encodeURIComponent(time)"
        "+'&source='+encodeURIComponent(source)+'&color='+encodeURIComponent(color)})"
        ".then(r=>r.json());};"
        "</script>"
    )
    return (
        # Define dpIso FIRST so grid JS can use it
        js +
        '<div id="s-plan" class="plan-section">'
        '<div class="plan-section-label">Step 4 &mdash; Build today&#39;s plan</div>'
        + family_grid
        + '</div>'
    )


# ---------------------------------------------------------------------------
# Plan fragment (AJAX reload for dp-list)
# ---------------------------------------------------------------------------
def render_plan_fragment_html(iso):
    plan  = load_daily_plan(iso)
    items = plan.get("items", [])
    times = generate_half_hour_times()
    if not items:
        return "<p class='muted' style='padding:8px 0;font-size:0.85em;'>No items yet.</p>"
    rows = ""
    for item in items:
        rows += _dp_row_html(
            escape(item["id"]),
            escape(item["text"]),
            item.get("time", ""),
            item.get("color", "#888"),
            item.get("done", False),
            item.get("source", "manual"),
            times,
        )
    return rows


# ---------------------------------------------------------------------------
# Dashboard plan timeline (check-off view)
# ---------------------------------------------------------------------------
def render_dashboard_plan(iso):
    plan      = load_daily_plan(iso)
    published = plan.get("published", False)
    items     = plan.get("items", [])
    if not published or not items:
        return ""

    timed   = sorted([i for i in items if i.get("time", "")],
                     key=lambda i: _slot_minutes(i.get("time", "")))
    unsched = [i for i in items if not i.get("time", "")]

    def _item_html(item):
        iid   = escape(item["id"])
        text  = escape(item["text"])
        meta  = escape(item.get("source",""))
        done  = item.get("done", False)
        color = item.get("color", "#6b7280")
        text_style  = "text-decoration:line-through;color:var(--ink-faint);" if done else ""
        circle_bg   = "#2d5016" if done else "transparent"
        circle_border = "#2d5016" if done else "var(--ink-faint)"
        check_inner = ('<svg width="12" height="12" viewBox="0 0 12 12"><polyline points="2,6 5,9 10,3" '
                       'fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
                       if done else "")
        return (
            '<div id="dpi-' + iid + '" class="plan-check-item">'
            '<button onclick="dpCheck(\'' + iid + '\')" class="plan-check-circle' + (' done' if done else '') + '"'
            ' style="background:' + circle_bg + ';border-color:' + circle_border + ';'
            'display:flex;align-items:center;justify-content:center;">'
            + check_inner +
            '</button>'
            '<div style="flex:1;min-width:0;">'
            '<div class="plan-check-text" style="' + text_style + '">' + text + '</div>'
            + (f'<div class="plan-check-meta">{meta}</div>' if meta and meta not in ("manual","grid") else "") +
            '</div>'
            '</div>'
        )

    from itertools import groupby
    timeline = ""
    for time_label, group in groupby(timed, key=lambda i: i.get("time", "")):
        items_html = "".join(_item_html(i) for i in group)
        timeline += (
            '<div style="display:grid;grid-template-columns:56px 1fr;gap:8px;align-items:start;">'
            '<div style="font-size:0.75em;color:var(--ink-faint);font-weight:600;padding-top:14px;white-space:nowrap;text-align:right;">' + escape(time_label) + '</div>'
            '<div style="border-left:1px solid var(--border-light);padding-left:10px;">' + items_html + '</div>'
            '</div>'
        )

    unsched_html = ""
    if unsched:
        unsched_html = (
            '<div style="margin-top:10px;padding-top:10px;border-top:1px solid #f5f0eb;">'
            '<div style="font-size:0.72em;color:#aaa;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;">Unscheduled</div>'
            + "".join(_item_html(i) for i in unsched) +
            '</div>'
        )

    done_count  = sum(1 for i in items if i.get("done"))
    total_count = len(items)
    pct         = int(done_count / total_count * 100) if total_count else 0

    return (
        '<div class="card" style="padding:14px 18px;margin-bottom:16px;" id="dashboard-plan">'
        '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap;gap:8px;">'
        '<h3 style="margin:0;">Today\'s Plan</h3>'
        '<div style="display:flex;align-items:center;gap:10px;">'
        '<span id="dp-prog-label" style="font-size:0.82em;color:#888;">' + str(done_count) + '/' + str(total_count) + ' done</span>'
        '<div style="width:80px;height:6px;background:#f0ebe4;border-radius:3px;overflow:hidden;">'
        '<div id="dp-prog-bar" style="width:' + str(pct) + '%;height:100%;background:#27ae60;border-radius:3px;transition:width 0.3s;"></div>'
        '</div>'
        '<a class="link-button" href="/mom#s-plan" style="font-size:0.78em;">Edit plan</a>'
        '</div></div>'
        '<div id="dp-timeline">' + timeline + unsched_html + '</div>'
        '</div>'
        '<script>'
        'function dpCheck(itemId){'
        'fetch("/plan-toggle-item",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        'body:"iso="+encodeURIComponent("' + escape(iso) + '")+"&id="+encodeURIComponent(itemId)})'
        '.then(r=>r.json()).then(function(d){'
        'var wrap=document.getElementById("dpi-"+itemId);if(!wrap)return;'
        'var btn=wrap.querySelector("button"),span=wrap.querySelector("span");'
        'if(d.done){btn.innerHTML="&#9745;";btn.style.color="#27ae60";span.style.textDecoration="line-through";span.style.opacity="0.45";}'
        'else{btn.innerHTML="&#9744;";btn.style.color="#ccc";span.style.textDecoration="";span.style.opacity="";}'
        'var allBtns=document.querySelectorAll("#dp-timeline button"),done=0;'
        'allBtns.forEach(function(b){if(b.innerHTML.trim()==="&#9745;")done++;});'
        'var total=allBtns.length,pct=total?Math.round(done/total*100):0;'
        'var bar=document.getElementById("dp-prog-bar"),label=document.getElementById("dp-prog-label");'
        'if(bar)bar.style.width=pct+"%";if(label)label.textContent=done+"/"+total+" done";});}'
        '</script>'
    )


# ---------------------------------------------------------------------------
# Dashboard grid view (read-only, shown on home page when published)
# ---------------------------------------------------------------------------
def render_dashboard_grid(iso):
    if not is_grid_published(iso):
        return ""

    from daily_schedule_engine import CHILDREN
    from config import child_color

    try:
        d = date.fromisoformat(iso)
        weekday  = d.strftime("%A")
        date_lbl = d.strftime("%A, %B %d")
    except Exception:
        weekday = date_lbl = "Today"

    people = _get_plan_column_people() or list(CHILDREN)
    people_with_mom = ["Mom"] + [p for p in people if p != "Mom"]

    schedule = load_family_schedule()
    times    = schedule.get("times", []) or generate_half_hour_times()
    grid     = load_day_grid(iso)
    if not grid:
        grid = get_or_seed_grid(iso, weekday, people_with_mom)
    if not grid:
        print("[GRID-DASH] grid still empty after seed, returning ''")
        return ""

    now         = get_eastern_now()
    now_minutes = now.hour * 60 + now.minute

    active_times = [
        t for t in times
        if any(grid.get(p, {}).get(t, "").strip() for p in people_with_mom)
        or (_slot_minutes(t) <= now_minutes < _slot_minutes(t) + 30)
    ]
    if not active_times:
        return ""

    header = "<th style='background:#f5f0eb;width:64px;min-width:64px;font-size:0.72em;color:#888;padding:5px 6px;border-right:1px solid #e4dbd2;'>Time</th>"
    for person in people_with_mom:
        clr = "#7c4a2d" if person == "Mom" else (child_color(person, "bg") if person in CHILDREN else "#555")
        header += "<th style='background:#f5f0eb;padding:5px 8px;text-align:center;font-size:0.8em;border-left:1px solid #e4dbd2;'><span style='color:" + clr + ";font-weight:700;'>" + escape(person) + "</span></th>"

    rows = ""
    for t in active_times:
        sm     = _slot_minutes(t)
        is_now = (sm <= now_minutes < sm + 30)
        is_half = t.endswith(":30 AM") or t.endswith(":30 PM")
        row_bg = "#fffbf5" if is_now else ("white" if not is_half else "#fafafa")
        time_color = "#e67e22" if is_now else ("#ccc" if is_half else "#888")
        now_dot = " &#x1F7E0;" if is_now else ""
        cells = "<td style='font-size:0.7em;color:" + time_color + ";padding:3px 5px;white-space:nowrap;background:#f5f0eb;border-right:1px solid #e4dbd2;text-align:right;'>" + escape(t) + now_dot + "</td>"
        for person in people_with_mom:
            val = grid.get(person, {}).get(t, "").strip()
            clr = "#7c4a2d" if person == "Mom" else (child_color(person, "bg") if person in CHILDREN else "#555")
            cells += (
                "<td style='padding:3px 6px;border-left:1px solid #f0ebe4;border-bottom:1px solid #f5f0eb;background:" + row_bg + ";'>"
                "<span style='font-size:0.78em;color:" + ("#333" if val else "#eee") + ";'>" + escape(val) + "</span></td>"
            )
        rows += "<tr>" + cells + "</tr>"

    return (
        '<div class="card" style="padding:0;overflow:hidden;margin-bottom:16px;">'
        '<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:#f9f8f6;border-bottom:1px solid #e4dbd2;flex-wrap:wrap;gap:8px;">'
        '<h3 style="margin:0;font-size:0.95rem;">Family grid &mdash; ' + escape(date_lbl) + '</h3>'
        '<div style="display:flex;gap:8px;">'
        '<a href="/grid-print?iso=' + escape(iso) + '" target="_blank" class="link-button" style="font-size:0.78em;">Print</a>'
        '<a href="/mom#s-plan" class="link-button" style="font-size:0.78em;">Edit grid</a>'
        '</div></div>'
        '<div style="overflow-x:auto;max-height:360px;overflow-y:auto;">'
        '<table style="border-collapse:collapse;width:100%;">'
        '<thead style="position:sticky;top:0;z-index:2;"><tr>' + header + '</tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table></div></div>'
    )


# ---------------------------------------------------------------------------
# Print page (standalone, landscape)
# ---------------------------------------------------------------------------
def render_grid_print_page(iso):
    from daily_schedule_engine import CHILDREN
    from config import child_color

    try:
        d = date.fromisoformat(iso)
        weekday  = d.strftime("%A")
        date_lbl = d.strftime("%A, %B %d, %Y")
    except Exception:
        weekday = date_lbl = "Today"

    people = _get_plan_column_people() or list(CHILDREN)
    people_with_mom = ["Mom"] + [p for p in people if p != "Mom"]

    schedule = load_family_schedule()
    times    = schedule.get("times", []) or generate_half_hour_times()
    grid     = load_day_grid(iso)

    active_times = [t for t in times if any(grid.get(p, {}).get(t, "").strip() for p in people_with_mom)]
    if not active_times:
        active_times = times[:40]

    col_w = max(80, 480 // max(len(people_with_mom), 1))

    header = "<th style='width:52pt;border:1px solid #ccc;padding:4pt 5pt;background:#f5f0eb;font-size:8pt;'>Time</th>"
    for person in people_with_mom:
        clr = "#7c4a2d" if person == "Mom" else (child_color(person, "bg") if person in CHILDREN else "#555")
        header += "<th style='width:" + str(col_w) + "pt;border:1px solid #ccc;padding:4pt 5pt;background:#f5f0eb;font-size:8pt;color:" + clr + ";'>" + escape(person) + "</th>"

    rows = ""
    for t in active_times:
        is_half = t.endswith(":30 AM") or t.endswith(":30 PM")
        row_bg  = "#fafafa" if is_half else "white"
        t_clr   = "#aaa" if is_half else "#333"
        cells   = "<td style='border:1px solid #ddd;padding:3pt 4pt;font-size:7.5pt;color:" + t_clr + ";background:#f9f9f9;white-space:nowrap;text-align:right;'>" + escape(t) + "</td>"
        for person in people_with_mom:
            val = grid.get(person, {}).get(t, "").strip()
            cells += "<td style='border:1px solid #ddd;padding:3pt 4pt;font-size:8pt;background:" + row_bg + ";'>" + escape(val) + "</td>"
        rows += "<tr>" + cells + "</tr>"

    return (
        "<!doctype html>\n<html><head><meta charset='utf-8'>"
        "<title>Family Grid - " + escape(date_lbl) + "</title>"
        "<style>"
        "*{box-sizing:border-box;margin:0;padding:0;}"
        "body{font-family:Georgia,'Times New Roman',serif;background:white;color:#111;}"
        ".no-print{display:none;}"
        "@media screen{body{padding:20px;}.no-print{display:block;}}"
        "@media print{@page{margin:0.4in;size:landscape;}}"
        "</style></head><body>"
        "<div class='no-print' style='background:#333;color:white;padding:10px 20px;font-family:sans-serif;font-size:13px;margin-bottom:16px;display:flex;gap:12px;align-items:center;'>"
        "<button onclick='window.print()' style='background:#8b5a3c;color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;'>Print</button>"
        "<a href='/' style='color:#ccc;'>Dashboard</a>"
        "<a href='/mom#s-plan' style='color:#ccc;'>Edit grid</a>"
        "</div>"
        "<div style='padding:0 0 12px;'>"
        "<h2 style='font-size:13pt;margin-bottom:3pt;'>" + escape(date_lbl) + " &mdash; Family Schedule</h2>"
        "<p style='font-size:8pt;color:#888;'>Family Planner</p>"
        "</div>"
        "<table style='border-collapse:collapse;width:100%;'>"
        "<thead><tr>" + header + "</tr></thead>"
        "<tbody>" + rows + "</tbody>"
        "</table></body></html>"
    )