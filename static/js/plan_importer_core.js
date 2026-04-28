// plan_importer_core.js
// Core results rendering, apply, receipt, and undo logic for /plan-import.
// TODAY_ISO, TODAY_LABEL, and FAMILY are injected by the page before this script loads.

// ── State ──────────────────────────────────────────────────────────────────
let analysisData = null;   // Full analysis JSON from server
let currentAnswers = {};  // question id -> answer text
let _freshAnalysis = false; // True only when results came from a just-run analysis (gates autoConveneCouncil)

const _STORAGE_KEY = 'planImporter_session_v1';

function _saveSession() {
  try {
    const planText = document.getElementById('plan-text').value || '';
    localStorage.setItem(_STORAGE_KEY, JSON.stringify({
      analysisData,
      planText,
      savedAt: Date.now(),
    }));
  } catch(e) {}
}

function _clearSession() {
  try { localStorage.removeItem(_STORAGE_KEY); } catch(e) {}
}

async function saveSessionToServer() {
  const btn = document.getElementById('save-to-server-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
  try {
    const planText = document.getElementById('plan-text').value || '';
    const resp = await fetch('/plan-import-save-session', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        plan_text: planText,
        analysis: analysisData,
        source: 'recovered',
      }),
    });
    if (!resp.ok) throw new Error(await resp.text());
    if (btn) { btn.textContent = '✓ Saved'; btn.style.background = '#166534'; }
  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = '⚠ Retry'; }
    alert('Could not save: ' + e.message);
  }
}

function _restoreSession() {
  _freshAnalysis = false;
  try {
    const raw = localStorage.getItem(_STORAGE_KEY);
    if (!raw) return;
    const session = JSON.parse(raw);
    // Only restore sessions from the last 24 hours
    if (!session.analysisData || (Date.now() - (session.savedAt||0)) > 86400000) {
      _clearSession(); return;
    }
    // Restore plan text
    if (session.planText) document.getElementById('plan-text').value = session.planText;
    // Restore analysis
    analysisData = session.analysisData;
    renderResults(analysisData);
    showPhase('phase-results');
    // Show a subtle "restored" banner
    const banner = document.getElementById('restore-banner');
    if (banner) banner.style.display = 'flex';
  } catch(e) { _clearSession(); }
}

// ── Phase helpers ──────────────────────────────────────────────────────────
function showPhase(id) {
  document.querySelectorAll('.phase').forEach(p => p.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

function resetToPaste() {
  analysisData = null; currentAnswers = {};
  document.getElementById('plan-text').value = '';
  document.getElementById('paste-error').style.display = 'none';
  document.getElementById('analyze-btn').disabled = false;
  _clearSession();
  showPhase('phase-paste');
}

// ── Image upload (file / drag-drop / paste) ────────────────────────────────
let _planImageFile = null;
function _setPlanImageFile(file) {
  if (!file || !file.type || !file.type.startsWith('image/')) return;
  // Cap at ~8 MB to keep request size reasonable for Claude vision
  if (file.size > 8 * 1024 * 1024) {
    const e = document.getElementById('paste-error');
    e.textContent = 'Image is too large (max 8 MB). Please use a smaller screenshot.';
    e.style.display = 'block';
    return;
  }
  _planImageFile = file;
  const wrap = document.getElementById('img-preview-wrap');
  const img  = document.getElementById('img-preview');
  document.getElementById('img-preview-name').textContent = file.name || 'pasted image';
  document.getElementById('img-preview-size').textContent =
    Math.round(file.size / 1024) + ' KB · ' + file.type;
  const reader = new FileReader();
  reader.onload = ev => { img.src = ev.target.result; };
  reader.readAsDataURL(file);
  wrap.style.display = 'block';
  document.getElementById('img-drop').style.display = 'none';
  document.getElementById('paste-error').style.display = 'none';
}
function clearPlanImage() {
  _planImageFile = null;
  document.getElementById('img-preview-wrap').style.display = 'none';
  document.getElementById('img-drop').style.display = 'block';
  document.getElementById('plan-image-input').value = '';
}
(function initImageUpload() {
  const drop = document.getElementById('img-drop');
  const input = document.getElementById('plan-image-input');
  if (!drop || !input) return;
  drop.addEventListener('click', () => input.click());
  input.addEventListener('change', e => {
    if (e.target.files && e.target.files[0]) _setPlanImageFile(e.target.files[0]);
  });
  ['dragenter','dragover'].forEach(ev =>
    drop.addEventListener(ev, e => { e.preventDefault(); drop.style.background = '#ecfdf5';
                                       drop.style.borderColor = '#86efac'; }));
  ['dragleave','drop'].forEach(ev =>
    drop.addEventListener(ev, e => { e.preventDefault(); drop.style.background = '#fafaf7';
                                       drop.style.borderColor = '#cbd5e1'; }));
  drop.addEventListener('drop', e => {
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0])
      _setPlanImageFile(e.dataTransfer.files[0]);
  });
  // Paste-from-clipboard anywhere on the page during paste phase
  document.addEventListener('paste', e => {
    const phase = document.getElementById('phase-paste');
    if (!phase || !phase.classList.contains('active')) return;
    const items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    for (const it of items) {
      if (it.kind === 'file' && it.type.startsWith('image/')) {
        const f = it.getAsFile();
        if (f) { _setPlanImageFile(f); e.preventDefault(); break; }
      }
    }
  });
})();

// ── Analyze ────────────────────────────────────────────────────────────────
async function analyzePlan(extraAnswers) {
  const text = document.getElementById('plan-text').value.trim();
  if (!text && !_planImageFile) {
    const e = document.getElementById('paste-error');
    e.textContent = 'Please paste a plan or attach an image first.';
    e.style.display = 'block';
    return;
  }
  document.getElementById('paste-error').style.display = 'none';
  document.getElementById('analyze-btn').disabled = true;
  document.getElementById('thinking-label').textContent = _planImageFile
    ? 'Reading your image and analyzing…'
    : 'Analyzing your plan…';
  showPhase('phase-thinking');

  let resp;
  try {
    if (_planImageFile) {
      const fd = new FormData();
      fd.append('plan_text', text);
      fd.append('plan_image', _planImageFile, _planImageFile.name || 'pasted.png');
      if (extraAnswers) fd.append('answers', JSON.stringify(extraAnswers));
      resp = await fetch('/plan-import-analyze', {method:'POST', body: fd});
    } else {
      const body = new URLSearchParams({plan_text: text});
      if (extraAnswers) body.append('answers', JSON.stringify(extraAnswers));
      resp = await fetch('/plan-import-analyze', {method:'POST', body});
    }
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    analysisData = data;
    _freshAnalysis = true;
    renderResults(data);
    showPhase('phase-results');
    _saveSession();
  } catch(err) {
    document.getElementById('analyze-btn').disabled = false;
    showPhase('phase-paste');
    const e = document.getElementById('paste-error');
    e.textContent = 'Analysis failed: ' + err.message;
    e.style.display = 'block';
  }
}

async function reanalyzeWithAnswers() {
  const qs = document.querySelectorAll('.q-answer');
  const answers = {};
  qs.forEach(inp => { answers[inp.dataset.qid] = inp.value.trim(); });
  currentAnswers = answers;
  showPhase('phase-thinking');
  document.getElementById('thinking-label').textContent = 'Re-analyzing with your answers…';

  const text = document.getElementById('plan-text').value.trim();
  const body = new URLSearchParams({plan_text: text, answers: JSON.stringify(answers)});
  try {
    const resp = await fetch('/plan-import-analyze', {method:'POST', body});
    if (!resp.ok) throw new Error(await resp.text());
    analysisData = await resp.json();
    renderResults(analysisData);
    showPhase('phase-results');
    _saveSession();
  } catch(err) {
    showPhase('phase-results');
    alert('Re-analysis failed: ' + err.message);
  }
}

// ── Render results ─────────────────────────────────────────────────────────
function renderResults(data) {
  const events = data.events || [];
  const tasks  = data.tasks  || [];
  const questions = data.questions || [];
  const warnings  = data.warnings  || [];
  const suggestions = data.suggestions || [];
  const placements = data.placements || [];

  const hasAnything = events.length + tasks.length + placements.length > 0;

  // Questions
  const qSec = document.getElementById('section-questions');
  if (questions.length) {
    qSec.style.display = '';
    document.getElementById('q-count').textContent = questions.length;
    document.getElementById('questions-list').innerHTML = questions.map(q => `
      <div class="q-item">
        <div class="q-text">&#10067; ${esc(q.text)}</div>
        <input class="q-input q-answer" data-qid="${q.id}" placeholder="Your answer…"
               value="${esc(currentAnswers[q.id] || '')}">
      </div>
    `).join('');
  } else {
    qSec.style.display = 'none';
  }

  // Warnings & Suggestions
  const wsSec = document.getElementById('section-warnings');
  const total_ws = warnings.length + suggestions.length;
  if (total_ws) {
    wsSec.style.display = '';
    document.getElementById('ws-count').textContent = total_ws;
    document.getElementById('warnings-list').innerHTML = warnings.map(w => `
      <div class="warn-item ${w.severity === 'high' ? '' : w.severity}">
        <span class="warn-icon">${w.severity === 'high' ? '&#128308;' : w.severity === 'medium' ? '&#128993;' : '&#9898;'}</span>
        <span class="warn-text">${esc(w.text)}</span>
      </div>
    `).join('');
    document.getElementById('suggestions-list').innerHTML = suggestions.map((s, idx) => `
      <div class="sug-item" id="sug-${idx}"
           style="align-items:flex-start;gap:8px;flex-wrap:wrap;">
        <span class="warn-icon" style="flex-shrink:0;margin-top:2px;">&#128161;</span>
        <span class="sug-text" style="flex:1;min-width:0;">${esc(s.text)}</span>
        <div style="display:flex;gap:5px;flex-shrink:0;margin-top:1px;">
          <button class="pi-btn pi-btn-sm pi-btn-primary"
                  style="padding:3px 10px;font-size:0.72em;"
                  onclick="acceptSuggestion(${idx})">
            &#10003; Add as task
          </button>
          <button class="pi-btn pi-btn-sm pi-btn-remove"
                  style="padding:3px 10px;font-size:0.72em;"
                  onclick="ignoreSuggestion(${idx})">
            &#10005; Ignore
          </button>
        </div>
      </div>
    `).join('');
  } else {
    wsSec.style.display = 'none';
  }

  // Placements
  const plSec = document.getElementById('section-placements');
  if (placements.length) {
    plSec.style.display = '';
    document.getElementById('placements-count').textContent = placements.length;
    document.getElementById('placements-list').innerHTML = placements.map(p => renderPlacementItem(p)).join('');
  } else {
    plSec.style.display = 'none';
  }

  // Events
  const evSec = document.getElementById('section-events');
  if (events.length) {
    evSec.style.display = '';
    document.getElementById('ev-count').textContent = events.length;
    document.getElementById('events-list').innerHTML = events.map(ev => renderEventItem(ev)).join('');
  } else {
    evSec.style.display = 'none';
  }

  // Tasks — always show so "Add task manually" is accessible
  const tSec = document.getElementById('section-tasks');
  tSec.style.display = '';
  document.getElementById('task-count').textContent = tasks.length;
  document.getElementById('tasks-list').innerHTML = tasks.map(t => renderTaskItem(t)).join('');

  // Empty state
  document.getElementById('section-empty').style.display = hasAnything ? 'none' : '';

  // Apply bar
  document.getElementById('apply-bar').style.display = hasAnything ? 'flex' : 'none';
  updateApplySummary();

  // Companion panel — reset old chat state and render fresh
  consultHistories = {};
  activeCompanion = null;
  const chatArea = document.getElementById('consult-chat-area');
  if (chatArea) chatArea.style.display = 'none';
  document.getElementById('consult-panel').style.display = 'none';
  if (data._companions && data._companions.length && hasAnything) {
    renderCompanionPanel(data._companions);
    // Quick review almost always wants to run first — fire it automatically
    // so Lauren doesn't have to click. The function self-guards on an empty
    // council thread, so re-analyses won't double-run it.
    try { autoConveneCouncil(); } catch(_) {}
  }
}

function renderEventItem(ev) {
  const conf = ev.confidence || 'high';
  const who  = (ev.who || []).join(', ');
  const time = [ev.time, ev.end_time].filter(Boolean).join(' – ');
  const meta = [ev.date, time, who].filter(Boolean).join(' &middot; ');
  return `<div class="item-row" id="item-${ev.id}">
    <div class="item-main" onclick="toggleEdit('${ev.id}')">
      <input type="checkbox" class="item-cb" id="cb-${ev.id}" checked
             onclick="event.stopPropagation();updateApplySummary()">
      <div class="item-info">
        <div class="item-title">&#128197; ${esc(ev.title)}</div>
        <div class="item-meta">${meta}</div>
      </div>
      <span class="item-conf conf-${conf}">${conf}</span>
      <span style="color:var(--ink-faint);font-size:0.75em;margin-left:4px;">&#9660;</span>
    </div>
    <div class="item-edit" id="edit-${ev.id}">
      <div class="edit-grid">
        <div class="edit-field" style="grid-column:1/-1;">
          <label>Title</label>
          <input type="text" id="ef-title-${ev.id}" value="${esc(ev.title)}">
        </div>
        <div class="edit-field">
          <label>Date</label>
          <input type="date" id="ef-date-${ev.id}" value="${ev.date || ''}">
        </div>
        <div class="edit-field">
          <label>Start Time</label>
          <input type="text" id="ef-time-${ev.id}" value="${esc(ev.time || '')}" placeholder="10:00 AM">
        </div>
        <div class="edit-field">
          <label>End Time</label>
          <input type="text" id="ef-endtime-${ev.id}" value="${esc(ev.end_time || '')}" placeholder="11:00 AM">
        </div>
        <div class="edit-field">
          <label>Who</label>
          <input type="text" id="ef-who-${ev.id}" value="${esc(who)}" placeholder="Lauren, JP">
        </div>
        <div class="edit-field" style="grid-column:1/-1;">
          <label>Notes</label>
          <input type="text" id="ef-notes-${ev.id}" value="${esc(ev.notes || '')}">
        </div>
      </div>
      <div style="margin-top:10px;display:flex;justify-content:flex-end;">
        <button class="pi-btn pi-btn-sm pi-btn-remove" onclick="removeItem('${ev.id}')">
          &#128465; Remove
        </button>
      </div>
    </div>
  </div>`;
}

// Builds the inner HTML for the task's action area. When the task is
// uncertain (low/medium confidence) we show a three-way decision strip;
// otherwise we show the standard Remove button. Used both at initial
// render time and when confirmTask/deferTask swap the strip for Remove.
function _taskActionsHtml(id, conf) {
  if (conf === 'low' || conf === 'medium') {
    return `<div class="task-decide-row">
      <button class="pi-btn pi-btn-sm pi-btn-add"   onclick="confirmTask('${id}')">&#10003; Add it</button>
      <button class="pi-btn pi-btn-sm pi-btn-skip"  onclick="removeItem('${id}')">&#10005; Not now</button>
      <button class="pi-btn pi-btn-sm pi-btn-defer" onclick="deferTask('${id}')">&#9200; Remind me tomorrow</button>
    </div>`;
  }
  return `<div style="display:flex;justify-content:flex-end;">
    <button class="pi-btn pi-btn-sm pi-btn-remove" onclick="removeItem('${id}')">
      &#128465; Remove
    </button>
  </div>`;
}

function renderTaskItem(t) {
  const conf = t.confidence || 'high';
  const subtasks = t.subtasks || [];
  const meta = [t.person, t.due_date ? 'due ' + t.due_date : ''].filter(Boolean).join(' &middot; ');
  // Low/medium-confidence tasks render unchecked so they aren't applied
  // unless Lauren actively chooses Add it or Remind me tomorrow.
  const checkedAttr = (conf === 'low' || conf === 'medium') ? '' : 'checked';
  return `<div class="item-row" id="item-${t.id}">
    <div class="item-main" onclick="toggleEdit('${t.id}')">
      <input type="checkbox" class="item-cb" id="cb-${t.id}" ${checkedAttr}
             onclick="event.stopPropagation();updateApplySummary()">
      <div class="item-info">
        <div class="item-title">&#9989; ${esc(t.text)}</div>
        <div class="item-meta">${meta}${subtasks.length ? ' &middot; ' + subtasks.length + ' subtasks' : ''}</div>
      </div>
      <span class="item-conf conf-${conf}">${conf}</span>
      <span style="color:var(--ink-faint);font-size:0.75em;margin-left:4px;">&#9660;</span>
    </div>
    <div class="item-edit" id="edit-${t.id}">
      <div class="edit-grid">
        <div class="edit-field" style="grid-column:1/-1;">
          <label>Task</label>
          <input type="text" id="tf-text-${t.id}" value="${esc(t.text)}">
        </div>
        <div class="edit-field">
          <label>Assigned to</label>
          <select id="tf-person-${t.id}">
            ${FAMILY.map(m => `<option value="${m}"${m === t.person ? ' selected' : ''}>${m}</option>`).join('')}
          </select>
        </div>
        <div class="edit-field">
          <label>Due date</label>
          <input type="date" id="tf-date-${t.id}" value="${t.due_date || ''}">
        </div>
        <div class="edit-field" style="grid-column:1/-1;">
          <label>Notes</label>
          <input type="text" id="tf-notes-${t.id}" value="${esc(t.notes || '')}">
        </div>
      </div>
      ${subtasks.length ? `
      <div style="margin-top:10px;">
        <div style="font-size:0.72em;font-weight:700;color:var(--ink-faint);text-transform:uppercase;
                    letter-spacing:.04em;margin-bottom:6px;">Subtasks</div>
        <div class="subtask-list" id="stl-${t.id}">
          ${subtasks.map((s,i) => `
          <div class="subtask-item" id="sti-${t.id}-${i}">
            <input value="${esc(s)}" id="st-${t.id}-${i}" placeholder="Subtask…">
            <button class="subtask-del" onclick="removeSubtask('${t.id}',${i})" title="Remove">&#215;</button>
          </div>`).join('')}
        </div>
        <button class="pi-btn pi-btn-sm pi-btn-edit" style="margin-top:6px;"
                onclick="addSubtask('${t.id}')">+ Add subtask</button>
      </div>` : `
      <div style="margin-top:10px;">
        <div class="subtask-list" id="stl-${t.id}"></div>
        <button class="pi-btn pi-btn-sm pi-btn-edit" onclick="addSubtask('${t.id}')">+ Add subtask</button>
      </div>`}
      <div id="actions-${t.id}" style="margin-top:10px;">
        ${_taskActionsHtml(t.id, conf)}
      </div>
    </div>
  </div>`;
}

// Confirms an uncertain task: checks the box and swaps the three-button
// strip for the standard Remove button. Does NOT mutate task data.
function confirmTask(id) {
  const cb = document.getElementById('cb-' + id);
  if (cb) cb.checked = true;
  const actions = document.getElementById('actions-' + id);
  if (actions) actions.innerHTML = _taskActionsHtml(id, 'high');
  updateApplySummary();
}

// Defers an uncertain task to tomorrow as a high-confidence task. Updates
// both the in-memory task object AND the visible date/notes inputs so the
// apply payload (which reads from the inputs) picks up the new values.
function deferTask(id) {
  const task = ((analysisData && analysisData.tasks) || []).find(x => x.id === id);
  if (!task) return;

  // tomorrow = TODAY_ISO + 1 day, formatted as YYYY-MM-DD
  const tomorrow = new Date(new Date(TODAY_ISO).getTime() + 86400000)
    .toISOString().slice(0, 10);

  const deferMarker = 'Deferred from plan import';
  const existingNotes = (task.notes || '').trim();
  const newNotes = existingNotes ? (existingNotes + '; ' + deferMarker) : deferMarker;

  task.due_date   = tomorrow;
  task.confidence = 'high';
  task.notes      = newNotes;

  // Sync the visible inputs — collectApproved reads from these on apply.
  const dateEl  = document.getElementById('tf-date-'  + id);
  const notesEl = document.getElementById('tf-notes-' + id);
  if (dateEl)  dateEl.value  = tomorrow;
  if (notesEl) notesEl.value = newNotes;

  // Check the box and swap action area to the standard Remove button.
  const cb = document.getElementById('cb-' + id);
  if (cb) cb.checked = true;
  const actions = document.getElementById('actions-' + id);
  if (actions) actions.innerHTML = _taskActionsHtml(id, 'high');

  updateApplySummary();
  if (typeof _saveSession === 'function') _saveSession();
}

const PLACEMENT_DEST_LABELS = {
  'events.json':              '&#128197; Event note',
  'profiles/jp.json':         '&#128100; JP’s Profile',
  'profiles/joseph.json':     '&#128100; Joseph’s Profile',
  'profiles/michael.json':    '&#128100; Michael’s Profile',
  'profiles/james.json':      '&#128100; James’ Profile',
  'profiles/mom.json':        '&#128105; Mom’s Profile',
  'profiles/john.json':       '&#128100; John’s Profile',
  'friends.json':             '&#128101; Friend Family',
  'meal_inventory.json':      '&#127859; Pantry / Inventory',
  'prayer/intentions.json':   '&#128591; Prayer Intention',
  'thankyou_reminders.json':  '&#128140; Thank-You Reminder',
};

function placementDestLabel(dest) {
  return PLACEMENT_DEST_LABELS[dest] || ('&#128193; ' + (dest || 'unknown'));
}

function renderPlacementItem(p) {
  const conf   = p.confidence || 'medium';
  const action = (p.action || 'UPDATE').toLowerCase();
  const actionClass = ['update','append','create'].includes(action) ? action : 'update';
  const destLabel = placementDestLabel(p.destination);
  const fieldLabel = p.field ? ('· ' + esc(p.field)) : '';
  const matchLabel = p.match_hint ? esc(p.match_hint) : '—';
  return `<div class="placement-row" id="item-${p.id}">
    <div class="placement-main" onclick="toggleEdit('${p.id}')">
      <input type="checkbox" class="item-cb" id="cb-${p.id}" checked
             onclick="event.stopPropagation();updateApplySummary()">
      <div class="item-info">
        <div class="item-title">${destLabel} ${fieldLabel}</div>
        <div class="placement-dest">&rarr; ${matchLabel}</div>
      </div>
      <span class="action-badge ${actionClass}">${esc(p.action || 'update')}</span>
      <span class="item-conf conf-${conf}">${conf}</span>
      <span style="color:var(--ink-faint);font-size:0.75em;margin-left:4px;">&#9660;</span>
    </div>
    <div class="item-edit" id="edit-${p.id}">
      <div class="placement-meta-row">
        <span><strong>Destination:</strong> ${esc(p.destination || '')}</span>
        <span><strong>Field:</strong> ${esc(p.field || '')}</span>
        <span><strong>Match:</strong> ${matchLabel}</span>
      </div>
      <div class="edit-field">
        <label>Value (edit before applying)</label>
        <textarea class="placement-value" id="pf-value-${p.id}">${esc(p.value || '')}</textarea>
      </div>
      ${p.reason ? `<div class="placement-reason">&#128161; ${esc(p.reason)}</div>` : ''}
      <div style="margin-top:10px;display:flex;justify-content:flex-end;">
        <button class="pi-btn pi-btn-sm pi-btn-remove" onclick="removeItem('${p.id}')">
          &#128465; Remove
        </button>
      </div>
    </div>
  </div>`;
}

function toggleEdit(id) {
  const el = document.getElementById('edit-' + id);
  el.classList.toggle('open');
}

function removeItem(id) {
  const row = document.getElementById('item-' + id);
  if (row) row.remove();
  updateApplySummary();
}

function removeSubtask(tid, idx) {
  const el = document.getElementById('sti-' + tid + '-' + idx);
  if (el) el.remove();
}

function addSubtask(tid) {
  const list = document.getElementById('stl-' + tid);
  if (!list) return;
  const idx = list.children.length;
  const div = document.createElement('div');
  div.className = 'subtask-item';
  div.id = 'sti-' + tid + '-' + idx;
  div.innerHTML = `<input id="st-${tid}-${idx}" placeholder="Subtask…">
    <button class="subtask-del" onclick="removeSubtask('${tid}',${idx})">&#215;</button>`;
  list.appendChild(div);
}

function updateApplySummary() {
  const checked = document.querySelectorAll('.item-cb:checked').length;
  const total   = document.querySelectorAll('.item-cb').length;
  document.getElementById('apply-summary').innerHTML =
    `<strong>${checked}</strong> of ${total} items selected`;
  document.getElementById('apply-btn').disabled = checked === 0;
}

// ── Accept/Ignore counsel suggestions ─────────────────────────────────────
function acceptSuggestion(idx) {
  const row    = document.getElementById('sug-' + idx);
  const textEl = row ? row.querySelector('.sug-text') : null;
  const text   = textEl ? textEl.textContent.trim() : '';
  if (!text) return;

  const newTask = {
    id:         'sug-' + Date.now(),
    text,
    person:     'Lauren',
    due_date:   '',
    notes:      'From counsel suggestion',
    subtasks:   [],
    confidence: 'low',
  };

  if (!analysisData) analysisData = {events:[], tasks:[]};
  if (!analysisData.tasks) analysisData.tasks = [];
  analysisData.tasks.push(newTask);

  const list = document.getElementById('tasks-list');
  if (list) {
    const tmp = document.createElement('div');
    tmp.innerHTML = renderTaskItem(newTask);
    list.appendChild(tmp.firstElementChild);
  }

  const cnt = document.getElementById('task-count');
  if (cnt) cnt.textContent = (analysisData.tasks || []).length;
  document.getElementById('section-tasks').style.display = '';
  document.getElementById('apply-bar').style.display = 'flex';
  updateApplySummary();
  _saveSession();

  // Confirm and dismiss the suggestion row
  if (row) {
    row.style.background = '#f0fdf4';
    row.innerHTML = '<span style="color:#16a34a;font-size:0.82em;padding:4px 0;display:block;">&#10003; Added to tasks &mdash; edit it in the Tasks section below.</span>';
    setTimeout(() => row.remove(), 2200);
  }
}

function ignoreSuggestion(idx) {
  const row = document.getElementById('sug-' + idx);
  if (row) {
    row.style.transition = 'opacity .25s';
    row.style.opacity    = '0';
    setTimeout(() => row.remove(), 300);
  }
}

// ── Manual Add Task ────────────────────────────────────────────────────────
function showAddTaskForm(prefill) {
  const form    = document.getElementById('add-task-form');
  const showBtn = document.getElementById('show-add-task-btn');
  form.style.display = 'block';
  if (showBtn) showBtn.style.display = 'none';
  if (prefill) document.getElementById('new-task-text').value = prefill;
  setTimeout(() => document.getElementById('new-task-text').focus(), 50);
}

function cancelAddTask() {
  document.getElementById('add-task-form').style.display = 'none';
  const showBtn = document.getElementById('show-add-task-btn');
  if (showBtn) showBtn.style.display = '';
  document.getElementById('new-task-text').value  = '';
  document.getElementById('new-task-date').value  = '';
  document.getElementById('new-task-notes').value = '';
}

function submitManualTask() {
  const text = (document.getElementById('new-task-text').value || '').trim();
  if (!text) { document.getElementById('new-task-text').focus(); return; }

  const person   = document.getElementById('new-task-person').value;
  const due_date = document.getElementById('new-task-date').value;
  const notes    = (document.getElementById('new-task-notes').value || '').trim();

  const newTask = {
    id:         'manual-' + Date.now(),
    text, person, due_date, notes,
    subtasks:   [],
    confidence: 'high',
  };

  if (!analysisData) analysisData = {events:[], tasks:[]};
  if (!analysisData.tasks) analysisData.tasks = [];
  analysisData.tasks.push(newTask);

  const list = document.getElementById('tasks-list');
  if (list) {
    const tmp = document.createElement('div');
    tmp.innerHTML = renderTaskItem(newTask);
    list.appendChild(tmp.firstElementChild);
  }

  const cnt = document.getElementById('task-count');
  if (cnt) cnt.textContent = (analysisData.tasks || []).length;
  document.getElementById('section-tasks').style.display = '';
  document.getElementById('apply-bar').style.display = 'flex';
  updateApplySummary();
  _saveSession();
  cancelAddTask();
}

// ── Collect current state ──────────────────────────────────────────────────
function collectApproved() {
  if (!analysisData) return {events:[], tasks:[], project_label: ''};
  const projectLabel = (document.getElementById('project-label-input') || {}).value || '';
  const events = (analysisData.events || []).filter(ev => {
    const cb = document.getElementById('cb-' + ev.id);
    const row = document.getElementById('item-' + ev.id);
    return cb && cb.checked && row;
  }).map(ev => ({
    ...ev,
    title:    (document.getElementById('ef-title-' + ev.id)   || {}).value || ev.title,
    date:     (document.getElementById('ef-date-' + ev.id)    || {}).value || ev.date,
    time:     (document.getElementById('ef-time-' + ev.id)    || {}).value || ev.time || '',
    end_time: (document.getElementById('ef-endtime-' + ev.id) || {}).value || ev.end_time || '',
    who:      ((document.getElementById('ef-who-' + ev.id)    || {}).value || '').split(',').map(s=>s.trim()).filter(Boolean),
    notes:    (document.getElementById('ef-notes-' + ev.id)   || {}).value || ev.notes || '',
  }));

  const tasks = (analysisData.tasks || []).filter(t => {
    const cb = document.getElementById('cb-' + t.id);
    const row = document.getElementById('item-' + t.id);
    return cb && cb.checked && row;
  }).map(t => {
    const stList = document.getElementById('stl-' + t.id);
    const subtasks = stList
      ? Array.from(stList.querySelectorAll('input')).map(i => i.value.trim()).filter(Boolean)
      : (t.subtasks || []);
    return {
      ...t,
      text:     (document.getElementById('tf-text-' + t.id)   || {}).value || t.text,
      person:   (document.getElementById('tf-person-' + t.id) || {}).value || t.person,
      due_date: (document.getElementById('tf-date-' + t.id)   || {}).value || t.due_date || '',
      notes:    (document.getElementById('tf-notes-' + t.id)  || {}).value || t.notes || '',
      subtasks,
    };
  });

  const placements = (analysisData.placements || []).filter(p => {
    const cb = document.getElementById('cb-' + p.id);
    const row = document.getElementById('item-' + p.id);
    return cb && cb.checked && row;
  }).map(p => {
    const valueEl = document.getElementById('pf-value-' + p.id);
    const liveValue = valueEl ? valueEl.value : (p.value || '');
    return {
      id:          p.id,
      destination: p.destination || '',
      action:      p.action || 'UPDATE',
      match_hint:  p.match_hint || '',
      field:       p.field || '',
      value:       liveValue,
      confidence:  p.confidence || 'medium',
    };
  });

  // Pick up checked companion-suggestion cards (merge into the main events
  // and tasks arrays — no new payload key, the apply route is unchanged).
  document.querySelectorAll('.companion-suggestions .item-row').forEach(row => {
    const id = (row.id || '').replace(/^item-/, '');
    if (!id.startsWith('cs-')) return;
    const cb = document.getElementById('cb-' + id);
    if (!cb || !cb.checked) return;
    const stash = companionSuggestions[id];
    if (!stash) return;
    if (stash.kind === 'event') {
      const ev = stash.data;
      events.push({
        ...ev,
        title:    (document.getElementById('ef-title-' + id)   || {}).value || ev.title,
        date:     (document.getElementById('ef-date-' + id)    || {}).value || ev.date || '',
        time:     (document.getElementById('ef-time-' + id)    || {}).value || ev.time || '',
        end_time: (document.getElementById('ef-endtime-' + id) || {}).value || ev.end_time || '',
        who:      ((document.getElementById('ef-who-' + id)    || {}).value || '').split(',').map(s=>s.trim()).filter(Boolean),
        notes:    (document.getElementById('ef-notes-' + id)   || {}).value || ev.notes || '',
      });
    } else if (stash.kind === 'task') {
      const t = stash.data;
      const stList = document.getElementById('stl-' + id);
      const subtasks = stList
        ? Array.from(stList.querySelectorAll('input')).map(i => i.value.trim()).filter(Boolean)
        : (t.subtasks || []);
      tasks.push({
        ...t,
        text:     (document.getElementById('tf-text-' + id)   || {}).value || t.text,
        person:   (document.getElementById('tf-person-' + id) || {}).value || t.person,
        due_date: (document.getElementById('tf-date-' + id)   || {}).value || t.due_date || '',
        notes:    (document.getElementById('tf-notes-' + id)  || {}).value || t.notes || '',
        subtasks,
      });
    }
  });

  return {events, tasks, placements, project_label: projectLabel};
}

// ── Apply ──────────────────────────────────────────────────────────────────
async function applyPlan() {
  const btn = document.getElementById('apply-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Applying…';

  const payload = collectApproved();
  try {
    const resp = await fetch('/plan-import-apply', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error(await resp.text());
    const result = await resp.json();
    const evAdded = result.events_added || 0;
    const tAdded  = result.tasks_added  || 0;
    const pAdded  = result.placements_applied || 0;
    document.getElementById('success-body').innerHTML =
      `<strong>${evAdded} event${evAdded!==1?'s':''}</strong>,
       <strong>${tAdded} task${tAdded!==1?'s':''}</strong>,
       <strong>${pAdded} placement${pAdded!==1?'s':''}</strong> applied to the family plan.`;
    renderReceipt(result);
    _clearSession();
    showPhase('phase-receipt');
  } catch(err) {
    btn.disabled = false;
    btn.innerHTML = '&#9989; Apply Selected Items';
    alert('Apply failed: ' + err.message);
  }
}

// ── Receipt rendering ─────────────────────────────────────────────────────
function renderReceipt(result) {
  const receipt = Array.isArray(result.receipt) ? result.receipt : [];
  const events = receipt.filter(r => r.type === 'event');
  const tasks  = receipt.filter(r => r.type === 'task');
  const places = receipt.filter(r => r.type === 'placement');

  const evCount = result.events_added || 0;
  const tkCount = result.tasks_added  || 0;
  const plCount = result.placements_applied || 0;
  const total   = evCount + tkCount + plCount;
  document.getElementById('receipt-summary').textContent =
    `${total} item${total!==1?'s':''} filed to the family plan.`;

  document.getElementById('receipt-events-count').textContent = events.length;
  document.getElementById('receipt-tasks-count').textContent = tasks.length;
  document.getElementById('receipt-placements-count').textContent = places.length;

  document.getElementById('receipt-events-body').innerHTML =
    events.length ? events.map(renderReceiptRow).join('')
                  : '<div class="receipt-empty">No new events.</div>';
  document.getElementById('receipt-tasks-body').innerHTML =
    tasks.length ? tasks.map(renderReceiptRow).join('')
                 : '<div class="receipt-empty">No new tasks.</div>';
  document.getElementById('receipt-placements-body').innerHTML =
    places.length ? places.map(renderReceiptRow).join('')
                  : '<div class="receipt-empty">No placements filed.</div>';
}

let _receiptRowSeq = 0;
function renderReceiptRow(entry) {
  const rowId = 'rcpt-' + (++_receiptRowSeq);
  const label = esc(entry.label || '');
  const title = esc(entry.title || '(untitled)');
  const action = esc(entry.action || '');
  const fld = entry.field ? ' · field: ' + esc(entry.field) : '';
  const meta = entry.meta ? esc(entry.meta) : '';
  const preview = entry.value_preview
    ? '<div class="receipt-row-preview">' + esc(entry.value_preview) + '</div>' : '';
  const metaLine = (meta || fld || action)
    ? '<div class="receipt-row-meta">' + (action ? esc(action) : '')
      + (meta ? (action ? ' · ' : '') + meta : '')
      + fld + '</div>'
    : '';
  let undoCell = '';
  if (entry.undo_id) {
    undoCell = '<button class="receipt-undo-btn" id="' + rowId + '-btn" '
             + 'onclick="undoPlacement(\'' + entry.undo_id + '\',\'' + rowId + '\')">'
             + '&#8617; Undo</button>';
  }
  return '<div class="receipt-row" id="' + rowId + '">'
       +   '<div class="receipt-row-info">'
       +     '<div class="receipt-row-label">' + label + '</div>'
       +     '<div class="receipt-row-title">' + title + '</div>'
       +     preview + metaLine
       +   '</div>'
       +   undoCell
       + '</div>';
}

async function undoPlacement(undoId, rowId) {
  const row = document.getElementById(rowId);
  const btn = document.getElementById(rowId + '-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Undoing…'; }
  try {
    const resp = await fetch('/plan-import-undo-placement', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({undo_id: undoId}),
    });
    const result = await resp.json();
    if (result.ok) {
      if (row) row.classList.add('undone');
      if (btn) {
        btn.outerHTML = '<span class="receipt-undo-status">&#8617; Undone</span>';
      }
    } else {
      if (btn) {
        btn.outerHTML = '<span class="receipt-undo-status">Can\'t undo: '
                      + esc(result.reason || 'unknown') + '</span>';
      }
    }
  } catch(err) {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '↩ Undo';
    }
    alert('Undo failed: ' + err.message);
  }
}

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// ── Auto-restore on page load ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  _restoreSession();
});
