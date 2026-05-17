"""
render_frol_wizard.py — Rule of Life Wizard (Phase 1).

A 10-step setup flow that helps any family build their daily/weekly rhythm.
Two modes:
  - Lucy-guided (conversational, requires API key)
  - Structured (form-based, no API key needed)

Auto-saves after every field/step to data/frol_wizard_progress.json so
interruptions lose nothing.

Public surface:
  - render_frol_wizard_page(viewer, step=None, mode=None) -> str
  - render_frol_setup_card(viewer)                        -> str
  - load_progress() / save_progress(p)
  - save_field(step, field, value, mode=None)             -> dict
  - advance_step(step, mode=None)                         -> dict
  - reset_progress()                                      -> dict
  - finalize_wizard()                                     -> dict
  - build_wizard_chat_context(progress)                   -> str
  - has_anthropic_key()                                   -> bool
  - is_complete()                                         -> bool
  - is_dismissed()                                        -> bool   (uses cookie set by JS)
  - WIZARD_TOTAL_STEPS = 10
"""

import os
import json
import shutil
from datetime import datetime
from html import escape

from config import (
    FROL_WIZARD_PROGRESS_FILE,
    APP_SETTINGS_FILE,
    PRAYER_INTENTIONS_FILE,
)
from data_helpers import safe_save_json


WIZARD_TOTAL_STEPS = 10
DAY_TEMPLATES_DIR = "data/day_templates"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"]


# ── V2 section identity table (Phase 4 will wire these into the flow) ───────
# Each tuple: (section_index, slug, display_title, subtitle).
# Identity-only for Phase 3 — existing 10-step structure remains active until
# Phase 4 lights up the new sections.
V2_SECTIONS = [
    (1,  "family",       "Your Family",                "Who lives here and how the week feels"),
    (2,  "little_ones",  "The Little Ones First",      "James + Michael's rhythms first"),
    (3,  "fixed",        "Fixed Commitments",          "What's already on the calendar"),
    (4,  "prayer",       "Prayer",                     "The heartbeat of the day"),
    (5,  "meals",        "Meals",                      "Breakfast, lunch, dinner, snacks, prep"),
    (6,  "school",       "School",                     "Homeschool format and per-subject rhythm"),
    (7,  "chores",       "Chores & Household",         "Daily, weekly, monthly, seasonal, annual"),
    (8,  "health",       "Exercise & Health",          "Movement, wellness, emergency contacts"),
    (9,  "rest",         "Rest, Free Time, Faith Life","Sabbath, marriage, traditions"),
    (10, "flex",         "Flex, Buffers & Seasonal",   "Transitions, energy, the things that go wrong"),
    (11, "build",        "Build Your Day",             "Visual placement on the timeline"),
    (12, "commitments",  "Seven Commitments Check",    "Where the day reflects each commitment"),
    (13, "review",       "AI Review & Suggestions",    "Multitasking, development, optimization"),
]
V2_TOTAL_SECTIONS = len(V2_SECTIONS)


# Seven commitments shown on the landing screen (Laura Dominick framing).
SEVEN_COMMITMENTS = [
    "Daily prayer that anchors the family",
    "Sunday Mass and weekly Adoration",
    "Meals shared at a common table",
    "Sabbath rest each week",
    "Service to those in need",
    "Hospitality and welcome in the home",
    "Time for play, beauty, and joy",
]


# ── Progress load/save ──────────────────────────────────────────────────────

def _empty_progress() -> dict:
    return {
        "mode":            "",
        "current_step":    0,
        "completed_steps": [],
        "data":            {},
        "started_at":      "",
        "updated_at":      "",
        "finalized_at":    "",
    }


def load_progress() -> dict:
    if not os.path.exists(FROL_WIZARD_PROGRESS_FILE):
        return _empty_progress()
    try:
        with open(FROL_WIZARD_PROGRESS_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return _empty_progress()
    base = _empty_progress()
    base.update(data if isinstance(data, dict) else {})
    return base


def save_progress(p: dict) -> dict:
    p["updated_at"] = datetime.now().isoformat(timespec="seconds")
    if not p.get("started_at"):
        p["started_at"] = p["updated_at"]
    safe_save_json(FROL_WIZARD_PROGRESS_FILE, p)
    return p


def reset_progress() -> dict:
    p = _empty_progress()
    safe_save_json(FROL_WIZARD_PROGRESS_FILE, p)
    return p


def is_complete() -> bool:
    p = load_progress()
    return bool(p.get("finalized_at"))


def is_dismissed() -> bool:
    """Wizard card dismissal is stored client-side (cookie). The server can't
    know without inspecting the request; callers that need this should check
    the cookie themselves. Provided here for symmetry."""
    return False


def save_field(step: int, field: str, value, mode: str = "") -> dict:
    p = load_progress()
    if mode and not p.get("mode"):
        p["mode"] = mode
    step_key = f"step_{int(step)}"
    bucket = p["data"].setdefault(step_key, {})
    bucket[field] = value
    return save_progress(p)


def advance_step(step: int, mode: str = "") -> dict:
    p = load_progress()
    if mode and not p.get("mode"):
        p["mode"] = mode
    step = int(step)
    if step not in p["completed_steps"]:
        p["completed_steps"].append(step)
    p["current_step"] = max(p.get("current_step", 0), step + 1)
    return save_progress(p)


# ── API key check (env first, then settings) ────────────────────────────────

def has_anthropic_key() -> bool:
    if (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        return True
    try:
        with open(APP_SETTINGS_FILE, encoding="utf-8") as fh:
            s = json.load(fh)
        fc_key = (s.get("family_constraints", {}) or {}).get("anthropic_api_key", "")
        top_key = s.get("anthropic_api_key", "")
        return bool((fc_key or top_key or "").strip())
    except Exception:
        return False


def get_anthropic_key() -> str:
    env_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if env_key:
        return env_key
    try:
        with open(APP_SETTINGS_FILE, encoding="utf-8") as fh:
            s = json.load(fh)
        return ((s.get("family_constraints", {}) or {}).get("anthropic_api_key", "")
                or s.get("anthropic_api_key", "")).strip()
    except Exception:
        return ""


# ── Heuristic suggestion library (hand-coded for Phase 1) ───────────────────

def derive_heuristic_notes(progress: dict) -> list:
    """Return a list of gentle suggestions based on collected data so far."""
    notes = []
    d = progress.get("data", {}) or {}
    members = (d.get("step_1", {}) or {}).get("members", []) or []
    young_kids = [m for m in members if _age_bucket(m) in ("toddler", "preschool")]
    homeschool = (d.get("step_5", {}) or {}).get("homeschool_yes") in ("yes", "true", True)
    schoolers   = (d.get("step_5", {}) or {}).get("homeschool_kids", []) or []

    if young_kids:
        notes.append("With a child under five in the family, consider an "
                     "afternoon rest block of at least 90 minutes — protects "
                     "everyone's energy through dinner.")
    if homeschool and len(schoolers) >= 2:
        notes.append("Homeschooling more than one child? Block a 30-minute "
                     "buffer between subjects so transitions don't blur the day.")
    if not (d.get("step_4", {}) or {}).get("morning_dinner_prep"):
        notes.append("If dinner often runs late, scheduling a 15-minute "
                     "morning prep slot makes evenings dramatically calmer.")
    return notes


def _age_bucket(member: dict) -> str:
    bd = (member.get("birthday") or "").strip()
    if not bd:
        return (member.get("role", "") or "").lower()
    try:
        y, m, d = [int(x) for x in bd.split("-")]
        today = datetime.now().date()
        age = today.year - y - ((today.month, today.day) < (m, d))
    except Exception:
        return ""
    if age < 2:   return "toddler"
    if age < 5:   return "preschool"
    if age < 12:  return "child"
    if age < 18:  return "teen"
    return "adult"


# ── Page chrome ─────────────────────────────────────────────────────────────

WIZARD_CSS = """
:root{
  --frol-blue:#4a6fa5; --frol-blue-dark:#33507e; --frol-cream:#fbf6ec;
  --frol-ink:#2b2b2b;  --frol-mute:#6e6e6e;     --frol-line:#e6dec8;
}
*{box-sizing:border-box}
body{margin:0;background:var(--frol-cream);color:var(--frol-ink);
     font-family:Georgia,'Times New Roman',serif;line-height:1.55;}
.frol-wrap{max-width:780px;margin:0 auto;padding:28px 22px 80px;}
.frol-top{display:flex;align-items:center;justify-content:space-between;
          margin-bottom:18px;font-size:0.85em;color:var(--frol-mute);}
.frol-top a{color:var(--frol-blue);text-decoration:none}
.frol-dots{display:flex;gap:6px;margin:8px 0 24px;justify-content:center;}
.frol-dot{width:14px;height:14px;border-radius:50%;
          background:#e8dec0;border:1px solid var(--frol-line);}
.frol-dot.done{background:var(--frol-blue);border-color:var(--frol-blue);}
.frol-dot.current{background:var(--frol-blue);outline:3px solid #c8d6ec;
                  outline-offset:2px;}
.frol-card{background:#fff;border:1px solid var(--frol-line);
           border-radius:14px;padding:28px 26px;
           box-shadow:0 6px 20px rgba(74,111,165,0.06);}
.frol-title{font-family:Georgia,serif;font-size:1.7em;color:var(--frol-blue-dark);
            margin:0 0 6px;}
.frol-sub{color:var(--frol-mute);margin:0 0 22px;font-style:italic;}
.frol-fld{display:block;margin:14px 0 6px;font-weight:700;font-size:0.94em;}
.frol-help{font-size:0.85em;color:var(--frol-mute);margin:-2px 0 8px;}
.frol-input,.frol-select,.frol-textarea{
  width:100%;padding:9px 11px;border:1px solid var(--frol-line);
  border-radius:8px;font-size:1em;font-family:inherit;background:#fffdf6;
}
.frol-textarea{min-height:70px;resize:vertical}
.frol-row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;}
.frol-row > *{flex:1 1 160px}
.frol-check{display:inline-flex;align-items:center;gap:8px;margin:6px 14px 6px 0;
            font-weight:500;}
.frol-actions{display:flex;justify-content:space-between;align-items:center;
              margin-top:30px;padding-top:18px;border-top:1px solid var(--frol-line);}
.frol-btn{background:var(--frol-blue);color:#fff;border:none;border-radius:8px;
          padding:11px 22px;font-size:1em;font-weight:700;cursor:pointer;
          font-family:inherit;text-decoration:none;display:inline-block;}
.frol-btn:hover{background:var(--frol-blue-dark)}
.frol-btn.ghost{background:transparent;color:var(--frol-blue);
                border:1px solid var(--frol-blue);}
.frol-save-status{font-size:0.82em;color:var(--frol-mute);}
.frol-companion{background:#eaf0fa;border-left:4px solid var(--frol-blue);
                padding:14px 18px;border-radius:6px;margin:18px 0;}
.frol-companion .name{font-weight:700;color:var(--frol-blue-dark);}
.frol-pop-note{background:#fef9e7;border:1px solid #f0e0a0;border-radius:8px;
               padding:10px 14px;font-size:0.9em;margin:14px 0;color:#6b5d28;}
.frol-grid{display:grid;grid-template-columns:120px 1fr;gap:6px 10px;
           margin:6px 0;align-items:center;font-size:0.92em;}
.frol-member{border:1px solid var(--frol-line);border-radius:10px;
             padding:14px;margin:10px 0;background:#fffdf6;}
.frol-rm{background:transparent;border:none;color:#a0524a;cursor:pointer;
         font-size:0.85em;text-decoration:underline;padding:0;}
.frol-add{background:transparent;border:1px dashed var(--frol-blue);
          color:var(--frol-blue);border-radius:8px;padding:8px 14px;
          font-family:inherit;cursor:pointer;font-size:0.9em;
          margin-top:6px;}
.frol-chat{margin-top:24px;border:1px solid var(--frol-line);border-radius:12px;
           padding:14px;background:#fffdf6;}
.frol-chat h3{margin:0 0 10px;font-size:1em;color:var(--frol-blue-dark);}
.frol-chat-log{min-height:120px;max-height:340px;overflow-y:auto;
               font-family:Georgia,serif;font-size:0.95em;line-height:1.5;}
.frol-chat-log .me{color:#444;margin:8px 0;}
.frol-chat-log .me::before{content:"You: ";font-weight:700;color:var(--frol-blue-dark)}
.frol-chat-log .lu{color:#222;margin:8px 0;}
.frol-chat-log .lu::before{content:"Lucy: ";font-weight:700;color:#7a4ea3;}
.frol-chat-form{display:flex;gap:8px;margin-top:10px;}
.frol-chat-form input{flex:1;padding:9px 11px;border:1px solid var(--frol-line);
                      border-radius:8px;font-family:inherit;font-size:0.95em;}
.frol-chat-form button{background:#7a4ea3;color:#fff;border:none;border-radius:8px;
                       padding:9px 16px;font-weight:700;cursor:pointer;}
@media (min-width:1024px){
  .frol-with-chat{display:grid;grid-template-columns:1.1fr 0.9fr;gap:22px;}
  .frol-with-chat .frol-chat{margin-top:0;}
}
"""


def _progress_dots(current: int, completed: list) -> str:
    parts = []
    for i in range(1, WIZARD_TOTAL_STEPS + 1):
        cls = "frol-dot"
        if i in (completed or []):
            cls += " done"
        if i == current:
            cls += " current"
        parts.append(f'<span class="{cls}" title="Step {i}"></span>')
    return f'<div class="frol-dots">{"".join(parts)}</div>'


# ── V2 shared components (Phase 3) ──────────────────────────────────────────
# These are additive helpers that Phase 4 section renderers will compose
# without touching the existing render_step_* functions.

def render_section_dots(current: int, total: int, completed: list) -> str:
    """Generic progress dots for any N-section flow (V2 uses 13)."""
    parts = []
    for i in range(1, int(total) + 1):
        cls = "frol-dot"
        if i in (completed or []):
            cls += " done"
        if i == current:
            cls += " current"
        parts.append(f'<span class="{cls}" title="Section {i}"></span>')
    return f'<div class="frol-dots">{"".join(parts)}</div>'


def render_reflection_card(title: str, body_html: str, key: str,
                            attribution: str = "",
                            open_first_visit: bool = True) -> str:
    """Collapsible reflection card. Opens on first visit (no cookie),
    remembers user's open/closed choice afterward via localStorage."""
    safe_key  = escape(key, quote=True)
    safe_attr = ""
    if attribution:
        safe_attr = (
            f'<div style="margin-top:10px;font-size:0.78em;color:#7d6a4a;'
            f'font-style:italic;text-align:right;">{escape(attribution)}</div>'
        )
    default_open = "open" if open_first_visit else ""
    return f"""
      <details class="frol-reflection" data-reflect-key="{safe_key}" {default_open}
               style="background:#fbf7ef;border:1px solid #ead9b8;border-left:4px solid #c89c4a;
                      border-radius:10px;padding:12px 16px;margin:14px 0;">
        <summary style="cursor:pointer;font-weight:700;color:#7d5a1f;font-family:Georgia,serif;">
          {escape(title)}
        </summary>
        <div style="margin-top:10px;color:#3f3220;line-height:1.55;font-size:0.95em;">
          {body_html}
        </div>
        {safe_attr}
      </details>
    """


def render_companion_intro_card(name: str, icon_html: str, one_liner: str,
                                 href: str, accent: str = "#4a6fa5",
                                 light: str = "#eaf0fa") -> str:
    """Compact companion intro card with a 'Meet' link, used inside a section
    when that companion is first introduced (Sister Mary in §4, Lorenzo in
    §5, Father Gregory in §6, Coach + Dr. Monica in §8, etc.)."""
    return f"""
      <div style="background:{light};border:1px solid {accent}33;border-left:4px solid {accent};
                  border-radius:10px;padding:12px 14px;margin:12px 0;
                  display:flex;align-items:center;gap:12px;">
        <div style="font-size:1.6em;color:{accent};">{icon_html}</div>
        <div style="flex:1;">
          <div style="font-weight:700;color:{accent};font-size:1.02em;">{escape(name)}</div>
          <div style="font-size:0.88em;color:#444;margin-top:2px;line-height:1.4;">
            {escape(one_liner)}
          </div>
        </div>
        <a href="{escape(href, quote=True)}" target="_blank"
           style="text-decoration:none;color:{accent};font-weight:700;font-size:0.86em;
                  white-space:nowrap;">Meet &rarr;</a>
      </div>
    """


def render_lucy_hint_slot(step: int) -> str:
    """Empty container that the wizard JS fills with real-time Lucy hints
    as the user fills the section. Stays hidden until JS injects content."""
    return (
        f'<div class="frol-lucy-hint" id="frol-lucy-hint-{int(step)}" '
        f'data-step="{int(step)}" style="display:none;background:#f3f0f9;'
        f'border:1px solid #d8cdec;border-left:4px solid #7a4ea3;border-radius:10px;'
        f'padding:10px 14px;margin:10px 0;font-size:0.9em;color:#3e2a5e;"></div>'
    )


# Suggestion-checkbox sets the activity builder can render by section slug.
# Phase 4 will expand these per-section; Phase 3 ships a starter set so the
# JS + Python wiring can be smoke-tested.
_ACTIVITY_SUGGESTIONS = {
    "prayer":  ["Morning Offering", "Family Rosary", "Daily Mass",
                "Examen", "Bedtime Prayer"],
    "meals":   ["Breakfast", "Lunch", "Dinner", "Snack",
                "Meal prep", "Batch cooking", "Grocery run"],
    "school":  ["Math", "Language Arts", "History", "Science",
                "Latin", "Religion", "Art", "PE"],
    "health":  ["Family walk", "Strength training", "Yoga", "Sports practice"],
    "rest":    ["Quiet reading", "Outdoor play", "Family movie",
                "Sabbath dinner", "Hobby time"],
}

_ACTIVITY_WHEN_BUCKETS = [
    ("early_morning", "Early morning (5:00–6:59)"),
    ("morning",       "Morning (7:00–11:59)"),
    ("afternoon",     "Afternoon (12:00–16:59)"),
    ("evening",       "Evening (17:00–19:59)"),
    ("late_evening",  "Late evening (20:00–22:00)"),
    ("anytime",       "Anytime"),
]

_ACTIVITY_DURATIONS = [5, 10, 15, 20, 30, 45, 60, 90, 120]


def render_activity_builder(step: int, section_slug: str,
                             family_members: list,
                             saved_activities: list = None) -> str:
    """Shared activity builder used across every V2 section that collects
    activities. Renders:
      - suggestion checkboxes (per section_slug)
      - a freeform "Add custom activity" row builder
      - any saved rows for this section, editable in place
    Auto-save fires through the existing saveField pipeline using
    data-step / data-key / data-list / data-idx attributes."""
    saved_activities = saved_activities or []
    sug = _ACTIVITY_SUGGESTIONS.get(section_slug, [])
    member_opts = "".join(
        f'<option value="{escape(m.get("name",""), quote=True)}">{escape(m.get("name",""))}</option>'
        for m in (family_members or []) if m.get("name")
    )
    when_opts = "".join(
        f'<option value="{escape(k, quote=True)}">{escape(v)}</option>'
        for k, v in _ACTIVITY_WHEN_BUCKETS
    )
    dur_opts = "".join(
        f'<option value="{d}">{d} min</option>' for d in _ACTIVITY_DURATIONS
    )
    sug_html = ""
    for s in sug:
        sug_html += (
            f'<label class="frol-sug" style="display:inline-flex;align-items:center;'
            f'gap:6px;background:#f3f6fb;border:1px solid #d6e0f0;border-radius:999px;'
            f'padding:4px 12px;font-size:0.86em;cursor:pointer;margin:3px;">'
            f'<input type="checkbox" data-step="{int(step)}" data-key="suggested" '
            f'data-multi="1" value="{escape(s, quote=True)}"> {escape(s)}</label>'
        )
    rows_html = ""
    for idx, row in enumerate(saved_activities):
        if not isinstance(row, dict):
            continue
        rows_html += _activity_row_html(step, section_slug, idx, row,
                                        member_opts, when_opts, dur_opts)
    return f"""
      <div class="frol-activity-builder" data-step="{int(step)}"
           data-slug="{escape(section_slug, quote=True)}">
        <div style="font-weight:700;color:#33507e;margin-bottom:6px;">
          Add what already happens in this section
        </div>
        <div class="frol-sug-row" style="margin-bottom:10px;">{sug_html}</div>
        <div class="frol-activity-rows" id="frol-activity-rows-{int(step)}">
          {rows_html}
        </div>
        <button type="button" class="frol-btn ghost"
                onclick="frolActivityAdd({int(step)},'{escape(section_slug, quote=True)}')"
                style="margin-top:8px;">+ Add activity</button>
      </div>
    """


def _activity_row_html(step: int, slug: str, idx: int, row: dict,
                       member_opts: str, when_opts: str, dur_opts: str) -> str:
    """Render one editable row inside the activity builder. Field names use
    `activities` as data-list and the index as data-idx so the existing
    saveField pipeline (which already handles dict-of-dicts) persists each
    column in place."""
    def attr(k, v):
        return (f'data-step="{int(step)}" data-key="{escape(k, quote=True)}" '
                f'data-list="activities" data-idx="{int(idx)}" value="{escape(str(v or ""), quote=True)}"')
    name      = row.get("name", "")
    leader    = row.get("leader", "")
    when_v    = row.get("when", "anytime")
    dur_v     = row.get("duration_min", 30)
    credits_v = row.get("credits", "")
    seasonal  = row.get("seasonal", "no")
    # Build select options with the row's current values selected.
    def _sel_options(opts_html: str, current: str) -> str:
        if not current:
            return opts_html
        cur_esc = escape(str(current), quote=True)
        marker  = f'value="{cur_esc}"'
        return opts_html.replace(marker, f'{marker} selected', 1)
    return f"""
      <div class="frol-activity-row" data-idx="{int(idx)}"
           style="display:grid;grid-template-columns:1.2fr 0.8fr 1fr 0.7fr 0.7fr auto;
                  gap:6px;margin-bottom:6px;align-items:center;">
        <input type="text" placeholder="Activity name" {attr('name', name)}>
        <select data-step="{int(step)}" data-key="leader" data-list="activities" data-idx="{int(idx)}">
          <option value="">Leader…</option>{_sel_options(member_opts, leader)}
        </select>
        <select data-step="{int(step)}" data-key="when" data-list="activities" data-idx="{int(idx)}">
          {_sel_options(when_opts, when_v)}
        </select>
        <select data-step="{int(step)}" data-key="duration_min" data-list="activities" data-idx="{int(idx)}">
          {_sel_options(dur_opts, dur_v)}
        </select>
        <input type="text" placeholder="Credits" {attr('credits', credits_v)}
               style="width:100%;">
        <button type="button" class="frol-btn ghost"
                onclick="frolActivityRemove(this, {int(step)}, {int(idx)})"
                style="padding:4px 10px;">&times;</button>
      </div>
    """


def _step_chrome(step: int, title: str, subtitle: str, body_html: str,
                 mode: str, progress: dict, lucy_visible: bool) -> str:
    completed = progress.get("completed_steps", []) or []
    dots = _progress_dots(step, completed)
    back_link = ""
    if step > 1:
        back_link = (f'<a href="/frol-wizard?step={step-1}&mode={escape(mode, quote=True)}"'
                     f' class="frol-btn ghost">&larr; Back</a>')
    next_step = step + 1 if step < WIZARD_TOTAL_STEPS else step
    advance_label = "Save & Continue" if step < WIZARD_TOTAL_STEPS else "Save"
    next_action = f"/frol-wizard?step={next_step}&mode={escape(mode, quote=True)}"
    chat_panel = ""
    if mode == "lucy" and lucy_visible:
        chat_panel = _render_chat_panel(step)
    main_block = f"""
      <div class="frol-card">
        <h2 class="frol-title">{escape(title)}</h2>
        <p class="frol-sub">{escape(subtitle)}</p>
        <form id="frol-form" data-step="{step}" data-mode="{escape(mode, quote=True)}"
              method="POST" action="/frol-wizard"
              onsubmit="return frolAdvance(event, {step}, '{escape(mode, quote=True)}')">
          <input type="hidden" name="action" value="advance">
          <input type="hidden" name="step"   value="{step}">
          <input type="hidden" name="mode"   value="{escape(mode, quote=True)}">
          {body_html}
          <div class="frol-actions">
            <div>{back_link}</div>
            <div style="display:flex;align-items:center;gap:14px;">
              <span class="frol-save-status" id="frol-save-status">Saved automatically</span>
              <button type="submit" class="frol-btn">{advance_label} &rarr;</button>
            </div>
          </div>
        </form>
      </div>
    """
    if chat_panel:
        return f'<div class="frol-with-chat">{main_block}{chat_panel}</div>'
    return main_block


def _render_chat_panel(step: int) -> str:
    return f"""
      <div class="frol-chat" id="frol-chat" data-step="{step}">
        <h3>Talking with Lucy</h3>
        <div class="frol-chat-log" id="frol-chat-log">
          <div class="lu">I'm here to help you build your family's rhythm.
          Tell me about your week — I'll fill in the form as we talk.</div>
        </div>
        <form class="frol-chat-form" onsubmit="return frolChatSend(event, {step})">
          <input type="text" id="frol-chat-input" autocomplete="off"
                 placeholder="Type a message…">
          <button type="submit">Send</button>
        </form>
      </div>
    """


# ── V2 plumbing (Phase 4) ───────────────────────────────────────────────────
# V2 stores per-section data under `section_N` keys, separate from V1 `step_N`
# so legacy renderers keep working and Lauren's V1 progress is preserved.

# Map: V2 section index → V1 step index whose data to seed from.
_V2_MIGRATION_MAP = {
    1: 1,   # Family ← Family
    3: 2,   # Fixed ← Anchors (wake/bed/fixed_commitments)
    4: 3,   # Prayer ← Prayer
    5: 4,   # Meals ← Meals
    6: 5,   # School ← Work Blocks (homeschool kids, subjects)
    8: 6,   # Health ← Exercise (extra fields from step_8 also merged)
    9: 7,   # Rest ← Rest, Family & Marriage
}


def _migrate_v1_to_v2(progress: dict) -> bool:
    """One-shot copy of V1 step_N data into V2 section_N keys for sections
    that map cleanly. Idempotent — only fills section_N if absent or empty.
    Returns True if any data was migrated."""
    data = progress.setdefault("data", {})
    migrated = False
    for v2_idx, v1_idx in _V2_MIGRATION_MAP.items():
        v2_key = f"section_{v2_idx}"
        v1_key = f"step_{v1_idx}"
        if data.get(v2_key):
            continue
        src = data.get(v1_key) or {}
        if not src:
            continue
        data[v2_key] = dict(src)
        migrated = True
    # Section 8 also pulls health appointment fields from legacy step_8.
    sec8 = data.get("section_8") or {}
    s8 = data.get("step_8") or {}
    if s8 and not sec8.get("emergency_contacts"):
        sec8.setdefault("emergency_contacts", s8.get("emergency_contacts") or [])
        sec8.setdefault("tracked_members",    s8.get("tracked_members") or [])
        sec8.setdefault("recurring_appt_types", s8.get("recurring_appt_types") or [])
        sec8.setdefault("recurring_appts",    s8.get("recurring_appts") or "")
        sec8.setdefault("notif_channels",     s8.get("notif_channels") or [])
        sec8.setdefault("notif_email",        s8.get("notif_email") or "")
        data["section_8"] = sec8
        migrated = True
    # Translate V1 completed_steps → V2 completed sections (only the mapped
    # ones get marked complete; new V2 sections 2,7,10,11,12,13 stay open).
    if migrated and progress.get("completed_steps"):
        v1_completed = set(int(s) for s in progress.get("completed_steps", []) or [])
        v2_completed = sorted({v2 for v2, v1 in _V2_MIGRATION_MAP.items() if v1 in v1_completed})
        progress["_v1_completed_steps"] = list(progress.get("completed_steps") or [])
        progress["completed_steps"] = v2_completed
        progress["current_step"]    = max(v2_completed) + 1 if v2_completed else 1
        progress["_v2_migrated_at"] = datetime.now().isoformat(timespec="seconds")
    return migrated


def save_section_field(section: int, field: str, value,
                        list_: str = "", idx: str = "", mode: str = "") -> dict:
    """V2 analogue of save_field: writes under `section_N` keys. Supports
    scalar (field only), list-of-dicts (integer idx), and dict-of-dicts
    (non-integer idx)."""
    p = load_progress()
    if mode and not p.get("mode"):
        p["mode"] = mode
    bucket = p["data"].setdefault(f"section_{int(section)}", {})
    if list_ and idx != "":
        try:
            i = int(idx); is_int = True
        except Exception:
            is_int = False
        if is_int and i >= 0:
            items = bucket.get(list_)
            if not isinstance(items, list):
                items = []
                bucket[list_] = items
            while len(items) <= i:
                items.append({})
            if value == "__DELETE__":
                if i < len(items):
                    items.pop(i)
            elif isinstance(items[i], dict):
                items[i][field] = value
            else:
                items[i] = {field: value}
        else:
            items = bucket.get(list_)
            if not isinstance(items, dict):
                items = {}
                bucket[list_] = items
            entry = items.get(idx)
            if not isinstance(entry, dict):
                entry = {}
                items[idx] = entry
            entry[field] = value
    elif field:
        bucket[field] = value
    return save_progress(p)


def advance_section(section: int, mode: str = "") -> dict:
    p = load_progress()
    if mode and not p.get("mode"):
        p["mode"] = mode
    section = int(section)
    if section not in p["completed_steps"]:
        p["completed_steps"].append(section)
    p["current_step"] = max(p.get("current_step", 0), section + 1)
    return save_progress(p)


def _sv(progress: dict, section: int, field: str, default=""):
    """V2 reader. Falls back to legacy step_N if section_N missing."""
    bucket = (progress.get("data", {}) or {}).get(f"section_{section}", {}) or {}
    if field in bucket:
        return bucket.get(field, default)
    v1_idx = _V2_MIGRATION_MAP.get(section)
    if v1_idx is not None:
        return ((progress.get("data", {}) or {}).get(f"step_{v1_idx}", {}) or {}).get(field, default)
    return default


def _section_chrome(section: int, title: str, subtitle: str, body_html: str,
                    mode: str, progress: dict, lucy_visible: bool = True) -> str:
    """V2 chrome — sets data-version="2" so the JS uses save_section_field /
    advance_v2 actions and uses 'Section N of V2_TOTAL_SECTIONS'."""
    completed = progress.get("completed_steps", []) or []
    dots = render_section_dots(section, V2_TOTAL_SECTIONS, completed)
    back_link = ""
    if section > 1:
        back_link = (f'<a href="/frol-wizard?step={section-1}&mode={escape(mode, quote=True)}"'
                     f' class="frol-btn ghost">&larr; Back</a>')
    advance_label = ("Save & Continue" if section < V2_TOTAL_SECTIONS
                     else "Save my Rule of Life")
    chat_panel = ""
    if mode == "lucy" and lucy_visible:
        chat_panel = _render_chat_panel(section)
    main_block = f"""
      {dots}
      <div class="frol-card">
        <h2 class="frol-title">{escape(title)}</h2>
        <p class="frol-sub">{escape(subtitle)}</p>
        <form id="frol-form" data-step="{section}" data-version="2"
              data-mode="{escape(mode, quote=True)}"
              method="POST" action="/frol-wizard"
              onsubmit="return frolAdvance(event, {section}, '{escape(mode, quote=True)}')">
          <input type="hidden" name="action"  value="advance_v2">
          <input type="hidden" name="section" value="{section}">
          <input type="hidden" name="mode"    value="{escape(mode, quote=True)}">
          {render_lucy_hint_slot(section)}
          {body_html}
          <div class="frol-actions">
            <div>{back_link}</div>
            <div style="display:flex;align-items:center;gap:14px;">
              <span class="frol-save-status" id="frol-save-status">Saved automatically</span>
              <button type="submit" class="frol-btn">{advance_label} &rarr;</button>
            </div>
          </div>
        </form>
      </div>
    """
    if chat_panel:
        return f'<div class="frol-with-chat">{main_block}{chat_panel}</div>'
    return main_block


# ── V2 section renderers ────────────────────────────────────────────────────

def _v2_members(progress: dict) -> list:
    """Best available member list across V2 + V1 + app_settings."""
    members = _sv(progress, 1, "members", []) or []
    if not members:
        members = _settings_members() or []
    return members


def render_section_1(progress: dict, mode: str) -> str:
    """V2 §1 — Your Family: family name, members, weekend rhythm,
    JP hour-tracking toggle, sibling-pairing intro."""
    family_name = _sv(progress, 1, "family_name", "") or ""
    weekend_rhythm = _sv(progress, 1, "weekend_rhythm", "") or ""
    jp_track = _sv(progress, 1, "jp_hour_tracking", "no")
    pair_intro_seen = _sv(progress, 1, "pairing_intro_seen", "")
    members = _v2_members(progress)
    if not members:
        members = [{"name": "", "role": "", "birthday": "", "color": ""}]
    rows = []
    for i, m in enumerate(members):
        rows.append(f"""
        <div class="frol-member" data-mem-idx="{i}">
          <div class="frol-row">
            <div><label class="frol-fld">Name</label>
              <input class="frol-input" data-step="1" data-list="members" data-idx="{i}"
                     data-key="name" value="{escape(m.get('name','') or '', quote=True)}"
                     placeholder="Mom, JP, Joseph, …"></div>
            <div><label class="frol-fld">Role</label>
              <input class="frol-input" data-step="1" data-list="members" data-idx="{i}"
                     data-key="role" value="{escape(m.get('role','') or '', quote=True)}"
                     placeholder="Mom, Dad, Child, Toddler, …"></div>
          </div>
          <div class="frol-row">
            <div><label class="frol-fld">Birthday <span style="font-weight:400;color:#888;">(optional)</span></label>
              <input class="frol-input" type="date" data-step="1" data-list="members" data-idx="{i}"
                     data-key="birthday" value="{escape(m.get('birthday','') or '', quote=True)}"></div>
            <div><label class="frol-fld">Color <span style="font-weight:400;color:#888;">(optional)</span></label>
              <input class="frol-input" type="color" data-step="1" data-list="members" data-idx="{i}"
                     data-key="color" value="{escape(m.get('color','#4a6fa5') or '#4a6fa5', quote=True)}"></div>
            <div style="flex:0 0 auto;align-self:flex-end;">
              <button type="button" class="frol-rm" onclick="frolRemoveMember({i})">Remove</button>
            </div>
          </div>
        </div>
        """)
    refl = render_reflection_card(
        "Why your family matters in this Rule",
        "<p>Before we plan a single block of the day, we name the people who "
        "live here. The Rule of Life is for <em>them</em> — not the other way "
        "around. Names, ages, and the colors that mean each person become the "
        "fabric that everything else hangs on.</p>",
        key="sec1_intro",
    )
    pair_intro_html = ""
    if pair_intro_seen != "yes":
        pair_intro_html = render_reflection_card(
            "Sibling pairing — a sneak peek",
            "<p>Later (in §6 School and §11 Build Your Day) we'll suggest "
            "natural sibling pairs based on age and the subjects you teach — "
            "e.g., Michael shadowing Joseph for read-alouds, James riding "
            "along during Math. Today, just confirm who lives here.</p>",
            key="sec1_pairing",
        )
    body = f"""
      {refl}
      <label class="frol-fld">Family name <span style="font-weight:400;color:#888;">(used in greetings)</span></label>
      <input class="frol-input" type="text" data-step="1" data-key="family_name"
             value="{escape(family_name, quote=True)}" placeholder="The McAdams Family">

      <h3 style="margin-top:18px;">Family members</h3>
      <div id="frol-members">{''.join(rows)}</div>
      <button type="button" class="frol-add" onclick="frolAddMember()">+ Add another person</button>

      <label class="frol-fld" style="margin-top:22px;">Weekend rhythm <span style="font-weight:400;color:#888;">(one or two sentences)</span></label>
      <p class="frol-help">How does Saturday and Sunday feel different from the
        weekday rhythm? Anchors like Sunday Mass, slower morning, family dinner.</p>
      <textarea class="frol-textarea" data-step="1" data-key="weekend_rhythm"
                placeholder="Sat: Adoration in the morning, errands, family dinner. Sun: Mass at 10:30, lazy afternoon, batch-cook the week.">{escape(weekend_rhythm)}</textarea>

      <h3 style="margin-top:22px;">JP — hour tracking</h3>
      <label style="display:flex;align-items:center;gap:10px;font-weight:normal;">
        <input type="checkbox" data-step="1" data-key="jp_hour_tracking"
               value="yes" {'checked' if jp_track == "yes" else ''}>
        <span>JP is tracking high-school hours this year. (Turning this on
              activates the per-subject hour ledger in §6 School.)</span>
      </label>
      {pair_intro_html}
    """
    return _section_chrome(1, "Your Family",
        "Who lives here, the colors that mean each person, and how your weekends feel different.",
        body, mode, progress, lucy_visible=True)


def render_section_2(progress: dict, mode: str) -> str:
    """V2 §2 — The Little Ones First: capture James + Michael rhythms before
    older-kid planning. Names a 'developmental framework' info card."""
    members = _v2_members(progress)
    little = [m for m in members if isinstance(m, dict) and (m.get("role","").lower() in ("child","toddler") or m.get("name","").lower() in ("james","michael"))]
    # Always at least include James + Michael labels even if members empty.
    if not little:
        little = [{"name": "Michael"}, {"name": "James"}]
    rows = ""
    for m in little:
        nm = m.get("name", "")
        nap   = _sv(progress, 2, f"{nm}__nap_time", "")
        wake  = _sv(progress, 2, f"{nm}__wake_time", "")
        bed   = _sv(progress, 2, f"{nm}__bed_time", "")
        needs = _sv(progress, 2, f"{nm}__needs", "")
        rows += f"""
        <div style="background:#f6f8fc;border:1px solid #d8e1ef;border-left:3px solid #4a6fa5;
                    border-radius:10px;padding:12px 14px;margin:10px 0;">
          <div style="font-weight:700;color:#33507e;margin-bottom:6px;">{escape(nm)}</div>
          <div class="frol-row">
            <div><label class="frol-fld">Wake</label>
              <input class="frol-input" type="time" data-step="2" data-key="{escape(nm, quote=True)}__wake_time"
                     value="{escape(wake, quote=True)}"></div>
            <div><label class="frol-fld">Nap window</label>
              <input class="frol-input" type="text" data-step="2" data-key="{escape(nm, quote=True)}__nap_time"
                     value="{escape(nap, quote=True)}" placeholder="13:00–15:00"></div>
            <div><label class="frol-fld">Bedtime</label>
              <input class="frol-input" type="time" data-step="2" data-key="{escape(nm, quote=True)}__bed_time"
                     value="{escape(bed, quote=True)}"></div>
          </div>
          <label class="frol-fld" style="margin-top:8px;">Needs / quirks <span style="font-weight:400;color:#888;">(food, sensory, comfort)</span></label>
          <textarea class="frol-textarea" data-step="2" data-key="{escape(nm, quote=True)}__needs"
                    placeholder="e.g., needs water bottle for sleep, gets fussy without afternoon outdoor time">{escape(needs)}</textarea>
        </div>
        """
    info_card = render_reflection_card(
        "Why we start with the little ones",
        "<p>Babies and toddlers don't bend to schedules — schedules bend to "
        "them. Setting nap windows, mealtime needs, and quiet hours <em>first</em> "
        "means the rest of the day fits around what's already non-negotiable.</p>"
        "<p style='margin-top:8px;'><strong>Developmental framework:</strong> "
        "0–2 needs sleep + feeding rhythm. 2–4 needs predictable routines + "
        "outdoor time. 4–6 needs structured play + independence-building. "
        "Each child's rhythms here will inform §11 Build Your Day.</p>",
        key="sec2_intro",
    )
    body = f"""
      {info_card}
      {rows}
      <p class="frol-help" style="margin-top:12px;">
        These rhythms anchor §11 Build Your Day — quiet hours auto-block during
        nap windows, and meals get scheduled around little-one feeding times.
      </p>
    """
    return _section_chrome(2, "The Little Ones First",
        "Naps, bedtimes, and the needs that anchor everything else.",
        body, mode, progress, lucy_visible=True)


def render_section_3(progress: dict, mode: str) -> str:
    """V2 §3 — Fixed Commitments: recurring commitments + John's work +
    driving/errands. Seeded from V1 step_2.fixed_commitments where present."""
    wake_school   = _sv(progress, 3, "wake_school_adults",   "06:00")
    wake_weekend  = _sv(progress, 3, "wake_weekend_adults",  "07:00")
    bed_adults    = _sv(progress, 3, "bed_adults",           "22:30")
    fixed         = _sv(progress, 3, "fixed_commitments",    "")
    john_work     = _sv(progress, 3, "john_work_schedule",   "")
    driving       = _sv(progress, 3, "driving_errands",      "")
    refl = render_reflection_card(
        "Fixed commitments first",
        "<p>Some things on your week are already decided — Mass times, work "
        "hours, sports practice, lessons, appointments. Pinning them down "
        "<em>before</em> we plan flex time keeps us honest about how much "
        "space the family actually has.</p>",
        key="sec3_intro",
    )
    body = f"""
      {refl}
      <h3>Wake &amp; sleep anchors</h3>
      <div class="frol-row">
        <div><label class="frol-fld">Adults wake (school days)</label>
          <input class="frol-input" type="time" data-step="3" data-key="wake_school_adults"
                 value="{escape(wake_school, quote=True)}"></div>
        <div><label class="frol-fld">Adults wake (weekends)</label>
          <input class="frol-input" type="time" data-step="3" data-key="wake_weekend_adults"
                 value="{escape(wake_weekend, quote=True)}"></div>
        <div><label class="frol-fld">Adults bedtime</label>
          <input class="frol-input" type="time" data-step="3" data-key="bed_adults"
                 value="{escape(bed_adults, quote=True)}"></div>
      </div>

      <label class="frol-fld" style="margin-top:18px;">Recurring weekly commitments</label>
      <p class="frol-help">One per line. Format: <code>Day HH:MM Title</code>
        (e.g., <code>Wed 09:30 Piano lessons</code>, <code>Mon 18:00 CAP</code>).</p>
      <textarea class="frol-textarea" data-step="3" data-key="fixed_commitments"
                placeholder="Mon 18:00 CAP (JP, Joe, John)&#10;Wed 09:30 Piano lessons&#10;Sun 10:30 Mass">{escape(fixed)}</textarea>

      <label class="frol-fld" style="margin-top:18px;">John's work schedule</label>
      <p class="frol-help">Days, hours, work-from-home pattern, anything that
        affects who's home with the kids.</p>
      <textarea class="frol-textarea" data-step="3" data-key="john_work_schedule"
                placeholder="Mon–Fri 8:00–17:00, WFH Wed; gym Tue+Thu 17:30 → home ~18:30">{escape(john_work)}</textarea>

      <label class="frol-fld" style="margin-top:18px;">Driving / errand patterns</label>
      <p class="frol-help">Recurring drives — school drop-off, weekly grocery
        run, sports carpool — and who usually handles them.</p>
      <textarea class="frol-textarea" data-step="3" data-key="driving_errands"
                placeholder="Tue 15:00 Joseph sports carpool (Lauren)&#10;Fri 10:00 weekly Aldi run (Lauren + Michael)">{escape(driving)}</textarea>
    """
    return _section_chrome(3, "Fixed Commitments",
        "What's already on the calendar before we add anything else.",
        body, mode, progress, lucy_visible=True)


def render_section_4(progress: dict, mode: str) -> str:
    """V2 §4 — Prayer. Introduces Sister Mary. Supports a 'can combine with
    another' linking textarea so users can note prayers that double up
    (e.g., Angelus during lunch)."""
    morning_time   = _sv(progress, 4, "morning_time",       "07:15")
    morning_prayer = _sv(progress, 4, "morning_prayer",     "Lauds")
    morning_multi  = _sv(progress, 4, "morning_prayers_multi", []) or []
    evening_multi  = _sv(progress, 4, "evening_prayers_multi", []) or []
    night_multi    = _sv(progress, 4, "night_prayers_multi",   []) or []
    angelus_times  = _sv(progress, 4, "angelus_times",      []) or []
    divine_mercy   = _sv(progress, 4, "divine_mercy_3pm",   "")
    vespers        = _sv(progress, 4, "vespers",            "")
    examen         = _sv(progress, 4, "examen",             "")
    other_devo     = _sv(progress, 4, "other_devotions",    "")
    combine_notes  = _sv(progress, 4, "combine_notes",      "")
    def _cb_v2(key: str, options: list, current: list) -> str:
        cur = set(current or [])
        out = []
        for opt in options:
            checked = "checked" if opt in cur else ""
            out.append(
                f'<label style="display:inline-flex;align-items:center;gap:6px;'
                f'background:#f3f6fb;border:1px solid #d6e0f0;border-radius:999px;'
                f'padding:4px 12px;font-size:0.88em;cursor:pointer;margin:3px;">'
                f'<input type="checkbox" data-step="4" data-key="{escape(key, quote=True)}" '
                f'data-multi="1" value="{escape(opt, quote=True)}" {checked}>'
                f'{escape(opt)}</label>'
            )
        return "".join(out)
    sister = render_companion_intro_card(
        "Sister Mary", "🕊️",
        "Catholic prayer companion — she'll help you build a sustainable prayer rule, "
        "track liturgical seasons, and adapt as your family grows.",
        href="/sister-mary", accent="#5b3a8a", light="#f3eff8",
    )
    refl = render_reflection_card(
        "Prayer is the spine of the day",
        "<p>A rule of life isn't a schedule with prayer sprinkled on top — it's "
        "a prayer life with everything else built around it. Start with the "
        "anchors (morning offering, Angelus, examen) and let the family rhythm "
        "form around them, not the other way around.</p>",
        key="sec4_intro",
    )
    body = f"""
      {sister}
      {refl}

      <label class="frol-fld">Morning prayer time</label>
      <div class="frol-row">
        <div><input class="frol-input" type="time" data-step="4" data-key="morning_time"
                    value="{escape(morning_time, quote=True)}"></div>
        <div><input class="frol-input" type="text" data-step="4" data-key="morning_prayer"
                    placeholder="Lauds / Morning Offering / etc."
                    value="{escape(morning_prayer, quote=True)}"></div>
      </div>

      <label class="frol-fld" style="margin-top:14px;">Morning prayers <span style="font-weight:400;color:#888;">(check all)</span></label>
      {_cb_v2("morning_prayers_multi", ["Morning Offering", "Divine Office", "Rosary", "Daily Mass", "Bible reading", "Lectio Divina"], morning_multi)}

      <label class="frol-fld" style="margin-top:14px;">Angelus times <span style="font-weight:400;color:#888;">(traditional: 6am, noon, 6pm)</span></label>
      {_cb_v2("angelus_times", ["06:00", "12:00", "18:00"], angelus_times)}

      <label class="frol-fld" style="margin-top:14px;">Afternoon devotions</label>
      <div style="display:flex;gap:18px;flex-wrap:wrap;font-weight:normal;">
        <label><input type="checkbox" data-step="4" data-key="divine_mercy_3pm" value="yes" {'checked' if divine_mercy == "yes" else ''}> Divine Mercy at 3:00 PM</label>
        <label><input type="checkbox" data-step="4" data-key="vespers" value="yes" {'checked' if vespers == "yes" else ''}> Vespers</label>
        <label><input type="checkbox" data-step="4" data-key="examen" value="yes" {'checked' if examen == "yes" else ''}> Examen</label>
      </div>

      <label class="frol-fld" style="margin-top:14px;">Evening prayers</label>
      {_cb_v2("evening_prayers_multi", ["Family Rosary", "Vespers", "Bible reading", "Spiritual reading", "Holy Hour"], evening_multi)}

      <label class="frol-fld" style="margin-top:14px;">Night prayers</label>
      {_cb_v2("night_prayers_multi", ["Compline", "Examination of conscience", "Night prayers", "Marian antiphon"], night_multi)}

      <label class="frol-fld" style="margin-top:14px;">Other devotions / seasonal practices</label>
      <textarea class="frol-textarea" data-step="4" data-key="other_devotions"
                placeholder="First-Friday Mass, Lenten Stations, Sunday Mass at 12:30, etc.">{escape(other_devo)}</textarea>

      <label class="frol-fld" style="margin-top:14px;">Prayers that combine with something else <span style="font-weight:400;color:#888;">(saves time)</span></label>
      <p class="frol-help">e.g., "Angelus during lunch", "Rosary during the
        afternoon walk", "Examen while tucking in the boys".</p>
      <textarea class="frol-textarea" data-step="4" data-key="combine_notes"
                placeholder="Angelus during lunch&#10;Rosary on the school drive">{escape(combine_notes)}</textarea>
    """
    return _section_chrome(4, "Prayer",
        "The spine of the day. Pin down the anchors first; everything else builds around them.",
        body, mode, progress, lucy_visible=True)


def render_section_5(progress: dict, mode: str) -> str:
    """V2 §5 — Meals. Introduces Lorenzo. Covers breakfast / lunch / dinner /
    snack / meal-prep / batch / grocery."""
    breakfast_time = _sv(progress, 5, "breakfast_time", "08:30")
    breakfast_who  = _sv(progress, 5, "breakfast_who",  "")
    lunch_time     = _sv(progress, 5, "lunch_time",     "12:00")
    lunch_together = _sv(progress, 5, "lunch_together", "")
    dinner_time    = _sv(progress, 5, "dinner_time",    "17:30")
    dinner_who     = _sv(progress, 5, "dinner_who",     "")
    snack_times    = _sv(progress, 5, "snack_times",    "")
    meal_prep_who  = _sv(progress, 5, "meal_prep_who",  []) or []
    batch_days     = _sv(progress, 5, "batch_cook_days", []) or []
    grocery_day    = _sv(progress, 5, "grocery_day",    "")
    grocery_who    = _sv(progress, 5, "grocery_who",    "")
    morning_prep   = _sv(progress, 5, "morning_dinner_prep", "")
    def _cb(key: str, options: list, current: list) -> str:
        cur = set(current or [])
        out = []
        for opt in options:
            checked = "checked" if opt in cur else ""
            out.append(
                f'<label style="display:inline-flex;align-items:center;gap:6px;'
                f'background:#fbf6ee;border:1px solid #ead9b8;border-radius:999px;'
                f'padding:4px 12px;font-size:0.88em;cursor:pointer;margin:3px;">'
                f'<input type="checkbox" data-step="5" data-key="{escape(key, quote=True)}" '
                f'data-multi="1" value="{escape(opt, quote=True)}" {checked}>'
                f'{escape(opt)}</label>'
            )
        return "".join(out)
    lorenzo = render_companion_intro_card(
        "Lorenzo", "🍝",
        "Personal chef AI — he plans meals against your week, suggests batch-cook "
        "days, and pulls recipes from your saved collection.",
        href="/lorenzo", accent="#8a4a2a", light="#fbeee0",
    )
    refl = render_reflection_card(
        "Meals are the day's heartbeat",
        "<p>Three meals + snacks shape the day more than any other anchor. "
        "Get them honest first — when you actually eat, who cooks, what days "
        "you batch — then schedule everything else around them.</p>",
        key="sec5_intro",
    )
    body = f"""
      {lorenzo}
      {refl}

      <label class="frol-fld">Breakfast</label>
      <div class="frol-row">
        <div><input class="frol-input" type="time" data-step="5" data-key="breakfast_time"
                    value="{escape(breakfast_time, quote=True)}"></div>
        <div><input class="frol-input" type="text" data-step="5" data-key="breakfast_who"
                    placeholder="Who eats / cooks (e.g., Varies, Mom)"
                    value="{escape(breakfast_who, quote=True)}"></div>
      </div>

      <label class="frol-fld" style="margin-top:14px;">Lunch</label>
      <div class="frol-row">
        <div><input class="frol-input" type="time" data-step="5" data-key="lunch_time"
                    value="{escape(lunch_time, quote=True)}"></div>
        <div><input class="frol-input" type="text" data-step="5" data-key="lunch_together"
                    placeholder="Together? Split? On the go?"
                    value="{escape(lunch_together, quote=True)}"></div>
      </div>

      <label class="frol-fld" style="margin-top:14px;">Dinner</label>
      <div class="frol-row">
        <div><input class="frol-input" type="time" data-step="5" data-key="dinner_time"
                    value="{escape(dinner_time, quote=True)}"></div>
        <div><input class="frol-input" type="text" data-step="5" data-key="dinner_who"
                    placeholder="Who cooks (Mom, Dad, kids helping)"
                    value="{escape(dinner_who, quote=True)}"></div>
      </div>

      <label class="frol-fld" style="margin-top:14px;">Snack times</label>
      <input class="frol-input" type="text" data-step="5" data-key="snack_times"
             placeholder="10:30 AM, 3:00 PM"
             value="{escape(snack_times, quote=True)}">

      <label class="frol-fld" style="margin-top:18px;">Morning dinner prep?</label>
      <div style="font-weight:normal;">
        <label style="margin-right:18px;"><input type="radio" data-step="5" data-key="morning_dinner_prep" value="yes" {'checked' if morning_prep == "yes" else ''}> Yes — prep dinner ingredients in the morning</label>
        <label><input type="radio" data-step="5" data-key="morning_dinner_prep" value="no" {'checked' if morning_prep == "no" else ''}> No</label>
      </div>

      <label class="frol-fld" style="margin-top:18px;">Who handles meal prep?</label>
      {_cb("meal_prep_who", ["Mom", "Dad", "Older children", "Whoever's home"], meal_prep_who)}

      <label class="frol-fld" style="margin-top:14px;">Batch-cook days</label>
      {_cb("batch_cook_days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], batch_days)}

      <label class="frol-fld" style="margin-top:14px;">Grocery day &amp; who shops</label>
      <div class="frol-row">
        <div><input class="frol-input" type="text" data-step="5" data-key="grocery_day"
                    placeholder="Friday morning" value="{escape(grocery_day, quote=True)}"></div>
        <div><input class="frol-input" type="text" data-step="5" data-key="grocery_who"
                    placeholder="Lauren + Michael" value="{escape(grocery_who, quote=True)}"></div>
      </div>
    """
    return _section_chrome(5, "Meals",
        "When you eat, who cooks, what days you batch — the day's heartbeat.",
        body, mode, progress, lucy_visible=True)


def render_section_6(progress: dict, mode: str) -> str:
    """V2 §6 — School. Introduces Father Gregory. Captures format (Solo /
    Mom-led / Paired / Group), JP per-subject hour-tracking toggle (writes
    to hour_tracking categories at finalize), sibling-pairing suggestion."""
    members = _v2_members(progress)
    member_names = [m.get("name","") for m in members if isinstance(m, dict) and m.get("name")]
    homeschool_kids = _sv(progress, 6, "homeschool_kids", []) or []
    subjects        = _sv(progress, 6, "subjects_multi", []) or []
    chore_blocks    = _sv(progress, 6, "chore_time_blocks", []) or []
    parent_wfh      = _sv(progress, 6, "parent_wfh", "")
    school_format   = _sv(progress, 6, "school_format", "")
    jp_subjects_tracked = _sv(progress, 6, "jp_subjects_tracked", []) or []
    pairing_notes   = _sv(progress, 6, "pairing_notes", "")
    dev_check       = _sv(progress, 6, "developmental_check", "")
    jp_tracking_on  = _sv(progress, 1, "jp_hour_tracking", "") == "yes"

    def _cb(key: str, options: list, current: list) -> str:
        cur = set(current or [])
        out = []
        for opt in options:
            checked = "checked" if opt in cur else ""
            out.append(
                f'<label style="display:inline-flex;align-items:center;gap:6px;'
                f'background:#eef4ed;border:1px solid #c9d9c5;border-radius:999px;'
                f'padding:4px 12px;font-size:0.88em;cursor:pointer;margin:3px;">'
                f'<input type="checkbox" data-step="6" data-key="{escape(key, quote=True)}" '
                f'data-multi="1" value="{escape(opt, quote=True)}" {checked}>'
                f'{escape(opt)}</label>'
            )
        return "".join(out)

    gregory = render_companion_intro_card(
        "Father Gregory", "📚",
        "Homeschool academic headmaster — he'll help with curriculum design, "
        "weekly lesson planning, assignment analysis, and per-student pacing.",
        href="/father-gregory", accent="#2e5d3b", light="#e8efe5",
    )
    refl = render_reflection_card(
        "School in a homeschool is a verb",
        "<p>The shape of your school day matters more than the curriculum. "
        "How much is Solo (independent work), Mom-led (taught live), Paired "
        "(sibling-shadowing), and Group (whole-family read-alouds)? Most "
        "families find their best week mixes all four.</p>",
        key="sec6_intro",
    )
    jp_section = ""
    if jp_tracking_on:
        full_subjects = ["Math", "Religion", "Reading", "Writing", "Science",
                         "History", "Latin", "Art", "Music", "PE", "Logic", "Geography"]
        jp_section = f"""
        <div style="background:#fff4e0;border:1px solid #ead9b8;border-left:4px solid #c89c4a;
                    border-radius:10px;padding:12px 14px;margin:14px 0;">
          <div style="font-weight:700;color:#7d5a1f;">JP hour tracking — choose subjects</div>
          <p style="font-size:0.88em;color:#3f3220;margin:6px 0 8px;">
            (You turned this on in §1.) Each subject you check becomes a tracked
            category in JP's hour ledger — visible from his student portal in Phase 5.
          </p>
          {_cb("jp_subjects_tracked", full_subjects, jp_subjects_tracked)}
        </div>
        """
    pair_card = render_reflection_card(
        "Sibling pairing — Michael with the older boys",
        "<p>Suggestions for the McAdams house: Michael can shadow Joseph for "
        "morning read-alouds and Math review. James naps during Latin and "
        "Logic — good blocks for JP independent work. Pairing notes below "
        "feed §11 Build Your Day.</p>",
        key="sec6_pairing",
        open_first_visit=False,
    )
    dev_card = render_reflection_card(
        "Developmental check",
        "<p>Quick sanity check before §11: is each child's school load matched "
        "to their stage? K–2 = play + reading. 3–5 = skill drills + curiosity. "
        "6–8 = abstract reasoning. 9–12 = mastery + responsibility. Adjust "
        "the notes below.</p>",
        key="sec6_dev",
        open_first_visit=False,
    )
    body = f"""
      {gregory}
      {refl}

      <label class="frol-fld">Which children are being homeschooled?</label>
      {_cb("homeschool_kids", member_names, homeschool_kids)}

      <label class="frol-fld" style="margin-top:14px;">School format <span style="font-weight:400;color:#888;">(check all that apply)</span></label>
      {_cb("school_format", ["Solo / independent", "Mom-led / taught live", "Paired / sibling shadowing", "Group / whole-family read-alouds"], [school_format] if isinstance(school_format, str) and school_format else (school_format or []))}

      <label class="frol-fld" style="margin-top:14px;">Subjects this year</label>
      {_cb("subjects_multi", ["Math", "Religion", "Reading", "Writing", "Science", "History", "Latin", "Art", "Music", "PE", "Logic", "Geography"], subjects)}

      <label class="frol-fld" style="margin-top:14px;">Chore time blocks during the school day</label>
      {_cb("chore_time_blocks", ["Morning", "Mid-morning break", "Lunch", "After school", "Evening"], chore_blocks)}

      <label class="frol-fld" style="margin-top:14px;">Parent work-from-home / check-in pattern</label>
      <textarea class="frol-textarea" data-step="6" data-key="parent_wfh"
                placeholder="2:30–4 work with the boys and check school work; 11 Lauren checks school work">{escape(parent_wfh)}</textarea>

      {jp_section}
      {pair_card}
      <label class="frol-fld">Pairing &amp; sibling-shadow notes</label>
      <textarea class="frol-textarea" data-step="6" data-key="pairing_notes"
                placeholder="Michael shadows Joseph for read-alouds; James naps during JP Latin">{escape(pairing_notes)}</textarea>

      {dev_card}
      <label class="frol-fld">Developmental notes / adjustments</label>
      <textarea class="frol-textarea" data-step="6" data-key="developmental_check"
                placeholder="JP ready for more Latin; Joseph needs slower Math pacing">{escape(dev_check)}</textarea>
    """
    return _section_chrome(6, "School",
        "Format, subjects, sibling-pairing — and (if JP's tracking hours) which subjects count.",
        body, mode, progress, lucy_visible=True)


def _seed_chores_for_section7(progress: dict) -> dict:
    """Build the section_7 seed by reading existing chores.json. Idempotent —
    only fills section_7.chores if absent."""
    from data_helpers import load_chores_data
    sec7 = progress.setdefault("data", {}).setdefault("section_7", {})
    if sec7.get("chores"):
        return sec7
    raw = load_chores_data() or {}
    chores = {}
    # boys
    for nm, p in (raw.get("boys") or {}).items():
        if isinstance(p, dict):
            chores[nm] = p
    # lauren
    if isinstance(raw.get("lauren"), dict):
        chores["Lauren"] = raw.get("lauren")
    sec7["chores"] = chores
    return sec7


def _chore_item_text(item) -> str:
    if isinstance(item, dict):
        return item.get("text", "") or ""
    return str(item or "")


def _bucket_textarea(person: str, bucket_key: str, sub_key: str,
                     items: list, placeholder: str = "") -> str:
    """One textarea representing a single chore list. data-key is
    'chores__{person}__{bucket}__{sub_key}' and the save handler will split
    on newlines at finalize time."""
    val = "\n".join(_chore_item_text(it) for it in (items or []) if _chore_item_text(it).strip())
    key = f"chores__{person}__{bucket_key}__{sub_key}"
    safe_ph = escape(placeholder, quote=True)
    return f"""
      <div style="margin:6px 0;">
        <label class="frol-fld" style="font-weight:600;color:#33507e;">
          {escape(person)} <span style="font-weight:400;color:#888;">· {escape(sub_key)}</span>
        </label>
        <textarea class="frol-textarea" rows="3"
                  data-step="7" data-key="{escape(key, quote=True)}"
                  placeholder="{safe_ph}">{escape(val)}</textarea>
      </div>
    """


_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_WEEK_BUCKETS = ["week_1", "week_2", "week_3", "week_4"]
_SEASONS = ["spring", "summer", "fall", "winter"]
_MONTHS_LC = ["january", "february", "march", "april", "may", "june",
              "july", "august", "september", "october", "november", "december"]


def render_section_7(progress: dict, mode: str) -> str:
    """V2 §7 — Chores & Household: 5 sub-builders (Daily / Weekly / Monthly /
    Seasonal / Annual), seeded from chores.json, plus a grooming subsection
    that tags items with `is_grooming` at finalize-save time."""
    sec7 = _seed_chores_for_section7(progress)
    chores = sec7.get("chores") or {}
    grooming = sec7.get("grooming") or {}
    persons = list(chores.keys()) or ["JP", "Joseph", "Michael", "James", "Lauren"]

    refl = render_reflection_card(
        "Chores teach more than they clean",
        "<p>A chore is a small liturgy: it teaches that everyone serves, that "
        "the house is a shared good, and that work has a rhythm. We've seeded "
        "what's already in your chores list — adjust, add, remove. The grooming "
        "subsection at the bottom flags personal-care items so they surface as "
        "gentle nudges from Dr. Monica rather than chores.</p>",
        key="sec7_intro",
    )

    # Daily bucket
    daily_html = ""
    for nm in persons:
        items = (chores.get(nm) or {}).get("daily") or []
        daily_html += _bucket_textarea(nm, "daily", "daily", items,
            "One chore per line. Examples: Make bed, Daily Room Reset, Practice piano 15 min")

    # Weekly bucket — collapsible per person, with one textarea per weekday
    weekly_html = ""
    for nm in persons:
        wk = ((chores.get(nm) or {}).get("weekly") or {})
        if not isinstance(wk, dict): wk = {}
        sub = ""
        for day in _WEEKDAYS:
            items = wk.get(day) or []
            sub += _bucket_textarea(nm, "weekly", day, items, f"{day} chores, one per line")
        weekly_html += f"""
          <details style="background:#f6f8fc;border:1px solid #d8e1ef;border-radius:8px;
                          padding:8px 12px;margin:8px 0;">
            <summary style="cursor:pointer;font-weight:700;color:#33507e;">{escape(nm)} — weekly</summary>
            <div style="padding-top:8px;">{sub}</div>
          </details>
        """

    # Monthly — week_1..4
    monthly_html = ""
    for nm in persons:
        mn = ((chores.get(nm) or {}).get("monthly") or {})
        if not isinstance(mn, dict): mn = {}
        sub = ""
        for w in _WEEK_BUCKETS:
            items = mn.get(w) or []
            sub += _bucket_textarea(nm, "monthly", w, items, f"{w.replace('_',' ').title()} of the month")
        monthly_html += f"""
          <details style="background:#f6f8fc;border:1px solid #d8e1ef;border-radius:8px;
                          padding:8px 12px;margin:8px 0;">
            <summary style="cursor:pointer;font-weight:700;color:#33507e;">{escape(nm)} — monthly</summary>
            <div style="padding-top:8px;">{sub}</div>
          </details>
        """

    # Seasonal — 4 seasons
    seasonal_html = ""
    for nm in persons:
        sn = ((chores.get(nm) or {}).get("seasonal") or {})
        if not isinstance(sn, dict): sn = {}
        sub = ""
        for season in _SEASONS:
            items = sn.get(season) or []
            sub += _bucket_textarea(nm, "seasonal", season, items, f"{season.title()} chores")
        seasonal_html += f"""
          <details style="background:#f6f8fc;border:1px solid #d8e1ef;border-radius:8px;
                          padding:8px 12px;margin:8px 0;">
            <summary style="cursor:pointer;font-weight:700;color:#33507e;">{escape(nm)} — seasonal</summary>
            <div style="padding-top:8px;">{sub}</div>
          </details>
        """

    # Annual — 12 months
    annual_html = ""
    for nm in persons:
        an = ((chores.get(nm) or {}).get("annual") or {})
        if not isinstance(an, dict): an = {}
        sub = ""
        for month in _MONTHS_LC:
            items = an.get(month) or []
            sub += _bucket_textarea(nm, "annual", month, items, f"{month.title()} chores")
        annual_html += f"""
          <details style="background:#f6f8fc;border:1px solid #d8e1ef;border-radius:8px;
                          padding:8px 12px;margin:8px 0;">
            <summary style="cursor:pointer;font-weight:700;color:#33507e;">{escape(nm)} — annual</summary>
            <div style="padding-top:8px;">{sub}</div>
          </details>
        """

    # Grooming — per-person textarea (one per line); merged into is_grooming
    # flags at §13 finalize-save.
    grooming_html = ""
    for nm in persons:
        val = "\n".join(_chore_item_text(it) for it in (grooming.get(nm) or []))
        grooming_html += f"""
          <div style="margin:6px 0;">
            <label class="frol-fld" style="font-weight:600;color:#7d5a1f;">
              {escape(nm)} — personal grooming
            </label>
            <textarea class="frol-textarea" rows="2"
                      data-step="7" data-key="grooming__{escape(nm, quote=True)}"
                      placeholder="Brush teeth (morning + bed), Floss (Sun), Trim nails (Mon), Shower (Tue/Thu/Sat)">{escape(val)}</textarea>
          </div>
        """

    body = f"""
      {refl}

      <details open style="background:#ffffff;border:1px solid #d8e1ef;border-left:4px solid #4a6fa5;
                            border-radius:10px;padding:12px 16px;margin:14px 0;">
        <summary style="cursor:pointer;font-weight:700;color:#33507e;font-size:1.02em;">
          Daily chores
        </summary>
        <div style="padding-top:10px;">{daily_html}</div>
      </details>

      <details style="background:#ffffff;border:1px solid #d8e1ef;border-left:4px solid #4a6fa5;
                       border-radius:10px;padding:12px 16px;margin:14px 0;">
        <summary style="cursor:pointer;font-weight:700;color:#33507e;font-size:1.02em;">
          Weekly chores
        </summary>
        <div style="padding-top:10px;">{weekly_html}</div>
      </details>

      <details style="background:#ffffff;border:1px solid #d8e1ef;border-left:4px solid #4a6fa5;
                       border-radius:10px;padding:12px 16px;margin:14px 0;">
        <summary style="cursor:pointer;font-weight:700;color:#33507e;font-size:1.02em;">
          Monthly chores
        </summary>
        <div style="padding-top:10px;">{monthly_html}</div>
      </details>

      <details style="background:#ffffff;border:1px solid #d8e1ef;border-left:4px solid #4a6fa5;
                       border-radius:10px;padding:12px 16px;margin:14px 0;">
        <summary style="cursor:pointer;font-weight:700;color:#33507e;font-size:1.02em;">
          Seasonal chores
        </summary>
        <div style="padding-top:10px;">{seasonal_html}</div>
      </details>

      <details style="background:#ffffff;border:1px solid #d8e1ef;border-left:4px solid #4a6fa5;
                       border-radius:10px;padding:12px 16px;margin:14px 0;">
        <summary style="cursor:pointer;font-weight:700;color:#33507e;font-size:1.02em;">
          Annual chores
        </summary>
        <div style="padding-top:10px;">{annual_html}</div>
      </details>

      <details open style="background:#fbf6ee;border:1px solid #ead9b8;border-left:4px solid #c89c4a;
                            border-radius:10px;padding:12px 16px;margin:14px 0;">
        <summary style="cursor:pointer;font-weight:700;color:#7d5a1f;font-size:1.02em;">
          Personal grooming
        </summary>
        <p class="frol-help" style="margin-top:8px;">These items are stored as
          chores but tagged so Dr. Monica surfaces them as gentle nudges
          (e.g., "Time to brush teeth") rather than as task-list items.</p>
        <div style="padding-top:6px;">{grooming_html}</div>
      </details>
    """
    return _section_chrome(7, "Chores &amp; Household",
        "Five sub-builders — Daily, Weekly, Monthly, Seasonal, Annual — plus personal grooming.",
        body, mode, progress, lucy_visible=True)


def render_section_8(progress: dict, mode: str) -> str:
    """V2 §8 — Exercise & Health. Introduces Coach + Dr. Monica. Captures
    exercise patterns, health setup, notification prefs (off by default), and
    up to 5 emergency contacts (only the first row shown by default)."""
    members = _v2_members(progress)
    member_names = [m.get("name","") for m in members if isinstance(m, dict) and m.get("name")]
    who_ex      = _sv(progress, 8, "who_exercises_multi", []) or []
    types_ex    = _sv(progress, 8, "types",               []) or []
    recurring   = _sv(progress, 8, "recurring_classes",   "")
    fam_or_ind  = _sv(progress, 8, "family_or_individual","")
    tracked     = _sv(progress, 8, "tracked_members",     []) or []
    appt_types  = _sv(progress, 8, "recurring_appt_types",[]) or []
    appt_notes  = _sv(progress, 8, "recurring_appts",     "")
    notif_ch    = _sv(progress, 8, "notif_channels",      []) or []
    notif_email = _sv(progress, 8, "notif_email",         "")
    notif_sms   = _sv(progress, 8, "notif_sms",           "")
    contacts    = _sv(progress, 8, "emergency_contacts",  []) or []
    while len(contacts) < 5:
        contacts.append({"name": "", "phone": "", "relation": ""})

    def _cb(key: str, options: list, current: list, accent: str = "#2e5d3b", light: str = "#eef4ed") -> str:
        cur = set(current or [])
        out = []
        for opt in options:
            checked = "checked" if opt in cur else ""
            out.append(
                f'<label style="display:inline-flex;align-items:center;gap:6px;'
                f'background:{light};border:1px solid {accent}33;border-radius:999px;'
                f'padding:4px 12px;font-size:0.88em;cursor:pointer;margin:3px;">'
                f'<input type="checkbox" data-step="8" data-key="{escape(key, quote=True)}" '
                f'data-multi="1" value="{escape(opt, quote=True)}" {checked}>'
                f'{escape(opt)}</label>'
            )
        return "".join(out)

    coach = render_companion_intro_card(
        "Coach", "🏋️",
        "Family fitness companion — designs strength + mobility plans, tracks "
        "consistency, and adapts to pregnancy / postpartum / kids' ages.",
        href="/coach", accent="#1f7a3a", light="#e8f5ec",
    )
    monica = render_companion_intro_card(
        "Dr. Monica", "🩺",
        "Pediatric + child-development companion — appointment reminders, "
        "milestone tracking, and gentle nudges on grooming + hygiene.",
        href="/dr-monica", accent="#9a3a6e", light="#f8eef3",
    )
    refl = render_reflection_card(
        "The body has its own liturgy",
        "<p>Strength, sleep, and movement aren't a separate domain — they're "
        "how the family <em>shows up</em> for everything else. Take this "
        "section honestly: what does your household actually do, and what's "
        "in the way of doing more?</p>",
        key="sec8_intro",
    )

    contact_rows = ""
    for i, c in enumerate(contacts):
        nm  = c.get("name","")  if isinstance(c, dict) else ""
        ph  = c.get("phone","") if isinstance(c, dict) else ""
        rel = c.get("relation","") if isinstance(c, dict) else ""
        # First row visible by default; rest hidden behind a Reveal toggle.
        hidden = "" if i == 0 else 'style="display:none;"'
        contact_rows += f"""
          <div class="frol-row frol-contact-row" {hidden}>
            <div><label class="frol-fld">Name</label>
              <input class="frol-input" data-step="8" data-list="emergency_contacts" data-idx="{i}"
                     data-key="name" value="{escape(nm, quote=True)}"></div>
            <div><label class="frol-fld">Phone</label>
              <input class="frol-input" data-step="8" data-list="emergency_contacts" data-idx="{i}"
                     data-key="phone" value="{escape(ph, quote=True)}"></div>
            <div><label class="frol-fld">Relation</label>
              <input class="frol-input" data-step="8" data-list="emergency_contacts" data-idx="{i}"
                     data-key="relation" placeholder="Spouse, neighbor, doctor"
                     value="{escape(rel, quote=True)}"></div>
          </div>
        """

    body = f"""
      {coach}
      {monica}
      {refl}

      <h3 style="margin-top:14px;color:#1f7a3a;">Exercise</h3>
      <label class="frol-fld">Who exercises regularly?</label>
      {_cb("who_exercises_multi", member_names or ["Mom", "Dad", "JP", "Joseph", "Michael", "James"], who_ex)}

      <label class="frol-fld" style="margin-top:12px;">Types</label>
      {_cb("types", ["Strength", "Walks", "Running", "Cycling", "Sports", "Yoga", "Stretching"], types_ex)}

      <label class="frol-fld" style="margin-top:12px;">Recurring classes / commitments</label>
      <textarea class="frol-textarea" data-step="8" data-key="recurring_classes"
                placeholder="John lifts Tue+Thu 17:30; JP soccer Wed 16:00">{escape(recurring)}</textarea>

      <label class="frol-fld" style="margin-top:12px;">Family or individual?</label>
      <div style="font-weight:normal;">
        <label style="margin-right:14px;"><input type="radio" data-step="8" data-key="family_or_individual" value="family"     {'checked' if fam_or_ind == "family" else ''}> Family</label>
        <label style="margin-right:14px;"><input type="radio" data-step="8" data-key="family_or_individual" value="individual" {'checked' if fam_or_ind == "individual" else ''}> Individual</label>
        <label><input type="radio" data-step="8" data-key="family_or_individual" value="mixed"      {'checked' if fam_or_ind == "mixed" else ''}> Mixed</label>
      </div>

      <h3 style="margin-top:22px;color:#9a3a6e;">Health setup</h3>
      <label class="frol-fld">Whose appointments are we tracking?</label>
      {_cb("tracked_members", member_names or ["Lauren", "John", "JP", "Joseph", "Michael", "James"], tracked, accent="#9a3a6e", light="#f8eef3")}

      <label class="frol-fld" style="margin-top:12px;">Recurring appointment types</label>
      {_cb("recurring_appt_types", ["Annual physicals", "Dental cleanings", "Eye exams", "Orthodontist", "Therapy", "Specialist follow-ups", "Well-baby checks"], appt_types, accent="#9a3a6e", light="#f8eef3")}

      <label class="frol-fld" style="margin-top:12px;">Recurring appointment notes</label>
      <textarea class="frol-textarea" data-step="8" data-key="recurring_appts"
                placeholder="Orthodontist adjustments for JP every 6 weeks">{escape(appt_notes)}</textarea>

      <h3 style="margin-top:22px;color:#33507e;">Notifications</h3>
      <p class="frol-help">All notifications are <strong>off</strong> by default — opt in below.</p>
      {_cb("notif_channels", ["email", "sms"], notif_ch, accent="#33507e", light="#eaf0fa")}
      <div class="frol-row" style="margin-top:8px;">
        <div><label class="frol-fld">Email</label>
          <input class="frol-input" type="email" data-step="8" data-key="notif_email"
                 value="{escape(notif_email, quote=True)}"></div>
        <div><label class="frol-fld">SMS</label>
          <input class="frol-input" type="tel" data-step="8" data-key="notif_sms"
                 value="{escape(notif_sms, quote=True)}"></div>
      </div>

      <h3 style="margin-top:22px;color:#c0392b;">Emergency contacts</h3>
      <p class="frol-help">Up to 5 contacts. We show one to start — click below for more.</p>
      <div id="frol-emergency-contacts">
        {contact_rows}
      </div>
      <button type="button" id="frol-add-contact" onclick="frolRevealContact()"
              style="background:none;border:1px dashed #c0392b;color:#c0392b;
                     border-radius:6px;padding:6px 12px;font-weight:600;
                     font-size:0.86em;cursor:pointer;margin-top:6px;">
        + Add another emergency contact
      </button>
    """
    return _section_chrome(8, "Exercise &amp; Health",
        "Movement, medical, notifications, and the people to call when things go sideways.",
        body, mode, progress, lucy_visible=True)


def render_section_9(progress: dict, mode: str) -> str:
    """V2 §9 — Rest / Free Time / Faith Life. Rest + traditions + marriage +
    faith life with feast-day flagging."""
    afternoon_rest = _sv(progress, 9, "afternoon_rest", "")
    date_night     = _sv(progress, 9, "date_night",     "")
    couple_time    = _sv(progress, 9, "couple_time",    "")
    traditions     = _sv(progress, 9, "traditions",     []) or []
    confession     = _sv(progress, 9, "confession_cadence", "")
    adoration      = _sv(progress, 9, "adoration_cadence",  "")
    service        = _sv(progress, 9, "service_notes",      "")
    feast_days     = _sv(progress, 9, "feast_days_flag",    "")

    def _cb(key: str, options: list, current: list) -> str:
        cur = set(current or [])
        out = []
        for opt in options:
            checked = "checked" if opt in cur else ""
            out.append(
                f'<label style="display:inline-flex;align-items:center;gap:6px;'
                f'background:#f3eff8;border:1px solid #d8cdec;border-radius:999px;'
                f'padding:4px 12px;font-size:0.88em;cursor:pointer;margin:3px;">'
                f'<input type="checkbox" data-step="9" data-key="{escape(key, quote=True)}" '
                f'data-multi="1" value="{escape(opt, quote=True)}" {checked}>'
                f'{escape(opt)}</label>'
            )
        return "".join(out)

    refl = render_reflection_card(
        "Rest is an act of trust",
        "<p>Sabbath, naps, slow Sundays, family game nights — these aren't "
        "luxuries you earn after the chores are done. They're how the family "
        "remembers it's loved by a God who rests. Build them in <em>first</em> "
        "and let the work fit around them.</p>",
        key="sec9_intro",
    )
    body = f"""
      {refl}

      <h3>Rest &amp; family rhythm</h3>
      <label class="frol-fld">Afternoon rest / quiet block</label>
      <input class="frol-input" type="text" data-step="9" data-key="afternoon_rest"
             placeholder="2 to 4" value="{escape(afternoon_rest, quote=True)}">

      <label class="frol-fld" style="margin-top:12px;">Family traditions</label>
      {_cb("traditions", ["Read-aloud", "Holy hour", "Game night", "Nature walk", "Family movie", "Sunday brunch", "Birthday rituals", "Liturgical year crafts"], traditions)}

      <h3 style="margin-top:18px;">Marriage</h3>
      <label class="frol-fld">Date night</label>
      <input class="frol-input" type="text" data-step="9" data-key="date_night"
             placeholder="Wednesday 5:30" value="{escape(date_night, quote=True)}">

      <label class="frol-fld" style="margin-top:12px;">Couple time / connection</label>
      <input class="frol-input" type="text" data-step="9" data-key="couple_time"
             placeholder="evening on the porch, morning coffee, etc."
             value="{escape(couple_time, quote=True)}">

      <h3 style="margin-top:18px;">Faith life</h3>
      <label class="frol-fld">Confession cadence</label>
      <input class="frol-input" type="text" data-step="9" data-key="confession_cadence"
             placeholder="Monthly first Saturday" value="{escape(confession, quote=True)}">

      <label class="frol-fld" style="margin-top:12px;">Adoration / holy hour cadence</label>
      <input class="frol-input" type="text" data-step="9" data-key="adoration_cadence"
             placeholder="Tue 9pm John, Sat morning family"
             value="{escape(adoration, quote=True)}">

      <label class="frol-fld" style="margin-top:12px;">Service / works of mercy</label>
      <textarea class="frol-textarea" data-step="9" data-key="service_notes"
                placeholder="Monthly food pantry, parish hospitality, visiting elderly">{escape(service)}</textarea>

      <label class="frol-fld" style="margin-top:12px;">Flag feast days for the family calendar?</label>
      <div style="font-weight:normal;">
        <label style="margin-right:14px;"><input type="radio" data-step="9" data-key="feast_days_flag" value="yes" {'checked' if feast_days == "yes" else ''}> Yes — surface upcoming feasts on the dashboard</label>
        <label><input type="radio" data-step="9" data-key="feast_days_flag" value="no" {'checked' if feast_days == "no" else ''}> No</label>
      </div>
    """
    return _section_chrome(9, "Rest, Free Time, Faith Life",
        "Sabbath, traditions, marriage, and the sacraments that shape the year.",
        body, mode, progress, lucy_visible=True)


def render_section_10(progress: dict, mode: str) -> str:
    """V2 §10 — Flex / Buffers / Seasonal. Captures transition buffers, flex
    blocks, energy levels (feeds AI scheduler), weekly reset, seasonal flags."""
    buffer_min   = _sv(progress, 10, "transition_buffer_min", "10")
    flex_blocks  = _sv(progress, 10, "flex_blocks",           "")
    energy       = _sv(progress, 10, "energy_levels",         {}) or {}
    weekly_reset = _sv(progress, 10, "weekly_reset",          "")
    seasonal     = _sv(progress, 10, "seasonal_flags",        []) or []

    def _cb(key: str, options: list, current: list) -> str:
        cur = set(current or [])
        out = []
        for opt in options:
            checked = "checked" if opt in cur else ""
            out.append(
                f'<label style="display:inline-flex;align-items:center;gap:6px;'
                f'background:#fbf6ee;border:1px solid #ead9b8;border-radius:999px;'
                f'padding:4px 12px;font-size:0.88em;cursor:pointer;margin:3px;">'
                f'<input type="checkbox" data-step="10" data-key="{escape(key, quote=True)}" '
                f'data-multi="1" value="{escape(opt, quote=True)}" {checked}>'
                f'{escape(opt)}</label>'
            )
        return "".join(out)

    energy_rows = ""
    for tod in ["morning", "midday", "afternoon", "evening"]:
        cur = (energy.get(tod) if isinstance(energy, dict) else "") or ""
        energy_rows += f"""
          <div style="display:flex;align-items:center;gap:10px;margin:6px 0;">
            <div style="width:90px;font-weight:600;color:#33507e;">{tod.title()}</div>
            <select class="frol-input" data-step="10" data-key="energy__{tod}">
              <option value="">—</option>
              <option value="high"   {'selected' if cur == "high" else ''}>High</option>
              <option value="medium" {'selected' if cur == "medium" else ''}>Medium</option>
              <option value="low"    {'selected' if cur == "low" else ''}>Low</option>
            </select>
          </div>
        """

    refl = render_reflection_card(
        "Buffers are not waste",
        "<p>The most common reason rules of life collapse: no buffer between "
        "blocks. Transitions take time — getting shoes on, finding the bag, "
        "settling the baby. Naming a transition buffer (5–15 min between "
        "blocks) and a few flex blocks per week is what keeps the rest of "
        "the rule alive.</p>",
        key="sec10_intro",
    )

    body = f"""
      {refl}

      <label class="frol-fld">Transition buffer between blocks <span style="font-weight:400;color:#888;">(minutes)</span></label>
      <input class="frol-input" type="number" min="0" max="60" data-step="10" data-key="transition_buffer_min"
             value="{escape(str(buffer_min), quote=True)}"
             style="max-width:120px;">
      <p class="frol-help">§11 Build Your Day will insert a gray buffer slot of
        this length between back-to-back activities.</p>

      <label class="frol-fld" style="margin-top:14px;">Weekly flex blocks <span style="font-weight:400;color:#888;">(named time + day)</span></label>
      <p class="frol-help">One per line. Format: <code>Day HH:MM Name</code>
        (e.g., <code>Sat 09:00 Catch-up block</code>).</p>
      <textarea class="frol-textarea" data-step="10" data-key="flex_blocks"
                placeholder="Sat 09:00 Catch-up block&#10;Wed 13:00 Anything-goes hour">{escape(flex_blocks)}</textarea>

      <label class="frol-fld" style="margin-top:14px;">Energy levels by time of day</label>
      <p class="frol-help">The AI scheduler uses these to suggest hard tasks in
        your high-energy windows and gentle tasks in your low ones.</p>
      {energy_rows}

      <label class="frol-fld" style="margin-top:14px;">Weekly reset ritual</label>
      <input class="frol-input" type="text" data-step="10" data-key="weekly_reset"
             placeholder="Sunday afternoon: plan the week, batch cook, family meeting"
             value="{escape(weekly_reset, quote=True)}">

      <label class="frol-fld" style="margin-top:14px;">Seasonal flags</label>
      <p class="frol-help">Check anything that genuinely changes the rhythm in
        that season — the AI will offer to re-evaluate your rule then.</p>
      {_cb("seasonal_flags", ["Advent slow-down", "Christmas / Octave", "Lenten fast", "Easter Octave", "Summer / no school", "Back-to-school", "Holy Week", "Liturgical New Year (Nov)"], seasonal)}
    """
    return _section_chrome(10, "Flex, Buffers &amp; Seasonal",
        "The breathing room that keeps the rule alive — and the seasons that re-shape it.",
        body, mode, progress, lucy_visible=True)


# Spec color palette (Section 11 timeline)
_TIMELINE_PALETTE = [
    ("prayer",     "Prayer",        "#4a6fa5"),  # Marian blue
    ("meal",       "Meal",          "#d4a017"),  # amber
    ("rest",       "Rest",          "#7fa686"),  # soft green
    ("personal",   "Personal",      "#c89c4a"),  # golden
    ("school",     "School",        "#e07b3a"),  # orange
    ("family",     "Family time",   "#b59cd6"),  # lavender
    ("chore",      "Chore",         "#d99aa8"),  # rose
    ("work",       "Work",          "#5b3a8a"),  # deep purple
    ("buffer",     "Buffer",        "#8a8a8a"),  # dark gray
    ("free",       "Free / open",   "#d8d8d8"),  # light gray
]
_PALETTE_BY_KEY = {k: (l, c) for k, l, c in _TIMELINE_PALETTE}

_TIMELINE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
                  "Friday", "Saturday", "Sunday"]


def _timeline_slots():
    """5:00 AM through 9:30 PM in 30-minute increments (34 slots)."""
    out = []
    for hour in range(5, 22):
        for minute in (0, 30):
            out.append(f"{hour:02d}{minute:02d}")
    return out


def _slot_to_label(slot_hhmm: str) -> str:
    h = int(slot_hhmm[:2]); m = int(slot_hhmm[2:])
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def render_section_11(progress: dict, mode: str) -> str:
    """V2 §11 — Build Your Day: a visual 5 AM–10 PM 30-minute timeline.
    Each slot shows day-of-week dropdown content. Per-day editable with
    activity label, category (color), assigned person, and a paired-with
    field for shadow activities. Gray buffer slots auto-suggested at the
    transition-buffer interval from §10."""
    sec11 = (progress.get("data", {}) or {}).get("section_11", {}) or {}
    cur_day = sec11.get("current_day") or "Monday"
    if cur_day not in _TIMELINE_DAYS:
        cur_day = "Monday"
    weekend_view = sec11.get("weekend_view", "") == "yes"
    per_person = (sec11.get("per_person_filter") or "").strip()
    placements = sec11.get(f"placements_{cur_day}") or {}
    buffer_min = int((progress.get("data", {}) or {}).get("section_10", {}).get("transition_buffer_min") or 10)

    members = _v2_members(progress)
    member_names = [m.get("name","") for m in members if isinstance(m, dict) and m.get("name")]

    refl = render_reflection_card(
        "The day, made visible",
        "<p>Here's where the rule becomes a picture. Click a slot to assign "
        "an activity, a category color, who's responsible, and (optionally) "
        "a paired sibling shadowing along. Gray buffer slots are auto-inserted "
        "between back-to-back activities at the buffer width you set in §10.</p>",
        key="sec11_intro",
    )

    # Day switcher
    day_btns = ""
    for d in _TIMELINE_DAYS:
        is_cur = d == cur_day
        day_btns += (
            f'<a href="/frol-wizard?step=11&amp;day={d}&amp;mode={escape(mode, quote=True)}" '
            f'style="display:inline-block;padding:6px 12px;margin:2px;'
            f'background:{"#4a6fa5" if is_cur else "#e8eef7"};'
            f'color:{"#fff" if is_cur else "#33507e"};'
            f'border-radius:6px;text-decoration:none;font-weight:700;'
            f'font-size:0.86em;">{d[:3]}</a>'
        )

    # Per-person filter dropdown
    person_opts = '<option value="">All people</option>'
    for nm in member_names:
        sel = "selected" if nm == per_person else ""
        person_opts += f'<option value="{escape(nm, quote=True)}" {sel}>{escape(nm)}</option>'

    # Color palette legend
    legend = ""
    for k, label, color in _TIMELINE_PALETTE:
        legend += (
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'margin:2px 6px 2px 0;font-size:0.8em;color:#555;">'
            f'<span style="display:inline-block;width:14px;height:14px;'
            f'background:{color};border-radius:3px;border:1px solid #00000022;"></span>'
            f'{escape(label)}</span>'
        )

    # Build slot rows
    slots = _timeline_slots()
    rows_html = ""
    last_activity_end_idx = -99
    for i, slot in enumerate(slots):
        placement = placements.get(slot) or {}
        label    = placement.get("label", "") if isinstance(placement, dict) else ""
        category = placement.get("category", "") if isinstance(placement, dict) else ""
        person   = placement.get("person", "") if isinstance(placement, dict) else ""
        paired   = placement.get("paired_with", "") if isinstance(placement, dict) else ""
        # Per-person filter: gray-out non-matching rows
        muted = bool(per_person and person and person.lower() != per_person.lower())
        # Auto-buffer hint: if previous row had a non-buffer activity and the
        # difference is exactly one 30-min slot and the current row is empty
        # and the buffer width is <= 30 min, show "buffer suggested" hint.
        show_buffer_hint = (not label and not category
                            and (i - last_activity_end_idx) == 1
                            and buffer_min and buffer_min <= 30)
        if label and category and category != "buffer":
            last_activity_end_idx = i
        # Determine color band
        _, color = _PALETTE_BY_KEY.get(category, ("", "#f4f4f4"))
        # Render category dropdown
        cat_opts = '<option value="">—</option>'
        for k, lab, _c in _TIMELINE_PALETTE:
            sel = "selected" if k == category else ""
            cat_opts += f'<option value="{escape(k, quote=True)}" {sel}>{escape(lab)}</option>'
        # Person dropdown
        pers_opts = '<option value="">—</option>'
        for nm in member_names:
            sel = "selected" if nm == person else ""
            pers_opts += f'<option value="{escape(nm, quote=True)}" {sel}>{escape(nm)}</option>'
        # Paired dropdown
        pair_opts = '<option value="">—</option>'
        for nm in member_names:
            sel = "selected" if nm == paired else ""
            pair_opts += f'<option value="{escape(nm, quote=True)}" {sel}>{escape(nm)}</option>'
        row_style = (f"background:{color}1a;border-left:4px solid {color};"
                     f"opacity:{'0.45' if muted else '1'};")
        buffer_chip = ""
        if show_buffer_hint:
            buffer_chip = (
                f'<span style="font-size:0.72em;color:#8a8a8a;margin-left:6px;'
                f'background:#eee;border-radius:3px;padding:2px 6px;">'
                f'buffer ({buffer_min} min)</span>'
            )
        rows_html += f"""
          <div class="frol-slot-row" data-slot="{slot}" style="display:grid;
                grid-template-columns:80px 1.5fr 1fr 1fr 1fr;gap:6px;
                align-items:center;padding:6px 8px;margin:2px 0;
                border-radius:6px;{row_style}">
            <div style="font-weight:700;color:#33507e;font-size:0.86em;">
              {escape(_slot_to_label(slot))}{buffer_chip}
            </div>
            <input class="frol-input" type="text"
                   data-step="11" data-list="placements_{escape(cur_day, quote=True)}"
                   data-idx="{slot}" data-key="label"
                   placeholder="Activity (e.g., Math, Rosary)"
                   value="{escape(label, quote=True)}">
            <select class="frol-input"
                    data-step="11" data-list="placements_{escape(cur_day, quote=True)}"
                    data-idx="{slot}" data-key="category">{cat_opts}</select>
            <select class="frol-input"
                    data-step="11" data-list="placements_{escape(cur_day, quote=True)}"
                    data-idx="{slot}" data-key="person">{pers_opts}</select>
            <select class="frol-input"
                    data-step="11" data-list="placements_{escape(cur_day, quote=True)}"
                    data-idx="{slot}" data-key="paired_with">{pair_opts}</select>
          </div>
        """

    body = f"""
      {refl}

      <div style="background:#f6f8fc;border:1px solid #d8e1ef;border-radius:8px;
                  padding:10px 14px;margin:10px 0;">
        <div style="margin-bottom:6px;">{day_btns}</div>
        <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
          <label style="font-size:0.88em;color:#555;font-weight:normal;">
            <input type="checkbox" data-step="11" data-key="weekend_view" value="yes"
                   {'checked' if weekend_view else ''}> Show weekend rhythm side-by-side
          </label>
          <label style="font-size:0.88em;color:#555;font-weight:normal;display:flex;
                        align-items:center;gap:6px;">
            Per-person filter
            <select class="frol-input" data-step="11" data-key="per_person_filter"
                    style="max-width:160px;">{person_opts}</select>
          </label>
        </div>
        <div style="margin-top:8px;">{legend}</div>
      </div>

      <div style="background:#fff;border:1px solid #d8e1ef;border-radius:8px;
                  padding:12px;margin:10px 0;">
        <div style="display:grid;grid-template-columns:80px 1.5fr 1fr 1fr 1fr;
                    gap:6px;padding:0 8px 6px;font-size:0.78em;color:#888;
                    font-weight:700;">
          <div>Time</div><div>Activity</div><div>Category</div><div>Person</div><div>Paired with</div>
        </div>
        {rows_html}
      </div>

      <p class="frol-help">Tap mode: type directly into any row to assign.
        Quick mode: use the "Common activity templates" list below to bulk-add.
        Paired activities (e.g., Michael shadowing Joseph for read-aloud) appear
        as a soft outline on the second person's row.</p>
    """
    return _section_chrome(11, f"Build Your Day — {cur_day}",
        "Click any slot to assign an activity, category, and person. The picture builds itself.",
        body, mode, progress, lucy_visible=True)


def _commitments_status(progress: dict) -> list:
    """Derive ✅/⚠️ status for each of the SEVEN_COMMITMENTS based on the
    collected V2 section data. Returns list of dicts with index, label,
    status ('ok' / 'warn'), fix_section (int), and reason (str)."""
    data = progress.get("data", {}) or {}
    s4  = data.get("section_4")  or {}
    s5  = data.get("section_5")  or {}
    s9  = data.get("section_9")  or {}
    s10 = data.get("section_10") or {}
    out = []
    def _has(v) -> bool:
        if isinstance(v, list):
            return any(str(x).strip() for x in v)
        if isinstance(v, str):
            return bool(v.strip())
        return bool(v)
    # 1. Daily prayer
    ok = (_has(s4.get("morning_prayer")) or _has(s4.get("morning_prayers_multi"))
          or _has(s4.get("angelus_times")))
    out.append({"idx": 1, "label": SEVEN_COMMITMENTS[0],
                "status": "ok" if ok else "warn", "fix_section": 4,
                "reason": "Anchored at " + (s4.get("morning_time") or "morning")
                          if ok else "No daily anchor set."})
    # 2. Sunday Mass + Adoration
    ok = (_has(s9.get("adoration_cadence"))
          or "mass" in (s4.get("other_devotions") or "").lower()
          or "Daily Mass" in (s4.get("morning_prayers_multi") or [])
          or "Holy Hour" in (s4.get("evening_prayers_multi") or []))
    out.append({"idx": 2, "label": SEVEN_COMMITMENTS[1],
                "status": "ok" if ok else "warn", "fix_section": 9,
                "reason": "Adoration / Mass cadence set." if ok
                          else "Add an Adoration cadence in §9."})
    # 3. Meals at common table
    ok = (_has(s5.get("dinner_time")) and (_has(s5.get("lunch_together"))
          or _has(s5.get("dinner_who"))))
    out.append({"idx": 3, "label": SEVEN_COMMITMENTS[2],
                "status": "ok" if ok else "warn", "fix_section": 5,
                "reason": ("Dinner at " + (s5.get("dinner_time") or "—") + ".") if ok
                          else "Set a dinner time and who cooks in §5."})
    # 4. Sabbath rest
    ok = _has(s9.get("afternoon_rest")) or _has(s10.get("weekly_reset"))
    out.append({"idx": 4, "label": SEVEN_COMMITMENTS[3],
                "status": "ok" if ok else "warn", "fix_section": 9,
                "reason": "Rest block and / or weekly reset defined." if ok
                          else "Define an afternoon rest in §9 or a weekly reset in §10."})
    # 5. Service
    ok = _has(s9.get("service_notes"))
    out.append({"idx": 5, "label": SEVEN_COMMITMENTS[4],
                "status": "ok" if ok else "warn", "fix_section": 9,
                "reason": "Service notes recorded." if ok
                          else "Name at least one work of mercy in §9."})
    # 6. Hospitality — heuristic: traditions mentioning brunch, dinner guests,
    # or any text in service_notes mentioning "guest", "host", "neighbor".
    trad = [str(t).lower() for t in (s9.get("traditions") or [])]
    notes_l = (s9.get("service_notes") or "").lower()
    ok = (any("brunch" in t or "dinner" in t for t in trad)
          or "guest" in notes_l or "host" in notes_l or "neighbor" in notes_l)
    out.append({"idx": 6, "label": SEVEN_COMMITMENTS[5],
                "status": "ok" if ok else "warn", "fix_section": 9,
                "reason": "Hospitality patterns noted." if ok
                          else "Note a hospitality habit in §9 (e.g., Sunday brunch, neighbor visits)."})
    # 7. Play, beauty, joy
    ok = _has(s9.get("traditions"))
    out.append({"idx": 7, "label": SEVEN_COMMITMENTS[6],
                "status": "ok" if ok else "warn", "fix_section": 9,
                "reason": ("Family traditions: " + ", ".join((s9.get("traditions") or [])[:3])) if ok
                          else "Add at least one family tradition in §9."})
    return out


def render_section_12(progress: dict, mode: str) -> str:
    """V2 §12 — Seven Commitments Check. Renders the Dominick seven with
    derived ✅/⚠️ status and one-tap deep-link 'Fix' buttons."""
    items = _commitments_status(progress)
    refl = render_reflection_card(
        "The Dominick Seven",
        "<p>Before you save, let's check the rule against the seven commitments "
        "Dominick names as the spine of a healthy Catholic family life. A ⚠️ "
        "doesn't mean your rule is wrong — it means we couldn't find the data "
        "yet. Click <em>Fix</em> to jump back and add it, or move on if it "
        "genuinely doesn't apply to your season.</p>",
        key="sec12_intro",
        attribution="— Adapted from Dominick's Seven Commitments",
    )
    rows = ""
    ok_count = sum(1 for it in items if it["status"] == "ok")
    for it in items:
        is_ok = it["status"] == "ok"
        icon  = "✅" if is_ok else "⚠️"
        accent = "#7fa686" if is_ok else "#c89c4a"
        light  = "#eef4ed" if is_ok else "#fbf6ee"
        fix_btn = ""
        if not is_ok:
            fix_btn = (
                f'<a href="/frol-wizard?step={it["fix_section"]}&amp;mode={escape(mode, quote=True)}" '
                f'style="background:#c89c4a;color:#fff;padding:6px 14px;border-radius:6px;'
                f'text-decoration:none;font-weight:700;font-size:0.85em;">Fix in §{it["fix_section"]}</a>'
            )
        rows += f"""
          <div style="background:{light};border:1px solid {accent}55;border-left:4px solid {accent};
                      border-radius:10px;padding:12px 14px;margin:8px 0;
                      display:flex;align-items:center;gap:12px;">
            <div style="font-size:1.4em;">{icon}</div>
            <div style="flex:1;">
              <div style="font-weight:700;color:#33507e;">{it["idx"]}. {escape(it["label"])}</div>
              <div style="font-size:0.86em;color:#555;margin-top:2px;">{escape(it["reason"])}</div>
            </div>
            {fix_btn}
          </div>
        """
    body = f"""
      {refl}
      <div style="background:#eaf0fa;border:1px solid #c8d6ec;border-radius:8px;
                  padding:10px 14px;margin:10px 0;font-weight:700;color:#33507e;">
        {ok_count} of 7 commitments anchored in your rule.
      </div>
      {rows}
    """
    return _section_chrome(12, "Seven Commitments Check",
        "How does your rule line up with the Dominick seven? Fix any gaps, or move on.",
        body, mode, progress, lucy_visible=True)


# ── §13 finalize-save ───────────────────────────────────────────────────────

def _parse_textarea_lines(text) -> list:
    if not text:
        return []
    if isinstance(text, list):
        return [str(t).strip() for t in text if str(t).strip()]
    return [ln.strip() for ln in str(text).splitlines() if ln.strip()]


def _slot_to_label_12h(slot: str) -> str:
    """Convert 'HHMM' → '6:00 AM' style label matching day_templates grid."""
    return _slot_to_label(slot)


def finalize_v2(progress: dict) -> dict:
    """Write all collected V2 data to their final destinations:
      - data/day_templates/{Mon..Sun}.json (backed up first)
      - data/chores.json (expanded, with is_grooming flags)
      - data/hour_tracking.json (JP per-subject categories)
      - data/app_settings.json (notification prefs)
      - data/prayer_intentions.json (if any other_devotions text)
      - data/frol_wizard_progress.json (marked finalized_at)
    Returns a dict of {target: status_str} for the §13 receipt view."""
    import os, shutil
    from datetime import datetime as _dt
    from data_helpers import (
        load_chores_data, save_chores_data,
        load_hour_tracking, save_hour_tracking,
    )
    from render_settings import load_app_settings, save_app_settings
    DAY_TEMPLATE_DIR = "data/day_templates"
    receipt = {}
    data = progress.get("data", {}) or {}
    stamp = _dt.now().strftime("%Y%m%d_%H%M%S")

    # 1) day_templates with backup
    try:
        backup_dir = os.path.join(DAY_TEMPLATE_DIR, f"_backup_{stamp}")
        os.makedirs(backup_dir, exist_ok=True)
        written = 0
        for day in _TIMELINE_DAYS:
            placements = (data.get("section_11") or {}).get(f"placements_{day}") or {}
            src = os.path.join(DAY_TEMPLATE_DIR, f"{day}.json")
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(backup_dir, f"{day}.json"))
            # Build grid keyed by person → {time_label: activity}
            grid = {}
            if placements:
                for slot, p in placements.items():
                    if not isinstance(p, dict):
                        continue
                    label = (p.get("label") or "").strip()
                    if not label:
                        continue
                    person = (p.get("person") or "").strip() or "Family"
                    time_label = _slot_to_label_12h(slot)
                    grid.setdefault(person, {})[time_label] = label
                    paired = (p.get("paired_with") or "").strip()
                    if paired and paired != person:
                        grid.setdefault(paired, {})[time_label] = f"(with {person}) {label}"
            if grid:
                with open(src, "w", encoding="utf-8") as f:
                    json.dump({"weekday": day, "grid": grid}, f, indent=2, ensure_ascii=False)
                written += 1
        receipt["day_templates"] = f"Backed up to {os.path.basename(backup_dir)}; wrote {written} day(s)."
    except Exception as e:
        receipt["day_templates"] = f"ERROR: {e}"

    # 2) chores.json — merge section_7 chores into existing structure +
    # apply is_grooming flags from section_7.grooming
    try:
        sec7 = data.get("section_7") or {}
        chores_raw = load_chores_data() or {}
        boys = chores_raw.setdefault("boys", {})
        # Iterate every key flat-saved by §7 (chores__{person}__{bucket}__{sub_key}).
        # If user typed into a textarea, save_section_field stored the value
        # under that key directly at the top level of section_7 (because we
        # didn't use list_/idx). Read those keys.
        flat = {k: v for k, v in sec7.items() if k.startswith("chores__")}
        # Group by (person, bucket)
        by_person = {}
        for k, v in flat.items():
            try:
                _, person, bucket, sub = k.split("__", 3)
            except ValueError:
                continue
            by_person.setdefault(person, {}).setdefault(bucket, {})[sub] = _parse_textarea_lines(v)
        # Apply
        for person, buckets in by_person.items():
            target = boys.setdefault(person, {}) if person != "Lauren" else chores_raw.setdefault("lauren", {})
            for bucket, sub_map in buckets.items():
                if bucket == "daily":
                    target["daily"] = sub_map.get("daily", [])
                else:
                    cur = target.setdefault(bucket, {})
                    if not isinstance(cur, dict): cur = {}
                    for sub, lines in sub_map.items():
                        cur[sub] = lines
                    target[bucket] = cur
        # Grooming flags
        grooming_flat = {k: v for k, v in sec7.items() if k.startswith("grooming__")}
        tagged = 0
        for k, v in grooming_flat.items():
            person = k.split("__", 1)[1]
            target = boys.get(person) if person != "Lauren" else chores_raw.get("lauren")
            if not isinstance(target, dict):
                continue
            wanted = set(_parse_textarea_lines(v))
            # Walk daily + weekly + monthly + seasonal + annual; if a string
            # item matches a wanted line (case-insensitive substring), upgrade
            # to {text, is_grooming: True}.
            def _upgrade_list(lst):
                nonlocal tagged
                if not isinstance(lst, list):
                    return lst
                out = []
                for it in lst:
                    txt = _chore_item_text(it)
                    if txt and any(w.lower() in txt.lower() for w in wanted):
                        out.append({"text": txt, "is_grooming": True}); tagged += 1
                    else:
                        out.append(it)
                return out
            target["daily"] = _upgrade_list(target.get("daily") or [])
            for bucket_key in ("weekly", "monthly", "seasonal", "annual"):
                bucket = target.get(bucket_key) or {}
                if isinstance(bucket, dict):
                    for sub, items in list(bucket.items()):
                        bucket[sub] = _upgrade_list(items)
                    target[bucket_key] = bucket
            # If no matches found, also append the wanted lines as new
            # is_grooming daily items so they always end up tagged.
            existing_texts = {_chore_item_text(it).lower() for it in (target.get("daily") or [])}
            for w in wanted:
                if w.lower() not in existing_texts:
                    target.setdefault("daily", []).append({"text": w, "is_grooming": True})
                    tagged += 1
        save_chores_data(chores_raw)
        receipt["chores"] = f"Updated chores for {len(by_person)} person(s); tagged {tagged} grooming item(s)."
    except Exception as e:
        receipt["chores"] = f"ERROR: {e}"

    # 3) hour_tracking — JP per-subject categories
    try:
        sec6 = data.get("section_6") or {}
        tracked_subjects = sec6.get("jp_subjects_tracked") or []
        jp_tracking_on = (data.get("section_1") or {}).get("jp_hour_tracking") == "yes"
        if jp_tracking_on and tracked_subjects:
            ht = load_hour_tracking() or {}
            jp = ht.setdefault("JP", {})
            for subj in tracked_subjects:
                s = jp.setdefault(subj, {"categories": [], "logs": []})
                if not isinstance(s.get("categories"), list): s["categories"] = []
                if subj not in s["categories"]:
                    s["categories"].append(subj)
            save_hour_tracking(ht)
            receipt["hour_tracking"] = f"JP tracking enabled for {len(tracked_subjects)} subject(s)."
        else:
            receipt["hour_tracking"] = "JP hour tracking off — skipped."
    except Exception as e:
        receipt["hour_tracking"] = f"ERROR: {e}"

    # 4) app_settings — notification prefs from §8
    try:
        sec8 = data.get("section_8") or {}
        app_settings = load_app_settings() or {}
        prefs = app_settings.setdefault("notification_prefs", {})
        prefs["channels"] = sec8.get("notif_channels") or []
        prefs["email"]    = sec8.get("notif_email") or ""
        prefs["sms"]      = sec8.get("notif_sms") or ""
        # Feast-day flag from §9
        sec9 = data.get("section_9") or {}
        if sec9.get("feast_days_flag") == "yes":
            app_settings["feast_days_on_dashboard"] = True
        save_app_settings(app_settings)
        receipt["app_settings"] = "Notification prefs + feast-day flag saved."
    except Exception as e:
        receipt["app_settings"] = f"ERROR: {e}"

    # 5) prayer_intentions — pull free-form 'other_devotions' as a starter
    # intention if there's no existing intentions yet.
    try:
        from data_helpers import load_prayer_intentions, save_prayer_intentions
        sec4 = data.get("section_4") or {}
        other = (sec4.get("other_devotions") or "").strip()
        if other:
            pi = load_prayer_intentions() or {}
            ongoing = pi.setdefault("ongoing", [])
            already = {(o.get("text") or "").strip().lower() for o in ongoing if isinstance(o, dict)}
            if other.lower() not in already:
                ongoing.append({"text": other, "added_at": _dt.now().isoformat(timespec="seconds"),
                                "source": "frol_wizard_v2"})
                save_prayer_intentions(pi)
                receipt["prayer_intentions"] = "Added 1 intention from §4."
            else:
                receipt["prayer_intentions"] = "Intention already present — skipped."
        else:
            receipt["prayer_intentions"] = "No free-form devotions to add."
    except Exception as e:
        receipt["prayer_intentions"] = f"ERROR: {e}"

    # 6) Mark wizard finalized
    try:
        progress["finalized_at"] = _dt.now().isoformat(timespec="seconds")
        if V2_TOTAL_SECTIONS not in (progress.get("completed_steps") or []):
            progress.setdefault("completed_steps", []).append(V2_TOTAL_SECTIONS)
        save_progress(progress)
        receipt["wizard"] = "Marked complete."
    except Exception as e:
        receipt["wizard"] = f"ERROR: {e}"

    return receipt


def render_section_13(progress: dict, mode: str) -> str:
    """V2 §13 — AI Review + Save. Three review cards (Multitasking /
    Developmental / Schedule optimization) shown as Accept / Modify / Skip,
    plus the Save button that runs finalize_v2()."""
    sec13 = (progress.get("data", {}) or {}).get("section_13", {}) or {}
    receipt = sec13.get("receipt") or {}
    finalized = bool(progress.get("finalized_at"))

    refl = render_reflection_card(
        "Before we save",
        "<p>Three quick AI-generated reviews of your rule, each as a card you "
        "can Accept, Modify, or Skip. None of them change your rule on their "
        "own — they're starting points to think with.</p>",
        key="sec13_intro",
        attribution="— Concept: Dominick's iterative-rule methodology",
    )

    # Heuristic review cards (no LLM call needed for these — they read the
    # data structure and produce specific observations).
    items = _commitments_status(progress)
    warn_count = sum(1 for it in items if it["status"] == "warn")
    members = _v2_members(progress)
    person_count = len([m for m in members if isinstance(m, dict) and m.get("name")])
    s11 = (progress.get("data", {}) or {}).get("section_11", {}) or {}
    placed_days = sum(1 for d in _TIMELINE_DAYS if (s11.get(f"placements_{d}") or {}))

    def _review_card(title: str, body: str, key: str) -> str:
        current = sec13.get(f"review_{key}", "")
        opts = [("accept", "Accept", "#7fa686"), ("modify", "Modify", "#c89c4a"), ("skip", "Skip", "#8a8a8a")]
        btns = ""
        for v, lab, color in opts:
            checked = "checked" if current == v else ""
            btns += (
                f'<label style="display:inline-flex;align-items:center;gap:6px;'
                f'background:#fff;border:1px solid {color}77;color:{color};border-radius:6px;'
                f'padding:6px 14px;margin-right:6px;font-weight:700;cursor:pointer;font-size:0.86em;">'
                f'<input type="radio" data-step="13" data-key="review_{escape(key, quote=True)}" '
                f'value="{v}" {checked}> {lab}</label>'
            )
        return f"""
          <div style="background:#f6f8fc;border:1px solid #d8e1ef;border-left:4px solid #4a6fa5;
                      border-radius:10px;padding:14px 16px;margin:10px 0;">
            <div style="font-weight:700;color:#33507e;font-size:1.02em;margin-bottom:6px;">{escape(title)}</div>
            <div style="font-size:0.92em;color:#444;line-height:1.55;">{body}</div>
            <div style="margin-top:10px;">{btns}</div>
          </div>
        """

    multi_body = (
        f"<p>Looking at §4 Prayer combine-notes and §5 Meals, your rule has "
        f"{'some' if (progress.get('data',{}).get('section_4') or {}).get('combine_notes') else 'no'} "
        f"explicit prayer-during-task pairings. Pairing prayer with existing "
        f"transitions (Angelus during lunch prep, Rosary during the school "
        f"drive) gets prayer in without adding minutes to the day.</p>"
    )
    dev_body = (
        f"<p>You have {person_count} family member(s) recorded. §2 Little Ones "
        f"captured rhythms for the youngest; §6 School set up paired-activity "
        f"slots for the older kids. The biggest developmental risk in this "
        f"rule is over-scheduling Michael (age ~5) — his stage is play + "
        f"outdoor time, not seated learning. Consider naming a daily outdoor "
        f"block for him in §11.</p>"
    )
    sched_body = (
        f"<p>You placed activities on <strong>{placed_days}</strong> of 7 days "
        f"in §11. You have <strong>{warn_count}</strong> commitment(s) "
        f"flagged ⚠️ in §12. The biggest schedule risk is back-to-back blocks "
        f"with no buffer — your §10 transition buffer is "
        f"<strong>{((progress.get('data',{}).get('section_10') or {}).get('transition_buffer_min') or 10)} minutes</strong>, "
        f"which is reasonable for a family of {person_count}.</p>"
    )

    receipt_html = ""
    if receipt:
        rows = ""
        for k, v in receipt.items():
            is_err = "ERROR" in str(v).upper()
            rows += (
                f'<tr><td style="padding:6px 10px;font-weight:700;color:#33507e;">{escape(k)}</td>'
                f'<td style="padding:6px 10px;color:{"#c0392b" if is_err else "#2e5d3b"};">{escape(str(v))}</td></tr>'
            )
        receipt_html = f"""
          <div style="background:#eef4ed;border:1px solid #c9d9c5;border-left:4px solid #7fa686;
                      border-radius:10px;padding:12px 16px;margin:10px 0;">
            <div style="font-weight:700;color:#2e5d3b;margin-bottom:8px;">Save receipt</div>
            <table style="border-collapse:collapse;width:100%;font-size:0.88em;">{rows}</table>
          </div>
        """

    save_btn = ""
    if not finalized:
        save_btn = f"""
          <div style="margin-top:18px;text-align:center;">
            <form method="POST" action="/frol-wizard" style="display:inline-block;">
              <input type="hidden" name="action"  value="finalize_v2">
              <input type="hidden" name="section" value="13">
              <input type="hidden" name="mode"    value="{escape(mode, quote=True)}">
              <button type="submit" class="frol-btn"
                      style="background:#4a6fa5;color:#fff;border-radius:8px;
                             padding:14px 28px;font-weight:700;font-size:1.05em;
                             border:none;cursor:pointer;">
                💾 Save my Rule of Life
              </button>
            </form>
            <p class="frol-help" style="margin-top:8px;">
              This writes your day templates (with backup), chores, hour-tracking
              categories, notification prefs, and prayer intentions.
            </p>
          </div>
        """
    else:
        save_btn = f"""
          <div style="margin-top:18px;text-align:center;background:#eef4ed;
                      border:1px solid #c9d9c5;border-radius:10px;padding:14px;">
            <div style="font-weight:700;color:#2e5d3b;font-size:1.05em;">
              ✅ Your Rule of Life is saved.
            </div>
            <div style="font-size:0.9em;color:#555;margin-top:6px;">
              Finalized at {escape(progress.get("finalized_at",""))}.
            </div>
            <a href="/" style="display:inline-block;margin-top:10px;background:#4a6fa5;
                                color:#fff;padding:10px 22px;border-radius:8px;
                                text-decoration:none;font-weight:700;">
              Go to home &rarr;
            </a>
          </div>
        """

    closing = render_reflection_card(
        "A rule is a starting place, not a prison",
        "<p>Your rule will breathe — feast days, illness, summer break, a new "
        "baby. Come back to the wizard any time and the values you've set "
        "here will still be here, ready to adjust. The rule serves the "
        "family; the family doesn't serve the rule.</p>",
        key="sec13_closing",
        attribution="— Dominick",
        open_first_visit=True,
    )

    body = f"""
      {refl}
      {_review_card("Multitasking review", multi_body, "multi")}
      {_review_card("Developmental review", dev_body, "dev")}
      {_review_card("Schedule optimization review", sched_body, "sched")}
      {receipt_html}
      {save_btn}
      {closing}
    """
    return _section_chrome(13, "AI Review &amp; Save",
        "Three reviews, then the Save button. After that, you're done.",
        body, mode, progress, lucy_visible=False)


# Dispatcher map — complete for Phase 4.
def _section_renderer(section: int):
    return {
        1: render_section_1,
        2: render_section_2,
        3: render_section_3,
        4: render_section_4,
        5: render_section_5,
        6: render_section_6,
        7: render_section_7,
        8: render_section_8,
        9: render_section_9,
        10: render_section_10,
        11: render_section_11,
        12: render_section_12,
        13: render_section_13,
    }.get(section)


def _section_placeholder(section: int, mode: str, progress: dict) -> str:
    """Stub for unbuilt sections so the dispatcher never 500s mid-rollout."""
    if not (1 <= section <= V2_TOTAL_SECTIONS):
        return render_landing(progress)
    title = next((t for (i, _slug, t, _sub) in V2_SECTIONS if i == section), f"Section {section}")
    sub   = next((s for (i, _slug, _t, s) in V2_SECTIONS if i == section), "")
    body = (
        f'<div class="frol-pop-note">This section is being built. Your existing '
        f'answers are safe — come back once the next update lands.</div>'
    )
    return _section_chrome(section, title, sub, body, mode, progress, lucy_visible=False)


# ── Step renderers ──────────────────────────────────────────────────────────

def _v(progress: dict, step: int, field: str, default=""):
    return ((progress.get("data", {}) or {}).get(f"step_{step}", {}) or {}).get(field, default)


def _settings_members() -> list:
    """Return existing family members from app_settings.json, if any."""
    try:
        with open(APP_SETTINGS_FILE, encoding="utf-8") as fh:
            s = json.load(fh)
    except Exception:
        return []
    bdays = s.get("child_birthdays", {}) or {}
    colors = s.get("child_colors", {}) or {}
    out = []
    for name, bd in bdays.items():
        out.append({"name": name, "role": "Child", "birthday": bd or "",
                    "color": (colors.get(name, {}) or {}).get("bg", "")})
    return out


def render_landing(progress: dict) -> str:
    have_key = has_anthropic_key()
    resume_html = ""
    cur = progress.get("current_step", 0) or 0
    if cur and not progress.get("finalized_at"):
        mode = progress.get("mode", "structured")
        resume_html = (
            f'<div class="frol-pop-note">Welcome back — you left off at '
            f'step {cur}. <a href="/frol-wizard?step={cur}&mode={escape(mode, quote=True)}"'
            f' style="color:#33507e;font-weight:700;">Continue</a> · '
            f'<a href="/frol-wizard?reset=1" style="color:#a0524a;">Start over</a></div>'
        )
    lucy_btn = ""
    if have_key:
        lucy_btn = (
            '<a href="/frol-wizard?step=1&mode=lucy" class="frol-btn" '
            'style="background:#7a4ea3;">Guide me with Lucy</a>'
        )
    else:
        lucy_btn = (
            '<span class="frol-btn" style="background:#bbb;cursor:not-allowed;" '
            'title="Add an Anthropic API key in Settings to enable Lucy mode.">'
            'Guide me with Lucy (API key required)</span>'
        )
    self_btn = ('<a href="/frol-wizard?step=1&mode=structured" class="frol-btn ghost">'
                "I'll set it up myself</a>")

    # Lucy intro — shown prominently when she'll be guiding the wizard.
    lucy_intro_html = ""
    if have_key:
        lucy_intro_html = """
        <div style="background:linear-gradient(135deg,#eef2fb,#e1e9f7);
                    border:1px solid #c8d6ec;border-left:4px solid #7a4ea3;
                    border-radius:12px;padding:18px 20px;margin:24px auto 0;
                    max-width:620px;text-align:left;">
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="font-size:1.6em;">&#10024;</div>
            <div>
              <div style="font-weight:700;color:#5a3a82;font-size:1.05em;">
                Lucy will guide you
              </div>
              <div style="font-size:0.92em;color:#444;margin-top:3px;">
                If you choose <em>Guide me with Lucy</em>, she'll walk you
                through every step — asking gentle questions, suggesting
                rhythms, and filling in answers as you talk. You can switch
                to the structured form at any time.
              </div>
            </div>
          </div>
        </div>
        """

    # Companions grid — soft cards, 2 columns, Marian-blue accents.
    companions = [
        ("&#10024;", "Lucy",           "Your family's personal assistant, always ready to help you think and plan.", "/lucy"),
        ("&#127860;", "Lorenzo",       "Meal planning and kitchen wisdom.",                                          "/lorenzo"),
        ("&#10016;", "Sister Mary",    "Spiritual companion and prayer guide.",                                      "/sister-mary"),
        ("&#128218;", "Father Gregory","Academic mentor for your children.",                                         "/gregory"),
        ("&#128170;", "Coach",         "Family fitness and wellness.",                                               "/programs"),
        ("&#127800;", "Dr. Monica",    "Family health and wellbeing.",                                               "/dr-monica"),
    ]
    comp_cards = []
    for icon, name, desc, href in companions:
        comp_cards.append(f"""
          <a href="{href}" target="_blank" style="text-decoration:none;color:inherit;
              background:#f6f8fc;border:1px solid #d8e1ef;border-left:3px solid #4a6fa5;
              border-radius:10px;padding:12px 14px;display:block;
              transition:background 0.15s,transform 0.15s;">
            <div style="display:flex;align-items:baseline;gap:8px;">
              <span style="font-size:1.05em;">{icon}</span>
              <span style="font-weight:700;color:#33507e;">{escape(name)}</span>
            </div>
            <div style="font-size:0.85em;color:#555;margin-top:4px;line-height:1.35;">
              {escape(desc)}
            </div>
          </a>
        """)
    companions_html = f"""
      <div style="margin:32px auto 0;max-width:620px;text-align:left;">
        <div style="font-size:0.78em;color:#7d7d7d;text-transform:uppercase;
                    letter-spacing:0.06em;font-weight:700;margin-bottom:10px;
                    text-align:center;">
          Meet your companions
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
                    gap:10px;">
          {''.join(comp_cards)}
        </div>
      </div>
    """

    # Seven-commitments cream card (Laura Dominick framing) — appears between
    # the subtitle and the mode buttons on the landing screen.
    commitments_li = "".join(
        f'<li style="margin:4px 0;">{escape(c)}</li>'
        for c in SEVEN_COMMITMENTS
    )
    commitments_card = f"""
      <div style="background:#fbf7ef;border:1px solid #ead9b8;border-left:4px solid #c89c4a;
                  border-radius:14px;padding:20px 26px;margin:22px auto 24px;
                  max-width:620px;text-align:left;">
        <div style="font-family:Georgia,serif;font-size:1.05em;color:#5a4520;
                    line-height:1.55;font-style:italic;">
          &ldquo;A Rule of Life is not a cage &mdash; it is a trellis. It gives the
          ordinary days of a family the shape that grace can climb.&rdquo;
        </div>
        <div style="margin-top:14px;font-weight:700;color:#7d5a1f;font-size:0.92em;
                    text-transform:uppercase;letter-spacing:0.04em;">
          Seven commitments
        </div>
        <ol style="margin:6px 0 0 22px;padding:0;color:#3f3220;font-size:0.95em;line-height:1.5;">
          {commitments_li}
        </ol>
        <div style="margin-top:14px;font-size:0.78em;color:#7d6a4a;font-style:italic;text-align:right;">
          Inspired by <em>A Plan for Joy in the Home</em>, Laura Dominick
        </div>
      </div>
    """

    return f"""
      <div class="frol-card" style="text-align:center;padding:46px 32px;">
        <h1 class="frol-title" style="font-size:2.1em;">Your Rule of Life</h1>
        <p class="frol-sub" style="font-size:1.08em;max-width:560px;margin:14px auto 6px;
                                    font-family:Georgia,serif;font-style:italic;color:#5a4a78;">
          A Workbook for Your Family
        </p>
        <p class="frol-sub" style="font-size:0.98em;max-width:560px;margin:0 auto 6px;">
          Your Rule of Life is the rhythm that holds your family's day. It's
          not a rigid schedule &mdash; it's a framework of love. Let's build
          yours together.
        </p>
        {commitments_card}
        {resume_html}
        <div style="display:flex;gap:14px;justify-content:center;
                    flex-wrap:wrap;margin-top:18px;">
          {lucy_btn}
          {self_btn}
        </div>
        <p style="margin-top:30px;font-size:0.85em;color:#7d7d7d;">
          A few short sections · Auto-saves as you go · About 15&ndash;20 minutes
        </p>
        {lucy_intro_html}
        {companions_html}
      </div>
    """


def render_step_1(progress: dict, mode: str) -> str:
    """Your Family — render rows merged from BOTH sources at every render:
       (a) _settings_members() (existing family from app_settings.json)
       (b) any extra named members already in progress.step_1.members
           whose name is NOT already in (a).
    The renderer never writes — typing saves naturally via debounced
    saveField, and Save & Continue triggers a single atomic
    seed_members POST that persists this exact merged list."""
    existing = _settings_members()
    progress_members = _v(progress, 1, "members", []) or []
    seen_names = {(m.get("name") or "").strip().lower() for m in existing if (m.get("name") or "").strip()}
    extras = []
    for m in progress_members:
        nm = (m.get("name") or "").strip().lower() if isinstance(m, dict) else ""
        if nm and nm not in seen_names:
            extras.append(m)
            seen_names.add(nm)
    members = list(existing) + extras
    if not members:
        members = [{"name": "", "role": "", "birthday": "", "color": ""}]
    rows = []
    for i, m in enumerate(members):
        rows.append(f"""
        <div class="frol-member" data-mem-idx="{i}">
          <div class="frol-row">
            <div>
              <label class="frol-fld">Name</label>
              <input class="frol-input" data-step="1" data-list="members" data-idx="{i}"
                     data-key="name" value="{escape(m.get('name','') or '', quote=True)}"
                     placeholder="Mom, JP, Joseph, …">
            </div>
            <div>
              <label class="frol-fld">Role</label>
              <input class="frol-input" data-step="1" data-list="members" data-idx="{i}"
                     data-key="role" value="{escape(m.get('role','') or '', quote=True)}"
                     placeholder="Mom, Dad, Child, Toddler, …">
            </div>
          </div>
          <div class="frol-row">
            <div>
              <label class="frol-fld">Birthday <span style="font-weight:400;color:#888;">(optional)</span></label>
              <input class="frol-input" type="date" data-step="1" data-list="members" data-idx="{i}"
                     data-key="birthday" value="{escape(m.get('birthday','') or '', quote=True)}">
            </div>
            <div>
              <label class="frol-fld">Color <span style="font-weight:400;color:#888;">(optional)</span></label>
              <input class="frol-input" type="color" data-step="1" data-list="members" data-idx="{i}"
                     data-key="color" value="{escape(m.get('color','#4a6fa5') or '#4a6fa5', quote=True)}">
            </div>
            <div style="flex:0 0 auto;align-self:flex-end;">
              <button type="button" class="frol-rm" onclick="frolRemoveMember({i})">Remove</button>
            </div>
          </div>
        </div>
        """)
    skip_note = ""
    if existing and not _v(progress, 1, "members"):
        skip_note = (f'<div class="frol-pop-note">We found {len(existing)} family '
                     f'member(s) in your settings. They\'re pre-filled below — adjust if needed.</div>')
    body = f"""
      {skip_note}
      <div id="frol-members">{''.join(rows)}</div>
      <button type="button" class="frol-add" onclick="frolAddMember()">+ Add another person</button>
    """
    return _step_chrome(1, "Your Family",
        "Who lives in this house? Names and roles are required; birthdays and colors help us personalize the schedule.",
        body, mode, progress, lucy_visible=True)


def render_step_2(progress: dict, mode: str) -> str:
    body = f"""
      <label class="frol-fld">Wake time on school days</label>
      <div class="frol-row">
        <div><label class="frol-help">Adults</label>
          <input class="frol-input" type="time" data-step="2" data-key="wake_school_adults"
                 value="{escape(_v(progress,2,'wake_school_adults','06:00'), quote=True)}"></div>
        <div><label class="frol-help">Teens</label>
          <input class="frol-input" type="time" data-step="2" data-key="wake_school_teens"
                 value="{escape(_v(progress,2,'wake_school_teens','06:30'), quote=True)}"></div>
        <div><label class="frol-help">Children</label>
          <input class="frol-input" type="time" data-step="2" data-key="wake_school_children"
                 value="{escape(_v(progress,2,'wake_school_children','07:00'), quote=True)}"></div>
      </div>
      <label class="frol-fld">Wake time on weekends</label>
      <div class="frol-row">
        <div><label class="frol-help">Adults</label>
          <input class="frol-input" type="time" data-step="2" data-key="wake_weekend_adults"
                 value="{escape(_v(progress,2,'wake_weekend_adults','07:00'), quote=True)}"></div>
        <div><label class="frol-help">Teens</label>
          <input class="frol-input" type="time" data-step="2" data-key="wake_weekend_teens"
                 value="{escape(_v(progress,2,'wake_weekend_teens','08:00'), quote=True)}"></div>
        <div><label class="frol-help">Children</label>
          <input class="frol-input" type="time" data-step="2" data-key="wake_weekend_children"
                 value="{escape(_v(progress,2,'wake_weekend_children','08:00'), quote=True)}"></div>
      </div>
      <label class="frol-fld">Bedtime</label>
      <div class="frol-row">
        <div><label class="frol-help">Adults</label>
          <input class="frol-input" type="time" data-step="2" data-key="bed_adults"
                 value="{escape(_v(progress,2,'bed_adults','22:30'), quote=True)}"></div>
        <div><label class="frol-help">Teens</label>
          <input class="frol-input" type="time" data-step="2" data-key="bed_teens"
                 value="{escape(_v(progress,2,'bed_teens','21:30'), quote=True)}"></div>
        <div><label class="frol-help">Children</label>
          <input class="frol-input" type="time" data-step="2" data-key="bed_children"
                 value="{escape(_v(progress,2,'bed_children','20:30'), quote=True)}"></div>
      </div>
      <label class="frol-fld">Common fixed commitments <span style="font-weight:400;color:#888;">(check any that apply)</span></label>
      {''.join(_checkbox_group(progress, 2, "common_anchors", ["Daily Mass", "Piano lessons", "Sports practice", "Co-op", "Therapy", "Work from home", "Doctor appointments", "Sea Cadets", "Music lessons"]))}
      <label class="frol-fld">Fixed weekly commitments <span style="font-weight:400;color:#888;">(details &amp; times)</span></label>
      <p class="frol-help">Recurring classes, jobs, appointments — one per line.
        Format: <code>Day HH:MM Title</code> (e.g., "Wed 09:30 Piano lessons").</p>
      <textarea class="frol-textarea" data-step="2" data-key="fixed_commitments"
                placeholder="Mon 16:00 Soccer practice&#10;Wed 09:30 Piano lessons">{escape(_v(progress,2,'fixed_commitments',''))}</textarea>
    """
    return _step_chrome(2, "Anchors",
        "The fixed points in your week — when you wake, when you sleep, what's already on the calendar.",
        body, mode, progress, lucy_visible=True)


def render_step_3(progress: dict, mode: str) -> str:
    angelus = _v(progress, 3, "angelus_times", []) or []
    def chk(t, label):
        c = "checked" if t in angelus else ""
        return (f'<label class="frol-check"><input type="checkbox" data-step="3" '
                f'data-key="angelus_times" data-multi="1" value="{t}" {c}> {label}</label>')
    body = f"""
      <div class="frol-pop-note">
        The prayer times you set here will automatically populate the
        <strong>time-block homepage prayer schedule</strong> — Lauren's
        morning, midday, afternoon, and evening views will pull from these answers.
      </div>
      <label class="frol-fld">Morning prayer time</label>
      <input class="frol-input" type="time" data-step="3" data-key="morning_time"
             value="{escape(_v(progress,3,'morning_time','06:30'), quote=True)}">
      <label class="frol-fld">Angelus — which times to observe</label>
      {chk("06:00","6 AM")}{chk("12:00","Noon")}{chk("18:00","6 PM")}
      <label class="frol-fld">Divine Mercy Chaplet at 3 PM?</label>
      <select class="frol-select" data-step="3" data-key="divine_mercy_3pm">
        {_yesno_opts(_v(progress,3,'divine_mercy_3pm','no'))}
      </select>
      <label class="frol-fld">Evening Rosary time</label>
      <input class="frol-input" type="time" data-step="3" data-key="evening_rosary_time"
             value="{escape(_v(progress,3,'evening_rosary_time','19:30'), quote=True)}">
      <label class="frol-fld">Morning prayers <span style="font-weight:400;color:#888;">(check any you pray)</span></label>
      {''.join(_checkbox_group(progress, 3, "morning_prayers_multi", ["Morning Offering", "Lauds", "Rosary", "Lectio Divina", "Divine Office"]))}
      <label class="frol-fld">Evening prayers <span style="font-weight:400;color:#888;">(check any you pray)</span></label>
      {''.join(_checkbox_group(progress, 3, "evening_prayers_multi", ["Rosary", "Vespers", "Chaplet of Divine Mercy", "Chaplet of St Michael"]))}
      <label class="frol-fld">Night prayers <span style="font-weight:400;color:#888;">(check any you pray)</span></label>
      {''.join(_checkbox_group(progress, 3, "night_prayers_multi", ["Compline", "Examination of conscience", "Night prayers"]))}
      <label class="frol-fld">Other family devotions <span style="font-weight:400;color:#888;">(optional)</span></label>
      <textarea class="frol-textarea" data-step="3" data-key="other_devotions"
                placeholder="Sacred Heart enthronement, Lectio Divina on Sundays, …">{escape(_v(progress,3,'other_devotions',''))}</textarea>
      <div class="frol-companion">
        <div class="name">&#10016; Sister Mary</div>
        Sister Mary is your contemplative Marian companion. She remembers your
        family's prayer intentions and answers from a place of stillness.
        <a href="/sister-mary" target="_blank" style="color:#33507e;">Meet Sister Mary &rarr;</a>
      </div>
    """
    return _step_chrome(3, "Prayer",
        "The rhythm of prayer that anchors your family's day.",
        body, mode, progress, lucy_visible=True)


def _checkbox_group(progress: dict, step: int, key: str, options: list) -> list:
    """Render a multi-checkbox group bound to a single list field via the
    existing data-multi="1" JS handler. Returns a list of HTML fragments."""
    sel = _v(progress, step, key, []) or []
    if not isinstance(sel, list):
        sel = []
    out = []
    for o in options:
        c = "checked" if o in sel else ""
        out.append(f'<label class="frol-check"><input type="checkbox" data-step="{step}" '
                   f'data-key="{key}" data-multi="1" value="{escape(o, quote=True)}" {c}> '
                   f'{escape(o)}</label>')
    return out


def _yesno_opts(cur: str) -> str:
    cur = (cur or "no").lower()
    out = []
    for v, l in [("yes", "Yes"), ("no", "No")]:
        sel = "selected" if v == cur else ""
        out.append(f'<option value="{v}" {sel}>{l}</option>')
    return "".join(out)


def render_step_4(progress: dict, mode: str) -> str:
    body = f"""
      <div class="frol-row">
        <div><label class="frol-fld">Breakfast time</label>
          <input class="frol-input" type="time" data-step="4" data-key="breakfast_time"
                 value="{escape(_v(progress,4,'breakfast_time','07:30'), quote=True)}"></div>
        <div><label class="frol-fld">Lunch time</label>
          <input class="frol-input" type="time" data-step="4" data-key="lunch_time"
                 value="{escape(_v(progress,4,'lunch_time','12:00'), quote=True)}"></div>
        <div><label class="frol-fld">Dinner time</label>
          <input class="frol-input" type="time" data-step="4" data-key="dinner_time"
                 value="{escape(_v(progress,4,'dinner_time','17:30'), quote=True)}"></div>
      </div>
      <label class="frol-fld">Lunch together or separate?</label>
      <select class="frol-select" data-step="4" data-key="lunch_together">
        <option value="together" {"selected" if _v(progress,4,'lunch_together','together')=='together' else ""}>Together</option>
        <option value="separate" {"selected" if _v(progress,4,'lunch_together','')=='separate' else ""}>Separate</option>
      </select>
      <label class="frol-fld">Morning prep slot for dinner?</label>
      <select class="frol-select" data-step="4" data-key="morning_dinner_prep">
        {_yesno_opts(_v(progress,4,'morning_dinner_prep','no'))}
      </select>
      <label class="frol-fld">Who prepares meals <span style="font-weight:400;color:#888;">(check any that apply)</span></label>
      {''.join(_checkbox_group(progress, 4, "meal_prep_who", ["Mom", "Dad", "JP", "Joseph", "Older children", "Together as family"]))}
      <label class="frol-fld">Batch cooking day(s) <span style="font-weight:400;color:#888;">(check any)</span></label>
      {''.join(_checkbox_group(progress, 4, "batch_cook_days", list(WEEKDAYS)))}
      <div class="frol-companion">
        <div class="name">&#127860; Lorenzo</div>
        Lorenzo is your personal chef AI — meal plans, grocery lists, recipes.
        <a href="/lorenzo" target="_blank" style="color:#33507e;">Meet Lorenzo &rarr;</a>
      </div>
    """
    return _step_chrome(4, "Meals",
        "When you eat together, who cooks, and how the kitchen flows.",
        body, mode, progress, lucy_visible=True)


def render_step_5(progress: dict, mode: str) -> str:
    members = _v(progress, 1, "members", []) or []
    if not members:
        members = _settings_members()
    _kid_roles = ("child", "teen", "kid", "student", "toddler", "baby",
                  "son", "daughter", "preschool", "preschooler")
    kid_names = []
    for m in members:
        nm = (m.get("name") or "").strip()
        role = (m.get("role") or "").strip().lower()
        if not nm:
            continue
        if role in _kid_roles or role not in ("mom", "dad", "parent", "adult", "mother", "father"):
            kid_names.append(nm)
    homeschool_kids = _v(progress, 5, "homeschool_kids", []) or []
    chk_kids = []
    for n in kid_names:
        if not n: continue
        c = "checked" if n in homeschool_kids else ""
        chk_kids.append(f'<label class="frol-check"><input type="checkbox" data-step="5" '
                        f'data-key="homeschool_kids" data-multi="1" value="{escape(n,quote=True)}" {c}> {escape(n)}</label>')
    body = f"""
      <label class="frol-fld">Are you homeschooling?</label>
      <select class="frol-select" data-step="5" data-key="homeschool_yes">
        {_yesno_opts(_v(progress,5,'homeschool_yes','yes'))}
      </select>
      <label class="frol-fld">Homeschool hours</label>
      <div class="frol-row">
        <div><label class="frol-help">Start</label>
          <input class="frol-input" type="time" data-step="5" data-key="school_start"
                 value="{escape(_v(progress,5,'school_start','08:30'), quote=True)}"></div>
        <div><label class="frol-help">End</label>
          <input class="frol-input" type="time" data-step="5" data-key="school_end"
                 value="{escape(_v(progress,5,'school_end','12:30'), quote=True)}"></div>
      </div>
      <label class="frol-fld">Which children?</label>
      {''.join(chk_kids) or '<p class="frol-help">Add children in step 1 first.</p>'}
      <label class="frol-fld">Subject list per child <span style="font-weight:400;color:#888;">(brief — full curriculum comes later)</span></label>
      <textarea class="frol-textarea" data-step="5" data-key="subjects_per_kid"
                placeholder="JP: Math, Latin, History, Religion&#10;Joseph: Math, Reading, Science">{escape(_v(progress,5,'subjects_per_kid',''))}</textarea>
      <label class="frol-fld">Chore time blocks <span style="font-weight:400;color:#888;">(check any that apply)</span></label>
      {''.join(_checkbox_group(progress, 5, "chore_time_blocks", ["Morning", "Midday", "After school", "Evening"]))}
      <label class="frol-fld">Subjects covered <span style="font-weight:400;color:#888;">(check any)</span></label>
      {''.join(_checkbox_group(progress, 5, "subjects_multi", ["Math", "Religion", "Reading", "Writing", "Science", "History", "Latin", "Art", "Music", "PE"]))}
      <label class="frol-fld">Parent work-from-home hours to protect</label>
      <textarea class="frol-textarea" data-step="5" data-key="parent_wfh"
                placeholder="John: Mon–Fri 09:00–11:30 (deep work, no interruptions)">{escape(_v(progress,5,'parent_wfh',''))}</textarea>
      <div class="frol-companion">
        <div class="name">&#128218; Father Gregory</div>
        Father Gregory is your homeschool academic headmaster — assignments,
        gradebook, weekly planning. <a href="/gregory" target="_blank" style="color:#33507e;">Meet Father Gregory &rarr;</a>
      </div>
    """
    return _step_chrome(5, "Work Blocks",
        "Homeschool, chores, and parent work — the productive hours of the day.",
        body, mode, progress, lucy_visible=True)


def render_step_6(progress: dict, mode: str) -> str:
    types_sel = _v(progress, 6, "types", []) or []
    type_chk = []
    for t in ["Strength", "Cardio", "Walks", "PE", "Sports"]:
        c = "checked" if t in types_sel else ""
        type_chk.append(f'<label class="frol-check"><input type="checkbox" data-step="6" '
                        f'data-key="types" data-multi="1" value="{t}" {c}> {t}</label>')
    body = f"""
      <label class="frol-fld">Family exercise routine?</label>
      <select class="frol-select" data-step="6" data-key="family_routine">
        {_yesno_opts(_v(progress,6,'family_routine','yes'))}
      </select>
      <label class="frol-fld">When</label>
      <select class="frol-select" data-step="6" data-key="when">
        {''.join(f'<option {("selected" if _v(progress,6,"when","morning")==v else "")} value="{v}">{l}</option>' for v,l in [("morning","Morning"),("afternoon","Afternoon"),("evening","Evening")])}
      </select>
      <label class="frol-fld">Who exercises <span style="font-weight:400;color:#888;">(check any)</span></label>
      {''.join(_checkbox_group(progress, 6, "who_exercises_multi", ["Mom", "Dad", "JP", "Joseph", "Michael", "Family together"]))}
      <label class="frol-fld">Types</label>
      {''.join(type_chk)}
      <label class="frol-fld">Recurring classes or scheduled workouts</label>
      <textarea class="frol-textarea" data-step="6" data-key="recurring_classes"
                placeholder="Tue 10:00 CAP PT&#10;Sat 09:00 Family run">{escape(_v(progress,6,'recurring_classes',''))}</textarea>
      <label class="frol-fld">Family exercise time or individual?</label>
      <select class="frol-select" data-step="6" data-key="family_or_individual">
        <option value="family"     {"selected" if _v(progress,6,'family_or_individual','family')=='family' else ""}>Family time</option>
        <option value="individual" {"selected" if _v(progress,6,'family_or_individual','')=='individual' else ""}>Individual</option>
        <option value="mixed"      {"selected" if _v(progress,6,'family_or_individual','')=='mixed' else ""}>Mix of both</option>
      </select>
      <div class="frol-companion">
        <div class="name">&#128170; Coach</div>
        Coach is your family fitness AI — programs, logs, encouragement.
        <a href="/programs" target="_blank" style="color:#33507e;">Meet Coach &rarr;</a>
      </div>
    """
    return _step_chrome(6, "Exercise & Health",
        "Bodies need rhythm too. How do you move together?",
        body, mode, progress, lucy_visible=True)


def render_step_7(progress: dict, mode: str) -> str:
    trad_sel = _v(progress, 7, "traditions", []) or []
    trad_chk = []
    for t in ["Read-aloud", "Sunday brunch", "Holy hour", "Family Rosary", "Game night", "Movie night", "Nature walk", "Sunday meatballs"]:
        c = "checked" if t in trad_sel else ""
        trad_chk.append(f'<label class="frol-check"><input type="checkbox" data-step="7" '
                        f'data-key="traditions" data-multi="1" value="{t}" {c}> {t}</label>')
    body = f"""
      <label class="frol-fld">Afternoon rest / quiet time</label>
      <input class="frol-input" data-step="7" data-key="afternoon_rest"
             value="{escape(_v(progress,7,'afternoon_rest',''), quote=True)}"
             placeholder="Toddlers nap 1–3 PM; everyone reads quietly 2–3 PM">
      <label class="frol-fld">Family free time — when?</label>
      <input class="frol-input" data-step="7" data-key="family_free_time"
             value="{escape(_v(progress,7,'family_free_time',''), quote=True)}"
             placeholder="Evenings 6–7:30 PM, Saturday afternoons">
      <label class="frol-fld">Weekly traditions</label>
      {''.join(trad_chk)}
      <label class="frol-fld">Other tradition?</label>
      <input class="frol-input" data-step="7" data-key="other_tradition"
             value="{escape(_v(progress,7,'other_tradition',''), quote=True)}"
             placeholder="Sunday meatballs, Friday holy hour, …">
      <label class="frol-fld">Date night — day &amp; time</label>
      <input class="frol-input" data-step="7" data-key="date_night"
             value="{escape(_v(progress,7,'date_night',''), quote=True)}"
             placeholder="Friday 8 PM after kids' bedtime">
      <label class="frol-fld">Daily couple time</label>
      <select class="frol-select" data-step="7" data-key="couple_time">
        <option value="morning_coffee" {"selected" if _v(progress,7,'couple_time','morning_coffee')=='morning_coffee' else ""}>Morning coffee</option>
        <option value="evening"        {"selected" if _v(progress,7,'couple_time','')=='evening' else ""}>Evening together</option>
        <option value="both"           {"selected" if _v(progress,7,'couple_time','')=='both' else ""}>Both</option>
        <option value=""               {"selected" if not _v(progress,7,'couple_time','morning_coffee') else ""}>None scheduled</option>
      </select>
      <label class="frol-fld">Weekly marriage check-in — day &amp; time</label>
      <input class="frol-input" data-step="7" data-key="weekly_checkin"
             value="{escape(_v(progress,7,'weekly_checkin',''), quote=True)}"
             placeholder="Sunday evening 8 PM">
      <label class="frol-fld">Weekend rhythm — different from weekdays?</label>
      <textarea class="frol-textarea" data-step="7" data-key="weekend_diff"
                placeholder="Saturdays = chores morning, free afternoon. Sundays = Mass, family meal, rest.">{escape(_v(progress,7,'weekend_diff',''))}</textarea>
      <div class="frol-companion">
        <div class="name">&#127800; Dr. Monica</div>
        Dr. Monica is your child development &amp; pediatric health AI — sleep,
        behavior, milestones. <a href="/dr-monica" target="_blank" style="color:#33507e;">Meet Dr. Monica &rarr;</a>
      </div>
    """
    return _step_chrome(7, "Rest, Family & Marriage",
        "The rhythm of rest, togetherness, and the marriage that holds it all.",
        body, mode, progress, lucy_visible=True)


def render_step_8(progress: dict, mode: str) -> str:
    members = _v(progress, 1, "members", []) or []
    tracked = _v(progress, 8, "tracked_members", []) or []
    chk = []
    for m in members:
        n = m.get("name", "")
        if not n: continue
        c = "checked" if n in tracked else ""
        chk.append(f'<label class="frol-check"><input type="checkbox" data-step="8" '
                   f'data-key="tracked_members" data-multi="1" value="{escape(n,quote=True)}" {c}> {escape(n)}</label>')
    notif_sel = _v(progress, 8, "notif_channels", []) or []
    notif_chk = []
    for n_ in ["email", "push", "sms", "in_app"]:
        c = "checked" if n_ in notif_sel else ""
        notif_chk.append(f'<label class="frol-check"><input type="checkbox" data-step="8" '
                         f'data-key="notif_channels" data-multi="1" value="{n_}" {c}> {n_.replace("_"," ").title()}</label>')
    contacts = _v(progress, 8, "emergency_contacts", []) or []
    while len(contacts) < 5:
        contacts.append({})
    # Show only filled rows, plus row 0 if none filled. Hidden rows revealed by JS.
    visible_count = max(1, sum(1 for c in contacts[:5] if (c.get("name") or c.get("phone") or c.get("email"))))
    contact_rows = []
    for i, c in enumerate(contacts[:5]):
        hidden_style = "" if i < visible_count else "display:none;"
        contact_rows.append(f"""
        <div class="frol-row frol-contact-row" data-contact-idx="{i}" style="{hidden_style}">
          <div><input class="frol-input" data-step="8" data-list="emergency_contacts" data-idx="{i}" data-key="name"
                      value="{escape(c.get('name','') or '', quote=True)}" placeholder="Name"></div>
          <div><input class="frol-input" type="tel" data-step="8" data-list="emergency_contacts" data-idx="{i}" data-key="phone"
                      value="{escape(c.get('phone','') or '', quote=True)}" placeholder="Phone"></div>
          <div><input class="frol-input" type="email" data-step="8" data-list="emergency_contacts" data-idx="{i}" data-key="email"
                      value="{escape(c.get('email','') or '', quote=True)}" placeholder="Email"></div>
        </div>""")
    add_btn_hidden = "display:none;" if visible_count >= 5 else ""
    contact_rows.append(f'<button type="button" id="frol-add-contact" class="frol-add" '
                        f'onclick="frolRevealContact()" style="{add_btn_hidden}">+ Add another contact</button>')
    body = f"""
      <label class="frol-fld">Set up health tracking for which family members?</label>
      {''.join(chk) or '<p class="frol-help">Add family members in step 1 first.</p>'}
      <label class="frol-fld">Current medications <span style="font-weight:400;color:#888;">(basic list — full prescription scanning comes in Phase 2)</span></label>
      <textarea class="frol-textarea" data-step="8" data-key="medications"
                placeholder="JP: daily multivitamin&#10;Mom: prenatal vitamin">{escape(_v(progress,8,'medications',''))}</textarea>
      <label class="frol-fld">Common recurring appointments <span style="font-weight:400;color:#888;">(check any that apply)</span></label>
      {''.join(_checkbox_group(progress, 8, "recurring_appt_types", ["Annual physicals", "Dental cleanings", "Eye exams", "Orthodontist", "Therapy", "Postpartum checkup"]))}
      <label class="frol-fld">Recurring health appointments <span style="font-weight:400;color:#888;">(details &amp; cadence)</span></label>
      <textarea class="frol-textarea" data-step="8" data-key="recurring_appts"
                placeholder="James PT — Wed 10:30 AM weekly&#10;Mom OBGYN — every 4 weeks">{escape(_v(progress,8,'recurring_appts',''))}</textarea>
      <label class="frol-fld">Notification channels <span style="font-weight:400;color:#888;">(all off by default)</span></label>
      {''.join(notif_chk)}
      <div class="frol-row">
        <div><label class="frol-help">Phone</label>
          <input class="frol-input" type="tel" data-step="8" data-key="notif_phone"
                 value="{escape(_v(progress,8,'notif_phone',''), quote=True)}"></div>
        <div><label class="frol-help">Email</label>
          <input class="frol-input" type="email" data-step="8" data-key="notif_email"
                 value="{escape(_v(progress,8,'notif_email',''), quote=True)}"></div>
      </div>
      <label class="frol-fld">Emergency contacts <span style="font-weight:400;color:#888;">(up to 5)</span></label>
      {''.join(contact_rows)}
    """
    return _step_chrome(8, "Family Health & Wellbeing",
        "Health tracking, medications, appointments, and how you'd like to be notified.",
        body, mode, progress, lucy_visible=True)


def render_step_9(progress: dict, mode: str) -> str:
    members = _v(progress, 1, "members", []) or []
    if not [m for m in members if (m.get("name") or "").strip()]:
        members = _settings_members()
    if not members:
        body = ('<p class="frol-help">Add family members in step 1 to see '
                "each person's day here.</p>")
        return _step_chrome(9, "Each Person's Role",
            "A day's rhythm, one person at a time.", body, mode, progress, lucy_visible=True)
    summaries = _build_person_summaries(progress)
    missing_html = _missing_steps_prompt(progress, mode)
    blocks = []
    for m in members:
        nm = m.get("name", "")
        if not nm: continue
        s = summaries.get(nm, [])
        items = "".join(f'<div class="frol-grid"><div>{escape(str(t))}</div><div>{escape(str(act))}</div></div>'
                        for t, act in s)
        blocks.append(f"""
          <div class="frol-member">
            <h3 style="margin:0 0 6px;color:var(--frol-blue-dark);">{escape(nm)}</h3>
            <p class="frol-help" style="margin:0 0 8px;">Built from your wizard answers — adjust below.</p>
            {items or '<p class="frol-help">No anchor times set yet — go back to the earlier steps to fill them in.</p>'}
            <label class="frol-fld">Adjustments for {escape(nm)}</label>
            <textarea class="frol-textarea" data-step="9" data-list="adjustments" data-idx="{escape(nm,quote=True)}" data-key="notes"
                      placeholder="Anything different for {escape(nm)}?">{escape((((_v(progress,9,'adjustments',{}) or {}).get(nm) or {}).get('notes') or ''))}</textarea>
          </div>
        """)
    body = f"""
      <p class="frol-help">Each person's day below is built directly from the
      answers you've given so far in this wizard. When you continue from this
      step, those answers will be written to
      <code>data/day_templates/&lt;Weekday&gt;.json</code>. Existing templates
      will be backed up first.</p>
      {missing_html}
      {''.join(blocks)}
    """
    return _step_chrome(9, "Each Person's Role",
        "A day's rhythm, one person at a time.", body, mode, progress, lucy_visible=True)


def _row_sort_minutes(t: str) -> int:
    """Convert a row's time field to minutes-since-midnight for sorting.
    Accepts HH:MM 24-hour strings and a few keyword tokens used elsewhere
    in the wizard (evening, night). Unknown values sort to the end."""
    s = (t or "").strip().lower()
    if s == "evening":
        return 19 * 60
    if s == "night":
        return 21 * 60
    if len(s) >= 4 and ":" in s:
        try:
            hh, mm = s.split(":", 1)
            return int(hh) * 60 + int(mm[:2])
        except (ValueError, TypeError):
            return 24 * 60 + 1
    return 24 * 60 + 1


def _fmt_12h(t: str) -> str:
    """Format an HH:MM 24-hour string as 12-hour with AM/PM. Pass keyword
    tokens (evening, night) and unparseable values through unchanged."""
    s = (t or "").strip()
    if not s or ":" not in s:
        return s
    try:
        hh_str, rest = s.split(":", 1)
        hh = int(hh_str)
        mm = int(rest[:2])
    except (ValueError, TypeError):
        return s
    suffix = "AM" if hh < 12 else "PM"
    h12 = hh % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{mm:02d} {suffix}"


def _build_person_summaries(progress: dict) -> dict:
    """Compose a per-person time-block summary purely from the wizard's
    collected answers in frol_wizard_progress.json — never from the
    existing FROL day_templates. Pulls anchors from step_2, prayer from
    step_3, meals from step_4, work blocks from step_5, exercise from
    step_6, and rest/marriage from step_7."""
    out = {}
    members = _v(progress, 1, "members", []) or []
    if not members:
        members = _settings_members()
    d  = progress.get("data", {}) or {}
    s2 = d.get("step_2", {}) or {}
    s3 = d.get("step_3", {}) or {}
    s4 = d.get("step_4", {}) or {}
    s5 = d.get("step_5", {}) or {}
    s6 = d.get("step_6", {}) or {}
    s7 = d.get("step_7", {}) or {}
    _when_to_time = {"morning": "06:30", "afternoon": "15:00", "evening": "18:30"}
    for m in members:
        nm = m.get("name", "")
        if not nm:
            continue
        bucket = (m.get("role", "") or "").lower()
        if bucket in ("mom", "dad", "parent", "adult", "mother", "father"):
            wake = s2.get("wake_school_adults", "06:00")
            bed  = s2.get("bed_adults", "22:30")
            person_class = "adult"
        elif bucket in ("teen", "student") or _age_bucket(m) == "teen":
            wake = s2.get("wake_school_teens", "06:30")
            bed  = s2.get("bed_teens", "21:30")
            person_class = "teen"
        else:
            wake = s2.get("wake_school_children", "07:00")
            bed  = s2.get("bed_children", "20:30")
            person_class = "child"
        rows = []
        rows.append((wake, "Up & moving"))
        # ── Step 3 prayer (multi-checkbox groups + times) ────────────────
        _morning_multi = s3.get("morning_prayers_multi") or []
        if s3.get("morning_time") and _morning_multi:
            rows.append((s3["morning_time"], " / ".join(_morning_multi)))
        elif s3.get("morning_time"):
            rows.append((s3["morning_time"], "Morning prayer"))
        for t in (s3.get("angelus_times") or []):
            rows.append((t, "Angelus"))
        if s3.get("divine_mercy_3pm") == "yes":
            rows.append(("15:00", "Divine Mercy Chaplet"))
        # ── Step 4 meals ─────────────────────────────────────────────────
        # Lunch and Dinner default to 12:30 / 18:00 when the user hasn't
        # filled in the time field, so they always appear on the schedule.
        if s4.get("breakfast_time"):
            rows.append((s4["breakfast_time"], "Breakfast"))
        rows.append((s4.get("lunch_time")  or "12:30", "Lunch"))
        rows.append((s4.get("dinner_time") or "18:00", "Dinner"))
        # ── Step 5 work blocks ───────────────────────────────────────────
        # The old "homeschool_yes" yes/no field was removed in dedup; treat
        # homeschooling as ON when homeschool_kids has any entries.
        _hs_kids = s5.get("homeschool_kids") or []
        if _hs_kids and nm in _hs_kids:
            rows.append((s5.get("school_start", "08:30"), "Homeschool — start"))
            rows.append((s5.get("school_end",   "12:30"), "Homeschool — end"))
        # Chore time blocks — map each checked block to a representative
        # time and add a Chores row for everyone.
        _chore_block_times = {
            "Morning":      "08:00",
            "Midday":       "12:00",
            "After school": "15:00",
            "Evening":      "18:00",
        }
        for _cb in (s5.get("chore_time_blocks") or []):
            if _cb in _chore_block_times:
                rows.append((_chore_block_times[_cb], "Chores"))
        # ── Step 6 exercise ──────────────────────────────────────────────
        # The old single-select "when" field was removed in dedup; prefer
        # the new "exercise_when" if present, otherwise default to 07:00
        # so exercise still appears for everyone who's checked.
        _ex_who   = s6.get("who_exercises_multi") or []
        _ex_when  = s6.get("exercise_when") or s6.get("when") or ""
        _ex_types = s6.get("types") or []
        _is_family = "Family together" in _ex_who
        if _ex_who and (nm in _ex_who or _is_family):
            _ex_time = _when_to_time.get(_ex_when, "07:00")
            _ex_label = "Exercise"
            if _ex_types:
                _ex_label = f"Exercise — {_ex_types[0]}"
            rows.append((_ex_time, _ex_label))
        # ── Step 3 evening prayers ───────────────────────────────────────
        if s3.get("evening_rosary_time"):
            rows.append((s3["evening_rosary_time"], "Rosary"))
        for _ep in (s3.get("evening_prayers_multi") or []):
            if _ep == "Rosary":
                continue
            rows.append((s3.get("evening_rosary_time", ""), _ep))
        # ── Step 7 rest / marriage ───────────────────────────────────────
        if s7.get("afternoon_rest"):
            rows.append(("14:00", f"Afternoon rest — {s7['afternoon_rest']}"))
        if s7.get("family_free_time"):
            rows.append(("evening", f"Family time — {s7['family_free_time']}"))
        if person_class == "adult":
            if s7.get("date_night"):
                rows.append(("evening", f"Date night — {s7['date_night']}"))
            if s7.get("weekly_checkin"):
                rows.append(("weekly", f"Marriage check-in — {s7['weekly_checkin']}"))
        # ── Step 3 night prayers ─────────────────────────────────────────
        for _np in (s3.get("night_prayers_multi") or []):
            rows.append(("night", _np))
        rows.append((bed, "Bedtime"))
        # ── Step 9 per-person adjustments (free-text notes) ──────────────
        # Adjustments are saved as step_9.adjustments[name].notes by the
        # extended save_field handler. Older snapshots may store this as
        # a list, so guard for both shapes.
        s9 = d.get("step_9", {}) or {}
        _adj = s9.get("adjustments")
        if isinstance(_adj, dict):
            _entry = _adj.get(nm) or {}
            _notes = (_entry.get("notes") or "").strip() if isinstance(_entry, dict) else ""
            if _notes:
                for _line in _notes.splitlines():
                    _line = _line.strip()
                    if _line:
                        rows.append(("", f"Adjustment — {_line}"))
        # Sort chronologically by parsed time, then format times in 12-hour
        # AM/PM. Keyword tokens (evening, night) pass through unchanged.
        rows.sort(key=lambda r: _row_sort_minutes(r[0]))
        out[nm] = [(_fmt_12h(t), act) for (t, act) in rows]
    return out


def _missing_step_buckets(progress: dict) -> list:
    """Return [(step_num, friendly_name), ...] for any wizard step whose
    bucket is empty / unanswered. Used by steps 9 and 10 to show a gentle
    'go back and complete' prompt instead of an empty schedule."""
    d = progress.get("data", {}) or {}
    checks = [
        (2, "Anchors",          ("wake_school_adults", "bed_adults")),
        (3, "Prayer",           ("morning_time", "evening_rosary_time")),
        (4, "Meals",            ("breakfast_time", "lunch_time", "dinner_time")),
        (5, "Work Blocks",      ("homeschool_kids", "chore_time_blocks")),
        (6, "Exercise",         ("who_exercises_multi",)),
        (7, "Rest & Marriage",  ("family_free_time", "afternoon_rest", "couple_time")),
    ]
    missing = []
    for step_num, label, keys in checks:
        bucket = d.get(f"step_{step_num}", {}) or {}
        if not any(bucket.get(k) for k in keys):
            missing.append((step_num, label))
    return missing


def _missing_steps_prompt(progress: dict, mode: str) -> str:
    """Render a soft-yellow prompt card listing any wizard steps with no
    data yet, with a back link to each so the user can fill them in."""
    missing = _missing_step_buckets(progress)
    if not missing:
        return ""
    items = []
    for step_num, label in missing:
        href = f"/frol-wizard?step={step_num}&mode={escape(mode, quote=True)}"
        items.append(f'<li>Step {step_num} — <strong>{escape(label)}</strong> '
                     f'<a href="{href}" style="color:#33507e;">go back &amp; complete &rarr;</a></li>')
    return ('<div class="frol-pop-note"><strong>A few steps still need your '
            'answers</strong> before we can build your full schedule:'
            f'<ul style="margin:8px 0 0 18px;">{"".join(items)}</ul></div>')


def render_step_10(progress: dict, mode: str) -> str:
    notes = derive_heuristic_notes(progress)
    members = _v(progress, 1, "members", []) or []
    if not members:
        members = _settings_members()
    person_names = [m.get("name", "") for m in members if m.get("name")]
    summaries = _build_person_summaries(progress)
    missing_html = _missing_steps_prompt(progress, mode)
    grid_html = []
    for nm in person_names:
        rows = summaries.get(nm, [])
        if rows:
            items = "".join(f'<div>{escape(str(t))} — {escape(str(act))}</div>' for t, act in rows[:8])
        else:
            items = ('<div style="color:#888;font-style:italic;">No schedule yet — '
                     'complete the earlier steps to build one.</div>')
        grid_html.append(f"""
          <div class="frol-member">
            <strong style="color:var(--frol-blue-dark);">{escape(nm)}</strong>
            <div style="font-size:0.88em;color:#444;margin-top:4px;">{items}</div>
          </div>
        """)
    gaps = _detect_gaps(progress)
    gap_html = ""
    if gaps:
        gap_html = ('<div class="frol-pop-note"><strong>A few things to consider:</strong><ul>'
                    + "".join(f"<li>{escape(g)}</li>" for g in gaps) + "</ul></div>")
    note_html = ""
    if notes:
        note_html = ('<div class="frol-pop-note"><strong>Lucy noticed:</strong><ul>'
                     + "".join(f"<li>{escape(n)}</li>" for n in notes) + "</ul></div>")
    body = f"""
      <p class="frol-help">A snapshot of your family week, built directly from
      the answers you've given so far in this wizard. When you click
      <strong>Save</strong>, your Rule of Life is written to your day templates,
      family settings, and prayer schedule.</p>
      {missing_html}
      {gap_html}
      {note_html}
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;">
        {''.join(grid_html)}
      </div>
      <p class="frol-help" style="margin-top:18px;">Use <strong>Back</strong>
      to revisit any step before saving.</p>
    """
    # Step 10 swaps the standard Save button for the finalize button.
    completed = progress.get("completed_steps", []) or []
    dots = _progress_dots(10, completed)
    back_link = (f'<a href="/frol-wizard?step=9&mode={escape(mode, quote=True)}" '
                 f'class="frol-btn ghost">&larr; Back</a>')
    return f"""
      <div class="frol-card">
        <h2 class="frol-title">Review</h2>
        <p class="frol-sub">Your family week, all together.</p>
        {body}
        <form method="POST" action="/frol-wizard-finalize" style="margin-top:24px;">
          <input type="hidden" name="mode" value="{escape(mode, quote=True)}">
          <label class="frol-check" style="display:flex;align-items:flex-start;gap:10px;
                  background:#eaf0fa;border:1px solid #c8d6ec;border-radius:10px;
                  padding:14px 16px;margin:8px 0 18px;font-weight:600;">
            <input type="checkbox" name="want_ai_suggestions" value="1"
                   data-step="10" data-key="want_ai_suggestions"
                   {"checked" if _v(progress,10,'want_ai_suggestions','') in ('1', 'yes', 'true', True) else ""}
                   style="margin-top:3px;">
            <span>Would you like suggestions for scheduling remaining activities
            based on your fixed commitments?
            <span style="display:block;font-weight:400;color:#555;font-size:0.9em;margin-top:3px;">
              When checked, Lucy will review your week and suggest specific day &amp; time
              slots for the activities you haven't yet anchored — shown right after Save.
            </span></span>
          </label>
          <div class="frol-actions">
            {back_link}
            <button type="submit" class="frol-btn">Save my Rule of Life &check;</button>
          </div>
        </form>
      </div>
    """


def _detect_gaps(progress: dict) -> list:
    g = []
    s3 = progress.get("data", {}).get("step_3", {}) or {}
    s4 = progress.get("data", {}).get("step_4", {}) or {}
    if not s3.get("morning_time"):
        g.append("No morning prayer time set.")
    if not s4.get("breakfast_time") or not s4.get("dinner_time"):
        g.append("Breakfast or dinner time isn't set.")
    if s4.get("morning_dinner_prep") == "no" and not (s4.get("batch_cook_days") or []):
        g.append("No dinner-prep slot and no batch-cook day — evenings may be tight.")
    return g


def render_completion_screen() -> str:
    # If finalize wrote AI scheduling suggestions to progress.json, surface
    # them as a beautiful card on the completion screen.
    suggestions_html = ""
    try:
        _p = load_progress()
        _sug = (_p.get("ai_suggestions") or "").strip()
        if _sug:
            _sug_html = escape(_sug).replace("\n\n", "</p><p>").replace("\n", "<br>")
            suggestions_html = f"""
    <div class="frol-card" style="background:linear-gradient(135deg,#fbf6ec 0%,#eaf0fa 100%);
                border:1px solid #c8d6ec;border-left:5px solid var(--frol-blue);
                margin-top:22px;text-align:left;padding:26px 28px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
        <span style="font-size:1.6em;color:var(--frol-blue);">&#10024;</span>
        <h2 class="frol-title" style="margin:0;font-size:1.35em;">Lucy's scheduling suggestions</h2>
      </div>
      <p class="frol-sub" style="margin:0 0 14px;">Specific day &amp; time recommendations
      based on your fixed commitments — adjust freely.</p>
      <div style="font-family:Georgia,serif;line-height:1.65;color:#2b2b2b;font-size:1em;">
        <p>{_sug_html}</p>
      </div>
    </div>"""
    except Exception:
        suggestions_html = ""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Your Rule of Life · Saved</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{WIZARD_CSS}</style></head><body>
<div class="frol-wrap">
  <div class="frol-card" style="text-align:center;padding:50px 32px;">
    <div style="font-size:3em;color:var(--frol-blue);">&check;</div>
    <h1 class="frol-title" style="font-size:1.9em;">Your Rule of Life is saved.</h1>
    <p class="frol-sub" style="font-size:1.05em;max-width:520px;margin:14px auto 26px;">
      It will evolve &mdash; come back anytime to adjust it as your family
      grows and seasons change.
    </p>
    <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap;">
      <a href="/" class="frol-btn">Home &rarr;</a>
      <a href="/frol-wizard?reset=1" class="frol-btn ghost">Start over</a>
    </div>
  </div>
  {suggestions_html}
</div>
</body></html>"""


# ── Public page entry ───────────────────────────────────────────────────────

def render_frol_wizard_page(viewer: str = "", step=None, mode: str = "") -> str:
    progress = load_progress()
    if not mode:
        mode = progress.get("mode", "") or "structured"
    cur = step
    if cur is None or str(cur) == "":
        cur = progress.get("current_step", 0) or 0
    try:
        cur = int(cur)
    except Exception:
        cur = 0
    cur = max(0, min(V2_TOTAL_SECTIONS, cur))

    if mode in ("lucy", "structured") and not progress.get("mode"):
        progress["mode"] = mode
        save_progress(progress)

    # Phase 4: migrate V1 → V2 once, idempotent.
    if _migrate_v1_to_v2(progress):
        save_progress(progress)
        # current_step was overwritten by the migration; honor an explicit
        # step param if the caller supplied one.
        if step is not None and str(step) != "":
            try:
                cur = max(0, min(V2_TOTAL_SECTIONS, int(step)))
            except Exception:
                pass
        else:
            cur = progress.get("current_step", 0) or 0

    if cur == 0 or not progress.get("mode"):
        body = render_landing(progress)
    else:
        renderer = _section_renderer(cur)
        body = renderer(progress, mode) if renderer else _section_placeholder(cur, mode, progress)

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Rule of Life Wizard</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{WIZARD_CSS}</style></head><body>
<div class="frol-wrap">
  <div class="frol-top">
    <a href="/">&larr; Home</a>
    <span>Rule of Life · Section {cur or "Start"} of {V2_TOTAL_SECTIONS}</span>
  </div>
  {body}
</div>
<script src="/static/js/frol_wizard.js"></script>
</body></html>"""


# ── Setup card on Lauren's dashboard ────────────────────────────────────────

def render_frol_setup_card(viewer: str = "") -> str:
    if (viewer or "").lower() not in ("lauren", "john"):
        return ""
    p = load_progress()
    if p.get("finalized_at"):
        return ""
    cur = int(p.get("current_step", 0) or 0)
    has_started = bool(p.get("mode"))
    label = "Continue setup" if has_started else "Start setup"
    sub = (f"You left off at step {cur}." if has_started
           else "A 15–20-minute walk through your daily and weekly rhythm.")
    return f"""
      <div id="frol-setup-card" class="tb-card" data-frol-card="1"
           style="display:block;background:#eaf0fa;border:1px solid #c8d6ec;
                  border-left:4px solid #4a6fa5;border-radius:12px;
                  padding:14px 16px;margin:12px 0;position:relative;">
        <button onclick="frolDismissCard()" aria-label="Dismiss"
                style="position:absolute;top:8px;right:10px;background:transparent;
                       border:none;font-size:1.2em;color:#7d7d7d;cursor:pointer;">×</button>
        <div style="font-weight:700;color:#33507e;margin-bottom:4px;">
          Build your Rule of Life
        </div>
        <div style="font-size:0.9em;color:#444;margin-bottom:10px;">{escape(sub)}</div>
        <a href="/frol-wizard" class="frol-btn"
           style="background:#4a6fa5;color:#fff;border-radius:8px;padding:8px 14px;
                  text-decoration:none;font-weight:700;font-size:0.9em;display:inline-block;">
          {label} &rarr;
        </a>
      </div>
      <script>
        (function(){{
          try {{
            if (document.cookie.indexOf('frol_card_dismissed=1') !== -1) {{
              var c = document.getElementById('frol-setup-card');
              if (c) c.style.display = 'none';
            }}
          }} catch(e) {{}}
        }})();
      </script>
    """


# ── Lucy chat context for the wizard ────────────────────────────────────────

def build_wizard_chat_context(progress: dict) -> str:
    cur = int(progress.get("current_step", 1) or 1)
    data_so_far = json.dumps(progress.get("data", {}), indent=2)[:3000]
    notes = derive_heuristic_notes(progress)
    note_block = ""
    if notes:
        note_block = "Patterns you might gently mention:\n- " + "\n- ".join(notes)
    return f"""You are Lucy, a warm Catholic family friend helping a mom (Lauren)
build her family's Rule of Life. You are walking her through a 10-step setup
wizard. The user is currently on step {cur}.

Your style: maternal, encouraging, never anxious or pushy. Ask ONE question
at a time. When the user answers, briefly affirm it and ask the next question.
Keep replies under 4 sentences.

When the user gives you a concrete answer that fills a wizard field, emit a
hidden tag like:
  <frol-set field="FIELD_NAME" value="VALUE" />
The browser strips these tags and writes the value into the form. Use the
same field names that appear in the form (e.g. `morning_time`, `breakfast_time`,
`homeschool_yes`).

For times, use 24-hour HH:MM. For yes/no, use "yes" or "no".

Collected so far:
```
{data_so_far}
```

{note_block}

Speak warmly. Make this feel like a friend on the porch, not a form.
"""
# ── Finalize: write to real data files ──────────────────────────────────────

def finalize_wizard() -> dict:
    """Apply the wizard's collected data to day_templates, app_settings,
    and prayer_intentions. Backs up day_templates first."""
    p = load_progress()
    d = p.get("data", {}) or {}
    summary = {"day_templates_written": [], "settings_merged": False,
               "prayer_added": 0, "backups": []}

    # 1. Back up + write day templates from per-person summaries.
    summaries = _build_person_summaries(p)
    if summaries:
        os.makedirs(DAY_TEMPLATES_DIR, exist_ok=True)
        # Build a 30-min slot grid 6:00 AM – 9:30 PM.
        slots = []
        for hour in range(6, 22):
            for mm in (0, 30):
                hr12 = hour - 12 if hour > 12 else (12 if hour == 0 else hour)
                ampm = "AM" if hour < 12 else "PM"
                slots.append(f"{hr12}:{mm:02d} {ampm}")
        for weekday in WEEKDAYS:
            path = os.path.join(DAY_TEMPLATES_DIR, f"{weekday}.json")
            if os.path.exists(path):
                bak = path + ".bak_pre_frol_wizard"
                try:
                    shutil.copy2(path, bak)
                    summary["backups"].append(bak)
                except Exception:
                    pass
            grid = {}
            for nm, rows in summaries.items():
                slot_grid = {s: "" for s in slots}
                for t, act in rows:
                    label = _to_slot_label(t)
                    if label and label in slot_grid:
                        slot_grid[label] = act
                grid[nm] = slot_grid
            safe_save_json(path, {"weekday": weekday, "grid": grid})
            summary["day_templates_written"].append(weekday)

    # 2. Merge family-level into app_settings.json.
    try:
        s = {}
        if os.path.exists(APP_SETTINGS_FILE):
            with open(APP_SETTINGS_FILE, encoding="utf-8") as fh:
                s = json.load(fh)
        members = (d.get("step_1", {}) or {}).get("members", []) or []
        bdays = s.get("child_birthdays", {}) or {}
        colors = s.get("child_colors", {}) or {}
        for m in members:
            nm = (m.get("name") or "").strip()
            if not nm: continue
            if m.get("birthday"):
                bdays[nm] = m["birthday"]
            if m.get("color"):
                colors.setdefault(nm, {})["bg"] = m["color"]
        s["child_birthdays"] = bdays
        s["child_colors"] = colors
        # Health bucket from step 8 — merge non-destructively: only update
        # keys the user actually filled in. Preserves existing health data
        # if step 8 was skipped or partially completed.
        _s8 = d.get("step_8", {}) or {}
        _existing_health = (s.setdefault("family_constraints", {})
                              .setdefault("health", {}) or {})
        for _hk in ("tracked_members", "medications", "recurring_appts",
                    "notif_channels", "notif_phone", "notif_email",
                    "emergency_contacts"):
            if _hk not in _s8:
                continue
            _hv = _s8.get(_hk)
            # Skip empty strings/lists so blanks don't clobber existing values.
            if _hv in ("", [], None):
                continue
            if _hk == "emergency_contacts" and isinstance(_hv, list):
                _hv = [c for c in _hv if isinstance(c, dict) and any(
                    (c.get(k) or "").strip() for k in ("name","phone","email"))]
                if not _hv:
                    continue
            _existing_health[_hk] = _hv
        s["family_constraints"]["health"] = _existing_health
        safe_save_json(APP_SETTINGS_FILE, s)
        summary["settings_merged"] = True
    except Exception:
        pass

    # 3. Append prayer schedule to prayer_intentions.json (repeating).
    try:
        pi = {"daily": [], "repeating": [], "novenas": []}
        if os.path.exists(PRAYER_INTENTIONS_FILE):
            with open(PRAYER_INTENTIONS_FILE, encoding="utf-8") as fh:
                pi = json.load(fh)
        pi.setdefault("repeating", [])
        s3 = d.get("step_3", {}) or {}
        added = 0
        def _add(text, when):
            nonlocal added
            entry = {
                "text":         text,
                "schedule":     when,
                "repeat_days":  ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "added_iso":    datetime.now().date().isoformat(),
                "source":       "frol_wizard",
            }
            if not any(e.get("text") == text and e.get("source") == "frol_wizard"
                       for e in pi["repeating"]):
                pi["repeating"].append(entry)
                added += 1
        # Morning prayer: first checked option in the multi group, fall back
        # to a generic label so finalize still records something useful.
        _morning_multi = s3.get("morning_prayers_multi") or []
        for _mp in _morning_multi:
            _add(_mp, s3.get("morning_time", ""))
        if not _morning_multi and s3.get("morning_time"):
            _add("Morning prayer", s3.get("morning_time", ""))
        for t in (s3.get("angelus_times") or []):
            _add(f"Angelus ({t})", t)
        if s3.get("divine_mercy_3pm") == "yes":
            _add("Divine Mercy Chaplet", "15:00")
        if s3.get("evening_rosary_time"):
            _add("Family Rosary", s3["evening_rosary_time"])
        # Evening / night prayers come from the new multi-checkbox groups.
        for _ep in (s3.get("evening_prayers_multi") or []):
            _add(_ep, s3.get("evening_rosary_time", "") if _ep == "Rosary" else "")
        for _np in (s3.get("night_prayers_multi") or []):
            _add(_np, "")
        safe_save_json(PRAYER_INTENTIONS_FILE, pi)
        summary["prayer_added"] = added
    except Exception:
        pass

    # 4. Stamp finalized_at.
    p["finalized_at"] = datetime.now().isoformat(timespec="seconds")
    p["current_step"] = WIZARD_TOTAL_STEPS
    save_progress(p)
    summary["finalized_at"] = p["finalized_at"]

    # 5. Optional AI scheduling suggestions (only when the user opted in on
    # the Step 10 review checkbox). One Anthropic call; failure is silent
    # so finalize never appears to break.
    try:
        _wants = _v(p, 10, "want_ai_suggestions", "")
        if _wants in ("1", "yes", "true", True) and has_anthropic_key():
            _sug = _generate_scheduling_suggestions(p)
            if _sug:
                p["ai_suggestions"] = _sug
                save_progress(p)
                summary["ai_suggestions_generated"] = True
    except Exception as _se:
        summary["ai_suggestions_error"] = str(_se)

    return summary


def _generate_scheduling_suggestions(progress: dict) -> str:
    """Ask Claude for specific day & time scheduling recommendations based on
    the wizard's collected fixed commitments and selected activities."""
    import urllib.request as _req
    api_key = get_anthropic_key()
    if not api_key:
        return ""
    d = progress.get("data", {}) or {}
    snapshot = json.dumps(d, indent=2)[:4000]
    system = (
        "You are Lucy, a warm Catholic family-rhythm planner. Given a family's "
        "fixed weekly commitments and the activities they want to anchor "
        "(prayer, meals, exercise, school, traditions), produce 5–8 specific "
        "scheduling suggestions. Each suggestion must name a concrete day and "
        "time window (e.g., 'Wednesday 7:00–7:30 AM family Rosary'). Group by "
        "morning/afternoon/evening when natural. Keep each line short and "
        "actionable. Be encouraging, not prescriptive. End with one gentle "
        "sentence inviting them to adjust freely."
    )
    user = (
        "Here is the family's collected Rule of Life data (JSON):\n\n"
        f"{snapshot}\n\n"
        "Please suggest specific day & time slots for the activities they "
        "selected (checkbox lists like common_anchors, morning/evening/night "
        "prayers, traditions, meal_prep_who, batch_cook_days, chore_time_blocks, "
        "subjects_multi, who_exercises_multi, recurring_appt_types) that don't "
        "yet have explicit times — taking their fixed commitments and existing "
        "anchor times into account. Format as plain text, one suggestion per "
        "line, with a blank line between morning/afternoon/evening groups."
    )
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 700,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    try:
        req = _req.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with _req.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
        return (result["content"][0]["text"] or "").strip()
    except Exception:
        return ""


def _to_slot_label(t: str) -> str:
    """Convert HH:MM (24-hr) to 'H:MM AM/PM' label used in day_templates."""
    if not t or ":" not in t:
        return ""
    try:
        hh, mm = t.split(":", 1)
        hh = int(hh); mm = int(mm[:2])
        if mm < 15:    mm = 0
        elif mm < 45:  mm = 30
        else:          hh += 1; mm = 0
        ampm = "AM" if hh < 12 else "PM"
        h12 = hh - 12 if hh > 12 else (12 if hh == 0 else hh)
        return f"{h12}:{mm:02d} {ampm}"
    except Exception:
        return ""
