# Progress

**This is the hand-off file.** Every phase runs in a fresh session. Read this before
touching code; update it before stopping. See `CLAUDE.md` → Session hand-off protocol.

**Status key:** `⬜ not started` · `🟦 scaffolded (greyed, real layout/copy, not functional)` · `🟨 in progress` · `✅ done` · `⚠️ blocked`

---

## Phase status

| Phase | Scope | Status |
|---|---|---|
| 0 | Docs aligned with data + wireframe (2026-09-21) | ✅ |
| 1 | Foundation, graph seed, UI skeleton (all 19 states greyed) | ✅ |
| 2 | rPPG pipeline | ✅ |
| 3 | Session and person memory | 🟨 |
| 4 | Conversation and pain points | ✅ |
| 5 | Second look: face mesh and posture | ✅ |
| 6 | Synthesis, reasoning, report | ✅ |
| 7 | Developer mode, village, deploy, demo hardening | 🟨 (items 4/5/6 — deployment, demo hardening, docs — done; screens 16/17/i18n items tracked separately) |

---

## Screen activation

The visible measure of progress. Each state goes greyed → live as its feature lands.
Ids are wireframe labels (`specs.md` §2 has the alias mapping).

| Wireframe | Screen | Phase | Status |
|---|---|---|---|
| 1 | Camp dashboard | 3 | ✅ |
| 2 | Intake + consent | 3 | ✅ |
| 3 | Scan intro | 2 | ✅ |
| 4 | Live scan | 2 | ✅ |
| 4b | Live scan — low light / motion | 2 | ✅ (folded into 4's live states; kept as static preview route) |
| 5 | Vitals results | 2 | ✅ |
| 5b | Vitals results — low signal | 2 | ✅ |
| 6 | Voice consultation | 4 | ✅ |
| 7 | Analysing | 4 | ✅ |
| 8 | What we heard | 4 | ✅ |
| 9 | Edit symptoms | 4 | ✅ |
| 10 | Next step (agent suggestion) | 5 | ✅ |
| 11 | Guided motion capture | 5 | ✅ |
| 12 | Findings | 5 | ✅ |
| 13 | Assessment | 6 | ✅ |
| 14 | Session saved | 3 | ✅ |
| 15 | Person profile | 3 | ✅ |
| 16 | Knowledge graph (explain) / dev toggle | 6 / 7 | ✅ (Phase 7 — un-greyed; explain view and developer-mode D3 traversal both live against `/api/synthesis/explain`) |
| 17 | Village dashboard | 7 | ✅ (Phase 7 — un-greyed; reads real `GET /api/village/{village_id}/summary` aggregation with a live waterborne-illness cluster alert; static-fallback copy still matches the wireframe 1:1 when Neo4j is unreachable) |

---

## Golden path readiness

The demo is only real when every row is green.

| Step | Works | Notes |
|---|---|---|
| Seed loads clean; golden-path slugs resolve | ✅ | `backend/tests/test_seed.py`, 10/10 passing against the CSVs/YAML directly (no live Neo4j needed for the test) |
| Intake with consent | ✅ | `/api/session/start` rejects `consent: false` with 400; screen 2 blocks the CTA until checked and validated age. Verified against a live (Neo4j-less) backend with curl; full Neo4j write path not exercised in this sandbox (no Docker daemon available here — needs `docker compose up` verification before the demo) |
| Real rPPG scan, quality gated (4b / 5b states) | ✅ | Verified end-to-end against the backend pipeline (synthetic tests) and rendered in-browser (screens 3/5/5b); live camera capture needs manual verification with a real webcam — the sandboxed preview browser blocks getUserMedia |
| Telugu transcription | ✅ | `GeminiSTT` wired for en/te/hi through `POST /api/consult/transcribe`; the golden-path Telugu transcript is cached to `backend/app/providers/golden_path.json` and served when the live call is unavailable or the input matches the demo script. **Live Gemini call unverified — no API key in this sandbox** |
| Speaker attribution | ✅ | Content-based (`agents/attribution.py`) — transcript text to the LLM, labelled by who asks vs. who describes. Deterministic question-mark heuristic when the LLM is unavailable. No audio-diarization path exists. Tested in `test_consult.py` |
| Pain points extracted, canonicalised, editable | ✅ | `agents/extraction.py` (structured output) + `agents/normalise.py` (alias resolution). All 5 golden-path slugs resolve (`test_consult.py`). Screens 8/9 let the officer remove/correct/add; `POST /api/consult/painpoints` writes the reviewed list with `source: officer` |
| Agent proposes chest-rise capture | ✅ | `backend/tests/test_secondlook.py::test_golden_path_symptom_set_proposes_chest_rise_first` — the golden-path symptom set (cough, chest_tightness, fatigue, night_sweats, weight_loss) proposes `chest_rise_respiration` first via `agents/triggers.propose_features`. Screen 10 fetches this live from `GET /api/secondlook/suggest` |
| Guided capture completes | ✅ | Screen 11 runs live pose/face-mesh capture (`capture/secondLookCapture.ts`) and posts the landmark trace to `/api/secondlook/submit`, which runs `agents/secondlook_features.py` and routes to screen 12. Camera-based capture unverified with a real webcam in this sandbox (same `getUserMedia` limitation as Phases 2/4) |
| TB consideration with reasoning chain citing the NTEP rule | ✅ | `agents/reasoning.py::traverse_candidates` cites the exact `screening_rule` string off the curated `PRESENTS_WITH` edge only when the reported cough duration meets `min_duration_days`; `backend/tests/test_synthesis.py::test_tb_reasoning_chain_cites_ntep_screening_rule` and `::test_screening_rule_not_cited_when_duration_below_threshold` |
| Risk model output with metric | ✅ | `risk/models.py` — documented rule-based scorers (no trained artifact; see Open questions below), every output carries `metric`/`basis`/`disclaimer`; `backend/tests/test_risk.py` |
| PDF generated | ✅ | `report/pdf.py` (ReportLab, specs.md §6 structure) + `POST /api/report/generate` / `GET /api/report/{artifact_id}` (`api/report.py`). Verified by calling `build_report_pdf()` directly in this sandbox against golden-path-shaped data — produces a valid multi-section PDF (4.3KB) with header/person/vitals/consultation/findings/considerations/risk/recommendations/disclaimer/footer all present. The FastAPI route itself was not exercised end-to-end (no server run in this sandbox) — needs a `docker compose up` curl check before the demo |
| Explainability graph (16) shows the chain | 🟨 | `GET /api/synthesis/explain` now derives its edges from the real top consideration's reasoning chain (falls back to the golden-path TB edges if none); screen 16 itself was not touched this phase (out of scope per the task's screen-touch constraint) — it already calls this endpoint from Phase 1's stub wiring, so it will render live data once un-greyed in Phase 7 |
| Runs offline against fixtures | ✅ | `test_synthesis.py` uses a stub `GraphClient` (no live Neo4j); `test_risk.py` is pure-function; both run in the existing `pytest backend/tests` offline suite |

---

## Decisions log

Append every architectural decision made during the build, with reasoning.

| Date | Decision | Reasoning |
|---|---|---|
| 2026-09-21 | Live consultation failures return explicit 4xx/5xx errors; golden-path transcript and pain points are available only in explicit fixture mode | Empty audio, missing keys, timeouts, and provider errors must never look like real patient/person-derived clinical content. Migrated the provider from deprecated `google-generativeai` to `google-genai`, load the repository `.env` for local Uvicorn runs, preserve the browser audio MIME type, and reject undersized recordings. |
| 2026-09-20 | Real rPPG, not simulated | Authenticity; quality gating absorbs the noise |
| 2026-09-20 | Neo4j over NetworkX | Real Cypher; developer-mode visual needs it |
| 2026-09-20 | Gemini always, offline as pitch | Time budget; provider seam keeps the claim honest |
| 2026-09-20 | Deploy live, demo from localhost | Credibility from the URL, reliability from local |
| 2026-09-20 | Client extracts RGB, server processes | Render free tier cannot take video over venue wifi |
| 2026-09-20 | One graph, two labelled subgraphs | Single-query traversal person → precaution |
| 2026-09-20 | Content-based speaker attribution | More robust than Gemini audio diarization |
| 2026-09-20 | TB as golden path | Real screening criteria we can actually capture |
| 2026-09-20 | Haemoglobin cut | No credible camera-based method across skin tones |
| 2026-09-20 | BP trend only, no mmHg | Published MAE ~8-9 mmHg, outside clinical tolerance |
| 2026-09-21 | Docs live at repo root; `CLAUDE.md` is the session entry point, `progress.md` the hand-off | Each phase is a new session with no chat memory |
| 2026-09-21 | `frontend/ui-reference/sanjeevani-flow.html` replaces the "Stitch per-screen HTML" | That is the wireframe that actually exists: one file, 19 states, plain CSS tokens |
| 2026-09-21 | Wireframe labels (1…17, 4b, 5b) are the canonical screen ids | Specs had 15, wireframe has 19; the extra states (4b, 5b, 7, 9) are required |
| 2026-09-21 | KB has two layers: Kaggle (`source: kaggle`) + curated (`source: curated`); curated overrides | Kaggle only supports Disease/Symptom/Precaution; everything clinical beyond that needs a provenance |
| 2026-09-21 | Symptom canonical term = cleaned Kaggle snake_case slug; aliases file for extraction | Makes "normalise to English canonical terms" enforceable |
| 2026-09-21 | Kaggle `PRESENTS_WITH.weight = frequency × severity/7` | Uses the only two signals the data has; curated edges override explicitly |
| 2026-09-21 | Composite health score cut (rule 9) | Undefined formula; reads as a verdict |
| 2026-09-21 | No offline/encryption claims in UI copy (rule 10) | Gemini is required; claim only what ships |
| 2026-09-21 | Screen 16 = explainability view + developer-mode toggle, one route | Same data, two depths; avoids a 20th screen |
| 2026-09-21 | Agent never authors clinical content; curated entries carry `review` status (rule 11) | CLAUDE.md "do not guess on anything clinical"; only TB restates published criteria |
| 2026-09-21 | Raw CSVs moved to `data/seed/kaggle/`, never hand-edited; all fixes live in `seed.py` | Rebuildable KB; defects are documented in `architecture.md` §5.4 |
| 2026-09-21 | Backend uses `uv`-compatible `pyproject.toml` (PEP 621, hatchling backend) rather than Poetry | Simpler single-file dependency spec; `uv pip install --system` in the Dockerfile keeps the image small and fast to build |
| 2026-09-21 | Frontend component vocabulary (`top`, `card`, `tag`, …) implemented as named exports in one `frontend/src/components/Primitives.tsx` rather than 30 separate files | Phase 1 velocity; still "one React component per class" in spirit — CLAUDE.md's intent (composability, no ad-hoc styling in screens) is preserved. Revisit if a component grows non-trivial state/logic |
| 2026-09-21 | Screens 16 (knowledge graph) and 17 (village dashboard) built from the component vocabulary rather than transcribed from the wireframe file | `frontend/ui-reference/sanjeevani-flow.html` does not carry markup for these two states (its own 20-step flow index maps 1-15 plus 4b/5b only); specs.md §2 fully specifies their content, so they were composed from the same tokens/components per CLAUDE.md "If the spec needs a state the wireframe lacks" |
| 2026-09-21 | Fixed the Kaggle join-key bug during seed-test verification: raw slug is `dimorphic_hemmorhoids_piles` (with underscore before "piles" from the `(piles)` parenthesis), not `dimorphic_hemmorhoidspiles` as first drafted | Caught by `test_every_kaggle_disease_has_symptom_description_precaution`; documents the exact broken-join fix architecture.md §5.4 calls for |
| 2026-09-21 | `api/kb.py` falls back to a small static mock symptom/disease list when Neo4j is unreachable | Keeps `docker compose up` demoable even before the seed job has been run manually |
| 2026-09-21 | te.json / hi.json shipped as placeholder files with only a `_note` key, English fully filled | Matches the already-logged open question "Telugu and Hindi copy — machine translated or reviewed?"; do not guess on trilingual clinical copy |
| 2026-09-21 | te.json / hi.json filled with machine-translated UI chrome copy (all 75 keys, matching en.json 1:1) | Phase 7 item 3. UI chrome only (buttons, labels, screen titles, status strings) — not clinical content, not the `golden_path.json` scripted Telugu speech (separate, already logged). No live translator/native speaker in this sandbox, so `_note` field kept and reworded to flag machine-translation and the need for native-speaker review before demo, rather than clearing the open question |
| 2026-09-21 | `normalise()` in `rppg/signal.py` divides by the temporal mean (DC), not z-score to unit variance | POS/CHROM extract the pulse from the *relative* AC/DC ratio across R/G/B (different hemoglobin absorption per wavelength); z-scoring to unit variance equalises that ratio away and cancels the pulse to numerical noise. Caught by `test_clean_1_2hz_sinusoid_returns_72bpm` returning ~64bpm off a degenerate synthetic signal before the fix |
| 2026-09-21 | Wireframe 4b (low light/motion) is not a separate live route; `Screen4LiveScan.tsx` renders that exact visual state itself, driven by live client quality feedback (face_lost / low_light / high_motion / good) | Matches specs.md §2's own description of 4b as "a state of screen 4, not a separate route"; `/4b` is kept only as the wireframe-referenced static preview |
| 2026-09-21 | Phase 2 uses a `sessionStorage`-backed `capture/sessionStore.ts` (session id + vitals result handoff) instead of the full session-creation flow | `/api/session/start` and person intake are Phase 3; the scan flow (3→4→5/5b) needed to be independently testable now. Falls back to the golden-path demo session id (`SAN-2026-0982`) when Phase 3 hasn't set a real one |
| 2026-09-21 | Screen 2 (Intake) got age validation (integer, 0–120) ahead of full Phase 3 activation, still wrapped in `GreyedOverlay` | Explicit Phase 2 instruction ("Validate age at intake so the results screen can never render an invalid demographic"); small, non-clinical, golden-path-serving addition per CLAUDE.md's improvisation allowance |
| 2026-09-21 | `roi.ts`'s `RoiSampler.sampleRoi` averages the landmark polygon's axis-aligned bounding box rather than clipping to the exact polygon | Per-pixel polygon clipping via canvas `clip()` plus `getImageData` on every ROI, every frame, at 30fps was too expensive for a live capture loop; the bbox is still a real per-pixel average of the live video frame (never a simulated value), just a coarser region |
| 2026-09-21 | Passive findings (pallor, facial tension, blink rate) computed server-side from the RGB/motion traces already being sent, not from a separate eye/iris landmark stream | No infrastructure exists yet to send eye-landmark data (would mean sending more than RGB+motion, against rule 5); pallor uses cheek redness ratio, facial tension uses motion-score variance, blink rate uses a coarse dip-counting heuristic on the forehead green channel. Documented as heuristic in code comments — revisit if reviewer wants tighter fidelity |
| 2026-09-21 | Tier 3 (`build_person_summary`) split into a pure function (`memory/summary.py`) and a graph-reading orchestrator (`memory/persistence.py`) | CLAUDE.md "signal-processing functions are pure" applied to memory too — lets the rolling-baseline/longitudinal-delta logic be tested without a live Neo4j, same pattern as `test_seed.py` |
| 2026-09-21 | Tier 1 `SessionState` lives in a module-level `_SESSIONS` dict in `memory/state.py` (`open_session` / `get_session` / `get_or_create_session`), not a class instance passed through FastAPI dependency injection | Simplest thing that works for a single-process hackathon demo; explicitly in-process and lost on restart per architecture.md §6, matching the existing job-queue pattern |
| 2026-09-21 | Background synthesis job queue is a module-level dict in `memory/jobs.py` (`create_job` / `run_job` / `latest_job_for_session`), driven by FastAPI `BackgroundTasks` | Explicit instruction: no Celery/Redis. `POST /api/synthesis/run` queues a job; `GET /api/synthesis/result` looks it up by session id and falls back to the same golden-path result if no job was queued yet, so the demo never shows a broken state |
| 2026-09-21 | `/api/session/save` (continuous Tier-2 reading writes) and `/api/session/complete` are new endpoints, not in specs.md §3 | specs.md only documents `/start` and `/pending`; the task explicitly requires continuous persistence and a lifecycle beyond start/pending, so these were added following the same request/response shape conventions as the rest of §3. Recorded here per CLAUDE.md's improvisation allowance — flag for a specs.md update |
| 2026-09-21 | `GET /api/village/autocomplete?prefix=` added, not in specs.md §3 | specs.md §2 requires "village (autocomplete from prior sessions)" on screen 2 but never contracts the endpoint; added the smallest thing that satisfies the requirement, with the same static-fallback pattern as `api/kb.py` |
| 2026-09-21 | Every write-side endpoint (`session.py`, `village.py` autocomplete) silently no-ops the graph write and keeps serving from Tier 1 / static fallback when `app.state.graph_client` is None or a Neo4j call raises | Matches the existing `api/kb.py` pattern exactly; keeps the frontend demoable without `docker compose up`, which this sandbox cannot run (no Docker daemon) |
| 2026-09-21 | Golden-path LLM/STT responses cached to `backend/app/providers/golden_path.json`, served by `providers/cache.py` when the input matches the demo script **or** any live call fails | A rate limit, a missing key or venue wifi must not kill the demo. Same explicit-fallback pattern as `api/kb.py`'s static mock and `sessionStore.ts`'s golden-path session id; every response carries `source: "live"` / `"golden_path_cache"` so nothing silently claims to be live |
| 2026-09-21 | `TranscriptTurn` gained `text_original`; `TranscribeResponse`/`ExtractResponse` gained `source`; `ExtractResponse` gained `red_flag_messages` | specs.md §2 screen 6 requires an original-language line *and* an English line, which the §3 shape cannot carry; `source` backs developer mode; `red_flag_messages` carries the officer-facing escalation copy so the frontend never has to author clinical text. Extensions to specs.md §3 — flag for a specs update |
| 2026-09-21 | `POST /api/consult/painpoints` added, not in specs.md §3 | Screens 8 and 9 are explicitly human-in-the-loop; the officer's corrections have to reach the graph and the audit log. Officer-authored entries are written with `source: 'officer'` on the `:PHI:Utterance` |
| 2026-09-21 | Screen 6 builds the transcript by re-transcribing the audio recorded so far every 20s, rather than a streaming STT socket | Gemini STT is request/response, not streaming. The first `MediaRecorder` chunk carries the WebM header, so concatenating chunks-so-far is decodable; this gives a genuinely live-building transcript with no fabricated turns, plus one final pass on stop |
| 2026-09-21 | Red flags are derived from `TRIGGER_TABLE`'s priority-0 rows rather than a second hand-authored table, and `facial_droop` is the **only** one | architecture.md §8 and specs.md §5 (`facial_asymmetry`) document exactly one escalation. Inventing more would be inventing clinical content (rule 11). Raised as an open question instead |
| 2026-09-21 | `detect_red_flags` matches canonical slugs only — never aliases or free text | An unmapped term must not trigger an escalation; the officer maps it on screen 9 first, which is exactly the human-in-the-loop guarantee screen 8's footer claims |
| 2026-09-21 | `agents/normalise.py` reuses `graph.seed.load_curated_aliases` rather than re-reading `symptom_aliases.csv` | One loader for that file. It is a read of a seed *file*, not a `:KB` write, and it lives in `agents/` not `api/`, so the "no api/ module imports graph.seed" structural check still holds |
| 2026-09-21 | Telugu strings in `golden_path.json` were authored for the demo script and are unreviewed | They are the person's speech in the scripted consultation, not clinical content or UI copy — but they still need a native-speaker check. Added to Open questions |
| 2026-09-21 | Manually-added symptoms (screen 9) are recorded with `confidence: 1.0` | The officer reporting it *is* the evidence, and the `:REPORTS` edge confidence is evidence confidence, not clinical certainty — the clinical weight still comes from the `PRESENTS_WITH` edge in the graph. Rule 6 is satisfied: the join edge still carries a confidence value |
| 2026-09-21 | Chest-rise/rPPG respiration disagreement tolerance set at >20% relative difference | Not specified in architecture.md §8 / specs.md §5 beyond "large disagreement lowers both confidence scores" — chosen as the most conservative documented-adjacent threshold; both sides' confidence/quality are discounted (×0.6) rather than either being discarded. Judgment call, flagged rather than guessed on anything clinical |
| 2026-09-21 | `propose_features` priority-number -> officer-facing band: 0/1 -> "high", 2/3 -> "medium", 4 -> "low" | `SecondLookSuggestion.priority` is a 3-value enum (specs.md §3) but `TRIGGER_TABLE` has 5 numeric priorities; this is the smallest mapping that keeps facial_asymmetry (0) and the golden-path respiratory pair (1) both "high" without collapsing the whole table to one band. Judgment call — not a new clinical rule, just a label mapping |
| 2026-09-21 | `lip_cyanosis`, `sclera_colour`, `blink_rate_tremor` implemented as documented-minimal (reuse the closest already-specified RGB-ratio / luminance-dip pattern from `rppg/pipeline.py`'s passive findings), confidence capped at ~0.5 and `limitations` states they are undocumented beyond the architecture.md §8 trigger-table one-line description | specs.md §5 only fully specifies 7 features (`chest_rise_respiration`, `swelling_asymmetry`, `guided_range_of_motion`, `pallor_check`, `posture_assessment`, `facial_asymmetry`, `gait_balance`); these 3 are trigger-table outputs without a dedicated spec section. Rather than inventing new clinical measurement logic (rule 11), reused the nearest already-documented pattern and lowered confidence + labelled the gap explicitly, per "do not guess on anything clinical" |
| 2026-09-21 | `:PHI:Finding -[:INDICATES]-> :KB:Symptom` slug mapping (`memory/persistence.FEATURE_INDICATES_SYMPTOM`) mirrors the same symptom groupings already in `agents/triggers.TRIGGER_TABLE` (e.g. `chest_rise_respiration` -> `exertional_breathlessness`) | architecture.md §5 requires every join edge to name a target symptom but does not enumerate one; using the table's own documented symptom-feature association avoids inventing a new mapping. An unmatched slug (KB doesn't carry it) writes no edge — the runtime never creates `:KB` nodes |
| 2026-09-21 | Second-look landmark payload shape (`{t, pose: {"11": [x,y,z], ...}, face: {...}}`) is a new convention, not specified in specs.md §3 beyond "Pose/mesh landmark series + feature id" | Kept as small, named indices only (shoulders/hips/elbows/wrists/ankles/ears for pose; nose tip + mouth corners for face) — never the full 33/468-point mesh or any image data (rule 5). Documented in `agents/secondlook_features.py`'s module docstring and mirrored by `frontend/src/capture/secondLookCapture.ts` |
| 2026-09-21 | No public dataset for anemia/COPD/hypertension/CKD risk models — shipped documented rule-based scorers instead of pickled scikit-learn artifacts | This sandbox has no internet access to source or validate a dataset this session; progress.md's own Open questions row pre-approved exactly this fallback. Every `risk/models.py` function is pure, restricted to architecture.md §9's phone-capturable feature list, and returns `metric`/`basis`/`disclaimer` so the UI/PDF never present a rule-based score as a trained-model accuracy figure. Swappable behind the same signature if a dataset is sourced later |
| 2026-09-21 | `RiskModelOutput.f1` made optional (`float \| None`); added `metric`, `basis`, and a mandatory `disclaimer` field | The rule-based scorers have no F1 to report; `f1` stays for a future trained artifact, `metric` carries the rule-based disclosure string instead. Extension to specs.md §3's shape — flag for a specs update, same pattern as every other Phase 3-5 API extension logged above |
| 2026-09-21 | Synthesis candidate scoring = `Σ(edge.weight × evidence_confidence) × (0.6 + 0.4 × symptom_coverage)`, capped at top 5 diseases | specs.md §7 says "weight × evidence confidence, summed per disease, with symptom-coverage and village-prior terms" but does not give a formula; this is the smallest one satisfying that description — coverage rewards diseases whose *documented* symptom set the person's reported symptoms actually span, evidence confidence comes from the highest-confidence pain point or finding that named the symptom. Village cluster context adds a flat +0.05 and appears in the chain with `role: context`, never `strongest` (specs.md §7) |
| 2026-09-21 | `GET /api/synthesis/result` runs the real traversal synchronously (not only via the queued background job) when no job has been queued yet for the session | specs.md §2 screen 13 can be reached without first going through screen 12's "See assessment" → queue step (e.g. direct navigation, or the officer skipping second look); returning a stale/empty result there would violate rule 9's spirit (never render a fabricated composite) more than a same-request traversal costs in latency for a single-officer demo |
| 2026-09-21 | PDF report artifacts stored in an in-process `dict[artifact_id, bytes]` in `api/report.py`, served by a new `GET /api/report/{artifact_id}` | Matches `memory/jobs.py`'s existing module-level-dict pattern (CLAUDE.md: no Celery/Redis, and no object storage was in the stack table to add) — not in specs.md §3, which only specifies `POST /api/report/generate` returning a URL; the URL now resolves to a real download instead of a placeholder |
| 2026-09-21 | Added `backend/tests/test_risk.py` and `backend/tests/test_report.py`; added `pypdf2>=3.0` to `pyproject.toml`'s `dev` extra | `test_synthesis.py` already covered the reasoning-chain traversal, but risk-model scoring and PDF output had no dedicated coverage yet. `test_report.py` extracts real text from the rendered PDF (via PyPDF2, already present in the environment) rather than asserting on the story list Claude built, so it actually verifies what a reviewer opening the file would see — disclaimer text, the screening-signal string, the NTEP citation, and the absence of any mmHg value |
| 2026-09-21 | Village-dashboard cluster threshold: `CLUSTER_WINDOW_DAYS = 6`, `CLUSTER_MULTIPLE = 3.0` (`backend/app/api/village.py`) | Wireframe screen 17's own copy is the only documented value ("9 cases in Kadiri West over 6 days" / "3x baseline"); no other threshold is specified anywhere. Baseline = average count over the 4 prior same-length windows (24 days of history), floored at 1.0 to avoid a divide-by-zero/trivial trigger on a hamlet with zero prior cases. Added `CLUSTER_MIN_COUNT = 3` (not wireframe-specified — a judgment call so a hamlet with one or two sessions total can't "spike" at 3x of a near-zero baseline) |
| 2026-09-21 | Village endemic-region prior resolved as: not implemented as a numeric prior at all — the dashboard's cluster detection compares session counts against the disease's own `PRESENTS_WITH` symptom set and a rolling baseline, never `rural_india.yaml`'s `endemic_regions` state-name field | `endemic_regions` names states ("Andhra Pradesh"), and no session carries a village→state join against that vocabulary (open question since Phase 6). Building one now would mean inventing a mapping the seed data doesn't provide. The dashboard's own cluster math doesn't need it — it compares a village's sessions against its own history, not a national prior — so the open question is resolved by *not* needing the prior, rather than by fabricating a join |
| 2026-09-21 | `village.py`'s `referred` and follow-up-compliance figures reuse existing data only: `referred` = sessions whose `/session/complete`-written `recommendations` list is non-empty; `followups_due` = sessions with `status == 'done_unopened'` | No dedicated "referral" or "follow-up compliance" concept exists in the graph (screen 1's Decisions log already flagged the same gap for "Referrals" — shown as "—" there). Rather than inventing a new tracked concept, the dashboard reuses the two real signals that already exist and documents the proxy explicitly in the endpoint's own docstring, per rule 9's spirit (never render a fabricated number as if it were a defined metric) |
| 2026-09-21 | `SANJEEVANI_FIXTURE_MODE` env var added to `providers/llm.py` (`fixture_mode()`) and checked at the top of both `GeminiLLM.complete()` and `GeminiSTT.transcribe()` | Phase 7 demo-hardening: a "no network at all" contingency distinct from the existing fail-on-error fallback (`providers/cache.py`). When set, every provider call raises `LLMUnavailable`/`STTUnavailable` immediately, without attempting the live Gemini call at all, so callers fall onto the golden-path cache exactly as they already do on a real failure — no new fallback branch needed anywhere else, the existing exception-handling chain (`api/consult.py`, `agents/attribution.py`) absorbs it for free. Read live via `os.environ.get(...)` each call, not cached at import, so it can be flipped without a process restart |
| 2026-09-21 | `docker-compose.yml`'s top-level `version: "3.9"` key removed | `docker compose config` (available in this sandbox, unlike prior phases' notes) flagged it as obsolete/ignored in current Compose syntax; cosmetic only, no behaviour change |
| 2026-09-21 | Render deploy uses a Blueprint (`render.yaml`) with `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`/`GEMINI_API_KEY` marked `sync: false` (Render prompts for them as dashboard secrets) rather than committing any value | Matches CLAUDE.md/system rules — secrets are never committed; the existing env var names (`NEO4J_URI` etc., already read by `graph/client.py`) were kept as-is, not renamed, so no code change was needed for AuraDB — `neo4j+s://` works through the same `AsyncGraphDatabase.driver()` call as `bolt://` |
| 2026-09-21 | No `frontend/vercel.json` added | The app uses `HashRouter` (`#/1`, `#/6`, …); a hash fragment never reaches the server as a path, so there is nothing for Vercel's static host to 404 on and no SPA rewrite rule is needed. `frontend/src/api/client.ts`'s `BASE_URL` was already reading `import.meta.env.VITE_API_BASE_URL` (falling back to `localhost:8000`) before this phase — no hardcoded URL to fix |
| 2026-09-21 | `backend/tests/test_golden_path_e2e.py` drives the real FastAPI app via `TestClient` with `SANJEEVANI_FIXTURE_MODE=true` and no live Neo4j, rather than mocking the provider seam directly | Exercises the actual HTTP routes end-to-end (session start through report download) for the first time — every prior phase's fixture-based test (`test_synthesis.py`, `test_report.py`, `test_secondlook.py`) covers pure functions or a single module, not the full chain. Synthetic rPPG/pose signals reuse the exact synthetic-signal technique already established in `test_rppg.py` / `test_secondlook.py` (a real signal fed through the real pipeline, never a fabricated *result*) |
| 2026-09-21 | Village dashboard `population` = distinct-person count in the graph for that village, not a real census figure | No population field exists anywhere in the schema — it's demographic metadata a health-camp session never captures. Screened-person count is an honest lower bound, not a fabricated statistic; documented in the endpoint's docstring. The static wireframe-fidelity fallback (served when Neo4j is unreachable) still uses the wireframe's own `4200` |
| 2026-09-21 | `backend/app/graph/demo_seed.py` added as a standalone script (not folded into `seed.py`) | `seed.py` is the idempotent KB-only seed (Kaggle + curated layers); this is `:PHI` demo/person data — a different concern, and mixing them would make `seed.py` non-idempotent for a fresh KB-only run. Reuses `memory.persistence.write_pain_points` / `complete_session` (same Cypher the live app uses) rather than a bespoke write path, backdating only `created_at` on session creation so the cluster falls inside the dashboard's real rolling window |
| 2026-09-21 | `d3-force`/`d3-drag`/`d3-selection` added for screen 16's developer-mode graph, not `neovis.js` | neovis.js drives its layout off a live Bolt/websocket connection from the *browser* to Neo4j — CLAUDE.md rule 5 ("never stream video to the backend") generalises to "the browser never talks to the database directly" for the same reason (load-bearing for the deployed demo, and a security boundary). D3-force lays out the exact JSON `GET /api/synthesis/explain?full=true` already returns from the backend, so the graph is real without opening a second, unaudited channel to Neo4j from the client. Individual `d3-force`/`d3-drag`/`d3-selection` packages instead of the full `d3` bundle to keep the addition minimal |
| 2026-09-21 | `ExplainResponse` gained `nodes`/`graph_edges` (`GraphNode`/`GraphEdgeOut` in `models.py`), populated only when `full=true` | specs.md §2 screen 16 says developer mode "expands to the real Neo4j traversal … highlighting the path used" but `GET /api/synthesis/explain` had no node/edge shape yet, only the ranked `edges` list. `api/synthesis.py::_build_dev_graph` is a pure function that reshapes the already-computed rank-1 consideration's reasoning chain into person/disease/symptom/context nodes and traversed edges — no new clinical lookup, no second graph query. Extension to specs.md §3's shape, same pattern as every other Phase 2-6 API extension logged above |

---

## Data profile (so nobody re-derives it)

Kaggle *disease-symptom-description* dataset, `data/seed/kaggle/`:

- `dataset.csv`: 4,920 rows → 304 unique after dedupe; 41 diseases; 131 symptoms;
  321 unique disease→symptom pairs.
- `Symptom-severity.csv`: 132 rows, weights 1–7. Junk row `prognosis`; `fluid_overload`
  duplicated (6, 4).
- `symptom_Description.csv`, `symptom_precaution.csv`: 41 rows each.
- Broken joins before cleaning: `spotting_ urination`, `dischromic _patches`,
  `foul_smell_of urine` (dataset) vs the severity file; `hemmorhoids` vs `hemorrhoids`
  (dataset vs description).
- Not in Kaggle but required: COPD, anemia, CKD; `night_sweats`, `chest_tightness`,
  `exertional_breathlessness`; all tests, exposures, stages, vital types, geography.
- Clinically odd pairs retained and down-weighted (log grows as found):
  Tuberculosis → `yellowing_of_eyes`; Common Cold → `chest_pain`; Bronchial Asthma →
  `high_fever`.

---

## Open questions

Raise here rather than guessing. Anything clinical must be asked, not assumed.

| Question | Raised | Resolved |
|---|---|---|
| Which public dataset for each risk model (anemia, COPD, hypertension, CKD)? If none confirmed by Phase 6, ship a documented rule-based scorer instead | 2026-09-20 | **2026-09-21 — no internet access in this sandbox to source/validate a public dataset (UCI CKD etc.), and `data/` carries no pre-trained artifact.** Shipped the pre-approved fallback: a documented, table-driven rule-based scorer (`risk/models.py`) restricted to phone-capturable features, `f1: null` (not measured — no held-out dataset), `metric`/`basis`/`"screening signal, not a diagnosis"` on every output. Swap-in point for a real artifact is the same function signature. Still open: sourcing a real dataset for Phase 7+ |
| Village endemic-region prior for synthesis scoring: `rural_india.yaml`'s `endemic_regions` names states (e.g. "Andhra Pradesh"), but no session carries a resolved village→region join against that vocabulary | 2026-09-21 | **2026-09-21 — resolved by not needing it.** `agents/reasoning.py::traverse_candidates` already accepts an optional `village_cluster` dict (disease-group match, +0.05 score, always `role: context`) for synthesis scoring, and that's sufficient — nothing further was added. The Phase 7 village dashboard (`api/village.py`) does its own cluster detection by comparing a village's own session history against itself (rolling baseline), which needs no state-level endemic-region prior at all. Inventing a village→state join against `endemic_regions` would have meant fabricating a mapping the seed data doesn't provide |
| Stamp/seal artwork for the PDF? | 2026-09-20 | |
| Telugu and Hindi copy — machine translated or reviewed? | 2026-09-20 | **2026-09-21 — machine-translated. `te.json`/`hi.json` now carry all 75 UI-chrome keys from `en.json` (full parity, no missing keys). No live translator/native speaker available in this sandbox — still needs native-speaker review before the demo. Not clinical content: button/label/status copy only.** |
| Doctor available to validate the golden path and sign off `rural_india.yaml` entries (`review: pending` → `approved`)? | 2026-09-20 | |
| Exact NTEP presumptive-TB wording to cite on the edge | 2026-09-21 | |
| Village baseline for cluster detection: rolling window length and multiple (wireframe says 3× over 6 days) | 2026-09-21 | **2026-09-21 — resolved using the wireframe's own numbers**, the only documented values: `CLUSTER_WINDOW_DAYS = 6`, `CLUSTER_MULTIPLE = 3.0`. Baseline = average session count over the 4 prior same-length (6-day) windows, i.e. 24 days of history, floored at 1.0. `CLUSTER_MIN_COUNT = 3` was added as a judgment call (not wireframe-specified) so a hamlet with only 1-2 sessions total can't trigger off a near-zero baseline. See `backend/app/api/village.py::cluster_alerts_from_rows` and `backend/tests/test_village.py` |
| Should any symptom other than `facial_droop` be a red flag (immediate escalation)? architecture.md §8 documents only the stroke case. **Not guessed — `detect_red_flags` ships with the one documented rule** | 2026-09-21 | |
| Telugu transcript strings in `backend/app/providers/golden_path.json` are unreviewed — needs a native speaker before the demo | 2026-09-21 | |

---

## Blockers

| Blocker | Impact | Owner | Status |
|---|---|---|---|
| Golden path is not producible from Kaggle alone | TB chain needs curated `night_sweats`, `chest_tightness`, the NTEP edge and `symptom_aliases.csv` | Phase 1 | ⬜ open — resolved by Phase 1 seed deliverables |

---

## Phase notes

### Phase 0 — docs alignment (2026-09-21)
- Profiled the data, read all 19 wireframe states, rewrote `CLAUDE.md`,
  `architecture.md` §4/§5/§7/§11/§13, `specs.md` §1/§2/§3/§4/§6 + new §7 (Knowledge
  base) and §8 (Wireframe copy rules).
- Moved `data/*.csv` → `data/seed/kaggle/`, wireframe → `frontend/ui-reference/`.
- `prompts.md` at the root is the owner's private prompt file; it is **not** part of
  the docs and is not referenced anywhere. Phase prompts are given manually.

### Phase 1 — foundation, graph seed, UI skeleton (2026-09-21)

**Done:**
- Monorepo scaffold matches architecture.md §11 exactly: `backend/app/{main.py,
  api/, rppg/, graph/, agents/, providers/, risk/, memory/, report/}`,
  `backend/tests/`, `frontend/src/{screens/, components/, capture/, api/, i18n/}`.
- `docker-compose.yml`: Neo4j 5 (healthchecked), backend (FastAPI on 8000),
  frontend (Vite dev server on 5173). `GEMINI_API_KEY` is optional — the app
  boots without it; `providers/llm.py` and `providers/stt.py` only raise if a
  call is actually made with no key set.
- `backend/app/graph/schema.cypher`: constraints/indexes for every `:KB` and
  `:PHI` node type in architecture.md §5, all `IF NOT EXISTS` (idempotent).
- `backend/app/graph/seed.py`: full Kaggle cleaning pipeline (4,920 → 304 unique
  rows after dedupe, slug rule, the exact broken-join fixes listed in
  architecture.md §5.4 including the `dimorphic_hemmorhoids_piles` ↔
  `dimorphic_hemorrhoids_piles` join), `weight = frequency × severity/7`, then
  the curated layer (MERGE, overrides Kaggle on same slug/edge).
- `data/seed/curated/rural_india.yaml`: 10 diseases (tuberculosis + copd,
  anemia, dengue, malaria, typhoid, hypertension, type_2_diabetes,
  chronic_kidney_disease, waterborne_illness), diagnostic tests, exposures,
  stages, vital types. Only `tuberculosis` is `review: approved`, with the
  exact edge `screening_rule: "NTEP presumptive TB: cough >= 2 weeks"`,
  `min_duration_days: 14`, `weight: 1.0`. Every other disease is `review:
  pending` — none were promoted without a clinician, per rule 11.
- `data/seed/curated/symptom_aliases.csv`: covers every specs.md §1 golden-path
  phrase and every architecture.md §8 trigger-table term.
- `backend/tests/test_seed.py`: 10 tests, **all passing**, run against the
  CSVs/YAML directly (no live Neo4j needed) — disease/symptom/precaution
  completeness, severity coverage, weight bounds, the five golden-path slugs,
  the exact TB screening edge, the approved/pending split, and a structural
  check that no `api/` module imports `graph.seed`.
- FastAPI skeleton: all 9 route modules (vitals, session, consult, secondlook,
  synthesis, report, person, village, kb), Pydantic model for every request/
  response in specs.md §3, all handlers `async def`, returning the exact
  golden-path mock values (HR 96, RR 22, SpO2 94%, session id
  `SAN-2026-0982`). `providers/llm.py` / `providers/stt.py` are Protocol-based
  seams; `google.generativeai` is imported only inside them. App imports
  cleanly and registers 20 routes with zero dependencies beyond Pydantic/
  FastAPI actually required to boot.
- React app: all 19 screens (1, 2, 3, 4, 4b, 5, 5b, 6, 7, 8, 9, 10, 11, 12, 13,
  14, 15, 16, 17) as components under `frontend/src/screens/`, wrapped in a
  `GreyedOverlay` (Phase-1 "Not yet implemented" affordance) while still
  rendering real layout/copy pulled from the wireframe with specs.md §8
  substitutions applied (no BP mmHg, no health score, no ICD codes, no
  offline/encryption claims, "screening" not "triage", golden-path values).
  React Router (`HashRouter`) wires all 19 with a step rail. Tailwind config
  extended 1:1 from the wireframe's `:root` tokens. `tsc -b --noEmit` and
  `vite build` both succeed with zero errors.
- `frontend/src/api/client.ts` + `api/types.ts`: one typed method per
  specs.md §3 endpoint, types hand-mirrored field-for-field from
  `backend/app/models.py`. No `fetch` outside `client.ts`.
- i18n: `react-i18next` wired, `en.json` fully filled, `te.json`/`hi.json`
  shipped as placeholders (open question, see above).

**Stubbed (intentionally, for later phases):** `rppg/signal.py` (POS/CHROM/
Welch — Phase 2), `agents/*` (extraction, triggers, synthesis, reasoning —
Phases 4-6), `risk/models.py` (Phase 6), `memory/state.py` Tier 2/3 persistence
(Phase 3), `report/pdf.py` (Phase 6). All raise `NotImplementedError` with a
comment naming the phase, so nothing silently returns wrong data.

**Not done / deviations:** see Decisions log above (uv-style pyproject over
Poetry, combined `Primitives.tsx`, screens 16/17 composed rather than
transcribed). No clinical content was invented beyond what §5 of
architecture.md and the golden path in specs.md §1 specify.

**How to run:**
```
docker compose up
# backend:  http://localhost:8000/health        -> {"status": "ok"}
# frontend: http://localhost:5173/#/1            -> camp dashboard (greyed)
# neo4j browser: http://localhost:7474            (neo4j / sanjeevani123)

# Seed the graph (once Neo4j is up):
docker compose exec backend python -m app.graph.seed

# Run the seed validation test (no Neo4j required):
cd backend && pip install -e ".[dev]" && pytest tests/test_seed.py -v
# -> 10 passed
```
Verify in the Neo4j browser with `MATCH (d:KB:Disease) RETURN count(d)` (41 +
10 curated, minus any curated slug that also exists in Kaggle, e.g. none
currently collide) and `MATCH (d:KB:Disease {slug:'tuberculosis'})-[r:PRESENTS_WITH]->(:KB:Symptom {slug:'cough'}) RETURN r.screening_rule`.

### Phase 2 — rPPG pipeline (2026-09-21)

**Done:**
- `backend/app/rppg/signal.py`: real `detrend` (moving-average high-pass),
  `normalise` (DC/temporal-mean division — see Decisions log for why this
  matters for POS/CHROM), `pos_projection`, `chrom_projection`, `bandpass`
  (4th-order Butterworth, zero-phase via `sosfiltfilt`), `welch_psd`,
  `dominant_frequency_bpm` (SNR-based quality).
- `backend/app/rppg/pipeline.py`: orchestrates specs.md §4 end-to-end —
  resample to uniform time base, motion-based frame rejection (fail fast
  >30% rejected), detrend/normalise/POS+CHROM cross-check per ROI, bandpass,
  Welch → HR; RSA-envelope → respiration; ratio-of-ratios → SpO2 (always
  `approximate`); feature-based BP trend classification (direction only,
  never mmHg); passive findings (pallor score from cheek redness ratio,
  facial tension from motion variance, blink rate from a forehead-luminance
  dip heuristic).
- `backend/app/api/vitals.py`: `/api/vitals/process` now runs the real
  pipeline instead of returning the Phase-1 hardcoded stub. Tiers are fixed
  per vital type (HR/RR `reliable`, SpO2 `approximate`, BP `trend_only`) per
  architecture.md §4's table; quality/values come from the pipeline.
- `backend/tests/test_rppg.py`: 6 tests, **all passing** — clean 1.2Hz
  sinusoid → ~72bpm (`test_clean_1_2hz_sinusoid_returns_72bpm`), >30%
  high-motion frames → `retake_recommended` with `rejected_fraction > 0.3`,
  pure-noise signal → low HR quality, bandpass correctly isolates an
  in-band frequency, POS projection shape check, BP output is always a
  categorical direction never a number.
- Client capture (`frontend/src/capture/`): `faceMesh.ts` wraps MediaPipe
  `FaceLandmarker` (WASM, GPU delegate, loaded from the public CDN model
  URL); `landmarks.ts` defines the forehead/cheek_l/cheek_r landmark index
  groups; `roi.ts` samples mean R/G/B per ROI per frame via an offscreen
  canvas (bbox-of-polygon approximation, see Decisions log); `rppg.ts`
  (`captureVitals`) drives the full 30s/30fps capture loop with live quality
  callbacks (`face_lost` / `low_light` / `high_motion` / `good`) and never
  sends video or image data — only the accumulated scalar traces, per rule 5.
- `frontend/src/api/types.ts` / `client.ts`: added `ROITrace` and
  `VitalsProcessRequest` types; `processVitals` is now fully typed (was
  `body: unknown`).
- Screens **3, 4, 5, 5b activated** (live, un-greyed): screen 3 requests real
  camera permission and reflects it in the status tag; screen 4 runs the real
  capture loop with a live signal-quality bar and instruction chips driven by
  client quality feedback, then POSTs to `/api/vitals/process` and routes to
  5 or 5b based on `retake_recommended`; screen 5 renders the real response
  (falls back to golden-path values only if no scan ran yet this session);
  screen 5b shows the real quality percentage and retakes via `/4`. Screen 4b
  is *not* a separate live route (matches specs.md §2's own description) —
  screen 4 renders that exact visual state itself; `/4b` is kept as a static
  wireframe preview only.
- Screen 2 (Intake): added age validation (integer 0–120) ahead of full
  Phase 3 activation, per explicit instruction — still `GreyedOverlay`d.
- `frontend/src/capture/sessionStore.ts`: `sessionStorage`-backed session id
  + vitals-result handoff between screens 3→4→5/5b, standing in for the
  Phase 3 session-creation flow (defaults to the golden-path session id).
- `frontend/package.json`: added `@mediapipe/tasks-vision`.
- `.claude/launch.json` added so the frontend dev server can be previewed.
- Verified: `pytest` 16/16 passing (10 seed + 6 rppg); `tsc -b --noEmit` and
  `vite build` clean; screens 3/5/5b render correctly in-browser with no
  console errors (screen 4's live capture loop could not be exercised in the
  sandboxed preview browser, which blocks `getUserMedia` — needs manual
  verification with a real webcam before the demo).

**Not done / deviations:** see Decisions log above (DC-normalisation fix,
4b folded into 4, sessionStorage handoff standing in for Phase 3, bbox ROI
sampling, heuristic passive findings). No haemoglobin estimation was
implemented (rule 3); no absolute BP value is ever emitted (rule 2); every
vital ships with a quality score and fixed tier (rule 4).

**Next:** Phase 3 (session/person memory) should replace `sessionStore.ts`'s
placeholder session-id handoff with the real `/api/session/start` flow and
wire screen 2's full intake (name/village/consent) end-to-end.

### Phase 3 — session and person memory (2026-09-21)

**Done:**
- `backend/app/memory/state.py`: Tier 1 `SessionState` (unchanged shape, added
  `person_id`) plus an in-process registry (`open_session`, `get_session`,
  `get_or_create_session`) so `api/session.py` can find a session's working
  memory across requests within the same process.
- `backend/app/memory/summary.py`: Tier 3 `build_person_summary()` — pure
  function, returns exactly the architecture.md §6 structure (`demographics`,
  `village_context`, `chronic_flags`, `vital_baselines` as rolling medians,
  `last_session` digest, `open_followups`). Also `vital_delta()` for the
  longitudinal-delta requirement. No I/O — tested directly in
  `backend/tests/test_memory.py` without a live Neo4j.
- `backend/app/memory/persistence.py`: Tier 2 continuous writes
  (`start_session`, `save_reading`, `complete_session`) and the graph-read
  side of Tier 3 (`fetch_person_summary`, `list_pending_sessions`,
  `village_autocomplete`). All Cypher lives in `graph/queries.py`
  (`CREATE_SESSION_READING`, `COMPLETE_SESSION`, `LIST_PENDING_SESSIONS`,
  `GET_PERSON_FOR_SUMMARY`, `LIST_PERSON_SESSIONS_WITH_READINGS`,
  `VILLAGE_AUTOCOMPLETE`).
- `backend/app/memory/jobs.py`: in-process background job queue
  (`create_job`/`run_job`/`latest_job_for_session`) backing
  `POST /api/synthesis/run` (FastAPI `BackgroundTasks`) and
  `GET /api/synthesis/result` (polls by session id). No Celery/Redis.
- `api/session.py`: `/start` now rejects any request with `consent: false`
  (400) and, when Neo4j is reachable, writes `:PHI:Person`/`:PHI:Village`/
  `:PHI:Session` immediately. New `/save` (continuous `:PHI:Reading` writes —
  called once per captured vital, not batched) and `/complete` (marks the
  session `done_unopened`, stores `top_findings`/`recommendations`). `/pending`
  now reads real `:PHI:Session` nodes when Neo4j is available, falling back to
  the golden-path mock otherwise (same pattern as `api/kb.py`).
- `api/person.py`: `GET /api/person/{id}` now assembles the Tier 3 summary via
  `memory.persistence.fetch_person_summary` and returns it as `summary` on
  `PersonProfileResponse`, alongside the real session timeline and
  `vital_series` built from `:PHI:Reading` nodes. Falls back to the
  golden-path Ramesh Kumar profile if the person has no graph data yet.
- `api/village.py`: new `GET /api/village/autocomplete?prefix=` for screen 2's
  village field, reading distinct `:PHI:Village` names.
- Screens **1, 2, 14, 15 activated** (live, un-greyed):
  - Screen 1 (camp dashboard) — real stat tiles and lists from
    `GET /api/session/pending`.
  - Screen 2 (intake) — full form wired to `POST /api/session/start`,
    village field autocompletes from `GET /api/village/autocomplete`, consent
    checkbox blocks the CTA and the backend enforces it independently.
  - Screen 14 (session saved) — calls `POST /api/session/complete` on
    mount, links to `/15?person=<id>` and back to `/1`.
  - Screen 15 (person profile) — reads `GET /api/person/{id}` (id from the
    `?person=` query param or the last-known id in `sessionStore`), renders
    the vital-baseline list, session timeline and per-vital trend from real
    data, with a loading state.
  - `frontend/src/capture/sessionStore.ts` gained `getPersonId`/`setPersonId`
    alongside the existing session-id handoff.
- `backend/tests/test_memory.py`: 4 tests — `build_person_summary` returns the
  exact architecture.md §6 key set and computes the correct rolling median
  across two sessions with different vitals; `vital_delta` computes the
  correct longitudinal change and returns `None` with fewer than two points;
  `SessionState` registry round-trips.
- Verified: `pytest` 20/20 passing (10 seed + 6 rppg + 4 memory); `tsc -b
  --noEmit` and `vite build` both clean; exercised the full lifecycle with
  curl against a live (Neo4j-less) backend — consent rejection, `/save`,
  `/complete`, `/pending`, `/village/autocomplete` all behave as expected
  under the graceful-fallback path; screens 1/2/14/15 render correctly
  in-browser against that backend (network calls fail gracefully to empty/
  golden-path states when the backend isn't running).

**Not done / deviations:**
- No live Neo4j was available in this sandbox (no Docker daemon), so the real
  graph-write path (`:PHI:Session`/`:PHI:Reading` creation, person-summary
  reads, village autocomplete against real data) is implemented and unit-
  tested at the pure-function level but **not** exercised end-to-end against
  a running database. Needs a `docker compose up` pass — start a session,
  save a couple of readings, complete it, then reopen `/api/person/{id}` and
  confirm `vital_baselines`/`vital_series` reflect the real writes — before
  the demo.
- `/api/session/save`, `/api/session/complete` and
  `/api/village/autocomplete` are not in specs.md §3; added per the task and
  logged in the Decisions log above. specs.md should be updated to match.
- Session ids are now `SAN-<year>-<4 hex chars>` (previously hardcoded
  `SAN-2026-0982`); the golden-path fallback session id in `sessionStore.ts`
  and the `/pending` mock are unchanged so screens 3-5b/12-13 (not yet wired
  to real sessions) keep working standalone.
- Screen 1's "Referrals" stat has no backing data yet (no referral concept in
  the graph until Phase 6's synthesis/report work) — shown as "—" rather than
  a fabricated number.
- Did not touch screens 3-13/16-17 beyond what they already had; person/
  session data they'll eventually write (transcript, findings, assessment)
  is still Phase 4-6 scope. `SessionState.findings` is consulted by
  `/complete` as a fallback for `top_findings` but nothing populates it yet.

**How to run:**
```
docker compose up
# then, per the golden path:
# 1. http://localhost:5173/#/1  -> camp dashboard (live counts)
# 2. + New person -> fill intake, check consent -> Continue to scan
# 3. complete the scan flow through to screen 14 -> "Session saved"
# 4. View person profile -> screen 15 shows the real timeline/baselines

pytest backend/tests -v   # 20 passed
```

### Phase 4 — conversation and pain points (2026-09-21)

**Done:**
- **Provider seam** (`backend/app/providers/`) now matches architecture.md §10
  exactly: `STTProvider` / `LLMProvider` Protocols, `GeminiSTT` / `GeminiLLM`
  implemented for real against `google-generativeai` (the SDK already in
  `pyproject.toml`), and `WhisperCppSTT` / `OllamaLLM` raising
  `NotImplementedError` with a comment saying they exist to back the offline
  pitch claim and are deliberately not wired. Both Gemini classes construct
  without a key (the app still boots) and raise `STTUnavailable` /
  `LLMUnavailable` only when a call is actually made.
- `providers/llm.py` owns the structured-output contract: `schema_instruction`
  (JSON Schema + "no markdown fences"), `strip_fences` (handles ```json fences
  and prose-wrapped JSON) and `parse_structured` (raises a clear `ValueError`
  rather than letting a `JSONDecodeError` escape a route handler).
- **Audio capture** — `frontend/src/capture/audio.ts`: `MediaRecorder` →
  WebM/Opus, live waveform from a WebAudio `AnalyserNode` RMS, elapsed timer,
  `snapshot()` for the in-progress blob, and an in-memory (never persisted)
  handoff of the finished recording from screen 6 to screen 7. Isolated from
  screens per CLAUDE.md; posted through `api/client.ts`, never `fetch` in a
  component.
- **Transcription** — `POST /api/consult/transcribe` (multipart audio +
  `session_id` + `language`) returns `{turns, language_detected, source}` for
  en / te / hi.
- **Speaker attribution by content** (`backend/app/agents/attribution.py`):
  the plain transcript text goes to the LLM, which labels each numbered turn
  `officer` or `person` by who asks questions and who describes what they feel.
  No audio-diarization code path exists anywhere. A deterministic heuristic
  (question mark → officer, else alternate) takes over when the LLM is
  unavailable, so a rate limit can never leave turns unlabelled.
- **Pain-point extraction** (`backend/app/agents/extraction.py`): Pydantic
  `ExtractionResult` through `LLMProvider.complete`; the prompt forbids
  inference, disease names and anything not actually said. The model never
  chooses the slug — `canonicalise()` resolves it afterwards and collapses
  duplicates to the highest-confidence entry.
- **Symptom normalisation** (`backend/app/agents/normalise.py`): resolves
  through `data/seed/curated/symptom_aliases.csv`, reusing
  `graph.seed.load_curated_aliases` (one loader for that file). Exact alias →
  slugified form → longest contained alias. Unresolvable terms keep
  `canonical: null` and carry `unmapped_text`; **runtime never creates a
  `:KB:Symptom`**.
- **The join into the graph**: new named Cypher in `graph/queries.py`
  (`CREATE_UTTERANCE`, `CREATE_UTTERANCE_REPORTS_SYMPTOM`,
  `DELETE_SESSION_UTTERANCES`, `LIST_SESSION_REPORTED_SYMPTOMS`) plus
  `persistence.write_transcript` / `write_pain_points`. Every `:REPORTS` edge
  carries `confidence` **and** `verbatim` (rule 6). The `OPTIONAL MATCH` on
  `:KB:Symptom` means an unknown slug writes the utterance and no edge — it can
  never create a node. No Cypher inline in business logic.
- **Red-flag detection** (`backend/app/agents/triggers.py`): pure, table-driven
  `detect_red_flags` / `red_flag_slugs`, derived from `TRIGGER_TABLE`'s
  priority-0 rows. Matches canonical slugs only. Feeds `red_flags` +
  `red_flag_messages` on `/extract` and `/painpoints`.
- **Golden-path cache** — `backend/app/providers/golden_path.json` +
  `providers/cache.py`: the exact specs.md §1 Ramesh Kumar consultation
  (Telugu + English transcript, attributed turns, all five pain points with the
  21-day cough). Served when 3 of 5 marker phrases match the input, or whenever
  a live call fails for any reason. Every response carries `source` so the UI
  never claims a cached answer was live.
- **Screens 6, 7, 8, 9 activated** (live, `GreyedOverlay` removed):
  - **6 — Voice consultation**: real mic capture, live waveform, elapsed timer,
    speaker chips (Officer name / Person name), timestamp, original-language
    line above the English line, "Stop and analyse". The transcript builds every
    20s from the audio recorded so far.
  - **7 — Analysing**: runs the real final transcription then the extraction,
    with the four-step checklist reflecting actual progress, then routes to 8.
  - **8 — What we heard**: symptom cards with confidence dots coloured by band
    (≥0.85 accent / ≥0.6 warn / else bad), duration + canonical-slug chips,
    verbatim quote in English and in the session language, remove (✕),
    "+ Add a symptom" → screen 9, red-flag banner when one fires, footer
    "Corrections are tracked in the audit log".
  - **9 — Edit symptoms**: picker searching `GET /api/kb/symptoms` by slug,
    name and alias; free text with no match is kept with `canonical: null` and
    `unmapped_text`; per-entry remove; saves via `POST /api/consult/painpoints`
    with `edited_by: "officer"`.
  - Every specs.md §8 substitution applied: no ICD codes, "Mic active",
    "Structured summary & screening priority", "Audio is sent for
    transcription; video never leaves the device" (no encryption or offline
    claim), Ramesh Kumar / 52y / SAN-2026-0982.
- `Primitives.tsx` gained `Wave({levels})` (live mic levels, falling back to the
  wireframe's static bars) and `ConfidenceDot` / `confidenceBand`. Additive
  only — no already-activated screen changed except `Screen2Intake`, which now
  calls `setLanguage()` so screen 6 knows the session language.
- `backend/tests/test_consult.py`: **22 tests, all passing** — table-driven
  red-flag engine (8 cases), escalation copy carries no diagnosis language, all
  five golden-path pain points resolve to non-null canonical slugs via the alias
  file (both by symptom name and by verbatim phrase), cough duration is 21 days
  (≥ the 14-day NTEP trigger), unresolvable terms stay unmapped, duplicate
  collapse, content-based attribution (LLM labels + deterministic fallback),
  golden-path cache matching, fence/prose-wrapped JSON parsing, and a structural
  check that **no module outside `app/providers/` imports
  `google.generativeai`** (mirrors `test_seed.py`'s `graph.seed` check).
- Verified: `pytest backend/tests -v` → **42 passed** (10 seed + 6 rppg +
  4 memory + 22 consult); `tsc -b --noEmit` and `vite build` both clean, zero
  errors; the three consult endpoints exercised with curl against a live
  (Neo4j-less) backend — `/transcribe` returns the 6 attributed bilingual turns,
  `/extract` returns the exact five specs.md §1 pain points with the right
  slugs / durations / confidences, and `/painpoints` with a `facial_droop` entry
  returns `red_flags: ["facial_droop"]`.

**Not done / deviations:**
- **Needs manual verification with a real API key and a real microphone before
  the demo** — the same limitation Phase 2 recorded for the live webcam loop.
  This sandbox has no `GEMINI_API_KEY` and no mic, so every path above ran
  through the golden-path fallback. Unverified: the live Gemini STT call on real
  WebM/Opus audio in Telugu and Hindi, the live attribution and extraction
  passes, and `MediaRecorder` capture itself (the preview browser blocks
  `getUserMedia`). To check: set `GEMINI_API_KEY`, open `#/6`, speak, and
  confirm the response carries `source: "live"` — a `"golden_path_cache"` source
  means the live call failed.
- No live Neo4j (no Docker daemon here), so the `:PHI:Utterance` / `:REPORTS`
  writes are implemented and follow the existing graceful-no-op pattern but were
  not exercised against a real database. Verify with
  `MATCH (u:PHI:Utterance)-[r:REPORTS]->(s:KB:Symptom) RETURN s.slug, r.confidence, r.verbatim`
  after a `docker compose up` run.
- `text_original`, `source`, `red_flag_messages` and `POST
  /api/consult/painpoints` are not in specs.md §3 — added per the task and
  logged in the Decisions log. specs.md should be updated to match.
- Only `facial_droop` is a red flag. Anything else would have been invented
  clinical content — raised in Open questions instead of guessed (CLAUDE.md
  "do not guess on anything clinical").
- Screen 8's "Continue →" routes to `/10` (still Phase 5, greyed). The inline
  marker chips screen 6's wireframe shows ("extracted terms as they appear") are
  not rendered during recording — extraction runs once, after stop, so showing
  them live would mean fabricating them.
- The Telugu transcript strings in `golden_path.json` are unreviewed (Open
  questions).

**How to run:**
```
docker compose up
# then, the consultation leg of the golden path:
# 1. http://localhost:5173/#/2  -> intake, pick తెలుగు, consent -> scan
# 2. finish the scan -> screen 5 -> "Start consultation"
# 3. #/6 grants mic, records, transcript builds -> "Stop and analyse"
# 4. #/7 runs transcription + extraction -> #/8 review, edit, #/9 add

# Live Gemini (otherwise every response is source: "golden_path_cache"):
export GEMINI_API_KEY=...        # optional: GEMINI_MODEL / GEMINI_STT_MODEL

pytest backend/tests -v                                 # 42 passed
cd frontend && npx tsc -b --noEmit && npx vite build    # clean
```

### Phase 5 — second look: face mesh and posture (2026-09-21)

**Done:**
- **Trigger engine** (`backend/app/agents/triggers.py`): `propose_features()`
  implemented — pure, deterministic, table-driven off the existing
  `TRIGGER_TABLE` (no new trigger rules invented). Ranked by priority (0 =
  `facial_asymmetry`, always first); each proposal carries `feature`,
  `priority` (mapped to the `high`/`medium`/`low` enum), `rationale` (names
  the actual triggering symptoms present this session), `instruction`
  (`FEATURE_INSTRUCTIONS`, one per feature per specs.md §5), and
  `triggered_by`. Duplicate features across multiple matching rules
  (`chest_rise_respiration` / `lip_cyanosis` both trigger on the same
  cough/breathlessness/chest-pain group) are de-duplicated, keeping the
  highest-priority occurrence.
- **Feature processing** (`backend/app/agents/secondlook_features.py`, new
  module): pure functions for all 7 specs.md §5 features
  (`chest_rise_respiration`, `swelling_asymmetry`, `guided_range_of_motion`,
  `pallor_check`, `posture_assessment`, `facial_asymmetry`, `gait_balance`)
  plus documented-minimal implementations for the 3 trigger-table-only
  outputs (`lip_cyanosis`, `sclera_colour`, `blink_rate_tremor` — see
  Decisions log). Every finding carries `value`, `unit`, `method`,
  `interpretation`, `confidence` and an explicit `limitations` string quoting
  the specs.md §5 limitation language (monocular asymmetry-not-volume,
  skin-tone/lighting confound, etc.). Confidence scales with usable-frame
  count and signal regularity, capped below 0.9 — never full confidence off
  one capture.
- **Respiration cross-check** (Task 3): `vitals.py::process_vitals` now
  writes the rPPG-derived RR into Tier 1 `SessionState.vitals`;
  `chest_rise_respiration()` compares its own rate against it and
  `cross_check_rr()` lowers both sides' confidence/quality when the relative
  difference exceeds 20% (threshold judgment call, logged above).
- **Graph writes**: `graph/queries.py` gained `CREATE_FINDING` and
  `CREATE_FINDING_INDICATES_SYMPTOM`; `memory/persistence.write_findings()`
  writes one `:PHI:Finding` per result and an `:INDICATES {confidence}` edge
  to the symptom the feature is documented to indicate
  (`FEATURE_INDICATES_SYMPTOM`, mirroring `TRIGGER_TABLE`'s own groupings).
  Same graceful-no-op pattern as every other api/ module when
  `graph_client` is `None` or a Cypher call raises.
- **`api/secondlook.py`** rewritten off the Phase-1 hardcoded stub:
  `GET /suggest` reads the session's canonical reported symptoms from Tier 1
  `SessionState.pain_points` (written by `/api/consult/extract` and
  `/painpoints`), falling back to the golden-path pain points if nothing has
  been extracted yet in-process. `POST /submit` dispatches to
  `FEATURE_PROCESSORS`, applies the RR cross-check for
  `chest_rise_respiration`, appends the finding to
  `SessionState.findings`, and best-effort writes it to the graph.
- **Frontend**: `frontend/src/capture/pose.ts` (new) wraps MediaPipe Tasks
  Vision `PoseLandmarker`, same WASM/CDN pattern as `faceMesh.ts`, with a
  `POSE_LANDMARKS` index reference (shoulders 11/12, hips 23/24, elbows,
  wrists, ankles, ears). `frontend/src/capture/secondLookCapture.ts` (new)
  drives the guided-capture loop: runs pose and/or face mesh depending on the
  requested feature, accumulates a small named-landmark trace per frame
  (never video/image data), and reports live metrics (cycles, fps, lock) via
  a callback. `sessionStore.ts` gained the screen 10→11→12 handoff
  (`storeSecondLookSuggestions`, `setChosenFeature`/`getChosenFeature`,
  `appendSecondLookFindings`/`readSecondLookFindings`). `api/types.ts` /
  `client.ts` gained typed `SecondLookSuggestResponse`,
  `SecondLookSubmitRequest`/`Response`, `LandmarkFrame`.
- **Screens 10, 11, 12 activated** (`GreyedOverlay` removed):
  - **10 — Next step**: fetches `GET /api/secondlook/suggest` on mount,
    renders the real priority card (red-flag styled and labelled when
    `facial_asymmetry` is first) with its rationale quoting the triggering
    symptoms, an "Also suggested" list of the remaining ranked suggestions,
    "Start capture" (stores the chosen feature, routes to 11) and "Skip to
    findings" (routes to 12).
  - **11 — Guided motion capture**: requests the camera, runs
    `captureFeature()` for the chosen feature with live positioning guidance
    text (`POSITIONING_GUIDANCE`), a countdown, and the wireframe's
    cycles/fps/lock readout, then posts to `/api/secondlook/submit` and
    routes to 12. Cancel aborts the capture and returns to 10.
  - **12 — Findings**: renders the accumulated second-look findings (value,
    method, interpretation, confidence bar, limitations) grouped under "From
    the guided capture", plus the passive vitals findings from screen 4/5
    under "From the face scan", using the exact wireframe card layout.
    "See assessment" routes to `/13` (Phase 6 — navigation only, no screen
    13 content built).
- **Screen 8 → 10 wiring** (Task 9): verified — screen 8 already writes
  `state.pain_points` via `/api/consult/extract` and `/painpoints` before
  routing to `/10`; `api/secondlook.py::_session_canonical_symptoms` reads
  exactly that Tier 1 state, so no change was needed there beyond the new
  endpoint logic itself.
- `backend/tests/test_secondlook.py` (new): table-driven `propose_features`
  tests (11 symptom-set cases including the golden path and an unrelated
  symptom producing no proposals), a facial-asymmetry-always-first test, a
  rationale-quotes-the-symptom test, synthetic-signal tests for
  `chest_rise_respiration` (recovers an approximate rate from a synthetic
  18 brpm oscillation), the cross-check disagreement/agreement behaviour, a
  missing-landmarks low-confidence test for `facial_asymmetry`, and a
  required-fields check.
- Verified: `pytest backend/tests -v` → **63 passed** (10 seed + 6 rppg +
  4 memory + 22 consult + 21 secondlook); `npx tsc -b --noEmit` and
  `npx vite build` both clean, zero errors.

**Not done / deviations:**
- **Needs manual verification with a real webcam before the demo** — same
  limitation as Phases 2 and 4 (`getUserMedia` is blocked in this sandbox's
  preview browser). Screen 11's live pose/face-mesh capture loop and the
  MediaPipe `PoseLandmarker` model load were exercised for build/type
  correctness only, not against a live camera feed.
- No live Neo4j in this sandbox (no Docker daemon), so `:PHI:Finding` /
  `:INDICATES` writes are implemented and unit-testable at the pure-function
  level but not exercised against a running database. Verify with
  `MATCH (f:PHI:Finding)-[r:INDICATES]->(s:KB:Symptom) RETURN f.feature, s.slug, r.confidence`
  after a `docker compose up` pass.
- `lip_cyanosis`, `sclera_colour`, `blink_rate_tremor` are the 3 trigger-table
  features specs.md §5 doesn't fully specify; implemented as
  documented-minimal, low-confidence-capped reuses of already-specified
  patterns rather than invented clinical logic (Decisions log above). If a
  clinician reviews this build, these three should be the first things
  checked or explicitly deferred.
- The chest-rise/rPPG 20% disagreement tolerance is a judgment call, not a
  cited threshold (Decisions log above) — flag for clinical review.
- Screen 12's "See assessment" routes to `/13`, which remains Phase 6's
  greyed stub — not touched, per the task's constraints.
- `screens 3-9/13-17` were not touched beyond what Task 9 required (verifying
  the existing screen 8 → pain-points → `/10` wiring, which needed no change).

**How to run:**
```
docker compose up
# then, the second-look leg of the golden path:
# 1. finish the consultation through screen 9 (cough, chest_tightness,
#    fatigue, night_sweats, weight_loss)
# 2. #/10 -> "Recommended next step" shows the chest-rise capture as priority,
#    rationale quoting "cough"
# 3. "Start capture" -> #/11 grants the camera, runs the guided capture,
#    posts to /api/secondlook/submit
# 4. #/12 -> Findings shows the respiration finding plus the passive vitals

pytest backend/tests -v                                 # 63 passed
cd frontend && npx tsc -b --noEmit && npx vite build    # clean
```

### Phase 6 — synthesis, reasoning, report (2026-09-21)

**Done:**
- `graph/queries.py` — `CANDIDATE_DISEASES_FOR_SYMPTOMS` and `DISEASE_FINDING_EDGES`,
  named Cypher constants, capped traversal (never dumps the whole KB).
- `agents/reasoning.py::traverse_candidates` — the real graph traversal + scoring.
  Score = weighted evidence sum × (0.6 + 0.4 × symptom coverage), +0.05 for a
  village-cluster context match (tagged `role: context`, never `strongest`).
  Capped at `TOP_N_CANDIDATES = 5` (documented choice — specs.md sets no
  number). Returns an ordered `evidence → edge → conclusion` reasoning-chain
  list per candidate, citing the curated `screening_rule` string verbatim only
  when `min_duration_days` is actually met by the reported symptom duration.
  Falls back to `[]` gracefully with no graph client or no resolved symptoms —
  same pattern as every other `api/` module.
- `risk/models.py` — documented rule-based scorers for anemia, COPD,
  hypertension, CKD, restricted to phone-capturable features. No trained
  artifact (no internet access in this sandbox to source/validate a public
  dataset — see Open questions). `hypertension_risk` never takes or emits an
  mmHg value (rule 2, trend direction only); `anemia_risk` never estimates
  haemoglobin (rule 3, pallor-based only). Every output carries `metric`,
  `basis` and the literal `"screening signal, not a diagnosis"` string.
  `run_all()` skips any model whose required capture is missing rather than
  fabricating an input.
- `report/pdf.py` — full ReportLab pipeline matching specs.md §6's 10-part
  structure exactly (header → person block → vitals table with confidence
  tiers, BP trend-only → consultation summary → second-look findings with
  limitations → ranked considerations with reasoning chains → risk outputs
  with metrics → recommendations → disclaimer block → footer with page
  numbers/timestamp/verification ID). Pure builder: plain dict in, PDF bytes
  out — no I/O beyond the in-memory buffer, so it never needs a live event
  loop or DB connection to render. A small per-language dict gives the
  person-facing headline line in the session language; the clinical body
  stays English throughout (CLAUDE.md > Graph conventions).
- `api/synthesis.py` — `/run`, `/result`, `/explain` now call the real
  traversal against Tier 1 `SessionState`, falling back to the golden-path TB
  synthesis when the graph is unreachable, no session state exists yet, or no
  symptoms have resolved (same graceful-no-op pattern as the rest of the app).
- `api/report.py` — `/generate` assembles session data (Tier 1 state +
  golden-path fallback fields), calls `report/pdf.py`, stores bytes in an
  in-process artifact store (module-level dict, same pattern as
  `memory/jobs.py` — no object storage added). `GET /api/report/{artifact_id}`
  serves the PDF for download.
- Frontend: screen 13 (Assessment) is live — un-greyed, fetches
  `GET /api/synthesis/result`, renders ranked considerations with expandable
  reasoning chains, risk-check items with metric + disclaimer, priority tags,
  and a "Download report" button wired to `POST /api/report/generate`.
  Golden-path fallback data lives client-side too, so the screen never shows
  broken state if the backend is unreachable. Report-download button also
  wired on screen 5 (Vitals results). `api/client.ts`/`api/types.ts` carry the
  typed request/response shapes; no `fetch` in either screen component.
- Tests added this phase: `backend/tests/test_synthesis.py` (7 cases — fixture
  `GraphClient` stub, asserts the NTEP chain, ordered-list shape, TB > COPD
  ranking, duration-gated screening_rule citation, Top-N cap, graceful
  fallbacks), `backend/tests/test_risk.py` (10 cases — table-driven, every
  output discloses the screening-signal string, hypertension/anemia never
  carry an mmHg/haemoglobin value), `backend/tests/test_report.py` (5 cases —
  real PDF-text extraction via PyPDF2, asserts the disclaimer, screening-signal
  string, NTEP citation, and the absence of any mmHg value in the rendered
  document). Added `pypdf2` to `pyproject.toml`'s `dev` extra for the report
  test's text extraction.

**Not done / deviations:**
- Screen 16 (Knowledge graph / explain) was **not** un-greyed this phase —
  out of scope per the task brief ("do not touch screens 14-17 beyond
  report-download wiring on screen 5"). `GET /api/synthesis/explain` already
  returns real data derived from the top consideration's reasoning chain, so
  the screen will render live once Phase 7 removes its `GreyedOverlay`.
- No risk-model dataset was sourced (no internet access) — rule-based scorers
  are the shipped, documented fallback; see Open questions.
- Village endemic-region prior is not a numeric score term — `rural_india.yaml`
  names states in `endemic_regions`, but no session carries a resolved
  village→region join against that vocabulary. Adding a number without a real
  join would be inventing evidence, so it is left for Phase 7 and logged in
  Open questions instead.
- Person-facing PDF summary is a single translated headline line, not a fully
  translated document body — no translated string catalogue exists for report
  prose in this build (only UI copy is translated via react-i18next).

**How to run:**
```
docker compose up
# golden path through synthesis + report:
# 1. finish the consultation (screens 6-9) and second-look capture (10-12)
# 2. #/13 Assessment -> GET /api/synthesis/result shows TB (rank 1, high
#    priority, NTEP-cited reasoning chain) and COPD (rank 2); tap "Show
#    reasoning chain" on a card to expand it
# 3. "Download report" -> POST /api/report/generate -> opens the PDF from
#    GET /api/report/{artifact_id} in a new tab
# 4. Same download button is live on #/5 (Vitals results)

pytest backend/tests -v                                 # 63 -> 86 passed
cd frontend && npx tsc -b --noEmit && npx vite build    # clean
```

### Phase 7
_In progress — see subsections below for items completed this phase._

### Phase 7 — developer mode graph visualization (2026-09-21)

**Done (item 1 of Phase 7 — screen 16 developer mode):**
- `backend/app/models.py`: `ExplainResponse` gained `nodes: list[GraphNode]` and
  `graph_edges: list[GraphEdgeOut]`, populated only when `?full=true`. Pure
  pass-through shape — no new clinical content, just a node/edge list a force-
  graph renderer can consume directly (person/disease/symptom/context node
  types; edges carry `relationship`, `weight`, `confidence`, `role`,
  `highlighted`).
- `backend/app/api/synthesis.py::_build_dev_graph` (new, pure function):
  reshapes the already-computed rank-1 consideration's reasoning chain
  (`ExplainEdge[]`, itself derived from `agents/reasoning.py::traverse_candidates`)
  into that node/edge list. No second graph query, no invented clinical
  content — every node/edge traces back to data `traverse_candidates` already
  produced. `GET /api/synthesis/explain` builds it only when `full=true`;
  the default explainability view response is unchanged.
- Frontend: `frontend/src/components/GraphViz.tsx` (new) — a D3-force graph
  (`d3-force`/`d3-drag`/`d3-selection`, see Decisions log for why not
  neovis.js) rendered as SVG, dark-theme tokens only (`--accent`/`--bad`/
  `--warn`/`--text-3`), draggable nodes, traversed-path edges rendered solid
  and full-opacity, `context`-role edges (village priors) rendered dashed and
  dim — the highlighted-vs-dimmer contrast the task asked for. The browser
  fetches only `GET /api/synthesis/explain?full=true` from the backend; it
  never opens a connection to Neo4j itself.
- `frontend/src/screens/Screen16Graph.tsx`: **un-greyed** (`GreyedOverlay`
  removed). Default view fetches `GET /api/synthesis/explain` (real reasoning-
  chain edges, ranked list with role tags and the NTEP `screening_rule` line
  where present) — golden-path fallback client-side if the backend is
  unreachable, same pattern as screen 13. "Developer mode" `Seg` toggle
  (specs.md §2's dev-mode affordance) lazily fetches
  `GET /api/synthesis/explain?full=true` on first switch and renders it
  through `GraphViz`; if that call fails (no live backend/Neo4j), the graph
  area just shows nothing rather than a fabricated traversal — no invented
  data path was added.
- `frontend/package.json`: added `d3-force`, `d3-drag`, `d3-selection` (+
  their `@types/*`) — the one approved stack addition for this task.
- `backend/tests/test_synthesis.py`: 4 new tests for `_build_dev_graph` —
  person+disease nodes always present, one node per evidence row (symptom vs
  context type split), every symptom/context node's edge targets the disease
  node (the traversed path), and village-context edges are never marked
  `strongest`. All pure-function, no live Neo4j/FastAPI server needed, same
  fixture pattern as the existing `traverse_candidates` tests in this file.

**Verified:**
- `pytest backend/tests -v` → **90 passed** (86 prior + 4 new
  `_build_dev_graph` tests).
- `cd frontend && npx tsc -b --noEmit && npx vite build` — both clean, zero
  errors/warnings.
- Not verified in this sandbox: the developer-mode graph against a *live*
  Neo4j-backed traversal (no Docker daemon here, same limitation as every
  prior phase) — `_build_dev_graph` was exercised against fixture
  `ExplainEdge` rows and the golden-path fallback path in
  `api/synthesis.py::explain`, and `GraphViz` was exercised via `tsc`/`vite
  build` only. Needs a `docker compose up` pass: open `#/16`, toggle
  "Developer mode", confirm the force-graph renders the same TB chain as the
  explain-view list below it.

**Not done / deviations:**
- Only item 1 of Phase 7 (developer mode, screen 16) is covered by this
  entry. Village dashboard (screen 17), deploy, and demo hardening are other
  Phase 7 items — out of scope here, owned by other concurrent sessions per
  the task brief.
- `full=true`'s node/edge list is built only from the **top-ranked**
  consideration's reasoning chain (same scope `GET /api/synthesis/explain`
  already had without `full`) — it does not additionally traverse or render
  the other up-to-4 lower-ranked considerations from `/synthesis/result`.
  specs.md §2 describes developer mode as expanding "the real Neo4j traversal
  for the session," which the golden path's session is exactly this one
  consideration; extending to multi-consideration traversal would be a
  UI/product decision (how to visually multiplex several diseases in one
  force-graph) rather than a data-availability gap, so it's flagged here
  rather than guessed at.

**How to run:**
```
docker compose up
# then, from the assessment screen:
# 1. finish the golden path through #/13 (Assessment)
# 2. "Open knowledge graph" (screen 15) or navigate to #/16 directly
# 3. Explain view shows the ranked evidence list (cough/weight_loss/
#    night_sweats/respiration_rate/village cluster) with role tags
# 4. Toggle "Developer mode" -> force-graph renders the same evidence as
#    nodes converging on the disease node, traversed edges highlighted,
#    village-context edge dashed/dim; drag nodes to rearrange

pytest backend/tests -v                                 # 90 passed
cd frontend && npx tsc -b --noEmit && npx vite build    # clean
```

### Phase 7 — village dashboard (2026-09-21)

**Done (item 2 of Phase 7 — screen 17 village dashboard):**
- `backend/app/graph/queries.py`: added `VILLAGE_MATCHING_SESSIONS` (village →
  person → session, with each session's reported-symptom slugs collected via
  `:TRANSCRIBED`/`:REPORTS`, using the same substring-prefix convention as the
  existing `VILLAGE_AUTOCOMPLETE`), `DISTINCT_PERSON_COUNT_FOR_VILLAGE`, and
  `DISEASE_SYMPTOM_SLUGS` (a curated disease's `PRESENTS_WITH` symptom set +
  its real `mitigation` copy). No Cypher inline in `village.py`.
- `backend/app/api/village.py`: `GET /api/village/{village_id}/summary` now
  runs the real aggregation when Neo4j is reachable and the village has
  session data, falling back to the exact previous wireframe-fidelity static
  response otherwise (same graceful pattern as every other `api/` module).
  Split into pure, independently-testable functions:
  - `cluster_alerts_from_rows` — the waterborne-illness cluster detector.
    Compares, per hamlet (`:PHI:Village.name`), the count of sessions
    reporting a symptom in `waterborne_illness`'s own curated symptom set
    within the last `CLUSTER_WINDOW_DAYS` (6) against the average count over
    the 4 prior same-length windows, alerting when the ratio reaches
    `CLUSTER_MULTIPLE` (3.0) — both numbers are the wireframe's own copy, the
    only documented threshold (Open questions, resolved this phase). A
    `CLUSTER_MIN_COUNT` (3) floor avoids alerting on a hamlet with 1-2
    sessions total.
  - `aggregate_village_summary` — screened/referred/followups-due (quarter
    window), top symptoms, hamlet breakdown, month trend, all from real
    `:PHI:Session`/`:REPORTS` rows.
  Both are pure (rows in, response out) — no I/O — same "signal-processing
  functions are pure" convention CLAUDE.md applies elsewhere, and it's what
  makes `test_village.py` possible without a live Neo4j.
- `population` = distinct screened-person count for the village (no
  population field exists in the graph at all); `referred` = sessions whose
  `/session/complete`-written `recommendations` list is non-empty;
  `followups_due` = sessions with `status == 'done_unopened'` (the existing
  Phase 3 lifecycle state — no new compliance concept invented). All three are
  documented as proxies in the module docstring, not presented as more precise
  than they are.
- `backend/app/models.py`: unchanged — `VillageSummaryResponse` and its
  sub-models already matched specs.md §2/§3's shape exactly from the Phase-1
  scaffold.
- `backend/app/graph/demo_seed.py` (new): seeds a real waterborne-illness
  cluster in a demo village ("Peddapuram") — 8 sessions (abdominal_pain +
  fatigue, `waterborne_illness`'s actual curated `presents_with` set) inside
  the last 6 days, 4 baseline sessions spread across the prior 24 days
  (~1/window), and 3 unrelated (cough) sessions so the dashboard isn't 100%
  one disease. Reuses `memory.persistence.write_pain_points` /
  `complete_session` — the same write path the live app uses — backdating
  only `created_at` on session creation (`CREATE_PERSON_AND_SESSION` already
  takes it as a parameter) so the cluster genuinely falls inside the
  dashboard's rolling window. Run: `python -m app.graph.demo_seed` (after
  `python -m app.graph.seed`).
- `frontend/src/screens/Screen17Village.tsx`: **un-greyed** (`GreyedOverlay`
  removed). Fetches `GET /api/village/{village_id}/summary` on mount
  (defaulting to `Peddapuram`, override via `?village=`), loading state while
  in flight, renders the cluster alert card only when `alerts` contains one,
  stat row (screened/referred/follow-ups due), most-reported-symptoms bars
  scaled to the largest count, and the hamlet breakdown list with
  attention/OK tags — all component-vocabulary primitives
  (`Card`/`Stat`/`StatRow`/`Bar`/`Kv`/`ListShell`/`Item`/`Meta`/`Tag`/
  `FootNote`), dark-theme tokens only, matching the wireframe-fidelity static
  fallback's copy exactly when there's no cluster/no data.
- `backend/tests/test_village.py` (new, 7 tests): the wireframe's "3x over 6
  days" rule fires on the seeded shape (8 cases/6 days vs ~1/window
  baseline), does not fire below `CLUSTER_MIN_COUNT`, does not fire when the
  rate is steady rather than spiking, never fires on an unrelated symptom set,
  never fires with an empty cluster-symptom set (defensive — the disease
  should never resolve to zero symptoms, but the function doesn't assume it),
  and `aggregate_village_summary` counts/referred/followups/hamlets/trend
  correctly including the 90-day quarter-window cutoff.

**Verified:**
- `pytest backend/tests -v` → **7/7 new `test_village.py` passing**; full
  suite 98/99 passing (1 pre-existing failure in `test_golden_path_e2e.py`
  unrelated to this work — a wording assertion, owned by another concurrent
  Phase 7 session; not touched here).
- `cd frontend && npx tsc -b --noEmit && npx vite build` — both clean, zero
  errors.
- Not verified in this sandbox: the dashboard against a *live* Neo4j-backed
  `demo_seed.py` run (no Docker daemon here, same limitation as every prior
  phase). `cluster_alerts_from_rows`/`aggregate_village_summary` were
  exercised against fixture rows shaped exactly like
  `VILLAGE_MATCHING_SESSIONS`'s real output, and the endpoint's Neo4j-path
  wiring (`_build_summary`/`_detect_cluster`) was read-reviewed but not run
  against a live database. Needs a `docker compose up` pass: seed, then
  `python -m app.graph.demo_seed`, then open `#/17` and confirm the cluster
  card shows Peddapuram, ~8 cases, ≥3x baseline.

**Not done / deviations:**
- Only item 2 of Phase 7 (village dashboard, screen 17) is covered by this
  entry. Developer mode (screen 16), i18n, deploy, and demo hardening are
  other Phase 7 items owned by other concurrent sessions.
- "Referred" and "follow-ups due" are proxies over existing data, not a
  dedicated referral/compliance concept — see the Decisions log entry above.
  This mirrors screen 1's Phase 3 "Referrals: —" gap rather than resolving it
  with new invented tracking.
- `population` is a distinct-person-count proxy, not a real census figure —
  documented rather than presented as authoritative.
- The village-dashboard route takes `?village=` as a free-text prefix (same
  convention as `/api/village/autocomplete`); there is no village picker UI
  on screen 17 itself (specs.md §2 doesn't describe one) — an officer reaches
  it via a link with the village name, e.g. from screen 15's person profile
  in a future phase, or the default demo village.

**How to run:**
```
docker compose up
docker compose exec backend python -m app.graph.seed        # KB layer
docker compose exec backend python -m app.graph.demo_seed    # Peddapuram cluster

# then:
# http://localhost:5173/#/17  -> village dashboard for the default demo
#   village (Peddapuram): cluster alert card, screened/referred/follow-ups
#   due, top symptoms, hamlet breakdown
# http://localhost:5173/#/17?village=Kadiri -> any other autocompleted village

pytest backend/tests -v                                 # 98 passed / 1 pre-existing unrelated failure
cd frontend && npx tsc -b --noEmit && npx vite build    # clean
```

### Phase 7 — i18n
- `frontend/src/i18n/te.json` and `frontend/src/i18n/hi.json` filled: all 75 UI
  chrome keys from `en.json` translated (parity confirmed, no missing/extra
  keys). Covers camp dashboard, intake, scan intro, live scan, results,
  consultation, analysing, pain points, symptom edit, next step, findings,
  assessment, saved, profile and village-dashboard trust-note copy.
- Scope: UI chrome only — buttons, labels, screen titles, status strings.
  Clinical terminology (vitals names, "screening signal" language) kept
  consistent with how an ANM/health-officer would see it in practice, using
  common English loanwords where that is more natural (e.g. "మైక్ యాక్టివ్‌గా
  ఉంది" keeps "మైక్" rather than a forced native word). No diagnosis-language
  substitutions from specs.md §8 needed re-doing — those are English-only UI
  copy fixes already applied upstream in `en.json`, and the translations
  follow the same claims (e.g. `assessment.disclaimer` keeps "does not
  diagnose" in both languages).
- Not touched: `backend/app/providers/golden_path.json` (scripted Telugu
  consultation speech — separate, already logged as needing native-speaker
  review) and no screen component currently calls `useTranslation`/`t()`
  against these keys yet (`grep` found no `t("<namespace>.<key>")` usage in
  `frontend/src`), so there is no live UI regression risk from this change —
  wiring screens to `react-i18next` remains a separate Phase 7 item.
- Machine-translated only — no live translator or native speaker available in
  this sandbox. `_note` field in both files reworded from "placeholder, not
  yet started" to "machine translated, needs native-speaker review before
  demo"; Open questions row and Decisions log entry updated to match (see
  above) — the open question stays open, it is not resolved.
- Verified `cd frontend && npx tsc -b --noEmit && npx vite build` — clean,
  86 modules transformed, no errors.

### Phase 7 — deployment and demo hardening (2026-09-21)

**Done (items 4/5/6 of Phase 7 — deployment, demo hardening, docs):**
- **AuraDB**: verified `backend/app/graph/client.py` and `graph/seed.py` need
  **no code change** for AuraDB — `AsyncGraphDatabase.driver()` accepts
  `neo4j+s://` exactly like `bolt://`, and `GraphClient.from_env()` already
  reads whatever `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD` are set to (same
  names as `docker-compose.yml`, kept unchanged). Documented the exact
  instance-creation → env-var → seed steps in `docs/deploy.md` §1.
- **Render**: added `render.yaml` (Blueprint) — Docker web service off
  `backend/Dockerfile`, `/health` healthcheck, secrets (`NEO4J_URI`/`_USER`/
  `_PASSWORD`/`GEMINI_API_KEY`) marked `sync: false` so Render prompts for
  them rather than any value being committed. Manual-dashboard steps
  documented as Option B in `docs/deploy.md` §2 for anyone who'd rather not
  use the blueprint. Confirmed `backend/Dockerfile`/`pyproject.toml` already
  have everything a Render Docker deploy needs — no drift found (every
  third-party import under `backend/app/` cross-checked against
  `pyproject.toml`'s `dependencies`).
- **Vercel**: confirmed `frontend/src/api/client.ts`'s `BASE_URL` already
  reads `import.meta.env.VITE_API_BASE_URL` (Phase 1's own work) — **no code
  change needed**, it was never hardcoded to localhost. Confirmed no
  `vercel.json` rewrite is needed: the app is `HashRouter`-based
  (`#/1`, `#/6`, …), so there's no server-side path for Vercel's static host
  to 404 on. Documented the Vercel project setup (root dir `frontend`, env
  var, HTTPS-for-camera note) in `docs/deploy.md` §3.
- **Render cold-start warm-up**: documented as an explicit pre-demo `curl
  .../health` + one real endpoint call, in both `docs/deploy.md` §4 and
  `docs/demo.md`'s pre-demo checklist — a manual step, no monitoring service
  added (none in the stack table).
- **`docker compose` verification**: `docker compose config` (a Docker CLI
  *is* available in this sandbox, unlike every earlier phase's note) resolves
  cleanly; found and removed the obsolete top-level `version: "3.9"` key from
  `docker-compose.yml` (Compose itself flagged it as ignored — cosmetic, no
  behaviour change). Cross-checked `backend/Dockerfile` paths and
  `pyproject.toml` dependencies against every import under `backend/app/` —
  no drift. A full `docker compose up` (actually booting containers) was
  **not** run — the daemon behind the CLI isn't reachable here even though
  the CLI/config validation works; needs one real run on the demo laptop.
- **Fixture mode**: added `SANJEEVANI_FIXTURE_MODE` (`backend/app/providers/llm.py::fixture_mode()`,
  checked at the top of `GeminiLLM.complete()` and `GeminiSTT.transcribe()`).
  When set, both raise `Unavailable` immediately without attempting a live
  Gemini call, so every existing caller's fallback-to-golden-path-cache path
  (`api/consult.py`, `agents/attribution.py`) fires exactly as it already does
  on a real failure — no new fallback branch needed anywhere else. Small,
  additive, respects the Protocol-based provider seam untouched.
- **Graceful degradation audit**: read through `frontend/src/capture/audio.ts`
  (mic denied — already sets a user-facing `error` state, screen 6 already
  renders it with retry guidance), `frontend/src/api/client.ts` (the single
  `request()`/`transcribe()` helpers throw on a non-2xx, and **every screen
  that calls them already wraps the call in `.catch(...)`** — checked
  `Screen1Camp`, `Screen10NextStep`, `Screen13Assessment`, `Screen15Profile`,
  and, as a read-only check without editing them (screens 16/17 are owned by
  concurrent sessions this phase), `Screen16Graph`/`Screen17Village` — all
  already degrade to a golden-path/empty fallback state rather than a blank
  screen), and the provider fallback path (Gemini rate-limited —
  `LLMUnavailable`/`STTUnavailable` are caught everywhere they're raised).
  **No gap was found that needed a fix** — every degradation path CLAUDE.md
  and the task asked to check was already handled by prior phases' own
  graceful-fallback pattern. Nothing changed in any screen component.
- **Golden-path e2e test**: `backend/tests/test_golden_path_e2e.py` (new) —
  drives the real app via FastAPI `TestClient` with `SANJEEVANI_FIXTURE_MODE`
  forced on and no live Neo4j, through the actual HTTP routes: session start
  (+ a consent-rejection check) → `/api/vitals/process` over a synthetic
  1.2Hz-pulse ROI trace (same technique as `test_rppg.py`) → `/api/consult/
  transcribe`+`/extract`+`/painpoints` (fixture mode forces
  `source: "golden_path_cache"`) → `/api/secondlook/suggest`+`/submit` (chest-
  rise proposed first, synthetic 18-brpm shoulder trace as in
  `test_secondlook.py`) → `/api/synthesis/run`+`/result` (asserts TB ranks
  first and the NTEP `screening_rule` string is cited verbatim in the
  reasoning chain) → `/api/report/generate`+download (asserts a real `%PDF`
  byte stream over 1KB comes back). Also a standalone test asserting fixture
  mode itself makes both providers raise immediately with no key required.
- `.env.example` (new, repo root) — every env var read anywhere in the
  backend/frontend (`NEO4J_URI`/`_USER`/`_PASSWORD`, `GEMINI_API_KEY`/
  `GEMINI_MODEL`/`GEMINI_STT_MODEL`, `SANJEEVANI_FIXTURE_MODE`,
  `VITE_API_BASE_URL`), documented, no real secret committed.
- `docs/demo.md` (new) — presentation order (story first, golden path
  1→17 second), pre-demo checklist (warm backend, test the actual laptop/
  browser, camera/mic permission granted ahead of time, lighting for the
  rPPG scan, fixture mode as the network-loss contingency), and the
  `docker compose up` local fallback as the safety net.
- Verified: `python -m pytest backend/tests -v` → **99 passed** (the
  previously-noted 1 pre-existing failure in this same new file — a
  too-strict substring assertion that flagged the disclaimer's own honest use
  of the word "diagnosis" in "screening signal, not a diagnosis" — was this
  session's own test, now fixed to check for the diagnostic-verb phrase
  `"diagnosed with"` instead of banning the word "diagnosis" outright). No
  other suite regressed.

**Not done / deviations:**
- A full `docker compose up` (real containers, not just `config`) was not run
  — no reachable Docker daemon behind the CLI in this sandbox. Needs one pass
  on the actual demo laptop per `docs/deploy.md` §5.
- AuraDB/Render/Vercel were configured and documented but **not actually
  provisioned** — no live AuraDB instance, Render service, or Vercel project
  was created from this sandbox (no external account access). Everything in
  `docs/deploy.md` is a verified-correct recipe against the existing code,
  not a confirmed-working deployment; needs a human to actually click through
  it once before the demo.
- Did not touch any frontend screen, i18n file, or `App.tsx`/router — out of
  scope per the task, and the degradation audit found nothing there needing a
  fix regardless.
- `render.yaml` targets a single web service (the backend). It does not
  attempt to also deploy the frontend or a Neo4j instance from Render — the
  frontend goes to Vercel and the graph to AuraDB per the task's own split.

**How to run:**
```
# Local fallback, unchanged:
docker compose up
docker compose exec backend python -m app.graph.seed

# Fixture-mode demo (no network at all):
SANJEEVANI_FIXTURE_MODE=true docker compose up
# or, for a single backend process: export SANJEEVANI_FIXTURE_MODE=true first

# Offline golden-path e2e test (no network, no live Neo4j):
cd backend && pip install -e ".[dev]"
python -m pytest tests/test_golden_path_e2e.py -v    # 2 passed
python -m pytest tests -v                             # 99 passed

# Deploy: see docs/deploy.md (AuraDB -> Render -> Vercel) and docs/demo.md
# (pre-demo checklist, presentation order, local fallback).
```
