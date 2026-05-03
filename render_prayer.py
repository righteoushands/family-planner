"""
render_prayer.py — Prayer Intentions

Routes:
  GET  /prayer-intentions              — full list
  GET  /prayer-intention/ID            — detail modal/page
  GET  /prayer-intention/share/TOKEN   — public share card
  POST /prayer-intention-add           — add intention (multipart, optional photo)
  POST /prayer-intention-delete        — delete intention
  POST /prayer-intention-log           — add a prayer log entry
  POST /prayer-intention-complete      — mark answered / archive

Data:
  data/prayer/intentions.json          — list of all intentions
  data/prayer/photos/ID.jpg            — uploaded photos
"""
import json, os, uuid, base64
from datetime import date, timedelta
from html import escape

from render_settings import load_app_settings
from ui_helpers import html_page, top_nav, render_status_message
from safe_utils import safe_save_json

PRAYER_DIR   = "data/prayer"
PHOTOS_DIR   = "data/prayer/photos"
INTENTS_FILE = "data/prayer/intentions.json"

# Built-in prayer types
PRAYER_TYPES = [
    ("rosary",    "Rosary",               "🌹"),
    ("chaplet",   "Divine Mercy Chaplet",  "✝"),
    ("mass",      "Holy Mass",             "⛪"),
    ("sacrifice", "Sacrifice",             "🕊"),
    ("fast",      "Fasting",               "💧"),
    ("holy_hour", "Holy Hour",             "🕯"),
    ("novena",    "Novena",                "📿"),
    ("office",    "Liturgy of the Hours",  "📖"),
    ("custom",    "Custom",                "✨"),
]

PRAYER_TYPE_MAP = {k: (label, icon) for k, label, icon in PRAYER_TYPES}


# ── Data helpers ──────────────────────────────────────────────────────────────

def _ensure_dirs():
    os.makedirs(PRAYER_DIR,  exist_ok=True)
    os.makedirs(PHOTOS_DIR,  exist_ok=True)


def load_intentions() -> list:
    _ensure_dirs()
    try:
        with open(INTENTS_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_intentions(intentions: list):
    safe_save_json(INTENTS_FILE, intentions)


def _update_intention(intention_id: str, updates: dict):
    intentions = load_intentions()
    for i in intentions:
        if i.get("id") == intention_id:
            i.update(updates)
    save_intentions(intentions)


def add_intention(title: str, description: str = "",
                  photo_bytes: bytes = None, photo_ext: str = "jpg") -> dict:
    _ensure_dirs()
    new_id = str(uuid.uuid4())[:8]
    token  = str(uuid.uuid4())[:12]
    photo_filename = ""
    if photo_bytes:
        photo_filename = f"{new_id}.{photo_ext.lower().lstrip('.')}"
        with open(f"{PHOTOS_DIR}/{photo_filename}", "wb") as f:
            f.write(photo_bytes)
    intention = {
        "id":          new_id,
        "title":       title,
        "description": description,
        "photo":       photo_filename,
        "created":     date.today().isoformat(),
        "active":      True,
        "answered":    False,
        "prayer_log":  [],
        "share_token": token,
    }
    intentions = load_intentions()
    intentions.insert(0, intention)
    save_intentions(intentions)
    return intention


def log_prayer(intention_id: str, prayer_type: str,
               count: int = 1, custom_label: str = "", note: str = ""):
    intentions = load_intentions()
    for i in intentions:
        if i.get("id") == intention_id:
            entry = {
                "date":         date.today().isoformat(),
                "type":         prayer_type,
                "custom_label": custom_label,
                "count":        max(1, count),
                "note":         note,
            }
            i.setdefault("prayer_log", []).append(entry)
    save_intentions(intentions)


def _photo_src(photo_filename: str) -> str:
    """Return a URL src for a prayer photo."""
    if not photo_filename:
        return ""
    # Verify file exists
    path = f"{PHOTOS_DIR}/{photo_filename}"
    if os.path.exists(path):
        return f"/prayer-photo/{photo_filename}"
    return ""


def _photo_data_uri(photo_filename: str) -> str:
    """Legacy — redirect to URL-based approach."""
    return _photo_src(photo_filename)


def _prayer_summary(prayer_log: list) -> dict:
    """Aggregate totals by type."""
    totals = {}
    for entry in prayer_log:
        ptype = entry.get("type", "custom")
        label_key = entry.get("custom_label") or ptype
        count = entry.get("count", 1)
        totals[label_key] = totals.get(label_key, 0) + count
    return totals


def _total_prayers(prayer_log: list) -> int:
    return sum(e.get("count", 1) for e in prayer_log)


# ── Intention card (shared between list and detail) ───────────────────────────

def _intention_card_small(intention: dict, show_open_btn: bool = True) -> str:
    iid         = escape(intention.get("id",""))
    title       = escape(intention.get("title",""))
    desc        = escape(intention.get("description","")[:80])
    created     = escape(intention.get("created",""))
    photo       = intention.get("photo","")
    answered    = intention.get("answered", False)
    prayer_log  = intention.get("prayer_log", [])
    total       = _total_prayers(prayer_log)
    summary     = _prayer_summary(prayer_log)

    # Photo thumbnail
    photo_html = ""
    if photo:
        uri = _photo_data_uri(photo)
        if uri:
            photo_html = (
                f'<img src="{uri}" alt="{title}" '
                f'style="width:52px;height:52px;object-fit:cover;'
                f'border-radius:10px;flex-shrink:0;">'
            )
        else:
            photo_html = (
                f'<div style="width:52px;height:52px;border-radius:10px;'
                f'background:var(--parchment);display:flex;align-items:center;'
                f'justify-content:center;font-size:1.4em;flex-shrink:0;">🙏</div>'
            )
    else:
        photo_html = (
            f'<div style="width:52px;height:52px;border-radius:10px;'
            f'background:var(--parchment);display:flex;align-items:center;'
            f'justify-content:center;font-size:1.4em;flex-shrink:0;">🙏</div>'
        )

    # Prayer type pills
    pills = ""
    for label_key, count in list(summary.items())[:3]:
        _, icon = PRAYER_TYPE_MAP.get(label_key, ("", "✨"))
        pills += (
            f'<span style="font-size:0.65em;background:var(--gold-light);'
            f'color:var(--brown);padding:1px 6px;border-radius:8px;'
            f'font-weight:700;">{icon} {count}x</span> '
        )

    answered_badge = ""
    if answered:
        answered_badge = (
            f'<span style="font-size:0.65em;background:#dcfce7;color:#166534;'
            f'font-weight:700;padding:1px 7px;border-radius:10px;margin-left:4px;">'
            f'✓ Answered</span>'
        )

    open_btn = ""
    if show_open_btn:
        open_btn = (
            f'<button onclick="openIntention(\'{iid}\')" '
            f'style="padding:5px 12px;font-size:0.75em;background:var(--ink);'
            f'color:var(--gold-light);border:none;border-radius:8px;'
            f'font-family:inherit;cursor:pointer;font-weight:600;flex-shrink:0;">'
            f'Open</button>'
        )

    border = "1.5px solid #bbf7d0" if answered else "1.5px solid var(--border)"
    bg     = "#f0fdf4" if answered else "white"

    # Pre-compute conditionals
    desc_html  = ('<div style="font-size:0.78em;color:var(--ink-muted);margin-top:2px;">'
                  + desc + ('...' if len(intention.get('description','')) > 80 else '')
                  + '</div>') if desc else ''
    total_html = ('<span style="font-size:0.65em;color:var(--ink-faint);">'
                  + str(total) + ' prayers total</span>') if total > 0 else ''

    return (
        '<div id="card-' + iid + '" style="border:' + border + ';border-radius:12px;'
        'padding:12px;margin-bottom:8px;background:' + bg + ';cursor:pointer;" '
        'onclick="openIntention(\'' + iid + '\')">'
        '<div style="display:flex;align-items:flex-start;gap:10px;">'
        + photo_html
        + '<div style="flex:1;min-width:0;">'
        '<div style="font-weight:700;font-size:0.92em;color:var(--ink);">'
        + title + answered_badge + '</div>'
        + desc_html
        + '<div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:3px;">'
        + pills + total_html
        + '</div>'
        '<div style="font-size:0.65em;color:var(--ink-faint);margin-top:3px;">'
        'Added ' + created + '</div>'
        '</div>'
        + open_btn
        + '</div></div>'
    )


# ── Detail modal content ──────────────────────────────────────────────────────

def _intention_detail_html(intention: dict) -> str:
    """Full detail view rendered inside a modal."""
    iid        = escape(intention.get("id",""))
    title      = escape(intention.get("title",""))
    desc       = escape(intention.get("description",""))
    photo      = intention.get("photo","")
    answered   = intention.get("answered", False)
    prayer_log = intention.get("prayer_log", [])
    token      = escape(intention.get("share_token",""))
    created    = escape(intention.get("created",""))
    total      = _total_prayers(prayer_log)
    summary    = _prayer_summary(prayer_log)

    # Photo
    photo_html = ""
    if photo:
        uri = _photo_data_uri(photo)
        if uri:
            photo_html = (
                f'<div style="text-align:center;margin-bottom:14px;">'
                f'<img src="{uri}" alt="{title}" '
                f'style="max-width:100%;max-height:200px;object-fit:cover;'
                f'border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.12);">'
                f'</div>'
            )

    # Prayer summary tiles
    summary_tiles = ""
    for label_key, count in summary.items():
        label_txt, icon = PRAYER_TYPE_MAP.get(label_key, (label_key, "✨"))
        display = label_key if label_key not in PRAYER_TYPE_MAP else label_txt
        summary_tiles += (
            f'<div style="text-align:center;padding:8px 12px;'
            f'background:var(--gold-light);border-radius:10px;">'
            f'<div style="font-size:1.1em;">{icon}</div>'
            f'<div style="font-size:1.1rem;font-weight:700;color:var(--ink);">{count}</div>'
            f'<div style="font-size:0.65em;color:var(--brown);font-weight:600;">'
            f'{escape(display)}</div>'
            f'</div>'
        )

    # Prayer log entries (last 10)
    log_rows = ""
    for entry in reversed(prayer_log[-10:]):
        etype   = entry.get("type","custom")
        elabel  = entry.get("custom_label","") or PRAYER_TYPE_MAP.get(etype, (etype,"✨"))[0]
        eicon   = PRAYER_TYPE_MAP.get(etype, ("","✨"))[1]
        ecount  = entry.get("count", 1)
        enote   = escape(entry.get("note",""))
        edate   = escape(entry.get("date",""))
        log_rows += (
            f'<div style="display:flex;align-items:center;gap:8px;padding:6px 0;'
            f'border-bottom:1px solid var(--border-light);">'
            f'<span style="font-size:0.9em;">{eicon}</span>'
            f'<div style="flex:1;">'
            + '<span style="font-size:0.82em;font-weight:600;">' + escape(elabel) + '</span>'
            + ('<span style="font-size:0.75em;color:var(--ink-muted);margin-left:4px;">' + enote + '</span>' if enote else '')
            + '</div>'
            f'<span style="font-size:0.75em;font-weight:700;color:var(--brown);">{ecount}×</span>'
            f'<span style="font-size:0.7em;color:var(--ink-faint);">{edate}</span>'
            f'</div>'
        )

    # Prayer type buttons
    type_btns = ""
    for key, label, icon in PRAYER_TYPES[:-1]:  # all except custom
        type_btns += (
            f'<button onclick="quickLog(\'{iid}\',\'{key}\')" '
            f'style="padding:6px 12px;font-size:0.78em;border-radius:8px;'
            f'background:var(--parchment);color:var(--ink);border:1px solid var(--border);'
            f'font-family:inherit;cursor:pointer;display:flex;align-items:center;gap:4px;">'
            f'{icon} {escape(label)}</button>'
        )

    # Share URL
    share_url = f"/prayer-intention/share/{token}"

    answered_toggle = (
        f'<button onclick="markAnswered(\'{iid}\', {"false" if answered else "true"})" '
        f'style="padding:6px 14px;font-size:0.78em;border-radius:8px;'
        f'background:{"#dcfce7" if answered else "var(--parchment)"};'
        f'color:{"#166534" if answered else "var(--ink)"};'
        f'border:1px solid {"#86efac" if answered else "var(--border)"};'
        f'font-family:inherit;cursor:pointer;font-weight:600;">'
        f'{"✓ Answered — click to re-open" if answered else "Mark as answered ✓"}</button>'
    )

    return f"""
{photo_html}

<div style="font-family:'Cormorant Garamond',Georgia,serif;
            font-size:1.5rem;font-weight:600;color:var(--ink);margin-bottom:4px;">
  {title}
</div>
<div style="font-size:0.72em;color:var(--ink-faint);margin-bottom:10px;">
  Added {created} &middot; {total} total prayers offered
</div>

{"<div style='font-size:0.88em;line-height:1.65;color:var(--ink);margin-bottom:12px;padding:10px 12px;background:var(--parchment);border-radius:8px;'>" + desc + "</div>" if desc else ""}

{"<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(70px,1fr));gap:8px;margin-bottom:14px;'>" + summary_tiles + "</div>" if summary_tiles else '<div style="font-size:0.82em;color:var(--ink-faint);margin-bottom:14px;">No prayers logged yet.</div>'}

<!-- Quick log -->
<div style="margin-bottom:14px;">
  <div style="font-size:0.7em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:8px;">Log a Prayer</div>
  <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px;">
    {type_btns}
  </div>
  <!-- Custom prayer entry -->
  <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px;">
    <input type="text" id="custom-label-{iid}" placeholder="Custom prayer type..."
           style="flex:1;min-width:120px;padding:6px 10px;font-size:0.82em;
                  border-radius:8px;border:1.5px solid var(--border);font-family:inherit;">
    <input type="number" id="custom-count-{iid}" value="1" min="1"
           style="width:60px;padding:6px;font-size:0.82em;border-radius:8px;
                  border:1.5px solid var(--border);font-family:inherit;text-align:center;">
    <input type="text" id="custom-note-{iid}" placeholder="Note (optional)..."
           style="flex:2;min-width:120px;padding:6px 10px;font-size:0.82em;
                  border-radius:8px;border:1.5px solid var(--border);font-family:inherit;">
    <button onclick="customLog('{iid}')"
            style="padding:6px 14px;background:var(--ink);color:var(--gold-light);
                   border:none;border-radius:8px;font-family:inherit;
                   font-size:0.82em;cursor:pointer;font-weight:600;">+ Log</button>
  </div>
  <div id="log-status-{iid}" style="font-size:0.78em;color:#22c55e;min-height:16px;margin-top:4px;"></div>
</div>

<!-- Prayer log history -->
{"<div style='margin-bottom:14px;'><div style='font-size:0.7em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:6px;'>Prayer History</div>" + log_rows + "</div>" if log_rows else ""}

<!-- Share + actions -->
<div style="display:flex;flex-wrap:wrap;gap:8px;padding-top:10px;
            border-top:1px solid var(--border-light);">
  {answered_toggle}
  <button onclick="aiIntentionPrayer('{iid}', this)"
          style="padding:6px 14px;font-size:0.78em;border-radius:8px;
                 background:var(--gold-light);color:var(--brown);
                 border:1px solid var(--gold-mid);font-family:inherit;cursor:pointer;">
    ✨ Write a prayer
  </button>
  <button onclick="copyShareLink('{share_url}')"
          style="padding:6px 14px;font-size:0.78em;border-radius:8px;
                 background:var(--parchment);color:var(--brown);
                 border:1px solid var(--border);font-family:inherit;cursor:pointer;">
    📤 Share with a friend
  </button>
  <button onclick="deleteIntention('{iid}')"
          style="padding:6px 14px;font-size:0.78em;border-radius:8px;
                 background:transparent;color:#ef4444;
                 border:1px solid #fecaca;font-family:inherit;cursor:pointer;">
    Remove
  </button>
</div>
<div id="ai-prayer-{iid}" style="display:none;margin-top:10px;padding:12px;
     background:linear-gradient(135deg,#1c1610,#2a1e10);border-radius:10px;
     font-size:0.88em;line-height:1.7;color:var(--gold-light);font-style:italic;">
</div>
<div id="share-status-{iid}" style="font-size:0.78em;color:#166534;
     min-height:16px;margin-top:4px;"></div>
"""


# ── Public share page ─────────────────────────────────────────────────────────

def render_share_page(token: str) -> str:
    intentions = load_intentions()
    intention  = next((i for i in intentions if i.get("share_token") == token), None)

    if not intention:
        body = top_nav() + """
<div style="text-align:center;padding:40px 20px;">
  <div style="font-size:2em;margin-bottom:12px;">🙏</div>
  <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.5rem;
              color:var(--ink);">This intention is no longer available.</div>
</div>"""
        return html_page("Prayer Intention", body)

    title      = escape(intention.get("title",""))
    desc       = escape(intention.get("description",""))
    photo      = intention.get("photo","")
    prayer_log = intention.get("prayer_log",[])
    total      = _total_prayers(prayer_log)
    summary    = _prayer_summary(prayer_log)

    photo_html = ""
    if photo:
        uri = _photo_data_uri(photo)
        if uri:
            photo_html = (
                f'<div style="text-align:center;margin-bottom:20px;">'
                f'<img src="{uri}" alt="{title}" '
                f'style="max-width:100%;max-height:240px;object-fit:cover;'
                f'border-radius:16px;box-shadow:0 6px 24px rgba(0,0,0,0.15);">'
                f'</div>'
            )

    summary_html = ""
    for label_key, count in summary.items():
        label_txt, icon = PRAYER_TYPE_MAP.get(label_key, (label_key, "✨"))
        display = label_key if label_key not in PRAYER_TYPE_MAP else label_txt
        summary_html += (
            f'<div style="text-align:center;padding:10px 16px;'
            f'background:var(--gold-light);border-radius:12px;">'
            f'<div style="font-size:1.3em;">{icon}</div>'
            f'<div style="font-size:1.3rem;font-weight:700;color:var(--ink);">{count}</div>'
            f'<div style="font-size:0.72em;color:var(--brown);font-weight:600;">'
            f'{escape(display)}</div>'
            f'</div>'
        )

    body = f"""
<div style="max-width:480px;margin:0 auto;padding:20px 16px;">
  <div style="text-align:center;margin-bottom:20px;">
    <div style="font-size:1.5em;">🙏</div>
    <div style="font-size:0.82em;color:var(--ink-muted);margin-top:4px;">
      Someone is praying for this intention
    </div>
  </div>

  {photo_html}

  <div style="font-family:'Cormorant Garamond',Georgia,serif;
              font-size:1.8rem;font-weight:600;color:var(--ink);
              text-align:center;margin-bottom:8px;">
    {title}
  </div>

  {"<div style='font-size:0.88em;line-height:1.7;color:var(--ink-muted);text-align:center;margin-bottom:16px;'>" + desc + "</div>" if desc else ""}

  <div style="padding:14px 16px;background:linear-gradient(135deg,#1c1610,#2a1e10);
              border-radius:12px;text-align:center;margin-bottom:16px;">
    <div style="font-size:0.7em;font-weight:800;letter-spacing:.12em;
                text-transform:uppercase;color:rgba(201,164,74,0.7);margin-bottom:4px;">
      Prayers offered
    </div>
    <div style="font-size:2rem;font-weight:700;color:var(--gold-light);">{total}</div>
  </div>

  {"<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(80px,1fr));gap:8px;margin-bottom:20px;'>" + summary_html + "</div>" if summary_html else ""}

  <div style="text-align:center;padding:16px;background:var(--parchment);
              border-radius:12px;font-size:0.85em;color:var(--ink-muted);
              line-height:1.6;font-style:italic;">
    &ldquo;The prayer of a righteous person is powerful and effective.&rdquo;<br>
    <span style="font-size:0.85em;color:var(--ink-faint);">— James 5:16</span>
  </div>
</div>"""
    return html_page(f"Praying for: {intention.get('title','')}", body)


# ── Main list page ────────────────────────────────────────────────────────────

def render_prayer_page(status: str = "") -> str:
    intentions = load_intentions()
    active     = [i for i in intentions if i.get("active", True) and not i.get("answered")]
    answered   = [i for i in intentions if i.get("answered")]

    active_cards = "".join(_intention_card_small(i) for i in active)
    answered_cards = "".join(_intention_card_small(i) for i in answered)

    if not active_cards:
        active_cards = (
            '<div style="text-align:center;padding:24px;color:var(--ink-faint);">'
            '<div style="font-size:2em;margin-bottom:8px;">🙏</div>'
            '<div style="font-size:0.88em;">No active intentions yet.</div>'
            '</div>'
        )

    # Add intention form
    type_opts = "".join(
        f'<option value="{k}">{icon} {escape(label)}</option>'
        for k, label, icon in PRAYER_TYPES
    )

    # Build detail modal content for all intentions (pre-rendered, shown/hidden)
    modal_contents = {}
    for i in intentions:
        modal_contents[i.get("id","")] = _intention_detail_html(i)

    modal_contents_js = json.dumps(modal_contents)

    # Liturgy of the Hours widget (moved here from the dashboard)
    try:
        from render_liturgy_hours import render_hours_dashboard_widget
        _loh_widget = render_hours_dashboard_widget()
    except Exception:
        _loh_widget = ""

    body = top_nav() + render_status_message(status) + f"""
<div style="display:flex;align-items:flex-start;justify-content:space-between;
            flex-wrap:wrap;gap:8px;padding-top:4px;margin-bottom:16px;">
  <div>
    <div style="font-family:'Cormorant Garamond',Georgia,serif;
                font-size:2rem;font-weight:600;color:var(--ink);">Prayer Intentions</div>
    <div style="font-size:0.85em;color:var(--ink-muted);margin-top:2px;">
      {len(active)} active &middot; {len(answered)} answered
    </div>
  </div>
  <button onclick="showAddForm()"
          style="padding:8px 18px;background:var(--ink);color:var(--gold-light);
                 border:none;border-radius:10px;font-size:0.85em;font-weight:700;
                 font-family:inherit;cursor:pointer;">+ Add intention</button>
</div>

<!-- Liturgy of the Hours -->
{_loh_widget}

<!-- Lucy's Notes: one per family member + friends/intentions -->
<div style="margin-bottom:20px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:10px;">Lucy's Notes</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
    <!-- Lauren -->
    <div class="card card-tight" style="border-left:4px solid #7c3aed;grid-column:1/-1;">
      <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                  color:#7c3aed;margin-bottom:6px;">&#10022; For Lauren</div>
      <div id="lucy-prayer-lauren"
           style="font-size:.88em;line-height:1.6;color:#444;min-height:36px;">
        <span style="color:#bbb;font-style:italic;">Loading\u2026</span>
      </div>
    </div>
    <!-- John -->
    <div class="card card-tight" style="border-left:4px solid #2563eb;grid-column:1/-1;">
      <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                  color:#2563eb;margin-bottom:6px;">&#10022; For John</div>
      <div id="lucy-prayer-john"
           style="font-size:.88em;line-height:1.6;color:#444;min-height:36px;">
        <span style="color:#bbb;font-style:italic;">Loading\u2026</span>
      </div>
    </div>
    <!-- JP -->
    <div class="card card-tight" style="border-left:4px solid #b45309;">
      <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                  color:#b45309;margin-bottom:6px;">&#10022; For JP</div>
      <div id="lucy-prayer-jp"
           style="font-size:.88em;line-height:1.6;color:#444;min-height:36px;">
        <span style="color:#bbb;font-style:italic;">Loading\u2026</span>
      </div>
    </div>
    <!-- Joseph -->
    <div class="card card-tight" style="border-left:4px solid #047857;">
      <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                  color:#047857;margin-bottom:6px;">&#10022; For Joseph</div>
      <div id="lucy-prayer-joseph"
           style="font-size:.88em;line-height:1.6;color:#444;min-height:36px;">
        <span style="color:#bbb;font-style:italic;">Loading\u2026</span>
      </div>
    </div>
    <!-- Michael -->
    <div class="card card-tight" style="border-left:4px solid #0284c7;">
      <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                  color:#0284c7;margin-bottom:6px;">&#10022; For Michael</div>
      <div id="lucy-prayer-michael"
           style="font-size:.88em;line-height:1.6;color:#444;min-height:36px;">
        <span style="color:#bbb;font-style:italic;">Loading\u2026</span>
      </div>
    </div>
    <!-- James -->
    <div class="card card-tight" style="border-left:4px solid #be185d;">
      <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                  color:#be185d;margin-bottom:6px;">&#10022; For James</div>
      <div id="lucy-prayer-james"
           style="font-size:.88em;line-height:1.6;color:#444;min-height:36px;">
        <span style="color:#bbb;font-style:italic;">Loading\u2026</span>
      </div>
    </div>
    <!-- Friends & Intentions -->
    <div class="card card-tight" style="border-left:4px solid var(--gold-mid);grid-column:1/-1;">
      <div style="font-size:0.72em;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
                  color:var(--brown);margin-bottom:6px;">&#10022; Friends &amp; Intentions</div>
      <div id="lucy-prayer-friends"
           style="font-size:.88em;line-height:1.6;color:#444;min-height:36px;">
        <span style="color:#bbb;font-style:italic;">Loading\u2026</span>
      </div>
    </div>
  </div>
</div>
<script>
(function() {{
  var _slugs = ['lauren','john','jp','joseph','michael','james','friends'];
  _slugs.forEach(function(slug) {{
    var el = document.getElementById('lucy-prayer-' + slug);
    if (!el) return;
    fetch('/lucy-prayer-brief/' + slug)
      .then(function(r) {{ return r.json(); }})
      .then(function(d) {{
        el.innerHTML = d.html || "<span style='color:#bbb;font-style:italic;'>Not available right now.</span>";
      }})
      .catch(function() {{
        el.innerHTML = "<span style='color:#bbb;font-style:italic;'>Could not load.</span>";
      }});
  }});
}})();
</script>

<!-- Add form (hidden by default) -->
<div id="add-form" style="display:none;margin-bottom:16px;">
  <div class="card" style="border:2px solid var(--gold-mid);">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;
                text-transform:uppercase;color:var(--ink-faint);margin-bottom:12px;">
      New Prayer Intention
    </div>
    <div id="add-form-error" style="display:none;font-size:0.82em;color:#ef4444;margin-bottom:8px;"></div>
    <label style="font-size:0.75em;">Intention title *</label>
    <input type="text" id="add-title" placeholder="e.g. Grandma's healing..."
           style="margin-bottom:10px;" oninput="prayerDraftSave()">
    <label style="font-size:0.75em;">Description / prayer request</label>
    <textarea id="add-desc" rows="3"
              placeholder="Details about what you're praying for..."
              style="margin-bottom:10px;font-size:0.88em;resize:vertical;"
              oninput="prayerDraftSave()"></textarea>
    <label style="font-size:0.75em;">Photo (optional)</label>
    <input type="file" id="add-photo" accept="image/*"
           style="margin-bottom:14px;font-size:0.85em;">
    <div style="display:flex;gap:8px;">
      <button id="add-submit-btn" onclick="submitAddIntention()"
              style="padding:8px 18px;background:var(--ink);color:var(--gold-light);
                     border:none;border-radius:8px;font-family:inherit;font-size:0.88em;
                     cursor:pointer;font-weight:600;">Add intention</button>
      <button type="button" onclick="hideAddForm()"
              style="padding:8px 14px;background:transparent;border:1.5px solid var(--border);
                     border-radius:8px;font-family:inherit;font-size:0.88em;cursor:pointer;">
        Cancel</button>
    </div>
  </div>
</div>

<!-- Active intentions -->
<div style="margin-bottom:20px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:10px;">Active</div>
  <div id="active-list">{active_cards}</div>
</div>

<!-- Answered intentions -->
{"<div style='margin-bottom:20px;'><div style='font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:10px;'>Answered ✓</div>" + answered_cards + "</div>" if answered_cards else ""}

<!-- Detail modal -->
<div id="intention-modal"
     style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.55);
            z-index:1000;padding:16px;align-items:flex-start;justify-content:center;
            overflow-y:auto;">
  <div style="background:white;border-radius:16px;padding:22px;
              max-width:480px;width:100%;margin:20px auto;position:relative;">
    <button onclick="closeModal()"
            style="position:absolute;top:14px;right:14px;background:none;border:none;
                   font-size:1.3em;cursor:pointer;color:var(--ink-faint);">&times;</button>
    <div id="modal-body"><!-- filled by JS --></div>
  </div>
</div>

<script>
var _modalContents = {modal_contents_js};

function showAddForm() {{
  document.getElementById('add-form').style.display = 'block';
  document.getElementById('add-form').scrollIntoView({{behavior:'smooth'}});
}}
function hideAddForm() {{
  document.getElementById('add-form').style.display = 'none';
}}

function openIntention(id) {{
  var body = document.getElementById('modal-body');
  var modal = document.getElementById('intention-modal');
  if (!body || !modal) return;
  body.innerHTML = _modalContents[id] || '<p>Not found.</p>';
  modal.style.display = 'flex';
  document.body.style.overflow = 'hidden';
}}

function closeModal() {{
  var modal = document.getElementById('intention-modal');
  if (modal) modal.style.display = 'none';
  document.body.style.overflow = '';
}}

// Close on backdrop click
document.getElementById('intention-modal').addEventListener('click', function(e) {{
  if (e.target === this) closeModal();
}});

function quickLog(iid, ptype) {{
  fetch('/prayer-intention-log', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'id=' + encodeURIComponent(iid) +
          '&type=' + encodeURIComponent(ptype) +
          '&count=1&note='
  }}).then(function() {{
    var el = document.getElementById('log-status-' + iid);
    if (el) {{ el.textContent = 'Logged \u2713'; setTimeout(function(){{el.textContent=''}},2000); }}
  }});
}}

function customLog(iid) {{
  var label = document.getElementById('custom-label-' + iid);
  var count = document.getElementById('custom-count-' + iid);
  var note  = document.getElementById('custom-note-' + iid);
  if (!label || !label.value.trim()) return;
  fetch('/prayer-intention-log', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'id=' + encodeURIComponent(iid) +
          '&type=custom' +
          '&custom_label=' + encodeURIComponent(label.value.trim()) +
          '&count=' + encodeURIComponent(count ? count.value : '1') +
          '&note='  + encodeURIComponent(note  ? note.value  : '')
  }}).then(function() {{
    var el = document.getElementById('log-status-' + iid);
    if (el) {{ el.textContent = 'Logged \u2713'; setTimeout(function(){{el.textContent=''}},2000); }}
    if (label) label.value = '';
    if (note)  note.value  = '';
    if (count) count.value = '1';
  }});
}}

function markAnswered(iid, answered) {{
  fetch('/prayer-intention-complete', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'id=' + encodeURIComponent(iid) + '&answered=' + answered
  }}).then(function() {{
    closeModal(); location.reload();
  }});
}}

function submitAddIntention() {{
  var title = document.getElementById('add-title').value.trim();
  var errEl = document.getElementById('add-form-error');
  if (!title) {{
    errEl.textContent = 'Title is required.';
    errEl.style.display = 'block';
    return;
  }}
  errEl.style.display = 'none';
  var btn = document.getElementById('add-submit-btn');
  btn.disabled = true; btn.textContent = 'Saving\u2026';

  var formData = new FormData();
  formData.append('title', title);
  formData.append('description', document.getElementById('add-desc').value);
  var photoInput = document.getElementById('add-photo');
  if (photoInput.files.length > 0) {{
    formData.append('photo', photoInput.files[0]);
  }}

  fetch('/prayer-intention-add', {{
    method: 'POST',
    body: formData
  }}).then(function(r) {{
    // Server redirects — just navigate to intentions page
    try {{ localStorage.removeItem('prayerIntentionDraft'); }} catch(e) {{}}
    window.location.href = '/prayer-intentions';
  }}).catch(function() {{
    btn.disabled = false; btn.textContent = 'Add intention';
    errEl.textContent = 'Error saving — please try again.';
    errEl.style.display = 'block';
  }});
}}
function deleteIntention(iid) {{
  if (!confirm('Remove this intention?')) return;
  fetch('/prayer-intention-delete', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'id=' + encodeURIComponent(iid)
  }}).then(function() {{
    window.location.href = '/prayer-intentions';
  }}).catch(function() {{
    window.location.href = '/prayer-intentions';
  }});
}}

function copyShareLink(path) {{
  var url = window.location.origin + path;
  navigator.clipboard.writeText(url).then(function() {{
    document.querySelectorAll('[id^="share-status-"]').forEach(function(el) {{
      el.textContent = 'Link copied! \u2713 Send to a friend.';
      setTimeout(function(){{el.textContent=''}},3000);
    }});
  }}).catch(function() {{
    prompt('Copy this link:', window.location.origin + path);
  }});
}}
function aiIntentionPrayer(iid, btn) {{
  var result = document.getElementById('ai-prayer-' + iid);
  if (!result) return;
  btn.disabled = true; btn.textContent = '\u2728 Writing\u2026';
  result.style.display = 'block';
  result.textContent   = '\u2728 Asking Claude to write a prayer\u2026';
  fetch('/ai-intention-prayer', {{
    method:'POST', headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'id=' + encodeURIComponent(iid)
  }}).then(function(r){{return r.json();}}).then(function(d){{
    result.innerHTML = d.html || '<p>No response.</p>';
    btn.disabled = false; btn.textContent = '\u2728 Write a prayer';
  }}).catch(function(){{
    result.textContent = 'Error \u2014 check connection.';
    btn.disabled = false;
  }});
}}

// ── Prayer intention draft save/restore ────────────────────────────────────
var _PRAYER_DRAFT_KEY = 'prayerIntentionDraft';
function prayerDraftSave() {{
  try {{
    var draft = {{
      title: document.getElementById('add-title').value || '',
      desc:  document.getElementById('add-desc').value  || '',
      savedAt: Date.now()
    }};
    localStorage.setItem(_PRAYER_DRAFT_KEY, JSON.stringify(draft));
  }} catch(e) {{}}
}}
(function prayerDraftRestore() {{
  try {{
    var raw = localStorage.getItem(_PRAYER_DRAFT_KEY);
    if (!raw) return;
    var draft = JSON.parse(raw);
    if (!draft || !draft.title || (Date.now() - (draft.savedAt||0)) > 86400000) {{ return; }}
    document.getElementById('add-title').value = draft.title;
    document.getElementById('add-desc').value  = draft.desc || '';
    // Auto-open the add form so the draft is visible
    var form = document.getElementById('add-form');
    if (form) {{ form.style.display = 'block'; }}
    // Add a small notice
    var errEl = document.getElementById('add-form-error');
    if (errEl) {{
      errEl.textContent = 'Your draft was restored. Continue where you left off.';
      errEl.style.color = '#166534';
      errEl.style.background = '#f0fdf4';
      errEl.style.padding = '6px 10px';
      errEl.style.borderRadius = '6px';
      errEl.style.display = 'block';
    }}
  }} catch(e) {{}}
}})();
</script>
"""
    return html_page("Prayer Intentions", body)


# ── Dashboard widget ──────────────────────────────────────────────────────────

def render_prayer_dashboard_widget() -> str:
    intentions = load_intentions()
    active     = [i for i in intentions if i.get("active", True) and not i.get("answered")]

    if not active:
        return (
            f'<div class="card" style="margin-bottom:14px;">'
            f'<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;'
            f'text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;'
            f'display:flex;justify-content:space-between;align-items:center;">'
            f'<span>🙏 Prayer Intentions</span>'
            f'<a href="/prayer-intentions" style="font-size:0.9em;color:var(--brown);'
            f'font-weight:600;text-decoration:none;text-transform:none;">Add &rarr;</a></div>'
            f'<p style="font-size:0.82em;color:var(--ink-faint);">No active intentions.</p>'
            f'</div>'
        )

    rows = ""
    for i in active[:4]:
        iid    = escape(i.get("id",""))
        title  = escape(i.get("title",""))
        photo  = i.get("photo","")
        total  = _total_prayers(i.get("prayer_log",[]))
        summary = _prayer_summary(i.get("prayer_log",[]))

        # Tiny photo circle
        photo_circle = ""
        if photo:
            uri = _photo_data_uri(photo)
            if uri:
                photo_circle = (
                    f'<img src="{uri}" '
                    f'style="width:28px;height:28px;border-radius:50%;'
                    f'object-fit:cover;flex-shrink:0;">'
                )
        if not photo_circle:
            photo_circle = (
                f'<div style="width:28px;height:28px;border-radius:50%;'
                f'background:var(--gold-light);display:flex;align-items:center;'
                f'justify-content:center;font-size:0.85em;flex-shrink:0;">🙏</div>'
            )

        # Top prayer type
        top_type = ""
        if summary:
            top_key = max(summary, key=lambda k: summary[k])
            _, icon = PRAYER_TYPE_MAP.get(top_key, ("","✨"))
            top_type = f'<span style="font-size:0.7em;">{icon} {summary[top_key]}</span>'

        total_html = ('<div style="font-size:0.68em;color:var(--ink-faint);">'
                      + str(total) + ' prayers</div>') if total else ''
        rows += (
            '<a href="/prayer-intentions" '
            'style="display:flex;align-items:center;gap:8px;padding:5px 0;'
            'border-bottom:1px solid var(--border-light);text-decoration:none;">'
            + photo_circle
            + '<div style="flex:1;min-width:0;">'
            '<div style="font-size:0.82em;font-weight:600;color:var(--ink);'
            'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + title + '</div>'
            + total_html
            + '</div>'
            + top_type
            + '</a>'
        )

    more = f'<div style="font-size:0.72em;color:var(--ink-faint);margin-top:6px;">' \
           f'+ {len(active)-4} more</div>' if len(active) > 4 else ""

    return (
        f'<div class="card" style="margin-bottom:14px;">'
        f'<div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;'
        f'text-transform:uppercase;color:var(--ink-faint);margin-bottom:8px;'
        f'display:flex;justify-content:space-between;align-items:center;">'
        f'<span>🙏 Prayer Intentions</span>'
        f'<a href="/prayer-intentions" style="font-size:0.9em;color:var(--brown);'
        f'font-weight:600;text-decoration:none;text-transform:none;">'
        f'All {len(active)} &rarr;</a></div>'
        f'{rows}{more}'
        f'</div>'
    )