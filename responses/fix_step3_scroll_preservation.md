# claud.md read-back + FIX — Rule 20 applied to Step 3 (s3Save)

## claud.md — all rules (Rule 15 read-back)

### Python 3.11 hard rules (1–12)
1. No backslashes inside f-strings.
2. No nested quotes inside f-strings — use a variable outside the f-string.
3. GET routing uses `elif` chains in `do_GET`; POST routing in `do_POST` ALSO uses `elif` chains. ONE exception: multipart recipe routes (`/recipe-save`, `/recipe-import`) share an `elif path in (...)` outer block with nested `if` inner blocks for upload-parsing setup only.
4. Never put imports inside `if` blocks or functions. [Known deviation: some do_POST handlers use inline imports; new code keeps imports at module top.]
5. All file writes use `safe_save_json` (tmp + `os.replace`) — never `open(f, 'w')`.
6. No walrus operator (`:=`).
7. Never use a raw newline inside a JS string within a Python string literal — use the escape sequence.
8. multipart/form-data: FormData POSTs arrive as multipart; sniff Content-Type and use `cgi.FieldStorage`.
9. py_compile is syntax-only; after it run an in-process smoke test, then the relevant `verify_phase_*.py` harness and paste the result.
10. Test fixtures never write to live data; use a temp copy; restore from backup after.
11. Never double-escape HTML entities.
12. JS newline rule (7) applies to ALL files with JS embedded in Python.

### Conventions
Data in `data/*.json`; person keys title-case in progress/chores/events, lowercase in auth/pins & profiles; progress keys `"YYYY-MM-DD::Person::task"`; GET → render_*.py; POST → do_POST elif; JSON POST bodies registered in `_JSON_PATHS`; `<a href>` can't POST/mutate. FROL form bypass trap: `_body_has_form` suppresses Save-and-Continue on `action="/frol-wizard"`.

### Additional rules (13–20)
13. FROL nested-form addendum — confirm section-body form actions aren't `/frol-wizard`.
14. Pre-flight checklist — file count/list; JS-in-f-strings; form handling; confirmed vs assumed root cause; multi-file → split; data-shape change → confirm.
15. claud.md read-back required at session start.
16. Magnifica Humanitas — tool not authority; suggestions not prescriptions; AI supports not replaces thinking; transparency; subsidiarity.
17. One fix per instruction.
18. August 15th build plan is the priority filter (June 1–Aug 15 2026).
19. Build for a future second family — config in app_settings.json; data IO through data_helpers.py.
20. **Preserve scroll on same-page reloads** — any `fetch()` POST that, on success, navigates via `window.location.href` to the SAME page must save `window.scrollY` to `sessionStorage` immediately before navigating, then restore with `window.scrollTo` and clear the key on load (read → scrollTo → removeItem, gated on `document.readyState`/`DOMContentLoaded`). Forward navigations to a different page/step are exempt. `render_meal_wizard_step4.py` is the reference. Client-side only; obey Rules 7 & 12.

### Which rules apply to THIS fix
- **Rule 20 (the whole point):** Step 3's `s3Save` does `fetch('/meal-wizard-step3-save')` then on success `window.location.href = '/meal-wizard-step3?saved=1'` — a same-page reload of a long multi-day list. Now governed.
- **Rules 7 & 12:** the JS lives in concatenated string literals inside Python; no raw newline added (smoke test asserts none in the rendered `<script>` block).
- **Rule 9:** py_compile → in-process smoke test → `verify_meal_wizard_step3.py`, all run and pasted below.
- **Rule 17:** single file, single fix — only `render_meal_wizard_step3.py`, nothing else bundled.
- **Rule 15:** read-back above.
- **Not touched:** Rule 5 (no write path changed — pure client-side JS); data shape unchanged.

---

## FIX (one file: `render_meal_wizard_step3.py`, client-side JS only)

Mirrors `render_meal_wizard_step4.py`'s `s4Keep` / `s4RestoreScroll` exactly, with an `s3ScrollY` key.

1. **Save scroll before navigating** — in `window.s3Save`'s success branch, immediately before the redirect:
   ```js
   .then(function(j){ if(j && j.ok){ sessionStorage.setItem('s3ScrollY', String(window.scrollY)); window.location.href = '/meal-wizard-step3?saved=1'; }
   ```

2. **Restore + clear on load** — added just before the IIFE closes:
   ```js
   function s3RestoreScroll(){ var y = sessionStorage.getItem('s3ScrollY'); if(y !== null){ window.scrollTo(0, parseInt(y, 10)); sessionStorage.removeItem('s3ScrollY'); } }
   if(document.readyState === 'loading'){ document.addEventListener('DOMContentLoaded', s3RestoreScroll); } else { s3RestoreScroll(); }
   ```
   Reads `s3ScrollY`, scrolls there, then **removes the key** so it can't leak into unrelated loads. Runs immediately if the DOM is already parsed, else on `DOMContentLoaded`.

3. **Error path untouched** — both "Could not save. Please try again." messages (`.then` else + `.catch`) are unchanged; on failure the page stays put.

---

## Validation results (all pass)

### 1. `py_compile render_meal_wizard_step3.py`
```
py_compile OK
```

### 2. In-process smoke test
```
save scrollY before nav: OK
exactly 1 navigation saves scrollY: OK
restore fn (scrollTo + removeItem): OK
readyState/DOMContentLoaded gate: OK
error path intact (2 messages): OK
no raw newline in rendered JS block: OK
full render contains scroll save + restore: OK

SMOKE OK: save-before-nav wired, restore self-clears, readyState-gated, error path intact, no raw newline
```

### 3. Harness — `verify_meal_wizard_step3.py`
```
PASS complexity persisted
PASS planning_window persisted
PASS prefill keys allowlist-filtered correctly
PASS prefilled meal has correct locked/off-shopping shape
PASS non-prefill (generated) meal preserved across save
PASS prefill entries refreshed (old prefill cleared, new applied)
PASS saved-confirmation view reflects persisted session
PASS Step 2 confirmed_inventory preserved (additive)

PASS all Step 3 session-state checks passed
EXIT=0
```

## Scope confirmation
Only `render_meal_wizard_step3.py` changed. No other fix bundled (Rule 17). Server save logic and data shape unchanged.
