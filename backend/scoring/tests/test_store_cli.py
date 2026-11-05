"""`score store` and `score sparql`: every graph.ttl below a runs root, queried per run or across runs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import kg, prov
from agent.tests.runs import Built, corpus_env, research, rows  # noqa: F401  (pytest fixtures)
from scoring.cli import main as cli
from scoring.store import RunStore

from .test_store import Q, make_run


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    make_run(runs / "m4-72", "a")  # a batch's runs root inside $RUNS
    make_run(runs, "b")
    make_run(runs / ".jobs", "hidden")  # hidden directories are not searched
    make_run(runs / "c", "nested")  # c is a run directory (config.json): not searched below
    (runs / "c" / "config.json").write_text("{}", encoding="utf-8")
    make_run(runs / "m4-73", "a")  # a second run with id a: reported, not loaded over the first
    return runs


def test_store_loads_the_tree_and_sparql_queries_it(tree: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = tmp_path / "store"
    assert cli(["store", str(tree), "--path", str(store)]) == 0
    out = capsys.readouterr().out
    assert "2 runs with graph.ttl, 2 (re)loaded" in out and f"skipped {tree / 'm4-73' / 'a'}" in out
    query = tmp_path / "q.rq"
    query.write_text(Q, encoding="utf-8")
    assert cli(["sparql", str(query), "--run", "a", "--path", str(store)]) == 0
    assert json.loads(capsys.readouterr().out) == {"vars": ["c"], "rows": [{"c": "urn:thesis-agent:run:a/claim/claim-000001"}]}
    assert cli(["sparql", str(query), "--path", str(store)]) == 0
    assert len(json.loads(capsys.readouterr().out)["rows"]) == 2
    query.write_text("DELETE WHERE { ?s ?p ?o }", encoding="utf-8")
    assert cli(["sparql", str(query), "--path", str(store)]) == 1
    assert "only SELECT" in capsys.readouterr().out


def test_default_path_is_under_runs(tree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("RUNS", str(tree))
    assert cli(["store", str(tree)]) == 0
    assert cli(["store", str(tree)]) == 0  # unchanged graphs are not reloaded
    assert "2 runs with graph.ttl, 0 (re)loaded" in capsys.readouterr().out.splitlines()[-1]
    assert RunStore(tree / ".oxigraph").runs() == ["a", "b"]


def test_a_real_run_export(research: Built, tmp_path: Path) -> None:
    kg.write(research.run, research.manifest)
    prov.write(research.run)
    store = RunStore(tmp_path / "store")
    assert store.load_tree(research.run.root.parent)["loaded"] == ["research-r1"]
    found = store.query(f"PREFIX oa: <{prov.OA}> SELECT ?exact WHERE {{ ?s oa:exact ?exact }} ORDER BY ?exact",
                        run_id="research-r1")
    accepted = sorted(r["used"]["anchor"]["exact"] for r in rows(research.run.claims) if r["status"] == "accepted")
    assert [r["exact"] for r in found["rows"]] == accepted and len(accepted) == 6
