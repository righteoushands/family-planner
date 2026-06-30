# claud.md read-back + DIAGNOSIS — `name`/`ingredients`/`protein` slot-key inventory

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
9. py_compile is syntax-only; after it run an in-process smoke test, then the relevant verify harness and paste the result.
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
20. Preserve scroll on same-page reloads (fetch → `window.location.href` to same page must save/restore `scrollY`); `render_meal_wizard_step4.py` is the reference.

### Which rules apply to THIS task
- **Rule 14 (data-shape change → confirm) is the headline** — this is exactly the "confirm the full blast radius before a data-shape change" case. This report IS that confirmation step; it lists every site so the next instruction changes all of them at once.
- **Rule 9** will govern the eventual change (py_compile → smoke → every `verify_meal_wizard_*` harness, since the slot shape is a multi-caller data contract).
- **Rule 19** — the shape lives in the wizard session / meal store via `data_helpers.py`; keep IO there.
- **Rule 7/12** — `render_meal_wizard_step4.py`'s write-loop JS and `_s4_slot_block` will need new dish fields without raw newlines.
- **DIAGNOSIS ONLY** this turn — no code changed, no migration written (Rule 17 deferred to the change instruction).

---

## ⚠️ Important correction before the inventory

**There is no `meal_name` key anywhere in the codebase** (`rg meal_name` → 0 hits). The flat dish-name key on a slot object is **`name`**. The flat slot shape today is:

```
{ "name", "ingredients", "protein", "note", "source",
  "locked", "recipe_id", "recipe_on_request", "skip_shopping" }
```

So the move is `name`/`ingredients`/`protein` (+`note`) → `dishes: [{category, name, ingredients, protein}, ...]`. Plan the rename against **`name`**, not `meal_name`, or the change will miss every real site.

---

## The inventory — every read/write of `name` / `ingredients` / `protein` on a slot object

### render_meal_wizard_gen.py — the generation data contract
| Function | Line(s) | R/W | What |
|---|---|---|---|
| `parse_wizard_meal_response` | 104, 105, 106, 107 | **READ** | `val.get("name"/"protein"/"ingredients"/"note")` from Lorenzo's JSON |
| `parse_wizard_meal_response` | 115–124 | **WRITE** | builds the flat `out[key] = {"name","protein","ingredients","note",…}` (→ `suggested_meals`) |
| `build_wizard_meal_prompt` | 174 | **READ** | `cv.get("name")` from `confirmed_meals` for the "already decided" block |
| `build_wizard_meal_prompt` | 237–238 | **WRITE (prompt text)** | the JSON contract dictated to the model: `{"name","protein","ingredients","note"}` — must teach the model the new `dishes[]` shape |
| `wizard_target_slot_keys` | 45 | reads `confirmed_meals` **keys only** (not the 3 data keys) — adjacent, no change to data fields |

### render_meal_wizard_step4.py — write loop + display
| Function | Line(s) | R/W | What |
|---|---|---|---|
| `_S4_JS` `s4Keep` | 213, 215, 216, 217–218 | **WRITE (client)** | reads the name/ing/protein inputs and POSTs `{name, ingredients, protein, …}` to `/meal-wizard-step4-confirm` |
| `_s4_slot_block` (empty-slot affordance) | 301, 302, 303 | **READ** | `suggestion.get("name"/"ingredients"/"protein")` to pre-fill the entry inputs from a Lorenzo draft |
| `_s4_slot_block` (confirmed display) | 323 | **READ** | `entry.get("name")` only — **ingredients/protein are NOT shown** in the confirmed display today |
| `_s4_recipe_label` | 190–193 | reads `recipe_id`/`recipe_on_request` only — **not** the 3 keys (no change) |

Note: the HTML input ids (`s4-name--`, `s4-ing--`, `s4-prot--`) and the single name/ingredients/protein input row will need to become repeatable per dish.

### app.py — do_POST write handlers
| Route / context | Line(s) | R/W | What |
|---|---|---|---|
| `/meal-wizard-step3-save` (prefill build) | 10740–10743 | **WRITE** | prefill entries store **`name`** only (`{"name", "locked", "source":"prefill", "skip_shopping", "recipe_on_request"}`) — no ingredients/protein today |
| `/meal-wizard-step4-confirm` | 10783 | **READ** | `name` from payload |
| `/meal-wizard-step4-confirm` | 10804–10813 | **WRITE** | builds the confirmed slot entry: `"name"` (10805), `"ingredients"` (10808), `"protein"` (10812) |
| `/meal-wizard-step4-confirm` | 10827 | derived | `recompute_used_proteins(_s4_meals)` |
| `/meal-wizard-step4-remove` | 10860, 10863 | pops slot + `recompute_used_proteins` — no direct key read |
| `/meal-wizard-generate` | ~10943, ~10946 | **WRITE** | stores `parse_wizard_meal_response` output into `suggested_meals` (carries the flat shape from gen.py) |

### data_helpers.py — the used-protein check
| Function | Line(s) | R/W | What |
|---|---|---|---|
| `recompute_used_proteins` | 3341 | **READ** | `_entry.get("protein")` over every `confirmed_meals` value — **this is the used_proteins check.** With `dishes[]` it must iterate each dish's `protein` (the docstring at 3327–3336 also references the single `protein`/`ingredients` fields and needs updating) |
| `get_confirmed_meals` | 3320–3324 | returns the dict — no per-key read |

### render_meals.py — the store boundary (homepage / lock view source)
| Function | Line(s) | R/W | What |
|---|---|---|---|
| `apply_confirmed_meals_to_store` | 227 | **READ** | `entry.get("name")` |
| `apply_confirmed_meals_to_store` | 232–233 | **READ/WRITE** | reads `recipe_id`; writes store value `{"display": name, "recipe_id": rid}` or bare `name` |
| `as_text` store reader | 46–49 | reads `value.get("display")` — **store shape, not the wizard slot keys** |

**Key finding about the homepage / lock view:** the canonical meal store only ever keeps **`display` (the name) + `recipe_id`**. `ingredients` and `protein` are **dropped at the `apply_confirmed_meals_to_store` boundary** and never reach the store. So the homepage / weekly meal-plan renderer (which reads the store via `as_text`/`display`) does **not** read `ingredients` or `protein` at all today. If a multi-dish meal should show all its dish names on the homepage, `apply_confirmed_meals_to_store` (line 233) is the **only** place to decide how `dishes[]` collapses into the store's `display` string — that is the one spot that currently flattens the shape.

### Test harnesses that hard-code the flat shape (data/verify_*.py)
Not app code, but they encode the contract and will fail until updated alongside the change (Rule 9 requires running them):
- `verify_meal_wizard_gen.py` — 66, 89–90, 104, 112, 135
- `verify_meal_wizard_step4.py` — 87–103
- `verify_meal_wizard_step4_writeloop.py` — 107, 176–177
- `verify_meal_wizard_g1a.py` — 65–69, 112–131
- `verify_meal_wizard_step3.py` — `_build_confirmed_meals` (49) and its assertions

---

## Summary of the blast radius (6 app files + 5 harnesses)

1. **render_meal_wizard_gen.py** — parser output shape, prompt's "already decided" read, and the model-facing JSON contract.
2. **render_meal_wizard_step4.py** — `s4Keep` payload (write), `_s4_slot_block` suggestion-prefill (read) + confirmed display (currently name-only), repeatable per-dish inputs.
3. **app.py** — `/meal-wizard-step4-confirm` (read+write), `/meal-wizard-step3-save` prefill write (name-only today), `/meal-wizard-generate` (suggested_meals write).
4. **data_helpers.py** — `recompute_used_proteins` must walk `dishes[].protein` (+ docstring).
5. **render_meals.py** — `apply_confirmed_meals_to_store` is the single flatten point where `dishes[]` must collapse to the store's `display`; everything downstream (homepage/lock view) reads only `display`+`recipe_id`, so no further homepage edits are needed beyond that collapse.
6. **5 verify harnesses** — update fixtures/assertions to the `dishes[]` shape and re-run per Rule 9.

**Two facts that most affect the design:** (a) the key is **`name`, not `meal_name`**; (b) `ingredients`/`protein` already die at the store boundary, so the homepage never reads them — the only decision there is how `dishes[]` renders into the store `display` string in `apply_confirmed_meals_to_store` (render_meals.py:233).

No code was changed (diagnosis only, per instruction).
