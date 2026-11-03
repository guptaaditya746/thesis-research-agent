"""The four engine seams (stages.py): with none registered a run is byte-identical to before; a registered
stage can change what the engine records, in registration order."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from evidence import engine, stages
from evidence.plan import Plan, WordList
from evidence.tests.conftest import PROTOCOL, make_corpus

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden" / "regex_run_outputs.json"


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    stages.clear()
    yield
    stages.clear()


def _run(tmp_path: Path, strategy: str = "all", **kw) -> Path:
    corpus = make_corpus(tmp_path / "corpus")
    return engine.run(PROTOCOL, corpus, tmp_path / "runs", selection="regex-only", provider=None, strategy=strategy,
                      cache=tmp_path / "cache", **kw)


def _outputs(root: Path) -> dict[str, str]:
    return json.loads((root / "run.json").read_text(encoding="utf-8"))["outputs"]


@pytest.mark.parametrize("strategy", ["all", "gaps"])
def test_no_stages_run_is_byte_identical(tmp_path: Path, strategy: str) -> None:
    # golden hashes were recorded with the engine as it was before the seams (committed fixture)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))[strategy]
    root = _run(tmp_path, strategy)
    outputs = _outputs(root)
    assert outputs == golden
    from jsonio import sha256_hex
    for name, digest in outputs.items():
        assert sha256_hex((root / name).read_bytes()) == digest


def test_after_run_output_is_hashed(tmp_path: Path) -> None:
    stages.register("demo", "after_run", lambda run, plan: {"x": 1})
    root = _run(tmp_path)
    outputs = _outputs(root)
    assert "demo.json" in outputs
    assert json.loads((root / "demo.json").read_text(encoding="utf-8")) == {"x": 1}
    from jsonio import sha256_hex
    assert outputs["demo.json"] == sha256_hex((root / "demo.json").read_bytes())
    assert (root / "manifest.json").exists()


def test_stages_are_called_in_registration_order(tmp_path: Path) -> None:
    seen: list[str] = []
    for name in ("a", "b", "c"):
        stages.register(name, "before_extract", lambda doc, plan, n=name: seen.append(n))
    _run(tmp_path)
    assert seen[:3] == ["a", "b", "c"] and len(seen) == 15   # five documents


def test_after_type_changes_the_merged_items_and_after_document_adds_items(tmp_path: Path) -> None:
    base = _run(tmp_path / "base")
    n_base = len((base / "evidence.jsonl").read_text(encoding="utf-8").splitlines())
    calls: list[str] = []

    def drop_all(doc, etype, merged):
        calls.append(etype)
        return []

    stages.register("drop", "after_type", drop_all)
    root = _run(tmp_path / "dropped")
    assert calls and (root / "evidence.jsonl").read_text(encoding="utf-8").strip() == ""
    assert n_base > 0
    stages.clear()
    extra: list[int] = []
    stages.register("noop", "after_document", lambda doc: extra.append(1) or [])
    _run(tmp_path / "noop")
    assert len(extra) == 5


def test_plan_goes_to_before_extract_and_after_run(tmp_path: Path) -> None:
    from evidence.plan import write_plan
    plan = Plan(question="q", field="cs", lines=[], main_rule="r", decisions=[], clarifications=[],
                words=WordList(things={}, cues=[], written_by="test", ontology_names={}))
    path = tmp_path / "plan.json"
    write_plan(plan, path)
    got: list[object] = []
    stages.register("p", "before_extract", lambda doc, p: got.append(p))
    stages.register("r", "after_run", lambda run, p: got.append(p) or {})
    _run(tmp_path, plan=str(path))
    assert got[0] == plan and got[-1] == plan
