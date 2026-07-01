# Meta follow-ups on the generate-merge fix (2026-07-01)

## 1. What "architect review" actually checked, and by what mechanism

It was a **separate subagent pass**, not the same context grading itself. Via the
`code_review` skill I spawned an architect subagent (alias
`subagent_evaluate_task-distinct-kakarikis`) with its own fresh context. It was
handed: the task description, the relevant file paths, and the current **git diff**
(`includeGitDiff: true`). It then **read** the code and diff independently and
formed a verdict.

Important honest caveats:
- It is a separate agent instance with fresh context, but the **same model
  family** — not an external/third-party system or a human reviewer.
- It **did not re-run** the harnesses. It read the diff and relied on the test
  results I reported (17/17, mirror-survived=True). So its "regression signal is
  strong" is a judgment over my reported numbers plus its own reading of the code
  paths — not an independent execution of the tests.

So: a second independent *reading* pass, not an independent *execution* pass.

## 2. The pre-existing file-backed session race, precisely

It is a classic lost-update on a JSON file with no locking, in two layers:

- **`update_meal_wizard_session` (data_helpers.py):** `load → session.update →
  save`, no lock. Two concurrent callers each load the same base, each apply their
  patch, and the later `save` wins — the earlier caller's write is lost.
  `safe_save_json` makes each individual write atomic (temp + rename, no
  corruption), but atomicity of one write does **not** prevent the lost-update
  across two overlapping read-modify-write cycles.
- **The generate handler compounds it:** `_g_session =
  load_meal_wizard_session()` is read *before* the ~90s Anthropic call, then the
  merged dict is built from that early snapshot and written after. Any
  confirm/remove that lands during those ~90s is absent from `_g_session` and is
  overwritten when generate finally writes (even with the merge, the final
  `update_meal_wizard_session({"suggested_meals": _g_merged})` replaces the whole
  `suggested_meals` key with a value derived from the stale snapshot).

**How I confirmed it predates this change (not assumed):**
- `git log -1 -- data_helpers.py` → the file that owns `load/update/save` (and has
  no locking) was last modified at `d5b57c3` (2026-06-30 22:03), which is **before**
  all of my session commits (`c212603 … 23ec89a`). I never touched
  `update_meal_wizard_session`.
- The `_g_session = load_meal_wizard_session()` early-read and the
  load-then-later-write shape existed in the handler before my edit; my diff added
  only three lines (read existing → `.update()` → write merged) *between* the parse
  and the existing `update_meal_wizard_session` call. Both the mechanism and the
  90s window predate the fix; the merge neither introduces nor closes the race.

## 3. What got written to memory, and where — NOT claud.md

Nothing was added to `claud.md` (confirmed: no numbered rule, grep for my terms
returns nothing — untouched). The note went to the **agent memory directory**:

- `.agents/memory/MEMORY.md` — one index line:
  > `- [MW session shallow update](meal-wizard-session-shallow-update.md) — update_meal_wizard_session is top-level dict.update; writing a whole nested key (suggested_meals) wholesale-replaces it — read-merge-write to keep siblings.`
- `.agents/memory/meal-wizard-session-shallow-update.md` — topic file: the
  shallow-update gotcha (rule / why / how-to-apply) plus a "Merge tradeoff: no
  pruning" section added for point 4 below.

This memory is separate from `claud.md`; it is my cross-session working memory, not
a project rule.

## 4. Stale entries are now never pruned — true; minor, worth logging not fixing

**Confirmed true.** The old wholesale-replace acted as an implicit pruner: every
generate reset `suggested_meals` to just the current run's targets. The merge
removed that, so entries for slots dropped from `confirmed_what_to_plan`, or for
past dates, now persist indefinitely.

**Does any render path treat a stale entry as current? Essentially no.** The only
two readers of `suggested_meals` are in `render_meal_wizard_step4.py`:
- `render_meal_wizard_step4` (L519) → `_s4_day_card`, which loops **dates in the
  planning window × slots in `confirmed_what_to_plan`** and only does
  `suggested.get(date::slot)` inside that gate.
- `render_step4_slot_and_lock` (L494) → looks up a single `date::slot`, and is only
  called for the specific slot the user is actively confirming/removing (which is
  by definition currently rendered, i.e. in window×to_plan).

No reader iterates all `suggested_meals` keys, so stale entries are inert in normal
flow. **The one resurfacing edge:** if a stale `date::slot` later re-enters
window×to_plan while unconfirmed, the empty-slot branch would prefill that old
suggestion as if current.

**Assessment:** low severity — file growth plus that one resurfacing edge. Worth
logging (done, in the memory topic file), not worth a fix right now. If it's ever
addressed, the clean spot is a prune step in generate (drop keys outside
window×to_plan before/after the merge), which would restore pruning without
reintroducing the wholesale-replace that wiped the mirror.
