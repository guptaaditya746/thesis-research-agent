"""The benchmark question set: 50 in-corpus questions and 50 whose true answer is "not reported", made from the seed.

Everything except the wording is code. Per question type a SPARQL template over seed.ttl gives the gold; the
candidates of each type are every slot combination the seed supports (found by SPARQL too), so the generator works
unchanged on a bigger seed. A seeded random order and a quota per type choose the questions; a type the seed cannot
fill gives its places to the other types of its half and is reported as a shortfall. The LLM only rewords the code's
template text (reword.py: code check + blind verifier).

The blueprint's generator section (profile.py) gives every domain word: slot names (context, factor, time), the
question templates, quota, out-of-scope pools and near-miss context variants. Examples below are medical.

In-corpus types (gold = rows of the seed):
  lookup    every matching row, unique on the open-point columns (questions.gold).
  effect    "does A beat B on M": one row per study and time point/group, the reported difference and a verdict
            (A better / B better / no clear difference: |difference| not above the rounding step). Needs a comparator.
  best      which factor value or subject is best, winner needs a margin above the rounding step (questions.gold).
  trend     M over time (factor stated) or over the factor (time stated): the rows, plus one ordered series per group
            with its direction (goes down / goes up / flat / mixed, steps within rounding count as flat).
  list      which studies test X: the papers holding a matching row.
  conflict  one fact (subject, factor, time, measure, context) reported by two papers with values further apart than
            the rounding step: both rows, flagged conflict.
Not-reported types (gold status "not_reported", `why` made by code, 0 rows from the question's SPARQL):
  absent        a corpus subject and a fact no paper gives (another time, measure or context).
  near_miss     close to a real fact but the wrong context or factor value (elderly vs adults, 30 mg between 20 and
                40); gold keeps the closest real fact ids, to see whether a system answers with them.
  out_of_scope  a subject or topic in no paper.md and nowhere in seed.ttl (checked by code, word by word).

The blueprint's hand-written questions (questions.SPECS) are kept as they are; new ids continue after them. Questions
about practice papers go to practice.jsonl, the rest (and every out-of-scope one) to test.jsonl.
"""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

from rdflib import Graph

from evqa.paths import DATASET, REPO, domain_dir
from evqa.seed import build as seed_build
from evqa.seed import questions as qs
from evqa.seed import reword
from evqa.seed.check import full_graph
from evqa.seed.profile import Gen, default_gen
from evqa.seed.rdf import query as locked_query

IN_CORPUS = ("lookup", "effect", "best", "trend", "list", "conflict")
NOT_REPORTED = ("absent", "near_miss", "out_of_scope")
TYPES = IN_CORPUS + NOT_REPORTED
QUOTA: dict[str, int] | None = None   # override (tests); else the blueprint's generator.bench.quota


# ---------------------------------------------------------------- what the seed holds

FACTS = """PREFIX ex: <https://w3id.org/evqa/seed#>
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX dcterms: <http://purl.org/dc/terms/>
SELECT ?r ?paper ?split ?title ?role ?subject ?comparator ?measure ?context ?stat ?factor ?time ?value WHERE {
  ?r a ex:Result ; ex:reportedIn ?paper ; ex:subject ?subject ;
     sosa:observedProperty ?measure ; sosa:hasFeatureOfInterest ?context ; ex:statistic ?stat ;
     ex:condition/ex:setting/qudt:numericValue ?factor ; ex:atTime/qudt:numericValue ?time ;
     sosa:hasResult/qudt:numericValue ?value .
  OPTIONAL { ?r ex:comparator ?comparator }
  ?paper ex:split ?split ; dcterms:title ?title .
  OPTIONAL { ?paper ex:role ?role }
}"""


def _local(iri: Any) -> str:
    return str(iri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _num(x: Any) -> str:
    return format(Decimal(str(x)).normalize(), "f")


def core(label: str, gen: Gen | None = None) -> str:
    """What a question names of a measure label (the blueprint's measure_core pattern; e.g. 'HbA1c')."""
    return (gen or default_gen()).core(label)


class World:
    """The seed seen by key: facts (blueprint keys, Decimal values; settings under the blueprint's slot names),
    labels, papers, paper texts."""

    def __init__(self, domain: str, g: Graph | None = None, texts: dict[str, str] | None = None,
                 seed_text: str | None = None):
        self.domain = domain
        self.g = g if g is not None else full_graph(domain)
        bp = seed_build.load_blueprint(domain)
        self.gen = gen = Gen(bp)
        self.C, self.F, self.T = gen.C, gen.F, gen.T
        self.labels = qs.names(domain)                                   # item key -> label
        item_of = {qs.item_iri(domain, k)[2:]: k for k in bp["items"]}  # seed local name -> key
        self.measures = {k: {"label": v["label"], "core": gen.core(v["label"]), "alt": list(v.get("alt", [])),
                             "hib": bool(v["higher_is_better"]), "step": Decimal(1).scaleb(-v["decimals"])}
                         for k, v in bp["measures"].items()}
        self.contexts = {k: v["label"] for k, v in gen.section("context").items()}
        measure_of = {seed_build.slug(k): k for k in self.measures}
        context_of = {seed_build.slug(k): k for k in self.contexts}
        self.papers: dict[str, dict[str, str]] = {}
        self.facts: list[dict[str, Any]] = []
        for r in locked_query(self.g, FACTS):
            subj, meas, ctx = item_of.get(_local(r.subject)), measure_of.get(_local(r.measure)), \
                context_of.get(_local(r.context))
            comp = item_of.get(_local(r.comparator)) if r.comparator is not None else None
            if None in (subj, meas, ctx) or (r.comparator is not None and comp is None):
                continue
            pid = _local(r.paper)
            self.papers[pid] = {"split": str(r.split), "title": str(r.title), "role": str(r.role or "")}
            self.facts.append({"id": _local(r.r), "paper": pid, "split": str(r.split), "subject": subj,
                               "comparator": comp, "measure": meas, self.C: ctx, "stat": _local(r.stat),
                               self.F: Decimal(str(r.factor.toPython())), self.T: Decimal(str(r.time.toPython())),
                               "value": Decimal(str(r.value))})
        self.facts.sort(key=lambda f: f["id"])
        # A subject whose papers are all distractors is asked about by no question (it stays in the corpus as noise).
        roles: dict[str, set[str]] = {}
        for f in self.facts:
            roles.setdefault(f["subject"], set()).add(self.papers[f["paper"]]["role"])
        self.avoid = {k for k, v in roles.items() if v == {"distractor"}}
        self.cfacts = [f for f in self.facts if f["subject"] not in self.avoid]   # facts questions are made from
        if texts is None:
            texts = {p.parent.name: p.read_text(encoding="utf-8")
                     for p in sorted((DATASET / domain).glob("*/paper.md"))}
        self.texts = {k: v.lower() for k, v in texts.items()}
        if seed_text is None:
            seed_text = (domain_dir(domain) / "seed.ttl").read_text(encoding="utf-8")
        self.seed_text = seed_text.lower()

    def bench_cfg(self) -> dict[str, Any]:
        return self.gen.g.get("bench") or {}

    def template(self, key: str) -> list[str]:
        return self.bench_cfg()["templates"][key]

    # a fact usable under the standard card (the blueprint's statistic, against its default comparator)
    def card_facts(self, split: str | None = None) -> list[dict[str, Any]]:
        return [f for f in self.cfacts if f["stat"] == self.gen.statistic
                and f["comparator"] == self.gen.default_comparator and (split is None or f["split"] == split)]

    def split_share(self) -> dict[str, float]:
        """Share of the papers in each split (questions follow it)."""
        n = Counter(p["split"] for p in self.papers.values())
        return {k: v / sum(n.values()) for k, v in n.items()}

    def splits(self) -> list[str]:
        return sorted({f["split"] for f in self.facts})

    def subject_split(self, subject: str) -> str | None:
        found = {f["split"] for f in self.facts if f["subject"] == subject}
        return found.pop() if len(found) == 1 else None

    def subject_text(self, subject: str) -> str:
        """The paper.md text of every paper holding a row of this subject (lower case)."""
        pids = sorted({f["paper"] for f in self.facts if f["subject"] == subject})
        return "\n".join(self.texts.get(p, "") for p in pids)

    def new_group(self, label: str, terms: tuple[str, ...]) -> bool:
        """A near-miss context must differ from every seed context: none of its marker terms in any seed context
        label, and its words not all inside one seed context label."""
        labels = [x.lower() for x in self.contexts.values()]
        if any(mentions(x, t) for x in labels for t in terms):
            return False
        mine = set(reword._content(label))
        return not any(mine <= set(reword._content(x)) for x in labels)

    def absent_everywhere(self, term: str) -> bool:
        """True when `term` is in no paper.md and not in seed.ttl (word-boundary, case-insensitive)."""
        pat = re.compile(rf"(?<![a-z0-9]){re.escape(term.lower())}", re.I)
        return not pat.search(self.seed_text) and not any(pat.search(t) for t in self.texts.values())


def mentions(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}", text) is not None


# ---------------------------------------------------------------- candidates (one Spec per slot combination)

def _open(fixed: dict[str, Any], variant: str | None = None, *, gen: Gen | None = None) -> tuple[str, ...]:
    """The open points of a question: every setting the question does not state, then how the value is measured."""
    gen = gen or default_gen()
    pts = [p for role, p in gen.g["open_points"].items() if fixed.get(gen.g[role]["slot"]) is None]
    return (*pts, variant or gen.g["measure_variant"])


def _dir(w: World, m: str, most: bool = False) -> str:
    return w.gen.verb(w.measures[m]["hib"], most)


def _plain(v: Any) -> Any:
    """Decimal -> int or float, as the kept specs write numbers (sparql filters on int/float, json can dump it)."""
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    return v


def _spec(qtype: str, split: str, text: str, fixed: dict[str, Any], *, kind: str, open_: tuple[str, ...] | None = None,
          candidate: str | None = None, gen: Gen | None = None, **extra: Any) -> qs.Spec:
    fixed = {k: _plain(v) for k, v in fixed.items()}
    return qs.Spec("", qtype, split, text, fixed, open_ if open_ is not None else _open(fixed, gen=gen),
                   candidate=candidate, extra={"kind": kind, **extra})


def _words(w: World, m: str | None = None, **more: Any) -> dict[str, Any]:
    """Template fields: the measure as questions name it, its direction verbs, plus `more`."""
    out: dict[str, Any] = dict(more)
    if m is not None:
        out.update(measure=w.measures[m]["core"], verb=_dir(w, m), verbs=_dir(w, m, True))
    return out


def _say(w: World, key: str, **fields: Any) -> tuple[str, str]:
    """(kind, question text) of a template; not-reported templates give (kind, text, why)."""
    kind, text, *why = w.template(key)
    return kind, text.format(**fields)


def candidates(w: World) -> dict[str, list[qs.Spec]]:
    """Every candidate question of every type the seed supports (gold not checked yet)."""
    out: dict[str, list[qs.Spec]] = {t: [] for t in TYPES}
    L, C, F, T, gen = w.labels, w.C, w.F, w.T, w.gen
    fp, tp = (lambda v: gen.phrase("factor", v)), (lambda v: gen.phrase("time", v))
    pt = gen.g["open_points"]

    def add(qtype: str, key: str, split: str, fixed: dict[str, Any], words: dict[str, Any], **kw: Any) -> None:
        kind, text = _say(w, key, **words)
        out[qtype].append(_spec(qtype, split, text, fixed, kind=kind, gen=gen, **kw))

    for split in w.splits():
        facts = w.card_facts(split)
        sm = sorted({(f["subject"], f["measure"]) for f in facts})
        for a, m in sm:
            fm = [f for f in facts if f["subject"] == a and f["measure"] == m]
            fvals = sorted({f[F] for f in fm})
            tvals = sorted({f[T] for f in fm})
            ctxs = sorted({f[C] for f in fm})
            base = {"subject": [a], "measure": m}
            wd = _words(w, m, subject=L[a])
            add("lookup", "lookup_subject", split, base, wd)
            for d in fvals:
                add("lookup", "lookup_factor", split, {**base, F: d}, {**wd, "factor": fp(d)})
                if len({f[T] for f in fm if f[F] == d}) >= 2:
                    add("trend", "trend_over_time", split, {**base, F: d}, {**wd, "factor": fp(d)}, axis=pt["time"])
            for tv in tvals:
                add("lookup", "lookup_time", split, {**base, T: tv}, {**wd, "time": tp(tv)})
                at = [f for f in fm if f[T] == tv]
                if len({f[F] for f in at}) >= 2:
                    add("trend", "trend_over_factor", split, {**base, T: tv}, {**wd, "time": tp(tv)},
                        axis=pt["factor"])
                    add("best", "best_factor_any_context", split, {**base, T: tv}, {**wd, "time": tp(tv)},
                        open_=(pt["context"], gen.g["measure_variant"]), candidate=F)
                    for cx in sorted({f[C] for f in at}):
                        if len({f[F] for f in at if f[C] == cx}) >= 2:
                            add("best", "best_factor", split, {**base, T: tv, C: cx},
                                {**wd, "time": tp(tv), "context": w.contexts[cx]},
                                open_=(gen.g["measure_variant"],), candidate=F)
                for d in sorted({f[F] for f in at}):
                    keyed: dict[str, set] = {}
                    for f in at:
                        if f[F] == d:
                            keyed.setdefault(f[C], set()).add(f["paper"])
                    if any(len(p) >= 2 for p in keyed.values()):
                        add("conflict", "conflict", split, {**base, F: d, T: tv},
                            {**wd, "factor": fp(d), "time": tp(tv)})
            for cx in ctxs:
                add("lookup", "lookup_context", split, {**base, C: cx}, {**wd, "context": w.contexts[cx]})
            add("list", "list_subject_measure", split, base, wd, open_=())
        for a in sorted({f["subject"] for f in w.cfacts if f["split"] == split}):
            add("list", "list_subject", split, {"subject": [a]}, {"subject": L[a]}, open_=())
            for cx in sorted({f[C] for f in w.cfacts if f["split"] == split and f["subject"] == a}):
                add("list", "list_subject_context", split, {"subject": [a], C: cx},
                    {"subject": L[a], "context": w.contexts[cx]}, open_=())
        for m, cx in sorted({(f["measure"], f[C]) for f in w.cfacts if f["split"] == split}):
            add("list", "list_measure_context", split, {"measure": m, C: cx},
                _words(w, m, context=w.contexts[cx]), open_=())
        # best between subjects: two subjects of this split with the measure at the same time
        subjects = sorted({f["subject"] for f in facts})
        for i, a in enumerate(subjects):
            for b in subjects[i + 1:]:
                for m in sorted(w.measures):
                    wa = {f[T] for f in facts if f["subject"] == a and f["measure"] == m}
                    wb = {f[T] for f in facts if f["subject"] == b and f["measure"] == m}
                    for tv in sorted(wa & wb):
                        add("best", "best_subjects", split, {"subject": [a, b], "measure": m, T: tv},
                            _words(w, m, subject=L[a], subject_b=L[b], time=tp(tv)),
                            open_=(pt["factor"], pt["context"], gen.g["measure_variant"]), candidate="subject")
        # effect: A against its stated comparator (default or another subject), the blueprint's statistic
        eff = [f for f in w.cfacts if f["split"] == split and f["stat"] == gen.statistic
               and f["comparator"] is not None]
        tpl = w.bench_cfg().get("templates", {})
        for a, b, m in sorted({(f["subject"], f["comparator"], f["measure"]) for f in eff}):
            fx = {"subject": [a], "comparator": b, "measure": m}
            active = b != gen.default_comparator
            than = tpl["than_active" if active else "than_default"].format(comparator=L.get(b, b))
            vs = tpl.get("active_suffix", "") if active else ""
            variant = gen.g["difference_variant"]
            wd = _words(w, m, subject=L[a], than=than)
            kind, text = _say(w, "effect_subject", **wd)
            out["effect"].append(_spec("effect", split, text, fx, kind=kind + vs, open_=_open(fx, variant, gen=gen)))
            for d in sorted({f[F] for f in eff if (f["subject"], f["comparator"], f["measure"]) == (a, b, m)}):
                fd = {**fx, F: d}
                kind, text = _say(w, "effect_factor", **wd, factor=fp(d))
                out["effect"].append(_spec("effect", split, text, fd, kind=kind + vs,
                                           open_=_open(fd, variant, gen=gen)))
    _not_reported(w, out)
    return out


def _nr(w: World, out: dict[str, list[qs.Spec]], qtype: str, key: str, split: str, fixed: dict[str, Any],
        fields: dict[str, Any], kind_tail: str = "", **kw: Any) -> None:
    """Add one not-reported candidate: template text and `why` from the blueprint."""
    kind, text, why = w.template(key)
    out[qtype].append(_spec(qtype, split, text.format(**fields), fixed, kind=kind + kind_tail, gen=w.gen, **kw,
                            why=why.format(**fields)))


def _not_reported(w: World, out: dict[str, list[qs.Spec]]) -> None:
    L, C, F, T, gen = w.labels, w.C, w.F, w.T, w.gen
    cfg = w.bench_cfg()
    fp, tp = (lambda v: gen.phrase("factor", v)), (lambda v: gen.phrase("time", v))
    pt = gen.g["open_points"]
    all_tvals = sorted({f[T] for f in w.cfacts} | {Decimal(x) for x in gen.g["time"].get("extra", [])})
    for a in sorted({f["subject"] for f in w.card_facts()}):
        split = w.subject_split(a)
        if split is None:
            continue
        fa = [f for f in w.card_facts(split) if f["subject"] == a]
        text = w.subject_text(a)
        for m in sorted({f["measure"] for f in fa}):
            fm = [f for f in fa if f["measure"] == m]
            wd = _words(w, m, subject=L[a])
            tvals = sorted({f[T] for f in fm})
            fvals = sorted({f[F] for f in fm})
            # absent: another time
            for d in fvals:
                for tv in all_tvals:
                    if tv in tvals or gen.mentioned("time", text, tv):
                        continue
                    _nr(w, out, "absent", "absent_time", split, {"subject": [a], "measure": m, F: d, T: tv},
                        {**wd, "factor": fp(d), "time": tp(tv), "times": ", ".join(_num(x) for x in tvals)})
            # absent: a corpus context the subject was not tested in
            for cx in sorted(set(w.contexts) - {f[C] for f in fa}):
                if any(f[C] == cx for f in w.cfacts):
                    _nr(w, out, "absent", "absent_context", split, {"subject": [a], "measure": m, C: cx},
                        {**wd, "context": w.contexts[cx]})
            # near miss: a close context (a regex variant of a real context label)
            for cx in sorted({f[C] for f in fm}):
                for v in cfg.get("context_variants", []):
                    label = re.sub(v["sub"], v["with"], w.contexts[cx], count=v.get("count", 0))
                    terms = tuple(v["terms"])
                    if label == w.contexts[cx] or not w.new_group(label, terms):
                        continue
                    if any(mentions(text, t) for t in terms):
                        continue
                    near = [f["id"] for f in fm if f[C] == cx]
                    _nr(w, out, "near_miss", "near_miss_context", split,
                        {"subject": [a], "measure": m, C: qs.LABEL + label},
                        {**wd, "context": label, "real": w.contexts[cx]}, kind_tail=f":{v['name']}",
                        open_=(pt["factor"], pt["time"], gen.g["measure_variant"]), near=near)
            # near miss: a factor value between two reported values, or double the highest
            near_fvals = {(lo + hi) / 2: (lo, hi) for lo, hi in zip(fvals, fvals[1:], strict=False)}
            if fvals:
                near_fvals[fvals[-1] * 2] = (fvals[-1],)
            for d, around in sorted(near_fvals.items()):
                d = d.normalize()
                if d in fvals or d != d.to_integral_value() or gen.mentioned("factor", text, d):
                    continue
                near = [f["id"] for f in fm if f[F] in around]
                _nr(w, out, "near_miss", "near_miss_factor", split, {"subject": [a], "measure": m, F: d},
                    {**wd, "factor": fp(d), "around": ", ".join(fp(x) for x in around)}, near=near)
        # absent: a corpus measure no paper gives for this subject
        for m in sorted(set(w.measures) - {f["measure"] for f in fa}):
            if not any(f["measure"] == m for f in w.cfacts):
                continue
            have = ", ".join(sorted({w.measures[f["measure"]]["core"] for f in fa}))
            _nr(w, out, "absent", "absent_measure", split, {"subject": [a], "measure": m},
                _words(w, m, subject=L[a], have=have))
    # out of scope: a subject no paper names (asked about a corpus measure), or a topic no paper names (a test subject)
    test_subjects = sorted({f["subject"] for f in w.card_facts("test")})
    measures = sorted({f["measure"] for f in w.card_facts("test")})
    for i, x in enumerate(cfg.get("out_of_scope_subjects", [])):
        if not measures or not w.absent_everywhere(x):
            continue
        m = measures[i % len(measures)]
        _nr(w, out, "out_of_scope", "out_of_scope_subject", "test", {"subject": [x], "measure": m},
            _words(w, m, subject=x), terms=[x])
    for i, (topic, terms) in enumerate(cfg.get("out_of_scope_topics", [])):
        if not test_subjects or not all(w.absent_everywhere(t) for t in terms):
            continue
        a = test_subjects[i % len(test_subjects)]
        _nr(w, out, "out_of_scope", "out_of_scope_topic", "test", {"subject": [a], "measure": qs.LABEL + topic},
            {"subject": L[a], "topic": topic}, terms=list(terms))


# ---------------------------------------------------------------- gold per type

def _rows(w: World, spec: qs.Spec, *, use_card: bool = True) -> tuple[str, list[dict[str, Any]]]:
    query = qs.sparql(w.domain, spec, use_card=use_card)
    return query, qs.run_query(w.g, query)


def _check_split(w: World, spec: qs.Spec, rows: list[dict[str, Any]]) -> None:
    bad = [r["id"] for r in rows if w.papers[r["paper"]]["split"] != spec.split]
    if bad:
        raise qs.Rejected(f"rows {bad} are not in the {spec.split} split")


def _cols(w: World, spec: qs.Spec) -> list[tuple[str, str]]:
    return [(p, qs.INTENT[w.domain][p].column) for p in qs.open_columns(w.domain, spec)]


def _columns(w: World, points: list[str]) -> list[dict[str, str]]:
    return [{"key": p, "label": qs.INTENT[w.domain][p].label} for p in points]


def _gold_frame(w: World, spec: qs.Spec, query: str, rows: list[dict[str, Any]], answer: dict[str, Any],
                *, answerable: bool = True, use_card: bool = True) -> dict[str, Any]:
    loose = qs.run_query(w.g, qs.sparql(w.domain, spec, use_card=False))
    slots = {k: v for k, v in qs.resolve(w.domain, spec, use_card=use_card).items() if v is not None}
    return {"qid": spec.qid, "domain": w.domain, "type": spec.type, "split": spec.split, "answerable": answerable,
            "status": "answered" if answerable else "not_reported", "sparql": query,
            "slots": json.loads(json.dumps(slots, default=_num)), "open_columns": qs.open_columns(w.domain, spec),
            "row_ids": [r["id"] for r in rows], "answer": answer, "rows_without_card": len(loose),
            "notes": spec.notes, "spec": spec_json(spec)}


def _verdict(value: Decimal, hib: bool, step: Decimal, a: str, b: str) -> str:
    if abs(value) <= step:
        return "no clear difference"
    return f"{a} better" if (value > 0) == hib else f"{b} better"


def gold_effect(w: World, spec: qs.Spec) -> dict[str, Any]:
    query, rows = _rows(w, spec)
    if not rows:
        raise qs.Rejected("the query finds no row")
    _check_split(w, spec, rows)
    m = w.measures[spec.fixed["measure"]]
    keys = _cols(w, spec)
    seen = set()
    for r in rows:
        k = (r["paper"], *(qs.cell(r, s, w.gen) for _, s in keys))
        if k in seen:
            raise qs.Rejected(f"two rows of one study share {k}")
        seen.add(k)
    a, b = w.labels[spec.fixed["subject"][0]], w.labels.get(spec.fixed["comparator"], spec.fixed["comparator"])
    ordered = sorted(rows, key=lambda r: (r["paper"], *qs._sort_key(r, [s for _, s in keys], w.gen)))
    table = [{**qs._table_row(r, keys, w.gen), "verdict": _verdict(r["value"], m["hib"], m["step"], a, b)} for r in ordered]
    studies: dict[str, list[dict[str, Any]]] = {}
    for t in table:
        studies.setdefault(t["paper"], []).append(t)
    answer = {"columns": _columns(w, [p for p, _ in keys]), "table": table, "comparator": b,
              "rounding_step": str(m["step"]), "higher_is_better": m["hib"],
              "per_study": [{"paper": p, "title": w.papers[p]["title"], "rows": [t["row"] for t in ts],
                             "verdicts": sorted({t["verdict"] for t in ts})} for p, ts in studies.items()],
              "text": "; ".join(f"{t['paper']}, {', '.join(t['cells'].values()) or 'all'}: {t['value']} {t['unit']} "
                                f"({t['verdict']})" for t in table)}
    return _gold_frame(w, spec, query, ordered, answer)


def _direction(values: list[Decimal], step: Decimal) -> str:
    moves = {("down" if y - x < -step else "up" if y - x > step else "flat") for x, y in zip(values, values[1:],
                                                                                            strict=False)}
    if moves == {"flat"}:
        return "flat"
    moves.discard("flat")
    return {"down": "goes down", "up": "goes up"}[moves.pop()] if len(moves) == 1 else "mixed"


def gold_trend(w: World, spec: qs.Spec) -> dict[str, Any]:
    query, rows = _rows(w, spec)
    if not rows:
        raise qs.Rejected("the query finds no row")
    _check_split(w, spec, rows)
    m = w.measures[spec.fixed["measure"]]
    keys = _cols(w, spec)
    axis = spec.extra["axis"]
    axis_slot = qs.INTENT[w.domain][axis].column
    seen = set()
    for r in rows:
        k = tuple(qs.cell(r, s, w.gen) for _, s in keys)
        if k in seen:
            raise qs.Rejected(f"two rows share the open-point values {k}")
        seen.add(k)
    by = [(p, s) for p, s in keys if p != axis]
    series: dict[tuple, list[dict[str, Any]]] = {}
    for r in sorted(rows, key=lambda r: qs._sort_key(r, [*(s for _, s in by), axis_slot], w.gen)):
        series.setdefault(tuple(qs.cell(r, s, w.gen) for _, s in by), []).append(r)
    out_series = [{"cells": dict(zip([p for p, _ in by], k, strict=True)),
                   "points": [{"at": qs.cell(r, axis_slot, w.gen), "value": str(r["value"]), "unit": r["unit"],
                               "row": r["id"]} for r in rs],
                   "direction": _direction([r["value"] for r in rs], m["step"]) if len(rs) >= 2 else "one point"}
                  for k, rs in series.items()]
    if not any(len(s["points"]) >= 2 for s in out_series):
        raise qs.Rejected("no group has two points to show a trend")
    ordered = sorted(rows, key=lambda r: qs._sort_key(r, [s for _, s in keys], w.gen))
    answer = {"columns": _columns(w, [p for p, _ in keys]), "table": [qs._table_row(r, keys, w.gen) for r in ordered],
              "axis": {"key": axis, "label": qs.INTENT[w.domain][axis].label},
              "series": out_series, "rounding_step": str(m["step"]),
              "text": "; ".join(f"{', '.join(s['cells'].values()) or 'all'}: "
                                + ", ".join(f"{p['at']} {p['value']}" for p in s["points"])
                                + f" ({s['direction']})" for s in out_series)}
    return _gold_frame(w, spec, query, ordered, answer)


def gold_list(w: World, spec: qs.Spec) -> dict[str, Any]:
    query, rows = _rows(w, spec, use_card=False)
    if not rows:
        raise qs.Rejected("the query finds no row")
    _check_split(w, spec, rows)
    papers: dict[str, list[str]] = {}
    for r in sorted(rows, key=lambda r: (r["paper"], r["id"])):
        papers.setdefault(r["paper"], []).append(r["id"])
    answer = {"columns": [{"key": "paper", "label": "study"}],
              "table": [{"row": ids[0], "paper": p, "cells": {"paper": w.papers[p]["title"]}, "value": "", "unit": ""}
                        for p, ids in papers.items()],
              "papers": [{"paper": p, "title": w.papers[p]["title"], "rows": ids} for p, ids in papers.items()],
              "text": f"{len(papers)} stud{'y' if len(papers) == 1 else 'ies'}: "
                      + "; ".join(f"{p} ({w.papers[p]['title']})" for p in papers)}
    return _gold_frame(w, spec, query, sorted(rows, key=lambda r: (r["paper"], r["id"])), answer, use_card=False)


def gold_conflict(w: World, spec: qs.Spec) -> dict[str, Any]:
    query, rows = _rows(w, spec)
    _check_split(w, spec, rows)
    m = w.measures[spec.fixed["measure"]]
    keys = _cols(w, spec)
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for r in sorted(rows, key=lambda r: (*qs._sort_key(r, [s for _, s in keys], w.gen), r["paper"])):
        groups.setdefault(tuple(qs.cell(r, s, w.gen) for _, s in keys), []).append(r)
    out = []
    for k, rs in groups.items():
        spread = max(r["value"] for r in rs) - min(r["value"] for r in rs)
        status = ("single" if len({r["paper"] for r in rs}) < 2 else "conflict" if spread > m["step"] else "agree")
        out.append({"cells": dict(zip([p for p, _ in keys], k, strict=True)), "status": status, "spread": str(spread),
                    "rows": [{"row": r["id"], "paper": r["paper"], "value": str(r["value"]), "unit": r["unit"]}
                             for r in rs]})
    if not any(g["status"] == "conflict" for g in out):
        raise qs.Rejected("no group where two papers disagree by more than the rounding step")
    ordered = [r for rs in groups.values() for r in rs]
    answer = {"columns": _columns(w, [p for p, _ in keys]), "table": [qs._table_row(r, keys, w.gen) for r in ordered],
              "conflict": True, "groups": out, "rounding_step": str(m["step"]),
              "text": "; ".join(f"{', '.join(g['cells'].values()) or 'all'}: {g['status']} ("
                                + " vs ".join(f"{x['paper']} {x['value']} {x['unit']}" for x in g["rows"]) + ")"
                                for g in out)}
    return _gold_frame(w, spec, query, ordered, answer)


def gold_not_reported(w: World, spec: qs.Spec) -> dict[str, Any]:
    query, rows = _rows(w, spec)
    if rows:
        raise qs.Rejected(f"the query finds {len(rows)} row(s); the fact is reported")
    check: dict[str, Any] = {}
    if spec.type == "out_of_scope":
        hits = {t: [p for p, txt in w.texts.items() if mentions(txt, t)] + (["seed.ttl"] if mentions(w.seed_text, t)
                                                                            else [])
                for t in spec.extra["terms"]}
        if any(hits.values()):
            raise qs.Rejected(f"out-of-scope terms found: {hits}")
        check = {"terms": spec.extra["terms"], "papers_checked": len(w.texts), "seed_checked": True, "hits": 0}
    else:
        subj = spec.fixed["subject"][0]
        if not any(f["subject"] == subj and f["split"] == spec.split for f in w.facts):
            raise qs.Rejected(f"{subj} is not in the corpus, so this is not an absent/near-miss question")
    near = [f for f in w.facts if f["id"] in set(spec.extra.get("near", []))]
    if spec.type == "near_miss" and not near:
        raise qs.Rejected("a near miss needs at least one closest real fact")
    keys = _cols(w, spec)
    answer = {"status": "not_reported", "why": spec.extra["why"], "columns": _columns(w, [p for p, _ in keys]),
              "table": [], "text": f"not reported: {spec.extra['why']}"}
    out = _gold_frame(w, spec, query, [], answer, answerable=False)
    if spec.type == "near_miss":
        out["near_rows"] = [f["id"] for f in near]
    if check:
        out["absence_check"] = check
    return out


def gold(w: World, spec: qs.Spec) -> dict[str, Any]:
    """The gold of one question (raises qs.Rejected when the seed gives no clear answer of its type)."""
    if spec.type in ("lookup", "best"):
        out = qs.gold(w.domain, spec, w.g)
        if spec.extra:   # a new question: same gold as the kept ones, plus the bench fields
            out = {**out, "answerable": True, "status": "answered", "spec": spec_json(spec)}
        return out
    return {"effect": gold_effect, "trend": gold_trend, "list": gold_list, "conflict": gold_conflict}.get(
        spec.type, gold_not_reported)(w, spec)


# ---------------------------------------------------------------- spec <-> json (gold keeps its spec)

def spec_json(spec: qs.Spec) -> dict[str, Any]:
    return json.loads(json.dumps({"type": spec.type, "split": spec.split, "template": spec.text,
                                  "fixed": {k: _plain(v) for k, v in spec.fixed.items()}, "open": list(spec.open), "candidate": spec.candidate,
                                  "extra": spec.extra}, default=_num))


def spec_from(qid: str, d: dict[str, Any]) -> qs.Spec:
    return qs.Spec(qid, d["type"], d["split"], d["template"], d["fixed"], tuple(d["open"]), candidate=d["candidate"],
                   extra=d["extra"])


def regold(w: World, g: dict[str, Any]) -> dict[str, Any]:
    """Recompute a frozen gold from its stored spec (no LLM): equal to the file minus `wording` when nothing moved."""
    spec = next((s for s in qs.SPECS[w.domain] if s.qid == g["qid"]), None)
    if spec is None:
        spec = spec_from(g["qid"], g["spec"])
    return gold(w, spec)


# ---------------------------------------------------------------- choosing

def _signature(spec: qs.Spec) -> str:
    fixed = {k: v for k, v in spec.fixed.items() if v is not None}
    return json.dumps([spec.type, spec.split, fixed, sorted(spec.open), spec.candidate], sort_keys=True, default=_num)


def _family(spec: qs.Spec) -> str:
    return ",".join(sorted(spec.fixed.get("subject") or [])) or str(spec.fixed.get("measure"))


class Pool:
    """The candidates of one type in a seeded order; gold is computed lazily, only as far as needed."""

    def __init__(self, w: World, specs: list[qs.Spec], rng: random.Random, seen: set[str]):
        self.w, self.order, self.i = w, [], 0
        for s in specs:
            sig = _signature(replace(s, extra={}))
            if sig not in seen:   # skip duplicates and the kept questions
                seen.add(sig)
                self.order.append(s)
        rng.shuffle(self.order)
        by_kind: dict[str, list[qs.Spec]] = {}
        for sp in self.order:   # interleave template kinds, so a rare kind (head-to-head) is checked early too
            by_kind.setdefault(sp.extra["kind"], []).append(sp)
        lanes = list(by_kind.values())
        self.order = [lane[i] for i in range(max(map(len, lanes), default=0)) for lane in lanes if i < len(lane)]
        self.ok: list[tuple[qs.Spec, dict[str, Any]]] = []
        self.rejected: Counter = Counter()

    def fill(self, n: int) -> None:
        """Check candidates until n are valid or none are left."""
        while len(self.ok) < n and self.i < len(self.order):
            s = self.order[self.i]
            self.i += 1
            try:
                self.ok.append((s, gold(self.w, s)))
            except qs.Rejected as e:
                self.rejected[re.sub(r"-?\d+(\.\d+)?|R-[\w-]+|\[.*\]|\{.*\}", "#", str(e))[:80]] += 1

    def info(self) -> dict[str, Any]:
        return {"candidates": len(self.order), "checked": self.i, "valid": len(self.ok),
                "rejected": dict(self.rejected)}


def _pick(pool: Pool, n: int, taken: list) -> list[tuple[qs.Spec, dict[str, Any]]]:
    """n more valid questions of the pool, spreading over subjects and template kinds, and keeping each split near its
    share of the papers (pool order breaks ties)."""
    share = pool.w.split_share()
    pool.fill(len(taken) + max(4 * n, 12))
    order = [c for c in pool.ok if c not in taken]
    used_f: Counter = Counter(_family(s) for s, _ in taken)
    used_k: Counter = Counter(s.extra["kind"] for s, _ in taken)
    used_s: Counter = Counter(s.split for s, _ in taken)
    out = []
    while order and len(out) < n:
        size = len(taken) + len(out) + 1

        def cost(j: int) -> tuple:
            s = order[j][0]
            over = max(0.0, used_s[s.split] + 1 - share.get(s.split, 0.0) * size)
            return (used_f[_family(s)] + used_k[s.extra["kind"]] + 4 * over, j)
        i = min(range(len(order)), key=cost)
        s, g = order.pop(i)
        used_f[_family(s)] += 1
        used_k[s.extra["kind"]] += 1
        used_s[s.split] += 1
        out.append((s, g))
    return out


def choose(w: World, seed: int, quota: dict[str, int] | None = None) -> dict[str, Any]:
    """Pick the questions per type. Kept questions count towards their type. A type the seed cannot fill gives its
    places to the other types of its half (in order), and the shortfall is reported."""
    quota = dict(quota or quota_of(w.domain))
    rng = random.Random(seed)
    seen = {_signature(replace(s, extra={})) for s in qs.SPECS[w.domain]}
    cands = candidates(w)
    pools = {t: Pool(w, cands[t], rng, seen) for t in TYPES}
    kept_n = Counter(s.type for s in qs.SPECS[w.domain])
    want = {t: max(0, quota.get(t, 0) - kept_n[t]) for t in TYPES}
    picked: dict[str, list] = {}
    report: dict[str, Any] = {}
    for half, name in ((IN_CORPUS, "in_corpus"), (NOT_REPORTED, "not_reported")):
        spare = 0
        for t in half:
            picked[t] = _pick(pools[t], want[t], [])
            spare += want[t] - len(picked[t])
        for t in half:   # give the spare places to types that still have candidates
            if spare <= 0:
                break
            more = _pick(pools[t], spare, picked[t])
            picked[t] += more
            spare -= len(more)
        for t in half:
            total = kept_n[t] + len(picked[t])
            report[t] = {"quota": quota.get(t, 0), "kept": kept_n[t], "new": len(picked[t]), "total": total,
                         "shortfall": max(0, quota.get(t, 0) - total), **pools[t].info()}
        report["missing_" + name] = spare
    chosen = [c for t in TYPES for c in picked[t]]
    rng.shuffle(chosen)   # ids say nothing about the type
    return {"chosen": chosen, "report": report}


def quota_of(domain: str) -> dict[str, int]:
    """The questions wanted per type: QUOTA when set (tests), else the blueprint's generator.bench.quota."""
    return dict(QUOTA if QUOTA is not None else qs.gen_of(domain).g["bench"]["quota"])


def id_prefix(domain: str) -> str:
    """The <d> of question ids: the middle part of the blueprint's paper ids (P-med-01 -> med)."""
    found = {p["id"].split("-")[1] for p in qs._blueprint(domain)["papers"] if p["id"].count("-") >= 2}
    return found.pop() if len(found) == 1 else domain[:3]


def assign_ids(domain: str, chosen: list[tuple[qs.Spec, dict[str, Any]]]) -> list[tuple[qs.Spec, dict[str, Any]]]:
    """Q-<d>-NN for test (after the kept ones), Q-<d>-pN for practice."""
    prefix = id_prefix(domain)
    nums = {"test": [], "practice": []}
    for s in qs.SPECS[domain]:
        tail = s.qid.rsplit("-", 1)[-1]
        nums["practice" if tail.startswith("p") else "test"].append(int(tail.lstrip("p")))
    nxt = {k: max(v, default=0) + 1 for k, v in nums.items()}
    width = max(2, len(str(nxt["test"] + sum(s.split == "test" for s, _ in chosen) - 1)))
    out = []
    for s, g in chosen:
        n = nxt[s.split]
        nxt[s.split] += 1
        qid = f"Q-{prefix}-{n:0{width}d}" if s.split == "test" else f"Q-{prefix}-p{n}"
        out.append((replace(s, qid=qid), {**g, "qid": qid}))
    return out


# ---------------------------------------------------------------- wording tasks

def task_of(w: World, spec: qs.Spec, g: dict[str, Any]) -> reword.Task:
    """What the wording must keep, the gold values it must not leak, and the subject names it must not add."""
    keep: list[reword.Keep] = []
    f = spec.fixed
    for s in f.get("subject") or []:
        keep.append(reword.Keep("name", w.labels.get(s, s)))
    if f.get("comparator") and spec.type == "effect":
        keep.append(reword.Keep("name", w.labels.get(f["comparator"], f["comparator"])))
    for role, slot in (("factor", w.F), ("time", w.T)):
        if f.get(slot) is not None:
            keep.append(reword.Keep(slot, w.gen.phrase(role, f[slot]), pattern=w.gen.g[role]["mention"]))
    ctx = f.get(w.C)
    if ctx:
        keep.append(reword.Keep("group", ctx[len(qs.LABEL):] if str(ctx).startswith(qs.LABEL) else w.contexts[ctx]))
    m = f.get("measure")
    if m and str(m).startswith(qs.LABEL):
        keep.append(reword.Keep("phrase", m[len(qs.LABEL):]))
    elif m:
        keep.append(reword.Keep("measure", w.measures[m]["core"], tuple(w.measures[m]["alt"])))
    values = [r["value"] for r in g["answer"].get("table", []) if r.get("value")]
    comparator = {w.labels.get(w.gen.default_comparator, "")} if w.gen.default_comparator else set()
    names = sorted({*w.labels.values(), *w.bench_cfg().get("out_of_scope_subjects", [])} - comparator
                   - {k.text for k in keep if k.kind == "name"})
    return reword.Task(spec.qid, spec.text, keep, values=values, other_names=names)


# ---------------------------------------------------------------- files

def record(domain: str, spec: qs.Spec, text: str | None = None, answerable: bool = True) -> dict[str, Any]:
    rec = qs.record(domain, spec) if text is None else {
        "qid": spec.qid, "domain": domain, "split": spec.split, "type": spec.type, "question": text,
        "intent_card": qs.card(domain, spec), "intent_text": qs.card_text(qs.card(domain, spec))}
    return {**rec, "answerable": answerable}


def replay_wording(folder: Path, tasks: list[reword.Task]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """The wording records and reword settings stored in a frozen gold folder, for the same questions (no LLM).
    Raises when a stored wording belongs to another template or the reword prompts changed since."""
    out = {}
    for t in tasks:
        stored = json.loads((folder / f"{t.qid}.json").read_text(encoding="utf-8")).get("wording")
        if stored is None or stored["template"] != t.template:
            raise ValueError(f"{t.qid}: the stored wording is for another question ({(stored or {}).get('template')})")
        out[t.qid] = stored
    info = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["generator"]["reword"]
    if info["prompt_sha256"] != reword.prompt_sha():
        raise ValueError("the reword prompts changed since the frozen set was worded")
    return out, info


def render(domain: str, *, gen: Any = None, ver: Any = None, seed: int | None = None,
           w: World | None = None, replay: Path | None = None) -> tuple[dict[Path, str], dict[str, Any]]:
    """Every file of the 100-question set as path -> text, and the selection report. gen/ver None = no LLM (the
    template text stays; a dry run). `replay` = a gold folder whose stored wordings are reused (no LLM), to prove
    that code rebuilds a frozen set byte for byte."""
    w = w or World(domain)
    seed = seed if seed is not None else int(seed_build.load_blueprint(domain).get("random_seed", 0))
    picked = choose(w, seed)
    chosen = assign_ids(domain, picked["chosen"])
    tasks = [task_of(w, s, g) for s, g in chosen]
    reword_info = {"generator": getattr(gen, "model", None), "verifier": getattr(ver, "model", None),
                   "prompt_sha256": reword.prompt_sha(), "attempts": reword.ATTEMPTS}
    if replay is not None:
        wording, reword_info = replay_wording(replay, tasks)
    else:
        wording = reword.reword_all(gen, ver, tasks) if gen is not None else reword.template_only(tasks)
    files: dict[Path, str] = {}
    by_split: dict[str, list[tuple[str, str]]] = {}
    for spec in qs.SPECS[domain]:
        by_split.setdefault(spec.split, []).append((spec.qid, json.dumps(record(domain, spec), ensure_ascii=False)))
        files[qs.gold_dir(domain) / f"{spec.qid}.json"] = qs._dump(qs.gold(domain, spec, w.g))
    for spec, g in chosen:
        wd = wording[spec.qid]
        rec = record(domain, spec, wd["text"], g["answerable"])
        by_split.setdefault(spec.split, []).append((spec.qid, json.dumps(rec, ensure_ascii=False)))
        files[qs.gold_dir(domain) / f"{spec.qid}.json"] = qs._dump({**g, "wording": wd})
    for split, lines in sorted(by_split.items()):
        lines.sort(key=lambda x: _qid_key(x[0]))
        files[qs.questions_dir(domain) / f"{split}.jsonl"] = "\n".join(t for _, t in lines) + "\n"
    report = {**picked["report"], "seed": seed, "questions": len(qs.SPECS[domain]) + len(chosen),
              "worded_by_llm": sum(wording[s.qid]["source"] == "llm" for s, _ in chosen),
              "kept_template": sum(wording[s.qid]["source"] == "template" for s, _ in chosen)}
    gen_info = {"by": "evqa seed bench", "seed": seed, "quota": quota_of(domain), "report": report,
                "reword": reword_info}
    files[qs.gold_dir(domain) / "manifest.json"] = qs._dump(manifest(domain, files, gen_info))
    return files, report


def _qid_key(qid: str) -> tuple:
    tail = qid.rsplit("-", 1)[-1]
    return (tail.startswith("p"), int(tail.lstrip("p")))


def manifest(domain: str, files: dict[Path, str], generator: dict[str, Any]) -> dict[str, Any]:
    """Same shape as questions.manifest (questions.verify reads it), for every question of the set."""
    shas = {p.relative_to(REPO).as_posix(): qs.sha(t) for p, t in sorted(files.items()) if p.name != "manifest.json"}
    recs = {}
    for p, t in files.items():
        if p.suffix == ".jsonl":
            recs.update({r["qid"]: r for r in (json.loads(x) for x in t.splitlines() if x.strip())})
    per_q = {q: qs.sha(json.dumps({"record": recs[q], "gold": json.loads(files[qs.gold_dir(domain) / f"{q}.json"])},
                                  sort_keys=True, ensure_ascii=False)) for q in sorted(recs, key=_qid_key)}
    return {"domain": domain, "set_sha256": qs.sha(json.dumps(shas, sort_keys=True)), "questions": per_q,
            "files": shas, "generator": generator}


def build(domain: str, *, gen: Any = None, ver: Any = None, force: bool = False, dry_run: bool = False,
          out: Path | None = None, w: World | None = None, replay: Path | None = None) -> dict[str, Any]:
    """Make and (unless dry_run) write the set. A frozen set on disk is replaced only with `force`. With `out`,
    every file goes to out/<repo-relative path> (the frozen folders are never written; no `force` needed)."""
    files, report = render(domain, gen=gen, ver=ver, w=w, replay=replay)
    if dry_run:
        return {"written": False, "report": report}
    old = qs.gold_dir(domain) / "manifest.json"
    if out is None and old.is_file() and not force:
        raise qs.Frozen("a frozen question set exists; rebuild with --force on purpose")
    gold_out = seed_build.relocate(qs.gold_dir(domain), out)
    stale = [p for p in gold_out.glob("*.json") if seed_build.relocate(qs.gold_dir(domain) / p.name, None) not in files]
    for p in stale:
        p.unlink()
    qs.write_files(files, out)
    return {"written": True, "report": report, "removed": [p.name for p in stale],
            "files": len(files)}
