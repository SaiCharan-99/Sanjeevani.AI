"""Tier 2 (continuous :PHI:Session / :PHI:Reading writes) and the graph-read
side of Tier 3 (person summary inputs). All Cypher lives in graph/queries.py
(CLAUDE.md); this module only shapes params and rows. Every function takes a
GraphClient explicitly — no global state, no ORM.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.graph import queries as q
from app.graph.client import GraphClient
from app.memory.summary import build_person_summary


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def find_existing_person(
    client: GraphClient, *, name: str, village_id: str, gender: str
) -> str | None:
    """Returning-patient lookup for /api/session/start (architecture.md §6
    Tier 3) — narrow, deliberately conservative match on name + village +
    gender (case-insensitive); see queries.FIND_EXISTING_PERSON. Returns None
    on no match, letting the caller mint a fresh person_id as before."""
    rows = await client.run(q.FIND_EXISTING_PERSON, name=name, village_id=village_id, gender=gender)
    return rows[0]["person_id"] if rows else None


async def start_session(
    client: GraphClient,
    *,
    person_id: str,
    session_id: str,
    name: str,
    age: int,
    gender: str,
    village_id: str,
    village_name: str,
    language: str,
    consent: bool,
) -> None:
    await client.run(
        q.CREATE_PERSON_AND_SESSION,
        person_id=person_id,
        name=name,
        age=age,
        gender=gender,
        village_id=village_id,
        village_name=village_name,
        session_id=session_id,
        language=language,
        consent=consent,
        created_at=_now(),
    )


async def save_reading(
    client: GraphClient,
    *,
    session_id: str,
    vital: str,
    value: float,
    unit: str,
    quality: float,
    tier: str,
) -> str:
    """Writes one :PHI:Reading immediately — called as each vital is captured
    during the session, not batched at the end (architecture.md §6 tier 2:
    'a mid-session crash must lose nothing')."""
    reading_id = f"r_{uuid.uuid4().hex[:8]}"
    await client.run(
        q.CREATE_SESSION_READING,
        session_id=session_id,
        reading_id=reading_id,
        vital=vital,
        value=value,
        unit=unit,
        quality=quality,
        tier=tier,
        created_at=_now(),
    )
    return reading_id


async def complete_session(
    client: GraphClient,
    *,
    session_id: str,
    top_findings: list[str],
    recommendations: list[str],
) -> None:
    await client.run(
        q.COMPLETE_SESSION,
        session_id=session_id,
        completed_at=_now(),
        top_findings=top_findings,
        recommendations=recommendations,
    )


async def list_pending_sessions(client: GraphClient) -> list[dict[str, Any]]:
    return await client.run(q.LIST_PENDING_SESSIONS)


async def village_autocomplete(client: GraphClient, prefix: str) -> list[str]:
    rows = await client.run(q.VILLAGE_AUTOCOMPLETE, prefix=prefix)
    return [row["name"] for row in rows]


async def fetch_person_summary(client: GraphClient, person_id: str) -> dict[str, Any] | None:
    """Tier 3 assembly: reads the person + session chain, then delegates to the
    pure `build_person_summary` (memory/summary.py). Returns None if the person
    does not exist — callers fall back to the golden-path demo profile."""
    person_rows = await client.run(q.GET_PERSON_FOR_SUMMARY, person_id=person_id)
    if not person_rows:
        return None
    person_row = person_rows[0]
    session_rows = await client.run(q.LIST_PERSON_SESSIONS_WITH_READINGS, person_id=person_id)

    person = {
        "person_id": person_row["person_id"],
        "name": person_row["name"],
        "age": person_row["age"],
        "gender": person_row["gender"],
    }
    village = {"village_id": person_row["village_id"], "name": person_row["village_name"]}
    sessions = [
        {
            "session_id": row["session_id"],
            "created_at": row["created_at"],
            "status": row["status"],
            "top_findings": row["top_findings"],
            "recommendations": row["recommendations"],
            "readings": row["readings"],
        }
        for row in session_rows
    ]

    summary = build_person_summary(person, village, sessions)
    return {"person": person_row, "sessions": sessions, "summary": summary}


# ---------------------------------------------------------------------------
# Consultation (Phase 4) — :PHI:Utterance writes and the :REPORTS join into the
# knowledge graph. Every join edge carries a confidence value (CLAUDE.md rule 6).
# ---------------------------------------------------------------------------

async def write_transcript(
    client: GraphClient, *, session_id: str, turns: list[dict[str, Any]], language: str
) -> int:
    """One :PHI:Utterance per attributed turn. Rewrites the session's turns, so
    re-running transcription does not duplicate them."""
    await client.run(q.DELETE_SESSION_UTTERANCES, session_id=session_id)
    written = 0
    for i, turn in enumerate(turns):
        await client.run(
            q.CREATE_UTTERANCE,
            session_id=session_id,
            utterance_id=f"u_{session_id}_{i}",
            speaker=turn.get("speaker", "person"),
            text=turn.get("text", ""),
            text_original=turn.get("text_original"),
            start_s=float(turn.get("start_s", 0.0)),
            language=language,
            created_at=_now(),
        )
        written += 1
    return written


async def write_pain_points(
    client: GraphClient,
    *,
    session_id: str,
    pain_points: list[dict[str, Any]],
    language: str,
    source: str = "llm",
) -> int:
    """Writes one :PHI:Utterance per reported pain point and, when the term
    resolved to a canonical slug, a `:REPORTS {confidence, verbatim}` edge to
    the `:KB:Symptom`. Unresolved terms keep `unmapped_text` and no edge — the
    runtime never creates `:KB` nodes."""
    written = 0
    for i, p in enumerate(pain_points):
        await client.run(
            q.CREATE_UTTERANCE_REPORTS_SYMPTOM,
            session_id=session_id,
            utterance_id=f"pp_{session_id}_{i}",
            slug=p.get("canonical"),
            confidence=float(p.get("confidence", 0.5)),
            verbatim=p.get("verbatim") or p.get("symptom", ""),
            verbatim_original=p.get("verbatim_original"),
            unmapped_text=p.get("unmapped_text"),
            duration_days=p.get("duration_days"),
            language=language,
            source=source,
            created_at=_now(),
        )
        written += 1
    return written


# ---------------------------------------------------------------------------
# Second look (Phase 5) — :PHI:Finding writes and the :INDICATES join into the
# knowledge graph. Every join edge carries a confidence value (rule 6).
# ---------------------------------------------------------------------------

#: Which `:KB:Symptom` slug a second-look feature's finding indicates.
#: Mirrors the symptom groupings in agents/triggers.py's TRIGGER_TABLE — the
#: same documented association, not a new clinical rule. An unmatched slug
#: (if the KB doesn't carry it) simply writes no :INDICATES edge; the runtime
#: never creates :KB nodes.
FEATURE_INDICATES_SYMPTOM = {
    "facial_asymmetry": "facial_droop",
    "chest_rise_respiration": "exertional_breathlessness",
    "lip_cyanosis": "breathlessness",
    "swelling_asymmetry": "limb_pain",
    "guided_range_of_motion": "limb_pain",
    "pallor_check": "fatigue",
    "sclera_colour": "jaundice_signs",
    "posture_assessment": "back_pain",
    "gait_balance": "difficulty_walking",
    "blink_rate_tremor": "disorientation",
}


async def write_findings(
    client: GraphClient, *, session_id: str, findings: list[dict[str, Any]]
) -> int:
    """One :PHI:Finding per second-look result, joined via `:INDICATES
    {confidence}` to the `:KB:Symptom` the feature is documented to indicate
    (architecture.md §5 "The join"; CLAUDE.md rule 6)."""
    written = 0
    for i, f in enumerate(findings):
        finding_id = f"f_{session_id}_{f.get('feature')}_{i}"
        await client.run(
            q.CREATE_FINDING,
            session_id=session_id,
            finding_id=finding_id,
            feature=f.get("feature"),
            value=float(f.get("value", 0.0)),
            unit=f.get("unit", ""),
            method=f.get("method", ""),
            interpretation=f.get("interpretation", ""),
            confidence=float(f.get("confidence", 0.0)),
            limitations=f.get("limitations", ""),
            created_at=_now(),
        )
        slug = FEATURE_INDICATES_SYMPTOM.get(f.get("feature"))
        if slug:
            await client.run(
                q.CREATE_FINDING_INDICATES_SYMPTOM,
                finding_id=finding_id,
                slug=slug,
                confidence=float(f.get("confidence", 0.0)),
            )
        written += 1
    return written
