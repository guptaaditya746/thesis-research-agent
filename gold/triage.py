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
batch, and a reply that labels none of them counts as a failed call and is not cached (else the same
batch would hit the same useless reply on every rerun). Labels are appended to triage.jsonl as
batches finish ({id, label, model, served_model, prompt_sha256, concept_sha256}), so a stopped run
keeps what it sorted; a rerun sorts only candidates without a label, which retries failed batches.
The last line for an id wins.

A label holds only for the concept and the prompt it was given under: `load_labels` ignores lines
whose concept_sha256 is not doc.json's or whose prompt_sha256 is not this triage prompt's, so a D
rebuilt for another concept, or a new triage prompt, is triaged again rather than reusing labels.
(Candidate ids already differ between concepts, gold/build.py IdRegistry; this is the second lock.)
triage.json lists every triage run with what shaped its labels: batch size, passage size, sampling,
models, the corpus manifest and whether passages were shown. The CLI needs the corpus; without one
(library use) a fact is shown with its quote alone, and triage.json says so.
"""
from __future__ import annotations

import asyncio
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from agent.rundir import utc_now

import modelcall
from .build import BuildSettings, QuestionDir, append_jsonl, load_doc, read_jsonl, write_json
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


def load_labels(qdir: QuestionDir, concept_hash: str | None = None) -> dict[str, str]:
    """candidate id -> label from triage.jsonl (the last line for an id wins), only lines given under
    `concept_hash` (default: doc.json's) and the current triage prompt."""
    if concept_hash is None:
        try:
            concept_hash = load_doc(qdir)["concept_sha256"]
        except (FileNotFoundError, ValueError, KeyError):
            return {}
    return {row["id"]: row["label"] for row in read_jsonl(qdir.triage)
            if row.get("concept_sha256") == concept_hash and row.get("prompt_sha256") == PROMPT.sha256}


class Texts:
    """Paper texts for passages, read once each with the corpus hash check (a file that fails it raises:
    the corpus is not the one D was built from). Without a corpus every text is None."""

    def __init__(self, corpus: GoldCorpus | None) -> None:
        self.corpus = corpus
        self._texts: dict[str, str | None] = {}

    def get(self, paper_id: str) -> str | None:
        if paper_id not in self._texts:
            self._texts[paper_id] = self.corpus.text(paper_id) if self.corpus else None
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


async def _triage(qdir: QuestionDir, texts: Texts, rotation: modelcall.Rotation, settings: BuildSettings, batch: int,
                  log: Callable[[str], None]) -> Counter[str]:
    doc = load_doc(qdir)
    concept_hash = doc["concept_sha256"]
    candidates = read_jsonl(qdir.candidates)
    known = load_labels(qdir, concept_hash)
    todo = [c for c in candidates if c["id"] not in known]
    batches = [todo[i:i + batch] for i in range(0, len(todo), max(1, batch))]
    log(f"{qdir.qid}: {len(todo)} candidates to sort ({len(candidates) - len(todo)} already sorted), "
        f"{len(batches)} calls" + ("" if texts.corpus else " (no corpus: facts shown with their quote only)"))
    caller = Caller(rotation, modelcall.JsonlCache(qdir.cache), concurrency=settings.concurrency,
                    timeout_s=settings.call_timeout_s, temperature=settings.temperature, seed=settings.seed)
    qdir.root.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()

    async def one(items: list[dict[str, Any]]) -> None:
        wanted = {c["id"] for c in items}

        def accept(output: Labels) -> str | None:
            return None if any(item.id in wanted for item in output.labels) else "no label for any id of the batch"

        try:
            result = await caller.call("triage", PROMPT, Labels, batch_prompt(doc, items, texts), max_tokens=MAX_TOKENS,
                                       accept=accept)
        except CallError as exc:
            log(f"{qdir.qid}: a batch of {len(items)} failed ({exc.reason}); run triage again to retry it")
            return
        lines = {}
        for item in result.output.labels:
            if item.id in wanted and item.id not in lines:
                lines[item.id] = {"id": item.id, "label": item.label, "model": result.meta["model"],
                                  "served_model": result.meta["served_model"], "prompt_sha256": PROMPT.sha256,
                                  "concept_sha256": concept_hash}
        append_jsonl(qdir.triage, lines.values())
        known.update({i: line["label"] for i, line in lines.items()})

    await asyncio.gather(*(one(items) for items in batches))
    counts = Counter(known[c["id"]] for c in candidates if c["id"] in known)
    counts["unsorted"] = sum(c["id"] not in known for c in candidates)
    _record_run(qdir, doc, texts, caller, batch, started_at, len(todo), counts)
    log(f"{qdir.qid}: " + ", ".join(f"{label} {counts.get(label, 0)}" for label in LABELS)
        + (f", unsorted {counts['unsorted']} (run triage again)" if counts["unsorted"] else "")
        + f" · calls {caller.counters.made} (cached {caller.counters.cached}, failed {caller.counters.failed})")
    return counts


def _record_run(qdir: QuestionDir, doc: dict[str, Any], texts: Texts, caller: Caller, batch: int, started_at: str,
                todo: int, counts: Counter[str]) -> None:
    """Append this run to triage.json: what shaped the labels it wrote."""
    try:
        runs = json.loads(qdir.triage_runs.read_text(encoding="utf-8")).get("runs", [])
    except (OSError, ValueError, AttributeError):
        runs = []
    corpus = texts.corpus
    runs.append({
        "started_at": started_at, "ended_at": utc_now(), "concept_sha256": doc["concept_sha256"],
        "prompt": PROMPT.json(), "batch": batch, "context_chars": CONTEXT_CHARS, "max_tokens": MAX_TOKENS,
        **caller.settings(), "models": [modelcall.model_name(m) for m in caller.rotation.models],
        "served": sorted(caller.served), "passages": corpus is not None,
        "corpus_manifest_sha256": corpus.manifest_sha256 if corpus else None,
        "to_sort": todo, "unsorted": counts["unsorted"], "model_calls": caller.counters.json(),
    })
    write_json(qdir.triage_runs, {"qid": qdir.qid, "runs": runs})


def triage(qid: str, out_root: Path, corpus: GoldCorpus | None, rotation: modelcall.Rotation, *,
           settings: BuildSettings | None = None, batch: int = BATCH,
           log: Callable[[str], None] = print) -> dict[str, int]:
    """Label every candidate of $GOLD/<qid>/ that has no label yet; returns the label counts (and unsorted)."""
    counts = asyncio.run(_triage(QuestionDir(Path(out_root) / qid), Texts(corpus), rotation,
                                 settings or BuildSettings.from_env(), batch, log))
    return {label: counts.get(label, 0) for label in (*LABELS, "unsorted")}
