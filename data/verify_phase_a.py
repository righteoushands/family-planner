"""Phase A verification harness — exercises the v3 activity schema,
legacy upgrade path, backup behavior, and round-trip persistence.

Run with: python data/verify_phase_a.py

Does NOT touch live data — operates on a copy in a temp directory."""
import json
import os
import shutil
import sys
import tempfile


def main() -> int:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, repo)
    import data_helpers as dh

    failures = []

    def check(cond, msg):
        if cond:
            print(f"  PASS  {msg}")
        else:
            print(f"  FAIL  {msg}")
            failures.append(msg)

    # ── Isolate: redirect FROL_ACTIVITIES_FILE to a tempdir copy ──────────
    tmp = tempfile.mkdtemp(prefix="frol_phase_a_")
    live = "data/frol_activities.json"
    test_file = os.path.join(tmp, "frol_activities.json")
    test_backup = os.path.join(tmp, "frol_activities.v2_backup.json")
    if os.path.exists(live):
        shutil.copy2(live, test_file)
    else:
        with open(test_file, "w") as f:
            json.dump([], f)

    dh.FROL_ACTIVITIES_FILE = test_file
    dh._ACTIVITIES_V2_BACKUP = test_backup

    print("── 1. Legacy upgrade against a copy of live data ──")
    items = dh.load_frol_activities()
    check(isinstance(items, list), "load_frol_activities returns a list")
    for it in items:
        for f in ("id", "name", "section", "who_type", "who", "leader",
                  "per_person_times", "time", "duration_min", "days",
                  "schedule_variant", "category", "color", "credits",
                  "seasonal", "is_grooming"):
            if f not in it:
                check(False, f"upgraded entry missing field {f}: {it.get('name')!r}")
                break
        else:
            check(True, f"upgraded entry has all 16 fields: {it.get('name','')[:30]!r}")
            continue
        break
    # Backup created only if legacy entries were present.
    had_legacy = any(
        not (it.get("id") and it.get("who_type"))
        for it in (json.load(open(live)) if os.path.exists(live) else [])
        if isinstance(it, dict)
    )
    if had_legacy:
        check(os.path.exists(test_backup), "v2_backup file written when legacy entries detected")

    print("── 2. Round-trip the three who_types ──")
    seeds = [
        {
            "id": "act_test_fam", "name": "Family rosary", "section": 2,
            "who_type": "family",
            "who": ["Lauren","John","JP","Joseph","Michael","James"],
            "leader": "John", "per_person_times": {},
            "time": "19:00", "duration_min": 20,
            "days": ["Monday","Tuesday","Wednesday","Thursday","Friday"],
            "schedule_variant": ["weekday"],
            "category": "prayer", "color": "", "credits": ["xp:5"],
            "seasonal": "year_round", "is_grooming": False,
        },
        {
            "id": "act_test_ind", "name": "JP guitar practice", "section": 11,
            "who_type": "individual", "who": ["JP"], "leader": "",
            "per_person_times": {"JP": {"time": "16:30", "duration_min": 45}},
            "time": "", "duration_min": 0,
            "days": ["Monday","Wednesday","Friday"],
            "schedule_variant": ["weekday"],
            "category": "personal", "color": "", "credits": [],
            "seasonal": "school_year", "is_grooming": False,
        },
        {
            "id": "act_test_mix", "name": "Boys bath time", "section": 9,
            "who_type": "mixed", "who": ["Joseph","Michael","James"], "leader": "Lauren",
            "per_person_times": {
                "Joseph":  {"time": "19:30", "duration_min": 15},
                "Michael": {"time": "19:45", "duration_min": 20},
                "James":   {"time": "18:30", "duration_min": 20},
            },
            "time": "", "duration_min": 0,
            "days": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
            "schedule_variant": ["weekday","saturday","sunday"],
            "category": "chore", "color": "", "credits": [],
            "seasonal": "year_round", "is_grooming": True,
        },
    ]
    base = dh.load_frol_activities()
    dh.save_frol_activities(base + seeds)
    after = dh.load_frol_activities()
    by_id = {a["id"]: a for a in after}
    for seed in seeds:
        rt = by_id.get(seed["id"])
        check(rt is not None, f"{seed['name']!r} survived round-trip")
        if rt:
            check(rt["who_type"] == seed["who_type"],
                  f"{seed['name']!r} who_type preserved")
            check(rt["per_person_times"] == seed["per_person_times"],
                  f"{seed['name']!r} per_person_times preserved")
            check(rt["schedule_variant"] == seed["schedule_variant"],
                  f"{seed['name']!r} schedule_variant preserved")
            check(rt["is_grooming"] == seed["is_grooming"],
                  f"{seed['name']!r} is_grooming preserved")

    print("── 3. Idempotency: re-upgrade a v3 entry is a no-op ──")
    once = dh._upgrade_activity_v2_to_v3(seeds[0])
    twice = dh._upgrade_activity_v2_to_v3(once)
    check(once == twice, "v3 entry upgrade is idempotent")

    print("── 4. Legacy inference rules ──")
    cases = [
        ({"activity_name": "Solo", "who": ["JP"], "time": "08:00", "duration_min": 15},
         "individual", 1),
        ({"activity_name": "Pair", "who": ["JP","Joseph"], "time": "10:00", "duration_min": 30},
         "mixed", 2),
        ({"activity_name": "Family meal", "who": ["Lauren","John","JP","Joseph","Michael","James"],
          "time": "18:00", "duration_min": 45}, "family", 6),
    ]
    for legacy, expected_wt, n_who in cases:
        up = dh._upgrade_activity_v2_to_v3(legacy)
        check(up["who_type"] == expected_wt,
              f"len(who)={n_who} → {expected_wt} (got {up['who_type']})")
        if expected_wt == "family":
            check(up["time"] == legacy["time"] and up["duration_min"] == legacy["duration_min"],
                  "family keeps top-level time/duration")
            check(up["per_person_times"] == {}, "family has empty per_person_times")
        else:
            check(up["time"] == "" and up["duration_min"] == 0,
                  f"{expected_wt} clears top-level time/duration")
            check(all(p in up["per_person_times"] for p in legacy["who"]),
                  f"{expected_wt} populates per_person_times for each person")

    print("── 4b. Individual edit-form field names match POST handler ──")
    # Regression: the edit drawer for individual activities must emit
    # single_time / single_duration_min (not person_<name>_*), because
    # the /frol-edit-activity branch only reads single_* for individual.
    import importlib, render_frol_wizard as _rfw
    importlib.reload(_rfw)
    ind = {
        "id": "act_edit_ind", "name": "Test individual", "section": 5,
        "who_type": "individual", "who": ["JP"], "leader": "",
        "per_person_times": {"JP": {"time": "07:00", "duration_min": 15}},
        "time": "", "duration_min": 0,
        "days": ["Monday"], "schedule_variant": ["weekday"],
        "category": "personal", "color": "", "credits": [],
        "seasonal": "year_round", "is_grooming": False,
    }
    edit_html = _rfw._render_activity_edit_form(ind, 5, "structured")
    check('name="single_time"' in edit_html,
          "individual edit form emits name=\"single_time\"")
    check('name="single_duration_min"' in edit_html,
          "individual edit form emits name=\"single_duration_min\"")
    check('name="who_single"' in edit_html and 'value="JP"' in edit_html,
          "individual edit form emits hidden who_single=JP")
    check('name="person_JP_time"' not in edit_html,
          "individual edit form does NOT emit person_<name>_time (would never persist)")
    check('name="active_variant"' in edit_html,
          "edit form includes active_variant hidden fallback")

    print("── 5. Delete + add round-trip ──")
    items = dh.load_frol_activities()
    items = [a for a in items if a["id"] != "act_test_fam"]
    dh.save_frol_activities(items)
    after_del = dh.load_frol_activities()
    check(not any(a["id"] == "act_test_fam" for a in after_del),
          "deleted activity is gone after save")

    print("── 6. Backup is one-shot (does not overwrite) ──")
    if os.path.exists(test_backup):
        first_size = os.path.getsize(test_backup)
        dh._ensure_activities_backup()
        check(os.path.getsize(test_backup) == first_size,
              "_ensure_activities_backup is idempotent")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n── Result: {len(failures)} failure(s) ──")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
