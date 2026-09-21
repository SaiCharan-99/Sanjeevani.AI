"""Golden-path response cache.

A rate limit, a missing key or a flaky venue wifi must not kill the demo. The
exact specs.md §1 Ramesh Kumar consultation (transcription, speaker attribution
and pain-point extraction) is cached on disk and served when:

  * the input matches the golden path (marker phrases present), or
  * a live Gemini call fails for any reason.

Same spirit as `api/kb.py`'s static fallback and `sessionStore.ts`'s golden-path
session id: the fallback is explicit, named and never silently pretends to be a
live result (callers get a `source` flag).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

GOLDEN_PATH_FILE = Path(__file__).resolve().parent / "golden_path.json"

#: how many marker phrases must appear before we treat a transcript as the
#: golden-path script. 3 of 5 tolerates STT wobble without matching arbitrary
#: consultations.
MATCH_THRESHOLD = 3


@lru_cache(maxsize=1)
def load_golden_path() -> dict[str, Any]:
    with open(GOLDEN_PATH_FILE, encoding="utf-8") as f:
        return json.load(f)


def matches_golden_path(text: str) -> bool:
    """True when `text` is (close enough to) the specs.md §1 demo script."""
    if not text:
        return False
    lowered = text.lower()
    markers = load_golden_path().get("match_markers", [])
    hits = sum(1 for m in markers if m.lower() in lowered)
    return hits >= MATCH_THRESHOLD


def golden_transcribe() -> dict[str, Any]:
    return load_golden_path()["transcribe"]


def golden_extract() -> dict[str, Any]:
    return load_golden_path()["extract"]


def golden_transcript_text() -> str:
    """The cached transcript as plain text — used as the extraction input when
    the demo runs without a live STT call."""
    turns = golden_transcribe()["turns"]
    return "\n".join(f"{t['speaker']}: {t['text']}" for t in turns)
