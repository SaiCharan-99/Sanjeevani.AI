"""Graph traversal + reasoning chains (architecture.md §5 "The join", §9;
specs.md §7). Given a session's symptoms/findings/vitals, traverse
`PRESENTS_WITH` (and, via `memory.persistence.FEATURE_INDICATES_SYMPTOM`, the
`:INDICATES` edges already written for second-look findings) to candidate
diseases, score them, and return an ordered reasoning chain per candidate.

This module never invents clinical content (CLAUDE.md rule 11): every
candidate disease, symptom, test and screening_rule string comes straight off
a `:KB` node/edge read through `graph/queries.py`. The LLM is not involved in
scoring or in choosing what to say — it may only be asked, elsewhere, to
*phrase* output, never to originate it. This module produces the facts.

Cap: top N=5 candidate diseases (documented choice — specs.md doesn't set a
number; 5 keeps the assessment screen and the PDF readable without truncating
anything the golden path needs, which surfaces only 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.graph import queries as q
from app.graph.client import GraphClient

TOP_N_CANDIDATES = 5

#: Kept in sync with agents/triggers.py FEATURE->symptom mapping; imported
#: lazily inside functions to avoid a circular import at module load time.


@dataclass
class ReasoningStepDict:
    evidence: str
    edge: str
    weight: float
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"evidence": self.evidence, "edge": self.edge, "weight": self.weight, "note": self.note}


@dataclass
class ConsiderationDict:
    disease: str
    slug: str
    score: float
    rank: int
    reasoning_chain: list[dict[str, Any]] = field(default_factory=list)
    recommended_tests: list[str] = field(default_factory=list)
    priority: str = "low"
    review: str = "pending"


def _duration_for(slug: str, pain_points: list[dict[str, Any]]) -> int | None:
    for p in pain_points:
        if p.get("canonical") == slug and p.get("duration_days") is not None:
            return int(p["duration_days"])
    return None


def _confidence_for(slug: str, pain_points: list[dict[str, Any]], findings: list[dict[str, Any]]) -> float:
    """Evidence confidence for a matched symptom slug: the highest confidence
    among any pain point (verbal report) or finding (:INDICATES) that named it.
    Defaults to 0.5 (a graph-only symptom with no direct session evidence —
    should not normally happen since matched_symptoms are already filtered to
    the session's reported/observed set, but keeps scoring defined)."""
    from app.memory.persistence import FEATURE_INDICATES_SYMPTOM

    best = 0.0
    found = False
    for p in pain_points:
        if p.get("canonical") == slug:
            best = max(best, float(p.get("confidence", 0.5)))
            found = True
    for f in findings:
        if FEATURE_INDICATES_SYMPTOM.get(f.get("feature")) == slug:
            best = max(best, float(f.get("confidence", 0.5)))
            found = True
    return best if found else 0.5


def _priority_from_score(score: float, has_screening_rule: bool) -> str:
    if has_screening_rule or score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


async def traverse_candidates(
    client: GraphClient | None,
    *,
    symptom_slugs: list[str],
    pain_points: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    village_cluster: dict[str, Any] | None = None,
) -> list[ConsiderationDict]:
    """Traverse `:KB:Disease-[:PRESENTS_WITH]->:KB:Symptom` for the session's
    reported/observed symptom slugs, score by edge weight × evidence
    confidence with a symptom-coverage bonus, cap at TOP_N_CANDIDATES, and
    build an ordered reasoning chain per candidate (evidence -> edge ->
    conclusion). Returns [] gracefully if the graph is unreachable or no
    symptoms resolved — callers fall back to the golden-path result, same
    pattern as every other api/ module (CLAUDE.md)."""
    if client is None or not symptom_slugs:
        return []
    try:
        rows = await client.run(q.CANDIDATE_DISEASES_FOR_SYMPTOMS, slugs=symptom_slugs)
    except Exception:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        matched = row.get("matched_symptoms") or []
        total = row.get("total_symptoms") or len(matched) or 1
        weighted_sum = 0.0
        for m in matched:
            weight = float(m.get("weight") or 0.0)
            slug = m.get("symptom")
            confidence = _confidence_for(slug, pain_points, findings)
            weighted_sum += weight * confidence
        coverage = len(matched) / total if total else 0.0
        score = min(1.0, weighted_sum * (0.6 + 0.4 * coverage))
        # Village prior nudges score up slightly as context, never as strongest
        # evidence (specs.md §7 "role: context, never strongest").
        if village_cluster and village_cluster.get("disease_group") == row.get("slug"):
            score = min(1.0, score + 0.05)
        scored.append((score, row))

    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:TOP_N_CANDIDATES]

    considerations: list[ConsiderationDict] = []
    for rank, (score, row) in enumerate(top, start=1):
        matched = row.get("matched_symptoms") or []
        matched_sorted = sorted(matched, key=lambda m: float(m.get("weight") or 0.0), reverse=True)
        chain: list[dict[str, Any]] = []
        has_screening_rule = False
        for m in matched_sorted:
            slug = m.get("symptom")
            weight = float(m.get("weight") or 0.0)
            screening_rule = m.get("screening_rule")
            duration = _duration_for(slug, pain_points)
            evidence = slug.replace("_", " ") if slug else "symptom"
            if duration is not None:
                evidence = f"{evidence} ({duration} days)"
            note = None
            if screening_rule:
                min_days = m.get("min_duration_days")
                if min_days is None or (duration is not None and duration >= min_days):
                    note = screening_rule
                    has_screening_rule = True
            chain.append(
                ReasoningStepDict(evidence=evidence, edge="PRESENTS_WITH", weight=weight, note=note).as_dict()
            )
        if village_cluster and village_cluster.get("disease_group") == row.get("slug"):
            chain.append(
                ReasoningStepDict(
                    evidence=village_cluster.get("summary", "village cluster context"),
                    edge="HAS_CLUSTER",
                    weight=0.0,
                    note="village context — supporting, not strongest evidence",
                ).as_dict()
            )
        tests = [t.get("name") for t in (row.get("tests") or []) if t and t.get("name")]
        considerations.append(
            ConsiderationDict(
                disease=row.get("name") or row.get("slug"),
                slug=row.get("slug"),
                score=round(score, 2),
                rank=rank,
                reasoning_chain=chain,
                recommended_tests=tests,
                priority=_priority_from_score(score, has_screening_rule),
                review=row.get("review") or "pending",
            )
        )
    return considerations
