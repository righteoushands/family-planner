"""
render_timeblock.py — Lauren's time-block homepage.

Five blocks driven by server (Eastern) time. Each block shows a
full-screen contemplative image, time-appropriate prayers, today's
prayer intentions, optional novena prompt, and a small practical
snapshot (FROL slot + meals).

Block schedule:
  05:00–06:59  → early_morning
  07:00–11:59  → morning
  12:00–16:59  → afternoon
  17:00–19:59  → evening
  20:00–04:59  → late_evening   (wraps through midnight)
"""
import os
import re
import json
from datetime import date, datetime, timedelta
from html import escape

try:
    from zoneinfo import ZoneInfo
    _EASTERN = ZoneInfo("America/New_York")
except ImportError:
    import pytz
    _EASTERN = pytz.timezone("America/New_York")


# ─────────────────────────────────────────────────────────────────────────────
# Time blocks
# ─────────────────────────────────────────────────────────────────────────────

def _now_eastern() -> datetime:
    try:
        return datetime.now(_EASTERN)
    except Exception:
        return datetime.now()


def _resolve_block(now_dt: datetime) -> str:
    h = now_dt.hour
    if 5 <= h <= 6:
        return "early_morning"
    if 7 <= h <= 11:
        return "morning"
    if 12 <= h <= 16:
        return "afternoon"
    if 17 <= h <= 19:
        return "evening"
    return "late_evening"  # 20-23 and 0-4


_BLOCK_LABELS = {
    "early_morning": "Early Morning",
    "morning":       "Morning",
    "afternoon":     "Afternoon",
    "evening":       "Evening",
    "late_evening":  "Night",
}

_BLOCK_GREETINGS = {
    "early_morning": "Praised be Jesus Christ.",
    "morning":       "Good morning, Lauren.",
    "afternoon":     "Peace be with you.",
    "evening":       "How was the day?",
    "late_evening":  "He gives sleep to His beloved.",
}


# ─────────────────────────────────────────────────────────────────────────────
# Image resolution (priority cascade with graceful fallback)
# ─────────────────────────────────────────────────────────────────────────────

_SEASON_FOR_MONTH = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}

_SEASON_GRADIENT = {
    "winter": "linear-gradient(180deg,#3a4a6b 0%,#6c7d99 50%,#aab8cd 100%)",
    "spring": "linear-gradient(180deg,#7a9c5a 0%,#a8c47e 50%,#dce8b8 100%)",
    "summer": "linear-gradient(180deg,#3a6b8a 0%,#6ca0b8 50%,#c2dde8 100%)",
    "autumn": "linear-gradient(180deg,#7a3e1a 0%,#b8703c 50%,#e0b078 100%)",
}

# Unsplash Source API (no API key required) — seasonal nature photography.
# Format: https://source.unsplash.com/1600x900/?{comma-separated-query}
_UNSPLASH_QUERIES = {
    "spring": "spring,nature,flowers,peaceful",
    "summer": "summer,nature,golden,light",
    "autumn": "autumn,leaves,warm,forest",
    "winter": "winter,snow,peaceful,forest",
}

def _unsplash_url(season: str) -> str:
    q = _UNSPLASH_QUERIES.get(season, _UNSPLASH_QUERIES["spring"])
    return "https://source.unsplash.com/1600x900/?" + q

# Curated public-domain sacred art from Wikimedia Commons.
# Each entry: feast_slug -> (needle_substring_to_match_in_feast_name_lower, image_url).
# All works are pre-1928 old-master paintings or PD-tagged Commons files.
_FEAST_ART = {
    "our-lady-of-fatima": (
        "fatima",
        "https://upload.wikimedia.org/wikipedia/commons/9/9b/Statue_of_Our_Lady_of_F%C3%A1tima.jpg",
    ),
    "immaculate-conception": (
        "immaculate conception",
        "https://upload.wikimedia.org/wikipedia/commons/c/c6/Bartolom%C3%A9_Esteban_Murillo_-_The_Immaculate_Conception_of_the_Venerable_Ones_-_Google_Art_Project.jpg",
    ),
    "assumption": (
        "assumption",
        "https://upload.wikimedia.org/wikipedia/commons/9/9c/Titian_-_Assumption_of_the_Virgin_-_WGA22833.jpg",
    ),
    "annunciation": (
        "annunciation",
        "https://upload.wikimedia.org/wikipedia/commons/0/0c/ANGELICO%2C_Fra_Annunciation%2C_1437-46_%282236990916%29.jpg",
    ),
    "nativity-of-mary": (
        "birth of the bless",
        "https://upload.wikimedia.org/wikipedia/commons/6/6f/Giotto_-_Scrovegni_-_-07-_-_Birth_of_the_Virgin.jpg",
    ),
    "our-lady-of-guadalupe": (
        "guadalupe",
        "https://upload.wikimedia.org/wikipedia/commons/3/35/1531_Nuestra_Se%C3%B1ora_de_Guadalupe_anagoria.jpg",
    ),
    "easter": (
        "easter",
        "https://upload.wikimedia.org/wikipedia/commons/9/95/Piero_della_Francesca_-_Resurrection_-_WGA17609.jpg",
    ),
    "christmas": (
        "christmas",
        "https://upload.wikimedia.org/wikipedia/commons/3/35/Bartolom%C3%A9_Esteban_Perez_Murillo_022.jpg",
    ),
    "pentecost": (
        "pentecost",
        "https://upload.wikimedia.org/wikipedia/commons/5/5a/Titian_-_Pentecost_-_WGA22852.jpg",
    ),
    "ascension": (
        "ascension",
        "https://upload.wikimedia.org/wikipedia/commons/5/55/Giotto_-_Scrovegni_-_-38-_-_Ascension.jpg",
    ),
}

def _feast_art_url(feast_name: str) -> str:
    if not feast_name:
        return ""
    n = feast_name.lower()
    for _slug, pair in _FEAST_ART.items():
        needle, url = pair
        if needle in n:
            return url
    return ""


def _slugify(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def _is_marian(feast_name: str) -> bool:
    if not feast_name:
        return False
    n = feast_name.lower()
    needles = (
        "mary", "lady", "annunciation", "assumption", "immaculate",
        "visitation", "queenship", "sorrows", "guadalupe", "lourdes",
        "fatima", "carmel", "presentation of the bless",
    )
    return any(x in n for x in needles)


def _file_exists(rel_path: str) -> bool:
    try:
        return os.path.isfile(rel_path)
    except Exception:
        return False


def _resolve_image(iso: str) -> dict:
    """
    Returns {"url": "/static/...", "credit": "...", "fallback_gradient": "..."}.
    Priority:
      1. /static/images/timeblock/feasts/{slug}.jpg
      2. /static/images/timeblock/marian/{slug}.jpg  (if Marian feast)
      3. /static/images/timeblock/feasts/{season}.jpg  (season name as feast)
      4. /static/images/timeblock/seasons/{season}/N.jpg  (rotating)
    """
    try:
        d = datetime.fromisoformat(iso).date()
    except Exception:
        d = _now_eastern().date()
    season = _SEASON_FOR_MONTH.get(d.month, "spring")
    gradient = _SEASON_GRADIENT.get(season, _SEASON_GRADIENT["spring"])

    feast_name = ""
    try:
        from render_liturgical import get_day_info
        info = get_day_info(d)
        feast_name = (info.get("feast_name") or "").strip()
    except Exception:
        info = {}

    base = "static/images/timeblock"

    if feast_name:
        slug = _slugify(feast_name)
        cand = f"{base}/feasts/{slug}.jpg"
        if _file_exists(cand):
            return {"url": "/" + cand, "credit": feast_name, "fallback_gradient": gradient}
        # Curated Wikimedia public-domain sacred art for major feasts
        art_url = _feast_art_url(feast_name)
        if art_url:
            return {"url": art_url, "credit": feast_name, "fallback_gradient": gradient}
        if _is_marian(feast_name):
            cand_m = f"{base}/marian/{slug}.jpg"
            if _file_exists(cand_m):
                return {"url": "/" + cand_m, "credit": feast_name, "fallback_gradient": gradient}

    # Season fallbacks: rotating image by day-of-year
    season_dir = f"{base}/seasons/{season}"
    if os.path.isdir(season_dir):
        try:
            files = sorted([f for f in os.listdir(season_dir)
                            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))])
            if files:
                idx = (d.timetuple().tm_yday) % len(files)
                return {
                    "url": "/" + season_dir + "/" + files[idx],
                    "credit": season.capitalize(),
                    "fallback_gradient": gradient,
                }
        except Exception:
            pass

    # Unsplash Source API — seasonal nature photography (no API key)
    return {
        "url": _unsplash_url(season),
        "credit": season.capitalize(),
        "fallback_gradient": gradient,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Rosary mysteries
# ─────────────────────────────────────────────────────────────────────────────

_MYSTERIES = {
    "Joyful": {
        "days": ["Monday", "Saturday"],
        "list": [
            ("The Annunciation",          "Humility"),
            ("The Visitation",            "Love of Neighbor"),
            ("The Nativity",              "Poverty of Spirit"),
            ("The Presentation",          "Obedience"),
            ("The Finding in the Temple", "Joy in Finding Jesus"),
        ],
    },
    "Sorrowful": {
        "days": ["Tuesday", "Friday"],
        "list": [
            ("The Agony in the Garden", "Sorrow for Sin"),
            ("The Scourging at the Pillar", "Purity"),
            ("The Crowning with Thorns", "Courage"),
            ("The Carrying of the Cross", "Patience"),
            ("The Crucifixion", "Final Perseverance"),
        ],
    },
    "Glorious": {
        "days": ["Sunday", "Wednesday"],
        "list": [
            ("The Resurrection",            "Faith"),
            ("The Ascension",               "Hope"),
            ("The Descent of the Holy Spirit", "Wisdom"),
            ("The Assumption of Mary",      "Devotion to Mary"),
            ("The Coronation of Mary",      "Eternal Happiness"),
        ],
    },
    "Luminous": {
        "days": ["Thursday"],
        "list": [
            ("The Baptism in the Jordan",        "Openness to the Holy Spirit"),
            ("The Wedding at Cana",              "To Jesus through Mary"),
            ("The Proclamation of the Kingdom",  "Repentance and Trust in God"),
            ("The Transfiguration",              "Desire for Holiness"),
            ("The Institution of the Eucharist", "Eucharistic Adoration"),
        ],
    },
}


def _rosary_for(weekday: str) -> dict:
    for name, blob in _MYSTERIES.items():
        if weekday in blob["days"]:
            return {"name": name, "list": blob["list"]}
    return {"name": "Glorious", "list": _MYSTERIES["Glorious"]["list"]}


# ─────────────────────────────────────────────────────────────────────────────
# Prayer block content (HTML fragments per block)
# ─────────────────────────────────────────────────────────────────────────────

_MORNING_OFFERING = (
    "O Jesus, through the Immaculate Heart of Mary, I offer You my prayers, "
    "works, joys, and sufferings of this day, in union with the Holy Sacrifice "
    "of the Mass throughout the world. I offer them for all the intentions of "
    "Your Sacred Heart: the salvation of souls, reparation for sin, and the "
    "reunion of all Christians. I offer them for the intentions of our Bishops "
    "and of all Apostles of Prayer, and in particular for those recommended by "
    "our Holy Father this month. Amen."
)

_DIVINE_MERCY = (
    "Eternal Father, I offer You the Body and Blood, Soul and Divinity of Your "
    "dearly beloved Son, Our Lord Jesus Christ, in atonement for our sins and "
    "those of the whole world. For the sake of His sorrowful Passion, have "
    "mercy on us and on the whole world. Holy God, Holy Mighty One, Holy "
    "Immortal One, have mercy on us and on the whole world."
)

_ANGELUS = (
    "V. The Angel of the Lord declared unto Mary,\n"
    "R. And she conceived of the Holy Spirit.\n\n"
    "Hail Mary, full of grace, the Lord is with thee...\n\n"
    "V. Behold the handmaid of the Lord,\n"
    "R. Be it done unto me according to thy word.\n\n"
    "Hail Mary...\n\n"
    "V. And the Word was made Flesh,\n"
    "R. And dwelt among us.\n\n"
    "Hail Mary..."
)

_SALVE_REGINA = (
    "Hail, holy Queen, Mother of Mercy, our life, our sweetness, and our hope. "
    "To thee do we cry, poor banished children of Eve. To thee do we send up "
    "our sighs, mourning and weeping in this valley of tears. Turn then, most "
    "gracious Advocate, thine eyes of mercy toward us, and after this our "
    "exile show unto us the blessed fruit of thy womb, Jesus. O clement, O "
    "loving, O sweet Virgin Mary."
)


def _accent() -> str:
    return "#4a6fa5"


def _card(title: str, body_html: str, *, scriptural: str = "") -> str:
    sub = ""
    if scriptural:
        sub = (f'<div style="font-style:italic;color:#5a6a85;font-size:0.86em;'
               f'margin:0 0 10px;line-height:1.5;">&ldquo;{escape(scriptural)}&rdquo;</div>')
    return (
        f'<section style="background:white;border:1px solid #d4dcea;border-radius:14px;'
        f'padding:18px 20px;margin:0 0 14px;box-shadow:0 1px 2px rgba(0,0,0,0.03);">'
        f'<h2 style="font-family:Georgia,serif;font-weight:400;font-size:1.15em;'
        f'color:{_accent()};margin:0 0 8px;">{escape(title)}</h2>'
        f'{sub}{body_html}</section>'
    )


def _prose(text: str) -> str:
    safe = escape(text).replace("\n", "<br>")
    return (f'<div style="font-family:Georgia,serif;font-size:0.96em;line-height:1.7;'
            f'color:#1a1a1a;white-space:pre-line;">{safe}</div>')


def _render_block_prayers(block: str, now_dt: datetime, weekday: str) -> str:
    out = []
    if block == "early_morning":
        out.append(_card("Morning Offering",
                         _prose(_MORNING_OFFERING),
                         scriptural="In the morning, O Lord, You hear my voice. — Ps 5:3"))
        out.append(_card("Lauds — at a glance",
                         _prose("Open the day with the Church: Ps 63 (longing), the Benedictus, "
                                "and intercession for the Church and the world.")))
    elif block == "morning":
        # Countdown to Angelus at noon
        secs_to_noon = max(0, (12 * 3600) - (now_dt.hour * 3600 + now_dt.minute * 60))
        mins = secs_to_noon // 60
        when = f"in {mins // 60}h {mins % 60}m" if mins else "now"
        out.append(_card("The Angelus — at noon",
                         _prose(f"Bell rings {when}.\n\n{_ANGELUS}"),
                         scriptural="And the Word became flesh and dwelt among us. — Jn 1:14"))
        out.append(_card("A breath at mid-morning",
                         _prose("Pause. One slow breath. 'Jesus, I trust in You.'"),
                         scriptural="Be still, and know that I am God. — Ps 46:10"))
    elif block == "afternoon":
        is_three = (now_dt.hour == 15)
        title = "Divine Mercy — the Hour of Mercy" if is_three else "Divine Mercy Chaplet"
        scrip = ("At three o'clock, implore My mercy. — Diary of St. Faustina"
                 if is_three else "")
        out.append(_card(title, _prose(_DIVINE_MERCY), scriptural=scrip))
        out.append(_card("Midday Prayer (Sext)",
                         _prose("'O God, come to my assistance. O Lord, make haste to help me.' "
                                "A Psalm, a quiet word, a return to the day's work in His company.")))
    elif block == "evening":
        out.append(_card("The Angelus — at six",
                         _prose(_ANGELUS),
                         scriptural="And the Word became flesh. — Jn 1:14"))
        ros = _rosary_for(weekday)
        rows = "".join(
            f'<li style="margin:6px 0;"><strong>{escape(t)}</strong>'
            f' &mdash; <em>fruit:</em> {escape(f)}</li>'
            for t, f in ros["list"]
        )
        out.append(_card(
            f"The Holy Rosary — {ros['name']} Mysteries",
            f'<ol style="font-family:Georgia,serif;font-size:0.96em;line-height:1.7;'
            f'padding-left:20px;color:#1a1a1a;">{rows}</ol>',
            scriptural="Pray the Rosary every day. — Our Lady of Fatima",
        ))
        out.append(_card("Vespers — at a glance",
                         _prose("The Church lifts up the Magnificat with Mary at evening: "
                                "'My soul magnifies the Lord.'")))
    else:  # late_evening
        out.append(_card("Examen — five minutes",
                         _prose("1. Give thanks for the gifts of today.\n"
                                "2. Ask for light to see honestly.\n"
                                "3. Walk through the day, hour by hour.\n"
                                "4. Ask forgiveness; rest in His mercy.\n"
                                "5. Offer tomorrow into His hands."),
                         scriptural="Search me, O God, and know my heart. — Ps 139:23"))
        out.append(_card("Compline — Night Prayer",
                         _prose("'Into Your hands, O Lord, I commend my spirit.'\n\n"
                                "Pray Psalm 91 or Psalm 4. End with the Salve Regina.")))
        out.append(_card("Salve Regina",
                         _prose(_SALVE_REGINA)))
    return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# Intentions widget
# ─────────────────────────────────────────────────────────────────────────────

def _render_intentions_widget(iso: str) -> str:
    items_html = ""
    try:
        from data_helpers import get_active_intentions_for_date
        active = get_active_intentions_for_date(iso)
        rows = []
        for d_int in active.get("daily", []):
            t = (d_int.get("text") or "").strip()
            if t:
                rows.append(f'<li style="margin:4px 0;">&middot; {escape(t)}'
                            f' <span style="color:#999;font-size:0.8em;">(today)</span></li>')
        for r_int in active.get("repeating", []):
            t = (r_int.get("text") or "").strip()
            if t:
                rows.append(f'<li style="margin:4px 0;">&middot; {escape(t)}'
                            f' <span style="color:#999;font-size:0.8em;">(ongoing)</span></li>')
        for n_int in active.get("novenas", []):
            saint = (n_int.get("saint") or "").strip()
            day_n = n_int.get("current_day", 0)
            if saint:
                rows.append(f'<li style="margin:4px 0;">&middot; Novena to {escape(saint)}'
                            f' <span style="color:#999;font-size:0.8em;">'
                            f'(day {day_n} of 9)</span></li>')
        if rows:
            items_html = (f'<ul style="list-style:none;padding:0;margin:0 0 12px;'
                          f'font-size:0.92em;line-height:1.5;color:#2d4a78;">'
                          f'{"".join(rows)}</ul>')
        else:
            items_html = ('<div style="color:#888;font-style:italic;font-size:0.88em;'
                          'margin:0 0 12px;">No intentions recorded for today.</div>')
    except Exception as e:
        items_html = f'<div style="color:#888;font-size:0.85em;">(Could not load: {escape(str(e))})</div>'

    form = (
        '<form method="POST" action="/timeblock-add-intention" '
        'style="display:flex;gap:8px;margin:10px 0 8px;">'
        '<input type="text" name="text" placeholder="Add an intention for today..." '
        'required maxlength="280" '
        'style="flex:1;border:1px solid #c8d4e8;border-radius:18px;padding:8px 14px;'
        'font-size:0.92em;font-family:inherit;">'
        f'<button type="submit" style="background:{_accent()};color:white;border:none;'
        'border-radius:18px;padding:8px 16px;font-size:0.9em;cursor:pointer;'
        'font-family:inherit;">Add</button>'
        '</form>'
        '<div style="text-align:right;">'
        '<a href="/sister-mary" style="color:#2d4a78;font-size:0.85em;'
        'text-decoration:none;font-style:italic;">'
        'Talk to Sister Mary &rarr;</a>'
        '</div>'
    )
    return _card("Today's Prayer Intentions", items_html + form)


# ─────────────────────────────────────────────────────────────────────────────
# Novena prompt
# ─────────────────────────────────────────────────────────────────────────────

def _render_novena_prompt() -> str:
    try:
        from data_helpers import check_upcoming_novenas
        upcoming = check_upcoming_novenas()
    except Exception:
        upcoming = []
    if not upcoming:
        return ""
    blocks = []
    for u in upcoming[:2]:
        saint = u.get("saint", "")
        feast = u.get("feast_date", "")
        days  = u.get("days_away", 0)
        if not saint or not feast:
            continue
        blocks.append(
            f'<div style="margin:6px 0 12px;font-size:0.92em;line-height:1.5;color:#2d4a78;">'
            f'<strong>{escape(saint)}</strong> &mdash; in {days} days '
            f'<span style="color:#999;">({escape(feast)})</span>'
            f'</div>'
            f'<form method="POST" action="/timeblock-add-novena" style="display:inline;">'
            f'<input type="hidden" name="saint" value="{escape(saint)}">'
            f'<input type="hidden" name="feast_date" value="{escape(feast)}">'
            f'<button type="submit" style="background:{_accent()};color:white;border:none;'
            f'border-radius:18px;padding:7px 16px;font-size:0.88em;cursor:pointer;'
            f'font-family:inherit;margin:0 8px 12px 0;">'
            f'Begin novena</button></form>'
        )
    if not blocks:
        return ""
    return _card("A novena is approaching",
                 "".join(blocks),
                 scriptural="Pray without ceasing. — 1 Thes 5:17")


# ─────────────────────────────────────────────────────────────────────────────
# Practical content (FROL + meals)
# ─────────────────────────────────────────────────────────────────────────────

_BLOCK_HOUR_RANGE = {
    "early_morning": (5, 7),
    "morning":       (7, 12),
    "afternoon":     (12, 17),
    "evening":       (17, 20),
    "late_evening":  (20, 24),
}


def _render_frol_snapshot(weekday: str, block: str) -> str:
    try:
        from data_helpers import get_frol_day_slots
        slots = get_frol_day_slots(weekday, person="Mom") or {}
    except Exception:
        slots = {}
    if not slots:
        return ""
    lo, hi = _BLOCK_HOUR_RANGE.get(block, (0, 24))

    def _hour_of(t: str) -> int:
        try:
            return int(t.split(":")[0])
        except Exception:
            return -1

    rows = []
    for t in sorted(slots.keys()):
        h = _hour_of(t)
        if lo <= h < hi:
            label = (slots[t] or "").strip()
            if label:
                rows.append(f'<div style="display:flex;gap:12px;padding:5px 0;'
                            f'border-bottom:1px dashed #e4eaf3;">'
                            f'<div style="color:{_accent()};font-weight:600;'
                            f'font-size:0.85em;width:60px;">{escape(t)}</div>'
                            f'<div style="font-size:0.92em;color:#1a1a1a;">'
                            f'{escape(label)}</div></div>')
    if not rows:
        return ""
    return _card(f"Rule of Life — {_BLOCK_LABELS.get(block, block)}",
                 "".join(rows))


def _meal_keys_for_block(block: str) -> list:
    if block in ("early_morning", "morning"):
        return [("breakfast", "Breakfast"), ("lunch", "Lunch (prep)")]
    if block == "afternoon":
        return [("lunch", "Lunch"), ("dinner", "Dinner (prep)")]
    if block == "evening":
        return [("dinner", "Dinner")]
    return [("breakfast", "Tomorrow's breakfast (prep)")]


def _week_key_for(d: date) -> str:
    monday = d - timedelta(days=d.weekday())
    iso = monday.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _render_meals_snapshot(weekday: str, today: date, block: str) -> str:
    try:
        from render_meals import load_meal_plan
        wk = _week_key_for(today)
        plan = load_meal_plan(wk) or {}
        if block == "late_evening":
            tomorrow = today + timedelta(days=1)
            day_meals = (plan.get("days", {}) or {}).get(tomorrow.strftime("%A"), {}) or {}
        else:
            day_meals = (plan.get("days", {}) or {}).get(weekday, {}) or {}
    except Exception:
        day_meals = {}
    rows = []
    for key, label in _meal_keys_for_block(block):
        val = (day_meals.get(key) or "").strip()
        if val:
            rows.append(f'<div style="padding:6px 0;border-bottom:1px dashed #e4eaf3;">'
                        f'<div style="font-size:0.78em;text-transform:uppercase;'
                        f'letter-spacing:0.06em;color:{_accent()};font-weight:700;">'
                        f'{escape(label)}</div>'
                        f'<div style="font-size:0.92em;color:#1a1a1a;margin-top:2px;">'
                        f'{escape(val)}</div></div>')
        else:
            rows.append(f'<div style="padding:6px 0;border-bottom:1px dashed #e4eaf3;'
                        f'color:#999;font-size:0.88em;font-style:italic;">'
                        f'{escape(label)}: &mdash;</div>')
    return _card(f"Meals — {_BLOCK_LABELS.get(block, block)}",
                 "".join(rows) +
                 '<div style="text-align:right;margin-top:8px;">'
                 '<a href="/lorenzo" style="color:#2d4a78;font-size:0.85em;'
                 'text-decoration:none;">Talk to Lorenzo &rarr;</a></div>')


# ─────────────────────────────────────────────────────────────────────────────
# Saint card + Pope intention card
# ─────────────────────────────────────────────────────────────────────────────

def _render_saint_card(iso: str) -> str:
    try:
        from render_liturgical import get_day_info
        info = get_day_info(datetime.fromisoformat(iso).date())
    except Exception:
        return ""
    feast = (info.get("feast_name") or "").strip()
    season = (info.get("season") or "").strip()
    obs = info.get("observances", []) or []
    if not feast and not season and not obs:
        return ""
    bits = []
    if feast:
        bits.append(f'<div style="font-family:Georgia,serif;font-size:1.05em;'
                    f'color:#1a1a1a;margin:0 0 6px;">{escape(feast)}</div>')
    if season:
        bits.append(f'<div style="font-size:0.86em;color:#5a6a85;">'
                    f'Liturgical season: {escape(season)}</div>')
    for o in obs:
        bits.append(f'<div style="font-size:0.86em;color:#7a3e1a;margin-top:4px;">'
                    f'&middot; {escape(o)}</div>')
    return _card("Today in the Church", "".join(bits))


def _render_pope_card(iso: str) -> str:
    try:
        from data_helpers import get_pope_intention_for_month
        text = get_pope_intention_for_month(iso)
    except Exception:
        text = ""
    if not text:
        return ""
    return _card("The Holy Father's Intention this month",
                 _prose(text))


def _render_daily_mass_link() -> str:
    return (
        '<div style="text-align:center;margin:6px 0 14px;">'
        f'<a href="/daily-mass" target="_blank" rel="noopener" '
        f'style="display:inline-block;background:{_accent()};color:white;'
        f'text-decoration:none;padding:10px 22px;border-radius:22px;'
        f'font-size:0.92em;font-family:inherit;">'
        '&#10016; Today\'s Daily Mass Readings &rarr;</a>'
        '</div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Page assembly
# ─────────────────────────────────────────────────────────────────────────────

def render_timeblock_homepage(viewer: str = "lauren") -> str:
    now_dt     = _now_eastern()
    today      = now_dt.date()
    iso        = today.isoformat()
    weekday    = now_dt.strftime("%A")
    date_label = now_dt.strftime("%A, %B %d, %Y")
    time_label = now_dt.strftime("%-I:%M %p")
    block      = _resolve_block(now_dt)
    block_lbl  = _BLOCK_LABELS.get(block, block)
    greeting   = _BLOCK_GREETINGS.get(block, "Peace be with you.")

    img = _resolve_image(iso)
    # Hero background is always the gradient (acts as fallback when img onerror fires).
    bg_value = img.get("fallback_gradient", _SEASON_GRADIENT["spring"])
    _img_url = img.get("url", "")
    hero_img_html = ""
    if _img_url:
        _src_attr = escape(_img_url, quote=True)
        # onerror hides the img so the gradient shows through
        hero_img_html = (
            '<img class="tb-hero-img" src="' + _src_attr + '" alt="" '
            'onerror="this.style.display=&#39;none&#39;">'
        )

    saint_card     = _render_saint_card(iso)
    prayers_html   = _render_block_prayers(block, now_dt, weekday)
    pope_card      = _render_pope_card(iso) if block == "afternoon" else ""
    intentions     = _render_intentions_widget(iso)
    novena_prompt  = _render_novena_prompt()
    frol_card      = _render_frol_snapshot(weekday, block)
    meals_card     = _render_meals_snapshot(weekday, today, block)
    daily_mass     = _render_daily_mass_link()

    # Switch link to the dashboard for Lauren who wants it
    switch_link = (
        '<div style="text-align:center;padding:12px 0 28px;">'
        '<a href="/today" style="color:rgba(255,255,255,0.7);font-size:0.82em;'
        'text-decoration:none;">View today\'s tasks &rarr;</a>'
        '</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>{escape(block_lbl)} &middot; McAdams Family</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#f4f7fc;color:#1a1a1a;min-height:100vh;}}
.tb-hero{{
    position:relative;
    min-height:62vh;
    background:{bg_value};
    background-size:cover; background-position:center;
    display:flex;flex-direction:column;justify-content:flex-end;
    padding:28px 22px 24px;color:white;
    text-shadow:0 1px 6px rgba(0,0,0,0.5);
    overflow:hidden;
}}
.tb-hero-img{{
    position:absolute;top:0;left:0;width:100%;height:100%;
    object-fit:cover;object-position:center;z-index:0;
    background:transparent;
}}
.tb-hero-shade{{
    position:absolute;top:0;left:0;width:100%;height:100%;
    background:linear-gradient(180deg, rgba(20,30,55,0.15) 0%, rgba(20,30,55,0.55) 100%);
    z-index:1;pointer-events:none;
}}
.tb-hero > .greet, .tb-hero > .when, .tb-hero > div:last-child{{position:relative;z-index:2;}}
.tb-hero .greet{{font-family:Georgia,serif;font-size:1.85em;font-weight:400;letter-spacing:0.01em;}}
.tb-hero .when{{font-size:0.92em;opacity:0.92;margin-top:6px;}}
.tb-hero .blocklbl{{display:inline-block;background:rgba(255,255,255,0.2);
    color:white;padding:4px 12px;border-radius:14px;font-size:0.78em;
    margin-top:10px;letter-spacing:0.04em;text-transform:uppercase;
    backdrop-filter:blur(4px);}}
.tb-hero .credit{{position:absolute;bottom:6px;right:10px;font-size:0.7em;
    opacity:0.55;color:white;}}
.tb-hero-wrap{{position:relative;}}
.tb-body{{max-width:760px;margin:0 auto;padding:18px 16px 40px;}}
.tb-nav{{position:fixed;top:14px;right:14px;z-index:10;}}
.tb-nav a{{display:inline-block;background:rgba(255,255,255,0.86);
    color:#2d4a78;padding:7px 14px;border-radius:18px;font-size:0.84em;
    text-decoration:none;backdrop-filter:blur(6px);font-weight:600;
    border:1px solid rgba(255,255,255,0.6);}}
@media (min-width:740px){{
    .tb-hero{{min-height:54vh;padding:36px 32px 30px;}}
    .tb-hero .greet{{font-size:2.4em;}}
}}
</style>
</head>
<body>
<div class="tb-nav"><a href="/today">Tasks &rarr;</a></div>
<div class="tb-hero-wrap">
  <div class="tb-hero">
    {hero_img_html}
    <div class="tb-hero-shade"></div>
    <div class="greet">{escape(greeting)}</div>
    <div class="when">{escape(date_label)} &middot; {escape(time_label)} ET</div>
    <div><span class="blocklbl">{escape(block_lbl)}</span></div>
  </div>
  <div class="credit">{escape(img.get("credit",""))}</div>
</div>
<div class="tb-body">
  {saint_card}
  {prayers_html}
  {daily_mass}
  {pope_card}
  {intentions}
  {novena_prompt}
  {frol_card}
  {meals_card}
</div>
{switch_link}
</body>
</html>"""
