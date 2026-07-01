"""Meal Wizard Phase G1b-2a verification harness (manual write loop + guard).

Run from project root (the "Start application" workflow must be up on :5000):
    PYTHONPATH=. python data/verify_meal_wizard_step4_writeloop.py

This is an AUTHENTICATED HTTP ROUND-TRIP — the G1b-1 import bug hid behind the
unauth 302 because the route body never ran, so a page load alone proves
nothing. Here we mint a real Lauren session and actually POST through the live
handlers, then read the session back.

Covers:
  GUARD (server-side, /meal-wizard-step4-confirm):
    1. recipe_id "" and recipe_on_request omitted  -> auto-set True.
    2. recipe_id present, flag omitted             -> left False (no fire).
    3. recipe_on_request already True              -> left True.
  WRITE LOOP:
    a. confirm a manual meal -> session has it, locked True, recipe_on_request
       True (guard) even though the client omitted it.
    b. GET /meal-wizard-step4 -> shows the meal, a "Change" button, "No recipe
       needed".
    c. remove it -> session slot gone; GET shows the empty entry state again.
    d. a prefill (past) entry renders locked with NO "Change" button.

Rule 10: `mw_test_isolation` (imported first) redirects the session file AND the
meal_plan store to private temp locations and this harness POSTs to an IN-PROCESS
server it starts on an ephemeral port -- so the live meal_wizard_session.json,
data/meal_plan/*, and the live :5000 server are never touched (no snapshot/
restore needed). The minted auth session token is destroyed in finally.
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

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
BASE = "http://localhost:5000"  # replaced at runtime with the in-process server

_D1 = "2026-06-29"  # Monday
_D2 = "2026-06-30"  # Tuesday


def _check(cond, ok_msg, fail_msg, failures):
    if cond:
        print(PASS, ok_msg)
    else:
        failures.append(fail_msg)
        print(FAIL, fail_msg)


# Rule 10 guard: this harness isolates the meal_wizard session file AND the
# meal_plan store (via MEAL_PLAN_DIR), but render_john.py reads a HARDCODED live
# meal_plan path that the override does NOT cover. That code is only reachable via
# the /john route, which this harness never calls. This makes that durable: if a
# future edit ever points a request at /john, the run fails loudly instead of
# silently touching live data.
_UNISOLATED_ROUTES = ("/john",)


def _forbid_unisolated_routes(path):
    for r in _UNISOLATED_ROUTES:
        if path == r or path.startswith(r + "/") or path.startswith(r + "?"):
            raise AssertionError(
                "Rule 10 guard: harness must not request " + repr(path) + " -- "
                "render_john.py reads the live meal_plan path directly (not "
                "MEAL_PLAN_DIR), so that route is NOT isolated. Redirect "
                "render_john before removing this guard."
            )


def _post(path, payload, token):
    _forbid_unisolated_routes(path)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Cookie", "session=" + token)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read().decode("utf-8", "ignore")


def _get(path, token):
    _forbid_unisolated_routes(path)
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Cookie", "session=" + token)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read().decode("utf-8", "ignore")


def _entry(date_iso, slot):
    meals = dh.load_meal_wizard_session().get("confirmed_meals") or {}
    return meals.get(date_iso + "::" + slot)


def main():
    global BASE
    failures = []

    mw_test_isolation.assert_isolated()
    BASE, _shutdown_server = mw_test_isolation.start_server()

    token = None
    try:
        token = auth.create_session("lauren")

        # Seed a window + slots to plan; start with no confirmed meals.
        dh.clear_meal_wizard_session()
        dh.update_meal_wizard_session({
            "planning_window": {"start_iso": _D1, "end_iso": _D2},
            "confirmed_what_to_plan": ["breakfast", "lunch", "dinner"],
            "confirmed_meals": {},
        })

        # ── GUARD branch 1 + write-loop (a): confirm with recipe fields OMITTED
        st, raw = _post("/meal-wizard-step4-confirm", {
            "date": _D1, "slot": "dinner",
            "dishes": [{"category": "main", "name": "Chicken Parm",
                        "ingredients": "", "protein": "chicken"}],
            "source": "manual",
        }, token)
        ok = (st == 200) and (json.loads(raw).get("ok") is True)
        _check(ok, "confirm POST returns 200 {ok:true}",
               "confirm POST did not return ok", failures)
        # No-reload contract: confirm now returns the rendered CONFIRMED slot
        # fragment + lock control for in-place DOM injection (not a reload).
        _cj = json.loads(raw)
        _conf_change_call = "s4Change('" + _D1 + "','dinner')"
        _check("slot_html" in _cj and "Chicken Parm" in _cj["slot_html"]
               and _conf_change_call in _cj["slot_html"]
               and ("s4-row--" + _D1 + "--dinner") in _cj["slot_html"],
               "confirm response returns the confirmed slot fragment (row id + Change)",
               "confirm response missing the confirmed slot fragment", failures)
        _check(_cj.get("lockable") is True
               and "lock_html" in _cj and "s4-lock-control" in _cj["lock_html"],
               "confirm response reports lock-eligibility True + lock-control HTML",
               "confirm response lock-eligibility payload wrong", failures)
        e = _entry(_D1, "dinner")
        _check(isinstance(e, dict),
               "confirmed meal persisted to session",
               "confirmed meal missing from session", failures)
        _check(isinstance(e, dict) and e.get("locked") is True,
               "confirmed meal is locked", "confirmed meal not locked", failures)
        _check(isinstance(e, dict) and e.get("recipe_on_request") is True,
               "GUARD 1: recipe_on_request auto-set True (client omitted it)",
               "GUARD 1 failed: recipe_on_request not auto-set", failures)
        _check(isinstance(e, dict) and (e.get("recipe_id") or "") == "",
               "confirmed meal has empty recipe_id", "recipe_id unexpectedly set",
               failures)
        _ed = dh.slot_dishes(e) if isinstance(e, dict) else []
        _check(bool(_ed) and _ed[0].get("name") == "Chicken Parm"
               and _ed[0].get("category") == "main"
               and isinstance(e, dict) and "name" not in e,
               "confirmed entry stored in dishes[] shape (no flat name key)",
               "confirmed entry not stored in dishes[] shape", failures)

        # ── write-loop (b): GET shows the meal + Change + "No recipe needed"
        st, html = _get("/meal-wizard-step4", token)
        change_call = "s4Change('" + _D1 + "','dinner')"
        _check(st == 200 and "Chicken Parm" in html,
               "GET page shows the confirmed meal", "meal not shown on page",
               failures)
        _check(change_call in html,
               "confirmed meal shows a 'Change' button",
               "Change button missing for confirmed meal", failures)
        _check("No recipe needed" in html,
               "confirmed meal shows 'No recipe needed'",
               "'No recipe needed' missing", failures)

        # ── GUARD branch 2: recipe_id present, flag omitted -> stays False
        _post("/meal-wizard-step4-confirm", {
            "date": _D1, "slot": "lunch",
            "dishes": [{"name": "Turkey wrap"}],
            "source": "manual", "recipe_id": "r-9",
        }, token)
        e2 = _entry(_D1, "lunch")
        _check(isinstance(e2, dict) and e2.get("recipe_id") == "r-9"
               and e2.get("recipe_on_request") is False,
               "GUARD 2: recipe_id present -> recipe_on_request left False",
               "GUARD 2 failed: flag changed when recipe_id present", failures)

        # ── GUARD branch 3: recipe_on_request already True -> stays True
        _post("/meal-wizard-step4-confirm", {
            "date": _D2, "slot": "lunch",
            "dishes": [{"name": "Soup"}],
            "source": "manual", "recipe_on_request": True,
        }, token)
        e3 = _entry(_D2, "lunch")
        _check(isinstance(e3, dict) and e3.get("recipe_on_request") is True,
               "GUARD 3: recipe_on_request already True -> left True",
               "GUARD 3 failed: True flag was altered", failures)

        # ── write-loop (c): remove -> slot gone; page back to entry state
        st, raw = _post("/meal-wizard-step4-remove",
                        {"date": _D1, "slot": "dinner"}, token)
        ok = (st == 200) and (json.loads(raw).get("ok") is True)
        _check(ok and _entry(_D1, "dinner") is None,
               "remove POST clears the slot from the session",
               "remove did not clear the slot", failures)
        # No-reload contract: remove returns the reverted ENTRY-state slot
        # fragment for in-place DOM injection (not a reload). Because
        # /meal-wizard-step4-confirm now mirrors the saved dishes[] into
        # suggested_meals, the reverted slot is back in the entry affordance
        # (its s4-name textarea id is present) but PRE-FILLED with Lauren's
        # LAST-CONFIRMED value ("Chicken Parm") -- never blank, never Lorenzo's
        # older draft. The s4-name textarea id only renders in the entry state
        # (a confirmed row shows the name in a static div), so its presence
        # together with the value proves "reverted to entry, showing last value".
        _rj = json.loads(raw)
        # Phase B: entry state is now identified by the dish-container id
        # (s4-dishes--{key}), not the old s4-name-- textarea id.  The
        # container only renders in the entry affordance (never in the
        # confirmed-row view), so its presence together with "Chicken Parm"
        # proves "reverted to entry, pre-filled with the last-confirmed value".
        _rm_dishes_id = "s4-dishes--" + _D1 + "--dinner"
        _check("slot_html" in _rj and _rm_dishes_id in _rj["slot_html"]
               and "Chicken Parm" in _rj["slot_html"]
               and "lock_html" in _rj and "s4-lock-control" in _rj["lock_html"],
               "remove response reverts to entry state showing the last-confirmed value",
               "remove response did not show the last-confirmed value in entry state",
               failures)
        st, html = _get("/meal-wizard-step4", token)
        dishes_id = "s4-dishes--" + _D1 + "--dinner"
        _check(st == 200 and (dishes_id in html) and ("Chicken Parm" in html),
               "removed slot returns to entry state showing the last-confirmed value",
               "removed slot did not show the last-confirmed value in entry state",
               failures)

        # ── write-loop (d): a prefill (past) entry is locked, NO Change button
        meals = dh.load_meal_wizard_session().get("confirmed_meals") or {}
        meals[_D2 + "::breakfast"] = {
            "dishes": [{"category": "main", "name": "Oatmeal",
                        "ingredients": "oats", "protein": ""}],
            "source": "prefill", "locked": True, "recipe_id": "",
            "recipe_on_request": True, "skip_shopping": False,
        }
        dh.update_meal_wizard_session({"confirmed_meals": meals})
        st, html = _get("/meal-wizard-step4", token)
        prefill_change = "s4Change('" + _D2 + "','breakfast')"
        _check(st == 200 and "Oatmeal" in html and prefill_change not in html,
               "prefill (past) meal renders locked with NO 'Change' button",
               "prefill meal incorrectly got a Change button", failures)

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

    print()
    if failures:
        print(FAIL, str(len(failures)), "check(s) failed")
        sys.exit(1)
    print(PASS, "all G1b-2a write-loop + guard checks passed")


if __name__ == "__main__":
    main()
