"""Confirmation (`Settings.confirm`): with `llm`, an item only GLiNER found counts only when an LLM extractor of the
same cascade found it too (the same merged item); `none` keeps every item, as runs before 29 Oct did."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from evidence import engine
from evidence.extractors import gliner
from evidence.replay import replay

from .conftest import PROTOCOL, corpus_of, provider_of, scripted, screen_yes
from .fake_gliner import FakeGliner

TEXT = "# Study\n\nWe report Performance and accuracy of a closed-book baseline and its retrieval-augmented variant.\n"
EM_TEXT = "# Study\n\nWe report Exact Match (EM) of a closed-book baseline and its retrieval-augmented variant.\n"
# complete after position 0: regex conditions and measurements, the metric from GLiNER alone
TABLE = ("# T\n\n## Setup\n\nWe compare a closed-book baseline (B) with its retrieval-augmented variant (R).\n\n"
         "## Results\n\n| System | Dataset | Factual accuracy (%) |\n|---|---|---|\n| B | NQ | 60.0 |\n| R | NQ | 70.0 |\n")
PATTERNS = {"evaluation metric": [(r"\bPerformance\b", 0.9), (r"\baccuracy\b", 0.9), (r"Exact Match \(EM\)", 0.9),
                                  (r"\bFactual accuracy\b", 0.9)]}


@pytest.fixture(autouse=True)
def fresh_info(monkeypatch: pytest.MonkeyPatch) -> None:
    gliner.forget()
    monkeypatch.delenv("GLINER_URL", raising=False)


def protocol_file(tmp_path: Path) -> Path:
    """rag-factuality with the metric cascade gliner_metric, llm_metric."""
    proto = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    proto["evidence_types"]["metric"]["extractors"] = [{"name": "gliner_metric"}, {"name": "llm_metric"}]
    path = tmp_path / "protocol.yaml"
    path.write_text(yaml.safe_dump(proto, sort_keys=False), encoding="utf-8")
    return path


def metric_script(name: str | None, quote: str | None = None) -> Any:
    """The LLM finds one metric `name` (quoted as `quote`, default the name), nothing else."""
    def script(kind: str, _doc: str, prompt: str) -> dict[str, Any]:
        if kind == "screen":
            return screen_yes(prompt)
        if kind == "metric" and name is not None:
            return {"items": [{"fields": {"name": name, "canonical": "factual_accuracy", "higher_is_better": True},
                               "quotes": {"metric_label": quote or name}}]}
        return {"items": []} if kind != "retry" else {"quotes": []}
    return script


def run_with(tmp_path: Path, text: str, script: Any, *, confirm: str = "llm", strategy: str = "all",
             gliner_url: str | None = None, selection: str = "cascade", out: str = "runs") -> Path:
    settings = engine.Settings(corpus=str(tmp_path / "corpus"), cache=str(tmp_path / "cache"), model="scripted-alias",
                               strategy=strategy, gliner_url=gliner_url, selection=selection,  # type: ignore[arg-type]
                               confirm=confirm)  # type: ignore[arg-type]
    if not (tmp_path / "corpus").exists():
        corpus_of(tmp_path / "corpus", {"P1": text})
    proto = tmp_path / "protocol.yaml" if (tmp_path / "protocol.yaml").exists() else protocol_file(tmp_path)
    return engine.execute_run(proto.read_bytes(), settings, tmp_path / out, provider=provider_of(scripted(script, [])))


def served_run(tmp_path: Path, text: str, script: Any, **kw: Any) -> Path:
    with FakeGliner(patterns=PATTERNS) as server:
        return run_with(tmp_path, text, script, gliner_url=server.url, **kw)


def rows(run: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def metrics(run: Path) -> list[dict[str, Any]]:
    items = [json.loads(x) for x in (run / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    return [i for i in items if i["evidence_type"] == "metric"]


def metric_merges(run: Path) -> list[dict[str, Any]]:
    return [e for e in rows(run) if e["subtype"] == "merge" and e["custom_metadata"]["evidence_type"] == "metric"]


def test_gliner_only_item_dropped(tmp_path: Path) -> None:
    run = served_run(tmp_path, TEXT, metric_script("accuracy"))
    assert [i["fields"]["name"] for i in metrics(run)] == ["accuracy"]
    [merge] = metric_merges(run)
    assert len(merge["custom_metadata"]["unconfirmed"]) == 1
    assert merge["custom_metadata"]["unconfirmed"][0] not in merge["generated"]


def test_confirmed_item_kept_with_both_extractors(tmp_path: Path) -> None:
    run = served_run(tmp_path, TEXT, metric_script("accuracy"))
    [item] = metrics(run)
    assert [i.split("@")[0] for i in item["found_by"]] == ["gliner_metric", "llm_metric"]


def test_unconfirmed_confirmed_eagerly_in_gaps(tmp_path: Path) -> None:
    run = served_run(tmp_path, TABLE, metric_script(None), strategy="gaps")   # the LLM confirms nothing
    llm = [e for e in rows(run) if e["subtype"] == "extractor_call" and e["agent_id"].startswith("llm_metric@")
           and e["custom_metadata"]["document"] == "P1"]
    assert len(llm) == 1
    funnel = json.loads((run / "funnel.json").read_text(encoding="utf-8"))["documents"]["P1"]
    # the LLM position runs in round 0, right after GLiNER's, before the measurements link to the metric ...
    assert {"round": 0, "position": 1, "types": ["metric"], "calls": [llm[0]["task_id"]]} in funnel["steps"]
    assert metrics(run) == []                                            # ... the GLiNER metric is gone
    assert funnel["decisions"][0]["complete"] is False                   # ... before the first decision


def test_gaps_confirm_keeps_measurement_links(tmp_path: Path) -> None:
    """The LLM agrees with GLiNER's metric: the measurements link to the confirmed metric (not to a GLiNER-only id
    a later merge replaced), so the study reads as with `none`."""
    script = metric_script("Factual accuracy", quote="Factual accuracy (%)")
    a = served_run(tmp_path, TABLE, script, confirm="none", strategy="gaps", out="a")
    gliner.forget()
    b = served_run(tmp_path, TABLE, script, confirm="llm", strategy="gaps", out="b")
    direction = [json.loads((r / "answer.json").read_text(encoding="utf-8"))["studies"][0]["direction"] for r in (a, b)]
    assert direction == ["supports", "supports"]
    items = [json.loads(x) for x in (b / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    ids = {i["item_id"] for i in items}
    assert [(i["item_id"], v) for i in items for v in i["links"].values() if v not in ids] == []
    assert [[x.split("@")[0] for x in i["found_by"]] for i in metrics(b)] == [["gliner_metric", "llm_metric"]]
    llm = [e for e in rows(b) if e["subtype"] == "extractor_call" and e["agent_id"].startswith("llm_metric@")]
    funnel = json.loads((b / "funnel.json").read_text(encoding="utf-8"))["documents"]["P1"]
    assert {"round": 0, "position": 1, "types": ["metric"], "calls": [llm[0]["task_id"]]} in funnel["steps"]
    assert [d["complete"] for d in funnel["decisions"]] == [True]


def test_unconfirmed_dropped_llm_variant_kept(tmp_path: Path) -> None:
    run = served_run(tmp_path, EM_TEXT, metric_script("exact match", quote="Exact Match"))
    assert [i["fields"]["name"] for i in metrics(run)] == ["exact match"]


def test_confirm_noop_without_gliner(tmp_path: Path) -> None:
    script = metric_script("accuracy")
    a = run_with(tmp_path, TEXT, script, confirm="none", strategy="gaps", out="a")
    b = run_with(tmp_path, TEXT, script, confirm="llm", strategy="gaps", out="b")
    assert (a / "answer.json").read_bytes() == (b / "answer.json").read_bytes()


@pytest.mark.parametrize("selection", ["llm-only", "regex-only"])
def test_confirm_noop_for_single_kind_selections(tmp_path: Path, selection: str) -> None:
    script = metric_script("accuracy")
    a = served_run(tmp_path, TEXT, script, confirm="none", selection=selection, out="a")
    b = served_run(tmp_path, TEXT, script, confirm="llm", selection=selection, out="b")
    assert (a / "answer.json").read_bytes() == (b / "answer.json").read_bytes()


def test_replay_of_old_run_uses_none(tmp_path: Path) -> None:
    run = served_run(tmp_path, TEXT, metric_script("accuracy"), confirm="none", strategy="gaps")
    assert "confirm" not in json.loads((run / "run.json").read_text(encoding="utf-8"))["settings"]
    assert sorted(i["fields"]["name"] for i in metrics(run)) == ["Performance", "accuracy"]   # nothing dropped
    gliner.forget()
    _, report = replay(run)
    assert report["ok"], report


def test_replay_of_confirm_run(tmp_path: Path) -> None:
    run = served_run(tmp_path, TABLE, metric_script(None), strategy="gaps")
    assert json.loads((run / "run.json").read_text(encoding="utf-8"))["settings"]["confirm"] == "llm"
    gliner.forget()
    _, report = replay(run)
    assert report["ok"], report
