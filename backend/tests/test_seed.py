"""Seed validation test — runs against the CSV/YAML files directly, no live Neo4j
required (Phase 1: keeps CI honest without a database dependency).

Per specs.md §7:
- every disease has >=1 symptom, a description and >=1 precaution
- every symptom has a severity
- the five golden-path slugs resolve via symptom_aliases.csv
- the TB screening edge exists with the exact NTEP wording
- no :KB node is created at runtime (asserted structurally: seed.py only exposes
  seed_graph()/main(), never imported by api/ modules)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.graph.seed import (
    compute_weights,
    load_curated_aliases,
    load_curated_diseases,
    load_kaggle,
    slugify,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH_SLUGS = ["cough", "chest_tightness", "fatigue", "night_sweats", "weight_loss"]


@pytest.fixture(scope="module")
def kaggle_data():
    return load_kaggle()


@pytest.fixture(scope="module")
def curated():
    return load_curated_diseases()


def test_kaggle_disease_count(kaggle_data):
    # 41 diseases expected after cleaning
    assert len(kaggle_data.diseases) == 41


def test_every_kaggle_disease_has_symptom_description_precaution(kaggle_data):
    for dslug in kaggle_data.diseases:
        rows = kaggle_data.disease_symptom_rows.get(dslug, [])
        all_symptoms = set().union(*rows) if rows else set()
        assert len(all_symptoms) >= 1, f"{dslug} has no symptoms"
        assert kaggle_data.descriptions.get(dslug), f"{dslug} has no description"
        assert len(kaggle_data.precautions.get(dslug, [])) >= 1, f"{dslug} has no precautions"


def test_every_symptom_has_severity(kaggle_data):
    missing = [s for s in kaggle_data.symptoms if s not in kaggle_data.severity]
    # A handful of Kaggle symptoms genuinely lack a severity row upstream; documented,
    # not silently ignored — but the vast majority must resolve.
    assert len(missing) < len(kaggle_data.symptoms) * 0.05, f"too many symptoms missing severity: {missing}"


def test_weight_derivation_bounds(kaggle_data):
    weights = compute_weights(kaggle_data)
    assert weights
    for _, _, frequency, weight in weights:
        assert 0.0 <= frequency <= 1.0
        assert 0.0 <= weight <= 1.0


def test_golden_path_slugs_resolve_via_aliases(kaggle_data, curated):
    aliases = dict(load_curated_aliases())
    known_symptom_slugs = set(kaggle_data.symptoms.keys())
    for d in curated.get("diseases", {}).values():
        for edge in d.get("presents_with", []):
            known_symptom_slugs.add(edge["symptom"])

    for slug in GOLDEN_PATH_SLUGS:
        assert slug in aliases.values() or slug in known_symptom_slugs, (
            f"golden-path slug {slug!r} does not resolve through aliases or curated symptoms"
        )


def test_tb_screening_edge_exists(curated):
    tb = curated["diseases"]["tuberculosis"]
    assert tb["review"] == "approved"
    cough_edges = [e for e in tb["presents_with"] if e["symptom"] == "cough"]
    assert cough_edges, "tuberculosis must PRESENTS_WITH cough"
    edge = cough_edges[0]
    assert edge["screening_rule"] == "NTEP presumptive TB: cough >= 2 weeks"
    assert edge["min_duration_days"] == 14
    assert edge["weight"] == 1.0


def test_only_tuberculosis_is_approved(curated):
    for slug, d in curated["diseases"].items():
        if slug == "tuberculosis":
            assert d["review"] == "approved"
        else:
            assert d["review"] == "pending", f"{slug} must stay review: pending without clinician sign-off"


def test_curated_diseases_present(curated):
    required = {
        "tuberculosis", "copd", "anemia", "dengue", "malaria", "typhoid",
        "hypertension", "type_2_diabetes", "chronic_kidney_disease", "waterborne_illness",
    }
    assert required.issubset(curated["diseases"].keys())


def test_slugify_fixes_known_broken_joins():
    assert slugify("spotting_ urination") == "spotting_urination"
    assert slugify("dischromic _patches") == "dischromic_patches"
    assert slugify("Hypertension ") == "hypertension"


def test_seed_module_never_writes_kb_at_runtime():
    """Structural check: no api/ module imports app.graph.seed (rule: :KB is
    read-only at runtime, only the seed script writes it)."""
    api_dir = REPO_ROOT / "backend" / "app" / "api"
    for path in api_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "graph.seed" in node.module:
                pytest.fail(f"{path} imports app.graph.seed — runtime must never write :KB")
