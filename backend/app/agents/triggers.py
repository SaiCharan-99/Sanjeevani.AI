"""Second-look trigger engine (architecture.md §8). Deterministic, table-driven —
not an LLM decision. Pure functions: symptom slugs in, feature/escalation list out.

`TRIGGER_TABLE` mirrors architecture.md §8 exactly, including priority ordering.
Priority 0 is reserved for **red flags**: findings that interrupt the flow and
escalate immediately, regardless of anything else in the pipeline. Today
`facial_droop` is the only priority-0 row — it is the only escalation the
documented clinical sources (architecture.md §8, specs.md §5 `facial_asymmetry`)
support. Nothing else was invented here; see progress.md → Open questions.

`propose_features` (the full second-look proposal) is Phase 5. `detect_red_flags`
is wired now because `POST /api/consult/extract` returns `red_flags`.
"""

from __future__ import annotations

from dataclasses import dataclass

TRIGGER_TABLE = [
    {"symptoms": ["facial_droop"], "feature": "facial_asymmetry", "priority": 0},  # highest
    {"symptoms": ["chest pain", "breathlessness", "cough"], "feature": "chest_rise_respiration", "priority": 1},
    {"symptoms": ["chest pain", "breathlessness", "cough"], "feature": "lip_cyanosis", "priority": 1},
    {"symptoms": ["limb_pain", "injury"], "feature": "swelling_asymmetry", "priority": 2},
    {"symptoms": ["limb_pain", "injury"], "feature": "guided_range_of_motion", "priority": 2},
    {"symptoms": ["fatigue", "weakness", "dizziness"], "feature": "pallor_check", "priority": 3},
    {"symptoms": ["jaundice_signs", "dark_urine"], "feature": "sclera_colour", "priority": 3},
    {"symptoms": ["back_pain", "neck_pain"], "feature": "posture_assessment", "priority": 4},
    {"symptoms": ["difficulty_walking"], "feature": "gait_balance", "priority": 4},
    {"symptoms": ["disorientation"], "feature": "blink_rate_tremor", "priority": 4},
]

#: Officer-facing escalation copy per red-flag symptom. Screening language only —
#: never a diagnosis (rule 1).
RED_FLAG_COPY = {
    "facial_droop": (
        "Facial droop reported — stroke screening takes priority. "
        "Escalate now; do not wait for the rest of the assessment."
    ),
}


@dataclass(frozen=True)
class RedFlag:
    symptom: str
    feature: str
    message: str


def _normalise(slugs: list[str] | None) -> list[str]:
    return [s.strip().lower() for s in (slugs or []) if s and s.strip()]


def detect_red_flags(reported_symptoms: list[str] | None) -> list[RedFlag]:
    """Pure, table-driven. Any priority-0 trigger whose symptom is present
    escalates immediately, independent of the rest of the pipeline.

    Input is canonical `:KB:Symptom` slugs (post-normalisation). Unknown or
    unmapped terms never escalate — a red flag must come from the table."""
    present = set(_normalise(reported_symptoms))
    flags: list[RedFlag] = []
    for rule in TRIGGER_TABLE:
        if rule["priority"] != 0:
            continue
        for symptom in rule["symptoms"]:
            if symptom in present:
                flags.append(
                    RedFlag(
                        symptom=symptom,
                        feature=rule["feature"],
                        message=RED_FLAG_COPY.get(
                            symptom, f"{symptom} reported — escalate for officer review."
                        ),
                    )
                )
    return flags


def red_flag_slugs(reported_symptoms: list[str] | None) -> list[str]:
    """`red_flags` as specs.md §3 shapes it: a list of canonical slugs."""
    return [f.symptom for f in detect_red_flags(reported_symptoms)]


#: Officer-facing capture instructions per feature (specs.md §5). Positioning /
#: timing copy only — never a clinical claim.
FEATURE_INSTRUCTIONS = {
    "facial_asymmetry": (
        "Ask the person to smile and raise their eyebrows, facing the camera "
        "directly. Hold steady for 15 seconds."
    ),
    "chest_rise_respiration": (
        "Ask the person to sit sideways, about 1.5m from the camera, and "
        "breathe normally for 20 seconds."
    ),
    "lip_cyanosis": (
        "Frame the face close, in even light, for 10 seconds without talking."
    ),
    "swelling_asymmetry": (
        "Frame both limbs (or both sides of the affected region) together, "
        "still, for 10 seconds."
    ),
    "guided_range_of_motion": (
        "Ask the person to raise the affected arm to shoulder height, then "
        "rotate the wrist, staying in frame throughout."
    ),
    "pallor_check": (
        "Frame the face close, in even light, eyes open, for 10 seconds."
    ),
    "sclera_colour": (
        "Ask the person to look directly at the camera and open their eyes "
        "wide for 10 seconds."
    ),
    "posture_assessment": (
        "Ask the person to stand side-on to the camera, in their normal "
        "posture, for 15 seconds."
    ),
    "gait_balance": (
        "Ask the person to walk toward the camera for 3-4 steps, with the "
        "full body in frame."
    ),
    "blink_rate_tremor": (
        "Frame the face steady for 20 seconds while the person sits quietly."
    ),
}

#: priority-number -> officer-facing band. 0/1 are the highest-value signals
#: (0 is the stroke red flag, 1 is the golden-path respiratory pair); 2/3 are
#: secondary; 4 is exploratory. Judgment call, not specified in architecture.md
#: §8 — logged in progress.md Decisions log.
_PRIORITY_LABELS = {0: "high", 1: "high", 2: "medium", 3: "medium", 4: "low"}


def _rationale(feature: str, matched: list[str], priority: int) -> str:
    """A sentence naming the actual triggering symptoms present this session
    (specs.md §2 screen 10: 'rationale quoting the triggering symptoms')."""
    quoted = ", ".join(m.replace("_", " ") for m in matched)
    if feature == "facial_asymmetry":
        return f"Facial droop reported — stroke screening takes priority over the rest of the assessment."
    readable_feature = feature.replace("_", " ")
    return f"Reported {quoted} makes {readable_feature} the highest-value next signal."


def propose_features(reported_symptoms: list[str]) -> list[dict]:
    """Table-driven, deterministic (architecture.md §8). Ranked by
    `TRIGGER_TABLE` priority (0 = highest, always first — the facial-asymmetry
    red flag). Each proposal names the actual triggering symptoms present in
    this session, never a generic sentence.

    Input: canonical `:KB:Symptom` slugs already resolved for this session
    (Tier 1 `SessionState.pain_points` canonical values). Output: ranked list
    of dicts matching `SecondLookSuggestion`.
    """
    present = set(_normalise(reported_symptoms))
    proposals: list[dict] = []
    seen_features: set[str] = set()
    for rule in sorted(TRIGGER_TABLE, key=lambda r: r["priority"]):
        matched = [s for s in rule["symptoms"] if s in present]
        if not matched:
            continue
        feature = rule["feature"]
        if feature in seen_features:
            continue
        seen_features.add(feature)
        proposals.append(
            {
                "feature": feature,
                "priority": _PRIORITY_LABELS.get(rule["priority"], "low"),
                "rationale": _rationale(feature, matched, rule["priority"]),
                "instruction": FEATURE_INSTRUCTIONS.get(
                    feature, "Follow the officer's positioning guidance for this capture."
                ),
                "triggered_by": matched,
            }
        )
    return proposals
