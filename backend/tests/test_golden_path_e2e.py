"""Phase 7 — one true end-to-end golden-path test.

Runs the full golden path documented in specs.md §1 (session start -> vitals
-> consult -> second look -> synthesis -> report) through FastAPI's
`TestClient` against the real app, with `SANJEEVANI_FIXTURE_MODE=true` so
every STT/LLM call is forced onto the golden-path cache without attempting a
live Gemini call, and with no live Neo4j required (the app's lifespan already
degrades to `graph_client = None` when Neo4j is unreachable, exactly as it
would on a laptop with no Docker daemon — see progress.md's own recurring
note about this sandbox). Pure network isolation: no `GEMINI_API_KEY` needs
to be set for this test to pass.

Mirrors what's already unit-tested in `test_synthesis.py` (the reasoning
chain / NTEP citation) and `test_report.py` (real PDF text extraction), but
as one continuous run through the actual HTTP routes rather than calling the
pure functions directly — the thing nobody had exercised yet end-to-end.
"""

from __future__ import annotations

import math
import os

import pytest
from fastapi.testclient import TestClient

os.environ["SANJEEVANI_FIXTURE_MODE"] = "true"
os.environ.pop("GEMINI_API_KEY", None)

from app.main import app  # noqa: E402  (env vars must be set before import)

NTEP_RULE = "NTEP presumptive TB: cough >= 2 weeks"


def _shoulder_frames(n: int = 300, fs: float = 15.0, brpm: float = 18.0) -> list[dict]:
    """Synthetic guided-capture landmark series: shoulder midpoint oscillating
    at `brpm` breaths/min — same synthetic-signal style as test_secondlook.py
    (never a fabricated *finding*, a fabricated *input signal* fed through the
    real pure processing function, exactly like test_rppg.py's sinusoid)."""
    frames = []
    freq_hz = brpm / 60.0
    for i in range(n):
        t = i / fs
        y = 0.5 + 0.02 * math.sin(2 * math.pi * freq_hz * t)
        frames.append({"t": t, "pose": {"11": [0.4, y, 0.0], "12": [0.6, y, 0.0]}})
    return frames


def _synthetic_roi(freq_hz: float, fs: float, duration_s: float, seed: int) -> dict:
    import numpy as np

    n = int(fs * duration_s)
    t = np.arange(n) / fs
    rng = np.random.default_rng(seed)
    pulse = 0.02 * np.sin(2 * np.pi * freq_hz * t)
    base_r, base_g, base_b = 150.0, 120.0, 100.0
    r = base_r + base_r * pulse * 0.6 + rng.normal(0, 0.002 * base_r, n)
    g = base_g + base_g * pulse * 1.0 + rng.normal(0, 0.002 * base_g, n)
    b = base_b + base_b * pulse * 0.4 + rng.normal(0, 0.002 * base_b, n)
    return {"r": r.tolist(), "g": g.tolist(), "b": b.tolist()}


GOLDEN_PATH_PAIN_POINTS = [
    {
        "symptom": "cough", "canonical": "cough", "duration_days": 21, "confidence": 0.95,
        "verbatim": "for two or three weeks now I have had a cough",
    },
    {
        "symptom": "chest tightness", "canonical": "chest_tightness", "confidence": 0.90,
        "verbatim": "when I walk to the field my chest feels tight",
    },
    {
        "symptom": "fatigue", "canonical": "fatigue", "confidence": 0.88,
        "verbatim": "I get tired very fast",
    },
    {
        "symptom": "night sweats", "canonical": "night_sweats", "confidence": 0.75,
        "verbatim": "sometimes at night",
    },
    {
        "symptom": "weight loss", "canonical": "weight_loss", "confidence": 0.85,
        "verbatim": "I have lost weight",
    },
]


@pytest.fixture(autouse=True)
def _fixture_mode_env(monkeypatch):
    """Belt and suspenders: reassert fixture mode for every test in this
    module even though it's also set at import time above, in case another
    test module in the same run cleared it."""
    monkeypatch.setenv("SANJEEVANI_FIXTURE_MODE", "true")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_fixture_mode_forces_provider_calls_to_the_cache():
    """Fixture-mode flag itself: both providers refuse a live attempt and
    raise Unavailable immediately, regardless of whether a key is set."""
    import asyncio

    from app.providers.llm import GeminiLLM, LLMUnavailable
    from app.providers.stt import GeminiSTT, STTUnavailable
    from pydantic import BaseModel

    class _Schema(BaseModel):
        x: int = 0

    async def _run():
        llm = GeminiLLM()
        with pytest.raises(LLMUnavailable, match="SANJEEVANI_FIXTURE_MODE"):
            await llm.complete("hello", _Schema)
        stt = GeminiSTT()
        with pytest.raises(STTUnavailable, match="SANJEEVANI_FIXTURE_MODE"):
            await stt.transcribe(b"not-empty", "te")

    asyncio.run(_run())


def test_golden_path_end_to_end_offline():
    """session start -> vitals -> consult -> secondlook -> synthesis -> report,
    with fixture mode forcing every provider call onto the golden-path cache
    and no live Neo4j required. Asserts TB lands as the top consideration with
    the NTEP-cited reasoning chain and a real PDF comes back."""
    with TestClient(app) as client:
        # 1. Session start — consent required (rule 7), person intake.
        start = client.post(
            "/api/session/start",
            json={
                "person": {"name": "Ramesh Kumar", "age": 52, "gender": "male", "village": "Kadiri"},
                "language": "te",
                "consent": True,
            },
        )
        assert start.status_code == 200
        session_id = start.json()["session_id"]
        assert session_id

        # Consent is enforced, not just accepted: reject a no-consent session.
        rejected = client.post(
            "/api/session/start",
            json={
                "person": {"name": "X", "age": 30, "gender": "other", "village": "Y"},
                "language": "en",
                "consent": False,
            },
        )
        assert rejected.status_code == 400

        # 2. Vitals — real rPPG pipeline over a synthetic 1.2Hz-pulse ROI trace
        # (same technique as test_rppg.py), so heart_rate/respiration_rate end
        # up in Tier 1 SessionState for the second-look cross-check below.
        fs, duration_s = 30.0, 30.0
        n = int(fs * duration_s)
        traces = {
            roi: _synthetic_roi(1.2, fs, duration_s, seed)
            for roi, seed in (("forehead", 1), ("cheek_l", 2), ("cheek_r", 3))
        }
        vitals = client.post(
            "/api/vitals/process",
            json={
                "session_id": session_id,
                "fps": int(fs),
                "duration_s": duration_s,
                "traces": traces,
                "motion_score": 0.05,
                "timestamps": [i / fs for i in range(n)],
            },
        )
        assert vitals.status_code == 200
        assert vitals.json()["heart_rate"]["tier"] == "reliable"
        assert "value" in vitals.json()["bp_trend"]["direction"] or vitals.json()["bp_trend"]["direction"] in (
            "elevated", "stable", "low",
        )
        # Rule 2: never an absolute BP value anywhere in the response.
        assert "mmHg" not in str(vitals.json())

        # 3. Consult — transcribe (fixture mode forces the STT fallback to the
        # golden-path cache), extract, and save the reviewed pain points.
        transcribe = client.post(
            "/api/consult/transcribe",
            data={"session_id": session_id, "language": "te"},
        )
        assert transcribe.status_code == 200
        assert transcribe.json()["source"] == "golden_path_cache"
        assert len(transcribe.json()["turns"]) > 0

        extract = client.post("/api/consult/extract", params={"session_id": session_id})
        assert extract.status_code == 200
        extracted = extract.json()
        assert extracted["source"] == "golden_path_cache"
        extracted_slugs = {p["canonical"] for p in extracted["pain_points"]}
        assert {"cough", "chest_tightness", "fatigue", "night_sweats", "weight_loss"} <= extracted_slugs

        painpoints = client.post(
            "/api/consult/painpoints",
            json={"session_id": session_id, "pain_points": GOLDEN_PATH_PAIN_POINTS, "edited_by": "officer"},
        )
        assert painpoints.status_code == 200
        assert painpoints.json()["saved"] == 5

        # 4. Second look — the agent must propose the chest-rise capture first
        # for this exact symptom set (mirrors test_secondlook.py's golden-path
        # assertion), then submit a synthetic guided-capture landmark series.
        suggest = client.get("/api/secondlook/suggest", params={"session_id": session_id})
        assert suggest.status_code == 200
        suggestions = suggest.json()["suggestions"]
        assert suggestions[0]["feature"] == "chest_rise_respiration"

        submit = client.post(
            "/api/secondlook/submit",
            json={
                "session_id": session_id,
                "feature": "chest_rise_respiration",
                "landmark_series": _shoulder_frames(),
            },
        )
        assert submit.status_code == 200
        finding = submit.json()["findings"][0]
        assert finding["feature"] == "chest_rise_respiration"
        assert "limitations" in finding and finding["limitations"]

        # 5. Synthesis — run the job, then poll the result. TB must rank first
        # with the NTEP screening_rule cited verbatim in its reasoning chain
        # (rule 1: "consideration"/"screening", never "diagnosis" language).
        run = client.post("/api/synthesis/run", params={"session_id": session_id})
        assert run.status_code == 200

        result = client.get("/api/synthesis/result", params={"session_id": session_id})
        assert result.status_code == 200
        considerations = result.json()["considerations"]
        assert considerations, "synthesis produced no considerations"
        top = considerations[0]
        assert "tuberculosis" in top["disease"].lower()
        notes = [step.get("note") for step in top["reasoning_chain"]]
        assert NTEP_RULE in notes
        # Rule 1: never diagnostic language ("has"/"diagnosed with") — the
        # word "diagnosis" itself is fine in a disclaimer ("not a diagnosis").
        assert "diagnosed with" not in str(result.json()).lower()

        # 6. Report — PDF is actually produced and downloadable.
        generate = client.post("/api/report/generate", json={"session_id": session_id})
        assert generate.status_code == 200
        artifact_id = generate.json()["artifact_id"]

        download = client.get(f"/api/report/{artifact_id}")
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/pdf"
        assert download.content[:4] == b"%PDF"
        assert len(download.content) > 1000  # a real multi-section document, not an empty shell
