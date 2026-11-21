"""Prism: score one evqa run folder against the seed, layer by layer. Code only, no LLM, deterministic.

    score_run(run_dir, domain="medical") -> dict      (also written to run_dir/eval.json)

Per question, for each gold fact (the seed rows behind the gold answer, gold `row_ids`):
  L0  kept     the fact has an L0 span in its paper.md (data/seed/<domain>/l0/<paper>.json)
  L1  find     the fact's paper is in find.jsonl and one of its passages [start, end) overlaps an L0 span of the fact
  L2  extract  a non-dropped row of the same paper whose quote [quote_start, quote_end) overlaps an L0 span of the
               fact and whose std value equals the seed value (norm.same: half a unit of the last printed decimal).
               name_ok (subject, measure, time, dose, patient group in canonical form) and quote_ok are kept apart.
               precision = non-dropped rows matching some gold fact / non-dropped rows.
  L3  answer   lookup: answer rows vs gold rows on (canonical cells, value): recall, precision, exact.
               best:   per gold group, the answer group with the same cells must have the same status and winner.
               effect: per gold row, an effect entry with the same cells whose difference A - B equals the gold value
                       (norm.same) and whose verdict names the same side (A, B, or no clear difference); F1.
               trend:  per gold series, the answer series with the same cells: same ordered points (axis value and
                       value) and the same direction (gold "goes down"/"goes up" = decreasing/increasing).
               list:   F1 of the answer's paper set against the gold paper set.
               conflict: per gold conflict group, an Answer.conflicts entry holding every paper's value (flagged).
               not reported (absent, near_miss, out_of_scope): right iff the answer says not reported or has no
                       value. hallucination = the answer shows a value anyway; near-miss trap = a value the answer
                       uses comes from one of the closest real facts the gold lists. These questions have no gold
                       facts: L0..L2 and blame are n/a (None) and stay out of the means.
  blame        the first layer that lost the fact: L0 -> find -> extract -> answer ("none" = in the answer).
               extract also takes the blame when the value was read but no matched row is usable (quote not
               checked, or a wrong name), so Answer could not use it.
  advisor      spec.json vs the gold intent: type, subjects, measure, fixed slots, "all" columns, best_by,
               direction. score = checks passed / checks; the failed checks are listed.
Patient groups (a value's settings) are compared by provenance, never by wording (plan v2 step 5): the gold setting of
an answer item is the seed context of the facts its rows come from (row paper + quote offsets overlapping the fact's
L0 span + same value); the item's label is not read. An item whose rows come from facts of several contexts, or from
no seed fact, matches no gold context. The label the user sees is checked separately by a blind LLM judge
(eval/judge.py, reported apart in eval.json). Measures: the seed name (or an alternative name) and the spec's name
(or a synonym) must contain one another as whole normalised phrases.
Totals: answerable L3 (mean over in-corpus types), per type, and the not-reported block (accuracy, hallucination
rate, near-miss trap rate).
Intervals: eval.json "intervals" holds a 95% bootstrap interval (resampling questions, eval/bootstrap.py) for each
headline total; every headline total is a mean over questions. The other keys of eval.json are unchanged.
Data: eval.json "data" holds the hashes of the papers, questions and gold files the score was made on (datahash.py).
Eval may read data/seed; the pipeline steps may not (seed wall test).
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from evqa import datahash, norm
from evqa.answer import canon
from evqa.contracts import Answer, FindHit, Row, RunConfig, Spec, read_jsonl
from evqa.eval import bootstrap
from evqa.paths import domain_dir
from evqa.seed import brief
from evqa.seed import questions as seed_questions

LAYERS = ("L0", "find", "extract", "answer")
GOLD_SLOT = {"dose": "dose", "week": "time_point", "context": "patient_group"}   # gold slot -> spec slot
PROVENANCE_SLOTS = ("patient_group",)                                 # gold slots compared by provenance
STATUS = {"not reported": "not_reported", "not_reported": "not_reported", "winner": "winner", "tie": "tie"}
NOT_REPORTED_TYPES = ("absent", "near_miss", "out_of_scope")          # gold answer: not reported
ANSWERABLE_TYPES = ("lookup", "effect", "best", "trend", "list", "conflict")
TYPES = (*ANSWERABLE_TYPES, *NOT_REPORTED_TYPES)
# the Spec type each dataset type is asked as (bench.py words conflict and the not-reported kinds as lookups)
SPEC_TYPE = {"conflict": "lookup", "absent": "lookup", "near_miss": "lookup", "out_of_scope": "lookup"}
DIRECTION = {"goes down": "decreasing", "goes up": "increasing", "flat": "flat", "mixed": "mixed",
             "one point": "one point"}                                 # gold trend wording -> TrendSeries.direction


# ---------------------------------------------------------------- seed side (truth)
@lru_cache(maxsize=4)
def seed_facts(domain: str) -> dict[str, dict[str, Any]]:
    """Seed fact id -> fact (paper, subject, measure, measure_alt, context, dose, week, value, unit, ...)."""
    return {f["id"]: f for p in brief.paper_facts(domain).values() for f in p["facts"]}


@lru_cache(maxsize=4)
def contexts(domain: str) -> tuple[str, ...]:
    return tuple(sorted({f["context"] for f in seed_facts(domain).values()}))


@lru_cache(maxsize=4)
def gold(domain: str) -> dict[str, dict[str, Any]]:
    folder = domain_dir(domain) / "gold"
    return {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(folder.glob("*.json")) if p.name != "manifest.json"}


def blueprint_label(domain: str, key: str) -> str:
    """The seed label of a blueprint key (context or measure key, drug key); 'label:<text>' gives <text>."""
    if str(key).startswith("label:"):
        return str(key)[len("label:"):]
    bp = seed_questions._blueprint(domain)
    for section in ("contexts", "measures", "items"):
        item = (bp.get(section) or {}).get(key)
        if isinstance(item, dict) and item.get("label"):
            return seed_questions.names(domain).get(key, item["label"]) if section == "items" else item["label"]
        if isinstance(item, str):
            return item
    return str(key)


def measure_names(domain: str, key: str) -> dict[str, Any]:
    """A fact-like {measure, measure_alt} for a gold measure slot (for measure_ok when the question has no facts)."""
    item = (seed_questions._blueprint(domain).get("measures") or {}).get(key)
    if isinstance(item, dict):
        return {"measure": item.get("label", key), "measure_alt": list(item.get("alt", []))}
    return {"measure": blueprint_label(domain, key), "measure_alt": []}


@lru_cache(maxsize=32)
def l0_spans(domain: str, paper: str) -> dict[str, tuple[tuple[int, int], ...]]:
    path = domain_dir(domain) / "l0" / f"{paper}.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {f["id"]: tuple((s["start"], s["end"]) for s in f.get("spans", [])) for f in data.get("facts", [])}


def _symbol(iri: str | None) -> str:
    return norm.units().get(iri or "", {}).get("symbol", "") if iri else ""


def fact_slots(f: dict[str, Any]) -> dict[str, str]:
    """The canonical slot values of a seed fact."""
    out = {"subject": f["subject"].lower(), "patient_group": f["context"]}
    if f.get("dose") is not None:
        out["dose"] = canon.dose(f"{f['dose']} {_symbol(f.get('dose_unit')) or 'mg'}")
    if f.get("week") is not None:
        out["time_point"] = canon.time(f"{f['week']} {_symbol(f.get('time_unit')) or 'wk'}")
    return out


# ---------------------------------------------------------------- comparing names and values
def slot_value(slot: str, text: str | None, domain: str) -> str:
    """Canonical value of a cell or row slot, comparable with fact_slots."""
    if slot == "patient_group":                          # gold side only: seed context labels, as written
        return re.sub(r"\s+", " ", (text or "").strip())
    if slot == "subject":
        return re.sub(r"\s+", " ", (text or "").strip().lower())
    return canon.value(slot, text)


def _phrase(text: str) -> str:
    return " " + " ".join(re.findall(r"[a-z0-9]+", (text or "").lower())) + " "


def measure_ok(label: str, synonyms: list[str], fact: dict[str, Any]) -> bool:
    """One of the names contains one of the seed measure's names as a whole phrase, or the other way round
    ("HbA1c" and "change in HbA1c from baseline"). No word list."""
    mine = [_phrase(n) for n in [label, *synonyms] if _phrase(n).strip()]
    seed = [_phrase(n) for n in [fact["measure"], *fact.get("measure_alt", [])] if _phrase(n).strip()]
    return any(a in b or b in a for a in mine for b in seed)


def _value(text: str, unit: str) -> norm.Value | None:
    try:
        d = Decimal(text)
    except (InvalidOperation, TypeError):
        return None
    return norm.Value(d, unit or None, max(0, -d.as_tuple().exponent), "change")   # type: ignore[operator]


def same_value(text: str, unit: str, fact: dict[str, Any]) -> bool:
    v = _value(text, unit)
    return v is not None and norm.same(v, norm.seed_value(fact["value"], fact["unit"])).verdict == norm.Verdict.SAME


def _num(x: Any) -> str:
    return format(Decimal(str(x)).normalize(), "f")


def _overlaps(a: tuple[int, int], spans: tuple[tuple[int, int], ...]) -> bool:
    return any(a[0] < e and s < a[1] for s, e in spans)


# ---------------------------------------------------------------- run side
def _load(path: Path, cls: Any) -> Any:
    if not path.is_file():
        return None
    try:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError:
        return None


def _jsonl(path: Path, cls: Any) -> list[Any]:
    try:
        return read_jsonl(path, cls)
    except ValidationError:
        return []


def _f1(r: float, p: float) -> float:
    return 0.0 if r + p == 0 else 2 * r * p / (r + p)


# ---------------------------------------------------------------- layers
def row_names(row: Row, fact: dict[str, Any], domain: str) -> dict[str, bool]:
    want = fact_slots(fact)
    out = {"subject": slot_value("subject", row.subject, domain) == want["subject"]
           or want["subject"] in row.subject.lower(),
           "measure": measure_ok(row.measure, [], fact)}   # settings: by provenance (the row is this fact's)
    for k in ("time_point", "dose"):
        if k in want:
            out[k] = slot_value(k, getattr(row, k), domain) == want[k]
    return out


def _gold_key(grow: dict[str, Any], columns: list[dict[str, str]], domain: str) -> dict[str, str]:
    out = {}
    for col in columns:
        slot = canon.slot(col["label"]) if col["key"] == "candidate" else canon.slot(col["key"])
        out[slot] = slot_value(slot, grow["cells"].get(col["key"]), domain)
    return out


class Provenance:
    """Row index -> the seed facts the row states (same paper, quote offsets overlapping the fact's L0 span, same
    value). Gives the provenance value of a gold slot for a set of rows (PROVENANCE_SLOTS)."""

    def __init__(self, rows: list[Row], domain: str) -> None:
        facts_all = seed_facts(domain)
        by_paper: dict[str, list[dict[str, Any]]] = {}
        for f in facts_all.values():
            by_paper.setdefault(f["paper"], []).append(f)
        self.facts: dict[int, list[dict[str, Any]]] = {}
        for i, r in enumerate(rows):
            if r.dropped or r.std is None or r.quote_start < 0:
                continue
            spans = l0_spans(domain, r.paper)
            self.facts[i] = [f for f in by_paper.get(r.paper, [])
                             if _overlaps((r.quote_start, r.quote_end), spans.get(f["id"], ()))
                             and same_value(r.std.value, r.std.unit, f)]

    def value(self, slot: str, idxs: list[int]) -> str:
        """The one value of `slot` the rows' facts share; '?' when none or several."""
        got = {fact_slots(f).get(slot, "") for i in idxs for f in self.facts.get(int(i), [])}
        return got.pop() if len(got) == 1 else "?"


def _cells_key(cells: dict[str, str], domain: str, idxs: list[int] | None = None,
               prov: Provenance | None = None) -> dict[str, str]:
    """Comparable cells of an answer item: wording for subject, canonical time and dose, provenance for settings."""
    out = {canon.slot(lbl): slot_value(canon.slot(lbl), v, domain) for lbl, v in cells.items()
           if canon.slot(lbl) not in PROVENANCE_SLOTS}
    if prov is not None and idxs is not None:
        for slot in PROVENANCE_SLOTS:
            out[slot] = prov.value(slot, idxs)
    return out


def _cells_match(want: dict[str, str], got: dict[str, str]) -> bool:
    return all(got.get(k) == v for k, v in want.items())


def answer_layer(g: dict[str, Any], ans: Answer | None, facts: dict[str, dict[str, Any]], domain: str,
                 prov: Provenance | None = None) -> dict[str, Any]:
    """L3: which gold rows the answer table holds, and (best) which gold groups it gets right."""
    ga = g["answer"]
    grows = ga["table"]
    table = ans.table if ans else []
    keys = [_cells_key(a.cells, domain, a.rows, prov) for a in table]
    hit: dict[str, bool] = {}
    used: set[int] = set()
    for grow in grows:
        want = _gold_key(grow, ga["columns"], domain)
        f = facts[grow["row"]]
        found = [i for i, a in enumerate(table) if _cells_match(want, keys[i]) and same_value(a.value, a.unit, f)]
        hit[grow["row"]] = bool(found)
        used.update(found)
    recall = sum(hit.values()) / len(grows) if grows else 0.0
    precision = len(used) / len(table) if table else 0.0
    out: dict[str, Any] = {"recall": round(recall, 4), "precision": round(precision, 4),
                           "exact": bool(grows) and recall == 1.0 and precision == 1.0 and len(table) == len(grows),
                           "answer_rows": len(table), "gold_rows": len(grows), "in_answer": hit}
    if g["type"] != "best":
        out["score"] = round(_f1(recall, precision), 4)
        return out
    cand_col = next(c for c in ga["columns"] if c["key"] == "candidate")
    cand = canon.slot(cand_col["label"])
    agroups = ans.groups if ans else []
    akeys = [_cells_key(b.group, domain, [i for r in b.ranking for i in r.get("rows", [])], prov) for b in agroups]
    groups, right, matched = [], 0, set()
    for gg in ga["groups"]:
        want = {canon.slot(k): slot_value(canon.slot(k), v, domain) for k, v in gg["cells"].items()}
        i = next((i for i, k in enumerate(akeys) if i not in matched and _cells_match(want, k)), None)
        gw = slot_value(cand, gg.get("winner"), domain) if gg.get("winner") else None
        gs = STATUS.get(gg["status"], gg["status"])
        if i is None:
            groups.append({"cells": gg["cells"], "gold_status": gs, "gold_winner": gg.get("winner"), "found": False,
                           "ok": False})
            continue
        matched.add(i)
        b = agroups[i]
        aw = slot_value(cand, b.winner, domain) if b.winner else None
        ok = b.status == gs and aw == gw
        right += ok
        groups.append({"cells": gg["cells"], "gold_status": gs, "gold_winner": gg.get("winner"), "found": True,
                       "status": b.status, "winner": b.winner, "ok": ok})
    out["groups"] = groups
    out["extra_groups"] = len(agroups) - len(matched)
    out["score"] = round(right / max(len(ga["groups"]), len(agroups)), 4) if ga["groups"] else 0.0
    out["exact"] = bool(ga["groups"]) and right == len(ga["groups"]) == len(agroups)
    return out

def _role(verdict: str | None, a: str, b: str) -> str:
    """'a', 'b' or 'none' (no clear difference) from a verdict text such as '<A> better'."""
    v = (verdict or "").strip().lower()
    if not v or "no clear" in v:
        return "none"
    if a and v.startswith(a.lower()):
        return "a"
    if b and v.startswith(b.lower()):
        return "b"
    return "?" + v


def effect_layer(g: dict[str, Any], ans: Answer | None, facts: dict[str, dict[str, Any]], domain: str,
                 prov: Provenance | None = None) -> dict[str, Any]:
    """L3 effect: per gold row one entry with the same cells, the same difference and the same verdict side."""
    ga = g["answer"]
    names = seed_questions.names(domain)
    a_gold = names.get(g["slots"]["subject"][0], g["slots"]["subject"][0])
    b_gold = names.get(ga.get("comparator") or "", ga.get("comparator") or "")
    entries = ans.effects if ans else []
    keys = [{k: v for k, v in _cells_key(e.group, domain, e.rows, prov).items() if k not in ("paper", "comparator")}
            for e in entries]
    rows, used, right = [], set(), 0
    for grow in ga["table"]:
        want = {k: v for k, v in _gold_key(grow, ga["columns"], domain).items() if k not in ("paper", "comparator")}
        f = {**facts[grow["row"]], "value": grow["value"]}
        cand = [i for i, e in enumerate(entries) if all(keys[i].get(k, v) == v for k, v in want.items())
                and same_value(e.difference, e.unit, f)]
        side_ok = [i for i in cand if _role(entries[i].verdict, entries[i].a, entries[i].b)
                   == _role(grow.get("verdict"), a_gold, b_gold)]
        used.update(side_ok)
        right += bool(side_ok)
        rows.append({"row": grow["row"], "cells": grow["cells"], "value": grow["value"], "verdict": grow.get("verdict"),
                     "value_ok": bool(cand), "verdict_ok": bool(side_ok)})
    n = len(ga["table"])
    recall = right / n if n else 0.0
    precision = len(used) / len(entries) if entries else 0.0
    return {"recall": round(recall, 4), "precision": round(precision, 4), "score": round(_f1(recall, precision), 4),
            "exact": bool(n) and right == n == len(entries), "answer_rows": len(entries), "gold_rows": n,
            "effects": rows}


def trend_layer(g: dict[str, Any], ans: Answer | None, facts: dict[str, dict[str, Any]], domain: str,
                prov: Provenance | None = None) -> dict[str, Any]:
    """L3 trend: per gold series the answer series with the same cells, same ordered points, same direction."""
    ga = g["answer"]
    axis = canon.slot(ga["axis"]["key"])
    series = ans.trend if ans else []
    keys = [_cells_key(s.group, domain, [i for p in s.points for i in p.get("rows", [])], prov) for s in series]
    out, right, matched = [], 0, set()
    for gs in ga["series"]:
        want = {canon.slot(k): slot_value(canon.slot(k), v, domain) for k, v in gs["cells"].items()}
        i = next((i for i, k in enumerate(keys) if i not in matched and _cells_match(want, k)), None)
        gdir = DIRECTION.get(gs["direction"], gs["direction"])
        rec: dict[str, Any] = {"cells": gs["cells"], "gold_direction": gdir, "found": i is not None}
        if i is None:
            out.append({**rec, "points_ok": False, "direction_ok": False, "ok": False})
            continue
        matched.add(i)
        s = series[i]
        gat = [canon.value(axis, p["at"]) for p in gs["points"]]
        aat = [canon.value(axis, str(p.get("at", ""))) for p in s.points]
        points_ok = gat == aat and all(
            same_value(str(ap.get("value", "")), str(ap.get("unit", "")), {**facts[gp["row"]], "value": gp["value"]})
            for gp, ap in zip(gs["points"], s.points, strict=True))
        direction_ok = s.direction == gdir
        ok = points_ok and direction_ok
        right += ok
        out.append({**rec, "direction": s.direction, "points": aat, "gold_points": gat, "points_ok": points_ok,
                    "direction_ok": direction_ok, "ok": ok})
    n = len(ga["series"])
    return {"score": round(right / max(n, len(series)), 4) if n else 0.0,
            "exact": bool(n) and right == n == len(series), "series": out, "extra_series": len(series) - len(matched),
            "answer_rows": len(series), "gold_rows": n}


def list_layer(g: dict[str, Any], ans: Answer | None) -> dict[str, Any]:
    """L3 list: F1 of the paper sets."""
    want = {p["paper"] for p in g["answer"]["papers"]}
    got = {p.paper for p in (ans.papers if ans else [])}
    hit = want & got
    recall = len(hit) / len(want) if want else 0.0
    precision = len(hit) / len(got) if got else 0.0
    return {"recall": round(recall, 4), "precision": round(precision, 4), "score": round(_f1(recall, precision), 4),
            "exact": bool(want) and want == got, "papers": sorted(got), "gold_papers": sorted(want),
            "answer_rows": len(got), "gold_rows": len(want)}


def conflict_layer(g: dict[str, Any], ans: Answer | None, facts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """L3 conflict: each gold conflict group is flagged in Answer.conflicts with every paper's value."""
    gold_groups = [gg for gg in g["answer"]["groups"] if gg["status"] == "conflict"]
    flagged = ans.conflicts if ans else []
    out, right = [], 0
    for gg in gold_groups:
        def holds(c: Any) -> bool:
            return all(any(v.get("paper") == r["paper"] and same_value(str(v.get("value")), str(v.get("unit", "")),
                                                                        {**facts[r["row"]], "value": r["value"]})
                           for v in c.values) for r in gg["rows"])
        ok = any(holds(c) for c in flagged)
        right += ok
        out.append({"cells": gg["cells"], "papers": [r["paper"] for r in gg["rows"]], "ok": ok})
    n = len(gold_groups)
    return {"score": round(right / n, 4) if n else 0.0, "exact": bool(n) and right == n, "conflicts": out,
            "flagged": len(flagged), "answer_rows": len(ans.table) if ans else 0, "gold_rows": n}


def answer_rows_used(ans: Answer) -> set[int]:
    """Indexes into rows.jsonl of every row a part of the answer shows."""
    used: set[int] = set()
    for a in ans.table:
        used.update(a.rows)
    for e in ans.effects:
        used.update(e.rows)
    for s in ans.trend:
        for p in s.points:
            used.update(int(i) for i in p.get("rows", []))
    for b in ans.groups:
        for r in b.ranking:
            used.update(int(i) for i in r.get("rows", []))
    for c in ans.conflicts:
        for v in c.values:
            used.update(int(i) for i in v.get("rows", []))
    return used


def shows_value(ans: Answer) -> bool:
    """Does the answer show any value (a table value, an effect, a trend point, a ranked candidate)?"""
    return (any(a.value.strip() for a in ans.table) or bool(ans.effects) or any(s.points for s in ans.trend)
            or any(b.ranking for b in ans.groups) or bool(ans.conflicts))


def not_reported_layer(g: dict[str, Any], ans: Answer | None, rows: list[Row], domain: str) -> dict[str, Any]:
    """L3 for a question the papers cannot answer: right iff not reported (or no value); hallucination, trap."""
    near = list(g.get("spec", {}).get("extra", {}).get("near") or [])
    if ans is None:
        return {"score": 0.0, "exact": False, "said_not_reported": False, "hallucination": False,
                "near_miss_trap": False, "near": near, "trap_rows": [], "answer_rows": 0, "gold_rows": 0}
    value = shows_value(ans)
    right = ans.not_reported or not value
    facts_all = seed_facts(domain)
    trap = []
    for i in sorted(answer_rows_used(ans)):
        if not 0 <= i < len(rows) or rows[i].std is None:
            continue
        r = rows[i]
        for fid in near:
            f = facts_all.get(fid)
            if f is None or f["paper"] != r.paper or not same_value(r.std.value, r.std.unit, f):
                continue
            spans = l0_spans(domain, f["paper"]).get(fid, ())
            if not spans or r.quote_start < 0 or _overlaps((r.quote_start, r.quote_end), spans):
                trap.append({"row": i, "fact": fid})
                break
    return {"score": 1.0 if right else 0.0, "exact": right, "said_not_reported": ans.not_reported,
            "hallucination": value, "near_miss_trap": bool(trap), "near": near, "trap_rows": trap,
            "answer_rows": len(ans.table), "gold_rows": 0}


def advisor(g: dict[str, Any], spec: Spec | None, facts: dict[str, dict[str, Any]], domain: str) -> dict[str, Any]:
    """Spec vs the gold intent: one check per item; score = share passed. Effect against a drug: the spec form
    subjects [A, B] with no comparator is the expected one (spec/build.py shape)."""
    if spec is None:
        return {"score": 0.0, "checks": 0, "mismatches": ["no spec.json"]}
    names = seed_questions.names(domain)
    slots = g["slots"]
    some_fact = facts[g["row_ids"][0]] if g["row_ids"] else None
    want_type = SPEC_TYPE.get(g["type"], g["type"])
    checks: list[tuple[str, bool]] = [(f"type {spec.type} != {want_type}", spec.type == want_type)]
    want_subj = [names.get(s, s).lower() for s in slots.get("subject") or []]
    comp = slots.get("comparator")
    if g["type"] == "effect" and comp and comp != "placebo":
        want_subj.append(names.get(comp, comp).lower())          # B is a drug: [A, B], no comparator
    got_subj = {s.label.lower() for s in spec.subjects}
    checks.append((f"subjects {sorted(got_subj)} != {sorted(set(want_subj))}", got_subj == set(want_subj)))
    if slots.get("measure"):
        mfact = some_fact or measure_names(domain, slots["measure"])
        checks.append((f"measure {spec.measure.label!r} is not {mfact['measure']!r}",
                       measure_ok(spec.measure.label, spec.measure.synonyms, mfact)))
    fixed = {canon.slot(k): v for k, v in spec.fixed.items()}
    want_fixed: dict[str, str] = {}
    for gslot, sslot in GOLD_SLOT.items():
        if slots.get(gslot) is None:
            continue
        if gslot == "context":
            want_fixed[sslot] = some_fact["context"] if some_fact else blueprint_label(domain, str(slots[gslot]))
        elif some_fact:
            want_fixed[sslot] = fact_slots({**some_fact, gslot: _num(slots[gslot])})[sslot]
        else:
            want_fixed[sslot] = canon.value(sslot, f"{_num(slots[gslot])} {'mg' if gslot == 'dose' else 'wk'}")
    for sslot in sorted(set(want_fixed) | set(fixed)):
        got = slot_value(sslot, fixed.get(sslot), domain) if sslot in fixed else None
        want = slot_value(sslot, want_fixed[sslot], domain) if sslot in want_fixed else None
        if sslot in PROVENANCE_SLOTS:                     # a setting: fixed or not (its wording is not compared;
            same = sslot in fixed                         # Spec checked its quote against the question)
        else:
            same = got == want
        checks.append((f"fixed {sslot}: {fixed.get(sslot)!r} != {want_fixed.get(sslot)!r}",
                       sslot in want_fixed and same))
    all_points = {canon.slot(p.id) for p in spec.open_points if p.choice.strip().lower() == "all"}
    cols = {canon.slot(c) for c in spec.columns}
    want_open = {canon.slot(c) for c in g.get("open_columns", [])}
    if g["type"] == "trend":
        want_open.add(canon.slot(g["answer"]["axis"]["key"]))   # the trend axis is always an "all" column
    if g["type"] != "list":
        for c in sorted(want_open | (cols - {"subject"})):
            checks.append((f"open point {c}: answered 'all' and a column? gold {'yes' if c in want_open else 'no'}",
                           (c in want_open) == (c in all_points and c in cols)))
    if g["type"] == "best":
        cand = canon.slot(next(c for c in g["answer"]["columns"] if c["key"] == "candidate")["label"])
        checks.append((f"best_by {spec.best_by} != {cand}", spec.best_by == cand))
    if g["type"] in ("best", "effect"):
        hib = g["answer"].get("higher_is_better")
        checks.append((f"higher_is_better {spec.higher_is_better} != {hib}", spec.higher_is_better == hib))
    if g["type"] == "trend":
        axis = canon.slot(g["answer"]["axis"]["key"])
        checks.append((f"trend_by {spec.trend_by} != {axis}", spec.trend_by == axis))
    passed = sum(ok for _, ok in checks)
    return {"score": round(passed / len(checks), 4), "checks": len(checks),
            "mismatches": [m for m, ok in checks if not ok]}


def l3_layer(g: dict[str, Any], ans: Answer | None, rows: list[Row], facts: dict[str, dict[str, Any]], domain: str
             ) -> dict[str, Any]:
    """The L3 scorer of the question's dataset type (module doc). Each result has score, exact, in_answer."""
    t = g["type"]
    prov = Provenance(rows, domain)
    if t in NOT_REPORTED_TYPES:
        out = not_reported_layer(g, ans, rows, domain)
    elif t == "effect":
        out = effect_layer(g, ans, facts, domain, prov)
    elif t == "trend":
        out = trend_layer(g, ans, facts, domain, prov)
    elif t == "list":
        out = list_layer(g, ans)
    elif t == "conflict":
        out = conflict_layer(g, ans, facts)
    else:
        return answer_layer(g, ans, facts, domain, prov)
    if ans is not None and ans.not_reported and t not in NOT_REPORTED_TYPES:
        out["said_not_reported"] = True                   # an answerable question answered "not reported"
    # which gold facts the answer shows (for blame): a table row with the fact's cells and value
    out["in_answer"] = answer_layer(g, ans, facts, domain, prov)["in_answer"] if t in ("effect", "trend", "conflict") \
        else {rid: False for rid in g["row_ids"]}
    if t == "list":                                       # list: a fact is in the answer when its paper is listed
        listed = {p.paper for p in (ans.papers if ans else [])}
        out["in_answer"] = {rid: facts[rid]["paper"] in listed for rid in g["row_ids"]}
    return out


def score_question(qdir: Path, g: dict[str, Any], domain: str) -> dict[str, Any]:
    facts_all = seed_facts(domain)
    facts = {rid: facts_all[rid] for rid in g["row_ids"]}
    missing = [n for n in ("spec.json", "find.jsonl", "rows.jsonl", "answer.json") if not (qdir / n).is_file()]
    spec = _load(qdir / "spec.json", Spec)
    hits = {h.paper: h for h in _jsonl(qdir / "find.jsonl", FindHit)}
    rows: list[Row] = _jsonl(qdir / "rows.jsonl", Row)
    ans = _load(qdir / "answer.json", Answer)
    live = [(i, r) for i, r in enumerate(rows) if not r.dropped]
    l3 = l3_layer(g, ans, rows, facts, domain)

    per_fact, good_rows = [], set()
    for rid, f in facts.items():
        spans = l0_spans(domain, f["paper"]).get(rid, ())
        hit = hits.get(f["paper"])
        l1 = bool(spans) and hit is not None and any(_overlaps((p.start, p.end), spans) for p in hit.passages)
        matched = [i for i, r in live if r.paper == f["paper"] and r.std is not None and r.quote_start >= 0
                   and _overlaps((r.quote_start, r.quote_end), spans) and same_value(r.std.value, r.std.unit, f)]
        good_rows.update(matched)
        names = {i: row_names(rows[i], f, domain) for i in matched}
        usable = [i for i in matched if rows[i].quote_ok and all(names[i].values())]
        in_answer = l3["in_answer"].get(rid, False)
        blame = ("L0" if not spans else "find" if not l1 else "extract" if not matched else
                 "none" if in_answer else "extract" if not usable else "answer")
        per_fact.append({"id": rid, "paper": f["paper"], "l0": bool(spans), "l1": l1, "l2": bool(matched),
                         "name_ok": bool(matched) and any(all(n.values()) for n in names.values()),
                         "quote_ok": any(rows[i].quote_ok for i in matched), "rows": matched,
                         "names": {str(i): n for i, n in names.items()}, "in_answer": in_answer, "blame": blame})
    l3.pop("in_answer")
    base = {"qid": g["qid"], "type": g["type"], "answerable": g["type"] not in NOT_REPORTED_TYPES,
            "missing_files": missing, "facts": per_fact, "l3": l3, "advisor": advisor(g, spec, facts, domain)}
    if not per_fact:                                      # no gold facts (not reported): fact layers do not apply
        return {**base, "l0": None, "l1": None,
                "l2": {"recall": None, "precision": None, "name_ok": None, "rows": len(live),
                       "dropped": len(rows) - len(live), "matched_rows": 0},
                "blame": {k: 0 for k in (*LAYERS, "none")}}
    n = len(per_fact)
    blame_counts = {k: sum(p["blame"] == k for p in per_fact) for k in (*LAYERS, "none")}
    l2_recall = sum(p["l2"] for p in per_fact) / n
    l2_precision = len(good_rows) / len(live) if live else 0.0
    return {**base, "l0": round(sum(p["l0"] for p in per_fact) / n, 4),
            "l1": round(sum(p["l1"] for p in per_fact) / n, 4),
            "l2": {"recall": round(l2_recall, 4), "precision": round(l2_precision, 4),
                   "name_ok": round(sum(p["name_ok"] for p in per_fact) / n, 4),
                   "rows": len(live), "dropped": len(rows) - len(live), "matched_rows": len(good_rows)},
            "blame": blame_counts}


def _mean(xs: list[float | None]) -> float | None:
    """Mean of the values that apply (None = n/a is left out); None when none applies."""
    got = [x for x in xs if x is not None]
    return round(sum(got) / len(got), 4) if got else None


def _rate(flags: list[bool]) -> float | None:
    return round(sum(flags) / len(flags), 4) if flags else None


def type_totals(qs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per dataset type: questions, L3 mean, exact answers, fact layers (answerable types) or the not-reported rates."""
    out: dict[str, dict[str, Any]] = {}
    for t in TYPES:
        mine = [q for q in qs if q["type"] == t]
        if not mine:
            continue
        row: dict[str, Any] = {"questions": len(mine), "l3": _mean([q["l3"]["score"] for q in mine]),
                               "exact": sum(bool(q["l3"].get("exact")) for q in mine),
                               "advisor": _mean([q["advisor"]["score"] for q in mine])}
        if t in NOT_REPORTED_TYPES:
            row["hallucination"] = _rate([q["l3"]["hallucination"] for q in mine])
            if t == "near_miss":
                row["near_miss_trap"] = _rate([q["l3"]["near_miss_trap"] for q in mine])
        else:
            row.update({"l1": _mean([q["l1"] for q in mine]), "l2_recall": _mean([q["l2"]["recall"] for q in mine]),
                        "said_not_reported": sum(bool(q["l3"].get("said_not_reported")) for q in mine)})
        out[t] = row
    return out


def run_intervals(qs: list[dict[str, Any]]) -> dict[str, Any]:
    """95% bootstrap intervals (eval/bootstrap.py) for the headline totals. Every one of them is a mean over
    questions (no total pools facts across questions), so each interval resamples the questions the total averages."""
    ans_q = [q for q in qs if q["answerable"]]
    nr_q = [q for q in qs if not q["answerable"]]
    per_q = {"l0": [q["l0"] for q in qs], "l1": [q["l1"] for q in qs],
             "l2_recall": [q["l2"]["recall"] for q in qs], "l2_precision": [q["l2"]["precision"] for q in qs],
             "l2_name_ok": [q["l2"]["name_ok"] for q in qs], "l3": [q["l3"]["score"] for q in ans_q],
             "advisor": [q["advisor"]["score"] for q in qs],
             "not_reported_accuracy": [float(q["l3"]["score"] == 1.0) for q in nr_q],
             "not_reported_hallucination": [float(bool(q["l3"]["hallucination"])) for q in nr_q]}
    return {"method": bootstrap.METHOD, **{k: bootstrap.mean_interval(v) for k, v in per_q.items()}}


def score_run(run_dir: Path, domain: str = "medical", only: list[str] | None = None) -> dict[str, Any]:
    """Score every question of the run's config (its list, else every gold question of its split; `only` narrows
    it, e.g. for an old run made when the split had fewer questions); write eval.json."""
    run_dir = Path(run_dir)
    cfg_path = run_dir / "config.yaml"
    cfg = RunConfig.load(cfg_path) if cfg_path.is_file() else RunConfig(domain=domain)
    domain = cfg.domain or domain
    golds = gold(domain)
    qids = list(cfg.questions) or [q for q, g in golds.items() if g.get("split") == cfg.split]
    if only:
        qids = [q for q in qids if q in only]
    questions = {q: score_question(run_dir / q, golds[q], domain) for q in qids if q in golds}
    qs = list(questions.values())
    ans_q = [q for q in qs if q["answerable"]]
    nr_q = [q for q in qs if not q["answerable"]]
    near_q = [q for q in nr_q if q["type"] == "near_miss"]
    totals = {"questions": len(qs), "answerable": len(ans_q), "not_reported_questions": len(nr_q),
              "facts": sum(len(q["facts"]) for q in qs),
              "l0": _mean([q["l0"] for q in qs]), "l1": _mean([q["l1"] for q in qs]),
              "l2_recall": _mean([q["l2"]["recall"] for q in qs]),
              "l2_precision": _mean([q["l2"]["precision"] for q in qs]),
              "l2_name_ok": _mean([q["l2"]["name_ok"] for q in qs]),
              "l3": _mean([q["l3"]["score"] for q in ans_q]),          # answerable questions only
              "l3_exact": sum(bool(q["l3"]["exact"]) for q in ans_q),
              "advisor": _mean([q["advisor"]["score"] for q in qs]),
              "blame": {k: sum(q["blame"][k] for q in qs) for k in (*LAYERS, "none")},
              "not_reported": {"questions": len(nr_q),
                               "accuracy": _rate([q["l3"]["score"] == 1.0 for q in nr_q]),
                               "hallucination": _rate([q["l3"]["hallucination"] for q in nr_q]),
                               "near_miss_trap": _rate([q["l3"]["near_miss_trap"] for q in near_q]),
                               "near_miss_questions": len(near_q)},
              "per_type": type_totals(qs)}
    out = {"run_id": run_dir.name, "domain": domain, "config_name": cfg.name, "closed_book": cfg.closed_book,
           "unknown_questions": [q for q in qids if q not in golds], "totals": totals, "questions": questions}
    out["intervals"] = run_intervals(qs)
    out["data"] = datahash.data_hashes(domain, cfg.split)   # the data this score was made on (evqa/datahash.py)
    (run_dir / "eval.json").write_text(json.dumps(out, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":   # python -m evqa.eval.prism runs/evqa/<run_id> [domain] [qid,qid,...]
    import sys
    res = score_run(Path(sys.argv[1]), *(sys.argv[2:3] or ["medical"]),
                    only=sys.argv[3].split(",") if len(sys.argv) > 3 else None)
    print(json.dumps(res["totals"], indent=2))
