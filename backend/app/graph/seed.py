"""Idempotent knowledge-graph seed script.

Loads the 4 raw Kaggle CSVs (data/seed/kaggle/, never hand-edited) and the curated
layer (data/seed/curated/), applying the cleaning rules documented in
architecture.md §5.4. Curated overrides Kaggle on the same slug/edge.

Run: `python -m app.graph.seed` (needs NEO4J_* env vars) or invoked by the seed test
against a fixture-only in-memory pass (see backend/tests/test_seed.py which loads
the CSVs/YAML directly without a live Neo4j — the graph write path is exercised only
when a driver is available).
"""

from __future__ import annotations

import asyncio
import csv
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.graph import queries as q
from app.graph.client import GraphClient

def _find_repo_root() -> Path:
    """Locate the directory containing data/seed/.

    Fixed-depth `parents[N]` breaks across environments: locally this file
    sits at <repo>/backend/app/graph/seed.py (3 levels down), but the Docker
    image copies `backend/app` to `/app/app`, dropping the `backend/`
    nesting level entirely. Search upward instead of assuming a depth.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "data" / "seed").is_dir():
            return parent
    raise FileNotFoundError("Could not locate data/seed/ above " + str(__file__))


REPO_ROOT = _find_repo_root()
KAGGLE_DIR = REPO_ROOT / "data" / "seed" / "kaggle"
CURATED_DIR = REPO_ROOT / "data" / "seed" / "curated"

# Known broken joins that the naive slug rule alone would not reconcile.
# Maps a raw (post-slug) spelling to the canonical spelling used everywhere else.
JOIN_FIXES = {
    "spotting_urination": "spotting_urination",  # dataset has "spotting_ urination" -> slug collapses space, fine
    "dischromic_patches": "dischromic_patches",  # dataset has "dischromic _patches"
    "foul_smell_ofurine": "foul_smell_of_urine",  # severity file spelling vs dataset "foul_smell_of urine"
    "foul_smell_of_urine": "foul_smell_of_urine",
    # dataset: "Dimorphic hemmorhoids(piles)" vs description file: "Dimorphic hemorrhoids(piles)"
    "dimorphic_hemmorhoids_piles": "dimorphic_hemorrhoids_piles",
}


def slugify(raw: str) -> str:
    """Lowercase, trim, collapse whitespace, non-alnum -> _, collapse repeats, strip _."""
    s = raw.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    return JOIN_FIXES.get(s, s)


@dataclass
class KaggleData:
    diseases: dict[str, str] = field(default_factory=dict)  # slug -> display name
    symptoms: dict[str, str] = field(default_factory=dict)  # slug -> display name
    severity: dict[str, int] = field(default_factory=dict)  # slug -> 1-7
    descriptions: dict[str, str] = field(default_factory=dict)  # disease slug -> text
    precautions: dict[str, list[str]] = field(default_factory=dict)  # disease slug -> [precaution slugs]
    precaution_text: dict[str, str] = field(default_factory=dict)  # precaution slug -> text
    disease_symptom_rows: dict[str, list[set[str]]] = field(default_factory=lambda: defaultdict(list))
    # disease slug -> list of symptom-sets, one per unique row (post-dedupe)


def load_kaggle() -> KaggleData:
    data = KaggleData()

    # dataset.csv: dedupe exact rows first, then build disease/symptom slugs.
    with open(KAGGLE_DIR / "dataset.csv", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        seen_rows: set[tuple[str, ...]] = set()
        rows = []
        for row in reader:
            key = tuple(c.strip() for c in row)
            if key in seen_rows:
                continue
            seen_rows.add(key)
            rows.append(row)

    for row in rows:
        disease_raw = row[0]
        disease_slug = slugify(disease_raw)
        data.diseases[disease_slug] = disease_raw.strip()
        symptom_cells = [c for c in row[1:] if c and c.strip()]
        symptom_slugs = set()
        for cell in symptom_cells:
            sslug = slugify(cell)
            if not sslug:
                continue
            symptom_slugs.add(sslug)
            data.symptoms.setdefault(sslug, cell.strip())
        data.disease_symptom_rows[disease_slug].append(symptom_slugs)

    # Symptom-severity.csv: drop junk "prognosis" row; first occurrence wins on dupes.
    with open(KAGGLE_DIR / "Symptom-severity.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            name = (r.get("Symptom") or "").strip()
            if not name or name.lower() == "prognosis":
                continue
            sslug = slugify(name)
            if sslug in data.severity:
                continue  # keep first (fluid_overload dedupe rule)
            try:
                data.severity[sslug] = int(r["weight"])
            except (KeyError, ValueError):
                continue

    # symptom_Description.csv: join on corrected slug, not raw text.
    with open(KAGGLE_DIR / "symptom_Description.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            dslug = slugify(r.get("Disease", ""))
            desc = (r.get("Description") or "").strip()
            if dslug and desc:
                data.descriptions[dslug] = desc

    # symptom_precaution.csv: skip empty cells, dedupe shared precaution text.
    text_to_slug: dict[str, str] = {}
    with open(KAGGLE_DIR / "symptom_precaution.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            dslug = slugify(r.get("Disease", ""))
            if not dslug:
                continue
            plist = []
            for col in ("Precaution_1", "Precaution_2", "Precaution_3", "Precaution_4"):
                text = (r.get(col) or "").strip()
                if not text:
                    continue
                norm = re.sub(r"\s+", " ", text.lower())
                pslug = text_to_slug.get(norm)
                if pslug is None:
                    pslug = slugify(text)
                    text_to_slug[norm] = pslug
                    data.precaution_text[pslug] = text
                plist.append(pslug)
            data.precautions[dslug] = plist

    return data


def compute_weights(data: KaggleData) -> list[tuple[str, str, float, float]]:
    """Returns (disease_slug, symptom_slug, frequency, weight) for every unique pair.

    frequency = unique rows of D containing S / unique rows of D
    weight    = frequency * (severity(S) / 7)
    """
    out = []
    for dslug, rows in data.disease_symptom_rows.items():
        total = len(rows)
        counts: dict[str, int] = defaultdict(int)
        for rowset in rows:
            for s in rowset:
                counts[s] += 1
        for sslug, c in counts.items():
            frequency = c / total if total else 0.0
            severity = data.severity.get(sslug, 1)
            weight = frequency * (severity / 7)
            out.append((dslug, sslug, frequency, weight))
    return out


def load_curated_diseases() -> dict[str, Any]:
    path = CURATED_DIR / "rural_india.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_curated_aliases() -> list[tuple[str, str]]:
    path = CURATED_DIR / "symptom_aliases.csv"
    out = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            alias = (r.get("alias") or "").strip()
            slug = (r.get("slug") or "").strip()
            if alias and slug:
                out.append((alias, slug))
    return out


async def seed_graph(client: GraphClient) -> None:
    data = load_kaggle()
    curated = load_curated_diseases()

    # --- Kaggle layer ---
    for slug, name in data.diseases.items():
        await client.run(
            q.MERGE_KB_DISEASE,
            slug=slug, name=name, source="kaggle",
            description=data.descriptions.get(slug),
        )
    for slug, name in data.symptoms.items():
        await client.run(
            q.MERGE_KB_SYMPTOM,
            slug=slug, name=name, source="kaggle",
            severity=data.severity.get(slug), aliases=[],
        )
    for slug, text in data.precaution_text.items():
        await client.run(q.MERGE_KB_PRECAUTION, slug=slug, text=text)

    for dslug, sslug, frequency, weight in compute_weights(data):
        await client.run(
            q.MERGE_PRESENTS_WITH_KAGGLE,
            disease_slug=dslug, symptom_slug=sslug, frequency=frequency, weight=weight,
        )
    for dslug, plist in data.precautions.items():
        for order, pslug in enumerate(plist):
            await client.run(
                q.MERGE_REQUIRES_PRECAUTION,
                disease_slug=dslug, precaution_slug=pslug, order=order,
            )

    # --- Curated layer (overrides) ---
    for dslug, d in (curated.get("diseases") or {}).items():
        await client.run(
            q.MERGE_KB_DISEASE_CURATED,
            slug=dslug, name=d.get("name", dslug),
            description=d.get("description"), why_it_occurs=d.get("why_it_occurs"),
            mitigation=d.get("mitigation"), endemic_regions=d.get("endemic_regions", []),
            review=d.get("review", "pending"),
        )
        for edge in d.get("presents_with", []):
            await client.run(
                q.MERGE_KB_SYMPTOM_CURATED,
                slug=edge["symptom"], name=edge.get("symptom_name"),
                severity=edge.get("severity"),
            )
            await client.run(
                q.MERGE_PRESENTS_WITH_CURATED,
                disease_slug=dslug, symptom_slug=edge["symptom"],
                weight=edge.get("weight", 0.5), typical_stage=edge.get("typical_stage"),
                screening_rule=edge.get("screening_rule"),
                min_duration_days=edge.get("min_duration_days"),
            )
        for edge in d.get("confirmed_by", []):
            await client.run(q.MERGE_KB_TEST, slug=edge["test"], name=edge.get("test_name", edge["test"]))
            await client.run(
                q.MERGE_CONFIRMED_BY,
                disease_slug=dslug, test_slug=edge["test"], priority=edge.get("priority", 1),
            )
        for edge in d.get("risk_factors", []):
            await client.run(q.MERGE_KB_EXPOSURE, slug=edge["exposure"], name=edge.get("exposure_name", edge["exposure"]))
            await client.run(
                q.MERGE_RISK_FACTOR,
                disease_slug=dslug, exposure_slug=edge["exposure"], weight=edge.get("weight", 0.5),
            )
        for i, stage in enumerate(d.get("stages", [])):
            await client.run(q.MERGE_KB_STAGE, slug=stage, name=stage, order=i)
            await client.run(q.MERGE_HAS_STAGE, disease_slug=dslug, stage_slug=stage)

    for v in curated.get("vital_types", []):
        await client.run(q.MERGE_KB_VITALTYPE, slug=v["slug"], name=v["name"])
        for m in v.get("measures", []):
            await client.run(
                q.MERGE_MEASURED_BY,
                symptom_slug=m["symptom"], vital_slug=v["slug"], direction=m.get("direction", "positive"),
            )

    for alias, slug in load_curated_aliases():
        await client.run(q.MERGE_SYMPTOM_ALIAS, slug=slug, alias=[alias])


async def main() -> None:
    client = GraphClient.from_env()
    await client.apply_schema()
    await seed_graph(client)
    await client.close()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
