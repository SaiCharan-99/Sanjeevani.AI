"""Three-tier memory model tests (architecture.md §6).

Tier 3 (`build_person_summary`) is pure — dicts in, dict out — so it is tested
directly against fabricated session/reading data, no live Neo4j required, same
approach as test_seed.py for the KB layer. `vital_delta` gets its own test for
the longitudinal-delta requirement.
"""

from __future__ import annotations

from app.memory.state import SessionState, get_or_create_session, get_session, open_session
from app.memory.summary import build_person_summary, vital_delta

PERSON = {"person_id": "p_test", "name": "Lakshmamma Boya", "age": 52, "gender": "female"}
VILLAGE = {"village_id": "kadiri", "name": "Kadiri Rural"}


def _session(session_id: str, created_at: str, heart_rate: float, spo2: float, findings=None):
    return {
        "session_id": session_id,
        "created_at": created_at,
        "status": "done_unopened",
        "top_findings": findings or [],
        "recommendations": [],
        "readings": [
            {"vital": "heart_rate", "value": heart_rate, "unit": "bpm", "quality": 0.8, "tier": "reliable"},
            {"vital": "spo2", "value": spo2, "unit": "%", "quality": 0.6, "tier": "approximate"},
        ],
    }


def test_build_person_summary_shape_and_rolling_baseline():
    # Two sessions, different vitals — session 2 (newest) has a lower spo2 and
    # higher heart rate than session 1.
    session_1 = _session("SAN-2026-0001", "2026-08-02T09:00:00+00:00", heart_rate=78, spo2=97)
    session_2 = _session(
        "SAN-2026-0002", "2026-09-20T09:00:00+00:00", heart_rate=96, spo2=94, findings=["TB presumptive"]
    )
    # sessions are passed newest-first, matching LIST_PERSON_SESSIONS_WITH_READINGS
    sessions = [session_2, session_1]

    summary = build_person_summary(PERSON, VILLAGE, sessions)

    assert set(summary.keys()) == {
        "demographics",
        "village_context",
        "chronic_flags",
        "vital_baselines",
        "last_session",
        "open_followups",
    }
    assert summary["demographics"] == {"person_id": "p_test", "name": "Lakshmamma Boya", "age": 52, "gender": "female"}
    assert summary["village_context"] == VILLAGE

    # median of [78, 96] = 87; median of [97, 94] = 95.5
    assert summary["vital_baselines"]["heart_rate"] == 87
    assert summary["vital_baselines"]["spo2"] == 95.5

    assert summary["last_session"]["date"] == "2026-09-20T09:00:00+00:00"
    assert summary["last_session"]["top_findings"] == ["TB presumptive"]


def test_build_person_summary_no_sessions_yet():
    summary = build_person_summary(PERSON, VILLAGE, [])
    assert summary["vital_baselines"] == {}
    assert summary["last_session"] is None


def test_vital_delta_longitudinal_change():
    session_1 = _session("SAN-2026-0001", "2026-08-02T09:00:00+00:00", heart_rate=78, spo2=97)
    session_2 = _session("SAN-2026-0002", "2026-09-20T09:00:00+00:00", heart_rate=96, spo2=94)

    delta = vital_delta([session_1, session_2], "spo2")
    assert delta["from"] == {"date": "2026-08-02T09:00:00+00:00", "value": 97}
    assert delta["to"] == {"date": "2026-09-20T09:00:00+00:00", "value": 94}
    assert delta["delta"] == -3

    assert vital_delta([session_1], "spo2") is None


def test_session_state_tier1_registry_round_trip():
    state = open_session("SAN-2026-9999", person_id="p_test")
    assert isinstance(state, SessionState)
    assert get_session("SAN-2026-9999") is state

    state.vitals["heart_rate"] = {"value": 88, "unit": "bpm", "quality": 0.9, "tier": "reliable"}
    state.pain_points.append({"symptom": "cough"})

    same_state = get_or_create_session("SAN-2026-9999")
    assert same_state is state
    assert same_state.vitals["heart_rate"]["value"] == 88

    fresh = get_or_create_session("SAN-2026-0000-not-yet-opened")
    assert fresh.session_id == "SAN-2026-0000-not-yet-opened"
    assert fresh.vitals == {}
