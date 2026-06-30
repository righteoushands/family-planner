# NAME WRAP — meal name shows full text, no truncation

**Scope:** ONE FILE, CSS/markup only, additive. `render_meal_wizard_step4.py`. `app.py`, `window.s4Keep`, `window.s4Generate`, and the confirm route were **not** touched.

---

## Confirmed first
The meal-NAME field in the EMPTY branch of `_s4_slot_block` **was** a single-line `<input type="text" id="s4-name--{key}">`. Proceeded with the textarea conversion.

## What changed (name field only)
- The meal-name `<input>` is now a **`<textarea>`** so long names like "Ground Beef Pasta with Spaghetti Sauce" wrap and show in full with no horizontal scroll.
- **`id="s4-name--{key}"` is byte-for-byte unchanged** (s4Keep reads this id at click time).
- **Pre-fill moved into the textarea body** (textareas have no `value=` attribute). The name is still `html.escape`-d exactly once — no double-escape.
- **Auto-sizing without JS:** `rows="2"` plus a small CSS style (`resize:vertical; overflow-wrap:break-word; white-space:pre-wrap; line-height:1.3`, reusing the existing input style). Short names stay compact; long names wrap; no auto-grow library added.
- **Ingredients and protein fields left exactly as they are** (single-line inputs with `value=`). The ingredients collapse is a separate later instruction.
- The Keep button, its onclick, and all three ids are identical.

New style constant added: `_S4_NAME_AREA` (built from `_S4_INPUT` + wrapping/resize).

---

## Validation
- **py_compile** `render_meal_wizard_step4.py` -> **PASS**
- **node --check** on emitted `_S4_JS` -> **JS SYNTAX: OK**
- **In-process smoke** (no live writes), EMPTY entry + suggestion `{"name": 'Ground Beef Pasta with Spaghetti Sauce', ...}`:
  1. name renders inside the `<textarea>` body -> **PASS**
  2. name is NOT in a `value=` attr -> **PASS**
  3. id is still `s4-name--...` on the textarea -> **PASS**
  4. a name with a double-quote (`Mac "n" Cheese`) renders escaped as `&quot;` with no attribute breakout -> **PASS**
  5. Keep onclick + ingredients/protein ids unchanged -> **PASS**
- **Step 4 harness** (`data/verify_meal_wizard_step4.py`) -> **PASS** (12/12 checks)

App restarted so the change is live.
