"""
render_daily_bar.py — Daily info bar: weather, saint of the day, gospel link, special events.
Also provides child age helpers used on child pages and print pages.
Data sources:
  - Weather: wttr.in (free, no API key)
  - Saint / gospel: render_liturgical + USCCB URL
  - Special events: data/app_settings.json
  - Child birthdays: data/app_settings.json
"""
from datetime import date, datetime, timedelta
from html import escape

from safe_utils import ensure_file, safe_save_json, debug_log
from render_liturgical import get_day_info


APP_SETTINGS_FILE = "data/app_settings.json"


# ── App settings helpers ───────────────────────────────────────────────────────
def _load() -> dict:
    return ensure_file(APP_SETTINGS_FILE, {})


def get_location() -> str:
    return _load().get("location", "")


def get_child_birthdays() -> dict:
    """Return {child_name: 'YYYY-MM-DD'} for children with birthdays set."""
    return _load().get("child_birthdays", {})


def get_special_events() -> list:
    """Return list of {label, date (YYYY-MM-DD or '')} dicts."""
    return _load().get("special_events", [])


# ── Weather ────────────────────────────────────────────────────────────────────
# Module-level weather cache — refreshes at most once per 30 minutes
_WEATHER_CACHE: dict = {}
_WEATHER_CACHE_TIME: float = 0.0
_WEATHER_CACHE_TTL: float = 30 * 60  # 30 minutes
_WEATHER_FETCHING: bool = False       # guard against duplicate background fetches


def _fetch_weather_background(location: str) -> None:
    """Fetch weather in a background thread and populate the cache."""
    global _WEATHER_CACHE, _WEATHER_CACHE_TIME, _WEATHER_FETCHING
    try:
        import urllib.request as _ur, json as _json, time as _t
        loc_enc = location.strip().replace(" ", "+")
        url = f"https://wttr.in/{loc_enc}?format=j1"
        req = _ur.Request(url, headers={"User-Agent": "FamilyPlanner/1.0"})
        with _ur.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        _populate_weather_cache(data)
        _WEATHER_CACHE_TIME = _t.time()
    except Exception:
        pass
    finally:
        _WEATHER_FETCHING = False


def _populate_weather_cache(data: dict) -> None:
    global _WEATHER_CACHE
    import datetime as _dt
    cur   = data["current_condition"][0]
    today_data = data["weather"][0]
    condition = cur.get("weatherDesc", [{}])[0].get("value", "")
    temp_f    = int(cur.get("temp_F", 0))
    feels_f   = int(cur.get("FeelsLikeF", temp_f))
    high_f    = int(today_data.get("maxtempF", temp_f))
    low_f     = int(today_data.get("mintempF", temp_f))

    def _icon_for(cond: str) -> str:
        c = cond.lower()
        if any(w in c for w in ("thunder", "storm")):        return "⛈"
        if any(w in c for w in ("snow", "blizzard", "sleet")): return "❄️"
        if any(w in c for w in ("rain", "drizzle", "shower")):  return "🌧"
        if any(w in c for w in ("cloud", "overcast", "fog", "mist")): return "☁️"
        if any(w in c for w in ("sunny", "clear")):          return "☀️"
        if "partly" in c:                                     return "⛅"
        return "🌤"

    forecast = []
    today_date = _dt.date.today()
    for i, day_data in enumerate(data.get("weather", [])[:3]):
        d_date = today_date + _dt.timedelta(days=i)
        d_label = "Today" if i == 0 else d_date.strftime("%a")
        hourly = day_data.get("hourly", [])
        mid_idx = len(hourly) // 2
        d_cond = hourly[mid_idx].get("weatherDesc", [{}])[0].get("value", "") if hourly else ""
        forecast.append({
            "label": d_label,
            "high_f": int(day_data.get("maxtempF", 0)),
            "low_f":  int(day_data.get("mintempF", 0)),
            "icon":   _icon_for(d_cond),
        })

    _WEATHER_CACHE = {
        "temp_f": temp_f, "feels_like_f": feels_f, "condition": condition,
        "icon": _icon_for(condition), "high_f": high_f, "low_f": low_f,
        "forecast": forecast,
    }


def fetch_weather(location: str) -> dict:
    """
    Return cached weather immediately; kick off a background refresh if stale.
    Never blocks a page load — worst case returns empty dict on very first call.
    """
    global _WEATHER_FETCHING
    import time as _time, threading as _threading
    if not location:
        return {}
    now = _time.time()
    # Return cached value if still fresh
    if _WEATHER_CACHE and (now - _WEATHER_CACHE_TIME) < _WEATHER_CACHE_TTL:
        return _WEATHER_CACHE
    # Cache is stale (or empty) — start a background fetch if one isn't running
    if not _WEATHER_FETCHING:
        _WEATHER_FETCHING = True
        _threading.Thread(target=_fetch_weather_background, args=(location,),
                          daemon=True).start()
    # Return whatever we have (may be empty on very first boot — shows "Weather unavailable")
    return _WEATHER_CACHE


# ── Child age helpers ──────────────────────────────────────────────────────────
def get_child_age(child: str, as_of: date = None) -> dict:
    """
    Return age breakdown for a child.
    Returns dict with months, weeks, days, hours, years, dob_str
    or empty dict if no birthday set.
    """
    if as_of is None:
        as_of = date.today()
    birthdays = get_child_birthdays()
    dob_str   = birthdays.get(child, "")
    if not dob_str:
        return {}
    try:
        dob = date.fromisoformat(dob_str)
    except Exception:
        return {}

    delta       = as_of - dob
    total_days  = delta.days
    if total_days < 0:
        return {}

    total_weeks  = total_days // 7
    total_months = 0
    d = dob
    while True:
        # Advance one month
        month = d.month + 1 if d.month < 12 else 1
        year  = d.year if d.month < 12 else d.year + 1
        try:
            import calendar
            max_day = calendar.monthrange(year, month)[1]
            next_d  = d.replace(year=year, month=month, day=min(d.day, max_day))
        except Exception:
            break
        if next_d > as_of:
            break
        total_months += 1
        d = next_d

    years         = total_months // 12
    months_rem    = total_months % 12
    total_hours   = total_days * 24
    total_minutes = total_days * 24 * 60
    total_seconds = total_days * 24 * 60 * 60

    return {
        "dob_str":      dob_str,
        "years":        years,
        "months":       total_months,
        "months_rem":   months_rem,
        "weeks":        total_weeks,
        "days":         total_days,
        "hours":        total_hours,
        "minutes":      total_minutes,
        "seconds":      total_seconds,
    }


def render_child_age_strip(child: str, as_of: date = None) -> str:
    """Compact one-line age strip for child schedule pages and print."""
    age = get_child_age(child, as_of)
    if not age:
        return ""
    y  = age["years"]
    m  = age["months"]
    w  = age["weeks"]
    d  = age["days"]
    h  = age["hours"]
    mn = age["minutes"]
    sc = age["seconds"]
    return (
        f"<span style='font-size:0.82em;color:#888;'>"
        f"{y}y {age['months_rem']}mo &nbsp;&middot;&nbsp; "
        f"{m:,} months &nbsp;&middot;&nbsp; "
        f"{w:,} weeks &nbsp;&middot;&nbsp; "
        f"{d:,} days &nbsp;&middot;&nbsp; "
        f"{h:,} hours &nbsp;&middot;&nbsp; "
        f"{mn:,} minutes &nbsp;&middot;&nbsp; "
        f"{sc:,} seconds"
        f"</span>"
    )


# ── Special events ─────────────────────────────────────────────────────────────
def get_todays_special_events(for_date: date = None) -> list:
    """Return list of event labels that are today or have no date (always-show)."""
    if for_date is None:
        for_date = date.today()
    iso = for_date.isoformat()
    events = get_special_events()
    result = []
    for ev in events:
        ev_date = ev.get("date", "").strip()
        label   = ev.get("label", "").strip()
        if not label:
            continue
        if not ev_date or ev_date == iso:
            result.append(label)
    return result


# ── Daily bar ──────────────────────────────────────────────────────────────────
def render_daily_bar(for_date: date = None, compact: bool = False) -> str:
    """
    Full-width daily info bar.
    compact=True gives a denser single-row version for print pages.
    """
    if for_date is None:
        for_date = date.today()

    # Liturgical info
    lit      = get_day_info(for_date)
    feast    = lit.get("feast_name", "")
    season   = lit.get("season", "")
    vest_bg  = lit.get("season_color", "#6b7280")
    vest_txt = lit.get("season_text_color", "white")

    # Saint of day — use cached saint_data if available
    saint_label = ""
    saint_url   = "https://mycatholic.life/saints/saints-of-the-liturgical-year/"
    _season_names_bar = {"lent","advent","christmas","easter","ordinary time","holy week"}
    try:
        from saint_data import fetch_saint_data as _fsd
        _sd = _fsd(for_date)
        _nm = _sd.get("name","")
        if _nm and _nm.lower() not in _season_names_bar:
            saint_label = _nm
            saint_url   = _sd.get("bio_url", saint_url)
    except Exception:
        pass
    if not saint_label:
        saint_label = feast if (feast and feast.lower() not in _season_names_bar) else ""

    # Gospel / mass readings
    readings_url = f"https://bible.usccb.org/bible/readings/{for_date.strftime('%m%d%y')}.cfm"

    # Weather
    location = get_location()
    weather  = fetch_weather(location) if location else {}

    # Special events
    events = get_todays_special_events(for_date)

    # ── Weather pill ────────────────────────────────────────────────────────
    if weather:
        icon      = weather["icon"]
        temp      = weather["temp_f"]
        high      = weather["high_f"]
        low       = weather["low_f"]
        condition = weather["condition"]
        forecast  = weather.get("forecast", [])
        if location:
            w_label = escape(location.split(",")[0].strip())
        else:
            w_label = ""

        # 3-day forecast mini-strip
        forecast_html = ""
        if forecast:
            day_pills = ""
            for fc in forecast:
                day_pills += (
                    f'<div style="display:flex;flex-direction:column;align-items:center;'
                    f'gap:1px;min-width:38px;">'
                    f'<span style="font-size:0.72em;color:#aaa;font-weight:600;">'
                    f'{escape(fc["label"])}</span>'
                    f'<span style="font-size:0.95em;">{fc["icon"]}</span>'
                    f'<span style="font-size:0.72em;color:#555;">'
                    f'{fc["high_f"]}° <span style="color:#bbb">{fc["low_f"]}°</span></span>'
                    f'</div>'
                )
            forecast_html = (
                f'<div style="display:flex;gap:8px;align-items:flex-start;'
                f'border-left:1px solid #e0d8d0;padding-left:10px;margin-left:4px;">'
                f'{day_pills}</div>'
            )

        weather_html = f"""
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
            <div style="display:flex;align-items:center;gap:6px;white-space:nowrap;">
                <span style="font-size:1.1em;">{icon}</span>
                <span style="font-weight:600;">{temp}°F</span>
                <span style="color:#888;font-size:0.88em;">{escape(condition)} · H:{high} L:{low}</span>
                {f'<span style="font-size:0.82em;color:#aaa;">({w_label})</span>' if w_label else ""}
            </div>
            {forecast_html}
        </div>"""
    elif location:
        weather_html = f'<span style="font-size:0.85em;color:#aaa;">Weather unavailable</span>'
    else:
        weather_html = f'<a href="/settings#s-general" style="font-size:0.82em;color:#aaa;">Add location for weather →</a>'

    # ── Saint pill ──────────────────────────────────────────────────────────
    if saint_label:
        saint_html = (
            f'<div style="display:flex;align-items:center;gap:5px;white-space:nowrap;">'
            f'<span style="font-size:0.88em;color:#888;">\u271d</span>'
            f'<a href="{saint_url}" target="_blank"'
            f' style="font-size:0.88em;font-weight:600;color:#7c4a2d;max-width:200px;'
            f'overflow:hidden;text-overflow:ellipsis;display:inline-block;">'
            f'{escape(saint_label)}</a>'
            f'</div>'
        )
    else:
        saint_html = f'<span style="font-size:0.82em;color:#aaa;">\u271d Feria</span>'

    # ── Gospel pill ─────────────────────────────────────────────────────────
    gospel_html = f"""
    <a href="/readings?date={for_date.isoformat()}"
       style="font-size:0.88em;font-weight:600;color:#4a6a9e;white-space:nowrap;">
        📖 Mass Readings
    </a>"""

    # ── Season pill ─────────────────────────────────────────────────────────
    season_html = f"""
    <span style="background:{vest_bg};color:{vest_txt};font-size:0.78em;font-weight:700;
                 padding:2px 10px;border-radius:999px;white-space:nowrap;">
        {escape(season)}
    </span>"""

    # ── Special events ──────────────────────────────────────────────────────
    events_html = ""
    for ev in events:
        events_html += f"""
        <span style="background:#fef9c3;border:1px solid #fde047;color:#713f12;
                     font-size:0.82em;font-weight:700;padding:2px 10px;border-radius:999px;
                     white-space:nowrap;">
            ⭐ {escape(ev)}
        </span>"""

    if compact:
        # Print-friendly single line — no weather, simpler layout
        return f"""
        <div style="border:1px solid #e0d8d0;border-radius:8px;padding:6px 12px;
                    margin-bottom:12px;display:flex;flex-wrap:wrap;gap:10px;align-items:center;
                    font-family:Georgia,serif;font-size:10pt;">
            {season_html}
            {saint_html}
            {gospel_html}
            {events_html}
        </div>"""

    _settings_link_html = (
        '<a href="/settings#s-daily" style="margin-left:auto;font-size:0.78em;color:#ccc;">&#9881;</a>'
        if not location else ""
    )
    # ── Single combined card: weather on top, liturgy row below ─────────────
    _divider = '<div style="width:1px;height:14px;background:#e0d8d0;flex-shrink:0;margin:0 8px;"></div>'
    _lit_row = f"""
        <div style="padding:7px 14px;display:flex;flex-wrap:nowrap;gap:0;
                    align-items:center;overflow:hidden;font-size:0.82em;">
            {season_html}
            {_divider}
            {saint_html}
            {_divider}
            {gospel_html}
            {events_html}
            {_settings_link_html}
        </div>"""

    if weather:
        return f"""
    <div style="background:white;border:1px solid #e4dbd2;border-radius:14px;
                margin-bottom:14px;overflow:hidden;">
        <div style="padding:9px 14px;border-bottom:1px solid #f0e8e0;font-size:0.82em;">
            {weather_html}
        </div>
        {_lit_row}
    </div>"""
    else:
        return f"""
    <div style="background:white;border:1px solid #e4dbd2;border-radius:14px;
                margin-bottom:14px;overflow:hidden;">
        {_lit_row}
    </div>"""

    # (unreachable — kept for reference)
    return f"""
    <div style="background:white;border:1px solid #e4dbd2;border-radius:12px;
                padding:8px 16px;margin-bottom:16px;
                display:flex;flex-wrap:nowrap;gap:0;align-items:center;overflow:hidden;">
        {_settings_link_html}
    </div>"""