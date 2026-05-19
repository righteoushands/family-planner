"""
render_seasons.py — Phase F season detection helper.

Defines 11 season labels (8 fixed-date + 3 moveable Catholic feasts) and
provides upcoming_season(today) which returns the next season window the
family is approaching, including its start date and days_until.

This module is intentionally pure (no I/O). Save/load of saved schedules
lives in data_helpers; UI lives in the relevant render_*.py modules.
"""
from datetime import date, timedelta

from render_liturgical import _easter


# 8 fixed-date seasons (Mon-Fri assumed irrelevant — these are calendar dates)
_FIXED_SEASONS = [
    ("End of school year",   5, 15),
    ("Summer",               6, 1),
    ("Back to School",       8, 15),
    ("Fall",                 9, 22),
    ("November",            11, 1),
    ("Christmas",           12, 25),
    ("New Year",             1, 1),
    ("Post-break ramp-up",   1, 7),
]

# 3 moveable Catholic seasons keyed by their starting feast.
_MOVEABLE_KEYS = ("Lent", "Easter", "Advent")

# Ordered for UI dropdowns + library grouping. Exact strings here are
# persisted in app_settings.dismissed_season_prompts and in saved
# schedules — do not rename without a migration.
SEASON_LABELS = [
    "Post-break ramp-up",
    "Lent",
    "Easter",
    "End of school year",
    "Summer",
    "Back to School",
    "Fall",
    "November",
    "Advent",
    "Christmas",
    "New Year",
]

# One-time migration: any persisted entries that still use the old label
# spellings need to be updated to the new strings at read time.
_LABEL_MIGRATIONS = {
    "Post-Christmas Break": "Post-break ramp-up",
    "End of School Year":   "End of school year",
}


def migrate_label(label: str) -> str:
    """Return the canonical label for a (possibly historical) string."""
    return _LABEL_MIGRATIONS.get((label or "").strip(), label)


def _moveable_start(label: str, year: int) -> date:
    """Return the start date for a moveable season in the given year."""
    easter = _easter(year)
    if label == "Lent":
        return easter - timedelta(days=46)         # Ash Wednesday
    if label == "Easter":
        return easter                              # Easter Sunday
    if label == "Advent":
        christmas = date(year, 12, 25)
        # First Sunday of Advent = 4th Sunday before Christmas.
        offset = (christmas.weekday() + 1) % 7 + 21
        return christmas - timedelta(days=offset)
    raise ValueError(f"unknown moveable season: {label!r}")


def season_start(label: str, year: int) -> date:
    """Return the calendar date that `label` begins in `year`."""
    if label in _MOVEABLE_KEYS:
        return _moveable_start(label, year)
    for name, mo, dy in _FIXED_SEASONS:
        if name == label:
            return date(year, mo, dy)
    raise ValueError(f"unknown season: {label!r}")


def _all_starts_for_year(year: int) -> list:
    """Return (label, start_date) pairs for every season starting in `year`."""
    out = []
    for label in SEASON_LABELS:
        try:
            out.append((label, season_start(label, year)))
        except Exception:
            continue
    return out


def upcoming_season(today: date = None, window_days: int = 365) -> dict:
    """Return the next season that begins on/after `today` within window_days.

    Result shape::
        {"label": str, "year": int, "start_date": date, "days_until": int}

    Returns None only when window_days is non-positive."""
    if today is None:
        today = date.today()
    if window_days <= 0:
        return None
    # Search current year + next year so wrap-around is handled.
    candidates = _all_starts_for_year(today.year) + _all_starts_for_year(today.year + 1)
    soonest = None
    for label, sd in candidates:
        if sd < today:
            continue
        days = (sd - today).days
        if days > window_days:
            continue
        if soonest is None or sd < soonest[2]:
            soonest = (label, sd.year, sd, days)
    if not soonest:
        return None
    label, yr, sd, days = soonest
    return {"label": label, "year": yr, "start_date": sd, "days_until": days}


def current_season(today: date = None) -> dict:
    """Return the season currently in progress (most recent past start)."""
    if today is None:
        today = date.today()
    candidates = (
        _all_starts_for_year(today.year - 1)
        + _all_starts_for_year(today.year)
    )
    best = None
    for label, sd in candidates:
        if sd > today:
            continue
        if best is None or sd > best[2]:
            best = (label, sd.year, sd)
    if not best:
        return None
    label, yr, sd = best
    return {"label": label, "year": yr, "start_date": sd}
