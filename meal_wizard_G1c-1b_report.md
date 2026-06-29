# MEAL WIZARD — G1c-1b BUILD REPORT (for Claude)

**Phase:** G1c-1b — generation prompt builder + live `POST /meal-wizard-generate` endpoint.
**Status:** ✅ Built, validated end-to-end through the real authenticated route, and code-reviewed. Two deliberate deviations from the literal spec are reported below (both defensible).

---

## 1. Rule 15 read-back — all 19 claud.md rules

1. No backslashes inside f-strings.
2. No nested quotes inside f-strings — use a variable outside the f-string instead.
3. All GET routing uses `elif` chains in `do_GET`; POST routing in `do_POST` ALSO uses `elif path == "/route-name":` chains (verified live convention). Only exception: the multipart recipe routes share an `elif path in (...)` outer block with nested `if` inner blocks — do NOT copy that for ordinary JSON/form routes.
4. Never put `import` statements inside `if` blocks or functions. (Known deviation, not a license: several live `do_POST` handlers use inline `import json as _json`; new code keeps imports at module top.)
5. All file writes use `safe_save_json` (tmp file + `os.replace`) — never `open(f, 'w')` directly.
6. No walrus operator (`:=`).
7. Never use a raw newline inside a JS string within a Python string literal — emit the escape sequence so the browser receives it.
8. multipart/form-data parsing: sniff `Content-Type` and parse with `cgi.FieldStorage` for multipart; if a POST handler gets empty data, check `Content-Type` first.
9. `py_compile` passes but runtime fails: always run an in-process smoke test after `py_compile`, then run the relevant `verify_*` harness and paste the result. Don't skip the harness for changes touching shared data files, save paths, or multi-caller functions.
10. Test fixtures must never write to live data: harnesses operate on a temp copy; never call write helpers on live data during testing; always restore from backup after any test that touches data files.
11. Double-escaping HTML entities: never pass an already-escaped string through `escape()` again.
12. JS-newline-in-Python-f-strings (Rule 7) applies to ALL files with JS embedded in Python, not just one render file.
13. FROL Wizard nested-form addendum: `_body_has_form` in `_section_chrome` looks for `action="/frol-wizard"`; any section-body form posting to `/frol-wizard` suppresses the Save & Continue button. Forms posting to other routes are safe.
14. Pre-flight checklist (files touched? JS-in-f-strings? form handling? root cause confirmed? multiple files? data-shape/migration?).
15. claud.md read-back required at session start (this section).
16. Magnifica Humanitas design principles — tool not authority; suggestions never prescriptions; companions serve real relationships; AI supports thinking not replaces it; transparency about what AI is; language of grace not performance (no gamification/streaks/shaming); subsidiarity (Lauren is the authority); formation in digital wisdom.
17. One fix per instruction — don't bundle multiple fixes unless same file + directly related; multi-file builds split into sequential single-purpose phases with compile + report between each.
18. August 15th build plan is the priority filter (June 1–Aug 15 2026).
19. Build for a future second family — never hardcode a single family's specifics; keep family identity/config in `app_settings.json`; route data reads/writes through `data_helpers.py`.

**Rules that apply to G1c-1b:** 1, 2, 7 (prompt is assembled with no backslashes/nested quotes/raw-JS-newlines), 3 (the new POST route is an `elif` in `do_POST`), 4 (new imports added at module top), 5 (writes go through `update_meal_wizard_session` → `safe_save_json`), 9 + 10 (in-process smoke + offline harness + real call, all on snapshotted/restored live data), 16 (suggestions are framed as a draft, never auto-confirmed), 17 (single-purpose phase), 19 (generic dad-lunch phrasing instead of hardcoding "John"). **Not applicable:** 8, 11, 12, 13 (no multipart, no HTML escaping, no embedded JS, no FROL forms in this phase), 6 (no walrus used), 14/15/18 (process rules satisfied).

---

## 2. What was built

**`render_meal_wizard_gen.py` — `build_wizard_meal_prompt(session, target_keys)`**
- Module-top imports of `render_lorenzo` helpers (`_get_meal_constraints`, `_get_calendar_this_week`, `_get_saved_recipes`) — verified no circular import.
- Prompt assembled as a list of lines `"\n".join(...)` (Rules 1/2/7 — no f-string backslashes, no nested quotes, no raw JS newlines).
- Context blocks: target slot tokens (kept **raw**, e.g. `2026-06-30::dinner`, so the model echoes keys the G1c-1a parser matches), confirmed meals to protect, use-soon items, inventory, used proteins to avoid, complexity, calendar, and an explicit JSON output contract.

**`app.py`**
- `import requests` added at module top.
- Top-level import of `wizard_target_slot_keys, parse_wizard_meal_response, build_wizard_meal_prompt`.
- `/meal-wizard-generate` added to the **local** `_JSON_PATHS` set inside `do_POST` (required so the JSON body isn't silently consumed by the form parser).
- New `elif path == "/meal-wizard-generate":` route (before `/meal-generate`), mirroring `/meal-generate`: empty-target short-circuit → build prompt → call Anthropic → parse with G1c-1a parser → `update_meal_wizard_session({"suggested_meals": ...})`.
- **Draft-layer isolation:** the route writes ONLY `suggested_meals`. It never touches `confirmed_meals`, the canonical meal store, or `used_proteins`.

---

## 3. ⚠️ Deviation 1 (BLOCKING bug found & fixed) — model string

The spec said to use `claude-sonnet-4-20250514`. **That model returns `404 not_found` with this app's live API key** — it is fully retired (claud.md already flags it as "stale/unverified"). Left as-is, the production route would have failed on every call.

Probe results against the live key:
| model | result |
|---|---|
| `claude-sonnet-4-20250514` | **404 not_found** |
| `claude-sonnet-4-6` | **200 OK** ✅ |
| `claude-sonnet-4-5` / `claude-sonnet-4-5-20250929` | 200 OK |
| `claude-haiku-4-5-20251001` | 200 OK (Lorenzo's model) |

**Action taken:** route model string switched to **`claude-sonnet-4-6`** (the spec's own named fallback). Note: several *other* handlers in `app.py` still hardcode the dead `claude-sonnet-4-20250514` — those are latent bugs to fix when next touched (logged to memory), but out of scope for this single-purpose phase (Rule 17).

## 4. Deviation 2 (defensible, by design) — generic dad-lunch phrasing

The spec's example text named "John" for the dad-lunch slot. I phrased it generically ("the dad-lunch slot … he prefers meat") rather than hardcoding the name, per **Rule 19** (no single-family specifics baked into code). The behavior is identical; only the literal string differs.

---

## 5. Validation evidence

- **`py_compile`** passes for `app.py` and `render_meal_wizard_gen.py`.
- **Offline harness** `data/verify_meal_wizard_gen.py`: all 39 checks PASS (incl. step3/step4 regressions).
- **Real authenticated HTTP wiring** (no paid call): `POST /meal-wizard-generate` with empty targets → `{"ok": true, "generated": 0, "message": "No empty slots to generate."}` — proves route registration + `_JSON_PATHS` + auth.
- **Real paid generation through the LIVE route** (one authenticated `POST /meal-wizard-generate` as Lauren, model `claude-sonnet-4-6`): HTTP 200, `{"ok": true, "generated": 2, "target": 2}`, `suggested_meals` populated. Live session snapshotted before and restored after (Rule 10).

Sample generated draft (respects use-soon spinach + inventory beef/beans, avoids chicken which was a used protein, "simple" complexity, date-night note):
```json
{
  "2026-06-30::dinner": {"name": "Ground Beef Taco Bowls with Black Beans and Spinach", "protein": "ground beef", "source": "lorenzo", "recipe_on_request": true, "skip_shopping": false, "...": "..."},
  "2026-07-01::dinner": {"name": "Black Bean and Spinach Rice Bowls", "protein": "", "note": "Meatless; Date Night — kids eat simple bowls", "source": "lorenzo", "...": "..."}
}
```

**Assertions (live route):** `ok == True`; `generated > 0`; suggested keys ⊆ targets (no confirmed/out-of-window/extra slot leaked); `confirmed_meals` UNTOUCHED; `used_proteins` UNTOUCHED.

---

## 6. Architect code review outcome

The architect's only blocking finding was the dead model string — which is now fixed and re-verified through the live route (generated:2). It confirmed: core architecture correct, draft-layer isolation correct (only `suggested_meals` written), routing/import/style constraints respected, no security issues, and the Rule 19 dad-lunch phrasing is acceptable (not a failure).

---

## 7. Out of scope (next phase G1c-2)

No UI/button was added this phase — that is G1c-2. The endpoint is live and ready for a trigger to be wired to it.
