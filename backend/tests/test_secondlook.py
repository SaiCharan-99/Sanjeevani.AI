"""Phase 5 — second-look trigger engine and feature-processing tests.
Table-driven, same style as test_consult.py; run without a live Neo4j or
Gemini key (the trigger engine and the feature functions are pure)."""

from __future__ import annotations

import pytest

from app.agents.secondlook_features import chest_rise_respiration, cross_check_rr, facial_asymmetry
from app.agents.triggers import propose_features


# --- propose_features: table-driven, symptom set in, expected feature list out ---

@pytest.mark.parametrize(
    "symptoms,expected_features",
    [
        ([], []),
        (["cough"], ["chest_rise_respiration", "lip_cyanosis"]),
        (["fatigue"], ["pallor_check"]),
        (["facial_droop"], ["facial_asymmetry"]),
        (["facial_droop", "cough", "fatigue"], ["facial_asymmetry", "chest_rise_respiration", "lip_cyanosis", "pallor_check"]),
        (["limb_pain"], ["swelling_asymmetry", "guided_range_of_motion"]),
        (["difficulty_walking"], ["gait_balance"]),
        (["disorientation"], ["blink_rate_tremor"]),
        (["jaundice_signs"], ["sclera_colour"]),
        (["back_pain"], ["posture_assessment"]),
        (["unrelated_symptom_not_in_table"], []),
    ],
)
def test_propose_features_table_driven(symptoms, expected_features):
    proposals = propose_features(symptoms)
    assert [p["feature"] for p in proposals] == expected_features


def test_facial_asymmetry_is_always_first_and_highest_priority():
    proposals = propose_features(["cough", "fatigue", "facial_droop", "limb_pain"])
    assert proposals[0]["feature"] == "facial_asymmetry"
    assert proposals[0]["priority"] == "high"


def test_every_proposal_carries_rationale_and_instruction_and_triggered_by():
    for proposals in (
        propose_features(["cough"]),
        propose_features(["fatigue"]),
        propose_features(["facial_droop"]),
    ):
        for p in proposals:
            assert p["rationale"]
            assert p["instruction"]
            assert p["triggered_by"]
            assert set(p["triggered_by"]).issubset({"cough", "fatigue", "facial_droop"})


def test_rationale_quotes_the_actual_triggering_symptom():
    proposals = propose_features(["cough"])
    assert any("cough" in p["rationale"] for p in proposals)


def test_golden_path_symptom_set_proposes_chest_rise_first():
    """The golden-path Ramesh Kumar consultation reports cough, chest_tightness,
    fatigue, night_sweats, weight_loss (specs.md §1) — the demo's 'agent
    proposes chest-rise capture' beat must come out of exactly this table."""
    proposals = propose_features(["cough", "chest_tightness", "fatigue", "night_sweats", "weight_loss"])
    assert proposals[0]["feature"] == "chest_rise_respiration"


# --- feature processing: pure, landmark series in, finding dict out ---

def _shoulder_frames(n=300, fs=15.0, brpm=18.0):
    """Synthetic pose frames: shoulder midpoint oscillating at `brpm` breaths/min."""
    import math

    frames = []
    freq_hz = brpm / 60.0
    for i in range(n):
        t = i / fs
        y = 0.5 + 0.02 * math.sin(2 * math.pi * freq_hz * t)
        frames.append({"t": t, "pose": {"11": [0.4, y, 0.0], "12": [0.6, y, 0.0]}})
    return frames


def test_chest_rise_respiration_recovers_approximate_rate():
    frames = _shoulder_frames(brpm=18.0)
    finding = chest_rise_respiration(frames)
    assert finding["feature"] == "chest_rise_respiration"
    assert 10.0 <= finding["value"] <= 26.0  # coarse zero-crossing counter, generous tolerance
    assert finding["confidence"] > 0.0
    assert "limitations" in finding and finding["limitations"]


def test_chest_rise_respiration_too_few_frames_is_low_confidence():
    finding = chest_rise_respiration([{"t": 0.0, "pose": {"11": [0.4, 0.5, 0.0]}}])
    assert finding["confidence"] <= 0.1


def test_cross_check_lowers_confidence_on_disagreement():
    frames = _shoulder_frames(brpm=18.0)
    finding = chest_rise_respiration(frames, rppg_rr_bpm=40.0, rppg_rr_quality=0.9)
    # Large disagreement (rPPG says 40, chest-rise says ~18) must lower the
    # chest-rise confidence and the rPPG-side quality (Task 3, >20% tolerance).
    assert finding["confidence"] < 0.9
    _, adjusted_quality = cross_check_rr(finding, 40.0, 0.9)
    assert adjusted_quality < 0.9


def test_cross_check_agreement_does_not_penalise():
    frames = _shoulder_frames(brpm=18.0)
    finding_no_check = chest_rise_respiration(frames)
    close_rr = finding_no_check["value"]  # exact agreement
    finding = chest_rise_respiration(frames, rppg_rr_bpm=close_rr, rppg_rr_quality=0.9)
    _, adjusted_quality = cross_check_rr(finding, close_rr, 0.9)
    assert adjusted_quality == 0.9


def test_facial_asymmetry_missing_landmarks_is_low_confidence_not_fabricated():
    finding = facial_asymmetry([{"t": 0.0, "face": {}}])
    assert finding["feature"] == "facial_asymmetry"
    assert finding["confidence"] <= 0.1
    assert finding["value"] == 0.0


def test_every_finding_has_required_fields():
    frames = _shoulder_frames()
    finding = chest_rise_respiration(frames)
    for key in ("feature", "value", "unit", "method", "interpretation", "confidence", "limitations"):
        assert key in finding
