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

import asyncio
import json
import os
import re
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-3.6-flash")

ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
ANTHROPIC_VERSION = "2023-06-01"

# Bounds every live LLM call so a slow/rate-limited/hanging request returns
# an explicit error instead of leaving the UI stuck.
LIVE_CALL_TIMEOUT_S = 15.0


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

    Constructing it never raises, so the app boots without a key.
    `.complete()` raises `LLMUnavailable` when no key is set or the live call
    fails. Only explicit fixture mode may substitute golden-path data."""

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
        from google import genai  # imported only here, per CLAUDE.md
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self.model_name,
                    contents=f"{prompt}\n\n{schema_instruction(schema)}",
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema.model_json_schema(),
                    ),
                ),
                timeout=LIVE_CALL_TIMEOUT_S,
            )
        except TimeoutError as exc:
            raise LLMUnavailable(f"Gemini call timed out after {LIVE_CALL_TIMEOUT_S}s") from exc
        except Exception as exc:  # rate limit, network, safety block — all the same to callers
            raise LLMUnavailable(f"Gemini call failed: {exc}") from exc
        if response.parsed is not None:
            return schema.model_validate(response.parsed)
        return parse_structured(response.text or "", schema)


class LLMUnavailable(RuntimeError):
    """No key, rate limited, network down, or an unparseable response.
    Callers fall back to the golden-path cache rather than showing an error."""


class OpenRouterLLM:
    """Structured-output wrapper over OpenRouter's OpenAI-compatible
    `chat/completions` endpoint (https://openrouter.ai/api/v1).

    Same contract as `GeminiLLM`: constructing it never raises, `.complete()`
    raises `LLMUnavailable` on any failure so callers fall back to the
    golden-path cache exactly as they do for Gemini."""

    def __init__(self, model: str = OPENROUTER_MODEL) -> None:
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.model_name = model

    async def complete(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        if fixture_mode():
            raise LLMUnavailable(
                "SANJEEVANI_FIXTURE_MODE is set — serving from the golden-path cache, no live call attempted."
            )
        if not self.api_key:
            raise LLMUnavailable(
                "OPENROUTER_API_KEY not set — no live LLM call is possible in this environment."
            )
        import httpx  # imported only here, mirrors the google.genai isolation above

        try:
            async with httpx.AsyncClient(timeout=LIVE_CALL_TIMEOUT_S) as client:
                response = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "user", "content": f"{prompt}\n\n{schema_instruction(schema)}"}
                        ],
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMUnavailable(f"OpenRouter call timed out after {LIVE_CALL_TIMEOUT_S}s") from exc
        except Exception as exc:  # rate limit, network, safety block — all the same to callers
            raise LLMUnavailable(f"OpenRouter call failed: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMUnavailable(f"OpenRouter returned an unexpected shape: {data!r}") from exc
        return parse_structured(content or "", schema)


class AnthropicLLM:
    """Structured-output wrapper over Anthropic's Messages API
    (https://api.anthropic.com/v1/messages).

    Text-only — Anthropic's API has no audio-input modality, so this can back
    `LLMProvider` (reasoning/extraction/attribution) but never `STTProvider`.
    Same contract as `GeminiLLM`/`OpenRouterLLM`: constructing it never
    raises, `.complete()` raises `LLMUnavailable` on any failure so callers
    fall back to the golden-path cache exactly as they do for the others."""

    def __init__(self, model: str = ANTHROPIC_MODEL) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.model_name = model

    async def complete(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        if fixture_mode():
            raise LLMUnavailable(
                "SANJEEVANI_FIXTURE_MODE is set — serving from the golden-path cache, no live call attempted."
            )
        if not self.api_key:
            raise LLMUnavailable(
                "ANTHROPIC_API_KEY not set — no live LLM call is possible in this environment."
            )
        import httpx  # imported only here, mirrors the google.genai isolation above

        try:
            async with httpx.AsyncClient(timeout=LIVE_CALL_TIMEOUT_S) as client:
                response = await client.post(
                    f"{ANTHROPIC_BASE_URL}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": ANTHROPIC_VERSION,
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model_name,
                        "max_tokens": 4096,
                        "messages": [
                            {"role": "user", "content": f"{prompt}\n\n{schema_instruction(schema)}"}
                        ],
                    },
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMUnavailable(f"Anthropic call timed out after {LIVE_CALL_TIMEOUT_S}s") from exc
        except Exception as exc:  # rate limit, network, safety block — all the same to callers
            raise LLMUnavailable(f"Anthropic call failed: {exc}") from exc

        try:
            content = "".join(
                block.get("text", "") for block in data["content"] if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise LLMUnavailable(f"Anthropic returned an unexpected shape: {data!r}") from exc
        return parse_structured(content, schema)


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
