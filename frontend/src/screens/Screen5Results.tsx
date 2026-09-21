/** Wireframe 5 — Vitals results. Phase 2 — live. No composite health score
 * (rule 9) — shows the overall quality badge instead. Renders the real
 * /api/vitals/process response stored by screen 4; falls back to the
 * golden-path values (specs §1/§8) only if no scan has run yet in this
 * session (e.g. navigated here directly from the rail). */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Avatar, Bar, Card, Cta, Item, Kv, Meta, Note, Tabs, Tag, Top, IconBtn } from "../components/Primitives";
import type { VitalsProcessResponse } from "../api/types";
import { readVitalsResult, getSessionId } from "../capture/sessionStore";
import { api, BASE_URL } from "../api/client";

const GOLDEN_PATH_FALLBACK: VitalsProcessResponse = {
  heart_rate: { value: 96, unit: "bpm", quality: 0.86, tier: "reliable" },
  respiration_rate: { value: 22, unit: "brpm", quality: 0.71, tier: "reliable" },
  spo2: { value: 94, unit: "%", quality: 0.63, tier: "approximate" },
  bp_trend: { direction: "elevated", quality: 0.41, tier: "trend_only" },
  passive_findings: { pallor_score: 0.7, facial_tension: 0.4, blink_rate: 14 },
  overall_quality: 0.74,
  retake_recommended: false,
};

function bandPct(quality: number): number {
  return Math.round(Math.min(1, Math.max(0, quality)) * 100);
}

export default function Screen5Results() {
  const navigate = useNavigate();
  const [tab, setTab] = useState(0);
  const [result, setResult] = useState<VitalsProcessResponse>(GOLDEN_PATH_FALLBACK);
  const [downloading, setDownloading] = useState(false);

  async function downloadReport() {
    setDownloading(true);
    try {
      const { pdf_url } = await api.generateReport(getSessionId());
      window.open(`${BASE_URL}${pdf_url}`, "_blank");
    } catch {
      /* backend unreachable in this sandbox — no forced-failure UI, matches the
       * graceful-fallback pattern the rest of the app uses when Neo4j/Gemini
       * aren't available. */
    } finally {
      setDownloading(false);
    }
  }

  useEffect(() => {
    const stored = readVitalsResult();
    if (stored) setResult(stored);
  }, []);

  const anemiaLikelihood =
    result.passive_findings.pallor_score >= 0.6
      ? "High"
      : result.passive_findings.pallor_score >= 0.35
        ? "Moderate"
        : "Low";

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate(-1)}>‹</IconBtn>
        <Tag variant="accent">Signal quality {Math.round(result.overall_quality * 100)}%</Tag>
      </Top>
      <Tabs tabs={["Key body vitals", "Heart health", "Stress level"]} active={tab} onChange={setTab} />
      <Card>
        <Kv
          left={<div><h3 className="font-semibold">Heart rate</h3><p className="text-text-2 text-[13px]">Rhythm pulse wave</p></div>}
          right={<div><span className="text-[30px] font-bold text-accent">{result.heart_rate.value}</span> <span className="text-[13px] text-text-3">{result.heart_rate.unit}</span></div>}
        />
        <div className="mt-4"><Bar pct={bandPct(result.heart_rate.quality)} /></div>
      </Card>
      <Card>
        <Kv
          left={<div><h3 className="font-semibold">Respiration rate</h3><p className="text-text-2 text-[13px]">Micro-chest displacement</p></div>}
          right={<div><span className="text-[30px] font-bold text-warn">{result.respiration_rate.value}</span> <span className="text-[13px] text-text-3">{result.respiration_rate.unit}</span></div>}
        />
        <div className="mt-4"><Bar pct={bandPct(result.respiration_rate.quality)} color="bg-warn" /></div>
      </Card>
      <Card>
        <Kv
          left={<div><h3 className="font-semibold">Oxygen saturation</h3><Tag variant="warn">Approximate</Tag></div>}
          right={<div><span className="text-[30px] font-bold text-warn">{result.spo2.value}</span> <span className="text-[13px] text-text-3">%</span></div>}
        />
      </Card>
      <Card>
        <Kv left={<div><h3 className="font-semibold">Blood pressure</h3><Tag variant="mute">Trend only — not a measurement</Tag></div>} />
        <Item>
          <Avatar initials={result.bp_trend.direction === "elevated" ? "↗" : result.bp_trend.direction === "low" ? "↘" : "→"} />
          <Meta
            title={`Trending ${result.bp_trend.direction}`}
            subtitle={result.bp_trend.direction === "elevated" ? "Cuff check advised" : "No action needed"}
          />
        </Item>
      </Card>
      <Card>
        <Kv left={<div><h3 className="font-semibold">Anemia indicator</h3><Tag variant="mute">Screening signal</Tag></div>} />
        <p className="mt-3 text-sm">
          {anemiaLikelihood} likelihood — pallor score {result.passive_findings.pallor_score.toFixed(2)} across conjunctiva
          and facial microvasculature. CBC suggested.
        </p>
      </Card>
      <Note>
        Signal quality was {Math.round(result.overall_quality * 100) >= 70 ? "good" : "fair"} (
        {Math.round(result.overall_quality * 100)}%). Values marked approximate should be confirmed with a device.
      </Note>
      <Cta ghost disabled={downloading} onClick={downloadReport}>{downloading ? "Preparing report…" : "Download report"}</Cta>
      <Cta onClick={() => navigate("/6")}>Start consultation →</Cta>
    </>
  );
}
