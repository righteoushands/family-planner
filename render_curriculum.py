"""
render_curriculum.py — Curriculum Management System
Four interconnected modules:
1. Curriculum Library - subjects, units, assignments, pacing
2. Reference Documents - PDF storage and organization  
3. Student Submissions - upload interface for boys
4. Grading Interface - review and feedback workflow
"""
import os
from data_helpers import (
    load_curriculum, save_curriculum,
    load_curriculum_library, save_curriculum_library, get_subject_by_id,
    get_assignments_for_student, load_student_submissions, get_submissions_for_grading,
    get_submissions_by_student, load_grading_history, load_curriculum_documents,
    add_student_submission, add_grade_record, add_curriculum_document, today_iso
)
from daily_schedule_engine import CHILDREN
from ui_helpers import render_nav_tabs, html_page, page_header


def _get_openai_key() -> str:
    """Return the OpenAI API key from the environment secret."""
    return os.environ.get("OPENAI_API_KEY", "").strip()


_SUBJECT_MINUTES = {
    "math": 45, "mathematics": 45, "algebra": 45, "geometry": 45,
    "latin": 30, "greek": 30,
    "history": 40, "science": 40,
    "english": 35, "writing": 35, "grammar": 30, "literature": 40,
    "religion": 30, "catechism": 30,
    "art": 30, "music": 30, "logic": 30,
}

def _recommended_minutes(subject: str) -> int:
    """Return a sensible default session length (minutes) for a subject."""
    key = subject.lower().strip()
    for name, mins in _SUBJECT_MINUTES.items():
        if name in key:
            return mins
    return 35

def render_curriculum_main():
    """Main curriculum dashboard with module navigation."""
    
    # Get summary stats
    library = load_curriculum_library()
    submissions = load_student_submissions()
    pending_reviews = len([s for s in submissions["submissions"] if s["status"] == "pending_review"])
    total_subjects = len(library["subjects"])
    
    tabs = [
        {"id": "library", "label": "📚 Curriculum Library", "url": "/curriculum-library"},
        {"id": "documents", "label": "📄 Reference Docs", "url": "/curriculum-docs"},
        {"id": "submissions", "label": "📤 Student Work", "url": "/submit-work"},
        {"id": "grading", "label": f"✅ Grading Queue ({pending_reviews})", "url": "/grading-queue"}
    ]
    
    nav_html = render_nav_tabs(tabs, "curriculum")
    
    return f"""
    <div class="curriculum-main">
        {nav_html}
        
        <div class="dashboard-overview">
            <div class="stat-cards">
                <div class="stat-card">
                    <h3>{total_subjects}</h3>
                    <p>Active Subjects</p>
                </div>
                <div class="stat-card">
                    <h3>{pending_reviews}</h3>
                    <p>Pending Reviews</p>
                </div>
                <div class="stat-card">
                    <h3>{len(submissions['submissions'])}</h3>
                    <p>Total Submissions</p>
                </div>
            </div>
            
            <div class="quick-actions">
                <h3>Quick Actions</h3>
                <a href="/curriculum-library/new-subject" class="btn btn-primary">➕ Add New Subject</a>
                <a href="/curriculum-docs/upload" class="btn btn-secondary">📁 Upload Document</a>
                <a href="/grading-queue" class="btn btn-accent">🔍 Review Work</a>
            </div>
            
            <div class="recent-activity">
                <h3>Recent Submissions</h3>
                {render_recent_submissions_widget()}
            </div>
        </div>
    </div>
    
    <style>
    .curriculum-main {{ margin: 20px; }}
    .dashboard-overview {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }}
    .stat-cards {{ display: flex; gap: 15px; }}
    .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; min-width: 100px; }}
    .stat-card h3 {{ margin: 0; font-size: 24px; color: #2c3e50; }}
    .stat-card p {{ margin: 5px 0 0 0; color: #7f8c8d; }}
    .quick-actions, .recent-activity {{ background: #fff; padding: 20px; border-radius: 8px; border: 1px solid #ddd; }}
    .quick-actions h3, .recent-activity h3 {{ margin-top: 0; }}
    .btn {{ display: inline-block; padding: 8px 16px; margin-right: 10px; text-decoration: none; border-radius: 4px; }}
    .btn-primary {{ background: #3498db; color: white; }}
    .btn-secondary {{ background: #95a5a6; color: white; }}
    .btn-accent {{ background: #e74c3c; color: white; }}
    </style>
    """

def render_recent_submissions_widget():
    """Widget showing last 5 submissions."""
    submissions = load_student_submissions()
    recent = sorted(submissions["submissions"], key=lambda x: x["submitted_date"], reverse=True)[:5]
    
    if not recent:
        return "<p>No submissions yet.</p>"
    
    rows = []
    for sub in recent:
        subject = get_subject_by_id(sub["subject_id"])
        subject_name = subject["name"] if subject else "Unknown Subject"
        status_class = "pending" if sub["status"] == "pending_review" else "graded"
        status_text = "Pending Review" if sub["status"] == "pending_review" else "Graded"
        
        rows.append(f"""
        <tr>
            <td>{sub['student']}</td>
            <td>{subject_name}</td>
            <td>{sub['submitted_date']}</td>
            <td><span class="status {status_class}">{status_text}</span></td>
        </tr>
        """)
    
    return f"""
    <table class="submissions-table">
        <thead>
            <tr><th>Student</th><th>Subject</th><th>Date</th><th>Status</th></tr>
        </thead>
        <tbody>{"".join(rows)}</tbody>
    </table>
    <style>
    .submissions-table {{ width: 100%; border-collapse: collapse; }}
    .submissions-table th, .submissions-table td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
    .submissions-table th {{ background: #f8f9fa; }}
    .status {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
    .status.pending {{ background: #fff3cd; color: #856404; }}
    .status.graded {{ background: #d1edff; color: #0c5460; }}
    </style>
    """

def render_curriculum_library():
    """Curriculum Library - subjects, units, assignments, pacing."""
    library = load_curriculum_library()
    
    subjects_html = ""
    for subject in library["subjects"].values():
        units_count = len(subject.get("units", []))
        total_assignments = sum(len(unit.get("assignments", [])) for unit in subject.get("units", []))
        
        subjects_html += f"""
        <div class="subject-card">
            <h4>{subject['name']}</h4>
            <p><strong>Student:</strong> {subject.get('student', 'N/A')}</p>
            <p><strong>Grade Level:</strong> {subject.get('grade_level', 'N/A')}</p>
            <p><strong>Units:</strong> {units_count} | <strong>Assignments:</strong> {total_assignments}</p>
            <div class="subject-actions">
                <a href="/curriculum-library/edit/{subject['id']}" class="btn btn-small">✏️ Edit</a>
                <a href="/curriculum-library/view/{subject['id']}" class="btn btn-small">👁️ View</a>
            </div>
        </div>
        """
    
    if not subjects_html:
        subjects_html = "<p>No subjects created yet. <a href='/curriculum-library/new-subject'>Add your first subject</a></p>"
    
    return html_page("Curriculum Library", f"""
    {page_header("📚 Curriculum Library")}
    
    <div class="library-header">
        <a href="/curriculum-library/new-subject" class="btn btn-primary">➕ Add New Subject</a>
    </div>
    
    <div class="subjects-grid">
        {subjects_html}
    </div>
    
    <style>
    .library-header {{ margin: 20px 0; }}
    .subjects-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }}
    .subject-card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 20px; }}
    .subject-card h4 {{ margin-top: 0; color: #2c3e50; }}
    .subject-actions {{ margin-top: 15px; }}
    .btn-small {{ padding: 6px 12px; margin-right: 8px; font-size: 14px; }}
    </style>
    """)


def _parse_modg_locally(raw_text: str) -> dict:
    """Fast local regex parse of a MODG paste. Returns week_str→assignment dict."""
    import re
    weeks = {}
    pattern = re.compile(r'(?:Week|Wk\.?)\s*(\d+)[:\s]+(.+?)(?=(?:Week|Wk\.?)\s*\d+|$)', re.IGNORECASE | re.DOTALL)
    for m in pattern.finditer(raw_text):
        key = f"Week {m.group(1).zfill(2)}"
        weeks[key] = m.group(2).strip()
    return weeks


def _parse_with_ai(subject: str, raw_text: str) -> tuple:
    """AI fallback parse — returns (weeks_dict, error_str)."""
    return {}, "AI parse not yet implemented — please use the manual week format."


def parse_modg_paste(subject: str, raw_text: str) -> tuple:
    """Parse a MODG full-year subject paste into {week_str: assignment_text}.
    Tries fast local regex first; falls back to AI only if that fails.
    Returns (weeks_dict, error_str)."""
    local = _parse_modg_locally(raw_text)
    if len(local) >= 3:
        return local, ""
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
                week_count = sum(1 for k in weeks if not k.startswith("_"))
                stored_mins = weeks.get("_minutes", _recommended_minutes(subj))
                this_week = weeks.get(str(current_week), "")
                preview = (this_week[:80] + "…") if len(this_week) > 80 else this_week
                preview_html = (
                    f'<span class="cur-preview">{preview}</span>'
                    if preview else
                    '<span class="cur-no-assign">— no assignment this week —</span>'
                )
                subj_js = subj.replace("'", "\\'")
                child_js = child.replace("'", "\\'")
                rows += f"""
                <tr>
                  <td class="cur-subj">{subj}</td>
                  <td class="cur-weeks">{week_count} wks</td>
                  <td class="cur-mins-cell">
                    <input class="cur-mins-input" type="number" min="5" max="240" step="5"
                           value="{stored_mins}"
                           id="mins-{child}-{subj}"
                           onchange="saveMinutes('{child_js}','{subj_js}',this.value)">
                    <span class="cur-mins-label">min</span>
                  </td>
                  <td class="cur-this-week">{preview_html}</td>
                  <td class="cur-actions">
                    <button class="cur-del-btn" onclick="deleteSubject('{child_js}','{subj_js}')">✕</button>
                  </td>
                </tr>"""
            child_sections += f"""
            <div class="cur-child-block">
              <h3 class="cur-child-name">{child}</h3>
              <table class="cur-table">
                <thead><tr>
                  <th>Subject</th><th>Weeks</th>
                  <th>Min/session</th>
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
  .cur-mins-cell {{ white-space: nowrap; }}
  .cur-mins-input {{ width: 56px; padding: 3px 6px; border: 1px solid #c4a882;
                     border-radius: 5px; font-size: 0.88em; background: #fdf8f2;
                     text-align: center; color: #3b2a1a; }}
  .cur-mins-input:focus {{ outline: 2px solid #7c3aed; border-color: #7c3aed; }}
  .cur-mins-label {{ font-size: 0.78em; color: #9b8872; margin-left: 3px; }}
  .cur-mins-saved {{ font-size: 0.72em; color: #16a34a; margin-left: 4px; }}

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
        <input class="cur-input" type="text" id="impSubject" placeholder="e.g. Latin, Math, Religion"
               oninput="suggestMinutes(this.value)">
      </div>
      <div class="cur-field" style="max-width:130px;">
        <label>Min per session</label>
        <div style="display:flex;align-items:center;gap:6px;">
          <input class="cur-input" type="number" id="impMinutes" min="5" max="240" step="5"
                 placeholder="30" style="width:70px;">
          <span style="font-size:0.8em;color:#9b8872;">min</span>
        </div>
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

const _MINS_MAP = {{
  math:45, algebra:45, geometry:45, latin:45, greek:45,
  english:30, grammar:30, language:30, spelling:20, vocabulary:20,
  editing:30, religion:30, theology:30, history:45, geography:30,
  science:45, biology:45, chemistry:45, physics:45,
  reading:60, literature:45, composition:30, writing:30,
  art:45, music:20, poetry:15, penmanship:15, handwriting:15,
}};

function suggestMinutes(subjectName) {{
  const s = subjectName.toLowerCase();
  const el = document.getElementById('impMinutes');
  if (el.dataset.edited) return;   // user already changed it manually
  for (const [kw, mins] of Object.entries(_MINS_MAP)) {{
    if (s.includes(kw)) {{ el.value = mins; return; }}
  }}
  el.value = 30;
}}

async function saveMinutes(child, subject, minutes) {{
  const mins = parseInt(minutes, 10);
  if (!mins || mins < 5) return;
  await fetch('/curriculum-minutes', {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{ child, subject, minutes: mins }})
  }});
}}

async function saveCurriculum() {{
  const child   = document.getElementById('impChild').value.trim();
  const subject = document.getElementById('impSubject').value.trim();
  const minsEl  = document.getElementById('impMinutes');
  const minutes = parseInt(minsEl.value, 10) || 30;
  const status  = document.getElementById('saveStatus');
  status.textContent = '';
  if (!Object.keys(_parsedData).length) return;
  try {{
    const res = await fetch('/curriculum-save', {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{ child, subject, weeks: _parsedData, minutes }})
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
