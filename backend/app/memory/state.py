"""Three-tier memory model (architecture.md §6).

Tier 1 — SessionState: in-process working memory, life of one session, lost on
restart (acceptable per architecture.md §6).

Tier 2 persistence (continuous :PHI:Session / :PHI:Reading writes) and Tier 3
assembly (person summary) live in memory/persistence.py and memory/summary.py
respectively — this module only owns Tier 1 plus the in-process registry that
lets api/session.py find a session's working memory across requests.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionState:
    """Tier 1 — working memory, in-process, life of one session. Lost on
    restart; that is acceptable per architecture.md §6."""

    session_id: str
    person_id: str | None = None
    vitals: dict = field(default_factory=dict)
    transcript: list[dict] = field(default_factory=list)
    pain_points: list[dict] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    proposed_features: list[str] = field(default_factory=list)
    accepted_features: list[str] = field(default_factory=list)


_SESSIONS: dict[str, SessionState] = {}


def open_session(session_id: str, person_id: str | None = None) -> SessionState:
    state = SessionState(session_id=session_id, person_id=person_id)
    _SESSIONS[session_id] = state
    return state


def get_session(session_id: str) -> SessionState | None:
    return _SESSIONS.get(session_id)


def get_or_create_session(session_id: str) -> SessionState:
    return _SESSIONS.setdefault(session_id, SessionState(session_id=session_id))
