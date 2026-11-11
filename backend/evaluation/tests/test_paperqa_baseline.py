"""The PaperQA2 baseline with paper-qa replaced by a fake at `run_paperqa` (no paper-qa install, no network): the
answer.json shape, citations mapped back to paper ids, the mapping call, and the hard rule (manifest + papers only)."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from evaluation.baselines import paperqa as pq
from evaluation.baselines.common import SystemCorpus

from . import fixtures as fx
from .helpers import Scripted, guard_corpus
from .test_rag import MAPPED

ANSWER = "Retrieval raised accuracy (unknownauthorsUnknownyears001 chunk 1)."


def fake_paperqa(corpus: SystemCorpus, question: str, **kw: Any) -> pq.PaperQAResult:
    """What paper-qa gives back after reading the files `write_papers` wrote: contexts named as its index names them,
    with the md5 of their file, the first one cited."""
    with tempfile.TemporaryDirectory() as tmp:
        papers = pq.write_papers(corpus, Path(tmp))
        contexts = [{"id": f"pqac-{i}", "docname": f"unknownauthorsUnknownyears00{i + 1}", "dockey": f"k{i}",
                     "content_hash": hashlib.md5((papers / f"{p.id}.txt").read_bytes()).hexdigest(),
                     "text": p.text[10:60], "summary": "relevant", "score": 8 - i}
                    for i, p in enumerate(corpus.papers)]
    settings = {"paperqa_version": "fake", "embedding": pq.EMBEDDING, "model": kw["model"], "seed": kw["seed"]}
    return pq.PaperQAResult(answer=ANSWER, contexts=contexts, cited=["pqac-0"], settings=settings, status="success",
                            session={"question": question, "answer": ANSWER})


def test_answer_json_cites_paper_ids_and_reads_manifest_and_papers_only(tmp_path: Path,
                                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = fx.write_corpus(tmp_path)
    attempts = guard_corpus(monkeypatch, corpus)
    model = Scripted(MAPPED)
    answer, session = pq.paperqa_baseline(corpus, model=model.model(), question=fx.QUESTION, ask=fake_paperqa)
    assert attempts == []
    assert answer["system"] == "paperqa2" and answer["label"] == "mixed" and answer["answer_text"] == ANSWER
    assert answer["studies"] == [{"document": "S001", "direction": "supports"},
                                 {"document": "S002", "direction": "contradicts"}]
    start = fx.S001.index(fx.S001[10:60])
    assert answer["citations"] == [{"document": "S001", "start": start, "end": start + 50, "context_id": "pqac-0"}]
    assert [r["document"] for r in answer["retrieved"]] == ["S001", "S002"] and answer["retrieved"][0]["score"] == 8
    assert answer["settings"]["embedding"] == "sparse" and answer["settings"]["model"] == "orch-model"
    assert answer["paperqa"]["status"] == "success" and session["answer"] == ANSWER
    [mapping] = model.prompts   # paper-qa's own calls are not ours: only the mapping call is made here
    assert "Retrieval raised accuracy (S001 chunk 1)." in mapping and "Cited papers: S001" in mapping
    assert fx.S001[10:60] not in mapping


def test_cli_writes_answer_and_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from evaluation import cli
    corpus = fx.write_corpus(tmp_path)
    monkeypatch.setattr(cli, "_model", lambda alias: (Scripted(MAPPED).model(alias), alias))
    monkeypatch.setattr(pq, "run_paperqa", fake_paperqa)
    assert cli.main(["paperqa-baseline", "--corpus", str(corpus), "--out", str(tmp_path / "o")]) == 0
    answer = json.loads((tmp_path / "o" / "answer.json").read_text(encoding="utf-8"))
    session = json.loads((tmp_path / "o" / pq.SESSION_FILE).read_text(encoding="utf-8"))
    assert answer["system"] == "paperqa2" and answer["mapping_call"]["model"] == "orch-model"
    assert session["answer"] == ANSWER
