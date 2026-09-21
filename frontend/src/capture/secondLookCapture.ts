/** Guided second-look capture (Phase 5, wireframe 11). Isolated from screens
 * per CLAUDE.md. Runs MediaPipe Pose + Face Mesh over the live camera feed,
 * accumulates a per-frame landmark trace (never video or image data — rule
 * 5), and reports live metrics for the screen's readout (cycles, fps, lock
 * status) via `onMetric`. */

import { detectFace, getFaceLandmarker } from "./faceMesh";
import { detectPose, getPoseLandmarker } from "./pose";

export interface SecondLookFrame {
  t: number;
  pose?: Record<string, [number, number, number]>;
  face?: Record<string, [number, number, number]>;
}

export interface LiveMetric {
  elapsedS: number;
  cycles: number;
  fps: number;
  locked: boolean;
  progressPct: number;
}

//: which face/pose landmark indices to record per feature, kept small (never
//: the whole 468/33-point mesh) — just enough for the backend's feature
//: functions (agents/secondlook_features.py).
const POSE_INDICES = [7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 27, 28];
const FACE_INDICES = [1, 61, 291];

//: positioning guidance text per feature (specs.md §5 / screen 11).
export const POSITIONING_GUIDANCE: Record<string, string> = {
  chest_rise_respiration: "Sit sideways, about 1.5m from the camera. Breathe normally.",
  swelling_asymmetry: "Frame both limbs together, still.",
  guided_range_of_motion: "Raise the affected arm to shoulder height, then rotate the wrist.",
  pallor_check: "Face the camera, even light, eyes open.",
  posture_assessment: "Stand side-on to the camera, in your normal posture.",
  facial_asymmetry: "Face the camera. Smile, then raise your eyebrows.",
  gait_balance: "Walk toward the camera for 3-4 steps.",
  lip_cyanosis: "Face the camera close, without talking.",
  sclera_colour: "Look at the camera, open your eyes wide.",
  blink_rate_tremor: "Sit quietly, face steady toward the camera.",
};

export function captureFeature(
  feature: string,
  videoEl: HTMLVideoElement,
  durationS = 20,
  onMetric?: (m: LiveMetric) => void,
  abortSignal?: AbortSignal
): Promise<SecondLookFrame[]> {
  const faceFeatures = new Set(["facial_asymmetry", "lip_cyanosis", "sclera_colour", "pallor_check", "blink_rate_tremor"]);
  const usesFace = faceFeatures.has(feature);
  const usesPose = !usesFace || feature === "posture_assessment";

  return Promise.all([usesPose ? getPoseLandmarker() : null, usesFace ? getFaceLandmarker() : null]).then(
    ([poseLandmarker, faceLandmarker]) => {
      const frames: SecondLookFrame[] = [];
      const startTime = performance.now();
      let cycles = 0;
      let prevSign = 1;
      let lastY: number | null = null;

      return new Promise<SecondLookFrame[]>((resolve, reject) => {
        let rafId = 0;

        const finish = () => {
          cancelAnimationFrame(rafId);
          resolve(frames);
        };

        const step = (nowMs: number) => {
          if (abortSignal?.aborted) {
            reject(new Error("Capture cancelled"));
            return;
          }
          const elapsedS = (performance.now() - startTime) / 1000;
          if (elapsedS >= durationS) {
            finish();
            return;
          }

          const frame: SecondLookFrame = { t: elapsedS };

          if (poseLandmarker) {
            const pose = detectPose(poseLandmarker, videoEl, nowMs);
            if (pose) {
              frame.pose = {};
              for (const idx of POSE_INDICES) {
                const p = pose.landmarks[idx];
                if (p) frame.pose[String(idx)] = [p.x, p.y, p.z];
              }
              const ls = pose.landmarks[11];
              const rs = pose.landmarks[12];
              if (ls && rs) {
                const y = (ls.y + rs.y) / 2;
                if (lastY !== null) {
                  const sign = y - lastY >= 0 ? 1 : -1;
                  if (sign !== prevSign) cycles += 0.5;
                  prevSign = sign;
                }
                lastY = y;
              }
            }
          }

          if (faceLandmarker) {
            const face = detectFace(faceLandmarker, videoEl, nowMs);
            if (face) {
              frame.face = {};
              for (const idx of FACE_INDICES) {
                const p = face.landmarks[idx];
                if (p) frame.face[String(idx)] = [p.x, p.y, p.z];
              }
            }
          }

          if (frame.pose || frame.face) {
            frames.push(frame);
          }

          onMetric?.({
            elapsedS,
            cycles: Math.floor(cycles),
            fps: frames.length > 1 ? Math.round(frames.length / elapsedS) : 0,
            locked: Boolean(frame.pose || frame.face),
            progressPct: Math.min(100, Math.round((elapsedS / durationS) * 100)),
          });

          rafId = requestAnimationFrame(step);
        };

        rafId = requestAnimationFrame(step);
      });
    }
  );
}
