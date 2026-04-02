"""
render_5am.py — 5AM Club · Sancta Familia Edition

The Hour of Victory: 3 x 20 minutes
  Move    — physical movement
  Reflect — prayer, virtue, gratitude, journal
  Grow    — reading or learning

Routes:
  GET  /5am              — today
  GET  /5am?date=YYYY-MM-DD — specific day

Data: data/5am/YYYY-MM-DD.json
"""
import json, os
from datetime import date, timedelta
from html import escape

from render_settings import load_app_settings
from ui_helpers import html_page, top_nav, render_status_message

CLUB_DIR = "data/5am"

DEFAULT_MOVES = [
    "Walk outside", "Stretching / yoga", "Strength training",
    "Running", "Pilates", "Dance", "Bike ride", "Swimming",
]

JOURNAL_PROMPTS_BY_SEASON = {
    "Advent":       [
        "What am I waiting for with hope right now?",
        "Where can I make room — in my home, schedule, or heart — for Christ?",
        "What do I want to receive this Advent that isn't a gift I can wrap?",
    ],
    "Christmas":    [
        "What gift did God give me this year that I haven't fully received yet?",
        "Where did I see the face of Christ in my family this week?",
        "What does 'God with us' mean in my particular life today?",
    ],
    "Lent":         [
        "What is one thing I am clinging to that I could offer to God today?",
        "Where do I most need conversion right now?",
        "What small death am I being asked to accept with peace?",
    ],
    "Holy Week":    [
        "Where is the cross showing up in my life, and can I unite it to His?",
        "What would it look like to pour myself out completely today?",
        "Who in my family needs me to love them with the love of the Cross?",
    ],
    "Easter":       [
        "Where do I need to believe the resurrection is real — not just in doctrine but in my actual life?",
        "What is rising in me that I have been afraid to let grow?",
        "How is joy being asked of me today, even when it costs something?",
    ],
    "Ordinary Time": [
        "What is ordinary grace I have been overlooking?",
        "Where is God asking me to grow in faithfulness in small things?",
        "What does holiness look like in the particular texture of my day today?",
    ],
}


def _ensure_dir():
    os.makedirs(CLUB_DIR, exist_ok=True)


def load_day(d: date = None) -> dict:
    _ensure_dir()
    if d is None:
        d = date.today()
    path = f"{CLUB_DIR}/{d.isoformat()}.json"
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {
            "date": d.isoformat(),
            "move":    {"done": False, "activity": "", "minutes": 20, "note": ""},
            "reflect": {"done": False, "lauds": False, "rosary_intention": "",
                        "virtue_intention": "", "gratitude": ["","",""], "journal": "",
                        "daily_cross": ""},
            "grow":    {"done": False, "book_title": "", "book_author": "",
                        "pages": "", "topic": "", "note": ""},
            "devotions": {"fa": "", "fe": "", "ca": "", "pa": ""},
        }


def save_day(data: dict):
    _ensure_dir()
    path = f"{CLUB_DIR}/{data['date']}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _streak(today: date) -> int:
    count = 0
    d = today
    while True:
        rec = load_day(d)
        if rec.get("move",{}).get("done") or rec.get("reflect",{}).get("done") or rec.get("grow",{}).get("done"):
            count += 1
            d -= timedelta(days=1)
        else:
            break
        if count > 365:
            break
    return count


def _week_dots(today: date) -> str:
    dots = ""
    for i in range(6, -1, -1):
        d   = today - timedelta(days=i)
        rec = load_day(d)
        m   = rec.get("move",{}).get("done", False)
        r   = rec.get("reflect",{}).get("done", False)
        g   = rec.get("grow",{}).get("done", False)
        done_count = sum([m, r, g])
        if done_count == 3:
            col = "#22c55e"
        elif done_count > 0:
            col = "#f59e0b"
        else:
            col = "#e5e7eb"
        lbl = d.strftime("%a")
        is_today = (d == today)
        border = "2px solid var(--ink)" if is_today else "none"
        dots += (
            f'<div style="text-align:center;">'
            f'<div style="width:20px;height:20px;border-radius:50%;background:{col};'
            f'margin:0 auto 2px;border:{border};"></div>'
            f'<div style="font-size:0.62em;color:var(--ink-faint);">{lbl}</div>'
            f'</div>'
        )
    return dots


def _journal_prompt(season: str, d: date) -> str:
    prompts = JOURNAL_PROMPTS_BY_SEASON.get(season,
              JOURNAL_PROMPTS_BY_SEASON["Ordinary Time"])
    return prompts[d.timetuple().tm_yday % len(prompts)]


def _current_virtue() -> str:
    try:
        from render_virtues import load_personal_virtue
        pv = load_personal_virtue()
        return pv.get("current", {}).get("virtue", "")
    except Exception:
        return ""


def _goal_step_for_category(category_prefix: str) -> str:
    """Pull this week's step for a goal matching a category prefix."""
    try:
        from render_goals import get_active_goals_with_steps
        goals = get_active_goals_with_steps()
        for g in goals:
            if g.get("category","").lower().startswith(category_prefix.lower()):
                step = g.get("step","")
                if step:
                    return f'{g["title"]}: {step}'
    except Exception:
        pass
    return ""


def _current_book() -> tuple:
    """Return (title, author) from settings or last saved day."""
    settings = load_app_settings()
    title  = settings.get("5am_book_title", "")
    author = settings.get("5am_book_author", "")
    if not title:
        # Try last saved day
        try:
            files = sorted(os.listdir(CLUB_DIR), reverse=True)
            for fn in files[:7]:
                if fn.endswith(".json"):
                    with open(f"{CLUB_DIR}/{fn}") as f:
                        rec = json.load(f)
                    t = rec.get("grow",{}).get("book_title","")
                    a = rec.get("grow",{}).get("book_author","")
                    if t:
                        return t, a
        except Exception:
            pass
    return title, author


# ── Dashboard widget ──────────────────────────────────────────────────────────

def render_5am_dashboard_widget() -> str:
    today   = date.today()
    rec     = load_day(today)
    streak  = _streak(today)
    dots    = _week_dots(today)

    m_done  = rec.get("move",{}).get("done", False)
    r_done  = rec.get("reflect",{}).get("done", False)
    g_done  = rec.get("grow",{}).get("done", False)
    all_done = m_done and r_done and g_done

    def seg(label, done):
        col = "#22c55e" if done else "#e5e7eb"
        txt_col = "#166534" if done else "var(--ink-faint)"
        return (
            f'<div style="flex:1;text-align:center;padding:6px 4px;'
            f'background:{col}20;border-radius:8px;border:1.5px solid {col};">'
            f'<div style="font-size:0.72em;font-weight:700;color:{txt_col};">'
            f'{"✓ " if done else ""}{label}</div>'
            f'</div>'
        )

    streak_badge = (
        f'<span style="font-size:0.85em;font-weight:700;color:var(--brown);">'
        f'{"🔥 " + str(streak) + " day streak" if streak > 1 else ("✨ Start your streak!" if streak == 0 else "Day 1 — great start!")}'
        f'</span>'
    )

    return (
        f'<div class="card" style="margin-bottom:14px;">'
        f'<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;'
        f'text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;'
        f'display:flex;justify-content:space-between;align-items:center;">'
        f'<span>5AM Club</span>'
        f'<a href="/5am" style="font-size:0.9em;color:var(--brown);'
        f'font-weight:600;text-decoration:none;text-transform:none;">'
        f'Open &rarr;</a></div>'
        f'<div style="margin-bottom:8px;">{streak_badge}</div>'
        f'<div style="display:flex;gap:6px;margin-bottom:10px;">'
        f'{seg("Move", m_done)}{seg("Reflect", r_done)}{seg("Grow", g_done)}'
        f'</div>'
        f'<div style="display:flex;gap:6px;justify-content:space-between;">{dots}</div>'
        f'</div>'
    )


# ── Main page ─────────────────────────────────────────────────────────────────

def render_5am_page(date_str: str = None, status: str = "") -> str:
    today = date.today()
    if date_str:
        try:
            target = date.fromisoformat(date_str)
        except Exception:
            target = today
    else:
        target = today

    prev_date = (target - timedelta(days=1)).isoformat()
    next_date = (target + timedelta(days=1)).isoformat()
    is_today  = (target == today)

    rec    = load_day(target)
    streak = _streak(today)
    dots   = _week_dots(today)

    settings = load_app_settings()
    api_key  = (settings.get("anthropic_api_key", "") or
                settings.get("family_constraints", {}).get("anthropic_api_key", ""))

    # Liturgical season
    season = "Ordinary Time"
    try:
        from render_liturgical import get_liturgical_season
        season = get_liturgical_season(target)
    except Exception:
        pass

    # Current virtue
    virtue = _current_virtue()

    # Journal prompt
    journal_prompt = _journal_prompt(season, target)

    # Goal steps
    move_goal  = _goal_step_for_category("Physical")
    grow_goal  = _goal_step_for_category("Latin") or _goal_step_for_category("Creative") or _goal_step_for_category("Classical")

    # Current book
    book_title, book_author = _current_book()
    # Override with saved day values if present
    saved_book  = rec.get("grow", {}).get("book_title", "")
    saved_author= rec.get("grow", {}).get("book_author", "")
    if saved_book:
        book_title  = saved_book
        book_author = saved_author

    # ── Move section ─────────────────────────────────────────────────────────
    move      = rec.get("move", {})
    m_done    = move.get("done", False)
    m_act     = escape(move.get("activity", ""))
    m_min     = move.get("minutes", 20)
    m_note    = escape(move.get("note", ""))

    move_opts = "".join(
        f'<option value="{escape(a)}" {"selected" if m_act == a else ""}>{escape(a)}</option>'
        for a in DEFAULT_MOVES
    )

    move_goal_html = ""
    if move_goal:
        move_goal_html = (
            f'<div style="margin-top:8px;padding:8px 10px;background:var(--gold-light);'
            f'border-radius:8px;font-size:0.78em;color:var(--brown);">'
            f'<strong>Goal step:</strong> {escape(move_goal)}</div>'
        )

    move_card = _section_card(
        number="1", label="Move", minutes=20,
        color="#27ae60", done=m_done, who_id="move",
        content=(
            f'<div style="display:grid;grid-template-columns:1fr auto;gap:8px;margin-bottom:8px;">'
            f'<select id="m-activity" onchange="autoSave()"'
            f' style="padding:7px 10px;border-radius:8px;border:1.5px solid var(--border);'
            f'font-family:inherit;font-size:0.85em;">'
            f'<option value="">Choose activity...</option>{move_opts}'
            f'<option value="Other" {"selected" if m_act and m_act not in DEFAULT_MOVES else ""}>Other...</option>'
            f'</select>'
            f'<div style="display:flex;align-items:center;gap:6px;">'
            f'<input type="number" id="m-minutes" value="{m_min}" min="5" max="120"'
            f' onchange="autoSave()" '
            f'style="width:60px;padding:7px;border-radius:8px;border:1.5px solid var(--border);'
            f'font-family:inherit;font-size:0.85em;text-align:center;">'
            f'<span style="font-size:0.78em;color:var(--ink-faint);">min</span>'
            f'</div></div>'
            f'<input type="text" id="m-other" value="{m_act if m_act and m_act not in DEFAULT_MOVES else ""}"'
            f' placeholder="Describe your movement..." onchange="autoSave()"'
            f' style="width:100%;margin-bottom:6px;display:{"block" if m_act and m_act not in DEFAULT_MOVES else "none"};">'
            f'<textarea id="m-note" rows="2" placeholder="How did it feel? Any notes..."'
            f' onchange="autoSave()" style="width:100%;font-size:0.82em;resize:vertical;">'
            f'{m_note}</textarea>'
            + move_goal_html
        )
    )

    # ── Reflect section ───────────────────────────────────────────────────────
    reflect       = rec.get("reflect", {})
    r_done        = reflect.get("done", False)
    r_lauds       = reflect.get("lauds", False)
    r_rosary      = escape(reflect.get("rosary_intention", ""))
    r_virtue_int  = escape(reflect.get("virtue_intention", virtue))
    r_grat        = reflect.get("gratitude", ["","",""])
    r_journal     = escape(reflect.get("journal", ""))
    r_cross       = escape(reflect.get("daily_cross", ""))

    virtue_hint = ""
    if virtue:
        virtue_hint = (
            f'<div style="font-size:0.72em;color:var(--brown);margin-bottom:4px;">'
            f'Current virtue focus: <strong>{escape(virtue)}</strong></div>'
        )

    ai_journal_btn = ""
    if api_key:
        ai_journal_btn = (
            f'<button onclick="aiJournalPrompt()" '
            f'style="font-size:0.72em;padding:4px 10px;background:var(--parchment);'
            f'color:var(--brown);border:1px solid var(--border);border-radius:6px;'
            f'font-family:inherit;cursor:pointer;margin-bottom:6px;">'
            f'\u2728 New prompt</button>'
        )

    grat_inputs = "".join(
        f'<input type="text" id="r-grat-{i}" value="{escape(r_grat[i] if i < len(r_grat) else "")}"'
        f' placeholder="I am grateful for..." onchange="autoSave()"'
        f' style="margin-bottom:6px;">'
        for i in range(3)
    )

    reflect_card = _section_card(
        number="2", label="Reflect", minutes=20,
        color="#8b5a3c", done=r_done, who_id="reflect",
        content=(
            f'<!-- Lauds -->'
            f'<div style="display:flex;align-items:center;gap:8px;padding:8px 0;'
            f'border-bottom:1px solid var(--border-light);margin-bottom:10px;">'
            f'<input type="checkbox" id="r-lauds" {"checked" if r_lauds else ""}'
            f' onchange="autoSave()" style="width:18px;height:18px;flex-shrink:0;">'
            f'<label for="r-lauds" style="font-size:0.88em;font-weight:600;flex:1;">'
            f'Lauds / Morning Prayer</label>'
            f'<a href="https://universalis.com/lauds.htm" target="_blank"'
            f' style="font-size:0.72em;color:var(--brown);font-weight:700;text-decoration:none;">'
            f'Open &rarr;</a></div>'
            f'<!-- Rosary intention -->'
            f'<label style="font-size:0.75em;">Rosary intention</label>'
            f'<input type="text" id="r-rosary" value="{r_rosary}"'
            f' placeholder="Offer your Rosary for..." onchange="autoSave()"'
            f' style="margin-bottom:10px;">'
            f'<!-- Virtue -->'
            f'{virtue_hint}'
            f'<label style="font-size:0.75em;">Virtue intention for today</label>'
            f'<input type="text" id="r-virtue" value="{r_virtue_int}"'
            f' placeholder="How will I practice {escape(virtue or "my virtue")} today?"'
            f' onchange="autoSave()" style="margin-bottom:10px;">'
            f'<!-- Gratitude -->'
            f'<label style="font-size:0.75em;">Three gratitudes</label>'
            f'{grat_inputs}'
            f'<!-- Journal -->'
            f'<label style="font-size:0.75em;display:flex;justify-content:space-between;'
            f'align-items:center;">Morning journal {ai_journal_btn}</label>'
            f'<div id="journal-prompt" style="font-size:0.78em;font-style:italic;'
            f'color:var(--brown);margin-bottom:6px;padding:6px 10px;'
            f'background:var(--gold-light);border-radius:6px;">'
            f'\u201c{escape(journal_prompt)}\u201d</div>'
            f'<textarea id="r-journal" rows="4" placeholder="Write freely..."'
            f' onchange="autoSave()" style="width:100%;font-size:0.85em;resize:vertical;">'
            f'{r_journal}</textarea>'
            f'<!-- Daily Cross -->'
            f'<label style="font-size:0.75em;margin-top:10px;display:block;">Daily Cross — What challenge can you offer to God today?</label>'
            f'<input type="text" id="r-cross" value="{r_cross}"'
            f' placeholder="Offer it up: fatigue, difficulty, frustration..." onchange="autoSave()"'
            f' style="margin-top:4px;">'
        )
    )

    # ── Devotions section ──────────────────────────────────────────────────────
    dev_data = rec.get("devotions", {})
    dev_fa   = escape(dev_data.get("fa", ""))
    dev_fe   = escape(dev_data.get("fe", ""))
    dev_ca   = escape(dev_data.get("ca", ""))
    dev_pa   = escape(dev_data.get("pa", ""))
    devotions_card = (
        '<div class="card" style="border-left:4px solid #1c1610;margin-bottom:12px;">'
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">'
        '<div style="width:32px;height:32px;border-radius:50%;background:#1c1610;'
        'color:#f0e8c8;display:flex;align-items:center;justify-content:center;'
        'font-weight:800;font-size:0.85em;flex-shrink:0;">✦</div>'
        '<div>'
        '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;font-size:1.2rem;font-weight:600;color:var(--ink);">Devotions</div>'
        '<div style="font-size:0.72em;color:var(--ink-faint);">Family &amp; Personal</div>'
        '</div></div>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">'
        '<div>'
        '<div style="font-size:0.68em;font-weight:700;color:var(--brown);margin-bottom:4px;">FA — Family Activity</div>'
        '<input type="text" id="dev-fa" value="' + dev_fa + '" '
        'placeholder="A family activity for today..." onchange="autoSave()" '
        'style="padding:6px 10px;font-size:0.82em;border-radius:8px;border:1.5px solid var(--border);font-family:inherit;width:100%;box-sizing:border-box;">'
        '</div>'
        '<div>'
        '<div style="font-size:0.68em;font-weight:700;color:var(--brown);margin-bottom:4px;">FE — Family Evening</div>'
        '<input type="text" id="dev-fe" value="' + dev_fe + '" '
        'placeholder="Family evening intention..." onchange="autoSave()" '
        'style="padding:6px 10px;font-size:0.82em;border-radius:8px;border:1.5px solid var(--border);font-family:inherit;width:100%;box-sizing:border-box;">'
        '</div>'
        '<div>'
        '<div style="font-size:0.68em;font-weight:700;color:#1c1610;margin-bottom:4px;">CA — Catechesis Activity</div>'
        '<input type="text" id="dev-ca" value="' + dev_ca + '" '
        'placeholder="Catechesis or formation today..." onchange="autoSave()" '
        'style="padding:6px 10px;font-size:0.82em;border-radius:8px;border:1.5px solid var(--border);font-family:inherit;width:100%;box-sizing:border-box;">'
        '</div>'
        '<div>'
        '<div style="font-size:0.68em;font-weight:700;color:#1c1610;margin-bottom:4px;">PA — Prayer Activity</div>'
        '<input type="text" id="dev-pa" value="' + dev_pa + '" '
        'placeholder="Special prayer intention today..." onchange="autoSave()" '
        'style="padding:6px 10px;font-size:0.82em;border-radius:8px;border:1.5px solid var(--border);font-family:inherit;width:100%;box-sizing:border-box;">'
        '</div>'
        '</div>'
        '</div>'
    )

    # ── Grow section ──────────────────────────────────────────────────────────
    grow     = rec.get("grow", {})
    g_done   = grow.get("done", False)
    g_title  = escape(grow.get("book_title",  book_title))
    g_author = escape(grow.get("book_author", book_author))
    g_pages  = escape(str(grow.get("pages", "")))
    g_topic  = escape(grow.get("topic", ""))
    g_note   = escape(grow.get("note", ""))

    grow_goal_html = ""
    if grow_goal:
        grow_goal_html = (
            f'<div style="margin-bottom:10px;padding:8px 10px;background:var(--gold-light);'
            f'border-radius:8px;font-size:0.78em;color:var(--brown);">'
            f'<strong>Goal step:</strong> {escape(grow_goal)}</div>'
        )

    grow_card = _section_card(
        number="3", label="Grow", minutes=20,
        color="#2980b9", done=g_done, who_id="grow",
        content=(
            grow_goal_html
            + f'<label style="font-size:0.75em;">Currently reading</label>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">'
            f'<input type="text" id="g-title" value="{g_title}"'
            f' placeholder="Book title..." onchange="autoSave()">'
            f'<input type="text" id="g-author" value="{g_author}"'
            f' placeholder="Author..." onchange="autoSave()">'
            f'</div>'
            f'<div style="display:flex;gap:8px;margin-bottom:8px;">'
            f'<div style="flex:1;">'
            f'<label style="font-size:0.75em;">Pages read today</label>'
            f'<input type="number" id="g-pages" value="{g_pages}" min="0"'
            f' placeholder="0" onchange="autoSave()">'
            f'</div>'
            f'<div style="flex:2;">'
            f'<label style="font-size:0.75em;">OR learning focus</label>'
            f'<input type="text" id="g-topic" value="{g_topic}"'
            f' placeholder="Latin, theology, skill..." onchange="autoSave()">'
            f'</div></div>'
            f'<textarea id="g-note" rows="2" placeholder="Key insight or takeaway..."'
            f' onchange="autoSave()" style="width:100%;font-size:0.82em;resize:vertical;">'
            f'{g_note}</textarea>'
        )
    )

    # ── History strip & stats ─────────────────────────────────────────────────
    total_complete = 0
    for i in range(30):
        d = today - timedelta(days=i)
        r = load_day(d)
        if r.get("move",{}).get("done") and r.get("reflect",{}).get("done") and r.get("grow",{}).get("done"):
            total_complete += 1

    streak_badge = ""
    if streak >= 7:
        streak_badge = f'<span style="font-size:1.1em;">🏆</span>'
    elif streak >= 3:
        streak_badge = f'<span style="font-size:1.1em;">🔥</span>'
    else:
        streak_badge = f'<span style="font-size:1.1em;">✨</span>'

    date_label = target.strftime("%A, %B %-d") + (" — Today" if is_today else "")

    rec_js = json.dumps(rec)

    body = top_nav() + render_status_message(status) + f"""
<!-- Header -->
<div style="display:flex;align-items:flex-start;justify-content:space-between;
            flex-wrap:wrap;gap:8px;padding-top:4px;margin-bottom:16px;">
  <div>
    <div style="font-family:'Cormorant Garamond',Georgia,serif;
                font-size:2rem;font-weight:600;color:var(--ink);">5AM Club</div>
    <div style="font-size:0.85em;color:var(--ink-muted);margin-top:2px;">
      {escape(date_label)} &middot; {escape(season)}
    </div>
  </div>
  <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
    <a href="/5am?date={prev_date}"
       style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;
              font-size:0.82em;text-decoration:none;color:var(--ink);">&larr;</a>
    {"" if is_today else '<a href="/5am" style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);">Today</a>'}
    {'<a href="/5am?date=' + next_date + '" style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);">&rarr;</a>' if not is_today else ''}
    <button onclick="saveAll()"
            style="padding:7px 16px;background:var(--ink);color:var(--gold-light);
                   border:none;border-radius:8px;font-size:0.82em;font-weight:700;
                   font-family:inherit;cursor:pointer;">Save</button>
  </div>
</div>
<div id="save-status" style="font-size:0.82em;color:#22c55e;min-height:16px;margin-bottom:8px;"></div>

<!-- Streak + 7-day -->
<div class="card" style="margin-bottom:14px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
    <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.2rem;font-weight:600;">
      {streak_badge} {streak} day{"s" if streak != 1 else ""} strong
    </div>
    <div style="font-size:0.78em;color:var(--ink-faint);">{total_complete}/30 days this month</div>
  </div>
  <div style="display:flex;gap:8px;justify-content:space-between;">{dots}</div>
</div>

<!-- The three blocks -->
{move_card}
{reflect_card}
{grow_card}
{devotions_card}

<!-- Navigation -->
<div style="display:flex;gap:8px;flex-wrap:wrap;padding:8px 0;">
  <a href="/virtues/me" style="font-size:0.82em;color:var(--brown);font-weight:700;text-decoration:none;">Virtue focus &rarr;</a>
  <span style="color:var(--border);">|</span>
  <a href="/plan-week" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">Plan my week &rarr;</a>
</div>

<script>
var _date = '{escape(target.isoformat())}';
var _rec  = {rec_js};
var _saveTimer = null;

function autoSave() {{
  clearTimeout(_saveTimer);
  _saveTimer = setTimeout(saveAll, 1000);
}}

function saveAll() {{
  // Gather move
  var mAct = document.getElementById('m-activity');
  var mOther = document.getElementById('m-other');
  var mMin = document.getElementById('m-minutes');
  var mNote = document.getElementById('m-note');
  var mDone = document.getElementById('done-move');
  _rec.move = {{
    done:     mDone ? mDone.checked : _rec.move.done,
    activity: (mAct && mAct.value === 'Other') ? (mOther ? mOther.value : '') : (mAct ? mAct.value : ''),
    minutes:  mMin  ? parseInt(mMin.value) || 20 : 20,
    note:     mNote ? mNote.value : '',
  }};
  // Gather reflect
  var rLauds   = document.getElementById('r-lauds');
  var rRosary  = document.getElementById('r-rosary');
  var rVirtue  = document.getElementById('r-virtue');
  var rJournal = document.getElementById('r-journal');
  var rDone    = document.getElementById('done-reflect');
  var grats    = [0,1,2].map(function(i){{
    var el = document.getElementById('r-grat-' + i);
    return el ? el.value : '';
  }});
  var rCross = document.getElementById('r-cross');
  _rec.reflect = {{
    done:              rDone    ? rDone.checked    : _rec.reflect.done,
    lauds:             rLauds   ? rLauds.checked   : false,
    rosary_intention:  rRosary  ? rRosary.value    : '',
    virtue_intention:  rVirtue  ? rVirtue.value    : '',
    gratitude:         grats,
    journal:           rJournal ? rJournal.value   : '',
    daily_cross:       rCross   ? rCross.value     : '',
  }};
  // Gather devotions
  var dFa = document.getElementById('dev-fa');
  var dFe = document.getElementById('dev-fe');
  var dCa = document.getElementById('dev-ca');
  var dPa = document.getElementById('dev-pa');
  _rec.devotions = {{
    fa: dFa ? dFa.value : '',
    fe: dFe ? dFe.value : '',
    ca: dCa ? dCa.value : '',
    pa: dPa ? dPa.value : '',
  }};
  // Gather grow
  var gTitle  = document.getElementById('g-title');
  var gAuthor = document.getElementById('g-author');
  var gPages  = document.getElementById('g-pages');
  var gTopic  = document.getElementById('g-topic');
  var gNote   = document.getElementById('g-note');
  var gDone   = document.getElementById('done-grow');
  _rec.grow = {{
    done:        gDone   ? gDone.checked        : _rec.grow.done,
    book_title:  gTitle  ? gTitle.value         : '',
    book_author: gAuthor ? gAuthor.value        : '',
    pages:       gPages  ? (gPages.value || '') : '',
    topic:       gTopic  ? gTopic.value         : '',
    note:        gNote   ? gNote.value          : '',
  }};

  fetch('/5am-save', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'date=' + encodeURIComponent(_date) +
          '&data=' + encodeURIComponent(JSON.stringify(_rec))
  }}).then(function() {{
    var el = document.getElementById('save-status');
    if (el) {{ el.textContent = 'Saved \u2713'; setTimeout(function(){{ el.textContent=''; }}, 2000); }}
    // Update done badges
    ['move','reflect','grow'].forEach(function(sec) {{
      var cb    = document.getElementById('done-' + sec);
      var badge = document.getElementById('badge-' + sec);
      if (cb && badge) {{
        badge.style.background  = cb.checked ? '#22c55e' : 'var(--border)';
        badge.textContent       = cb.checked ? '\u2713 Done' : 'Mark done';
        badge.style.color       = cb.checked ? 'white' : 'var(--ink-muted)';
      }}
    }});
  }});
}}

// Show/hide "other" activity input
var mActSel = document.getElementById('m-activity');
if (mActSel) {{
  mActSel.addEventListener('change', function() {{
    var other = document.getElementById('m-other');
    if (other) other.style.display = this.value === 'Other' ? 'block' : 'none';
  }});
}}

function aiJournalPrompt() {{
  fetch('/ai-journal-prompt', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'season=' + encodeURIComponent('{escape(season)}') +
          '&virtue=' + encodeURIComponent('{escape(virtue)}')
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    var el = document.getElementById('journal-prompt');
    if (el && d.prompt) el.textContent = '\u201c' + d.prompt + '\u201d';
  }});
}}
</script>
"""
    return html_page("5AM Club \u00b7 " + date_label, body)


# ── Section card builder ──────────────────────────────────────────────────────

def _section_card(number, label, minutes, color, done, who_id, content):
    done_bg  = "#22c55e" if done else "var(--border)"
    done_txt = "\u2713 Done" if done else "Mark done"
    done_col = "white" if done else "var(--ink-muted)"
    return (
        f'<div class="card" style="border-left:4px solid {color};margin-bottom:12px;">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'margin-bottom:12px;">'
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'<div style="width:32px;height:32px;border-radius:50%;background:{color};'
        f'color:white;display:flex;align-items:center;justify-content:center;'
        f'font-weight:800;font-size:0.85em;flex-shrink:0;">{number}</div>'
        f'<div>'
        f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        f'font-size:1.2rem;font-weight:600;color:var(--ink);">{label}</div>'
        f'<div style="font-size:0.72em;color:var(--ink-faint);">{minutes} minutes</div>'
        f'</div></div>'
        f'<label style="display:flex;align-items:center;gap:6px;cursor:pointer;">'
        f'<input type="checkbox" id="done-{who_id}" {"checked" if done else ""}'
        f' onchange="autoSave()" style="display:none;">'
        f'<span id="badge-{who_id}" onclick="document.getElementById(\'done-{who_id}\').click();autoSave()"'
        f' style="padding:5px 14px;border-radius:20px;font-size:0.78em;font-weight:700;'
        f'cursor:pointer;background:{done_bg};color:{done_col};">{done_txt}</span>'
        f'</label>'
        f'</div>'
        f'{content}'
        f'</div>'
    )