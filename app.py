"""
app.py — HTTP server and router only.
All rendering lives in render_*.py modules.
All data I/O lives in data_helpers.py.
"""
import os, uuid
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
from urllib.parse import parse_qs, urlparse

from daily_schedule_engine import CHILDREN, set_task_done
from notes_router import add_note, archive_note, load_notes, save_notes
from school_pdf_engine import (
    approve_school_preview, extract_pdf_text,
    load_school_preview, parse_school_pdf_text, save_school_preview,
)
from safe_utils import safe_save_json

from config import HOST, PORT, ROADMAP_STATUSES, WEEKDAYS
from data_helpers import (
    safe_int, clean_text, clean_child, clean_weekday, clean_priority,
    lines_to_list, sort_school_days, is_math_subject, is_math_test_text,
    load_manual_tasks, save_manual_tasks, active_manual_tasks,
    load_chores_data, save_chores_data,
    load_roadmap, save_roadmap,
    load_mom_notes, save_mom_notes,
    load_calendar_config, save_calendar_config,
    load_calendar_rules, save_calendar_rules,
    load_subscribed_calendars, save_subscribed_calendars,
    load_family_schedule, save_family_schedule,
    load_liturgical_custom, save_liturgical_custom,
    advance_recurring_task,
)
from ui_helpers import parse_urlencoded_body, parse_multipart_form
from render_schedule import render_child_schedule, render_today_all, render_week, render_print_day, render_print_week
from render_schedule_support import render_family_schedule_page, generate_half_hour_times
from render_calendar import render_calendar_page, refresh_calendar
from render_liturgical import render_liturgical_page, render_liturgical_edit_page
from render_readings import render_readings_page
from render_lucy import render_lucy_page, build_lucy_context
from render_memory_book import render_memory_book_page, add_memory_entry, delete_memory_entry
from render_chores import render_chores_page, render_van_roles_page, apply_laundry_defaults, apply_van_rotation
from render_misc import (
    render_dashboard, render_mom_page, render_notes, render_tasks,
    render_roadmap_page, render_planner_page, render_history_page,
    render_school_page, render_school_edit_page, render_now_page,
)
from render_settings import render_settings_page, load_app_settings, save_app_settings
from render_signup import render_signup_page, render_waitlist_admin, save_signup
from render_ai_planner import build_context_packet, render_ai_panel
from render_morning_anchor import save_anchor_state
from render_meals import (
    render_meal_planner_page, render_meal_print_page,
    load_meal_plan, save_meal_plan, load_inventory, save_inventory,
    load_recipes, save_recipe, _build_meal_prompt, _week_key,
)
from render_daily_plan import (
    get_or_seed_plan, add_item_to_plan, toggle_plan_item,
    delete_plan_item, reorder_plan_items, update_item_time,
    publish_plan, reset_plan, render_plan_fragment_html,
    sort_plan_chronologically,
    save_day_template, load_day_grid, save_day_grid,
    get_or_seed_grid, publish_day_grid, render_grid_print_page,
)


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        route = urlparse(self.path)
        path  = route.path
        query = parse_qs(route.query)
        body  = None

        if   path == "/":                body = render_dashboard()
        elif path == "/today":           body = render_today_all(query.get("date",[""])[0])
        elif path == "/set-school-mode":
            # Quick toggle: /set-school-mode?mode=normal|light_week|custom_pause
            _sm = clean_text(query.get("mode",["normal"])[0])
            if _sm in ("normal","light_week","custom_pause"):
                _ss = load_app_settings()
                _ss.setdefault("family_constraints",{})["school_mode"] = _sm
                save_app_settings(_ss)
            self.send_response(302)
            self.send_header("Location", query.get("next",["/today"])[0])
            self.end_headers()
            return
        elif path == "/now":             body = render_now_page()
        elif path == "/week":            body = render_week()
        elif path == "/school":          body = render_school_page()
        elif path == "/kids-week":
            from render_kids_week import render_kids_week_page
            wk = clean_text(query.get("week",[""])[0])
            body = render_kids_week_page(week_key=wk or None)
        elif path == "/plan-tomorrow":
            from render_plan_tomorrow import render_plan_tomorrow_page
            body = render_plan_tomorrow_page()
        elif path == "/plan-today":
            from render_plan_tomorrow import render_plan_tomorrow_page
            body = render_plan_tomorrow_page(for_date=date.today())
        elif path == "/plan-week":
            from render_plan_week import render_plan_week_page
            wk = clean_text(query.get("week",[""])[0])
            body = render_plan_week_page(week_key=wk or None)
        elif path == "/plan-month":
            from render_plan_month import render_plan_month_page
            mk = clean_text(query.get("month",[""])[0])
            body = render_plan_month_page(month_key=mk or None)
        elif path == "/plan-year":
            from render_plan_year import render_plan_year_page
            yr = clean_text(query.get("year",[""])[0])
            body = render_plan_year_page(year=yr or None)
        elif path == "/plan-quarter":
            from render_plan_quarter import render_plan_quarter_page
            qk = clean_text(query.get("quarter",[""])[0])
            body = render_plan_quarter_page(quarter_key=qk or None)
        elif path == "/virtues":
            from render_virtues import render_virtues_dashboard
            body = render_virtues_dashboard()
        elif path == "/5am":
            from render_5am import render_5am_page
            ds = clean_text(query.get("date",[""])[0])
            body = render_5am_page(date_str=ds or None)
        elif path == "/liturgy-hours":
            from render_liturgy_hours import render_liturgy_hours_page
            ds = clean_text(query.get("date",[""])[0])
            body = render_liturgy_hours_page(date_str=ds or None)
        elif path == "/prayer-intentions":
            from render_prayer import render_prayer_page
            status = clean_text(query.get("msg",[""])[0]).replace("+"," ")
            body = render_prayer_page(status)
        elif path.startswith("/prayer-photo/"):
            filename = path[len("/prayer-photo/"):]
            # Sanitise — no path traversal
            filename = filename.replace("/","").replace("\\","").replace("..","")
            photo_path = f"data/prayer/photos/{filename}"
            try:
                with open(photo_path, "rb") as f:
                    photo_data = f.read()
                ext = filename.rsplit(".",1)[-1].lower() if "." in filename else "jpg"
                mime = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png",
                        "gif":"image/gif","webp":"image/webp"}.get(ext,"image/jpeg")
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(photo_data)))
                self.send_header("Cache-Control", "max-age=86400")
                self.end_headers()
                try: self.wfile.write(photo_data)
                except BrokenPipeError: pass
            except Exception:
                self.send_response(404)
                self.end_headers()
            return
        elif path.startswith("/prayer-intention/share/"):
            from render_prayer import render_share_page
            token = path[len("/prayer-intention/share/"):]
            body = render_share_page(clean_text(token))
        elif path == "/virtues/me":
            from render_virtues import render_virtue_me_page
            vp = clean_text(query.get("virtue",[""])[0])
            body = render_virtue_me_page(virtue_pick=vp or None)
        elif path == "/virtues/family":
            from render_virtues import render_virtue_family_page
            vp = clean_text(query.get("virtue",[""])[0])
            body = render_virtue_family_page(virtue_pick=vp or None)
        elif path.startswith("/virtues/child/"):
            from render_virtues import render_virtue_child_page
            child_id = path[len("/virtues/child/"):]
            vp = clean_text(query.get("virtue",[""])[0])
            body = render_virtue_child_page(child_id, virtue_pick=vp or None)
        elif path == "/school/edit":     body = render_school_edit_page(clean_child(query.get("child",[""])[0]))
        elif path == "/chores":          body = render_chores_page(status_message=query.get("msg",[""])[0])
        elif path == "/van-roles":       body = render_van_roles_page()
        elif path == "/print/day":       body = render_print_day(query.get("date",[""])[0])
        elif path == "/print/week":      body = render_print_week()
        elif path == "/notes":           body = render_notes()
        elif path == "/tasks":           body = render_tasks()
        elif path == "/mom":             body = render_mom_page(target_date_str=query.get("date",[""])[0])
        elif path == "/roadmap":         body = render_roadmap_page()
        elif path == "/signup":           body = render_signup_page()
        elif path == "/waitlist":         body = render_waitlist_admin(False)
        elif path == "/family-schedule": body = render_family_schedule_page()
        elif path == "/calendar":        body = render_calendar_page()
        elif path == "/planner":         body = render_planner_page()
        elif path == "/readings":         body = render_readings_page(date_str=query.get("date",[""])[0])
        elif path == "/lucy":             body = render_lucy_page(iso=query.get("date",[""])[0])
        elif path == "/memory-book":      body = render_memory_book_page()
        elif path == "/liturgical":      body = render_liturgical_page()
        elif path == "/prayer":           body = render_liturgical_page()
        elif path == "/liturgical/edit": body = render_liturgical_edit_page(query.get("date",[""])[0])
        elif path == "/settings":        body = render_settings_page(status_message=query.get("msg",[""])[0])
        elif path == "/history":         body = render_history_page(status_message=query.get("msg",[""])[0])
        elif path == "/plan-fragment":
            iso  = clean_text(query.get("iso",[""])[0]) or date.today().isoformat()
            frag = render_plan_fragment_html(iso)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            try: self.wfile.write(frag.encode())
            except BrokenPipeError: pass
            return

        elif path == "/grid-print":
            iso  = clean_text(query.get("iso",[""])[0]) or date.today().isoformat()
            html = render_grid_print_page(iso)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/mom-step":
            step_id = clean_text(query.get("step",["morning"])[0])
            iso_q   = clean_text(query.get("iso",[""])[0]) or date.today().isoformat()
            from render_misc import render_mom_step_fragment
            html = render_mom_step_fragment(step_id, iso_q)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/meals":
            wk   = clean_text(query.get("week",[""])[0])
            body = render_meal_planner_page(week_key=wk or None)
        elif path == "/meal-print":
            wk   = clean_text(query.get("week",[""])[0])
            html = render_meal_print_page(week_key=wk or None)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            try: self.wfile.write(html.encode())
            except BrokenPipeError: pass
            return
        elif path == "/recipes":
            from render_meals import render_recipes_page
            body = render_recipes_page()
        elif path == "/api-key":
            settings = load_app_settings()
            key = settings.get("anthropic_api_key","")
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.end_headers()
            import json as _json
            try: self.wfile.write(_json.dumps({"key": key}).encode())
            except BrokenPipeError: pass
            return
        elif path.startswith("/schedule/"):
            child = path[len("/schedule/"):]
            # URL-decode and match against CHILDREN (case-insensitive)
            child = child.replace("%20"," ").replace("+"," ").split("?")[0]
            matched = next((c for c in CHILDREN if c.lower() == child.lower() or c.replace(" ","_") == child), None)
            if not matched:
                self.send_response(404); self.end_headers(); return
            body = render_child_schedule(matched, query.get("date",[""])[0])
        elif path == "/calendar/refresh":
            refresh_calendar(force=True)
            self.send_response(303); self.send_header("Location","/calendar"); self.end_headers(); return
        elif path.startswith("/lucy-child-brief/"):
            import json as _json
            child_slug = path[len("/lucy-child-brief/"):].strip().lower()
            matched_child = next((c for c in CHILDREN if c.lower() == child_slug), None)
            if not matched_child:
                self.send_response(404); self.end_headers(); return
            try:
                from render_lucy import get_child_lucy_brief
                from render_child_goals import load_child_goals
                from daily_schedule_engine import build_schedule_payload, generate_day_packet
                from datetime import date as _date2
                _today = _date2.today()
                _pkt = generate_day_packet(_today.isoformat())
                _payload = build_schedule_payload(matched_child, _pkt["weekday"], _pkt["date_label"], _pkt["iso"])
                _tasks = []
                for _item in (_payload.get("manual_task_items", []) + _payload.get("chore_items", [])):
                    _tasks.append(_item.get("label", _item.get("text", "")))
                for _blk in _payload.get("school_blocks", []):
                    for _si in _blk.get("items", []):
                        _tasks.append(_si.get("label", _si.get("text", "")))
                _goals = [g for g in load_child_goals(matched_child) if not g.get("archived")]
                _brief = get_child_lucy_brief(matched_child, _tasks, _goals)
                from html import escape as _esc
                _html = _brief.replace("\n\n", "</p><p>").replace("\n", " ")
                _html = f"<p>{_html}</p>" if _html else ""
            except Exception as _e:
                _html = ""
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try: self.wfile.write(_json.dumps({"html": _html}).encode())
            except BrokenPipeError: pass
            return
        else:
            self.send_response(404); self.end_headers(); return

        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.end_headers()
        try:
            self.wfile.write(body.encode())
        except BrokenPipeError:
            pass

    def _send_html(self, body: str):
        """Helper for POST handlers that return HTML directly."""
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.end_headers()
        try:
            self.wfile.write(body.encode())
        except BrokenPipeError:
            pass

    def do_POST(self):
        path     = urlparse(self.path).path
        redirect = "/"

        if path == "/school-upload" or path == "/prayer-intention-add":
            form = parse_multipart_form(self)

            if path == "/school-upload":
                child = clean_child(form.getfirst("child",""))
                raw_text = clean_text(form.getfirst("raw_text",""))
                filename = "pasted_text"
                uploaded = form["file"] if "file" in form else None
                file_bytes = b""; uploaded_name = ""
                if uploaded is not None and getattr(uploaded,"filename",""):
                    uploaded_name = uploaded.filename
                    file_bytes = uploaded.file.read() if uploaded.file else b""
                if uploaded_name: filename = uploaded_name
                if not raw_text and file_bytes:
                    if uploaded_name.lower().endswith(".pdf"): raw_text = extract_pdf_text(file_bytes)
                    else:
                        try:    raw_text = file_bytes.decode("utf-8")
                        except: raw_text = file_bytes.decode("latin-1", errors="ignore")
                if child and raw_text:
                    save_school_preview(child, filename, raw_text, parse_school_pdf_text(raw_text, child))
                redirect = "/school#top"

            elif path == "/prayer-intention-add":
                import json as _pj
                title_in = clean_text(form.getfirst("title", ""))
                desc_in  = clean_text(form.getfirst("description", ""))
                photo_bytes = None
                photo_ext   = "jpg"
                photo_error = ""
                try:
                    photo_field = form["photo"] if "photo" in form else None
                    if photo_field:
                        fname = getattr(photo_field, "filename", "") or ""
                        if fname:
                            photo_ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "jpg"
                            raw_bytes = photo_field.file.read() if photo_field.file else b""
                            if raw_bytes and len(raw_bytes) > 100:
                                photo_bytes = raw_bytes
                            elif raw_bytes:
                                photo_error = f"Photo too small ({len(raw_bytes)} bytes) — skipped"
                except Exception as _pe:
                    photo_error = str(_pe)
                    print(f"[PRAYER] Photo error: {_pe}")
                if title_in:
                    from render_prayer import add_intention
                    add_intention(title_in, desc_in, photo_bytes, photo_ext)
                    out = _pj.dumps({"ok": True, "photo_error": photo_error}).encode()
                else:
                    out = _pj.dumps({"ok": False, "error": "Title required"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

        else:
            data = parse_urlencoded_body(self)

            if path == "/toggle-task":
                set_task_done(data.get("task_id",[""])[0], data.get("new_value",["false"])[0]=="true")
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                self.wfile.write(b'{"ok":true}'); return

            elif path == "/add-note":
                text = clean_text(data.get("text",[""])[0])
                if text: add_note(text)
                redirect = "/notes#top"

            elif path == "/archive-note":
                archive_note(data.get("id",[""])[0]); redirect = "/notes#top"

            elif path == "/convert-note":
                note_id=data.get("id",[""])[0]; assigned_to=clean_text(data.get("assigned_to",[""])[0])
                due_date=clean_text(data.get("due_date",[""])[0]); priority=clean_priority(data.get("priority",["MEDIUM"])[0])
                notes=load_notes(); tasks=load_manual_tasks()
                for note in notes:
                    if note.get("id")==note_id:
                        tasks.append({"text":clean_text(note.get("text","")),"assigned_to":assigned_to,"due_date":due_date,"priority":priority,"status":"active"})
                        note["status"]="archived"; break
                save_manual_tasks(tasks); save_notes(notes); redirect="/notes"

            elif path == "/add-task":
                text=clean_text(data.get("text",[""])[0]); assigned_to=clean_text(data.get("assigned_to",[""])[0])
                due_date=clean_text(data.get("due_date",[""])[0]); priority=clean_priority(data.get("priority",["MEDIUM"])[0])
                is_recurring=data.get("recurring",[""])[0]=="true"
                iv=safe_int(data.get("interval_value",["1"])[0],1); iu=clean_text(data.get("interval_unit",["weeks"])[0])
                if iu not in ("days","weeks","months"): iu="weeks"
                if iv<1: iv=1
                if text:
                    tasks=load_manual_tasks()
                    t={"text":text,"assigned_to":assigned_to,"due_date":due_date,"priority":priority,"status":"active","recurring":is_recurring}
                    if is_recurring: t["interval_value"]=iv; t["interval_unit"]=iu
                    tasks.append(t); save_manual_tasks(tasks)
                ru=data.get("return_url",["/tasks"])[0]
                redirect=(ru if ru in ("/tasks","/mom") else "/tasks") + "#top"

            elif path == "/task-done":
                idx=safe_int(data.get("index",["0"])[0],0); tasks=load_manual_tasks()
                if 0<=idx<len(tasks) and isinstance(tasks[idx],dict):
                    t=tasks[idx]; tasks[idx]=advance_recurring_task(t) if t.get("recurring") else {**t,"status":"done"}
                    save_manual_tasks(tasks)
                redirect=data.get("return_url",["/tasks"])[0] + "#top"

            elif path == "/task-delete":
                idx=safe_int(data.get("index",["0"])[0],0); tasks=load_manual_tasks()
                if 0<=idx<len(tasks) and isinstance(tasks[idx],dict):
                    tasks[idx]["status"]="inactive"; save_manual_tasks(tasks)
                redirect="/tasks#top"

            elif path == "/approve-school-preview":
                child=clean_child(data.get("child",[""])[0])
                if child: approve_school_preview(child)
                redirect="/school#top"

            elif path == "/reparse-school-preview":
                child=clean_child(data.get("child",[""])[0]); raw_text=clean_text(data.get("raw_text",[""])[0])
                preview=load_school_preview(child)
                if child and raw_text and preview:
                    save_school_preview(child, preview.get("filename","edited_preview"), raw_text, parse_school_pdf_text(raw_text,child))
                redirect=f"/school/edit?child={child}"

            elif path == "/save-school-preview-edits":
                child=clean_child(data.get("child",[""])[0]); preview=load_school_preview(child)
                if child and preview:
                    dc=safe_int(data.get("day_count",["0"])[0],0); parsed_days=[]
                    for di in range(dc):
                        wd=clean_weekday(data.get(f"weekday__{di}",[""])[0]); dl=clean_text(data.get(f"day_label__{di}",[""])[0])
                        bc=safe_int(data.get(f"block_count__{di}",["0"])[0],0); bwo=[]
                        for bi in range(bc):
                            s=clean_text(data.get(f"subject__{di}__{bi}",[""])[0]); a=clean_text(data.get(f"assignment__{di}__{bi}",[""])[0])
                            o=safe_int(data.get(f"order__{di}__{bi}",["0"])[0],bi+1)
                            if data.get(f"delete__{di}__{bi}",[""])[0]=="yes": continue
                            if not s and not a: continue
                            bwo.append({"order":o,"subject":s or "Unsorted","assignment_text":a})
                        bwo.sort(key=lambda b:(b["order"],b["subject"].lower()))
                        blocks=[{"subject":b["subject"],"assignment_text":b["assignment_text"],"is_math":is_math_subject(b["subject"]),"is_math_test":is_math_test_text(b["subject"],b["assignment_text"])} for b in bwo]
                        parsed_days.append({"weekday":wd,"day_label":dl,"blocks":blocks})
                    parsed_days=sort_school_days(parsed_days)
                    save_school_preview(child,preview.get("filename","edited_preview"),preview.get("raw_text",""),{"child":child,"parsed_days":parsed_days,"raw_text":preview.get("raw_text","")})
                redirect=f"/school/edit?child={child}"

            elif path == "/save-chores":
                chores={"boys":{}}
                for child in CHILDREN:
                    chores["boys"][child]={"daily":lines_to_list(data.get(f"daily__{child}",[""])[0]),"weekly":{wd:lines_to_list(data.get(f"weekly__{child}__{wd}",[""])[0]) for wd in WEEKDAYS}}
                save_chores_data(chores); redirect="/chores#top"

            elif path == "/apply-laundry":
                save_chores_data(apply_laundry_defaults(load_chores_data()))
                redirect="/chores?msg=Laundry+schedule+applied+to+weekly+chores#top"

            elif path == "/signup-submit":
                import urllib.parse as _up
                name       = clean_text(data.get("name",[""])[0])
                email      = clean_text(data.get("email",[""])[0])
                if not name or not email:
                    body = render_signup_page(error="Please enter your name and email address.")
                    self._send_html(body); return
                entry = {
                    "submitted_at":      datetime.now().isoformat(timespec="seconds"),
                    "name":              name,
                    "email":             email,
                    "num_children":      clean_text(data.get("num_children",[""])[0]),
                    "child_ages":        clean_text(data.get("child_ages",[""])[0]),
                    "hs_years":          clean_text(data.get("hs_years",[""])[0]),
                    "family_type":       clean_text(data.get("family_type",[""])[0]),
                    "device":            clean_text(data.get("device",[""])[0]),
                    "willingness_to_pay":clean_text(data.get("willingness_to_pay",[""])[0]),
                    "price_range":       clean_text(data.get("price_range",[""])[0]),
                    "biggest_challenge": clean_text(data.get("biggest_challenge",[""])[0]),
                    "other_notes":       clean_text(data.get("other_notes",[""])[0]),
                    "notify":            clean_text(data.get("notify",["Yes"])[0]),
                    "current_tools":     [clean_text(v) for v in data.get("current_tools",[])],
                    "features":          [clean_text(v) for v in data.get("features",[])],
                }
                save_signup(entry)
                body = render_signup_page(submitted=True)
                self._send_html(body); return

            elif path == "/waitlist":
                pw = clean_text(data.get("pw",[""])[0])
                from render_settings import load_app_settings as _las
                _s  = _las()
                ok  = (pw == _s.get("waitlist_password","admin2026"))
                body = render_waitlist_admin(ok)
                self._send_html(body); return

            elif path == "/apply-canonical-chores":
                from render_chores import apply_canonical_chores
                save_chores_data(apply_canonical_chores(load_chores_data()))
                redirect = "/chores?msg=Canonical+chore+defaults+applied#top"

            elif path == "/apply-kitchen-rotation":
                from render_chores import (
                    get_kitchen_roles,
                    KITCHEN_ROLE_A_MORNING, KITCHEN_ROLE_A_EVENING,
                    KITCHEN_ROLE_B_MORNING, KITCHEN_ROLE_B_EVENING,
                )
                chores = load_chores_data()
                boys   = chores.get("boys", {})
                roles  = get_kitchen_roles()
                for child in ("JP", "Joseph"):
                    role    = roles[child]
                    morning = KITCHEN_ROLE_A_MORNING if role == "A" else KITCHEN_ROLE_B_MORNING
                    evening = KITCHEN_ROLE_A_EVENING if role == "A" else KITCHEN_ROLE_B_EVENING
                    boys.setdefault(child, {"daily": [], "weekly": {}})
                    existing    = boys[child].get("daily", [])
                    non_kitchen = [l for l in existing if not l.startswith("KITCHEN")]
                    boys[child]["daily"] = non_kitchen + [""] + morning + [""] + evening
                chores["boys"] = boys
                save_chores_data(chores)
                redirect = "/chores?msg=Kitchen+rotation+applied+to+daily+chores#top"

            elif path == "/apply-van-rotation":
                save_chores_data(apply_van_rotation(load_chores_data())); redirect="/van-roles#top"

            elif path == "/mom-add-note":
                text=clean_text(data.get("text",[""])[0])
                if text:
                    notes=load_mom_notes(); notes.append({"id":str(uuid.uuid4()),"text":text,"status":"active"}); save_mom_notes(notes)
                redirect="/mom#top"

            elif path == "/mom-archive-note":
                note_id=data.get("id",[""])[0]; notes=load_mom_notes()
                for note in notes:
                    if str(note.get("id",""))==note_id: note["status"]="archived"; break
                save_mom_notes(notes); redirect="/mom#top"

            elif path == "/history-restore": redirect="/roadmap#top"

            elif path == "/plan-add-item":
                iso    = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                text   = clean_text(data.get("text",[""])[0])
                source = clean_text(data.get("source",["manual"])[0])
                color  = clean_text(data.get("color",["#6b7280"])[0])
                itime  = clean_text(data.get("time",[""])[0])
                if text:
                    plan = add_item_to_plan(iso, text, source, color, itime)
                    count = len(plan.get("items",[]))
                else:
                    count = 0
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                import json as _json
                try: self.wfile.write(_json.dumps({"ok":True,"count":count}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/plan-toggle-item":
                iso     = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                item_id = clean_text(data.get("id",[""])[0])
                done    = toggle_plan_item(iso, item_id)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                import json as _json
                try: self.wfile.write(_json.dumps({"ok":True,"done":done}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/plan-delete-item":
                iso     = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                item_id = clean_text(data.get("id",[""])[0])
                delete_plan_item(iso, item_id)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-reorder":
                iso  = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                ids  = clean_text(data.get("ids",[""])[0]).split(",")
                ids  = [i.strip() for i in ids if i.strip()]
                reorder_plan_items(iso, ids)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-set-time":
                iso     = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                item_id = clean_text(data.get("id",[""])[0])
                itime   = clean_text(data.get("time",[""])[0])
                update_item_time(iso, item_id, itime)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-publish":
                iso = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                publish_plan(iso)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-reset":
                iso = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                reset_plan(iso)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/anchor-save":
                import json as _json
                iso      = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                raw_data = clean_text(data.get("data",["{}"])[0])
                try:
                    updates_flat = _json.loads(raw_data)
                    # Support dot-notation keys like "evening.dinner_cleanup"
                    from render_daily_plan import load_daily_plan, save_daily_plan
                    plan   = load_daily_plan(iso)
                    anchor = plan.get("anchor", {})
                    for k, v in updates_flat.items():
                        if "." in k:
                            section, sub = k.split(".", 1)
                            anchor.setdefault(section, {})[sub] = v
                        else:
                            anchor[k] = v
                    plan["anchor"] = anchor
                    save_daily_plan(plan)
                except Exception as e:
                    debug_log("anchor-save error:", str(e))
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-sort":
                iso = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                sort_plan_chronologically(iso)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/grid-save-template":
                import json as _json
                iso     = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                weekday = clean_text(data.get("weekday",[""])[0])
                if weekday:
                    grid = load_day_grid(iso)
                    save_day_template(weekday, {"weekday": weekday, "grid": grid})
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/grid-push-weekly":
                import json as _json
                iso     = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                weekday = clean_text(data.get("weekday",[""])[0])
                if weekday:
                    grid = load_day_grid(iso)
                    # Push Mom's column to the family schedule
                    mom_slots = grid.get("Mom", {})
                    if mom_slots:
                        schedule = load_family_schedule()
                        schedule.setdefault("days", {})[weekday] = {k:v for k,v in mom_slots.items() if v.strip()}
                        if not schedule.get("times"):
                            schedule["times"] = generate_half_hour_times()
                        save_family_schedule(schedule)
                        save_day_template(weekday, {"weekday": weekday, "grid": grid})
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/grid-cell-save":
                import json as _json
                iso     = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                raw     = clean_text(data.get("changes",["{}"])[0])
                try:
                    changes = _json.loads(raw)
                    grid    = load_day_grid(iso)
                    for person, slots in changes.items():
                        grid.setdefault(person, {}).update(slots)
                    save_day_grid(iso, grid)
                except Exception as e:
                    debug_log("grid-cell-save error:", str(e))
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/grid-publish":
                from datetime import datetime as _dt
                from render_schedule_support import get_eastern_now
                iso = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                publish_day_grid(iso)
                try:
                    now_et = get_eastern_now()
                    ts = now_et.strftime("%B %d at %-I:%M %p")
                except Exception:
                    ts = _dt.now().strftime("%B %d at %I:%M %p")
                import json as _json
                payload = _json.dumps({"ok": True, "published_at": ts}).encode()
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(payload)
                except BrokenPipeError: pass
                return

            elif path == "/grid-reset":
                iso = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                try:
                    from render_daily_plan import _get_plan_column_people
                    from daily_schedule_engine import CHILDREN
                    d       = date.fromisoformat(iso)
                    weekday = d.strftime("%A")
                    people  = _get_plan_column_people() or list(CHILDREN)
                    people_with_mom = ["Mom"] + [p for p in people if p != "Mom"]
                    from render_daily_plan import seed_day_grid
                    grid = seed_day_grid(iso, weekday, people_with_mom)
                    save_day_grid(iso, grid)
                except Exception as e:
                    debug_log("grid-reset error:", str(e))
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-ai-suggest":
                import json as _json, urllib.request as _req
                iso      = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                mode     = clean_text(data.get("mode",["ask"])[0])
                question = clean_text(data.get("question",[""])[0])
                # Load API key from settings
                settings_data = load_app_settings()
                api_key = settings_data.get("family_constraints",{}).get("anthropic_api_key","").strip()
                if not api_key:
                    self.send_response(400)
                    self.send_header("Content-Type","text/plain")
                    self.end_headers()
                    try: self.wfile.write(b"No API key set. Go to Settings -> Family & AI to add your Anthropic API key.")
                    except BrokenPipeError: pass
                    return
                try:
                    d = date.fromisoformat(iso)
                    weekday    = d.strftime("%A")
                    date_label = d.strftime("%B %d, %Y")
                except Exception:
                    weekday = date_label = iso
                context = build_context_packet(iso, weekday, date_label)
                # Build the user message based on mode
                if mode == "review":
                    user_msg = (
                        "Please review today's full schedule. Look at the family grid, each child's assignments, "
                        "and the current plan. Flag: (1) any time where James has no supervisor, "
                        "(2) any child who is overloaded or has unexplained gaps, "
                        "(3) any conflicts with calendar events, "
                        "(4) any sequencing problems. Be specific about time slots. "
                        "Format as a short bulleted list, then a 1-2 sentence summary."
                    )
                elif mode == "generate":
                    extra = f" Additional constraints for today: {question}" if question else ""
                    user_msg = (
                        f"Build an optimal schedule for today ({weekday}).{extra} "
                        "Show a time-slot schedule for each person. Format it as a simple table: "
                        "Time | Mom | JP | Joseph | Michael | James. "
                        "Make sure James always has a supervisor. "
                        "Fit school, chores, meals, and any calendar events. "
                        "Keep it practical and achievable."
                    )
                else:
                    user_msg = question if question else "What should I be thinking about for today's schedule?"
                # Call Anthropic API (non-streaming for simplicity — streams as one chunk)
                payload = _json.dumps({
                    "model":      "claude-sonnet-4-20250514",
                    "max_tokens": 1200,
                    "system":     context,
                    "messages":   [{"role":"user","content":user_msg}]
                }).encode()
                req = _req.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={
                        "Content-Type":      "application/json",
                        "x-api-key":         api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    method="POST"
                )
                try:
                    with _req.urlopen(req, timeout=45) as resp:
                        result = _json.loads(resp.read().decode())
                    text = result.get("content",[{}])[0].get("text","(No response)")
                except Exception as e:
                    text = f"API error: {e}"
                self.send_response(200)
                self.send_header("Content-Type","text/plain; charset=utf-8")
                self.end_headers()
                try: self.wfile.write(text.encode("utf-8"))
                except BrokenPipeError: pass
                return

            elif path == "/memory-book-save":
                text     = clean_text(data.get("text",[""])[0])
                date_iso = clean_text(data.get("date",[""])[0])
                if text:
                    add_memory_entry(text, date_iso)
                self.send_response(200)
                self.send_header("Content-Type","text/plain")
                self.end_headers()
                self.wfile.write(b"ok")
                return

            elif path == "/memory-book-delete":
                entry_id = clean_text(data.get("id",[""])[0])
                delete_memory_entry(entry_id)
                self.send_response(200)
                self.send_header("Content-Type","text/plain")
                self.end_headers()
                self.wfile.write(b"ok")
                return

            elif path == "/lucy-rule-save":
                import json as _json
                action    = clean_text(data.get("action",[""])[0]).strip()
                rule_text = clean_text(data.get("rule",[""])[0]).strip()
                if rule_text and action in ("add", "remove"):
                    _s = load_app_settings()
                    fc = _s.setdefault("family_constraints", {})
                    rules = fc.get("lucy_rules", [])
                    if not isinstance(rules, list):
                        rules = []
                    if action == "add" and rule_text not in rules:
                        rules.append(rule_text)
                    elif action == "remove":
                        rules = [r for r in rules if r != rule_text]
                    fc["lucy_rules"] = rules
                    _s["family_constraints"] = fc
                    save_app_settings(_s)
                self.send_response(200)
                self.send_header("Content-Type","text/plain")
                self.end_headers()
                self.wfile.write(b"ok")
                return

            elif path == "/lucy-chat":
                import json as _json, urllib.request as _req
                from data_helpers import (
                    load_lucy_history, append_lucy_messages, LUCY_CONTEXT_MAX
                )
                from datetime import datetime as _dt
                from web_fetch import extract_urls, fetch_urls, build_url_context
                iso      = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                capacity = clean_text(data.get("capacity",[""])[0])
                message  = clean_text(data.get("message",[""])[0])
                settings_data = load_app_settings()
                api_key = (settings_data.get("family_constraints",{}).get("anthropic_api_key","")
                           or settings_data.get("anthropic_api_key","")).strip()
                if not api_key:
                    self.send_response(400)
                    self.send_header("Content-Type","text/plain")
                    self.end_headers()
                    try: self.wfile.write(b"No API key. Add your Anthropic key in Settings \u2192 Family & AI.")
                    except BrokenPipeError: pass
                    return
                try:
                    d = date.fromisoformat(iso)
                    weekday    = d.strftime("%A")
                    date_label = d.strftime("%B %d, %Y")
                except Exception:
                    weekday = date_label = iso
                lucy_context = build_lucy_context(iso, weekday, date_label, capacity)
                # ── Fetch any URLs in the user's message ──────────────────────
                _urls = extract_urls(message)
                if _urls:
                    _fetched = fetch_urls(_urls)
                    _web_ctx = build_url_context(_fetched)
                    if _web_ctx:
                        lucy_context += _web_ctx
                # ── Save user message to server-side history ──────────────────
                ts_now = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                append_lucy_messages([{"role": "user", "content": message, "ts": ts_now}])
                # ── Build Claude message list from server history ─────────────
                server_history = load_lucy_history()
                messages = []
                for h in server_history[-LUCY_CONTEXT_MAX:]:
                    role    = h.get("role","user")
                    content = h.get("content","")
                    if role in ("user","assistant") and content:
                        messages.append({"role": role, "content": content})
                # Ensure conversation ends with user message
                if not messages or messages[-1].get("role") != "user":
                    messages.append({"role": "user", "content": message})
                payload = _json.dumps({
                    "model":      "claude-haiku-4-5-20251001",
                    "max_tokens": 1500,
                    "system":     lucy_context,
                    "messages":   messages,
                }).encode()
                req = _req.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={
                        "Content-Type":      "application/json",
                        "x-api-key":         api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    method="POST"
                )
                try:
                    with _req.urlopen(req, timeout=45) as resp:
                        result = _json.loads(resp.read().decode())
                    text = result.get("content",[{}])[0].get("text","(No response)")
                except Exception as e:
                    text = f"I ran into an issue: {e}"
                # ── Save assistant response to server-side history ────────────
                ts_reply = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
                append_lucy_messages([{"role": "assistant", "content": text, "ts": ts_reply}])
                self.send_response(200)
                self.send_header("Content-Type","text/plain; charset=utf-8")
                self.end_headers()
                try: self.wfile.write(text.encode("utf-8"))
                except BrokenPipeError: pass
                return

            elif path == "/lucy-clear-history":
                from data_helpers import clear_lucy_history
                clear_lucy_history()
                redirect = "/lucy"

            elif path in ("/calendar-config-save","/calendar-save-config"):
                apple_id=clean_text(data.get("apple_id",[""])[0]); app_password=clean_text(data.get("app_password",[""])[0])
                cfg=load_calendar_config()
                if apple_id: cfg["apple_id"]=apple_id
                if app_password: cfg["app_password"]=app_password
                save_calendar_config(cfg)
                if path=="/calendar-config-save": refresh_calendar(force=True)
                redirect="/calendar#top"

            elif path == "/calendar-approve":
                tk=clean_text(data.get("title_key",[""])[0]).lower(); d=clean_text(data.get("decision",[""])[0])
                if tk and d in ("show_boys","mom_only","skip"):
                    rules=load_calendar_rules(); rules.setdefault("rules",{})[tk]=d; save_calendar_rules(rules)
                redirect="/calendar#top"

            elif path == "/planner-add-task":
                text=clean_text(data.get("text",[""])[0])
                if text:
                    tasks=load_manual_tasks(); tasks.append({"text":text,"assigned_to":"Mom","due_date":"","priority":"MEDIUM","status":"active","recurring":False}); save_manual_tasks(tasks)
                redirect="/planner#top"

            elif path == "/subscribed-cal-add":
                name=clean_text(data.get("name",[""])[0]); url=clean_text(data.get("url",[""])[0]); color=clean_text(data.get("color",["#9b59b6"])[0])
                if name and url:
                    cals=load_subscribed_calendars(); cals.append({"id":str(uuid.uuid4()),"name":name,"url":url,"color":color,"enabled":True}); save_subscribed_calendars(cals)
                redirect="/calendar#top"

            elif path == "/subscribed-cal-toggle":
                idx_in = safe_int(data.get("index",["0"])[0], 0)
                cals   = load_subscribed_calendars()
                if 0 <= idx_in < len(cals):
                    cals[idx_in]["enabled"] = not cals[idx_in].get("enabled", True)
                    save_subscribed_calendars(cals)
                redirect = "/settings#s-integrations"

            elif path == "/subscribed-cal-delete":
                idx=safe_int(data.get("index",["0"])[0],0); cals=load_subscribed_calendars()
                if 0<=idx<len(cals): cals.pop(idx)
                save_subscribed_calendars(cals); redirect="/calendar#top"

            elif path == "/calendar-refresh":
                refresh_calendar(force=True)
                from render_calendar import refresh_subscribed_calendars
                refresh_subscribed_calendars(force=True)
                redirect="/calendar#top"

            elif path in ("/family-schedule-save", "/settings-schedule-save"):
                schedule=load_family_schedule(); days_data=schedule.get("days",{})
                for key,val_list in data.items():
                    if key.startswith("slot__"):
                        parts=key.split("__",2)
                        if len(parts)==3: _,day,ts=parts; days_data.setdefault(day,{})[ts]=clean_text(val_list[0])
                schedule["days"]=days_data; schedule["times"]=generate_half_hour_times(); save_family_schedule(schedule)
                redirect="/settings?msg=Schedule+saved#s-systems"

            elif path == "/roadmap-add":
                title=clean_text(data.get("title",[""])[0]); nt=clean_text(data.get("notes",[""])[0]); status=clean_text(data.get("status",["Someday"])[0])
                if status not in ROADMAP_STATUSES: status="Someday"
                if title:
                    ideas=load_roadmap(); ideas.append({"id":str(uuid.uuid4()),"title":title,"notes":nt,"status":status}); save_roadmap(ideas)
                redirect="/roadmap#top"

            elif path == "/roadmap-update":
                idea_id=clean_text(data.get("id",[""])[0]); nt=clean_text(data.get("notes",[""])[0]); status=clean_text(data.get("status",["Someday"])[0])
                if status not in ROADMAP_STATUSES: status="Someday"
                ideas=load_roadmap()
                for idea in ideas:
                    if str(idea.get("id",""))==idea_id: idea["notes"]=nt; idea["status"]=status; break
                save_roadmap(ideas); redirect="/roadmap#top"

            elif path == "/roadmap-delete":
                idea_id=clean_text(data.get("id",[""])[0])
                save_roadmap([i for i in load_roadmap() if str(i.get("id",""))!=idea_id]); redirect="/roadmap#top"

            elif path == "/liturgical-save":
                ds=clean_text(data.get("date",[""])[0]); nm=clean_text(data.get("name",[""])[0]); nt=clean_text(data.get("notes",[""])[0]); col=clean_text(data.get("color",[""])[0])
                try: date.fromisoformat(ds); valid=True
                except: valid=False
                if valid and (nm or nt or col):
                    custom=load_liturgical_custom(); custom[ds]={"name":nm,"notes":nt,"color":col}; save_liturgical_custom(custom)
                redirect="/liturgical#top"

            elif path == "/liturgical-delete":
                ds=clean_text(data.get("date",[""])[0]); custom=load_liturgical_custom(); custom.pop(ds,None); save_liturgical_custom(custom); redirect="/liturgical#top"

            elif path == "/liturgical-note":
                ds=clean_text(data.get("date",[""])[0]); fn=clean_text(data.get("family_note",[""])[0])
                try: date.fromisoformat(ds); valid=True
                except: valid=False
                if valid:
                    custom=load_liturgical_custom(); custom.setdefault(ds,{})["family_note"]=fn; save_liturgical_custom(custom)
                redirect="/liturgical#top"

            elif path == "/settings-save-ajax":
                # AJAX autosave — accepts same form fields, returns JSON
                import json as _json
                from daily_schedule_engine import CHILDREN as _CHILDREN
                _settings = load_app_settings()
                fn = clean_text(data.get("family_name",[""])[0])
                if fn: _settings["family_name"] = fn
                tz = clean_text(data.get("timezone",[""])[0])
                if tz: _settings["timezone"] = tz
                loc = clean_text(data.get("location",[""])[0])
                _settings["location"] = loc
                sh = safe_int(data.get("schedule_start_hour",["6"])[0], 6)
                eh = safe_int(data.get("schedule_end_hour",["22"])[0], 22)
                _settings["schedule_start_hour"] = max(0, min(sh, 21))
                _settings["schedule_end_hour"]   = max(_settings["schedule_start_hour"]+1, min(eh, 24))
                ve = clean_text(data.get("van_epoch",[""])[0])
                try: date.fromisoformat(ve); _settings["van_epoch"] = ve
                except Exception: pass
                colors = _settings.get("child_colors", {})
                for _c in _CHILDREN:
                    ce = _c.replace(" ","_")
                    bg    = clean_text(data.get(f"color_bg_{ce}",   [""])[0])
                    txt   = clean_text(data.get(f"color_text_{ce}", [""])[0])
                    light = clean_text(data.get(f"color_light_{ce}",[""])[0])
                    if bg or txt or light:
                        colors[_c] = {
                            "bg":    bg    if bg    else colors.get(_c,{}).get("bg","#888"),
                            "text":  txt   if txt   else colors.get(_c,{}).get("text","#fff"),
                            "light": light if light else colors.get(_c,{}).get("light","#f5f5f5"),
                        }
                _settings["child_colors"] = colors
                fc_keys = ["anthropic_api_key","james_schedule","supervision_rules",
                           "independence_notes","school_durations","mom_supervision_subjects",
                           "meal_prep","other_notes","family_exercise",
                           "school_mode","core_subjects","paused_subjects"]
                constraints = _settings.get("family_constraints", {})
                for k in fc_keys:
                    val = clean_text(data.get(f"fc_{k}", [""])[0])
                    if val or f"fc_{k}" in data:
                        # Never blank out the API key — only update if a real value sent
                        if k == "anthropic_api_key" and not val:
                            pass
                        else:
                            constraints[k] = val
                _settings["family_constraints"] = constraints
                birthdays = _settings.get("child_birthdays", {})
                for _c in _CHILDREN:
                    ce  = _c.replace(" ","_")
                    dob = clean_text(data.get(f"birthday_{ce}", [""])[0])
                    if dob:
                        try: date.fromisoformat(dob); birthdays[_c] = dob
                        except Exception: pass
                _settings["child_birthdays"] = birthdays
                events = []
                for i in range(10):
                    lbl = clean_text(data.get(f"event_label_{i}", [""])[0])
                    edt = clean_text(data.get(f"event_date_{i}",  [""])[0])
                    if lbl: events.append({"label": lbl, "date": edt})
                _settings["special_events"] = events
                theme_val = clean_text(data.get("color_theme", ["ivory"])[0])
                if theme_val in {"ivory","parchment","night","minimal","liturgical"}:
                    _settings["color_theme"] = theme_val
                # Boolean toggles — only update if the sentinel field is present
                # (prevents autosave from wiping toggles when only other fields changed)
                if "cycle_fields_section" in data:
                    _settings["cycle_show_detail_fields"] = "cycle_show_detail_fields" in data
                if "liturgy_section" in data:
                    _settings["show_liturgy_hours_widget"] = "show_liturgy_hours_widget" in data
                    _settings["auto_fetch_hours"]           = "auto_fetch_hours" in data
                    uc = clean_text(data.get("universalis_country", ["United States"])[0])
                    _settings["universalis_country"] = uc
                # Meal rules passed as JSON string
                meal_rules_raw = data.get("meal_rules_json", [""])[0]
                if meal_rules_raw:
                    try:
                        import json as _mrj
                        _settings["meal_rules"] = _mrj.loads(meal_rules_raw)
                    except Exception: pass
                save_app_settings(_settings)
                # Schedule grid slots
                _sched = load_family_schedule()
                _days  = _sched.get("days", {})
                _has   = False
                for key, val_list in data.items():
                    if key.startswith("slot__"):
                        parts = key.split("__", 2)
                        if len(parts) == 3:
                            _, day, ts = parts
                            _days.setdefault(day, {})[ts] = clean_text(val_list[0])
                            _has = True
                if _has:
                    _sched["days"]  = _days
                    _sched["times"] = generate_half_hour_times()
                    save_family_schedule(_sched)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": True}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/settings-save":
                from daily_schedule_engine import CHILDREN as _CHILDREN
                settings = load_app_settings()
                # General
                fn = clean_text(data.get("family_name",[""])[0])
                if fn: settings["family_name"] = fn
                tz = clean_text(data.get("timezone",[""])[0])
                if tz: settings["timezone"] = tz
                loc = clean_text(data.get("location",[""])[0])
                settings["location"] = loc
                # Schedule hours
                sh = safe_int(data.get("schedule_start_hour",["6"])[0], 6)
                eh = safe_int(data.get("schedule_end_hour",["22"])[0], 22)
                settings["schedule_start_hour"] = max(0, min(sh, 21))
                settings["schedule_end_hour"]   = max(settings["schedule_start_hour"]+1, min(eh, 24))
                # Van epoch
                ve = clean_text(data.get("van_epoch",[""])[0])
                try:
                    date.fromisoformat(ve)
                    settings["van_epoch"] = ve
                except Exception:
                    pass
                # Child colors
                colors = settings.get("child_colors", {})
                for child in _CHILDREN:
                    ce = child.replace(" ","_")
                    bg    = clean_text(data.get(f"color_bg_{ce}",   [""])[0])
                    text  = clean_text(data.get(f"color_text_{ce}", [""])[0])
                    light = clean_text(data.get(f"color_light_{ce}",[""])[0])
                    if bg or text or light:
                        colors[child] = {
                            "bg":    bg    if bg    else colors.get(child,{}).get("bg","#888"),
                            "text":  text  if text  else colors.get(child,{}).get("text","#fff"),
                            "light": light if light else colors.get(child,{}).get("light","#f5f5f5"),
                        }
                settings["child_colors"] = colors
                # Plan columns
                plan_cols = data.get("plan_columns", [])
                if isinstance(plan_cols, list):
                    settings["plan_columns"] = [clean_text(p) for p in plan_cols if clean_text(p)]
                # Family constraints (fc_ prefix)
                fc_keys = [
                    "anthropic_api_key", "james_schedule", "supervision_rules",
                    "independence_notes", "school_durations", "mom_supervision_subjects",
                    "meal_prep", "other_notes", "family_exercise",
                    "school_mode", "core_subjects", "paused_subjects",
                ]
                constraints = settings.get("family_constraints", {})
                for k in fc_keys:
                    val = clean_text(data.get(f"fc_{k}", [""])[0])
                    # Never overwrite API key with blank — only update if a value was sent
                    if k == "anthropic_api_key":
                        if val: constraints[k] = val
                    else:
                        constraints[k] = val
                settings["family_constraints"] = constraints
                # Child birthdays
                birthdays = settings.get("child_birthdays", {})
                for child in _CHILDREN:
                    ce  = child.replace(" ","_")
                    dob = clean_text(data.get(f"birthday_{ce}", [""])[0])
                    if dob:
                        try: date.fromisoformat(dob); birthdays[child] = dob
                        except Exception: pass
                    elif f"birthday_{ce}" in data:
                        birthdays.pop(child, None)
                settings["child_birthdays"] = birthdays
                # Special events
                events = []
                for i in range(10):
                    label = clean_text(data.get(f"event_label_{i}", [""])[0])
                    edate = clean_text(data.get(f"event_date_{i}",  [""])[0])
                    if label:
                        events.append({"label": label, "date": edate})
                settings["special_events"] = events
                # Color theme
                theme_val = clean_text(data.get("color_theme", ["ivory"])[0])
                valid_themes = {"ivory", "parchment", "night", "minimal", "liturgical"}
                if theme_val in valid_themes:
                    settings["color_theme"] = theme_val
                # Cycle detail fields toggle
                if "cycle_fields_section" in data:
                    settings["cycle_show_detail_fields"] = "cycle_show_detail_fields" in data
                # Liturgy of the Hours toggles
                if "liturgy_section" in data:
                    settings["show_liturgy_hours_widget"] = "show_liturgy_hours_widget" in data
                    settings["auto_fetch_hours"]           = "auto_fetch_hours" in data
                    uc2 = clean_text(data.get("universalis_country", ["United States"])[0])
                    settings["universalis_country"] = uc2
                save_app_settings(settings)
                print(f"[SETTINGS] Saved location={repr(settings.get('location'))}, keys={list(settings.keys())}")
                # Verify the file was written
                import json as _json
                try:
                    _verify = _json.load(open("data/app_settings.json"))
                    print(f"[SETTINGS] Verified on disk: location={repr(_verify.get('location'))}")
                except Exception as _ve:
                    print(f"[SETTINGS] WARNING: Could not verify file: {_ve}")
                # Also save schedule grid slots if included
                schedule  = load_family_schedule()
                days_data = schedule.get("days", {})
                has_slots = False
                for key, val_list in data.items():
                    if key.startswith("slot__"):
                        parts = key.split("__", 2)
                        if len(parts) == 3:
                            _, day, ts = parts
                            days_data.setdefault(day, {})[ts] = clean_text(val_list[0])
                            has_slots = True
                if has_slots:
                    schedule["days"]  = days_data
                    schedule["times"] = generate_half_hour_times()
                    save_family_schedule(schedule)
                redirect = "/settings?msg=Settings+saved#top"

            elif path == "/school-settings-save":
                import json as _json
                _ss = load_app_settings()
                _fc = _ss.setdefault("family_constraints", {})
                mode   = clean_text(data.get("fc_school_mode",   ["normal"])[0])
                core   = clean_text(data.get("fc_core_subjects",  [""])[0])
                paused = clean_text(data.get("fc_paused_subjects",[""])[0])
                if mode in ("normal", "light_week", "custom_pause"):
                    _fc["school_mode"] = mode
                _fc["core_subjects"]   = core
                _fc["paused_subjects"] = paused
                _ss["family_constraints"] = _fc
                save_app_settings(_ss)
                # Clear the school filter cache so schedule reflects change immediately
                try:
                    import daily_schedule_engine as _dse
                    _dse._SCHOOL_FILTER_CACHE = None
                    _dse._SCHOOL_FILTER_TIME  = 0.0
                except Exception:
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": True}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/child-goal-add":
                import json as _json
                from render_child_goals import add_child_goal
                _child  = clean_text(data.get("child",[""])[0])
                _title  = clean_text(data.get("title",[""])[0])
                _cat    = clean_text(data.get("category",["Spiritual Formation"])[0])
                _why    = clean_text(data.get("why",[""])[0])
                _dl     = clean_text(data.get("deadline",[""])[0])
                _rev    = clean_text(data.get("review_frequency",["weekly"])[0])
                if _child and _title:
                    add_child_goal(_child, _title, _cat, _why, _dl, _rev)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": True}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/child-goal-archive":
                import json as _json
                from render_child_goals import update_child_goal
                _child  = clean_text(data.get("child",[""])[0])
                _gid    = clean_text(data.get("goal_id",[""])[0])
                if _child and _gid:
                    update_child_goal(_child, _gid, {"archived": True})
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": True}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/child-substep-add":
                import json as _json
                from render_child_goals import add_substep
                _child  = clean_text(data.get("child",[""])[0])
                _gid    = clean_text(data.get("goal_id",[""])[0])
                _text   = clean_text(data.get("text",[""])[0])
                step    = {}
                if _child and _gid and _text:
                    step = add_substep(_child, _gid, _text)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": bool(step), "step": step}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/child-substep-toggle":
                import json as _json
                from render_child_goals import toggle_substep
                _child  = clean_text(data.get("child",[""])[0])
                _gid    = clean_text(data.get("goal_id",[""])[0])
                _sid    = clean_text(data.get("step_id",[""])[0])
                _done   = False
                if _child and _gid and _sid:
                    _done = toggle_substep(_child, _gid, _sid)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": True, "done": _done}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/child-substep-delete":
                import json as _json
                from render_child_goals import delete_substep
                _child  = clean_text(data.get("child",[""])[0])
                _gid    = clean_text(data.get("goal_id",[""])[0])
                _sid    = clean_text(data.get("step_id",[""])[0])
                if _child and _gid and _sid:
                    delete_substep(_child, _gid, _sid)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps({"ok": True}).encode())
                except BrokenPipeError: pass
                return

            elif path == "/calendar-add-event":
                import json as _json
                ev_date  = clean_text(data.get("date",[""])[0]) or date.today().isoformat()
                ev_title = clean_text(data.get("title",[""])[0])
                ev_start = clean_text(data.get("start_time",[""])[0])
                ev_end   = clean_text(data.get("end_time",[""])[0])
                ev_notes = clean_text(data.get("notes",[""])[0])
                if ev_title:
                    from data_helpers import load_calendar_cache, save_calendar_cache
                    cache  = load_calendar_cache()
                    events = cache.get("events", [])
                    start_iso = f"{ev_date}T{ev_start}:00" if ev_start else ev_date
                    end_iso   = f"{ev_date}T{ev_end}:00"   if ev_end   else ev_date
                    events.append({
                        "title":    ev_title,
                        "start":    start_iso,
                        "end":      end_iso,
                        "all_day":  not bool(ev_start),
                        "calendar": "Manual",
                        "color":    "#8b5a3c",
                        "location": ev_notes,
                        "id":       str(uuid.uuid4()),
                    })
                    save_calendar_cache({"events": events, "fetched_at": datetime.now().isoformat()})
                redirect = "/mom#calendar"

            elif path == "/cycle-log-add":
                import json as _json, os as _os
                from datetime import date as _date
                day1 = clean_text(data.get("day1",[""])[0])
                note = clean_text(data.get("note",[""])[0])
                if day1:
                    CYCLE_LOG = "data/cycle_log.json"
                    try:
                        with open(CYCLE_LOG) as f:
                            log = _json.load(f)
                    except Exception:
                        log = []
                    log = [e for e in log if e.get("day1") != day1]
                    log.append({"day1": day1, "note": note, "logged": _date.today().isoformat()})
                    safe_save_json(CYCLE_LOG, log)
                redirect = "/settings?msg=Cycle+Day+1+saved#s-cycle"

            elif path == "/cycle-log-delete":
                import json as _json
                day1 = clean_text(data.get("day1",[""])[0])
                CYCLE_LOG = "data/cycle_log.json"
                try:
                    with open(CYCLE_LOG) as f:
                        log = _json.load(f)
                    log = [e for e in log if e.get("day1") != day1]
                    safe_save_json(CYCLE_LOG, log)
                except Exception:
                    pass
                redirect = "/settings?msg=Entry+deleted#s-cycle"

            elif path == "/add-to-plan-quick":
                from datetime import date as _date
                from render_daily_plan import get_or_seed_plan, add_item_to_plan
                iso_q  = clean_text(data.get("iso",[""])[0]) or _date.today().isoformat()
                text_q = clean_text(data.get("text",[""])[0])
                src_q  = clean_text(data.get("source",["manual"])[0])
                if text_q:
                    plan_q = get_or_seed_plan(iso_q)
                    add_item_to_plan(plan_q, text_q, source=src_q)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/cycle-ai-suggest":
                import json as _json
                raw  = data.get("data",["{}"])[0]
                try:    payload = _json.loads(raw)
                except: payload = {}

                phase     = clean_text(payload.get("phase","unknown"))
                cycle_day = clean_text(payload.get("cycle_day",""))
                energy    = clean_text(payload.get("energy",""))
                mood      = clean_text(payload.get("mood",""))
                symptoms  = clean_text(payload.get("symptoms",""))
                stress    = clean_text(payload.get("stress",""))

                settings  = load_app_settings()
                api_key   = settings.get("anthropic_api_key","") or settings.get("fc_anthropic_api_key","")

                if not api_key:
                    resp_json = _json.dumps({"error": "No API key set in Settings."}).encode()
                else:
                    try:
                        import urllib.request as _ur
                        prompt = (
                            f"You are a supportive, practical assistant for a Catholic homeschool mother. "
                            f"She is on cycle day {cycle_day or 'unknown'}, in her {phase} phase. "
                            f"Energy: {energy or 'not specified'}. Mood: {mood or 'not specified'}. "
                            f"Symptoms: {symptoms or 'none noted'}. Stress: {stress or 'not specified'}.\n\n"
                            f"Give her 3-5 sentences of warm, practical, research-based guidance for today. "
                            f"Cover: (1) what her body needs today, (2) what kinds of tasks she's best suited for, "
                            f"(3) one specific suggestion for her home or school day. "
                            f"Be specific, warm, and brief. No bullet points — flowing prose. "
                            f"Do not mention cycle phases by clinical name unless relevant."
                        )
                        req_body = _json.dumps({
                            "model": "claude-haiku-4-5-20251001",
                            "max_tokens": 300,
                            "messages": [{"role": "user", "content": prompt}]
                        }).encode()
                        req = _ur.Request(
                            "https://api.anthropic.com/v1/messages",
                            data=req_body,
                            headers={"Content-Type":"application/json",
                                     "x-api-key": api_key,
                                     "anthropic-version":"2023-06-01"}
                        )
                        with _ur.urlopen(req, timeout=20) as r:
                            result = _json.loads(r.read())
                        suggestion = result["content"][0]["text"].strip()
                        resp_json  = _json.dumps({"suggestion": suggestion}).encode()
                    except Exception as ex:
                        resp_json = _json.dumps({"error": f"AI error: {str(ex)[:80]}"}).encode()

                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(resp_json)
                except BrokenPipeError: pass
                return
            elif path == "/cycle-save":
                import json as _json, os as _os
                from datetime import date as _date
                iso_c  = clean_text(data.get("iso",[""])[0]) or _date.today().isoformat()
                raw_c  = data.get("data",["{}"])[0]
                try:   entry = _json.loads(raw_c)
                except: entry = {}
                allowed = {"phase","cycle_day","energy","mood","symptoms","sleep","cravings","stress"}
                entry = {k: clean_text(str(v)) for k,v in entry.items() if k in allowed}
                month_key  = iso_c[:7]
                cycle_dir  = "data/cycle"
                _os.makedirs(cycle_dir, exist_ok=True)
                cycle_file = f"{cycle_dir}/{month_key}.json"
                try:
                    with open(cycle_file) as f:
                        month_data = _json.load(f)
                except Exception:
                    month_data = {}
                month_data[iso_c] = entry
                safe_save_json(cycle_file, month_data)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/meal-save-plan":
                import json as _json
                wk    = clean_text(data.get("week",[""])[0]) or _week_key()
                raw   = data.get("days",["{}"])[0]
                try:   days_in = _json.loads(raw)
                except: days_in = {}
                plan = load_meal_plan(wk)
                for day, slots in days_in.items():
                    if day not in plan["days"]: plan["days"][day] = {}
                    for slot, val in slots.items():
                        plan["days"][day][slot] = clean_text(val)
                plan["week"] = wk
                save_meal_plan(plan)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/kids-week-save":
                import json as _json
                wk_in   = clean_text(data.get("week",[""])[0])
                raw_in  = data.get("data",["{}"])[0]
                try:
                    plan_in = _json.loads(raw_in)
                    if not wk_in:
                        wk_in = plan_in.get("week","")
                    if wk_in:
                        from render_kids_week import save_week_plan
                        plan_in["week"] = wk_in
                        save_week_plan(plan_in)
                except Exception:
                    pass
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return
            elif path == "/meal-rule-add":
                import json as _json
                rule_text = clean_text(data.get("rule",[""])[0])
                RULES_FILE = "data/meal_rules.json"
                if rule_text:
                    try:
                        with open(RULES_FILE) as f:
                            rules = _json.load(f)
                    except Exception:
                        rules = []
                    rules.append({"rule": rule_text})
                    safe_save_json(RULES_FILE, rules)
                redirect = "/settings?msg=Rule+added#s-meals"

            elif path == "/meal-rule-delete":
                import json as _json
                RULES_FILE = "data/meal_rules.json"
                try:
                    idx = int(data.get("rule_index",["0"])[0])
                    with open(RULES_FILE) as f:
                        rules = _json.load(f)
                    if 0 <= idx < len(rules):
                        rules.pop(idx)
                    safe_save_json(RULES_FILE, rules)
                except Exception:
                    pass
                redirect = "/settings?msg=Rule+removed#s-meals"

            elif path == "/meal-save-inventory":
                import json as _json
                raw = data.get("data",["{}"])[0]
                try:   inv_in = _json.loads(raw)
                except: inv_in = {}
                inv = load_inventory()
                for k in ("fridge","freezer","pantry","use_soon"):
                    if k in inv_in: inv[k] = clean_text(inv_in[k])
                from datetime import date as _date
                inv["last_updated"] = _date.today().isoformat()
                save_inventory(inv)
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/meal-generate":
                import json as _json, requests as _req
                wk     = clean_text(data.get("week",[""])[0]) or _week_key()
                raw_inv = data.get("inventory",["{}"])[0]
                try:   inv_in = _json.loads(raw_inv)
                except: inv_in = {}
                # Save inventory first
                inv = load_inventory()
                for k in ("fridge","freezer","pantry","use_soon"):
                    if k in inv_in: inv[k] = clean_text(inv_in[k])
                save_inventory(inv)
                # Get cycle phase and capacity from today's anchor
                from render_morning_anchor import _get_anchor_state
                from datetime import date as _date
                anchor = _get_anchor_state(_date.today().isoformat())
                cycle_phase = anchor.get("cycle_phase","")
                capacity    = anchor.get("capacity","")
                # Build prompt
                prompt = _build_meal_prompt(inv, cycle_phase, capacity)
                # Call Anthropic API
                settings = load_app_settings()
                api_key  = settings.get("anthropic_api_key","")
                if not api_key:
                    self.send_response(200)
                    self.send_header("Content-Type","application/json")
                    self.end_headers()
                    try: self.wfile.write(_json.dumps({"error":"No API key set in Settings"}).encode())
                    except BrokenPipeError: pass
                    return
                try:
                    resp = _req.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": "claude-opus-4-6",
                            "max_tokens": 4096,
                            "messages": [{"role":"user","content": prompt}],
                        },
                        timeout=90,
                    )
                    resp.raise_for_status()
                    resp_json = resp.json()
                    text = "".join(
                        b.get("text","") for b in resp_json.get("content",[])
                        if b.get("type") == "text"
                    )
                    # Extract JSON from response
                    import re as _re
                    json_match = _re.search(r'\{[\s\S]*\}', text)
                    if json_match:
                        parsed = _json.loads(json_match.group())
                    else:
                        parsed = {}
                    # Extract the day plan (7 day keys) vs metadata
                    from render_meals import DAYS as _DAYS
                    days_out = {d: parsed.get(d,{}) for d in _DAYS}
                    grocery_gaps  = parsed.get("grocery_gaps", [])
                    prep_notes    = parsed.get("prep_notes", {})
                    use_soon_used = parsed.get("use_soon_used", [])
                    # Save plan
                    plan = load_meal_plan(wk)
                    plan["days"]          = days_out
                    plan["grocery_gaps"]  = grocery_gaps
                    plan["prep_notes"]    = prep_notes
                    plan["use_soon_used"] = use_soon_used
                    plan["generated"]     = True
                    plan["week"]          = wk
                    save_meal_plan(plan)
                    result = {
                        "ok": True,
                        "days": days_out,
                        "grocery_gaps": grocery_gaps,
                        "prep_notes": prep_notes,
                        "use_soon_used": use_soon_used,
                    }
                except Exception as e:
                    result = {"error": str(e)}
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(_json.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/recipe-save":
                import json as _json
                rid_edit = clean_text(data.get("id",[""])[0])
                name    = clean_text(data.get("name",[""])[0])
                ingr    = clean_text(data.get("ingredients",[""])[0])
                instr   = clean_text(data.get("instructions",[""])[0])
                tags_raw = clean_text(data.get("tags",[""])[0])
                tags    = [t.strip() for t in tags_raw.split(",") if t.strip()]
                prep    = clean_text(data.get("prep_time",[""])[0])
                if name:
                    if rid_edit:
                        # Update existing recipe
                        recipes = load_recipes()
                        for r in recipes:
                            if r.get("id") == rid_edit:
                                r["name"] = name; r["ingredients"] = ingr
                                r["instructions"] = instr; r["tags"] = tags; r["prep_time"] = prep
                        from render_meals import save_recipes
                        save_recipes(recipes)
                    else:
                        save_recipe(name, ingr, instr, tags, prep)
                redirect = "/recipes?msg=Recipe+saved"

            elif path == "/recipe-import":
                import json as _json
                name     = clean_text(data.get("name",[""])[0])
                url_in   = clean_text(data.get("url",[""])[0])
                text_in  = clean_text(data.get("text",[""])[0])
                # Use AI to parse if API key available
                content  = text_in or url_in
                ingr = ""; instr = ""; tags = []
                if content and name:
                    try:
                        from render_ai_planner import get_api_key
                        api_key = get_api_key()
                        if api_key:
                            import urllib.request as _ur, json as _js
                            prompt = (
                                f"Parse this recipe into structured JSON. "
                                f"Return ONLY valid JSON with keys: ingredients (string), "
                                f"instructions (string), tags (array of strings), prep_time (string).\n\n"
                                f"Recipe source: {content[:2000]}"
                            )
                            req_body = _js.dumps({
                                "model": "claude-haiku-4-5-20251001",
                                "max_tokens": 600,
                                "messages": [{"role": "user", "content": prompt}]
                            }).encode()
                            req = _ur.Request(
                                "https://api.anthropic.com/v1/messages",
                                data=req_body,
                                headers={"Content-Type":"application/json","x-api-key":api_key,
                                         "anthropic-version":"2023-06-01"}
                            )
                            with _ur.urlopen(req, timeout=15) as resp:
                                result = _js.loads(resp.read())
                            raw = result["content"][0]["text"]
                            # Strip markdown fences
                            raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                            parsed = _js.loads(raw)
                            ingr  = parsed.get("ingredients","")
                            instr = parsed.get("instructions","")
                            tags  = parsed.get("tags",[])
                            prep  = parsed.get("prep_time","")
                    except Exception:
                        ingr = content[:500]
                if name:
                    save_recipe(name, ingr, instr, tags, prep if 'prep' in dir() else "")
                redirect = "/recipes?msg=Recipe+imported"

            elif path == "/recipe-delete":
                rid = clean_text(data.get("id",[""])[0])
                if rid:
                    recipes = load_recipes()
                    recipes = [r for r in recipes if r.get("id") != rid]
                    from render_meals import save_recipes
                    save_recipes(recipes)
                redirect = "/recipes"

            # ── Planning system JSON endpoints ──────────────────────────────
            elif path == "/plan-week-save":
                import json as _json
                wk_in  = clean_text(data.get("week",[""])[0])
                raw_in = data.get("data",["{}"])[0]
                try:
                    d_in = _json.loads(raw_in)
                    if wk_in:
                        d_in["week"] = wk_in
                    if d_in.get("week"):
                        from render_plan_week import save_intentions_data
                        save_intentions_data(d_in)
                except Exception:
                    pass
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-month-save":
                import json as _json
                mk_in  = clean_text(data.get("month",[""])[0])
                raw_in = data.get("data",["{}"])[0]
                try:
                    d_in = _json.loads(raw_in)
                    if mk_in:
                        d_in["month"] = mk_in
                    if d_in.get("month"):
                        from render_plan_month import save_month_plan
                        save_month_plan(d_in)
                except Exception:
                    pass
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/quarter-save-goals":
                import json as _json
                qk_in      = clean_text(data.get("quarter",[""])[0])
                ids_raw    = data.get("goal_ids",["[]"])[0]
                try:
                    goal_ids = _json.loads(ids_raw)
                    if qk_in and isinstance(goal_ids, list):
                        from render_goals import load_quarter_plan, save_quarter_plan
                        plan = load_quarter_plan(qk_in)
                        plan["active_goal_ids"] = goal_ids[:5]
                        save_quarter_plan(plan)
                except Exception:
                    pass
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/quarter-save-step":
                qk_in   = clean_text(data.get("quarter",[""])[0])
                gid_in  = clean_text(data.get("goal_id",[""])[0])
                wk_in   = safe_int(data.get("week",["1"])[0], 1)
                step_in = clean_text(data.get("step",[""])[0])
                if qk_in and gid_in:
                    from render_goals import update_weekly_step
                    update_weekly_step(qk_in, gid_in, wk_in, step_in)
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/quarter-checkin":
                qk_in     = clean_text(data.get("quarter",[""])[0])
                gid_in    = clean_text(data.get("goal_id",[""])[0])
                wk_in     = safe_int(data.get("week",["1"])[0], 1)
                status_in = clean_text(data.get("status",[""])[0])
                if qk_in and gid_in and status_in in ("done","partial","skip"):
                    from render_goals import record_weekly_checkin
                    record_weekly_checkin(qk_in, gid_in, wk_in, status_in)
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/goal-add":
                title_in  = clean_text(data.get("title",[""])[0])
                cat_in    = clean_text(data.get("category",["Wildcard"])[0])
                why_in    = clean_text(data.get("why",[""])[0])
                metric_in = clean_text(data.get("metric",[""])[0])
                qk_in     = clean_text(data.get("quarter",[""])[0])
                if title_in:
                    from render_goals import add_master_goal
                    add_master_goal(title_in, cat_in, why_in, metric_in)
                redirect = ("/plan-quarter?quarter=" + qk_in if qk_in else "/plan-quarter") + "&msg=Goal+added"

            elif path == "/virtue-checkin":
                import json as _json
                from datetime import date as _date
                who_in    = clean_text(data.get("who",[""])[0])
                rating_in = safe_int(data.get("rating",["0"])[0], 0)
                note_in   = clean_text(data.get("note",[""])[0])
                if who_in and 0 < rating_in <= 5:
                    checkin = {"date": _date.today().isoformat(),
                               "rating": rating_in, "note": note_in}
                    if who_in == "me":
                        from render_virtues import load_personal_virtue, save_personal_virtue
                        pv = load_personal_virtue()
                        if pv.get("current"):
                            pv["current"].setdefault("checkins",[]).append(checkin)
                            save_personal_virtue(pv)
                    elif who_in == "family":
                        from render_virtues import load_family_virtue, save_family_virtue
                        fv = load_family_virtue()
                        if fv.get("current"):
                            fv["current"].setdefault("checkins",[]).append(checkin)
                            save_family_virtue(fv)
                    else:
                        # child id
                        from render_virtues import load_child_virtue, save_child_virtue
                        from config import CHILDREN
                        child_name = who_in.replace("_"," ")
                        matched = next((c for c in CHILDREN if c.lower()==child_name.lower()), child_name)
                        cv = load_child_virtue(matched)
                        if cv.get("current"):
                            cv["current"].setdefault("checkins",[]).append(checkin)
                            save_child_virtue(matched, cv)
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/prayer-intention-delete":
                iid_in = clean_text(data.get("id",[""])[0])
                if iid_in:
                    from render_prayer import load_intentions, save_intentions
                    intents = load_intentions()
                    intents = [i for i in intents if i.get("id") != iid_in]
                    save_intentions(intents)
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/prayer-intention-log":
                import json as _json
                iid_in    = clean_text(data.get("id",[""])[0])
                ptype_in  = clean_text(data.get("type",["custom"])[0])
                clabel_in = clean_text(data.get("custom_label",[""])[0])
                count_in  = safe_int(data.get("count",["1"])[0], 1)
                note_in   = clean_text(data.get("note",[""])[0])
                if iid_in:
                    from render_prayer import log_prayer
                    log_prayer(iid_in, ptype_in, count_in, clabel_in, note_in)
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/prayer-intention-complete":
                iid_in      = clean_text(data.get("id",[""])[0])
                answered_in = data.get("answered",["false"])[0].lower() == "true"
                if iid_in:
                    from render_prayer import _update_intention
                    _update_intention(iid_in, {"answered": answered_in})
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/liturgy-hours-save":
                raw_in = data.get("data",["{}"])[0]
                try:
                    d_in = _json.loads(raw_in)
                    if not ds_in:
                        ds_in = d_in.get("date","")
                    if ds_in:
                        d_in["date"] = ds_in
                        from render_liturgy_hours import save_day_hours
                        save_day_hours(d_in)
                except Exception:
                    pass
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/liturgy-hours-fetch":
                import json as _json
                ds_in    = clean_text(data.get("date",[""])[0])
                force_in = "force" in data
                try:
                    from datetime import date as _date
                    from render_liturgy_hours import fetch_week, _week_monday, HOURS_DIR
                    import os as _os
                    target_d = _date.fromisoformat(ds_in) if ds_in else _date.today()
                    monday   = _week_monday(target_d)
                    if force_in:
                        # Delete stored files for this week so they get re-fetched
                        for i in range(7):
                            day = monday + __import__('datetime').timedelta(days=i)
                            fp  = _os.path.join(HOURS_DIR, f"{day.isoformat()}.json")
                            if _os.path.exists(fp):
                                _os.remove(fp)
                    fetch_week(monday)
                    out = _json.dumps({"ok": True}).encode()
                except Exception as e:
                    out = _json.dumps({"ok": False, "error": str(e)}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/5am-save":
                import json as _json
                ds_in  = clean_text(data.get("date",[""])[0])
                raw_in = data.get("data",["{}"])[0]
                try:
                    d_in = _json.loads(raw_in)
                    if not ds_in:
                        ds_in = d_in.get("date","")
                    if ds_in:
                        d_in["date"] = ds_in
                        from render_5am import save_day
                        from datetime import date as _date
                        save_day(d_in)
                except Exception:
                    pass
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return

            elif path == "/plan-tomorrow-questions":
                import json as _j
                from render_plan_tomorrow import _gather_tomorrow_data, ai_generate_questions
                iso_in  = clean_text(data.get("iso",[""])[0]) or (date.today()+timedelta(days=1)).isoformat()
                cap_in  = clean_text(data.get("capacity",[""])[0])
                wday_in = clean_text(data.get("weekday",[""])[0])
                try:
                    from datetime import date as _d2
                    tmrw = _d2.fromisoformat(iso_in)
                    d_data = _gather_tomorrow_data(tmrw)
                    d_data["selected_capacity"] = cap_in
                    questions = ai_generate_questions(d_data)
                    out = _j.dumps({"questions": questions}).encode()
                except Exception as e:
                    out = _j.dumps({"error": str(e)}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/plan-tomorrow-generate":
                import json as _j
                from render_plan_tomorrow import _gather_tomorrow_data, ai_generate_plan, _format_plan_html
                iso_in      = clean_text(data.get("iso",[""])[0]) or (date.today()+timedelta(days=1)).isoformat()
                cap_in      = clean_text(data.get("capacity",[""])[0])
                wday_in     = clean_text(data.get("weekday",[""])[0])
                answers_in  = clean_text(data.get("answers",[""])[0])
                questions_in= clean_text(data.get("questions",[""])[0])
                refine_in   = clean_text(data.get("refine",[""])[0])
                try:
                    from datetime import date as _d3
                    tmrw   = _d3.fromisoformat(iso_in)
                    d_data = _gather_tomorrow_data(tmrw)
                    # Include questions context in answers
                    full_answers = (f"Questions asked:\n{questions_in}\n\nAnswers:\n{answers_in}"
                                   if questions_in else answers_in)
                    plan_raw  = ai_generate_plan(d_data, cap_in, full_answers, refine_in)
                    plan_html = _format_plan_html(plan_raw)
                    out = _j.dumps({"plan_html": plan_html, "plan_raw": plan_raw}).encode()
                except Exception as e:
                    out = _j.dumps({"error": str(e)}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/plan-tomorrow-push":
                import json as _j
                iso_in   = clean_text(data.get("iso",[""])[0]) or (date.today()+timedelta(days=1)).isoformat()
                wday_in  = clean_text(data.get("weekday",[""])[0])
                plan_raw = data.get("plan",[""])[0]
                try:
                    # Parse the plan text into per-person time slots
                    from render_daily_plan import get_or_seed_grid, save_day_grid, publish_day_grid
                    from render_schedule_support import generate_half_hour_times
                    import re as _re
                    times = generate_half_hour_times()
                    # Map person headers to grid column names
                    person_map = {"MOM":"Mom","JP":"JP","JOSEPH":"Joseph","MICHAEL":"Michael","JAMES":"James"}
                    grid = get_or_seed_grid(iso_in, wday_in, list(person_map.values()))
                    current_person = None
                    for line in plan_raw.splitlines():
                        if line.startswith("## "):
                            current_person = person_map.get(line[3:].strip().upper())
                        elif current_person and (" \u2014 " in line or " - " in line):
                            sep  = " \u2014 " if " \u2014 " in line else " - "
                            time_str, task = line.strip().split(sep, 1)
                            # Match time_str to nearest slot
                            time_str = time_str.strip()
                            _m = _re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", time_str, _re.IGNORECASE)
                            if _m:
                                h, m, ampm = int(_m.group(1)), int(_m.group(2)), (_m.group(3) or "").upper()
                                if ampm == "PM" and h != 12: h += 12
                                if ampm == "AM" and h == 12: h = 0
                                target_min = h * 60 + m
                                best_slot = min(times, key=lambda t: abs(
                                    (lambda p: int(p.split(":")[0]) * 60 + int(p.split(":")[1].split()[0]))(t)
                                    - target_min
                                ))
                                if current_person in grid:
                                    existing = grid[current_person].get(best_slot, "")
                                    grid[current_person][best_slot] = (existing + " / " + task.strip() if existing else task.strip())
                    save_day_grid(iso_in, grid)
                    publish_day_grid(iso_in)
                    out = _j.dumps({"ok": True}).encode()
                except Exception as e:
                    out = _j.dumps({"ok": False, "error": str(e)}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/ai-daily-schedule":
                import json as _j
                from render_ai_daily import ai_daily_schedule
                iso_in  = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                cap_in  = clean_text(data.get("capacity",[""])[0])
                wday_in = clean_text(data.get("weekday",[""])[0])
                try:
                    result = ai_daily_schedule(iso_in, cap_in, wday_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-meal-plan":
                import json as _j
                from render_ai_daily import ai_meal_plan
                wk_in = clean_text(data.get("week_key",[""])[0])
                try:
                    result = ai_meal_plan(wk_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-school-plan":
                import json as _j
                from render_ai_daily import ai_school_plan
                iso_in  = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                cap_in  = clean_text(data.get("capacity",[""])[0])
                wday_in = clean_text(data.get("weekday",[""])[0])
                try:
                    result = ai_school_plan(iso_in, wday_in, cap_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-evening-examen":
                import json as _j
                from render_ai_daily import ai_evening_examen
                iso_in = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                try:
                    result = ai_evening_examen(iso_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-weekly-review":
                import json as _j
                from render_ai_daily import ai_weekly_review
                wk_in = clean_text(data.get("week_key",[""])[0])
                try:
                    result = ai_weekly_review(wk_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-chore-adjust":
                import json as _j
                from render_ai_daily import ai_chore_adjust
                iso_in = clean_text(data.get("iso",[""])[0]) or date.today().isoformat()
                cap_in = clean_text(data.get("capacity",[""])[0])
                try:
                    result = ai_chore_adjust(iso_in, cap_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-intention-prayer":
                import json as _j
                from render_ai_daily import ai_intention_prayer
                iid_in = clean_text(data.get("id",[""])[0])
                try:
                    result = ai_intention_prayer(iid_in)
                except Exception as e:
                    result = {"html": f"<p>Error: {e}</p>", "text": ""}
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(_j.dumps(result).encode())
                except BrokenPipeError: pass
                return

            elif path == "/ai-capacity-preview":
                import json as _json, urllib.request as _ur
                iso_in  = clean_text(data.get("iso",[""])[0])
                cap_in  = clean_text(data.get("capacity",[""])[0])
                try:
                    settings = load_app_settings()
                    api_key  = (settings.get("anthropic_api_key","") or
                                settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    # Get family constraints for context
                    fc = settings.get("family_constraints",{})
                    context = []
                    if fc.get("james_schedule"):    context.append(f"Baby schedule: {fc['james_schedule'][:100]}")
                    if fc.get("school_durations"):  context.append(f"School: {fc['school_durations'][:100]}")
                    if fc.get("mom_supervision_subjects"): context.append(f"Mom-needed: {fc['mom_supervision_subjects'][:100]}")
                    context_str = "\n".join(context) if context else "No specific constraints on file."
                    cap_desc = {
                        "High":   "full energy, full capacity — can handle normal school, chores, cooking, and all responsibilities",
                        "Medium": "moderate energy — can do essentials but may need to simplify or delegate",
                        "Low":    "low energy — need to scale back significantly, focus only on the most important things",
                    }.get(cap_in, cap_in)
                    prompt = (
                        f"You are a warm Catholic homeschool family assistant.\n"
                        f"Mom just set her capacity to: {cap_in} ({cap_desc})\n"
                        f"Family context:\n{context_str}\n\n"
                        f"In 2-3 warm, practical sentences, briefly tell her:\n"
                        f"1. What this means for her day (what she can let go or lean into)\n"
                        f"2. One specific encouragement tailored to this capacity level\n"
                        f"Be concise and encouraging. No bullet points."
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 200,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=15) as resp:
                        result = _json.loads(resp.read())
                    preview = result["content"][0]["text"].strip()
                    out = _json.dumps({"preview": preview}).encode()
                except Exception as e:
                    cap_msgs = {
                        "High":   "You're at full capacity today — take on the full rhythm.",
                        "Medium": "Moderate capacity today — focus on what matters most.",
                        "Low":    "Low capacity today — give yourself grace and simplify.",
                    }
                    out = _json.dumps({"preview": cap_msgs.get(cap_in, f"Capacity set to {cap_in}.")}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return
                import json as _json, urllib.request as _ur
                season_in = clean_text(data.get("season",["Ordinary Time"])[0])
                virtue_in = clean_text(data.get("virtue",[""])[0])
                try:
                    settings = load_app_settings()
                    api_key  = (settings.get("anthropic_api_key","") or
                                settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    prompt = (
                        f"Write one deep, beautiful morning journal prompt for a Catholic "
                        f"homeschooling mom. Season: {season_in}. "
                        f"{'Virtue focus: ' + virtue_in + '. ' if virtue_in else ''}"
                        f"The prompt should invite honest self-reflection and openness to God. "
                        f"One sentence only. No quotation marks. Return JSON only: {{\"prompt\": \"...\"}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 150,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=15) as resp:
                        result = _json.loads(resp.read())
                    raw    = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    out    = _json.dumps(parsed).encode()
                except Exception as e:
                    out = _json.dumps({"prompt": "What does God want to say to me this morning?"}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return
                import json as _json, urllib.request as _ur
                who_in      = clean_text(data.get("who",["me"])[0])
                child_id_in = clean_text(data.get("child_id",[""])[0])
                try:
                    settings = load_app_settings()
                    api_key  = (settings.get("anthropic_api_key","") or
                                settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    try:
                        from render_liturgical import get_liturgical_season
                        from datetime import date as _date
                        season = get_liturgical_season(_date.today())
                    except Exception:
                        season = "Ordinary Time"
                    # Build recent history context
                    if who_in == "me":
                        from render_virtues import load_personal_virtue
                        pv = load_personal_virtue()
                        recent = [h.get("virtue","") for h in pv.get("history",[])][-4:]
                        current = pv.get("current",{}).get("virtue","")
                        who_desc = "a Catholic homeschooling mom"
                    elif who_in == "family":
                        from render_virtues import load_family_virtue
                        fv = load_family_virtue()
                        recent = [h.get("virtue","") for h in fv.get("history",[])][-4:]
                        current = fv.get("current",{}).get("virtue","")
                        who_desc = "a Catholic homeschooling family"
                    else:
                        from render_virtues import load_child_virtue, child_age, age_band
                        from config import CHILDREN
                        child_name = child_id_in.replace("_"," ")
                        matched = next((c for c in CHILDREN if c.lower()==child_name.lower()), child_name)
                        cv = load_child_virtue(matched)
                        age = child_age(matched)
                        ab  = age_band(age)
                        recent = [h.get("virtue","") for h in cv.get("history",[])][-4:]
                        current = cv.get("current",{}).get("virtue","")
                        who_desc = f"a {ab.replace('_',' ')} child named {matched}"
                    from render_virtues import VIRTUE_LIBRARY
                    exclude = set(recent + ([current] if current else []))
                    available = [v for v in VIRTUE_LIBRARY if v not in exclude]
                    prompt = (
                        f"Suggest 3 virtues for {who_desc} to work on next.\n"
                        f"Liturgical season: {season}\n"
                        f"Recently practiced: {', '.join(recent) or 'none'}\n"
                        f"Available virtues: {', '.join(available[:12])}\n\n"
                        f"Return JSON only:\n"
                        f"{{\"html\": \"<p>1-2 warm sentences of reasoning, then list the 3 suggestions as clickable links using the format <a href='/virtues/TYPE?virtue=VIRTUE_NAME'>VIRTUE_NAME</a> where TYPE is 'me', 'family', or 'child/CHILD_ID'</p>\"}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 400,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=20) as resp:
                        result = _json.loads(resp.read())
                    raw    = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    out    = _json.dumps(parsed).encode()
                except Exception as e:
                    out = _json.dumps({"html": f"<p>Error: {e}</p>"}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            # ── AI endpoints (return JSON) ───────────────────────────────────
            elif path == "/ai-week-brief":
                import json as _json, urllib.request as _ur
                raw_in = data.get("data",["{}"])[0]
                try:
                    payload    = _json.loads(raw_in)
                    settings   = load_app_settings()
                    api_key    = (settings.get("anthropic_api_key","") or
                                  settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    goals_list = payload.get("goals",[])
                    goal_lines = "\n".join(
                        f"- {g.get('title','')} (step this week: {g.get('step','—')})"
                        for g in goals_list
                    )
                    prompt = (
                        f"You are a warm Catholic family life coach. "
                        f"Week {payload.get('quarter_week','?')} of this quarter.\n"
                        f"Most important: {payload.get('important','—')}\n"
                        f"Protect: {payload.get('protect','—')}\n"
                        f"Let go: {payload.get('let_go','—')}\n"
                        f"Active goals this week:\n{goal_lines or '—'}\n\n"
                        f"Write 2-3 sentences of warm, practical encouragement for the week ahead. "
                        f"Then return a JSON array called 'items' with 4-6 specific, actionable items "
                        f"to help her succeed this week — each with a 'text' field (one sentence, concrete action) "
                        f"and a 'category' field (Goal/School/Home/Prayer/Self). "
                        f"Format response as JSON only: {{\"briefing\": \"...\", \"items\": [{{}}, ...]}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 700,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=20) as resp:
                        result = _json.loads(resp.read())
                    raw = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    out = _json.dumps(parsed).encode()
                except Exception as e:
                    out = _json.dumps({"briefing": f"Error: {e}", "items": []}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/ai-month-brief":
                import json as _json, urllib.request as _ur
                raw_in = data.get("data",["{}"])[0]
                try:
                    payload  = _json.loads(raw_in)
                    settings = load_app_settings()
                    api_key  = (settings.get("anthropic_api_key","") or
                                settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    goals_list = payload.get("goals",[])
                    goal_lines = "\n".join(f"- {g.get('title','')}" for g in goals_list)
                    prompt = (
                        f"You are a warm Catholic family life coach.\n"
                        f"Month: {payload.get('month','?')}\n"
                        f"Theme: {payload.get('theme','—')}\n"
                        f"Focus: {payload.get('focus','—')}\n"
                        f"Protect: {payload.get('protect','—')}\n"
                        f"Active goals:\n{goal_lines or '—'}\n\n"
                        f"Write 3-4 sentences of warm, practical monthly encouragement. "
                        f"Consider the liturgical season and how it can inspire her goals. "
                        f"Return JSON only: {{\"briefing\": \"...\"}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 400,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=20) as resp:
                        result = _json.loads(resp.read())
                    raw = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    out = _json.dumps(parsed).encode()
                except Exception as e:
                    out = _json.dumps({"briefing": f"Error: {e}"}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/ai-year-brief":
                import json as _json, urllib.request as _ur
                raw_in = data.get("data",["{}"])[0]
                try:
                    payload  = _json.loads(raw_in)
                    settings = load_app_settings()
                    api_key  = (settings.get("anthropic_api_key","") or
                                settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    goals_list = payload.get("goals",[])
                    goal_lines = "\n".join(f"- {g.get('title','')} ({g.get('category','')})" for g in goals_list)
                    prompt = (
                        f"You are a warm Catholic family life coach reviewing the year {payload.get('year','?')}.\n"
                        f"Goals in master list:\n{goal_lines or '—'}\n\n"
                        f"Write 3-4 sentences reflecting on the year's goals, what rhythms matter "
                        f"for a Catholic homeschooling family, and what to carry into the new year. "
                        f"Return JSON only: {{\"briefing\": \"...\"}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 400,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=20) as resp:
                        result = _json.loads(resp.read())
                    raw = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    out = _json.dumps(parsed).encode()
                except Exception as e:
                    out = _json.dumps({"briefing": f"Error: {e}"}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/ai-suggest-goals":
                import json as _json, urllib.request as _ur
                raw_in = data.get("data",["{}"])[0]
                try:
                    payload    = _json.loads(raw_in)
                    settings   = load_app_settings()
                    api_key    = (settings.get("anthropic_api_key","") or
                                  settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    goals_list = payload.get("goals",[])
                    quarter    = payload.get("quarter","?")
                    goal_lines = "\n".join(
                        f"- [{g.get('id','')}] {g.get('title','')} ({g.get('category','')}) — {g.get('why','')}"
                        for g in goals_list
                    )
                    # Liturgical season for quarter start
                    try:
                        from render_goals import quarter_start
                        from render_liturgical import get_liturgical_season
                        qs = quarter_start(quarter)
                        season = get_liturgical_season(qs)
                    except Exception:
                        season = "Ordinary Time"
                    prompt = (
                        f"You are a wise Catholic family life coach helping plan the quarter {quarter}.\n"
                        f"Liturgical season: {season}\n"
                        f"Available goals:\n{goal_lines}\n\n"
                        f"Select 4-5 goals that are most suited to this quarter and season. "
                        f"Consider the spiritual rhythm of {season}, what's realistic for a homeschooling mom, "
                        f"and natural seasonal energy. Return JSON only:\n"
                        f"{{\"html\": \"<p>2-3 sentences of warm reasoning</p>\", "
                        f"\"suggested_ids\": [\"id1\", \"id2\", \"id3\", \"id4\"]}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 500,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=20) as resp:
                        result = _json.loads(resp.read())
                    raw = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    out = _json.dumps(parsed).encode()
                except Exception as e:
                    out = _json.dumps({"html": f"Error: {e}", "suggested_ids": []}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

            elif path == "/ai-generate-steps":
                import json as _json, urllib.request as _ur
                quarter_in  = clean_text(data.get("quarter",[""])[0])
                gid_in      = clean_text(data.get("goal_id",[""])[0])
                goal_raw    = data.get("goal_data",["{}"])[0]
                try:
                    goal_data = _json.loads(goal_raw)
                    settings  = load_app_settings()
                    api_key   = (settings.get("anthropic_api_key","") or
                                 settings.get("family_constraints",{}).get("anthropic_api_key",""))
                    try:
                        from render_goals import quarter_start, quarter_label
                        from render_liturgical import get_liturgical_season
                        qs     = quarter_start(quarter_in)
                        season = get_liturgical_season(qs)
                        qlabel = quarter_label(quarter_in)
                    except Exception:
                        season = "Ordinary Time"; qlabel = quarter_in
                    prompt = (
                        f"You are a Catholic family life coach creating a 13-week action plan.\n"
                        f"Quarter: {qlabel} | Season: {season}\n"
                        f"Goal: {goal_data.get('title','')}\n"
                        f"Why it matters: {goal_data.get('why','')}\n"
                        f"Success metric: {goal_data.get('metric','')}\n\n"
                        f"Create a specific, realistic 13-week step plan for a homeschooling mom. "
                        f"Each week should build on the last. Steps should be concrete (5-12 words each). "
                        f"Return JSON only: {{\"steps\": {{\"1\": \"Step text\", \"2\": \"...\", ... \"13\": \"...\"}}}}"
                    )
                    req_body = _json.dumps({
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 900,
                        "messages": [{"role":"user","content": prompt}]
                    }).encode()
                    req = _ur.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=req_body,
                        headers={"Content-Type":"application/json","x-api-key":api_key,
                                 "anthropic-version":"2023-06-01"}
                    )
                    with _ur.urlopen(req, timeout=25) as resp:
                        result = _json.loads(resp.read())
                    raw    = result["content"][0]["text"].strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    parsed = _json.loads(raw)
                    steps  = parsed.get("steps", {})
                    # Save to quarter plan
                    if quarter_in and gid_in:
                        from render_goals import load_quarter_plan, save_quarter_plan
                        plan = load_quarter_plan(quarter_in)
                        plan.setdefault("goals", {}).setdefault(gid_in, {})["weekly_steps"] = steps
                        save_quarter_plan(plan)
                    # Build HTML for the step grid
                    rows_html = ""
                    for w in range(1, 14):
                        step_text = steps.get(str(w), "")
                        gid_esc = gid_in.replace("'", "\\'")
                        rows_html += (
                            f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0;'
                            f'border-bottom:1px solid var(--border-light);">'
                            f'<div style="font-size:0.72em;font-weight:700;color:var(--ink-faint);'
                            f'width:28px;flex-shrink:0;">W{w}</div>'
                            f'<input type="text" id="step-{gid_in}-{w}" value="{step_text}" '
                            f'onblur="saveStepEdit(\'{gid_esc}\',{w})" '
                            f'style="flex:1;padding:5px 8px;font-size:0.82em;border-radius:6px;'
                            f'border:1px solid var(--border-light);font-family:inherit;">'
                            f'</div>'
                        )
                    out = _json.dumps({"html": rows_html, "steps": steps}).encode()
                except Exception as e:
                    out = _json.dumps({"html": f"<p style='color:#ef4444;'>Error: {e}</p>", "steps": {}}).encode()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                try: self.wfile.write(out)
                except BrokenPipeError: pass
                return

        self.send_response(303); self.send_header("Location",redirect); self.end_headers()


def initialize_data_files():
    os.makedirs("data",exist_ok=True); os.makedirs("data/history",exist_ok=True); os.makedirs("data/daily_plans",exist_ok=True); os.makedirs("data/day_templates",exist_ok=True); os.makedirs("data/day_grids",exist_ok=True); os.makedirs("data/meal_plan",exist_ok=True); os.makedirs("data/saint_cache",exist_ok=True)
    defaults={
        "data/chores.json":{"boys":{}},"data/manual_tasks.json":[],"data/notes.json":[],"data/mom_notes.json":[],
        "data/progress.json":{},"data/task_registry.json":{},"data/school_previews.json":{},"data/school_weeks.json":{"approved":{}},
        "data/roadmap.json":[],"data/liturgical.json":{},"data/family_schedule.json":{"times":[],"days":{}},
        "data/calendar_config.json":{},"data/calendar_cache.json":{"events":[],"fetched_at":""},
        "data/calendar_rules.json":{"rules":{}},"data/subscribed_calendars.json":[],"data/monthly_planner.json":{},
        "data/app_settings.json":{},
    }
    for fpath,default in defaults.items():
        if not os.path.exists(fpath): safe_save_json(fpath,default)


if __name__ == "__main__":
    initialize_data_files()
    # Pre-fetch saint data for the week in the background
    try:
        import threading
        from saint_data import prefetch_week
        threading.Thread(target=prefetch_week, daemon=True).start()
    except Exception:
        pass
    # Auto-fetch Liturgy of the Hours on Sundays if enabled
    try:
        from render_liturgy_hours import maybe_auto_fetch, cleanup_old_files
        cleanup_old_files()
        maybe_auto_fetch()
    except Exception:
        pass
    import socket as _socket, time as _time2

    class ReusableServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads       = True   # clean up threads automatically
        allow_reuse_address  = True
        allow_reuse_port     = True

        def server_bind(self):
            self.socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            try:
                self.socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass
            super().server_bind()

    # Retry binding — old process may still be releasing the port
    _server = None
    for _attempt in range(10):
        try:
            _server = ReusableServer((HOST, PORT), Handler)
            break
        except OSError:
            if _attempt < 9:
                _time2.sleep(1)
    if _server is None:
        raise RuntimeError(f"Could not bind to port {PORT} after 10 attempts")

    print(f"Running on http://{HOST}:{PORT}")
    _server.serve_forever()