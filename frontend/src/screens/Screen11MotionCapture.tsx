/** Wireframe 11 — Guided motion capture. Phase 5 — live. Runs pose + face
 * mesh over a live camera feed for the chosen feature, shows positioning
 * guidance, a countdown, and a live metric readout, then posts the
 * accumulated landmark trace (never video) to `/api/secondlook/submit` and
 * routes to screen 12. */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { captureFeature, POSITIONING_GUIDANCE, type LiveMetric } from "../capture/secondLookCapture";
import { appendSecondLookFindings, getChosenFeature, getSessionId } from "../capture/sessionStore";
import { Bar, Camera, ChipPill, IconBtn, Kv, Tag } from "../components/Primitives";

type Stage = "starting" | "capturing" | "submitting" | "error";

export default function Screen11MotionCapture() {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const feature = getChosenFeature() ?? "chest_rise_respiration";
  const sessionId = getSessionId();

  const [stage, setStage] = useState<Stage>("starting");
  const [metric, setMetric] = useState<LiveMetric | null>(null);
  const [error, setError] = useState<string | null>(null);

  const durationS = feature === "guided_range_of_motion" ? 18 : feature === "facial_asymmetry" || feature === "gait_balance" ? 15 : 20;

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;
    let stream: MediaStream | null = null;

    async function run() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        setStage("capturing");
        const frames = await captureFeature(
          feature,
          videoRef.current!,
          durationS,
          (m) => setMetric(m),
          controller.signal
        );
        setStage("submitting");
        const res = await api.submitSecondLook({ session_id: sessionId, feature, landmark_series: frames });
        appendSecondLookFindings(res.findings);
        navigate("/12");
      } catch (e) {
        if (controller.signal.aborted) return;
        setError(e instanceof Error ? e.message : "Capture failed");
        setStage("error");
      } finally {
        stream?.getTracks().forEach((t) => t.stop());
      }
    }

    void run();
    return () => {
      controller.abort();
      stream?.getTracks().forEach((t) => t.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function cancel() {
    abortRef.current?.abort();
    navigate("/10");
  }

  const remaining = metric ? Math.max(0, Math.ceil(durationS - metric.elapsedS)) : durationS;
  const guidance = POSITIONING_GUIDANCE[feature] ?? "Follow the officer's positioning guidance.";

  return (
    <Camera>
      <div className="flex justify-between items-center">
        <IconBtn onClick={cancel}>✕</IconBtn>
        <Tag variant="accent">● Guided motion capture</Tag>
        <IconBtn onClick={() => window.location.reload()}>↺</IconBtn>
      </div>
      <div className="flex flex-col items-center gap-4">
        <video ref={videoRef} muted playsInline className="w-[220px] h-[180px] rounded-xl object-cover border border-dashed border-accent" />
        <ChipPill tone={error ? "warn" : "accent"}>{error ?? guidance}</ChipPill>
        <div className="text-[42px] font-bold tracking-tight">{stage === "capturing" ? remaining : "—"}</div>
        <div className="text-[13px] text-text-3 -mt-2.5">
          {stage === "starting" && "Requesting camera…"}
          {stage === "capturing" && "seconds remaining"}
          {stage === "submitting" && "Processing capture…"}
          {stage === "error" && "Capture could not complete"}
        </div>
      </div>
      <div>
        <div className="bg-surface/85 border border-line-soft rounded-r-lg p-3.5 mb-3.5">
          <Kv
            left={<span className="text-[13px] text-text-2">Tracking lock</span>}
            right={<b className="text-[15px]">{metric?.locked ? "Stable" : "Searching"}</b>}
          />
          <div className="mt-2.5">
            <Bar pct={metric?.progressPct ?? 0} />
          </div>
          <div className="flex justify-between mt-2.5 text-[11.5px] text-text-3">
            <span>Cycles: {metric?.cycles ?? 0}</span>
            <span>Frame: {metric?.fps ?? 0} fps</span>
            <span>Feature: {feature.replace(/_/g, " ")}</span>
          </div>
        </div>
        <button className="w-full text-center text-text-3 text-[15px]" onClick={cancel}>
          Cancel capture
        </button>
      </div>
    </Camera>
  );
}
