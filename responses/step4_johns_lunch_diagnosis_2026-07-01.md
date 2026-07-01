# Step 4 — John's Lunch diagnosis

**Date:** 2026-07-01  
**Source:** live `meal_wizard_session.json` (read-only) + `render_meal_wizard_step4.py` lines 363–401

---

## 1. What's stored in `confirmed_meals[date::johns_lunch]["dishes"]`

**Key `2026-07-01::johns_lunch`** — 1 dish:
```json
[
  {
    "category": "main",
    "name": "Packed Rotisserie Chicken & Sourdough Sandwich with Grapes",
    "ingredients": "rotisserie chicken, sourdough bread, shredded cheese, carrots, green grapes",
    "protein": "rotisserie chicken"
  }
]
```

**Key `2026-07-02::johns_lunch`** — 2 dishes (Keep persisted both):
```json
[
  {
    "category": "main",
    "name": "Leftover Ground Beef Pasta Thermos",
    "ingredients": "leftover ground beef pasta, spaghetti sauce, shredded cheese",
    "protein": "ground beef"
  },
  {
    "category": "bread",
    "name": "Garlic bread",
    "ingredients": "",
    "protein": ""
  }
]
```

**Keep DID persist multiple dishes correctly.** Both dishes are in storage for 2026-07-02. Storage is not the bug.

---

## 2. What's stored in `suggested_meals[date::johns_lunch]["dishes"]`

The mirror written by Keep is identical to confirmed_meals in both cases:

**`2026-07-01::johns_lunch`** — 1 dish (matches confirmed exactly).

**`2026-07-02::johns_lunch`** — 2 dishes (matches confirmed exactly):
```json
[
  { "category": "main", "name": "Leftover Ground Beef Pasta Thermos", ... },
  { "category": "bread", "name": "Garlic bread", "ingredients": "", "protein": "" }
]
```

Both dishes are in suggested_meals. The mirror is correct and complete. Storage is not losing the sides.

---

## 3. Does `_s4_slot_block`'s empty-branch prefill only ever rebuild one row?

**Yes — confirmed by reading the code directly, lines 363–401.**

Here is the full prefill block (lines 363–370):

```python
if isinstance(suggestion, dict):
    _sug_dishes = slot_dishes(suggestion)
    _sug0 = _sug_dishes[0] if _sug_dishes else {}      # ← only dish 0
    name_body = escape(_sug0.get("name") or "")
    ing_body  = escape(_sug0.get("ingredients") or "")
    sug_prot  = escape(_sug0.get("protein") or "")
    prot_val  = ' value="' + sug_prot + '"'
    ing_open  = " open"
```

`slot_dishes(suggestion)` reads ALL dishes from the suggestion. But then `_sug0 = _sug_dishes[0]` immediately discards everything except the first element. `_sug_dishes[1:]` is never touched again.

The HTML returned (lines 374–401) then renders **exactly one `<div class="s4dr">`** using `name_body`, `ing_body`, `prot_val` — all of which come from `_sug0` alone:

```python
return (
    f'<div id="s4-row--{key}" ...>'
    f'<div id="s4-dishes--{key}">'
    f'<div class="s4dr">'          # ← one row, hardcoded, no loop
    f'<select data-role="cat">...</select>'
    f'<textarea data-role="name">{name_body}</textarea>'   # ← dish 0 name
    f'<textarea data-role="ing">{ing_body}</textarea>'     # ← dish 0 ingredients
    f'<input data-role="prot"{prot_val}>'                  # ← dish 0 protein
    f'<button data-role="rm" style="display:none;">Remove</button>'
    f'</div>'                      # ← closes the single .s4dr
    f'</div>'                      # ← closes s4-dishes-- container
    ...
)
```

There is no loop, no `for d in _sug_dishes[1:]`, no additional `.s4dr` rendered for dishes at index 1 or beyond. One row is always emitted, regardless of how many dishes are in the suggestion.

---

## Conclusion

The bug is in the **render**, not storage.

| Layer | Status |
|---|---|
| `confirmed_meals[2026-07-02::johns_lunch]["dishes"]` | Correct — 2 dishes stored |
| `suggested_meals[2026-07-02::johns_lunch]["dishes"]` | Correct — 2 dishes mirrored |
| `_s4_slot_block` prefill (entry-state after Change) | **Bug — only dish[0] is ever rendered; dishes[1+] are silently dropped** |

**Sequence that produces Lauren's experience:**

1. Lauren has a reverted slot (entry state). She adds a second row via "+ Add a dish".
2. She fills in: row 0 = "Leftover Ground Beef Pasta Thermos" (main), row 1 = "Garlic bread" (bread).
3. She clicks "Keep this meal". `s4Keep` sends both dishes. Server stores both. Confirmed view shows `format_dish_list` output: *"Leftover Ground Beef Pasta Thermos with Garlic bread"* — correct.
4. She clicks "Change". `s4Change` removes the entry from `confirmed_meals`, mirrors it to `suggested_meals` (still 2 dishes), returns the server-rendered entry-state slot HTML.
5. `_s4_slot_block` is called with `suggestion = suggested_meals["2026-07-02::johns_lunch"]` (2 dishes). It reads them, takes only `_sug0` (the pasta), and renders **one row**. Garlic bread is silently gone from the UI.
6. Lauren sees one row where she had two. From her view: the side dish disappeared.

The fix (not implemented here per scope) is to loop over all `_sug_dishes` in the prefill block and emit one `.s4dr` per dish, with the Remove button hidden only on the first row.
