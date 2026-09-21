"""Second-look feature processing (specs.md §5). Pure functions: a landmark/pose
series in, a finding dict out — no I/O, same discipline as `rppg/signal.py`.

Input shape: `landmark_series` is a list of per-frame dicts, one per captured
frame, each `{"t": <seconds>, "pose": {"<index>": [x, y, z], ...}, "face": {...}}`.
`pose` indices follow MediaPipe Pose (11/12 shoulders, 23/24 hips — specs.md §5);
`face` indices follow MediaPipe Face Mesh (frontend/src/capture/landmarks.ts).
Only normalised landmark coordinates are ever sent from the client — never image
or video data (CLAUDE.md rule 5).

Every finding carries `value`, `unit`, `method`, `interpretation`, `confidence`
and an explicit `limitations` string (specs.md §5). Confidence is a rough,
documented heuristic based on how many usable frames were captured and how
regular the extracted signal is — never fabricated precision.
"""

from __future__ import annotations

import math

import numpy as np

# Cross-check tolerance between the chest-rise respiration rate and the
# rPPG-derived RR from vitals.py (Task 3). >20% relative difference is treated
# as disagreement. This threshold is a judgment call, not specified in
# architecture.md / specs.md — logged in progress.md.
RR_DISAGREEMENT_TOLERANCE = 0.20

MIN_USABLE_FRAMES = 10


def _get_point(frame: dict, group: str, index: int) -> tuple[float, float, float] | None:
    node = frame.get(group) or {}
    pt = node.get(str(index)) if str(index) in node else node.get(index)
    if pt is None or len(pt) < 2:
        return None
    z = pt[2] if len(pt) > 2 else 0.0
    return float(pt[0]), float(pt[1]), float(z)


def _series(frames: list[dict], group: str, index: int) -> list[tuple[float, float, float]]:
    out = []
    for f in frames:
        pt = _get_point(f, group, index)
        if pt is not None:
            out.append(pt)
    return out


def _midpoint_series(frames: list[dict], group: str, i1: int, i2: int) -> np.ndarray:
    """Vertical (y) trace of the midpoint between two landmarks, one row per
    frame that has both points."""
    ys = []
    for f in frames:
        p1 = _get_point(f, group, i1)
        p2 = _get_point(f, group, i2)
        if p1 is not None and p2 is not None:
            ys.append((p1[1] + p2[1]) / 2.0)
    return np.asarray(ys, dtype=float)


def _duration_s(frames: list[dict]) -> float:
    ts = [f.get("t") for f in frames if isinstance(f.get("t"), (int, float))]
    if len(ts) < 2:
        return float(len(frames)) / 30.0  # assume 30fps if no timestamps
    return float(max(ts) - min(ts))


def _count_oscillations(y: np.ndarray) -> int:
    """Counts zero-crossings of the detrended, smoothed signal about its mean —
    a coarse cycle counter, same style as the forehead blink-dip heuristic in
    rppg/pipeline.py."""
    if len(y) < 4:
        return 0
    detrended = y - np.mean(y)
    # light smoothing (3-point moving average) to avoid counting sensor noise
    if len(detrended) >= 3:
        kernel = np.ones(3) / 3.0
        detrended = np.convolve(detrended, kernel, mode="same")
    signs = np.sign(detrended)
    signs[signs == 0] = 1
    crossings = np.sum(np.abs(np.diff(signs)) > 0)
    return int(crossings // 2)  # one full cycle = two zero-crossings


def _regularity(y: np.ndarray) -> float:
    """0-1 smoothness proxy: inverse coefficient of variation of successive
    differences. Higher = more regular / less jerky motion."""
    if len(y) < 3:
        return 0.0
    diffs = np.diff(y)
    if np.mean(np.abs(diffs)) < 1e-9:
        return 0.0
    cv = np.std(diffs) / (np.mean(np.abs(diffs)) + 1e-9)
    return float(np.clip(1.0 / (1.0 + cv), 0.0, 1.0))


def _frame_count_confidence(n_frames: int, target: int = 300) -> float:
    """Confidence scales with how many usable frames were captured relative to
    a nominal 20s @ 15fps capture (300 frames). Never above 0.9 — camera-based
    findings are never asserted at full confidence (CLAUDE.md rule 6 spirit)."""
    return float(np.clip(0.5 + 0.4 * min(1.0, n_frames / target), 0.0, 0.9))


# ---------------------------------------------------------------------------
# chest_rise_respiration
# ---------------------------------------------------------------------------

def chest_rise_respiration(
    frames: list[dict],
    rppg_rr_bpm: float | None = None,
    rppg_rr_quality: float | None = None,
) -> dict:
    """Pose shoulder-midpoint (11/12) vertical oscillation over the capture
    window. Cross-checked against the session's rPPG-derived respiration rate
    (Task 3) — >20% relative disagreement lowers both confidences."""
    y = _midpoint_series(frames, "pose", 11, 12)
    duration = _duration_s(frames)
    if len(y) < MIN_USABLE_FRAMES or duration <= 0:
        return _low_confidence_finding(
            "chest_rise_respiration",
            unit="brpm",
            method="Pose shoulder-midpoint (landmarks 11/12) oscillation over the capture window.",
            reason="not enough usable frames with both shoulders visible",
        )

    cycles = _count_oscillations(y)
    rate_brpm = cycles * (60.0 / duration)
    amplitude = float(np.clip(np.std(y) * 10.0, 0.0, 1.0))
    regularity = _regularity(y)

    confidence = _frame_count_confidence(len(y)) * (0.5 + 0.5 * regularity)
    interpretation = _respiration_interpretation(rate_brpm)
    limitation = (
        "Pose-based chest-wall motion, not a spirometer; sensitive to camera angle, "
        "loose clothing and the person shifting position."
    )

    if rppg_rr_bpm is not None and rppg_rr_bpm > 0:
        relative_diff = abs(rate_brpm - rppg_rr_bpm) / rppg_rr_bpm
        if relative_diff > RR_DISAGREEMENT_TOLERANCE:
            confidence = float(np.clip(confidence * 0.6, 0.0, 0.9))
            interpretation += (
                f" Disagrees with the rPPG-derived respiration rate ({rppg_rr_bpm:.0f} brpm) "
                f"by {relative_diff * 100:.0f}% — both readings' confidence has been lowered."
            )
            limitation += " Cross-check with the rPPG-derived RR from the vitals scan disagreed beyond the 20% tolerance."
        else:
            interpretation += f" Agrees with the rPPG-derived respiration rate ({rppg_rr_bpm:.0f} brpm)."

    return {
        "feature": "chest_rise_respiration",
        "value": round(rate_brpm, 1),
        "unit": "brpm",
        "method": "Pose shoulder-midpoint (landmarks 11/12) oscillation, 20s capture.",
        "interpretation": interpretation,
        "confidence": round(confidence, 2),
        "limitations": limitation,
        "_extra": {"amplitude": round(amplitude, 2), "regularity": round(regularity, 2), "cycles": cycles},
    }


def _respiration_interpretation(rate_brpm: float) -> str:
    if rate_brpm > 20:
        return f"Above the 12-20 adult range ({rate_brpm:.0f} brpm)."
    if rate_brpm < 12:
        return f"Below the 12-20 adult range ({rate_brpm:.0f} brpm)."
    return f"Within the 12-20 adult range ({rate_brpm:.0f} brpm)."


def cross_check_rr(chest_rise_finding: dict, rppg_rr_bpm: float, rppg_rr_quality: float) -> tuple[dict, float]:
    """Given the chest-rise finding and the rPPG RR, returns
    (updated_chest_rise_finding, adjusted_rppg_rr_quality) after applying the
    same disagreement penalty to the rPPG side."""
    value = chest_rise_finding.get("value", 0.0)
    if not rppg_rr_bpm or rppg_rr_bpm <= 0 or not value:
        return chest_rise_finding, rppg_rr_quality
    relative_diff = abs(value - rppg_rr_bpm) / rppg_rr_bpm
    if relative_diff > RR_DISAGREEMENT_TOLERANCE:
        return chest_rise_finding, float(np.clip(rppg_rr_quality * 0.6, 0.0, 1.0))
    return chest_rise_finding, rppg_rr_quality


# ---------------------------------------------------------------------------
# swelling_asymmetry
# ---------------------------------------------------------------------------

def swelling_asymmetry(frames: list[dict]) -> dict:
    """Compares left/right landmark distances against the body midline
    (shoulder-to-hip distance on each side). Monocular vision cannot measure
    true volume — this detects asymmetry, not absolute swelling (specs.md §5)."""
    left = _series(frames, "pose", 11) and _series(frames, "pose", 23)
    if not frames:
        return _low_confidence_finding(
            "swelling_asymmetry", unit="%", method="Left/right landmark distance ratio.", reason="no frames captured"
        )

    left_dists, right_dists = [], []
    for f in frames:
        ls, lh = _get_point(f, "pose", 11), _get_point(f, "pose", 23)
        rs, rh = _get_point(f, "pose", 12), _get_point(f, "pose", 24)
        if ls and lh:
            left_dists.append(math.dist(ls[:2], lh[:2]))
        if rs and rh:
            right_dists.append(math.dist(rs[:2], rh[:2]))

    if not left_dists or not right_dists:
        return _low_confidence_finding(
            "swelling_asymmetry", unit="%", method="Left/right landmark distance ratio.", reason="both sides not visible"
        )

    left_mean = float(np.mean(left_dists))
    right_mean = float(np.mean(right_dists))
    bigger, smaller = max(left_mean, right_mean), min(left_mean, right_mean)
    asymmetry_pct = 0.0 if bigger < 1e-9 else (bigger - smaller) / bigger * 100.0

    confidence = _frame_count_confidence(min(len(left_dists), len(right_dists)), target=150) * 0.8  # extra discount, monocular
    flagged = asymmetry_pct > 15.0
    interpretation = (
        f"{asymmetry_pct:.0f}% left/right difference — {'above' if flagged else 'within'} the 15% flag threshold."
    )
    return {
        "feature": "swelling_asymmetry",
        "value": round(asymmetry_pct, 1),
        "unit": "%",
        "method": "Left/right landmark distance ratio (shoulder-to-hip line each side).",
        "interpretation": interpretation,
        "confidence": round(confidence, 2),
        "limitations": "Monocular vision detects asymmetry, not absolute swelling; sensitive to camera angle and posture.",
    }


# ---------------------------------------------------------------------------
# guided_range_of_motion
# ---------------------------------------------------------------------------

def guided_range_of_motion(frames: list[dict], expected_max_deg: float = 180.0) -> dict:
    """Tracks the shoulder-elbow-wrist joint angle across the capture (raise
    arm to shoulder / rotate wrist). Reports max angle achieved vs. expected."""
    angles = []
    for f in frames:
        shoulder = _get_point(f, "pose", 11)
        elbow = _get_point(f, "pose", 13)
        wrist = _get_point(f, "pose", 15)
        if shoulder and elbow and wrist:
            angles.append(_joint_angle_deg(shoulder, elbow, wrist))

    if len(angles) < MIN_USABLE_FRAMES:
        return _low_confidence_finding(
            "guided_range_of_motion",
            unit="deg",
            method="Shoulder-elbow-wrist joint angle sweep.",
            reason="arm not tracked through the full sweep",
        )

    max_angle = float(np.max(angles))
    smoothness = _regularity(np.asarray(angles))
    pct_of_expected = max_angle / expected_max_deg * 100.0
    confidence = _frame_count_confidence(len(angles)) * (0.5 + 0.5 * smoothness)
    interpretation = f"Reached {max_angle:.0f}° of an expected {expected_max_deg:.0f}° sweep ({pct_of_expected:.0f}%)."
    return {
        "feature": "guided_range_of_motion",
        "value": round(max_angle, 1),
        "unit": "deg",
        "method": "Shoulder-elbow-wrist joint angle across the guided sweep, 15-20s.",
        "interpretation": interpretation,
        "confidence": round(confidence, 2),
        "limitations": "2D pose estimate of a 3D motion; camera angle and compensating movement in another joint can distort the reading.",
    }


def _joint_angle_deg(a: tuple, b: tuple, c: tuple) -> float:
    """Angle at vertex b, in degrees, for points a-b-c (x, y only)."""
    ba = np.array([a[0] - b[0], a[1] - b[1]])
    bc = np.array([c[0] - b[0], c[1] - b[1]])
    na, nc = np.linalg.norm(ba), np.linalg.norm(bc)
    if na < 1e-9 or nc < 1e-9:
        return 0.0
    cos_angle = np.clip(np.dot(ba, bc) / (na * nc), -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


# ---------------------------------------------------------------------------
# pallor_check
# ---------------------------------------------------------------------------

def pallor_check(frames: list[dict], cheek_group: str = "face_rgb_cheek", sclera_group: str = "face_rgb_sclera") -> dict:
    """Face-mesh cheek redness normalised against the sclera's white balance.
    Heavily confounded by skin tone and lighting — must be labelled as such
    (specs.md §5). Reuses the same RGB-redness-ratio approach as the passive
    pallor score in rppg/pipeline.py, but referenced against the sclera here
    rather than a fixed neutral constant."""
    cheek_rgb = [f.get(cheek_group) for f in frames if f.get(cheek_group)]
    sclera_rgb = [f.get(sclera_group) for f in frames if f.get(sclera_group)]

    if not cheek_rgb:
        return _low_confidence_finding(
            "pallor_check", unit="score", method="Cheek redness normalised against sclera white balance.", reason="cheek region not captured"
        )

    cheek_arr = np.asarray(cheek_rgb, dtype=float)  # [[r,g,b], ...]
    cheek_redness = float(np.mean(cheek_arr[:, 0] / (np.sum(cheek_arr, axis=1) + 1e-9)))

    if sclera_rgb:
        sclera_arr = np.asarray(sclera_rgb, dtype=float)
        sclera_brightness = float(np.mean(np.sum(sclera_arr, axis=1)) / 3.0)
        white_balance_factor = 128.0 / (sclera_brightness + 1e-9)
    else:
        white_balance_factor = 1.0

    normalised_redness = cheek_redness * np.clip(white_balance_factor, 0.5, 2.0)
    pallor_score = float(np.clip(1.5 - normalised_redness * 3.0, 0.0, 1.0))

    confidence = _frame_count_confidence(len(cheek_rgb), target=150) * (0.7 if sclera_rgb else 0.5)
    band = "Higher" if pallor_score >= 0.6 else "Moderate" if pallor_score >= 0.35 else "Low"
    interpretation = f"{band} pallor score ({pallor_score:.2f})."
    return {
        "feature": "pallor_check",
        "value": round(pallor_score, 2),
        "unit": "score",
        "method": "Cheek redness ratio normalised against the sclera as a white-balance reference.",
        "interpretation": interpretation,
        "confidence": round(confidence, 2),
        "limitations": "Confounded by skin tone and lighting; a screening signal, not a haemoglobin measurement (rule 3 — haemoglobin estimation from camera is explicitly out of scope).",
    }


# ---------------------------------------------------------------------------
# posture_assessment
# ---------------------------------------------------------------------------

def posture_assessment(frames: list[dict]) -> dict:
    """Side-view pose: forward head angle (ear-to-shoulder line vs vertical)
    and shoulder height difference."""
    ear_shoulder_angles = []
    shoulder_height_diffs = []
    for f in frames:
        ear = _get_point(f, "pose", 7) or _get_point(f, "pose", 8)  # left/right ear
        shoulder_l = _get_point(f, "pose", 11)
        shoulder_r = _get_point(f, "pose", 12)
        if ear and shoulder_l:
            dx = ear[0] - shoulder_l[0]
            dy = ear[1] - shoulder_l[1]
            angle_from_vertical = math.degrees(math.atan2(abs(dx), abs(dy) + 1e-9))
            ear_shoulder_angles.append(angle_from_vertical)
        if shoulder_l and shoulder_r:
            shoulder_height_diffs.append(abs(shoulder_l[1] - shoulder_r[1]))

    if not ear_shoulder_angles:
        return _low_confidence_finding(
            "posture_assessment", unit="deg", method="Forward head angle vs. vertical, side view.", reason="ear/shoulder landmarks not both visible"
        )

    forward_head_deg = float(np.mean(ear_shoulder_angles))
    shoulder_diff = float(np.mean(shoulder_height_diffs)) if shoulder_height_diffs else 0.0
    confidence = _frame_count_confidence(len(ear_shoulder_angles), target=150) * 0.85
    deviation = forward_head_deg > 15.0
    interpretation = (
        f"Forward head angle {forward_head_deg:.0f}° from vertical "
        f"({'above' if deviation else 'within'} the 15° comfortable range)."
    )
    recommendation = (
        "Consider an ergonomic/posture recommendation alongside the assessment."
        if deviation
        else "No posture deviation flagged."
    )
    return {
        "feature": "posture_assessment",
        "value": round(forward_head_deg, 1),
        "unit": "deg",
        "method": "Forward head angle (ear-to-shoulder vs. vertical) and shoulder height difference, side view, 15s.",
        "interpretation": f"{interpretation} {recommendation}",
        "confidence": round(confidence, 2),
        "limitations": "Side-view 2D estimate; sensitive to camera height and the person's distance from frame.",
    }


# ---------------------------------------------------------------------------
# facial_asymmetry (highest-priority red-flag capture)
# ---------------------------------------------------------------------------

def facial_asymmetry(frames: list[dict]) -> dict:
    """Face-mesh landmark displacement across the facial midline during a
    requested smile / eyebrow-raise. Highest priority — a positive finding is
    a stroke-screening red flag, surfaced immediately (specs.md §5)."""
    mouth_left = _series(frames, "face", 61)  # left mouth corner
    mouth_right = _series(frames, "face", 291)  # right mouth corner
    nose_tip = _series(frames, "face", 1)

    if not mouth_left or not mouth_right or not nose_tip:
        return _low_confidence_finding(
            "facial_asymmetry", unit="%", method="Facial midline landmark displacement during smile/eyebrow-raise.", reason="mouth/nose landmarks not tracked"
        )

    left_disp = [math.dist((p[0], p[1]), (n[0], n[1])) for p, n in zip(mouth_left, nose_tip)]
    right_disp = [math.dist((p[0], p[1]), (n[0], n[1])) for p, n in zip(mouth_right, nose_tip)]

    left_range = float(np.max(left_disp) - np.min(left_disp)) if left_disp else 0.0
    right_range = float(np.max(right_disp) - np.min(right_disp)) if right_disp else 0.0
    bigger, smaller = max(left_range, right_range), min(left_range, right_range)
    asymmetry_pct = 0.0 if bigger < 1e-9 else (bigger - smaller) / bigger * 100.0

    confidence = _frame_count_confidence(len(mouth_left), target=200) * 0.85
    flagged = asymmetry_pct > 20.0
    interpretation = (
        f"{asymmetry_pct:.0f}% difference in mouth-corner displacement during the requested movement "
        f"({'above' if flagged else 'within'} the 20% screening threshold)."
    )
    if flagged:
        interpretation += " Consider immediate stroke-screening escalation."
    return {
        "feature": "facial_asymmetry",
        "value": round(asymmetry_pct, 1),
        "unit": "%",
        "method": "Face-mesh mouth-corner displacement relative to the nose tip, smile/eyebrow-raise, 15s.",
        "interpretation": interpretation,
        "confidence": round(confidence, 2),
        "limitations": "A screening signal only, never a stroke diagnosis; requires the person to actively perform the movement.",
    }


# ---------------------------------------------------------------------------
# gait_balance
# ---------------------------------------------------------------------------

def gait_balance(frames: list[dict]) -> dict:
    """Pose over a short walk toward the camera: step symmetry (ankle
    left/right cadence) and lateral sway of the hip midpoint."""
    left_ankle_y = [p[1] for p in _series(frames, "pose", 27)]
    right_ankle_y = [p[1] for p in _series(frames, "pose", 28)]
    hip_x = [p[0] for p in _midpoint_hip_series(frames)]

    if len(left_ankle_y) < MIN_USABLE_FRAMES or len(right_ankle_y) < MIN_USABLE_FRAMES:
        return _low_confidence_finding(
            "gait_balance", unit="score", method="Pose ankle cadence and hip-midpoint sway over a short walk.", reason="ankles not tracked through the walk"
        )

    left_cycles = _count_oscillations(np.asarray(left_ankle_y))
    right_cycles = _count_oscillations(np.asarray(right_ankle_y))
    step_symmetry = 1.0 - (abs(left_cycles - right_cycles) / max(1, max(left_cycles, right_cycles)))
    sway = float(np.std(hip_x)) if hip_x else 0.0
    balance_score = float(np.clip(step_symmetry - sway * 2.0, 0.0, 1.0))

    confidence = _frame_count_confidence(len(left_ankle_y), target=150) * 0.75
    interpretation = f"Balance/gait score {balance_score:.2f} (step symmetry {step_symmetry:.2f}, lateral sway {sway:.2f})."
    return {
        "feature": "gait_balance",
        "value": round(balance_score, 2),
        "unit": "score",
        "method": "Pose ankle-cadence step symmetry and hip-midpoint lateral sway over a short walk toward the camera.",
        "interpretation": interpretation,
        "confidence": round(confidence, 2),
        "limitations": "Requires an unobstructed few-step walk toward the camera; a short or partially framed walk understates sway.",
    }


def _midpoint_hip_series(frames: list[dict]) -> list[tuple[float, float, float]]:
    out = []
    for f in frames:
        l, r = _get_point(f, "pose", 23), _get_point(f, "pose", 24)
        if l and r:
            out.append(((l[0] + r[0]) / 2.0, (l[1] + r[1]) / 2.0, 0.0))
    return out


# ---------------------------------------------------------------------------
# Secondary trigger outputs not fully specified in specs.md §5 — documented
# minimal implementations reusing the closest specified pattern rather than
# inventing new clinical logic (see progress.md Decisions log).
# ---------------------------------------------------------------------------

def lip_cyanosis(frames: list[dict], lip_group: str = "face_rgb_lip") -> dict:
    """Not separately specified in specs.md §5 beyond the architecture.md §8
    trigger-table description ('face mesh: lip region hue'). Reuses the same
    redness-ratio pattern as pallor_check, applied to the lip region, as the
    closest documented pattern — not a new clinical rule."""
    lip_rgb = [f.get(lip_group) for f in frames if f.get(lip_group)]
    if not lip_rgb:
        return _low_confidence_finding(
            "lip_cyanosis", unit="score", method="Lip-region hue ratio.", reason="lip region not captured"
        )
    arr = np.asarray(lip_rgb, dtype=float)
    blueness = float(np.mean(arr[:, 2] / (np.sum(arr, axis=1) + 1e-9)))
    cyanosis_score = float(np.clip((blueness - 0.30) * 5.0, 0.0, 1.0))
    confidence = _frame_count_confidence(len(lip_rgb), target=150) * 0.5  # low — undocumented pattern, most conservative reading
    return {
        "feature": "lip_cyanosis",
        "value": round(cyanosis_score, 2),
        "unit": "score",
        "method": "Lip-region blue-channel ratio (architecture.md §8 trigger description).",
        "interpretation": f"Lip hue cyanosis score {cyanosis_score:.2f}.",
        "confidence": round(confidence, 2),
        "limitations": "Undocumented beyond the trigger-table description; heavily confounded by lighting and camera colour balance. Treat as low-confidence screening only.",
    }


def sclera_colour(frames: list[dict], sclera_group: str = "face_rgb_sclera") -> dict:
    """Eye-white hue, per the architecture.md §8 trigger description. Reuses
    the same white-balance-reference pattern as pallor_check."""
    sclera_rgb = [f.get(sclera_group) for f in frames if f.get(sclera_group)]
    if not sclera_rgb:
        return _low_confidence_finding(
            "sclera_colour", unit="score", method="Sclera (eye-white) hue ratio.", reason="sclera region not captured"
        )
    arr = np.asarray(sclera_rgb, dtype=float)
    yellowness = float(np.mean((arr[:, 0] + arr[:, 1]) / (2 * (arr[:, 2] + 1e-9))))
    jaundice_score = float(np.clip((yellowness - 1.05) * 2.0, 0.0, 1.0))
    confidence = _frame_count_confidence(len(sclera_rgb), target=150) * 0.5
    return {
        "feature": "sclera_colour",
        "value": round(jaundice_score, 2),
        "unit": "score",
        "method": "Sclera red+green vs. blue channel ratio (architecture.md §8 trigger description).",
        "interpretation": f"Sclera yellowing score {jaundice_score:.2f}.",
        "confidence": round(confidence, 2),
        "limitations": "Undocumented beyond the trigger-table description; heavily confounded by lighting and camera colour balance. Treat as low-confidence screening only.",
    }


def blink_rate_tremor(frames: list[dict], forehead_group: str = "face_rgb_forehead") -> dict:
    """Reuses the existing forehead-luminance dip heuristic from
    rppg/pipeline.py's passive blink-rate finding, applied over this capture's
    window, per the architecture.md §8 trigger description ('face mesh over
    time')."""
    forehead_rgb = [f.get(forehead_group) for f in frames if f.get(forehead_group)]
    duration = _duration_s(frames)
    if not forehead_rgb or duration <= 0:
        return _low_confidence_finding(
            "blink_rate_tremor", unit="blinks/min", method="Forehead-luminance dip counting over the capture window.", reason="forehead region not captured"
        )
    luminance = np.asarray([sum(rgb) / 3.0 for rgb in forehead_rgb], dtype=float)
    mean_l = np.mean(luminance)
    detrended = luminance - mean_l
    threshold = -1.5 * np.std(detrended) if np.std(detrended) > 1e-8 else -1e9
    dips = 0
    below = False
    for v in detrended:
        if v < threshold and not below:
            dips += 1
            below = True
        elif v >= threshold:
            below = False
    rate_per_min = float(np.clip(dips * (60.0 / duration), 8.0, 30.0))
    confidence = _frame_count_confidence(len(forehead_rgb), target=300) * 0.5
    return {
        "feature": "blink_rate_tremor",
        "value": round(rate_per_min, 1),
        "unit": "blinks/min",
        "method": "Forehead-luminance dip counting over the capture window (same heuristic as the passive blink-rate finding in rppg/pipeline.py).",
        "interpretation": f"Blink rate approximately {rate_per_min:.0f}/min.",
        "confidence": round(confidence, 2),
        "limitations": "A coarse luminance-dip proxy, not true eye-landmark blink detection; undocumented beyond the trigger-table description.",
    }


FEATURE_PROCESSORS = {
    "chest_rise_respiration": chest_rise_respiration,
    "swelling_asymmetry": swelling_asymmetry,
    "guided_range_of_motion": guided_range_of_motion,
    "pallor_check": pallor_check,
    "posture_assessment": posture_assessment,
    "facial_asymmetry": facial_asymmetry,
    "gait_balance": gait_balance,
    "lip_cyanosis": lip_cyanosis,
    "sclera_colour": sclera_colour,
    "blink_rate_tremor": blink_rate_tremor,
}


def _low_confidence_finding(feature: str, *, unit: str, method: str, reason: str) -> dict:
    return {
        "feature": feature,
        "value": 0.0,
        "unit": unit,
        "method": method,
        "interpretation": f"Could not compute a reliable reading — {reason}. Retake recommended.",
        "confidence": 0.1,
        "limitations": f"Insufficient landmark data this capture ({reason}); treat as unreliable.",
    }
