"""The answer-level baseline: retrieve passages for the question, ask a model for the answer.

1. Every paper (SystemCorpus: manifest.json and papers/ only) is cut into passages at Markdown
   headings and paragraph breaks (gold/chunks.split) of at most `max_chars` characters.
2. BM25 (rank_bm25.BM25Okapi over all passages of the corpus, lower-cased word tokens) scores every
   passage against the question. Two modes:
   - `per_paper` (default, k = 2): the top k passages of EVERY paper, so the model sees each study
     and the per-study comparison (C) is not capped by retrieval; papers in id order.
   - `global` (the standard RAG setup, k = 8): the top k passages of the whole corpus; on a corpus of
     20 papers the model then sees only some papers, mostly their abstracts.
   Ties are broken by paper id and offset, so retrieval is deterministic. The mode and k are recorded
   in answer.json (`settings`).
3. One schema-constrained call (common.AnswerReply: label, per-paper stance, answer text; temperature
   0, fixed seed) answers from those passages alone. It is cached (gold.llm.JsonlCache) by prompt
   hash, model and the exact user prompt, so a rerun costs nothing and gives the same answer.json.

answer.json has `system: rag-baseline` and `retrieved: [{document, start, end, score}]`, raw character
offsets into the paper text (agent/anchor.read_text), as placements use.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_ai.models import Model
from rank_bm25 import BM25Okapi

from gold.chunks import split
from gold.llm import JsonlCache

from .common import DEFAULT_QUESTION, LABEL_RULES, SystemCorpus, answer_json, cached_reply

SYSTEM = "rag-baseline"
MODES = ("per_paper", "global")
K = {"per_paper": 2, "global": 8}  # default k per mode
MAX_CHARS = 1_500
TOKEN = re.compile(r"\w+")

INSTRUCTIONS = f"""You answer a research question using only the passages from scientific papers given below.
Each passage starts with [paper id, start-end]. Read the numbers the passages report and decide, for every
paper whose passages bear on the question, whether its evidence supports, contradicts or is neutral on the
question. Then give the overall label and a short answer. Cite papers only by the ids shown. If the passages
do not let you decide, say so with the label insufficient.

{LABEL_RULES}"""


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


def retrieve(chunks: list[Passage], question: str, k: int | None = None, mode: str = "per_paper"
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


def user_prompt(question: str, hits: list[tuple[Passage, float]]) -> str:
    body = "\n\n".join(f"[{p.document}, {p.start}-{p.end}]\n{p.text.strip()}" for p, _ in hits)
    return f"Question: {question}\n\nPassages:\n\n{body}"


def rag_baseline(corpus_dir: Path, *, model: Model, question: str = DEFAULT_QUESTION, k: int | None = None,
                 mode: str = "per_paper", max_chars: int = MAX_CHARS, cache: JsonlCache | None = None,
                 model_id: str | None = None, seed: int = 0) -> dict[str, Any]:
    """answer.json of the RAG baseline for one corpus (`mode` per_paper or global; k defaults per mode)."""
    corpus = SystemCorpus(corpus_dir)
    k = K.get(mode, 0) if k is None else k
    hits = retrieve(passages(corpus, max_chars), question, k, mode)
    reply, call = cached_reply(cache, INSTRUCTIONS, user_prompt(question, hits), model=model, model_id=model_id,
                               seed=seed)
    retrieved = [{"document": p.document, "start": p.start, "end": p.end, "score": round(s, 6)} for p, s in hits]
    call.pop("cached")  # so a cached rerun writes the same bytes
    return answer_json(SYSTEM, question, reply, corpus.ids, retrieved=retrieved, corpus_id=corpus.corpus_id,
                       settings={"retrieval": mode, "k": k, "max_chars": max_chars, "retriever": "bm25okapi"},
                       model_call=call)
