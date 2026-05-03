"""
render_virtues.py — Virtue Tracker for Sancta Familia

Pages:
  /virtues              — family dashboard
  /virtues/me           — Mom's personal virtue focus
  /virtues/family       — family virtue of the month
  /virtues/child/NAME   — per-child virtue (age-adapted)

Data:
  data/virtues/personal.json
  data/virtues/family.json
  data/virtues/children/CHILD.json
"""
import json, os, uuid
from datetime import date, timedelta
from html import escape

from config import CHILDREN, child_color
from render_settings import load_app_settings
from ui_helpers import html_page, top_nav, render_status_message
from safe_utils import safe_save_json

VIRTUE_DIR    = "data/virtues"
CHILDREN_DIR  = "data/virtues/children"

# ── Virtue library (built-in seed, AI enriches on demand) ────────────────────
VIRTUE_LIBRARY = [
    "Prudence", "Justice", "Fortitude", "Temperance",
    "Faith", "Hope", "Charity", "Humility", "Patience",
    "Diligence", "Chastity", "Kindness", "Gratitude",
    "Obedience", "Generosity", "Purity of Heart",
    "Meekness", "Zeal", "Simplicity", "Magnanimity",
]

# Liturgical season → suggested virtue
SEASON_VIRTUES = {
    "Advent":       ["Hope", "Patience", "Simplicity"],
    "Christmas":    ["Gratitude", "Charity", "Generosity"],
    "Lent":         ["Temperance", "Humility", "Diligence"],
    "Holy Week":    ["Fortitude", "Faith", "Obedience"],
    "Easter":       ["Joy", "Zeal", "Charity"],
    "Ordinary Time":["Prudence", "Justice", "Kindness"],
}

# Age-band labels
def age_band(age_years):
    if age_years is None: return "adult"
    if age_years < 4:     return "toddler"
    if age_years <= 7:    return "young_child"
    if age_years <= 11:   return "child"
    if age_years <= 15:   return "teen"
    return "young_adult"


def child_age(child_name):
    """Return integer age (years) or None."""
    try:
        settings = load_app_settings()
        bdays    = settings.get("child_birthdays", {})
        dob_str  = bdays.get(child_name, "")
        if not dob_str:
            return None
        dob = date.fromisoformat(dob_str)
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age
    except Exception:
        return None


# ── Data helpers ──────────────────────────────────────────────────────────────

def _ensure_dirs():
    os.makedirs(VIRTUE_DIR,   exist_ok=True)
    os.makedirs(CHILDREN_DIR, exist_ok=True)


def load_personal_virtue():
    _ensure_dirs()
    try:
        with open(f"{VIRTUE_DIR}/personal.json") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"current": None, "history": []}
        return data
    except Exception:
        return {"current": None, "history": []}


def save_personal_virtue(data):
    safe_save_json(f"{VIRTUE_DIR}/personal.json", data)


def load_family_virtue():
    _ensure_dirs()
    try:
        with open(f"{VIRTUE_DIR}/family.json") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"current": None, "history": []}
        return data
    except Exception:
        return {"current": None, "history": []}


def save_family_virtue(data):
    safe_save_json(f"{VIRTUE_DIR}/family.json", data)


def load_child_virtue(child_name):
    _ensure_dirs()
    safe = child_name.replace(" ", "_")
    try:
        with open(f"{CHILDREN_DIR}/{safe}.json") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"current": None, "history": []}
        return data
    except Exception:
        return {"current": None, "history": []}


def save_child_virtue(child_name, data):
    safe = child_name.replace(" ", "_")
    safe_save_json(f"{CHILDREN_DIR}/{safe}.json", data)


def _current_season():
    try:
        from render_liturgical import get_liturgical_season
        return get_liturgical_season(date.today())
    except Exception:
        return "Ordinary Time"


def _api_key():
    settings = load_app_settings()
    return (settings.get("anthropic_api_key", "") or
            settings.get("family_constraints", {}).get("anthropic_api_key", ""))


# ── AI content generation (called server-side for initial load) ───────────────

def _call_claude(prompt, max_tokens=800):
    import urllib.request as _ur
    api_key = _api_key()
    if not api_key:
        return None
    req_body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = _ur.Request(
        "https://api.anthropic.com/v1/messages",
        data=req_body,
        headers={"Content-Type": "application/json", "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"}
    )
    with _ur.urlopen(req, timeout=25) as resp:
        result = json.loads(resp.read())
    raw = result["content"][0]["text"].strip()
    raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(raw)


def generate_virtue_content(virtue, who="adult", age_band_str="adult", season="Ordinary Time"):
    """
    Returns dict:
      definition, thomistic_note, practices (list), saint_name,
      saint_story, daily_prompt, examen_question, morning_encouragement
    """
    depth_map = {
        "toddler":     "a 3-4 year old child. Use 1 simple sentence. One fun practice.",
        "young_child": "a 5-7 year old. Simple words, 2 short sentences, 2 easy practices.",
        "child":       "an 8-11 year old. Clear explanation, 3 practices, saint story in 3 sentences.",
        "teen":        "a 12-15 year old. Fuller meaning, 3-4 practices, saint story with detail and personal challenge.",
        "young_adult": "a 16-18 year old. Near-adult depth, philosophical dimension, personal application.",
        "adult":       "a Catholic adult woman (homeschooling mom). Rich theological depth, practical home application, contemplative dimension.",
    }
    depth = depth_map.get(age_band_str, depth_map["adult"])
    who_label = who if who != "adult" else "Mom"

    prompt = (
        f"You are a Catholic virtue educator. Create virtue formation content for {who_label}.\n"
        f"Virtue: {virtue}\n"
        f"Liturgical season: {season}\n"
        f"Audience: {depth}\n\n"
        f"Return ONLY valid JSON with these exact keys:\n"
        f"- definition: string (age-appropriate explanation)\n"
        f"- thomistic_note: string (brief Aquinas/classical insight, adult only; empty string for children)\n"
        f"- practices: array of 2-5 strings (concrete home practices, age-appropriate)\n"
        f"- saint_name: string (one saint known for this virtue)\n"
        f"- saint_story: string (story about saint practicing this virtue, age-appropriate length)\n"
        f"- daily_prompt: string (morning focus question or intention, age-appropriate)\n"
        f"- examen_question: string (evening reflection question, age-appropriate)\n"
        f"- morning_encouragement: string (one warm sentence of encouragement)\n"
        f"Keep all text age-appropriate. No markdown formatting in strings."
    )
    try:
        result = _call_claude(prompt, max_tokens=900)
        return result
    except Exception:
        return _fallback_content(virtue, age_band_str)


def _fallback_content(virtue, age_band_str="adult"):
    practices_adult = [
        f"Begin each morning by asking God for the grace to practice {virtue} today.",
        f"When you feel the opposite of {virtue} arising, pause and offer a brief prayer.",
        f"At dinner, share one moment today where you saw {virtue} in yourself or another.",
        "Read one paragraph from a saint who exemplified this virtue before bed.",
    ]
    practices_child = [
        f"Try to practice {virtue} once today and tell someone about it.",
        "Ask a saint for help when it feels hard.",
    ]
    practices = practices_child if age_band_str in ("toddler","young_child","child") else practices_adult
    return {
        "definition":           f"{virtue} is a good habit that helps us become more like God.",
        "thomistic_note":       "",
        "practices":            practices,
        "saint_name":           "St. Thérèse of Lisieux",
        "saint_story":          f"St. Thérèse practiced {virtue} in small, hidden ways every day.",
        "daily_prompt":         f"How can I practice {virtue} today?",
        "examen_question":      f"Did I practice {virtue} today? When was it hard?",
        "morning_encouragement": f"You are growing in {virtue} — one small act at a time.",
    }


# ── Shared card builder ───────────────────────────────────────────────────────

def _virtue_card(virtue_data, who_label, who_id, color_bg="#8b5a3c",
                 show_checkin=True, age_band_str="adult"):
    """Render a full virtue focus card."""
    if not virtue_data:
        return ""

    virtue  = escape(virtue_data.get("virtue", ""))
    content = virtue_data.get("content", {})
    started = escape(virtue_data.get("started", ""))
    checkins = virtue_data.get("checkins", [])

    defn        = escape(content.get("definition", ""))
    thomas      = escape(content.get("thomistic_note", ""))
    practices   = content.get("practices", [])
    saint_name  = escape(content.get("saint_name", ""))
    saint_story = escape(content.get("saint_story", ""))
    daily_p     = escape(content.get("daily_prompt", ""))
    examen_q    = escape(content.get("examen_question", ""))
    encourage   = escape(content.get("morning_encouragement", ""))

    practice_items = "".join(
        f'<li style="margin-bottom:6px;font-size:0.85em;line-height:1.5;">{escape(p)}</li>'
        for p in practices
    )

    thomas_block = ""
    if thomas and age_band_str == "adult":
        thomas_block = (
            f'<div style="margin:10px 0;padding:10px 12px;'
            f'background:rgba(139,90,60,0.07);border-left:3px solid {color_bg};'
            f'border-radius:0 8px 8px 0;">'
            f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;'
            f'text-transform:uppercase;color:{color_bg};margin-bottom:4px;">Classical Insight</div>'
            f'<div style="font-size:0.82em;font-style:italic;color:var(--ink);line-height:1.6;">'
            f'{thomas}</div></div>'
        )

    saint_block = ""
    if saint_name:
        saint_block = (
            f'<div style="margin:12px 0;padding:12px;background:var(--gold-light);'
            f'border-radius:10px;">'
            f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;'
            f'text-transform:uppercase;color:var(--brown);margin-bottom:5px;">'
            f'\u271d Saint Exemplar</div>'
            f'<div style="font-weight:700;font-size:0.88em;margin-bottom:4px;">{saint_name}</div>'
            f'<div style="font-size:0.82em;line-height:1.6;color:var(--ink);">{saint_story}</div>'
            f'</div>'
        )

    prompts_block = ""
    if daily_p or examen_q:
        prompts_block = (
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;">'
        )
        if daily_p:
            prompts_block += (
                f'<div style="padding:10px;background:#f0fdf4;border-radius:8px;">'
                f'<div style="font-size:0.65em;font-weight:800;letter-spacing:.1em;'
                f'text-transform:uppercase;color:#166534;margin-bottom:4px;">\u2600\ufe0f Morning</div>'
                f'<div style="font-size:0.82em;color:var(--ink);line-height:1.5;">{daily_p}</div>'
                f'</div>'
            )
        if examen_q:
            prompts_block += (
                f'<div style="padding:10px;background:#faf5ff;border-radius:8px;">'
                f'<div style="font-size:0.65em;font-weight:800;letter-spacing:.1em;'
                f'text-transform:uppercase;color:#6b21a8;margin-bottom:4px;">\U0001F319 Evening Examen</div>'
                f'<div style="font-size:0.82em;color:var(--ink);line-height:1.5;">{examen_q}</div>'
                f'</div>'
            )
        prompts_block += '</div>'

    # Checkin strip (last 7 days)
    checkin_strip = ""
    if show_checkin:
        today = date.today()
        checkin_map = {c.get("date",""):c.get("rating",0) for c in checkins}
        dots = ""
        for i in range(6, -1, -1):
            d  = (today - timedelta(days=i)).isoformat()
            r  = checkin_map.get(d, 0)
            col = "#22c55e" if r >= 4 else "#f59e0b" if r >= 2 else "#e5e7eb"
            lbl = (today - timedelta(days=i)).strftime("%a")
            dots += (
                f'<div style="text-align:center;">'
                f'<div style="width:18px;height:18px;border-radius:50%;background:{col};'
                f'margin:0 auto 2px;"></div>'
                f'<div style="font-size:0.6em;color:var(--ink-faint);">{lbl}</div>'
                f'</div>'
            )
        today_str = today.isoformat()
        today_rating = checkin_map.get(today_str, 0)
        stars = "".join(
            f'<button onclick="rateVirtue(\'{escape(who_id)}\',{i})" '
            f'style="background:none;border:none;cursor:pointer;font-size:1.3em;'
            f'color:{"#f59e0b" if i <= today_rating else "#d1d5db"};">'
            f'&#9733;</button>'
            for i in range(1, 6)
        )
        checkin_strip = (
            f'<div style="margin-top:12px;padding-top:10px;'
            f'border-top:1px solid var(--border-light);">'
            f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;'
            f'text-transform:uppercase;color:var(--ink-faint);margin-bottom:6px;">7-Day Practice</div>'
            f'<div style="display:flex;gap:8px;justify-content:space-between;margin-bottom:10px;">'
            f'{dots}</div>'
            f'<div style="font-size:0.72em;color:var(--ink-faint);margin-bottom:4px;">Today\'s rating</div>'
            f'<div style="display:flex;align-items:center;gap:4px;">'
            f'{stars}'
            f'<input type="text" id="note-{escape(who_id)}" '
            f'placeholder="Brief reflection..." '
            f'style="flex:1;margin-left:8px;padding:5px 8px;font-size:0.78em;'
            f'border-radius:8px;border:1px solid var(--border);font-family:inherit;">'
            f'<button onclick="saveCheckin(\'{escape(who_id)}\')" '
            f'style="padding:5px 12px;background:var(--ink);color:var(--gold-light);'
            f'border:none;border-radius:8px;font-size:0.75em;font-family:inherit;cursor:pointer;">'
            f'Save</button>'
            f'</div></div>'
        )

    encourage_block = ""
    if encourage:
        encourage_block = (
            f'<div style="padding:8px 12px;background:linear-gradient(135deg,#1c1610,#2a1e10);'
            f'border-radius:8px;margin-bottom:10px;">'
            f'<div style="font-size:0.82em;font-style:italic;color:var(--gold-light);'
            f'line-height:1.5;">\u201c{encourage}\u201d</div>'
            f'</div>'
        )

    started_label = f' <span style="font-size:0.7em;color:var(--ink-faint);font-weight:400;">since {started}</span>' if started else ""

    return (
        f'<div class="card" style="border-left:4px solid {color_bg};">'
        f'<div style="display:flex;align-items:flex-start;justify-content:space-between;'
        f'margin-bottom:10px;">'
        f'<div>'
        f'<div style="font-size:0.7em;font-weight:800;letter-spacing:.12em;'
        f'text-transform:uppercase;color:{color_bg};margin-bottom:3px;">'
        f'{escape(who_label)} &middot; Current Virtue</div>'
        f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        f'font-size:1.5rem;font-weight:600;color:var(--ink);">'
        f'{virtue}{started_label}</div>'
        f'</div>'
        f'<a href="/virtues/{escape(who_id)}" '
        f'style="font-size:0.75em;color:{color_bg};font-weight:700;text-decoration:none;">'
        f'Full view &rarr;</a>'
        f'</div>'
        f'{encourage_block}'
        f'<div style="font-size:0.88em;line-height:1.65;color:var(--ink);margin-bottom:8px;">'
        f'{defn}</div>'
        f'{thomas_block}'
        f'<div style="margin:10px 0;">'
        f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;'
        f'text-transform:uppercase;color:var(--ink-faint);margin-bottom:6px;">'
        f'Practices at Home</div>'
        f'<ul style="margin:0;padding-left:18px;">{practice_items}</ul>'
        f'</div>'
        f'{saint_block}'
        f'{prompts_block}'
        f'{checkin_strip}'
        f'</div>'
    )


# ── Dashboard widget (small) ──────────────────────────────────────────────────

def render_virtue_dashboard_widget():
    """Small widget for main dashboard showing current virtues."""
    personal = load_personal_virtue()
    family   = load_family_virtue()

    p_virtue = personal.get("current", {}).get("virtue", "")
    f_virtue = family.get("current", {}).get("virtue", "")

    rows = ""
    if f_virtue:
        rows += (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:5px 0;border-bottom:1px solid var(--border-light);">'
            f'<div style="font-size:0.78em;font-weight:600;color:var(--brown);">'
            f'\U0001f3e0 Family</div>'
            f'<div style="font-size:0.82em;color:var(--ink);font-weight:700;">{escape(f_virtue)}</div>'
            f'<a href="/virtues/family" style="font-size:0.7em;color:var(--ink-faint);text-decoration:none;">view &rarr;</a>'
            f'</div>'
        )
    if p_virtue:
        rows += (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:5px 0;border-bottom:1px solid var(--border-light);">'
            f'<div style="font-size:0.78em;font-weight:600;color:var(--brown);">'
            f'\u2764 Mom</div>'
            f'<div style="font-size:0.82em;color:var(--ink);font-weight:700;">{escape(p_virtue)}</div>'
            f'<a href="/virtues/me" style="font-size:0.7em;color:var(--ink-faint);text-decoration:none;">view &rarr;</a>'
            f'</div>'
        )
    for child in CHILDREN:
        cdata    = load_child_virtue(child)
        c_virtue = cdata.get("current", {}).get("virtue", "")
        c_bg     = child_color(child, "bg")
        c_id     = child.replace(" ", "_")
        if c_virtue:
            rows += (
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:5px 0;border-bottom:1px solid var(--border-light);">'
                f'<div style="font-size:0.78em;font-weight:600;color:{c_bg};">'
                f'{escape(child)}</div>'
                f'<div style="font-size:0.82em;color:var(--ink);font-weight:700;">{escape(c_virtue)}</div>'
                f'<a href="/virtues/child/{escape(c_id)}" '
                f'style="font-size:0.7em;color:var(--ink-faint);text-decoration:none;">view &rarr;</a>'
                f'</div>'
            )

    if not rows:
        rows = (
            '<p style="font-size:0.82em;color:var(--ink-faint);">'
            'No virtues set yet.</p>'
        )

    return (
        f'<div class="card" style="margin-bottom:14px;">'
        f'<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;'
        f'text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;'
        f'display:flex;justify-content:space-between;align-items:center;">'
        f'<span>\u271d Virtue Focus</span>'
        f'<a href="/virtues" style="font-size:0.9em;color:var(--brown);'
        f'font-weight:600;text-decoration:none;text-transform:none;">'
        f'Manage &rarr;</a></div>'
        f'{rows}'
        f'</div>'
    )


# ── Main dashboard (/virtues) ─────────────────────────────────────────────────

def render_virtues_dashboard(status=""):
    personal = load_personal_virtue()
    family   = load_family_virtue()
    season   = _current_season()

    p_current = personal.get("current")
    f_current = family.get("current")

    # Summary cards
    cards_html = ""

    # Family card (compact)
    if f_current:
        f_v = escape(f_current.get("virtue",""))
        f_content = f_current.get("content",{})
        f_defn = escape(f_content.get("definition",""))
        cards_html += (
            f'<div class="card" style="border-left:4px solid var(--brown);margin-bottom:12px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
            f'<div>'
            f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;'
            f'text-transform:uppercase;color:var(--brown);">\U0001f3e0 Family Virtue</div>'
            f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
            f'font-size:1.4rem;font-weight:600;">{f_v}</div>'
            f'</div>'
            f'<a href="/virtues/family" style="padding:7px 14px;background:var(--ink);'
            f'color:var(--gold-light);border-radius:8px;text-decoration:none;'
            f'font-size:0.78em;font-weight:700;">Open &rarr;</a>'
            f'</div>'
            f'<div style="font-size:0.82em;color:var(--ink-muted);">{f_defn[:120]}{"..." if len(f_defn)>120 else ""}</div>'
            f'</div>'
        )
    else:
        cards_html += (
            f'<div class="card" style="border-left:4px solid var(--border);margin-bottom:12px;">'
            f'<div style="font-size:0.72em;color:var(--ink-faint);margin-bottom:8px;">\U0001f3e0 Family Virtue</div>'
            f'<p style="font-size:0.85em;color:var(--ink-faint);">No family virtue set for this month.</p>'
            f'<a href="/virtues/family" style="font-size:0.85em;color:var(--brown);font-weight:700;text-decoration:none;">'
            f'Set family virtue &rarr;</a>'
            f'</div>'
        )

    # Mom card (compact)
    if p_current:
        p_v     = escape(p_current.get("virtue",""))
        p_enc   = escape(p_current.get("content",{}).get("morning_encouragement",""))
        cards_html += (
            f'<div class="card" style="border-left:4px solid #8b5a3c;margin-bottom:12px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
            f'<div>'
            f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;'
            f'text-transform:uppercase;color:#8b5a3c;">\u2764 Mom\'s Virtue</div>'
            f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
            f'font-size:1.4rem;font-weight:600;">{p_v}</div>'
            f'</div>'
            f'<a href="/virtues/me" style="padding:7px 14px;background:var(--ink);'
            f'color:var(--gold-light);border-radius:8px;text-decoration:none;'
            f'font-size:0.78em;font-weight:700;">Open &rarr;</a>'
            f'</div>'
            + ('<div style="font-size:0.82em;color:var(--ink-muted);font-style:italic;">' + p_enc + '</div>' if p_enc else '')
            + '</div>'
        )
    else:
        cards_html += (
            f'<div class="card" style="border-left:4px solid var(--border);margin-bottom:12px;">'
            f'<div style="font-size:0.72em;color:var(--ink-faint);margin-bottom:8px;">\u2764 Mom\'s Virtue</div>'
            f'<p style="font-size:0.85em;color:var(--ink-faint);">No personal virtue set.</p>'
            f'<a href="/virtues/me" style="font-size:0.85em;color:var(--brown);font-weight:700;text-decoration:none;">'
            f'Choose my virtue &rarr;</a>'
            f'</div>'
        )

    # Children cards
    for child in CHILDREN:
        cdata    = load_child_virtue(child) or {"current": None, "history": []}
        c_v      = (cdata.get("current") or {}).get("virtue","")
        c_bg     = child_color(child, "bg")
        c_age    = child_age(child)
        c_id     = child.replace(" ","_")
        age_lbl  = f"Age {c_age}" if c_age is not None else ""
        c_defn   = escape((cdata.get("current") or {}).get("content",{}).get("definition",""))

        if c_v:
            cards_html += (
                f'<div class="card" style="border-left:4px solid {c_bg};margin-bottom:12px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
                f'<div>'
                f'<div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;'
                f'text-transform:uppercase;color:{c_bg};">{escape(child)} {age_lbl}</div>'
                f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
                f'font-size:1.4rem;font-weight:600;">{escape(c_v)}</div>'
                f'</div>'
                f'<a href="/virtues/child/{escape(c_id)}" style="padding:7px 14px;background:var(--ink);'
                f'color:var(--gold-light);border-radius:8px;text-decoration:none;'
                f'font-size:0.78em;font-weight:700;">Open &rarr;</a>'
                f'</div>'
                + ('<div style="font-size:0.82em;color:var(--ink-muted);">' + c_defn[:100] + ("..." if len(c_defn)>100 else "") + '</div>' if c_defn else '')
                + '</div>'
            )
        else:
            cards_html += (
                f'<div class="card" style="border-left:4px solid var(--border);margin-bottom:12px;">'
                f'<div style="font-size:0.72em;color:{c_bg};font-weight:700;margin-bottom:6px;">'
                f'{escape(child)}</div>'
                f'<p style="font-size:0.85em;color:var(--ink-faint);">No virtue set yet.</p>'
                f'<a href="/virtues/child/{escape(c_id)}" '
                f'style="font-size:0.85em;color:var(--brown);font-weight:700;text-decoration:none;">'
                f'Choose virtue &rarr;</a>'
                f'</div>'
            )

    # Season suggestion strip
    suggestions = SEASON_VIRTUES.get(season, ["Prudence","Charity","Humility"])
    sugg_btns = "".join(
        f'<a href="/virtues/me?virtue={escape(v)}" '
        f'style="padding:5px 12px;background:var(--gold-light);color:var(--brown);'
        f'border-radius:20px;font-size:0.78em;font-weight:700;text-decoration:none;'
        f'border:1px solid var(--gold-mid);">{escape(v)}</a>'
        for v in suggestions
    )

    body = top_nav() + render_status_message(status) + f"""
<div style="display:flex;align-items:flex-start;justify-content:space-between;
            flex-wrap:wrap;gap:8px;padding-top:4px;margin-bottom:16px;">
  <div>
    <div style="font-family:'Cormorant Garamond',Georgia,serif;
                font-size:2rem;font-weight:600;color:var(--ink);">Virtue Tracker</div>
    <div style="font-size:0.85em;color:var(--ink-muted);margin-top:2px;">
      {escape(season)} &middot; Growing in holiness together
    </div>
  </div>
</div>

<div style="padding:10px 14px;background:var(--gold-light);border-radius:10px;
            margin-bottom:16px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
              color:var(--brown);">{escape(season)} suggestions</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;">{sugg_btns}</div>
</div>

{cards_html}

<div class="card" style="margin-bottom:14px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:10px;">Quick Set</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;">
    <a href="/virtues/me" style="padding:8px 16px;background:var(--ink);color:var(--gold-light);
       border-radius:8px;text-decoration:none;font-size:0.82em;font-weight:600;">Mom's virtue</a>
    <a href="/virtues/family" style="padding:8px 16px;background:var(--ink);color:var(--gold-light);
       border-radius:8px;text-decoration:none;font-size:0.82em;font-weight:600;">Family virtue</a>
    {"".join(
        '<a href="/virtues/child/' + child.replace(" ","_") + '" style="padding:8px 16px;'
        'background:' + child_color(child,"bg") + ';color:white;'
        'border-radius:8px;text-decoration:none;font-size:0.82em;font-weight:600;">'
        + escape(child) + '</a>'
        for child in CHILDREN
    )}
  </div>
</div>
"""
    return html_page("Virtue Tracker", body)


# ── Mom personal page (/virtues/me) ──────────────────────────────────────────

def render_virtue_me_page(virtue_pick=None, status=""):
    personal = load_personal_virtue()
    current  = personal.get("current")
    season   = _current_season()
    api_key  = _api_key()

    # If a virtue was requested via URL, generate and set it
    if virtue_pick and (not current or current.get("virtue","").lower() != virtue_pick.lower()):
        content = generate_virtue_content(virtue_pick, "Mom", "adult", season)
        current = {
            "virtue":  virtue_pick,
            "content": content,
            "started": date.today().isoformat(),
            "checkins": [],
        }
        personal["current"] = current
        save_personal_virtue(personal)

    virtue_list_opts = "".join(
        f'<option value="{escape(v)}" {"selected" if current and current.get("virtue")==v else ""}>'
        f'{escape(v)}</option>'
        for v in VIRTUE_LIBRARY
    )

    card_html = ""
    if current:
        card_html = _virtue_card(current, "Mom", "me", "#8b5a3c", True, "adult")

    history = personal.get("history", [])
    history_html = ""
    for h in history[-5:][::-1]:
        history_html += (
            f'<div style="display:flex;gap:8px;align-items:center;padding:5px 0;'
            f'border-bottom:1px solid var(--border-light);">'
            f'<span style="font-size:0.85em;font-weight:600;color:var(--ink);">'
            f'{escape(h.get("virtue",""))}</span>'
            f'<span style="font-size:0.72em;color:var(--ink-faint);">'
            f'{escape(h.get("started",""))} &rarr; {escape(h.get("ended",""))}</span>'
            f'</div>'
        )

    ai_suggest_btn = ""
    if api_key:
        ai_suggest_btn = (
            f'<button onclick="aiSuggestVirtue(\'me\')" '
            f'style="width:100%;padding:10px;background:linear-gradient(135deg,#1c1610,#2a1e10);'
            f'color:var(--gold-light);border:none;border-radius:10px;font-size:0.88em;'
            f'font-weight:600;font-family:inherit;cursor:pointer;margin-top:8px;">'
            f'\u2728 Let AI suggest a virtue for {escape(season)}</button>'
            f'<div id="ai-suggest-me-result" style="display:none;margin-top:8px;'
            f'padding:10px;background:#faf8f5;border-radius:8px;font-size:0.85em;'
            f'color:var(--ink);line-height:1.6;"></div>'
        )

    body = top_nav() + render_status_message(status) + f"""
<div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
  <a href="/virtues" style="font-size:0.82em;color:var(--ink-faint);text-decoration:none;">&larr; All virtues</a>
  <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.8rem;font-weight:600;color:var(--ink);">Mom's Virtue Focus</div>
</div>

<div class="card" style="margin-bottom:14px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:10px;">Choose a Virtue</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;">
    <select id="virtue-select-me"
            style="flex:1;min-width:180px;padding:8px 10px;border-radius:8px;
                   border:1.5px solid var(--border);font-family:inherit;font-size:0.88em;">
      <option value="">— choose —</option>
      {virtue_list_opts}
    </select>
    <button onclick="setVirtue('me')"
            style="padding:8px 18px;background:var(--ink);color:var(--gold-light);
                   border:none;border-radius:8px;font-family:inherit;font-weight:600;
                   font-size:0.88em;cursor:pointer;">Set &amp; generate</button>
  </div>
  {ai_suggest_btn}
</div>

<div id="virtue-me-loading" style="display:none;text-align:center;padding:20px;
     color:var(--ink-faint);font-size:0.88em;">\u231b Generating content...</div>

<div id="virtue-me-card">
  {card_html}
</div>

{"<div class='card'><div style='font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;'>Past Virtues</div>" + history_html + "</div>" if history_html else ""}

<div id="rate-status" style="font-size:0.82em;color:#22c55e;min-height:16px;margin-top:4px;"></div>

<script>
var _currentRating = 0;

function setVirtue(who) {{
  var sel = document.getElementById('virtue-select-' + who);
  if (!sel || !sel.value) return;
  var loading = document.getElementById('virtue-' + who + '-loading');
  if (loading) loading.style.display = 'block';
  window.location.href = '/virtues/' + (who === 'me' ? 'me' : who) + '?virtue=' + encodeURIComponent(sel.value);
}}

function rateVirtue(who, rating) {{
  _currentRating = rating;
  document.querySelectorAll('button[onclick*="rateVirtue"]').forEach(function(btn) {{
    var m = btn.getAttribute('onclick').match(new RegExp(',([0-9])\\)'));
    if (m) btn.style.color = parseInt(m[1]) <= rating ? '#f59e0b' : '#d1d5db';
  }});
}}

function saveCheckin(who) {{
  var noteEl = document.getElementById('note-' + who);
  var note   = noteEl ? noteEl.value : '';
  fetch('/virtue-checkin', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'who=' + encodeURIComponent(who) +
          '&rating=' + _currentRating +
          '&note='   + encodeURIComponent(note)
  }}).then(function() {{
    var el = document.getElementById('rate-status');
    if (el) {{ el.textContent = 'Saved \u2713'; setTimeout(function(){{ el.textContent=''; }}, 2000); }}
    if (noteEl) noteEl.value = '';
  }});
}}

function aiSuggestVirtue(who) {{
  var resultEl = document.getElementById('ai-suggest-' + who + '-result');
  if (resultEl) resultEl.style.display = 'none';
  fetch('/ai-suggest-virtue', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'who=' + encodeURIComponent(who)
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (resultEl) {{
      resultEl.style.display = 'block';
      resultEl.innerHTML = (d.html || d.text || '');
    }}
  }});
}}
</script>
"""
    return html_page("Mom's Virtue \u00b7 Sancta Familia", body)


# ── Family page (/virtues/family) ─────────────────────────────────────────────

def render_virtue_family_page(virtue_pick=None, status=""):
    family  = load_family_virtue()
    current = family.get("current")
    season  = _current_season()
    api_key = _api_key()

    if virtue_pick and (not current or current.get("virtue","").lower() != virtue_pick.lower()):
        content = generate_virtue_content(virtue_pick, "Family", "adult", season)
        # Also generate a family-specific practice overlay
        content["practices"] = _family_practices(virtue_pick, season, content.get("practices",[]))
        current = {
            "virtue":  virtue_pick,
            "content": content,
            "started": date.today().isoformat(),
            "checkins": [],
        }
        family["current"] = current
        save_family_virtue(family)

    virtue_list_opts = "".join(
        f'<option value="{escape(v)}" {"selected" if current and current.get("virtue")==v else ""}>'
        f'{escape(v)}</option>'
        for v in VIRTUE_LIBRARY
    )

    card_html = ""
    if current:
        card_html = _virtue_card(current, "Family", "family", "var(--brown)", True, "adult")

    ai_suggest_btn = ""
    if api_key:
        ai_suggest_btn = (
            f'<button onclick="aiSuggestVirtue(\'family\')" '
            f'style="width:100%;padding:10px;background:linear-gradient(135deg,#1c1610,#2a1e10);'
            f'color:var(--gold-light);border:none;border-radius:10px;font-size:0.88em;'
            f'font-weight:600;font-family:inherit;cursor:pointer;margin-top:8px;">'
            f'\u2728 Suggest a family virtue for {escape(season)}</button>'
            f'<div id="ai-suggest-family-result" style="display:none;margin-top:8px;'
            f'padding:10px;background:#faf8f5;border-radius:8px;font-size:0.85em;'
            f'color:var(--ink);line-height:1.6;"></div>'
        )

    body = top_nav() + render_status_message(status) + f"""
<div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
  <a href="/virtues" style="font-size:0.82em;color:var(--ink-faint);text-decoration:none;">&larr; All virtues</a>
  <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.8rem;font-weight:600;color:var(--ink);">Family Virtue</div>
</div>

<div class="card" style="margin-bottom:14px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:10px;">Choose This Month's Family Virtue</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;">
    <select id="virtue-select-family"
            style="flex:1;min-width:180px;padding:8px 10px;border-radius:8px;
                   border:1.5px solid var(--border);font-family:inherit;font-size:0.88em;">
      <option value="">— choose —</option>
      {virtue_list_opts}
    </select>
    <button onclick="setVirtue('family')"
            style="padding:8px 18px;background:var(--ink);color:var(--gold-light);
                   border:none;border-radius:8px;font-family:inherit;font-weight:600;
                   font-size:0.88em;cursor:pointer;">Set &amp; generate</button>
  </div>
  {ai_suggest_btn}
</div>

<div id="virtue-family-loading" style="display:none;text-align:center;padding:20px;
     color:var(--ink-faint);font-size:0.88em;">\u231b Generating content...</div>

<div id="virtue-family-card">
  {card_html}
</div>
<div id="rate-status" style="font-size:0.82em;color:#22c55e;min-height:16px;margin-top:4px;"></div>

<script>
var _currentRating = 0;
function setVirtue(who) {{
  var sel = document.getElementById('virtue-select-' + who);
  if (!sel || !sel.value) return;
  window.location.href = '/virtues/family?virtue=' + encodeURIComponent(sel.value);
}}
function rateVirtue(who, rating) {{
  _currentRating = rating;
  document.querySelectorAll('button[onclick*="rateVirtue"]').forEach(function(btn) {{
    var m = btn.getAttribute('onclick').match(new RegExp(',([0-9])\\)'));
    if (m) btn.style.color = parseInt(m[1]) <= rating ? '#f59e0b' : '#d1d5db';
  }});
}}
function saveCheckin(who) {{
  var noteEl = document.getElementById('note-' + who);
  fetch('/virtue-checkin', {{
    method: 'POST', headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'who=' + encodeURIComponent(who) + '&rating=' + _currentRating +
          '&note=' + encodeURIComponent(noteEl ? noteEl.value : '')
  }}).then(function() {{
    var el = document.getElementById('rate-status');
    if (el) {{ el.textContent = 'Saved \u2713'; setTimeout(function(){{ el.textContent=''; }}, 2000); }}
    if (noteEl) noteEl.value = '';
  }});
}}
function aiSuggestVirtue(who) {{
  var resultEl = document.getElementById('ai-suggest-' + who + '-result');
  fetch('/ai-suggest-virtue', {{
    method: 'POST', headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'who=' + encodeURIComponent(who)
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (resultEl) {{ resultEl.style.display = 'block'; resultEl.innerHTML = d.html || d.text || ''; }}
  }});
}}
</script>
"""
    return html_page("Family Virtue \u00b7 Sancta Familia", body)


def _family_practices(virtue, season, base_practices):
    """Inject family-specific practices alongside base ones."""
    family_extras = [
        f"At dinner this week, ask each family member: \u201cHow did you practice {virtue} today?\u201d",
        f"Do one act of {virtue} together as a family before Sunday Mass.",
    ]
    return list(base_practices) + family_extras


# ── Child page (/virtues/child/NAME) ─────────────────────────────────────────

def render_virtue_child_page(child_id, virtue_pick=None, status=""):
    # Resolve child name from id
    child_name = child_id.replace("_", " ")
    # Try to match to actual CHILDREN list
    matched = next((c for c in CHILDREN if c.lower() == child_name.lower()), child_name)

    cdata   = load_child_virtue(matched)
    current = cdata.get("current")
    season  = _current_season()
    api_key = _api_key()
    age     = child_age(matched)
    ab      = age_band(age)
    c_bg    = child_color(matched, "bg")
    c_id    = matched.replace(" ","_")

    age_label_map = {
        "toddler":     "Little One (3\u20134)",
        "young_child": "Young Child (5\u20137)",
        "child":       "Child (8\u201311)",
        "teen":        "Teen (12\u201315)",
        "young_adult": "Young Adult (16+)",
        "adult":       "Adult",
    }
    age_label = age_label_map.get(ab, "Child")
    if age is not None:
        age_label += f" \u00b7 Age {age}"

    if virtue_pick and (not current or current.get("virtue","").lower() != virtue_pick.lower()):
        content = generate_virtue_content(virtue_pick, matched, ab, season)
        current = {
            "virtue":  virtue_pick,
            "content": content,
            "started": date.today().isoformat(),
            "checkins": [],
        }
        cdata["current"] = current
        save_child_virtue(matched, cdata)

    virtue_list_opts = "".join(
        f'<option value="{escape(v)}" {"selected" if current and current.get("virtue")==v else ""}>'
        f'{escape(v)}</option>'
        for v in VIRTUE_LIBRARY
    )

    card_html = ""
    if current:
        card_html = _virtue_card(current, matched, c_id, c_bg, True, ab)

    ai_btn = ""
    if api_key:
        ai_btn = (
            f'<button onclick="aiSuggestChildVirtue()" '
            f'style="width:100%;padding:10px;background:linear-gradient(135deg,#1c1610,#2a1e10);'
            f'color:var(--gold-light);border:none;border-radius:10px;font-size:0.88em;'
            f'font-weight:600;font-family:inherit;cursor:pointer;margin-top:8px;">'
            f'\u2728 Suggest a virtue for {escape(matched)}</button>'
            f'<div id="ai-suggest-child-result" style="display:none;margin-top:8px;'
            f'padding:10px;background:#faf8f5;border-radius:8px;font-size:0.85em;'
            f'color:var(--ink);line-height:1.6;"></div>'
        )

    history      = cdata.get("history", [])
    history_html = ""
    for h in history[-4:][::-1]:
        history_html += (
            f'<div style="display:flex;gap:8px;align-items:center;padding:5px 0;'
            f'border-bottom:1px solid var(--border-light);">'
            f'<span style="font-size:0.85em;font-weight:600;">{escape(h.get("virtue",""))}</span>'
            f'<span style="font-size:0.72em;color:var(--ink-faint);">'
            f'{escape(h.get("started",""))} &rarr; {escape(h.get("ended",""))}</span>'
            f'</div>'
        )

    c_id_esc = escape(c_id)
    body = top_nav() + render_status_message(status) + f"""
<div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
  <a href="/virtues" style="font-size:0.82em;color:var(--ink-faint);text-decoration:none;">&larr; All virtues</a>
  <div>
    <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.8rem;font-weight:600;color:{c_bg};">{escape(matched)}</div>
    <div style="font-size:0.78em;color:var(--ink-faint);">{age_label}</div>
  </div>
</div>

<div class="card" style="margin-bottom:14px;border-left:4px solid {c_bg};">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:10px;">Choose a Virtue for {escape(matched)}</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;">
    <select id="virtue-select-child"
            style="flex:1;min-width:180px;padding:8px 10px;border-radius:8px;
                   border:1.5px solid var(--border);font-family:inherit;font-size:0.88em;">
      <option value="">— choose —</option>
      {virtue_list_opts}
    </select>
    <button onclick="setChildVirtue()"
            style="padding:8px 18px;background:{c_bg};color:white;
                   border:none;border-radius:8px;font-family:inherit;font-weight:600;
                   font-size:0.88em;cursor:pointer;">Set &amp; generate</button>
  </div>
  {ai_btn}
</div>

<div id="virtue-child-loading" style="display:none;text-align:center;padding:20px;
     color:var(--ink-faint);font-size:0.88em;">\u231b Generating content...</div>

<div id="virtue-child-card">
  {card_html}
</div>
{"<div class='card'><div style='font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;'>Past Virtues</div>" + history_html + "</div>" if history_html else ""}
<div id="rate-status" style="font-size:0.82em;color:#22c55e;min-height:16px;margin-top:4px;"></div>

<script>
var _childId = '{c_id_esc}';
var _currentRating = 0;

function setChildVirtue() {{
  var sel = document.getElementById('virtue-select-child');
  if (!sel || !sel.value) return;
  document.getElementById('virtue-child-loading').style.display = 'block';
  window.location.href = '/virtues/child/' + encodeURIComponent(_childId) + '?virtue=' + encodeURIComponent(sel.value);
}}

function rateVirtue(who, rating) {{
  _currentRating = rating;
  document.querySelectorAll('button[onclick*="rateVirtue"]').forEach(function(btn) {{
    var m = btn.getAttribute('onclick').match(new RegExp(',([0-9])\\)'));
    if (m) btn.style.color = parseInt(m[1]) <= rating ? '#f59e0b' : '#d1d5db';
  }});
}}

function saveCheckin(who) {{
  var noteEl = document.getElementById('note-' + who);
  fetch('/virtue-checkin', {{
    method: 'POST', headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'who=' + encodeURIComponent(who) + '&rating=' + _currentRating +
          '&note=' + encodeURIComponent(noteEl ? noteEl.value : '')
  }}).then(function() {{
    var el = document.getElementById('rate-status');
    if (el) {{ el.textContent = 'Saved \u2713'; setTimeout(function(){{ el.textContent=''; }}, 2000); }}
    if (noteEl) noteEl.value = '';
  }});
}}

function aiSuggestChildVirtue() {{
  var resultEl = document.getElementById('ai-suggest-child-result');
  fetch('/ai-suggest-virtue', {{
    method: 'POST', headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'who=child&child_id=' + encodeURIComponent(_childId)
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (resultEl) {{ resultEl.style.display='block'; resultEl.innerHTML = d.html || d.text || ''; }}
  }});
}}
</script>
"""
    return html_page(f"{matched}'s Virtue \u00b7 Sancta Familia", body)