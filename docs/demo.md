# Demo

Practical run-of-show for the pitch. Not a rehash of `architecture.md` —
if you need to explain *why* something works, that's the other docs; this
one is about not fumbling the ten minutes on stage.

---

## Presentation order: story first, then the app

Judges see a lot of "here's our app" openers in a row. Lead with the problem,
not the screen.

1. **The problem** (30-45s): rural health camps run through dozens of people
   a day; the medical officer has a stethoscope, a BP cuff if they're lucky,
   and no lab. A cough that's "probably nothing" and a cough that's
   presumptive TB look identical from the intake line. Follow-up tests either
   don't get ordered, or get ordered for everyone, both fail.
2. **The Sanjeevani approach** (30-45s): the officer's phone becomes a second
   set of eyes, not a diagnosis machine. Camera-based vitals with an honest
   quality tier, a natural-language conversation instead of a checklist,
   a knowledge graph seeded from real screening criteria (NTEP for TB) doing
   the reasoning, and the officer stays the decision-maker — the system
   produces *considerations* and *recommended tests*, never a diagnosis
   (CLAUDE.md absolute rule 1). Say this rule out loud; it's the credibility
   line.
3. **The golden path, live** (5-7 min): screens 1 -> 17 in order, narrating
   what's real vs. what's a screening signal:
   - **1 (dashboard) -> 2 (intake)**: consent gate — "no capture happens
     without this checkbox, enforced twice, in the UI and in the API."
   - **3 -> 4 -> 5**: real rPPG scan. Call out the quality bar and that BP is
     a trend arrow, never a number — "the phone camera cannot give you an
     mmHg reading and we won't pretend it can."
   - **6 -> 7 -> 8 -> 9**: voice consultation in Telugu, live transcript,
     extracted pain points with confidence dots, officer can edit/remove —
     "the model proposes, the officer disposes."
   - **10 -> 11 -> 12**: the agent proposes a targeted second-look capture
     (chest-rise for the golden path) instead of a generic checklist, runs it,
     shows the finding with its stated limitations.
   - **13**: the assessment — TB ranked first, with the actual reasoning
     chain (cough >= 2 weeks meets the NTEP presumptive-TB threshold, weight
     loss, night sweats) and recommended tests, not a verdict.
   - **16** (if built/un-greyed by the time you present): open the reasoning
     chain as a graph — this is "developer mode," the receipts behind the
     assessment.
   - **17**: village dashboard — this case isn't isolated, here's the cluster
     view.
   - **14/15/Download report**: the PDF, the thing the officer actually walks
     away with.
4. **Close** (15-20s): what's real today (real signal processing, real graph
   reasoning, real STT) vs. what's explicitly out of scope (no haemoglobin
   estimate, no health score, no self-diagnosis) — CLAUDE.md's absolute rules
   are the honesty story, not a limitation to apologize for.

---

## Pre-demo checklist

Do this in order, ~15-20 minutes before your slot:

- [ ] **Warm the backend.** If running against the deployed Render URL:
      `curl https://<render-url>/health`, wait for `{"status":"ok"}`, then hit
      a real endpoint too (`/api/session/pending`) so the Neo4j connection
      pool is warm, not just the process. See `docs/deploy.md` §4. Repeat once
      more right before you're called up if there's been a gap.
- [ ] **Check AuraDB isn't paused.** Free-tier AuraDB auto-pauses after
      inactivity — open the Aura console and confirm the instance shows
      "Running," not "Paused."
- [ ] **Test on the exact laptop and browser you'll present with.** Not a
      different machine "that should be the same." Chrome or Edge (MediaPipe
      WASM + `getUserMedia` + `MediaRecorder` all need testing on the real
      device, not assumed from earlier phases' sandboxed verification).
- [ ] **Grant camera + mic permission ahead of time.** Open the app, get to
      screen 3 and screen 6, accept both permission prompts *before* you're
      on stage — a permission dialog mid-pitch is the single most avoidable
      failure. Reload once after granting to confirm it stuck.
- [ ] **Check lighting for the rPPG scan.** The signal quality bar (screen 4)
      needs even, front-facing light on the presenter's face — avoid strong
      backlighting (window/spotlight behind the demoer) and avoid deep venue
      shadow. Do a 10-second test scan and confirm it reaches "good," not
      "low_light"/"high_motion," before you're live. If the venue lighting is
      bad and can't be fixed, know the story: screen 4b/5b (low-signal state)
      is itself a real, honest UI state — worst case, narrate *that* instead
      of pretending it isn't happening.
- [ ] **Have fixture mode ready as a network-loss contingency.** Venue wifi
      is the single most common hackathon failure mode. Set
      `SANJEEVANI_FIXTURE_MODE=true` on the Render service (dashboard ->
      Environment -> edit -> redeploy) *before* the slot if you have any
      doubt about the venue network, or keep a terminal ready to flip it fast.
      With it set, every STT/LLM call skips the live attempt entirely and
      serves the golden-path Ramesh Kumar script — the demo narrative doesn't
      change, only the `source` field (visible in developer mode) flips from
      `"live"` to `"golden_path_cache"`. Flip it back to `false` after the
      slot if you want live calls for Q&A follow-ups.
- [ ] **Confirm the golden-path script matches what you'll say.** The cached
      transcript is the specs.md §1 Ramesh Kumar script (21-day cough, chest
      tightness, fatigue, night sweats, weight loss) — if you're improvising
      different symptoms live and the network holds, that's fine (real
      extraction); if fixture mode is on, say *that* script regardless of
      what you actually say into the mic, since the audio itself isn't what's
      served back.

---

## Local fallback: `docker compose up`

If Render/Vercel/AuraDB are unreachable at the venue (or you'd rather not
depend on wifi at all), the whole stack runs from `docker compose up` on the
demo laptop, exactly as every phase since Phase 1 has verified:

```
docker compose up
# backend:  http://localhost:8000/health        -> {"status": "ok"}
# frontend: http://localhost:5173/#/1            -> camp dashboard
# neo4j browser: http://localhost:7474            (neo4j / sanjeevani123)

# once, before the first demo run:
docker compose exec backend python -m app.graph.seed
```

This is the safety net, not the primary path — the deployed URLs are the
credibility signal ("this actually runs on the internet, not just my
laptop"), per the Phase-0 decision log ("Deploy live, demo from localhost" —
if in doubt at the venue, invert that and demo from localhost, keep the
deployed URLs for the judges to check afterward). Local mode has no external
network dependency at all beyond the Gemini calls themselves — set
`SANJEEVANI_FIXTURE_MODE=true` in the shell before `docker compose up` (or
add it to a local `.env`, which `docker-compose.yml`'s `GEMINI_API_KEY:
${GEMINI_API_KEY:-}` pattern already supports extending) to remove even that
dependency.

Run the offline end-to-end test any time to confirm the whole golden path
still works with zero network, zero live Neo4j:
```
cd backend
SANJEEVANI_FIXTURE_MODE=true pytest tests/test_golden_path_e2e.py -v
```
