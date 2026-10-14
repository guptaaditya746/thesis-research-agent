"""The reviewed answer key (labelling gold.py export, ported): `$GOLD/<qid>/key.json` from the pulled reviews.

Decision rule for one person's answer on a review or overlap record (`decide_one`):
- `correct`: the candidate fact is kept, with its quote, paper and row. With a correction `s | p | o` the
  corrected fact is kept instead (an empty part keeps the candidate's; row values equal to the old s or o
  follow the fix). A correction that does not parse drops the record and is listed as a problem: it is
  not what the person meant;
- `incorrect`: dropped; `unsure`: dropped and listed in export.json for a second look.
A kept fact is vital when the person answered vital yes.

Answers count only on records that still show the candidate's current fact: a record id carries a
digest of the fact (gold/review.py record_id), and answers on a record whose id no candidate has now
(D rebuilt, the id re-used for another fact) are listed as `stale` and not used.

Several answers on one record (the overlap): people disagree when they differ on keep/drop or keep
different facts. The adjudicator (`--adjudicator NAME`: a third person, or the outcome of a recorded
discussion entered under a separate user) decides with their own answer; if the adjudicator is one of the
two raters, that rater's answer wins and the export says so. Unresolved disagreements stay out of the key
and are listed in export.json. A fact both keep is vital only if both said vital.

Quotes: every key fact's quote is text that occurs in its corpus file, read through review.Corpus (the
manifest hash check of agent/broker.py). A kept candidate is located again (review.Corpus.locate) and its
quote is the exact text found there; one whose quote is not in the file, or whose file the corpus cannot
give, is left out and listed under `unanchored`. A quote that occurs several times is kept (the reviewer
saw it marked; C1's draft leaves such candidates out because they have no single anchor). Missing facts:
each line `s | p | o | file | quote` of the missing and screening records is anchored with
agent/anchor.py, as the broker anchors the agent's claims (an ambiguous quote is rejected there too, so
the reviewer quotes more). An anchored line becomes a key fact (vital false, candidate_id null); a line
that does not parse or anchor is listed in export.json `rejected` and not added.

Rows (`merge_rows`) follow the rule of C1's draft key and doc.json, imported from gold/build.py (norm,
key_column, merge_cells with its count_columns, row_key: one implementation), so key.draft.json
and key.json group the same facts the same way: table rows with the same normalised value (NFKC,
casefold, letters and digits) in the first string column are one row, list cells unioned, a count column
of a list recomputed, other cells the first value given, rows without a key value never merged; graph
rows are one per (source type, normalised source, predicate, target type, normalised target), the edge
type picked by predicate and node types. A fact without a row (an added one) gets a row built from it,
which joins the row its subject (or, failing that, its object) names. Facts with the same normalised
s/p/o in one row are one fact (vital if any copy is), as in the draft.

The key (plan "Gold", "Answer key"): `{qid, concept_sha256, kind, version: "v1", reviewed: true, rows,
notes, key_sha256, review}`, `review` counting what was decided and recording what the key was built from
(`inputs`: D's build, the sha256 of C1's files and of the pulled reviews, the exporting commit);
`key_sha256` is the hash of the rows, for scoring to record next to the version. Facts carry the answer
schema's fields, with `claims: []` and `origin: "research"` (the key has no broker claims; its quote is in
`quote`), plus the gold-only fields `paper_id, quote, vital, candidate_id`. `as_answer(key)` strips those
and the result validates against `agent.concept.answer_schema_for(concept)`. Export writes no key that does
not validate or that was built on a D for another concept; it then moves an older key.json aside to
key.stale.json, so readers never take a key the current review no longer gives.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agent import anchor
from agent.canonical import canonical_bytes, file_sha256, sha256_hex
from agent.concept import concept_sha256 as concept_hash
from agent.concept import validate_answer
from agent.rundir import git_head

from . import review
from .build import _edge_spec, key_column, merge_cells, norm, row_key

VERSION = "v1"
KEY_FILE = "key.json"
STALE_KEY_FILE = "key.stale.json"
EXPORT_FILE = "export.json"
GOLD_ONLY = ("paper_id", "quote", "vital", "candidate_id")
EDGE_FIELDS = ("source", "source_type", "predicate", "target", "target_type")
MISSING_PARTS = 5  # s | p | o | file | quote; the quote is the rest of the line and may hold "|"
INPUT_FILES = ("doc.json", "candidates.jsonl", "chunks.jsonl", "triage.jsonl", "pool.jsonl", "pool.strata.json")


def strict(value: Any) -> str:
    """Whitespace and case only: whether two people kept the same fact, or a correction changed it."""
    return " ".join(str(value).split()).casefold()


def _name(value: Any) -> str:
    """Loose name for matching predicates and columns: `evaluates on` ~ `evaluatesOn`."""
    return re.sub(r"[^0-9a-z]", "", str(value).casefold())


def spo_key(fact: dict[str, Any]) -> tuple[str, str, str]:
    return strict(fact["s"]), strict(fact["p"]), strict(fact["o"])


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
    stale: list[dict[str, Any]] = field(default_factory=list)  # answered records that show no current fact
    problems: list[str] = field(default_factory=list)
    adjudicated: int = 0
    adjudicated_by_a_rater: int = 0  # disagreements the adjudicator had answered as one of the two raters


def decide(items: dict[str, dict[str, Any]], records: list[dict[str, Any]],
           adjudicator: str | None = None) -> Decided:
    """Decisions for review and overlap records. `items`: the pool records by their current record id
    (review.current_records); a record with another id is stale and its answers are not used."""
    out = Decided()
    candidates = {item["id"] for item in items.values()}
    for record in records:
        item = items.get(record["id"])
        answers = review.submitted(record)
        if item is None:
            cid, _ = review.split_record_id(record["id"])
            if answers:
                why = ("the candidate's fact changed since it was pushed" if cid in candidates
                       else "no candidate of the current D has this id")
                out.stale.append({"record": record["id"], "candidate_id": cid, "reason": why, "answers": answers})
            continue
        cid = item["id"]
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
    if out.stale:
        out.problems.append(f"{len(out.stale)} answered record(s) show a fact the current D does not have; "
                            "their answers are not used (export.json `stale`)")
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
                try:
                    file = corpus.resolve(parsed["file"])
                    sel = anchor.find(corpus.index(file), parsed["quote"], file=file)
                except review.Rejected as exc:  # unknown_file, missing_file, corpus_file_hash_mismatch
                    rejected.append({**base, "reason": exc.reason, "detail": corpus.file_name(parsed["file"])})
                    continue
                except anchor.AnchorError as exc:
                    rejected.append({**base, "reason": exc.reason, "detail": str(exc)})
                    continue
                added.append({**base, "s": parsed["s"], "p": parsed["p"], "o": parsed["o"], "file": file,
                              "paper_id": corpus.paper_id(file), "quote": sel.exact, "anchor": sel.json()})
    return added, rejected


# --- rows of the key ----------------------------------------------------------------------------------------

def fact_key(fact: dict[str, Any]) -> tuple[str, str, str]:
    """One fact per row and normalised s/p/o, as in C1's draft key."""
    return norm(fact["s"]), norm(fact["p"]), norm(fact["o"])


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
        return value if isinstance(value, bool) else {"true": True, "false": False}.get(strict(value))
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip() or None


def pick_edge(edges: list[dict[str, Any]], raw: dict[str, Any], fact: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """(edge type, problem) for a row: named by the row's predicate (which must then match), else by the
    fact's; among those, the one whose node types are the row's (the concept may use one predicate
    between several type pairs). Name alone decides only when the row has no types; when several still
    fit, the first is taken and the problem says so."""
    named = raw.get("predicate") or fact.get("p", "")
    fits = [e for e in edges if _name(e["predicate"]) == _name(named)]
    if raw.get("predicate") and not fits:
        return None, f"no edge type of the concept is called {named!r}"
    fits = fits or edges
    types = (raw.get("source_type"), raw.get("target_type"))
    if any(types):
        fits = [e for e in fits if all(t is None or t == have for t, have in zip(types, (e["source"], e["target"])))]
        if not fits:
            return None, f"no edge type {types[0]} -{named}-> {types[1]} in the concept"
    if len(fits) > 1:
        options = ", ".join(f"{e['source']} -{e['predicate']}-> {e['target']}" for e in fits)
        return fits[0], f"several edge types fit predicate {named!r} ({options}); took the first"
    return fits[0], None


def row_content(concept: dict[str, Any], raw: dict[str, Any] | None,
                fact: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """(a row's fields in the concept's answer shape, without id and facts; a problem or None). The row
    is None when no edge type fits. Values are coerced to their column types."""
    shape = concept["answer_shape"]
    raw = raw or {}
    if shape["kind"] == "table":
        cells = raw["cells"] if isinstance(raw.get("cells"), dict) else raw
        return {"cells": {c["name"]: coerce(cells.get(c["name"]), c["type"]) for c in shape["columns"]}}, None
    edge, problem = pick_edge(shape["edges"], raw, fact)
    if edge is None:
        return None, problem
    attrs = raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {}
    return {"source": str(raw.get("source") or fact["s"]), "source_type": edge["source"],
            "predicate": edge["predicate"], "target": str(raw.get("target") or fact["o"]),
            "target_type": edge["target"],
            "attributes": {a["name"]: coerce(attrs.get(a["name"]), a["type"]) for a in edge.get("attributes", [])}}, problem


def added_cells(shape: dict[str, Any], fact: dict[str, Any], keys: set[Any]) -> dict[str, Any]:
    """Table cells for an added fact: the key column names its subject (or its object, when only the
    object names a row already there), a column named like the predicate the other side."""
    columns = shape["columns"]
    key = key_column(columns) or columns[0]["name"]
    own, other = fact["s"], fact["o"]
    if norm(own) not in keys and norm(other) in keys:
        own, other = other, own
    return {key: own, **{c["name"]: other for c in columns if c["name"] != key and _name(c["name"]) == _name(fact["p"])}}


def substitute(value: Any, old: dict[str, Any], new: dict[str, Any]) -> Any:
    """Row values equal to the old subject or object, replaced by the corrected ones."""
    swap = {strict(old[k]): new[k] for k in ("s", "o") if strict(old[k]) != strict(new[k])}
    if not swap:
        return value
    if isinstance(value, dict):
        return {k: substitute(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, old, new) for v in value]
    return swap.get(strict(value), value) if isinstance(value, str) else value


def merge_rows(concept: dict[str, Any], items: list[tuple[dict[str, Any] | None, dict[str, Any]]],
               ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Rows of the key from (raw row | None, fact) pairs in order: (rows, merged duplicates, problems)."""
    shape = concept["answer_shape"]
    graph = shape["kind"] == "graph"
    groups: dict[Any, dict[str, Any]] = {}
    merged: list[dict[str, Any]] = []
    problems: list[str] = []
    for raw, fact in items:
        label = fact.get("candidate_id") or f"added fact {fact['s']} | {fact['p']} | {fact['o']}"
        if not str(fact["s"]).strip() or not str(fact["p"]).strip():
            problems.append(f"{label}: empty subject or predicate; left out")
            continue
        if raw is None and not graph:
            raw = added_cells(shape, fact, set(groups))
        content, problem = row_content(concept, raw, fact)
        if problem:
            problems.append(f"{label}: {problem}" + ("; left out" if content is None else ""))
        if content is None:
            continue
        key = row_key(shape, content if graph else content["cells"])
        group = groups.setdefault(key if key is not None else ("unkeyed", len(groups)), {"rows": [], "facts": {}})
        group["rows"].append(content)
        same = group["facts"].get(fact_key(fact))
        if same is None:
            group["facts"][fact_key(fact)] = dict(fact)
        else:
            same["vital"] = same["vital"] or fact["vital"]
            merged.append({"kept": same.get("candidate_id"), "merged": fact.get("candidate_id"),
                           "fact": f"{fact['s']} | {fact['p']} | {fact['o']}"})
    out, n = [], 0
    for r, group in enumerate(groups.values(), 1):
        rows = group["rows"]
        if graph:
            attributes, conflicts = merge_cells(_edge_spec(shape, rows[0]).get("attributes", []),
                                                [row["attributes"] for row in rows])
            fields: dict[str, Any] = {**{k: rows[0][k] for k in EDGE_FIELDS}, "attributes": attributes}
        else:
            cells, conflicts = merge_cells(shape["columns"], [row["cells"] for row in rows])
            fields = {"cells": cells}
        kept = fields["attributes"] if graph else fields["cells"]
        for name, values in conflicts.items():
            problems.append(f"row r{r}: {name} is {values!r} in different candidates; kept {kept[name]!r}")
        row_facts = []
        for fact in group["facts"].values():
            n += 1
            o = fact["o"] if isinstance(fact["o"], (str, int, float, bool)) else json.dumps(fact["o"])
            row_facts.append({"id": f"f{n}", "s": str(fact["s"]), "p": str(fact["p"]), "o": o, "claims": [],
                              "origin": "research", "paper_id": fact.get("paper_id"), "quote": fact.get("quote"),
                              "vital": bool(fact["vital"]), "candidate_id": fact.get("candidate_id")})
        out.append({"id": f"r{r}", **fields, "facts": row_facts})
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


def rows_sha256(rows: list[dict[str, Any]]) -> str:
    return sha256_hex(canonical_bytes(rows))


def git_commit() -> str | None:
    try:
        return git_head(review.REPO)
    except (OSError, subprocess.CalledProcessError):
        return None


def inputs(root: Path, qid: str) -> dict[str, Any]:
    """What a key was built from: D's build, the sha256 of C1's files and of the pulled reviews, the code."""
    folder = review.qdir(root, qid)

    def sha(path: Path) -> str | None:
        return file_sha256(path) if path.is_file() else None

    doc = review.read_json(folder / "doc.json") or {}
    return {"doc_built": doc.get("built"), "doc_concept_sha256": doc.get("concept_sha256"),
            "files": {name: sha(folder / name) for name in INPUT_FILES},
            "reviews": {f"{review.REVIEW_DIR}/{d}.jsonl": sha(folder / review.REVIEW_DIR / f"{d}.jsonl")
                        for d in review.QUESTION_DATASETS},
            "git_commit": git_commit()}


def checks(root: Path, qid: str, pulled: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """The passes besides the fact records: the missing-facts record marked done, the screening sample checked."""
    from . import screening_check  # it imports gold/agreement.py, which imports this module

    missing_done = any(answer.get("done") == "yes" for record in pulled["missing"]
                       for answer in review.submitted(record).values())
    drawn = screening_check.load_sample(root, qid)
    papers = {str(p) for p in (drawn or {}).get("papers", [])}
    checked = {str((r.get("metadata") or {}).get("paper_id")) for r in pulled["screening"]
               if screening_check.verdicts(r)} & papers
    return {"missing_done": missing_done, "screening_sampled": len(papers), "screening_checked": len(checked)}


@dataclass
class Export:
    qid: str
    key: dict[str, Any] | None
    report: dict[str, Any]
    problems: list[str]


def _set_aside(folder: Path) -> str | None:
    """Move a key.json the current review no longer gives to key.stale.json; its new path, if any."""
    key = folder / KEY_FILE
    if not key.is_file():
        return None
    return str(key.replace(folder / STALE_KEY_FILE))


def export(root: Path, qid: str, *, corpus: review.Corpus, concepts: Path | None,
           adjudicator: str | None = None, write: bool = True) -> Export:
    """Decide every pulled record of one question and build its key; write export.json, and key.json
    only when the key validates for the picked concept (else an older key.json is set aside)."""
    concept = review.concept(concepts, qid)
    if concept is None:
        return Export(qid, None, {}, [f"{qid}: no concept.json under {concepts}; nothing exported"])
    current = review.current_records(root, qid)
    by_candidate = {item["id"]: item for item in current.values()}
    pulled = review.reviews(root, qid)
    decided = decide(current, pulled["review"] + pulled["overlap"], adjudicator)
    added, rejected = added_facts(pulled["missing"] + pulled["screening"], corpus)
    pairs: list[tuple[dict[str, Any] | None, dict[str, Any]]] = []
    unanchored: list[dict[str, Any]] = []
    repeated: list[dict[str, Any]] = []
    for d in sorted(decided.decisions, key=lambda d: d.candidate_id):
        if not (d.keep and d.fact):
            continue
        item = by_candidate[d.candidate_id]
        try:
            found = corpus.locate(item)
        except (review.Rejected, anchor.AnchorError) as exc:
            unanchored.append({"candidate_id": d.candidate_id, "file": item.get("file"), "reason": exc.reason,
                               "anchor_status": item.get("anchor_status")})
            continue
        if found.occurrences > 1:
            repeated.append({"candidate_id": d.candidate_id, "occurrences": found.occurrences, "chosen": found.how})
        pairs.append((substitute(item.get("row"), item, d.fact),
                      {**d.fact, "paper_id": item.get("paper_id") or corpus.paper_id(found.file),
                       "quote": found.exact, "vital": d.vital, "candidate_id": d.candidate_id}))
    pairs += [(None, {"s": a["s"], "p": a["p"], "o": a["o"], "paper_id": a["paper_id"], "quote": a["quote"],
                      "vital": False, "candidate_id": None}) for a in added]
    rows, merged, problems = merge_rows(concept, pairs)
    problems = decided.problems + problems
    if unanchored:
        problems.append(f"{len(unanchored)} kept candidate(s) left out: their quote is not in their file "
                        "(export.json `unanchored`)")
    sha = concept_hash(concept)
    doc = review.read_json(review.qdir(root, qid) / "doc.json") or {}
    stale = bool(doc.get("concept_sha256")) and doc["concept_sha256"] != sha
    if stale:
        problems.append(f"{qid}: D was built for concept {doc['concept_sha256'][:12]}, the picked concept is "
                        f"{sha[:12]}; rebuild D before exporting")
    unresolved = sum(1 for d in decided.disagreements if "resolved_by" not in d)
    passes = checks(root, qid, pulled)
    counts = {"records": len(current), "decided": len(decided.decisions),
              "kept": sum(d.keep for d in decided.decisions), "dropped": sum(not d.keep for d in decided.decisions),
              "unsure": len({u["candidate_id"] for u in decided.unsure}), "unreviewed": len(decided.unreviewed),
              "disagreements": len(decided.disagreements), "unresolved": unresolved,
              "adjudicated": decided.adjudicated, "adjudicated_by_a_rater": decided.adjudicated_by_a_rater,
              "stale": len(decided.stale), "unanchored": len(unanchored),
              "added": len(added), "added_rejected": len(rejected), **passes,
              "facts": sum(len(r["facts"]) for r in rows), "rows": len(rows)}
    complete = (not decided.unreviewed and not unresolved and passes["missing_done"]
                and passes["screening_checked"] == passes["screening_sampled"])
    reviewers = sorted({u for d in decided.decisions for u in d.reviewers}
                       | {a["user"] for a in added})
    exported_at = review.utc_now()
    built_from = inputs(root, qid)
    key = {"qid": qid, "concept_sha256": sha, "kind": concept["answer_shape"]["kind"], "version": VERSION,
           "reviewed": True, "rows": rows,
           "notes": (f"Answer key of D reviewed in Argilla by {', '.join(reviewers) or 'nobody yet'}: "
                     f"{counts['kept']} of {counts['records']} candidate facts kept, {counts['added']} added "
                     "by reviewers. Details in export.json."),
           "key_sha256": rows_sha256(rows),
           "review": {"exported_at": exported_at, "reviewers": reviewers, "adjudicator": adjudicator,
                      **counts, "complete": complete, "inputs": built_from}}
    invalid = validate_key(key, concept)
    problems += invalid
    if decided.adjudicated_by_a_rater:
        problems.append(f"{qid}: {decided.adjudicated_by_a_rater} disagreement(s) settled by {adjudicator}, "
                        "one of the two raters: their own answer won (prefer a third person)")
    ok = not invalid and not stale
    report = {"qid": qid, "exported_at": exported_at, "status": "ok" if ok else "failed", "key_written": ok and write,
              "key_sha256": key["key_sha256"] if ok else None, "adjudicator": adjudicator, "counts": counts,
              "complete": complete, "inputs": built_from,
              "decisions": [asdict(d) for d in decided.decisions], "disagreements": decided.disagreements,
              "unsure": decided.unsure, "unreviewed": decided.unreviewed, "stale": decided.stale,
              "unanchored": unanchored, "repeated_quotes": repeated, "added": added, "rejected": rejected,
              "merged": merged, "problems": problems}
    if write:
        folder = review.qdir(root, qid)
        if ok:
            review.write_json(folder / KEY_FILE, key)
        elif (moved := _set_aside(folder)) is not None:
            report["stale_key"] = moved
            problems.append(f"{qid}: the earlier key.json no longer holds; moved to {STALE_KEY_FILE}")
        review.write_json(folder / EXPORT_FILE, report)
    return Export(qid, key if ok else None, report, problems)
