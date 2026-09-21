"""Second-look trigger engine + capture ingest (Phase 5, architecture.md §8,
specs.md §5). `/suggest` reads the session's reported pain points (Tier 1
`SessionState`, written by `/api/consult/extract` and `/painpoints`) and runs
them through the deterministic trigger table. `/submit` runs the requested
feature's pure signal-processing function over the posted landmark series,
cross-checks respiration against the rPPG-derived RR already in Tier 1, and
best-effort writes the resulting `:PHI:Finding` + `:INDICATES` edges — the
same graceful-fallback pattern as every other api/ module.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.agents.secondlook_features import FEATURE_PROCESSORS, cross_check_rr
from app.agents.triggers import propose_features
from app.memory import persistence
from app.memory.state import get_or_create_session
from app.models import (
    Finding,
    SecondLookSubmitRequest,
    SecondLookSubmitResponse,
    SecondLookSuggestResponse,
    SecondLookSuggestion,
)
from app.providers import cache

router = APIRouter(prefix="/api/secondlook", tags=["secondlook"])


def _session_canonical_symptoms(session_id: str) -> list[str]:
    """The canonical slugs reported this session (Task 9: screen 8 -> 10
    wiring). Falls back to the golden-path pain points when nothing has been
    extracted yet in this process (e.g. screen 10 opened standalone) — same
    fallback spirit as the rest of the app."""
    state = get_or_create_session(session_id)
    slugs = [p.get("canonical") for p in state.pain_points if p.get("canonical")]
    if slugs:
        return slugs
    return [p.get("canonical") for p in cache.golden_extract().get("pain_points", []) if p.get("canonical")]


@router.get("/suggest", response_model=SecondLookSuggestResponse)
async def suggest(session_id: str) -> SecondLookSuggestResponse:
    symptoms = _session_canonical_symptoms(session_id)
    proposals = propose_features(symptoms)
    return SecondLookSuggestResponse(
        suggestions=[SecondLookSuggestion(**p) for p in proposals]
    )


async def _write_findings(request: Request, session_id: str, findings: list[dict]) -> None:
    client = getattr(request.app.state, "graph_client", None)
    if client is None:
        return
    try:
        await persistence.write_findings(client, session_id=session_id, findings=findings)
    except Exception:
        pass  # graceful no-op — Tier 1 SessionState.findings still holds them


@router.post("/submit", response_model=SecondLookSubmitResponse)
async def submit(request: SecondLookSubmitRequest, req: Request) -> SecondLookSubmitResponse:
    processor = FEATURE_PROCESSORS.get(request.feature)
    if processor is None:
        # Unknown feature id — most conservative response, never fabricated.
        finding = {
            "feature": request.feature,
            "value": 0.0,
            "unit": "",
            "method": "No processing pipeline is defined for this feature.",
            "interpretation": "Unable to process this capture.",
            "confidence": 0.0,
            "limitations": "Feature id not recognised by the second-look pipeline.",
        }
    elif request.feature == "chest_rise_respiration":
        state = get_or_create_session(request.session_id)
        rr = state.vitals.get("respiration_rate") or {}
        finding = processor(
            request.landmark_series,
            rppg_rr_bpm=rr.get("value"),
            rppg_rr_quality=rr.get("quality"),
        )
        if rr.get("value") is not None:
            _, adjusted_quality = cross_check_rr(finding, rr["value"], rr.get("quality", 0.0))
            state.vitals["respiration_rate"] = {"value": rr["value"], "quality": adjusted_quality}
    else:
        finding = processor(request.landmark_series)

    finding.pop("_extra", None)

    state = get_or_create_session(request.session_id)
    state.findings.append(finding)

    await _write_findings(req, request.session_id, [finding])

    return SecondLookSubmitResponse(findings=[Finding(**finding)])
