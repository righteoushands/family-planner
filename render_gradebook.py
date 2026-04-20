"""
render_gradebook.py — Per-child gradebook of recorded assignment scores.

Page: /gradebook?child=JP&year=2025-2026
- Subjects view, divided by school year (Aug-Jul).
- GPA-style for older boys (JP, Joseph). Encouragement marks for Michael.
- Inline edit + delete; entries link back to the source analyzer card when present.
- Stored in data/gradebook.json via data_helpers.

Routes (POST in app.py):
  /gradebook-add     {child, subject, title, date, raw_score, total, percentage, letter, note, source_analysis_id}
  /gradebook-update  {id, edits:json}
  /gradebook-delete  {id}
"""
from html import escape as _esc
from urllib.parse import quote as _q
from datetime import date as _date

from data_helpers import (
    gradebook_for_child,
    GRADE_LETTERS,
    GPA_CHILDREN,
    letter_to_gpa,
    school_year_for_date,
)
from ui_helpers import html_page

CHILDREN = ["JP", "Joseph", "Michael"]
SUBJECTS = [
    "Math", "Latin", "Greek", "Religion", "History", "Science",
    "Reading", "Writing", "Grammar", "Literature", "Art", "Music",
    "Logic", "PE", "Other",
]


def _fmt_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        d = _date.fromisoformat(iso[:10])
        return d.strftime("%b %-d, %Y")
    except Exception:
        return iso


def _avg(nums):
    nums = [n for n in nums if n is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _all_school_years_for(child: str):
    """Years that have entries for this child, plus current year, sorted desc."""
    from data_helpers import load_gradebook
    years = {e.get("school_year","") for e in load_gradebook()["entries"]
             if e.get("child") == child and e.get("school_year")}
    years.add(school_year_for_date(_date.today().isoformat()))
    return sorted([y for y in years if y], reverse=True)


def _entry_row_html(e: dict, gpa_mode: bool) -> str:
    eid = _esc(e.get("id",""))
    date_str = _esc(_fmt_date(e.get("date","")))
    title = _esc(str(e.get("title","")))
    raw = e.get("raw_score","")
    total = e.get("total","")
    pct = e.get("percentage","")
    letter = e.get("letter","")
    note = e.get("note","")
    src = e.get("source_analysis_id","")

    score_str = ""
    if raw not in ("", None) and total not in ("", None):
        score_str = f"{raw} / {total}"
    elif raw not in ("", None):
        score_str = str(raw)

    pct_str = ""
    if pct not in ("", None):
        try: pct_str = f"{float(pct):.0f}%"
        except Exception: pct_str = str(pct)

    gpa_chip = ""
    if gpa_mode and letter:
        g = letter_to_gpa(letter)
        if g is not None:
            gpa_chip = f' <span class="gb-gpa">{g:.1f}</span>'

    src_link = ""
    if src:
        src_link = f' <a class="gb-src" href="/assignment-analyzer#{_esc(src)}" title="View original analysis">📎</a>'

    return f"""
    <tr class="gb-row" data-id="{eid}">
      <td class="gb-date">{date_str}</td>
      <td class="gb-title">{title}{src_link}</td>
      <td class="gb-score">{_esc(score_str)}</td>
      <td class="gb-pct">{_esc(pct_str)}</td>
      <td class="gb-letter">{_esc(str(letter))}{gpa_chip}</td>
      <td class="gb-note">{_esc(str(note))}</td>
      <td class="gb-actions">
        <button class="gb-edit" data-id="{eid}" title="Edit">✎</button>
        <button class="gb-del"  data-id="{eid}" title="Delete">✕</button>
      </td>
    </tr>
    """


def _subject_section_html(subject: str, entries: list, gpa_mode: bool) -> str:
    pcts = []
    gpas = []
    for e in entries:
        try:
            if e.get("percentage") not in ("", None):
                pcts.append(float(e["percentage"]))
        except Exception:
            pass
        if gpa_mode:
            g = letter_to_gpa(e.get("letter",""))
            if g is not None:
                gpas.append(g)

    avg_p = _avg(pcts)
    avg_g = _avg(gpas) if gpa_mode else None

    summary_bits = [f"{len(entries)} graded"]
    if avg_p is not None:
        summary_bits.append(f"avg {avg_p:.1f}%")
    if avg_g is not None:
        summary_bits.append(f"GPA {avg_g:.2f}")
    summary = " · ".join(summary_bits)

    rows = "\n".join(_entry_row_html(e, gpa_mode) for e in entries)

    return f"""
    <section class="gb-subject">
      <header class="gb-subject-head">
        <h3>{_esc(subject)}</h3>
        <span class="gb-subject-sum">{_esc(summary)}</span>
      </header>
      <table class="gb-table">
        <thead><tr>
          <th>Date</th><th>Assignment</th><th>Score</th><th>%</th><th>Grade</th><th>Note</th><th></th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    """


def render_gradebook_page(child: str = "", year: str = "") -> str:
    if child not in CHILDREN:
        child = "JP"
    if not year:
        year = school_year_for_date(_date.today().isoformat())

    gpa_mode = child in GPA_CHILDREN
    entries = gradebook_for_child(child, school_year=year)

    # Group by subject (preserve SUBJECTS order, then any extras alphabetically)
    by_subj = {}
    for e in entries:
        s = (e.get("subject") or "Other").strip() or "Other"
        by_subj.setdefault(s, []).append(e)
    ordered_subjs = [s for s in SUBJECTS if s in by_subj] + \
                    sorted([s for s in by_subj if s not in SUBJECTS])

    sections = "\n".join(
        _subject_section_html(s, by_subj[s], gpa_mode) for s in ordered_subjs
    )

    if not entries:
        sections = (
            '<div class="gb-empty">No grades recorded yet for this year. '
            'Record one from the <a href="/assignment-analyzer">Assignment Analyzer</a> — '
            'each analyzed card now has a <strong>📓 Record grade</strong> button.</div>'
        )

    # Overall summary across subjects
    all_pcts = []
    all_gpas = []
    for e in entries:
        try:
            if e.get("percentage") not in ("", None):
                all_pcts.append(float(e["percentage"]))
        except Exception:
            pass
        if gpa_mode:
            g = letter_to_gpa(e.get("letter",""))
            if g is not None:
                all_gpas.append(g)

    overall_bits = [f"{len(entries)} entries"]
    if all_pcts:
        overall_bits.append(f"overall {sum(all_pcts)/len(all_pcts):.1f}%")
    if all_gpas:
        overall_bits.append(f"GPA {sum(all_gpas)/len(all_gpas):.2f}")
    overall = " · ".join(overall_bits)

    # Tabs: child + year
    child_tabs = "".join(
        f'<a class="gb-tab{" gb-tab-on" if c == child else ""}" '
        f'href="/gradebook?child={_q(c)}&year={_q(year)}">{_esc(c)}</a>'
        for c in CHILDREN
    )
    years = _all_school_years_for(child)
    year_tabs = "".join(
        f'<a class="gb-ytab{" gb-ytab-on" if y == year else ""}" '
        f'href="/gradebook?child={_q(child)}&year={_q(y)}">{_esc(y)}</a>'
        for y in years
    )

    subj_opts = "".join(f'<option value="{_esc(s)}">{_esc(s)}</option>' for s in SUBJECTS)
    letter_opts = "".join(f'<option value="{_esc(l)}">{_esc(l)}</option>' for l in [""] + GRADE_LETTERS)

    body = f"""
    <div class="gb-wrap">
      <a class="gb-back" href="/school">← School</a>
      <h1 class="gb-h1">📓 Gradebook</h1>
      <p class="gb-sub">Recorded scores for assignments. Subject view, divided by school year.</p>

      <nav class="gb-tabs">{child_tabs}</nav>
      <nav class="gb-ytabs">{year_tabs}</nav>

      <div class="gb-overall">{_esc(overall)}{' · GPA scale' if gpa_mode else ' · encouragement marks (no GPA)'}</div>

      <div class="gb-add">
        <button id="gb-add-toggle" class="gb-add-btn">+ Record a grade</button>
        <form id="gb-add-form" class="gb-add-form" style="display:none;">
          <div class="gb-add-grid">
            <label>Date<input type="date" name="date" value="{_date.today().isoformat()}" required/></label>
            <label>Subject<select name="subject" required>{subj_opts}</select></label>
            <label class="gb-add-wide">Assignment title<input type="text" name="title" required placeholder="e.g. Latin Quiz 4"/></label>
            <label>Score<input type="text" name="raw_score" placeholder="18" inputmode="decimal"/></label>
            <label>Total<input type="text" name="total" placeholder="20" inputmode="decimal"/></label>
            <label>% (auto)<input type="text" name="percentage" placeholder="auto" inputmode="decimal"/></label>
            <label>Letter<select name="letter">{letter_opts}</select></label>
            <label class="gb-add-wide">Note (optional)<input type="text" name="note" placeholder="e.g. retake — first attempt 78%"/></label>
          </div>
          <div class="gb-add-foot">
            <button type="submit" class="gb-add-save">Save grade</button>
            <button type="button" id="gb-add-cancel" class="gb-add-cancel">Cancel</button>
            <span id="gb-add-status" class="gb-add-status"></span>
          </div>
        </form>
      </div>

      {sections}
    </div>

    <style>
      .gb-wrap {{ max-width: 980px; margin: 0 auto; padding: 18px 16px 80px; color: var(--ink); font-family: 'DM Sans', system-ui, sans-serif; }}
      .gb-back {{ color: var(--ink-muted); text-decoration: none; font-size: 14px; }}
      .gb-back:hover {{ color: var(--gold); }}
      .gb-h1 {{ font-family: 'Cormorant Garamond', serif; font-size: 32px; margin: 8px 0 4px; color: var(--ink); }}
      .gb-sub {{ color: var(--ink-muted); font-size: 14px; margin: 0 0 16px; }}
      .gb-tabs, .gb-ytabs {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }}
      .gb-tab, .gb-ytab {{ padding: 6px 12px; border: 1px solid var(--border); border-radius: 999px; text-decoration: none; color: var(--ink-muted); font-size: 13px; background: white; }}
      .gb-tab-on, .gb-ytab-on {{ background: var(--gold-light); border-color: var(--gold-mid); color: var(--ink); font-weight: 600; }}
      .gb-ytab {{ font-size: 12px; }}
      .gb-overall {{ color: var(--ink-muted); font-size: 13px; margin: 10px 0 16px; padding: 8px 12px; background: rgba(0,0,0,0.025); border-radius: 6px; }}

      .gb-add {{ margin-bottom: 22px; }}
      .gb-add-btn {{ background: var(--gold-light); color: var(--ink); border: 1px solid var(--gold-mid); padding: 8px 14px; border-radius: 8px; font-weight: 500; cursor: pointer; font-size: 14px; }}
      .gb-add-btn:hover {{ background: var(--gold-mid); color: white; }}
      .gb-add-form {{ background: var(--card-bg, #fff); border: 1px solid var(--border); border-radius: 10px; padding: 14px; margin-top: 10px; }}
      .gb-add-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }}
      .gb-add-grid .gb-add-wide {{ grid-column: span 2; }}
      .gb-add-grid label {{ display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--ink-muted); text-transform: uppercase; letter-spacing: 0.04em; }}
      .gb-add-grid input, .gb-add-grid select {{ padding: 7px 9px; border: 1px solid var(--border); border-radius: 6px; font-size: 14px; font-family: inherit; background: white; color: var(--ink); }}
      .gb-add-foot {{ display: flex; align-items: center; gap: 10px; margin-top: 12px; }}
      .gb-add-save {{ background: var(--gold-mid); color: white; border: 0; padding: 8px 16px; border-radius: 6px; font-weight: 500; cursor: pointer; }}
      .gb-add-cancel {{ background: transparent; border: 1px solid var(--border); padding: 8px 14px; border-radius: 6px; cursor: pointer; color: var(--ink-muted); }}
      .gb-add-status {{ font-size: 13px; color: var(--ink-muted); }}
      .gb-add-status.ok {{ color: #246b3a; }}
      .gb-add-status.err {{ color: var(--crimson, #b33); }}

      .gb-subject {{ margin-bottom: 26px; }}
      .gb-subject-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 6px; border-bottom: 1px solid var(--border); padding-bottom: 4px; }}
      .gb-subject-head h3 {{ font-family: 'Cormorant Garamond', serif; font-size: 22px; margin: 0; color: var(--ink); }}
      .gb-subject-sum {{ color: var(--ink-faint); font-size: 13px; }}
      .gb-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
      .gb-table th {{ text-align: left; font-weight: 500; color: var(--ink-faint); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; padding: 6px 8px; border-bottom: 1px solid var(--border); }}
      .gb-table td {{ padding: 8px; border-bottom: 1px solid var(--border-light, #eee); vertical-align: top; }}
      .gb-date {{ color: var(--ink-muted); white-space: nowrap; font-size: 13px; }}
      .gb-title {{ font-weight: 500; }}
      .gb-score, .gb-pct, .gb-letter {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
      .gb-letter {{ font-weight: 600; color: #1e3566; }}
      .gb-gpa {{ color: var(--ink-faint); font-weight: 400; font-size: 12px; margin-left: 4px; }}
      .gb-note {{ color: var(--ink-muted); font-size: 13px; }}
      .gb-actions {{ white-space: nowrap; text-align: right; }}
      .gb-edit, .gb-del {{ background: transparent; border: 0; cursor: pointer; padding: 2px 6px; color: var(--ink-faint); font-size: 14px; }}
      .gb-edit:hover {{ color: var(--ink); }}
      .gb-del:hover {{ color: var(--crimson, #b33); }}
      .gb-src {{ text-decoration: none; opacity: 0.55; margin-left: 4px; }}
      .gb-src:hover {{ opacity: 1; }}
      .gb-empty {{ background: rgba(0,0,0,0.025); border: 1px dashed var(--border); border-radius: 8px; padding: 24px; text-align: center; color: var(--ink-muted); }}

      @media (max-width: 720px) {{
        .gb-add-grid {{ grid-template-columns: repeat(2, 1fr); }}
        .gb-add-grid .gb-add-wide {{ grid-column: span 2; }}
        .gb-table {{ font-size: 13px; }}
        .gb-table th:nth-child(6), .gb-table td.gb-note {{ display: none; }}
      }}
      @media print {{
        .gb-tabs, .gb-ytabs, .gb-add, .gb-actions, .gb-back {{ display: none !important; }}
        .gb-table th:nth-child(7) {{ display: none; }}
      }}
    </style>

    <script>
      (function() {{
        var $ = function(id) {{ return document.getElementById(id); }};
        var toggle = $('gb-add-toggle');
        var form   = $('gb-add-form');
        var cancel = $('gb-add-cancel');
        var status = $('gb-add-status');
        if (toggle) toggle.addEventListener('click', function() {{
          form.style.display = (form.style.display === 'none') ? 'block' : 'none';
          if (form.style.display === 'block') {{
            var t = form.querySelector('input[name="title"]'); if (t) t.focus();
          }}
        }});
        if (cancel) cancel.addEventListener('click', function() {{
          form.style.display = 'none';
          form.reset();
        }});

        // Auto-compute % and letter when score/total change
        function autoCalc() {{
          var raw = parseFloat(form.raw_score.value);
          var tot = parseFloat(form.total.value);
          var pctField = form.percentage;
          var letField = form.letter;
          if (!isNaN(raw) && !isNaN(tot) && tot > 0) {{
            var p = (raw / tot) * 100;
            pctField.value = p.toFixed(1);
            letField.value = letterFromPct(p);
          }} else if (form.percentage.value && !isNaN(parseFloat(form.percentage.value))) {{
            letField.value = letterFromPct(parseFloat(form.percentage.value));
          }}
        }}
        function letterFromPct(p) {{
          var scale = [['A+',97],['A',93],['A-',90],['B+',87],['B',83],['B-',80],['C+',77],['C',73],['C-',70],['D',60],['F',0]];
          for (var i=0;i<scale.length;i++) {{ if (p >= scale[i][1]) return scale[i][0]; }}
          return 'F';
        }}
        ['raw_score','total','percentage'].forEach(function(n) {{
          var el = form && form.elements && form.elements[n];
          if (el) el.addEventListener('input', autoCalc);
        }});

        if (form) form.addEventListener('submit', function(ev) {{
          ev.preventDefault();
          autoCalc();
          var fd = new FormData(form);
          fd.append('child', {child!r});
          status.textContent = 'Saving…'; status.className = 'gb-add-status';
          fetch('/gradebook-add', {{ method: 'POST', body: fd }})
            .then(function(r) {{ return r.json(); }})
            .then(function(j) {{
              if (j && j.ok) {{
                status.textContent = '✓ Saved'; status.className = 'gb-add-status ok';
                setTimeout(function() {{ window.location.reload(); }}, 400);
              }} else {{
                status.textContent = '✗ ' + ((j && j.error) || 'Save failed');
                status.className = 'gb-add-status err';
              }}
            }})
            .catch(function(e) {{
              status.textContent = '✗ ' + e; status.className = 'gb-add-status err';
            }});
        }});

        // Per-row delete
        document.querySelectorAll('.gb-del').forEach(function(btn) {{
          btn.addEventListener('click', function() {{
            if (!confirm('Delete this grade entry? This cannot be undone.')) return;
            var id = btn.dataset.id;
            var fd = new FormData(); fd.append('id', id);
            fetch('/gradebook-delete', {{ method: 'POST', body: fd }})
              .then(function(r) {{ return r.json(); }})
              .then(function(j) {{
                if (j && j.ok) {{
                  var row = btn.closest('tr'); if (row) row.remove();
                }} else {{
                  alert('Delete failed.');
                }}
              }});
          }});
        }});

        // Per-row edit (inline prompt-based, simple)
        document.querySelectorAll('.gb-edit').forEach(function(btn) {{
          btn.addEventListener('click', function() {{
            var row = btn.closest('tr');
            var title = row.querySelector('.gb-title').textContent.replace(/📎.*/,'').trim();
            var newTitle = prompt('Assignment title:', title);
            if (newTitle === null) return;
            var newScore = prompt('Score (e.g. 18):', row.querySelector('.gb-score').textContent.split('/')[0].trim());
            if (newScore === null) return;
            var newTotal = prompt('Out of (e.g. 20):', row.querySelector('.gb-score').textContent.split('/')[1] ? row.querySelector('.gb-score').textContent.split('/')[1].trim() : '');
            if (newTotal === null) return;
            var newNote = prompt('Note (optional):', row.querySelector('.gb-note').textContent);
            if (newNote === null) return;
            var edits = {{ title: newTitle, raw_score: newScore, total: newTotal, note: newNote }};
            if (newScore && newTotal && parseFloat(newTotal) > 0) {{
              var p = (parseFloat(newScore) / parseFloat(newTotal)) * 100;
              edits.percentage = p.toFixed(1);
              edits.letter = letterFromPct(p);
            }}
            var fd = new FormData();
            fd.append('id', btn.dataset.id);
            fd.append('edits', JSON.stringify(edits));
            fetch('/gradebook-update', {{ method: 'POST', body: fd }})
              .then(function(r) {{ return r.json(); }})
              .then(function(j) {{
                if (j && j.ok) window.location.reload();
                else alert('Update failed.');
              }});
          }});
        }});
      }})();
    </script>
    """

    return html_page("Gradebook · Sancta Familia", body)
