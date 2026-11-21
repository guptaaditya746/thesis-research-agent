"""D1: a BM25 baseline (word matching, no model): how easy is each question for plain search?

For each question, every sentence of the question's papers is ranked by BM25 against the question text. The rank of
the best gold sentence (a sentence tagged for one of the question's gold facts) is recorded. Ties count against the
gold sentence (pessimistic rank), so a question whose gold sentence ties with others is not called easy.
Reported overall and per question_type: share of questions with gold at rank 1, share in the top 5, median rank,
and questions with no tagged gold sentence (left out of the ranks).
"""
from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from typing import Any

K1, B = 1.5, 0.75
WORD = re.compile(r"\w+")


def tokens(text: str) -> list[str]:
    return WORD.findall(text.lower())


def bm25(query: list[str], docs: list[list[str]]) -> list[float]:
    n = len(docs)
    avg = sum(map(len, docs)) / max(1, n)
    df = Counter(t for d in docs for t in set(d))
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in set(query)}
    out = []
    for d in docs:
        tf = Counter(d)
        out.append(sum(idf[t] * tf[t] * (K1 + 1) / (tf[t] + K1 * (1 - B + B * len(d) / max(1e-9, avg)))
                       for t in query if tf[t]))
    return out


def gold_rank(q: dict[str, Any], tagged: dict[str, Any]) -> int | None:
    """Rank (1 = best) of the best gold sentence among all sentences of the question's papers; None: no gold
    sentence was tagged."""
    sents, gold = [], []
    for pid in q["papers"]:
        t = tagged[pid]
        spans = {tuple(sp) for i in q["gold"] for sp in t["spans"].get(i, [])}
        for s in t["sentences"]:
            gold.append(tuple(s[:2]) in spans)
            sents.append(s[2])
    if not any(gold):
        return None
    scores = bm25(tokens(q["text"]), [tokens(s) for s in sents])
    best = max(sc for sc, g in zip(scores, gold) if g)
    return sum(sc >= best for sc, g in zip(scores, gold) if not g) + 1


def summary(ranks: list[int | None]) -> dict[str, Any]:
    r = [x for x in ranks if x is not None]
    return {"questions": len(ranks), "no_gold_sentence": len(ranks) - len(r),
            "rank1_share": round(sum(x == 1 for x in r) / len(r), 3) if r else None,
            "top5_share": round(sum(x <= 5 for x in r) / len(r), 3) if r else None,
            "median_rank": statistics.median(r) if r else None}


def report(questions: list[dict[str, Any]], tagged: dict[str, Any]) -> dict[str, Any]:
    ranks = {q["id"]: gold_rank(q, tagged) for q in questions}
    by_type: dict[str, list[int | None]] = {}
    for q in questions:
        by_type.setdefault(q.get("question_type", "unknown"), []).append(ranks[q["id"]])
    return {"about": __doc__.split("\n\n")[1].replace("\n", " "), "all": summary(list(ranks.values())),
            "by_question_type": {k: summary(v) for k, v in sorted(by_type.items())}, "ranks": ranks}
