from datetime import datetime
from pathlib import Path
from uuid import uuid4

from safe_utils import ensure_file, safe_save_json


DATA_DIR = Path("data")
NOTES_FILE = str(DATA_DIR / "notes.json")


def load_notes():
        data = ensure_file(NOTES_FILE, [])
        return data if isinstance(data, list) else []


def save_notes(notes):
        safe_save_json(NOTES_FILE, notes)


def route_note_text(text: str) -> dict:
        lowered = text.lower()

        if any(word in lowered for word in ["buy", "order", "pick up", "pickup", "amazon"]):
            return {"suggested_destination": "shopping"}
        if any(word in lowered for word in ["call", "email", "text", "message"]):
            return {"suggested_destination": "follow-up"}
        if any(word in lowered for word in ["appointment", "doctor", "dentist", "meeting", "party"]):
            return {"suggested_destination": "events"}
        if any(word in lowered for word in ["school", "lesson", "assignment", "math", "read"]):
            return {"suggested_destination": "school"}
        return {"suggested_destination": "notes"}


def add_note(text: str):
        notes = load_notes()
        notes.append({
            "id": str(uuid4()),
            "text": text,
            "status": "active",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })
        save_notes(notes)


def archive_note(note_id: str):
        notes = load_notes()
        for note in notes:
            if note.get("id") == note_id:
                note["status"] = "archived"
        save_notes(notes)


def search_notes(query: str):
        query = query.strip().lower()
        notes = load_notes()
        if not query:
            return notes
        return [n for n in notes if query in n.get("text", "").lower()]