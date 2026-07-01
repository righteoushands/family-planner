# TRACKER — Known Issues

Living log of known issues, debts, and gotchas. Newest first. Entries here are
documented, not necessarily fixed; each notes severity and whether a fix is
planned.

---

## KI-001 — Session helper shallow-merge wipes sibling keys (July 1 2026)
**Area:** `data_helpers.update_meal_wizard_session` / any `load → dict.update → save` session helper.
**Severity:** Medium (was a silent data-loss bug; now fixed at the one known call site).
**Status:** Root cause documented; specific occurrence fixed.

`update_meal_wizard_session(updates)` merges only at the **top level**
(`session.update(updates)`). Passing a whole nested key — e.g.
`{"suggested_meals": {...}}` — **replaces that entire nested dict**, silently
dropping sibling inner keys (other `date::slot` entries).

- **How it bit us:** `/meal-wizard-generate` wrote `{"suggested_meals":
  _g_suggestions}` (only its targets), wiping the Step 4 confirm-mirror entries
  for confirmed slots (which `wizard_target_slot_keys` excludes from generate
  targets, so they never came back).
- **Fix applied:** the generate handler now reads `suggested_meals` **fresh**
  (immediately before the write, not from the pre-model-call snapshot),
  `.update()`s the new targets onto it, and writes the merged dict — so both
  pre-existing mirror entries and any confirm/remove that lands mid-call survive.
- **General rule:** to preserve siblings in a nested session map, read fresh →
  `.update()` → write; never pass the partial nested dict directly. (See claud.md
  Rule 21.)

---

## KI-002 — Merge-based generate no longer prunes stale suggested_meals (July 1 2026)
**Area:** `/meal-wizard-generate` (`app.py`) suggested_meals lifecycle.
**Severity:** Low (housekeeping + one narrow resurfacing edge).
**Status:** Logged, not fixed.

Because `/meal-wizard-generate` now **merges** into `suggested_meals` instead of
wholesale-replacing it, the implicit pruning the old replace performed is gone.
Stale entries — slots dropped from `confirmed_what_to_plan`, or past-date keys —
are never pruned and accumulate in the session file.

- **Render impact:** essentially none in normal flow. The only readers
  (`render_meal_wizard_step4.py`) look up `suggested[date::slot]` for dates in the
  planning window × slots in `confirmed_what_to_plan`; no reader iterates all
  keys, so stale entries are inert.
- **Narrow edge:** a stale `date::slot` that later re-enters window×to_plan while
  unconfirmed would resurface its old suggestion as a prefill (shown as if
  current).
- **If addressed:** prune keys outside window×to_plan inside the generate handler
  (do not revert to wholesale replace — that reintroduces KI-001). (See claud.md
  Rule 22.)
