# Meal Wizard — Phase G1 LOCK BUILD REPORT ("Set this plan")

**Date:** June 28, 2026 · Single capability per Rule 17 · runs after the Lock Step Diagnosis (complete)

> Adds the final wizard step: a **"Set this plan"** action that writes every confirmed Step 4 meal into the **canonical meal store** (`data/meal_plan/<Monday>.json`) so the meals show up on the homepage meal cards. The wizard session is **KEPT (revisitable), not cleared** — Lauren can re-open the wizard and the confirmed meals are still there, now marked locked. **No Lorenzo, no shopping-list generation, no Step 3→4 nav rework — those are out of scope.**

---

## RULE 15 — CLAUD.MD READ-BACK

### Stack / People (context)
- Python 3.11, no framework, raw `http.server` `do_GET`/`do_POST`, JSON files in `data/`, no DB, frontend = HTML/CSS/JS rendered as Python strings, Anthropic via `urllib.request`.
- People: Lauren/Mom, John, JP (14), Joseph (12), Michael (5), James (13 mo — never assignable). Title-case in display; Mom and Lauren are the same person.

### Python 3.11 hard rules
1. No backslashes inside f-strings.
2. No nested quotes inside f-strings — pull the value into a variable first.
3. GET routing uses `elif` chains in `do_GET`; POST routing **also** uses `elif` chains in `do_POST`. Do not refactor routing structure.
4. Imports at module top — never inside if-blocks or functions.
5. All file writes go through `safe_save_json` (tmp + `os.replace`) — never `open(f,'w')` directly.
6. No walrus operator.
7. No literal backslash-n inside a JS string embedded in a Python string literal.
8. multipart/form-data parsed with `cgi.FieldStorage`. *(N/A — this is a JSON `fetch` POST.)*
9. `py_compile` passing ≠ runtime correct — run an in-process smoke test AND the nearest `verify_*` harness for shared data/save-path changes.
10. Test fixtures never touch live data — temp copy, snapshot + restore.
11. Escape HTML once.
12. The JS-newline rule (7) applies to every file embedding JS in Python.

### Data / routes / nav / AI / change discipline
- Data in `data/*.json`; `data_helpers.py` is the only JSON reader/writer; `config.py` owns paths.
- GET → `render_*.py` returning HTML; POST chained as `elif path == "/route"`. **JSON POST bodies must be in `_JSON_PATHS`** (a LOCAL set inside `do_POST`).
- Plain `<a href>` cannot POST/mutate state.
- All changes additive; never delete/modify existing behavior unless required; modules under ~800 lines.
- Family Quest isolation: `family_quest/` is decoupled — not touched here.

### Additional rules 13–19
13. FROL nested-form addendum — N/A (no forms; a button + `fetch` only).
14. Pre-flight checklist (below).
15. This read-back.
16. Magnifica Humanitas — tool not authority; Lauren is the authority. The lock is **Lauren's explicit action** ("Set this plan"), never an automatic assumption; no streaks/scores/shame.
17. One fix per instruction — single capability: write confirmed meals into the canonical store.
18. Aug-15 build plan is the priority filter — the Meal Wizard is on the must-build path.
19. Build for a future second family — no hardcoded family specifics; reads/writes via the data layer.

### Rules that APPLY to G1 LOCK
- **Rules 1 & 2** — the new banner/button markup keeps f-string discipline; no nested quotes inside f-string expressions (style strings are pulled into constants).
- **Rules 7 & 12** — **THIS STEP ADDS JS** (`window.s4Lock`). Built as **concatenated string literals**, **no backslash-n in any JS string** (verified below).
- **Rule 4** — the new `apply_confirmed_meals_to_store` import was added to the existing top-of-file `from render_meals import (...)` block; no inline imports added.
- **Rule 5** — the store write goes through the existing `save_meal_plan` → `safe_save_json`; the session write goes through `update_meal_wizard_session`. No new write path.
- **Rule 6** — no walrus.
- **Rule 11** — meal names are escaped once on render (homepage + Step 4 already do this); the lock route echoes no user data.
- **Rule 16** — the button reads as Lauren's choice — **"Set this plan"** — and the post-lock banner is informational ("Your plan is set"); the wizard stays editable, the app assumes nothing.
- **Rule 17** — one capability: persist confirmed meals to the canonical store.
- **Route patterns** — **one** new POST route `/meal-wizard-step4-lock` added as an `elif` branch, and added to the LOCAL `_JSON_PATHS` set (JSON body). Routing structure unchanged.
- **Rule 10** — the harness snapshots + restores every meal_plan week file it touches AND the live session file, and destroys the minted token.
- **Rule 19** — slot mapping and store shape are generic; no family specifics.
- Confirmed: **NO `<form>` elements** added (Rule 13) — a button + `fetch` only.

---

## PRE-FLIGHT (Rule 14)
1. **Files touched (3):** `render_meals.py` (the store-write helper + slot map), `app.py` (one import + one `_JSON_PATHS` entry + one `elif` route), `render_meal_wizard_step4.py` (banner + button + `window.s4Lock`). One capability.
2. **JS in Python f-strings?** **YES** — `window.s4Lock` added to `_S4_JS`. Built as concatenated string literals; Rules 7/12 honored (no backslash-n in any JS string).
3. **Form handling / nested `/frol-wizard` forms?** NO forms — a button + `fetch` only.
4. **Root cause confirmed?** Yes — the Lock Step Diagnosis established that the canonical store is `data/meal_plan/<Monday>.json`, the homepage card gates only on non-empty slot text (not on `generated`/any lock flag), and there is no plan-level "locked" flag. This build writes into that exact store.
5. **Multiple files?** Three, directly related (the helper, its route, its button).
6. **Data shape change?** NO new store shape — writes into the existing `days[Weekday][slot]` shape. Adds one session key, `plan_locked_at` (a date string), which is additive.

---

## KEY DECISIONS (baked in)
- **Wizard-slot → store-slot mapping.** The wizard uses richer slot names than the store. The map `_WIZARD_TO_STORE_SLOT` resolves them:
  - `breakfast/lunch/dinner/dessert/snacks` → same-named store slot (1:1).
  - `johns_lunch` → **`dad_lunch`** (the store's name for John's packed lunch).
  - `feast_meal`, `batch_cook` → **no store home → skipped** (they are planning aids, not homepage meal-card slots).
- **Prefill meals are skipped.** Entries with `source == "prefill"` are *existing* past meals already in the store — re-writing them would be redundant and could clobber. The lock writes only the meals Lauren actively confirmed.
- **Additive, per-slot write.** For each confirmed meal the helper writes **only** that `days[Weekday][slot]` cell. Other slots on the same day, other days, and the file's `generated` flag are left exactly as they were. A plan that spans two calendar weeks is split by Monday and written to **both** week files.
- **`generated` is left untouched.** The homepage card already shows any non-empty slot regardless of `generated`, so the lock does not need (and must not) flip it.
- **Session is KEPT, not cleared.** The lock sets `plan_locked_at` (today's ISO date) on the wizard session and leaves `confirmed_meals` in place, so the wizard is **revisitable** — Lauren can re-open Step 4, see the banner, and keep editing. (There is no plan-level lock flag in the store, by design — the diagnosis confirmed none exists.)
- **No "locked" gate on display.** Because the homepage already keys off slot text, simply writing the meal makes it appear — no extra flag needed.

---

## WHAT WAS BUILT

### STEP 1 — `render_meals.py`: the store-write helper
Added right after `save_meal_plan`:
- `_WIZARD_TO_STORE_SLOT` — the slot map above. Slots not present in the map (`feast_meal`, `batch_cook`) have no store home and are skipped.
- `apply_confirmed_meals_to_store(confirmed_meals)` — iterates the wizard session's `confirmed_meals` (`"<date_iso>::<slot>"` → entry):
  - skips `source == "prefill"` entries and slots with no store home;
  - groups the rest by their **Monday-week**;
  - for each week, loads the existing store file (or a fresh skeleton), writes each meal **additively** into `days[Weekday][store_slot]`, leaves `generated` and untouched slots alone, and saves via `save_meal_plan` (→ `safe_save_json`);
  - returns a summary `{"weeks_written": [...], "slots_written": N, "skipped": [...]}`.

All imports stay at module top (Rule 4); no walrus (Rule 6); the write goes through the existing `safe_save_json` path (Rule 5).

### STEP 2 — `app.py`: the lock route
- Added `apply_confirmed_meals_to_store` to the existing top-of-file `from render_meals import (...)` block.
- Added `/meal-wizard-step4-lock` to the LOCAL `_JSON_PATHS` set inside `do_POST` (JSON body).
- Added the route as an `elif path == "/meal-wizard-step4-lock":` branch (routing structure unchanged, Rule 3). It reads/discards the request body, loads `confirmed_meals` from the wizard session, calls the helper, sets `plan_locked_at` = today's ISO date on the session via `update_meal_wizard_session` (**does NOT clear the session**), and returns `json {"ok": true, **summary}`. Behind the existing POST-auth gate.

### STEP 3 — `render_meal_wizard_step4.py`: banner + button + JS
- Added banner/lock style constants and `_S4_LOCKABLE_SLOTS` (the set of wizard slots that have a store home — used to decide whether a "Set this plan" action is meaningful).
- Added `window.s4Lock` to `_S4_JS` (concatenated string literals, **no backslash-n**): POSTs `{}` to `/meal-wizard-step4-lock`; on `{ok:true}` reloads `/meal-wizard-step4` (so the banner appears), else shows an inline message.
- The render function computes `locked_at` (from the session) and `has_lockable` (any confirmed meal in a lockable slot), then inserts between the day cards and the nav:
  - a **banner** — *"Your plan is set — showing on your homepage for this week."* — when `plan_locked_at` is set;
  - the **"Set this plan"** button (with an inline message `<div id="s4-lock-msg">`) when there is at least one lockable confirmed meal, **or** a muted hint *"Confirm at least one meal to set your plan"* when there is not.
- All prior Step 4 behavior (entry/Change/prefill display, the G1b-2a write loop, the back link) is preserved. The wizard stays editable after locking.

---

## EXPLICITLY OUT OF SCOPE FOR G1 LOCK (not built)
- No shopping-list generation, no Lorenzo, no recipe-attach.
- No plan-level "locked" flag in the store (none exists, and the homepage doesn't need one).
- No clearing/reset of the wizard session (it stays revisitable, by design).
- No Step 3→4 navigation rework.
- No `feast_meal` / `batch_cook` store destination (they have no homepage home).

---

## VALIDATION RESULTS (Rules 9 / 10) — THE ROUND-TRIP WAS RUN

**1. `py_compile render_meals.py app.py render_meal_wizard_step4.py`** → **COMPILE OK.**

**2 + 3. AUTHENTICATED HTTP ROUND-TRIP + UNIT** (`data/verify_meal_wizard_step4_lock.py`) — a unit test of the pure helper plus an authenticated round-trip that mints a real Lauren session and POSTs the live `/meal-wizard-step4-lock`, then reads the live week files and session back. Snapshots + restores **every** meal_plan week file it touches AND the live session file, and destroys the minted token (Rule 10). The dates cross a Monday so two week files are exercised:
```
PASS UNIT: cross-Monday wrote exactly two week files
PASS UNIT: slots_written counts only real writes (3)
PASS UNIT: feast_meal skipped (no store home)
PASS UNIT: johns_lunch landed in store slot dad_lunch
PASS UNIT: prefill meal was NOT written to the store
PASS lock POST returns 200 {ok:true}
PASS lock wrote both week files (cross-Monday)
PASS this-week dinner persisted to days[Weekday][dinner]
PASS next-week dinner persisted (second file)
PASS johns_lunch -> dad_lunch in the store
PASS pre-existing UNRELATED slot still present (additive)
PASS 'generated' left unchanged (still False)
PASS feast_meal NOT written to either store file
PASS prefill meal NOT written to the store
PASS session STILL has confirmed_meals (not cleared)
PASS session now has plan_locked_at
PASS homepage meals card shows the locked meal (block=afternoon)
PASS Step 4 shows the 'Your plan is set' banner
PASS Step 4 keeps the meals editable (Set this plan still present)

PASS all G1 lock checks passed
```
This satisfies the required round-trip exactly: a confirmed plan spanning two calendar weeks is locked via the live route → both `data/meal_plan/<Monday>.json` files gain the right meals at the right `days[Weekday][slot]` cells, `johns_lunch` maps to `dad_lunch`, `feast_meal` and prefill entries are skipped, a pre-existing unrelated slot survives (additive), `generated` is unchanged, the **session is NOT cleared** and gains `plan_locked_at`, the **homepage** meal card shows the locked meal, and **Step 4 shows the banner and stays editable**.

**4. Regression harnesses:**
```
verify_meal_wizard_step3.py  -> PASS all Step 3 session-state checks passed
verify_meal_wizard_step4.py  -> PASS all G1b-1 read-only screen checks passed
```
Both pass untouched — the lock work is purely additive to Step 3 and the Step 4 screen.

**5. Report items:**
- Rules applied: 1, 2, 4, 5, 6, 7, 11, 12, 16, 17, 14, 19, Route patterns, Rule 10. Rules 8 & 13 did NOT apply (no multipart, no forms).
- **JS built as concatenated literals — confirmed; no backslash-n in any JS string.**
- **One route added** (`/meal-wizard-step4-lock`) and added to `_JSON_PATHS`; routing structure unchanged.

---

## CODE REVIEW (architect) — PASS
The architect reviewed the diff and returned **PASS — no severe/blocking issues.** It confirmed: the core write path is correct (slot mapping `johns_lunch → dad_lunch`, `feast_meal`/`batch_cook`/prefill skipped, per-Monday grouping, additive `days[Weekday][slot]` writes); additive/no-clobber behavior is correct and `generated` is untouched; route integration is correct (top-level import, `_JSON_PATHS` entry, `elif` branch, session **not** cleared, JSON summary returned); the UI is correct for a revisitable lock (banner + "Set this plan", stays editable); and the validation evidence (py_compile, 19/19 authenticated round-trip + unit, both regressions) is strong and task-aligned. Security: none observed — the endpoint sits behind the existing POST-auth gate. The one non-blocking suggestion (centralize meal-plan path constants into `config.py`) is deferred: the meal slot/path constants already live in `render_meals.py` by existing convention, and moving them is out of this single-capability scope.

---

## SUMMARY
Phase **G1 LOCK is complete**: Step 4 now has a working **"Set this plan"** action that writes Lauren's confirmed wizard meals into the canonical meal store, so they appear on the homepage meal cards. The write is **additive** (no unrelated slots or `generated` clobbered), maps `johns_lunch → dad_lunch`, **skips** `feast_meal`/`batch_cook`/prefill entries, and splits a multi-week plan across the right `data/meal_plan/<Monday>.json` files. The wizard **session is kept revisitable** and marked `plan_locked_at`, and Step 4 shows a "Your plan is set" banner while staying editable. The JS is concatenated string literals with no backslash-n, one route was added and registered in `_JSON_PATHS`, and routing structure is unchanged. All validation passes — the authenticated HTTP round-trip (19/19), both regressions, and the architect review. **Stopping here.**
