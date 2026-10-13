"""Triage (M3, plan "Gold": triage.jsonl): a model sorts every candidate into answers / context / irrelevant.

Ported from the labelling repo (src/labelling/triage.py, prompts/triage.md -> gold/prompts/triage-v1.md).
Reviewing every fact of D does not scale, so review is stratified (gold/pool.py): people review every
candidate triage put in `answers` or `context` plus a seeded sample of the `irrelevant` ones, and the
sample measures what triage missed (C2's report). The labels only order the review: they are never
gold and reviewers do not see them. The one exception is `gold draft`, a stand-in key from the labels
alone, marked as a draft.

What changed from the labelling repo: the model judges against the picked concept (title, definition,
measure, scope, answer shape) where the labelling repo gave an interpretation's label and gloss, and
each fact comes with the answer row it was extracted for, its quote and the passage around the quote
(CONTEXT_CHARS of the file on each side; the quote alone when it has no anchor). Calls go through
gold/calls.py like the build's (sub-model rotation, cache.jsonl, GOLD_CONCURRENCY, per-call timeout).

Candidates are sent in batches (`--batch`, default 20); a reply's labels are kept only for ids of its
batch. Labels are appended to triage.jsonl as batches finish ({id, label, model, served_model,
prompt_sha256}), so a stopped run keeps what it sorted; a rerun sorts only candidates without a label,
which retries failed batches. The last line for an id wins.
"""
from __future__ import annotations

import asyncio
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from . import llm
from .build import BuildSettings, QuestionDir, load_doc, read_jsonl
from .calls import Caller, CallError, PromptFile, load_prompt
from .chunks import GoldCorpus

LABELS = ("answers", "context", "irrelevant")
BATCH = 20
CONTEXT_CHARS = 300
MAX_TOKENS = 4096


class Label(BaseModel):
    id: str
    label: Literal["answers", "context", "irrelevant"]


class Labels(BaseModel):
    labels: list[Label]


PROMPT: PromptFile = load_prompt("triage-v1.md", Labels)


def load_labels(qdir: QuestionDir) -> dict[str, str]:
    """candidate id -> label from triage.jsonl (the last line for an id wins)."""
    return {row["id"]: row["label"] for row in read_jsonl(qdir.triage)}


class Texts:
    """Paper texts for passages, read once each (None when a file cannot be read or fails its hash)."""

    def __init__(self, corpus: GoldCorpus | None) -> None:
        self.corpus = corpus
        self._texts: dict[str, str | None] = {}

    def get(self, paper_id: str) -> str | None:
        if paper_id not in self._texts:
            try:
                self._texts[paper_id] = self.corpus.text(paper_id) if self.corpus else None
            except Exception:  # noqa: BLE001 - a passage is context; the quote alone still works
                self._texts[paper_id] = None
        return self._texts[paper_id]


def passage(texts: Texts, candidate: dict[str, Any], chars: int = CONTEXT_CHARS) -> str:
    anchor = candidate.get("anchor")
    text = texts.get(candidate["paper_id"]) if anchor else None
    if not text:
        return str(candidate["quote"])
    return text[max(0, anchor["start"] - chars):anchor["end"] + chars]


def concept_brief(concept: dict[str, Any]) -> dict[str, Any]:
    return {k: concept[k] for k in ("title", "definition", "measure", "scope", "answer_shape") if k in concept}


def batch_prompt(doc: dict[str, Any], batch: list[dict[str, Any]], texts: Texts) -> str:
    return json.dumps({
        "question": doc.get("question") or "",
        "concept": concept_brief(doc["concept"]),
        "facts": [{"id": c["id"], "subject": c["s"], "relation": c["p"], "object": c["o"], "row": c["row"],
                   "paper": c["paper_id"], "quote": c["quote"], "passage": passage(texts, c)} for c in batch],
    }, ensure_ascii=False, indent=1)


async def _triage(qdir: QuestionDir, texts: Texts, rotation: llm.Rotation, settings: BuildSettings, batch: int,
                  log: Callable[[str], None]) -> Counter[str]:
    doc = load_doc(qdir)
    candidates = read_jsonl(qdir.candidates)
    known = load_labels(qdir)
    todo = [c for c in candidates if c["id"] not in known]
    batches = [todo[i:i + batch] for i in range(0, len(todo), max(1, batch))]
    log(f"{qdir.qid}: {len(todo)} candidates to sort ({len(candidates) - len(todo)} already sorted), "
        f"{len(batches)} calls")
    caller = Caller(rotation, llm.JsonlCache(qdir.cache), concurrency=settings.concurrency,
                    timeout_s=settings.call_timeout_s, temperature=settings.temperature, seed=settings.seed)
    qdir.root.mkdir(parents=True, exist_ok=True)

    async def one(items: list[dict[str, Any]]) -> None:
        try:
            result = await caller.call("triage", PROMPT, Labels, batch_prompt(doc, items, texts), max_tokens=MAX_TOKENS)
        except CallError as exc:
            log(f"{qdir.qid}: a batch of {len(items)} failed ({exc.reason}); run triage again to retry it")
            return
        wanted = {c["id"] for c in items}
        lines = {}
        for item in result.output.labels:
            if item.id in wanted and item.id not in lines:
                lines[item.id] = {"id": item.id, "label": item.label, "model": result.meta["model"],
                                  "served_model": result.meta["served_model"], "prompt_sha256": PROMPT.sha256}
        with qdir.triage.open("a", encoding="utf-8", newline="\n") as fh:
            fh.writelines(json.dumps(line, sort_keys=True) + "\n" for line in lines.values())
        known.update({i: line["label"] for i, line in lines.items()})

    await asyncio.gather(*(one(items) for items in batches))
    counts = Counter(known[c["id"]] for c in candidates if c["id"] in known)
    counts["unsorted"] = sum(c["id"] not in known for c in candidates)
    log(f"{qdir.qid}: " + ", ".join(f"{label} {counts.get(label, 0)}" for label in LABELS)
        + (f", unsorted {counts['unsorted']} (run triage again)" if counts["unsorted"] else "")
        + f" · calls {caller.counters.made} (cached {caller.counters.cached}, failed {caller.counters.failed})")
    return counts


def triage(qid: str, out_root: Path, corpus: GoldCorpus | None, rotation: llm.Rotation, *,
           settings: BuildSettings | None = None, batch: int = BATCH,
           log: Callable[[str], None] = print) -> dict[str, int]:
    """Label every candidate of $GOLD/<qid>/ that has no label yet; returns the label counts (and unsorted)."""
    counts = asyncio.run(_triage(QuestionDir(Path(out_root) / qid), Texts(corpus), rotation,
                                 settings or BuildSettings.from_env(), batch, log))
    return {label: counts.get(label, 0) for label in (*LABELS, "unsorted")}
