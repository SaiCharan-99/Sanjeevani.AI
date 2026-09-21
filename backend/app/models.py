"""Pydantic models for every request/response in specs.md §3.

Naming per CLAUDE.md: Person not Patient, consideration not diagnosis,
finding for observed evidence, symptom for graph-canonical terms.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Gender = Literal["male", "female", "other"]
Language = Literal["en", "te", "hi"]
Tier = Literal["reliable", "approximate", "trend_only", "not_implemented"]
Priority = Literal["high", "medium", "low"]
ReviewStatus = Literal["approved", "pending"]


# --- session -----------------------------------------------------------------

class PersonIn(BaseModel):
    name: str
    age: int = Field(ge=0, le=120)
    gender: Gender
    village: str


class SessionStartRequest(BaseModel):
    person: PersonIn
    language: Language
    consent: bool


class SessionStartResponse(BaseModel):
    session_id: str
    person_id: str


class PendingSession(BaseModel):
    session_id: str
    person_name: str
    status: Literal["queued", "running", "done_unopened"]


class SessionPendingResponse(BaseModel):
    sessions: list[PendingSession]


class SessionSaveRequest(BaseModel):
    """Continuous Tier-2 persistence: one reading at a time, called as each
    vital is captured (architecture.md §6 — a mid-session crash loses nothing)."""

    session_id: str
    vital: str
    value: float
    unit: str
    quality: float = Field(ge=0.0, le=1.0)
    tier: Tier


class SessionSaveResponse(BaseModel):
    reading_id: str


class SessionCompleteRequest(BaseModel):
    session_id: str
    top_findings: list[str] = []
    recommendations: list[str] = []


class SessionCompleteResponse(BaseModel):
    session_id: str
    status: str


class VillageAutocompleteResponse(BaseModel):
    villages: list[str]


# --- vitals --------------------------------------------------------------------

class ROITrace(BaseModel):
    r: list[float]
    g: list[float]
    b: list[float]


class VitalsProcessRequest(BaseModel):
    session_id: str
    fps: int
    duration_s: float
    traces: dict[str, ROITrace]
    motion_score: float
    timestamps: list[float]


class VitalReading(BaseModel):
    value: float
    unit: str
    quality: float = Field(ge=0.0, le=1.0)
    tier: Tier


class BPTrendReading(BaseModel):
    direction: Literal["elevated", "stable", "low"]
    quality: float = Field(ge=0.0, le=1.0)
    tier: Tier = "trend_only"


class PassiveFindings(BaseModel):
    pallor_score: float
    facial_tension: float
    blink_rate: float


class VitalsProcessResponse(BaseModel):
    heart_rate: VitalReading
    respiration_rate: VitalReading
    spo2: VitalReading
    bp_trend: BPTrendReading
    passive_findings: PassiveFindings
    overall_quality: float = Field(ge=0.0, le=1.0)
    retake_recommended: bool


# --- consult ---------------------------------------------------------------

class TranscriptTurn(BaseModel):
    speaker: Literal["officer", "person"]
    text: str
    start_s: float
    #: the same utterance in the session language, when the transcript carries
    #: it. Screen 6 renders the original-language line above the English line.
    #: Extension to the specs.md §3 shape — see progress.md Decisions log.
    text_original: str | None = None


class TranscribeResponse(BaseModel):
    turns: list[TranscriptTurn]
    language_detected: Language
    #: "live" when Gemini answered, "golden_path_cache" when the cached demo
    #: response was served (no key, rate limit, or the golden-path script).
    #: Never rendered as a claim in the UI; used by developer mode.
    source: Literal["live", "golden_path_cache"] = "live"


class PainPoint(BaseModel):
    symptom: str
    canonical: str | None
    duration_days: int | None = None
    confidence: float
    verbatim: str
    verbatim_original: str | None = None
    unmapped_text: str | None = None


class ExtractResponse(BaseModel):
    pain_points: list[PainPoint]
    red_flags: list[str]
    #: officer-facing escalation copy, one per red flag, in the same order.
    #: Screening language only — never a diagnosis (rule 1).
    red_flag_messages: list[str] = []
    source: Literal["live", "golden_path_cache"] = "live"


class PainPointsSaveRequest(BaseModel):
    """Screens 8/9 — the officer's reviewed list replaces the extracted one.
    Human-in-the-loop is a feature, not a fallback (specs.md §2 screen 8).
    Entries the officer added or corrected are attributed to them in the audit
    log via `edited_by`."""

    session_id: str
    pain_points: list[PainPoint]
    edited_by: str = "officer"


class PainPointsSaveResponse(BaseModel):
    session_id: str
    saved: int
    red_flags: list[str] = []


# --- second look --------------------------------------------------------------

class SecondLookSuggestion(BaseModel):
    feature: str
    priority: Priority
    rationale: str
    instruction: str
    triggered_by: list[str]


class SecondLookSuggestResponse(BaseModel):
    suggestions: list[SecondLookSuggestion]


class SecondLookSubmitRequest(BaseModel):
    session_id: str
    feature: str
    landmark_series: list[dict]


class Finding(BaseModel):
    feature: str
    value: float
    unit: str
    method: str
    interpretation: str
    confidence: float
    limitations: str


class SecondLookSubmitResponse(BaseModel):
    findings: list[Finding]


# --- synthesis -----------------------------------------------------------------

class SynthesisRunResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done"]


class ReasoningStep(BaseModel):
    evidence: str
    edge: str
    weight: float
    note: str | None = None


class Consideration(BaseModel):
    disease: str
    score: float
    rank: int
    reasoning_chain: list[ReasoningStep]
    recommended_tests: list[str]
    priority: Priority
    review: ReviewStatus = "pending"


class RiskModelOutput(BaseModel):
    name: str
    score: float
    #: model accuracy/F1 when a trained artifact exists; for the current
    #: documented rule-based scorers (risk/models.py) this is None and
    #: `metric` carries the disclosure string instead (progress.md Decisions
    #: log, 2026-09-21 — no public dataset was confirmed for Phase 6).
    f1: float | None = None
    metric: str | None = None
    basis: str | None = None
    inputs: list[str]
    #: literal "screening signal, not a diagnosis" (CLAUDE.md rule 1) — always
    #: rendered alongside the score, never omitted.
    disclaimer: str = "screening signal, not a diagnosis"


class SynthesisResultResponse(BaseModel):
    considerations: list[Consideration]
    risk_models: list[RiskModelOutput]


class ExplainEdge(BaseModel):
    evidence: str
    source: Literal["reported", "inferred", "capture", "village"]
    confidence: float | None = None
    role: Literal["strongest", "supporting", "context"]
    edge: str | None = None
    weight: float | None = None
    screening_rule: str | None = None


class GraphNode(BaseModel):
    """One node of the developer-mode graph visualisation (screen 16, Phase 7).
    Pure pass-through of what `agents/reasoning.py::traverse_candidates` already
    computed for `edges` above — no new clinical content, just a node/edge shape
    a force-graph renderer can consume directly. The browser never talks to
    Neo4j; this is served by the backend only (CLAUDE.md rule 5's video
    constraint generalised — no direct Bolt connection from the client)."""

    id: str
    label: str
    type: Literal["person", "disease", "symptom", "context"]
    highlighted: bool = False


class GraphEdgeOut(BaseModel):
    id: str
    source: str
    target: str
    relationship: str
    weight: float | None = None
    confidence: float | None = None
    role: Literal["strongest", "supporting", "context"]
    highlighted: bool = True


class ExplainResponse(BaseModel):
    consideration: str
    score: float
    edges: list[ExplainEdge]
    #: populated only when `full=true` — the node/edge list for the
    #: developer-mode force-graph, derived 1:1 from `edges` above (rank-1
    #: consideration + its reasoning-chain evidence). Empty for the default
    #: explainability view, which renders `edges` as a ranked list instead.
    nodes: list[GraphNode] = []
    graph_edges: list[GraphEdgeOut] = []


# --- report ---------------------------------------------------------------

class ReportGenerateRequest(BaseModel):
    session_id: str


class ReportGenerateResponse(BaseModel):
    artifact_id: str
    pdf_url: str


# --- person / village -----------------------------------------------------

class SessionSummary(BaseModel):
    date: str
    kind: str
    outcome: str


class VitalSeriesPoint(BaseModel):
    date: str
    value: float | str


class PersonSummary(BaseModel):
    """Tier 3 (architecture.md §6) — the only thing that enters the agent
    context, never the full history."""

    demographics: dict
    village_context: dict
    chronic_flags: list[dict] = []
    vital_baselines: dict[str, float | None] = {}
    last_session: dict | None = None
    open_followups: list[dict] = []


class PersonProfileResponse(BaseModel):
    person_id: str
    name: str
    age: int
    gender: Gender
    village: str
    sessions: list[SessionSummary]
    vital_series: dict[str, list[VitalSeriesPoint]]
    summary: PersonSummary | None = None


class TopSymptom(BaseModel):
    slug: str
    count: int


class VillageTrendPoint(BaseModel):
    month: str
    screened: int
    referred: int


class Hamlet(BaseModel):
    name: str
    screened: int
    referred: int
    status: Literal["ok", "attention"]


class VillageAlert(BaseModel):
    kind: Literal["cluster"]
    disease_group: str
    count: int
    baseline_multiple: float
    window_days: int
    ward: str
    suggestion: str


class VillageSummaryResponse(BaseModel):
    population: int
    screened_quarter: int
    referred: int
    followups_due: int
    top_symptoms: list[TopSymptom]
    trend: list[VillageTrendPoint]
    hamlets: list[Hamlet]
    alerts: list[VillageAlert]


# --- kb ---------------------------------------------------------------------

class SymptomOut(BaseModel):
    slug: str
    name: str
    severity: int | None
    aliases: list[str] = []


class DiseaseEdgesOut(BaseModel):
    slug: str
    name: str
    review: ReviewStatus
    symptoms: list[str]
    precautions: list[str]
    tests: list[str]
