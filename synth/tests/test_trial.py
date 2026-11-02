"""The 5-paper trial gate (plan 2 Task 7): `synth build --renderer llm` is refused unless `trial.json` passed on the
recipe as it is now. The models are scripted (no live call): the writer returns the template paper of the study the
plan names, the blind reader replies in the recipe's schema."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

from synth import cli, corpus, truth
from synth.corpus import gate, level_of, trial
from synth.levels import LEVELS
from synth.recipe import load_recipe
from synth.render_llm import LlmRenderer
from synth.render_template import render_study

from .conftest import kept_registry
from .test_fidelity_schema import reply_of

FIXTURES = Path(__file__).resolve().parents[2] / "evidence" / "tests" / "fixtures"
GATE_ERROR = "ERROR: no passing 5-paper trial for this generator.yaml (run synth trial)"


def copy_fixture(tmp_path: Path) -> Path:
    shutil.copytree(FIXTURES / "drugtoy", tmp_path / "drugtoy")
    return tmp_path


def touch_recipe(root: Path) -> None:
    path = root / "drugtoy" / "generator.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "\n# a changed recipe is a new recipe\n", encoding="utf-8")


def papers_of(root: Path, seed: int = 0) -> dict:
    """The template paper of each of the trial's studies, by paper id."""
    recipe = load_recipe("drugtoy", root=root)
    with kept_registry():
        studies = truth.generate(seed, 5, None, truth.default_spec(recipe), recipe=recipe, preset="builds_on")
    return {s.study_id: render_study(s, level_of(s, studies, LEVELS), seed) for s in studies}


def answer(info, args):
    if info.output_tools:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])
    return ModelResponse(parts=[TextPart(json.dumps(args))])


def llm_renderer(tmp_path: Path, root: Path | None = None, verify: bool = True, spoil: bool = False) -> LlmRenderer:
    papers = papers_of(root or FIXTURES) if (verify or spoil) else {}

    def last_prompt(messages) -> str:
        return str([p.content for m in messages for p in m.parts if isinstance(p, UserPromptPart)][-1])

    def write(messages, info):
        plan = json.loads(last_prompt(messages).removeprefix("Rendering plan:\n").split("\n\nYour previous")[0])
        text = papers[plan["paper"]].text
        return answer(info, {"markdown": text.replace("Discussion", "Notes") if spoil else text})

    def read(messages, info):
        text = last_prompt(messages).removeprefix("Paper:\n\n")
        return answer(info, reply_of(next(r.plan for r in papers.values() if r.text == text)))

    return LlmRenderer(FunctionModel(write, model_name="fake-writer"), tmp_path / "cache.jsonl", attempts=2,
                       verify_model=FunctionModel(read, model_name="fake-reader") if verify else None,
                       statements=False)


def test_build_refused_without_trial(tmp_path, capsys):
    code = cli.main(["build", "--domain", "drugtoy", "--root", str(FIXTURES), "--name", "x", "--seed", "1",
                     "--renderer", "llm", "--model", "exchange:w", "--out", str(tmp_path)])
    assert code == 2
    assert GATE_ERROR in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


def test_trial_needs_a_verify_model(tmp_path):
    with pytest.raises(SystemExit, match="verify"):
        trial("drugtoy", renderer=llm_renderer(tmp_path, verify=False), root=copy_fixture(tmp_path / "d"))
    assert not (tmp_path / "d" / "drugtoy" / "trial.json").exists()


def test_trial_records_recipe_hash_and_stale_trial_refused(tmp_path):
    root = copy_fixture(tmp_path / "d")
    assert gate("drugtoy", root=root) is False          # no trial yet
    t = trial("drugtoy", renderer=llm_renderer(tmp_path, root), root=root)
    assert t["passed"], t["fidelity"]
    assert t["recipe_sha256"] == load_recipe("drugtoy", root=root).sha256
    assert (t["studies"], t["levels"], t["renderer"]) == (5, ["mixed"], "llm")
    assert len(t["fidelity"]) == 5 and all(f["ok"] for f in t["fidelity"])
    assert all([c["name"] for c in b["checks"]] == list(corpus.BLIND_CHECKS) for b in t["blind"])
    assert json.loads((root / "drugtoy" / "trial.json").read_text(encoding="utf-8")) == t
    assert gate("drugtoy", root=root) is True
    touch_recipe(root)
    assert gate("drugtoy", root=root) is False


def test_a_paper_that_fails_fails_the_trial_and_the_gate(tmp_path):
    root = copy_fixture(tmp_path / "d")
    t = trial("drugtoy", renderer=llm_renderer(tmp_path, root, spoil=True), root=root)
    assert t["passed"] is False and not all(f["ok"] for f in t["fidelity"])
    assert gate("drugtoy", root=root) is False


def test_the_template_renderer_is_not_gated(tmp_path, capsys):
    code = cli.main(["build", "--domain", "drugtoy", "--root", str(FIXTURES), "--name", "x", "--seed", "1",
                     "--studies", "3", "--levels", "explicit", "--preset", "builds_on", "--out", str(tmp_path)])
    assert code == 0 and GATE_ERROR not in capsys.readouterr().err
