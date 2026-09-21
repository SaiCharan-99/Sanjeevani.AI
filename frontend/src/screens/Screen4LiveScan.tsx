/** Wireframe 4 — Live scan. Phase 2 — live. Real MediaPipe Face Mesh capture,
 * live signal-quality bar driven by client quality feedback. The low-light/
 * motion state (wireframe 4b) is a visual state of this screen, not a
 * separate route (specs.md §2). On completion, POSTs the accumulated traces
 * to /api/vitals/process and routes to 5 or 5b per overall_quality. */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Bar, Camera, ChipPill, IconBtn, Kv, Tag } from "../components/Primitives";
import { captureVitals, type CaptureQualityState, type LiveQuality } from "../capture/rppg";
import { getSessionId, storeVitalsResult } from "../capture/sessionStore";

const DURATION_S = 30;

const STATE_COPY: Record<CaptureQualityState, { pill: string; instruction: string; tag: string }> = {
  face_lost: { pill: "☹ No face detected", instruction: "Position the face inside the oval", tag: "Face lost" },
  low_light: { pill: "☀ Move into better light", instruction: "Move into better light", tag: "Scan paused" },
  high_motion: { pill: "✋ Hold still", instruction: "Hold still", tag: "Scan paused" },
  good: { pill: "✓ Good signal", instruction: "", tag: "Pulse locked" },
};

export default function Screen4LiveScan() {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [quality, setQuality] = useState<LiveQuality>({
    faceDetected: false,
    lightingAdequate: true,
    motionAcceptable: true,
    state: "face_lost",
    elapsedGoodS: 0,
    progressPct: 0,
  });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const abort = new AbortController();
    abortRef.current = abort;

    let stream: MediaStream | null = null;

    async function run() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 } },
        });
        const video = videoRef.current;
        if (!video) return;
        video.srcObject = stream;
        await video.play();

        const result = await captureVitals(video, DURATION_S, setQuality, abort.signal);

        setSubmitting(true);
        const response = await api.processVitals({
          session_id: getSessionId(),
          fps: result.fps,
          duration_s: result.duration_s,
          traces: result.traces,
          motion_score: result.motion_score,
          timestamps: result.timestamps,
        });
        storeVitalsResult(response);
        navigate(response.retake_recommended ? "/5b" : "/5");
      } catch (err) {
        if (abort.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Scan failed");
      } finally {
        stream?.getTracks().forEach((t) => t.stop());
      }
    }

    run();

    return () => {
      abort.abort();
      stream?.getTracks().forEach((t) => t.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const copy = STATE_COPY[quality.state];
  const isGood = quality.state === "good";
  const secondsRemaining = Math.max(0, DURATION_S - Math.floor(quality.elapsedGoodS));
  const pct = quality.progressPct;

  return (
    <Camera>
      <video
        ref={videoRef}
        playsInline
        muted
        className="absolute inset-0 w-full h-full object-cover -scale-x-100"
      />
      <div className="absolute inset-0 bg-black/35" />
      <div className="flex justify-between items-center">
        <IconBtn
          onClick={() => {
            abortRef.current?.abort();
            navigate("/3");
          }}
        >
          ✕
        </IconBtn>
        <Tag variant={isGood ? "accent" : "warn"}>{submitting ? "● Processing" : `● ${copy.tag}`}</Tag>
        <IconBtn>⚡</IconBtn>
      </div>
      <div className="flex flex-col items-center">
        <div className="relative w-[220px] h-[240px] flex items-center justify-center">
          <div className={`absolute inset-0 rounded-full border-4 ${isGood ? "border-accent/30" : "border-warn/40"}`} />
          <div className="flex flex-col items-center justify-center">
            <div className="text-[46px] font-bold tracking-tight">{secondsRemaining}</div>
            <div className="text-[13px] text-text-3">seconds remaining</div>
            <Tag variant={isGood ? "accent" : "warn"}>{submitting ? "Analysing" : copy.tag}</Tag>
          </div>
        </div>
        <ChipPill tone={isGood ? "accent" : "warn"}>{submitting ? "Processing scan…" : copy.pill}</ChipPill>
      </div>
      <div>
        <div className="bg-surface/85 border border-line-soft rounded-r-lg p-3.5 mb-3.5">
          <Kv
            left={<span className="text-[13px] text-text-2">Signal quality</span>}
            right={<b className="text-[15px]">{pct}%</b>}
          />
          <div className="mt-2.5">
            <Bar pct={pct} color={isGood ? "bg-accent" : "bg-warn"} />
          </div>
          <div className="flex justify-between mt-2.5 text-[11.5px] text-text-3">
            <span className={quality.lightingAdequate ? "" : "text-warn"}>
              Lighting: {quality.lightingAdequate ? "Even" : "Low"}
            </span>
            <span className={quality.motionAcceptable ? "" : "text-warn"}>
              Motion: {quality.motionAcceptable ? "Low" : "High"}
            </span>
            <span>rPPG: {quality.faceDetected ? "Locked" : "Searching"}</span>
          </div>
        </div>
        {error && <p className="text-center text-bad text-sm mb-2">{error}</p>}
        <div
          className="text-center text-text-3 text-[15px] cursor-pointer"
          onClick={() => {
            abortRef.current?.abort();
            navigate("/3");
          }}
        >
          Cancel scan
        </div>
      </div>
    </Camera>
  );
}
