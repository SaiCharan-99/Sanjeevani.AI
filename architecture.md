# Architecture — Sanjeevani

> Phone-based diagnostic assistant for rural health camps in India.
> Single monorepo. Python (FastAPI) backend, React frontend, Neo4j knowledge graph.

---

## 1. The problem and the premise

Rural India has a shortage of doctors *and* a shortage of connectivity. Health camps
are organised, but the infrastructure does not match the population-to-doctor ratio.

The premise: **bring complete diagnostics onto a phone**, hand it to a medical health
officer, and let them run a camp in a village using nothing but that phone.

Every sensor the phone already has gets used. The technology already exists but is
scattered — rPPG research, MediaPipe, speech-to-text, medical knowledge graphs,
disease risk models. This project brings them together into one guided workflow.

**This is an officer-facing application.** It is not a patient self-diagnosis app.
That is a different product and mixing the two confuses the story.

**Terminology:** a person arriving at the camp is a *person*, not a patient. They only
become a patient once something is found. The UI must respect this.

---

## 2. Decisions already made

| Decision | Choice | Reasoning |
|---|---|---|
| rPPG | Real signal processing | Noisy but authentic; quality gating handles the noise |
| Graph DB | Neo4j | Real Cypher, and the developer-mode graph visual needs it |
| Offline | Gemini API always | Offline is a *pitch* claim, backed by a clean provider seam |
| Deployment | Live URL (Aura + Render + Vercel) | Judge can open it; local docker still built as fallback |
| Capture | Live webcam | Higher risk, materially more impressive |
| Demo | Scripted golden path, generic engine | Reliable demo, honest architecture |
| Languages | English, Telugu, Hindi | Gemini handles all three natively |
| Graph layout | One database, two labelled subgraphs | Traversal from person to precaution in one query |

---

## 3. System overview

```
┌──────────────────────── BROWSER (React, Vercel) ────────────────────────┐
│                                                                          │
│  Camera capture ──► MediaPipe WASM ──┬──► Face Mesh (468 landmarks)      │
│                                      └──► Pose (33 landmarks)            │
│                                                                          │
│  rPPG client stage:                                                      │
│    per frame: extract forehead + cheek ROI ──► mean R, G, B              │
│    accumulate ~900 triplets over 30s + motion score                      │
│    POST ~40KB JSON (NOT video)                                           │
│                                                                          │
│  Mic capture ──► WebM/Opus blob ──► POST                                 │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │ HTTPS / WebSocket
┌──────────────────────────────▼──────── BACKEND (FastAPI, Render) ────────┐
│                                                                          │
│  /api/vitals/process   signal pipeline (NumPy + SciPy)                   │
│  /api/session/*        session lifecycle, memory tiers                   │
│  /api/consult/*        Gemini STT, speaker attribution, pain points      │
│  /api/secondlook/*     trigger rules, findings ingest                    │
│  /api/synthesis/*      graph traversal, reasoning chains, risk models    │
│  /api/report/*         PDF generation                                    │
│                                                                          │
│  Background worker: risk models run while next person is seen            │
└───────────┬────────────────────────────────────┬─────────────────────────┘
            │                                    │
   ┌────────▼────────┐                  ┌────────▼────────┐
   │  Neo4j AuraDB   │                  │  Gemini API     │
   │  KB + PHI graph │                  │  STT + reasoning│
   └─────────────────┘                  └─────────────────┘
```

---

## 4. Why rPPG is split across client and server

This is the single most important architectural decision in the project.

**Do not stream video to the backend.** Render's free tier cold-starts in ~50 seconds
and sleeps after 15 minutes idle. Pushing 30 seconds of video over venue wifi will
kill the demo.

**Client does extraction. Server does signal processing.**

The browser already runs MediaPipe Face Mesh (it is needed anyway for the swelling and
pallor checks). It locks onto the forehead and both cheeks, and for each frame computes
the mean red, green and blue value inside those regions. Thirty seconds at 30fps is
about 900 RGB triplets — roughly 40KB of JSON.

The server receives that array and does the real work:

```
raw RGB traces
  → per-channel detrend (remove slow lighting drift)
  → normalise
  → POS or CHROM projection (isolate the pulsatile component)
  → bandpass filter 0.7–4.0 Hz (42–240 bpm plausible range)
  → Welch PSD / FFT
  → dominant peak → heart rate
  → SNR around that peak → quality score
```

Respiration comes from two independent sources that cross-check each other:
respiratory sinus arrhythmia (the low-frequency modulation of the rPPG waveform,
0.1–0.5 Hz) and, during the second-look capture, chest-rise amplitude from pose
landmarks.

The signal processing is genuinely real. Only the transport is optimised.

### Vital confidence tiers — enforced in the UI

| Vital | Tier | How it is shown |
|---|---|---|
| Heart rate | Reliable | Plain number |
| Respiration rate | Reliable | Plain number |
| SpO₂ | Approximate | Number + "approximate" badge |
| Blood pressure | Trend only | Direction arrow, never an absolute mmHg |
| Haemoglobin | Not implemented | Replaced by a pallor-based anemia *risk flag* |

Consumer RGB cameras have no infrared channel, so camera SpO₂ is a ratio-of-ratios
approximation, not a pulse oximeter. Published rPPG blood-pressure work reports mean
absolute errors around 8–9 mmHg under favourable conditions — well outside clinical
tolerance — though change-detection is reasonable. Haemoglobin estimation has known
agreement problems across skin tones.

**Every vital ships with a quality score.** Below threshold, the UI says "retake"
rather than printing a number. A judge who is a clinician will respect honest gating
far more than confident garbage.

### The two non-happy states are first-class screens

The wireframe makes both explicit and they must be built, not bolted on:

- **During capture — low light / motion (wireframe 4b).** Ring pauses, quality bar
  drops to the caution band, an instruction chip tells the officer what to fix
  ("move into better light", "shadow on left cheek", "hold still"). Capture resumes
  automatically when live quality recovers; the 30 s clock counts good frames only.
- **After capture — low signal (wireframe 5b).** `overall_quality < 0.4` ⇒
  `retake_recommended: true`. The screen shows *why* (movement, lighting), a field
  lighting tip, and **retake as the only primary action**. The wireframe's "continue
  with degraded vitals" button is not built — rule 4 forbids rendering an ungated
  vital. Between 0.4 and 0.7 values render inside a warning band.

There is no composite health score on the results screen (rule 9).

---

## 5. Graph model

One Neo4j database, two labelled subgraphs, joined at `Symptom`.

### Knowledge subgraph — label prefix `:KB`

Static, curated, versioned, rebuilt from seed files. Never written to at runtime.
It has **two layers with different provenance**, and every node and edge carries a
`source` property saying which.

#### 5.1 Kaggle layer — `source: "kaggle"`

What the dataset in `data/seed/kaggle/` actually supports, nothing more:

```
(:KB:Disease    {slug, name, description, source})
(:KB:Symptom    {slug, name, severity, aliases: [..]})     // severity 1–7 from Symptom-severity.csv
(:KB:Precaution {slug, text})                              // deduplicated across diseases

(:KB:Disease)-[:PRESENTS_WITH {frequency, weight, source}]->(:KB:Symptom)
(:KB:Disease)-[:REQUIRES_PRECAUTION {order}]->(:KB:Precaution)
```

Size after cleaning: 41 diseases, 131 symptoms, 321 `PRESENTS_WITH` edges,
~120 distinct precautions. The dataset gives **no** duration, stage, test,
medication, exposure, vital or geography information.

#### 5.2 Curated layer — `source: "curated"`

`data/seed/curated/rural_india.yaml`. Hand-written, reviewed like code, and the only
place clinical structure beyond disease→symptom→precaution comes from:

```
(:KB:Disease)-[:PRESENTS_WITH {weight, typical_stage, screening_rule,
                               min_duration_days, source}]->(:KB:Symptom)
(:KB:Disease)-[:CONFIRMED_BY {priority}]->(:KB:DiagnosticTest)
(:KB:Disease)-[:RISK_FACTOR {weight}]->(:KB:Exposure)      // biomass smoke, water source
(:KB:Disease)-[:HAS_STAGE]->(:KB:Stage)
(:KB:Disease)-[:TREATED_BY]->(:KB:Medication)               // optional, not needed for demo
(:KB:Medication)-[:CAUSES]->(:KB:SideEffect)                // optional, not needed for demo
(:KB:Symptom)-[:MEASURED_BY {direction}]->(:KB:VitalType)   // links vitals into the graph
```

Disease nodes from this layer additionally carry `why_it_occurs`, `mitigation`,
`endemic_regions`, and `review` (`"approved" | "pending"`). **Curated overrides
Kaggle** on the same slug or edge.

The curated layer must add what Kaggle lacks and the demo needs:

| Gap | Curated addition |
|---|---|
| Diseases absent from Kaggle | `copd`, `anemia`, `chronic_kidney_disease`; `waterborne_illness` as a cluster label over gastroenteritis / typhoid |
| Golden-path symptoms absent from Kaggle | `night_sweats`, `exertional_breathlessness`, `chest_tightness` |
| Trigger-table symptoms absent from Kaggle (§8) | `facial_droop`, `limb_pain`, `injury`, `difficulty_walking`, `disorientation`; `jaundice_signs` as an alias group over `yellowish_skin`, `yellowing_of_eyes`, `dark_urine` |
| The national TB screening rule | edge `tuberculosis -PRESENTS_WITH-> cough` with `screening_rule: "NTEP presumptive TB: cough ≥ 2 weeks"`, `min_duration_days: 14`, `weight: 1.0` |
| Recommendations | `DiagnosticTest` nodes: sputum smear / CBNAAT, chest X-ray, CBC, spirometry, BP cuff confirmation, serum creatinine, malaria RDT, dengue NS1/IgM, blood culture |
| Village context | `Exposure` nodes: `biomass_smoke`, `borewell_water`, `stagnant_water` |
| Vitals into the graph | `VitalType` nodes: `heart_rate`, `respiration_rate`, `spo2`, `bp_trend`, `pallor_score` |

Only the TB entry is fully derivable from published national criteria already in
`specs.md`. Every other curated entry ships with `review: pending` until a clinician
signs it off, and the UI badges it (rule 11). **The coding agent does not silently
author clinical content.**

#### 5.3 Village context

Needed by the assessment, explainability and village screens (wireframe 13, 16, 17):

```
(:PHI:Village)-[:HAS_CLUSTER {disease_count, period, confirmed}]->(:KB:Disease)
```

Written by the village rollup job, read by synthesis as a prior. This is how
"2 confirmed TB cases in Kadiri this quarter" becomes a context edge in a reasoning
chain, and how a waterborne cluster is detected: diseases linked by `RISK_FACTOR` to
a water-source `Exposure` spiking above the village's rolling baseline.

#### 5.4 Seed data and cleaning rules

Four files in `data/seed/kaggle/` (Kaggle *disease-symptom-description* dataset):

| File | Content | Defects the seed script must fix |
|---|---|---|
| `dataset.csv` | 4,920 rows, 41 diseases × 120 rows, up to 17 symptom columns | 4,616 exact-duplicate rows → deduplicate to 304 unique rows first; leading spaces in every symptom cell; trailing spaces on `"Hypertension "`, `"Diabetes "`; internal spaces in `spotting_ urination`, `dischromic _patches`, `foul_smell_of urine` |
| `Symptom-severity.csv` | 132 symptom → weight 1–7 | junk row `prognosis`; `fluid_overload` listed twice (6 and 4 — keep the first); `spotting_urination`, `dischromic_patches`, `foul_smell_ofurine` are the canonical spellings |
| `symptom_Description.csv` | 41 disease → paragraph | `Dimorphic hemorrhoids(piles)` vs dataset `Dimorphic hemmorhoids(piles)` — join on the corrected slug via the curated `display_name` / alias, not on raw text |
| `symptom_precaution.csv` | 41 disease → up to 4 precautions | empty cells (Allergy col 3, Heart attack col 4); repeated texts across diseases → dedupe into shared `Precaution` nodes |

Slug rule: lowercase, trim, collapse internal whitespace, replace non-alphanumerics
with `_`, collapse repeated `_`, strip leading/trailing `_`. Applied to diseases and
symptoms before any join. Original Kaggle spellings (`Osteoarthristis`,
`Peptic ulcer diseae`, `(vertigo) Paroymsal  Positional Vertigo`) stay in `name`;
the curated file may set `display_name` to correct them.

**Weight derivation (decision 2026-09-21):**

```
frequency = unique rows of disease D containing symptom S / unique rows of D
weight    = frequency × (severity(S) / 7)          # both in [0, 1]
```

`frequency` is empirical co-occurrence; `severity` is the dataset's global
per-symptom weight. Curated edges set `weight` directly and override. Clinically odd
Kaggle pairs (Tuberculosis → `yellowing_of_eyes`) are retained and end up
low-weighted; they are listed in `progress.md`, not deleted.

`data/seed/curated/symptom_aliases.csv` (`alias,slug`) maps the English phrases the
LLM extractor produces — "chest feels tight", "tired quickly", "sweating at night",
"exertional dyspnea" — to canonical slugs. It must cover every term in `specs.md` §1
and the §8 trigger table. Extraction output that resolves to no slug is stored as
`unmapped_text` on the utterance and shown to the officer for manual mapping; it
never creates a node.

### Person subgraph — label prefix `:PHI`

Dynamic, per-person, written every session.

```
(:PHI:Person)-[:LIVES_IN]->(:PHI:Village)
(:PHI:Person)-[:HAD_SESSION]->(:PHI:Session)
(:PHI:Session)-[:CAPTURED]->(:PHI:Reading)        // vitals, with quality score
(:PHI:Session)-[:TRANSCRIBED]->(:PHI:Utterance)   // speaker-attributed turns
(:PHI:Session)-[:OBSERVED]->(:PHI:Finding)        // face mesh / posture results
(:PHI:Session)-[:CONCLUDED]->(:PHI:Assessment)
```

### The join

```
(:PHI:Reading)-[:SUGGESTS {confidence}]->(:KB:Symptom)
(:PHI:Utterance)-[:REPORTS {confidence, verbatim}]->(:KB:Symptom)
(:PHI:Finding)-[:INDICATES {confidence}]->(:KB:Symptom)
(:PHI:Assessment)-[:CONSIDERED {score, rank}]->(:KB:Disease)
(:PHI:Assessment)-[:RECOMMENDS]->(:KB:DiagnosticTest)
```

**Every join edge carries a confidence value.** rPPG and face mesh are probabilistic.
A single noisy reading must never assert a disease at full confidence.

### Separation without separate databases

The separation Udit's instinct was reaching for is real — different lifecycles,
different ownership, different privacy posture — but it is achieved through labels,
permissions and pipelines, not through two physical stores:

- **Label-based RBAC.** The app service writes `:PHI`, reads `:KB`. The seed job does
  the inverse.
- **Separate pipelines.** `:KB` loads from versioned seed files via a migration script,
  reviewed like code. `:PHI` writes only through the app.
- **KB is rebuildable.** The graph is a materialised copy of the seed files. If a
  physical split is ever needed, the door is open.

Splitting physically now would force `Person → Symptom → Disease → Precaution` to
become an application-layer join across two databases — rebuilding by hand exactly the
thing a graph database exists to avoid.

---

## 6. Memory model

Three tiers. The agent's context is never the full history.

### Tier 1 — Working memory (in-process, life of one turn)

Live session state: current vitals, running transcript, extracted pain points,
findings so far, which second-look features have been proposed and accepted.
Held in a `SessionState` object. Lost on restart; that is acceptable.

### Tier 2 — Session memory (`:PHI:Session` node)

One visit. Persisted continuously so a mid-session crash loses nothing. Holds
readings, utterances, findings, assessment, the reasoning chain, and the report.

### Tier 3 — Person memory (`:PHI:Person` node + session chain)

Accumulates across visits. Enables longitudinal statements — "SpO₂ was 97% in March,
94% today." Only a **summary** enters the agent context, never the full history:

```python
{
  "demographics": {...},
  "village_context": {...},          # endemic exposure, recent village trends
  "chronic_flags": [...],            # confirmed ongoing conditions
  "vital_baselines": {...},          # rolling median per vital
  "last_session": {"date":..., "top_findings": [...], "recommendations": [...]},
  "open_followups": [...]            # recommended but not yet confirmed done
}
```

### Context assembly

```
agent_context = person_summary + current_session_state + retrieved_subgraph
```

The retrieved subgraph is the result of graph traversal, capped at the top N candidate
diseases. Never dump the whole knowledge graph into the prompt.

---

## 7. Session flow

**Stages 2 and 4 are both camera captures, and the separation is deliberate.**
Stage 2 is unconditional and identical for everyone. Stage 4 exists only because
something in stage 3 triggered it. That conditionality is what makes the agent look
intelligent rather than scripted.

| # | Stage | What happens | Wireframe screens |
|---|---|---|---|
| 1 | Intake | Name, age, gender, village, language, consent. No ID required. | 1, 2 |
| 2 | Face vitals scan | Always first. rPPG + passive face mesh. | 3, 4, 4b, 5, 5b |
| 3 | Consultation | Record, transcribe, attribute speakers, extract pain points, officer review. | 6, 7, 8, 9 |
| 4 | Second look | Agent proposes a feature; officer accepts; guided capture. | 10, 11, 12 |
| 5 | Synthesis | Graph traversal + risk models + reasoning chain. | 13, 16 |
| 6 | Report | PDF, record write, village rollup. | 14, 15, 17 |

Stage 5 runs as a **background job**. The officer saves the session and calls the next
person while analysis completes, then recalls the first person to show the report.
This mirrors how labs already work and is how Swaroop specified it.

---

## 8. Second-look trigger engine

A rules layer, not an LLM decision. Deterministic, explainable, testable.
The LLM extracts symptoms; the rule engine maps symptoms to capture features.

| Trigger | Feature proposed | What it measures |
|---|---|---|
| chest pain, breathlessness, cough | Chest-rise respiration | Pose: shoulder/chest amplitude, rate |
| " | Lip cyanosis | Face mesh: lip region hue |
| limb pain, accident, injury | Swelling asymmetry | Landmark distance, left vs right |
| " | Guided range of motion | Pose: joint angle sweep |
| fatigue, weakness, dizziness | Pallor check | Face mesh: conjunctiva + skin |
| jaundice signs, dark urine | Sclera colour | Face mesh: eye white hue |
| facial droop observed | Facial asymmetry | **Highest priority — stroke red flag** |
| back/neck pain, can't stand long | Posture assessment | Forward head, shoulder tilt, spinal curve |
| difficulty walking, limp | Gait and balance | Pose over a walk cycle |
| disorientation reported | Blink rate, micro-tremor | Face mesh over time |

**Always-on during stage 2** (no extra capture needed): facial tension / stress
estimate, blink rate.

Each rule carries a priority. Facial asymmetry outranks everything — a suspected
stroke interrupts the flow immediately.

---

## 9. Risk models (background)

While the consultation is happening, captured parameters run against lightweight
models. Swaroop's brief: find parameters a phone can capture without extra equipment,
then find models that run on exactly those.

Phone-capturable inputs: age, gender, HR, RR, SpO₂, BP trend, pallor score, BMI
(if height/weight entered), reported symptoms, village exposure, posture score.

Demo models (scikit-learn, trained offline, shipped as pickled artifacts):
- **Anemia risk** — pallor + HR + fatigue + gender
- **COPD risk** — age + RR + SpO₂ + biomass exposure + cough duration
- **Hypertension risk** — age + BMI + BP trend + HR variability
- **CKD risk** — the classic UCI CKD feature set, restricted to phone-capturable fields

Every output ships with the model's reported metric (accuracy or F1) and an explicit
"screening signal, not a diagnosis" label.

---

## 10. AI provider seam

Offline is a pitch claim today, and the architecture must make that claim credible.

```python
class STTProvider(Protocol):
    async def transcribe(self, audio: bytes, lang_hint: str) -> Transcript: ...

class LLMProvider(Protocol):
    async def complete(self, prompt: str, schema: type[BaseModel]) -> BaseModel: ...
```

Implementations: `GeminiSTT`, `GeminiLLM` (used now); `WhisperCppSTT`, `OllamaLLM`
(stubbed, documented, not wired).

This lets you point at a real seam in the code during the pitch and say: *the knowledge
graph is already fully local; this is where the local models drop in.* That is honest,
and the graph being local is the strongest part of the offline claim anyway.

### Speaker attribution

Gemini can transcribe audio, but reliable audio-level diarization is not its strength.
**Attribute by content, not by audio.** Send the full transcript and have the LLM
assign turns based on who asks questions and who uses clinical vocabulary. This is more
robust than audio diarization and demos identically. Swaroop himself named this as the
acceptable path.

### Languages

English, Telugu, Hindi. Gemini handles all three natively. The officer picks the
language at session start; it is stored on the session. Extracted symptoms are always
normalised to **English canonical terms** before graph lookup — the graph is
English-only, the UI is trilingual.

---

## 11. Repository layout

```
sanjeevani/                     # this repo root
├─ CLAUDE.md                    # entry point for every session
├─ architecture.md              # this file
├─ specs.md
├─ progress.md                  # hand-off file between sessions
├─ demo.md                      # written in Phase 7
├─ docker-compose.yml           # neo4j + backend + frontend, local fallback
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ api/                   # vitals, session, consult, secondlook, synthesis, report, person, village, kb
│  │  ├─ rppg/                  # signal.py, quality.py, pos.py, chrom.py
│  │  ├─ graph/                 # client.py, queries.py, seed.py, schema.cypher
│  │  ├─ agents/                # extraction, triggers, synthesis, reasoning
│  │  ├─ providers/             # stt.py, llm.py — the seam
│  │  ├─ risk/                  # model wrappers + artifacts
│  │  ├─ memory/                # session state, person summary assembly
│  │  └─ report/                # pdf builder, templates, assets
│  └─ tests/
├─ frontend/
│  ├─ src/
│  │  ├─ screens/               # one per wireframe state
│  │  ├─ components/            # one per wireframe CSS class
│  │  ├─ capture/               # mediapipe, rppg client extraction, pose
│  │  ├─ api/                   # client.ts + generated types
│  │  └─ i18n/                  # en, te, hi
│  └─ ui-reference/
│     └─ sanjeevani-flow.html   # the wireframe — visual source of truth
└─ data/
   └─ seed/
      ├─ kaggle/                # 4 raw csv, never hand-edited
      └─ curated/               # rural_india.yaml, symptom_aliases.csv
```

---

## 12. Deployment

| Component | Host | Notes |
|---|---|---|
| Frontend | Vercel | Static build; camera needs HTTPS, Vercel provides it |
| Backend | Render free tier | ~50s cold start — **warm it before the demo** |
| Graph | Neo4j AuraDB free | 200k nodes / 400k relationships limit; ample |
| Secrets | Env vars | Gemini key, Neo4j URI/user/password |

**Demo from localhost.** Deploy for the URL and the credibility; run the actual
demo off `docker compose up` on the laptop. Venue wifi has ended more hackathon demos
than bad code has.

---

## 13. Known risks

| Risk | Mitigation |
|---|---|
| rPPG signal poor under venue lighting | Quality gating + retake prompt + a ring light in the bag |
| Render cold start mid-demo | Warm the backend before presenting; localhost fallback |
| Webcam permission denied on stage | Test the exact browser/laptop beforehand; keep a recorded clip |
| MediaPipe WASM slow on older hardware | Cap frame rate; degrade ROI count gracefully |
| Gemini rate limit or latency | Cache golden-path responses; retry with backoff |
| Judge asks about clinical validation | Answer honestly: screening aid, not diagnosis; validation is the next step |
| Overclaiming accuracy | Confidence tiers enforced in UI, not just in docs |
| Curated clinical content unreviewed | `review: pending` badge in UI; say so to the judge; only the TB entry is guideline-derived |
| Golden path not reproducible from Kaggle alone | Curated TB entry + `symptom_aliases.csv` are Phase 1 deliverables, validated by a seed test |

---

## 14. Ethical position

State this plainly in the pitch and in the product:

- This is a **screening and documentation aid for a trained officer**, never a
  diagnosis and never a replacement for one.
- Every recommendation carries visible reasoning.
- Vitals outside their confidence tier are labelled, not hidden.
- The person gives explicit consent at intake, before any camera turns on.
- Where a phone cannot do something, the app says so rather than approximating it.

The transparency is a competitive advantage. Any judge with clinical background will
trust a system that names its limits over one that hides them.
