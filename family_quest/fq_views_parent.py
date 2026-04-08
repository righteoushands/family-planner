"""
fq_views_parent.py — Parent-facing views for Family Quest.
"""
from html import escape as _esc
from datetime import date

import fq_data as D
import fq_render as R


def _build_child_cards(xp_data: dict, today: str) -> str:
    """Build the per-child summary card HTML for the parent dashboard."""
    child_cards = ""
    for key in D.CHILDREN_KEYS:
        name   = D.CHILDREN_NAMES[key]
        emoji  = R.CHILD_EMOJI[key]
        colors = R.CHILD_COLORS[key]
        state  = D._xp_state(xp_data, key)
        total  = state["total_xp"]
        lvl    = state["level"]
        nxt    = state["next_level"]
        pct    = state["progress_pct"]

        quests_today = D.get_quests_for_child(key, today)
        completed    = sum(1 for q in quests_today if D.is_completed(q, key))
        total_q      = len(quests_today)
        next_label   = f"Next: {nxt['label']} at {nxt['xp_min']} XP" if nxt else "Max level!"

        child_cards += f"""
<div class="card" style="border-top:4px solid {colors['bg']};">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">
    <div style="width:52px;height:52px;border-radius:50%;background:{colors['bg']};
                display:flex;align-items:center;justify-content:center;
                font-size:1.6em;flex-shrink:0;">
      {emoji}
    </div>
    <div style="flex:1;min-width:0;">
      <div style="font-size:1.1em;font-weight:800;color:var(--ink);">{_esc(name)}</div>
      <div style="font-size:0.8em;color:var(--ink-muted);">Level {lvl['level']} — {_esc(lvl['label'])}</div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:1.4em;font-weight:800;color:{colors['bg']};">{total}
        <span style="font-size:0.55em;font-weight:600;color:var(--ink-muted);">XP</span>
      </div>
      <div style="font-size:0.72em;color:var(--ink-muted);">{completed}/{total_q} quests today</div>
    </div>
  </div>
  <div style="margin-bottom:6px;">
    <div class="xp-bar-wrap">
      <div class="xp-bar-fill" style="width:{pct}%;background:{colors['bg']};"></div>
    </div>
  </div>
  <div style="font-size:0.72em;color:var(--ink-muted);text-align:right;">{next_label}</div>
</div>"""
    return child_cards


def render_parent_dashboard(viewer: str) -> str:
    """Parent dashboard showing all children's XP, level, and today's quest progress."""
    xp_data     = D.load_xp()
    today       = date.today().isoformat()
    child_cards = _build_child_cards(xp_data, today)

    body = f"""
{R.topbar(viewer, True)}
<div class="fq-main">
  <h1 style="margin-bottom:4px;">Quest Dashboard</h1>
  <p style="color:var(--ink-muted);margin-bottom:24px;font-size:0.9em;">
    {date.today().strftime('%A, %B %-d, %Y')}
  </p>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
    {child_cards}
  </div>

  <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;">
    <a href="/quest/quests" class="btn btn-primary">+ New Quest</a>
    <a href="/quest/rewards" class="btn btn-muted">🎁 Rewards</a>
  </div>
</div>"""

    return R.html_page("Parent Dashboard", body)


def render_quests_page(viewer: str, msg: str = "", err: str = "") -> str:
    today   = date.today().isoformat()
    quests  = D.load_quests()

    alert = ""
    if msg:
        alert = f'<div class="alert alert-ok">✓ {_esc(msg)}</div>'
    elif err:
        alert = f'<div class="alert alert-err">{_esc(err)}</div>'

    # ── Quest creation form ─────────────────────────────────────────────────────
    type_opts = "".join(
        f'<option value="{t}">{R.TYPE_COLORS[t]["label"]}</option>'
        for t in D.QUEST_TYPES
    )

    child_checks = "".join(
        f'<label style="display:inline-flex;align-items:center;gap:6px;margin-right:14px;'
        f'font-size:0.88em;font-weight:600;cursor:pointer;">'
        f'<input type="checkbox" name="assigned_to" value="{k}" '
        f'style="width:auto;accent-color:{R.CHILD_COLORS[k]["bg"]};"> '
        f'{_esc(D.CHILDREN_NAMES[k])}</label>'
        for k in D.CHILDREN_KEYS
    )

    form_html = f"""
<div class="card">
  <div class="card-title">⚔️ Create New Quest</div>
  <form method="POST" action="/quest/quests/create">
    <div class="form-row">
      <div class="form-group" style="margin-bottom:0;">
        <label>Quest Title</label>
        <input type="text" name="title" placeholder="Make your bed" required maxlength="120">
      </div>
      <div class="form-group" style="margin-bottom:0;">
        <label>Type</label>
        <select name="type">{type_opts}</select>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group" style="margin-bottom:0;">
        <label>XP Reward</label>
        <input type="number" name="xp_value" value="10" min="1" max="500">
      </div>
      <div class="form-group" style="margin-bottom:0;">
        <label>Date</label>
        <input type="date" name="date" value="{today}">
      </div>
    </div>
    <div class="form-group">
      <label>Assign To</label>
      <div style="padding:8px 0;">{child_checks}</div>
    </div>
    <button type="submit" class="btn btn-primary">Create Quest</button>
  </form>
</div>"""

    # ── Quest list ──────────────────────────────────────────────────────────────
    sorted_q = sorted(quests, key=lambda q: q.get("date", ""), reverse=True)

    rows = ""
    for q in sorted_q:
        tc       = R.TYPE_COLORS.get(q.get("type", "daily"), R.TYPE_COLORS["daily"])
        names    = ", ".join(D.CHILDREN_NAMES.get(c, c) for c in q.get("assigned_to", []))
        active   = q.get("active", True)
        done_by  = [k for k in q.get("assigned_to", []) if q.get("completions", {}).get(k)]
        done_names = ", ".join(D.CHILDREN_NAMES.get(k, k) for k in done_by)
        opacity  = "opacity:.55;" if not active else ""

        rows += f"""
<div class="card" style="padding:14px 16px;{opacity}">
  <div style="display:flex;align-items:flex-start;gap:12px;">
    <span style="font-size:1.3em;flex-shrink:0;">{tc['icon']}</span>
    <div style="flex:1;min-width:0;">
      <div style="font-weight:700;color:var(--ink);">{_esc(q.get('title',''))}</div>
      <div style="font-size:0.78em;color:var(--ink-muted);margin-top:2px;">
        <span class="badge" style="background:{tc['bg']}22;color:{tc['bg']};">{tc['label']}</span>
        &nbsp;{_esc(names)}&nbsp;·&nbsp;{q.get('date','')}
        &nbsp;·&nbsp;<strong style="color:var(--gold-mid);">+{q.get('xp_value',0)} XP</strong>
        {'&nbsp;·&nbsp;<span style="color:#15803d;">✓ Done by: ' + _esc(done_names) + '</span>' if done_by else ''}
        {'&nbsp;·&nbsp;<span style="color:#9ca3af;">[inactive]</span>' if not active else ''}
      </div>
    </div>
    <div style="display:flex;gap:6px;flex-shrink:0;">
      {'<form method="POST" action="/quest/quests/deactivate" style="display:inline;"><input type="hidden" name="quest_id" value="' + q['id'] + '"><button type="submit" class="btn btn-muted btn-sm" title="Deactivate">Pause</button></form>' if active else ''}
      <form method="POST" action="/quest/quests/delete" style="display:inline;"
            onsubmit="return confirm('Delete this quest?')">
        <input type="hidden" name="quest_id" value="{q['id']}">
        <button type="submit" class="btn btn-danger btn-sm">Delete</button>
      </form>
    </div>
  </div>
</div>"""

    if not quests:
        rows = '<div class="card" style="text-align:center;color:var(--ink-muted);padding:32px;">No quests yet. Create one above!</div>'

    body = f"""
{R.topbar(viewer, True)}
<div class="fq-main">
  {alert}
  {form_html}
  <h2>All Quests ({len(quests)})</h2>
  {rows}
</div>"""

    return R.html_page("Manage Quests", body)


def render_rewards_page(viewer: str, msg: str = "", err: str = "") -> str:
    rewards = D.load_rewards()

    alert = ""
    if msg:
        alert = f'<div class="alert alert-ok">✓ {_esc(msg)}</div>'
    elif err:
        alert = f'<div class="alert alert-err">{_esc(err)}</div>'

    form_html = """
<div class="card">
  <div class="card-title">🎁 Add Reward</div>
  <form method="POST" action="/quest/rewards/create">
    <div class="form-row">
      <div class="form-group" style="margin-bottom:0;">
        <label>Reward Label</label>
        <input type="text" name="label" placeholder="Ice cream night" required maxlength="120">
      </div>
      <div class="form-group" style="margin-bottom:0;">
        <label>Unlock at XP (0 = any)</label>
        <input type="number" name="xp_threshold" value="0" min="0">
      </div>
    </div>
    <div class="form-group">
      <label>Unlock at Level (0 = any)</label>
      <select name="level_threshold">
        <option value="0">Any level</option>
        <option value="2">Level 2 — Apprentice</option>
        <option value="3">Level 3 — Knight</option>
        <option value="4">Level 4 — Champion</option>
        <option value="5">Level 5 — Legend</option>
      </select>
    </div>
    <button type="submit" class="btn btn-primary">Add Reward</button>
  </form>
</div>"""

    rows = ""
    for r in rewards:
        threshold = ""
        if r.get("xp_threshold"):
            threshold += f"<span class='badge' style='background:#fef3c7;color:#92400e;'>{r['xp_threshold']} XP</span> "
        if r.get("level_threshold"):
            threshold += f"<span class='badge' style='background:#eff6ff;color:#1d4ed8;'>Level {r['level_threshold']}</span>"
        if not threshold:
            threshold = "<span style='color:var(--ink-muted);font-size:0.82em;'>No threshold</span>"

        rows += f"""
<div class="card" style="padding:14px 16px;">
  <div style="display:flex;align-items:center;gap:12px;">
    <span style="font-size:1.3em;">🎁</span>
    <div style="flex:1;">
      <div style="font-weight:700;color:var(--ink);">{_esc(r.get('label',''))}</div>
      <div style="margin-top:4px;">{threshold}</div>
    </div>
    <form method="POST" action="/quest/rewards/delete"
          onsubmit="return confirm('Remove this reward?')">
      <input type="hidden" name="reward_id" value="{r['id']}">
      <button type="submit" class="btn btn-danger btn-sm">Remove</button>
    </form>
  </div>
</div>"""

    if not rewards:
        rows = '<div class="card" style="text-align:center;color:var(--ink-muted);padding:32px;">No rewards yet. Add one above!</div>'

    body = f"""
{R.topbar(viewer, True)}
<div class="fq-main">
  {alert}
  {form_html}
  <h2>Rewards ({len(rewards)})</h2>
  {rows}
</div>"""

    return R.html_page("Rewards", body)
