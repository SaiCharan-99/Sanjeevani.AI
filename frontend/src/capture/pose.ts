/** MediaPipe Pose (Tasks Vision) wrapper — same WASM/CDN pattern as
 * faceMesh.ts. Isolated from screens per CLAUDE.md ("Capture logic lives in
 * capture/"). Runs entirely client-side; only normalised landmark
 * coordinates ever leave this module (never image/video data, rule 5). */

import { FilesetResolver, PoseLandmarker } from "@mediapipe/tasks-vision";

const WASM_BASE = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";

let landmarkerPromise: Promise<PoseLandmarker> | null = null;

export function getPoseLandmarker(): Promise<PoseLandmarker> {
  if (!landmarkerPromise) {
    landmarkerPromise = FilesetResolver.forVisionTasks(WASM_BASE).then((fileset) =>
      PoseLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
        runningMode: "VIDEO",
        numPoses: 1,
      })
    );
  }
  return landmarkerPromise;
}

export interface DetectedPose {
  landmarks: { x: number; y: number; z: number }[];
}

export function detectPose(
  landmarker: PoseLandmarker,
  video: HTMLVideoElement,
  timestampMs: number
): DetectedPose | null {
  const result = landmarker.detectForVideo(video, timestampMs);
  const pose = result.landmarks?.[0];
  if (!pose || pose.length === 0) return null;
  return { landmarks: pose };
}

/** MediaPipe Pose (BlazePose, 33-point) landmark indices used by the second-
 * look features (specs.md §5). */
export const POSE_LANDMARKS = {
  LEFT_EAR: 7,
  RIGHT_EAR: 8,
  LEFT_SHOULDER: 11,
  RIGHT_SHOULDER: 12,
  LEFT_ELBOW: 13,
  RIGHT_ELBOW: 14,
  LEFT_WRIST: 15,
  RIGHT_WRIST: 16,
  LEFT_HIP: 23,
  RIGHT_HIP: 24,
  LEFT_ANKLE: 27,
  RIGHT_ANKLE: 28,
} as const;
