"""PDF rendering for KFL Drone Risk Assessment and Mission Sheet.

Generates PDFs matching the exact layout of the KFL source documents:
- KFL_Drone_Risk_Assessment.pdf (2-page hazard assessment + risk matrix + sign-off)
- KFL_Drone_Mission_Sheet.pdf (1-page flight log + sign-off)

Uses reportlab for precise layout control matching the source documents.
"""

import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=ss["Title"], fontSize=14, spaceAfter=6,
            alignment=0, textColor=colors.HexColor("#1a1a1a"),
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=ss["Normal"], fontSize=9, spaceAfter=2,
            textColor=colors.HexColor("#4a4a4a"),
        ),
        "section": ParagraphStyle(
            "section", parent=ss["Heading3"], fontSize=10, spaceBefore=8,
            spaceAfter=4, textColor=colors.HexColor("#1a1a1a"),
        ),
        "field": ParagraphStyle(
            "field", parent=ss["Normal"], fontSize=9, leading=12,
        ),
        "small": ParagraphStyle(
            "small", parent=ss["Normal"], fontSize=8, leading=10,
            textColor=colors.HexColor("#4a4a4a"),
        ),
        "cell": ParagraphStyle(
            "cell", parent=ss["Normal"], fontSize=8, leading=10,
        ),
        "cellBold": ParagraphStyle(
            "cellBold", parent=ss["Normal"], fontSize=8, leading=10,
            fontName="Helvetica-Bold",
        ),
        "signoff": ParagraphStyle(
            "signoff", parent=ss["Normal"], fontSize=9, leading=12,
        ),
    }


def _field_row(styles, label, value):
    """Two-column field row: Label | Value."""
    return Table(
        [[Paragraph(f"<b>{label}</b>", styles["field"]), Paragraph(str(value or "—"), styles["field"])]],
        colWidths=[1.3 * inch, 5.2 * inch],
    )


def _header_block(styles, title, subtitle, fields):
    """Build the document header block with title and field rows."""
    flowables = []
    flowables.append(Paragraph(title, styles["title"]))
    flowables.append(Paragraph(subtitle, styles["subtitle"]))
    flowables.append(Spacer(1, 6))
    flowables.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a1a1a")))
    flowables.append(Spacer(1, 8))
    for label, value in fields:
        flowables.append(_field_row(styles, label, value))
        flowables.append(Spacer(1, 3))
    return flowables


def _hazards_table(styles, hazards):
    """Build the hazards assessment table matching the source PDF."""
    header = [
        Paragraph("<b>Hazard</b>", styles["cellBold"]),
        Paragraph("<b>Risk</b>", styles["cellBold"]),
        Paragraph("<b>Mitigation in place</b>", styles["cellBold"]),
        Paragraph("<b>Score after mitigation</b>", styles["cellBold"]),
    ]
    data = [header]
    for h in hazards:
        data.append([
            Paragraph(h.get("hazard", ""), styles["cell"]),
            Paragraph(h.get("risk", ""), styles["cell"]),
            Paragraph(h.get("mitigation", ""), styles["cell"]),
            Paragraph(h.get("score", ""), styles["cell"]),
        ])

    t = Table(data, colWidths=[1.5 * inch, 1.8 * inch, 2.2 * inch, 1.5 * inch], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#888888")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _risk_matrix(styles):
    """Build the 5x5 risk matrix table."""
    severity = ["1 Negligible", "2 Minor", "3 Moderate", "4 Major", "5 Catastrophic"]
    likelihood = ["1 Rare", "2 Unlikely", "3 Possible", "4 Likely", "5 Almost certain"]

    data = [[Paragraph("<b>Severity \\ Likelihood</b>", styles["cellBold"])] + [
        Paragraph(f"<b>{s}</b>", styles["cellBold"]) for s in severity
    ]]

    matrix = [
        [5, 10, 15, 20, 25],   # 5 Almost certain
        [4, 8, 12, 16, 20],    # 4 Likely
        [3, 6, 9, 12, 15],     # 3 Possible
        [2, 4, 6, 8, 10],      # 2 Unlikely
        [1, 2, 3, 4, 5],       # 1 Rare
    ]

    for i, row in enumerate(matrix):
        row_data = [Paragraph(f"<b>{likelihood[i]}</b>", styles["cellBold"])]
        for val in row:
            level = "Low" if val <= 4 else ("Medium" if val <= 9 else "High")
            row_data.append(Paragraph(f"{val}<br/>{level}", styles["cell"]))
        data.append(row_data)

    t = Table(data, colWidths=[1.2 * inch] + [0.95 * inch] * 5)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8e8e8")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#888888")),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def _signoff_block(styles, fields):
    """Build the sign-off block with signature lines."""
    flowables = []
    flowables.append(Spacer(1, 10))
    flowables.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a1a1a")))
    flowables.append(Spacer(1, 6))
    flowables.append(Paragraph("Sign-off", styles["section"]))
    for label, value in fields:
        flowables.append(_field_row(styles, label, value))
        flowables.append(Spacer(1, 5))
    return flowables


def render_risk_assessment_pdf(data: dict) -> bytes:
    """Render a KFL Drone Risk Assessment PDF matching the source document.

    Expected data keys:
      - location, date, project_type, drone_type, pic (header fields)
      - hazards: list of {hazard, risk, mitigation, score}
      - overall_risk_score, overall_risk_level, flight_decision, conditions
      - filed_by, approved_by, date_filed, head_signature, approval_date
    """
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title="Drone Operations Risk Assessment",
        author="KENYA FLYING LABS | FLIGHT SAFETY",
    )

    flowables = []

    # Page 1 header + hazards
    flowables.extend(_header_block(
        styles,
        "Drone Operations Risk Assessment",
        "KENYA FLYING LABS | FLIGHT SAFETY",
        [
            ("Location / coordinates", data.get("location", "")),
            ("Date", data.get("date", "")),
            ("Project type", data.get("project_type", "")),
            ("Drone type / model", data.get("drone_type", "")),
            ("Pilot in Command (PIC)", data.get("pic", "")),
        ],
    ))
    flowables.append(Spacer(1, 8))
    flowables.append(Paragraph("Hazards and Mitigations", styles["section"]))
    flowables.append(Paragraph(
        "Tick hazards present and verify the listed controls before flight. "
        "Scores assume the controls are in place. Reassess if site conditions warrant a different score.",
        styles["small"],
    ))
    flowables.append(Spacer(1, 4))
    flowables.append(_hazards_table(styles, data.get("hazards", [])))
    flowables.append(Spacer(1, 6))
    flowables.append(Paragraph(
        f"<b>L × S scoring:</b> {data.get('scoring_note', '')}",
        styles["small"],
    ))

    # Page break for risk matrix
    from reportlab.platypus import PageBreak
    flowables.append(PageBreak())

    # Page 2: Risk matrix + flight decision + sign-off
    flowables.append(Paragraph("Risk Matrix and Approval", styles["section"]))
    flowables.append(Paragraph(
        "Rate likelihood and severity after mitigation. Multiply the two ratings to get the score. "
        "Use the highest remaining hazard rating as the overall risk level.",
        styles["small"],
    ))
    flowables.append(Spacer(1, 6))
    flowables.append(_risk_matrix(styles))
    flowables.append(Spacer(1, 8))

    # Risk level legend
    flowables.append(Paragraph(
        "<b>Low (1–4)</b>: Proceed once controls are verified and approval is recorded.&nbsp;&nbsp;"
        "<b>Medium (5–9)</b>: Confirm controls and obtain Head of Safety approval before flight.&nbsp;&nbsp;"
        "<b>High (10–25)</b>: Hold the flight. Reduce the risk and reassess before approval.",
        styles["small"],
    ))
    flowables.append(Spacer(1, 8))

    # Flight Decision
    flowables.append(Paragraph("Flight Decision", styles["section"]))
    flowables.append(_field_row(styles, "Overall residual risk (score and level)",
                                f"{data.get('overall_risk_score', '—')} — {data.get('overall_risk_level', '—')}"))
    flowables.append(Spacer(1, 3))
    flowables.append(_field_row(styles, "Proceed / Hold", data.get("flight_decision", "")))
    flowables.append(Spacer(1, 3))
    flowables.append(_field_row(styles, "Additional conditions or notes", data.get("conditions", "")))
    flowables.append(Spacer(1, 4))
    flowables.append(Paragraph(
        "Reassess if weather, airspace, site conditions or the scope of the flight changes.",
        styles["small"],
    ))
    flowables.append(Spacer(1, 8))

    # Sign-off
    flowables.extend(_signoff_block(
        styles,
        [
            ("Filed by PIC (full name)", data.get("filed_by", "")),
            ("PIC full name", data.get("pic_full_name", "")),
            ("Date filed", data.get("date_filed", "")),
            ("Approved by Head of Safety", data.get("approved_by", "")),
            ("Head of Safety signature", data.get("head_signature", "")),
            ("Approval date", data.get("approval_date", "")),
        ],
    ))

    doc.build(flowables)
    buf.seek(0)
    return buf.read()


def render_mission_sheet_pdf(data: dict) -> bytes:
    """Render a KFL Drone Mission Sheet PDF matching the source document.

    Expected data keys:
      - location, date, pic_name, operation_type, kcaa_oa, drone_type (header fields)
      - flights: list of {flight_no, start, end, total_run, battery, charge_cycles}
      - filed_by, pic_full_name, date_filed
    """
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title="Drone Mission Sheet",
        author="KENYA FLYING LABS | FLIGHT SAFETY",
    )

    flowables = []

    # Header
    flowables.extend(_header_block(
        styles,
        "Drone Mission Sheet",
        "KENYA FLYING LABS | FLIGHT SAFETY",
        [
            ("Location", data.get("location", "")),
            ("Date", data.get("date", "")),
            ("Pilot in Command (PIC) name", data.get("pic_name", "")),
            ("Type of operation", data.get("operation_type", "")),
            ("KCAA OA reference number", data.get("kcaa_oa", "")),
            ("Drone type / model", data.get("drone_type", "")),
        ],
    ))
    flowables.append(Spacer(1, 8))

    # Flight Log
    flowables.append(Paragraph("Flight Log", styles["section"]))
    flowables.append(Paragraph(
        "Record start and end times in 24-hour local time (HH:MM).",
        styles["small"],
    ))
    flowables.append(Spacer(1, 4))

    header = [
        Paragraph("<b>Flight no.</b>", styles["cellBold"]),
        Paragraph("<b>Start (HH:MM)</b>", styles["cellBold"]),
        Paragraph("<b>End (HH:MM)</b>", styles["cellBold"]),
        Paragraph("<b>Total run (HH:MM)</b>", styles["cellBold"]),
        Paragraph("<b>Battery number</b>", styles["cellBold"]),
        Paragraph("<b>Charge cycles</b>", styles["cellBold"]),
    ]
    fl_data = [header]
    for i in range(11):
        f = data.get("flights", [{}])[i] if i < len(data.get("flights", [])) else {}
        fl_data.append([
            Paragraph(str(i + 1), styles["cell"]),
            Paragraph(str(f.get("start", "")), styles["cell"]),
            Paragraph(str(f.get("end", "")), styles["cell"]),
            Paragraph(str(f.get("total_run", "")), styles["cell"]),
            Paragraph(str(f.get("battery", "")), styles["cell"]),
            Paragraph(str(f.get("charge_cycles", "")), styles["cell"]),
        ])

    t = Table(fl_data, colWidths=[0.8 * inch, 1.1 * inch, 1.0 * inch, 1.2 * inch, 1.1 * inch, 1.0 * inch], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#888888")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    flowables.append(t)
    flowables.append(Spacer(1, 12))

    # Sign-off
    flowables.extend(_signoff_block(
        styles,
        [
            ("Filed by PIC", data.get("filed_by", "")),
            ("PIC full name", data.get("pic_full_name", "")),
            ("Signature", ""),
            ("Date filed", data.get("date_filed", "")),
        ],
    ))

    doc.build(flowables)
    buf.seek(0)
    return buf.read()
