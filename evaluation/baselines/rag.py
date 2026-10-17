"""The answer-level baseline: a plain retrieve-then-answer system (the supervisor's baseline, STATE.md §1 §7).

1. Every paper (SystemCorpus: manifest.json and papers/ only) is cut into passages at Markdown
   headings and paragraph breaks (gold/chunks.split) of at most `max_chars` characters.
2. BM25 (rank_bm25.BM25Okapi over all passages of the corpus, lower-cased word tokens) scores every
   passage against the question. Two modes:
   - `global` (default, k = 8; the standard RAG setup): the top k passages of the whole corpus; on a
     corpus of 20 papers the model then sees only some papers, mostly their abstracts.
   - `per_paper` (k = 2; "every paper seen"): the top k passages of EVERY paper, so the model sees each
     study and the per-study comparison (C) is not capped by retrieval; papers in id order.
   Ties are broken by paper id and offset, so retrieval is deterministic. The mode and k are recorded
   in answer.json (`settings`).
3. One schema-constrained call (CitedAnswer: the answer text and the passages it cites; temperature 0,
   fixed seed) answers from those passages alone, under a neutral prompt (INSTRUCTIONS): no label, no
   per-paper stance, no rules. A citation that is not one of the retrieved passages is dropped into
   `dropped_citations`. The call is cached (gold.llm.JsonlCache) by prompt hash, model and the exact
   user prompt, so a rerun costs nothing and gives the same answer.json.
4. The mapping call shared with the agent baseline (common.map_answer) turns the answer (its text and
   the cited passages) into the label and per-paper stances the synthesis score (C) compares; an empty
   answer is `insufficient` without a call.

answer.json has `system: rag-baseline`, the A4 shape from the mapping (`label`, `counts`, `studies`,
groups, `label_by_rule`), `answer_text` (the model's own answer), `citations` and `retrieved`
(`[{document, start, end(, score)}]`, raw character offsets into the paper text as agent/anchor.read_text
and the placements use), `settings`, `model_call` and `mapping_call`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai.models import Model
from rank_bm25 import BM25Okapi

from gold.chunks import split
from gold.llm import JsonlCache

from .common import DEFAULT_QUESTION, AnswerReply, SystemCorpus, answer_json, cached_reply, map_answer

SYSTEM = "rag-baseline"
MODES = ("global", "per_paper")
DEFAULT_MODE = "global"
K = {"global": 8, "per_paper": 2}  # default k per mode
MAX_CHARS = 1_500
TOKEN = re.compile(r"\w+")

INSTRUCTIONS = ("Answer the question using only the passages below. Say what the evidence shows and cite the passages "
                "you rely on as [paper id, start-end].")


class Citation(BaseModel):
    document: str = Field(description="the paper id of the cited passage, as in its header")
    start: int = Field(description="the start offset of the cited passage, as in its header")
    end: int = Field(description="the end offset of the cited passage, as in its header")


class CitedAnswer(BaseModel):
    """The answering call's schema: the answer and the passages it rests on."""
    answer_text: str = Field(description="the answer, citing passages as [paper id, start-end]")
    citations: list[Citation] = Field(description="the passages the answer relies on, from those given")


@dataclass(frozen=True)
class Passage:
    document: str
    start: int
    end: int
    text: str


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def passages(corpus: SystemCorpus, max_chars: int = MAX_CHARS) -> list[Passage]:
    return [Passage(p.id, a, b, p.text[a:b]) for p in corpus.papers for a, b, _ in split(p.text, max_chars)
            if p.text[a:b].strip()]


def retrieve(chunks: list[Passage], question: str, k: int | None = None, mode: str = DEFAULT_MODE
             ) -> list[tuple[Passage, float]]:
    """The passages the model sees, with their BM25 scores (see the module docstring for the modes)."""
    if mode not in MODES:
        raise ValueError(f"retrieval mode must be one of {MODES}")
    k = K[mode] if k is None else k
    if not chunks:
        return []
    scores = BM25Okapi([tokens(c.text) or ["\0"] for c in chunks]).get_scores(tokens(question))
    ranked = sorted(zip(chunks, (float(s) for s in scores)), key=lambda cs: (-cs[1], cs[0].document, cs[0].start))
    if mode == "global":
        return ranked[:k]
    per: dict[str, list[tuple[Passage, float]]] = {}
    for passage, score in ranked:
        per.setdefault(passage.document, []).append((passage, score))
    return [hit for document in sorted(per) for hit in per[document][:k]]


def header(p: Passage | Citation) -> str:
    return f"[{p.document}, {p.start}-{p.end}]"


def user_prompt(question: str, hits: list[tuple[Passage, float]]) -> str:
    body = "\n\n".join(f"{header(p)}\n{p.text.strip()}" for p, _ in hits)
    return f"Question: {question}\n\nPassages:\n\n{body}"


def keep_citations(citations: list[Citation], hits: list[tuple[Passage, float]]
                   ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(kept, dropped): a citation is kept when it names a retrieved passage exactly (document, start, end);
    a passage cited twice is kept once, in citation order."""
    known = {(p.document, p.start, p.end) for p, _ in hits}
    kept, dropped, seen = [], [], set()
    for c in citations:
        key = (c.document, c.start, c.end)
        entry = {"document": c.document, "start": c.start, "end": c.end}
        if key not in known:
            dropped.append(entry)
        elif key not in seen:
            seen.add(key)
            kept.append(entry)
    return kept, dropped


def mapping_text(answer: CitedAnswer, kept: list[dict[str, Any]], hits: list[tuple[Passage, float]]) -> str:
    """What the mapping call reads: the answer text and the kept citations with their passage text."""
    text = {(p.document, p.start, p.end): p.text.strip() for p, _ in hits}
    lines = [answer.answer_text.strip()]
    if kept:
        lines.append("\nCited passages:")
        lines += [f"[{c['document']}, {c['start']}-{c['end']}]\n{text[(c['document'], c['start'], c['end'])]}"
                  for c in kept]
    return "\n".join(lines)


def rag_baseline(corpus_dir: Path, *, model: Model, question: str = DEFAULT_QUESTION, k: int | None = None,
                 mode: str = DEFAULT_MODE, max_chars: int = MAX_CHARS, cache: JsonlCache | None = None,
                 model_id: str | None = None, seed: int = 0) -> dict[str, Any]:
    """answer.json of the RAG baseline for one corpus (`mode` global or per_paper; k defaults per mode)."""
    corpus = SystemCorpus(corpus_dir)
    hits = retrieve(passages(corpus, max_chars), question, k, mode)
    k = K[mode] if k is None else k
    answer, call = cached_reply(cache, INSTRUCTIONS, user_prompt(question, hits), model=model, model_id=model_id,
                                seed=seed, output_type=CitedAnswer)
    call.pop("cached")  # so a cached rerun writes the same bytes
    citations, dropped = keep_citations(answer.citations, hits)
    if not answer.answer_text.strip():
        reply, mapping = AnswerReply(label="insufficient", studies=[], answer_text="(no answer)"), None
    else:
        reply, mapping = map_answer(cache, question, corpus.ids, mapping_text(answer, citations, hits), model=model,
                                    model_id=model_id, seed=seed)
    retrieved = [{"document": p.document, "start": p.start, "end": p.end, "score": round(s, 6)} for p, s in hits]
    return answer_json(SYSTEM, question, reply, corpus.ids, answer_text=answer.answer_text, citations=citations,
                       dropped_citations=dropped, retrieved=retrieved, corpus_id=corpus.corpus_id,
                       settings={"retrieval": mode, "k": k, "max_chars": max_chars, "retriever": "bm25okapi"},
                       model_call=call, mapping_call=mapping, mapped_answer_text=reply.answer_text)
