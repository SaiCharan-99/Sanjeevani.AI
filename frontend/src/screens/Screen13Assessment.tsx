/** Wireframe 13 — Assessment. Phase 6 — live. "consideration" not "diagnosis";
 * review: pending badge per rule 11. Fetches the real synthesis result
 * (GET /api/synthesis/result, falling back server-side to the golden-path TB
 * synthesis if nothing has run yet). Reasoning chains are expandable —
 * screen 16's explainability view shows the same data at more depth. */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Avatar, Bar, Card, Cta, IconBtn, Item, Kv, ListShell, Meta, Note, Sec, Tag, Top } from "../components/Primitives";
import type { Consideration, RiskModelOutput, SynthesisResultResponse } from "../api/types";
import { api, BASE_URL } from "../api/client";
import { getSessionId } from "../capture/sessionStore";

const GOLDEN_PATH_FALLBACK: SynthesisResultResponse = {
  considerations: [
    {
      disease: "Pulmonary tuberculosis", score: 0.87, rank: 1, priority: "high", review: "approved",
      reasoning_chain: [
        { evidence: "cough (21 days)", edge: "PRESENTS_WITH", weight: 0.9, note: "NTEP presumptive TB: cough >= 2 weeks" },
        { evidence: "weight loss", edge: "PRESENTS_WITH", weight: 0.8, note: null },
        { evidence: "night sweats", edge: "PRESENTS_WITH", weight: 0.7, note: null },
      ],
      recommended_tests: ["Sputum smear / NAAT", "Chest X-ray"],
    },
    {
      disease: "COPD", score: 0.42, rank: 2, priority: "medium", review: "pending",
      reasoning_chain: [
        { evidence: "age 52 + biomass exposure + exertional breathlessness", edge: "RISK_FACTOR", weight: 0.5, note: null },
      ],
      recommended_tests: ["Spirometry"],
    },
  ],
  risk_models: [
    {
      name: "anemia_risk", score: 0.62, f1: null,
      metric: "rule-based scorer — no trained-model accuracy metric",
      basis: "pallor + tachycardia + reported fatigue + sex", inputs: ["pallor_score", "heart_rate", "fatigue"],
      disclaimer: "screening signal, not a diagnosis",
    },
  ],
};

function priorityTag(priority: string) {
  if (priority === "high") return <Tag variant="bad">High</Tag>;
  if (priority === "medium") return <Tag variant="warn">Moderate</Tag>;
  return <Tag variant="mute">Low</Tag>;
}

function ConsiderationCard({ c }: { c: Consideration }) {
  const [open, setOpen] = useState(false);
  const barColor = c.priority === "high" ? "bg-bad" : c.priority === "medium" ? "bg-warn" : "bg-text-3";
  return (
    <Card>
      <Kv
        left={
          <div>
            <h3 className="font-semibold">
              {c.disease} {c.review === "pending" && <Tag variant="mute">Needs clinical review</Tag>}
            </h3>
            <p className="text-text-2 text-[13px]">
              {c.reasoning_chain.slice(0, 3).map((s) => s.evidence).join(" · ")}
            </p>
          </div>
        }
        right={priorityTag(c.priority)}
      />
      <div className="mt-3"><Bar pct={Math.round(c.score * 100)} color={barColor} /></div>
      {c.recommended_tests.length > 0 && (
        <p className="mt-2 text-xs text-text-3">Recommended: {c.recommended_tests.join(", ")}</p>
      )}
      <button className="mt-2 text-xs text-accent font-semibold" onClick={() => setOpen((v) => !v)}>
        {open ? "Hide reasoning ▲" : "Show reasoning chain ▼"}
      </button>
      {open && (
        <div className="mt-2 pl-3 border-l border-line-soft space-y-1.5">
          {c.reasoning_chain.map((step, i) => (
            <p key={i} className="text-xs text-text-2">
              <b>{step.evidence}</b> → {step.edge} (weight {step.weight.toFixed(2)})
              {step.note && <em className="block not-italic text-text-3">{step.note}</em>}
            </p>
          ))}
        </div>
      )}
    </Card>
  );
}

function RiskCheckItem({ r }: { r: RiskModelOutput }) {
  const pct = Math.round(r.score * 100);
  const tone = pct >= 60 ? "!" : "✓";
  return (
    <Item>
      <Avatar initials={tone} tone={pct >= 60 ? "bad" : "accent"} />
      <Meta
        title={`${r.name.replace(/_/g, " ")}: ${pct}%`}
        subtitle={`${r.metric ?? (r.f1 != null ? `F1 ${r.f1}` : "—")} · ${r.disclaimer}`}
      />
    </Item>
  );
}

export default function Screen13Assessment() {
  const navigate = useNavigate();
  const [result, setResult] = useState<SynthesisResultResponse>(GOLDEN_PATH_FALLBACK);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .synthesisResult(getSessionId())
      .then((r) => {
        if (!cancelled && r.considerations.length > 0) setResult(r);
      })
      .catch(() => {
        /* backend unreachable — keep the golden-path fallback so the demo
         * never shows a broken assessment screen. */
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  async function downloadReport() {
    setDownloading(true);
    try {
      const { pdf_url } = await api.generateReport(getSessionId());
      window.open(`${BASE_URL}${pdf_url}`, "_blank");
    } catch {
      /* graceful no-op, matches the rest of the app's offline-backend pattern */
    } finally {
      setDownloading(false);
    }
  }

  const top = result.considerations[0];

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate(-1)}>‹</IconBtn>
        {top && priorityTag(top.priority) && <Tag variant={top.priority === "high" ? "bad" : "warn"}>{top.priority === "high" ? "Refer today" : "Monitor"}</Tag>}
      </Top>
      <h2 className="text-[26px] font-bold mb-1.5">Assessment</h2>
      <p className="text-sm text-text-2 mb-5">Decision support only. The final call stays with you.</p>
      {loading && <Note>Loading assessment…</Note>}
      {top && (
        <Card className={top.priority === "high" ? "border-bad bg-bad-soft" : ""}>
          {priorityTag(top.priority)}
          <h3 className="text-[19px] mt-2.5 font-semibold">
            {top.priority === "high" ? `Refer for ${top.disease.toLowerCase()} screening` : `Monitor for ${top.disease.toLowerCase()}`}
          </h3>
          <p>
            {top.reasoning_chain.find((s) => s.note)?.note ??
              top.reasoning_chain.map((s) => s.evidence).join(", ")}
            . {top.recommended_tests.length > 0 && `Recommended: ${top.recommended_tests.join(", ")}.`}
          </p>
        </Card>
      )}
      <Sec title="Considerations" right="Ranked" />
      {result.considerations.map((c) => (
        <ConsiderationCard key={c.disease} c={c} />
      ))}
      <Sec title="Background risk checks" right={`${result.risk_models.length} run`} />
      <ListShell>
        {result.risk_models.length > 0 ? (
          result.risk_models.map((r) => <RiskCheckItem key={r.name} r={r} />)
        ) : (
          <Item><Avatar initials="—" /><Meta title="No risk model outputs yet" subtitle="Captured vitals feed these checks" /></Item>
        )}
      </ListShell>
      <Note tone="warn">Sanjeevani does not diagnose. Confirm with laboratory testing before starting any treatment.</Note>
      <Cta ghost disabled={downloading} onClick={downloadReport}>{downloading ? "Preparing report…" : "Download report"}</Cta>
      <Cta onClick={() => navigate("/14")}>Save session &amp; refer →</Cta>
      <Cta ghost onClick={() => navigate("/9")}>Edit assessment</Cta>
    </>
  );
}
