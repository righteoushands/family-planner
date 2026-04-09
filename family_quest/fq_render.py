"""
fq_render.py — HTML rendering helpers for Family Quest.
Provides the common page shell and shared UI components.
"""
from html import escape as _esc


# ── Color palette (matches Sancta Familia's warm editorial aesthetic) ──────────
CHILD_COLORS = {
    "jp":      {"bg": "#b91c1c", "light": "#fef2f2", "text": "#fff"},
    "joseph":  {"bg": "#15803d", "light": "#f0fdf4", "text": "#fff"},
    "michael": {"bg": "#c2410c", "light": "#fff7ed", "text": "#fff"},
    "james":   {"bg": "#6d28d9", "light": "#f5f3ff", "text": "#fff"},
}

CHILD_NAMES = {"jp": "JP", "joseph": "Joseph", "michael": "Michael", "james": "James"}
CHILD_EMOJI = {"jp": "⚓", "joseph": "🛡", "michael": "🚂", "james": "🐣"}

TYPE_COLORS = {
    "daily": {"bg": "#1d4ed8", "light": "#eff6ff", "icon": "☀️", "label": "Daily"},
    "side":  {"bg": "#15803d", "light": "#f0fdf4", "icon": "⚡", "label": "Side"},
    "boss":  {"bg": "#b91c1c", "light": "#fef2f2", "icon": "🏆", "label": "Boss"},
    "event": {"bg": "#7c3aed", "light": "#f5f3ff", "icon": "🎉", "label": "Event"},
}

BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --ink:          #1f2937;
  --ink-muted:    #6b7280;
  --ink-faint:    #d1d5db;
  --parchment:    #fdf8f0;
  --warm-white:   #fffef9;
  --gold:         #92400e;
  --gold-light:   #fef3c7;
  --gold-mid:     #d97706;
  --border:       #e5d8c5;
  --border-light: #f0e8d8;
  --card-shadow:  0 2px 12px rgba(0,0,0,.08);
}
body {
  background: var(--parchment);
  color: var(--ink);
  font-family: Georgia, "Times New Roman", serif;
  min-height: 100vh;
  line-height: 1.5;
}
.fq-topbar {
  background: #1a1a2e;
  color: #f9fafb;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  position: sticky;
  top: 0;
  z-index: 50;
  box-shadow: 0 2px 8px rgba(0,0,0,.3);
}
.fq-topbar-title {
  font-size: 1em;
  font-weight: 800;
  letter-spacing: .04em;
  color: #f9d77e;
  flex: 1;
}
.fq-topbar a {
  color: #e5e7eb;
  text-decoration: none;
  font-size: 0.82em;
  font-weight: 600;
  padding: 5px 10px;
  border-radius: 8px;
  transition: background .15s;
}
.fq-topbar a:hover { background: rgba(255,255,255,.12); }
.fq-main {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 16px 48px;
}
.card {
  background: var(--warm-white);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px;
  box-shadow: var(--card-shadow);
  margin-bottom: 18px;
}
.card-title {
  font-size: 1.05em;
  font-weight: 800;
  color: var(--ink);
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  gap: 8px;
}
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 16px;
  border: none;
  border-radius: 10px;
  font-size: 0.88em;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  text-decoration: none;
  transition: opacity .15s, transform .1s;
}
.btn:active { transform: scale(.97); }
.btn-primary { background: #1a1a2e; color: #f9d77e; }
.btn-danger  { background: #fef2f2; color: #b91c1c; border: 1px solid #fca5a5; }
.btn-muted   { background: #f3f4f6; color: #374151; }
.btn-sm { padding: 6px 11px; font-size: 0.78em; }
label {
  display: block;
  font-size: 0.8em;
  font-weight: 600;
  color: var(--ink-muted);
  margin-bottom: 5px;
}
input[type=text], input[type=number], input[type=date], select, textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1.5px solid var(--border);
  border-radius: 10px;
  font-size: 0.92em;
  font-family: inherit;
  background: var(--warm-white);
  color: var(--ink);
  outline: none;
  transition: border-color .15s;
}
input:focus, select:focus, textarea:focus { border-color: var(--gold-mid); }
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}
@media (max-width: 560px) {
  .form-row { grid-template-columns: 1fr; }
}
.form-group { margin-bottom: 14px; }
.alert {
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 0.88em;
  font-weight: 600;
  margin-bottom: 16px;
}
.alert-ok  { background: #f0fdf4; border: 1px solid #86efac; color: #15803d; }
.alert-err { background: #fef2f2; border: 1px solid #fca5a5; color: #b91c1c; }
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 0.72em;
  font-weight: 700;
  letter-spacing: .03em;
}
.xp-bar-wrap {
  background: #e5e7eb;
  border-radius: 20px;
  height: 10px;
  overflow: hidden;
}
.xp-bar-fill {
  height: 100%;
  border-radius: 20px;
  transition: width .5s ease;
}
h1 { font-size: 1.6em; font-weight: 800; margin-bottom: 4px; }
h2 { font-size: 1.2em; font-weight: 800; margin-bottom: 12px; }
"""


def html_page(title: str, body: str, extra_css: str = "", extra_head: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1, user-scalable=no">
<title>{_esc(title)} — Family Quest</title>
<style>
{BASE_CSS}
{extra_css}
</style>
{extra_head}
</head>
<body>
{body}
</body>
</html>"""


def topbar(viewer: str, is_parent: bool) -> str:
    from fq_auth import USERS
    u = USERS.get(viewer, {})
    name = u.get("name", viewer.title())
    home = "/quest/" if is_parent else f"/quest/board/{viewer}"
    links = ""
    if is_parent:
        links = (
            f'<a href="/quest/">Dashboard</a>'
            f'<a href="/quest/quests">Quests</a>'
            f'<a href="/quest/rewards">Rewards</a>'
            f'<a href="/quest/boss-settings">⚔️ Boss</a>'
        )
    return (
        f'<div class="fq-topbar">'
        f'  <a href="{home}" class="fq-topbar-title">⚔️ Family Quest</a>'
        f'  {links}'
        f'  <a href="/quest/logout" style="color:#fca5a5;">Logout ({_esc(name)})</a>'
        f'</div>'
    )
