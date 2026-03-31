"""
render_plan_quarter.py — Quarterly Goal Planning

At the start of each quarter, select 4-5 goals from the master list.
AI helps choose which ones fit the season, cycle patterns, and calendar.
AI also generates a 13-week step plan for each selected goal.
"""
import json, os
from datetime import date, timedelta
from html import escape

from render_goals import (
    load_master_goals, save_master_goals, add_master_goal,
    load_quarter_plan, save_quarter_plan, get_active_goals_with_steps,
    current_quarter, quarter_start, quarter_label, quarter_week_number,
    all_quarters, goal_progress_bars, completion_pct,
    CATEGORIES, CATEGORY_ICONS, STATUS_COLORS, CHECK_LABELS, CHECK_COLORS,
)
from render_settings import load_app_settings
from ui_helpers import html_page, top_nav, render_status_message


def render_plan_quarter_page(quarter_key: str = None, status: str = "") -> str:
    if not quarter_key:
        quarter_key = current_quarter()

    plan    = load_quarter_plan(quarter_key)
    master  = load_master_goals()
    active_ids = plan.get("active_goal_ids", [])
    settings   = load_app_settings()
    api_key    = (settings.get("anthropic_api_key", "") or
                  settings.get("family_constraints", {}).get("anthropic_api_key", ""))

    wk_num  = quarter_week_number(quarter_key=quarter_key)
    qs      = quarter_start(quarter_key)
    q_label = quarter_label(quarter_key)

    # Liturgical season for this quarter
    try:
        from render_liturgical import get_liturgical_season
        season = get_liturgical_season(qs)
    except Exception:
        season = "Ordinary Time"

    # ── Master goal list cards ────────────────────────────────────────────────
    master_cards = ""
    for g in master:
        gid      = g.get("id","")
        title    = escape(g.get("title",""))
        cat      = g.get("category","")
        why      = escape(g.get("why",""))
        metric   = escape(g.get("metric",""))
        icon     = CATEGORY_ICONS.get(cat, "\u2b50")
        is_active = gid in active_ids
        g_plan   = plan.get("goals", {}).get(gid, {})
        pct      = completion_pct(g_plan, wk_num) if is_active else 0
        bars     = goal_progress_bars(g_plan, quarter_key) if is_active else ""

        active_badge = ""
        if is_active:
            active_badge = (
                f'<span style="font-size:0.68em;background:#dcfce7;color:#166534;'
                f'font-weight:700;padding:2px 8px;border-radius:10px;margin-left:6px;">'
                f'Active Q</span>'
            )

        pct_bar = ""
        if is_active and wk_num > 1:
            pct_bar = (
                f'<div style="margin-top:8px;">'
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:0.72em;color:var(--ink-faint);margin-bottom:3px;">'
                f'<span>Week {wk_num} of 13</span><span>{pct}% complete</span></div>'
                f'<div style="height:5px;background:var(--border);border-radius:3px;">'
                f'<div style="height:5px;background:#22c55e;border-radius:3px;'
                f'width:{pct}%;transition:width 0.3s;"></div></div>'
                f'<div style="margin-top:4px;">{bars}</div>'
                f'</div>'
            )

        master_cards += f"""
<div id="goal-card-{escape(gid)}"
     style="border:2px solid {'#22c55e' if is_active else 'var(--border)'};
            border-radius:12px;padding:14px;margin-bottom:12px;
            background:{'#f0fdf4' if is_active else 'white'};">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;">
    <div style="flex:1;">
      <div style="font-size:0.72em;color:var(--ink-faint);margin-bottom:3px;">
        {icon} {escape(cat)}
      </div>
      <div style="font-weight:700;font-size:0.95em;color:var(--ink);">
        {title}{active_badge}
      </div>
      {f'<div style="font-size:0.78em;color:var(--ink-muted);margin-top:4px;font-style:italic;">{why}</div>' if why else ''}
      {f'<div style="font-size:0.75em;color:var(--ink-faint);margin-top:3px;">Metric: {metric}</div>' if metric else ''}
      {pct_bar}
    </div>
    <div style="display:flex;flex-direction:column;gap:6px;flex-shrink:0;">
      <button onclick="toggleGoalActive('{escape(gid)}', this)"
              data-active="{'true' if is_active else 'false'}"
              style="padding:6px 14px;font-size:0.78em;border-radius:8px;
                     font-family:inherit;cursor:pointer;font-weight:600;
                     background:{'#dcfce7' if is_active else 'var(--ink)'};
                     color:{'#166534' if is_active else 'var(--gold-light)'};
                     border:{'2px solid #22c55e' if is_active else 'none'};">
        {'✓ Selected' if is_active else '+ Select'}
      </button>
      <button onclick="showGoalSteps('{escape(gid)}')"
              style="padding:5px 10px;font-size:0.72em;border-radius:8px;
                     background:var(--parchment);color:var(--ink);
                     border:1px solid var(--border);font-family:inherit;cursor:pointer;">
        {'View steps' if is_active else 'Preview'}
      </button>
    </div>
  </div>

  <!-- Step plan (collapsible) -->
  <div id="steps-{escape(gid)}" style="display:none;margin-top:12px;
       border-top:1px solid var(--border-light);padding-top:12px;">
    <div style="font-size:0.72em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
                color:var(--ink-faint);margin-bottom:8px;">13-Week Plan</div>
    <div id="steps-content-{escape(gid)}">
      {_render_step_grid(gid, plan, wk_num)}
    </div>
    {('<button onclick="aiGenerateSteps(\'' + escape(gid) + '\')" style="margin-top:10px;width:100%;padding:9px;background:linear-gradient(135deg,#1c1610,#2a1e10);color:var(--gold-light);border:none;border-radius:8px;font-size:0.85em;font-family:inherit;cursor:pointer;font-weight:600;">\u2728 Generate 13-week plan with AI</button>') if api_key else ''}
  </div>
</div>"""

    # ── Add new goal form ────────────────────────────────────────────────────
    cat_opts = "".join(
        f'<option value="{escape(c)}">{escape(c)}</option>'
        for c in CATEGORIES
    )

    # ── AI reasoning panel ───────────────────────────────────────────────────
    ai_reasoning = escape(plan.get("ai_reasoning", ""))
    ai_panel = ""
    if api_key:
        ai_panel = f"""
<div class="card" style="margin-bottom:16px;background:linear-gradient(135deg,#1c1610,#2a1e10);color:var(--gold-light);">
  <div style="font-size:0.68em;font-weight:800;letter-spacing:.14em;text-transform:uppercase;
              color:rgba(201,164,74,0.7);margin-bottom:6px;">AI Goal Coach</div>
  <div style="font-size:0.85em;margin-bottom:12px;color:rgba(245,234,216,0.8);">
    Let AI review your master goals and suggest which 4\u20135 to focus on this quarter,
    with reasoning based on the liturgical season, your past progress, and what's realistic.
  </div>
  <button onclick="aiSuggestGoals()"
          style="width:100%;padding:10px;background:rgba(255,255,255,0.1);
                 color:var(--gold-light);border:1px solid rgba(201,164,74,0.4);
                 border-radius:10px;font-size:0.88em;font-weight:600;
                 font-family:inherit;cursor:pointer;">
    \u2728 Suggest goals for {escape(q_label)}
  </button>
  <div id="ai-suggest-loading" style="display:none;text-align:center;
       padding:12px;font-size:0.82em;color:rgba(245,234,216,0.6);">\u231b Thinking...</div>
  <div id="ai-suggest-result" style="display:none;margin-top:12px;padding:12px;
       background:rgba(255,255,255,0.05);border-radius:10px;font-size:0.88em;
       line-height:1.7;color:rgba(245,234,216,0.9);">
    {ai_reasoning}
  </div>
  {f'<div style="margin-top:8px;">{ai_reasoning}</div>' if ai_reasoning else ''}
</div>"""

    active_count = len(active_ids)
    count_color  = "#22c55e" if 4 <= active_count <= 5 else "#f59e0b" if active_count > 0 else "#9ca3af"

    plan_js = json.dumps(plan)
    master_js = json.dumps(master)

    body = top_nav() + render_status_message(status) + f"""
<div style="display:flex;align-items:flex-start;justify-content:space-between;
            flex-wrap:wrap;gap:8px;padding-top:4px;margin-bottom:16px;">
  <div>
    <div style="font-family:'Cormorant Garamond',Georgia,serif;
                font-size:2rem;font-weight:600;color:var(--ink);">
      Quarterly Goals
    </div>
    <div style="font-size:0.85em;color:var(--ink-muted);margin-top:2px;">
      {escape(q_label)} \u00b7 Week {wk_num} of 13
    </div>
  </div>
  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
    <span style="font-size:0.82em;font-weight:700;color:{count_color};">
      {active_count}/5 goals selected
    </span>
    <button onclick="saveActiveGoals()"
            style="padding:9px 18px;background:var(--ink);color:var(--gold-light);
                   border:none;border-radius:10px;font-size:0.85em;font-weight:700;
                   font-family:inherit;cursor:pointer;">Save selection</button>
  </div>
</div>

<div id="save-status" style="font-size:0.82em;color:#22c55e;min-height:18px;
     margin-bottom:8px;font-weight:600;"></div>

{ai_panel}

<!-- Master goal list -->
<div style="margin-bottom:20px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:12px;">
    Your Goals ({len(master)}/12)
  </div>
  {master_cards if master_cards else
   '<div class="card"><p class="small">No goals yet. Add your first goal below.</p></div>'}
</div>

<!-- Add goal form -->
<div class="card" style="margin-bottom:20px;">
  <div style="font-size:0.72em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
              color:var(--ink-faint);margin-bottom:12px;">Add a Goal</div>
  <form method="POST" action="/goal-add">
    <input type="hidden" name="quarter" value="{escape(quarter_key)}">
    <label style="font-size:0.75em;">Goal title</label>
    <input type="text" name="title" required placeholder="e.g. Daily Rosary as a family"
           style="margin-bottom:8px;">
    <label style="font-size:0.75em;">Category</label>
    <select name="category" style="margin-bottom:8px;">{cat_opts}</select>
    <label style="font-size:0.75em;">Why does this matter?</label>
    <input type="text" name="why" placeholder="Your motivation..."
           style="margin-bottom:8px;">
    <label style="font-size:0.75em;">Success metric</label>
    <input type="text" name="metric" placeholder="How will you know you succeeded?"
           style="margin-bottom:12px;">
    <button type="submit"
            style="padding:8px 18px;background:var(--ink);color:var(--gold-light);
                   border:none;border-radius:8px;font-family:inherit;font-size:0.85em;
                   cursor:pointer;font-weight:600;">Add goal</button>
  </form>
</div>

<!-- Quarter navigation -->
<div style="display:flex;gap:8px;flex-wrap:wrap;padding:8px 0;">
  <a href="/plan-year" style="font-size:0.82em;color:var(--brown);font-weight:700;text-decoration:none;">
    Annual overview \u2192
  </a>
  <span style="color:var(--border);">|</span>
  <a href="/plan-week" style="font-size:0.82em;color:var(--ink-muted);text-decoration:none;">
    Plan this week \u2192
  </a>
</div>

<script>
var _quarter = '{escape(quarter_key)}';
var _plan    = {plan_js};
var _master  = {master_js};
var _activeIds = {json.dumps(active_ids)};

function toggleGoalActive(gid, btn) {{
  var isActive = btn.dataset.active === 'true';
  if (!isActive && _activeIds.length >= 5) {{
    alert('You can only select up to 5 goals per quarter. Deselect one first.');
    return;
  }}
  if (isActive) {{
    _activeIds = _activeIds.filter(function(id) {{ return id !== gid; }});
    btn.dataset.active = 'false';
    btn.textContent = '+ Select';
    btn.style.background = 'var(--ink)';
    btn.style.color = 'var(--gold-light)';
    btn.style.border = 'none';
    var card = document.getElementById('goal-card-' + gid);
    if (card) {{
      card.style.borderColor = 'var(--border)';
      card.style.background = 'white';
    }}
  }} else {{
    _activeIds.push(gid);
    btn.dataset.active = 'true';
    btn.textContent = '\u2713 Selected';
    btn.style.background = '#dcfce7';
    btn.style.color = '#166534';
    btn.style.border = '2px solid #22c55e';
    var card = document.getElementById('goal-card-' + gid);
    if (card) {{
      card.style.borderColor = '#22c55e';
      card.style.background = '#f0fdf4';
    }}
  }}
  var countEl = document.querySelector('[style*="goals selected"]');
  if (countEl) countEl.textContent = _activeIds.length + '/5 goals selected';
}}

function showGoalSteps(gid) {{
  var el = document.getElementById('steps-' + gid);
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}}

function saveActiveGoals() {{
  fetch('/quarter-save-goals', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'quarter=' + encodeURIComponent(_quarter) +
          '&goal_ids=' + encodeURIComponent(JSON.stringify(_activeIds))
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    var el = document.getElementById('save-status');
    if (el) {{ el.textContent = 'Saved \u2713'; setTimeout(function(){{ el.textContent=''; }}, 2500); }}
  }});
}}

function aiSuggestGoals() {{
  var loading = document.getElementById('ai-suggest-loading');
  var result  = document.getElementById('ai-suggest-result');
  if (loading) loading.style.display = 'block';
  if (result)  result.style.display  = 'none';

  var payload = {{
    quarter:   _quarter,
    goals:     _master,
    active_ids: _activeIds,
  }};
  fetch('/ai-suggest-goals', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'data=' + encodeURIComponent(JSON.stringify(payload))
  }}).then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      if (loading) loading.style.display = 'none';
      if (result) {{
        result.style.display = 'block';
        result.innerHTML = (d.html || d.text || 'No suggestion returned.');
      }}
      // Auto-select suggested goals if returned
      if (d.suggested_ids && Array.isArray(d.suggested_ids)) {{
        d.suggested_ids.forEach(function(gid) {{
          if (!_activeIds.includes(gid)) {{
            var btn = document.querySelector('[onclick*="toggleGoalActive(\'' + gid + '\'"]');
            if (btn) toggleGoalActive(gid, btn);
          }}
        }});
      }}
    }}).catch(function() {{
      if (loading) loading.style.display = 'none';
      if (result) {{ result.style.display='block'; result.textContent='Error — check your API key in Settings.'; }}
    }});
}}

function aiGenerateSteps(gid) {{
  var goal = _master.find(function(g) {{ return g.id === gid; }});
  if (!goal) return;
  var contentEl = document.getElementById('steps-content-' + gid);
  if (contentEl) contentEl.innerHTML = '<p style="font-size:0.82em;color:var(--ink-faint);padding:8px 0;">\u231b Generating 13-week plan...</p>';

  fetch('/ai-generate-steps', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'quarter=' + encodeURIComponent(_quarter) +
          '&goal_id=' + encodeURIComponent(gid) +
          '&goal_data=' + encodeURIComponent(JSON.stringify(goal))
  }}).then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      if (d.html && contentEl) {{
        contentEl.innerHTML = d.html;
      }}
    }}).catch(function() {{
      if (contentEl) contentEl.innerHTML = '<p style="color:#ef4444;font-size:0.82em;">Error generating steps.</p>';
    }});
}}

function saveStepEdit(gid, week) {{
  var inp = document.getElementById('step-' + gid + '-' + week);
  if (!inp) return;
  fetch('/quarter-save-step', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
    body: 'quarter=' + encodeURIComponent(_quarter) +
          '&goal_id=' + encodeURIComponent(gid) +
          '&week=' + week +
          '&step=' + encodeURIComponent(inp.value)
  }});
}}
</script>
"""
    return html_page(f"Quarterly Goals \u00b7 {q_label}", body)


def _render_step_grid(goal_id: str, plan: dict, current_wk: int) -> str:
    """Render the 13-week step grid for a goal."""
    g_plan = plan.get("goals", {}).get(goal_id, {})
    steps    = g_plan.get("weekly_steps", {})
    checkins = g_plan.get("checkins", {})
    gid = escape(goal_id)

    if not steps:
        return '<p style="font-size:0.82em;color:var(--ink-faint);padding:4px 0;">No steps planned yet. Use AI to generate or add manually.</p>'

    rows = ""
    for w in range(1, 14):
        step   = steps.get(str(w), "")
        status = checkins.get(str(w), "")
        is_now = (w == current_wk)
        past   = w < current_wk

        status_btn = ""
        if past or is_now:
            for s, label in [("done","\u2713 Done"),("partial","\u223c Partial"),("skip","\u2715 Skip")]:
                active = status == s
                status_btn += (
                    f'<button onclick="recordCheckin(\'{gid}\',{w},\'{s}\')" '
                    f'style="padding:3px 8px;font-size:0.68em;border-radius:6px;'
                    f'font-family:inherit;cursor:pointer;margin-right:3px;'
                    f'background:{"' + CHECK_COLORS[s] + '" if active else "#f3f4f6"};'
                    f'color:{"white" if active else "#6b7280"};'
                    f'border:{"1.5px solid ' + CHECK_COLORS[s] + '" if active else "1px solid #e5e7eb"};">'
                    f'{label}</button>'
                )

        rows += (
            f'<div style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;'
            f'border-bottom:1px solid var(--border-light);'
            f'{"background:#fffbeb;border-radius:8px;padding:8px;" if is_now else ""}">'
            f'<div style="font-size:0.72em;font-weight:700;color:var(--ink-faint);'
            f'width:28px;flex-shrink:0;padding-top:5px;">W{w}</div>'
            f'<div style="flex:1;">'
            f'<input type="text" id="step-{gid}-{w}" value="{escape(step)}" '
            f'placeholder="Week {w} action..." '
            f'onblur="saveStepEdit(\'{gid}\',{w})" '
            f'style="width:100%;padding:5px 8px;font-size:0.82em;border-radius:6px;'
            f'border:1px solid var(--border-light);font-family:inherit;'
            f'{"font-weight:700;" if is_now else ""}">'
            f'<div style="margin-top:4px;">{status_btn}</div>'
            f'</div>'
            f'</div>'
        )

    rows += """
<script>
function recordCheckin(gid, week, status) {
  var qk = typeof _quarter !== 'undefined' ? _quarter : '';
  fetch('/quarter-checkin', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: 'quarter=' + encodeURIComponent(qk) +
          '&goal_id=' + encodeURIComponent(gid) +
          '&week=' + week + '&status=' + encodeURIComponent(status)
  }).then(function() {
    // Refresh button states
    document.querySelectorAll('[onclick*="recordCheckin(\\\'' + gid + '\\\''  + ')"]').forEach(function(b) {
      var s = b.getAttribute('onclick').match(/'([^']+)'\)$/);
      if (s) {
        var isActive = (s[1] === status);
        var colors = {done:'#22c55e', partial:'#f59e0b', skip:'#ef4444'};
        b.style.background = isActive ? (colors[s[1]] || '#e5e7eb') : '#f3f4f6';
        b.style.color = isActive ? 'white' : '#6b7280';
      }
    });
  });
}
</script>"""
    return rows