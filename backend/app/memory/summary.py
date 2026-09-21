"""Tier 3 — person memory summary assembly (architecture.md §6). Pure functions:
plain dicts in, plain dicts out, no I/O (CLAUDE.md "signal-processing functions
are pure" applied to memory too). Graph reads live in memory/persistence.py;
this module never talks to Neo4j.

`sessions` is always ordered newest-first, each shaped:
{"session_id", "created_at", "status", "top_findings": [...], "recommendations": [...],
 "readings": [{"vital", "value", "unit", "quality", "tier"}, ...]}
"""

from __future__ import annotations

from statistics import median
from typing import Any


def _rolling_median(readings: list[dict[str, Any]], vital: str) -> float | None:
    values = [r["value"] for r in readings if r.get("vital") == vital and r.get("value") is not None]
    if not values:
        return None
    return median(values)


def build_person_summary(
    person: dict[str, Any],
    village: dict[str, Any] | None,
    sessions: list[dict[str, Any]],
    chronic_flags: list[dict[str, Any]] | None = None,
    open_followups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Returns exactly the structure in architecture.md §6. This is what enters
    the agent context — never the full history."""
    all_readings = [r for s in sessions for r in s.get("readings", []) if r.get("vital")]
    vital_names = sorted({r["vital"] for r in all_readings})
    vital_baselines = {v: _rolling_median(all_readings, v) for v in vital_names}

    last = sessions[0] if sessions else None
    last_session = (
        {
            "date": last["created_at"],
            "top_findings": last.get("top_findings", []),
            "recommendations": last.get("recommendations", []),
        }
        if last
        else None
    )

    return {
        "demographics": {
            "person_id": person.get("person_id"),
            "name": person.get("name"),
            "age": person.get("age"),
            "gender": person.get("gender"),
        },
        "village_context": village or {},
        "chronic_flags": chronic_flags or [],
        "vital_baselines": vital_baselines,
        "last_session": last_session,
        "open_followups": open_followups or [],
    }


def vital_delta(sessions: list[dict[str, Any]], vital: str) -> dict[str, Any] | None:
    """Longitudinal delta for one vital: the two most recent readings, oldest
    to newest. `sessions` may be in any order; this sorts by created_at itself."""
    points = [
        (s["created_at"], r["value"])
        for s in sessions
        for r in s.get("readings", [])
        if r.get("vital") == vital and r.get("value") is not None
    ]
    if len(points) < 2:
        return None
    points.sort(key=lambda p: p[0])
    (prev_date, prev_val), (latest_date, latest_val) = points[-2], points[-1]
    return {
        "from": {"date": prev_date, "value": prev_val},
        "to": {"date": latest_date, "value": latest_val},
        "delta": latest_val - prev_val,
    }
