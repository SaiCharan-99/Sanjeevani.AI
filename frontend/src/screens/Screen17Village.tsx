/** Wireframe 17 — Village dashboard. Phase 7 — live. Aggregates only; no
 * person identifiers (specs.md §2 screen 17, copy substitution: "individual
 * records are not shown", not "never leave the device"). Composed from the
 * component vocabulary — see progress.md Decisions log on the wireframe not
 * carrying this screen's markup.
 *
 * Reads `GET /api/village/{village_id}/summary`, which aggregates real
 * :PHI:Session / :PHI:Utterance data server-side (backend/app/api/village.py)
 * — this screen only renders the finished aggregate, never raw per-person
 * rows. Defaults to the seeded demo village ("Peddapuram",
 * backend/app/graph/demo_seed.py) so the cluster-alert story renders without
 * requiring the officer to search first; `?village=` overrides it. */
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { VillageSummaryResponse } from "../api/types";
import { Bar, Card, FootNote, IconBtn, Item, Kv, ListShell, Meta, Sec, Stat, StatRow, Tag, Top } from "../components/Primitives";

const DEFAULT_VILLAGE = "Peddapuram";

export default function Screen17Village() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const villageId = params.get("village") ?? DEFAULT_VILLAGE;
  const [summary, setSummary] = useState<VillageSummaryResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getVillageSummary(villageId)
      .then((res) => {
        if (!cancelled) setSummary(res);
      })
      .catch(() => {
        if (!cancelled) setSummary(null);
      });
    return () => {
      cancelled = true;
    };
  }, [villageId]);

  if (!summary) {
    return (
      <>
        <Top>
          <IconBtn onClick={() => navigate(-1)}>‹</IconBtn>
        </Top>
        <p className="text-sm text-text-2 text-center py-10">Loading village dashboard…</p>
      </>
    );
  }

  const maxTopSymptom = Math.max(1, ...summary.top_symptoms.map((s) => s.count));
  const clusterAlert = summary.alerts.find((a) => a.kind === "cluster");

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate(-1)}>‹</IconBtn>
        <Tag variant="accent">
          {villageId} · pop. {summary.population}
        </Tag>
      </Top>
      <h2 className="text-[26px] font-bold mb-1.5">Village dashboard</h2>
      <p className="text-sm text-text-2 mb-5">{summary.screened_quarter} screened this quarter.</p>

      {clusterAlert && (
        <Card className="border-bad bg-bad-soft">
          <Tag variant="bad">Cluster alert</Tag>
          <h3 className="text-[17px] mt-2 font-semibold">
            {clusterAlert.disease_group.replace(/_/g, " ")} — {clusterAlert.baseline_multiple}x baseline
          </h3>
          <p>
            {clusterAlert.count} cases in {clusterAlert.ward} over {clusterAlert.window_days} days. Suggested:{" "}
            {clusterAlert.suggestion}
          </p>
        </Card>
      )}

      <StatRow>
        <Stat label="Screened" value={summary.screened_quarter} />
        <Stat label="Referred" value={summary.referred} tone="warn" />
        <Stat label="Follow-ups due" value={summary.followups_due} />
      </StatRow>

      <Sec title="Most-reported symptoms" />
      <Card>
        {summary.top_symptoms.length === 0 && <p className="text-sm text-text-3">No symptoms reported yet.</p>}
        {summary.top_symptoms.map((s, i) => (
          <div key={s.slug} className={i < summary.top_symptoms.length - 1 ? "mb-2" : ""}>
            <Kv left={s.slug.replace(/_/g, " ")} right={String(s.count)} />
            <div className="mt-1">
              <Bar pct={Math.round((s.count / maxTopSymptom) * 100)} />
            </div>
          </div>
        ))}
      </Card>

      <Sec title="Hamlet breakdown" />
      <ListShell>
        {summary.hamlets.length === 0 && (
          <Item>
            <Meta title="No hamlet data yet" />
          </Item>
        )}
        {summary.hamlets.map((h) => (
          <Item key={h.name}>
            <Meta title={h.name} subtitle={`${h.screened} screened · ${h.referred} referred`} />
            <Tag variant={h.status === "attention" ? "warn" : "mute"}>{h.status === "attention" ? "Attention" : "OK"}</Tag>
          </Item>
        ))}
      </ListShell>

      <FootNote>Aggregated locally · individual records are not shown</FootNote>
    </>
  );
}
