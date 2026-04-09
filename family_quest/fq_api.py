"""
fq_api.py — Single adapter between Family Quest and Sancta Familia.

This is the ONLY file in Family Quest that imports from the main app.
All other FQ modules call functions here instead of reaching into the
parent directory themselves.

To move Family Quest to a separate Repl in the future, replace the
function bodies below with HTTP calls to Sancta Familia's API endpoints.
Everything else in the family_quest/ directory stays exactly the same.
"""
import os
import sys

# ── One-time parent path setup ────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ── Auth ──────────────────────────────────────────────────────────────────────

def _auth():
    import auth
    return auth


def get_users() -> dict:
    """Return the full USERS dict (all family members with colors, roles, etc.)."""
    return _auth().USERS


def check_pin(user: str, pin: str) -> bool:
    return _auth().check_pin(user, pin)


def create_session(user: str) -> str:
    return _auth().create_session(user)


def get_session_user(token: str):
    return _auth().get_session_user(token)


def destroy_session(token: str):
    _auth().destroy_session(token)


def is_admin(user: str) -> bool:
    return _auth().is_admin(user)


def load_pins() -> dict:
    return _auth().load_pins()


# ── Day list / curriculum ─────────────────────────────────────────────────────

def get_day_list(child_name: str, weekday: str, iso_date: str) -> list:
    """Return the built day list for a child on a given day."""
    from daily_schedule_engine import build_day_list
    return build_day_list(child_name, weekday, iso_date)


def get_school_tasks(child_name: str, weekday: str) -> list:
    """Return extracted school subject blocks for a child."""
    from daily_schedule_engine import extract_school_tasks_for_child
    return extract_school_tasks_for_child(child_name, weekday)
