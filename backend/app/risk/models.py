"""Risk model wrappers (architecture.md §9): anemia, COPD, hypertension, CKD.

**Decision (2026-09-21, see progress.md Open questions):** no public dataset
for any of the four risk models was confirmed by Phase 6, and this sandbox has
no internet access to source or validate one. Per progress.md's own
pre-approved fallback, every model below is a **documented, rule-based
scorer** — not a trained scikit-learn artifact — restricted to exactly the
phone-capturable features architecture.md §9 lists. This is disclosed, not
hidden: every output carries `basis` (what combination of inputs produced the
score), a `metric` string naming the fact that no trained-model accuracy
figure exists, and the literal string "screening signal, not a diagnosis".

If a public dataset is sourced later (UCI CKD, a published anemia/COPD/HTN
cohort), swap the scorer body for a pickled artifact behind the same
function signature — `agents/synthesis.py` and the report only depend on the
returned dict shape.

Every function is pure: floats/bools/strings in, a dict out. No I/O.
"""

from __future__ import annotations

SCREENING_DISCLAIMER = "screening signal, not a diagnosis"
RULE_BASED_METRIC = "rule-based scorer — no trained-model accuracy metric; see progress.md Open questions"


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def anemia_risk(pallor_score: float, heart_rate: float, fatigue_reported: bool, gender: str) -> dict:
    """Anemia screening signal from pallor + compensatory tachycardia + reported
    fatigue + gender (women have a lower normal Hb threshold — a documented
    epidemiological fact, not an invented rule). Never estimates haemoglobin
    (CLAUDE.md rule 3) — pallor_score is the camera-derived proxy from
    rppg/pipeline.py's passive findings."""
    score = 0.5 * _clamp(pallor_score)
    if heart_rate > 90:
        score += 0.2 * _clamp((heart_rate - 90) / 40)
    if fatigue_reported:
        score += 0.2
    if gender == "female":
        score += 0.1
    score = _clamp(score)
    return {
        "name": "anemia_risk",
        "score": round(score, 2),
        "metric": RULE_BASED_METRIC,
        "basis": "0.5x pallor_score + tachycardia term (HR>90) + 0.2 if fatigue reported + 0.1 for female sex",
        "inputs": ["pallor_score", "heart_rate", "fatigue"],
        "disclaimer": SCREENING_DISCLAIMER,
    }


def copd_risk(age: int, respiration_rate: float, spo2: float, biomass_exposure: bool, cough_duration_days: int) -> dict:
    """COPD screening signal from age, elevated respiration, low-normal SpO2,
    biomass-smoke exposure (a documented rural-India COPD risk factor,
    architecture.md §5.2) and chronic cough duration."""
    score = 0.0
    if age >= 40:
        score += 0.15 * _clamp((age - 40) / 40)
    if respiration_rate > 20:
        score += 0.25 * _clamp((respiration_rate - 20) / 15)
    if spo2 < 95:
        score += 0.25 * _clamp((95 - spo2) / 15)
    if biomass_exposure:
        score += 0.2
    if cough_duration_days >= 21:
        score += 0.15
    score = _clamp(score)
    return {
        "name": "copd_risk",
        "score": round(score, 2),
        "metric": RULE_BASED_METRIC,
        "basis": "age + elevated RR + low SpO2 + biomass exposure + chronic cough duration, each weighted",
        "inputs": ["age", "respiration_rate", "spo2", "biomass_exposure", "cough_duration_days"],
        "disclaimer": SCREENING_DISCLAIMER,
    }


def hypertension_risk(age: int, bmi: float | None, bp_trend: str, hr_variability: float) -> dict:
    """Hypertension screening signal from age, BMI (if height/weight entered),
    the rPPG-derived BP *trend direction* (never an mmHg value — CLAUDE.md
    rule 2) and heart-rate variability."""
    score = 0.0
    if age >= 45:
        score += 0.2 * _clamp((age - 45) / 35)
    if bmi is not None and bmi >= 25:
        score += 0.2 * _clamp((bmi - 25) / 15)
    if bp_trend == "elevated":
        score += 0.4
    elif bp_trend == "low":
        score -= 0.1
    score += 0.1 * _clamp(hr_variability)
    score = _clamp(score)
    return {
        "name": "hypertension_risk",
        "score": round(score, 2),
        "metric": RULE_BASED_METRIC,
        "basis": "age + BMI (if available) + BP trend direction (elevated adds, low subtracts) + HR variability",
        "inputs": ["age", "bmi", "bp_trend", "hr_variability"],
        "disclaimer": SCREENING_DISCLAIMER,
    }


def ckd_risk(features: dict) -> dict:
    """CKD screening signal restricted to the phone-capturable subset of the
    UCI CKD feature set architecture.md §9 names: age, hypertension flag,
    reported diabetes, and pallor (a documented CKD-anemia correlate) — no
    serum creatinine or urinalysis, which the phone cannot capture."""
    age = features.get("age", 0)
    hypertensive = bool(features.get("hypertensive", False))
    diabetic = bool(features.get("diabetic", False))
    pallor_score = features.get("pallor_score", 0.0)
    score = 0.0
    if age >= 50:
        score += 0.15 * _clamp((age - 50) / 30)
    if hypertensive:
        score += 0.3
    if diabetic:
        score += 0.3
    score += 0.15 * _clamp(pallor_score)
    score = _clamp(score)
    return {
        "name": "ckd_risk",
        "score": round(score, 2),
        "metric": RULE_BASED_METRIC,
        "basis": "age + hypertension flag + diabetes flag + pallor, restricted to the UCI CKD "
                 "feature set's phone-capturable fields",
        "inputs": ["age", "hypertensive", "diabetic", "pallor_score"],
        "disclaimer": SCREENING_DISCLAIMER,
    }


def run_all(session_vitals: dict, pain_points: list[dict], age: int, gender: str) -> list[dict]:
    """Convenience entry point for the synthesis job: runs every model whose
    inputs are available from the session, silently skipping ones missing a
    required capture (e.g. no height/weight entered for BMI)."""
    reported = {p.get("canonical") for p in pain_points if p.get("canonical")}
    results: list[dict] = []

    pallor = session_vitals.get("pallor_score")
    hr = session_vitals.get("heart_rate")
    if pallor is not None and hr is not None:
        results.append(anemia_risk(pallor, hr, "fatigue" in reported, gender))

    rr = session_vitals.get("respiration_rate")
    spo2 = session_vitals.get("spo2")
    if rr is not None and spo2 is not None:
        cough_days = next((p.get("duration_days") or 0 for p in pain_points if p.get("canonical") == "cough"), 0)
        results.append(copd_risk(age, rr, spo2, session_vitals.get("biomass_exposure", False), cough_days))

    bp_trend = session_vitals.get("bp_trend")
    if bp_trend is not None:
        results.append(hypertension_risk(age, session_vitals.get("bmi"), bp_trend, session_vitals.get("hr_variability", 0.3)))

    if pallor is not None:
        results.append(
            ckd_risk(
                {
                    "age": age,
                    "hypertensive": bp_trend == "elevated",
                    "diabetic": "type_2_diabetes" in reported,
                    "pallor_score": pallor,
                }
            )
        )
    return results
