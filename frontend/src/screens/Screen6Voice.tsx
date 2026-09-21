/** Wireframe 6 — Voice consultation. Phase 4 — live.
 *
 * Real MediaRecorder capture (capture/audio.ts), live waveform from the mic
 * RMS, elapsed timer, and a transcript that builds during the recording: every
 * REFRESH_S the audio recorded so far is posted to /api/consult/transcribe and
 * the returned speaker-attributed turns replace the list. Attribution is
 * content-based on the backend — there is no audio diarization anywhere.
 *
 * Copy substitutions per specs.md §8: no ICD codes, "Mic active" not
 * "Dual-mic active", "Audio is sent for transcription; video never leaves the
 * device", canonical golden-path person (Ramesh Kumar, 52y, SAN-2026-0982).
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Language, TranscriptTurn } from "../api/types";
import { Avatar, Card, Cta, IconBtn, Meta, Note, Tag, Top, Turn, Wave } from "../components/Primitives";
import { formatElapsed, setPendingAudio, startRecording, type AudioRecorderHandle } from "../capture/audio";
import { getLanguage, getSessionId, storeAudioMeta, storeTranscript } from "../capture/sessionStore";

/** How often the in-progress recording is re-transcribed so the officer sees
 * the conversation building. Long enough not to hammer the API. */
const REFRESH_S = 20;

const LANGUAGE_TAG: Record<Language, string> = {
  en: "English",
  te: "తెలుగు (Telugu)",
  hi: "हिन्दी (Hindi)",
};

const SPEAKER_LABEL: Record<"officer" | "person", string> = {
  officer: "Officer (Dr. Meera Rao)",
  person: "Ramesh",
};

export default function Screen6Voice() {
  const navigate = useNavigate();
  const language = getLanguage();
  const sessionId = getSessionId();

  const handleRef = useRef<AudioRecorderHandle | null>(null);
  const startedRef = useRef(false);
  const refreshingRef = useRef(false);

  const [elapsed, setElapsed] = useState(0);
  const [levels, setLevels] = useState<number[]>([]);
  const [turns, setTurns] = useState<TranscriptTurn[]>([]);
  const [recording, setRecording] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    let interval: number | undefined;

    async function begin() {
      try {
        const handle = await startRecording(({ elapsedS, levels: l }) => {
          setElapsed(elapsedS);
          setLevels(l);
        });
        handleRef.current = handle;
        setRecording(true);

        interval = window.setInterval(async () => {
          if (refreshingRef.current || !handleRef.current || !handleRef.current.hasSpeech()) return;
          refreshingRef.current = true;
          try {
            const partial = await api.transcribe(sessionId, language, handleRef.current.snapshot());
            setTurns(partial.turns);
          } catch {
            /* transcript keeps whatever it had; the final pass runs on stop */
          } finally {
            refreshingRef.current = false;
          }
        }, REFRESH_S * 1000);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Microphone unavailable");
      }
    }

    void begin();
    return () => {
      if (interval) window.clearInterval(interval);
      handleRef.current?.cancel();
      handleRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function stopAndAnalyse() {
    if (!handleRef.current) {
      navigate("/7");
      return;
    }
    setStopping(true);
    try {
      const recorded = await handleRef.current.stop();
      handleRef.current = null;
      setRecording(false);
      if (recorded.durationS < 2 || recorded.blob.size < 1024 || recorded.peakRms < 0.008) {
        setStopping(false);
        setError("No usable speech was captured. Check the microphone input level, speak clearly, and record for at least two seconds");
        return;
      }
      setPendingAudio(recorded);
      storeAudioMeta({ durationS: recorded.durationS, mimeType: recorded.mimeType });
      if (turns.length) storeTranscript(turns);
      navigate("/7");
    } catch (err) {
      setStopping(false);
      setError(err instanceof Error ? err.message : "Could not stop the recording");
    }
  }

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate("/5")}>‹</IconBtn>
        <Tag variant={recording ? "bad" : "mute"}>● {recording ? "Recording" : "Idle"}</Tag>
      </Top>

      <Card className="flex items-center gap-3">
        <Avatar initials="RK" />
        <Meta title="Ramesh Kumar · 52y · M" subtitle={`${sessionId} · Kadiri camp`} />
      </Card>

      <div className="flex gap-2 mb-2">
        <Tag variant="accent">🌐 {LANGUAGE_TAG[language]}</Tag>
        <Tag variant="mute">🎙 {recording ? "Mic active" : "Mic idle"}</Tag>
      </div>

      <div className="flex flex-col items-center py-5">
        <div
          className={`w-[88px] h-[88px] rounded-full border-[3px] flex items-center justify-center ${
            recording ? "border-bad" : "border-line"
          }`}
        >
          <span className={`w-6 h-6 rounded-md block ${recording ? "bg-bad" : "bg-surface-2"}`} />
        </div>
        <div className="font-bold text-2xl tracking-wide mt-3.5">{formatElapsed(elapsed)}</div>
        <Wave levels={levels.length ? levels : undefined} />
      </div>

      {error && (
        <Note tone="bad" title="Microphone unavailable">
          {error} — grant microphone permission and reload this screen to record the consultation.
        </Note>
      )}

      {turns.length === 0 && !error && (
        <Note title="Listening">
          The transcript appears as the conversation is transcribed — the first turns arrive after about{" "}
          {REFRESH_S} seconds.
        </Note>
      )}

      {turns.map((t, i) => (
        <Turn
          key={`${i}-${t.start_s}`}
          who={SPEAKER_LABEL[t.speaker]}
          time={formatElapsed(t.start_s)}
          indent={t.speaker === "person"}
        >
          {t.text_original && <p className="text-[14px] mb-1">{t.text_original}</p>}
          <p className={t.text_original ? "text-[13.5px] text-text-2" : ""}>{t.text}</p>
        </Turn>
      ))}

      <Note title="Audio is sent for transcription">
        Video never leaves the device. Preliminary observations are for screening review only.
      </Note>

      <Cta onClick={stopAndAnalyse} disabled={stopping || (!recording && !error)}>
        ⏹ {stopping ? "Saving audio…" : "Stop and analyse"}
      </Cta>
    </>
  );
}
