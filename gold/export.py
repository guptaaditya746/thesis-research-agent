"""The reviewed answer key (labelling gold.py export, ported): `$GOLD/<qid>/key.json` from the pulled reviews.

Decision rule for one person's answer on a review or overlap record (`decide_one`):
- `correct`: the candidate fact is kept, with its quote, paper and row. With a correction `s | p | o` the
  corrected fact is kept instead (an empty part keeps the candidate's; row values equal to the old s or o
  follow the fix). A correction that does not parse drops the record and is listed as a problem: it is
  not what the person meant;
- `incorrect`: dropped; `unsure`: dropped and listed in export.json for a second look.
A kept fact is vital when the person answered vital yes.

Several answers on one record (the overlap): people disagree when they differ on keep/drop or keep
different facts. The adjudicator (`--adjudicator NAME`: a third person, or the outcome of a recorded
discussion entered under a separate user) decides with their own answer; if the adjudicator is one of the
two raters, that rater's answer wins and the export says so. Unresolved disagreements stay out of the key
and are listed in export.json. A fact both keep is vital only if both said vital.

Missing facts: each line `s | p | o | file | quote` of the missing and screening records is anchored in
the corpus file with agent/anchor.py, the check the agent's claims pass. An anchored line becomes a key
fact (its quote the exact text in the file, vital false, candidate_id null); a line that does not parse or
anchor is listed in export.json `rejected` and not added.

Rows (`merge_rows`): kept facts are grouped into rows of the concept's answer shape by the merge rule of
C1's draft key, implemented here until C1's module is merged: one graph row per (source, predicate,
target) of the candidate's row; one table row per value of the concept's first column, other cells the
first value given, list cells the union. A fact without a row (an added one) joins the row its subject or
object names, else it gets a row built from it. Facts with the same s/p/o in one row are one fact (vital
if any copy is).

The key (plan "Gold", "Answer key"): `{qid, concept_sha256, kind, version: "v1", reviewed: true, rows,
notes, review}`, `review` counting what was decided. Facts carry the answer schema's fields, with
`claims: []` and `origin: "research"` (the key has no broker claims; its quote is in `quote`), plus the
gold-only fields `paper_id, quote, vital, candidate_id`. `as_answer(key)` strips those and the result
validates against `agent.concept.answer_schema_for(concept)`; export writes no key that does not.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agent import anchor
from agent.concept import concept_sha256 as concept_hash
from agent.concept import validate_answer

from . import review

VERSION = "v1"
KEY_FILE = "key.json"
EXPORT_FILE = "export.json"
GOLD_ONLY = ("paper_id", "quote", "vital", "candidate_id")
MISSING_PARTS = 5  # s | p | o | file | quote; the quote is the rest of the line and may hold "|"


def norm(value: Any) -> str:
    return " ".join(str(value).split()).casefold()


def _name(value: Any) -> str:
    """Loose name for matching predicates and columns: `evaluates on` ~ `evaluatesOn`."""
    return re.sub(r"[^0-9a-z]", "", str(value).casefold())


def spo_key(fact: dict[str, Any]) -> tuple[str, str, str]:
    return norm(fact["s"]), norm(fact["p"]), norm(fact["o"])


# --- one answer -------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Outcome:
    keep: bool
    fact: dict[str, Any] | None  # the kept s/p/o
    vital: bool
    reason: str  # correct, corrected, incorrect, unsure, bad_correction, unanswered


def corrected(text: Any, base: dict[str, Any]) -> dict[str, Any]:
    """The fact after a correction `s | p | o` (an empty part keeps `base`'s); ValueError if it is not one."""
    text = str(text or "").strip()
    if not text:
        return {k: base[k] for k in "spo"}
    parts = [part.strip() for part in text.split("|")]
    if len(parts) != 3 or not any(parts):
        raise ValueError(f"not `s | p | o`: {text!r}")
    return {k: part or base[k] for k, part in zip("spo", parts)}


def decide_one(item: dict[str, Any], answer: dict[str, Any]) -> Outcome:
    label = answer.get("label")
    if label == "correct":
        try:
            fact = corrected(answer.get("correction"), item)
        except ValueError:
            return Outcome(False, None, False, "bad_correction")
        changed = spo_key(fact) != spo_key(item)
        return Outcome(True, fact, answer.get("vital") == "yes", "corrected" if changed else "correct")
    if label in ("incorrect", "unsure"):
        return Outcome(False, None, False, str(label))
    return Outcome(False, None, False, "unanswered")


def would_keep(answer: dict[str, Any]) -> bool:
    """The keep/drop half of the rule without a candidate: agreement counts keep/drop exactly as export."""
    return decide_one({"s": "s", "p": "p", "o": "o"}, answer).keep


# --- all answers of a question -----------------------------------------------------------------------------

@dataclass
class Decision:
    candidate_id: str
    keep: bool
    fact: dict[str, Any] | None
    vital: bool
    reviewers: list[str]
    reason: str


@dataclass
class Decided:
    decisions: list[Decision] = field(default_factory=list)
    disagreements: list[dict[str, Any]] = field(default_factory=list)
    unsure: list[dict[str, Any]] = field(default_factory=list)
    unreviewed: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    adjudicated: int = 0
    adjudicated_by_a_rater: int = 0  # disagreements the adjudicator had answered as one of the two raters


def decide(items: dict[str, dict[str, Any]], records: list[dict[str, Any]],
           adjudicator: str | None = None) -> Decided:
    """Decisions for review and overlap records (`items`: pool records by candidate id)."""
    out = Decided()
    for record in records:
        cid = record["id"]
        item = items.get(cid)
        if item is None:
            out.problems.append(f"record {cid} has no pool record here")
            continue
        answers = review.submitted(record)
        if not answers:
            out.unreviewed.append(cid)
            continue
        outcomes = {user: decide_one(item, answer) for user, answer in answers.items()}
        for user, outcome in sorted(outcomes.items()):
            if outcome.reason == "bad_correction":
                out.problems.append(f"{cid}: {user}'s correction {answers[user].get('correction')!r} is not "
                                    "`s | p | o`; counted as dropped")
            elif outcome.reason == "unsure":
                out.unsure.append({"candidate_id": cid, "user": user, "note": answers[user].get("note")})
        reviewers = sorted(answers)
        kept = {spo_key(o.fact) for o in outcomes.values() if o.keep and o.fact}
        if len({o.keep for o in outcomes.values()}) > 1 or len(kept) > 1:
            row: dict[str, Any] = {"candidate_id": cid, "fact": f"{item['s']} | {item['p']} | {item['o']}",
                                   "answers": answers}
            if adjudicator and adjudicator in outcomes:
                # With two answers the adjudicator is one side (a rater whose own answer wins); a third
                # person's adjudication is a third answer.
                rater = len(outcomes) <= 2
                o = outcomes[adjudicator]
                out.decisions.append(Decision(cid, o.keep, o.fact, o.vital, reviewers,
                                              f"adjudicated by {adjudicator}"
                                              + (" (one of the two raters)" if rater else "") + f": {o.reason}"))
                row |= {"resolved_by": adjudicator, "resolved_by_a_rater": rater}
                out.adjudicated += 1
                out.adjudicated_by_a_rater += rater
            out.disagreements.append(row)
            continue
        first = outcomes[min(outcomes)]
        vital = first.keep and all(o.vital for o in outcomes.values())
        out.decisions.append(Decision(cid, first.keep, first.fact, vital, reviewers, first.reason))
    return out


# --- facts people added ---------------------------------------------------------------------------------

def parse_missing(line: str) -> dict[str, str] | None:
    parts = [part.strip() for part in line.split("|", MISSING_PARTS - 1)]
    if len(parts) != MISSING_PARTS or not all(parts):
        return None
    return dict(zip(("s", "p", "o", "file", "quote"), parts))


def added_facts(records: list[dict[str, Any]], corpus: review.Corpus) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Facts from the `missing` answers of missing-facts and screening records: (anchored, rejected)."""
    added: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for record in records:
        for user, answer in sorted(review.submitted(record).items()):
            for line in str(answer.get("missing") or "").splitlines():
                if not line.strip():
                    continue
                base = {"line": line.strip(), "user": user, "record": record["id"]}
                parsed = parse_missing(line)
                if parsed is None:
                    rejected.append({**base, "reason": "format", "detail": "want `s | p | o | file | quote`"})
                    continue
                file = corpus.file_name(parsed["file"])
                if not corpus.has(file):
                    rejected.append({**base, "reason": "unknown_file", "detail": file})
                    continue
                try:
                    sel = anchor.find(corpus.index(file), parsed["quote"], file=file)
                except anchor.AnchorError as exc:
                    rejected.append({**base, "reason": exc.reason, "detail": str(exc)})
                    continue
                added.append({**base, "s": parsed["s"], "p": parsed["p"], "o": parsed["o"], "file": file,
                              "paper_id": corpus.paper_id(file), "quote": sel.exact, "anchor": sel.json()})
    return added, rejected


# --- rows (the draft key's merge rule) ------------------------------------------------------------------

def coerce(value: Any, type_name: str) -> Any:
    """A cell or attribute value in the column's type; None when it cannot be one (null = not established)."""
    if value is None or value == "" or value == []:
        return None
    if type_name.startswith("list<"):
        values = value if isinstance(value, list) else [value]
        out = [v for v in (coerce(x, type_name[5:-1]) for x in values) if v is not None]
        return out or None
    if type_name in ("integer", "number"):
        if isinstance(value, bool):
            return None
        try:
            number = float(str(value).strip().replace(",", ""))
        except ValueError:
            return None
        if type_name == "number":
            return number
        return int(number) if number.is_integer() else None
    if type_name == "boolean":
        return value if isinstance(value, bool) else {"true": True, "false": False}.get(norm(value))
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip() or None


def _pick_edge(edges: list[dict[str, Any]], raw: dict[str, Any], fact: dict[str, Any]) -> dict[str, Any] | None:
    """The edge type named by the row's predicate (which must then match), else by the fact's predicate,
    else by the row's node types, else the concept's only edge type."""
    if raw.get("predicate"):
        return next((e for e in edges if _name(e["predicate"]) == _name(raw["predicate"])), None)
    if found := [e for e in edges if _name(e["predicate"]) == _name(fact.get("p", ""))]:
        return found[0]
    typed = [e for e in edges if (e["source"], e["target"]) == (raw.get("source_type"), raw.get("target_type"))]
    if len(typed) == 1:
        return typed[0]
    return edges[0] if len(edges) == 1 else None


def row_content(concept: dict[str, Any], raw: dict[str, Any] | None, fact: dict[str, Any]) -> dict[str, Any] | None:
    """A row's fields (no id, no facts) in the concept's answer shape; None when no edge type fits."""
    shape = concept["answer_shape"]
    raw = raw or {}
    if shape["kind"] == "table":
        cells = raw["cells"] if isinstance(raw.get("cells"), dict) else raw
        if not cells:  # an added fact: the first column names the subject, a column named like p the object
            first = shape["columns"][0]["name"]
            cells = {first: fact["s"], **{c["name"]: fact["o"] for c in shape["columns"][1:]
                                           if _name(c["name"]) == _name(fact["p"])}}
        return {"cells": {c["name"]: coerce(cells.get(c["name"]), c["type"]) for c in shape["columns"]}}
    edge = _pick_edge(shape["edges"], raw, fact)
    if edge is None:
        return None
    attrs = raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {}
    return {"source": str(raw.get("source") or fact["s"]), "source_type": edge["source"],
            "predicate": edge["predicate"], "target": str(raw.get("target") or fact["o"]),
            "target_type": edge["target"],
            "attributes": {a["name"]: coerce(attrs.get(a["name"]), a["type"]) for a in edge.get("attributes", [])}}


def _cell_key(value: Any) -> str:
    return norm(json.dumps(value, ensure_ascii=False, sort_keys=True))


def row_key(concept: dict[str, Any], content: dict[str, Any]) -> str:
    if concept["answer_shape"]["kind"] == "graph":
        return "\x1f".join((norm(content["source"]), content["predicate"], norm(content["target"])))
    cells = content["cells"]
    first = cells[concept["answer_shape"]["columns"][0]["name"]]
    return _cell_key(first if first is not None else cells)


def _merge_values(old: dict[str, Any], new: dict[str, Any], where: str, problems: list[str]) -> None:
    for name, value in new.items():
        if value is None:
            continue
        if old.get(name) is None:
            old[name] = value
        elif isinstance(old[name], list):
            old[name] += [v for v in value if norm(v) not in {norm(x) for x in old[name]}]
        elif norm(old[name]) != norm(value):
            problems.append(f"{where}: {name} is {old[name]!r} in one candidate and {value!r} in another; kept the first")


def substitute(value: Any, old: dict[str, Any], new: dict[str, Any]) -> Any:
    """Row values equal to the old subject or object, replaced by the corrected ones."""
    swap = {norm(old[k]): new[k] for k in ("s", "o") if norm(old[k]) != norm(new[k])}
    if not swap:
        return value
    if isinstance(value, dict):
        return {k: substitute(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, old, new) for v in value]
    return swap.get(norm(value), value) if isinstance(value, str) else value


def merge_rows(concept: dict[str, Any], items: list[tuple[dict[str, Any] | None, dict[str, Any]]],
               ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Rows of the key from (raw row | None, fact) pairs in order: (rows, merged duplicates, problems).

    TODO(integration): C1's draft key (gold/draft.py) groups candidates into rows; once it is merged, call
    its rule here so key.draft.json and key.json group facts the same way.
    """
    graph = concept["answer_shape"]["kind"] == "graph"
    rows: dict[str, dict[str, Any]] = {}
    facts: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = {}
    merged: list[dict[str, Any]] = []
    problems: list[str] = []
    for raw, fact in items:
        label = fact.get("candidate_id") or f"added fact {fact['s']} | {fact['p']} | {fact['o']}"
        if not str(fact["s"]).strip() or not str(fact["p"]).strip():
            problems.append(f"{label}: empty subject or predicate; left out")
            continue
        key = None
        if raw is None and not graph:  # an added table fact joins the row its subject or object names
            key = next((k for k in rows if k in (_cell_key(fact["s"]), _cell_key(fact["o"]))), None)
        if key is None:
            content = row_content(concept, raw, fact)
            if content is None:
                problems.append(f"{label}: no edge type of the concept fits predicate {fact['p']!r}; left out")
                continue
            key = row_key(concept, content)
            if key in rows:
                _merge_values(rows[key]["attributes" if graph else "cells"],
                              content["attributes" if graph else "cells"], label, problems)
            else:
                rows[key], facts[key] = content, {}
        same = facts[key].get(spo_key(fact))
        if same is None:
            facts[key][spo_key(fact)] = dict(fact)
        else:
            same["vital"] = same["vital"] or fact["vital"]
            merged.append({"kept": same.get("candidate_id"), "merged": fact.get("candidate_id"),
                           "fact": f"{fact['s']} | {fact['p']} | {fact['o']}"})
    out, n = [], 0
    for r, (key, content) in enumerate(rows.items(), 1):
        row_facts = []
        for fact in facts[key].values():
            n += 1
            o = fact["o"] if isinstance(fact["o"], (str, int, float, bool)) else json.dumps(fact["o"])
            row_facts.append({"id": f"f{n}", "s": str(fact["s"]), "p": str(fact["p"]), "o": o, "claims": [],
                              "origin": "research", "paper_id": fact.get("paper_id"), "quote": fact.get("quote"),
                              "vital": bool(fact["vital"]), "candidate_id": fact.get("candidate_id")})
        out.append({"id": f"r{r}", **content, "facts": row_facts})
    return out, merged, problems


# --- the key ---------------------------------------------------------------------------------------------

def as_answer(key: dict[str, Any]) -> dict[str, Any]:
    """The key in the agent's answer shape: gold-only fields and keys stripped."""
    rows = [{**row, "facts": [{k: v for k, v in f.items() if k not in GOLD_ONLY} for f in row["facts"]]}
            for row in key["rows"]]
    return {"concept_sha256": key["concept_sha256"], "kind": key["kind"], "rows": rows,
            **({"notes": key["notes"]} if "notes" in key else {})}


def validate_key(key: dict[str, Any], concept: dict[str, Any]) -> list[str]:
    return validate_answer(as_answer(key), concept)


@dataclass
class Export:
    qid: str
    key: dict[str, Any] | None
    report: dict[str, Any]
    problems: list[str]


def export(root: Path, qid: str, *, corpus: review.Corpus, concepts: Path | None,
           adjudicator: str | None = None, write: bool = True) -> Export:
    """Decide every pulled record of one question and build its key; write key.json (only when it
    validates) and export.json."""
    concept = review.concept(concepts, qid)
    if concept is None:
        return Export(qid, None, {}, [f"{qid}: no concept.json under {concepts}"])
    items = {item["id"]: item for item in review.pool(root, qid)}
    pulled = review.reviews(root, qid)
    decided = decide(items, pulled["review"] + pulled["overlap"], adjudicator)
    added, rejected = added_facts(pulled["missing"] + pulled["screening"], corpus)
    pairs: list[tuple[dict[str, Any] | None, dict[str, Any]]] = []
    for d in sorted(decided.decisions, key=lambda d: d.candidate_id):
        if d.keep and d.fact:
            item = items[d.candidate_id]
            pairs.append((substitute(item.get("row"), item, d.fact),
                          {**d.fact, "paper_id": item.get("paper_id"), "quote": item.get("quote"),
                           "vital": d.vital, "candidate_id": d.candidate_id}))
    pairs += [(None, {"s": a["s"], "p": a["p"], "o": a["o"], "paper_id": a["paper_id"], "quote": a["quote"],
                      "vital": False, "candidate_id": None}) for a in added]
    rows, merged, problems = merge_rows(concept, pairs)
    problems = decided.problems + problems
    sha = concept_hash(concept)
    doc = review.read_json(review.qdir(root, qid) / "doc.json") or {}
    stale = bool(doc.get("concept_sha256")) and doc["concept_sha256"] != sha
    if stale:
        problems.append(f"{qid}: D was built for concept {doc['concept_sha256'][:12]}, the picked concept is "
                        f"{sha[:12]}; rebuild D before exporting")
    unresolved = sum(1 for d in decided.disagreements if "resolved_by" not in d)
    counts = {"records": len(items), "decided": len(decided.decisions),
              "kept": sum(d.keep for d in decided.decisions), "dropped": sum(not d.keep for d in decided.decisions),
              "unsure": len({u["candidate_id"] for u in decided.unsure}), "unreviewed": len(decided.unreviewed),
              "disagreements": len(decided.disagreements), "unresolved": unresolved,
              "adjudicated": decided.adjudicated, "adjudicated_by_a_rater": decided.adjudicated_by_a_rater,
              "added": len(added), "added_rejected": len(rejected),
              "facts": sum(len(r["facts"]) for r in rows), "rows": len(rows)}
    reviewers = sorted({u for d in decided.decisions for u in d.reviewers}
                       | {a["user"] for a in added})
    exported_at = review.utc_now()
    key = {"qid": qid, "concept_sha256": sha, "kind": concept["answer_shape"]["kind"], "version": VERSION,
           "reviewed": True, "rows": rows,
           "notes": (f"Answer key of D reviewed in Argilla by {', '.join(reviewers) or 'nobody yet'}: "
                     f"{counts['kept']} of {counts['records']} candidate facts kept, {counts['added']} added "
                     "by reviewers. Details in export.json."),
           "review": {"exported_at": exported_at, "reviewers": reviewers, "adjudicator": adjudicator,
                      **counts, "complete": not decided.unreviewed and not unresolved}}
    invalid = validate_key(key, concept)
    problems += invalid
    if decided.adjudicated_by_a_rater:
        problems.append(f"{qid}: {decided.adjudicated_by_a_rater} disagreement(s) settled by {adjudicator}, "
                        "one of the two raters: their own answer won (prefer a third person)")
    report = {"qid": qid, "exported_at": exported_at, "adjudicator": adjudicator, "counts": counts,
              "decisions": [asdict(d) for d in decided.decisions], "disagreements": decided.disagreements,
              "unsure": decided.unsure, "unreviewed": decided.unreviewed, "added": added, "rejected": rejected,
              "merged": merged, "problems": problems}
    ok = not invalid and not stale
    if write:
        review.write_json(review.qdir(root, qid) / EXPORT_FILE, report)
        if ok:
            review.write_json(review.qdir(root, qid) / KEY_FILE, key)
    return Export(qid, key if ok else None, report, problems)
