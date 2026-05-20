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
import re
import json
import shutil
import hashlib
import urllib.request
from datetime import datetime
from data_helpers import save_frol_activities
from html import escape

from config import (
    FROL_WIZARD_PROGRESS_FILE,
    APP_SETTINGS_FILE,
    PRAYER_INTENTIONS_FILE,
    DAY_TEMPLATES_DIR,
    DAY_TEMPLATES_PREVIEW_DIR,
    DAY_TEMPLATES_BACKUP_DIR,
)
from data_helpers import safe_save_json


WIZARD_TOTAL_STEPS = 10
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
    (11, "holidays",     "Holidays & Feast Days",      "Catholic feasts and US holidays — what changes"),
    (12, "durations",    "How Long Does Each Activity Take?",
                                                       "Set a realistic time for each thing in your rule"),
    (13, "build",        "Build Your Day",             "Visual placement on the timeline"),
    (14, "commitments",  "Seven Commitments Check",    "Where the day reflects each commitment"),
    (15, "review",       "AI Review & Save",           "Multitasking, development, optimization — then Save"),
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


_V3_SEED_NARRATIVE_KEYS = {
    "notes", "extra_notes", "other_notes", "other", "comments",
    "free_text", "anything_else", "additional_info", "considerations",
    "narrative", "context", "background",
}


def _seed_v3_activities_from_progress(progress: dict) -> None:
    """One-shot Phase C seed pass. For each §2-§10 section bucket, parse
    any obviously-compatible list-shaped answers into Phase A activity
    entries and stash narrative free-text fields under a `wizard_answers`
    blob on the same bucket. Idempotent at the section level — if any
    activity already exists for a section, that section is skipped.

    No-op-safe on failure: callers wrap in try/except so a malformed
    bucket cannot block the v3 migration.
    """
    from data_helpers import load_frol_activities, save_frol_activities

    data = progress.get("data") or {}
    if not isinstance(data, dict):
        return
    try:
        existing = load_frol_activities() or []
    except Exception:
        existing = []
    sections_with_activities = set()
    for it in existing:
        if isinstance(it, dict) and it.get("section") is not None:
            try:
                sections_with_activities.add(int(it["section"]))
            except (TypeError, ValueError):
                continue

    # (section, list-key, category, default_duration_min)
    _SEED_RULES = [
        (3,  "morning_prayers_multi", "prayer", 15),
        (3,  "evening_prayers_multi", "prayer", 15),
        (3,  "night_prayers_multi",   "prayer", 10),
        (5,  "meal_prep_who",         "meal",   30),
        (6,  "subjects_multi",        "school", 30),
        (7,  "chore_time_blocks",     "chore",  20),
        (8,  "types",                 "health", 30),
        (9,  "traditions",            "rest",   60),
    ]

    new_items = list(existing)
    appended = 0
    for sec_num, key, cat, dur in _SEED_RULES:
        if sec_num in sections_with_activities:
            continue
        bucket = data.get(f"section_{sec_num}") or {}
        if not isinstance(bucket, dict):
            continue
        items = bucket.get(key) or []
        if not isinstance(items, list):
            continue
        for raw in items:
            name = str(raw).strip()
            if not name:
                continue
            new_items.append({
                "id":               "",  # filled by save_frol_activities
                "name":             name[:80],
                "section":          sec_num,
                "who_type":         "family",
                "who":              [],
                "leader":           "",
                "per_person_times": {},
                "time":             "",
                "duration_min":     int(dur),
                "days":             ["Monday", "Tuesday", "Wednesday",
                                     "Thursday", "Friday"],
                "schedule_variant": ["weekday"],
                "category":         cat,
                "color":            "",
                "credits":          [],
                "seasonal":         "year_round",
                "is_grooming":      False,
                "_seeded_v3":       True,
            })
            appended += 1

    # Preserve narrative free-text in wizard_answers per section so the
    # builder UI in §§2-10 can surface it back to the user even though
    # the activity list takes over the structured fields.
    for sec_num in range(2, 11):
        bucket = data.get(f"section_{sec_num}")
        if not isinstance(bucket, dict):
            continue
        narrative = {}
        for k, v in list(bucket.items()):
            if k == "wizard_answers" or k.startswith("durations__"):
                continue
            if isinstance(v, str) and (k in _V3_SEED_NARRATIVE_KEYS
                                       or len(v.strip()) > 80):
                narrative[k] = v
        if narrative:
            existing_wa = bucket.get("wizard_answers")
            if not isinstance(existing_wa, dict):
                existing_wa = {}
            # Don't clobber prior wizard_answers entries.
            for k, v in narrative.items():
                existing_wa.setdefault(k, v)
            bucket["wizard_answers"] = existing_wa

    if appended:
        try:
            save_frol_activities(new_items)
        except Exception:
            pass


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
    # ─── v3 one-time renumber migration ─────────────────────────────────
    # When the new §11 Holiday & Feast Day was inserted, sections 11..14
    # shifted forward by one to become 12..15. We stamp schema_version="v3"
    # the first time we run, write a backup, and shift the four affected
    # buckets in DESCENDING order so we never double-shift.
    if base.get("schema_version") != "v3" and isinstance(base.get("data"), dict):
        # Backup BEFORE we mutate — uses safe_save_json so the write is
        # atomic (the architectural rule for this project: every JSON
        # write goes through safe_save_json, never raw open/json.dump).
        try:
            backup_path = FROL_WIZARD_PROGRESS_FILE.replace(
                ".json", ".v2_backup.json")
            if not os.path.exists(backup_path):
                safe_save_json(backup_path, base)
        except Exception:
            pass
        _v3d = base["data"]
        # Descending order means each destination has just been vacated
        # by the previous step, so we don't need the "_k_to not in _v3d"
        # guard. Any stale payload sitting in a destination bucket prior
        # to migration is moved out first by its own iteration. This
        # avoids leaving orphaned old data stranded under 11-14 in
        # mixed-shape snapshots.
        for _from, _to in ((14, 15), (13, 14), (12, 13), (11, 12)):
            _k_from = f"section_{_from}"
            _k_to = f"section_{_to}"
            if _k_from in _v3d:
                _v3d[_k_to] = _v3d.pop(_k_from)
        # Bump completed_steps + current_step pointers to match.
        _comp = base.get("completed_steps") or []
        if isinstance(_comp, list):
            _comp_new = []
            for _s in _comp:
                try:
                    _si = int(_s)
                except (TypeError, ValueError):
                    continue
                _comp_new.append(_si + 1 if 11 <= _si <= 14 else _si)
            base["completed_steps"] = _comp_new
        _cur = base.get("current_step")
        try:
            if isinstance(_cur, int) and 11 <= _cur <= 14:
                base["current_step"] = _cur + 1
        except Exception:
            pass
        base["schema_version"] = "v3"
        # One-shot seed pass: convert any compatible list-shaped answers in
        # §§2-10 into Phase A activity entries, and stash narrative
        # free-text into wizard_answers on each section bucket. Guarded by
        # data["v3_seeded"] so this only runs once even if the v3 stamp
        # were ever cleared. Failures here must not block the migration.
        try:
            if not _v3d.get("v3_seeded"):
                _seed_v3_activities_from_progress(base)
                _v3d["v3_seeded"] = True
        except Exception as _se:
            try:
                debug_log(f"frol v3 seed failed: {_se}")
            except Exception:
                pass
        try:
            safe_save_json(FROL_WIZARD_PROGRESS_FILE, base)
        except Exception:
            pass
    # One-time renumber migration: when §11 duration picker was inserted,
    # old §11 (Build Your Day) shifted to §12 and old §13 (AI Review) to §14.
    # Only scalar settings are carried over. placements_* keys are NOT
    # migrated — the legacy list-shaped placement data is incompatible with
    # the renderer (which expects a dict keyed by HHMM slot), and the new
    # AI-generated schedule replaces the old manual placement approach.
    _pdata = base.get("data") or {}
    if isinstance(_pdata, dict):
        _old11 = _pdata.get("section_11") or {}
        _new12 = _pdata.get("section_12") or {}
        if isinstance(_old11, dict) and not _new12:
            _carry12 = {}
            for _k in ("current_day", "weekend_view", "per_person_filter"):
                if _k in _old11:
                    _carry12[_k] = _old11[_k]
            if _carry12:
                _pdata["section_12"] = _carry12
        # Defensive normalization: a previous buggy migration may have left
        # section_12 with list-shaped placements_* values that crash the
        # renderer. Coerce any non-dict section_12 to {} and drop any
        # placements_* key whose value isn't a dict.
        _s12 = _pdata.get("section_12")
        if not isinstance(_s12, dict):
            _pdata["section_12"] = {}
        else:
            for _k in list(_s12.keys()):
                if _k.startswith("placements_") and not isinstance(_s12[_k], dict):
                    del _s12[_k]
        _old13 = _pdata.get("section_13") or {}
        _new14 = _pdata.get("section_14") or {}
        if (isinstance(_old13, dict) and not _new14 and any(
                k == "receipt" or k.startswith("review_")
                for k in _old13.keys())):
            _pdata["section_14"] = dict(_old13)
        base["data"] = _pdata
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

    def _v2_title(i: int) -> str:
        for (idx, _slug, t, _sub) in V2_SECTIONS:
            if idx == i:
                return t
        return f"Section {i}"

    back_link = ""
    if section > 1:
        _prev_title = _v2_title(section - 1)
        back_link = (f'<a href="/frol-wizard?step={section-1}&mode={escape(mode, quote=True)}"'
                     f' class="frol-btn ghost">&larr; {escape(_prev_title)}</a>')
    advance_label = ("Save & Continue" if section < V2_TOTAL_SECTIONS
                     else "Save my Rule of Life")
    next_dest_html = ""
    if section < V2_TOTAL_SECTIONS:
        _next_title = _v2_title(section + 1)
        next_dest_html = (
            f'<div style="font-size:0.78em;color:#6b7280;margin-top:3px;'
            f'text-align:center;">{escape(_next_title)} &rarr;</div>'
        )
    chat_panel = ""
    if mode == "lucy" and lucy_visible:
        chat_panel = _render_chat_panel(section)

    # ── Fix 3 (generalized): don't wrap bodies that already contain a <form>
    # in the outer advance_v2 form. HTML forbids nesting <form>s: the
    # parser silently DROPS the inner <form> tag, all its hidden inputs
    # end up inside the outer form, and the FIRST input named "action"
    # wins. That broke §14 (Save button POSTing finalize_v2 was hijacked
    # by the outer advance_v2 form, redirecting to a phantom step+1) and
    # also breaks §12 Stage A — each question-option is its own <form>
    # posting action=s12_answer, but nesting causes the click to fire
    # advance_v2 instead, silently skipping past §12 without saving the
    # answer. Auto-detect inner <form> tags and, if present, skip the
    # outer form entirely; the body's own forms handle submission.
    # Compute _body_has_form against the ORIGINAL body so the Phase C
    # mount (which contains its own <form>s for the variant tab bar and
    # activity builder) does not trip the outer-form bypass below. If we
    # let the mount's forms count, sections §2-§10 would lose their
    # Save & Continue button and the V2 autosave probe in
    # static/js/frol_wizard.js (which checks #frol-form[data-version="2"])
    # would silently fall back to legacy save_field / step_N writes.
    _body_has_form = 'action="/frol-wizard"' in body_html
    # Phase C: §2-§10 auto-mount the variant tab bar + activity builder
    # + grid preview as a SIBLING of (not inside) the outer #frol-form.
    # The phase-c block contains its own <form>s (variant tabs, activity
    # builder CRUD), and HTML forbids nesting <form>s — the parser
    # silently DROPS the inner <form> tags and merges all their hidden
    # inputs into the outer form, hijacking the submit action. By
    # emitting phase_c_html AFTER the closing </form>, we avoid the
    # nesting entirely while still keeping the outer form (and its
    # Save & Continue + V2 autosave wiring) intact for §2-§10.
    # Sections 1, 11 (holidays), 12 (durations), 13 (build), 14
    # (commitments) and 15 (review) opt out — they have their own
    # structure.
    try:
        _phase_c_sec = int(section)
    except (TypeError, ValueError):
        _phase_c_sec = 0
    phase_c_html = ""
    if 2 <= _phase_c_sec <= 10:
        phase_c_html = _render_phase_c_block(_phase_c_sec, progress, mode)
    if section >= V2_TOTAL_SECTIONS or _body_has_form:
        main_block = f"""
          {dots}
          <div class="frol-card">
            <h2 class="frol-title">{escape(title)}</h2>
            <p class="frol-sub">{escape(subtitle)}</p>
            {render_lucy_hint_slot(section)}
            {body_html}
            <div class="frol-actions" style="margin-top:18px;">
              <div>{back_link}</div>
              <div></div>
            </div>
            {phase_c_html}
          </div>
        """
    else:
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
                  <div style="display:flex;flex-direction:column;align-items:stretch;">
                    <button type="submit" class="frol-btn">{advance_label} &rarr;</button>
                    {next_dest_html}
                  </div>
                </div>
              </div>
            </form>
            {phase_c_html}
          </div>
        """
    if chat_panel:
        return f'<div class="frol-with-chat">{main_block}{chat_panel}</div>'
    return main_block


# ── V3 shared activity builder (Phase A) ────────────────────────────────────
# Self-contained — does not touch any existing section renderer. Phases B-D
# will mount _render_activity_builder()/_render_activity_card() inside the
# section pages and grid preview.

ACTIVITY_CATEGORIES = [
    ("prayer",   "Prayer",        "#7c3aed"),
    ("meal",     "Meal",          "#d97706"),
    ("school",   "School",        "#2563eb"),
    ("chore",    "Chore",         "#0891b2"),
    ("rest",     "Rest / Sleep",  "#475569"),
    ("family",   "Family time",   "#16a34a"),
    ("personal", "Personal",      "#db2777"),
    ("health",   "Health / Fitness", "#dc2626"),
    ("fixed",    "Fixed / Other", "#64748b"),
]

ACTIVITY_VARIANTS = [
    ("weekday",         "Weekday (Mon–Fri)"),
    ("saturday",        "Saturday"),
    ("sunday",          "Sunday"),
    ("john_traveling",  "John is traveling"),
]


def _category_color(cat: str) -> str:
    for key, _label, color in ACTIVITY_CATEGORIES:
        if key == cat:
            return color
    return "#64748b"


_SAFE_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def _safe_color(c: str, fallback: str = "#64748b") -> str:
    """Allow only #RGB / #RRGGBB hex tokens through to inline style attrs.
    Anything else (including empty, named colors, or attacker-controlled
    text) is replaced with the fallback so we never inject CSS-breakout
    characters into a style="..." block."""
    if isinstance(c, str) and _SAFE_COLOR_RE.fullmatch(c.strip()):
        return c.strip()
    return fallback


def _category_label(cat: str) -> str:
    for key, label, _color in ACTIVITY_CATEGORIES:
        if key == cat:
            return label
    return cat or "—"


def _activity_persons(progress: dict) -> list:
    """Names of every adult + child in the family. Drives the Step C
    person-pickers. Falls back to a sensible default if no members exist."""
    members = _v2_members(progress) or []
    names = []
    for m in members:
        if isinstance(m, dict):
            n = (m.get("name") or "").strip()
            if n and n not in names:
                names.append(n)
    if not names:
        names = ["Lauren", "John", "JP", "Joseph", "Michael", "James"]
    return names


def _fmt_time_12h(t: str) -> str:
    """'09:30' -> '9:30 AM'. Returns the input unchanged if it can't parse."""
    if not t or ":" not in t:
        return t or ""
    try:
        hh, mm = t.split(":", 1)
        hh_i = int(hh)
        mm_i = int(mm)
    except (ValueError, TypeError):
        return t
    suffix = "AM" if hh_i < 12 else "PM"
    h12 = hh_i % 12 or 12
    return f"{h12}:{mm_i:02d} {suffix}"


def _render_activity_edit_form(activity: dict, section: int, mode: str,
                               active_variant: str = "weekday") -> str:
    """Inline edit form embedded in each card's <details> drawer. Mirrors
    the builder fields but is pre-populated and posts to /frol-edit-activity.
    Kept compact (single column) so it fits inside the card."""
    aid = escape(str(activity.get("id") or ""), quote=True)
    name = escape(activity.get("name") or "", quote=True)
    wt = activity.get("who_type") or "individual"
    cat = activity.get("category") or ""
    seas = activity.get("seasonal") or "year_round"
    days_set = set(activity.get("days") or [])
    vars_set = set(activity.get("schedule_variant") or ["weekday"])
    mode_esc = escape(mode, quote=True)
    sec_esc = str(int(section))
    persons = ["Lauren", "John", "JP", "Joseph", "Michael", "James"]
    # Time/duration fields differ by who_type — render all three but
    # show only the relevant one (no JS toggle here since who_type
    # rarely changes after creation; user can delete + re-add for that).
    if wt == "family":
        t_val = escape(activity.get("time") or "", quote=True)
        d_val = int(activity.get("duration_min") or 0)
        time_block = (f'<label style="font-size:11px;color:#6b7280;">Time</label>'
                      f'<input type="time" name="time" value="{t_val}" '
                      f'style="width:100%;padding:5px;border:1px solid #d1d5db;border-radius:6px;margin-bottom:4px;">'
                      f'<label style="font-size:11px;color:#6b7280;">Duration (min)</label>'
                      f'<input type="number" name="duration_min" min="0" max="600" value="{d_val}" '
                      f'style="width:100%;padding:5px;border:1px solid #d1d5db;border-radius:6px;">')
    elif wt == "individual":
        # Render the single-person row using the server's individual-branch
        # field names (single_time/single_duration_min) so edits actually
        # persist. who_single is hidden — person identity doesn't change
        # via the edit drawer (delete + re-add for that).
        who_lst = activity.get("who") or []
        if who_lst:
            p0 = who_lst[0]
            slot = (activity.get("per_person_times") or {}).get(p0) or {}
            pt = escape(slot.get("time") or "", quote=True)
            pd = int(slot.get("duration_min") or 0)
            time_block = (
                f'<input type="hidden" name="who_single" value="{escape(p0, quote=True)}">'
                f'<div style="font-size:11px;color:#374151;margin-bottom:4px;">'
                f'For: <strong>{escape(p0)}</strong></div>'
                f'<label style="font-size:11px;color:#6b7280;">Time</label>'
                f'<input type="time" name="single_time" value="{pt}" '
                f'style="width:100%;padding:5px;border:1px solid #d1d5db;border-radius:6px;margin-bottom:4px;">'
                f'<label style="font-size:11px;color:#6b7280;">Duration (min)</label>'
                f'<input type="number" name="single_duration_min" min="0" max="600" value="{pd}" '
                f'style="width:100%;padding:5px;border:1px solid #d1d5db;border-radius:6px;">'
            )
        else:
            time_block = '<em style="font-size:11px;color:#9ca3af;">No person assigned.</em>'
    else:
        # mixed
        ppt = activity.get("per_person_times") or {}
        rows = []
        for p in (activity.get("who") or []):
            slot = ppt.get(p) or {}
            pt = escape(slot.get("time") or "", quote=True)
            pd = int(slot.get("duration_min") or 0)
            p_safe = escape(str(p), quote=True)
            p_disp = escape(str(p))
            rows.append(
                f'<div style="display:grid;grid-template-columns:80px 1fr 80px;gap:4px;'
                f'margin-bottom:3px;align-items:center;">'
                f'<span style="font-size:11px;color:#374151;">{p_disp}</span>'
                f'<input type="time" name="person_{p_safe}_time" value="{pt}" '
                f'style="padding:4px;border:1px solid #d1d5db;border-radius:4px;font-size:11px;">'
                f'<input type="number" name="person_{p_safe}_duration_min" value="{pd}" min="0" max="600" '
                f'style="padding:4px;border:1px solid #d1d5db;border-radius:4px;font-size:11px;">'
                f'</div>'
            )
            # Also include hidden checkbox-equivalent so server sees who:
            rows.append(f'<input type="hidden" name="who" value="{p_safe}">')
        time_block = "".join(rows) if rows else '<em style="font-size:11px;color:#9ca3af;">No people assigned.</em>'
    day_chips = "".join(
        f'<label style="font-size:11px;margin-right:4px;">'
        f'<input type="checkbox" name="days" value="{d}"{" checked" if d in days_set else ""}> {d[:3]}'
        f'</label>'
        for d in WEEKDAYS
    )
    var_chips = "".join(
        f'<label style="font-size:11px;margin-right:4px;">'
        f'<input type="checkbox" name="schedule_variant" value="{vk}"'
        f'{" checked" if vk in vars_set else ""}> {escape(vl)}'
        f'</label>'
        for vk, vl in ACTIVITY_VARIANTS
    )
    cat_opts = "".join(
        f'<option value="{k}"{" selected" if k == cat else ""}>{escape(l)}</option>'
        for k, l, _c in ACTIVITY_CATEGORIES
    )
    seas_opts = "".join(
        f'<option value="{k}"{" selected" if k == seas else ""}>{escape(l)}</option>'
        for k, l in (("year_round","Year-round"),("school_year","School year"),("summer","Summer"))
    )
    leader_opts = '<option value="">— none —</option>' + "".join(
        f'<option value="{escape(p, quote=True)}"'
        f'{" selected" if p == activity.get("leader") else ""}>{escape(p)}</option>'
        for p in persons
    )
    credits_val = escape(",".join(activity.get("credits") or []), quote=True)
    grm_chk = " checked" if activity.get("is_grooming") else ""
    return f"""
    <form method="POST" action="/frol-edit-activity"
          style="margin-top:8px;padding:8px;background:#f9fafb;border:1px solid #e5e7eb;
                 border-radius:6px;font-size:12px;">
      <input type="hidden" name="id" value="{aid}">
      <input type="hidden" name="section" value="{sec_esc}">
      <input type="hidden" name="mode" value="{mode_esc}">
      <input type="hidden" name="who_type" value="{escape(wt, quote=True)}">
      <input type="hidden" name="active_variant" value="{escape((active_variant or 'weekday'), quote=True)}">
      <label style="font-size:11px;color:#6b7280;">Name</label>
      <input type="text" name="name" value="{name}" required
             style="width:100%;padding:5px;border:1px solid #d1d5db;border-radius:6px;margin-bottom:6px;">
      {time_block}
      <div style="margin-top:6px;">{day_chips}</div>
      <div style="margin-top:4px;">{var_chips}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-top:6px;">
        <div><label style="font-size:11px;color:#6b7280;">Category</label>
          <select name="category" style="width:100%;padding:5px;border:1px solid #d1d5db;border-radius:6px;">{cat_opts}</select></div>
        <div><label style="font-size:11px;color:#6b7280;">Seasonal</label>
          <select name="seasonal" style="width:100%;padding:5px;border:1px solid #d1d5db;border-radius:6px;">{seas_opts}</select></div>
        <div><label style="font-size:11px;color:#6b7280;">Leader</label>
          <select name="leader" style="width:100%;padding:5px;border:1px solid #d1d5db;border-radius:6px;">{leader_opts}</select></div>
      </div>
      <label style="font-size:11px;color:#6b7280;display:block;margin-top:6px;">Credits</label>
      <input type="text" name="credits" value="{credits_val}"
             style="width:100%;padding:5px;border:1px solid #d1d5db;border-radius:6px;">
      <label style="display:inline-flex;align-items:center;gap:4px;margin-top:6px;font-size:11px;">
        <input type="checkbox" name="is_grooming" value="1"{grm_chk}> Counts as grooming
      </label>
      <div style="text-align:right;margin-top:8px;">
        <button type="submit" class="frol-btn" style="padding:4px 12px;font-size:12px;">Save changes</button>
      </div>
    </form>
    """


_WHO_TYPE_ICONS = {
    "family":     "&#128106;",   # 👪 family
    "individual": "&#128100;",   # 👤 single bust
    "mixed":      "&#128101;",   # 👥 two busts
}


def _render_activity_card(activity: dict, section: int, mode: str,
                          active_variant: str = "weekday") -> str:
    """Compact chip-style display of one activity. Includes an inline edit
    form (toggled via <details>) and a delete button. All POSTs go to the
    Phase A routes — section pages just embed this card."""
    if not isinstance(activity, dict):
        return ""
    aid = escape(str(activity.get("id") or ""), quote=True)
    name = escape(activity.get("name") or "(unnamed)")
    cat = activity.get("category") or ""
    color = _safe_color(activity.get("color") or "", _category_color(cat))
    who_type = activity.get("who_type") or "individual"
    wt_icon = _WHO_TYPE_ICONS.get(who_type, "&#128100;")
    who_list = activity.get("who") or []
    who_str = ", ".join(escape(str(w)) for w in who_list) or "—"
    # Time summary line.
    if who_type == "family":
        t_str = _fmt_time_12h(activity.get("time") or "")
        dur = int(activity.get("duration_min") or 0)
        time_html = f"{escape(t_str) or '—'} · {dur} min" if (t_str or dur) else "—"
    else:
        ppt = activity.get("per_person_times") or {}
        bits = []
        for n in who_list:
            slot = ppt.get(n) or {}
            t = _fmt_time_12h(slot.get("time") or "")
            d = int(slot.get("duration_min") or 0)
            if t or d:
                bits.append(f"{escape(str(n))} {escape(t) or '?'} · {d}m")
        time_html = " · ".join(bits) if bits else "—"
    av_card = (active_variant or "weekday").strip() or "weekday"
    av_esc = escape(av_card, quote=True)
    edit_form = _render_activity_edit_form(activity, int(section), mode, av_card)
    days_list = activity.get("days") or []
    days_short = "".join((d[:1] if d else "") for d in days_list) or "—"
    variants = activity.get("schedule_variant") or ["weekday"]
    # Variant badges — one chip per variant, short labels.
    _VAR_SHORT = {"weekday": "Wkdy", "saturday": "Sat",
                  "sunday": "Sun", "john_traveling": "John✈"}
    var_badges = "".join(
        f'<span style="display:inline-block;padding:1px 6px;border-radius:10px;'
        f'background:#eef2ff;color:#4338ca;font-size:10px;font-weight:600;'
        f'margin-right:3px;">{escape(_VAR_SHORT.get(v, v))}</span>'
        for v in variants
    ) or '<span style="font-size:10px;color:#9ca3af;">—</span>'
    seasonal = escape(activity.get("seasonal") or "year_round")
    mode_esc = escape(mode, quote=True)
    cat_label = escape(_category_label(cat))
    # Explicit category color dot in addition to the left border.
    color_dot = (f'<span title="{cat_label}" style="display:inline-block;width:10px;'
                 f'height:10px;border-radius:50%;background:{color};'
                 f'margin-right:6px;vertical-align:middle;"></span>')
    return f"""
    <div class="frol-act-card" id="frol-act-{aid}" data-act-id="{aid}"
         style="border-left:4px solid {color};background:#fff;border-radius:8px;
                padding:10px 12px;margin:6px 0;box-shadow:0 1px 2px rgba(0,0,0,.05);">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;">
        <div style="flex:1;min-width:0;">
          <div style="font-weight:600;font-size:14px;color:#1f2937;">
            {color_dot}<span style="font-size:14px;margin-right:4px;" aria-label="{escape(who_type)}"
                  title="{escape(who_type)}">{wt_icon}</span>{name}
          </div>
          <div style="font-size:12px;color:#6b7280;margin-top:2px;">
            <span style="display:inline-block;padding:1px 6px;border-radius:4px;
                         background:{color}22;color:{color};font-weight:600;">{cat_label}</span>
            · {who_str}
          </div>
          <div style="font-size:12px;color:#374151;margin-top:4px;">{time_html}</div>
          <div style="font-size:11px;color:#9ca3af;margin-top:4px;">
            Days: {escape(days_short)} &nbsp; {var_badges} &nbsp; · {seasonal}
          </div>
        </div>
        <div style="display:flex;gap:4px;flex-shrink:0;align-items:flex-start;">
          <details style="margin:0;">
            <summary style="cursor:pointer;padding:4px 8px;font-size:11px;color:#2563eb;
                            list-style:none;">Edit</summary>
            {edit_form}
          </details>
          <form method="POST" action="/frol-delete-activity"
                onsubmit="return confirm('Delete this activity?');" style="margin:0;">
            <input type="hidden" name="id" value="{aid}">
            <input type="hidden" name="section" value="{section}">
            <input type="hidden" name="mode" value="{mode_esc}">
            <input type="hidden" name="active_variant" value="{av_esc}">
            <button type="submit" class="frol-btn ghost"
                    style="padding:4px 8px;font-size:11px;color:#dc2626;">Delete</button>
          </form>
        </div>
      </div>
    </div>
    """


def _render_activity_list(section: int, progress: dict, activities: list,
                          active_variant: str, mode: str) -> str:
    """Render every activity assigned to (section, active_variant) as a
    stack of cards. Phase A scope: section filter + variant filter only."""
    if not isinstance(activities, list):
        return ""
    try:
        sec_int = int(section)
    except (TypeError, ValueError):
        sec_int = 0
    av = (active_variant or "weekday").strip() or "weekday"
    matches = []
    for a in activities:
        if not isinstance(a, dict):
            continue
        if int(a.get("section") or 0) != sec_int:
            continue
        variants = a.get("schedule_variant") or ["weekday"]
        if av not in variants:
            continue
        matches.append(a)
    if not matches:
        return ('<div style="font-size:12px;color:#9ca3af;font-style:italic;'
                'padding:8px 0;">No activities yet for this section.</div>')
    return "".join(_render_activity_card(a, sec_int, mode, av) for a in matches)


# ─── Phase B — Persistent live grid preview ─────────────────────────────
# A reusable component that renders the per-person daily grid (time rows ×
# person columns) at the bottom of any section page. Phase B builds the
# component only; Phase C mounts it into every section.

GRID_PERSONS = ["Lauren", "John", "JP", "Joseph", "Michael", "James"]

# 36 half-hour slots from 05:00 through 22:30 inclusive. The task spec
# says "34 rows from 5:00 AM to 10:30 PM" — those two numbers don't agree
# (34 half-hours from 05:00 ends at 21:30; 22:30 needs 36). We honor the
# end-label "10:30 PM" since that's what the user sees and what fits the
# family's actual bedtime data (e.g. 22:00 Bedtime in current fixture).
GRID_SLOTS = [(h, m) for h in range(5, 23) for m in (0, 30)]

# Default visible person columns per section. Sections that center around
# the whole family default to everyone; the Little Ones / school / chores
# sections default to the relevant subset so the grid isn't visually busy
# when there's nothing to look at in the other columns. Stored toggle
# state in progress.data.section_{N}.grid_visible_persons overrides this.
SECTION_DEFAULT_VISIBLE = {
    2:  ["James", "Michael", "Lauren"],
    6:  ["JP", "Joseph", "Michael", "Lauren"],
    7:  ["Lauren", "John", "JP", "Joseph", "Michael"],
    8:  ["Lauren", "John", "JP", "Joseph", "Michael"],
}


def _grid_time_label(hh: int, mm: int) -> str:
    """5,0 -> '5:00 AM'; 22,30 -> '10:30 PM'."""
    suffix = "AM" if hh < 12 else "PM"
    h12 = hh % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{mm:02d} {suffix}"


def _grid_parse_hhmm(t):
    """'09:30' -> 570 (minutes since midnight). None on failure."""
    if not t or ":" not in str(t):
        return None
    try:
        parts = str(t).split(":", 1)
        return int(parts[0]) * 60 + int(parts[1][:2])
    except Exception:
        return None


def _grid_activity_placements(act: dict):
    """Yield (person, start_min, dur_min) tuples for one activity. Reads
    the right field per who_type: family uses top-level time/duration;
    individual + mixed use per_person_times[person]."""
    wt = (act.get("who_type") or "individual").strip() or "individual"
    who = act.get("who") or []
    out = []
    if wt == "family":
        sm = _grid_parse_hhmm(act.get("time") or "")
        try:
            dm = int(act.get("duration_min") or 0)
        except (TypeError, ValueError):
            dm = 0
        if sm is None:
            return out
        for p in who:
            if isinstance(p, str) and p.strip():
                out.append((p.strip(), sm, dm))
        return out
    ppt = act.get("per_person_times") or {}
    for p in who:
        if not (isinstance(p, str) and p.strip()):
            continue
        pp = ppt.get(p) or {}
        sm = _grid_parse_hhmm(pp.get("time") or "")
        if sm is None:
            continue
        try:
            dm = int(pp.get("duration_min") or 0)
        except (TypeError, ValueError):
            dm = 0
        out.append((p.strip(), sm, dm))
    return out


def _grid_visible_persons(section: int, progress: dict) -> list:
    """Resolve the visible person columns for this section. Order is
    always the canonical GRID_PERSONS order so the grid is stable across
    toggles. Stored override under section_{N}.grid_visible_persons wins;
    otherwise falls back to SECTION_DEFAULT_VISIBLE or full roster."""
    bucket = ((progress.get("data") or {})
              .get(f"section_{int(section)}") or {})
    stored = bucket.get("grid_visible_persons")
    if isinstance(stored, list) and stored:
        keep = {str(s).strip() for s in stored if str(s).strip()}
        return [p for p in GRID_PERSONS if p in keep]
    default = SECTION_DEFAULT_VISIBLE.get(int(section), GRID_PERSONS)
    return [p for p in GRID_PERSONS if p in default]


def _grid_chip_html(act: dict, start_min: int, dur_min: int,
                    rowspan: int, is_overlay: bool = False) -> str:
    """Render the inner activity chip. End time appears at the bottom
    only when the activity ends mid-slot (end_min % 30 != 0) and the
    activity actually spans more than one slot.

    is_overlay=True renders a year-over-year ghost chip (faded, dashed
    border, no rowspan, no end-time) used by the Phase F overlay."""
    cat = (act.get("category") or "").strip() or "fixed"
    color = _safe_color(act.get("color") or "", _category_color(cat))
    name = (act.get("name") or "").strip() or "(untitled)"
    sh, sm = divmod(start_min, 60)
    start_lbl = _grid_time_label(sh, sm)
    end_min = start_min + max(0, dur_min)
    eh, em = divmod(end_min, 60)
    end_lbl = _grid_time_label(eh, em) if eh < 24 else ""
    if is_overlay:
        return (
            f'<div class="frol-grid-chip frol-grid-overlay-chip" '
            f'data-overlay="1" '
            f'style="background:{color};color:#fff;border-radius:4px;'
            f'padding:2px 4px;margin:1px 0;min-height:14px;opacity:0.35;'
            f'border:1px dashed rgba(255,255,255,0.85);font-size:9px;'
            f'line-height:1.1;overflow:hidden;font-style:italic;">'
            f'<span style="font-size:8px;opacity:0.9;">{escape(start_lbl)} </span>'
            f'<span style="font-weight:600;">{escape(name)}</span>'
            f'</div>'
        )
    show_end = (rowspan > 1) and (end_min % 30 != 0) and bool(end_lbl)
    end_html = ""
    if show_end:
        end_html = (
            f'<div style="font-size:9px;color:#fff;opacity:0.85;'
            f'text-align:center;margin-top:auto;">{escape(end_lbl)}</div>'
        )
    return (
        f'<div class="frol-grid-chip" '
        f'style="background:{color};color:#fff;border-radius:4px;'
        f'padding:3px 5px;margin:1px 0;min-height:22px;'
        f'display:flex;flex-direction:column;height:100%;'
        f'box-sizing:border-box;font-size:10px;line-height:1.15;'
        f'overflow:hidden;">'
        f'<div style="font-size:9px;opacity:0.85;">{escape(start_lbl)}</div>'
        f'<div style="font-weight:600;flex:1;">{escape(name)}</div>'
        f'{end_html}'
        f'</div>'
    )


def _grid_build_table(section: int, active_variant: str,
                      visible: list, activities: list,
                      overlay_activities: list = None) -> str:
    """Build the inner <table> for the grid. Sticky thead + first column.
    Multi-slot activities use rowspan; collisions in the same start cell
    stack as multiple chips inside one td. Slots covered by a rowspan
    above are skipped (no <td> emitted).

    overlay_activities (Phase F) renders as faded ghost chips inside each
    cell, without contributing to rowspan. Cells inside a current-row
    rowspan continuation will not display overlay chips — an accepted
    edge-case for year-over-year visual comparison."""
    av = (active_variant or "weekday").strip() or "weekday"
    sec_i = int(section)
    # Pre-bucket activity placements per (person, start_slot_index).
    placements = {p: {} for p in visible}
    overlay_placements = {p: {} for p in visible}
    # Fix 2: collect activities that match section + variant but yield no
    # placements (no time, or no who assigned). These are seeded/in-flight
    # activities that Lauren still needs to fill in — show them as a soft
    # gray "needs setup" chip in a dedicated Unscheduled row above the
    # time grid so they don't silently disappear.
    incomplete = []
    for a in activities:
        if not isinstance(a, dict):
            continue
        try:
            if int(a.get("section") or 0) != sec_i:
                continue
        except (TypeError, ValueError):
            continue
        variants = a.get("schedule_variant") or ["weekday"]
        if av not in variants:
            continue
        placed_any = False
        for p, sm, dm in _grid_activity_placements(a):
            if p not in placements:
                continue
            if sm < 5 * 60 or sm >= 5 * 60 + 36 * 30:
                continue
            slot_idx = (sm - 5 * 60) // 30
            placements[p].setdefault(slot_idx, []).append((sm, dm, a))
            placed_any = True
        if not placed_any:
            incomplete.append(a)
    for a in (overlay_activities or []):
        if not isinstance(a, dict):
            continue
        try:
            if int(a.get("section") or 0) != sec_i:
                continue
        except (TypeError, ValueError):
            continue
        variants = a.get("schedule_variant") or ["weekday"]
        if av not in variants:
            continue
        for p, sm, dm in _grid_activity_placements(a):
            if p not in overlay_placements:
                continue
            if sm < 5 * 60 or sm >= 5 * 60 + 36 * 30:
                continue
            slot_idx = (sm - 5 * 60) // 30
            overlay_placements[p].setdefault(slot_idx, []).append((sm, dm, a))
    # Track skip-until-slot per person (rowspan continuation tracker).
    skip_until = {p: -1 for p in visible}
    rows_html = []
    header_cells = ['<th class="frol-grid-corner" '
                    'style="position:sticky;top:0;left:0;z-index:3;'
                    'background:#f6f8fc;border:1px solid #d8e1ef;'
                    'min-width:62px;padding:4px 6px;font-size:10px;'
                    'color:#33507e;">Time</th>']
    for p in visible:
        header_cells.append(
            f'<th class="frol-grid-head" '
            f'style="position:sticky;top:0;z-index:2;'
            f'background:#f6f8fc;border:1px solid #d8e1ef;'
            f'min-width:88px;padding:4px 6px;font-size:11px;'
            f'color:#33507e;font-weight:700;">{escape(p)}</th>'
        )
    thead = "<thead><tr>" + "".join(header_cells) + "</tr></thead>"
    body = []
    # Fix 2: "Unscheduled" row at the top of tbody — one cell across all
    # visible person columns containing a placeholder chip per incomplete
    # activity. Each chip is an anchor link to that activity's card on
    # the same page (#frol-act-{id}) so clicking scrolls to the card,
    # where the Edit drawer can be expanded to assign time + people.
    if incomplete:
        chips_html = []
        for _a in incomplete:
            _aid = escape(str(_a.get("id") or ""), quote=True)
            _nm = escape((_a.get("name") or "(untitled)")[:40])
            _cat = (_a.get("category") or "").strip() or "fixed"
            _col = _safe_color(_a.get("color") or "", _category_color(_cat))
            chips_html.append(
                f'<a href="#frol-act-{_aid}" class="frol-grid-chip frol-grid-incomplete-chip" '
                f'data-act-id="{_aid}" title="Needs time and people — click to edit" '
                f'style="display:inline-flex;align-items:center;gap:4px;'
                f'background:#f3f4f6;color:#4b5563;border:1px dashed #9ca3af;'
                f'border-left:3px solid {_col};border-radius:4px;'
                f'padding:3px 6px;margin:2px;font-size:10px;line-height:1.15;'
                f'text-decoration:none;font-weight:600;cursor:pointer;">'
                f'<span aria-hidden="true">&#9998;</span>'
                f'<span>{_nm}</span></a>'
            )
        unsched_cells = (
            f'<td class="frol-grid-time" '
            f'style="position:sticky;left:0;z-index:1;background:#f9fafb;'
            f'border:1px solid #d8e1ef;border-top:2px solid #c9d4e6;'
            f'padding:2px 6px;font-size:10px;color:#6b7280;'
            f'text-align:right;white-space:nowrap;'
            f'min-width:62px;font-style:italic;">Setup</td>'
            f'<td colspan="{max(1, len(visible))}" '
            f'class="frol-grid-cell frol-grid-unscheduled" '
            f'style="border:1px solid #eef1f6;border-top:2px solid #c9d4e6;'
            f'background:#f9fafb;padding:4px 6px;vertical-align:top;">'
            f'<div style="font-size:10px;color:#6b7280;font-weight:700;'
            f'margin-bottom:2px;">Needs time &amp; people:</div>'
            f'<div style="display:flex;flex-wrap:wrap;">'
            f'{"".join(chips_html)}</div></td>'
        )
        body.append("<tr>" + unsched_cells + "</tr>")
    for slot_idx, (hh, mm) in enumerate(GRID_SLOTS):
        is_hour = (mm == 0)
        label = _grid_time_label(hh, mm)
        row_bg = "#fafbfd" if is_hour else "#fff"
        time_border = "2px solid #c9d4e6" if is_hour else "1px solid #eef1f6"
        cells = [
            f'<td class="frol-grid-time" '
            f'style="position:sticky;left:0;z-index:1;background:{row_bg};'
            f'border:1px solid #d8e1ef;border-top:{time_border};'
            f'padding:2px 6px;font-size:10px;color:#6b7280;'
            f'text-align:right;white-space:nowrap;'
            f'min-width:62px;height:30px;">{escape(label)}</td>'
        ]
        for p in visible:
            if skip_until[p] > slot_idx:
                continue
            acts_here = placements[p].get(slot_idx) or []
            overlay_here = overlay_placements[p].get(slot_idx) or []
            overlay_chips = "".join(
                _grid_chip_html(_a, _sm, _dm, 1, is_overlay=True)
                for (_sm, _dm, _a) in overlay_here
            )
            if not acts_here:
                cells.append(
                    f'<td class="frol-grid-cell" '
                    f'style="border:1px solid #eef1f6;'
                    f'border-top:{time_border};background:{row_bg};'
                    f'height:30px;padding:0;">{overlay_chips}</td>'
                )
                continue
            # Rowspan = max slot-span among activities starting in this
            # cell. We cap to the grid bottom so we never overflow.
            max_span = 1
            for _sm, _dm, _a in acts_here:
                span = max(1, (max(0, _dm) + 29) // 30)
                span = min(span, len(GRID_SLOTS) - slot_idx)
                if span > max_span:
                    max_span = span
            skip_until[p] = slot_idx + max_span
            chips = "".join(
                _grid_chip_html(_a, _sm, _dm,
                                min(max(1, (max(0, _dm) + 29) // 30),
                                    len(GRID_SLOTS) - slot_idx))
                for (_sm, _dm, _a) in acts_here
            )
            rs = f' rowspan="{max_span}"' if max_span > 1 else ""
            cells.append(
                f'<td class="frol-grid-cell"{rs} '
                f'style="border:1px solid #eef1f6;'
                f'border-top:{time_border};background:#fff;'
                f'padding:1px;vertical-align:top;'
                f'height:{30 * max_span}px;">{chips}{overlay_chips}</td>'
            )
        body.append("<tr>" + "".join(cells) + "</tr>")
    tbody = "<tbody>" + "".join(body) + "</tbody>"
    return (
        '<table class="frol-grid-table" '
        'style="border-collapse:separate;border-spacing:0;'
        'table-layout:fixed;width:max-content;'
        'font-family:inherit;">'
        + thead + tbody + '</table>'
    )


def _seasonal_overlay_state():
    """Phase F: return (overlay_activities_or_None, source_label, source_id, on)
    by consulting app_settings.frol_overlay_source_id / frol_overlay_on
    and looking up the snapshot. Activities are stripped to dicts compatible
    with the grid; on=False when toggle is off but a source is configured."""
    try:
        import json as _json
        from config import APP_SETTINGS_FILE as _ASF
        if not os.path.exists(_ASF):
            return (None, "", "", False)
        with open(_ASF, encoding="utf-8") as _fh:
            _s = _json.load(_fh) or {}
        src_id = (_s.get("frol_overlay_source_id") or "").strip()
        on = bool(_s.get("frol_overlay_on"))
        if not src_id:
            return (None, "", "", False)
        from data_helpers import get_seasonal_schedule as _gss
        entry = _gss(src_id)
        if not entry:
            return (None, "", src_id, False)
        label = (
            f"{entry.get('season_label','')} {entry.get('year','')}"
        ).strip()
        return (entry.get("activities_snapshot") or [], label, src_id, on)
    except Exception:
        return (None, "", "", False)


def _render_grid_preview(section: int, progress: dict,
                         active_variant: str = "weekday",
                         activities=None) -> str:
    """Reusable grid preview component. Returns the full container with
    variant tabs, person pills, scrollbox, and table. Phase B builds it;
    Phase C will mount it at the bottom of every section page.

    Live updates: JS in static/js/frol_wizard.js listens for Phase A
    add/edit/delete responses and refetches /frol-grid-fragment for the
    inner table, so the grid never causes a full page reload."""
    sec_i = int(section)
    av = (active_variant or "weekday").strip() or "weekday"
    if activities is None:
        try:
            from data_helpers import load_frol_activities as _laa
            activities = _laa()
        except Exception:
            activities = []
    visible = _grid_visible_persons(sec_i, progress)
    # Variant tabs
    tabs = []
    for vkey, vlabel in ACTIVITY_VARIANTS:
        is_on = (vkey == av)
        bg = "#4a6fa5" if is_on else "#fff"
        fg = "#fff" if is_on else "#33507e"
        tabs.append(
            f'<button type="button" class="frol-grid-vtab" '
            f'data-variant="{escape(vkey, quote=True)}" '
            f'onclick="frolGridVariant(this)" '
            f'style="background:{bg};color:{fg};border:1px solid #4a6fa555;'
            f'border-radius:14px;padding:4px 10px;margin:2px;'
            f'font-size:0.82em;font-weight:700;cursor:pointer;'
            f'font-family:inherit;">{escape(vlabel)}</button>'
        )
    tab_bar = (
        '<div class="frol-grid-tabs" '
        'style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px;">'
        + "".join(tabs) + '</div>'
    )
    # Person pills
    pills = []
    for p in GRID_PERSONS:
        is_on = (p in visible)
        bg = "#4a6fa5" if is_on else "#fff"
        fg = "#fff" if is_on else "#33507e"
        pills.append(
            f'<button type="button" class="frol-grid-ppill" '
            f'data-person="{escape(p, quote=True)}" '
            f'data-on="{"1" if is_on else "0"}" '
            f'onclick="frolGridTogglePerson(this)" '
            f'style="background:{bg};color:{fg};border:1px solid #4a6fa555;'
            f'border-radius:12px;padding:3px 9px;margin:2px;'
            f'font-size:0.78em;font-weight:600;cursor:pointer;'
            f'font-family:inherit;">{escape(p)}</button>'
        )
    pill_bar = (
        '<div class="frol-grid-pills" '
        'style="display:flex;flex-wrap:wrap;gap:3px;margin-bottom:8px;">'
        '<span style="font-size:11px;color:#6b7280;align-self:center;'
        'margin-right:4px;">Show:</span>' + "".join(pills) + '</div>'
    )
    overlay_acts, overlay_label, overlay_id, overlay_on = _seasonal_overlay_state()
    overlay_for_grid = overlay_acts if (overlay_acts and overlay_on) else None
    table_html = _grid_build_table(sec_i, av, visible, activities,
                                   overlay_activities=overlay_for_grid)
    overlay_toggle = ""
    if overlay_acts:
        _olbl   = escape(overlay_label or "saved schedule")
        _btn_lbl = "Hide overlay" if overlay_on else "Show overlay"
        _btn_bg  = "#4a235a" if overlay_on else "#fff"
        _btn_fg  = "#fff" if overlay_on else "#4a235a"
        _clear_form = (
            '<form method="POST" action="/frol-overlay-clear" '
            'style="display:inline-block;margin:0 0 0 4px;">'
            '<button type="submit" style="background:transparent;border:none;'
            'color:#7d5a9a;text-decoration:underline;font-size:0.8em;'
            'cursor:pointer;padding:0;">clear</button>'
            '</form>'
        )
        overlay_toggle = (
            '<div class="frol-grid-overlay-bar" '
            'style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;'
            'background:#f3eef7;border:1px solid #d8c8e6;border-radius:8px;'
            'padding:6px 10px;margin-bottom:6px;font-size:0.85em;color:#4a235a;">'
            f'<span style="font-weight:700;">Year-over-year overlay:</span>'
            f'<span style="font-style:italic;">{_olbl}</span>'
            f'<form method="POST" action="/frol-overlay-toggle" '
            f'style="margin-left:auto;">'
            f'<button type="submit" style="background:{_btn_bg};color:{_btn_fg};'
            f'border:1px solid #4a235a55;border-radius:14px;padding:3px 12px;'
            f'font-weight:700;font-size:0.82em;cursor:pointer;">{_btn_lbl}</button>'
            f'</form>'
            f'{_clear_form}'
            '</div>'
        )
    # Status label for screen readers + manual debugging.
    status = (
        f'<div class="frol-grid-status" '
        f'style="font-size:11px;color:#9ca3af;margin-top:4px;">'
        f'Section {sec_i} · {escape(av)} · {len(visible)} person(s)'
        f'</div>'
    )
    scrollbox = (
        '<div class="frol-grid-scroll" '
        'style="overflow:auto;max-height:70vh;'
        'border:1px solid #d8e1ef;border-radius:8px;background:#fff;'
        '-webkit-overflow-scrolling:touch;">'
        + table_html + '</div>'
    )
    container = (
        f'<div class="frol-grid-preview" id="frol-grid-container" '
        f'data-section="{sec_i}" '
        f'data-active-variant="{escape(av, quote=True)}" '
        f'style="background:#f6f8fc;border:1px solid #d8e1ef;'
        f'border-radius:10px;padding:10px 12px;margin:14px 0;">'
        f'<div style="font-weight:700;color:#33507e;font-size:0.95em;'
        f'margin-bottom:6px;">Live grid preview</div>'
        f'{overlay_toggle}{tab_bar}{pill_bar}{scrollbox}{status}'
        f'</div>'
    )
    return container


def _render_grid_preview_fragment(section: int, progress: dict,
                                  active_variant: str = "weekday",
                                  activities=None) -> str:
    """Return only the inner table HTML for the grid — used by the
    /frol-grid-fragment GET so the JS can swap innerHTML on the scrollbox
    without rebuilding the tabs/pills chrome."""
    sec_i = int(section)
    av = (active_variant or "weekday").strip() or "weekday"
    if activities is None:
        try:
            from data_helpers import load_frol_activities as _laa
            activities = _laa()
        except Exception:
            activities = []
    visible = _grid_visible_persons(sec_i, progress)
    overlay_acts, _olbl, _oid, overlay_on = _seasonal_overlay_state()
    overlay_for_grid = overlay_acts if (overlay_acts and overlay_on) else None
    return _grid_build_table(sec_i, av, visible, activities,
                             overlay_activities=overlay_for_grid)


def _render_activity_builder(section: int, progress: dict,
                             existing_activities: list,
                             active_variant: str,
                             mode: str = "") -> str:
    """The 4-step add-activity form. Self-contained <form> posting to
    /frol-add-activity. JS in static/js/frol_wizard.js handles progressive
    reveal of Steps B/C/D. Phase A: builder + list display only — section
    pages will mount this in Phase C."""
    try:
        sec_int = int(section)
    except (TypeError, ValueError):
        sec_int = 0
    av = (active_variant or "weekday").strip() or "weekday"
    persons = _activity_persons(progress)
    mode_esc = escape(mode, quote=True)
    sec_esc = str(sec_int)
    # ── Step A: name ─────────────────────────────────────────────────────
    step_a = f"""
    <div class="frol-ab-step" data-ab-step="A">
      <div style="font-weight:600;font-size:12px;color:#6b7280;
                  text-transform:uppercase;letter-spacing:.5px;">Step A — Name</div>
      <input type="text" name="name" required maxlength="80"
             placeholder="What is this activity called?"
             class="frol-input"
             oninput="frolActivityStepReveal(this.form);"
             style="width:100%;margin-top:4px;padding:8px;border:1px solid #d1d5db;
                    border-radius:6px;">
    </div>
    """
    # ── Step B: who_type ─────────────────────────────────────────────────
    step_b = f"""
    <div class="frol-ab-step" data-ab-step="B" style="margin-top:14px;display:none;">
      <div style="font-weight:600;font-size:12px;color:#6b7280;
                  text-transform:uppercase;letter-spacing:.5px;">Step B — Who is this for?</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:6px;">
        <label class="frol-ab-radio">
          <input type="radio" name="who_type" value="family" required
                 onchange="frolActivityWhoType(this.form,'family');"> Whole family
        </label>
        <label class="frol-ab-radio">
          <input type="radio" name="who_type" value="individual"
                 onchange="frolActivityWhoType(this.form,'individual');"> Individual
        </label>
        <label class="frol-ab-radio">
          <input type="radio" name="who_type" value="mixed"
                 onchange="frolActivityWhoType(this.form,'mixed');"> Mixed (some people)
        </label>
      </div>
    </div>
    """
    # ── Step C: per-who_type branches ────────────────────────────────────
    person_options = "".join(
        f'<option value="{escape(n, quote=True)}">{escape(n)}</option>'
        for n in persons
    )
    person_checkboxes = "".join(
        f"""<label class="frol-ab-person" style="display:inline-flex;align-items:center;
                  gap:4px;padding:4px 8px;border:1px solid #d1d5db;border-radius:6px;
                  margin:2px;font-size:12px;cursor:pointer;">
              <input type="checkbox" name="who" value="{escape(n, quote=True)}"
                     onchange="frolActivityPeopleChange(this.form);"> {escape(n)}
            </label>"""
        for n in persons
    )
    # Family branch: single time + duration + optional leader.
    family_branch = f"""
      <div class="frol-ab-branch" data-branch="family" style="display:none;">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:6px;">
          <div>
            <label style="font-size:11px;color:#6b7280;">Time</label>
            <input type="time" name="time" class="frol-input"
                   style="width:100%;padding:6px;border:1px solid #d1d5db;border-radius:6px;">
          </div>
          <div>
            <label style="font-size:11px;color:#6b7280;">Duration (min)</label>
            <input type="number" name="duration_min" min="0" max="600" value="30"
                   class="frol-input"
                   style="width:100%;padding:6px;border:1px solid #d1d5db;border-radius:6px;">
          </div>
          <div>
            <label style="font-size:11px;color:#6b7280;">Leader (optional)</label>
            <select name="leader" class="frol-input"
                    style="width:100%;padding:6px;border:1px solid #d1d5db;border-radius:6px;">
              <option value="">— none —</option>
              {person_options}
            </select>
          </div>
        </div>
      </div>
    """
    # Individual branch: single-person select + their time + duration.
    individual_branch = f"""
      <div class="frol-ab-branch" data-branch="individual" style="display:none;">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:6px;">
          <div>
            <label style="font-size:11px;color:#6b7280;">Person</label>
            <select name="who_single" class="frol-input"
                    onchange="frolActivitySinglePerson(this.form, this.value);"
                    style="width:100%;padding:6px;border:1px solid #d1d5db;border-radius:6px;">
              <option value="">— choose —</option>
              {person_options}
            </select>
          </div>
          <div>
            <label style="font-size:11px;color:#6b7280;">Time</label>
            <input type="time" name="single_time" class="frol-input"
                   style="width:100%;padding:6px;border:1px solid #d1d5db;border-radius:6px;">
          </div>
          <div>
            <label style="font-size:11px;color:#6b7280;">Duration (min)</label>
            <input type="number" name="single_duration_min" min="0" max="600" value="30"
                   class="frol-input"
                   style="width:100%;padding:6px;border:1px solid #d1d5db;border-radius:6px;">
          </div>
        </div>
      </div>
    """
    # Mixed branch: checkboxes + per-person time/duration (JS-generated).
    mixed_branch = f"""
      <div class="frol-ab-branch" data-branch="mixed" style="display:none;">
        <div style="font-size:11px;color:#6b7280;margin-top:6px;">Pick the people involved:</div>
        <div style="display:flex;flex-wrap:wrap;margin-top:4px;">
          {person_checkboxes}
        </div>
        <div data-mixed-rows style="margin-top:8px;"></div>
      </div>
    """
    step_c = f"""
    <div class="frol-ab-step" data-ab-step="C" style="margin-top:14px;display:none;">
      <div style="font-weight:600;font-size:12px;color:#6b7280;
                  text-transform:uppercase;letter-spacing:.5px;">Step C — When &amp; how long</div>
      {family_branch}
      {individual_branch}
      {mixed_branch}
    </div>
    """
    # ── Step D: days + variants + category + seasonal + credits ──────────
    day_chips = "".join(
        f"""<label style="display:inline-flex;align-items:center;gap:4px;padding:4px 8px;
                  border:1px solid #d1d5db;border-radius:6px;margin:2px;font-size:11px;
                  cursor:pointer;">
              <input type="checkbox" name="days" value="{d}"
                {' checked' if d in ('Monday','Tuesday','Wednesday','Thursday','Friday') else ''}>
              {d[:3]}
            </label>"""
        for d in WEEKDAYS
    )
    # Spec: builder always defaults to weekday-only, regardless of what
    # variant the user is currently viewing. They can opt into more.
    variant_chips = "".join(
        f"""<label style="display:inline-flex;align-items:center;gap:4px;padding:4px 8px;
                  border:1px solid #d1d5db;border-radius:6px;margin:2px;font-size:11px;
                  cursor:pointer;">
              <input type="checkbox" name="schedule_variant" value="{vk}"
                {' checked' if vk == 'weekday' else ''}>
              {escape(vl)}
            </label>"""
        for vk, vl in ACTIVITY_VARIANTS
    )
    cat_options = "".join(
        f'<option value="{key}">{escape(label)}</option>'
        for key, label, _c in ACTIVITY_CATEGORIES
    )
    step_d = f"""
    <div class="frol-ab-step" data-ab-step="D" style="margin-top:14px;display:none;">
      <div style="font-weight:600;font-size:12px;color:#6b7280;
                  text-transform:uppercase;letter-spacing:.5px;">Step D — Days &amp; details</div>
      <div style="margin-top:6px;">
        <div style="font-size:11px;color:#6b7280;">Days of week:</div>
        <div style="display:flex;flex-wrap:wrap;">{day_chips}</div>
      </div>
      <div style="margin-top:8px;">
        <div style="font-size:11px;color:#6b7280;">Schedule variants:</div>
        <div style="display:flex;flex-wrap:wrap;">{variant_chips}</div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:8px;">
        <div>
          <label style="font-size:11px;color:#6b7280;">Category</label>
          <select name="category" class="frol-input"
                  style="width:100%;padding:6px;border:1px solid #d1d5db;border-radius:6px;">
            {cat_options}
          </select>
        </div>
        <div>
          <label style="font-size:11px;color:#6b7280;">Seasonal</label>
          <select name="seasonal" class="frol-input"
                  style="width:100%;padding:6px;border:1px solid #d1d5db;border-radius:6px;">
            <option value="year_round">Year-round</option>
            <option value="school_year">School year only</option>
            <option value="summer">Summer only</option>
          </select>
        </div>
        <div>
          <label style="font-size:11px;color:#6b7280;">Credits (FQ, comma-separated)</label>
          <input type="text" name="credits" placeholder="e.g. xp:10,gold:2"
                 class="frol-input"
                 style="width:100%;padding:6px;border:1px solid #d1d5db;border-radius:6px;">
        </div>
      </div>
      <label style="display:inline-flex;align-items:center;gap:6px;margin-top:8px;font-size:12px;">
        <input type="checkbox" name="is_grooming" value="1"> Counts as grooming
      </label>
    </div>
    """
    # ── Submit row ───────────────────────────────────────────────────────
    submit_row = f"""
    <div style="margin-top:14px;display:flex;justify-content:flex-end;gap:8px;">
      <button type="submit" class="frol-btn">Add activity</button>
    </div>
    """
    # ── Existing activity cards above the builder ────────────────────────
    list_html = _render_activity_list(sec_int, progress, existing_activities, av, mode)
    return f"""
    <div class="frol-activity-builder" data-section="{sec_esc}" data-variant="{escape(av, quote=True)}">
      <div class="frol-activity-list" style="margin-bottom:14px;">
        <div style="font-weight:600;font-size:13px;color:#374151;margin-bottom:4px;">
          Activities in this section (variant: {escape(av)})
        </div>
        {list_html}
      </div>
      <form method="POST" action="/frol-add-activity" class="frol-ab-form"
            style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:12px;">
        <input type="hidden" name="section" value="{sec_esc}">
        <input type="hidden" name="mode" value="{mode_esc}">
        <input type="hidden" name="active_variant" value="{escape(av, quote=True)}">
        <div style="font-weight:600;font-size:14px;color:#1f2937;margin-bottom:6px;">
          Add a new activity
        </div>
        {step_a}
        {step_b}
        {step_c}
        {step_d}
        {submit_row}
      </form>
    </div>
    """


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
            "<p>Later (in §6 School and §12 Build Your Day) we'll suggest "
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
        "Each child's rhythms here will inform §12 Build Your Day.</p>",
        key="sec2_intro",
    )
    body = f"""
      {info_card}
      {rows}
      <p class="frol-help" style="margin-top:12px;">
        These rhythms anchor §12 Build Your Day — quiet hours auto-block during
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
    john_wake     = _sv(progress, 3, "john_wake_time",       "06:00")
    john_bed      = _sv(progress, 3, "john_bedtime",         "22:30")
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

      <label class="frol-fld" style="margin-top:18px;">John's personal rhythm</label>
      <p class="frol-help">John's own wake and sleep times — separate from
        the family adult anchors above. Auto-saves as you type.</p>
      <div class="frol-row">
        <div><label class="frol-fld">John's typical wake time</label>
          <input class="frol-input" type="time" data-step="3" data-key="john_wake_time"
                 value="{escape(john_wake, quote=True)}"></div>
        <div><label class="frol-fld">John's typical bedtime</label>
          <input class="frol-input" type="time" data-step="3" data-key="john_bedtime"
                 value="{escape(john_bed, quote=True)}"></div>
      </div>

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
        "feed §12 Build Your Day.</p>",
        key="sec6_pairing",
        open_first_visit=False,
    )
    dev_card = render_reflection_card(
        "Developmental check",
        "<p>Quick sanity check before §12: is each child's school load matched "
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
                     items: list, placeholder: str = "",
                     sec7: dict | None = None) -> str:
    """One textarea representing a single chore list. data-key is
    'chores__{person}__{bucket}__{sub_key}' and the save handler will split
    on newlines at finalize time. When sec7 is provided and contains the
    flat key (autosaved user edits), that value wins over the chores.json
    seed — otherwise the seed list is shown."""
    key = f"chores__{person}__{bucket_key}__{sub_key}"
    saved = sec7.get(key) if isinstance(sec7, dict) else None
    if saved is not None:
        val = str(saved)
    else:
        val = "\n".join(_chore_item_text(it) for it in (items or []) if _chore_item_text(it).strip())
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
            "One chore per line. Examples: Make bed, Daily Room Reset, Practice piano 15 min",
            sec7=sec7)

    # Weekly bucket — collapsible per person, with one textarea per weekday
    weekly_html = ""
    for nm in persons:
        wk = ((chores.get(nm) or {}).get("weekly") or {})
        if not isinstance(wk, dict): wk = {}
        sub = ""
        for day in _WEEKDAYS:
            items = wk.get(day) or []
            sub += _bucket_textarea(nm, "weekly", day, items, f"{day} chores, one per line", sec7=sec7)
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
            sub += _bucket_textarea(nm, "monthly", w, items, f"{w.replace('_',' ').title()} of the month", sec7=sec7)
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
            sub += _bucket_textarea(nm, "seasonal", season, items, f"{season.title()} chores", sec7=sec7)
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
            sub += _bucket_textarea(nm, "annual", month, items, f"{month.title()} chores", sec7=sec7)
        annual_html += f"""
          <details style="background:#f6f8fc;border:1px solid #d8e1ef;border-radius:8px;
                          padding:8px 12px;margin:8px 0;">
            <summary style="cursor:pointer;font-weight:700;color:#33507e;">{escape(nm)} — annual</summary>
            <div style="padding-top:8px;">{sub}</div>
          </details>
        """

    # Grooming — per-person textarea (one per line); merged into is_grooming
    # flags at §14 finalize-save.
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
    sec10        = (progress.get("data", {}) or {}).get("section_10", {}) or {}
    if not isinstance(sec10, dict):
        sec10 = {}
    buffer_min   = _sv(progress, 10, "transition_buffer_min", "10")
    flex_blocks  = _sv(progress, 10, "flex_blocks",           "")
    weekly_reset = _sv(progress, 10, "weekly_reset",          "")
    seasonal     = _sv(progress, 10, "seasonal_flags",        []) or []
    john_travel  = _sv(progress, 10, "john_travel_notes",     "")

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
        cur = sec10.get(f"energy__{tod}") or ""
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
      <p class="frol-help">§12 Build Your Day will insert a gray buffer slot of
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

      <label class="frol-fld" style="margin-top:14px;">When John is traveling for work</label>
      <p class="frol-help">Lauren is solo-parenting on these days — note what
        shifts (earlier kid bedtime? simpler dinner? skipped couple time?
        Lauren's own evening routine). This feeds the John-Traveling variant
        of §13 Build Your Day.</p>
      <textarea class="frol-textarea" data-step="10" data-key="john_travel_notes"
                placeholder="Kids go down 30 min earlier. Dinner is sandwiches. Lauren takes 20 min of quiet reading after bedtime instead of couple time.">{escape(john_travel)}</textarea>

      <label class="frol-fld" style="margin-top:14px;">Seasonal flags</label>
      <p class="frol-help">Check anything that genuinely changes the rhythm in
        that season — the AI will offer to re-evaluate your rule then.</p>
      {_cb("seasonal_flags", ["Advent slow-down", "Christmas / Octave", "Lenten fast", "Easter Octave", "Summer / no school", "Back-to-school", "Holy Week", "Liturgical New Year (Nov)"], seasonal)}
    """
    return _section_chrome(10, "Flex, Buffers &amp; Seasonal",
        "The breathing room that keeps the rule alive — and the seasons that re-shape it.",
        body, mode, progress, lucy_visible=True)


# ── Phase C §11: Holiday & Feast Day ────────────────────────────────────────
# A short, checkbox-driven page. Each checked feast/holiday surfaces a
# small per-item "what changes" selector + free-text note. At the bottom
# two general rules cover all Marian feasts and major solemnities.
# Persisted under progress.data.section_11 via the standard /frol-save-field
# pipeline (data-step="11", data-key="…").

CATHOLIC_FEASTS = [
    ("all_saints",      "All Saints' Day (Nov 1)"),
    ("immaculate",      "Immaculate Conception (Dec 8)"),
    ("christmas",       "Christmas (Dec 25)"),
    ("epiphany",        "Epiphany"),
    ("ash_wednesday",   "Ash Wednesday"),
    ("holy_thursday",   "Holy Thursday"),
    ("good_friday",     "Good Friday"),
    ("easter",          "Easter Sunday"),
    ("easter_monday",   "Easter Monday"),
    ("ascension",       "Ascension"),
    ("pentecost",       "Pentecost"),
    ("assumption",      "Assumption (Aug 15)"),
    ("our_lady_guadalupe", "Our Lady of Guadalupe (Dec 12)"),
]

US_HOLIDAYS = [
    ("new_years",       "New Year's Day"),
    ("mlk",             "Martin Luther King Jr. Day"),
    ("presidents",      "Presidents' Day"),
    ("memorial",        "Memorial Day"),
    ("juneteenth",      "Juneteenth"),
    ("independence",    "Independence Day (Jul 4)"),
    ("labor",           "Labor Day"),
    ("columbus",        "Columbus Day"),
    ("veterans",        "Veterans Day"),
    ("thanksgiving",    "Thanksgiving"),
    ("day_after_thx",   "Day after Thanksgiving"),
]

SCHEDULE_MODES = [
    ("normal",     "Normal day"),
    ("lighter",    "Lighter schedule"),
    ("school_off", "School off"),
    ("rest_day",   "Full rest day"),
]


def _holiday_card(slug: str, label: str, saved: dict) -> str:
    """Per-holiday card. Spec calls for THREE inputs once the holiday is
    observed: school off Y/N, special schedule Y/N, and a free-text
    note. We persist via the existing list/idx/key autosave pipeline so
    every field lands under section_11.holidays[slug].{observe,
    school_off, special_schedule, note}. Using data-key (not data-field)
    is critical — the binder in static/js/frol_wizard.js only picks up
    [data-step][data-key] elements."""
    cur = saved.get(slug) or {}
    checked_obs = " checked" if cur.get("observe") in (True, "yes", "1", 1) else ""
    checked_so  = " checked" if cur.get("school_off") in (True, "yes", "1", 1) else ""
    checked_ss  = " checked" if cur.get("special_schedule") in (True, "yes", "1", 1) else ""
    note_val = escape(cur.get("note") or "", quote=True)
    slug_esc = escape(slug, quote=True)
    return f"""
      <label style="display:flex;align-items:flex-start;gap:8px;
                    padding:8px;border:1px solid #d8e1ef;border-radius:8px;
                    background:#fff;margin:4px 0;">
        <input type="checkbox" data-step="11"
               data-list="holidays" data-idx="{slug_esc}" data-key="observe"
               value="1"{checked_obs}
               onchange="frolHolidayToggle(this);"
               style="margin-top:4px;">
        <div style="flex:1;">
          <div style="font-weight:600;color:#33507e;">{escape(label)}</div>
          <div class="frol-holiday-detail"
               data-slug="{slug_esc}"
               style="margin-top:6px;{'display:none;' if not checked_obs else ''}">
            <div style="display:flex;flex-wrap:wrap;gap:14px;
                        align-items:center;font-size:0.86em;color:#33507e;">
              <label style="display:flex;align-items:center;gap:5px;">
                <input type="checkbox" data-step="11"
                       data-list="holidays" data-idx="{slug_esc}"
                       data-key="school_off"
                       value="1"{checked_so}> School off
              </label>
              <label style="display:flex;align-items:center;gap:5px;">
                <input type="checkbox" data-step="11"
                       data-list="holidays" data-idx="{slug_esc}"
                       data-key="special_schedule"
                       value="1"{checked_ss}> Special schedule
              </label>
            </div>
            <input class="frol-input" type="text" data-step="11"
                   data-list="holidays" data-idx="{slug_esc}" data-key="note"
                   value="{note_val}"
                   placeholder="Notes (e.g. attend morning Mass, dinner with cousins)"
                   style="width:100%;margin-top:6px;font-size:0.86em;
                          padding:4px 8px;">
          </div>
        </div>
      </label>
    """


_RULE_MODES = [
    ("normal",     "Normal day"),
    ("lighter",    "Lighter day"),
    ("school_off", "School off"),
]


def _rule_card(label: str, sub: str, key: str, saved: dict) -> str:
    """General-rule card (Marian feasts, major solemnities). Per spec,
    one single 3-state selector: normal / lighter / school_off. Persists
    DIRECTLY under section_11.{key} as a flat string (not nested under
    a list), e.g. section_11.marian_rule = "lighter". Uses data-key
    (not data-field) so the autosave binder picks it up."""
    cur_mode = saved if isinstance(saved, str) else ""
    if not cur_mode or cur_mode not in {m for m, _ in _RULE_MODES}:
        cur_mode = "normal"
    opts = "".join(
        f'<option value="{m}"{" selected" if m == cur_mode else ""}>'
        f'{escape(l)}</option>'
        for m, l in _RULE_MODES
    )
    key_esc = escape(key, quote=True)
    return f"""
      <div style="border:1px solid #d8e1ef;border-radius:8px;
                  background:#fff;padding:10px 12px;margin:6px 0;">
        <div style="font-weight:600;color:#33507e;">{escape(label)}</div>
        <div style="font-size:0.82em;color:#888;margin-bottom:6px;">{escape(sub)}</div>
        <label style="display:flex;align-items:center;gap:8px;
                      font-size:0.86em;color:#33507e;">
          What happens?
          <select class="frol-input" data-step="11"
                  data-key="{key_esc}"
                  style="font-size:0.86em;padding:3px 8px;">
            {opts}
          </select>
        </label>
      </div>
    """


def render_section_11_holidays(progress: dict, mode: str) -> str:
    """New v3 §11 — Holidays & Feast Days. Two checkbox grids (Catholic
    feasts + US civic holidays) with per-item what-changes selectors,
    plus two general rules at the bottom. All inputs persist via the
    standard data-step/data-key save pipeline."""
    sec = (progress.get("data", {}) or {}).get("section_11", {}) or {}
    holidays = sec.get("holidays") or {}

    refl = render_reflection_card(
        "When the calendar pulls the day off its rails",
        "<p>The liturgical year and US holidays will reshape your weekly "
        "rhythm dozens of times. Telling the wizard which ones you observe "
        "— and what changes when they hit — lets §13 Build Your Day "
        "produce a schedule that already knows when to relax, when to add "
        "a morning Mass, and when to stand the school day down.</p>",
        key="sec11_intro",
    )
    feast_cards = "".join(
        _holiday_card(slug, label, holidays) for slug, label in CATHOLIC_FEASTS
    )
    us_cards = "".join(
        _holiday_card(slug, label, holidays) for slug, label in US_HOLIDAYS
    )
    marian = _rule_card(
        "All other Marian feasts",
        "What's the family's default on Marian feast days not listed above?",
        "marian_rule", sec.get("marian_rule") or "",
    )
    sol = _rule_card(
        "All other major solemnities",
        "What's the default for any solemnity (e.g. St. Joseph, Sts. Peter & Paul)?",
        "solemnity_rule", sec.get("solemnity_rule") or "",
    )

    holiday_script = """
      <script>
      (function(){
        if (window.__frolHolidayReady) return;
        window.__frolHolidayReady = true;
        window.frolHolidayToggle = function(cb) {
          var slug = cb.getAttribute('data-idx');
          if (!slug) return;
          var detail = cb.parentElement.querySelector(
            '.frol-holiday-detail[data-slug="' + slug + '"]'
          );
          if (detail) {
            detail.style.display = cb.checked ? '' : 'none';
          }
        };
      })();
      </script>
    """
    body = f"""
      {refl}
      <h3 style="color:#33507e;margin-top:14px;">Catholic feast days</h3>
      <div>{feast_cards}</div>
      <h3 style="color:#33507e;margin-top:18px;">US holidays</h3>
      <div>{us_cards}</div>
      <h3 style="color:#33507e;margin-top:18px;">General rules</h3>
      {marian}
      {sol}
      {holiday_script}
    """
    return _section_chrome(11, "Holidays &amp; Feast Days",
        "Catholic feasts and US holidays — what changes when each one lands.",
        body, mode, progress, lucy_visible=True)


# ── Phase C variant tab bar + per-section grid mount ────────────────────────

def _active_variant(progress: dict) -> str:
    av = ((progress.get("data") or {}).get("active_variant") or "weekday")
    return str(av).strip() or "weekday"


def _render_variant_tab_bar(section: int, progress: dict, mode: str) -> str:
    """Sticky tab bar that lets the user flip between weekday/Sat/Sun/
    travel variants. Selection is persisted to progress.data.active_variant
    via /frol-set-variant so it survives navigation between sections."""
    av = _active_variant(progress)
    sec_esc = str(int(section))
    mode_esc = escape(mode, quote=True)
    tabs = ""
    for vk, vl in ACTIVITY_VARIANTS:
        is_sel = (vk == av)
        bg = "#4a6fa5" if is_sel else "#fff"
        fg = "#fff" if is_sel else "#33507e"
        tabs += (
            f'<button type="button" '
            f'onclick="frolSetVariant(\'{escape(vk, quote=True)}\','
            f'{sec_esc},\'{mode_esc}\')" '
            f'style="background:{bg};color:{fg};border:1px solid #4a6fa555;'
            f'border-radius:14px;padding:4px 12px;margin:2px;font-size:0.85em;'
            f'font-weight:700;cursor:pointer;font-family:inherit;">'
            f'{escape(vl)}</button>'
        )
    return (
        '<div class="frol-variant-tabs" style="position:sticky;top:0;z-index:5;'
        'background:#f6f8fc;border:1px solid #d8e1ef;border-radius:8px;'
        'padding:6px 8px;margin:8px 0;display:flex;flex-wrap:wrap;'
        'align-items:center;gap:2px;">'
        '<span style="font-size:0.78em;color:#666;margin-right:6px;">Variant:</span>'
        f'{tabs}</div>'
    )


def _render_phase_c_block(section: int, progress: dict, mode: str) -> str:
    """Mounted by _section_chrome for §2-§10: variant tab bar, activity
    builder, activity list, and grid preview. Self-contained — needs no
    external state beyond the progress dict."""
    try:
        from data_helpers import load_frol_activities as _laa
        activities = _laa()
    except Exception:
        activities = []
    av = _active_variant(progress)
    tabs = _render_variant_tab_bar(section, progress, mode)
    builder = _render_activity_builder(section, progress, activities, av, mode)
    grid = _render_grid_preview(section, progress, av, activities)
    return f"""
      <div class="frol-phase-c-mount" style="margin-top:16px;">
        {tabs}
        <details open style="background:#f9fafb;border:1px solid #e5e7eb;
                             border-radius:8px;padding:10px;margin-top:8px;">
          <summary style="cursor:pointer;font-weight:700;color:#33507e;">
            Activities &amp; preview
          </summary>
          <div style="margin-top:10px;">{builder}</div>
          <div style="margin-top:14px;">{grid}</div>
        </details>
      </div>
    """


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


# ── §11 duration picker ────────────────────────────────────────────────────

_DURATION_CHOICES = [5, 10, 15, 20, 30, 45, 60, 90, 120]


def _slugify_activity(s: str) -> str:
    out = []
    prev_dash = False
    for ch in str(s).lower().strip():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("_")
            prev_dash = True
    return "".join(out).strip("_") or "item"


def _collect_duration_targets(progress: dict) -> list:
    """Walk §§2-10 progress data and produce a list of activity targets
    grouped by section. Each entry: {group, slug, label, default}. Catholic
    anchor activities (Morning Offering, Rosary, Sunday Mass) are always
    included even if no specific section enabled them."""
    data = progress.get("data", {}) or {}
    if not isinstance(data, dict):
        data = {}

    def _sect(n: int) -> dict:
        # Prefer V2 keys; fall back to V1 step_N if V2 section is absent.
        v2 = data.get(f"section_{n}") or {}
        v1 = data.get(f"step_{n}") or {}
        if isinstance(v2, dict) and v2:
            return v2
        return v1 if isinstance(v1, dict) else {}

    seen = set()
    out = []

    def _add(group: str, label: str, default: int):
        label = (label or "").strip()
        if not label:
            return
        slug = _slugify_activity(label)
        if slug in seen:
            return
        seen.add(slug)
        out.append({"group": group, "slug": slug, "label": label, "default": int(default)})

    # Always-on Catholic anchors
    _add("Prayer", "Morning Offering", 5)
    _add("Prayer", "Rosary", 20)
    _add("Prayer", "Sunday Mass", 60)

    # §3 Prayer
    s3 = _sect(3)
    if s3:
        mp = (s3.get("morning_prayer") or "").strip()
        if mp:
            _add("Prayer", mp if mp.lower() not in ("lauds", "laudes")
                 else "Lauds (Morning Prayer)", 15)
        for it in (s3.get("morning_prayers_multi") or []):
            _add("Prayer", str(it), 15)
        for it in (s3.get("evening_prayers_multi") or []):
            _add("Prayer", str(it), 15)
        for it in (s3.get("night_prayers_multi") or []):
            _add("Prayer", str(it), 10)
        if (s3.get("angelus_times") or []):
            _add("Prayer", "Angelus", 3)
        if (s3.get("divine_mercy_3pm") or "").lower() == "yes":
            _add("Prayer", "Divine Mercy Chaplet", 10)
        if (s3.get("vespers") or "").lower() == "yes":
            _add("Prayer", "Vespers", 15)
        if (s3.get("examen") or "").lower() == "yes":
            _add("Prayer", "Examen", 10)
        if (s3.get("other_devotions") or "").strip():
            _add("Prayer", "Other devotions", 15)

    # §5 Meals — try V2 section_5 first, then V1 step_4 (where meals lived).
    s5 = data.get("section_5") or data.get("step_4") or {}
    if not isinstance(s5, dict):
        s5 = {}
    _add("Meals", "Breakfast", 30)
    _add("Meals", "Lunch", 30)
    _add("Meals", "Dinner", 45)
    _add("Meals", "Snack", 10)
    if (s5.get("morning_dinner_prep") or "").lower() == "yes":
        _add("Meals", "Morning dinner prep", 20)
    if (s5.get("meal_prep_who") or []):
        _add("Meals", "Meal prep", 30)
    if (s5.get("batch_cook_days") or []):
        _add("Meals", "Batch cook session", 120)

    # §6 School — V2 section_6, V1 step_5.
    s6 = data.get("section_6") or data.get("step_5") or {}
    if not isinstance(s6, dict):
        s6 = {}
    subj_defaults = {
        "math": 45, "religion": 20, "reading": 30, "writing": 30,
        "science": 30, "history": 30, "latin": 30, "art": 30,
        "music": 20, "pe": 30, "geography": 30, "logic": 30,
        "spelling": 15, "grammar": 20, "handwriting": 15,
    }
    for subj in (s6.get("subjects_multi") or []):
        nm = str(subj).strip()
        if nm:
            _add("School", nm, subj_defaults.get(nm.lower(), 30))
    _add("School", "Read-aloud", 30)

    # §7 Chores
    s7 = _sect(7)
    blocks = s7.get("chore_time_blocks") or []
    if blocks:
        for blk in blocks:
            nm = str(blk).strip()
            if nm:
                _add("Chores", f"Chores — {nm}", 20)
    else:
        _add("Chores", "Daily chores", 20)

    # §8 Health — V2 section_8, V1 step_6.
    s8 = data.get("section_8") or data.get("step_6") or {}
    if not isinstance(s8, dict):
        s8 = {}
    for t in (s8.get("types") or []):
        nm = str(t).strip()
        if nm:
            _add("Health", f"Exercise — {nm}", 30)

    # §9 Rest — V2 section_9, V1 step_7.
    s9 = data.get("section_9") or data.get("step_7") or {}
    if not isinstance(s9, dict):
        s9 = {}
    if (s9.get("afternoon_rest") or "").strip():
        _add("Rest", "Afternoon rest", 60)
    if (s9.get("date_night") or "").strip():
        _add("Rest", "Date night", 90)
    for trad in (s9.get("traditions") or []):
        nm = str(trad).strip()
        if nm:
            _add("Rest", nm, 60)

    # §10 Flex
    s10 = _sect(10)
    if (s10.get("weekly_reset") or "").strip():
        _add("Flex", "Weekly reset", 30)
    flex_text = (s10.get("flex_blocks") or "").strip()
    if flex_text:
        for ln in flex_text.splitlines():
            ln = ln.strip()
            if ln:
                _add("Flex", ln[:60], 60)

    return out


def render_section_11(progress: dict, mode: str) -> str:
    """V2 §11 — How Long Does Each Activity Take? One card per activity
    collected across §§2-10, with a duration picker (5/10/15/20/30/45/
    60/90/120 min + custom free text). Pre-filled with Catholic-homeschool
    defaults. Saves immediately via the existing saveField pipeline using
    data-step='11' and data-key='durations__{slug}' / 'custom__{slug}'."""
    sec11 = (progress.get("data", {}) or {}).get("section_12", {}) or {}
    targets = _collect_duration_targets(progress)
    active_variant = _active_variant(progress)
    variant_tabs = _render_variant_tab_bar(12, progress, mode)

    # Group by section first, then by variant. Today every collected
    # target applies across all variants (per-variant durations are
    # Phase D), so within each section group we display one card per
    # activity and persist the duration under a variant-aware key
    # `durations__{variant}__{slug}` — falling back to the legacy
    # `durations__{slug}` key for read so existing data isn't orphaned.
    groups = {}
    order = []
    for t in targets:
        g = t["group"]
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(t)

    # Pre-count missing-duration items (no user-saved value at all) so we
    # can surface the count at the top of the page and red-flag the
    # individual cards below.
    def _saved_for(slug: str):
        v = sec11.get(f"durations__{active_variant}__{slug}")
        if v in (None, ""):
            v = sec11.get(f"durations__{slug}")
        return v
    _missing_count = sum(
        1 for t in targets if _saved_for(t["slug"]) in (None, "")
    )

    refl = render_reflection_card(
        "Be honest about minutes",
        "<p>Schedules collapse when activities take longer than we pretend. "
        "For each thing you've named so far, pick a realistic duration — "
        "the time it actually takes on a normal day, not the time you wish "
        "it took. You can always tune these later as you live the rule.</p>"
        "<p style='margin-top:8px;'>Defaults are pre-filled with common "
        "Catholic-homeschool times. Tap a chip to change it, or type a "
        "custom value if your family's pace is different. Cards outlined "
        "in red still need a confirmed duration — defaults are shown but "
        "not yet saved.</p>",
        key="sec11_intro",
    )
    _missing_banner = ""
    if _missing_count:
        _missing_banner = (
            f'<div style="background:#fff4f4;border:1px solid #f5c2c2;'
            f'border-left:4px solid #c0392b;border-radius:8px;'
            f'padding:8px 12px;margin:8px 0;color:#7a1f1f;'
            f'font-weight:600;font-size:0.92em;">'
            f'{_missing_count} activit'
            f'{"y" if _missing_count == 1 else "ies"} still need '
            f'a confirmed duration on this variant.'
            f'</div>'
        )

    if not targets:
        body = (refl + variant_tabs +
                '<div class="frol-pop-note">No activities collected '
                'yet from §§2-10. Fill in earlier sections, then come back '
                'here to set durations.</div>')
        return _section_chrome(12, "How Long Does Each Activity Take?",
            "One card per activity. Pick a realistic duration.",
            body, mode, progress, lucy_visible=True)

    cards_html = ""
    for g in order:
        rows = ""
        for t in groups[g]:
            slug    = t["slug"]
            label   = t["label"]
            default = t["default"]
            saved   = _saved_for(slug)
            is_missing = saved in (None, "")
            current = str(saved) if not is_missing else str(default)
            custom  = str(sec11.get(f"custom__{active_variant}__{slug}")
                          or sec11.get(f"custom__{slug}") or "")
            # Variant-aware persistence key. Legacy `durations__{slug}`
            # values still load via _saved_for() fallback so existing
            # weekday durations aren't lost during the transition.
            persist_key = f"durations__{active_variant}__{slug}"
            custom_key  = f"custom__{active_variant}__{slug}"
            border_color = "#c0392b" if is_missing else "#4a6fa5"
            border_left  = ("3px solid #c0392b" if is_missing
                            else "3px solid #4a6fa5")
            missing_badge = ""
            if is_missing:
                missing_badge = (
                    '<span style="background:#c0392b;color:#fff;'
                    'border-radius:10px;padding:1px 8px;font-size:0.72em;'
                    'font-weight:700;margin-left:8px;letter-spacing:0.4px;'
                    'text-transform:uppercase;">Needs duration</span>'
                )
            chip_html = ""
            for choice in _DURATION_CHOICES:
                is_sel = (str(choice) == current and not is_missing)
                chip_bg = "#4a6fa5" if is_sel else "#fff"
                chip_fg = "#fff" if is_sel else "#33507e"
                active_attr = ' data-active="1"' if is_sel else ""
                chip_html += (
                    f'<button type="button" class="frol-dur-chip"'
                    f' data-slug="{escape(slug, quote=True)}"'
                    f' data-variant="{escape(active_variant, quote=True)}"'
                    f' data-value="{choice}"{active_attr}'
                    f' onclick="frolDurationPick(this)"'
                    f' style="background:{chip_bg};color:{chip_fg};'
                    f'border:1px solid #4a6fa555;border-radius:14px;'
                    f'padding:4px 10px;margin:2px;font-size:0.82em;'
                    f'font-weight:700;cursor:pointer;font-family:inherit;">'
                    f'{choice}m</button>'
                )
            rows += f"""
              <div style="background:#fff;border:1px solid {border_color}55;
                          border-left:{border_left};border-radius:8px;
                          padding:10px 12px;margin:6px 0;">
                <div style="font-weight:700;color:#33507e;margin-bottom:6px;">{escape(label)}{missing_badge}</div>
                <div style="display:flex;flex-wrap:wrap;align-items:center;gap:2px;">
                  {chip_html}
                  <input type="hidden" data-step="12"
                         data-key="{escape(persist_key, quote=True)}"
                         value="{escape(current, quote=True)}">
                  <span style="font-size:0.78em;color:#888;margin-left:8px;">or custom:</span>
                  <input class="frol-input" type="text" inputmode="numeric"
                         data-step="12" data-key="{escape(custom_key, quote=True)}"
                         value="{escape(custom, quote=True)}"
                         placeholder="e.g. 25"
                         style="max-width:110px;font-size:0.86em;padding:4px 8px;">
                </div>
              </div>
            """
        plural = "s" if len(groups[g]) != 1 else ""
        cards_html += f"""
          <details open style="background:#f6f8fc;border:1px solid #d8e1ef;
                               border-radius:10px;padding:8px 12px;margin:10px 0;">
            <summary style="cursor:pointer;font-weight:700;color:#33507e;font-size:1.0em;">
              {escape(g)} <span style="color:#888;font-weight:400;font-size:0.85em;">({len(groups[g])} item{plural})</span>
            </summary>
            <div style="padding-top:8px;">{rows}</div>
          </details>
        """

    chip_script = """
      <script>
      (function(){
        if (window.__frolDurationPickReady) return;
        window.__frolDurationPickReady = true;
        window.frolDurationPick = function(btn) {
          var slug = btn.getAttribute('data-slug');
          var val  = btn.getAttribute('data-value');
          var parent = btn.parentElement;
          if (!parent) return;
          var siblings = parent.querySelectorAll(
            'button.frol-dur-chip[data-slug="' + slug + '"]'
          );
          for (var i = 0; i < siblings.length; i++) {
            siblings[i].style.background = '#fff';
            siblings[i].style.color = '#33507e';
            siblings[i].removeAttribute('data-active');
          }
          btn.style.background = '#4a6fa5';
          btn.style.color = '#fff';
          btn.setAttribute('data-active', '1');
          var variant = btn.getAttribute('data-variant') || 'weekday';
          var keyName = 'durations__' + variant + '__' + slug;
          var hidden = parent.querySelector(
            'input[type=hidden][data-step="12"][data-key="' + keyName + '"]'
          );
          if (hidden) {
            hidden.value = val;
            // Belt-and-suspenders: the bound input listener will fire
            // off the dispatched 'input' event, but we also push the
            // save directly so a chip click always persists even if
            // the binder hasn't run yet (e.g. dynamically inserted
            // chips after Phase D variant switch).
            hidden.dispatchEvent(new Event('input', { bubbles: true }));
            if (typeof window.frolSaveField === 'function') {
              window.frolSaveField({
                step: '12', key: keyName, list: '', idx: '', value: val
              });
            }
          }
        };
      })();
      </script>
    """
    body = f"""
      {refl}
      {variant_tabs}
      {_missing_banner}
      {cards_html}
      <p class="frol-help">Durations save as you tap on the
        <strong>{escape(active_variant)}</strong> variant. Switch the
        variant tab above to set different durations for Saturday,
        Sunday, or travel days. §13 Build Your Day will use these to
        size each block on the timeline.</p>
      {chip_script}
    """
    return _section_chrome(12, "How Long Does Each Activity Take?",
        "One card per activity. Pick a realistic duration.",
        body, mode, progress, lucy_visible=True)


_S12_CATEGORY_KEYS = [_k for _k, _l, _c in _TIMELINE_PALETTE]


# ── Phase D: per-variant bucket structure ──────────────────────────────────
# section_13 is now keyed by variant slug (weekday/saturday/sunday/
# john_traveling). Each variant has its own {questions, answers, schedule,
# gen_hash, _generating, schedule_error} sub-bucket so each day-type can be
# generated and edited independently.

_S12_VARIANT_KEYS = [_vk for _vk, _vl in ACTIVITY_VARIANTS]
_S12_FLAT_KEYS = (
    "questions", "answers", "schedule", "gen_hash",
    "_generating", "schedule_error", "save_error",
)


def _s12_migrate_per_variant(progress: dict) -> bool:
    """One-shot in-place migration: if section_13 has any legacy flat key
    (questions/answers/schedule/...) at the top level, move them under
    section_13.weekday. Idempotent. Returns True if any migration
    happened (caller may save_progress)."""
    data = progress.setdefault("data", {})
    sec13 = data.setdefault("section_13", {})
    if not isinstance(sec13, dict):
        sec13 = {}
        data["section_13"] = sec13
    moved = False
    for _k in _S12_FLAT_KEYS:
        if _k in sec13:
            _wk = sec13.setdefault("weekday", {})
            if not isinstance(_wk, dict):
                _wk = {}
                sec13["weekday"] = _wk
            # Conflict handling: if both root-flat and weekday already
            # have this key, prefer the weekday copy (post-Phase-D writes
            # land there, so weekday is presumed fresher). Log the
            # conflict and stash the dropped root copy under
            # section_13._migration_conflicts so nothing is silently lost.
            if _k in _wk:
                if _wk[_k] != sec13[_k]:
                    _bin = sec13.setdefault("_migration_conflicts", {})
                    if isinstance(_bin, dict):
                        _bin[_k] = sec13[_k]
                    print(
                        f"[_s12_migrate_per_variant] conflict on "
                        f"section_13.{_k}: keeping weekday copy, "
                        f"dropped root copy parked at "
                        f"section_13._migration_conflicts.{_k}",
                        flush=True,
                    )
            else:
                _wk[_k] = sec13[_k]
            sec13.pop(_k, None)
            moved = True
    return moved


def _s12_bucket(progress: dict, variant: str = None) -> dict:
    """Return the per-variant sub-dict of section_13, creating it if
    missing. Performs lazy migration so any caller is safe."""
    _s12_migrate_per_variant(progress)
    if not variant:
        variant = _active_variant(progress)
    if variant not in _S12_VARIANT_KEYS:
        variant = "weekday"
    sec13 = progress.setdefault("data", {}).setdefault("section_13", {})
    if not isinstance(sec13, dict):
        sec13 = {}
        progress["data"]["section_13"] = sec13
    bucket = sec13.get(variant)
    if not isinstance(bucket, dict):
        bucket = {}
        sec13[variant] = bucket
    return bucket


def _s12_filter_activities_by_variant(sec12: dict, variant: str) -> dict:
    """Slice the section_12 (duration review) bucket down to only the
    keys belonging to a given variant. Pattern keys are
    'durations__{variant}__{slug}' and 'custom__{variant}__{slug}'."""
    if not isinstance(sec12, dict):
        return {}
    prefix_d = f"durations__{variant}__"
    prefix_c = f"custom__{variant}__"
    return {
        _k: _v for _k, _v in sec12.items()
        if _k.startswith(prefix_d) or _k.startswith(prefix_c)
    }


def _s12_collect_context(progress: dict, variant: str = "weekday") -> dict:
    """Gather all collected data from sections 1-11 plus the seven
    commitments into a compact dict suitable for the AI prompt.

    Variant-aware (Phase D): section_12_activities is filtered to only
    the durations recorded for this variant, and for 'john_traveling'
    the §10 john_travel_notes free-text is surfaced explicitly so the
    Pass 2 prompt can reason about the solo-parent scenario.

    Also loads the family's existing day_templates JSON files so the AI
    can use the current daily rhythm as the foundation rather than
    starting from scratch. For the weekday variant we load Mon-Fri; for
    saturday/sunday we load that single day; for john_traveling we load
    Mon-Fri (a travel week still falls on weekdays). Missing files are
    skipped silently."""
    data = progress.get("data", {}) or {}
    if variant == "saturday":
        _days = ("Saturday",)
    elif variant == "sunday":
        _days = ("Sunday",)
    else:
        _days = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
    existing_schedule = {}
    for _weekday in _days:
        _path = os.path.join(DAY_TEMPLATES_DIR, f"{_weekday}.json")
        try:
            with open(_path, "r", encoding="utf-8") as _f:
                existing_schedule[_weekday] = json.load(_f)
        except Exception:
            continue
    _sec3 = data.get("section_3") or {}
    _sec10 = data.get("section_10") or {}
    # Strip john_travel_notes from the generic §10 dump so it only
    # surfaces when the active variant is john_traveling.
    if variant != "john_traveling" and isinstance(_sec10, dict) and "john_travel_notes" in _sec10:
        _sec10 = {_k: _v for _k, _v in _sec10.items() if _k != "john_travel_notes"}
    ctx = {
        "variant":               variant,
        "members":               (data.get("section_1") or {}).get("members") or [],
        "section_2_anchors":     data.get("section_2") or {},
        "section_3_meals":       data.get("section_3") or {},
        "john_wake_time":        _sec3.get("john_wake_time") or "",
        "john_bedtime":          _sec3.get("john_bedtime")   or "",
        "section_4_prayer":      data.get("section_4") or {},
        "section_5_meals":       data.get("section_5") or {},
        "section_6_school":      data.get("section_6") or {},
        "section_7_chores":      data.get("section_7") or {},
        "section_8_work":        data.get("section_8") or {},
        "section_9_rest":        data.get("section_9") or {},
        "section_10_flex":       _sec10,
        "section_11_holidays":   data.get("section_11") or {},
        "section_12_activities": _s12_filter_activities_by_variant(
            data.get("section_12") or {}, variant),
        "seven_commitments":     list(SEVEN_COMMITMENTS),
        "existing_schedule":     existing_schedule,
    }
    if variant == "john_traveling":
        ctx["john_travel_notes"] = str(_sec10.get("john_travel_notes") or "").strip()
    return ctx


def _s12_progress_hash(ctx: dict) -> str:
    """Stable short hash of the sections-1-11 context. Used to detect
    whether the cached §12 schedule is stale relative to the underlying
    data the user has since edited."""
    try:
        blob = json.dumps(ctx, sort_keys=True, default=str)
    except Exception:
        blob = repr(ctx)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _s12_repair_json(raw: str):
    """Best-effort JSON repair for LLM output. Mirrors the strategy used
    in app.py's _repair_and_parse_json: try as-is, then strip trailing
    commas, then escape literal newlines inside string values."""
    # Attempt 1: as-is
    try:
        return json.loads(raw)
    except Exception:
        pass
    # Attempt 2: remove trailing commas before } or ]
    fixed = re.sub(r',(\s*[}\]])', r'\1', raw)
    try:
        return json.loads(fixed)
    except Exception:
        pass
    # Attempt 3: escape literal newlines/tabs/returns inside string values
    out_chars = []
    in_str = False
    i = 0
    while i < len(fixed):
        c = fixed[i]
        if c == '"' and (i == 0 or fixed[i - 1] != "\\"):
            in_str = not in_str
            out_chars.append(c)
        elif in_str and c == "\n":
            out_chars.append("\\n")
        elif in_str and c == "\r":
            out_chars.append("\\r")
        elif in_str and c == "\t":
            out_chars.append("\\t")
        else:
            out_chars.append(c)
        i += 1
    fixed2 = "".join(out_chars)
    try:
        return json.loads(fixed2)
    except Exception:
        pass
    # Attempt 4: trailing commas again after newline escape
    try:
        return json.loads(re.sub(r',(\s*[}\]])', r'\1', fixed2))
    except Exception:
        return None


def _s12_call_anthropic_json(system_prompt: str, user_prompt: str,
                             max_tokens: int = 2000):
    """Call Claude and parse the response as JSON. Returns None on any
    failure. Uses the same urllib pattern as the rest of the wizard."""
    api_key = get_anthropic_key()
    if not api_key:
        return None
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        text = (result.get("content", [{}])[0].get("text") or "").strip()
    except Exception:
        return None
    # Strip ``` fences if present
    if text.startswith("```"):
        nl = text.find("\n")
        if nl > 0:
            text = text[nl + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    # Try repair on the full text first, then on bracket-bounded slices
    parsed = _s12_repair_json(text)
    if parsed is not None:
        return parsed
    for opener, closer in (("{", "}"), ("[", "]")):
        i = text.find(opener)
        j = text.rfind(closer)
        if i >= 0 and j > i:
            parsed = _s12_repair_json(text[i:j + 1])
            if parsed is not None:
                return parsed
    return None


_S12_VARIANT_FRAMING = {
    "weekday": (
        "This is a normal Monday–Friday weekday — school, work, the regular "
        "weekday rhythm. Build the schedule that anchors the rest of the week."
    ),
    "saturday": (
        "This is a Saturday — no school. The day's spine is family time, "
        "weekly house cleaning, errands, and family activities. Treat "
        "structured school work and weekday work blocks as absent unless the "
        "family data explicitly says otherwise."
    ),
    "sunday": (
        "This is a Sunday — the Lord's Day. The schedule must protect Sunday "
        "Mass attendance and a real Sabbath rest. No school. No work for "
        "John or Lauren. Lean toward family meals, rest, prayer, hospitality, "
        "and quiet. Do NOT schedule chores, errands, or work blocks."
    ),
    "john_traveling": (
        "John is out of town this entire day for work — Lauren is solo-"
        "parenting all four boys. The schedule must NOT include John in the "
        "'who' list for any slot. Couple time cannot happen. Account for "
        "Lauren's reduced bandwidth: simpler dinner, possibly earlier kid "
        "bedtime, no second adult for handoffs. Honor whatever shifts "
        "Lauren noted in john_travel_notes."
    ),
}


def _s12_generate_questions(progress: dict, variant: str = "weekday") -> list:
    """Pass 1 — surface 3-5 specific scheduling conflicts or ambiguities
    that need Lauren's input before a draft schedule can be made. Caches
    in section_13[variant].questions and returns the cleaned list."""
    bucket = _s12_bucket(progress, variant)
    cached = bucket.get("questions")
    if isinstance(cached, list) and cached:
        return cached
    ctx = _s12_collect_context(progress, variant)
    framing = _S12_VARIANT_FRAMING.get(variant, _S12_VARIANT_FRAMING["weekday"])
    system = (
        "You are a Catholic family scheduling assistant helping Lauren — "
        "mother of four boys ages 14, 12, 5, and 13 months — turn a "
        "collected Rule of Life dataset into a concrete weekday schedule. "
        "The end goal is to fill in a per-person daily grid — one column "
        "per family member (Lauren, John, JP, Joseph, Michael, James), "
        "one row per time slot — matching the existing day_templates "
        "structure under existing_schedule. Your job in this pass is to "
        "identify 3 to 5 specific gaps that prevent you from filling "
        "that per-person grid cleanly. Focus questions on how each "
        "person's day is structured individually and where their "
        "schedules intersect — for example: \"What time does JP start "
        "independent school work?\" or \"Who is with Michael during the "
        "9-10 AM block?\" or \"Is John home for lunch on WFH days?\" "
        "Avoid family-level logistics questions that don't help you "
        "decide what goes in a specific person's column at a specific "
        "time. Do NOT ask about preferences that are already clearly "
        "stated in the data. You have access to this family's existing "
        "daily schedule under existing_schedule — use it as the "
        "foundation and build on it rather than starting from scratch. "
        "Preserve timing that already works and only suggest changes "
        "where the wizard data indicates something new or different. "
        "\n\nDAY-TYPE FRAMING: " + framing
    )
    user = (
        "Family's collected Rule of Life data (sections 1 through 11) "
        "plus the seven commitments framing. The variant being scheduled "
        f"is: {variant}.\n\n"
        + json.dumps(ctx, indent=2, default=str)
        + "\n\nReturn ONLY a JSON object of this exact shape, no prose:\n"
        + '{"questions": [{"question_text": "...", '
        + '"options": ["option A", "option B", "option C"]}]}\n\n'
        + "Provide 3 to 5 questions. Each question must have 2 to 4 "
        + "plain-text options. Phrase each in second person, addressed "
        + "directly to Lauren. Questions must be specific to the "
        + f"{variant} variant, not generic."
    )
    parsed = _s12_call_anthropic_json(system, user, max_tokens=1500)
    if not isinstance(parsed, dict):
        return []
    raw = parsed.get("questions") or []
    cleaned = []
    for q in raw:
        if not isinstance(q, dict):
            continue
        qt = str(q.get("question_text", "")).strip()
        opts_raw = q.get("options") or []
        opts = [str(o).strip() for o in opts_raw if str(o).strip()]
        if qt and 2 <= len(opts) <= 4:
            cleaned.append({"question_text": qt, "options": opts[:4]})
    cleaned = cleaned[:5]
    # Cache via direct save_progress (mirrors _seed_chores_for_section7 pattern)
    p = load_progress()
    bucket = _s12_bucket(p, variant)
    bucket["questions"] = cleaned
    save_progress(p)
    return cleaned


def _s12_generate_schedule(progress: dict, variant: str = "weekday") -> list:
    """Pass 2 — with Lauren's answers in hand, ask the AI for a complete
    suggested schedule honoring the seven commitments. Variant-aware
    (Phase D): each variant has its own framing and its own cache in
    section_13[variant].schedule."""
    bucket = _s12_bucket(progress, variant)
    cached = bucket.get("schedule")
    if isinstance(cached, list) and cached:
        return cached
    ctx = _s12_collect_context(progress, variant)
    framing = _S12_VARIANT_FRAMING.get(variant, _S12_VARIANT_FRAMING["weekday"])
    questions = bucket.get("questions") or []
    answers   = bucket.get("answers")   or {}
    if not isinstance(answers, dict):
        answers = {}
    qa_pairs = []
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        ans = answers.get(str(i)) or answers.get(i) or ""
        qa_pairs.append({
            "question": q.get("question_text", ""),
            "answer":   ans,
        })
    cat_list = ", ".join(_S12_CATEGORY_KEYS)
    system = (
        "You are a Catholic family scheduling assistant. With the family's "
        "collected Rule of Life data and Lauren's clarifying answers, "
        f"produce a complete suggested schedule for the {variant} variant. "
        "\n\nDAY-TYPE FRAMING: " + framing + "\n\n"
        "The schedule MUST honor the seven commitments: a "
        "set wake time; prayer in the morning, at noon, and at night; "
        "basic daily chores; flex buffer time; couple time for John and "
        "Lauren; a set bedtime. Use the family's stated times where given; "
        "for everything else, propose sensible times. Order chronologically "
        "from wake to bedtime. The output must be suitable for populating "
        "a per-person daily grid — one column per family member (Lauren, "
        "John, JP, Joseph, Michael, James), one row per time slot — not "
        "just a flat chronological list. Every slot MUST specify which "
        "person or persons are involved via the who field, naming "
        "specific family members rather than vague labels like 'family' "
        "or 'everyone'. If a slot truly involves the whole household, "
        "list every member by name. Account for each person's distinct "
        "rhythm: John may wake/sleep at different times than Lauren "
        "(see john_wake_time and john_bedtime), the older boys have "
        "school work, Michael is in kindergarten, James naps. You have "
        "access to this family's existing daily schedule under "
        "existing_schedule — use it as the foundation and build on it "
        "rather than starting from scratch. Preserve timing that already "
        "works and only suggest changes where the wizard data indicates "
        "something new or different."
    )
    user = (
        "Family Rule of Life data (sections 1 through 11):\n\n"
        + json.dumps(ctx, indent=2, default=str)
        + "\n\nLauren's clarifying answers:\n"
        + json.dumps(qa_pairs, indent=2, default=str)
        + "\n\nReturn ONLY a JSON object of this exact shape, no prose:\n"
        + '{"schedule": [{"time": "HH:MM", "activity_name": "...", '
        + '"duration_min": 30, "who": ["Lauren", "John"], '
        + '"category": "prayer", "note": ""}]}\n\n'
        + "Rules:\n"
        + "- time is 24-hour HH:MM\n"
        + "- duration_min is an integer (minutes)\n"
        + "- who is a list of names from this family roster only\n"
        + "- category MUST be one of: " + cat_list + "\n"
        + "- note is optional and may be empty\n"
        + "- Include the seven required commitments explicitly\n"
        + "- 12 to 20 time slots total, ordered chronologically"
    )
    parsed = _s12_call_anthropic_json(system, user, max_tokens=3500)
    if not isinstance(parsed, dict):
        return []
    gen_hash = _s12_progress_hash(ctx)
    raw = parsed.get("schedule") or []
    cleaned = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        t = str(it.get("time", "")).strip()
        if t and ":" in t:
            try:
                hh_s, mm_s = t.split(":", 1)
                hh_i = int(hh_s); mm_i = int(mm_s[:2])
                if 0 <= hh_i < 24 and 0 <= mm_i < 60:
                    t = f"{hh_i:02d}:{mm_i:02d}"
                else:
                    continue
            except Exception:
                continue
        else:
            continue
        name = str(it.get("activity_name", "")).strip()
        if not name:
            continue
        try:
            dur = int(it.get("duration_min") or 0)
        except Exception:
            dur = 0
        who_raw = it.get("who") or []
        if isinstance(who_raw, list):
            who = [str(w).strip() for w in who_raw if str(w).strip()]
        else:
            who = []
        cat = str(it.get("category", "")).strip().lower()
        if cat not in _S12_CATEGORY_KEYS:
            cat = "free"
        note = str(it.get("note", "")).strip()
        cleaned.append({
            "time":          t,
            "activity_name": name,
            "duration_min":  dur,
            "who":           who,
            "category":      cat,
            "note":          note,
            "keep":          True,
        })
    cleaned.sort(key=lambda x: x.get("time", ""))
    p = load_progress()
    bucket = _s12_bucket(p, variant)
    bucket["schedule"] = cleaned
    bucket["gen_hash"] = gen_hash
    save_progress(p)
    return cleaned


def s12_persist_kept_to_activities(progress: dict) -> int:
    """Phase D: aggregate kept schedule slots across ALL variants under
    section_13 and write them to data/frol_activities.json, tagging each
    item with its variant. Returns the number of items written, or -1
    on a write failure (caller should treat as non-success and NOT
    advance the wizard)."""
    _s12_migrate_per_variant(progress)
    sec13 = (progress.get("data", {}) or {}).get("section_13", {}) or {}
    kept = []
    for vk in _S12_VARIANT_KEYS:
        vb = sec13.get(vk) or {}
        if not isinstance(vb, dict):
            continue
        sched = vb.get("schedule") or []
        if not isinstance(sched, list):
            continue
        for it in sched:
            if not isinstance(it, dict) or not it.get("keep", True):
                continue
            tagged = dict(it)
            tagged["variant"] = vk
            kept.append(tagged)
    try:
        save_frol_activities(kept)
    except Exception:
        return -1
    return len(kept)


# ── Phase E: §15 Preview / Save / Keep helpers ─────────────────────────────
# §15 (the wizard's final step) writes per-variant day-template files into
# either the preview dir or the permanent dir. Mon-Fri are written from the
# weekday variant's schedule (5 copies); Saturday + Sunday + JohnTraveling
# are written from their own variant. The POD reader chooses which file to
# read at request time based on (weekday × john_traveling toggle × whether
# a preview dir is present).

_S15_VARIANT_TO_FILENAMES = {
    "weekday":        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "saturday":       ["Saturday"],
    "sunday":         ["Sunday"],
    "john_traveling": ["JohnTraveling"],
}


def _s15_hhmm24_to_label12(t: str) -> str:
    """Convert '14:30' → '2:30 PM'. Returns '' on invalid input."""
    try:
        parts = (t or "").strip().split(":", 1)
        if len(parts) != 2:
            return ""
        hh = int(parts[0])
        mm = int(parts[1][:2])
        if not (0 <= hh < 24 and 0 <= mm < 60):
            return ""
        suffix = "AM" if hh < 12 else "PM"
        h12 = hh % 12
        if h12 == 0:
            h12 = 12
        return f"{h12}:{mm:02d} {suffix}"
    except Exception:
        return ""


def _s15_build_grid_from_schedule(sched_list: list) -> dict:
    """Turn a per-variant schedule (list of {time, activity_name, who[], ...})
    into a day-template grid: {Person: {"H:MM AM": activity_name}}. Skips
    items with keep=False, blank labels, blank times, or empty who[]."""
    grid: dict = {}
    if not isinstance(sched_list, list):
        return grid
    for it in sched_list:
        if not isinstance(it, dict):
            continue
        if not it.get("keep", True):
            continue
        label = str(it.get("activity_name") or "").strip()
        if not label:
            continue
        lab = _s15_hhmm24_to_label12(str(it.get("time") or "").strip())
        if not lab:
            continue
        who = it.get("who") or []
        if not isinstance(who, list):
            continue
        for person in who:
            nm = str(person or "").strip()
            if not nm:
                continue
            grid.setdefault(nm, {})[lab] = label
    return grid


def s15_write_variants_to_dir(progress: dict, target_dir: str) -> list:
    """Write all per-variant schedules from section_13 into JSON files
    under `target_dir`. Returns the list of filename stems written.
    Variants with no schedule data are skipped silently."""
    _s12_migrate_per_variant(progress)
    os.makedirs(target_dir, exist_ok=True)
    sec13 = (progress.get("data", {}) or {}).get("section_13", {}) or {}
    written: list = []
    for variant, stems in _S15_VARIANT_TO_FILENAMES.items():
        bucket = sec13.get(variant) or {}
        if not isinstance(bucket, dict):
            continue
        sched = bucket.get("schedule") or []
        if not isinstance(sched, list) or not sched:
            continue
        grid = _s15_build_grid_from_schedule(sched)
        if not grid:
            continue
        for stem in stems:
            payload = {
                "weekday": stem,
                "grid":    grid,
                "frol_meta": {
                    "variant":     variant,
                    "written_at":  datetime.now().isoformat(timespec="seconds"),
                },
            }
            path = os.path.join(target_dir, f"{stem}.json")
            safe_save_json(path, payload)
            written.append(stem)
    return written


def s15_backup_permanent() -> str:
    """Copy every *.json under DAY_TEMPLATES_DIR into a fresh timestamped
    subdir under DAY_TEMPLATES_BACKUP_DIR. Returns the backup dir path
    (may be empty if there was nothing to back up). Safe to call when
    DAY_TEMPLATES_DIR is missing — returns "" in that case."""
    if not os.path.isdir(DAY_TEMPLATES_DIR):
        return ""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(DAY_TEMPLATES_BACKUP_DIR, stamp)
    os.makedirs(backup_dir, exist_ok=True)
    for nm in os.listdir(DAY_TEMPLATES_DIR):
        src = os.path.join(DAY_TEMPLATES_DIR, nm)
        if os.path.isfile(src) and nm.endswith(".json"):
            try:
                shutil.copy2(src, os.path.join(backup_dir, nm))
            except Exception:
                pass
    return backup_dir


def s15_preview_active() -> bool:
    """True if a preview dir exists and contains at least one JSON file."""
    if not os.path.isdir(DAY_TEMPLATES_PREVIEW_DIR):
        return False
    try:
        return any(
            nm.endswith(".json")
            for nm in os.listdir(DAY_TEMPLATES_PREVIEW_DIR)
        )
    except Exception:
        return False


def s15_discard_preview() -> bool:
    """Remove the preview dir entirely. Returns True if anything was deleted."""
    if os.path.isdir(DAY_TEMPLATES_PREVIEW_DIR):
        shutil.rmtree(DAY_TEMPLATES_PREVIEW_DIR, ignore_errors=True)
        return True
    return False


def s15_promote_preview_to_permanent() -> dict:
    """Back up the permanent dir, then copy every JSON file out of the
    preview dir into the permanent dir. Only deletes the preview dir if
    ALL eligible files copy successfully; otherwise the preview is left
    intact so no data is lost and the error is surfaced in the receipt."""
    receipt: dict = {"promoted": 0, "backup_dir": "",
                     "skipped": "no_preview", "errors": []}
    if not s15_preview_active():
        return receipt
    receipt["skipped"] = ""
    receipt["backup_dir"] = s15_backup_permanent()
    os.makedirs(DAY_TEMPLATES_DIR, exist_ok=True)
    copied = 0
    errors: list = []
    eligible = [
        nm for nm in os.listdir(DAY_TEMPLATES_PREVIEW_DIR)
        if nm.endswith(".json")
        and os.path.isfile(os.path.join(DAY_TEMPLATES_PREVIEW_DIR, nm))
    ]
    for nm in eligible:
        src = os.path.join(DAY_TEMPLATES_PREVIEW_DIR, nm)
        try:
            shutil.copy2(src, os.path.join(DAY_TEMPLATES_DIR, nm))
            copied += 1
        except Exception as _exc:
            errors.append(f"{nm}: {type(_exc).__name__}: {_exc}")
    receipt["promoted"] = copied
    receipt["errors"]   = errors
    # Only clear preview if every eligible file made it across. If even
    # one failed, keep the preview dir so the user can retry or inspect.
    if not errors and copied == len(eligible):
        shutil.rmtree(DAY_TEMPLATES_PREVIEW_DIR, ignore_errors=True)
        receipt["preview_cleared"] = "yes"
    else:
        receipt["preview_cleared"] = "no (errors)"
    return receipt


def john_traveling_enabled() -> bool:
    """Read app_settings.john_traveling.enabled. Defaults to False."""
    try:
        from render_settings import load_app_settings
        st = (load_app_settings() or {}).get("john_traveling") or {}
        return bool(st.get("enabled"))
    except Exception:
        return False


def set_john_traveling(enabled: bool) -> None:
    """Set the app-wide john_traveling toggle, stamping set_at."""
    from render_settings import load_app_settings, save_app_settings
    s = load_app_settings() or {}
    s["john_traveling"] = {
        "enabled": bool(enabled),
        "set_at":  datetime.now().isoformat(timespec="seconds"),
    }
    save_app_settings(s)


def pod_template_stem(weekday: str) -> str:
    """Return the day-template filename stem the POD should read for
    `weekday`, honoring the john_traveling toggle. Saturday/Sunday are
    always their own files; Mon-Fri use JohnTraveling when the toggle
    is on, otherwise the weekday's own file."""
    if weekday in ("Saturday", "Sunday"):
        return weekday
    if john_traveling_enabled():
        return "JohnTraveling"
    return weekday


def pod_template_dir() -> str:
    """Return the directory POD should read from: preview if a preview
    is active, otherwise the permanent dir."""
    return DAY_TEMPLATES_PREVIEW_DIR if s15_preview_active() else DAY_TEMPLATES_DIR


def get_pod_day_slots(weekday: str, person: str = "Mom") -> dict:
    """POD-aware variant of get_frol_day_slots. Resolves the right file
    (Saturday/Sunday/JohnTraveling/{weekday}) and the right directory
    (preview dir if active, else permanent dir), then returns the same
    {time_label: activity_name} dict get_frol_day_slots returns. All JSON
    reads are delegated to data_helpers.load_day_template (per the
    'data_helpers is the only file that should read/write JSON' rule)."""
    from data_helpers import load_day_template
    stem = pod_template_stem(weekday)
    base = pod_template_dir()
    payload = load_day_template(stem, base_dir=base)
    if not payload and base != DAY_TEMPLATES_DIR:
        # Preview is active but this variant isn't in the preview dir
        # (e.g. user only previewed weekday but it's Saturday); fall
        # back to the permanent copy.
        payload = load_day_template(stem, base_dir=DAY_TEMPLATES_DIR)
    grid = (payload or {}).get("grid", {}) or {}
    if person in ("Lauren", "Mom"):
        mom_grid    = dict(grid.get("Mom", {})    or {})
        lauren_grid = dict(grid.get("Lauren", {}) or {})
        if person == "Mom":
            merged = {**lauren_grid, **mom_grid}
        else:
            merged = {**mom_grid, **lauren_grid}
        return {t: v for t, v in merged.items() if (v or "").strip()}
    own = grid.get(person, {}) or {}
    return {t: v for t, v in dict(own).items() if (v or "").strip()}


def render_section_12(progress: dict, mode: str) -> str:
    """V2 §12 — Build Your Day (AI-driven, two-pass).
    Pass 1 surfaces clarifying questions; Pass 2 produces a suggested
    weekday schedule. Both calls are cached in section_12 so a page
    refresh does not re-trigger the API."""
    # ── Phase D: per-variant bucket + lazy migration ───────────────────────
    av = _active_variant(progress)
    av_esc = escape(av, quote=True)
    if av not in _S12_VARIANT_KEYS:
        av = "weekday"; av_esc = "weekday"
    av_label = dict(ACTIVITY_VARIANTS).get(av, av)
    sec12 = _s12_bucket(progress, av)

    # ── Fix 1: clear stuck _generating flag (per-variant) ──────────────────
    if sec12.get("_generating") and not sec12.get("schedule"):
        _qs_chk  = sec12.get("questions") or []
        _ans_chk = sec12.get("answers") or {}
        _all_answered = (
            isinstance(_qs_chk, list) and len(_qs_chk) > 0
            and isinstance(_ans_chk, dict)
            and all(
                (str(_i) in _ans_chk) or (_i in _ans_chk)
                for _i in range(len(_qs_chk))
            )
        )
        if not _all_answered:
            _pl = load_progress()
            _bk = _s12_bucket(_pl, av)
            _bk.pop("_generating", None)
            save_progress(_pl)
            sec12 = _bk

    mode_esc = escape(mode, quote=True)
    variant_tabs_html = _render_variant_tab_bar(13, progress, mode)

    refl = render_reflection_card(
        "The day, built for you",
        "<p>Instead of dragging activities onto a blank grid, everything you "
        "collected in §1 through §11 is sent to an AI scheduler. First it "
        "asks a few clarifying questions, then it drafts a complete weekday "
        "schedule honoring the seven commitments. You can tweak each slot "
        "before saving.</p>",
        key="sec12_intro",
    )

    # Missing API key → friendly notice, no API calls attempted
    if not has_anthropic_key():
        notice = (
            '<div style="background:#fef3e6;border:1px solid #e6b97a;'
            'border-radius:8px;padding:14px;margin:10px 0;color:#8a5a1a;">'
            '<strong>Anthropic API key not configured.</strong> Add your key '
            'in Settings &rarr; AI &amp; Planning, then return here to '
            'generate your day.'
            '</div>'
        )
        return _section_chrome(13, "Build Your Day",
            "AI-suggested schedule built from everything you've collected.",
            refl + variant_tabs_html + notice, mode, progress, lucy_visible=True)

    # ── Pass 1 cache (call if absent) ──────────────────────────────────────
    questions = sec12.get("questions")
    if not isinstance(questions, list) or not questions:
        questions = _s12_generate_questions(progress, av)
        sec12 = _s12_bucket(load_progress(), av)

    answers = sec12.get("answers") or {}
    if not isinstance(answers, dict):
        answers = {}

    # Pass 1 failed entirely → show error + regenerate
    if not questions:
        body = (
            '<div style="background:#fef3e6;border:1px solid #e6b97a;'
            'border-radius:8px;padding:14px;margin:10px 0;color:#8a5a1a;">'
            "<strong>Couldn't reach the AI to generate questions.</strong> "
            "Try again in a moment."
            '</div>'
            '<form method="POST" action="/frol-wizard" style="margin-top:14px;">'
            '<input type="hidden" name="action" value="s12_regenerate">'
            '<input type="hidden" name="section" value="12">'
            f'<input type="hidden" name="variant" value="{av_esc}">'
            f'<input type="hidden" name="mode" value="{mode_esc}">'
            '<button type="submit" style="padding:10px 18px;background:#4a6fa5;'
            'color:#fff;border:none;border-radius:6px;cursor:pointer;'
            'font-weight:700;">Try again</button>'
            '</form>'
        )
        return _section_chrome(13, "Build Your Day",
            f"AI-suggested schedule — {av_label}.",
            refl + variant_tabs_html + body, mode, progress, lucy_visible=True)

    # First unanswered question (if any)
    next_idx = None
    for i, _q in enumerate(questions):
        if str(i) not in answers and i not in answers:
            next_idx = i
            break

    # ── Stage A: still answering questions ─────────────────────────────────
    if next_idx is not None:
        q = questions[next_idx]
        qt = q.get("question_text", "")
        opts = q.get("options", []) or []
        total = len(questions)
        progress_label = f"Question {next_idx + 1} of {total}"

        opt_buttons = ""
        for opt in opts:
            opt_esc = escape(str(opt), quote=True)
            opt_disp = escape(str(opt))
            opt_buttons += (
                '<form method="POST" action="/frol-wizard" style="margin:6px 0;">'
                '<input type="hidden" name="action" value="s12_answer">'
                '<input type="hidden" name="section" value="12">'
                f'<input type="hidden" name="variant" value="{av_esc}">'
                f'<input type="hidden" name="mode" value="{mode_esc}">'
                f'<input type="hidden" name="q_idx" value="{next_idx}">'
                f'<input type="hidden" name="value" value="{opt_esc}">'
                '<button type="submit" style="width:100%;text-align:left;'
                'padding:14px 18px;background:#fff;border:1px solid #d8e1ef;'
                'border-radius:8px;cursor:pointer;font-size:1em;'
                'color:#33507e;font-weight:600;">'
                f'{opt_disp}'
                '</button>'
                '</form>'
            )

        regen_form = (
            '<form method="POST" action="/frol-wizard" style="margin-top:14px;">'
            '<input type="hidden" name="action" value="s12_regenerate">'
            '<input type="hidden" name="section" value="12">'
            f'<input type="hidden" name="variant" value="{av_esc}">'
            f'<input type="hidden" name="mode" value="{mode_esc}">'
            '<button type="submit" style="background:transparent;border:none;'
            'color:#7088a8;cursor:pointer;text-decoration:underline;'
            'font-size:0.86em;">Regenerate questions</button>'
            '</form>'
        )

        body = f"""
          {refl}
          {variant_tabs_html}
          <div style="background:#f6f8fc;border:1px solid #d8e1ef;
                      border-radius:8px;padding:18px;margin:10px 0;">
            <div style="font-size:0.82em;color:#7088a8;margin-bottom:8px;
                        font-weight:600;text-transform:uppercase;
                        letter-spacing:0.5px;">
              {escape(progress_label)}
            </div>
            <div style="font-size:1.08em;color:#33507e;font-weight:600;
                        margin-bottom:14px;line-height:1.4;">
              {escape(qt)}
            </div>
            {opt_buttons}
          </div>
          {regen_form}
        """
        return _section_chrome(13, "Build Your Day",
            f"{av_label}: a few quick clarifying questions, then your draft.",
            body, mode, progress, lucy_visible=True)

    # ── Stage B: all questions answered → schedule ─────────────────────────
    schedule = sec12.get("schedule")
    if not isinstance(schedule, list) or not schedule:
        # Defensive UX: show a loading interstitial on first arrival
        # rather than blocking the page for the full 20-40s API call
        # with no feedback. A meta-refresh re-enters this branch with
        # the _generating flag set, at which point we run the actual
        # API call synchronously and the next render shows the result.
        if not sec12.get("_generating"):
            _pl = load_progress()
            _s12_bucket(_pl, av)["_generating"] = True
            save_progress(_pl)
            loading_body = (
                '<div style="text-align:center;padding:60px 20px;">'
                '<div style="font-size:1.3em;color:#33507e;'
                'font-weight:600;">Generating your schedule&hellip;</div>'
                '<div style="margin-top:10px;color:#7088a8;'
                'font-size:0.92em;">This usually takes 20 to 40 seconds. '
                'The page will refresh automatically.</div>'
                '<div style="margin:24px auto 0;width:40px;height:40px;'
                'border:4px solid #d8e1ef;border-top-color:#4a6fa5;'
                'border-radius:50%;animation:s12spin 1s linear infinite;">'
                '</div>'
                '<style>@keyframes s12spin{to{transform:rotate(360deg)}}'
                '</style>'
                '<meta http-equiv="refresh" content="1">'
                '</div>'
            )
            return _section_chrome(13, "Build Your Day",
                f"Generating your suggested {av_label} schedule.",
                refl + variant_tabs_html + loading_body, mode, progress, lucy_visible=False)
        # _generating flag is set — actually call the API now and clear.
        # Fix 2: hard-guard the API call so any exception ALWAYS clears
        # _generating; otherwise the flag persists and suppresses the
        # loading interstitial on every subsequent visit.
        import traceback as _s12_tb
        _gen_err = None
        try:
            schedule = _s12_generate_schedule(progress, av)
        except Exception as _s12_exc:
            schedule = []
            _gen_err = f"{type(_s12_exc).__name__}: {_s12_exc}"
            _tb_blob = _s12_tb.format_exc()
            print(
                f"[s12_generate_schedule] FAILED ({av}): {_gen_err}",
                flush=True,
            )
            print(_tb_blob, flush=True)
        _pl = load_progress()
        _bk = _s12_bucket(_pl, av)
        _bk.pop("_generating", None)
        if _gen_err:
            _bk["schedule_error"] = _gen_err
        else:
            _bk.pop("schedule_error", None)
        save_progress(_pl)
        sec12 = _bk
        schedule = sec12.get("schedule") or []

    if not schedule:
        _err_detail = sec12.get("schedule_error") or ""
        _err_html = ""
        if _err_detail:
            _err_html = (
                '<div style="margin-top:8px;font-size:0.88em;color:#8a5a1a;'
                'font-family:monospace;background:#fff7ea;padding:8px 10px;'
                'border-radius:6px;">'
                + escape(str(_err_detail))
                + '</div>'
            )
        body = (
            '<div style="background:#fef3e6;border:1px solid #e6b97a;'
            'border-radius:8px;padding:14px;margin:10px 0;color:#8a5a1a;">'
            "<strong>Couldn't generate a schedule.</strong> The AI didn't "
            'return a valid response. Try regenerating below.'
            + _err_html +
            '</div>'
            '<form method="POST" action="/frol-wizard" style="margin-top:14px;">'
            '<input type="hidden" name="action" value="s12_regenerate">'
            '<input type="hidden" name="section" value="12">'
            f'<input type="hidden" name="variant" value="{av_esc}">'
            f'<input type="hidden" name="mode" value="{mode_esc}">'
            '<button type="submit" style="padding:10px 18px;background:#4a6fa5;'
            'color:#fff;border:none;border-radius:6px;cursor:pointer;'
            'font-weight:700;">Regenerate</button>'
            '</form>'
        )
        return _section_chrome(13, "Build Your Day",
            f"AI-suggested {av_label} schedule.",
            refl + variant_tabs_html + body, mode, progress, lucy_visible=True)

    # Move-picker options: every 10 min from 04:00 through 23:50
    time_options = []
    for _hour in range(4, 24):
        for _minute in (0, 10, 20, 30, 40, 50):
            time_options.append(f"{_hour:02d}:{_minute:02d}")

    cards_html = ""
    for i, item in enumerate(schedule):
        if not isinstance(item, dict):
            continue
        t       = str(item.get("time", "")).strip()
        name    = str(item.get("activity_name", "")).strip()
        try:
            dur = int(item.get("duration_min") or 0)
        except Exception:
            dur = 0
        who_raw = item.get("who") or []
        if isinstance(who_raw, list):
            who_str = ", ".join(str(w) for w in who_raw if str(w).strip()) or "—"
        else:
            who_str = "—"
        cat     = str(item.get("category", "")).strip() or "free"
        note    = str(item.get("note", "")).strip()
        kept    = bool(item.get("keep", True))
        _lbl, color = _PALETTE_BY_KEY.get(cat, ("Free", "#d8d8d8"))

        # 12-hour display
        try:
            hh_s, mm_s = t.split(":", 1)
            hh_i = int(hh_s); mm_i = int(mm_s)
            suffix = "AM" if hh_i < 12 else "PM"
            hh12 = hh_i % 12 or 12
            time_disp = f"{hh12}:{mm_i:02d} {suffix}"
        except Exception:
            time_disp = t

        move_opts = ""
        for opt_t in time_options:
            sel = "selected" if opt_t == t else ""
            # Fix 1: render the dropdown labels in 12-hour AM/PM so iOS
            # and desktop users never see military time. The option
            # value stays HH:MM 24-hour for server-side parsing.
            try:
                _oh, _om = opt_t.split(":", 1)
                _ohi = int(_oh); _omi = int(_om)
                _osuf = "AM" if _ohi < 12 else "PM"
                _o12  = _ohi % 12 or 12
                opt_lbl = f"{_o12}:{_omi:02d} {_osuf}"
            except Exception:
                opt_lbl = opt_t
            move_opts += f'<option value="{opt_t}" {sel}>{opt_lbl}</option>'

        if kept:
            action_name  = "s12_remove"
            btn_label    = "Remove"
            btn_color    = "#b04a4a"
            card_opacity = "1"
            card_strike  = ""
        else:
            action_name  = "s12_restore"
            btn_label    = "Restore"
            btn_color    = "#5b8a5b"
            card_opacity = "0.45"
            card_strike  = "text-decoration:line-through;"

        dur_chip = ""
        if dur:
            dur_chip = f'<span style="font-size:0.78em;color:#888;">· {dur} min</span>'
        note_html = ""
        if note:
            note_html = (
                '<div style="font-size:0.84em;color:#7d7d7d;margin-top:4px;'
                f'font-style:italic;">{escape(note)}</div>'
            )

        # Fix 2 + Fix 3: no inline <form>s here. The time-picker and
        # Remove/Restore button carry data-s12-* attrs; the inline
        # <script> further down in this body uses fetch() to POST to
        # the existing s12_move / s12_remove / s12_restore handlers
        # without a page reload, then patches the card DOM and flashes
        # the "Saved" pill so Lauren sees the change persisted.
        cards_html += f"""
          <div class="s12-card" data-slot-idx="{i}"
               style="background:#fff;border:1px solid #d8e1ef;
                      border-left:5px solid {color};border-radius:8px;
                      padding:12px 16px;margin:8px 0;opacity:{card_opacity};">
            <div style="display:flex;align-items:center;
                        justify-content:space-between;gap:12px;">
              <div class="s12-card-body" style="flex:1;{card_strike}">
                <div style="display:flex;align-items:center;gap:10px;
                            margin-bottom:4px;flex-wrap:wrap;">
                  <span class="s12-time-disp"
                        style="font-weight:700;color:#33507e;font-size:1.04em;">
                    {escape(time_disp)}
                  </span>
                  <span style="display:inline-block;width:10px;height:10px;
                               background:{color};border-radius:50%;
                               border:1px solid #00000022;"></span>
                  <span style="font-size:0.78em;color:#888;
                               text-transform:capitalize;">{escape(cat)}</span>
                  {dur_chip}
                  <span class="s12-flash"
                        style="font-size:0.78em;color:#2e5d3b;
                               font-weight:700;opacity:0;
                               transition:opacity 0.25s;">Saved &check;</span>
                </div>
                <div style="font-size:1.02em;color:#222;font-weight:600;
                            margin-bottom:3px;">
                  {escape(name)}
                </div>
                <div style="font-size:0.86em;color:#666;">
                  {escape(who_str)}
                </div>
                {note_html}
              </div>
              <div style="display:flex;flex-direction:column;gap:6px;
                          align-items:flex-end;">
                <select data-s12-action="s12_move" data-s12-slot="{i}"
                        data-s12-mode="{mode_esc}" data-s12-variant="{av_esc}"
                        style="padding:4px 8px;border:1px solid #d8e1ef;
                               border-radius:4px;font-size:0.84em;
                               background:#fbfcfd;cursor:pointer;">
                  {move_opts}
                </select>
                <button type="button" data-s12-action="{action_name}"
                        data-s12-slot="{i}" data-s12-mode="{mode_esc}"
                        data-s12-variant="{av_esc}"
                        style="padding:4px 12px;background:transparent;
                               border:1px solid {btn_color};color:{btn_color};
                               border-radius:4px;cursor:pointer;
                               font-size:0.82em;">
                  {btn_label}
                </button>
              </div>
            </div>
          </div>
        """

    # ── Enhancement 2: overload warning ────────────────────────────────────
    total_kept_min = 0
    for _it in schedule:
        if isinstance(_it, dict) and _it.get("keep", True):
            try:
                total_kept_min += int(_it.get("duration_min") or 0)
            except Exception:
                pass
    total_hours_disp = round(total_kept_min / 60.0, 1)
    overload_html = ""
    if total_kept_min > 720:
        overload_html = (
            '<div style="background:#fde2e2;border:1px solid #d97a7a;'
            'border-radius:8px;padding:14px;margin:10px 0;color:#8a2a2a;'
            'font-weight:600;">'
            'This schedule has more structured activity than a family day '
            'can realistically hold. Please remove or shorten some items.'
            '</div>'
        )
    elif total_kept_min > 600:
        overload_html = (
            '<div style="background:#fef3e6;border:1px solid #e6b97a;'
            'border-radius:8px;padding:14px;margin:10px 0;color:#8a5a1a;'
            'font-weight:600;">'
            f'This day is very full — {total_hours_disp} hours scheduled. '
            'For a family with young children 10 hours of structured '
            'activity is usually the limit.'
            '</div>'
        )

    # ── Enhancement 1: per-person grid view ────────────────────────────────
    def _s12_hhmm_to_min(hhmm):
        try:
            _hp, _mp = str(hhmm).split(":", 1)
            return int(_hp) * 60 + int(_mp)
        except Exception:
            return None

    def _s12_min_to_label(rm):
        _hh = rm // 60
        _mm = rm % 60
        _suf = "AM" if _hh < 12 else "PM"
        _h12 = _hh % 12 or 12
        return f"{_h12}:{_mm:02d} {_suf}"

    people_list = []
    seen_people = set()
    for _it in schedule:
        if not isinstance(_it, dict):
            continue
        _who = _it.get("who") or []
        if not isinstance(_who, list):
            continue
        for _w in _who:
            _ws = str(_w).strip()
            if _ws and _ws not in seen_people:
                seen_people.add(_ws)
                people_list.append(_ws)

    slot_mins = []
    for _it in schedule:
        if not isinstance(_it, dict):
            continue
        _mm = _s12_hhmm_to_min(str(_it.get("time", "")).strip())
        if _mm is not None:
            slot_mins.append((_mm // 30) * 30)

    if slot_mins:
        grid_start = min(slot_mins)
        grid_end   = max(slot_mins)
        row_times  = list(range(grid_start, grid_end + 30, 30))
    else:
        row_times = []

    cell_map = {}
    for _it in schedule:
        if not isinstance(_it, dict):
            continue
        _mm = _s12_hhmm_to_min(str(_it.get("time", "")).strip())
        if _mm is None:
            continue
        _row_min = (_mm // 30) * 30
        _cat = str(_it.get("category", "")).strip() or "free"
        _lbl_c, c_color = _PALETTE_BY_KEY.get(_cat, ("Free", "#d8d8d8"))
        _name_v = str(_it.get("activity_name", "")).strip()
        _who_raw = _it.get("who") or []
        if not isinstance(_who_raw, list):
            continue
        for _w in _who_raw:
            _ws = str(_w).strip()
            if not _ws:
                continue
            cell_map.setdefault((_row_min, _ws), []).append((_name_v, c_color))

    pills_html = ""
    for _p in people_list:
        _p_esc  = escape(_p)
        _p_attr = escape(_p, quote=True)
        pills_html += (
            f'<button type="button" class="s12-person-pill" data-person="{_p_attr}" '
            'data-hidden="0" onclick="s12TogglePerson(this)" '
            'style="padding:4px 12px;margin:2px;border:1px solid #4a6fa5;'
            'background:#4a6fa5;color:#fff;border-radius:999px;cursor:pointer;'
            f'font-size:0.82em;font-weight:600;">{_p_esc}</button>'
        )

    th_cells = (
        '<th style="padding:6px;border:1px solid #d8e1ef;'
        'background:#f6f8fc;text-align:left;">Time</th>'
    )
    for _p in people_list:
        _p_esc  = escape(_p)
        _p_attr = escape(_p, quote=True)
        th_cells += (
            f'<th class="s12-col" data-person="{_p_attr}" '
            'style="padding:6px;border:1px solid #d8e1ef;background:#f6f8fc;'
            f'text-align:center;">{_p_esc}</th>'
        )

    grid_rows_html = ""
    for _rm in row_times:
        _rl = escape(_s12_min_to_label(_rm))
        _row_cells = (
            f'<td style="padding:6px;border:1px solid #d8e1ef;background:#fbfcfd;'
            f'font-size:0.82em;color:#33507e;font-weight:600;'
            f'white-space:nowrap;">{_rl}</td>'
        )
        for _p in people_list:
            _items_here = cell_map.get((_rm, _p), [])
            _inner = ""
            for _nm, _col in _items_here:
                _inner += (
                    '<div style="font-size:0.82em;color:#222;'
                    'line-height:1.3;margin:1px 0;">'
                    '<span style="display:inline-block;width:8px;height:8px;'
                    f'background:{_col};border-radius:50%;'
                    'border:1px solid #00000022;margin-right:4px;'
                    f'vertical-align:middle;"></span>{escape(_nm)}</div>'
                )
            _p_attr = escape(_p, quote=True)
            _row_cells += (
                f'<td class="s12-col" data-person="{_p_attr}" '
                'style="padding:4px;border:1px solid #d8e1ef;'
                f'vertical-align:top;">{_inner}</td>'
            )
        grid_rows_html += f'<tr>{_row_cells}</tr>'

    if row_times and people_list:
        grid_html = (
            '<div id="s12-grid" style="display:none;margin:10px 0;">'
            '<div style="margin-bottom:8px;">'
            '<span style="font-size:0.82em;color:#7088a8;'
            'margin-right:6px;font-weight:600;">Show / hide:</span>'
            f'{pills_html}'
            '</div>'
            '<div style="overflow-x:auto;">'
            '<table style="border-collapse:collapse;width:100%;'
            'background:#fff;">'
            f'<thead><tr>{th_cells}</tr></thead>'
            f'<tbody>{grid_rows_html}</tbody>'
            '</table></div></div>'
        )
    else:
        grid_html = (
            '<div id="s12-grid" style="display:none;margin:10px 0;'
            'padding:14px;background:#f6f8fc;border:1px solid #d8e1ef;'
            'border-radius:8px;color:#7088a8;">'
            'No scheduled times to display in grid view.'
            '</div>'
        )

    view_toggle_html = (
        '<div style="margin:10px 0;display:flex;gap:6px;">'
        '<button type="button" id="s12-btn-list" '
        'onclick="s12ShowView(&#39;list&#39;)" '
        'style="padding:6px 16px;border:1px solid #4a6fa5;background:#4a6fa5;'
        'color:#fff;border-radius:6px;cursor:pointer;font-weight:600;">'
        'List view</button>'
        '<button type="button" id="s12-btn-grid" '
        'onclick="s12ShowView(&#39;grid&#39;)" '
        'style="padding:6px 16px;border:1px solid #4a6fa5;background:#fff;'
        'color:#4a6fa5;border-radius:6px;cursor:pointer;font-weight:600;">'
        'Grid view</button>'
        '</div>'
    )

    # NOTE: s12ShowView() and s12TogglePerson() live in
    # /static/js/frol_wizard.js (loaded by the wizard page chrome) so
    # they cannot be silently lost to any future <script>-stripping in
    # _section_chrome or in transit. Do not re-inline them here.

    # ── Fix 3: stale-cache warning (per-variant ctx) ───────────────────────
    _cur_hash   = _s12_progress_hash(_s12_collect_context(progress, av))
    _gen_hash   = sec12.get("gen_hash")
    stale_html  = ""
    if _gen_hash and _gen_hash != _cur_hash:
        stale_html = (
            '<div style="background:#fef3e6;border:1px solid #e6b97a;'
            'border-radius:8px;padding:14px;margin:10px 0;color:#8a5a1a;'
            'font-weight:600;">'
            'You have made changes since this schedule was generated. '
            'Tap Regenerate to update it.'
            '</div>'
        )

    regen_btn = (
        '<form method="POST" action="/frol-wizard" '
        'style="display:inline-block;margin-right:10px;">'
        '<input type="hidden" name="action" value="s12_regenerate">'
        '<input type="hidden" name="section" value="12">'
        f'<input type="hidden" name="variant" value="{av_esc}">'
        f'<input type="hidden" name="mode" value="{mode_esc}">'
        f'<button type="submit" style="padding:10px 18px;background:#fbf6ee;'
        f'border:1px solid #ead9b8;color:#8a6a2a;border-radius:6px;'
        f'cursor:pointer;font-weight:700;">Regenerate {escape(av_label)}</button>'
        '</form>'
    )
    save_btn = (
        '<form method="POST" action="/frol-wizard" style="display:inline-block;">'
        '<input type="hidden" name="action" value="s12_save_continue">'
        '<input type="hidden" name="section" value="12">'
        f'<input type="hidden" name="mode" value="{mode_esc}">'
        '<button type="submit" style="padding:10px 18px;background:#4a6fa5;'
        'border:none;color:#fff;border-radius:6px;cursor:pointer;'
        'font-weight:700;">Save and Continue</button>'
        '</form>'
    )

    # ── Phase D: cross-variant status strip ────────────────────────────────
    _all_sec13 = (progress.get("data", {}) or {}).get("section_13", {}) or {}
    _gen_chips = ""
    for _vk, _vl in ACTIVITY_VARIANTS:
        _vb = _all_sec13.get(_vk) if isinstance(_all_sec13, dict) else None
        _has = isinstance(_vb, dict) and isinstance(_vb.get("schedule"), list) and len(_vb.get("schedule")) > 0
        _bg = "#e2efe5" if _has else "#f0f0f0"
        _fg = "#2e5d3b" if _has else "#888"
        _mark = "✓" if _has else "—"
        _gen_chips += (
            f'<span style="display:inline-block;padding:3px 10px;margin:2px;'
            f'border-radius:999px;background:{_bg};color:{_fg};'
            f'font-size:0.78em;font-weight:700;">{_mark} {escape(_vl)}</span>'
        )
    variant_status_html = (
        '<div style="background:#f6f8fc;border:1px solid #d8e1ef;'
        'border-radius:8px;padding:8px 12px;margin:10px 0;font-size:0.82em;'
        'color:#7088a8;">'
        '<strong style="color:#33507e;">Variants generated:</strong> '
        + _gen_chips +
        '</div>'
    )

    kept_count = sum(
        1 for it in schedule if isinstance(it, dict) and it.get("keep", True)
    )

    # ── Fix 2 + Fix 3: inline fetch() handlers for the per-card time
    # picker and Remove/Restore button. Hooks POST to the existing
    # s12_move / s12_remove / s12_restore handlers in app.py without
    # a page reload, then patches the card DOM in place and flashes a
    # "Saved" pill near the changed card. Guard prevents double-binding
    # if §12 ever re-renders inside the same page. Plain JS, no JS
    # string literals contain newlines (per claud.md rule).
    fetch_script = """
      <script>
      (function(){
        if (window.s12FetchHandlersBound) { return; }
        window.s12FetchHandlersBound = true;
        function flash(card){
          if (!card) { return; }
          var f = card.querySelector('.s12-flash');
          if (!f) { return; }
          f.style.opacity = '1';
          setTimeout(function(){ f.style.opacity = '0'; }, 1500);
        }
        function post(act, slot, mode, variant, extra){
          var fd = new FormData();
          fd.append('action',   act);
          fd.append('section',  '12');
          fd.append('mode',     mode);
          fd.append('slot_idx', slot);
          fd.append('variant',  variant || 'weekday');
          if (extra) { for (var k in extra) { fd.append(k, extra[k]); } }
          return fetch('/frol-wizard', {
            method: 'POST', body: fd, credentials: 'same-origin'
          });
        }
        function fmt12(hhmm){
          var p = String(hhmm).split(':');
          var hh = parseInt(p[0], 10);
          if (isNaN(hh)) { return hhmm; }
          var mm  = p[1] || '00';
          var suf = hh < 12 ? 'AM' : 'PM';
          var h12 = (hh % 12) || 12;
          return h12 + ':' + mm + ' ' + suf;
        }
        document.addEventListener('change', function(ev){
          var el = ev.target;
          if (!el || !el.getAttribute) { return; }
          if (el.getAttribute('data-s12-action') !== 's12_move') { return; }
          var slot   = el.getAttribute('data-s12-slot');
          var mode   = el.getAttribute('data-s12-mode') || 'structured';
          var variant = el.getAttribute('data-s12-variant') || 'weekday';
          var newVal = el.value;
          var card   = el.closest('.s12-card');
          post('s12_move', slot, mode, variant, {new_time: newVal}).then(function(r){
            if (!r.ok) { return; }
            var disp = card && card.querySelector('.s12-time-disp');
            if (disp) { disp.textContent = fmt12(newVal); }
            flash(card);
          }).catch(function(){});
        });
        document.addEventListener('click', function(ev){
          var btn = ev.target;
          if (!btn || !btn.getAttribute) { return; }
          var act = btn.getAttribute('data-s12-action');
          if (act !== 's12_remove' && act !== 's12_restore') { return; }
          ev.preventDefault();
          var slot = btn.getAttribute('data-s12-slot');
          var mode = btn.getAttribute('data-s12-mode') || 'structured';
          var variant = btn.getAttribute('data-s12-variant') || 'weekday';
          var card = btn.closest('.s12-card');
          post(act, slot, mode, variant, null).then(function(r){
            if (!r.ok) { return; }
            var body = card && card.querySelector('.s12-card-body');
            if (act === 's12_remove'){
              if (card) { card.style.opacity = '0.45'; }
              if (body) { body.style.textDecoration = 'line-through'; }
              btn.setAttribute('data-s12-action', 's12_restore');
              btn.textContent = 'Restore';
              btn.style.borderColor = '#5b8a5b';
              btn.style.color       = '#5b8a5b';
            } else {
              if (card) { card.style.opacity = '1'; }
              if (body) { body.style.textDecoration = ''; }
              btn.setAttribute('data-s12-action', 's12_remove');
              btn.textContent = 'Remove';
              btn.style.borderColor = '#b04a4a';
              btn.style.color       = '#b04a4a';
            }
            flash(card);
          }).catch(function(){});
        });
      })();
      </script>
    """

    body = f"""
      {refl}
      {variant_tabs_html}
      {variant_status_html}
      <div style="background:#f6f8fc;border:1px solid #d8e1ef;
                  border-radius:8px;padding:10px 14px;margin:10px 0;
                  font-size:0.88em;color:#33507e;">
        <strong>{kept_count}</strong> of <strong>{len(schedule)}</strong>
        {escape(av_label)} slots kept. Change a time or tap Remove and it saves
        automatically — no page reload. Tap Regenerate to start over.
      </div>
      {stale_html}
      {overload_html}
      {view_toggle_html}
      <div id="s12-list">{cards_html}</div>
      {grid_html}
      {fetch_script}
      <div style="margin-top:18px;padding-top:14px;border-top:1px solid #d8e1ef;">
        {regen_btn}
        {save_btn}
      </div>
    """
    return _section_chrome(13, "Build Your Day",
        f"AI-suggested {av_label} schedule — flip the tabs above to build each variant.",
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


def render_section_13(progress: dict, mode: str) -> str:
    """V2 §13 — Seven Commitments Check. Renders the Dominick seven with
    derived ✅/⚠️ status and one-tap deep-link 'Fix' buttons."""
    items = _commitments_status(progress)
    refl = render_reflection_card(
        "The Dominick Seven",
        "<p>Before you save, let's check the rule against the seven commitments "
        "Dominick names as the spine of a healthy Catholic family life. A ⚠️ "
        "doesn't mean your rule is wrong — it means we couldn't find the data "
        "yet. Click <em>Fix</em> to jump back and add it, or move on if it "
        "genuinely doesn't apply to your season.</p>",
        key="sec13_intro",
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
    return _section_chrome(14, "Seven Commitments Check",
        "How does your rule line up with the Dominick seven? Fix any gaps, or move on.",
        body, mode, progress, lucy_visible=True)


# ── §14 finalize-save ───────────────────────────────────────────────────────

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
    Returns a dict of {target: status_str} for the §14 receipt view."""
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

    # ── Fix 4: read §14 review-card answers up front so each day template
    # can be stamped with what Lauren explicitly accepted / wants to
    # modify / chose to skip. "accept" is the only value that imports
    # downstream meaning; the others are recorded for the audit trail.
    sec14_pre        = data.get("section_15") or {}
    review_answers   = {
        "multitasking":  (sec14_pre.get("review_multi") or "").strip(),
        "developmental": (sec14_pre.get("review_dev")   or "").strip(),
        "schedule_opt":  (sec14_pre.get("review_sched") or "").strip(),
    }
    accepted_reviews = sorted(k for k, v in review_answers.items() if v == "accept")

    # 1) day_templates with backup
    try:
        backup_dir = os.path.join(DAY_TEMPLATE_DIR, f"_backup_{stamp}")
        os.makedirs(backup_dir, exist_ok=True)
        written = 0
        for day in _TIMELINE_DAYS:
            placements = (data.get("section_13") or {}).get(f"placements_{day}") or {}
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
                # Fix 4: stamp accepted review-card guidance into the
                # day template so downstream readers (today view,
                # gradebook, etc.) can react to it.
                _day_payload = {
                    "weekday": day,
                    "grid":    grid,
                    "frol_meta": {
                        "finalized_at":     stamp,
                        "review_answers":   review_answers,
                        "accepted_reviews": accepted_reviews,
                    },
                }
                with open(src, "w", encoding="utf-8") as f:
                    json.dump(_day_payload, f, indent=2, ensure_ascii=False)
                written += 1
        receipt["day_templates"] = f"Backed up to {os.path.basename(backup_dir)}; wrote {written} day(s)."
        # Fix 4: report the review-card answers in the receipt so Lauren
        # sees what got applied on the §14 success panel.
        receipt["reviews"] = (
            "; ".join(f"{_k}={_v or '(none)'}" for _k, _v in review_answers.items())
            + (f"  →  applied: {', '.join(accepted_reviews)}" if accepted_reviews else "")
        )
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


def render_section_14(progress: dict, mode: str) -> str:
    """V2 §14 — AI Review + Save. Three review cards (Multitasking /
    Developmental / Schedule optimization) shown as Accept / Modify / Skip,
    plus the Save button that runs finalize_v2()."""
    sec14 = (progress.get("data", {}) or {}).get("section_15", {}) or {}
    receipt = sec14.get("receipt") or {}
    finalized = bool(progress.get("finalized_at"))

    refl = render_reflection_card(
        "Before we save",
        "<p>Three quick AI-generated reviews of your rule, each as a card you "
        "can Accept, Modify, or Skip. None of them change your rule on their "
        "own — they're starting points to think with.</p>",
        key="sec14_intro",
        attribution="— Concept: Dominick's iterative-rule methodology",
    )

    # Heuristic review cards (no LLM call needed for these — they read the
    # data structure and produce specific observations).
    items = _commitments_status(progress)
    warn_count = sum(1 for it in items if it["status"] == "warn")
    members = _v2_members(progress)
    person_count = len([m for m in members if isinstance(m, dict) and m.get("name")])
    s12 = (progress.get("data", {}) or {}).get("section_13", {}) or {}
    placed_days = sum(1 for d in _TIMELINE_DAYS if (s12.get(f"placements_{d}") or {}))

    def _review_card(title: str, body: str, key: str) -> str:
        current = sec14.get(f"review_{key}", "")
        opts = [("accept", "Accept", "#7fa686"), ("modify", "Modify", "#c89c4a"), ("skip", "Skip", "#8a8a8a")]
        btns = ""
        for v, lab, color in opts:
            checked = "checked" if current == v else ""
            btns += (
                f'<label style="display:inline-flex;align-items:center;gap:6px;'
                f'background:#fff;border:1px solid {color}77;color:{color};border-radius:6px;'
                f'padding:6px 14px;margin-right:6px;font-weight:700;cursor:pointer;font-size:0.86em;">'
                f'<input type="radio" data-step="15" data-key="review_{escape(key, quote=True)}" '
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
        f"block for him in §12.</p>"
    )
    sched_body = (
        f"<p>You placed activities on <strong>{placed_days}</strong> of 7 days "
        f"in §12. You have <strong>{warn_count}</strong> commitment(s) "
        f"flagged ⚠️ in §13. The biggest schedule risk is back-to-back blocks "
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

    # ── Phase E: three save actions ────────────────────────────────────────
    # 1. Preview this week  — write to data/day_templates_preview/
    # 2. Save permanently   — back up + write to data/day_templates/
    # 3. Keep existing      — just mark wizard finalized, write nothing
    preview_on = s15_preview_active()
    _mesc      = escape(mode, quote=True)

    preview_banner = ""
    if preview_on:
        preview_banner = """
          <div style="background:#fff7e0;border:1px solid #e7c66a;border-left:4px solid #d99a16;
                      border-radius:10px;padding:12px 16px;margin:10px 0;">
            <div style="font-weight:700;color:#8a5a00;margin-bottom:4px;">
              🟡 Preview is live
            </div>
            <div style="font-size:0.9em;color:#555;">
              Your home page is showing the preview schedule. Use the buttons
              below to keep it permanently or discard it.
            </div>
          </div>
        """

    if not finalized:
        save_btn = f"""
          {preview_banner}
          <div style="margin-top:18px;display:flex;flex-direction:column;gap:10px;
                      max-width:520px;margin-left:auto;margin-right:auto;">

            <form method="POST" action="/frol-wizard">
              <input type="hidden" name="action"  value="frol_s15_preview">
              <input type="hidden" name="section" value="15">
              <input type="hidden" name="mode"    value="{_mesc}">
              <button type="submit" class="frol-btn"
                      style="background:#d99a16;color:#fff;border-radius:8px;
                             padding:12px 18px;font-weight:700;font-size:1em;
                             border:none;cursor:pointer;width:100%;">
                👀 Preview this week
              </button>
              <p class="frol-help" style="margin:6px 0 0;font-size:0.84em;color:#666;">
                Writes a non-destructive preview. Your home page will show the
                new schedule with Keep / Discard buttons.
              </p>
            </form>

            <form method="POST" action="/frol-wizard">
              <input type="hidden" name="action"  value="frol_s15_save">
              <input type="hidden" name="section" value="15">
              <input type="hidden" name="mode"    value="{_mesc}">
              <button type="submit" class="frol-btn"
                      style="background:#4a6fa5;color:#fff;border-radius:8px;
                             padding:14px 22px;font-weight:700;font-size:1.05em;
                             border:none;cursor:pointer;width:100%;"
                      onclick="return confirm('Save permanently? Your current day templates will be backed up.');">
                💾 Save permanently
              </button>
              <p class="frol-help" style="margin:6px 0 0;font-size:0.84em;color:#666;">
                Backs up your current day templates, then writes the new
                weekday / Saturday / Sunday / John-traveling schedules.
              </p>
            </form>

            <form method="POST" action="/frol-wizard">
              <input type="hidden" name="action"  value="frol_s15_keep">
              <input type="hidden" name="section" value="15">
              <input type="hidden" name="mode"    value="{_mesc}">
              <button type="submit" class="frol-btn"
                      style="background:#f3f4f6;color:#444;border-radius:8px;
                             padding:10px 16px;font-weight:600;font-size:0.95em;
                             border:1px solid #d1d5db;cursor:pointer;width:100%;">
                Keep my existing schedule
              </button>
              <p class="frol-help" style="margin:6px 0 0;font-size:0.84em;color:#666;">
                Marks the wizard complete without changing your day templates.
              </p>
            </form>

            {_render_save_seasonal_card()}
          </div>
        """
    else:
        save_btn = f"""
          {preview_banner}
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
        key="sec14_closing",
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
    return _section_chrome(15, "AI Review &amp; Save",
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
        # Phase C insertion: §11 is the new Holiday & Feast Day page.
        # Old §11..§14 shifted to §12..§15. Function names were kept
        # to keep diffs small; only their dispatch slots moved.
        11: render_section_11_holidays,
        12: render_section_11,   # old "duration picker" — now §12
        13: render_section_12,   # old "Build Your Day"  — now §13
        14: render_section_13,   # old "Commitments"     — now §14
        15: render_section_14,   # old "AI Review"       — now §15
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

    # Resources section — recommended reading that inspires the wizard.
    resources_html = """
      <div style="margin:24px auto 0;max-width:620px;text-align:left;">
        <div style="font-size:0.78em;color:#7d7d7d;text-transform:uppercase;
                    letter-spacing:0.06em;font-weight:700;margin-bottom:10px;
                    text-align:center;">
          Resources
        </div>
        <div style="background:#fbf7ef;border:1px solid #ead9b8;border-left:3px solid #c89c4a;
                    border-radius:10px;padding:12px 14px;">
          <div style="display:flex;align-items:baseline;gap:8px;">
            <span style="font-size:1.05em;">&#128218;</span>
            <span style="font-weight:700;color:#7d5a1f;">A Plan for Joy in the Home</span>
          </div>
          <div style="font-size:0.85em;color:#5a4520;margin-top:4px;line-height:1.45;">
            by Laura Dominick &mdash; the framework that inspired the seven
            commitments. A gentle, encouraging guide to ordering family life
            around joy.
          </div>
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

    upcoming_card_html = _render_landing_seasonal_awareness_card()
    library_html = _render_seasonal_library_section()
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
        {upcoming_card_html}
        {resources_html}
        {resume_html}
        <div style="display:flex;gap:14px;justify-content:center;
                    flex-wrap:wrap;margin-top:18px;">
          {lucy_btn}
          {self_btn}
        </div>
        <p style="margin-top:30px;font-size:0.85em;color:#7d7d7d;">
          A few short sections · Auto-saves as you go · About 15&ndash;20 minutes
        </p>
        {library_html}
        {lucy_intro_html}
        {companions_html}
      </div>
    """


# ── Phase F: seasonal library helpers ────────────────────────────────────────
def _render_save_seasonal_card() -> str:
    """The §15 save-with-season-label card. Lives below the three save
    buttons. Dropdown pre-selects the upcoming season."""
    from render_seasons import SEASON_LABELS as _SL, upcoming_season as _us
    from datetime import date as _date
    nxt = _us(_date.today()) or {}
    pre_label = nxt.get("label") or _SL[0]
    pre_year  = nxt.get("year") or _date.today().year
    opts = []
    for lab in _SL:
        sel = " selected" if lab == pre_label else ""
        opts.append(f'<option value="{escape(lab, quote=True)}"{sel}>{escape(lab)}</option>')
    days_blurb = ""
    if nxt:
        _dn = nxt.get("days_until", 0)
        if _dn == 0:
            days_blurb = " (begins today)"
        elif _dn == 1:
            days_blurb = " (begins tomorrow)"
        else:
            days_blurb = f" (in {int(_dn)} days)"
    return f"""
      <div style="background:#f3eef7;border:1px solid #d8c8e6;
                  border-left:4px solid #4a235a;border-radius:10px;
                  padding:14px 16px;margin-top:14px;">
        <div style="font-weight:700;color:#4a235a;margin-bottom:6px;">
          📚 Save this rule to your seasonal library
        </div>
        <div style="font-size:0.86em;color:#555;margin-bottom:10px;">
          Tag this snapshot with a season so you can return to it next year.
          We've pre-selected your upcoming season{escape(days_blurb)}.
        </div>
        <form method="POST" action="/frol-save-seasonal"
              style="display:flex;flex-direction:column;gap:8px;">
          <label style="font-size:0.85em;color:#4a235a;font-weight:600;">
            Season label
            <select name="season_label"
                    style="margin-left:8px;padding:6px 10px;border-radius:6px;
                           border:1px solid #c8b3d8;font-size:0.92em;">
              {"".join(opts)}
            </select>
          </label>
          <label style="font-size:0.85em;color:#4a235a;font-weight:600;">
            Year
            <input type="number" name="year" value="{int(pre_year)}"
                   min="2020" max="2099"
                   style="margin-left:8px;width:80px;padding:6px 10px;
                          border-radius:6px;border:1px solid #c8b3d8;font-size:0.92em;">
          </label>
          <textarea name="notes" rows="2" placeholder="Notes for next year (optional)…"
                    style="padding:8px 10px;border-radius:6px;border:1px solid #c8b3d8;
                           font-size:0.9em;font-family:inherit;resize:vertical;"></textarea>
          <button type="submit"
                  style="background:#4a235a;color:#fff;border:none;
                         border-radius:8px;padding:10px 16px;font-weight:700;
                         font-size:0.95em;cursor:pointer;">
            📚 Save to seasonal library
          </button>
        </form>
      </div>
    """


def _render_landing_seasonal_awareness_card() -> str:
    """Phase F: on the wizard landing, show a Marian-blue card when an
    upcoming season is within 14 days AND a *previous-year* saved
    schedule (year < upcoming year) exists for that label."""
    try:
        from render_seasons import upcoming_season as _us, migrate_label as _ml
        from datetime import date as _date
        from data_helpers import load_seasonal_schedules as _lss
        nxt = _us(_date.today(), window_days=14)
        if not nxt:
            return ""
        label = nxt["label"]
        upcoming_year = int(nxt["year"])
        matches = [
            e for e in _lss()
            if _ml(e.get("season_label")) == label
            and int(e.get("year") or 0) < upcoming_year
        ]
        if not matches:
            return ""
        matches.sort(key=lambda e: e.get("year", 0), reverse=True)
        latest = matches[0]
        _olbl = escape(label)
        _yr   = int(latest.get("year") or 0)
        _dn   = int(nxt.get("days_until") or 0)
        _id   = escape(str(latest.get("id") or ""), quote=True)
        when  = "today" if _dn == 0 else ("tomorrow" if _dn == 1 else f"in {_dn} days")
        return f"""
          <div style="background:linear-gradient(135deg,#e6edf7,#d6e1f0);
                      border:1px solid #b3c5e0;border-left:4px solid #2563eb;
                      border-radius:12px;padding:16px 20px;margin:18px auto 0;
                      max-width:620px;text-align:left;">
            <div style="font-weight:700;color:#1e3a8a;font-size:1.02em;
                        margin-bottom:6px;">
              🗓 {_olbl} starts {escape(when)}
            </div>
            <div style="font-size:0.9em;color:#33507e;line-height:1.45;
                        margin-bottom:10px;">
              You have a saved schedule from {_yr}. Want to start with last
              year's rhythm and edit from there?
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
              <a href="/frol-seasonal-view?id={_id}"
                 style="background:#fff;color:#1e3a8a;border:1px solid #2563eb;
                        border-radius:8px;padding:8px 14px;text-decoration:none;
                        font-weight:700;font-size:0.88em;">View</a>
              <form method="POST" action="/frol-seasonal-use" style="margin:0;">
                <input type="hidden" name="id" value="{_id}">
                <button type="submit"
                        style="background:#2563eb;color:#fff;border:none;
                               border-radius:8px;padding:8px 14px;font-weight:700;
                               font-size:0.88em;cursor:pointer;">
                  Use as starting point
                </button>
              </form>
            </div>
          </div>
        """
    except Exception:
        return ""


def _render_seasonal_library_section() -> str:
    """Phase F: list every saved seasonal schedule with View + Use buttons."""
    try:
        from data_helpers import load_seasonal_schedules as _lss
        entries = _lss()
    except Exception:
        entries = []
    if not entries:
        return """
          <div style="margin:32px auto 0;max-width:620px;text-align:left;">
            <div style="font-size:0.78em;color:#7d7d7d;text-transform:uppercase;
                        letter-spacing:0.06em;font-weight:700;margin-bottom:10px;
                        text-align:center;">Seasonal library</div>
            <div style="background:#f7f5fb;border:1px dashed #cdb6e1;
                        border-radius:10px;padding:14px 16px;color:#6b5a82;
                        font-size:0.88em;line-height:1.5;text-align:center;">
              No saved schedules yet. Finish a rule and save it from §15
              to build your seasonal library.
            </div>
          </div>
        """
    entries_sorted = sorted(
        entries,
        key=lambda e: (e.get("year", 0), e.get("saved_at", "")),
        reverse=True,
    )
    cards = []
    for e in entries_sorted:
        _eid   = escape(str(e.get("id") or ""), quote=True)
        _lab   = escape(str(e.get("season_label") or ""))
        _yr    = int(e.get("year") or 0)
        _saved = escape(str(e.get("saved_at") or "")[:10])
        _notes = escape((e.get("notes") or "")[:140])
        _acount = len(e.get("activities_snapshot") or [])
        _dcount = len(e.get("day_templates_snapshot") or {})
        cards.append(f"""
          <div style="background:#fff;border:1px solid #d8c8e6;border-left:3px solid #4a235a;
                      border-radius:10px;padding:12px 14px;display:flex;
                      flex-direction:column;gap:6px;">
            <div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px;">
              <span style="font-weight:700;color:#4a235a;">{_lab} {_yr}</span>
              <span style="font-size:0.78em;color:#888;">saved {_saved}</span>
            </div>
            <div style="font-size:0.82em;color:#666;">
              {_acount} activities · {_dcount} day templates
            </div>
            {f'<div style="font-size:0.85em;color:#5a4a78;font-style:italic;">{_notes}</div>' if _notes else ''}
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:4px;">
              <a href="/frol-seasonal-view?id={_eid}"
                 style="background:#fff;color:#4a235a;border:1px solid #4a235a;
                        border-radius:6px;padding:5px 10px;text-decoration:none;
                        font-weight:600;font-size:0.82em;">View</a>
              <form method="POST" action="/frol-seasonal-use" style="margin:0;">
                <input type="hidden" name="id" value="{_eid}">
                <button type="submit"
                        style="background:#4a235a;color:#fff;border:none;
                               border-radius:6px;padding:5px 10px;font-weight:600;
                               font-size:0.82em;cursor:pointer;">
                  Use as starting point
                </button>
              </form>
              <form method="POST" action="/frol-seasonal-delete" style="margin:0;"
                    onsubmit="return confirm('Delete this saved schedule?');">
                <input type="hidden" name="id" value="{_eid}">
                <button type="submit"
                        style="background:transparent;color:#a33;border:none;
                               text-decoration:underline;font-size:0.82em;
                               cursor:pointer;padding:5px 4px;">Delete</button>
              </form>
            </div>
          </div>
        """)
    return f"""
      <div style="margin:32px auto 0;max-width:620px;text-align:left;">
        <div style="font-size:0.78em;color:#7d7d7d;text-transform:uppercase;
                    letter-spacing:0.06em;font-weight:700;margin-bottom:10px;
                    text-align:center;">Seasonal library</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
                    gap:10px;">
          {''.join(cards)}
        </div>
      </div>
    """


def render_seasonal_view_page(entry_id: str) -> str:
    """Phase F: read-only snapshot view at /frol-seasonal-view?id=…"""
    from data_helpers import get_seasonal_schedule as _gss
    entry = _gss(entry_id)
    if not entry:
        return """<!doctype html><html><head><title>Not found</title></head>
          <body style="font-family:sans-serif;padding:40px;text-align:center;">
            <h2>Saved schedule not found.</h2>
            <p><a href="/frol-wizard">&larr; Back to Rule of Life</a></p>
          </body></html>"""
    acts = entry.get("activities_snapshot") or []
    dts  = entry.get("day_templates_snapshot") or {}
    rows = []
    for a in acts:
        if not isinstance(a, dict):
            continue
        rows.append(
            "<tr>"
            f"<td style='padding:4px 8px;border-bottom:1px solid #eee;'>{escape(str(a.get('time') or a.get('start_time') or ''))}</td>"
            f"<td style='padding:4px 8px;border-bottom:1px solid #eee;'>{escape(str(a.get('name') or a.get('activity_name') or ''))}</td>"
            f"<td style='padding:4px 8px;border-bottom:1px solid #eee;'>{escape(str(a.get('duration_min') or ''))}</td>"
            f"<td style='padding:4px 8px;border-bottom:1px solid #eee;'>{escape(', '.join(a.get('who') or []))}</td>"
            "</tr>"
        )
    dt_summary = "".join(
        f"<li><strong>{escape(stem)}</strong>: {len(items) if isinstance(items, list) else '—'} slots</li>"
        for stem, items in sorted(dts.items())
    )
    _eid_esc = escape(str(entry.get("id") or ""), quote=True)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{escape(entry.get('season_label',''))} {int(entry.get('year') or 0)} — Saved Schedule</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{font-family:-apple-system,sans-serif;background:#f7f5fb;color:#1a1a1a;margin:0;padding:24px;}}
.wrap{{max-width:760px;margin:0 auto;background:#fff;border-radius:12px;
       padding:24px;border:1px solid #d8c8e6;}}
h1{{color:#4a235a;font-size:1.5em;margin:0 0 6px;}}
.sub{{color:#666;font-size:0.9em;margin-bottom:18px;}}
table{{width:100%;border-collapse:collapse;font-size:0.9em;}}
th{{text-align:left;padding:6px 8px;background:#f3eef7;color:#4a235a;
     border-bottom:2px solid #d8c8e6;}}
.btn{{background:#4a235a;color:#fff;border:none;border-radius:8px;
      padding:10px 16px;font-weight:700;cursor:pointer;text-decoration:none;
      display:inline-block;}}
.btn-ghost{{background:#fff;color:#4a235a;border:1px solid #4a235a;}}
</style></head>
<body><div class="wrap">
  <a href="/frol-wizard" style="color:#4a235a;">&larr; Back to Rule of Life</a>
  <h1>{escape(entry.get('season_label',''))} {int(entry.get('year') or 0)}</h1>
  <div class="sub">
    Saved {escape(str(entry.get('saved_at') or '')[:19])}
  </div>
  {f'<p style="background:#f3eef7;border-left:3px solid #4a235a;padding:10px 14px;border-radius:6px;color:#4a235a;font-style:italic;">{escape(entry.get("notes",""))}</p>' if entry.get('notes') else ''}
  <h3 style="color:#4a235a;margin-top:18px;">Day templates</h3>
  <ul style="margin:8px 0 18px 22px;color:#555;line-height:1.6;">{dt_summary or '<li>(none)</li>'}</ul>
  <h3 style="color:#4a235a;">Activities ({len(acts)})</h3>
  <table>
    <thead><tr><th>Time</th><th>Activity</th><th>Min</th><th>Who</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan=4 style="padding:12px;color:#999;">No activities recorded.</td></tr>'}</tbody>
  </table>
  <div style="margin-top:20px;display:flex;gap:8px;flex-wrap:wrap;">
    <form method="POST" action="/frol-seasonal-use" style="margin:0;">
      <input type="hidden" name="id" value="{_eid_esc}">
      <button type="submit" class="btn">Use as starting point</button>
    </form>
    <form method="POST" action="/frol-overlay-set" style="margin:0;">
      <input type="hidden" name="id" value="{_eid_esc}">
      <button type="submit" class="btn btn-ghost">Overlay on current grid</button>
    </form>
  </div>
</div></body></html>"""


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

    _completed_set = set(progress.get("completed_steps", []) or [])
    _jump_mode = escape(mode or progress.get("mode") or "structured", quote=True)
    _jump_items = []
    for (_idx, _slug, _t, _sub) in V2_SECTIONS:
        _check  = "✓ " if _idx in _completed_set else ""
        _is_cur = (_idx == cur)
        _bg     = "#fff4d6" if _is_cur else "transparent"
        _weight = "700" if _is_cur else "500"
        _color  = "#7a4ea3" if _is_cur else "#222"
        _jump_items.append(
            f'<a href="/frol-wizard?step={_idx}&mode={_jump_mode}" '
            f'style="display:block;padding:8px 12px;text-decoration:none;'
            f'background:{_bg};color:{_color};font-weight:{_weight};'
            f'border-bottom:1px solid #f1ecde;font-size:0.92em;">'
            f'<span style="display:inline-block;width:28px;color:#888;">{_idx}.</span>'
            f'{_check}{escape(_t)}</a>'
        )
    _cur_label = f"Section {cur} of {V2_TOTAL_SECTIONS}" if cur else f"Start · {V2_TOTAL_SECTIONS} sections"
    _jump_popover = (
        f'<details class="frol-section-jump" '
        f'style="position:relative;display:inline-block;">'
        f'<summary style="cursor:pointer;list-style:none;user-select:none;'
        f'padding:2px 8px;border-radius:6px;background:#f5efe0;'
        f'border:1px solid #e2d6b8;font-size:0.92em;color:#5a4520;">'
        f'Rule of Life · {_cur_label} &#9662;</summary>'
        f'<div style="position:absolute;top:100%;left:0;margin-top:6px;'
        f'min-width:280px;max-height:60vh;overflow-y:auto;background:#fff;'
        f'border:1px solid #d8cdb0;border-radius:10px;'
        f'box-shadow:0 6px 20px rgba(0,0,0,0.12);z-index:1000;">'
        f'{"".join(_jump_items)}</div></details>'
    )
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Rule of Life Wizard</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{WIZARD_CSS}
.frol-section-jump > summary::-webkit-details-marker {{ display:none; }}
.frol-section-jump > summary::marker {{ content:""; }}
</style></head><body>
<div class="frol-wrap">
  <div class="frol-top">
    <a href="/">&larr; Home</a>
    {_jump_popover}
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
    finalized = bool(p.get("finalized_at"))

    # ── Phase E: preview-mode banner (highest priority) ────────────────────
    # When a preview is live, show Keep / Discard right on the dashboard.
    if s15_preview_active():
        return """
          <div class="tb-card" data-frol-preview="1"
               style="background:#fff7e0;border:1px solid #e7c66a;
                      border-left:4px solid #d99a16;border-radius:12px;
                      padding:14px 16px;margin:12px 0;">
            <div style="font-weight:700;color:#8a5a00;margin-bottom:4px;">
              🟡 Previewing your new Rule of Life
            </div>
            <div style="font-size:0.9em;color:#444;margin-bottom:10px;">
              The schedule shown below is a preview from the wizard. Keep it
              to make it your everyday schedule, or discard to return to your
              previous Rule of Life.
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
              <form method="POST" action="/preview-keep" style="margin:0;">
                <button type="submit"
                        style="background:#2e7d4f;color:#fff;border:none;
                               border-radius:8px;padding:8px 16px;font-weight:700;
                               font-size:0.9em;cursor:pointer;">
                  ✅ Keep this schedule
                </button>
              </form>
              <form method="POST" action="/preview-discard" style="margin:0;"
                    onsubmit="return confirm('Discard the preview?');">
                <button type="submit"
                        style="background:#fff;color:#a33;border:1px solid #a33;
                               border-radius:8px;padding:8px 16px;font-weight:700;
                               font-size:0.9em;cursor:pointer;">
                  Discard preview
                </button>
              </form>
            </div>
          </div>
        """

    # ── Phase E: tiny green-check badge once §15 has saved permanently ─────
    if finalized:
        return """
          <div class="tb-card" data-frol-finalized="1"
               style="background:#eef6f0;border:1px solid #cde0d2;
                      border-left:4px solid #2e7d4f;border-radius:10px;
                      padding:8px 14px;margin:10px 0;font-size:0.85em;
                      color:#2e5d3b;display:flex;align-items:center;
                      justify-content:space-between;gap:8px;">
            <span><strong>✓</strong> Rule of Life saved.</span>
            <a href="/frol-wizard" style="color:#2e5d3b;text-decoration:underline;
                                           font-size:0.85em;">Edit</a>
          </div>
        """

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
