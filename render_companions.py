"""Standalone /companions page — discoverable directory of the six AI companions."""
from html import escape
from ui_helpers import html_page


_COMPANIONS = [
    ("&#10024;",   "Lucy",          "Your family's personal assistant — always ready to help you think, plan, and remember.", "/lucy",        "#5b3a8a", "#f3f0f9", "#7a4ea3"),
    ("&#127869;&#65039;", "Lorenzo",       "Personal chef and meal-planning companion. Kitchen wisdom and weekly menus.",            "/lorenzo",     "#8b3a1a", "#faf0ec", "#c87146"),
    ("&#10016;",   "Sister Mary",   "Marian companion and prayer guide. Be still, and know that I am God.",                   "/sister-mary", "#2d4a78", "#eaf0fa", "#4a6fa5"),
    ("&#128218;",  "Father Gregory","Academic headmaster — homeschool guidance, curriculum, and student support.",            "/headmaster",  "#1e3566", "#eef1f8", "#3a5a99"),
    ("&#128170;",  "Coach",         "Family fitness, programs, and wellness routines.",                                       "/programs",    "#1a6e3e", "#eef7f1", "#3a8e5e"),
    ("&#127800;",  "Dr. Monica",    "Pediatric and child-development companion for family health questions.",                 "/dr-monica",   "#8b3a5c", "#faf0f5", "#c8769a"),
]


def render_companions_page() -> str:
    cards = []
    for icon, name, desc, href, fg, bg, accent in _COMPANIONS:
        cards.append(f"""
          <a href="{href}" style="text-decoration:none;color:inherit;
              background:{bg};border:1px solid #e5e7eb;border-left:4px solid {accent};
              border-radius:14px;padding:18px 20px;display:block;
              transition:transform 0.15s, box-shadow 0.15s;"
              onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 4px 14px rgba(0,0,0,0.06)';"
              onmouseout="this.style.transform='';this.style.boxShadow='';">
            <div style="display:flex;align-items:baseline;gap:10px;">
              <span style="font-size:1.4em;">{icon}</span>
              <span style="font-weight:700;color:{fg};font-size:1.12em;">{escape(name)}</span>
            </div>
            <div style="font-size:0.92em;color:#444;margin-top:8px;line-height:1.45;">
              {escape(desc)}
            </div>
            <div style="margin-top:10px;font-size:0.82em;color:{fg};font-weight:600;">
              Open &rarr;
            </div>
          </a>
        """)
    body = f"""
      <div style="max-width:880px;margin:0 auto;padding:24px 18px 60px;">
        <h1 style="font-family:Georgia,serif;color:#33507e;margin-bottom:6px;">
          Meet your companions
        </h1>
        <p style="color:#555;margin:0 0 24px;font-size:1.02em;line-height:1.5;max-width:620px;">
          Six AI companions are available throughout Sancta Familia — each
          shaped for a different part of family life. Tap any card to open
          that companion in their own chat.
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
                    gap:14px;">
          {''.join(cards)}
        </div>
      </div>
    """
    return html_page("Companions", body)
