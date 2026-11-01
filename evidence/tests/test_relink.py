"""Relinking (`Settings.relink`): under `gaps` a type escalated in a later round is merged again, and an item whose
spans grew gets a new id. With `on` the links of the other types follow it (the merge event lists the remap as
`relinked`), and the run counts the links that point to no item (`dangling_links`); `off` is the engine of runs
before 1 Nov, which left those links dangling."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from evidence import engine, merge
from evidence.contract import ExtractionResult, Item, Span
from evidence.extractors import gliner
from evidence.protocol import parse
from evidence.replay import replay

from .conftest import PROTOCOL, context_id, corpus_of, provider_of, scripted, screen_yes
from .fake_gliner import FakeGliner
from .test_funnel import MISSING_BASELINE


@pytest.fixture(autouse=True)
def fresh_info(monkeypatch: pytest.MonkeyPatch) -> None:
    gliner.forget()
    monkeypatch.delenv("GLINER_URL", raising=False)


def rows(run: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def evidence(run: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (run / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]


def dangling(run: Path) -> list[tuple[str, str, str]]:
    items = evidence(run)
    ids = {i["item_id"] for i in items}
    return [(i["item_id"], k, v) for i in items for k, v in i["links"].items() if v not in ids]


def study(run: Path) -> dict[str, Any]:
    return json.loads((run / "answer.json").read_text(encoding="utf-8"))["studies"][0]


def respan_script(kind: str, _doc: str, prompt: str) -> dict[str, Any]:
    """The careful reader of MISSING_BASELINE: the baseline condition and its value; and the rag condition the regex
    found, quoted without its "(R)", so the re-merge of round 1 gives that condition a second span and a new id."""
    if kind == "screen":
        return screen_yes(prompt)
    if kind == "retry":
        return {"quotes": []}
    if kind == "condition":
        return {"items": [{"fields": {"label": "standard generator", "role": "baseline"},
                           "quotes": {"condition_label": "standard generator (S)"}},
                          {"fields": {"label": "retrieval-augmented variant", "role": "rag"},
                           "quotes": {"condition_label": "retrieval-augmented variant"}}]}
    if kind == "measurement":
        base, acc = context_id(prompt, '"baseline"'), context_id(prompt, '"factual_accuracy"')
        return {"items": [{"fields": {"value": 0.6, "dataset": "NQ", "form": None}, "links": {"condition": base, "metric": acc},
                           "quotes": {"value": "60.0", "condition_label": None, "metric_label": None, "value_total": None}}]}
    return {"items": []}


def respan_run(tmp_path: Path, relink: str, out: str = "runs") -> Path:
    if not (tmp_path / "corpus").exists():
        corpus_of(tmp_path / "corpus", {"P2": MISSING_BASELINE})
    settings = engine.Settings(corpus=str(tmp_path / "corpus"), cache=str(tmp_path / "cache"), model="scripted-alias",
                               strategy="gaps", confirm="none", relink=relink)  # type: ignore[arg-type]
    return engine.execute_run(PROTOCOL.read_bytes(), settings, tmp_path / out,
                              provider=provider_of(scripted(respan_script, [])))


def test_relink_on_keeps_links_after_a_later_round_respans_a_condition(tmp_path: Path) -> None:
    run = respan_run(tmp_path, "on")
    assert dangling(run) == []
    assert study(run)["direction"] == "supports"
    merges = [e for e in rows(run) if e["subtype"] == "merge" and e["custom_metadata"]["evidence_type"] == "condition"]
    [old] = merges[0]["generated"]                       # round 0: the regex rag condition
    [[was, now]] = merges[1]["custom_metadata"]["relinked"]
    assert was == old and now in merges[1]["generated"] and now != old
    rag = [i for i in evidence(run) if i["item_id"] == now][0]
    assert [x.split("@")[0] for x in rag["found_by"]] == ["regex_condition", "llm_condition"]
    assert any(i["links"].get("condition") == now for i in evidence(run) if i["evidence_type"] == "measurement")
    funnel = json.loads((run / "funnel.json").read_text(encoding="utf-8"))
    assert funnel["dangling_links"] == 0 and funnel["documents"]["P2"]["dangling_links"] == []
    record = json.loads((run / "run.json").read_text(encoding="utf-8"))
    assert record["settings"]["relink"] == "on" and record["dangling_links"] == 0


def test_relink_off_is_the_old_engine(tmp_path: Path) -> None:
    run = respan_run(tmp_path, "off")
    assert [k for _, k, _ in dangling(run)] == ["condition"]
    assert (study(run)["direction"], study(run)["reason"]["code"]) == ("undetermined", "no_pair")
    assert all("relinked" not in e["custom_metadata"] for e in rows(run) if e["subtype"] == "merge")
    funnel = json.loads((run / "funnel.json").read_text(encoding="utf-8"))
    assert "dangling_links" not in funnel and "dangling_links" not in funnel["documents"]["P2"]
    record = json.loads((run / "run.json").read_text(encoding="utf-8"))
    assert "relink" not in record["settings"] and "dangling_links" not in record


@pytest.mark.parametrize("relink", ["on", "off"])
def test_replay_repeats_relink(tmp_path: Path, relink: str) -> None:
    _, report = replay(respan_run(tmp_path, relink))
    assert report["ok"], report


def test_cli_relink_default_on() -> None:
    from evidence.cli import _parser
    args = _parser().parse_args(["run", "--protocol", "p", "--corpus", "c"])
    assert args.relink == "on"
    assert _parser().parse_args(["run", "--protocol", "p", "--corpus", "c", "--relink", "off"]).relink == "off"


# --- merge level -------------------------------------------------------------------------------------------

TEXT = "We compare the retrieval-augmented variant (R) with a baseline."
SPEC = parse(PROTOCOL.read_text(encoding="utf-8")).evidence_types["condition"]


def condition(extractor: str, quote: str) -> ExtractionResult:
    start = TEXT.index(quote)
    span = Span(role="condition_label", selector={"file": "p.md", "start": start, "end": start + len(quote),
                                                  "exact": quote})
    item = Item.build("condition", {"label": "retrieval-augmented variant", "role": "rag"}, [span])
    return ExtractionResult(extractor_id=extractor, task_sha256="t", status="ok", items=(item,))


def test_merge_from_maps_each_earlier_item_to_the_item_that_absorbed_it() -> None:
    first = [("t1", condition("regex@1", "retrieval-augmented variant (R)"))]
    both = [*first, ("t2", condition("llm@1", "retrieval-augmented variant"))]
    [old], _, _ = merge.merge(first, SPEC)
    items, sources, collisions, remap = merge.merge_from(both, SPEC, 1)
    [new] = items
    assert remap == {old.item_id: new.item_id} and new.item_id != old.item_id
    assert (items, sources, collisions) == merge.merge(both, SPEC)
    assert merge.merge_from(both, SPEC, 2)[3] == {}                       # nothing new: no remap
    assert merge.merge_from(first + [("t2", condition("llm@1", "retrieval-augmented variant (R)"))], SPEC, 1)[3] == {}


# --- eager confirmation in a later round -------------------------------------------------------------------

LATE = ("# T\n\n## Setup\n\nWe compare a closed-book baseline (B) with its retrieval-augmented variant (R).\n\n"
        "## Results\n\n| System | Dataset | Groundedness score (%) |\n|---|---|---|\n| B | NQ | 60.0 |\n"
        "| R | NQ | 70.0 |\n")


def late_script(kind: str, _doc: str, prompt: str) -> dict[str, Any]:
    if kind == "screen":
        return screen_yes(prompt)
    if kind == "retry":
        return {"quotes": []}
    if kind == "metric":
        return {"items": [{"fields": {"name": "Groundedness score", "canonical": "factual_accuracy",
                                      "higher_is_better": True}, "quotes": {"metric_label": "Groundedness score"}}]}
    if kind == "measurement":
        rag, base = context_id(prompt, '"rag"'), context_id(prompt, '"baseline"')
        metric = context_id(prompt, '"factual_accuracy"')
        return {"items": [{"fields": {"value": v, "dataset": "NQ", "form": None}, "links": {"condition": c, "metric": metric},
                           "quotes": {"value": q, "condition_label": None, "metric_label": None, "value_total": None}}
                          for v, c, q in ((0.6, base, "60.0"), (0.7, rag, "70.0"))]}
    return {"items": []}


def test_eager_confirm_in_a_later_round(tmp_path: Path) -> None:
    """The metric cascade of best-*/cons-*: regex, abbrev, GLiNER, LLM. Neither regex nor abbrev knows the metric,
    so GLiNER runs in round 2 and the LLM confirms its item in the same round, before measurement escalates."""
    proto = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    proto["evidence_types"]["metric"]["extractors"] = [{"name": n} for n in
                                                       ("regex_metric", "abbrev_metric", "gliner_metric", "llm_metric")]
    path = tmp_path / "protocol.yaml"
    path.write_text(yaml.safe_dump(proto, sort_keys=False), encoding="utf-8")
    corpus_of(tmp_path / "corpus", {"P1": LATE})
    with FakeGliner(patterns={"evaluation metric": [(r"Groundedness score", 0.9)]}) as server:
        settings = engine.Settings(corpus=str(tmp_path / "corpus"), cache=str(tmp_path / "cache"), model="scripted-alias",
                                   strategy="gaps", gliner_url=server.url)
        run = engine.execute_run(path.read_bytes(), settings, tmp_path / "runs",
                                 provider=provider_of(scripted(late_script, [])))
    funnel = json.loads((run / "funnel.json").read_text(encoding="utf-8"))["documents"]["P1"]
    metric_steps = [(s["round"], s["position"]) for s in funnel["steps"] if "metric" in s["types"]]
    assert metric_steps == [(0, 0), (1, 1), (2, 2), (2, 3)]               # GLiNER, then the LLM, both in round 2
    # GLiNER's item has canonical `other` (no term of the lists in "Groundedness score"): it is not the LLM's item
    # and is dropped in the round-2 merge; the LLM's item stays
    merges = [e for e in rows(run) if e["subtype"] == "merge" and e["custom_metadata"]["evidence_type"] == "metric"]
    assert [len(e["custom_metadata"].get("unconfirmed", [])) for e in merges] == [0, 0, 1]
    [metric] = [i for i in evidence(run) if i["evidence_type"] == "metric"]
    assert [x.split("@")[0] for x in metric["found_by"]] == ["llm_metric"]
    assert [(s["round"], s["types"]) for s in funnel["steps"]][-1] == (3, ["measurement"])
    assert dangling(run) == []
    assert study(run)["direction"] == "supports"
    gliner.forget()
    _, report = replay(run)
    assert report["ok"], report
