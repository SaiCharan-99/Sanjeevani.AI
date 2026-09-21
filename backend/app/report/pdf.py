"""ReportLab PDF builder (specs.md §6). Structure, in order: header, person
block, vitals table (BP row shows trend only — never mmHg, rule 2; no
composite score, rule 9), consultation summary, second-look findings with
limitations, ranked considerations with reasoning chains, risk model outputs
with metrics, recommendations with priority, disclaimer block, footer (page
numbers, timestamp, verification ID, stamp placeholder).

Trilingual per specs.md §6: the person-facing summary section renders in the
session language when a translated string is available (a small dict here —
not machine-translating the whole document, which would be inventing
clinical-adjacent copy); the clinical body stays in English throughout.

Pure builder: session data in (a plain dict assembled by the caller), PDF
bytes out. No I/O beyond writing to the in-memory buffer it returns.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_STYLES = getSampleStyleSheet()
_H1 = ParagraphStyle("H1", parent=_STYLES["Heading1"], fontSize=16, spaceAfter=6)
_H2 = ParagraphStyle("H2", parent=_STYLES["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
_BODY = ParagraphStyle("Body", parent=_STYLES["BodyText"], fontSize=9.5, leading=13)
_SMALL = ParagraphStyle("Small", parent=_STYLES["BodyText"], fontSize=8, textColor=colors.grey)
_DISCLAIMER = ParagraphStyle("Disclaimer", parent=_STYLES["BodyText"], fontSize=9, textColor=colors.HexColor("#7a5a00"))

#: Screening-aid person-facing phrase, translated for the trilingual
#: person-facing summary line (specs.md §6). Clinical body stays English.
_PERSON_FACING_HEADLINE = {
    "en": "This is a screening summary, not a diagnosis. A doctor should review these results.",
    "te": "ఇది స్క్రీనింగ్ సారాంశం, రోగనిర్ధారణ కాదు. ఈ ఫలితాలను వైద్యుడు సమీక్షించాలి.",
    "hi": "यह एक स्क्रीनिंग सारांश है, निदान नहीं। इन परिणामों की समीक्षा डॉक्टर द्वारा की जानी चाहिए।",
}

DISCLAIMER_TEXT = (
    "Sanjeevani is a screening and documentation aid for a trained medical officer. "
    "It does not diagnose. Every consideration above is a screening signal, to be "
    "confirmed by laboratory testing and the officer's own clinical judgement before "
    "any treatment decision is made. Vitals outside their confidence tier are labelled, "
    "not hidden; curated knowledge-base entries not yet reviewed by a clinician are "
    "marked 'Needs clinical review'."
)


def _footer(canvas, doc, verification_id: str) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    canvas.drawString(18 * mm, 12 * mm, f"Generated {ts}  ·  Verification ID {verification_id}")
    canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Page {doc.page}")
    canvas.setFont("Helvetica-Oblique", 7)
    canvas.drawCentredString(A4[0] / 2, 8 * mm, "Sanjeevani screening record — not a substitute for clinical diagnosis")
    canvas.restoreState()


def _table(rows: list[list[str]], col_widths: list[float] | None = None) -> Table:
    t = Table(rows, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9f1ee")),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def build_report_pdf(session_data: dict[str, Any], *, verification_id: str) -> bytes:
    """`session_data` shape (assembled by api/report.py):
    {person: {...}, session_id, language, camp: {...}, officer: {...},
     vitals: {...}, transcript_summary: str, pain_points: [...],
     findings: [...], considerations: [...], risk_models: [...]}
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
    )
    story: list[Any] = []

    person = session_data.get("person", {})
    language = session_data.get("language", "en")
    camp = session_data.get("camp", {"name": "Sanjeevani health camp", "id": "N/A"})
    officer = session_data.get("officer", {"name": "Medical Health Officer", "id": "N/A"})

    # 1. Header
    story.append(Paragraph("Sanjeevani Screening Report", _H1))
    story.append(
        Paragraph(
            f"Programme: {camp.get('name')}  ·  Camp ID: {camp.get('id')}  ·  "
            f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  ·  "
            f"Officer: {officer.get('name')} ({officer.get('id')})",
            _SMALL,
        )
    )
    story.append(Spacer(1, 6))
    story.append(Paragraph(_PERSON_FACING_HEADLINE.get(language, _PERSON_FACING_HEADLINE["en"]), _DISCLAIMER))
    story.append(Spacer(1, 6))

    # 2. Person block
    story.append(Paragraph("Person", _H2))
    story.append(
        _table(
            [
                ["Name", "Age", "Gender", "Village", "Session ID"],
                [
                    person.get("name", "—"), str(person.get("age", "—")), person.get("gender", "—"),
                    person.get("village", "—"), session_data.get("session_id", "—"),
                ],
            ]
        )
    )

    # 3. Vitals table — confidence tier per row; BP row shows trend only, no mmHg
    story.append(Paragraph("Vitals", _H2))
    vitals = session_data.get("vitals", {})
    vital_rows = [["Vital", "Value", "Status", "Confidence tier"]]
    hr = vitals.get("heart_rate")
    if hr:
        vital_rows.append(["Heart rate", f"{hr.get('value')} {hr.get('unit', 'bpm')}", "—", hr.get("tier", "—")])
    rr = vitals.get("respiration_rate")
    if rr:
        vital_rows.append(["Respiration rate", f"{rr.get('value')} {rr.get('unit', 'brpm')}", "—", rr.get("tier", "—")])
    spo2 = vitals.get("spo2")
    if spo2:
        vital_rows.append(["SpO2", f"{spo2.get('value')} {spo2.get('unit', '%')}", "Approximate", spo2.get("tier", "—")])
    bp = vitals.get("bp_trend")
    if bp:
        vital_rows.append(["Blood pressure", f"Trending {bp.get('direction', '—')}", "Trend only — not a measurement", bp.get("tier", "trend_only")])
    if len(vital_rows) > 1:
        story.append(_table(vital_rows))
    else:
        story.append(Paragraph("No vitals captured this session.", _BODY))

    # 4. Consultation summary
    story.append(Paragraph("Consultation summary", _H2))
    pain_points = session_data.get("pain_points", [])
    if pain_points:
        rows = [["Symptom", "Duration", "Confidence", "Verbatim"]]
        for p in pain_points:
            dur = f"{p.get('duration_days')} days" if p.get("duration_days") is not None else "—"
            rows.append(
                [
                    (p.get("canonical") or p.get("unmapped_text") or p.get("symptom", "—")).replace("_", " "),
                    dur, f"{int(float(p.get('confidence', 0)) * 100)}%", p.get("verbatim", "—"),
                ]
            )
        story.append(_table(rows, col_widths=[90, 55, 55, 200]))
    else:
        story.append(Paragraph("No reported symptoms recorded.", _BODY))

    # 5. Second-look findings with limitations
    story.append(Paragraph("Second-look findings", _H2))
    findings = session_data.get("findings", [])
    if findings:
        rows = [["Feature", "Value", "Method", "Interpretation", "Limitations"]]
        for f in findings:
            rows.append(
                [
                    f.get("feature", "—").replace("_", " "), f"{f.get('value')} {f.get('unit', '')}",
                    f.get("method", "—"), f.get("interpretation", "—"), f.get("limitations", "—"),
                ]
            )
        story.append(_table(rows, col_widths=[75, 55, 90, 110, 70]))
    else:
        story.append(Paragraph("No guided capture performed this session.", _BODY))

    # 6. Assessment — ranked considerations with reasoning chains
    story.append(Paragraph("Assessment — ranked considerations", _H2))
    considerations = session_data.get("considerations", [])
    for c in considerations:
        review_badge = "" if c.get("review") == "approved" else "  [Needs clinical review]"
        story.append(
            Paragraph(
                f"<b>{c.get('rank')}. {c.get('disease')}</b> — score {c.get('score')}, "
                f"priority {c.get('priority', '—').upper()}{review_badge}",
                _BODY,
            )
        )
        for step in c.get("reasoning_chain", []):
            note = f" — {step.get('note')}" if step.get("note") else ""
            story.append(
                Paragraph(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;• {step.get('evidence')} → {step.get('edge')} "
                    f"(weight {step.get('weight')}){note}",
                    _SMALL,
                )
            )
        tests = c.get("recommended_tests", [])
        if tests:
            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Recommended: {', '.join(tests)}", _SMALL))
        story.append(Spacer(1, 4))
    if not considerations:
        story.append(Paragraph("No considerations generated — see the officer's own assessment.", _BODY))

    # 7. Risk model outputs with metrics
    story.append(Paragraph("Background risk checks", _H2))
    risk_models = session_data.get("risk_models", [])
    if risk_models:
        rows = [["Model", "Score", "Metric", "Inputs"]]
        for r in risk_models:
            rows.append(
                [
                    r.get("name", "—").replace("_", " "), str(r.get("score", "—")),
                    r.get("metric") or (f"F1 {r.get('f1')}" if r.get("f1") is not None else "—"),
                    ", ".join(r.get("inputs", [])),
                ]
            )
        story.append(_table(rows, col_widths=[85, 45, 190, 90]))
        story.append(Paragraph(risk_models[0].get("disclaimer", "screening signal, not a diagnosis"), _SMALL))
    else:
        story.append(Paragraph("No risk model outputs available this session.", _BODY))

    # 8. Recommendations — tests, referral priority, precautions
    story.append(Paragraph("Recommendations", _H2))
    if considerations:
        top = considerations[0]
        story.append(
            Paragraph(
                f"Priority: <b>{top.get('priority', '—').upper()}</b>. Tests: "
                f"{', '.join(top.get('recommended_tests', [])) or '—'}. Precautions: as per KB (see officer copy).",
                _BODY,
            )
        )
    else:
        story.append(Paragraph("No recommendation generated.", _BODY))

    # 9. Disclaimer block
    story.append(Spacer(1, 8))
    story.append(Paragraph("Disclaimer", _H2))
    story.append(Paragraph(DISCLAIMER_TEXT, _DISCLAIMER))

    doc.build(
        story,
        onFirstPage=lambda c, d: _footer(c, d, verification_id),
        onLaterPages=lambda c, d: _footer(c, d, verification_id),
    )
    return buf.getvalue()
