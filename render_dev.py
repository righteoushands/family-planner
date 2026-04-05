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

_MAX_FILE_CHARS = 50_000   # chars per injected file (~12k tokens — covers most files in full)
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
4. You can request specific sections of large files using this tag:

[READ: filename.py:start_line-end_line]

Example: [READ: app.py:1000-1200] — a "Load lines 1000–1200" button will appear
and Lauren can click it to inject that section into the conversation.
You can use multiple [READ:] tags per response to request different sections.
If you need a specific function, estimate its line range from context.

5. You can see live server error logs. Lauren has a "Show Errors" button that
   fetches the last 300 lines of the server log and injects them as context.
   If Lauren clicks it, you will receive the log text in the next message.

6. app.py is the largest file (5000+ lines). Use [READ: app.py:start-end] to
   request specific sections rather than asking for the whole file at once.

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
  <div style="background:linear-gradient(135deg,#1e3a8a 0%,#1e40af 60%,#2563eb 100%);
              border-radius:16px;padding:20px 20px 16px;margin-bottom:16px;">
    <div style="display:flex;align-items:center;gap:14px;">
      <div style="width:56px;height:56px;border-radius:50%;background:rgba(255,255,255,0.15);
                  border:2px solid rgba(255,255,255,0.3);
                  display:flex;align-items:center;justify-content:center;font-size:1.8em;flex-shrink:0;">
        &#128187;
      </div>
      <div style="flex:1;">
        <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.7em;font-weight:700;
                    color:white;line-height:1.1;">The Help Desk</div>
        <div style="font-size:0.78em;color:rgba(255,255,255,0.75);margin-top:2px;">
          Felix &middot; your app&rsquo;s built-in programmer &middot; reads code &middot; applies real fixes
        </div>
      </div>
      <button onclick="toggleGuide()" id="guide-btn"
              title="Show / hide the full guide explaining every button and how Felix works"
              style="padding:6px 13px;font-size:0.78em;border-radius:8px;
                     border:1.5px solid rgba(255,255,255,0.4);
                     background:rgba(255,255,255,0.12);color:white;
                     font-family:inherit;cursor:pointer;font-weight:600;white-space:nowrap;">
        &#10067; How it works
      </button>
    </div>

    <!-- Action buttons row -->
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;">
      <button onclick="toggleErrors()" id="errors-toggle-btn"
              title="Show / hide the live server error log panel. Errors, tracebacks, and print statements from the running app appear here in real time."
              style="padding:6px 13px;font-size:0.78em;border-radius:8px;
                     border:1.5px solid rgba(252,165,165,0.6);
                     background:rgba(220,38,38,0.15);color:#fca5a5;
                     font-family:inherit;cursor:pointer;font-weight:600;">
        &#128680; Live Errors
      </button>
      <button onclick="toggleFileLoader()" id="file-loader-btn"
              title="Open the file loader: pick any source file (and optional line range) to inject directly into the chat so Felix can read it."
              style="padding:6px 13px;font-size:0.78em;border-radius:8px;
                     border:1.5px solid rgba(216,180,254,0.5);
                     background:rgba(124,58,237,0.15);color:#d8b4fe;
                     font-family:inherit;cursor:pointer;font-weight:600;">
        &#128196; Load File
      </button>
      <button onclick="restartServer()" id="restart-btn"
              title="Gracefully restart the server after applying a code fix. The page will tell you when to refresh."
              style="padding:6px 13px;font-size:0.78em;border-radius:8px;
                     border:1.5px solid rgba(251,191,36,0.5);
                     background:rgba(245,158,11,0.15);color:#fcd34d;
                     font-family:inherit;cursor:pointer;font-weight:600;">
        &#128260; Restart Server
      </button>
      <form method="POST" action="/dev-clear" style="display:inline;">
        <button type="submit"
                title="Clear Felix's entire conversation history and start fresh. Useful when a conversation gets too long or goes off track."
                style="padding:6px 13px;font-size:0.78em;border-radius:8px;
                       border:1.5px solid rgba(255,255,255,0.2);
                       background:rgba(255,255,255,0.08);color:rgba(255,255,255,0.6);
                       font-family:inherit;cursor:pointer;">
          &#128465; Clear Chat
        </button>
      </form>
    </div>
  </div>

  <!-- Collapsible Guide -->
  <div id="guide-panel" style="display:none;background:#f8faff;border:1.5px solid #dbeafe;
       border-radius:14px;padding:18px 20px;margin-bottom:14px;">
    <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.1em;font-weight:700;
                color:#1e3a8a;margin-bottom:14px;">&#128218; Help Desk Guide</div>

    <div style="display:grid;gap:12px;">

      <div style="background:white;border-radius:10px;padding:13px 15px;border-left:4px solid #dc2626;">
        <div style="font-weight:700;font-size:0.82em;color:#dc2626;margin-bottom:4px;">&#128680; Live Errors</div>
        <div style="font-size:0.78em;color:#475569;line-height:1.6;">
          Opens a panel showing the last 300 lines of the server&rsquo;s live output — including Python
          tracebacks, error messages, and print statements from any part of the app. Use
          <strong>Auto-refresh</strong> to keep it updating every 5 seconds, or <strong>Refresh now</strong>
          to pull the latest manually. When you see an error, click <strong>Send log to Felix</strong>
          and he will diagnose it immediately.
        </div>
      </div>

      <div style="background:white;border-radius:10px;padding:13px 15px;border-left:4px solid #7c3aed;">
        <div style="font-weight:700;font-size:0.82em;color:#7c3aed;margin-bottom:4px;">&#128196; Load File</div>
        <div style="font-size:0.78em;color:#475569;line-height:1.6;">
          Opens a panel where you pick any source file from a dropdown and optionally enter a line range
          (e.g. 500 to 700). Clicking <strong>Inject into chat</strong> sends that section straight to
          Felix so he can read it. Leave the line numbers blank to load the entire file. You can also
          let Felix request sections himself — he will write <code>[READ: filename.py:100-300]</code>
          in his response and a purple <strong>Load &amp; send to Felix</strong> button will appear.
        </div>
      </div>

      <div style="background:white;border-radius:10px;padding:13px 15px;border-left:4px solid #d97706;">
        <div style="font-weight:700;font-size:0.82em;color:#d97706;margin-bottom:4px;">&#128260; Restart Server</div>
        <div style="font-size:0.78em;color:#475569;line-height:1.6;">
          After Felix proposes a fix and you click <strong>Apply Fix</strong>, the code is written to
          the file but the server keeps running the old version. Click <strong>Restart Server</strong>
          to reload everything. A toast will count down — refresh the page after 5 seconds to confirm
          the fix is live.
        </div>
      </div>

      <div style="background:white;border-radius:10px;padding:13px 15px;border-left:4px solid #64748b;">
        <div style="font-weight:700;font-size:0.82em;color:#64748b;margin-bottom:4px;">&#128465; Clear Chat</div>
        <div style="font-size:0.78em;color:#475569;line-height:1.6;">
          Wipes Felix&rsquo;s entire conversation history and starts fresh. Useful when a conversation
          goes long or drifts off topic. Felix&rsquo;s memory of the codebase is rebuilt automatically
          from the source files on each new message.
        </div>
      </div>

      <div style="background:white;border-radius:10px;padding:13px 15px;border-left:4px solid #15803d;">
        <div style="font-weight:700;font-size:0.82em;color:#15803d;margin-bottom:4px;">&#128295; Apply Fix (green card)</div>
        <div style="font-size:0.78em;color:#475569;line-height:1.6;">
          When Felix proposes a code change, it appears as a dark card showing exactly what will be
          removed (red) and added (green). Click <strong>Apply Fix ✓</strong> to write the change
          directly to the file. Then restart the server to see it live. You can always roll back using
          a checkpoint if something goes wrong.
        </div>
      </div>

      <div style="background:white;border-radius:10px;padding:13px 15px;border-left:4px solid #7c3aed;">
        <div style="font-weight:700;font-size:0.82em;color:#7c3aed;margin-bottom:4px;">&#128196; Load Section (purple card)</div>
        <div style="font-size:0.78em;color:#475569;line-height:1.6;">
          Felix sometimes needs to see a specific part of a large file. He will write
          <code>[READ: app.py:1000-1200]</code> and a purple card appears. Click
          <strong>Load &amp; send to Felix</strong> to fetch those exact lines and send them back
          into the conversation automatically.
        </div>
      </div>

      <div style="background:#fffbeb;border-radius:10px;padding:13px 15px;border-left:4px solid #f59e0b;">
        <div style="font-weight:700;font-size:0.82em;color:#92400e;margin-bottom:4px;">&#128161; Tips for best results</div>
        <div style="font-size:0.78em;color:#475569;line-height:1.6;">
          &bull; Describe bugs in plain English — Felix will figure out which file to read.<br>
          &bull; If you get a Python traceback, click <strong>Live Errors</strong>, then <strong>Send log to Felix</strong>.<br>
          &bull; For huge files like <code>app.py</code>, let Felix ask for the section he needs via [READ:] rather than loading the whole thing.<br>
          &bull; One [FIX] block = one logical change. Felix will split big changes into multiple cards.<br>
          &bull; If a fix breaks something, roll back using the checkpoint history (the app saves checkpoints automatically).
        </div>
      </div>

    </div>
  </div>

  <!-- Live Errors Panel (hidden by default) -->
  <div id="errors-panel" style="display:none;background:#0f172a;border:1.5px solid #334155;
       border-radius:14px;padding:0;margin-bottom:14px;overflow:hidden;">
    <div style="display:flex;align-items:center;justify-content:space-between;
                padding:10px 14px;background:#1e293b;border-bottom:1px solid #334155;">
      <div style="font-size:0.78em;font-weight:700;color:#f1f5f9;">
        &#128680; Live Server Log <span id="log-line-count" style="font-weight:400;color:#64748b;"></span>
      </div>
      <div style="display:flex;gap:8px;align-items:center;">
        <label style="font-size:0.72em;color:#94a3b8;display:flex;align-items:center;gap:5px;cursor:pointer;">
          <input type="checkbox" id="log-auto-refresh" onchange="toggleAutoRefresh()"
                 style="accent-color:#3b82f6;">
          Auto-refresh (5s)
        </label>
        <button onclick="refreshLogs()" id="log-refresh-btn"
                title="Pull the latest server output right now"
                style="padding:4px 10px;font-size:0.72em;border-radius:6px;border:1px solid #475569;
                       background:#334155;color:#94a3b8;font-family:inherit;cursor:pointer;">
          &#8635; Refresh now
        </button>
        <button onclick="sendLogToFelix()"
                title="Copy the visible log text into the chat input and ask Felix to diagnose it"
                style="padding:4px 10px;font-size:0.72em;border-radius:6px;border:1px solid #3b82f6;
                       background:#1d4ed8;color:white;font-family:inherit;cursor:pointer;font-weight:600;">
          &#128172; Send to Felix
        </button>
      </div>
    </div>
    <pre id="log-content" style="margin:0;padding:12px 14px;font-size:0.72em;color:#94a3b8;
         max-height:280px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;
         line-height:1.5;">Loading&hellip;</pre>
  </div>

  <!-- File loader panel (hidden by default) -->
  <div id="file-loader-panel" style="display:none;background:#fdf4ff;border:1.5px solid #e9d5ff;
       border-radius:12px;padding:14px;margin-bottom:14px;">
    <div style="font-size:0.78em;font-weight:700;color:#7e22ce;margin-bottom:10px;">
      &#128196; Load a file (or section) into the conversation
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
      <select id="fl-file" style="flex:1;min-width:160px;padding:7px 10px;border:1.5px solid #e9d5ff;
              border-radius:8px;font-family:inherit;font-size:0.82em;background:white;">
        <option value="">-- choose file --</option>
        {chr(10).join(f'<option value="{fn}">{fn}</option>' for fn in sorted(f for f in os.listdir('.') if f.endswith('.py')))}
      </select>
      <input id="fl-start" type="number" placeholder="from line" min="1"
             style="width:90px;padding:7px 10px;border:1.5px solid #e9d5ff;border-radius:8px;
                    font-family:inherit;font-size:0.82em;">
      <input id="fl-end" type="number" placeholder="to line"
             style="width:90px;padding:7px 10px;border:1.5px solid #e9d5ff;border-radius:8px;
                    font-family:inherit;font-size:0.82em;">
      <button onclick="loadFileSection()" id="fl-load-btn"
              title="Fetch the selected file (and line range if specified) and send it to Felix as context"
              style="padding:7px 14px;background:#7c3aed;color:white;border:none;border-radius:8px;
                     font-family:inherit;font-size:0.82em;font-weight:700;cursor:pointer;">
        Inject into chat
      </button>
    </div>
    <div style="font-size:0.72em;color:#a855f7;margin-top:6px;">
      Leave line numbers blank to load the entire file &middot; Felix can also request sections automatically with [READ: filename.py:100-300]
    </div>
  </div>

  <!-- Quick prompts -->
  <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px;">
    <button onclick="quickMsg('Can you explain how the app is structured?')"
            title="Ask Felix for a plain-English overview of how the codebase is organized"
            class="q-chip">App overview</button>
    <button onclick="quickMsg('Are there any common bugs or edge cases I should know about?')"
            title="Ask Felix to scan the codebase for known pitfalls and fragile spots"
            class="q-chip">Common issues</button>
    <button onclick="quickMsg('Something is broken — I will paste the error below. What could cause this?')"
            title="Pre-fill a debugging prompt — then paste your error message and hit Send"
            class="q-chip">Debug an error</button>
    <button onclick="quickMsg('Can you read render_plan_importer.py and check it for bugs?')"
            title="Ask Felix to read and audit the Plan Importer source file"
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

// ── Parse [FIX:...] and [READ:...] blocks ─────────────────────────────────
function parseFixes(bubble, fullText) {{
  const fixPattern  = /\[FIX:\s*([^\]]+)\]\s*\nFIND:\n([\s\S]*?)\nREPLACE:\n([\s\S]*?)\n\[\/FIX\]/g;
  const readPattern = /\[READ:\s*([^:\]]+):(\d+)-(\d+)\]/g;
  const rawEl   = bubble.querySelector('.felix-raw');
  const fixesEl = bubble.querySelector('.felix-fixes');
  if (!rawEl || !fixesEl) return;

  let cleanText = fullText;
  let match;

  // ── FIX blocks ────────────────────────────────────────────────────────────
  while ((match = fixPattern.exec(fullText)) !== null) {{
    const filename = match[1].trim();
    const findStr  = match[2];
    const replStr  = match[3];
    cleanText = cleanText.replace(match[0], `\u2705 Fix proposed for ${{filename}} (see button below)`);
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
          Apply Fix \u2713
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

  // ── READ blocks ───────────────────────────────────────────────────────────
  let readMatch;
  while ((readMatch = readPattern.exec(fullText)) !== null) {{
    const fname = readMatch[1].trim();
    const start = parseInt(readMatch[2]);
    const end   = parseInt(readMatch[3]);
    cleanText = cleanText.replace(readMatch[0],
      `[Felix wants to read ${{fname}} lines ${{start}}-${{end}} \u2014 see button below]`);
    const readCard = document.createElement('div');
    readCard.style.cssText = 'margin-top:10px;border:1.5px solid #e9d5ff;border-radius:10px;overflow:hidden;';
    readCard.innerHTML = `
      <div style="background:#fdf4ff;padding:8px 12px;font-size:0.75em;font-weight:700;
                  color:#7e22ce;display:flex;align-items:center;justify-content:space-between;">
        <span>&#128196; Felix needs: <code>${{escHtml(fname)}}</code> lines ${{start}}\u2013${{end}}</span>
        <button onclick="loadFileSectionDirect('${{escHtml(fname)}}',${{start}},${{end}})"
                style="padding:4px 12px;background:#7c3aed;color:white;border:none;border-radius:6px;
                       font-size:0.85em;font-weight:700;cursor:pointer;font-family:inherit;">
          Load &amp; send to Felix
        </button>
      </div>`;
    fixesEl.appendChild(readCard);
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
      const lines = text.split('\n').length;
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
  inp.value = '\ud83d\udea8 Server error log (last 300 lines):\n\n' + logText +
    '\n\nPlease analyze this log. Identify any errors, exceptions, or warnings and explain what caused them.';
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
    injectContext('\u{1F4C4} File section loaded — ' + fname +
      (start > 0 ? ' lines ' + start + '-' + end : ' (full file)') +
      ':\n\n' + text);
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
  const preview = contextText.substring(0, 80).replace(/\n/g,' ') + '\u2026';
  info.innerHTML = `<span>&#128196; Context loaded: ${{escHtml(preview)}}</span>
    <button onclick="this.closest('div').remove()" style="background:none;border:none;cursor:pointer;
            color:#0369a1;font-size:1em;">&#10005;</button>`;
  box.appendChild(info);

  // Pre-fill input with the context + a prompt
  const inp = document.getElementById('felix-input');
  inp.value = contextText + '\n\nPlease analyze this and let me know what you see.';
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
    Welcome to the Help Desk, Lauren! I&rsquo;m Felix, your app&rsquo;s programmer. &#128075;<br><br>
    I know this codebase inside and out. Tell me what&rsquo;s not working &mdash; describe the problem,
    paste an error message, or just say <em>&ldquo;the plan importer is broken&rdquo;</em> and I&rsquo;ll
    read the code and figure it out.<br><br>
    A few things that might help you get started:<br>
    &bull; Click <strong>&#128680; Live Errors</strong> to see the server&rsquo;s live output &mdash;
      tracebacks and errors show up there in real time.<br>
    &bull; Click <strong>&#10067; How it works</strong> for a full guide to every button on this page.<br>
    &bull; Use the quick-prompt chips below to get started with common tasks.<br><br>
    When I find a fix, I&rsquo;ll show it to you and you can apply it with one tap.
    Nothing changes until you say so. &#128512;
  </div>
</div>"""
