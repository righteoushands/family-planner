"""
School Week printable PDF generator.

Builds a 5-page portrait Letter PDF — one weekday Mon-Fri per page —
showing JP, Joseph, and Michael's school assignments side-by-side so
Lauren can plan and track the week at a glance.

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
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
)
from reportlab.lib.enums import TA_LEFT

from config import child_color
from daily_schedule_engine import extract_school_tasks_for_child


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
    """Return the Monday on or before d (date.weekday(): Mon=0 .. Sun=6)."""
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
    abort the whole PDF build."""
    try:
        out = extract_school_tasks_for_child(child, weekday) or []
        return out if isinstance(out, list) else []
    except Exception:
        return []


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
            leftIndent=14, spaceAfter=2, alignment=TA_LEFT,
        ),
        "empty": ParagraphStyle(
            "Empty", parent=base["BodyText"],
            fontName="Helvetica-Oblique", fontSize=10, leading=13,
            leftIndent=14, textColor=colors.HexColor("#888888"),
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


def generate_school_pdf(target_date_str: str = "") -> bytes:
    """
    Build a 5-page PDF of the week's school assignments for JP, Joseph,
    Michael (Mon-Fri).  Returns the PDF bytes.

    target_date_str: optional 'YYYY-MM-DD'.  Any date in the desired week
    works — the function snaps back to Monday.  Default = today.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title="McAdams School Week",
    )
    styles = _build_styles()

    # Pre-build child header styles (one per child, color from app palette).
    child_styles = {}
    for c in CHILDREN:
        col_hex = child_color(c, "bg") or "#1f2937"
        child_styles[c] = ParagraphStyle(
            f"Child_{c}", parent=styles["child_header"],
            textColor=colors.HexColor(col_hex),
        )

    story = []
    week = _week_dates(target_date_str)
    for idx, (d, wname) in enumerate(week):
        date_label = d.strftime("%B %-d, %Y") if hasattr(d, "strftime") else str(d)
        header = f"{wname} — {date_label}"
        story.append(Paragraph(_xml_escape(header), styles["date_header"]))

        for child in CHILDREN:
            story.append(Paragraph(_xml_escape(child), child_styles[child]))
            blocks = _child_blocks_safe(child, wname)
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
                    line = f"<b>{_xml_escape(subj)}:</b> {_xml_escape(txt)}"
                    story.append(Paragraph(line, styles["row"]))

            story.append(Spacer(1, 4))

        if idx != len(week) - 1:
            story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()
