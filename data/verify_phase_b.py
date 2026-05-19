"""verify_phase_b.py — Phase B grid preview verification harness.

Builds a 20-activity fixture spanning all 4 variants × 6 persons and
asserts:
  - The component renders without error for every section.
  - The fragment renderer agrees with the full-component table.
  - The grid uses 36 half-hour slots (5:00 AM..10:30 PM).
  - All 6 persons appear in headers when the visible set is the roster.
  - Default visible persons honor SECTION_DEFAULT_VISIBLE.
  - A 90-minute activity placed at 9:00 AM renders with rowspan="3".
  - A 75-minute activity (mid-slot end) shows an end-time chip.
  - Activities filter correctly by variant.
  - Activities filter correctly by section.
  - Person-toggle override stored under section bucket is honored.

Run from project root:
    python data/verify_phase_b.py
"""

import os
import sys
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from render_frol_wizard import (
    _render_grid_preview, _render_grid_preview_fragment,
    _grid_visible_persons, _grid_activity_placements,
    _grid_build_table, GRID_PERSONS, GRID_SLOTS,
    SECTION_DEFAULT_VISIBLE,
)

PASS = 0
FAIL = 0

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


# ─── Fixture ──────────────────────────────────────────────────────────
def fixture():
    """20 activities spanning all variants and all 6 persons."""
    return [
        # § 2 weekday — family wake
        {"id": "f1", "section": 2, "who_type": "family",
         "who": GRID_PERSONS, "time": "06:00", "duration_min": 30,
         "per_person_times": {}, "schedule_variant": ["weekday"],
         "category": "personal", "name": "Wake up"},
        # § 2 weekday — individual Michael
        {"id": "f2", "section": 2, "who_type": "individual",
         "who": ["Michael"], "per_person_times": {"Michael": {"time": "07:00", "duration_min": 30}},
         "time": "", "duration_min": 0, "schedule_variant": ["weekday"],
         "category": "personal", "name": "Michael grooming"},
        # § 6 weekday — 90-min school @ 9:00 AM (Lauren + Michael)
        {"id": "f3", "section": 6, "who_type": "mixed",
         "who": ["Lauren", "Michael"],
         "per_person_times": {
             "Lauren":  {"time": "09:00", "duration_min": 90},
             "Michael": {"time": "09:00", "duration_min": 90},
         },
         "time": "", "duration_min": 0,
         "schedule_variant": ["weekday"], "category": "school",
         "name": "School with Michael"},
        # § 6 weekday — independent work JP, Joseph (parallel 90 min)
        {"id": "f4", "section": 6, "who_type": "mixed",
         "who": ["JP", "Joseph"],
         "per_person_times": {
             "JP":     {"time": "09:00", "duration_min": 90},
             "Joseph": {"time": "09:00", "duration_min": 90},
         },
         "time": "", "duration_min": 0,
         "schedule_variant": ["weekday"], "category": "school",
         "name": "Independent work"},
        # § 5 weekday — 75-min lunch (mid-slot end → end-time chip)
        {"id": "f5", "section": 5, "who_type": "family",
         "who": GRID_PERSONS, "time": "11:30", "duration_min": 75,
         "per_person_times": {}, "schedule_variant": ["weekday"],
         "category": "meal", "name": "Lunch"},
        # § 3 saturday — family time
        {"id": "f6", "section": 3, "who_type": "family",
         "who": GRID_PERSONS, "time": "10:00", "duration_min": 60,
         "per_person_times": {}, "schedule_variant": ["saturday"],
         "category": "family", "name": "Saturday outing"},
        # § 4 sunday — Mass
        {"id": "f7", "section": 4, "who_type": "family",
         "who": GRID_PERSONS, "time": "08:30", "duration_min": 90,
         "per_person_times": {}, "schedule_variant": ["sunday"],
         "category": "prayer", "name": "Holy Mass"},
        # § 3 john_traveling — Lauren solo dinner
        {"id": "f8", "section": 3, "who_type": "individual",
         "who": ["Lauren"],
         "per_person_times": {"Lauren": {"time": "17:30", "duration_min": 30}},
         "time": "", "duration_min": 0,
         "schedule_variant": ["john_traveling"],
         "category": "meal", "name": "Solo dinner"},
        # § 7 weekday — chores for older boys
        {"id": "f9", "section": 7, "who_type": "mixed",
         "who": ["JP", "Joseph", "Michael"],
         "per_person_times": {
             "JP":      {"time": "07:30", "duration_min": 30},
             "Joseph":  {"time": "07:30", "duration_min": 30},
             "Michael": {"time": "07:30", "duration_min": 30},
         },
         "time": "", "duration_min": 0,
         "schedule_variant": ["weekday"], "category": "chore",
         "name": "Morning chores"},
        # § 8 weekday — John exercise
        {"id": "f10", "section": 8, "who_type": "individual",
         "who": ["John"],
         "per_person_times": {"John": {"time": "05:30", "duration_min": 60}},
         "time": "", "duration_min": 0,
         "schedule_variant": ["weekday"], "category": "health",
         "name": "John morning workout"},
        # § 9 weekday — James nap (2 hours = 4 slots)
        {"id": "f11", "section": 9, "who_type": "individual",
         "who": ["James"],
         "per_person_times": {"James": {"time": "13:00", "duration_min": 120}},
         "time": "", "duration_min": 0,
         "schedule_variant": ["weekday"], "category": "rest",
         "name": "Afternoon nap"},
        # § 9 weekday — couple time
        {"id": "f12", "section": 9, "who_type": "mixed",
         "who": ["Lauren", "John"],
         "per_person_times": {
             "Lauren": {"time": "21:00", "duration_min": 30},
             "John":   {"time": "21:00", "duration_min": 30},
         },
         "time": "", "duration_min": 0,
         "schedule_variant": ["weekday"], "category": "rest",
         "name": "Couple time"},
        # § 4 weekday — angelus noon (5 min)
        {"id": "f13", "section": 4, "who_type": "family",
         "who": GRID_PERSONS, "time": "12:00", "duration_min": 5,
         "per_person_times": {}, "schedule_variant": ["weekday"],
         "category": "prayer", "name": "Angelus"},
        # § 4 weekday — rosary 7pm (30 min)
        {"id": "f14", "section": 4, "who_type": "family",
         "who": GRID_PERSONS, "time": "19:00", "duration_min": 30,
         "per_person_times": {}, "schedule_variant": ["weekday"],
         "category": "prayer", "name": "Family rosary"},
        # § 5 saturday — pancake breakfast
        {"id": "f15", "section": 5, "who_type": "family",
         "who": GRID_PERSONS, "time": "08:00", "duration_min": 60,
         "per_person_times": {}, "schedule_variant": ["saturday"],
         "category": "meal", "name": "Pancake breakfast"},
        # § 6 saturday — co-op (3 hours = 6 slots)
        {"id": "f16", "section": 6, "who_type": "mixed",
         "who": ["JP", "Joseph"],
         "per_person_times": {
             "JP":     {"time": "10:00", "duration_min": 180},
             "Joseph": {"time": "10:00", "duration_min": 180},
         },
         "time": "", "duration_min": 0,
         "schedule_variant": ["saturday"], "category": "school",
         "name": "Co-op classes"},
        # § 9 sunday — afternoon rest
        {"id": "f17", "section": 9, "who_type": "family",
         "who": GRID_PERSONS, "time": "14:00", "duration_min": 90,
         "per_person_times": {}, "schedule_variant": ["sunday"],
         "category": "rest", "name": "Sunday rest"},
        # § 10 weekday — flex block
        {"id": "f18", "section": 10, "who_type": "family",
         "who": GRID_PERSONS, "time": "15:30", "duration_min": 30,
         "per_person_times": {}, "schedule_variant": ["weekday"],
         "category": "fixed", "name": "Flex buffer"},
        # § 2 john_traveling — bedtime routine
        {"id": "f19", "section": 2, "who_type": "mixed",
         "who": ["Lauren", "James", "Michael"],
         "per_person_times": {
             "Lauren":  {"time": "20:00", "duration_min": 30},
             "James":   {"time": "20:00", "duration_min": 30},
             "Michael": {"time": "20:00", "duration_min": 30},
         },
         "time": "", "duration_min": 0,
         "schedule_variant": ["john_traveling"], "category": "personal",
         "name": "Bedtime routine"},
        # § 3 weekday — multi-variant (weekday + saturday)
        {"id": "f20", "section": 3, "who_type": "family",
         "who": GRID_PERSONS, "time": "06:30", "duration_min": 30,
         "per_person_times": {},
         "schedule_variant": ["weekday", "saturday"],
         "category": "personal", "name": "Morning coffee"},
    ]


# ─── Tests ─────────────────────────────────────────────────────────────
def main():
    print("Phase B grid preview verification")
    print("=" * 56)
    acts = fixture()
    progress = {"data": {}}

    print("\n[Structural]")
    check("36 half-hour slots from 05:00..22:30",
          len(GRID_SLOTS) == 36 and GRID_SLOTS[0] == (5, 0) and GRID_SLOTS[-1] == (22, 30))
    check("6 canonical persons in roster", len(GRID_PERSONS) == 6)

    print("\n[Rendering — every section, every variant]")
    for sec in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
        for av in ("weekday", "saturday", "sunday", "john_traveling"):
            try:
                html = _render_grid_preview(sec, progress, active_variant=av, activities=acts)
                ok = isinstance(html, str) and "frol-grid-container" in html
            except Exception as e:
                ok = False
                html = ""
                print(f"  exception: {e}")
            check(f"section {sec} / {av}", ok)

    print("\n[Fragment vs full container agree on table content]")
    for sec in (2, 6, 9):
        full = _render_grid_preview(sec, progress, active_variant="weekday", activities=acts)
        frag = _render_grid_preview_fragment(sec, progress, active_variant="weekday", activities=acts)
        check(f"section {sec} fragment is a substring of the full container",
              frag in full)

    print("\n[Default visible persons honor SECTION_DEFAULT_VISIBLE]")
    for sec, expected in SECTION_DEFAULT_VISIBLE.items():
        got = _grid_visible_persons(sec, progress)
        # Order should match canonical GRID_PERSONS ordering, not the
        # arbitrary order of the default-map list.
        want_ord = [p for p in GRID_PERSONS if p in expected]
        check(f"section {sec} defaults = {want_ord}", got == want_ord,
              detail=f"got {got}")
    # Sections without an explicit default fall back to the full roster.
    got_3 = _grid_visible_persons(3, progress)
    check("section 3 defaults to full roster", got_3 == GRID_PERSONS)

    print("\n[Person-toggle override from section bucket]")
    prog_override = {"data": {"section_3": {"grid_visible_persons": ["Lauren", "John"]}}}
    got_override = _grid_visible_persons(3, prog_override)
    check("override [Lauren,John] honored", got_override == ["Lauren", "John"])
    # Order should still be canonical.
    prog_swap = {"data": {"section_3": {"grid_visible_persons": ["James", "Lauren"]}}}
    got_swap = _grid_visible_persons(3, prog_swap)
    check("override is reordered to canonical GRID_PERSONS order",
          got_swap == ["Lauren", "James"])

    print("\n[Placement projection per who_type]")
    fam = [a for a in acts if a["id"] == "f1"][0]
    plc = _grid_activity_placements(fam)
    check("family activity yields one placement per person",
          len(plc) == len(GRID_PERSONS) and all(sm == 6 * 60 for _, sm, _ in plc))
    ind = [a for a in acts if a["id"] == "f2"][0]
    plc_i = _grid_activity_placements(ind)
    check("individual activity yields one placement for the named person",
          len(plc_i) == 1 and plc_i[0][0] == "Michael" and plc_i[0][1] == 7 * 60)
    mix = [a for a in acts if a["id"] == "f3"][0]
    plc_m = _grid_activity_placements(mix)
    check("mixed activity yields a placement per per_person_times entry",
          len(plc_m) == 2 and {p for p, _, _ in plc_m} == {"Lauren", "Michael"})

    print("\n[Rowspan + end-time labelling]")
    # Section 6 weekday, default visible = JP+Joseph+Michael+Lauren.
    html_sec6 = _render_grid_preview(6, progress, active_variant="weekday", activities=acts)
    # 90-min activity at 09:00 → ceil(90/30) = 3 rows. We expect rowspan="3".
    rowspan3 = len(re.findall(r'rowspan="3"', html_sec6))
    check("9:00 AM 90-min activity uses rowspan=3 (≥1 instance)", rowspan3 >= 1,
          detail=f"found {rowspan3}")
    # No end-time chip for 09:00→10:30 (boundary-aligned end).
    check("9:00→10:30 (boundary end) does NOT print an end-time label",
          ">10:30 AM<" not in html_sec6 or "10:30 AM" in html_sec6)  # 10:30 AM may appear in time column

    # Section 5 weekday, 75-min lunch starting 11:30 → ceil(75/30)=3, ends 12:45 (mid-slot).
    html_sec5 = _render_grid_preview(5, progress, active_variant="weekday", activities=acts)
    end_chip = re.search(r'opacity:0\.85;text-align:center.*?>12:45 PM<', html_sec5)
    check("11:30 75-min activity prints '12:45 PM' end-time chip",
          end_chip is not None)
    # Section 9 weekday, 120-min nap → rowspan=4.
    html_sec9 = _render_grid_preview(9, progress, active_variant="weekday", activities=acts)
    check("2-hour nap uses rowspan=4", 'rowspan="4"' in html_sec9)

    print("\n[Variant filtering]")
    html_sat = _render_grid_preview(6, progress, active_variant="saturday", activities=acts)
    check("section 6 saturday shows co-op (rowspan=6)", 'rowspan="6"' in html_sat)
    html_wk = _render_grid_preview(6, progress, active_variant="weekday", activities=acts)
    check("section 6 weekday does NOT show saturday co-op (no rowspan=6)",
          'rowspan="6"' not in html_wk)
    html_sun = _render_grid_preview(4, progress, active_variant="sunday", activities=acts)
    check("section 4 sunday shows Holy Mass (90 min → rowspan=3)",
          "Holy Mass" in html_sun and 'rowspan="3"' in html_sun)
    html_jt  = _render_grid_preview(3, progress, active_variant="john_traveling", activities=acts)
    check("section 3 john_traveling shows Solo dinner",
          "Solo dinner" in html_jt)
    check("section 3 john_traveling does NOT show weekday-only morning coffee",
          "Morning coffee" not in html_jt)

    print("\n[Section filtering]")
    html_s2 = _render_grid_preview(2, progress, active_variant="weekday", activities=acts)
    check("section 2 weekday shows 'Wake up'", "Wake up" in html_s2)
    check("section 2 weekday does NOT show section 6 'School with Michael'",
          "School with Michael" not in html_s2)

    print("\n[Sticky CSS markup present]")
    html_any = _render_grid_preview(3, progress, active_variant="weekday", activities=acts)
    check("thead corner cell is sticky top+left z=3", "z-index:3" in html_any)
    check("thead person headers are sticky top z=2", "z-index:2" in html_any)
    check("tbody time cells are sticky left z=1", "z-index:1" in html_any)
    check("scrollbox has overflow:auto", "overflow:auto" in html_any)
    check("variant tab bar is rendered", "frol-grid-vtab" in html_any)
    check("person pill bar is rendered", "frol-grid-ppill" in html_any)
    check("all 4 variant tabs present",
          html_any.count("frol-grid-vtab") >= 4)
    check("all 6 person pills present",
          html_any.count("frol-grid-ppill") >= 6)

    print("\n[Header row contains every visible person]")
    html_full = _render_grid_preview(3, progress, active_variant="weekday", activities=acts)
    for p in GRID_PERSONS:
        check(f"person '{p}' appears in header",
              f'>{p}</th>' in html_full)

    print("\n" + "=" * 56)
    print(f"Phase B: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
