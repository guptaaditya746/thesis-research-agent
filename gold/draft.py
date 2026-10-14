"""Draft answer key (M3, plan "Gold": key.draft.json) from triage alone, before people review D.

Ported from the labelling repo's `draft_rows`: every candidate triage put in `answers` or `context`
is kept as if a reviewer had accepted it, so scoring (D) and the web app (E) can run end to end
before the review. Here it must also have passed the quote check (`anchor_status` ok): a fact whose
quote failed is not evidence. Nothing checks that a kept fact is correct; the key says so
(`version` v1-draft, `reviewed` false, `notes`), and C2's reviewed key.json replaces it.

The key has the agent's answer shape so scoring compares like with like. Kept candidates are merged
into rows by the build's rule (gold/build.py `merge_rows`); each row's facts are its candidates,
one fact per distinct (s, p, o) after normalisation (the others are listed under `merged_facts`), as
{id, s, p, o, claims, origin, paper_id, quote, vital, candidate_id}. `quote` is the anchored text
exactly as it stands in the file, `vital` is false (people mark vital facts in review). `claims` is
[] and `origin` "research" only so that a row, once the gold-only fields (GOLD_ONLY) are stripped,
is a valid answer row: the answer schema requires both, and gold facts are sourced by their quote
and candidate, not by broker claims. `validate_key` checks exactly that, with
agent.concept.validate_answer (schema from answer_schema_for(concept), concept hash, unique ids).
A graph candidate without a source or target cannot be a valid edge and is left out (counted).

A draft key from a partial D would understate recall without saying so, so `draft_key` refuses a
trial or a D with failed calls unless `allow_partial`, and refuses while candidates have no triage
label unless `allow_untriaged` (they would silently be missing from the key). Either way the key
records the D it was made from (`built.doc`: coverage, failures, trial settings, doc.json's sha256),
`built.partial`, the untriaged count and the git state, and `notes` says when it is partial.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.concept import concept_sha256, validate_answer
from agent.rundir import utc_now

from .build import (
    QuestionDir,
    doc_state,
    file_hash,
    git_state,
    incomplete,
    load_doc,
    merge_rows,
    norm,
    read_jsonl,
    write_json,
)
from .triage import load_labels

VERSION = "v1-draft"
TIERS = ("answers", "context")
GOLD_ONLY = ("paper_id", "quote", "vital", "candidate_id")
EDGE_FIELDS = ("source", "source_type", "predicate", "target", "target_type")


def strip_gold(row: dict[str, Any]) -> dict[str, Any]:
    """A key row as an answer row: the gold-only fact fields removed."""
    return {**row, "facts": [{k: v for k, v in f.items() if k not in GOLD_ONLY} for f in row["facts"]]}


def answer_view(key: dict[str, Any]) -> dict[str, Any]:
    """The key as an answer document (agent/schemas/answer.schema.json): what scoring compares runs with."""
    return {"concept_sha256": key["concept_sha256"], "kind": key["kind"],
            "rows": [strip_gold(r) for r in key["rows"]]}


def validate_key(key: dict[str, Any], concept: dict[str, Any]) -> list[str]:
    """Problems with a draft or reviewed key: its rows as an answer for `concept`, and the gold fields."""
    problems = validate_answer(answer_view(key), concept)
    for row in key["rows"]:
        for fact in row["facts"]:
            missing = [k for k in GOLD_ONLY if k not in fact]
            if missing:
                problems.append(f"{row['id']}/{fact['id']}: missing {missing}")
    return problems


def _row(concept: dict[str, Any], n: int, merged: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any]:
    if concept["answer_shape"]["kind"] == "table":
        return {"id": f"r{n}", "cells": merged["cells"], "facts": facts}
    cells = merged["cells"]
    return {"id": f"r{n}", **{k: cells[k] for k in EDGE_FIELDS}, "attributes": cells["attributes"], "facts": facts}


def draft_key(qid: str, out_root: Path, *, tiers: tuple[str, ...] = TIERS, allow_partial: bool = False,
              allow_untriaged: bool = False) -> dict[str, Any]:
    """Write key.draft.json for one question from doc.json, candidates.jsonl and triage.jsonl; return it."""
    qdir = QuestionDir(Path(out_root) / qid)
    doc = load_doc(qdir)
    concept = doc["concept"]
    state = doc_state(doc)
    why = incomplete(state)
    if why and not allow_partial:
        raise ValueError(f"{qid}: D is not complete ({why}); finish `gold build {qid}` first, or pass "
                         "--allow-partial for a draft key that says it is partial")
    candidates = read_jsonl(qdir.candidates)
    labels = load_labels(qdir, doc["concept_sha256"])
    if candidates and not labels:
        raise ValueError(f"{qid}: no triage labels; run `gold triage {qid}` first")
    untriaged = sum(c["id"] not in labels for c in candidates)
    if untriaged and not allow_untriaged:
        raise ValueError(f"{qid}: {untriaged} candidates have no triage label; run `gold triage {qid}` again, or "
                         "pass --allow-untriaged to leave them out of the draft key (recorded in it)")
    graph = concept["answer_shape"]["kind"] == "graph"
    kept, skipped = [], {"untriaged": 0, "other_tiers": 0, "unanchored": 0, "incomplete_edge": 0}
    for c in candidates:
        label = labels.get(c["id"])
        if label is None:
            skipped["untriaged"] += 1
        elif label not in tiers:
            skipped["other_tiers"] += 1
        elif c["anchor_status"] != "ok":
            skipped["unanchored"] += 1
        elif graph and (c["row"].get("source") is None or c["row"].get("target") is None):
            skipped["incomplete_edge"] += 1
        else:
            kept.append(c)
    by_id = {c["id"]: c for c in kept}
    rows, merged_facts, fact_no = [], {}, 0
    for merged in merge_rows(concept, kept):
        facts: dict[tuple[str, str, str], dict[str, Any]] = {}
        for cid in merged["candidates"]:
            c = by_id[cid]
            spo = (norm(c["s"]), norm(c["p"]), norm(c["o"]))
            if spo in facts:
                merged_facts.setdefault(facts[spo]["id"], []).append(cid)
                continue
            fact_no += 1
            facts[spo] = {"id": f"f{fact_no}", "s": c["s"], "p": c["p"], "o": c["o"], "claims": [],
                          "origin": "research", "paper_id": c["paper_id"], "quote": c["anchor"]["exact"],
                          "vital": False, "candidate_id": cid}
        rows.append(_row(concept, len(rows) + 1, merged, list(facts.values())))
    notes = ("DRAFT: rows from model triage alone (labels " + ", ".join(tiers) + ", quotes that passed the "
             "check), not reviewed by people; scores against it are provisional. The reviewed key.json "
             "replaces it.")
    if why:
        notes += f" PARTIAL: made from an incomplete D ({why}); recall against it is understated."
    if untriaged:
        notes += f" {untriaged} candidates had no triage label and are left out."
    git = git_state(log=None)
    key = {
        "qid": qid, "concept_sha256": concept_sha256(concept), "kind": concept["answer_shape"]["kind"],
        "version": VERSION, "reviewed": False, "rows": rows,
        "notes": notes,
        "merged_facts": merged_facts,
        "counts": {"candidates": len(candidates), "kept": len(kept), "rows": len(rows), "facts": fact_no,
                   "skipped": skipped},
        "built": {"tiers": list(tiers), "created_at": utc_now(), "git_commit": git["commit"], "git": git,
                  "partial": bool(why), "partial_reason": why, "untriaged": untriaged,
                  "doc": {**state, "sha256": file_hash(qdir.doc)},
                  "doc_concept_sha256": doc["concept_sha256"], "candidates_sha256": file_hash(qdir.candidates),
                  "triage_sha256": file_hash(qdir.triage)},
    }
    problems = validate_key(key, concept)
    if problems:
        raise ValueError(f"{qid}: the draft key does not validate: {problems[:10]}")
    write_json(qdir.draft, key)
    return key
