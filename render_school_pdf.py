"""
School Week printable PDF generator.

Builds a 15-page portrait Letter PDF — one page per (child, weekday)
pair, ordered JP Mon..Fri, then Joseph Mon..Fri, then Michael Mon..Fri.
Each page shows a single child's assignments for a single day with an
empty checkbox to the left of every line, so Lauren and the kids can
tick work off as they go.

Pulls live data via daily_schedule_engine.extract_school_tasks_for_child,
the same source the daily-schedule grids and weekly student views use,
so this PDF stays in lock-step with the on-screen view.

Public API:
    generate_school_pdf(target_date_str: str = "") -> bytes
"""

from io import BytesIO
from datetime import date, datetime, timedelta

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.enums import TA_LEFT

from config import child_color
from daily_schedule_engine import extract_school_tasks_for_child
from data_helpers import (
    load_curriculum, get_curriculum_week,
    subject_meeting_days, subject_day_index, resolve_week_text,
)


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
CHILDREN = ["JP", "Joseph", "Michael"]


def _parse_target_date(target_date_str: str):
    """Parse target_date_str (YYYY-MM-DD) or fall back to today.
    Returns a date object."""
    s = (target_date_str or "").strip()
    if s:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def _monday_of_week(d):
    """Return the Monday of d's school week.
    Mon-Sat (weekday 0..5) snap back to that week's Monday.
    Sunday (weekday 6) snaps FORWARD to the upcoming Monday — Sunday is
    treated as the start of the new school week, not the tail of the old one."""
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d - timedelta(days=d.weekday())


def _week_dates(target_date_str: str):
    """Return list of (date, weekday_name) tuples for Mon-Fri of the target week."""
    monday = _monday_of_week(_parse_target_date(target_date_str))
    return [(monday + timedelta(days=i), WEEKDAYS[i]) for i in range(5)]


def _assignment_text(block) -> str:
    """Pull the human-readable assignment text from one extract_school_tasks_for_child
    block. Prefer assignment_text; fall back to first checklist item; finally
    the empty string. Defensive against missing keys."""
    if not isinstance(block, dict):
        return ""
    txt = (block.get("assignment_text") or "").strip()
    if txt:
        return txt
    chk = block.get("checklist") or []
    if isinstance(chk, list) and chk:
        first = chk[0]
        if isinstance(first, str):
            return first.strip()
    return ""


def _child_blocks_safe(child: str, weekday: str):
    """Wrap extract_school_tasks_for_child so a single bad child/day cannot
    abort the whole PDF build.  Retained for any caller still expecting the
    engine-driven list — the printable PDF itself now uses
    _curriculum_blocks_for_day instead (see docstring there)."""
    try:
        out = extract_school_tasks_for_child(child, weekday) or []
        return out if isinstance(out, list) else []
    except Exception:
        return []


def _curriculum_blocks_for_day(child: str, weekday: str, curriculum: dict):
    """Build per-(child, weekday) assignment blocks straight from curriculum.json.

    The on-screen daily-view engine (extract_school_tasks_for_child) deliberately
    drives `day_pref` from each subject's stored `_current_day` cursor, so manual
    cursor advances (e.g. "skip ahead to Day 5") show up immediately on today's
    grid.  That's correct for one-day-at-a-time use, but it means a Mon-Fri
    weekly printable shows the SAME lesson for every weekday a subject meets.

    For the PDF we want each weekday to show its own position-based lesson:
    Monday = Day 1 of this curriculum week, Tuesday = Day 2, etc., as derived
    from the subject's `_weekdays` list via subject_day_index.

    Returns a list of dicts shaped to mirror the engine's output keys
    (subject / assignment_text / is_math / checklist / from_curriculum), so
    downstream rendering helpers (e.g. _assignment_text) work unchanged.
    Subjects with no `_current_week`, `_current_week >= 999` (completed
    sentinel), no meeting on `weekday`, or empty resolved text are skipped.
    """
    out = []
    if not isinstance(curriculum, dict):
        return out

    child_subjects = curriculum.get(child, {}) or {}
    if not isinstance(child_subjects, dict):
        return out

    for subject, subj_node in child_subjects.items():
        if not isinstance(subj_node, dict):
            continue
        # Per spec: skip subjects with NO _current_week, an invalid value, or
        # the 999 "completed" sentinel.  No global-week fallback — the PDF
        # only prints curriculum-claimed subjects with a real cursor.
        _raw_week = subj_node.get("_current_week")
        if _raw_week is None:
            continue
        try:
            subj_week = int(_raw_week)
        except (TypeError, ValueError):
            continue
        if subj_week >= 999:
            continue
        try:
            meeting = subject_meeting_days(child, subject, subj_node) or []
        except Exception:
            meeting = []
        try:
            day_idx = subject_day_index(meeting, weekday)
        except Exception:
            day_idx = None
        # Subject doesn't meet today — skip.
        if day_idx is None:
            continue
        # POSITION-based lookup — Monday→Day 1, Tuesday→Day 2 of this week.
        # Deliberately NOT the subject's _current_day cursor.
        try:
            text = resolve_week_text(subj_node, subj_week, day_pref=day_idx)
        except Exception:
            text = ""
        if not text:
            continue
        is_math = ("algebra" in subject.lower()) or ("math" in subject.lower())
        if is_math:
            pfx = f"{text} — "
            checklist = [
                f"{pfx}Assignment completed",
                f"{pfx}Given to checker",
                f"{pfx}Fixed missed problems",
                f"{pfx}Received brother's math",
                f"{pfx}Checked brother's math",
            ]
        else:
            checklist = [text]
        out.append({
            "subject": subject,
            "assignment_text": text,
            "is_math": is_math,
            "checklist": checklist,
            "from_curriculum": True,
        })
    return out


def _build_styles():
    """Reportlab paragraph styles used throughout the document."""
    base = getSampleStyleSheet()
    return {
        "date_header": ParagraphStyle(
            "DateHeader", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=18, leading=22,
            textColor=colors.HexColor("#5a3a1a"),
            spaceAfter=12, alignment=TA_LEFT,
        ),
        "child_header": ParagraphStyle(
            "ChildHeader", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=13, leading=16,
            spaceBefore=8, spaceAfter=4, alignment=TA_LEFT,
        ),
        "row": ParagraphStyle(
            "Row", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10, leading=13,
            leftIndent=0, spaceAfter=0, alignment=TA_LEFT,
        ),
        "empty": ParagraphStyle(
            "Empty", parent=base["BodyText"],
            fontName="Helvetica-Oblique", fontSize=10, leading=13,
            leftIndent=18, textColor=colors.HexColor("#888888"),
            spaceAfter=2, alignment=TA_LEFT,
        ),
    }


def _xml_escape(s: str) -> str:
    """Escape & < > so reportlab Paragraph parses the string as plain text.
    Lightweight inline helper to avoid an extra import."""
    if not s:
        return ""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))


class _Checkbox(Flowable):
    """Empty 10x10pt square drawn at the flowable's origin — a printable
    tick-box rendered to the left of each assignment row."""
    def __init__(self, size=10):
        super().__init__()
        self.size = size
        self.width = size
        self.height = size

    def draw(self):
        c = self.canv
        c.setLineWidth(0.7)
        c.setStrokeColor(colors.HexColor("#333333"))
        c.rect(0, 0, self.size, self.size, stroke=1, fill=0)


def _checklist_row(line_html: str, row_style) -> Table:
    """Build one assignment row: [empty checkbox] [paragraph], with 8pt
    bottom padding and a hairline divider below for scan-friendly
    visual separation between subjects."""
    para = Paragraph(line_html, row_style)
    tbl = Table(
        [[_Checkbox(10), para]],
        colWidths=[18, None],
    )
    tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (0, 0), 2),
        ("TOPPADDING",    (1, 0), (1, 0), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.3, colors.HexColor("#e8e8e8")),
    ]))
    return tbl


def generate_school_pdf(target_date_str: str = "") -> bytes:
    """
    Build a 15-page PDF of the week's school assignments — one page per
    (child, weekday) pair, ordered JP Mon..Fri, Joseph Mon..Fri,
    Michael Mon..Fri.  Returns the PDF bytes.

    target_date_str: optional 'YYYY-MM-DD'.  Any date in the desired week
    works — the function snaps back to Monday.  Default = today.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        title="McAdams School Week",
    )
    styles = _build_styles()

    # Pre-build child header styles (one per child, color from app palette).
    child_styles = {}
    for c in CHILDREN:
        col_hex = "#2980b9" if c == "JP" else (child_color(c, "bg") or "#1f2937")
        child_styles[c] = ParagraphStyle(
            f"Child_{c}", parent=styles["child_header"],
            textColor=colors.HexColor(col_hex),
        )

    try:
        curriculum = load_curriculum() or {}
    except Exception:
        curriculum = {}

    story = []
    week = _week_dates(target_date_str)
    total_pages = len(CHILDREN) * len(week)
    page_idx = 0
    for child in CHILDREN:
        child_cur = curriculum.get(child, {}) if isinstance(curriculum, dict) else {}
        for d, wname in week:
            date_label = d.strftime("%B %-d, %Y") if hasattr(d, "strftime") else str(d)
            header = f"{child} — {wname}, {date_label}"
            story.append(Paragraph(_xml_escape(header), child_styles[child]))

            blocks = _curriculum_blocks_for_day(child, wname, curriculum)
            rows = []
            for blk in blocks:
                subj = (blk.get("subject") or "").strip() if isinstance(blk, dict) else ""
                txt  = _assignment_text(blk)
                if not subj and not txt:
                    continue
                rows.append((subj, txt))

            if not rows:
                story.append(Paragraph("No assignments scheduled.", styles["empty"]))
            else:
                for subj, txt in rows:
                    subj_node = child_cur.get(subj, {}) if isinstance(child_cur, dict) else {}
                    meta_html = ""
                    if isinstance(subj_node, dict) and subj_node.get("_current_week") is not None:
                        wk_val = subj_node.get("_current_week")
                        dy_val = subj_node.get("_current_day")
                        meta_txt = f"Week {wk_val}"
                        if dy_val is not None:
                            meta_txt = f"{meta_txt} · Day {dy_val}"
                        meta_html = (
                            f' <font size="8" color="#888888">'
                            f'{_xml_escape(meta_txt)}</font>'
                        )
                    line = (
                        f'<font size="12"><b>{_xml_escape(subj)}</b></font>'
                        f"{meta_html}<br/>{_xml_escape(txt)}"
                    )
                    story.append(_checklist_row(line, styles["row"]))

            page_idx += 1
            if page_idx < total_pages:
                story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()
