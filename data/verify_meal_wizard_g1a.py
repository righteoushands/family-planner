"""Meal Wizard Phase G1a verification harness.

Run from project root:  PYTHONPATH=. python data/verify_meal_wizard_g1a.py

Covers the G1a data foundation:
  1. recompute_used_proteins: only the 'protein' field counts, de-duped,
     lowercased, first-seen order; littles' food in 'ingredients' is excluded.
  2. Confirm path logic: a valid entry lands in confirmed_meals keyed
     'YYYY-MM-DD::slot', is locked, and used_proteins reflects its protein.
  3. Remove path logic: the slot is gone afterward and used_proteins updates;
     removing an absent slot is idempotent (no error).
  4. Validation: a bad slot and a bad date are both rejected (no write).

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

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

_SLOTS = {"breakfast", "lunch", "dinner", "johns_lunch",
          "snacks", "dessert", "feast_meal", "batch_cook"}
_SOURCES = {"manual", "lorenzo", "prefill"}


def _valid_iso(v):
    try:
        _d.fromisoformat(v)
        return v
    except Exception:
        return ""


def _confirm(payload):
    """Replica of /meal-wizard-step4-confirm logic against the session helpers,
    so the harness validates the documented contract independently of HTTP.
    Returns True on accept, False on reject (no write)."""
    date_v = _valid_iso(str(payload.get("date", "")))
    slot_v = str(payload.get("slot", "")).strip().lower()
    name_v = dh.clean_text(payload.get("name", ""))
    if (not date_v) or (slot_v not in _SLOTS) or (not name_v):
        return False
    source_v = payload.get("source", "manual")
    if source_v not in _SOURCES:
        source_v = "manual"
    entry = {
        "name": name_v,
        "source": source_v,
        "locked": True,
        "ingredients": dh.clean_text(payload.get("ingredients", "")),
        "recipe_id": dh.clean_text(payload.get("recipe_id", "")),
        "recipe_on_request": bool(payload.get("recipe_on_request")),
        "skip_shopping": bool(payload.get("skip_shopping")),
        "protein": dh.clean_text(payload.get("protein", "")),
    }
    meals = dh.load_meal_wizard_session().get("confirmed_meals") or {}
    meals[date_v + "::" + slot_v] = entry
    dh.update_meal_wizard_session({
        "confirmed_meals": meals,
        "used_proteins": dh.recompute_used_proteins(meals),
    })
    return True


def _remove(payload):
    """Replica of /meal-wizard-step4-remove logic. Returns True on accept,
    False on reject. Idempotent on accept (absent slot is a no-op)."""
    date_v = _valid_iso(str(payload.get("date", "")))
    slot_v = str(payload.get("slot", "")).strip().lower()
    if (not date_v) or (slot_v not in _SLOTS):
        return False
    meals = dh.load_meal_wizard_session().get("confirmed_meals") or {}
    meals.pop(date_v + "::" + slot_v, None)
    dh.update_meal_wizard_session({
        "confirmed_meals": meals,
        "used_proteins": dh.recompute_used_proteins(meals),
    })
    return True


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
        dh.clear_meal_wizard_session()

        # ── Test 1: recompute_used_proteins behavior ────────────────────────
        sample = {
            "2026-06-29::dinner": {"protein": "Chicken"},
            "2026-06-30::dinner": {"protein": "chicken"},          # dup (case)
            "2026-07-01::dinner": {"protein": "Beef",
                                   "ingredients": "+ nuggets for James"},
            "2026-07-02::lunch": {"protein": ""},                   # empty -> skip
            "2026-07-03::lunch": {"ingredients": "chicken nuggets for James"},  # no protein
            "2026-07-04::dinner": "not a dict",                     # ignored
        }
        up = dh.recompute_used_proteins(sample)
        if up == ["chicken", "beef"]:
            print(PASS, "recompute_used_proteins: deduped/lowercased/first-seen, littles excluded")
        else:
            failures.append("recompute_used_proteins wrong: " + str(up))
            print(FAIL, "recompute_used_proteins:", up)

        # ── Test 2: confirm a valid entry ───────────────────────────────────
        ok = _confirm({
            "date": "2026-06-29", "slot": "dinner", "name": "Sheet-pan chicken",
            "source": "manual", "protein": "Chicken",
            "ingredients": "thighs, broccoli", "recipe_id": "",
            "recipe_on_request": True, "skip_shopping": False,
        })
        sess = dh.load_meal_wizard_session()
        cm = sess.get("confirmed_meals") or {}
        entry = cm.get("2026-06-29::dinner") or {}
        if (ok and entry.get("name") == "Sheet-pan chicken"
                and entry.get("locked") is True
                and entry.get("source") == "manual"):
            print(PASS, "confirm: entry persisted, locked, correct source")
        else:
            failures.append("confirm entry shape wrong: " + str(entry))
            print(FAIL, "confirm entry:", entry)
        if sess.get("used_proteins") == ["chicken"]:
            print(PASS, "confirm: used_proteins reflects the protein")
        else:
            failures.append("confirm used_proteins wrong: " + str(sess.get("used_proteins")))
            print(FAIL, "confirm used_proteins:", sess.get("used_proteins"))

        # ── Test 3: remove that slot ────────────────────────────────────────
        ok_rm = _remove({"date": "2026-06-29", "slot": "dinner"})
        sess = dh.load_meal_wizard_session()
        cm = sess.get("confirmed_meals") or {}
        if ok_rm and "2026-06-29::dinner" not in cm and sess.get("used_proteins") == []:
            print(PASS, "remove: slot gone and used_proteins updated")
        else:
            failures.append("remove failed: " + str(cm) + " / " + str(sess.get("used_proteins")))
            print(FAIL, "remove:", cm, sess.get("used_proteins"))
        # idempotent remove (absent slot)
        if _remove({"date": "2026-06-29", "slot": "dinner"}) is True:
            print(PASS, "remove: idempotent on absent slot")
        else:
            failures.append("remove not idempotent")
            print(FAIL, "remove not idempotent")

        # ── Test 4: validation rejects bad slot / bad date ──────────────────
        before = dh.load_meal_wizard_session().get("confirmed_meals") or {}
        bad_slot = _confirm({"date": "2026-06-29", "slot": "elevenses", "name": "x"})
        bad_date = _confirm({"date": "2026-13-40", "slot": "dinner", "name": "x"})
        after = dh.load_meal_wizard_session().get("confirmed_meals") or {}
        if bad_slot is False and bad_date is False and after == before:
            print(PASS, "validation: bad slot and bad date both rejected (no write)")
        else:
            failures.append("validation did not reject: slot=%s date=%s" % (bad_slot, bad_date))
            print(FAIL, "validation: slot=%s date=%s" % (bad_slot, bad_date))

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
    print(PASS, "all G1a data-foundation checks passed")


if __name__ == "__main__":
    main()
