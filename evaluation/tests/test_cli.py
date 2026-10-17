"""`evaluate` end to end on the hand corpus: score, rag-baseline, agent-baseline, compare."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation import cli

from . import fixtures as fx
from .agentic_fakes import FakeRunner
from .helpers import Scripted
from .test_agent_baseline import MAPPED, agent_record


CITED = {"answer_text": "Retrieval helped in S001 and hurt in S002.", "citations": []}


@pytest.fixture
def scripted(monkeypatch: pytest.MonkeyPatch) -> Scripted:
    """The RAG baseline's answering call (its prompt lists passages) and the mapping call of both baselines."""
    model = Scripted(lambda prompt: CITED if "\n\nPassages:\n\n" in prompt else MAPPED)
    monkeypatch.setattr(cli, "_model", lambda alias: (model.model(alias), alias))
    return model


def test_score_and_compare(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    run = fx.write_run(tmp_path / "runs", list(fx.perfect_items().values()), fx.engine_answer(fx.perfect_items()))
    fx.dump(tmp_path / "rag.json", fx.baseline_answer("rag-baseline", {"S001": "supports"}, "supported"))
    assert cli.main(["score", "--run", str(run), "--corpus", str(corpus), "--baseline", str(tmp_path / "rag.json"),
                     "--out", str(tmp_path / "out")]) == 0
    report = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert [s["system"] for s in report["synthesis"]] == ["evidence-engine", "rag-baseline"]
    assert "## A. Extraction" in (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert cli.main(["score", "--corpus", str(corpus), "--baseline", str(tmp_path / "rag.json"),
                     "--out", str(tmp_path / "only")]) == 0
    assert cli.main(["compare", str(tmp_path / "out"), str(tmp_path / "only" / "report.json"),
                     "--out", str(tmp_path / "cmp")]) == 0
    rows = json.loads((tmp_path / "cmp" / "compare.json").read_text(encoding="utf-8"))["rows"]
    assert {r["system"] for r in rows} == {"evidence-engine", "rag-baseline"} and rows[0]["level"] == "mixed"


def test_shift_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from .test_shift import VARIANT, corpora

    base, variant = corpora(tmp_path)
    for idx, (corpus, s2, label) in enumerate(((base, "contradicts", "mixed"), (variant, "supports", "supported"))):
        fx.dump(tmp_path / f"engine-{idx}.json", fx.baseline_answer("evidence-engine", {"S001": "supports", "S002": s2}, label))
        assert cli.main(["score", "--corpus", str(corpus), "--baseline", str(tmp_path / f"engine-{idx}.json"),
                         "--out", str(tmp_path / f"report-{idx}")]) == 0
    fx.dump(tmp_path / "variant.json", VARIANT)
    assert cli.main(["shift", "--base", str(tmp_path / "report-0"), "--variant", str(tmp_path / "report-1" / "report.json"),
                     "--variant-json", str(tmp_path / "variant.json"), "--out", str(tmp_path / "shift")]) == 0
    result = json.loads((tmp_path / "shift" / "shift.json").read_text(encoding="utf-8"))
    assert result["systems"][0]["shifted_as_expected"] is True
    assert "evidence-engine=yes" in capsys.readouterr().out
    assert "# Shift from base to base-cf-S002-supports" in (tmp_path / "shift" / "shift.md").read_text(encoding="utf-8")
    with pytest.raises(SystemExit, match="base corpus id"):
        cli.main(["shift", "--base", str(tmp_path / "report-1"), "--variant", str(tmp_path / "report-0"),
                  "--variant-json", str(tmp_path / "variant.json"), "--out", str(tmp_path / "shift2")])


def test_benchmark_command(tmp_path: Path) -> None:
    from .test_benchmark import add_calls

    corpus = fx.write_corpus(tmp_path)
    run = fx.write_run(tmp_path / "runs", list(fx.perfect_items().values()), fx.engine_answer(fx.perfect_items()))
    add_calls(run)
    assert cli.main(["score", "--run", str(run), "--corpus", str(corpus), "--out", str(tmp_path / "out")]) == 0
    assert cli.main(["benchmark", str(tmp_path / "out"), str(tmp_path / "out" / "report.json"),
                     "--out", str(tmp_path / "bench")]) == 0
    record = json.loads((tmp_path / "bench" / fx.REGEX / "benchmark.json").read_text(encoding="utf-8"))
    assert record["cost"]["calls"] == 8 and len(record["corpora"]) == 2   # the same report twice: pooled twice
    assert (tmp_path / "bench" / "benchmark.md").is_file()
    fx.dump(tmp_path / "rag.json", fx.baseline_answer("rag-baseline", {"S001": "supports"}, "supported"))
    assert cli.main(["score", "--corpus", str(corpus), "--baseline", str(tmp_path / "rag.json"), "--out", str(tmp_path / "only")]) == 0
    with pytest.raises(SystemExit, match="no report has an `extractors` section"):
        cli.main(["benchmark", str(tmp_path / "only"), "--out", str(tmp_path / "bench2")])


def test_rag_baseline_command(tmp_path: Path, scripted: Scripted) -> None:
    corpus = fx.write_corpus(tmp_path)
    assert cli.main(["rag-baseline", "--corpus", str(corpus), "--out", str(tmp_path / "rag"), "--k", "2"]) == 0
    answer = json.loads((tmp_path / "rag" / "answer.json").read_text(encoding="utf-8"))
    assert answer["system"] == "rag-baseline" and len(answer["retrieved"]) == 2 and answer["label"] == "mixed"
    assert answer["settings"] == {"retrieval": "global", "k": 2, "max_chars": 1500, "retriever": "bm25okapi"}
    assert answer["model_call"]["model"] == answer["mapping_call"]["model"] == cli.DEFAULT_ALIAS == "orch-model"
    assert (tmp_path / "rag" / "rag-baseline-calls.jsonl").is_file()
    assert cli.parser().parse_args(["rag-baseline", "--corpus", "c", "--out", "o"]).retrieval == "global"


def test_agent_baseline_command(tmp_path: Path, scripted: Scripted, monkeypatch: pytest.MonkeyPatch) -> None:
    import agent.cli
    import evidence.agentic.runner as runner

    made: list[dict] = []

    def fake_runner(settings, work_dir=None):  # noqa: ANN001, ANN202
        made.append({"settings": settings, "work_dir": work_dir})
        return FakeRunner(agent_record())

    monkeypatch.setattr(agent.cli, "stop_on_sigterm", lambda: None)
    monkeypatch.setattr(runner, "ResearchAgentRunner", fake_runner)
    corpus = fx.write_corpus(tmp_path)
    assert cli.main(["agent-baseline", "--corpus", str(corpus), "--out", str(tmp_path / "ag"), "--sandbox",
                     "unsandboxed", "--steps", "5", "--model", "sub-model-2"]) == 0
    answer = json.loads((tmp_path / "ag" / "answer.json").read_text(encoding="utf-8"))
    assert answer["system"] == "agent-baseline" and answer["label"] == "mixed"
    assert made[0]["settings"].sandbox_mode == "unsandboxed"
    assert made[0]["settings"].model == "sub-model-2" == answer["mapping_call"]["model"]  # --model reaches the agent
    assert cli.parser().parse_args(["agent-baseline", "--corpus", "c", "--out", "o"]).model == "orch-model"
