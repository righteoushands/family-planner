# claud.md read-back + DIAGNOSIS — scroll-loss anti-pattern sweep

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

### Additional rules (13–19)
13. FROL nested-form addendum — confirm section-body form actions aren't `/frol-wizard`.
14. Pre-flight checklist — file count/list; JS-in-f-strings; form handling; confirmed vs assumed root cause; multi-file → split; data-shape change → confirm.
15. claud.md read-back required at session start.
16. Magnifica Humanitas — tool not authority; suggestions not prescriptions; AI supports not replaces thinking; transparency; subsidiarity.
17. One fix per instruction.
18. August 15th build plan is the priority filter (June 1–Aug 15 2026).
19. Build for a future second family — config in app_settings.json; data IO through data_helpers.py.

### Which rules apply to THIS task
- **Rule 15** (read-back, done above) and **Rule 14** (pre-flight: I list every file checked below).
- **DIAGNOSIS ONLY** — no code changed, so Rules 5/7/9/17 (write/JS/test/one-fix) are not exercised this turn. They will govern any future fix.

---

## Key technical distinction (determines whether a fix is even needed)

The Step 4 anti-pattern was specifically **`window.location.href = <same URL>`** after a `fetch()` POST. A same-URL assignment to `location.href` is treated by the browser as a **navigation**, which **scrolls to the top** — that is the jump Lauren saw.

By contrast, **`location.reload()`** is a *reload*, and modern browsers **preserve and restore the scroll position** across a reload (via history scroll restoration). So `reload()` callers usually do **not** exhibit the jump-to-top symptom. I've split the findings accordingly: **TRUE MATCH** = the exact `href`-to-same-page pattern; **RELOAD VARIANT** = full reload of a list page (milder, scroll usually retained, but still a full server round-trip with no explicit scroll handling).

---

## Files checked (complete list — 13 render modules + 1 JS file)

`render_meal_wizard_step3.py`, `render_meal_wizard.py` (Step 1 week-glance, Step 2, pantry-staples), `render_prayer.py`, `render_misc.py`, `render_schedule.py`, `render_virtues.py`, `render_assignment_analyzer.py`, `render_settings.py`, `render_dev.py`, `render_gradebook.py`, `render_student.py`, `render_friends.py`, and `static/inventory_input.js` (Step 2's save logic).

---

## TRUE MATCHES — fetch → `window.location.href` to the SAME page, no scroll save/restore

### 1. `render_meal_wizard_step3.py` — YES
- **Save & continue** — handler `window.s3Save` (def line 163), POST `/meal-wizard-step3-save` (line 175), on success `window.location.href = '/meal-wizard-step3?saved=1'` (line 178).
- Same page (Step 3), which is a long multi-day prefill/meal-type list. No `scrollY`/`scrollTo` anywhere in the file. **Exact sibling of the Step 4 pattern.** (One Save button rather than per-item buttons, but the page is fully scrollable.)

### 2. `render_prayer.py` — YES (page: `/prayer-intentions`, multi-item list)
- **Remove intention** — `deleteIntention(iid)` (line 806), POST `/prayer-intention-delete` (808), on success `window.location.href = '/prayer-intentions'` (813; the `.catch` also navigates at 815).
- **Add intention (modal submit)** — `submitAddIntention()` (line 773), POST `/prayer-intention-add` (793), on success `window.location.href = '/prayer-intentions'` (799). Lands back on the same scrollable list.
- No scroll save/restore in the file.

---

## RELOAD VARIANTS — fetch → `location.reload()` of a same list page (milder; browser usually keeps scroll; no explicit scroll handling)

### 3. `render_prayer.py` — `markAnswered(iid, answered)` (line 763), POST `/prayer-intention-complete` (764), on success `closeModal(); location.reload()` (769).

### 4. `render_misc.py` — Tasks page ("Active Tasks" multi-item list) + Mom dashboard
- `_taskAction(btn, url, taskId)` (line 5331), fetch `url` (5336), on success `setTimeout(window.location.reload, 200)` (5342); `.catch` reload (5346).
- `_taskEditSave(taskId, btn)` (line 5354), POST `/task-update` (5382), on success `window.location.reload()` (5388); `.catch` reload (5391).
- `taskEditSaveStep` / `taskEditDoneStep` (4238 / 4253) → `_stepRefreshTasks()` (4213): **prefers** a partial DOM refresh `window._momStepReload('tasks')` and only falls back to `window.location.reload()` (4215). Mostly-correct already.

### 5. `render_schedule.py` — Today / Day List (multi-item task list)
- `_tovPost(params, cb)` (line 2072), POST `/task-override` (2073), default callback `location.reload()` (2074); driven by `_tovAct` / `_tovActTime` / `_tovClear`.
- Schedule modal actions (2139 / 2149 / 2159) → `_schedClose(); location.reload()`.
- Task edit save → POST `/task-update`, on success `location.reload()` (2238).
- **Note (correct pattern, not a match):** the checkbox toggles `toggleDashTask` (1953) / `_showUndoSnack` revert (1946) / `toggle-task` (1973) do **optimistic partial DOM updates** + `_dashUpdateProgress` — no reload.

---

## NOT the anti-pattern (and why)

### 6. `render_meal_wizard.py` (Step 1 week-glance, Step 2, pantry-staples) — NO
- File has **no** `fetch → same-page href`. Step 2's Save (`saveInventoryWizard`, in `static/inventory_input.js` line 192) does fetch `/meal-wizard-step2-save` (203) then `window.location.href = "/meal-wizard-step3"` (211) — a **forward** navigation to a *different* page in the wizard flow, where jumping to the top is correct.
- Pantry-staples uses `<form method="POST" action="/pantry-staples-save">` (156 / 231) — a full-page **server-redirect** form, not a fetch.
- Week-glance does one read-only merged fetch (429) for display; no mutation, no nav.

### 7. `render_virtues.py` — NO
- `saveCheckin(who)` (743) and `aiSuggestVirtue(who)` (759) already do **partial DOM updates** (status text / `innerHTML`); neither reloads.
- The `window.location.href` calls at 732 / 859 / 1023 are `<select>` `onchange` handlers that navigate to a **different** virtue view (`?virtue=…`) — intentional navigation, not a same-page reload.

### 8. `render_student.py` — NO
- Has `fetch()` but **no** `window.location.href` / `location.reload` to the same page (updates happen in place).

### 9. `render_assignment_analyzer.py` — NO (not a list)
- `window.location.reload()` at 544 / 548 follows an upload/analysis action on a single-flow page, not a multi-item list with per-item buttons.

### 10. `render_settings.py` — NO (not a scrollable item list)
- `location.reload()` at 911 is on the form-driven settings page; not a per-item list.

### 11. `render_dev.py` — NO (not a list)
- `window.location.reload()` at 1341 is a delayed dev-tools refresh.

### 12. `render_gradebook.py` — RELOAD VARIANT / borderline
- `window.location.reload()` at 365 / 419 after fetch. If the gradebook view is a long scrollable list this is a mild reload variant; it uses `reload()` (scroll usually preserved), not `href`-to-same-page, so it is **not** the exact Step-4 jump.

### 13. `render_friends.py` — RELOAD VARIANT / borderline
- `window.location.reload()` at 563 after fetch. Same note as gradebook: `reload()` variant, not the `href` jump.

---

## Summary

| File | Verdict | Mechanism |
|---|---|---|
| render_meal_wizard_step3.py | **TRUE MATCH** | `href` → same page (1 action) |
| render_prayer.py | **TRUE MATCH** (+1 reload variant) | `href` → same page (delete, add); `reload()` (markAnswered) |
| render_misc.py | reload variant | `location.reload()` (tasks list; mom-step prefers partial) |
| render_schedule.py | reload variant | `location.reload()` (overrides/modal/edit); toggles already partial |
| render_gradebook.py | reload variant (borderline) | `location.reload()` |
| render_friends.py | reload variant (borderline) | `location.reload()` |
| render_meal_wizard.py (Steps 1/2/pantry) | NO | forward nav / server-redirect form / read-only |
| render_virtues.py | NO | partial DOM updates; selects navigate to other views |
| render_student.py | NO | in-place updates |
| render_assignment_analyzer.py | NO | reload on single-flow upload page |
| render_settings.py | NO | reload on form page |
| render_dev.py | NO | delayed dev refresh |

**Exact siblings of the Step-4 bug (would visibly jump to top): `render_meal_wizard_step3.py` and `render_prayer.py` (delete + add intention).** The `location.reload()` callers in misc/schedule/gradebook/friends are full reloads of list pages but typically retain scroll, so they're a lower-severity class.

No code was changed (diagnosis only, per instruction).
