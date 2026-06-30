# BUILD complete — `/meal-wizard-generate` slot cap + observability log

**File changed:** `app.py` only (one file, additive). Diff scope: `+34 / −2`. No data-shape change, no JS-in-f-strings, no form handling.

## What was added

### 1. Module-level constant + log helper (near `_PLACEMENT_UNDO_CAP`)
```python
_WIZARD_GEN_SLOT_CAP = 14  # conservative placeholder (2 meal types x 7 days).
# NOT measured — the known-good point is ~7 slots (1 type/week), the known-bad
# point is 55. Tune this from the log below once real stop_reason data exists.
# Added 2026-06-30.
_WIZARD_GEN_LOG = "data/meal_wizard_gen.log"


def _wizard_gen_log_line(n_targets, stop_reason):
    """Append-only OBSERVABILITY log for /meal-wizard-generate ... Deliberately
    uses a plain append (mode "a"), NOT safe_save_json ... Fail-soft: never
    raises into the handler."""
    try:
        rec = {"ts": datetime.now().isoformat(timespec="seconds"),
               "targets": n_targets, "stop_reason": stop_reason}
        with open(_WIZARD_GEN_LOG, "a", encoding="utf-8") as _fh:
            _fh.write(json.dumps(rec) + "\n")
    except Exception:
        pass
```
(`datetime` and `json` are already imported at module top — app.py lines 148–149 — so Rule 4 "no in-function imports" is respected.)

### 2. Hard cap BEFORE the API call (in the `/meal-wizard-generate` handler)
Inserted right after `_g_targets = wizard_target_slot_keys(_g_session)` and before the existing empty-target check. It returns the **same JSON shape** as the existing branch (`ok` / `generated` / `target` / `message`), with `ok:False`, and never calls the API:
```python
                    _g_targets = wizard_target_slot_keys(_g_session)
                    if len(_g_targets) > _WIZARD_GEN_SLOT_CAP:
                        _g_cap_msg = ("Lorenzo plans best a couple of meal types at a time. "
                                      "You've selected enough to fill " + str(len(_g_targets)) +
                                      " meals at once — try fewer meal types or a shorter window, "
                                      "then come back for the rest.")
                        _g_result = {"ok": False, "generated": 0,
                                     "target": len(_g_targets), "message": _g_cap_msg}
                    elif not _g_targets:
                        _g_result = {"ok": True, "generated": 0, "target": 0,
                                     "message": "No empty slots to generate."}
                    else:
                        ...
```

### 3. Log line on every cap-respecting API call (success or failure)
Logged as soon as `stop_reason` is available, right after the response is parsed:
```python
                            _g_resp.raise_for_status()
                            _g_resp_json = _g_resp.json()
                            _g_stop = _g_resp_json.get("stop_reason")
                            _wizard_gen_log_line(len(_g_targets), _g_stop)
```
This captures the exact truncation signature behind the silent-zero bug (`stop_reason == "max_tokens"`) alongside the slot count, so the cap can be tuned from real numbers.

## ⚠️ Flag for your sign-off (as the spec requested)
The new log uses a **plain append-only write** (`open(..., "a")`) and intentionally **bypasses `safe_save_json`** (Rule 5). This is deliberate: it's an observability/tuning log, **not** canonical app state, so the tmp-file + `os.replace` atomic-write machinery isn't appropriate. **Please confirm this distinction is acceptable before it's treated as a precedent** for other logging. If you'd rather it route through a state-write path or live under a `logs/` dir, say so and I'll adjust.

---

## Validation results (all required checks pass)

### 1. `py_compile app.py`
```
py_compile OK
```

### 2. In-process smoke test
Poisoned `app.requests.post` to raise if the network is touched.
```
cap constant: 14
Case A (20 slots): False | target: 20
  -> ok:False with cap message; network calls so far: 0
Case B (5 slots): proceeded to API path = True
  -> proceeds normally (not blocked by cap); network calls: 1
log last line: {"ts": "2026-06-30T14:40:03", "targets": 7, "stop_reason": "end_turn"}

SMOKE OK: 20->cap(ok:False,no network); 5->proceeds; log appends
```
- **20 target slots** → `ok:False`, message states "20 meals", **zero network calls** (cap refuses before the API).
- **5 target slots** → passes both guards and reaches the API path (the poisoned `post` fired exactly once, proving it proceeds normally).
- Log helper appends a JSONL record and never raises.

### 3. Meal-wizard harnesses
```
verify_meal_wizard_gen.py           → PASS all G1c-1a generation-contract checks passed   (exit 0)
verify_meal_wizard_step4.py         → PASS all G1b-1 read-only screen checks passed        (exit 0)
verify_meal_wizard_step4_lock.py    → PASS all G1 lock checks passed                       (exit 0)
verify_meal_wizard_step4_writeloop.py → PASS all G1b-2a write-loop + guard checks passed   (exit 0)
```

### Note on `verify_phase_g.py` (one pre-existing, unrelated FAIL)
`verify_phase_g.py` reported `FAIL: COACH block contains needle: exercise`. This is **pre-existing and unrelated** to this change:
- That harness tests the **Coach seasonal-context block** (`get_seasonal_context` / companion blocks), not meal generation.
- `grep -c "meal-wizard-generate|_WIZARD_GEN|wizard_target_slot_keys" data/verify_phase_g.py` → **0** (it references none of the symbols I touched).
- My entire diff is confined to `app.py` (`+34 / −2`) in the generate handler + the module constant.

I did not modify the Coach block and made no attempt to "fix" it, per the one-file / additive-only scope. Flagging it so you're aware it exists.

## Scope confirmation
No other changes were made — only `app.py`.
