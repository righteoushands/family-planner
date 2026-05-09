"""
render_calendar.py — Calendar fetching, event display, calendar page.
Imports from: config, data_helpers, ui_helpers
"""
from datetime import date, timedelta
from html import escape

from safe_utils import debug_log
from data_helpers import (
    load_calendar_config, save_calendar_config,
    load_calendar_cache, save_calendar_cache,
    load_subscribed_calendars, save_subscribed_calendars,
    load_subscribed_calendar_cache, save_subscribed_calendar_cache,
    load_calendar_rules, save_calendar_rules,
    expand_local_events_for_range,
)
from ui_helpers import html_page, page_header, render_status_message

# ── Background refresh guards ─────────────────────────────────────────────────
# Prevents duplicate background fetches when multiple threads hit a stale cache.
_CALDAV_REFRESHING   = False
_SUBSCRIBED_REFRESHING = False


# ── CalDAV ────────────────────────────────────────────────────────────────────
def fetch_caldav_events(apple_id: str, app_password: str, days_ahead: int = 14) -> list:
    try:
        import urllib.request, base64, re
        from datetime import datetime as _dt
        base_url    = "https://caldav.icloud.com"
        credentials = base64.b64encode(f"{apple_id}:{app_password}".encode()).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/xml; charset=utf-8",
            "Depth": "1",
        }
        today    = date.today()
        end_date = today + timedelta(days=days_ahead)
        def fmt_ical(d): return d.strftime("%Y%m%dT000000Z")
        report_body = f"""<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop><D:getetag/><C:calendar-data/></D:prop>
  <C:filter><C:comp-filter name="VCALENDAR"><C:comp-filter name="VEVENT">
    <C:time-range start="{fmt_ical(today)}" end="{fmt_ical(end_date)}"/>
  </C:comp-filter></C:comp-filter></C:filter>
</C:calendar-query>""".encode()
        disc_req = urllib.request.Request(f"{base_url}/",
            data=b'<?xml version="1.0"?><D:propfind xmlns:D="DAV:"><D:prop><D:current-user-principal/></D:prop></D:propfind>',
            headers={**headers, "Content-Type":"application/xml","Depth":"0"}, method="PROPFIND")
        with urllib.request.urlopen(disc_req, timeout=5) as resp:
            principal_xml = resp.read().decode()
        def _abs(href):
            href = href.strip()
            return href if href.startswith("http") else f"{base_url}{href}"
        pm = re.search(r"current-user-principal[^<]*<(?:D:)?href[^>]*>((?:https?://|/)[^<]+)</(?:D:)?href>", principal_xml, re.DOTALL)
        if not pm: return []
        principal_url = _abs(pm.group(1))
        home_req = urllib.request.Request(principal_url,
            data=b'<?xml version="1.0"?><D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"><D:prop><C:calendar-home-set/></D:prop></D:propfind>',
            headers={**headers,"Content-Type":"application/xml","Depth":"0"}, method="PROPFIND")
        with urllib.request.urlopen(home_req, timeout=10) as resp:
            home_xml = resp.read().decode()
        hm = re.search(r"calendar-home-set.*?<(?:D:)?href[^>]*>((?:https?://|/)[^<]+)</(?:D:)?href>", home_xml, re.DOTALL)
        if not hm: return []
        home_url = _abs(hm.group(1))
        cal_req = urllib.request.Request(home_url,
            data=b'<?xml version="1.0"?><D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"><D:prop><D:displayname/><C:supported-calendar-component-set/></D:prop></D:propfind>',
            headers={**headers,"Content-Type":"application/xml","Depth":"1"}, method="PROPFIND")
        with urllib.request.urlopen(cal_req, timeout=10) as resp:
            cal_xml = resp.read().decode()
        cal_paths = re.findall(r"<(?:D:)?href[^>]*>((?:https?://|/)[^<]*calendar[^<]*)</(?:D:)?href>", cal_xml) or \
                    re.findall(r"<(?:D:)?href[^>]*>((?:https?://|/)[^<]+/)</(?:D:)?href>", cal_xml)
        all_events = []
        for cal_path in set(cal_paths):
            try:
                ev_req = urllib.request.Request(_abs(cal_path), data=report_body, headers=headers, method="REPORT")
                with urllib.request.urlopen(ev_req, timeout=10) as resp:
                    ev_xml = resp.read().decode()
                for vevent in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ev_xml, re.DOTALL):
                    def prop(name):
                        m = re.search(rf"{name}[^:]*:(.*?)\r?\n", vevent)
                        return m.group(1).strip() if m else ""
                    title=prop("SUMMARY"); dtstart=prop("DTSTART"); dtend=prop("DTEND")
                    location=prop("LOCATION"); notes=prop("DESCRIPTION")
                    all_day=False; start_iso=end_iso=""
                    try:
                        if "T" in dtstart:
                            dc=re.sub(r"[TZ]",lambda m:" " if m.group()=="T" else "",dtstart).strip()[:15]
                            parsed=_dt.strptime(dc,"%Y%m%d %H%M%S"); start_iso=parsed.strftime("%Y-%m-%dT%H:%M")
                            if dtend and "T" in dtend:
                                dc2=re.sub(r"[TZ]",lambda m:" " if m.group()=="T" else "",dtend).strip()[:15]
                                end_iso=_dt.strptime(dc2,"%Y%m%d %H%M%S").strftime("%Y-%m-%dT%H:%M")
                        else:
                            all_day=True; parsed=_dt.strptime(dtstart[:8],"%Y%m%d")
                            start_iso=parsed.strftime("%Y-%m-%d"); end_iso=start_iso
                    except Exception: continue
                    if title and start_iso:
                        all_events.append({"title":title,"start":start_iso,"end":end_iso,"all_day":all_day,"location":location,"notes":notes})
            except Exception: continue
        all_events.sort(key=lambda e: e["start"])
        return all_events
    except Exception as e:
        debug_log("CalDAV fetch failed:", str(e))
        return []


def _do_refresh_calendar():
    """Background worker: fetch CalDAV events and update cache."""
    global _CALDAV_REFRESHING
    try:
        from datetime import datetime as _dt
        cfg = load_calendar_config()
        apple_id = cfg.get("apple_id", ""); app_password = cfg.get("app_password", "")
        if apple_id and app_password:
            events = fetch_caldav_events(apple_id, app_password)
            save_calendar_cache({"events": events, "fetched_at": _dt.now().isoformat()})
    except Exception as e:
        debug_log("CalDAV background refresh failed:", str(e))
    finally:
        _CALDAV_REFRESHING = False


def refresh_calendar(force: bool = False) -> list:
    """Return cached CalDAV events immediately; refresh in background if stale."""
    global _CALDAV_REFRESHING
    import threading as _threading
    from datetime import datetime as _dt
    cache      = load_calendar_cache()
    fetched_at = cache.get("fetched_at", "")
    events     = cache.get("events", [])
    stale      = True
    if fetched_at and not force:
        try:
            stale = (_dt.now() - _dt.fromisoformat(fetched_at)).total_seconds() > 1800
        except Exception:
            stale = True
    if stale and not _CALDAV_REFRESHING:
        _CALDAV_REFRESHING = True
        _threading.Thread(target=_do_refresh_calendar, daemon=True).start()
    return events


# ── ICS subscriptions ─────────────────────────────────────────────────────────
def fetch_ics_events(url: str, name: str, color: str = "#9b59b6") -> list:
    try:
        import urllib.request, re
        from datetime import datetime as _dt
        url = url.replace("webcal://", "https://").replace("webcal:", "https:")
        req = urllib.request.Request(url, headers={"User-Agent":"FamilyPlanner/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        events = []; today = date.today(); lookahead = today + timedelta(days=60)

        def _parse_dt(dtstr: str):
            import time as _time, datetime as _dtt
            if not dtstr:
                return None, False
            is_utc    = dtstr.endswith("Z")
            is_allday = len(dtstr.strip()) == 8 and dtstr.strip().isdigit()
            clean = re.sub(r"[TZ]", lambda m: " " if m.group()=="T" else "", dtstr).strip()
            try:
                if is_allday or len(clean) < 10:
                    parsed = _dt.strptime(clean[:8], "%Y%m%d")
                    return parsed, True
                parsed = _dt.strptime(clean[:15], "%Y%m%d %H%M%S")
                if is_utc:
                    utc_off = _time.timezone if not _time.daylight else _time.altzone
                    parsed  = parsed - __import__('datetime').timedelta(seconds=utc_off)
                return parsed, False
            except Exception:
                return None, False

        def _expand_rrule(dtstart_dt, dtend_dt, all_day, rrule_str, summary, location, desc,
                          exdates=None, override_keys=None, uid=None):
            """Expand a recurring event into occurrences within today..lookahead."""
            import datetime as _dtt
            if not rrule_str:
                return []
            if exdates is None:    exdates = set()
            if override_keys is None: override_keys = set()
            params = {}
            for part in rrule_str.split(";"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k.strip().upper()] = v.strip()
            freq   = params.get("FREQ","").upper()
            count  = int(params.get("COUNT", 9999))
            until  = None
            if "UNTIL" in params:
                u, _ = _parse_dt(params["UNTIL"])
                if u: until = u.date() if hasattr(u,"date") else u
            interval = int(params.get("INTERVAL", 1))
            byday    = params.get("BYDAY","")   # e.g. MO,WE,FR
            bymonth  = params.get("BYMONTH","") # e.g. 12
            bymonthday = params.get("BYMONTHDAY","")

            # Map BYDAY to weekday numbers
            day_map = {"MO":0,"TU":1,"WE":2,"TH":3,"FR":4,"SA":5,"SU":6}
            byday_nums = set()
            for d in byday.split(","):
                d = d.strip().upper()[-2:]  # strip any +n/-n prefix
                if d in day_map:
                    byday_nums.add(day_map[d])

            occurrences = []
            cur = dtstart_dt
            seen = 0
            # Duration
            if dtend_dt and dtstart_dt:
                duration = dtend_dt - dtstart_dt
            else:
                duration = _dtt.timedelta(hours=1)

            max_iter = 500  # safety limit
            iters = 0
            while seen < count and iters < max_iter:
                iters += 1
                cur_date = cur.date() if hasattr(cur, "date") else cur
                if until and cur_date > until:
                    break
                if cur_date > lookahead:
                    break

                # Check filters
                include = True
                if byday_nums and cur_date.weekday() not in byday_nums:
                    include = False
                if bymonth and str(cur_date.month) not in bymonth.split(","):
                    include = False
                if bymonthday and str(cur_date.day) not in bymonthday.split(","):
                    include = False
                # Skip excluded dates (EXDATE)
                if cur_date.isoformat() in exdates:
                    include = False
                # Skip instances overridden by a RECURRENCE-ID event
                if uid and (uid, cur_date.isoformat()) in override_keys:
                    include = False

                if include and cur_date >= today:
                    end_dt = cur + duration
                    if all_day:
                        start_iso = cur_date.strftime("%Y-%m-%d")
                        end_iso   = start_iso
                    else:
                        start_iso = cur.strftime("%Y-%m-%dT%H:%M")
                        end_iso   = end_dt.strftime("%Y-%m-%dT%H:%M")
                    occurrences.append({
                        "title":summary,"start":start_iso,"end":end_iso,
                        "all_day":all_day,"location":location,
                        "notes":desc[:200] if desc else "","calendar":name,
                        "color":color,"source":"subscribed"
                    })
                    seen += 1

                # Advance
                if freq == "DAILY":
                    cur += _dtt.timedelta(days=interval)
                elif freq == "WEEKLY":
                    if byday_nums:
                        # Advance to next matching weekday
                        cur += _dtt.timedelta(days=1)
                        # After a full interval weeks, skip to next interval
                    else:
                        cur += _dtt.timedelta(weeks=interval)
                elif freq == "MONTHLY":
                    # Same day next month
                    month = cur.month + interval
                    year  = cur.year + (month - 1) // 12
                    month = ((month - 1) % 12) + 1
                    day   = min(cur.day, [31,29 if year%4==0 else 28,31,30,31,30,31,31,30,31,30,31][month-1])
                    cur   = cur.replace(year=year, month=month, day=day)
                elif freq == "YEARLY":
                    try:
                        cur = cur.replace(year=cur.year + interval)
                    except ValueError:
                        cur = cur.replace(year=cur.year + interval, day=28)
                else:
                    break  # unknown freq

            return occurrences

        # First pass: collect all UIDs that are overridden by RECURRENCE-ID events
        # and collect EXDATEs per UID
        uid_exdates   = {}   # uid -> set of date strings to skip
        override_keys = set()  # (uid, recurrence_date_iso) pairs — these override base recurring

        for vevent in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", raw, re.DOTALL):
            def _prop0(p):
                m = re.search(r"^"+re.escape(p)+r"[;:][^\r\n]+", vevent, re.MULTILINE)
                if not m: return ""
                line = re.sub(r"\r?\n[ \t]","",m.group(0))
                idx = line.rfind(":"); return line[idx+1:].strip() if idx>=0 else ""
            uid    = _prop0("UID")
            rec_id = _prop0("RECURRENCE-ID")
            exdate = _prop0("EXDATE")
            status = _prop0("STATUS").upper()
            if rec_id and uid:
                # Parse the recurrence date
                rec_parsed, _ = _parse_dt(rec_id)
                if rec_parsed:
                    override_keys.add((uid, rec_parsed.date().isoformat()))
            if exdate and uid:
                # EXDATE can be comma-separated list of dates to exclude
                if uid not in uid_exdates:
                    uid_exdates[uid] = set()
                for ex in exdate.split(","):
                    ex_parsed, _ = _parse_dt(ex.strip())
                    if ex_parsed:
                        uid_exdates[uid].add(ex_parsed.date().isoformat())

        for vevent in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", raw, re.DOTALL):
            def prop(p):
                m = re.search(r"^"+re.escape(p)+r"[;:][^\r\n]+", vevent, re.MULTILINE)
                if not m: return ""
                line = m.group(0)
                line = re.sub(r"\r?\n[ \t]","",line)
                colon_idx = line.rfind(":")
                if colon_idx == -1: return ""
                return line[colon_idx+1:].strip()

            summary     = prop("SUMMARY").replace("\\,",",").replace("\\n"," ")
            dtstart     = prop("DTSTART"); dtend = prop("DTEND")
            rrule       = prop("RRULE")
            recurrence_id = prop("RECURRENCE-ID")
            uid         = prop("UID")
            status      = prop("STATUS").upper()
            location    = prop("LOCATION").replace("\\,",",")
            desc        = prop("DESCRIPTION").replace("\\n"," ").replace("\\,",",")
            if not summary or not dtstart: continue

            # Skip cancelled events
            if status == "CANCELLED":
                continue

            parsed_start, all_day = _parse_dt(dtstart)
            if not parsed_start: continue
            parsed_end, _ = _parse_dt(dtend)

            if rrule:
                # Expand recurring event, respecting EXDATEs and RECURRENCE-ID overrides
                exdates_for_uid = uid_exdates.get(uid, set())
                recurrences = _expand_rrule(
                    parsed_start, parsed_end, all_day, rrule,
                    summary, location, desc,
                    exdates=exdates_for_uid,
                    override_keys=override_keys,
                    uid=uid,
                )
                events.extend(recurrences)
            elif recurrence_id:
                # This is a modification of a specific instance of a recurring event
                # Only include it if it's not cancelled and falls in range
                event_date = parsed_start.date()
                if not (today <= event_date <= lookahead): continue
                if all_day:
                    start_iso = parsed_start.strftime("%Y-%m-%d")
                    end_iso   = start_iso
                else:
                    start_iso = parsed_start.strftime("%Y-%m-%dT%H:%M")
                    end_iso   = parsed_end.strftime("%Y-%m-%dT%H:%M") if parsed_end else ""
                events.append({"title":summary,"start":start_iso,"end":end_iso,
                               "all_day":all_day,"location":location,
                               "notes":desc[:200] if desc else "","calendar":name,
                               "color":color,"source":"subscribed"})
            else:
                # Single non-recurring event
                event_date = parsed_start.date()
                if not (today <= event_date <= lookahead): continue
                if all_day:
                    start_iso = parsed_start.strftime("%Y-%m-%d")
                    end_iso   = start_iso
                else:
                    start_iso = parsed_start.strftime("%Y-%m-%dT%H:%M")
                    end_iso   = parsed_end.strftime("%Y-%m-%dT%H:%M") if parsed_end else ""
                events.append({"title":summary,"start":start_iso,"end":end_iso,
                               "all_day":all_day,"location":location,
                               "notes":desc[:200] if desc else "","calendar":name,
                               "color":color,"source":"subscribed"})

        events.sort(key=lambda e: e["start"])
        return events
    except Exception as e:
        debug_log(f"ICS fetch failed for {name}:", str(e))
        return []


def _do_refresh_subscribed():
    """Background worker: fetch all subscribed ICS calendars and update cache."""
    global _SUBSCRIBED_REFRESHING
    try:
        from datetime import datetime as _dt
        cals = load_subscribed_calendars()
        fresh = []
        for cal in cals:
            if not cal.get("url") or not cal.get("enabled", True):
                continue
            fresh.extend(fetch_ics_events(
                cal["url"], cal.get("name", "Calendar"), cal.get("color", "#9b59b6")
            ))
        fresh.sort(key=lambda e: e["start"])
        save_subscribed_calendar_cache({"events": fresh, "fetched_at": _dt.now().isoformat()})
    except Exception as e:
        debug_log("Subscribed calendar background refresh failed:", str(e))
    finally:
        _SUBSCRIBED_REFRESHING = False


def _apply_calendar_event_filters(events: list) -> list:
    """Remove blocked/hidden events based on calendar_rules.json blocked_event_titles."""
    rules = load_calendar_rules()
    blocked = [t.lower().strip() for t in rules.get("blocked_event_titles", [])]
    if not blocked:
        return events
    return [e for e in events if e.get("title", "").lower().strip() not in blocked]


def refresh_subscribed_calendars(force: bool = False) -> list:
    """Return cached subscribed calendar events immediately; refresh in background if stale."""
    global _SUBSCRIBED_REFRESHING
    import threading as _threading
    from datetime import datetime as _dt
    cache      = load_subscribed_calendar_cache()
    fetched_at = cache.get("fetched_at", "")
    events     = cache.get("events", [])
    stale      = True
    if fetched_at and not force:
        try:
            stale = (_dt.now() - _dt.fromisoformat(fetched_at)).total_seconds() > 1800
        except Exception:
            stale = True
    if stale and not _SUBSCRIBED_REFRESHING:
        _SUBSCRIBED_REFRESHING = True
        _threading.Thread(target=_do_refresh_subscribed, daemon=True).start()
    return _apply_calendar_event_filters(events)


def events_for_date(events: list, iso: str) -> list:
    return [e for e in events if e["start"].startswith(iso) or
            (e["all_day"] and e["start"] <= iso <= (e["end"] or e["start"]))]


def get_all_events(iso: str = "") -> list:
    if not iso: iso = date.today().isoformat()
    try:
        from render_liturgical import get_floating_liturgical_events
        year = int(iso[:4])
        floating = get_floating_liturgical_events([year - 1, year, year + 1])
    except Exception:
        floating = []
    # Manual events from data/events.json (also surfaces /plan-import-apply entries).
    # expand_local_events_for_range filters archived and expands recurrence.
    try:
        local_events = expand_local_events_for_range(iso, iso)
    except Exception:
        local_events = []
    all_events = refresh_calendar() + refresh_subscribed_calendars() + floating + local_events
    all_events.sort(key=lambda e: e["start"])
    return events_for_date(all_events, iso)


# ── Event rendering ───────────────────────────────────────────────────────────
def render_event_pill(event: dict) -> str:
    title    = escape(event.get("title",""))
    location = event.get("location","")
    start    = event.get("start","")
    end      = event.get("end","")
    start_t  = event.get("start_time","")
    end_t    = event.get("end_time","")
    all_day  = event.get("all_day", False)
    color    = event.get("color","#4a90d9")
    cal_name = event.get("calendar","")

    def _fmt_iso(s: str) -> str:
        try:
            from datetime import datetime as _dt
            return _dt.fromisoformat(s).strftime("%-I:%M %p")
        except Exception:
            return ""

    start_str = ""
    end_str   = ""
    if not all_day:
        start_str = start_t or (_fmt_iso(start) if "T" in start else "")
        end_str   = end_t   or (_fmt_iso(end)   if "T" in end   else "")

    if start_str and end_str:
        time_str = f"{start_str} – {end_str}"
    else:
        time_str = start_str

    loc_str   = f" · {escape(location)}" if location else ""
    time_html = f"<span style='color:#888;font-size:0.8em;margin-right:4px;'>{escape(time_str)}</span>" if time_str else ""
    cal_html  = f"<span style='font-size:0.75em;color:#aaa;margin-left:4px;'>{escape(cal_name)}</span>" if cal_name else ""

    # Expandable detail row — shows notes + assignees on tap.
    notes    = event.get("notes", "") or ""
    assigned = event.get("assigned_to", []) or []
    detail_parts = []
    if assigned:
        if isinstance(assigned, list):
            asg_str = ", ".join(str(a) for a in assigned if str(a).strip())
        else:
            asg_str = str(assigned)
        if asg_str.strip():
            detail_parts.append(
                "<div style='font-size:0.78em;color:#7c4a2d;margin-bottom:4px;'>"
                f"<strong>For:</strong> {escape(asg_str)}</div>"
            )
    if notes.strip():
        detail_parts.append(
            "<div style='font-size:0.82em;color:#555;white-space:pre-wrap;'>"
            f"{escape(notes)}</div>"
        )

    on_attr    = ""
    cursor_css = ""
    detail_html = ""
    if detail_parts:
        js = ('this.nextElementSibling.style.display = '
              'this.nextElementSibling.style.display === "none" ? "block" : "none"')
        on_attr    = " onclick='" + js + "'"
        cursor_css = "cursor:pointer;"
        detail_html = (
            "<div style='display:none;padding:6px 14px 10px 22px;"
            "background:#faf6ef;border-bottom:1px solid #f0ebe4;'>"
            + "".join(detail_parts) + "</div>"
        )

    return f"""
    <div>
        <div{on_attr} style="display:flex;align-items:center;gap:6px;padding:5px 0;border-bottom:1px solid #f0ebe4;{cursor_css}">
            <span style="width:8px;height:8px;border-radius:50%;background:{color};flex-shrink:0;"></span>
            {time_html}<span style="font-size:0.9em;">{title}{loc_str}</span>{cal_html}
        </div>
        {detail_html}
    </div>"""


def render_calendar_today_strip(iso: str = "") -> str:
    if not iso: iso = date.today().isoformat()
    cfg      = load_calendar_config()
    apple_id = cfg.get("apple_id", "")
    subs     = load_subscribed_calendars()

    # No credentials and no subscriptions — show setup link
    if not apple_id and not subs:
        return "<div style='color:#aaa;font-size:0.85em;padding:4px 0;'><a href='/settings#s-integrations' style='color:#7c4a2d;'>Set up calendars →</a></div>"

    # Merge cached iCloud + cached subscribed calendar events (both refresh in background)
    caldav_events = refresh_calendar()
    ics_events    = refresh_subscribed_calendars()
    # Manual events from data/events.json (also surfaces /plan-import-apply entries).
    # expand_local_events_for_range filters archived and expands recurrence.
    try:
        local_events = expand_local_events_for_range(iso, iso)
    except Exception:
        local_events = []
    all_events    = sorted(caldav_events + ics_events + local_events, key=lambda e: e["start"])
    today_events = events_for_date(all_events, iso)

    if not today_events:
        return "<p class='muted' style='font-size:0.88em;'>No events today. <a href='/calendar'>Calendar →</a></p>"

    pills = "".join(render_event_pill(e) for e in today_events)
    return f"<div>{pills}<div style='margin-top:6px;'><a class='link-button' href='/calendar' style='font-size:0.8em;'>Full Calendar</a></div></div>"


# ── Calendar page ─────────────────────────────────────────────────────────────
def render_calendar_page(status_message: str = "") -> str:
    cfg        = load_calendar_config()
    apple_id   = cfg.get("apple_id","")
    cache      = load_calendar_cache()
    fetched_at = cache.get("fetched_at","")
    events     = cache.get("events",[])

    # Status bar
    connected = apple_id or load_subscribed_calendars()
    if fetched_at:
        sync_text = f"Last synced: {escape(fetched_at[:16].replace('T',' '))}"
    else:
        sync_text = "Not yet synced"
    status_bar = f"""
    <div style="display:flex;align-items:center;justify-content:space-between;
                flex-wrap:wrap;gap:8px;margin-bottom:16px;">
        <span class="small" style="color:#888;">{sync_text}</span>
        <div class="link-row" style="margin:0;">
            <form method="POST" action="/calendar-refresh" style="display:inline;">
                <button type="submit" class="secondary" style="padding:5px 12px;font-size:0.85em;">↻ Sync</button>
            </form>
            <a class="link-button" href="/settings#s-integrations">⚙ Calendar settings</a>
        </div>
    </div>"""

    if not connected:
        body = f"""
        {page_header("Calendar")}
        {render_status_message(status_message)}
        {status_bar}
        <div class="card">
            <p>No calendar connected yet.</p>
            <a class="link-button" href="/settings#s-integrations">Connect iCloud or add .ics feeds →</a>
        </div>"""
        return html_page("Calendar", body)

    if not events:
        sub_events = refresh_subscribed_calendars()
    else:
        sub_events = refresh_subscribed_calendars()

    today          = date.today()
    # Manual events from data/events.json (also surfaces /plan-import-apply entries).
    # expand_local_events_for_range filters archived and expands recurrence.
    try:
        local_events = expand_local_events_for_range(
            today.isoformat(),
            (today + timedelta(days=365)).isoformat(),
        )
    except Exception:
        local_events = []
    all_cal_events = sorted(events + sub_events + local_events, key=lambda e: e["start"])

    week_html = ""
    for i in range(7):
        d        = today + timedelta(days=i)
        iso      = d.isoformat()
        de       = events_for_date(all_cal_events, iso)
        is_today = (d == today)
        hstyle   = "font-weight:700;color:#7c4a2d;" if is_today else "font-weight:600;"
        tbadge   = " <span class='badge' style='background:#7c4a2d;color:white;font-size:0.75em;'>Today</span>" if is_today else ""
        ev_html  = "".join(render_event_pill(e) for e in de) if de else "<p class='muted' style='font-size:0.85em;'>No events.</p>"
        week_html += f"<div class='card card-tight'><div style='{hstyle}margin-bottom:8px;'>{escape(d.strftime('%A, %B %d'))}{tbadge}</div>{ev_html}</div>"

    week_cutoff    = (today + timedelta(days=7)).isoformat()
    upcoming_html = ""
    for e in all_cal_events[:40]:
        start = e.get("start","")
        if start[:10] < week_cutoff[:10]:
            continue
        try:
            from datetime import datetime as _dt
            if "T" in start:
                dl = _dt.fromisoformat(start).strftime("%a %b %d · %-I:%M %p")
            else:
                dl = _dt.strptime(start[:10],"%Y-%m-%d").strftime("%a %b %d · All day")
        except Exception:
            dl = start
        loc        = f" · {escape(e['location'])}" if e.get("location") else ""
        notes_html = f'<div class="small">{escape(e["notes"][:120])}</div>' if e.get("notes") else ""
        upcoming_html += (
            f"<div class='card card-tight'>"
            f"<div style='font-size:0.82em;color:#888;margin-bottom:2px;'>{escape(dl)}</div>"
            f"<div style='font-weight:600;'>{escape(e.get('title',''))}{loc}</div>"
            f"{notes_html}</div>"
        )

    if not upcoming_html:
        upcoming_html = "<div class='card'><p class='muted'>No upcoming events.</p></div>"

    body = f"""
    {page_header("Calendar")}
    {render_status_message(status_message)}
    {status_bar}
    <div class="two-col">
        <div><h2>This Week</h2>{week_html}</div>
        <div><h2>Upcoming</h2>{upcoming_html}</div>
    </div>"""
    return html_page("Calendar", body)