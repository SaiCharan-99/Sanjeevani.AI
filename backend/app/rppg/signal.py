"""rPPG signal processing. Pure functions: arrays in, arrays out, no I/O (CLAUDE.md).

Implements the pipeline in specs.md §4: detrend -> normalise -> POS/CHROM
projection -> bandpass -> Welch PSD -> dominant peak -> bpm + SNR quality.
"""

from __future__ import annotations

import numpy as np
from scipy import signal as scipy_signal


def detrend(channel: np.ndarray) -> np.ndarray:
    """Removes slow lighting drift via a moving-average high-pass (smoothness-priors style)."""
    n = len(channel)
    if n < 3:
        return channel - np.mean(channel)
    window = max(3, n // 10 | 1)  # odd window, ~10% of signal
    kernel = np.ones(window) / window
    padded = np.pad(channel, (window // 2, window // 2), mode="edge")
    trend = np.convolve(padded, kernel, mode="valid")[:n]
    return channel - trend


def normalise(channel: np.ndarray, dc_reference: float | None = None) -> np.ndarray:
    """Divides by the DC (temporal mean) level, per the POS/CHROM formulation.

    POS and CHROM rely on the *relative* AC/DC ratio differing across R/G/B
    (different hemoglobin absorption per wavelength) — z-scoring to unit
    variance would erase exactly that ratio, so this normalises by the mean
    level instead. `dc_reference` lets the caller pass the pre-detrend mean
    (the true DC level) when `channel` itself is already detrended (mean ~0).
    """
    dc = dc_reference if dc_reference is not None else np.mean(channel)
    if abs(dc) < 1e-8:
        return np.zeros_like(channel)
    return channel / dc


def pos_projection(rgb: np.ndarray) -> np.ndarray:
    """POS algorithm (Wang et al. 2017) isolating the pulsatile component.

    rgb: (n_samples, 3) array of normalised R, G, B traces.
    Returns a 1D pulse signal.
    """
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    s1 = g - b
    s2 = g + b - 2 * r
    alpha = np.std(s1) / (np.std(s2) + 1e-8)
    return s1 + alpha * s2


def chrom_projection(rgb: np.ndarray) -> np.ndarray:
    """CHROM algorithm (de Haan & Jeanne 2013), used as a cross-check against POS."""
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    x = 3 * r - 2 * g
    y = 1.5 * r + g - 1.5 * b
    alpha = np.std(x) / (np.std(y) + 1e-8)
    return x - alpha * y


def bandpass(sig: np.ndarray, fs: float, low: float, high: float, order: int = 4) -> np.ndarray:
    """4th-order Butterworth, zero-phase (filtfilt)."""
    nyq = fs / 2.0
    low_n = max(low / nyq, 1e-6)
    high_n = min(high / nyq, 0.999999)
    sos = scipy_signal.butter(order, [low_n, high_n], btype="bandpass", output="sos")
    padlen = min(3 * order, len(sig) - 1)
    if padlen < 1:
        return sig
    return scipy_signal.sosfiltfilt(sos, sig, padlen=padlen)


def welch_psd(sig: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    nperseg = min(len(sig), max(64, len(sig) // 2))
    freqs, psd = scipy_signal.welch(sig, fs=fs, nperseg=nperseg)
    return freqs, psd


def dominant_frequency_bpm(
    sig: np.ndarray, fs: float, band_low_hz: float = 0.7, band_high_hz: float = 4.0
) -> tuple[float, float]:
    """Welch PSD -> (bpm, quality/SNR).

    Quality is the fraction of in-band power concentrated at the dominant peak
    (+/- 1 neighbouring bin), clamped to [0, 1].
    """
    freqs, psd = welch_psd(sig, fs)
    in_band = (freqs >= band_low_hz) & (freqs <= band_high_hz)
    if not np.any(in_band):
        return 0.0, 0.0
    band_freqs = freqs[in_band]
    band_psd = psd[in_band]
    total_power = np.sum(band_psd)
    if total_power < 1e-12:
        return 0.0, 0.0
    peak_idx = int(np.argmax(band_psd))
    peak_freq = band_freqs[peak_idx]
    lo = max(0, peak_idx - 1)
    hi = min(len(band_psd), peak_idx + 2)
    peak_power = np.sum(band_psd[lo:hi])
    snr = float(peak_power / total_power)
    bpm = float(peak_freq * 60.0)
    return bpm, min(max(snr, 0.0), 1.0)
