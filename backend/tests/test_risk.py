"""Phase 6 — rule-based risk scorer tests (risk/models.py). Table-driven: a
higher-risk feature set must never score below a lower-risk one, every output
carries the literal "screening signal, not a diagnosis" disclaimer, and
hypertension_risk never receives/emits an absolute mmHg value (CLAUDE.md
rule 2) while anemia_risk never receives/emits a haemoglobin value
(CLAUDE.md rule 3)."""

from __future__ import annotations

import pytest

from app.risk import models as risk


def test_anemia_risk_increases_with_pallor_and_fatigue():
    low = risk.anemia_risk(pallor_score=0.1, heart_rate=75, fatigue_reported=False, gender="male")
    high = risk.anemia_risk(pallor_score=0.9, heart_rate=110, fatigue_reported=True, gender="female")
    assert high["score"] > low["score"]
    assert 0.0 <= low["score"] <= 1.0
    assert 0.0 <= high["score"] <= 1.0


def test_anemia_risk_never_carries_a_haemoglobin_field():
    out = risk.anemia_risk(pallor_score=0.5, heart_rate=88, fatigue_reported=True, gender="female")
    dumped = str(out).lower()
    assert "hb" not in out
    assert "haemoglobin" not in dumped and "hemoglobin" not in dumped


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pallor_score": 0.2, "heart_rate": 80, "fatigue_reported": False, "gender": "male"},
        {"pallor_score": 0.8, "heart_rate": 100, "fatigue_reported": True, "gender": "female"},
    ],
)
def test_anemia_risk_always_discloses_screening_signal(kwargs):
    out = risk.anemia_risk(**kwargs)
    assert out["disclaimer"] == "screening signal, not a diagnosis"
    assert out["metric"] == risk.RULE_BASED_METRIC  # rule-based — no trained-model accuracy figure
    assert set(out["inputs"]) <= {"pallor_score", "heart_rate", "fatigue"}


def test_copd_risk_increases_with_age_exposure_and_chronic_cough():
    low = risk.copd_risk(age=22, respiration_rate=16, spo2=99, biomass_exposure=False, cough_duration_days=2)
    high = risk.copd_risk(age=60, respiration_rate=26, spo2=90, biomass_exposure=True, cough_duration_days=30)
    assert high["score"] > low["score"]
    assert high["disclaimer"] == "screening signal, not a diagnosis"


def test_hypertension_risk_never_emits_an_mmhg_value():
    """Only a trend string goes in; only a 0..1 score comes out — no absolute
    blood-pressure number anywhere in the output (CLAUDE.md rule 2)."""
    out = risk.hypertension_risk(age=50, bmi=27, bp_trend="elevated", hr_variability=0.4)
    assert isinstance(out["score"], float)
    for value in out.values():
        if isinstance(value, str):
            assert "mmhg" not in value.lower()
    assert out["disclaimer"] == "screening signal, not a diagnosis"


def test_hypertension_risk_trend_direction_changes_score():
    elevated = risk.hypertension_risk(age=50, bmi=25, bp_trend="elevated", hr_variability=0.3)
    low = risk.hypertension_risk(age=50, bmi=25, bp_trend="low", hr_variability=0.3)
    assert elevated["score"] > low["score"]


def test_ckd_risk_restricted_to_phone_capturable_fields():
    out = risk.ckd_risk({"age": 55, "hypertensive": True, "diabetic": True, "pallor_score": 0.6})
    assert set(out["inputs"]) == {"age", "hypertensive", "diabetic", "pallor_score"}
    assert "creatinine" not in out["inputs"]
    assert "gfr" not in [i.lower() for i in out["inputs"]]
    assert out["disclaimer"] == "screening signal, not a diagnosis"


def test_ckd_risk_increases_with_more_risk_flags():
    low = risk.ckd_risk({"age": 30, "hypertensive": False, "diabetic": False, "pallor_score": 0.1})
    high = risk.ckd_risk({"age": 60, "hypertensive": True, "diabetic": True, "pallor_score": 0.7})
    assert high["score"] > low["score"]


def test_run_all_skips_models_missing_required_captures():
    """No vitals captured yet this session -> run_all returns [] rather than
    fabricating a score from missing inputs."""
    results = risk.run_all(session_vitals={}, pain_points=[], age=40, gender="male")
    assert results == []


def test_run_all_produces_golden_path_shaped_output():
    vitals = {
        "pallor_score": 0.4, "heart_rate": 96, "respiration_rate": 22, "spo2": 94,
        "bp_trend": "elevated", "bmi": 24, "hr_variability": 0.3,
    }
    pain_points = [
        {"canonical": "cough", "duration_days": 21, "confidence": 0.95},
        {"canonical": "fatigue", "confidence": 0.88},
    ]
    results = risk.run_all(vitals, pain_points, age=52, gender="male")
    names = {r["name"] for r in results}
    assert {"anemia_risk", "copd_risk", "hypertension_risk", "ckd_risk"} <= names
    for r in results:
        assert r["disclaimer"] == "screening signal, not a diagnosis"
        assert 0.0 <= r["score"] <= 1.0
