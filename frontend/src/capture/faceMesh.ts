/** MediaPipe Face Mesh (WASM) wrapper — runs entirely client-side. Isolated
 * from screens per CLAUDE.md ("Capture logic lives in capture/"). */

import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";

const WASM_BASE = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

let landmarkerPromise: Promise<FaceLandmarker> | null = null;

export function getFaceLandmarker(): Promise<FaceLandmarker> {
  if (!landmarkerPromise) {
    landmarkerPromise = FilesetResolver.forVisionTasks(WASM_BASE).then((fileset) =>
      FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
        runningMode: "VIDEO",
        numFaces: 1,
      })
    );
  }
  return landmarkerPromise;
}

export interface DetectedFace {
  landmarks: { x: number; y: number; z: number }[];
}

export function detectFace(landmarker: FaceLandmarker, video: HTMLVideoElement, timestampMs: number): DetectedFace | null {
  const result = landmarker.detectForVideo(video, timestampMs);
  const face = result.faceLandmarks?.[0];
  if (!face || face.length === 0) return null;
  return { landmarks: face };
}
