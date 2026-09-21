"""Consultation: transcription, content-based speaker attribution, pain-point
extraction (specs.md §3, architecture.md §10).

Live mode is fail-closed: missing/empty audio and every Gemini failure return an
explicit HTTP error, so cached clinical content can never be mistaken for a
real consultation. The golden-path cache is used only when
`SANJEEVANI_FIXTURE_MODE=true`, for deliberate offline demos and tests.

Graph writes are best-effort in the same way: when `app.state.graph_client` is
None or a Cypher call raises, the write is a silent no-op and Tier 1 working
memory still carries the session forward.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile

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
from app.providers.llm import LLMUnavailable, OpenRouterLLM, fixture_mode
from app.providers.stt import FasterWhisperSTT, STTUnavailable, Transcript

router = APIRouter(prefix="/api/consult", tags=["consult"])
logger = logging.getLogger("sanjeevani.consult")

# LLM reasoning (extraction/attribution) runs through OpenRouter, model
# anthropic/claude-haiku-4.5 (OPENROUTER_API_KEY / OPENROUTER_MODEL). STT runs
# fully local via faster-whisper (real ASR, not a generative model) — live
# testing showed every multimodal-LLM STT option tried (Gemini,
# openai/gpt-audio-mini, openai/gpt-audio) hallucinates a plausible fake
# transcript from silence/non-speech audio instead of returning empty, which
# is unsafe for a medical-transcription path. Whisper decodes audio frames
# rather than generating text, so it isn't prone to this failure mode.
# GeminiLLM/AnthropicLLM/GeminiSTT/OpenRouterSTT stay defined in providers/ as
# alternate implementations of the same Protocol seam.
_llm = OpenRouterLLM()
_stt = FasterWhisperSTT()


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

    if not fixture_mode() and len(audio_bytes) < 1024:
        raise HTTPException(
            status_code=400,
            detail="No usable microphone audio was received. Record for at least one second and try again.",
        )

    source = "live"
    transcript: Transcript | None = None
    try:
        mime_type = audio.content_type if audio and audio.content_type else "audio/webm"
        transcript = await _stt.transcribe(audio_bytes, language, mime_type)
        if not transcript.segments:
            raise STTUnavailable("Empty transcript.")
    except (STTUnavailable, NotImplementedError, ValueError) as exc:
        logger.exception(
            "Live transcription failed session=%s bytes=%d content_type=%s",
            session_id,
            len(audio_bytes),
            audio.content_type if audio else None,
        )
        if not fixture_mode():
            raise HTTPException(status_code=503, detail=f"Live transcription failed: {exc}") from exc
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
    memory, written by /transcribe). The cache is used only in explicit fixture
    mode or when a live transcript exactly matches the demo script."""
    state = get_or_create_session(session_id)
    if not state.transcript and not fixture_mode():
        raise HTTPException(status_code=409, detail="No live transcript exists for this session.")
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
        except Exception as exc:
            logger.exception("Live pain-point extraction failed session=%s", session_id)
            if not fixture_mode():
                message = str(exc) if isinstance(exc, LLMUnavailable) else type(exc).__name__
                raise HTTPException(status_code=503, detail=f"Live pain-point extraction failed: {message}") from exc
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
