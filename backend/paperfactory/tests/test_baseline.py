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


def test_a_failed_paper_is_cut_from_questions_not_the_questions_dropped() -> None:
    """Qwen smoke llm: one failed paper of three removed every question; now only that paper goes."""
    from paperfactory.evaluate import scope_questions
    facts = {"A": {"papers": {"P1": "claim"}}, "B": {"papers": {"P2": "decoy"}}, "C": {"papers": {"P2": "claim",
                                                                                                    "P3": "claim"}}}
    qs = [{"id": "P1:t", "papers": ["P1", "P2"], "gold": ["A", "B"], "sparql": "q"},
          {"id": "P2:t", "papers": ["P2", "P1"], "gold": ["B"], "sparql": "q"},
          {"id": "P3:t", "papers": ["P3", "P2"], "gold": ["C"], "sparql": "q"},
          {"id": "P1:u", "papers": ["P1", "P2"], "gold": ["B"], "sparql": "q"}]
    out, rescoped, dropped = scope_questions(qs, facts, {"P1", "P3"})
    assert [(q["id"], q["papers"], q["gold"]) for q in out] == [("P1:t", ["P1"], ["A"]), ("P3:t", ["P3"], ["C"])]
    assert rescoped[0] == {"id": "P1:t", "papers_removed": ["P2"], "gold_removed": ["B"]}
    assert {d["id"]: d["reason"] for d in dropped} == {"P2:t": "own paper left out", "P1:u": "no gold left"}


def test_leak_report_shows_hit_sentences_and_copied_pack_words(tmp_path) -> None:
    from paperfactory import config
    from paperfactory.evaluate import Eval
    _, gold = seed.make(PILOT, LAW, per_question=3, seed=1)
    sents = ["Rusk relied on section 14 of the Act.", "Marrin v. Tolst Media and Rusk are cited.",
             "The court in Rusk discussed Marrin at length."]
    t = tagged(sents, {"K5-relies_on-S14": [0]})
    s = config.Settings("law", "argument", out=str(tmp_path), leak_trials=2)
    (tmp_path / "work" / "L-01").mkdir(parents=True)
    (tmp_path / "work" / "L-01" / "paper.md").write_text(" ".join(sents))

    def call(role, step, system, user, out, check=None):
        lines = user.split("SENTENCES:\n")[1].splitlines()
        return {"pick": next(int(x.split(".")[0]) for x in lines if "section 14" in x)}
    r = Eval(s, PILOT, LAW, gold, call).leak({"L-01": t})
    assert r["hits"] == 2 and r["hit_sentences"][0]["planted"] == sents[0]
    assert r["planted_with_pack_words"] == {"sentences": 1, "verbatim": 1, "share": 1.0}     # "relied on"
