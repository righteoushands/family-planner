"""
render_memory_book.py — Family memory book.

Stores memorable moments Mom wants to remember, saved from Lucy conversations
or entered manually. Displayed as a warm journal/scrapbook page.
"""
import json
import os
import uuid
from datetime import datetime
from safe_utils import safe_save_json
try:
    from zoneinfo import ZoneInfo
    _EASTERN = ZoneInfo("America/New_York")
except ImportError:
    import pytz
    _EASTERN = pytz.timezone("America/New_York")

_MEMORY_FILE = os.path.join("data", "memory_book.json")


# ─────────────────────────────────────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_memory_book() -> dict:
    if os.path.exists(_MEMORY_FILE):
        try:
            with open(_MEMORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"entries": []}


def save_memory_book(data: dict) -> None:
    safe_save_json(_MEMORY_FILE, data)


def add_memory_entry(text: str, date_iso: str = "") -> dict:
    now = datetime.now(_EASTERN)
    if not date_iso:
        date_iso = now.date().isoformat()
    entry = {
        "id":       str(uuid.uuid4())[:8],
        "date":     date_iso,
        "text":     text.strip(),
        "saved_at": now.isoformat(),
    }
    book = load_memory_book()
    book["entries"].insert(0, entry)  # newest first
    save_memory_book(book)
    return entry


def delete_memory_entry(entry_id: str) -> bool:
    book = load_memory_book()
    before = len(book["entries"])
    book["entries"] = [e for e in book["entries"] if e.get("id") != entry_id]
    if len(book["entries"]) < before:
        save_memory_book(book)
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Page renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_memory_book_page() -> str:
    from html import escape
    book  = load_memory_book()
    entries = book.get("entries", [])

    # Group by month
    grouped: dict[str, list] = {}
    for e in entries:
        d = e.get("date", "")
        try:
            from datetime import date as _date
            parsed = _date.fromisoformat(d)
            month_key = parsed.strftime("%B %Y")
        except Exception:
            month_key = d[:7] if d else "Unknown"
        grouped.setdefault(month_key, []).append(e)

    entries_html = ""
    if not entries:
        entries_html = """
        <div style="text-align:center;padding:60px 20px;color:#aaa;">
            <div style="font-size:2em;margin-bottom:12px;">📖</div>
            <div style="font-size:1em;color:#bbb;">No memories saved yet.</div>
            <div style="font-size:0.85em;color:#ccc;margin-top:6px;">
                Ask Lucy about your day — she&#39;ll prompt you to save special moments.
            </div>
        </div>"""
    else:
        for month, month_entries in grouped.items():
            entries_html += f"""
            <div style="margin-bottom:32px;">
                <div style="font-size:0.75em;font-weight:700;letter-spacing:0.12em;
                            color:#c49020;text-transform:uppercase;margin-bottom:14px;
                            padding-bottom:6px;border-bottom:1px solid #ede7e0;">
                    {escape(month)}
                </div>"""
            for e in month_entries:
                eid  = escape(e.get("id", ""))
                text = escape(e.get("text", ""))
                d    = e.get("date", "")
                try:
                    from datetime import date as _date
                    parsed = _date.fromisoformat(d)
                    day_label = parsed.strftime("%A, %B %d")
                except Exception:
                    day_label = d
                entries_html += f"""
                <div style="background:white;border:1px solid #ede7e0;border-radius:12px;
                            padding:16px 18px;margin-bottom:12px;position:relative;
                            box-shadow:0 1px 4px rgba(0,0,0,0.04);">
                    <div style="font-size:0.75em;color:#c49020;font-weight:600;margin-bottom:6px;">
                        {escape(day_label)}
                    </div>
                    <div style="font-size:0.92em;color:#1a1a1a;line-height:1.6;white-space:pre-wrap;">
                        {text}
                    </div>
                    <button onclick="deleteMemory('{eid}')"
                            style="position:absolute;top:12px;right:12px;background:none;
                                   border:none;color:#ccc;cursor:pointer;font-size:0.8em;
                                   padding:2px 6px;border-radius:4px;"
                            onmouseover="this.style.color='#c0392b'"
                            onmouseout="this.style.color='#ccc'">✕</button>
                </div>"""
            entries_html += "</div>"

    body = f"""
<div style="max-width:680px;margin:0 auto;padding:24px 16px 60px;">

    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:28px;">
        <a href="/" style="font-size:0.82em;color:#aaa;text-decoration:none;">&larr; Dashboard</a>
        <a href="/lucy" style="font-size:0.82em;color:#8b5a3c;text-decoration:none;">Talk to Lucy &rarr;</a>
    </div>

    <div style="display:flex;align-items:center;gap:14px;margin-bottom:32px;">
        <div style="font-size:2em;">📖</div>
        <div>
            <div style="font-family:Georgia,serif;font-size:1.6em;font-weight:600;color:#1a1a1a;line-height:1.1;">
                Memory Book
            </div>
            <div style="font-size:0.82em;color:#aaa;margin-top:3px;">
                Moments worth remembering
            </div>
        </div>
    </div>

    <!-- Manual add form -->
    <div style="background:#fdfaf7;border:1px solid #ede7e0;border-radius:12px;
                padding:16px;margin-bottom:32px;">
        <div style="font-size:0.8em;color:#888;font-weight:600;margin-bottom:8px;">
            ADD A MEMORY
        </div>
        <textarea id="new-memory" rows="3" placeholder="Write something worth remembering…"
                  style="width:100%;resize:vertical;font-family:inherit;font-size:0.9em;
                         padding:10px 12px;border:1px solid #e4dbd2;border-radius:8px;
                         outline:none;line-height:1.55;color:#1a1a1a;background:white;
                         box-sizing:border-box;"></textarea>
        <div style="display:flex;justify-content:flex-end;margin-top:8px;">
            <button onclick="addMemory()"
                    style="padding:8px 20px;background:#3b2a1a;color:white;border:none;
                           border-radius:8px;cursor:pointer;font-size:0.85em;font-weight:600;
                           font-family:inherit;">
                Save Memory
            </button>
        </div>
    </div>

    <!-- Entries -->
    <div id="entries-container">
        {entries_html}
    </div>

</div>

<script>
function addMemory() {{
    var text = document.getElementById('new-memory').value.trim();
    if (!text) return;
    fetch('/memory-book-save', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: 'text=' + encodeURIComponent(text)
    }}).then(function(r) {{
        if (r.ok) {{ location.reload(); }}
        else {{ alert('Could not save. Please try again.'); }}
    }});
}}

function deleteMemory(id) {{
    if (!confirm('Remove this memory?')) return;
    fetch('/memory-book-delete', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: 'id=' + encodeURIComponent(id)
    }}).then(function(r) {{
        if (r.ok) {{ location.reload(); }}
    }});
}}
</script>"""

    from ui_helpers import html_page
    return html_page("Memory Book", body)
