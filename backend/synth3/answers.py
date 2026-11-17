"""Answers in one shape: the text, the papers it cites, and what the system pulled (engine facts or baseline
passages). The judge reads `AnswerRecord`s only; it never learns which system answered (`answer_text`).

Files: `<results>/<domain>/s<seed>/<system>/<qid>.answer.json` (local, git-ignored)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import Field

from evidence.rundir import ANSWER_FILE, RUN_FILE, Corpus, PaperIndex, RunDir
from jsonio import canonical, write_json_atomic
from synth2.recipe import Strict
from synth3.questions import Question, question_sha256
from synth3.sheetfacts import Folder

SYSTEM_ID = r"^[a-z0-9][a-z0-9-]*$"
MAX_TEXT = 12_000
HIDDEN = ("system", "question", "question_id", "protocol", "corpus_id", "run_id", "retrieved", "settings",
          "citations", "dropped_citations")
RAG_SYSTEM = "rag-baseline"
_PAPER = re.compile(r"\bS\d{3}\b")


class PulledFact(Strict):
    paper: str
    kind: str   # the evidence type, or "passage"
    fields: dict
    quote: str
    start: int | None = None
    end: int | None = None


class AnswerRecord(Strict):
    domain: str
    seed: int
    corpus_id: str
    question_id: str
    question_sha256: str
    system: str
    text: str
    text_cut: bool
    cited: list[str]
    facts: list[PulledFact] | None   # None: the system pulls no per-paper facts
    passages: list[PulledFact]
    source: str
    asked_sha256: str | None = Field(None, exclude_if=lambda v: v is None)   # the system's records only


def _clean(value: Any) -> Any:
    """`value` without the HIDDEN keys and the `*_call` keys, at any depth."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if k not in HIDDEN and not str(k).endswith("_call")}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def answer_text(answer: dict) -> tuple[str, bool]:
    """The text a judge reads and whether it was cut at MAX_TEXT: `answer_text` when it is a non-empty string,
    else the canonical JSON of the answer without what names the system."""
    given = answer.get("answer_text")
    text = given if isinstance(given, str) and given.strip() else canonical(_clean(answer))
    if len(text) <= MAX_TEXT:
        return text, False
    return text[:MAX_TEXT] + f"\n[cut at {MAX_TEXT} characters]", True


def cited_papers(text: str, ids: list[str]) -> list[str]:
    """The folder's paper ids named in the text, first-seen order, unknown ids dropped."""
    known = set(ids)
    return [p for p in dict.fromkeys(_PAPER.findall(text)) if p in known]


def _record(folder: Folder, q: Question, system: str, answer: dict, cited_from: list[str] | None, source: str,
            facts: list[PulledFact] | None, passages: list[PulledFact]) -> AnswerRecord:
    text, cut = answer_text(answer)
    ids = PaperIndex.of_corpus(folder.path).ids
    cited = cited_papers(text, ids) if cited_from is None else cited_from
    return AnswerRecord(domain=folder.spec.domain, seed=folder.seed, corpus_id=folder.corpus_id,
                        question_id=q.id, question_sha256=question_sha256(q), system=system, text=text,
                        text_cut=cut, cited=cited, facts=facts, passages=passages, source=source)


def from_engine_run(run: Path, folder: Folder, q: Question, system: str = "engine") -> AnswerRecord:
    rd = RunDir(run)
    answer = rd.json(ANSWER_FILE)
    if not isinstance(answer, dict):
        raise ValueError(f"{run}: no {ANSWER_FILE}; is the run finished?")
    record = rd.json(RUN_FILE)
    named = record.get("corpus_id") if isinstance(record, dict) else None
    if named != folder.corpus_id:
        raise ValueError(f"{run}: the run is of corpus {named!r}, the folder is {folder.corpus_id!r}; "
                         "a run on another corpus is refused")
    index = PaperIndex.of_corpus(folder.path)
    facts = []
    for item in rd.items():
        sel = item.spans[0].selector
        facts.append(PulledFact(paper=index.of(item), kind=item.evidence_type, fields=item.fields,
                                quote=str(sel.get("exact", "")), start=sel.get("start"), end=sel.get("end")))
    return _record(folder, q, system, answer, None, str(run), facts, [])


def from_rag_answer(answer: dict, folder: Folder, q: Question, source: str) -> AnswerRecord:
    corpus = Corpus(folder.path)
    papers = {p.id: p for p in corpus.papers}
    cited, passages = [], []
    for c in answer.get("citations") or []:
        doc, start, end = c["document"], int(c["start"]), int(c["end"])
        if doc not in papers:
            raise ValueError(f"{source}: cites {doc}, which is not a paper of the folder")
        text = corpus.text(papers[doc])
        if not 0 <= start <= end <= len(text):
            raise ValueError(f"{source}: the citation {doc} {start}-{end} is outside the paper")
        if doc not in cited:
            cited.append(doc)
        passages.append(PulledFact(paper=doc, kind="passage", fields={}, quote=text[start:end],
                                   start=start, end=end))
    return _record(folder, q, RAG_SYSTEM, answer, cited, source, None, passages)


def answer_path(results: Path, domain: str, seed: int, system: str, qid: str) -> Path:
    return results / domain / f"s{seed}" / system / f"{qid}.answer.json"


def save_answer(results: Path, rec: AnswerRecord) -> Path:
    path = answer_path(results, rec.domain, rec.seed, rec.system, rec.question_id)
    write_json_atomic(path, rec.model_dump())
    return path


def load_answer(path: Path) -> AnswerRecord:
    return AnswerRecord(**json.loads(Path(path).read_text(encoding="utf-8")))


def load_answers(results: Path, domain: str) -> list[AnswerRecord]:
    out = [load_answer(p) for p in (results / domain).glob("s*/*/*.answer.json")]
    return sorted(out, key=lambda r: (r.seed, r.system, r.question_id))


def item_id(rec: AnswerRecord) -> str:
    return f"{rec.domain}/s{rec.seed}/{rec.system}/{rec.question_id}"
