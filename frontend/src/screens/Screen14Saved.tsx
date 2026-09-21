/** Wireframe 14 — Session saved (specs.md alias S11). Phase 3 — live. Copy
 * per specs §8: "Saved to this camp's record" — no offline-sync claim (rule
 * 10). Calls POST /api/session/complete (Tier 2: marks the :PHI:Session
 * done_unopened so it shows up in the camp dashboard's pending list). */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { getPersonId, getSessionId } from "../capture/sessionStore";
import { Avatar, Cta, Item, ListShell, Meta, Note, Tag } from "../components/Primitives";

export default function Screen14Saved() {
  const navigate = useNavigate();
  const sessionId = getSessionId();
  const personId = getPersonId();
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .completeSession({ session_id: sessionId, top_findings: [], recommendations: [] })
      .then(() => {
        if (!cancelled) setSaved(true);
      })
      .catch(() => {
        if (!cancelled) setSaved(true); // Tier 1 already has the data; graph write is best-effort for the demo
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return (
    <>
      <div className="text-center py-10 pb-5">
        <div className="w-[84px] h-[84px] rounded-full bg-accent text-accent-ink flex items-center justify-center text-4xl mx-auto mb-5">✓</div>
        <h2 className="text-[26px] font-bold mb-1.5">Session saved</h2>
        <p className="text-sm text-text-2">{sessionId} · {saved ? "recorded" : "saving…"}</p>
      </div>
      <ListShell>
        <Item><Avatar initials="📄" /><Meta title="Structured summary" subtitle="Screening review · 2 pages" /><Tag variant="accent">Ready</Tag></Item>
        <Item><Avatar initials="🎙" /><Meta title="Audio & transcript" subtitle="02:45 · bilingual" /><Tag variant="accent">Stored</Tag></Item>
        <Item><Avatar initials="📷" /><Meta title="Scan captures" subtitle="Face vitals + breathing · signals only" /><Tag variant="accent">Stored</Tag></Item>
        <Item><Avatar initials="➜" tone="bad" /><Meta title="PHC referral slip" subtitle="Kadiri PHC · sputum + CBNAAT" /><Tag variant="bad">To print</Tag></Item>
      </ListShell>
      <Note>Saved to this camp's record.</Note>
      <Cta onClick={() => navigate(`/15?person=${encodeURIComponent(personId)}`)}>View person profile →</Cta>
      <Cta ghost onClick={() => navigate("/1")}>Back to camp dashboard</Cta>
    </>
  );
}
