"""Phase D verification harness — §13 Build Your Day per-variant restructure.

Runs against a deep-copy of the real progress so the live JSON file is never
mutated. Stubs the two Anthropic-backed generators so no network call is made.
Exits non-zero on the first failed assertion."""

import copy
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import render_frol_wizard as rfw


_FAKE_QUESTIONS = [
    {"question_text": "Stub Q1?", "options": ["A", "B"]},
    {"question_text": "Stub Q2?", "options": ["X", "Y"]},
]


def _fake_schedule(variant: str):
    return [
        {"time": "07:00", "activity_name": f"{variant}-breakfast",
         "duration_min": 30, "who": ["Lauren"], "category": "free",
         "note": "", "keep": True},
        {"time": "09:00", "activity_name": f"{variant}-school",
         "duration_min": 120, "who": ["Lauren"], "category": "school",
         "note": "", "keep": True},
    ]


# ───────────────────────── Stub generators ──────────────────────────
def _stub_gen_questions(progress, variant="weekday"):
    bk = rfw._s12_bucket(progress, variant)
    bk["questions"] = list(_FAKE_QUESTIONS)
    bk["gen_hash"] = "stub-q-" + variant
    rfw.save_progress(progress) if False else None  # don't write live file
    return list(_FAKE_QUESTIONS)


def _stub_gen_schedule(progress, variant="weekday"):
    bk = rfw._s12_bucket(progress, variant)
    sch = _fake_schedule(variant)
    bk["schedule"] = sch
    bk["gen_hash"] = "stub-s-" + variant
    return sch


rfw._s12_generate_questions = _stub_gen_questions
rfw._s12_generate_schedule = _stub_gen_schedule


# Patch save_progress to be a no-op so the harness can't pollute the
# live data/frol_wizard_progress.json.
_NOOP_SAVES = []
def _noop_save(p):
    _NOOP_SAVES.append(True)
rfw.save_progress = _noop_save


# ───────────────────────── Load real progress ──────────────────────
_LIVE_PATH = os.path.join(_HERE, "frol_wizard_progress.json")
if os.path.exists(_LIVE_PATH):
    with open(_LIVE_PATH, "r", encoding="utf-8") as _f:
        _real = json.load(_f)
else:
    _real = {"data": {}, "section": 13}
progress = copy.deepcopy(_real)


def _ok(msg):
    print(f"  OK  {msg}")


def _fail(msg):
    print(f"FAIL  {msg}")
    sys.exit(1)


# ───────────────────── 1. Migration is idempotent ───────────────────
print("\n[1] Migration: flat keys → .weekday bucket")
progress.setdefault("data", {})["section_13"] = {
    "questions": [{"question_text": "old", "options": ["x"]}],
    "answers": {"0": "x"},
    "schedule": [{"time": "07:00", "activity_name": "old", "duration_min": 10,
                  "who": ["Lauren"], "category": "free", "note": "", "keep": True}],
    "gen_hash": "old-hash",
}
changed = rfw._s12_migrate_per_variant(progress)
if not changed:
    _fail("expected migration to report changed=True on flat input")
sec13 = progress["data"]["section_13"]
for _k in ("questions", "answers", "schedule", "gen_hash"):
    if _k in sec13:
        _fail(f"flat key '{_k}' still present after migration")
_ok("flat keys removed from section_13 root")
if "weekday" not in sec13 or not isinstance(sec13["weekday"], dict):
    _fail("section_13.weekday bucket missing")
if sec13["weekday"].get("gen_hash") != "old-hash":
    _fail("gen_hash did not migrate to weekday bucket")
_ok("flat keys moved into section_13.weekday")
changed2 = rfw._s12_migrate_per_variant(progress)
if changed2:
    _fail("second migration should be a no-op")
_ok("migration is idempotent")


# ───────────────────── 2. _s12_bucket creates buckets ───────────────
print("\n[2] _s12_bucket")
for vk in rfw._S12_VARIANT_KEYS:
    b = rfw._s12_bucket(progress, vk)
    if not isinstance(b, dict):
        _fail(f"_s12_bucket({vk}) did not return a dict")
_ok("all 4 variant buckets exist and are dicts")


# ───────────────────── 3. Activity filter by variant ────────────────
print("\n[3] _s12_filter_activities_by_variant")
# Pass the flat section_12 dict (real shape — keys live at the root, not
# nested under 'section_12_activities').
sample_sec12 = {
    "durations__weekday__Math":            "30",
    "durations__saturday__Chores":         "45",
    "durations__sunday__Mass":             "60",
    "durations__john_traveling__Solo":     "20",
    "custom__weekday__extra":              "weekday-only",
    "custom__sunday__rest":                "sunday-only",
    "unrelated_key":                       "kept-always",
}
for vk in rfw._S12_VARIANT_KEYS:
    out = rfw._s12_filter_activities_by_variant(sample_sec12, vk)
    if not isinstance(out, dict):
        _fail(f"filter for {vk} did not return a dict")
    # Must contain at least the two keys tagged for this variant
    if f"durations__{vk}__" not in next(iter(out.keys()), "") + " ":
        # gentler check: ensure ≥1 key starts with the variant prefix
        if not any(k.startswith(f"durations__{vk}__")
                   or k.startswith(f"custom__{vk}__") for k in out):
            _fail(f"filter for {vk} dropped its own variant keys")
    # Must NOT contain any foreign variant's keys
    foreign = [other for other in rfw._S12_VARIANT_KEYS if other != vk]
    for k in out:
        for fv in foreign:
            if k.startswith(f"durations__{fv}__") or k.startswith(f"custom__{fv}__"):
                _fail(f"filter for {vk} leaked foreign key {k!r}")
_ok("activity filter scopes durations__/custom__ by variant")


# ───────────────────── 4. john_traveling pulls §10 notes ────────────
print("\n[4] john_traveling context includes §10.john_travel_notes")
progress.setdefault("data", {}).setdefault("section_10", {})[
    "john_travel_notes"
] = "Lauren handles bedtime alone; cereal-night Tue/Thu."
ctx = rfw._s12_collect_context(progress, "john_traveling")
ctx_str = json.dumps(ctx)
if "cereal-night" not in ctx_str:
    _fail("john_travel_notes not surfaced into john_traveling ctx")
_ok("john_travel_notes flows into john_traveling context")
ctx_wd = rfw._s12_collect_context(progress, "weekday")
if "cereal-night" in json.dumps(ctx_wd):
    _fail("john_travel_notes leaked into weekday context")
_ok("john_travel_notes does NOT leak into weekday context")


# ───────────────────── 5. Per-variant generation independence ───────
print("\n[5] Per-variant generation independence")
# Reset buckets
progress["data"]["section_13"] = {}
for vk in rfw._S12_VARIANT_KEYS:
    _stub_gen_questions(progress, vk)
    _stub_gen_schedule(progress, vk)
for vk in rfw._S12_VARIANT_KEYS:
    bk = rfw._s12_bucket(progress, vk)
    sch = bk.get("schedule") or []
    if not sch:
        _fail(f"{vk}: schedule empty after stub-gen")
    if not any(vk in str(it.get("activity_name", "")) for it in sch):
        _fail(f"{vk}: schedule not tagged with variant prefix")
_ok("each variant has its own schedule with variant-prefixed activities")


# ───────────────────── 6. Edit isolation ────────────────────────────
print("\n[6] Removing a slot in saturday must not touch weekday")
sat_before = copy.deepcopy(rfw._s12_bucket(progress, "saturday")["schedule"])
wd_before  = copy.deepcopy(rfw._s12_bucket(progress, "weekday")["schedule"])
rfw._s12_bucket(progress, "saturday")["schedule"][0]["keep"] = False
sat_after = rfw._s12_bucket(progress, "saturday")["schedule"]
wd_after  = rfw._s12_bucket(progress, "weekday")["schedule"]
if sat_after[0]["keep"] is not False:
    _fail("saturday slot 0 keep did not flip")
if wd_after != wd_before:
    _fail("weekday schedule mutated when editing saturday")
_ok("variant edits are isolated")


# ───────────────────── 7. Aggregated persist tags variant ───────────
print("\n[7] s12_persist_kept_to_activities aggregates across variants")
# Spy on save_frol_activities to capture what would be written
captured = {"kept": None}
def _spy_save(items):
    captured["kept"] = items
rfw.save_frol_activities = _spy_save
n = rfw.s12_persist_kept_to_activities(progress)
if n < 0:
    _fail("persist returned -1")
if captured["kept"] is None:
    _fail("save_frol_activities was not invoked")
variants_seen = {it.get("variant") for it in captured["kept"]
                 if isinstance(it, dict)}
expected = set(rfw._S12_VARIANT_KEYS)
# saturday slot 0 was un-kept above, but saturday slot 1 remains kept
missing = expected - variants_seen
if missing:
    _fail(f"persist missing variants in tagged output: {missing}")
_ok(f"persist wrote {n} items spanning {len(variants_seen)} variants")


# ───────────────────── 8. Render §13 for each variant ───────────────
print("\n[8] render_section_12 runs for each variant without exception")
# Set the active variant in turn and render. We avoid network by relying
# on the stubbed generators above.
for vk in rfw._S12_VARIANT_KEYS:
    progress.setdefault("data", {})["active_variant"] = vk
    try:
        html = rfw.render_section_12(progress, "structured")
    except Exception as e:
        import traceback as _tb
        print(_tb.format_exc())
        _fail(f"render_section_12 raised for {vk}: {type(e).__name__}: {e}")
    if not isinstance(html, str) or len(html) < 200:
        _fail(f"render_section_12 returned suspiciously short HTML for {vk}")
_ok("render_section_12 produced HTML for all 4 variants")


print("\nALL PHASE D CHECKS PASSED")
