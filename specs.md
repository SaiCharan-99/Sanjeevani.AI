# Specifications — Sanjeevani

Functional spec for every screen, endpoint and rule. Read alongside `architecture.md`.

---

## 1. Golden path — the demo story

**Ramesh Kumar, 52, male, farmer, Kadiri (Andhra Pradesh).**
Health camp run by **Dr. Meera Rao**, Medical Health Officer. One phone.
Session id format `SAN-<yyyy>-<nnnn>`, e.g. `SAN-2026-0982`.

> The wireframe is inconsistent here (age 54, surname Gowda on one screen, three id
> formats, HR 80). **These values are canonical**; the wireframe strings are corrected
> when the screens are built. HR 96 / RR 22 / SpO₂ 94 are chosen because they feed the
> TB consideration *and* the anemia risk model.

| Stage | What the officer does | What the system does | What the judge sees |
|---|---|---|---|
| Intake | Types name, age 52, male, village | Creates `Person` + `Session` | Clean form, consent checkbox |
| Vitals | Points camera at Ramesh's face, 30s | rPPG → HR 96, RR 22, SpO₂ 94%, quality good | Live scan ring, then results card |
| Consult | Taps record, they talk in Telugu | STT → attribution → pain points | Transcript building live, tagged by speaker |
| Second look | Accepts the agent's suggestion | Pose chest-rise + lip colour | **Agent proposes a capture — the wow beat** |
| Synthesis | Saves, calls next person | Background traversal + risk models | Progress indicator, then notification |
| Report | Recalls Ramesh, opens report | PDF generated | Government-grade PDF |

### The consultation script (Telugu, subtitled)

> **Officer:** What is troubling you?
> **Ramesh:** For two or three weeks now I have had a cough. It does not go.
> **Officer:** Any difficulty breathing?
> **Ramesh:** When I walk to the field my chest feels tight. I get tired very fast.
> **Officer:** Fever?
> **Ramesh:** Sometimes at night. And I have lost weight.

### Extracted pain points

```json
[
  {"symptom": "cough", "canonical": "cough", "duration_days": 21, "confidence": 0.95,
   "verbatim": "for two or three weeks now I have had a cough"},
  {"symptom": "exertional chest tightness", "canonical": "chest_tightness", "confidence": 0.90,
   "verbatim": "when I walk to the field my chest feels tight"},
  {"symptom": "fatigue", "canonical": "fatigue", "confidence": 0.88,
   "verbatim": "I get tired very fast"},
  {"symptom": "night sweats", "canonical": "night_sweats", "confidence": 0.75,
   "verbatim": "sometimes at night"},
  {"symptom": "weight loss", "canonical": "weight_loss", "confidence": 0.85,
   "verbatim": "I have lost weight"}
]
```

`canonical` is a `:KB:Symptom` slug resolved through `symptom_aliases.csv`. Every one
of these five must resolve, or the golden path is broken — the seed test asserts it.

### Why TB is the right golden path

- **Highest-impact rural Indian disease story** — a judge immediately understands
  the stakes.
- **Genuinely screened by what we can capture.** India's national TB elimination
  programme uses a cough lasting two weeks or more as a presumptive-TB screening
  trigger, combined with fever, weight loss and night sweats. Our pipeline captures
  every one of those.
- **The recommendation is real and correct**: sputum smear / NAAT and chest X-ray at
  the nearest PHC. We are not inventing clinical logic — we are routing to it.
- **It makes the graph look clinical rather than toy.**

### Synthesis output

```
Primary consideration: Pulmonary tuberculosis (screening positive)
  Reasoning chain:
    - Cough ≥ 2 weeks  →  national presumptive-TB screening trigger
    - Weight loss + night sweats  →  classic constitutional TB symptoms
    - RR 22 (elevated) + SpO₂ 94% (low-normal)  →  respiratory involvement
  Recommendation: sputum smear/NAAT + chest X-ray at nearest PHC
  Priority: HIGH — refer within 48 hours

Secondary: COPD
  Reasoning: age 52 + rural biomass-fuel exposure + exertional breathlessness
  Recommendation: spirometry if TB screening returns negative

Background risk model: anemia likelihood 0.62
  Inputs: pallor score 0.7, HR 96, reported fatigue
  Model F1 0.81 — screening signal only
```

### Secondary demo path — the hand injury

Shorter, proves the engine is not a one-trick script.
Person reports hand pain after a fall. Agent proposes **swelling asymmetry +
guided range of motion**. Pose measures joint angle sweep; face mesh not involved.
Output: suspected soft-tissue injury vs possible fracture, recommend X-ray.

Run this only if time allows and judge one is engaged.

---

## 2. Screens

The wireframe `frontend/ui-reference/sanjeevani-flow.html` defines **19 states**.
Wireframe labels are the canonical ids; the `S` numbers are aliases kept so older
notes still make sense. Every state exists from Phase 1 (greyed); the *Phase* column
says when it goes live.

| Wireframe | Alias | Screen | Phase |
|---|---|---|---|
| 1 | S1 | Camp dashboard | 3 |
| 2 | S2 | Intake + consent | 3 |
| 3 | S3 | Scan intro | 2 |
| 4 | S4 | Live scan | 2 |
| 4b | S4b | Live scan — low light / motion | 2 |
| 5 | S5 | Vitals results | 2 |
| 5b | S5b | Vitals results — low signal, retake | 2 |
| 6 | S6 | Voice consultation | 4 |
| 7 | S7a | Analysing (processing state) | 4 |
| 8 | S7 | What we heard — pain points review | 4 |
| 9 | S7b | Edit symptoms — manual add | 4 |
| 10 | S8 | Next step — agent suggestion | 5 |
| 11 | S9 | Guided motion capture | 5 |
| 12 | S10 | Findings | 5 |
| 13 | S12 | Assessment | 6 |
| 14 | S11 | Session saved | 3 |
| 15 | S13 | Person profile | 3 |
| 16 | S14 | Knowledge graph — explainability, with developer-mode toggle | 6 (explain) / 7 (dev toggle) |
| 17 | S15 | Village dashboard | 7 |

### 1 — Camp dashboard
Camp tag (village · date), greeting with officer name, three stat tiles (seen today,
reports pending, referrals), **New person** CTA, "Needs your attention" list (report
ready), "Today's sessions" list with one-line outcome per person. List subtitles use
tiered language: `BP trend ↗`, never a mmHg pair; `Anemia screening: high likelihood`,
never "severe anemia suspected".

### 2 — Intake + consent
Full name, age (validated integer 0–120; **never** render an unvalidated age
anywhere), gender segmented control (Male / Female / Other), village (autocomplete
from prior sessions), conversation language segmented control
(English / తెలుగు / हिन्दी), consent checkbox with the exact wireframe text.
**Consent is mandatory and blocks progression.** No camera before consent.

### 3 — Scan intro
"Camera ready · 720p" status tag reflecting real permission/resolution state. Four
guideline rows (sit still, face the light, remove glasses, 30 seconds). Trust note:
"Processed on device — video is never stored or uploaded" (this one is true).
Proceed CTA disabled until camera permission is granted.

### 4 — Live scan
Full-bleed camera, face-oval guide, circular countdown ring with seconds remaining,
status pill ("Pulse locked"), **live signal-quality bar** with percentage and three
diagnostics (lighting, motion, rPPG lock). Cancel.

### 4b — Live scan, low light / motion
Same layout; ring pauses, status becomes "Scan paused", quality band goes to caution,
instruction chip names the fix ("Move into better light", "Shadow on left cheek",
"Hold still"). Resumes automatically when live quality recovers. Not a separate route —
a state of screen 4 driven by the client quality feedback.

### 5 — Vitals results
Tabbed sections (Key body vitals / Heart health / Stress). Per-vital cards with value,
unit, range bar and **confidence tier badge** (rule 4): heart rate, respiration rate,
SpO₂ (badge "Approximate"), blood pressure (arrow + "Trending elevated / stable" +
"Trend only — not a measurement"; **no number**), anemia indicator ("Screening
signal", likelihood band, CBC suggested). Quality note with the overall percentage.
**No health-score ring** (rule 9); the top of the screen shows the overall quality
badge instead. Actions: "Download report" (Phase 6), "Start consultation".

### 5b — Vitals results, low signal
Shown when `overall_quality < 0.4`. Headline with the percentage, cause line
(movement, lighting), field lighting tip card, per-vital cards rendered **without
values** ("Inconclusive") and the reason. Primary and only forward action:
**Retake scan**. The wireframe's "Continue with degraded vitals" is not built.
Between 0.4 and 0.7 screen 5 is shown with warning bands, not this screen.

### 6 — Voice consultation
Person header (initials, name, age/gender, session id, camp), language tag, mic
status, elapsed timer, waveform. Live transcript as turns with speaker chip
(Officer name / Person name), timestamp, original-language line and English line.
Inline marker chips for extracted terms as they appear. "Stop and analyse".
No ICD codes.

### 7 — Analysing
Processing state after stop: audio saved confirmation, four-step checklist with
live status — Transcribing → Identifying speakers → Extracting symptoms →
Structuring summary. ETA line. Cancel. Trust note limited to what is true
("Preliminary observations are for screening review only").

### 8 — What we heard (pain points review)
"Officer control" tag. Reported symptoms as cards: name, confidence label and
percentage, duration/context chip, verbatim quote in English and in the session
language, remove (✕). Confidence dot colour by band. "Add a symptom" → screen 9.
Footer: "Corrections are tracked in the audit log". CTA: continue.
**Human-in-the-loop is a feature, not a fallback.**

### 9 — Edit symptoms
Manual add form: symptom picker (search over `GET /api/kb/symptoms`, free text
allowed and stored as `unmapped_text` if no slug matches), clinical note. Current list
with remove. Entries are attributed to the officer in the audit log. Save and
continue.

### 10 — Next step (agent suggestion — the wow beat)
"Adaptive protocol" tag. Priority card: feature title, **rationale quoting the
triggering symptoms**, three chips (duration, camera, position). "Also suggested"
list of optional captures with one-line reason and duration. Warning note on what
skipping costs. CTAs: "Start capture" / "Skip to findings". If `facial_asymmetry`
is triggered it is the priority card and is labelled as a red flag.

### 11 — Guided motion capture
Camera with pose skeleton overlay, positioning guide, countdown, live metric readout
(cycles, fps, lock status). Cancel.

### 12 — Findings
Grouped by capture ("From the breathing capture · 20 s · good", "From the face
scan · 30 s · good"). Each finding: value, unit, method line, interpretation line,
confidence. Limitations note per feature (specs §5). Disclaimer note. CTA "See
assessment" → queues synthesis (screen 14 shows the saved state while it runs).

### 13 — Assessment
Referral banner (priority + action + rationale citing the screening rule).
Ranked considerations: name, evidence summary, likelihood band (High / Moderate /
Low), expandable to the reasoning chain. Background risk checks list (✓ / !) —
model outputs with metric and "screening signal" label, BP trend confirmation,
village cluster context. Disclaimer: "Sanjeevani does not diagnose. Confirm with
laboratory testing before starting any treatment." CTAs: "Save session & refer",
"Edit assessment". `review: pending` badge on any curated-but-unreviewed edge.

### 14 — Session saved
Confirmation with person, session id, date. Artefact rows (structured summary,
audio & transcript, scan captures — "signals only", PHC referral slip) with status.
Trust note: what is stored and that no video exists. CTAs: "View person profile",
"Back to camp dashboard". Copy must not claim offline sync (rule 10).

### 15 — Person profile
Header (initials, name, age/gender, village, session id, active-referral tag).
Stat tiles (visits, open flags, last seen). Open items list (referral, BP cuff
confirmation). Timeline of encounters. Vital trend chart across visits: respiration
rate and **BP trend index** (categorical elevated/stable per visit — not a systolic
axis). "Open knowledge graph".

### 16 — Knowledge graph
Default: **explainability view** — a small force graph of the top consideration
with its contributing evidence nodes, and the ranked edge list (evidence · source ·
confidence · role: strongest / supporting / context). Note: "Remove any symptom on
the review screen and the graph recalculates." **Developer-mode toggle** (Phase 7)
expands to the real Neo4j traversal for the session (neovis.js or D3 over
`GET /api/synthesis/explain?full=true`), highlighting the path used. This is how the
graph is proven real during the pitch.

### 17 — Village dashboard
Village header (population, screened this quarter), cluster alert card (signal,
ward, multiple of baseline, window, suggested source check), stat tiles (screened,
referred, follow-ups due), most-reported symptoms bar list, screened/referred trend
chart, hamlet breakdown with status tags. Copy: "Aggregated locally · individual
records are not shown" (not "never leave the device").

## 3. API contracts

### `POST /api/session/start`
```json
{"person": {"name":"Ramesh","age":52,"gender":"male","village":"Kadiri"},
 "language":"te", "consent": true}
→ {"session_id":"s_...", "person_id":"p_..."}
```

### `POST /api/vitals/process`
`overall_quality < 0.4` ⇒ `retake_recommended: true` and the client shows screen 5b
with no forward path except retake. No composite score field exists in this response.

```json
{"session_id":"s_...",
 "fps": 30,
 "duration_s": 30.1,
 "traces": {"forehead":{"r":[...],"g":[...],"b":[...]},
            "cheek_l":{...}, "cheek_r":{...}},
 "motion_score": 0.12,
 "timestamps": [...]}
```
```json
→ {"heart_rate":{"value":96,"unit":"bpm","quality":0.86,"tier":"reliable"},
   "respiration_rate":{"value":22,"unit":"brpm","quality":0.71,"tier":"reliable"},
   "spo2":{"value":94,"unit":"%","quality":0.63,"tier":"approximate"},
   "bp_trend":{"direction":"elevated","quality":0.41,"tier":"trend_only"},
   "passive_findings":{"pallor_score":0.7,"facial_tension":0.4,"blink_rate":14},
   "overall_quality":0.74,
   "retake_recommended": false}
```

### `POST /api/consult/transcribe`
Multipart audio + `session_id` + `language`.
```json
→ {"turns":[{"speaker":"officer","text":"...","start_s":0.0},
            {"speaker":"person","text":"...","start_s":3.2}],
   "language_detected":"te"}
```

### `POST /api/consult/extract`
```json
→ {"pain_points":[{"symptom":"cough","canonical":"cough","duration_days":21,
                   "confidence":0.95,"verbatim":"...","verbatim_original":"..."},
                  {"symptom":"burning in my feet","canonical":null,
                   "unmapped_text":"burning in my feet","confidence":0.7,"verbatim":"..."}],
   "red_flags":[]}
```
`canonical` is a graph slug or `null`. Unmapped terms are shown to the officer for
manual mapping on screen 9. The extractor never creates symptoms.

### `GET /api/secondlook/suggest?session_id=...`
```json
→ {"suggestions":[{"feature":"chest_rise_respiration","priority":"high",
     "rationale":"Cough ≥3 weeks with exertional chest tightness.",
     "instruction":"Ask the person to stand sideways, 1.5m from camera, breathe normally for 20 seconds.",
     "triggered_by":["cough","exertional chest tightness"]}]}
```

### `POST /api/secondlook/submit`
Pose/mesh landmark series + feature id → findings with confidence.

### `POST /api/synthesis/run`
Queues background job.
```json
→ {"job_id":"j_...","status":"queued"}
```

### `GET /api/synthesis/result?session_id=...`
```json
→ {"considerations":[{"disease":"Pulmonary tuberculosis","score":0.87,"rank":1,
     "reasoning_chain":[
        {"evidence":"cough 21 days","edge":"PRESENTS_WITH","weight":0.9,
         "note":"national presumptive-TB screening trigger"},
        {"evidence":"weight loss","edge":"PRESENTS_WITH","weight":0.8}],
     "recommended_tests":["Sputum smear / NAAT","Chest X-ray"],
     "priority":"high"}],
   "risk_models":[{"name":"anemia_risk","score":0.62,"f1":0.81,
                   "inputs":["pallor_score","heart_rate","fatigue"]}]}
```

### `POST /api/report/generate`
→ PDF bytes + stored artifact reference.

### `GET /api/synthesis/explain?session_id=...&full=false`
Explainability for screen 16.
```json
→ {"consideration":"tuberculosis","score":0.87,
   "edges":[
     {"evidence":"cough (21 days)","source":"reported","confidence":0.98,
      "role":"strongest","edge":"PRESENTS_WITH","weight":1.0,
      "screening_rule":"NTEP presumptive TB: cough ≥ 2 weeks"},
     {"evidence":"weight_loss","source":"inferred","confidence":0.74,"role":"supporting"},
     {"evidence":"night_sweats","source":"reported","confidence":0.68,"role":"supporting"},
     {"evidence":"respiration_rate 23","source":"capture","confidence":0.8,"role":"supporting"},
     {"evidence":"Kadiri TB cluster (2 confirmed)","source":"village","role":"context"}]}
```
With `full=true` returns the node/edge list of the actual traversal for the
developer-mode view.

### `GET /api/person/{person_id}`
Screen 15. Person summary (architecture §6 tier 3) plus `sessions[]` timeline
(date, kind, one-line outcome) and `vital_series` per vital across visits.
`bp_trend` series is categorical (`elevated | stable | low`), never numeric.

### `GET /api/village/{village_id}/summary`
Screen 17. `{population, screened_quarter, referred, followups_due,
top_symptoms:[{slug,count}], trend:[{month,screened,referred}],
hamlets:[{name,screened,referred,status}], alerts:[{kind:"cluster",
disease_group:"waterborne", count, baseline_multiple, window_days, ward, suggestion}]}`.
Aggregates only; no person identifiers.

### `GET /api/kb/symptoms`
`[{slug, name, severity, aliases:[..]}]` — powers the picker on screen 9 and the seed
test. `GET /api/kb/diseases/{slug}` returns the disease with its edges for developer
mode.

### `GET /api/session/pending`
Dashboard badges: sessions whose synthesis job is queued/running/done-but-unopened.

---

## 4. rPPG specification

**Capture:** 30 seconds, 30fps target, 720p minimum.
**ROIs:** forehead, left cheek, right cheek (MediaPipe landmark groups).
**Client output:** mean R/G/B per ROI per frame + per-frame motion magnitude.

**Server pipeline:**
1. Resample to uniform time base (browser frame timing is not uniform).
2. Reject frames where motion score exceeds threshold; if >30% rejected, fail fast
   with `retake_recommended: true`.
3. Detrend each channel (smoothness-priors or moving-average).
4. Normalise per channel.
5. POS projection (primary) and CHROM (cross-check). Disagreement beyond tolerance
   lowers the quality score.
6. Bandpass 0.7–4.0 Hz, 4th-order Butterworth, zero-phase.
7. Welch PSD. Dominant peak → HR.
8. SNR = peak power / total in-band power → quality score.
9. Respiration: bandpass 0.1–0.5 Hz on the RSA envelope.
10. SpO₂: ratio-of-ratios across red and blue, calibrated against a fixed constant.
    **Always tier `approximate`.**
11. BP: feature-based trend classification only. **Never emit an mmHg value.**

**Quality thresholds:** `>0.7` show value; `0.4–0.7` show with warning;
`<0.4` force retake (screen 5b, retake is the only forward action).

The pipeline produces per-vital values and qualities only. It does **not** produce a
composite health score (rule 9).

**Never implement haemoglobin estimation.** Replace it with the pallor-based
anemia risk flag from the risk models.

---

## 5. Second-look feature specs

### `chest_rise_respiration`
Pose landmarks 11/12 (shoulders), 23/24 (hips). Measure vertical oscillation of the
shoulder midpoint over 20s. Output: rate (brpm), amplitude (normalised), regularity.
Cross-check against rPPG-derived RR; large disagreement lowers both confidence scores.

### `swelling_asymmetry`
Face mesh for facial regions, pose for limbs. Compare left/right landmark distances
against the body's own midline. Output: asymmetry ratio per region, flagged above 15%.
**Limitation to state in the report:** monocular vision cannot measure true volume —
this detects asymmetry, not absolute swelling.

### `guided_range_of_motion`
Instruct a specific joint movement (raise arm to shoulder, rotate wrist).
Track joint angle across the sweep. Output: max angle achieved vs expected range,
smoothness, and whether the person compensated with another joint.

### `pallor_check`
Face mesh conjunctiva and cheek regions. Normalise against ambient white balance using
the sclera as reference. Output: pallor score 0–1.
**Heavily confounded by skin tone and lighting — must be labelled as such.**

### `posture_assessment`
Pose from a side view. Forward head angle (ear-to-shoulder line vs vertical),
shoulder height difference, thoracic curve approximation.
Output: scored deviations plus ergonomic recommendation.

### `facial_asymmetry`
Face mesh, comparing landmark displacement across the facial midline during a
requested smile/raise-eyebrows action.
**Highest priority rule. If triggered, interrupt the flow and surface a
stroke-screening red flag immediately.**

### `gait_balance`
Pose over a short walk toward the camera. Step symmetry, stance width, sway.

---

## 6. Report specification

The PDF is a headline deliverable, not an afterthought. Swaroop's brief: stamp,
page headers, proper structure, authentic enough to enter government systems.

**Structure:**
1. Header — programme name, camp ID, date, officer name and ID
2. Person block — name, age, gender, village, session ID
3. Vitals table — value, normal range, status, **confidence tier**; BP row shows
   trend only; no composite score
4. Consultation summary — structured, plus reported symptoms with duration
5. Second-look findings — what was captured, what it showed, limitations
6. Assessment — ranked considerations with reasoning chains
7. Risk model outputs — with metrics and screening-only labels
8. Recommendations — tests, referral priority, precautions
9. **Disclaimer block** — screening aid, not diagnosis; officer's clinical judgement
   governs
10. Footer — page numbers, generation timestamp, verification ID, stamp

Generated with ReportLab. Trilingual: the person-facing summary section renders in
the session language; the clinical body stays in English.

---

## 7. Knowledge base

What the system is allowed to surface as a consideration, and where it comes from.
Full graph model in `architecture.md` §5.

- **Consideration set** = 41 Kaggle diseases + curated additions (`copd`, `anemia`,
  `chronic_kidney_disease`). Nothing else can appear on screen 13.
- **Symptom vocabulary** = 131 Kaggle slugs + curated additions. The extractor's
  `canonical` field must be one of these or `null`.
- **Edge weights**: Kaggle edges `weight = frequency × severity/7`; curated edges set
  `weight` explicitly and override. Scoring in synthesis uses weight × evidence
  confidence, summed per disease, with symptom-coverage and village-prior terms.
- **Screening rules** are properties on curated `PRESENTS_WITH` edges
  (`screening_rule`, `min_duration_days`). The reasoning chain cites them verbatim.
  The TB rule (cough ≥ 14 days) is the only one that must exist for the demo.
- **Recommendations** (`DiagnosticTest`, `Precaution`) are read from the graph and
  displayed verbatim. The LLM may not rewrite or add to them.
- **Village priors** come from `(:PHI:Village)-[:HAS_CLUSTER]->(:KB:Disease)` and
  appear in chains as `role: "context"`, never as `strongest`.
- **Review status**: any curated node/edge with `review: pending` is badged
  "Needs clinical review" on screens 13 and 16 and in the developer view. Only the TB
  entry may ship `review: approved` without a clinician, because it restates the
  published national criteria already in §1.
- **Seed validation test** (Phase 1): every disease has ≥1 symptom, a description and
  ≥1 precaution; every symptom has a severity; the five golden-path slugs resolve;
  the TB screening edge exists; no `:KB` node is created at runtime.

---

## 8. Wireframe copy rules

Strings in the wireframe that conflict with the absolute rules, and what to render
instead. Apply these when building the screen; do not copy the wireframe verbatim.

| Screen | Wireframe string | Render instead | Rule |
|---|---|---|---|
| 1 | `Vitals normal · BP 124/82` | `Vitals normal · BP trend stable` | 2 |
| 1 | `Severe anemia suspected` | `Anemia screening: high likelihood` | 1 |
| 5 | `80 /100 Health score · Great` | overall quality badge (`Signal quality 74%`) | 9 |
| 5, 12 | `Camp triage` / `triage` (anywhere) | `screening` | 1 |
| 5b | `Hemoglobin proxy` | `Pallor signal` | 3 |
| 5b | `Continue with degraded vitals` / `Continue to triage chart anyway` | not rendered | 4 |
| 6 | `⚠ Exertional dyspnea (R06.0)` | `Exertional breathlessness` (no ICD code) | 1 |
| 6 | `Dual-mic active` | `Mic active` | 10 |
| 7 | `SOAP format & triage tier` | `Structured summary & screening priority` | 1 |
| 7 | `On-device cryptographic guard · Processing stays encrypted on device` | `Audio is sent for transcription; video never leaves the device` | 10 |
| 7 | `Generating clinical report…` | `Preparing the review…` | 1 |
| 1, 2 | `🔒 Encrypted and stored locally in offline mode` | `🔒 Video never leaves the device` | 10 |
| 14 | `Queued for sync · will upload when the camp regains connectivity · Nothing leaves the device` | `Saved to this camp's record` | 10 |
| 15 | chart legend `Systolic trend` | `BP trend` (categorical) | 2 |
| 17 | `no individual records leave the device` | `individual records are not shown` | 10 |
| 6, 7, 15 | `54y`, `#AP-8842`, `#ASHA-9042`, `Ramesh Gowda` | `52y`, `SAN-2026-0982`, `Ramesh Kumar` | §1 |
| 5, 12 | HR `80` | HR `96` | §1 |

Vocabulary everywhere: *person* (not patient), *consideration* (not diagnosis),
*screening* (not triage), *finding* for observed evidence, *symptom* for graph terms.

---

## 9. Non-goals

Explicitly out of scope. Say so if asked, rather than half-building:

- Patient-facing self-diagnosis (Swaroop: *"that will be a different application"*)
- Haemoglobin estimation from camera
- Absolute blood pressure values
- Prescribing medication doses
- Anything replacing a clinician's judgement
- True offline operation in this build (architecturally prepared, not wired) — and
  therefore no UI copy claiming it
- A composite health score
- ICD coding of symptoms or considerations
