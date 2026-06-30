"""Meal Wizard dish-join verification harness (multi-dish slots).

Run from project root:  PYTHONPATH=. python data/verify_meal_wizard_dish_join.py

Pure-logic checks on fixtures only — NO network call, NO live data writes.
Covers render_meals.format_dish_list (collapsing a slot's dishes[] into the one
display string the canonical meal store holds) and the data_helpers.slot_dishes
read-time migration that feeds it.

Display contract:
  - Lead = all 'main' dishes if any, else all 'soup' dishes if any, else none.
  - Rest = every other dish in entry order (lead excluded).
  - Lead names join with ' and '; rest names join as a no-Oxford-comma list
    (0->''; 1->'X'; 2->'X and Y'; 3+->'X, Y and Z').
  - Combined 'lead with rest', or just lead, or just rest, or ''.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from render_meals import format_dish_list  # noqa: E402
from data_helpers import slot_dishes  # noqa: E402

_failures = []


def check(label, cond):
    if cond:
        print("PASS " + label)
    else:
        print("FAIL " + label)
        _failures.append(label)


def _m(n):
    return {"category": "main", "name": n}


def _s(n):
    return {"category": "side", "name": n}


def _soup(n):
    return {"category": "soup", "name": n}


# ── The 8 canonical display cases ────────────────────────────────────────────
_cases = [
    ("single main only",
     [_m("Roast Chicken")],
     "Roast Chicken"),
    ("main + 1 side",
     [_m("Roast Chicken"), _s("Mashed Potatoes")],
     "Roast Chicken with Mashed Potatoes"),
    ("main + 2 sides",
     [_m("Roast Chicken"), _s("Mashed Potatoes"), _s("Green Beans")],
     "Roast Chicken with Mashed Potatoes and Green Beans"),
    ("main + 3 sides (no Oxford comma)",
     [_m("Roast Chicken"), _s("Mashed Potatoes"), _s("Green Beans"), _s("Dinner Rolls")],
     "Roast Chicken with Mashed Potatoes, Green Beans and Dinner Rolls"),
    ("2 mains + 2 sides",
     [_m("Roast Chicken"), _m("Meatloaf"), _s("Mashed Potatoes"), _s("Green Beans")],
     "Roast Chicken and Meatloaf with Mashed Potatoes and Green Beans"),
    ("no main, soup leads",
     [_soup("Tomato Soup"), _s("Salad"), _s("Bread")],
     "Tomato Soup with Salad and Bread"),
    ("no main/soup, 2 dishes (no 'with')",
     [_s("Mashed Potatoes"), _s("Salad")],
     "Mashed Potatoes and Salad"),
    ("no main/soup, single dish",
     [_s("Just This")],
     "Just This"),
]
for _label, _dishes, _expected in _cases:
    _got = format_dish_list(_dishes)
    check("display: " + _label + " -> " + repr(_expected),
          _got == _expected)

# ── Edge cases ───────────────────────────────────────────────────────────────
check("empty dishes -> ''", format_dish_list([]) == "")
check("non-list -> ''", format_dish_list(None) == "")
check("blank names dropped", format_dish_list([_m(""), _s("Salad")]) == "Salad")
check("soup ignored when a main exists (main leads)",
      format_dish_list([_soup("Broth"), _m("Steak")]) == "Steak with Broth")

# ── slot_dishes migration feeding format_dish_list ───────────────────────────
check("old flat entry migrates then joins to its name",
      format_dish_list(slot_dishes(
          {"name": "Leftovers", "ingredients": "x", "protein": "beef"})) == "Leftovers")
check("bare string entry migrates then joins",
      format_dish_list(slot_dishes("Grilled Cheese")) == "Grilled Cheese")
check("new dishes entry passes through join",
      format_dish_list(slot_dishes(
          {"dishes": [_m("Tacos"), _s("Rice")]})) == "Tacos with Rice")

print("")
if _failures:
    print("FAILURES: " + str(len(_failures)))
    sys.exit(1)
print("PASS all dish-join + migration checks passed")
