# Rule 10a — enforced in code, not by inspection

## Rule 10 and 10a (pasted back from claud.md, lines 58–71)

**10.** test fixtures must never write to live data: verification harnesses must
always operate on a temp copy of live data files. Never call save_progress,
safe_save_json, or any write helper on live data during testing. Always restore
from backup after any test that touches data files.

**10a.** RULE 10 ADDENDUM — ISOLATION MUST BE STRUCTURAL, NOT PROCEDURAL. Any
verify_*.py harness that reads or writes app data must import its isolation guard
(e.g. mw_test_isolation.assert_isolated) as the literal first import in the file —
before data_helpers, config, or any render_*.py module. The guard must be called
before the first write, and must raise (not warn) if the write target still
resolves to a live path. A harness that skips this ordering is non-compliant with
Rule 10 regardless of whether it happens to include snapshot/restore logic —
snapshot-and-restore-after is not equivalent to never touching live data. When
isolating a new data store beyond the meal wizard, extend the existing isolation
module's pattern (env-var override, defense-in-depth path normalization,
assert_isolated) rather than writing a new one-off mechanism per feature.

---

## What I built (single code change + one broken fixture)

### 1. `data/mw_test_isolation.py` — import-time structural gate
Added `_enforce_first_project_import()`, which runs **at module import time,
before any env-var override logic**. It snapshots `sys.modules` and raises
`ImportError` if `config`, `data_helpers`, or any `render_*` module is already
loaded when `mw_test_isolation` is first imported:

```python
def _enforce_first_project_import():
    offenders = []
    for _name in list(sys.modules):
        if _name == "config" or _name == "data_helpers" or _name.startswith("render_"):
            offenders.append(_name)
    if offenders:
        raise ImportError(
            "Rule 10a violation: mw_test_isolation must be imported BEFORE any "
            "app module that binds a live data path, but these were already "
            "imported first: " + ", ".join(sorted(offenders)) + ". Move "
            "'import mw_test_isolation' above them (it must be the first project "
            "import in the harness)."
        )

_enforce_first_project_import()
```

Why this is the literal reading of Rule 10a, enforced mechanically:
- It runs off `sys.modules`, the actual runtime import record — **not** file
  layout or line numbers. A harness cannot satisfy 10a "by accident of file
  layout"; wrong order fails loudly and immediately.
- It applies to **every present and future** `verify_*.py` that imports
  `mw_test_isolation` — no per-harness wiring, and impossible to opt out of
  without removing the isolation import itself (which `assert_isolated()` then
  catches at the path level).
- It is defense-in-depth **in front of** the existing path guards
  (`assert_isolated()`), not a replacement.

Why it does not false-positive on the legit harnesses:
- The three real harnesses import `mw_test_isolation` before any app module, so
  at first import `sys.modules` holds only stdlib — no offenders.
- `config`/`render_*`/`app` get imported later, via `assert_isolated()` and
  `start_server()`, **after** this module is cached, so the top-level check does
  not re-run. `list(sys.modules)` makes the scan safe against concurrent
  mutation.

### 2. `data/verify_rule10a_badorder_fixture.py` — deliberately broken, stays broken
A fixture that imports `config` **first** and asserts the `ImportError` fires.
Its purpose is to remain non-compliant forever so it can prove the guard works;
it must never be "fixed."

---

## Rule 9 verification (all run, all green)

```
py_compile data/mw_test_isolation.py data/verify_rule10a_badorder_fixture.py  -> OK

bad-order fixture (config imported first):
  ✅ PASS  bad import order raised ImportError: Rule 10a violation ... already
           imported first: config. Move 'import mw_test_isolation' above them ...
  exit=0   (0 == the check fired as required)

re-ran all three standing harnesses WITH the new check:
  verify_meal_wizard_step4.py            -> PASS  exit=0
  verify_meal_wizard_step4_lock.py       -> PASS  exit=0
  verify_meal_wizard_step4_writeloop.py  -> PASS  exit=0
```

Architect review: **PASS** — check is correct, cannot false-positive on legit
harnesses, `sys.modules` scan is safe, existing isolation not weakened.

## Scope
Exactly two files, as instructed: `data/mw_test_isolation.py` (the check) and
`data/verify_rule10a_badorder_fixture.py` (the proof fixture). Nothing else
changed.
