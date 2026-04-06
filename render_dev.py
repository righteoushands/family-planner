"""
render_dev.py — Felix, the Sancta Familia built-in programmer.

Felix is a skilled, friendly software developer who knows this codebase
inside and out. He can diagnose bugs, read relevant source files, propose
precise code fixes, and — with Lauren's approval — apply those fixes
directly to the live codebase.

Admin-only. API:
  POST /dev-chat          — streaming chat (may contain [FIX:…] blocks)
  POST /dev-apply         — apply a code fix (find/replace in a file)
  POST /dev-restart       — gracefully restart the server
  POST /dev-clear         — clear Felix's chat history
"""

import os
import re
import json
from html import escape
from datetime import datetime
from pathlib import Path

# ── File-detection keyword map ────────────────────────────────────────────────
# Maps message keywords → source files Felix should read for context
_KEYWORD_FILES: list[tuple[list[str], str]] = [
    (["plan import", "plan-import", "analyze", "apply plan", "council", "consult"],
     "render_plan_importer.py"),
    (["lucy", "integrator", "family rules", "lucy chat"],                   "render_lucy.py"),
    (["lorenzo", "chef", "meal chat"],                                       "render_lorenzo.py"),
    (["father gregory", "gregory", "headmaster", "homeschool chat"],        "render_gregory.py"),
    (["coach", "fitness chat"],                                              "render_coach.py"),
    (["dr. monica", "monica", "child development"],                         "render_monica.py"),
    (["calendar", "events", "ical", "subscribe"],                           "render_calendar.py"),
    (["chores", "van", "laundry", "rotation"],                              "render_chores.py"),
    (["meals", "recipe", "meal plan", "menu"],                              "render_meals.py"),
    (["settings", "api key", "anthropic", "pin", "theme"],                  "render_settings.py"),
    (["login", "logout", "auth", "session", "pin"],                         "auth.py"),
    (["schedule", "slot", "today", "/today", "daily plan"],                 "render_schedule.py"),
    (["5am", "morning", "gratitude", "journal", "autosave"],                "render_5am.py"),
    (["morning anchor", "anchor", "brain dump"],                            "render_morning_anchor.py"),
    (["prayer", "intention", "rosary"],                                     "render_prayer.py"),
    (["friends", "family book", "playdate"],                                "render_friends.py"),
    (["goals", "child goals", "substep"],                                   "render_child_goals.py"),
    (["child profile", "profile"],                                          "render_child_profile.py"),
    (["mom profile", "lauren profile"],                                     "render_mom_profile.py"),
    (["memory book"],                                                        "render_memory_book.py"),
    (["virtues", "virtue"],                                                  "render_virtues.py"),
    (["nav", "navigation", "top_nav", "html_page", "ui_helpers"],           "ui_helpers.py"),
    (["data_helpers", "load_", "save_", "history", "json file"],            "data_helpers.py"),
    (["route", "handler", "endpoint", "app.py", "path =="],                 "app.py"),
    (["daily_schedule", "engine", "build_schedule", "CHILDREN"],            "daily_schedule_engine.py"),
]

_MAX_FILE_CHARS = 6_000    # chars per injected file (~1.5k tokens — use [READ:] for more)
_MAX_FILES      = 2        # inject at most 2 files per request


def _get_relevant_files(message: str) -> list[tuple[str, str]]:
    """Return [(filename, content), …] for files relevant to this message."""
    msg_lower = message.lower()
    seen: list[str] = []
    results: list[tuple[str, str]] = []

    # 1. Explicit filename mentions (e.g. "render_lucy.py")
    for fname in os.listdir("."):
        if fname.endswith(".py") and fname in message:
            if fname not in seen:
                seen.append(fname)

    # 2. Keyword matching
    for keywords, fname in _KEYWORD_FILES:
        if any(kw in msg_lower for kw in keywords):
            if fname not in seen:
                seen.append(fname)
        if len(seen) >= _MAX_FILES:
            break

    for fname in seen[:_MAX_FILES]:
        try:
            content = Path(fname).read_text(encoding="utf-8")
            if len(content) > _MAX_FILE_CHARS:
                content = content[:_MAX_FILE_CHARS] + "\n\n… [truncated — ask for a specific section]"
            results.append((fname, content))
        except Exception:
            pass
    return results


# ── Architecture overview (always included) ───────────────────────────────────
def _app_overview() -> str:
    try:
        readme = Path("replit.md").read_text(encoding="utf-8")
        if len(readme) > 4000:
            readme = readme[:4000] + "\n…[truncated]"
        return readme
    except Exception:
        return "Sancta Familia — Python HTTP server on port 5000. Render modules return HTML strings."


def _file_listing() -> str:
    try:
        py_files = sorted(f for f in os.listdir(".") if f.endswith(".py"))
        return "\n".join(py_files)
    except Exception:
        return ""


# ── System prompt ─────────────────────────────────────────────────────────────
def build_felix_context() -> str:
    overview  = _app_overview()
    file_list = _file_listing()
    return f"""You are Felix, the built-in programmer for the Sancta Familia family dashboard.

════════════ APP OVERVIEW ════════════
{overview}

════════════ SOURCE FILES ════════════
{file_list}

════════════ RESPONSE RULES — follow these strictly ════════════
- Keep ALL replies to 1-3 short sentences. Never write more.
- NEVER show code in your text. Code goes only inside [FIX:] blocks.
- No bullet lists, no headers, no long explanations.
- If you need to read a file before answering, do that first with [READ:].
- If something can't be fixed, say so in one sentence.

════════════ YOUR TOOLS ════════════
READ FILES: [READ: filename.py:start_line-end_line]
  ALWAYS include line numbers. Example: [READ: app.py:100-200]
  Use this before proposing any fix. For large files, read 50-100 lines at a time.

APPLY FIXES: Use this exact format — Lauren sees a clean Apply button, no code shown:

[FIX: filename.py]
WHAT: One plain-English sentence describing what changes (e.g. "Increase body font from 15px to 16px")
FIND:
<exact text to replace — include 3-5 lines for context>
REPLACE:
<new text>
[/FIX]

  Rules: FIND must match the file exactly. One change per block. Correct indentation.
  Server restarts automatically after apply.

════════════ LIMITS ════════════
- Cannot run code or test fixes — always say "apply and restart to check".
- Cannot see the browser unless Lauren sends a screenshot.
- Uncertain? Say so in one sentence. Never guess with false confidence.

════════════ PERSONALITY ════════════
- Warm, brief, plain English. Lauren is not a developer.
- One clear answer beats three vague ones.
"""


# ── Render page ───────────────────────────────────────────────────────────────
def render_dev_page(history: list) -> str:
    from ui_helpers import html_page, top_nav

    # Build prior messages HTML
    msg_html = ""
    for m in history:
        role    = m.get("role", "user")
        content = m.get("content", "")
        ts      = m.get("ts", "")
        if role == "user":
            msg_html += _user_bubble(content, ts)
        elif role == "assistant":
            msg_html += _felix_bubble(content, ts)

    body = f"""
{top_nav()}

<div style="max-width:680px;margin:0 auto;padding:10px 14px 130px;">

  <!-- Compact Header -->
  <div style="display:none;background:linear-gradient(135deg,#1e3a8a 0%,#1e40af 60%,#2563eb 100%);
              border-radius:16px;padding:20px 20px 16px;margin-bottom:16px;">
  </div>

  <!-- ── Compact top bar ───────────────────────────────────────────────── -->
  <div style="display:flex;align-items:center;gap:10px;padding:8px 2px 12px;">
    <div style="width:38px;height:38px;border-radius:50%;
                background:linear-gradient(135deg,#1e3a8a,#3b82f6);
                display:flex;align-items:center;justify-content:center;
                font-size:1.1em;flex-shrink:0;">&#128187;</div>
    <div style="flex:1;">
      <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.25em;
                  font-weight:700;color:#1e3a8a;line-height:1.1;">The Help Desk</div>
      <div style="font-size:0.72em;color:#94a3b8;">
        Felix &middot; reads code &middot; checks errors &middot; applies fixes
      </div>
    </div>
    <button onclick="restartServer()" id="restart-btn"
            title="Restart the server after a fix has been applied"
            style="padding:5px 11px;font-size:0.76em;border-radius:8px;
                   border:1.5px solid #f59e0b;background:#fffbeb;color:#92400e;
                   font-family:inherit;cursor:pointer;font-weight:600;">
      &#128260; Restart
    </button>
    <form method="POST" action="/dev-clear" style="display:inline;">
      <button type="submit"
              title="Clear Felix&rsquo;s conversation and start fresh"
              style="padding:5px 10px;font-size:0.76em;border-radius:8px;
                     border:1.5px solid #e2e8f0;background:white;color:#94a3b8;
                     font-family:inherit;cursor:pointer;">
        &#128465;
      </button>
    </form>
  </div>

  <!-- ── Capability intro (shown only when no history yet) ────────────── -->
  {'<div id="felix-intro" style="background:#f0f9ff;border:1.5px solid #bae6fd;border-radius:14px;padding:16px 18px;margin-bottom:16px;">' if not msg_html else '<div id="felix-intro" style="display:none;">'}
    <div style="font-family:\'Cormorant Garamond\',Georgia,serif;font-size:1.05em;font-weight:700;
                color:#0369a1;margin-bottom:10px;">What Felix can do for you</div>
    <div style="display:grid;gap:8px;">
      <div style="display:flex;gap:10px;align-items:flex-start;">
        <span style="font-size:1.1em;flex-shrink:0;">&#128680;</span>
        <div style="font-size:0.8em;color:#334155;line-height:1.5;">
          <strong>See live errors automatically.</strong> Every time you send a message,
          Felix quietly reads the most recent server log so he already knows about
          any tracebacks or crashes &mdash; you don&rsquo;t have to paste anything.
        </div>
      </div>
      <div style="display:flex;gap:10px;align-items:flex-start;">
        <span style="font-size:1.1em;flex-shrink:0;">&#128196;</span>
        <div style="font-size:0.8em;color:#334155;line-height:1.5;">
          <strong>Read any source file himself.</strong> When Felix needs to see code,
          he requests the exact section he needs and the page fetches it for him
          automatically &mdash; no copy-pasting required.
        </div>
      </div>
      <div style="display:flex;gap:10px;align-items:flex-start;">
        <span style="font-size:1.1em;flex-shrink:0;">&#128295;</span>
        <div style="font-size:0.8em;color:#334155;line-height:1.5;">
          <strong>Propose and apply code fixes.</strong> When Felix has a solution,
          he shows exactly what changes &mdash; green for added, red for removed.
          Tap <strong>Apply Fix</strong> and the file is updated instantly. Then hit
          <strong>Restart</strong> to make it live.
        </div>
      </div>
      <div style="display:flex;gap:10px;align-items:flex-start;">
        <span style="font-size:1.1em;flex-shrink:0;">&#128172;</span>
        <div style="font-size:0.8em;color:#334155;line-height:1.5;">
          <strong>Just describe the problem.</strong> You don&rsquo;t need to know which
          file it&rsquo;s in or what the error means. Tell Felix what&rsquo;s broken
          in plain English and he&rsquo;ll figure out the rest.
        </div>
      </div>
    </div>
    <div style="margin-top:12px;display:flex;gap:6px;flex-wrap:wrap;">
      <button onclick="quickMsg('Can you explain how this app is structured?')" class="q-chip">App overview</button>
      <button onclick="quickMsg('Check the recent error log and tell me what is wrong.')" class="q-chip">Diagnose errors</button>
      <button onclick="quickMsg('Something is broken. Here is what I see: ')" class="q-chip">Debug something</button>
      <button onclick="quickMsg('Read render_plan_importer.py and look for bugs.')" class="q-chip">Audit a file</button>
    </div>
  </div>
  <style>
    .q-chip {{
      padding:5px 12px;font-size:0.78em;border-radius:20px;
      border:1.5px solid #bae6fd;background:#e0f2fe;color:#0369a1;
      font-family:inherit;cursor:pointer;font-weight:600;
    }}
    .q-chip:hover {{ background:#bae6fd; }}
  </style>

  <!-- Chat messages -->
  <div id="felix-msgs" style="display:flex;flex-direction:column;gap:14px;margin-bottom:8px;">
    {msg_html if msg_html else _welcome_bubble()}
  </div>

  <!-- Thinking indicator -->
  <div id="felix-thinking" style="display:none;padding:12px 16px;background:#eff6ff;
       border-radius:12px;font-size:0.85em;color:#1d4ed8;margin-bottom:8px;">
    <span>&#9679;&#9679;&#9679;</span> Felix is reading the code&hellip;
  </div>

  <!-- Error -->
  <div id="felix-error" style="display:none;padding:10px 14px;background:#fef2f2;
       border-radius:10px;font-size:0.82em;color:#dc2626;margin-bottom:8px;"></div>

  <!-- Restart toast -->
  <div id="restart-toast" style="display:none;position:fixed;top:80px;left:50%;transform:translateX(-50%);
       background:#1e3a8a;color:white;padding:10px 20px;border-radius:12px;z-index:9999;
       font-size:0.85em;font-weight:600;">Server restarting&hellip; refresh in 5 seconds.</div>

</div>

<!-- Fixed input bar -->
<div style="position:fixed;bottom:64px;left:0;right:0;background:#fdf8f0;
            border-top:1px solid #e2e8f0;padding:8px 14px;z-index:1000;">
  <div style="max-width:680px;margin:0 auto;">

    <!-- Image preview strip (hidden until image is attached) -->
    <div id="felix-img-preview" style="display:none;align-items:center;gap:8px;
         padding:6px 10px;margin-bottom:6px;background:#eff6ff;border-radius:10px;
         border:1.5px solid #bfdbfe;">
      <img id="felix-img-thumb" style="height:48px;width:auto;border-radius:6px;
           object-fit:cover;border:1px solid #dbeafe;">
      <div style="flex:1;font-size:0.75em;color:#1d4ed8;">
        Screenshot attached &mdash; Felix will see this image.
      </div>
      <button onclick="clearImage()"
              style="padding:2px 8px;border-radius:6px;border:1px solid #bfdbfe;
                     background:white;color:#3b82f6;font-size:0.75em;cursor:pointer;">
        ✕ Remove
      </button>
    </div>

    <!-- Input row -->
    <div style="display:flex;gap:8px;align-items:flex-end;">
      <input type="file" id="felix-img-input" accept="image/*" style="display:none"
             onchange="handleImageSelect(event)">
      <button onclick="document.getElementById('felix-img-input').click()"
              id="felix-cam-btn"
              title="Attach a screenshot so Felix can see the problem"
              style="padding:10px 11px;border:1.5px solid #dbeafe;border-radius:12px;
                     background:white;color:#3b82f6;font-size:1.1em;cursor:pointer;
                     flex-shrink:0;line-height:1;">
        &#128247;
      </button>
      <textarea id="felix-input" rows="2"
                placeholder="Describe the problem, or just say what&rsquo;s broken&hellip;"
                style="flex:1;padding:10px 12px;border:1.5px solid #dbeafe;border-radius:12px;
                       font-family:inherit;font-size:0.88em;resize:none;outline:none;
                       background:#fff;max-height:120px;"
                onkeydown="if(event.key==='Enter'&&!event.shiftKey){{event.preventDefault();sendToFelix();}}"></textarea>
      <button onclick="sendToFelix()" id="felix-send"
              style="padding:10px 18px;background:#1e3a8a;color:white;border:none;border-radius:12px;
                     font-family:inherit;font-size:0.88em;font-weight:700;cursor:pointer;white-space:nowrap;">
        Send
      </button>
    </div>
  </div>
</div>

<script>
// ── Image attachment ───────────────────────────────────────────────────────
let _pendingImage = null;  // {{ base64, mediaType }}

function handleImageSelect(evt) {{
  const file = evt.target.files[0];
  if (!file) return;
  resizeAndEncode(file).then(img => {{
    _pendingImage = img;
    const thumb = document.getElementById('felix-img-thumb');
    const preview = document.getElementById('felix-img-preview');
    thumb.src = 'data:' + img.mediaType + ';base64,' + img.base64;
    preview.style.display = 'flex';
    // Tint the camera button to show active state
    document.getElementById('felix-cam-btn').style.background = '#dbeafe';
  }});
  evt.target.value = '';  // allow re-selecting the same file
}}

function clearImage() {{
  _pendingImage = null;
  document.getElementById('felix-img-preview').style.display = 'none';
  document.getElementById('felix-img-thumb').src = '';
  document.getElementById('felix-cam-btn').style.background = 'white';
}}

function resizeAndEncode(file) {{
  return new Promise(resolve => {{
    const reader = new FileReader();
    reader.onload = e => {{
      const img = new Image();
      img.onload = () => {{
        const MAX = 1280;
        let w = img.width, h = img.height;
        if (w > MAX || h > MAX) {{
          if (w > h) {{ h = Math.round(h * MAX / w); w = MAX; }}
          else {{ w = Math.round(w * MAX / h); h = MAX; }}
        }}
        const canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
        resolve({{ base64: dataUrl.split(',')[1], mediaType: 'image/jpeg' }});
      }};
      img.src = e.target.result;
    }};
    reader.readAsDataURL(file);
  }});
}}

// ── Quick prompts ──────────────────────────────────────────────────────────
function quickMsg(text) {{
  document.getElementById('felix-input').value = text;
  sendToFelix();
}}

// ── Send message ──────────────────────────────────────────────────────────
async function sendToFelix() {{
  const inp  = document.getElementById('felix-input');
  const text = inp.value.trim();
  if (!text && !_pendingImage) return;  // need at least something
  inp.value = '';

  // Collapse the capability intro after first message
  const intro = document.getElementById('felix-intro');
  if (intro) intro.style.display = 'none';

  const box    = document.getElementById('felix-msgs');
  const errEl  = document.getElementById('felix-error');
  const thinkEl= document.getElementById('felix-thinking');
  errEl.style.display = 'none';

  // Grab and clear the pending image before building the bubble so it appears in it
  const imageToSend = _pendingImage;
  clearImage();

  // If only a screenshot was sent with no text, give Felix a prompt
  const payload = text || (imageToSend ? 'Here\u2019s a screenshot \u2014 please review it and let me know what you see or what might need fixing.' : '');

  // Append user bubble immediately (shows the clean text + thumbnail if image attached)
  box.appendChild(buildUserBubble(payload, imageToSend));
  box.scrollTop = box.scrollHeight;

  setThinking('Checking server logs\u2026');

  // ── Auto-fetch recent log tail to give Felix live context ────────────
  let logContext = '';
  try {{
    const logResp = await fetch('/dev-logs');
    if (logResp.ok) {{
      const logText = await logResp.text();
      const logLines = logText.split('\\n').filter(l => l.trim());
      const tail = logLines.slice(-10).join('\\n');
      if (tail) {{
        logContext = '\\n\\n[SERVER LOG \u2014 last 10 lines, for your reference only:\\n' + tail + '\\n]';
      }}
    }}
  }} catch(e) {{}}

  setThinking('Felix is thinking\u2026');
  await streamFelix(payload + logContext, false, imageToSend);
}}

// ── Core streaming function (reusable for auto-reads) ─────────────────
async function streamFelix(payload, isAutoRead, image) {{
  const box    = document.getElementById('felix-msgs');
  const errEl  = document.getElementById('felix-error');
  const thinkEl= document.getElementById('felix-thinking');
  document.getElementById('felix-send').disabled = true;

  try {{
    let formBody = 'message=' + encodeURIComponent(payload);
    if (image) {{
      formBody += '&image_data=' + encodeURIComponent(image.base64)
               + '&image_type=' + encodeURIComponent(image.mediaType);
    }}
    const resp = await fetch('/dev-chat', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
      body: formBody,
    }});
    if (!resp.ok) throw new Error(await resp.text());

    thinkEl.style.display = 'none';
    const bubble = buildFelixBubble('');
    box.appendChild(bubble);
    box.scrollTop = box.scrollHeight;

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let full = '';

    try {{
      while (true) {{
        const {{done, value}} = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, {{stream: true}});
        full += chunk;
        const raw = bubble.querySelector('.felix-raw');
        if (raw) raw.textContent = full;
        box.scrollTop = box.scrollHeight;
      }}
    }} catch(streamErr) {{
      // iOS Safari drops streaming connections — show whatever arrived
      if (full) {{
        const raw = bubble.querySelector('.felix-raw');
        if (raw) raw.textContent = full + ' \u2026';
        const note = document.createElement('div');
        note.style.cssText = 'margin-top:8px;font-size:0.75em;color:#9ca3af;font-style:italic;';
        note.textContent = '(Response cut off — tap Send again if you need more.)';
        bubble.appendChild(note);
      }} else {{
        throw streamErr; // nothing received — surface the real error
      }}
    }}

    // Post-process: render [FIX:] cards
    parseFixes(bubble, full);
    box.scrollTop = box.scrollHeight;

    // ── Auto-process [READ:] tags — Felix reads files himself ────────
    if (full) await autoHandleReads(full);

  }} catch(err) {{
    thinkEl.style.display = 'none';
    errEl.textContent = 'Error: ' + err.message;
    errEl.style.display = 'block';
  }} finally {{
    document.getElementById('felix-send').disabled = false;
    document.getElementById('felix-input').focus();
  }}
}}

// ── Auto-handle [READ:] tags — no button click needed ─────────────────
async function autoHandleReads(fullText) {{
  const readPattern = /\[READ:\s*([^:\]]+)(?::(\d+)-(\d+))?\]/g;
  const sections = [];
  let m;
  while ((m = readPattern.exec(fullText)) !== null) {{
    sections.push({{ fname: m[1].trim(), start: m[2] ? parseInt(m[2]) : 0, end: m[3] ? parseInt(m[3]) : 0 }});
  }}
  if (sections.length === 0) return;

  const box = document.getElementById('felix-msgs');

  // Show a small status bubble
  const statusEl = document.createElement('div');
  statusEl.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 12px;' +
    'background:#fdf4ff;border:1px solid #e9d5ff;border-radius:10px;' +
    'font-size:0.76em;color:#7e22ce;';
  const names = sections.map(s => s.fname).join(', ');
  statusEl.innerHTML = '<span style="animation:spin 1s linear infinite;display:inline-block;">&#9696;</span>' +
    ' Felix is reading ' + escHtml(names) + '\u2026';
  box.appendChild(statusEl);
  box.scrollTop = box.scrollHeight;

  // Fetch all requested sections
  const parts = [];
  for (const {{fname, start, end}} of sections) {{
    try {{
      const params = new URLSearchParams({{file: fname, start, end}});
      const resp = await fetch('/dev-read-file?' + params);
      if (resp.ok) parts.push(await resp.text());
    }} catch(e) {{ parts.push('Could not load ' + fname + ': ' + e.message); }}
  }}

  statusEl.remove();

  if (parts.length === 0) return;

  // Send the file content back to Felix silently (no user bubble)
  const contextPayload =
    '[SYSTEM: You requested the following file sections. Here they are \u2014 please continue your analysis.]\\n\\n' +
    parts.join('\\n\\n\u2500\u2500\u2500\\n\\n') +
    '\\n\\n[END OF FILE SECTIONS]';

  setThinking('Felix is reading the code\u2026');
  await streamFelix(contextPayload, true);
}}

function setThinking(msg) {{
  const el = document.getElementById('felix-thinking');
  el.innerHTML = '<span style="opacity:0.6">\u25cf\u25cf\u25cf</span> ' + escHtml(msg);
  el.style.display = 'block';
}}

// ── Bubble builders ────────────────────────────────────────────────────────
function buildUserBubble(text, image) {{
  const d = document.createElement('div');
  d.style.cssText = 'display:flex;justify-content:flex-end;';
  const imgHtml = image
    ? `<div style="text-align:right;margin-bottom:6px;">
         <img src="data:${{image.mediaType}};base64,${{image.base64}}"
              style="max-height:100px;max-width:220px;border-radius:8px;
                     border:2px solid #3b82f6;object-fit:cover;">
         <div style="font-size:0.7em;color:#93c5fd;margin-top:2px;">📷 Screenshot attached</div>
       </div>`
    : '';
  d.innerHTML = `<div style="max-width:80%;background:#1e3a8a;color:white;padding:10px 14px;
    border-radius:14px 14px 4px 14px;font-size:0.88em;line-height:1.5;">${{imgHtml}}<span style="white-space:pre-wrap;">${{escHtml(text)}}</span></div>`;
  return d;
}}

function buildFelixBubble(text) {{
  const d = document.createElement('div');
  d.style.cssText = 'display:flex;gap:10px;align-items:flex-start;';
  d.innerHTML = `
    <div style="width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#1e3a8a,#3b82f6);
                display:flex;align-items:center;justify-content:center;font-size:1em;flex-shrink:0;">&#128187;</div>
    <div style="flex:1;background:#f8faff;border:1px solid #dbeafe;padding:12px 14px;
                border-radius:4px 14px 14px 14px;">
      <div class="felix-raw" style="font-size:0.87em;line-height:1.6;white-space:pre-wrap;color:#1e293b;">${{escHtml(text)}}</div>
      <div class="felix-fixes"></div>
    </div>`;
  return d;
}}

function escHtml(str) {{
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
         .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}}

// ── Parse [FIX:...] and [READ:...] blocks ─────────────────────────────────
function parseFixes(bubble, fullText) {{
  const fixPattern  = /\[FIX:\s*([^\]]+)\]\s*[\\r\\n]+(?:WHAT:\s*([^\\r\\n]*)[\\r\\n]+)?FIND:[\\r\\n]+([\s\S]*?)[\\r\\n]+REPLACE:[\\r\\n]+([\s\S]*?)[\\r\\n]+\[\/FIX\]/g;
  const readPattern = /\[READ:\s*([^:\]]+)(?::(\d+)-(\d+))?\]/g;
  const rawEl   = bubble.querySelector('.felix-raw');
  const fixesEl = bubble.querySelector('.felix-fixes');
  if (!rawEl || !fixesEl) return;

  let cleanText = fullText;
  let match;

  // ── FIX blocks — show clean approval card, no code ────────────────────────
  while ((match = fixPattern.exec(fullText)) !== null) {{
    const filename = match[1].trim();
    const whatDesc = (match[2] || '').trim() || 'Update ' + filename;
    const findStr  = match[3];
    const replStr  = match[4];
    cleanText = cleanText.replace(match[0], '');
    const card = document.createElement('div');
    card.style.cssText = 'margin-top:10px;border:1.5px solid #86efac;border-radius:12px;overflow:hidden;';
    card.innerHTML = `
      <div style="background:#f0fdf4;padding:10px 14px;display:flex;align-items:center;gap:10px;">
        <span style="font-size:1.1em;">&#128295;</span>
        <span style="flex:1;font-size:0.88em;color:#166534;font-weight:600;">${{escHtml(whatDesc)}}</span>
        <span style="font-size:0.72em;color:#6b7280;">${{escHtml(filename)}}</span>
        <button onclick="applyFix(this,'${{escHtml(filename)}}', this.dataset.find, this.dataset.replace)"
                data-find="${{escHtml(findStr)}}"
                data-replace="${{escHtml(replStr)}}"
                style="padding:6px 16px;background:#15803d;color:white;border:none;border-radius:8px;
                       font-size:0.85em;font-weight:700;cursor:pointer;font-family:inherit;flex-shrink:0;">
          Apply
        </button>
      </div>`;
    fixesEl.appendChild(card);
  }}

  // ── READ blocks — silently strip them (autoHandleReads processes them) ──
  let readMatch;
  while ((readMatch = readPattern.exec(fullText)) !== null) {{
    const fname = readMatch[1].trim();
    const start = readMatch[2];
    const end   = readMatch[3];
    const rangeLabel = (start && end) ? ` lines ${{start}}\u2013${{end}}` : '';
    cleanText = cleanText.replace(readMatch[0], `[📄 Reading ${{fname}}${{rangeLabel}}\u2026]`);
  }}

  rawEl.textContent = cleanText;
}}

// ── Guide panel ───────────────────────────────────────────────────────────
function toggleGuide() {{
  const p = document.getElementById('guide-panel');
  const b = document.getElementById('guide-btn');
  if (p.style.display === 'none') {{
    p.style.display = 'block';
    b.textContent = '\u2715 Close guide';
  }} else {{
    p.style.display = 'none';
    b.innerHTML = '&#10067; How it works';
  }}
}}

// ── Live errors panel ─────────────────────────────────────────────────────
let _autoRefreshTimer = null;

function toggleErrors() {{
  const panel = document.getElementById('errors-panel');
  const btn   = document.getElementById('errors-toggle-btn');
  if (panel.style.display === 'none') {{
    panel.style.display = 'block';
    btn.style.background = 'rgba(220,38,38,0.35)';
    refreshLogs();
  }} else {{
    panel.style.display = 'none';
    btn.style.background = 'rgba(220,38,38,0.15)';
    stopAutoRefresh();
    document.getElementById('log-auto-refresh').checked = false;
  }}
}}

async function refreshLogs() {{
  const btn = document.getElementById('log-refresh-btn');
  if (btn) {{ btn.disabled = true; btn.textContent = 'Loading\u2026'; }}
  try {{
    const resp = await fetch('/dev-logs');
    const text = await resp.text();
    const pre  = document.getElementById('log-content');
    if (pre) {{
      // Colorize common patterns
      const colored = text
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/(Traceback \(most recent call last\):)/g,
          '<span style="color:#f87171;font-weight:700;">$1</span>')
        .replace(/(Error|Exception|Traceback):/g,
          '<span style="color:#f87171;font-weight:700;">$1:</span>')
        .replace(/(\d{{3}}\s+[A-Z]+)/g,
          '<span style="color:#fbbf24;">$1</span>')
        .replace(/(WARNING)/g,
          '<span style="color:#fbbf24;font-weight:600;">$1</span>');
      pre.innerHTML = colored;
      pre.scrollTop = pre.scrollHeight;
      const lines = text.split('\\n').length;
      const ctr = document.getElementById('log-line-count');
      if (ctr) ctr.textContent = '(' + lines + ' lines)';
    }}
  }} catch(e) {{
    const pre = document.getElementById('log-content');
    if (pre) pre.textContent = 'Could not load log: ' + e.message;
  }} finally {{
    if (btn) {{ btn.disabled = false; btn.textContent = '\u21bb Refresh now'; }}
  }}
}}

function toggleAutoRefresh() {{
  const cb = document.getElementById('log-auto-refresh');
  if (cb && cb.checked) {{
    _autoRefreshTimer = setInterval(refreshLogs, 5000);
  }} else {{
    stopAutoRefresh();
  }}
}}

function stopAutoRefresh() {{
  if (_autoRefreshTimer) {{ clearInterval(_autoRefreshTimer); _autoRefreshTimer = null; }}
}}

function sendLogToFelix() {{
  const pre = document.getElementById('log-content');
  if (!pre) return;
  const logText = pre.innerText || pre.textContent || '';
  const inp = document.getElementById('felix-input');
  inp.value = '[!!] Server error log (last 300 lines):\\n\\n' + logText +
    '\\n\\nPlease analyze this log. Identify any errors, exceptions, or warnings and explain what caused them.';
  inp.focus();
  document.getElementById('felix-msgs').scrollTop = 99999;
}}

// ── File loader panel ─────────────────────────────────────────────────────
function toggleFileLoader() {{
  const panel = document.getElementById('file-loader-panel');
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}}

async function loadFileSection() {{
  const fname = document.getElementById('fl-file').value;
  if (!fname) {{ alert('Pick a file first.'); return; }}
  const start = document.getElementById('fl-start').value || '';
  const end   = document.getElementById('fl-end').value   || '';
  await loadFileSectionDirect(fname, start ? parseInt(start) : 0, end ? parseInt(end) : 0);
  document.getElementById('file-loader-panel').style.display = 'none';
}}

async function loadFileSectionDirect(fname, start, end) {{
  const btn = event && event.target;
  if (btn) {{ btn.disabled = true; btn.textContent = 'Loading\u2026'; }}
  try {{
    const params = new URLSearchParams({{file: fname}});
    if (start > 0) params.append('start', start);
    if (end   > 0) params.append('end',   end);
    const resp = await fetch('/dev-read-file?' + params.toString());
    const text = await resp.text();
    if (!resp.ok) {{ alert('Error: ' + text); return; }}
    // Inject as a context message, then send to Felix
    injectContext('📄 File section loaded — ' + fname +
      (start > 0 ? ' lines ' + start + '-' + end : ' (full file)') +
      ':\\n\\n' + text);
  }} catch(e) {{
    alert('Network error: ' + e.message);
  }} finally {{
    if (btn) {{ btn.disabled = false; btn.textContent = 'Load & send to Felix'; }}
  }}
}}

// ── Inject context message and ask Felix to analyze ─────────────────────
function injectContext(contextText) {{
  const box = document.getElementById('felix-msgs');
  // Show a teal "context loaded" indicator
  const info = document.createElement('div');
  info.style.cssText = 'background:#e0f2fe;border:1px solid #7dd3fc;border-radius:10px;padding:8px 12px;' +
    'font-size:0.75em;color:#0369a1;display:flex;justify-content:space-between;align-items:center;';
  const preview = contextText.substring(0, 80).replace(/\\n/g,' ') + '\u2026';
  info.innerHTML = `<span>&#128196; Context loaded: ${{escHtml(preview)}}</span>
    <button onclick="this.closest('div').remove()" style="background:none;border:none;cursor:pointer;
            color:#0369a1;font-size:1em;">&#10005;</button>`;
  box.appendChild(info);

  // Pre-fill input with the context + a prompt
  const inp = document.getElementById('felix-input');
  inp.value = contextText + '\\n\\nPlease analyze this and let me know what you see.';
  inp.focus();
  box.scrollTop = box.scrollHeight;
}}

// ── Apply a fix ───────────────────────────────────────────────────────────
async function applyFix(btn, filename, findStr, replaceStr) {{
  btn.disabled = true;
  btn.textContent = 'Applying\u2026';
  try {{
    const body = new URLSearchParams({{
      file:    filename,
      find:    findStr,
      replace: replaceStr,
    }});
    const resp = await fetch('/dev-apply', {{method:'POST', body}});
    const txt  = await resp.text();
    if (!resp.ok) {{
      btn.textContent = '\u274c Failed';
      btn.style.background = '#dc2626';
      btn.disabled = false;
      // Show error in a small note below the card
      const errNote = document.createElement('div');
      errNote.style.cssText = 'padding:6px 14px;font-size:0.75em;color:#dc2626;background:#fef2f2;';
      errNote.textContent = txt;
      btn.closest('div').parentElement.appendChild(errNote);
      return;
    }}
    // Success — replace the row with Applied + Undo
    const row = btn.closest('div');
    row.innerHTML = `
      <span style="font-size:1.1em;">&#10003;</span>
      <span style="flex:1;font-size:0.88em;color:#166534;font-weight:600;">Applied — restarting\u2026</span>
      <button onclick="undoFix('${{escHtml(filename)}}')"
              style="padding:6px 14px;background:#64748b;color:white;border:none;border-radius:8px;
                     font-size:0.82em;font-weight:600;cursor:pointer;font-family:inherit;">
        Undo
      </button>`;
    row.style.cssText += ';background:#dcfce7;';
    restartServer();
  }} catch(e) {{
    btn.textContent = 'Error';
    btn.style.background = '#dc2626';
    btn.disabled = false;
  }}
}}

// ── Undo the last applied fix ─────────────────────────────────────────────
async function undoFix(filename) {{
  try {{
    const resp = await fetch('/dev-undo', {{
      method: 'POST',
      headers: {{'Content-Type':'application/x-www-form-urlencoded'}},
      body: 'file=' + encodeURIComponent(filename),
    }});
    const txt = await resp.text();
    if (!resp.ok) {{
      alert('Undo failed: ' + txt);
      return;
    }}
    // Refresh so the restored file takes effect
    restartServer();
  }} catch(e) {{
    alert('Undo error: ' + e.message);
  }}
}}

// ── Restart server ────────────────────────────────────────────────────────
async function restartServer() {{
  const btn   = document.getElementById('restart-btn');
  const toast = document.getElementById('restart-toast');
  btn.disabled = true; btn.textContent = 'Restarting\u2026';
  toast.style.display = 'block';
  try {{
    await fetch('/dev-restart', {{method:'POST'}});
  }} catch(e) {{}}
  setTimeout(() => {{ window.location.reload(); }}, 5000);
}}
</script>
"""
    return html_page("Felix — Dev", body)


# ── Bubble HTML helpers (used for server-rendered history) ────────────────────
import re as _re

def _clean_user_history(text: str) -> str:
    """Strip auto-injected server log / system context from saved user messages."""
    # Remove [SERVER LOG — ...] block. Ends with \n] (bracket on its own line).
    # Can't use [^\[] because log lines contain [ characters (e.g. [05/Apr/2026]).
    text = _re.sub(r'\n\n\[SERVER LOG.*?\n\]', '', text, flags=_re.DOTALL)
    # Remove any [SYSTEM: ...][END OF FILE SECTIONS] auto-read injections
    text = _re.sub(r'\n\n\[SYSTEM:.*?\[END OF FILE SECTIONS\]', '', text, flags=_re.DOTALL)
    return text.strip()

def _user_bubble(text: str, ts: str) -> str:
    ts_label = f'<div style="font-size:0.7em;color:#94a3b8;margin-top:4px;text-align:right;">{escape(ts[:16])}</div>' if ts else ""
    clean = _clean_user_history(text)
    return f"""<div style="display:flex;justify-content:flex-end;">
  <div style="max-width:80%;background:#1e3a8a;color:white;padding:10px 14px;
              border-radius:14px 14px 4px 14px;font-size:0.88em;line-height:1.5;white-space:pre-wrap;">
    {escape(clean)}{ts_label}
  </div>
</div>"""


def _felix_bubble(text: str, ts: str) -> str:
    ts_label = f'<div style="font-size:0.7em;color:#94a3b8;margin-top:6px;">{escape(ts[:16])}</div>' if ts else ""
    # Strip [READ:...] and [FIX:...][/FIX] blocks from history (already processed)
    clean = _re.sub(r'\[READ:[^\]]*\]', '', text)
    clean = _re.sub(r'\[FIX:[^\]]*\].*?\[/FIX\]', '', clean, flags=_re.DOTALL)
    clean = clean.strip()
    safe = escape(clean)
    return f"""<div style="display:flex;gap:10px;align-items:flex-start;">
  <div style="width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#1e3a8a,#3b82f6);
              display:flex;align-items:center;justify-content:center;font-size:1em;flex-shrink:0;">&#128187;</div>
  <div style="flex:1;background:#f8faff;border:1px solid #dbeafe;padding:12px 14px;
              border-radius:4px 14px 14px 14px;">
    <div style="font-size:0.87em;line-height:1.6;white-space:pre-wrap;color:#1e293b;">{safe}</div>
    {ts_label}
  </div>
</div>"""


def _welcome_bubble() -> str:
    return """<div style="display:flex;gap:10px;align-items:flex-start;">
  <div style="width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#1e3a8a,#3b82f6);
              display:flex;align-items:center;justify-content:center;font-size:1em;flex-shrink:0;">&#128187;</div>
  <div style="flex:1;background:#f8faff;border:1px solid #dbeafe;padding:12px 14px;
              border-radius:4px 14px 14px 14px;font-size:0.87em;line-height:1.6;color:#1e293b;">
    Hi Lauren &mdash; I&rsquo;m Felix, your Help Desk. &#128075;<br><br>
    Just tell me what&rsquo;s wrong in plain English. I&rsquo;ll handle everything else myself:
    I&rsquo;ll check the live error log, read whatever files I need, and show you exactly
    what to change &mdash; or apply the fix myself if you say go ahead.<br><br>
    <em>You don&rsquo;t need to paste errors, copy code, or know which file the bug is in.
    Just describe what you&rsquo;re seeing.</em>
  </div>
</div>"""
