"""
render_student.py — Student Portal (Phase 1).

A focused, mobile-first school interface for child users (JP, Joseph) that
shows today's school assignments from the curriculum, lets them check off
each item via the existing /toggle-task endpoint, and provides a
Message Mom button.

Task IDs match the format used by build_schedule_payload (in
daily_schedule_engine.py) so check-offs synchronise instantly with the
schedule page and the dashboard:

    make_task_id(child, iso, f"SCHOOL::{subject}::{checklist_item}")

Math subjects emit a 5-item checklist; non-math subjects emit a single
checklist item (the assignment text itself).  The engine
extract_school_tasks_for_child already builds this checklist for us.
"""
from html import escape

from daily_schedule_engine import (
    extract_school_tasks_for_child, generate_day_packet, load_progress,
    make_task_id, get_task_done,
)
from data_helpers import (
    normalize_date_query, gradebook_for_child, school_year_for_date,
    letter_to_gpa,
)
from config import child_color
from ui_helpers import html_page
import auth as _auth

_GRADES_SUBJECTS_ORDER = [
    "Math", "Latin", "Greek", "Religion", "History", "Science",
    "Reading", "Writing", "Grammar", "Literature", "Art", "Music",
    "Logic", "PE", "Other",
]


def _render_messages_from_mom(child: str) -> str:
    """Phase 3: green-bordered 'Messages from Mom' section. Hidden
    entirely (returns '') when there are zero unread messages — D9."""
    try:
        msgs = _auth.load_kid_messages(child.lower())
    except Exception:
        return ""
    unread = [m for m in (msgs or []) if not m.get("read", False)]
    if not unread:
        return ""
    unread.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
    rows = []
    for m in unread:
        from_name = (m.get("from_name") or m.get("from") or "Mom").strip()
        text      = (m.get("text") or "").strip()
        ts        = (m.get("timestamp") or "")[:16].replace("T", " ")
        mid       = (m.get("id") or "").strip()
        rows.append(
            f'<div style="background:white;border:1px solid rgba(46,125,50,0.30);'
            f'border-radius:8px;padding:10px 12px;margin-top:8px;">'
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:baseline;gap:8px;flex-wrap:wrap;">'
            f'<strong style="color:#246b3a;">{escape(from_name)}</strong>'
            f'<span style="font-size:.78rem;color:var(--ink-muted);">{escape(ts)}</span>'
            f'</div>'
            f'<div style="margin-top:4px;white-space:pre-wrap;line-height:1.45;'
            f'color:var(--ink);">{escape(text)}</div>'
            f'<form method="post" action="/student-message-read" '
            f'style="margin-top:8px;text-align:right;">'
            f'<input type="hidden" name="msg_id" value="{escape(mid, quote=True)}"/>'
            f'<input type="hidden" name="kid" value="{escape(child.lower(), quote=True)}"/>'
            f'<button type="submit" style="background:rgba(46,125,50,0.10);'
            f'color:#246b3a;border:1px solid rgba(46,125,50,0.30);'
            f'border-radius:999px;padding:4px 12px;font-size:.78rem;'
            f'font-weight:600;cursor:pointer;">✓ Mark read</button>'
            f'</form></div>'
        )
    return (
        f'<section style="margin-bottom:24px;padding:14px 16px;'
        f'background:rgba(46,125,50,0.06);border:1px solid rgba(46,125,50,0.30);'
        f'border-radius:var(--radius-md);">'
        f'<h2 style="margin:0;font-family:\'Cormorant Garamond\',Georgia,serif;'
        f'font-size:1.3rem;color:#246b3a;">'
        f'💌 Messages from Mom <span style="font-size:.85rem;font-weight:600;'
        f'background:#246b3a;color:white;border-radius:999px;padding:2px 10px;'
        f'margin-left:6px;vertical-align:middle;">{len(unread)}</span></h2>'
        + "".join(rows) + '</section>'
    )


def _recent_school_work(child: str, limit: int = 10) -> list:
    """Read data/grades.json and return the child's most recent entries
    (across all subjects), newest first. Read-only; failures yield []."""
    try:
        from render_subject import load_grades
        grades = load_grades() or {}
    except Exception:
        return []
    by_child = grades.get(child) or {}
    rows = []
    for subject, node in by_child.items():
        for ent in (node or {}).get("entries", []) or []:
            r = dict(ent)
            r.setdefault("subject", subject)
            rows.append(r)
    rows.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    return rows[:max(limit, 0)]


def _letter_grade_local(pct):
    """Lightweight letter mapping for the history chip — duplicates the
    13-point scale from render_subject.letter_grade so we don't add a
    cross-module import for one helper. Returns '—' for None."""
    if not isinstance(pct, (int, float)):
        return "—"
    p = float(pct)
    if p >= 97: return "A+"
    if p >= 93: return "A"
    if p >= 90: return "A-"
    if p >= 87: return "B+"
    if p >= 83: return "B"
    if p >= 80: return "B-"
    if p >= 77: return "C+"
    if p >= 73: return "C"
    if p >= 70: return "C-"
    if p >= 60: return "D"
    return "F"


def _render_school_work_section(child: str) -> str:
    """The 'School Work' history block shown below today's assignments."""
    rows = _recent_school_work(child, limit=10)
    if not rows:
        empty = (
            '<div style="padding:24px 16px;text-align:center;color:var(--ink-muted);'
            'font-style:italic;background:var(--warm-white);border:1px solid var(--border);'
            'border-radius:var(--radius-md);">'
            'No graded work yet — upload your first assignment from a subject page.'
            '</div>'
        )
        return (
            '<section style="margin-top:32px;">'
            '<h2 style="font-family:\'Cormorant Garamond\',Georgia,serif;'
            'font-size:1.5rem;color:var(--ink);margin:0 0 12px 4px;">'
            '📚 Recent School Work</h2>'
            f'{empty}</section>'
        )
    cards = []
    for r in rows:
        subj  = r.get("subject", "")
        title = r.get("lesson") or (r.get("kind") or "entry").title()
        when  = (r.get("created_at") or "")[:10]
        grade = r.get("grade")
        gtxt  = f"{grade:g}" if isinstance(grade, (int, float)) else "—"
        letter = _letter_grade_local(grade)
        feedback = (r.get("feedback") or "").strip()
        strengths = r.get("strengths") or []
        growth = r.get("growth_edges") or []
        rationale = (r.get("grade_rationale") or "").strip()
        badge = "AI" if r.get("ai_assessed") else "manual"
        # Phase 3 (Change 7): when Mom has graded, replace the gold AI
        # chip with a prominent green Mom-graded block. AI grade is
        # demoted to a small subnote so the kid still sees both.
        mom_letter = (r.get("mom_grade_letter") or "").strip()
        mom_pct    = r.get("mom_grade_pct")
        mom_note   = (r.get("mom_grade_note") or "").strip()

        fb_html = ""
        if feedback:
            fb_html = (
                f'<div style="margin-top:6px;font-size:.92rem;line-height:1.45;'
                f'color:var(--ink);white-space:pre-wrap;">{escape(feedback)}</div>'
            )
        chips = ""
        if strengths:
            chips += (
                '<div style="margin-top:8px;font-size:.85rem;">'
                '<span style="font-weight:600;color:#246b3a;">✦ Strengths: </span>'
                + " · ".join(escape(str(s)) for s in strengths)
                + '</div>'
            )
        if growth:
            chips += (
                '<div style="margin-top:4px;font-size:.85rem;">'
                '<span style="font-weight:600;color:#1e3566;">↗ Try next: </span>'
                + " · ".join(escape(str(g)) for g in growth)
                + '</div>'
            )
        if rationale:
            chips += (
                '<div style="margin-top:6px;font-size:.82rem;color:var(--ink-muted);'
                'font-style:italic;">'
                f'Father Gregory: {escape(rationale)}</div>'
            )

        from urllib.parse import urlencode as _ue
        subj_url = "/subject?" + _ue({"child": child, "subject": subj})
        if mom_letter:
            _mom_pct_str = (f"{mom_pct:g}%" if isinstance(mom_pct, (int, float))
                            else "")
            _ai_sub_text = ""
            if gtxt != "—" or letter != "—":
                _ai_sub_text = (
                    f'<div style="font-size:.74rem;color:var(--ink-faint);'
                    f'margin-top:3px;">AI suggested: {escape(letter)}'
                    f'{" · " + escape(gtxt) + "%" if gtxt != "—" else ""}</div>'
                )
            _mom_note_html = (
                f'<div style="margin-top:4px;font-size:.88rem;color:var(--ink);">'
                f'{escape(mom_note)}</div>'
            ) if mom_note else ""
            grade_block_html = (
                f'<div style="background:rgba(46,125,50,0.08);'
                f'border:1px solid rgba(46,125,50,0.30);border-radius:8px;'
                f'padding:8px 12px;margin-top:8px;">'
                f'<div style="font-size:.74rem;font-weight:700;color:#246b3a;'
                f'text-transform:uppercase;letter-spacing:.05em;">'
                f'📓 Mom graded this</div>'
                f'<div style="font-size:1.1rem;font-weight:700;color:#246b3a;'
                f'margin-top:2px;">{escape(mom_letter)}'
                f'{" · " + _mom_pct_str if _mom_pct_str else ""}</div>'
                f'{_mom_note_html}{_ai_sub_text}</div>'
            )
            grade_chip_html = ""
        else:
            grade_block_html = ""
            grade_chip_html = (
                f'<div style="font-weight:700;color:var(--gold);white-space:nowrap;">'
                f'{escape(gtxt)} <span style="font-size:.85rem;color:var(--ink-muted);">'
                f'({escape(letter)})</span></div>'
            )
        cards.append(
            f'<div style="background:var(--warm-white);border:1px solid var(--border);'
            f'border-radius:var(--radius-md);padding:12px 14px;margin-bottom:10px;'
            f'box-shadow:var(--shadow-sm);">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
            f'gap:10px;flex-wrap:wrap;">'
            f'<div style="min-width:0;flex:1;">'
            f'<a href="{escape(subj_url)}" style="font-weight:600;color:var(--ink);'
            f'text-decoration:none;border-bottom:1px dotted var(--gold-mid);">'
            f'{escape(subj)}</a> · '
            f'<span style="color:var(--ink-muted);font-size:.92rem;">{escape(title)}</span>'
            f'</div>'
            f'{grade_chip_html}'
            f'</div>'
            f'<div style="font-size:.78rem;color:var(--ink-muted);margin-top:2px;">'
            f'{escape(when)} · {escape(badge)}</div>'
            f'{grade_block_html}'
            f'{fb_html}{chips}'
            f'</div>'
        )
    return (
        '<section style="margin-top:32px;">'
        '<h2 style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        'font-size:1.5rem;color:var(--ink);margin:0 0 12px 4px;">'
        '📚 Recent School Work</h2>'
        + "".join(cards)
        + '</section>'
    )


_STUDENT_TOGGLE_JS = """
<script>
(function() {
  function handleToggle(cb) {
    var tid = cb.getAttribute('data-tid');
    var iso = cb.getAttribute('data-iso') || '';
    if (!tid) return;
    var done = cb.checked;
    var li = cb.closest('.st-item');
    if (li) {
      li.style.opacity = done ? '0.45' : '1';
      var lbl = li.querySelector('.st-label');
      if (lbl) lbl.style.textDecoration = done ? 'line-through' : 'none';
    }
    fetch('/toggle-task', {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: 'task_id=' + encodeURIComponent(tid) +
            '&new_value=' + encodeURIComponent(done ? 'true' : 'false') +
            '&return_url=' + encodeURIComponent(window.location.pathname +
                                                (iso ? ('?date=' + iso) : ''))
    }).then(function(r) {
      if (!r.ok) {
        cb.checked = !done;
        if (li) {
          li.style.opacity = '1';
          var lbl2 = li.querySelector('.st-label');
          if (lbl2) lbl2.style.textDecoration = 'none';
        }
        alert('Could not save \\u2014 please try again.');
      }
    }).catch(function() {
      cb.checked = !done;
      if (li) {
        li.style.opacity = '1';
        var lbl2 = li.querySelector('.st-label');
        if (lbl2) lbl2.style.textDecoration = 'none';
      }
    });
  }

  function bind() {
    var boxes = document.querySelectorAll('input.st-checkbox[data-tid]');
    for (var i = 0; i < boxes.length; i++) {
      boxes[i].addEventListener('change', function(ev) { handleToggle(ev.target); });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
</script>
"""


def render_student_page(child: str, target_date_str: str = "") -> str:
    """Render the Student Portal page for a child.

    `child` must be the proper-case CHILDREN name ("JP" or "Joseph") — the
    route handler in app.py is responsible for mapping URL slug ->
    CHILDREN entry.

    `target_date_str` is optional; defaults to today (matches the
    /schedule/ route's ?date= contract).
    """
    packet = generate_day_packet(normalize_date_query(target_date_str))
    iso        = packet["iso"]
    weekday    = packet["weekday"]
    date_label = packet["date_label"]

    blocks = extract_school_tasks_for_child(child, weekday, iso) or []
    progress = load_progress()
    color = child_color(child, "bg") or "#1f2937"
    name_safe = escape(child)
    iso_safe  = escape(iso)

    # ── Subject sections ─────────────────────────────────────────────────────
    if blocks:
        sections = []
        for block in blocks:
            subject = block.get("subject", "")
            assignment_text = block.get("assignment_text", "")
            checklist = block.get("checklist") or []
            is_math = bool(block.get("is_math", False))

            items_html = []
            for item in checklist:
                task_text = f"SCHOOL::{subject}::{item}"
                tid = make_task_id(child, iso, task_text)
                done = get_task_done(progress, tid)
                # Use data-* attributes (HTML-escaped, quote=True) instead of
                # interpolating into a JS string literal — safer for task IDs
                # containing apostrophes (e.g. "Alfred's Essentials") and
                # eliminates an injection sink for curriculum-derived text.
                tid_attr = escape(tid, quote=True)
                lbl_style = (
                    "text-decoration:line-through;" if done else ""
                )
                row_op = "0.45" if done else "1"
                items_html.append(
                    f'<label class="st-item" style="display:flex;align-items:flex-start;'
                    f'gap:14px;padding:14px 12px;border-bottom:1px solid var(--border-light);'
                    f'cursor:pointer;opacity:{row_op};">'
                    f'<input type="checkbox" class="st-checkbox" '
                    f'data-tid="{tid_attr}" data-iso="{iso_safe}"'
                    f'{" checked" if done else ""}'
                    f' style="width:24px;height:24px;margin-top:2px;flex-shrink:0;'
                    f'accent-color:{color};cursor:pointer;">'
                    f'<span class="st-label" style="flex:1;font-size:1.02em;line-height:1.4;'
                    f'color:var(--ink);{lbl_style}">{escape(item)}</span>'
                    f'</label>'
                )

            # For non-math subjects, the single checklist item IS the
            # assignment text — no need to repeat it as a separate header.
            # For math, show the lesson text once as a sub-heading above
            # the 5 checklist items (which all reference the same lesson).
            assignment_block = ""
            if is_math and assignment_text:
                assignment_block = (
                    f'<div style="padding:8px 12px 14px;color:var(--ink-muted);'
                    f'font-size:0.95em;font-style:italic;">{escape(assignment_text)}</div>'
                )

            sections.append(
                f'<section style="margin-bottom:24px;background:var(--warm-white);'
                f'border:1px solid var(--border);border-radius:var(--radius-md);'
                f'overflow:hidden;box-shadow:var(--shadow-sm);">'
                f'<h2 style="margin:0;padding:14px 16px;background:var(--gold-light);'
                f'border-bottom:1px solid var(--border);font-family:\'Cormorant Garamond\',Georgia,serif;'
                f'font-size:1.35rem;color:var(--crimson);">{escape(subject)}</h2>'
                f'{assignment_block}'
                f'<div>{"".join(items_html)}</div>'
                f'</section>'
            )
        sections_html = "".join(sections)
    else:
        sections_html = (
            '<div style="padding:48px 20px;text-align:center;color:var(--ink-muted);'
            'font-style:italic;background:var(--warm-white);border:1px solid var(--border);'
            'border-radius:var(--radius-md);">'
            '<div style="font-size:2.5em;margin-bottom:12px;">📭</div>'
            'No school assignments today.'
            '</div>'
        )

    # ── Page body ────────────────────────────────────────────────────────────
    body = f"""
<div style="max-width:680px;margin:0 auto;padding:8px 4px 24px;">

  <!-- Header bar: back arrow + child + date -->
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;
              padding:8px 4px;">
    <a href="/schedule/{escape(child)}"
       aria-label="Back to schedule"
       style="display:inline-flex;align-items:center;justify-content:center;
              width:44px;height:44px;border-radius:50%;background:var(--warm-white);
              border:1px solid var(--border);text-decoration:none;color:var(--ink);
              font-size:1.4em;flex-shrink:0;">
      ←
    </a>
    <div style="flex:1;min-width:0;">
      <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.8rem;
                  font-weight:700;color:{color};line-height:1.1;">
        {name_safe}'s School
      </div>
      <div style="font-size:0.92em;color:var(--ink-muted);margin-top:2px;">
        {escape(date_label)}
      </div>
    </div>
  </div>

  <!-- Messages from Mom (Phase 3): hidden entirely when zero unread -->
  {_render_messages_from_mom(child)}

  <!-- Subject sections -->
  {sections_html}

  <!-- Recent school work (history with AI feedback) -->
  {_render_school_work_section(child)}

  <!-- Message Mom button (uses existing #msg-mom-modal injected by top_nav) -->
  <div style="margin-top:28px;text-align:center;">
    <button type="button"
      onclick="var m=document.getElementById('msg-mom-modal');if(m)m.style.display='flex';"
      style="background:#7c3aed;color:white;border:none;border-radius:24px;
             padding:14px 28px;font-size:1em;font-weight:700;cursor:pointer;
             font-family:inherit;box-shadow:var(--shadow-sm);">
      💌 Message Mom
    </button>
  </div>

</div>
{_STUDENT_TOGGLE_JS}
"""
    return html_page(f"School — {child}", body)


# ─── Phase 4: Read-only gradebook view (/grades/<child>) ──────────────────────

def _gp4_fmt_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        from datetime import date as _d
        return _d.fromisoformat(iso[:10]).strftime("%b %-d, %Y")
    except Exception:
        return iso


def _gp4_pct_to_letter(pct):
    """Reuse the local 13-point scale already defined in this module."""
    return _letter_grade_local(pct)


def _gp4_norm_gb(e: dict) -> dict:
    """Normalize a gradebook.json entry into the unified row schema."""
    pct = e.get("percentage", "")
    try:
        pct_val = float(pct) if pct not in ("", None) else None
    except Exception:
        pct_val = None
    return {
        "date":    e.get("date", "") or "",
        "subject": (e.get("subject") or "Other").strip() or "Other",
        "title":   str(e.get("title") or "").strip() or "(untitled)",
        "letter":  str(e.get("letter") or "").strip(),
        "pct":     pct_val,
        "note":    str(e.get("note") or "").strip(),
        "source":  "mom",
        "ts":      e.get("ts", "") or "",
    }


def _gp4_norm_grades(subject: str, e: dict) -> dict | None:
    """Normalize a grades.json (AI-graded) entry. Returns None if:
      - the entry has been Mom-graded (gradebook copy is canonical, D3), or
      - the entry has no numeric grade yet (ungraded uploads are skipped, D3).
    """
    if e.get("mom_grade_letter"):
        return None
    g = e.get("grade")
    if not isinstance(g, (int, float)):
        return None
    pct_val = float(g)
    fb = (e.get("feedback") or "").strip()
    if len(fb) > 220:
        fb = fb[:217].rstrip() + "…"
    date_iso = (e.get("created_at") or "")[:10]
    return {
        "date":    date_iso,
        "subject": subject,
        "title":   f"Submission {_gp4_fmt_date(date_iso)}".strip(),
        "letter":  _gp4_pct_to_letter(pct_val),
        "pct":     pct_val,
        "note":    fb,
        "source":  "ai",
        "ts":      e.get("created_at", "") or "",
    }


def _gp4_subject_section(subject: str, rows: list, gpa_mode: bool) -> str:
    pcts = [r["pct"] for r in rows if isinstance(r["pct"], (int, float))]
    gpas = []
    if gpa_mode:
        for r in rows:
            g = letter_to_gpa(r["letter"])
            if g is not None:
                gpas.append(g)
    bits = [f"{len(rows)} graded"]
    if pcts:
        bits.append(f"avg {sum(pcts)/len(pcts):.1f}%")
    if gpas:
        bits.append(f"GPA {sum(gpas)/len(gpas):.2f}")
    summary = " · ".join(bits)

    body_rows = []
    for r in rows:
        pct_str = f"{r['pct']:.0f}%" if isinstance(r["pct"], (int, float)) else ""
        if r["source"] == "mom":
            chip = ('<span style="background:rgba(46,125,50,0.10);color:#246b3a;'
                    'border:1px solid rgba(46,125,50,0.30);border-radius:999px;'
                    'padding:2px 8px;font-size:.72rem;font-weight:600;">📓 Mom</span>')
        else:
            chip = ('<span style="background:rgba(124,58,237,0.10);color:#5b3a8a;'
                    'border:1px solid rgba(124,58,237,0.30);border-radius:999px;'
                    'padding:2px 8px;font-size:.72rem;font-weight:600;">🤖 AI</span>')
        body_rows.append(
            f'<tr style="border-top:1px solid #f1f1f1;">'
            f'<td style="padding:8px 6px;color:var(--ink-muted);font-size:.85rem;white-space:nowrap;">{escape(_gp4_fmt_date(r["date"]))}</td>'
            f'<td style="padding:8px 6px;font-weight:600;">{escape(r["title"])}</td>'
            f'<td style="padding:8px 6px;color:var(--ink-muted);font-size:.85rem;white-space:nowrap;">{escape(pct_str)}</td>'
            f'<td style="padding:8px 6px;font-weight:700;white-space:nowrap;">{escape(r["letter"] or "—")}</td>'
            f'<td style="padding:8px 6px;font-size:.85rem;color:var(--ink-muted);">{escape(r["note"])}</td>'
            f'<td style="padding:8px 6px;text-align:right;">{chip}</td>'
            f'</tr>'
        )

    return (
        f'<section style="margin-bottom:20px;background:white;border:1px solid var(--border);'
        f'border-radius:var(--radius-md);padding:14px 16px;">'
        f'<header style="display:flex;justify-content:space-between;align-items:baseline;'
        f'gap:10px;flex-wrap:wrap;margin-bottom:8px;">'
        f'<h3 style="margin:0;font-family:\'Cormorant Garamond\',Georgia,serif;'
        f'font-size:1.15rem;color:var(--ink);">{escape(subject)}</h3>'
        f'<span style="color:var(--ink-muted);font-size:.82rem;">{escape(summary)}</span>'
        f'</header>'
        f'<table style="width:100%;border-collapse:collapse;font-size:.95rem;">'
        f'<thead><tr style="text-align:left;color:var(--ink-muted);font-size:.75rem;'
        f'text-transform:uppercase;letter-spacing:.06em;">'
        f'<th style="padding:6px;font-weight:600;">Date</th>'
        f'<th style="padding:6px;font-weight:600;">Assignment</th>'
        f'<th style="padding:6px;font-weight:600;">%</th>'
        f'<th style="padding:6px;font-weight:600;">Grade</th>'
        f'<th style="padding:6px;font-weight:600;">Note</th>'
        f'<th style="padding:6px;font-weight:600;text-align:right;">By</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        f'</table></section>'
    )


def render_student_grades(child: str) -> str:
    """Phase 4: read-only gradebook for a kid. Merges Lauren's recorded
    grades (data/gradebook.json) with Father Gregory's AI grades
    (data/grades.json), de-duped by analysis_id (D3). Current school
    year only (D6). GPA only for JP (D2)."""
    from datetime import date as _date
    year = school_year_for_date(_date.today().isoformat())
    gpa_mode = (child == "JP")

    # 1. Mom-recorded entries (gradebook.json) — already year-filtered.
    gb_entries = gradebook_for_child(child, school_year=year)
    mom_rows = [_gp4_norm_gb(e) for e in gb_entries]
    mom_analysis_ids = {
        (e.get("source_analysis_id") or "").strip()
        for e in gb_entries
        if (e.get("source_analysis_id") or "").strip()
    }

    # 2. AI-graded entries (grades.json), filtered to current year + de-duped.
    ai_rows = []
    try:
        from render_subject import load_grades
        grades = load_grades() or {}
    except Exception:
        grades = {}
    for subject, node in (grades.get(child) or {}).items():
        for ent in (node or {}).get("entries", []) or []:
            aid = (ent.get("analysis_id") or "").strip()
            if aid and aid in mom_analysis_ids:
                continue  # gradebook covers it (D3)
            row = _gp4_norm_grades(subject, ent)
            if row is None:
                continue
            # Year filter on AI rows
            try:
                if school_year_for_date(row["date"]) != year:
                    continue
            except Exception:
                continue
            ai_rows.append(row)

    all_rows = mom_rows + ai_rows

    # 3. Group by subject (SUBJECTS order, then alphabetical extras)
    by_subj: dict[str, list] = {}
    for r in all_rows:
        by_subj.setdefault(r["subject"], []).append(r)
    for s in by_subj:
        by_subj[s].sort(key=lambda r: (r["date"], r["ts"]), reverse=True)
    ordered = [s for s in _GRADES_SUBJECTS_ORDER if s in by_subj] + \
              sorted([s for s in by_subj if s not in _GRADES_SUBJECTS_ORDER])

    # 4. Overall summary
    all_pcts = [r["pct"] for r in all_rows if isinstance(r["pct"], (int, float))]
    all_gpas = []
    if gpa_mode:
        for r in all_rows:
            g = letter_to_gpa(r["letter"])
            if g is not None:
                all_gpas.append(g)
    overall_bits = [f"{len(all_rows)} entries"]
    if all_pcts:
        overall_bits.append(f"overall {sum(all_pcts)/len(all_pcts):.1f}%")
    if all_gpas:
        overall_bits.append(f"GPA {sum(all_gpas)/len(all_gpas):.2f}")
    overall = " · ".join(overall_bits)
    scale_label = "GPA scale" if gpa_mode else "encouragement marks (no GPA)"

    color = child_color(child)
    sections_html = "".join(
        _gp4_subject_section(s, by_subj[s], gpa_mode) for s in ordered
    )

    if not all_rows:
        sections_html = (
            '<div style="background:white;border:1px solid var(--border);'
            'border-radius:var(--radius-md);padding:24px;text-align:center;'
            'color:var(--ink-muted);">No grades yet — keep up the good work!</div>'
        )

    body = f"""
<div style="max-width:980px;margin:0 auto;padding:18px 16px 80px;">
  <a href="/student/{escape(child.lower())}" style="color:var(--ink-muted);
     text-decoration:none;font-size:14px;">← School</a>
  <h1 style="font-family:'Cormorant Garamond',Georgia,serif;font-size:32px;
             margin:8px 0 4px;color:{escape(color)};">📊 Grades — {escape(child)}</h1>
  <p style="color:var(--ink-muted);font-size:14px;margin:0 0 16px;">{escape(year)} · {escape(scale_label)}</p>
  <div style="color:var(--ink-muted);font-size:13px;margin:10px 0 18px;
              padding:8px 12px;background:rgba(0,0,0,0.025);border-radius:6px;">{escape(overall)}</div>
  {sections_html}
</div>
"""
    return html_page(f"Grades — {child}", body)
