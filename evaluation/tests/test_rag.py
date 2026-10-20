"""The RAG baseline with scripted models: retrieval, the answer with citations, the mapping call, the cache,
the hard rule, and completeness / traceability in score C."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

import pytest

from evaluation.baselines import rag
from evaluation.baselines.common import MAP_INSTRUCTIONS, SystemCorpus
from evaluation.score import score_answers
from modelcall import JsonlCache

from . import fixtures as fx
from .helpers import Scripted, guard_corpus

HEADER = re.compile(r"\[(\S+), (\d+)-(\d+)\]")
ANSWER_TEXT = "S001 improves accuracy; S002 hallucinates more with retrieval."
MAPPED = {"label": "mixed", "answer_text": "Retrieval helped in S001 and hurt in S002.",
          "studies": [{"document": "S001", "stance": "supports"}, {"document": "S002", "stance": "contradicts"},
                      {"document": "S999", "stance": "supports"}, {"document": "S001", "stance": "neutral"}]}


def scripted(cite: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
             mapped: dict[str, Any] = MAPPED, text: str = ANSWER_TEXT) -> Scripted:
    """One scripted model for both calls: the answering call (its prompt lists the passages) cites the
    passages `cite` picks from the headers shown (default: all of them); the mapping call returns `mapped`."""
    def reply(prompt: str) -> dict[str, Any]:
        if "\n\nPassages:\n\n" in prompt:
            shown = [{"document": d, "start": int(a), "end": int(b)} for d, a, b in HEADER.findall(prompt)]
            return {"answer_text": text, "citations": cite(shown) if cite else shown}
        return mapped
    return Scripted(reply)


def test_rag_baseline_answers_with_citations_then_maps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = fx.write_corpus(tmp_path)
    attempts = guard_corpus(monkeypatch, corpus)
    model = scripted()
    answer = rag.rag_baseline(corpus, model=model.model(), k=3, mode="global", max_chars=200)
    assert attempts == []
    assert answer["system"] == "rag-baseline" and answer["label"] == "mixed"
    assert answer["studies"] == [{"document": "S001", "direction": "supports"},
                                 {"document": "S002", "direction": "contradicts"}]  # S999 dropped, S001 once
    assert answer["dropped"] == ["S999"] and answer["supporting"] == ["S001"] and answer["contradicting"] == ["S002"]
    assert answer["counts"] == {"supporting": 1, "contradicting": 1, "neutral": 0, "undetermined": 0}
    assert len(answer["retrieved"]) == 3 and answer["label_by_rule"] == "mixed"
    assert answer["answer_text"] == ANSWER_TEXT and answer["mapped_answer_text"] == MAPPED["answer_text"]
    assert answer["citations"] == [{k: r[k] for k in ("document", "start", "end")} for r in answer["retrieved"]]
    assert answer["dropped_citations"] == []
    answering, mapping = model.prompts
    texts = {"S001": fx.S001, "S002": fx.S002}
    for hit in answer["retrieved"]:  # offsets are raw offsets into the paper, and the prompt quotes them
        passage = texts[hit["document"]][hit["start"]:hit["end"]].strip()
        assert passage and passage in answering
        assert passage not in mapping and f"[{hit['document']}, {hit['start']}-{hit['end']}]" in mapping  # headers only
    assert answering.startswith("Question: " + fx.QUESTION) and "Labels" not in answering and "stance" not in answering
    assert "Corpus paper ids: S001, S002" in mapping and "Cited passages:" in mapping and ANSWER_TEXT in mapping
    assert "Labels (the same rule" in MAP_INSTRUCTIONS and "cite" in rag.INSTRUCTIONS
    assert answer["model_call"]["prompt_sha256"] != answer["mapping_call"]["prompt_sha256"]
    assert "cached" not in answer["model_call"] and "cached" not in answer["mapping_call"]
    monkeypatch.undo()
    result = score_answers(corpus, [_dump(tmp_path / "a.json", answer)])
    assert result["synthesis"][0]["label_correct"]


def test_retrieval_is_bm25_and_deterministic(tmp_path: Path) -> None:
    corpus = SystemCorpus(fx.write_corpus(tmp_path))
    chunks = rag.passages(corpus, max_chars=200)
    assert all(c.end - c.start <= 200 for c in chunks)
    hits = rag.retrieve(chunks, "hallucinated fetched passages", k=2, mode="global")
    assert hits[0][0].document == "S002" and hits[0][1] > 0
    assert rag.retrieve(list(reversed(chunks)), "hallucinated fetched passages", k=2, mode="global") == hits
    with pytest.raises(ValueError, match="retrieval mode"):
        rag.retrieve(chunks, "x", mode="all")


def test_default_retrieval_is_the_top_8_of_the_corpus(tmp_path: Path) -> None:
    """Part G.1: plain retrieve-then-answer, global top 8 by default; per_paper is the "every paper seen" option."""
    loud = "\n\n".join(f"Retrieval-augmented generation improves factual accuracy of answers, part {n}."
                       for n in range(12))
    quiet = {f"Q{n:02d}": f"# Study {n}\n\nThe system with documents scored {50 + n}% versus {40 + n}% without."
             for n in range(6)}
    corpus = tmp_path / "c"
    (corpus / "papers").mkdir(parents=True)
    papers = {"LOUD": loud, **quiet}
    for pid, text in papers.items():
        (corpus / "papers" / f"{pid}.md").write_text(text, encoding="utf-8", newline="\n")
    fx.dump(corpus / "manifest.json", {"corpus_id": "c", "papers": [{"id": p, "file": f"papers/{p}.md"} for p in papers]})
    answer = rag.rag_baseline(corpus, model=scripted().model(), max_chars=120)
    assert answer["settings"]["retrieval"] == "global" and answer["settings"]["k"] == 8
    assert len(answer["retrieved"]) == 8 and {r["document"] for r in answer["retrieved"]} == {"LOUD"}
    assert rag.DEFAULT_MODE == "global" and rag.K == {"global": 8, "per_paper": 2}
    every = rag.rag_baseline(corpus, model=scripted().model(), mode="per_paper", max_chars=120)
    seen = [r["document"] for r in every["retrieved"]]
    assert sorted(set(seen)) == sorted(papers) and all(seen.count(p) <= 2 for p in papers)
    assert every["settings"]["retrieval"] == "per_paper" and every["settings"]["k"] == 2


def test_citations_outside_the_retrieved_set_are_dropped(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    fake = {"document": "S001", "start": 1, "end": 5}
    other = {"document": "S999", "start": 0, "end": 10}
    model = scripted(lambda shown: [shown[1], fake, shown[1], other, shown[0]])
    answer = rag.rag_baseline(corpus, model=model.model(), k=4, mode="global", max_chars=200)
    shown = [{k: r[k] for k in ("document", "start", "end")} for r in answer["retrieved"]]
    assert answer["citations"] == [shown[1], shown[0]]          # once each, in citation order
    assert answer["dropped_citations"] == [fake, other]
    mapping = model.prompts[1]
    assert rag.header(rag.Citation(**shown[1])) in mapping and rag.header(rag.Citation(**shown[2])) not in mapping


def test_empty_answer_is_insufficient_without_a_mapping_call(tmp_path: Path) -> None:
    model = scripted(text="   ")
    answer = rag.rag_baseline(fx.write_corpus(tmp_path), model=model.model())
    assert answer["label"] == "insufficient" and answer["studies"] == [] and answer["mapping_call"] is None
    assert len(model.prompts) == 1 and answer["citations"]


def test_cache_makes_a_rerun_free_and_identical(tmp_path: Path) -> None:
    corpus = fx.write_corpus(tmp_path)
    cache = JsonlCache(tmp_path / "cache" / "rag.jsonl")
    first = scripted()
    a = rag.rag_baseline(corpus, model=first.model(), cache=cache)
    assert len(first.prompts) == 2
    second = scripted(mapped={"label": "supported", "studies": [], "answer_text": "other"}, text="other answer")
    b = rag.rag_baseline(corpus, model=second.model(), cache=JsonlCache(tmp_path / "cache" / "rag.jsonl"))
    assert second.prompts == [] and a == b
    c = rag.rag_baseline(corpus, model=second.model(), cache=cache, k=1, mode="global")  # other passages: new calls
    assert len(second.prompts) == 2 and c["label"] == "supported" and c["answer_text"] == "other answer"


def test_completeness_and_traceability_on_the_fixture_corpus(tmp_path: Path) -> None:
    """Score C of a RAG answer: a stance for S001 only (completeness 1/2); two cited passages of S001, one
    holding the abstract's "62%" (a placement), one holding no placement (the title): traceability 1/2."""
    corpus = fx.write_corpus(tmp_path)
    chunks = [c for c in rag.passages(SystemCorpus(corpus), max_chars=100) if c.document == "S001"]
    placed = [(p["start"], p["end"]) for p in fx.placements() if p["paper"] == "S001"]
    clean = next(c for c in chunks if not any(c.start < b and a < c.end for a, b in placed))
    traced = next(c for c in chunks if "62%" in c.text)
    wanted = {(clean.start, clean.end), (traced.start, traced.end)}
    model = scripted(lambda shown: [c for c in shown if c["document"] == "S001" and (c["start"], c["end"]) in wanted],
                     mapped={"label": "supported", "answer_text": "S001 helps.",
                             "studies": [{"document": "S001", "stance": "supports"}]})
    answer = rag.rag_baseline(corpus, model=model.model(), k=50, mode="global", max_chars=100)
    assert len(answer["citations"]) == 2
    system = score_answers(corpus, [_dump(tmp_path / "a.json", answer)])["synthesis"][0]
    rows = {r["level"]: r for r in system["rows"]}
    assert (rows["all"]["completeness"], rows["all"]["citations"], rows["all"]["traceability"]) == (0.5, 2, 0.5)
    assert (rows["explicit"]["completeness"], rows["explicit"]["traceability"]) == (1.0, 0.5)
    assert (rows["paraphrased"]["completeness"], rows["paraphrased"]["citations"],
            rows["paraphrased"]["traceability"]) == (0.0, 0, None)
    assert rows["all"]["direction_accuracy"] == 0.5 and rows["all"]["completeness"] == 0.5


@pytest.mark.parametrize("file", ["ground_truth.json", "decoys.json", "papers/../decoys.json", "notes/S001.md"])
def test_manifest_can_point_a_baseline_only_into_papers(tmp_path: Path, file: str) -> None:
    """Review 8: an allow-list (files directly in papers/), not a list of known evaluation files."""
    corpus = fx.write_corpus(tmp_path)
    (corpus / "notes").mkdir()
    (corpus / "notes" / "S001.md").write_text(fx.S001, encoding="utf-8")
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    manifest["papers"].append({"id": "X", "file": file, "sha256": ""})
    fx.dump(corpus / "manifest.json", manifest)
    with pytest.raises(ValueError, match="may not read"):
        SystemCorpus(corpus)


def _dump(path: Path, obj: dict) -> Path:
    fx.dump(path, obj)
    return path


def test_rag_baseline_two_live_calls_share_one_loop(tmp_path: Path) -> None:
    """The real model class over keep-alive HTTP: the answering call and then the mapping call in one process
    both reach the server (EV1: the second call failed with "Event loop is closed" when each call ran in its
    own `asyncio.run`, because the pooled connection belonged to the first, closed loop)."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from modelcall import openai_model

    prompts: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"  # keep the connection open between requests, as LiteLLM does

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            prompt = body["messages"][-1]["content"]
            prompts.append(prompt)
            content = json.dumps(scripted().reply(prompt))
            data = json.dumps({"id": f"c{len(prompts)}", "object": "chat.completion", "created": 0, "model": "m",
                               "choices": [{"index": 0, "finish_reason": "stop",
                                            "message": {"role": "assistant", "content": content}}],
                               "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        model = openai_model("orch-model", url=f"http://127.0.0.1:{server.server_address[1]}/v1")
        answer = rag.rag_baseline(fx.write_corpus(tmp_path), model=model, k=3, mode="global", max_chars=200)
    finally:
        server.shutdown()
        server.server_close()
    assert len(prompts) == 2 and answer["label"] == "mixed" and answer["mapping_call"] is not None
