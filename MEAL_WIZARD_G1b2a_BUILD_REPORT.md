# Meal Wizard — Phase G1b-2a BUILD REPORT (manual write loop + server guard)

**Date:** June 28, 2026 · Single capability per Rule 17 · **First JavaScript in Step 4** · runs after G1b-1 (complete)

> Makes the read-only Step 4 screen INTERACTIVE for manual planning: each empty, non-prefill slot gets an entry affordance (meal name + optional ingredients + optional main protein) and a **"Keep this meal"** button that confirms it into the wizard session; each confirmed non-prefill meal gets a **"Change"** button that removes it so Lauren can re-enter. Plus a one-line server guard so a meal can never persist half-confirmed. **GREEN/RED ingredient checks and the RECIPE-ATTACH link were NOT built — they are G1b-2b.**

---

## RULE 15 — CLAUD.MD READ-BACK

### Stack / People (context)
- Python 3.11, no framework, raw `http.server` `do_GET`/`do_POST`, JSON files in `data/`, no DB, frontend = HTML/CSS/JS rendered as Python strings, Anthropic via `urllib.request`.
- People: Lauren/Mom, John, JP (14), Joseph (12), Michael (5), James (13 mo — never assignable, excluded from school renderers). Always title-case; Mom and Lauren are the same person.

### Python 3.11 hard rules
1. No backslashes inside f-strings.
2. No nested quotes inside f-strings — pull the value into a variable outside the f-string.
3. GET routing uses `elif` chains in `do_GET`; POST routing **also** uses `elif` chains in `do_POST` (`elif path == "/route": … return`). The ONE exception is the multipart recipe routes' shared-setup nested block — do not copy it. *(Corrected June 28; code wins.)*
4. Never put imports inside if-blocks or functions — all imports at module top. *(Known live deviation: some `do_POST` handlers use inline `import json as _json`; new code keeps imports at top — this work added none.)*
5. All file writes go through `safe_save_json` (tmp + `os.replace`) — never `open(f,'w')` directly. *(Honored transitively: writes go through `update_meal_wizard_session`.)*
6. No walrus operator.
7. Never put a literal backslash-n inside a JS string within a Python string literal — use the escaped form so the browser receives the escape sequence, not a raw newline.
8. multipart/form-data: sniff Content-Type, parse with `cgi.FieldStorage`. *(N/A — these are JSON `fetch` POSTs.)*
9. `py_compile` passing ≠ runtime correct — run an in-process smoke test AND the nearest existing `verify_*` harness; don't skip the harness for changes touching shared data/save paths or multi-caller functions.
10. Test fixtures never touch live data — temp copy, snapshot + restore.
11. Escape HTML once (no double-escaping).
12. The JS-newline rule (7) applies to every file embedding JS in Python.

### Data / routes / nav / AI / change discipline
- Data in `data/*.json`; person keys title-case in progress/chores/events, lowercase in `auth/pins.json` and `profiles/`; compound progress keys `YYYY-MM-DD::Person::task`.
- GET → `render_*.py` returning HTML; POST chained as `elif path == "/route"`. **JSON POST bodies must be in `_JSON_PATHS`** (a LOCAL set inside `do_POST`, ~app.py 3547).
- Plain `<a href>` cannot POST/mutate state.
- AI model not uniform; Lorenzo uses `claude-haiku-4-5-20251001`; `_repair_and_parse_json` is plan-importer-only. *(Not exercised by G1b-2a — no AI here.)*
- All changes additive; never delete/modify existing behavior unless required; flag out-of-scope file edits; modules under ~800 lines.
- FROL form-bypass trap: `_section_chrome`/`_body_has_form` suppress Save&Continue when a body form posts to `/frol-wizard`. *(N/A — no forms here.)*

### Additional rules 13–19
13. FROL nested-form addendum — N/A (no forms; buttons + `fetch` only).
14. Pre-flight checklist (below).
15. This read-back.
16. Magnifica Humanitas — tool not authority; suggestion never prescription; language of grace, no gamification/streaks/scores/shame; Lauren is the authority and the app never quietly assumes a decision that belongs to her.
17. One fix per instruction — single capability: the manual write loop (+ its server guard, same flow, directly related).
18. Aug-15 build plan is the priority filter — the Meal Wizard is on the must-build path.
19. Build for a future second family — read/write via `data_helpers`; no hardcoded family specifics in this screen.

### Rules that APPLY to G1b-2a
- **Rules 1 & 2** — the new render markup keeps f-string discipline; the `onclick` value is pulled into a variable (`keep_call`/`change_call`) to avoid nested quotes.
- **Rules 7 & 12** — **THIS STEP HAS JS.** `_S4_JS` is built as **concatenated string literals** (like step3's `s3Save`), and contains **no backslash-n inside any JS string** (verified below).
- **Rule 5** — the confirm/remove handlers write only through `update_meal_wizard_session`; the guard mutates the in-memory entry before that single write. No new write path.
- **Rule 6** — no walrus.
- **Rule 11** — every dynamic display value (meal name, recipe label, source tag) escaped exactly once; the inputs are empty placeholders (no echo of user data).
- **Rule 16** — buttons read as Lauren's choices: **"Keep this meal" / "Change"**; no streaks, scores, or prescriptions; the server auto-sets the no-recipe default rather than nagging.
- **Rule 17** — one capability: the manual write loop + its guard.
- **Route patterns** — the two POST routes (`/meal-wizard-step4-confirm`, `/meal-wizard-step4-remove`) already exist and are already in `_JSON_PATHS` from G1a; **no routes were added and `_JSON_PATHS` was not edited.**
- **Rule 14** — pre-flight done.
- **Rule 19** — reads/writes flow through `data_helpers`; no hardcoded family specifics.
- Confirmed: **NO `<form>` elements** anywhere in Step 4 (Rule 13) — buttons + `fetch` only.

---

## PRE-FLIGHT (Rule 14)
1. **Files touched (2):** `render_meal_wizard_step4.py` (entry UI + the keep/change JS) and `app.py` (the one-line guard INSIDE the existing `/meal-wizard-step4-confirm` handler). One capability.
2. **JS in Python f-strings?** **YES — first JS in Step 4.** Built as concatenated string literals like `s3Save`; Rules 7/12 honored (no backslash-n in JS strings).
3. **Form handling / nested `/frol-wizard` forms?** NO forms — buttons + `fetch` only.
4. **Root cause confirmed/assumed?** N/A — additive interactivity on a proven screen.
5. **Multiple files?** Two, directly related (the loop's UI + its server guard).
6. **Data shape change?** NO new shape — writes the SAME `confirmed_meals` entry shape G1a defined, via the EXISTING confirm route.

---

## KEY DECISIONS (as approved by Lauren — baked in)
- **Recipe default (client):** a manually entered meal has no `recipe_id`, so the confirm payload sends `recipe_on_request = true` — the intentional "No recipe needed" default; the flow never stops to build a recipe. Reversible later (attaching a recipe in G1b-2b sets `recipe_id`).
- **Server guard (belt-and-suspenders):** in the existing `/meal-wizard-step4-confirm` handler, if `recipe_id` is empty AND `recipe_on_request` was not sent true, **auto-set** `recipe_on_request = true` server-side. So even a buggy/crafted request can't persist a half-confirmed meal. **Auto-set, never reject** (rejecting would stop the flow, contradicting the chosen default).
- **Change = remove for now:** "Change" removes the meal (back to the entry state) so Lauren re-enters. In-place editing is a later refinement.
- **Prefill meals are locked:** entries with `source == "prefill"` are past meals — shown read-only with NO "Change" button. The write loop applies to non-prefill slots only.

---

## WHAT WAS BUILT

### STEP 1 — `app.py`, the server guard (inside the EXISTING confirm handler)
After `_s4_entry` is built and **before** it is written to `confirmed_meals`:
```python
                # G1b-2a server guard (belt-and-suspenders): a manually entered
                # meal has no recipe_id; if the client also did not send
                # recipe_on_request true, auto-set it true so a meal can never
                # persist in the half-confirmed "no recipe AND not marked
                # no-recipe-needed" state. Auto-set, never reject ... (Rule 16).
                if (not _s4_entry["recipe_id"]) and (not _s4_entry["recipe_on_request"]):
                    _s4_entry["recipe_on_request"] = True
```
That is the whole guard. The rest of the handler is unchanged; no new route, no `_JSON_PATHS` edit, imports stay at module top, no walrus.

### STEP 2 — `render_meal_wizard_step4.py`, interactive slots
`_s4_slot_block` now takes `(date_iso, slot_key, label, entry)` and branches three ways:
- **ABSENT (empty slot)** — renders a text input for the **meal name** (required), an optional **ingredients** free-text input (the placeholder explicitly invites *"+ chicken nuggets for James"*), an optional **main-protein** input, a **"Keep this meal"** button (`onclick="s4Keep('<date>','<slot>')"`), and an inline message `<div>`. Inputs carry unique ids `s4-name--<date>--<slot>`, `s4-ing--…`, `s4-prot--…`.
- **PRESENT, `source != "prefill"`** — the full G1b-1 display (name, recipe-state label, source/off-shopping tags) **plus** a **"Change"** button (`onclick="s4Change('<date>','<slot>')"`) and the inline message `<div>`.
- **PRESENT, `source == "prefill"`** — unchanged from G1b-1: locked, no button.

All existing G1b-1 display (recipe-state labels, source tag, off-shopping note, liturgical header, events, gate state, back link) is preserved. New styling lives in pulled-out constants (`_S4_INPUT`, `_S4_KEEP_BTN`, `_S4_CHANGE_BTN`, `_S4_MSG`) so no styles sit inside f-string expressions.

The `onclick` value is built **outside** the f-string (`keep_call = "s4Keep('" + date_iso + "','" + slot_key + "')"`) to avoid nested quotes (Rule 2). `date_iso` is a validated ISO date and `slot_key` comes from the fixed `_S4_SLOT_ORDER` allowlist, so both are safe to inline (no XSS sink).

### STEP 3 — `render_meal_wizard_step4.py`, the JS (`_S4_JS`)
Built as **concatenated string literals** (NOT an f-string), mirroring `s3Save`. **No backslash-n appears in any JS string.** Two globals:
- `window.s4Keep(date, slot)` — reads name/ingredients/protein by id; if name is empty, shows an inline message and returns (never POSTs an empty meal); otherwise POSTs `{date, slot, name, source:'manual', ingredients, protein, recipe_id:'', recipe_on_request:true}` to `/meal-wizard-step4-confirm`; on `{ok:true}` reloads `/meal-wizard-step4`, else shows an inline error.
- `window.s4Change(date, slot)` — POSTs `{date, slot}` to `/meal-wizard-step4-remove`; on `{ok:true}` reloads, else inline error.

Inputs/buttons are addressed by unique element id (`s4-<field>--<date>--<slot>`) so no quoted attribute selectors are needed. **On success the page RELOADS** — the session stays the single source of truth and there is no client-side state to drift. `_S4_JS` is appended to the normal page body only; the gate state remains script-free.

---

## EXPLICITLY OUT OF SCOPE FOR G1b-2a (not built)
- No ingredient green/red parsing of `confirmed_inventory` (G1b-2b).
- No recipe-attach link/flow (G1b-2b).
- No in-place editing (Change = remove + re-enter for now).
- No cook assignment / cook-conflict hint.
- No new routes, no `_JSON_PATHS` edits (the two routes already exist from G1a).
- No plan lock, no Step 3→4 nav wiring, no Lorenzo.

---

## VALIDATION RESULTS (Rules 9 / 10) — THE ROUND-TRIP WAS RUN

**1. `py_compile render_meal_wizard_step4.py app.py`** → **COMPILE OK.**

**2 + 3. AUTHENTICATED HTTP ROUND-TRIP** (`data/verify_meal_wizard_step4_writeloop.py`) — mints a real Lauren session and POSTs through the live handlers, then reads the session back. Snapshots + restores the live `meal_wizard_session.json` and destroys the minted token (Rule 10):
```
PASS confirm POST returns 200 {ok:true}
PASS confirmed meal persisted to session
PASS confirmed meal is locked
PASS GUARD 1: recipe_on_request auto-set True (client omitted it)
PASS confirmed meal has empty recipe_id
PASS GET page shows the confirmed meal
PASS confirmed meal shows a 'Change' button
PASS confirmed meal shows 'No recipe needed'
PASS GUARD 2: recipe_id present -> recipe_on_request left False
PASS GUARD 3: recipe_on_request already True -> left True
PASS remove POST clears the slot from the session
PASS removed slot returns to the empty entry state
PASS prefill (past) meal renders locked with NO 'Change' button

PASS all G1b-2a write-loop + guard checks passed
```
This satisfies the required round-trip exactly: **(a)** POST confirm with recipe fields omitted → session has the entry, `locked` true, `recipe_on_request` true (guard worked though the client omitted it); **(b)** GET shows "Chicken Parm" + a "Change" button + "No recipe needed"; **(c)** POST remove → slot gone, GET back to the empty entry state; **(d)** a prefill entry renders locked with NO "Change". The guard's three branches are exercised as units 1/2/3 against the real handler.

**4. Regression harnesses:**
```
verify_meal_wizard_step4.py  -> PASS all G1b-1 read-only screen checks passed
verify_meal_wizard_step3.py  -> PASS all Step 3 session-state checks passed
```
*Note on the G1b-1 harness:* its one display-only assertion ("seeded render adds no `<script>`") encoded the G1b-1 zero-JS contract, which G1b-2a intentionally supersedes. That single check was updated to assert the seeded render now ships **exactly** the write-loop script (`window.s4Keep`/`window.s4Change`, one `<script>` beyond chrome); the gate-state zero-JS check is unchanged and still passes. All other regression checks are untouched.

**5. Report items:**
- Rules applied: 1, 2, 5, 6, 7, 11, 12, 16, 17, 14, 19, Route patterns. Rules 8 & 13 did NOT apply (no multipart, no forms).
- **JS built as concatenated literals — confirmed; no backslash-n in any JS string.**
- **NO green/red and NO recipe-attach were added** (both deferred to G1b-2b).

---

## CODE REVIEW (architect) — PASS
The architect reviewed the diff and returned **PASS, no blocking functional defects.** It confirmed: the server guard auto-sets (never rejects) exactly as specified; the three slot branches (entry / Change / prefill-locked) are correct; the JS is concatenated literals with no backslash-n misuse; no route surface expansion and `_JSON_PATHS` untouched; the XSS sink points (`onclick`, ids) are constrained to safe values (validated ISO date + allowlisted slot) and meal text is escaped on render; and the validation evidence (py_compile, authenticated round-trip, both regressions) is strong and task-aligned. Non-blocking suggestions for later: add a negative-path test for the JS network-failure UX, and continue the same round-trip harness pattern into G1b-2b.

---

## SUMMARY
Phase **G1b-2a is complete**: Step 4 now has a working manual write loop — enter a meal → "Keep this meal" (confirm) → "Change" (remove) → re-enter — backed by a server-side guard that prevents any half-confirmed meal. Manual entries default to "No recipe needed" so the flow never stalls. Prefill meals stay locked. The JS is concatenated string literals with no backslash-n, no new routes were added, and **no green/red checks or recipe-attach were built (G1b-2b)**. All validation passes, including the required authenticated HTTP round-trip and the architect review. **Stopping here — G1b-2b not started.**
