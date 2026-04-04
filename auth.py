"""
auth.py — Session-based auth for McAdams Family Dashboard.

PIN: 4-digit code (MMDD of birthday by default).
Michael/James: tap avatar = instant login (no PIN).
Sessions: in-memory dict, cleared on server restart; session cookie
          has no max-age, so it dies when the browser is closed.
"""
import os, json, secrets

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
                     "/chores", "/prayer", "/change-pin"])

CHILD_ALLOWED_GET: dict[str, frozenset] = {
    "jp":      _SHARED | frozenset(["/schedule/jp"]),
    "joseph":  _SHARED | frozenset(["/schedule/joseph"]),
    "michael": _SHARED | frozenset(["/schedule/michael"]),
    "james":   frozenset(["/"]),
}

# Paths children may POST to
CHILD_POST_ALLOWED = frozenset(["/toggle-task", "/message-mom", "/change-pin"])

# ── PIN storage ───────────────────────────────────────────────────────────────
AUTH_PATH = "data/auth/pins.json"


def load_pins() -> dict:
    try:
        with open(AUTH_PATH) as f:
            return json.load(f)
    except Exception:
        return {u: "0000" for u in USERS}


def save_pins(pins: dict) -> None:
    os.makedirs("data/auth", exist_ok=True)
    existing = load_pins()
    existing.update(pins)
    with open(AUTH_PATH, "w") as f:
        json.dump(existing, f, indent=2)


def get_pin(username: str) -> str:
    return load_pins().get(username, "0000")


def check_pin(username: str, entered: str) -> bool:
    if username not in USERS:
        return False
    if not USERS[username].get("pin_required", True):
        return True
    return entered == get_pin(username)


# ── Session store (in-memory — cleared on server restart) ────────────────────
_SESSIONS: dict = {}


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = username
    return token


def get_session_user(token: str):
    return _SESSIONS.get(token)


def destroy_session(token: str):
    _SESSIONS.pop(token, None)


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
    os.makedirs("data", exist_ok=True)
    with open(MSG_PATH, "w") as f:
        json.dump(msgs, f, indent=2)


def mark_messages_read() -> None:
    msgs = load_messages()
    for m in msgs:
        m["read"] = True
    with open(MSG_PATH, "w") as f:
        json.dump(msgs, f, indent=2)


def unread_count() -> int:
    return sum(1 for m in load_messages() if not m.get("read", False))
