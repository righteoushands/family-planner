# H1 VERIFICATION REPORT — full, raw, uncompressed (2026-07-03)

Scope: the H1 build (Step 5 shopping-day skeleton) committed at checkpoint
`ba1960b9c2a2318bf1df7acbfc40733023341797`. Everything below is pasted from
actual tool output, actual file contents, and the actual git diff — not
summarized.

---

## PART 0 — claud.md READ-BACK (Rule 15): every rule, pasted back

**Python 3.11 hard rules — never violate these**
1. No backslashes inside f-strings
2. No nested quotes inside f-strings — use a variable outside the f-string instead
3. All GET routing uses elif chains in do_GET — never a bare if, never nested if
   blocks for routing. POST routing in do_POST ALSO uses elif chains
   (`elif path == "/route-name": ... return`) — this is the real convention in the
   live code, verified June 28 2026. The ONE exception is the multipart recipe
   routes (/recipe-save, /recipe-import): they share an `elif path in (...)` outer
   block with nested `if path ==` inner blocks ONLY to share upload-parsing setup.
   Do NOT copy that nested pattern for ordinary JSON or form routes.
   [CORRECTED June 28 2026: a June 10 note had claimed do_POST uses standalone if
   blocks. The live code uses elif chains. Code wins.]
4. Never put import statements inside if blocks or functions
   [KNOWN DEVIATION, not a license: several live do_POST handlers use inline
   `import json as _json` etc. New code keeps imports at module top.]
5. All file writes use safe_save_json (tmp file + os.replace) — never open(f,'w') directly
6. No walrus operator (:=)
7. Never use a raw newline escape inside a JS string within a Python string
   literal — the browser must receive the escape sequence, not a raw newline
8. multipart/form-data parsing: when fetch POSTs use FormData the server receives
   multipart/form-data not urlencoded. do_POST must sniff Content-Type and parse
   with cgi.FieldStorage for multipart. If a POST handler receives empty data,
   check the Content-Type first.
9. py_compile passes but runtime fails: py_compile only validates syntax, not
   runtime correctness. Always run an in-process smoke test after py_compile to
   catch NameError, missing variable definitions, and import failures. After the
   in-process smoke test, also run the relevant existing verify_phase_*.py harness
   for the area touched and paste the result. Do not skip the harness run for
   changes that touch shared data files, save paths, or any function called from
   more than one place.
10. Test fixtures must never write to live data: verification harnesses must
    always operate on a temp copy of live data files. Never call save_progress,
    safe_save_json, or any write helper on live data during testing. Always
    restore from backup after any test that touches data files.
10a. RULE 10 ADDENDUM — ISOLATION MUST BE STRUCTURAL, NOT PROCEDURAL. Any
    verify_*.py harness that reads or writes app data must import its isolation
    guard (e.g. mw_test_isolation.assert_isolated) as the literal first import in
    the file — before data_helpers, config, or any render_*.py module. The guard
    must be called before the first write, and must raise (not warn) if the write
    target still resolves to a live path. Snapshot-and-restore-after is NOT
    equivalent to never touching live data. When isolating a new data store,
    extend the existing isolation module's pattern rather than writing a new
    one-off mechanism.
11. Double-escaping HTML entities: never pass a string that is already
    HTML-escaped through escape() again.
12. JS newline rule (Rule 7) applies to ALL files containing JS embedded in
    Python, not just render_frol_wizard.py.
13. FROL WIZARD NESTED FORM ADDENDUM — any form inside a section body posting to
    /frol-wizard suppresses the Save and Continue button (_body_has_form checks
    for action="/frol-wizard"). Confirm every new form's action attribute.
14. PRE-FLIGHT CHECKLIST — before any spec: (1) how many files, list them —
    unknown means diagnosis first; (2) JS inside Python f-strings? flag the
    backslash-n rule; (3) form handling? confirm no nested forms posting to
    /frol-wizard; (4) root cause confirmed or assumed? assumed means diagnose
    first; (5) multiple files at once? break into single-purpose instructions;
    (6) data shape changes? confirm before/after structure explicitly.
15. CLAUD.MD READ-BACK REQUIRED — at the start of every session read claud.md and
    paste back every rule found; then identify which rules apply to today's task.
    If you cannot paste the rules back accurately, stop and ask Lauren to
    re-paste claud.md.
16. MAGNIFICA HUMANITAS DESIGN PRINCIPLES — the app must never become an
    optimization engine; people are persons called to relationship and communion,
    not projects to be optimized. (1) The app is a tool not an authority — every
    AI suggestion framed as suggestion, never prescription. (2) Companions serve
    real relationships, never replace them. (3) AI supports thinking, does not
    replace it — ask before suggesting. (4) Be transparent about what AI is —
    no theological claims with personal authority; prayer texts from verified
    Catholic sources only. (5) Language of grace not performance — no
    gamification, streaks, or shaming scores; a hard day is never failure.
    (6) Subsidiarity — Lauren is always the authority. (7) Formation in digital
    wisdom — JP should finish high school able to plan his day without the app.
    Every feature must answer yes to at least one of the four questions
    (faithful to truth / learn and teach / real closeness / justice and peace)
    and harm none.
17. ONE FIX PER INSTRUCTION — never bundle multiple fixes into one instruction
    unless same-file and directly related. Complex multi-file builds are broken
    into sequential single-purpose phases with a compile check and report
    between each phase.
18. AUGUST 15TH BUILD PLAN IS THE PRIORITY FILTER — between June 1 and August 15
    2026 every build request is checked against the August 15th plan; off-plan
    requests are flagged before starting; new ideas go on the post-September
    list. Scope is the first thing to cut, not quality.
19. BUILD FOR A FUTURE SECOND FAMILY — never hardcode McAdams specifics; family
    identity/config in app_settings.json; all data reads/writes through
    data_helpers.py; no single-user assumptions where cheap to avoid.
    [KNOWN DEBT: build_lorenzo_context hardcodes the roster; do not deepen.]
20. PRESERVE SCROLL ON SAME-PAGE RELOADS — any fetch() POST that on success
    reloads the SAME page via window.location.href must save window.scrollY to
    sessionStorage before navigating and restore+clear on the next load.
    Forward navigations to a different page/step are exempt.
    render_meal_wizard_step4.py is the reference implementation.
21. SESSION HELPER SHALLOW-MERGE — update_meal_wizard_session merges ONLY at the
    top level. Passing a whole nested key (e.g. {"suggested_meals": {...}})
    REPLACES that entire nested dict, dropping sibling inner keys. To preserve
    siblings: read fresh, .update(), write merged — and read the snapshot
    immediately before the write, not before a long-running step.
    [KNOWN DEVIATION July 1 2026: bit the Step 4 confirm-mirror; fixed by
    fresh-read + merge in the generate handler.]
22. MERGE-BASED GENERATE NO LONGER PRUNES — stale suggested_meals entries
    accumulate; renders are gated by window × confirmed_what_to_plan so stale
    entries are inert, EXCEPT a stale date::slot re-entering window×to_plan
    while unconfirmed resurfaces its old suggestion. Low severity; logged not
    fixed. Cross-ref KI-001/KI-002.

**Named sections also read:** People (James 13 months — never assigned tasks);
Data file patterns (person-key casing, compound progress keys, date-key
formats); Route patterns (_JSON_PATHS is a LOCAL set inside do_POST ~3536 —
new JSON routes must be added there); Anchor-tag navigation (anchors cannot
POST; destination handler must accept + persist query params it needs); AI
calls (Lorenzo = claude-haiku-4-5-20251001; _repair_and_parse_json is
plan-importer-only); Change discipline (additive only; known-issues tracker
lives OUTSIDE the repo — never create one in-repo; modules under 800 lines);
FROL form-bypass trap; DOC CORRECTION LOG (June 28 + July 1 2026 corrections).

**Rules that apply to THIS task (H1 verification report):**
- **15** — this read-back.
- **9** — paste actual verification output, not claims → Part 1 below is the
  raw run. (The "relevant existing harness" clause: no verify_*.py harness
  covers step5 yet — the H1 spec explicitly said not to create one; the step4
  harnesses cover the only shared surface touched, and the step4 file change
  is a banner-HTML-only edit.)
- **10 / 10a** — the smoke test re-run below imports mw_test_isolation as the
  literal first project import and proves live-file integrity by sha256.
- **3, 4, 5, 7, 12, 21** — verified against the pasted diffs in Part 3 (elif
  routes; module-top import; write via update_meal_wizard_session →
  safe_save_json; JS as concatenated literals with no raw newline escapes;
  scalar top-level session key).
- **17** — this instruction is report-only; no code was changed for it (the
  only file activity was re-creating, running, and deleting the temp smoke
  test, plus writing this response document).

---

## PART 1 — SMOKE TEST, FULL RAW OUTPUT

The original H1 smoke test was an ad-hoc temp file, deleted after its run per
the spec. For this report it was re-created with the "no other key changed"
check split into NINE NAMED per-key assertions — the key names below were
read (read-only) from the live data/meal_wizard_session.json immediately
before the run:

```
['confirmed_inventory', 'use_soon_items', 'confirmed_what_to_plan',
 'confirmed_complexity', 'planning_window', 'confirmed_meals',
 'suggested_meals', 'used_proteins', 'plan_locked_at']
```

Command: `PYTHONPATH=. python3 data/_smoke_h1_step5.py` (temp file, deleted
after the run). Complete unedited output:

```
sha256 of LIVE data/meal_wizard_session.json BEFORE: 9088a81511e120e6096d3cd5be4f1ac04fbe5bc16a0462f8dbc36bf734b73e98
Seeded isolated session keys: ['confirmed_complexity', 'confirmed_inventory', 'confirmed_meals', 'confirmed_what_to_plan', 'plan_locked_at', 'planning_window', 'suggested_meals', 'use_soon_items', 'used_proteins']
127.0.0.1 - - [03/Jul/2026 13:35:32] "POST /meal-wizard-step5-save HTTP/1.1" 200 -
PASS POST day=Wednesday -> HTTP 200 body {"ok":true}
PASS confirmed_shopping_day == 'Wednesday'
PASS key unchanged: confirmed_inventory
PASS key unchanged: use_soon_items
PASS key unchanged: confirmed_what_to_plan
PASS key unchanged: confirmed_complexity
PASS key unchanged: planning_window
PASS key unchanged: confirmed_meals
PASS key unchanged: suggested_meals
PASS key unchanged: used_proteins
PASS key unchanged: plan_locked_at
PASS no unexpected keys added (after = 9 seeded + confirmed_shopping_day)
127.0.0.1 - - [03/Jul/2026 13:35:32] "POST /meal-wizard-step5-save HTTP/1.1" 400 -
PASS POST day=Blursday -> HTTP 400 body {"ok":false,"error":"invalid day"}
PASS entire session unchanged after rejected day
127.0.0.1 - - [03/Jul/2026 13:35:32] "GET /meal-wizard-step5 HTTP/1.1" 200 -
PASS GET /meal-wizard-step5 -> HTTP 200; Wednesday selected; exactly one aria-pressed=true
sha256 of LIVE data/meal_wizard_session.json AFTER:  9088a81511e120e6096d3cd5be4f1ac04fbe5bc16a0462f8dbc36bf734b73e98
PASS live session file untouched (sha256 identical)

ALL CHECKS PASS
EXIT=0
```

Notes on what this run proves and does not prove:
- The per-key checks compare each key's value byte-identically (via
  `json.dumps(..., sort_keys=True)`) before vs after the save — inside the
  ISOLATED temp session seeded with the same 9 key names as live.
- The sha256 lines prove the LIVE session file was never touched during the
  run (identical hash before/after, and it also matches the hash from the
  original H1 run: 9088a815...b73e98 — the live file has not changed since).
- This is an isolated in-process test. It is NOT a live-browser test — see
  Part 5.

---

## PART 2 — DAY-VALIDATION ALLOWLIST + THE 7 WIRE STRINGS

### 2a. The literal allowlist definition (render_meal_wizard_step5.py, lines 27–30)

```python
# Canonical day order — also the server-side allowlist mirror (app.py validates
# against the same seven names before persisting).
_S5_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
            "Sunday"]
```

### 2b. The literal server-side validation code (app.py POST handler, lines 11036–11062)

```python
            elif path == "/meal-wizard-step5-save":
                # H1: save the shopping day. JSON body (registered in
                # _JSON_PATHS so the form-parser leaves it alone); read and
                # parse the raw body like step3-save. Writes ONE scalar session
                # key (confirmed_shopping_day) — safe under the shallow merge
                # (Rule 21: no nested structure). Day is allowlisted against
                # the same seven names the Step 5 picker renders.
                _s5_cl  = int(self.headers.get("Content-Length","0") or 0)
                _s5_raw = self.rfile.read(_s5_cl).decode("utf-8","ignore") if _s5_cl else ""
                try:    _s5_payload = json.loads(_s5_raw)
                except Exception: _s5_payload = {}
                _s5_day = str(_s5_payload.get("day","") or "").strip()
                if _s5_day not in _S5_DAYS:
                    self.send_response(400)
                    self.send_header("Content-Type","application/json")
                    self.end_headers()
                    try: self.wfile.write(b'{"ok":false,"error":"invalid day"}')
                    except BrokenPipeError: pass
                    return
                update_meal_wizard_session({"confirmed_shopping_day": _s5_day})
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                try: self.wfile.write(b'{"ok":true}')
                except BrokenPipeError: pass
                return
```

`_S5_DAYS` reaches app.py via the module-top import (app.py line 258):

```python
from render_meal_wizard_step5 import render_step5, _S5_DAYS
```

So the server validates against the SAME list object the renderer uses —
there are not two copies to drift apart.

### 2c. What the picker's fetch() actually sends, per day

The JS (pasted in full in Part 3a) defines:

```javascript
var DAYS = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
```

and each button's onclick is generated from `_S5_DAYS` as
`onclick="s5Pick('<Day>')"` (the `\u0027` escapes in the Python source are
apostrophes — the browser receives `s5Pick('Monday')` etc.). `s5Pick(day)`
sends `body: JSON.stringify({ day: day })`. The exact wire body for each of
the 7 buttons:

| Button tapped | Exact POST body sent | In `_S5_DAYS`? |
|---|---|---|
| Monday    | `{"day":"Monday"}`    | yes — exact match |
| Tuesday   | `{"day":"Tuesday"}`   | yes — exact match |
| Wednesday | `{"day":"Wednesday"}` | yes — exact match |
| Thursday  | `{"day":"Thursday"}`  | yes — exact match |
| Friday    | `{"day":"Friday"}`    | yes — exact match |
| Saturday  | `{"day":"Saturday"}`  | yes — exact match |
| Sunday    | `{"day":"Sunday"}`    | yes — exact match |

Case/spelling agreement is structural on the server side (one imported list)
and verifiable by eye on the JS side: compare the `DAYS = [...]` line above
against the `_S5_DAYS = [...]` block in 2a — seven names, identical
title-case spelling, identical order. (The JS `DAYS` array is a hand-written
literal, not generated from `_S5_DAYS` — flagged honestly: if a day name were
ever edited in one place and not the other, the onclick handlers built from
`_S5_DAYS` would still send valid values, but the in-place style swap loop
could miss a button. Today they match exactly.)

---

## PART 3 — FULL DIFFS OF ALL THREE TOUCHED FILES

Source: `git show ba1960b9c2a2318bf1df7acbfc40733023341797` (the H1
checkpoint commit). Pasted verbatim.

### 3a. render_meal_wizard_step5.py — NEW FILE, full contents (133 lines)

```python
"""
render_meal_wizard_step5.py — Meal Planning Wizard, Step 5 (shopping day).

Phase H1 (skeleton): this screen does exactly ONE thing — pick and save the
shopping day. A seven-button day picker (Monday through Sunday) shows the
session's confirmed_shopping_day as selected when already set. Tapping a day
POSTs {"day": "<DayName>"} to /meal-wizard-step5-save via fetch() and swaps the
selected state in place — no full page reload (matching the async s4Keep /
s4Change pattern in render_meal_wizard_step4.py, so Rule 20 scroll-restore is
not needed). OUT OF SCOPE for H1 (future Phase H builds, Rule 17): conflict
detection UI, the John's-note field, and any "Continue" button.

All data access goes through data_helpers (Rule 19); page chrome comes from
ui_helpers.html_page. The inline JS is built as CONCATENATED STRING LITERALS
(not an f-string) like Step 4's _S4_JS, so there are no Python-side brace or
quote conflicts (Rules 1, 2) and no backslash-n ever appears inside a JS string
(Rules 7, 12).
"""
from html import escape
from ui_helpers import html_page
from data_helpers import load_meal_wizard_session

_HEADING_FONT = "'Cormorant Garamond', serif"

_S5_TITLE = "Pick Your Shopping Day"

# Canonical day order — also the server-side allowlist mirror (app.py validates
# against the same seven names before persisting).
_S5_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
            "Sunday"]

# ── Style constants (pulled out of f-strings: Rules 1 & 2; mirror Step 4) ─────
_S5_SUBTITLE = "color:var(--ink-muted);font-size:0.95em;margin:2px 0 22px;"
_S5_CARD = ("background:var(--warm-white,#fff);border:1px solid var(--border,#e6e0d4);"
            "border-radius:var(--radius-md,12px);padding:18px 20px;margin-bottom:14px;")
_S5_HINT = "color:var(--ink);font-size:0.98em;line-height:1.5;margin:0 0 14px;"
_S5_DAY_WRAP = "display:flex;flex-direction:column;gap:8px;"
_S5_DAY_BTN = ("display:block;width:100%;text-align:left;padding:12px 16px;"
               "border:1px solid var(--border,#e6e0d4);"
               "border-radius:var(--radius-md,12px);"
               "background:var(--warm-white,#fff);color:var(--ink);"
               "font-size:1em;cursor:pointer;")
_S5_DAY_BTN_SEL = ("display:block;width:100%;text-align:left;padding:12px 16px;"
                   "border:1px solid var(--gold-mid,#c9a84a);"
                   "border-radius:var(--radius-md,12px);"
                   "background:var(--gold-mid,#c9a84a);color:var(--ink);"
                   "font-size:1em;font-weight:700;cursor:pointer;")
_S5_MSG = "color:var(--ink-muted);font-size:0.9em;margin-top:10px;min-height:1em;"
_S5_NAV_ROW = "display:flex;justify-content:flex-start;align-items:center;margin-top:18px;"
_S5_BACK = "color:var(--ink-muted);font-size:0.95em;text-decoration:none;"

# H1 inline JS — CONCATENATED STRING LITERALS (not an f-string), matching Step
# 4's _S4_JS. On success the picker swaps the selected button style in place
# (no reload). The two style strings are injected below by plain string
# concatenation; they contain no quotes, so the single-quoted JS literals stay
# valid (Rules 1, 2, 7, 12).
_S5_JS = (
    "<script>"
    "(function(){"
    "  var DAYS = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];"
    "  var STYLE_SEL = '" + _S5_DAY_BTN_SEL + "';"
    "  var STYLE_UNSEL = '" + _S5_DAY_BTN + "';"
    "  function elById(id){ return document.getElementById(id); }"
    "  window.s5Pick = function(day){"
    "    var msg = elById('s5-msg');"
    "    if(msg){ msg.textContent = ''; }"
    "    fetch('/meal-wizard-step5-save', { method:'POST',"
    "      headers:{'Content-Type':'application/json'}, body: JSON.stringify({ day: day }) })"
    "      .then(function(r){ return r.json(); })"
    "      .then(function(j){ if(j && j.ok){"
    "          for(var i = 0; i < DAYS.length; i++){"
    "            var b = elById('s5-day--' + DAYS[i]);"
    "            if(b){ b.style.cssText = (DAYS[i] === day ? STYLE_SEL : STYLE_UNSEL);"
    "                   b.setAttribute('aria-pressed', DAYS[i] === day ? 'true' : 'false'); }"
    "          }"
    "          if(msg){ msg.textContent = 'Shopping day saved: ' + day; }"
    "        } else { if(msg){ msg.textContent = 'Could not save. Please try again.'; } } })"
    "      .catch(function(){ if(msg){ msg.textContent = 'Could not save. Please try again.'; } });"
    "  };"
    "})();"
    "</script>"
)


def render_step5(user: str) -> str:
    """Step 5 of the Meal Planning Wizard — shopping day picker (H1 skeleton).
    Reads confirmed_shopping_day from the wizard session to mark the current
    selection; writes nothing (the save happens via /meal-wizard-step5-save)."""
    session = load_meal_wizard_session() or {}
    current = (session.get("confirmed_shopping_day") or "").strip()

    day_buttons = []
    for day in _S5_DAYS:
        selected = (day == current)
        style = _S5_DAY_BTN_SEL if selected else _S5_DAY_BTN
        pressed = "true" if selected else "false"
        day_buttons.append(
            f'<button type="button" id="s5-day--{day}" style="{style}" '
            f'aria-pressed="{pressed}" '
            f'onclick="s5Pick(\u0027{day}\u0027)">{escape(day)}</button>'
        )

    hint = "Which day do you usually shop? One tap saves it \u2014 you can change it any time."
    picker = (
        f'<div style="{_S5_CARD}">'
        f'<p style="{_S5_HINT}">{escape(hint)}</p>'
        f'<div style="{_S5_DAY_WRAP}">'
        f'{"".join(day_buttons)}'
        f'</div>'
        f'<div id="s5-msg" style="{_S5_MSG}"></div>'
        f'</div>'
    )

    nav = (
        f'<div style="{_S5_NAV_ROW}">'
        f'<a href="/meal-wizard-step4" style="{_S5_BACK}">\u2190 Back to your menu</a>'
        f'</div>'
    )

    inner = (
        f'<h1 style="font-family:{_HEADING_FONT};font-size:2em;font-weight:600;'
        f'color:var(--ink);margin:0 0 2px;">{_S5_TITLE}</h1>'
        f'<p style="{_S5_SUBTITLE}">Step 5 of 6 \u2014 Shopping day</p>'
        f'{picker}'
        f'{nav}'
    )
    body = (
        f'<div style="max-width:680px;margin:0 auto;padding:24px 16px 96px;">'
        f'{inner}'
        f'</div>'
        f'{_S5_JS}'
    )
    return html_page(_S5_TITLE, body)
```

(One clarification on `\u0027`: that is a Python unicode escape for the
apostrophe character, resolved at compile time — NOT a backslash surviving
into an f-string at runtime and NOT a JS-string newline. It is the same
technique Step 4 uses to keep nested quotes out of f-strings per Rule 2.)

### 3b. app.py — actual diff (git show, verbatim; 4 hunks)

```diff
diff --git a/app.py b/app.py
index e79576d..29f552a 100644
--- a/app.py
+++ b/app.py
@@ -255,6 +255,7 @@ from render_monica import render_monica_page, build_monica_context
 from render_wizards import render_wizards_page
 from render_meal_wizard import render_pantry_staples_page, render_meal_wizard_week_glance, render_meal_wizard_step2, render_meal_wizard_step3, render_meal_wizard_step4
 from render_meal_wizard_step4 import render_step4_slot_and_lock, CATEGORIES as _S4_CATEGORIES
+from render_meal_wizard_step5 import render_step5, _S5_DAYS
 from render_meal_wizard_step3 import _feast_in_window as _s3_feast_in_window, _has_sunday_batch as _s3_has_sunday_batch
 from render_meal_wizard_gen import wizard_target_slot_keys, parse_wizard_meal_response, build_wizard_meal_prompt, _WIZARD_GEN_SLOT_CAP
 from render_plan_importer import (
@@ -1354,6 +1355,16 @@ class Handler(BaseHTTPRequestHandler):
             try: self.wfile.write(html.encode())
             except BrokenPipeError: pass
             return
+        elif path == "/meal-wizard-step5":
+            html = render_step5(viewer)
+            self.send_response(200)
+            self.send_header("Content-Type","text/html; charset=utf-8")
+            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
+            self.send_header("Pragma","no-cache")
+            self.end_headers()
+            try: self.wfile.write(html.encode())
+            except BrokenPipeError: pass
+            return
         elif path == "/sister-mary":
             from render_sister_mary import render_sister_mary_page
             html = render_sister_mary_page(
@@ -3568,7 +3579,7 @@ class Handler(BaseHTTPRequestHandler):
 
         else:
             # /plan-import-apply reads its own raw JSON body — don't consume it with URL form parse
-            _JSON_PATHS = {"/plan-import-apply", "/plan-import-undo-placement", "/curriculum-save", "/curriculum-minutes", "/poetry-passage-save", "/meal-wizard-step3-save", "/meal-wizard-step4-confirm", "/meal-wizard-step4-remove", "/meal-wizard-step4-lock", "/meal-wizard-generate"}
+            _JSON_PATHS = {"/plan-import-apply", "/plan-import-undo-placement", "/curriculum-save", "/curriculum-minutes", "/poetry-passage-save", "/meal-wizard-step3-save", "/meal-wizard-step4-confirm", "/meal-wizard-step4-remove", "/meal-wizard-step4-lock", "/meal-wizard-generate", "/meal-wizard-step5-save"}
             if path in _JSON_PATHS:
                 data = {}
             else:
@@ -11022,6 +11033,33 @@ class Handler(BaseHTTPRequestHandler):
                 except BrokenPipeError: pass
                 return
 
+            elif path == "/meal-wizard-step5-save":
+                # H1: save the shopping day. JSON body (registered in
+                # _JSON_PATHS so the form-parser leaves it alone); read and
+                # parse the raw body like step3-save. Writes ONE scalar session
+                # key (confirmed_shopping_day) — safe under the shallow merge
+                # (Rule 21: no nested structure). Day is allowlisted against
+                # the same seven names the Step 5 picker renders.
+                _s5_cl  = int(self.headers.get("Content-Length","0") or 0)
+                _s5_raw = self.rfile.read(_s5_cl).decode("utf-8","ignore") if _s5_cl else ""
+                try:    _s5_payload = json.loads(_s5_raw)
+                except Exception: _s5_payload = {}
+                _s5_day = str(_s5_payload.get("day","") or "").strip()
+                if _s5_day not in _S5_DAYS:
+                    self.send_response(400)
+                    self.send_header("Content-Type","application/json")
+                    self.end_headers()
+                    try: self.wfile.write(b'{"ok":false,"error":"invalid day"}')
+                    except BrokenPipeError: pass
+                    return
+                update_meal_wizard_session({"confirmed_shopping_day": _s5_day})
+                self.send_response(200)
+                self.send_header("Content-Type","application/json")
+                self.end_headers()
+                try: self.wfile.write(b'{"ok":true}')
+                except BrokenPipeError: pass
+                return
+
             elif path == "/meal-generate":
                 import json as _json, requests as _req
                 wk     = clean_text(data.get("week",[""])[0]) or _week_key()
```

Current line numbers after the commit: import = 258, GET elif = 1358,
_JSON_PATHS = 3582, POST elif = 11036. (The report from the build turn quoted
261/1361/3585/11039 — those were pre-final-state numbers; the grep-verified
numbers after the last edit are the ones here.)

### 3c. render_meal_wizard_step4.py — actual diff (git show, verbatim; 1 hunk)

```diff
diff --git a/render_meal_wizard_step4.py b/render_meal_wizard_step4.py
index 94a317c..b9e23d9 100644
--- a/render_meal_wizard_step4.py
+++ b/render_meal_wizard_step4.py
@@ -702,8 +702,17 @@ def render_meal_wizard_step4(user: str, start_iso: str = None) -> str:
     has_lockable = _s4_has_lockable(confirmed)
 
     if locked_at:
+        # H1: once the plan is set, offer the forward step (shopping day).
+        # Forward navigation to a DIFFERENT page — Rule 20 does not apply.
         banner_text = "Your plan is set \u2014 showing on your homepage for this week."
-        banner_html = f'<div style="{_S4_BANNER}">{escape(banner_text)}</div>'
+        banner_html = (
+            f'<div style="{_S4_BANNER}">{escape(banner_text)}'
+            f'<div style="margin-top:10px;">'
+            f'<a href="/meal-wizard-step5" style="{_S4_LINK_BTN}">'
+            f'Next: pick your shopping day \u2192</a>'
+            f'</div>'
+            f'</div>'
+        )
     else:
         banner_html = ""
 
```

(The commit also contains three files that are not code: this session's
response document, the attached H1 spec text file, and an agent-assets
metadata file — visible in the commit stat. No other code files changed.)

---

## PART 4 — WHAT "ARCHITECT CODE REVIEW" ACTUALLY IS (direct answer)

It is **not me re-reading my own output, but it is also not an independent
process in the way a human reviewer would be.** Plainly:

- It is a separate reviewer subagent — a distinct AI instance that Replit
  provides, invoked by me through a review tool. It is given the file paths
  and the git diff and reads the actual code itself; it does not just grade
  my summary of what I did.
- It is a different context from me: it forms its judgment from the files and
  diff, so it can and does catch things I missed (it has flagged real issues
  in earlier phases of this project).
- BUT: I choose what to send it, I frame the task description it receives,
  and it is another AI — not a human, and not adversarial. Its "PASS" is a
  second automated opinion, not independent certification.

So the honest label is: **a second AI reviewer reading the real diff, invoked
and framed by me.** Where my reports have said "architect review: PASS," read
it as that — useful, materially better than self-review, but not independent
verification. Your own Part 5 question is the actual independent check.

---

## PART 5 — REAL-DATA / LIVE-BROWSER VERIFICATION: NOT DONE (direct answer)

**No.** `/meal-wizard-step5` has NOT been loaded in a live authenticated
browser session, and no day has been tapped against the live session file.
What HAS actually been done, exactly:

1. The isolated in-process smoke test (Part 1) — synthetic session in a temp
   file, in-process server, authenticated via a programmatically created
   session token. This exercised the real GET render and the real POST
   handler code paths end-to-end over HTTP, but against isolated data.
2. An unauthenticated `curl` against the LIVE running server:
   `GET /meal-wizard-step5 -> 302` and `GET /meal-wizard-step4 -> 302`
   (identical auth-redirect behavior — proves the route is live and gated,
   nothing more).
3. The live server was restarted so the running process has the new code.

What has NOT happened: no real browser page-load as a logged-in user, no
visual confirmation of the picker, no tap, and — deliberately — no write of
`confirmed_shopping_day` to the live session file. The live file's sha256
(9088a815…b73e98) is unchanged since before the H1 build.

Why I didn't do it: tapping a day in the live app writes to live data, and
the standing rules of this project have me leave live-data mutations to you
unless instructed. It is a safe write if you want it — a single scalar key,
re-tappable to change, and Blursday-proof — but it changes the live session
file.

**The 60-second live check, when you want it:** log in → open
`/meal-wizard-step4` → the gold "plan is set" banner should now show
"Next: pick your shopping day →" → click it → seven day buttons, none
highlighted (nothing saved yet on live) → tap your real shopping day → the
tapped button turns gold in place, "Shopping day saved: <Day>" appears under
the list, no page reload → refresh the page → the same day is still
highlighted. If any of that differs, tell me exactly which step and I will
diagnose before touching anything else. Alternatively, say the word and I
will perform the authenticated tap against the live server myself and paste
the before/after of the live session file.
