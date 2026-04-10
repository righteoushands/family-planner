"""
fq_views_child.py — Child-facing board for Family Quest (GDD v2).

Board sections (in order):
  1. Header bar  — name, emoji, child color
  2. Currency row — Real Coins 🪙 / Game Coins 💰 / Energy ⚡ (live-updating IDs)
  3. Resource row — Crystals 💎 / Diamonds 💠 / Copper 🟤 / Iron ⚙️
  4. Hero panel   — active hero stats, level, form, evolution progress
  5. Zone tabs    — Bosses | Big Boss | Fortress | Mines | Equipment | Store
  6. Quest list   — daily/side quests with energy+coin reward display
"""
from html import escape as _esc
from datetime import date

import fq_data   as D
import fq_render  as R
import fq_auth    as A


def is_parent(user: str) -> bool:
    return A.USERS.get(user, {}).get("role") == "parent"


# ── Entry point ────────────────────────────────────────────────────────────────

def render_child_board(child_key: str, viewer: str) -> str:
    """Render the full quest board page for child_key, viewed by viewer."""
    if child_key not in D.CHILDREN_KEYS:
        return R.html_page("Error", "<div class='fq-main'><p>Unknown child.</p></div>")

    is_self   = (viewer == child_key)
    can_complete = is_self
    name      = D.CHILDREN_NAMES[child_key]
    colors    = R.CHILD_COLORS[child_key]
    emoji     = R.CHILD_EMOJI[child_key]
    today     = date.today().isoformat()

    # ── Data loads ─────────────────────────────────────────────────────────────
    state       = D.get_child_state(child_key)
    real_coins  = state["real_coins"]
    game_coins  = state["game_coins"]
    energy      = state["energy"]
    crystals    = state["crystals"]
    diamonds    = state["diamonds"]
    copper      = state["copper"]
    iron        = state["iron"]

    hero        = D.get_active_hero(child_key)
    hero_roster = D.get_hero_roster(child_key)
    boss_state  = D.get_boss_state(child_key)
    fortress    = D.get_fortress_state(child_key)
    big_bosses  = D.get_big_boss_states(child_key)
    eq          = D.get_equipment(child_key)
    inv         = D.get_inventory(child_key)
    rewards     = D.load_rewards()
    active_mine = D.get_active_mine(child_key)
    streak      = D.get_streak(child_key)
    quests      = D.get_quests_for_child(child_key, today)

    # ── Streak badge ──────────────────────────────────────────────────────────
    streak_n = streak.get("current", 0)
    streak_html = ""
    if streak_n > 0:
        streak_html = (
            f'<div style="display:inline-flex;align-items:center;gap:4px;'
            f'background:rgba(255,255,255,.18);border-radius:20px;'
            f'padding:4px 10px;margin-top:10px;font-size:0.82em;font-weight:700;">'
            f'🔥 <span id="streak-count">{streak_n} day streak</span>'
            f'</div>'
        )

    # ── Header card ───────────────────────────────────────────────────────────
    header = f"""
<div style="background:{colors['bg']};border-radius:20px;padding:20px 20px 16px;
            color:white;margin-bottom:14px;position:relative;overflow:hidden;">
  <div style="position:absolute;top:-16px;right:-8px;font-size:5.5em;opacity:.12;line-height:1;">{emoji}</div>
  <div style="display:flex;align-items:center;gap:12px;position:relative;">
    <div style="width:56px;height:56px;border-radius:50%;background:rgba(255,255,255,.2);
                display:flex;align-items:center;justify-content:center;
                font-size:1.8em;flex-shrink:0;">{emoji}</div>
    <div style="flex:1;">
      <div style="font-size:1.2em;font-weight:800;">{_esc(name)}'s Quest Board</div>
      <div style="font-size:0.82em;opacity:.85;">
        {_esc(hero['form_label'])} · Level {hero['level']}
      </div>
    </div>
    <div style="text-align:right;flex-shrink:0;font-size:0.78em;opacity:.8;">
      <div>Boss #{boss_state['boss_num']}</div>
      <div>{boss_state['total_defeated']} defeated</div>
    </div>
  </div>
  {streak_html}
</div>"""

    # ── Currency row ──────────────────────────────────────────────────────────
    currency_row = f"""
<div class="card" style="padding:12px 16px;margin-bottom:10px;">
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0;text-align:center;">
    <div>
      <div style="font-size:1.5em;">🪙</div>
      <div id="real-coin-total" style="font-size:1.4em;font-weight:900;color:#b45309;">{real_coins}</div>
      <div style="font-size:0.62em;color:var(--ink-muted);font-weight:700;text-transform:uppercase;letter-spacing:.04em;">Real Coins</div>
    </div>
    <div style="border-left:1px solid var(--border-light);border-right:1px solid var(--border-light);">
      <div style="font-size:1.5em;">💰</div>
      <div id="game-coin-total" style="font-size:1.4em;font-weight:900;color:#15803d;">{game_coins}</div>
      <div style="font-size:0.62em;color:var(--ink-muted);font-weight:700;text-transform:uppercase;letter-spacing:.04em;">Game Coins</div>
    </div>
    <div>
      <div style="font-size:1.5em;">⚡</div>
      <div id="energy-total" style="font-size:1.4em;font-weight:900;color:#7c3aed;">{energy}</div>
      <div style="font-size:0.62em;color:var(--ink-muted);font-weight:700;text-transform:uppercase;letter-spacing:.04em;">Energy</div>
    </div>
  </div>
</div>"""

    # ── Resource row ──────────────────────────────────────────────────────────
    resource_row = f"""
<div class="card" style="padding:10px 14px;margin-bottom:14px;">
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:0;text-align:center;">
    <div>
      <div style="font-size:1.25em;">💎</div>
      <div id="crystal-total" style="font-size:1.1em;font-weight:800;color:#0ea5e9;">{crystals}</div>
      <div style="font-size:0.6em;color:var(--ink-muted);font-weight:700;text-transform:uppercase;">Crystals</div>
    </div>
    <div style="border-left:1px solid var(--border-light);">
      <div style="font-size:1.25em;">💠</div>
      <div id="diamond-total" style="font-size:1.1em;font-weight:800;color:#8b5cf6;">{diamonds}</div>
      <div style="font-size:0.6em;color:var(--ink-muted);font-weight:700;text-transform:uppercase;">Diamonds</div>
    </div>
    <div style="border-left:1px solid var(--border-light);">
      <div style="font-size:1.25em;">🟤</div>
      <div id="copper-total" style="font-size:1.1em;font-weight:800;color:#92400e;">{copper}</div>
      <div style="font-size:0.6em;color:var(--ink-muted);font-weight:700;text-transform:uppercase;">Copper</div>
    </div>
    <div style="border-left:1px solid var(--border-light);">
      <div style="font-size:1.25em;">⚙️</div>
      <div id="iron-total" style="font-size:1.1em;font-weight:800;color:#6b7280;">{iron}</div>
      <div style="font-size:0.6em;color:var(--ink-muted);font-weight:700;text-transform:uppercase;">Iron</div>
    </div>
  </div>
</div>"""

    # ── Hero panel ────────────────────────────────────────────────────────────
    hero_xp    = hero["xp"]
    hero_xp_to = hero["xp_to_next"]
    hero_pct   = int(hero_xp * 100 / hero_xp_to) if hero_xp_to else 100

    hero_xp_line = (
        f"<div style='font-size:0.75em;color:var(--ink-muted);margin-bottom:4px;'>"
        f"{hero_xp} / {hero_xp_to} XP to Level {hero['level']+1}"
        f"</div>"
    ) if hero_xp_to else "<div style='font-size:0.75em;color:#15803d;font-weight:700;'>Max Level!</div>"

    # Hero stat bars (scaled to 0-100 for display)
    dmg_pct = min(100, int(hero['damage'] / 20))
    def_pct = min(100, int(hero['defense'] / 20))
    hp_pct  = min(100, int(hero['hp'] / 30))

    # Evolution section
    evol_html = ""
    if hero.get("can_evolve"):
        evol_cost = hero.get("evolution_cost", {})
        cost_parts = []
        for field, needed in (evol_cost or {}).items():
            icons = {"copper":"🟤","game_coins":"💰","crystals":"💎","diamonds":"💠","iron":"⚙️"}
            cost_parts.append(f"{icons.get(field,'')} {needed}")
        cost_str = " · ".join(cost_parts)
        evol_html = f"""
<div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:12px;padding:12px;margin-top:14px;">
  <div style="font-weight:800;font-size:0.88em;color:#92400e;">✨ Evolution Ready!</div>
  <div style="font-size:0.75em;color:#92400e;margin-top:3px;">Cost: {cost_str}</div>
  {'<button onclick="evolveHero(this)" class="btn btn-primary btn-sm" style="margin-top:8px;width:100%;justify-content:center;">⭐ Evolve ' + _esc(hero["name"]) + '</button>' if is_self or is_parent(viewer) else ''}
</div>"""
    elif hero['level'] < 50 and hero['form'] == 1:
        pct_to_evol = int(hero['level'] * 2)
        evol_html = f"""
<div style="margin-top:10px;">
  <div style="display:flex;justify-content:space-between;font-size:0.7em;color:var(--ink-muted);margin-bottom:3px;">
    <span>⭐ Evolution (Level 50)</span><span>Level {hero['level']}/50</span>
  </div>
  <div class="xp-bar-wrap" style="height:6px;">
    <div class="xp-bar-fill" style="width:{pct_to_evol}%;background:#f59e0b;"></div>
  </div>
</div>"""

    # Hero switcher (only for self/parent)
    roster = hero_roster.get("roster", {})
    hero_options = ""
    for hkey in roster:
        hdef = D.HEROES.get(hkey, {})
        if not hdef:
            continue
        state_h = roster[hkey]
        hlbl    = hdef.get("name", hkey)
        hemoji  = hdef.get("emoji", "⚔️")
        hlevel  = state_h.get("level", 1)
        sel = "selected" if hkey == hero["key"] else ""
        hero_options += f'<option value="{hkey}" {sel}>{hemoji} {hlbl} (Lv.{hlevel})</option>'

    switch_html = ""
    if (is_self or is_parent(viewer)) and len(roster) > 1:
        switch_html = f"""
<div style="display:flex;gap:8px;align-items:center;margin-top:12px;">
  <select id="hero-select" style="flex:1;font-size:0.82em;padding:7px 10px;">{hero_options}</select>
  <button type="button" onclick="switchHero()" class="btn btn-muted btn-sm">Switch</button>
</div>"""

    hero_panel = f"""
<div class="card" style="margin-bottom:14px;">
  <div class="card-title">{hero['emoji']} Hero</div>
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
    <div style="width:52px;height:52px;border-radius:50%;background:{colors['bg']};
                display:flex;align-items:center;justify-content:center;font-size:1.7em;flex-shrink:0;">
      {hero['emoji']}
    </div>
    <div style="flex:1;">
      <div style="font-weight:800;font-size:1.02em;">{_esc(hero['name'])}</div>
      <div style="font-size:0.76em;color:var(--ink-muted);">{_esc(hero['form_label'])}</div>
      <div style="font-size:0.72em;color:#7c3aed;font-weight:700;margin-top:2px;">
        Level {hero['level']} &nbsp;·&nbsp; {hero['hits_per_turn']} hits/turn
      </div>
    </div>
    <div style="text-align:right;font-size:0.82em;">
      <div style="font-weight:700;color:#7c3aed;">Lv.{hero['level']}</div>
      <div style="font-size:0.72em;color:var(--ink-muted);">Form {hero['form']}</div>
    </div>
  </div>

  <div style="margin-bottom:8px;">
    <div style="display:flex;justify-content:space-between;font-size:0.75em;font-weight:700;margin-bottom:3px;">
      <span>⚔️ Damage</span><span style="color:#dc2626;">{hero['damage']}</span>
    </div>
    <div class="xp-bar-wrap" style="height:7px;">
      <div class="xp-bar-fill" style="width:{dmg_pct}%;background:#dc2626;"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:0.75em;font-weight:700;margin-top:7px;margin-bottom:3px;">
      <span>🛡️ Defense</span><span style="color:#2563eb;">{hero['defense']}</span>
    </div>
    <div class="xp-bar-wrap" style="height:7px;">
      <div class="xp-bar-fill" style="width:{def_pct}%;background:#2563eb;"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:0.75em;font-weight:700;margin-top:7px;margin-bottom:3px;">
      <span>❤️ Health</span><span style="color:#16a34a;">{hero['hp']}</span>
    </div>
    <div class="xp-bar-wrap" style="height:7px;">
      <div class="xp-bar-fill" style="width:{hp_pct}%;background:#16a34a;"></div>
    </div>
  </div>

  <div style="margin-top:10px;">
    <div style="display:flex;justify-content:space-between;font-size:0.7em;color:var(--ink-muted);margin-bottom:3px;">
      <span>Hero XP</span><span id="hero-xp-label">{hero_xp} / {hero_xp_to or '—'}</span>
    </div>
    <div class="xp-bar-wrap" style="height:7px;">
      <div id="hero-xp-bar" class="xp-bar-fill" style="width:{hero_pct}%;background:#7c3aed;"></div>
    </div>
  </div>
  {evol_html}
  {switch_html}
</div>"""

    # ── Zone tabs ─────────────────────────────────────────────────────────────
    tab_ids  = ["zone-bosses", "zone-bigboss", "zone-fortress", "zone-mines", "zone-equipment", "zone-store"]
    tab_lbls = ["⚔️ Bosses", "👹 Big Boss", "🏰 Fortress", "⛏️ Mines", "🎒 Equipment", "🛒 Store"]

    tab_btns = "".join(
        f'<button onclick="openZone(\'{tid}\')" id="tab-{tid}" '
        f'style="flex-shrink:0;padding:8px 14px;border:none;border-radius:10px;font-size:0.8em;font-weight:700;'
        f'cursor:pointer;font-family:inherit;transition:all .15s;white-space:nowrap;'
        f'background:{"#1a1a2e" if i==0 else "#f3f4f6"};color:{"#f9d77e" if i==0 else "#374151"};">'
        f'{lbl}</button>'
        for i, (tid, lbl) in enumerate(zip(tab_ids, tab_lbls))
    )

    tab_nav = f"""
<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:14px;">
  <div style="display:flex;gap:8px;padding-bottom:4px;">
    {tab_btns}
  </div>
</div>"""

    # ── Zone: Bosses ──────────────────────────────────────────────────────────
    boss_num     = boss_state["boss_num"]
    boss_hp_tot  = boss_state["boss_hp_total"]
    boss_hp_rem  = boss_state["boss_hp_remaining"]
    boss_pct     = boss_state["boss_pct"]
    boss_rewards = boss_state["rewards"]
    axe_count    = inv.get("battle_axe", 0)

    energy_per_attack = hero["hits_per_turn"]
    can_attack = energy >= energy_per_attack

    axe_toggle_html = ""
    if axe_count > 0:
        axe_toggle_html = f"""
<label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;
              background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;
              padding:6px 10px;font-size:0.82em;font-weight:600;margin-bottom:10px;">
  <input type="checkbox" id="use-axe-toggle" style="width:auto;accent-color:#d97706;">
  🪓 Use Battle Axe ({axe_count} left) — 1.5× damage
</label>"""

    boss_zone = f"""
<div id="zone-bosses" class="zone-panel">
  <div style="text-align:center;padding:4px 0 16px;">
    <div style="font-size:2.5em;">👹</div>
    <div style="font-weight:900;font-size:1.2em;color:var(--ink);">Boss #{boss_num}</div>
    <div style="font-size:0.82em;color:var(--ink-muted);margin-top:2px;">
      Sequential boss fight — defeat to advance!
    </div>
  </div>
  <div style="background:#f9fafb;border-radius:12px;padding:14px;margin-bottom:14px;">
    <div style="display:flex;justify-content:space-between;font-size:0.78em;color:var(--ink-muted);margin-bottom:6px;">
      <span>Boss HP</span>
      <span id="boss-hp-label">{boss_hp_rem:,} / {boss_hp_tot:,}</span>
    </div>
    <div class="xp-bar-wrap" style="height:16px;">
      <div id="boss-hp-bar" class="xp-bar-fill" style="width:{boss_pct}%;background:#dc2626;"></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:12px;text-align:center;">
      <div>
        <div style="font-size:0.7em;color:var(--ink-muted);">Win Rewards</div>
        <div style="font-size:0.9em;font-weight:800;color:#15803d;">💰 {boss_rewards['game_coins']}</div>
        <div style="font-size:0.9em;font-weight:800;color:#b45309;">🪙 {boss_rewards['real_coins']}</div>
      </div>
      <div>
        <div style="font-size:0.7em;color:var(--ink-muted);">Energy Cost</div>
        <div style="font-size:1.1em;font-weight:800;color:#7c3aed;">⚡ {energy_per_attack}</div>
        <div style="font-size:0.68em;color:var(--ink-muted);">{hero['hits_per_turn']} hits</div>
      </div>
      <div>
        <div style="font-size:0.7em;color:var(--ink-muted);">Your Energy</div>
        <div id="boss-energy-display" style="font-size:1.1em;font-weight:800;color:{'#7c3aed' if can_attack else '#9ca3af'};">⚡ {energy}</div>
        <div style="font-size:0.68em;color:{'#15803d' if can_attack else '#dc2626'};">{'Ready!' if can_attack else 'Need more'}</div>
      </div>
    </div>
  </div>
  {axe_toggle_html}
  {'<button onclick="attackBoss(this)" class="btn btn-primary" style="width:100%;justify-content:center;font-size:1em;padding:14px;" id="attack-btn">⚔️ Attack Boss (⚡' + str(energy_per_attack) + ')</button>' if (is_self and can_attack) else ('<div style="text-align:center;padding:10px;font-size:0.85em;color:#9ca3af;">Complete quests to earn energy ⚡, then attack the boss!</div>' if is_self else '')}
  <div style="margin-top:14px;font-size:0.78em;color:var(--ink-muted);text-align:center;">
    Next boss: #{boss_num+1} · HP {boss_hp_tot + 500:,} · 
    Reward 💰{boss_rewards['game_coins']+10} 🪙{boss_rewards['real_coins']+10}
  </div>
</div>"""

    # ── Zone: Big Boss ────────────────────────────────────────────────────────
    bb_cards = ""
    for bb in big_bosses:
        bb_pct    = bb["hp_pct"]
        defeated  = bb["defeated"]
        hp_color  = "#22c55e" if defeated else "#dc2626"
        bg_col    = "f0fdf4" if defeated else "f9fafb"
        bd_col    = "#86efac" if defeated else "#e5e7eb"
        bb_id     = bb["id"]
        bb_emoji  = bb["emoji"]
        bb_name   = _esc(bb["name"])
        bb_desc   = _esc(bb.get("description", ""))
        bb_hp_rem = bb.get("hp_remaining", 0)
        bb_gc     = bb.get("game_coins", 0)
        bb_rc     = bb.get("real_coins", 0)
        bb_unlock = bb.get("unlock_hero", "")
        unlock_name = D.HEROES.get(bb_unlock, {}).get("name", "?") if bb_unlock else ""

        if defeated:
            hp_html = '<span style="color:#15803d;font-weight:800;">✅ Defeated!</span>'
        else:
            hp_html = f'<span style="font-weight:700;">HP {bb_hp_rem:,}</span>'

        bar_html = "" if defeated else (
            f'<div class="xp-bar-wrap" style="height:10px;">'
            f'<div class="xp-bar-fill" style="width:{bb_pct}%;background:{hp_color};"></div></div>'
        )

        reward_html = ""
        if not defeated:
            unlock_span = f'<span>Unlocks: {unlock_name} hero</span>' if bb_unlock else ""
            reward_html = (
                f'<div style="display:flex;justify-content:space-between;font-size:0.7em;'
                f'color:var(--ink-muted);margin-top:4px;">'
                f'<span>Rewards: 💰{bb_gc} 🪙{bb_rc}</span>'
                f'{unlock_span}</div>'
            )

        atk_btn_html = ""
        if is_self and not defeated and can_attack:
            atk_btn_html = (
                f'<button onclick="attackBigBoss(&quot;{bb_id}&quot;, this)" '
                f'class="btn btn-primary btn-sm" '
                f'style="width:100%;justify-content:center;margin-top:10px;">'
                f'⚔️ Attack (⚡{energy_per_attack})</button>'
            )

        bb_cards += f"""
<div style="background:#{bg_col};border:1px solid {bd_col};
            border-radius:14px;padding:14px;margin-bottom:10px;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
    <span style="font-size:2em;">{bb_emoji}</span>
    <div style="flex:1;">
      <div style="font-weight:800;">{bb_name}</div>
      <div style="font-size:0.75em;color:var(--ink-muted);">{bb_desc}</div>
    </div>
    <div style="text-align:right;font-size:0.8em;">{hp_html}</div>
  </div>
  {bar_html}
  {reward_html}
  {atk_btn_html}
</div>"""

    bigboss_zone = f"""
<div id="zone-bigboss" class="zone-panel" style="display:none;">
  <p style="font-size:0.82em;color:var(--ink-muted);margin-bottom:14px;">
    Massive bosses with huge rewards — and hero unlocks! Uses the same energy as regular bosses.
  </p>
  {bb_cards}
</div>"""

    # ── Zone: Fortress ────────────────────────────────────────────────────────
    ft_can_collect = True  # simplification — server checks properly
    ft_upgrade_cost = fortress["upgrade_cost"]
    ft_can_upgrade = ft_upgrade_cost and game_coins >= ft_upgrade_cost and (is_self or is_parent(viewer))
    ft_upgrade_btn = ""
    if not fortress["max_level"] and (is_self or is_parent(viewer)):
        ft_upgrade_btn = f"""
<button onclick="upgradeFortress(this)"
        class="btn {'btn-primary' if ft_can_upgrade else 'btn-muted'}"
        {'disabled' if not ft_can_upgrade else ''}
        style="width:100%;justify-content:center;margin-top:10px;">
  {'🏰 Upgrade (💰 ' + str(ft_upgrade_cost) + ' GC)' if ft_upgrade_cost else '★ Max Level'}
</button>"""

    fortress_zone = f"""
<div id="zone-fortress" class="zone-panel" style="display:none;">
  <div style="text-align:center;padding:8px 0 16px;">
    <div style="font-size:3em;">{fortress['emoji']}</div>
    <div style="font-weight:900;font-size:1.15em;">{_esc(fortress['label'])}</div>
    <div style="font-size:0.78em;color:var(--ink-muted);">Level {fortress['level']}</div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px;">
    <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:12px;padding:14px;text-align:center;">
      <div style="font-size:0.72em;color:#15803d;font-weight:700;text-transform:uppercase;">Daily Income</div>
      <div style="font-size:1.5em;font-weight:900;color:#15803d;margin-top:4px;">
        💰 {fortress['passive_income']}
      </div>
      <div style="font-size:0.7em;color:#15803d;">Game Coins/day</div>
    </div>
    <div style="background:#eff6ff;border:1px solid #93c5fd;border-radius:12px;padding:14px;text-align:center;">
      <div style="font-size:0.72em;color:#1d4ed8;font-weight:700;text-transform:uppercase;">Defenders</div>
      <div style="font-size:1.5em;font-weight:900;color:#1d4ed8;margin-top:4px;">{fortress['defenders']}</div>
      <div style="font-size:0.7em;color:#1d4ed8;">troops</div>
    </div>
  </div>
  {f'<button onclick="collectFortressIncome(this)" class="btn btn-primary" style="width:100%;justify-content:center;">💰 Collect Daily Income</button>' if (is_self or is_parent(viewer)) else ''}
  {ft_upgrade_btn}
  {f'<div style="margin-top:8px;font-size:0.75em;color:var(--ink-muted);text-align:center;">Next: {_esc(fortress["next_label"])} (Level {fortress["level"]+1})</div>' if fortress["next_label"] else '<div style="margin-top:8px;text-align:center;font-size:0.82em;color:#15803d;font-weight:700;">⭐ Maximum Fortress Level!</div>'}
</div>"""

    # ── Zone: Mines ───────────────────────────────────────────────────────────
    hammer_count = inv.get("hammer", 0)
    hammer_toggle_html = ""
    if hammer_count > 0:
        hammer_toggle_html = f"""
<label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;
              background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;
              padding:6px 10px;font-size:0.82em;font-weight:600;margin-bottom:10px;">
  <input type="checkbox" id="use-hammer-toggle" style="width:auto;accent-color:#d97706;">
  🔨 Use Hammer ({hammer_count} left) — 1.5× yield
</label>"""

    # Active mine display
    active_mine_html = ""
    if active_mine:
        mine_def     = D.MINE_TYPES.get(active_mine.get("mine_type", "gold"), {})
        mine_label   = mine_def.get("label", "Mine")
        mine_emoji   = mine_def.get("emoji", "⛏️")
        start_ts     = active_mine.get("start_ts", 0)
        duration_min = active_mine.get("duration_min", 10)
        cave_mult    = 2.0 if active_mine.get("mine_type") == "gold" else 3.0
        cave_at      = duration_min * cave_mult
        active_mine_html = f"""
<div style="border:2px solid #f59e0b;background:#fffbeb;border-radius:14px;padding:14px;margin-bottom:14px;">
  <div style="font-weight:800;color:#92400e;margin-bottom:6px;">{mine_emoji} Active Mine Run</div>
  <div style="text-align:center;padding:8px 0;">
    <div style="font-size:2em;">{mine_emoji}</div>
    <div style="font-weight:700;">{_esc(mine_label)}</div>
    <div style="font-size:0.82em;color:var(--ink-muted);margin-top:4px;" id="mine-timer">Calculating...</div>
    <div style="font-size:0.72em;color:#92400e;margin-top:3px;">
      Cave-in after {cave_at:.0f} min
      {'· 🔨 Hammer active (1.5× yield)!' if active_mine.get('hammer_used') else ''}
    </div>
  </div>
  <button onclick="collectMine('{active_mine['id']}', this)"
          class="btn btn-primary" style="width:100%;justify-content:center;margin-top:10px;">
    ⛏️ Collect Yield
  </button>
  <script>
  (function() {{
    var startTs = {start_ts};
    var durationMin = {duration_min};
    var caveAtMin = {cave_at};
    function updateTimer() {{
      var now = Date.now() / 1000;
      var elapsedSec = now - startTs;
      var targetSec  = durationMin * 60;
      var remaining  = targetSec - elapsedSec;
      var el = document.getElementById('mine-timer');
      if (!el) return;
      if (remaining > 0) {{
        var m = Math.floor(remaining / 60);
        var s = Math.floor(remaining % 60);
        el.textContent = m + 'm ' + s + 's remaining';
        el.style.color = '';
      }} else {{
        var elapsedMin = elapsedSec / 60;
        if (elapsedMin >= caveAtMin) {{
          el.textContent = '💥 Cave-in zone! Collect now for consolation loot!';
          el.style.color = '#dc2626';
        }} else {{
          var over = Math.round(elapsedMin - durationMin);
          el.textContent = '✅ Ready! +' + over + 'm overtime (collect before cave-in!)';
          el.style.color = '#15803d';
        }}
      }}
    }}
    updateTimer();
    setInterval(updateTimer, 1000);
  }})();
  </script>
</div>"""

    # Mine buttons (only if no active mine)
    mine_btns_html = ""
    if not active_mine:
        total_done_today = sum(1 for q in quests if D.is_completed(q, child_key))
        has_quest_done   = total_done_today > 0
        for mt, mdef in D.MINE_TYPES.items():
            can_mine = has_quest_done and (is_self or is_parent(viewer))
            res_emoji = {"real_coins":"🪙","crystals":"💎","diamonds":"💠","copper":"🟤","iron":"⚙️"}.get(mdef["resource"],"📦")
            mine_btns_html += f"""
<button onclick="startMine('{mt}', this)"
        class="btn {'btn-primary' if can_mine else 'btn-muted'}"
        {'disabled' if not can_mine else ''}
        style="display:flex;align-items:center;gap:10px;width:100%;padding:12px 14px;margin-bottom:8px;text-align:left;">
  <span style="font-size:1.6em;">{mdef['emoji']}</span>
  <div>
    <div style="font-size:0.92em;font-weight:700;">{_esc(mdef['label'])}</div>
    <div style="font-size:0.72em;opacity:.8;">
      {res_emoji} {mdef['base_rate']}/min · {mdef['duration_min']}min target · {_esc(mdef['description'])}
    </div>
  </div>
</button>"""
        if not has_quest_done and is_self:
            mine_btns_html += '<div style="text-align:center;font-size:0.82em;color:#9ca3af;padding:8px;">Complete at least 1 quest to unlock mine runs!</div>'

    mines_zone = f"""
<div id="zone-mines" class="zone-panel" style="display:none;">
  <p style="font-size:0.8em;color:var(--ink-muted);margin-bottom:12px;">
    Run a mine to gather resources. Collect anytime — speed bonuses for collecting quickly.
    Cave-in risk after {2}× target time for Gold, {3}× for others.
  </p>
  {hammer_toggle_html}
  {active_mine_html}
  {mine_btns_html}
</div>"""

    # ── Zone: Equipment ───────────────────────────────────────────────────────
    eq_slots_html = ""
    for slot_key, slot_def in D.EQUIPMENT_SLOTS.items():
        level     = eq.get(slot_key, 0)
        max_level = slot_def["max_level"]
        slot_label = slot_def["label"]
        slot_emoji = slot_def["emoji"]
        # Cost for next upgrade
        if level < max_level:
            next_cost = slot_def["upgrade_costs"][level]
            cost_parts = []
            for res, amt in next_cost.items():
                icons = {"crystals":"💎","diamonds":"💠","copper":"🟤","iron":"⚙️"}
                cost_parts.append(f"{icons.get(res,'')}{amt}")
            cost_str = " ".join(cost_parts)
            can_upgrade = all(
                state.get(res, 0) >= amt for res, amt in next_cost.items()
            )
            upgrade_btn = f"""<button onclick="upgradeEquipment('{slot_key}', this)"
              class="btn btn-sm {'btn-primary' if can_upgrade else 'btn-muted'}"
              {'disabled' if not (can_upgrade and (is_self or is_parent(viewer))) else ''}
              title="Cost: {cost_str}">
              ↑ {cost_str}
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
  <span style="font-size:1.3em;width:28px;text-align:center;">{slot_emoji}</span>
  <div style="flex:1;">
    <div style="font-weight:700;font-size:0.88em;">{_esc(slot_label)} <span style="color:var(--ink-muted);font-weight:400;font-size:0.82em;">Lv.{level}</span></div>
    <div style="margin-top:3px;">{level_dots}</div>
    <div style="font-size:0.7em;color:var(--ink-muted);">{_esc(slot_def['description'])}</div>
  </div>
  {upgrade_btn}
</div>"""

    # Items section
    items_html = ""
    for item_key, item_def in D.ITEMS.items():
        count = inv.get(item_key, 0)
        if count > 0:
            items_html += f"""
<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--border-light);">
  <span style="font-size:1.3em;">{item_def['emoji']}</span>
  <div style="flex:1;">
    <div style="font-weight:700;font-size:0.85em;">{_esc(item_def['label'])} <span style="color:#15803d;font-weight:800;">×{count}</span></div>
    <div style="font-size:0.7em;color:var(--ink-muted);">{_esc(item_def['description'])}</div>
  </div>
</div>"""
    if not items_html:
        items_html = '<div style="font-size:0.8em;color:var(--ink-muted);padding:8px 0;">No special items — earn them from quests!</div>'

    equipment_zone = f"""
<div id="zone-equipment" class="zone-panel" style="display:none;">
  {eq_slots_html}
  <div style="margin-top:14px;">
    <div style="font-size:0.8em;font-weight:700;color:var(--ink-muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:.04em;">Special Items</div>
    {items_html}
  </div>
  <div style="margin-top:12px;font-size:0.72em;color:var(--ink-muted);">
    ⚔️ Sword upgrades cost 💎 Crystals &nbsp;·&nbsp; 🛡️ Shield &amp; 🧥 Armor cost 💠 Diamonds
  </div>
</div>"""

    # ── Zone: Store (Real Coin Rewards) ───────────────────────────────────────
    pending_set = {r["reward_id"] for r in D.load_redemptions()
                   if r.get("child") == child_key and r.get("status") == "pending"}
    reward_cards = ""
    for r in rewards:
        rid    = r.get("id", "")
        price  = r.get("coin_price", 10)
        can_buy = real_coins >= price
        pending = rid in pending_set
        item_badge = ""
        if r.get("item_reward"):
            idef = D.ITEMS.get(r["item_reward"], {})
            item_badge = f'<span style="font-size:0.7em;background:#f0fdf4;color:#15803d;border-radius:6px;padding:1px 6px;margin-left:4px;">{idef.get("emoji","")} {idef.get("label","")}</span>'

        if pending:
            action = '<div style="font-size:0.75em;color:#d97706;font-weight:700;background:#fef3c7;padding:4px 10px;border-radius:8px;">⏳ Pending</div>'
        elif can_buy and is_self:
            action = f'<button onclick="redeemReward(\'{rid}\', \'{_esc(r.get("label",""))}\', {price}, this)" style="background:#15803d;color:white;border:none;border-radius:10px;padding:6px 12px;font-size:0.8em;font-weight:700;cursor:pointer;">Redeem 🪙{price}</button>'
        else:
            action = f'<div style="font-size:0.75em;color:#9ca3af;">Need 🪙{max(0, price - real_coins)} more</div>'

        reward_cards += f"""
<div style="display:flex;align-items:center;gap:10px;padding:12px 14px;
            background:{'#f0fdf4' if can_buy else '#f9fafb'};
            border:1px solid {'#86efac' if can_buy else '#e5e7eb'};
            border-radius:12px;margin-bottom:8px;">
  <span style="font-size:1.3em;">{'🎁' if can_buy else '🔒'}</span>
  <div style="flex:1;">
    <div style="font-weight:700;font-size:0.92em;">{_esc(r.get('label',''))}{item_badge}</div>
    <div style="font-size:0.75em;color:var(--ink-muted);">🪙 {price} Real Coins</div>
  </div>
  {action}
</div>"""

    if not reward_cards:
        reward_cards = '<div style="font-size:0.82em;color:var(--ink-muted);text-align:center;padding:20px;">No rewards yet — ask Mom to add some!</div>'

    store_zone = f"""
<div id="zone-store" class="zone-panel" style="display:none;">
  <div style="font-size:0.82em;color:var(--ink-muted);margin-bottom:14px;">
    Spend 🪙 Real Coins (earned from chores) on real prizes! Mom must approve each redemption.
    You have <strong>🪙 {real_coins} Real Coins</strong>.
  </div>
  {reward_cards}
</div>"""

    # ── Quest list ────────────────────────────────────────────────────────────
    total_done   = 0
    total_quests = len(quests)
    quest_sections = ""
    grouped = {t: [] for t in D.QUEST_TYPES}
    for q in quests:
        grouped.setdefault(q.get("type", "daily"), []).append(q)

    for qt in D.QUEST_TYPES:
        qlist = grouped.get(qt, [])
        if not qlist:
            continue
        tc    = R.TYPE_COLORS[qt]
        cards = ""
        for q in qlist:
            done = D.is_completed(q, child_key)
            if done:
                total_done += 1
            e_val  = q.get("energy_value", 1)
            rc_val = q.get("real_coin_value", 1)
            gc_val = q.get("game_coin_value", 2)
            synced_badge = (
                '<span style="font-size:0.62em;background:#e0f2fe;color:#0369a1;'
                'border-radius:6px;padding:1px 5px;margin-left:4px;">⚡ synced</span>'
            ) if q.get("synced") else ""

            if can_complete and not done:
                action_btn = f"""
<button onclick="completeQuest('{q['id']}', this)"
  style="width:50px;height:50px;border-radius:50%;border:3px solid {tc['bg']};
         background:white;color:{tc['bg']};font-size:1.2em;cursor:pointer;
         flex-shrink:0;transition:all .2s;display:flex;align-items:center;
         justify-content:center;">&#9675;</button>"""
            elif done:
                action_btn = f"""
<div style="width:50px;height:50px;border-radius:50%;background:{tc['bg']};
            display:flex;align-items:center;justify-content:center;
            font-size:1.2em;flex-shrink:0;">&#10003;</div>"""
            else:
                action_btn = f"""
<div style="width:50px;height:50px;border-radius:50%;border:3px solid #e5e7eb;
            display:flex;align-items:center;justify-content:center;
            font-size:0.95em;flex-shrink:0;color:#9ca3af;">&#9675;</div>"""

            done_style = "opacity:.5;" if done else ""
            cards += f"""
<div class="card" style="padding:12px 14px;{done_style}">
  <div style="display:flex;align-items:center;gap:12px;">
    {action_btn}
    <div style="flex:1;min-width:0;">
      <div style="font-size:0.95em;font-weight:700;{'text-decoration:line-through;' if done else ''}">
        {_esc(q.get('title',''))}{synced_badge}
      </div>
      <div style="margin-top:4px;display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
        <span class="badge" style="background:{tc['bg']}22;color:{tc['bg']};font-size:0.68em;">
          {tc['icon']} {tc['label']}
        </span>
        <span style="font-size:0.72em;font-weight:700;color:#7c3aed;">⚡+{e_val}</span>
        <span style="font-size:0.72em;font-weight:700;color:#b45309;">🪙+{rc_val}</span>
        <span style="font-size:0.72em;font-weight:700;color:#15803d;">💰+{gc_val}</span>
      </div>
    </div>
  </div>
</div>"""

        quest_sections += f"""
<div style="margin-bottom:20px;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
    <span style="font-size:1.3em;">{tc['icon']}</span>
    <h2 style="margin-bottom:0;font-size:0.95em;font-weight:800;color:{tc['bg']};
               text-transform:uppercase;letter-spacing:.06em;">{tc['label']} Quests</h2>
    <span class="badge" style="background:{tc['bg']};color:white;">
      {sum(1 for q in qlist if D.is_completed(q, child_key))}/{len(qlist)}
    </span>
  </div>
  {cards}
</div>"""

    if not quests:
        quest_sections = """
<div class="card" style="text-align:center;padding:36px 20px;">
  <div style="font-size:3em;margin-bottom:10px;">📋</div>
  <div style="font-size:1.05em;font-weight:700;margin-bottom:6px;">No quests today</div>
  <div style="font-size:0.85em;color:var(--ink-muted);">Check back later — your parents are preparing quests!</div>
</div>"""

    # ── Progress summary ───────────────────────────────────────────────────────
    if total_quests > 0:
        prog_pct = int(total_done * 100 / total_quests)
        all_done_msg = ""
        if total_done == total_quests:
            all_done_msg = '<div style="text-align:center;margin-top:10px;font-size:1.1em;">🎉 All quests done! Great work today!</div>'
        summary = f"""
<div class="card" style="background:linear-gradient(135deg,#f9fafb,#f3f4f6);margin-bottom:18px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
    <div style="font-weight:800;">Today's Progress</div>
    <div style="font-weight:800;color:{colors['bg']};">{total_done}/{total_quests}</div>
  </div>
  <div class="xp-bar-wrap" style="height:12px;">
    <div class="xp-bar-fill" style="width:{prog_pct}%;background:{colors['bg']};"></div>
  </div>
  {all_done_msg}
</div>"""
    else:
        summary = ""

    # ── CSS ───────────────────────────────────────────────────────────────────
    extra_css = """
@keyframes check-pop {
  0%   { transform: scale(0); opacity: 0; }
  70%  { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(1); }
}
@keyframes toast-in {
  0%   { opacity:0; transform:translateY(20px) scale(.9); }
  100% { opacity:1; transform:translateY(0) scale(1); }
}
@keyframes coin-pop {
  0%   { transform: scale(1); }
  40%  { transform: scale(1.3); }
  100% { transform: scale(1); }
}
.coin-pop { animation: coin-pop .35s ease; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
"""

    # ── JavaScript ────────────────────────────────────────────────────────────
    extra_head = f"""
<script>
var _childKey = '{child_key}';

// ── Zone tabs ────────────────────────────────────────────────────────────────
function openZone(zoneId) {{
  var zones = document.querySelectorAll('.zone-panel');
  zones.forEach(function(z) {{ z.style.display = 'none'; }});
  var tabs  = document.querySelectorAll('[id^="tab-zone-"]');
  tabs.forEach(function(t) {{
    t.style.background = '#f3f4f6';
    t.style.color      = '#374151';
  }});
  var panel = document.getElementById(zoneId);
  if (panel) panel.style.display = '';
  var tab = document.getElementById('tab-' + zoneId);
  if (tab) {{ tab.style.background = '#1a1a2e'; tab.style.color = '#f9d77e'; }}
}}

// ── Quest completion ──────────────────────────────────────────────────────────
function completeQuest(questId, btn) {{
  btn.disabled = true;
  btn.style.opacity = '0.5';
  fetch('/quest/api/complete-quest', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{quest_id: questId, child: _childKey}})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(data) {{
    if (data.error) {{
      btn.disabled = false; btn.style.opacity = '1';
      alert('Error: ' + data.error); return;
    }}
    // Mark quest card done
    var card = btn.closest('.card');
    if (card) {{ card.style.opacity = '.5'; }}
    btn.parentElement.innerHTML = '<div style="width:50px;height:50px;border-radius:50%;background:currentColor;display:flex;align-items:center;justify-content:center;font-size:1.2em;flex-shrink:0;animation:check-pop .3s ease;">&#10003;</div>';

    // Update currency displays
    if (data.real_coins !== undefined) updateEl('real-coin-total', data.real_coins, 'coin-pop');
    if (data.game_coins !== undefined) updateEl('game-coin-total', data.game_coins, 'coin-pop');
    if (data.energy     !== undefined) updateEl('energy-total',    data.energy,     'coin-pop');

    // Update boss energy display
    var bossEn = document.getElementById('boss-energy-display');
    if (bossEn && data.energy !== undefined) bossEn.textContent = '⚡ ' + data.energy;

    var toastMsg = '+' + data.energy_earned + ' ⚡ +' + data.rc_earned + ' 🪙 +' + data.gc_earned + ' 💰';
    showToast(toastMsg, '#1a1a2e', '#f9d77e');

    if (data.streak_bonus_gc && data.streak_bonus_gc > 0) {{
      setTimeout(function() {{
        showToast('🔥 ' + data.streak.current + '-Day Streak! +' + data.streak_bonus_gc + ' 💰', '#7c2d12', '#fef3c7');
      }}, 700);
    }}
    if (data.streak) {{
      var sc = document.getElementById('streak-count');
      if (sc) sc.textContent = data.streak.current + ' day streak';
    }}
  }})
  .catch(function() {{ btn.disabled = false; btn.style.opacity = '1'; }});
}}

function updateEl(id, val, animClass) {{
  var el = document.getElementById(id);
  if (!el) return;
  el.textContent = val;
  if (animClass) {{
    el.classList.remove(animClass);
    void el.offsetWidth;
    el.classList.add(animClass);
  }}
}}

// ── Boss attack ───────────────────────────────────────────────────────────────
function attackBoss(btn) {{
  var useAxe = false;
  var axeTog = document.getElementById('use-axe-toggle');
  if (axeTog) useAxe = axeTog.checked;
  btn.disabled = true;
  var orig = btn.innerHTML;
  btn.innerHTML = '⚔️ Attacking...';
  fetch('/quest/api/attack-boss', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey, use_battle_axe: useAxe}})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(data) {{
    btn.disabled = false; btn.innerHTML = orig;
    if (data.error) {{ showToast('❌ ' + data.error, '#7f1d1d', '#fee2e2'); return; }}
    if (data.energy !== undefined) updateEl('energy-total', data.energy, 'coin-pop');
    if (data.boss_defeated) {{
      showToast('🏆 Boss #' + data.boss_num + ' DEFEATED! 💰+' + (data.rewards.game_coins||0) + ' 🪙+' + (data.rewards.real_coins||0), '#14532d', '#d1fae5');
      if (data.rewards && data.rewards.real_coins) {{
        var rc = document.getElementById('real-coin-total');
        if (rc) updateEl('real-coin-total', parseInt(rc.textContent) + (data.rewards.real_coins||0), 'coin-pop');
      }}
      if (data.rewards && data.rewards.game_coins) {{
        var gc = document.getElementById('game-coin-total');
        if (gc) updateEl('game-coin-total', parseInt(gc.textContent) + (data.rewards.game_coins||0), 'coin-pop');
      }}
      if (data.level_up && data.level_up.leveled_up) {{
        setTimeout(function() {{
          showToast('⭐ Hero leveled up to Level ' + data.level_up.new_level + '!', '#7c3aed', '#f5f3ff');
        }}, 1000);
      }}
      setTimeout(function() {{ location.reload(); }}, 2500);
    }} else {{
      // Update HP bar
      var bar   = document.getElementById('boss-hp-bar');
      var label = document.getElementById('boss-hp-label');
      if (data.hp_remaining !== undefined) {{
        var total = {boss_hp_tot};
        var pct   = Math.max(0, Math.round(data.hp_remaining / total * 100));
        if (bar)   bar.style.width   = pct + '%';
        if (label) label.textContent = data.hp_remaining.toLocaleString() + ' / ' + total.toLocaleString();
      }}
      showToast('⚔️ Hit! ' + data.hits + ' hits · ' + data.damage.toLocaleString() + ' dmg!', '#1a1a2e', '#f9d77e');
    }}
  }})
  .catch(function() {{ btn.disabled = false; btn.innerHTML = orig; }});
}}

function attackBigBoss(bigBossId, btn) {{
  var useAxe = false;
  var axeTog = document.getElementById('use-axe-toggle');
  if (axeTog) useAxe = axeTog.checked;
  btn.disabled = true;
  var orig = btn.innerHTML;
  btn.innerHTML = '⚔️ Attacking...';
  fetch('/quest/api/attack-big-boss', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey, big_boss_id: bigBossId, use_battle_axe: useAxe}})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(data) {{
    btn.disabled = false; btn.innerHTML = orig;
    if (data.error) {{ showToast('❌ ' + data.error, '#7f1d1d', '#fee2e2'); return; }}
    if (data.energy !== undefined) updateEl('energy-total', data.energy, 'coin-pop');
    if (data.boss_defeated) {{
      showToast('👹 ' + data.big_boss_name + ' DEFEATED! Massive rewards earned!', '#14532d', '#d1fae5');
      setTimeout(function() {{ location.reload(); }}, 2000);
    }} else {{
      showToast('⚔️ ' + data.damage.toLocaleString() + ' dmg to ' + data.big_boss_name + '!', '#1a1a2e', '#f9d77e');
    }}
  }})
  .catch(function() {{ btn.disabled = false; btn.innerHTML = orig; }});
}}

// ── Fortress ──────────────────────────────────────────────────────────────────
function collectFortressIncome(btn) {{
  btn.disabled = true;
  var orig = btn.innerHTML;
  btn.innerHTML = '⏳ Collecting...';
  fetch('/quest/api/collect-fortress', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey}})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(data) {{
    btn.disabled = false; btn.innerHTML = orig;
    if (data.error || !data.ok) {{
      showToast(data.message || data.error || 'Already collected today', '#92400e', '#fef3c7');
      return;
    }}
    updateEl('game-coin-total', parseInt(document.getElementById('game-coin-total').textContent||'0') + data.game_coins, 'coin-pop');
    showToast('🏰 Fortress income! 💰+' + data.game_coins + ' Game Coins', '#14532d', '#d1fae5');
    btn.disabled = true; btn.textContent = '✅ Collected today';
  }})
  .catch(function() {{ btn.disabled = false; btn.innerHTML = orig; }});
}}

function upgradeFortress(btn) {{
  btn.disabled = true;
  var orig = btn.innerHTML;
  btn.innerHTML = '⏳ Upgrading...';
  fetch('/quest/api/upgrade-fortress', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey}})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(data) {{
    btn.disabled = false; btn.innerHTML = orig;
    if (data.error) {{ showToast('❌ ' + data.error, '#7f1d1d', '#fee2e2'); return; }}
    showToast('🏰 Fortress upgraded to Level ' + data.new_level + '! ' + data.new_label, '#14532d', '#d1fae5');
    setTimeout(function() {{ location.reload(); }}, 1500);
  }})
  .catch(function() {{ btn.disabled = false; btn.innerHTML = orig; }});
}}

// ── Mines ─────────────────────────────────────────────────────────────────────
function startMine(mineType, btn) {{
  var useHammer = false;
  var hamTog = document.getElementById('use-hammer-toggle');
  if (hamTog) useHammer = hamTog.checked;
  btn.disabled = true;
  var orig = btn.innerHTML;
  btn.innerHTML = '⛏️ Starting...';
  fetch('/quest/api/start-mine', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey, mine_type: mineType, use_hammer: useHammer}})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(data) {{
    btn.disabled = false; btn.innerHTML = orig;
    if (data.error) {{ showToast('❌ ' + data.error, '#7f1d1d', '#fee2e2'); return; }}
    showToast('⛏️ Mine started! Come back to collect!', '#1a1a2e', '#f9d77e');
    setTimeout(function() {{ location.reload(); }}, 1000);
  }})
  .catch(function() {{ btn.disabled = false; btn.innerHTML = orig; }});
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
  .then(function(r) {{ return r.json(); }})
  .then(function(data) {{
    btn.disabled = false; btn.innerHTML = orig;
    if (data.error) {{ showToast('❌ ' + data.error, '#7f1d1d', '#fee2e2'); return; }}
    var bg    = data.cave_in ? '#7f1d1d' : '#14532d';
    var color = data.cave_in ? '#fee2e2' : '#d1fae5';
    showToast(data.message || '⛏️ Mine collected!', bg, color);
    if (data.real_coins  !== undefined) updateEl('real-coin-total',  data.real_coins,  'coin-pop');
    if (data.game_coins  !== undefined) updateEl('game-coin-total',  data.game_coins,  'coin-pop');
    if (data.crystals    !== undefined) updateEl('crystal-total',    data.crystals,    'coin-pop');
    if (data.diamonds    !== undefined) updateEl('diamond-total',    data.diamonds,    'coin-pop');
    if (data.copper      !== undefined) updateEl('copper-total',     data.copper,      'coin-pop');
    if (data.iron        !== undefined) updateEl('iron-total',       data.iron,        'coin-pop');
    setTimeout(function() {{ location.reload(); }}, 2000);
  }})
  .catch(function() {{ btn.disabled = false; btn.innerHTML = orig; }});
}}

// ── Equipment upgrade ─────────────────────────────────────────────────────────
function upgradeEquipment(slot, btn) {{
  btn.disabled = true;
  var orig = btn.innerHTML;
  btn.innerHTML = '⏳';
  fetch('/quest/api/upgrade-equipment', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey, slot: slot}})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(data) {{
    if (data.error) {{
      btn.disabled = false; btn.innerHTML = orig;
      showToast('❌ ' + data.error, '#7f1d1d', '#fee2e2');
      return;
    }}
    showToast('✨ ' + (data.slot_label||slot) + ' upgraded to Level ' + data.new_level + '!', '#1a1a2e', '#f9d77e');
    if (data.crystals !== undefined) updateEl('crystal-total', data.crystals, 'coin-pop');
    if (data.diamonds !== undefined) updateEl('diamond-total', data.diamonds, 'coin-pop');
    setTimeout(function() {{ location.reload(); }}, 1200);
  }})
  .catch(function() {{ btn.disabled = false; btn.innerHTML = orig; }});
}}

// ── Hero switch ───────────────────────────────────────────────────────────────
function switchHero() {{
  var sel = document.getElementById('hero-select');
  if (!sel) return;
  var heroKey = sel.value;
  fetch('/quest/api/set-hero', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey, hero: heroKey}})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(data) {{
    if (data.error) {{ alert('Error: ' + data.error); return; }}
    showToast('Hero switched! Reloading...', '#1a1a2e', '#f9d77e');
    setTimeout(function() {{ location.reload(); }}, 1000);
  }});
}}

// ── Hero evolution ────────────────────────────────────────────────────────────
function evolveHero(btn) {{
  if (!confirm('Evolve hero? This will consume the required resources.')) return;
  btn.disabled = true;
  var orig = btn.innerHTML;
  btn.innerHTML = '⭐ Evolving...';
  fetch('/quest/api/evolve-hero', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{child: _childKey}})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(data) {{
    btn.disabled = false; btn.innerHTML = orig;
    if (data.error) {{ showToast('❌ ' + data.error, '#7f1d1d', '#fee2e2'); return; }}
    showToast('⭐ Evolution complete! Form 2 unlocked!', '#7c3aed', '#f5f3ff');
    setTimeout(function() {{ location.reload(); }}, 1500);
  }})
  .catch(function() {{ btn.disabled = false; btn.innerHTML = orig; }});
}}

// ── Reward redemption ─────────────────────────────────────────────────────────
function redeemReward(rewardId, label, price, btn) {{
  if (!confirm('Spend 🪙' + price + ' Real Coins on "' + label + '"?\\nMom will need to approve.')) return;
  btn.disabled = true; btn.textContent = '⏳';
  fetch('/quest/api/redeem-reward', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{reward_id: rewardId, child: _childKey}})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(data) {{
    if (data.error) {{ btn.disabled = false; btn.textContent = 'Redeem 🪙' + price; alert(data.error); return; }}
    btn.parentElement.innerHTML = '<div style="font-size:0.75em;color:#d97706;font-weight:700;background:#fef3c7;padding:4px 10px;border-radius:8px;">⏳ Pending mom\'s OK</div>';
    showToast('Request sent! Mom will approve ✅', '#14532d', '#d1fae5');
  }})
  .catch(function() {{ btn.disabled = false; btn.textContent = 'Redeem 🪙' + price; }});
}}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, bg, color) {{
  var toast = document.createElement('div');
  toast.innerHTML = msg;
  toast.style.cssText = 'position:fixed;top:80px;right:20px;background:' + bg + ';color:' + color + ';' +
    'padding:12px 20px;border-radius:14px;font-weight:800;font-size:0.88em;z-index:999;' +
    'animation:toast-in .3s ease;box-shadow:0 4px 20px rgba(0,0,0,.3);max-width:280px;line-height:1.4;';
  document.body.appendChild(toast);
  setTimeout(function() {{ toast.remove(); }}, 3200);
}}
</script>"""

    body = f"""
{R.topbar(viewer, False)}
<div class="fq-main">
  {header}
  {currency_row}
  {resource_row}
  {hero_panel}
  {tab_nav}
  <div id="zones-container">
    {boss_zone}
    {bigboss_zone}
    {fortress_zone}
    {mines_zone}
    {equipment_zone}
    {store_zone}
  </div>
  <hr style="border:none;border-top:1px solid var(--border);margin:24px 0 18px;">
  {summary}
  <div style="font-size:0.82em;font-weight:800;color:var(--ink-muted);text-transform:uppercase;
              letter-spacing:.06em;margin-bottom:12px;">📋 Today's Quests</div>
  {quest_sections}
</div>"""

    return R.html_page(f"{name}'s Quest Board", body, extra_css=extra_css, extra_head=extra_head)
