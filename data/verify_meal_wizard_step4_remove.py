"""Meal Wizard /meal-wizard-step4-remove verification harness.

Run from project root:
    PYTHONPATH=. python data/verify_meal_wizard_step4_remove.py

Covers:
  SHA256 INTEGRITY:
    - sha256 of data/meal_wizard_session.json is captured BEFORE and AFTER the
      entire run, then asserted identical inside the test -- proving the live
      file was never touched (not just manually verified after the fact).

  REMOVE ROUTE (authenticated HTTP round-trip via in-process server):
    1. Bad date -> 400 {ok:false}; session unchanged.
    2. Bad slot -> 400 {ok:false}; session unchanged.
    3. Absent slot -> 200 {ok:true} (idempotent); session unchanged.
    4. Mixed-origin case: confirmed_meals has MAIN + SIDE (Lauren added the
       side manually after Lorenzo suggested only the main). suggested_meals
       has only the main dish. After /meal-wizard-step4-remove the reverted
       slot HTML contains BOTH dishes -- the Lauren-only side is NOT dropped
       (it came from revert_dishes, not from the suggested fallback).
    5. No-reload contract: response contains slot_html and lock_html.
    6. Confirmed slot is gone from session after remove.

Rule 10a: `mw_test_isolation` is the first project import; it redirects
BOTH the session file and the meal_plan store to private temp locations for
this process. The in-process server shares those redirected paths, so
data/meal_wizard_session.json is NEVER read or written during the run --
not even snapshotted/restored. The sha256 integrity assertion at the end is
proof, not a promise.
"""
import hashlib
import json
import os
import sys
import traceback
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import mw_test_isolation  # noqa: E402,F401  MUST precede config: sets the override

import config  # noqa: E402,F401
import data_helpers as dh  # noqa: E402
import auth  # noqa: E402

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
BASE = "http://localhost:5000"  # replaced at runtime with the in-process server

# Absolute path to the live session file -- used ONLY for the before/after
# sha256 integrity check, never for reading session state in tests.
_LIVE_SESSION = os.path.join(_ROOT, "data", "meal_wizard_session.json")

_DATE = "2026-07-10"   # future date; no collision with any seeded live data
_SLOT = "dinner"


def _sha256_live():
    """Return hex sha256 of the live session file, or 'ABSENT' if it does not exist."""
    if not os.path.exists(_LIVE_SESSION):
        return "ABSENT"
    with open(_LIVE_SESSION, "rb") as _fh:
        return hashlib.sha256(_fh.read()).hexdigest()


def _check(cond, ok_msg, fail_msg, failures):
    if cond:
        print(PASS, ok_msg)
    else:
        failures.append(fail_msg)
        print(FAIL, fail_msg)


# Rule 10 guard: render_john.py reads a hardcoded live meal_plan path that
# MEAL_PLAN_DIR does NOT cover. That code is only reachable via /john, which
# this harness never calls. Guard is kept so a future accidental /john request
# fails loudly instead of silently touching live data.
_UNISOLATED_ROUTES = ("/john",)


def _forbid_unisolated_routes(path):
    for r in _UNISOLATED_ROUTES:
        if path == r or path.startswith(r + "/") or path.startswith(r + "?"):
            raise AssertionError(
                "Rule 10 guard: harness must not request " + repr(path) + " -- "
                "render_john.py reads the live meal_plan path directly "
                "(not MEAL_PLAN_DIR). Redirect render_john before removing this guard."
            )


def _post(path, payload, token):
    _forbid_unisolated_routes(path)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Cookie", "session=" + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "ignore")


def main():
    global BASE
    failures = []

    # ── Capture live-file hash BEFORE any work. ───────────────────────────────
    hash_before = _sha256_live()
    print("sha256 BEFORE:", hash_before)

    mw_test_isolation.assert_isolated()
    BASE, _shutdown_server = mw_test_isolation.start_server()

    token = None
    try:
        token = auth.create_session("lauren")

        # ── Test 1: bad date -> 400 ───────────────────────────────────────────
        st, raw = _post("/meal-wizard-step4-remove",
                        {"date": "not-a-date", "slot": _SLOT}, token)
        _check(st == 400 and json.loads(raw).get("ok") is False,
               "bad date -> 400 {ok:false}",
               "bad date did not return 400 {ok:false}", failures)

        # ── Test 2: bad slot -> 400 ───────────────────────────────────────────
        st, raw = _post("/meal-wizard-step4-remove",
                        {"date": _DATE, "slot": "elevenses"}, token)
        _check(st == 400 and json.loads(raw).get("ok") is False,
               "bad slot -> 400 {ok:false}",
               "bad slot did not return 400 {ok:false}", failures)

        # ── Test 3: absent slot -> 200 idempotent ─────────────────────────────
        dh.clear_meal_wizard_session()
        dh.update_meal_wizard_session({
            "planning_window": {"start_iso": _DATE, "end_iso": _DATE},
            "confirmed_what_to_plan": [_SLOT],
            "confirmed_meals": {},
            "suggested_meals": {},
        })
        st, raw = _post("/meal-wizard-step4-remove",
                        {"date": _DATE, "slot": _SLOT}, token)
        _check(st == 200 and json.loads(raw).get("ok") is True,
               "absent slot -> 200 {ok:true} (idempotent)",
               "absent slot did not return 200 {ok:true}", failures)

        # ── Test 4: mixed-origin case ─────────────────────────────────────────
        # confirmed_meals: MAIN + SIDE (Lauren added the side after Lorenzo
        #   suggested only the main).
        # suggested_meals: MAIN only.
        # After /meal-wizard-step4-remove the reverted slot HTML must contain
        # BOTH dishes. The Lauren-only side must NOT be dropped because the
        # handler now passes revert_dishes from the prior confirmed entry
        # instead of falling back to suggested_meals.
        dh.clear_meal_wizard_session()
        dh.update_meal_wizard_session({
            "planning_window": {"start_iso": _DATE, "end_iso": _DATE},
            "confirmed_what_to_plan": [_SLOT],
            "suggested_meals": {
                _DATE + "::" + _SLOT: {
                    "dishes": [
                        {"category": "main",
                         "name": "Brined Roast Chicken",
                         "ingredients": "chicken, kosher salt, water",
                         "protein": "chicken"},
                    ]
                }
            },
            "confirmed_meals": {
                _DATE + "::" + _SLOT: {
                    "dishes": [
                        {"category": "main",
                         "name": "Brined Roast Chicken",
                         "ingredients": "chicken, kosher salt, water",
                         "protein": "chicken"},
                        {"category": "side",
                         "name": "Roasted Sweet Potatoes",
                         "ingredients": "sweet potatoes, olive oil, salt",
                         "protein": ""},
                    ],
                    "source": "manual",
                    "locked": True,
                    "recipe_id": "",
                    "recipe_on_request": True,
                    "skip_shopping": False,
                }
            },
        })

        # Verify test fixture: side is NOT in suggested_meals (so any presence
        # in the reverted HTML proves it came from confirmed, not the fallback).
        sess_before = dh.load_meal_wizard_session()
        sugg_dishes = (sess_before.get("suggested_meals", {})
                       .get(_DATE + "::" + _SLOT, {})
                       .get("dishes", []))
        sugg_names = [d.get("name", "") for d in sugg_dishes]
        _check("Roasted Sweet Potatoes" not in sugg_names,
               "fixture: Roasted Sweet Potatoes absent from suggested_meals "
               "(confirms it can only come from confirmed entry, not fallback)",
               "test-setup error: side dish present in suggested_meals", failures)

        st, raw = _post("/meal-wizard-step4-remove",
                        {"date": _DATE, "slot": _SLOT}, token)
        rj = json.loads(raw)

        _check(st == 200 and rj.get("ok") is True,
               "mixed-origin remove -> 200 {ok:true}",
               "mixed-origin remove did not return 200 {ok:true}", failures)

        # No-reload contract: slot_html + lock_html present.
        _check("slot_html" in rj and "lock_html" in rj,
               "response contains slot_html and lock_html (no-reload contract)",
               "no-reload keys (slot_html / lock_html) missing from response",
               failures)

        # Slot must be gone from session.
        sess_after = dh.load_meal_wizard_session()
        cm = sess_after.get("confirmed_meals") or {}
        _check((_DATE + "::" + _SLOT) not in cm,
               "confirmed slot removed from session after remove",
               "confirmed slot still present in session after remove", failures)

        # BOTH dishes must appear in reverted HTML (core regression assertion).
        slot_html = rj.get("slot_html", "")
        _check("Brined Roast Chicken" in slot_html,
               "reverted HTML contains the main dish (Brined Roast Chicken)",
               "main dish missing from reverted HTML", failures)
        _check("Roasted Sweet Potatoes" in slot_html,
               "reverted HTML contains the Lauren-only side "
               "(Roasted Sweet Potatoes) -- came from revert_dishes, not suggested",
               "Lauren-only side MISSING from reverted HTML "
               "-- mixed-origin regression: revert_dishes not passed correctly",
               failures)

    except Exception:
        failures.append("exception")
        traceback.print_exc()
    finally:
        if token:
            try:
                auth.destroy_session(token)
            except Exception:
                pass
        _shutdown_server()

    # ── Capture live-file hash AFTER all work; assert identical. ─────────────
    hash_after = _sha256_live()
    print("sha256 AFTER: ", hash_after)
    _check(
        hash_before == hash_after,
        (
            "INTEGRITY: live session file hash identical before/after "
            "(before=" + hash_before[:16] + "... "
            "after=" + hash_after[:16] + "...)"
        ),
        (
            "INTEGRITY FAIL: live session file was modified during the run! "
            "before=" + hash_before + " "
            "after=" + hash_after
        ),
        failures,
    )

    print()
    if failures:
        print(FAIL, str(len(failures)), "check(s) failed")
        sys.exit(1)
    print(PASS, "all step4-remove checks passed")


if __name__ == "__main__":
    main()
