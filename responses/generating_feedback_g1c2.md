# GENERATING FEEDBACK — Generate button shows it's working during the call

**Scope:** ONE FILE, JS only, additive. `render_meal_wizard_step4.py` (`window.s4Generate` in `_S4_JS`). `app.py`, `/meal-wizard-generate`, `window.s4Keep`, the confirm route, and every meal field were **not** touched.

---

## Problem
`s4Generate` disabled the button and fetched `/meal-wizard-generate`, but the button **label never changed** — so a ~60s call looked frozen.

## What changed (`window.s4Generate` only)
1. **On click, before the fetch:** after disabling the button, the current label text is saved to a local `origLabel`, then the button text is set to:
   `Generating... this can take up to a minute`
   (plain ASCII — three dots, no apostrophe, no em-dash, so no escape rules are triggered.)
2. **On success** (`generated > 0`): reloads as before. Label not restored — the page reloads.
3. **On failure** (error key, `generated` 0, `ok` falsy, or `.catch`): the button is re-enabled **and** its label is restored to the saved `origLabel`, then `s4-gen-msg` shows the error as before.

No spinner, image, or library — text only. Nothing else changed.

---

## Validation
- **py_compile** -> **PASS**
- **node --check** on emitted `_S4_JS` -> **JS SYNTAX: OK**
- **Label string safety** — `Generating... this can take up to a minute`: no backslash, no single quote, no double quote, no raw newline, ASCII only -> **all True**
- **Step 4 harness** (`data/verify_meal_wizard_step4.py`) -> **PASS** (12/12 checks)

App restarted so the change is live.
