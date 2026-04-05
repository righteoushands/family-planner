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

_MAX_FILE_CHARS = 12_000   # chars per injected file (roughly 3k tokens)
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
You are friendly, precise, and deeply familiar with this codebase.
Your job: diagnose bugs, explain how the code works, and propose concrete fixes.

════════════ APP OVERVIEW ════════════
{overview}

════════════ SOURCE FILES ════════════
{file_list}

════════════ YOUR CAPABILITIES ════════════
1. You can read any source file — Lauren will paste the relevant section, or ask you by name.
2. When you propose a code change, output it in this EXACT format (one block per fix):

[FIX: filename.py]
FIND:
<exact code to be replaced — include 3-5 lines for context>
REPLACE:
<new code>
[/FIX]

Rules for FIX blocks:
- The FIND section must be an exact substring of the current file.
- Use 3-5 lines of context (not just the changed line) so the match is unambiguous.
- One logical change per [FIX] block.
- Keep REPLACE code properly indented.
- After a fix is applied, the server needs to be restarted (there is a Restart button in the UI).

3. When the fix is displayed, Lauren sees an "Apply This Fix" button.
   Clicking it writes the change directly to the file.
4. You can also see error logs if Lauren pastes them.

════════════ PERSONALITY ════════════
- Speak plainly. Lauren is not a developer — explain WHY as well as WHAT.
- Be direct: name the file and line, don't hedge.
- Celebrate when a fix works. Be encouraging.
- If you are unsure, say so and ask Lauren to paste the relevant code.
- Sign off with something cheerful but brief.
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

<div style="max-width:700px;margin:0 auto;padding:16px 16px 120px;">

  <!-- Header -->
  <div style="display:flex;align-items:center;gap:14px;margin-bottom:20px;padding-top:8px;">
    <div style="width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,#1e3a8a,#3b82f6);
                display:flex;align-items:center;justify-content:center;font-size:1.6em;flex-shrink:0;">
      &#128187;
    </div>
    <div>
      <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.5em;font-weight:700;
                  color:#1e3a8a;line-height:1.1;">Felix</div>
      <div style="font-size:0.78em;color:#64748b;">Your app's built-in programmer · reads code · applies real fixes</div>
    </div>
    <div style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end;">
      <button onclick="restartServer()" id="restart-btn"
              style="padding:6px 12px;font-size:0.78em;border-radius:8px;border:1.5px solid #f59e0b;
                     background:#fffbeb;color:#92400e;font-family:inherit;cursor:pointer;font-weight:600;">
        &#128260; Restart
      </button>
      <form method="POST" action="/dev-clear" style="display:inline;">
        <button type="submit"
                style="padding:6px 12px;font-size:0.78em;border-radius:8px;border:1.5px solid #e2e8f0;
                       background:white;color:#64748b;font-family:inherit;cursor:pointer;">
          &#128465; Clear
        </button>
      </form>
    </div>
  </div>

  <!-- Capability chips -->
  <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:18px;">
    <span style="padding:4px 10px;background:#eff6ff;color:#1d4ed8;border-radius:20px;font-size:0.75em;font-weight:600;">Reads source files</span>
    <span style="padding:4px 10px;background:#f0fdf4;color:#15803d;border-radius:20px;font-size:0.75em;font-weight:600;">Applies code fixes</span>
    <span style="padding:4px 10px;background:#fef3c7;color:#92400e;border-radius:20px;font-size:0.75em;font-weight:600;">Restarts server</span>
    <span style="padding:4px 10px;background:#fdf4ff;color:#7e22ce;border-radius:20px;font-size:0.75em;font-weight:600;">Explains bugs</span>
  </div>

  <!-- Quick prompts -->
  <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px;">
    <button onclick="quickMsg('Can you explain how the app is structured?')"
            class="q-chip">App overview</button>
    <button onclick="quickMsg('Are there any common bugs or edge cases I should know about?')"
            class="q-chip">Common issues</button>
    <button onclick="quickMsg('Something is broken — I will paste the error below. What could cause this?')"
            class="q-chip">Debug an error</button>
    <button onclick="quickMsg('Can you read render_plan_importer.py and check it for bugs?')"
            class="q-chip">Audit Plan Importer</button>
  </div>
  <style>
    .q-chip {{
      padding:5px 12px;font-size:0.78em;border-radius:20px;
      border:1.5px solid #dbeafe;background:#eff6ff;color:#1d4ed8;
      font-family:inherit;cursor:pointer;font-weight:600;
    }}
    .q-chip:hover {{ background:#dbeafe; }}
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
            border-top:1px solid #e2e8f0;padding:10px 14px;z-index:1000;">
  <div style="max-width:700px;margin:0 auto;display:flex;gap:8px;align-items:flex-end;">
    <textarea id="felix-input" rows="2" placeholder="Ask Felix… describe the bug, paste an error, or name a feature"
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

<script>
// ── Quick prompts ──────────────────────────────────────────────────────────
function quickMsg(text) {{
  document.getElementById('felix-input').value = text;
  sendToFelix();
}}

// ── Send message ──────────────────────────────────────────────────────────
async function sendToFelix() {{
  const inp  = document.getElementById('felix-input');
  const text = inp.value.trim();
  if (!text) return;
  inp.value = '';

  const box    = document.getElementById('felix-msgs');
  const errEl  = document.getElementById('felix-error');
  const thinkEl= document.getElementById('felix-thinking');
  errEl.style.display = 'none';

  // Append user bubble immediately
  box.appendChild(buildUserBubble(text));
  box.scrollTop = box.scrollHeight;

  // Thinking
  thinkEl.style.display = 'block';
  document.getElementById('felix-send').disabled = true;

  try {{
    const resp = await fetch('/dev-chat', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
      body: 'message=' + encodeURIComponent(text),
    }});
    if (!resp.ok) throw new Error(await resp.text());

    thinkEl.style.display = 'none';
    const bubble = buildFelixBubble('');
    box.appendChild(bubble);
    box.scrollTop = box.scrollHeight;

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let full = '';

    while (true) {{
      const {{done, value}} = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, {{stream: true}});
      full += chunk;
      const raw = bubble.querySelector('.felix-raw');
      if (raw) raw.textContent = full;
      box.scrollTop = box.scrollHeight;
    }}

    // Post-process: parse [FIX:...] blocks into Apply buttons
    parseFixes(bubble, full);
    box.scrollTop = box.scrollHeight;

  }} catch(err) {{
    thinkEl.style.display = 'none';
    errEl.textContent = 'Error: ' + err.message;
    errEl.style.display = 'block';
  }} finally {{
    document.getElementById('felix-send').disabled = false;
    inp.focus();
  }}
}}

// ── Bubble builders ────────────────────────────────────────────────────────
function buildUserBubble(text) {{
  const d = document.createElement('div');
  d.style.cssText = 'display:flex;justify-content:flex-end;';
  d.innerHTML = `<div style="max-width:80%;background:#1e3a8a;color:white;padding:10px 14px;
    border-radius:14px 14px 4px 14px;font-size:0.88em;line-height:1.5;white-space:pre-wrap;">${{escHtml(text)}}</div>`;
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

// ── Parse [FIX:...] blocks ─────────────────────────────────────────────────
function parseFixes(bubble, fullText) {{
  // Format: [FIX: filename.py]\nFIND:\nold code\nREPLACE:\nnew code\n[/FIX]
  const pattern = /\[FIX:\s*([^\]]+)\]\s*\nFIND:\n([\s\S]*?)\nREPLACE:\n([\s\S]*?)\n\[\/FIX\]/g;
  const rawEl   = bubble.querySelector('.felix-raw');
  const fixesEl = bubble.querySelector('.felix-fixes');
  if (!rawEl || !fixesEl) return;

  let cleanText = fullText;
  let match;

  while ((match = pattern.exec(fullText)) !== null) {{
    const filename = match[1].trim();
    const findStr  = match[2];
    const replStr  = match[3];

    // Remove the raw FIX block from display text
    cleanText = cleanText.replace(match[0], `✅ Fix proposed for ${{filename}} (see button below)`);

    // Build apply card
    const card = document.createElement('div');
    card.style.cssText = 'margin-top:12px;border:1.5px solid #86efac;border-radius:10px;overflow:hidden;';
    card.innerHTML = `
      <div style="background:#f0fdf4;padding:8px 12px;font-size:0.75em;font-weight:700;
                  color:#166534;display:flex;align-items:center;justify-content:space-between;">
        <span>&#128295; Fix for <code>${{escHtml(filename)}}</code></span>
        <button onclick="applyFix(this,'${{escHtml(filename)}}', this.dataset.find, this.dataset.replace)"
                data-find="${{escHtml(findStr)}}"
                data-replace="${{escHtml(replStr)}}"
                style="padding:4px 12px;background:#15803d;color:white;border:none;border-radius:6px;
                       font-size:0.85em;font-weight:700;cursor:pointer;font-family:inherit;">
          Apply Fix &#10003;
        </button>
      </div>
      <div style="background:#1e293b;padding:10px 12px;">
        <div style="font-size:0.7em;color:#94a3b8;margin-bottom:4px;">REMOVE:</div>
        <pre style="margin:0;font-size:0.78em;color:#fca5a5;white-space:pre-wrap;word-break:break-all;">${{escHtml(findStr)}}</pre>
        <div style="font-size:0.7em;color:#94a3b8;margin:8px 0 4px;">ADD:</div>
        <pre style="margin:0;font-size:0.78em;color:#86efac;white-space:pre-wrap;word-break:break-all;">${{escHtml(replStr)}}</pre>
      </div>`;
    fixesEl.appendChild(card);
  }}

  rawEl.textContent = cleanText;
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
      btn.textContent = '&#10060; Failed';
      btn.style.background = '#dc2626';
      alert('Apply failed: ' + txt);
      return;
    }}
    btn.textContent = '&#10003; Applied!';
    btn.style.background = '#166534';
    btn.parentElement.parentElement.style.borderColor = '#16a34a';
    // Offer restart
    if (confirm('Fix applied! Restart the server now to see the change?')) {{
      restartServer();
    }}
  }} catch(e) {{
    btn.textContent = 'Error';
    btn.style.background = '#dc2626';
    alert('Network error: ' + e.message);
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
def _user_bubble(text: str, ts: str) -> str:
    ts_label = f'<div style="font-size:0.7em;color:#94a3b8;margin-top:4px;text-align:right;">{escape(ts[:16])}</div>' if ts else ""
    return f"""<div style="display:flex;justify-content:flex-end;">
  <div style="max-width:80%;background:#1e3a8a;color:white;padding:10px 14px;
              border-radius:14px 14px 4px 14px;font-size:0.88em;line-height:1.5;white-space:pre-wrap;">
    {escape(text)}{ts_label}
  </div>
</div>"""


def _felix_bubble(text: str, ts: str) -> str:
    ts_label = f'<div style="font-size:0.7em;color:#94a3b8;margin-top:6px;">{escape(ts[:16])}</div>' if ts else ""
    # For server-rendered history, just show raw text (no FIX parsing — those are past fixes)
    safe = escape(text)
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
    Hi Lauren! I'm Felix, your app's programmer. &#128075;<br><br>
    I know this codebase inside and out. Tell me what's not working — describe the problem,
    paste an error message, or just say <em>"the plan importer is broken"</em> and I'll read
    the code and figure it out.<br><br>
    When I find a fix, I'll show it to you and you can apply it with one tap.
    Nothing changes until you say so. &#128512;
  </div>
</div>"""
