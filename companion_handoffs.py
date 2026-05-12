"""
companion_handoffs.py — Shared cross-companion handoff system.

Each AI companion can refer Lauren to another companion using response tags:
  [TAG]Brief message for that companion[/TAG]

The tag is stripped from the visible bubble and a "→ Open in X" button is rendered.
Clicking it opens the target companion pre-loaded with the brief via ?q=&from= params.
"""

COMPANIONS = {
    "LUCY": {
        "name": "Lucy",
        "route": "/lucy",
        "emoji": "✝",
        "input_id": "lucy-input",
        "chat_id": "lucy-history",
        "bg": "#5b21b6",
        "desc": "family life, spiritual direction, emotional support, liturgical life, daily rhythms, wellbeing",
    },
    "LORENZO": {
        "name": "Lorenzo",
        "route": "/lorenzo",
        "emoji": "🍳",
        "input_id": "lz-input",
        "chat_id": "lz-history",
        "bg": "#92400e",
        "desc": "personal chef, meal planning, grocery lists, recipe ideas, kitchen management",
    },
    "IZZY": {
        "name": "Izzy",
        "route": "/dev",
        "emoji": "🛠",
        "input_id": "felix-input",
        "chat_id": "felix-msgs",
        "bg": "#1e3a8a",
        "desc": "built-in programmer, builds/fixes/adds features to the dashboard app",
    },
    "GREGORY": {
        "name": "Father Gregory",
        "route": "/headmaster",
        "emoji": "📚",
        "input_id": "gr-input",
        "chat_id": "gr-chat",
        "bg": "#14532d",
        "desc": "homeschool headmaster, classical Catholic education, academics for each child, lesson planning",
    },
    "MONICA": {
        "name": "Dr. Monica",
        "route": "/dr-monica",
        "emoji": "❤",
        "input_id": "mo-input",
        "chat_id": "mo-chat",
        "bg": "#7f1d1d",
        "desc": "child development expert, pediatric health, James's milestones, parenting guidance",
    },
    "COACH": {
        "name": "Coach",
        "route": "/coach",
        "emoji": "💪",
        "input_id": "co-input",
        "chat_id": "co-chat",
        "bg": "#1c1917",
        "desc": "family fitness guide, age-appropriate movement, PE planning, exercise",
    },
    "SISTERMARY": {
        "name": "Sister Mary",
        "route": "/sister-mary",
        "emoji": "✠",
        "input_id": "sm-input",
        "chat_id": "sm-chat",
        "bg": "#4a6fa5",
        "desc": "contemplative Marian companion, prayer intentions, sacraments, spiritual direction in difficulty",
    },
}


def handoff_prefill(self_tag: str, q: str, from_: str) -> tuple:
    """
    Given raw ?q= and ?from= URL params, return (q_safe, banner_html).
    q_safe is HTML-escaped text for pre-filling the textarea.
    banner_html is a ready-to-insert HTML div (empty string if no handoff).
    """
    import html as _html
    self_name  = COMPANIONS[self_tag]["name"]
    q_safe     = _html.escape(q.strip()) if q else ""
    from_label = _html.escape(from_.strip()) if from_ else ""
    banner_html = ""
    if q_safe:
        sender = from_label if from_label else "A companion"
        banner_html = (
            f'<div style="background:#dbeafe;color:#1e3a8a;font-size:0.82em;'
            f'padding:8px 14px;border-radius:8px;margin:0 0 10px;border:1px solid #93c5fd;">'
            f'&#128203; <strong>{sender} has a note for {self_name}.</strong> '
            f'Review it below and hit Send, or edit first.</div>'
        )
    return q_safe, banner_html


def companion_system_block(self_tag: str) -> list:
    """Return system prompt lines about the other companions for the given companion."""
    others = {tag: c for tag, c in COMPANIONS.items() if tag != self_tag}
    self_name = COMPANIONS[self_tag]["name"]
    lines = [
        "== YOUR COMPANION COLLEAGUES ==",
        "You are part of a team of AI companions for the McAdams family. When a question",
        "clearly belongs to another companion, acknowledge Lauren's question warmly first,",
        "then include a handoff tag so a 'Open in X' button appears automatically.",
        "",
        "The other companions and their handoff tags:",
    ]
    for tag, c in others.items():
        lines.append(f"  [{tag}]: {c['name']} — {c['desc']}")
        lines.append(
            f"    Usage: [{tag}]Write 1-3 sentences briefing {c['name']} — "
            f"what Lauren needs and any key context.[/{tag}]"
        )
    lines += [
        "",
        "HANDOFF RULES:",
        "- Use a handoff tag when Lauren's question clearly belongs to another companion.",
        "- ALWAYS answer what you can first, then add the handoff. Never refuse outright.",
        "- The tag content is stripped from your visible response — it becomes a button.",
        "- You can include multiple handoff tags in one response if needed.",
        f"- Never say 'I can't help with that' — either help, or warmly hand off.",
        "",
        "CONVERSATION STYLE — CRITICAL:",
        "- Ask AT MOST ONE question per response. Never list multiple questions.",
        "- If you need several pieces of information, pick the single most important",
        "  question and ask only that. Ask the next question in your following reply",
        "  once Lauren has answered the first.",
        "- If you find yourself writing a second question mark in a response, delete",
        "  everything after the first question and send only that.",
    ]
    return lines


def frol_context_block(weekday: str) -> list:
    """
    Return system-prompt lines showing the full Family Rule of Life grid.
    Call this from any companion's context builder so they can SEE the schedule.
    """
    try:
        from data_helpers import get_full_frol_context
        body = get_full_frol_context(weekday)
    except Exception as _e:
        body = f"(Could not load Rule of Life: {_e})"
    return [
        "== FAMILY RULE OF LIFE (Schedule Grid) ==",
        "You can see AND edit the McAdams family's Rule of Life below.",
        "The 'family-wide' schedule applies to all members. Per-person overrides exist for",
        "specific individuals on specific days (currently only Friday has per-person templates).",
        "",
        body,
    ]


def frol_edit_instructions() -> list:
    """
    Return system-prompt lines explaining the <frol_update> action tag.
    Call this from any companion's context builder so they can EDIT the schedule.
    """
    return [
        "",
        "== HOW TO EDIT THE FAMILY RULE OF LIFE ==",
        "When Mom asks you to change, add, or remove a time slot in the schedule, use",
        "the <frol_update> action tag. It is applied server-side automatically.",
        "",
        "FAMILY-WIDE change (updates family_schedule.json for everyone):",
        '  <frol_update weekday="Saturday" person="Family">',
        "  9:00 AM: Morning Prayer",
        "  10:00 AM: Morning chores",
        "  </frol_update>",
        "",
        "PERSON-SPECIFIC change (updates only that person's day template):",
        '  <frol_update weekday="Monday" person="JP">',
        "  8:00 AM: School — Saxon Math",
        "  9:00 AM: Latin",
        "  </frol_update>",
        "",
        "Tag rules:",
        "  - weekday: Monday / Tuesday / Wednesday / Thursday / Friday / Saturday / Sunday",
        "  - person: Family (family-wide) | JP | Joseph | Michael | Lauren | John",
        "  - Body: one 'H:MM AM/PM: Activity' line per slot",
        "  - To clear a slot entirely, write: '9:00 AM: ' (empty value)",
        "  - You may include multiple <frol_update> blocks in one response",
        "  - After the tag applies you will see a [FROL_UPDATED:...] confirmation",
        "  - Do NOT instruct Mom to open Settings — the tag applies the change directly.",
    ]


def undo_instructions() -> list:
    """Return system-prompt lines explaining the <undo_last_change/> action tag.
    Every companion gets these so Mom can simply say 'undo that' in chat."""
    return [
        "",
        "== HOW TO UNDO YOUR LAST CHANGE ==",
        "If Mom explicitly asks you to undo, revert, take back, or 'put back'",
        "the change you just made (e.g. 'undo that', 'never mind, undo',",
        "'revert your last change', 'put it back the way it was'), reply with",
        "the action tag <undo_last_change/> on its own line.",
        "",
        "What happens when you emit <undo_last_change/>:",
        "  - The system restores every file you wrote in your previous turn",
        "    to the snapshot taken just before that turn (full automatic).",
        "  - Mom will see a confirmation listing exactly which files were",
        "    rolled back. You don't need to spell those out yourself.",
        "  - Use it ALONE — do not combine <undo_last_change/> with",
        "    <plan_update>, <frol_update>, or any other action tag in the",
        "    same response.",
        "",
        "Only use this tag when Mom clearly wants to reverse YOUR most",
        "recent edit. Do not use it pre-emptively, do not use it for older",
        "edits, and do not invent it without an explicit request.",
        "",
    ]


def _js_companions_dict(self_tag: str) -> str:
    """Return a JS object literal of other companions for handoff rendering."""
    others = {tag: c for tag, c in COMPANIONS.items() if tag != self_tag}
    entries = []
    for tag, c in others.items():
        name  = c["name"].replace("'", "\\'")
        route = c["route"]
        emoji = c["emoji"]
        bg    = c["bg"]
        entries.append(f"'{tag}':{{'name':'{name}','route':'{route}','emoji':'{emoji}','bg':'{bg}'}}")
    return "{" + ",".join(entries) + "}"


# Shared JS helpers used by every companion's response bubble:
# escape HTML and convert markdown [label](url) into clickable <a> tags.
# Built as a regular (non-f) string so the regex backslashes don't violate
# claud rule #1 (no backslashes inside f-strings).
_LINKIFY_JS = (
    "\n// ── Shared markdown-link rendering (for companion response bubbles) ──\n"
    "function _escapeHTML(s){"
    "  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')"
    "    .replace(/>/g,'&gt;').replace(/\"/g,'&quot;').replace(/'/g,'&#39;');"
    "}\n"
    "function _linkify(s){"
    "  var esc=_escapeHTML(s);"
    "  return esc.replace(/\\[([^\\]]+)\\]\\(([^)\\s]+)\\)/g, function(m,label,url){"
    "    if(!/^(\\/|https?:\\/\\/)/.test(url)) return m;"
    "    return '<a href=\"'+url+'\" style=\"color:inherit;text-decoration:underline;font-weight:600;\">'+label+'</a>';"
    "  });"
    "}\n"
)


def handoff_js(self_tag: str) -> str:
    """
    Return the JS block to embed in a companion page for:
    1. Handoff tag stripping + button rendering (_stripHandoffTags, _renderHandoffBtns)
    2. ?q=&from= URL param prefill on page load
    """
    c        = COMPANIONS[self_tag]
    self_name   = c["name"].replace("'", "\\'")
    input_id    = c["input_id"]
    chat_id     = c["chat_id"]
    ho_dict     = _js_companions_dict(self_tag)

    return f"""
// ── Companion handoffs ({self_name}) ─────────────────────────────────────────
var _HO = {ho_dict};

function _stripHandoffTags(text) {{
    return text.replace(/\\[[A-Z]+\\][\\s\\S]*?\\[\\/[A-Z]+\\]/g, '').trim();
}}

function _renderHandoffBtns(full, wrapEl) {{
    if (!wrapEl) return;
    var rx = /\\[([A-Z]+)\\]([\\s\\S]*?)\\[\\/\\1\\]/g, m;
    while ((m = rx.exec(full)) !== null) {{
        var ho = _HO[m[1]];
        if (!ho) continue;
        var brief = m[2].trim();
        (function(ho, brief) {{
            var row = document.createElement('div');
            row.style.cssText = 'display:flex;align-items:center;gap:10px;margin-top:10px;'
                + 'padding:11px 14px;background:' + ho.bg + ';border-radius:10px;';
            var icon = document.createElement('span');
            icon.textContent = ho.emoji;
            icon.style.cssText = 'font-size:1.2em;flex-shrink:0;';
            var msg = document.createElement('span');
            msg.textContent = '{self_name} has a note for ' + ho.name + '.';
            msg.style.cssText = 'font-size:0.83em;color:rgba(255,255,255,0.85);flex:1;';
            var btn = document.createElement('a');
            btn.textContent = '\\u2192 Open in ' + ho.name;
            btn.href = ho.route + '?q=' + encodeURIComponent(brief) + '&from=' + encodeURIComponent('{self_name}');
            btn.style.cssText = 'padding:7px 15px;background:white;color:' + ho.bg + ';'
                + 'text-decoration:none;border-radius:8px;font-size:0.85em;font-weight:700;'
                + 'font-family:inherit;flex-shrink:0;white-space:nowrap;';
            row.appendChild(icon);
            row.appendChild(msg);
            row.appendChild(btn);
            wrapEl.appendChild(row);
        }})(ho, brief);
    }}
}}

// Prefill from ?q= URL param (handoff from another companion)
// The banner is rendered server-side; this only ensures the input is filled.
window.addEventListener('load', function() {{
    var params = new URLSearchParams(window.location.search);
    var q = params.get('q');
    if (!q || !q.trim()) return;
    var inp = document.getElementById('{input_id}');
    if (!inp) return;
    if (!inp.value) inp.value = q.trim();
    inp.style.height = 'auto';
    inp.style.height = Math.min(inp.scrollHeight, 120) + 'px';
}});
""" + _LINKIFY_JS
