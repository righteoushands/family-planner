---
name: meal-wizard session update is top-level replace
description: update_meal_wizard_session does dict.update at top level, so writing a whole nested key wholesale-replaces it
---

`update_meal_wizard_session(updates)` does `session.update(updates)` — a shallow,
top-level merge. Any nested top-level key (e.g. `suggested_meals`, a dict keyed by
`date::slot`) passed in **replaces the entire nested dict**; sibling inner keys not
present in the new value are dropped.

**Why:** This silently wiped Step 4 confirm-mirror entries: `/meal-wizard-generate`
wrote `{"suggested_meals": _g_suggestions}` (only its targets), erasing mirror
entries for confirmed slots. `wizard_target_slot_keys` excludes confirmed slots
from generate targets, so those keys never came back on their own.

**How to apply:** To preserve sibling entries in a nested session map, read the
existing value, `.update()` the new keys onto it, then write the merged dict — do
not pass the partial dict directly. This is a general file-backed-session race-free-
ish read-merge-write; note a true concurrent-writer race still exists (stale
snapshot) but is pre-existing.
