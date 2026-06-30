# DIAGNOSIS — /meal-wizard-generate ACTUAL failure (reproduced in-process)

**Scope:** Read-only. Nothing changed, nothing written. The Anthropic call was reproduced in-process against Lauren's real current session; no `suggested_meals` save was performed (print-only).

---

## 1. Exact model string
`app.py` line 10905:
```python
json={"model": "claude-sonnet-4-6",
```
It **is** `claude-sonnet-4-6`, as G1c-1b claimed. **This is NOT the problem** — the call returns HTTP 200 (see below).

## 2. Timeout value
`app.py` line 10908 — this uses the `requests` library (not urllib):
```python
timeout=90)
```
So **timeout = 90 seconds**. The 65s-timeout theory is **disproven**: the call completed well under 90s and returned 200.

## 3. In-process reproduction (Lauren's real session, current week)
Loaded the same session via `load_meal_wizard_session()`, built the prompt via `build_wizard_meal_prompt()` over `wizard_target_slot_keys()`, made the identical API call, and ran `parse_wizard_meal_response()` — print only, no save.

```
model used         : claude-sonnet-4-6
num target slots   : 55
api key present     : True
http status         : 200
stop_reason         : max_tokens          <-- TRUNCATED
usage.output_tokens : 4096                 <-- hit the cap exactly
response text len   : 13409 chars
has opening ```json : True
has closing ```     : False                <-- no closing fence
``` fence count     : 1                     (opening only)
fence regex match   : False                <-- parser's fenced-JSON path fails
brace regex match   : True
brace json.loads    : FAIL -> JSONDecodeError: Expecting ',' delimiter: line 329 column 8
last 120 chars      : '...batch rice base"\n      },\n      "feast_meal": {'   <-- cut off mid-object
parse succeeded     : False | count: 0
```

## 4. Reconstruction was faithful
The current session **was** reproduced in-process (real data, 55 real target slots) — no seeded/fabricated test. The result above is the genuine failure.

---

## ROOT CAUSE (proven, not guessed)
The model, API key, route, timeout, and client-side JS are all **fine**. The failure is a **truncated response that the parser cannot read**:

1. The session has **55 empty target slots** (full week × up to 7 slot kinds). Generating a full meal object (`name`/`protein`/`ingredients`/`note`) for each needs far more than **4096 output tokens**.
2. The model hits the cap: `stop_reason = max_tokens`, `output_tokens = 4096`. The JSON is cut off mid-object (`"feast_meal": {` with no value).
3. `parse_wizard_meal_response` (`render_meal_wizard_gen.py` ~59–85) then fails on **both** of its paths:
   - The fenced-JSON regex `` ```json ... ``` `` requires a **closing** ` ``` ` — there is none (only 1 fence) → no match.
   - The greedy `{ ... }` brace match captures the truncated object → `json.loads` raises `JSONDecodeError`; the trailing-comma cleanup also fails because braces are unbalanced.
   - `parsed` stays `{}` → the function returns `{}`.
4. The handler's success branch therefore returns `{"ok": True, "generated": 0, "target": 55, "suggested_meals": {}}` and writes an **empty** `suggested_meals`. To Lauren the page reloads with **no meals filled in** — indistinguishable from "the button does nothing." (This also matches the observed `suggested_meals keys: []`.)

## Fix options (for the NEXT phase — not done here)
Any one of these, or a combination:
- **Raise `max_tokens`** for this call (e.g. 8192+), since 55 slots needs more room. Note even 8192 may be tight for 55 full objects — measure.
- **Chunk the generation** (batch the target slots across multiple calls) so each response stays within the token budget.
- **Harden `parse_wizard_meal_response`** to tolerate truncation: when `stop_reason == "max_tokens"` or the fence has no closer, salvage complete slot objects from the partial JSON instead of all-or-nothing `json.loads`.
- Optionally have the handler treat `generated: 0` as a soft error so the UI tells Lauren "couldn't generate, try again" instead of silently reloading an empty page.
