import json
import os
import shutil
from datetime import datetime, date, timedelta


# -------------------------
# LOGGING
# -------------------------

def debug_log(*parts):
    """Simple safe logger."""
    try:
        print("[DEBUG]", *parts)
    except Exception:
        pass


# -------------------------
# PATH HELPERS
# -------------------------

def ensure_parent_dir(path):
    """Make sure the parent folder exists."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


# -------------------------
# JSON HELPERS
# -------------------------

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
    Does NOT snapshot automatically — call snapshot_before_save() first
    when saving user-facing data files.
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
    """Safe dictionary lookup."""
    try:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return default
    except Exception:
        return default


# -------------------------
# DATE HELPERS
# -------------------------

def today_iso():
    return date.today().isoformat()


def yesterday_iso():
    return (date.today() - timedelta(days=1)).isoformat()


def tomorrow_iso():
    return (date.today() + timedelta(days=1)).isoformat()


# -------------------------
# SNAPSHOT SYSTEM
# -------------------------

HISTORY_DIR = "data/history"
MAX_SNAPSHOTS_PER_FILE = 10

# Files that should be snapshotted before saving
SNAPSHOTTED_FILES = {
    "data/chores.json",
    "data/manual_tasks.json",
    "data/notes.json",
    "data/mom_notes.json",
    "data/school_previews.json",
    "data/school_weeks.json",
    "data/family_schedule.json",
    "data/roadmap.json",
    "data/liturgical.json",
}


def _snapshot_filename(original_path: str, timestamp: str) -> str:
    """
    Build the snapshot filename.
    e.g. data/chores.json -> data/history/chores__2026-03-23T14-05-32.json
    """
    basename = os.path.basename(original_path)          # chores.json
    stem, ext = os.path.splitext(basename)               # chores, .json
    safe_ts = timestamp.replace(":", "-")                # colons illegal on Windows
    return os.path.join(HISTORY_DIR, f"{stem}__{safe_ts}{ext}")


def snapshot_before_save(path: str) -> bool:
    """
    Save a timestamped copy of `path` into data/history/ before it is overwritten.
    Keeps only the most recent MAX_SNAPSHOTS_PER_FILE snapshots for that file.
    Returns True if a snapshot was created, False if the file didn't exist yet
    (nothing to snapshot) or if the operation was skipped/failed.
    """
    if not os.path.exists(path):
        return False  # Nothing to snapshot yet

    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        dest = _snapshot_filename(path, timestamp)
        shutil.copy2(path, dest)

        # Purge old snapshots for this file, keeping only the newest N
        _purge_old_snapshots(path)
        return True

    except Exception as e:
        debug_log("Snapshot failed for:", path, "| Error:", str(e))
        return False


def _purge_old_snapshots(original_path: str):
    """Remove oldest snapshots beyond MAX_SNAPSHOTS_PER_FILE for a given file."""
    try:
        stem = os.path.splitext(os.path.basename(original_path))[0]
        all_snapshots = sorted([
            f for f in os.listdir(HISTORY_DIR)
            if f.startswith(stem + "__") and f.endswith(".json")
        ])
        excess = len(all_snapshots) - MAX_SNAPSHOTS_PER_FILE
        if excess > 0:
            for old in all_snapshots[:excess]:
                try:
                    os.remove(os.path.join(HISTORY_DIR, old))
                except Exception:
                    pass
    except Exception as e:
        debug_log("Purge snapshots failed:", str(e))


def list_snapshots(original_path: str = None) -> list:
    """
    List available snapshots.
    If original_path is given, list only snapshots for that file.
    Returns list of dicts: {filename, stem, timestamp, path, original_path}
    """
    if not os.path.exists(HISTORY_DIR):
        return []

    results = []
    try:
        for f in sorted(os.listdir(HISTORY_DIR), reverse=True):
            if not f.endswith(".json"):
                continue

            # Parse stem and timestamp from filename like "chores__2026-03-23T14-05-32.json"
            name_no_ext = f[:-5]  # remove .json
            if "__" not in name_no_ext:
                continue

            parts = name_no_ext.rsplit("__", 1)
            if len(parts) != 2:
                continue

            file_stem, ts_raw = parts
            original = f"data/{file_stem}.json"

            if original_path and original != original_path:
                continue

            # Convert safe timestamp back to readable format
            ts_display = ts_raw.replace("-", ":", 2)  # only first two dashes are colons

            results.append({
                "filename": f,
                "stem": file_stem,
                "timestamp": ts_display,
                "timestamp_raw": ts_raw,
                "path": os.path.join(HISTORY_DIR, f),
                "original_path": original,
            })
    except Exception as e:
        debug_log("list_snapshots failed:", str(e))

    return results


def restore_snapshot(snapshot_filename: str) -> tuple:
    """
    Restore a snapshot by copying it over the original file.
    First snapshots the current file so the restore itself is reversible.
    Returns (success: bool, message: str)
    """
    snapshot_path = os.path.join(HISTORY_DIR, snapshot_filename)

    if not os.path.exists(snapshot_path):
        return False, f"Snapshot not found: {snapshot_filename}"

    # Parse the original file path from the snapshot filename
    name_no_ext = snapshot_filename[:-5]
    if "__" not in name_no_ext:
        return False, "Cannot determine original file from snapshot name."

    file_stem = name_no_ext.rsplit("__", 1)[0]
    original_path = f"data/{file_stem}.json"

    try:
        # Snapshot the current version before overwriting (so restore is reversible)
        snapshot_before_save(original_path)

        # Restore
        shutil.copy2(snapshot_path, original_path)
        return True, f"Restored {file_stem}.json from snapshot {name_no_ext.rsplit('__', 1)[1]}."

    except Exception as e:
        return False, f"Restore failed: {str(e)}"


def load_snapshot_data(snapshot_filename: str):
    """Load and return the JSON data from a snapshot file without restoring it."""
    snapshot_path = os.path.join(HISTORY_DIR, snapshot_filename)
    return safe_load_json(snapshot_path, None)
