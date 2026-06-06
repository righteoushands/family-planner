---
name: Companion/page route + nav wiring pattern
description: How to wire a new authenticated HTML page route in this raw http.server app (Sancta Familia)
---

# Wiring a new authenticated page route

**Rule:** New full-page HTML routes follow the companion-page pattern exactly. Do not invent auth checks or wrappers.

**How to apply:**
- Render module: build a `body` string and `return html_page(title, body)` (html_page lives in ui_helpers.py and supplies chrome + `:root` design tokens). Import `html_page` at module top (Rule 4). Use existing CSS vars only (--ink, --gold-mid, --warm-white, --parchment, --border, --radius-*, --shadow-*).
- Route: add an `elif path == "/x":` branch in `do_GET` (Handler in app.py), in the elif chain near the other companion routes (/lucy, /lorenzo, /companions, /sister-mary). Mirror their body exactly: send_response(200) + Content-Type text/html + no-store/no-cache + Pragma + end_headers + `try: self.wfile.write(html.encode()) except BrokenPipeError: pass` + `return`.
- Auth: handled GLOBALLY by `viewer = self._require_auth(path)` (app.py ~line 888), which runs before the route chain. Per-route auth checks are NOT added for normal pages. `_require_auth` only bypasses /login, /logout, /static/*. Pass `viewer` (NOT a `user` var — there is no `user` binding in do_GET) into the render fn.
- Nav highlight: add the path to the `morePaths` JS array in ui_helpers.py (single-quoted entry) so the mobile More button highlights on that page. Active-state JS auto-highlights an item whose href matches the current path.

**Why:** All companion pages rely on the single upstream auth gate; duplicating auth or page chrome per-route causes drift and rule violations. Verified live: an authed page returns 302 to /login when logged out, 200 when authed.
