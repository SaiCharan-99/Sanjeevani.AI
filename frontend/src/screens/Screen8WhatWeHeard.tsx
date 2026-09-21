/** Wireframe 8 — What we heard (pain points review). Phase 4 — live.
 *
 * Human-in-the-loop is a feature, not a fallback (specs.md §2 screen 8): the
 * officer can remove or correct any extracted entry, and "+ Add a symptom"
 * opens screen 9. The reviewed list is what the rest of the pipeline uses, and
 * every correction is written back with the officer as its source.
 *
 * Reported complaints only — no consideration, no diagnosis language.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { PainPoint } from "../api/types";
import {
  Card,
  ConfidenceDot,
  Cta,
  FootNote,
  IconBtn,
  Kv,
  Note,
  Pill,
  PillRow,
  Quote,
  Tag,
  Top,
} from "../components/Primitives";
import { getSessionId, readPainPoints, storePainPoints } from "../capture/sessionStore";

const LANGUAGE_LABEL: Record<string, string> = { te: "Telugu", hi: "Hindi", en: "English" };

function contextChip(p: PainPoint): string {
  if (p.duration_days && p.duration_days >= 14) {
    return `${Math.round(p.duration_days / 7)} weeks · reported`;
  }
  if (p.duration_days) return `${p.duration_days} days · reported`;
  return "Reported";
}

export default function Screen8WhatWeHeard() {
  const navigate = useNavigate();
  const sessionId = getSessionId();

  const [points, setPoints] = useState<PainPoint[]>(() => readPainPoints() ?? []);
  const [redFlags, setRedFlags] = useState<string[]>([]);
  const [loading, setLoading] = useState(points.length === 0);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (points.length > 0) return;
    let cancelled = false;
    api
      .extractPainPoints(sessionId)
      .then((res) => {
        if (cancelled) return;
        setPoints(res.pain_points);
        setRedFlags(res.red_flag_messages ?? []);
        storePainPoints(res.pain_points);
      })
      .catch(() => undefined)
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function remove(index: number) {
    const next = points.filter((_, i) => i !== index);
    setPoints(next);
    storePainPoints(next);
  }

  async function saveAndContinue() {
    setSaving(true);
    storePainPoints(points);
    try {
      await api.savePainPoints({ session_id: sessionId, pain_points: points, edited_by: "officer" });
    } catch {
      /* the reviewed list is already in session memory; the backend write is
         best-effort, matching the rest of the graph-write path */
    }
    navigate("/10");
  }

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate("/7")}>‹</IconBtn>
        <Tag variant="accent">Officer control</Tag>
      </Top>

      <h2 className="text-[26px] font-bold mb-1.5">What we heard</h2>
      <p className="text-sm text-text-2 mb-5">
        Review these before we continue. Remove anything that was not reported, or add what was missed.
      </p>

      {redFlags.map((message) => (
        <Note tone="bad" title="Needs immediate attention" key={message}>
          {message}
        </Note>
      ))}

      {loading && <Note title="Reading the transcript">Preparing the review…</Note>}

      {!loading && points.length === 0 && (
        <Note title="Nothing extracted yet">
          No reported symptoms came back from this consultation. Add them by hand below.
        </Note>
      )}

      {points.map((p, i) => (
        <Card key={`${p.symptom}-${i}`}>
          <Kv
            left={
              <div>
                <h3 className="font-semibold capitalize">{p.symptom}</h3>
                <ConfidenceDot confidence={p.confidence} />
              </div>
            }
            right={
              <button aria-label={`Remove ${p.symptom}`} onClick={() => remove(i)} className="text-text-3">
                ✕
              </button>
            }
          />
          <PillRow>
            <Pill>{contextChip(p)}</Pill>
            {p.canonical ? <Pill>{p.canonical}</Pill> : <Pill>Not in the symptom list</Pill>}
          </PillRow>
          <Quote
            text={`"${p.verbatim}"`}
            sub={p.verbatim_original ? `${LANGUAGE_LABEL.te}: ${p.verbatim_original}` : undefined}
          />
        </Card>
      ))}

      <Cta ghost onClick={() => navigate("/9")}>
        + Add a symptom
      </Cta>
      <Cta onClick={saveAndContinue} disabled={saving}>
        {saving ? "Saving…" : "Continue →"}
      </Cta>
      <FootNote>Corrections are tracked in the audit log</FootNote>
    </>
  );
}
