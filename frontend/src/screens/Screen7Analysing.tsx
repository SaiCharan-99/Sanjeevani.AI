/** Wireframe 7 — Analysing. Phase 4 — live.
 *
 * Runs the real pipeline after screen 6 stops: final transcription (which also
 * performs content-based speaker attribution on the backend) then pain-point
 * extraction, with the four-step checklist reflecting actual progress. Routes
 * to screen 8 when the extraction returns.
 *
 * Copy per specs.md §8: "Preparing the review…" not "Generating clinical
 * report…"; "Structured summary & screening priority" not "SOAP format &
 * triage tier"; "Audio is sent for transcription; video never leaves the
 * device" — no encryption or on-device-processing claim (rule 10).
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Avatar, Bar, Card, Cta, FootNote, IconBtn, Meta, Note, Tag, Top } from "../components/Primitives";
import { formatElapsed, takePendingAudio } from "../capture/audio";
import {
  getLanguage,
  getSessionId,
  readAudioMeta,
  readPainPoints,
  readTranscript,
  storePainPoints,
  storeTranscript,
} from "../capture/sessionStore";

type StepStatus = "pending" | "active" | "done";

const STEPS = [
  { key: "transcribe", label: "Transcribing", sub: "Audio converted to a bilingual transcript" },
  { key: "attribute", label: "Identifying speakers", sub: "By what was said, not by voice" },
  { key: "extract", label: "Extracting symptoms", sub: "Reported complaints, in the person's words" },
  { key: "structure", label: "Structuring summary", sub: "Vitals, symptoms & screening priority" },
] as const;

const LANGUAGE_TAG: Record<string, string> = { en: "English", te: "తెలుగు", hi: "हिन्दी" };

export default function Screen7Analysing() {
  const navigate = useNavigate();
  const sessionId = getSessionId();
  const language = getLanguage();
  const audioMeta = readAudioMeta();
  const startedRef = useRef(false);

  const [stepIndex, setStepIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    async function run() {
      try {
        const recorded = takePendingAudio();
        if (recorded) {
          const transcript = await api.transcribe(sessionId, language, recorded.blob);
          storeTranscript(transcript.turns);
        } else if (!readTranscript()) {
          // Arrived here without a recording (deep link or a reload) — the
          // backend still holds the session's transcript in working memory.
          const transcript = await api.transcribe(sessionId, language, new Blob([], { type: "audio/webm" }));
          storeTranscript(transcript.turns);
        }
        setStepIndex(2); // transcription + attribution both come back from /transcribe

        const extracted = await api.extractPainPoints(sessionId);
        storePainPoints(extracted.pain_points);
        setStepIndex(3);

        window.setTimeout(() => navigate("/8"), 600);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not prepare the review");
      }
    }

    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function statusOf(i: number): StepStatus {
    if (i < stepIndex) return "done";
    if (i === stepIndex) return "active";
    return "pending";
  }

  const pct = Math.round(((stepIndex + 1) / STEPS.length) * 100);
  const alreadyExtracted = Boolean(readPainPoints());

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate("/6")}>‹</IconBtn>
        <Tag variant="accent">{LANGUAGE_TAG[language] ?? "English"}</Tag>
      </Top>

      <Card className="flex items-center gap-3">
        <Avatar initials="🎙" />
        <Meta
          title={`Audio recorded · ${formatElapsed(audioMeta?.durationS ?? 0)}`}
          subtitle={`Ramesh Kumar (52M) · ${sessionId}`}
        />
        <Tag variant="accent">Saved</Tag>
      </Card>

      <Card className="text-center py-7">
        <div className="text-3xl">🧠</div>
        <h3 className="text-lg mt-2.5 font-semibold">Understanding the conversation</h3>
        <p className="text-text-2 text-sm">Preparing screening signals from the transcript</p>
        <div className="text-left mt-5 flex flex-col gap-4">
          {STEPS.map((s, i) => {
            const status = statusOf(i);
            return (
              <div key={s.key} className="flex items-center gap-3">
                <span
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                    status === "done"
                      ? "bg-accent text-accent-ink"
                      : status === "active"
                        ? "bg-accent-soft text-accent"
                        : "bg-surface-2 text-text-3"
                  }`}
                >
                  {status === "done" ? "✓" : status === "active" ? "●" : "○"}
                </span>
                <Meta title={s.label} subtitle={s.sub} />
              </div>
            );
          })}
        </div>
        <div className="mt-5">
          <Bar pct={pct} />
        </div>
      </Card>

      {error ? (
        <Note tone="bad" title="Could not prepare the review">
          {error}
        </Note>
      ) : (
        <Note title="Audio is sent for transcription">
          Video never leaves the device. Preliminary observations are for screening review only.
        </Note>
      )}

      <Cta disabled={!error && !alreadyExtracted} onClick={() => navigate("/8")}>
        {error ? "Continue to the review →" : "Preparing the review…"}
      </Cta>
      <FootNote>
        <button onClick={() => navigate("/6")}>Cancel analysis</button>
      </FootNote>
    </>
  );
}
