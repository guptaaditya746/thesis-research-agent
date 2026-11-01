"""The truth network (plan 2 Task 4): a latent ranking of things per population, studies on the recipe's edges with
exact count values per arm, and the chains the network allows, with verdicts from the shared chain rule."""
from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from pathlib import Path

import pytest

from evidence import contract, rules
from synth import corpus, truth
from synth.levels import make_plan, parse_value, write_value
from synth.network import chains, comparisons, edge_of as edge, latent, plan_studies
from synth.recipe import load_recipe
from synth.truth import generate

FIXTURES = Path(__file__).resolve().parents[2] / "evidence" / "tests" / "fixtures"
DRUGTOY = load_recipe("drugtoy", root=FIXTURES)
_BEFORE = dict(contract.ITEM_PREFIX)
SPEC = truth.default_spec(DRUGTOY)      # loading the drugtoy protocol registers its pack's types (arm, outcome, result)
contract.ITEM_PREFIX.clear()
contract.ITEM_PREFIX.update(_BEFORE)
PINS = Path(__file__).resolve().parent / "data" / "rag_set_sha256.json"


@pytest.fixture(autouse=True)
def _registry():
    """Each test leaves the type registry as it found it: drawing a drugtoy set loads its protocol, which registers
    the drugtoy types globally, and another test's pack may use the same type names with other prefixes."""
    before = dict(contract.ITEM_PREFIX)
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def test_values_are_exact_counts_over_arm_size():
    for s in generate(3, 12, recipe=DRUGTOY):
        for m in s.measurements:
            n = s.arm_sizes[m.condition]
            assert m.k is not None and 1 <= m.k < n and m.value == m.k / n


def test_network_edges_all_appear_in_each_context():
    seen = {(edge(s), s.population) for s in generate(3, 12, recipe=DRUGTOY)}
    assert len(seen) == 6


def test_chain_truth_follows_latent_order():
    studies = generate(3, 12, recipe=DRUGTOY)
    c = [c for c in chains(studies, DRUGTOY, SPEC) if c["source"] == "Zelvora" and c["target"] == "Morvectin"]
    assert c and all(c_["via"] == ["Quintapride"] for c_ in c)
    assert {c_["verdict"] for c_ in c} <= {"better", "worse", "refused"}
    rate = latent(3, DRUGTOY)
    seen = set()
    for c_ in c:     # a path within one population concludes what the latent ranking says, when via lies between
        if c_["context"] is None:
            assert (c_["verdict"], c_["reason"]) == ("refused", "context_differs")
            continue
        z, q, m = (rate[(t, c_["context"])] for t in ("Zelvora", "Quintapride", "Morvectin"))
        expected = (("better", None) if z > q > m else ("worse", None) if z < q < m
                    else ("refused", "mixed_directions"))
        assert (c_["verdict"], c_["reason"]) == expected
        seen.add(expected[0])
    assert seen and any(c_["context"] is None for c_ in c)


def test_rag_set_unchanged_without_network():
    """The rag recipe has no network: its sets are the pinned Task 2 sets (preflight P8, D1)."""
    pins = json.loads(PINS.read_text(encoding="utf-8"))["sets"]
    assert load_recipe("rag").network is None
    assert {str(s): hashlib.sha256(repr(generate(s, 6, recipe=load_recipe("rag"))).encode()).hexdigest()
            for s in (1, 2, 3)} == pins


def test_k_of_n_renders_and_parses_back():
    """Two arms of different sizes: each value written as "k of n patients", percent or a percent cell reads back
    within the evaluation tolerance (0.005); "k of n" reads back exactly."""
    study = next(s for s in generate(3, 12, recipe=DRUGTOY) if len(set(s.arm_sizes.values())) > 1)
    for m in study.measurements:
        n = study.arm_sizes[m.condition]
        text = write_value(m.value, "k_of_n", k=m.k, n=n, noun=DRUGTOY.text.unit_noun)
        assert text == f"{m.k} of {n} patients"
        assert parse_value(text, "k_of_n") == round(m.k / n, 6)
        for fmt in ("pct", "cell_pct"):
            assert abs(parse_value(write_value(m.value, fmt), fmt) - m.value) < 0.005
    with pytest.raises(ValueError, match="k_of_n"):
        write_value(0.5, "k_of_n")


def test_adjacent_things_in_the_latent_order_differ_by_the_gap():
    gap = 2 * SPEC.min_effect + DRUGTOY.effects["supports"][0]
    low, high = DRUGTOY.question_metrics[0].pair_range
    for seed in range(1, 6):
        rate = latent(seed, DRUGTOY)
        nodes = [*DRUGTOY.network.things, DRUGTOY.network.reference]
        assert set(rate) == {(t, c) for t in nodes for c in DRUGTOY.network.contexts}
        for context in DRUGTOY.network.contexts:
            values = sorted(rate[(t, context)] for t in nodes)
            assert all(b - a >= gap - 1e-9 for a, b in zip(values, values[1:]))
            assert low <= values[0] and values[-1] <= high


@pytest.mark.parametrize("seed", range(1, 6))
def test_every_study_takes_its_edge_direction_from_the_latent_ranking(seed):
    rate = latent(seed, DRUGTOY)
    for s in generate(seed, 12, recipe=DRUGTOY):
        a, b = edge(s)
        assert s.datasets == (s.population,)
        t, c = s.value_of(s.effect.treatment), s.value_of(s.effect.control)
        assert (s.effect.direction, s.effect.delta) == rules.effect(t, c, True, SPEC.min_effect)
        assert s.effect.direction == ("supports" if rate[(a, s.population)] > rate[(b, s.population)] else "contradicts")
        assert [c.role for c in s.conditions[2:]] in ([], ["other"])


def test_studies_are_planned_round_robin_over_edges_and_contexts():
    planned = plan_studies(3, 14, DRUGTOY, SPEC)
    counts = Counter(planned)
    assert len(planned) == 14 and len(counts) == 6 and set(counts.values()) == {2, 3}
    assert planned != plan_studies(4, 14, DRUGTOY, SPEC)


def test_a_distractor_arm_is_never_shared_between_studies():
    """So no chain can pass through a distractor: a path needs its middle thing in two studies."""
    for seed in range(1, 6):
        used = [c.label for s in generate(seed, 12, recipe=DRUGTOY) for c in s.conditions[2:]]
        assert len(used) == len(set(used))


def test_labels_are_unique_author_year_in_study_order():
    studies = generate(3, 12, recipe=DRUGTOY)
    labels = [s.label for s in studies]
    assert len(set(labels)) == 12 and all(" et al. (" in x for x in labels)
    years = [int(x[-5:-1]) for x in labels]
    assert years == sorted(years)
    assert {x.split(" et al.")[0] for x in labels} <= set(DRUGTOY.text.authors)


def test_count_values_cannot_be_redrawn_by_the_thousandths_knobs():
    with pytest.raises(SystemExit, match="network"):
        generate(3, 12, recipe=DRUGTOY, hard=True)
    with pytest.raises(SystemExit, match="network"):
        generate(3, 12, recipe=DRUGTOY, outliers=1)
    with pytest.raises(SystemExit, match="network"):
        generate(3, 12, {"supports": 1.0}, recipe=DRUGTOY)


def test_duplicates_and_missing_keep_counts_and_drop_out_of_the_network():
    studies = generate(3, 12, recipe=DRUGTOY, duplicates=1, missing=1)
    dup = next(s for s in studies if s.duplicate_of)
    assert set(dup.arm_sizes) == {c.id for c in dup.conditions}
    gone = next(s for s in studies if s.missing)
    docs = {c["document"] for c in comparisons(studies, SPEC)}
    assert dup.study_id not in docs
    assert all(not (c["document"] == gone.study_id and set(edge(gone)) == {c["a"], c["b"]})
               for c in comparisons(studies, SPEC))


def test_no_chain_where_a_direct_study_exists():
    studies = generate(3, 12, recipe=DRUGTOY)
    direct = {frozenset((c["a"], c["b"])) for c in comparisons(studies, SPEC)}
    found = chains(studies, DRUGTOY, SPEC)
    assert found and all(frozenset((c["source"], c["target"])) not in direct for c in found)
    assert all(c["metric"] == "response_rate" and len(c["studies"]) == 2 for c in found)


def test_chain_verdict_rule():
    assert rules.chain_verdict([("supports", "adults"), ("supports", "adults")]) == ("better", None)
    assert rules.chain_verdict([("contradicts", None), ("contradicts", "adults")]) == ("worse", None)
    assert rules.chain_verdict([("supports", "adults"), ("supports", "older adults")]) == ("refused", "context_differs")
    assert rules.chain_verdict([("supports", None), ("neutral", None)]) == ("refused", "mixed_directions")
    assert rules.chain_verdict([("supports", None), ("contradicts", None)]) == ("refused", "mixed_directions")


def test_ground_truth_records_population_label_arm_sizes_and_network():
    studies = generate(3, 4, recipe=DRUGTOY)
    s = studies[0]
    plan = make_plan(s, "explicit", random.Random(0))
    record = corpus.study_truth(corpus.Rendered(s, plan, "", [], [], None), SPEC)
    assert (record["population"], record["label"], record["arm_sizes"]) == (s.population, s.label, s.arm_sizes)
    top = corpus.network_truth(studies, DRUGTOY, SPEC)
    assert top["types"]["measurement"] == {"list": "measurements", "main_role": "value"}
    assert top["network"]["things"] == ["Zelvora", "Quintapride", "Morvectin", "placebo"]
    assert top["network"]["comparisons"] == comparisons(studies, SPEC)
    assert top["network"]["chains"] == chains(studies, DRUGTOY, SPEC)


def test_rag_truth_records_gain_no_keys():
    s = generate(1, 2)[0]
    record = corpus.study_truth(corpus.Rendered(s, make_plan(s, "explicit", random.Random(0)), "", [], [], None),
                                truth.default_spec())
    assert not {"population", "label", "arm_sizes"} & set(record)
    assert corpus.network_truth(generate(1, 2), load_recipe("rag"), truth.default_spec()) == {}


@pytest.mark.parametrize("old,new,match", [
    ("[Zelvora, Quintapride, Morvectin]", "[Zelvora, Quintapride, Dalnorex]", "distinct labels"),
    ("[Quintapride, Morvectin]]", "[Quintapride, Quintapride]]", "join two"),
    ("contexts: [adults, older adults]", "contexts: [children]", "contexts"),
    ("arm_size: [60, 240]", "arm_size: null", "arm_size"),
])
def test_recipe_network_is_checked(tmp_path, old, new, match):
    folder = tmp_path / "drugtoy"
    folder.mkdir()
    text = (FIXTURES / "drugtoy" / "generator.yaml").read_text(encoding="utf-8")
    assert old in text
    (folder / "generator.yaml").write_text(text.replace(old, new), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        load_recipe("drugtoy", root=tmp_path)
