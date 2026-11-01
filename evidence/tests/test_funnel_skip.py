"""Skipped (unavailable) extractors in the funnel: same-round fall-through, replay, scoring, and the latency wording
shared by the abbrev and GLiNER metric extractors."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from agent.anchor import Index, text_sha256
from evaluation import cli
from evidence import engine, extractors, protocol, replay
from evidence.calls import EngineContext, NotRecorded
from evidence.contract import DocumentRef, ExtractionTask, ProtocolRef
from evidence.extractors import gliner

from .conftest import PROTOCOL, corpus_of, pack_words
from .fake_gliner import FakeGliner

PROTOCOLS = PROTOCOL.parent
EXAMPLE = Path(__file__).resolve().parents[2] / "synth" / "examples" / "rag-demo-explicit"
TEXT = ("# Study\n\nWe compare a closed-book baseline (B) with its retrieval-augmented variant (R). We report "
        "factual accuracy (FA).\n\n## Results\n\n| System | Dataset | FA (%) |\n|---|---|---|\n| B | NQ | 60.0 |\n| R | NQ | 70.0 |\n")


@pytest.fixture(autouse=True)
def no_gliner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GLINER_URL", raising=False)
    gliner.forget()


def test_rag_latency_steps_share_the_latency_wording() -> None:
    p = protocol.load(PROTOCOLS / "rag-latency.yaml")
    steps = {r.name: r.config for r in p.evidence_types["metric"].extractors}
    assert steps["abbrev_metric"]["metrics"] == steps["gliner_metric"]["metrics"] == steps["regex_metric"]["metrics"]
    by_name = {r.name: r.config for r in p.evidence_types["measurement"].extractors}
    assert by_name["regex_measurement_units"] == by_name["number_measurement"]
    assert by_name["number_measurement"]["fraction_metrics"] == ["factual_accuracy", "hallucination_rate"]


def metric_config(name: str) -> dict[str, Any]:
    spec = protocol.load(PROTOCOLS / "rag-latency.yaml").evidence_types["metric"]
    ref = next(r for r in spec.extractors if r.name == name)
    return {**pack_words(name, "metric"), **ref.config, "evidence_type": "metric", "field_schema": spec.fields, "roles": list(spec.roles)}


def extract(extractor: Any, text: str) -> Any:
    doc = DocumentRef(id="P", file="papers/P.md", sha256=text_sha256(text))
    task = ExtractionTask(protocol=ProtocolRef(id="x", sha256="0" * 64), evidence_type="metric",
                          field_schema_sha256="x", document=doc)
    return extractor.extract(task, EngineContext(text, Index(text), [], {}, None))


def test_abbrev_metric_names_a_defined_latency_with_the_protocols_wording() -> None:
    text = "We measure the response latency (RL) of each system. RL is lower for B.\n"
    result = extract(extractors.get("abbrev_metric", metric_config("abbrev_metric")), text)
    assert [i.fields["canonical"] for i in result.items] == ["latency"], result.items


def test_gliner_metric_takes_the_protocols_metric_wording() -> None:
    text = "We report latency (Lat.) of each system.\n"
    with FakeGliner(patterns={"evaluation metric": [(r"latency \(Lat\.\)", 0.9)]}) as server:
        cfg = {**metric_config("gliner_metric"), gliner.URL_KEY: server.url}
        result = extract(extractors.get("gliner_metric", cfg), text)
        plain = extractors.get("gliner_metric", {**pack_words("gliner_metric", "metric"), "evidence_type": "metric",
                                                 gliner.URL_KEY: server.url})   # the pack's wording only
        assert plain.spec.extractor_id != extractors.get("gliner_metric", cfg).spec.extractor_id
    assert [i.fields["canonical"] for i in result.items] == ["latency"], result


def run_gaps(tmp_path: Path, steps: list[Any], name: str, gliner_url: str | None = None) -> Path:
    proto = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    proto["evidence_types"]["metric"]["extractors"] = steps
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(proto, sort_keys=False), encoding="utf-8")
    settings = engine.Settings(corpus=str(corpus_of(tmp_path / f"corpus-{name}", {"P1": TEXT})),
                               cache=str(tmp_path / f"cache-{name}"), strategy="gaps", gliner_url=gliner_url)
    return engine.execute_run(path.read_bytes(), settings, tmp_path / f"runs-{name}", provider=None)


def events_of(run: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def rounds(run: Path) -> tuple[list[Any], int]:
    funnel = json.loads((run / "funnel.json").read_text(encoding="utf-8"))
    steps = sorted({s["round"] for d in funnel["documents"].values() for s in d["steps"]})
    return steps, sum(e["subtype"] == "completeness" for e in events_of(run))


def test_a_skipped_position_falls_through_in_the_same_round(tmp_path: Path) -> None:
    with_skip = run_gaps(tmp_path, [{"name": "gliner_metric"}, {"name": "regex_metric"}], "a")
    without = run_gaps(tmp_path, [{"name": "regex_metric"}], "b")
    assert rounds(with_skip) == rounds(without)
    assert sum(e["status"] == "skipped" for e in events_of(with_skip) if e["subtype"] == "extractor_call") == 1


def test_gliner_answering_info_but_failing_predict_is_an_error_and_falls_through(tmp_path: Path) -> None:
    with FakeGliner(delay=1.0) as server:
        steps = [{"name": "gliner_metric", "config": {"timeout": 0.3}}, {"name": "regex_metric"}]
        run = run_gaps(tmp_path, steps, "c", gliner_url=server.url)
    calls = [(e["agent_id"].split("@")[0], e["status"]) for e in events_of(run)
             if e["subtype"] == "extractor_call" and e["custom_metadata"]["evidence_type"] == "metric"]
    assert calls == [("gliner_metric", "error"), ("regex_metric", "ok")]
    assert json.loads((run / "answer.json").read_text(encoding="utf-8"))


def test_replay_of_a_recorded_gliner_call_whose_record_is_gone_raises(tmp_path: Path) -> None:
    with FakeGliner() as server:
        run = run_gaps(tmp_path, [{"name": "gliner_metric"}, {"name": "regex_metric"}], "d", gliner_url=server.url)
    assert ("gliner_metric", "ok") in [(e["agent_id"].split("@")[0], e["status"]) for e in events_of(run)
                                        if e["subtype"] == "extractor_call"]
    _, check = replay.replay(run)   # the service is gone: the recorded call replays from the cache
    assert check["ok"], check
    cache = tmp_path / "cache-d" / "extractor_calls.jsonl"
    kept = [x for x in cache.read_text(encoding="utf-8").splitlines() if "gliner_metric" not in x]
    cache.write_text("\n".join(kept) + "\n", encoding="utf-8")
    with pytest.raises(NotRecorded):
        replay.replay(run)


def test_a_run_with_gliner_off_has_no_gliner_row_in_the_per_extractor_scores(tmp_path: Path) -> None:
    run = engine.run(PROTOCOLS / "rag-factuality-funnel.yaml", EXAMPLE, tmp_path / "runs", selection="cascade",
                     provider=None, strategy="all")
    assert cli.main(["score", "--run", str(run), "--corpus", str(EXAMPLE), "--out", str(tmp_path / "out")]) == 0
    report = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    ext = report["extractors"]
    assert "regex_metric" in {r["extractor"].split("@")[0] for r in ext["rows"]}
    for part in (ext["rows"], ext["papers"]):
        assert not [r for r in part if r["extractor"].startswith("gliner_")]
