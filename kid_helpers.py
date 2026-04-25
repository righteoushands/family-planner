"""Kid-helper assignment.

Single source of truth for which boys can be assigned cooking-helper
tasks, and the matcher that picks one age-eligible step per boy from
a recipe's kid_steps list.

The four boys' ages are fixed in this household: JP 14, Joseph 12,
Michael 5, James 13mo. James is high-chair only and is excluded by
design from any helper assignment.
"""

BOYS_AGES = [("JP", 14), ("Joseph", 12), ("Michael", 5)]


def _step_age_min(step):
    """Return step's age_min coerced to int, or 0 if missing / malformed.

    Centralises the coercion so the same number flows into both the
    eligibility check and the "highest eligible age_min" ranking key —
    otherwise a string '5' would lexicographically outrank '12' and the
    wrong boy would get the wrong step.
    """
    if not isinstance(step, dict):
        return 0
    try:
        return int(step.get("age_min", 0))
    except (TypeError, ValueError):
        return 0


def _step_fits_age(step, age):
    """True if `age` falls within step's age_min/age_max bounds.

    `age_min` missing or malformed is treated as 0 (any age can do it).
    `age_max` missing means no upper bound.
    """
    if not isinstance(step, dict):
        return False
    if age < _step_age_min(step):
        return False
    age_max = step.get("age_max")
    if age_max is not None:
        try:
            if age > int(age_max):
                return False
        except (TypeError, ValueError):
            return False
    return True


def assign_kid_steps(kid_steps):
    """Pick one age-eligible step per boy from a kid_steps list.

    Each step is a dict like
        {"step": "wash the broccoli", "age_min": 4, "age_max": 99}.

    Walks BOYS_AGES oldest-first; each boy claims the step with the
    highest age_min he still qualifies for, so the oldest gets the
    most grown-up step and the youngest gets whatever simpler step
    is left. A step claimed by one boy is not offered to another.

    Returns a list of (boy_name, step_text) tuples for boys who got
    a step. Boys with no eligible step are omitted. Returns [] if
    nobody can be matched.
    """
    if not kid_steps:
        return []

    available = list(kid_steps)
    assignments = []

    for boy_name, boy_age in BOYS_AGES:
        eligible = [s for s in available if _step_fits_age(s, boy_age)]
        if not eligible:
            continue
        chosen = max(eligible, key=_step_age_min)
        assignments.append((boy_name, chosen.get("step", "")))
        available.remove(chosen)

    return assignments
