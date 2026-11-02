"""The D34 fallback helper: it writes the pack from the paper texts alone, never opens anything but manifest.json and
papers/*, refuses beside a generator.yaml, and its proposal passes the same code checks and the same verifier as the
agent's. Models are scripted (FunctionModel): no live model."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from evaluation.tests.helpers import guard_corpus
from evidence.pack import load_pack
from packbuilder.helper import helper
from packbuilder.tests.test_agent import P1, P2, PROPOSAL, proposal, reply, scripted_verifier, write_corpus


class Scripted:
    """A helper model that answers `final` and keeps the prompts it was shown."""

    def __init__(self, final: dict[str, Any] = PROPOSAL) -> None:
        self.final, self.prompts = final, []

    def model(self) -> FunctionModel:
        def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            self.prompts.append("\n".join(str(p.content) for m in messages for p in m.parts
                                          if isinstance(p, UserPromptPart)))
            return reply(info, self.final)
        return FunctionModel(answer, model_name="scripted-helper")


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """Two papers and gold files beside them (ground_truth.json, corpus.json with a recipe note); no generator.yaml."""
    root = write_corpus(tmp_path)
    (root / "generator.yaml").unlink()
    (root / "corpus.json").write_text(json.dumps({"recipe": {"readable": ["domains/toy"], "filler": "zebrafish"}}),
                                      encoding="utf-8")
    return root


def run(corpus: Path, tmp_path: Path, model: Any, verify_model: Any = None, name: str = "toy") -> Path:
    return helper(corpus, name, model=model, verify_model=verify_model or scripted_verifier(),
                  cache=tmp_path / "c.jsonl", root=tmp_path / "domains")


def test_helper_reads_only_manifest_and_papers(monkeypatch: pytest.MonkeyPatch, corpus: Path, tmp_path: Path) -> None:
    attempts = guard_corpus(monkeypatch, corpus)
    path = run(corpus, tmp_path, Scripted().model())
    assert attempts == []
    prov = json.loads((path / "provenance.json").read_text(encoding="utf-8"))
    assert prov["words"]["files_read"] == ["manifest.json", "papers/T001.md", "papers/T002.md"]


def test_helper_prompt_holds_only_the_question_and_the_papers(corpus: Path, tmp_path: Path) -> None:
    m = Scripted()
    run(corpus, tmp_path, m.model())
    shown = json.loads(m.prompts[0])
    assert {p["id"]: p["text"] for p in shown["papers"]} == {"T001": P1, "T002": P2}
    assert set(shown) == {"question", "display_keys", "taken_prefixes", "papers"}
    assert "zebrafish" not in m.prompts[0] and "generator" not in m.prompts[0]      # corpus.json is never read


def test_helper_refuses_when_generator_yaml_present_in_the_corpus(corpus: Path, tmp_path: Path) -> None:
    (corpus / "generator.yaml").write_text("{}", encoding="utf-8")
    m = Scripted()
    with pytest.raises(ValueError, match="generator.yaml"):
        run(corpus, tmp_path, m.model())
    assert m.prompts == [] and not (tmp_path / "domains" / "toy" / "pack.yaml").exists()


def test_helper_refuses_when_generator_yaml_present_in_the_pack_folder(corpus: Path, tmp_path: Path) -> None:
    folder = tmp_path / "domains" / "toy"
    folder.mkdir(parents=True)
    (folder / "generator.yaml").write_text("{}", encoding="utf-8")
    m = Scripted()
    with pytest.raises(ValueError, match="generator.yaml"):
        run(corpus, tmp_path, m.model())
    assert m.prompts == [] and not (folder / "pack.yaml").exists()


def test_helper_pack_is_logged_and_loads(corpus: Path, tmp_path: Path) -> None:
    path = run(corpus, tmp_path, Scripted().model())
    prov = json.loads((path / "provenance.json").read_text(encoding="utf-8"))
    assert prov["words"]["by"] == prov["pack"]["by"] == "packbuilder helper (D34)"
    assert prov["words"]["model"] == "scripted-helper" and prov["words"]["tool_calls"] == []
    assert prov["words"]["verify"]["model"] == "scripted-verifier" and prov["words"]["sources"] == PROPOSAL["sources"]
    assert list(load_pack("toy", root=tmp_path / "domains").words.conditions) == ["velmora", "placebo"]


def test_helper_proposal_goes_through_the_code_checks(corpus: Path, tmp_path: Path) -> None:
    bad = proposal(limitation_categories=["small_sample", "high_cost"])      # a category with no source
    with pytest.raises(ValueError, match="fails its checks"):
        run(corpus, tmp_path, Scripted(bad).model())
    assert not (tmp_path / "domains" / "toy" / "pack.yaml").exists()


def test_helper_proposal_goes_through_the_verifier(corpus: Path, tmp_path: Path) -> None:
    path = run(corpus, tmp_path, Scripted().model(), verify_model=scripted_verifier({("small_sample", "limitation")}))
    prov = json.loads((path / "provenance.json").read_text(encoding="utf-8"))
    assert [d["word"] for d in prov["words"]["verify"]["dropped"]] == ["small_sample"]
    assert load_pack("toy", root=tmp_path / "domains").limitation_categories == []


def test_helper_needs_a_verify_model(corpus: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="verify model"):
        helper(corpus, "toy", model=Scripted().model(), cache=tmp_path / "c.jsonl", root=tmp_path / "domains")


def test_a_cached_helper_proposal_makes_no_model_call(corpus: Path, tmp_path: Path) -> None:
    first = Scripted()
    run(corpus, tmp_path, first.model())
    second = Scripted(proposal(display={"treatment": "x", "control": "y"}))      # would fail if it were called
    helper(corpus, "toy", model=second.model(), verify_model=scripted_verifier(), cache=tmp_path / "c.jsonl",
           root=tmp_path / "domains2")                           # same cache and input, a new domains folder
    assert len(first.prompts) == 1 and second.prompts == []
