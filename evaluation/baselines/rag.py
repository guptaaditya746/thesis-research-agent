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
   `dropped_citations`. The call is cached (modelcall.JsonlCache) by prompt hash, model and the exact
   user prompt, so a rerun costs nothing and gives the same answer.json.
4. The mapping call shared with the agent baseline (common.map_answer) turns the answer (its text and
   the headers of its kept citations, not the passages' text) into the label and per-paper stances the
   synthesis score (C) compares; an empty answer is `insufficient` without a call.

Oracle passages (`oracle=True`, CLI `--oracle-passages`): a **diagnostic**, not a baseline. It breaks the
hard rule on purpose: step 2 is replaced by `oracle_passages`, which reads ground_truth.json and gives the
paragraphs (runs of text between blank lines) that hold each study's `value` placements, in paper and offset
order; steps 3 and 4 are unchanged. It separates retrieval failures from reasoning failures (`evaluate score
--oracle`); answer.json has `system: rag-oracle-passages`, `settings.retrieval: oracle_passages` and
`retrieved` without scores.

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
from modelcall import JsonlCache

from ..truth import GroundTruth
from .common import DEFAULT_QUESTION, AnswerReply, SystemCorpus, answer_json, cached_reply, map_answer

SYSTEM = "rag-baseline"
ORACLE_SYSTEM = "rag-oracle-passages"   # the diagnostic that reads ground_truth.json
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


def paragraph(text: str, start: int, end: int) -> tuple[int, int]:
    """The run of text between blank lines around [start, end)."""
    a = text.rfind("\n\n", 0, start)
    b = text.find("\n\n", end)
    return (0 if a < 0 else a + 2), (len(text) if b < 0 else b)


def oracle_passages(truth: GroundTruth, corpus_dir: Path) -> list[Passage]:
    """Diagnostic (reads ground_truth.json): the paragraphs holding each study's value placements, once each,
    in paper and offset order. Paper texts come from SystemCorpus, hash-checked like the baseline's."""
    texts = {p.id: p.text for p in SystemCorpus(corpus_dir).papers}
    found = {(p["paper"], *paragraph(texts[p["paper"]], p["start"], p["end"]))
             for p in truth.placements if p["role"] == "value" and p["paper"] in texts}
    return [Passage(doc, a, b, texts[doc][a:b]) for doc, a, b in sorted(found)]


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


def mapping_text(answer: CitedAnswer, kept: list[dict[str, Any]]) -> str:
    """What the mapping call reads: the answer text and the kept citations' headers ([paper id, start-end])
    only, never the passages' text, so the mapper cannot read the evidence a second time and assign a
    stance from numbers the answer never stated (the agent mapping likewise reads the agent's answer)."""
    lines = [answer.answer_text.strip()]
    if kept:
        lines.append("\nCited passages: " + ", ".join(f"[{c['document']}, {c['start']}-{c['end']}]" for c in kept))
    return "\n".join(lines)


def rag_baseline(corpus_dir: Path, *, model: Model, question: str = DEFAULT_QUESTION, k: int | None = None,
                 mode: str = DEFAULT_MODE, max_chars: int = MAX_CHARS, cache: JsonlCache | None = None,
                 model_id: str | None = None, seed: int = 0, oracle: bool = False) -> dict[str, Any]:
    """answer.json of the RAG baseline for one corpus (`mode` global or per_paper; k defaults per mode).
    `oracle`: the diagnostic on `oracle_passages` instead of BM25 (reads ground_truth.json)."""
    corpus = SystemCorpus(corpus_dir)
    if oracle:
        hits = [(p, 0.0) for p in oracle_passages(GroundTruth.load(Path(corpus_dir) / "ground_truth.json"), corpus_dir)]
        system, settings = ORACLE_SYSTEM, {"retrieval": "oracle_passages", "retriever": "ground_truth value placements"}
    else:
        hits = retrieve(passages(corpus, max_chars), question, k, mode)
        k = K[mode] if k is None else k
        system, settings = SYSTEM, {"retrieval": mode, "k": k, "max_chars": max_chars, "retriever": "bm25okapi"}
    answer, call = cached_reply(cache, INSTRUCTIONS, user_prompt(question, hits), model=model, model_id=model_id,
                                seed=seed, output_type=CitedAnswer)
    call.pop("cached")  # so a cached rerun writes the same bytes
    citations, dropped = keep_citations(answer.citations, hits)
    if not answer.answer_text.strip():
        reply, mapping = AnswerReply(label="insufficient", studies=[], answer_text="(no answer)"), None
    else:
        reply, mapping = map_answer(cache, question, corpus.ids, mapping_text(answer, citations), model=model,
                                    model_id=model_id, seed=seed)
    retrieved = [{"document": p.document, "start": p.start, "end": p.end} | ({} if oracle else {"score": round(s, 6)})
                 for p, s in hits]
    return answer_json(system, question, reply, corpus.ids, answer_text=answer.answer_text, citations=citations,
                       dropped_citations=dropped, retrieved=retrieved, corpus_id=corpus.corpus_id, settings=settings,
                       model_call=call, mapping_call=mapping, mapped_answer_text=reply.answer_text)
