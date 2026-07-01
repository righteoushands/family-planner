# Step 4 mirror write — three follow-ups (2026-07-01)

## 1. Harness assertions rewritten (L209–231) — 17/17 PASS

The two remove-section checks were flipped from "reverted slot must be EMPTY" to
"reverted slot must show the LAST-CONFIRMED value, in the entry state."

Discriminator basis: the `s4-name--{key}` **textarea** id only renders in the
empty/entry branch of `_s4_slot_block`; a confirmed row shows the name in a static
div and has no such textarea. So `name_id` present + value present proves
"reverted to entry state AND pre-filled with the last value."

Updated assertions:

```python
        _rj = json.loads(raw)
        _rm_name_id = "s4-name--" + _D1 + "--dinner"
        _check("slot_html" in _rj and _rm_name_id in _rj["slot_html"]
               and "Chicken Parm" in _rj["slot_html"]
               and "lock_html" in _rj and "s4-lock-control" in _rj["lock_html"],
               "remove response reverts to entry state showing the last-confirmed value",
               "remove response did not show the last-confirmed value in entry state",
               failures)
        st, html = _get("/meal-wizard-step4", token)
        name_id = "s4-name--" + _D1 + "--dinner"
        _check(st == 200 and (name_id in html) and ("Chicken Parm" in html),
               "removed slot returns to entry state showing the last-confirmed value",
               "removed slot did not show the last-confirmed value in entry state",
               failures)
```

Result: `PASS all G1b-2a write-loop + guard checks passed` — all 17 checks green.

## 2. Does /meal-wizard-generate read/branch on suggested_meals[slot]["source"]? — NO

The generate handler (app.py ~10928) never reads `suggested_meals` at all before
writing, and never reads `source`. Its slot selection comes entirely from
`wizard_target_slot_keys(session)`, which reads only **confirmed_meals**
(render_meal_wizard_gen.py 36–64):

```python
    slots = session.get("confirmed_what_to_plan") or []
    confirmed = session.get("confirmed_meals") or {}
    ...
        for slot in slots:
            k = d.isoformat() + "::" + str(slot)
            if k not in confirmed:      # <-- only confirmed_meals gates a slot
                keys.add(k)
```

The handler then writes the fresh draft with a wholesale replace:

```python
    _g_suggestions = parse_wizard_meal_response(_g_text, _g_targets)
    update_meal_wizard_session({"suggested_meals": _g_suggestions})
```

So generate does not skip/branch on `source`, and `parse_wizard_meal_response`
re-tags every entry `source='lorenzo'` itself.

**Does the mirror write omitting `source` matter anywhere? No.**
- No reader branches on `suggested_meals[...]["source"]`. The render prefill path
  (`_s4_slot_block` empty branch) reads only `slot_dishes(suggestion)` (name /
  ingredients / protein) — never `source`.
- `_s4_has_lockable` reads `source` only on **confirmed_meals**, not suggested.
- On the next generate, `suggested_meals` is fully replaced, so the source-less
  mirror entry is discarded regardless.

The only source-less-entry consequence is cosmetic-adjacent and correct: a reverted
slot shows Lauren's last value with no "Lorenzo" chip (the chip is a confirmed-row
tag, and the entry-state textarea has no chip anyway).

## 3. Mirror write only touched the target key — neighbor proven untouched

Isolated in-process harness (`data/verify_mirror_neighbor_untouched.py`, Rule 10a):
seeded a real Lorenzo suggestion at the NEIGHBOR slot `2026-06-29::lunch`, then
confirmed the TARGET slot `2026-06-29::dinner`.

```
BEFORE suggested_meals[2026-06-29::lunch] (neighbor):
  {"dishes": [{"category":"main","ingredients":"tuna, bread, cheese","name":"Lorenzo Tuna Melt","protein":"tuna"}], "source": "lorenzo"}
BEFORE suggested_meals[2026-06-29::dinner] (target):
  null

POST /meal-wizard-step4-confirm dinner -> 200 True

AFTER suggested_meals[2026-06-29::lunch] (neighbor):
  {"dishes": [{"category":"main","ingredients":"tuna, bread, cheese","name":"Lorenzo Tuna Melt","protein":"tuna"}], "source": "lorenzo"}
AFTER suggested_meals[2026-06-29::dinner] (target):
  {"dishes": [{"category":"main","ingredients":"","name":"Chicken Parm","protein":"chicken"}]}

neighbor untouched (byte-identical, source='lorenzo' kept): True
target written with mirrored dishes[]: True
suggested_meals keys after == {lunch, dinner} only: True
RESULT: PASS
```

The neighbor's Lorenzo entry (dishes[] AND `source='lorenzo'`) is byte-identical
before/after; only `2026-06-29::dinner` was added. This holds because the handler
loads the full existing `suggested_meals`, sets just the one target key, and writes
the whole dict back — `update_meal_wizard_session` replaces `suggested_meals` with
that same-plus-one dict, so untouched keys survive verbatim.
