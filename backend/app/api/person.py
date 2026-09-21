"""GET /api/person/{person_id} — screen 15 (S13). Assembles the Tier 3 person
summary (architecture.md §6) plus the session timeline and vital trends.
Falls back to the golden-path Ramesh Kumar profile when Neo4j is unreachable
or the person has no recorded sessions yet, same pattern as api/kb.py."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.memory import persistence
from app.models import PersonProfileResponse, PersonSummary, SessionSummary, VitalSeriesPoint

router = APIRouter(prefix="/api/person", tags=["person"])


def _golden_path_profile(person_id: str) -> PersonProfileResponse:
    return PersonProfileResponse(
        person_id=person_id,
        name="Ramesh Kumar",
        age=52,
        gender="male",
        village="Kadiri",
        sessions=[
            SessionSummary(date="2026-09-20", kind="Face scan + voice consult", outcome="TB presumptive - referred"),
            SessionSummary(date="2026-08-02", kind="Routine screening", outcome="Mild pallor noted"),
        ],
        vital_series={
            "respiration_rate": [
                VitalSeriesPoint(date="2026-08-02", value=18),
                VitalSeriesPoint(date="2026-09-20", value=22),
            ],
            "bp_trend": [
                VitalSeriesPoint(date="2026-08-02", value="stable"),
                VitalSeriesPoint(date="2026-09-20", value="elevated"),
            ],
        },
    )


def _outcome_line(session: dict) -> str:
    findings = session.get("top_findings") or []
    return ", ".join(findings) if findings else "No findings recorded"


@router.get("/{person_id}", response_model=PersonProfileResponse)
async def get_person(person_id: str, request: Request) -> PersonProfileResponse:
    client = getattr(request.app.state, "graph_client", None)
    if client is None:
        return _golden_path_profile(person_id)

    try:
        fetched = await persistence.fetch_person_summary(client, person_id)
    except Exception:
        return _golden_path_profile(person_id)

    if fetched is None:
        return _golden_path_profile(person_id)

    person_row = fetched["person"]
    sessions = fetched["sessions"]  # newest-first

    vital_series: dict[str, list[VitalSeriesPoint]] = {}
    for session in reversed(sessions):  # oldest-first for a trend chart
        for reading in session.get("readings", []):
            vital = reading.get("vital")
            if not vital:
                continue
            vital_series.setdefault(vital, []).append(
                VitalSeriesPoint(date=session["created_at"], value=reading["value"])
            )

    return PersonProfileResponse(
        person_id=person_row["person_id"],
        name=person_row["name"],
        age=person_row["age"],
        gender=person_row["gender"],
        village=person_row["village_name"],
        sessions=[
            SessionSummary(date=s["created_at"], kind="Screening", outcome=_outcome_line(s)) for s in sessions
        ],
        vital_series=vital_series,
        summary=PersonSummary(**fetched["summary"]),
    )
