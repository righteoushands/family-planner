"""Offline harness for render_meal_wizard_gen (G1c-1a / G1c-3a).

Pure-logic checks on fixtures only — NO network call, NO live data writes.
Run: python data/verify_meal_wizard_gen.py

G1c-3a changes vs G1c-1a:
- parse_wizard_meal_response fixtures updated to dishes[] schema.
- Old flat-shape fixtures removed (schema replaced, not extended).
- New tests: truncation (non-multi slot with >1 dish) and drop (all dishes
  have invalid category) behaviors.
- build_wizard_meal_prompt checks extended for dishes[] schema and categories.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from render_meal_wizard_gen import (  # noqa: E402
    wizard_target_slot_keys,
    parse_wizard_meal_response,
    build_wizard_meal_prompt,
    _DISH_CATEGORIES,
    _MULTI_DISH_SLOTS,
)
from data_helpers import slot_dishes  # noqa: E402


def _first_dish(entry):
    """First dish of a slot entry via the read-time migration helper, {} if none."""
    _d = slot_dishes(entry)
    return _d[0] if _d else {}


_failures = []


def check(label, cond):
    if cond:
        print("PASS " + label)
    else:
        print("FAIL " + label)
        _failures.append(label)


# ── wizard_target_slot_keys ──────────────────────────────────────────────────
_session = {
    "planning_window": {"start_iso": "2026-06-29", "end_iso": "2026-07-01"},
    "confirmed_what_to_plan": ["dinner", "breakfast"],
    "confirmed_meals": {"2026-06-29::dinner": {"name": "Roast chicken", "locked": True}},
}
_keys = wizard_target_slot_keys(_session)
_expected = [
    "2026-06-29::breakfast",
    "2026-06-30::breakfast",
    "2026-06-30::dinner",
    "2026-07-01::breakfast",
    "2026-07-01::dinner",
]
check("confirmed slot excluded", "2026-06-29::dinner" not in _keys)
check("5 remaining keys (3 days x 2 slots - 1 confirmed)", len(_keys) == 5)
check("exact expected keys", _keys == _expected)
check("result is sorted", _keys == sorted(_keys))
check("missing window -> []", wizard_target_slot_keys({
    "confirmed_what_to_plan": ["dinner"]}) == [])
check("missing slots -> []", wizard_target_slot_keys({
    "planning_window": {"start_iso": "2026-06-29", "end_iso": "2026-07-01"}}) == [])
check("inverted window (end<start) -> []", wizard_target_slot_keys({
    "planning_window": {"start_iso": "2026-07-01", "end_iso": "2026-06-29"},
    "confirmed_what_to_plan": ["dinner"]}) == [])
check("bad date -> []", wizard_target_slot_keys({
    "planning_window": {"start_iso": "nope", "end_iso": "2026-06-29"},
    "confirmed_what_to_plan": ["dinner"]}) == [])

# ── _DISH_CATEGORIES / _MULTI_DISH_SLOTS sanity ──────────────────────────────
check("_DISH_CATEGORIES is a tuple or frozenset", isinstance(_DISH_CATEGORIES, (tuple, frozenset)))
check("'main' in _DISH_CATEGORIES", "main" in _DISH_CATEGORIES)
check("'side' in _DISH_CATEGORIES", "side" in _DISH_CATEGORIES)
check("'snack' in _DISH_CATEGORIES", "snack" in _DISH_CATEGORIES)
check("'dinner' in _MULTI_DISH_SLOTS", "dinner" in _MULTI_DISH_SLOTS)
check("'feast_meal' in _MULTI_DISH_SLOTS", "feast_meal" in _MULTI_DISH_SLOTS)
check("'breakfast' NOT in _MULTI_DISH_SLOTS", "breakfast" not in _MULTI_DISH_SLOTS)

# ── parse_wizard_meal_response — dishes[] schema ─────────────────────────────
_target = _expected  # the 5 empties from the target-keys test above

# Primary fixture: fenced JSON, dishes[] schema.
_fenced = """Here is the week:
```json
{
  "meals": {
    "2026-06-30": {
      "dinner": {
        "dishes": [
          {"category": "main", "name": "Lentil soup",
           "protein": "lentils", "ingredients": "lentils, carrots, broth"}
        ],
        "note": "batch"
      },
      "breakfast": {
        "dishes": [
          {"category": "main", "name": "Oatmeal",
           "protein": "", "ingredients": "oats, milk"}
        ]
      }
    },
    "2026-06-29": {
      "dinner": {
        "dishes": [
          {"category": "main", "name": "SHOULD NOT APPEAR already confirmed"}
        ]
      }
    },
    "2026-08-15": {
      "dinner": {
        "dishes": [
          {"category": "main", "name": "SHOULD NOT APPEAR out of window"}
        ]
      }
    }
  }
}
```
Enjoy!"""
_out = parse_wizard_meal_response(_fenced, _target)
check("only target keys present", set(_out.keys()) <= set(_target))
check("confirmed key absent", "2026-06-29::dinner" not in _out)
check("out-of-window date absent", "2026-08-15::dinner" not in _out)
_e = _out.get("2026-06-30::dinner", {})
_ed = _first_dish(_e)
check("target dinner mapped (dishes[0].name)", _ed.get("name") == "Lentil soup")
check("entry has dishes list", isinstance(_e.get("dishes"), list) and len(_e["dishes"]) == 1)
check("dish category main", _ed.get("category") == "main")
check("no flat name key on entry", "name" not in _e)
check("entry source lorenzo", _e.get("source") == "lorenzo")
check("entry recipe_on_request True", _e.get("recipe_on_request") is True)
check("entry recipe_id empty", _e.get("recipe_id") == "")
check("entry skip_shopping False", _e.get("skip_shopping") is False)
check("dish protein captured", _ed.get("protein") == "lentils")
check("dish ingredients captured", _ed.get("ingredients") == "lentils, carrots, broth")
check("entry note captured (top-level)", _e.get("note") == "batch")

# Trailing-comma JSON still parses (dishes[] schema).
_tc = """```json
{"meals": {"2026-06-30": {"dinner": {"dishes": [{"category": "main", "name": "Chili",}],},}}}
```"""
check("trailing-comma JSON parses", bool(parse_wizard_meal_response(_tc, _target)))

# Garbage -> {}.
check("garbage -> {}", parse_wizard_meal_response("no json here at all", _target) == {})
check("empty string -> {}", parse_wizard_meal_response("", _target) == {})

# Bare {date:{slot:...}} wrapper (no "meals" key) — outer structure compat.
_bare = (
    '{"2026-06-30": {"dinner": {"dishes": ['
    '{"category": "main", "name": "Tacos", "protein": "beef"}]}}}'
)
_bo = parse_wizard_meal_response(_bare, _target)
check("bare wrapper maps", _first_dish(_bo.get("2026-06-30::dinner", {})).get("name") == "Tacos")

# Slot with no 'dishes' key (old flat shape) → no valid dishes → slot dropped.
_old_flat = '{"meals": {"2026-06-30": {"dinner": {"name": "Grilled cheese", "protein": ""}}}}'
_fo = parse_wizard_meal_response(_old_flat, _target)
check("old flat shape (no dishes key) -> slot dropped", "2026-06-30::dinner" not in _fo)

# Bare-string slot value → no valid dishes → slot dropped.
_str_slot = '{"meals": {"2026-06-30": {"dinner": "Grilled cheese"}}}'
_so = parse_wizard_meal_response(_str_slot, _target)
check("bare-string slot value -> slot dropped", "2026-06-30::dinner" not in _so)

# Empty target -> nothing maps.
check("empty target -> {}", parse_wizard_meal_response(_fenced, []) == {})

# ── G1c-3a: truncation and drop behavior ─────────────────────────────────────
print("")
print("--- G1c-3a truncation and drop tests ---")

# Fixture: breakfast slot (non-multi) with 3 dishes.
#   dish 1: category "main",  name "Oatmeal"   → valid
#   dish 2: category "fried", name "Eggs"       → INVALID category → dropped
#   dish 3: category "side",  name "Fruit bowl" → valid but non-multi cap fires
# Expected: exactly 1 dish, "Oatmeal" only (first valid; cap stops there).
_trunc_target = ["2026-06-30::breakfast"]
_trunc_raw = (
    '{"meals": {"2026-06-30": {"breakfast": {"dishes": ['
    '{"category": "main",  "name": "Oatmeal"},'
    '{"category": "fried", "name": "Eggs"},'
    '{"category": "side",  "name": "Fruit bowl"}'
    ']}}}}'
)
_trunc_out = parse_wizard_meal_response(_trunc_raw, _trunc_target)
_trunc_entry = _trunc_out.get("2026-06-30::breakfast", {})
_trunc_dishes = _trunc_entry.get("dishes", [])
check("truncation: breakfast slot present in output", "2026-06-30::breakfast" in _trunc_out)
check("truncation: exactly 1 dish kept (single-dish cap)", len(_trunc_dishes) == 1)
check("truncation: first valid dish kept (Oatmeal)", _trunc_dishes[0].get("name") == "Oatmeal" if _trunc_dishes else False)
check("truncation: 'main' category retained", _trunc_dishes[0].get("category") == "main" if _trunc_dishes else False)
check("truncation: invalid 'fried' dish not present", not any(d.get("name") == "Eggs" for d in _trunc_dishes))
check("truncation: 'Fruit bowl' not present (truncated, not just invalid)", not any(d.get("name") == "Fruit bowl" for d in _trunc_dishes))

# Fixture: dinner slot (multi) with 1 dish whose category is invalid.
# Expected: zero valid dishes → slot dropped entirely.
_drop_target = ["2026-06-30::dinner"]
_drop_raw = (
    '{"meals": {"2026-06-30": {"dinner": {"dishes": ['
    '{"category": "badcategory", "name": "Mystery meat"}'
    ']}}}}'
)
_drop_out = parse_wizard_meal_response(_drop_raw, _drop_target)
check("drop: dinner slot with all-invalid categories → slot absent", "2026-06-30::dinner" not in _drop_out)

# Fixture: dinner slot (multi) with valid dishes — confirm multi-dish is NOT truncated.
_multi_target = ["2026-06-30::dinner"]
_multi_raw = (
    '{"meals": {"2026-06-30": {"dinner": {"dishes": ['
    '{"category": "main", "name": "Roast chicken", "protein": "chicken"},'
    '{"category": "side", "name": "Green beans", "protein": ""},'
    '{"category": "side", "name": "Rice", "protein": ""}'
    ']}}}}'
)
_multi_out = parse_wizard_meal_response(_multi_raw, _multi_target)
_multi_dishes = _multi_out.get("2026-06-30::dinner", {}).get("dishes", [])
check("multi-dish: dinner keeps all 3 valid dishes", len(_multi_dishes) == 3)
check("multi-dish: main dish present", any(d.get("name") == "Roast chicken" for d in _multi_dishes))
check("multi-dish: both sides present", sum(1 for d in _multi_dishes if d.get("category") == "side") == 2)

# Fixture: dinner slot (multi) with mixed valid/invalid — invalid dropped, valid kept.
_mixed_target = ["2026-06-30::dinner"]
_mixed_raw = (
    '{"meals": {"2026-06-30": {"dinner": {"dishes": ['
    '{"category": "main",   "name": "Salmon", "protein": "salmon"},'
    '{"category": "INVALID","name": "Bad dish"},'
    '{"category": "side",   "name": "Salad greens"}'
    ']}}}}'
)
_mixed_out = parse_wizard_meal_response(_mixed_raw, _mixed_target)
_mixed_dishes = _mixed_out.get("2026-06-30::dinner", {}).get("dishes", [])
check("mixed multi: 2 valid dishes kept (1 invalid dropped)", len(_mixed_dishes) == 2)
check("mixed multi: invalid dish absent", not any(d.get("name") == "Bad dish" for d in _mixed_dishes))
check("mixed multi: 'Salmon' present", any(d.get("name") == "Salmon" for d in _mixed_dishes))

# ── build_wizard_meal_prompt (G1c-1b / G1c-3a smoke — offline, no network) ───
print("")
print("--- build_wizard_meal_prompt tests ---")

_p_session = {
    "planning_window": {"start_iso": "2026-06-29", "end_iso": "2026-07-02"},
    "confirmed_what_to_plan": ["dinner", "breakfast"],
    "use_soon_items": "old bananas",
    "confirmed_inventory": "green beans (canned)",
    "used_proteins": ["chicken"],
    "confirmed_complexity": "simple",
    # Migration fixture: an OLD flat-shaped confirmed entry (no 'dishes' key).
    # build_wizard_meal_prompt must read its name via the read-time migration.
    "confirmed_meals": {
        "2026-06-29::dinner": {"name": "Leftover Migrated Stew",
                               "protein": "beef", "locked": True},
    },
}
_p_targets = wizard_target_slot_keys(_p_session)
_prompt = build_wizard_meal_prompt(_p_session, _p_targets)
check("prompt is a non-empty string", isinstance(_prompt, str) and bool(_prompt))
for _d in ("2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02"):
    check("prompt contains target date " + _d, _d in _prompt)
check("prompt contains slot word 'dinner'", "dinner" in _prompt)
check("prompt contains slot word 'breakfast'", "breakfast" in _prompt)
check("prompt contains use-soon 'old bananas'", "old bananas" in _prompt)
check("prompt notes the form 'canned'", "canned" in _prompt)
check("prompt lists used protein 'chicken'", "chicken" in _prompt)
check("prompt contains complexity word 'simple'", "simple" in _prompt)
check("prompt contains dishes[] output schema",
      '"dishes"' in _prompt)
check("prompt contains JSON output-contract outer shape",
      '{"meals": {"YYYY-MM-DD": {"slot":' in _prompt)
check("prompt forbids extra cells",
      "Do not add any day or meal type" in _prompt)
check("prompt protects confirmed meals",
      "ALREADY decided" in _prompt)
check("prompt migrates OLD flat confirmed entry name (read-time migration)",
      "Leftover Migrated Stew" in _prompt)
check("prompt lists valid categories from _DISH_CATEGORIES",
      all(c in _prompt for c in _DISH_CATEGORIES))
check("prompt mentions multi-dish dinner rule",
      "multi" in _prompt.lower() and "dinner" in _prompt)
check("prompt mentions single-dish rule for non-dinner",
      "single" in _prompt.lower())
check("prompt annotates dinner target as multi-dish",
      "multi-dish" in _prompt)
check("prompt annotates breakfast target as single-dish",
      "single dish" in _prompt)

print("")
if _failures:
    print("FAILURES: " + str(len(_failures)))
    sys.exit(1)
print("PASS all G1c-1a / G1c-3a generation-contract checks passed")
