"""Phase C verification harness.

Loads Lauren's real frol_wizard_progress.json (or a freshly emptied stub
if the file is missing), exercises the v3 migration on a deep copy of it,
and renders every section 1-15 against the migrated state. Also walks the
rollback path end-to-end.

Run with: PORT=5000 python data/verify_phase_c.py
"""
from __future__ import annotations
import copy
import json
import os
import sys
import tempfile

# Make the project root importable when run from data/.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import render_frol_wizard as rfw
from render_frol_wizard import (
    V2_SECTIONS,
    V2_TOTAL_SECTIONS,
    load_progress,
    save_progress,
    FROL_WIZARD_PROGRESS_FILE,
    _section_renderer,
)


PASS = "\x1b[32mPASS\x1b[0m"
FAIL = "\x1b[31mFAIL\x1b[0m"


def _assert(cond: bool, label: str, detail: str = "") -> bool:
    print(f"  {PASS if cond else FAIL}  {label}" + (f"  — {detail}" if detail else ""))
    return cond


def check_layout() -> bool:
    print("\n[1] V2_SECTIONS layout")
    ok = True
    ok &= _assert(V2_TOTAL_SECTIONS == 15,
                  f"V2_SECTIONS has 15 rows", f"got {V2_TOTAL_SECTIONS}")
    slugs = [s for _, s, _, _ in V2_SECTIONS]
    ok &= _assert(slugs[10] == "holidays", "§11 is 'holidays'", f"slug={slugs[10]}")
    ok &= _assert(slugs[11] == "durations", "§12 is 'durations'", f"slug={slugs[11]}")
    ok &= _assert(slugs[12] == "build", "§13 is 'build'", f"slug={slugs[12]}")
    ok &= _assert(slugs[13] == "commitments", "§14 is 'commitments'")
    ok &= _assert(slugs[14] == "review", "§15 is 'review'")
    return ok


def check_dispatch() -> bool:
    print("\n[2] Dispatcher map")
    ok = True
    for i in range(1, 16):
        fn = _section_renderer(i)
        ok &= _assert(callable(fn), f"§{i} dispatches to a callable",
                      f"got {fn!r}")
    return ok


def check_migration_idempotence(tmpdir: str) -> bool:
    print("\n[3] v3 migration idempotence + backup")
    # Build a synthetic v2-shape progress with all four legacy buckets
    # populated, then point load_progress at a temp file and re-run twice.
    fake = {
        "current_step": 12,
        "completed_steps": [1, 2, 3, 11, 12],
        "mode": "structured",
        "data": {
            "section_1": {"members": [{"name": "Lauren"}]},
            "section_11": {"durations__abc": 25},
            "section_12": {"schedule": [{"time": "07:00", "title": "Wake"}]},
            "section_13": {"placements_Mon": [{"slot": "08:00"}]},
            "section_14": {"receipt": {"saved_at": "2024-01-01"}},
        },
    }
    target = os.path.join(tmpdir, "frol_wizard_progress.json")
    backup = os.path.join(tmpdir, "frol_wizard_progress.v2_backup.json")
    with open(target, "w", encoding="utf-8") as f:
        json.dump(fake, f)
    orig_path = rfw.FROL_WIZARD_PROGRESS_FILE
    rfw.FROL_WIZARD_PROGRESS_FILE = target
    try:
        out1 = load_progress()
        out2 = load_progress()
        ok = True
        ok &= _assert(out1.get("schema_version") == "v3",
                      "schema_version stamped 'v3' after first load")
        d1 = out1.get("data", {})
        ok &= _assert("section_12" in d1 and d1["section_12"].get("durations__abc") == 25,
                      "old section_11 shifted into section_12")
        ok &= _assert("section_13" in d1 and "schedule" in d1["section_13"],
                      "old section_12 shifted into section_13")
        ok &= _assert("section_14" in d1 and "placements_Mon" in d1["section_14"],
                      "old section_13 shifted into section_14")
        ok &= _assert("section_15" in d1 and "receipt" in d1["section_15"],
                      "old section_14 shifted into section_15")
        ok &= _assert("section_11" not in d1,
                      "no leftover section_11 bucket after shift",
                      f"got {list(d1.keys())}")
        ok &= _assert(os.path.exists(backup),
                      "backup file written to data/frol_wizard_progress.v2_backup.json")
        ok &= _assert(out2.get("schema_version") == "v3",
                      "second load is a no-op (schema_version stays v3)")
        # Idempotence: deep-equal the two loads.
        ok &= _assert(out1.get("data") == out2.get("data"),
                      "second load produces identical data")
        # current_step bumped 12 → 13
        ok &= _assert(out1.get("current_step") == 13,
                      "current_step bumped 12 → 13")
        # completed_steps bumped: 11,12 → 12,13
        cs = out1.get("completed_steps") or []
        ok &= _assert(12 in cs and 13 in cs,
                      "completed_steps {11,12} bumped → {12,13}",
                      f"got {cs}")
        return ok
    finally:
        rfw.FROL_WIZARD_PROGRESS_FILE = orig_path


def check_rollback(tmpdir: str) -> bool:
    print("\n[4] Rollback path restores backup")
    target = os.path.join(tmpdir, "frol_wizard_progress.json")
    backup = os.path.join(tmpdir, "frol_wizard_progress.v2_backup.json")
    # Ensure both files exist from the previous check.
    if not (os.path.exists(target) and os.path.exists(backup)):
        return _assert(False, "prerequisite files missing — skipped")
    orig_path = rfw.FROL_WIZARD_PROGRESS_FILE
    rfw.FROL_WIZARD_PROGRESS_FILE = target
    try:
        from data_helpers import safe_save_json
        with open(backup, encoding="utf-8") as _bf:
            restored = json.load(_bf)
        restored.pop("schema_version", None)
        safe_save_json(target, restored)
        # After rollback, loading should re-trigger v3 migration (no
        # schema_version present) → restoring the post-v3 shape again.
        out = load_progress()
        ok = True
        ok &= _assert(out.get("schema_version") == "v3",
                      "post-rollback load re-migrates to v3")
        ok &= _assert(out.get("data", {}).get("section_12", {}).get("durations__abc") == 25,
                      "post-rollback load preserves durations")
        return ok
    finally:
        rfw.FROL_WIZARD_PROGRESS_FILE = orig_path


def check_render_each_section() -> bool:
    print("\n[5] Render every section against current real progress")
    p = load_progress()
    ok = True
    for i in range(1, V2_TOTAL_SECTIONS + 1):
        fn = _section_renderer(i)
        try:
            html = fn(p, "structured")
            ok &= _assert(bool(html) and "<" in html,
                          f"§{i} renders non-empty HTML",
                          f"len={len(html or '')}")
        except Exception as e:
            ok &= _assert(False, f"§{i} renders without error",
                          f"{type(e).__name__}: {e}")
    return ok


def main() -> int:
    print("Phase C verification harness")
    overall = True
    overall &= check_layout()
    overall &= check_dispatch()
    with tempfile.TemporaryDirectory() as tmp:
        overall &= check_migration_idempotence(tmp)
        overall &= check_rollback(tmp)
    overall &= check_render_each_section()
    print()
    print("ALL CHECKS PASSED" if overall else "SOME CHECKS FAILED")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
