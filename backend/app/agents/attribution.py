"""Content-based speaker attribution (architecture.md §10, CLAUDE.md).

Gemini's audio-level diarization is not reliable enough, and Swaroop named
content-based attribution as the acceptable path. We send the **plain
transcript text** to the LLM and have it assign each utterance to `officer` or
`person` by who asks questions and who describes what they feel.

There is deliberately no audio-diarization code path anywhere in this codebase.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.providers.llm import LLMUnavailable, LLMProvider
from app.providers.stt import Transcript

ATTRIBUTION_PROMPT = """You are labelling the turns of a transcribed consultation at a
rural health camp in India. There are exactly two speakers:

  - "officer": the medical health officer running the camp. They ASK the questions,
    give instructions, and use clinical vocabulary.
  - "person": the person attending the camp. They ANSWER, and describe what they feel
    in everyday words ("my chest feels tight", "I get tired very fast").

Assign every numbered turn below to exactly one of those two labels. Use the content
and the question/answer structure only — you are not doing voice identification.
Consecutive turns may share a speaker. Do not rewrite, translate, merge, split or
summarise the turns; only label them. Return one entry per input turn, in order,
echoing each turn's index.

Turns:
{turns}
"""


class TurnLabel(BaseModel):
    index: int
    speaker: str = Field(description="officer or person")


class AttributionResult(BaseModel):
    labels: list[TurnLabel] = []


def _fallback_speaker(index: int, text: str) -> str:
    """Deterministic heuristic used when the LLM is unavailable: a question is
    the officer, an answer is the person, otherwise alternate from the top."""
    stripped = (text or "").strip()
    if stripped.endswith("?"):
        return "officer"
    return "person" if index % 2 else "officer"


def apply_labels(transcript: Transcript, labels: list[TurnLabel]) -> Transcript:
    by_index = {l.index: l.speaker for l in labels}
    for i, seg in enumerate(transcript.segments):
        speaker = by_index.get(i, seg.speaker)
        seg.speaker = speaker if speaker in ("officer", "person") else _fallback_speaker(i, seg.text)
    return transcript


async def attribute_speakers(llm: LLMProvider, transcript: Transcript) -> Transcript:
    """Fill in `speaker` on every segment. Never raises — falls back to the
    deterministic heuristic so a rate limit cannot break the consultation."""
    if not transcript.segments:
        return transcript

    numbered = "\n".join(f"{i}. {seg.text}" for i, seg in enumerate(transcript.segments))
    try:
        result = await llm.complete(
            ATTRIBUTION_PROMPT.format(turns=numbered), AttributionResult
        )
        labels = result.labels if isinstance(result, AttributionResult) else []
    except (LLMUnavailable, ValueError, NotImplementedError):
        labels = []

    if not labels:
        labels = [
            TurnLabel(index=i, speaker=_fallback_speaker(i, seg.text))
            for i, seg in enumerate(transcript.segments)
        ]
    return apply_labels(transcript, labels)


def segments_to_turns(transcript: Transcript) -> list[dict]:
    """Shape for `TranscribeResponse.turns` (specs.md §3)."""
    out = []
    for i, seg in enumerate(transcript.segments):
        speaker = seg.speaker if seg.speaker in ("officer", "person") else _fallback_speaker(i, seg.text)
        out.append(
            {
                "speaker": speaker,
                "text": seg.text,
                "text_original": seg.text_original,
                "start_s": seg.start_s,
            }
        )
    return out


def turns_to_transcript_text(turns: list[dict]) -> str:
    return "\n".join(f"{t.get('speaker', 'person')}: {t.get('text', '')}" for t in turns)
