"""Pain-point extraction from a consultation transcript.

Structured output through `LLMProvider.complete` (CLAUDE.md "AI provider
rules"): a Pydantic schema, a prompt that forbids markdown fences, defensive
parsing in `providers/llm.py`.

The LLM **reports what the person said**. It does not diagnose, does not invent
symptoms and does not choose the canonical slug — normalisation against
`symptom_aliases.csv` happens here, in `agents/normalise.py`, after the model
has spoken. An unresolvable term keeps `canonical = None` and is carried as
`unmapped_text` for the officer to map on screen 9.

See specs.md §1 for the golden-path extraction this must reproduce.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.normalise import resolve_symptom
from app.providers.llm import LLMProvider, LLMUnavailable

EXTRACTION_PROMPT = """From the consultation transcript below, list every symptom or
complaint the PERSON reported about themselves.

Rules:
  - Report only what was actually said. Never infer, never add a symptom that was not
    mentioned, never name a disease and never give a diagnosis.
  - Do not include the officer's questions as symptoms.
  - One symptom per entry. When the person lists several complaints in a single
    sentence (e.g. "I have fever, cold and headache"), split it into one entry per
    complaint — never merge them, and never drop any of them.
  - "symptom" is a short everyday English description of THAT ONE complaint only
    (e.g. "exertional chest tightness", "night sweats") — not a summary of everything
    the person said.
  - "duration_days" only when a duration was actually stated; convert to whole days
    (e.g. "two or three weeks" -> 21). Otherwise null.
  - "confidence" is 0.0-1.0: how certain you are the person reported this symptom.
  - "verbatim" is the specific word or phrase for THAT ONE symptom only, copied from
    the transcript — never the whole sentence it came from.
  - "verbatim_original" is the same word or phrase in the original spoken language if
    the transcript carries them, otherwise null.

Transcript:
{transcript}
"""


class ExtractedPainPoint(BaseModel):
    symptom: str
    duration_days: int | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    verbatim: str = ""
    verbatim_original: str | None = None


class ExtractionResult(BaseModel):
    pain_points: list[ExtractedPainPoint] = []


def canonicalise(points: list[ExtractedPainPoint]) -> list[dict]:
    """Resolve each extracted term to a `:KB:Symptom` slug, or carry it as
    `unmapped_text`. Duplicate slugs collapse to the highest-confidence entry."""
    out: list[dict] = []
    seen: dict[str, int] = {}
    for p in points:
        # Only resolve against the LLM's own short paraphrase, never `verbatim`:
        # verbatim can be a whole multi-symptom sentence (observed in testing —
        # the model doesn't reliably scope it to one symptom), and matching
        # against that risks an unrelated symptom's name appearing as a
        # substring and getting silently, wrongly attached here. An unresolved
        # symptom correctly stays `unmapped_text` for officer review instead.
        slug = resolve_symptom(p.symptom)
        record = {
            "symptom": p.symptom,
            "canonical": slug,
            "duration_days": p.duration_days,
            "confidence": round(max(0.0, min(1.0, p.confidence)), 2),
            "verbatim": p.verbatim or p.symptom,
            "verbatim_original": p.verbatim_original,
            "unmapped_text": None if slug else p.symptom,
        }
        if slug and slug in seen:
            existing = out[seen[slug]]
            if record["confidence"] > existing["confidence"]:
                out[seen[slug]] = record
            continue
        if slug:
            seen[slug] = len(out)
        out.append(record)
    return out


async def extract_pain_points(llm: LLMProvider, transcript_text: str) -> list[dict]:
    """Run the extraction pass and canonicalise the result.

    Raises `LLMUnavailable` so the caller can decide to serve the golden-path
    cache instead — this module never fabricates clinical content of its own.
    """
    if not transcript_text.strip():
        return []
    result = await llm.complete(
        EXTRACTION_PROMPT.format(transcript=transcript_text), ExtractionResult
    )
    if not isinstance(result, ExtractionResult):
        raise LLMUnavailable("Extraction returned an unexpected schema.")
    return canonicalise(result.pain_points)
