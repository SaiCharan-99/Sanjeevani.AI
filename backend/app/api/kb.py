"""Read-only knowledge-base endpoints. Powers the symptom picker (screen 9) and
developer mode. Reads :KB via graph/queries.py — never writes it (seed.py owns
writes). Falls back to a small static mock list if Neo4j is unreachable, so the
API stays usable before `docker compose up` has run the seed."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.graph import queries as q
from app.models import DiseaseEdgesOut, SymptomOut

router = APIRouter(prefix="/api/kb", tags=["kb"])

_MOCK_SYMPTOMS = [
    SymptomOut(slug="cough", name="Cough", severity=4, aliases=["coughing"]),
    SymptomOut(slug="chest_tightness", name="Chest tightness", severity=3, aliases=[]),
    SymptomOut(slug="fatigue", name="Fatigue", severity=3, aliases=["tired"]),
    SymptomOut(slug="night_sweats", name="Night sweats", severity=3, aliases=[]),
    SymptomOut(slug="weight_loss", name="Weight loss", severity=3, aliases=[]),
]


@router.get("/symptoms", response_model=list[SymptomOut])
async def list_symptoms(request: Request) -> list[SymptomOut]:
    client = getattr(request.app.state, "graph_client", None)
    if client is None:
        return _MOCK_SYMPTOMS
    try:
        rows = await client.run(q.LIST_SYMPTOMS)
        return [SymptomOut(**row) for row in rows]
    except Exception:
        return _MOCK_SYMPTOMS


@router.get("/diseases/{slug}", response_model=DiseaseEdgesOut)
async def get_disease(slug: str, request: Request) -> DiseaseEdgesOut:
    client = getattr(request.app.state, "graph_client", None)
    if client is not None:
        try:
            rows = await client.run(q.GET_DISEASE_WITH_EDGES, slug=slug)
            if rows:
                row = rows[0]
                node = row["d"]
                return DiseaseEdgesOut(
                    slug=node.get("slug", slug),
                    name=node.get("name", slug),
                    review=node.get("review", "pending"),
                    symptoms=[s["symptom"] for s in row["symptoms"] if s.get("symptom")],
                    precautions=[p for p in row["precautions"] if p],
                    tests=[t for t in row["tests"] if t],
                )
        except Exception:
            pass
    return DiseaseEdgesOut(
        slug="tuberculosis", name="Pulmonary tuberculosis", review="approved",
        symptoms=["cough", "night_sweats", "weight_loss"],
        precautions=["consult nearest hospital"],
        tests=["Sputum smear / CBNAAT", "Chest X-ray"],
    )
