"""The single-call LLM extractors with a scripted model (pydantic-ai FunctionModel): cascade merge with
found_by, the quote retry, the cache (a rerun costs no model call), replay without a model, re-execution,
failures as statuses, and extractor ids that change with prompt and config."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from evidence import engine, extractors
from evidence.replay import reexec, replay

from .conftest import context_id, provider_of, scripted

EXTRA: dict[str, Any] = {"on": False}


def s001(evidence_type: str, doc: str, prompt: str) -> dict[str, Any]:
    """S001 as a careful reader would extract it, plus one fabricated quote; nothing for the others."""
    if evidence_type == "retry":
        return {"quotes": [{"id": "q1", "quote": "an accuracy of 99% that is not in the paper"}]}
    if doc != "S001":
        return {"items": []}
    if evidence_type == "condition":
        return {"items": [
            {"fields": {"label": "closed-book model", "role": "baseline"}, "quotes": {"condition_label": "We compare a closed-book model"}},
            {"fields": {"label": "retrieval-augmented model", "role": "rag"},
             "quotes": {"condition_label": "with a retrieval-augmented model on"}}]}
    if evidence_type == "metric":
        return {"items": [{"fields": {"name": "answer accuracy", "canonical": "factual_accuracy", "higher_is_better": True},
                           "quotes": {"metric_label": "reaches an answer accuracy of"}}]}
    if evidence_type == "measurement":
        rag, base, acc = (context_id(prompt, '"rag"'), context_id(prompt, '"baseline"'),
                          context_id(prompt, '"answer accuracy"'))
        items = [{"fields": {"value": 71, "dataset": "Natural Questions"}, "links": {"condition": rag, "metric": acc},
                  "quotes": {"value": "reaches an answer accuracy of 71%", "condition_label": None, "metric_label": None}},
                 {"fields": {"value": 0.99, "dataset": None}, "links": {"condition": base, "metric": acc},
                  "quotes": {"value": "an accuracy of 99%", "condition_label": None, "metric_label": None}}]
        if EXTRA["on"]:
            items.append({"fields": {"value": 0.62, "dataset": "Natural Questions"}, "links": {"condition": base, "metric": acc},
                          "quotes": {"value": "| Closed-book model | 62.0", "condition_label": None, "metric_label": None}})
        return {"items": items}
    return {"items": [{"fields": {"direction": "improves"},
                       "quotes": {"claim": "Retrieval-augmented generation improves the factual accuracy"}}]}


def cascade(protocol_file: Path, corpus: Path, tmp_path: Path, calls: list[str], **kw: Any) -> Path:
    model = scripted(s001, calls)
    return engine.run(protocol_file, corpus, tmp_path / "runs", cache=tmp_path / "cache", provider=provider_of(model),
                      model="scripted-alias", **kw)


def evidence(root: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (root / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]


def test_cascade_merge_keeps_spans_and_found_by(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    calls: list[str] = []
    root = cascade(protocol_file, corpus, tmp_path, calls)
    record = json.loads((root / "run.json").read_text())
    ids = {e.split("@")[0]: e for e in record["extractors"]}
    items = evidence(root)
    base = next(i for i in items if i["evidence_type"] == "condition" and i["fields"]["role"] == "baseline"
                and i["spans"][0]["selector"]["file"] == "papers/S001.md")
    assert base["found_by"] == [ids["regex_condition"], ids["llm_condition"]]
    m71 = next(i for i in items if i["evidence_type"] == "measurement" and i["fields"]["value"] == 0.71)
    assert m71["found_by"] == [ids["regex_measurement"], ids["llm_measurement"]]
    assert m71["fields"]["dataset"] == "Natural Questions"           # null filled from the later extractor
    assert [s["selector"]["exact"] for s in m71["spans"] if s["role"] == "value"] == ["71%", "71.0"]
    assert not any(i["fields"].get("value") == 0.99 for i in items)
    llm_call = next(json.loads(p.read_text()) for p in (root / "calls").glob("*.json")
                    if json.loads(p.read_text())["extractor_id"] == ids["llm_measurement"]
                    and json.loads(p.read_text())["items"])
    assert [r["reason"] for r in llm_call["rejected"]] == ["not_found"]   # still not found after the retry
    assert len(llm_call["model_calls"]) == 2 and any("Rejected quotes:" in c for c in calls)
    assert record["cost"]["model_calls"] == len(calls) and record["cost"]["input_tokens"] > 0


def test_cache_hit_costs_no_model_call_and_replay_needs_no_model(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    calls: list[str] = []
    first = cascade(protocol_file, corpus, tmp_path, calls)
    made = len(calls)
    second = cascade(protocol_file, corpus, tmp_path, calls)
    assert len(calls) == made
    cost = json.loads((second / "run.json").read_text())["cost"]
    assert cost["cached_calls"] == cost["calls"] == 40 and cost["made_model_calls"] == 0
    assert json.loads((first / "run.json").read_text())["outputs"] == json.loads((second / "run.json").read_text())["outputs"]
    _, report = replay(first)        # replay is given no model at all
    assert report["ok"]
    cache = (tmp_path / "cache" / "extractor_calls.jsonl").read_text(encoding="utf-8").splitlines()
    value = next(json.loads(x)["value"] for x in cache if json.loads(x)["value"]["model_calls"])
    record = value["model_calls"][0]
    assert {"request", "response", "usage"} <= set(record) and record["request"]["settings"]["temperature"] == 0.0


def test_reexec_counts_differences(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    calls: list[str] = []
    root = cascade(protocol_file, corpus, tmp_path, calls)
    same = json.loads((reexec(root, provider=provider_of(scripted(s001, calls))) / "reexec.json").read_text())
    assert same["totals"] == {"identical": 40}
    EXTRA["on"] = True
    try:
        changed = reexec(root, "llm_measurement", provider=provider_of(scripted(s001, calls)))
    finally:
        EXTRA["on"] = False
    report = json.loads((changed / "reexec.json").read_text())
    row = next(c for c in report["calls"] if c["extractor"] == "llm_measurement" and c["document"] == "S001")
    assert row["outcome"] == "items_added" and row["added"] == 1
    assert report["summary"]["llm_measurement"]["items_added"] == 1
    assert report["summary"]["regex_measurement"]["identical"] == 5


def test_model_failure_is_a_status_and_redacted(protocol_file: Path, corpus: Path, tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-secret-key-123456")

    def broken(alias: str) -> Any:
        raise RuntimeError("auth failed for key sk-secret-key-123456")

    root = engine.run(protocol_file, corpus, tmp_path / "runs", selection="llm-only", provider=broken)
    record = json.loads((root / "run.json").read_text())
    assert all(e.startswith("llm_") for e in record["extractors"])
    for path in (root / "calls").glob("*.json"):
        result = json.loads(path.read_text())
        assert result["status"] == "error" and result["coverage"][0]["status"] == "error"
        assert "sk-secret" not in path.read_text() and "***" in result["error"]["detail"]
    answer = json.loads((root / "answer.json").read_text())
    assert answer["label"] == "insufficient"


def test_extractor_id_changes_with_prompt_config_and_model() -> None:
    def ident(name: str, **config: Any) -> str:
        return extractors.get(name, config).spec.extractor_id

    base = ident("llm_condition")
    assert ident("llm_condition") == base
    assert ident("llm_condition", instructions="Another prompt {evidence_type}{description}{fields}{links}{roles}") != base
    assert ident("llm_condition", seed=1) != base
    assert ident("llm_condition", model="sub-model-2") != base
    assert ident("llm_condition", field_schema={"type": "object", "properties": {"label": {"type": "string"}}}) != base
    spec = extractors.get("llm_condition").spec
    assert spec.kind == "llm" and spec.config["temperature"] == 0.0 and len(spec.config["prompt_sha256"]) == 64
    assert ident("regex_metric") != ident("regex_metric", metrics=[[r"\bBLEU\b", "other", True]])
    assert extractors.get("regex_metric").spec.determinism == "exact"


def test_registry_api() -> None:
    assert {"regex_condition", "llm_measurement"} <= set(extractors.names())
    marker = extractors.get("regex_condition")
    extractors.register("test_alias_extractor", lambda config: marker)
    assert extractors.get("test_alias_extractor") is marker
    with pytest.raises(KeyError, match="no extractor named"):
        extractors.get("missing_extractor")
    with pytest.raises(ValueError):
        extractors.register("Bad-Name", lambda config: marker)


def test_engine_runs_inside_an_event_loop(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    calls: list[str] = []

    async def main() -> Path:
        return cascade(protocol_file, corpus, tmp_path, calls)

    root = asyncio.run(main())
    assert calls and any(i["evidence_type"] == "author_claim" and len(i["found_by"]) == 2 for i in evidence(root))
