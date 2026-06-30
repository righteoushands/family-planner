# BUILD complete — inventory double-spend soft-guard (prompt-only)

**File changed:** `render_meal_wizard_gen.py` (one file, additive only). No data-shape change, no migration, no JavaScript, no f-strings, no backslash-n.

## What was added
Immediately after the on-hand inventory block (after the "Respect the form exactly…" line), inside `build_wizard_meal_prompt`:

```python
    lines.append("Respect the form exactly: if an item is canned, do not plan a dish that needs it fresh, and vice versa; treat the canned/frozen form as usable as-is.")
    # TEMPORARY soft-guard, prompt-only — no real inventory depletion exists yet.
    # Revisit/remove when structured inventory lands (TRACKER 40/44). Added 2026-06-30.
    lines.append("The already-decided meals above draw from this same on-hand list.")
    lines.append("Some on-hand items are a single package or a small fresh amount. Do not propose a new dish that relies on a limited fresh or perishable item that an already-decided meal already uses — treat that item as spent.")
    lines.append("")
    lines.append("Do NOT repeat a main protein already used this week:")
```

This is an interim prompt-level guard only — it does **not** subtract ingredients from inventory and changes no data. Real depletion remains pending the structured-inventory build (TRACKER 40/44), as flagged in the June 30 diagnosis.

## Validation results (all three passed, in order)

### 1. `py_compile render_meal_wizard_gen.py`
```
py_compile OK
```

### 2. In-process smoke test (`build_wizard_meal_prompt` with a confirmed meal + inventory)
```
line1 count: 1
line2 count: 1
--- context ---
 canned tomatoes, frozen peas
Respect the form exactly: if an item is canned, do not plan a dish that needs it fresh, and vice versa; treat the canned/frozen form as usable as-is.
The already-decided meals above draw from this same on-hand list.
Some on-hand items are a single package or a small fresh amount. Do not propose a new dish that relies on a limited fresh or perishable item that an already-decided meal already uses — treat that item as spent.

Do
SMOKE OK: both new lines present exactly once
```
Both new lines appear exactly once, in the correct position (directly after the inventory "Respect the form" line, before the protein-rotation block).

### 3. `verify_meal_wizard_gen.py`
```
PASS all G1c-1a generation-contract checks passed
exit: 0
```
All 39 generation-contract checks passed (slot scoping, parser mapping, prompt content — including use-soon, form/canned, used proteins, complexity, confirmed-meal protection, and output-contract shape). No regressions.

## Scope confirmation
No other changes were made. Only the four added lines (two comment lines + two `lines.append(...)` lines) in `render_meal_wizard_gen.py`.
