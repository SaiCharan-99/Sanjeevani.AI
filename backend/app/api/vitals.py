"""POST /api/vitals/process — real rPPG pipeline (backend/app/rppg/), per specs.md §4.

Client posts accumulated RGB traces + motion score (never video). Server runs
detrend -> POS/CHROM -> bandpass -> Welch -> HR/RR/SpO2/BP-trend, enforces the
quality tiers (rule 4) and the retake gate (overall_quality < 0.4).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger("sanjeevani.vitals")

from app.memory.state import get_or_create_session
from app.models import (
    BPTrendReading,
    PassiveFindings,
    VitalReading,
    VitalsProcessRequest,
    VitalsProcessResponse,
)
from app.rppg.pipeline import run_pipeline

router = APIRouter(prefix="/api/vitals", tags=["vitals"])


@router.post("/process", response_model=VitalsProcessResponse)
async def process_vitals(request: VitalsProcessRequest) -> VitalsProcessResponse:
    traces = {name: roi.model_dump() for name, roi in request.traces.items()}

    frame_counts = {name: len(roi.get("r", [])) for name, roi in traces.items()}
    logger.warning(
        "[DIAG] vitals/process IN session=%s fps=%s duration_s=%s motion_score=%s frame_counts=%s",
        request.session_id, request.fps, request.duration_s, request.motion_score, frame_counts,
    )

    result = run_pipeline(
        traces=traces,
        timestamps=request.timestamps,
        motion_score_series=None,
        single_motion_score=request.motion_score,
        fs_hint=request.fps,
        duration_s=request.duration_s,
    )

    logger.warning(
        "[DIAG] vitals/process OUT hr=%.1f(q=%.2f) rr=%.1f(q=%.2f) spo2=%.1f(q=%.2f) bp=%s(q=%.2f) "
        "overall=%.2f retake=%s rejected_fraction=%.2f",
        result.heart_rate_bpm, result.heart_rate_quality,
        result.respiration_brpm, result.respiration_quality,
        result.spo2_pct, result.spo2_quality,
        result.bp_direction, result.bp_quality,
        result.overall_quality, result.retake_recommended, result.rejected_fraction,
    )

    # Tier 1 working memory: the second-look chest-rise capture cross-checks
    # its computed respiration rate against this rPPG-derived RR (Phase 5,
    # agents/secondlook_features.py::chest_rise_respiration).
    state = get_or_create_session(request.session_id)
    state.vitals["respiration_rate"] = {
        "value": result.respiration_brpm,
        "unit": "brpm",
        "quality": result.respiration_quality,
        "tier": "reliable",
    }
    state.vitals["heart_rate"] = {
        "value": result.heart_rate_bpm,
        "unit": "bpm",
        "quality": result.heart_rate_quality,
        "tier": "reliable",
    }
    state.vitals["spo2"] = {
        "value": result.spo2_pct,
        "unit": "%",
        "quality": result.spo2_quality,
        "tier": "approximate",
    }
    state.vitals["bp_trend"] = {
        "direction": result.bp_direction,
        "quality": result.bp_quality,
        "tier": "trend_only",
    }

    return VitalsProcessResponse(
        heart_rate=VitalReading(
            value=result.heart_rate_bpm, unit="bpm", quality=result.heart_rate_quality, tier="reliable"
        ),
        respiration_rate=VitalReading(
            value=result.respiration_brpm,
            unit="brpm",
            quality=result.respiration_quality,
            tier="reliable",
        ),
        spo2=VitalReading(value=result.spo2_pct, unit="%", quality=result.spo2_quality, tier="approximate"),
        bp_trend=BPTrendReading(direction=result.bp_direction, quality=result.bp_quality, tier="trend_only"),
        passive_findings=PassiveFindings(
            pallor_score=result.pallor_score,
            facial_tension=result.facial_tension,
            blink_rate=result.blink_rate,
        ),
        overall_quality=result.overall_quality,
        retake_recommended=result.retake_recommended,
    )
