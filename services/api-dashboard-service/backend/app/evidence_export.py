"""
evidence_export.py — PDF evidence packet generator for api-dashboard-service.

Builds a polished PDF from a change event's evidence fields using ReportLab.
Called after x402 payment is verified.
"""

from __future__ import annotations

import io
import textwrap
from datetime import datetime
from typing import Dict, Any

try:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        HRFlowable,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def generate_evidence_pdf(event: Dict[str, Any]) -> bytes:
    """
    Generates a PDF evidence packet from a change event dict.

    Returns raw bytes of the PDF.
    Raises RuntimeError if reportlab is not installed.
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError(
            "reportlab is not installed. Run: pip install reportlab"
        )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=18,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#16213e"),
        spaceBefore=14,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#333333"),
    )
    clause_style = ParagraphStyle(
        "Clause",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#555555"),
        leftIndent=16,
        borderPad=6,
    )

    CHANGE_TYPE_COLORS = {
        "TIGHTENING": colors.HexColor("#dc2626"),
        "LOOSENING": colors.HexColor("#16a34a"),
        "SCOPE_CHANGE": colors.HexColor("#d97706"),
        "STYLISTIC": colors.HexColor("#6b7280"),
    }
    change_color = CHANGE_TYPE_COLORS.get(
        event.get("change_type", ""), colors.HexColor("#1e40af")
    )

    story = []

    # Header
    story.append(Paragraph("PolicyDiff — Evidence Brief", title_style))
    story.append(Paragraph(
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        body_style,
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1e40af")))
    story.append(Spacer(1, 0.15 * inch))

    # Key details table
    change_type_badge = f'<font color="{change_color.hexval() if hasattr(change_color, "hexval") else "#dc2626"}"><b>{event.get("change_type", "N/A")}</b></font>'
    detail_data = [
        ["Payer", event.get("payer", "")],
        ["Policy", event.get("policy_title", "")],
        ["Service Line", event.get("service_line", "")],
        ["Change Type", event.get("change_type", "")],
        ["Confidence", f"{event.get('confidence', 0) * 100:.0f}%"],
        ["Revenue at Risk", f"${event.get('revenue_at_risk_usd', 0):,.0f}"],
    ]
    detail_table = Table(detail_data, colWidths=[2 * inch, 5.5 * inch])
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1e40af")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 0.2 * inch))

    # Change summary
    story.append(Paragraph("Change Summary", heading_style))
    story.append(Paragraph(event.get("change_summary", "N/A"), body_style))

    # Changed clause
    story.append(Paragraph("Changed Clause", heading_style))
    story.append(Paragraph(
        f'<i>"{event.get("changed_clause", "N/A")}"</i>', clause_style
    ))

    # Clinical impact
    story.append(Paragraph("Clinical Impact", heading_style))
    story.append(Paragraph(event.get("clinical_impact", "N/A"), body_style))

    # CPT codes
    story.append(Paragraph("Affected CPT Codes", heading_style))
    cpt_codes = event.get("cpt_codes_affected", [])
    story.append(Paragraph(", ".join(cpt_codes) if cpt_codes else "None identified", body_style))

    # Recommended action
    story.append(Paragraph("Recommended Action", heading_style))
    story.append(Paragraph(event.get("recommended_action", "N/A"), body_style))

    # Senso link
    if event.get("cited_md_url"):
        story.append(Paragraph("Senso Evidence Brief", heading_style))
        story.append(Paragraph(
            f'<link href="{event["cited_md_url"]}">{event["cited_md_url"]}</link>',
            body_style,
        ))

    # Markdown evidence
    if event.get("cited_markdown"):
        story.append(Paragraph("Full Evidence Markdown", heading_style))
        wrapped = textwrap.shorten(event["cited_markdown"], width=2000, placeholder="...")
        story.append(Paragraph(wrapped.replace("\n", "<br/>"), body_style))

    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#d1d5db")))
    story.append(Paragraph(
        "This document was generated by PolicyDiff — payer policy change intelligence for denial prevention.",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor=colors.gray),
    ))

    doc.build(story)
    return buf.getvalue()
