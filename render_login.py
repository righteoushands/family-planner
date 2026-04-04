"""
render_login.py — Family login screen.

Avatar grid → tap Michael/James = instant login (no PIN).
Tap any other member → PIN pad (4 digits).
Auto-submits when 4 digits are entered.
"""
from html import escape
from auth import USERS, get_pin, unread_count


def render_login_page(error: str = "", redirect_to: str = "/") -> str:
    from auth import load_pins
    pins_set = load_pins()
    all_default = all(pins_set.get(u, "0000") == "0000" for u in ("lauren", "john"))

    warning_html = ""
    if all_default:
        warning_html = (
            "<div style='background:#fef3c7;border:1px solid #f59e0b;border-radius:10px;"
            "padding:10px 14px;font-size:0.82em;color:#92400e;margin-bottom:18px;text-align:left;max-width:380px;'>"
            "<strong>First-time setup:</strong> All PINs are set to <code>0000</code>. "
            "Log in as Lauren or John and go to Settings to set real PINs."
            "</div>"
        )

    error_html = ""
    if error:
        error_html = (
            f"<div id='login-error' style='background:#fee2e2;border:1px solid #fca5a5;"
            f"border-radius:10px;padding:8px 14px;font-size:0.85em;color:#991b1b;"
            f"margin-bottom:14px;'>{escape(error)}</div>"
        )

    # Build avatar buttons
    avatars_html = ""
    order = ["lauren", "john", "jp", "joseph", "michael", "james"]
    for uid in order:
        u = USERS[uid]
        color  = u["color"]
        light  = u["light"]
        name   = u["name"]
        emoji  = u["emoji"]
        no_pin = not u.get("pin_required", True)

        if no_pin:
            # Tap → immediate POST
            click = f"quickLogin('{uid}')"
            subtitle = "Tap to enter"
        else:
            click = f"showPin('{uid}','{escape(name)}')"
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
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1">
<title>McAdams Family</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    min-height: 100vh;
    background: #1a1a2e;
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
  .family-name {{
    font-size: 0.72em;
    font-weight: 800;
    letter-spacing: .18em;
    text-transform: uppercase;
    color: #9ca3af;
    margin-bottom: 4px;
  }}
  h1 {{
    font-size: 1.7em;
    color: #1f2937;
    margin-bottom: 6px;
  }}
  .tagline {{
    font-size: 0.82em;
    color: #9ca3af;
    font-style: italic;
    margin-bottom: 28px;
  }}
  .avatar-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
    margin-bottom: 8px;
  }}

  /* PIN modal */
  #pin-overlay {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.7);
    backdrop-filter: blur(4px);
    z-index: 100;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }}
  #pin-overlay.show {{ display: flex; }}
  #pin-card {{
    background: #fdf8f0;
    border-radius: 20px;
    padding: 28px 24px;
    width: 100%;
    max-width: 320px;
    text-align: center;
    box-shadow: 0 20px 50px rgba(0,0,0,.5);
  }}
  .pin-name {{
    font-size: 1.1em;
    font-weight: 800;
    color: #1f2937;
    margin-bottom: 4px;
  }}
  .pin-hint {{ font-size:0.78em;color:#9ca3af;margin-bottom:20px; }}
  .pin-dots {{
    display: flex;
    justify-content: center;
    gap: 14px;
    margin-bottom: 24px;
  }}
  .pin-dot {{
    width: 16px; height: 16px;
    border-radius: 50%;
    border: 2px solid #d1d5db;
    background: transparent;
    transition: all .15s;
  }}
  .pin-dot.filled {{
    background: #1f2937;
    border-color: #1f2937;
  }}
  .pin-error {{
    font-size:0.8em;color:#dc2626;min-height:20px;margin-bottom:8px;
  }}
  .keypad {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }}
  .key {{
    padding: 14px 8px;
    border: 1.5px solid #e5e7eb;
    border-radius: 12px;
    background: white;
    font-size: 1.2em;
    font-weight: 700;
    color: #1f2937;
    cursor: pointer;
    transition: all .1s;
    font-family: inherit;
  }}
  .key:active, .key:hover {{ background: #f3f4f6; transform: scale(.96); }}
  .key.wide {{ grid-column: span 2; font-size:1em; }}.key.back {{ font-size:1em; }}
  .key.cancel-btn {{ background:#fef2f2;border-color:#fca5a5;color:#991b1b; }}
  @keyframes shake {{
    0%,100%{{ transform:translateX(0) }}
    20%{{ transform:translateX(-8px) }}
    40%{{ transform:translateX(8px) }}
    60%{{ transform:translateX(-5px) }}
    80%{{ transform:translateX(5px) }}
  }}
  .shake {{ animation: shake .35s ease; }}
</style>
</head>
<body>

<div class="card">
  <div class="family-name">McAdams Family</div>
  <h1>Welcome home.</h1>
  <div class="tagline">Who's using the dashboard?</div>

  {warning_html}
  {error_html}

  <div class="avatar-grid">
    {avatars_html}
  </div>
</div>

<!-- Hidden form for quick (no-PIN) logins -->
<form id="quick-form" method="POST" action="/login" style="display:none;">
  <input type="hidden" name="user" id="qf-user">
  <input type="hidden" name="pin"  value="">
  <input type="hidden" name="next" value="{escape(redirect_to)}">
</form>

<!-- PIN overlay -->
<div id="pin-overlay">
  <div id="pin-card">
    <div class="pin-name" id="pin-name">JP</div>
    <div class="pin-hint">Enter your 4-digit PIN</div>
    <div class="pin-dots">
      <div class="pin-dot" id="d0"></div>
      <div class="pin-dot" id="d1"></div>
      <div class="pin-dot" id="d2"></div>
      <div class="pin-dot" id="d3"></div>
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
      <button class="key back" onclick="backspace()">&#9003;</button>
    </div>
  </div>
</div>

<!-- Hidden PIN form -->
<form id="pin-form" method="POST" action="/login" style="display:none;">
  <input type="hidden" name="user" id="pf-user">
  <input type="hidden" name="pin"  id="pf-pin">
  <input type="hidden" name="next" value="{escape(redirect_to)}">
</form>

<script>
var _pinUser = '';
var _pinVal  = '';

function quickLogin(uid) {{
  document.getElementById('qf-user').value = uid;
  document.getElementById('quick-form').submit();
}}

function showPin(uid, name) {{
  _pinUser = uid;
  _pinVal  = '';
  document.getElementById('pin-name').textContent = name;
  document.getElementById('pin-error').textContent = '';
  updateDots();
  document.getElementById('pin-overlay').classList.add('show');
}}

function closePin() {{
  document.getElementById('pin-overlay').classList.remove('show');
  _pinVal = ''; updateDots();
}}

function addDigit(d) {{
  if (_pinVal.length >= 4) return;
  _pinVal += d;
  updateDots();
  if (_pinVal.length === 4) {{
    setTimeout(submitPin, 120);
  }}
}}

function backspace() {{
  _pinVal = _pinVal.slice(0, -1);
  updateDots();
  document.getElementById('pin-error').textContent = '';
}}

function updateDots() {{
  for (var i = 0; i < 4; i++) {{
    var dot = document.getElementById('d' + i);
    if (dot) dot.classList.toggle('filled', i < _pinVal.length);
  }}
}}

function submitPin() {{
  document.getElementById('pf-user').value = _pinUser;
  document.getElementById('pf-pin').value  = _pinVal;
  document.getElementById('pin-form').submit();
}}
</script>
</body>
</html>"""
