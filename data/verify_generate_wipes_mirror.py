"""Diagnosis harness: does /meal-wizard-generate (which wholesale-replaces
suggested_meals) wipe a mirror entry that /meal-wizard-step4-confirm wrote for a
DIFFERENT slot?

Flow:
  1. confirm D1::dinner  -> mirror lands in suggested_meals[D1::dinner]
  2. generate (targets D1::lunch only; dinner is confirmed, so excluded)
  3. check whether suggested_meals[D1::dinner] survived

The real generate handler is driven end-to-end; only the external boundary is
stubbed so the run is deterministic and offline: app.requests (Anthropic call),
app.load_app_settings (API key), and app._wizard_gen_log_line (observability log
path, not covered by isolation). The suggested_meals write path under test
(update_meal_wizard_session) runs for real.

Rule 10/10a: mw_test_isolation imported FIRST; in-process server; live data
untouched. 'PASS' here means the mirror SURVIVED generate; 'FAIL' means generate
wiped it.
"""
import json
import os
import sys
import traceback
import types
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import mw_test_isolation  # noqa: E402,F401  MUST precede config

import config  # noqa: E402,F401
import data_helpers as dh  # noqa: E402
import auth  # noqa: E402
import app  # noqa: E402

_D1 = "2026-06-29"
BASE = None


def _post(path, payload, token):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Cookie", "session=" + token)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, resp.read().decode("utf-8", "ignore")


def _sug():
    return dh.load_meal_wizard_session().get("suggested_meals") or {}


def main():
    global BASE
    mw_test_isolation.assert_isolated()

    _fake_json = {
        "meals": {_D1: {"lunch": {"name": "Generated Lunch",
                                  "ingredients": "greens", "protein": "turkey"}}}
    }

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"stop_reason": "end_turn",
                    "content": [{"type": "text",
                                 "text": json.dumps(_fake_json)}]}

    def _fake_post(url, **kwargs):
        return _FakeResp()

    _orig_requests = app.requests
    _orig_settings = app.load_app_settings
    _orig_log = app._wizard_gen_log_line
    app.requests = types.SimpleNamespace(post=_fake_post)
    app.load_app_settings = lambda: {"anthropic_api_key": "test-key"}
    app._wizard_gen_log_line = lambda *a, **k: None

    BASE, _shutdown_server = mw_test_isolation.start_server()
    token = None
    survived = None
    try:
        token = auth.create_session("lauren")
        dh.clear_meal_wizard_session()
        dh.update_meal_wizard_session({
            "planning_window": {"start_iso": _D1, "end_iso": _D1},
            "confirmed_what_to_plan": ["lunch", "dinner"],
            "confirmed_meals": {},
        })

        # (1) confirm dinner -> mirror written
        st, raw = _post("/meal-wizard-step4-confirm", {
            "date": _D1, "slot": "dinner",
            "dishes": [{"category": "main", "name": "Chicken Parm",
                        "ingredients": "", "protein": "chicken"}],
            "source": "manual",
        }, token)
        print("(1) confirm dinner ->", st, json.loads(raw).get("ok"))
        _after_confirm = _sug()
        _mirror = _after_confirm.get(_D1 + "::dinner")
        print("    suggested_meals[" + _D1 + "::dinner] (mirror):")
        print("      " + json.dumps(_mirror, sort_keys=True))
        print("    suggested_meals keys:", sorted(_after_confirm.keys()))
        mirror_present = isinstance(_mirror, dict) and bool(dh.slot_dishes(_mirror))
        print("    mirror present after confirm:", mirror_present)

        # (2) generate -> targets lunch only (dinner is confirmed => excluded)
        st, raw = _post("/meal-wizard-generate", {}, token)
        _gj = json.loads(raw)
        print("\n(2) generate ->", st, "ok=", _gj.get("ok"),
              "generated=", _gj.get("generated"), "target=", _gj.get("target"))

        # (3) did the dinner mirror survive?
        _after_gen = _sug()
        _mirror2 = _after_gen.get(_D1 + "::dinner")
        print("\n(3) suggested_meals keys after generate:",
              sorted(_after_gen.keys()))
        print("    suggested_meals[" + _D1 + "::dinner] after generate:")
        print("      " + json.dumps(_mirror2, sort_keys=True))
        survived = isinstance(_mirror2, dict) and bool(dh.slot_dishes(_mirror2))
        print("    mirror survived generate:", survived)
    except Exception:
        traceback.print_exc()
    finally:
        app.requests = _orig_requests
        app.load_app_settings = _orig_settings
        app._wizard_gen_log_line = _orig_log
        if token:
            try: auth.destroy_session(token)
            except Exception: pass
        _shutdown_server()

    print()
    print("RESULT:", "PASS (mirror survived)" if survived
          else "FAIL (generate wiped the mirror)")
    sys.exit(0 if survived else 1)


if __name__ == "__main__":
    main()
