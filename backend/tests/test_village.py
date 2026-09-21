"""Village dashboard (screen 17, Phase 7) tests.

`cluster_alerts_from_rows` and `aggregate_village_summary` are pure — no I/O —
so the wireframe's "3x baseline over 6 days" rule and the
screened/referred/followups-due/hamlet aggregation are tested directly against
fabricated `VILLAGE_MATCHING_SESSIONS`-shaped rows, no live Neo4j required
(same approach as test_memory.py / test_synthesis.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.api.village import (
    CLUSTER_MIN_COUNT,
    CLUSTER_MULTIPLE,
    CLUSTER_WINDOW_DAYS,
    aggregate_village_summary,
    cluster_alerts_from_rows,
)

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)


def _row(village_name, days_ago, symptoms, recommendations=None, status="done_unopened"):
    created_at = (NOW - timedelta(days=days_ago)).isoformat()
    return {
        "village_name": village_name,
        "session_id": f"s_{village_name}_{days_ago}",
        "created_at": created_at,
        "status": status,
        "recommendations": recommendations or [],
        "symptoms": symptoms,
    }


def test_waterborne_cluster_fires_at_3x_baseline_over_6_days():
    # 8 waterborne cases in the last 6 days ("Peddapuram" hamlet), vs ~1/window
    # baseline over the prior 4 windows (24 days) — mirrors demo_seed.py.
    rows = [_row("Peddapuram", d, ["abdominal_pain", "fatigue"]) for d in [0.5, 1, 1.5, 2, 3, 4, 5, 5.5]]
    rows += [_row("Peddapuram", d, ["abdominal_pain"]) for d in [9, 15, 21, 27]]

    alerts = cluster_alerts_from_rows(
        rows, cluster_symptoms={"abdominal_pain", "fatigue"}, mitigation="Check the shared water source.", now=NOW
    )

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.kind == "cluster"
    assert alert.ward == "Peddapuram"
    assert alert.window_days == CLUSTER_WINDOW_DAYS
    assert alert.count == 8
    assert alert.baseline_multiple >= CLUSTER_MULTIPLE
    assert alert.suggestion == "Check the shared water source."


def test_no_alert_when_no_prior_spike():
    # Only 2 cases ever reported — below CLUSTER_MIN_COUNT, never alerts.
    rows = [_row("Kadiri West", d, ["abdominal_pain"]) for d in [1, 2]]
    alerts = cluster_alerts_from_rows(rows, cluster_symptoms={"abdominal_pain"}, mitigation="x", now=NOW)
    assert alerts == []
    assert CLUSTER_MIN_COUNT >= 2  # sanity: fixture is intentionally below threshold


def test_no_alert_when_baseline_keeps_pace():
    # Steady rate: ~8 cases every 6-day window, this window included — no spike.
    days = [0.5, 1, 1.5, 2, 3, 4, 5, 5.5]  # window 0
    for w in range(1, 5):
        days += [w * CLUSTER_WINDOW_DAYS + d for d in [0.5, 1, 1.5, 2, 3, 4, 5, 5.5]]
    rows = [_row("Steadyville", d, ["abdominal_pain"]) for d in days]
    alerts = cluster_alerts_from_rows(rows, cluster_symptoms={"abdominal_pain"}, mitigation="x", now=NOW)
    assert alerts == []


def test_unrelated_symptoms_never_contribute_to_the_cluster():
    rows = [_row("Peddapuram", d, ["cough"]) for d in range(1, 10)]
    alerts = cluster_alerts_from_rows(rows, cluster_symptoms={"abdominal_pain", "fatigue"}, mitigation="x", now=NOW)
    assert alerts == []


def test_empty_cluster_symptom_set_never_alerts():
    rows = [_row("Peddapuram", 1, ["abdominal_pain"])]
    assert cluster_alerts_from_rows(rows, cluster_symptoms=set(), mitigation="x", now=NOW) == []


def test_aggregate_village_summary_counts_and_hamlets():
    rows = [
        _row("Peddapuram", 1, ["abdominal_pain"], recommendations=["ORS"], status="done_unopened"),
        _row("Peddapuram", 2, ["fatigue"], recommendations=[], status="queued"),
        _row("Kothapalli", 3, ["cough"], recommendations=["Referral"], status="done_unopened"),
    ]
    summary = aggregate_village_summary(rows, population=42, alerts=[], now=NOW)

    assert summary.population == 42
    assert summary.screened_quarter == 3
    assert summary.referred == 2  # rows 1 and 3 have non-empty recommendations
    assert summary.followups_due == 2  # rows 1 and 3 are done_unopened

    slugs = {s.slug for s in summary.top_symptoms}
    assert slugs == {"abdominal_pain", "fatigue", "cough"}

    names = {h.name for h in summary.hamlets}
    assert names == {"Peddapuram", "Kothapalli"}


def test_aggregate_village_summary_trend_groups_by_month():
    rows = [
        _row("Peddapuram", 1, [], status="done_unopened"),  # this month
        _row("Peddapuram", 400, [], status="done_unopened"),  # over a year ago — still in `trend`, not in quarter stats
    ]
    summary = aggregate_village_summary(rows, population=10, alerts=[], now=NOW)
    # The 400-day-old row falls outside the 90-day quarter window.
    assert summary.screened_quarter == 1
    # But trend is built from every row, not just the quarter — two distinct months.
    months = {t.month for t in summary.trend}
    assert len(months) == 2
