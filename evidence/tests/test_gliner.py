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
from evidence import engine, protocol
from evidence.calls import EngineContext
from evidence.contract import DocumentRef, ExtractionTask, ProtocolRef
from evidence.extractors import get, gliner

from .conftest import PROTOCOL, corpus_of, provider_of, screen_yes, scripted
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
    return {"evidence_type": etype, "field_schema": spec.fields, "roles": list(spec.roles), **more}


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
    assert record["request"]["model"] == "fake/gliner-a" and record["response"]["entities"]
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
    assert metric_calls[0]["status"] == "error" and "metric" in seen
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
