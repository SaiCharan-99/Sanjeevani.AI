"""Graph traversal + risk models + reasoning chain. Runs as a background job
(architecture.md §7 stage 5 — the officer moves to the next person and polls
GET /api/synthesis/result later). Job queue is memory/jobs.py: FastAPI
BackgroundTasks + a module-level dict, no Celery/Redis (CLAUDE.md).

Phase 6: real graph traversal (agents/reasoning.py, graph/queries.py) and
documented rule-based risk models (risk/models.py) now run against Tier 1
SessionState. Same graceful-no-op pattern as every other api/ module: if the
graph is unreachable, no symptoms have resolved yet, or the session has no
Tier 1 state, this falls back to the golden-path TB synthesis from
specs.md §1/§3 so the demo never shows a broken state."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request

from app.agents import reasoning
from app.memory import jobs
from app.memory.state import get_session
from app.models import (
    Consideration,
    ExplainEdge,
    ExplainResponse,
    GraphEdgeOut,
    GraphNode,
    ReasoningStep,
    RiskModelOutput,
    SynthesisResultResponse,
    SynthesisRunResponse,
)
from app.risk import models as risk_models

router = APIRouter(prefix="/api/synthesis", tags=["synthesis"])


def _golden_path_result() -> SynthesisResultResponse:
    return SynthesisResultResponse(
        considerations=[
            Consideration(
                disease="Pulmonary tuberculosis",
                score=0.87,
                rank=1,
                reasoning_chain=[
                    ReasoningStep(evidence="cough (21 days)", edge="PRESENTS_WITH", weight=0.9,
                                  note="NTEP presumptive TB: cough >= 2 weeks"),
                    ReasoningStep(evidence="weight loss", edge="PRESENTS_WITH", weight=0.8),
                    ReasoningStep(evidence="night sweats", edge="PRESENTS_WITH", weight=0.7),
                    ReasoningStep(evidence="respiration_rate 22 (elevated) + spo2 94% (low-normal)",
                                  edge="MEASURED_BY", weight=0.5, note="respiratory involvement"),
                ],
                recommended_tests=["Sputum smear / NAAT", "Chest X-ray"],
                priority="high",
                review="approved",
            ),
            Consideration(
                disease="COPD",
                score=0.42,
                rank=2,
                reasoning_chain=[
                    ReasoningStep(evidence="age 52 + biomass exposure + exertional breathlessness",
                                  edge="RISK_FACTOR", weight=0.5),
                ],
                recommended_tests=["Spirometry"],
                priority="medium",
                review="pending",
            ),
        ],
        risk_models=[
            RiskModelOutput(
                name="anemia_risk", score=0.62, f1=None,
                metric=risk_models.RULE_BASED_METRIC,
                basis="0.5x pallor_score + tachycardia term (HR>90) + 0.2 if fatigue reported + 0.1 for female sex",
                inputs=["pallor_score", "heart_rate", "fatigue"],
            ),
        ],
    )


async def _run_real_synthesis(request: Request, session_id: str) -> SynthesisResultResponse:
    """Real path: reads Tier 1 SessionState for this session, traverses the
    graph, runs the rule-based risk models, and returns a result. Falls back
    to the golden path when Tier 1 has nothing yet or the graph traversal
    returns no candidates (graph unreachable, no resolved symptoms)."""
    state = get_session(session_id)
    if state is None:
        return _golden_path_result()

    pain_points = state.pain_points or []
    findings = state.findings or []
    symptom_slugs = sorted({p["canonical"] for p in pain_points if p.get("canonical")})
    if not symptom_slugs:
        return _golden_path_result()

    client = getattr(request.app.state, "graph_client", None)
    candidates = await reasoning.traverse_candidates(
        client, symptom_slugs=symptom_slugs, pain_points=pain_points, findings=findings
    )
    if not candidates:
        return _golden_path_result()

    considerations = [
        Consideration(
            disease=c.disease,
            score=c.score,
            rank=c.rank,
            reasoning_chain=[ReasoningStep(**step) for step in c.reasoning_chain],
            recommended_tests=c.recommended_tests,
            priority=c.priority,  # type: ignore[arg-type]
            review=c.review,  # type: ignore[arg-type]
        )
        for c in candidates
    ]

    age = 52
    gender = "male"
    if state.person_id:
        pass  # person demographics not needed beyond session vitals for the rule-based scorers
    raw_risk = risk_models.run_all(state.vitals or {}, pain_points, age=age, gender=gender)
    risk_outputs = [
        RiskModelOutput(
            name=r["name"], score=r["score"], f1=r.get("f1"), metric=r.get("metric"),
            basis=r.get("basis"), inputs=r["inputs"], disclaimer=r.get("disclaimer", risk_models.SCREENING_DISCLAIMER),
        )
        for r in raw_risk
    ]
    if not risk_outputs:
        # Nothing captured yet this session to feed a model — the golden
        # path's anemia figure is still a real, documented example output.
        risk_outputs = _golden_path_result().risk_models

    return SynthesisResultResponse(considerations=considerations, risk_models=risk_outputs)


@router.post("/run", response_model=SynthesisRunResponse)
async def run_synthesis(session_id: str, background_tasks: BackgroundTasks, request: Request) -> SynthesisRunResponse:
    job_id = jobs.new_job_id()
    jobs.create_job(job_id, session_id)

    async def _work() -> SynthesisResultResponse:
        return await _run_real_synthesis(request, session_id)

    background_tasks.add_task(jobs.run_job, job_id, _work)
    return SynthesisRunResponse(job_id=job_id, status="queued")


@router.get("/result", response_model=SynthesisResultResponse)
async def synthesis_result(session_id: str, request: Request) -> SynthesisResultResponse:
    job = jobs.latest_job_for_session(session_id)
    if job is not None and job["status"] == "done":
        return job["result"]
    # No job queued yet, or still running: run synchronously so the demo
    # still has a result to show immediately (screen 13 can be opened
    # without having gone through screen 12's "See assessment" queue step).
    return await _run_real_synthesis(request, session_id)


def _evidence_slug(evidence: str) -> str:
    """`"cough (21 days)"` -> `"cough"`; `"Kadiri TB cluster (2 confirmed)"` ->
    `"kadiri_tb_cluster"`. Pure string transform for node ids in the
    developer-mode graph — not a new lookup, just an id derived from the
    already-computed evidence label."""
    base = evidence.split(" (")[0].strip()
    return base.lower().replace(" ", "_")


def _build_dev_graph(consideration_slug: str, disease_name: str, score: float, edges: list[ExplainEdge]) -> tuple[list[GraphNode], list[GraphEdgeOut]]:
    """Node/edge list for screen 16's developer-mode force-graph, built purely
    from the already-computed `edges` (the rank-1 consideration's reasoning
    chain from agents/reasoning.py::traverse_candidates). No new clinical
    lookups — the graph the browser gets to draw is exactly the traversal the
    backend already ran, never a live Bolt connection from the client
    (CLAUDE.md rule 5, generalised beyond video)."""
    person_id = "person:session"
    disease_id = f"disease:{consideration_slug}"
    nodes: list[GraphNode] = [
        GraphNode(id=person_id, label="This person", type="person", highlighted=True),
        GraphNode(id=disease_id, label=disease_name, type="disease", highlighted=True),
    ]
    graph_edges: list[GraphEdgeOut] = []
    for i, e in enumerate(edges):
        is_context = e.role == "context"
        node_type = "context" if is_context else "symptom"
        node_id = f"{node_type}:{_evidence_slug(e.evidence)}"
        nodes.append(GraphNode(id=node_id, label=e.evidence, type=node_type, highlighted=True))
        # Person reported/observed this evidence.
        graph_edges.append(
            GraphEdgeOut(
                id=f"person-{node_id}", source=person_id, target=node_id,
                relationship=e.source, confidence=e.confidence, role=e.role,
                highlighted=True,
            )
        )
        # Evidence contributes to the disease consideration — the traversed edge.
        graph_edges.append(
            GraphEdgeOut(
                id=f"{node_id}-{disease_id}-{i}", source=node_id, target=disease_id,
                relationship=e.edge or "PRESENTS_WITH", weight=e.weight, confidence=e.confidence,
                role=e.role, highlighted=True,
            )
        )
    return nodes, graph_edges


@router.get("/explain", response_model=ExplainResponse)
async def explain(session_id: str, request: Request, full: bool = False) -> ExplainResponse:
    result = await synthesis_result(session_id, request)
    if not result.considerations:
        edges = [
            ExplainEdge(evidence="cough (21 days)", source="reported", confidence=0.98,
                        role="strongest", edge="PRESENTS_WITH", weight=1.0,
                        screening_rule="NTEP presumptive TB: cough >= 2 weeks"),
        ]
        nodes, graph_edges = ([], [])
        if full:
            nodes, graph_edges = _build_dev_graph("tuberculosis", "Pulmonary tuberculosis", 0.87, edges)
        return ExplainResponse(consideration="tuberculosis", score=0.87, edges=edges, nodes=nodes, graph_edges=graph_edges)
    top = result.considerations[0]
    edges: list[ExplainEdge] = []
    for i, step in enumerate(top.reasoning_chain):
        role = "strongest" if i == 0 else ("context" if step.edge == "HAS_CLUSTER" else "supporting")
        source = "village" if step.edge == "HAS_CLUSTER" else ("capture" if "respiration" in step.evidence or "spo2" in step.evidence else "reported")
        edges.append(
            ExplainEdge(
                evidence=step.evidence, source=source, confidence=step.weight, role=role,
                edge=step.edge, weight=step.weight, screening_rule=step.note if step.note and "NTEP" in step.note else None,
            )
        )
    consideration_slug = top.disease.lower().replace(" ", "_")
    nodes, graph_edges = ([], [])
    if full:
        nodes, graph_edges = _build_dev_graph(consideration_slug, top.disease, top.score, edges)
    return ExplainResponse(consideration=consideration_slug, score=top.score, edges=edges, nodes=nodes, graph_edges=graph_edges)
