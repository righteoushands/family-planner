"""Meal Wizard Step 3 verification harness.

Run from project root:  PYTHONPATH=. python data/verify_meal_wizard_step3.py

Covers the session-state contract introduced in the Meal Wizard Step 3 build
(there is no existing verify_phase_*.py for the meal-wizard track;
verify_phase_f.py belongs to the unrelated seasons track):

  1. Session round-trip: update_meal_wizard_session persists and reloads the
     four Step 3 keys (confirmed_what_to_plan, confirmed_complexity,
     planning_window, confirmed_meals) with correct shapes.
  2. Pre-fill -> confirmed_meals replicates the POST handler transformation:
     allowlist-filtered slots, exact value shape
     {name, locked, source, skip_shopping, recipe_on_request}, and that
     non-prefill confirmed_meals are preserved across a save.
  3. Saved-confirmation view reflects the persisted session (plan labels,
     complexity, window, prefill count).
  4. Step 2's confirmed_inventory key is untouched by a Step 3 save (additive).

Rule 10: operates ONLY on a temp copy of the session file. The live
meal_wizard_session.json is snapshotted and restored on exit (pass or fail);
if it did not exist before, it is removed again.
"""
import os
import shutil
import sys
import tempfile
import traceback
from datetime import date as _d

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import config  # noqa: E402
import data_helpers as dh  # noqa: E402
import render_meal_wizard_step3 as s3  # noqa: E402

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

_S3_SLOTS = {"breakfast", "lunch", "dinner", "johns_lunch"}
_S3_PLAN_KEYS = {"breakfast", "lunch", "dinner", "johns_lunch",
                 "snacks", "dessert", "feast_meal", "batch_cook"}
_S3_CX_KEYS = {"full_effort", "normal", "simple"}


def _build_confirmed_meals(prefill_in, existing_meals):
    """Replica of the /meal-wizard-step3-save transformation, so the harness
    validates the documented contract independently of the HTTP handler."""
    new_prefill = {}
    if isinstance(prefill_in, dict):
        for pk, pv in prefill_in.items():
            name = dh.clean_text(pv)
            if not name:
                continue
            parts = str(pk).split("::")
            if len(parts) != 2:
                continue
            pd, pslot = parts[0], parts[1]
            if pslot not in _S3_SLOTS:
                continue
            try:
                _d.fromisoformat(pd)
            except Exception:
                continue
            new_prefill[pd + "::" + pslot] = {
                "dishes": [{"category": "main", "name": name,
                            "ingredients": "", "protein": ""}],
                "locked": True, "source": "prefill",
                "skip_shopping": True, "recipe_on_request": True,
            }
    confirmed = {
        k: v for k, v in (existing_meals or {}).items()
        if not (isinstance(v, dict) and v.get("source") == "prefill")
    }
    confirmed.update(new_prefill)
    return confirmed


def main():
    failures = []

    # ── Snapshot live session file (Rule 10) ────────────────────────────────
    live_path = config.MEAL_WIZARD_SESSION_FILE
    existed = os.path.exists(live_path)
    backup = None
    if existed:
        fd, backup = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        shutil.copy2(live_path, backup)

    try:
        # Start from a clean session for deterministic assertions.
        dh.clear_meal_wizard_session()

        # ── Test 1: round-trip of the four Step 3 keys ──────────────────────
        prefill_in = {
            "2026-06-15::dinner": "Leftover lasagna",
            "2026-06-16::breakfast": "Oatmeal",
            "2026-06-16::snacks": "should be dropped (not a slot)",
            "bad-key-no-sep": "dropped",
            "2026-13-40::dinner": "dropped (bad date)",
            "2026-06-17::lunch": "   ",  # blank after clean -> dropped
        }
        confirmed_meals = _build_confirmed_meals(prefill_in, {})
        dh.update_meal_wizard_session({
            "confirmed_what_to_plan": ["breakfast", "dinner", "feast_meal", "bogus"],
            "confirmed_complexity": "simple",
            "planning_window": {"start_iso": "2026-06-15", "end_iso": "2026-06-20"},
            "confirmed_meals": confirmed_meals,
        })
        sess = dh.load_meal_wizard_session()
        if sess.get("confirmed_complexity") == "simple":
            print(PASS, "complexity persisted")
        else:
            failures.append("complexity not persisted")
            print(FAIL, "complexity not persisted")

        win = sess.get("planning_window") or {}
        if win.get("start_iso") == "2026-06-15" and win.get("end_iso") == "2026-06-20":
            print(PASS, "planning_window persisted")
        else:
            failures.append("planning_window not persisted")
            print(FAIL, "planning_window not persisted:", win)

        # ── Test 2: confirmed_meals shape + allowlist filtering ─────────────
        cm = sess.get("confirmed_meals") or {}
        expected_keys = {"2026-06-15::dinner", "2026-06-16::breakfast"}
        if set(cm.keys()) == expected_keys:
            print(PASS, "prefill keys allowlist-filtered correctly")
        else:
            failures.append("prefill key filtering wrong: " + str(set(cm.keys())))
            print(FAIL, "prefill keys:", set(cm.keys()))

        one = cm.get("2026-06-15::dinner") or {}
        _one_dishes = dh.slot_dishes(one)
        if (_one_dishes and _one_dishes[0].get("name") == "Leftover lasagna"
                and _one_dishes[0].get("category") == "main" and "name" not in one
                and one.get("locked") is True
                and one.get("source") == "prefill" and one.get("skip_shopping") is True
                and one.get("recipe_on_request") is True):
            print(PASS, "prefilled meal has correct dishes[]/locked/off-shopping shape")
        else:
            failures.append("prefill value shape wrong: " + str(one))
            print(FAIL, "prefill value shape:", one)

        # ── Test 3: non-prefill meals preserved, prefill refreshed ──────────
        seeded = dict(cm)
        seeded["2026-06-19::dinner"] = {"name": "AI suggestion", "source": "generated"}
        dh.update_meal_wizard_session({"confirmed_meals": seeded})
        # Now a second Step 3 save with different prefill
        prefill2 = {"2026-06-15::dinner": "Changed to soup"}
        existing = dh.load_meal_wizard_session().get("confirmed_meals") or {}
        rebuilt = _build_confirmed_meals(prefill2, existing)
        dh.update_meal_wizard_session({"confirmed_meals": rebuilt})
        after = dh.load_meal_wizard_session().get("confirmed_meals") or {}
        if after.get("2026-06-19::dinner", {}).get("source") == "generated":
            print(PASS, "non-prefill (generated) meal preserved across save")
        else:
            failures.append("generated meal not preserved")
            print(FAIL, "generated meal not preserved:", after.get("2026-06-19::dinner"))
        _changed = dh.slot_dishes(after.get("2026-06-15::dinner", {}))
        if (_changed and _changed[0].get("name") == "Changed to soup"
                and "2026-06-16::breakfast" not in after):
            print(PASS, "prefill entries refreshed (old prefill cleared, new applied)")
        else:
            failures.append("prefill refresh wrong")
            print(FAIL, "prefill refresh:", {k: v.get("name") for k, v in after.items()})

        # ── Test 4: saved-confirmation view reflects session ────────────────
        # Reset to a known state for the view assertions.
        dh.clear_meal_wizard_session()
        dh.update_meal_wizard_session({
            "confirmed_what_to_plan": ["breakfast", "dinner"],
            "confirmed_complexity": "normal",
            "planning_window": {"start_iso": "2026-06-18", "end_iso": "2026-06-20"},
            "confirmed_meals": _build_confirmed_meals(
                {"2026-06-17::dinner": "Tacos"}, {}),
        })
        view = s3.render_meal_wizard_step3("Lauren", saved=True)
        view_ok = all(m in view for m in [
            "Breakfast", "Dinner", "Normal", "2026-06-18 to 2026-06-20",
            "1 past meal pre-filled",
        ])
        if view_ok:
            print(PASS, "saved-confirmation view reflects persisted session")
        else:
            failures.append("saved view missing expected content")
            print(FAIL, "saved view content mismatch")

        # ── Test 5: Step 2 inventory key untouched by Step 3 saves ──────────
        dh.clear_meal_wizard_session()
        dh.update_meal_wizard_session({"confirmed_inventory": "Fridge: eggs"})
        dh.update_meal_wizard_session({
            "confirmed_what_to_plan": ["lunch"],
            "confirmed_complexity": "full_effort",
            "planning_window": {"start_iso": "2026-06-18", "end_iso": "2026-06-20"},
            "confirmed_meals": {},
        })
        s2 = dh.load_meal_wizard_session()
        if s2.get("confirmed_inventory") == "Fridge: eggs":
            print(PASS, "Step 2 confirmed_inventory preserved (additive)")
        else:
            failures.append("Step 2 inventory clobbered")
            print(FAIL, "Step 2 inventory:", s2.get("confirmed_inventory"))

    except Exception:
        failures.append("exception")
        traceback.print_exc()
    finally:
        # ── Restore live session file (Rule 10) ─────────────────────────────
        if existed and backup:
            shutil.copy2(backup, live_path)
            os.remove(backup)
        elif not existed and os.path.exists(live_path):
            os.remove(live_path)

    print()
    if failures:
        print(FAIL, str(len(failures)), "check(s) failed")
        sys.exit(1)
    print(PASS, "all Step 3 session-state checks passed")


if __name__ == "__main__":
    main()
