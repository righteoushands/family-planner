"""
render_curriculum.py — MODG Curriculum Importer page.
Lets Lauren paste a full-year subject plan (all weeks at once) and
stores it so the school tab automatically shows the right week.
"""
import json as _json
import os as _os
import re as _re
import urllib.request as _req

from data_helpers import (
    load_curriculum, save_curriculum,
    get_curriculum_week, get_curriculum_subjects,
)
from daily_schedule_engine import CHILDREN

_APP_SETTINGS_FILE = "data/app_settings.json"


def _load_app_settings() -> dict:
    try:
        if _os.path.exists(_APP_SETTINGS_FILE):
            return _json.load(open(_APP_SETTINGS_FILE))
    except Exception:
        pass
    return {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_openai_key() -> str:
    """Read OPENAI_API_KEY from environment."""
    return _os.environ.get("OPENAI_API_KEY", "").strip()


def _call_gpt(system: str, user: str, max_tokens: int = 2000) -> tuple:
    """
    Call OpenAI GPT-4o-mini and return (text, error_msg).
    On success: (text, "")
    On failure: ("", error description)
    """
    import urllib.error as _uerr
    api_key = _get_openai_key()
    if not api_key:
        return "", "OPENAI_API_KEY is not set."
    payload = {
        "model": "gpt-4o-mini",
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    }
    try:
        req = _req.Request(
            "https://api.openai.com/v1/chat/completions",
            data=_json.dumps(payload).encode(),
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with _req.urlopen(req, timeout=45) as resp:
            result = _json.loads(resp.read())
        return result["choices"][0]["message"]["content"].strip(), ""
    except _uerr.HTTPError as e:
        body = e.read()[:300]
        return "", f"OpenAI error {e.code}: {body}"
    except Exception as e:
        return "", str(e)


# ── Parse MODG paste ──────────────────────────────────────────────────────────


def _parse_modg_locally(raw_text: str) -> dict:
    """
    Fast regex parser for MODG's predictable 'Week N' structure.
    No API call needed. Returns {week_str: assignment_text} or {} if
    fewer than 3 week boundaries are found.
    """
    # Match "Week" (case-insensitive) + optional colon/space + digits
    # Allow it anywhere on a line — not just at the start
    week_re = _re.compile(
        r'(?i)(?:^|\n)[^\n]*?(?<!\w)week\s*:?\s*(\d+)\b',
        _re.MULTILINE,
    )
    matches = list(week_re.finditer(raw_text))
    if len(matches) < 3:
        return {}

    result = {}
    for i, m in enumerate(matches):
        week_num = str(int(m.group(1)))
        # Everything from end of "Week N" match to start of next week
        content_raw = raw_text[m.end() : (matches[i + 1].start() if i + 1 < len(matches) else len(raw_text))]

        first_nl = content_raw.find('\n')
        if first_nl == -1:
            # Single-line: "Week N: Lesson text here" — strip leading separators
            chunk = _re.sub(r'^[\s,\-:;.]+', '', content_raw).strip()
        else:
            rest_of_header = content_raw[:first_nl]
            after_header   = content_raw[first_nl + 1:]
            # Keep inline content only if it's meaningful (not just ", Day: 1-4")
            inline = _re.sub(r'^[\s,\-:;.]+', '', rest_of_header).strip()
            # Strip "Day: 1-4", "Day 1:", "Day 1-5" type metadata patterns
            inline = _re.sub(r'(?i)\bday\s*[:\s]*\d+(?:\s*[-–]\s*\d+)?[\s,;.]*', '', inline).strip()
            inline = _re.sub(r'^[\s,\-:;.]+', '', inline).strip()
            chunk = ((inline + ' ') if len(inline) > 8 else '') + after_header

        # Strip "Day N:" prefixes and collapse whitespace
        chunk = _re.sub(r'(?im)^\s*day\s*\d+[\s\-:]*', ' ', chunk)
        chunk = _re.sub(r'\s+', ' ', chunk).strip()

        if len(chunk) > 5:
            result[week_num] = chunk

    return result


def _parse_with_ai(subject: str, raw_text: str) -> tuple:
    """AI fallback — only called when regex finds < 3 weeks."""
    system = (
        "You are a curriculum parser for a Catholic homeschool family using "
        "Mother of Divine Grace (MODG) curriculum. "
        "The user will paste the full-year syllabus for a single subject. "
        "Your job is to extract the assignments week by week and return ONLY valid JSON. "
        'Format: {"1": "assignment for week 1", "2": "assignment for week 2", ...} '
        "Use the week number as the key (string). "
        "Keep text concise but complete — preserve lesson numbers, page numbers, exercise labels. "
        "If multiple days exist in a week, combine them into one string. "
        "If the week number is unclear, infer it from the sequence. "
        "Output ONLY the JSON object, no explanation."
    )
    user = f"Subject: {subject}\n\nPaste from MODG planner:\n\n{raw_text}"

    raw, err = _call_gpt(system, user, max_tokens=3000)
    if err:
        return {}, err
    if not raw:
        return {}, "AI returned empty response."

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        parsed = _json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}, ""
    except Exception as e:
        return {}, f"Could not read AI output: {e}. Raw: {raw[:200]}"
    return {}, "Unexpected AI response format."


def parse_modg_paste(subject: str, raw_text: str) -> tuple:
    """
    Parse a MODG full-year subject paste into {week_str: assignment_text}.
    Tries fast local regex first; falls back to AI only if that fails.
    Returns (weeks_dict, error_str).
    """
    # 1. Try instant local parse (no network, no timeout)
    local = _parse_modg_locally(raw_text)
    if len(local) >= 3:
        return local, ""

    # 2. AI fallback for unusual formats
    return _parse_with_ai(subject, raw_text)


# ── Page render ───────────────────────────────────────────────────────────────

def render_curriculum_page() -> str:
    cur = load_curriculum()
    current_week = int(cur.get("current_week", 1))
    api_key = _get_openai_key()
    school_children = ["JP", "Joseph", "Michael"]

    # Build per-child summary of imported subjects
    child_sections = ""
    for child in school_children:
        subjects = cur.get(child, {})
        if subjects:
            rows = ""
            for subj, weeks in sorted(subjects.items()):
                week_count = len(weeks)
                this_week = weeks.get(str(current_week), "")
                preview = (this_week[:80] + "…") if len(this_week) > 80 else this_week
                preview_html = (
                    f'<span class="cur-preview">{preview}</span>'
                    if preview else
                    '<span class="cur-no-assign">— no assignment this week —</span>'
                )
                rows += f"""
                <tr>
                  <td class="cur-subj">{subj}</td>
                  <td class="cur-weeks">{week_count} wks</td>
                  <td class="cur-this-week">{preview_html}</td>
                  <td class="cur-actions">
                    <button class="cur-del-btn" onclick="deleteSubject('{child}','{subj}')">✕</button>
                  </td>
                </tr>"""
            child_sections += f"""
            <div class="cur-child-block">
              <h3 class="cur-child-name">{child}</h3>
              <table class="cur-table">
                <thead><tr>
                  <th>Subject</th><th>Weeks</th>
                  <th>Week {current_week} Assignment</th><th></th>
                </tr></thead>
                <tbody>{rows}</tbody>
              </table>
            </div>"""
        else:
            child_sections += f"""
            <div class="cur-child-block">
              <h3 class="cur-child-name">{child}</h3>
              <p class="cur-empty">No curriculum imported yet.</p>
            </div>"""

    no_key_warning = "" if api_key else """
    <div class="cur-warning">
      ⚠ OPENAI_API_KEY not found — contact your Replit admin to add the secret before importing.
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Curriculum Importer — Sancta Familia</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Georgia, serif; background: #fdf8f2; color: #3b2a1a; min-height: 100vh; }}
  .cur-header {{ background: #7c3aed; color: #fff; padding: 18px 20px; display: flex;
                 align-items: center; gap: 14px; }}
  .cur-header a {{ color: #e9d5ff; text-decoration: none; font-size: 0.85em; }}
  .cur-header h1 {{ font-size: 1.3em; font-weight: normal; flex: 1; }}
  .cur-body {{ max-width: 780px; margin: 0 auto; padding: 20px 16px 60px; }}

  .cur-week-bar {{ background: #fff; border: 1px solid #e5d5c5; border-radius: 10px;
                   padding: 16px 20px; margin-bottom: 24px;
                   display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }}
  .cur-week-label {{ font-size: 1.05em; font-weight: bold; color: #7c3aed; flex: 1; }}
  .cur-week-note {{ font-size: 0.82em; color: #8b7355; }}
  .cur-week-ctrl {{ display: flex; align-items: center; gap: 8px; }}
  .cur-wbtn {{ background: #7c3aed; color: #fff; border: none; border-radius: 6px;
               padding: 6px 14px; cursor: pointer; font-size: 1em; }}
  .cur-wbtn:hover {{ background: #6d28d9; }}
  .cur-wnum {{ font-size: 1.3em; font-weight: bold; min-width: 30px; text-align: center; }}
  .cur-wset-form {{ display: flex; gap: 6px; align-items: center; }}
  .cur-wset-form input {{ width: 60px; padding: 5px 8px; border: 1px solid #c4a882;
                           border-radius: 6px; text-align: center; font-size: 0.95em; }}
  .cur-wset-btn {{ background: #e9d5ff; color: #5b21b6; border: 1px solid #c4b5fd;
                   border-radius: 6px; padding: 5px 12px; cursor: pointer; font-size: 0.85em; }}

  .cur-warning {{ background: #fff7ed; border: 1px solid #fcd34d; border-radius: 8px;
                  padding: 12px 16px; margin-bottom: 20px; font-size: 0.9em; color: #92400e; }}

  .cur-child-block {{ background: #fff; border: 1px solid #e5d5c5; border-radius: 10px;
                       padding: 16px 18px; margin-bottom: 18px; }}
  .cur-child-name {{ font-size: 1em; font-weight: bold; color: #5b21b6; margin-bottom: 12px; }}
  .cur-table {{ width: 100%; border-collapse: collapse; font-size: 0.88em; }}
  .cur-table th {{ text-align: left; padding: 6px 10px; border-bottom: 2px solid #e5d5c5;
                   color: #8b7355; font-weight: normal; font-size: 0.85em; }}
  .cur-table td {{ padding: 7px 10px; border-bottom: 1px solid #f0e8dc; vertical-align: top; }}
  .cur-subj {{ font-weight: bold; color: #3b2a1a; }}
  .cur-weeks {{ color: #9b8872; font-size: 0.85em; }}
  .cur-preview {{ color: #5a4432; font-style: italic; }}
  .cur-no-assign {{ color: #c4b5a0; font-style: italic; }}
  .cur-del-btn {{ background: none; border: 1px solid #e5c5c5; border-radius: 4px;
                  color: #dc6b6b; cursor: pointer; padding: 2px 7px; font-size: 0.85em; }}
  .cur-del-btn:hover {{ background: #fef2f2; }}
  .cur-empty {{ color: #b0a090; font-style: italic; font-size: 0.9em; }}

  .cur-import-card {{ background: #fff; border: 2px solid #c4b5fd; border-radius: 12px;
                       padding: 20px 20px 24px; margin-top: 28px; }}
  .cur-import-card h2 {{ font-size: 1.05em; color: #5b21b6; margin-bottom: 16px; }}
  .cur-form-row {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }}
  .cur-form-row label {{ font-size: 0.85em; color: #8b7355; display: block; margin-bottom: 4px; }}
  .cur-select, .cur-input {{ padding: 8px 12px; border: 1px solid #c4a882; border-radius: 7px;
                               font-size: 0.95em; background: #fdf8f2; width: 100%; }}
  .cur-field {{ flex: 1; min-width: 140px; }}
  .cur-paste-area {{ width: 100%; min-height: 180px; padding: 12px; border: 1px solid #c4a882;
                     border-radius: 8px; font-family: monospace; font-size: 0.82em;
                     background: #fdf8f2; resize: vertical; margin-bottom: 14px; }}
  .cur-hint {{ font-size: 0.8em; color: #9b8872; margin-bottom: 14px; line-height: 1.4; }}
  .cur-parse-btn {{ background: #7c3aed; color: #fff; border: none; border-radius: 8px;
                    padding: 10px 24px; font-size: 0.95em; cursor: pointer; }}
  .cur-parse-btn:hover {{ background: #6d28d9; }}
  .cur-parse-btn:disabled {{ background: #c4b5fd; cursor: wait; }}

  .cur-preview-section {{ display: none; margin-top: 18px; }}
  .cur-preview-section.visible {{ display: block; }}
  .cur-preview-section h3 {{ font-size: 0.95em; color: #5b21b6; margin-bottom: 10px; }}
  .cur-preview-table {{ width: 100%; border-collapse: collapse; font-size: 0.84em; }}
  .cur-preview-table th {{ text-align: left; padding: 5px 8px; background: #f5f0ff;
                            color: #5b21b6; border-bottom: 2px solid #c4b5fd; }}
  .cur-preview-table td {{ padding: 6px 8px; border-bottom: 1px solid #ede9f7; vertical-align: top; }}
  .cur-preview-table td:first-child {{ font-weight: bold; width: 60px; color: #7c3aed; }}
  .cur-save-btn {{ background: #16a34a; color: #fff; border: none; border-radius: 8px;
                   padding: 10px 24px; font-size: 0.95em; cursor: pointer; margin-top: 14px; }}
  .cur-save-btn:hover {{ background: #15803d; }}
  .cur-error {{ color: #dc2626; font-size: 0.88em; margin-top: 8px; }}
  .cur-success {{ color: #16a34a; font-size: 0.88em; margin-top: 8px; font-weight: bold; }}
  .cur-spinner {{ display: inline-block; margin-left: 8px; }}
</style>
</head>
<body>
<div class="cur-header">
  <a href="/settings">← Settings</a>
  <h1>📚 Curriculum Importer</h1>
  <span style="font-size:0.8em;opacity:0.8;">MODG full-year plans</span>
</div>

<div class="cur-body">

  {no_key_warning}

  <!-- Week Control -->
  <div class="cur-week-bar">
    <div>
      <div class="cur-week-label">School Week {current_week}</div>
      <div class="cur-week-note">The school tab shows this week's assignment for each imported subject.</div>
    </div>
    <div class="cur-week-ctrl">
      <button class="cur-wbtn" onclick="changeWeek(-1)">−</button>
      <span class="cur-wnum" id="weekDisplay">{current_week}</span>
      <button class="cur-wbtn" onclick="changeWeek(1)">+</button>
    </div>
    <div class="cur-wset-form">
      <input type="number" id="weekJump" min="1" max="40" placeholder="Wk #">
      <button class="cur-wset-btn" onclick="setWeek()">Go to week</button>
    </div>
  </div>

  <!-- Per-child tables -->
  {child_sections}

  <!-- Import Form -->
  <div class="cur-import-card">
    <h2>Import a Subject Plan</h2>
    <div class="cur-form-row">
      <div class="cur-field">
        <label>Child</label>
        <select class="cur-select" id="impChild">
          {''.join(f'<option value="{c}">{c}</option>' for c in school_children)}
        </select>
      </div>
      <div class="cur-field">
        <label>Subject name</label>
        <input class="cur-input" type="text" id="impSubject" placeholder="e.g. Latin, Math, Religion">
      </div>
    </div>
    <p class="cur-hint">
      In MODG's online planner, open a subject's full year view, then select all and copy (Ctrl+A → Ctrl+C).
      Paste it below — AI will extract each week's assignment automatically.
    </p>
    <textarea class="cur-paste-area" id="impPaste"
              placeholder="Paste the MODG syllabus for this subject here…"></textarea>
    <button class="cur-parse-btn" id="parseBtn" onclick="parseCurriculum()">
      Parse with AI
    </button>
    <div id="parseError" class="cur-error"></div>

    <div class="cur-preview-section" id="previewSection">
      <h3 id="previewTitle"></h3>
      <table class="cur-preview-table">
        <thead><tr><th>Week</th><th>Assignment</th></tr></thead>
        <tbody id="previewBody"></tbody>
      </table>
      <button class="cur-save-btn" onclick="saveCurriculum()">Save to Curriculum</button>
      <div id="saveStatus"></div>
    </div>
  </div>

</div>

<script>
let _parsedData = {{}};
let _currentWeek = {current_week};

function changeWeek(delta) {{
  const next = Math.max(1, _currentWeek + delta);
  _setWeekNum(next);
}}

function setWeek() {{
  const val = parseInt(document.getElementById('weekJump').value);
  if (val && val >= 1) _setWeekNum(val);
}}

function _setWeekNum(n) {{
  fetch('/curriculum-week', {{
    method: 'POST',
    headers: {{'Content-Type':'application/x-www-form-urlencoded'}},
    body: 'week=' + n
  }}).then(r => {{
    if (r.ok) {{ _currentWeek = n; location.reload(); }}
  }});
}}

async function parseCurriculum() {{
  const child   = document.getElementById('impChild').value.trim();
  const subject = document.getElementById('impSubject').value.trim();
  const paste   = document.getElementById('impPaste').value.trim();
  const errEl   = document.getElementById('parseError');
  errEl.textContent = '';
  if (!subject) {{ errEl.textContent = 'Enter a subject name.'; return; }}
  if (!paste)   {{ errEl.textContent = 'Paste the MODG syllabus first.'; return; }}

  const btn = document.getElementById('parseBtn');
  btn.disabled = true;
  btn.textContent = 'Parsing…';

  try {{
    const res = await fetch('/curriculum-parse', {{
      method: 'POST',
      headers: {{'Content-Type':'application/x-www-form-urlencoded'}},
      body: 'child=' + encodeURIComponent(child) +
            '&subject=' + encodeURIComponent(subject) +
            '&paste=' + encodeURIComponent(paste)
    }});
    const json = await res.json();
    if (json.error) {{ errEl.textContent = json.error; return; }}
    _parsedData = json.weeks || {{}};
    showPreview(child, subject, _parsedData);
  }} catch(e) {{
    errEl.textContent = 'Parse failed — check API key in Settings.';
  }} finally {{
    btn.disabled = false;
    btn.textContent = 'Parse with AI';
  }}
}}

function showPreview(child, subject, weeks) {{
  const section = document.getElementById('previewSection');
  const body    = document.getElementById('previewBody');
  const title   = document.getElementById('previewTitle');
  const keys    = Object.keys(weeks).sort((a,b) => parseInt(a)-parseInt(b));
  title.textContent = child + ' — ' + subject + ' (' + keys.length + ' weeks parsed)';
  body.innerHTML = keys.map(k =>
    '<tr><td>' + k + '</td><td>' + escHtml(weeks[k]) + '</td></tr>'
  ).join('');
  section.classList.add('visible');
  section.scrollIntoView({{behavior:'smooth', block:'nearest'}});
}}

async function saveCurriculum() {{
  const child   = document.getElementById('impChild').value.trim();
  const subject = document.getElementById('impSubject').value.trim();
  const status  = document.getElementById('saveStatus');
  status.textContent = '';
  if (!Object.keys(_parsedData).length) return;
  try {{
    const res = await fetch('/curriculum-save', {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{ child, subject, weeks: _parsedData }})
    }});
    if (res.ok) {{
      status.className = 'cur-success';
      status.textContent = '✓ Saved! Reloading…';
      setTimeout(() => location.reload(), 900);
    }} else {{
      status.className = 'cur-error';
      status.textContent = 'Save failed.';
    }}
  }} catch(e) {{
    status.className = 'cur-error';
    status.textContent = 'Save failed.';
  }}
}}

async function deleteSubject(child, subject) {{
  if (!confirm('Remove ' + subject + ' from ' + child + "'s curriculum?")) return;
  const res = await fetch('/curriculum-delete', {{
    method: 'POST',
    headers: {{'Content-Type':'application/x-www-form-urlencoded'}},
    body: 'child=' + encodeURIComponent(child) + '&subject=' + encodeURIComponent(subject)
  }});
  if (res.ok) location.reload();
}}

function escHtml(s) {{
  return String(s)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}}
</script>
</body>
</html>"""
