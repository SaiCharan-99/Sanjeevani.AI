"""rPPG pipeline tests (specs.md §4, CLAUDE.md Testing).

Synthetic signals with known frequency: inject a clean 1.2 Hz sinusoid into a
plausible RGB trace and assert the pipeline returns ~72 bpm. A noisy/high-motion
case must be rejected by the quality gate.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.rppg.pipeline import run_pipeline
from app.rppg.signal import bandpass, dominant_frequency_bpm, pos_projection

FS = 30.0
DURATION_S = 30.0


def _synthetic_roi(freq_hz: float, fs: float, duration_s: float, noise_std: float = 0.002) -> dict:
    n = int(fs * duration_s)
    t = np.arange(n) / fs
    pulse = 0.02 * np.sin(2 * np.pi * freq_hz * t)
    base_r, base_g, base_b = 150.0, 120.0, 100.0
    rng = np.random.default_rng(42)
    r = base_r + base_r * pulse * 0.6 + rng.normal(0, noise_std * base_r, n)
    g = base_g + base_g * pulse * 1.0 + rng.normal(0, noise_std * base_g, n)
    b = base_b + base_b * pulse * 0.4 + rng.normal(0, noise_std * base_b, n)
    return {"r": r.tolist(), "g": g.tolist(), "b": b.tolist()}


def _synthetic_traces(freq_hz: float, fs: float = FS, duration_s: float = DURATION_S) -> dict:
    return {
        "forehead": _synthetic_roi(freq_hz, fs, duration_s),
        "cheek_l": _synthetic_roi(freq_hz, fs, duration_s),
        "cheek_r": _synthetic_roi(freq_hz, fs, duration_s),
    }


def test_clean_1_2hz_sinusoid_returns_72bpm():
    """1.2 Hz * 60 = 72 bpm."""
    freq_hz = 1.2
    n = int(FS * DURATION_S)
    timestamps = (np.arange(n) / FS).tolist()
    traces = _synthetic_traces(freq_hz)

    result = run_pipeline(
        traces=traces,
        timestamps=timestamps,
        motion_score_series=None,
        single_motion_score=0.05,
        fs_hint=int(FS),
        duration_s=DURATION_S,
    )

    assert result.retake_recommended is False
    assert result.heart_rate_bpm == pytest.approx(72.0, abs=3.0)
    assert result.heart_rate_quality > 0.4


def test_high_motion_traces_rejected_by_quality_gate():
    """>30% of frames flagged high-motion must fail fast with retake_recommended."""
    freq_hz = 1.2
    n = int(FS * DURATION_S)
    timestamps = (np.arange(n) / FS).tolist()
    traces = _synthetic_traces(freq_hz)

    result = run_pipeline(
        traces=traces,
        timestamps=timestamps,
        motion_score_series=None,
        single_motion_score=0.9,  # well above MOTION_REJECT_THRESHOLD -> 100% rejected
        fs_hint=int(FS),
        duration_s=DURATION_S,
    )

    assert result.retake_recommended is True
    assert result.rejected_fraction > 0.3
    assert result.overall_quality == 0.0


def test_pure_noise_signal_has_low_quality():
    """No physiological pulse -> low SNR quality, even if motion is acceptable."""
    n = int(FS * DURATION_S)
    rng = np.random.default_rng(7)
    timestamps = (np.arange(n) / FS).tolist()
    traces = {
        roi: {
            "r": (150 + rng.normal(0, 5, n)).tolist(),
            "g": (120 + rng.normal(0, 5, n)).tolist(),
            "b": (100 + rng.normal(0, 5, n)).tolist(),
        }
        for roi in ("forehead", "cheek_l", "cheek_r")
    }

    result = run_pipeline(
        traces=traces,
        timestamps=timestamps,
        motion_score_series=None,
        single_motion_score=0.05,
        fs_hint=int(FS),
        duration_s=DURATION_S,
    )

    assert result.heart_rate_quality < 0.6


def test_bandpass_removes_out_of_band_frequency():
    n = int(FS * DURATION_S)
    t = np.arange(n) / FS
    in_band = np.sin(2 * np.pi * 1.2 * t)  # 72 bpm, inside 0.7-4.0 Hz
    out_of_band = np.sin(2 * np.pi * 0.05 * t)  # far below band
    sig = in_band + out_of_band

    filtered = bandpass(sig, FS, 0.7, 4.0)
    bpm, quality = dominant_frequency_bpm(filtered, FS, 0.7, 4.0)

    assert bpm == pytest.approx(72.0, abs=3.0)
    assert quality > 0.3


def test_pos_projection_shape():
    n = 300
    rgb = np.random.default_rng(1).normal(0, 1, (n, 3))
    pulse = pos_projection(rgb)
    assert pulse.shape == (n,)


def test_bp_trend_never_emits_absolute_value():
    """Rule 2 / specs.md §4 step 11: BP output must be a direction, never mmHg."""
    n = int(FS * DURATION_S)
    timestamps = (np.arange(n) / FS).tolist()
    traces = _synthetic_traces(1.2)

    result = run_pipeline(
        traces=traces,
        timestamps=timestamps,
        motion_score_series=None,
        single_motion_score=0.05,
        fs_hint=int(FS),
        duration_s=DURATION_S,
    )

    assert result.bp_direction in ("elevated", "stable", "low")
