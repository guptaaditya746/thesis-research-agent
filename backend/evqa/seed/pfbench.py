"""Benchmark questions and gold answers for a paperfactory domain, all by code (22 Nov 2026).

Input (written by `paperfactory export-workbench`, services/paper-factory/src/paperfactory/workbench.py):
  data/seed/<d>/facts.jsonl    one shared fact row per planted relation and per reported number, each with its paper:
                               what = relation | attr | effect | pool; subject, relation, object, attr, stat, value, unit
  data/seed/<d>/entities.json  id -> {kind, label, alt, attrs}
  data/seed/<d>/vocab.json     the field's words: number labels per kind, relation words, effect measure
Output:
  data/seed/<d>/gold/<qid>.json         slots, row_ids, answer {columns, table, entities?}, status, spec
  data/dataset/<d>/questions/test.jsonl qid, domain, split, type, question, intent_card, intent_text, answerable

Every paper in facts.jsonl passed the paperfactory checks, so each number row is in its paper as written and each
relation was found by the tagger. Values are the world's (quant.py): one value per (subject, number), so a number in
several papers is ONE gold row (its papers listed in "papers"); systems may cite any of them.

Types (the evqa names; the same scoring code, eval/text_answer.py):
  lookup        one number of one entity                      -> its row
  effect        the effect a study reported for one object    -> estimate and 95% CI rows
  best          the effect (or a number) across the entities that share one object -> one row per candidate
  trend         the same, ordered by year (>= 3 years)        -> one row per candidate
  list          which entities stand in one relation to an object -> the entities (scored by names, not numbers)
  conflict      an object two studies disagree about (conflict-pair relations) -> their effect rows, else names
  absent        a number of an entity in the corpus that no paper reports       -> not reported
  near_miss     an effect of a study for an object it never studied (it studied a sibling); in law, a number of a
                decision asked under a court that did not decide it              -> not reported
  out_of_scope  a number of an entity no paper mentions (a fresh invented name)  -> not reported
Wording: fixed templates (the model may reword later; a verifier must check the reworded question).
"""
from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from evqa.paths import DATASET, domain_dir

MIX = {"lookup": 4, "effect": 4, "best": 4, "trend": 3, "list": 4, "conflict": 3,
       "absent": 6, "near_miss": 6, "out_of_scope": 6}           # 40: 22 in corpus, 18 not reported
NOT_REPORTED = ("absent", "near_miss", "out_of_scope")
OTHER_NAMES = {"point": "other_names", "label": "other names", "ask": "Do you know other names for these?",
               "answer": "I know no other names. Use the names in the question."}
EVERY_PAPER = {"point": "papers", "label": "papers", "ask": "Which papers should I use?",
               "answer": "Use every paper that reports it."}
STAT_WORDS = {"estimate": "estimate", "ci_low": "95% CI lower bound", "ci_high": "95% CI upper bound",
              "baseline": "baseline", "with": "with the method"}


class Domain:
    def __init__(self, domain: str) -> None:
        d = domain_dir(domain)
        self.name = domain
        self.rows = [json.loads(x) for x in (d / "facts.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        self.ents: dict[str, Any] = json.loads((d / "entities.json").read_text(encoding="utf-8"))
        self.vocab: dict[str, Any] = json.loads((d / "vocab.json").read_text(encoding="utf-8"))
        self.mentioned = {x for r in self.rows for x in (r.get("subject"), r.get("object")) if x}
        self.attr: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self.effect: dict[tuple[str, str, str], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        self.rel: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for r in self.rows:
            if r["what"] == "attr":
                self.attr[(r["subject"], r["attr"])].append(r)
            elif r["what"] == "effect":
                self.effect[(r["subject"], r["relation"], r["object"])][r["stat"]].append(r)
            elif r["what"] == "relation":
                self.rel[(r["subject"], r["relation"], r["object"])].append(r)

    # ---- words
    def label(self, eid: str) -> str:
        return self.ents[eid]["label"]

    def kind(self, eid: str) -> str:
        return self.ents[eid]["kind"]

    def num_label(self, kind: str, attr: str) -> str:
        return self.vocab["kinds"][kind]["numbers"][attr]["label"]

    def numbers_of(self, kind: str) -> list[str]:
        return list(self.vocab["kinds"].get(kind, {}).get("numbers", {}))

    def word(self, key: str, default: str = "") -> str:
        return self.vocab["words"].get(key, default)

    @property
    def eff(self) -> dict[str, Any] | None:
        return self.vocab.get("effect")

    @property
    def eff_name(self) -> str:
        """What the estimate row holds: on a difference scale the change (llm: the gain in accuracy, not accuracy)."""
        e = self.eff or {}
        name = e.get("name", "effect")
        if e.get("scale") == "difference" and not name.startswith("change"):
            return f"change in {name} ({e.get('delta_unit', e.get('unit', ''))})"
        return name


# ---------------------------------------------------------------- gold rows
def _row(rows: list[dict[str, Any]], cells: dict[str, str]) -> dict[str, Any]:
    """One gold row from the fact rows that carry the same value (one per paper)."""
    first = sorted(rows, key=lambda r: r["paper"])[0]
    return {"row": first["id"], "paper": first["paper"], "papers": sorted({r["paper"] for r in rows}), "cells": cells,
            "value": first["value"], "unit": first.get("unit", "")}


def _gold(qid: str, d: Domain, typ: str, question: str, slots: dict[str, Any], table: list[dict[str, Any]],
          columns: list[dict[str, str]], entities: list[dict[str, Any]] | None = None, notes: str = "",
          spec: dict[str, Any] | None = None) -> dict[str, Any]:
    nr = typ in NOT_REPORTED
    answer: dict[str, Any] = {"columns": columns, "table": table}
    if entities is not None:
        answer["entities"] = entities
    if nr:
        answer = {"status": "not_reported", "why": notes, "columns": columns, "table": []}
    return {"qid": qid, "domain": d.name, "type": typ, "split": "test", "answerable": not nr,
            "status": "not_reported" if nr else "answered", "slots": slots, "open_columns": [],
            "row_ids": [] if nr else [t["row"] for t in table], "answer": answer, "rows_without_card": 0,
            "notes": notes, "spec": spec or {}, "wording": {"template": question, "source": "template", "text": question},
            "source": "pfbench"}


def _ent(d: Domain, eid: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"id": eid, "label": d.label(eid), "alt": d.ents[eid].get("alt", []),
            "papers": sorted({r["paper"] for r in rows}), "row": sorted(rows, key=lambda r: r["paper"])[0]["id"]}


# ---------------------------------------------------------------- candidates per type
def lookups(d: Domain) -> list[dict[str, Any]]:
    out = []
    for (s, a), rows in sorted(d.attr.items()):
        lab = d.num_label(d.kind(s), a)
        q = f"For {d.label(s)}, what number is reported for {lab}?"
        out.append({"q": q, "slots": {"subject": [d.label(s)], "attr": a},
                    "table": [_row(rows, {})], "columns": [], "key": ("lookup", s, a)})
    return out


def effects(d: Domain) -> list[dict[str, Any]]:
    if not d.eff:
        return []
    out = []
    for (s, r, o), stats in sorted(d.effect.items()):
        if "estimate" not in stats:
            continue
        table = [_row(stats[k], {"statistic": STAT_WORDS[k]}) for k in ("estimate", "ci_low", "ci_high") if k in stats]
        q = f"What {d.eff_name} did {d.label(s)} report for {d.label(o)}, with its 95% confidence interval?"
        out.append({"q": q, "slots": {"subject": [d.label(s), d.label(o)], "relation": r}, "table": table,
                    "columns": [{"key": "statistic", "label": "statistic"}], "key": ("effect", s, o)})
    return out


def _groups(d: Domain) -> list[tuple[str, list[tuple[str, list[dict[str, Any]]]], str]]:
    """(object, [(subject, value rows)], what): the subjects with a number about one shared object. With an effect
    measure: each subject's effect estimate for the object. Without (law): one number of the subjects that stand in
    a relation to the object (e.g. the damages of the decisions relying on one provision)."""
    out = []
    if d.eff:
        by_o: dict[str, list[tuple[str, list[dict[str, Any]]]]] = defaultdict(list)
        for (s, _, o), stats in sorted(d.effect.items()):
            if "estimate" in stats:
                by_o[o].append((s, stats["estimate"]))
        out += [(o, xs, "effect") for o, xs in sorted(by_o.items()) if len({s for s, _ in xs}) >= 2]
    else:
        subj_of: dict[str, set[str]] = defaultdict(set)
        for (s, _, o) in d.rel:
            subj_of[o].add(s)
        for o, ss in sorted(subj_of.items()):
            for a in sorted({a for (s, a) in d.attr if s in ss}):
                xs = [(s, d.attr[(s, a)]) for s in sorted(ss) if (s, a) in d.attr]
                if len(xs) >= 2:
                    out.append((o, xs, a))
    return out


def _cand_q(d: Domain, o: str, what: str, s0: str, mode: str) -> str:
    plural = d.word("subject_plural", "studies")
    if what == "effect":
        side = d.eff.get("better_side", "higher")   # type: ignore[union-attr]
        best = "lowest" if side == "lower" else "highest"
        if mode == "best":
            return (f"Among the {plural} that report a {d.eff_name} for {d.label(o)}, "
                    f"which reports the {best} value?")
        return (f"How has the {d.eff_name} reported for {d.label(o)} changed "
                f"across {plural} over the years?")
    lab = d.num_label(d.kind(s0), what)
    if mode == "best":
        return f"Among the {plural} that concern {d.label(o)}, which has the highest number for {lab}?"
    return f"How has the {lab} of the {plural} that concern {d.label(o)} changed over the years?"


def bests(d: Domain) -> list[dict[str, Any]]:
    out = []
    for o, xs, what in _groups(d):
        table = [_row(rows, {"candidate": d.label(s)}) for s, rows in xs]
        out.append({"q": _cand_q(d, o, what, xs[0][0], "best"),
                    "slots": {"subject": [d.label(o)], "candidates": [d.label(s) for s, _ in xs], "measure": what},
                    "table": table, "columns": [{"key": "candidate", "label": d.word("subject_kind", "study")}],
                    "key": ("best", o, what)})
    return out


def trends(d: Domain) -> list[dict[str, Any]]:
    out = []
    for o, xs, what in _groups(d):
        years = {s: d.ents[s].get("attrs", {}).get("year") for s, _ in xs}
        if any(not isinstance(y, int) for y in years.values()) or len(set(years.values())) < 3:
            continue
        xs = sorted(xs, key=lambda x: (years[x[0]], x[0]))
        table = [_row(rows, {"candidate": d.label(s), "year": str(years[s])}) for s, rows in xs]
        out.append({"q": _cand_q(d, o, what, xs[0][0], "trend"),
                    "slots": {"subject": [d.label(o)], "candidates": [d.label(s) for s, _ in xs], "measure": what},
                    "table": table, "columns": [{"key": "candidate", "label": d.word("subject_kind", "study")},
                                                {"key": "year", "label": "year"}], "key": ("trend", o, what)})
    return out


def lists(d: Domain) -> list[dict[str, Any]]:
    by: dict[tuple[str, str], list[str]] = defaultdict(list)
    for (s, r, o) in sorted(d.rel):
        by[(r, o)].append(s)
    out = []
    for (r, o), ss in sorted(by.items()):
        if len(ss) < 2:
            continue
        words = d.vocab["relations"][r]["words"]
        plural = d.word("subject_plural", "studies")
        ents = [_ent(d, s, d.rel[(s, r, o)]) for s in ss]
        out.append({"q": f"Which {plural} {words} {d.label(o)}?", "slots": {"subject": [d.label(o)], "relation": r},
                    "table": [], "entities": ents, "columns": [{"key": "entity", "label": d.word("subject_kind")}],
                    "key": ("list", r, o)})
    return out


def conflicts(d: Domain) -> list[dict[str, Any]]:
    pairs = {tuple(p) for p in d.vocab.get("conflict_pairs", [])}
    pairs |= {(b, a) for a, b in pairs}
    by_o: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for (s, r, o) in sorted(d.rel):
        by_o[o][r].append(s)
    out = []
    for o, rels in sorted(by_o.items()):
        hit = [(a, b) for a in rels for b in rels if a < b and (a, b) in pairs]
        if not hit:
            continue
        ss = sorted({s for a, b in hit for s in rels[a] + rels[b]})
        plural = d.word("subject_plural", "studies")
        q = f"Do the {plural} agree about {d.label(o)}? What does each one report?"
        if d.eff and all(any((s, r, o) in d.effect and "estimate" in d.effect[(s, r, o)] for r in rels) for s in ss):
            table = []
            for s in ss:
                r = next(r for r in rels if (s, r, o) in d.effect and "estimate" in d.effect[(s, r, o)])
                table.append(_row(d.effect[(s, r, o)]["estimate"], {"candidate": d.label(s)}))
            out.append({"q": q, "slots": {"subject": [d.label(o)], "candidates": [d.label(s) for s in ss]},
                        "table": table, "columns": [{"key": "candidate", "label": d.word("subject_kind")}],
                        "key": ("conflict", o)})
        else:
            ents = [_ent(d, s, [x for r in rels for x in d.rel.get((s, r, o), [])]) for s in ss]
            out.append({"q": q, "slots": {"subject": [d.label(o)], "candidates": [d.label(s) for s in ss]},
                        "table": [], "entities": ents, "columns": [{"key": "entity", "label": d.word("subject_kind")}],
                        "key": ("conflict", o)})
    return out


def absents(d: Domain) -> list[dict[str, Any]]:
    out = []
    for s in sorted(d.mentioned):
        reported = {a for (x, a) in d.attr if x == s}
        for a in d.numbers_of(d.kind(s)):
            if a in reported or not reported:      # only entities the corpus gives numbers for: a fair trap
                continue
            lab = d.num_label(d.kind(s), a)
            others = ", ".join(sorted(d.num_label(d.kind(s), x) for x in reported))
            out.append({"q": f"For {d.label(s)}, what number is reported for {lab}?", "slots": {"subject": [d.label(s)], "attr": a},
                        "why": f"no paper reports the {lab} of {d.label(s)} (its papers report: {others})",
                        "key": ("absent", s, a)})
    return out


def near_misses(d: Domain) -> list[dict[str, Any]]:
    out = []
    if d.eff:
        for (s, r, o) in sorted(d.effect):
            for o2 in sorted(e for e in d.mentioned if e != o and d.kind(e) == d.kind(o)):
                if any(k[0] == s and k[2] == o2 for k in list(d.effect) + list(d.rel)):
                    continue
                q = f"What {d.eff_name} did {d.label(s)} report for {d.label(o2)}?"
                out.append({"q": q, "slots": {"subject": [d.label(s), d.label(o2)]},
                            "why": f"{d.label(s)} reports on {d.label(o)}, not on {d.label(o2)}",
                            "key": ("near_miss", s, o2)})
    else:   # law: a decision's number asked under a court that did not decide it
        courts = sorted(e for e in d.ents if d.kind(e) == "court")
        for (s, a) in sorted(d.attr):
            own = d.ents[s].get("attrs", {}).get("court")
            for c in courts:
                if c == own or own is None:
                    continue
                lab = d.num_label(d.kind(s), a)
                q = f"In {d.label(s)} before the {d.label(c)}, what number is reported for {lab}?"
                out.append({"q": q, "slots": {"subject": [d.label(s), d.label(c)], "attr": a},
                            "why": f"{d.label(s)} was decided by the {d.label(own)}, not the {d.label(c)}",
                            "key": ("near_miss", s, a, c)})
    return out


def _fresh_label(d: Domain, eid: str, rng: random.Random) -> str:
    """The entity's label with each invented word swapped for a fresh one no entity uses (and not part of one)."""
    per_ent = [{w.lower() for n in [e["label"], *e.get("alt", [])] for w in re.findall(r"[A-Za-z]+", n)}
               for e in d.ents.values()]
    used = set().union(*per_ent)
    # a word in two or more entities' names is a common word (the, trial, Bank, the country); one entity's own is
    # invented
    common = {w for w in used if sum(w in x for x in per_ent) >= 2} | set(re.findall(r"[a-z]+", json.dumps(d.vocab).lower()))

    def fresh(like: str) -> str:
        while True:
            w = "".join(rng.choice("bdfgklmnprstvz") + rng.choice("aeiou") for _ in range(rng.choice((2, 3))))
            if len(w) >= 5 and not any(w in u or u in w for u in used if len(u) >= 4):
                used.add(w)
                return w.upper() if like.isupper() else w.capitalize() if like[:1].isupper() else w
    return re.sub(r"[A-Za-z]+", lambda m: m.group(0) if m.group(0).lower() in common else fresh(m.group(0)),
                  d.label(eid))


def out_of_scopes(d: Domain, rng: random.Random) -> list[dict[str, Any]]:
    out = []
    for (s, a) in sorted(d.attr):
        new = _fresh_label(d, s, rng)
        lab = d.num_label(d.kind(s), a)
        out.append({"q": f"For {new}, what number is reported for {lab}?", "slots": {"subject": [new], "attr": a},
                    "why": f"no paper mentions {new}", "key": ("out_of_scope", s, a)})
    return out


# ---------------------------------------------------------------- build
def _pick(cands: list[dict[str, Any]], n: int, rng: random.Random) -> list[dict[str, Any]]:
    """n candidates spread over subjects: shuffled, then at most one per subject before any repeat."""
    rng.shuffle(cands)
    seen: set[Any] = set()
    first = [c for c in cands if not (c["key"][1] in seen or seen.add(c["key"][1]))]
    rest = [c for c in cands if c not in first]
    return (first + rest)[:n]


def build(domain: str, seed: int = 20261122, mix: dict[str, int] | None = None) -> dict[str, Any]:
    """Questions + gold for the domain. Types with too few candidates give their share to lookup (reported)."""
    d, rng = Domain(domain), random.Random(f"{seed}:{domain}")
    mix = dict(mix or MIX)
    makers = {"lookup": lambda: lookups(d), "effect": lambda: effects(d), "best": lambda: bests(d),
              "trend": lambda: trends(d), "list": lambda: lists(d), "conflict": lambda: conflicts(d),
              "absent": lambda: absents(d), "near_miss": lambda: near_misses(d),
              "out_of_scope": lambda: out_of_scopes(d, rng)}
    cands = {t: makers[t]() for t in mix}
    short = {t: mix[t] - len(cands[t]) for t in mix if len(cands[t]) < mix[t]}
    for t, n in short.items():
        mix[t] -= n
        mix["lookup"] += n
    picked: list[tuple[str, dict[str, Any]]] = []
    for t, n in mix.items():
        picked += [(t, c) for c in _pick(cands[t], n, rng)]
    golds, qs = [], []
    prefix = re.sub(r"[^a-z0-9]", "", domain.lower())[:6]
    for i, (t, c) in enumerate(picked, 1):
        qid = f"Q-{prefix}-{i:02d}"
        g = _gold(qid, d, t, c["q"], c["slots"], c.get("table", []), c.get("columns", []), c.get("entities"),
                  c.get("why", ""), {"type": t, "key": [str(x) for x in c["key"]]})
        golds.append(g)
        card = [OTHER_NAMES] + ([EVERY_PAPER] if t not in NOT_REPORTED else [])
        qs.append({"qid": qid, "domain": domain, "split": "test", "type": t, "question": c["q"], "intent_card": card,
                   "intent_text": "\n".join(f"{x['label']}: {x['answer']}" for x in card), "answerable": t not in NOT_REPORTED})
    return {"golds": golds, "questions": qs, "mix": mix, "short": short,
            "candidates": {t: len(v) for t, v in cands.items()}}


def write(domain: str, got: dict[str, Any]) -> dict[str, Any]:
    if not (domain_dir(domain) / "facts.jsonl").is_file():
        raise ValueError(f"{domain} is not a paperfactory export (no facts.jsonl); its gold is not pfbench's to replace")
    gdir = domain_dir(domain) / "gold"
    gdir.mkdir(parents=True, exist_ok=True)
    for old in gdir.glob("Q-*.json"):
        old.unlink()
    for g in got["golds"]:
        (gdir / f"{g['qid']}.json").write_text(json.dumps(g, indent=1, ensure_ascii=False), encoding="utf-8")
    qdir = Path(DATASET) / domain / "questions"
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / "test.jsonl").write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in got["questions"]),
                                     encoding="utf-8")
    return {"domain": domain, "questions": len(got["questions"]), "mix": got["mix"], "short": got["short"],
            "candidates": got["candidates"]}
