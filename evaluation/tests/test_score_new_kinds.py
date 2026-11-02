"""Expected answers and A/B/C scores of the kinds chaining, limitations and builds_on (plan 2 Task 13).

DRUG is a template-built drugtoy corpus (synth build --domain drugtoy --root evidence/tests/fixtures --seed 5
--studies 8 --levels explicit --preset builds_on --renderer template): Zelvora is worse than Morvectin through
Quintapride on one population (S004, S006) and refused on the others; S008 reports S007's placebo value as its own
(a copied result); S003 and S007 reuse a dataset of S002, S006 one of S005, and S005 the method of S001 (Zelvora).
DRUG1 is evaluation/tests/data/drugtoy (seed 1, six studies), where Zelvora against Morvectin is refused."""
from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from evaluation.canon import Canon
from evaluation.expected import expected, thing_key, truth_comparisons
from evaluation.score import Matching, integration_kind, protocol_matching, score_extraction, score_kind
from evaluation.truth import GroundTruth
from evidence import contract, rules
from evidence.comparisons import Comparison, Comparisons
from evidence.contract import Item, Span
from evidence.kinds import builds_on, chaining, limitations
from evidence.names import NameGroups
from evidence.pack import load_pack, register_pack
from evidence.protocol import load as load_protocol
from evidence.questions import QuestionTruth

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"
FIXTURES = ROOT / "evidence" / "tests" / "fixtures"
PROTOCOLS = FIXTURES / "drugtoy" / "protocols"
DRUG = GroundTruth.load(DATA / "drugtoy-s5" / "ground_truth.json")
DRUG1 = GroundTruth.load(DATA / "drugtoy" / "ground_truth.json")
CANON = Canon.from_truth(DRUG, root=FIXTURES)   # the drugtoy recipe is not under domains/: effect needs its root

CHAIN_PARAMS = QuestionTruth(metric="response_rate", min_effect=0.01, source="Zelvora", target="Morvectin")
DIRECT_PARAMS = QuestionTruth(metric="response_rate", min_effect=0.01, source="Zelvora", target="placebo")
NO_PATH_PARAMS = QuestionTruth(metric="response_rate", min_effect=0.01, source="Morvectin", target="placebo")
EFFECT_PARAMS = QuestionTruth(metric="response_rate", min_effect=0.01)
NEW_QUESTIONS = [("chaining", CHAIN_PARAMS), ("chaining", DIRECT_PARAMS), ("chaining", NO_PATH_PARAMS),
                 ("limitations", QuestionTruth()), ("limitations", QuestionTruth(thing="Zelvora")),
                 ("builds_on", QuestionTruth()), ("builds_on", QuestionTruth(thing="Zelvora"))]
HEADLINE_FIELDS = {"chaining": ("verdict_correct", "inferred_correct", "path_correct", "refusal_correct", "headline"),
                   "limitations": ("jaccard_mean", "exact_match", "headline"),
                   "builds_on": ("follower_f1_mean", "ranking_tau", "top1_correct", "headline")}


@pytest.fixture(autouse=True)
def _registry() -> Iterator[None]:
    """Each test leaves the evidence-type registry as it found it (the drugtoy pack registers its types)."""
    before = dict(contract.ITEM_PREFIX)
    register_pack(load_pack("drugtoy", root=FIXTURES))
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def headline(result: dict[str, Any]) -> dict[str, Any]:
    """The C result's boolean and float fields the kind is judged by (None ones left out: not applicable)."""
    return {k: result[k] for k in HEADLINE_FIELDS[result["kind"]] if result[k] is not None}


def counting_copy_twice() -> dict[str, Any]:
    """The expected effect answer, but S008 (which reports S007's placebo value as its own) counted with S007's drug
    value too: S007's comparison appears a second time, at S008."""
    exp = expected(DRUG, "effect", EFFECT_PARAMS, canon=CANON)
    by_doc = {s["document"]: s for s in exp["studies"]}
    by_doc["S008"]["treatment"] = {**by_doc["S008"]["treatment"], "value": by_doc["S007"]["treatment"]["value"]}
    return exp | {"system": "x"}


# --- the brief's tests ------------------------------------------------------------------------------------------

def test_expected_answer_scores_perfectly_against_itself():
    for kind, params in NEW_QUESTIONS:
        exp = expected(DRUG, kind, params)
        assert all(v in (1.0, True)
                   for v in headline(score_kind(DRUG, kind, params, None, exp | {"system": "x"})).values())


def test_wrong_via_scores_path_incorrect():
    exp = expected(DRUG, "chaining", CHAIN_PARAMS)
    assert score_kind(DRUG, "chaining", CHAIN_PARAMS, None, exp | {"via": ["Morvectin"]})["path_correct"] is False


def test_double_counted_copy_is_caught():
    assert score_kind(DRUG, "effect", EFFECT_PARAMS, None, counting_copy_twice(), CANON)["copied_counted_once"] is False


# --- expected answers -------------------------------------------------------------------------------------------

def test_expected_chain_is_inferred_through_the_one_concluding_path():
    exp = expected(DRUG, "chaining", CHAIN_PARAMS)
    assert (exp["kind"], exp["verdict"], exp["inferred"], exp["reason"]) == ("chaining", "worse", True, None)
    assert (exp["via"], exp["studies"]) == (["Quintapride"], ["S004", "S006"])
    assert exp["note"] == "inferred through Quintapride, not tested directly"
    assert len(exp["paths"]) == 4
    assert {p["reason"] for p in exp["paths"]} == {None, "mixed_directions", "context_differs"}


def test_expected_chain_direct_comparison_and_no_path():
    direct = expected(DRUG, "chaining", DIRECT_PARAMS)
    assert (direct["verdict"], direct["inferred"], direct["reason"]) == ("better", False, "direct_comparison")
    assert (direct["via"], direct["studies"]) == ([], ["S001", "S005", "S007", "S008"])
    none = expected(DRUG, "chaining", NO_PATH_PARAMS)
    assert (none["verdict"], none["reason"], none["via"], none["studies"], none["paths"]) == (
        "refused", "no_path", [], [], [])


def test_expected_chain_refused_when_no_path_concludes():
    exp = expected(DRUG1, "chaining", CHAIN_PARAMS)
    assert (exp["verdict"], exp["inferred"], exp["reason"]) == ("refused", False, "mixed_directions")
    assert (exp["via"], exp["studies"]) == (["Quintapride"], ["S002", "S003", "S004", "S005"])
    result = score_kind(DRUG1, "chaining", CHAIN_PARAMS, None, exp | {"system": "x"})
    assert result["refusal_correct"] is True and result["headline"] == 1.0
    wrong = score_kind(DRUG1, "chaining", CHAIN_PARAMS, None, exp | {"reason": "context_differs"})
    assert wrong["refusal_correct"] is False and wrong["verdict_correct"] is True


def test_chain_paths_combines_like_the_chaining_kind():
    assert rules.chain_paths([("refused", "mixed_directions"), ("better", None)]) == ("better", None, [1])
    assert rules.chain_paths([("better", None), ("worse", None)]) == ("refused", "paths_disagree", [0, 1])
    assert rules.chain_paths([("refused", "context_differs"), ("refused", "mixed_directions")]) == (
        "refused", "mixed_directions", [0, 1])
    assert rules.chain_paths([("refused", "context_differs")]) == ("refused", "context_differs", [0])
    with pytest.raises(ValueError):
        rules.chain_paths([])


def test_expected_limitations_counts_by_thing_name_and_unlinked_apart():
    exp = expected(DRUG, "limitations", QuestionTruth())
    assert exp["counts"]["Zelvora"] == {"small_sample": 2, "cost": 1, "short_follow_up": 3}
    assert exp["counts"]["Quintapride"] == {"small_sample": 2, "side_effects": 1, "short_follow_up": 1, "cost": 1}
    assert exp["unlinked"] == {}
    only = expected(DRUG, "limitations", QuestionTruth(thing="ZV-791"))   # a code name of Zelvora
    assert set(only["counts"]) == {"Zelvora"} and {e["thing"] for e in only["entries"]} == {"Zelvora"}


def test_expected_builds_on_links_origins_and_followers():
    exp = expected(DRUG, "builds_on", QuestionTruth())
    assert [(x["from"], x["to"], x["reuses"]) for x in exp["links"]] == [
        ("S003", "S002", "dataset"), ("S005", "S001", "method"), ("S006", "S005", "dataset"),
        ("S007", "S002", "dataset"), ("S008", "S007", "result")]
    assert exp["origins"]["Zelvora"] == "S001" and exp["followers"]["Zelvora"] == ["S005", "S006"]
    assert exp["origins"]["Morvectin"] == "S002" and exp["followers"]["Morvectin"] == ["S003", "S007", "S008"]
    assert exp["ranking"][0] == "Morvectin" and exp["influence"]["Morvectin"] == 3
    assert exp["unresolved"] == []
    one = expected(DRUG, "builds_on", QuestionTruth(thing="Zelvora"))
    assert list(one["origins"]) == ["Zelvora"] and len(one["links"]) == 5


def test_a_dependency_outside_the_corpus_is_unresolved_not_a_link():
    truth = copy.deepcopy(DRUG)
    dep = next(d for s in truth.studies for d in s.get("dependencies") or [] if d["id"] == "S006.d1")
    dep["outside_corpus"] = True
    exp = expected(truth, "builds_on", QuestionTruth())
    assert ("S006", "S005") not in {(x["from"], x["to"]) for x in exp["links"]}
    assert exp["unresolved"] == [dep["label"]]
    assert exp["followers"]["Zelvora"] == ["S005"]


# --- C scores ---------------------------------------------------------------------------------------------------

def test_chaining_scores_name_forms_by_group_and_wrong_verdict():
    exp = expected(DRUG, "chaining", CHAIN_PARAMS)
    spelled = score_kind(DRUG, "chaining", CHAIN_PARAMS, None, exp | {"via": ["QT-626"], "system": "x"})
    assert spelled["path_correct"] is True                      # a code name of Quintapride is Quintapride
    wrong = score_kind(DRUG, "chaining", CHAIN_PARAMS, None, exp | {"verdict": "better"})
    assert (wrong["verdict_correct"], wrong["path_correct"], wrong["headline"]) == (False, True, 0.5)
    assert wrong["refusal_correct"] is None                      # truth does not refuse


def test_limitations_score_jaccard_per_thing():
    exp = expected(DRUG, "limitations", QuestionTruth())
    answer = copy.deepcopy(exp) | {"system": "x"}
    del answer["counts"]["Zelvora"]["cost"]                      # 2 of 3 categories
    answer["counts"]["Placebo"] = {"cost": 1}                    # a thing truth has no limitation for
    result = score_kind(DRUG, "limitations", QuestionTruth(), None, answer)
    rows = {r["thing"]: r for r in result["things"]}
    assert rows["Zelvora"]["jaccard"] == pytest.approx(2 / 3) and rows["Zelvora"]["exact"] is False
    assert rows["placebo"]["jaccard"] == 0.0
    n = len(rows)
    assert result["headline"] == pytest.approx((n - 2 + 2 / 3) / n)
    assert result["exact_match"] == pytest.approx((n - 2) / n)


def test_builds_on_scores_followers_ranking_and_top1():
    exp = expected(DRUG, "builds_on", QuestionTruth())
    answer = copy.deepcopy(exp) | {"system": "x"}
    answer["followers"]["Zelvora"] = ["S005"]                    # S006 missed: F1 2/3
    answer["influence"]["Zelvora"] = 1
    answer["ranking"] = ["Zelvora", *[t for t in exp["ranking"] if t != "Zelvora"]]
    result = score_kind(DRUG, "builds_on", QuestionTruth(), None, answer)
    rows = {r["thing"]: r for r in result["things"]}
    assert rows["Zelvora"]["f1"] == pytest.approx(2 / 3)
    assert result["top1_correct"] is False
    assert result["ranking_tau"] < 1.0
    assert result["headline"] == pytest.approx((len(rows) - 1 + 2 / 3) / len(rows))


def test_copied_counted_once_on_the_expected_answer_and_absent_on_old_corpora():
    exp = expected(DRUG, "effect", EFFECT_PARAMS, canon=CANON)
    assert score_kind(DRUG, "effect", EFFECT_PARAMS, None, exp | {"system": "x"}, CANON)["copied_counted_once"] is True
    assert counting_copy_twice()["studies"] != exp["studies"]


# --- engine and truth agree -------------------------------------------------------------------------------------

class Papers:
    """Hand-built engine items by document from the truth (one span per item, positions made up)."""

    def __init__(self) -> None:
        self.items: dict[str, list[Item]] = {}
        self.at = 0

    def add(self, doc: str, etype: str, fields: dict[str, Any], role: str,
            links: dict[str, str] | None = None) -> Item:
        self.at += 10
        span = Span(role=role, selector={"file": f"papers/{doc}.md", "start": self.at, "end": self.at + 4,
                                         "exact": "text", "prefix": "", "suffix": "", "sha256": "0"})
        item = Item.build(etype, fields, [span], links=links)
        self.items.setdefault(doc, []).append(item)
        return item


def truth_items(truth: GroundTruth) -> tuple[list[str], dict[str, list[Item]]]:
    """A perfect extraction of the truth's arms, study labels, limitations and dependencies (labels as written)."""
    papers = Papers()
    for s in truth.studies:
        doc = s["paper"]
        papers.add(doc, "study_label", {"label": s["study_label"]["label"]}, "label")
        arms = {c["id"]: papers.add(doc, "arm", {"label": c["label"], "role": "drug"}, "condition_label")
                for c in s["conditions"]}
        for lim in s.get("limitations") or []:
            papers.add(doc, "limitation", {"category": lim["category"]}, "limitation",
                       {"thing": arms[lim["thing"]].item_id} if lim["thing"] else None)
        for d in s.get("dependencies") or []:
            cited = d["label"]   # as the paper writes it, also for a study outside the corpus
            papers.add(doc, "dependency", {"cited": cited, "reuses": d["reuses"]}, "citation",
                       {"thing": arms[d["thing"]].item_id} if d["thing"] else None)
    return [s["paper"] for s in truth.studies], papers.items


def name_groups(truth: GroundTruth) -> NameGroups:
    """The run's name groups (`names: on`) as a perfect grouping gives them: every form of a thing under its key."""
    canon = Canon.from_truth(truth)
    groups: dict[str, list[str]] = {}
    for s in truth.studies:
        for c in s["conditions"]:
            forms = groups.setdefault(canon.key("condition", c["label"]) or c["label"], [])
            forms += [f for f in (c["label"], *c["aliases"]) if f not in forms]
    return NameGroups(groups=groups, matches=[], unresolved=[])


def test_engine_builds_on_on_perfect_items_scores_perfectly():
    documents, items = truth_items(DRUG)
    protocol = load_protocol(PROTOCOLS / "drugtoy-builds-on.yaml", FIXTURES)
    answer, _ = builds_on.answer(protocol, documents, items, groups=name_groups(DRUG))
    result = score_kind(DRUG, "builds_on", QuestionTruth(), None, answer)
    assert all(v in (1.0, True) for v in headline(result).values()), result
    b = integration_kind(Matching([], DRUG, {}, (), None, CANON), "builds_on", answer)
    assert (b["link_precision"], b["link_recall"]) == (1.0, 1.0)


def test_engine_limitations_on_perfect_items_scores_perfectly():
    documents, items = truth_items(DRUG)
    protocol = load_protocol(PROTOCOLS / "drugtoy-limits.yaml", FIXTURES)
    answer, _ = limitations.answer(protocol, documents, items, groups=name_groups(DRUG))
    result = score_kind(DRUG, "limitations", QuestionTruth(), None, answer)
    assert result["exact_match"] == 1.0 and result["headline"] == 1.0


def network_comparisons(truth: GroundTruth) -> Comparisons:
    """The truth network's comparisons (synth/network.py) as the engine's comparisons.json holds them (B's truth)."""
    return Comparisons(comparisons=tuple(
        Comparison(id=f"cmp-{n}", document=c["document"], a=c["a"], b=c["b"], metric=c["metric"], context=c["context"],
                   a_value=c["a_value"], b_value=c["b_value"], direction=c["direction"], delta=c["delta"], items=(),
                   copied_from=None)
        for n, c in enumerate(truth.network["comparisons"])), min_effect=0.01)


def chain_items(truth: GroundTruth) -> tuple[list[str], dict[str, list[Item]]]:
    """A perfect extraction for the chaining protocol: arms, outcomes, study labels, and each value linked to its arm
    and outcome with its population; a copied value links a `result` dependency citing its origin's label."""
    papers = Papers()
    by_id = {s["study_id"]: s for s in truth.studies}
    for s in truth.studies:
        doc = s["paper"]
        papers.add(doc, "study_label", {"label": s["study_label"]["label"]}, "label")
        arms = {c["id"]: papers.add(doc, "arm", {"label": c["label"], "role": "drug"}, "condition_label")
                for c in s["conditions"]}
        outcomes = {k["id"]: papers.add(doc, "outcome", {"name": k["name"], "canonical": k["canonical"],
                                                         "higher_is_better": k["higher_is_better"]}, "metric_label")
                    for k in s["metrics"]}
        for m in s["measurements"]:
            links = {"arm": arms[m["condition"]].item_id, "outcome": outcomes[m["metric"]].item_id}
            if m.get("copied_from"):
                dep = papers.add(doc, "dependency", {"cited": by_id[m["copied_from"]]["study_label"]["label"],
                                                     "reuses": "result"}, "citation")
                links["source"] = dep.item_id
            papers.add(doc, "result", {"value": m["value"], "population": m["dataset"]}, "value", links)
    return [s["paper"] for s in truth.studies], papers.items


def chain_protocol(params: QuestionTruth, max_hops: int = 2):
    protocol = load_protocol(PROTOCOLS / "drugtoy-chain.yaml", FIXTURES)
    assert protocol.chaining is not None
    return protocol.model_copy(update={"chaining": protocol.chaining.model_copy(
        update={"source": params.source, "target": params.target, "max_hops": max_hops})})


def relabelled(truth: GroundTruth, study: str, old: str, new: str) -> GroundTruth:
    """`truth` with one arm of `study` named otherwise."""
    out = copy.deepcopy(truth)
    arm = next(c for s in out.studies if s["paper"] == study for c in s["conditions"] if c["label"] == old)
    arm["label"] = new
    return out


def on_other_metric(truth: GroundTruth, study: str) -> GroundTruth:
    """`truth` with `study`'s outcome another one (canonical `other`)."""
    out = copy.deepcopy(truth)
    for s in out.studies:
        if s["paper"] == study:
            s["metrics"] = [k | {"canonical": "other", "name": "remission"} for k in s["metrics"]]
    return out


MOR_PLACEBO = NO_PATH_PARAMS
VIA_OTHER_ARM = relabelled(DRUG, "S006", "watchful waiting", "dietary counselling")
OTHER_METRIC = on_other_metric(DRUG, "S006")
WW_PARAMS = QuestionTruth(metric="response_rate", min_effect=0.01, source="Morvectin", target="watchful waiting")
CHAIN_CASES = [  # (truth, params, max_hops, expected verdict, expected reason)
    (DRUG, CHAIN_PARAMS, 2, "worse", None),
    (DRUG, DIRECT_PARAMS, 2, "better", "direct_comparison"),
    (DRUG, MOR_PLACEBO, 2, "refused", "no_path"),
    (DRUG1, CHAIN_PARAMS, 2, "refused", "mixed_directions"),
    (DRUG, MOR_PLACEBO, 3, None, None),                   # 3 steps: Morvectin - Quintapride - Zelvora - placebo
    (VIA_OTHER_ARM, MOR_PLACEBO, 2, None, None),          # only through dietary counselling, not a network thing
    (OTHER_METRIC, WW_PARAMS, 2, "refused", "metric_differs"),
]


def test_truth_comparisons_are_the_engines_on_a_perfect_extraction():
    from evidence.comparisons import of_run
    protocol = chain_protocol(CHAIN_PARAMS)
    documents, items = chain_items(DRUG)
    engine = of_run(protocol, documents, items, protocol.roles(), name_groups(DRUG))
    canon = Canon.from_truth(DRUG)
    truth = truth_comparisons(DRUG, canon, 0.01)

    def keyed(c: Comparison) -> tuple[Any, ...]:
        return (c.document, *sorted((thing_key(canon, c.a), thing_key(canon, c.b))), c.metric, c.context,
                round(c.a_value + c.b_value, 6), c.copied_from)
    assert sorted(map(keyed, engine.comparisons)) == sorted(map(keyed, truth)) and not engine.copied
    assert any(c.copied_from == "S007" for c in truth)    # S008's comparison resting on S007's placebo value


@pytest.mark.parametrize("truth,params,hops,verdict,reason", CHAIN_CASES)
def test_engine_chaining_on_a_perfect_extraction_agrees_with_the_truth(truth, params, hops, verdict, reason):
    protocol = chain_protocol(params, hops)
    documents, items = chain_items(truth)
    answer, _ = chaining.answer(protocol, documents, items, groups=name_groups(truth))
    exp = expected(truth, "chaining", params, protocol)
    if verdict is not None:
        assert (exp["verdict"], exp["reason"]) == (verdict, reason)
    result = score_kind(truth, "chaining", params, protocol, answer)
    assert all(v in (1.0, True) for v in headline(result).values()), result


def test_max_hops_and_non_network_arms_open_paths_the_old_truth_chains_lacked():
    hops3 = expected(DRUG, "chaining", MOR_PLACEBO, chain_protocol(MOR_PLACEBO, 3))
    assert hops3["reason"] != "no_path" and set(hops3["via"]) == {"Quintapride", "Zelvora"}
    assert all(len(p["steps"]) == 3 for p in hops3["paths"])
    other = expected(VIA_OTHER_ARM, "chaining", MOR_PLACEBO, chain_protocol(MOR_PLACEBO))
    assert other["reason"] != "no_path" and other["via"] == ["dietary counselling"]
    assert not any({c["source"], c["target"]} == {"Morvectin", "placebo"} for c in VIA_OTHER_ARM.network["chains"])


# --- A and B ----------------------------------------------------------------------------------------------------

def test_limitation_extraction_precision_recall_of_study_thing_category():
    protocol = load_protocol(PROTOCOLS / "drugtoy-limits.yaml", FIXTURES)
    _, items = truth_items(DRUG)
    flat = [i for doc in items.values() for i in doc]
    files = {f"papers/{s['paper']}.md": s["paper"] for s in DRUG.studies}
    m = protocol_matching(flat, DRUG, files, protocol, CANON)
    assert "limitation" in m.types
    row = next(r for r in score_extraction(m)["rows"] if (r["evidence_type"], r["level"]) == ("limitation", "all"))
    assert (row["precision"], row["recall"]) == (1.0, 1.0)
    # a limitation linked to the wrong arm (S001's placebo, not Zelvora) is no match
    s001 = items["S001"]
    placebo = next(i for i in s001 if i.evidence_type == "arm" and i.fields["label"] == "placebo")
    wrong = [i.model_copy(update={"links": {"thing": placebo.item_id}}) if i.evidence_type == "limitation" else i
             for i in s001]
    m = Matching([*wrong, *(i for d, its in items.items() if d != "S001" for i in its)], DRUG, files,
                 ("limitation",), None, CANON)
    row = next(r for r in score_extraction(m)["rows"] if (r["evidence_type"], r["level"]) == ("limitation", "all"))
    n = row["facts"]
    assert row["matched"] == n - 2 and row["recall"] == pytest.approx((n - 2) / n)


def test_builds_on_link_precision_recall():
    exp = expected(DRUG, "builds_on", QuestionTruth())
    answer = copy.deepcopy(exp)
    answer["links"] = answer["links"][:-1] + [{"from": "S008", "to": "S001", "reuses": "result", "items": []}]
    b = integration_kind(Matching([], DRUG, {}, (), None, CANON), "builds_on", answer)
    assert (b["links"], b["expected_links"], b["matched_links"]) == (5, 5, 4)
    assert b["link_precision"] == pytest.approx(0.8) and b["link_recall"] == pytest.approx(0.8)


def test_chaining_comparison_precision_recall_against_the_network():
    comparisons = network_comparisons(DRUG).json()
    m = Matching([], DRUG, {}, (), None, CANON)
    b = integration_kind(m, "chaining", None, comparisons=comparisons)
    assert (b["comparison_precision"], b["comparison_recall"]) == (1.0, 1.0)
    given = list(comparisons["comparisons"])
    assert (given[0]["document"], given[6]["document"], given[6]["a"]) == ("S001", "S003", "Quintapride")
    given[0] = dict(given[0], context="children")                    # the population wrong
    given[6] = dict(given[6], a="QT-626")                            # Quintapride by a code name: still right
    b = integration_kind(m, "chaining", None, comparisons={**comparisons, "comparisons": given})
    n = len(comparisons["comparisons"])
    assert (b["matched_comparisons"], b["comparisons"], b["expected_comparisons"]) == (n - 1, n, n)
    assert integration_kind(m, "chaining", None)["comparison_recall"] is None   # a run without comparisons.json


def test_old_rag_truth_has_no_network_and_no_copy_key():
    rag = ROOT / "tests" / "EV2" / "corpora" / "rag-claude-s1-mixed" / "ground_truth.json"
    if not rag.is_file():
        pytest.skip("EV2 corpora not present")
    truth = GroundTruth.load(rag)
    assert truth.network == {}
    exp = expected(truth, "effect", QuestionTruth(metric="factual_accuracy", min_effect=0.01))
    assert "copied_counted_once" not in score_kind(truth, "effect", QuestionTruth(metric="factual_accuracy",
                                                                                   min_effect=0.01), None, exp)
    assert json.loads(json.dumps(truth.fact_lists))   # old truth: the four fact lists


def test_report_renders_the_new_kinds():
    from evaluation.report import render_integration_kind, render_synthesis_kind
    m = Matching([], DRUG, {}, (), None, CANON)
    for kind, params in NEW_QUESTIONS:
        exp = expected(DRUG, kind, params)
        c = render_synthesis_kind(kind, [score_kind(DRUG, kind, params, None, exp)])
        b = render_integration_kind(kind, integration_kind(m, kind, exp, comparisons=network_comparisons(DRUG).json()))
        assert c[0].startswith("## C.") and b[0].startswith("## B.")


# --- fix round 1: a real truth with fidelity exclusions, the copy check, the limitation type by role --------------

# The DRUG build with S001 and S002 forced out as fidelity failures (synth build as DRUG, corpus.exclusions wrapped
# to fail them): S005 still cites S001 (the Zelvora method) and S003 and S007 S002 (a dataset), marked outside_corpus.
EXCLUDED = GroundTruth.load(DATA / "drugtoy-s5-excluded" / "ground_truth.json")


def test_a_generated_truth_with_excluded_cited_studies_scores_the_engine_perfectly():
    outside = {(s["paper"], d["cites"]) for s in EXCLUDED.studies for d in s.get("dependencies") or []
               if d.get("outside_corpus")}
    assert outside == {("S003", "S002"), ("S005", "S001"), ("S007", "S002")}
    exp = expected(EXCLUDED, "builds_on", QuestionTruth())
    assert [(x["from"], x["to"]) for x in exp["links"]] == [("S006", "S005"), ("S008", "S007")]
    assert exp["unresolved"] == ["Lindqvar et al. (2009)", "Ferreval et al. (2008)"]
    # S005 took Zelvora from S001 (outside): the origin is the next own mention, S003 (2009), with no follower
    assert (exp["origins"]["Zelvora"], exp["followers"]["Zelvora"]) == ("S003", [])
    documents, items = truth_items(EXCLUDED)
    protocol = load_protocol(PROTOCOLS / "drugtoy-builds-on.yaml", FIXTURES)
    answer, _ = builds_on.answer(protocol, documents, items, groups=name_groups(EXCLUDED))
    assert answer["unresolved"] == exp["unresolved"]
    result = score_kind(EXCLUDED, "builds_on", QuestionTruth(), None, answer)
    assert all(v in (1.0, True) for v in headline(result).values()), result
    b = integration_kind(Matching([], EXCLUDED, {}, (), None, Canon.from_truth(EXCLUDED)), "builds_on", answer)
    assert (b["link_precision"], b["link_recall"]) == (1.0, 1.0)


def test_a_coincidental_pair_or_a_partial_entry_is_not_a_copied_comparison():
    exp = expected(DRUG, "effect", EFFECT_PARAMS, canon=CANON)
    by_doc = {s["document"]: s for s in exp["studies"]}
    # S005 holds no copied value: carrying S007's pair is a wrong answer, not a copy counted twice
    by_doc["S005"]["treatment"] = dict(by_doc["S005"]["treatment"], value=by_doc["S007"]["treatment"]["value"])
    by_doc["S005"]["control"] = dict(by_doc["S005"]["control"], value=by_doc["S007"]["control"]["value"])
    by_doc["S008"]["control"] = None                     # no pair: not a comparison
    by_doc["S008"]["treatment"] = dict(by_doc["S008"]["treatment"], value=by_doc["S007"]["treatment"]["value"])
    result = score_kind(DRUG, "effect", EFFECT_PARAMS, None, exp | {"system": "x"}, CANON)
    assert (result["copied_counted_once"], result["copied_counted_twice"]) == (True, [])
    assert score_kind(DRUG, "effect", EFFECT_PARAMS, None, counting_copy_twice(), CANON)["copied_counted_twice"] == [
        "S008"]


def test_a_limitation_type_of_another_name_is_matched_by_its_role():
    from evaluation.score import limitation_type
    assert limitation_type(load_protocol(PROTOCOLS / "drugtoy-limits.yaml", FIXTURES)) == "limitation"
    assert limitation_type(load_protocol(PROTOCOLS / "drugtoy-chain.yaml", FIXTURES)) is None
    contract.ITEM_PREFIX["caveat"] = "xcv"
    _, items = truth_items(DRUG)
    renamed = [i.model_copy(update={"evidence_type": "caveat"}) if i.evidence_type == "limitation" else i
               for its in items.values() for i in its]
    files = {f"papers/{s['paper']}.md": s["paper"] for s in DRUG.studies}
    m = Matching(renamed, DRUG, files, ("limitation",), None, CANON, {"caveat": "limitation"})
    row = next(r for r in score_extraction(m)["rows"] if (r["evidence_type"], r["level"]) == ("limitation", "all"))
    assert (row["precision"], row["recall"]) == (1.0, 1.0)
    assert integration_kind(m, "limitations", None)["link_share"] == 1.0


def test_headline_is_a_float_when_no_thing_is_on_either_side():
    exp = expected(DRUG, "limitations", QuestionTruth(thing="Nonexistia"))
    assert exp["counts"] == {} and score_kind(DRUG, "limitations", QuestionTruth(thing="Nonexistia"), None,
                                              exp)["headline"] == 1.0
    empty = {"kind": "builds_on", "thing": None, "links": [], "origins": {}, "followers": {}, "influence": {},
             "ranking": [], "unresolved": []}
    from evaluation.score import score_builds_on
    assert score_builds_on(empty, empty, CANON)["headline"] == 1.0
