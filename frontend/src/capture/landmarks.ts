/** MediaPipe Face Mesh (468-point) landmark index groups for the rPPG ROIs
 * (architecture.md §4 / specs.md §4). Each group defines a small polygon on
 * the face used to sample mean RGB per frame. */

export const ROI_LANDMARK_GROUPS: Record<"forehead" | "cheek_l" | "cheek_r", number[]> = {
  // Between the eyebrows and the hairline, avoiding hair pixels.
  forehead: [109, 10, 338, 297, 332, 333, 299, 337, 151, 108, 69, 104, 103],
  // Person's left cheek (appears on the right side of a mirrored selfie view).
  cheek_l: [116, 123, 147, 213, 192, 214, 135, 138, 172, 136],
  // Person's right cheek.
  cheek_r: [345, 352, 376, 433, 416, 434, 364, 367, 397, 365],
};

export interface NormalizedPoint {
  x: number;
  y: number;
}
