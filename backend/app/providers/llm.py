"""LLM provider seam (architecture.md §10).

**Never import `google.generativeai` outside `app/providers/`.** A structural
test in `backend/tests/test_consult.py` enforces this, mirroring the
`no api/ module imports graph.seed` check in `test_seed.py`.

Always request structured output: every caller passes a Pydantic schema, the
prompt instructs the model to return only JSON with no markdown fences, and the
response is parsed defensively (fences stripped as a safety net, first JSON
object extracted if the model wraps it in prose).
"""

from __future__ import annotations

import json
import os
import re
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")


def fixture_mode() -> bool:
    """True when `SANJEEVANI_FIXTURE_MODE` forces every provider call to serve
    from the golden-path cache without attempting a live call at all — "no
    network whatsoever" demo mode (docs/demo.md). Read live (not cached at
    import time) so a test or a pre-demo toggle can flip it without a restart."""
    return os.environ.get("SANJEEVANI_FIXTURE_MODE", "").strip().lower() in ("1", "true", "yes")

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class LLMProvider(Protocol):
    async def complete(self, prompt: str, schema: type[BaseModel]) -> BaseModel: ...


def strip_fences(raw: str) -> str:
    """Defensive JSON cleanup. The prompt says 'no markdown fences'; models
    emit them anyway often enough that this must not be optional."""
    text = (raw or "").strip()
    fenced = _FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    if text.startswith("{") or text.startswith("["):
        return text
    # Model wrapped the JSON in prose — take the outermost object/array.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            return text[start : end + 1]
    return text


def parse_structured(raw: str, schema: type[T]) -> T:
    """Parse a model response into `schema`, raising a clear ValueError rather
    than letting a JSONDecodeError escape into a route handler."""
    cleaned = strip_fences(raw)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM did not return JSON: {raw[:200]!r}") from exc
    return schema.model_validate(payload)


def schema_instruction(schema: type[BaseModel]) -> str:
    return (
        "Return ONLY a single JSON object matching this JSON Schema. "
        "Do not wrap it in markdown fences. Do not add commentary.\n"
        f"{json.dumps(schema.model_json_schema())}"
    )


class GeminiLLM:
    """Structured-output wrapper over the Gemini API.

    Degrades gracefully: constructing it never raises, so the app boots without
    a key. `.complete()` raises `LLMUnavailable` when no key is set or the live
    call fails, and callers decide whether to fall back to the golden-path
    cache (see `providers/cache.py`)."""

    def __init__(self, model: str = GEMINI_MODEL) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model_name = model

    async def complete(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        if fixture_mode():
            raise LLMUnavailable(
                "SANJEEVANI_FIXTURE_MODE is set — serving from the golden-path cache, no live call attempted."
            )
        if not self.api_key:
            raise LLMUnavailable(
                "GEMINI_API_KEY not set — no live LLM call is possible in this environment."
            )
        import google.generativeai as genai  # imported only here, per CLAUDE.md

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model_name)
        try:
            response = await model.generate_content_async(
                f"{prompt}\n\n{schema_instruction(schema)}",
                generation_config={"response_mime_type": "application/json"},
            )
        except Exception as exc:  # rate limit, network, safety block — all the same to callers
            raise LLMUnavailable(f"Gemini call failed: {exc}") from exc
        return parse_structured(response.text, schema)


class LLMUnavailable(RuntimeError):
    """No key, rate limited, network down, or an unparseable response.
    Callers fall back to the golden-path cache rather than showing an error."""


class OllamaLLM:
    """Stubbed local-model implementation.

    Exists to back the offline pitch claim honestly (architecture.md §10): this
    is the seam a local model drops into. Deliberately **not wired** in this
    build — Gemini is required today and the UI must not claim otherwise
    (rule 10)."""

    async def complete(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        raise NotImplementedError(
            "OllamaLLM is a documented seam, not wired in this build (architecture.md §10)."
        )
