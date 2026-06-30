# claud.md read-back + FIX — Step 4 scroll preservation

## claud.md — all rules (Rule 15 read-back)

### Python 3.11 hard rules (1–12)
1. No backslashes inside f-strings.
2. No nested quotes inside f-strings — use a variable outside the f-string.
3. GET routing uses `elif` chains in `do_GET`; POST routing in `do_POST` ALSO uses `elif` chains. ONE exception: multipart recipe routes (`/recipe-save`, `/recipe-import`) share an `elif path in (...)` outer block with nested `if` inner blocks for upload-parsing setup only. [Corrected June 28 2026.]
4. Never put imports inside `if` blocks or functions. [Known deviation: some do_POST handlers use inline imports; new code keeps imports at module top.]
5. All file writes use `safe_save_json` (tmp + `os.replace`) — never `open(f, 'w')`.
6. No walrus operator (`:=`).
7. Never use a raw newline inside a JS string within a Python string literal — use the escape sequence.
8. multipart/form-data: FormData POSTs arrive as multipart; sniff Content-Type and use `cgi.FieldStorage`. Empty data → check Content-Type first.
9. py_compile is syntax-only; after it run an in-process smoke test, then the relevant `verify_phase_*.py` harness and paste the result. Don't skip the harness for shared data files, save paths, or multi-caller functions.
10. Test fixtures never write to live data; use a temp copy; restore from backup after.
11. Never double-escape HTML entities.
12. JS newline rule (7) applies to ALL files with JS embedded in Python.

### Conventions
Data in `data/*.json`; person keys title-case in progress/chores/events, lowercase in auth/pins & profiles; progress keys `"YYYY-MM-DD::Person::task"`; GET → render_*.py; POST → do_POST elif; JSON POST bodies registered in `_JSON_PATHS` (LOCAL set in do_POST ~3536); `<a href>` can't POST/mutate. FROL form bypass trap: `_body_has_form` suppresses Save-and-Continue on `action="/frol-wizard"`.

### Additional rules (13–19)
13. FROL nested-form addendum — confirm section-body form actions aren't `/frol-wizard`.
14. Pre-flight checklist — file count/list; JS-in-f-strings (flag backslash-n); form handling; confirmed vs assumed root cause; multi-file → split; data-shape change → confirm.
15. claud.md read-back required at session start.
16. Magnifica Humanitas — tool not authority; suggestions not prescriptions; companions serve real relationships; AI supports not replaces thinking; transparency; grace not performance; subsidiarity; formation in digital wisdom.
17. One fix per instruction.
18. August 15th build plan is the priority filter (June 1–Aug 15 2026).
19. Build for a future second family — config in app_settings.json; data IO through data_helpers.py.

### Which rules apply to THIS fix
- **Directly governed:** Rule 7 & 12 (the change adds JS inside a Python string literal — no raw newline used, confirmed by smoke test), Rule 2 (the JS block is concatenated string literals, not an f-string, so no nested-quote conflict), Rule 9 (py_compile + smoke test + the two harnesses, all run below), Rule 14 (pre-flight: one file, JS-in-Python flagged, root cause already confirmed in prior diagnosis), Rule 15 (read-back), Rule 17 (single-purpose, no bundling).
- **Not touched:** Rule 5 (no write path changed — pure client-side JS), Rule 13/8/18, data-shape unchanged.

---

## FIX (one file: `render_meal_wizard_step4.py`, client-side JS only)

1. **Scroll saved before each navigation.** All four success-path navigations (`s4Keep`, `s4Change`, `s4Lock`, `s4Generate`) now run `sessionStorage.setItem('s4ScrollY', String(window.scrollY));` immediately before `window.location.href = '/meal-wizard-step4';`, in the same statement.

2. **Restore on load, self-clearing.** Added to the existing IIFE:
   ```js
   function s4RestoreScroll(){ var y = sessionStorage.getItem('s4ScrollY'); if(y !== null){ window.scrollTo(0, parseInt(y, 10)); sessionStorage.removeItem('s4ScrollY'); } }
   if(document.readyState === 'loading'){ document.addEventListener('DOMContentLoaded', s4RestoreScroll); } else { s4RestoreScroll(); }
   ```
   It reads `s4ScrollY`, scrolls there, then **removes the key** so it can't leak into unrelated page loads or persist if Lauren navigates away and back without clicking a button. The `readyState` guard runs it immediately if the DOM is already parsed, else on `DOMContentLoaded`.

3. **Rule 7/12 respected** — no raw newline inside the JS (verified by the smoke test asserting `"\n" not in _S4_JS`).

4. **Error path untouched** — the `s4-msg--<key>` / `s4-gen-msg` / `s4-lock-msg` failure messages are unchanged; on failure the page stays put exactly as before.

---

## Validation results (all pass)

### 1. `py_compile render_meal_wizard_step4.py`
```
py_compile OK
```

### 2. In-process smoke test
```
no raw newline in JS: OK
all 4 navigations save scrollY first: OK
restore-on-load + removeItem + readyState guard: OK
error paths intact: OK
full render contains scroll logic + expected button state: OK

SMOKE OK: 4 saves wired, restore self-clears, error paths intact, no raw newline
```
- Exactly 4 navigations and 4 scroll-saves; each navigation has the save immediately before it.
- Restore function present with `scrollTo`, `removeItem`, and the `readyState`/`DOMContentLoaded` guard.
- All four error-path messages still present.

### 3. Harnesses
```
verify_meal_wizard_step4.py      → PASS all G1b-1 read-only screen checks passed  (exit 0)
verify_meal_wizard_step4_lock.py → PASS all G1 lock checks passed                 (exit 0)
```

## Scope confirmation
Only `render_meal_wizard_step4.py` changed. No other fix bundled (Rule 17).
