/** Client-side rPPG extraction (architecture.md §4). Isolated from screens
 * per CLAUDE.md ("Capture logic lives in capture/").
 *
 * Locks onto forehead/cheek ROIs via MediaPipe Face Mesh, accumulates mean
 * R/G/B per ROI per frame plus a motion magnitude, for up to `durationS`
 * seconds at a 30fps target. NEVER sends video frames or image data — only
 * the accumulated scalar traces are returned, per the /api/vitals/process
 * contract. */

import { detectFace, getFaceLandmarker } from "./faceMesh";
import { ROI_LANDMARK_GROUPS, type NormalizedPoint } from "./landmarks";
import { RoiSampler } from "./roi";

export interface RoiTrace {
  r: number[];
  g: number[];
  b: number[];
}

export interface CaptureResult {
  fps: number;
  duration_s: number;
  traces: Record<"forehead" | "cheek_l" | "cheek_r", RoiTrace>;
  motion_score: number;
  timestamps: number[];
}

export type CaptureQualityState = "face_lost" | "low_light" | "high_motion" | "good";

export interface LiveQuality {
  faceDetected: boolean;
  lightingAdequate: boolean;
  motionAcceptable: boolean;
  state: CaptureQualityState;
  elapsedGoodS: number;
  progressPct: number;
}

const TARGET_FPS = 30;
const MIN_MEAN_BRIGHTNESS = 40; // 0-255 scale; below this, lighting flagged inadequate
const MOTION_LOCK_THRESHOLD = 0.03; // normalized landmark-centroid displacement per frame

function roiCentroid(landmarks: { x: number; y: number }[], indices: number[]): NormalizedPoint {
  let x = 0;
  let y = 0;
  for (const i of indices) {
    x += landmarks[i].x;
    y += landmarks[i].y;
  }
  return { x: x / indices.length, y: y / indices.length };
}

function roiPolygon(landmarks: { x: number; y: number }[], indices: number[]): NormalizedPoint[] {
  return indices.map((i) => ({ x: landmarks[i].x, y: landmarks[i].y }));
}

export async function captureVitals(
  videoEl: HTMLVideoElement,
  durationS = 30,
  onQuality?: (q: LiveQuality) => void,
  abortSignal?: AbortSignal
): Promise<CaptureResult> {
  const landmarker = await getFaceLandmarker();
  const width = videoEl.videoWidth || 640;
  const height = videoEl.videoHeight || 480;
  const sampler = new RoiSampler(width, height);

  const traces: CaptureResult["traces"] = {
    forehead: { r: [], g: [], b: [] },
    cheek_l: { r: [], g: [], b: [] },
    cheek_r: { r: [], g: [], b: [] },
  };
  const timestamps: number[] = [];
  const motionScores: number[] = [];

  let goodFrames = 0;
  let prevCentroid: NormalizedPoint | null = null;
  const startTime = performance.now();
  const frameIntervalMs = 1000 / TARGET_FPS;
  let lastFrameTime = 0;

  return new Promise((resolve, reject) => {
    let rafId = 0;

    const finish = () => {
      cancelAnimationFrame(rafId);
      const elapsedS = (performance.now() - startTime) / 1000;
      const avgMotion =
        motionScores.length > 0 ? motionScores.reduce((a, b) => a + b, 0) / motionScores.length : 0;
      resolve({
        fps: timestamps.length > 1 ? Math.round(timestamps.length / elapsedS) : TARGET_FPS,
        duration_s: Math.round(elapsedS * 10) / 10,
        traces,
        motion_score: Math.round(avgMotion * 1000) / 1000,
        timestamps,
      });
    };

    const step = (nowMs: number) => {
      if (abortSignal?.aborted) {
        reject(new Error("Capture cancelled"));
        return;
      }
      if (goodFrames >= durationS * TARGET_FPS) {
        finish();
        return;
      }
      if (nowMs - lastFrameTime < frameIntervalMs) {
        rafId = requestAnimationFrame(step);
        return;
      }
      lastFrameTime = nowMs;

      const face = detectFace(landmarker, videoEl, nowMs);

      if (!face) {
        onQuality?.({
          faceDetected: false,
          lightingAdequate: true,
          motionAcceptable: true,
          state: "face_lost",
          elapsedGoodS: goodFrames / TARGET_FPS,
          progressPct: Math.min(100, Math.round((goodFrames / (durationS * TARGET_FPS)) * 100)),
        });
        rafId = requestAnimationFrame(step);
        return;
      }

      sampler.drawFrame(videoEl);
      const foreheadPoly = roiPolygon(face.landmarks, ROI_LANDMARK_GROUPS.forehead);
      const cheekLPoly = roiPolygon(face.landmarks, ROI_LANDMARK_GROUPS.cheek_l);
      const cheekRPoly = roiPolygon(face.landmarks, ROI_LANDMARK_GROUPS.cheek_r);

      const forehead = sampler.sampleRoi(foreheadPoly);
      const cheekL = sampler.sampleRoi(cheekLPoly);
      const cheekR = sampler.sampleRoi(cheekRPoly);

      const brightness = (forehead.r + forehead.g + forehead.b) / 3;
      const lightingAdequate = brightness >= MIN_MEAN_BRIGHTNESS;

      const centroid = roiCentroid(face.landmarks, ROI_LANDMARK_GROUPS.forehead);
      let motion = 0;
      if (prevCentroid) {
        motion = Math.hypot(centroid.x - prevCentroid.x, centroid.y - prevCentroid.y);
      }
      prevCentroid = centroid;
      const motionAcceptable = motion <= MOTION_LOCK_THRESHOLD;

      const state: CaptureQualityState = !lightingAdequate
        ? "low_light"
        : !motionAcceptable
          ? "high_motion"
          : "good";

      if (lightingAdequate) {
        traces.forehead.r.push(forehead.r);
        traces.forehead.g.push(forehead.g);
        traces.forehead.b.push(forehead.b);
        traces.cheek_l.r.push(cheekL.r);
        traces.cheek_l.g.push(cheekL.g);
        traces.cheek_l.b.push(cheekL.b);
        traces.cheek_r.r.push(cheekR.r);
        traces.cheek_r.g.push(cheekR.g);
        traces.cheek_r.b.push(cheekR.b);
        timestamps.push((nowMs - startTime) / 1000);
        motionScores.push(motion);
        goodFrames++;
      }

      onQuality?.({
        faceDetected: true,
        lightingAdequate,
        motionAcceptable,
        state,
        elapsedGoodS: goodFrames / TARGET_FPS,
        progressPct: Math.min(100, Math.round((goodFrames / (durationS * TARGET_FPS)) * 100)),
      });

      rafId = requestAnimationFrame(step);
    };

    rafId = requestAnimationFrame(step);
  });
}
