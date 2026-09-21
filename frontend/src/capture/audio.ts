/** Microphone capture for the consultation (screen 6).
 *
 * Capture logic lives in `capture/`, isolated from screens (CLAUDE.md code
 * conventions) — the same split as `capture/rppg.ts`.
 *
 * MediaRecorder -> WebM/Opus blob, plus a live waveform (per-frame RMS from a
 * WebAudio AnalyserNode) and an elapsed timer. Unlike the video path, the audio
 * blob *is* posted to the backend for transcription: rule 5 is about video, and
 * specs.md §8 requires the UI to say exactly that — "Audio is sent for
 * transcription; video never leaves the device".
 */

const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];

export interface RecorderTick {
  /** seconds since start */
  elapsedS: number;
  /** 24 normalised bar heights in [0,1], newest last — drives the waveform */
  levels: number[];
}

export interface AudioRecording {
  blob: Blob;
  mimeType: string;
  durationS: number;
  /** Highest raw RMS observed; used to reject muted/disconnected input. */
  peakRms: number;
}

export interface AudioRecorderHandle {
  /** Blob of everything recorded so far, without stopping. Used to build the
   * transcript live on screen 6 — the first chunk carries the WebM header, so
   * concatenating chunks-so-far yields a decodable file. */
  snapshot: () => Blob;
  hasSpeech: () => boolean;
  stop: () => Promise<AudioRecording>;
  cancel: () => void;
}

/** In-memory handoff of the finished recording from screen 6 to screen 7.
 * A Blob cannot go in sessionStorage, and the audio must not be persisted
 * anywhere in the browser. Lives only for this page session. */
let pendingAudio: AudioRecording | null = null;

export function setPendingAudio(recording: AudioRecording | null): void {
  pendingAudio = recording;
}

export function takePendingAudio(): AudioRecording | null {
  const value = pendingAudio;
  pendingAudio = null;
  return value;
}

export function pickMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "audio/webm";
  for (const type of MIME_CANDIDATES) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return "audio/webm";
}

const BAR_COUNT = 24;

/**
 * Starts recording. Resolves with a handle; `stop()` resolves with the blob.
 * `onTick` fires ~10x/second with the elapsed time and waveform levels.
 */
export async function startRecording(onTick: (tick: RecorderTick) => void): Promise<AudioRecorderHandle> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true },
  });

  const mimeType = pickMimeType();
  const recorder = new MediaRecorder(stream, { mimeType });
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  const audioCtx = new AudioContext();
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 512;
  audioCtx.createMediaStreamSource(stream).connect(analyser);
  const buffer = new Uint8Array(analyser.frequencyBinCount);

  const levels: number[] = new Array(BAR_COUNT).fill(0.08);
  const startedAt = performance.now();
  let raf = 0;
  let lastPush = 0;
  let peakRms = 0;

  const loop = () => {
    analyser.getByteTimeDomainData(buffer);
    let sum = 0;
    for (let i = 0; i < buffer.length; i += 1) {
      const centred = (buffer[i] - 128) / 128;
      sum += centred * centred;
    }
    const rms = Math.sqrt(sum / buffer.length);
    peakRms = Math.max(peakRms, rms);
    const now = performance.now();
    if (now - lastPush > 90) {
      lastPush = now;
      levels.push(Math.min(1, Math.max(0.08, rms * 3)));
      if (levels.length > BAR_COUNT) levels.shift();
      onTick({ elapsedS: (now - startedAt) / 1000, levels: [...levels] });
    }
    raf = requestAnimationFrame(loop);
  };

  recorder.start(1000);
  raf = requestAnimationFrame(loop);

  const teardown = () => {
    cancelAnimationFrame(raf);
    stream.getTracks().forEach((t) => t.stop());
    void audioCtx.close().catch(() => undefined);
  };

  return {
    snapshot: () => new Blob(chunks, { type: mimeType }),
    hasSpeech: () => peakRms >= 0.008,
    stop: () =>
      new Promise<AudioRecording>((resolve) => {
        const durationS = (performance.now() - startedAt) / 1000;
        recorder.onstop = () => {
          teardown();
          resolve({ blob: new Blob(chunks, { type: mimeType }), mimeType, durationS, peakRms });
        };
        if (recorder.state === "inactive") {
          teardown();
          resolve({ blob: new Blob(chunks, { type: mimeType }), mimeType, durationS, peakRms });
        } else {
          recorder.stop();
        }
      }),
    cancel: () => {
      if (recorder.state !== "inactive") recorder.stop();
      teardown();
    },
  };
}

export function formatElapsed(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const mm = String(Math.floor(total / 60)).padStart(2, "0");
  const ss = String(total % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}
