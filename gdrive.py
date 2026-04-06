"""
Google Drive integration helper — Python wrapper around gdrive_helper.js
Uses @replit/connectors-sdk (Node.js) via subprocess for authenticated Drive API calls.
"""
import subprocess, json, os

_HELPER = os.path.join(os.path.dirname(__file__), "gdrive_helper.js")
_NODE = "node"


def _run(args: list, binary_output: bool = False):
    result = subprocess.run(
        [_NODE, _HELPER] + args,
        capture_output=True,
        timeout=25,
    )
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="ignore").strip()
        try:
            parsed = json.loads(err)
            raise RuntimeError(parsed.get("error", err))
        except (json.JSONDecodeError, KeyError):
            raise RuntimeError(err or f"gdrive_helper exited {result.returncode}")
    if binary_output:
        return result.stdout
    return json.loads(result.stdout.decode("utf-8"))


def list_files(folder_id: str = "root") -> list:
    """List files/folders in a Drive folder. Returns list of file dicts."""
    data = _run(["list", folder_id])
    return data.get("files", [])


def search_files(query: str) -> list:
    """Search Drive files by name. Returns list of file dicts."""
    data = _run(["search", query])
    return data.get("files", [])


def get_file_meta(file_id: str) -> dict:
    """Get metadata for a single file."""
    return _run(["meta", file_id])


def download_file(file_id: str, mime_type: str = "") -> bytes:
    """Download file content as bytes. Google Docs are exported as plain text."""
    return _run(["download", file_id, mime_type], binary_output=True)


FOLDER_MIME = "application/vnd.google-apps.folder"
DOC_MIME    = "application/vnd.google-apps.document"

MIME_ICONS = {
    FOLDER_MIME: "📁",
    "application/pdf": "📄",
    DOC_MIME: "📝",
    "application/vnd.google-apps.spreadsheet": "📊",
    "text/plain": "📃",
}

def mime_icon(mime: str) -> str:
    return MIME_ICONS.get(mime, "📄")


def is_readable(mime: str) -> bool:
    """Returns True if the file can be read as text by the school upload."""
    return mime in (
        "application/pdf",
        DOC_MIME,
        "text/plain",
        "application/vnd.google-apps.spreadsheet",
    )
