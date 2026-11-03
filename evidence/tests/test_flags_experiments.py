"""synthesis.flag keys duplicates on the paper's experiment (experiments.attach): the same numbers in two settings are
two findings; a run without an experiment map flags as before."""
from __future__ import annotations

from evidence import synthesis
from evidence.contract import Item, Span
from evidence.experiments import attach
from evidence.protocol import load
from evidence.records import Experiment, item

from .conftest import PROTOCOL

PROTO = load(PROTOCOL)


def span(start: int, end: int, role: str = "value") -> Span:
    return Span(role=role, selector={"file": "p.md", "start": start, "end": end, "exact": "x", "sha256": "0" * 64})


def value(doc: str, v: float, start: int) -> Item:
    return Item.build("measurement", {"value": v, "dataset": None}, [span(start, start + 3)], {}, 1.0)


def experiment(doc: str, label: str, dataset: str, start: int) -> Item:
    return item(Experiment(exp_id=f"ex-{doc}-{label}", document=doc, label=label, setting={"dataset": dataset},
                           span=span(start, start + 5, "experiment")))


def study(doc: str, t: Item, c: Item) -> dict:
    return {"document": doc, "direction": "supports", "delta": 0.1, "metric": "factual_accuracy",
            "treatment": {"value": t.fields["value"], synthesis.SIDE_VALUE: t.item_id},
            "control": {"value": c.fields["value"], synthesis.SIDE_VALUE: c.item_id}, "author_claim": None}


def world(settings: tuple[str | None, str | None]) -> tuple[list[dict], dict[str, list[Item]]]:
    studies, items = [], {}
    for doc, dataset in zip(("A", "B"), settings):
        t, c = value(doc, 0.7, 100), value(doc, 0.6, 200)
        mine = [t, c] + ([experiment(doc, "exp", dataset, 10)] if dataset else [])
        items[doc] = mine
        studies.append(study(doc, t, c))
    return studies, items


def test_same_numbers_in_two_settings_are_two_findings() -> None:
    studies, items = world(("NQ", "TriviaQA"))
    assert synthesis.flag(PROTO, studies, items)["duplicate"] == []


def test_same_numbers_in_the_same_setting_are_a_duplicate() -> None:
    studies, items = world(("NQ", "NQ"))
    assert synthesis.flag(PROTO, studies, items)["duplicate"] == ["B"]


def test_without_an_experiment_map_flags_as_before() -> None:
    studies, items = world((None, None))
    assert synthesis.flag(PROTO, studies, items)["duplicate"] == ["B"]
    assert synthesis.flag(PROTO, world((None, None))[0])["duplicate"] == ["B"]


def test_attach_is_what_picks_the_experiment() -> None:
    _, items = world(("NQ", "NQ"))
    exp = Experiment(exp_id="ex-A-exp", document="A", label="exp", setting={"dataset": "NQ"}, span=span(10, 15, "experiment"))
    assert attach(items["A"][0], [exp]) == "ex-A-exp"
