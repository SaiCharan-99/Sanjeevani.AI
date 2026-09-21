/** Wireframe 9 — Edit symptoms. Phase 4 — live.
 *
 * Manual add: the picker searches the real symptom vocabulary
 * (GET /api/kb/symptoms, slug + name + aliases). Free text is allowed and, when
 * it matches no slug, is stored as `unmapped_text` with `canonical: null`
 * (specs.md §3) — the runtime never creates a :KB:Symptom.
 *
 * Entries added here are attributed to the officer in the audit log.
 */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { PainPoint, SymptomOut } from "../api/types";
import {
  Avatar,
  Card,
  Cta,
  Field,
  IconBtn,
  Item,
  ListShell,
  Meta,
  Note,
  Sec,
  Tag,
  Top,
} from "../components/Primitives";
import { getSessionId, readPainPoints, storePainPoints } from "../capture/sessionStore";

/** Confidence recorded for an entry the officer typed in themselves. It is the
 * officer's own report, so it is certain as evidence — the clinical weight
 * still comes from the graph edge, not from this number. */
const OFFICER_CONFIDENCE = 1.0;

export default function Screen9EditSymptoms() {
  const navigate = useNavigate();
  const sessionId = getSessionId();

  const [catalogue, setCatalogue] = useState<SymptomOut[]>([]);
  const [query, setQuery] = useState("");
  const [note, setNote] = useState("");
  const [selected, setSelected] = useState<SymptomOut | null>(null);
  const [points, setPoints] = useState<PainPoint[]>(() => readPainPoints() ?? []);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .listSymptoms()
      .then(setCatalogue)
      .catch(() => setCatalogue([]));
  }, []);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return catalogue
      .filter(
        (s) =>
          s.slug.includes(q.replace(/\s+/g, "_")) ||
          s.name.toLowerCase().includes(q) ||
          s.aliases.some((a) => a.toLowerCase().includes(q))
      )
      .slice(0, 6);
  }, [query, catalogue]);

  function insert() {
    const text = query.trim();
    if (!text && !selected) return;
    const entry: PainPoint = selected
      ? {
          symptom: selected.name,
          canonical: selected.slug,
          confidence: OFFICER_CONFIDENCE,
          verbatim: note.trim() || selected.name,
          unmapped_text: null,
        }
      : {
          symptom: text,
          canonical: null,
          confidence: OFFICER_CONFIDENCE,
          verbatim: note.trim() || text,
          unmapped_text: text,
        };
    const next = [...points, entry];
    setPoints(next);
    storePainPoints(next);
    setQuery("");
    setNote("");
    setSelected(null);
  }

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
      /* best-effort write, same as the rest of the graph path */
    }
    navigate("/8");
  }

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate("/8")}>‹</IconBtn>
        <Tag variant="accent">Editing</Tag>
      </Top>

      <h2 className="text-[26px] font-bold mb-1.5">Editing reported symptoms</h2>
      <p className="text-sm text-text-2 mb-5">
        Manual add — entries are attributed to you in the audit log.
      </p>

      <Card>
        <label className="block font-semibold text-[13px] text-text-2 mb-2">Symptom</label>
        <Field
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelected(null);
          }}
          placeholder="Search the symptom list, or free text"
          className="mb-2"
        />
        {matches.length > 0 && (
          <div className="mb-4 flex flex-wrap gap-2">
            {matches.map((m) => (
              <button
                key={m.slug}
                onClick={() => {
                  setSelected(m);
                  setQuery(m.name);
                }}
                className={`h-9 px-3.5 rounded-full border text-[13px] font-semibold ${
                  selected?.slug === m.slug
                    ? "bg-accent border-accent text-accent-ink"
                    : "bg-surface-2 border-line text-text-2"
                }`}
              >
                {m.name}
              </button>
            ))}
          </div>
        )}
        {query.trim() && matches.length === 0 && (
          <p className="text-[12.5px] text-text-3 mb-4">
            No match in the symptom list — this will be kept as free text for later mapping.
          </p>
        )}
        <label className="block font-semibold text-[13px] text-text-2 mb-2">Clinical note</label>
        <Field
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Observation / context"
        />
        <Cta onClick={insert} disabled={!query.trim() && !selected}>
          Insert symptom
        </Cta>
      </Card>

      <Sec title="Current list" right={`${points.length} items`} />
      <ListShell>
        {points.length === 0 && (
          <Item>
            <Meta title="Nothing on the list yet" subtitle="Add a symptom above" />
          </Item>
        )}
        {points.map((p, i) => (
          <Item key={`${p.symptom}-${i}`}>
            <Avatar initials="●" tone={p.canonical ? "accent" : "bad"} />
            <Meta
              title={p.symptom}
              subtitle={`${p.canonical ?? "free text · not in the symptom list"} · ${Math.round(
                p.confidence * 100
              )}%`}
            />
            <button aria-label={`Remove ${p.symptom}`} onClick={() => remove(i)} className="text-text-3">
              ✕
            </button>
          </Item>
        ))}
      </ListShell>

      <Note title="Human-in-the-loop">
        {points.length} reported {points.length === 1 ? "symptom" : "symptoms"} · reviewed by Dr. Meera Rao,
        Medical Health Officer. Free text without a match stays unmapped until it is mapped by hand.
      </Note>

      <Cta onClick={saveAndContinue} disabled={saving}>
        {saving ? "Saving…" : "Save and continue →"}
      </Cta>
    </>
  );
}
