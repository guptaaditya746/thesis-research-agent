"""S2: every question's SPARQL returns its gold, best winners need a margin, the set is frozen by sha256."""
from __future__ import annotations

import dataclasses
import json
from decimal import Decimal

import pytest

from evqa.paths import DATASET, REPO
from evqa.seed import questions as qs
from evqa.seed.check import full_graph

DOMAIN = "medical"


@pytest.fixture(scope="module")
def graph():
    return full_graph(DOMAIN)


def test_every_query_returns_its_frozen_gold(graph) -> None:
    for spec in qs.SPECS[DOMAIN]:
        frozen = json.loads((qs.gold_dir(DOMAIN) / f"{spec.qid}.json").read_text(encoding="utf-8"))
        assert qs.gold(DOMAIN, spec, graph) == frozen
        rows = [r["id"] for r in qs.run_query(graph, frozen["sparql"])]
        assert rows == frozen["row_ids"] and rows


def test_known_answers(graph) -> None:
    got = {s.qid: qs.gold(DOMAIN, s, graph)["answer"] for s in qs.SPECS[DOMAIN]}
    q1 = [(r["cells"]["time_point"], r["cells"]["patient_group"][:14], r["value"]) for r in got["Q-med-01"]["table"]]
    assert q1 == [("12 wk", "adults with ty", "-0.72"), ("24 wk", "adults with ne", "-0.99"),
                  ("24 wk", "adults with ty", "-0.78"), ("36 wk", "adults with ty", "-0.78"),
                  ("52 wk", "adults with ty", "-0.82")]   # the near miss stays, as its own patient group
    assert len(got["Q-med-02"]["table"]) == 4
    (g3,) = got["Q-med-03"]["groups"]
    assert (g3["status"], g3["winner"], g3["margin"]) == ("winner", "40 mg", "0.13")
    g4 = {g["cells"]["patient_group"][:14]: g for g in got["Q-med-04"]["groups"]}
    assert (g4["adults with ty"]["winner"], g4["adults with ty"]["ranking"][1]["cells"]["dose"]) == ("brenoxalin", "10 mg")
    assert (g4["adults with ne"]["status"], g4["adults with ne"]["missing"]) == ("not reported", ["kavolemin"])


def _bench_set() -> bool:
    """True once the 100-question set of `evqa seed bench` is frozen (then test_bench checks the new questions)."""
    m = json.loads((qs.gold_dir(DOMAIN) / "manifest.json").read_text(encoding="utf-8"))
    return "generator" in m


def test_frozen_files_match_manifest_and_a_fresh_build() -> None:
    assert qs.verify(DOMAIN) == []
    for path, text in qs.render(DOMAIN).items():
        if _bench_set() and (path.suffix == ".jsonl" or path.name == "manifest.json"):
            continue   # the bench set holds more questions and adds `answerable`; its gold files of these 5 stay
        assert path.read_text(encoding="utf-8") == text, path


def test_best_rejects_a_tie_or_a_margin_within_rounding() -> None:
    step = Decimal("0.1")
    with pytest.raises(qs.Rejected):
        qs.pick_best({"20 mg": Decimal("-1.2"), "40 mg": Decimal("-1.2")}, False, step)
    with pytest.raises(qs.Rejected):
        qs.pick_best({"20 mg": Decimal("-1.2"), "40 mg": Decimal("-1.3")}, False, step)
    assert qs.pick_best({"20 mg": Decimal("-1.1"), "40 mg": Decimal("-1.3")}, False, step) == ("40 mg", Decimal("0.2"))


def test_groups_tie_and_not_reported() -> None:
    step, row = Decimal("0.1"), lambda i, d, w, v: {"id": i, "dose": Decimal(d), "week": Decimal(w), "value": Decimal(v),
                                                    "unit": "kg"}
    rows = [row("a", 20, 12, "-1.2"), row("b", 40, 12, "-1.25"), row("c", 20, 24, "-1.0"), row("d", 40, 24, "-1.5"),
            row("e", 40, 36, "-1.6")]
    groups = qs.decide(rows, "dose", ["20 mg", "40 mg"], ["week"], [], False, step)
    assert [g["status"] for g in groups] == ["tie", "winner", "not reported"]
    assert groups[1]["winner"] == "40 mg" and groups[2]["missing"] == ["20 mg"]


def test_seed_question_within_rounding_is_rejected(graph) -> None:
    # Weight at 24 weeks: 20 mg -1.2 kg, 40 mg -1.3 kg; a margin of 0.1 is the rounding step itself.
    spec = qs.Spec("Q-x", "best", "test", "Which {drug_a} dose lowers weight most at 24 weeks on metformin?",
                   {"subject": ["drug_a"], "measure": "weight_change", "week": 24, "context": "t2d_metformin"},
                   ("measure_variant",), candidate="dose")
    with pytest.raises(qs.Rejected):
        qs.gold(DOMAIN, spec, graph)


def test_lookup_with_duplicate_open_values_is_rejected(graph) -> None:
    # Leave week open but do not show it as a column: two rows then share every shown value.
    spec = dataclasses.replace(qs.SPECS[DOMAIN][0], open=("patient_group", "measure_variant"))
    with pytest.raises(ValueError):   # the week slot is neither stated nor open
        qs.gold(DOMAIN, spec, graph)


def test_card_answers_all_for_every_open_column() -> None:
    for point, choice in qs.INTENT[DOMAIN].items():
        assert bool(choice.column) == (point in {"time_point", "patient_group", "dose"})
        if choice.column:
            assert choice.rule == {} and choice.answer.startswith("Show every")


def test_manifest_sha_changes_when_a_question_changes(monkeypatch) -> None:
    before = qs.manifest(DOMAIN, qs.render(DOMAIN))
    first = qs.SPECS[DOMAIN][0]
    changed = [dataclasses.replace(first, text=first.text + " Really?"), *qs.SPECS[DOMAIN][1:]]
    monkeypatch.setitem(qs.SPECS, DOMAIN, changed)
    after = qs.manifest(DOMAIN, qs.render(DOMAIN))
    assert after["set_sha256"] != before["set_sha256"]
    assert after["questions"][first.qid] != before["questions"][first.qid]
    assert all(after["questions"][s.qid] == before["questions"][s.qid] for s in changed[1:])
    with pytest.raises(qs.Frozen):
        qs.build(DOMAIN)


def test_card_changes_the_sha_too(monkeypatch) -> None:
    before = qs.manifest(DOMAIN, qs.render(DOMAIN))
    policy = dict(qs.INTENT[DOMAIN])
    policy["other_names"] = dataclasses.replace(policy["other_names"], answer="Also called BRN-233.")
    monkeypatch.setitem(qs.INTENT, DOMAIN, policy)
    assert qs.manifest(DOMAIN, qs.render(DOMAIN))["set_sha256"] != before["set_sha256"]


def test_questions_use_only_papers_of_their_split(graph) -> None:
    split_of = {str(r.r).rsplit("/", 1)[-1]: str(r.s) for r in graph.query(
        "PREFIX ex: <https://w3id.org/evqa/seed#> SELECT ?r ?s WHERE { ?r ex:reportedIn/ex:split ?s }")}
    tests = [s for s in qs.SPECS[DOMAIN] if s.split == "test"]
    assert sum(s.type == "lookup" for s in tests) == 2 and sum(s.type == "best" for s in tests) == 2
    for spec in qs.SPECS[DOMAIN]:
        g = qs.gold(DOMAIN, spec, graph)
        assert {split_of[r] for r in g["row_ids"]} == {spec.split}
    records = [json.loads(x) for x in (qs.questions_dir(DOMAIN) / "test.jsonl").read_text().splitlines()]
    assert {r["split"] for r in records} == {"test"} and len(records) >= 4
    assert [r["qid"] for r in records[:4]] == ["Q-med-01", "Q-med-02", "Q-med-03", "Q-med-04"]


def test_gold_never_under_dataset() -> None:
    assert qs.gold_dir(DOMAIN).resolve().is_relative_to((REPO / "data" / "seed").resolve())
    assert not list(DATASET.rglob("gold")) and not list(DATASET.rglob("manifest.json"))
    allowed = {"qid", "domain", "split", "type", "question", "intent_card", "intent_text"}
    bench = allowed | {"answerable"}   # the 100-question set (bench.py) adds it to every record
    others = [p for p in DATASET.rglob("*") if p.is_file() and p.name != "paper.md" and p.parent.name != "questions"]
    assert others == [], "data/dataset holds only paper.md files and questions/*.jsonl (the rest is truth)"
    for path in DATASET.rglob("*.jsonl"):
        text = path.read_text(encoding="utf-8")
        assert "R-med-" not in text and "sparql" not in text.lower()
        for line in text.splitlines():
            assert set(json.loads(line)) in (allowed, bench)


def test_every_card_has_an_answer_per_open_point() -> None:
    for spec in qs.SPECS[DOMAIN]:
        rec = qs.record(DOMAIN, spec)
        assert [e["point"] for e in rec["intent_card"]] == [*spec.open, "other_names"]
        assert "{" not in rec["question"]
