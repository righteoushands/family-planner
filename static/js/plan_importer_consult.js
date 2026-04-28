// plan_importer_consult.js
// Companion consultation, council, and suggestion logic for /plan-import.
// Depends on plan_importer_core.js being loaded first.

// ── Group Council ─────────────────────────────────────────────────────────
const COMPANION_VOICE_COLORS = {
  'Father Gregory': '#1e3566',
  'Lorenzo':        '#8b3a1a',
  'Coach':          '#1a6e3e',
  'Dr. Monica':     '#8b3a5c',
  "Lucy's Synthesis": '#5b3a8a',
  'Lucy':           '#5b3a8a',
};

// Map of companion key → (display name, accent color) for the suggestions strip
const COMPANION_KEY_DISPLAY = {
  lucy: 'Lucy', lorenzo: 'Lorenzo', gregory: 'Father Gregory',
  coach: 'Coach', monica: 'Dr. Monica',
};
const COMPANION_KEY_ACCENT = {
  lucy: '#5b3a8a', lorenzo: '#8b3a1a', gregory: '#1e3566',
  coach: '#1a6e3e', monica: '#8b3a5c',
};

// Stash of suggestion items keyed by their cs-* id, so collectApproved() can
// look them back up when the user clicks Apply.
const companionSuggestions = {};

async function extractCompanionSuggestions(companionName, responseText) {
  if (!responseText || responseText.trim().length < 10) {
    return {tasks:[], events:[]};
  }
  try {
    const body = new URLSearchParams({
      companion: companionName || 'Companion',
      text:      responseText,
    });
    const resp = await fetch('/api/extract-suggestions', {method:'POST', body});
    if (!resp.ok) return {tasks:[], events:[]};
    const data = await resp.json();
    return {
      tasks:  Array.isArray(data.tasks)  ? data.tasks  : [],
      events: Array.isArray(data.events) ? data.events : [],
    };
  } catch(_) {
    return {tasks:[], events:[]};
  }
}

function renderCompanionSuggestions(headerLabel, accentColor, items, mountAfterEl) {
  if (!items) return null;
  const evs = items.events || [];
  const ts  = items.tasks  || [];
  if (!evs.length && !ts.length) return null;
  if (!mountAfterEl || !mountAfterEl.parentNode) return null;
  const wrap = document.createElement('div');
  wrap.className = 'companion-suggestions';
  if (accentColor) wrap.style.borderLeftColor = accentColor;
  let html = `<div class="companion-suggestions-header">${esc(headerLabel)}</div>`;
  for (const ev of evs) {
    companionSuggestions[ev.id] = {kind:'event', data: ev};
    html += renderEventItem(ev);
  }
  for (const t of ts) {
    companionSuggestions[t.id] = {kind:'task', data: t};
    html += renderTaskItem(t);
  }
  wrap.innerHTML = html;
  mountAfterEl.parentNode.insertBefore(wrap, mountAfterEl.nextSibling);
  return wrap;
}

function selectPreset(btn, text) {
  document.querySelectorAll('.council-preset').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
  document.getElementById('council-input').value = text;
}

// Auto-fire the "Quick review" council the moment results render. Guarded so
// it never runs over a council the user has already seen or convened.
function autoConveneCouncil() {
  if (!_freshAnalysis) return;
  const panel = document.getElementById('consult-panel');
  if (!panel || panel.style.display === 'none') return;
  const thread = document.getElementById('council-thread');
  if (!thread || thread.innerHTML.trim() !== '') return;

  let quickBtn = null;
  document.querySelectorAll('.council-preset').forEach(b => {
    if (!quickBtn && b.textContent && b.textContent.indexOf('Quick review') !== -1) {
      quickBtn = b;
    }
  });
  if (!quickBtn) return;

  selectPreset(quickBtn, 'Quick check — anything missing or that we might regret skipping?');
  conveneCouncil();
}

async function conveneCouncil() {
  const inp = document.getElementById('council-input');
  const question = inp.value.trim();
  if (!question) { inp.focus(); return; }

  const btn    = document.getElementById('council-btn');
  const resp   = document.getElementById('council-response');
  const thread = document.getElementById('council-thread');

  btn.disabled = true;
  btn.textContent = '…';
  resp.style.display = 'block';
  thread.innerHTML = '<div class="council-thinking">The companions are conferring…</div>';

  // Clear any prior council suggestion strips from previous runs — they're
  // mounted as siblings of #council-thread, so resetting thread.innerHTML
  // alone leaves them stranded in the DOM where collectApproved would still
  // pick them up.
  let _staleSugg = thread.nextElementSibling;
  while (_staleSugg && _staleSugg.classList && _staleSugg.classList.contains('companion-suggestions')) {
    const _next = _staleSugg.nextElementSibling;
    _staleSugg.remove();
    _staleSugg = _next;
  }

  // Collect currently displayed companion keys
  const compKeys = Array.from(document.querySelectorAll('.companion-btn'))
    .map(b => b.id.replace('cbtn-',''))
    .filter(Boolean);

  const body = new URLSearchParams({
    question:   question,
    companions: JSON.stringify(compKeys),
    plan_json:  JSON.stringify(analysisData || {})
  });

  try {
    const r = await fetch('/plan-import-group-consult', {method:'POST', body});
    if (!r.ok) throw new Error(await r.text());

    const reader  = r.body.getReader();
    const decoder = new TextDecoder();
    let   fullText = '';

    thread.innerHTML = '';
    let streamEl = document.createElement('div');
    streamEl.style.cssText = 'font-size:.82em;line-height:1.55;color:var(--ink);white-space:pre-wrap;';
    thread.appendChild(streamEl);

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      fullText += decoder.decode(value, {stream: true});
      streamEl.textContent = fullText;
      thread.scrollIntoView({block:'nearest'});
    }

    // Parse and render formatted voices
    thread.innerHTML = parseCouncilResponse(fullText);

    // Seed each companion's chat history with the council exchange so 1-on-1
    // chats pick up where the council left off. Silent — best-effort.
    try { seedCompanionHistoriesFromCouncil(question, fullText, compKeys); } catch(_) {}

    // Run extraction on the full council text (best-effort, never blocks UI)
    try {
      const sugg = await extractCompanionSuggestions('Council', fullText);
      renderCompanionSuggestions('💡 Council Suggestions', '#5b3a8a', sugg, thread);
      thread.scrollIntoView({block:'nearest'});
    } catch(_) {}
  } catch(err) {
    thread.innerHTML = `<div class="council-error">Council failed: ${esc(err.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Convene &#x2728;';
  }
}

function parseCouncilResponse(text) {
  // Split on **Name:** pattern
  const parts = text.split(/\*\*([^*]+)\*\*:/);
  let html = '';
  for (let i = 1; i < parts.length; i += 2) {
    const name    = parts[i].trim();
    const content = (parts[i+1] || '').trim();
    const color   = COMPANION_VOICE_COLORS[name] || '#666';
    const isSynth = name.includes('Synthesis') || name === 'Lucy';
    html += `<div class="${isSynth ? 'council-synthesis' : 'council-voice'}" style="border-left-color:${color};">
      <div class="council-voice-name" style="color:${color};">${esc(name)}</div>
      <div class="council-voice-text">${esc(content)}</div>
      <div style="margin-top:8px;text-align:right;">
        <button class="pi-btn pi-btn-sm pi-btn-edit"
                style="font-size:0.72em;padding:3px 10px;"
                data-prefill="${esc(content.slice(0,120))}"
                onclick="showAddTaskForm(this.getAttribute('data-prefill'))">
          &#43; Make this a task
        </button>
      </div>
    </div>`;
  }
  return html || `<div class="council-voice-text" style="padding:6px;">${esc(text)}</div>`;
}

// Pre-load each companion's chat history with the council exchange so 1-on-1
// chats start in continuity instead of cold. Silent: nothing renders until
// Lauren actually opens that companion's chat. Never overwrites a companion
// the user has already chatted with.
function seedCompanionHistoriesFromCouncil(question, fullText, compKeys) {
  if (!fullText || !compKeys || !compKeys.length) return;

  const ev = (analysisData && analysisData.events) ? analysisData.events.length : 0;
  const tk = (analysisData && analysisData.tasks)  ? analysisData.tasks.length  : 0;
  const planSummary = '(' + ev + ' event' + (ev === 1 ? '' : 's')
                    + ', ' + tk + ' task' + (tk === 1 ? '' : 's') + ' in plan)';
  const userTurn = question + '\n\n' + planSummary;

  // Map display-name → that companion's section, using the same **Name:**
  // marker pattern parseCouncilResponse already splits on.
  const sectionByName = {};
  const parts = fullText.split(/\*\*([^*]+)\*\*:/);
  for (let i = 1; i < parts.length; i += 2) {
    const nm = (parts[i] || '').trim();
    const ct = (parts[i+1] || '').trim();
    if (nm) sectionByName[nm] = ct;
  }

  for (const key of compKeys) {
    if (consultHistories[key] && consultHistories[key].length > 0) continue;
    const display = COMPANION_KEY_DISPLAY[key] || key;
    const section = sectionByName[display] || fullText;
    consultHistories[key] = [
      { role: 'user',      content: userTurn },
      { role: 'assistant', content: section  }
    ];
  }
}

// ── Companion Consultation ─────────────────────────────────────────────────
let activeCompanion = null;      // current companion key
let consultHistories = {};      // key -> [{role, content}]

function renderCompanionPanel(companions) {
  if (!companions || !companions.length) return;
  const panel = document.getElementById('consult-panel');
  const row   = document.getElementById('companion-row');
  if (!panel || !row) return;

  row.innerHTML = companions.map(c => `
    <button class="companion-btn" id="cbtn-${c.key}"
            style="background:${c.color};"
            onclick="openCompanionChat('${c.key}','${esc(c.label)}','${c.color}','${esc(c.emoji)}','${esc(c.role)}')">
      ${c.emoji} ${esc(c.label)} <span style="opacity:.75;font-weight:400;">&middot; ${esc(c.role)}</span>
    </button>
  `).join('');

  panel.style.display = '';
}

function openCompanionChat(key, label, color, emoji, role) {
  // Toggle if already active
  if (activeCompanion === key) {
    closeConsultChat();
    return;
  }
  activeCompanion = key;
  if (!consultHistories[key]) consultHistories[key] = [];

  // Update active state on buttons
  document.querySelectorAll('.companion-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('cbtn-' + key);
  if (btn) btn.classList.add('active');

  // Update chat header
  document.getElementById('consult-chat-emoji').textContent = emoji;
  const nameEl = document.getElementById('consult-chat-name');
  nameEl.textContent = label + ' · ' + role;
  nameEl.style.color = color;
  document.getElementById('consult-send-btn').style.background = color;

  // Show chat area
  const chatArea = document.getElementById('consult-chat-area');
  chatArea.style.display = '';
  chatArea.style.borderTopColor = color + '40';

  // Render existing history
  renderConsultHistory();

  // If no history, send an opening "review" message automatically.
  // IMPORTANT: a companion seeded by seedCompanionHistoriesFromCouncil() has
  // length === 2, so this gate naturally skips the auto-opener — Lauren's
  // first typed message is the one that lands at the server, carrying the
  // seeded council context as history. Do NOT remove this gate.
  if (consultHistories[key].length === 0) {
    autoOpenConsult(key);
  }

  // Focus input
  setTimeout(() => document.getElementById('consult-input').focus(), 100);
}

function closeConsultChat() {
  activeCompanion = null;
  document.querySelectorAll('.companion-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('consult-chat-area').style.display = 'none';
}

function renderConsultHistory() {
  const msgs = consultHistories[activeCompanion] || [];
  const box  = document.getElementById('consult-messages');
  box.innerHTML = msgs.map(m => m.role === 'user'
    ? `<div class="cmsg-user">${esc(m.content)}</div>`
    : `<div class="cmsg-ai">${m.content}</div>`
  ).join('');
  box.scrollTop = box.scrollHeight;
}

async function autoOpenConsult(key) {
  const openMsg = 'Please review the parsed plan and give me your expert perspective.';
  await runConsultMessage(key, openMsg, true);
}

async function consultSend() {
  if (!activeCompanion) return;
  const inp = document.getElementById('consult-input');
  const msg = inp.value.trim();
  if (!msg) return;
  inp.value = '';
  await runConsultMessage(activeCompanion, msg, false);
}

async function runConsultMessage(key, message, isAuto) {
  if (!consultHistories[key]) consultHistories[key] = [];

  // Add user message (show only if not auto)
  if (!isAuto) {
    consultHistories[key].push({role:'user', content: message});
    renderConsultHistory();
  }

  // Show thinking
  const box = document.getElementById('consult-messages');
  const thinkEl = document.createElement('div');
  thinkEl.className = 'cmsg-thinking';
  thinkEl.id = 'consult-thinking';
  thinkEl.textContent = '…';
  box.appendChild(thinkEl);
  box.scrollTop = box.scrollHeight;

  // Disable input
  const sendBtn = document.getElementById('consult-send-btn');
  const inp     = document.getElementById('consult-input');
  sendBtn.disabled = true; inp.disabled = true;

  // Build history to send. Always honor existing history (including any
  // seeded council context); only drop the just-pushed user turn for non-auto
  // sends. The original isAuto-zeroes-history behavior is preserved for
  // first-time-empty-history opens (slice([0,-1]) of [] is still []), and
  // seeded companions never reach this path with isAuto=true anyway.
  let histToSend = [...consultHistories[key]];
  if (!isAuto) histToSend = histToSend.slice(0, -1);

  const body = new URLSearchParams({
    companion: key,
    message:   message,
    history:   JSON.stringify(histToSend),
    plan_json: JSON.stringify(analysisData || {})
  });

  try {
    const resp = await fetch('/plan-import-consult', {method:'POST', body});
    if (!resp.ok) throw new Error(await resp.text());

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let text = '';

    // Replace thinking with streaming bubble
    thinkEl.remove();
    const aiEl = document.createElement('div');
    aiEl.className = 'cmsg-ai';
    box.appendChild(aiEl);

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      text += decoder.decode(value, {stream:true});
      aiEl.textContent = text;
      box.scrollTop = box.scrollHeight;
    }

    // Save to history
    if (!isAuto) {
      consultHistories[key].push({role:'assistant', content: text});
    } else {
      // Auto message: just show the response (don't save user turn to history)
      consultHistories[key].push({role:'assistant', content: text});
    }

    // Run extraction on the assistant reply (best-effort, never blocks UI)
    try {
      const display = COMPANION_KEY_DISPLAY[key] || key;
      const accent  = COMPANION_KEY_ACCENT[key]  || '#5b3a8a';
      const sugg    = await extractCompanionSuggestions(display, text);
      renderCompanionSuggestions(
        '💡 Suggested by ' + display, accent, sugg, aiEl
      );
      box.scrollTop = box.scrollHeight;
    } catch(_) {}
  } catch(err) {
    thinkEl.remove();
    const errEl = document.createElement('div');
    errEl.className = 'cmsg-thinking';
    errEl.textContent = 'Error: ' + err.message;
    box.appendChild(errEl);
  } finally {
    sendBtn.disabled = false; inp.disabled = false;
    inp.focus();
  }
}

