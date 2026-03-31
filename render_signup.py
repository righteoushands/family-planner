# -*- coding: utf-8 -*-
"""
render_signup.py - Beta waitlist signup survey.
Stores responses in data/waitlist.json
Accessible at /signup (public) and /waitlist (admin, password-protected)
"""
import json, os
from datetime import datetime
from html import escape
from safe_utils import ensure_file, safe_save_json

WAITLIST_FILE = "data/waitlist.json"


def load_waitlist():
    return ensure_file(WAITLIST_FILE, [])

def save_signup(entry: dict):
    os.makedirs("data", exist_ok=True)
    waitlist = load_waitlist()
    waitlist.append(entry)
    safe_save_json(WAITLIST_FILE, waitlist)


def render_signup_page(submitted: bool = False, error: str = "") -> str:
    if submitted:
        return _render_thankyou()

    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sancta Familia — Join the Waitlist</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=DM+Sans:wght@300;400;500;600&display=swap');
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --ink: #1c1610; --gold: #8b6914; --gold-light: #f5ead8;
  --parchment: #f7f3ee; --border: #e8e0d5; --muted: #6b5e4e;
  --crimson: #7c1a1a; --forest: #2d5016;
}
body {
  font-family: 'DM Sans', sans-serif;
  background: var(--ink);
  min-height: 100vh;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 40px 16px 60px;
}
.container {
  width: 100%;
  max-width: 560px;
}
.logo {
  font-family: 'Cormorant Garamond', serif;
  font-size: 42px;
  font-weight: 600;
  color: var(--gold-light);
  line-height: 1;
  margin-bottom: 6px;
}
.tagline {
  font-family: 'Cormorant Garamond', serif;
  font-style: italic;
  font-size: 17px;
  color: rgba(245,234,216,0.55);
  margin-bottom: 10px;
}
.lede {
  font-size: 14px;
  color: rgba(245,234,216,0.65);
  line-height: 1.7;
  margin-bottom: 36px;
  border-left: 2px solid var(--gold);
  padding-left: 14px;
}
.card {
  background: var(--parchment);
  border-radius: 20px;
  padding: 32px 28px;
  margin-bottom: 16px;
}
.card-title {
  font-family: 'Cormorant Garamond', serif;
  font-size: 22px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 20px;
}
.field { margin-bottom: 18px; }
label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 6px;
}
label .req { color: var(--crimson); margin-left: 2px; }
input[type=text], input[type=email], input[type=number], textarea, select {
  width: 100%;
  padding: 11px 14px;
  border: 1.5px solid var(--border);
  border-radius: 10px;
  font-family: inherit;
  font-size: 14px;
  color: var(--ink);
  background: white;
  outline: none;
  transition: border-color 0.15s;
}
input:focus, textarea:focus, select:focus { border-color: var(--gold); }
textarea { resize: vertical; min-height: 80px; }
.check-group { display: flex; flex-direction: column; gap: 8px; }
.check-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border: 1.5px solid var(--border);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
  background: white;
}
.check-item:has(input:checked) {
  border-color: var(--gold);
  background: #fef9f0;
}
.check-item input { width: 16px; height: 16px; accent-color: var(--gold); flex-shrink: 0; }
.check-item span { font-size: 13px; color: var(--ink); }
.radio-group { display: flex; flex-direction: column; gap: 8px; }
.radio-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border: 1.5px solid var(--border);
  border-radius: 10px;
  cursor: pointer;
  background: white;
  transition: all 0.15s;
}
.radio-item:has(input:checked) {
  border-color: var(--gold);
  background: #fef9f0;
}
.radio-item input { width: 16px; height: 16px; accent-color: var(--gold); flex-shrink: 0; }
.radio-item span { font-size: 13px; color: var(--ink); }
.section-divider {
  font-family: 'Cormorant Garamond', serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--ink);
  padding-bottom: 14px;
  margin-bottom: 18px;
  border-bottom: 1px solid var(--border);
}
.submit-btn {
  width: 100%;
  padding: 16px;
  background: var(--ink);
  color: var(--gold-light);
  border: none;
  border-radius: 14px;
  font-family: inherit;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  letter-spacing: 0.03em;
  margin-top: 8px;
  transition: opacity 0.15s;
}
.submit-btn:hover { opacity: 0.85; }
.error-msg {
  background: #fdecea;
  border: 1px solid #f5b8b0;
  color: var(--crimson);
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 13px;
  margin-bottom: 16px;
}
.features-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 24px;
}
.feature-chip {
  background: rgba(245,234,216,0.08);
  border: 1px solid rgba(245,234,216,0.15);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 12px;
  color: rgba(245,234,216,0.75);
  display: flex;
  align-items: center;
  gap: 8px;
}
.feature-chip .icon { font-size: 16px; }
.privacy-note {
  font-size: 11px;
  color: rgba(245,234,216,0.3);
  text-align: center;
  margin-top: 16px;
  line-height: 1.6;
}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div style="padding: 0 4px 32px;">
    <div class="logo">Sancta<br>Familia</div>
    <div class="tagline">A planning system for Catholic homeschool families</div>
    <div class="lede">
      One app for your daily routine, school schedule, liturgical calendar,
      family grid, chore rotations, and AI-powered planning — built by a
      homeschool mom, for homeschool families.
    </div>
    <div class="features-grid">
      <div class="feature-chip"><span class="icon">📋</span> Daily planning flow</div>
      <div class="feature-chip"><span class="icon">✝</span> Liturgical calendar</div>
      <div class="feature-chip"><span class="icon">👨‍👩‍👧‍👦</span> Family day grid</div>
      <div class="feature-chip"><span class="icon">✨</span> AI scheduling assistant</div>
      <div class="feature-chip"><span class="icon">📚</span> School management</div>
      <div class="feature-chip"><span class="icon">🧹</span> Chore rotations</div>
    </div>
  </div>

  ''' + (f'<div class="error-msg">{escape(error)}</div>' if error else '') + '''

  <form method="POST" action="/signup-submit">

    <!-- Card 1: About you -->
    <div class="card">
      <div class="card-title">Tell us about yourself</div>

      <div class="field">
        <label>Your name <span class="req">*</span></label>
        <input type="text" name="name" placeholder="First name is fine" required>
      </div>

      <div class="field">
        <label>Email address <span class="req">*</span></label>
        <input type="email" name="email" placeholder="you@example.com" required>
      </div>

      <div class="field">
        <label>How many children do you have?</label>
        <input type="number" name="num_children" min="0" max="20" placeholder="e.g. 4">
      </div>

      <div class="field">
        <label>Ages of your children (homeschooled)</label>
        <input type="text" name="child_ages" placeholder="e.g. 17, 15, 12, 1">
      </div>

      <div class="field">
        <label>How long have you been homeschooling?</label>
        <div class="radio-group">
          <label class="radio-item"><input type="radio" name="hs_years" value="Just starting"> <span>Just starting out</span></label>
          <label class="radio-item"><input type="radio" name="hs_years" value="1-3 years"> <span>1–3 years</span></label>
          <label class="radio-item"><input type="radio" name="hs_years" value="4-8 years"> <span>4–8 years</span></label>
          <label class="radio-item"><input type="radio" name="hs_years" value="9+ years"> <span>9+ years (seasoned veteran)</span></label>
        </div>
      </div>
    </div>

    <!-- Card 2: Your planning life -->
    <div class="card">
      <div class="card-title">Your planning life right now</div>

      <div class="field">
        <label>What do you currently use to plan your days?</label>
        <div class="check-group">
          <label class="check-item"><input type="checkbox" name="current_tools" value="Paper planner"> <span>Paper planner or bullet journal</span></label>
          <label class="check-item"><input type="checkbox" name="current_tools" value="Google Calendar"> <span>Google Calendar</span></label>
          <label class="check-item"><input type="checkbox" name="current_tools" value="iCloud Calendar"> <span>iCloud / Apple Calendar</span></label>
          <label class="check-item"><input type="checkbox" name="current_tools" value="Homeschool-specific app"> <span>Homeschool-specific app (Homeschool Planet, etc.)</span></label>
          <label class="check-item"><input type="checkbox" name="current_tools" value="Spreadsheets"> <span>Spreadsheets</span></label>
          <label class="check-item"><input type="checkbox" name="current_tools" value="Nothing consistent"> <span>Nothing consistent — that's the problem</span></label>
        </div>
      </div>

      <div class="field">
        <label>What's your biggest daily planning challenge?</label>
        <textarea name="biggest_challenge" placeholder="e.g. keeping track of each child's schedule, remembering chores, planning around appointments..."></textarea>
      </div>

      <div class="field">
        <label>Which features interest you most? (pick all that apply)</label>
        <div class="check-group">
          <label class="check-item"><input type="checkbox" name="features" value="Daily planning flow"> <span>📋 The morning planning routine (Step 0–5)</span></label>
          <label class="check-item"><input type="checkbox" name="features" value="Family grid"> <span>👨‍👩‍👧‍👦 Family day grid — everyone's schedule at a glance</span></label>
          <label class="check-item"><input type="checkbox" name="features" value="Liturgical calendar"> <span>✝ Liturgical calendar integration</span></label>
          <label class="check-item"><input type="checkbox" name="features" value="AI assistant"> <span>✨ AI scheduling assistant</span></label>
          <label class="check-item"><input type="checkbox" name="features" value="School management"> <span>📚 School schedule and subject tracking</span></label>
          <label class="check-item"><input type="checkbox" name="features" value="Chore rotations"> <span>🧹 Chore and rotation systems</span></label>
          <label class="check-item"><input type="checkbox" name="features" value="Calendar sync"> <span>📆 Calendar sync (iCloud, Google, parish)</span></label>
        </div>
      </div>
    </div>

    <!-- Card 3: Fit and interest -->
    <div class="card">
      <div class="card-title">Interest & fit</div>

      <div class="field">
        <label>What best describes your family?</label>
        <div class="radio-group">
          <label class="radio-item"><input type="radio" name="family_type" value="Catholic homeschool"> <span>Catholic homeschool family</span></label>
          <label class="radio-item"><input type="radio" name="family_type" value="Christian homeschool"> <span>Christian homeschool family (other denomination)</span></label>
          <label class="radio-item"><input type="radio" name="family_type" value="Secular homeschool"> <span>Secular homeschool family</span></label>
          <label class="radio-item"><input type="radio" name="family_type" value="Not homeschooling"> <span>Not homeschooling but interested in the planning system</span></label>
        </div>
      </div>

      <div class="field">
        <label>What device do you use most during your day?</label>
        <div class="radio-group">
          <label class="radio-item"><input type="radio" name="device" value="iPhone"> <span>iPhone</span></label>
          <label class="radio-item"><input type="radio" name="device" value="Android phone"> <span>Android phone</span></label>
          <label class="radio-item"><input type="radio" name="device" value="iPad/tablet"> <span>iPad or tablet</span></label>
          <label class="radio-item"><input type="radio" name="device" value="Desktop/laptop"> <span>Desktop or laptop</span></label>
        </div>
      </div>

      <div class="field">
        <label>Would you be willing to pay a monthly subscription?</label>
        <div class="radio-group">
          <label class="radio-item"><input type="radio" name="willingness_to_pay" value="Yes, if it saves me time"> <span>Yes, if it genuinely saves me time and stress</span></label>
          <label class="radio-item"><input type="radio" name="willingness_to_pay" value="Maybe, depends on price"> <span>Maybe — depends on the price</span></label>
          <label class="radio-item"><input type="radio" name="willingness_to_pay" value="Prefer one-time"> <span>I'd prefer a one-time purchase</span></label>
          <label class="radio-item"><input type="radio" name="willingness_to_pay" value="Only if free"> <span>Only if there's a free tier</span></label>
        </div>
      </div>

      <div class="field">
        <label>What would you expect to pay per month?</label>
        <div class="radio-group">
          <label class="radio-item"><input type="radio" name="price_range" value="Under $5"> <span>Under $5/month</span></label>
          <label class="radio-item"><input type="radio" name="price_range" value="$5-10"> <span>$5–10/month</span></label>
          <label class="radio-item"><input type="radio" name="price_range" value="$10-15"> <span>$10–15/month</span></label>
          <label class="radio-item"><input type="radio" name="price_range" value="$15-20"> <span>$15–20/month for the full system</span></label>
        </div>
      </div>

      <div class="field">
        <label>Anything else you'd want us to know?</label>
        <textarea name="other_notes" placeholder="Features you'd want, concerns, questions, or just encouragement..."></textarea>
      </div>

      <div class="field">
        <label>Notify me when it launches</label>
        <div class="radio-group">
          <label class="radio-item"><input type="radio" name="notify" value="Yes" checked> <span>Yes — send me an email when it's ready</span></label>
          <label class="radio-item"><input type="radio" name="notify" value="Beta"> <span>Yes — and I'd love to be a beta tester</span></label>
          <label class="radio-item"><input type="radio" name="notify" value="No"> <span>No notifications, just submitting feedback</span></label>
        </div>
      </div>

    </div>

    <button type="submit" class="submit-btn">Submit &rarr;</button>

  </form>

  <div class="privacy-note">
    Your information is used only to notify you about this app's launch.<br>
    We will never share or sell your email address.
  </div>

</div>
</body>
</html>'''


def _render_thankyou() -> str:
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Thank you — Sancta Familia</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=DM+Sans:wght@300;400;500;600&display=swap');
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'DM Sans',sans-serif;background:#1c1610;min-height:100vh;
     display:flex;align-items:center;justify-content:center;padding:40px 16px;}
.wrap{max-width:480px;text-align:center;}
.cross{font-size:48px;margin-bottom:20px;}
.title{font-family:'Cormorant Garamond',serif;font-size:38px;font-weight:600;
       color:#f5ead8;line-height:1.1;margin-bottom:14px;}
.body{font-size:15px;color:rgba(245,234,216,0.6);line-height:1.7;margin-bottom:32px;}
.highlight{color:#f5ead8;font-weight:600;}
.btn{display:inline-block;padding:14px 28px;background:#8b6914;color:#f5ead8;
     border-radius:12px;font-size:14px;font-weight:700;text-decoration:none;
     letter-spacing:0.03em;}
</style>
</head>
<body>
<div class="wrap">
  <div class="cross">✝</div>
  <div class="title">You&#39;re on the list.</div>
  <div class="body">
    Thank you for your interest in <span class="highlight">Sancta Familia</span>.<br><br>
    We&#39;ll be in touch when the app is ready for early access.
    Your feedback will help shape something genuinely useful for
    Catholic homeschool families.
  </div>
  <a href="/signup" class="btn">Submit another response</a>
</div>
</body>
</html>'''


def render_waitlist_admin(password_ok: bool = False) -> str:
    """Admin view of all signups — password protected."""
    if not password_ok:
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Waitlist Admin</title>
<style>
body{font-family:sans-serif;background:#1c1610;display:flex;align-items:center;
     justify-content:center;min-height:100vh;padding:20px;}
.box{background:#f7f3ee;border-radius:16px;padding:32px;max-width:320px;width:100%;}
h2{font-size:18px;margin-bottom:16px;}
input{width:100%;padding:10px;border:1.5px solid #e8e0d5;border-radius:8px;
      font-family:inherit;font-size:14px;margin-bottom:12px;}
button{width:100%;padding:12px;background:#1c1610;color:#f5ead8;border:none;
       border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;}
</style></head><body>
<div class="box">
  <h2>Waitlist Admin</h2>
  <form method="POST" action="/waitlist">
    <input type="password" name="pw" placeholder="Password">
    <button type="submit">View List</button>
  </form>
</div>
</body></html>'''

    waitlist = load_waitlist()
    if not waitlist:
        entries_html = '<p style="color:#888;padding:20px;">No signups yet.</p>'
    else:
        entries_html = ''
        for i, e in enumerate(waitlist, 1):
            notify_badge = {
                'Yes':  ('background:#eef7ee;color:#2a5a2a', 'Notify'),
                'Beta': ('background:#eff6ff;color:#1d4ed8', 'Beta tester'),
                'No':   ('background:#f5f5f5;color:#888',    'No notify'),
            }.get(e.get('notify',''), ('background:#f5f5f5;color:#888', e.get('notify','')))

            features = ', '.join(e.get('features', [])) or '—'
            tools    = ', '.join(e.get('current_tools', [])) or '—'
            entries_html += f'''
            <div style="padding:16px;border-bottom:1px solid #f0ebe4;">
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap;">
                <span style="font-weight:700;font-size:15px;">{i}. {escape(e.get("name",""))}</span>
                <a href="mailto:{escape(e.get("email",""))}" style="color:#8b6914;font-size:13px;">{escape(e.get("email",""))}</a>
                <span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;{notify_badge[0]}">{notify_badge[1]}</span>
              </div>
              <div style="font-size:12px;color:#666;display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;">
                <div><strong>Children:</strong> {escape(str(e.get("num_children","")))} ({escape(e.get("child_ages",""))})</div>
                <div><strong>HS years:</strong> {escape(e.get("hs_years",""))}</div>
                <div><strong>Family type:</strong> {escape(e.get("family_type",""))}</div>
                <div><strong>Device:</strong> {escape(e.get("device",""))}</div>
                <div><strong>Willing to pay:</strong> {escape(e.get("willingness_to_pay",""))}</div>
                <div><strong>Price range:</strong> {escape(e.get("price_range",""))}</div>
                <div style="grid-column:span 2;"><strong>Tools now:</strong> {escape(tools)}</div>
                <div style="grid-column:span 2;"><strong>Interested in:</strong> {escape(features)}</div>
              </div>
              {f'<div style="margin-top:8px;font-size:12px;background:#fafafa;padding:8px;border-radius:6px;color:#444;"><strong>Challenge:</strong> {escape(e.get("biggest_challenge",""))}</div>' if e.get("biggest_challenge") else ""}
              {f'<div style="margin-top:6px;font-size:12px;background:#fafafa;padding:8px;border-radius:6px;color:#444;"><strong>Notes:</strong> {escape(e.get("other_notes",""))}</div>' if e.get("other_notes") else ""}
              <div style="margin-top:6px;font-size:10px;color:#bbb;">{escape(e.get("submitted_at",""))}</div>
            </div>'''

    beta_count   = sum(1 for e in waitlist if e.get('notify') == 'Beta')
    notify_count = sum(1 for e in waitlist if e.get('notify') in ('Yes', 'Beta'))

    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Waitlist — {len(waitlist)} signups</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&display=swap');
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'DM Sans',sans-serif;background:#f7f3ee;padding:24px 16px;}}
.header{{max-width:800px;margin:0 auto 20px;display:flex;align-items:center;
         justify-content:space-between;flex-wrap:wrap;gap:12px;}}
h1{{font-size:22px;color:#1c1610;}}
.stat{{background:white;border:1px solid #e8e0d5;border-radius:10px;
       padding:10px 16px;font-size:13px;color:#6b5e4e;}}
.stat strong{{color:#1c1610;font-size:18px;display:block;}}
.card{{max-width:800px;margin:0 auto;background:white;border-radius:16px;
       border:1px solid #e8e0d5;overflow:hidden;}}
a{{color:inherit;}}
</style>
</head><body>
<div class="header">
  <h1>Waitlist &mdash; {len(waitlist)} responses</h1>
  <div style="display:flex;gap:10px;flex-wrap:wrap;">
    <div class="stat"><strong>{notify_count}</strong> want notification</div>
    <div class="stat"><strong>{beta_count}</strong> want to beta test</div>
    <div class="stat"><a href="/signup">View signup form</a></div>
    <div class="stat"><a href="/">Back to app</a></div>
  </div>
</div>
<div class="card">{entries_html}</div>
</body></html>'''
