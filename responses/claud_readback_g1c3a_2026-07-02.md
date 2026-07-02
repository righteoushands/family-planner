# Rule 15 read-back — G1c-3a session (2026-07-02)

## All rules pasted back

**1.** No backslashes inside f-strings.

**2.** No nested quotes inside f-strings — use a variable outside the f-string instead.

**3.** All GET routing uses `elif` chains in `do_GET`; POST routing in `do_POST` ALSO uses `elif` chains. ONE exception: the multipart recipe routes share an `elif path in (...)` outer block. Do NOT copy that pattern for ordinary routes.
[CORRECTED June 28 2026: prior note claimed standalone `if` blocks; live code uses `elif` chains.]

**4.** Never put import statements inside `if` blocks or functions.
[KNOWN DEVIATION: several live handlers use inline `import json as _json`. New code: imports at module top.]

**5.** All file writes use `safe_save_json` — never `open(f, 'w')` directly.

**6.** No walrus operator (`:=`).

**7.** Never use raw `\n` inside a JS string within a Python string literal — use `'\n'`.

**8.** multipart/form-data: sniff `Content-Type` and parse with `cgi.FieldStorage`. If a POST handler gets empty data check Content-Type first.

**9.** `py_compile` only validates syntax. Always run an in-process smoke test after `py_compile`. Then run the relevant `verify_*.py` harness. Do not skip the harness for changes touching shared data files or functions called from more than one place.

**10.** Test fixtures must never write to live data. Always restore from backup after any test touching data files.

**10a.** ISOLATION MUST BE STRUCTURAL. Any `verify_*.py` harness must import its isolation guard as the literal first import — before `data_helpers`, `config`, or any `render_*.py`. The guard must raise (not warn) if the write target resolves to a live path.

**11.** Never pass an already-HTML-escaped string through `escape()` again.

**12.** Rule 7 applies to ALL files with JS embedded in Python, not just `render_frol_wizard.py`.

**13.** FROL WIZARD NESTED FORM ADDENDUM — `_body_has_form` check looks for `action="/frol-wizard"`. Confirm `action` attribute before adding any form to a section body.

**14.** PRE-FLIGHT CHECKLIST — (1) how many files, list them; (2) JS in f-strings → flag `\n` rule; (3) form handling → no nested forms to `/frol-wizard`; (4) root cause confirmed or assumed; (5) multiple files → break into single-purpose phases; (6) data shape changes → confirm before/after explicitly.

**15.** CLAUD.MD READ-BACK REQUIRED — paste every rule at session start. ✅ done.

**16.** MAGNIFICA HUMANITAS — app is a tool not an authority; companions serve real relationships; AI supports thinking; transparent about AI; language of grace not performance; subsidiarity; formation in digital wisdom.

**17.** ONE FIX PER INSTRUCTION — never bundle multiple fixes unless same file and directly related. Multi-file builds → sequential single-purpose phases.

**18.** AUGUST 15TH PRIORITY FILTER — every build request checked against the August 15th plan. Scope is the first thing to cut.

**19.** BUILD FOR A FUTURE SECOND FAMILY — no hardcoded family specifics; family identity in `app_settings.json`; all reads/writes through `data_helpers.py`.
[KNOWN DEBT: `build_lorenzo_context` hardcodes roster. New Step 4 / Lorenzo work must NOT deepen this.]

**20.** PRESERVE SCROLL ON SAME-PAGE RELOADS — `fetch()` POST that reloads same page must save/restore `scrollY` via `sessionStorage`. Forward nav to different page exempt.

**21.** SESSION HELPER SHALLOW-MERGE — `update_meal_wizard_session` merges ONLY at top level. Nested key write (`{"suggested_meals": {...}}`) REPLACES the whole nested dict. Read fresh → merge → write; read immediately before write, not before a long AI call.
[KNOWN DEVIATION July 1 2026: the confirm-mirror bug; fixed by fresh-read + merge.]

**22.** MERGE-BASED GENERATE NO LONGER PRUNES — stale `suggested_meals` entries accumulate. Inert unless a stale key re-enters window×to_plan unconfirmed. If addressed: prune in the generate handler, do not revert to wholesale replace.

---

## Pre-flight checklist (Rule 14) — G1c-3a

1. **Files touched:** `render_meal_wizard_gen.py` (production), `data/verify_meal_wizard_gen.py` (harness). Not touching app.py or render_meal_wizard_step4.py.
2. **JS in f-strings?** No — `render_meal_wizard_gen.py` contains no JS. Not applicable.
3. **Form handling?** No.
4. **Root cause confirmed?** Yes — task is a planned schema upgrade, not a bug fix.
5. **Multiple files?** Yes (gen + harness). Both are in scope per the task; harness is the verification artifact for the same change.
6. **Data shape change?** Yes. Before: `{name, protein, ingredients, note}` flat per slot. After: `{dishes: [{category, name, protein, ingredients}], note}` per slot.

## Circular import flag (Rule 4 corollary)

`render_meal_wizard_step4.py:37` already imports `_WIZARD_GEN_SLOT_CAP` from `render_meal_wizard_gen`. Adding `from render_meal_wizard_step4 import CATEGORIES` in the reverse direction closes the cycle → `ImportError` at load time. Resolution: define `_DISH_CATEGORIES` locally in `render_meal_wizard_gen.py` with a comment pointing to `render_meal_wizard_step4.CATEGORIES` and a TODO to consolidate in `config.py` in a future cleanup pass. This satisfies "do not hardcode in the prompt text."

## Rules that apply to G1c-3a

| Rule | Why |
|---|---|
| **1, 2** | `build_wizard_meal_prompt` uses string concatenation (no f-strings) — already compliant; stay compliant on any new lines |
| **4** | All imports stay at module top; no inline imports |
| **9** | py_compile + in-process smoke test + harness run required |
| **10 / 10a** | Harness reads `meal_wizard_session.json` indirectly; `verify_meal_wizard_gen.py` is a pure-logic harness (no live data writes), so isolation is N/A for this harness — but import order still matters |
| **14** | Pre-flight done above |
| **17** | One phase, two files (gen + its harness) — directly related ✓ |
| **19** | `_DISH_CATEGORIES` must not embed family names; categories are domain constants, not family data |
| **21** | Not touched in this pass, but any downstream caller writing `suggested_meals` must read-fresh + merge |
| **22** | Awareness: stale entries in `suggested_meals` may resurface with old flat shape after this change |
