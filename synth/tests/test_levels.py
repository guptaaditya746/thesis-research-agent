"""Each difficulty level has its defining property; the fidelity checks catch broken papers."""
from __future__ import annotations

import dataclasses
import re

import pytest

from synth import fidelity, levelcheck, truth
from synth.levels import LEVELS, make_plan, parse_value, plan_rng, write_value
from synth.recipe import default_recipe
from synth.render_template import render, render_study


def papers(level: str, seeds=range(1, 9), n: int = 6):
    for seed in seeds:
        for s in truth.generate(seed, n):
            yield s, render_study(s, level, seed)


@pytest.mark.parametrize("level", LEVELS)
def test_template_papers_pass_every_check(level: str) -> None:
    for _, r in papers(level, range(1, 21), 8):
        bad = [c for c in r.fidelity.checks if not c.ok]
        assert not bad, (r.study.study_id, bad)


def test_explicit_one_sentence_names_condition_metric_dataset() -> None:
    for s, r in papers("explicit"):
        values = [p for p in r.placements if p.role == "value"]
        assert len(values) == len(r.plan.measurements) and "|" not in r.text
        for p in values:
            m = next(m for m in r.plan.measurements if m.id == p.fact)
            a, b = levelcheck.sentence_of(r.text, p.start, p.end)
            sentence = r.text[a:b]
            assert next(c.label for c in s.conditions if c.id == m.condition) in sentence
            assert s.primary.name in sentence and m.dataset in sentence and p.exact.endswith("%")


def test_paraphrased_never_uses_labels_and_varies_formats() -> None:
    formats = set()
    for s, r in papers("paraphrased"):
        low = r.text.lower()
        assert not any(re.search(r"(?<!\w)" + re.escape(c.label.lower()) + r"(?!\w)", low) for c in s.conditions)
        assert s.primary.name.lower() not in low
        fmts = {p.fmt for p in r.placements if p.role == "value"}
        assert len(fmts) >= 2
        formats |= fmts
    assert formats == {"pct", "frac", "count"}


def test_distributed_values_only_in_the_table_codes_defined_far_away() -> None:
    for s, r in papers("distributed"):
        lines = r.text.split("\n")
        table = [ln for ln in lines if ln.startswith("|")]
        prose = "\n".join(ln for ln in lines if not ln.startswith("|"))
        for p in (p for p in r.placements if p.role == "value"):
            assert levelcheck.in_table(r.text, p.start)
            assert p.exact not in prose
        assert all(c.label not in "\n".join(table) for c in s.conditions)
        assert table[0] == f"| System | {s.primary.abbr} (%) |"
        first_table = r.text.index("\n|") + 1
        for c in s.conditions:
            definition = r.text.index(f"we denote it by {c.code}.")
            assert first_table - definition > levelcheck.DISTANCE
        assert f"abbreviate it as {s.primary.abbr}" in prose


def test_complex_has_distractors_two_datasets_and_one_relative_value() -> None:
    for s, r in papers("complex"):
        assert len(r.plan.datasets) == 2 and len(r.plan.metrics) >= 2
        assert len(r.plan.measurements) == len(s.measurements)
        rel = [p for p in r.placements if p.fmt == "relative"]
        assert [p.fact for p in rel] == [s.effect.treatment] and "percentage points" in rel[0].exact
        base = s.value_of(s.effect.control)
        assert parse_value(rel[0].exact, "relative", base) == s.value_of(s.effect.treatment)
        assert "see text" in r.text


def test_contradictory_claim_disagrees_with_the_data() -> None:
    decoys = 0
    for s, r in papers("contradictory"):
        assert r.plan.claim == s.false_claim
        assert r.plan.claim != s.claim
        claims = [p.exact for p in r.placements if p.role == "claim"]
        assert claims == list(r.plan.claim_sentences)
        for d in r.decoys:
            decoys += 1
            assert r.text[d.start:d.end] == d.exact and not levelcheck.in_table(r.text, d.start)
            assert all(abs(d.stated_value - m.value) > truth.DECOY_GAP for m in s.measurements)
    assert decoys > 0


@pytest.mark.parametrize("level", [lv for lv in LEVELS if lv != "contradictory"])
def test_other_levels_claim_agrees(level: str) -> None:
    for s, r in papers(level, range(1, 3)):
        assert r.plan.claim == s.claim and not r.decoys


@pytest.mark.parametrize(("fmt", "value", "text"), [
    ("pct", 0.624, "62.4%"), ("frac", 0.624, "0.624"), ("count", 0.624, "624 out of 1,000"),
    ("cell_pct", 0.071, "7.1"), ("cell_raw", 1.24, "1.24")])
def test_value_formats_round_trip(fmt: str, value: float, text: str) -> None:
    assert write_value(value, fmt) == text and parse_value(text, fmt) == value


def test_relative_round_trip() -> None:
    assert write_value(0.694, "relative", 0.624) == "7.0 percentage points higher"
    assert parse_value("0.3 percentage points lower", "relative", 0.624) == 0.621


def _fixture():
    s = truth.generate(2, 2)[0]
    plan = make_plan(s, "explicit", plan_rng(2, s.study_id, "explicit"))
    text, ps, decoys = render(plan, plan_rng(2, s.study_id, "explicit:text"))
    return plan, text, ps, decoys


def failing(plan, text, ps, decoys) -> set[str]:
    return {c.name for c in fidelity.check_paper(text, plan, ps, decoys) if not c.ok}


def test_values_apart_check_flags_close_true_values() -> None:
    plan, text, ps, decoys = _fixture()
    s = plan.study
    ms = list(s.measurements)
    ms[-1] = dataclasses.replace(ms[-1], value=round(ms[0].value + 0.004, 3))
    close = dataclasses.replace(plan, study=dataclasses.replace(s, measurements=tuple(ms)))
    assert "values_apart" in failing(close, text, ps, decoys)
    assert "values_apart" not in failing(plan, text, ps, decoys)


def test_checks_catch_moved_placement_and_wrong_value() -> None:
    plan, text, ps, decoys = _fixture()
    v = next(i for i, p in enumerate(ps) if p.role == "value")
    moved = [*ps[:v], dataclasses.replace(ps[v], start=ps[v].start + 1, end=ps[v].end + 1), *ps[v + 1:]]
    assert "anchored" in failing(plan, text, moved, decoys)
    p = ps[v]
    wrong = text[:p.start] + "99.9%" + text[p.end:]
    shifted = [dataclasses.replace(q, exact="99.9%") if q is p else q for q in ps]
    assert {"values_match"} <= failing(plan, wrong, shifted, decoys)


def test_checks_catch_stray_number_duplicate_value_and_unrecorded_label() -> None:
    plan, text, ps, decoys = _fixture()
    value = next(p for p in ps if p.role == "value")
    stray = text + f"\nAn earlier system reached {value.exact.rstrip('%')} points.\n"
    assert "stray_numbers" in failing(plan, stray, ps, decoys)
    dup = text + f"\nSee also {value.exact} above.\n"
    assert "values_unique" in failing(plan, dup, ps, decoys)
    label = plan.cond_name[plan.conditions[0].id]
    extra = text + f"\nThe {label} is cheap.\n"
    assert "labels_covered" in failing(plan, extra, ps, decoys)
    assert "facts_rendered" in failing(plan, text, [p for p in ps if p.role != "claim"], decoys)
    assert failing(plan, text, ps, decoys) == set()


def _llm_read(level: str, edit):
    """A template paper changed by `edit(text, plan)` and read back as the LLM renderer reads a paper."""
    from synth.render_llm import locate
    s = truth.generate(4, 3)[1]
    plan = make_plan(s, level, plan_rng(4, s.study_id, level))
    text = edit(render(plan, plan_rng(4, s.study_id, level + ":text"))[0], plan)
    ps, decoys, problems = locate(text, plan)
    assert problems == []
    return text, plan, ps, decoys


def test_a_stray_code_is_not_a_placement() -> None:
    """Review item 9: 'Appendix B' is not condition B."""
    text, plan, ps, decoys = _llm_read("distributed", lambda t, p: t + "\nSee Appendix B and R for details.\n")
    tail = text.rindex("Appendix B")
    assert not [p for p in ps if p.start >= tail]
    assert failing(plan, text, ps, decoys) == set()


@pytest.mark.parametrize(("level", "added"), [
    ("explicit", "\nAn earlier system reached 71.2% on the same split.\n"),
    ("complex", "\nThe gap of 3 points is consistent across seeds.\n"),
    ("distributed", "\nWe used 8 GPUs for every run.\n"),
    ("paraphrased", "\nThe index holds 2,500,000 passages.\n"),
])
def test_added_number_fails(level: str, added: str) -> None:
    """G.2: a number outside the value placements, the decoys and the allowlist is added content."""
    text, plan, ps, decoys = _llm_read(level, lambda t, p: t + added)
    assert failing(plan, text, ps, decoys) & {"added_numbers"} == {"added_numbers"}
    detail = next(c.detail for c in fidelity.check_paper(text, plan, ps, decoys) if c.name == "added_numbers")
    number = re.search(r"\d[\d,.]*", added).group()
    assert repr(number) in detail and f"at {text.index(added) + added.index(number)}" in detail


@pytest.mark.parametrize("allowed", [
    "\nSee Table 1 and Section 3 for details; Figure 2 shows the setup.\n",
    "\n1. First point.\n2. Second point.\n",
    "\nEach benchmark has 1,000 questions.\n",
])
def test_allowlisted_numbers_pass(allowed: str) -> None:
    text, plan, ps, decoys = _llm_read("explicit", lambda t, p: t + allowed)
    assert "added_numbers" not in failing(plan, text, ps, decoys)


def test_distributed_codes_are_allowed_numbers() -> None:
    """The A1-style codes of the recipe (`other_codes`) hold a digit; they are allowed by name, a bare digit is not."""
    s = next(s for seed in range(1, 20) for s in truth.generate(seed, 6) if len(s.conditions) > 2)
    r = render_study(s, "distributed", 1)
    assert "A1" in r.text and r.fidelity.ok
    text = r.text + "\nSee Appendix A1 for details, and part 1 of the supplement.\n"
    assert "added_numbers" in failing(r.plan, text, r.placements, r.decoys)
    detail = next(c.detail for c in fidelity.check_paper(text, r.plan, r.placements, r.decoys) if c.name == "added_numbers")
    assert detail.count(" at ") == 1 and "'1' at" in detail and "part 1" in detail


@pytest.mark.parametrize("sentence", [
    "Retrieval augmentation clearly improves the answers in every setting we tried.",
    "The RAG pipeline reduces hallucinated content.",
    "We find that retrieval does not help on this benchmark.",
    "Our retrieval-augmented variant outperforms the plain generator.",
])
def test_added_claim_fails(sentence: str) -> None:
    """G.2: a second sentence that names retrieval and states an effect (terms.CLAIMS) is an added claim."""
    text, plan, ps, decoys = _llm_read("explicit", lambda t, p: t + "\n" + sentence + "\n")
    assert "added_claims" in failing(plan, text, ps, decoys)
    detail = next(c.detail for c in fidelity.check_paper(text, plan, ps, decoys) if c.name == "added_claims")
    assert repr(sentence) in detail and f"at {text.index(sentence)}" in detail


def test_sentences_without_the_subject_or_without_an_effect_are_not_claims() -> None:
    text, plan, ps, decoys = _llm_read("explicit", lambda t, p: t + "\nThe annotation improved after the second round. "
                                                                   "Retrieval latency is reported separately.\n")
    assert "added_claims" not in failing(plan, text, ps, decoys)


def test_alternative_retrieval_methods_is_not_an_added_claim() -> None:
    text, plan, ps, decoys = _llm_read("explicit", lambda t, p: t +
        "\nThe use of a dense retriever is a standard choice, and we did not explore alternative retrieval methods.\n")
    assert "added_claims" not in failing(plan, text, ps, decoys)


def test_irrelevant_papers_pass_every_check_and_place_nothing() -> None:
    from synth.levels import irrelevant_plan
    for topic in truth.IRRELEVANT_TOPICS:
        for seed in range(1, 6):
            s = truth.irrelevant_study(3, topic, default_recipe())
            r = render_study(s, "explicit", seed)
            assert r.fidelity.ok, [(c.name, c.detail) for c in r.fidelity.checks if not c.ok]
            assert r.placements == [] and r.decoys == [] and r.plan == irrelevant_plan(s, "explicit")
            assert [c.name for c in r.fidelity.checks][-1] == "irrelevant"
            assert r.text == render_study(s, "complex", seed).text     # the same at every level
    with pytest.raises(ValueError):
        irrelevant_plan(truth.generate(1, 1)[0], "explicit")


def test_paraphrased_forbids_the_abbreviation() -> None:
    text, plan, ps, decoys = _llm_read("paraphrased", lambda t, p: t + f"\nWe write {p.metrics[0].abbr} for short.\n")
    assert "level_paraphrased" in failing(plan, text, ps, decoys)


def test_distributed_abbreviation_defined_far_from_the_table() -> None:
    def near_table(t: str, p) -> str:
        at = t.index("\n|") + 1
        q = p.metrics[0]
        return t[:at] + f"Recall that the {q.name} is abbreviated as {q.abbr}.\n\n" + t[at:]
    text, plan, ps, decoys = _llm_read("distributed", near_table)
    assert "level_distributed" in failing(plan, text, ps, decoys)


def test_complex_definition_says_one_table() -> None:
    from synth.levels import DEFINITIONS
    assert "one table per dataset" not in DEFINITIONS["complex"] and "Dataset column" in DEFINITIONS["complex"]


# --- --hard: every experiment in one complex table with an Experiment column --------------------------------

def hard_papers(level: str, seeds=range(1, 4), n: int = 30, **knobs):
    for seed in seeds:
        for s in truth.generate(seed, n, hard=True, **knobs):
            yield s, render_study(s, level, seed)


@pytest.mark.parametrize("level", LEVELS)
def test_hard_template_papers_pass_every_check(level: str) -> None:
    for _, r in hard_papers(level):
        bad = [c for c in r.fidelity.checks if not c.ok]
        assert not bad, (r.study.study_id, bad)
    for _, r in hard_papers(level, range(1, 2), 30, duplicates=3, missing=3, outliers=2, irrelevant=2):
        bad = [c for c in r.fidelity.checks if not c.ok]
        assert not bad, (r.study.study_id, bad)


def test_hard_complex_renders_every_experiment_in_one_table() -> None:
    multi = 0
    for s, r in hard_papers("complex"):
        table = [ln for ln in r.text.split("\n") if ln.startswith("|")]
        assert r.text.count("\n|---") == 1 and table[0].startswith("| System | Experiment | Dataset |")
        assert len(r.plan.measurements) == len(s.measurements)
        assert {p.fact for p in r.placements if p.role == "value"} == {m.id for m in s.measurements}
        for e in s.experiments:
            for d in e.datasets:
                assert sum(f"| {e.name} | {d} |" in ln for ln in table) == len(e.conditions)
        rel = [p for p in r.placements if p.fmt == "relative"]
        assert [p.fact for p in rel] == [s.effect.treatment]
        multi += len(s.experiments) > 1
    assert multi >= 5


@pytest.mark.parametrize("level", [lv for lv in LEVELS if lv != "complex"])
def test_hard_other_levels_show_only_the_main_experiment(level: str) -> None:
    for s, r in hard_papers(level, range(1, 2)):
        assert {m.experiment for m in r.plan.measurements} <= {s.main_experiment}
        assert set(r.plan.conditions) == set(s.main_conditions) and not r.plan.experiments


def test_cli_hard_builds_are_deterministic_and_recorded(tmp_path) -> None:
    import json
    from synth import cli
    args = ["build", "--name", "h", "--seed", "1", "--studies", "100", "--hard", "--levels", "complex"]
    assert cli.main(args + ["--out", str(tmp_path / "a")]) == 0
    assert cli.main(args + ["--out", str(tmp_path / "b")]) == 0
    a, b = (tmp_path / "a" / "h-complex" / "corpus.json"), (tmp_path / "b" / "h-complex" / "corpus.json")
    assert a.read_bytes() == b.read_bytes()
    meta = json.loads(a.read_text(encoding="utf-8"))
    assert meta["settings"]["hard"] is True and meta["selection"]["retained_studies"] == 100
    gt = json.loads((tmp_path / "a" / "h-complex" / "ground_truth.json").read_text(encoding="utf-8"))
    multi = [s for s in gt["studies"] if len(s["experiments"]) > 1]
    assert multi and all(s["experiments"][0]["synthesis"] and not any(e["synthesis"] for e in s["experiments"][1:])
                         for s in multi)
    assert all("experiment" in m for s in multi for m in s["measurements"])


def test_cli_hard_refuses_the_llm_renderer(tmp_path, capsys) -> None:
    from synth import cli
    assert cli.main(["build", "--name", "h", "--seed", "1", "--hard", "--renderer", "llm", "--out", str(tmp_path)]) == 2
    assert "--hard" in capsys.readouterr().err and not any(tmp_path.iterdir())


def test_variant_of_a_hard_corpus(tmp_path) -> None:
    import json
    from synth import cli
    assert cli.main(["build", "--name", "h", "--seed", "1", "--studies", "12", "--hard", "--levels", "complex",
                     "--out", str(tmp_path)]) == 0
    base = tmp_path / "h-complex"
    gt = json.loads((base / "ground_truth.json").read_text(encoding="utf-8"))
    study = next(s for s in gt["studies"] if len(s["experiments"]) > 1 and s["effect"]["direction"] == "supports")
    assert cli.main(["variant", "--corpus", str(base), "--study", study["study_id"], "--direction", "contradicts"]) == 0
    assert cli.main(["variant", "--corpus", str(base), "--study", study["study_id"], "--direction", "neutral",
                     "--renderer", "llm"]) == 2
