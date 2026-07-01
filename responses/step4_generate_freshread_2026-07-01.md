# Generate fresh-read fix + mid-call race test + docs (2026-07-01)

## 1. Code fix — `/meal-wizard-generate` reads `suggested_meals` fresh

The merge base is now read **immediately before** the write, not from the
`_g_session` snapshot taken before the ~90s Anthropic call:

```python
_g_suggestions = parse_wizard_meal_response(_g_text, _g_targets)
# ...read suggested_meals FRESH here (not from _g_session, taken before the
# ~90s model call) so any confirm/remove that landed mid-call is preserved...
_g_merged = (load_meal_wizard_session().get("suggested_meals") or {})
_g_merged.update(_g_suggestions)
update_meal_wizard_session({"suggested_meals": _g_merged})
```

`py_compile app.py` → OK.

## 2. Verification — all three harnesses PASS

| Harness | Result |
|---|---|
| `data/verify_generate_wipes_mirror.py` | **PASS** — mirror survives generate |
| `data/verify_meal_wizard_step4_writeloop.py` | **PASS** — 17/17 checks |
| `data/verify_generate_midcall_race.py` (new) | **PASS** — mid-call write survives |

### New harness: what it proves
Setup — single day, plan breakfast/lunch/dinner:
1. Confirm **dinner** → `suggested_meals[D1::dinner]` mirror written (pre-call).
2. Run generate (targets = breakfast + lunch, dinner excluded). **Inside the
   stubbed Anthropic call** — i.e. after generate captured its early snapshot,
   before generate's own write — a concurrent confirm of **breakfast** writes
   `confirmed_meals` + a `suggested_meals[D1::breakfast]` mirror. The stub then
   returns a menu for **lunch** only.
3. After generate's final write, assert all three survive.

Output:
```
(3) suggested keys after generate: ['2026-06-29::breakfast', '2026-06-29::dinner', '2026-06-29::lunch']
    mid-call breakfast write survived: True
    pre-call dinner mirror survived: True
    generated lunch present: True
RESULT: PASS (mid-call write survived)
```

With the old stale-snapshot code the breakfast write (landing mid-call) would be
clobbered — the merge base predated it. The fresh read preserves it. Rule 10/10a
honored: `mw_test_isolation` imported first, in-process server, live data
untouched; only the external boundary (requests / API key / gen log) is stubbed.

**Architect review: PASS** — "correctly implements the fresh-read merge and meets
the stated objective without regression." It flagged (for later, not now) that the
generic file read-modify-write race in `update_meal_wizard_session` still exists
between the fresh read and save; the fresh read shrinks the window to microseconds
but does not add locking. Out of scope for this fix.

## 3. Docs — no code change

### Added to `claud.md` (two numbered rules + DOC CORRECTION LOG bullet)

```
        21.     SESSION HELPER SHALLOW-MERGE — update_meal_wizard_session (and any
load -> dict.update -> save session helper) merges ONLY at the top level. Passing
a whole nested key such as {"suggested_meals": {...}} REPLACES that entire nested
dict, silently dropping sibling inner keys (e.g. other date::slot entries). To
preserve siblings, read the current value FRESH, .update() the new keys onto it,
then write the merged dict. Read that snapshot immediately before the write — not
before a long-running step (e.g. a ~90s AI call) — or a concurrent write landing
mid-call is clobbered by the stale snapshot.
[KNOWN DEVIATION, logged July 1 2026: this bit the Step 4 confirm-mirror —
/meal-wizard-generate wrote {"suggested_meals": _g_suggestions} and wiped the
mirror entries for confirmed slots. Fixed by fresh-read + merge in the generate
handler.]
        22.     MERGE-BASED GENERATE NO LONGER PRUNES — Because /meal-wizard-generate
now merges into suggested_meals instead of replacing it, stale entries (slots
dropped from confirmed_what_to_plan, or past-date keys) are never pruned and
accumulate in the session file. Render is gated: the only readers look up
suggested[date::slot] for dates in the planning window × slots in
confirmed_what_to_plan, so stale entries are inert — EXCEPT a stale date::slot
that later re-enters window×to_plan while unconfirmed will resurface its old
suggestion as a prefill. Low severity; logged not fixed. If addressed, prune keys
outside window×to_plan in the generate handler rather than reverting to wholesale
replace. Cross-ref: TRACKER_Known_Issues.md KI-001 / KI-002.
```

DOC CORRECTION LOG:
```
        •       July 1 2026: added Rules 21 (session helper shallow-merge wipes
sibling keys) and 22 (merge-based generate no longer prunes stale
suggested_meals), surfaced by the Step 4 confirm-mirror diagnosis + fix pass;
also filed as TRACKER_Known_Issues.md KI-001 / KI-002.
```

### Created `TRACKER_Known_Issues.md` (did not exist — no file by that name found)

```
# TRACKER — Known Issues

Living log of known issues, debts, and gotchas. Newest first. Entries here are
documented, not necessarily fixed; each notes severity and whether a fix is
planned.

---

## KI-001 — Session helper shallow-merge wipes sibling keys (July 1 2026)
**Area:** data_helpers.update_meal_wizard_session / any load -> dict.update -> save session helper.
**Severity:** Medium (was a silent data-loss bug; now fixed at the one known call site).
**Status:** Root cause documented; specific occurrence fixed.

update_meal_wizard_session(updates) merges only at the top level
(session.update(updates)). Passing a whole nested key — e.g.
{"suggested_meals": {...}} — replaces that entire nested dict, silently dropping
sibling inner keys (other date::slot entries).

- How it bit us: /meal-wizard-generate wrote {"suggested_meals": _g_suggestions}
  (only its targets), wiping the Step 4 confirm-mirror entries for confirmed
  slots (which wizard_target_slot_keys excludes from generate targets, so they
  never came back).
- Fix applied: the generate handler now reads suggested_meals fresh (immediately
  before the write, not from the pre-model-call snapshot), .update()s the new
  targets onto it, and writes the merged dict — so both pre-existing mirror
  entries and any confirm/remove that lands mid-call survive.
- General rule: to preserve siblings in a nested session map, read fresh ->
  .update() -> write; never pass the partial nested dict directly. (See claud.md
  Rule 21.)

---

## KI-002 — Merge-based generate no longer prunes stale suggested_meals (July 1 2026)
**Area:** /meal-wizard-generate (app.py) suggested_meals lifecycle.
**Severity:** Low (housekeeping + one narrow resurfacing edge).
**Status:** Logged, not fixed.

Because /meal-wizard-generate now merges into suggested_meals instead of
wholesale-replacing it, the implicit pruning the old replace performed is gone.
Stale entries — slots dropped from confirmed_what_to_plan, or past-date keys —
are never pruned and accumulate in the session file.

- Render impact: essentially none in normal flow. The only readers
  (render_meal_wizard_step4.py) look up suggested[date::slot] for dates in the
  planning window × slots in confirmed_what_to_plan; no reader iterates all keys,
  so stale entries are inert.
- Narrow edge: a stale date::slot that later re-enters window×to_plan while
  unconfirmed would resurface its old suggestion as a prefill (shown as if
  current).
- If addressed: prune keys outside window×to_plan inside the generate handler
  (do not revert to wholesale replace — that reintroduces KI-001). (See claud.md
  Rule 22.)
```

## Files touched
- `app.py` — fresh-read in `/meal-wizard-generate` (1 line changed + comment).
- `data/verify_generate_midcall_race.py` — new harness.
- `claud.md` — Rules 21 & 22 + DOC CORRECTION LOG bullet.
- `TRACKER_Known_Issues.md` — new file, KI-001 & KI-002.
