"""Meal Wizard Phase G1 LOCK verification harness ("Set this plan").

Run from project root (the "Start application" workflow must be up on :5000):
    PYTHONPATH=. python data/verify_meal_wizard_step4_lock.py

This is an AUTHENTICATED HTTP ROUND-TRIP. It mints a real Lauren session and
POSTs /meal-wizard-step4-lock, then reads the live meal_plan week files and the
wizard session back.

Covers:
  UNIT (apply_confirmed_meals_to_store on a crafted dict):
    - a dinner THIS week + a dinner in the NEXT Monday-week (cross-Monday)
      -> two week keys in weeks_written.
    - johns_lunch -> lands in store slot dad_lunch.
    - feast_meal -> skipped (no store home); source=='prefill' -> skipped.
    - slots_written counts only the real writes.
  ROUND-TRIP (live POST):
    - each planned meal lands at days[<Weekday>][<store_slot>] with the right
      name; a pre-existing UNRELATED slot is STILL there (additive, not wiped);
      'generated' is unchanged.
    - the session STILL has confirmed_meals (not cleared) and now has
      plan_locked_at.
    - GET / (homepage) shows a locked meal name for today (current week).
    - GET /meal-wizard-step4 shows the "Your plan is set" banner and meals stay
      editable.

Rule 10: `mw_test_isolation` (imported first) redirects BOTH the session file
AND the meal_plan store to private temp locations, and this harness POSTs to an
IN-PROCESS server it starts on an ephemeral port -- so the live
meal_wizard_session.json, the live data/meal_plan/* week files, and the live
:5000 server are never touched. No snapshot/restore of live data is needed: the
week files this harness writes live in the isolated temp dir and are removed
wholesale at process exit. The minted auth session token is destroyed in finally.
"""
import json
import os
import sys
import traceback
import urllib.request
from datetime import date, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import mw_test_isolation  # noqa: E402,F401  MUST precede config: sets the override

import config  # noqa: E402,F401
import data_helpers as dh  # noqa: E402
import auth  # noqa: E402
import render_meals as rm  # noqa: E402
from render_timeblock import _resolve_block, _now_eastern, _meal_keys_for_block  # noqa: E402

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
BASE = "http://localhost:5000"  # replaced at runtime with the in-process server


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


def _monday(d: date) -> str:
    return (d - timedelta(days=d.weekday())).isoformat()


def main():
    global BASE
    failures = []

    mw_test_isolation.assert_isolated()
    BASE, _shutdown_server = mw_test_isolation.start_server()

    # ── Dates. Use TODAY so the homepage (which reads today's week) can see the
    # locked meal, plus a date in the NEXT Monday-week to exercise cross-Monday.
    today = _now_eastern().date()
    this_wk = _monday(today)
    next_wk_date = today + timedelta(days=7)
    next_wk = _monday(next_wk_date)
    today_iso = today.isoformat()
    today_weekday = today.strftime("%A")
    # Meals keyed on the Monday dates land on weekday "Monday" in the store.
    mon_weekday = date.fromisoformat(this_wk).strftime("%A")       # "Monday"
    next_mon_weekday = date.fromisoformat(next_wk).strftime("%A")  # "Monday"

    # The homepage shows different slots per time-block; figure out what the
    # current block surfaces so we can lock a meal that WILL appear and assert it.
    block = _resolve_block(_now_eastern())
    if block == "late_evening":
        hp_date = today + timedelta(days=1)          # late_evening shows tomorrow
    else:
        hp_date = today
    hp_date_iso = hp_date.isoformat()
    hp_keys = [k for (k, _label) in _meal_keys_for_block(block)]  # store slot keys
    hp_slot = hp_keys[0] if hp_keys else "dinner"
    hp_name = "Homepage Check Stew"

    # ── 1. UNIT TEST: pure function, no live writes yet. -----------------------
    unit_confirmed = {
        # dishes[]-shaped (new contract); the rest stay flat to exercise migration.
        this_wk + "::dinner":      {"dishes": [{"category": "main", "name": "Unit Dinner A",
                                                "ingredients": "", "protein": ""}],
                                    "source": "manual"},
        next_wk + "::dinner":      {"name": "Unit Dinner B", "source": "manual"},
        this_wk + "::johns_lunch": {"name": "Leftovers for John", "source": "manual"},
        this_wk + "::feast_meal":  {"name": "Feast Roast", "source": "manual"},
        this_wk + "::breakfast":   {"name": "Past Oatmeal", "source": "prefill"},
    }
    # No snapshot/restore: MEAL_PLAN_DIR is the isolated temp dir (see
    # mw_test_isolation), so these week files are throwaway and cleaned up at exit.
    summary = rm.apply_confirmed_meals_to_store(unit_confirmed)
    _check(set(summary["weeks_written"]) == {this_wk, next_wk},
           "UNIT: cross-Monday wrote exactly two week files",
           "UNIT: weeks_written wrong: " + str(summary["weeks_written"]),
           failures)
    _check(summary["slots_written"] == 3,
           "UNIT: slots_written counts only real writes (3)",
           "UNIT: slots_written wrong: " + str(summary["slots_written"]),
           failures)
    _check((this_wk + "::feast_meal") in summary["skipped"]
           and (this_wk + "::breakfast") not in summary["weeks_written"],
           "UNIT: feast_meal skipped (no store home)",
           "UNIT: feast_meal not skipped", failures)
    plan_this = rm.load_meal_plan(this_wk)
    _check(plan_this["days"].get(mon_weekday, {}).get("dad_lunch") == "Leftovers for John",
           "UNIT: johns_lunch landed in store slot dad_lunch",
           "UNIT: johns_lunch did not map to dad_lunch", failures)
    _check(plan_this["days"].get(mon_weekday, {}).get("breakfast") != "Past Oatmeal",
           "UNIT: prefill meal was NOT written to the store",
           "UNIT: prefill meal leaked into the store", failures)
    # Reset the isolated store so the round-trip below starts clean (the unit
    # test wrote into the same temp dir; no live data is involved).
    for _wk in (this_wk, next_wk):
        _p = rm._plan_path(_wk)
        if os.path.exists(_p):
            os.remove(_p)

    # ── 2. AUTHENTICATED ROUND-TRIP. ------------------------------------------
    # Pre-seed an UNRELATED slot in this week's file to prove the lock is
    # additive (does not wipe slots it didn't plan).
    pre = rm.load_meal_plan(this_wk)
    pre.setdefault("days", {}).setdefault(mon_weekday, {})["snacks"] = "Pre-existing Snack"
    pre["generated"] = False
    pre["week"] = this_wk
    pre["start"] = this_wk
    rm.save_meal_plan(pre)

    token = None
    try:
        token = auth.create_session("lauren")

        # Seed the wizard session: a real mix, including the homepage-visible
        # meal, a cross-Monday dinner, a johns_lunch, a feast_meal (skipped),
        # and a prefill (skipped).
        dh.clear_meal_wizard_session()
        seeded = {
            # dishes[]-shaped lockable entry (new contract) drives the lockability
            # gate + store write; flat entries below exercise read-time migration.
            this_wk + "::dinner":      {"dishes": [{"category": "main",
                                                    "name": "Locked Dinner Here",
                                                    "ingredients": "", "protein": ""}],
                                        "source": "manual",
                                        "recipe_id": "", "recipe_on_request": True},
            next_wk + "::dinner":      {"name": "Next Week Dinner", "source": "manual",
                                        "recipe_id": "", "recipe_on_request": True},
            this_wk + "::johns_lunch": {"name": "John Leftovers", "source": "manual"},
            this_wk + "::feast_meal":  {"name": "Skip Feast", "source": "manual"},
            next_wk + "::breakfast":   {"name": "Skip Prefill", "source": "prefill"},
            hp_date_iso + "::" + hp_slot: {"dishes": [{"category": "main", "name": hp_name,
                                                      "ingredients": "", "protein": ""}],
                                          "source": "manual",
                                          "recipe_id": "", "recipe_on_request": True},
        }
        dh.update_meal_wizard_session({
            "planning_window": {"start_iso": today_iso, "end_iso": next_wk_date.isoformat()},
            "confirmed_what_to_plan": ["breakfast", "lunch", "dinner",
                                       "johns_lunch", "feast_meal"],
            "confirmed_meals": seeded,
        })

        # POST the lock.
        st, raw = _post("/meal-wizard-step4-lock", {}, token)
        body = json.loads(raw)
        _check(st == 200 and body.get("ok") is True,
               "lock POST returns 200 {ok:true}",
               "lock POST did not return ok", failures)
        _check(set(body.get("weeks_written", [])) == {this_wk, next_wk},
               "lock wrote both week files (cross-Monday)",
               "lock weeks_written wrong: " + str(body.get("weeks_written")),
               failures)

        # Store assertions.
        plan_this = rm.load_meal_plan(this_wk)
        plan_next = rm.load_meal_plan(next_wk)
        _check(plan_this["days"].get(mon_weekday, {}).get("dinner") == "Locked Dinner Here",
               "this-week dinner persisted to days[Weekday][dinner]",
               "this-week dinner missing from store", failures)
        _check(plan_next["days"].get(next_mon_weekday, {}).get("dinner") == "Next Week Dinner",
               "next-week dinner persisted (second file)",
               "next-week dinner missing from store", failures)
        _check(plan_this["days"].get(mon_weekday, {}).get("dad_lunch") == "John Leftovers",
               "johns_lunch -> dad_lunch in the store",
               "johns_lunch did not map to dad_lunch", failures)
        _check(plan_this["days"].get(mon_weekday, {}).get("snacks") == "Pre-existing Snack",
               "pre-existing UNRELATED slot still present (additive)",
               "lock wiped an unrelated slot", failures)
        _check(plan_this.get("generated") is False,
               "'generated' left unchanged (still False)",
               "lock altered 'generated'", failures)
        _check("Skip Feast" not in json.dumps(plan_this) + json.dumps(plan_next),
               "feast_meal NOT written to either store file",
               "feast_meal leaked into the store", failures)
        _check("Skip Prefill" not in json.dumps(plan_this) + json.dumps(plan_next),
               "prefill meal NOT written to the store",
               "prefill meal leaked into the store", failures)

        # Session must be KEPT (revisitable) and marked locked.
        sess = dh.load_meal_wizard_session()
        _check((sess.get("confirmed_meals") or {}).get(this_wk + "::dinner") is not None,
               "session STILL has confirmed_meals (not cleared)",
               "session confirmed_meals was cleared", failures)
        _check(bool((sess.get("plan_locked_at") or "").strip()),
               "session now has plan_locked_at",
               "plan_locked_at not set on session", failures)

        # Homepage shows the locked meal for the current block.
        st, hp = _get("/", token)
        _check(st == 200 and hp_name in hp,
               "homepage meals card shows the locked meal (block=" + block + ")",
               "locked meal not on homepage (block=" + block + ", slot=" + hp_slot + ")",
               failures)

        # Step 4 shows the banner and stays editable.
        st, s4 = _get("/meal-wizard-step4", token)
        _check(st == 200 and "Your plan is set" in s4,
               "Step 4 shows the 'Your plan is set' banner",
               "banner missing after lock", failures)
        _check("Set this plan" in s4,
               "Step 4 keeps the meals editable (Set this plan still present)",
               "Step 4 no longer editable after lock", failures)

    except Exception:
        failures.append("exception")
        traceback.print_exc()
    finally:
        if token:
            try:
                auth.destroy_session(token)
            except Exception:
                pass
        # No live data to restore: the session file and the meal_plan store are
        # both isolated temp paths (see mw_test_isolation) and are cleaned up
        # wholesale at process exit.
        _shutdown_server()

    print()
    if failures:
        print(FAIL, str(len(failures)), "check(s) failed")
        sys.exit(1)
    print(PASS, "all G1 lock checks passed")


if __name__ == "__main__":
    main()
