import pytest

from evidence.kg.build import build
from evidence.kg.query import Answer
from evidence.kg.sensitivity import Run, Sensitivity, Verdict, alternatives, label, rerun, winners_verdict
from evidence.plan import Decision, EvidenceLine

from .kg_support import ROLES, Doc, paper, register, restore


@pytest.fixture(autouse=True)
def _registry():
    before = register()
    yield
    restore(before)


def decision(kind: str, value, ident: str = "d1") -> Decision:
    return Decision(id=ident, type=kind, value=value, reason="test")


def line(query: str) -> EvidenceLine:
    return EvidenceLine(id="l1", question="q", query=query, template=None)


def graph(*docs: Doc):
    return build([paper(d.id) for d in docs], {d.id: d.items for d in docs}, ROLES, None)


def test_threshold_alternatives_are_0_main_double():
    assert alternatives(decision("threshold", 0.05), []) == [("strict", 0), ("main", 0.05), ("loose", 0.1)]


def test_must_match_and_counts_as_alternatives_change_one_item():
    got = alternatives(decision("must_match", ["dataset"]), ["dataset", "model"])
    assert got == [("strict", ["dataset", "model"]), ("main", ["dataset"]), ("loose", [])]
    got = alternatives(decision("counts_as", ["a", "b"]), ["a", "b", "c"])
    assert got == [("strict", ["b"]), ("strict", ["a"]), ("main", ["a", "b"]), ("loose", ["a", "b", "c"])]
    assert alternatives(decision("counts_as", ["a"]), ["a", "b"]) == [("main", ["a"]), ("loose", ["a", "b"])]


RAG = """SELECT ?e1 ?e2 ?win WHERE {
  ?ta ev:name "RAG" . ?tb ev:name "Base" .
  ?va ev:of ?ta ; ev:number ?na ; ev:inExperiment ?e1 .
  ?vb ev:of ?tb ; ev:number ?nb ; ev:inExperiment ?e2 .
  ?e1 ev:inPaper ?p . ?e2 ev:inPaper ?p .
  $must_match[?e1, ?e2]
  BIND(?na > ?nb AS ?win)
}"""


def helps(answer: Answer) -> Verdict:
    share = sum(1 for r in answer.rows if r["win"]) / len(answer.rows) if answer.rows else 0.0
    return Verdict("RAG helps" if share >= 0.7 else "RAG does not help", len(answer.rows), share)


def rag_graph():
    """12 groups, each a RAG and a Base experiment; RAG wins 9 groups; the 3 groups where model sizes differ all
    favour RAG, so matching on model size leaves 6 wins in 9."""
    d = Doc("p1")
    for i in range(12):
        mismatch = i < 3
        win = i < 9
        d.experiment(f"r{i}", {"grp": str(i), "model size": "3B", "population": f"r{i}"})
        d.experiment(f"b{i}", {"grp": str(i), "model size": "70B" if mismatch else "3B", "population": f"b{i}"})
        d.value("RAG", 0.6 if win else 0.4, population=f"r{i}")
        d.value("Base", 0.5, population=f"b{i}", side="base")
    return graph(d)


def test_rag_example_depends_on_model_size():
    result = rerun(rag_graph(), line(RAG), [decision("must_match", ["grp"])], verdict=helps,
                   candidates={"must_match": ["grp", "model size"]})
    assert result.main == Verdict("RAG helps", 12, 0.75)
    assert [(r.field, r.setting) for r in result.flipping] == [("model size", "strict")]
    assert (result.flipping[0].verdict.n, result.flipping[0].verdict.size) == (9, pytest.approx(6 / 9))
    assert label(result) == "depends on model size"
    # the loose rerun (drop grp) holds more pairs than the main one: they are listed as indirect
    assert result.indirect and all(r["note"] == "indirect on: grp" for r in result.indirect)


BEST = """SELECT (MIN(?name) AS ?thing) (COUNT(DISTINCT ?unit) AS ?count) WHERE {
  ?c a ev:Comparison ; ev:better ?v ; ev:inExperiment ?e . ?v ev:of ?t . ?t ev:name ?name .
  ?e ev:inPaper ?p .
  VALUES ?kind { $counts_as }
  BIND(IF(?kind = "paper", STR(?p), STR(?v)) AS ?unit)
} GROUP BY ?t ORDER BY DESC(?count) ?thing"""


def author_graph():
    docs = []
    for author, per_paper in (("Chen", [3, 3, 2, 2, 2]), ("Rossi", [3, 1, 1, 1, 1, 1, 1])):   # 12 results/5 papers; 9/7
        for n, wins in enumerate(per_paper):
            d = Doc(f"{author}{n}")
            for _ in range(wins):
                d.value(author, 0.9)
            d.value("Low", 0.1, side="base")
            docs.append(d)
    return graph(*docs)


def test_best_author_example():
    best = EvidenceLine(id="best", question="q", query="", template="best")
    result = rerun(author_graph(), best, [decision("counts_as", ["result"])], params={"metric": "acc"},
                   verdict=winners_verdict, candidates={"counts_as": ["result", "paper"]})
    assert result.main == Verdict("result: Chen", 12)   # Chen 12 results against Rossi 9
    [flip] = result.flipping                             # the one change: also count papers (Rossi 7 against Chen 5)
    assert (flip.field, flip.setting, flip.value) == ("counts_as", "loose", ["result", "paper"])
    assert flip.verdict.label == "paper: Rossi; result: Chen"
    assert label(result) == "depends on counts_as"


def effect_graph():
    docs = []
    for pid, (t, c) in zip(("p1", "p2", "p3"), ((0.515, 0.5), (0.616, 0.6), (0.717, 0.7))):
        d = Doc(pid)
        d.value("RAG", t, side="rag")
        d.value("Closed", c, side="baseline")
        docs.append(d)
    return graph(*docs)


def supported(answer: Answer) -> Verdict:
    from evidence.kg import after
    counts = after.counts(answer.rows) if answer.rows else {"supporting": 0}
    return Verdict("supported" if counts["supporting"] == 3 else "not supported", 3)


def test_effect_template_follows_the_threshold_decision():
    """Each gap is 0.015: a study at the main threshold 0.01, neutral at twice that (0.02)."""
    line_ = EvidenceLine(id="eff", question="q", query="", template="effect")
    params = {"sides": ["rag", "baseline"], "metrics": ["acc"], "higher_is_better": {"acc": True}}
    result = rerun(effect_graph(), line_, [decision("threshold", 0.01)], params=params, verdict=supported)
    assert result.main.label == "supported"
    assert [(r.field, r.setting, r.verdict.label) for r in result.flipping] == [("threshold", "loose", "not supported")]
    assert label(result) == "depends on threshold"


def test_effect_template_follows_counts_as_and_must_match():
    d = Doc("p1")
    d.experiment("a", {"population": "x", "size": "3B"})
    d.value("RAG", 0.6, side="rag", population="x")
    d.value("Closed", 0.5, side="baseline", population="x")
    params = {"sides": ["rag", "baseline"], "metrics": ["acc"], "higher_is_better": {"acc": True}, "min_effect": 0.01}
    store = graph(d)
    from evidence.kg.query import run_template
    assert run_template(store, "effect", {**params, "must_match": []}).rows[0]["direction"] == "supports"
    assert run_template(store, "effect", {**params, "must_match": ["size"]}).rows[0]["direction"] == "supports"
    assert run_template(store, "effect", {**params, "must_match": ["model"]}).empty   # no such setting: nothing matches
    assert run_template(store, "effect", {**params, "metrics": ["other"]}).empty


def test_two_decisions_of_one_type_need_their_own_parameters():
    line_ = EvidenceLine(id="b", question="q", query="", template="best")
    two = [decision("counts_as", ["result"], "d1"), decision("counts_as", ["paper"], "d2")]
    with pytest.raises(ValueError, match="both fill parameter"):
        rerun(author_graph(), line_, two, params={"metric": "acc"}, verdict=winners_verdict)
    with pytest.raises(ValueError, match="both fill parameter"):
        rerun(author_graph(), line_, two, params={"metric": "acc"}, param_of={"d1": "x", "d2": "x"})
    q = "SELECT ?k WHERE { VALUES ?k { $units $others } }"
    result = rerun(author_graph(), EvidenceLine(id="q", question="q", query=q, template=None), two,
                   param_of={"d1": "units", "d2": "others"}, candidates={"d1": ["result", "paper"]})
    assert result.main.n == 2 and [r.decision for r in result.runs].count("d1") == 1   # d1's pool is its own


def test_too_few():
    s = Sensitivity(line="l", main=Verdict("x", 2), runs=[Run("d", "f", "strict", [], Verdict("y", 1), True)])
    assert label(s) == "too few to tell"
    assert label(s, min_count=1) == "depends on f"


def test_solid_and_same_direction():
    solid = Sensitivity(line="l", main=Verdict("x", 9, 0.8), runs=[Run("d", "threshold", "loose", 1, Verdict("x", 9, 0.78), False)])
    assert label(solid) == "solid"
    weak = Sensitivity(line="l", main=Verdict("x", 9, 0.8), runs=[Run("d", "threshold", "loose", 1, Verdict("x", 9, 0.5), False)])
    assert label(weak) == "same direction"
