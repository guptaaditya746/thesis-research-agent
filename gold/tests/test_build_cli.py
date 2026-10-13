"""`gold build | triage | pool | draft | status` end to end, with the scripted model in place of LiteLLM."""
from __future__ import annotations

import json

import pytest

from agent.canonical import write_json
from gold import build_cli, cli
from gold.build import QuestionDir, read_jsonl

from .scripted import Script, corpus, table_concept


@pytest.fixture
def env(tmp_path, monkeypatch):
    c = corpus(tmp_path)
    concepts = tmp_path / "concepts" / "q01"
    concepts.mkdir(parents=True)
    write_json(concepts / "concept.json", table_concept())
    write_json(concepts / "session.json", {"question": "Which benchmarks do the RAG papers evaluate on?"})
    monkeypatch.setenv("CORPUS", str(c.root))
    monkeypatch.setenv("CONCEPTS", str(tmp_path / "concepts"))
    monkeypatch.setenv("GOLD", str(tmp_path / "gold"))
    monkeypatch.setenv("GOLD_CONCURRENCY", "3")
    script = Script()
    seen = []

    def rotation(args):
        seen.append(args.models)
        return script.rotation()

    monkeypatch.setattr(build_cli, "_rotation", rotation)
    return {"gold": tmp_path / "gold", "script": script, "models": seen}


def test_the_whole_c1_pipeline_from_the_command_line(env, capsys):
    assert cli.main(["build", "q01", "--only-papers", "p3,p5,p6"]) == 0
    qdir = QuestionDir(env["gold"] / "q01")
    doc = json.loads(qdir.doc.read_text(encoding="utf-8"))
    assert doc["question"] == "Which benchmarks do the RAG papers evaluate on?"
    settings = doc["built"]["settings"]
    assert settings["concurrency"] == 3 and settings["only_papers"] == ["p3", "p5", "p6"]
    assert env["models"] == ["sub-model-1,sub-model-2"]
    assert cli.main(["triage", "q01"]) == 0
    assert cli.main(["pool", "q01", "--sample", "1", "--seed", "7"]) == 0
    assert json.loads(qdir.strata.read_text(encoding="utf-8"))["seed"] == "7"
    assert cli.main(["draft", "q01"]) == 0
    assert len(read_jsonl(qdir.pool)) == 6
    capsys.readouterr()
    assert cli.main(["status"]) == 0
    line = capsys.readouterr().out.strip()
    assert line.startswith("q01") and "done" in line and "triage answers 4" in line and "draft 3 rows" in line
    assert cli.main(["status", "q01", "--json"]) == 0
    found = json.loads(capsys.readouterr().out)
    assert found[0]["coverage"]["relevant"] == 3 and found[0]["pool"]["records"] == 6


def test_build_exits_1_while_calls_failed(env):
    env["script"].fail = lambda stage, paper, part: stage == "screen" and paper == "p5" and part == 2
    assert cli.main(["build", "q01", "--only-papers", "p5"]) == 1
    env["script"].fail = None
    assert cli.main(["build", "q01", "--only-papers", "p5"]) == 0


def test_build_without_a_concept_says_what_to_do(env):
    with pytest.raises(SystemExit, match="no concept"):
        cli.main(["build", "q09"])


def test_status_of_an_empty_gold_root(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("GOLD", str(tmp_path / "nothing"))
    assert cli.main(["status"]) == 0
    assert "no gold folders" in capsys.readouterr().out
