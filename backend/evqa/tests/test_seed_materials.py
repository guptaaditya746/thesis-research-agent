"""Domain-free data generation (Q4): seed build and bench read every domain word from the blueprint.

1. The effect-model formula evaluator gives the same floats as the Python expression and allows nothing else.
2. The medical set rebuilds byte for byte from the profile (questions + gold + manifest, wordings replayed).
3. The materials blueprint builds by code only: mean values without comparator, its own slot names and templates,
   no medical word in its questions.
4. seed/ code holds no medical words outside docstrings (reword.py and brief.py excepted, see the report).
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path

import pytest
from rdflib import Graph

from evqa.paths import BACKEND_EVQA, REPO, domain_dir
from evqa.seed import bench, build, check, profile, rebuild
from evqa.seed import questions as qs
from evqa.seed.build import EX

MAT = "materials"


# ---------------------------------------------------------------- 1. formula

def test_formula_matches_python_bit_for_bit() -> None:
    f = "emax * dose / (ed50 + dose) * (1 - exp(-week / tau)) * context_factor"
    for emax, ed50, dose, week, tau, cf in ((-1.3, 12, 20, 24, 6, 1.0), (0.8, 5, 10, 52, 10, 1.25)):
        env = dict(emax=emax, ed50=ed50, dose=dose, week=week, tau=tau, context_factor=cf)
        assert profile.evaluate(f, env) == emax * dose / (ed50 + dose) * (1 - math.exp(-week / tau)) * cf


@pytest.mark.parametrize("bad", ["__import__('os')", "x.real", "[1, 2]", "open('f')", "y"])
def test_formula_rejects_anything_but_arithmetic(bad: str) -> None:
    with pytest.raises(ValueError):
        profile.evaluate(bad, {"x": 1.0})


def test_medical_blueprint_gets_its_generator_from_the_profile() -> None:
    raw = {"domain": "medical"}
    assert profile.generator(raw)["factor"]["slot"] == "dose"
    assert "generator" in build.load_blueprint(MAT) and build.load_blueprint(MAT)["generator"]["factor"]["slot"] == \
        "temperature"
    with pytest.raises(ValueError, match="no generator"):
        profile.generator({"domain": "nowhere"})


# (2. medical byte identity removed 21 Nov 2026: medical is now the merge of two generated sets.)

# ---------------------------------------------------------------- 3. materials

@pytest.fixture(scope="module")
def mat_graph() -> Graph:
    return build.build(build.load_blueprint(MAT), rebuild.names_of(MAT))


@pytest.fixture(scope="module")
def mat_world(mat_graph) -> bench.World:
    return bench.World(MAT, g=rebuild.full(mat_graph), texts={}, seed_text=build.text(MAT, mat_graph))


def test_materials_rows_use_its_slots_and_mean_values(mat_graph) -> None:
    bp = build.load_blueprint(MAT)
    rows = build.rows(bp)
    gen = profile.Gen(bp)
    assert len(rows) == sum(sum(len(arm["temperatures"]) for arm in gen.arms(p)) * len(p["hours"])
                            * len(p["measures"]) for p in bp["papers"])
    assert all(r["comparator"] is None and r["statistic"] == "MeanValue" for r in rows)
    assert {"temperature", "hours", "state"} <= set(rows[0])
    assert (None, EX.comparator, None) not in mat_graph
    assert len(build.conflicts(bp)) == 2
    assert [r["value"] for r in rows] == [r["value"] for r in build.rows(build.load_blueprint(MAT))]


def test_materials_seed_passes_shapes_except_the_comparator_bound_conflict_rule(mat_graph) -> None:
    """shapes.ttl's conflict rule needs ex:comparator; mean values have none (see the Q4 report). Without the
    conflict links every other shape and the split check pass."""
    g = rebuild.full(mat_graph)
    assert not check.shapes(g)["conforms"]
    g.remove((None, EX.conflictsWith, None))
    assert check.shapes(g)["conforms"]
    assert check.split_overlap(g)["count"] == 0


def test_materials_bench_fills_its_quota_with_valid_gold(mat_world) -> None:
    quota = bench.quota_of(MAT)
    picked = bench.choose(mat_world, 20261122)
    rep = picked["report"]
    assert sum(rep[t]["total"] for t in bench.TYPES) == sum(quota.values())
    assert rep["effect"]["candidates"] == 0          # no comparator, so no effect questions
    for spec, g in picked["chosen"]:
        assert g["split"] == spec.split
        if spec.type in bench.NOT_REPORTED:
            assert g["row_ids"] == [] and g["answer"]["status"] == "not_reported"
        else:
            assert g["row_ids"] and all(mat_world.papers[f["paper"]]["split"] == spec.split
                                        for f in mat_world.facts if f["id"] in g["row_ids"])


def test_materials_questions_hold_no_medical_words(mat_world) -> None:
    picked = bench.choose(mat_world, 20261122)
    text = " ".join(s.text + json.dumps(g) for s, g in picked["chosen"]).lower()
    for word in ("placebo", " mg", "weeks", "drug", "dose", "patient", "hba1c", "metformin"):
        assert word not in text, word


def test_rebuild_writes_only_under_out(tmp_path: Path) -> None:
    assert rebuild.main([MAT, "--out", str(tmp_path), "--seed-only"]) == 0
    seed = tmp_path / (domain_dir(MAT) / "seed.ttl").relative_to(REPO)
    assert seed.is_file() and seed.read_text(encoding="utf-8").startswith("# Seed of the materials domain")
    assert rebuild.main(["medical", "--in-place"]) == 1      # a frozen set is never rebuilt in place


# ---------------------------------------------------------------- 4. no medical words in seed code

def _strings(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs]


@pytest.mark.parametrize("name", ["build.py", "questions.py", "bench.py", "profile.py", "rebuild.py"])
def test_seed_code_has_no_medical_words(name: str) -> None:
    words = ("placebo", "hba1c", "metformin", "drug", "dose", "week", "patient", " mg", "medical")
    hits = [s for s in _strings(BACKEND_EVQA / "seed" / name) if any(w in s.lower() for w in words)]
    assert hits == [], hits
