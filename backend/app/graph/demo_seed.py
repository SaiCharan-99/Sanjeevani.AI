"""Phase 7 demo fixture: a real waterborne-illness cluster in "Peddapuram" so
the village dashboard (screen 17, `GET /api/village/{village_id}/summary`) has
something genuine to aggregate against a live Neo4j, without walking the full
golden path through the app first.

Writes ~15 real :PHI:Person / :PHI:Session / :PHI:Utterance nodes via the same
`memory.persistence` functions the live app uses (`start_session`,
`write_pain_points`, `complete_session`) — no separate write path, so this
fixture is exercised by exactly the same Cypher as a real session. Backdates
`created_at` directly (persistence.start_session doesn't take that parameter)
so the "8 cases in the last 6 days vs ~1/6-days baseline" shape used by
`api/village.py::cluster_alerts_from_rows` is actually present in the graph.

Symptoms used are exactly `waterborne_illness`'s curated `presents_with` set
(`data/seed/curated/rural_india.yaml`: abdominal_pain, fatigue) — no invented
clinical content (CLAUDE.md rule 11).

Run (after `python -m app.graph.seed`, which must have already written the
`waterborne_illness` / `abdominal_pain` / `fatigue` KB nodes):

    python -m app.graph.demo_seed

Idempotent-ish: uses fixed person/session ids (`demo_pedd_NN` /
`SAN-DEMO-PEDD-NN`), so re-running MERGEs onto the same person nodes rather
than duplicating people — but session/utterance nodes are recreated each run,
which is fine for a demo fixture. Re-run shortly before a demo since the
cluster window is relative to "now" at seed time.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.graph import queries as q
from app.graph.client import GraphClient
from app.memory import persistence

VILLAGE_ID = "peddapuram"
VILLAGE_NAME = "Peddapuram"

WATERBORNE_SYMPTOMS = ["abdominal_pain", "fatigue"]
UNRELATED_SYMPTOMS = ["cough"]


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


async def _seed_session(
    client: GraphClient,
    *,
    idx: int,
    days_ago: float,
    symptoms: list[str],
    recommendations: list[str],
) -> None:
    person_id = f"demo_pedd_{idx:02d}"
    session_id = f"SAN-DEMO-PEDD-{idx:02d}"

    # Backdated session write — reuses the exact same Cypher as
    # memory.persistence.start_session, just with an explicit created_at
    # instead of "now", so the seeded cluster actually falls inside the
    # dashboard's rolling window.
    await client.run(
        q.CREATE_PERSON_AND_SESSION,
        person_id=person_id,
        name=f"Peddapuram resident {idx}",
        age=30 + (idx % 40),
        gender="female" if idx % 2 == 0 else "male",
        village_id=VILLAGE_ID,
        village_name=VILLAGE_NAME,
        session_id=session_id,
        language="te",
        consent=True,
        created_at=_iso(days_ago),
    )

    pain_points = [
        {"canonical": slug, "confidence": 0.8, "verbatim": slug.replace("_", " ")}
        for slug in symptoms
    ]
    await persistence.write_pain_points(
        client, session_id=session_id, pain_points=pain_points, language="te", source="officer"
    )

    await persistence.complete_session(
        client,
        session_id=session_id,
        top_findings=[s.replace("_", " ") for s in symptoms],
        recommendations=recommendations,
    )


async def seed_demo_village(client: GraphClient) -> None:
    # 8 sessions inside the last CLUSTER_WINDOW_DAYS (6) — the cluster itself.
    cluster_days_ago = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 5.5]
    for i, days_ago in enumerate(cluster_days_ago, start=1):
        await _seed_session(
            client,
            idx=i,
            days_ago=days_ago,
            symptoms=WATERBORNE_SYMPTOMS,
            recommendations=["ORS", "Referral for suspected typhoid"] if i % 2 == 0 else [],
        )

    # 4 sessions spread across the prior 4 windows (baseline ≈ 1/window).
    baseline_days_ago = [9.0, 15.0, 21.0, 27.0]
    for i, days_ago in enumerate(baseline_days_ago, start=9):
        await _seed_session(
            client,
            idx=i,
            days_ago=days_ago,
            symptoms=WATERBORNE_SYMPTOMS,
            recommendations=[],
        )

    # 3 unrelated sessions (different symptom) so top_symptoms / hamlet
    # screened counts aren't 100% one disease — a more realistic dashboard.
    unrelated_days_ago = [1.0, 10.0, 20.0]
    for i, days_ago in enumerate(unrelated_days_ago, start=13):
        await _seed_session(
            client,
            idx=i,
            days_ago=days_ago,
            symptoms=UNRELATED_SYMPTOMS,
            recommendations=[],
        )


async def main() -> None:
    client = GraphClient.from_env()
    await seed_demo_village(client)
    await client.close()
    print(
        f"Demo village seeded: {VILLAGE_NAME} — 8 waterborne-illness cases in the last 6 "
        "days, 4 baseline cases over the prior 24 days, 3 unrelated sessions."
    )


if __name__ == "__main__":
    asyncio.run(main())
