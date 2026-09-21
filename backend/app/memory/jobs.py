"""In-process background job queue (architecture.md §7 stage 5, §9). Synthesis
runs as a FastAPI BackgroundTasks job; the officer moves to the next person and
polls GET /api/synthesis/result later. No Celery/Redis (CLAUDE.md) — a
module-level dict is the whole queue, and it survives being polled because it
outlives any single request in this process."""

from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable

_JOBS: dict[str, dict[str, Any]] = {}
_SESSION_JOBS: dict[str, str] = {}  # session_id -> latest job_id


def new_job_id() -> str:
    return f"j_{uuid.uuid4().hex[:8]}"


def create_job(job_id: str, session_id: str) -> None:
    _JOBS[job_id] = {"status": "queued", "result": None}
    _SESSION_JOBS[session_id] = job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    return _JOBS.get(job_id)


def latest_job_for_session(session_id: str) -> dict[str, Any] | None:
    job_id = _SESSION_JOBS.get(session_id)
    return _JOBS.get(job_id) if job_id else None


async def run_job(job_id: str, work: Callable[[], Awaitable[Any]]) -> None:
    job = _JOBS.get(job_id)
    if job is None:
        return
    job["status"] = "running"
    try:
        job["result"] = await work()
        job["status"] = "done"
    except Exception as exc:  # defensive — a broken job must not lose the slot
        job["status"] = "error"
        job["result"] = {"error": str(exc)}
