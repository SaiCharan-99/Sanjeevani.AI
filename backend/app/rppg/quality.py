"""Vital quality gating thresholds (specs.md §4). Pure functions, no I/O."""

from __future__ import annotations

RETAKE_THRESHOLD = 0.4
WARNING_THRESHOLD = 0.7


def tier_for_quality(quality: float) -> str:
    if quality < RETAKE_THRESHOLD:
        return "retake"
    if quality < WARNING_THRESHOLD:
        return "warning"
    return "good"


def retake_recommended(overall_quality: float) -> bool:
    return overall_quality < RETAKE_THRESHOLD
