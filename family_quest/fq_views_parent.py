"""
fq_views_parent.py — Parent-facing views for Family Quest.
Phase 2: RPG — character/resource display, boss settings.
"""
from html import escape as _esc
from datetime import date

import fq_data as D
import fq_render as R


def _build_child_cards(xp_data: dict, today: str) -> str:
    """Build the per-child summary card HTML for the parent dashboard."""
    child_cards = ""
    for key in D.CHILDREN_KEYS:
        name    = D.CHILDREN_NAMES[key]
        emoji   = R.CHILD_EMOJI[key]
        colors  = R.CHILD_COLORS[key]
        state   = D._xp_state(xp_data, key)
        streak  = D.get_streak(key)
        char    = D.get_character(key)
        eq      = D.get_equipment(key)
        stamina = D.get_stamina(key)
        total   = state["total_xp"]
        coins   = state.get("coins", 0)
        crystals = state.get("crystals", 0)
        diamonds = state.get("diamonds", 0)
        lvl     = state["level"]
        nxt     = state["next_level"]
        pct     = state["progress_pct"]
        attack  = D.get_attack_stat(key)
        defense = D.get_defense_stat(key)

        quests_today = D.get_quests_for_child(key, today)
        completed    = sum(1 for q in quests_today if D.is_completed(q, key))
        total_q      = len(quests_today)
        next_label   = f"Next: {nxt['label']} at {nxt['xp_min']} XP" if nxt else "Max level!"

        cur_streak   = streak.get("current", 0)
        best_streak  = streak.get("best", 0)
        streak_color = "#dc2626" if cur_streak >= 7 else ("#d97706" if cur_streak >= 3 else "#9ca3af")
        streak_label = f"🔥 {cur_streak}" if cur_streak > 0 else "—"

        char_name  = char.get("name", "Fighter")
        char_emoji = char.get("emoji", "⚔️")

        # Equipment level summary
        eq_levels = "/".join(str(eq.get(s, 0)) for s in D.EQUIPMENT_SLOTS)

        child_cards += f"""
<div class="card" style="border-top:4px solid {colors['bg']};">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">
    <a href="/quest/board/{key}" style="text-decoration:none;">
      <div style="width:52px;height:52px;border-radius:50%;background:{colors['bg']};
                  display:flex;align-items:center;justify-content:center;
                  font-size:1.6em;flex-shrink:0;">
        {emoji}
      </div>
    </a>
    <div style="flex:1;min-width:0;">
      <div style="font-size:1.1em;font-weight:800;color:var(--ink);">
        <a href="/quest/board/{key}" style="color:inherit;text-decoration:none;">{_esc(name)}</a>
      </div>
      <div style="font-size:0.8em;color:var(--ink-muted);">Level {lvl['level']} — {_esc(lvl['label'])}</div>
      <div style="font-size:0.75em;color:var(--ink-muted);">{char_emoji} {_esc(char_name)} · ⚡{stamina}/{D.MAX_STAMINA}</div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:1.4em;font-weight:800;color:{colors['bg']};">{total}
        <span style="font-size:0.55em;font-weight:600;color:var(--ink-muted);">XP</span>
      </div>
      <div style="font-size:0.72em;color:var(--ink-muted);">{completed}/{total_q} quests today</div>
    </div>
  </div>
  <div style="margin-bottom:10px;">
    <div class="xp-bar-wrap">
      <div class="xp-bar-fill" style="width:{pct}%;background:{colors['bg']};"></div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:10px;">
    <div style="text-align:center;background:#fffbeb;border-radius:8px;padding:6px 4px;">
      <div style="font-size:1em;">🪙</div>
      <div style="font-size:0.85em;font-weight:800;color:#d97706;">{coins}</div>
    </div>
    <div style="text-align:center;background:#f0f9ff;border-radius:8px;padding:6px 4px;">
      <div style="font-size:1em;">💎</div>
      <div style="font-size:0.85em;font-weight:800;color:#0ea5e9;">{crystals}</div>
    </div>
    <div style="text-align:center;background:#f5f3ff;border-radius:8px;padding:6px 4px;">
      <div style="font-size:1em;">💠</div>
      <div style="font-size:0.85em;font-weight:800;color:#8b5cf6;">{diamonds}</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;font-size:0.72em;">
    <div style="color:var(--ink-muted);">{next_label}</div>
    <div style="color:{streak_color};font-weight:700;" title="Streak (best: {best_streak})">
      {streak_label} streak
    </div>
  </div>
  <div style="margin-top:8px;font-size:0.72em;color:var(--ink-muted);display:flex;gap:10px;">
    <span>⚔️ {attack} atk</span>
    <span>🛡️ {defense} def</span>
    <span>🎒 Eq: {eq_levels}</span>
  </div>
</div>"""
    return child_cards


def render_parent_dashboard(viewer: str) -> str:
    """Parent dashboard showing all children's XP, level, streak, resources, and character."""
    xp_data     = D.load_xp()
    today       = date.today().isoformat()
    child_cards = _build_child_cards(xp_data, today)

    all_quests_today = D.load_quests()
    synced_count = sum(1 for q in all_quests_today if q.get("date") == today and q.get("synced"))
    sync_pill = (
        f'<span style="font-size:0.75em;background:#e0f2fe;color:#0369a1;'
        f'border-radius:8px;padding:3px 10px;font-weight:700;">&#9889; {synced_count} synced from Sancta Familia</span>'
        if synced_count else ""
    )

    # Boss settings quick view
    boss_settings = D.load_boss_settings()
    diff_key = boss_settings.get("difficulty", "medium")
    diff = D.BOSS_DIFFICULTIES.get(diff_key, D.BOSS_DIFFICULTIES["medium"])
    boss_type_key = boss_settings.get("boss_type", "orc")
    boss_type_def = D.BOSS_TYPES.get(boss_type_key, D.BOSS_TYPES["orc"])
    available = boss_settings.get("available", True)
    exchange_rate = int(boss_settings.get("exchange_rate", 1))

    boss_status = f"""
<div class="card" style="margin-top:18px;border-color:{'#f59e0b' if available else '#e5e7eb'};">
  <div class="card-title">⚔️ Boss Battle Settings</div>
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
    <div style="font-size:2em;">{boss_type_def['emoji']}</div>
    <div>
      <div style="font-weight:700;">{boss_type_def['label']} · {diff['label']} <span style="color:{'#15803d' if available else '#9ca3af'};font-size:0.85em;">{'● Active' if available else '● Disabled'}</span></div>
      <div style="font-size:0.8em;color:var(--ink-muted);">{boss_type_def['description']} · HP {diff['hp']} · ⚡{diff['stamina_cost']}</div>
    </div>
  </div>
  <div style="font-size:0.78em;color:var(--ink-muted);margin-bottom:10px;">
    💰 Exchange rate: {exchange_rate}¢/coin · 100 coins = ${exchange_rate:.0f}.00 (parent payout)
  </div>
  <a href="/quest/boss-settings" class="btn btn-muted btn-sm">⚙️ Configure Boss</a>
</div>"""

    body = f"""
{R.topbar(viewer, True)}
<div class="fq-main">
  <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:4px;">
    <h1 style="margin-bottom:0;">Quest Dashboard</h1>
    {sync_pill}
  </div>
  <p style="color:var(--ink-muted);margin-bottom:24px;font-size:0.9em;">
    {date.today().strftime('%A, %B %-d, %Y')}
  </p>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
    {child_cards}
  </div>

  {boss_status}

  <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px;">
    <a href="/quest/quests" class="btn btn-primary">+ New Quest</a>
    <a href="/quest/rewards" class="btn btn-muted">&#127873; Rewards</a>
    <a href="/quest/boss-settings" class="btn btn-muted">⚔️ Boss Settings</a>
  </div>
</div>"""

    return R.html_page("Parent Dashboard", body)


def render_boss_settings_page(viewer: str, msg: str = "", err: str = "") -> str:
    settings = D.load_boss_settings()
    available = settings.get("available", True)
    current_diff = settings.get("difficulty", "medium")
    current_boss_type = settings.get("boss_type", "orc")
    exchange_rate = int(settings.get("exchange_rate", 1))

    alert = ""
    if msg:
        alert = f'<div class="alert alert-ok">&#10003; {_esc(msg)}</div>'
    elif err:
        alert = f'<div class="alert alert-err">{_esc(err)}</div>'

    diff_opts = ""
    for dk, dd in D.BOSS_DIFFICULTIES.items():
        sel = "selected" if dk == current_diff else ""
        diff_opts += f'<option value="{dk}" {sel}>{dd["emoji"]} {dd["label"]} — {dd["description"]}</option>'

    boss_type_opts = ""
    for btk, btd in D.BOSS_TYPES.items():
        sel = "selected" if btk == current_boss_type else ""
        boss_type_opts += f'<option value="{btk}" {sel}>{btd["emoji"]} {btd["label"]} — {btd["description"]}</option>'

    boss_table_rows = ""
    for dk, dd in D.BOSS_DIFFICULTIES.items():
        boss_table_rows += f"""
<tr style="{'background:#f0fdf4;' if dk == current_diff else ''}">
  <td style="padding:8px 10px;">{dd['emoji']} {dd['label']}</td>
  <td style="padding:8px 10px;text-align:center;">{dd['hp']}</td>
  <td style="padding:8px 10px;text-align:center;">⚡{dd['stamina_cost']}</td>
  <td style="padding:8px 10px;text-align:center;">🪙{dd['win_coins']} +{dd['win_xp']} XP</td>
  <td style="padding:8px 10px;text-align:center;">{dd['lose_chores']} chores</td>
</tr>"""

    form_html = f"""
<div class="card">
  <div class="card-title">⚙️ Configure Boss Battle</div>
  <form method="POST" action="/quest/boss-settings/save">
    <div class="form-row">
      <div class="form-group" style="margin-bottom:0;">
        <label>Boss Difficulty</label>
        <select name="difficulty">{diff_opts}</select>
      </div>
      <div class="form-group" style="margin-bottom:0;">
        <label>Boss Type (today's enemy)</label>
        <select name="boss_type">{boss_type_opts}</select>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group" style="margin-bottom:0;">
        <label>Boss Availability</label>
        <select name="available">
          <option value="1" {'selected' if available else ''}>✅ Available today</option>
          <option value="0" {'' if available else 'selected'}>❌ Disabled today</option>
        </select>
      </div>
      <div class="form-group" style="margin-bottom:0;">
        <label>Coin Exchange Rate (¢ per coin)</label>
        <input type="number" name="exchange_rate" value="{exchange_rate}" min="1" max="100"
               style="width:100%;"
               title="How many cents each coin is worth in real money. Parents track payouts manually.">
        <div style="font-size:0.75em;color:var(--ink-muted);margin-top:4px;">
          At {exchange_rate}¢/coin: 100 coins = ${exchange_rate:.0f}.00 (parents pay out manually)
        </div>
      </div>
    </div>
    <button type="submit" class="btn btn-primary" style="margin-top:10px;">Save Settings</button>
  </form>
</div>

<div class="card">
  <div class="card-title">📊 Boss Difficulty Reference</div>
  <table style="width:100%;border-collapse:collapse;font-size:0.82em;">
    <thead>
      <tr style="background:var(--parchment);font-weight:700;">
        <th style="padding:8px 10px;text-align:left;">Boss</th>
        <th style="padding:8px 10px;text-align:center;">HP</th>
        <th style="padding:8px 10px;text-align:center;">Stamina</th>
        <th style="padding:8px 10px;text-align:center;">Win Reward</th>
        <th style="padding:8px 10px;text-align:center;">Lose Penalty</th>
      </tr>
    </thead>
    <tbody>
      {boss_table_rows}
    </tbody>
  </table>
  <p style="font-size:0.78em;color:var(--ink-muted);margin-top:10px;">
    Attack stat (from character + equipment) multiplies hit damage.
    Sword level reduces quests needed per hit.
    Defense reduces penalty chores on loss.
    Completing daily quests restores stamina.
  </p>
</div>"""

    # Item award section
    child_checks = "".join(
        f'<label style="display:inline-flex;align-items:center;gap:6px;margin-right:14px;'
        f'font-size:0.88em;font-weight:600;cursor:pointer;">'
        f'<input type="checkbox" name="assigned_to" value="{k}" '
        f'style="width:auto;accent-color:{R.CHILD_COLORS[k]["bg"]};"> '
        f'{_esc(D.CHILDREN_NAMES[k])}</label>'
        for k in D.CHILDREN_KEYS
    )

    item_opts = "".join(
        f'<option value="{ik}">{iv["emoji"]} {iv["label"]} — {iv["description"]}</option>'
        for ik, iv in D.ITEMS.items()
    )

    item_award_form = f"""
<div class="card">
  <div class="card-title">🎁 Award Special Items</div>
  <p style="font-size:0.82em;color:var(--ink-muted);margin-bottom:14px;">
    Award single-use Battle Axe (doubles boss hits) or Hammer (1.5× mine yield) to children.
  </p>
  <form method="POST" action="/quest/boss-settings/award-item">
    <div class="form-group">
      <label>Item</label>
      <select name="item_key">{item_opts}</select>
    </div>
    <div class="form-group">
      <label>Award To</label>
      <div style="padding:8px 0;">{child_checks}</div>
    </div>
    <button type="submit" class="btn btn-primary">Award Item</button>
  </form>
</div>"""

    body = f"""
{R.topbar(viewer, True)}
<div class="fq-main">
  {alert}
  <h2>⚔️ Boss Battle Settings</h2>
  {form_html}
  {item_award_form}
</div>"""

    return R.html_page("Boss Settings", body)


def render_quests_page(viewer: str, msg: str = "", err: str = "") -> str:
    today   = date.today().isoformat()
    quests  = D.load_quests()

    alert = ""
    if msg:
        alert = f'<div class="alert alert-ok">&#10003; {_esc(msg)}</div>'
    elif err:
        alert = f'<div class="alert alert-err">{_esc(err)}</div>'

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

    item_opts_none = '<option value="">None</option>'
    item_opts_items = "".join(
        f'<option value="{ik}">{iv["emoji"]} {iv["label"]}</option>'
        for ik, iv in D.ITEMS.items()
    )

    form_html = f"""
<div class="card">
  <div class="card-title">&#9876; Create New Quest</div>
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
      <label>Item Reward (optional — given immediately on complete)</label>
      <select name="item_reward">{item_opts_none}{item_opts_items}</select>
    </div>
    <div class="form-group">
      <label>Assign To</label>
      <div style="padding:8px 0;">{child_checks}</div>
    </div>
    <button type="submit" class="btn btn-primary">Create Quest</button>
  </form>
</div>"""

    sync_card = f"""
<div class="card" style="background:linear-gradient(135deg,#f0f9ff,#e0f2fe);border-color:#7dd3fc;">
  <div class="card-title" style="color:#0369a1;">&#9889; Sync Today's Chores from Sancta Familia</div>
  <p style="font-size:0.88em;color:#0c4a6e;margin-bottom:14px;line-height:1.5;">
    Automatically pull today's chore assignments from each child's Day List and
    add them as daily quests here. Duplicates are skipped automatically.
  </p>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
    <button onclick="syncChores(this)" class="btn"
            style="background:#0369a1;color:white;">
      &#9889; Sync Now
    </button>
    <span id="sync-status" style="font-size:0.85em;color:#0369a1;font-weight:600;"></span>
  </div>
  <div id="sync-result" style="margin-top:12px;display:none;font-size:0.82em;line-height:1.6;"></div>
</div>

<script>
function syncChores(btn) {{
  btn.disabled = true;
  btn.textContent = '&#9889; Syncing...';
  document.getElementById('sync-status').textContent = '';
  document.getElementById('sync-result').style.display = 'none';

  fetch('/quest/sync-chores', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{}})
  }})
  .then(r => r.json())
  .then(data => {{
    btn.disabled = false;
    btn.innerHTML = '&#9889; Sync Now';

    var created = data.created || [];
    var skipped = data.skipped || [];
    var errors  = data.errors  || [];

    var statusEl = document.getElementById('sync-status');
    if (created.length > 0) {{
      statusEl.textContent = created.length + ' quest' + (created.length !== 1 ? 's' : '') + ' added!';
      statusEl.style.color = '#15803d';
    }} else {{
      statusEl.textContent = 'Nothing new to add.';
      statusEl.style.color = '#6b7280';
    }}

    var html = '';
    if (created.length > 0) {{
      html += '<div style="margin-bottom:6px;font-weight:700;color:#15803d;">&#10003; Added:</div>';
      created.forEach(function(c) {{ html += '<div style="color:#15803d;">· ' + c + '</div>'; }});
    }}
    if (skipped.length > 0) {{
      html += '<div style="margin-top:6px;font-weight:700;color:#6b7280;">Already exists:</div>';
      skipped.forEach(function(s) {{ html += '<div style="color:#9ca3af;">· ' + s + '</div>'; }});
    }}
    if (errors.length > 0) {{
      html += '<div style="margin-top:6px;font-weight:700;color:#b91c1c;">Errors:</div>';
      errors.forEach(function(e) {{ html += '<div style="color:#b91c1c;">· ' + e + '</div>'; }});
    }}
    var resultEl = document.getElementById('sync-result');
    resultEl.innerHTML = html;
    resultEl.style.display = html ? 'block' : 'none';

    if (created.length > 0) setTimeout(function() {{ location.reload(); }}, 2000);
  }})
  .catch(function() {{
    btn.disabled = false;
    btn.innerHTML = '&#9889; Sync Now';
    document.getElementById('sync-status').textContent = 'Error — try again.';
    document.getElementById('sync-status').style.color = '#b91c1c';
  }});
}}
</script>"""

    sorted_q = sorted(quests, key=lambda q: q.get("date", ""), reverse=True)

    rows = ""
    for q in sorted_q:
        tc       = R.TYPE_COLORS.get(q.get("type", "daily"), R.TYPE_COLORS["daily"])
        names    = ", ".join(D.CHILDREN_NAMES.get(c, c) for c in q.get("assigned_to", []))
        active   = q.get("active", True)
        done_by  = [k for k in q.get("assigned_to", []) if q.get("completions", {}).get(k)]
        done_names = ", ".join(D.CHILDREN_NAMES.get(k, k) for k in done_by)
        opacity  = "opacity:.55;" if not active else ""
        synced_tag = (
            '<span style="font-size:0.7em;background:#e0f2fe;color:#0369a1;'
            'border-radius:6px;padding:1px 6px;margin-left:4px;">&#9889; synced</span>'
            if q.get("synced") else ""
        )

        rows += f"""
<div class="card" style="padding:14px 16px;{opacity}">
  <div style="display:flex;align-items:flex-start;gap:12px;">
    <span style="font-size:1.3em;flex-shrink:0;">{tc['icon']}</span>
    <div style="flex:1;min-width:0;">
      <div style="font-weight:700;color:var(--ink);">{_esc(q.get('title',''))}{synced_tag}</div>
      <div style="font-size:0.78em;color:var(--ink-muted);margin-top:2px;">
        <span class="badge" style="background:{tc['bg']}22;color:{tc['bg']};">{tc['label']}</span>
        &nbsp;{_esc(names)}&nbsp;&#183;&nbsp;{q.get('date','')}
        &nbsp;&#183;&nbsp;<strong style="color:var(--gold-mid);">+{q.get('xp_value',0)} XP</strong>
        {'&nbsp;&#183;&nbsp;<span style="color:#15803d;">&#10003; Done by: ' + _esc(done_names) + '</span>' if done_by else ''}
        {'&nbsp;&#183;&nbsp;<span style="color:#9ca3af;">[inactive]</span>' if not active else ''}
      </div>
    </div>
    <div style="display:flex;gap:6px;flex-shrink:0;">
      {'<form method="POST" action="/quest/quests/deactivate" style="display:inline;"><input type="hidden" name="quest_id" value="' + q['id'] + '"><button type="submit" class="btn btn-muted btn-sm" title="Deactivate">Pause</button></form>' if active else ''}
      <form method="POST" action="/quest/quests/delete" style="display:inline;"
            onsubmit="return confirm('Remove this quest? No XP will be awarded.')">
        <input type="hidden" name="quest_id" value="{q['id']}">
        <button type="submit" class="btn btn-danger btn-sm">Remove (no XP)</button>
      </form>
    </div>
  </div>
</div>"""

    if not quests:
        rows = '<div class="card" style="text-align:center;color:var(--ink-muted);padding:32px;">No quests yet. Create one above or sync today\'s chores!</div>'

    body = f"""
{R.topbar(viewer, True)}
<div class="fq-main">
  {alert}
  {form_html}
  {sync_card}
  <h2>All Quests ({len(quests)})</h2>
  {rows}
</div>"""

    return R.html_page("Manage Quests", body)


def render_rewards_page(viewer: str, msg: str = "", err: str = "") -> str:
    rewards = D.load_rewards()

    alert = ""
    if msg:
        alert = f'<div class="alert alert-ok">&#10003; {_esc(msg)}</div>'
    elif err:
        alert = f'<div class="alert alert-err">{_esc(err)}</div>'

    milestone_rows = "".join(
        f'<div style="display:flex;justify-content:space-between;padding:5px 0;'
        f'border-bottom:1px solid var(--border-light);font-size:0.85em;">'
        f'<span>&#128293; {days}-day streak</span>'
        f'<span style="font-weight:700;color:#d97706;">+{xp} Bonus XP</span>'
        f'</div>'
        for days, xp in sorted(D.STREAK_MILESTONES.items())
    )
    streak_ref = f"""
<div class="card" style="background:linear-gradient(135deg,#fff7ed,#fef3c7);border-color:#fcd34d;margin-bottom:18px;">
  <div class="card-title" style="color:#92400e;">&#128293; Streak Milestone Bonuses</div>
  <p style="font-size:0.82em;color:#78350f;margin-bottom:10px;">
    Awarded automatically when a child completes all their Daily quests on consecutive days.
  </p>
  {milestone_rows}
</div>"""

    item_opts_none = '<option value="">None (coin reward only)</option>'
    item_opts_items = "".join(
        f'<option value="{ik}">{iv["emoji"]} {iv["label"]} — {iv["description"]}</option>'
        for ik, iv in D.ITEMS.items()
    )

    form_html = f"""
<div class="card">
  <div class="card-title">&#127873; Add Reward</div>
  <form method="POST" action="/quest/rewards/create">
    <div class="form-row">
      <div class="form-group" style="margin-bottom:0;">
        <label>Reward Label</label>
        <input type="text" name="label" placeholder="Ice cream night" required maxlength="120">
      </div>
      <div class="form-group" style="margin-bottom:0;">
        <label>🪙 Coin Price</label>
        <input type="number" name="coin_price" value="25" min="1" placeholder="25">
      </div>
    </div>
    <div class="form-row">
      <div class="form-group" style="margin-bottom:0;">
        <label>Unlock at XP (0 = any)</label>
        <input type="number" name="xp_threshold" value="0" min="0">
      </div>
      <div class="form-group" style="margin-bottom:0;">
        <label>Unlock at Level (0 = any)</label>
        <select name="level_threshold">
          <option value="0">Any level</option>
          <option value="2">Level 2 — Apprentice</option>
          <option value="3">Level 3 — Knight</option>
          <option value="4">Level 4 — Champion</option>
          <option value="5">Level 5 — Legend</option>
        </select>
      </div>
    </div>
    <div class="form-group">
      <label>Special Item Grant (optional)</label>
      <select name="item_reward">{item_opts_none}{item_opts_items}</select>
    </div>
    <button type="submit" class="btn btn-primary">Add Reward</button>
  </form>
</div>"""

    pending = D.get_pending_redemptions()
    redemption_rows = ""
    for red in pending:
        child_name = D.CHILDREN_NAMES.get(red.get("child",""), red.get("child","").title())
        redemption_rows += f"""
<div class="card" style="padding:14px 16px;border-left:4px solid #f59e0b;">
  <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
    <span style="font-size:1.4em;">🪙</span>
    <div style="flex:1;">
      <div style="font-weight:700;color:var(--ink);">{_esc(child_name)} wants: {_esc(red.get('reward_label',''))}</div>
      <div style="font-size:0.8em;color:var(--ink-muted);">
        Cost: 🪙{red.get('coin_price',0)} &nbsp;·&nbsp; Requested: {_esc(red.get('created_at',''))}
      </div>
    </div>
    <div style="display:flex;gap:8px;">
      <form method="POST" action="/quest/redemptions/approve" style="display:inline;">
        <input type="hidden" name="redemption_id" value="{red['id']}">
        <button type="submit" class="btn btn-primary btn-sm">✓ Approve</button>
      </form>
      <form method="POST" action="/quest/redemptions/reject" style="display:inline;"
            onsubmit="return confirm('Reject this request?')">
        <input type="hidden" name="redemption_id" value="{red['id']}">
        <button type="submit" class="btn btn-danger btn-sm">✗ Reject</button>
      </form>
    </div>
  </div>
</div>"""
    if not pending:
        redemption_rows = '<div style="color:var(--ink-muted);font-size:0.88em;padding:10px 0;">No pending requests.</div>'
    redemption_section = f"""
<div class="card" style="margin-bottom:18px;border-color:#f59e0b;">
  <div class="card-title" style="color:#92400e;">⏳ Pending Reward Requests ({len(pending)})</div>
  {redemption_rows}
</div>"""

    rows = ""
    for r in rewards:
        price = r.get("coin_price", 10)
        threshold = f"<span class='badge' style='background:#fef9c3;color:#713f12;'>🪙 {price} coins</span> "
        if r.get("xp_threshold"):
            threshold += f"<span class='badge' style='background:#fef3c7;color:#92400e;'>{r['xp_threshold']} XP unlock</span> "
        if r.get("level_threshold"):
            threshold += f"<span class='badge' style='background:#eff6ff;color:#1d4ed8;'>Level {r['level_threshold']} unlock</span> "
        if r.get("item_reward"):
            idef = D.ITEMS.get(r["item_reward"], {})
            threshold += f"<span class='badge' style='background:#f0fdf4;color:#15803d;'>{idef.get('emoji','')} {idef.get('label','Item')} included</span>"

        rows += f"""
<div class="card" style="padding:14px 16px;">
  <div style="display:flex;align-items:center;gap:12px;">
    <span style="font-size:1.3em;">&#127873;</span>
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
  {redemption_section}
  {streak_ref}
  {form_html}
  <h2>Rewards ({len(rewards)})</h2>
  {rows}
</div>"""

    return R.html_page("Rewards", body)
