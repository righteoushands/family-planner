"""
fq_views_child.py — Child-facing quest board for Family Quest.
Designed for age-flexibility: big tap targets, colorful, game-like.
Phase 2: Full RPG — characters, resources, boss battles, mine runs, equipment.
"""
from html import escape as _esc
from datetime import date

import fq_data as D
import fq_render as R


def render_child_board(child_key: str, viewer: str) -> str:
    today    = date.today().isoformat()
    quests   = D.get_quests_for_child(child_key, today)
    state    = D.get_child_xp_state(child_key)
    rewards  = D.load_rewards()
    streak   = D.get_streak(child_key)
    char     = D.get_character(child_key)
    eq       = D.get_equipment(child_key)
    inv      = D.get_inventory(child_key)
    stamina  = D.get_stamina(child_key)
    attack   = D.get_attack_stat(child_key)
    defense  = D.get_defense_stat(child_key)
    health   = D.get_health_stat(child_key)
    active_mine = D.get_active_mine(child_key)
    boss_settings = D.load_boss_settings()

    name    = D.CHILDREN_NAMES.get(child_key, child_key.title())
    emoji   = R.CHILD_EMOJI.get(child_key, "⭐")
    colors  = R.CHILD_COLORS.get(child_key, {"bg": "#1f2937", "light": "#f9fafb", "text": "#fff"})
    total   = state["total_xp"]
    coins   = state.get("coins", 0)
    crystals = state.get("crystals", 0)
    diamonds = state.get("diamonds", 0)
    lvl     = state["level"]
    nxt     = state["next_level"]
    pct     = state["progress_pct"]

    is_self = (viewer == child_key)
    from fq_auth import is_parent
    can_complete = is_self or is_parent(viewer)

    # ── Streak display ──────────────────────────────────────────────────────────
    cur_streak  = streak.get("current", 0)
    best_streak = streak.get("best", 0)

    streak_html = f"""
<div style="display:flex;align-items:center;gap:6px;margin-top:10px;
            background:rgba(255,255,255,.15);border-radius:10px;
            padding:7px 12px;justify-content:space-between;">
  <div style="display:flex;align-items:center;gap:6px;">
    <span style="font-size:1.3em;">🔥</span>
    <div>
      <div id="streak-count" style="font-size:1em;font-weight:800;color:white;line-height:1;">
        {cur_streak} day{'s' if cur_streak != 1 else ''} streak
      </div>
      <div style="font-size:0.65em;opacity:.75;">Best: {best_streak}</div>
    </div>
  </div>
  <div style="font-size:0.7em;opacity:.7;text-align:right;">
    {'🔥 On fire!' if cur_streak >= 7 else ('Keep it up!' if cur_streak >= 3 else ('Start your streak!' if cur_streak == 0 else 'Building...'))}
  </div>
</div>"""

    # ── Stamina bar ─────────────────────────────────────────────────────────────
    stamina_pct = int(stamina * 100 / D.MAX_STAMINA)
    stamina_color = "#22c55e" if stamina >= 7 else ("#f59e0b" if stamina >= 4 else "#ef4444")
    stamina_dots = "".join(
        f'<span style="font-size:1em;opacity:{"1" if i < stamina else "0.2"};">⚡</span>'
        for i in range(D.MAX_STAMINA)
    )
    stamina_html = f"""
<div style="background:rgba(255,255,255,.12);border-radius:10px;padding:8px 12px;margin-top:8px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
    <span style="font-size:0.75em;font-weight:700;color:white;opacity:.85;">⚡ Stamina</span>
    <span id="stamina-count" style="font-size:0.75em;font-weight:800;color:white;">{stamina}/{D.MAX_STAMINA}</span>
  </div>
  <div style="display:flex;gap:3px;flex-wrap:wrap;" id="stamina-dots">
    {stamina_dots}
  </div>
</div>"""

    # ── Header card ────────────────────────────────────────────────────────────
    next_line = (
        f"<div style='font-size:0.82em;color:#e5e7eb;margin-top:2px;'>"
        f"{nxt['xp_min'] - total} XP to Level {nxt['level']} — {_esc(nxt['label'])}"
        f"</div>"
    ) if nxt else "<div style='font-size:0.82em;color:#f9d77e;margin-top:2px;'>Max level reached! 🏆</div>"

    header = f"""
<div style="background:{colors['bg']};border-radius:20px;padding:22px 20px 20px;
            color:white;margin-bottom:18px;position:relative;overflow:hidden;">
  <div style="position:absolute;top:-20px;right:-10px;font-size:6em;opacity:.12;line-height:1;">{emoji}</div>
  <div style="display:flex;align-items:center;gap:14px;position:relative;">
    <div style="width:60px;height:60px;border-radius:50%;background:rgba(255,255,255,.2);
                display:flex;align-items:center;justify-content:center;
                font-size:1.9em;flex-shrink:0;">{emoji}</div>
    <div style="flex:1;min-width:0;">
      <div style="font-size:1.2em;font-weight:800;">{_esc(name)}'s Quest Board</div>
      <div style="font-size:0.85em;opacity:.85;">Level {lvl['level']} — {_esc(lvl['label'])}</div>
      {next_line}
    </div>
    <div style="text-align:right;flex-shrink:0;">
      <div id="xp-total" style="font-size:2em;font-weight:900;line-height:1;">{total}</div>
      <div style="font-size:0.7em;opacity:.8;letter-spacing:.08em;text-transform:uppercase;">XP</div>
    </div>
  </div>
  <div style="margin-top:14px;">
    <div style="display:flex;justify-content:space-between;font-size:0.72em;opacity:.8;margin-bottom:5px;">
      <span>Level {lvl['level']}</span>
      <span>{'Level ' + str(nxt['level']) if nxt else '★ Max'}</span>
    </div>
    <div class="xp-bar-wrap" style="height:12px;">
      <div id="xp-bar" class="xp-bar-fill"
           style="width:{pct}%;background:rgba(255,255,255,.7);"></div>
    </div>
  </div>
  {streak_html}
  {stamina_html}
</div>"""

    # ── Resources bar ───────────────────────────────────────────────────────────
    resources_html = f"""
<div class="card" style="padding:14px 16px;margin-bottom:18px;">
  <div style="display:flex;gap:0;justify-content:space-around;text-align:center;">
    <div>
      <div style="font-size:1.6em;">🪙</div>
      <div id="coin-total" style="font-size:1.3em;font-weight:900;color:#d97706;">{coins}</div>
      <div style="font-size:0.68em;color:var(--ink-muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Coins</div>
    </div>
    <div style="width:1px;background:var(--border-light);"></div>
    <div>
      <div style="font-size:1.6em;">💎</div>
      <div id="crystal-total" style="font-size:1.3em;font-weight:900;color:#0ea5e9;">{crystals}</div>
      <div style="font-size:0.68em;color:var(--ink-muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Crystals</div>
    </div>
    <div style="width:1px;background:var(--border-light);"></div>
    <div>
      <div style="font-size:1.6em;">💠</div>
      <div id="diamond-total" style="font-size:1.3em;font-weight:900;color:#8b5cf6;">{diamonds}</div>
      <div style="font-size:0.68em;color:var(--ink-muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Diamonds</div>
    </div>
  </div>
</div>"""

    # ── Character panel ─────────────────────────────────────────────────────────
    char_key      = char.get("key", "fighter")
    char_name     = char.get("name", "Fighter")
    char_emoji    = char.get("emoji", "⚔️")
    char_desc     = char.get("description", "")
    char_special  = char.get("special", "")

    attack_pct  = min(100, int(attack * 5))
    defense_pct = min(100, int(defense * 5))
    health_pct  = min(100, int(health * 100 / 200))

    char_options = ""
    for ck, cd in D.CHARACTERS.items():
        selected = "selected" if ck == char_key else ""
        char_options += f'<option value="{ck}" {selected}>{cd["emoji"]} {cd["name"]}</option>'

    character_panel = f"""
<div class="card" style="margin-bottom:18px;">
  <div class="card-title">{char_emoji} Character</div>
  <div style="display:flex;align-items:center;gap:14px;margin-bottom:14px;">
    <div style="width:56px;height:56px;border-radius:50%;background:{colors['bg']};
                display:flex;align-items:center;justify-content:center;font-size:1.8em;flex-shrink:0;">
      {char_emoji}
    </div>
    <div style="flex:1;">
      <div style="font-weight:800;font-size:1.05em;">{_esc(char_name)}</div>
      <div style="font-size:0.78em;color:var(--ink-muted);margin-top:2px;">{_esc(char_desc)}</div>
      <div style="font-size:0.72em;color:#7c3aed;margin-top:3px;font-style:italic;">✨ {_esc(char_special)}</div>
    </div>
  </div>
  <div style="margin-bottom:12px;">
    <div style="display:flex;justify-content:space-between;font-size:0.78em;font-weight:700;margin-bottom:4px;">
      <span>⚔️ Attack</span><span style="color:#dc2626;">{attack}</span>
    </div>
    <div class="xp-bar-wrap" style="height:8px;">
      <div class="xp-bar-fill" style="width:{attack_pct}%;background:#dc2626;"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:0.78em;font-weight:700;margin-top:8px;margin-bottom:4px;">
      <span>🛡️ Defense</span><span style="color:#2563eb;">{defense}</span>
    </div>
    <div class="xp-bar-wrap" style="height:8px;">
      <div class="xp-bar-fill" style="width:{defense_pct}%;background:#2563eb;"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:0.78em;font-weight:700;margin-top:8px;margin-bottom:4px;">
      <span>❤️ Health</span><span style="color:#16a34a;">{health}</span>
    </div>
    <div class="xp-bar-wrap" style="height:8px;">
      <div class="xp-bar-fill" style="width:{health_pct}%;background:#16a34a;"></div>
    </div>
  </div>
  {'<form style="display:flex;gap:8px;align-items:center;"><select id="char-select" style="flex:1;font-size:0.85em;padding:7px 10px;">' + char_options + '</select><button type="button" onclick="changeCharacter()" class="btn btn-muted btn-sm">Switch</button></form>' if is_self or is_parent(viewer) else ''}
</div>"""

    # ── Equipment panel ─────────────────────────────────────────────────────────
    eq_slots_html = ""
    for slot_key, slot_def in D.EQUIPMENT_SLOTS.items():
        level     = eq.get(slot_key, 0)
        max_level = slot_def["max_level"]
        slot_label = slot_def["label"]
        slot_emoji = slot_def["emoji"]
        bonus_val  = slot_def["bonuses"][level]
        stat_label = slot_def["stat"].title()

        if level < max_level:
            next_cost  = slot_def["upgrade_costs"][level]
            c_cost = next_cost.get("crystals", 0)
            d_cost = next_cost.get("diamonds", 0)
            can_upgrade = (crystals >= c_cost and diamonds >= d_cost)
            upgrade_cost_str = f"💎{c_cost}" + (f" 💠{d_cost}" if d_cost else "")
            upgrade_btn = f"""<button onclick="upgradeEquipment('{slot_key}', this)"
              class="btn btn-sm {'btn-primary' if can_upgrade else 'btn-muted'}"
              {'disabled' if not can_upgrade else ''}
              title="Cost: {upgrade_cost_str}">
              ↑ {upgrade_cost_str}
            </button>"""
        else:
            upgrade_btn = '<span style="font-size:0.72em;color:#15803d;font-weight:700;">★ MAX</span>'

        level_dots = "".join(
            f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            f'margin-right:2px;background:{"#d97706" if i < level else "#e5e7eb"};"></span>'
            for i in range(max_level)
        )

        eq_slots_html += f"""
<div style="display:flex;align-items:center;gap:10px;padding:10px 0;
            border-bottom:1px solid var(--border-light);" id="eq-{slot_key}">
  <span style="font-size:1.4em;width:32px;text-align:center;">{slot_emoji}</span>
  <div style="flex:1;">
    <div style="font-weight:700;font-size:0.9em;">{_esc(slot_label)} <span style="color:var(--ink-muted);font-weight:400;font-size:0.85em;">Lv.{level}</span></div>
    <div style="margin-top:3px;">{level_dots}</div>
    <div style="font-size:0.72em;color:var(--ink-muted);">+{bonus_val} {stat_label}</div>
  </div>
  {upgrade_btn}
</div>"""

    # Single-use items
    items_html = ""
    for item_key, item_def in D.ITEMS.items():
        count = inv.get(item_key, 0)
        if count > 0:
            items_html += f"""
<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--border-light);">
  <span style="font-size:1.4em;">{item_def['emoji']}</span>
  <div style="flex:1;">
    <div style="font-weight:700;font-size:0.88em;">{_esc(item_def['label'])} <span style="color:#15803d;font-weight:800;">×{count}</span></div>
    <div style="font-size:0.72em;color:var(--ink-muted);">{_esc(item_def['description'])}</div>
  </div>
</div>"""
    if not items_html:
        items_html = '<div style="font-size:0.82em;color:var(--ink-muted);padding:8px 0;">No special items — earn them from side quests!</div>'

    equipment_panel = f"""
<div class="card" style="margin-bottom:18px;">
  <div class="card-title">🎒 Equipment</div>
  {eq_slots_html}
  <div style="margin-top:14px;">
    <div style="font-size:0.82em;font-weight:700;color:var(--ink-muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:.04em;">Special Items</div>
    {items_html}
  </div>
</div>"""

    # ── Quest sections ──────────────────────────────────────────────────────────
    grouped: dict = {t: [] for t in D.QUEST_TYPES}
    for q in quests:
        t = q.get("type", "daily")
        grouped.setdefault(t, []).append(q)

    quest_sections = ""
    total_done = 0
    total_quests = len(quests)

    for qt in D.QUEST_TYPES:
        qlist = grouped.get(qt, [])
        if not qlist:
            continue
        tc = R.TYPE_COLORS[qt]
        cards = ""
        for q in qlist:
            done = D.is_completed(q, child_key)
            if done:
                total_done += 1
            xp_val = q.get("xp_value", 0)
            synced_badge = (
                '<span style="font-size:0.65em;background:#e0f2fe;color:#0369a1;'
                'border-radius:6px;padding:1px 6px;margin-left:4px;">⚡ synced</span>'
                if q.get("synced") else ""
            )

            if can_complete and not done:
                action_btn = f"""
<button onclick="completeQuest('{q['id']}', this)"
  style="width:52px;height:52px;border-radius:50%;border:3px solid {tc['bg']};
         background:white;color:{tc['bg']};font-size:1.3em;cursor:pointer;
         flex-shrink:0;transition:all .2s;display:flex;align-items:center;
         justify-content:center;"
  title="Complete quest">&#9675;</button>"""
            elif done:
                action_btn = f"""
<div style="width:52px;height:52px;border-radius:50%;background:{tc['bg']};
            display:flex;align-items:center;justify-content:center;
            font-size:1.3em;flex-shrink:0;">&#10003;</div>"""
            else:
                action_btn = f"""
<div style="width:52px;height:52px;border-radius:50%;border:3px solid #e5e7eb;
            display:flex;align-items:center;justify-content:center;
            font-size:1em;flex-shrink:0;color:#9ca3af;">&#9675;</div>"""

            done_style = "opacity:.5;text-decoration:line-through;" if done else ""
            cards += f"""
<div class="card" style="padding:14px 16px;{done_style}">
  <div style="display:flex;align-items:center;gap:14px;">
    {action_btn}
    <div style="flex:1;min-width:0;">
      <div style="font-size:1em;font-weight:700;color:var(--ink);">
        {_esc(q.get('title',''))}{synced_badge}
      </div>
      <div style="margin-top:4px;">
        <span class="badge" style="background:{tc['bg']}22;color:{tc['bg']};font-size:0.75em;">
          {tc['icon']} {tc['label']}
        </span>
        <span style="margin-left:8px;font-size:0.8em;font-weight:700;color:{'#15803d' if done else '#d97706'};">
          {'&#10003; +' if done else '+'}{xp_val} XP
        </span>
      </div>
    </div>
  </div>
</div>"""

        quest_sections += f"""
<div style="margin-bottom:22px;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
    <span style="font-size:1.4em;">{tc['icon']}</span>
    <h2 style="margin-bottom:0;font-size:1em;font-weight:800;color:{tc['bg']};
               text-transform:uppercase;letter-spacing:.06em;">{tc['label']} Quests</h2>
    <span class="badge" style="background:{tc['bg']};color:white;">
      {sum(1 for q in qlist if D.is_completed(q, child_key))}/{len(qlist)}
    </span>
  </div>
  {cards}
</div>"""

    if not quests:
        quest_sections = """
<div class="card" style="text-align:center;padding:40px 20px;">
  <div style="font-size:3em;margin-bottom:12px;">&#9939;</div>
  <div style="font-size:1.1em;font-weight:700;color:var(--ink);margin-bottom:6px;">No quests assigned for today</div>
  <div style="font-size:0.88em;color:var(--ink-muted);">Check back later — your parents are preparing your quests!</div>
</div>"""

    # ── Progress summary ────────────────────────────────────────────────────────
    if total_quests > 0:
        prog_pct = int(total_done * 100 / total_quests)
        summary = f"""
<div class="card" style="background:linear-gradient(135deg,#f9fafb,#f3f4f6);border-color:#e5e7eb;margin-bottom:18px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <div style="font-weight:800;color:var(--ink);">Today's Progress</div>
    <div style="font-weight:800;color:{colors['bg']};">{total_done}/{total_quests}</div>
  </div>
  <div class="xp-bar-wrap" style="height:14px;">
    <div class="xp-bar-fill" style="width:{prog_pct}%;background:{colors['bg']};"></div>
  </div>
  {'<div style="text-align:center;margin-top:10px;font-size:1.2em;">&#127881; All done! You earned 3 stamina ⚡</div>' if total_done == total_quests and total_quests > 0 else ''}
</div>"""
    else:
        summary = ""

    # ── Boss Battle / Mine Run panel ─────────────────────────────────────────────
    difficulty_key = D.get_active_difficulty()
    diff = D.BOSS_DIFFICULTIES.get(difficulty_key, D.BOSS_DIFFICULTIES["medium"])
    boss_type_key = boss_settings.get("boss_type", "orc")
    boss_type_def = D.BOSS_TYPES.get(boss_type_key, D.BOSS_TYPES["orc"])
    boss_available = boss_settings.get("available", True)

    boss_stamina_needed = diff["stamina_cost"]
    can_boss = boss_available and stamina >= boss_stamina_needed and total_done > 0

    axe_count    = inv.get("battle_axe", 0)
    hammer_count = inv.get("hammer", 0)
    has_axe    = axe_count > 0
    has_hammer = hammer_count > 0

    # Active mine display
    active_mine_html = ""
    if active_mine:
        mine_def = D.MINE_TYPES.get(active_mine.get("mine_type", "gold"), {})
        mine_label = mine_def.get("label", "Mine")
        mine_emoji = mine_def.get("emoji", "⛏️")
        start_ts   = active_mine.get("start_ts", 0)
        duration   = active_mine.get("duration_min", 10)
        cave_in_at = duration * 3
        active_mine_html = f"""
<div class="card" style="border:2px solid #f59e0b;background:#fffbeb;margin-bottom:18px;">
  <div class="card-title" style="color:#92400e;">{mine_emoji} Active Mine Run</div>
  <div style="text-align:center;padding:10px 0;">
    <div style="font-size:2em;margin-bottom:6px;">{mine_emoji}</div>
    <div style="font-weight:700;color:var(--ink);">{_esc(mine_label)}</div>
    <div style="font-size:0.85em;color:var(--ink-muted);margin-top:4px;" id="mine-timer">Calculating...</div>
    <div style="font-size:0.78em;color:#92400e;margin-top:4px;">
      Cave-in risk after {cave_in_at} min ({3}× overtime)
      {'· 🔨 Hammer active — 1.5× yield!' if active_mine.get('hammer_used') else ''}
    </div>
  </div>
  <button onclick="collectMine('{active_mine['id']}', this)"
          class="btn btn-primary" style="width:100%;margin-top:10px;justify-content:center;">
    ⛏️ Collect Yield
  </button>
  <script>
  (function() {{
    var startTs = {start_ts};
    var durationMin = {duration};
    var caveInMin = {cave_in_at};
    function updateTimer() {{
      var now = Date.now() / 1000;
      var elapsedSec = now - startTs;
      var targetSec = durationMin * 60;
      var remaining = targetSec - elapsedSec;
      var el = document.getElementById('mine-timer');
      if (!el) return;
      if (remaining > 0) {{
        var m = Math.floor(remaining / 60);
        var s = Math.floor(remaining % 60);
        el.textContent = m + 'm ' + s + 's remaining (collect anytime!)';
        el.style.color = '';
      }} else {{
        var elapsedMin = elapsedSec / 60;
        if (elapsedMin >= caveInMin) {{
          el.textContent = '💥 Cave-in! Collect for consolation loot only!';
          el.style.color = '#dc2626';
        }} else {{
          var overMin = Math.round(elapsedMin - durationMin);
          el.textContent = 'Ready! +' + overMin + 'm over target (collect before ' + caveInMin + 'min!)';
          el.style.color = '#15803d';
        }}
      }}
    }}
    updateTimer();
    setInterval(updateTimer, 1000);
  }})();
  </script>
</div>"""

    if not active_mine_html:
        # Item equip toggles
        axe_toggle = ""
        if has_axe:
            axe_toggle = f"""
<label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;
              background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;
              padding:6px 10px;font-size:0.82em;font-weight:600;margin-bottom:8px;">
  <input type="checkbox" id="use-axe-toggle" checked
         style="width:auto;accent-color:#d97706;">
  🪓 Use Battle Axe ({axe_count} left) — doubles hits on boss
</label>"""

        hammer_toggle = ""
        if has_hammer:
            hammer_toggle = f"""
<label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;
              background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;
              padding:6px 10px;font-size:0.82em;font-weight:600;margin-bottom:8px;">
  <input type="checkbox" id="use-hammer-toggle" checked
         style="width:auto;accent-color:#d97706;">
  🔨 Use Hammer ({hammer_count} left) — 1.5× mine yield
</label>"""

        # Boss button
        boss_label = f"{boss_type_def['emoji']} {boss_type_def['label']}"
        boss_disabled = "" if can_boss else "disabled"
        boss_class = "btn-primary" if can_boss else "btn-muted"
        boss_unavail_note = "" if boss_available else '<div style="font-size:0.78em;color:#9ca3af;margin-top:6px;">Boss not available today</div>'
        boss_no_quest_note = "" if total_done > 0 or not boss_available else '<div style="font-size:0.78em;color:#9ca3af;margin-top:6px;">Complete at least 1 quest first</div>'

        boss_btn = f"""
<button onclick="startBossFromPanel('{difficulty_key}', this)"
        class="btn {boss_class}" {boss_disabled}
        style="flex:1;justify-content:center;flex-direction:column;padding:14px 8px;text-align:center;min-height:90px;">
  <div style="font-size:1.5em;">{boss_type_def['emoji']}</div>
  <div style="font-size:0.82em;font-weight:700;margin-top:4px;">Boss Battle</div>
  <div style="font-size:0.68em;opacity:.9;margin-top:2px;">{_esc(boss_label)} · {diff['label']}</div>
  <div style="font-size:0.68em;opacity:.8;">⚡{boss_stamina_needed} · HP {diff['hp']}</div>
  <div style="font-size:0.65em;opacity:.7;">{total_done} quest{'s' if total_done != 1 else ''} → attack hits</div>
</button>
{boss_unavail_note}{boss_no_quest_note}"""

        # Mine buttons — requires at least 1 completed quest
        mine_choices = ""
        mine_no_quest_note = ""
        for mt, mdef in D.MINE_TYPES.items():
            mine_stamina = mdef["stamina_cost"]
            can_mine = stamina >= mine_stamina and total_done > 0
            mine_choices += f"""
<button onclick="startMineFromPanel('{mt}', this)"
        class="btn {'btn-primary' if can_mine else 'btn-muted'}"
        {'disabled' if not can_mine else ''}
        style="flex:1;justify-content:center;flex-direction:column;padding:12px 6px;text-align:center;min-height:80px;">
  <div style="font-size:1.4em;">{mdef['emoji']}</div>
  <div style="font-size:0.78em;font-weight:700;margin-top:3px;">{_esc(mdef['label'])}</div>
  <div style="font-size:0.65em;opacity:.8;">⚡{mine_stamina} · {mdef['base_rate']}/min</div>
  <div style="font-size:0.65em;opacity:.7;">{mdef['duration_min']}min run</div>
</button>"""
        if total_done == 0:
            mine_no_quest_note = '<div style="font-size:0.78em;color:#9ca3af;text-align:center;margin-top:6px;">Complete at least 1 quest to unlock mine runs</div>'

        battle_mine_panel = f"""
<div class="card" style="margin-bottom:18px;">
  <div class="card-title">⚔️ Quest Rewards</div>
  <p style="font-size:0.82em;color:var(--ink-muted);margin-bottom:10px;">
    Complete quests to power up your attacks! Use ⚡ stamina to start a battle or mine run.
    Mine speed bonuses: ⚡+50% within 10% of target · ⚡+25% within 25% · ⚡+10% on time.
    Cave-in after 3× target time — consolation crystals/diamonds only!
  </p>
  {axe_toggle}
  {hammer_toggle}
  <div style="margin-bottom:6px;font-size:0.8em;font-weight:700;color:var(--ink-muted);">⚔️ Boss Battle</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;">
    {boss_btn}
  </div>
  <div style="font-size:0.8em;font-weight:700;color:var(--ink-muted);margin-bottom:8px;">⛏️ Mine Runs</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;">
    {mine_choices}
  </div>
  {mine_no_quest_note}
</div>"""
    else:
        battle_mine_panel = active_mine_html

    # ── Recent battle results ────────────────────────────────────────────────────
    recent_battles = D.get_recent_battles(child_key, 3)
    battle_history_html = ""
    for b in recent_battles:
        won = b.get("won", False)
        bg  = "#f0fdf4" if won else "#fef2f2"
        border = "#86efac" if won else "#fca5a5"
        icon   = "🏆" if won else "💀"
        diff_label = D.BOSS_DIFFICULTIES.get(b.get("difficulty", "medium"), {}).get("label", "?")
        battle_history_html += f"""
<div style="padding:8px 10px;background:{bg};border:1px solid {border};
            border-radius:10px;margin-bottom:6px;font-size:0.82em;">
  {icon} <strong>{diff_label} Boss</strong> —
  {b.get('total_hits',0)} hits · {b.get('total_damage',0)} dmg vs {b.get('boss_hp',0)} HP ·
  {'Won 🪙' + str(b.get('win_coins',0)) if won else 'Lost (' + str(b.get('penalty_chores',0)) + ' penalty chores)'}
</div>"""

    if battle_history_html:
        battle_history_html = f"""
<div class="card" style="margin-bottom:18px;">
  <div class="card-title" style="font-size:0.92em;">📜 Recent Battles</div>
  {battle_history_html}
</div>"""

    # ── Rewards / Store panel ────────────────────────────────────────────────────
    cur_level = lvl["level"]
    pending_redemptions = {r["reward_id"] for r in D.load_redemptions()
                           if r.get("child") == child_key and r.get("status") == "pending"}
    reward_cards = ""
    for r in rewards:
        rid     = r.get("id", "")
        xp_req  = r.get("xp_threshold", 0)
        lvl_req = r.get("level_threshold", 0)
        price   = r.get("coin_price", 10)
        unlocked = (xp_req == 0 or total >= xp_req) and (lvl_req == 0 or cur_level >= lvl_req)
        can_buy  = unlocked and coins >= price
        pending  = rid in pending_redemptions

        item_badge = ""
        if r.get("item_reward"):
            idef = D.ITEMS.get(r["item_reward"], {})
            item_badge = f'<span style="margin-left:6px;font-size:0.72em;background:#f0fdf4;color:#15803d;border-radius:6px;padding:1px 6px;">{idef.get("emoji","")} {idef.get("label","")}</span>'

        if pending:
            action = """<div style="font-size:0.75em;color:#d97706;font-weight:700;
                            background:#fef3c7;padding:4px 10px;border-radius:8px;">
              ⏳ Pending mom's OK
            </div>"""
        elif can_buy and is_self:
            action = f"""<button onclick="redeemReward('{rid}', '{_esc(r.get('label',''))}', {price}, this)"
              style="background:#15803d;color:white;border:none;border-radius:10px;
                     padding:6px 12px;font-size:0.8em;font-weight:700;cursor:pointer;">
              Buy 🪙{price}
            </button>"""
        elif not unlocked:
            action = f"""<div style="font-size:0.72em;color:#9ca3af;">
              {'🔒 Need ' + str(xp_req) + ' XP' if xp_req else ''}
              {(' · ' if xp_req and lvl_req else '') + ('Lvl ' + str(lvl_req) if lvl_req else '')}
            </div>"""
        else:
            action = f"""<div style="font-size:0.78em;color:#9ca3af;">Need 🪙{price - coins} more</div>"""

        bg_r   = "#f0fdf4" if can_buy else "#f9fafb"
        border_r = "#86efac" if can_buy else "#e5e7eb"
        reward_cards += f"""
<div style="display:flex;align-items:center;gap:10px;padding:12px 14px;
            background:{bg_r};border:1px solid {border_r};border-radius:12px;margin-bottom:8px;">
  <span style="font-size:1.4em;">{"🎁" if can_buy else "🔒"}</span>
  <div style="flex:1;">
    <div style="font-weight:700;color:var(--ink);font-size:0.95em;">{_esc(r.get('label',''))}{item_badge}</div>
    <div style="font-size:0.78em;color:var(--ink-muted);margin-top:2px;">🪙 {price} coins</div>
  </div>
  {action}
</div>"""

    rewards_section = ""
    if rewards:
        rewards_section = f"""
<div class="card" style="margin-top:8px;">
  <div class="card-title">🛒 Reward Store &nbsp;<span style="font-size:0.75em;color:var(--ink-muted);">You have 🪙{coins}</span></div>
  {reward_cards}
</div>"""

    extra_css = """
@keyframes xp-pop {
  0%   { transform: scale(1); }
  50%  { transform: scale(1.2); }
  100% { transform: scale(1); }
}
.xp-pop { animation: xp-pop .4s ease; }
@keyframes check-pop {
  0%   { transform: scale(0); opacity: 0; }
  70%  { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(1); }
}
@keyframes toast-in {
  0%   { opacity:0; transform:translateY(20px) scale(.9); }
  100% { opacity:1; transform:translateY(0) scale(1); }
}
.btn:disabled { opacity: .5; cursor: not-allowed; }
"""

    extra_head = f"""
<script>
var _childKey = '{child_key}';

function completeQuest(questId, btn) {{
  btn.disabled = true;
  btn.style.opacity = '0.5';
  fetch('/quest/api/complete-quest', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{quest_id: questId, child: _childKey}})
  }})
  .then(r => r.json())
  .then(data => {{
    if (data.error) {{
      btn.disabled = false; btn.style.opacity = '1';
      alert('Error: ' + data.error); return;
    }}
    var xpEl = document.getElementById('xp-total');
    var barEl = document.getElementById('xp-bar');
    if (xpEl) {{
      xpEl.textContent = data.total_xp;
      xpEl.classList.remove('xp-pop');
      void xpEl.offsetWidth;
      xpEl.classList.add('xp-pop');
    }}
    if (barEl) barEl.style.width = data.progress_pct + '%';

    var card = btn.closest('.card');
    if (card) {{ card.style.opacity = '.5'; card.style.textDecoration = 'line-through'; }}

    var circle = btn.parentElement;
    circle.innerHTML = '<div style="width:52px;height:52px;border-radius:50%;background:currentColor;display:flex;align-items:center;justify-content:center;font-size:1.3em;flex-shrink:0;animation:check-pop .3s ease;">&#10003;</div>';

    var coinEl = document.getElementById('coin-total');
    if (coinEl && data.coins !== undefined) coinEl.textContent = data.coins;

    if (data.stamina !== undefined) updateStaminaDisplay(data.stamina);

    var toastMsg = '+' + data.xp_earned + ' XP  🪙+' + data.xp_earned;
    showToast(toastMsg, '#1a1a2e', '#f9d77e');

    if (data.stamina_refilled) {{
      setTimeout(function() {{
        showToast('⚡+' + data.stamina_refilled + ' Stamina from completing daily quests!', '#065f46', '#d1fae5');
      }}, 800);
    }}

    if (data.streak_bonus && data.streak_bonus > 0) {{
      setTimeout(function() {{
        showToast('&#128293; ' + data.streak.current + '-Day Streak! +' + data.streak_bonus + ' Bonus XP', '#7c2d12', '#fef3c7');
      }}, 600);
    }}

    if (data.streak) {{
      var sc = document.getElementById('streak-count');
      if (sc) {{
        var n = data.streak.current;
        sc.textContent = n + ' day' + (n !== 1 ? 's' : '') + ' streak';
      }}
    }}

    if (data.level) {{
      document.title = 'Level ' + data.level.level + ' \u2014 Family Quest';
    }}
  }})
  .catch(() => {{ btn.disabled = false; btn.style.opacity = '1'; }});
}}

function updateStaminaDisplay(newVal) {{
  var countEl = document.getElementById('stamina-count');
  var dotsEl  = document.getElementById('stamina-dots');
  var max = {D.MAX_STAMINA};
  if (countEl) countEl.textContent = newVal + '/' + max;
  if (dotsEl) {{
    var html = '';
    for (var i = 0; i < max; i++) {{
      html += '<span style="font-size:1em;opacity:' + (i < newVal ? '1' : '0.2') + ';">⚡</span>';
    }}
    dotsEl.innerHTML = html;
  }}
}}

function redeemReward(rewardId, label, price, btn) {{
  if (!confirm('Spend 🪙' + price + ' coins on "' + label + '"?\\nMom will need to approve it.')) return;
  btn.disabled = true; btn.textContent = '⏳';
  fetch('/quest/api/redeem-reward', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{reward_id: rewardId, child: _childKey}})
  }})
  .then(r => r.json())
  .then(data => {{
    if (data.error) {{ btn.disabled = false; btn.textContent = 'Buy 🪙' + price; alert(data.error); return; }}
    btn.parentElement.innerHTML = '<div style="font-size:0.75em;color:#d97706;font-weight:700;background:#fef3c7;padding:4px 10px;border-radius:8px;">⏳ Pending mom\'s OK</div>';
    showToast('Request sent! Mom will approve ✅', '#14532d', '#d1fae5');
  }})
  .catch(() => {{ btn.disabled = false; btn.textContent = 'Buy 🪙' + price; }});
}}

function changeCharacter() {{
  var sel = document.getElementById('char-select');
  if (!sel) return;
  var charKey = sel.value;
  fetch('/quest/api/set-character', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey, character: charKey}})
  }})
  .then(r => r.json())
  .then(data => {{
    if (data.error) {{ alert('Error: ' + data.error); return; }}
    showToast('Character changed! Reloading...', '#1a1a2e', '#f9d77e');
    setTimeout(() => location.reload(), 1000);
  }});
}}

function upgradeEquipment(slot, btn) {{
  btn.disabled = true;
  var orig = btn.innerHTML;
  btn.innerHTML = '⏳';
  fetch('/quest/api/upgrade-equipment', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey, slot: slot}})
  }})
  .then(r => r.json())
  .then(data => {{
    if (data.error) {{
      btn.disabled = false; btn.innerHTML = orig;
      showToast('❌ ' + data.error, '#7f1d1d', '#fee2e2');
      return;
    }}
    showToast('✨ ' + data.slot_label + ' upgraded to Level ' + data.new_level + '!', '#1a1a2e', '#f9d77e');
    var crystalEl = document.getElementById('crystal-total');
    var diamondEl = document.getElementById('diamond-total');
    if (crystalEl && data.crystals !== undefined) crystalEl.textContent = data.crystals;
    if (diamondEl && data.diamonds !== undefined) diamondEl.textContent = data.diamonds;
    setTimeout(() => location.reload(), 1200);
  }})
  .catch(() => {{ btn.disabled = false; btn.innerHTML = orig; }});
}}

function startBossFromPanel(difficulty, btn) {{
  var useAxe = false;
  var axeTog = document.getElementById('use-axe-toggle');
  if (axeTog) useAxe = axeTog.checked;
  var axeNote = useAxe ? '\\n🪓 Battle Axe will be consumed (doubles hits)!' : '';
  if (!confirm('Start Boss Battle (' + difficulty + ')?' + axeNote + '\\nThis costs stamina ⚡.')) return;
  btn.disabled = true;
  var orig = btn.innerHTML;
  btn.innerHTML = '⚔️ Battling...';
  fetch('/quest/api/boss-battle', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey, difficulty: difficulty, use_battle_axe: useAxe}})
  }})
  .then(r => r.json())
  .then(data => {{
    btn.disabled = false;
    btn.innerHTML = orig;
    if (data.error) {{
      showToast('❌ ' + data.error, '#7f1d1d', '#fee2e2');
      return;
    }}
    if (data.stamina !== undefined) updateStaminaDisplay(data.stamina);
    showBattleResult(data);
    if (data.win_coins) {{
      var coinEl = document.getElementById('coin-total');
      if (coinEl) coinEl.textContent = parseInt(coinEl.textContent) + data.win_coins;
    }}
    setTimeout(() => location.reload(), 3500);
  }})
  .catch(() => {{ btn.disabled = false; btn.innerHTML = orig; }});
}}

function showBattleResult(data) {{
  var won = data.won;
  var bossHp = data.boss_hp || 0;
  var dmg = data.total_damage || 0;
  var hits = data.total_hits || 0;
  var hpRemaining = Math.max(0, bossHp - dmg);
  var hpPct = bossHp > 0 ? Math.round(hpRemaining / bossHp * 100) : 0;
  var dmgPct = bossHp > 0 ? Math.min(100, Math.round(dmg / bossHp * 100)) : 100;
  var overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px;';
  var bg = won ? '#14532d' : '#7f1d1d';
  var textColor = won ? '#d1fae5' : '#fee2e2';
  var icon = won ? '🏆' : '💀';
  var title = won ? 'VICTORY!' : 'DEFEATED!';
  overlay.innerHTML = '<div style="background:#1c1c2e;border-radius:18px;padding:28px 24px;max-width:360px;width:100%;text-align:center;border:2px solid ' + bg + ';">'
    + '<div style="font-size:2.5em;margin-bottom:8px;">' + icon + '</div>'
    + '<div style="font-size:1.3em;font-weight:900;color:' + textColor + ';margin-bottom:12px;">' + title + '</div>'
    + '<div style="font-size:0.82em;color:#9ca3af;margin-bottom:14px;">' + hits + ' hits · ' + dmg + ' damage vs ' + bossHp + ' HP</div>'
    + '<div style="background:#111827;border-radius:10px;padding:10px;margin-bottom:14px;">'
    + '<div style="font-size:0.72em;color:#9ca3af;margin-bottom:6px;">Boss HP Bar</div>'
    + '<div style="background:#374151;border-radius:8px;height:18px;overflow:hidden;">'
    + '<div style="height:100%;background:' + (won ? '#22c55e' : '#ef4444') + ';width:' + hpPct + '%;transition:width 1s;border-radius:8px;"></div>'
    + '</div>'
    + '<div style="font-size:0.72em;color:#9ca3af;margin-top:4px;">' + hpRemaining + ' / ' + bossHp + ' HP remaining</div>'
    + '</div>'
    + '<div style="font-size:0.85em;color:white;margin-bottom:16px;">' + (data.message || '') + '</div>'
    + '<div style="font-size:0.75em;color:#6b7280;">Refreshing in 3 seconds...</div>'
    + '</div>';
  document.body.appendChild(overlay);
  overlay.addEventListener('click', function() {{ overlay.remove(); }});
}}

function startMineFromPanel(mineType, btn) {{
  var useHammer = false;
  var hamTog = document.getElementById('use-hammer-toggle');
  if (hamTog) useHammer = hamTog.checked;
  var hammerMsg = useHammer ? '\\n🔨 Hammer will be consumed for 1.5× yield.' : '';
  if (!confirm('Start ' + mineType + ' mine run?' + hammerMsg + '\\nCollect at any time (cave-in after 3× target time)!')) return;
  btn.disabled = true;
  var orig = btn.innerHTML;
  btn.innerHTML = '⛏️ Starting...';
  fetch('/quest/api/start-mine', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey, mine_type: mineType, use_hammer: useHammer}})
  }})
  .then(r => r.json())
  .then(data => {{
    btn.disabled = false;
    btn.innerHTML = orig;
    if (data.error) {{
      showToast('❌ ' + data.error, '#7f1d1d', '#fee2e2');
      return;
    }}
    showToast('⛏️ Mine run started! Come back to collect (cave-in after 3× target time)!', '#1a1a2e', '#f9d77e');
    if (data.stamina !== undefined) updateStaminaDisplay(data.stamina);
    setTimeout(() => location.reload(), 1000);
  }})
  .catch(() => {{ btn.disabled = false; btn.innerHTML = orig; }});
}}

function collectMine(mineId, btn) {{
  btn.disabled = true;
  var orig = btn.innerHTML;
  btn.innerHTML = '⛏️ Collecting...';
  fetch('/quest/api/collect-mine', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey, mine_id: mineId}})
  }})
  .then(r => r.json())
  .then(data => {{
    btn.disabled = false;
    btn.innerHTML = orig;
    if (data.error) {{
      showToast('❌ ' + data.error, '#7f1d1d', '#fee2e2');
      return;
    }}
    var bg    = data.cave_in ? '#7f1d1d' : '#14532d';
    var color = data.cave_in ? '#fee2e2' : '#d1fae5';
    showToast(data.message || '⛏️ Mine complete!', bg, color);
    if (data.coins !== undefined) {{
      var coinEl = document.getElementById('coin-total');
      if (coinEl) coinEl.textContent = data.coins;
    }}
    if (data.crystals !== undefined) {{
      var el = document.getElementById('crystal-total');
      if (el) el.textContent = data.crystals;
    }}
    if (data.diamonds !== undefined) {{
      var el = document.getElementById('diamond-total');
      if (el) el.textContent = data.diamonds;
    }}
    setTimeout(() => location.reload(), 2000);
  }})
  .catch(() => {{ btn.disabled = false; btn.innerHTML = orig; }});
}}

function showToast(msg, bg, color) {{
  var toast = document.createElement('div');
  toast.innerHTML = msg;
  toast.style.cssText = 'position:fixed;top:80px;right:20px;background:' + bg + ';color:' + color + ';' +
    'padding:12px 20px;border-radius:14px;font-weight:800;font-size:0.9em;z-index:999;' +
    'animation:toast-in .3s ease;box-shadow:0 4px 20px rgba(0,0,0,.3);max-width:280px;line-height:1.4;';
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}}
</script>"""

    body = f"""
{R.topbar(viewer, False)}
<div class="fq-main">
  {header}
  {resources_html}
  {character_panel}
  {battle_mine_panel}
  {battle_history_html}
  {equipment_panel}
  {summary}
  {quest_sections}
  {rewards_section}
</div>"""

    return R.html_page(f"{name}'s Quest Board", body, extra_css=extra_css, extra_head=extra_head)
