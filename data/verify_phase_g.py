"""verify_phase_g.py — Phase G companion seasonal awareness verification.

Imports each companion's build_*_context, asserts the seasonal context block
is present in the right position with the role-specific content.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date

from data_helpers import get_seasonal_context, get_companion_seasonal_block


def _assert(cond, msg):
    print(("PASS" if cond else "FAIL") + ": " + msg)
    if not cond:
        raise SystemExit(1)


def test_seasonal_context_shape():
    ctx = get_seasonal_context(date(2026, 5, 19))
    _assert(isinstance(ctx, dict), "ctx is dict")
    for k in ("current_label", "upcoming_label", "days_until", "school_phase",
              "is_summer", "is_stress_season", "prior_year_saved"):
        _assert(k in ctx, f"ctx has key {k}")
    _assert(ctx["school_phase"] == "End-of-year wind-down",
            "May 19 → End-of-year wind-down phase")

    summer = get_seasonal_context(date(2026, 7, 4))
    _assert(summer["school_phase"] == "Summer mode" and summer["is_summer"],
            "July 4 → Summer mode + is_summer")

    nov = get_seasonal_context(date(2026, 11, 10))
    _assert(nov["school_phase"] == "Mid-year", "Nov 10 → Mid-year phase")
    _assert(nov["is_stress_season"] is True, "Nov 10 → stress season")

    bts = get_seasonal_context(date(2026, 8, 20))
    _assert(bts["school_phase"] == "Back to School ramp-up",
            "Aug 20 → Back to School ramp-up")


def test_role_blocks():
    roles = {
        "LUCY":       ("School-year phase", "approaching"),
        "LORENZO":    ("Lent: simplicity",  "Back to School: easy"),
        "SISTERMARY": ("SEASONAL CONTEXT",  "transition"),  # very loose
        "GREGORY":    ("School-year phase", "feedback"),
        "COACH":      ("SEASONAL CONTEXT",  "exercise"),
        "MONICA":     ("SEASONAL CONTEXT",  "stress"),
    }
    for role, needles in roles.items():
        block = get_companion_seasonal_block(role)
        _assert(isinstance(block, list) and len(block) >= 3,
                f"{role} block has >= 3 lines")
        joined = "\n".join(block)
        _assert("== SEASONAL CONTEXT ==" in joined,
                f"{role} block starts with header")
        _assert("Current season:" in joined,
                f"{role} contains Current season fact")
        for n in needles:
            _assert(n.lower() in joined.lower(),
                    f"{role} block contains needle: {n}")


def test_prompt_injection():
    """Each companion's build_*_context returns a string with the seasonal block."""
    iso        = "2026-05-19"
    weekday    = "Tuesday"
    date_label = "May 19, 2026"

    from render_lucy        import build_lucy_context
    from render_lorenzo     import build_lorenzo_context
    from render_gregory     import build_gregory_context
    from render_coach       import build_coach_context
    from render_monica      import build_monica_context

    for name, prompt in [
        ("Lucy",    build_lucy_context(iso, weekday, date_label)),
        ("Lorenzo", build_lorenzo_context(iso, weekday, date_label)),
        ("Gregory", build_gregory_context(iso, weekday, date_label)),
        ("Coach",   build_coach_context(iso, weekday, date_label)),
        ("Monica",  build_monica_context(iso, weekday, date_label)),
    ]:
        _assert("== SEASONAL CONTEXT ==" in prompt,
                f"{name} prompt contains seasonal header")
        _assert("Current season:" in prompt,
                f"{name} prompt contains current season line")
        # Block must appear before the companion_system_block "HANDOFF RULES:" header
        seasonal_pos = prompt.find("== SEASONAL CONTEXT ==")
        handoff_pos  = prompt.find("HANDOFF RULES:")
        if handoff_pos > 0:
            _assert(seasonal_pos < handoff_pos,
                    f"{name} seasonal block is before HANDOFF RULES")

    # Date-consistency check: build a Lucy prompt for a date in November and
    # confirm seasonal facts reflect that date, not today.
    nov_prompt = build_lucy_context("2026-11-10", "Tuesday", "November 10, 2026")
    _assert("Current season: November" in nov_prompt,
            "Lucy prompt for Nov 10 reflects November season (not today's)")

    aug_prompt = build_lucy_context("2026-08-20", "Thursday", "August 20, 2026")
    _assert("School-year phase: Back to School ramp-up" in aug_prompt,
            "Lucy prompt for Aug 20 reflects Back to School ramp-up phase")

    # Sister Mary — only injected when family-context setting is on.
    from render_sister_mary import build_sister_mary_context
    from render_settings    import load_app_settings, save_app_settings
    settings = load_app_settings() or {}
    prev     = settings.get("sister_mary_family_context", False)
    try:
        settings["sister_mary_family_context"] = True
        save_app_settings(settings)
        sm_prompt = build_sister_mary_context(iso, weekday, date_label)
        _assert("== SEASONAL CONTEXT ==" in sm_prompt,
                "Sister Mary (family-ctx on) contains seasonal header")
    finally:
        settings["sister_mary_family_context"] = prev
        save_app_settings(settings)


if __name__ == "__main__":
    test_seasonal_context_shape()
    test_role_blocks()
    test_prompt_injection()
    print()
    print("ALL PHASE G VERIFICATIONS PASSED")
