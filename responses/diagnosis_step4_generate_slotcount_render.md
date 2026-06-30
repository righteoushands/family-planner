# DIAGNOSIS — Step 3 "what to plan", target-slot timing, token budget, Step 4 render-time state

Read-only investigation. **No changes made.**

---

## 1. Where Step 3's meal-type checkboxes render, and where `confirmed_what_to_plan` is written

**Checkbox render** — `render_meal_wizard_step3.py`. Each checkbox is built by `_mt_checkbox` (lines 249–259):
```python
def _mt_checkbox(key, label, prefill, checked):
    ev_key = escape(key)
    ev_label = escape(label)
    pf = "1" if prefill else "0"
    ck = " checked" if checked else ""
    return (
        f'<label style="{_S3_ITEM_LABEL}">'
        f'<input type="checkbox" class="mt-check" value="{ev_key}" '
        f'data-prefill="{pf}" data-label="{ev_label}"{ck}> {ev_label}'
        f'</label>'
    )
```
The set is assembled (lines 295–307), with prior selection re-checked from session, default `{"breakfast","lunch","dinner"}` otherwise:
```python
    options = _meal_type_options(feast, batch)

    if "confirmed_what_to_plan" in session:
        selected = set(session.get("confirmed_what_to_plan") or [])
    else:
        selected = set(_S3_DEFAULT_PLAN)
    ...
    checkboxes = "".join(
        _mt_checkbox(k, lbl, pf, k in selected) for (k, lbl, pf) in options
    )
```
The client packs the checked values into the JSON payload (line 174):
```python
"    var payload = { what_to_plan: wtp, complexity: cx, planning_window: win, prefill: prefill };"
```

**Write to session** — `app.py`, the `/meal-wizard-step3-save` handler. Incoming values are filtered to the known plan keys (lines 10681–10682), feast/batch pruned if not applicable (10699–10702), then persisted (lines 10732–10737):
```python
                _wtp_in = _s3_payload.get("what_to_plan") or []
                _what_to_plan = [k for k in _wtp_in if k in _S3_PLAN_KEYS] \
                ...
                update_meal_wizard_session({
                    "confirmed_what_to_plan": _what_to_plan,
                    "confirmed_complexity": _complexity,
                    "planning_window": _planning_window,
                    "confirmed_meals": _confirmed_meals,
                })
```

---

## 2. When is the full target slot list/count first known, BEFORE the API call?

**In `app.py`'s `/meal-wizard-generate` handler:** the target list is computed immediately after loading the session and **before** the API request. Line 10888:
```python
                    _g_targets = wizard_target_slot_keys(_g_session)
```
This precedes the empty-target short-circuit (10889–10891) and the prompt build (10893), and the actual API call doesn't happen until line 10900 (`_g_resp = requests.post(...)`). So `len(_g_targets)` — the exact count — is fully known at line 10888, before any network call.

**In `render_meal_wizard_gen.py`'s `wizard_target_slot_keys`:** the count is knowable as soon as the function returns — it deterministically enumerates `window × confirmed_what_to_plan` minus already-confirmed keys (lines 48–56):
```python
    keys = set()
    d = d0
    while d <= d1:
        for slot in slots:
            k = d.isoformat() + "::" + str(slot)
            if k not in confirmed:
                keys.add(k)
        d = d + timedelta(days=1)
    return sorted(keys)
```
It needs only `planning_window` + `confirmed_what_to_plan` + `confirmed_meals` from the session — no API, no I/O. The count is a pure function of session state.

---

## 3. Any existing note/constant about a safe slot count or token budget per slot?

**None found.** Searching `render_meal_wizard_gen.py` (and `build_wizard_meal_prompt`) for `token / budget / slot count / safe slot / max_tokens / too many / limit` returned no matching comment, constant, or note. The only `max_tokens` in play is the literal `"max_tokens": 4096` set on the request **in `app.py`** (line 10906) — there is no per-slot budget, no safe-slot-count constant, and no note anywhere in `render_meal_wizard_gen.py` relating output size to the number of target slots. The two grep hits in that file (lines 130, 206) are unrelated comments (raw-slot-token formatting; the inventory soft-guard).

---

## 4. At first Step 4 render, are `planning_window`, `confirmed_what_to_plan`, `confirmed_meals` already in session — could the page compute the slot count and set the Generate button's initial state at render?

**Yes — all three (plus `suggested_meals`) are read at render time.** `render_meal_wizard_step4.py` lines 435–439:
```python
    session = load_meal_wizard_session() or {}
    window = session.get("planning_window") or {}
    to_plan = session.get("confirmed_what_to_plan") or []
    confirmed = session.get("confirmed_meals") or {}
    suggested = session.get("suggested_meals") or {}
```
The render already iterates the whole window to build day cards (lines 473–478), so it has every date and every planned slot in hand. It has **exactly the three inputs `wizard_target_slot_keys` needs** — so the page could compute the empty-slot count at render with no extra I/O.

**But today it does NOT.** The Generate button is emitted as a static control with no count-derived initial state (lines 526–532):
```python
    generate_html = (
        f'<div style="{_S4_LOCK_WRAP}">'
        f'<button type="button" id="s4-gen-btn" style="{_S4_LOCK_BTN}" '
        f'onclick="s4Generate(this)">Generate my week with Lorenzo</button>'
        f'<div id="s4-gen-msg" style="{_S4_LOCK_MSG}"></div>'
        f'</div>'
    )
```
The button's only state change happens **at click**, in JS (`s4Generate`, lines 247–260): it disables itself and swaps the label to "Generating... this can take up to a minute". There is no render-time disable/enable, no "N meals to generate" label, and `wizard_target_slot_keys` is not called inside Step 4 (Step 4 imports `load_meal_wizard_session` and `get_merged_calendar_events` only — line 34 — not the slot-key helper). The separate "Set this plan" lock button *does* compute a render-time `has_lockable` flag (lines 485–494), but that gates the lock control, not the Generate control.

**Bottom line for Q4:** The data to set the Generate button's initial state at render is fully present in session at render time; the current code simply doesn't use it — the button is static until clicked.

---

*Report only. No code or files were changed.*
