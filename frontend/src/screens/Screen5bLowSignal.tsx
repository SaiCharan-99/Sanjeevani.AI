/** Wireframe 5b — Vitals results, low signal. Phase 2 — live. Shown when
 * overall_quality < 0.4. Retake is the only forward action — the wireframe's
 * "Continue with degraded vitals" button is NOT built (architecture.md §4,
 * absolute rule 4). */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Cta, IconBtn, Kv, Note, Tag, Top } from "../components/Primitives";
import { readVitalsResult } from "../capture/sessionStore";

export default function Screen5bLowSignal() {
  const navigate = useNavigate();
  const [qualityPct, setQualityPct] = useState(32);

  useEffect(() => {
    const stored = readVitalsResult();
    if (stored) setQualityPct(Math.round(stored.overall_quality * 100));
  }, []);

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate(-1)}>‹</IconBtn>
        <Tag variant="warn">● Caution</Tag>
      </Top>
      <Note tone="bad" title={`Signal quality was too low (${qualityPct}%)`}>
        Movement and low ambient light affected optical capture. Values cannot be validated.
      </Note>
      <Card><Kv left={<h3 className="font-semibold">Heart rate</h3>} right={<Tag variant="warn">Inconclusive</Tag>} /></Card>
      <Card><Kv left={<h3 className="font-semibold">Respiration rate</h3>} right={<Tag variant="warn">Inconclusive</Tag>} /></Card>
      <Card><Kv left={<h3 className="font-semibold">Oxygen saturation</h3>} right={<Tag variant="bad">Inconclusive</Tag>} /></Card>
      <Card><Kv left={<h3 className="font-semibold">Pallor signal</h3>} right={<Tag variant="warn">Inconclusive</Tag>} /></Card>
      <Note tone="warn" title="Field lighting tip">
        Seat the person in diffuse morning sunlight on the cheeks. Avoid canopy shadows.
      </Note>
      <Cta onClick={() => navigate("/4")}>↺ Retake scan</Cta>
    </>
  );
}
