"""decisions.yaml as freeze reads it (docs/evidence-system.md Part E): a decision without a reason is refused,
and so are an unknown choice, a value without `custom`, a changed choice still `by: model`, a missing card."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from evidence import cli
from evidence.propose import freeze
from evidence.propose.common import ProposalError

from .propose_support import Scripted, flow


@pytest.fixture
def proposal(tmp_path: Path) -> Path:
    return flow(tmp_path / "p", Scripted(), until="cards")


def edit(d: Path, card: str, **changes: Any) -> None:
    data = yaml.safe_load((d / "decisions.yaml").read_text(encoding="utf-8"))
    for x in data["decisions"]:
        if x["card"] == card:
            for k, v in changes.items():
                if v is None:
                    x.pop(k, None)
                else:
                    x[k] = v
    (d / "decisions.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


@pytest.mark.parametrize("reason", ["", "   ", None])
def test_a_decision_without_a_reason_is_refused(proposal: Path, reason: str | None) -> None:
    edit(proposal, "min_effect", reason=reason)
    with pytest.raises(ProposalError, match="min_effect: a decision without a reason is refused"):
        freeze.run(proposal)
    assert not (proposal / "protocol.yaml").exists() and not (proposal / "proposal.json").exists()


def test_the_cli_exits_2_on_a_refused_decision(proposal: Path, capsys: pytest.CaptureFixture[str]) -> None:
    edit(proposal, "label", reason="")
    assert cli.main(["propose", "freeze", str(proposal)]) == 2
    assert "without a reason" in capsys.readouterr().err
    edit(proposal, "label", reason="default table", by="AG")
    assert cli.main(["propose", "freeze", str(proposal)]) == 0


def test_a_choice_that_is_no_option_is_refused(proposal: Path) -> None:
    edit(proposal, "locate", choice="semantic", by="AG", reason="try it")
    with pytest.raises(ProposalError, match="'semantic' is not an option"):
        freeze.run(proposal)


def test_custom_needs_a_value_in_the_cards_shape(proposal: Path) -> None:
    edit(proposal, "min_effect", choice="custom", by="AG", reason="tighter")
    with pytest.raises(ProposalError, match="min_effect: choice custom needs a `value`"):
        freeze.run(proposal)
    edit(proposal, "min_effect", value={"min_effect": -1})
    with pytest.raises(ProposalError, match="custom needs a `value`"):
        freeze.run(proposal)
    edit(proposal, "min_effect", value={"min_effect": 0.015})
    freeze.run(proposal)


def test_a_value_beside_an_option_is_refused(proposal: Path) -> None:
    edit(proposal, "min_effect", value={"min_effect": 0.5})
    with pytest.raises(ProposalError, match="`value` is only for choice custom"):
        freeze.run(proposal)


def test_a_changed_choice_must_name_who_decided(proposal: Path) -> None:
    edit(proposal, "min_effect", choice="strict")
    with pytest.raises(ProposalError, match="not the model's default"):
        freeze.run(proposal)
    edit(proposal, "min_effect", by="AG", reason="the benchmark's effects are small")
    freeze.run(proposal)


@pytest.mark.parametrize("who", ["Model", "MODEL"])
def test_a_changed_choice_by_the_model_in_any_case_is_refused(proposal: Path, who: str) -> None:
    edit(proposal, "min_effect", choice="strict", by=who)
    with pytest.raises(ProposalError, match="not the model's default"):
        freeze.run(proposal)


def test_every_card_needs_one_decision(proposal: Path) -> None:
    data = yaml.safe_load((proposal / "decisions.yaml").read_text(encoding="utf-8"))
    data["decisions"] = [x for x in data["decisions"] if x["card"] != "pairing"] + [data["decisions"][0]]
    (proposal / "decisions.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ProposalError) as err:
        freeze.run(proposal)
    assert "pairing: no decision" in str(err.value) and "screen: decided twice" in str(err.value)


def test_a_failed_model_call_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                     capsys: pytest.CaptureFixture[str]) -> None:
    from pydantic_ai.models.function import FunctionModel

    from evidence.propose import common

    def broken(messages, info):   # noqa: ANN001, ANN202
        raise ConnectionError("server down, key sk-secret1234")
    monkeypatch.setattr(common.modelcall, "openai_model", lambda alias: FunctionModel(broken, model_name=alias))
    assert cli.main(["propose", "frame", "--question", "Q?", "--out", str(tmp_path / "p")]) == 1
    err = capsys.readouterr().err
    assert "model call failed" in err and "sk-secret1234" not in err
    assert not (tmp_path / "p" / "frame.json").exists()


def test_cards_do_not_overwrite_edited_decisions(tmp_path: Path) -> None:
    model = Scripted()
    d = flow(tmp_path / "p", model, until="cards")
    from evidence.propose import cards
    cards.run(d, model=model.model)             # untouched: made again
    edit(d, "min_effect", reason="checked", by="AG")
    with pytest.raises(ProposalError, match="has been edited"):
        cards.run(d, model=model.model)
