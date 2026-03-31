# -*- coding: utf-8 -*-
"""
saint_data.py — Rich saint/feast day data for Sancta Familia.

Primary source: Catholic Readings API (cpbjr.github.io)
  - Free, no auth, USCCB-aligned, covers every day
  - Returns: saint name, type, quote, description, image URL
  - URL: https://cpbjr.github.io/catholic-readings-api/readings/YYYY/MM-DD.json

Fallback: Church Calendar API (calapi.inadiutorium.cz)
  - Returns all celebrations including optional memorials

Both cached in data/saint_cache/ to avoid repeated network calls.
"""
import json
import os
import urllib.request
from datetime import date, timedelta
from html import escape

CACHE_DIR = "data/saint_cache"


def _cache_path(for_date: date) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return f"{CACHE_DIR}/{for_date.isoformat()}.json"


def _load_cache(for_date: date) -> dict:
    path = _cache_path(for_date)
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_cache(for_date: date, data: dict):
    try:
        with open(_cache_path(for_date), "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def fetch_saint_data(for_date: date) -> dict:
    """
    Return rich saint data for a given date.

    Returns dict with keys:
        name        - saint name or feast name (str)
        type        - "Solemnity" / "Feast" / "Memorial" / "Optional Memorial" / "Ferial"
        quote       - a quote from or about the saint (str, may be empty)
        description - short bio (str, may be empty)
        image_url   - Wikipedia image URL (str, may be empty)
        source      - which API provided this ("catholic_readings", "calapi", "local")
        bio_url     - link to saint biography page
        all_saints  - list of all saints/celebrations today (list of str)
    """
    # Check cache first
    cached = _load_cache(for_date)
    if cached and cached.get("name"):
        return cached

    result = {}

    # ── Primary: Catholic Readings API ───────────────────────────────────────
    try:
        url = (
            f"https://cpbjr.github.io/catholic-readings-api/readings/"
            f"{for_date.year}/{for_date.month:02d}-{for_date.day:02d}.json"
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": "SanctaFamilia/1.0"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())

        cel = data.get("celebration", {})
        name = cel.get("name", "")
        # Never use season name as saint name — ferial days have no saint
        # (season like "Lent" or "Ordinary Time" is not a saint)
        _season_names = {"lent","advent","christmas","easter","ordinary time",
                         "holy week","lenten season","easter season","christmas season"}
        if name.lower() in _season_names:
            name = ""

        result = {
            "name":        name,
            "type":        cel.get("type", "Ferial").replace("_", " ").title(),
            "quote":       cel.get("quote", ""),
            "description": cel.get("description", ""),
            "image_url":   cel.get("image", ""),
            "bio_url":     (
                f"https://www.catholic.org/saints/stotd.php"
                if name else "https://www.catholic.org/saints/"
            ),
            "all_saints":  [name] if name else [],
            "source":      "catholic_readings",
            "season":      data.get("season", ""),
            "readings":    data.get("readings", {}),
            "usccb_link":  data.get("usccbLink", ""),
        }

        if result["name"]:
            _save_cache(for_date, result)
            return result

    except Exception:
        pass

    # ── Fallback: Church Calendar API ────────────────────────────────────────
    try:
        url = (
            f"http://calapi.inadiutorium.cz/api/v0/en/calendars/default/"
            f"{for_date.year}/{for_date.month}/{for_date.day}"
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": "SanctaFamilia/1.0"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())

        celebrations = data.get("celebrations", [])
        # Filter out pure ferial days, prefer actual saint celebrations
        saints = [
            c for c in celebrations
            if c.get("title") and c.get("rank") != "ferial"
        ]
        if not saints:
            saints = celebrations

        primary = saints[0] if saints else {}
        name    = primary.get("title", "")
        rank    = primary.get("rank", "ferial").replace("_", " ").title()

        result = {
            "name":        name,
            "type":        rank,
            "quote":       "",
            "description": "",
            "image_url":   "",
            "bio_url":     "https://mycatholic.life/saints/saints-of-the-liturgical-year/",
            "all_saints":  [c.get("title","") for c in saints if c.get("title")],
            "source":      "calapi",
            "season":      data.get("season", ""),
            "readings":    {},
            "usccb_link":  (
                f"https://bible.usccb.org/bible/readings/"
                f"{for_date.strftime('%m%d%y')}.cfm"
            ),
        }

        _save_cache(for_date, result)
        return result

    except Exception:
        pass

    # ── Final fallback: empty ────────────────────────────────────────────────
    result = {
        "name":        "",
        "type":        "Ferial",
        "quote":       "",
        "description": "",
        "image_url":   "",
        "bio_url":     "https://mycatholic.life/saints/saints-of-the-liturgical-year/",
        "all_saints":  [],
        "source":      "none",
        "season":      "",
        "readings":    {},
        "usccb_link":  (
            f"https://bible.usccb.org/bible/readings/"
            f"{for_date.strftime('%m%d%y')}.cfm"
        ),
    }
    return result


def get_saint_html_card(for_date: date, dark: bool = False) -> str:
    """
    Returns an HTML card showing today's saint with bio, quote, and image.
    dark=True for use on dark background (dashboard spiritual card).
    """
    data = fetch_saint_data(for_date)
    name        = data.get("name", "")
    feast_type  = data.get("type", "")
    quote       = data.get("quote", "")
    description = data.get("description", "")
    image_url   = data.get("image_url", "")
    bio_url     = data.get("bio_url", "https://mycatholic.life/saints/saints-of-the-liturgical-year/")
    all_saints  = data.get("all_saints", [])

    txt_color   = "var(--gold-light)" if dark else "var(--ink)"
    sub_color   = "rgba(245,234,216,0.6)" if dark else "var(--ink-muted)"
    border_col  = "rgba(201,164,74,0.3)" if dark else "var(--border-light)"
    bg_extra    = "background:rgba(255,255,255,0.05);" if dark else "background:var(--parchment);"

    if not name:
        return (
            f'<div style="padding:10px 0;">'
            f'<div style="font-size:0.72em;font-weight:700;letter-spacing:.1em;'
            f'text-transform:uppercase;color:{sub_color};margin-bottom:4px;">Saint of the Day</div>'
            f'<div style="font-size:0.85em;color:{sub_color};">No feast today &mdash; feria</div>'
            f'<a href="{escape(bio_url)}" target="_blank" '
            f'style="font-size:0.75em;color:var(--brown);margin-top:4px;display:inline-block;">'
            f'All saints today ↗</a>'
            f'</div>'
        )

    # Type badge color
    type_colors = {
        "Solemnity": "#c49020",
        "Feast":     "#8b5a3c",
        "Memorial":  "#2d5016",
        "Optional Memorial": "#555",
    }
    type_color = type_colors.get(feast_type, "#888")

    # Image if available
    img_html = ""
    if image_url:
        img_html = (
            f'<img src="{escape(image_url)}" alt="{escape(name)}" '
            f'style="float:right;width:64px;height:64px;object-fit:cover;'
            f'border-radius:50%;margin:0 0 8px 12px;border:2px solid {border_col};">'
        )

    # Additional saints
    others_html = ""
    if len(all_saints) > 1:
        others = [s for s in all_saints[1:] if s][:3]
        if others:
            others_html = (
                f'<div style="font-size:0.72em;color:{sub_color};margin-top:6px;">'
                f'Also: {escape(", ".join(others))}</div>'
            )

    # Quote
    quote_html = ""
    if quote:
        quote_html = (
            f'<div style="font-style:italic;font-size:0.82em;color:{sub_color};'
            f'margin-top:8px;padding:8px 10px;{bg_extra}border-radius:8px;">'
            f'&ldquo;{escape(quote)}&rdquo;</div>'
        )

    # Description (truncated)
    desc_html = ""
    if description:
        short = description[:180] + ("..." if len(description) > 180 else "")
        desc_html = (
            f'<div style="font-size:0.8em;color:{sub_color};margin-top:6px;">'
            f'{escape(short)}</div>'
        )

    return (
        f'<div style="padding:10px 0;">'
        f'{img_html}'
        f'<div style="font-size:0.72em;font-weight:700;letter-spacing:.1em;'
        f'text-transform:uppercase;color:{sub_color};margin-bottom:4px;">Saint of the Day</div>'
        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
        f'<span style="font-size:0.95em;font-weight:700;color:{txt_color};">{escape(name)}</span>'
        f'<span style="font-size:0.7em;font-weight:700;color:{type_color};'
        f'background:{type_color}18;border-radius:4px;padding:2px 6px;">{escape(feast_type)}</span>'
        f'</div>'
        f'{others_html}'
        f'{quote_html}'
        f'{desc_html}'
        f'<a href="{escape(bio_url)}" target="_blank" '
        f'style="font-size:0.75em;color:var(--brown);margin-top:8px;display:inline-block;">'
        f'Full biography ↗</a>'
        f'<div style="clear:both;"></div>'
        f'</div>'
    )


def prefetch_week(start_date: date = None):
    """Pre-fetch and cache saint data for the next 7 days. Call on app startup."""
    if start_date is None:
        start_date = date.today()
    for i in range(7):
        d = start_date + timedelta(days=i)
        if not _load_cache(d):
            try:
                fetch_saint_data(d)
            except Exception:
                pass
