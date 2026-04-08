"""
family_quest/app.py — HTTP server and router for Family Quest.
Runs on port 8080 (or $FQ_PORT).
Shares child/parent auth with the main Sancta Familia app.
"""
import os
import sys
import json

# ── Add parent directory to path so we can import auth.py etc ─────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── Add this directory to path for local imports ───────────────────────────────
_SELF = os.path.dirname(os.path.abspath(__file__))
if _SELF not in sys.path:
    sys.path.insert(0, _SELF)

# ── Pin timezone ───────────────────────────────────────────────────────────────
os.environ.setdefault("TZ", "America/New_York")
import time as _time
_time.tzset()

from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
from urllib.parse import parse_qs, urlparse, parse_qsl

import fq_auth as _auth
import fq_data as D
import fq_render as R

HOST = "0.0.0.0"
PORT = int(os.environ.get("FQ_PORT", 8080))


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
  <div style="font-size:2em;margin-bottom:8px;">⚔️</div>
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


# ── Request handler ───────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # suppress default access log

    def _parse_cookie(self) -> dict:
        raw = self.headers.get("Cookie", "")
        result = {}
        for part in raw.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                result[k.strip()] = v.strip()
        return result

    def _get_viewer(self):
        token = self._parse_cookie().get("fq_session", "")
        return _auth.get_session_user(token) if token else None

    def _set_session_cookie(self, token: str):
        self.send_header("Set-Cookie",
            f"fq_session={token}; Path=/quest; HttpOnly; SameSite=Lax")

    def _clear_session_cookie(self):
        self.send_header("Set-Cookie",
            "fq_session=deleted; Path=/quest; HttpOnly; Max-Age=0")

    def _redirect(self, location: str, code: int = 302):
        self.send_response(code)
        self.send_header("Location", location)
        self.end_headers()

    def _send_html(self, html: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        try:
            self.wfile.write(html.encode())
        except BrokenPipeError:
            pass

    def _send_json(self, data: dict, code: int = 200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def _parse_form_multi(self) -> dict:
        """Parse form body preserving multi-value fields (e.g. checkboxes)."""
        body = self._read_body().decode(errors="replace")
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

    def _read_json(self) -> dict:
        try:
            return json.loads(self._read_body())
        except Exception:
            return {}

    def _require_auth(self) -> str | None:
        viewer = self._get_viewer()
        return viewer if viewer else None

    # ── GET ───────────────────────────────────────────────────────────────────

    def do_GET(self):
        route = urlparse(self.path)
        path  = route.path
        query = parse_qs(route.query)

        # ── Login ──────────────────────────────────────────────────────────────
        if path in ("/quest/login", "/quest/login/"):
            viewer = self._get_viewer()
            if viewer:
                dest = "/quest/" if _auth.is_parent(viewer) else f"/quest/board/{viewer}"
                self._redirect(dest); return
            redir = query.get("next", ["/quest/"])[0]
            self._send_html(_render_login(redirect_to=redir)); return

        # ── Logout ─────────────────────────────────────────────────────────────
        if path in ("/quest/logout", "/quest/logout/"):
            token = self._parse_cookie().get("fq_session", "")
            if token:
                _auth.destroy_session(token)
            self.send_response(302)
            self._clear_session_cookie()
            self.send_header("Location", "/quest/login")
            self.end_headers(); return

        # ── Root redirect (if no /quest prefix) ────────────────────────────────
        if path in ("/", ""):
            self._redirect("/quest/"); return

        # ── Auth gate ──────────────────────────────────────────────────────────
        viewer = self._require_auth()
        if not viewer:
            from urllib.parse import quote as _q
            self._redirect(f"/quest/login?next={_q(path)}"); return

        is_parent = _auth.is_parent(viewer)

        # ── Root → dashboard or board ──────────────────────────────────────────
        if path in ("/quest", "/quest/", "/quest/dashboard"):
            if is_parent:
                from fq_views_parent import render_parent_dashboard
                self._send_html(render_parent_dashboard(viewer)); return
            else:
                self._redirect(f"/quest/board/{viewer}"); return

        # ── Parent: quest management ───────────────────────────────────────────
        if path in ("/quest/quests", "/quest/quests/"):
            if not is_parent:
                self._redirect(f"/quest/board/{viewer}"); return
            from fq_views_parent import render_quests_page
            msg = query.get("msg", [""])[0]
            err = query.get("err", [""])[0]
            self._send_html(render_quests_page(viewer, msg=msg, err=err)); return

        # ── Parent: rewards management ─────────────────────────────────────────
        if path in ("/quest/rewards", "/quest/rewards/"):
            if not is_parent:
                self._redirect(f"/quest/board/{viewer}"); return
            from fq_views_parent import render_rewards_page
            msg = query.get("msg", [""])[0]
            err = query.get("err", [""])[0]
            self._send_html(render_rewards_page(viewer, msg=msg, err=err)); return

        # ── Child board ────────────────────────────────────────────────────────
        if path.startswith("/quest/board/"):
            child_key = path[len("/quest/board/"):].strip("/")
            if child_key not in D.CHILDREN_KEYS:
                self._redirect("/quest/"); return
            if not _auth.can_view_child(viewer, child_key):
                self._redirect(f"/quest/board/{viewer}"); return
            from fq_views_child import render_child_board
            self._send_html(render_child_board(child_key, viewer)); return

        # 404
        self._send_html("<h1>Page not found</h1>", 404)

    # ── POST ──────────────────────────────────────────────────────────────────

    def do_POST(self):
        path = urlparse(self.path).path

        # ── Login (no auth required) ───────────────────────────────────────────
        if path in ("/quest/login", "/quest/login/"):
            form = self._parse_form_multi()
            user = str(form.get("user", "")).strip().lower()
            pin  = str(form.get("pin",  "")).strip()
            nxt  = str(form.get("next", "/quest/")).strip() or "/quest/"
            if not nxt.startswith("/quest"):
                nxt = "/quest/"
            if _auth.check_pin(user, pin):
                token = _auth.create_session(user)
                self.send_response(302)
                self._set_session_cookie(token)
                dest = "/quest/" if _auth.is_parent(user) else f"/quest/board/{user}"
                if nxt and nxt != "/quest/login" and nxt.startswith("/quest"):
                    dest = nxt
                self.send_header("Location", dest)
                self.end_headers(); return
            else:
                self._send_html(_render_login(
                    error="Wrong PIN — try again.",
                    redirect_to=nxt
                )); return

        # ── Auth gate for all other POST ───────────────────────────────────────
        viewer = self._require_auth()
        if not viewer:
            self._redirect("/quest/login"); return

        is_parent = _auth.is_parent(viewer)

        # ── Create quest ───────────────────────────────────────────────────────
        if path in ("/quest/quests/create", "/quest/quests/create/"):
            if not is_parent:
                self._redirect("/quest/"); return
            form = self._parse_form_multi()
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
                self._redirect("/quest/quests?err=Title+is+required"); return
            if not assigned:
                self._redirect("/quest/quests?err=Select+at+least+one+child"); return

            D.create_quest(title, qtype, assigned, xp_val, iso)
            self._redirect("/quest/quests?msg=Quest+created"); return

        # ── Delete quest ───────────────────────────────────────────────────────
        if path in ("/quest/quests/delete", "/quest/quests/delete/"):
            if not is_parent:
                self._redirect("/quest/"); return
            form = self._parse_form_multi()
            D.delete_quest(str(form.get("quest_id", "")))
            self._redirect("/quest/quests?msg=Quest+deleted"); return

        # ── Deactivate quest ───────────────────────────────────────────────────
        if path in ("/quest/quests/deactivate", "/quest/quests/deactivate/"):
            if not is_parent:
                self._redirect("/quest/"); return
            form = self._parse_form_multi()
            D.deactivate_quest(str(form.get("quest_id", "")))
            self._redirect("/quest/quests?msg=Quest+paused"); return

        # ── Create reward ──────────────────────────────────────────────────────
        if path in ("/quest/rewards/create", "/quest/rewards/create/"):
            if not is_parent:
                self._redirect("/quest/"); return
            form = self._parse_form_multi()
            label    = str(form.get("label", "")).strip()
            xp_raw   = str(form.get("xp_threshold", "0"))
            lvl_raw  = str(form.get("level_threshold", "0"))
            xp_thr   = int(xp_raw) if xp_raw.lstrip("-").isdigit() else 0
            lvl_thr  = int(lvl_raw) if lvl_raw.lstrip("-").isdigit() else 0
            if not label:
                self._redirect("/quest/rewards?err=Label+is+required"); return
            D.create_reward(label, xp_thr, lvl_thr)
            self._redirect("/quest/rewards?msg=Reward+added"); return

        # ── Delete reward ──────────────────────────────────────────────────────
        if path in ("/quest/rewards/delete", "/quest/rewards/delete/"):
            if not is_parent:
                self._redirect("/quest/"); return
            form = self._parse_form_multi()
            D.delete_reward(str(form.get("reward_id", "")))
            self._redirect("/quest/rewards?msg=Reward+removed"); return

        # ── API: complete quest (JSON) ──────────────────────────────────────────
        if path in ("/quest/api/complete-quest", "/quest/api/complete-quest/"):
            data = self._read_json()
            quest_id  = str(data.get("quest_id", ""))
            child_key = str(data.get("child", ""))

            if not (viewer == child_key or is_parent):
                self._send_json({"error": "unauthorized"}, 403); return

            if child_key not in D.CHILDREN_KEYS:
                self._send_json({"error": "invalid child"}, 400); return

            quests = D.load_quests()
            q = next((x for x in quests if x.get("id") == quest_id), None)
            quest_xp = q.get("xp_value", 0) if q else 0

            result = D.complete_quest(quest_id, child_key)
            if "error" in result:
                self._send_json(result, 400); return

            # If complete_quest already set xp_earned=0 (idempotent), keep it;
            # otherwise set it to the quest's XP value.
            if "xp_earned" not in result:
                result["xp_earned"] = quest_xp
            self._send_json(result); return

        # 404
        self._send_html("<h1>Not found</h1>", 404)


# ── Server setup ──────────────────────────────────────────────────────────────

class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    print(f"Family Quest starting on {HOST}:{PORT}")
    server = ThreadedHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Family Quest stopped.")
