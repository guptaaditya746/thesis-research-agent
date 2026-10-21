"""A1: the measurement bound follows the metric's scale, not the model's yes/no on `fraction`
(diagnostic: tests/EV1/diagnostics/proposal/frame.json has factual_accuracy and accuracy as `fraction: false`)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from evidence import engine
from evidence.propose import critic, draft, frame
from evidence.propose.common import dump_yaml, read_yaml
from evidence.propose.frame import Outcome
from evidence.protocol import parse

from .conftest import PROTOCOL, corpus_of

ROOT = Path(__file__).resolve().parents[2]
EV1 = ROOT / "tests" / "EV1"
HAND = PROTOCOL
RATE = {"factual_accuracy", "hallucination_rate", "factscore", "accuracy"}


def template() -> dict[str, Any]:
    return read_yaml(HAND)


def live_frame() -> frame.Frame:
    return frame.load(EV1 / "diagnostics/proposal/frame.json")


def frame_with(*outcomes: Outcome) -> frame.Frame:
    f = live_frame()
    return f.model_copy(update={"outcomes": list(outcomes)})


def bound_values(protocol_dict: dict[str, Any]) -> list[str]:
    bounds = protocol_dict["evidence_types"]["measurement"]["bounds"]
    return [v for b in bounds for v in b["when"]["values"]]


def protocol_without_bounds(f: frame.Frame):
    protocol_dict, _ = draft.build(f, template(), "p")
    protocol_dict["evidence_types"]["measurement"]["bounds"] = []
    return parse(dump_yaml(protocol_dict))


def accepted_values(protocol_path: Path, text: str, tmp: Path) -> list[float]:
    run = engine.run(protocol_path, corpus_of(tmp / "c", {"P": text}), tmp / "r", selection="regex-only", provider=None)
    import json
    items = [json.loads(x) for x in (run / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    return sorted(i["fields"]["value"] for i in items if i["evidence_type"] == "measurement")


def test_a_legacy_frame_with_fraction_loads() -> None:
    f = live_frame()
    acc = next(o for o in f.outcomes if o.canonical == "factual_accuracy")
    assert acc.scale == "other" and acc.fraction is False
    rate = next(o for o in f.outcomes if o.canonical == "hallucination_rate")
    assert rate.scale == "fraction" and rate.fraction is True


def test_a_scale_wins_over_a_legacy_fraction_key() -> None:
    o = Outcome.model_validate({"canonical": "x", "label": "x", "higher_is_better": True, "scale": "count", "fraction": True})
    assert o.scale == "count"


def test_rate_like_outcomes_get_the_unit_bound_even_when_the_model_says_not_a_fraction() -> None:
    protocol_dict, _ = draft.build(live_frame(), template(), "p")
    assert set(bound_values(protocol_dict)) >= RATE


def test_the_generated_protocol_rejects_175_percent_like_the_hand_protocol(tmp_path: Path) -> None:
    protocol_dict, _ = draft.build(live_frame(), template(), "p")
    generated = tmp_path / "generated.yaml"
    generated.write_text(dump_yaml(protocol_dict), encoding="utf-8")
    text = ("# Invalid accuracy\nThe RAG model attains factual accuracy of 175%. "
            "The closed-book model attains factual accuracy of 60%.\n")
    assert accepted_values(generated, text, tmp_path / "g") == accepted_values(HAND, text, tmp_path / "h") == [0.6]


def test_a_score_on_another_scale_gets_no_unit_bound() -> None:
    f = frame_with(Outcome(canonical="human_score", label="human score", higher_is_better=True, scale="score"))
    protocol_dict, _ = draft.build(f, template(), "p")
    assert "human_score" not in bound_values(protocol_dict)


def test_rate_like_follows_the_scale_then_the_name() -> None:
    def o(scale: str, label: str = "thing", synonyms: list[str] | None = None) -> Outcome:
        return Outcome.model_validate({"canonical": "thing", "label": label, "higher_is_better": True, "scale": scale,
                                       "synonyms": [{"term": s} for s in synonyms or []]})
    assert draft.rate_like(o("percent")) and draft.rate_like(o("fraction"))
    assert not draft.rate_like(o("count", "accuracy")) and not draft.rate_like(o("score", "accuracy"))
    assert draft.rate_like(o("other", "exact match")) and draft.rate_like(o("other", "thing", ["error rate"]))
    assert not draft.rate_like(o("other", "latency"))


def test_critic_flags_a_rate_like_outcome_without_a_bound() -> None:
    f = live_frame()
    ok, msg = critic.bounds_cover_rate_metrics(protocol_without_bounds(f), f)
    assert not ok and "factual_accuracy" in msg
    protocol_dict, _ = draft.build(f, template(), "p")
    ok, _ = critic.bounds_cover_rate_metrics(parse(dump_yaml(protocol_dict)), f)
    assert ok
