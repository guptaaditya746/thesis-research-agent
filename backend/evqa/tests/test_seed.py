"""S1: the seed is built by code, and the three checks (shapes, name clashes, split overlap) catch broken seeds."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import threading
import time
from decimal import Decimal
from pathlib import Path

import pytest
from rdflib import Graph, Literal
from rdflib.namespace import SKOS

from evqa import llm
from evqa.paths import BACKEND_EVQA, SCHEMA, VOCAB, domain_dir
from evqa.seed import build, check, names, view
from evqa.seed.build import D, EX, SOSA

NAMES = json.loads((domain_dir("medical") / "names.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bp() -> dict:
    return build.load_blueprint("medical")


def graph(bp: dict) -> Graph:
    g = build.build(bp, NAMES)
    g.parse(SCHEMA / "glue.ttl")
    for f in VOCAB.glob("*.ttl"):
        g.parse(f)
    return g


def test_good_seed_passes_all_checks(bp: dict) -> None:
    g = graph(bp)
    assert check.shapes(g)["conforms"]
    assert check.split_overlap(g)["count"] == 0


def test_values_are_deterministic_and_rounded(bp: dict) -> None:
    a, b = build.rows(bp), build.rows(copy.deepcopy(bp))
    assert [r["value"] for r in a] == [r["value"] for r in b]
    assert len(a) == sum(sum(len(arm["doses"]) for arm in build.arms(p)) * len(p["weeks"]) * len(p["measures"])
                         for p in bp["papers"])
    hba1c = [r for r in a if r["measure"] == "hba1c_change"]
    assert all(r["value"].as_tuple().exponent == -2 for r in hba1c)


def test_adding_a_paper_keeps_other_values(bp: dict) -> None:
    more = copy.deepcopy(bp)
    more["papers"].append({**bp["papers"][0], "id": "P-med-99"})
    before = {r["id"]: r["value"] for r in build.rows(bp)}
    after = {r["id"]: r["value"] for r in build.rows(more)}
    assert all(after[k] == v for k, v in before.items())


def test_old_papers_keep_their_values(bp: dict) -> None:
    """P-med-01..05 values did not move when P-med-06..20 were added (21 Nov): sha256 of the 50 old (id, value)."""
    v = {r["id"]: str(r["value"]) for r in build.rows(bp)}
    old = sorted((k, x) for k, x in v.items() if k < "R-med-06")
    assert len(old) == 50 and (v["R-med-01-01"], v["R-med-01-02"]) == ("-0.46", "-0.57")
    digest = hashlib.sha256(json.dumps(old).encode()).hexdigest()
    assert digest == "5d38b77c312b5da9782e8514cb7fbbd0e177adaec48c693fe0cd108261a40deb"


def test_conflicts_must_be_declared_and_clear(bp: dict) -> None:
    pairs = build.conflicts(bp)
    assert ("R-med-06-04", "R-med-08-01") in pairs and len(pairs) == 6
    undeclared = copy.deepcopy(bp)
    for p in undeclared["papers"]:
        p.pop("conflict_with", None)
    with pytest.raises(ValueError, match="declare conflict_with"):
        build.conflicts(undeclared)
    rows = build.rows(bp)
    twin = next(r for r in rows if r["id"] == "R-med-06-04")
    close = [{**r, "value": twin["value"] + Decimal("0.02")} if r["id"] == "R-med-08-01" else r for r in rows]
    with pytest.raises(ValueError, match="too small"):
        build.conflicts(bp, close)


def test_shapes_catch_a_false_conflict(bp: dict) -> None:
    g = graph(bp)
    assert (D["R-med-06-04"], EX.conflictsWith, D["R-med-08-01"]) in g
    g.add((D["R-med-01-01"], EX.conflictsWith, D["R-med-01-02"]))
    g.add((D["R-med-01-02"], EX.conflictsWith, D["R-med-01-01"]))
    assert not check.shapes(g)["conforms"]


def test_multi_arm_and_active_comparator_rows(bp: dict) -> None:
    rows = {r["id"]: r for r in build.rows(bp)}
    assert [rows[f"R-med-11-0{i}"]["subject"] for i in (1, 2, 3)] == ["drug_d", "drug_e", "drug_f"]
    assert rows["R-med-12-01"]["comparator"] == "sitagliptin"


def test_shapes_catch_missing_comparator(bp: dict) -> None:
    g = graph(bp)
    g.remove((D["R-med-01-01"], EX.comparator, None))
    assert not check.shapes(g)["conforms"]


def test_shapes_catch_wrong_unit(bp: dict) -> None:
    g = graph(bp)
    value = g.value(D["R-med-01-01"], SOSA.hasResult)
    g.set((value, build.QUDT.unit, build.UNIT.PERCENT))
    assert not check.shapes(g)["conforms"]


def test_shapes_catch_duplicate_fact(bp: dict) -> None:
    g = graph(bp)
    for p, o in list(g.predicate_objects(D["R-med-01-01"])):
        g.add((D["R-copy"], p, o))
    report = check.shapes(g)
    assert not report["conforms"] and "same fact" in report["report"]


def test_split_check_catches_shared_drug(bp: dict) -> None:
    leaky = copy.deepcopy(bp)
    practice = next(p for p in leaky["papers"] if p["split"] == "practice")
    practice["drug"] = "drug_a"
    assert check.split_overlap(graph(leaky))["count"] == 1


INDEX = {"metformin": ("Metformin", "mesh:D008687"), "penoxalin": ("Penoxalin", "chebi:83569"),
         "placebos": ("Placebos", "mesh:D010919")}


def test_names_reject_real_and_close_labels() -> None:
    assert not names.judge("metformin", INDEX, [])["ok"]
    assert not names.judge("metformine", INDEX, [])["ok"]          # one letter more
    assert not names.judge("Velo-Trazin", INDEX, [])["ok"]         # not lower-case letters
    assert not names.judge("brenoxalin", INDEX, ["brenoxalim"])["ok"]   # close to our own
    assert names.judge("kavolemin", INDEX, ["brenoxalin"])["ok"]


def test_code_name_shape() -> None:
    assert names.code_name("brenoxalin") == names.code_name("brenoxalin")
    assert names.code_name("brenoxalin").startswith("BRN-")


class FakeLM:
    model = "fake"

    def __init__(self) -> None:
        self.calls = 0
        self.running = 0
        self.peak = 0
        self.lock = threading.Lock()

    def __call__(self, system: str, user: str, schema: dict) -> dict:
        with self.lock:
            self.calls += 1
            self.running += 1
            self.peak = max(self.peak, self.running)
        time.sleep(0.05)
        with self.lock:
            self.running -= 1
        kind = json.loads(user)["kind"]
        pool = {"a": ["metformin", "brenoxalin"], "b": ["kavolemin"], "c": ["veloranide"]}[kind]
        return {"output": {"names": (pool * 8)[:8]}}


def test_invent_skips_clashes_caches_and_caps_workers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "LLM_LOG", tmp_path / "log.jsonl")
    lm = FakeLM()
    slots = {"drug_a": "a", "drug_b": "b", "drug_c": "c"}
    out = names.invent(lm, slots, INDEX)
    assert [s["name"] for s in out["slots"].values()] == ["brenoxalin", "kavolemin", "veloranide"]
    assert out["slots"]["drug_a"]["checked"][0]["ok"] is False      # metformin was seen and rejected
    calls = lm.calls
    names.invent(lm, slots, INDEX)
    assert lm.calls == calls                                        # second run comes from the cache
    assert len((tmp_path / "log.jsonl").read_text().splitlines()) == calls
    assert llm.pmap(lambda x: x, range(10), workers=10) == list(range(10))


def test_pool_never_exceeds_three(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "LLM_LOG", tmp_path / "log.jsonl")
    lm = FakeLM()
    llm.pmap(lambda i: llm.call(lm, "s", json.dumps({"kind": "a", "i": i}), {}, step="t"), range(9), workers=9)
    assert lm.peak <= 3


def test_view_of_the_checked_in_seed() -> None:
    if not (domain_dir("medical") / "seed.ttl").is_file():
        pytest.skip("seed not built")
    o = view.overview("medical")
    assert len(o["rows"]) == sum(p["rows"] for p in o["papers"])
    assert any(f["path"].endswith("seed.ttl") for f in view.tree())
    with pytest.raises(KeyError):
        view.read_file("pyproject.toml")


def test_seed_wall() -> None:
    """Pipeline steps may not import the seed or eval, nor name the seed folder."""
    for step in ("spec", "find", "extract", "answer", "baselines"):
        folder = BACKEND_EVQA / step
        for f in folder.rglob("*.py") if folder.is_dir() else []:
            text = f.read_text(encoding="utf-8")
            assert "data/seed" not in text and "SEED" not in text, f
            for node in ast.walk(ast.parse(text)):
                mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                        else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                assert not any(m.startswith(("evqa.seed", "evqa.eval")) for m in mods), f


def test_checked_in_names_have_no_problems() -> None:
    data = json.loads((domain_dir("medical") / "names.json").read_text(encoding="utf-8"))
    for slot in data["slots"].values():
        assert slot["checked"][-1]["ok"] and slot["checked"][-1]["name"] == slot["name"]
    g = Graph().parse(domain_dir("medical") / "seed.ttl")
    made_up = {str(o) for s in g.subjects(EX.madeUp, Literal(True)) for o in g.objects(s, SKOS.prefLabel)}
    assert made_up == {s["name"] for s in data["slots"].values()}
