"""Offline harness for render_meal_wizard_gen (G1c-1a).

Pure-logic checks on fixtures only — NO network call, NO live data writes.
Run: python data/verify_meal_wizard_gen.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from render_meal_wizard_gen import (  # noqa: E402
    wizard_target_slot_keys,
    parse_wizard_meal_response,
    build_wizard_meal_prompt,
)

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

# ── parse_wizard_meal_response ───────────────────────────────────────────────
_target = _expected  # the 5 empties from above

_fenced = """Here is the week:
```json
{
  "meals": {
    "2026-06-30": {
      "dinner": {"name": "Lentil soup", "protein": "lentils", "ingredients": "lentils, carrots, broth", "note": "batch"},
      "breakfast": {"name": "Oatmeal"}
    },
    "2026-06-29": {
      "dinner": {"name": "SHOULD NOT APPEAR — already confirmed"}
    },
    "2026-08-15": {
      "dinner": {"name": "SHOULD NOT APPEAR — out of window"}
    }
  }
}
```
Enjoy!"""
_out = parse_wizard_meal_response(_fenced, _target)
check("only target keys present", set(_out.keys()) <= set(_target))
check("confirmed key absent", "2026-06-29::dinner" not in _out)
check("out-of-window date absent", "2026-08-15::dinner" not in _out)
check("target dinner mapped", _out.get("2026-06-30::dinner", {}).get("name") == "Lentil soup")
_e = _out.get("2026-06-30::dinner", {})
check("entry source lorenzo", _e.get("source") == "lorenzo")
check("entry recipe_on_request True", _e.get("recipe_on_request") is True)
check("entry recipe_id empty", _e.get("recipe_id") == "")
check("entry skip_shopping False", _e.get("skip_shopping") is False)
check("entry protein captured", _e.get("protein") == "lentils")
check("entry ingredients captured", _e.get("ingredients") == "lentils, carrots, broth")
check("entry note captured", _e.get("note") == "batch")

# trailing-comma JSON still parses
_tc = """```json
{"meals": {"2026-06-30": {"dinner": {"name": "Chili",},},}}
```"""
check("trailing-comma JSON parses", bool(parse_wizard_meal_response(_tc, _target)))

# garbage -> {}
check("garbage -> {}", parse_wizard_meal_response("no json here at all", _target) == {})
check("empty string -> {}", parse_wizard_meal_response("", _target) == {})

# bare {date:{slot:...}} with no "meals" wrapper
_bare = '{"2026-06-30": {"dinner": {"name": "Tacos", "protein": "beef"}}}'
_bo = parse_wizard_meal_response(_bare, _target)
check("bare wrapper maps", _bo.get("2026-06-30::dinner", {}).get("name") == "Tacos")

# bare string slot value -> name only
_str = '{"meals": {"2026-06-30": {"dinner": "Grilled cheese"}}}'
_so = parse_wizard_meal_response(_str, _target)
check("bare-string value -> name", _so.get("2026-06-30::dinner", {}).get("name") == "Grilled cheese")
check("bare-string value -> empty protein", _so.get("2026-06-30::dinner", {}).get("protein") == "")

# empty target -> nothing maps
check("empty target -> {}", parse_wizard_meal_response(_fenced, []) == {})

# ── build_wizard_meal_prompt (G1c-1b smoke — offline, no network) ─────────────
_p_session = {
    "planning_window": {"start_iso": "2026-06-29", "end_iso": "2026-07-02"},
    "confirmed_what_to_plan": ["dinner"],
    "use_soon_items": "old bananas",
    "confirmed_inventory": "green beans (canned)",
    "used_proteins": ["chicken"],
    "confirmed_complexity": "simple",
    "confirmed_meals": {},
}
_p_targets = wizard_target_slot_keys(_p_session)
_prompt = build_wizard_meal_prompt(_p_session, _p_targets)
check("prompt is a non-empty string", isinstance(_prompt, str) and bool(_prompt))
for _d in ("2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02"):
    check("prompt contains target date " + _d, _d in _prompt)
check("prompt contains slot word 'dinner'", "dinner" in _prompt)
check("prompt contains use-soon 'old bananas'", "old bananas" in _prompt)
check("prompt notes the form 'canned'", "canned" in _prompt)
check("prompt lists used protein 'chicken'", "chicken" in _prompt)
check("prompt contains complexity word 'simple'", "simple" in _prompt)
check("prompt contains JSON output-contract shape",
      '{"meals": {"YYYY-MM-DD": {"slot":' in _prompt)
check("prompt forbids extra cells",
      "Do not add any day or meal type" in _prompt)
check("prompt protects confirmed meals",
      "ALREADY decided" in _prompt)

print("")
if _failures:
    print("FAILURES: " + str(len(_failures)))
    sys.exit(1)
print("PASS all G1c-1a generation-contract checks passed")
