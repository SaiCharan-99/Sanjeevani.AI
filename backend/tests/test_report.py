"""Phase 6 — PDF report builder tests (report/pdf.py). Asserts valid PDF bytes
are produced and that the disclaimer / screening-signal strings specs.md §6
and CLAUDE.md require are actually present in the rendered document, plus
that a BP row never carries an mmHg value."""

from __future__ import annotations

from app.report.pdf import DISCLAIMER_TEXT, build_report_pdf


def _extract_text(pdf_bytes: bytes) -> str:
    """Real text extraction via PyPDF2 (already a project dependency), rather
    than a hand-rolled content-stream parser."""
    import io

    from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


SESSION_DATA = {
    "person": {"name": "Ramesh Kumar", "age": 52, "gender": "male", "village": "Kadiri"},
    "session_id": "s_test123",
    "language": "en",
    "camp": {"name": "Kadiri health camp", "id": "CAMP-KDR-01"},
    "officer": {"name": "Dr. Meera Rao", "id": "MHO-014"},
    "vitals": {
        "heart_rate": {"value": 96, "unit": "bpm", "tier": "reliable"},
        "bp_trend": {"direction": "elevated", "tier": "trend_only"},
    },
    "pain_points": [
        {"canonical": "cough", "duration_days": 21, "confidence": 0.95, "verbatim": "cough for weeks"},
    ],
    "findings": [],
    "considerations": [
        {
            "disease": "Pulmonary tuberculosis", "score": 0.87, "rank": 1, "priority": "high", "review": "approved",
            "reasoning_chain": [
                {"evidence": "cough (21 days)", "edge": "PRESENTS_WITH", "weight": 0.9,
                 "note": "NTEP presumptive TB: cough >= 2 weeks"},
            ],
            "recommended_tests": ["Sputum smear / NAAT"],
        },
    ],
    "risk_models": [
        {"name": "anemia_risk", "score": 0.62, "metric": "rule-based scorer — no trained-model accuracy metric",
         "inputs": ["pallor_score", "heart_rate", "fatigue"], "disclaimer": "screening signal, not a diagnosis"},
    ],
}


def test_build_report_pdf_produces_valid_pdf_bytes():
    pdf_bytes = build_report_pdf(SESSION_DATA, verification_id="SJV-TEST0001")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_report_contains_disclaimer_and_screening_signal_language():
    pdf_bytes = build_report_pdf(SESSION_DATA, verification_id="SJV-TEST0002")
    text = _extract_text(pdf_bytes)
    assert "screening signal" in text.lower()
    assert "not a diagnosis" in text.lower() or "not a substitute" in text.lower()


def test_report_bp_row_never_carries_an_mmhg_value():
    pdf_bytes = build_report_pdf(SESSION_DATA, verification_id="SJV-TEST0003")
    text = _extract_text(pdf_bytes).lower()
    assert "mmhg" not in text
    assert "trend" in text


def test_report_cites_the_ntep_screening_rule_in_the_reasoning_chain():
    pdf_bytes = build_report_pdf(SESSION_DATA, verification_id="SJV-TEST0004")
    text = _extract_text(pdf_bytes)
    assert "NTEP presumptive TB" in text


def test_disclaimer_text_constant_never_uses_diagnosis_language_as_a_verdict():
    assert "screening" in DISCLAIMER_TEXT.lower()
    assert "does not diagnose" in DISCLAIMER_TEXT.lower() or "not a diagnosis" in DISCLAIMER_TEXT.lower()
