"""Evaluation reads the corpus, not synth (plan 2 Task 12): the truth's own `types`, a name table built from the
ground truth (`Canon.from_truth`), the expected answer's spec from the domain's effect protocol, and no synth import.

The RAG scores staying unchanged is guarded by the golden tests of test_score_kinds.py (preflight P17)."""
from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from evaluation.canon import Canon
from evaluation.expected import effect_spec
from evaluation.truth import MAIN_ROLE, TYPES, GroundTruth
from evidence import contract
from evidence import protocol as protocol_module

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"
# A template-built drugtoy corpus (synth build --domain drugtoy --root evidence/tests/fixtures --seed 1 --studies 6
# --levels explicit --preset builds_on): S003 and S006 write Zelvora by its code name ZV-604, S004 Quintapride as
# QT-737, S002 Morvectin as "MV" (hereafter); S001 and S004 write Zelvora plainly.
DRUG_GT = DATA / "drugtoy" / "ground_truth.json"
FIXTURES = ROOT / "evidence" / "tests" / "fixtures"
MIXED = ROOT / "tests" / "EV2" / "corpora" / "rag-claude-s1-mixed" / "ground_truth.json"
# The modules Task 12 makes stand on their own (preflight P15; evaluation/review.py reads synth's review sheet on
# purpose and is not one of them).
CHANGED = ("evaluation.truth", "evaluation.canon", "evaluation.score", "evaluation.expected",
           "evaluation.baselines.common", "evaluation.baselines.rag", "evaluation.baselines.agent")


@pytest.fixture(autouse=True)
def _registry() -> Iterator[None]:
    """Each test leaves the evidence-type registry as it found it (loading the drugtoy protocol registers its types,
    and another test's pack uses the same type names with other prefixes)."""
    before = dict(contract.ITEM_PREFIX)
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def imported_modules(package: str) -> set[str]:
    """Every module a fresh interpreter has loaded after importing `package`'s changed modules (CHANGED)."""
    code = ("import importlib, json, sys\n"
            f"for name in {[m for m in CHANGED if m.startswith(package)]!r}:\n"
            "    importlib.import_module(name)\n"
            "print(json.dumps(sorted(sys.modules)))\n")
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
    return set(json.loads(done.stdout.strip().splitlines()[-1]))


def test_canon_built_from_truth_knows_name_variants():
    c = Canon.from_truth(GroundTruth.load(DRUG_GT))
    assert c.domain == "drugtoy"                                   # corpus.json recipe.domain
    assert c.key("condition", "ZV-604") == c.key("condition", "Zelvora") == "Zelvora"
    assert c.key("condition", "qt-737") == c.key("condition", "Quintapride") == "Quintapride"
    assert c.key("condition", "MV") == "Morvectin"                 # hereafter: the alias it stands for
    assert c.key("condition", "  zv-604 ") == "Zelvora"
    assert c.key("condition", "Avelumab") is None
    assert c.key("metric", "responder proportion") == "responder proportion"   # no recipe under domains/: as truth
    assert c.key("dataset", "older adults") == "older adults"


def test_canon_reads_the_domain_recipe_as_data():
    """With the drugtoy recipe in reach, its synonyms and metric forms join the keys, and the truth's variants map to
    the recipe's labels."""
    c = Canon.from_truth(GroundTruth.load(DRUG_GT), root=FIXTURES)
    assert c.key("condition", "oral kinase blocker") == c.key("condition", "ZV-604") == "Zelvora"
    assert c.key("metric", "RP") == c.key("metric", "proportion of patients counted as responders") == \
        "responder proportion"
    assert c.question_canonicals == {"response_rate"}


def test_canon_of_an_old_rag_corpus_is_the_recipes():
    """Old ground truth carries no synonym, abbreviation, description or kind: those come from domains/rag."""
    truth = GroundTruth.load(MIXED)
    c = Canon.from_truth(truth)
    assert truth.domain is None and c.domain == "rag"
    assert c.key("metric", "AA") == "answer accuracy"
    assert c.key("condition", "model that answers from its own parameters") == "closed-book model"
    assert c.key("condition", "B") is None                        # paper-local codes are never keys
    assert c.kind_of("RAG pipeline") == "rag" and c.kind_of("vanilla LLM") == "no-retrieval"
    assert c.question_canonicals == {"factual_accuracy", "hallucination_rate"}


def test_truth_reads_its_own_types():
    drug = GroundTruth.load(DRUG_GT)
    assert set(drug.types) >= {"limitation", "dependency", "study_label"} and "dataset" not in drug.types
    assert drug.main_role["limitation"] == "limitation" and drug.main_role["dependency"] == "dependency"
    limits = drug.of("S002", "limitation")
    assert [f.data["category"] for f in limits] == ["side_effects", "short_follow_up"]
    assert [f.id for f in drug.of("S003", "dependency")] == ["S003.d1"]
    assert [f.data["label"] for f in drug.of("S001", "study_label")] == ["Brekkan et al. (2006)"]
    rag = GroundTruth.load(MIXED)
    assert rag.types == TYPES and rag.main_role == MAIN_ROLE


def test_expected_spec_is_the_domains_effect_protocol():
    rag = protocol_module.load(ROOT / "domains" / "rag" / "protocols" / "rag-factuality.yaml").synthesis
    assert effect_spec("rag") == rag
    drug = protocol_module.load(FIXTURES / "drugtoy" / "protocols" / "drugtoy-response.yaml", FIXTURES).synthesis
    assert effect_spec("drugtoy", FIXTURES) == drug


def test_evaluation_does_not_import_synth():
    assert "synth" not in {m.split(".")[0] for m in imported_modules("evaluation")}
