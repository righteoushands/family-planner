"""
render_subject.py — Per-subject curriculum review pages.

Each child × subject has a page showing every week/day of the curriculum,
a place for the boys to upload tests/work for AI grading, manual grade
entries, plus a small library of reference links and documents.

A summary page shows subjects × averages per kid (semester + year).

Storage:
  data/grades.json    — grades, links, documents
  uploads/grades/<child>/<subject_slug>/<file>   — graded test images
  uploads/grade_docs/<child>/<subject_slug>/<file> — reference documents
"""
from __future__ import annotations
import os, json, re, uuid, time
from html import escape as _e
from urllib.parse import quote, urlencode
from datetime import datetime

from ui_helpers import html_page, page_header
import father_gregory
from data_helpers import add_assignment_analysis
import auth as _auth

GRADES_PATH = "data/grades.json"
UPLOAD_ROOT = "uploads"
GRADE_IMG_DIR = os.path.join(UPLOAD_ROOT, "grades")
GRADE_DOC_DIR = os.path.join(UPLOAD_ROOT, "grade_docs")

CHILDREN = ["JP", "Joseph", "Michael"]
KIND_OPTIONS = ["test", "quiz", "assignment", "project", "exam"]


# ── Storage helpers ───────────────────────────────────────────────────────────

def _ensure_dirs():
    for d in (GRADE_IMG_DIR, GRADE_DOC_DIR, "data"):
        os.makedirs(d, exist_ok=True)


def load_grades() -> dict:
    try:
        with open(GRADES_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save_grades(g: dict) -> None:
    _ensure_dirs()
    tmp = GRADES_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(g, f, indent=2)
    os.replace(tmp, GRADES_PATH)


def _node(g: dict, child: str, subject: str) -> dict:
    g.setdefault(child, {})
    n = g[child].setdefault(subject, {})
    n.setdefault("entries", [])
    n.setdefault("links", [])
    n.setdefault("documents", [])
    return n


def safe_slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("._-")
    return s[:80] or "x"


def _rel_upload(*parts: str) -> str:
    return "/".join(parts)


# ── Music URL detection (for Resources-tab grouping) ─────────────────────────

_MUSIC_HOSTS = frozenset([
    "music.apple.com", "apple.co",
    "open.spotify.com", "spotify.com",
    "music.youtube.com", "soundcloud.com",
    "tidal.com", "pandora.com", "bandcamp.com",
])


def _is_music_url(url: str) -> bool:
    """Return True if the URL host is a known music-platform domain.
    Suffix-match so subdomains (e.g. 'embed.spotify.com') still classify."""
    try:
        from urllib.parse import urlparse as _up
        host = (_up(url).hostname or "").lower()
        if not host:
            return False
        for h in _MUSIC_HOSTS:
            if host == h or host.endswith("." + h):
                return True
    except Exception:
        return False
    return False


# ── Curriculum reading ───────────────────────────────────────────────────────

def _load_curriculum() -> dict:
    try:
        with open("data/curriculum.json") as f:
            return json.load(f)
    except Exception:
        return {}


def subject_weeks(child: str, subject: str) -> list[tuple[int, str]]:
    """Return ordered [(week_num, lesson_text), ...] for the subject."""
    cur = _load_curriculum()
    sub = (cur.get(child) or {}).get(subject, {})
    out = []
    for k, v in sub.items():
        if k.startswith("_"):
            continue
        try:
            n = int(k)
        except (TypeError, ValueError):
            continue
        if isinstance(v, str) and v.strip():
            out.append((n, v.strip()))
        elif isinstance(v, dict):
            # Per-day MODG format — flatten to "Day 1: …\nDay 2: …" for display
            try:
                days = sorted(
                    ((int(dk), str(dv).strip()) for dk, dv in v.items()
                     if str(dk).isdigit()),
                    key=lambda t: t[0],
                )
            except Exception:
                days = []
            if days:
                out.append((n, "\n".join(f"Day {dk}: {dv}" for dk, dv in days if dv)))
    out.sort(key=lambda t: t[0])
    return out


def subject_current_week(child: str, subject: str) -> int:
    cur = _load_curriculum()
    sub = (cur.get(child) or {}).get(subject, {})
    cw = sub.get("_current_week") or cur.get("current_week") or 1
    try:
        return int(cw)
    except Exception:
        return 1


def list_subjects(child: str) -> list[str]:
    cur = _load_curriculum()
    subs = (cur.get(child) or {})
    return [k for k in subs.keys() if not k.startswith("_") and isinstance(subs[k], dict)]


# ── Grade math ───────────────────────────────────────────────────────────────

def _avg(nums: list[float]) -> float | None:
    nums = [n for n in nums if isinstance(n, (int, float))]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 1)


def subject_averages(node: dict) -> dict:
    """Return overall, semester1, semester2 averages from a subject node.

    Semester split is by week of the curriculum: weeks 1–17 = semester 1,
    weeks 18+ = semester 2 (a 34-week MODG default). If an entry has no
    week, it counts toward overall + the semester matching today's week.
    """
    entries = node.get("entries", [])
    overall, sem1, sem2 = [], [], []
    for e in entries:
        g = e.get("grade")
        if not isinstance(g, (int, float)):
            continue
        overall.append(float(g))
        wk = e.get("week")
        if isinstance(wk, int):
            (sem1 if wk <= 17 else sem2).append(float(g))
    return {
        "overall": _avg(overall),
        "semester1": _avg(sem1),
        "semester2": _avg(sem2),
        "count": len(overall),
    }


def letter_grade(pct: float | None) -> str:
    if pct is None:
        return "—"
    if pct >= 93: return "A"
    if pct >= 90: return "A-"
    if pct >= 87: return "B+"
    if pct >= 83: return "B"
    if pct >= 80: return "B-"
    if pct >= 77: return "C+"
    if pct >= 73: return "C"
    if pct >= 70: return "C-"
    if pct >= 67: return "D+"
    if pct >= 60: return "D"
    return "F"


# ── AI grading via Father Gregory (Anthropic) ────────────────────────────────

def ai_grade_image_gregory(image_bytes: bytes, mime: str, child: str,
                           subject: str, lesson: str = "",
                           kind: str = "test") -> dict:
    """Grade a student-uploaded image using the Father Gregory persona
    (Anthropic claude-opus-4-5). Returns:
        {"ok": bool, "grade": float|None, "feedback": str,
         "strengths": list, "growth_edges": list, "grade_rationale": str,
         "parsed": dict (full 16-key Father Gregory output),
         "error": str}
    """
    desc = f"Kind: {kind}"
    if lesson:
        desc += f" · Lesson: {lesson}"
    result = father_gregory.analyze_image(
        image_bytes, mime,
        child_hint=child, subject_hint=subject,
        lesson_hint=lesson, description=desc,
    )
    if not result.get("ok"):
        return {"ok": False, "grade": None, "feedback": "",
                "strengths": [], "growth_edges": [], "grade_rationale": "",
                "parsed": {}, "error": result.get("error", "ai_failed")}
    parsed = result.get("parsed") or {}
    letter = (parsed.get("suggested_grade") or "").strip()
    pct = father_gregory.letter_to_pct(letter)
    return {
        "ok": True,
        "grade": pct,
        "feedback": (parsed.get("gregory_feedback") or "").strip(),
        "strengths": parsed.get("strengths") or [],
        "growth_edges": parsed.get("growth_edges") or [],
        "grade_rationale": (parsed.get("grade_rationale") or "").strip(),
        "parsed": parsed,
        "error": "",
    }


# ── HTML rendering ───────────────────────────────────────────────────────────

def _subj_url(child: str, subject: str) -> str:
    return "/subject?" + urlencode({"child": child, "subject": subject})


def subject_link(child: str, subject: str, label: str = "") -> str:
    """Anchor that other modules can drop in to link a subject name."""
    label = label or subject
    return (f'<a href="{_e(_subj_url(child, subject))}" '
            f'style="color:inherit;text-decoration:none;border-bottom:1px dotted #c9a44a;">'
            f'{_e(label)}</a>')


def render_subject_page(child: str, subject: str, viewer_is_admin: bool = True) -> str:
    """Main per-subject page."""
    if child not in CHILDREN:
        return html_page("Subject", f"<p>Unknown student: {_e(child)}</p>")
    if subject not in list_subjects(child):
        body = (f'<p>No subject called "{_e(subject)}" was found for '
                f'{_e(child)}.</p>'
                f'<p><a href="/curriculum">Back to Curriculum</a></p>')
        return html_page("Subject", body)

    grades = load_grades()
    node = _node(grades, child, subject)
    weeks = subject_weeks(child, subject)
    cur_week = subject_current_week(child, subject)
    avgs = subject_averages(node)

    # Index entries by week
    by_week: dict[int | None, list[dict]] = {}
    for e in node["entries"]:
        by_week.setdefault(e.get("week") if isinstance(e.get("week"), int) else None, []).append(e)

    # ── Header ──
    head = f"""
<div style="margin:8px 0 18px;">
  <div style="font-size:.78rem;color:var(--ink-muted);text-transform:uppercase;letter-spacing:.08em;">
    {_e(child)} · Currently on Week {cur_week}
  </div>
  <h1 style="margin-top:4px;">{_e(subject)}</h1>
  <div style="display:flex;flex-wrap:wrap;gap:14px;margin-top:6px;font-size:.95rem;">
    <span><strong>Overall:</strong> {avgs['overall'] if avgs['overall'] is not None else '—'}
      ({letter_grade(avgs['overall'])})</span>
    <span><strong>Sem 1:</strong> {avgs['semester1'] if avgs['semester1'] is not None else '—'}</span>
    <span><strong>Sem 2:</strong> {avgs['semester2'] if avgs['semester2'] is not None else '—'}</span>
    <span><strong>Graded:</strong> {avgs['count']}</span>
  </div>
  <div style="margin-top:6px;font-size:.85rem;">
    <a href="/grades" style="color:var(--gold);">← Grades summary</a> ·
    <a href="/curriculum" style="color:var(--gold);">Curriculum</a>
  </div>
</div>
"""

    body = head + _render_subject_tabs_html(child, subject, node, weeks, by_week, cur_week, viewer_is_admin)
    return html_page(f"{subject} · {child}", body)


def _entry_card(e: dict, viewer_is_admin: bool) -> str:
    grade = e.get("grade")
    grade_str = f"{grade:g}" if isinstance(grade, (int, float)) else "—"
    letter = letter_grade(grade if isinstance(grade, (int, float)) else None)
    # Phase 3 (D3): when Mom has graded this entry, her grade takes
    # display priority and the AI grade is demoted to a small subnote.
    mom_letter = (e.get("mom_grade_letter") or "").strip()
    mom_pct    = e.get("mom_grade_pct")
    mom_note   = (e.get("mom_grade_note") or "").strip()
    mom_block_html = ""
    if mom_letter:
        _mom_pct_str = (f"{mom_pct:g}%" if isinstance(mom_pct, (int, float))
                        else "")
        _ai_sub = (f"<div style='font-size:.74rem;color:var(--ink-faint);"
                   f"margin-top:3px;'>AI suggested: {_e(letter)}"
                   f"{(' · ' + grade_str + '%') if grade_str != '—' else ''}"
                   f"</div>") if grade_str != "—" or letter != "—" else ""
        _mom_note_html = (f"<div style='margin-top:4px;font-size:.85rem;"
                          f"color:var(--ink);'>{_e(mom_note)}</div>"
                          if mom_note else "")
        mom_block_html = (
            f"<div style='background:rgba(46,125,50,0.08);"
            f"border:1px solid rgba(46,125,50,0.30);border-radius:8px;"
            f"padding:8px 12px;margin-top:8px;'>"
            f"<div style='font-size:.78rem;font-weight:700;color:#246b3a;"
            f"text-transform:uppercase;letter-spacing:.05em;'>"
            f"📓 Mom graded this</div>"
            f"<div style='font-size:1.15rem;font-weight:700;color:#246b3a;"
            f"margin-top:2px;'>{_e(mom_letter)}"
            f"{(' · ' + _mom_pct_str) if _mom_pct_str else ''}</div>"
            f"{_mom_note_html}{_ai_sub}</div>"
        )
    img_html = ""
    if e.get("image_path"):
        img_html = (f'<a href="/{_e(e["image_path"])}" target="_blank">'
                    f'<img src="/{_e(e["image_path"])}" alt="" '
                    f'style="max-width:120px;max-height:120px;border-radius:6px;'
                    f'border:1px solid var(--border);"></a>')
    feedback = (e.get("feedback") or "").strip()
    fb_html = f'<div style="font-size:.88rem;color:var(--ink);margin-top:6px;white-space:pre-wrap;line-height:1.45;">{_e(feedback)}</div>' if feedback else ""

    # Father Gregory extras (chips below feedback). All visible to BOTH
    # child and admin — same gating as the existing feedback paragraph.
    strengths = e.get("strengths") or []
    growth = e.get("growth_edges") or []
    rationale = (e.get("grade_rationale") or "").strip()
    fg_html = ""
    if strengths or growth or rationale:
        bits = []
        if strengths:
            bits.append(
                '<div style="margin-top:6px;font-size:.85rem;">'
                '<span style="font-weight:600;color:#246b3a;">✦ Strengths: </span>'
                + " · ".join(_e(str(s)) for s in strengths)
                + '</div>'
            )
        if growth:
            bits.append(
                '<div style="margin-top:4px;font-size:.85rem;">'
                '<span style="font-weight:600;color:#1e3566;">↗ Try next: </span>'
                + " · ".join(_e(str(g)) for g in growth)
                + '</div>'
            )
        if rationale:
            bits.append(
                '<div style="margin-top:6px;font-size:.82rem;color:var(--ink-muted);'
                'font-style:italic;">'
                f'Father Gregory: {_e(rationale)}</div>'
            )
        fg_html = "".join(bits)

    when = (e.get("created_at") or "")[:10]
    title = e.get("lesson") or e.get("kind", "entry").title()
    badge = "AI" if e.get("ai_assessed") else "manual"

    # Send-to-Mom action: only for AI-assessed entries; toggles to a chip
    # once sent. Cross-link to the analyzer queue is automatic on upload —
    # this button only fires the Message-Mom notification.
    send_html = ""
    if e.get("ai_assessed"):
        if e.get("sent_to_mom_at"):
            send_html = (
                '<span style="display:inline-block;background:rgba(46,125,50,0.10);'
                'color:#246b3a;padding:3px 10px;border-radius:999px;font-size:.78rem;'
                'font-weight:600;border:1px solid rgba(46,125,50,0.25);">'
                '✓ Sent to Mom</span>'
            )
        else:
            send_html = (
                f'<form method="post" action="/subject-send-to-mom" style="display:inline;">'
                f'<input type="hidden" name="child" value="{_e(e.get("child",""))}">'
                f'<input type="hidden" name="subject" value="{_e(e.get("subject",""))}">'
                f'<input type="hidden" name="entry_id" value="{_e(e.get("id",""))}">'
                f'<button type="submit" style="background:#7c3aed;color:white;border:0;'
                f'border-radius:999px;padding:4px 12px;font-size:.78rem;font-weight:600;'
                f'cursor:pointer;">📥 Send to Mom for review</button></form>'
            )

    delete_btn = ""
    if viewer_is_admin:
        delete_btn = (
            f'<form method="post" action="/subject-grade-delete" style="display:inline;">'
            f'<input type="hidden" name="child" value="{_e(e.get("child",""))}">'
            f'<input type="hidden" name="subject" value="{_e(e.get("subject",""))}">'
            f'<input type="hidden" name="id" value="{_e(e.get("id",""))}">'
            f'<button type="submit" style="background:none;border:0;color:#b91c1c;'
            f'cursor:pointer;font-size:.8rem;">delete</button></form>'
        )
    # If Mom has graded, hide the AI grade chip (its info appears inside
    # mom_block_html as the subnote) so the card has one prominent grade.
    grade_chip_html = "" if mom_letter else (
        f'<span style="font-size:1.05rem;font-weight:700;color:var(--gold);">'
        f'{grade_str} <span style="font-size:.8rem;color:var(--ink-muted);">'
        f'({letter})</span></span>'
    )
    return f"""
<div style="display:flex;gap:10px;padding:10px;background:#fcfaf6;
            border:1px solid var(--border-light);border-radius:8px;">
  {img_html}
  <div style="flex:1;min-width:0;">
    <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;">
      <strong>{_e(title)}</strong>
      {grade_chip_html}
    </div>
    <div style="font-size:.78rem;color:var(--ink-muted);">
      {_e(e.get("kind","").title())} · {_e(when)} · {badge} {delete_btn}
    </div>
    {mom_block_html}
    {fb_html}
    {fg_html}
    <div style="margin-top:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
      {send_html}
    </div>
  </div>
</div>"""


# ── Subject-page tabbed sections (Phase 5 redesign) ──────────────────────────

def _render_assignments_tab(child: str, subject: str,
                            weeks: list, cur_week: int) -> str:
    """Curriculum sequence. Each week is a <details> block; the current
    week opens by default. Day segments shown via week_day_segments() when
    present, else the raw curriculum text in a pre-wrap div."""
    from data_helpers import week_day_segments
    if not weeks:
        return (
            '<section style="background:var(--warm-white);border:1px solid var(--border);'
            'border-radius:var(--radius-md);padding:16px;margin-bottom:20px;">'
            '<p style="color:var(--ink-muted);margin:0;">No curriculum entered yet.</p>'
            '</section>'
        )
    blocks = []
    for (w, text) in weeks:
        is_now = (w == cur_week)
        open_attr = " open" if is_now else ""
        suffix = " · current" if is_now else ""
        segments = week_day_segments(text)
        if segments:
            li_html = "".join(
                f'<li style="margin:4px 0;"><strong>Day {d}:</strong> {_e(seg)}</li>'
                for (d, seg) in segments
            )
            body_html = (
                f'<ul style="margin:8px 0 0;padding-left:20px;">{li_html}</ul>'
            )
        else:
            body_html = (
                f'<div style="margin-top:8px;white-space:pre-wrap;">{_e(text)}</div>'
            )
        bg = "#fef9e8" if is_now else "white"
        blocks.append(
            f'<details{open_attr} style="background:{bg};border:1px solid var(--border-light);'
            f'border-radius:8px;padding:10px 14px;margin-bottom:8px;">'
            f'<summary style="cursor:pointer;font-weight:700;font-size:.95rem;">'
            f'Week {w}{suffix}</summary>{body_html}</details>'
        )
    return (
        '<section style="background:var(--warm-white);border:1px solid var(--border);'
        'border-radius:var(--radius-md);padding:16px;margin-bottom:20px;">'
        '<h2 style="margin:0 0 12px;">Curriculum sequence</h2>'
        + "".join(blocks) +
        '</section>'
    )


def _render_resources_tab(child: str, subject: str,
                          node: dict, viewer_is_admin: bool) -> str:
    """Three subsections: Links, Music, Documents. Read-only for kids;
    add forms shown only for admins. Music = links with type=='music'
    (URL-sniffed at write time by add_link)."""
    all_links = node.get("links", []) or []
    music_links = [(i, lk) for i, lk in enumerate(all_links)
                   if (lk.get("type") or "") == "music"]
    plain_links = [(i, lk) for i, lk in enumerate(all_links)
                   if (lk.get("type") or "") != "music"]

    def _link_li(i, lk, music=False):
        delete_btn = ""
        if viewer_is_admin:
            delete_btn = (
                f'<form method="post" action="/subject-link-delete" style="display:inline;">'
                f'<input type="hidden" name="child" value="{_e(child)}">'
                f'<input type="hidden" name="subject" value="{_e(subject)}">'
                f'<input type="hidden" name="idx" value="{i}">'
                f'<button type="submit" style="background:none;border:0;color:#b91c1c;'
                f'cursor:pointer;font-size:.85rem;">remove</button></form>'
            )
        icon = "&#127925; " if music else ""
        return (
            f'<li style="margin:4px 0;">{icon}<a href="{_e(lk.get("url",""))}" target="_blank" '
            f'rel="noopener" style="color:var(--gold);">'
            f'{_e(lk.get("label") or lk.get("url",""))}</a> {delete_btn}</li>'
        )

    plain_html = "".join(_link_li(i, lk) for (i, lk) in plain_links) or \
        '<li style="color:var(--ink-muted);list-style:none;padding:0;">None yet.</li>'
    music_html = "".join(_link_li(i, lk, music=True) for (i, lk) in music_links) or \
        '<li style="color:var(--ink-muted);list-style:none;padding:0;">None yet.</li>'

    docs_html = ""
    for d in node.get("documents", []) or []:
        rel = d.get("path", "")
        delete_btn = ""
        if viewer_is_admin:
            delete_btn = (
                f'<form method="post" action="/subject-doc-delete" style="display:inline;">'
                f'<input type="hidden" name="child" value="{_e(child)}">'
                f'<input type="hidden" name="subject" value="{_e(subject)}">'
                f'<input type="hidden" name="path" value="{_e(rel)}">'
                f'<button type="submit" style="background:none;border:0;color:#b91c1c;'
                f'cursor:pointer;font-size:.85rem;">remove</button></form>'
            )
        docs_html += (
            f'<li style="margin:4px 0;"><a href="/{_e(rel)}" target="_blank" '
            f'style="color:var(--gold);">{_e(d.get("label") or os.path.basename(rel))}</a> '
            f'{delete_btn}</li>'
        )
    if not docs_html:
        docs_html = '<li style="color:var(--ink-muted);list-style:none;padding:0;">None yet.</li>'

    add_link_form = ""
    add_music_form = ""
    add_doc_form = ""
    if viewer_is_admin:
        add_link_form = (
            f'<form method="post" action="/subject-link-add" style="margin-top:8px;display:grid;gap:6px;">'
            f'<input type="hidden" name="child" value="{_e(child)}">'
            f'<input type="hidden" name="subject" value="{_e(subject)}">'
            f'<input type="text" name="label" placeholder="Label (optional)" '
            f'style="padding:6px;border:1px solid var(--border);border-radius:6px;">'
            f'<input type="url" name="url" placeholder="https://..." required '
            f'style="padding:6px;border:1px solid var(--border);border-radius:6px;">'
            f'<button type="submit" style="padding:6px 10px;background:var(--ink);color:#fff;'
            f'border:0;border-radius:6px;cursor:pointer;">Add link</button>'
            f'</form>'
        )
        add_music_form = (
            f'<form method="post" action="/subject-link-add" style="margin-top:8px;display:grid;gap:6px;">'
            f'<input type="hidden" name="child" value="{_e(child)}">'
            f'<input type="hidden" name="subject" value="{_e(subject)}">'
            f'<input type="text" name="label" placeholder="Label (optional)" '
            f'style="padding:6px;border:1px solid var(--border);border-radius:6px;">'
            f'<input type="url" name="url" placeholder="Apple Music / Spotify / YouTube URL" required '
            f'style="padding:6px;border:1px solid var(--border);border-radius:6px;">'
            f'<button type="submit" style="padding:6px 10px;background:var(--ink);color:#fff;'
            f'border:0;border-radius:6px;cursor:pointer;">&#127925; Add music link</button>'
            f'</form>'
        )
        add_doc_form = (
            f'<form method="post" action="/subject-doc-upload" enctype="multipart/form-data" '
            f'style="margin-top:8px;display:grid;gap:6px;">'
            f'<input type="hidden" name="child" value="{_e(child)}">'
            f'<input type="hidden" name="subject" value="{_e(subject)}">'
            f'<input type="text" name="label" placeholder="Label (optional)" '
            f'style="padding:6px;border:1px solid var(--border);border-radius:6px;">'
            f'<input type="file" name="file" required>'
            f'<button type="submit" style="padding:6px 10px;background:var(--ink);color:#fff;'
            f'border:0;border-radius:6px;cursor:pointer;">Upload document</button>'
            f'</form>'
        )

    return (
        '<section style="background:var(--warm-white);border:1px solid var(--border);'
        'border-radius:var(--radius-md);padding:16px;margin-bottom:20px;">'
        '<div style="display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));">'
        '<div>'
        '<h3 style="font-size:1rem;margin:0 0 6px;">Links</h3>'
        f'<ul style="list-style:disc;padding-left:18px;margin:0;">{plain_html}</ul>'
        f'{add_link_form}'
        '</div>'
        '<div>'
        '<h3 style="font-size:1rem;margin:0 0 6px;">&#127925; Music</h3>'
        f'<ul style="list-style:none;padding-left:0;margin:0;">{music_html}</ul>'
        f'{add_music_form}'
        '</div>'
        '<div>'
        '<h3 style="font-size:1rem;margin:0 0 6px;">Documents</h3>'
        f'<ul style="list-style:disc;padding-left:18px;margin:0;">{docs_html}</ul>'
        f'{add_doc_form}'
        '</div>'
        '</div>'
        '</section>'
    )


def _render_grades_tab(child: str, subject: str, by_week: dict,
                       cur_week: int, viewer_is_admin: bool) -> str:
    """Upload form at top, then admin manual-grade form, then per-week
    entry cards. No curriculum text — that's in the Assignments tab."""
    upload_form = f"""
<section style="background:var(--warm-white);border:1px solid var(--border);
                border-radius:var(--radius-md);padding:16px;margin-bottom:20px;">
  <h2 style="margin:0 0 8px;">Upload a test or assignment</h2>
  <p style="font-size:.9rem;color:var(--ink-muted);margin:0 0 10px;">
    Snap a photo of your work. We'll save it and an AI tutor will give you a grade and feedback.
  </p>
  <form method="post" action="/subject-upload-image" enctype="multipart/form-data"
        style="display:grid;gap:10px;">
    <input type="hidden" name="child" value="{_e(child)}">
    <input type="hidden" name="subject" value="{_e(subject)}">
    <div style="display:flex;flex-wrap:wrap;gap:10px;">
      <label style="flex:1;min-width:120px;">
        Week
        <input type="number" name="week" value="{cur_week}" min="1" max="60"
               style="width:100%;padding:6px;border:1px solid var(--border);border-radius:6px;">
      </label>
      <label style="flex:1;min-width:140px;">
        Kind
        <select name="kind" style="width:100%;padding:6px;border:1px solid var(--border);border-radius:6px;">
          {''.join(f'<option value="{k}">{k.title()}</option>' for k in KIND_OPTIONS)}
        </select>
      </label>
      <label style="flex:2;min-width:200px;">
        Lesson / Title
        <input type="text" name="lesson" placeholder="e.g. Lesson 75 chapter test"
               style="width:100%;padding:6px;border:1px solid var(--border);border-radius:6px;">
      </label>
    </div>
    <input type="file" name="file" accept="image/*" capture="environment" required>
    <label style="font-size:.9rem;">
      <input type="checkbox" name="ai_grade" value="1" checked> Ask AI to grade and give feedback
    </label>
    <button type="submit" style="padding:10px 16px;background:var(--gold);color:#fff;
            border:0;border-radius:8px;font-weight:600;cursor:pointer;">
      Upload &amp; Grade
    </button>
  </form>
</section>
"""

    manual_form = ""
    if viewer_is_admin:
        kind_opts = "".join(
            f'<option value="{k}">{k.title()}</option>' for k in KIND_OPTIONS
        )
        manual_form = f"""
<section style="background:var(--warm-white);border:1px solid var(--border);
                border-radius:var(--radius-md);padding:16px;margin-bottom:20px;">
  <h2 style="margin:0 0 8px;">Record a grade by hand</h2>
  <form method="post" action="/subject-grade-add"
        style="display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));">
    <input type="hidden" name="child" value="{_e(child)}">
    <input type="hidden" name="subject" value="{_e(subject)}">
    <label>Week<input type="number" name="week" value="{cur_week}" min="1" max="60"
           style="width:100%;padding:6px;border:1px solid var(--border);border-radius:6px;"></label>
    <label>Kind
      <select name="kind" style="width:100%;padding:6px;border:1px solid var(--border);border-radius:6px;">
        {kind_opts}
      </select>
    </label>
    <label>Title<input type="text" name="lesson" placeholder="Lesson / title"
           style="width:100%;padding:6px;border:1px solid var(--border);border-radius:6px;"></label>
    <label>Grade (0-100)<input type="number" name="grade" min="0" max="100" step="0.1" required
           style="width:100%;padding:6px;border:1px solid var(--border);border-radius:6px;"></label>
    <label style="grid-column:1/-1;">Feedback / notes
      <textarea name="feedback" rows="2"
        style="width:100%;padding:6px;border:1px solid var(--border);border-radius:6px;"></textarea>
    </label>
    <button type="submit" style="grid-column:1/-1;padding:8px 14px;background:var(--ink);color:#fff;
            border:0;border-radius:8px;font-weight:600;cursor:pointer;">Save grade</button>
  </form>
</section>
"""

    week_blocks = []
    int_weeks = sorted([w for w in by_week.keys() if isinstance(w, int)])
    for w in int_weeks:
        ents = sorted(by_week.get(w, []), key=lambda e: e.get("created_at", ""))
        if not ents:
            continue
        is_now = (w == cur_week)
        bg = "#fef9e8" if is_now else "transparent"
        suffix = " · current" if is_now else ""
        cards_html = "".join(_entry_card(e, viewer_is_admin) for e in ents)
        week_blocks.append(
            f'<div style="background:{bg};border-top:1px solid var(--border-light);'
            f'padding:10px 6px;">'
            f'<div style="font-weight:700;margin-bottom:6px;">Week {w}{suffix}</div>'
            f'<div style="display:grid;gap:6px;">{cards_html}</div></div>'
        )

    orphan = by_week.get(None, []) or []
    orphan_html = ""
    if orphan:
        cards_html = "".join(
            _entry_card(e, viewer_is_admin)
            for e in sorted(orphan, key=lambda e: e.get("created_at", ""))
        )
        orphan_html = (
            '<div style="border-top:1px solid var(--border-light);padding:10px 6px;">'
            '<div style="font-weight:700;margin-bottom:6px;">Other graded work</div>'
            f'<div style="display:grid;gap:6px;">{cards_html}</div></div>'
        )

    if not week_blocks and not orphan_html:
        cards_section = (
            '<section style="background:var(--warm-white);border:1px solid var(--border);'
            'border-radius:var(--radius-md);padding:16px;color:var(--ink-muted);text-align:center;">'
            'No graded work yet — upload your first piece above!</section>'
        )
    else:
        cards_section = (
            '<section style="background:var(--warm-white);border:1px solid var(--border);'
            'border-radius:var(--radius-md);padding:16px;margin-bottom:20px;">'
            '<h2 style="margin:0 0 6px;">Submissions &amp; grades</h2>'
            + "".join(week_blocks) + orphan_html +
            '</section>'
        )

    return upload_form + manual_form + cards_section


def _render_subject_tabs_html(child: str, subject: str, node: dict,
                              weeks: list, by_week: dict, cur_week: int,
                              viewer_is_admin: bool) -> str:
    """Wrap the three tab panes in the radio-driven CSS scaffold (D1).

    LAYOUT CONTRACT (do not reorder): the three radio inputs MUST appear
    as older siblings of `.subj-panes` for the `~` general-sibling
    selector to match the right pane."""
    asg_html = _render_assignments_tab(child, subject, weeks, cur_week)
    res_html = _render_resources_tab(child, subject, node, viewer_is_admin)
    gra_html = _render_grades_tab(child, subject, by_week, cur_week, viewer_is_admin)
    style = (
        '<style>'
        '.subj-tab-radio{position:absolute;left:-9999px;}'
        '.subj-tabs{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 16px;}'
        '.subj-tab-label{padding:8px 16px;border:1px solid var(--border);'
        'border-radius:999px;background:white;color:var(--ink-muted);'
        'font-weight:600;font-size:.9rem;cursor:pointer;user-select:none;}'
        '.subj-tab-label:hover{border-color:var(--gold);color:var(--ink);}'
        '.subj-pane{display:none;}'
        '#subj-tab-asg:checked ~ .subj-tabs label[for="subj-tab-asg"],'
        '#subj-tab-res:checked ~ .subj-tabs label[for="subj-tab-res"],'
        '#subj-tab-gra:checked ~ .subj-tabs label[for="subj-tab-gra"]'
        '{background:#fef9e8;border-color:var(--gold);color:var(--ink);}'
        '#subj-tab-asg:checked ~ .subj-panes .subj-pane[data-pane="asg"],'
        '#subj-tab-res:checked ~ .subj-panes .subj-pane[data-pane="res"],'
        '#subj-tab-gra:checked ~ .subj-panes .subj-pane[data-pane="gra"]'
        '{display:block;}'
        '</style>'
    )
    return (
        style +
        '<input type="radio" name="subj-tab" id="subj-tab-asg" class="subj-tab-radio" checked>'
        '<input type="radio" name="subj-tab" id="subj-tab-res" class="subj-tab-radio">'
        '<input type="radio" name="subj-tab" id="subj-tab-gra" class="subj-tab-radio">'
        '<div class="subj-tabs">'
        '<label class="subj-tab-label" for="subj-tab-asg">&#128218; Assignments</label>'
        '<label class="subj-tab-label" for="subj-tab-res">&#128279; Resources</label>'
        '<label class="subj-tab-label" for="subj-tab-gra">&#128211; Grades</label>'
        '</div>'
        '<div class="subj-panes">'
        f'<div class="subj-pane" data-pane="asg">{asg_html}</div>'
        f'<div class="subj-pane" data-pane="res">{res_html}</div>'
        f'<div class="subj-pane" data-pane="gra">{gra_html}</div>'
        '</div>'
    )



def render_grades_summary_page() -> str:
    """Cross-child grades summary."""
    grades = load_grades()
    sections = []
    for child in CHILDREN:
        subjects = list_subjects(child)
        if not subjects:
            continue
        rows = []
        for subj in sorted(subjects):
            node = (grades.get(child) or {}).get(subj) or {"entries": [], "links": [], "documents": []}
            avg = subject_averages(node)
            rows.append(f"""
<tr>
  <td style="padding:6px 8px;border-top:1px solid var(--border-light);">
    {subject_link(child, subj)}
  </td>
  <td style="padding:6px 8px;border-top:1px solid var(--border-light);text-align:center;">
    {avg['semester1'] if avg['semester1'] is not None else '—'}
  </td>
  <td style="padding:6px 8px;border-top:1px solid var(--border-light);text-align:center;">
    {avg['semester2'] if avg['semester2'] is not None else '—'}
  </td>
  <td style="padding:6px 8px;border-top:1px solid var(--border-light);text-align:center;font-weight:700;">
    {avg['overall'] if avg['overall'] is not None else '—'}
  </td>
  <td style="padding:6px 8px;border-top:1px solid var(--border-light);text-align:center;">
    {letter_grade(avg['overall'])}
  </td>
  <td style="padding:6px 8px;border-top:1px solid var(--border-light);text-align:center;color:var(--ink-muted);">
    {avg['count']}
  </td>
</tr>""")

        # Child overall
        all_grades = []
        for subj in subjects:
            node = (grades.get(child) or {}).get(subj) or {}
            for e in node.get("entries", []):
                if isinstance(e.get("grade"), (int, float)):
                    all_grades.append(float(e["grade"]))
        gpa = _avg(all_grades)

        sections.append(f"""
<section style="background:var(--warm-white);border:1px solid var(--border);
                border-radius:var(--radius-md);padding:16px;margin-bottom:18px;">
  <div style="display:flex;justify-content:space-between;align-items:baseline;">
    <h2>{_e(child)}</h2>
    <div style="font-size:.95rem;">
      <strong>Year average:</strong>
      <span style="color:var(--gold);font-weight:700;">{gpa if gpa is not None else '—'}</span>
      ({letter_grade(gpa)})
    </div>
  </div>
  <table style="width:100%;border-collapse:collapse;margin-top:8px;font-size:.95rem;">
    <thead>
      <tr style="text-align:left;color:var(--ink-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.06em;">
        <th style="padding:6px 8px;">Subject</th>
        <th style="padding:6px 8px;text-align:center;">Sem 1</th>
        <th style="padding:6px 8px;text-align:center;">Sem 2</th>
        <th style="padding:6px 8px;text-align:center;">Overall</th>
        <th style="padding:6px 8px;text-align:center;">Letter</th>
        <th style="padding:6px 8px;text-align:center;"># Grades</th>
      </tr>
    </thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</section>""")

    body = (f'{page_header("Grades Summary", "All students · all subjects")}'
            + (''.join(sections) or "<p>No subjects in the curriculum yet.</p>"))
    return html_page("Grades Summary", body)


# ── POST helpers (called from app.py) ────────────────────────────────────────

def add_image_entry(child: str, subject: str, week: int | None, kind: str,
                    lesson: str, image_bytes: bytes, mime: str,
                    original_name: str, do_ai: bool = True) -> dict:
    """Save uploaded image, optionally call AI for a grade, append entry."""
    _ensure_dirs()
    if subject not in list_subjects(child):
        return {"ok": False, "error": "unknown_subject"}

    sub_dir = os.path.join(GRADE_IMG_DIR, safe_slug(child), safe_slug(subject))
    os.makedirs(sub_dir, exist_ok=True)

    ext = os.path.splitext(original_name or "")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"):
        # Guess from mime
        ext = {"image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
               "image/heic": ".heic"}.get(mime, ".jpg")

    eid = uuid.uuid4().hex[:12]
    fname = f"{int(time.time())}_{eid}{ext}"
    abs_path = os.path.join(sub_dir, fname)
    with open(abs_path, "wb") as f:
        f.write(image_bytes)
    rel_path = abs_path.replace(os.sep, "/")

    grade = None
    feedback = ""
    strengths: list = []
    growth_edges: list = []
    grade_rationale = ""
    parsed_full: dict = {}
    ai_assessed = False
    err = ""
    if do_ai:
        result = ai_grade_image_gregory(image_bytes, mime, child, subject,
                                         lesson, kind)
        if result["ok"]:
            grade = result["grade"]
            feedback = result["feedback"]
            strengths = result.get("strengths") or []
            growth_edges = result.get("growth_edges") or []
            grade_rationale = result.get("grade_rationale") or ""
            parsed_full = result.get("parsed") or {}
            ai_assessed = True
        else:
            err = result["error"]

    # Auto cross-link to Lauren's /assignment-analyzer queue (D2: cross-link
    # auto, notification manual). Failures here must never break the upload.
    analysis_id = ""
    if ai_assessed:
        try:
            analysis_record = add_assignment_analysis({
                "source_kind":     "student_upload",
                "source_filename": original_name or "",
                "source_mime":     mime or "",
                "upload_path":     rel_path,
                "upload_paths":    [{"path": rel_path, "kind": "image",
                                      "mime": mime or "",
                                      "filename": original_name or ""}],
                "child_hint":      child,
                "subject_hint":    subject,
                "raw_text":        "",
                "description":     f"Kind: {kind}" + (f" · Lesson: {lesson}"
                                                       if lesson else ""),
                "parsed":          parsed_full,
                "status":          "pending_review",
            })
            analysis_id = (analysis_record or {}).get("id", "")
        except Exception as _xlink_err:
            err = (err + " | " if err else "") + f"cross_link_failed: {_xlink_err}"[:200]

    entry = {
        "id": eid,
        "child": child,
        "subject": subject,
        "week": int(week) if isinstance(week, int) or (isinstance(week, str) and week.isdigit()) else None,
        "kind": kind or "test",
        "lesson": lesson or "",
        "grade": grade,
        "feedback": feedback,
        "strengths": strengths,
        "growth_edges": growth_edges,
        "grade_rationale": grade_rationale,
        "image_path": rel_path,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "ai_assessed": ai_assessed,
        "analysis_id": analysis_id,
        "sent_to_mom_at": "",
    }
    g = load_grades()
    _node(g, child, subject)["entries"].append(entry)
    save_grades(g)
    return {"ok": True, "entry": entry, "ai_error": err,
            "analysis_id": analysis_id}


def mark_entry_sent_to_mom(child: str, subject: str, entry_id: str) -> dict:
    """Stamp the entry as 'sent to Mom' and post a Message-Mom inbox note.
    Idempotent: a second call returns ok with already_sent=True and does not
    re-notify."""
    g = load_grades()
    n = _node(g, child, subject)
    target = None
    for e in n["entries"]:
        if e.get("id") == entry_id:
            target = e
            break
    if target is None:
        return {"ok": False, "error": "not_found"}
    if target.get("sent_to_mom_at"):
        return {"ok": True, "already_sent": True,
                "sent_at": target["sent_to_mom_at"]}
    target["sent_to_mom_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    save_grades(g)
    msg_err = ""
    try:
        lesson_bit = f" ({target.get('lesson')})" if target.get("lesson") else ""
        _auth.save_message(
            (child or "").lower(),
            f"📥 Submitted {subject}{lesson_bit} for Father Gregory's review — "
            f"see /assignment-analyzer"
        )
    except Exception as e:
        msg_err = str(e)[:200]
    return {"ok": True, "already_sent": False,
            "sent_at": target["sent_to_mom_at"],
            "msg_error": msg_err}


def apply_mom_grade(child: str, subject: str, analysis_id: str,
                    upload_path: str, pct, letter: str, note: str) -> dict:
    """Phase 3: stamp Mom's recorded grade onto the matching grades.json
    entry without overwriting the AI grade. Match by analysis_id (primary,
    Phase 2 entries) then by image_path == upload_path (fallback).
    Returns {ok, matched_id} or {ok=False, error='no_match'}."""
    g = load_grades()
    n = _node(g, child or "", subject or "")
    target = None
    if analysis_id:
        for e in n.get("entries", []) or []:
            if e.get("analysis_id") == analysis_id:
                target = e; break
    if target is None and upload_path:
        for e in n.get("entries", []) or []:
            if e.get("image_path") == upload_path:
                target = e; break
    if target is None:
        return {"ok": False, "error": "no_match"}
    try:    pct_val = float(pct) if pct not in ("", None) else None
    except Exception: pct_val = None
    target["mom_grade_pct"]    = pct_val
    target["mom_grade_letter"] = (letter or "").strip()
    target["mom_grade_note"]   = (note or "").strip()
    target["mom_graded_at"]    = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    save_grades(g)
    return {"ok": True, "matched_id": target.get("id", "")}


def add_manual_entry(child: str, subject: str, week, kind: str,
                     lesson: str, grade: float, feedback: str) -> dict:
    if subject not in list_subjects(child):
        return {"ok": False, "error": "unknown_subject"}
    try:
        wk = int(week) if str(week).strip() else None
    except Exception:
        wk = None
    try:
        g_val = float(grade)
        g_val = max(0.0, min(100.0, g_val))
    except Exception:
        return {"ok": False, "error": "bad_grade"}
    entry = {
        "id": uuid.uuid4().hex[:12],
        "child": child, "subject": subject, "week": wk,
        "kind": kind or "assignment", "lesson": lesson or "",
        "grade": g_val, "feedback": feedback or "",
        "image_path": "", "ai_assessed": False,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    g = load_grades()
    _node(g, child, subject)["entries"].append(entry)
    save_grades(g)
    return {"ok": True, "entry": entry}


def delete_entry(child: str, subject: str, entry_id: str) -> bool:
    g = load_grades()
    n = _node(g, child, subject)
    before = len(n["entries"])
    n["entries"] = [e for e in n["entries"] if e.get("id") != entry_id]
    if len(n["entries"]) != before:
        save_grades(g)
        return True
    return False


def add_link(child: str, subject: str, label: str, url: str) -> bool:
    url_clean = url.strip()
    if not url_clean:
        return False
    # URL scheme allowlist — block javascript:, data:, file:, etc.
    lower = url_clean.lower()
    if not (lower.startswith("https://") or lower.startswith("http://")
            or lower.startswith("music://")):
        return False
    if subject not in list_subjects(child):
        return False
    g = load_grades()
    rec = {
        "label": label.strip(), "url": url_clean,
        "added_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    if _is_music_url(url_clean):
        rec["type"] = "music"
    _node(g, child, subject)["links"].append(rec)
    save_grades(g)
    return True


def delete_link(child: str, subject: str, idx: int) -> bool:
    g = load_grades()
    n = _node(g, child, subject)
    if 0 <= idx < len(n["links"]):
        n["links"].pop(idx)
        save_grades(g)
        return True
    return False


def add_document(child: str, subject: str, label: str,
                 file_bytes: bytes, original_name: str) -> dict:
    if subject not in list_subjects(child):
        return {"ok": False, "error": "unknown_subject"}
    if not file_bytes:
        return {"ok": False, "error": "no_file"}
    _ensure_dirs()
    sub_dir = os.path.join(GRADE_DOC_DIR, safe_slug(child), safe_slug(subject))
    os.makedirs(sub_dir, exist_ok=True)
    fname = f"{int(time.time())}_{safe_slug(original_name or 'file')}"
    abs_path = os.path.join(sub_dir, fname)
    with open(abs_path, "wb") as f:
        f.write(file_bytes)
    rel_path = abs_path.replace(os.sep, "/")
    g = load_grades()
    _node(g, child, subject)["documents"].append({
        "label": label.strip(), "path": rel_path,
        "added_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    })
    save_grades(g)
    return {"ok": True, "path": rel_path}


def delete_document(child: str, subject: str, rel_path: str) -> bool:
    g = load_grades()
    n = _node(g, child, subject)
    found = False
    new_docs = []
    for d in n["documents"]:
        if d.get("path") == rel_path:
            found = True
            try:
                if os.path.exists(rel_path) and rel_path.startswith(GRADE_DOC_DIR):
                    os.remove(rel_path)
            except Exception:
                pass
        else:
            new_docs.append(d)
    if found:
        n["documents"] = new_docs
        save_grades(g)
    return found
