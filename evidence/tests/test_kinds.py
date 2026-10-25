"""The rules module of each question kind (evidence/kinds/): per-document entry, gap types, answer shape."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

from evidence import engine, kinds, synthesis
from evidence.contract import Item, Span
from evidence.protocol import Protocol

from .conftest import PROTOCOL, make_corpus

BASE: dict[str, Any] = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
BEST_KINDS = {"rag": ["RAG", "retrieval-augmented model", "retrieval-augmented variant"],
              "fine-tuned": ["fine-tuned model"],
              "baseline": ["closed-book model", "closed-book baseline", "LLM"]}


def protocol_data(kind: str, **blocks: Any) -> dict[str, Any]:
    """rag-factuality as a protocol of `kind`, with that kind's blocks (and no foreign ones)."""
    data = copy.deepcopy(BASE)
    data["kind"] = kind
    if kind in ("inventory", "best"):
        del data["synthesis"]
    if kind == "consistency":
        data["consistency"] = {"by": "direction"}
    if kind == "best":
        props = data["evidence_types"]["condition"]["fields"]["properties"]
        props["kind"] = {"type": "string", "enum": sorted(blocks["best"]["kinds"])}
        data["evidence_types"]["condition"]["fields"]["required"] = ["label"]
    if kind == "inventory" and blocks["inventory"]["target"] == "dataset":
        data["evidence_types"]["dataset"] = {"fields": {"type": "object", "properties": {"name": {"type": "string"}}},
                                             "roles": ["dataset_label"], "extractors": [{"name": "llm_dataset"}]}
    data.update(blocks)
    return data


def proto(kind: str, **blocks: Any) -> Protocol:
    return Protocol.model_validate(protocol_data(kind, **blocks))


def best_proto(higher_is_better: bool = True, canonical: str = "factual_accuracy") -> Protocol:
    return proto("best", best={"metric": {"canonical": canonical, "higher_is_better": higher_is_better},
                               "kinds": BEST_KINDS})


_POS = [0]


def span(role: str, text: str = "x", doc: str = "D1", prefix: str = "", suffix: str = "") -> Span:
    _POS[0] += 10
    start = _POS[0]
    return Span(role=role, selector={"file": f"papers/{doc}.md", "start": start, "end": start + len(text),
                                     "exact": text, "prefix": prefix, "suffix": suffix})


def item(etype: str, fields: dict[str, Any], role: str, links: dict[str, str] | None = None, doc: str = "D1",
         **kw: Any) -> Item:
    return Item.build(etype, fields, [span(role, doc=doc, **kw)], links)  # type: ignore[arg-type]


def cond(label: str, role: str | None = None, kind: str | None = None, doc: str = "D1") -> Item:
    fields: dict[str, Any] = {"label": label}
    if role:
        fields["role"] = role
    if kind:
        fields["kind"] = kind
    return item("condition", fields, "condition_label", doc=doc)


def metric(name: str, canonical: str = "factual_accuracy", doc: str = "D1") -> Item:
    return item("metric", {"name": name, "canonical": canonical, "higher_is_better": canonical != "hallucination_rate"},
                "metric_label", doc=doc)


def meas(c: Item, k: Item, value: float, dataset: str | None = None, doc: str = "D1", table: bool = False) -> Item:
    kw = {"prefix": "| ", "suffix": " |"} if table else {}
    return item("measurement", {"value": value, "dataset": dataset}, "value",
                {"condition": c.item_id, "metric": k.item_id}, doc=doc, **kw)


def claim(direction: str, doc: str = "D1") -> Item:
    return item("author_claim", {"direction": direction}, "claim", doc=doc)


def effect_items(rag: float, base: float, direction: str | None = "improves", doc: str = "D1") -> list[Item]:
    r, b, k = cond("RAG", "rag", doc=doc), cond("LLM", "baseline", doc=doc), metric("accuracy", doc=doc)
    out = [r, b, k, meas(r, k, rag, doc=doc), meas(b, k, base, doc=doc)]
    return out + ([claim(direction, doc=doc)] if direction else [])


# --- effect ------------------------------------------------------------------------------------------------


def test_effect_kind_is_todays_synthesis() -> None:
    p = proto("effect")
    assert kinds.of(p) is kinds.effect
    items = {"D1": effect_items(0.7, 0.6, doc="D1"), "D2": effect_items(0.5, 0.6, doc="D2"), "D3": []}
    for doc, its in items.items():
        assert kinds.of(p).study(p, doc, its) == synthesis.study(p, doc, its)
    assert kinds.of(p).answer(p, list(items), items, {}, {}) == synthesis.answer(p, list(items), items, {}, {})
    for code, types in synthesis.GAP_TYPES.items():
        assert kinds.of(p).gap_types(p, code) == types
    assert kinds.of(p).extractor_config(p) == {"question_metrics": ["factual_accuracy", "hallucination_rate"],
                                               "compare": {"treatment": "rag", "control": "baseline"}}


# --- consistency -------------------------------------------------------------------------------------------


def test_consistency_agrees_and_disagrees() -> None:
    p = proto("consistency")
    mod = kinds.of(p)
    items = {"D1": effect_items(0.7, 0.6, "improves", doc="D1"), "D2": effect_items(0.5, 0.6, "improves", doc="D2")}
    entry, used = mod.study(p, "D1", items["D1"])
    assert (entry["claim"], entry["direction"], entry["agrees"], entry["reason"]) == ("improves", "supports", True, None)
    assert used
    entry, _ = mod.study(p, "D2", items["D2"])
    assert (entry["direction"], entry["agrees"]) == ("contradicts", False)
    answer, _ = mod.answer(p, ["D1", "D2", "D3"], items, {}, {})
    assert answer["kind"] == "consistency" and answer["system"] == "evidence-engine"
    assert answer["metric"] == "factual_accuracy"
    assert [s["document"] for s in answer["studies"]] == ["D1", "D2", "D3"]
    assert set(answer["studies"][0]) == {"document", "claim", "direction", "agrees", "reason"}
    assert (answer["agreeing"], answer["disagreeing"], answer["undetermined"]) == (["D1"], ["D2"], ["D3"])
    assert mod.extractor_config(p) == kinds.effect.extractor_config(p)


def test_consistency_no_claim_gap() -> None:
    p = proto("consistency")
    entry, _ = kinds.of(p).study(p, "D1", effect_items(0.7, 0.6, direction=None))
    assert entry["claim"] is None and entry["agrees"] is None and entry["direction"] == "supports"
    assert entry["reason"]["code"] == "no_claim"
    assert kinds.of(p).gap_types(p, "no_claim") == ("author_claim",)
    assert kinds.of(p).gap_types(p, "no_pair") == ("measurement",)   # the effect codes stay


# --- inventory ---------------------------------------------------------------------------------------------


def test_inventory_groups_same_names() -> None:
    p = proto("inventory", inventory={"target": "metric", "same": {"answer accuracy": ["AA"]}})
    mod = kinds.of(p)
    a, b, c = metric("Answer Accuracy", doc="D1"), metric("answer accuracy", doc="D2"), metric("AA", doc="D2")
    other = metric("Latency", "other", doc="D2")
    items = {"D1": [a], "D2": [b, c, other]}
    entry, used = mod.study(p, "D1", items["D1"])
    assert entry["reason"] is None and used == [a.item_id]
    answer, used = mod.answer(p, ["D1", "D2"], items, {}, {})
    assert answer == {"kind": "inventory", "system": "evidence-engine", "target": "metric", "entries": [
        {"name": "answer accuracy", "aliases": ["AA", "Answer Accuracy"], "papers": ["D1", "D2"],
         "items": [a.item_id, b.item_id, c.item_id]},
        {"name": "Latency", "aliases": [], "papers": ["D2"], "items": [other.item_id]}]}
    assert sorted(used) == sorted([a.item_id, b.item_id, c.item_id, other.item_id])
    assert mod.extractor_config(p) == {"target": "metric", "same": {"answer accuracy": ["AA"]}}


def test_inventory_no_items_gap() -> None:
    p = proto("inventory", inventory={"target": "dataset"})
    entry, used = kinds.of(p).study(p, "D1", effect_items(0.7, 0.6))
    assert entry["reason"]["code"] == "no_target_items" and used == []
    assert kinds.of(p).gap_types(p, "no_target_items") == ("dataset",)
    assert kinds.of(p).gap_types(p, "screened_out") == ()


# --- best --------------------------------------------------------------------------------------------------


def best_items(values: dict[str, float], doc: str) -> list[Item]:
    k = metric("accuracy", doc=doc)
    out: list[Item] = [k]
    for label, value in values.items():
        c = cond(label, doc=doc)
        out += [c, meas(c, k, value, dataset="TriviaCheck", doc=doc)]
    return out


def test_best_counts_wins() -> None:
    p = best_proto()
    mod = kinds.of(p)
    items = {"D1": best_items({"RAG": 0.8, "LLM": 0.6}, "D1"),
             "D2": best_items({"retrieval-augmented model": 0.7, "fine-tuned model": 0.65}, "D2"),
             "D3": best_items({"RAG": 0.5, "fine-tuned model": 0.75, "LLM": 0.4}, "D3")}
    entry, used = mod.study(p, "D3", items["D3"])
    assert entry == {"document": "D3", "winner": "fine-tuned", "tied": [],
                     "values": {"rag": 0.5, "fine-tuned": 0.75, "baseline": 0.4}, "reason": None}
    assert len(used) == 7                 # three measurements, their conditions, the metric
    answer, _ = mod.answer(p, list(items), items, {}, {})
    assert answer["kind"] == "best" and answer["system"] == "evidence-engine" and answer["metric"] == "factual_accuracy"
    assert set(answer["studies"][0]) == {"document", "winner", "tied", "values", "reason"}
    assert answer["wins"] == {"rag": 2, "fine-tuned": 1}
    assert (answer["winner"], answer["tied"]) == ("rag", [])
    assert mod.extractor_config(p) == {"question_metrics": ["factual_accuracy"], "kinds": BEST_KINDS}


def test_best_tie_gives_no_win() -> None:
    p = best_proto()
    mod = kinds.of(p)
    items = {"D1": best_items({"RAG": 0.7, "fine-tuned model": 0.7, "LLM": 0.5}, "D1"),
             "D2": best_items({"RAG": 0.9, "LLM": 0.5}, "D2"), "D3": best_items({"LLM": 0.9, "RAG": 0.5}, "D3")}
    entry, _ = mod.study(p, "D1", items["D1"])
    assert entry["winner"] is None and entry["tied"] == ["fine-tuned", "rag"] and entry["reason"] is None
    answer, _ = mod.answer(p, list(items), items, {}, {})
    assert answer["wins"] == {"rag": 1, "baseline": 1}
    assert answer["winner"] is None and answer["tied"] == ["baseline", "rag"]


def test_best_paper_without_metric_is_undetermined() -> None:
    p = best_proto()
    mod = kinds.of(p)
    r, b, k = cond("RAG"), cond("LLM"), metric("hallucination rate", "hallucination_rate")
    items = [r, b, k, meas(r, k, 0.2), meas(b, k, 0.3)]       # measured, but not on the question metric
    entry, used = mod.study(p, "D1", items)
    assert entry["winner"] is None and entry["values"] == {} and entry["reason"]["code"] == "no_comparison"
    assert used == []
    assert mod.gap_types(p, "no_comparison") == ("measurement",)
    entry, _ = mod.study(p, "D2", [cond("RAG", doc="D2"), metric("accuracy", doc="D2")])
    assert entry["reason"]["code"] == "too_few_kinds" and mod.gap_types(p, "too_few_kinds") == ("condition",)
    answer, _ = mod.answer(p, ["D1", "D2"], {"D1": items}, {}, {})
    assert answer["wins"] == {} and answer["winner"] is None and answer["tied"] == []


def test_best_lower_is_better() -> None:
    p = best_proto(higher_is_better=False, canonical="hallucination_rate")
    k = metric("hallucination rate", "hallucination_rate")
    r, b = cond("RAG"), cond("LLM")
    entry, _ = kinds.of(p).study(p, "D1", [k, r, b, meas(r, k, 0.1), meas(b, k, 0.3)])
    assert entry["winner"] == "rag"


def test_best_pairs_on_the_first_dataset_and_prefers_table_cells() -> None:
    p = best_proto()
    k, r, b = metric("accuracy"), cond("RAG"), cond("LLM")
    items = [k, r, b, meas(r, k, 0.9, "OnlyRag"),               # one kind only: not comparable
             meas(r, k, 0.5, "TriviaCheck"), meas(b, k, 0.6, "TriviaCheck"),
             meas(r, k, 0.8, "TriviaCheck", table=True)]       # a table cell beats the earlier prose value
    entry, _ = kinds.of(p).study(p, "D1", items)
    assert entry["values"] == {"rag": 0.8, "baseline": 0.6} and entry["winner"] == "rag"


def test_kind_field_beats_the_label() -> None:
    p = best_proto()
    k, r, b = metric("accuracy"), cond("RAG", kind="fine-tuned"), cond("LLM")
    entry, _ = kinds.of(p).study(p, "D1", [k, r, b, meas(r, k, 0.9), meas(b, k, 0.6)])
    assert entry["winner"] == "fine-tuned"


def test_screened_out_entries_for_every_kind() -> None:
    preset = {"code": "screened_out", "text": "screened out: no"}
    for p in (proto("consistency"), proto("inventory", inventory={"target": "metric"}), best_proto()):
        entry, used = kinds.of(p).study(p, "D1", effect_items(0.7, 0.6), preset)
        assert entry["reason"] == preset and used == []
        assert kinds.of(p).gap_types(p, "screened_out") == ()


# --- the engine --------------------------------------------------------------------------------------------


def test_engine_runs_each_kind(tmp_path: Path) -> None:
    corpus = make_corpus(tmp_path / "corpus", ("S001", "S002"))
    protocols = {"effect": protocol_data("effect"), "consistency": protocol_data("consistency"),
                 "inventory": protocol_data("inventory", inventory={"target": "metric",
                                                                    "same": {"accuracy": ["answer accuracy"]}}),
                 "best": protocol_data("best", best={"metric": {"canonical": "factual_accuracy", "higher_is_better": True},
                                                     "kinds": BEST_KINDS})}
    answers = {}
    for kind, data in protocols.items():
        path = tmp_path / f"{kind}.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        for strategy in ("gaps", "all"):
            run = engine.run(path, corpus, tmp_path / f"runs-{kind}-{strategy}", selection="regex-only", provider=None,
                             strategy=strategy)
            answer = json.loads((run / "answer.json").read_text(encoding="utf-8"))
            assert (run / "graph.json").exists()
            if strategy == "gaps":
                answers[kind] = answer
    assert answers["effect"]["label"] == "supported" and "kind" not in answers["effect"]
    c = answers["consistency"]
    assert c["kind"] == "consistency" and c["agreeing"] == ["S001", "S002"] and c["disagreeing"] == []
    inv = answers["inventory"]
    assert inv["kind"] == "inventory" and inv["target"] == "metric"
    names = {e["name"]: e for e in inv["entries"]}
    assert names["accuracy"]["papers"] == ["S001", "S002"] and names["accuracy"]["aliases"] == ["answer accuracy"]
    assert [e["name"] for e in inv["entries"]] == sorted(names, key=str.casefold)
    b = answers["best"]
    assert b["kind"] == "best" and b["wins"] == {"rag": 2} and b["winner"] == "rag"
    assert [s["values"] for s in b["studies"]] == [{"rag": 0.71, "baseline": 0.62}, {"rag": 0.665, "baseline": 0.58}]
