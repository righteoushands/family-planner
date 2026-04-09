"""
fq_bridge.py — makes Family Quest work inside the main Sancta Familia app
(port 5000) by exposing handle_get(h) / handle_post(h) that accept the
main app's BaseHTTPRequestHandler instance and do all routing.

NOTE: This file intentionally lives on the boundary between the main app
and Family Quest — it is imported by the main app's HTTP server, not by
any Family Quest module.  It is the only exception to the rule that FQ
modules must go through fq_api.py to reach the main app's internals.
When Family Quest moves to a separate Repl, this file will be removed
and the main app will instead proxy /quest/* requests to the FQ server.
"""

import os
import sys
import json
from urllib.parse import parse_qs, urlparse, parse_qsl

_SELF = os.path.dirname(os.path.abspath(__file__))
if _SELF not in sys.path:
    sys.path.insert(0, _SELF)

import fq_auth as _auth
import fq_data as D


# ── Cookie / session helpers ──────────────────────────────────────────────────

def _parse_cookie(h) -> dict:
    raw = h.headers.get("Cookie", "")
    result = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def _get_viewer(h):
    token = _parse_cookie(h).get("fq_session", "")
    return _auth.get_session_user(token) if token else None


def _require_auth(h):
    return _get_viewer(h)


def _set_session_cookie(h, token: str):
    h.send_header("Set-Cookie",
        f"fq_session={token}; Path=/quest; HttpOnly; SameSite=Lax")


def _clear_session_cookie(h):
    h.send_header("Set-Cookie",
        "fq_session=deleted; Path=/quest; HttpOnly; Max-Age=0")


# ── Response helpers ──────────────────────────────────────────────────────────

def _redirect(h, location: str, code: int = 302):
    h.send_response(code)
    h.send_header("Location", location)
    h.end_headers()


def _send_html(h, html: str, code: int = 200):
    h.send_response(code)
    h.send_header("Content-Type", "text/html; charset=utf-8")
    h.end_headers()
    try:
        h.wfile.write(html.encode())
    except BrokenPipeError:
        pass


def _send_json(h, data: dict, code: int = 200):
    body = json.dumps(data).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    try:
        h.wfile.write(body)
    except BrokenPipeError:
        pass


def _read_body(h) -> bytes:
    length = int(h.headers.get("Content-Length", 0))
    return h.rfile.read(length) if length else b""


def _parse_form_multi(h) -> dict:
    body = _read_body(h).decode(errors="replace")
    pairs = parse_qsl(body, keep_blank_values=True)
    result: dict = {}
    for k, v in pairs:
        if k in result:
            existing = result[k]
            if isinstance(existing, list):
                existing.append(v)
            else:
                result[k] = [existing, v]
        else:
            result[k] = v
    return result


def _read_json(h) -> dict:
    try:
        return json.loads(_read_body(h))
    except Exception:
        return {}


# ── Login page ────────────────────────────────────────────────────────────────

def _render_login(error: str = "", redirect_to: str = "/quest/") -> str:
    from html import escape as _esc
    pins_set = _auth.load_pins()
    all_default = all(pins_set.get(u, "0000") == "0000" for u in ("lauren", "john"))

    warning_html = ""
    if all_default:
        warning_html = (
            "<div style='background:#fef3c7;border:1px solid #f59e0b;border-radius:10px;"
            "padding:10px 14px;font-size:0.82em;color:#92400e;margin-bottom:18px;text-align:left;'>"
            "<strong>First-time setup:</strong> All PINs are set to <code>0000</code>. "
            "Log in as Lauren or John and set real PINs in the main app Settings."
            "</div>"
        )

    error_html = ""
    if error:
        error_html = (
            f"<div style='background:#fee2e2;border:1px solid #fca5a5;"
            f"border-radius:10px;padding:8px 14px;font-size:0.85em;color:#991b1b;"
            f"margin-bottom:14px;'>{_esc(error)}</div>"
        )

    avatars_html = ""
    order = ["lauren", "john", "jp", "joseph", "michael", "james"]
    for uid in order:
        u      = _auth.USERS[uid]
        color  = u["color"]
        light  = u["light"]
        name   = u["name"]
        emoji  = u["emoji"]
        no_pin = not u.get("pin_required", True)
        if no_pin:
            click    = f"quickLogin('{uid}')"
            subtitle = "Tap to enter"
        else:
            click    = f"showPin('{uid}','{_esc(name)}')"
            subtitle = "PIN required"

        avatars_html += f"""
<div onclick="{click}" style="display:flex;flex-direction:column;align-items:center;
     gap:8px;cursor:pointer;padding:12px 8px;border-radius:16px;
     transition:background .15s;user-select:none;"
     onmouseenter="this.style.background='{light}'"
     onmouseleave="this.style.background='transparent'">
  <div style="width:72px;height:72px;border-radius:50%;background:{color};
              display:flex;align-items:center;justify-content:center;
              font-size:1.8em;color:white;font-weight:800;
              box-shadow:0 4px 12px {color}55;">
    {emoji}
  </div>
  <div style="font-size:0.88em;font-weight:700;color:#1f2937;">{name}</div>
  <div style="font-size:0.68em;color:#9ca3af;">{subtitle}</div>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1, user-scalable=no">
<title>Family Quest — Login</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    min-height: 100vh;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    font-family: Georgia, "Times New Roman", serif;
    padding: 24px 16px;
  }}
  .card {{
    background: #fdf8f0;
    border-radius: 24px;
    padding: 32px 28px;
    max-width: 480px;
    width: 100%;
    box-shadow: 0 25px 60px rgba(0,0,0,.5);
    text-align: center;
  }}
  .avatar-grid {{ display:grid;grid-template-columns:repeat(3, 1fr);gap:4px;margin-bottom:8px; }}
  #pin-overlay {{
    display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);
    backdrop-filter:blur(4px);z-index:100;align-items:center;
    justify-content:center;padding:20px;
  }}
  #pin-overlay.show {{ display:flex; }}
  #pin-card {{
    background:#fdf8f0;border-radius:20px;padding:28px 24px;
    width:100%;max-width:320px;text-align:center;
    box-shadow:0 20px 50px rgba(0,0,0,.5);
  }}
  .pin-dots {{ display:flex;justify-content:center;gap:14px;margin-bottom:24px; }}
  .pin-dot {{ width:16px;height:16px;border-radius:50%;border:2px solid #d1d5db;background:transparent;transition:all .15s; }}
  .pin-dot.filled {{ background:#1f2937;border-color:#1f2937; }}
  .pin-error {{ font-size:0.8em;color:#dc2626;min-height:20px;margin-bottom:8px; }}
  .keypad {{ display:grid;grid-template-columns:repeat(3,1fr);gap:10px; }}
  .key {{
    padding:14px 8px;border:1.5px solid #e5e7eb;border-radius:12px;
    background:white;font-size:1.2em;font-weight:700;color:#1f2937;
    cursor:pointer;transition:all .1s;font-family:inherit;
  }}
  .key:active,.key:hover {{ background:#f3f4f6;transform:scale(.96); }}
  .key.cancel-btn {{ background:#fef2f2;border-color:#fca5a5;color:#991b1b; }}
</style>
</head>
<body>
<div class="card">
  <div style="font-size:2em;margin-bottom:8px;">&#9876;</div>
  <div style="font-size:1.6em;font-weight:800;color:#1f2937;margin-bottom:4px;">Family Quest</div>
  <div style="font-size:0.82em;color:#9ca3af;font-style:italic;margin-bottom:28px;">Who's playing today?</div>
  {warning_html}
  {error_html}
  <div class="avatar-grid">{avatars_html}</div>
</div>

<form id="quick-form" method="POST" action="/quest/login" style="display:none;">
  <input type="hidden" name="user" id="qf-user">
  <input type="hidden" name="pin"  value="">
  <input type="hidden" name="next" value="{_esc(redirect_to)}">
</form>

<div id="pin-overlay">
  <div id="pin-card">
    <div style="font-size:1.1em;font-weight:800;color:#1f2937;margin-bottom:4px;" id="pin-name"></div>
    <div style="font-size:0.78em;color:#9ca3af;margin-bottom:20px;">Enter your 4-digit PIN</div>
    <div class="pin-dots">
      <div class="pin-dot" id="d0"></div><div class="pin-dot" id="d1"></div>
      <div class="pin-dot" id="d2"></div><div class="pin-dot" id="d3"></div>
    </div>
    <div class="pin-error" id="pin-error"></div>
    <div class="keypad">
      <button class="key" onclick="addDigit('1')">1</button>
      <button class="key" onclick="addDigit('2')">2</button>
      <button class="key" onclick="addDigit('3')">3</button>
      <button class="key" onclick="addDigit('4')">4</button>
      <button class="key" onclick="addDigit('5')">5</button>
      <button class="key" onclick="addDigit('6')">6</button>
      <button class="key" onclick="addDigit('7')">7</button>
      <button class="key" onclick="addDigit('8')">8</button>
      <button class="key" onclick="addDigit('9')">9</button>
      <button class="key cancel-btn" onclick="closePin()">Cancel</button>
      <button class="key" onclick="addDigit('0')">0</button>
      <button class="key" onclick="backspace()">&#9003;</button>
    </div>
  </div>
</div>
<form id="pin-form" method="POST" action="/quest/login" style="display:none;">
  <input type="hidden" name="user" id="pf-user">
  <input type="hidden" name="pin"  id="pf-pin">
  <input type="hidden" name="next" value="{_esc(redirect_to)}">
</form>
<script>
var _pu='',_pv='';
function quickLogin(uid){{document.getElementById('qf-user').value=uid;document.getElementById('quick-form').submit();}}
function showPin(uid,name){{_pu=uid;_pv='';document.getElementById('pin-name').textContent=name;document.getElementById('pin-error').textContent='';updateDots();document.getElementById('pin-overlay').classList.add('show');}}
function closePin(){{document.getElementById('pin-overlay').classList.remove('show');_pv='';updateDots();}}
function addDigit(d){{if(_pv.length>=4)return;_pv+=d;updateDots();if(_pv.length===4)setTimeout(submitPin,120);}}
function backspace(){{_pv=_pv.slice(0,-1);updateDots();document.getElementById('pin-error').textContent='';}}
function updateDots(){{for(var i=0;i<4;i++){{var dot=document.getElementById('d'+i);if(dot)dot.classList.toggle('filled',i<_pv.length);}}}}
function submitPin(){{document.getElementById('pf-user').value=_pu;document.getElementById('pf-pin').value=_pv;document.getElementById('pin-form').submit();}}
</script>
</body>
</html>"""


# ── GET router ────────────────────────────────────────────────────────────────

def handle_get(h) -> bool:
    """
    Call from the main app's do_GET when path starts with /quest.
    Returns True so the caller knows the request was handled.
    """
    route = urlparse(h.path)
    path  = route.path.rstrip("/") or "/quest"
    query = parse_qs(route.query)

    # normalise trailing slash for matching
    path_bare = path.rstrip("/")

    # ── Login ──────────────────────────────────────────────────────────────────
    if path_bare in ("/quest/login", "/quest/login"):
        viewer = _get_viewer(h)
        if viewer:
            dest = "/quest/" if _auth.is_parent(viewer) else f"/quest/board/{viewer}"
            _redirect(h, dest); return True
        redir = query.get("next", ["/quest/"])[0]
        _send_html(h, _render_login(redirect_to=redir)); return True

    # ── Logout ─────────────────────────────────────────────────────────────────
    if path_bare in ("/quest/logout",):
        token = _parse_cookie(h).get("fq_session", "")
        if token:
            _auth.destroy_session(token)
        h.send_response(302)
        _clear_session_cookie(h)
        h.send_header("Location", "/quest/login")
        h.end_headers(); return True

    # ── Auth gate ──────────────────────────────────────────────────────────────
    viewer = _require_auth(h)
    if not viewer:
        from urllib.parse import quote as _q
        _redirect(h, f"/quest/login?next={_q(path)}"); return True

    is_parent = _auth.is_parent(viewer)

    # ── Root → dashboard or board ──────────────────────────────────────────────
    if path_bare in ("/quest", "/quest/dashboard"):
        if is_parent:
            from fq_views_parent import render_parent_dashboard
            _send_html(h, render_parent_dashboard(viewer)); return True
        else:
            _redirect(h, f"/quest/board/{viewer}"); return True

    # ── Parent: quest management ───────────────────────────────────────────────
    if path_bare == "/quest/quests":
        if not is_parent:
            _redirect(h, f"/quest/board/{viewer}"); return True
        from fq_views_parent import render_quests_page
        msg = query.get("msg", [""])[0]
        err = query.get("err", [""])[0]
        _send_html(h, render_quests_page(viewer, msg=msg, err=err)); return True

    # ── Parent: rewards management ─────────────────────────────────────────────
    if path_bare == "/quest/rewards":
        if not is_parent:
            _redirect(h, f"/quest/board/{viewer}"); return True
        from fq_views_parent import render_rewards_page
        msg = query.get("msg", [""])[0]
        err = query.get("err", [""])[0]
        _send_html(h, render_rewards_page(viewer, msg=msg, err=err)); return True

    # ── Child board ────────────────────────────────────────────────────────────
    if path.startswith("/quest/board/"):
        child_key = path[len("/quest/board/"):].strip("/")
        if child_key not in D.CHILDREN_KEYS:
            _redirect(h, "/quest/"); return True
        if not _auth.can_view_child(viewer, child_key):
            _redirect(h, f"/quest/board/{viewer}"); return True
        from fq_views_child import render_child_board
        _send_html(h, render_child_board(child_key, viewer)); return True

    # 404
    _send_html(h, "<h1>Page not found</h1>", 404); return True


# ── POST router ───────────────────────────────────────────────────────────────

def handle_post(h) -> bool:
    """
    Call from the main app's do_POST when path starts with /quest.
    Returns True so the caller knows the request was handled.
    """
    path = urlparse(h.path).path.rstrip("/")

    # ── Login (no auth required) ───────────────────────────────────────────────
    if path in ("/quest/login",):
        form = _parse_form_multi(h)
        user = str(form.get("user", "")).strip().lower()
        pin  = str(form.get("pin",  "")).strip()
        nxt  = str(form.get("next", "/quest/")).strip() or "/quest/"
        if not nxt.startswith("/quest"):
            nxt = "/quest/"
        if _auth.check_pin(user, pin):
            token = _auth.create_session(user)
            h.send_response(302)
            _set_session_cookie(h, token)
            dest = "/quest/" if _auth.is_parent(user) else f"/quest/board/{user}"
            if nxt and nxt != "/quest/login" and nxt.startswith("/quest"):
                dest = nxt
            h.send_header("Location", dest)
            h.end_headers(); return True
        else:
            _send_html(h, _render_login(error="Wrong PIN — try again.", redirect_to=nxt))
            return True

    # ── Auth gate for all other POST ───────────────────────────────────────────
    viewer = _require_auth(h)
    if not viewer:
        _redirect(h, "/quest/login"); return True

    is_parent = _auth.is_parent(viewer)

    # ── Create quest ───────────────────────────────────────────────────────────
    if path == "/quest/quests/create":
        if not is_parent:
            _redirect(h, "/quest/"); return True
        form = _parse_form_multi(h)
        title  = str(form.get("title", "")).strip()
        qtype  = str(form.get("type", "daily"))
        xp_raw = str(form.get("xp_value", "10"))
        xp_val = max(1, int(xp_raw) if xp_raw.isdigit() else 10)
        iso    = str(form.get("date", "")).strip()
        assigned_raw = form.get("assigned_to", [])
        if isinstance(assigned_raw, str):
            assigned = [assigned_raw] if assigned_raw else []
        else:
            assigned = list(assigned_raw)
        if not title:
            _redirect(h, "/quest/quests?err=Title+is+required"); return True
        if not assigned:
            _redirect(h, "/quest/quests?err=Select+at+least+one+child"); return True
        D.create_quest(title, qtype, assigned, xp_val, iso)
        _redirect(h, "/quest/quests?msg=Quest+created"); return True

    # ── Delete quest ───────────────────────────────────────────────────────────
    if path == "/quest/quests/delete":
        if not is_parent:
            _redirect(h, "/quest/"); return True
        form = _parse_form_multi(h)
        D.delete_quest(str(form.get("quest_id", "")))
        _redirect(h, "/quest/quests?msg=Quest+deleted"); return True

    # ── Deactivate quest ───────────────────────────────────────────────────────
    if path == "/quest/quests/deactivate":
        if not is_parent:
            _redirect(h, "/quest/"); return True
        form = _parse_form_multi(h)
        D.deactivate_quest(str(form.get("quest_id", "")))
        _redirect(h, "/quest/quests?msg=Quest+paused"); return True

    # ── Create reward ──────────────────────────────────────────────────────────
    if path == "/quest/rewards/create":
        if not is_parent:
            _redirect(h, "/quest/"); return True
        form = _parse_form_multi(h)
        label      = str(form.get("label", "")).strip()
        xp_raw     = str(form.get("xp_threshold", "0"))
        lvl_raw    = str(form.get("level_threshold", "0"))
        price_raw  = str(form.get("coin_price", "25"))
        xp_thr     = int(xp_raw) if xp_raw.lstrip("-").isdigit() else 0
        lvl_thr    = int(lvl_raw) if lvl_raw.lstrip("-").isdigit() else 0
        coin_price = max(1, int(price_raw) if price_raw.lstrip("-").isdigit() else 25)
        if not label:
            _redirect(h, "/quest/rewards?err=Label+is+required"); return True
        D.create_reward(label, xp_thr, lvl_thr, coin_price)
        _redirect(h, "/quest/rewards?msg=Reward+added"); return True

    # ── Approve redemption ─────────────────────────────────────────────────────
    if path == "/quest/redemptions/approve":
        if not is_parent:
            _redirect(h, "/quest/"); return True
        form = _parse_form_multi(h)
        result = D.approve_redemption(str(form.get("redemption_id", "")))
        if "error" in result:
            _redirect(h, f"/quest/rewards?err={result['error'].replace(' ', '+')}"); return True
        child_name = D.CHILDREN_NAMES.get(result.get("child",""), "")
        _redirect(h, f"/quest/rewards?msg=Approved+for+{child_name.replace(' ', '+')}"); return True

    # ── Reject redemption ──────────────────────────────────────────────────────
    if path == "/quest/redemptions/reject":
        if not is_parent:
            _redirect(h, "/quest/"); return True
        form = _parse_form_multi(h)
        D.reject_redemption(str(form.get("redemption_id", "")))
        _redirect(h, "/quest/rewards?msg=Request+rejected"); return True

    # ── Delete reward ──────────────────────────────────────────────────────────
    if path == "/quest/rewards/delete":
        if not is_parent:
            _redirect(h, "/quest/"); return True
        form = _parse_form_multi(h)
        D.delete_reward(str(form.get("reward_id", "")))
        _redirect(h, "/quest/rewards?msg=Reward+removed"); return True

    # ── API: complete quest (JSON) ─────────────────────────────────────────────
    if path == "/quest/api/complete-quest":
        data = _read_json(h)
        quest_id  = str(data.get("quest_id", ""))
        child_key = str(data.get("child", ""))
        if not (viewer == child_key or is_parent):
            _send_json(h, {"error": "unauthorized"}, 403); return True
        if child_key not in D.CHILDREN_KEYS:
            _send_json(h, {"error": "invalid child"}, 400); return True
        quests = D.load_quests()
        q = next((x for x in quests if x.get("id") == quest_id), None)
        quest_xp = q.get("xp_value", 0) if q else 0
        result = D.complete_quest(quest_id, child_key)
        if "error" in result:
            _send_json(h, result, 400); return True
        if "xp_earned" not in result:
            result["xp_earned"] = quest_xp
        # Include current coin balance for client-side update
        result["coins"] = D.get_coins(child_key)
        _send_json(h, result); return True

    # ── API: redeem reward (child requests purchase) ────────────────────────────
    if path == "/quest/api/redeem-reward":
        data = _read_json(h)
        reward_id = str(data.get("reward_id", ""))
        child_key = str(data.get("child", ""))
        if child_key not in D.CHILDREN_KEYS:
            _send_json(h, {"error": "invalid child"}, 400); return True
        if not (viewer == child_key or is_parent):
            _send_json(h, {"error": "unauthorized"}, 403); return True
        # Check reward exists
        rewards = D.load_rewards()
        reward = next((r for r in rewards if r.get("id") == reward_id), None)
        if not reward:
            _send_json(h, {"error": "Reward not found"}, 404); return True
        # Check not already pending
        already = [r for r in D.load_redemptions()
                   if r.get("child") == child_key and r.get("reward_id") == reward_id
                   and r.get("status") == "pending"]
        if already:
            _send_json(h, {"error": "Already requested — waiting for approval"}); return True
        # Check coins (don't deduct yet — approval deducts)
        price = reward.get("coin_price", 10)
        current_coins = D.get_coins(child_key)
        if current_coins < price:
            _send_json(h, {"error": f"Not enough coins (have {current_coins}, need {price})"}); return True
        result = D.create_redemption(child_key, reward_id, reward.get("label",""), price)
        result["coins"] = D.get_coins(child_key)
        _send_json(h, result); return True

    # ── API: sync chores from Sancta Familia ──────────────────────────────────
    if path == "/quest/sync-chores":
        if not is_parent:
            _send_json(h, {"error": "unauthorized"}, 403); return True
        from fq_data import sync_chores_from_daily_schedule
        result = sync_chores_from_daily_schedule()
        _send_json(h, result); return True

    # 404
    _send_html(h, "<h1>Not found</h1>", 404); return True
