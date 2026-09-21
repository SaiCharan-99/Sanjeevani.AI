"""Orchestrates the rPPG pipeline (specs.md §4): resample -> reject high-motion
frames -> detrend -> normalise -> POS/CHROM -> bandpass -> Welch -> HR/RR/SpO2/BP.

Pure functions: arrays in, structured results out, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.rppg.quality import RETAKE_THRESHOLD, WARNING_THRESHOLD
from app.rppg.signal import (
    bandpass,
    chrom_projection,
    detrend,
    dominant_frequency_bpm,
    normalise,
    pos_projection,
)

MOTION_REJECT_THRESHOLD = 0.5  # per-frame motion score above this is rejected
MAX_REJECTED_FRACTION = 0.3  # specs.md §4 step 2: fail fast if >30% rejected

HR_BAND = (0.7, 4.0)  # 42-240 bpm
RESP_BAND = (0.1, 0.5)  # 6-30 brpm, RSA envelope


@dataclass
class RoiResult:
    pulse: np.ndarray
    filtered: np.ndarray
    bpm: float
    quality: float


@dataclass
class PipelineResult:
    heart_rate_bpm: float
    heart_rate_quality: float
    respiration_brpm: float
    respiration_quality: float
    spo2_pct: float
    spo2_quality: float
    bp_direction: str
    bp_quality: float
    overall_quality: float
    retake_recommended: bool
    rejected_fraction: float
    pallor_score: float
    facial_tension: float
    blink_rate: float


def _resample_uniform(values: np.ndarray, timestamps: np.ndarray, fs: float) -> np.ndarray:
    """Resamples a trace onto a uniform time base at fs Hz via linear interpolation."""
    if len(timestamps) < 2:
        return values
    t0, t1 = timestamps[0], timestamps[-1]
    n = max(2, int(round((t1 - t0) * fs)) + 1)
    uniform_t = np.linspace(t0, t1, n)
    return np.interp(uniform_t, timestamps, values)


def _motion_mask(motion_score: np.ndarray) -> np.ndarray:
    return motion_score <= MOTION_REJECT_THRESHOLD


def _process_roi(
    r: np.ndarray, g: np.ndarray, b: np.ndarray, fs: float
) -> tuple[RoiResult, RoiResult, np.ndarray]:
    """Returns (pos_result, chrom_result, normalised_rgb) for one ROI."""
    r_dc, g_dc, b_dc = np.mean(r), np.mean(g), np.mean(b)
    r_d, g_d, b_d = detrend(r), detrend(g), detrend(b)
    r_n = normalise(r_d, dc_reference=r_dc)
    g_n = normalise(g_d, dc_reference=g_dc)
    b_n = normalise(b_d, dc_reference=b_dc)
    rgb = np.stack([r_n, g_n, b_n], axis=1)

    pos_pulse = pos_projection(rgb)
    chrom_pulse = chrom_projection(rgb)

    pos_filtered = bandpass(pos_pulse, fs, *HR_BAND)
    chrom_filtered = bandpass(chrom_pulse, fs, *HR_BAND)

    pos_bpm, pos_q = dominant_frequency_bpm(pos_filtered, fs, *HR_BAND)
    chrom_bpm, chrom_q = dominant_frequency_bpm(chrom_filtered, fs, *HR_BAND)

    return (
        RoiResult(pos_pulse, pos_filtered, pos_bpm, pos_q),
        RoiResult(chrom_pulse, chrom_filtered, chrom_bpm, chrom_q),
        rgb,
    )


def _respiration_from_rsa(pulse_filtered: np.ndarray, fs: float) -> tuple[float, float]:
    """Respiratory sinus arrhythmia: envelope of the pulse signal, bandpassed 0.1-0.5 Hz."""
    envelope = np.abs(scipy_hilbert(pulse_filtered))
    resp_filtered = bandpass(envelope, fs, *RESP_BAND)
    brpm, quality = dominant_frequency_bpm(resp_filtered, fs, *RESP_BAND)
    return brpm, quality


def scipy_hilbert(x: np.ndarray) -> np.ndarray:
    from scipy.signal import hilbert

    return hilbert(x)


def _spo2_ratio_of_ratios(
    red_raw: np.ndarray, blue_raw: np.ndarray, red_filtered: np.ndarray, blue_filtered: np.ndarray
) -> float:
    """Ratio-of-ratios SpO2 approximation, calibrated against a fixed empirical constant.

    AC/DC ratio for red and blue channels; R = (AC_red/DC_red) / (AC_blue/DC_blue).
    SpO2 = A - B * R, standard pulse-oximetry calibration curve (A=110, B=25).
    Always tier "approximate" (rule 2 / architecture.md §4) — no infrared channel.
    """
    dc_red = np.mean(red_raw)
    dc_blue = np.mean(blue_raw)
    ac_red = np.std(red_filtered)
    ac_blue = np.std(blue_filtered)
    if dc_red < 1e-8 or dc_blue < 1e-8 or ac_blue < 1e-8:
        return 95.0
    ratio = (ac_red / dc_red) / (ac_blue / dc_blue + 1e-8)
    spo2 = 110.0 - 25.0 * ratio
    return float(np.clip(spo2, 70.0, 100.0))


def _bp_trend(hr_bpm: float, motion_score: np.ndarray, pulse_amplitude: float) -> str:
    """Feature-based trend classification only. Never emits an mmHg value (rule 2).

    Heuristic: elevated heart rate + low pulse-wave amplitude (stiffer arterial
    response) skews toward "elevated"; low HR skews toward "low"; otherwise "stable".
    """
    if hr_bpm >= 90 and pulse_amplitude < 0.5:
        return "elevated"
    if hr_bpm < 55:
        return "low"
    return "stable"


def _pallor_score(cheek_l_r: np.ndarray, cheek_l_g: np.ndarray, cheek_l_b: np.ndarray) -> float:
    """Redness ratio of the cheek ROI as a proxy for pallor (low redness -> higher pallor).

    Confounded by skin tone/lighting (specs.md §5) -- passive finding, not a vital.
    """
    total = np.mean(cheek_l_r) + np.mean(cheek_l_g) + np.mean(cheek_l_b)
    if total < 1e-8:
        return 0.5
    redness = np.mean(cheek_l_r) / total
    # redness ~0.33 (neutral) -> pallor 0.5; lower redness -> higher pallor score
    pallor = float(np.clip(1.5 - redness * 3.0, 0.0, 1.0))
    return pallor


def _facial_tension(motion_score: np.ndarray) -> float:
    """Proxy from micro-motion variance in the retained (non-rejected) frames."""
    if len(motion_score) == 0:
        return 0.0
    return float(np.clip(np.std(motion_score) * 2.0, 0.0, 1.0))


def _blink_rate(forehead_g: np.ndarray, fs: float, duration_s: float) -> float:
    """Counts local dips in the forehead green channel as a coarse blink proxy.

    A real implementation needs eye-landmark tracking (client-side, future work);
    this approximates blink-driven micro-shadow dips in the available trace.
    """
    if len(forehead_g) < 5 or duration_s <= 0:
        return 14.0
    detrended = detrend(forehead_g)
    threshold = -1.5 * np.std(detrended) if np.std(detrended) > 1e-8 else -1e9
    dips = 0
    below = False
    for v in detrended:
        if v < threshold and not below:
            dips += 1
            below = True
        elif v >= threshold:
            below = False
    rate_per_min = dips * (60.0 / duration_s)
    return float(np.clip(rate_per_min, 8.0, 30.0))


def run_pipeline(
    traces: dict[str, dict[str, list[float]]],
    timestamps: list[float],
    motion_score_series: list[float] | None,
    single_motion_score: float,
    fs_hint: int,
    duration_s: float,
) -> PipelineResult:
    """Runs the full pipeline over forehead/cheek_l/cheek_r ROI traces.

    `traces` keys: "forehead", "cheek_l", "cheek_r", each {"r": [...], "g": [...], "b": [...]}.
    `motion_score_series` is optional per-frame motion; if absent, a constant series
    built from `single_motion_score` is used (client sent one aggregate value).
    """
    ts = np.asarray(timestamps, dtype=float)
    n = len(ts)
    if motion_score_series is not None and len(motion_score_series) == n:
        motion = np.asarray(motion_score_series, dtype=float)
    else:
        motion = np.full(n, single_motion_score, dtype=float)

    fs = float(fs_hint) if fs_hint else (n / duration_s if duration_s > 0 else 30.0)

    mask = _motion_mask(motion)
    rejected_fraction = float(1.0 - np.mean(mask)) if n > 0 else 1.0

    if rejected_fraction > MAX_REJECTED_FRACTION:
        return PipelineResult(
            heart_rate_bpm=0.0,
            heart_rate_quality=0.0,
            respiration_brpm=0.0,
            respiration_quality=0.0,
            spo2_pct=0.0,
            spo2_quality=0.0,
            bp_direction="stable",
            bp_quality=0.0,
            overall_quality=0.0,
            retake_recommended=True,
            rejected_fraction=rejected_fraction,
            pallor_score=0.0,
            facial_tension=0.0,
            blink_rate=0.0,
        )

    roi_data = {}
    for name in ("forehead", "cheek_l", "cheek_r"):
        roi = traces.get(name)
        if roi is None:
            continue
        r_raw = _resample_uniform(np.asarray(roi["r"], dtype=float), ts, fs)
        g_raw = _resample_uniform(np.asarray(roi["g"], dtype=float), ts, fs)
        b_raw = _resample_uniform(np.asarray(roi["b"], dtype=float), ts, fs)
        resampled_mask = _resample_uniform(mask.astype(float), ts, fs) > 0.5
        if np.any(resampled_mask):
            r_raw, g_raw, b_raw = r_raw[resampled_mask], g_raw[resampled_mask], b_raw[resampled_mask]
        roi_data[name] = (r_raw, g_raw, b_raw)

    if "forehead" not in roi_data:
        raise ValueError("forehead ROI trace is required")

    pos_results, chrom_results = [], []
    for name, (r, g, b) in roi_data.items():
        if len(r) < 8:
            continue
        pos_res, chrom_res, _ = _process_roi(r, g, b, fs)
        pos_results.append(pos_res)
        chrom_results.append(chrom_res)

    if not pos_results:
        return PipelineResult(
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "stable", 0.0, 0.0, True, rejected_fraction, 0.0, 0.0, 0.0
        )

    best_pos = max(pos_results, key=lambda x: x.quality)
    best_chrom = max(chrom_results, key=lambda x: x.quality)

    # POS/CHROM cross-check: disagreement beyond tolerance lowers quality (specs.md §4 step 5)
    disagreement = abs(best_pos.bpm - best_chrom.bpm)
    agreement_penalty = 1.0 if disagreement <= 6.0 else max(0.0, 1.0 - (disagreement - 6.0) / 30.0)
    hr_quality = float(np.clip(best_pos.quality * agreement_penalty, 0.0, 1.0))
    hr_bpm = best_pos.bpm

    resp_brpm, resp_quality = _respiration_from_rsa(best_pos.filtered, fs)

    forehead_r, forehead_g, forehead_b = roi_data["forehead"]
    spo2 = _spo2_ratio_of_ratios(forehead_r, forehead_b, bandpass(forehead_r, fs, *HR_BAND), bandpass(forehead_b, fs, *HR_BAND))
    spo2_quality = float(np.clip(hr_quality * 0.85, 0.0, 1.0))  # SpO2 rides on pulse-signal quality

    pulse_amplitude = float(np.std(best_pos.filtered))
    bp_direction = _bp_trend(hr_bpm, motion, pulse_amplitude)
    bp_quality = float(np.clip(hr_quality * 0.6, 0.0, 1.0))  # trend-only, inherently lower confidence

    cheek = roi_data.get("cheek_l") or roi_data.get("cheek_r") or (forehead_r, forehead_g, forehead_b)
    pallor = _pallor_score(*cheek)
    tension = _facial_tension(motion[mask] if np.any(mask) else motion)
    blink = _blink_rate(forehead_g, fs, duration_s)

    overall_quality = float(np.clip(np.mean([hr_quality, resp_quality, spo2_quality]) * (1.0 - rejected_fraction * 0.5), 0.0, 1.0))

    return PipelineResult(
        heart_rate_bpm=round(hr_bpm, 1),
        heart_rate_quality=hr_quality,
        respiration_brpm=round(resp_brpm, 1),
        respiration_quality=resp_quality,
        spo2_pct=round(spo2, 1),
        spo2_quality=spo2_quality,
        bp_direction=bp_direction,
        bp_quality=bp_quality,
        overall_quality=overall_quality,
        retake_recommended=overall_quality < RETAKE_THRESHOLD,
        rejected_fraction=rejected_fraction,
        pallor_score=round(pallor, 2),
        facial_tension=round(tension, 2),
        blink_rate=round(blink, 1),
    )
