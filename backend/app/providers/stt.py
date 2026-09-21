"""STT provider seam (architecture.md §10).

**Never import `google.generativeai` outside `app/providers/`.**

Speaker attribution is *content-based*, not audio diarization (architecture.md
§10, CLAUDE.md "AI provider rules"): this module only turns audio into plain
timestamped text. `agents/attribution.py` then sends that text to the LLM and
assigns each turn to `officer` or `person` by who asks questions and who uses
symptom vocabulary. No audio-level diarization route exists anywhere in the
codebase, by design.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol

LANGUAGE_NAMES = {"en": "English", "te": "Telugu", "hi": "Hindi"}

GEMINI_MODEL = os.environ.get("GEMINI_STT_MODEL", "gemini-3.6-flash")

TRANSCRIBE_PROMPT = """You are transcribing a short medical-camp consultation between a
medical health officer and a person attending the camp. The audio is in {language}.

Produce a faithful transcript. For every utterance give:
  - "start_s": the start time in seconds (a number)
  - "text_original": the utterance transcribed in the original spoken language, in its
    native script
  - "text": a plain English translation of that same utterance

Do not merge two speakers into one utterance. Do not label the speakers — speaker
attribution is done separately. Do not summarise, interpret or add anything that was
not said. Do not add any clinical interpretation.
"""


@dataclass
class TranscriptSegment:
    """One utterance. `speaker` is filled in later by the content-based
    attribution pass — STT itself never assigns it."""

    text: str
    start_s: float
    text_original: str | None = None
    speaker: str | None = None


@dataclass
class Transcript:
    segments: list[TranscriptSegment] = field(default_factory=list)
    language_detected: str = "en"

    def plain_text(self) -> str:
        return "\n".join(s.text for s in self.segments)


class STTProvider(Protocol):
    async def transcribe(self, audio: bytes, lang_hint: str) -> Transcript: ...


class STTUnavailable(RuntimeError):
    """No key, rate limited, network down, or an unparseable response.
    Callers fall back to the golden-path cache rather than showing an error."""


class GeminiSTT:
    """Transcribes English / Telugu / Hindi audio via Gemini.

    Constructing it never raises, so the app boots without a key."""

    MIME_TYPE = "audio/webm"

    def __init__(self, model: str = GEMINI_MODEL) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model_name = model

    async def transcribe(self, audio: bytes, lang_hint: str) -> Transcript:
        from app.providers.llm import fixture_mode

        if fixture_mode():
            raise STTUnavailable(
                "SANJEEVANI_FIXTURE_MODE is set — serving from the golden-path cache, no live call attempted."
            )
        if not self.api_key:
            raise STTUnavailable(
                "GEMINI_API_KEY not set — no live transcription is possible in this environment."
            )
        if not audio:
            raise STTUnavailable("No audio bytes received.")

        import google.generativeai as genai  # imported only here, per CLAUDE.md

        from app.providers.llm import parse_structured

        from pydantic import BaseModel

        class _Utterance(BaseModel):
            start_s: float
            text: str
            text_original: str | None = None

        class _RawTranscript(BaseModel):
            language_detected: str = lang_hint
            utterances: list[_Utterance] = []

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model_name)
        prompt = TRANSCRIBE_PROMPT.format(language=LANGUAGE_NAMES.get(lang_hint, "English"))
        from app.providers.llm import schema_instruction

        try:
            response = await model.generate_content_async(
                [
                    f"{prompt}\n\n{schema_instruction(_RawTranscript)}",
                    {"mime_type": self.MIME_TYPE, "data": audio},
                ],
                generation_config={"response_mime_type": "application/json"},
            )
        except Exception as exc:  # rate limit, network, safety block
            raise STTUnavailable(f"Gemini STT call failed: {exc}") from exc

        try:
            parsed = parse_structured(response.text, _RawTranscript)
        except ValueError as exc:
            raise STTUnavailable(str(exc)) from exc

        detected = parsed.language_detected if parsed.language_detected in LANGUAGE_NAMES else lang_hint
        return Transcript(
            segments=[
                TranscriptSegment(text=u.text, start_s=u.start_s, text_original=u.text_original)
                for u in parsed.utterances
            ],
            language_detected=detected,
        )


class WhisperCppSTT:
    """Stubbed local-model implementation.

    Exists to back the offline pitch claim honestly (architecture.md §10): this
    is the seam a local whisper.cpp build drops into. Deliberately **not
    wired** in this build — Gemini is required today and the UI must not claim
    otherwise (rule 10)."""

    async def transcribe(self, audio: bytes, lang_hint: str) -> Transcript:
        raise NotImplementedError(
            "WhisperCppSTT is a documented seam, not wired in this build (architecture.md §10)."
        )
