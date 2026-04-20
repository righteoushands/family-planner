"""
render_assignment_analyzer.py — AI Assignment Analyzer

A page where Lauren can upload a photo or paste text of an assignment, get an
AI analysis (subject, child, type, instructions, sub-items, time estimate,
etc.), and stash the result for later placement into the curriculum.

The actual analysis work and storage live in app.py (POST /assignment-analyze).
This file only renders the UI.
"""
from html import escape as _esc
from urllib.parse import quote as _q
from data_helpers import load_assignment_analyses
from ui_helpers import html_page

CHILDREN = ["JP", "Joseph", "Michael"]
SUBJECTS = [
    "Math", "Latin", "Greek", "Religion", "History", "Science",
    "Reading", "Writing", "Grammar", "Literature", "Art", "Music",
    "Logic", "PE", "Other",
]


def _fmt_ts(ts: str) -> str:
    """'2026-04-20T10:45:30' -> 'Apr 20, 10:45 AM'."""
    if not ts:
        return ""
    try:
        from datetime import datetime as _dt
        d = _dt.fromisoformat(ts)
        return d.strftime("%b %-d, %-I:%M %p")
    except Exception:
        return ts


def _resolved(rec: dict, key: str, default=""):
    """Prefer Mom's edited value over the AI-parsed value."""
    edits = rec.get("user_edits", {}) or {}
    if key in edits and edits[key] not in (None, ""):
        return edits[key]
    parsed = rec.get("parsed", {}) or {}
    return parsed.get(key, default)


def _record_grade_block(rid: str, child: str, subject: str, title: str,
                        suggested_grade: str, recorded_id: str,
                        recorded_pct, recorded_letter: str) -> str:
    """Footer block — either '✓ Recorded' chip or the inline 'Record grade' form."""
    from datetime import date as _date
    from data_helpers import GRADE_LETTERS
    if recorded_id:
        chip_bits = ["✓ Recorded"]
        if recorded_pct not in ("", None):
            try: chip_bits.append(f"{float(recorded_pct):.0f}%")
            except Exception: pass
        if recorded_letter:
            chip_bits.append(_esc(str(recorded_letter)))
        chip = " · ".join(chip_bits)
        return (
            f'<a class="aa-status aa-status-recorded" '
            f'href="/gradebook?child={_q(str(child) or "JP")}">{chip}</a>'
        )

    # Otherwise: inline record-grade form (collapsed by default)
    today = _date.today().isoformat()
    letter_opts = "".join(
        f'<option value="{_esc(l)}"{" selected" if l == suggested_grade else ""}>{_esc(l)}</option>'
        for l in [""] + GRADE_LETTERS
    )
    return f"""
      <span class="aa-status">⏳ Pending grade</span>
      <button type="button" class="aa-record-toggle" data-id="{_esc(rid)}">📓 Record grade</button>
      <form class="aa-record-form" data-id="{_esc(rid)}" style="display:none;">
        <input type="hidden" name="source_analysis_id" value="{_esc(rid)}"/>
        <input type="hidden" name="child" value="{_esc(str(child) or "JP")}"/>
        <input type="hidden" name="subject" value="{_esc(str(subject) or "Other")}"/>
        <input type="hidden" name="title" value="{_esc(str(title))}"/>
        <input type="date" name="date" value="{today}"/>
        <input type="text" name="raw_score" placeholder="Score" inputmode="decimal" class="aa-rec-num"/>
        <span class="aa-rec-sep">/</span>
        <input type="text" name="total" placeholder="Total" inputmode="decimal" class="aa-rec-num"/>
        <select name="letter" title="Letter grade (auto-filled)">{letter_opts}</select>
        <input type="text" name="note" placeholder="Note (optional)" class="aa-rec-note"/>
        <button type="submit" class="aa-rec-save">Save</button>
        <button type="button" class="aa-rec-cancel">Cancel</button>
      </form>
    """


def _render_one_card(rec: dict) -> str:
    rid = rec.get("id", "")
    parsed = rec.get("parsed", {}) or {}
    err = parsed.get("error", "")
    ts_label = _fmt_ts(rec.get("ts", ""))
    src_kind = rec.get("source_kind", "text")
    src_name = rec.get("source_filename", "")
    upload_path = rec.get("upload_path", "")
    upload_paths = rec.get("upload_paths") or []
    # Back-compat: synthesize a single-item list for older records
    if not upload_paths and upload_path:
        upload_paths = [{"path": upload_path, "kind": src_kind,
                         "mime": rec.get("source_mime",""), "filename": src_name}]

    title = _resolved(rec, "title", "(untitled assignment)")
    subject = _resolved(rec, "subject", "")
    child_guess = _resolved(rec, "child_guess", "")
    atype = _resolved(rec, "assignment_type", "")
    minutes = _resolved(rec, "estimated_minutes", "")
    due_hint = _resolved(rec, "due_date_hint", "")
    summary = _resolved(rec, "instructions_summary", "")
    sub_items = _resolved(rec, "sub_items", []) or []
    materials = _resolved(rec, "materials_needed", []) or []
    notes = _resolved(rec, "notes_for_mom", "")
    gregory_feedback = _resolved(rec, "gregory_feedback", "")
    strengths = _resolved(rec, "strengths", []) or []
    growth_edges = _resolved(rec, "growth_edges", []) or []
    work_present = _resolved(rec, "work_present", False)
    suggested_grade = _resolved(rec, "suggested_grade", "")
    grade_rationale = _resolved(rec, "grade_rationale", "")
    # Has this card already been recorded in the gradebook?
    edits = rec.get("user_edits", {}) or {}
    recorded_id     = edits.get("_gradebook_id", "")
    recorded_pct    = edits.get("_gradebook_pct", "")
    recorded_letter = edits.get("_gradebook_letter", "")

    if not isinstance(sub_items, list):
        sub_items = [str(sub_items)]
    if not isinstance(materials, list):
        materials = [str(materials)]
    if not isinstance(strengths, list):
        strengths = [str(strengths)] if strengths else []
    if not isinstance(growth_edges, list):
        growth_edges = [str(growth_edges)] if growth_edges else []

    thumb_html = ""
    if upload_paths:
        _thumbs = []
        for _i, _u in enumerate(upload_paths):
            _ukind = _u.get("kind","")
            _ufn   = _u.get("filename","") or ("file %d" % (_i+1))
            _img_url = f"/assignment-image?id={_q(rid)}&n={_i}"
            if _ukind == "image":
                _thumbs.append(
                    f'<a href="{_img_url}" target="_blank" class="aa-thumb-link" title="{_esc(_ufn)}">'
                    f'<img src="{_img_url}" alt="{_esc(_ufn)}" class="aa-thumb"/></a>'
                )
            elif _ukind == "pdf":
                _thumbs.append(
                    f'<a href="{_img_url}" target="_blank" class="aa-thumb-link" title="Open {_esc(_ufn)}">'
                    f'<div class="aa-thumb aa-thumb-pdf">📄<br/><small>{_esc(_ufn)}</small></div></a>'
                )
            else:
                _thumbs.append(
                    f'<div class="aa-thumb aa-thumb-text">📎<br/><small>{_esc(_ufn)}</small></div>'
                )
        thumb_html = '<div class="aa-thumbs">' + "".join(_thumbs) + '</div>'
    else:
        thumb_html = '<div class="aa-thumb aa-thumb-text">📝<br/><small>Pasted text</small></div>'

    sub_html = ""
    if sub_items:
        lis = "".join(f"<li>{_esc(str(s))}</li>" for s in sub_items[:30])
        sub_html = f'<div class="aa-section"><h4>Sub-items ({len(sub_items)})</h4><ul>{lis}</ul></div>'

    mat_html = ""
    if materials:
        mat_html = (
            '<div class="aa-section"><h4>Materials</h4>'
            + ", ".join(_esc(str(m)) for m in materials)
            + "</div>"
        )

    notes_html = (
        f'<div class="aa-section aa-notes"><h4>Notes</h4>{_esc(str(notes))}</div>'
        if notes else ""
    )

    # Father Gregory's review (only shown if AI returned feedback)
    gregory_html = ""
    grade_html = ""
    if suggested_grade or grade_rationale:
        _g = _esc(str(suggested_grade)) if suggested_grade else "—"
        _gr = _esc(str(grade_rationale)) if grade_rationale else ""
        grade_html = (
            '<div class="aa-fg-grade">'
            f'<div class="aa-fg-grade-mark">{_g}</div>'
            f'<div class="aa-fg-grade-why"><div class="aa-fg-label">Suggested grade</div>'
            f'<div class="aa-fg-grade-text">{_gr}</div></div>'
            '</div>'
        )
    if gregory_feedback or strengths or growth_edges or grade_html:
        _strength_html = ""
        if strengths:
            _strength_html = (
                '<div class="aa-fg-block"><div class="aa-fg-label">✦ Strengths</div><ul>'
                + "".join(f'<li>{_esc(str(s))}</li>' for s in strengths)
                + '</ul></div>'
            )
        _growth_html = ""
        if growth_edges:
            _growth_html = (
                '<div class="aa-fg-block"><div class="aa-fg-label">↗ Where to grow</div><ul>'
                + "".join(f'<li>{_esc(str(g))}</li>' for g in growth_edges)
                + '</ul></div>'
            )
        _quote_html = (
            f'<blockquote class="aa-fg-quote">{_esc(str(gregory_feedback))}</blockquote>'
            if gregory_feedback else ""
        )
        gregory_html = (
            '<div class="aa-section aa-fg">'
            '<h4>🎓 Father Gregory&rsquo;s review</h4>'
            f'{grade_html}{_quote_html}{_strength_html}{_growth_html}'
            '</div>'
        )

    err_html = (
        f'<div class="aa-error">⚠️ AI analysis failed: {_esc(err)}</div>'
        if err else ""
    )

    children_opts = "".join(
        f'<option value="{_esc(c)}"{" selected" if str(child_guess) == c else ""}>{_esc(c)}</option>'
        for c in [""] + CHILDREN
    )
    subj_opts = "".join(
        f'<option value="{_esc(s)}"{" selected" if str(subject).lower() == s.lower() else ""}>{_esc(s)}</option>'
        for s in [""] + SUBJECTS
    )

    return f"""
    <article class="aa-card" data-id="{_esc(rid)}">
      <header class="aa-card-head">
        <div class="aa-card-thumbwrap">{thumb_html}</div>
        <div class="aa-card-titlebox">
          <input class="aa-title-input" data-field="title" value="{_esc(str(title))}" placeholder="Assignment title"/>
          <div class="aa-meta">{_esc(ts_label)} · {_esc(src_kind)}{' · ' + _esc(src_name) if src_name else ''}</div>
        </div>
        <button class="aa-delete" data-id="{_esc(rid)}" title="Delete">✕</button>
      </header>
      {err_html}
      <div class="aa-grid">
        <label>Subject
          <select class="aa-field" data-field="subject">{subj_opts}</select>
        </label>
        <label>Child
          <select class="aa-field" data-field="child_guess">{children_opts}</select>
        </label>
        <label>Type
          <input class="aa-field" data-field="assignment_type" value="{_esc(str(atype))}" placeholder="worksheet, test, reading…"/>
        </label>
        <label>Est. min
          <input class="aa-field" data-field="estimated_minutes" value="{_esc(str(minutes))}" placeholder="30" inputmode="numeric"/>
        </label>
        <label class="aa-span2">Due
          <input class="aa-field" data-field="due_date_hint" value="{_esc(str(due_hint))}" placeholder="today / Friday / 2026-05-01"/>
        </label>
      </div>
      <div class="aa-section"><h4>Summary</h4><div class="aa-summary">{_esc(str(summary))}</div></div>
      {gregory_html}
      {sub_html}
      {mat_html}
      {notes_html}
      <div class="aa-card-foot">
        {_record_grade_block(rid, child_guess, subject, title, suggested_grade, recorded_id, recorded_pct, recorded_letter)}
        <span class="aa-saved" data-id="{_esc(rid)}"></span>
      </div>
    </article>
    """


def render_assignment_analyzer_page() -> str:
    items = load_assignment_analyses()
    cards = "\n".join(_render_one_card(r) for r in items) if items else \
        '<p class="aa-empty">No analyses yet. Upload your first assignment above.</p>'

    children_opts = "".join(f'<option value="{_esc(c)}">{_esc(c)}</option>' for c in [""] + CHILDREN)
    subject_opts = "".join(f'<option value="{_esc(s)}">{_esc(s)}</option>' for s in [""] + SUBJECTS)

    body = f"""
    <div class="aa-wrap">
      <div class="aa-topnav">
        <a href="/curriculum" class="aa-back">← Curriculum</a>
        <a href="/gradebook" class="aa-back aa-back-gradebook">📓 Gradebook →</a>
      </div>
      <h1 class="aa-h1">📥 Assignment Analyzer</h1>
      <p class="aa-sub">Upload a photo or paste text. The AI will identify the
        subject, child, type, sub-tasks, and estimated time, and save it to a
        review queue. (Curriculum auto-placement coming soon — for now items
        wait here for you to slot in by hand.)</p>

      <form id="aa-form" class="aa-form" enctype="multipart/form-data">
        <div class="aa-row">
          <label class="aa-file-label">
            <span class="aa-file-btn">📷 Choose photo(s) or PDF(s)</span>
            <input type="file" name="file" id="aa-file" multiple accept="image/*,application/pdf,.pdf,.jpg,.jpeg,.png,.webp,.heic"/>
            <span id="aa-file-name" class="aa-file-name">No files chosen — you can pick more than one</span>
          </label>
        </div>
        <div class="aa-or">— or —</div>
        <div class="aa-row">
          <textarea name="raw_text" id="aa-text" rows="6"
            placeholder="Paste assignment text here (instructions, problems, reading list, etc.)"></textarea>
        </div>
        <div class="aa-row">
          <label class="aa-desc-label">
            <span class="aa-desc-title">📝 What was the assignment? <span class="aa-desc-opt">(optional but helps Father Gregory grade fairly)</span></span>
            <textarea name="description" id="aa-description" rows="3"
              placeholder="e.g. &quot;Write a one-page narration of the origins of the Greek gods, in your own words, with at least 3 named gods.&quot;"></textarea>
          </label>
        </div>
        <div class="aa-row aa-hints">
          <label>Child hint (optional)
            <select name="child_hint" id="aa-child">{children_opts}</select>
          </label>
          <label>Subject hint (optional)
            <select name="subject_hint" id="aa-subject">{subject_opts}</select>
          </label>
        </div>
        <div class="aa-row aa-actions">
          <button type="submit" id="aa-submit" class="aa-submit">✨ Analyze</button>
          <span id="aa-status" class="aa-status-msg"></span>
        </div>
      </form>

      <div class="aa-list">
        <h2 class="aa-h2">Analyzed assignments <span class="aa-count">({len(items)})</span></h2>
        {cards}
      </div>
    </div>

    <style>
      .aa-wrap {{ max-width: 880px; margin: 0 auto; padding: 18px 16px 80px; color: var(--ink); font-family: 'DM Sans', system-ui, sans-serif; }}
      .aa-topnav {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }}
      .aa-back {{ color: var(--ink-muted); text-decoration: none; font-size: 14px; padding: 8px 4px; display: inline-block; }}
      .aa-back:hover {{ color: var(--gold); }}
      .aa-back-gradebook {{ background: #ecfccb; border: 1.5px solid #84cc16; color: #3f6212; padding: 8px 14px; border-radius: 999px; font-weight: 600; }}
      .aa-back-gradebook:hover {{ background: #d9f99d; color: #3f6212; }}
      .aa-h1 {{ font-family: 'Cormorant Garamond', serif; font-size: 32px; margin: 8px 0 4px; color: var(--ink); }}
      .aa-h2 {{ font-family: 'Cormorant Garamond', serif; font-size: 22px; margin: 28px 0 12px; color: var(--ink); border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
      .aa-count {{ color: var(--ink-faint); font-size: 16px; font-weight: 400; }}
      .aa-sub {{ color: var(--ink-muted); font-size: 14px; line-height: 1.45; margin: 0 0 18px; }}
      .aa-form {{ background: var(--warm-white); border: 1px solid var(--border); border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(28,22,16,0.04); }}
      .aa-row {{ margin-bottom: 12px; }}
      .aa-row:last-child {{ margin-bottom: 0; }}
      .aa-or {{ text-align: center; color: var(--ink-faint); font-size: 12px; margin: 8px 0; letter-spacing: 0.1em; }}
      .aa-file-label {{ display: flex; align-items: center; gap: 12px; cursor: pointer; }}
      .aa-file-label input[type="file"] {{ display: none; }}
      .aa-file-btn {{ display: inline-block; background: var(--gold-light); color: var(--ink); border: 1px solid var(--gold-mid); border-radius: 8px; padding: 10px 14px; font-weight: 500; font-size: 14px; }}
      .aa-file-btn:hover {{ background: var(--gold-mid); color: white; }}
      .aa-file-name {{ color: var(--ink-muted); font-size: 13px; }}
      #aa-text, #aa-description {{ width: 100%; box-sizing: border-box; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; font-family: inherit; font-size: 14px; resize: vertical; background: white; }}
      #aa-text:focus, #aa-description:focus {{ outline: none; border-color: var(--gold-mid); box-shadow: 0 0 0 3px rgba(201,164,74,0.15); }}
      .aa-desc-label {{ display: block; }}
      .aa-desc-title {{ display: block; font-size: 13px; color: var(--ink-muted); margin-bottom: 6px; font-weight: 600; }}
      .aa-desc-opt {{ font-weight: 400; color: var(--ink-faint); }}
      .aa-hints {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
      .aa-hints label, .aa-grid label {{ display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--ink-muted); text-transform: uppercase; letter-spacing: 0.05em; }}
      .aa-hints select, .aa-grid select, .aa-grid input {{ padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 14px; font-family: inherit; background: white; color: var(--ink); }}
      .aa-actions {{ display: flex; align-items: center; gap: 14px; }}
      .aa-submit {{ background: var(--ink); color: white; border: 0; border-radius: 8px; padding: 12px 22px; font-size: 15px; font-weight: 500; cursor: pointer; font-family: inherit; }}
      .aa-submit:hover {{ background: var(--gold); }}
      .aa-submit:disabled {{ opacity: 0.5; cursor: wait; }}
      .aa-status-msg {{ color: var(--ink-muted); font-size: 13px; }}
      .aa-status-msg.aa-err {{ color: var(--crimson); }}
      .aa-status-msg.aa-ok {{ color: var(--forest); }}
      .aa-empty {{ color: var(--ink-faint); text-align: center; padding: 40px 0; font-style: italic; }}

      .aa-card {{ background: var(--warm-white); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(28,22,16,0.03); }}
      .aa-card-head {{ display: flex; gap: 14px; align-items: flex-start; margin-bottom: 12px; }}
      .aa-card-thumbwrap {{ flex-shrink: 0; }}
      .aa-thumb {{ width: 80px; height: 80px; object-fit: cover; border-radius: 8px; border: 1px solid var(--border); display: block; }}
      .aa-thumbs {{ display: flex; flex-wrap: wrap; gap: 8px; }}
      .aa-thumb-pdf, .aa-thumb-text {{ display: flex; flex-direction: column; align-items: center; justify-content: center; background: var(--gold-light); color: var(--ink-muted); font-size: 24px; line-height: 1.2; text-align: center; padding: 6px; box-sizing: border-box; }}
      .aa-thumb-pdf small, .aa-thumb-text small {{ font-size: 9px; margin-top: 4px; word-break: break-word; }}
      .aa-card-titlebox {{ flex: 1; min-width: 0; }}
      .aa-title-input {{ width: 100%; box-sizing: border-box; font-family: 'Cormorant Garamond', serif; font-size: 22px; font-weight: 600; border: 0; border-bottom: 1px dashed transparent; background: transparent; color: var(--ink); padding: 2px 0; }}
      .aa-title-input:focus {{ outline: none; border-bottom-color: var(--gold-mid); }}
      .aa-meta {{ color: var(--ink-faint); font-size: 12px; margin-top: 2px; }}
      .aa-delete {{ background: transparent; border: 0; color: var(--ink-faint); font-size: 18px; cursor: pointer; padding: 4px 8px; }}
      .aa-delete:hover {{ color: var(--crimson); }}
      .aa-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; margin-bottom: 12px; }}
      .aa-grid .aa-span2 {{ grid-column: span 2; }}
      .aa-section {{ margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-light); }}
      .aa-fg {{ background: linear-gradient(135deg, #f5f0e6 0%, #ede4d0 100%); border-left: 3px solid #1e3566; padding: 14px 16px 12px; border-radius: 8px; border-top: none; margin-top: 14px; }}
      .aa-fg h4 {{ color: #1e3566 !important; font-weight: 600; }}
      .aa-fg-quote {{ font-family: 'Cormorant Garamond', Georgia, serif; font-size: 16px; line-height: 1.5; font-style: italic; color: #2a2520; margin: 0 0 10px; padding: 0; border: none; }}
      .aa-fg-block {{ margin-top: 8px; }}
      .aa-fg-label {{ font-size: 12px; font-weight: 700; color: #1e3566; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 2px; }}
      .aa-fg ul {{ margin: 2px 0 0; padding-left: 20px; font-size: 14px; color: var(--ink); }}
      .aa-fg ul li {{ margin: 3px 0; }}
      .aa-fg-grade {{ display: flex; gap: 14px; align-items: center; background: rgba(30,53,102,0.06); border: 1px solid rgba(30,53,102,0.18); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; }}
      .aa-fg-grade-mark {{ font-family: 'Cormorant Garamond', Georgia, serif; font-size: 36px; line-height: 1; font-weight: 600; color: #1e3566; min-width: 56px; text-align: center; padding: 4px 8px; background: #fff; border: 1px solid rgba(30,53,102,0.25); border-radius: 6px; }}
      .aa-fg-grade-why {{ flex: 1; }}
      .aa-fg-grade-text {{ font-size: 13.5px; line-height: 1.5; color: var(--ink); margin-top: 2px; }}
      .aa-section h4 {{ font-family: 'Cormorant Garamond', serif; font-size: 15px; color: var(--ink-muted); margin: 0 0 6px; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 500; }}
      .aa-section ul {{ margin: 0; padding-left: 20px; font-size: 14px; color: var(--ink); }}
      .aa-section ul li {{ margin: 2px 0; }}
      .aa-summary {{ font-size: 14px; line-height: 1.5; color: var(--ink); }}
      .aa-notes {{ background: var(--gold-light); padding: 10px 12px; border-radius: 6px; border-top: 0; }}
      .aa-error {{ background: #fdebeb; color: var(--crimson); padding: 8px 12px; border-radius: 6px; margin: 8px 0; font-size: 13px; }}
      .aa-card-foot {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border-light); font-size: 12px; color: var(--ink-faint); }}
      .aa-saved {{ color: var(--forest); }}
      .aa-record-toggle {{ background: var(--gold-light); border: 1px solid var(--gold-mid); color: var(--ink); border-radius: 6px; padding: 5px 10px; font-size: 12px; font-weight: 500; cursor: pointer; }}
      .aa-record-toggle:hover {{ background: var(--gold-mid); color: white; }}
      .aa-status-recorded {{ background: rgba(46,125,50,0.10); color: #246b3a; padding: 4px 10px; border-radius: 999px; font-weight: 600; text-decoration: none; border: 1px solid rgba(46,125,50,0.25); }}
      .aa-status-recorded:hover {{ background: rgba(46,125,50,0.18); }}
      .aa-record-form {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; width: 100%; padding: 10px; background: rgba(0,0,0,0.025); border-radius: 8px; margin-top: 6px; }}
      .aa-record-form input[type="date"], .aa-record-form input[type="text"], .aa-record-form select {{ padding: 6px 8px; border: 1px solid var(--border); border-radius: 5px; font-size: 13px; font-family: inherit; background: white; color: var(--ink); }}
      .aa-rec-num {{ width: 60px; text-align: center; }}
      .aa-rec-sep {{ color: var(--ink-faint); }}
      .aa-rec-note {{ flex: 1; min-width: 140px; }}
      .aa-rec-save {{ background: var(--gold-mid); color: white; border: 0; padding: 6px 12px; border-radius: 5px; font-size: 13px; font-weight: 500; cursor: pointer; }}
      .aa-rec-cancel {{ background: transparent; border: 1px solid var(--border); padding: 6px 10px; border-radius: 5px; font-size: 13px; cursor: pointer; color: var(--ink-muted); }}

      @media (max-width: 600px) {{
        .aa-grid {{ grid-template-columns: 1fr 1fr; }}
        .aa-grid .aa-span2 {{ grid-column: span 2; }}
        .aa-hints {{ grid-template-columns: 1fr; }}
      }}
    </style>

    <script>
    (function() {{
      var DRAFT_KEY = 'assignment_analyzer_draft_v1';
      var $ = function(id) {{ return document.getElementById(id); }};
      var fileInput = $('aa-file');
      var fileName  = $('aa-file-name');
      var textArea  = $('aa-text');
      var descArea  = $('aa-description');
      var childSel  = $('aa-child');
      var subjSel   = $('aa-subject');
      var status    = $('aa-status');
      var submitBtn = $('aa-submit');
      var form      = $('aa-form');

      // Restore draft (text fields only — file pickers can't be restored)
      try {{
        var raw = localStorage.getItem(DRAFT_KEY);
        if (raw) {{
          var d = JSON.parse(raw);
          if ((Date.now() - (d._ts || 0)) < 24*3600*1000) {{
            if (d.text) textArea.value = d.text;
            if (d.desc) descArea.value = d.desc;
            if (d.child) childSel.value = d.child;
            if (d.subject) subjSel.value = d.subject;
            if (d.text || d.desc || d.child || d.subject) {{
              status.textContent = 'Your draft was restored.';
              status.className = 'aa-status-msg aa-ok';
              setTimeout(function() {{ status.textContent = ''; status.className = 'aa-status-msg'; }}, 4000);
            }}
          }} else {{
            localStorage.removeItem(DRAFT_KEY);
          }}
        }}
      }} catch(e) {{}}

      function saveDraft() {{
        try {{
          localStorage.setItem(DRAFT_KEY, JSON.stringify({{
            _ts: Date.now(),
            text: textArea.value,
            desc: descArea.value,
            child: childSel.value,
            subject: subjSel.value,
          }}));
        }} catch(e) {{}}
      }}
      ['input','change'].forEach(function(ev) {{
        textArea.addEventListener(ev, saveDraft);
        descArea.addEventListener(ev, saveDraft);
        childSel.addEventListener(ev, saveDraft);
        subjSel.addEventListener(ev, saveDraft);
      }});

      fileInput.addEventListener('change', function() {{
        var fs = fileInput.files;
        if (!fs || !fs.length) {{ fileName.textContent = 'No files chosen — you can pick more than one'; return; }}
        if (fs.length === 1) {{
          fileName.textContent = fs[0].name + ' (' + Math.round(fs[0].size/1024) + ' KB)';
        }} else {{
          var total = 0; var names = [];
          for (var i = 0; i < fs.length; i++) {{ total += fs[i].size; names.push(fs[i].name); }}
          fileName.textContent = fs.length + ' files (' + Math.round(total/1024) + ' KB total): ' + names.join(', ');
        }}
      }});

      form.addEventListener('submit', function(ev) {{
        ev.preventDefault();
        var fs = fileInput.files;
        var f = fs && fs.length ? fs[0] : null;
        var t = textArea.value.trim();
        if (!f && !t) {{
          status.textContent = 'Please choose a file or paste some text.';
          status.className = 'aa-status-msg aa-err';
          return;
        }}
        submitBtn.disabled = true;
        status.textContent = '🤔 Analyzing… (this can take 10–25 seconds)';
        status.className = 'aa-status-msg';
        var fd = new FormData(form);
        fetch('/assignment-analyze', {{ method: 'POST', body: fd }})
          .then(function(r) {{ return r.json().then(function(j) {{ return {{ ok: r.ok, body: j }}; }}); }})
          .then(function(res) {{
            submitBtn.disabled = false;
            if (!res.ok || !res.body || res.body.error) {{
              status.textContent = '✗ ' + ((res.body && res.body.error) || 'Analysis failed');
              status.className = 'aa-status-msg aa-err';
              return;
            }}
            // Success: clear draft and reload to show the new card
            localStorage.removeItem(DRAFT_KEY);
            if (res.body.warning) {{
              status.textContent = '✓ Saved — note: ' + res.body.warning;
              status.className = 'aa-status-msg aa-ok';
              setTimeout(function() {{ window.location.reload(); }}, 2200);
            }} else {{
              status.textContent = '✓ Saved — reloading';
              status.className = 'aa-status-msg aa-ok';
              setTimeout(function() {{ window.location.reload(); }}, 600);
            }}
          }})
          .catch(function(e) {{
            submitBtn.disabled = false;
            status.textContent = '✗ Network error: ' + e;
            status.className = 'aa-status-msg aa-err';
          }});
      }});

      // Per-card editing — debounced auto-save
      var debounceTimers = {{}};
      function scheduleSave(card, id) {{
        if (debounceTimers[id]) clearTimeout(debounceTimers[id]);
        debounceTimers[id] = setTimeout(function() {{ doSave(card, id); }}, 500);
      }}
      function doSave(card, id) {{
        var edits = {{}};
        card.querySelectorAll('[data-field]').forEach(function(el) {{
          edits[el.dataset.field] = el.value;
        }});
        var savedSpan = card.querySelector('.aa-saved');
        if (savedSpan) savedSpan.textContent = 'saving…';
        var fd = new FormData();
        fd.append('id', id);
        fd.append('edits', JSON.stringify(edits));
        fetch('/assignment-update', {{ method: 'POST', body: fd }})
          .then(function(r) {{ return r.ok; }})
          .then(function(ok) {{
            if (savedSpan) {{
              savedSpan.textContent = ok ? '✓ saved' : '✗ save failed';
              setTimeout(function() {{ savedSpan.textContent = ''; }}, 1800);
            }}
          }})
          .catch(function() {{
            if (savedSpan) savedSpan.textContent = '✗ network error';
          }});
      }}
      document.querySelectorAll('.aa-card').forEach(function(card) {{
        var id = card.dataset.id;
        card.querySelectorAll('[data-field]').forEach(function(el) {{
          el.addEventListener('input', function() {{ scheduleSave(card, id); }});
          el.addEventListener('change', function() {{ scheduleSave(card, id); }});
        }});
        var del = card.querySelector('.aa-delete');
        if (del) del.addEventListener('click', function() {{
          if (!confirm('Delete this analysis?')) return;
          var fd = new FormData(); fd.append('id', id);
          fetch('/assignment-delete', {{ method: 'POST', body: fd }})
            .then(function(r) {{ if (r.ok) card.remove(); }});
        }});

        // Record-grade interactions
        var recToggle = card.querySelector('.aa-record-toggle');
        var recForm   = card.querySelector('.aa-record-form');
        if (recToggle && recForm) {{
          recToggle.addEventListener('click', function() {{
            recForm.style.display = (recForm.style.display === 'none') ? 'flex' : 'none';
            if (recForm.style.display === 'flex') {{
              var s = recForm.querySelector('input[name="raw_score"]');
              if (s) s.focus();
            }}
          }});
          var cancel = recForm.querySelector('.aa-rec-cancel');
          if (cancel) cancel.addEventListener('click', function() {{
            recForm.style.display = 'none';
          }});
          // Auto-letter from score+total
          function gbLetterFromPct(p) {{
            var scale = [['A+',97],['A',93],['A-',90],['B+',87],['B',83],['B-',80],['C+',77],['C',73],['C-',70],['D',60],['F',0]];
            for (var i=0;i<scale.length;i++) {{ if (p >= scale[i][1]) return scale[i][0]; }}
            return 'F';
          }}
          function gbAutoCalc() {{
            var raw = parseFloat(recForm.raw_score.value);
            var tot = parseFloat(recForm.total.value);
            if (!isNaN(raw) && !isNaN(tot) && tot > 0) {{
              recForm.letter.value = gbLetterFromPct((raw/tot)*100);
            }}
          }}
          recForm.raw_score.addEventListener('input', gbAutoCalc);
          recForm.total.addEventListener('input', gbAutoCalc);

          recForm.addEventListener('submit', function(ev) {{
            ev.preventDefault();
            gbAutoCalc();
            var fd = new FormData(recForm);
            // Pull title from the latest edit (Mom may have changed it)
            var titleInput = card.querySelector('[data-field="title"]');
            if (titleInput) fd.set('title', titleInput.value);
            var subjectSel = card.querySelector('[data-field="subject"]');
            if (subjectSel) fd.set('subject', subjectSel.value);
            var childSel = card.querySelector('[data-field="child_guess"]');
            if (childSel && childSel.value) fd.set('child', childSel.value);
            var saveBtn = recForm.querySelector('.aa-rec-save');
            if (saveBtn) {{ saveBtn.disabled = true; saveBtn.textContent = '…'; }}
            fetch('/gradebook-add', {{ method: 'POST', body: fd }})
              .then(function(r) {{ return r.json(); }})
              .then(function(j) {{
                if (j && j.ok) {{
                  // Replace footer with recorded chip
                  var pct = (j.entry && j.entry.percentage != null) ? j.entry.percentage : '';
                  var letter = (j.entry && j.entry.letter) || '';
                  var chip = '✓ Recorded';
                  if (pct !== '') chip += ' · ' + Math.round(parseFloat(pct)) + '%';
                  if (letter) chip += ' · ' + letter;
                  var foot = card.querySelector('.aa-card-foot');
                  if (foot) {{
                    var childForLink = (childSel && childSel.value) || (j.entry && j.entry.child) || 'JP';
                    foot.innerHTML = '<a class="aa-status aa-status-recorded" href="/gradebook?child=' +
                      encodeURIComponent(childForLink) + '">' + chip + '</a>' +
                      '<span class="aa-saved" data-id="' + id + '"></span>';
                  }}
                }} else {{
                  if (saveBtn) {{ saveBtn.disabled = false; saveBtn.textContent = 'Save'; }}
                  alert((j && j.error) || 'Save failed');
                }}
              }})
              .catch(function(e) {{
                if (saveBtn) {{ saveBtn.disabled = false; saveBtn.textContent = 'Save'; }}
                alert('Network error: ' + e);
              }});
          }});
        }}
      }});
    }})();
    </script>
    """
    return html_page("Assignment Analyzer · Sancta Familia", body)
