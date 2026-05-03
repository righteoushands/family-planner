"""
render_plan_year.py — Plan My Year
Annual overview: all 4 quarters, all active goals, completion progress.
"""
import json, os
from datetime import date
from html import escape

from render_goals import (
    load_master_goals, load_quarter_plan, current_quarter, all_quarters,
    quarter_label, quarter_start, quarter_end, completion_pct,
    goal_progress_bars, CATEGORY_ICONS, CHECK_COLORS,
)
from render_settings import load_app_settings
from ui_helpers import html_page, top_nav, render_status_message


def render_plan_year_page(year=None, status=""):
    if year is None:
        year = date.today().year
    try:
        year = int(year)
    except Exception:
        year = date.today().year

    prev_year   = year - 1
    next_year   = year + 1
    master      = load_master_goals()
    master_map  = {g["id"]: g for g in master}
    settings    = load_app_settings()
    api_key     = (settings.get("anthropic_api_key", "") or
                   settings.get("family_constraints", {}).get("anthropic_api_key", ""))
    cur_quarter = current_quarter()

    # Load all 4 quarter plans
    quarters = {}
    for qk in all_quarters(year):
        quarters[qk] = load_quarter_plan(qk)

    # ── Annual stats ─────────────────────────────────────────────────────────
    total_goal_weeks = 0
    done_weeks       = 0
    active_goal_ids_year = set()
    for qk, qplan in quarters.items():
        for gid in qplan.get("active_goal_ids", []):
            active_goal_ids_year.add(gid)
            g_plan   = qplan.get("goals", {}).get(gid, {})
            checkins = g_plan.get("checkins", {})
            for w in range(1, 14):
                c = checkins.get(str(w))
                if c:
                    total_goal_weeks += 1
                    if c in ("done","partial"):
                        done_weeks += 1

    overall_pct = round(done_weeks / total_goal_weeks * 100) if total_goal_weeks else 0

    # ── Quarter panels ────────────────────────────────────────────────────────
    quarter_panels = ""
    for qk in all_quarters(year):
        qplan      = quarters[qk]
        qlabel     = quarter_label(qk)
        qstart     = quarter_start(qk)
        qend       = quarter_end(qk)
        active_ids = qplan.get("active_goal_ids", [])
        is_current = (qk == cur_quarter)
        is_past    = (qend < date.today())
        is_future  = (qstart > date.today())

        # Quarter status badge
        if is_current:
            badge_text = "Current"
            badge_bg   = "#dbeafe"
            badge_col  = "#1e40af"
        elif is_past:
            badge_text = "Complete"
            badge_bg   = "#dcfce7"
            badge_col  = "#166534"
        else:
            badge_text = "Upcoming"
            badge_bg   = "#f3f4f6"
            badge_col  = "#6b7280"

        badge = (
            f'<span style="font-size:0.68em;background:{badge_bg};color:{badge_col};'
            f'font-weight:700;padding:2px 8px;border-radius:10px;">{badge_text}</span>'
        )

        # Goal rows for this quarter
        goal_rows = ""
        q_done = q_total = 0
        for gid in active_ids:
            g      = master_map.get(gid, {})
            g_plan = qplan.get("goals", {}).get(gid, {})
            if not g:
                continue
            title   = escape(g.get("title",""))
            cat     = g.get("category","")
            icon    = CATEGORY_ICONS.get(cat, "\u2b50")
            bars    = goal_progress_bars(g_plan, qk)

            # Compute through correct week
            if is_current:
                from render_goals import quarter_week_number
                wk = quarter_week_number(quarter_key=qk)
            elif is_past:
                wk = 13
            else:
                wk = 0

            pct = completion_pct(g_plan, wk) if wk > 0 else 0
            q_done  += pct
            q_total += 1

            pct_color = "#22c55e" if pct >= 70 else "#f59e0b" if pct >= 40 else "#ef4444"

            goal_rows += (
                f'<div style="padding:8px 0;border-bottom:1px solid var(--border-light);">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
                f'<div>'
                f'<div style="font-size:0.68em;color:var(--ink-faint);">{icon} {escape(cat)}</div>'
                f'<div style="font-size:0.85em;font-weight:600;color:var(--ink);">{title}</div>'
                f'</div>'
                f'<div style="font-size:0.75em;font-weight:700;color:{pct_color};">'
                f'{"" if wk == 0 else str(pct) + "%"}</div>'
                f'</div>'
                f'<div style="margin-top:5px;">{bars}</div>'
                f'</div>'
            )

        q_avg = round(q_done / q_total) if q_total else 0
        border_color = "var(--gold-mid)" if is_current else "var(--border)"
        bg_color     = "var(--gold-light)" if is_current else "white"

        quarter_panels += f"""
<div style="border:1.5px solid {border_color};border-radius:14px;overflow:hidden;
            margin-bottom:14px;background:{bg_color};">
  <div style="padding:12px 16px;display:flex;align-items:center;
              justify-content:space-between;border-bottom:1px solid var(--border-light);">
    <div>
      <div style="font-weight:700;font-size:0.95em;color:var(--ink);">{escape(qlabel)}</div>
      <div style="font-size:0.75em;color:var(--ink-faint);">
        {len(active_ids)} goal{"s" if len(active_ids) != 1 else ""}
        {" &middot; " + str(q_avg) + "% avg" if q_avg > 0 else ""}
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:8px;">
      {badge}
      <a href="/plan-quarter?quarter={escape(qk)}"
         style="padding:5px 12px;font-size:0.78em;background:var(--ink);color:var(--gold-light);
                border-radius:8px;text-decoration:none;font-weight:600;">
        {"View" if not is_future else "Plan"}
      </a>
    </div>
  </div>
  <div style="padding:8px 16px;">
    {goal_rows if goal_rows else
     '<p style="font-size:0.82em;color:var(--ink-faint);padding:8px 0;">No goals planned yet.</p>'}
  </div>
</div>"""

    # ── Master goal summary ───────────────────────────────────────────────────
    master_rows = ""
    for g in master:
        gid   = g.get("id","")
        title = escape(g.get("title",""))
        cat   = g.get("category","")
        icon  = CATEGORY_ICONS.get(cat,"\u2b50")
        why   = escape(g.get("why",""))

        # Which quarters is this active in?
        active_in = [qk for qk in all_quarters(year)
                     if gid in quarters[qk].get("active_goal_ids",[])]
        q_badges  = "".join(
            f'<span style="font-size:0.65em;background:var(--gold-light);color:var(--brown);'
            f'padding:1px 6px;border-radius:8px;margin-right:3px;">{escape(quarter_label(qk))}</span>'
            for qk in active_in
        )

        # Pre-compute conditionals before string concatenation
        why_html   = (
            '<div style="font-size:0.72em;color:var(--ink-faint);margin-top:2px;'
            'font-style:italic;">' + why + '</div>'
        ) if why else ""
        badges_html = (
            q_badges if q_badges else
            '<span style="font-size:0.65em;color:var(--ink-faint);">Not scheduled this year</span>'
        )
        master_rows += (
            '<div style="display:flex;align-items:flex-start;justify-content:space-between;'
            'gap:8px;padding:8px 0;border-bottom:1px solid var(--border-light);">'
            '<div style="flex:1;">'
            '<div style="font-size:0.7em;color:var(--ink-faint);">' + icon + ' ' + escape(cat) + '</div>'
            '<div style="font-weight:600;font-size:0.88em;color:var(--ink);">' + title + '</div>'
            + why_html
            + '<div style="margin-top:4px;">' + badges_html + '</div>'
            '</div>'
            '<a href="/plan-quarter" style="font-size:0.72em;color:var(--brown);font-weight:600;'
            'text-decoration:none;white-space:nowrap;">Edit \u2192</a>'
            '</div>'
        )

    if not master_rows:
        master_rows = '<p style="font-size:0.82em;color:var(--ink-faint);padding:8px 0;">No goals yet. Add them in quarterly planning.</p>'

    # AI year button
    ai_btn = ""
    if api_key:
        ai_btn = (
            f'<button onclick="aiYearReview()" '
            f'style="width:100%;padding:10px;background:linear-gradient(135deg,#1c1610,#2a1e10);'
            f'color:var(--gold-light);border:none;border-radius:10px;font-size:0.88em;'
            f'font-weight:600;font-family:inherit;cursor:pointer;margin-top:12px;">'
            f'\u2728 AI Year Review &amp; Next Quarter Prep</button>'
            f'<div id="ai-year-loading" style="display:none;text-align:center;padding:12px;'
            f'font-size:0.82em;color:var(--ink-faint);">\u231b Thinking...</div>'
            f'<div id="ai-year-result" style="display:none;margin-top:10px;padding:10px 12px;'
            f'background:#faf8f5;border-radius:8px;font-size:0.85em;line-height:1.65;'
            f'color:var(--ink);"></div>'
        )

    master_js = json.dumps(master)

    body = top_nav() + render_status_message(status) + f"""
<div style="display:flex;align-items:flex-start;justify-content:space-between;
            flex-wrap:wrap;gap:8px;padding-top:4px;margin-bottom:16px;">
  <div>
    <div style="font-family:'Cormorant Garamond',Georgia,serif;
                font-size:2rem;font-weight:600;color:var(--ink);">Plan My Year</div>
    <div style="font-size:0.85em;color:var(--ink-muted);margin-top:2px;">{year}</div>
  </div>
  <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
    <a href="/plan-year?year={prev_year}"
       style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);">&larr; {prev_year}</a>
    <a href="/plan-year?year={next_year}"
       style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-size:0.82em;text-decoration:none;color:var(--ink);">{next_year} &rarr;</a>
  </div>
</div>

<!-- Annual stats -->
<div class="card" style="margin-bottom:16px;background:linear-gradient(135deg,#1c1610,#2a1e10);color:var(--gold-light);border:none;">
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;text-align:center;">
    <div>
      <div style="font-size:1.6rem;font-weight:700;">{len(active_goal_ids_year)}</div>
      <div style="font-size:0.72em;opacity:0.7;">Goals this year</div>
    </div>
    <div>
      <div style="font-size:1.6rem;font-weight:700;">{overall_pct}%</div>
      <div style="font-size:0.72em;opacity:0.7;">Overall progress</div>
    </div>
    <div>
      <div style="font-size:1.6rem;font-weight:700;">{done_weeks}</div>
      <div style="font-size:0.72em;opacity:0.7;">Weeks completed</div>
    </div>
  </div>
  {ai_btn}
</div>

<!-- Quarter panels -->
<div style="margin-bottom:16px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:10px;">Quarters</div>
  {quarter_panels}
</div>

<!-- Master goal list -->
<div class="card" style="margin-bottom:16px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:10px;display:flex;justify-content:space-between;">
    <span>All Goals ({len(master)}/12)</span>
    <a href="/plan-quarter" style="font-size:0.9em;color:var(--brown);font-weight:600;
       text-decoration:none;text-transform:none;">+ Add / manage &rarr;</a>
  </div>
  {master_rows}
</div>

<!-- Nav -->
<div style="display:flex;gap:8px;flex-wrap:wrap;padding:8px 0;">
  <a href="/plan-quarter" style="font-size:0.82em;color:var(--brown);font-weight:700;text-decoration:none;">Quarterly goals &rarr;</a>
  <span style="color:var(--border);">|</span>
  <a href="/plan-month" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">This month &rarr;</a>
  <span style="color:var(--border);">|</span>
  <a href="/plan-week" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">This week &rarr;</a>
</div>

<script>
var _year   = {year};
var _master = {master_js};

function aiYearReview() {{
  var loading = document.getElementById('ai-year-loading');
  var result  = document.getElementById('ai-year-result');
  if (loading) loading.style.display = 'block';
  if (result)  result.style.display  = 'none';
  fetch('/ai-year-brief', {{
    method: 'POST', headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'data=' + encodeURIComponent(JSON.stringify({{year: _year, goals: _master}}))
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (loading) loading.style.display = 'none';
    if (result) {{
      result.style.display = 'block';
      result.innerHTML = (d.briefing || d.text || 'No review returned.').replace(/\\n/g,'<br>');
    }}
  }}).catch(function() {{
    if (loading) loading.style.display = 'none';
    if (result) {{ result.style.display='block'; result.textContent='Error \u2014 check API key.'; }}
  }});
}}
</script>
"""
    return html_page(f"Plan My Year \u00b7 {year}", body)