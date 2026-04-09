"""
fq_auth.py — Auth module for Family Quest.
Uses fq_api as the single bridge to Sancta Familia's auth system.
"""
import fq_api as _api

# ── Re-export auth helpers ────────────────────────────────────────────────────

USERS            = _api.get_users()
check_pin        = _api.check_pin
create_session   = _api.create_session
get_session_user = _api.get_session_user
destroy_session  = _api.destroy_session
is_admin         = _api.is_admin
load_pins        = _api.load_pins

CHILDREN_KEYS = ["jp", "joseph", "michael", "james"]


def is_child(username: str) -> bool:
    return _api.get_users().get(username, {}).get("role") == "child"


def is_parent(username: str) -> bool:
    return _api.is_admin(username)


def can_view_child(viewer: str, child_key: str) -> bool:
    """Parents can view any child. Children can only view themselves."""
    if is_parent(viewer):
        return True
    return viewer == child_key
