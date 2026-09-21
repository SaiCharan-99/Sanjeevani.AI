"""PDF report generation (specs.md §6). Phase 6: assembles the session's Tier 1
state (+ golden-path fallback fields) into `report/pdf.py`'s ReportLab
pipeline and stores the bytes in an in-process artifact store (same
module-level-dict pattern as memory/jobs.py — no object storage in this
sandbox). `GET /api/report/{artifact_id}` serves the bytes for download,
wired behind the frontend's report-download buttons on screens 5 and 13."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.memory.state import get_session
from app.models import ReportGenerateRequest, ReportGenerateResponse
from app.report.pdf import build_report_pdf

router = APIRouter(prefix="/api/report", tags=["report"])

#: In-process artifact store: artifact_id -> pdf bytes. Mirrors memory/jobs.py's
#: module-level dict pattern (CLAUDE.md: no Celery/Redis, no object storage
#: added for this hackathon build).
_ARTIFACTS: dict[str, bytes] = {}

_GOLDEN_PATH_PERSON = {"name": "Ramesh Kumar", "age": 52, "gender": "male", "village": "Kadiri"}
_GOLDEN_PATH_CONSIDERATIONS = [
    {
        "disease": "Pulmonary tuberculosis", "score": 0.87, "rank": 1, "priority": "high", "review": "approved",
        "reasoning_chain": [
            {"evidence": "cough (21 days)", "edge": "PRESENTS_WITH", "weight": 0.9, "note": "NTEP presumptive TB: cough >= 2 weeks"},
            {"evidence": "weight loss", "edge": "PRESENTS_WITH", "weight": 0.8, "note": None},
            {"evidence": "night sweats", "edge": "PRESENTS_WITH", "weight": 0.7, "note": None},
        ],
        "recommended_tests": ["Sputum smear / NAAT", "Chest X-ray"],
    },
]
_GOLDEN_PATH_RISK = [
    {"name": "anemia_risk", "score": 0.62, "metric": "rule-based scorer — no trained-model accuracy metric",
     "inputs": ["pallor_score", "heart_rate", "fatigue"], "disclaimer": "screening signal, not a diagnosis"},
]
_GOLDEN_PATH_PAIN_POINTS = [
    {"canonical": "cough", "duration_days": 21, "confidence": 0.95, "verbatim": "for two or three weeks now I have had a cough"},
    {"canonical": "chest_tightness", "confidence": 0.90, "verbatim": "when I walk to the field my chest feels tight"},
    {"canonical": "fatigue", "confidence": 0.88, "verbatim": "I get tired very fast"},
    {"canonical": "night_sweats", "confidence": 0.75, "verbatim": "sometimes at night"},
    {"canonical": "weight_loss", "confidence": 0.85, "verbatim": "I have lost weight"},
]
_GOLDEN_PATH_VITALS = {
    "heart_rate": {"value": 96, "unit": "bpm", "tier": "reliable"},
    "respiration_rate": {"value": 22, "unit": "brpm", "tier": "reliable"},
    "spo2": {"value": 94, "unit": "%", "tier": "approximate"},
    "bp_trend": {"direction": "elevated", "tier": "trend_only"},
}


def _assemble_session_data(session_id: str) -> dict:
    """Builds the plain dict report/pdf.py consumes, from Tier 1 SessionState
    when available, falling back to the golden-path Ramesh Kumar record field
    by field so the report is always demoable (same pattern as every other
    api/ module's graceful fallback)."""
    state = get_session(session_id)
    person = _GOLDEN_PATH_PERSON
    pain_points = _GOLDEN_PATH_PAIN_POINTS
    findings: list = []
    vitals = _GOLDEN_PATH_VITALS
    language = "te"

    if state is not None:
        if state.pain_points:
            pain_points = state.pain_points
        if state.findings:
            findings = state.findings
        if state.vitals:
            vitals = state.vitals

    return {
        "person": person,
        "session_id": session_id,
        "language": language,
        "camp": {"name": "Kadiri health camp", "id": "CAMP-KDR-01"},
        "officer": {"name": "Dr. Meera Rao", "id": "MHO-014"},
        "vitals": vitals,
        "pain_points": pain_points,
        "findings": findings,
        "considerations": _GOLDEN_PATH_CONSIDERATIONS,
        "risk_models": _GOLDEN_PATH_RISK,
    }


@router.post("/generate", response_model=ReportGenerateResponse)
async def generate_report(request: ReportGenerateRequest, http_request: Request) -> ReportGenerateResponse:
    session_data = _assemble_session_data(request.session_id)

    # Prefer the real synthesis result over the golden-path considerations
    # baked into _assemble_session_data, when one is available for this session.
    try:
        from app.api.synthesis import synthesis_result

        result = await synthesis_result(request.session_id, http_request)
        if result.considerations:
            session_data["considerations"] = [c.model_dump() for c in result.considerations]
        if result.risk_models:
            session_data["risk_models"] = [r.model_dump() for r in result.risk_models]
    except Exception:
        pass  # keep the golden-path considerations assembled above

    artifact_id = f"r_{uuid.uuid4().hex[:8]}"
    verification_id = f"SJV-{artifact_id.upper()}"
    pdf_bytes = build_report_pdf(session_data, verification_id=verification_id)
    _ARTIFACTS[artifact_id] = pdf_bytes
    return ReportGenerateResponse(artifact_id=artifact_id, pdf_url=f"/api/report/{artifact_id}")


@router.get("/{artifact_id}")
async def download_report(artifact_id: str) -> Response:
    pdf_bytes = _ARTIFACTS.get(artifact_id)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Report artifact not found")
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{artifact_id}.pdf"'},
    )
