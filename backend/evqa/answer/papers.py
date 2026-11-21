"""Answer for list questions ("which studies tested X?"): the papers with a row that fits the spec. Code only.

A paper is listed when at least one of its rows fits the spec exactly (checked quote, a spec subject or any subject
when the question names none, the measure when the question names one, every fixed slot); the value need not be
readable. Each paper comes with its rows, their quotes, and the design facts the rows state (subject, dose, time
point, patient group, measure). No fitting row -> not_reported.
"""
from __future__ import annotations

from evqa.answer import canon
from evqa.answer.core import NOT_REPORTED, NOT_STATED, cell, fits, with_conflicts
from evqa.contracts import Answer, AnswerRow, PaperEntry, Row, Spec

DESIGN = (("subject", "subject"), ("dose", "dose"), ("time point", "time_point"), ("patient group", "patient_group"),
          ("measure", "measure"))


def papers(spec: Spec, rows: list[Row]) -> Answer:
    used = [(i, r) for i, r in enumerate(rows) if fits(r, spec, need_number=False, index=i)]
    ans = Answer(qid=spec.qid, type="list", columns=["paper"])
    what = " ".join(x for x in (", ".join(n.label for n in spec.subjects), spec.measure.label) if x) or "this"
    if not used:
        ans.not_reported, ans.sentence = True, NOT_REPORTED
        return ans
    by: dict[str, list[tuple[int, Row]]] = {}
    for i, r in used:
        by.setdefault(r.paper, []).append((i, r))
    for paper in sorted(by):
        got = by[paper]
        design: dict[str, list[str]] = {}
        for label, k in DESIGN:
            seen = {(r.measure if k == "measure" else cell(r, k)) for _, r in got}
            seen.discard(NOT_STATED)
            if seen:
                design[label] = sorted(seen, key=lambda v: canon.sort_key(k, v))
        quotes = list(dict.fromkeys(r.quote for _, r in got))
        ans.papers.append(PaperEntry(paper=paper, rows=[i for i, _ in got], quotes=quotes, design=design))
        ans.table.append(AnswerRow(cells={"paper": paper}, value="", unit="", rows=[i for i, _ in got]))
    n = len(ans.papers)
    ans.sentence = f"{n} stud{'y' if n == 1 else 'ies'} report {what}: " + "; ".join(map(_said, ans.papers)) + "."
    return with_conflicts(ans, used)


def _said(p: PaperEntry) -> str:
    facts = "; ".join(f"{k} {', '.join(p.design[k])}" for k in ("dose", "time point") if k in p.design)
    return f"{p.paper} ({facts})" if facts else p.paper
