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
    Save JSON safely with AUTOMATIC versioned snapshots.
    Every save first copies the prior version into data/history/ (mirroring
    the original directory structure). Skips snapshotting for paths that are
    on the deny-list (caches, the snapshot dir itself, etc.).
    Returns True on success, False on failure.
    """
    try:
        # Snapshot the prior version BEFORE we overwrite. We do this at the
        # one-and-only chokepoint so every page/companion/importer in the app
        # gets versioned history "for free" with no per-call wiring.
        try:
            if _should_snapshot(path):
                snapshot_before_save(path)
        except Exception as _se:
            debug_log("Auto-snapshot failed (continuing save):", path, str(_se))
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
MAX_SNAPSHOTS_PER_FILE = 30

# Paths/prefixes that we deliberately do NOT snapshot:
#   - the snapshot directory itself (would recurse into infinity)
#   - the meal-plan and companion-history archive dirs (already-archives)
#   - high-churn caches with no audit value
#   - large auto-fetched data that re-downloads on demand
SNAPSHOT_DENYLIST_PREFIXES = (
    "data/history/",
    "data/meal_plan/.backups/",
    "data/saint_cache/",
    "data/readings_cache/",
    "data/calendar_cache.json",
    "data/subscribed_calendar_cache.json",
    "data/auth/",  # session tokens — sensitive + high churn, no audit value
)
SNAPSHOT_DENYLIST_SUBSTRINGS = (
    ".archive/",      # any companion *_history.json.archive/ tree
    "/.backups/",     # any future per-area .backups dir
)
# Files that should be snapshotted before saving (kept for backward compat;
# now obsolete because EVERY data file is auto-snapshotted by default).
SNAPSHOTTED_FILES = set()


def _normalise(path: str) -> str:
    """Normalise to forward-slash relative path for prefix/substring matching."""
    return path.replace(os.sep, "/")


def _should_snapshot(path: str) -> bool:
    """Return True if `path` is a data file that deserves an auto-snapshot.
    Anything outside data/, anything on the deny-list, and non-JSON files
    are skipped."""
    if not path:
        return False
    p = _normalise(path)
    if not p.startswith("data/"):
        return False
    if not p.endswith(".json"):
        return False
    for pref in SNAPSHOT_DENYLIST_PREFIXES:
        if p.startswith(pref):
            return False
    for sub in SNAPSHOT_DENYLIST_SUBSTRINGS:
        if sub in p:
            return False
    return True


def _snapshot_dir_for(original_path: str) -> str:
    """Mirror the original file's parent dir under data/history/ so that
    nested paths (e.g. data/day_templates/Monday.json) get their own
    namespace and can never collide with a same-named file elsewhere."""
    p = _normalise(original_path)
    if p.startswith("data/"):
        rel_parent = os.path.dirname(p[len("data/"):])
    else:
        rel_parent = os.path.dirname(p)
    return os.path.join(HISTORY_DIR, rel_parent) if rel_parent else HISTORY_DIR


def _snapshot_filename(original_path: str, timestamp: str) -> str:
    """Build the snapshot filename inside the mirrored history sub-dir.
    e.g. data/day_templates/Monday.json
        -> data/history/day_templates/Monday__2026-04-18T14-05-32-123456-ab12.json
    """
    basename = os.path.basename(original_path)
    stem, ext = os.path.splitext(basename)
    safe_ts = timestamp.replace(":", "-")
    return os.path.join(_snapshot_dir_for(original_path), f"{stem}__{safe_ts}{ext}")


def snapshot_before_save(path: str) -> bool:
    """Save a timestamped copy of `path` into the mirrored history dir before
    it is overwritten. Collision-proof (microseconds + uuid suffix). Keeps the
    most recent MAX_SNAPSHOTS_PER_FILE per file. Returns True if a snapshot
    was created, False if the file didn't exist yet or the op failed."""
    if not os.path.exists(path):
        return False
    try:
        import uuid as _uuid
        out_dir = _snapshot_dir_for(path)
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")
        suffix = _uuid.uuid4().hex[:6]
        basename = os.path.basename(path)
        stem, ext = os.path.splitext(basename)
        dest = os.path.join(out_dir, f"{stem}__{ts}-{suffix}{ext}")
        shutil.copy2(path, dest)
        _purge_old_snapshots(path)
        return True
    except Exception as e:
        debug_log("Snapshot failed for:", path, "| Error:", str(e))
        return False


def _purge_old_snapshots(original_path: str):
    """Remove oldest snapshots beyond MAX_SNAPSHOTS_PER_FILE for a given file
    (scoped to that file's mirrored history sub-dir)."""
    try:
        out_dir = _snapshot_dir_for(original_path)
        if not os.path.isdir(out_dir):
            return
        stem = os.path.splitext(os.path.basename(original_path))[0]
        all_snapshots = sorted([
            f for f in os.listdir(out_dir)
            if f.startswith(stem + "__") and f.endswith(".json")
        ])
        excess = len(all_snapshots) - MAX_SNAPSHOTS_PER_FILE
        if excess > 0:
            for old in all_snapshots[:excess]:
                try:
                    os.remove(os.path.join(out_dir, old))
                except Exception:
                    pass
    except Exception as e:
        debug_log("Purge snapshots failed:", str(e))


def _walk_history_dir():
    """Yield (snapshot_path, snapshot_filename, mirrored_subpath) for every
    snapshot file under HISTORY_DIR, recursing into mirrored sub-dirs."""
    if not os.path.exists(HISTORY_DIR):
        return
    for root, _dirs, files in os.walk(HISTORY_DIR):
        for f in files:
            if not f.endswith(".json"):
                continue
            full = os.path.join(root, f)
            rel_dir = os.path.relpath(root, HISTORY_DIR)
            if rel_dir == ".":
                rel_dir = ""
            yield full, f, rel_dir


def list_snapshots(original_path: str = None) -> list:
    """List available snapshots (newest first). If `original_path` is given,
    return only snapshots for that file. Each entry has filename, stem,
    timestamp, path, original_path, and a stable `key` (relpath under
    HISTORY_DIR) suitable for restore."""
    results = []
    try:
        for full_path, fname, rel_dir in _walk_history_dir():
            name_no_ext = fname[:-5]
            if "__" not in name_no_ext:
                continue
            file_stem, ts_raw = name_no_ext.rsplit("__", 1)
            # Strip the uuid suffix off the timestamp for display, if present
            ts_display_raw = ts_raw
            if "-" in ts_raw and len(ts_raw.rsplit("-", 1)[-1]) == 6:
                ts_display_raw = ts_raw.rsplit("-", 1)[0]
            ts_display = ts_display_raw.replace("-", ":", 2)
            # Reconstruct the original path from the mirrored sub-dir + stem
            if rel_dir:
                original = f"data/{rel_dir.replace(os.sep, '/')}/{file_stem}.json"
            else:
                original = f"data/{file_stem}.json"
            if original_path and original != original_path:
                continue
            key = os.path.relpath(full_path, HISTORY_DIR).replace(os.sep, "/")
            results.append({
                "filename": fname,
                "key": key,
                "stem": file_stem,
                "timestamp": ts_display,
                "timestamp_raw": ts_raw,
                "path": full_path,
                "original_path": original,
            })
    except Exception as e:
        debug_log("list_snapshots failed:", str(e))
    # Sort newest first by timestamp_raw
    results.sort(key=lambda r: r.get("timestamp_raw", ""), reverse=True)
    return results


def _resolve_snapshot_path(snapshot_key: str) -> str:
    """Accept either a bare filename (legacy flat layout) or a relpath under
    HISTORY_DIR (new nested layout) and return an absolute snapshot path."""
    candidate = os.path.join(HISTORY_DIR, snapshot_key)
    if os.path.exists(candidate):
        return candidate
    # Fallback: legacy callers may have passed just the basename — search
    for full_path, fname, _rel in _walk_history_dir():
        if fname == snapshot_key:
            return full_path
    return candidate  # may not exist; caller will check


def restore_snapshot(snapshot_key: str) -> tuple:
    """Restore a snapshot by copying it over its original file. First
    snapshots the current version so the restore itself is reversible.
    `snapshot_key` is the relpath under HISTORY_DIR (preferred) or a bare
    filename (legacy). Returns (success: bool, message: str)."""
    snapshot_path = _resolve_snapshot_path(snapshot_key)
    if not os.path.exists(snapshot_path):
        return False, f"Snapshot not found: {snapshot_key}"
    try:
        # Reconstruct the original path from the mirrored layout
        rel = os.path.relpath(snapshot_path, HISTORY_DIR)
        rel_parent = os.path.dirname(rel).replace(os.sep, "/")
        fname = os.path.basename(snapshot_path)
        name_no_ext = fname[:-5]
        if "__" not in name_no_ext:
            return False, "Cannot determine original file from snapshot name."
        file_stem = name_no_ext.rsplit("__", 1)[0]
        original_path = (f"data/{rel_parent}/{file_stem}.json"
                         if rel_parent else f"data/{file_stem}.json")
        # Snapshot the current version before overwriting (reversible restore)
        snapshot_before_save(original_path)
        ensure_parent_dir(original_path)
        shutil.copy2(snapshot_path, original_path)
        return True, f"Restored {original_path} from snapshot."
    except Exception as e:
        return False, f"Restore failed: {str(e)}"


def load_snapshot_data(snapshot_key: str):
    """Load and return the JSON data from a snapshot file without restoring it."""
    snapshot_path = _resolve_snapshot_path(snapshot_key)
    return safe_load_json(snapshot_path, None)
