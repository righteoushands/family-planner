"""
render_liturgical.py — Liturgical calendar engine and page renderers.
Imports from: config, data_helpers, ui_helpers
"""
from datetime import date, timedelta
from html import escape

from data_helpers import load_liturgical_custom, save_liturgical_custom
from ui_helpers import html_page, page_header, render_status_message


# ── Fixed feast days ─────────────────────────────────────────────────────────
FIXED_FEASTS = {
    (1,  1):  ("Solemnity of Mary, Mother of God", "white", "Holy Day of Obligation"),
    (1,  6):  ("Epiphany of the Lord", "white", ""),
    (2,  2):  ("Presentation of the Lord", "white", "Candlemas"),
    (2, 14):  ("Valentine's Day", "", ""),
    (3, 17):  ("St. Patrick's Day", "green", ""),
    (3, 19):  ("St. Joseph, Spouse of the Blessed Virgin Mary", "white", "Solemnity"),
    (3, 25):  ("Annunciation of the Lord", "white", "Solemnity"),
    (4, 23):  ("St. George, Martyr", "red", ""),
    (5,  1):  ("St. Joseph the Worker", "white", ""),
    (5, 13):  ("Our Lady of Fatima", "white", ""),
    (5, 31):  ("Visitation of the Blessed Virgin Mary", "white", ""),
    (6, 13):  ("St. Anthony of Padua", "white", ""),
    (6, 24):  ("Birth of St. John the Baptist", "white", "Solemnity"),
    (6, 29):  ("Sts. Peter and Paul, Apostles", "red", "Solemnity"),
    (7, 22):  ("St. Mary Magdalene", "white", ""),
    (7, 25):  ("St. James, Apostle", "red", ""),
    (7, 26):  ("Sts. Joachim and Anne", "white", "Parents of the Virgin Mary"),
    (8,  6):  ("Transfiguration of the Lord", "white", "Feast"),
    (8, 10):  ("St. Lawrence, Deacon and Martyr", "red", ""),
    (8, 14):  ("St. Maximilian Kolbe", "red", ""),
    (8, 15):  ("Assumption of the Blessed Virgin Mary", "white", "Holy Day of Obligation"),
    (8, 22):  ("Queenship of the Blessed Virgin Mary", "white", ""),
    (8, 28):  ("St. Augustine of Hippo", "white", ""),
    (8, 29):  ("Passion of St. John the Baptist", "red", ""),
    (9,  8):  ("Birth of the Blessed Virgin Mary", "white", ""),
    (9, 14):  ("Exaltation of the Holy Cross", "red", "Feast"),
    (9, 15):  ("Our Lady of Sorrows", "white", ""),
    (9, 29):  ("Sts. Michael, Gabriel, and Raphael", "white", "Archangels"),
    (10,  2): ("Guardian Angels", "white", ""),
    (10,  4): ("St. Francis of Assisi", "white", ""),
    (10,  7): ("Our Lady of the Rosary", "white", ""),
    (10, 18): ("St. Luke, Evangelist", "red", ""),
    (10, 28): ("Sts. Simon and Jude, Apostles", "red", ""),
    (11,  1): ("All Saints Day", "white", "Holy Day of Obligation"),
    (11,  2): ("All Souls Day", "purple", "Day of Prayer for the Dead"),
    (11,  9): ("Dedication of the Lateran Basilica", "white", ""),
    (11, 11): ("St. Martin of Tours", "white", ""),
    (11, 21): ("Presentation of the Blessed Virgin Mary", "white", ""),
    (11, 22): ("St. Cecilia", "red", "Patron of Musicians"),
    (11, 30): ("St. Andrew, Apostle", "red", ""),
    (12,  6): ("St. Nicholas of Myra", "white", ""),
    (12,  8): ("Immaculate Conception", "white", "Holy Day of Obligation"),
    (12, 12): ("Our Lady of Guadalupe", "white", ""),
    (12, 13): ("St. Lucy", "red", ""),
    (12, 25): ("Christmas — Nativity of the Lord", "white", "Holy Day of Obligation"),
    (12, 26): ("St. Stephen, First Martyr", "red", ""),
    (12, 27): ("St. John, Apostle and Evangelist", "white", ""),
    (12, 28): ("Holy Innocents, Martyrs", "red", ""),
    (12, 29): ("St. Thomas Becket", "red", ""),
    (12, 31): ("St. Sylvester I, Pope", "white", ""),
}

SEASON_COLORS = {
    "Advent":        "#4a235a",
    "Christmas":     "#d4af37",
    "Ordinary Time": "#5d7a3e",
    "Lent":          "#6b3fa0",
    "Holy Week":     "#8b0000",
    "Easter":        "#d4af37",
}

SEASON_TEXT_COLORS = {
    "Advent":        "white",
    "Christmas":     "#222",
    "Ordinary Time": "white",
    "Lent":          "white",
    "Holy Week":     "white",
    "Easter":        "#222",
}

VESTMENT_COLORS = {
    "white":  ("#ffffff", "#333"),
    "red":    ("#c0392b", "#fff"),
    "purple": ("#6b3fa0", "#fff"),
    "green":  ("#27ae60", "#fff"),
    "rose":   ("#e91e8c", "#fff"),
    "gold":   ("#d4af37", "#333"),
    "black":  ("#222222", "#fff"),
}

SEASON_PRAYERS = {
    "Advent": ["O Antiphons (Dec 17-23) — great for evening prayer","Rorate Caeli — ancient Advent hymn","Advent wreath prayers at dinner","Daily Rosary intention: Come, Lord Jesus"],
    "Christmas": ["Gloria in Excelsis Deo","Angelus at noon","Prayer before the nativity scene","Te Deum — thanksgiving prayer"],
    "Ordinary Time": ["Daily Rosary","Angelus at noon","Liturgy of the Hours — Morning and Evening Prayer","Act of Consecration to the Sacred Heart"],
    "Lent": ["Stations of the Cross (especially Fridays)","Divine Mercy Chaplet at 3pm","Examine of conscience each evening","Miserere — Psalm 51"],
    "Holy Week": ["Attend all Holy Week liturgies","Tenebrae (if available locally)","Veneration of the Cross on Good Friday","Easter Vigil — the mother of all vigils"],
    "Easter": ["Regina Caeli (replaces Angelus during Easter)","Divine Mercy Novena (starts Good Friday)","Alleluia — sing it as much as possible","Rosary: Glorious Mysteries"],
}

SEASON_ACTIVITIES = {
    "Advent": ["Make or set up the Advent wreath","Jesse Tree — add a new ornament each day","St. Nicholas Day preparations (Dec 5 evening)","Read aloud from a Christmas book as a family","Write letters to be read at Christmas"],
    "Christmas": ["Visit the nativity scene at your parish","Sing Christmas carols as a family","Feast of the Holy Innocents — honor children","Epiphany: chalk the door (20+C+M+B+26)","Bake a King Cake for Epiphany"],
    "Ordinary Time": ["Learn about this week's saint","Work on a saint lapbook or notebook","Read a saint biography aloud","Nature study and journaling"],
    "Lent": ["Choose a family Lenten sacrifice","Rice bowl or almsgiving jar","Make a paper chain — remove a link each day","Attend Friday Stations of the Cross","Holy Week basket preparations"],
    "Holy Week": ["Palm Sunday: save palms for next Ash Wednesday","Holy Thursday: visit seven churches","Good Friday: fast, silence, no screens 12-3pm","Holy Saturday: prepare Easter baskets for blessing","Dye Easter eggs with natural dyes"],
    "Easter": ["Easter basket blessing at the Vigil or Easter morning","Paschal candle — keep it lit at meals","Learn the Regina Caeli","Make Paschal bread or Paska","Ascension: fly a kite to represent Jesus ascending"],
}

FEAST_ACTIVITIES = {
    "Ash Wednesday": ["Attend Mass and receive ashes","Begin your Lenten sacrifices today","Family Lenten commitment jar"],
    "St. Patrick's Day": ["Read about St. Patrick's life","Make soda bread","Learn the Breastplate of St. Patrick"],
    "St. Joseph, Spouse of the Blessed Virgin Mary": ["St. Joseph's Table — share food with the poor","Honor fathers and father figures","Make zeppole (traditional St. Joseph's Day pastry)"],
    "Annunciation of the Lord": ["Pray the Angelus","Read Luke 1:26-38 together","Make a paper lily for Mary"],
    "Easter Sunday": ["Easter basket blessing","Easter egg hunt","Special Easter meal as a family"],
    "Ascension of the Lord": ["Fly a kite","Read Acts 1:1-11 together","Make cloud cookies"],
    "Pentecost Sunday": ["Wear red","Make a birthday cake for the Church","Learn about the gifts of the Holy Spirit"],
    "Assumption of the Blessed Virgin Mary": ["Bring flowers to Mary's altar","Make a flower crown","Pray the Rosary as a family"],
    "All Saints Day": ["Make saint costumes","Saint hunt — match clues to saints","Holy card collection"],
    "All Souls Day": ["Visit a cemetery","Pray for the souls of deceased family members","Light a candle for each departed loved one"],
    "St. Nicholas of Myra": ["Put out shoes the night before","Learn about St. Nicholas giving in secret","Do a secret act of kindness"],
    "Immaculate Conception": ["Make a blue and white Mary crown","Pray the Miraculous Medal novena prayer","Special dessert — white and blue"],
    "Our Lady of Guadalupe": ["Make a rose centerpiece","Read the story of Juan Diego","Tamales or Mexican food for dinner"],
    "Christmas — Nativity of the Lord": ["Midnight Mass or Christmas morning Mass","Place the Christ Child in the nativity","Read Luke 2 before opening gifts"],
    "Corpus Christi": ["Attend procession if available","Make a floral carpet or altar at home","Pray before the Blessed Sacrament"],
    "Sacred Heart of Jesus": ["Enthrone the Sacred Heart image in your home","First Friday Mass and Communion","Act of Consecration to the Sacred Heart"],
    "Palm Sunday": ["Bring palms home and make crosses","Read the Passion narrative together","Begin Holy Week preparations"],
    "Holy Thursday": ["Wash each other's feet","Visit the altar of repose","Read John 13 together"],
    "Good Friday": ["Fast and abstain from meat","Stations of the Cross","Silence from noon to 3pm"],
}


# ── Engine ────────────────────────────────────────────────────────────────────
def _easter(year: int) -> date:
    a = year % 19; b = year // 100; c = year % 100; d = b // 4; e = b % 4
    f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4; k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day   = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_moveable_feasts(year: int) -> dict:
    easter = _easter(year)
    feasts = {}
    def add(delta, name, color, notes=""):
        feasts[easter + timedelta(days=delta)] = (name, color, notes)
    add(-46, "Ash Wednesday", "purple", "Fast and abstinence")
    add(-7,  "Palm Sunday", "red", "Holy Week begins")
    add(-3,  "Holy Thursday", "white", "Mass of the Lord's Supper")
    add(-2,  "Good Friday", "red", "Fast and abstinence — no Mass")
    add(-1,  "Holy Saturday", "white", "Easter Vigil")
    add(0,   "Easter Sunday", "gold", "Solemnity of solemnities")
    add(1,   "Easter Monday", "white", "Octave of Easter")
    add(7,   "Divine Mercy Sunday", "white", "Second Sunday of Easter")
    add(39,  "Ascension of the Lord", "white", "Holy Day of Obligation")
    add(49,  "Pentecost Sunday", "red", "")
    add(56,  "Trinity Sunday", "white", "")
    add(60,  "Corpus Christi", "white", "Body and Blood of Christ")
    add(68,  "Sacred Heart of Jesus", "red", "")
    christmas = date(year, 12, 25)
    advent_start = christmas - timedelta(days=(christmas.weekday() + 1) % 7 + 21)
    feasts[advent_start] = ("First Sunday of Advent", "purple", "Advent begins")
    return feasts


def get_floating_liturgical_events(years: list = None) -> list:
    """Return dynamically-calculated multi-day liturgical events as calendar event dicts.

    Each entry spans multiple days so events_for_date() will include it on every
    day within the range (start <= iso <= end, all_day=True).
    """
    if years is None:
        today = date.today()
        years = [today.year, today.year + 1]
    events = []
    for year in years:
        easter = _easter(year)

        # ── Octave of Easter ─────────────────────────────────────────────────
        # Easter Monday → Divine Mercy Sunday (Easter+1 through Easter+7)
        easter_monday = easter + timedelta(days=1)
        divine_mercy  = easter + timedelta(days=7)
        events.append({
            "title":    "Octave of Easter",
            "start":    easter_monday.isoformat(),
            "end":      divine_mercy.isoformat(),
            "all_day":  True,
            "location": "",
            "notes":    "Eight days of Eastertide from Easter Monday through Divine Mercy Sunday.",
            "calendar": "Liturgical",
            "color":    "#d4af37",
        })

        # ── Holy Week ────────────────────────────────────────────────────────
        # Palm Sunday → Holy Saturday (Easter-7 through Easter-1)
        palm_sunday    = easter - timedelta(days=7)
        holy_saturday  = easter - timedelta(days=1)
        events.append({
            "title":    "Holy Week",
            "start":    palm_sunday.isoformat(),
            "end":      holy_saturday.isoformat(),
            "all_day":  True,
            "location": "",
            "notes":    "The holiest week of the liturgical year, Palm Sunday through Holy Saturday.",
            "calendar": "Liturgical",
            "color":    "#7c3aed",
        })

    return events


def get_liturgical_season(d: date) -> str:
    year = d.year
    easter        = _easter(year)
    ash_wednesday = easter - timedelta(days=46)
    palm_sunday   = easter - timedelta(days=7)
    pentecost     = easter + timedelta(days=49)
    christmas     = date(year, 12, 25)
    advent_start  = christmas - timedelta(days=(christmas.weekday() + 1) % 7 + 21)
    if d >= advent_start:   return "Advent"
    if d >= pentecost:      return "Ordinary Time"
    if d >= easter:         return "Easter"
    if d >= palm_sunday:    return "Holy Week"
    if d >= ash_wednesday:  return "Lent"
    if d >= date(year, 1, 9): return "Ordinary Time"
    if d >= date(year, 1, 1): return "Christmas"
    return "Ordinary Time"


def is_fast_day(d: date) -> bool:
    e = _easter(d.year)
    return d == e - timedelta(days=46) or d == e - timedelta(days=2)


def is_abstinence_day(d: date) -> bool:
    e = _easter(d.year)
    ash = e - timedelta(days=46)
    gf  = e - timedelta(days=2)
    return d.weekday() == 4 and ash <= d <= gf


def get_day_info(d: date) -> dict:
    moveable = get_moveable_feasts(d.year)
    key = (d.month, d.day)
    feast_name = feast_color = feast_notes = ""
    if d in moveable:
        feast_name, feast_color, feast_notes = moveable[d]
    elif key in FIXED_FEASTS:
        feast_name, feast_color, feast_notes = FIXED_FEASTS[key]
    custom = load_liturgical_custom()
    iso = d.isoformat()
    if iso in custom:
        e = custom[iso]
        if e.get("name"):  feast_name  = e["name"]
        if e.get("color"): feast_color = e["color"]
        if e.get("notes"): feast_notes = e["notes"]
    season     = get_liturgical_season(d)
    fasting    = is_fast_day(d)
    abstinence = is_abstinence_day(d)
    observances = []
    if fasting:    observances.append("Fast day")
    if abstinence: observances.append("Abstinence (no meat)")
    if feast_notes: observances.append(feast_notes)
    return {
        "date": iso, "weekday": d.strftime("%A"),
        "date_label": d.strftime("%B %d, %Y"),
        "season": season,
        "season_color": SEASON_COLORS.get(season, "#888"),
        "season_text_color": SEASON_TEXT_COLORS.get(season, "white"),
        "feast_name": feast_name, "feast_color": feast_color,
        "observances": observances, "is_fast": fasting, "is_abstinence": abstinence,
    }


def get_vestment_color(info: dict) -> tuple:
    color_key = info.get("feast_color", "").lower()
    if not color_key:
        color_key = {"Advent":"purple","Christmas":"white","Ordinary Time":"green",
                     "Lent":"purple","Holy Week":"red","Easter":"white"}.get(info.get("season",""), "green")
    return VESTMENT_COLORS.get(color_key, ("#888", "#fff"))


def is_penance_season() -> bool:
    return get_liturgical_season(date.today()) in ("Lent", "Advent", "Holy Week")


# ── UI ────────────────────────────────────────────────────────────────────────
def render_liturgical_day_card(d: date, compact=False) -> str:
    info = get_day_info(d)
    season = info["season"]
    feast_name = info["feast_name"]
    vest_bg, vest_text = get_vestment_color(info)
    color_banner = (
        f'<div style="background:{vest_bg};color:{vest_text};border-radius:10px;'
        f'padding:8px 14px;margin-bottom:10px;font-weight:bold;font-size:0.95em;">'
        f'{escape(season)}{(" — "+escape(feast_name)) if feast_name else ""}</div>'
    )
    obs_html = "".join(f"<span class='badge'>{escape(o)}</span> " for o in info["observances"])
    info_date = info["date"]
    edit_link = f"<a class='link-button' href='/liturgical/edit?date={escape(info_date)}'>Add / Edit</a>"
    if compact:
        return f"<div>{color_banner}<div class='summary-row'>{obs_html}</div><div class='link-row no-print'>{edit_link}</div></div>"
    prayers_html   = "".join(f"<li>{escape(p)}</li>" for p in SEASON_PRAYERS.get(season, []))
    activities     = FEAST_ACTIVITIES.get(feast_name, []) + SEASON_ACTIVITIES.get(season, [])
    activities_html = "".join(f"<li>{escape(a)}</li>" for a in activities[:6])
    custom      = load_liturgical_custom()
    family_note = custom.get(info_date, {}).get("family_note", "")
    readings_url  = f"https://bible.usccb.org/bible/readings/{d.strftime('%m%d%y')}.cfm"
    readings_link = f"<a class='link-button' href='{readings_url}' target='_blank'>Mass Readings (USCCB) ↗</a>"
    family_note_html = f"""
    <div class="card card-tight" style="margin-top:10px;"><h4>Family Notes</h4>
    <form method="POST" action="/liturgical-note">
        <input type="hidden" name="date" value="{escape(info_date)}">
        <textarea name="family_note" rows="3">{escape(family_note)}</textarea>
        <button type="submit">Save Note</button>
    </form></div>"""
    return f"""
    <div class="card">
        <h3>{escape(info["weekday"])} — {escape(info["date_label"])}</h3>
        {color_banner}
        <div class="summary-row" style="margin-bottom:10px;">{obs_html}</div>
        <div class="link-row no-print">{readings_link} {edit_link}</div>
        {"<h4>Prayers &amp; Devotions</h4><ul>"+prayers_html+"</ul>" if prayers_html else ""}
        {"<h4>Family Activities</h4><ul>"+activities_html+"</ul>" if activities_html else ""}
        {family_note_html}
    </div>"""


def render_liturgical_page(status_message="") -> str:
    today     = date.today()
    today_d   = today
    from html import escape as _e

    # ── Spiritual snapshot block (moved from dashboard) ───────────────────────
    season = "Ordinary Time"
    feast  = ""
    try:
        info              = get_day_info(today_d)
        season            = info.get("season", "Ordinary Time")
        feast             = info.get("feast_name", "")
        vest_bg, vest_txt = get_vestment_color(info)
    except Exception:
        vest_bg, vest_txt = "#4a7c4a", "#ffffff"

    season_badge = (
        f'<span style="display:inline-block;background:{vest_bg};color:{vest_txt};'
        f'border-radius:6px;padding:3px 12px;font-size:0.78em;font-weight:700;'
        f'letter-spacing:.06em;text-transform:uppercase;">{_e(season)}</span>'
    )
    feast_html = (
        f'<span style="font-size:0.88em;font-weight:600;color:var(--gold-light);">{_e(feast)}</span>'
        if feast else ""
    )

    # Saint of the day
    _saint_card  = ""
    _saint_quote = ""
    _saint_name  = ""
    try:
        from saint_data import get_saint_html_card, fetch_saint_data as _fsd
        _sd = _fsd(today_d)
        if _sd.get("name") and not feast:
            feast = _sd["name"]
        _saint_quote = _sd.get("quote", "")
        _saint_name  = _sd.get("name", "")
        _saint_card  = get_saint_html_card(today_d, dark=True)
        _readings_url = _sd.get("usccb_link") or f"https://bible.usccb.org/bible/readings/{today_d.strftime('%m%d%y')}.cfm"
    except Exception:
        _readings_url = f"https://bible.usccb.org/bible/readings/{today_d.strftime('%m%d%y')}.cfm"

    # Seasonal quote
    quote, attrib = "", ""
    try:
        from render_morning_anchor import _get_quote_for_day
        quote, attrib = _get_quote_for_day(season, today_d)
    except Exception:
        pass

    # Mass week label + collect
    _mass_week_label = ""
    _collect_html    = ""
    try:
        from datetime import timedelta as _tdd
        _mv      = get_moveable_feasts(today_d.year)
        _mv_prev = get_moveable_feasts(today_d.year - 1)

        def _ff(mv, name):
            return next((d for d, v in mv.items() if v[0] == name), None)

        _ash   = _ff(_mv, "Ash Wednesday")
        _east  = _ff(_mv, "Easter Sunday")
        _adv1  = _ff(_mv, "First Sunday of Advent")
        _adv1p = _ff(_mv_prev, "First Sunday of Advent")

        _ss = None
        if season == "Lent"        and _ash:  _ss = _ash
        elif season == "Holy Week" and _east: _ss = _east - _tdd(days=7)
        elif season == "Easter"    and _east: _ss = _east
        elif season == "Advent":
            _ss = _adv1 if (_adv1 and today_d >= _adv1) else _adv1p
        elif season == "Christmas":
            import datetime as _dtt; _ss = _dtt.date(today_d.year, 12, 25)
        else:
            import datetime as _dtt; _ss = _dtt.date(today_d.year, 1, 6)

        _wn = ((today_d - _ss).days // 7 + 1) if (_ss and today_d >= _ss) else 1
        _ords = ["","First","Second","Third","Fourth","Fifth","Sixth","Seventh",
                 "Eighth","Ninth","Tenth","Eleventh","Twelfth","Thirteenth",
                 "Fourteenth","Fifteenth","Sixteenth","Seventeenth","Eighteenth",
                 "Nineteenth","Twentieth","Twenty-First","Twenty-Second",
                 "Twenty-Third","Twenty-Fourth","Twenty-Fifth","Twenty-Sixth",
                 "Twenty-Seventh","Twenty-Eighth","Twenty-Ninth","Thirtieth",
                 "Thirty-First","Thirty-Second","Thirty-Third","Thirty-Fourth"]
        _ord  = _ords[_wn] if 0 < _wn < len(_ords) else str(_wn)
        _year = ["C","A","B"][today_d.year % 3]
        _mass_week_label = f"{_ord} Week of {season} \u00b7 Year {_year}"

        COLLECTS = {
            "Lent":         "Grant, O Lord, that we may begin with holy fasting this campaign of Christian service, so that, as we take up battle against spiritual evils, we may be armed with weapons of self-restraint.",
            "Advent":       "Grant your faithful, we pray, almighty God, the resolve to run forth to meet your Christ with righteous deeds at his coming, so that, gathered at his right hand, they may be worthy to possess the heavenly Kingdom.",
            "Christmas":    "O God, who wonderfully created the dignity of human nature and still more wonderfully restored it, grant, we pray, that we may share in the divinity of Christ, who humbled himself to share in our humanity.",
            "Easter":       "O God, who on this day, through your Only Begotten Son, have conquered death and unlocked for us the path to eternity, grant, we pray, that we who keep the solemnity of the Lord's Resurrection may rise up in the light of life.",
            "Holy Week":    "Almighty ever-living God, who as an example of humility for the human race to follow caused our Savior to take flesh and submit to the Cross, graciously grant that we may heed his lesson of patient suffering and so merit a share in his Resurrection.",
            "Ordinary Time":"Grant us, O Lord our God, that we may honor you with all our mind, and love everyone in truth of heart. Through our Lord Jesus Christ, your Son, who lives and reigns with you in the unity of the Holy Spirit, God, for ever and ever.",
        }
        _collect_text = COLLECTS.get(season, COLLECTS["Ordinary Time"])
        _collect_html = (
            '<div style="font-size:0.68em;font-weight:800;letter-spacing:.14em;text-transform:uppercase;'
            'color:rgba(201,164,74,0.6);margin-bottom:8px;">Collect</div>'
            '<div style="font-style:italic;font-size:0.88em;color:rgba(245,234,216,0.85);'
            'line-height:1.75;padding:12px 16px;background:rgba(255,255,255,0.05);'
            'border-radius:10px;border-left:3px solid rgba(201,164,74,0.5);">'
            + _e(_collect_text) +
            '</div>'
            '<div style="margin-top:10px;">'
            f'<a href="{_e(_readings_url)}" target="_blank" '
            'style="font-size:0.78em;color:rgba(245,234,216,0.65);'
            'border-bottom:1px solid rgba(201,164,74,0.3);text-decoration:none;">'
            'Full Mass readings \u2197</a>'
            '</div>'
        )
    except Exception:
        pass

    # Pre-compute quote block
    _quote_block = ""
    if not _saint_quote and quote:
        _quote_block = (
            '<div style="margin-top:12px;padding:12px 14px;background:rgba(255,255,255,0.05);'
            'border-radius:10px;border-left:3px solid var(--gold);">'
            f'<div style="font-size:0.92em;font-style:italic;line-height:1.65;color:var(--gold-light);">{_e(quote)}</div>'
            f'<div style="font-size:0.75em;color:rgba(245,234,216,0.55);margin-top:6px;">&mdash; {_e(attrib)}</div>'
            '</div>'
        )

    spiritual_block = f"""
<div class="card" style="margin-bottom:16px;background:linear-gradient(135deg,#1c1610,#2a1e10);
     color:var(--gold-light);border:none;">
  <div style="display:flex;align-items:center;justify-content:space-between;
              flex-wrap:wrap;gap:8px;margin-bottom:10px;">
    {season_badge}
    {feast_html}
  </div>
  {_saint_card}
  {_quote_block}
  <div style="margin-top:16px;padding-top:14px;border-top:1px solid rgba(255,255,255,0.08);">
    <div style="font-size:0.68em;font-weight:800;letter-spacing:.14em;text-transform:uppercase;
                color:rgba(201,164,74,0.7);margin-bottom:4px;">Daily Mass</div>
    <div style="font-size:0.78em;color:rgba(245,234,216,0.55);margin-bottom:10px;">
      {_e(_mass_week_label)}
    </div>
    {_collect_html}
  </div>
</div>"""

    # ── Liturgical calendar content ───────────────────────────────────────────
    today_card = render_liturgical_day_card(today)
    week_html  = ""
    for offset in range(1, 7):
        d = today + timedelta(days=offset)
        info = get_day_info(d)
        vest_bg2, vest_text2 = get_vestment_color(info)
        dot   = f'<span style="background:{vest_bg2};color:{vest_text2};border-radius:6px;padding:2px 8px;font-size:0.8em;font-weight:bold;">{escape(info["season"])}</span>'
        feast2 = f" — {escape(info['feast_name'])}" if info["feast_name"] else ""
        obs   = "".join(f"<span class='badge'>{escape(o)}</span> " for o in info["observances"])
        week_html += f"""
        <div class="card card-tight">
            <strong>{escape(info["weekday"])}, {escape(info["date_label"])}</strong> {dot}{feast2}
            <div class="summary-row" style="margin-top:4px;">{obs}</div>
            <div class="link-row" style="margin-top:4px;">
                <a class="link-button" href="/liturgical/edit?date={escape(info['date'])}">Add / Edit</a>
            </div>
        </div>"""

    upcoming = []
    for offset in range(1, 61):
        d = today + timedelta(days=offset)
        info = get_day_info(d)
        if info["feast_name"] or info["is_fast"] or info["is_abstinence"]:
            upcoming.append(info)
    upcoming_html = ""
    for info in upcoming[:12]:
        tags = "".join(f"<span class='badge'>{escape(o)}</span> " for o in info["observances"])
        vest_bg3, vest_text3 = get_vestment_color(info)
        dot3 = f'<span style="background:{vest_bg3};color:{vest_text3};border-radius:4px;padding:1px 6px;font-size:0.78em;margin-left:6px;">{escape(info["season"])}</span>'
        upcoming_html += f"""
        <div class="card card-tight">
            <strong>{escape(info["date_label"])}</strong>{dot3} — {escape(info["feast_name"] or "Observance")}
            <div class="summary-row" style="margin-top:4px;">{tags}</div>
        </div>"""

    body = f"""
    {page_header("Prayer")}
    {render_status_message(status_message)}
    {spiritual_block}
    <div class="two-col">
        <div>
            <h2>Today</h2>{today_card}
            <h2>This Week</h2>{week_html}
        </div>
        <div>
            <h2>Upcoming (next 60 days)</h2>
            {upcoming_html or "<div class='card'><p class='muted'>No major feasts upcoming.</p></div>"}
            <div class="card">
                <h2>Add or Override a Day</h2>
                <form method="POST" action="/liturgical-save">
                    <label>Date</label><input type="date" name="date" value="{today.isoformat()}">
                    <label>Feast / Saint name</label><input type="text" name="name" placeholder="e.g. St. Therese of Lisieux">
                    <label>Notes</label><input type="text" name="notes" placeholder="e.g. Family feast day">
                    <label>Vestment color (optional)</label>
                    <select name="color">
                        <option value="">— auto —</option>
                        <option value="white">White</option><option value="red">Red</option>
                        <option value="purple">Purple / Violet</option><option value="green">Green</option>
                        <option value="rose">Rose</option><option value="gold">Gold</option>
                        <option value="black">Black</option>
                    </select>
                    <button type="submit">Save</button>
                </form>
            </div>
        </div>
    </div>"""
    return html_page("Prayer", body)


def render_liturgical_edit_page(date_str: str, status_message="") -> str:
    try:
        d = date.fromisoformat(date_str)
    except Exception:
        d = date.today()
    info = get_day_info(d)
    custom   = load_liturgical_custom()
    existing = custom.get(d.isoformat(), {})
    d_iso    = d.isoformat()
    color_opts = "".join(
        f'<option value="{c}" {"selected" if existing.get("color")==c else ""}>{c.capitalize()}</option>'
        for c in ["white","red","purple","green","rose","gold","black"]
    )
    delete_btn = (
        f"<form method='POST' action='/liturgical-delete'>"
        f"<input type='hidden' name='date' value='{escape(d_iso)}'>"
        f"<button type='submit' class='ghost'>Remove Custom Entry</button></form>"
        if existing else ""
    )
    body = f"""
    {page_header(f"Edit — {info['date_label']}")}
    {render_status_message(status_message)}
    <div class="card">
        <h2>Auto-detected info</h2>
        <p><strong>Season:</strong> {escape(info["season"])}</p>
        <p><strong>Feast:</strong> {escape(info["feast_name"] or "None")}</p>
        <p><strong>Observances:</strong> {escape(", ".join(info["observances"]) or "None")}</p>
    </div>
    <div class="card">
        <h2>Your Custom Entry</h2>
        <form method="POST" action="/liturgical-save">
            <input type="hidden" name="date" value="{escape(d_iso)}">
            <label>Feast / Saint name</label>
            <input type="text" name="name" value="{escape(existing.get("name",""))}">
            <label>Notes</label>
            <input type="text" name="notes" value="{escape(existing.get("notes",""))}">
            <label>Vestment color (optional)</label>
            <select name="color"><option value="">— auto —</option>{color_opts}</select>
            <button type="submit">Save</button>
        </form>
        {delete_btn}
    </div>
    <div class="link-row"><a class="link-button" href="/liturgical">Back to Calendar</a></div>"""
    return html_page(f"Edit Liturgical — {info['date_label']}", body)