import re
from io import BytesIO

try:
    from PyPDF2 import PdfReader as _PdfReader
except Exception:
    _PdfReader = None

from safe_utils import ensure_file, safe_save_json, debug_log


PREVIEWS_FILE = "data/school_previews.json"
WEEKS_FILE = "data/school_weeks.json"

WEEKDAY_HEADERS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

SUBJECT_PATTERNS = [
    r"Algebra 1/2 \(Saxon 3rd Edition\)",
    r"Math 87 \(Saxon 3rd Edition\)",
    r"Religion 8 \(Our Life in the Church\)",
    r"Religion 7 \(Acts of the Apostles\)",
    r"English 8 \(Easy Grammar Plus/7-8\)",
    r"Editing 7 \(Editor in Chief, Level 2\)",
    r"Spelling & Vocabulary 8 \(Vocabulary from Classical Roots B\)",
    r"Beginning Latin III Syllabus \(LS\)",
    r"Science 7 \(Exploring the Building Blocks of Science Book 7 Year 1\)",
    r"Science 6 \(Exploring the Building Blocks of Science Book 6\)",
    r"History & Geog 8 \(Old World & America\)",
    r"History & Geog 7 \(Old World & America\)",
    r"Poetry 8 Syllabus",
    r"Art 7 \(Ever Ancient, Ever New, Level 2\)",
    r"Music 8 \(Top 100 Classical Music 1685-1928 1-10\)",
    r"Music 7 \(Alfred's Essentials of Music\)",
    r"Reading 8 Syllabus",
    r"Reading 7 Syllabus",
]

SUBJECT_REGEX = re.compile(
    "(" + "|".join(SUBJECT_PATTERNS) + ")"
)

DAY_REGEX = re.compile(
    r"(Monday|Tuesday|Wednesday|Thursday|Friday),\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}"
)


# -------------------------
# PDF EXTRACTION
# -------------------------

def extract_pdf_text(pdf_bytes: bytes) -> str:
    if _PdfReader is None:
        debug_log("PyPDF2 not available — returning empty text")
        return ""

    try:
        reader = _PdfReader(BytesIO(pdf_bytes))
        pages = []

        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")

        return "\n".join(pages).strip()

    except Exception as e:
        debug_log("PDF extraction failed:", str(e))
        return ""


# -------------------------
# TEXT NORMALIZATION
# -------------------------

def normalize_text(text: str) -> str:
    # Normalize line endings and whitespace characters
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", " ")

    # Fix common smart quotes and special characters from PDFs
    text = text.replace("\u2019", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')
    text = text.replace("\u00d1", "-")
    text = text.replace("\u00d2", '"')
    text = text.replace("\u00d3", '"')
    text = text.replace("\u00d4", '"')
    text = text.replace("\u00d5", "'")

    # Remove page headers/footers in multiple formats:
    # "3/22/26, 6:37 PMPage 1 of 7" or "3/22/26, 6:37 PM\nPage 1 of 7"
    text = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4},?\s*\d{1,2}:\d{2}\s*(?:AM|PM)?\s*Page\s*\d+\s*of\s*\d+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"Page\s+\d+\s+of\s+\d+", " ", text, flags=re.IGNORECASE)

    # Collapse multiple spaces (but not newlines yet)
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Inject newlines before day headers (e.g. "Monday, March 23, 2026")
    text = DAY_REGEX.sub(lambda m: "\n" + m.group(0), text)

    # Inject newlines before known subject names
    # This handles run-together text like "...Lesson 63Religion 8..."
    text = SUBJECT_REGEX.sub(lambda m: "\n" + m.group(0), text)

    # Strip trailing " Syllabus - Week: X, Day: Y" from subject header lines
    # so each subject line ends cleanly before its assignment text begins
    text = re.sub(
        r"(" + "|".join(SUBJECT_PATTERNS) + r")\s+Syllabus\s+-\s+Week:\s*\d+,\s*Day:\s*\d+",
        lambda m: m.group(1),
        text
    )

    # Also handle subjects that don't have "Syllabus -" but have "- Week: X, Day: Y"
    text = re.sub(r"\s+-\s+Week:\s*\d+,\s*Day:\s*\d+", "", text)

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# -------------------------
# SUBJECT HELPERS
# -------------------------

def canonical_subject(subject_header: str) -> str:
    subject_header = subject_header.strip()

    mapping = {
        "Algebra 1/2 (Saxon 3rd Edition)": "Algebra 1/2",
        "Math 87 (Saxon 3rd Edition)": "Math 87",
        "Religion 8 (Our Life in the Church)": "Religion 8",
        "Religion 7 (Acts of the Apostles)": "Religion 7",
        "English 8 (Easy Grammar Plus/7-8)": "English 8",
        "Editing 7 (Editor in Chief, Level 2)": "Editing 7",
        "Spelling & Vocabulary 8 (Vocabulary from Classical Roots B)": "Spelling & Vocabulary 8",
        "Beginning Latin III Syllabus (LS)": "Beginning Latin III",
        "Science 7 (Exploring the Building Blocks of Science Book 7 Year 1)": "Science 7",
        "Science 6 (Exploring the Building Blocks of Science Book 6)": "Science 6",
        "History & Geog 8 (Old World & America)": "History & Geog 8",
        "History & Geog 7 (Old World & America)": "History & Geog 7",
        "Poetry 8 Syllabus": "Poetry 8",
        "Art 7 (Ever Ancient, Ever New, Level 2)": "Art 7",
        "Music 8 (Top 100 Classical Music 1685-1928 1-10)": "Music 8",
        "Music 7 (Alfred's Essentials of Music)": "Music 7",
        "Reading 8 Syllabus": "Reading 8",
        "Reading 7 Syllabus": "Reading 7",
    }

    return mapping.get(subject_header, subject_header)


def is_math_subject(subject: str) -> bool:
    subject_upper = subject.upper()
    return "ALGEBRA" in subject_upper or subject_upper.startswith("MATH ")


def is_math_test_text(subject: str, assignment_text: str) -> bool:
    combined = f"{subject} {assignment_text}".upper()
    return "TEST" in combined or "QUARTERLY ASSESSMENT" in combined


# -------------------------
# PARSING
# -------------------------

def split_into_day_sections(text: str):
    matches = list(DAY_REGEX.finditer(text))
    sections = []

    if not matches:
        return sections

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)

        day_label = match.group(0).strip()
        weekday = day_label.split(",", 1)[0].strip()

        section_text = text[start + len(match.group(0)):end].strip()
        sections.append({
            "weekday": weekday,
            "day_label": day_label,
            "text": section_text,
        })

    return sections


def parse_day_blocks(section_text: str):
    matches = list(SUBJECT_REGEX.finditer(section_text))
    blocks = []

    if not matches:
        if section_text.strip():
            blocks.append({
                "subject": "Unsorted",
                "assignment_text": section_text.strip(),
                "is_math": False,
                "is_math_test": False,
            })
        return blocks

    for index, match in enumerate(matches):
        subject_header = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section_text)

        assignment_text = section_text[start:end].strip()
        subject = canonical_subject(subject_header)

        blocks.append({
            "subject": subject,
            "assignment_text": assignment_text,
            "is_math": is_math_subject(subject),
            "is_math_test": is_math_test_text(subject, assignment_text),
        })

    return blocks


def parse_school_pdf_text(raw_text: str, child: str = "") -> dict:
    try:
        text = normalize_text(raw_text)
        parsed_days = []

        for day in split_into_day_sections(text):
            parsed_days.append({
                "weekday": day["weekday"],
                "day_label": day["day_label"],
                "blocks": parse_day_blocks(day["text"]),
            })

        return {
            "child": child,
            "parsed_days": parsed_days,
            "raw_text": text,
        }

    except Exception as e:
        debug_log("Parsing failed — returning safe fallback:", str(e))
        return {
            "child": child,
            "parsed_days": [],
            "raw_text": raw_text or "",
        }


# -------------------------
# STORAGE
# -------------------------

def save_school_preview(child: str, filename: str, raw_text: str, parsed: dict):
    previews = ensure_file(PREVIEWS_FILE, {})

    previews[child] = {
        "child": child,
        "filename": filename,
        "raw_text": raw_text,
        "parsed": parsed,
    }

    safe_save_json(PREVIEWS_FILE, previews)
    return previews[child]


def load_school_preview(child: str):
    previews = ensure_file(PREVIEWS_FILE, {})
    return previews.get(child)


def load_all_school_previews():
    return ensure_file(PREVIEWS_FILE, {})


def load_school_previews():
    return load_all_school_previews()


def approve_school_preview(child: str):
    previews = ensure_file(PREVIEWS_FILE, {})
    preview = previews.get(child)

    if not preview:
        return None

    weeks = ensure_file(WEEKS_FILE, {"approved": {}})
    weeks.setdefault("approved", {})
    weeks["approved"][child] = preview.get("parsed", {})

    safe_save_json(WEEKS_FILE, weeks)
    return weeks["approved"][child]


def load_school_weeks():
    return ensure_file(WEEKS_FILE, {"approved": {}})


# -------------------------
# QUERY
# -------------------------

def get_school_assignments_for_weekday(weekday: str):
    weeks = load_school_weeks()
    approved = weeks.get("approved", {})
    result = {}

    for child, parsed in approved.items():
        parsed_days = parsed.get("parsed_days", [])

        for day in parsed_days:
            day_weekday = str(day.get("weekday", "")).strip().lower()
            if weekday.lower() == day_weekday:
                result[child] = day
                break

    return result
