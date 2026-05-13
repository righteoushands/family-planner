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

# Curated Unsplash CDN URLs — direct image URLs to specific public photos.
# Format: https://images.unsplash.com/photo-{id}?w=1600&q=80
# Rotated by day-of-year to keep variety; no API key required for direct CDN.
_UNSPLASH_PHOTOS = {
    "spring": [
        "https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=1600&q=80",
        "https://images.unsplash.com/photo-1462275646964-a0e3386b89fa?w=1600&q=80",
        "https://images.unsplash.com/photo-1487070183336-b863922373d4?w=1600&q=80",
        "https://images.unsplash.com/photo-1494500764479-0c8f2919a3d8?w=1600&q=80",
    ],
    "summer": [
        "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=1600&q=80",
        "https://images.unsplash.com/photo-1501785888041-af3ef285b470?w=1600&q=80",
        "https://images.unsplash.com/photo-1518495973542-4542c06a5843?w=1600&q=80",
        "https://images.unsplash.com/photo-1473773508845-188df298d2d1?w=1600&q=80",
    ],
    "autumn": [
        "https://images.unsplash.com/photo-1507783548227-544c3b8fc065?w=1600&q=80",
        "https://images.unsplash.com/photo-1476820865390-c52aeebb9891?w=1600&q=80",
        "https://images.unsplash.com/photo-1508193638397-1c4234db14d8?w=1600&q=80",
        "https://images.unsplash.com/photo-1444930694458-01babe71870e?w=1600&q=80",
    ],
    "winter": [
        "https://images.unsplash.com/photo-1483921020237-2ff51e8e4b22?w=1600&q=80",
        "https://images.unsplash.com/photo-1418985991508-e47386d96a71?w=1600&q=80",
        "https://images.unsplash.com/photo-1457269449834-928af64c684d?w=1600&q=80",
        "https://images.unsplash.com/photo-1486825586573-7131f7991bdd?w=1600&q=80",
    ],
}

def _unsplash_url(season: str, day_of_year: int = 0) -> str:
    photos = _UNSPLASH_PHOTOS.get(season) or _UNSPLASH_PHOTOS["spring"]
    return photos[day_of_year % len(photos)]

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


_PEXELS_CACHE = {}

_PEXELS_SEASON_QUERIES = {
    "spring": "spring flowers nature peaceful",
    "summer": "summer golden light nature",
    "autumn": "autumn leaves forest warm",
    "winter": "winter snow peaceful forest",
}


def _pexels_search(query: str, cache_key, day_of_year: int) -> dict:
    """Hit Pexels /v1/search and return {url, photographer, photographer_url}
    or {} on failure. Results are cached per process by cache_key."""
    if cache_key in _PEXELS_CACHE:
        photos = _PEXELS_CACHE[cache_key]
    else:
        api_key = (os.environ.get("PEXELS_API_KEY") or "").strip()
        if not api_key:
            return {}
        import json as _json
        import urllib.request as _req
        import urllib.parse as _parse
        try:
            qs = _parse.urlencode({
                "query":       query,
                "per_page":    15,
                "orientation": "landscape",
            })
            req = _req.Request(
                "https://api.pexels.com/v1/search?" + qs,
                headers={"Authorization": api_key},
            )
            with _req.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
            photos = data.get("photos", []) or []
        except Exception:
            photos = []
        _PEXELS_CACHE[cache_key] = photos
    if not photos:
        return {}
    photo = photos[day_of_year % len(photos)]
    src = (photo.get("src") or {})
    url = src.get("landscape") or src.get("large") or src.get("original") or ""
    if not url:
        return {}
    return {
        "url":              url,
        "photographer":     (photo.get("photographer") or "").strip(),
        "photographer_url": (photo.get("photographer_url") or "").strip(),
    }


def _resolve_image(iso: str) -> dict:
    """Returns {url, photographer, photographer_url, fallback_gradient}.
    Pulls a daily-rotating photo from Pexels by season, Marian feast, or
    major feast; falls back to a CSS gradient on failure."""
    try:
        d = datetime.fromisoformat(iso).date()
    except Exception:
        d = _now_eastern().date()
    season = _SEASON_FOR_MONTH.get(d.month, "spring")
    gradient = _SEASON_GRADIENT.get(season, _SEASON_GRADIENT["spring"])
    day_of_year = d.timetuple().tm_yday

    feast_name = ""
    try:
        from render_liturgical import get_day_info
        info = get_day_info(d)
        feast_name = (info.get("feast_name") or "").strip()
    except Exception:
        feast_name = ""

    result = {}
    if feast_name:
        if _is_marian(feast_name):
            result = _pexels_search(
                "Our Lady Madonna painting Catholic",
                ("marian", day_of_year),
                day_of_year,
            )
        if not result:
            result = _pexels_search(
                f"{feast_name} painting Catholic art",
                (f"feast::{feast_name}", day_of_year),
                day_of_year,
            )
    if not result:
        query = _PEXELS_SEASON_QUERIES.get(season, _PEXELS_SEASON_QUERIES["spring"])
        result = _pexels_search(query, (season, day_of_year), day_of_year)

    if not result:
        return {
            "url":              "",
            "photographer":     "",
            "photographer_url": "",
            "fallback_gradient": gradient,
        }
    result["fallback_gradient"] = gradient
    return result


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

_ALMA_REDEMPTORIS = (
    "Loving Mother of the Redeemer, gate of heaven, star of the sea, "
    "hasten to aid thy fallen people who strive to rise once more. Thou "
    "who didst beget thy holy Creator, while all nature marvelled, Virgin "
    "before and after receiving the Angel's salutation, take pity on us "
    "sinners."
)

_AVE_REGINA_CAELORUM = (
    "Hail, O Queen of Heaven enthroned. Hail, by angels Mistress owned. "
    "Root of Jesse, Gate of morn, whence the world's true Light was born: "
    "Glorious Virgin, joy to thee, loveliest whom in heaven they see; "
    "fairest thou where all are fair, plead with Christ our sins to spare."
)

_REGINA_CAELI = (
    "Queen of Heaven, rejoice, alleluia.\n"
    "For He whom thou didst merit to bear, alleluia,\n"
    "Hath risen as He said, alleluia.\n"
    "Pray for us to God, alleluia.\n\n"
    "V. Rejoice and be glad, O Virgin Mary, alleluia.\n"
    "R. For the Lord hath risen indeed, alleluia."
)

_COMPLINE_EXAMEN = (
    "Pause in silence. Place yourself in God's presence.\n\n"
    "1. Give thanks for the gifts of this day — name three.\n"
    "2. Ask the Holy Spirit for light to see honestly.\n"
    "3. Walk slowly through the day, hour by hour. Where did love grow? "
    "Where did it shrink?\n"
    "4. Ask forgiveness for what was unloving. Rest in His mercy.\n"
    "5. Offer tomorrow into His hands."
)

_COMPLINE_CONFITEOR = (
    "I confess to almighty God, and to you, my brothers and sisters, "
    "that I have greatly sinned, in my thoughts and in my words, in what "
    "I have done and in what I have failed to do, through my fault, "
    "through my fault, through my most grievous fault; therefore I ask "
    "blessed Mary ever-Virgin, all the Angels and Saints, and you, my "
    "brothers and sisters, to pray for me to the Lord our God."
)

_TE_LUCIS_ANTE_TERMINUM = (
    "To Thee before the close of day, Creator of the world, we pray\n"
    "That, with Thy wonted favor, Thou wouldst be our guard and keeper now.\n\n"
    "From all ill dreams defend our eyes, from nightly fears and fantasies;\n"
    "Tread under foot our ghostly foe, that no pollution we may know.\n\n"
    "O Father, that we ask be done, through Jesus Christ, Thine only Son,\n"
    "Who, with the Holy Ghost and Thee, doth live and reign eternally. Amen."
)

_PSALM_91 = (
    "He who dwells in the shelter of the Most High, who abides in the "
    "shadow of the Almighty, will say to the Lord, 'My refuge and my "
    "fortress, my God, in whom I trust.'\n\n"
    "For He will deliver you from the snare of the fowler and from the "
    "deadly pestilence; He will cover you with His pinions, and under "
    "His wings you will find refuge; His faithfulness is a shield and "
    "buckler.\n\n"
    "You will not fear the terror of the night, nor the arrow that flies "
    "by day, nor the pestilence that stalks in darkness, nor the "
    "destruction that wastes at noonday.\n\n"
    "Because you have made the Lord your refuge, the Most High your "
    "habitation, no evil shall befall you, no scourge come near your "
    "tent. For He will give His angels charge of you to guard you in "
    "all your ways.\n\n"
    "When he calls to me, I will answer him; I will be with him in "
    "trouble, I will rescue him and honor him. With long life I will "
    "satisfy him, and show him my salvation."
)

_COMPLINE_SHORT_READING = (
    "You, O Lord, are in our midst, and we are called by Your name; "
    "do not forsake us, O Lord our God. — Jeremiah 14:9"
)

_NUNC_DIMITTIS = (
    "Lord, now lettest Thou Thy servant depart in peace, according to "
    "Thy word; for mine eyes have seen Thy salvation, which Thou hast "
    "prepared before the face of all peoples: a light to lighten the "
    "Gentiles, and the glory of Thy people Israel.\n\n"
    "Glory be to the Father, and to the Son, and to the Holy Spirit, "
    "as it was in the beginning, is now, and ever shall be, world "
    "without end. Amen."
)

_COMPLINE_CLOSING = (
    "May the all-powerful Lord grant us a restful night and a peaceful "
    "death. Amen."
)

_COMPLINE_RESPONSORY = (
    "V. Into your hands, Lord, I commend my spirit.\n"
    "R. Into your hands, Lord, I commend my spirit.\n"
    "V. You have redeemed us, Lord God of truth.\n"
    "R. I commend my spirit.\n"
    "V. Glory to the Father, and to the Son, and to the Holy Spirit.\n"
    "R. Into your hands, Lord, I commend my spirit."
)

# ── Liturgy of the Hours — shared elements ──────────────────────────────────

_LOH_OPENING = (
    "V. O God, come to my assistance.\n"
    "R. O Lord, make haste to help me.\n\n"
    "Glory to the Father, and to the Son, and to the Holy Spirit,\n"
    "as it was in the beginning, is now, and will be for ever. Amen."
)

_GLORY_BE = (
    "Glory to the Father, and to the Son, and to the Holy Spirit,\n"
    "as it was in the beginning, is now, and will be for ever. Amen."
)

_OUR_FATHER = (
    "Our Father, who art in heaven, hallowed be Thy name; Thy kingdom come; "
    "Thy will be done on earth as it is in heaven. Give us this day our "
    "daily bread; and forgive us our trespasses, as we forgive those who "
    "trespass against us; and lead us not into temptation, but deliver us "
    "from evil. Amen."
)

# ── Lauds (Morning Prayer) ──────────────────────────────────────────────────

_LAUDS_HYMN = (
    "Now that the daylight fills the sky, we lift our hearts to God on high,\n"
    "That He, in all we do or say, would keep us free from harm this day.\n\n"
    "May He restrain our tongues from strife, and shield from anger's din our life,\n"
    "And guard with watchful care our eyes from earth's absorbing vanities."
)

_LAUDS_ANTIPHON = (
    "Antiphon: O God, you are my God, for you I long; for you my soul is "
    "thirsting."
)

_LAUDS_PSALM_63 = (
    "O God, you are my God, for you I long; for you my soul is thirsting.\n"
    "My body pines for you like a dry, weary land without water.\n\n"
    "So I gaze on you in the sanctuary to see your strength and your glory.\n"
    "For your love is better than life, my lips will speak your praise.\n\n"
    "So I will bless you all my life, in your name I will lift up my hands.\n"
    "My soul shall be filled as with a banquet, my mouth shall praise you with joy.\n\n"
    "On my bed I remember you. On you I muse through the night\n"
    "for you have been my help; in the shadow of your wings I rejoice.\n\n"
    "My soul clings to you; your right hand holds me fast.\n\n"
    "(Glory to the Father…)"
)

_LAUDS_READING = (
    "Awake, O sleeper, and arise from the dead, and Christ shall give you "
    "light. — Ephesians 5:14"
)

_LAUDS_RESPONSORY = (
    "V. Blessed be the Lord our God, blessed from age to age.\n"
    "R. Blessed be the Lord our God, blessed from age to age."
)

_BENEDICTUS_ANTIPHON = (
    "Antiphon: Blessed be the Lord our God, who has come to His people and "
    "set them free."
)

_BENEDICTUS = (
    "Blessed be the Lord, the God of Israel; he has come to his people and "
    "set them free.\n\n"
    "He has raised up for us a mighty Saviour, born of the house of his "
    "servant David.\n\n"
    "Through his holy prophets he promised of old that he would save us "
    "from our enemies, from the hands of all who hate us.\n\n"
    "He promised to show mercy to our fathers and to remember his holy "
    "covenant.\n\n"
    "This was the oath he swore to our father Abraham: to set us free from "
    "the hands of our enemies, free to worship him without fear, holy and "
    "righteous in his sight all the days of our life.\n\n"
    "You, my child, shall be called the prophet of the Most High; for you "
    "will go before the Lord to prepare his way, to give his people "
    "knowledge of salvation by the forgiveness of their sins.\n\n"
    "In the tender compassion of our God the dawn from on high shall break "
    "upon us, to shine on those who dwell in darkness and the shadow of "
    "death, and to guide our feet into the way of peace.\n\n"
    "(Glory to the Father…)"
)

_LAUDS_INTERCESSIONS = (
    "Let us give thanks to Christ, who enlightens and sanctifies us, and "
    "say: Lord, have mercy.\n\n"
    "— For the Church, that she may be a faithful witness to your love today.\n"
    "— For the Holy Father and all bishops, that they may be strengthened "
    "in their service.\n"
    "— For our family, that the work of this day may be offered to you.\n"
    "— For those who suffer and those who are alone, that they may know "
    "your nearness.\n"
    "— For the dying and the dead, that they may rest in your peace."
)

_LAUDS_CLOSING_PRAYER = (
    "Lord, our God, almighty Father, the light of dawn breaks over the "
    "earth at your command. Keep us today free from sin and lead us along "
    "the path of holiness, that all we think and say and do may be pleasing "
    "in your sight. We ask this through Christ our Lord. Amen."
)

_LAUDS_BLESSING = (
    "May the Lord bless us, protect us from all evil, and bring us to "
    "everlasting life. Amen."
)

# ── Terce (Mid-Morning Prayer) ──────────────────────────────────────────────

_TERCE_HYMN = (
    "Come, Holy Spirit, ever One with God the Father and the Son;\n"
    "Come, fill our hearts with grace divine, that all our words and works "
    "be Thine."
)

_TERCE_PSALM = (
    "Antiphon: Blessed are those who walk in the law of the Lord.\n\n"
    "Teach me, O Lord, the way of your statutes, and I will keep it to the end.\n"
    "Give me understanding, that I may keep your law and observe it with "
    "my whole heart.\n"
    "Lead me in the path of your commandments, for I delight in it.\n"
    "Incline my heart to your testimonies, and not to gain!\n"
    "Turn my eyes from looking at vanities; give me life in your ways. — Ps 119\n\n"
    "(Glory to the Father…)"
)

_TERCE_READING = (
    "Whatever you do, in word or deed, do everything in the name of the "
    "Lord Jesus, giving thanks to God the Father through him. — Colossians 3:17"
)

_TERCE_RESPONSORY = (
    "V. Blessed are you, O Lord, in the firmament of heaven.\n"
    "R. Blessed are you, O Lord, in the firmament of heaven."
)

_TERCE_PRAYER = (
    "Lord God, Father of all light, at this hour you sent the Holy Spirit "
    "upon the apostles. Pour out the same Spirit upon us, that we may bear "
    "faithful witness to you before the world. Through Christ our Lord. Amen."
)

# ── Sext (Midday Prayer) ────────────────────────────────────────────────────

_SEXT_HYMN = (
    "O God of truth, O Lord of might, who orderest time and change aright,\n"
    "Who sendest the early morning ray, and lightest the glow of noonday."
)

_SEXT_PSALM = (
    "Antiphon: To you have I lifted up my eyes, you who dwell in the heavens.\n\n"
    "To you have I lifted up my eyes, you who dwell in the heavens;\n"
    "my eyes, like the eyes of slaves on the hand of their lords.\n\n"
    "Like the eyes of a servant on the hand of her mistress,\n"
    "so our eyes are on the Lord our God till he show us his mercy.\n\n"
    "Have mercy on us, Lord, have mercy. We are filled with contempt.\n"
    "Indeed, all too full is our soul with the scorn of the rich,\n"
    "with the proud man's disdain. — Ps 123\n\n"
    "(Glory to the Father…)"
)

_SEXT_READING = (
    "Beloved, do not be conformed to this world but be transformed by the "
    "renewal of your mind. — Romans 12:2"
)

_SEXT_RESPONSORY = (
    "V. The Lord will guard you from all evil.\n"
    "R. He will guard your soul."
)

_SEXT_PRAYER = (
    "Almighty and merciful God, you have given us a moment's rest from our "
    "labour at this midday hour. Look kindly on the work we have begun, "
    "make good its defects, and bring it to that completion which will give "
    "you glory. Through Christ our Lord. Amen."
)

# ── None (Mid-Afternoon Prayer) ─────────────────────────────────────────────

_NONE_HYMN = (
    "O God, creation's secret force, Yourself unmoved, all motion's source,\n"
    "Who from the morn till evening's ray, through every change dost guide "
    "the day."
)

_NONE_PSALM = (
    "Antiphon: Those who put their trust in the Lord are like Mount Zion, "
    "that cannot be shaken.\n\n"
    "Those who put their trust in the Lord are like Mount Zion,\n"
    "that cannot be shaken, that stands for ever.\n\n"
    "Jerusalem! The mountains surround her, so the Lord surrounds his people\n"
    "both now and for ever. — Ps 125\n\n"
    "(Glory to the Father…)"
)

_NONE_READING = (
    "If anyone is in Christ, he is a new creation; the old has passed away, "
    "behold, the new has come. — 2 Corinthians 5:17"
)

_NONE_RESPONSORY = (
    "V. The Lord redeems the souls of his servants.\n"
    "R. None who trust in him are condemned."
)

_NONE_PRAYER = (
    "Lord God, Father everlasting, at this hour your Son, suffering for the "
    "salvation of the world, surrendered his spirit into your hands. Help us "
    "in our weakness to die to sin and live for you alone. Through Christ "
    "our Lord. Amen."
)

# ── Vespers (Evening Prayer) ────────────────────────────────────────────────

_VESPERS_HYMN = (
    "O radiant Light, O Sun divine of God the Father's deathless face,\n"
    "O image of the light sublime that fills the heavenly dwelling place.\n\n"
    "O Son of God, the source of life, praise is your due by night and day;\n"
    "Our happy lips must raise the strain of your esteemed and splendid name."
)

_VESPERS_ANTIPHON = (
    "Antiphon: From the rising of the sun to its setting, the name of the "
    "Lord is to be praised."
)

_VESPERS_PSALM = (
    "The Lord's revelation to my Master: 'Sit on my right;\n"
    "your foes I will put beneath your feet.'\n\n"
    "The Lord will wield from Zion your sceptre of power; rule in the midst "
    "of all your foes.\n\n"
    "A prince from the day of your birth on the holy mountains;\n"
    "from the womb before the dawn I begot you.\n\n"
    "The Lord has sworn an oath he will not change. 'You are a priest for ever,\n"
    "a priest like Melchizedek of old.' — Ps 110\n\n"
    "(Glory to the Father…)"
)

_VESPERS_READING = (
    "Blessed be the God and Father of our Lord Jesus Christ, the Father of "
    "mercies and God of all consolation, who consoles us in all our "
    "afflictions. — 2 Corinthians 1:3-4"
)

_VESPERS_RESPONSORY = (
    "V. Let my prayer rise like incense before you, O Lord.\n"
    "R. Let my prayer rise like incense before you, O Lord."
)

_MAGNIFICAT_ANTIPHON = (
    "Antiphon: My soul proclaims the greatness of the Lord, for he has "
    "looked with favour on his lowly servant."
)

_MAGNIFICAT = (
    "My soul proclaims the greatness of the Lord, my spirit rejoices in "
    "God my Saviour;\n\n"
    "for he has looked with favour on his lowly servant. From this day "
    "all generations will call me blessed:\n\n"
    "the Almighty has done great things for me, and holy is his Name.\n\n"
    "He has mercy on those who fear him in every generation.\n\n"
    "He has shown the strength of his arm, he has scattered the proud in "
    "their conceit.\n\n"
    "He has cast down the mighty from their thrones, and has lifted up the lowly.\n\n"
    "He has filled the hungry with good things, and the rich he has sent away empty.\n\n"
    "He has come to the help of his servant Israel for he has remembered "
    "his promise of mercy,\n\n"
    "the promise he made to our fathers, to Abraham and his children for ever.\n\n"
    "(Glory to the Father…)"
)

_VESPERS_INTERCESSIONS = (
    "Let us call upon Christ, the light who never fades, and say: Lord, "
    "hear our prayer.\n\n"
    "— For the Church gathered at evening, that she may shine as a lamp "
    "before the world.\n"
    "— For our Holy Father and all who shepherd God's people.\n"
    "— For peace among nations and within every home.\n"
    "— For the sick, the lonely, and all who labour through the night.\n"
    "— For our beloved dead, that they may rest in your light."
)

_VESPERS_CLOSING_PRAYER = (
    "Lord God, send peaceful sleep to refresh our tired bodies. May your "
    "help always renew us and keep us strong in your service. We ask this "
    "through Christ our Lord. Amen."
)

_VESPERS_BLESSING = (
    "May the Lord bless us, protect us from all evil, and bring us to "
    "everlasting life. Amen."
)


# Inline novena prayers for the six most common novenas.
# Keys are lowercase substring matches against the saint/devotion name.
_NOVENA_PRAYERS = {
    "holy spirit": (
        "On this day of the Novena to the Holy Spirit:\n\n"
        "Come, Holy Spirit, fill the hearts of Thy faithful and kindle "
        "in them the fire of Thy love. Send forth Thy Spirit and they "
        "shall be created. And Thou shalt renew the face of the earth.\n\n"
        "O God, who by the light of the Holy Spirit didst instruct the "
        "hearts of the faithful, grant that by the same Holy Spirit we "
        "may be truly wise and ever rejoice in His consolation, through "
        "Christ Our Lord. Amen.\n\n"
        "Holy Spirit, Spirit of truth, come into our hearts; shed the "
        "brightness of Thy light on all nations, that they may be one "
        "in faith and pleasing to Thee.\n\n"
        "Pray one Our Father, Hail Mary, and Glory Be."
    ),
    "sacred heart": (
        "On this day of the Novena to the Sacred Heart of Jesus:\n\n"
        "O most holy Heart of Jesus, fountain of every blessing, I "
        "adore Thee, I love Thee, and with lively sorrow for my sins I "
        "offer Thee this poor heart of mine. Make me humble, patient, "
        "pure, and wholly obedient to Thy will. Grant, good Jesus, that "
        "I may live in Thee and for Thee.\n\n"
        "Protect me in the midst of danger; comfort me in my afflictions; "
        "give me health of body, assistance in my temporal needs, Thy "
        "blessing on all that I do, and the grace of a holy death.\n\n"
        "Within Thy Heart I place my every care. In every need let me "
        "come to Thee with humble trust saying, Heart of Jesus, help me.\n\n"
        "(State your intention.) Pray one Our Father, Hail Mary, and Glory Be."
    ),
    "divine mercy": (
        "On this day of the Divine Mercy Novena:\n\n"
        "Most Merciful Jesus, whose very nature it is to have compassion "
        "on us and to forgive us, do not look upon our sins, but upon "
        "our trust which we place in Your infinite goodness. Receive us "
        "all into the abode of Your Most Compassionate Heart, and never "
        "let us escape from It. We beg this of You by Your love which "
        "unites You to the Father and the Holy Spirit.\n\n"
        "Eternal Father, turn Your merciful gaze upon (today's intention "
        "from the Diary of St. Faustina), and through the Sorrowful "
        "Passion of Jesus and His mercy, grant our petitions.\n\n"
        "Then pray the Chaplet of Divine Mercy on ordinary rosary beads."
    ),
    "fatima": (
        "On this day of the Novena to Our Lady of Fatima:\n\n"
        "Most Holy Virgin, who hast deigned to come to Fatima to reveal "
        "to the three little shepherds the treasures of graces hidden "
        "in the recitation of the Rosary, inspire our hearts with a "
        "sincere love of this devotion, that, by meditating on the "
        "Mysteries of our Redemption recalled in it, we may gather the "
        "fruits and obtain the conversion of sinners, the special favor "
        "I now ask: (state your intention).\n\n"
        "I ask it for the greater glory of God, for thine own honor, and "
        "for the good of souls. Amen.\n\n"
        "Our Lady of the Most Holy Rosary of Fatima, pray for us.\n\n"
        "Pray one Our Father, Hail Mary, and Glory Be."
    ),
    "joseph": (
        "On this day of the Novena to St. Joseph:\n\n"
        "O Glorious Saint Joseph, faithful follower of Jesus Christ, to "
        "thee we raise our hearts and hands, to implore thy powerful "
        "intercession in obtaining from the benign Heart of Jesus all "
        "the helps and graces necessary for our spiritual and temporal "
        "welfare, particularly the grace of a happy death, and the "
        "special favor we now implore: (state your intention).\n\n"
        "O Guardian of the Word Incarnate, we feel animated with "
        "confidence that thy prayers in our behalf will be graciously "
        "heard before the throne of God.\n\n"
        "St. Joseph, foster-father of Jesus, pray for us. St. Joseph, "
        "most chaste spouse of Mary, pray for us.\n\n"
        "Pray one Our Father, Hail Mary, and Glory Be."
    ),
    "therese": (
        "On this day of the Novena to St. Thérèse of the Child Jesus:\n\n"
        "O Little Thérèse of the Child Jesus, please pick for me a rose "
        "from the heavenly gardens and send it to me as a message of "
        "love. O Little Flower of Jesus, ask God today to grant the "
        "favors I now place with confidence in your hands: (state your "
        "intention).\n\n"
        "St. Thérèse, help me to always believe, as you did, in God's "
        "great love for me, so that I might imitate your 'Little Way' "
        "each day. Amen.\n\n"
        "St. Thérèse of the Child Jesus, pray for us.\n\n"
        "Pray one Our Father, Hail Mary, and Glory Be."
    ),
}

_NOVENAS_FALLBACK_URL = "https://www.ewtn.com/catholicism/devotions/novenas"


def _novena_prayer_for(saint: str) -> str:
    s = (saint or "").lower()
    for key, text in _NOVENA_PRAYERS.items():
        if key in s:
            return text
    return ""


def _compline_marian_antiphon(d: date):
    """Return (title, prayer_text) for the season-appropriate Marian antiphon."""
    season = ""
    try:
        from render_liturgical import get_day_info
        info = get_day_info(d)
        season = (info or {}).get("season", "") or ""
    except Exception:
        season = ""
    s = season.lower()
    if "advent" in s or "christmas" in s:
        return ("Alma Redemptoris Mater", _ALMA_REDEMPTORIS)
    if "lent" in s or "holy week" in s or "passion" in s:
        return ("Ave Regina Caelorum", _AVE_REGINA_CAELORUM)
    if "easter" in s:
        return ("Regina Caeli", _REGINA_CAELI)
    return ("Salve Regina", _SALVE_REGINA)


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


def _hour_part(label: str, body_text: str) -> str:
    safe_label = escape(label)
    safe_body = escape(body_text).replace("\n", "<br>")
    return (
        f'<div style="margin:14px 0 0;">'
        f'<div style="font-family:Georgia,serif;font-weight:600;color:{_accent()};'
        f'font-size:0.95em;margin:0 0 6px;letter-spacing:0.02em;">{safe_label}</div>'
        f'<div style="font-family:Georgia,serif;font-size:0.96em;line-height:1.7;'
        f'color:#1a1a1a;white-space:pre-line;">{safe_body}</div>'
        f'</div>'
    )


def _collapsible_card(summary_text: str, body_html: str, *, scriptural: str = "") -> str:
    safe_summary = escape(summary_text)
    sub = ""
    if scriptural:
        sub = (f'<div style="font-style:italic;color:#5a6a85;font-size:0.86em;'
               f'margin:10px 0 0;line-height:1.5;">'
               f'&ldquo;{escape(scriptural)}&rdquo;</div>')
    return (
        f'<section style="background:white;border:1px solid #d4dcea;border-radius:14px;'
        f'padding:18px 20px;margin:0 0 14px;box-shadow:0 1px 2px rgba(0,0,0,0.03);">'
        f'<details style="margin:0;">'
        f'<summary style="cursor:pointer;font-family:Georgia,serif;font-weight:400;'
        f'font-size:1.15em;color:{_accent()};padding:0;list-style:none;">'
        f'{safe_summary}'
        f'<span style="color:{_accent()};font-size:0.7em;font-style:italic;'
        f'margin-left:8px;opacity:0.7;">(tap to expand)</span>'
        f'</summary>'
        f'<div style="margin-top:12px;">{body_html}</div>'
        f'</details>{sub}</section>'
    )


def _hour_details(summary_text: str, parts_html: str) -> str:
    safe_summary = escape(summary_text)
    return (
        f'<details style="margin:0;">'
        f'<summary style="cursor:pointer;font-family:Georgia,serif;'
        f'font-size:0.96em;line-height:1.7;color:#1a1a1a;padding:4px 0;">'
        f'{safe_summary} '
        f'<span style="color:{_accent()};font-size:0.82em;font-style:italic;'
        f'margin-left:4px;">(tap to expand the full prayer)</span>'
        f'</summary>'
        f'<div style="margin-top:10px;padding:14px 16px;background:#f4f7fc;'
        f'border-left:3px solid {_accent()};border-radius:6px;">'
        f'{parts_html}'
        f'</div>'
        f'</details>'
    )


def _lauds_full_html() -> str:
    parts = [
        _hour_part("Opening", _LOH_OPENING),
        _hour_part("Hymn", _LAUDS_HYMN),
        _hour_part("Psalmody — Psalm 63", _LAUDS_ANTIPHON + "\n\n" + _LAUDS_PSALM_63),
        _hour_part("Short Reading", _LAUDS_READING),
        _hour_part("Responsory", _LAUDS_RESPONSORY),
        _hour_part("Gospel Canticle — Benedictus (Lk 1:68-79)",
                   _BENEDICTUS_ANTIPHON + "\n\n" + _BENEDICTUS),
        _hour_part("Intercessions", _LAUDS_INTERCESSIONS),
        _hour_part("The Lord's Prayer", _OUR_FATHER),
        _hour_part("Concluding Prayer", _LAUDS_CLOSING_PRAYER),
        _hour_part("Blessing", _LAUDS_BLESSING),
    ]
    return "".join(parts)


def _terce_full_html() -> str:
    parts = [
        _hour_part("Opening", _LOH_OPENING),
        _hour_part("Hymn", _TERCE_HYMN),
        _hour_part("Psalmody", _TERCE_PSALM),
        _hour_part("Short Reading", _TERCE_READING),
        _hour_part("Responsory", _TERCE_RESPONSORY),
        _hour_part("Concluding Prayer", _TERCE_PRAYER),
    ]
    return "".join(parts)


def _sext_full_html() -> str:
    parts = [
        _hour_part("Opening", _LOH_OPENING),
        _hour_part("Hymn", _SEXT_HYMN),
        _hour_part("Psalmody — Psalm 123", _SEXT_PSALM),
        _hour_part("Short Reading", _SEXT_READING),
        _hour_part("Responsory", _SEXT_RESPONSORY),
        _hour_part("Concluding Prayer", _SEXT_PRAYER),
    ]
    return "".join(parts)


def _none_full_html() -> str:
    parts = [
        _hour_part("Opening", _LOH_OPENING),
        _hour_part("Hymn", _NONE_HYMN),
        _hour_part("Psalmody — Psalm 125", _NONE_PSALM),
        _hour_part("Short Reading", _NONE_READING),
        _hour_part("Responsory", _NONE_RESPONSORY),
        _hour_part("Concluding Prayer", _NONE_PRAYER),
    ]
    return "".join(parts)


def _vespers_full_html() -> str:
    parts = [
        _hour_part("Opening", _LOH_OPENING),
        _hour_part("Hymn", _VESPERS_HYMN),
        _hour_part("Psalmody — Psalm 110", _VESPERS_ANTIPHON + "\n\n" + _VESPERS_PSALM),
        _hour_part("Short Reading", _VESPERS_READING),
        _hour_part("Responsory", _VESPERS_RESPONSORY),
        _hour_part("Gospel Canticle — Magnificat (Lk 1:46-55)",
                   _MAGNIFICAT_ANTIPHON + "\n\n" + _MAGNIFICAT),
        _hour_part("Intercessions", _VESPERS_INTERCESSIONS),
        _hour_part("The Lord's Prayer", _OUR_FATHER),
        _hour_part("Concluding Prayer", _VESPERS_CLOSING_PRAYER),
        _hour_part("Blessing", _VESPERS_BLESSING),
    ]
    return "".join(parts)


def _compline_full_html(now_dt: datetime) -> str:
    ant_title, ant_text = _compline_marian_antiphon(now_dt.date())
    parts = [
        _hour_part("Opening", _LOH_OPENING),
        _hour_part("Examination of Conscience", _COMPLINE_EXAMEN),
        _hour_part("Confiteor", _COMPLINE_CONFITEOR),
        _hour_part("Hymn — Te lucis ante terminum", _TE_LUCIS_ANTE_TERMINUM),
        _hour_part("Psalmody — Psalm 91", _PSALM_91),
        _hour_part("Short Reading (Jer 14:9)", _COMPLINE_SHORT_READING),
        _hour_part("Responsory", _COMPLINE_RESPONSORY),
        _hour_part("Gospel Canticle — Nunc Dimittis (Lk 2:29-32)", _NUNC_DIMITTIS),
        _hour_part("The Lord's Prayer", _OUR_FATHER),
        _hour_part("Concluding Prayer & Blessing", _COMPLINE_CLOSING),
        _hour_part(f"Marian Antiphon — {ant_title}", ant_text),
    ]
    return "".join(parts)


def _render_block_prayers(block: str, now_dt: datetime, weekday: str) -> str:
    out = []
    if block == "early_morning":
        out.append(_card("Morning Offering",
                         _prose(_MORNING_OFFERING),
                         scriptural="In the morning, O Lord, You hear my voice. — Ps 5:3"))
        out.append(_card(
            "Lauds — Morning Prayer",
            _hour_details(
                "Open the day with the Church: Psalm 63 (longing), the "
                "Benedictus, and intercession for the Church and the world.",
                _lauds_full_html(),
            ),
        ))
    elif block == "morning":
        secs_to_noon = max(0, (12 * 3600) - (now_dt.hour * 3600 + now_dt.minute * 60))
        mins = secs_to_noon // 60
        when = f"in {mins // 60}h {mins % 60}m" if mins else "now"
        bell_html = (f'<div style="font-size:0.88em;color:#5a6a85;'
                     f'margin:0 0 10px;">Bell rings {escape(when)}.</div>')
        out.append(_collapsible_card(
            "The Angelus — at noon",
            bell_html + _prose(_ANGELUS),
            scriptural="And the Word became flesh and dwelt among us. — Jn 1:14",
        ))
        out.append(_card(
            "Terce — Mid-Morning Prayer",
            _hour_details(
                "A brief pause at the third hour, when the Holy Spirit "
                "descended on the apostles at Pentecost.",
                _terce_full_html(),
            ),
        ))
        out.append(_card("A breath at mid-morning",
                         _prose("Pause. One slow breath. 'Jesus, I trust in You.'"),
                         scriptural="Be still, and know that I am God. — Ps 46:10"))
    elif block == "afternoon":
        is_three = (now_dt.hour == 15)
        title = "Divine Mercy — the Hour of Mercy" if is_three else "Divine Mercy Chaplet"
        scrip = ("At three o'clock, implore My mercy. — Diary of St. Faustina"
                 if is_three else "")
        out.append(_card(title, _prose(_DIVINE_MERCY), scriptural=scrip))
        out.append(_card(
            "Sext — Midday Prayer",
            _hour_details(
                "A still moment at noon: Psalm 123, lifting our eyes to the "
                "Lord, and a return to the day's work in His company.",
                _sext_full_html(),
            ),
        ))
        out.append(_card(
            "None — Mid-Afternoon Prayer",
            _hour_details(
                "The ninth hour, when our Lord surrendered His spirit. "
                "Psalm 125 — those who trust the Lord stand firm as Zion.",
                _none_full_html(),
            ),
        ))
    elif block == "evening":
        out.append(_collapsible_card(
            "The Angelus — at six",
            _prose(_ANGELUS),
            scriptural="And the Word became flesh. — Jn 1:14",
        ))
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
        out.append(_card(
            "Vespers — Evening Prayer",
            _hour_details(
                "The Church lifts up the Magnificat with Mary at evening: "
                "'My soul magnifies the Lord.'",
                _vespers_full_html(),
            ),
        ))
    else:  # late_evening
        out.append(_card(
            "Compline — Night Prayer",
            _hour_details(
                "'Into Your hands, O Lord, I commend my spirit.' The Church's "
                "last prayer of the day — examen, Psalm 91, the Nunc Dimittis, "
                "and a Marian antiphon to close.",
                _compline_full_html(now_dt),
            ),
            scriptural="He gives sleep to His beloved. — Ps 127:2",
        ))
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
                _prayer_text = _novena_prayer_for(saint)
                if _prayer_text:
                    _safe_prayer = escape(_prayer_text).replace("\n", "<br>")
                    _detail_body = (
                        f'<div style="margin:6px 0 4px 14px;padding:10px 14px;'
                        f'background:#f4f7fc;border-left:3px solid {_accent()};'
                        f'border-radius:6px;font-family:Georgia,serif;font-size:0.92em;'
                        f'line-height:1.6;color:#1a1a1a;white-space:pre-line;">'
                        f'{_safe_prayer}</div>'
                    )
                else:
                    _ewtn = escape(_NOVENAS_FALLBACK_URL, quote=True)
                    _detail_body = (
                        f'<div style="margin:6px 0 4px 14px;padding:8px 14px;'
                        f'background:#f4f7fc;border-left:3px solid {_accent()};'
                        f'border-radius:6px;font-size:0.9em;color:#2d4a78;">'
                        f'Prayer text for this novena is not stored locally. '
                        f'<a href="{_ewtn}" target="_blank" rel="noopener" '
                        f'style="color:{_accent()};">Open EWTN novena library &rarr;</a>'
                        f'</div>'
                    )
                rows.append(
                    f'<li style="margin:6px 0;list-style:none;">'
                    f'<details style="cursor:pointer;">'
                    f'<summary style="display:list-item;list-style:disclosure-closed inside;'
                    f'color:#2d4a78;outline:none;">'
                    f'Novena to {escape(saint)}'
                    f' <span style="color:#999;font-size:0.8em;">'
                    f'(day {day_n} of 9 &middot; tap for prayer)</span>'
                    f'</summary>'
                    f'{_detail_body}'
                    f'</details></li>'
                )
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
    "late_evening":  (20, 22),
}

_BLOCK_EMPTY_FROL_MSG = {
    "early_morning": "No scheduled rhythm before 7 AM — let the day begin in quiet prayer.",
    "morning":       "The morning is open — offer the hours to the Lord and follow His lead.",
    "afternoon":     "Nothing scheduled this afternoon — a gift of unhurried time.",
    "evening":       "No fixed rhythm this evening — gather the family and rest.",
    "late_evening":  "Nothing on the rule tonight — the day is His. Time to rest.",
}


def _render_frol_snapshot(weekday: str, block: str) -> str:
    try:
        from data_helpers import get_frol_day_slots
        slots = get_frol_day_slots(weekday, person="Mom") or {}
    except Exception:
        slots = {}
    lo, hi = _BLOCK_HOUR_RANGE.get(block, (0, 24))
    hi_ext = min(24, hi + 2)

    def _minutes_of(t: str) -> int:
        try:
            s = (t or "").strip().upper()
            suffix = ""
            if s.endswith("AM") or s.endswith("PM"):
                suffix = s[-2:]
                s = s[:-2].strip()
            parts = s.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            if suffix == "AM":
                if h == 12:
                    h = 0
            elif suffix == "PM":
                if h != 12:
                    h = h + 12
            return h * 60 + m
        except Exception:
            return -1

    lo_min = lo * 60
    hi_min = hi_ext * 60
    sorted_keys = sorted(slots.keys(), key=_minutes_of)
    rows = []
    for t in sorted_keys:
        mins = _minutes_of(t)
        if lo_min <= mins < hi_min:
            label = (slots[t] or "").strip()
            if label:
                rows.append(f'<div style="display:flex;gap:12px;padding:5px 0;'
                            f'border-bottom:1px dashed #e4eaf3;">'
                            f'<div style="color:{_accent()};font-weight:600;'
                            f'font-size:0.85em;width:60px;">{escape(t)}</div>'
                            f'<div style="font-size:0.92em;color:#1a1a1a;">'
                            f'{escape(label)}</div></div>')
    if rows:
        body = "".join(rows)
    else:
        msg = _BLOCK_EMPTY_FROL_MSG.get(
            block,
            "No scheduled rhythm for this hour — pause and breathe.",
        )
        body = (f'<div style="font-style:italic;color:#5a6a85;font-size:0.92em;'
                f'line-height:1.6;padding:6px 0;">{escape(msg)}</div>')
    return _card(f"Rule of Life — {_BLOCK_LABELS.get(block, block)}",
                 body)


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


def _meal_prep_bullets(recipe: dict) -> list:
    if not recipe:
        return []
    instr = recipe.get("instructions", "") or ""
    if isinstance(instr, list):
        lines = [str(x).strip() for x in instr]
    else:
        lines = [ln.strip() for ln in str(instr).splitlines()]
    cleaned = []
    for ln in lines:
        if not ln:
            continue
        stripped = ln.lstrip("0123456789.)-•* \t")
        if stripped:
            cleaned.append(stripped)
        if len(cleaned) >= 3:
            break
    return cleaned


def _render_meal_row(label: str, slot_value) -> str:
    try:
        from render_meals import slot_display_text, slot_recipe_id
        from data_helpers import get_recipe_by_id
    except Exception:
        slot_display_text = lambda v: (str(v).strip() if isinstance(v, str) else "")
        slot_recipe_id    = lambda v: None
        get_recipe_by_id  = lambda r: None

    name = slot_display_text(slot_value)
    if not name:
        return (
            f'<div style="padding:8px 0;border-bottom:1px dashed #e4eaf3;">'
            f'<div style="font-size:0.78em;text-transform:uppercase;'
            f'letter-spacing:0.06em;color:{_accent()};font-weight:700;">'
            f'{escape(label)}</div>'
            f'<div style="font-size:0.88em;color:#999;font-style:italic;'
            f'margin-top:4px;">No meal planned &middot; '
            f'<a href="/lorenzo" style="color:#2d4a78;text-decoration:none;'
            f'font-style:normal;">ask Lorenzo to plan one &rarr;</a></div>'
            f'</div>'
        )

    recipe = None
    rid = slot_recipe_id(slot_value)
    if rid:
        try:
            recipe = get_recipe_by_id(rid) or None
        except Exception:
            recipe = None

    meta_bits = []
    if isinstance(slot_value, dict):
        prep_tasks = slot_value.get("prep_tasks") or slot_value.get("prep") or ""
        if isinstance(prep_tasks, list):
            prep_tasks = ", ".join(str(x) for x in prep_tasks if x)
        prep_tasks = str(prep_tasks or "").strip()
        if prep_tasks:
            meta_bits.append(f'<span style="color:#5a6a85;">'
                             f'&#9881;&#65039; {escape(prep_tasks)}</span>')
        helpers = slot_value.get("helpers") or slot_value.get("assigned") or ""
        if isinstance(helpers, list):
            helpers = ", ".join(str(x) for x in helpers if x)
        helpers = str(helpers or "").strip()
        if helpers:
            meta_bits.append(f'<span style="color:#5a6a85;">'
                             f'&#128101; {escape(helpers)}</span>')
        ct_raw = slot_value.get("cook_time") or slot_value.get("time") or ""
        cook_time = ct_raw.strip() if isinstance(ct_raw, str) else ""
    else:
        cook_time = ""
    if not cook_time and recipe:
        cook_time = str(recipe.get("prep_time", "") or "").strip()
    if cook_time:
        meta_bits.append(f'<span style="color:#5a6a85;">'
                         f'&#9201;&#65039; {escape(cook_time)}</span>')

    meta_html = ""
    if meta_bits:
        meta_html = (f'<div style="font-size:0.82em;margin-top:4px;'
                     f'display:flex;gap:12px;flex-wrap:wrap;">'
                     + "".join(meta_bits) + '</div>')

    bullets_html = ""
    bullets = _meal_prep_bullets(recipe)
    if bullets:
        items = "".join(
            f'<li style="margin:3px 0;">{escape(b)}</li>' for b in bullets
        )
        bullets_html = (
            f'<ul style="font-size:0.86em;color:#1a1a1a;line-height:1.5;'
            f'margin:6px 0 0;padding-left:20px;">{items}</ul>'
        )

    return (
        f'<div style="padding:8px 0;border-bottom:1px dashed #e4eaf3;">'
        f'<div style="font-size:0.78em;text-transform:uppercase;'
        f'letter-spacing:0.06em;color:{_accent()};font-weight:700;">'
        f'{escape(label)}</div>'
        f'<div style="font-size:0.96em;color:#1a1a1a;margin-top:3px;'
        f'font-weight:500;">{escape(name)}</div>'
        f'{meta_html}{bullets_html}'
        f'</div>'
    )


def _render_meals_snapshot(weekday: str, today: date, block: str) -> str:
    try:
        from render_meals import load_meal_plan
        monday = today - timedelta(days=today.weekday())
        wk = monday.isoformat()
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
        rows.append(_render_meal_row(label, day_meals.get(key)))
    return _card(f"Meals — {_BLOCK_LABELS.get(block, block)}",
                 "".join(rows) +
                 '<div style="text-align:right;margin-top:10px;">'
                 '<a href="/lorenzo" style="color:#2d4a78;font-size:0.85em;'
                 'text-decoration:none;">Talk to Lorenzo &rarr;</a></div>')


# ─────────────────────────────────────────────────────────────────────────────
# Saint card + Pope intention card
# ─────────────────────────────────────────────────────────────────────────────

_FEAST_AI_CACHE = {}

_UPCOMING_FEAST_NOTES = {
    "Christmas":              "The Nativity of the Lord — Christ is born for us.",
    "Easter":                 "The Resurrection of the Lord — He is risen, alleluia!",
    "Pentecost":              "Birth of the Church — the Holy Spirit comes in fire.",
    "Assumption":             "Mary taken body and soul into heaven.",
    "Immaculate Conception":  "Mary conceived without sin from her first moment.",
    "All Saints":             "The whole communion of saints, friends of God.",
    "Corpus Christi":         "Solemnity of the Body and Blood of Christ.",
    "Sacred Heart":           "The pierced Heart of Jesus, fountain of mercy.",
    "Our Lady of Guadalupe":  "Mary's appearance to St. Juan Diego on Tepeyac.",
    "St. Nicholas":           "The bishop who gave in secret — patron of children.",
    "St. Joseph":             "Foster-father of Jesus, guardian of the Holy Family.",
    "Annunciation":           "Gabriel greets Mary; the Word becomes flesh.",
    "Holy Family":            "Jesus, Mary, and Joseph — model of every home.",
    "Epiphany":               "The Magi arrive with gold, frankincense, and myrrh.",
    "Ash Wednesday":          "Lent begins with ashes and forty days of fasting.",
}


def _upcoming_feast_dates(today_d):
    out = []
    try:
        from render_liturgical import get_moveable_feasts as _gmv
    except Exception:
        _gmv = None
    for yr in (today_d.year, today_d.year + 1):
        out.extend([
            ("Christmas",              date(yr, 12, 25)),
            ("Epiphany",               date(yr,  1,  6)),
            ("Assumption",             date(yr,  8, 15)),
            ("Immaculate Conception",  date(yr, 12,  8)),
            ("All Saints",             date(yr, 11,  1)),
            ("Our Lady of Guadalupe",  date(yr, 12, 12)),
            ("St. Nicholas",           date(yr, 12,  6)),
            ("St. Joseph",             date(yr,  3, 19)),
            ("Annunciation",           date(yr,  3, 25)),
        ])
        if _gmv:
            try:
                mv = _gmv(yr) or {}
            except Exception:
                mv = {}
            wanted = {
                "Easter Sunday":         "Easter",
                "Pentecost Sunday":      "Pentecost",
                "Corpus Christi":        "Corpus Christi",
                "Sacred Heart of Jesus": "Sacred Heart",
                "Ash Wednesday":         "Ash Wednesday",
            }
            for d_, tup in mv.items():
                nm = tup[0] if isinstance(tup, (tuple, list)) and tup else ""
                if nm in wanted:
                    out.append((wanted[nm], d_))
        christmas = date(yr, 12, 25)
        offset = (6 - christmas.weekday()) % 7
        if offset == 0:
            offset = 7
        if christmas.weekday() == 6:
            holy_family = date(yr, 12, 30)
        else:
            holy_family = christmas + timedelta(days=offset)
        out.append(("Holy Family", holy_family))
    return out


def _render_upcoming_feast_notice(today_d) -> str:
    try:
        upcoming = _upcoming_feast_dates(today_d)
    except Exception:
        return ""
    target = today_d + timedelta(days=7)
    matches = [(n, d_) for (n, d_) in upcoming if d_ == target]
    if not matches:
        return ""
    name, d_ = matches[0]
    note = _UPCOMING_FEAST_NOTES.get(name, "")
    title_html = (
        f'<div style="font-family:Georgia,serif;font-size:1.0em;color:#1a1a1a;">'
        f'&#128197; <strong>{escape(name)}</strong> is in 7 days &mdash; start planning!'
        f'</div>'
    )
    note_html = ""
    if note:
        note_html = (
            f'<div style="font-size:0.9em;color:#5a6a85;margin-top:6px;'
            f'line-height:1.5;">{escape(note)}</div>'
        )
    return _card("Coming up in the Church", title_html + note_html)


def _get_feast_ai_summary(iso: str, feast_name: str) -> str:
    if not feast_name:
        return ""
    cache_key = iso
    if cache_key in _FEAST_AI_CACHE:
        return _FEAST_AI_CACHE[cache_key]
    import json as _json
    import urllib.request as _req
    try:
        from render_settings import load_app_settings
        settings = load_app_settings() or {}
    except Exception:
        settings = {}
    api_key = (settings.get("family_constraints", {}).get("anthropic_api_key", "")
               or settings.get("anthropic_api_key", "")).strip()
    if not api_key:
        api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        return ""
    system = (
        "You write warm, devotional Catholic feast-day notes for a Catholic mother "
        "who loves the faith. Output two paragraphs, plain text, no markdown, no "
        "headings beyond what is specified. "
        "First paragraph: 3-4 sentences about today's feast. Lead with a concrete "
        "fact, vivid story detail, or specific moment — never start with 'Today we "
        "celebrate' or any generic opener. For a Marian apparition begin with what "
        "actually happened in the apparition. For a martyr begin with their death "
        "or act of courage. For a confessor begin with the most memorable thing "
        "they did or said. End the first paragraph with one sentence about why "
        "this feast matters for daily life. "
        "Then a blank line, then a second paragraph that begins with the exact "
        "line 'Ways to celebrate today:' followed by 3-4 concrete suggestions on "
        "separate lines, each starting with a bullet character (•). Suggestions "
        "should include traditional foods, activities for children, prayers and "
        "devotional practices, and customs from Catholic tradition. "
        "Keep tone warm and devotional. Never preachy."
    )
    user = f"Today's feast is: {feast_name}. Write the note."
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 600,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    text = ""
    try:
        req = _req.Request(
            "https://api.anthropic.com/v1/messages",
            data=_json.dumps(payload).encode(),
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with _req.urlopen(req, timeout=20) as resp:
            result = _json.loads(resp.read())
        text = (result.get("content", [{}])[0].get("text", "") or "").strip()
    except Exception:
        text = ""
    if not text:
        return ""
    html_parts = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    for p in paragraphs:
        lines = [ln for ln in p.split("\n") if ln.strip()]
        bullets = [ln for ln in lines if ln.lstrip().startswith(("•", "-", "*"))]
        non_bullets = [ln for ln in lines if not ln.lstrip().startswith(("•", "-", "*"))]
        if bullets:
            if non_bullets:
                heading_html = escape(" ".join(non_bullets).strip())
                html_parts.append(
                    f'<div style="font-family:Georgia,serif;font-weight:600;'
                    f'color:{_accent()};font-size:0.95em;margin:14px 0 6px;">'
                    f'{heading_html}</div>'
                )
            li_items = []
            for b in bullets:
                clean = b.lstrip("•-* ").strip()
                if clean:
                    li_items.append(f'<li style="margin:4px 0;">{escape(clean)}</li>')
            html_parts.append(
                f'<ul style="font-family:Georgia,serif;font-size:0.94em;'
                f'line-height:1.6;color:#1a1a1a;padding-left:22px;margin:6px 0 0;">'
                + "".join(li_items) + "</ul>"
            )
        else:
            safe = escape(p).replace("\n", "<br>")
            html_parts.append(
                f'<div style="font-family:Georgia,serif;font-size:0.96em;'
                f'line-height:1.7;color:#1a1a1a;margin:10px 0 0;">{safe}</div>'
            )
    html = "".join(html_parts)
    _FEAST_AI_CACHE[cache_key] = html
    return html


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
    feast_for_ai = feast or (obs[0] if obs else "")
    summary_suffix = feast or (obs[0] if obs else "")
    if summary_suffix:
        summary_text = f"Today in the Church — {summary_suffix}"
    else:
        summary_text = "Today in the Church"
    bits = []
    if season:
        bits.append(f'<div style="font-size:0.86em;color:#5a6a85;">'
                    f'Liturgical season: {escape(season)}</div>')
    for o in obs:
        bits.append(f'<div style="font-size:0.86em;color:#7a3e1a;margin-top:4px;">'
                    f'&middot; {escape(o)}</div>')
    ai_html = _get_feast_ai_summary(iso, feast_for_ai)
    if ai_html:
        bits.append(ai_html)
    return _collapsible_card(summary_text, "".join(bits))


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


def _render_daily_mass_link(today_d: date = None, block: str = "") -> str:
    usccb_btn = ""
    if block in ("early_morning", "afternoon") and today_d is not None:
        _mmddyy = today_d.strftime("%m%d%y")
        _usccb_url = escape(f"https://bible.usccb.org/bible/readings/{_mmddyy}.cfm",
                            quote=True)
        usccb_btn = (
            f'<a href="{_usccb_url}" target="_blank" rel="noopener" '
            f'style="display:inline-block;background:{_accent()};color:white;'
            f'text-decoration:none;padding:10px 22px;border-radius:22px;'
            f'font-size:0.92em;font-family:inherit;margin:4px 6px;">'
            '&#128214; Today\'s Readings (USCCB) &rarr;</a>'
        )
    if not usccb_btn:
        return ""
    return (
        '<div style="text-align:center;margin:6px 0 14px;">'
        f'{usccb_btn}'
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
    photographer = (img.get("photographer") or "").strip()
    photographer_url = (img.get("photographer_url") or "").strip()
    hero_credit_html = ""
    if photographer:
        if photographer_url:
            _phref = escape(photographer_url, quote=True)
            inner = (
                f'Photo: <a href="{_phref}" target="_blank" rel="noopener" '
                f'style="color:inherit;text-decoration:underline;">'
                f'{escape(photographer)}</a> on '
                f'<a href="https://www.pexels.com" target="_blank" rel="noopener" '
                f'style="color:inherit;text-decoration:underline;">Pexels</a>'
            )
        else:
            inner = (
                f'Photo: {escape(photographer)} on '
                f'<a href="https://www.pexels.com" target="_blank" rel="noopener" '
                f'style="color:inherit;text-decoration:underline;">Pexels</a>'
            )
        hero_credit_html = f'<div class="credit">{inner}</div>'

    saint_card     = _render_saint_card(iso)
    upcoming_card  = _render_upcoming_feast_notice(today)
    prayers_html   = _render_block_prayers(block, now_dt, weekday)
    pope_card      = _render_pope_card(iso) if block == "afternoon" else ""
    intentions     = _render_intentions_widget(iso)
    novena_prompt  = _render_novena_prompt()
    frol_card      = _render_frol_snapshot(weekday, block)
    meals_card     = _render_meals_snapshot(weekday, today, block)
    daily_mass     = _render_daily_mass_link(today, block)

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
    {hero_credit_html}
    <div class="greet">{escape(greeting)}</div>
    <div class="when">{escape(date_label)} &middot; {escape(time_label)} ET</div>
    <div><span class="blocklbl">{escape(block_lbl)}</span></div>
  </div>
</div>
<div class="tb-body">
  {saint_card}
  {upcoming_card}
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
