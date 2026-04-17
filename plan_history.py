"""
plan_history.py — Persistent server-side history of Plan Importer analyses.

Every time a plan is analyzed (or a recovered browser session is uploaded),
we append the original paste plus the AI's full structured analysis to
data/plan_import_history.json. This way nothing is ever lost to a closed tab.
"""
from __future__ import annotations
import os, json, uuid
from datetime import datetime
from html import escape as _e

HISTORY_PATH = "data/plan_import_history.json"
MAX_ENTRIES = 200


def _load() -> list:
    try:
        with open(HISTORY_PATH) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(items: list) -> None:
    os.makedirs("data", exist_ok=True)
    tmp = HISTORY_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(items[-MAX_ENTRIES:], f, indent=2)
    os.replace(tmp, HISTORY_PATH)


def append_entry(plan_text: str, analysis, viewer: str = "",
                 source: str = "live") -> dict:
    """Append a new plan-history entry. `analysis` is whatever JSON the AI
    returned. `source` is one of: 'live', 'recovered', 'manual'."""
    if not plan_text and not analysis:
        return {"ok": False, "reason": "empty"}
    items = _load()
    entry = {
        "id": uuid.uuid4().hex[:12],
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "viewer": viewer or "",
        "source": source,
        "plan_text": plan_text or "",
        "analysis": analysis if analysis is not None else None,
    }
    items.append(entry)
    _save(items)
    return {"ok": True, "id": entry["id"], "count": len(items)}


def list_entries() -> list:
    items = _load()
    items.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    return items


def get_entry(entry_id: str) -> dict | None:
    for e in _load():
        if e.get("id") == entry_id:
            return e
    return None


def delete_entry(entry_id: str) -> bool:
    items = _load()
    new_items = [e for e in items if e.get("id") != entry_id]
    if len(new_items) == len(items):
        return False
    _save(new_items)
    return True


# ── Rendering ────────────────────────────────────────────────────────────────

def _short(s: str, n: int = 160) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[:n - 1] + "…"


def _summarize_analysis(a) -> str:
    """One-line summary of an analysis JSON for the index page."""
    if not isinstance(a, dict):
        return ""
    bits = []
    for key, label in (("events", "events"), ("tasks", "tasks"),
                       ("questions", "questions"),
                       ("suggestions", "suggestions")):
        v = a.get(key)
        if isinstance(v, list) and v:
            bits.append(f"{len(v)} {label}")
    summary = a.get("summary") or a.get("overview") or ""
    if isinstance(summary, str) and summary.strip():
        bits.append(_short(summary, 120))
    return " · ".join(bits)


def render_history_index() -> str:
    from ui_helpers import html_page, page_header
    items = list_entries()
    rows = []
    for e in items:
        when = (e.get("created_at") or "")[:19].replace("T", " ")
        rows.append(f"""
<tr>
  <td style="padding:8px;border-top:1px solid var(--border-light);
             font-family:'DM Sans',monospace;font-size:.85rem;white-space:nowrap;">{_e(when)}</td>
  <td style="padding:8px;border-top:1px solid var(--border-light);font-size:.8rem;color:var(--ink-muted);">
    {_e(e.get("source",""))}
  </td>
  <td style="padding:8px;border-top:1px solid var(--border-light);">
    <div style="font-weight:600;">{_e(_short(e.get("plan_text",""), 90))}</div>
    <div style="font-size:.78rem;color:var(--ink-muted);">{_e(_summarize_analysis(e.get("analysis")))}</div>
  </td>
  <td style="padding:8px;border-top:1px solid var(--border-light);text-align:right;white-space:nowrap;">
    <a href="/plan-import-history?id={_e(e['id'])}" style="color:var(--gold);">view</a> ·
    <form method="post" action="/plan-import-history-delete" style="display:inline;"
          onsubmit="return confirm('Delete this saved analysis?');">
      <input type="hidden" name="id" value="{_e(e['id'])}">
      <button type="submit" style="background:none;border:0;color:#b91c1c;cursor:pointer;font-size:.85rem;">delete</button>
    </form>
  </td>
</tr>""")

    body = (
        f'{page_header("Plan Import History", f"{len(items)} saved analyses")}'
        '<p style="margin-bottom:12px;"><a href="/plan-import" style="color:var(--gold);">← Back to Plan Importer</a></p>'
        + (f'<table style="width:100%;border-collapse:collapse;">'
           '<thead><tr style="text-align:left;color:var(--ink-muted);font-size:.78rem;'
           'text-transform:uppercase;letter-spacing:.06em;">'
           '<th style="padding:8px;">When</th><th style="padding:8px;">Source</th>'
           '<th style="padding:8px;">Plan / summary</th><th></th></tr></thead>'
           f'<tbody>{"".join(rows)}</tbody></table>'
           if items else '<p>No saved analyses yet.</p>')
    )
    return html_page("Plan Import History", body)


def render_history_entry(entry_id: str) -> str:
    from ui_helpers import html_page, page_header
    e = get_entry(entry_id)
    if not e:
        return html_page("Plan Import History", "<p>Not found.</p>")
    when = (e.get("created_at") or "").replace("T", " ").rstrip("Z")
    pretty = json.dumps(e.get("analysis"), indent=2, ensure_ascii=False)
    body = f"""
{page_header("Saved Analysis", when + " · " + _e(e.get("source","")))}
<p><a href="/plan-import-history" style="color:var(--gold);">← All saved analyses</a></p>

<section style="background:var(--warm-white);border:1px solid var(--border);
                border-radius:12px;padding:14px;margin:14px 0;">
  <h2 style="margin-bottom:6px;">Original paste</h2>
  <pre style="white-space:pre-wrap;font-family:inherit;font-size:.95rem;
              background:#fcfaf6;border:1px solid var(--border-light);
              border-radius:8px;padding:10px;max-height:400px;overflow:auto;">{_e(e.get("plan_text",""))}</pre>
</section>

<section style="background:var(--warm-white);border:1px solid var(--border);
                border-radius:12px;padding:14px;margin:14px 0;">
  <h2 style="margin-bottom:6px;">AI analysis (full JSON)</h2>
  <pre style="white-space:pre-wrap;font-family:'SF Mono',Menlo,monospace;font-size:.78rem;
              background:#1c1610;color:#f7f3ee;border-radius:8px;padding:10px;
              max-height:600px;overflow:auto;">{_e(pretty)}</pre>
</section>
"""
    return html_page("Saved Analysis", body)
