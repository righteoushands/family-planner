# DIAGNOSIS — G1c-2 "Generate my week with Lorenzo" button does nothing on click

**Scope:** Diagnosis only. Nothing was changed.

---

## 1. Generate button element (verbatim)
`render_meal_wizard_step4.py` lines 504–505:
```python
f'<button type="button" id="s4-gen-btn" style="{_S4_LOCK_BTN}" '
f'onclick="s4Generate(this)">Generate my week with Lorenzo</button>'
```
onclick calls **`s4Generate(this)`**.

## 2. s4Generate definition
`render_meal_wizard_step4.py` line 236, inside the `_S4_JS` IIFE:
```python
"  window.s4Generate = function(btn){"
```
- (a) Attached as **`window.s4Generate`** (not a bare local function).
- (b) Name **matches exactly** the `s4Generate` in the onclick.

## 3. Contrast — the working s4Lock
- Button onclick (line 482): `onclick="s4Lock()"`
- Definition (line 226): `"  window.s4Lock = function(){"`

Generate follows the same `window.*` pattern correctly. The emitted IIFE was run through `node --check` → **JS SYNTAX: OK** (no syntax error breaking the script, so s4Keep/s4Change/s4Lock/s4Generate all define).

## 4. _JSON_PATHS membership
`app.py` line 3550 — **present**:
```python
_JSON_PATHS = {..., "/meal-wizard-step4-confirm", "/meal-wizard-step4-remove", "/meal-wizard-step4-lock", "/meal-wizard-generate"}
```
So the `{}` body is **not** eaten by the form-parser.

## 5. Does the POST arrive?
**Yes — it already did, and returned 200.** From the server log:
```
20:22:01  GET  /meal-wizard-step4            200
20:23:06  POST /meal-wizard-generate         200   <- arrived, ~65s round-trip
20:25:51  POST /meal-wizard-step4-confirm    200
20:25:51  GET  /meal-wizard-step4            200
```
Crucially, **there is no `GET /meal-wizard-step4` immediately after the 20:23:06 generate POST.** `s4Generate` only reloads when `j.ok` is truthy; the absence of a reload means the JSON body came back **without `ok: true`**. The session confirms it: `suggested_meals keys: []` (nothing was written).

---

## Conclusion (root cause)
The button -> JS -> route wiring is **entirely correct**. The failure is **server-side in the handler's response shape**, not the click path.

In `app.py` (`/meal-wizard-generate`, lines 10886–10918), the success path returns `{"ok": True, ...}` (line 10914) and writes `suggested_meals`. But **every failure path returns an error object with no `ok` key**:
- No API key -> `{"error": "No API key set in Settings"}` (line 10898)
- Any exception (e.g. the Anthropic call raising) -> `except Exception as _ge: _g_result = {"error": str(_ge)}` (lines 10917–10918)

All of these still send **HTTP 200** (line 10919) but with a body where `j.ok` is falsy. So the client takes the `else` branch — re-enables the button, shows the `s4-gen-msg` text — and never reloads. To the user that looks like "the button does nothing," and `suggested_meals` stays empty.

## Suggested next step (not yet done)
- Inspect what `str(_ge)` actually was for the 20:23:06 call — most likely an Anthropic API error surfaced by `raise_for_status()` at line 10909 (model string, credit, or key issue).
- Consider surfacing `j.error` in `s4-gen-msg` instead of a generic message, so the real failure is visible to the user.
