"""The GLiNER client extractors (gliner_condition, gliner_metric, gliner_dataset) against the in-process stand-in
server (fake_gliner.py): items and roles, offsets across chunks, recorded calls and the id, a service that is
down, slow or not configured."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from agent.anchor import Index, text_sha256
from jsonio import file_sha256
from evidence import engine, protocol, seal
from evidence.calls import EngineContext
from evidence.contract import DocumentRef, ExtractionTask, ProtocolRef
from evidence.extractors import get, gliner
from evidence.replay import replay

from .conftest import PROTOCOL, corpus_of, pack_words, provider_of, screen_yes, scripted
from .fake_gliner import FakeGliner, closed_url

PROTO = protocol.load(PROTOCOL)
DATASETS = protocol.load(PROTOCOL.parent / "inv-datasets.yaml")
TEXT = ("# Study\n\nWe compare a closed-book baseline with its retrieval-augmented variant and with contrastive "
        "decoding on TriviaQA and NaturalQA. We report factual accuracy, BLEU and fluency.\n")


@pytest.fixture(autouse=True)
def fresh_info(monkeypatch: pytest.MonkeyPatch) -> None:
    gliner.forget()             # the /info cache is per process: every test starts empty
    monkeypatch.delenv("GLINER_URL", raising=False)


def config(etype: str, **more: Any) -> dict[str, Any]:
    spec = (DATASETS if etype == "dataset" else PROTO).evidence_types[etype]
    return {**pack_words(f"gliner_{etype}", etype), "evidence_type": etype, "field_schema": spec.fields,
            "roles": list(spec.roles), **more}


def extract(name: str, text: str, etype: str, cfg: dict[str, Any]) -> tuple[Any, EngineContext]:
    doc = DocumentRef(id="P", file="papers/P.md", sha256=text_sha256(text))
    task = ExtractionTask(protocol=ProtocolRef(id=PROTO.id, sha256=PROTO.sha256), evidence_type=etype,  # type: ignore[arg-type]
                          field_schema_sha256="x", document=doc)
    ctx = EngineContext(text, Index(text), [], {}, None)
    return get(name, cfg).extract(task, ctx), ctx


def fields(result: Any) -> list[dict[str, Any]]:
    return [i.fields for i in result.items]


def test_gliner_items_from_fake_server() -> None:
    with FakeGliner(model="fake/gliner-a") as server:
        cond, ctx = extract("gliner_condition", TEXT, "condition", config("condition", gliner_url=server.url))
        metric, _ = extract("gliner_metric", TEXT, "metric", config("metric", gliner_url=server.url))
        data, _ = extract("gliner_dataset", TEXT, "dataset", config("dataset", gliner_url=server.url))
    assert cond.status == "ok" and fields(cond) == [
        {"label": "closed-book baseline", "role": "baseline"},
        {"label": "retrieval-augmented variant", "role": "rag"},
        {"label": "contrastive decoding", "role": "other"}]            # no term matches: other
    assert [s.role for i in cond.items for s in i.spans] == ["condition_label"] * 3
    assert all(TEXT[s.selector["start"]:s.selector["end"]] == i.fields["label"] for i in cond.items for s in i.spans)
    # "fluency" scores 0.3, under the 0.5 threshold
    assert fields(metric) == [{"name": "factual accuracy", "canonical": "factual_accuracy", "higher_is_better": True},
                              {"name": "BLEU", "canonical": "other", "higher_is_better": True}]
    assert fields(data) == [{"name": "TriviaQA"}, {"name": "NaturalQA"}]
    assert {s.role for i in data.items for s in i.spans} == {"dataset_label"}
    # the request follows the contract; every call is recorded like a model call (no usage)
    assert server.requests[0] == {"text": TEXT, "labels": ["method", "system variant", "baseline model"], "threshold": 0.5}
    [record] = ctx.recorder.records
    assert record["request"]["labels"] == ["method", "system variant", "baseline model"]
    # /predict names no model: the record says the name came from /info, and the response claims none
    assert record["request"]["model_from_info"] == "fake/gliner-a" and "model" not in record["request"]
    assert record["response"]["entities"] and set(record["response"]) == {"entities"}
    assert "usage" not in record and cond.model_calls == (record["id"],)


def test_gliner_id_holds_model_labels_and_threshold() -> None:
    with FakeGliner(model="fake/gliner-a") as a, FakeGliner(model="fake/gliner-b") as b:
        one = get("gliner_metric", config("metric", gliner_url=a.url))
        assert one.available() and one.spec.kind == "model"
        assert one.spec.config["model"] == "fake/gliner-a" and one.spec.config["threshold"] == 0.5
        assert one.spec.config["labels"] == ["evaluation metric"]
        assert "gliner_url" not in json.dumps(one.spec.config)        # the address is not part of the id
        other_model = get("gliner_metric", config("metric", gliner_url=b.url))
        other_labels = get("gliner_metric", config("metric", gliner_url=a.url, labels=["metric"]))
        other_threshold = get("gliner_metric", config("metric", gliner_url=a.url, threshold=0.4))
        same = get("gliner_metric", config("metric", gliner_url=a.url))
        assert a.info_calls == 1                                       # /info is asked once per process
    ids = {one.spec.extractor_id, other_model.spec.extractor_id, other_labels.spec.extractor_id,
           other_threshold.spec.extractor_id}
    assert len(ids) == 4 and same.spec.extractor_id == one.spec.extractor_id


def test_gliner_offsets_mapped_across_chunks() -> None:
    para = "Filler sentence about nothing in particular, repeated to pass the chunk size. " * 20
    text = "# Paper\n\n" + para + "\n\n" + para + "\n\nWe evaluate on TriviaQA.\n\n" + para + "\n\nAlso on NaturalQA.\n"
    assert len(text) > 2 * 1500
    with FakeGliner() as server:
        result, _ = extract("gliner_dataset", text, "dataset", config("dataset", gliner_url=server.url))
    assert len(server.requests) > 1 and all(len(r["text"]) <= 1500 for r in server.requests)
    assert fields(result) == [{"name": "TriviaQA"}, {"name": "NaturalQA"}]
    for item in result.items:
        [span] = item.spans
        assert span.selector["start"] == text.index(item.fields["name"])
        assert text[span.selector["start"]:span.selector["end"]] == item.fields["name"]
    assert result.status == "ok" and sum(c.found for c in result.coverage) == 2


def test_gliner_wrong_offsets_are_rejected_not_kept() -> None:
    with FakeGliner(offsets=3) as server:
        result, _ = extract("gliner_dataset", TEXT, "dataset", config("dataset", gliner_url=server.url))
    assert result.items == () and {r.reason for r in result.rejected} == {"not_found"}


def test_gliner_disabled_without_url() -> None:
    ex = get("gliner_metric", config("metric"))           # no gliner_url and no GLINER_URL
    assert ex.available() is False and ex.spec.config["model"] is None
    result, ctx = extract("gliner_metric", TEXT, "metric", config("metric"))
    assert result.status == "error" and result.error.reason == "unavailable" and ctx.recorder.records == []
    assert engine.Settings(corpus="c", cache="k").gliner_url is None


def test_gliner_url_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    with FakeGliner() as server:
        monkeypatch.setenv("GLINER_URL", server.url)
        assert get("gliner_dataset", config("dataset")).available()
        assert engine.Settings(corpus="c", cache="k").gliner_url == server.url


def test_gliner_slow_service_is_an_extraction_error() -> None:
    with FakeGliner(delay=1.0) as server:
        result, ctx = extract("gliner_dataset", TEXT, "dataset", config("dataset", gliner_url=server.url, timeout=0.2))
    assert result.status == "error" and result.error.reason == "service_call"
    [record] = ctx.recorder.records
    assert "error" in record and result.model_calls == (record["id"],)


def test_gliner_down_falls_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLINER_URL", closed_url())
    proto = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    proto["evidence_types"]["metric"]["extractors"] = [{"name": "gliner_metric"}, {"name": "llm_metric"}]
    path = tmp_path / "protocol.yaml"
    path.write_text(yaml.safe_dump(proto, sort_keys=False), encoding="utf-8")
    doc = ("# T\n\n## Setup\n\nWe compare a closed-book baseline (B) with its retrieval-augmented variant (R).\n\n"
           "## Results\n\n| System | Dataset | Accuracy (%) |\n|---|---|---|\n| B | NQ | 60.0 |\n| R | NQ | 70.0 |\n")
    seen: list[str] = []

    def script(kind: str, _doc: str, prompt: str) -> dict[str, Any]:
        seen.append(kind)
        if kind == "screen":
            return screen_yes(prompt)
        if kind == "metric":
            return {"items": [{"fields": {"name": "Accuracy", "canonical": "factual_accuracy", "higher_is_better": True},
                               "quotes": {"metric_label": "Accuracy"}}]}
        return {"items": []} if kind != "retry" else {"quotes": []}

    run = engine.run(path, corpus_of(tmp_path / "corpus", {"P1": doc}), tmp_path / "runs", cache=tmp_path / "cache",
                     provider=provider_of(scripted(script, [])), model="scripted-alias", strategy="gaps", workers=1)
    rows = [json.loads(x) for x in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    metric_calls = [e for e in rows if e["subtype"] == "extractor_call" and e["custom_metadata"]["evidence_type"] == "metric"]
    assert [e["agent_id"].split("@")[0] for e in metric_calls] == ["gliner_metric", "llm_metric"]
    assert metric_calls[0]["status"] == "skipped" and "metric" in seen   # the service did not answer /info: skipped
    answer = json.loads((run / "answer.json").read_text(encoding="utf-8"))
    assert answer["label"] and json.loads((run / "run.json").read_text(encoding="utf-8"))["settings"]["gliner_url"]


def test_gliner_run_records_calls_in_calls_jsonl(tmp_path: Path) -> None:
    proto = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    proto["evidence_types"]["metric"]["extractors"] = [{"name": "gliner_metric"}, {"name": "regex_metric"}]
    path = tmp_path / "protocol.yaml"
    path.write_text(yaml.safe_dump(proto, sort_keys=False), encoding="utf-8")
    with FakeGliner() as server:
        settings = engine.Settings(corpus=str(corpus_of(tmp_path / "corpus", {"P1": TEXT})), cache=str(tmp_path / "cache"),
                                   strategy="all", gliner_url=server.url)
        run = engine.execute_run(path.read_bytes(), settings, tmp_path / "runs", provider=None)
    rows = [json.loads(x) for x in (run / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    [row] = [r for r in rows if r["extractor_id"].startswith("gliner_metric@")]
    assert row["model_calls"][0]["request"]["labels"] == ["evaluation metric"]
    assert json.loads((run / "run.json").read_text(encoding="utf-8"))["cost"]["model_calls"] >= 1


def gliner_protocol(tmp_path: Path) -> Path:
    proto = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    proto["evidence_types"]["metric"]["extractors"] = [{"name": "gliner_metric"}, {"name": "regex_metric"}]
    path = tmp_path / "gliner-protocol.yaml"
    path.write_text(yaml.safe_dump(proto, sort_keys=False), encoding="utf-8")
    return path


def recorded_run(tmp_path: Path) -> Path:
    """A run with a gliner_metric step against the stand-in; the server is gone when this returns."""
    with FakeGliner(model="fake/gliner-a") as server:
        settings = engine.Settings(corpus=str(corpus_of(tmp_path / "corpus", {"P1": TEXT})), cache=str(tmp_path / "cache"),
                                   strategy="all", gliner_url=server.url)
        run = engine.execute_run(gliner_protocol(tmp_path).read_bytes(), settings, tmp_path / "runs", provider=None)
    gliner.forget()             # a new process: nothing known about the service
    return run


def gliner_ids(run: Path) -> list[str]:
    return [i for i in json.loads((run / "run.json").read_text(encoding="utf-8"))["extractors"] if i.startswith("gliner_")]


def test_gliner_run_records_the_served_model(tmp_path: Path) -> None:
    run = recorded_run(tmp_path)
    settings = json.loads((run / "run.json").read_text(encoding="utf-8"))["settings"]
    assert settings["gliner_model"] == "fake/gliner-a"
    [spec] = [s for k, s in json.loads((run / "run.json").read_text(encoding="utf-8"))["extractor_specs"].items()
              if k.startswith("gliner_")]
    assert spec["config"]["model"] == "fake/gliner-a"


def test_gliner_replay_without_the_service(tmp_path: Path) -> None:
    run = recorded_run(tmp_path)
    new, report = replay(run)            # the recorded URL answers nothing now
    assert report["ok"], report
    assert gliner_ids(new) == gliner_ids(run)


def test_gliner_replay_takes_gliner_url_from_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = recorded_run(tmp_path)
    with FakeGliner(model="fake/gliner-a") as moved:
        monkeypatch.setenv("GLINER_URL", moved.url)
        new, report = replay(run)
    assert report["ok"], report
    settings = json.loads((new / "run.json").read_text(encoding="utf-8"))["settings"]
    assert settings["gliner_url"] == moved.url and settings["gliner_model"] == "fake/gliner-a"


def test_a_failed_info_is_asked_again_after_the_back_off_and_the_id_takes_the_model(
        monkeypatch: pytest.MonkeyPatch) -> None:
    with FakeGliner(model="fake/gliner-a", info_fails=1) as server:
        ex = get("gliner_metric", config("metric", gliner_url=server.url))
        down_id = ex.spec.extractor_id
        assert not ex.available() and not ex.available() and server.info_calls == 1   # within the back-off: not asked
        assert ex.spec.config["model"] is None
        monkeypatch.setattr(gliner, "RETRY_S", 0.0)
        assert ex.available() and server.info_calls == 2                           # asked again: up now
        assert ex.spec.config["model"] == "fake/gliner-a" and ex.spec.extractor_id != down_id
        up = get("gliner_metric", config("metric", gliner_url=server.url))          # the reply is kept
        assert server.info_calls == 2 and up.spec.extractor_id == ex.spec.extractor_id


def test_a_pinned_model_stays_and_needs_the_service_to_serve_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gliner, "RETRY_S", 0.0)
    with FakeGliner(model="fake/gliner-b", info_fails=1) as server:
        ex = get("gliner_metric", config("metric", gliner_url=server.url, model="fake/gliner-a"))
        pinned = ex.spec.extractor_id
        assert not ex.available() and ex.spec.extractor_id == pinned   # up, but another model: still unavailable
        assert ex.served == "fake/gliner-b" and ex.spec.config["model"] == "fake/gliner-a"


def test_gliner_up_after_the_run_started_is_used_and_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """/info fails when the run starts (the engine's ask and the extractor's), then answers at the first step: the
    step runs, run.json records the served model, and a replay without the service gives the same ids."""
    monkeypatch.setattr(gliner, "RETRY_S", 0.0)
    with FakeGliner(model="fake/gliner-a", info_fails=2) as server:
        settings = engine.Settings(corpus=str(corpus_of(tmp_path / "corpus", {"P1": TEXT})), cache=str(tmp_path / "cache"),
                                   strategy="all", gliner_url=server.url)
        run = engine.execute_run(gliner_protocol(tmp_path).read_bytes(), settings, tmp_path / "runs", provider=None)
        assert server.info_calls == 3
    rows = [json.loads(x) for x in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    statuses = [e["status"] for e in rows if e["subtype"] == "extractor_call" and e["agent_id"].startswith("gliner_")]
    assert statuses == ["ok"]
    record = json.loads((run / "run.json").read_text(encoding="utf-8"))
    assert record["settings"]["gliner_model"] == "fake/gliner-a"
    [spec] = [s for k, s in record["extractor_specs"].items() if k.startswith("gliner_")]
    assert spec["config"]["model"] == "fake/gliner-a"
    # the lock was rewritten with the ids the run used, and the seal hashed that final lock
    lock = json.loads((run / "protocol.lock.json").read_text(encoding="utf-8"))
    assert spec["extractor_id"] in [i for ids in lock["extractors"].values() for i in ids]
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["protocol_lock_sha256"] == file_sha256(run / "protocol.lock.json") == record["outputs"]["protocol.lock.json"]
    assert seal.check(run)["intact"]
    gliner.forget()
    new, report = replay(run)
    assert report["ok"], report
    assert gliner_ids(new) == gliner_ids(run)


def test_gliner_down_for_the_whole_run_asks_info_once_a_minute(tmp_path: Path) -> None:
    with FakeGliner(info_fails=100) as server:
        settings = engine.Settings(corpus=str(corpus_of(tmp_path / "corpus", {"P1": TEXT, "P2": TEXT})),
                                   cache=str(tmp_path / "cache"), strategy="all", gliner_url=server.url)
        run = engine.execute_run(gliner_protocol(tmp_path).read_bytes(), settings, tmp_path / "runs", provider=None)
        assert server.info_calls == 1          # the run is shorter than RETRY_S: the start's ask only
    rows = [json.loads(x) for x in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["status"] for e in rows if e["agent_id"].startswith("gliner_")] == ["skipped", "skipped"]
    assert json.loads((run / "run.json").read_text(encoding="utf-8"))["settings"]["gliner_model"] is None
