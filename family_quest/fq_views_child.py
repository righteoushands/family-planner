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

    name    = D.CHILDREN_NAMES.get(child_key, child_key.title())
    emoji   = R.CHILD_EMOJI.get(child_key, "⭐")
    colors  = R.CHILD_COLORS.get(child_key, {"bg": "#1f2937", "light": "#f9fafb", "text": "#fff"})
    total   = state["total_xp"]
    lvl     = state["level"]
    nxt     = state["next_level"]
    pct     = state["progress_pct"]

    is_self = (viewer == child_key)
    from fq_auth import is_parent
    can_complete = is_self or is_parent(viewer)

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

            if can_complete and not done:
                action_btn = f"""
<button onclick="completeQuest('{q['id']}', this)"
  style="width:52px;height:52px;border-radius:50%;border:3px solid {tc['bg']};
         background:white;color:{tc['bg']};font-size:1.3em;cursor:pointer;
         flex-shrink:0;transition:all .2s;display:flex;align-items:center;
         justify-content:center;"
  title="Complete quest">○</button>"""
            elif done:
                action_btn = f"""
<div style="width:52px;height:52px;border-radius:50%;background:{tc['bg']};
            display:flex;align-items:center;justify-content:center;
            font-size:1.3em;flex-shrink:0;">✓</div>"""
            else:
                action_btn = f"""
<div style="width:52px;height:52px;border-radius:50%;border:3px solid #e5e7eb;
            display:flex;align-items:center;justify-content:center;
            font-size:1em;flex-shrink:0;color:#9ca3af;">○</div>"""

            done_style = "opacity:.5;text-decoration:line-through;" if done else ""
            cards += f"""
<div class="card" style="padding:14px 16px;{done_style}">
  <div style="display:flex;align-items:center;gap:14px;">
    {action_btn}
    <div style="flex:1;min-width:0;">
      <div style="font-size:1em;font-weight:700;color:var(--ink);">{_esc(q.get('title',''))}</div>
      <div style="margin-top:4px;">
        <span class="badge" style="background:{tc['bg']}22;color:{tc['bg']};font-size:0.75em;">
          {tc['icon']} {tc['label']}
        </span>
        <span style="margin-left:8px;font-size:0.8em;font-weight:700;color:{'#15803d' if done else '#d97706'};">
          {'✓ +' if done else '+'}{xp_val} XP
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
  <div style="font-size:3em;margin-bottom:12px;">🗡️</div>
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
  {'<div style="text-align:center;margin-top:10px;font-size:1.2em;">🎉 All done!</div>' if total_done == total_quests and total_quests > 0 else ''}
</div>"""
    else:
        summary = ""

    # ── Rewards panel ───────────────────────────────────────────────────────────
    cur_level = lvl["level"]
    reward_cards = ""
    for r in rewards:
        xp_req  = r.get("xp_threshold", 0)
        lvl_req = r.get("level_threshold", 0)
        unlocked = (xp_req == 0 or total >= xp_req) and (lvl_req == 0 or cur_level >= lvl_req)
        threshold_txt = ""
        if xp_req:
            threshold_txt += f"{xp_req} XP"
        if lvl_req:
            threshold_txt += (" · " if threshold_txt else "") + f"Level {lvl_req}"
        if not threshold_txt:
            threshold_txt = "Always available"

        lock_icon = "🔓" if unlocked else "🔒"
        bg = "#f0fdf4" if unlocked else "#f9fafb"
        border = "#86efac" if unlocked else "#e5e7eb"
        reward_cards += f"""
<div style="display:flex;align-items:center;gap:10px;padding:12px 14px;
            background:{bg};border:1px solid {border};border-radius:12px;margin-bottom:8px;">
  <span style="font-size:1.4em;">{lock_icon}</span>
  <div style="flex:1;">
    <div style="font-weight:700;color:var(--ink);font-size:0.95em;">{_esc(r.get('label',''))}</div>
    <div style="font-size:0.74em;color:var(--ink-muted);">{threshold_txt}</div>
  </div>
</div>"""

    rewards_section = ""
    if rewards:
        rewards_section = f"""
<div class="card" style="margin-top:8px;">
  <div class="card-title">🎁 Rewards</div>
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
"""

    extra_head = """
<script>
function completeQuest(questId, btn) {
  btn.disabled = true;
  btn.style.opacity = '0.5';
  fetch('/quest/api/complete-quest', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({quest_id: questId, child: '""" + child_key + """'})
  })
  .then(r => r.json())
  .then(data => {
    if (data.error) {
      btn.disabled = false; btn.style.opacity = '1';
      alert('Error: ' + data.error); return;
    }
    // Update XP display
    var xpEl = document.getElementById('xp-total');
    var barEl = document.getElementById('xp-bar');
    if (xpEl) {
      xpEl.textContent = data.total_xp;
      xpEl.classList.remove('xp-pop');
      void xpEl.offsetWidth;
      xpEl.classList.add('xp-pop');
    }
    if (barEl) {
      barEl.style.width = data.progress_pct + '%';
    }
    // Mark quest card as done visually
    var card = btn.closest('.card');
    if (card) {
      card.style.opacity = '.5';
      card.style.textDecoration = 'line-through';
    }
    // Replace button with checkmark
    var circle = btn.parentElement;
    circle.innerHTML = '<div style="width:52px;height:52px;border-radius:50%;background:currentColor;display:flex;align-items:center;justify-content:center;font-size:1.3em;flex-shrink:0;animation:check-pop .3s ease;">✓</div>';
    // Show XP toast
    showXpToast('+' + data.xp_earned + ' XP');
    // Update level if changed
    if (data.level) {
      document.title = 'Level ' + data.level.level + ' — Family Quest';
    }
  })
  .catch(() => { btn.disabled = false; btn.style.opacity = '1'; });
}

function showXpToast(msg) {
  var toast = document.createElement('div');
  toast.textContent = msg;
  toast.style.cssText = 'position:fixed;top:80px;right:20px;background:#1a1a2e;color:#f9d77e;' +
    'padding:10px 18px;border-radius:12px;font-weight:800;font-size:1em;z-index:999;' +
    'animation:xp-pop .4s ease;box-shadow:0 4px 16px rgba(0,0,0,.3);';
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2200);
}
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
