"""
render_plan_importer.py — Plan Import Tool

Paste any free-form plan from an external AI, get it parsed into calendar
events and tasks, review/edit each item, then apply with one click.
"""
import json
import uuid
from datetime import date, timedelta
from html import escape

FAMILY_MEMBERS = ["Lauren", "John", "JP", "Joseph", "Michael", "James"]


def _load_upcoming_events(days: int = 30) -> list:
    try:
        with open("data/events.json") as f:
            data = json.load(f)
        events = data.get("data", [])
    except Exception:
        events = []
    today = date.today()
    cutoff = today + timedelta(days=days)
    upcoming = []
    for ev in events:
        if ev.get("archived"):
            continue
        try:
            d = date.fromisoformat(ev.get("start_date", ""))
            if today <= d <= cutoff:
                upcoming.append(ev)
        except Exception:
            pass
    return sorted(upcoming, key=lambda e: e.get("start_date", ""))


def _format_events_summary(events: list) -> str:
    if not events:
        return "No upcoming events in the next 30 days."
    lines = []
    for ev in events:
        who = ", ".join(ev.get("assigned_to", []))
        t = ev.get("start_time", "")
        e = ev.get("end_time", "")
        time_str = f" {t}" if t else ""
        if e:
            time_str += f"–{e}"
        lines.append(f"- {ev.get('start_date')} {ev.get('title','')}{time_str} [{who}]")
    return "\n".join(lines)


def build_analysis_system_prompt(iso_today: str, label_today: str, events_summary: str) -> str:
    return f"""You are a careful planning assistant for the McAdams Catholic homeschooling family.

TODAY IS: {label_today} ({iso_today})

== FAMILY MEMBERS ==
- Lauren (Mom) — manages the household and homeschool; default assignee for unspecified adult tasks
- John (Dad) — works; sometimes from home
- JP — 14 years old, 9th grade; handles significant academic and household tasks
- Joseph — 12 years old, 7th grade; capable but needs more support than JP
- Michael — 5 years old, kindergarten; very simple tasks only (e.g. "put away toys")
- James — 13 months old, toddler; CANNOT be assigned tasks

== PARSING RULES ==
1. Resolve ALL relative dates ("tomorrow", "next Tuesday", "this weekend", "in two weeks") using TODAY = {iso_today}
2. Separate CALENDAR EVENTS (time-bound) from TASKS (action items with deadlines)
3. If an item has both an event and preparatory tasks, split them
4. Assign to the most specific person context implies; use Lauren for unspecified adult items
5. For tasks with natural sub-steps, list as subtasks (max 5)
6. Set confidence: "high" = certain; "medium" = best inference; "low" = critical info missing
7. Items with missing critical info (date or person unknown) MUST appear in "questions" too

== EXISTING CALENDAR (next 30 days — scan for conflicts) ==
{events_summary}

== WARNINGS TO FLAG ==
- Date/time conflicts (same person, overlapping or same time slot)
- Days that look overloaded (many events + tasks on same day for same person)
- Deadlines that are already past today
- Events that likely need a time but have none (doctor, dentist, activity)
- Items that seem age-inappropriate for the assigned person

== SUGGESTIONS TO OFFER ==
- Shifting tasks to balance load across days
- Adding prep reminders before appointments (e.g. "pack bag the night before")
- Breaking multi-week projects into milestone tasks
- Anything else you notice that would help the family

== OUTPUT FORMAT ==
Respond with ONLY valid JSON inside ```json ... ``` code fences. No other text outside the fences.

{{
  "events": [
    {{
      "id": "e1",
      "title": "Dentist — Michael",
      "date": "YYYY-MM-DD",
      "time": "10:00 AM",
      "end_time": "11:00 AM",
      "who": ["Lauren", "Michael"],
      "notes": "Bring insurance card",
      "recurrence": "none",
      "confidence": "high"
    }}
  ],
  "tasks": [
    {{
      "id": "t1",
      "person": "JP",
      "text": "Write history essay introduction",
      "due_date": "YYYY-MM-DD",
      "subtasks": ["Research topic", "Create outline", "Write opening paragraph"],
      "notes": "",
      "confidence": "high"
    }}
  ],
  "questions": [
    {{
      "id": "q1",
      "text": "What time is the dentist appointment — morning or afternoon?",
      "related_to": "e1",
      "field": "time"
    }}
  ],
  "warnings": [
    {{
      "text": "JP already has a scheduled activity on that date — verify no conflict.",
      "severity": "high",
      "related_to": "e2"
    }}
  ],
  "suggestions": [
    {{
      "text": "Consider moving the grocery run to Monday to prepare for Tuesday's dinner.",
      "related_to": null
    }}
  ]
}}"""


def render_plan_import_page() -> str:
    today = date.today()
    iso   = today.isoformat()
    label = today.strftime("%A, %B %d, %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Plan Import &middot; McAdams Family</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --ink:#2c2825;--ink-soft:rgba(44,40,37,.7);--ink-faint:rgba(44,40,37,.4);
  --parchment:#fdf8f0;--cream:#f7f1e6;--gold:#b8860b;--gold-light:#d4a843;
  --border:rgba(44,40,37,.12);--border-light:rgba(44,40,37,.07);
  --green:#1a6e3e;--amber:#d97706;--red:#b91c1c;--navy:#1e3566;--purple:#5b3a8a;
}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:var(--parchment);color:var(--ink);min-height:100vh;padding-bottom:80px;}}
.pi-header{{background:var(--navy);color:#fff;padding:14px 16px 12px;
            display:flex;align-items:center;gap:10px;}}
.pi-header a{{color:rgba(255,255,255,0.7);text-decoration:none;font-size:0.8em;}}
.pi-header h1{{font-size:1em;font-weight:700;flex:1;}}
.pi-body{{max-width:680px;margin:0 auto;padding:16px;}}
.pi-card{{background:#fff;border:1px solid var(--border);border-radius:14px;
          padding:16px;margin-bottom:14px;}}
.pi-label{{font-size:0.72em;font-weight:700;letter-spacing:.06em;
           color:var(--ink-faint);text-transform:uppercase;margin-bottom:8px;}}
textarea.pi-paste{{width:100%;min-height:180px;border:1.5px solid var(--border);
  border-radius:10px;padding:12px;font-family:inherit;font-size:0.88em;
  line-height:1.55;color:var(--ink);background:var(--cream);resize:vertical;}}
textarea.pi-paste:focus{{outline:none;border-color:var(--navy);}}
.pi-btn{{display:inline-flex;align-items:center;gap:7px;padding:11px 22px;
         border:none;border-radius:24px;font-family:inherit;font-weight:700;
         font-size:0.88em;cursor:pointer;transition:opacity .15s;}}
.pi-btn:disabled{{opacity:.5;cursor:not-allowed;}}
.pi-btn-primary{{background:var(--navy);color:#fff;}}
.pi-btn-apply{{background:var(--green);color:#fff;font-size:0.95em;padding:13px 28px;}}
.pi-btn-sm{{padding:5px 12px;font-size:0.75em;border-radius:14px;font-weight:600;}}
.pi-btn-remove{{background:rgba(185,28,28,.08);color:var(--red);border:1px solid rgba(185,28,28,.18);}}
.pi-btn-edit{{background:rgba(30,53,102,.08);color:var(--navy);border:1px solid rgba(30,53,102,.15);}}
.section-header{{display:flex;align-items:center;gap:8px;margin-bottom:12px;}}
.section-icon{{font-size:1.2em;}}
.section-title{{font-size:0.9em;font-weight:700;color:var(--ink);}}
.section-count{{background:var(--navy);color:#fff;border-radius:10px;
                padding:2px 8px;font-size:0.72em;font-weight:700;}}
.section-count.green{{background:var(--green);}}
.section-count.amber{{background:var(--amber);}}
.section-count.red{{background:var(--red);}}
.item-row{{border:1px solid var(--border);border-radius:10px;margin-bottom:8px;overflow:hidden;}}
.item-main{{display:flex;align-items:center;gap:10px;padding:10px 12px;cursor:pointer;
            background:var(--cream);transition:background .1s;}}
.item-main:hover{{background:#efe9de;}}
.item-cb{{width:18px;height:18px;accent-color:var(--green);cursor:pointer;flex-shrink:0;}}
.item-info{{flex:1;min-width:0;}}
.item-title{{font-size:0.88em;font-weight:600;color:var(--ink);}}
.item-meta{{font-size:0.72em;color:var(--ink-soft);margin-top:2px;}}
.item-conf{{font-size:0.68em;padding:2px 7px;border-radius:8px;font-weight:700;
            flex-shrink:0;}}
.conf-high{{background:rgba(26,110,62,.12);color:var(--green);}}
.conf-medium{{background:rgba(217,119,6,.12);color:var(--amber);}}
.conf-low{{background:rgba(185,28,28,.12);color:var(--red);}}
.item-edit{{border-top:1px solid var(--border);padding:12px;background:#fff;display:none;}}
.item-edit.open{{display:block;}}
.edit-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;}}
.edit-field{{display:flex;flex-direction:column;gap:3px;}}
.edit-field label{{font-size:0.68em;font-weight:700;color:var(--ink-faint);
                   text-transform:uppercase;letter-spacing:.04em;}}
.edit-field input,.edit-field select,.edit-field textarea{{
  border:1px solid var(--border);border-radius:7px;padding:6px 9px;
  font-family:inherit;font-size:0.82em;color:var(--ink);background:#fafafa;}}
.edit-field input:focus,.edit-field select:focus,.edit-field textarea:focus{{
  outline:none;border-color:var(--navy);}}
.subtask-list{{margin-top:6px;}}
.subtask-item{{display:flex;align-items:center;gap:6px;margin-bottom:4px;}}
.subtask-item input{{flex:1;border:1px solid var(--border);border-radius:6px;
                     padding:4px 8px;font-size:0.8em;font-family:inherit;}}
.subtask-del{{background:none;border:none;color:var(--red);cursor:pointer;font-size:1em;}}
.q-item{{background:#fffbf0;border:1px solid rgba(217,119,6,.25);border-radius:10px;
          padding:12px;margin-bottom:8px;}}
.q-text{{font-size:0.85em;font-weight:600;color:var(--ink);margin-bottom:6px;}}
.q-input{{width:100%;border:1px solid var(--border);border-radius:7px;padding:7px 10px;
           font-family:inherit;font-size:0.84em;color:var(--ink);background:#fff;}}
.q-input:focus{{outline:none;border-color:var(--amber);}}
.warn-item{{display:flex;gap:10px;padding:10px 12px;border-radius:9px;margin-bottom:6px;
             background:rgba(185,28,28,.05);border:1px solid rgba(185,28,28,.15);}}
.warn-item.medium{{background:rgba(217,119,6,.06);border-color:rgba(217,119,6,.2);}}
.warn-item.low{{background:rgba(44,40,37,.04);border-color:var(--border);}}
.warn-icon{{font-size:1em;flex-shrink:0;}}
.warn-text{{font-size:0.82em;color:var(--ink);line-height:1.45;}}
.sug-item{{display:flex;gap:10px;padding:10px 12px;border-radius:9px;margin-bottom:6px;
            background:rgba(91,58,138,.05);border:1px solid rgba(91,58,138,.15);}}
.sug-text{{font-size:0.82em;color:var(--ink);line-height:1.45;}}
.spinner{{display:inline-block;width:16px;height:16px;border:2px solid rgba(255,255,255,.3);
          border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite;}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.phase{{display:none;}}
.phase.active{{display:block;}}
#phase-thinking{{text-align:center;padding:48px 24px;}}
.thinking-label{{font-size:0.85em;color:var(--ink-soft);margin-top:16px;}}
.thinking-spinner{{width:40px;height:40px;border:3px solid var(--border);
                   border-top-color:var(--navy);border-radius:50%;
                   animation:spin .9s linear infinite;margin:0 auto;}}
.apply-bar{{position:sticky;bottom:0;background:var(--parchment);
            border-top:1px solid var(--border);padding:12px 16px;
            display:flex;align-items:center;justify-content:space-between;}}
.apply-summary{{font-size:0.82em;color:var(--ink-soft);}}
.apply-summary strong{{color:var(--ink);}}
.badge{{display:inline-block;background:var(--gold-light);color:#fff;
        border-radius:12px;padding:2px 9px;font-size:0.7em;font-weight:700;
        margin-left:4px;vertical-align:middle;}}
.success-card{{text-align:center;padding:40px 20px;}}
.success-icon{{font-size:3em;margin-bottom:12px;}}
.success-title{{font-size:1.2em;font-weight:700;color:var(--green);margin-bottom:8px;}}
.success-body{{font-size:0.88em;color:var(--ink-soft);line-height:1.6;}}
.person-tag{{display:inline-block;padding:1px 7px;border-radius:8px;
             font-size:0.7em;font-weight:700;margin-right:3px;
             background:rgba(30,53,102,.1);color:var(--navy);}}
</style>
</head>
<body>
<div class="pi-header">
  <a href="/">&#8592; Home</a>
  <h1>&#128203; Plan Importer</h1>
</div>

<!-- Phase 1: Paste -->
<div id="phase-paste" class="phase active">
<div class="pi-body">
  <div class="pi-card">
    <div class="pi-label">Paste your plan</div>
    <p style="font-size:0.82em;color:var(--ink-soft);margin-bottom:10px;line-height:1.5;">
      Copy any plan you made with an external AI — ChatGPT, Claude, Gemini, etc. It can be a
      full weekly schedule, a project plan, a list of tasks, or anything in between. The more
      detail you include, the better the results.
    </p>
    <textarea class="pi-paste" id="plan-text"
      placeholder="Paste your plan here...&#10;&#10;For example:&#10;• Monday: dentist for Michael at 2pm, Lauren driving&#10;• JP needs to finish his history essay by Friday&#10;• Family picnic Saturday at Riverside Park&#10;• Joseph: read chapters 5–8 of The Hobbit this week"></textarea>
    <div style="margin-top:10px;display:flex;align-items:center;gap:10px;">
      <button class="pi-btn pi-btn-primary" id="analyze-btn" onclick="analyzePlan()">
        &#128269; Analyze Plan
      </button>
      <span style="font-size:0.75em;color:var(--ink-faint);">
        Claude will parse events, tasks, and flag any questions.
      </span>
    </div>
    <div id="paste-error" style="margin-top:8px;font-size:0.8em;color:var(--red);display:none;"></div>
  </div>

  <div style="font-size:0.72em;color:var(--ink-faint);padding:4px 4px;line-height:1.5;">
    &#128274; This tool only writes to your calendar and task lists when you click Apply.
    Everything is shown for your review and approval first. You can edit any item before applying.
  </div>
</div>
</div>

<!-- Phase 2: Thinking -->
<div id="phase-thinking" class="phase">
  <div class="thinking-spinner"></div>
  <div class="thinking-label" id="thinking-label">Analyzing your plan&hellip;</div>
</div>

<!-- Phase 3: Results -->
<div id="phase-results" class="phase">
<div class="pi-body">

  <!-- Questions -->
  <div id="section-questions" style="display:none;">
    <div class="pi-card">
      <div class="section-header">
        <span class="section-icon">&#10067;</span>
        <span class="section-title">Questions — needs clarification</span>
        <span class="section-count amber" id="q-count">0</span>
      </div>
      <p style="font-size:0.78em;color:var(--ink-soft);margin-bottom:12px;">
        Answer these to improve accuracy before applying, or leave blank to skip those items.
      </p>
      <div id="questions-list"></div>
      <button class="pi-btn pi-btn-primary" style="margin-top:4px;font-size:0.8em;padding:8px 18px;"
              onclick="reanalyzeWithAnswers()">
        &#8635; Re-analyze with my answers
      </button>
    </div>
  </div>

  <!-- Warnings & Suggestions -->
  <div id="section-warnings" style="display:none;">
    <div class="pi-card">
      <div class="section-header">
        <span class="section-icon">&#9888;&#65039;</span>
        <span class="section-title">Warnings &amp; Suggestions</span>
        <span class="section-count amber" id="ws-count">0</span>
      </div>
      <div id="warnings-list"></div>
      <div id="suggestions-list"></div>
    </div>
  </div>

  <!-- Calendar Events -->
  <div id="section-events" style="display:none;">
    <div class="pi-card">
      <div class="section-header">
        <span class="section-icon">&#128197;</span>
        <span class="section-title">Calendar Events</span>
        <span class="section-count green" id="ev-count">0</span>
      </div>
      <div id="events-list"></div>
    </div>
  </div>

  <!-- Tasks -->
  <div id="section-tasks" style="display:none;">
    <div class="pi-card">
      <div class="section-header">
        <span class="section-icon">&#9989;</span>
        <span class="section-title">Tasks</span>
        <span class="section-count green" id="task-count">0</span>
      </div>
      <div id="tasks-list"></div>
    </div>
  </div>

  <!-- No results fallback -->
  <div id="section-empty" style="display:none;">
    <div class="pi-card" style="text-align:center;padding:32px;">
      <div style="font-size:2em;margin-bottom:10px;">&#129300;</div>
      <div style="font-weight:700;margin-bottom:6px;">Nothing to parse</div>
      <div style="font-size:0.82em;color:var(--ink-soft);">
        The plan didn't contain any recognizable calendar events or tasks.
        Try including dates, times, and action items.
      </div>
      <button class="pi-btn pi-btn-primary" style="margin-top:16px;font-size:0.82em;"
              onclick="resetToPaste()">&#8592; Try again</button>
    </div>
  </div>

</div>

<!-- Apply bar -->
<div class="apply-bar" id="apply-bar" style="display:none;">
  <div>
    <button class="pi-btn" style="background:var(--ink-faint);color:#fff;font-size:0.78em;padding:8px 16px;"
            onclick="resetToPaste()">&#8592; Start over</button>
  </div>
  <div style="text-align:right;">
    <div class="apply-summary" id="apply-summary"></div>
    <button class="pi-btn pi-btn-apply" style="margin-top:6px;" id="apply-btn" onclick="applyPlan()">
      &#9989; Apply Selected Items
    </button>
  </div>
</div>
</div>

<!-- Phase 4: Success -->
<div id="phase-success" class="phase">
<div class="pi-body">
  <div class="pi-card success-card">
    <div class="success-icon">&#127881;</div>
    <div class="success-title">Plan Applied</div>
    <div class="success-body" id="success-body"></div>
    <div style="display:flex;gap:10px;justify-content:center;margin-top:20px;flex-wrap:wrap;">
      <a href="/calendar" class="pi-btn pi-btn-primary" style="text-decoration:none;">
        &#128197; View Calendar
      </a>
      <a href="/today" class="pi-btn" style="background:var(--green);color:#fff;text-decoration:none;">
        &#9989; View Today
      </a>
      <button class="pi-btn" style="background:var(--ink-faint);color:#fff;"
              onclick="resetToPaste()">&#128203; Import Another</button>
    </div>
  </div>
</div>
</div>

<script>
const TODAY_ISO = {json.dumps(iso)};
const TODAY_LABEL = {json.dumps(label)};
const FAMILY = {json.dumps(FAMILY_MEMBERS)};

// ── State ──────────────────────────────────────────────────────────────────
let analysisData = null;   // Full analysis JSON from server
let currentAnswers = {{}};  // question id -> answer text

// ── Phase helpers ──────────────────────────────────────────────────────────
function showPhase(id) {{
  document.querySelectorAll('.phase').forEach(p => p.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}}

function resetToPaste() {{
  analysisData = null; currentAnswers = {{}};
  document.getElementById('plan-text').value = '';
  document.getElementById('paste-error').style.display = 'none';
  document.getElementById('analyze-btn').disabled = false;
  showPhase('phase-paste');
}}

// ── Analyze ────────────────────────────────────────────────────────────────
async function analyzePlan(extraAnswers) {{
  const text = document.getElementById('plan-text').value.trim();
  if (!text) {{
    const e = document.getElementById('paste-error');
    e.textContent = 'Please paste a plan first.';
    e.style.display = 'block';
    return;
  }}
  document.getElementById('paste-error').style.display = 'none';
  document.getElementById('analyze-btn').disabled = true;
  document.getElementById('thinking-label').textContent = 'Analyzing your plan\u2026';
  showPhase('phase-thinking');

  const body = new URLSearchParams({{plan_text: text}});
  if (extraAnswers) {{
    body.append('answers', JSON.stringify(extraAnswers));
  }}

  try {{
    const resp = await fetch('/plan-import-analyze', {{method:'POST', body}});
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    analysisData = data;
    renderResults(data);
    showPhase('phase-results');
  }} catch(err) {{
    document.getElementById('analyze-btn').disabled = false;
    showPhase('phase-paste');
    const e = document.getElementById('paste-error');
    e.textContent = 'Analysis failed: ' + err.message;
    e.style.display = 'block';
  }}
}}

async function reanalyzeWithAnswers() {{
  const qs = document.querySelectorAll('.q-answer');
  const answers = {{}};
  qs.forEach(inp => {{ answers[inp.dataset.qid] = inp.value.trim(); }});
  currentAnswers = answers;
  showPhase('phase-thinking');
  document.getElementById('thinking-label').textContent = 'Re-analyzing with your answers\u2026';

  const text = document.getElementById('plan-text').value.trim();
  const body = new URLSearchParams({{plan_text: text, answers: JSON.stringify(answers)}});
  try {{
    const resp = await fetch('/plan-import-analyze', {{method:'POST', body}});
    if (!resp.ok) throw new Error(await resp.text());
    analysisData = await resp.json();
    renderResults(analysisData);
    showPhase('phase-results');
  }} catch(err) {{
    showPhase('phase-results');
    alert('Re-analysis failed: ' + err.message);
  }}
}}

// ── Render results ─────────────────────────────────────────────────────────
function renderResults(data) {{
  const events = data.events || [];
  const tasks  = data.tasks  || [];
  const questions = data.questions || [];
  const warnings  = data.warnings  || [];
  const suggestions = data.suggestions || [];

  const hasAnything = events.length + tasks.length > 0;

  // Questions
  const qSec = document.getElementById('section-questions');
  if (questions.length) {{
    qSec.style.display = '';
    document.getElementById('q-count').textContent = questions.length;
    document.getElementById('questions-list').innerHTML = questions.map(q => `
      <div class="q-item">
        <div class="q-text">&#10067; ${{esc(q.text)}}</div>
        <input class="q-input q-answer" data-qid="${{q.id}}" placeholder="Your answer\u2026"
               value="${{esc(currentAnswers[q.id] || '')}}">
      </div>
    `).join('');
  }} else {{
    qSec.style.display = 'none';
  }}

  // Warnings & Suggestions
  const wsSec = document.getElementById('section-warnings');
  const total_ws = warnings.length + suggestions.length;
  if (total_ws) {{
    wsSec.style.display = '';
    document.getElementById('ws-count').textContent = total_ws;
    document.getElementById('warnings-list').innerHTML = warnings.map(w => `
      <div class="warn-item ${{w.severity === 'high' ? '' : w.severity}}">
        <span class="warn-icon">${{w.severity === 'high' ? '&#128308;' : w.severity === 'medium' ? '&#128993;' : '&#9898;'}}</span>
        <span class="warn-text">${{esc(w.text)}}</span>
      </div>
    `).join('');
    document.getElementById('suggestions-list').innerHTML = suggestions.map(s => `
      <div class="sug-item">
        <span class="warn-icon">&#128161;</span>
        <span class="sug-text">${{esc(s.text)}}</span>
      </div>
    `).join('');
  }} else {{
    wsSec.style.display = 'none';
  }}

  // Events
  const evSec = document.getElementById('section-events');
  if (events.length) {{
    evSec.style.display = '';
    document.getElementById('ev-count').textContent = events.length;
    document.getElementById('events-list').innerHTML = events.map(ev => renderEventItem(ev)).join('');
  }} else {{
    evSec.style.display = 'none';
  }}

  // Tasks
  const tSec = document.getElementById('section-tasks');
  if (tasks.length) {{
    tSec.style.display = '';
    document.getElementById('task-count').textContent = tasks.length;
    document.getElementById('tasks-list').innerHTML = tasks.map(t => renderTaskItem(t)).join('');
  }} else {{
    tSec.style.display = 'none';
  }}

  // Empty state
  document.getElementById('section-empty').style.display = hasAnything ? 'none' : '';

  // Apply bar
  document.getElementById('apply-bar').style.display = hasAnything ? 'flex' : 'none';
  updateApplySummary();
}}

function renderEventItem(ev) {{
  const conf = ev.confidence || 'high';
  const who  = (ev.who || []).join(', ');
  const time = [ev.time, ev.end_time].filter(Boolean).join(' – ');
  const meta = [ev.date, time, who].filter(Boolean).join(' &middot; ');
  return `<div class="item-row" id="item-${{ev.id}}">
    <div class="item-main" onclick="toggleEdit('${{ev.id}}')">
      <input type="checkbox" class="item-cb" id="cb-${{ev.id}}" checked
             onclick="event.stopPropagation();updateApplySummary()">
      <div class="item-info">
        <div class="item-title">&#128197; ${{esc(ev.title)}}</div>
        <div class="item-meta">${{meta}}</div>
      </div>
      <span class="item-conf conf-${{conf}}">${{conf}}</span>
      <span style="color:var(--ink-faint);font-size:0.75em;margin-left:4px;">&#9660;</span>
    </div>
    <div class="item-edit" id="edit-${{ev.id}}">
      <div class="edit-grid">
        <div class="edit-field" style="grid-column:1/-1;">
          <label>Title</label>
          <input type="text" id="ef-title-${{ev.id}}" value="${{esc(ev.title)}}">
        </div>
        <div class="edit-field">
          <label>Date</label>
          <input type="date" id="ef-date-${{ev.id}}" value="${{ev.date || ''}}">
        </div>
        <div class="edit-field">
          <label>Start Time</label>
          <input type="text" id="ef-time-${{ev.id}}" value="${{esc(ev.time || '')}}" placeholder="10:00 AM">
        </div>
        <div class="edit-field">
          <label>End Time</label>
          <input type="text" id="ef-endtime-${{ev.id}}" value="${{esc(ev.end_time || '')}}" placeholder="11:00 AM">
        </div>
        <div class="edit-field">
          <label>Who</label>
          <input type="text" id="ef-who-${{ev.id}}" value="${{esc(who)}}" placeholder="Lauren, JP">
        </div>
        <div class="edit-field" style="grid-column:1/-1;">
          <label>Notes</label>
          <input type="text" id="ef-notes-${{ev.id}}" value="${{esc(ev.notes || '')}}">
        </div>
      </div>
      <div style="margin-top:10px;display:flex;justify-content:flex-end;">
        <button class="pi-btn pi-btn-sm pi-btn-remove" onclick="removeItem('${{ev.id}}')">
          &#128465; Remove
        </button>
      </div>
    </div>
  </div>`;
}}

function renderTaskItem(t) {{
  const conf = t.confidence || 'high';
  const subtasks = t.subtasks || [];
  const meta = [t.person, t.due_date ? 'due ' + t.due_date : ''].filter(Boolean).join(' &middot; ');
  return `<div class="item-row" id="item-${{t.id}}">
    <div class="item-main" onclick="toggleEdit('${{t.id}}')">
      <input type="checkbox" class="item-cb" id="cb-${{t.id}}" checked
             onclick="event.stopPropagation();updateApplySummary()">
      <div class="item-info">
        <div class="item-title">&#9989; ${{esc(t.text)}}</div>
        <div class="item-meta">${{meta}}${{subtasks.length ? ' &middot; ' + subtasks.length + ' subtasks' : ''}}</div>
      </div>
      <span class="item-conf conf-${{conf}}">${{conf}}</span>
      <span style="color:var(--ink-faint);font-size:0.75em;margin-left:4px;">&#9660;</span>
    </div>
    <div class="item-edit" id="edit-${{t.id}}">
      <div class="edit-grid">
        <div class="edit-field" style="grid-column:1/-1;">
          <label>Task</label>
          <input type="text" id="tf-text-${{t.id}}" value="${{esc(t.text)}}">
        </div>
        <div class="edit-field">
          <label>Assigned to</label>
          <select id="tf-person-${{t.id}}">
            ${{FAMILY.map(m => `<option value="${{m}}"${{m === t.person ? ' selected' : ''}}>${{m}}</option>`).join('')}}
          </select>
        </div>
        <div class="edit-field">
          <label>Due date</label>
          <input type="date" id="tf-date-${{t.id}}" value="${{t.due_date || ''}}">
        </div>
        <div class="edit-field" style="grid-column:1/-1;">
          <label>Notes</label>
          <input type="text" id="tf-notes-${{t.id}}" value="${{esc(t.notes || '')}}">
        </div>
      </div>
      ${{subtasks.length ? `
      <div style="margin-top:10px;">
        <div style="font-size:0.72em;font-weight:700;color:var(--ink-faint);text-transform:uppercase;
                    letter-spacing:.04em;margin-bottom:6px;">Subtasks</div>
        <div class="subtask-list" id="stl-${{t.id}}">
          ${{subtasks.map((s,i) => `
          <div class="subtask-item" id="sti-${{t.id}}-${{i}}">
            <input value="${{esc(s)}}" id="st-${{t.id}}-${{i}}" placeholder="Subtask\u2026">
            <button class="subtask-del" onclick="removeSubtask('${{t.id}}',${{i}})" title="Remove">&#215;</button>
          </div>`).join('')}}
        </div>
        <button class="pi-btn pi-btn-sm pi-btn-edit" style="margin-top:6px;"
                onclick="addSubtask('${{t.id}}')">+ Add subtask</button>
      </div>` : `
      <div style="margin-top:10px;">
        <div class="subtask-list" id="stl-${{t.id}}"></div>
        <button class="pi-btn pi-btn-sm pi-btn-edit" onclick="addSubtask('${{t.id}}')">+ Add subtask</button>
      </div>`}}
      <div style="margin-top:10px;display:flex;justify-content:flex-end;">
        <button class="pi-btn pi-btn-sm pi-btn-remove" onclick="removeItem('${{t.id}}')">
          &#128465; Remove
        </button>
      </div>
    </div>
  </div>`;
}}

function toggleEdit(id) {{
  const el = document.getElementById('edit-' + id);
  el.classList.toggle('open');
}}

function removeItem(id) {{
  const row = document.getElementById('item-' + id);
  if (row) row.remove();
  updateApplySummary();
}}

function removeSubtask(tid, idx) {{
  const el = document.getElementById('sti-' + tid + '-' + idx);
  if (el) el.remove();
}}

function addSubtask(tid) {{
  const list = document.getElementById('stl-' + tid);
  if (!list) return;
  const idx = list.children.length;
  const div = document.createElement('div');
  div.className = 'subtask-item';
  div.id = 'sti-' + tid + '-' + idx;
  div.innerHTML = `<input id="st-${{tid}}-${{idx}}" placeholder="Subtask\u2026">
    <button class="subtask-del" onclick="removeSubtask('${{tid}}',${{idx}})">&#215;</button>`;
  list.appendChild(div);
}}

function updateApplySummary() {{
  const checked = document.querySelectorAll('.item-cb:checked').length;
  const total   = document.querySelectorAll('.item-cb').length;
  document.getElementById('apply-summary').innerHTML =
    `<strong>${{checked}}</strong> of ${{total}} items selected`;
  document.getElementById('apply-btn').disabled = checked === 0;
}}

// ── Collect current state ──────────────────────────────────────────────────
function collectApproved() {{
  if (!analysisData) return {{events:[], tasks:[]}};
  const events = (analysisData.events || []).filter(ev => {{
    const cb = document.getElementById('cb-' + ev.id);
    const row = document.getElementById('item-' + ev.id);
    return cb && cb.checked && row;
  }}).map(ev => ({{
    ...ev,
    title:    (document.getElementById('ef-title-' + ev.id)   || {{}}).value || ev.title,
    date:     (document.getElementById('ef-date-' + ev.id)    || {{}}).value || ev.date,
    time:     (document.getElementById('ef-time-' + ev.id)    || {{}}).value || ev.time || '',
    end_time: (document.getElementById('ef-endtime-' + ev.id) || {{}}).value || ev.end_time || '',
    who:      ((document.getElementById('ef-who-' + ev.id)    || {{}}).value || '').split(',').map(s=>s.trim()).filter(Boolean),
    notes:    (document.getElementById('ef-notes-' + ev.id)   || {{}}).value || ev.notes || '',
  }}));

  const tasks = (analysisData.tasks || []).filter(t => {{
    const cb = document.getElementById('cb-' + t.id);
    const row = document.getElementById('item-' + t.id);
    return cb && cb.checked && row;
  }}).map(t => {{
    const stList = document.getElementById('stl-' + t.id);
    const subtasks = stList
      ? Array.from(stList.querySelectorAll('input')).map(i => i.value.trim()).filter(Boolean)
      : (t.subtasks || []);
    return {{
      ...t,
      text:     (document.getElementById('tf-text-' + t.id)   || {{}}).value || t.text,
      person:   (document.getElementById('tf-person-' + t.id) || {{}}).value || t.person,
      due_date: (document.getElementById('tf-date-' + t.id)   || {{}}).value || t.due_date || '',
      notes:    (document.getElementById('tf-notes-' + t.id)  || {{}}).value || t.notes || '',
      subtasks,
    }};
  }});

  return {{events, tasks}};
}}

// ── Apply ──────────────────────────────────────────────────────────────────
async function applyPlan() {{
  const btn = document.getElementById('apply-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Applying\u2026';

  const payload = collectApproved();
  try {{
    const resp = await fetch('/plan-import-apply', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(payload),
    }});
    if (!resp.ok) throw new Error(await resp.text());
    const result = await resp.json();
    const evAdded = result.events_added || 0;
    const tAdded  = result.tasks_added  || 0;
    document.getElementById('success-body').innerHTML =
      `Added <strong>${{evAdded}} calendar event${{evAdded!==1?'s':''}}</strong> and
       <strong>${{tAdded}} task${{tAdded!==1?'s':''}}</strong> to the family plan.`;
    showPhase('phase-success');
  }} catch(err) {{
    btn.disabled = false;
    btn.innerHTML = '&#9989; Apply Selected Items';
    alert('Apply failed: ' + err.message);
  }}
}}

function esc(str) {{
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}}
</script>
</body>
</html>"""
