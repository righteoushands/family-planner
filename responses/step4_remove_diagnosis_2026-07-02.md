# Step 4 — `/meal-wizard-step4-remove` diagnosis (2026-07-02)

Diagnosis only. No fix. All quotes are from the live source files.

---

## 1. How does the remove request identify which dish?

There are **two entirely separate "remove" mechanisms** in Step 4 — one client-side,
one server-side — and they operate at different granularities. This is the core of
the bug.

### a) `s4RemoveDish(btn)` — the "Remove" button on each individual dish row

**Client-side DOM manipulation only. No network request. Never touches the server.**

```javascript
window.s4RemoveDish = function(btn){
  var row = btn ? btn.closest('.s4dr') : null;
  if(!row){ return; }
  var container = row.parentNode;
  if(container && container.querySelectorAll('.s4dr').length > 1){
    container.removeChild(row);
  }
};
```
(`render_meal_wizard_step4.py` lines 293-300)

Identifies the target by `btn.closest('.s4dr')` — the enclosing dish-row div.
Removes exactly that DOM node. No identifier is sent anywhere; nothing is
persisted until the user subsequently clicks "Keep this meal".

### b) `s4Change(date, slot)` — the "Change" button on a confirmed slot

**Calls the server. Identifies by slot-key only — `{date, slot}`. No dish
identifier of any kind.**

```javascript
window.s4Change = function(date, slot){
  var key = date + '--' + slot;
  var msgId = 's4-msg--' + key;
  setMsg(msgId, '');
  var payload = { date: date, slot: slot };
  fetch('/meal-wizard-step4-remove', { method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) })
    .then(function(r){ return r.json(); })
    .then(function(j){ if(j && j.ok && j.slot_html){
        var row = elById('s4-row--' + key); if(row){ row.outerHTML = j.slot_html; }
        var lock = elById('s4-lock-control'); if(lock && j.lock_html){ lock.outerHTML = j.lock_html; } }
      else { setMsg(msgId, 'Could not change. Please try again.'); } })
    .catch(function(){ setMsg(msgId, 'Could not change. Please try again.'); });
};
```
(`render_meal_wizard_step4.py` lines 301-313)

---

## 2. Does the handler filter one dish from dishes[], or does it overwrite the whole slot?

**It pops the entire slot key from `confirmed_meals`. Every dish in that slot is
gone in a single operation. There is no per-dish filtering.**

The handler reads `confirmed_meals`, calls `.pop()` on the whole `"date::slot"` key,
and writes the mutated dict back. It does not read, inspect, or selectively modify
the `dishes[]` array inside the entry.

---

## 3. Is there a shallow-merge clobbering the dishes[] array?

**No — not in the remove handler itself.** The `update_meal_wizard_session(...)` at
the end does a top-level `dict.update` (the Rule 21 shallow merge), but here that is
correct: the entire `confirmed_meals` dict (with the slot popped) is passed as the
new value, and `suggested_meals` is left untouched. There is no dict whose `dishes[]`
array is being replaced by a sibling update.

The Rule 21 pattern would be a bug if the handler passed `{"confirmed_meals":
{one_key: new_entry}}` — that would wholesale-replace `confirmed_meals` with a
single-key dict, wiping all other confirmed slots. That is NOT what happens here:
`_s4r_meals` is the full session `confirmed_meals` dict, modified in place by
`.pop()`, then passed wholesale. The Rule 21 issue is not the source of this symptom.

---

## 4. The actual removal function (app.py lines 10878-10922)

```python
elif path == "/meal-wizard-step4-remove":
    # Idempotent removal of ONE confirmed meal (the "Change this
    # meal" backing op). Only Lauren triggers this from the UI; the
    # server never removes a meal on its own (Rule 16). Responds
    # {"ok":true} even when the slot was already absent.
    _s4r_cl  = int(self.headers.get("Content-Length","0") or 0)
    _s4r_raw = self.rfile.read(_s4r_cl).decode("utf-8","ignore") if _s4r_cl else ""
    try:    _s4r_payload = json.loads(_s4r_raw)
    except Exception: _s4r_payload = {}
    _S4R_SLOTS = {"breakfast","lunch","dinner","johns_lunch",
                  "snacks","dessert","feast_meal","batch_cook"}
    def _s4r_valid_iso(_v):
        try:    date.fromisoformat(_v); return _v
        except Exception: return ""
    _s4r_date = _s4r_valid_iso(str(_s4r_payload.get("date","")))
    _s4r_slot = str(_s4r_payload.get("slot","")).strip().lower()
    if (not _s4r_date) or (_s4r_slot not in _S4R_SLOTS):
        self.send_response(400)
        self.send_header("Content-Type","application/json")
        self.end_headers()
        try: self.wfile.write(b'{"ok":false}')
        except BrokenPipeError: pass
        return
    _s4r_meals = load_meal_wizard_session().get("confirmed_meals") or {}
    _s4r_meals.pop(_s4r_date + "::" + _s4r_slot, None)
    update_meal_wizard_session({
        "confirmed_meals": _s4r_meals,
        "used_proteins":   recompute_used_proteins(_s4r_meals),
    })
    # No-reload swap: return the reverted slot row (entry affordance,
    # carrying any standing Lorenzo suggestion) + lock control so the
    # client patches just that row in place.
    _s4r_frag = render_step4_slot_and_lock(_s4r_date, _s4r_slot)
    self.send_response(200)
    self.send_header("Content-Type","application/json")
    self.end_headers()
    _s4r_body = json.dumps({
        "ok": True,
        "slot_html": _s4r_frag["slot_html"],
        "lock_html": _s4r_frag["lock_html"],
        "lockable":  _s4r_frag["lockable"],
    }).encode()
    try: self.wfile.write(_s4r_body)
    except BrokenPipeError: pass
    return
```

---

## Diagnosis — what is actually causing the symptom

### Architecture mismatch (the root cause)

The "Remove" button on each dish row and the "Change" button on a confirmed slot are
**operating at completely different levels**, and these levels are not symmetric:

| Button | Label | Scope | Server? | Effect |
|---|---|---|---|---|
| dish row Remove | "Remove" | one dish row | **No** | DOM-only; removes that `.s4dr` div |
| confirmed slot | "Change" | whole slot | **Yes** | pops entire `confirmed_meals[date::slot]` |

There is no server-side "remove one dish from a confirmed multi-dish slot." The only
server remove is slot-level.

### How the side disappears

The bug occurs during `s4Change` (the confirmed-slot "Change" button), not `s4RemoveDish`.

**Step-by-step:**

1. Lauren confirms a dinner slot with two dishes: `confirmed_meals["date::dinner"] = {dishes: [main, side]}`. The confirmed slot row shows "Chicken / Sweet Potatoes" + a "Change" button.

2. Lauren clicks "Change" — intending to change or remove just one of the two dishes.

3. `s4Change` fires: `fetch('/meal-wizard-step4-remove', body={date, slot})`.

4. Server pops `"date::dinner"` from `confirmed_meals` entirely — **both dishes gone from session**.

5. Server calls `render_step4_slot_and_lock(date, 'dinner')` to build the reverted slot HTML. This renders the slot as an entry form. It pre-fills from `suggested_meals["date::dinner"]` — but at this point `suggested_meals` may contain **only the main dish** (e.g. if Lorenzo generated dinner as a single-dish suggestion before G1c-3a, or if the suggestion was subsequently overwritten by a re-generate that returned only one dish, or if the suggestion was never a multi-dish at all and Lauren had manually added the side dish at confirm time).

6. `s4Change` receives `slot_html` showing only one dish row (main, from `suggested_meals`). It replaces `s4-row--{key}.outerHTML`.

7. Lauren sees: the main dish row is there. The side dish — which she typed at confirm time and was stored in `confirmed_meals`, not in `suggested_meals` — is gone.

### Why `s4RemoveDish` is not the culprit

`s4RemoveDish` removes the correct DOM row and nothing else. The guard
(`querySelectorAll('.s4dr').length > 1`) correctly prevents removing the last row.
Neither the `_rm_hide` logic (set once per slot, correct for multi-dish) nor the
`btn.closest('.s4dr')` traversal introduce a second removal.

### The structural gap

`suggested_meals` is Lorenzo's draft. `confirmed_meals` is Lauren's confirmed
selection — which may include dishes she typed or edited that were never in
`suggested_meals`. When `s4Change` clears `confirmed_meals[slot]` and renders from
`suggested_meals`, any dish that existed in `confirmed_meals` but not in
`suggested_meals` is silently lost. There is no "revert to what Lauren had confirmed"
path — the revert goes straight to what Lorenzo suggested, which may be fewer dishes
or even empty.

### Summary for the fix

The fix requires dish-level granularity at the server. Options:

- **Option A (server):** Add a `dish_index` or `dish_name` to the remove payload; have the handler splice dishes[] in place within `confirmed_meals[slot]`, leaving the remaining dishes alone. Use this for the "remove one dish" action.
- **Option B (revert path):** When `s4Change` clears a slot, if `confirmed_meals` had dishes that are not in `suggested_meals`, copy those dishes back into `suggested_meals` first (or use `confirmed_meals` as the revert source instead of `suggested_meals`).
- **Option C (UX):** Keep `s4RemoveDish` as the dish-level remove (client-side), but wire it into the confirm flow automatically — i.e., after `s4RemoveDish` removes a row, immediately call `/meal-wizard-step4-confirm` with the remaining dishes so the confirmed state is updated in place. This avoids needing server-side dish-index logic.
