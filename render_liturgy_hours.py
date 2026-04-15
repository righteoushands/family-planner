"""
render_liturgy_hours.py — Liturgy of the Hours

Primary display: embedded Divine Office (divineoffice.org) iframe.
Completion tracking (mark as prayed) stored locally per day.
Universalis auto-fetch is retained as a background process so cached
text remains available if needed, but the main UI uses the DO embed.

Routes:
  GET  /liturgy-hours              — today
  GET  /liturgy-hours?date=YYYY-MM-DD
  POST /liturgy-hours-fetch        — manual fetch (background, optional)
"""
import json, os, re
from datetime import date, timedelta
from html import escape

from render_settings import load_app_settings, save_app_settings
from ui_helpers import html_page, top_nav, render_status_message

HOURS_DIR = "data/liturgy_hours"

OFFICES = [
    ("lauds",    "Lauds",    "Morning Prayer",  5,  8,  "\U0001f305"),
    ("terce",    "Terce",    "Mid-Morning",      9,  10, "\u2600\ufe0f"),
    ("sext",     "Sext",     "Midday Prayer",   12,  13, "\u2600\ufe0f"),
    ("none",     "None",     "Afternoon Prayer", 14, 16, "\U0001f324\ufe0f"),
    ("vespers",  "Vespers",  "Evening Prayer",  17,  20, "\U0001f307"),
    ("compline", "Compline", "Night Prayer",    21,  23, "\U0001f319"),
]


def _ensure_dir():
    os.makedirs(HOURS_DIR, exist_ok=True)


def _day_path(d: date) -> str:
    return f"{HOURS_DIR}/{d.isoformat()}.json"


def load_day_hours(d: date = None) -> dict:
    _ensure_dir()
    if d is None:
        d = date.today()
    path = _day_path(d)
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"date": d.isoformat(), "offices": {}, "completions": {}, "fetched": False}


def save_day_hours(data: dict):
    _ensure_dir()
    path = f"{HOURS_DIR}/{data['date']}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def cleanup_old_files():
    """Delete day files that are more than one day in the past.
    Keeps the current week AND any pre-fetched future days (e.g. next week
    downloaded on Sunday). At most ~14 files can accumulate before the old
    week rolls off naturally.
    """
    _ensure_dir()
    yesterday = date.today() - timedelta(days=1)
    try:
        for fn in os.listdir(HOURS_DIR):
            if not fn.endswith(".json"):
                continue
            try:
                file_date = date.fromisoformat(fn.replace(".json", ""))
                if file_date < yesterday:
                    os.remove(f"{HOURS_DIR}/{fn}")
            except Exception:
                pass
    except Exception:
        pass


def _week_monday(d: date = None) -> date:
    if d is None:
        d = date.today()
    return d - timedelta(days=d.weekday())


def _week_already_fetched(monday: date) -> bool:
    """True if all 7 days of the week have been fetched."""
    for i in range(7):
        d = monday + timedelta(days=i)
        rec = load_day_hours(d)
        if not rec.get("fetched"):
            return False
    return True


def _get_universalis_country() -> str:
    """Return the Universalis country slug from settings, defaulting to United States."""
    try:
        from render_settings import load_app_settings
        return load_app_settings().get("universalis_country", "United States")
    except Exception:
        return "United States"


def _fetch_office_text(office_key: str, d: date) -> str:
    """
    Fetch one office from Universalis and extract the prayer text.
    Returns plain text with basic structure preserved.
    Note: Universalis country selection is session/cookie based, not URL based.
    We use the general calendar URL which works reliably.
    """
    import urllib.request as _ur2
    date_str = d.strftime("%Y%m%d")
    url = f"https://universalis.com/{date_str}/{office_key}.htm"
    try:
        req = _ur2.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        })
        with _ur2.urlopen(req, timeout=15) as resp:
            html_bytes = resp.read()
        html_text = html_bytes.decode("utf-8", errors="replace")

        # Strip scripts, styles, nav, header, footer, the dates/links sidebar
        for tag in ['script','style','nav','header','footer']:
            html_text = re.sub(r'<'+tag+r'[^>]*>.*?</'+tag+r'>', '', html_text,
                               flags=re.DOTALL | re.IGNORECASE)

        # Universalis puts the sidebar (dates/links/calendar) in a div with class "day"
        # and prayer content in divs with class "section" inside a main content area.
        # Strategy: grab everything between the page title and the "Dates" heading
        # by finding the first <h1> or <h2> and taking until the sidebar begins.

        # Remove the sidebar div entirely (class="sidebar", id="dates", class="dates" etc.)
        html_text = re.sub(
            r'<div[^>]+(?:class|id)=["\'][^"\']*(?:sidebar|dates|links|calendar|copyright|podcast)[^"\']*["\'][^>]*>.*?</div>',
            '', html_text, flags=re.DOTALL | re.IGNORECASE
        )

        # Now grab the body content
        m = re.search(r'<body[^>]*>(.*?)</body>', html_text, flags=re.DOTALL | re.IGNORECASE)
        content = m.group(1) if m else html_text

        # Convert headings to our === markers
        content = re.sub(r'<h[1-4][^>]*>(.*?)</h[1-4]>', r'\n=== \1 ===\n',
                         content, flags=re.DOTALL | re.IGNORECASE)

        # Italic → underscore (responses/antiphons)
        content = re.sub(r'<(?:em|i)[^>]*>(.*?)</(?:em|i)>', r'_\1_',
                         content, flags=re.DOTALL | re.IGNORECASE)

        # Bold
        content = re.sub(r'<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>', r'**\1**',
                         content, flags=re.DOTALL | re.IGNORECASE)

        # Non-breaking spaces → real indent
        content = content.replace('&nbsp;&nbsp;', '  ').replace('&nbsp;', ' ')

        # Line breaks
        content = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
        content = re.sub(r'<p[^>]*>', '\n', content, flags=re.IGNORECASE)
        content = re.sub(r'</p>', '\n', content, flags=re.IGNORECASE)
        content = re.sub(r'<div[^>]*>', '\n', content, flags=re.IGNORECASE)
        content = re.sub(r'</div>', '\n', content, flags=re.IGNORECASE)

        # Strip all remaining tags
        content = re.sub(r'<[^>]+>', '', content)

        # Decode HTML entities
        import html as _html_mod
        content = _html_mod.unescape(content)

        # Clean up lines — remove nav debris, cut off at date sidebar / copyright
        lines = content.splitlines()
        clean_lines = []
        skip_keywords = {
            'pages','links','donate','tweet','podcast','cookie','copyright',
            'universalis','general calendar','local calendars','other dates',
            'click here','(top)','spoken word','show qr','settings',
            'latin and english', 'calendar used', 'contact us', 'cookies/privacy',
            'how to listen',
        }
        # Day-of-week patterns that indicate the date sidebar has started
        import re as _re2
        _day_pat = _re2.compile(
            r'^(sun|mon|tue|wed|thu|fri|sat)\s+\d+\s+\w+$', _re2.IGNORECASE
        )
        _copyright_pat = _re2.compile(r'copyright\s*©', _re2.IGNORECASE)

        blank_run = 0
        for line in lines:
            s   = line.rstrip()
            low = s.strip().lower()

            # Stop entirely when we hit the date sidebar or copyright
            if _day_pat.match(low): break
            if _copyright_pat.search(low): break
            if low in ('other dates', 'calendar used'): break

            # Skip individual nav debris lines
            if low in skip_keywords: continue
            if low.startswith('http'): continue

            if not s.strip():
                blank_run += 1
                if blank_run <= 2:
                    clean_lines.append('')
            else:
                blank_run = 0
                clean_lines.append(s)

        return '\n'.join(clean_lines).strip()
    except Exception as e:
        # Try to get response body for diagnosis
        err_detail = str(e)
        try:
            import urllib.error as _ue
            if hasattr(e, 'read'):
                body_preview = e.read(200).decode('utf-8','replace')
                err_detail = f"{e} | Response: {body_preview[:100]}"
        except Exception:
            pass
        return f"[Could not fetch — check connection. Error: {err_detail}]"


def fetch_week(monday: date = None, offices_to_fetch=None):
    """
    Fetch all offices for all 7 days of the week starting monday.
    Runs in background thread — updates files as each office completes.
    """
    if monday is None:
        monday = _week_monday()
    if offices_to_fetch is None:
        offices_to_fetch = [o[0] for o in OFFICES]

    for i in range(7):
        d = monday + timedelta(days=i)
        rec = load_day_hours(d)
        for office_key in offices_to_fetch:
            if office_key not in rec.get("offices", {}):
                text = _fetch_office_text(office_key, d)
                rec.setdefault("offices", {})[office_key] = text
        rec["fetched"] = True
        rec["date"]    = d.isoformat()
        save_day_hours(rec)


def _fetch_and_clean(monday: date):
    """Cleanup old files then fetch the full week. Runs in a background thread."""
    cleanup_old_files()
    fetch_week(monday)


def _next_week_monday(today: date = None) -> date:
    """Return the Monday of *next* week (7 days after this week's Monday)."""
    if today is None:
        today = date.today()
    return _week_monday(today) + timedelta(days=7)


def maybe_auto_fetch():
    """
    Called at app startup. On Sundays, pre-fetches *next* week's prayers if:
      - auto_fetch_hours setting is True
      - today is Sunday
      - next week not already fetched
    Also cleans up old files whenever a fresh fetch is triggered.
    """
    try:
        settings = load_app_settings()
        if not settings.get("auto_fetch_hours", False):
            return
        today = date.today()
        if today.weekday() != 6:   # 6 = Sunday
            return
        # Pre-fetch NEXT week so prayers are ready when Monday arrives
        next_monday = _next_week_monday(today)
        if _week_already_fetched(next_monday):
            return
        import threading
        threading.Thread(target=_fetch_and_clean, args=(next_monday,), daemon=True).start()
    except Exception:
        pass


def start_weekly_scheduler():
    """
    Long-running background thread that fires once a week on Sunday.
    Handles the case where the app stays up across a Sunday without restarting.
    Checks every hour; on Sunday morning triggers fetch+cleanup if not done yet.
    """
    import threading, time
    from datetime import datetime

    def _run():
        while True:
            try:
                now = datetime.now()
                # Sleep until the next top-of-hour
                secs_to_next_hour = 3600 - (now.minute * 60 + now.second)
                time.sleep(max(secs_to_next_hour, 60))

                settings = load_app_settings()
                if not settings.get("auto_fetch_hours", False):
                    continue
                today = date.today()
                if today.weekday() != 6:   # only on Sunday
                    continue
                # Pre-fetch NEXT week
                next_monday = _next_week_monday(today)
                if _week_already_fetched(next_monday):
                    continue
                _fetch_and_clean(next_monday)
            except Exception:
                time.sleep(3600)

    t = threading.Thread(target=_run, daemon=True, name="universalis-weekly")
    t.start()


def _current_office() -> str:
    """Return the office key appropriate for the current hour."""
    from datetime import datetime
    h = datetime.now().hour
    if h < 9:    return "lauds"
    elif h < 12: return "terce"
    elif h < 14: return "sext"
    elif h < 17: return "none"
    elif h < 21: return "vespers"
    else:        return "compline"


# ── Dashboard widget ──────────────────────────────────────────────────────────

def render_hours_dashboard_widget() -> str:
    settings = load_app_settings()
    if not settings.get("show_liturgy_hours_widget", True):
        return ""

    today       = date.today()
    rec         = load_day_hours(today)
    fetched     = rec.get("fetched", False)
    completions = rec.get("completions", {})
    current_key = _current_office()

    rows = ""
    for key, name, subtitle, start_h, end_h, icon in OFFICES:
        done      = completions.get(key, False)
        is_now    = (key == current_key)
        bg        = "var(--gold-light)" if is_now else "transparent"
        fw        = "700" if is_now else "400"
        col       = "var(--ink)" if is_now else "var(--ink-muted)"
        check_col = "#22c55e" if done else ("#f59e0b" if is_now else "#e5e7eb")
        link = f"/liturgy-hours?date={today.isoformat()}&open={key}#{key}"

        check_mark = '<span style="font-size:0.75em;font-weight:700;color:#22c55e;">✓</span>' if done else ''
        link_label = 'Pray ✝' if (is_now and not done) else ('✓ Done' if done else 'Open →')
        rows += (
            '<div style="display:flex;align-items:center;gap:8px;padding:5px 8px;'
            'border-radius:8px;background:' + bg + ';margin-bottom:2px;">'
            '<span style="font-size:0.9em;">' + icon + '</span>'
            '<div style="flex:1;">'
            '<div style="font-size:0.82em;font-weight:' + fw + ';color:' + col + ';">' + escape(name) + '</div>'
            '<div style="font-size:0.65em;color:var(--ink-faint);">' + escape(subtitle) + '</div>'
            '</div>'
            + check_mark +
            '<a href="' + link + '" style="font-size:0.7em;color:var(--brown);font-weight:600;'
            'text-decoration:none;">' + link_label + '</a>'
            '</div>'
        )

    done_count = sum(1 for k, *_ in OFFICES if completions.get(k))
    fetch_note = (
        f'<div style="font-size:0.72em;color:var(--ink-faint);margin-top:6px;">'
        f'{done_count} of {len(OFFICES)} offices prayed today</div>'
    )

    return (
        f'<div class="card" style="margin-bottom:14px;">'
        f'<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;'
        f'text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;'
        f'display:flex;justify-content:space-between;align-items:center;">'
        f'<span>\u271d Liturgy of the Hours</span>'
        f'<a href="/liturgy-hours" style="font-size:0.9em;color:var(--brown);'
        f'font-weight:600;text-decoration:none;text-transform:none;">'
        f'Full view &rarr;</a></div>'
        f'{rows}'
        f'{fetch_note}'
        f'</div>'
    )


# ── Full page ─────────────────────────────────────────────────────────────────

def render_liturgy_hours_page(date_str: str = None, status: str = "") -> str:
    today = date.today()
    if date_str:
        try:
            target = date.fromisoformat(date_str)
        except Exception:
            target = today
    else:
        target = today

    is_today  = (target == today)
    day_label = target.strftime("%A, %B %-d, %Y")

    rec         = load_day_hours(target)
    completions = rec.get("completions", {})
    current_key = _current_office() if is_today else ""

    # Liturgical info
    season = "Ordinary Time"
    try:
        from render_liturgical import get_liturgical_season
        season = get_liturgical_season(target)
    except Exception:
        pass

    done_count = sum(1 for k, *_ in OFFICES if completions.get(k))

    # ── Completion tracker row ──────────────────────────────────────────────
    tracker_items = ""
    for key, name, subtitle, start_h, end_h, icon in OFFICES:
        done   = completions.get(key, False)
        is_now = (key == current_key)
        bg     = "#f0fdf4" if done else ("var(--gold-light)" if is_now else "var(--parchment)")
        border = "#bbf7d0" if done else ("#f59e0b" if is_now else "var(--border)")
        color  = "#166534" if done else ("var(--ink)" if is_now else "var(--ink-muted)")
        fw     = "700" if (done or is_now) else "400"
        check  = "✓ " if done else ("▶ " if is_now else "")
        tracker_items += (
            f'<label style="display:flex;flex-direction:column;align-items:center;'
            f'gap:3px;cursor:pointer;flex:1;min-width:0;">'
            f'<input type="checkbox" {"checked" if done else ""} '
            f'onchange="markDone(\'{key}\', this.checked)" '
            f'style="position:absolute;opacity:0;pointer-events:none;">'
            f'<div onclick="markDone(\'{key}\', {str(not done).lower()})" '
            f'style="width:100%;text-align:center;padding:7px 4px;border-radius:8px;'
            f'background:{bg};border:1.5px solid {border};'
            f'font-size:0.7em;font-weight:{fw};color:{color};'
            f'cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
            f'{check}{icon} {escape(name)}</div>'
            f'</label>'
        )

    tracker_html = (
        f'<div style="margin-bottom:10px;">'
        f'<div style="display:flex;gap:5px;margin-bottom:4px;">'
        f'{tracker_items}'
        f'</div>'
        f'<div style="font-size:0.72em;color:var(--ink-faint);text-align:right;">'
        f'{done_count} of {len(OFFICES)} prayed today</div>'
        f'</div>'
    )

    rec_js = json.dumps(rec)

    body = top_nav() + render_status_message(status) + f"""
<div style="display:flex;align-items:center;justify-content:space-between;
            gap:8px;padding-top:4px;margin-bottom:10px;">
  <div>
    <div style="font-family:'Cormorant Garamond',Georgia,serif;
                font-size:1.7rem;font-weight:600;color:var(--ink);line-height:1.1;">
      Liturgy of the Hours
    </div>
    <div style="font-size:0.82em;color:var(--ink-muted);margin-top:2px;">
      {escape(season)}
    </div>
  </div>
  <a href="https://divineoffice.org" target="_blank"
     style="font-size:0.72em;color:var(--brown);font-weight:600;
            text-decoration:none;white-space:nowrap;flex-shrink:0;">
    divineoffice.org &#8599;
  </a>
</div>

{tracker_html}

<!-- Divine Office embed -->
<div style="border-radius:12px;overflow:hidden;border:1.5px solid var(--border);
            background:white;margin-bottom:14px;">
  <iframe
    src="https://divineoffice.org"
    style="width:100%;height:82vh;border:none;display:block;"
    title="Divine Office — Liturgy of the Hours"
    loading="lazy"
    allow="autoplay; encrypted-media"
  ></iframe>
</div>

<div style="display:flex;gap:8px;flex-wrap:wrap;padding:4px 0 8px;">
  <a href="/5am" style="font-size:0.82em;color:var(--brown);font-weight:700;text-decoration:none;">5AM Club &rarr;</a>
  <span style="color:var(--border);">|</span>
  <a href="/virtues" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">Virtue Tracker &rarr;</a>
</div>

<script>
var _date = '{escape(target.isoformat())}';
var _rec  = {rec_js};

function markDone(key, checked) {{
  if (!_rec.completions) _rec.completions = {{}};
  _rec.completions[key] = checked;
  fetch('/liturgy-hours-save', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'date=' + encodeURIComponent(_date) +
          '&data=' + encodeURIComponent(JSON.stringify(_rec))
  }}).then(function() {{
    location.reload();
  }});
}}
</script>
"""
    return html_page("Liturgy of the Hours", body)