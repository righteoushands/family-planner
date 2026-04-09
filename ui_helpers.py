"""
ui_helpers.py — Shared UI: html_page template (CSS + JS), navigation, form parsing.
Imports from: config
"""
import cgi
from html import escape
from urllib.parse import parse_qs

from daily_schedule_engine import CHILDREN
from config import child_color, parent_color


# ── HTML shell ───────────────────────────────────────────────────────────────

# ── Theme definitions ─────────────────────────────────────────────────────────
THEMES = {
    # name: (label, description, overrides_dict)
    "ivory": (
        "Warm Ivory",
        "The classic default — warm whites, gold accents, dark ink.",
        {}  # No overrides — this IS the default
    ),
    "parchment": (
        "Deep Parchment",
        "Richer, more aged feel. Deeper tans, amber accents.",
        {
            "--parchment":    "#f0e8d8",
            "--warm-white":   "#f7f0e4",
            "--gold":         "#7a5a10",
            "--gold-light":   "#eddfc0",
            "--gold-mid":     "#b89040",
            "--border":       "#d8ccbb",
            "--border-light": "#e8dece",
            "--brown":        "#7a4a2c",
            "--ink-faint":    "#baa898",
            "--bg-tint":      "#f0e8d8",
        }
    ),
    "night": (
        "Night Mode",
        "Dark background, cream text, muted gold. Easy on the eyes at night.",
        {
            "--ink":          "#f0e8d8",
            "--ink-muted":    "#c4b8a8",
            "--ink-faint":    "#7a6e5e",
            "--parchment":    "#1e1a14",
            "--warm-white":   "#252018",
            "--gold":         "#c9a44a",
            "--gold-light":   "#3a3020",
            "--gold-mid":     "#c9a44a",
            "--border":       "#3a3028",
            "--border-light": "#2e2820",
            "--brown":        "#c9906a",
            "--brown-dark":   "#b87a58",
            "--bg-tint":      "#1e1a14",
        }
    ),
    "minimal": (
        "Clean & Minimal",
        "Pure white, black text, slate blue accents. Modern and distraction-free.",
        {
            "--ink":          "#111827",
            "--ink-muted":    "#6b7280",
            "--ink-faint":    "#d1d5db",
            "--parchment":    "#ffffff",
            "--warm-white":   "#f9fafb",
            "--gold":         "#2563eb",
            "--gold-light":   "#eff6ff",
            "--gold-mid":     "#3b82f6",
            "--border":       "#e5e7eb",
            "--border-light": "#f3f4f6",
            "--brown":        "#2563eb",
            "--brown-dark":   "#1d4ed8",
            "--bg-tint":      "#ffffff",
        }
    ),
    "liturgical": (
        "Liturgical Seasons",
        "Colors shift with the Church calendar: purple for Lent/Advent, gold for Easter, green for Ordinary Time.",
        "auto"  # Calculated dynamically
    ),
}

# Season → color palette
LITURGICAL_PALETTES = {
    "Advent": {
        "--gold":         "#6b3fa0",
        "--gold-mid":     "#8b5fc0",
        "--gold-light":   "#f0eaf8",
        "--brown":        "#6b3fa0",
        "--brown-dark":   "#5a3090",
        "--border":       "#d8cce8",
        "--border-light": "#ece6f4",
        "--parchment":    "#f5f0fa",
        "--warm-white":   "#faf7fd",
        "--bg-tint":      "#f5f0fa",
        "--season-accent":"#6b3fa0",
    },
    "Christmas": {
        "--gold":         "#b8860b",
        "--gold-mid":     "#d4a017",
        "--gold-light":   "#fff8e8",
        "--brown":        "#8b1a1a",
        "--brown-dark":   "#7a1010",
        "--border":       "#e8dcc0",
        "--border-light": "#f4eedc",
        "--parchment":    "#fffdf5",
        "--warm-white":   "#fffef9",
        "--bg-tint":      "#fffdf5",
        "--season-accent":"#d4a017",
    },
    "Lent": {
        "--gold":         "#5c4070",
        "--gold-mid":     "#7a5a90",
        "--gold-light":   "#ece8f0",
        "--brown":        "#5c4070",
        "--brown-dark":   "#4a3060",
        "--border":       "#d0c8dc",
        "--border-light": "#e8e2f0",
        "--parchment":    "#f2eef8",
        "--warm-white":   "#f8f4fc",
        "--bg-tint":      "#f2eef8",
        "--season-accent":"#5c4070",
    },
    "Holy Week": {
        "--gold":         "#8b0000",
        "--gold-mid":     "#a01010",
        "--gold-light":   "#f8e8e8",
        "--brown":        "#8b0000",
        "--brown-dark":   "#7a0000",
        "--border":       "#e8cccc",
        "--border-light": "#f4e0e0",
        "--parchment":    "#fdf0f0",
        "--warm-white":   "#fff8f8",
        "--bg-tint":      "#fdf0f0",
        "--season-accent":"#8b0000",
    },
    "Easter": {
        "--gold":         "#b8860b",
        "--gold-mid":     "#d4a832",
        "--gold-light":   "#fff9e0",
        "--brown":        "#2d7a2d",
        "--brown-dark":   "#1e6a1e",
        "--border":       "#e0e8c8",
        "--border-light": "#eef4dc",
        "--parchment":    "#f8fdf0",
        "--warm-white":   "#fcfef8",
        "--bg-tint":      "#f8fdf0",
        "--season-accent":"#d4a832",
    },
    "Ordinary Time": {
        "--gold":         "#2d6a2d",
        "--gold-mid":     "#3a8a3a",
        "--gold-light":   "#e8f4e8",
        "--brown":        "#2d6a2d",
        "--brown-dark":   "#1e5a1e",
        "--border":       "#c8dcc8",
        "--border-light": "#dceadc",
        "--parchment":    "#f4f9f4",
        "--warm-white":   "#f8fcf8",
        "--bg-tint":      "#f4f9f4",
        "--season-accent":"#3a8a3a",
    },
}


def get_theme_css() -> str:
    """
    Returns a CSS :root override block based on the saved theme setting.
    Called once per page render — reads from app_settings.json.
    """
    try:
        import json as _json, os as _os
        settings_path = "data/app_settings.json"
        if _os.path.exists(settings_path):
            with open(settings_path) as f:
                settings = _json.load(f)
        else:
            settings = {}
        theme_key = settings.get("color_theme", "ivory")
    except Exception:
        theme_key = "ivory"

    overrides = {}

    if theme_key == "liturgical":
        # Calculate season directly using stdlib only — avoid circular import
        # (render_liturgical imports ui_helpers, so we can't import it here)
        try:
            from datetime import date as _date
            import json as _json, os as _os

            def _easter(year):
                """Anonymous Gregorian easter calculation."""
                a = year % 19
                b, c = divmod(year, 100)
                d, e = divmod(b, 4)
                f = (b + 8) // 25
                g = (b - f + 1) // 3
                h = (19*a + b - d - g + 15) % 30
                i, k = divmod(c, 4)
                l = (32 + 2*e + 2*i - h - k) % 7
                m = (a + 11*h + 22*l) // 451
                month, day = divmod(h + l - 7*m + 114, 31)
                return _date(year, month, day + 1)

            today = _date.today()
            y = today.year
            from datetime import timedelta as _td

            easter     = _easter(y)
            ash_wed    = easter - _td(days=46)
            holy_sat   = easter - _td(days=1)
            palm_sun   = easter - _td(days=7)
            pentecost  = easter + _td(days=49)
            xmas       = _date(y, 12, 25)
            # Advent = 4 Sundays before Christmas
            # Find the Sunday on or before Nov 30
            nov30      = _date(y, 11, 30)
            advent1    = nov30 - _td(days=nov30.weekday() + 1) if nov30.weekday() != 6 else nov30
            epiphany   = _date(y, 1, 6)

            if ash_wed <= today < palm_sun:
                season = "Lent"
            elif palm_sun <= today <= holy_sat:
                season = "Holy Week"
            elif easter <= today < pentecost:
                season = "Easter"
            elif advent1 <= today < xmas:
                season = "Advent"
            elif xmas <= today or today < epiphany:
                season = "Christmas"
            else:
                season = "Ordinary Time"

        except Exception:
            season = "Ordinary Time"
        overrides = LITURGICAL_PALETTES.get(season, LITURGICAL_PALETTES["Ordinary Time"])
    elif theme_key in THEMES:
        theme_data = THEMES[theme_key]
        overrides = theme_data[2] if theme_data[2] != "auto" else {}

    if not overrides:
        return ""  # Default ivory — no overrides needed

    lines = [":root {"]
    for var, val in overrides.items():
        lines.append(f"  {var}: {val};")
    lines.append("}")

    # Night mode also needs body background override
    if theme_key == "night":
        lines.append("body { background: var(--parchment); color: var(--ink); }")
        lines.append(".card { background: #252018; border-color: #3a3028; }")
        lines.append("input, select, textarea { background: #2a2418; color: var(--ink); border-color: #3a3028; }")
        lines.append(".settings-section h2, .settings-section h3 { color: var(--gold-mid); }")

    # Liturgical subtle background tint
    if theme_key == "liturgical" and "--bg-tint" in overrides:
        lines.append(f"body {{ background: {overrides['--bg-tint']}; }}")

    return "\n".join(lines)


def html_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>{escape(title)}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ── Design tokens ── */
:root {{
  --ink:          #1c1610;
  --ink-muted:    #6b5e4e;
  --ink-faint:    #c4b8a8;
  --parchment:    #f7f3ee;
  --warm-white:   #fdfaf7;
  --gold:         #8b6914;
  --gold-light:   #f5ead8;
  --gold-mid:     #c9a44a;
  --crimson:      #7c1a1a;
  --forest:       #2d5016;
  --border:       #e4dbd2;
  --border-light: #f0ebe4;
  --brown:        #8b5a3c;
  --brown-dark:   #7a4f35;
  --radius-sm:    8px;
  --radius-md:    14px;
  --radius-lg:    20px;
  --shadow-sm:    0 2px 6px rgba(0,0,0,0.06);
  --shadow-md:    0 4px 16px rgba(0,0,0,0.10);
}}

/* ── Reset ── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }}

/* ── Base ── */
body {{
  font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 16px;
  line-height: 1.6;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 16px 60px;
  background: var(--parchment);
  color: var(--ink);
}}

h1 {{
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 2.2rem;
  font-weight: 600;
  margin: 0 0 16px;
  color: var(--ink);
  line-height: 1.15;
}}
h2 {{
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--ink);
}}
h3 {{
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0 0 8px;
  color: var(--ink);
}}
h4 {{
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0 0 6px;
  color: var(--ink-muted);
}}

a {{ color: var(--brown); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

/* ── Navigation ── */
.nav-shell {{
  background: var(--ink);
  margin: 0 -16px 28px;
  padding: 0 16px;
  position: sticky;
  top: 0;
  z-index: 1000;
  box-shadow: 0 2px 12px rgba(0,0,0,0.25);
  overflow: visible;
}}
.nav-primary {{
  display: flex;
  align-items: center;
  gap: 2px;
  height: 52px;
  flex-wrap: nowrap;
  overflow-x: auto;
  scrollbar-width: none;
}}
.nav-primary::-webkit-scrollbar {{ display: none; }}
.nav-primary a {{
  white-space: nowrap;
  padding: 6px 11px;
  border-radius: var(--radius-sm);
  font-weight: 500;
  font-size: 0.85rem;
  color: rgba(245,234,216,0.7);
  transition: all 0.15s;
  flex-shrink: 0;
  text-decoration: none;
  letter-spacing: 0.01em;
}}
.nav-primary a:hover {{
  background: rgba(255,255,255,0.1);
  color: var(--gold-light);
}}
.nav-primary a.plan-link {{
  background: var(--brown);
  color: white;
  font-weight: 600;
  border-radius: var(--radius-sm);
}}
.nav-primary a.plan-link:hover {{ background: var(--brown-dark); }}
.nav-divider {{
  width: 1px;
  height: 20px;
  background: rgba(255,255,255,0.12);
  margin: 0 3px;
  flex-shrink: 0;
}}

/* Hamburger */
.nav-more {{ position: relative; margin-left: auto; flex-shrink: 0; }}
.nav-more-btn {{
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  font-weight: 600;
  font-size: 0.85rem;
  color: var(--gold-light);
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.15);
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
  transition: background 0.15s;
}}
.nav-more-btn:hover {{ background: rgba(255,255,255,0.18); }}
.nav-dropdown {{
  display: none;
  position: fixed;
  top: 60px;
  right: 16px;
  background: var(--warm-white);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: 0 16px 48px rgba(0,0,0,0.28);
  min-width: 230px;
  max-height: calc(100vh - 76px);
  overflow-y: auto;
  z-index: 2000;
  padding: 8px;
}}
.nav-dropdown.open {{ display: block; }}
.nav-dropdown a {{
  display: block;
  padding: 10px 16px;
  font-size: 0.88rem;
  color: var(--ink);
  border-radius: 10px;
  font-weight: 500;
  white-space: nowrap;
  text-decoration: none;
  transition: background 0.12s;
}}
.nav-dropdown a:hover {{ background: var(--gold-light); color: var(--brown); text-decoration: none; }}
.nav-dropdown .nav-drop-section {{
  font-size: 0.68rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--gold);
  padding: 12px 16px 4px;
}}
.nav-dropdown hr {{
  border: none;
  border-top: 1px solid var(--border-light);
  margin: 6px 0;
}}

/* ── Cards ── */
.card {{
  background: var(--warm-white);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s;
}}
.card:hover {{ box-shadow: var(--shadow-md); }}
.card-tight {{ padding: 14px 18px; }}
.card-flat  {{ box-shadow: none; }}

/* ── Layout grid ── */
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}

/* ── Badges ── */
.badge {{
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--gold-light);
  border: 1px solid #e0cfa8;
  font-size: 0.8em;
  color: var(--gold);
  font-weight: 600;
}}
.summary-row {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}

/* ── Forms ── */
label {{
  display: block;
  margin-bottom: 5px;
  font-weight: 600;
  font-size: 0.82em;
  color: var(--ink-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}}
input[type="text"], input[type="number"], input[type="date"],
input[type="email"], input[type="password"],
select, textarea {{
  width: 100%;
  max-width: 680px;
  margin-bottom: 14px;
  padding: 10px 13px;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  background: white;
  font-size: 0.95em;
  font-family: inherit;
  color: var(--ink);
  transition: border-color 0.15s, box-shadow 0.15s;
}}
input[type="file"] {{
  width: 100%;
  max-width: 680px;
  margin-bottom: 14px;
  font-size: 0.95em;
  font-family: inherit;
  color: var(--ink);
}}
input:focus, select:focus, textarea:focus {{
  outline: none;
  border-color: var(--brown);
  box-shadow: 0 0 0 3px rgba(139,90,60,0.12);
}}
button {{
  padding: 9px 18px;
  margin-right: 8px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--brown);
  color: white;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.88em;
  font-family: inherit;
  transition: background 0.15s, transform 0.1s;
  letter-spacing: 0.01em;
}}
button:hover {{ background: var(--brown-dark); }}
button:active {{ transform: scale(0.98); }}
button.secondary {{ background: #5a6e4a; }}
button.secondary:hover {{ background: #4a5e3a; }}
button.ghost {{
  background: transparent;
  color: var(--ink-muted);
  border: 1.5px solid var(--border);
}}
button.ghost:hover {{ background: var(--parchment); }}

/* ── Tasks ── */
.task {{ margin-bottom: 8px; display: flex; align-items: flex-start; gap: 10px; }}
.task form {{ display: flex; align-items: flex-start; gap: 10px; flex: 1; }}
.task.done label {{ text-decoration: line-through; color: var(--ink-faint); }}
.task label {{ line-height: 1.4; font-weight: 400; font-size: 0.95em; cursor: pointer; text-transform: none; letter-spacing: 0; }}

/* ── Status / success ── */
.success {{
  background: #eef7ee;
  border: 1px solid #c3e0c3;
  color: #2a5a2a;
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  margin-bottom: 14px;
  font-weight: 500;
  font-size: 0.9em;
}}

/* ── Misc helpers ── */
.muted  {{ color: var(--ink-muted); font-size: 0.9em; }}
.small  {{ font-size: 0.83em; color: var(--ink-muted); }}
.page-header {{ margin-bottom: 18px; }}
.link-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }}
.link-button {{
  display: inline-block;
  background: white;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 6px 13px;
  font-size: 0.83em;
  color: var(--ink-muted);
  font-weight: 500;
  transition: all 0.12s;
}}
.link-button:hover {{
  background: var(--gold-light);
  border-color: #e0cfa8;
  color: var(--brown);
  text-decoration: none;
}}
.section-stack > .card {{ margin-bottom: 12px; }}
.subject-card {{ border-top: 1px solid var(--border-light); padding-top: 12px; margin-top: 12px; }}
.preview-edit-block {{
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--parchment);
  padding: 14px;
  margin-bottom: 10px;
}}
.block-toolbar {{ display: grid; grid-template-columns: 140px 1fr; gap: 12px; }}
.block-remove {{ display: flex; align-items: center; gap: 8px; margin-top: 4px; }}
pre {{
  white-space: pre-wrap;
  background: var(--parchment);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
  overflow-x: auto;
  font-size: 0.85em;
}}

/* ── Plan My Day ── */
.plan-section {{
  margin-bottom: 28px;
  scroll-margin-top: 64px;
}}
.plan-section-label {{
  font-size: 0.68rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--gold);
  margin-bottom: 10px;
  padding-left: 2px;
}}
.plan-step-nav {{
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 20px;
  padding: 10px 14px;
  background: var(--ink);
  border-radius: var(--radius-md);
}}
.plan-step-nav a {{
  font-size: 0.8em;
  font-weight: 600;
  color: rgba(245,234,216,0.6);
  padding: 5px 12px;
  border-radius: 6px;
  background: rgba(255,255,255,0.06);
  white-space: nowrap;
  text-decoration: none;
  transition: all 0.15s;
  letter-spacing: 0.02em;
}}
.plan-step-nav a:hover {{
  background: rgba(255,255,255,0.14);
  color: var(--gold-light);
  text-decoration: none;
}}

/* ── Settings tabs ── */
.settings-tabs {{
  display: flex;
  border-bottom: 2px solid var(--border);
  margin-bottom: 24px;
  overflow-x: auto;
  scrollbar-width: none;
}}
.settings-tabs::-webkit-scrollbar {{ display: none; }}
.settings-tabs a {{
  padding: 10px 18px;
  font-size: 0.86em;
  font-weight: 600;
  color: var(--ink-muted);
  white-space: nowrap;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  text-decoration: none;
  transition: color 0.15s, border-color 0.15s;
}}
.settings-tabs a:hover {{ color: var(--ink); }}
.settings-tabs a.active {{ color: var(--brown); border-bottom-color: var(--brown); }}
.settings-section {{ scroll-margin-top: 64px; margin-bottom: 0; }}
.settings-section + .settings-section {{
  border-top: 1px solid var(--border-light);
  padding-top: 28px;
  margin-top: 28px;
}}

/* ── Activity pills (family grid) ── */
.pill {{
  display: inline-block;
  padding: 2px 9px;
  border-radius: 20px;
  font-size: 0.76em;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
}}
.pill-school  {{ background: #eef0fc; color: #3730a3; }}
.pill-chores  {{ background: #fef9c3; color: #713f12; }}
.pill-free    {{ background: #f0fdf4; color: #166534; }}
.pill-kitchen {{ background: #fef3c7; color: #92400e; }}
.pill-meal    {{ background: #fdf4ff; color: #7e22ce; }}
.pill-default {{ background: #f3f4f6; color: #374151; }}

/* ── Section label (mockup CAPS style) ── */
.section-cap {{
  font-size: 0.68rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--ink-faint);
  margin-bottom: 10px;
  margin-top: 20px;
}}

/* ── Plan checklist items ── */
.plan-check-item {{
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-light);
}}
.plan-check-item:last-child {{ border-bottom: none; }}
.plan-check-circle {{
  width: 22px; height: 22px;
  border-radius: 50%;
  border: 2px solid var(--ink-faint);
  flex-shrink: 0;
  margin-top: 1px;
  cursor: pointer;
  transition: all 0.15s;
}}
.plan-check-circle.done {{
  background: #2d5016;
  border-color: #2d5016;
}}
.plan-check-text {{ font-size: 0.9em; line-height: 1.45; }}
.plan-check-meta {{ font-size: 0.78em; color: var(--ink-muted); margin-top: 2px; }}
.plan-check-time {{ font-size: 0.8em; color: var(--ink-faint); font-weight: 600; margin-left: auto; padding-top: 2px; white-space: nowrap; }}

/* ── AI FAB button ── */
.ai-fab {{
  position: fixed;
  bottom: 84px;
  right: 20px;
  width: 52px; height: 52px;
  background: var(--ink);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  box-shadow: 0 4px 18px rgba(0,0,0,0.3);
  cursor: pointer;
  z-index: 900;
  border: none;
  transition: transform 0.15s;
}}
.ai-fab:hover {{ transform: scale(1.08); }}
@media (min-width: 769px) {{
  .ai-fab {{ bottom: 28px; }}
}}
@media print {{
  .nav-shell, .no-print, button, form, #ai-float, .mobile-bottom-nav {{ display: none !important; }}
  body {{ background: white; padding: 0; max-width: none; }}
  .card {{ border: 1px solid #ddd; box-shadow: none; padding: 12px; margin-bottom: 10px; }}
}}

/* ══════════════════════════════════════════
   MOBILE — phones under 768px
══════════════════════════════════════════ */
@media (max-width: 768px) {{
  body {{
    font-size: 14px;
    padding: 0 12px 80px;
  }}
  h1 {{ font-size: 1.7rem; margin-bottom: 10px; }}
  h2 {{ font-size: 1.25rem; }}
  h3 {{ font-size: 1rem; }}

  .card {{ padding: 14px; border-radius: 12px; margin-bottom: 12px; }}
  .card-tight {{ padding: 12px 14px; }}

  .nav-shell {{ display: none; }}
  .mobile-bottom-nav {{ display: flex !important; }}

  .page-header {{ margin-top: 14px; margin-bottom: 12px; }}

  .two-col {{ grid-template-columns: 1fr; gap: 10px; }}
  .grid {{ grid-template-columns: 1fr; gap: 10px; }}
  .block-toolbar {{ grid-template-columns: 1fr; }}

  input[type="text"], input[type="number"], input[type="date"],
  input[type="email"], input[type="password"],
  input[type="file"], select, textarea {{
    max-width: 100%;
    font-size: 16px;
  }}

  .plan-step-nav {{
    flex-wrap: nowrap;
    overflow-x: auto;
    scrollbar-width: none;
    padding: 8px 10px;
    margin-bottom: 14px;
    border-radius: 10px;
  }}
  .plan-step-nav::-webkit-scrollbar {{ display: none; }}
  .plan-step-nav a {{ font-size: 0.76em; padding: 4px 10px; flex-shrink: 0; }}

  #family-grid-card table {{ min-width: 480px; }}
  #family-grid-card input {{ font-size: 11px; padding: 3px 4px; min-width: 80px !important; }}

  .plan-section {{ margin-bottom: 18px; }}
  .plan-section-label {{ margin-bottom: 8px; }}
  .settings-tabs {{ flex-wrap: nowrap; overflow-x: auto; }}
  .settings-tabs a {{ padding: 8px 14px; font-size: 0.82em; }}

  .link-row {{ gap: 6px; }}
  .link-button {{ font-size: 0.8em; padding: 5px 10px; }}
  .no-mobile {{ display: none !important; }}
}}

/* Mobile bottom nav */
.mobile-bottom-nav {{
  display: none;
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: 64px;
  background: var(--ink);
  border-top: 1px solid rgba(255,255,255,0.08);
  z-index: 2000;
  align-items: flex-start;
  justify-content: space-around;
  padding: 8px 4px 0;
  box-shadow: 0 -4px 20px rgba(0,0,0,0.3);
}}
.mobile-nav-item {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 4px 10px;
  border-radius: 8px;
  cursor: pointer;
  text-decoration: none;
  min-width: 52px;
  transition: background 0.12s;
}}
.mobile-nav-item:hover {{ background: rgba(255,255,255,0.1); text-decoration: none; }}
.mobile-nav-icon {{ font-size: 20px; line-height: 1; }}
.mobile-nav-label {{
  font-size: 10px;
  font-weight: 600;
  color: rgba(245,234,216,0.5);
  letter-spacing: 0.02em;
  white-space: nowrap;
}}
.mobile-nav-item.active .mobile-nav-label {{ color: var(--gold-mid); }}
.mobile-nav-item.plan-item {{
  background: var(--brown);
  border-radius: 10px;
  padding: 6px 12px;
}}
.mobile-nav-item.plan-item .mobile-nav-label {{ color: white; }}

/* ── Theme overrides (injected per request) ── */
{get_theme_css()}
</style>
<script>
function toggleTask(checkbox, taskId, returnUrl) {{
    var row    = document.getElementById('task-' + taskId);
    var isDone = checkbox.checked;
    var newVal = isDone ? 'true' : 'false';
    if (row) {{
        row.classList.toggle('done', isDone);
    }}
    var body = 'task_id=' + encodeURIComponent(taskId) +
               '&new_value=' + encodeURIComponent(newVal) +
               '&return_url=' + encodeURIComponent(returnUrl);
    fetch('/toggle-task', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: body
    }}).then(function(resp) {{
        if (!resp.ok) {{
            checkbox.checked = !checkbox.checked;
            if (row) row.classList.toggle('done', !isDone);
        }}
    }}).catch(function() {{
        checkbox.checked = !checkbox.checked;
        if (row) row.classList.toggle('done', !isDone);
    }});
}}
function toggleMoreMenu() {{
    var d = document.getElementById('nav-dropdown');
    if (d) d.classList.toggle('open');
}}
document.addEventListener('click', function(e) {{
    var btn = document.querySelector('.nav-more-btn');
    var drop = document.getElementById('nav-dropdown');
    if (drop && btn && !btn.contains(e.target) && !drop.contains(e.target)) {{
        drop.classList.remove('open');
    }}
}});
</script>
</head>
<body>
{body}

<!-- Mobile bottom nav (shown only on phones via CSS) -->
<nav class="mobile-bottom-nav" aria-label="Mobile navigation">
  <a href="/" class="mobile-nav-item">
    <span class="mobile-nav-icon">&#127968;</span>
    <span class="mobile-nav-label">Home</span>
  </a>
  <a href="/tasks" class="mobile-nav-item">
    <span class="mobile-nav-icon">&#9989;</span>
    <span class="mobile-nav-label">Tasks</span>
  </a>
  <a href="/prayer" class="mobile-nav-item">
    <span class="mobile-nav-icon">&#10011;</span>
    <span class="mobile-nav-label">Prayer</span>
  </a>
  <a href="/plan-tomorrow" class="mobile-nav-item">
    <span class="mobile-nav-icon">&#10024;</span>
    <span class="mobile-nav-label">Tomorrow</span>
  </a>
  <button class="mobile-nav-item" onclick="toggleMobileMore()" id="mobile-more-btn"
          style="background:none;border:none;cursor:pointer;font-family:inherit;width:100%;">
    <span class="mobile-nav-icon" style="font-size:1.3em;">&#9776;</span>
    <span class="mobile-nav-label">More</span>
  </button>
</nav>

<!-- Mobile More slide-up sheet -->
<div id="mobile-more-overlay"
     onclick="if(event.target===this)closeMobileMore()"
     style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:9000;">
  <div id="mobile-more-sheet"
       style="position:absolute;bottom:0;left:0;right:0;background:white;
              border-radius:20px 20px 0 0;padding:0 0 env(safe-area-inset-bottom,0) 0;
              max-height:82vh;overflow-y:auto;
              transform:translateY(100%);transition:transform 0.28s cubic-bezier(.4,0,.2,1);">
    <!-- Handle -->
    <div style="display:flex;justify-content:center;padding:12px 0 4px;">
      <div style="width:40px;height:4px;border-radius:4px;background:#e5e7eb;"></div>
    </div>
    <!-- Sections -->
    <div style="padding:4px 16px 20px;">

      <!-- AI Companions section -->
      <div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
                  color:#9ca3af;margin:10px 0 8px;">Your Companions</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px;">
        <a href="/lucy" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;
                  background:#f3f0f9;border-radius:12px;text-decoration:none;
                  color:#5b3a8a;font-weight:700;font-size:0.88em;">
          <span>&#10024;</span> Lucy
        </a>
        <a href="/headmaster" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;
                  background:#eef1f8;border-radius:12px;text-decoration:none;
                  color:#1e3566;font-weight:700;font-size:0.88em;">
          <span>&#128218;</span> Fr. Gregory
        </a>
        <a href="/lorenzo" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;
                  background:#faf0ec;border-radius:12px;text-decoration:none;
                  color:#8b3a1a;font-weight:700;font-size:0.88em;">
          <span>&#127869;&#65039;</span> Lorenzo
        </a>
        <a href="/coach" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;
                  background:#eef7f1;border-radius:12px;text-decoration:none;
                  color:#1a6e3e;font-weight:700;font-size:0.88em;">
          <span>&#128170;</span> Coach
        </a>
        <a href="/dr-monica" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;
                  background:#faf0f5;border-radius:12px;text-decoration:none;
                  color:#8b3a5c;font-weight:700;font-size:0.88em;">
          <span>&#127800;</span> Dr. Monica
        </a>
        <a href="/dev" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;
                  background:#eef3fc;border-radius:12px;text-decoration:none;
                  color:#1e3a8a;font-weight:700;font-size:0.88em;">
          <span>&#128187;</span> Izzy
        </a>
      </div>

      <div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
                  color:#9ca3af;margin:10px 0 8px;">People</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:4px;">
        <a href="/mom-profile" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;
                  background:{parent_color('Lauren','light')};
                  border-radius:12px;text-decoration:none;color:{parent_color('Lauren','bg')};font-weight:600;font-size:0.9em;">
          <span style="font-size:1.2em;">&#9825;</span> Lauren
        </a>
        <a href="/john" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;
                  background:{parent_color('John','light')};
                  border-radius:12px;text-decoration:none;color:{parent_color('John','bg')};font-weight:600;font-size:0.9em;">
          <span style="font-size:1.2em;">&#9788;</span> John
        </a>
        {''.join(
          '<a href="/schedule/' + escape(c) + '" onclick="closeMobileMore()"'
          ' style="display:flex;align-items:center;gap:8px;padding:12px 14px;background:#fafafa;'
          'border-radius:12px;text-decoration:none;color:#374151;font-weight:600;font-size:0.9em;">'
          '<span style="width:9px;height:9px;border-radius:50%;background:' + child_color(c,'bg') + ';flex-shrink:0;display:inline-block;"></span>'
          + escape(c) + '</a>'
          for c in CHILDREN
        )}
        <a href="/friends" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:#f0faf4;
                  border-radius:12px;text-decoration:none;color:#2d6a4f;font-weight:600;font-size:0.9em;">
          <span style="font-size:1.2em;">&#128106;</span> Friends
        </a>
      </div>

      <div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
                  color:#9ca3af;margin:14px 0 8px;">Plan</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:4px;">
        <a href="/mom" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;
                  background:{parent_color('Lauren','light')};
                  border-radius:12px;text-decoration:none;color:{parent_color('Lauren','bg')};font-weight:600;font-size:0.9em;">
          &#128203; Plan my day
        </a>
        <a href="/calendar" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:#fafafa;
                  border-radius:12px;text-decoration:none;color:#374151;font-size:0.9em;">
          &#128198; Calendar
        </a>
        <a href="/notes" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:#fafafa;
                  border-radius:12px;text-decoration:none;color:#374151;font-size:0.9em;">
          &#128221; Notes
        </a>
        <a href="/planner" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:#fafafa;
                  border-radius:12px;text-decoration:none;color:#374151;font-size:0.9em;">
          &#128197; Monthly Planner
        </a>
        <a href="/mom#grid" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:#fafafa;
                  border-radius:12px;text-decoration:none;color:#374151;font-size:0.9em;">
          &#128203;&#10003; Family Rule of Life
        </a>
        <a href="/family-schedule" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:#fafafa;
                  border-radius:12px;text-decoration:none;color:#374151;font-size:0.9em;">
          &#128197; Today's Timeline
        </a>
        <a href="/settings" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:#fafafa;
                  border-radius:12px;text-decoration:none;color:#374151;font-size:0.9em;">
          &#9881; Settings
        </a>
      </div>

      <div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
                  color:#9ca3af;margin:14px 0 8px;">Kids</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:4px;">
        <a href="/school" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:#fafafa;
                  border-radius:12px;text-decoration:none;color:#374151;font-size:0.9em;">
          &#128218; School
        </a>
        <a href="/week-school" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:#eef1f8;
                  border-radius:12px;text-decoration:none;color:#1e3566;font-size:0.9em;font-weight:700;">
          &#128200; Week Progress
        </a>
        <a href="/chores" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:#fafafa;
                  border-radius:12px;text-decoration:none;color:#374151;font-size:0.9em;">
          &#129529; Chores
        </a>
      </div>

      <div style="font-size:0.68em;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
                  color:#9ca3af;margin:14px 0 8px;">Meals</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:4px;">
        <a href="/meals" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:#fafafa;
                  border-radius:12px;text-decoration:none;color:#374151;font-size:0.9em;">
          &#127829; Meals
        </a>
        <a href="/recipes" onclick="closeMobileMore()"
           style="display:flex;align-items:center;gap:10px;padding:12px 14px;background:#fafafa;
                  border-radius:12px;text-decoration:none;color:#374151;font-size:0.9em;">
          &#128218; Recipes
        </a>
      </div>

    </div>
  </div>
</div>

<script>
(function() {{
  var path = window.location.pathname;
  document.querySelectorAll('.mobile-nav-item').forEach(function(el) {{
    var href = el.getAttribute('href');
    if (href && (path === href || (href !== '/' && path.startsWith(href)))) {{
      if (!el.classList.contains('plan-item')) {{
        el.style.background = '#f5f0eb';
      }}
      var lbl = el.querySelector('.mobile-nav-label');
      if (lbl) lbl.style.color = '#8b5a3c';
    }}
  }});
  /* Highlight More btn if on a "more" page */
  var morePaths = ['/mom-profile','/john','/friends','/calendar','/notes','/planner',
                   '/school','/chores','/meals','/recipes','/family-schedule','/roadmap',
                   '/settings','/mom','/dev','/lucy','/lorenzo','/headmaster','/coach','/dr-monica'];
  if (morePaths.indexOf(path) > -1) {{
    var btn = document.getElementById('mobile-more-btn');
    if (btn) {{
      btn.style.background = '#f5f0eb';
      var lbl = btn.querySelector('.mobile-nav-label');
      if (lbl) lbl.style.color = '#8b5a3c';
    }}
  }}
}})();

window.toggleMobileMore = function() {{
  var overlay = document.getElementById('mobile-more-overlay');
  var sheet   = document.getElementById('mobile-more-sheet');
  if (!overlay || !sheet) return;
  var isOpen = overlay.style.display === 'flex';
  if (isOpen) {{
    closeMobileMore();
  }} else {{
    overlay.style.display = 'flex';
    requestAnimationFrame(function() {{
      requestAnimationFrame(function() {{
        sheet.style.transform = 'translateY(0)';
      }});
    }});
    document.body.style.overflow = 'hidden';
  }}
}};

window.closeMobileMore = function() {{
  var overlay = document.getElementById('mobile-more-overlay');
  var sheet   = document.getElementById('mobile-more-sheet');
  if (!overlay || !sheet) return;
  sheet.style.transform = 'translateY(100%)';
  setTimeout(function() {{
    overlay.style.display = 'none';
    document.body.style.overflow = '';
  }}, 280);
}};
</script>
</body>
</html>
"""


# ── Navigation ───────────────────────────────────────────────────────────────
def top_nav() -> str:
    try:
        import auth as _auth_mod
        viewer = _auth_mod.get_viewer()
        is_admin = _auth_mod.is_admin(viewer) if viewer else False
    except Exception:
        viewer = None
        is_admin = True

    # ── Child nav (simplified) ────────────────────────────────────────────────
    if viewer and not is_admin:
        u = _auth_mod.USERS.get(viewer, {})
        color = u.get("color", "#1f2937")
        name  = u.get("name", viewer.title())
        sched_link = f"/schedule/{viewer}"
        return f"""
    <nav class="nav-shell no-print">
      <div class="nav-primary">
        <a href="{sched_link}" style="color:{color};font-weight:800;">👤 {escape(name)}</a>
        <div class="nav-divider"></div>
        <a href="/today">Today</a>
        <a href="/week">Week</a>
        <div class="nav-divider"></div>
        <a href="/meals">🍽 Meals</a>
        <a href="/chores">🧹 Chores</a>
        <a href="/prayer">✝ Prayer</a>
        <div class="nav-divider"></div>
        <button onclick="document.getElementById('msg-mom-modal').style.display='flex'"
          style="background:#7c3aed;color:white;border:none;border-radius:20px;
                 padding:6px 14px;font-size:0.82em;font-weight:700;cursor:pointer;
                 font-family:inherit;">&#128140; Message Mom</button>
        <div class="nav-divider"></div>
        <a href="/change-pin" style="color:#9ca3af;font-size:0.8em;">Change PIN</a>
        <a href="/logout" style="color:#9ca3af;font-size:0.8em;">Sign out</a>
      </div>
    </nav>
    {_message_mom_modal()}
    """

    # ── Admin nav (full) ─────────────────────────────────────────────────────
    child_links = "".join(
        f'<a href="/schedule/{child}" style="color:{child_color(child,"bg")};font-weight:700;">{child}</a>'
        for child in CHILDREN
    )

    # Unread message badge
    badge = ""
    try:
        cnt = _auth_mod.unread_count()
        if cnt:
            badge = (f'<a href="/#mom-messages" style="background:#dc2626;color:white;'
                     f'border-radius:20px;padding:4px 10px;font-size:0.78em;font-weight:800;'
                     f'text-decoration:none;margin-left:4px;">&#128140; {cnt} new</a>')
    except Exception:
        pass

    user_pill = ""
    if viewer:
        u = _auth_mod.USERS.get(viewer, {})
        color = u.get("color", "#1f2937")
        name  = u.get("name", viewer.title())
        user_pill = (f'<span style="color:{color};font-weight:700;font-size:0.88em;">'
                     f'{escape(name)}</span>'
                     f'<a href="/logout" style="color:#9ca3af;font-size:0.75em;margin-left:6px;">sign out</a>'
                     f'<div class="nav-divider"></div>')

    return f"""
    <nav class="nav-shell no-print">
      <div class="nav-primary">
        {user_pill}
        <a href="/">🏠</a>
        {badge}
        <div class="nav-divider"></div>
        <a href="/today">Today</a>
        <a href="/week">Week</a>
        <div class="nav-divider"></div>
        {child_links}
        <div class="nav-divider"></div>
        <a href="/mom" class="plan-link">📋 Plan</a>
        <div class="nav-divider"></div>
        <a href="/prayer">✝ Prayer</a>
        <div class="nav-divider"></div>
        <a href="/settings">⚙️ Settings</a>
        <a href="/dev" style="color:#1e3a8a;font-weight:700;">&#128187; Izzy</a>
        <div class="nav-more">
          <button class="nav-more-btn" onclick="toggleMoreMenu()">☰ More</button>
          <div class="nav-dropdown" id="nav-dropdown">
            <div class="nav-drop-section">Plan</div>
            <a href="/calendar">📆 Calendar</a>
            <a href="/family-schedule">📅 Today's Timeline</a>
            <a href="/tasks">✅ Tasks</a>
            <a href="/notes">📝 Notes</a>
            <a href="/planner">🗓 Monthly Planner</a>
            <hr>
            <div class="nav-drop-section">Kids</div>
            <a href="/school">📚 School</a>
            <a href="/chores">🧹 Chores</a>
            <a href="/van-roles">🚐 Van</a>
            <hr>
            <div class="nav-drop-section">Meals</div>
            <a href="/meals">🍽 Meal Planner</a>
            <a href="/recipes">📖 Recipes</a>
            <hr>
            <div class="nav-drop-section">Print</div>
            <a href="/print/day">Print Today</a>
            <a href="/print/day?date=tomorrow">Print Tomorrow</a>
            <a href="/print/week">Print Week</a>
            <hr>
            <div class="nav-drop-section">People</div>
            <a href="/mom-profile">&#9825; Mom</a>
            <a href="/john">&#9788; John</a>
            <a href="/friends">&#128106; Friends</a>
            <hr>
            <div class="nav-drop-section">Admin</div>
            <a href="/roadmap">🗺 Roadmap</a>
            <a href="/history">📂 History</a>
            <a href="/dev" style="color:#1e3a8a;font-weight:700;">&#128187; Izzy</a>
            <a href="/signup" style="color:#8b5a3c;font-weight:700;">✨ Join Beta Waitlist</a>
          </div>
        </div>
      </div>
    </nav>
    """


def _message_mom_modal() -> str:
    """Floating modal for children to message Lauren."""
    return """
<div id="msg-mom-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);
     backdrop-filter:blur(3px);z-index:9999;align-items:center;justify-content:center;padding:20px;">
  <div style="background:#fdf8f0;border-radius:20px;padding:28px 24px;width:100%;max-width:380px;
              box-shadow:0 20px 50px rgba(0,0,0,.4);">
    <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:1.4em;font-weight:700;
                color:#7c3aed;margin-bottom:6px;">&#128140; Message Mom</div>
    <div style="font-size:0.82em;color:#6b7280;margin-bottom:16px;">
      She'll see your message when she checks the dashboard.
    </div>
    <form method="POST" action="/message-mom">
      <textarea name="text" rows="4" placeholder="Type your message..."
        style="width:100%;padding:12px;border:1.5px solid #e5e7eb;border-radius:12px;
               font-family:inherit;font-size:0.95em;resize:none;margin-bottom:12px;"
        required></textarea>
      <div style="display:flex;gap:10px;">
        <button type="submit"
          style="flex:1;background:#7c3aed;color:white;border:none;border-radius:12px;
                 padding:12px;font-weight:700;font-size:0.95em;cursor:pointer;font-family:inherit;">
          Send &#128140;
        </button>
        <button type="button"
          onclick="document.getElementById('msg-mom-modal').style.display='none'"
          style="flex:1;background:#f3f4f6;color:#374151;border:none;border-radius:12px;
                 padding:12px;font-weight:700;font-size:0.95em;cursor:pointer;font-family:inherit;">
          Cancel
        </button>
      </div>
    </form>
  </div>
</div>"""


def page_header(title: str, subtitle: str = "") -> str:
    sub = f'<div style="font-size:0.85em;color:var(--ink-muted);margin-top:3px;">{escape(subtitle)}</div>' if subtitle else ""
    return (
        f'<div id="top"></div>{top_nav()}'
        f'<div style="margin-bottom:18px;padding-top:4px;">'
        f'<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
        f'font-size:2rem;font-weight:600;color:var(--ink);line-height:1.15;">'
        f'{escape(title)}</div>{sub}</div>'
    )


def render_status_message(message: str) -> str:
    if not message:
        return ""
    if message.startswith("error:"):
        text = message[6:]
        return (f'<div style="background:#fef2f2;border:1px solid #fca5a5;'
                f'border-radius:8px;padding:10px 14px;margin-bottom:12px;'
                f'color:#b91c1c;font-size:0.9em;">'
                f'⚠️ {escape(text)}</div>')
    text = message[3:] if message.startswith("ok:") else message
    return f"<div class='success'>{escape(text)}</div>"


# ── Form parsing ─────────────────────────────────────────────────────────────
def parse_urlencoded_body(handler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8", errors="replace")
    return parse_qs(raw, keep_blank_values=True)


def parse_multipart_form(handler):
    return cgi.FieldStorage(
        fp=handler.rfile,
        headers=handler.headers,
        environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": handler.headers.get("Content-Type", ""),
        },
    )