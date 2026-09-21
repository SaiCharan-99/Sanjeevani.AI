# Sanjeevani.AI

Phone-based screening assistant for rural health camps in India. A medical officer
opens it in a browser, points the camera at a person, has a conversation, and gets a
structured assessment with recommended follow-up tests — with every recommendation
carrying its reasoning. Screening aid for a trained officer; never a diagnosis.

## Docs (read in this order)

| File | Purpose |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Entry point for every coding session — rules, conventions, hand-off protocol |
| [progress.md](progress.md) | What is done, stubbed, decided, open. Updated every phase |
| [architecture.md](architecture.md) | System design, graph model, seed data, memory model |
| [specs.md](specs.md) | Screens, API contracts, rPPG spec, knowledge base, copy rules |
| [frontend/ui-reference/sanjeevani-flow.html](frontend/ui-reference/sanjeevani-flow.html) | The wireframe — visual source of truth (open in a browser, ← / → to navigate) |

## Data

`data/seed/kaggle/` — raw Kaggle disease-symptom dataset, never hand-edited.
`data/seed/curated/` — hand-written rural-India layer (created in Phase 1).

## Run

```bash
docker compose up
```

(available from Phase 1)
