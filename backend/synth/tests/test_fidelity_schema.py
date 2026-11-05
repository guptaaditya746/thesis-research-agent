"""Rendering the new facts and checking them by the recipe's schema (plan 2 Task 6): a drug paper writes its byline,
dependency sentences (Method), limitation sentences (Discussion), name variants and counts per arm ("41 of 120
patients"); the fidelity checks read the fact types from the ground truth's `types` and the plan, and the blind reader's
reply schema (`blind_model`) comes from the recipe: its context name, its limitation categories, the reuse kinds."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evidence.extractors import abbrev
from modelcall import prompt_sha256
from synth import corpus, fidelity, render_llm, truth
from synth.fidelity import blind_check, blind_model, check_paper
from synth.levelcheck import sentence_of
from synth.levels import make_plan, plan_rng
from synth.recipe import load_recipe
from synth.render_template import TemplateRenderer, render_study
from synth.text import TRUTH_TYPES

from .conftest import kept_registry

FIXTURES = Path(__file__).resolve().parents[2] / "evidence" / "tests" / "fixtures"
DRUGTOY = load_recipe("drugtoy", root=FIXTURES)
RAG = load_recipe("rag")
with kept_registry():                   # loading the drugtoy protocol registers its pack's types
    SPEC = truth.default_spec(DRUGTOY)
    SET = truth.generate(2, 12, recipe=DRUGTOY, spec=SPEC, preset="builds_on")
    # seed 3 copies results ("as reported by"), which seed 2 does not
    COPIES = truth.generate(3, 12, recipe=DRUGTOY, spec=SPEC, preset="builds_on")
# A relevant study with limitations and a dependency on an earlier one
DRUG_STUDY = next(s for s in SET if s.relevant and s.limitations and s.dependencies)
LEVELS = ("explicit", "paraphrased", "distributed", "complex", "contradictory")


def ok(checks: list[fidelity.Check], name: str) -> bool:
    return next(c for c in checks if c.name == name).ok


def relocate(text: str, plan) -> list:
    """The placements the LLM renderer finds in a text (`render_llm.locate`)."""
    return render_llm.locate(text, plan)[0]


def run(coro):
    return asyncio.run(coro)


def reply_of(plan, drop: str | None = None) -> dict:
    """What a perfect blind reader returns for the paper of `plan`, without the field `drop`."""
    out = {"measurements": [{"condition": plan.cond_name[m.condition], "metric": plan.metric_name[m.metric],
                             plan.recipe.context: m.dataset, "value": m.value} for m in plan.measurements],
           "limitations": [{"condition": plan.cond_name[x.thing], "category": x.category} for x in plan.limitations],
           "cites": [{"label": d.label, "reuses": d.reuses} for d in plan.dependencies]}
    if drop:
        out[drop] = []
    return out


def scripted_blind(drop: str | None = None, study: truth.Study = DRUG_STUDY, level: str = "explicit", seed: int = 1):
    """A scripted blind reader (no live model) for the paper of `study`: it reads the plan, minus the field `drop`."""
    plan = make_plan(study, level, plan_rng(seed, study.study_id, level))
    model = blind_model(study.recipe)

    async def extract(_text: str):
        return model.model_validate(reply_of(plan, drop))
    return extract


# --- the plan's tests ---------------------------------------------------------------------------------------------

def test_template_drug_papers_pass_every_check(tmp_path):
    out = corpus.build(name="d", seed=2, studies=6, renderer=TemplateRenderer(), out=tmp_path, domain="drugtoy",
                       preset="builds_on", root=FIXTURES)
    assert out["excluded"] == {}


def test_missing_limitation_sentence_fails(tmp_path):
    r = render_study(DRUG_STUDY, "explicit", 1)
    text = r.text.replace(r.plan.limitations[0].sentence, "")
    assert not ok(check_paper(text, r.plan, relocate(text, r.plan), []), "limitations_placed")


def test_blind_reader_must_return_count_values_and_limitations():
    r = render_study(DRUG_STUDY, "explicit", 1)
    checks = run(blind_check(r.text, r.plan, scripted_blind(drop="limitations")))
    assert not ok(checks, "blind_limitations") and ok(checks, "blind_reextraction")


def test_blind_schema_uses_recipe_context_name():
    assert "population" in blind_model(DRUGTOY).model_json_schema()["$defs"]["BlindMeasurement"]["properties"]


# --- more ---------------------------------------------------------------------------------------------------------

def test_every_level_of_many_drug_studies_passes_with_its_planted_facts():
    assert {d.reuses for s in SET + COPIES for d in s.dependencies} == {"method", "dataset", "result"}
    for s, seed in [*((s, 2) for s in SET), *((s, 3) for s in COPIES)]:
        for level in LEVELS:
            r = render_study(s, level, seed)
            assert r.fidelity.ok, (s.study_id, level, [c for c in r.fidelity.checks if not c.ok])
            roles = {p.role for p in r.placements}
            assert {"study_label", "limitation"} <= roles and ("dependency" in roles) == bool(s.dependencies)


def test_the_planted_sentences_sit_in_their_sections_once():
    r = render_study(DRUG_STUDY, "explicit", 1)
    for x, section in [*((x, "Discussion") for x in r.plan.limitations), *((d, "Method") for d in r.plan.dependencies)]:
        assert r.text.count(x.sentence) == 1
        assert render_llm.levelcheck.section_at(r.text, r.text.index(x.sentence)) == section
    assert r.text.split("\n")[2] == DRUG_STUDY.label            # the byline, under the title


def test_a_dependency_sentence_moved_out_of_method_or_written_twice_fails():
    r = render_study(DRUG_STUDY, "explicit", 1)
    d = r.plan.dependencies[0].sentence
    moved = r.text.replace(" " + d, "").replace("\n## Conclusion\n", f"\n## Conclusion\n\n{d}\n")
    assert not ok(check_paper(moved, r.plan, relocate(moved, r.plan), []), "dependencies_placed")
    twice = r.text.replace("\n## Conclusion\n", f"\n## Conclusion\n\n{d}\n")
    assert "occurs 2 times" in next(c for c in check_paper(twice, r.plan, r.placements, []) if c.name ==
                                    "dependencies_placed").detail


def test_a_missing_byline_fails_facts_rendered():
    r = render_study(DRUG_STUDY, "explicit", 1)
    text = r.text.replace(DRUG_STUDY.label + "\n", "", 1)
    checks = check_paper(text, r.plan, relocate(text, r.plan), [])
    assert not ok(checks, "facts_rendered") and f"{DRUG_STUDY.study_id}.b1 has no study_label" in \
        next(c for c in checks if c.name == "facts_rendered").detail


def test_facts_rendered_follows_the_truth_types():
    plan = render_study(DRUG_STUDY, "explicit", 1).plan
    assert set(TRUTH_TYPES) >= {"condition", "metric", "measurement", "author_claim", "limitation", "dependency",
                                "study_label"}
    assert corpus.TRUTH_TYPES is TRUTH_TYPES
    assert plan.facts("limitations") == [x.id for x in DRUG_STUDY.limitations]
    assert plan.facts("study_label") == [f"{DRUG_STUDY.study_id}.b1"]


def test_explicit_drug_values_are_counts_of_the_arm_and_a_wrong_count_fails():
    r = render_study(DRUG_STUDY, "explicit", 1)
    values = [p for p in r.placements if p.role == "value"]
    assert values and all(p.fmt == "k_of_n" and p.exact.endswith(" patients") for p in values)
    p = values[0]
    k, _, rest = p.exact.partition(" of ")
    wrong = f"{int(k) + 1} of {rest}"
    bad = r.placements[:]
    bad[bad.index(p)] = type(p)(p.fact, p.role, p.paper, p.start, p.start + len(wrong), wrong, p.fmt)
    assert fidelity.values_match(r.plan, bad)
    assert not fidelity.values_match(r.plan, r.placements)


def test_paraphrased_drug_papers_mix_counts_and_percent():
    fmts = {p.fmt for s in SET if s.relevant for p in render_study(s, "paraphrased", 2).placements if p.role == "value"}
    assert fmts == {"k_of_n", "pct"}


def test_a_hereafter_variant_is_defined_at_the_start_of_its_sentence_and_read_by_abbrev():
    s, cid, form = next((s, c.id, c.variants[0][1]) for s in SET for c in s.conditions
                        if c.variants and c.variants[0][0] == "hereafter")
    r = render_study(s, "explicit", 2)
    label = r.plan.condition(cid).label
    assert f". {label} (hereafter {form}) " in r.text
    assert any(d.long == label and d.short == form for d in abbrev.definitions(r.text))
    assert r.plan.cond_name[cid] == form and label in r.plan.cond_aliases[cid]
    assert render_llm.locate(r.text, r.plan)[2] == []
    buried = r.text.replace(f". {label} (hereafter {form}) ", f". We include {label} (hereafter {form}), which ")
    assert any("must begin its sentence" in p for p in render_llm.locate(buried, r.plan)[2])


def test_a_code_name_passes_the_number_checks():
    s, cid, form = next((s, c.id, c.variants[0][1]) for s in SET for c in s.conditions
                        if c.variants and c.variants[0][0] == "code_name")
    r = render_study(s, "explicit", 2)
    assert f"({form})" in r.text and form.split("-")[1] in r.text
    assert ok(r.fidelity.checks, "added_numbers") and ok(r.fidelity.checks, "stray_numbers")


def test_the_paraphrased_level_writes_no_variant_and_the_truth_says_so():
    s = next(s for s in SET if any(c.variants for c in s.conditions))
    for level, has in (("explicit", True), ("paraphrased", False)):
        r = render_study(s, level, 2)
        record = corpus.study_truth(r, SPEC)
        assert any("variants" in c for c in record["conditions"]) is has
        assert [x["sentence"] for x in record["limitations"]] == [x.sentence for x in r.plan.limitations]
        assert all(x["sentence"] in r.text for x in record["limitations"])


def test_blind_reader_must_return_the_cited_labels_and_the_categories():
    r = render_study(DRUG_STUDY, "explicit", 1)
    checks = run(blind_check(r.text, r.plan, scripted_blind()))
    assert all(c.ok for c in checks) and [c.name for c in checks][-2:] == ["blind_limitations", "blind_dependencies"]
    checks = run(blind_check(r.text, r.plan, scripted_blind(drop="cites")))
    assert not ok(checks, "blind_dependencies") and ok(checks, "blind_limitations")
    wrong = reply_of(r.plan)
    wrong["limitations"] = [dict(x, category=next(c for c in DRUGTOY.limitations.categories if c != x["category"]))
                            for x in wrong["limitations"]]

    async def misread(_text: str):
        return blind_model(DRUGTOY).model_validate(wrong)
    assert not ok(run(blind_check(r.text, r.plan, misread)), "blind_limitations")


def test_blind_schema_gives_categories_and_reuses_as_enums():
    model = blind_model(DRUGTOY)
    with pytest.raises(ValidationError):
        model.model_validate({"measurements": [], "limitations": [{"condition": "x", "category": "bad_luck"}],
                              "cites": []})
    with pytest.raises(ValidationError):
        model.model_validate({"measurements": [], "limitations": [], "cites": [{"label": "x", "reuses": "idea"}]})


def test_the_rag_blind_schema_and_prompt_hash_do_not_move():
    """Filled from the rag recipe (no limitations, no builds_on, context dataset) the schema is the one the blind
    reader always had: its prompt hash (and so the cached calls) stays."""
    assert blind_model(RAG) is fidelity.BlindExtraction
    assert set(blind_model(RAG).model_fields) == {"measurements"}
    assert prompt_sha256("x", blind_model(RAG)) == "25cbd0da1ed6a1a6ea961244f85c943a3e72be4d8b3e5f3588a9f09b1f1d2e98"


def test_the_drug_prompts_follow_the_recipe():
    blind = render_llm.blind_instructions(DRUGTOY)
    assert "the population and the value" in blind and '"population": ...' in blind
    assert all(c in blind for c in DRUGTOY.limitations.categories) and "method, dataset, result" in blind
    writer = render_llm.instructions(DRUGTOY)
    assert "<<" not in writer and '13. Write the "byline"' in writer and "dataset size" not in writer
    assert '"limitation_sentences"' in render_llm.plain_instructions(DRUGTOY)


def test_plan_json_gives_the_planted_strings_and_locate_finds_them():
    r = render_study(DRUG_STUDY, "explicit", 1)
    planned = render_llm.plan_json(r.plan)
    assert planned["byline"] == {"write_exactly": DRUG_STUDY.label}
    assert [x["write_exactly"] for x in planned["limitation_sentences"]] == [x.sentence for x in r.plan.limitations]
    assert [x["write_exactly"] for x in planned["dependency_sentences"]] == [d.sentence for d in r.plan.dependencies]
    ps, _, problems = render_llm.locate(r.text, r.plan)
    assert problems == []
    assert {(p.fact, p.role) for p in ps} >= {(x.id, "limitation") for x in r.plan.limitations} | {
        (d.id, "dependency") for d in r.plan.dependencies} | {(f"{DRUG_STUDY.study_id}.b1", "study_label")}


def test_a_rag_plan_json_has_no_new_keys():
    s = truth.generate(1, 2)[0]
    planned = render_llm.plan_json(make_plan(s, "explicit", plan_rng(1, s.study_id, "explicit")))
    assert not {"byline", "limitation_sentences", "dependency_sentences"} & set(planned)
    assert all("introduce_exactly" not in c for c in planned["conditions"])


@pytest.mark.parametrize("statements", [False, True])
def test_the_llm_renderer_passes_a_drug_paper_with_a_scripted_writer_and_reader(tmp_path, statements):
    """The LLM path end to end on a drug study, with scripted models (no live call): the writer returns the template
    paper (and, with the statement stage, its Results sentences: counts of the arm), the blind reader replies in the
    recipe's schema."""
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, UserPromptPart
    from pydantic_ai.models.function import FunctionModel

    def respond(info, args):
        if info.output_tools:
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])
        return ModelResponse(parts=[TextPart(json.dumps(args))])

    paper = render_study(DRUG_STUDY, "explicit", 1)

    def sentence(value: str) -> str:
        a, b = sentence_of(paper.text, paper.text.index(value), paper.text.index(value) + len(value))
        return paper.text[a:b + 1]

    def write(messages, info):
        prompt = str([p.content for m in messages for p in m.parts if isinstance(p, UserPromptPart)][-1])
        if prompt.startswith("Statement tasks"):
            tasks = json.loads(prompt.split("\n", 1)[1])["tasks"]
            return respond(info, {"statements": [{"id": t["id"], "text": sentence(t["value"])} for t in tasks]})
        return respond(info, {"markdown": paper.text})

    writer = FunctionModel(write, model_name="fake-writer")
    reader = FunctionModel(lambda m, info: respond(info, reply_of(paper.plan)), model_name="fake-reader")
    renderer = render_llm.LlmRenderer(writer, tmp_path / "cache.jsonl", verify_model=reader, statements=statements)
    r = run(renderer.render_one(DRUG_STUDY, "explicit", 1))
    assert r.fidelity.ok, [c for c in r.fidelity.checks if not c.ok]
    assert [c.name for c in r.fidelity.checks][-2:] == ["blind_limitations", "blind_dependencies"]
    if statements:
        assert r.fidelity.statements == {"rounds": 1, "failed": []}
