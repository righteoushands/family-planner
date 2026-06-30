# claud.md read-back + DIAGNOSIS — Step 4 slot-action buttons & jump-to-top

## claud.md — all rules (Rule 15 read-back)

### Python 3.11 hard rules (1–12)
1. No backslashes inside f-strings.
2. No nested quotes inside f-strings — use a variable outside the f-string instead.
3. All GET routing uses `elif` chains in `do_GET`; POST routing in `do_POST` ALSO uses `elif` chains (`elif path == "/route-name": … return`). ONE exception: the multipart recipe routes (`/recipe-save`, `/recipe-import`) share an `elif path in (...)` outer block with nested `if` inner blocks ONLY to share upload-parsing setup. Don't copy that for ordinary JSON/form routes. [Corrected June 28 2026: do_POST is elif, not standalone-if.]
4. Never put import statements inside `if` blocks or functions. [Known deviation: several live do_POST handlers use inline `import json as _json`; new code keeps imports at module top.]
5. All file writes use `safe_save_json` (tmp file + `os.replace`) — never `open(f, 'w')` directly.
6. No walrus operator (`:=`).
7. Never use a raw newline inside a JS string within a Python string literal — use the escape sequence so the browser receives `\n`.
8. multipart/form-data parsing: FormData POSTs arrive as multipart, not urlencoded. `do_POST` must sniff Content-Type and use `cgi.FieldStorage` for multipart. Empty data → check Content-Type first.
9. py_compile only validates syntax. After it, run an in-process smoke test, then the relevant `verify_phase_*.py` harness and paste the result. Don't skip the harness for changes touching shared data files, save paths, or multi-caller functions.
10. Test fixtures never write to live data: operate on a temp copy; never call write helpers on live data during testing; restore from backup after.
11. Double-escaping HTML entities: never pass an already-escaped string through `escape()` again.
12. JS newline rule (7) applies to ALL files with JS embedded in Python, not just render_frol_wizard.py.

### Conventions (non-numbered)
Data in `data/*.json`; person keys title-case in progress/chores/events, lowercase in auth/pins & profiles; progress keys `"YYYY-MM-DD::Person::task"`; GET → render_*.py; POST → do_POST elif chains; JSON POST bodies must be registered in `_JSON_PATHS` (LOCAL set inside do_POST ~3536); `<a href>` can't POST/mutate — state travels in query string or is pre-persisted, else use `<form method="POST">`. FROL form bypass trap: `_section_chrome._body_has_form` suppresses Save-and-Continue when it sees `action="/frol-wizard"`.

### Additional rules (13–19)
13. FROL nested-form addendum — confirm section-body form actions aren't `/frol-wizard`; document before fixing.
14. Pre-flight checklist — file count/list; JS-in-f-strings (flag backslash-n); form handling (no nested /frol-wizard forms); root cause confirmed vs assumed (diagnose first if assumed); multiple files → split; data-shape change → confirm before/after.
15. claud.md read-back required at start of every session.
16. Magnifica Humanitas — tool not authority; suggestions not prescriptions; companions serve real relationships; AI supports not replaces thinking; transparency; grace not performance (no gamification/streaks/shaming); subsidiarity (Lauren is authority); formation in digital wisdom.
17. One fix per instruction — no bundling unless same file & directly related; multi-file builds split into phases with compile+report between each.
18. August 15th build plan is the priority filter (June 1–Aug 15 2026); flag off-plan requests; cut scope first not quality.
19. Build for a future second family — no hardcoded single-family specifics (config in app_settings.json); all data IO through data_helpers.py, no direct file access in handlers. [Known debt: build_lorenzo_context hardcodes the roster.]

### Which rules apply to THIS task (diagnosis only)
- **Govern this task:** Rule 14 (pre-flight: 1 render file + its app.py handlers), Rule 15 (read-back, done).
- **Relevant to the eventual fix:** Rule 7 & 12 (the button JS is Python string literals), Rule 2 (onclick built outside f-strings), Rule 5 (confirm/remove/lock are write paths), Rule 9 & 10 (smoke + harness), Rule 17 (single-purpose fix), Rule 19 (handlers via data_helpers).
- **Not applicable:** Rule 13 (no FROL form), Rule 8 (these are JSON POSTs, though `_JSON_PATHS` registration matters), Rule 18 (bug fix on existing must-have, not a new feature).

---

## DIAGNOSIS — root cause of the jump-to-top

**Headline:** Every meal-slot action button uses `fetch()` → on success → `window.location.href = '/meal-wizard-step4'` (a **full page navigation**, not a partial DOM update). Scroll position is **never** captured before or restored after — no `scrollY`, `pageYOffset`, `scrollTo`, `scrollIntoView`, or `sessionStorage` exists anywhere in the file. **This is the confirmed root cause of the jump-to-top.**

### Every button with this pattern

| # | Button | JS handler (line) | Action | POST route | On success | Scroll saved/restored? |
|---|---|---|---|---|---|---|
| 1 | **Keep this meal** (empty slot) | `s4Keep` (219–224) | Confirm a meal | `/meal-wizard-step4-confirm` | `window.location.href` (222) | **No** |
| 2 | **Change** (confirmed, non-prefill) | `s4Change` (226–237) | Remove the meal (Change = remove) | `/meal-wizard-step4-remove` | `window.location.href` (234) | **No** |
| 3 | **Set this plan** (page-level) | `s4Lock` (238–247) | Lock the whole plan | `/meal-wizard-step4-lock` | `window.location.href` (244) | **No** |
| 4 | **Generate my week with Lorenzo** (page-level) | `s4Generate` (248–262) | Generate drafts | `/meal-wizard-generate` | `window.location.href` (257, only if `ok && generated>0`) | **No** |

### Answers
1. **Reload vs partial update:** All four are `fetch()` POSTs, but none do a partial DOM update on success — each triggers a **full page reload** via `window.location.href = '/meal-wizard-step4'`. The fetch only sends the mutation and checks `j.ok`. The only partial-DOM behavior is the *error* path, which writes into the slot's `s4-msg--<key>` div and stays put; success always navigates.
2. **Scroll capture/restore:** **No.** No capture before the navigation, no restore after load. Navigating to the same URL resets the browser to the top. **Confirmed root cause.**
3. **Full list (not one example):** All four — the two per-slot buttons (**Keep this meal**, **Change**) plus the two page-level buttons (**Set this plan**, **Generate my week with Lorenzo**). Identical anti-pattern, no scroll preservation. Every list day renders Keep (empty) or Change (confirmed), so the jump appears on multiple buttons across multiple days — matching what Lauren reports.

### Terminology note
There is no separate "Remove" button — **"Change" IS the remove** (`s4Change` → `/meal-wizard-step4-remove`; code comment line 273: "Change = remove for now"). Prefill/past meals (line 332) render locked with **no** button and are unaffected.

No code changed. No fix proposed yet — per Rule 17 the eventual fix would be a single-purpose change to this one file's JS (capture scroll before navigation, restore on load).
