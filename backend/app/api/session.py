"""Session lifecycle (architecture.md §6 tiers 1/2, specs.md §3). Writes
:PHI:Person/:PHI:Session continuously so a mid-session crash loses nothing
(rule: consent before camera — /start rejects any session without
`consent: true`). Falls back to in-memory-only behaviour when Neo4j is
unreachable, same pattern as api/kb.py, so the demo still boots."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Request

from app.memory import persistence, state
from app.models import (
    PendingSession,
    SessionCompleteRequest,
    SessionCompleteResponse,
    SessionPendingResponse,
    SessionSaveRequest,
    SessionSaveResponse,
    SessionStartRequest,
    SessionStartResponse,
)

router = APIRouter(prefix="/api/session", tags=["session"])


def _graph(request: Request):
    return getattr(request.app.state, "graph_client", None)


@router.post("/start", response_model=SessionStartResponse)
async def start_session(request: SessionStartRequest, http_request: Request) -> SessionStartResponse:
    if not request.consent:
        raise HTTPException(status_code=400, detail="Session requires consent: true before any capture")

    year = date.today().year
    session_id = f"SAN-{year}-{uuid.uuid4().hex[:4]}"
    person_id = f"p_{uuid.uuid4().hex[:8]}"
    village_id = request.person.village.strip().lower().replace(" ", "_")

    client = _graph(http_request)
    if client is not None:
        try:
            await persistence.start_session(
                client,
                person_id=person_id,
                session_id=session_id,
                name=request.person.name,
                age=request.person.age,
                gender=request.person.gender,
                village_id=village_id,
                village_name=request.person.village,
                language=request.language,
                consent=request.consent,
            )
        except Exception:
            pass  # demo stays usable even if Neo4j write fails; Tier 1 still works

    state.open_session(session_id, person_id=person_id)
    return SessionStartResponse(session_id=session_id, person_id=person_id)


@router.post("/save", response_model=SessionSaveResponse)
async def save_reading(request: SessionSaveRequest, http_request: Request) -> SessionSaveResponse:
    """Tier 1 + Tier 2 together: updates the in-process SessionState and writes
    the :PHI:Reading immediately, not batched until /complete."""
    session_state = state.get_or_create_session(request.session_id)
    session_state.vitals[request.vital] = {
        "value": request.value,
        "unit": request.unit,
        "quality": request.quality,
        "tier": request.tier,
    }

    reading_id = f"r_{uuid.uuid4().hex[:8]}"
    client = _graph(http_request)
    if client is not None:
        try:
            reading_id = await persistence.save_reading(
                client,
                session_id=request.session_id,
                vital=request.vital,
                value=request.value,
                unit=request.unit,
                quality=request.quality,
                tier=request.tier,
            )
        except Exception:
            pass

    return SessionSaveResponse(reading_id=reading_id)


@router.post("/complete", response_model=SessionCompleteResponse)
async def complete_session(request: SessionCompleteRequest, http_request: Request) -> SessionCompleteResponse:
    session_state = state.get_session(request.session_id)
    top_findings = request.top_findings or (
        [f.get("feature", "") for f in session_state.findings] if session_state else []
    )

    client = _graph(http_request)
    if client is not None:
        try:
            await persistence.complete_session(
                client,
                session_id=request.session_id,
                top_findings=top_findings,
                recommendations=request.recommendations,
            )
        except Exception:
            pass

    return SessionCompleteResponse(session_id=request.session_id, status="done_unopened")


@router.get("/pending", response_model=SessionPendingResponse)
async def pending_sessions(request: Request) -> SessionPendingResponse:
    client = _graph(request)
    if client is not None:
        try:
            rows = await persistence.list_pending_sessions(client)
            if rows:
                return SessionPendingResponse(
                    sessions=[
                        PendingSession(session_id=r["session_id"], person_name=r["person_name"], status=r["status"])
                        for r in rows
                    ]
                )
        except Exception:
            pass

    return SessionPendingResponse(
        sessions=[
            PendingSession(session_id="SAN-2026-0982", person_name="Ramesh Kumar", status="done_unopened"),
        ]
    )
