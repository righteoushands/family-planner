"""Phase E verification harness.

Exercises the §15 three-way save flow end-to-end without touching the
permanent day_templates dir. Uses temporary dirs swapped in via
monkeypatch so the real user data is never modified.

Run with:  PYTHONPATH=. python data/verify_phase_e.py
"""
import json
import os
import shutil
import sys
import tempfile

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT     = os.path.dirname(THIS_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config
import render_frol_wizard as rfw


_FAKE_SCHEDULE = {
    "weekday": [
        {"time": "06:30", "activity_name": "Morning prayer",
         "who": ["Lauren", "John"], "category": "prayer",
         "duration_min": 15, "note": "", "keep": True},
        {"time": "12:00", "activity_name": "Angelus",
         "who": ["Lauren"], "category": "prayer",
         "duration_min": 5,  "note": "", "keep": True},
        {"time": "21:30", "activity_name": "Night prayer",
         "who": ["Lauren", "John"], "category": "prayer",
         "duration_min": 10, "note": "", "keep": True},
    ],
    "saturday": [
        {"time": "08:00", "activity_name": "Family chores",
         "who": ["Lauren", "John", "JP", "Joseph"], "category": "chores",
         "duration_min": 60, "note": "", "keep": True},
    ],
    "sunday": [
        {"time": "10:00", "activity_name": "Mass",
         "who": ["Lauren", "John", "JP", "Joseph", "Michael", "James"],
         "category": "prayer", "duration_min": 90, "note": "", "keep": True},
    ],
    "john_traveling": [
        {"time": "06:30", "activity_name": "Solo morning prayer",
         "who": ["Lauren"], "category": "prayer",
         "duration_min": 10, "note": "", "keep": True},
        {"time": "21:00", "activity_name": "Earlier solo bedtime",
         "who": ["Lauren"], "category": "rest",
         "duration_min": 0, "note": "John is away", "keep": True},
    ],
}


def _fake_progress():
    sec13 = {}
    for v, sched in _FAKE_SCHEDULE.items():
        sec13[v] = {"schedule": list(sched), "questions": [], "answers": {}}
    return {"data": {"section_13": sec13}, "current_step": 15}


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    tmp = tempfile.mkdtemp(prefix="phase_e_")
    perm_dir   = os.path.join(tmp, "permanent")
    prev_dir   = os.path.join(tmp, "preview")
    backup_dir = os.path.join(tmp, "backups")
    os.makedirs(perm_dir, exist_ok=True)

    # Seed permanent with a single existing file so backup has something to copy
    with open(os.path.join(perm_dir, "Monday.json"), "w", encoding="utf-8") as f:
        json.dump({"weekday": "Monday", "grid": {"Mom": {"6:00 AM": "OLD"}}}, f)

    # Monkey-patch every reference to the three dirs.
    orig = (
        config.DAY_TEMPLATES_DIR, config.DAY_TEMPLATES_PREVIEW_DIR,
        config.DAY_TEMPLATES_BACKUP_DIR,
        rfw.DAY_TEMPLATES_DIR, rfw.DAY_TEMPLATES_PREVIEW_DIR,
        rfw.DAY_TEMPLATES_BACKUP_DIR,
    )
    config.DAY_TEMPLATES_DIR         = perm_dir
    config.DAY_TEMPLATES_PREVIEW_DIR = prev_dir
    config.DAY_TEMPLATES_BACKUP_DIR  = backup_dir
    rfw.DAY_TEMPLATES_DIR            = perm_dir
    rfw.DAY_TEMPLATES_PREVIEW_DIR    = prev_dir
    rfw.DAY_TEMPLATES_BACKUP_DIR     = backup_dir

    failures = []
    def check(cond, msg):
        if cond:
            print(f"  ok  {msg}")
        else:
            print(f"  FAIL {msg}")
            failures.append(msg)

    try:
        # ── 1. HH:MM 24h → 12h label converter ───────────────────────────
        print("\n[1] _s15_hhmm24_to_label12")
        check(rfw._s15_hhmm24_to_label12("06:30") == "6:30 AM", "06:30 -> 6:30 AM")
        check(rfw._s15_hhmm24_to_label12("12:00") == "12:00 PM", "12:00 -> 12:00 PM")
        check(rfw._s15_hhmm24_to_label12("00:15") == "12:15 AM", "00:15 -> 12:15 AM")
        check(rfw._s15_hhmm24_to_label12("21:30") == "9:30 PM", "21:30 -> 9:30 PM")
        check(rfw._s15_hhmm24_to_label12("bogus") == "", "bogus -> ''")
        check(rfw._s15_hhmm24_to_label12("25:00") == "", "25:00 -> ''")

        # ── 2. grid builder ──────────────────────────────────────────────
        print("\n[2] _s15_build_grid_from_schedule")
        g = rfw._s15_build_grid_from_schedule(_FAKE_SCHEDULE["weekday"])
        check("Lauren" in g and "John" in g, "Lauren and John present")
        check(g["Lauren"].get("6:30 AM") == "Morning prayer",
              "Lauren 6:30 AM = Morning prayer")
        check(g["John"].get("9:30 PM") == "Night prayer",
              "John 9:30 PM = Night prayer")
        check("Angelus" not in (g.get("John") or {}).values(),
              "John has NO Angelus (Lauren-only slot)")
        # keep=False should drop the slot
        bad = [{"time": "07:00", "activity_name": "Skipme",
                "who": ["Lauren"], "keep": False}]
        check(rfw._s15_build_grid_from_schedule(bad) == {},
              "keep=False dropped")

        # ── 3. preview write ─────────────────────────────────────────────
        print("\n[3] Preview write")
        check(not rfw.s15_preview_active(), "preview NOT active initially")
        progress = _fake_progress()
        written = rfw.s15_write_variants_to_dir(progress, prev_dir)
        check(set(written) == {"Monday","Tuesday","Wednesday","Thursday",
                               "Friday","Saturday","Sunday","JohnTraveling"},
              "all 8 stems written")
        check(rfw.s15_preview_active(), "preview now active")
        # spot-check Monday content
        mon = _read_json(os.path.join(prev_dir, "Monday.json"))
        check(mon["weekday"] == "Monday", "Monday.weekday == 'Monday'")
        check(mon["frol_meta"]["variant"] == "weekday",
              "Monday.frol_meta.variant == 'weekday'")
        check(mon["grid"]["Lauren"].get("6:30 AM") == "Morning prayer",
              "Monday Lauren 6:30 AM correct")
        jt = _read_json(os.path.join(prev_dir, "JohnTraveling.json"))
        check(jt["frol_meta"]["variant"] == "john_traveling",
              "JohnTraveling.frol_meta.variant == 'john_traveling'")
        check("John" not in jt["grid"],
              "JohnTraveling has NO John column")

        # ── 4. discard preview ───────────────────────────────────────────
        print("\n[4] Discard preview")
        check(rfw.s15_discard_preview(), "discard returns True")
        check(not rfw.s15_preview_active(), "preview gone after discard")

        # ── 5. permanent save (with backup) ──────────────────────────────
        print("\n[5] Permanent save")
        old_mon = _read_json(os.path.join(perm_dir, "Monday.json"))
        check(old_mon["grid"]["Mom"].get("6:00 AM") == "OLD",
              "pre-save Monday still has OLD")
        bk = rfw.s15_backup_permanent()
        check(bk and os.path.isdir(bk), "backup_dir created")
        bk_files = os.listdir(bk)
        check("Monday.json" in bk_files, "backup contains Monday.json")
        bk_mon = _read_json(os.path.join(bk, "Monday.json"))
        check(bk_mon["grid"]["Mom"].get("6:00 AM") == "OLD",
              "backup preserved OLD content")
        rfw.s15_write_variants_to_dir(progress, perm_dir)
        new_mon = _read_json(os.path.join(perm_dir, "Monday.json"))
        check(new_mon["grid"]["Lauren"].get("6:30 AM") == "Morning prayer",
              "permanent Monday updated to new schedule")
        check("Mom" not in new_mon["grid"] or
              new_mon["grid"].get("Mom", {}).get("6:00 AM") != "OLD",
              "OLD content overwritten")

        # ── 6. preview → promote ─────────────────────────────────────────
        print("\n[6] Promote preview to permanent")
        # mutate the schedule slightly and re-preview
        progress["data"]["section_13"]["weekday"]["schedule"][0]["activity_name"] = "Morning prayer v2"
        rfw.s15_write_variants_to_dir(progress, prev_dir)
        check(rfw.s15_preview_active(), "preview active again")
        receipt = rfw.s15_promote_preview_to_permanent()
        check(receipt.get("promoted", 0) >= 8, "promoted >= 8 files")
        check(receipt.get("backup_dir"), "promote made a backup")
        check(not rfw.s15_preview_active(), "preview gone after promote")
        promoted_mon = _read_json(os.path.join(perm_dir, "Monday.json"))
        check(promoted_mon["grid"]["Lauren"].get("6:30 AM") == "Morning prayer v2",
              "permanent now reflects promoted v2")

        # ── 7. POD reader routing ────────────────────────────────────────
        print("\n[7] get_pod_day_slots routing")
        # No preview, no toggle → reads permanent weekday file
        slots_tue = rfw.get_pod_day_slots("Tuesday", "Mom")
        check(slots_tue.get("6:30 AM") == "Morning prayer v2",
              "Tuesday w/ toggle off reads weekday variant")
        # No preview, Saturday → reads Saturday file
        slots_sat = rfw.get_pod_day_slots("Saturday", "Lauren")
        check(slots_sat.get("8:00 AM") == "Family chores",
              "Saturday reads Saturday file")
        # pod_template_stem
        check(rfw.pod_template_stem("Saturday") == "Saturday",
              "Saturday stem unchanged")
        check(rfw.pod_template_stem("Sunday") == "Sunday",
              "Sunday stem unchanged")

        # ── 8. preview dir overrides permanent ───────────────────────────
        print("\n[8] preview dir takes precedence")
        progress["data"]["section_13"]["weekday"]["schedule"][0]["activity_name"] = "PREVIEW LABEL"
        rfw.s15_write_variants_to_dir(progress, prev_dir)
        check(rfw.s15_preview_active(), "preview live")
        slots_prev = rfw.get_pod_day_slots("Wednesday", "Mom")
        check(slots_prev.get("6:30 AM") == "PREVIEW LABEL",
              "POD reads from preview dir when active")
        # missing-variant fallback: only weekday in preview, Sunday absent →
        # writer wrote Sunday too (from fake). Verify file exists.
        check(os.path.exists(os.path.join(prev_dir, "Sunday.json")),
              "preview Sunday.json exists")
        rfw.s15_discard_preview()

    finally:
        # Restore originals so nothing leaks across this process.
        (config.DAY_TEMPLATES_DIR, config.DAY_TEMPLATES_PREVIEW_DIR,
         config.DAY_TEMPLATES_BACKUP_DIR,
         rfw.DAY_TEMPLATES_DIR, rfw.DAY_TEMPLATES_PREVIEW_DIR,
         rfw.DAY_TEMPLATES_BACKUP_DIR) = orig
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + ("=" * 60))
    if failures:
        print(f"FAILED: {len(failures)} check(s)")
        for m in failures:
            print(f"  - {m}")
        sys.exit(1)
    print("ALL PHASE E CHECKS PASSED")


if __name__ == "__main__":
    main()
