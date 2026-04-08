"""
fq_views_child.py — Child-facing quest board for Family Quest.
Designed for age-flexibility: big tap targets, colorful, game-like.
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

    name    = D.CHILDREN_NAMES.get(child_key, child_key.title())
    emoji   = R.CHILD_EMOJI.get(child_key, "⭐")
    colors  = R.CHILD_COLORS.get(child_key, {"bg": "#1f2937", "light": "#f9fafb", "text": "#fff"})
    total   = state["total_xp"]
    coins   = state.get("coins", 0)
    lvl     = state["level"]
    nxt     = state["next_level"]
    pct     = state["progress_pct"]

    is_self = (viewer == child_key)
    from fq_auth import is_parent
    can_complete = is_self or is_parent(viewer)

    # ── Streak display ──────────────────────────────────────────────────────────
    cur_streak = streak.get("current", 0)
    best_streak = streak.get("best", 0)
    if cur_streak >= 3:
        streak_color = "#dc2626"   # red flame for big streaks
    elif cur_streak >= 1:
        streak_color = "#d97706"   # amber for building
    else:
        streak_color = "#9ca3af"   # grey for none

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

    # ── Header card ────────────────────────────────────────────────────────────
    next_line = (
        f"<div style='font-size:0.82em;color:#e5e7eb;margin-top:2px;'>"
        f"{nxt['xp_min'] - total} XP to Level {nxt['level']} — {_esc(nxt['label'])}"
        f"</div>"
    ) if nxt else "<div style='font-size:0.82em;color:#f9d77e;margin-top:2px;'>Max level reached! 🏆</div>"

    header = f"""
<div style="background:{colors['bg']};border-radius:20px;padding:22px 20px 20px;
            color:white;margin-bottom:22px;position:relative;overflow:hidden;">
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
      <div style="margin-top:6px;background:rgba(255,255,255,.18);border-radius:8px;
                  padding:3px 8px;display:inline-block;">
        <span style="font-size:1em;">🪙</span>
        <span id="coin-total" style="font-size:0.9em;font-weight:800;">{coins}</span>
      </div>
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
</div>"""

    # ── Group quests by type ────────────────────────────────────────────────────
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
<div class="card" style="background:linear-gradient(135deg,#f9fafb,#f3f4f6);border-color:#e5e7eb;margin-bottom:22px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <div style="font-weight:800;color:var(--ink);">Today's Progress</div>
    <div style="font-weight:800;color:{colors['bg']};">{total_done}/{total_quests}</div>
  </div>
  <div class="xp-bar-wrap" style="height:14px;">
    <div class="xp-bar-fill" style="width:{prog_pct}%;background:{colors['bg']};"></div>
  </div>
  {'<div style="text-align:center;margin-top:10px;font-size:1.2em;">&#127881; All done!</div>' if total_done == total_quests and total_quests > 0 else ''}
</div>"""
    else:
        summary = ""

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

        bg     = "#f0fdf4" if can_buy else "#f9fafb"
        border = "#86efac" if can_buy else "#e5e7eb"
        reward_cards += f"""
<div style="display:flex;align-items:center;gap:10px;padding:12px 14px;
            background:{bg};border:1px solid {border};border-radius:12px;margin-bottom:8px;">
  <span style="font-size:1.4em;">{"🎁" if can_buy else "🔒"}</span>
  <div style="flex:1;">
    <div style="font-weight:700;color:var(--ink);font-size:0.95em;">{_esc(r.get('label',''))}</div>
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
    // Update XP display
    var xpEl = document.getElementById('xp-total');
    var barEl = document.getElementById('xp-bar');
    if (xpEl) {{
      xpEl.textContent = data.total_xp;
      xpEl.classList.remove('xp-pop');
      void xpEl.offsetWidth;
      xpEl.classList.add('xp-pop');
    }}
    if (barEl) barEl.style.width = data.progress_pct + '%';

    // Mark quest card as done visually
    var card = btn.closest('.card');
    if (card) {{ card.style.opacity = '.5'; card.style.textDecoration = 'line-through'; }}

    // Replace button with checkmark
    var circle = btn.parentElement;
    circle.innerHTML = '<div style="width:52px;height:52px;border-radius:50%;background:currentColor;display:flex;align-items:center;justify-content:center;font-size:1.3em;flex-shrink:0;animation:check-pop .3s ease;">&#10003;</div>';

    // Update coin display
    var coinEl = document.getElementById('coin-total');
    if (coinEl && data.coins !== undefined) coinEl.textContent = data.coins;

    // XP toast
    var toastMsg = '+' + data.xp_earned + ' XP  🪙+' + data.xp_earned;
    showToast(toastMsg, '#1a1a2e', '#f9d77e');

    // Streak milestone bonus toast
    if (data.streak_bonus && data.streak_bonus > 0) {{
      setTimeout(function() {{
        showToast('&#128293; ' + data.streak.current + '-Day Streak! +' + data.streak_bonus + ' Bonus XP', '#7c2d12', '#fef3c7');
      }}, 600);
    }}

    // Streak count update
    if (data.streak) {{
      var sc = document.getElementById('streak-count');
      if (sc) {{
        var n = data.streak.current;
        sc.textContent = n + ' day' + (n !== 1 ? 's' : '') + ' streak';
      }}
    }}

    // Level up?
    if (data.level) {{
      document.title = 'Level ' + data.level.level + ' \u2014 Family Quest';
    }}
  }})
  .catch(() => {{ btn.disabled = false; btn.style.opacity = '1'; }});
}}

function redeemReward(rewardId, label, price, btn) {{
  if (!confirm('Spend 🪙' + price + ' coins on "' + label + '"?\nMom will need to approve it.')) return;
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

function showToast(msg, bg, color) {{
  var toast = document.createElement('div');
  toast.innerHTML = msg;
  toast.style.cssText = 'position:fixed;top:80px;right:20px;background:' + bg + ';color:' + color + ';' +
    'padding:12px 20px;border-radius:14px;font-weight:800;font-size:1em;z-index:999;' +
    'animation:toast-in .3s ease;box-shadow:0 4px 20px rgba(0,0,0,.3);max-width:260px;';
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2800);
}}
</script>"""

    body = f"""
{R.topbar(viewer, False)}
<div class="fq-main">
  {header}
  {summary}
  {quest_sections}
  {rewards_section}
</div>"""

    return R.html_page(f"{name}'s Quest Board", body, extra_css=extra_css, extra_head=extra_head)
