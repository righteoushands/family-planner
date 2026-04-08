"""
fq_auth.py — Auth module for Family Quest.
Reuses the same PIN-based system and user definitions from the main app's auth.py.
Sessions are shared (same sessions.json file) so one login works across both apps.
"""
import sys
import os

# Make sure the parent directory is importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import auth as _auth

# Re-export the things we need
USERS            = _auth.USERS
check_pin        = _auth.check_pin
create_session   = _auth.create_session
get_session_user = _auth.get_session_user
destroy_session  = _auth.destroy_session
is_admin         = _auth.is_admin
load_pins        = _auth.load_pins

CHILDREN_KEYS = ["jp", "joseph", "michael", "james"]


def is_child(username: str) -> bool:
    return USERS.get(username, {}).get("role") == "child"


def is_parent(username: str) -> bool:
    return is_admin(username)


def can_view_child(viewer: str, child_key: str) -> bool:
    """Parents can view any child. Children can only view themselves."""
    if is_parent(viewer):
        return True
    return viewer == child_key
