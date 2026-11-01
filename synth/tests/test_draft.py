"""synth.draft: the paper count, the held-out and invented-name refusals, the quote check, the provenance merge.
Every model is scripted; none is a live call."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from evidence.pack import DOMAINS
from modelcall import ModelCallError
from synth.draft import draft, heldout_ids
from synth.recipe import load_recipe

HELDOUT = {"PMC1234567"}
BASE = yaml.safe_load((DOMAINS / "rag" / "generator.yaml").read_text(encoding="utf-8"))
BASE.pop("sha256", None)


def papers_dir(tmp_path: Path, n: int, first_text: str | None = None) -> Path:
    folder = tmp_path / "papers"
    folder.mkdir(exist_ok=True)
    for i in range(n):
        text = first_text if i == 0 and first_text else f"Paper {i} reports a trial. Arms held many people."
        (folder / f"paper{i}.txt").write_text(text, encoding="utf-8")
    return folder


def recipe_data(thing: str = "zorvex") -> dict:
    data = json.loads(json.dumps(BASE))
    data["network"] = {"things": [thing, "qelinol"], "reference": "qelinol", "edges": [[thing, "qelinol"]],
                       "contexts": ["adult ward"]}
    return data


def scripted(*replies: dict) -> FunctionModel:
    """A model that answers each call with the next reply (the last one repeats)."""
    calls = []

    def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        reply = replies[min(len(calls), len(replies) - 1)]
        calls.append(reply)
        if info.output_tools:
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, reply)])
        return ModelResponse(parts=[TextPart(json.dumps(reply))])
    model = FunctionModel(answer, model_name="fake")
    model.calls = calls  # type: ignore[attr-defined]
    return model


def scripted_recipe(thing: str = "zorvex") -> FunctionModel:
    return scripted(recipe_data(thing))


def scripted_quotes(quote: str = "Arms held many people.") -> FunctionModel:
    return scripted({"quotes": [{"field": "reporting.arm_size", "value": "many", "quote": quote}]})


SCRIPTED = scripted({})     # a model whose answer is never valid: a test that reaches it fails


def run(tmp_path: Path, folder: Path, model=None, verify=None, **kw) -> Path:
    return draft("toy", folder, model=model or SCRIPTED, verify_model=verify or SCRIPTED,
                 cache=tmp_path / "c.jsonl", root=tmp_path / "domains", heldout=kw.pop("heldout", HELDOUT), **kw)


def test_draft_needs_five_to_ten_papers(tmp_path):
    for n in (4, 11):
        with pytest.raises(ValueError, match="5-10"):
            run(tmp_path, papers_dir(tmp_path, n=n))


def test_heldout_paper_refused(tmp_path):
    with pytest.raises(ValueError, match="held out"):
        run(tmp_path, papers_dir(tmp_path, n=5, first_text="PMCID: PMC1234567"))
    assert not SCRIPTED.calls                                   # refused before any model call


def test_heldout_id_in_file_name_refused(tmp_path):
    folder = papers_dir(tmp_path, n=5)
    (folder / "paper0.txt").rename(folder / "PMC1234567.txt")
    with pytest.raises(ValueError, match="held out"):
        run(tmp_path, folder)


def test_real_drug_name_refused(tmp_path):
    with pytest.raises(ValueError, match="invented"):
        run(tmp_path, papers_dir(tmp_path, n=5, first_text="Metformin was given."), model=scripted_recipe("metformin"))
    assert not (tmp_path / "domains/toy/generator.yaml").exists()


def test_a_name_of_a_side_is_checked_too(tmp_path):
    with pytest.raises(ValueError, match="invented"):
        run(tmp_path, papers_dir(tmp_path, n=5, first_text="A closed-book model was used."), model=scripted_recipe())


def test_draft_is_logged_in_provenance(tmp_path):
    out = run(tmp_path, papers_dir(tmp_path, n=5), model=scripted_recipe(), verify=scripted_quotes())
    prov = json.loads((tmp_path / "domains/toy/provenance.json").read_text())
    gen = prov["generator"]
    assert len(gen["papers"]) == 5 and gen["prompt_sha256"]
    assert gen["quotes"][0]["quote"] == "Arms held many people."
    assert gen["model"] == "fake" and gen["calls"].endswith("c.jsonl")
    recipe = load_recipe("toy", tmp_path / "domains")             # what was written is a valid recipe
    assert out.name == "generator.yaml" and recipe.network.things == ["zorvex", "qelinol"]


def test_provenance_keeps_what_other_writers_put_there(tmp_path):
    folder = tmp_path / "domains/toy"
    folder.mkdir(parents=True)
    (folder / "provenance.json").write_text(json.dumps({"words": {"source": "w"}, "generator": {"source": "g"}}))
    run(tmp_path, papers_dir(tmp_path, n=5), model=scripted_recipe(), verify=scripted_quotes())
    prov = json.loads((folder / "provenance.json").read_text())
    assert prov["words"] == {"source": "w"} and prov["generator"]["source"] == "g" and prov["generator"]["papers"]


def test_quote_not_in_a_paper_refused(tmp_path):
    with pytest.raises(ValueError, match="verbatim"):
        run(tmp_path, papers_dir(tmp_path, n=5), model=scripted_recipe(), verify=scripted_quotes("Made up sentence."))
    assert not (tmp_path / "domains/toy/generator.yaml").exists()


def test_invalid_draft_goes_back_once_with_the_error(tmp_path):
    bad = recipe_data()
    bad["contexts"] = ["ward 3"]                                  # a digit in a name
    model = scripted(bad, recipe_data())
    run(tmp_path, papers_dir(tmp_path, n=5), model=model, verify=scripted_quotes())
    assert len(model.calls) == 2


def test_two_invalid_drafts_fail(tmp_path):
    bad = recipe_data()
    bad["contexts"] = ["ward 3"]
    with pytest.raises(ModelCallError, match="retries"):
        run(tmp_path, papers_dir(tmp_path, n=5), model=scripted(bad), verify=scripted_quotes())


def test_an_existing_recipe_is_not_replaced(tmp_path):
    (tmp_path / "domains/toy").mkdir(parents=True)
    (tmp_path / "domains/toy/generator.yaml").write_text("x: 1")
    with pytest.raises(ValueError, match="exists"):
        run(tmp_path, papers_dir(tmp_path, n=5))


def test_the_shipped_heldout_file_reads():
    assert isinstance(heldout_ids(), set)
