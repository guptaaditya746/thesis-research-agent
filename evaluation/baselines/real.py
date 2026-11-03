"""The RAG baseline on the real whole-run questions (W6, Task 6.5): the existing BM25 search-then-answer of
`rag.py` on `q.corpus_dir`, then one mapping call per question kind that puts the free-text answer into the shape
`wholerun.score` reads (rank: names best first; list: names; compare: a direction per study; claims: claim list).

Same pinned model, same papers (`engine_corpus`: the engine run's corpus dir, refused when its papers differ) and the
same question text as the engine. Both calls are cached (modelcall.JsonlCache) like `rag_baseline`. An empty answer
text is a valid, empty `Answer` with no mapping call.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai.models import Model

from modelcall import JsonlCache

from ..wholerun import Answer, RealQuestion
from . import rag
from .common import SystemCorpus, cached_reply, paper_id

DIRECTIONS = ("improves", "worsens", "no_effect")

COMMON = ("You read a written answer to a question and copy it into a fixed form. Use only what the answer says; "
          "write nothing the answer does not state. An answer that says nothing usable gives an empty form.")
MAP_INSTRUCTIONS = {
    "rank": COMMON + (" Output `ranking`: the names the answer ranks, best first, exactly as the answer writes them. "
                      "Example: the answer says \"B beats A, and C is last\" -> [\"B\", \"A\", \"C\"]."),
    "list": COMMON + (" Output `names`: every name the answer gives as an answer to the question, once each, exactly "
                      "as written. Example: \"It uses SQuAD and MNLI\" -> [\"SQuAD\", \"MNLI\"]."),
    "compare": COMMON + (" Output `studies`: one entry per paper the answer judges, with `document` its paper id (from "
                         "the list given) and `direction` improves, worsens or no_effect for the question's "
                         "treatment; and `conclusion`: the answer's overall direction, or null when it gives none. "
                         "Example: \"S1 is up, S2 is flat\" -> S1 improves, S2 no_effect."),
    "claims": COMMON + (" Output `claims`: one entry per conclusion the answer states, with `about` a short label of "
                        "what it is about and `direction` improves, worsens or no_effect."),
}


class RankReply(BaseModel):
    ranking: list[str] = Field(description="names ranked best first, as the answer writes them")


class ListReply(BaseModel):
    names: list[str] = Field(description="the names the answer gives, once each")


class StudyDirection(BaseModel):
    document: str = Field(description="the paper id, from the list given")
    direction: Literal["improves", "worsens", "no_effect"]


class CompareReply(BaseModel):
    studies: list[StudyDirection]
    conclusion: Literal["improves", "worsens", "no_effect"] | None = Field(
        default=None, description="the answer's overall direction, or null")


class ClaimItem(BaseModel):
    about: str = Field(description="a short label of what the claim is about")
    direction: Literal["improves", "worsens", "no_effect"]


class ClaimsReply(BaseModel):
    claims: list[ClaimItem]


REPLY = {"rank": RankReply, "list": ListReply, "compare": CompareReply, "claims": ClaimsReply}


def _papers(corpus_dir: Path) -> dict[str, str | None]:
    manifest = json.loads((Path(corpus_dir) / "manifest.json").read_text(encoding="utf-8"))
    return {p["id"]: p.get("sha256") for p in manifest["papers"]}


def check_same_papers(corpus_dir: Path, engine_corpus: Path) -> None:
    """Raise ValueError unless the two corpora hold the same paper ids with the same hashes."""
    if _papers(corpus_dir) != _papers(engine_corpus):
        raise ValueError(f"{corpus_dir} does not hold the same papers as the engine run's corpus {engine_corpus}; "
                         "the baseline and the engine must read the same papers")


def _to_answer(q: RealQuestion, reply: BaseModel, known: list[str]) -> Answer:
    if isinstance(reply, RankReply):
        return Answer(ranking=[n for n in reply.ranking if n.strip()])
    if isinstance(reply, ListReply):
        return Answer(names=[n for n in reply.names if n.strip()])
    if isinstance(reply, CompareReply):
        found = {}
        for s in reply.studies:
            doc = paper_id(s.document, known)
            if doc is not None:
                found.setdefault(doc, s.direction)
        return Answer(directions=found, conclusion=reply.conclusion)
    assert isinstance(reply, ClaimsReply)
    return Answer(claims=[{"about": q.id if len(q.gold.get("conclusions", [])) == 1 else c.about,
                           "direction": c.direction} for c in reply.claims])


def rag_real(q: RealQuestion, *, model: Model, mode: Literal["global", "per_paper"] = "global",
             engine_corpus: Path | None = None, cache: JsonlCache | None = None, model_id: str | None = None,
             seed: int = 0) -> Answer:
    """The baseline's `Answer` for `q` (see the module docstring). `engine_corpus`: the corpus dir the engine run
    reads; the baseline refuses a `q.corpus_dir` with other papers."""
    if q.kind not in REPLY:
        raise ValueError(f"unknown question kind {q.kind!r}")
    if engine_corpus is not None:
        check_same_papers(q.corpus_dir, engine_corpus)
    corpus = SystemCorpus(q.corpus_dir)
    hits = rag.retrieve(rag.passages(corpus), q.question, None, mode)
    limit = rag.MAX_TOKENS[mode]
    cited, _ = cached_reply(cache, rag.INSTRUCTIONS, rag.user_prompt(q.question, hits), model=model,
                            model_id=model_id, seed=seed, max_tokens=limit, output_type=rag.CitedAnswer)
    if not cited.answer_text.strip():
        return Answer()
    kept, _ = rag.keep_citations(cited.citations, hits)
    prompt = (f"Question: {q.question}\n\nCorpus paper ids: {', '.join(corpus.ids)}\n\nThe answer:\n"
              f"{rag.mapping_text(cited, kept)}")
    reply, _ = cached_reply(cache, MAP_INSTRUCTIONS[q.kind], prompt, model=model, model_id=model_id, seed=seed,
                            output_type=REPLY[q.kind])
    return _to_answer(q, reply, corpus.ids)
