"""
render_liturgy_hours.py — Liturgy of the Hours

Fetches Universalis pages for each office once per week (auto on Sundays if
setting is on, or manually). Stores per-day JSON in data/liturgy_hours/.
Keeps at most one week of files (Mon–Sun); older files are deleted on every
fetch and on app startup. A background thread checks every hour so the
download happens even if the app is never restarted on a Sunday.

Routes:
  GET  /liturgy-hours              — today
  GET  /liturgy-hours?date=YYYY-MM-DD
  POST /liturgy-hours-fetch        — manual fetch for a week
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
    """Delete day files outside the current Mon–Sun week. At most 7 files kept."""
    _ensure_dir()
    monday = _week_monday(date.today())
    sunday = monday + timedelta(days=6)
    try:
        for fn in os.listdir(HOURS_DIR):
            if not fn.endswith(".json"):
                continue
            try:
                file_date = date.fromisoformat(fn.replace(".json", ""))
                if file_date < monday or file_date > sunday:
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


def maybe_auto_fetch():
    """
    Called at app startup. Fetches this week if:
      - auto_fetch_hours setting is True
      - today is Sunday
      - week not already fetched
    Also cleans up old files whenever a fresh fetch is triggered.
    """
    try:
        settings = load_app_settings()
        if not settings.get("auto_fetch_hours", False):
            return
        today = date.today()
        if today.weekday() != 6:   # 6 = Sunday
            return
        monday = _week_monday(today)
        if _week_already_fetched(monday):
            return
        import threading
        threading.Thread(target=_fetch_and_clean, args=(monday,), daemon=True).start()
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
                monday = _week_monday(today)
                if _week_already_fetched(monday):
                    continue
                _fetch_and_clean(monday)
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
        link_label = ('Pray ✝' if (is_now and fetched) else ('Open →' if fetched else 'Fetch →'))
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

    if not fetched:
        fetch_note = (
            f'<div style="margin-top:8px;padding:7px 10px;background:#fef3c7;'
            f'border-radius:8px;font-size:0.75em;color:#92400e;">'
            f'Not yet downloaded. '
            f'<a href="/settings#s-app" style="color:#92400e;font-weight:700;">'
            f'Fetch in Settings</a> or '
            f'<a href="/liturgy-hours" style="color:#92400e;font-weight:700;">view online links</a>.'
            f'</div>'
        )
    else:
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

    prev_d    = (target - timedelta(days=1)).isoformat()
    next_d    = (target + timedelta(days=1)).isoformat()
    is_today  = (target == today)
    day_label = target.strftime("%A, %B %-d, %Y")

    rec         = load_day_hours(target)
    fetched     = rec.get("fetched", False)
    completions = rec.get("completions", {})
    current_key = _current_office() if is_today else ""

    settings = load_app_settings()
    api_key  = (settings.get("anthropic_api_key", "") or
                settings.get("family_constraints", {}).get("anthropic_api_key", ""))

    # Liturgical info
    season = "Ordinary Time"
    try:
        from render_liturgical import get_liturgical_season
        season = get_liturgical_season(target)
    except Exception:
        pass

    # Build office cards
    office_cards = ""
    for key, name, subtitle, start_h, end_h, icon in OFFICES:
        done      = completions.get(key, False)
        is_now    = (key == current_key)
        text      = rec.get("offices", {}).get(key, "")
        anchor_id = key

        # Card border/bg based on state
        if is_now and not done:
            border = "2px solid var(--gold-mid)"
            bg     = "var(--gold-light)"
        elif done:
            border = "1.5px solid #bbf7d0"
            bg     = "#f0fdf4"
        else:
            border = "1.5px solid var(--border)"
            bg     = "white"

        # Time range label
        def _fmt_h(h):
            if h == 0:   return "12 AM"
            elif h < 12: return f"{h} AM"
            elif h == 12: return "12 PM"
            else:        return f"{h-12} PM"
        time_range = f"{_fmt_h(start_h)} \u2013 {_fmt_h(end_h)}"

        # Prayer content
        if text:
            formatted = ""
            prev_blank = False
            for line in text.splitlines():
                stripped = line.rstrip()
                raw = stripped.strip()

                if not raw:
                    if not prev_blank:
                        formatted += '<div style="height:6px;"></div>'
                    prev_blank = True
                    continue
                prev_blank = False

                if raw.startswith("===") and raw.endswith("==="):
                    # Section heading
                    heading = escape(raw.strip("= ").strip())
                    formatted += (
                        f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.12em;'
                        f'text-transform:uppercase;color:var(--brown);margin:14px 0 4px;'
                        f'padding-top:10px;border-top:1px solid var(--border-light);">'
                        f'{heading}</div>'
                    )
                elif raw.startswith("**") and raw.endswith("**"):
                    bold = escape(raw.strip("*"))
                    formatted += (
                        f'<div style="font-weight:700;font-size:0.88em;color:var(--ink);'
                        f'margin:6px 0 2px;">{bold}</div>'
                    )
                elif stripped.startswith("  ") or stripped.startswith("\t"):
                    # Indented — psalm verse response
                    is_italic = raw.startswith("_") and raw.endswith("_")
                    text_content = escape(raw.strip("_") if is_italic else raw)
                    style = "font-style:italic;" if is_italic else ""
                    formatted += (
                        f'<div style="font-size:0.85em;line-height:1.75;color:var(--ink-muted);'
                        f'padding-left:16px;{style}">{text_content}</div>'
                    )
                elif raw.startswith("_") and raw.endswith("_"):
                    # Italics — antiphon or response
                    formatted += (
                        f'<div style="font-size:0.85em;line-height:1.75;color:var(--brown);'
                        f'font-style:italic;margin:2px 0;">{escape(raw.strip("_"))}</div>'
                    )
                else:
                    formatted += (
                        f'<div style="font-size:0.88em;line-height:1.8;color:var(--ink);'
                        f'margin:1px 0;">{escape(raw)}</div>'
                    )
            content_html = (
                f'<div id="text-{key}" style="display:none;margin-top:12px;'
                f'max-height:60vh;overflow-y:auto;padding:12px;'
                f'background:white;border-radius:10px;'
                f'border:1px solid var(--border-light);">'
                f'{formatted}'
                f'<div style="margin-top:16px;padding-top:10px;'
                f'border-top:1px solid var(--border-light);">'
                f'<a href="https://universalis.com/{target.strftime("%Y%m%d")}/{key}.htm" '
                f'target="_blank" style="font-size:0.75em;color:var(--brown);font-weight:600;">'
                f'View on Universalis \u2197</a></div>'
                f'</div>'
            )
            pray_label = 'Pray \u271d' if not done else 'Review'
            toggle_btn = (
                f'<button onclick="toggleOffice(\'{key}\')" '
                f'style="padding:5px 14px;font-size:0.78em;border-radius:8px;'
                f'background:var(--ink);color:var(--gold-light);border:none;'
                f'font-family:inherit;cursor:pointer;font-weight:600;">'
                + pray_label + '</button>'
            )
        else:
            # Not fetched — show Universalis link
            univ_url = f"https://universalis.com/{target.strftime('%Y%m%d')}/{key}.htm"
            content_html = ""
            toggle_btn = (
                f'<a href="{univ_url}" target="_blank" '
                f'style="padding:5px 14px;font-size:0.78em;border-radius:8px;'
                f'background:var(--parchment);color:var(--brown);border:1px solid var(--border);'
                f'text-decoration:none;font-weight:600;">'
                f'Open on Universalis \u2197</a>'
            )

        prayed_label = 'Prayed \u2713' if done else 'Mark as prayed'
        prayed_color = '#166534' if done else 'var(--ink-faint)'
        done_check = (
            f'<label style="display:flex;align-items:center;gap:6px;cursor:pointer;">'
            f'<input type="checkbox" {"checked" if done else ""} '
            f'onchange="markDone(\'{key}\', this.checked)" '
            f'style="width:16px;height:16px;accent-color:#22c55e;flex-shrink:0;">'
            f'<span style="font-size:0.78em;color:{prayed_color};">'
            + prayed_label + '</span>'
            f'</label>'
        )

        now_badge = ""
        if is_now and not done:
            now_badge = (
                f'<span style="font-size:0.65em;background:#fef3c7;color:#92400e;'
                f'font-weight:700;padding:2px 7px;border-radius:10px;margin-left:6px;">'
                f'Now</span>'
            )

        office_cards += (
            f'<div id="{anchor_id}" style="border:{border};border-radius:12px;'
            f'padding:14px;margin-bottom:10px;background:{bg};">'
            f'<div style="display:flex;align-items:flex-start;'
            f'justify-content:space-between;gap:8px;">'
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<span style="font-size:1.4em;">{icon}</span>'
            f'<div>'
            f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
            f'font-size:1.2rem;font-weight:600;color:var(--ink);">'
            f'{escape(name)}{now_badge}</div>'
            f'<div style="font-size:0.72em;color:var(--ink-faint);">'
            f'{escape(subtitle)} \u00b7 {time_range}</div>'
            f'</div></div>'
            f'<div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end;">'
            f'{toggle_btn}'
            f'{done_check}'
            f'</div></div>'
            f'{content_html}'
            f'</div>'
        )

    # Fetch status banner
    if not fetched:
        monday   = _week_monday(target)
        week_end = monday + timedelta(days=6)
        fetch_banner = (
            f'<div style="padding:12px 16px;background:#fef3c7;border-radius:10px;'
            f'margin-bottom:14px;display:flex;align-items:center;'
            f'justify-content:space-between;flex-wrap:wrap;gap:8px;">'
            f'<div>'
            f'<div style="font-size:0.82em;font-weight:700;color:#92400e;">'
            f'This week\u2019s Hours have not been downloaded yet.</div>'
            f'<div style="font-size:0.75em;color:#a16207;margin-top:2px;">'
            f'Week of {monday.strftime("%B %d")} \u2013 {week_end.strftime("%B %d")}</div>'
            f'</div>'
            f'<div style="display:flex;gap:8px;flex-wrap:wrap;">'
            f'<button onclick="fetchWeek()" '
            f'style="padding:7px 16px;background:#92400e;color:white;border:none;'
            f'border-radius:8px;font-family:inherit;font-size:0.82em;'
            f'cursor:pointer;font-weight:600;">'
            f'\u2193 Download this week</button>'
            f'<a href="https://universalis.com" target="_blank" '
            f'style="padding:7px 16px;background:transparent;border:1px solid #92400e;'
            f'color:#92400e;border-radius:8px;font-size:0.82em;text-decoration:none;">'
            f'Open Universalis \u2197</a>'
            f'</div></div>'
            f'<div id="fetch-status" style="font-size:0.82em;color:#166534;'
            f'min-height:16px;margin-bottom:4px;"></div>'
        )
    else:
        done_count  = sum(1 for k, *_ in OFFICES if completions.get(k))
        monday_str  = _week_monday(target).strftime("%B %d")
        fetch_banner = (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'flex-wrap:wrap;gap:8px;'
            f'padding:8px 12px;background:#f0fdf4;border-radius:10px;margin-bottom:14px;">'
            f'<div style="font-size:0.82em;color:#166534;font-weight:600;">'
            f'{done_count} of {len(OFFICES)} offices prayed today</div>'
            f'<div style="display:flex;gap:8px;align-items:center;">'
            f'<button onclick="fetchWeek(true)" '
            f'style="padding:4px 10px;font-size:0.75em;font-weight:600;font-family:inherit;'
            f'background:transparent;border:1px solid #166534;color:#166534;'
            f'border-radius:6px;cursor:pointer;">'
            f'\u21ba Re-download</button>'
            f'<a href="https://universalis.com" target="_blank" '
            f'style="font-size:0.75em;color:var(--brown);text-decoration:none;">'
            f'Universalis \u2197</a>'
            f'</div></div>'
            f'<div id="fetch-status" style="font-size:0.82em;color:#166534;'
            f'min-height:16px;margin-bottom:4px;"></div>'
        )

    rec_js = json.dumps(rec)

    body = top_nav() + render_status_message(status) + f"""
<div style="display:flex;align-items:flex-start;justify-content:space-between;
            flex-wrap:wrap;gap:8px;padding-top:4px;margin-bottom:16px;">
  <div>
    <div style="font-family:'Cormorant Garamond',Georgia,serif;
                font-size:2rem;font-weight:600;color:var(--ink);">
      Liturgy of the Hours
    </div>
    <div style="font-size:0.85em;color:var(--ink-muted);margin-top:2px;">
      {escape(day_label)} &middot; {escape(season)}
    </div>
  </div>
  <div style="display:flex;gap:6px;flex-wrap:wrap;">
    <a href="/liturgy-hours?date={prev_d}"
       style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;
              font-size:0.82em;text-decoration:none;color:var(--ink);">&larr;</a>
    {"" if is_today else '<a href="/liturgy-hours" style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);">Today</a>'}
    {"" if is_today else '<a href="/liturgy-hours?date=' + next_d + '" style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);">&rarr;</a>'}
  </div>
</div>

{fetch_banner}
{office_cards}

<div style="display:flex;gap:8px;flex-wrap:wrap;padding:8px 0;">
  <a href="/5am" style="font-size:0.82em;color:var(--brown);font-weight:700;text-decoration:none;">5AM Club &rarr;</a>
  <span style="color:var(--border);">|</span>
  <a href="/virtues" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">Virtue Tracker &rarr;</a>
</div>

<script>
var _date = '{escape(target.isoformat())}';
var _rec  = {rec_js};

function toggleOffice(key) {{
  var el = document.getElementById('text-' + key);
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}}

// Auto-open office if ?open=key in URL
(function() {{
  var params = new URLSearchParams(window.location.search);
  var openKey = params.get('open');
  if (openKey) {{
    var el = document.getElementById('text-' + openKey);
    if (el) {{
      el.style.display = 'block';
      setTimeout(function() {{
        var anchor = document.getElementById(openKey);
        if (anchor) anchor.scrollIntoView({{behavior:'smooth', block:'start'}});
      }}, 100);
    }}
  }}
}})();

function markDone(key, checked) {{
  if (!_rec.completions) _rec.completions = {{}};
  _rec.completions[key] = checked;
  fetch('/liturgy-hours-save', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'date=' + encodeURIComponent(_date) +
          '&data=' + encodeURIComponent(JSON.stringify(_rec))
  }}).then(function() {{
    // Update card style
    var card = document.getElementById(key);
    if (!card) return;
    if (checked) {{
      card.style.border     = '1.5px solid #bbf7d0';
      card.style.background = '#f0fdf4';
    }} else {{
      card.style.border     = '1.5px solid var(--border)';
      card.style.background = 'white';
    }}
  }});
}}

function fetchWeek(force) {{
  var btn = event ? event.target : document.querySelector('button[onclick^="fetchWeek"]');
  if (btn) {{ btn.textContent = '\u231b Downloading\u2026'; btn.disabled = true; }}
  fetch('/liturgy-hours-fetch', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'date=' + encodeURIComponent(_date) + (force ? '&force=1' : '')
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    var el = document.getElementById('fetch-status');
    if (el) {{
      el.style.display = 'block';
      el.textContent   = d.ok ? 'Downloaded! Reloading\u2026' : ('Error: ' + (d.error || 'unknown'));
    }}
    if (d.ok) setTimeout(function() {{ location.reload(); }}, 800);
    else if (btn) {{ btn.textContent = '\u2193 Download this week'; btn.disabled = false; }}
  }}).catch(function(e) {{
    if (btn) {{ btn.textContent = '\u2193 Download this week'; btn.disabled = false; }}
  }});
}}
</script>
"""
    return html_page("Liturgy of the Hours", body)