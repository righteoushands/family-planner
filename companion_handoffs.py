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
}


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
    ]
    return lines


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
window.addEventListener('load', function() {{
    var params = new URLSearchParams(window.location.search);
    var q    = params.get('q');
    var from = params.get('from');
    if (!q || !q.trim()) return;
    var inp = document.getElementById('{input_id}');
    if (!inp) return;
    inp.value = q.trim();
    inp.style.height = 'auto';
    inp.style.height = Math.min(inp.scrollHeight, 120) + 'px';
    inp.focus();
    var sender = from ? from : 'A companion';
    var banner = document.createElement('div');
    banner.innerHTML = '&#128203; <strong>' + sender + ' has a note for {self_name}.</strong> Review it below and hit Send, or edit first.';
    banner.style.cssText = 'background:#dbeafe;color:#1e3a8a;font-size:0.82em;padding:8px 14px;'
        + 'border-radius:8px;margin:10px 14px;border:1px solid #93c5fd;';
    var chat = document.getElementById('{chat_id}');
    if (chat) {{
        chat.parentNode ? chat.parentNode.insertBefore(banner, chat) : chat.appendChild(banner);
    }}
}});
"""
