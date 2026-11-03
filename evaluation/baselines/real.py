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
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai.models import Model

from modelcall import JsonlCache

from ..wholerun import Answer, RealQuestion
from . import rag
from .common import SystemCorpus, cached_reply, model_name, paper_id

DIRECTIONS = ("improves", "worsens", "no_effect")

COMMON = ("You read a written answer to a question and copy it into a fixed form. Use only what the answer says; "
          "write nothing the answer does not state. An answer that says nothing usable gives an empty form.")
MAP_INSTRUCTIONS = {
    "rank": COMMON + (" Output `ranking`: the papers the answer ranks, best first, each as its paper id from the list "
                      "given (a paper the answer names by title or author: the id it means). Example: the answer says "
                      "\"P2 beats P1, and P3 is last\" -> [\"P2\", \"P1\", \"P3\"]."),
    "list": COMMON + (" Output `names`: every name the answer gives as an answer to the question, once each, exactly "
                      "as written. Example: \"It uses SQuAD and MNLI\" -> [\"SQuAD\", \"MNLI\"]."),
    "compare": COMMON + (" Output `studies`: one entry per paper the answer judges, with `document` its paper id (from "
                         "the list given) and `direction` improves, worsens or no_effect for the question's "
                         "treatment; and `conclusion`: the answer's overall direction, or null when it gives none. "
                         "Example: \"S1 is up, S2 is flat\" -> S1 improves, S2 no_effect."),
    "claims": COMMON + (" Output `claims`: one entry per conclusion the answer states, with `about` the id of the "
                        "conclusion it addresses, taken from the conclusions listed in the input, and `direction` "
                        "improves, worsens or no_effect. A statement that addresses none of the listed conclusions "
                        "is left out."),
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
    about: str = Field(description="the id of the listed conclusion the claim addresses")
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
        ids = [paper_id(n, known) for n in reply.ranking if n.strip()]
        return Answer(ranking=list(dict.fromkeys(i for i in ids if i is not None)))
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
    ids = {c["id"] for c in q.gold.get("conclusions", [])}
    return Answer(claims=[{"about": c.about, "direction": c.direction} for c in reply.claims if c.about in ids])


def _mapping_prompt(q: RealQuestion, corpus: SystemCorpus, text: str) -> str:
    nl = chr(10)
    prompt = f"Question: {q.question}{nl}{nl}Corpus paper ids: {', '.join(corpus.ids)}{nl}{nl}"
    if q.kind == "claims":
        lines = [f"- {c['id']}: {q.question}" for c in q.gold.get("conclusions", [])]
        prompt += "Conclusions (id: text):" + nl + nl.join(lines) + nl + nl
    return prompt + "The answer:" + nl + text


def rag_real_full(q: RealQuestion, *, model: Model, engine_corpus: Path, engine_model_id: str,
                  mode: Literal["global", "per_paper"] = "global", cache: JsonlCache | None = None,
                  model_id: str | None = None, seed: int = 0) -> tuple[Answer, dict[str, Any]]:
    """(the `Answer`, its record) for `q`. The record has the fields of rag_baseline's answer.json: system,
    question, kind, corpus_id, answer_text, citations, dropped_citations, retrieved, settings, model_call,
    mapping_call (no `cached` flag, so a cached rerun writes the same bytes). `engine_corpus` and `engine_model_id`
    are the engine run's: the baseline refuses other papers or another model."""
    if q.kind not in REPLY:
        raise ValueError(f"unknown question kind {q.kind!r}")
    check_same_papers(q.corpus_dir, engine_corpus)
    used = model_id or model_name(model)
    if used != engine_model_id:
        raise ValueError(f"the baseline model {used!r} is not the engine's model {engine_model_id!r}; every real-set "
                         "row uses one pinned model")
    corpus = SystemCorpus(q.corpus_dir)
    hits = rag.retrieve(rag.passages(corpus), q.question, None, mode)
    limit = rag.MAX_TOKENS[mode]
    cited, call = cached_reply(cache, rag.INSTRUCTIONS, rag.user_prompt(q.question, hits), model=model,
                               model_id=model_id, seed=seed, max_tokens=limit, output_type=rag.CitedAnswer)
    call.pop("cached")
    kept, dropped = rag.keep_citations(cited.citations, hits)
    mapping = None
    answer = Answer()
    if cited.answer_text.strip():
        reply, mapping = cached_reply(cache, MAP_INSTRUCTIONS[q.kind],
                                      _mapping_prompt(q, corpus, rag.mapping_text(cited, kept)), model=model,
                                      model_id=model_id, seed=seed, output_type=REPLY[q.kind])
        mapping.pop("cached")
        answer = _to_answer(q, reply, corpus.ids)
    record = {"system": rag.SYSTEM, "question_id": q.id, "question": q.question, "kind": q.kind,
              "corpus_id": corpus.corpus_id, "answer_text": cited.answer_text, "citations": kept,
              "dropped_citations": dropped,
              "retrieved": [{"document": p.document, "start": p.start, "end": p.end, "score": round(sc, 6)}
                            for p, sc in hits],
              "settings": {"retrieval": mode, "k": rag.K[mode], "max_chars": rag.MAX_CHARS, "max_tokens": limit,
                           "retriever": "bm25okapi"},
              "model_call": call, "mapping_call": mapping}
    return answer, record


def rag_real(q: RealQuestion, **kwargs: Any) -> Answer:
    """The baseline's `Answer` for `q` (see `rag_real_full`, whose keyword arguments it takes)."""
    return rag_real_full(q, **kwargs)[0]
