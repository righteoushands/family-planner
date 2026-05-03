"""
auth.py — Session-based auth for McAdams Family Dashboard.

PIN: 4-digit code (MMDD of birthday by default).
Michael/James: tap avatar = instant login (no PIN).
Sessions: in-memory dict, cleared on server restart; session cookie
          has no max-age, so it dies when the browser is closed.
"""
import os, json, secrets
from safe_utils import safe_save_json

# ── User definitions ──────────────────────────────────────────────────────────
USERS = {
    "lauren":  {"name": "Lauren",  "role": "admin", "color": "#7c3aed", "light": "#f3f0ff",
                "initials": "L",  "emoji": "✝", "pin_required": True},
    "john":    {"name": "John",    "role": "admin", "color": "#1e3a6e", "light": "#eff6ff",
                "initials": "J",  "emoji": "⚓", "pin_required": True},
    "jp":      {"name": "JP",      "role": "child", "color": "#b91c1c", "light": "#fef2f2",
                "initials": "JP", "emoji": "⚓", "pin_required": True},
    "joseph":  {"name": "Joseph",  "role": "child", "color": "#15803d", "light": "#f0fdf4",
                "initials": "Jo", "emoji": "🛡", "pin_required": True},
    "michael": {"name": "Michael", "role": "child", "color": "#c2410c", "light": "#fff7ed",
                "initials": "Mi", "emoji": "🚂", "pin_required": False},
    "james":   {"name": "James",   "role": "child", "color": "#6d28d9", "light": "#f5f3ff",
                "initials": "Ja", "emoji": "🐣", "pin_required": False},
}

# ── Paths children may GET ────────────────────────────────────────────────────
_SHARED = frozenset(["/", "/today", "/week", "/meals", "/recipes",
                     "/chores", "/prayer", "/change-pin", "/subject"])

_UPLOADS = frozenset(["/uploads/grades", "/uploads/grade_docs"])

CHILD_ALLOWED_GET: dict[str, frozenset] = {
    "jp":      _SHARED | _UPLOADS | frozenset(["/schedule/jp",     "/student/jp",     "/grades/jp"]),
    "joseph":  _SHARED | _UPLOADS | frozenset(["/schedule/joseph", "/student/joseph", "/grades/joseph"]),
    "michael": _SHARED | _UPLOADS | frozenset(["/schedule/michael"]),
    "james":   frozenset(["/"]),
}

# Paths children may POST to
CHILD_POST_ALLOWED = frozenset([
    "/toggle-task", "/message-mom", "/change-pin", "/task-override",
    "/subject-upload-image",
    "/subject-send-to-mom",
    "/student-message-read",
])

# ── PIN storage ───────────────────────────────────────────────────────────────
AUTH_PATH = "data/auth/pins.json"


def load_pins() -> dict:
    try:
        with open(AUTH_PATH) as f:
            return json.load(f)
    except Exception:
        return {u: "0000" for u in USERS}


def save_pins(pins: dict) -> None:
    existing = load_pins()
    existing.update(pins)
    safe_save_json(AUTH_PATH, existing)


def get_pin(username: str) -> str:
    return load_pins().get(username, "0000")


def check_pin(username: str, entered: str) -> bool:
    if username not in USERS:
        return False
    if not USERS[username].get("pin_required", True):
        return True
    return entered == get_pin(username)


# ── Session store (file-backed — survives server restarts) ────────────────────
_SESSIONS_PATH = "data/auth/sessions.json"
_SESSIONS: dict = {}


def _load_sessions() -> None:
    global _SESSIONS
    try:
        with open(_SESSIONS_PATH) as f:
            _SESSIONS = json.load(f)
    except Exception:
        _SESSIONS = {}


def _save_sessions() -> None:
    safe_save_json(_SESSIONS_PATH, _SESSIONS)


# Load sessions from disk on import
_load_sessions()


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = username
    _save_sessions()
    return token


def get_session_user(token: str):
    if token in _SESSIONS:
        return _SESSIONS[token]
    # Re-read from disk in case another process created this session
    _load_sessions()
    return _SESSIONS.get(token)


def destroy_session(token: str):
    _SESSIONS.pop(token, None)
    _save_sessions()


# ── Current-viewer context (single-threaded server) ───────────────────────────
_viewer: dict = {"user": None}


def set_viewer(user):
    _viewer["user"] = user


def get_viewer():
    return _viewer.get("user")


# ── Access control ────────────────────────────────────────────────────────────
def is_admin(username: str) -> bool:
    return USERS.get(username, {}).get("role") == "admin"


def can_get(username: str, path: str) -> bool:
    if not username:
        return False
    if is_admin(username):
        return True
    clean = path.split("?")[0].rstrip("/") or "/"
    allowed = CHILD_ALLOWED_GET.get(username, frozenset())
    for p in allowed:
        if clean == p or clean.startswith(p + "/"):
            return True
    # Lucy brief for own child
    if path.startswith(f"/lucy-child-brief/{username}"):
        return True
    return False


def can_post(username: str, path: str) -> bool:
    if not username:
        return False
    if is_admin(username):
        return True
    return path.split("?")[0] in CHILD_POST_ALLOWED


# ── Message Mom ───────────────────────────────────────────────────────────────
MSG_PATH = "data/mom_messages.json"


def load_messages() -> list:
    try:
        with open(MSG_PATH) as f:
            return json.load(f)
    except Exception:
        return []


def save_message(from_user: str, text: str) -> None:
    import uuid
    from datetime import datetime
    msgs = load_messages()
    msgs.append({
        "id":        str(uuid.uuid4())[:8],
        "from":      from_user,
        "from_name": USERS.get(from_user, {}).get("name", from_user.title()),
        "text":      text.strip(),
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "read":      False,
    })
    safe_save_json(MSG_PATH, msgs)


def mark_messages_read() -> None:
    msgs = load_messages()
    for m in msgs:
        m["read"] = True
    safe_save_json(MSG_PATH, msgs)


def unread_count() -> int:
    return sum(1 for m in load_messages() if not m.get("read", False))


# ── Mom → Kid messaging (Phase 3) ─────────────────────────────────────────────
KID_MSG_PATH = "data/kid_messages.json"


def _load_kid_messages_all() -> list:
    try:
        with open(KID_MSG_PATH) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_kid_message(to_user: str, from_user: str, text: str,
                     ref_id: str = "") -> dict:
    """Append one Mom→Kid (or system→Kid) message. Mirrors save_message
    shape but adds a 'to' field so we can route per-child."""
    import uuid
    from datetime import datetime
    to_u   = (to_user or "").lower().strip()
    from_u = (from_user or "").strip()
    rec = {
        "id":        str(uuid.uuid4())[:8],
        "to":        to_u,
        "from":      from_u,
        "from_name": USERS.get(from_u, {}).get("name", from_u.title()),
        "text":      (text or "").strip()[:4000],
        "ref_id":    (ref_id or "").strip(),
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "read":      False,
    }
    msgs = _load_kid_messages_all()
    msgs.append(rec)
    safe_save_json(KID_MSG_PATH, msgs)
    return rec


def load_kid_messages(username: str = "") -> list:
    """Return all kid_messages routed to `username` (case-insensitive).
    Pass '' to get every message."""
    msgs = _load_kid_messages_all()
    if not username:
        return msgs
    u = username.lower().strip()
    return [m for m in msgs if (m.get("to") or "").lower() == u]


def unread_kid_count(username: str) -> int:
    """Count unread messages routed to `username`."""
    if not username:
        return 0
    u = username.lower().strip()
    return sum(1 for m in _load_kid_messages_all()
               if (m.get("to") or "").lower() == u and not m.get("read", False))


def mark_kid_message_read(msg_id: str, username: str) -> bool:
    """Mark one message read IFF it is routed to `username`. Returns True
    on success, False if not found or not addressed to that user
    (prevents kid A from clearing kid B's badge)."""
    if not msg_id or not username:
        return False
    u = username.lower().strip()
    msgs = _load_kid_messages_all()
    found = False
    for m in msgs:
        if m.get("id") == msg_id and (m.get("to") or "").lower() == u:
            if not m.get("read", False):
                m["read"] = True
            found = True
            break
    if not found:
        return False
    safe_save_json(KID_MSG_PATH, msgs)
    return True
