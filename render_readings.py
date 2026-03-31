"""
render_readings.py — Daily Mass readings page.

Fetches reading citations from saint_data (Catholic Readings API) and
retrieves the actual scripture text from bible-api.com (free, no key).
Caches scripture text locally to avoid repeated network calls.
"""
import json
import os
import re
import urllib.request
from datetime import date
from html import escape

from saint_data import fetch_saint_data

READINGS_CACHE_DIR = "data/readings_cache"


def _readings_cache_path(for_date: date) -> str:
    os.makedirs(READINGS_CACHE_DIR, exist_ok=True)
    return f"{READINGS_CACHE_DIR}/{for_date.isoformat()}.json"


def _load_readings_cache(for_date: date) -> dict:
    path = _readings_cache_path(for_date)
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_readings_cache(for_date: date, data: dict):
    try:
        with open(_readings_cache_path(for_date), "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _clean_reference(ref: str) -> str:
    """
    Normalize a lectionary citation for bible-api.com.
    e.g. 'Isaiah 49:1-6' -> 'Isaiah+49:1-6'
         'Psalm 71:1-2, 3-4a, 5ab-6ab, 15 and 17' -> 'Psalm+71:1-2,3-4,5-6,15,17'
    """
    # Strip verse-letter suffixes like '4a', '6ab'
    ref = re.sub(r'(\d+)[a-z]+\b', r'\1', ref)
    # Replace ' and ' with ','
    ref = ref.replace(' and ', ',')
    # Collapse multiple spaces/commas
    ref = re.sub(r',\s*', ',', ref)
    ref = re.sub(r'\s+', ' ', ref).strip()
    # URL-encode spaces
    ref = ref.replace(' ', '+')
    return ref


def _fetch_scripture_text(reference: str) -> str:
    """
    Fetch actual scripture text from bible-api.com.
    Returns the text or empty string on failure.
    """
    if not reference:
        return ""
    cleaned = _clean_reference(reference)
    url = f"https://bible-api.com/{cleaned}?translation=web"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SanctaFamilia/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        return data.get("text", "").strip()
    except Exception:
        return ""


def fetch_readings_for_date(for_date: date) -> dict:
    """
    Return a dict with:
        usccb_link      - str
        first_reading   - {reference, text}
        psalm           - {reference, text}
        second_reading  - {reference, text}  (may be empty on ferias)
        gospel          - {reference, text}
        season          - str
        feast_name      - str
    """
    cached = _load_readings_cache(for_date)
    if cached and cached.get("_complete"):
        return cached

    saint = fetch_saint_data(for_date)
    citations = saint.get("readings", {})
    usccb_link = saint.get("usccb_link", "") or (
        f"https://bible.usccb.org/bible/readings/{for_date.strftime('%m%d%y')}.cfm"
    )

    first_ref   = citations.get("firstReading", "")
    psalm_ref   = citations.get("psalm", "")
    second_ref  = citations.get("secondReading", "")
    gospel_ref  = citations.get("gospel", "")

    result = {
        "_complete":      True,
        "usccb_link":     usccb_link,
        "season":         saint.get("season", ""),
        "feast_name":     saint.get("name", ""),
        "first_reading":  {"reference": first_ref,  "text": _fetch_scripture_text(first_ref)  if first_ref  else ""},
        "psalm":          {"reference": psalm_ref,  "text": _fetch_scripture_text(psalm_ref)  if psalm_ref  else ""},
        "second_reading": {"reference": second_ref, "text": _fetch_scripture_text(second_ref) if second_ref else ""},
        "gospel":         {"reference": gospel_ref, "text": _fetch_scripture_text(gospel_ref) if gospel_ref else ""},
    }

    _save_readings_cache(for_date, result)
    return result


# ---------------------------------------------------------------------------
# HTML page renderer
# ---------------------------------------------------------------------------

def _reading_block(label: str, reading: dict, accent: str = "#1a3870") -> str:
    ref  = reading.get("reference", "")
    text = reading.get("text", "")
    if not ref:
        return ""

    text_html = ""
    if text:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        text_html = "".join(
            f'<p style="margin:0 0 10px 0;line-height:1.7;font-size:0.95em;">'
            f'{escape(p)}</p>'
            for p in paragraphs
        )
    else:
        text_html = (
            f'<p style="color:#aaa;font-style:italic;font-size:0.88em;">'
            f'Text could not be loaded automatically &mdash; '
            f'<a href="#usccb" style="color:#4a6a9e;">view on USCCB ↓</a></p>'
        )

    return f"""
    <div style="margin-bottom:28px;border-left:4px solid {accent};padding-left:16px;">
        <div style="font-size:0.72em;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
                    color:{accent};margin-bottom:4px;">{escape(label)}</div>
        <div style="font-size:0.9em;font-weight:600;color:#444;margin-bottom:10px;">{escape(ref)}</div>
        <div style="color:#222;">{text_html}</div>
    </div>"""


def render_readings_page(date_str: str = "") -> str:
    try:
        for_date = date.fromisoformat(date_str) if date_str else date.today()
    except Exception:
        for_date = date.today()

    readings = fetch_readings_for_date(for_date)

    season     = readings.get("season", "")
    feast_name = readings.get("feast_name", "")
    usccb_link = readings.get("usccb_link", "")
    date_label = for_date.strftime("%A, %B %d, %Y")

    subtitle = feast_name or season or ""

    # Navigation: prev / next day
    prev_date = (for_date - __import__('datetime').timedelta(days=1)).isoformat()
    next_date = (for_date + __import__('datetime').timedelta(days=1)).isoformat()

    nav_html = f"""
    <div style="display:flex;gap:12px;align-items:center;margin-bottom:20px;">
        <a href="/readings?date={prev_date}"
           style="font-size:0.85em;color:#4a6a9e;text-decoration:none;">&larr; Previous day</a>
        <span style="flex:1;text-align:center;font-size:0.8em;color:#aaa;">{escape(date_label)}</span>
        <a href="/readings?date={next_date}"
           style="font-size:0.85em;color:#4a6a9e;text-decoration:none;">Next day &rarr;</a>
    </div>"""

    # Build reading blocks
    blocks = ""
    blocks += _reading_block("First Reading", readings.get("first_reading", {}), "#8b5a3c")
    blocks += _reading_block("Responsorial Psalm", readings.get("psalm", {}), "#2d5016")
    second = readings.get("second_reading", {})
    if second and second.get("reference"):
        blocks += _reading_block("Second Reading", second, "#8b5a3c")
    blocks += _reading_block("Gospel", readings.get("gospel", {}), "#1a3870")

    if not blocks.strip():
        blocks = (
            '<p style="color:#888;text-align:center;padding:40px 0;">'
            'Reading citations are not available for this date yet.<br>'
            f'<a href="{escape(usccb_link)}" target="_blank" style="color:#4a6a9e;">'
            'View on USCCB ↗</a></p>'
        )

    usccb_html = ""
    if usccb_link:
        usccb_html = f"""
        <div id="usccb" style="margin-top:32px;padding-top:20px;border-top:1px solid #e0d8d0;
                                text-align:center;">
            <a href="{escape(usccb_link)}" target="_blank"
               style="display:inline-block;background:#1a3870;color:white;
                      font-size:0.88em;font-weight:600;padding:10px 22px;
                      border-radius:8px;text-decoration:none;">
                📖 Full Mass Readings on USCCB ↗
            </a>
            <div style="font-size:0.75em;color:#aaa;margin-top:8px;">
                Includes commentary, optional readings, and audio
            </div>
        </div>"""

    source_note = (
        '<div style="font-size:0.72em;color:#ccc;text-align:center;margin-top:20px;">'
        'Scripture text: World English Bible (WEB) via bible-api.com &middot; '
        'Citations: Catholic Readings API</div>'
    )

    body = f"""
    <div style="max-width:680px;margin:0 auto;padding:20px 16px 60px;">

        <div style="margin-bottom:24px;">
            <a href="/" style="font-size:0.82em;color:#aaa;text-decoration:none;">&larr; Dashboard</a>
        </div>

        {nav_html}

        <div style="margin-bottom:24px;">
            <div style="font-size:0.78em;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
                        color:#888;margin-bottom:4px;">Daily Mass Readings</div>
            <h1 style="font-family:Georgia,serif;font-size:1.7em;font-weight:600;color:#1a1a1a;
                       margin:0 0 4px 0;">{escape(date_label)}</h1>
            {f'<div style="font-size:0.9em;color:#8b5a3c;font-style:italic;">{escape(subtitle)}</div>' if subtitle else ''}
        </div>

        <div style="background:white;border:1px solid #e4dbd2;border-radius:12px;padding:28px 24px;">
            {blocks}
        </div>

        {usccb_html}
        {source_note}
    </div>"""

    from ui_helpers import html_page
    return html_page("Mass Readings", body)
