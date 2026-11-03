"""The experiment map: anchored experiments, the duplicate rule keyed on them, old runs unchanged. Fake LM only."""
from __future__ import annotations

import json

import pytest

from agent.anchor import Index, selector_at
from evidence import experiments, rules, steps
from evidence.contract import Item, Span
from evidence.steps import configure
from modelcall.cache import JsonlCache
from modelcall.dspy_lm import RecordedLM

TEXT = ("Abstract. We compare retrieval with a closed-book model.\n\n"
        "On Natural Questions we compare the two systems. Accuracy was 0.74 with retrieval and 0.61 without.\n\n"
        "On TriviaQA the same comparison gives 0.74 and 0.61 again.\n")
NQ = {"label": "Natural Questions", "quote": "On Natural Questions we compare", "setting": {"dataset": "Natural Questions"}}
TQ = {"label": "TriviaQA", "quote": "On TriviaQA the same comparison", "setting": {"dataset": "TriviaQA"}}


def lm(tmp_path, monkeypatch, reply: list[dict]) -> None:
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    configure(RecordedLM("alias", lambda prompt: json.dumps({"experiments": reply}),
                         cache=JsonlCache(tmp_path / "calls.jsonl")))


def value_at(quote: str, links: dict[str, str] | None = None) -> Item:
    start = TEXT.index(quote)
    span = Span.of("value", selector_at(TEXT, start, start + len(quote), file="p.md"))
    return Item.build("measurement", {"value": 0.74}, [span], links=links)


def test_two_experiments_same_values_not_duplicates(tmp_path, monkeypatch) -> None:
    lm(tmp_path, monkeypatch, [NQ, TQ])
    exps = experiments.map_experiments(TEXT, "p")
    assert [e.label for e in exps] == ["Natural Questions", "TriviaQA"]
    first = experiments.attach(value_at("0.74 with retrieval"), exps)
    second = experiments.attach(value_at("0.74 and 0.61 again"), exps)
    assert first == exps[0].exp_id and second == exps[1].exp_id and first != second
    # same metric and the same two numbers in both: with the map they are two studies, without it one duplicate
    assert rules.duplicates([("a", "accuracy", 0.74, 0.61, first), ("b", "accuracy", 0.74, 0.61, second)]) == {}
    assert rules.duplicates([("a", "accuracy", 0.74, 0.61, first), ("b", "accuracy", 0.74, 0.61, first)]) == {"b": "a"}


def test_old_run_duplicates_unchanged() -> None:
    old = [("a", "accuracy", 0.74, 0.61), ("b", "accuracy", 0.74, 0.61), ("c", "f1", 0.5, 0.4)]
    assert rules.duplicates(old) == {"b": "a"}
    assert rules.duplicates([(*s, None) for s in old]) == {"b": "a"}


def test_unanchored_experiment_rejected(tmp_path, monkeypatch) -> None:
    ghost = {"label": "WebQuestions", "quote": "On WebQuestions we compare", "setting": {"dataset": "WebQuestions"}}
    lm(tmp_path, monkeypatch, [NQ, ghost, {**NQ, "label": "NQ again"}])
    exps = experiments.map_experiments(TEXT, "p")
    assert [e.label for e in exps] == ["Natural Questions"]   # the ghost quote is not in the paper, the repeat adds nothing
    sel = exps[0].span.selector
    assert TEXT[sel["start"]:sel["end"]] == "On Natural Questions we compare"


def test_attach_prefers_setting_matching_the_linked_items(tmp_path, monkeypatch) -> None:
    lm(tmp_path, monkeypatch, [NQ, TQ])
    exps = experiments.map_experiments(TEXT, "p")
    dataset = Item.build("dataset", {"name": "TriviaQA"},
                         [Span.of("name", selector_at(TEXT, TEXT.index("TriviaQA"), TEXT.index("TriviaQA") + 8, file="p.md"))])
    v = value_at("0.74 with retrieval", {"dataset": dataset.item_id})
    assert experiments.attach(v, exps, {dataset.item_id: dataset}) == exps[1].exp_id
    assert experiments.attach(value_at("closed-book"), exps) is None   # before every experiment


def test_stage_items_are_idempotent(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    lm(tmp_path, monkeypatch, [NQ, TQ])
    doc = SimpleNamespace(doc=SimpleNamespace(id="p", file="p.md"), text=TEXT, index=Index(TEXT))
    ctx = SimpleNamespace(dspy_lm=lambda purpose: steps._LM)
    experiments.before_extract(doc, ctx)
    a = experiments.after_document(doc, ctx)
    b = experiments.after_document(doc, ctx)
    assert a == b and {i.evidence_type for i in a} == {"experiment"} and len(a) == 2


def _doc():
    from types import SimpleNamespace
    return SimpleNamespace(doc=SimpleNamespace(id="p", file="p.md"), text=TEXT, index=Index(TEXT))


def test_every_run_records_its_own_map_call(tmp_path, monkeypatch) -> None:
    """Nothing is kept between runs: a second run (own call cache) makes and records its own call."""
    from types import SimpleNamespace

    seen: list[str] = []
    for run in ("a", "b"):
        cache = JsonlCache(tmp_path / f"{run}.jsonl")
        lm_ = RecordedLM("alias", lambda prompt, run=run: seen.append(run) or json.dumps({"experiments": [NQ]}),
                         cache=cache)
        ctx = SimpleNamespace(dspy_lm=lambda purpose, lm_=lm_: lm_)
        experiments.before_extract(_doc(), ctx)
        experiments.after_document(_doc(), ctx)   # the same run again: answered from its cache
    assert seen == ["a", "b"]
    assert all((tmp_path / f"{r}.jsonl").read_text(encoding="utf-8").strip() for r in ("a", "b"))


def test_concurrent_documents_use_their_own_model(tmp_path, monkeypatch) -> None:
    import threading
    import time
    from types import SimpleNamespace

    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    answered: dict[str, list[str]] = {"x": [], "y": []}

    def make(name: str):
        def ask(prompt: str) -> str:
            time.sleep(0.05)      # a slow call: the other thread would configure its model meanwhile
            answered[name].append(name)
            return json.dumps({"experiments": [NQ]})
        return RecordedLM(name, ask, cache=JsonlCache(tmp_path / f"{name}.jsonl"))

    def work(name: str) -> None:
        ctx = SimpleNamespace(dspy_lm=lambda purpose, m=make(name): m)
        for _ in range(3):
            experiments.before_extract(_doc(), ctx)

    threads = [threading.Thread(target=work, args=(n,)) for n in ("x", "y")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert answered == {"x": ["x"], "y": ["y"]}   # each model was asked once, by its own thread, and cached the rest
