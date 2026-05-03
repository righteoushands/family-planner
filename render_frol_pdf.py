"""
FROL printable PDF generator.

Builds a 7-page landscape Letter PDF — one weekday per page, with five
person columns (Mom, JP, Joseph, Michael, James) shown side-by-side so
Lauren can review the family's weekly rhythm for consistency.

Reads directly from data/day_templates/{Weekday}.json.

Public API:
    generate_frol_pdf() -> bytes
"""

from io import BytesIO
from datetime import datetime
from pathlib import Path
import json

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak,
)


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"]
PERSONS  = ["Mom", "JP", "Joseph", "Michael", "James"]
TEMPLATES_DIR = "data/day_templates"


def _to_minutes(time_str: str) -> int:
    """Convert '6:00 AM' / '12:30 PM' to minutes-since-midnight for sorting.
    Returns a large sentinel on parse failure so unparseable rows sink
    to the bottom rather than crashing the build."""
    try:
        dt = datetime.strptime((time_str or "").strip(), "%I:%M %p")
        return dt.hour * 60 + dt.minute
    except Exception:
        return 99999


def _load_day_grid(weekday: str) -> dict:
    """Read data/day_templates/{Weekday}.json and return {person: {time: label}}.

    Mom column is the union of any 'Lauren' and 'Mom' keys (Mom wins on
    same-time conflict) — matches data_helpers.get_frol_day_slots semantics
    so the PDF shows the same rhythm Lauren sees in the app.
    """
    p = Path(f"{TEMPLATES_DIR}/{weekday}.json")
    if not p.exists():
        return {n: {} for n in PERSONS}
    try:
        grid = json.loads(p.read_text(encoding="utf-8")).get("grid", {}) or {}
    except Exception:
        return {n: {} for n in PERSONS}
    out = {}
    mom = dict(grid.get("Lauren", {}) or {})
    mom.update(grid.get("Mom", {}) or {})
    out["Mom"] = mom
    for n in ("JP", "Joseph", "Michael", "James"):
        out[n] = dict(grid.get(n, {}) or {})
    return out


def _all_times(grid: dict) -> list:
    """Chronologically-sorted union of every time key across all persons."""
    seen = set()
    for person_grid in grid.values():
        for t in person_grid.keys():
            if t:
                seen.add(t)
    return sorted(seen, key=_to_minutes)


def _xml_escape(s: str) -> str:
    """Minimal escaping for ReportLab Paragraph (which parses a tiny HTML
    subset). Order matters — & first."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_frol_pdf() -> bytes:
    """Build the 7-page weekly FROL PDF. Returns raw PDF bytes."""
    buf = BytesIO()
    page_w, _page_h = landscape(letter)  # 792 x 612 points

    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(letter),
        leftMargin=0.35 * inch,
        rightMargin=0.35 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.35 * inch,
        title="McAdams Family Rule of Life",
        author="Sancta Familia",
    )

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(
        "frol_cell", parent=styles["BodyText"],
        fontName="Helvetica", fontSize=7, leading=8.5,
        textColor=colors.HexColor("#222222"),
    )
    time_style = ParagraphStyle(
        "frol_time", parent=cell_style,
        fontName="Helvetica-Bold", fontSize=7.5, alignment=1,
    )
    header_style = ParagraphStyle(
        "frol_header", parent=styles["BodyText"],
        fontName="Helvetica-Bold", fontSize=9, alignment=1,
        textColor=colors.white, leading=10,
    )
    title_style = ParagraphStyle(
        "frol_title", parent=styles["Heading1"],
        fontName="Helvetica-Bold", fontSize=18, alignment=1,
        spaceAfter=8, textColor=colors.HexColor("#5a3a1a"),
    )

    # Column widths: Time = 60pt; the five person columns share the rest evenly.
    usable   = page_w - 0.70 * inch
    time_w   = 60.0
    person_w = (usable - time_w) / 5.0
    col_widths = [time_w] + [person_w] * 5

    flow = []
    for idx, weekday in enumerate(WEEKDAYS):
        grid  = _load_day_grid(weekday)
        times = _all_times(grid)

        flow.append(Paragraph(weekday, title_style))

        header_row = [Paragraph("Time", header_style)] + [
            Paragraph(p, header_style) for p in PERSONS
        ]
        rows = [header_row]

        for t in times:
            row = [Paragraph(_xml_escape(t), time_style)]
            for p_name in PERSONS:
                label = (grid.get(p_name, {}).get(t, "") or "").strip()
                row.append(Paragraph(_xml_escape(label), cell_style))
            rows.append(row)

        if not times:
            empty_msg = Paragraph(
                "No schedule entered for this day.", cell_style
            )
            rows.append([Paragraph("", cell_style), empty_msg,
                         Paragraph("", cell_style), Paragraph("", cell_style),
                         Paragraph("", cell_style), Paragraph("", cell_style)])

        tbl = Table(rows, colWidths=col_widths, repeatRows=1)
        tstyle = TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#5a3a1a")),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING",   (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ])
        # Alternating row shading (data rows only — skip the header at row 0)
        for r in range(1, len(rows)):
            if r % 2 == 0:
                tstyle.add("BACKGROUND", (0, r), (-1, r),
                           colors.HexColor("#faf6ee"))
        tbl.setStyle(tstyle)
        flow.append(tbl)

        if idx < len(WEEKDAYS) - 1:
            flow.append(PageBreak())

    doc.build(flow)
    return buf.getvalue()
