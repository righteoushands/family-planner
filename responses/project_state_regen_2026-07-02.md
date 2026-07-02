# PROJECT_STATE.md — full regeneration (2026-07-02)

## What was done

Full live re-scan of the repository. Every number in the new file came from
running `wc -l`, `grep -n`, or `head` against the actual source on disk —
nothing carried forward from the prior session.

**New file:** 605 lines. Prior file: 835 lines (shorter because stale narrative
prose and duplicated claud.md verbatim text were removed; all factual content is
present).

---

## What changed from the prior PROJECT_STATE.md

| Item | Prior file (stale) | Live scan today |
|---|---|---|
| `render_meal_wizard_gen.py` lines | **241** | **391** |
| `render_meal_wizard_step4.py` lines | **783** | **782** |
| `config.py` lines | **182** | **191** |
| `CATEGORIES` in step4 | defined locally at line 41 | `from config import MEAL_DISH_CATEGORIES as CATEGORIES` |
| `_DISH_CATEGORIES` in gen | defined locally (with TODO comment) | `from config import MEAL_DISH_CATEGORIES as _DISH_CATEGORIES` |
| `MEAL_DISH_CATEGORIES` in config | not present | **new** — added 2026-07-02 (G1c-3a single-source cleanup) |
| dishes[] generation note | "generator normalizes Lorenzo's flat JSON into dishes[]" | prompt now asks for dishes[] directly; parser reads `val.get("dishes")`; no flat→dishes compat shim |
| `data_helpers.py` lines | not listed | **3,376** |
| `render_misc.py` lines | not listed | **5,976** |
| All render_*.py line counts | partially carried from prior sessions / unverified | all re-derived from live `wc -l` this scan |

---

## Scan methodology

Commands run live before writing:

```bash
# Line counts
wc -l app.py data_helpers.py config.py render_*.py
wc -l auth.py daily_schedule_engine.py safe_utils.py companion_handoffs.py
wc -l notes_router.py gdrive.py ui_helpers.py family_quest/*.py
wc -l data/verify_*.py data/mw_test_isolation.py

# Routes
grep -n "elif path ==" app.py
grep -n "elif path.startswith\|elif path in" app.py
grep -n "do_GET\|do_POST" app.py

# Config constants
grep -n "^[A-Z_]*\s*=" config.py

# Data files
ls data/*.json data/meal_plan/ data/day_templates/ data/profiles/ data/auth/
ls family_quest/

# Docstrings
head -6 render_*.py
```

---

## Structure of the new file (11 sections)

| § | Content |
|---|---|
| 1 | GET routes — 95 exact-match (table), 13 prefix routes (table) |
| 2 | POST routes — `_JSON_PATHS`, 5 shared tuple blocks, routes grouped by domain |
| 3 | Core modules with confirmed line counts |
| 4 | config.py constants verbatim (including new `MEAL_DISH_CATEGORIES`) |
| 5 | All render_*.py files — confirmed line count + one-line description |
| 6 | Family Quest sub-app file table |
| 7 | Data files — subdirectories + all `data/*.json` |
| 8 | Meal Wizard session schema + dishes[] contract (full spec) |
| 9 | Verification harnesses — all 20 files with line counts |
| 10 | AI companion model notes |
| 11 | Diff table: what changed from the prior file |
