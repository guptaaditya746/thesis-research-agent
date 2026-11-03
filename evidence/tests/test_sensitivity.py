import pytest

from evidence.kg.build import build
from evidence.kg.query import Answer
from evidence.kg.sensitivity import Run, Sensitivity, Verdict, alternatives, label, rerun
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


def test_best_author_example():
    docs = []
    for author, per_paper in (("Chen", [3, 3, 2, 2, 2]), ("Rossi", [3, 1, 1, 1, 1, 1, 1])):   # 12 results / 5 papers; 9 / 7
        for n, wins in enumerate(per_paper):
            d = Doc(f"{author}{n}")
            for _ in range(wins):
                d.value(author, 0.9)
            d.value("Low", 0.1, side="base")
            docs.append(d)
    def top(answer: Answer) -> Verdict:   # the winner and how many it has: the records behind the verdict
        return Verdict(answer.rows[0]["thing"], answer.rows[0]["count"])

    result = rerun(graph(*docs), line(BEST), [decision("counts_as", ["result", "paper"])], verdict=top,
                   candidates={"counts_as": []})
    assert result.main.label == "Chen"
    assert [(r.field, r.setting, r.verdict.label) for r in result.flipping] == [("counts_as", "strict", "Rossi")] * 2 \
        or {(r.field, r.verdict.label) for r in result.flipping} == {("counts_as", "Rossi")}
    assert label(result) == "depends on counts_as"


def test_too_few():
    s = Sensitivity(line="l", main=Verdict("x", 2), runs=[Run("d", "f", "strict", [], Verdict("y", 1), True)])
    assert label(s) == "too few to tell"
    assert label(s, min_count=1) == "depends on f"


def test_solid_and_same_direction():
    solid = Sensitivity(line="l", main=Verdict("x", 9, 0.8), runs=[Run("d", "threshold", "loose", 1, Verdict("x", 9, 0.78), False)])
    assert label(solid) == "solid"
    weak = Sensitivity(line="l", main=Verdict("x", 9, 0.8), runs=[Run("d", "threshold", "loose", 1, Verdict("x", 9, 0.5), False)])
    assert label(weak) == "same direction"
