# PROJECT_STATE.md regenerated — full live re-scan (2026-07-01)

## claud.md read-back (Rule 15) — done
All rules pasted back in the chat: Python 3.11 hard rules **1–12 including 10a**,
data/route/AI patterns, anchor-tag navigation, change discipline, the FROL-form
trap, and additional rules **13–20**, plus the June 28 2026 correction log.

**Rules that apply to this task (regeneration of a doc):**
- **15** — read-back (done).
- **10 / 10a** — must be *documented* in the doc, and I must not violate them
  (I did not touch any harness).
- **3 / route patterns** — the doc's route/handler counts must be current.
- **14 pre-flight** — 1 file touched (PROJECT_STATE.md); no JS-in-f-strings; no
  form handling; not a fix (a regeneration); data-shape (dishes[]) reflected.
- **Change discipline** — "regeneration only, do not modify any other file."
  Only `PROJECT_STATE.md` was written.
- Rules 1,2,4,6,7,8,11,12 (Python coding) don't apply — this is a Markdown doc.

## The three required confirmations

### 1. `dishes[]` slot shape reflected (NOT the old flat shape) ✅
The meal-wizard data contract now documents the canonical shape:
`slot = { "dishes": [ {category, name, ingredients, protein}, … ] }`.
- New subsection **"Meal-wizard slot data contract (`dishes[]`)"** in Section 3.
- `data_helpers.slot_dishes()` documented as the **only** read-time migrator
  (flat `{name,ingredients,protein}` or bare string → one `{category:"main",…}`
  dish, **on read only**, never rewriting stored data).
- `render_meals.format_dish_list()` (dishes → display string) and
  `recompute_used_proteins()` (proteins derived from each slot's dishes)
  documented. The generator (`render_meal_wizard_gen.py`) is noted as normalizing
  Lorenzo's still-flat per-slot JSON into `dishes[]` before writing.
- `confirmed_meals` / `suggested_meals` keys corrected to `"YYYY-MM-DD::slot"`.
- Section 5 adds `slot_dishes`, `get_confirmed_meals`, `recompute_used_proteins`.
- The old flat `name/ingredients/protein` description is gone from the contract.

### 2. Rule 10a + `mw_test_isolation` noted ✅
- Section 7 now reproduces **Rule 10a** (was missing) and **Rule 20** (was
  missing) alongside rules 1–19.
- New Section 3 subsection **"Test infrastructure (data/)"** documents
  `data/mw_test_isolation.py` (141 lines) — `assert_isolated()`, `start_server()`,
  and the import-time `_enforce_first_project_import()` that raises `ImportError`
  if `config`/`data_helpers`/`render_*` was imported first (structural Rule 10a).
- `data/verify_rule10a_badorder_fixture.py` (50 lines) documented as the
  deliberately-broken proof fixture, and `verify_meal_wizard_dish_join.py` added
  to the harness inventory.

### 3. Route/handler counts and line counts current (not stale) ✅
Re-derived from live source on 2026-07-01:

| Metric | Old doc | Now (live) |
|---|---|---|
| GET exact-match routes | 100 | **99** |
| GET prefix routes | 16 | **16** |
| POST exact-match routes | 207 | **206** (+ 5 shared `path in (...)` blocks — 4 `elif`, 1 leading `if`; 1 prefix `/quest`) |
| `render_*.py` modules | 60 | **60** |
| `data_helpers.py` top-level funcs | 219 | **220** |
| `data/*.json` files | 61 | **61** |
| app.py | 12287 | **12343** |
| data_helpers.py | 3345 | **3376** |
| render_meals.py | 1721 | **1777** |
| render_meal_wizard_step4.py | 549 | **630** |
| render_meal_wizard_gen.py | 228 | **241** |
| config.py | 175 | **181** |

Other corrections made from the live scan:
- `_JSON_PATHS` location updated to app.py **line 3571**; `do_POST` starts at
  **2268**, `do_GET` at **773**.
- The five shared `elif path in (...)` blocks are now listed (recipe pair,
  subject-upload pair, FROL activity trio, and two config-alias pairs) — the doc
  had only mentioned the recipe exception.
- I diffed every live GET/POST route literal against the doc: **no route is
  missing and none listed no longer exists**, so the route tables are current in
  content; only the counts/characterization needed updating.

## Scope
`PROJECT_STATE.md` is the only file I edited. No code, data, or harness files were
touched by me.

Two other files show as changed in git status but are **not my edits**:
- `data/meal_wizard_session.json` — live runtime session state written by the
  running "Start application" workflow while it serves the app. I deliberately did
  **not** revert it: it is real app data, and reverting would both destroy current
  state and itself be an out-of-scope write.
- `.agents/agent_assets_metadata.toml` — auto-managed by the tool that presents
  this response document.

## Post-review correction
A code review flagged that Section 2 called the shared blocks "5 `elif path in
(...)` blocks." Verified against live source: it is **4 `elif` + 1 leading `if`**
(the `/subject-upload-image` + `/subject-doc-upload` pair uses a leading `if` for
shared multipart parsing). The doc header, the Section 2 paragraph, and the tuple
table (new "Dispatch" column) were corrected accordingly.
