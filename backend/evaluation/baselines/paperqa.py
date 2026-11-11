"""The PaperQA2 baseline: a state-of-the-art answer-level system (paper-qa, github.com/Future-House/paper-qa) on the
corpus's papers, its answer mapped like the other baselines' (third baseline, beside rag.py and agent.py).

1. The corpus (SystemCorpus: manifest.json and papers/ only, hash-checked) is copied as plain text, one
   `<paper id>.txt` per paper, into a work folder with a paper-qa manifest (manifest.csv) that gives each file its
   paper id as title and citation, so paper-qa reads nothing else and needs no model call to cite a file. paper-qa
   renames the documents of its index (e.g. "unknownauthorsUnknownyears020"), so a context is mapped back to its
   paper by the md5 of the file it came from (paper-qa's `content_hash`).
2. paper-qa answers the question with its agent (`agent_query`, agent type ToolSelector unless `agent_type` says
   otherwise): it searches a local full-text index (tantivy) of that folder, gathers evidence (one summary call per
   chunk, ranked by relevance) and writes a cited answer. Offline: no online paper search (the only search tool is the
   local index), no Semantic Scholar / Crossref metadata (`parsing.use_doc_details` false), no media parsing.
   No embedding model: `embedding="sparse"` (paper-qa's keyword-only sparse embedding), never a dense embedding.
   One model for everything: paper-qa's llm, summary_llm and agent_llm are the pinned orch-model through our LiteLLM
   gateway ($LITELLM_BASE_URL, key from $LITELLM_MASTER_KEY, as modelcall.gateway), temperature 0, seed `seed`,
   thinking off. The index is built by one worker (`index.concurrency` 1, default 5: with 5, tantivy's commits
   failed on Windows; 20-odd local text files need no parallel reads). Every other paper-qa setting keeps its default (evidence_k 10, answer_max_sources 5, answer and
   summary lengths, chunks of 5000 characters with 250 overlap, search_count 8, the agent timeout): the prompts they
   make stay far below orch-model's 65k-token context, so none needed changing.
   A run whose status is `fail` (paper-qa catches a failed model call and still answers "I cannot answer ...") is an
   error, never an answer: no answer.json is written.
3. The answer's cited contexts are mapped back to paper ids (`citations`; every context paper-qa kept is under
   `contexts`, with its relevance score; `start`/`end` when the chunk text is found verbatim in the paper).
4. The mapping call shared with the other baselines (common.map_answer, cached in our JsonlCache) turns the answer
   text (paper-qa's document names replaced by paper ids) and the cited paper ids into the question kind's reply; answer.json has the same shape as rag.py's
   (common.answer_json / kind_answer_json), with `system: paperqa2`, `answer_text` (paper-qa's answer), `citations`,
   `contexts`, `settings` (paper-qa version, embedding, model and the settings above), `paperqa` (status, its token
   counts, cost) and `mapping_call`.

NOT replayable call-for-call: paper-qa makes its own LLM calls (through LiteLLM) and they do not go through
modelcall.JsonlCache, so a rerun asks the model again and may answer differently; only the mapping call is cached.
What paper-qa returned is kept: the CLI writes its session (answer, contexts and their summaries, tool history) as
`paperqa_session.json` beside answer.json.

paper-qa is an optional dependency group (`uv sync --group paperqa`); it is imported only inside `run_paperqa`, so
everything else, and the tests (which pass a fake `ask`), runs without it.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai.models import Model

from modelcall import JsonlCache, redact
from modelcall.gateway import base_url
from modelcall.pins import ORCH_ALIAS

from .common import (DEFAULT_QUESTION, AnswerReply, SystemCorpus, answer_json, empty_reply, kind_answer_json,
                     kind_params, map_answer)

SYSTEM = "paperqa2"
EMBEDDING = "sparse"            # keyword-only sparse embedding: no embedding model is deployed, never a dense one
AGENT_TYPE = "ToolSelector"     # paper-qa's default agent; "fake" runs search, gather evidence, answer in a fixed order
SESSION_FILE = "paperqa_session.json"


@dataclass(frozen=True)
class PaperQAResult:
    """What one paper-qa run gives back, in plain data: the answer, its contexts (each with `id`, `docname`,
    `dockey`, `content_hash`, `text`, `summary`, `score`), the ids of the contexts the answer cites, the settings it ran with (no key), its
    status, token counts and cost, and the whole session (JSON-able) to keep beside answer.json."""
    answer: str
    contexts: list[dict[str, Any]]
    cited: list[str]
    settings: dict[str, Any]
    status: str | None = None
    token_counts: dict[str, Any] = field(default_factory=dict)
    cost: float | None = None
    session: dict[str, Any] = field(default_factory=dict)


Ask = Callable[..., PaperQAResult]


def write_papers(corpus: SystemCorpus, folder: Path) -> Path:
    """`<folder>/papers/<paper id>.txt` for every paper (the hash-checked text) and `<folder>/manifest.csv`, paper-qa's
    manifest: file_location, title, docname and citation are the paper id. Returns the papers folder. (A .txt name
    makes paper-qa read the file as text; a .md file would be chunked as code.)"""
    papers = folder / "papers"
    papers.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in corpus.papers:
        (papers / f"{p.id}.txt").write_text(p.text, encoding="utf-8", newline="")
        rows.append({"file_location": f"{p.id}.txt", "title": p.id, "docname": p.id, "citation": p.id, "doi": ""})
    with (folder / "manifest.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["file_location"])
        writer.writeheader()
        writer.writerows(rows)
    return papers


def _llm_config(alias: str, seed: int) -> dict[str, Any]:
    """A LiteLLM router config of one gateway alias (the key is read from the environment, never recorded)."""
    params = {"model": f"openai/{alias}", "api_base": base_url(), "api_key": os.environ.get("LITELLM_MASTER_KEY") or "none",
              "temperature": 0.0, "seed": seed, "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
    return {"name": alias, "model_list": [{"model_name": alias, "litellm_params": params}]}


def paperqa_settings(work: Path, *, model: str = ORCH_ALIAS, seed: int = 0, agent_type: str = AGENT_TYPE) -> Any:
    """paper-qa's Settings for a corpus written by `write_papers` into `work` (see the module docstring)."""
    from paperqa.settings import AgentSettings, IndexSettings, ParsingSettings, Settings
    config = _llm_config(model, seed)
    return Settings(
        llm=model, llm_config=config, summary_llm=model, summary_llm_config=config, embedding=EMBEDDING,
        temperature=0.0,
        parsing=ParsingSettings(use_doc_details=False, multimodal=False),
        agent=AgentSettings(agent_llm=model, agent_llm_config=config, agent_type=agent_type,
                            index=IndexSettings(name="corpus", paper_directory=work / "papers",
                                                manifest_file=work / "manifest.csv", index_directory=work / "index",
                                                concurrency=1)))


def settings_record(settings: Any, *, version: str, model: str, agent_type: str, seed: int) -> dict[str, Any]:
    """The settings recorded in answer.json: what was set here and the paper-qa defaults kept (no key, no paths)."""
    a, p, ag = settings.answer, settings.parsing, settings.agent
    return {"paperqa_version": version, "embedding": settings.embedding, "model": model, "llm": settings.llm,
            "summary_llm": settings.summary_llm, "agent_llm": ag.agent_llm, "agent_type": agent_type,
            "temperature": settings.temperature, "seed": seed, "thinking": False,
            "evidence_k": a.evidence_k, "answer_max_sources": a.answer_max_sources, "answer_length": a.answer_length,
            "evidence_summary_length": a.evidence_summary_length,
            "evidence_relevance_score_cutoff": a.evidence_relevance_score_cutoff,
            "chunk_chars": p.reader_config.get("chunk_chars"), "overlap": p.reader_config.get("overlap"),
            "use_doc_details": p.use_doc_details, "multimodal": str(p.multimodal), "search_count": ag.search_count,
            "agent_timeout": ag.timeout, "max_timesteps": ag.max_timesteps, "index_concurrency": ag.index.concurrency,
            "paper_search": "local tantivy index"}


def run_paperqa(corpus: SystemCorpus, question: str, *, model: str = ORCH_ALIAS, seed: int = 0,
                agent_type: str = AGENT_TYPE) -> PaperQAResult:
    """One real paper-qa agent run over the corpus (needs the paperqa dependency group and the gateway)."""
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")   # LiteLLM: no cost-map download (offline cluster)
    import paperqa
    from paperqa import Docs
    from paperqa.agents import agent_query

    docs = Docs()   # the agent adds the papers it reads here; the session's contexts lose their text, these keep it
    with tempfile.TemporaryDirectory(prefix="paperqa-") as tmp:
        work = Path(tmp)
        write_papers(corpus, work)
        settings = paperqa_settings(work, model=model, seed=seed, agent_type=agent_type)
        response = asyncio.run(agent_query(question, settings, docs=docs, agent_type=agent_type))
    session = response.session
    chunks = {t.name: t.text for t in docs.texts}
    contexts = [{"id": c.id, "docname": c.text.doc.docname, "dockey": str(c.text.doc.dockey),
                 "content_hash": c.text.doc.content_hash, "name": c.text.name,
                 "text": c.text.text or chunks.get(c.text.name, ""), "summary": c.context, "score": c.score}
                for c in session.contexts]
    return PaperQAResult(
        answer=session.answer, contexts=contexts, cited=sorted(session.used_contexts),
        settings=settings_record(settings, version=paperqa.__version__, model=model, agent_type=agent_type, seed=seed),
        status=str(response.status), token_counts=dict(session.token_counts), cost=session.cost,
        session=session.model_dump(mode="json", exclude={"config_md5"}))


def file_hashes(corpus: SystemCorpus) -> dict[str, str]:
    """md5 of each `<paper id>.txt` that `write_papers` writes -> paper id (paper-qa's Doc.content_hash)."""
    return {hashlib.md5(p.text.encode("utf-8")).hexdigest(): p.id for p in corpus.papers}


def paper_of(context: dict[str, Any], corpus: SystemCorpus) -> tuple[str | None, int | None, int | None]:
    """(paper id, start, end) of a context: by the md5 of its file, else its docname or dockey, else the paper whose
    text holds its chunk verbatim; start/end only when the chunk text is found verbatim in that paper."""
    texts = {p.id: p.text for p in corpus.papers}
    doc = file_hashes(corpus).get(context.get("content_hash") or "")
    if doc is None:
        doc = next((d for d in (context.get("docname"), context.get("dockey")) if d in texts), None)
    chunk = (context.get("text") or "").strip()
    if doc is None and chunk:
        doc = next((pid for pid, text in texts.items() if chunk in text), None)
    if doc is None or not chunk or (at := texts[doc].find(chunk)) < 0:
        return doc, None, None
    return doc, at, at + len(chunk)


def _passage(context: dict[str, Any], corpus: SystemCorpus) -> dict[str, Any] | None:
    doc, start, end = paper_of(context, corpus)
    if doc is None:
        return None
    return {"document": doc, **({"start": start, "end": end} if start is not None else {}), "context_id": context["id"]}


def mapping_text(answer: str, citations: list[dict[str, Any]], names: dict[str, str] | None = None) -> str:
    """What the mapping call reads: paper-qa's answer with its document names (`names`: name -> paper id) replaced by
    paper ids, and the paper ids it cites; never the passages (as rag.py)."""
    for name in sorted(names or {}, key=len, reverse=True):
        answer = answer.replace(name, (names or {})[name])
    cited = list(dict.fromkeys(c["document"] for c in citations))
    return answer.strip() + (f"\n\nCited papers: {', '.join(cited)}" if cited else "")


def paperqa_baseline(corpus_dir: Path, *, model: Model, question: str | None = None, cache: JsonlCache | None = None,
                     model_id: str | None = None, seed: int = 0, question_id: str | None = None,
                     questions: Path | None = None, alias: str = ORCH_ALIAS, agent_type: str = AGENT_TYPE,
                     ask: Ask | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """(answer.json, paper-qa's session) of the PaperQA2 baseline for one corpus. `model`/`model_id` make the mapping
    call; `alias` is the gateway alias paper-qa itself uses (the same model). `question_id`: a question of `questions`
    (not with `question`; default the default question). `ask` runs paper-qa (`run_paperqa`; a fake in tests)."""
    if question is not None and question_id is not None:
        raise ValueError("give question or question_id, not both")
    params = kind_params(question_id, questions) if question_id is not None else None
    question = params.question if params else (question or DEFAULT_QUESTION)
    corpus = SystemCorpus(corpus_dir)
    try:
        result = (ask or run_paperqa)(corpus, question, model=alias, seed=seed, agent_type=agent_type)
    except Exception as exc:   # LiteLLM errors can echo the key: only a redacted reason leaves here
        raise RuntimeError(redact(f"paper-qa run failed: {type(exc).__name__}: {exc}")[:1000]) from None
    if result.status == "fail":   # paper-qa swallows a failed model call and answers with a stock sentence
        raise RuntimeError(redact(f"paper-qa run failed (status fail): {result.answer}")[:1000])
    kept = [p | {"score": c.get("score")} for c in result.contexts if (p := _passage(c, corpus)) is not None]
    by_id = {c["id"]: c for c in result.contexts}
    citations = [p for i in result.cited if i in by_id and (p := _passage(by_id[i], corpus)) is not None]
    effect = params is None or params.kind == "effect"
    if not result.answer.strip():
        reply = (AnswerReply(label="insufficient", studies=[], answer_text="(no answer)") if effect
                 else empty_reply(params))  # type: ignore[arg-type]
        mapping = None
    else:
        names = {c["docname"]: doc for c in result.contexts if c.get("docname") and (doc := paper_of(c, corpus)[0])}
        reply, mapping = map_answer(cache, question, corpus.ids, mapping_text(result.answer, citations, names),
                                    model=model, model_id=model_id, seed=seed, params=params)
    extra = {"citations": citations, "contexts": kept, "corpus_id": corpus.corpus_id, "settings": result.settings,
             "paperqa": {"status": result.status, "token_counts": result.token_counts, "cost": result.cost},
             "mapping_call": mapping}
    if params is not None and not effect:
        answer = kind_answer_json(SYSTEM, params, reply, corpus.ids, answer_text=result.answer, **extra)
    else:
        answer = answer_json(SYSTEM, question, reply, corpus.ids, answer_text=result.answer, **extra,
                             mapped_answer_text=reply.answer_text, protocol=params.protocol if params else None,
                             **({"question_id": params.question_id} if params else {}))
    return answer, result.session
