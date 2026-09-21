"""Phase 4 — consultation pipeline tests.

All run without a live Neo4j and without a Gemini key, same as test_seed.py:
the trigger engine and the normaliser are pure, and the golden-path cache is a
file on disk.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from app.agents.attribution import TurnLabel, apply_labels, segments_to_turns
from app.agents.extraction import ExtractedPainPoint, canonicalise
from app.agents.normalise import resolve_symptom
from app.agents.triggers import detect_red_flags, red_flag_slugs
from app.providers import cache
from app.providers.llm import parse_structured, strip_fences
from app.providers.stt import Transcript, TranscriptSegment

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The Gemini SDK package. Only modules under backend/app/providers/ may import it.
GEMINI_SDK = "google.generativeai"


# --- red-flag trigger engine (table-driven, per CLAUDE.md testing conventions) ---

@pytest.mark.parametrize(
    "symptoms,expected",
    [
        ([], []),
        (["cough", "fatigue", "weight_loss"], []),
        (["facial_droop"], ["facial_droop"]),
        (["cough", "facial_droop", "night_sweats"], ["facial_droop"]),
        (["FACIAL_DROOP"], ["facial_droop"]),  # case-insensitive
        (["facial droop"], []),  # not a canonical slug -> never escalates
        (None, []),
        (["burning in my feet"], []),  # unmapped free text never escalates
    ],
)
def test_red_flag_table(symptoms, expected):
    assert red_flag_slugs(symptoms) == expected


def test_red_flag_carries_escalation_copy_without_diagnosis_language():
    flags = detect_red_flags(["facial_droop"])
    assert len(flags) == 1
    flag = flags[0]
    assert flag.feature == "facial_asymmetry"
    assert "screening" in flag.message.lower()
    lowered = flag.message.lower()
    for banned in ("diagnos", " has ", "confirmed stroke"):
        assert banned not in lowered


def test_golden_path_symptoms_produce_no_red_flags():
    slugs = [p["canonical"] for p in cache.golden_extract()["pain_points"]]
    assert red_flag_slugs(slugs) == []


# --- symptom normalisation via symptom_aliases.csv --------------------------

GOLDEN_SLUGS = ["cough", "chest_tightness", "fatigue", "night_sweats", "weight_loss"]


def test_every_golden_path_pain_point_resolves_to_a_canonical_slug():
    """specs.md §1: all five must resolve or the golden path is broken."""
    points = cache.golden_extract()["pain_points"]
    assert len(points) == 5
    for p in points:
        assert p["canonical"] is not None, f"{p['symptom']} did not resolve"
        assert resolve_symptom(p["symptom"]) == p["canonical"]
    assert [p["canonical"] for p in points] == GOLDEN_SLUGS


def test_golden_path_verbatim_phrases_resolve_through_the_alias_file():
    for p in cache.golden_extract()["pain_points"]:
        assert resolve_symptom(p["verbatim"]) == p["canonical"]


def test_cough_duration_is_captured_for_the_ntep_screening_rule():
    cough = next(p for p in cache.golden_extract()["pain_points"] if p["canonical"] == "cough")
    assert cough["duration_days"] == 21  # >= the 14-day NTEP presumptive-TB trigger


def test_unresolvable_term_stays_unmapped_and_never_invents_a_slug():
    assert resolve_symptom("burning in my feet") is None
    assert resolve_symptom("") is None
    assert resolve_symptom(None) is None


def test_canonicalise_carries_unmapped_text_and_collapses_duplicates():
    rows = canonicalise(
        [
            ExtractedPainPoint(symptom="cough", confidence=0.6, verbatim="a cough"),
            ExtractedPainPoint(symptom="persistent cough", confidence=0.9, verbatim="it does not go"),
            ExtractedPainPoint(symptom="burning in my feet", confidence=0.7, verbatim="my feet burn"),
        ]
    )
    assert len(rows) == 2
    cough = next(r for r in rows if r["canonical"] == "cough")
    assert cough["confidence"] == 0.9  # highest-confidence entry wins
    assert cough["unmapped_text"] is None
    unmapped = next(r for r in rows if r["canonical"] is None)
    assert unmapped["unmapped_text"] == "burning in my feet"


# --- content-based speaker attribution --------------------------------------

def test_attribution_is_content_based_and_falls_back_deterministically():
    transcript = Transcript(
        segments=[
            TranscriptSegment(text="What is troubling you?", start_s=0.0),
            TranscriptSegment(text="I have had a cough.", start_s=3.0),
        ],
        language_detected="te",
    )
    apply_labels(transcript, [])  # no LLM labels -> heuristic
    turns = segments_to_turns(transcript)
    assert turns[0]["speaker"] == "officer"  # asks a question
    assert turns[1]["speaker"] == "person"


def test_attribution_applies_llm_labels_in_order():
    transcript = Transcript(
        segments=[
            TranscriptSegment(text="Sometimes at night.", start_s=0.0),
            TranscriptSegment(text="Fever?", start_s=2.0),
        ]
    )
    apply_labels(
        transcript,
        [TurnLabel(index=0, speaker="person"), TurnLabel(index=1, speaker="officer")],
    )
    assert [s.speaker for s in transcript.segments] == ["person", "officer"]


# --- golden-path cache ------------------------------------------------------

def test_golden_path_cache_matches_the_demo_script_and_not_arbitrary_text():
    assert cache.matches_golden_path(cache.golden_transcript_text())
    assert not cache.matches_golden_path("My knee hurts after a fall last Tuesday.")
    assert not cache.matches_golden_path("")


def test_golden_path_transcript_is_attributed_and_bilingual():
    turns = cache.golden_transcribe()["turns"]
    assert cache.golden_transcribe()["language_detected"] == "te"
    assert {t["speaker"] for t in turns} == {"officer", "person"}
    assert all(t["text_original"] for t in turns), "screen 6 renders an original-language line"
    assert turns[0]["speaker"] == "officer"


# --- structured-output parsing ----------------------------------------------

def test_strip_fences_handles_markdown_and_prose_wrapping():
    assert json.loads(strip_fences('```json\n{"a": 1}\n```')) == {"a": 1}
    assert json.loads(strip_fences('```\n{"a": 1}\n```')) == {"a": 1}
    assert json.loads(strip_fences('Here you go: {"a": 1} hope that helps')) == {"a": 1}


def test_parse_structured_raises_a_clear_error_on_non_json():
    from app.agents.extraction import ExtractionResult

    with pytest.raises(ValueError, match="did not return JSON"):
        parse_structured("I cannot help with that.", ExtractionResult)


# --- structural check -------------------------------------------------------

def test_only_providers_may_import_the_gemini_sdk():
    """Mirrors test_seed.py's 'no api/ module imports graph.seed' check.

    CLAUDE.md: "Never import google.generativeai outside providers/"."""
    app_dir = REPO_ROOT / "backend" / "app"
    providers_dir = app_dir / "providers"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if providers_dir in path.parents or path.parent == providers_dir:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(a.name.startswith(GEMINI_SDK) for a in node.names):
                    offenders.append(str(path))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(GEMINI_SDK):
                    offenders.append(str(path))
    assert not offenders, f"{GEMINI_SDK} may only be imported inside app/providers/: {offenders}"
