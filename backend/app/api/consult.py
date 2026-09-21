"""Consultation: transcription, content-based speaker attribution, pain-point
extraction (specs.md §3, architecture.md §10).

Degradation policy, same as `api/kb.py` / `api/session.py`: every live Gemini
call is wrapped, and any failure (no key, rate limit, network, unparseable
response) falls back to the cached golden-path response
(`providers/golden_path.json`) rather than returning an error. The response
carries `source` so developer mode can tell the two apart — the UI never claims
a cached answer was live.

Graph writes are best-effort in the same way: when `app.state.graph_client` is
None or a Cypher call raises, the write is a silent no-op and Tier 1 working
memory still carries the session forward.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request, UploadFile

from app.agents.attribution import attribute_speakers, segments_to_turns, turns_to_transcript_text
from app.agents.extraction import extract_pain_points
from app.agents.triggers import detect_red_flags
from app.memory import persistence
from app.memory.state import get_or_create_session
from app.models import (
    ExtractResponse,
    PainPoint,
    PainPointsSaveRequest,
    PainPointsSaveResponse,
    TranscribeResponse,
    TranscriptTurn,
)
from app.providers import cache
from app.providers.llm import GeminiLLM
from app.providers.stt import GeminiSTT, STTUnavailable, Transcript

router = APIRouter(prefix="/api/consult", tags=["consult"])

_llm = GeminiLLM()
_stt = GeminiSTT()


def _cached_turns() -> list[dict]:
    return [dict(t) for t in cache.golden_transcribe()["turns"]]


async def _write_transcript(request: Request, session_id: str, turns: list[dict], language: str) -> None:
    client = getattr(request.app.state, "graph_client", None)
    if client is None:
        return
    try:
        await persistence.write_transcript(
            client, session_id=session_id, turns=turns, language=language
        )
    except Exception:
        pass  # graceful no-op — Tier 1 still holds the transcript


async def _write_pain_points(
    request: Request, session_id: str, pain_points: list[dict], language: str, source: str
) -> None:
    client = getattr(request.app.state, "graph_client", None)
    if client is None:
        return
    try:
        await persistence.write_pain_points(
            client,
            session_id=session_id,
            pain_points=pain_points,
            language=language,
            source=source,
        )
    except Exception:
        pass


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    request: Request,
    session_id: str = Form(...),
    language: str = Form("en"),
    audio: UploadFile | None = None,
) -> TranscribeResponse:
    """Multipart audio + session_id + language.

    Transcription is Gemini; **speaker attribution is content-based**, a second
    LLM pass over the plain transcript text (architecture.md §10). There is no
    audio-diarization path."""
    audio_bytes = await audio.read() if audio is not None else b""

    source = "live"
    transcript: Transcript | None = None
    try:
        transcript = await _stt.transcribe(audio_bytes, language)
        if not transcript.segments:
            raise STTUnavailable("Empty transcript.")
    except (STTUnavailable, NotImplementedError, ValueError):
        transcript = None

    if transcript is None:
        source = "golden_path_cache"
        cached = cache.golden_transcribe()
        turns = _cached_turns()
        detected = cached["language_detected"]
    else:
        transcript = await attribute_speakers(_llm, transcript)
        turns = segments_to_turns(transcript)
        detected = transcript.language_detected
        # If the live transcript is the demo script, prefer the cached turns so
        # the golden path is byte-stable on stage.
        if cache.matches_golden_path(turns_to_transcript_text(turns)):
            source = "golden_path_cache"
            turns = _cached_turns()
            detected = cache.golden_transcribe()["language_detected"]

    state = get_or_create_session(session_id)
    state.transcript = turns

    await _write_transcript(request, session_id, turns, detected)

    return TranscribeResponse(
        turns=[TranscriptTurn(**t) for t in turns],
        language_detected=detected if detected in ("en", "te", "hi") else "en",
        source=source,
    )


@router.post("/extract", response_model=ExtractResponse)
async def extract(session_id: str, request: Request) -> ExtractResponse:
    """Pain-point extraction over the session's transcript (Tier 1 working
    memory, written by /transcribe). Falls back to the cached golden-path
    extraction when the LLM is unavailable or the transcript is the demo
    script."""
    state = get_or_create_session(session_id)
    turns = state.transcript or _cached_turns()
    transcript_text = turns_to_transcript_text(turns)
    language = "te" if cache.matches_golden_path(transcript_text) else "en"

    source = "live"
    pain_points: list[dict] = []
    if cache.matches_golden_path(transcript_text):
        source = "golden_path_cache"
        pain_points = [dict(p) for p in cache.golden_extract()["pain_points"]]
    else:
        try:
            pain_points = await extract_pain_points(_llm, transcript_text)
        except Exception:
            source = "golden_path_cache"
            pain_points = [dict(p) for p in cache.golden_extract()["pain_points"]]

    for p in pain_points:
        p.setdefault("unmapped_text", None if p.get("canonical") else p.get("symptom"))

    flags = detect_red_flags([p["canonical"] for p in pain_points if p.get("canonical")])
    state.pain_points = pain_points

    await _write_pain_points(request, session_id, pain_points, language, source="llm")

    return ExtractResponse(
        pain_points=[PainPoint(**p) for p in pain_points],
        red_flags=[f.symptom for f in flags],
        red_flag_messages=[f.message for f in flags],
        source=source,
    )


@router.post("/painpoints", response_model=PainPointsSaveResponse)
async def save_pain_points(body: PainPointsSaveRequest, request: Request) -> PainPointsSaveResponse:
    """The officer's reviewed list (screens 8 and 9) replaces the extracted one.

    Not in specs.md §3 — added because screens 8/9 are explicitly
    human-in-the-loop and their corrections have to reach the graph and the
    audit log. Officer-authored entries are written with `source: 'officer'`.
    """
    pain_points = [p.model_dump() for p in body.pain_points]
    state = get_or_create_session(body.session_id)
    state.pain_points = pain_points

    await _write_pain_points(
        request, body.session_id, pain_points, "en", source=body.edited_by
    )

    flags = detect_red_flags([p["canonical"] for p in pain_points if p.get("canonical")])
    return PainPointsSaveResponse(
        session_id=body.session_id,
        saved=len(pain_points),
        red_flags=[f.symptom for f in flags],
    )
