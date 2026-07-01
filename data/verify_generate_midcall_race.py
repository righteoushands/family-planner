"""Mid-call race harness: a suggested_meals write that lands DURING generate's
model call must survive generate's final merge-and-write.

Setup: window = single day D1; what_to_plan = breakfast, lunch, dinner.
  (1) confirm dinner  -> suggested_meals[D1::dinner] mirror written.
  (2) generate: targets = {breakfast, lunch} (dinner confirmed => excluded).
      The stubbed Anthropic call, WHILE it runs (i.e. after generate captured its
      early _g_session snapshot, before generate's own write), simulates a
      concurrent confirm of BREAKFAST -- writing confirmed_meals + a
      suggested_meals[D1::breakfast] mirror to the session file. The stub then
      returns a menu for LUNCH only.
  (3) After generate's final write, assert the mid-call breakfast mirror survived
      (it would be clobbered by a pre-call stale snapshot; the fresh-read fix
      preserves it), alongside the pre-call dinner mirror and the generated lunch.

Rule 10/10a: mw_test_isolation imported FIRST; in-process server; live data
untouched. External boundary (requests / API key / gen log) stubbed for a
deterministic offline run; the suggested_meals write path under test runs for real.
'PASS' == mid-call write survived.
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


def _has(entry):
    return isinstance(entry, dict) and bool(dh.slot_dishes(entry)) \
        and (dh.slot_dishes(entry)[0].get("name") or "").strip() != ""


def main():
    global BASE
    mw_test_isolation.assert_isolated()

    _bf = {"category": "main", "name": "Midcall Eggs",
           "ingredients": "eggs", "protein": "egg"}
    _fake_menu = {"meals": {_D1: {"lunch": {"name": "Generated Lunch",
                                            "ingredients": "greens",
                                            "protein": "turkey"}}}}

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"stop_reason": "end_turn",
                    "content": [{"type": "text",
                                 "text": json.dumps(_fake_menu)}]}

    def _fake_post(url, **kwargs):
        # ── MID-CALL: a concurrent confirm of BREAKFAST lands now, during the
        # model call -- after generate captured its early snapshot, before its
        # own write. Mirror the breakfast dish into suggested_meals like the real
        # confirm handler does.
        _sess = dh.load_meal_wizard_session()
        _cm = _sess.get("confirmed_meals") or {}
        _cm[_D1 + "::breakfast"] = {"dishes": [dict(_bf)], "source": "manual",
                                    "locked": True, "recipe_id": "",
                                    "recipe_on_request": True,
                                    "skip_shopping": False}
        _sm = _sess.get("suggested_meals") or {}
        _sm[_D1 + "::breakfast"] = {"dishes": [dict(_bf)]}
        dh.update_meal_wizard_session({"confirmed_meals": _cm,
                                       "suggested_meals": _sm})
        return _FakeResp()

    _orig_requests = app.requests
    _orig_settings = app.load_app_settings
    _orig_log = app._wizard_gen_log_line
    app.requests = types.SimpleNamespace(post=_fake_post)
    app.load_app_settings = lambda: {"anthropic_api_key": "test-key"}
    app._wizard_gen_log_line = lambda *a, **k: None

    BASE, _shutdown_server = mw_test_isolation.start_server()
    token = None
    ok = False
    try:
        token = auth.create_session("lauren")
        dh.clear_meal_wizard_session()
        dh.update_meal_wizard_session({
            "planning_window": {"start_iso": _D1, "end_iso": _D1},
            "confirmed_what_to_plan": ["breakfast", "lunch", "dinner"],
            "confirmed_meals": {},
        })

        # (1) confirm dinner -> pre-call mirror
        st, raw = _post("/meal-wizard-step4-confirm", {
            "date": _D1, "slot": "dinner",
            "dishes": [{"category": "main", "name": "Chicken Parm",
                        "ingredients": "", "protein": "chicken"}],
            "source": "manual",
        }, token)
        print("(1) confirm dinner ->", st, json.loads(raw).get("ok"))
        print("    suggested keys:", sorted(_sug().keys()))

        # (2) generate (breakfast confirm lands mid-call inside the stub)
        st, raw = _post("/meal-wizard-generate", {}, token)
        _gj = json.loads(raw)
        print("\n(2) generate ->", st, "ok=", _gj.get("ok"),
              "generated=", _gj.get("generated"), "target=", _gj.get("target"))

        # (3) survival check
        after = _sug()
        print("\n(3) suggested keys after generate:", sorted(after.keys()))
        for k in ("breakfast", "dinner", "lunch"):
            print("    [" + _D1 + "::" + k + "] =",
                  json.dumps(after.get(_D1 + "::" + k), sort_keys=True))
        midcall_survived = _has(after.get(_D1 + "::breakfast"))
        precall_survived = _has(after.get(_D1 + "::dinner"))
        generated_present = _has(after.get(_D1 + "::lunch"))
        print()
        print("    mid-call breakfast write survived:", midcall_survived)
        print("    pre-call dinner mirror survived:", precall_survived)
        print("    generated lunch present:", generated_present)
        ok = midcall_survived and precall_survived and generated_present
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
    print("RESULT:", "PASS (mid-call write survived)" if ok
          else "FAIL (mid-call write clobbered)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
