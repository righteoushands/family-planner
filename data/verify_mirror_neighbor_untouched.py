"""#3 verification: /meal-wizard-step4-confirm mirror write touches ONLY the
target date::slot key in suggested_meals, leaving a neighboring slot's existing
Lorenzo-generated suggestion untouched.

Rule 10/10a: mw_test_isolation is imported FIRST (before config), redirecting the
session file + meal_plan store to private temp locations, and we POST to an
IN-PROCESS server on an ephemeral port -- the live session / store / :5000 are
never touched. The minted auth token is destroyed in finally.
"""
import json
import os
import sys
import traceback
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import mw_test_isolation  # noqa: E402,F401  MUST precede config: sets the override

import config  # noqa: E402,F401
import data_helpers as dh  # noqa: E402
import auth  # noqa: E402

_D1 = "2026-06-29"  # Monday
BASE = None


def _post(path, payload, token):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Cookie", "session=" + token)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read().decode("utf-8", "ignore")


def main():
    global BASE
    mw_test_isolation.assert_isolated()
    BASE, _shutdown_server = mw_test_isolation.start_server()
    token = None
    ok = True
    try:
        token = auth.create_session("lauren")

        # A neighboring slot (D1::lunch) already carries a REAL Lorenzo generation,
        # with source='lorenzo' and full dishes[]. The target slot (D1::dinner) is
        # what Lauren will confirm.
        _neighbor = {
            "dishes": [{"category": "main", "name": "Lorenzo Tuna Melt",
                        "ingredients": "tuna, bread, cheese", "protein": "tuna"}],
            "source": "lorenzo",
        }
        dh.clear_meal_wizard_session()
        dh.update_meal_wizard_session({
            "planning_window": {"start_iso": _D1, "end_iso": _D1},
            "confirmed_what_to_plan": ["lunch", "dinner"],
            "confirmed_meals": {},
            "suggested_meals": {_D1 + "::lunch": _neighbor},
        })

        before = (dh.load_meal_wizard_session().get("suggested_meals") or {})
        neigh_before = before.get(_D1 + "::lunch")
        print("BEFORE suggested_meals[" + _D1 + "::lunch] (neighbor):")
        print("  " + json.dumps(neigh_before, sort_keys=True))
        print("BEFORE suggested_meals[" + _D1 + "::dinner] (target):")
        print("  " + json.dumps(before.get(_D1 + "::dinner"), sort_keys=True))

        # Confirm the TARGET slot only.
        st, raw = _post("/meal-wizard-step4-confirm", {
            "date": _D1, "slot": "dinner",
            "dishes": [{"category": "main", "name": "Chicken Parm",
                        "ingredients": "", "protein": "chicken"}],
            "source": "manual",
        }, token)
        print("\nPOST /meal-wizard-step4-confirm dinner ->", st,
              json.loads(raw).get("ok"))

        after = (dh.load_meal_wizard_session().get("suggested_meals") or {})
        neigh_after = after.get(_D1 + "::lunch")
        print("\nAFTER suggested_meals[" + _D1 + "::lunch] (neighbor):")
        print("  " + json.dumps(neigh_after, sort_keys=True))
        print("AFTER suggested_meals[" + _D1 + "::dinner] (target):")
        print("  " + json.dumps(after.get(_D1 + "::dinner"), sort_keys=True))

        # Assertions.
        neigh_untouched = (neigh_after == neigh_before
                           and neigh_after == _neighbor
                           and (neigh_after or {}).get("source") == "lorenzo")
        target_written = (isinstance(after.get(_D1 + "::dinner"), dict)
                          and dh.slot_dishes(after.get(_D1 + "::dinner"))[0]
                          .get("name") == "Chicken Parm")
        only_expected_keys = set(after.keys()) == {_D1 + "::lunch",
                                                   _D1 + "::dinner"}
        print()
        print("neighbor untouched (byte-identical, source='lorenzo' kept):",
              neigh_untouched)
        print("target written with mirrored dishes[]:", target_written)
        print("suggested_meals keys after == {lunch, dinner} only:",
              only_expected_keys)
        ok = neigh_untouched and target_written and only_expected_keys
    except Exception:
        ok = False
        traceback.print_exc()
    finally:
        if token:
            try: auth.destroy_session(token)
            except Exception: pass
        _shutdown_server()

    print()
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
