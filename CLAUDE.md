# CLAUDE.md

Context for AI coding agents working in this repository.
**This file is the entry point for every session.** Each build phase runs in a fresh
session with no memory of the last one, so continuity lives in the files, not the chat.

Reading order at the start of every session:

1. `CLAUDE.md` (this file) — rules and conventions
2. `progress.md` — what is done, what is stubbed, decisions taken, open questions.
   **This is the hand-off file. Read it before touching code; update it before stopping.**
3. `architecture.md` — system design and graph model
4. `specs.md` — screens, API contracts, pipelines, copy rules
5. `frontend/ui-reference/sanjeevani-flow.html` — the visual source of truth (for any UI work)

Repository layout is in `architecture.md` §11. All docs live at the repo root.

---

## What this is

**Sanjeevani** — a phone-based diagnostic assistant for rural health camps in India.
A medical officer opens it in a browser, points the camera at a person, has a
conversation, and gets a structured assessment with recommended follow-up tests.

Built for a hackathon demo. Judged on whether the story lands and the demo works.

---

## Absolute rules

These are not preferences. Violating them breaks the product's integrity.

1. **Never emit a medical diagnosis.** The system produces *considerations*,
   *screening signals* and *recommendations for a trained officer*. Language matters:
   "consider", "screening positive for", "recommend testing for" — never "has" or
   "diagnosed with".

2. **Never emit an absolute blood pressure value from rPPG.** Trend direction only.
   The research does not support mmHg values from a phone camera.

3. **Never implement haemoglobin estimation from camera.** It was explicitly cut.
   Use the pallor-based anemia risk flag instead.

4. **Every vital ships with a quality score and a confidence tier.** If quality is
   below threshold, the UI prompts a retake rather than printing a number.
   Never render a vital without its tier.

5. **Never stream video to the backend.** The browser extracts mean RGB per ROI per
   frame and posts a small JSON array. This is load-bearing for the deployed demo.

6. **Every join edge between person data and the knowledge graph carries a
   confidence value.** rPPG and face mesh are probabilistic.

7. **Consent before camera.** No capture endpoint accepts a session without
   `consent: true`.

8. **A person is a "person", not a "patient"**, until something is found.
   This is in the UI copy and in the code's naming.

9. **No composite "health score".** The wireframe shows an `80/100` ring; it has no
   defined formula and reads as a verdict. It is cut. Render per-vital values with
   tiers instead. (Decision 2026-09-21, see `progress.md`.)

10. **UI copy claims only what the build delivers.** "Video never leaves the device"
    is true. "Offline mode", "queued for sync", "encrypted locally" are pitch claims
    while Gemini is required — do not put them in the UI. See `specs.md` §8 for the
    exact string substitutions.

11. **Never invent clinical content.** Symptom weights, diagnostic tests, screening
    rules and precautions come from the seed data (`data/seed/`). Curated entries
    not yet reviewed by a clinician carry `review: pending` and are badged in the UI.
    The LLM may *phrase* a recommendation; it may never *originate* one.

---

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.11 + FastAPI | async throughout |
| Signal | NumPy, SciPy, OpenCV | rPPG pipeline |
| Graph | Neo4j + official Python driver | Cypher, not an ORM |
| AI | Gemini API | behind a provider interface |
| ML | scikit-learn | pickled artifacts, trained offline |
| PDF | ReportLab | |
| Frontend | React 18 + Vite + TypeScript | |
| Vision | MediaPipe Tasks (WASM) | face mesh + pose, client-side |
| Styling | Tailwind | theme extended from the `:root` tokens in the wireframe; the wireframe itself uses plain CSS |
| i18n | react-i18next | en, te, hi |

---

## The UI-first workflow

**This is unusual and important.**

The visual source of truth is **`frontend/ui-reference/sanjeevani-flow.html`**.
It is a single self-contained prototype (not per-screen Stitch files): 19 screen
states defined as HTML template strings in a `SCREENS = [...]` array, styled by CSS
custom properties on `:root`, navigable with ← / → in a browser.

Before any frontend work, extract from it:

- **Tokens** (`:root`): `--bg #0E1512`, `--bg-2 #131D1A`, `--surface #17231F`,
  `--surface-2 #1D2C27`, `--line #25382F`, `--line-soft #1F302A`,
  `--accent #84D3B8`, `--accent-ink #0B1714`, `--accent-dim #2E5347`,
  `--accent-soft #1B2F29`, `--ok #84D3B8`, `--warn #E3B461`, `--warn-soft #2E2718`,
  `--bad #E08A7E`, `--bad-soft #2E1E1C`, `--text #E9F1EE`, `--text-2 #A7BCB5`,
  `--text-3 #728880`, `--r 14px`, `--r-lg 20px`, font Inter.
  Map these 1:1 into `tailwind.config` as named colours / radii. Dark theme only.
- **Component vocabulary** (CSS classes): `top`, `title`, `sub`, `card`, `sec`,
  `list`, `item`, `avatar`, `meta`, `tag` (+ `accent|warn|bad`), `kv`, `pill`,
  `pillrow`, `seg`, `field`, `cta`, `icon-btn`, `stat`, `bar`, `big`, `unit`,
  `note`, `quote`, `foot-note`, `ring-wrap`, `camera`, `tabs`/`tab`, `turn`,
  `who`, `bubble`, `chip-pill`, `wave`. Build one React component per class;
  screens compose them.
- **Copy** per screen — but apply the substitutions in `specs.md` §8 first; the
  wireframe contains strings that violate the absolute rules.

Screen identity: use the **wireframe labels** (`1`, `2`, `3`, `4`, `4b`, `5`, `5b`,
`6` … `17`). The `S1–S15` ids in older text are aliases; the mapping table is in
`specs.md` §2.

For every phase:

1. Read the relevant `SCREENS[]` entries first. Extract layout, spacing, tokens,
   structure and copy.
2. Build React components that match. Do not invent a different design.
   Do not "improve" it unasked.
3. **Every screen exists from Phase 1**, in a visibly inactive state — greyed,
   with a "Not yet implemented" affordance.
4. As each feature is built, activate its screen. The progression from greyed-out
   to live is itself the visible measure of progress. Record it in `progress.md`.

If the spec needs a state the wireframe lacks, build it from the same tokens and
components and note it in `progress.md`.

## Code conventions

**Python**
- Type hints everywhere. Pydantic models for every request and response.
- `async def` for all route handlers and I/O.
- Cypher lives in `graph/queries.py` as named constants, never inline in business
  logic.
- Providers are Protocol classes. Never import `google.generativeai` outside
  `providers/`.
- Signal-processing functions are pure: arrays in, arrays out, no I/O.

**TypeScript**
- No `any`. Generate types from the Pydantic schemas where practical.
- Capture logic lives in `capture/`, isolated from screens.
- API calls go through `api/client.ts`, never `fetch` in a component.

**Naming**
- `Person` not `Patient` in domain models.
- `consideration` not `diagnosis`.
- `finding` for observed evidence; `symptom` for graph-canonical terms.

---

## Graph conventions

- `:KB` labels are read-only at runtime. Only the seed script writes them.
- `:PHI` labels hold person data.
- Extracted symptoms are normalised to **English canonical terms** before any graph
  lookup. The graph is English-only; the UI is trilingual.
- Never dump the whole graph into an LLM prompt. Traverse, cap at top N, pass the
  subgraph.

---

## Knowledge-base data conventions

- Raw Kaggle CSVs live in `data/seed/kaggle/` and are **never hand-edited**. Every
  fix (whitespace, typos, broken joins, duplicates) is a rule in
  `backend/app/graph/seed.py`, documented in `architecture.md` §5.4.
- Hand-written clinical content lives in `data/seed/curated/` (`rural_india.yaml`,
  `symptom_aliases.csv`). **Curated overrides Kaggle** when both define the same
  slug or edge.
- The **symptom canonical term is its slug**: cleaned Kaggle snake_case
  (`skin_rash`, `night_sweats`, `chest_tightness`). Node `name` is the display form.
- The LLM extractor must return a slug that exists in the graph, resolved through
  `symptom_aliases.csv`. An unresolvable term stays on the `:PHI:Utterance` as
  `unmapped_text`; **runtime never creates `:KB:Symptom` nodes.**
- `PRESENTS_WITH.weight` on Kaggle edges is derived, not authored:
  `frequency × severity / 7` (see `architecture.md` §5.4). Curated edges set
  `weight` explicitly.
- Clinically odd Kaggle pairs (e.g. Tuberculosis → `yellowing_of_eyes`) are kept
  and down-weighted by frequency, never deleted silently. Log them in `progress.md`.
- Seed is idempotent: `MERGE` on slug, safe to re-run against local and AuraDB.

---

## AI provider rules

- All Gemini calls go through `providers/llm.py` or `providers/stt.py`.
- **Always request structured output.** Define a Pydantic schema, instruct the model
  to return only JSON with no markdown fences, parse defensively.
- Speaker attribution is **content-based**, not audio diarization. Send the transcript,
  have the LLM assign turns by who asks questions and who uses clinical vocabulary.
- Cache golden-path responses so a rate limit cannot kill the demo.

---

## Testing

- rPPG pipeline: synthetic signals with known frequency. If you inject a 1.2 Hz
  sinusoid, the pipeline must return 72 bpm.
- Trigger engine: table-driven. Symptom set in, expected feature list out.
- Graph traversal: fixture graph, assert the reasoning chain, not just the answer.
- Golden path: one end-to-end test with recorded fixtures that runs without network.

---

## What not to do

- Do not add features not in `specs.md`. Ask first — *except* small improvements
  that serve the golden path and do not touch clinical logic, styling tokens or the
  absolute rules. Record any such improvisation in `progress.md` → Decisions log.
- Do not build patient-facing self-diagnosis. Explicitly out of scope.
- Do not soften the confidence tiers to make the demo look better.
- Do not replace real signal processing with simulated values. The decision was real
  rPPG, noise accepted.
- Do not refactor the wireframe-derived design.
- Do not add an ORM over Neo4j.

---

## When you are unsure

Stop and ask. Specifically ask when:
- A clinical claim needs to be made and the graph does not support it
- The wireframe lacks a screen the spec requires and it cannot be composed from
  existing components
- A quality threshold needs to be chosen and no value is specified
- A dependency would need to be added that is not in the stack table

Do not guess on anything clinical. Guessing on styling is fine; guessing on
medical logic is not.

---

## Session hand-off protocol

Because each phase is a new session:

- **Start:** read the files in the order at the top of this document. Check
  `progress.md` → Phase status, Blockers and Open questions before writing code.
- **During:** append every non-trivial decision to `progress.md` → Decisions log
  with the date and the reasoning.
- **End:** update `progress.md` — phase status, screen activation table, golden-path
  readiness, phase notes (what is done, what is stubbed, what is next, how to run
  it). Leave the tree in a state where `docker compose up` works. Do not leave
  half-applied migrations or seeds.
