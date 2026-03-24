import json
import urllib.request
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

try:
    from dateutil.rrule import rrulestr
except Exception:
    rrulestr = None

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CALENDAR_SOURCES_FILE = DATA_DIR / "calendar_sources.json"

DEFAULT_SOURCES = [
    {
        "name": "Mom",
        "url": "",
        "applies_to": ["Mom"],
    }
]


def _load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, payload: Any):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_calendar_sources() -> list[dict]:
    return _load_json(CALENDAR_SOURCES_FILE, DEFAULT_SOURCES)


def save_calendar_sources(sources: list[dict]) -> None:
    _save_json(CALENDAR_SOURCES_FILE, sources)


def unfold_ics_lines(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded = []
    for line in lines:
        if not line:
            continue
        if line.startswith(" ") or line.startswith("\t"):
            if unfolded:
                unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def parse_ics_property(line: str):
    if ":" not in line:
        return line.upper(), {}, ""
    left, value = line.split(":", 1)
    parts = left.split(";")
    name = parts[0].upper()
    params = {}
    for piece in parts[1:]:
        if "=" in piece:
            k, v = piece.split("=", 1)
            params[k.upper()] = v
    return name, params, value.strip()


def parse_ics_datetime(value: str, params: dict):
    value = value.strip()
    value_type = params.get("VALUE", "").upper()

    if value_type == "DATE" or (len(value) == 8 and value.isdigit()):
        return datetime.strptime(value, "%Y%m%d"), True

    fmts = ["%Y%m%dT%H%M%S", "%Y%m%dT%H%M"]
    if value.endswith("Z"):
        base = value[:-1]
        for fmt in fmts:
            try:
                return datetime.strptime(base, fmt), False
            except Exception:
                pass
    else:
        for fmt in fmts:
            try:
                return datetime.strptime(value, fmt), False
            except Exception:
                pass

    raise ValueError(f"Unsupported ICS datetime: {value}")


def format_time_label(dt: datetime, all_day: bool) -> str:
    if all_day:
        return "All day"
    return dt.strftime("%I:%M %p").lstrip("0")


def event_matches_day(start_dt: datetime, end_dt: datetime | None, day: date, all_day: bool) -> bool:
    if all_day:
        start_day = start_dt.date()
        end_day = end_dt.date() if end_dt else (start_day + timedelta(days=1))
        return start_day <= day < end_day

    actual_end = end_dt or start_dt
    day_start = datetime.combine(day, time.min)
    day_end = datetime.combine(day, time.max)
    return start_dt <= day_end and actual_end >= day_start


def fetch_ics_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_events_from_ics(raw_text: str, day: date, source_name: str, applies_to: list[str]) -> list[dict]:
    lines = unfold_ics_lines(raw_text)

    vevents = []
    current = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            current = []
        elif line == "END:VEVENT":
            if current is not None:
                vevents.append(current)
            current = None
        elif current is not None:
            current.append(line)

    parsed_events = []

    for block in vevents:
        props = {}
        for line in block:
            name, params, value = parse_ics_property(line)
            props.setdefault(name, []).append((params, value))

        if "DTSTART" not in props:
            continue

        try:
            dtstart_params, dtstart_value = props["DTSTART"][0]
            start_dt, all_day = parse_ics_datetime(dtstart_value, dtstart_params)
        except Exception:
            continue

        end_dt = None
        if "DTEND" in props:
            try:
                dtend_params, dtend_value = props["DTEND"][0]
                end_dt, _ = parse_ics_datetime(dtend_value, dtend_params)
            except Exception:
                end_dt = None

        summary = props.get("SUMMARY", [({}, "Untitled")])[0][1]
        location = props.get("LOCATION", [({}, "")])[0][1]
        rrule_value = props.get("RRULE", [({}, "")])[0][1]

        duration = end_dt - start_dt if end_dt else (timedelta(days=1) if all_day else timedelta(hours=1))
        occurrence_start = start_dt
        occurrence_end = end_dt or (start_dt + duration)
        matches = False

        if rrule_value and rrulestr is not None:
            try:
                rule = rrulestr(rrule_value, dtstart=start_dt)
                window_start = datetime.combine(day, time.min)
                window_end = datetime.combine(day, time.max)
                occurrences = list(rule.between(window_start, window_end, inc=True))
                if occurrences:
                    occurrence_start = occurrences[0]
                    occurrence_end = occurrence_start + duration
                    matches = True
            except Exception:
                matches = event_matches_day(start_dt, end_dt, day, all_day)
        else:
            matches = event_matches_day(start_dt, end_dt, day, all_day)

        if not matches:
            continue

        parsed_events.append(
            {
                "title": summary or "Untitled",
                "location": location or "",
                "time_label": format_time_label(occurrence_start, all_day),
                "all_day": all_day,
                "source_calendar": source_name,
                "applies_to": applies_to,
                "display": f"{format_time_label(occurrence_start, all_day)} — {summary}" + (f" — {location}" if location else ""),
                "sort_key": (0 if all_day else 1, occurrence_start),
            }
        )

    parsed_events.sort(key=lambda x: x["sort_key"])
    return parsed_events


def get_all_events_for_date(target_date: date) -> list[dict]:
    events = []

    for source in load_calendar_sources():
        url = source.get("url", "").strip()
        if not url:
            continue

        name = source.get("name", "Calendar")
        applies_to = source.get("applies_to", [])

        try:
            raw_text = fetch_ics_text(url)
            events.extend(parse_events_from_ics(raw_text, target_date, name, applies_to))
        except Exception:
            continue

    events.sort(key=lambda x: x["sort_key"])
    return events


def get_events_for_date(target_date: date, person: str | None = None) -> list[dict]:
    events = get_all_events_for_date(target_date)
    if not person:
        return events
    return [e for e in events if person in e.get("applies_to", [])]