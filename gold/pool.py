"""Review pool (M3, plan "Gold": pool.jsonl, pool.strata.json): the records people review in Argilla.

Ported from the labelling repo's `stratify` (src/labelling/triage.py): every candidate triage put in
the reviewed tiers (`answers`, `context`), every candidate triage has not sorted (reviewed in full),
and a seeded random sample (`--sample`, default 50, fixed by `--seed`) of the rest (`irrelevant`).
The sample is the `sample_size` candidates ranked first by sha256("<seed>:<qid>:<id>"), so the same
seed and candidates give the same sample on any machine and Python version. Records are shuffled the
same way (sha256("<seed>:<qid>:order:<id>")) so sampled records do not sit together, and they carry
neither the triage label nor the stratum: reviewers judge each fact against its passage blind.
pool.strata.json keeps what the export needs to estimate what triage missed (C2): the label counts,
the size of the rest, how many were sampled, and which ids are in which stratum.

A record shows the fact (s, p, o, the answer row), its quote and anchor status, and the passage:
for an anchored quote PASSAGE_CHARS of the file on each side with the quote's span as `highlight`
(offsets into `passage.text`); for a quote that failed the check, the whole chunk it was extracted
from, without highlight, so a reviewer can still find (or not find) the fact.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from agent.rundir import utc_now

from .build import QuestionDir, file_hash, load_doc, read_jsonl, write_json, write_jsonl
from .chunks import GoldCorpus
from .triage import Texts, load_labels

TIERS = ("answers", "context")
SAMPLE = 50
PASSAGE_CHARS = 1500


def _rank(seed: str, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def sample_ids(ids: Iterable[str], size: int, seed: str) -> set[str]:
    """A deterministic random sample: the same seed and ids give the same sample."""
    return set(sorted(ids, key=lambda value: _rank(seed, value))[:max(0, size)])


def record_passage(texts: Texts, chunks: dict[tuple[str, int], dict[str, Any]], c: dict[str, Any],
                   chars: int = PASSAGE_CHARS) -> dict[str, Any] | None:
    text = texts.get(c["paper_id"])
    if text is None:
        return None
    if c.get("anchor"):
        start, end = max(0, c["anchor"]["start"] - chars), min(len(text), c["anchor"]["end"] + chars)
        return {"text": text[start:end], "start": start, "end": end,
                "highlight": {"start": c["anchor"]["start"] - start, "end": c["anchor"]["end"] - start}}
    chunk = chunks.get((c["paper_id"], c["chunk"]))
    if chunk is None:
        return None
    return {"text": text[chunk["start"]:chunk["end"]], "start": chunk["start"], "end": chunk["end"], "highlight": None}


def record(doc: dict[str, Any], c: dict[str, Any], passage: dict[str, Any] | None) -> dict[str, Any]:
    """One review record: the fact and its evidence, never its triage label or stratum."""
    concept = doc["concept"]
    return {"id": c["id"], "qid": doc["qid"], "question": doc.get("question"),
            "concept": {"title": concept["title"], "definition": concept["definition"]},
            "paper_id": c["paper_id"], "file": c["file"], "row": c["row"], "s": c["s"], "p": c["p"], "o": c["o"],
            "quote": c["quote"], "anchor_status": c["anchor_status"], "anchor": c.get("anchor"), "passage": passage}


def build_pool(qid: str, out_root: Path, corpus: GoldCorpus | None, *, sample: int = SAMPLE, seed: int | str = 0,
               tiers: Iterable[str] = TIERS) -> dict[str, Any]:
    """Write pool.jsonl and pool.strata.json for one question; returns the strata."""
    qdir = QuestionDir(Path(out_root) / qid)
    doc = load_doc(qdir)
    candidates = read_jsonl(qdir.candidates)
    labels = load_labels(qdir)
    tiers = tuple(tiers)
    reviewed = [c for c in candidates if labels.get(c["id"]) in tiers or c["id"] not in labels]
    rest = [c for c in candidates if c["id"] in labels and labels[c["id"]] not in tiers]
    picked = sample_ids((c["id"] for c in rest), sample, f"{seed}:{qid}")
    chosen = reviewed + [c for c in rest if c["id"] in picked]
    chosen.sort(key=lambda c: _rank(f"{seed}:{qid}:order", c["id"]))
    texts = Texts(corpus)
    chunks = {(r["paper_id"], r["chunk"]): r for r in read_jsonl(qdir.chunks)}
    write_jsonl(qdir.pool, (record(doc, c, record_passage(texts, chunks, c)) for c in chosen))
    strata = {
        "qid": qid, "seed": seed, "sample": sample, "tiers": list(tiers),
        "labels": dict(sorted(Counter(labels[c["id"]] for c in candidates if c["id"] in labels).items())),
        "candidates": len(candidates), "unsorted": sum(c["id"] not in labels for c in candidates),
        "reviewed_tiers": len(reviewed), "rest": len(rest), "sampled": len(picked), "records": len(chosen),
        "strata": {"triaged": [c["id"] for c in reviewed], "sample": sorted(picked)},
        "candidates_sha256": file_hash(qdir.candidates), "triage_sha256": file_hash(qdir.triage),
        "created_at": utc_now(),
    }
    write_json(qdir.strata, strata)
    return strata
