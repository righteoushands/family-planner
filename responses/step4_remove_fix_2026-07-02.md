# Step 4 — Change-revert fix (2026-07-02)

## What changed

### `render_meal_wizard_step4.py` — new `revert_dishes` parameter

**Old signature:**
```python
def render_step4_slot_and_lock(date_iso: str, slot_key: str) -> dict:
```

**New signature:**
```python
def render_step4_slot_and_lock(date_iso: str, slot_key: str,
                               revert_dishes=None) -> dict:
```

`revert_dishes` is a list of dish dicts (or `None`). When provided and non-empty,
the entry affordance pre-fills from those dishes instead of `suggested_meals`.
Falls back to `suggested_meals` when `None` or `[]`.

The function body gained one branch before the `_s4_slot_block` call:

```python
if revert_dishes:
    effective_suggestion = {"dishes": revert_dishes}
else:
    effective_suggestion = suggested.get(full)
slot_html = _s4_slot_block(date_iso, slot_key, label,
                           confirmed.get(full), effective_suggestion)
```

The return dict shape is **unchanged**: `{slot_html, lock_html, lockable}`.

### `app.py` — `/meal-wizard-step4-remove` handler

Two lines added before the `.pop()`, and one keyword argument added to the
`render_step4_slot_and_lock` call:

```python
# Before (was 2 lines):
_s4r_meals = load_meal_wizard_session().get("confirmed_meals") or {}
_s4r_meals.pop(_s4r_date + "::" + _s4r_slot, None)

# After (4 lines + updated call):
_s4r_meals = load_meal_wizard_session().get("confirmed_meals") or {}
# Capture confirmed dishes BEFORE popping so the reverted entry
# affordance can pre-fill from what Lauren actually confirmed,
# not from suggested_meals (which may be fewer dishes or empty).
_s4r_prior_entry  = _s4r_meals.get(_s4r_date + "::" + _s4r_slot) or {}
_s4r_prior_dishes = (_s4r_prior_entry.get("dishes")
                     if isinstance(_s4r_prior_entry, dict) else None)
_s4r_meals.pop(_s4r_date + "::" + _s4r_slot, None)
...
_s4r_frag = render_step4_slot_and_lock(_s4r_date, _s4r_slot,
                                       revert_dishes=_s4r_prior_dishes)
```

`suggested_meals` is not touched anywhere in this handler. No new payload fields.

---

## 1. py_compile

```
python3 -m py_compile render_meal_wizard_step4.py  →  PASS
python3 -m py_compile app.py                        →  PASS
```

---

## 2. In-process smoke test (6/6 PASS)

The test mirrors the actual handler sequence: pop confirmed first, then call render.

```
PASS 1: revert with prior_dishes shows both dishes (2 s4dr rows, both names present)
         — "Sheet Pan Chicken" + "Roasted Sweet Potatoes" both in HTML
PASS 2: revert_dishes=None falls back to suggested_meals (1 row, no side)
         — confirmed-only dish ("Roasted Sweet Potatoes") absent from fallback HTML
PASS 3: revert_dishes=[] falls back to suggested (1 row(s))
PASS 4: old call render_step4_slot_and_lock(date, slot) still works
PASS 5: return dict shape unchanged (slot_html, lock_html, lockable)
PASS 6: bare session (no confirmed, no suggested) renders without error
```

Test 1 specifically verifies the bug scenario: `suggested_meals` had only the main
dish, `confirmed_meals` had main + side (Lauren manually added). After the handler
pop + render call, the reverted form shows **both dishes** — not just the one in
`suggested_meals`.

---

## 3. verify_meal_wizard_step4 harness

```
PASS empty session renders gate state without raising
PASS gate state adds no <script> beyond page chrome (display-only)
PASS seeded render includes the G1b-2a write-loop script (s4Keep/s4Change)
PASS both day labels (Monday, Tuesday) present
PASS selected slot labels (Breakfast, Dinner) present
PASS all three confirmed meal names present
PASS recipe_id meal shows 'Recipe attached'
PASS recipe_on_request meal shows 'No recipe needed'
PASS half-confirmed meal shows 'Recipe: not set yet'
PASS source tags (manual/lorenzo/prefill) present
PASS skip_shopping meal shows 'off shopping list'
PASS back link to Step 3 present
PASS render exposes per-slot row ids + lock-control id (no-reload hooks)

PASS all G1b-1 read-only screen checks passed
```
