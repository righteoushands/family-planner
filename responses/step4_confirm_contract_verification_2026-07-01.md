# /meal-wizard-step4-confirm — contract verification (2026-07-01)

I checked the two shapes you listed against the live code before treating them as
a spec. **Your server-write shape is exactly right. Your client-payload shape is
not what the code actually sends.**

## Client payload — MISMATCH

**You wrote:**
```
{ date, slot, dishes: [{category, name, ingredients, protein}, ...],
  source, recipe_id, recipe_on_request }
```

**What the live client actually sends** (`render_meal_wizard_step4.py:222–223`, the `s4Keep` handler — verbatim):
```js
var payload = { date: date, slot: slot, name: name, source: 'manual',
  ingredients: ing, protein: prot, recipe_id: '', recipe_on_request: true };
```

Differences:
- **No `dishes[]` array.** It sends **flat** `name`, `ingredients`, `protein` — a
  single meal, never a list. There is no `category` field on the wire.
- `source` is hardcoded `'manual'`, `recipe_id` hardcoded `''`,
  `recipe_on_request` hardcoded `true` (the UI has no controls for these here).
- It does **not** send `skip_shopping` (server defaults it to `false`).

## Server read — also flat, not `dishes[]`

`/meal-wizard-step4-confirm` (`app.py:10784–10819`) reads flat scalar fields and
**constructs** the single-element `dishes[]` itself (verbatim):
```python
_s4_name = clean_text(_s4_payload.get("name",""))
...
_s4_entry = {
    "dishes": [{
        "category":    "main",
        "name":        _s4_name,
        "ingredients": clean_text(_s4_payload.get("ingredients","")),
        "protein":     clean_text(_s4_payload.get("protein","")),
    }],
    "source":            _s4_source,
    "locked":            True,
    "recipe_id":         clean_text(_s4_payload.get("recipe_id","")),
    "recipe_on_request": _s4_as_bool(_s4_payload.get("recipe_on_request")),
    "skip_shopping":     _s4_as_bool(_s4_payload.get("skip_shopping")),
}
```
So the server would **ignore** a `dishes[]` array if the client sent one — it only
reads `name`/`ingredients`/`protein`, and `category` is hardcoded `"main"`. Only
**one** dish per slot can be confirmed through this route today.

## Server write — MATCHES your description ✓

The persisted `confirmed_meals[date::slot]` shape is exactly what you wrote:
```
{ dishes: [{category, name, ingredients, protein}, ...],
  source, locked, recipe_id, recipe_on_request, skip_shopping }
```
(`dishes[]` is genuinely a list in storage, and `slot_dishes()` migrates older
flat entries on read — but the confirm route only ever puts a single-element list
into it.)

## Net
- **Storage/write shape:** already `dishes[]` — as you described. ✓
- **Client payload + server read:** flat single-dish (`name`/`ingredients`/`protein`),
  **not** the `dishes[]` payload you wrote. ✗

So the wire contract you listed describes a **multi-dish `dishes[]` payload that
does not exist yet** on the client or in the server's reader. The storage is ready
for it; the entry UI and the confirm handler are not.

## I did not change anything
Per your diagnose-before-fixing rule and one-fix-per-instruction, I stopped here to
confirm intent rather than assume. See the question in chat.
