"""GET /api/village/{village_id}/summary — screen 17. Phase 7. Aggregates
only; no person identifiers (rule per specs.md §2 screen 17).

GET /api/village/autocomplete powers screen 2's village field (specs.md §2
"village (autocomplete from prior sessions)") — reads distinct :PHI:Village
names already in the graph, falling back to a small static list.

Follow-up compliance uses the same :PHI:Session `status` lifecycle Phase 3
already writes (`queued` / `running` / `done_unopened`) — no new compliance
concept is invented. `referred` is a proxy: a session whose `recommendations`
list is non-empty (something was recommended at `/session/complete`); there is
no dedicated referral flag in the graph yet (progress.md Open questions/
Decisions log carries this honestly rather than inventing a richer concept).

Disease-cluster detection (the waterborne-illness story) compares, per hamlet/
ward (`:PHI:Village.name`), the count of sessions reporting a symptom in
`waterborne_illness`'s own curated `PRESENTS_WITH` set within the last
CLUSTER_WINDOW_DAYS against the average count in the same-length window over
each of the 4 prior periods. `CLUSTER_WINDOW_DAYS` / `CLUSTER_MULTIPLE` are the
wireframe's own numbers ("3x baseline ... over 6 days") — the only documented
value (progress.md Open questions, resolved this phase).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request

from app.graph import queries as q
from app.memory import persistence
from app.models import (
    Hamlet,
    TopSymptom,
    VillageAlert,
    VillageAutocompleteResponse,
    VillageSummaryResponse,
    VillageTrendPoint,
)

router = APIRouter(prefix="/api/village", tags=["village"])

_MOCK_VILLAGES = ["Kadiri Rural", "Kadiri Main", "Kadiri West", "Peddapuram"]

# Only the one curated disease-cluster label exists (data/seed/curated/
# rural_india.yaml `waterborne_illness`) — CLAUDE.md rule 11, never invent a
# second one.
CLUSTER_DISEASE_SLUG = "waterborne_illness"
CLUSTER_WINDOW_DAYS = 6  # wireframe screen 17: "9 cases ... over 6 days"
CLUSTER_MULTIPLE = 3.0  # wireframe screen 17: "3x baseline"
CLUSTER_MIN_COUNT = 3  # minimum absolute cases before alerting — avoids noise
#                         on a hamlet with one or two sessions total. Judgment
#                         call, not a clinical rule.
CLUSTER_BASELINE_WINDOWS = 4  # 4 prior windows = 24 days of history

_QUARTER_DAYS = 90


def _static_fallback() -> VillageSummaryResponse:
    """The exact wireframe copy (specs.md §2 screen 17 / sanjeevani-flow.html)
    served whenever Neo4j is unreachable or the requested village has no real
    session data yet — same graceful-fallback pattern as api/kb.py."""
    return VillageSummaryResponse(
        population=4200,
        screened_quarter=312,
        referred=18,
        followups_due=6,
        top_symptoms=[
            TopSymptom(slug="cough", count=41),
            TopSymptom(slug="fatigue", count=37),
            TopSymptom(slug="fever", count=25),
        ],
        trend=[
            VillageTrendPoint(month="2026-07", screened=98, referred=5),
            VillageTrendPoint(month="2026-08", screened=110, referred=6),
            VillageTrendPoint(month="2026-09", screened=104, referred=7),
        ],
        hamlets=[
            Hamlet(name="Kadiri Main", screened=180, referred=10, status="attention"),
            Hamlet(name="Kadiri West", screened=132, referred=8, status="ok"),
        ],
        alerts=[
            VillageAlert(
                kind="cluster", disease_group="waterborne", count=9, baseline_multiple=3.0,
                window_days=6, ward="Kadiri West", suggestion="Check the shared borewell source",
            )
        ],
    )


def cluster_alerts_from_rows(
    rows: list[dict], *, cluster_symptoms: set[str], mitigation: str, now: datetime | None = None
) -> list[VillageAlert]:
    """Pure — no I/O — so the wireframe's "3x baseline over 6 days" rule is
    unit-testable without a live Neo4j (backend/tests/test_village.py), same
    approach as agents/triggers.py and memory/summary.py."""
    if not cluster_symptoms:
        return []
    now = now or datetime.now(timezone.utc)
    window = timedelta(days=CLUSTER_WINDOW_DAYS)
    by_hamlet: dict[str, list[datetime]] = defaultdict(list)
    for r in rows:
        if cluster_symptoms.intersection(r["symptoms"] or []):
            try:
                dt = datetime.fromisoformat(r["created_at"])
            except (TypeError, ValueError):
                continue
            by_hamlet[r["village_name"]].append(dt)

    alerts: list[VillageAlert] = []
    for hamlet, dates in by_hamlet.items():
        window_count = sum(1 for d in dates if now - d <= window)
        if window_count < CLUSTER_MIN_COUNT:
            continue
        baseline_counts = []
        for i in range(1, CLUSTER_BASELINE_WINDOWS + 1):
            start = now - window * (i + 1)
            end = now - window * i
            baseline_counts.append(sum(1 for d in dates if start < d <= end))
        baseline = sum(baseline_counts) / CLUSTER_BASELINE_WINDOWS
        # Floor the baseline at 1 so a hamlet with zero prior cases doesn't
        # trigger on an undefined (divide-by-zero) ratio for a trivial count.
        baseline_for_ratio = max(baseline, 1.0)
        ratio = window_count / baseline_for_ratio
        if ratio >= CLUSTER_MULTIPLE:
            alerts.append(
                VillageAlert(
                    kind="cluster",
                    disease_group=CLUSTER_DISEASE_SLUG,
                    count=window_count,
                    baseline_multiple=round(ratio, 1),
                    window_days=CLUSTER_WINDOW_DAYS,
                    ward=hamlet,
                    suggestion=mitigation,
                )
            )
    return alerts


async def _detect_cluster(client, rows: list[dict]) -> list[VillageAlert]:
    disease_rows = await client.run(q.DISEASE_SYMPTOM_SLUGS, slug=CLUSTER_DISEASE_SLUG)
    if not disease_rows:
        return []
    cluster_symptoms = set(disease_rows[0].get("slugs") or [])
    mitigation = (disease_rows[0].get("mitigation") or "Check the shared water source").strip()
    return cluster_alerts_from_rows(rows, cluster_symptoms=cluster_symptoms, mitigation=mitigation)


def aggregate_village_summary(
    rows: list[dict], *, population: int, alerts: list[VillageAlert], now: datetime | None = None
) -> VillageSummaryResponse:
    """Pure aggregation over `VILLAGE_MATCHING_SESSIONS` rows — screened/
    referred/followups-due/top-symptoms/hamlet-breakdown/trend. Split out from
    `_build_summary` so it is unit-testable without a live Neo4j."""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=_QUARTER_DAYS)).isoformat()
    quarter_rows = [r for r in rows if r["created_at"] >= cutoff]

    screened_quarter = len(quarter_rows)
    referred = sum(1 for r in quarter_rows if r["recommendations"])
    followups_due = sum(1 for r in quarter_rows if r["status"] == "done_unopened")

    symptom_counts: Counter[str] = Counter()
    for r in quarter_rows:
        symptom_counts.update(r["symptoms"] or [])
    top_symptoms = [TopSymptom(slug=slug, count=count) for slug, count in symptom_counts.most_common(5)]

    hamlet_agg: dict[str, dict[str, int]] = defaultdict(lambda: {"screened": 0, "referred": 0})
    for r in quarter_rows:
        h = hamlet_agg[r["village_name"]]
        h["screened"] += 1
        if r["recommendations"]:
            h["referred"] += 1
    hamlets = [
        Hamlet(
            name=name,
            screened=agg["screened"],
            referred=agg["referred"],
            status="attention" if agg["referred"] >= max(3, agg["screened"] // 4) else "ok",
        )
        for name, agg in sorted(hamlet_agg.items())
    ]

    month_agg: dict[str, dict[str, int]] = defaultdict(lambda: {"screened": 0, "referred": 0})
    for r in rows:
        month = r["created_at"][:7]
        m = month_agg[month]
        m["screened"] += 1
        if r["recommendations"]:
            m["referred"] += 1
    trend = [
        VillageTrendPoint(month=month, screened=agg["screened"], referred=agg["referred"])
        for month, agg in sorted(month_agg.items())
    ][-6:]

    return VillageSummaryResponse(
        population=population,
        screened_quarter=screened_quarter,
        referred=referred,
        followups_due=followups_due,
        top_symptoms=top_symptoms,
        trend=trend,
        hamlets=hamlets,
        alerts=alerts,
    )


async def _build_summary(client, village_id: str) -> VillageSummaryResponse | None:
    rows = await client.run(q.VILLAGE_MATCHING_SESSIONS, prefix=village_id)
    if not rows:
        return None
    person_rows = await client.run(q.DISTINCT_PERSON_COUNT_FOR_VILLAGE, prefix=village_id)
    # No population field exists anywhere in the graph (it's demographic
    # metadata, not something a health-camp session captures). The distinct
    # screened-person count is used as an honest lower-bound proxy rather than
    # a fabricated figure — see progress.md Decisions log.
    population = person_rows[0]["n"] if person_rows else 0
    alerts = await _detect_cluster(client, rows)
    return aggregate_village_summary(rows, population=population, alerts=alerts)


@router.get("/autocomplete", response_model=VillageAutocompleteResponse)
async def autocomplete(prefix: str, request: Request) -> VillageAutocompleteResponse:
    client = getattr(request.app.state, "graph_client", None)
    if client is None:
        return VillageAutocompleteResponse(
            villages=[v for v in _MOCK_VILLAGES if prefix.lower() in v.lower()]
        )
    try:
        villages = await persistence.village_autocomplete(client, prefix)
        return VillageAutocompleteResponse(villages=villages)
    except Exception:
        return VillageAutocompleteResponse(villages=[])


@router.get("/{village_id}/summary", response_model=VillageSummaryResponse)
async def village_summary(village_id: str, request: Request) -> VillageSummaryResponse:
    client = getattr(request.app.state, "graph_client", None)
    if client is not None:
        try:
            summary = await _build_summary(client, village_id)
            if summary is not None:
                return summary
        except Exception:
            pass
    return _static_fallback()
