"""The cards prompt describes what the engine does: every option carries an `effect`, the prompt shows it, and a
rationale that contradicts it is flagged (advisory)."""
from __future__ import annotations

from pathlib import Path

import yaml

from evidence.propose import cards
from evidence.propose.common import read_json

from .propose_support import Scripted, flow

LIVE = Path(__file__).resolve().parents[2] / "tests" / "EV1" / "diagnostics" / "proposal" / "decisions.yaml"


def _live_reason(card: str) -> str:
    entries = yaml.safe_load(LIVE.read_text(encoding="utf-8"))["decisions"]
    return next(e["reason"] for e in entries if e["card"] == card).removeprefix("default: ")


def test_every_option_has_an_effect_and_the_prompt_shows_it(tmp_path: Path) -> None:
    model = Scripted()
    d = flow(tmp_path / "p", model, until="cards")
    shown = read_json(d / "cards.json")["cards"]
    assert [o["id"] for c in shown for o in c["options"] if not o.get("effect")] == []
    prompt = model.prompts[model.calls.index("cards")]
    for c in shown:
        for o in c["options"]:
            assert o["effect"] in prompt
    assert "not a significance test" in prompt and "chunk and top_k are ignored" in prompt


def test_a_fixed_option_without_an_effect_is_refused(tmp_path: Path, monkeypatch) -> None:
    text = cards.CARDS_FILE.read_text(encoding="utf-8").replace('      effect: "the whole document; chunk and top_k are ignored"\n', "")
    broken = tmp_path / "cards.yaml"
    broken.write_text(text, encoding="utf-8")
    monkeypatch.setattr(cards, "CARDS_FILE", broken)
    try:
        cards.definitions()
    except AssertionError as exc:
        assert "effect" in str(exc)
    else:
        raise AssertionError("an option without an effect was accepted")


def test_the_live_rationales_are_flagged(tmp_path: Path) -> None:
    model = Scripted()
    model.cards["min_effect"]["rationale"] = _live_reason("min_effect")
    model.cards["locate"]["rationale"] = _live_reason("locate")
    d = flow(tmp_path / "p", model, until="cards")
    flags = read_json(d / "cards.json")["rationale_contradicts_effect"]
    assert {(f["card"], f["option"]) for f in flags} == {("min_effect", "draft"), ("locate", "draft")}
    assert {f["term"].lower() for f in flags} >= {"significance"}


def test_a_rationale_that_follows_the_effect_is_not_flagged(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="cards")
    assert read_json(d / "cards.json")["rationale_contradicts_effect"] == []


def test_chunking_is_no_contradiction_for_bm25() -> None:
    assert cards.contradictions([{"id": "locate", "default": "bm25", "rationale": "chunks of 1500, top 6",
                                  "options": [{"id": "bm25", "value": {"strategy": "bm25", "params": {}}}]}]) == []


def test_cards_v1_is_kept() -> None:
    assert (Path(cards.__file__).parent / "prompts" / "cards-v1.md").exists() and cards.PROMPT == "cards-v2.md"
