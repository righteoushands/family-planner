# COLLAPSE INGREDIENTS — ingredients box collapsible, open only for an unreviewed Lorenzo suggestion

**Scope:** ONE FILE, markup/CSS, additive. `render_meal_wizard_step4.py`. `app.py`, `window.s4Keep`, `window.s4Generate`, the confirm route, and the meal-NAME textarea were **not** touched.

---

## Confirmed first (A / B)
- **A)** In the EMPTY branch of `_s4_slot_block`, the ingredients field **was** the single-line `<input id="s4-ing--{key}">` with `value=` prefill. ✓
- **B)** The CONFIRMED branch (entry is a dict / kept meal) renders **only** name + recipe meta + tag(s) + Change button — **no ingredients input box at all.** So "collapse on approved Lorenzo" needs **no code** in the confirmed branch; it's already satisfied. Only the EMPTY branch was changed.

## What changed (EMPTY branch only)
1. The ingredients `<input id="s4-ing--{key}">` is now wrapped in a native **`<details><summary>Ingredients</summary> ... </details>`** — pure HTML, no JS.
2. **Open vs closed by default:**
   - Slot **has** a Lorenzo suggestion (the `suggestion` dict is present — same condition that drives the prefill) -> `<details open>` (expanded for review).
   - Otherwise (empty slot, no suggestion) -> `<details>` (closed / compact).
3. **The input stays in the DOM** inside the `<details>` whether open or closed (collapsing only hides display; the element and its value persist). It was not moved, renamed, or conditionally omitted — `id="s4-ing--{key}"` is byte-for-byte unchanged, so `s4Keep` reads it at click time as before.
4. The protein field, the Keep button, and the name textarea are unchanged. Confirmed branch unchanged (it has no ingredients box).

New style constants added: `_S4_DETAILS`, `_S4_SUMMARY`.

---

## Validation
- **py_compile** -> **PASS**
- **node --check** on emitted `_S4_JS` -> **JS SYNTAX: OK**
- **In-process smoke** (no live writes):
  - (i) EMPTY + suggestion `{"ingredients":"diced tomatoes, rotini", ...}` -> `<details open>` wraps the ingredients input, input still has `id="s4-ing--..."` and its prefilled value, name renders -> **PASS**
  - (ii) EMPTY, no suggestion -> `<details>` (no `open`) and the ingredients input is still present with id intact (collapsed, not removed) -> **PASS**
  - (iii) double-quote in ingredients escaped once (`&quot;`), no attribute breakout -> **PASS**
- **Step 4 harness** (`data/verify_meal_wizard_step4.py`) -> **PASS** (12/12 checks)

App restarted so the change is live.
