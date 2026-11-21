"""D1: BM25 rank of the gold sentence; question_type on every question."""
from __future__ import annotations

from paperfactory import baseline, seed
from paperfactory.tests.test_offline import LAW, PILOT


def tagged(sents: list[str], spans: dict[str, list[int]]) -> dict:
    offs, a = [], 0
    for s in sents:
        offs.append([a, a + len(s), s])
        a += len(s) + 1
    return {"sentences": offs, "spans": {i: [offs[n][:2] for n in ns] for i, ns in spans.items()}}


def test_gold_rank_and_pessimistic_ties() -> None:
    t = {"P1": tagged(["Rusk relied on section 9.", "The weather was fine.", "Rusk relied on section 9."],
                      {"F1": [0]})}
    q = {"id": "q", "text": "Did Rusk rely on section 9?", "papers": ["P1"], "gold": ["F1"], "question_type": "pair"}
    assert baseline.gold_rank(q, t) == 2                       # ties with a non-gold copy: counted against gold
    t["P1"]["spans"]["F1"] = []
    assert baseline.gold_rank(q, t) is None
    r = baseline.report([q], t)
    assert r["all"]["no_gold_sentence"] == 1 and r["by_question_type"]["pair"]["questions"] == 1


def test_gold_at_rank_one() -> None:
    t = {"P1": tagged(["Marrin was decided in 2019.", "In Rusk the court distinguished Marrin."], {"F": [1]})}
    q = {"id": "q", "text": "How did Rusk treat Marrin?", "papers": ["P1"], "gold": ["F"]}
    assert baseline.report([q], t)["all"] == {"questions": 1, "no_gold_sentence": 0, "rank1_share": 1.0,
                                             "top5_share": 1.0, "median_rank": 1}


def test_every_question_has_a_type() -> None:
    _, gold = seed.make(PILOT, LAW, per_question=3, seed=1)
    assert {q["question_type"] for q in gold["questions"]} <= set(seed.QUESTION_TYPES.values())
    assert all("question_type" in q for q in gold["questions"])
