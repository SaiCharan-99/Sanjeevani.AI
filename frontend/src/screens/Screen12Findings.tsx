/** Wireframe 12 — Findings. Phase 5 — live. Renders the findings accumulated
 * from screen 11's guided captures (session handoff via sessionStore), plus
 * the passive vitals findings already captured in screen 4/5, grouped by
 * capture. Each finding: value, unit, method line, interpretation line,
 * confidence, limitations note (specs.md §5). */
import { useNavigate } from "react-router-dom";
import type { Finding } from "../api/types";
import { readSecondLookFindings, readVitalsResult } from "../capture/sessionStore";
import { Bar, Card, Cta, IconBtn, Kv, Note, Sec, Tag, Top } from "../components/Primitives";

function toneForConfidence(confidence: number): { text: string; bar: string } {
  if (confidence >= 0.7) return { text: "text-accent", bar: "bg-accent" };
  if (confidence >= 0.4) return { text: "text-warn", bar: "bg-warn" };
  return { text: "text-bad", bar: "bg-bad" };
}

function FindingCard({ finding }: { finding: Finding }) {
  const tone = toneForConfidence(finding.confidence);
  return (
    <Card>
      <Kv
        left={
          <div>
            <h3 className="font-semibold capitalize">{finding.feature.replace(/_/g, " ")}</h3>
            <p className="text-text-2 text-[13px]">{finding.method}</p>
          </div>
        }
        right={
          <div>
            <span className={`text-[30px] font-bold ${tone.text}`}>{finding.value}</span>{" "}
            <span className="text-[13px] text-text-3">{finding.unit}</span>
          </div>
        }
      />
      <div className="mt-3.5">
        <Bar pct={Math.round(finding.confidence * 100)} color={tone.bar} />
      </div>
      <p className="mt-2 text-sm">{finding.interpretation}</p>
      <p className="mt-1.5 text-xs text-text-3">{finding.limitations}</p>
    </Card>
  );
}

export default function Screen12Findings() {
  const navigate = useNavigate();
  const secondLookFindings = readSecondLookFindings() ?? [];
  const vitals = readVitalsResult();

  const hasAny = secondLookFindings.length > 0 || vitals !== null;

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate("/10")}>‹</IconBtn>
        <Tag variant="accent">Captures complete</Tag>
      </Top>
      <h2 className="text-[26px] font-bold mb-1.5">Findings</h2>
      <p className="text-sm text-text-2 mb-5">
        {secondLookFindings.length > 0
          ? "The guided capture combined with the reported symptoms."
          : "Passive vitals combined with the reported symptoms."}
      </p>

      {!hasAny && <Note title="No findings yet">Run a capture from the previous step, or continue to the assessment.</Note>}

      {secondLookFindings.length > 0 && (
        <>
          <Sec title="From the guided capture" right="good" />
          {secondLookFindings.map((f, i) => (
            <FindingCard key={`${f.feature}-${i}`} finding={f} />
          ))}
        </>
      )}

      {vitals && (
        <>
          <Sec title="From the face scan" right={`${vitals.overall_quality >= 0.6 ? "good" : "low"}`} />
          <Card>
            <Kv
              left={<h3 className="font-semibold">Heart rate</h3>}
              right={
                <div>
                  <span className="text-[30px] font-bold text-accent">{vitals.heart_rate.value}</span>{" "}
                  <span className="text-[13px] text-text-3">{vitals.heart_rate.unit}</span>
                </div>
              }
            />
          </Card>
          <Card>
            <Kv
              left={<h3 className="font-semibold">SpO₂ (approximate)</h3>}
              right={
                <div>
                  <span className="text-[30px] font-bold text-warn">{vitals.spo2.value}</span>{" "}
                  <span className="text-[13px] text-text-3">{vitals.spo2.unit}</span>
                </div>
              }
            />
          </Card>
          <Card>
            <Kv
              left={<h3 className="font-semibold">Pallor (passive)</h3>}
              right={<Tag variant={vitals.passive_findings.pallor_score >= 0.6 ? "warn" : "mute"}>{vitals.passive_findings.pallor_score >= 0.6 ? "Moderate likelihood" : "Low"}</Tag>}
            />
          </Card>
        </>
      )}

      <Note>These are screening signals, not diagnoses. The assessment combines them with the symptom history.</Note>
      <Cta onClick={() => navigate("/13")}>See assessment →</Cta>
    </>
  );
}
