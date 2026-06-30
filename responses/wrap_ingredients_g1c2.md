# WRAP INGREDIENTS — ingredients box shows full text, no truncation

**Scope:** ONE FILE, markup/CSS, additive. `render_meal_wizard_step4.py`. Same pattern as the meal-NAME textarea. `app.py`, `window.s4Keep`, `window.s4Generate`, the confirm route, the name textarea, and the `<details>` collapse wrapper were **not** touched.

---

## Confirmed first
Before this change, the ingredients field (inside the `<details>` in the EMPTY branch of `_s4_slot_block`) was the single-line `<input type="text" id="s4-ing--{key}" value=...>` with `value=` prefill. ✓ Still an `<input>`, so the conversion proceeded.

## What changed (ingredients field only)
- The ingredients `<input>` is now a **`<textarea>`** — identical approach to the name textarea. The prefill moved out of `value=` and into the **textarea body** (`{ing_body}`), `html.escape`'d **once** (no double-escape). It reuses the `_S4_NAME_AREA` wrapping style, so the full comma-list wraps and is visible with no horizontal truncation.
- `id="s4-ing--{key}"` kept **byte-for-byte** — `s4Keep` reads it at click time unchanged (textarea `.value` works the same as input `.value`).
- It stays **inside** the existing `<details>` wrapper — collapse behavior unchanged (`<details open>` for a Lorenzo suggestion, closed otherwise). The `<details>`/`<summary>` were not altered.
- Protein input, name textarea, and the Keep button are unchanged.

---

## Validation
- **py_compile** -> **PASS**
- **node --check** on emitted `_S4_JS` -> **JS SYNTAX: OK**
- **In-process smoke** (no live writes) — EMPTY entry + suggestion with a long ingredients string `"2 lbs cooked ground beef, jar spaghetti sauce, diced tomatoes, rotini pasta, shredded cheese"`:
  - (a) ingredients render in the `<textarea>` **body**, not `value=` -> **PASS**
  - (b) id still `s4-ing--...` -> **PASS**
  - (c) full text present (nothing truncated) -> **PASS**
  - (d) still wrapped in `<details>` -> **PASS**
  - (e) a double-quote escapes to `&quot;` with no breakout -> **PASS**
- **Step 4 harness** (`data/verify_meal_wizard_step4.py`) -> **PASS** (12/12 checks)

App restarted so the change is live.
