"""The generator reads its topic words from the recipe (domains/<name>/generator.yaml): the rag set is what it was
before the words moved, the filled prompts are the committed v2 texts, and no vocabulary module is left."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from modelcall import load_prompt
from synth import corpus, render_llm, truth
from synth.recipe import load_recipe
from synth.render_template import TemplateRenderer

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
# Pinned after the move (preflight P8): sha256 of repr(generate(seed, 6)) for seeds 1-3, and of a template build
# (name r, seed 1, 6 studies) file by file, corpus.json without `generator.code_sha256`. They equal the set and
# the papers built before the move (checked by hand when pinned); Tasks 4-5 assert them again.
PINS = Path(__file__).resolve().parent / "data" / "rag_set_sha256.json"


def build_digests(out: Path) -> dict[str, str]:
    """sha256 of every file of a build under `out`, corpus.json without the code hash (it moves with any edit)."""
    digests = {}
    for p in sorted(out.rglob("*")):
        if not p.is_file():
            continue
        data = p.read_bytes()
        if p.name == "corpus.json":
            meta = json.loads(data)
            del meta["generator"]["code_sha256"]
            data = corpus.dump(meta)
        digests[p.relative_to(out).as_posix()] = hashlib.sha256(data).hexdigest()
    return digests


def test_rag_build_from_recipe_passes_fidelity(tmp_path):
    out = corpus.build(name="r", seed=1, studies=6, renderer=TemplateRenderer(), out=tmp_path)
    assert out["excluded"] == {}


def test_rag_set_and_build_are_pinned(tmp_path):
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    assert {str(s): hashlib.sha256(repr(truth.generate(s, 6)).encode()).hexdigest() for s in (1, 2, 3)} == pins["sets"]
    corpus.build(name="r", seed=1, studies=6, renderer=TemplateRenderer(), out=tmp_path)
    assert build_digests(tmp_path) == pins["build"]


def test_build_records_the_recipe(tmp_path):
    corpus.build(name="r", seed=1, studies=2, levels=["explicit"], renderer=TemplateRenderer(), out=tmp_path)
    meta = json.loads((tmp_path / "r-explicit" / "corpus.json").read_text(encoding="utf-8"))
    recipe = load_recipe("rag")
    assert meta["recipe"] == {"domain": "rag", "sha256": recipe.sha256}
    assert meta["generator"]["version"] == corpus.GENERATOR_VERSION == "3"


def test_generate_defaults_to_the_default_recipe():
    assert truth.generate(1, 6) == truth.generate(1, 6, recipe=load_recipe("rag"))
    assert all(s.recipe.domain == "rag" for s in truth.generate(1, 3))


def test_no_vocab_module():
    assert importlib.util.find_spec("synth.vocab") is None


def test_filled_prompts_have_no_placeholder():
    assert "<<" not in render_llm.instructions(load_recipe("rag"))


def test_filled_v3_prompts_are_the_v2_texts():
    """Filled from the rag recipe, the v3 templates are the committed texts they replace, byte for byte, so the
    prompt hashes (and cached calls) of the rag pack do not move."""
    rag = load_recipe("rag")
    assert render_llm.instructions(rag) == load_prompt(PROMPTS / "render-v2.txt").text
    assert render_llm.statement_instructions(rag) == load_prompt(PROMPTS / "statements-v1.txt").text
    assert render_llm.blind_instructions(rag) == load_prompt(PROMPTS / "blind-v2.txt").text
