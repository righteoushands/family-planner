"""Deliberately-BROKEN harness fixture — proves the Rule 10a mechanical check.

Run from project root:  PYTHONPATH=. python data/verify_rule10a_badorder_fixture.py

This file INTENTIONALLY violates Rule 10a: it imports `config` (an app module
that binds a live data path) BEFORE `mw_test_isolation`. The isolation module's
import-time `_enforce_first_project_import()` check must detect that `config` is
already in sys.modules and raise ImportError.

Exit code 0 (PASS) == the check fired as required. Exit code 1 (FAIL) == the bad
import order was allowed through, which would let a real harness touch live data.
This fixture must NEVER be made "compliant"; its whole purpose is to stay broken
so it can prove the guard works.
"""
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

PASS = "\u2705 PASS"
FAIL = "\u274c FAIL"


def main():
    # WRONG ORDER ON PURPOSE: an app module that binds a live path, first.
    import config  # noqa: E402,F401
    try:
        import mw_test_isolation  # noqa: E402,F401
    except ImportError as e:
        msg = str(e)
        if "Rule 10a violation" in msg and "config" in msg:
            print(PASS, "bad import order raised ImportError:", msg)
            return 0
        print(FAIL, "raised ImportError but with an unexpected message:", msg)
        return 1
    except Exception as e:  # noqa: BLE001
        print(FAIL, "raised the wrong exception type:", repr(e))
        traceback.print_exc()
        return 1
    print(FAIL, "mw_test_isolation imported cleanly AFTER config -- the Rule 10a "
                "check did NOT fire (a real harness could touch live data).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
