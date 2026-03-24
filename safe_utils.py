import json
import os
from datetime import date, timedelta


def debug_log(*parts):
    """Simple safe logger."""
    try:
        print("[DEBUG]", *parts)
    except Exception:
        pass


def ensure_parent_dir(path):
    """Make sure the parent folder exists."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def ensure_file(path, default):
    """
    Ensure a JSON file exists.
    If missing, create it with the provided default value.
    """
    ensure_parent_dir(path)

    if not os.path.exists(path):
        safe_save_json(path, default)
        return default

    return safe_load_json(path, default)


def safe_load_json(path, default):
    """
    Load JSON safely.
    Returns default if file is missing, empty, or malformed.
    """
    try:
        if not os.path.exists(path):
            debug_log("JSON file missing, using default:", path)
            return default

        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()

        if not raw:
            debug_log("JSON file empty, using default:", path)
            return default

        return json.loads(raw)

    except Exception as e:
        debug_log("Failed to load JSON:", path, "| Error:", str(e))
        return default


def safe_save_json(path, data):
    """
    Save JSON safely.
    Returns True on success, False on failure.
    """
    try:
        ensure_parent_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        debug_log("Failed to save JSON:", path, "| Error:", str(e))
        return False


def safe_get(obj, key, default=None):
    """
    Safe dictionary lookup.
    """
    try:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return default
    except Exception:
        return default


def today_iso():
    return date.today().isoformat()


def yesterday_iso():
    return (date.today() - timedelta(days=1)).isoformat()


def tomorrow_iso():
    return (date.today() + timedelta(days=1)).isoformat()