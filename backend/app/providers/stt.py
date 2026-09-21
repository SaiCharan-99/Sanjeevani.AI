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

import asyncio
import os
from dataclasses import dataclass, field
from typing import Protocol

from app.providers.llm import LIVE_CALL_TIMEOUT_S

LANGUAGE_NAMES = {"en": "English", "te": "Telugu", "hi": "Hindi"}

GEMINI_MODEL = os.environ.get("GEMINI_STT_MODEL", "gemini-3.1-flash-lite")

OPENROUTER_STT_MODEL = os.environ.get("OPENROUTER_STT_MODEL", "openai/gpt-audio-mini")

_AUDIO_FORMAT_FROM_MIME = {
    "audio/webm": "webm",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mp3": "mp3",
    "audio/mpeg": "mp3",
}

TRANSCRIBE_PROMPT = """You are transcribing a short medical-camp consultation between a
medical health officer and a person attending the camp. The audio is in {language}.

Produce a faithful transcript. For every utterance give:
  - "start_s": the start time in seconds (a number)
  - "text_original": the utterance transcribed in the original spoken language, in its
    native script
  - "text": a plain English translation of that same utterance

Do not merge two speakers into one utterance. Do not label the speakers — speaker
attribution is done separately. Do not summarise, interpret or add anything that was
not said. Do not add any clinical interpretation. If there is no intelligible speech,
return an empty utterances list.
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
    async def transcribe(
        self, audio: bytes, lang_hint: str, mime_type: str = "audio/webm"
    ) -> Transcript: ...


class STTUnavailable(RuntimeError):
    """No key, rate limited, network down, or an unparseable response.
    Callers fall back to the golden-path cache rather than showing an error."""


class GeminiSTT:
    """Transcribes English / Telugu / Hindi audio via Gemini.

    Constructing it never raises, so the app boots without a key."""

    def __init__(self, model: str = GEMINI_MODEL) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model_name = model

    async def transcribe(
        self, audio: bytes, lang_hint: str, mime_type: str = "audio/webm"
    ) -> Transcript:
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

        from google import genai  # imported only here, per CLAUDE.md
        from google.genai import types

        from app.providers.llm import parse_structured

        from pydantic import BaseModel

        class _Utterance(BaseModel):
            start_s: float
            text: str
            text_original: str | None = None

        class _RawTranscript(BaseModel):
            language_detected: str = lang_hint
            utterances: list[_Utterance] = []

        client = genai.Client(api_key=self.api_key)
        prompt = TRANSCRIBE_PROMPT.format(language=LANGUAGE_NAMES.get(lang_hint, "English"))

        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self.model_name,
                    contents=[
                        prompt,
                        types.Part.from_bytes(data=audio, mime_type=mime_type),
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=_RawTranscript.model_json_schema(),
                    ),
                ),
                timeout=LIVE_CALL_TIMEOUT_S,
            )
        except TimeoutError as exc:
            raise STTUnavailable(f"Gemini STT call timed out after {LIVE_CALL_TIMEOUT_S}s") from exc
        except Exception as exc:  # rate limit, network, safety block
            raise STTUnavailable(f"Gemini STT call failed: {exc}") from exc

        try:
            parsed = (
                _RawTranscript.model_validate(response.parsed)
                if response.parsed is not None
                else parse_structured(response.text or "", _RawTranscript)
            )
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


class OpenRouterSTT:
    """Transcribes audio via OpenRouter's OpenAI-compatible `chat/completions`
    endpoint, using the `input_audio` content-part convention (works for any
    OpenRouter-hosted model that accepts audio input, e.g. `google/gemini-3.6-flash`).

    Same contract as `GeminiSTT`: constructing it never raises, `.transcribe()`
    raises `STTUnavailable` on any failure so callers fall back to the
    golden-path cache exactly as they do for Gemini."""

    def __init__(self, model: str = OPENROUTER_STT_MODEL) -> None:
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.model_name = model

    async def transcribe(
        self, audio: bytes, lang_hint: str, mime_type: str = "audio/webm"
    ) -> Transcript:
        from app.providers.llm import OPENROUTER_BASE_URL, LIVE_CALL_TIMEOUT_S, fixture_mode, parse_structured, schema_instruction

        if fixture_mode():
            raise STTUnavailable(
                "SANJEEVANI_FIXTURE_MODE is set — serving from the golden-path cache, no live call attempted."
            )
        if not self.api_key:
            raise STTUnavailable(
                "OPENROUTER_API_KEY not set — no live transcription is possible in this environment."
            )
        if not audio:
            raise STTUnavailable("No audio bytes received.")

        import base64

        import httpx  # imported only here, mirrors the google.genai isolation above

        from pydantic import BaseModel

        class _Utterance(BaseModel):
            start_s: float
            text: str
            text_original: str | None = None

        class _RawTranscript(BaseModel):
            language_detected: str = lang_hint
            utterances: list[_Utterance] = []

        prompt = TRANSCRIBE_PROMPT.format(language=LANGUAGE_NAMES.get(lang_hint, "English"))
        audio_format = _AUDIO_FORMAT_FROM_MIME.get(mime_type, mime_type.split("/")[-1])
        audio_b64 = base64.b64encode(audio).decode("ascii")

        try:
            async with httpx.AsyncClient(timeout=LIVE_CALL_TIMEOUT_S) as client:
                response = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model_name,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"{prompt}\n\n{schema_instruction(_RawTranscript)}"},
                                    {
                                        "type": "input_audio",
                                        "input_audio": {"data": audio_b64, "format": audio_format},
                                    },
                                ],
                            }
                        ],
                        # gpt-audio-mini rejects response_format=json_object when the
                        # request includes audio input (400 "not supported with this
                        # model") — the prompt's own JSON instruction plus
                        # parse_structured's defensive fence-stripping cover this.
                    },
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise STTUnavailable(f"OpenRouter STT call timed out after {LIVE_CALL_TIMEOUT_S}s") from exc
        except Exception as exc:  # rate limit, network, safety block
            raise STTUnavailable(f"OpenRouter STT call failed: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise STTUnavailable(f"OpenRouter returned an unexpected shape: {data!r}") from exc

        try:
            parsed = parse_structured(content or "", _RawTranscript)
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
    """Stubbed local-model implementation — kept as the documented seam name
    from architecture.md §10. Superseded by `FasterWhisperSTT` below, which is
    the actually-wired local implementation (faster-whisper/CTranslate2
    instead of a whisper.cpp binary, for a pip-installable Windows setup)."""

    async def transcribe(
        self, audio: bytes, lang_hint: str, mime_type: str = "audio/webm"
    ) -> Transcript:
        raise NotImplementedError(
            "WhisperCppSTT is a documented seam, not wired in this build — see FasterWhisperSTT."
        )


WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "large-v3-turbo")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

_whisper_model = None  # lazy singleton — loading is expensive, do it once per process


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel  # imported only here, mirrors provider isolation above

        _whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE
        )
    return _whisper_model


class FasterWhisperSTT:
    """Local, fully offline ASR via faster-whisper (CTranslate2) — the wired
    implementation of the seam `WhisperCppSTT` documents. No API key, no
    network call, for the transcription step itself.

    Whisper only does ASR (native-language transcript + timestamps); it does
    not reliably produce *both* a native transcript and an English
    translation in one pass the way the Gemini/OpenRouter providers do. Since
    downstream extraction/attribution (specs.md §3) expects `text` in
    English, a short follow-up call to an `LLMProvider` translates the
    batched utterances after ASR. Pass `translator=None` to use the default
    `OpenRouterLLM()` (same key/model as the rest of the app)."""

    def __init__(self, model_size: str = WHISPER_MODEL_SIZE, translator: object | None = None) -> None:
        self.model_size = model_size
        self._translator = translator

    async def transcribe(
        self, audio: bytes, lang_hint: str, mime_type: str = "audio/webm"
    ) -> Transcript:
        from app.providers.llm import fixture_mode

        if fixture_mode():
            raise STTUnavailable(
                "SANJEEVANI_FIXTURE_MODE is set — serving from the golden-path cache, no live call attempted."
            )
        if not audio:
            raise STTUnavailable("No audio bytes received.")

        try:
            segments, detected = await asyncio.to_thread(self._run_whisper, audio, lang_hint)
        except Exception as exc:
            raise STTUnavailable(f"Local Whisper transcription failed: {exc}") from exc

        if not segments:
            return Transcript(segments=[], language_detected=detected)

        texts_en = await self._translate(segments, detected)

        return Transcript(
            segments=[
                TranscriptSegment(text=en, start_s=start, text_original=native)
                for (start, native), en in zip(segments, texts_en)
            ],
            language_detected=detected,
        )

    def _run_whisper(self, audio: bytes, lang_hint: str) -> tuple[list[tuple[float, str]], str]:
        import io

        model = _get_whisper_model()
        language = lang_hint if lang_hint in LANGUAGE_NAMES else None
        # vad_filter=True (Silero VAD, bundled with faster-whisper/onnxruntime,
        # no extra download): strips non-speech before decoding. Without it,
        # silence/noise gets decoded into plausible-looking filler phrases
        # ("Thank you.") from Whisper's training data — confirmed in live
        # testing against a pure-silence clip.
        raw_segments, info = model.transcribe(
            io.BytesIO(audio), language=language, task="transcribe", vad_filter=True
        )
        out = [(seg.start, seg.text.strip()) for seg in raw_segments if seg.text.strip()]
        detected = info.language if info.language in LANGUAGE_NAMES else (lang_hint or "en")
        return out, detected

    async def _translate(self, segments: list[tuple[float, str]], detected_lang: str) -> list[str]:
        native_texts = [text for _, text in segments]
        if detected_lang == "en":
            return native_texts

        from pydantic import BaseModel

        from app.providers.llm import LLMUnavailable, OpenRouterLLM

        translator = self._translator or OpenRouterLLM()

        class _Translation(BaseModel):
            translations: list[str]

        prompt = (
            "Translate each of the following utterances (in "
            f"{LANGUAGE_NAMES.get(detected_lang, detected_lang)}) into plain English, faithfully "
            "and without adding, omitting, or interpreting anything. Return exactly one "
            "translation per utterance, in the same order.\n\n"
            + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(native_texts))
        )
        try:
            result = await translator.complete(prompt, _Translation)
        except LLMUnavailable as exc:
            raise STTUnavailable(f"Whisper transcript produced but translation failed: {exc}") from exc

        translations = result.translations
        if len(translations) != len(native_texts):
            raise STTUnavailable(
                f"Translation count mismatch: {len(translations)} translations for {len(native_texts)} utterances"
            )
        return translations
