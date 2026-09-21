/** Per-frame mean R/G/B extraction inside a landmark polygon, via an offscreen
 * canvas. Pixels never leave the browser — only the resulting scalar means do. */

import type { NormalizedPoint } from "./landmarks";

export interface RgbMean {
  r: number;
  g: number;
  b: number;
}

/** Reusable offscreen canvas + context, sized to the video's native resolution. */
export class RoiSampler {
  private canvas: OffscreenCanvas | HTMLCanvasElement;
  private ctx: OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D;
  private width: number;
  private height: number;

  constructor(width: number, height: number) {
    this.width = width;
    this.height = height;
    if (typeof OffscreenCanvas !== "undefined") {
      this.canvas = new OffscreenCanvas(width, height);
    } else {
      const c = document.createElement("canvas");
      c.width = width;
      c.height = height;
      this.canvas = c;
    }
    const ctx = this.canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) throw new Error("2D canvas context unavailable");
    this.ctx = ctx as OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D;
  }

  /** Draws the current video frame once per call site; must be called before sampleRoi(). */
  drawFrame(video: HTMLVideoElement): void {
    const ctx = this.ctx as CanvasRenderingContext2D;
    ctx.drawImage(video, 0, 0, this.width, this.height);
  }

  /** Samples the mean RGB inside the landmark polygon's bounding box of the
   * most recently drawn frame (bbox approximation of the true polygon —
   * cheap enough to run per-ROI per-frame at 30fps). */
  sampleRoi(polygon: NormalizedPoint[]): RgbMean {
    const ctx = this.ctx as CanvasRenderingContext2D;
    const xs = polygon.map((p) => p.x * this.width);
    const ys = polygon.map((p) => p.y * this.height);
    const minX = Math.max(0, Math.floor(Math.min(...xs)));
    const minY = Math.max(0, Math.floor(Math.min(...ys)));
    const maxX = Math.min(this.width, Math.ceil(Math.max(...xs)));
    const maxY = Math.min(this.height, Math.ceil(Math.max(...ys)));
    const w = Math.max(1, maxX - minX);
    const h = Math.max(1, maxY - minY);

    const { data } = ctx.getImageData(minX, minY, w, h);
    let rSum = 0;
    let gSum = 0;
    let bSum = 0;
    let count = 0;
    for (let i = 0; i < data.length; i += 4) {
      rSum += data[i];
      gSum += data[i + 1];
      bSum += data[i + 2];
      count++;
    }
    if (count === 0) return { r: 0, g: 0, b: 0 };
    return { r: rSum / count, g: gSum / count, b: bSum / count };
  }
}
