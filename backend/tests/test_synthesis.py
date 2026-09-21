"""Phase 6 — graph traversal + reasoning chain tests (agents/reasoning.py).
Fixture-based: a stub GraphClient returns rows shaped exactly like
CANDIDATE_DISEASES_FOR_SYMPTOMS, so this runs without a live Neo4j (same
pattern as test_secondlook.py's pure-function tests). Asserts the TB
reasoning chain cites the NTEP screening_rule string verbatim and that the
chain is an ordered list of evidence -> edge -> conclusion steps, not just a
final answer."""

from __future__ import annotations

import pytest

from app.agents import reasoning
from app.api.synthesis import _build_dev_graph
from app.models import ExplainEdge

NTEP_RULE = "NTEP presumptive TB: cough >= 2 weeks"


class _StubGraphClient:
    """Minimal stand-in for graph.client.GraphClient — only implements
    .run(), returning canned rows for CANDIDATE_DISEASES_FOR_SYMPTOMS."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def run(self, query: str, **params):
        return self._rows


def _tb_row(min_duration_days: int = 14) -> dict:
    return {
        "slug": "tuberculosis", "name": "Pulmonary tuberculosis",
        "description": "...", "review": "approved", "endemic_regions": [],
        "matched_symptoms": [
            {"symptom": "cough", "weight": 1.0, "screening_rule": NTEP_RULE,
             "min_duration_days": min_duration_days, "typical_stage": None},
            {"symptom": "weight_loss", "weight": 0.8, "screening_rule": None,
             "min_duration_days": None, "typical_stage": None},
            {"symptom": "night_sweats", "weight": 0.7, "screening_rule": None,
             "min_duration_days": None, "typical_stage": None},
        ],
        "total_symptoms": 6,
        "tests": [{"slug": "sputum_smear", "name": "Sputum smear / NAAT", "priority": 1},
                  {"slug": "chest_xray", "name": "Chest X-ray", "priority": 2}],
    }


def _copd_row() -> dict:
    return {
        "slug": "copd", "name": "COPD", "description": "...", "review": "pending", "endemic_regions": [],
        "matched_symptoms": [
            {"symptom": "cough", "weight": 0.4, "screening_rule": None, "min_duration_days": None, "typical_stage": None},
        ],
        "total_symptoms": 5,
        "tests": [{"slug": "spirometry", "name": "Spirometry", "priority": 1}],
    }


GOLDEN_PATH_PAIN_POINTS = [
    {"canonical": "cough", "duration_days": 21, "confidence": 0.95},
    {"canonical": "chest_tightness", "confidence": 0.90},
    {"canonical": "fatigue", "confidence": 0.88},
    {"canonical": "night_sweats", "confidence": 0.75},
    {"canonical": "weight_loss", "confidence": 0.85},
]


@pytest.mark.asyncio
async def test_tb_reasoning_chain_cites_ntep_screening_rule():
    client = _StubGraphClient([_tb_row(), _copd_row()])
    candidates = await reasoning.traverse_candidates(
        client, symptom_slugs=["cough", "weight_loss", "night_sweats"],
        pain_points=GOLDEN_PATH_PAIN_POINTS, findings=[],
    )
    tb = next(c for c in candidates if c.slug == "tuberculosis")
    notes = [step["note"] for step in tb.reasoning_chain]
    assert NTEP_RULE in notes


@pytest.mark.asyncio
async def test_reasoning_chain_is_ordered_list_not_just_an_answer():
    client = _StubGraphClient([_tb_row()])
    candidates = await reasoning.traverse_candidates(
        client, symptom_slugs=["cough", "weight_loss", "night_sweats"],
        pain_points=GOLDEN_PATH_PAIN_POINTS, findings=[],
    )
    tb = candidates[0]
    assert isinstance(tb.reasoning_chain, list)
    assert len(tb.reasoning_chain) >= 2
    for step in tb.reasoning_chain:
        assert set(step.keys()) >= {"evidence", "edge", "weight"}
        assert step["edge"]  # every step names the edge it traversed
    # Highest-weight evidence (cough, the screening trigger) leads the chain.
    assert tb.reasoning_chain[0]["evidence"].startswith("cough")


@pytest.mark.asyncio
async def test_tb_ranks_above_copd_for_golden_path_symptom_set():
    client = _StubGraphClient([_tb_row(), _copd_row()])
    candidates = await reasoning.traverse_candidates(
        client, symptom_slugs=["cough", "weight_loss", "night_sweats"],
        pain_points=GOLDEN_PATH_PAIN_POINTS, findings=[],
    )
    assert candidates[0].slug == "tuberculosis"
    assert candidates[0].rank == 1
    assert candidates[0].priority == "high"
    assert candidates[0].review == "approved"


@pytest.mark.asyncio
async def test_screening_rule_not_cited_when_duration_below_threshold():
    """The NTEP rule requires >= 14 days; a short cough must not cite it."""
    client = _StubGraphClient([_tb_row(min_duration_days=14)])
    candidates = await reasoning.traverse_candidates(
        client, symptom_slugs=["cough"],
        pain_points=[{"canonical": "cough", "duration_days": 3, "confidence": 0.9}], findings=[],
    )
    tb = candidates[0]
    notes = [s["note"] for s in tb.reasoning_chain]
    assert NTEP_RULE not in notes


@pytest.mark.asyncio
async def test_capped_at_top_n_candidates():
    rows = [
        {
            "slug": f"disease_{i}", "name": f"Disease {i}", "description": "", "review": "pending",
            "endemic_regions": [],
            "matched_symptoms": [{"symptom": "cough", "weight": 0.1 * (i + 1), "screening_rule": None,
                                   "min_duration_days": None, "typical_stage": None}],
            "total_symptoms": 3, "tests": [],
        }
        for i in range(10)
    ]
    client = _StubGraphClient(rows)
    candidates = await reasoning.traverse_candidates(
        client, symptom_slugs=["cough"], pain_points=[{"canonical": "cough", "confidence": 0.9}], findings=[],
    )
    assert len(candidates) <= reasoning.TOP_N_CANDIDATES


@pytest.mark.asyncio
async def test_no_graph_client_falls_back_to_empty_list():
    candidates = await reasoning.traverse_candidates(
        None, symptom_slugs=["cough"], pain_points=[], findings=[],
    )
    assert candidates == []


@pytest.mark.asyncio
async def test_no_symptoms_falls_back_to_empty_list():
    client = _StubGraphClient([_tb_row()])
    candidates = await reasoning.traverse_candidates(
        client, symptom_slugs=[], pain_points=[], findings=[],
    )
    assert candidates == []


# --- Phase 7 — developer-mode graph shape (api/synthesis.py::_build_dev_graph) ---
# Pure function, built from already-computed ExplainEdge rows (same pattern as
# the traverse_candidates tests above — no live Neo4j / FastAPI server needed).

def _golden_path_edges() -> list[ExplainEdge]:
    return [
        ExplainEdge(evidence="cough (21 days)", source="reported", confidence=0.98,
                    role="strongest", edge="PRESENTS_WITH", weight=1.0,
                    screening_rule=NTEP_RULE),
        ExplainEdge(evidence="weight_loss", source="inferred", confidence=0.74, role="supporting"),
        ExplainEdge(evidence="night_sweats", source="reported", confidence=0.68, role="supporting"),
        ExplainEdge(evidence="Kadiri TB cluster (2 confirmed)", source="village", role="context"),
    ]


def test_build_dev_graph_includes_person_and_disease_nodes():
    nodes, edges = _build_dev_graph("tuberculosis", "Pulmonary tuberculosis", 0.87, _golden_path_edges())
    types = {n.type for n in nodes}
    assert "person" in types
    assert "disease" in types
    disease_nodes = [n for n in nodes if n.type == "disease"]
    assert disease_nodes[0].label == "Pulmonary tuberculosis"


def test_build_dev_graph_one_symptom_node_per_evidence_row():
    edges_in = _golden_path_edges()
    nodes, edges = _build_dev_graph("tuberculosis", "Pulmonary tuberculosis", 0.87, edges_in)
    # 1 person + 1 disease + 4 evidence nodes (3 symptom, 1 context)
    assert len(nodes) == 2 + len(edges_in)
    symptom_nodes = [n for n in nodes if n.type == "symptom"]
    context_nodes = [n for n in nodes if n.type == "context"]
    assert len(symptom_nodes) == 3
    assert len(context_nodes) == 1


def test_build_dev_graph_every_evidence_node_traverses_to_the_disease():
    edges_in = _golden_path_edges()
    nodes, graph_edges = _build_dev_graph("tuberculosis", "Pulmonary tuberculosis", 0.87, edges_in)
    disease_id = next(n.id for n in nodes if n.type == "disease")
    targets_from_evidence = {e.target for e in graph_edges if e.source.startswith(("symptom:", "context:"))}
    assert targets_from_evidence == {disease_id}
    # every edge is marked highlighted — this is the traversed path, not
    # unrelated graph context (specs.md §2 screen 16 "highlighting the path used")
    assert all(e.highlighted for e in graph_edges)


def test_build_dev_graph_village_context_never_marked_strongest():
    nodes, graph_edges = _build_dev_graph("tuberculosis", "Pulmonary tuberculosis", 0.87, _golden_path_edges())
    context_edges = [e for e in graph_edges if e.role == "context"]
    assert context_edges and all(e.role != "strongest" for e in context_edges)
