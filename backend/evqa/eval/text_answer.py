"""L3-text: is the final answer right, judged from its text alone, the same way for every system (evqa or a
baseline such as PaperQA2), so their answers can be compared.

    evqa eval runs/evqa/<run> --text        -> <run>/eval_text.json, <qid>/claims.json; merged into eval.json

Answer text: a baseline's answer_text.json; for an evqa run, answer.json written out as lines (render()), each
value with its settings and its papers (from rows.jsonl).

Per question:
 1. Read claims (LLM, `reader`, ReadClaims): every value the text states, with what it is for (subject, measure,
    time point, dose, patient group, paper) and the line that states it. Code keeps a claim only when its quote is
    in the answer text and its value is in its quote and is a number (norm.normalize_value); the rest are dropped
    with a reason (claims.json).
 2. Match (code): the targets are the gold answer table rows (gold "answer.table": paper, cells, value). A claim
    matches a target when the value is the same (norm.same; "%" taken as percentage points for a percentage-point
    target), a subject of the question is named (claim subject or quote), and for each setting the targets differ
    on (time point, dose, candidate, paper, patient group) the claim states the target's one. Patient group wording
    is judged by a blind LLM (`judge`, eval/judge.py JudgeLabel: the claim's wording vs the seed's description).
 3. Score. Answerable: recall = targets matched / targets, precision = claims matching a target / claims kept,
    score = F1, exact = both 1. list: F1 of the papers the answer names (citations, claim papers, paper ids in the
    text) against the gold papers. Not reported (absent, near_miss, out_of_scope): right iff no claim was kept;
    hallucination = a claim was kept.
Not checked (reported, not scored): best winner and margin, effect verdict, trend direction words; the rows behind
them are scored. The reader and judge models are fixed per call (not the run's), so runs are graded alike; both are
recorded. Calls are cached (evqa/lm.py), so a second eval of the same texts costs nothing.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import dspy

from evqa import norm
from evqa.answer import canon
from evqa.contracts import Answer, Row, RunConfig, StepLLM, TextAnswer, TextClaim, TextClaims, read_jsonl
from evqa.eval import bootstrap, judge, prism
from evqa.seed import questions as seed_questions

VERSION = "text-1"
READER = StepLLM(backend="qwen", model="orch-model", think=False)
JUDGE = StepLLM(backend="qwen", model="sub-model-1", think=False)   # verifier on another sub-model
SETTING_KEYS = ("time_point", "dose", "candidate", "paper", "patient_group")
PP = "https://w3id.org/evqa/seed#PercentagePoint"
PERCENT = "http://qudt.org/vocab/unit/PERCENT"


class ReadClaims(dspy.Signature):
    """List every value the answer states as a result: one claim per value.

    Inputs: question is what the user asked; answer is a system's answer to it (plain text or lines).
    Output: claims, one per stated value. value_text is the value exactly as written in the answer with its unit and
    any direction words ("lowered HbA1c by 0.78 percentage points", "-0.54 mmol/L"). subject, comparator, measure,
    time_point, dose, patient_group, paper: copied from the answer for that value ("" when the answer does not say
    it for this value). paper is the paper id the answer gives (e.g. "P-med-03"). quote is the whole sentence or
    line of the answer that states the value, copied character for character.
    Only values that answer the question count: not doses, weeks, years, sample sizes or citation numbers on their
    own. A sentence with two values gives two claims with the same quote. An answer that says it cannot answer, or
    states no value, gives an empty list.
    Examples:
    answer "At week 24, drugX 20 mg lowered HbA1c by 0.78 percentage points versus placebo in adults (P-x-01)."
      -> [{value_text: "lowered HbA1c by 0.78 percentage points", subject: "drugX", comparator: "placebo",
           measure: "HbA1c", time_point: "week 24", dose: "20 mg", patient_group: "adults", paper: "P-x-01",
           quote: <the whole sentence>}]
    answer "- drugX 10 mg · 12 wk: -0.41 pp, 24 wk: -0.55 pp [P-x-02]" -> two claims (12 wk and 24 wk), same quote.
    answer "I cannot answer: no paper reports drugX on blood pressure." -> []
    """
    question: str = dspy.InputField()
    answer: str = dspy.InputField()
    claims: list[TextClaim] = dspy.OutputField()


class ReadClaimsPF(dspy.Signature):
    """List every value the answer states as an answer to the question: one claim per value.

    Inputs: question is what the user asked about invented studies, trials, court decisions or materials; answer is a
    system's answer to it (plain text or lines).
    Output: claims, one per stated value. value_text is the value exactly as written in the answer with its unit
    ("850 patients", "0.64", "65.0%", "EUR 135 thousand"). subject is the study, trial, decision or material the
    value belongs to, copied from the answer. paper is the paper id the answer gives for it (e.g. "MED-07"), "" when
    none. quote is the whole sentence or line of the answer that states the value, copied character for character.
    Count every number the answer gives for what the question asks, including counts such as patients, sites,
    judges or samples when the question asks for them. Leave out years, paper ids and citation numbers. A sentence
    with two values gives two claims with the same quote (an estimate and its confidence bounds are three claims).
    An answer that says it cannot answer, or states no value, gives an empty list.
    Examples:
    question "For the ZIMOR-3 trial, what number is reported for patients randomised?"
    answer "The ZIMOR-3 trial randomised 210 patients (MED-01)." -> [{value_text: "210 patients", subject: "the ZIMOR-3
      trial", paper: "MED-01", quote: <the whole sentence>}]
    question "What hazard ratio did the BRUMON-6 trial report for tukrapurtinib, with its 95% confidence interval?"
    answer "HR 0.64 (95% CI 0.46 to 0.91) [MED-03]" -> three claims (0.64, 0.46, 0.91), same quote.
    answer "No paper reports the number of sites for the KELAD-4 trial." -> []
    """
    question: str = dspy.InputField()
    answer: str = dspy.InputField()
    claims: list[TextClaim] = dspy.OutputField()


def is_pf(domain: str) -> bool:
    """A paperfactory domain (evqa/seed/pfbench.py gold: shared fact rows, no evqa seed graph)."""
    from evqa.seed import pfview
    return pfview.is_pf(domain)


# ---------------------------------------------------------------- answer text
def _sym(unit: str) -> str:
    return norm.units().get(unit, {}).get("symbol", unit) if unit else ""


def _cells(cells: dict[str, str]) -> str:
    return ", ".join(f"{k} {v}" for k, v in cells.items() if v and v != "not stated")


def render(ans: Answer, rows: list[Row]) -> str:
    """An evqa answer.json as plain lines: every value with its settings, unit and papers (what a reader sees)."""
    def papers(idxs: Any) -> str:
        got = sorted({rows[int(i)].paper for i in idxs or [] if 0 <= int(i) < len(rows)})
        return f" [{', '.join(got)}]" if got else ""
    lines = [ans.sentence] if ans.sentence else []
    for a in ans.table:
        lines.append(f"- {_cells(a.cells)}: {a.value} {_sym(a.unit)}{papers(a.rows)}")
    for e in ans.effects:
        lines.append(f"- {e.a} minus {e.b} ({_cells(e.group)}): {e.difference} {_sym(e.unit)}"
                     f"{f', {e.verdict}' if getattr(e, 'verdict', '') else ''}{papers(e.rows)}")
    for s in ans.trend:
        for p in s.points:
            lines.append(f"- {_cells(s.group)}, {s.axis} {p.get('at')}: {p.get('value')} {_sym(str(p.get('unit', '')))}"
                         f"{papers(p.get('rows'))}")
    for b in ans.groups:
        if b.winner:
            lines.append(f"- best ({_cells(b.group) or 'all'}): {b.winner} ({b.status})")
        for r in b.ranking:
            lines.append(f"- {r.get('candidate')} ({_cells(b.group)}): {r.get('value')} {_sym(str(r.get('unit', '')))}"
                         f"{papers(r.get('rows'))}")
    for p in ans.papers:
        lines.append(f"- paper {p.paper}")
    for c in ans.conflicts:
        for v in c.values:
            lines.append(f"- {_cells(c.cells)}: {v.get('value')} {_sym(str(v.get('unit', '')))} [{v.get('paper')}]")
    if ans.not_reported and len(lines) <= 1:
        lines.append("Not reported in the papers.")
    return "\n".join(lines)


def answer_text(qdir: Path) -> TextAnswer | None:
    """The question's answer as text: answer_text.json (baseline) or answer.json rendered (evqa); None if neither."""
    p = qdir / "answer_text.json"
    if p.is_file():
        return TextAnswer.model_validate_json(p.read_text(encoding="utf-8"))
    p = qdir / "answer.json"
    if not p.is_file():
        return None
    ans = Answer.model_validate_json(p.read_text(encoding="utf-8"))
    rows = read_jsonl(qdir / "rows.jsonl", Row) if (qdir / "rows.jsonl").is_file() else []
    used = {rows[i].paper for i in prism.answer_rows_used(ans) if 0 <= i < len(rows)}
    return TextAnswer(qid=ans.qid, system="evqa", text=render(ans, rows),
                      cannot_answer=ans.not_reported and not prism.shows_value(ans),
                      citations=sorted(used | {p.paper for p in ans.papers}))


# ---------------------------------------------------------------- claims
def _flat(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("−", "-")).strip().casefold()


def check(c: TextClaim, text: str) -> str | None:
    """Why the claim is dropped, or None when it is kept (module doc, step 1)."""
    quote = c.quote or c.value_text
    if not c.value_text.strip():
        return "no value_text"
    if _flat(quote) not in _flat(text):
        return "quote is not in the answer text"
    if _flat(c.value_text) not in _flat(quote):
        return "value_text is not in its quote"
    v = norm.normalize_value(c.value_text.replace("−", "-"))
    if v is None or (v.value is None and v.low is None):
        return "value_text holds no number"
    return None


def read_claims(question: str, text: str, lm: dspy.BaseLM, model: str, qid: str,
                sig: type[dspy.Signature] = ReadClaims) -> TextClaims:
    """ReadClaims + code checks; an unreadable reply is retried once, then gives no claims (dropped records why)."""
    sha = hashlib.sha256(text.encode()).hexdigest()
    got: list[TextClaim] | None = None
    for attempt in range(2):
        try:
            with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
                out = dspy.Predict(sig)(question=question, answer=text,
                                               config={"attempt": attempt} if attempt else {})
            got = [c if isinstance(c, TextClaim) else TextClaim.model_validate(c) for c in out.claims]
            break
        except Exception:   # noqa: BLE001 - an unreadable reply is retried once, then recorded
            continue
    if got is None:
        return TextClaims(qid=qid, text_sha256=sha, model=model, dropped=[{"claim": None, "why": "unreadable reply"}])
    kept, dropped = [], []
    for c in got:
        why = check(c, text)
        (dropped.append({"claim": c.model_dump(), "why": why}) if why else kept.append(c))
    return TextClaims(qid=qid, text_sha256=sha, model=model, claims=kept, dropped=dropped)


# ---------------------------------------------------------------- matching
def claim_value(c: TextClaim) -> norm.Value | None:
    """The claim's value read inside its quote, so direction words earlier in the sentence count ("lowered HbA1c by
    0.52 points at week 12 and by 0.54 at week 24": the second value is -0.54 too); alone when not found there."""
    vt, quote = c.value_text.replace("−", "-"), c.quote.replace("−", "-")
    i = quote.casefold().find(vt.casefold()) if vt else -1
    if i >= 0:
        found = norm.find_values(quote)
        inside = [f for f in found if i <= f.start < i + len(vt)]
        if inside:
            v = inside[0].value
            units = {f.value.unit for f in found if f.value.unit}
            if v.unit is None and len(units) == 1:   # "by 0.52 percentage points at week 12 and by 0.54 at week 24"
                v = norm.Value(v.value, units.pop(), v.decimals, v.sign_basis, v.low, v.high, v.raw)
            return v
    return norm.normalize_value(vt)


def same_value(c: TextClaim, value: str, unit: str) -> bool:
    v = claim_value(c)
    if v is None or not value:
        return False
    if unit == "":       # paperfactory rows: the number alone (units are field words such as "sites", "HR")
        return norm.same(norm.Value(v.value, None, v.decimals, v.sign_basis, v.low, v.high, v.raw),
                         norm.seed_value(value, None)).verdict == norm.Verdict.SAME  # type: ignore[arg-type]
    if unit == PP and v.unit == PERCENT:      # "-0.8 %" for an HbA1c change means percentage points
        v = norm.Value(v.value, PP, v.decimals, v.sign_basis, v.low, v.high, v.raw)
    return norm.same(v, norm.seed_value(value, unit)).verdict == norm.Verdict.SAME


def targets(g: dict[str, Any], domain: str) -> list[dict[str, Any]]:
    """The gold answer rows with a value: {row, paper, cells, value, unit (IRI of the fact's unit)}."""
    pf = is_pf(domain)
    facts = {} if pf else prism.seed_facts(domain)
    return [{"row": r["row"], "paper": r["paper"], "papers": r.get("papers", [r["paper"]]),
             "cells": dict(r.get("cells") or {}), "value": str(r["value"]), "unit": "" if pf else facts[r["row"]]["unit"]}
            for r in g.get("answer", {}).get("table", []) if str(r.get("value", ""))]


def varying(ts: list[dict[str, Any]]) -> list[str]:
    """The settings the targets differ on: a claim must state those to say which target it is."""
    out = [k for k in SETTING_KEYS if k != "paper" and len({t["cells"].get(k) for t in ts}) > 1]
    return [*out, "paper"] if len({t["paper"] for t in ts}) > 1 else out


class Matcher:
    def __init__(self, g: dict[str, Any], domain: str, judge_lm: dspy.BaseLM | None) -> None:
        self.domain = domain
        names = {} if is_pf(domain) else seed_questions.names(domain)
        slots = g.get("slots") or {}
        subj = [*(slots.get("subject") or []), *([slots["comparator"]] if slots.get("comparator") else [])]
        self.subjects = [names.get(s, s).lower() for s in subj if s != "placebo"]
        cols = g.get("answer", {}).get("columns", [])
        cand = next((c for c in cols if c["key"] == "candidate"), None)
        self.candidate_slot = canon.slot(cand["label"]) if cand else ""
        self.judge_lm = judge_lm
        self.verdicts: dict[tuple[str, str], str] = {}

    def names_subject(self, c: TextClaim) -> bool:
        said = f"{c.subject} {c.comparator} {c.quote}".lower()
        return not self.subjects or any(s in said for s in self.subjects)

    def group_ok(self, label: str, conditions: str) -> bool:
        key = (label.strip() or "not stated", conditions)
        if key not in self.verdicts:
            got = judge.ask(key[0], conditions, self.judge_lm) if self.judge_lm is not None else None
            self.verdicts[key] = got.verdict if got else "unreadable"
        return self.verdicts[key] == "matches"

    def setting_ok(self, key: str, c: TextClaim, t: dict[str, Any]) -> bool:
        want = t["paper"] if key == "paper" else t["cells"].get(key, "")
        if key == "paper":
            return c.paper.strip() == want or bool(re.search(rf"(?<![\w-]){re.escape(want)}(?![\w-])", c.quote))
        if key == "time_point":
            return bool(c.time_point) and canon.time(c.time_point) == canon.time(want)
        if key == "dose":
            return bool(c.dose) and canon.dose(c.dose) == canon.dose(want)
        if key == "candidate":
            if self.candidate_slot == "dose":
                return bool(c.dose) and canon.dose(c.dose) == canon.dose(want)
            if self.candidate_slot == "time_point":
                return bool(c.time_point) and canon.time(c.time_point) == canon.time(want)
            return want.lower() in f"{c.subject} {c.quote}".lower()
        if key == "patient_group":
            return self.group_ok(c.patient_group, want)
        return True

    def matches(self, c: TextClaim, t: dict[str, Any], keys: list[str]) -> bool:
        return (same_value(c, t["value"], t["unit"]) and self.names_subject(c)
                and all(self.setting_ok(k, c, t) for k in keys))


def _f1(r: float, p: float) -> float:
    return 0.0 if r + p == 0 else round(2 * r * p / (r + p), 4)


def _named_papers(ta: TextAnswer, claims: list[TextClaim], ids: list[str]) -> set[str]:
    named = set(ta.citations) | {c.paper.strip() for c in claims if c.paper.strip()}
    named |= {pid for pid in ids if re.search(rf"(?<![\w-]){re.escape(pid)}(?![\w-])", ta.text)}
    return named & set(ids) if ids else named


def score_question(g: dict[str, Any], ta: TextAnswer | None, tc: TextClaims | None, domain: str,
                   judge_lm: dspy.BaseLM | None, paper_ids: list[str]) -> dict[str, Any]:
    t = g["type"]
    answerable = t not in prism.NOT_REPORTED_TYPES
    if ta is None or tc is None:
        out: dict[str, Any] = {"score": 0.0, "exact": False, "claims": 0, "missing": "no answer"}
        return {**out, "said_not_reported": False, "hallucination": False} if not answerable else out
    claims = tc.claims
    base = {"claims": len(claims), "dropped": len(tc.dropped), "cannot_answer": ta.cannot_answer}
    if not answerable:
        right = not claims
        return {**base, "score": 1.0 if right else 0.0, "exact": right, "said_not_reported": right,
                "hallucination": bool(claims)}
    if g["answer"].get("entities") is not None:
        return {**base, **score_entities(g, ta.text, domain)}
    if t == "list":
        gold = {r["paper"] for r in g["answer"].get("table", [])}
        named = _named_papers(ta, claims, paper_ids)
        r = len(gold & named) / len(gold) if gold else 0.0
        p = len(gold & named) / len(named) if named else 0.0
        return {**base, "score": _f1(r, p), "exact": bool(gold) and named == gold, "recall": round(r, 4),
                "precision": round(p, 4), "papers": sorted(named), "gold_papers": sorted(gold),
                "matched": {rid: prism.seed_facts(domain)[rid]["paper"] in named for rid in g["row_ids"]}}
    ts = targets(g, domain)
    keys = varying(ts)
    if is_pf(domain):     # one gold row per value; it may stand in several papers, so the paper is not checked
        keys = [k for k in keys if k != "paper"]
    m = Matcher(g, domain, judge_lm)
    hit = {tg["row"]: False for tg in ts}
    useful = 0
    per_claim = []
    for c in claims:
        rows = [tg["row"] for tg in ts if m.matches(c, tg, keys)]
        useful += bool(rows)
        for r in rows:
            hit[r] = True
        per_claim.append({"value_text": c.value_text, "rows": rows})
    r = sum(hit.values()) / len(hit) if hit else 0.0
    p = useful / len(claims) if claims else 0.0
    return {**base, "score": _f1(r, p), "exact": bool(hit) and r == 1.0 and p == 1.0, "recall": round(r, 4),
            "precision": round(p, 4), "targets": len(ts), "settings_checked": keys, "matched": hit,
            "per_claim": per_claim, "said_not_reported": not claims,
            "patient_group_verdicts": [{"label": k[0], "conditions": k[1], "verdict": v} for k, v in m.verdicts.items()]}


def _names_in(text: str, names: list[str]) -> bool:
    flat = _flat(text)
    return any(re.search(rf"(?<![\w-]){re.escape(_flat(n))}(?![\w-])", flat) for n in names if n.strip())


def score_entities(g: dict[str, Any], text: str, domain: str) -> dict[str, Any]:
    """list / conflict questions answered by names (paperfactory): F1 of the gold entities the text names against
    every entity of the same kinds it names (data/seed/<d>/entities.json). Code only."""
    from evqa.paths import domain_dir
    ents = json.loads((domain_dir(domain) / "entities.json").read_text(encoding="utf-8"))
    gold = {e["id"] for e in g["answer"]["entities"]}
    kinds = {ents[e]["kind"] for e in gold if e in ents}
    named = {eid for eid, e in ents.items() if e["kind"] in kinds and _names_in(text, [e["label"], *e.get("alt", [])])}
    r = len(gold & named) / len(gold) if gold else 0.0
    p = len(gold & named) / len(named) if named else 0.0
    return {"score": _f1(r, p), "exact": bool(gold) and named == gold, "recall": round(r, 4), "precision": round(p, 4),
            "entities": sorted(named), "gold_entities": sorted(gold),
            "matched": {e["row"]: e["id"] in named for e in g["answer"]["entities"]}}


# ---------------------------------------------------------------- run
def _totals(qs: dict[str, dict[str, Any]], golds: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ans = [q for qid, q in qs.items() if golds[qid]["type"] not in prism.NOT_REPORTED_TYPES]
    nr = [q for qid, q in qs.items() if golds[qid]["type"] in prism.NOT_REPORTED_TYPES]
    per_type: dict[str, Any] = {}
    for t in prism.TYPES:
        mine = [q for qid, q in qs.items() if golds[qid]["type"] == t]
        if mine:
            per_type[t] = {"questions": len(mine), "l3_text": prism._mean([q["score"] for q in mine]),
                           "exact": sum(bool(q["exact"]) for q in mine)}
    return {"l3_text": prism._mean([q["score"] for q in ans]),
            "l3_text_exact": sum(bool(q["exact"]) for q in ans),
            "text_not_reported": {"questions": len(nr), "accuracy": prism._rate([q["score"] == 1.0 for q in nr]),
                                  "hallucination": prism._rate([q["hallucination"] for q in nr])},
            "per_type": per_type,
            "intervals": {"l3_text": bootstrap.mean_interval([q["score"] for q in ans]),
                          "text_not_reported_accuracy": bootstrap.mean_interval(
                              [float(q["score"] == 1.0) for q in nr])}}


def score_run(run_dir: Path, reader: StepLLM = READER, judge_llm: StepLLM = JUDGE, reader_lm: dspy.BaseLM | None = None,
              judge_lm: dspy.BaseLM | None = None) -> dict[str, Any]:
    """Score every question of the run (the questions prism scores); write eval_text.json and claims.json files,
    and merge the result into eval.json. Tests pass reader_lm / judge_lm (fake LMs)."""
    run_dir = Path(run_dir)
    cfg = RunConfig.load(run_dir / "config.yaml")
    if reader_lm is None or judge_lm is None:
        from evqa.lm import make_lm
        reader_lm = reader_lm or make_lm(reader)
        judge_lm = judge_lm or make_lm(judge_llm)
    golds = prism.gold(cfg.domain)
    qids = list(cfg.questions) or [q for q, g in golds.items() if g.get("split") == cfg.split]
    from evqa import corpus
    asked = {q["qid"]: q["question"] for q in corpus.questions(cfg.domain, cfg.split)}
    paper_ids = sorted(corpus.papers(cfg.domain))
    model = f"{reader.backend}:{reader.model}"
    qs: dict[str, dict[str, Any]] = {}
    for qid in [q for q in qids if q in golds]:
        qdir = run_dir / qid
        ta = answer_text(qdir)
        tc = None
        if ta is not None:
            path = qdir / "claims.json"
            sha = hashlib.sha256(ta.text.encode()).hexdigest()
            old = TextClaims.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None
            if old is not None and old.text_sha256 == sha and old.model == model:
                tc = old
            else:
                args = (asked.get(qid, ""), ta.text, reader_lm, model, qid)
                tc = read_claims(*args, sig=ReadClaimsPF) if is_pf(cfg.domain) else read_claims(*args)
                qdir.mkdir(parents=True, exist_ok=True)
                path.write_text(tc.model_dump_json(indent=2) + "\n", encoding="utf-8")
        qs[qid] = score_question(golds[qid], ta, tc, cfg.domain, judge_lm, paper_ids)
    out = {"version": VERSION, "run_id": run_dir.name, "system": cfg.system or "evqa",
           "reader": model, "judge": f"{judge_llm.backend}:{judge_llm.model}", "totals": _totals(qs, golds),
           "questions": qs}
    (run_dir / "eval_text.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    if is_pf(cfg.domain):     # no seed graph, so no L0-L3 from prism: eval.json holds the text score only
        (run_dir / "eval.json").write_text(json.dumps(merge({"run_id": run_dir.name, "domain": cfg.domain}, out),
                                                      indent=2) + "\n", encoding="utf-8")
    else:
        prism.score_run(run_dir, cfg.domain)      # rewrites eval.json with this text score merged in (merge())
    return out


def merge(ev: dict[str, Any], text: dict[str, Any]) -> dict[str, Any]:
    """Put the text scores into an eval.json dict (prism.score_run calls this too, so a re-score keeps them):
    totals l3_text, l3_text_exact, text_not_reported, per_type[t].l3_text, intervals.l3_text, questions[q].l3_text.
    A baseline fact Find found ("unscored") is blamed on the answer unless the answer text states it ("none")."""
    tt = text["totals"]
    tot = ev.setdefault("totals", {})
    tot["l3_text"], tot["l3_text_exact"] = tt["l3_text"], tt["l3_text_exact"]
    tot["text_not_reported"] = tt["text_not_reported"]
    for t, row in tt["per_type"].items():
        tot.setdefault("per_type", {}).setdefault(t, {})["l3_text"] = row["l3_text"]
    ev.setdefault("intervals", {})["l3_text"] = tt["intervals"]["l3_text"]
    ev["text_eval"] = {k: text[k] for k in ("version", "reader", "judge")}
    blame = tot.get("blame")
    for qid, q in (ev.get("questions") or {}).items():
        tq = text["questions"].get(qid)
        if tq is None:
            continue
        q["l3_text"] = {k: tq[k] for k in ("score", "exact", "claims") if k in tq}
        matched = tq.get("matched") or {}
        for f in q.get("facts", []):
            if f.get("blame") == "unscored":
                f["blame"] = "none" if matched.get(f["id"]) else "answer"
                f["in_answer"] = bool(matched.get(f["id"]))
                q["blame"]["unscored"] -= 1
                q["blame"][f["blame"]] = q["blame"].get(f["blame"], 0) + 1
                if isinstance(blame, dict):
                    blame["unscored"] = blame.get("unscored", 0) - 1
                    blame[f["blame"]] = blame.get(f["blame"], 0) + 1
    return ev
