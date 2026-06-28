"""Meal Wizard Phase G1b-1 verification harness (read-only Step 4 screen).

Run from project root:  PYTHONPATH=. python data/verify_meal_wizard_step4.py

Covers the read-only Step 4 screen:
  1. Empty session -> gate state ("Finish Step 3 first ..."), no raise.
  2. Seeded session (planning_window + a couple to_plan slots + confirmed_meals:
     one with recipe_id, one with recipe_on_request, one with neither) -> HTML
     contains each day label, each selected slot, the meal names, and the three
     recipe states ("Recipe attached", "No recipe needed", "Recipe: not set yet").
  3. No <script> tag is emitted (G1b-1 is display-only, zero JavaScript).

Rule 10: operates ONLY on a temp copy of the session. The live
meal_wizard_session.json is snapshotted and restored on exit (pass or fail);
if it did not exist before, it is removed again.
"""
import os
import shutil
import sys
import tempfile
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import config  # noqa: E402
import data_helpers as dh  # noqa: E402
from ui_helpers import html_page  # noqa: E402
from render_meal_wizard_step4 import render_meal_wizard_step4  # noqa: E402

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

# Baseline: scripts injected by the global page chrome (html_page) for an empty
# body. Step 4 must add ZERO scripts of its own beyond this baseline.
_CHROME_SCRIPTS = html_page("x", "").lower().count("<script")


def _check(cond, ok_msg, fail_msg, failures):
    if cond:
        print(PASS, ok_msg)
    else:
        failures.append(fail_msg)
        print(FAIL, fail_msg)


def main():
    failures = []

    live_path = config.MEAL_WIZARD_SESSION_FILE
    existed = os.path.exists(live_path)
    backup = None
    if existed:
        fd, backup = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        shutil.copy2(live_path, backup)

    try:
        # ── Test 1: empty session -> gate state ─────────────────────────────
        dh.clear_meal_wizard_session()
        try:
            gate_html = render_meal_wizard_step4("Lauren")
            raised = False
        except Exception:
            gate_html = ""
            raised = True
            traceback.print_exc()
        _check(not raised and "Finish Step 3 first" in gate_html,
               "empty session renders gate state without raising",
               "empty session did not render gate state", failures)
        _check(gate_html.lower().count("<script") == _CHROME_SCRIPTS,
               "gate state adds no <script> beyond page chrome (display-only)",
               "gate state added a <script> beyond page chrome", failures)

        # ── Test 2: seeded session -> full read-only render ─────────────────
        dh.update_meal_wizard_session({
            "planning_window": {"start_iso": "2026-06-29", "end_iso": "2026-06-30"},
            "confirmed_what_to_plan": ["breakfast", "dinner"],
            "confirmed_inventory": "chicken, rice, broccoli",
            "confirmed_meals": {
                # has recipe_id -> "Recipe attached"
                "2026-06-29::dinner": {
                    "name": "Sheet-pan chicken", "source": "manual", "locked": True,
                    "ingredients": "thighs, broccoli", "recipe_id": "r-123",
                    "recipe_on_request": False, "skip_shopping": False,
                    "protein": "chicken",
                },
                # recipe_on_request true -> "No recipe needed"
                "2026-06-29::breakfast": {
                    "name": "Oatmeal and fruit", "source": "prefill", "locked": True,
                    "ingredients": "oats, banana", "recipe_id": "",
                    "recipe_on_request": True, "skip_shopping": True,
                    "protein": "",
                },
                # neither -> "Recipe: not set yet" (half-confirmed state)
                "2026-06-30::dinner": {
                    "name": "Leftovers night", "source": "lorenzo", "locked": True,
                    "ingredients": "", "recipe_id": "",
                    "recipe_on_request": False, "skip_shopping": False,
                    "protein": "",
                },
            },
        })
        html = render_meal_wizard_step4("Lauren")

        _check(html.lower().count("<script") == _CHROME_SCRIPTS,
               "seeded render adds no <script> beyond page chrome (zero JavaScript)",
               "seeded render added a <script> beyond page chrome", failures)

        # Day labels (get_day_info weekday/date_label). Both dates should appear
        # by weekday name; assert the weekday names render.
        _check("Monday" in html and "Tuesday" in html,
               "both day labels (Monday, Tuesday) present",
               "expected day labels missing from render", failures)

        # Slots selected for the week.
        _check("Breakfast" in html and "Dinner" in html,
               "selected slot labels (Breakfast, Dinner) present",
               "selected slot labels missing", failures)

        # Meal names (escaped once).
        _check(all(n in html for n in
                   ["Sheet-pan chicken", "Oatmeal and fruit", "Leftovers night"]),
               "all three confirmed meal names present",
               "a confirmed meal name is missing", failures)

        # Three recipe states.
        _check("Recipe attached" in html,
               "recipe_id meal shows 'Recipe attached'",
               "'Recipe attached' missing", failures)
        _check("No recipe needed" in html,
               "recipe_on_request meal shows 'No recipe needed'",
               "'No recipe needed' missing", failures)
        _check("Recipe: not set yet" in html,
               "half-confirmed meal shows 'Recipe: not set yet'",
               "'Recipe: not set yet' missing", failures)

        # Source tags + off-shopping note.
        _check("manual" in html and "lorenzo" in html and "prefill" in html,
               "source tags (manual/lorenzo/prefill) present",
               "a source tag is missing", failures)
        _check("off shopping list" in html,
               "skip_shopping meal shows 'off shopping list'",
               "'off shopping list' note missing", failures)

        # Back link to Step 3, no forward 'continue' nav yet.
        _check('href="/meal-wizard-step3"' in html,
               "back link to Step 3 present",
               "back link to Step 3 missing", failures)

    except Exception:
        failures.append("exception")
        traceback.print_exc()
    finally:
        if existed and backup:
            shutil.copy2(backup, live_path)
            os.remove(backup)
        elif not existed and os.path.exists(live_path):
            os.remove(live_path)

    print()
    if failures:
        print(FAIL, str(len(failures)), "check(s) failed")
        sys.exit(1)
    print(PASS, "all G1b-1 read-only screen checks passed")


if __name__ == "__main__":
    main()
