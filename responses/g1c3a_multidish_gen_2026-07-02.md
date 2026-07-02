# G1c-3a — Lorenzo multi-dish generation (2026-07-02)

**Files changed:** `render_meal_wizard_gen.py`, `data/verify_meal_wizard_gen.py`
**Files NOT touched:** `app.py`, `render_meal_wizard_step4.py` ✓

---

## Circular import flag (resolved inline)

`render_meal_wizard_step4.py:37` already imports `_WIZARD_GEN_SLOT_CAP` from
`render_meal_wizard_gen`. Adding the reverse import (`from render_meal_wizard_step4
import CATEGORIES`) would close the cycle → `ImportError` at load time.

**Resolution:** `_DISH_CATEGORIES` is defined locally in `render_meal_wizard_gen.py`
with a comment naming the source of truth and a TODO to consolidate both into
`config.py` in a future cleanup pass. The category list is NOT hardcoded in any
prompt string — it is always referenced via `_DISH_CATEGORIES`. Satisfies the intent of
the instruction.

---

## What changed

### New constants (module level)

```python
_DISH_CATEGORIES = (
    "main", "side", "soup", "bread", "salad", "appetizer", "dessert", "snack"
)

_MULTI_DISH_SLOTS = frozenset({"dinner", "feast_meal"})
```

### New helper: `_parse_valid_dishes(raw_dishes, is_multi)`

Extracted from `parse_wizard_meal_response` to keep the logic testable and explicit:

- Iterates the raw `dishes` list from the model response.
- Drops any dish whose `category` is absent or not in `_DISH_CATEGORIES` — **no
  defaulting to "main"**.
- Drops any dish with an empty `name`.
- If `not is_multi`: breaks after the first valid dish (**single-dish cap enforced
  in the parser itself**, independent of the prompt).

### `parse_wizard_meal_response` — dishes[] schema replaces flat shape

**Before (G1c-1b):** each slot value was `{"name":"...", "protein":"...",
"ingredients":"...", "note":"..."}` (flat).

**After (G1c-3a):** each slot value is `{"dishes": [...], "note": "..."}`.

New behavior:
- `val.get("dishes")` — reads the list; if absent or not a list, `raw_dishes = []`.
- `val.get("note")` — still top-level per slot (unchanged).
- Old flat dicts and bare-string slot values produce `raw_dishes = []` → zero
  valid dishes → **slot dropped entirely** (no backward compat shim).
- Slots with zero valid dishes after `_parse_valid_dishes` are silently dropped.

### `build_wizard_meal_prompt` — dishes[] schema + count rules

New per-target annotations in the target block:
```
  - 2026-07-07 — dinner  [multi-dish: 2-3 dishes, one main + sides]
  - 2026-07-07 — breakfast  [single dish, category: main]
```

New prompt sections:
- **Dish count rules** — multi-dish slots (dinner, feast_meal): 2-3 dishes, cap 3;
  single-dish slots: exactly 1 with category "main".
- **Valid category values** — `", ".join(_DISH_CATEGORIES)` injected directly; never
  hardcoded as a literal string in the prompt.

New output schema line:
```
{"meals": {"YYYY-MM-DD": {"slot": {
  "dishes": [{"category": "...", "name": "...", "protein": "...", "ingredients": "..."}],
  "note": "..."
}}}}
```

---

## Test results

### py_compile
```
py_compile OK
```

### In-process smoke test (8/8)
```
  PASS wizard_target_slot_keys
  PASS _parse_valid_dishes non-multi cap
  PASS _parse_valid_dishes invalid cat dropped
  PASS _parse_valid_dishes all invalid -> []
  PASS parse drops slot with all-invalid cats
  PASS parse dinner multi keeps 3 dishes
  PASS build_wizard_meal_prompt smoke
  PASS constants sane
```

### verify_meal_wizard_gen harness (63/63)
```
PASS confirmed slot excluded
PASS 5 remaining keys (3 days x 2 slots - 1 confirmed)
PASS exact expected keys
PASS result is sorted
PASS missing window -> []
PASS missing slots -> []
PASS inverted window (end<start) -> []
PASS bad date -> []
PASS _DISH_CATEGORIES is a tuple or frozenset
PASS 'main' in _DISH_CATEGORIES
PASS 'side' in _DISH_CATEGORIES
PASS 'snack' in _DISH_CATEGORIES
PASS 'dinner' in _MULTI_DISH_SLOTS
PASS 'feast_meal' in _MULTI_DISH_SLOTS
PASS 'breakfast' NOT in _MULTI_DISH_SLOTS
PASS only target keys present
PASS confirmed key absent
PASS out-of-window date absent
PASS target dinner mapped (dishes[0].name)
PASS entry has dishes list
PASS dish category main
PASS no flat name key on entry
PASS entry source lorenzo
PASS entry recipe_on_request True
PASS entry recipe_id empty
PASS entry skip_shopping False
PASS dish protein captured
PASS dish ingredients captured
PASS entry note captured (top-level)
PASS trailing-comma JSON parses
PASS garbage -> {}
PASS empty string -> {}
PASS bare wrapper maps
PASS old flat shape (no dishes key) -> slot dropped
PASS bare-string slot value -> slot dropped
PASS empty target -> {}

--- G1c-3a truncation and drop tests ---
PASS truncation: breakfast slot present in output
PASS truncation: exactly 1 dish kept (single-dish cap)
PASS truncation: first valid dish kept (Oatmeal)
PASS truncation: 'main' category retained
PASS truncation: invalid 'fried' dish not present
PASS truncation: 'Fruit bowl' not present (truncated, not just invalid)
PASS drop: dinner slot with all-invalid categories → slot absent
PASS multi-dish: dinner keeps all 3 valid dishes
PASS multi-dish: main dish present
PASS multi-dish: both sides present
PASS mixed multi: 2 valid dishes kept (1 invalid dropped)
PASS mixed multi: invalid dish absent
PASS mixed multi: 'Salmon' present

--- build_wizard_meal_prompt tests ---
PASS prompt is a non-empty string
PASS prompt contains target date 2026-06-29 … 2026-07-02
PASS prompt contains slot word 'dinner'
PASS prompt contains slot word 'breakfast'
PASS prompt contains use-soon 'old bananas'
PASS prompt notes the form 'canned'
PASS prompt lists used protein 'chicken'
PASS prompt contains complexity word 'simple'
PASS prompt contains dishes[] output schema
PASS prompt contains JSON output-contract outer shape
PASS prompt forbids extra cells
PASS prompt protects confirmed meals
PASS prompt migrates OLD flat confirmed entry name (read-time migration)
PASS prompt lists valid categories from _DISH_CATEGORIES
PASS prompt mentions multi-dish dinner rule
PASS prompt mentions single-dish rule for non-dinner
PASS prompt annotates dinner target as multi-dish
PASS prompt annotates breakfast target as single-dish

PASS all G1c-1a / G1c-3a generation-contract checks passed
```

---

## Rules applied

| Rule | How |
|---|---|
| **1, 2** | `build_wizard_meal_prompt` uses `lines.append(...)` joined with `"\n".join(lines)` — no f-strings, no backslash/quote hazards |
| **4** | All imports at module top; no inline imports |
| **9** | py_compile + in-process smoke test + harness — all run, all reported |
| **17** | Two files (gen + its harness), directly related — one phase ✓ |
| **19** | `_DISH_CATEGORIES` is domain constants, not family data; category list injected via `", ".join(_DISH_CATEGORIES)`, never hardcoded in a string |

---

## What app.py's /meal-wizard-generate route will now receive

`parse_wizard_meal_response` returns entries shaped:
```json
{
  "2026-07-07::dinner": {
    "dishes": [
      {"category": "main", "name": "Roast chicken", "protein": "chicken", "ingredients": "..."},
      {"category": "side", "name": "Green beans",   "protein": "",        "ingredients": "..."}
    ],
    "note": "",
    "source": "lorenzo",
    "recipe_id": "",
    "recipe_on_request": true,
    "skip_shopping": false
  }
}
```

This is already the canonical `dishes[]` shape that `slot_dishes()`, `format_dish_list()`,
and the Step-4 confirm handler all expect. No migration needed downstream.
