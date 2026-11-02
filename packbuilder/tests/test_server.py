"""The corpus tool server, called in process: its six tools, the hard rule (manifest.json and papers/ only), BM25
search, grep, sections and tables, and errors for unknown papers, headings and bad regexes."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.mcp import MCPToolset

from evaluation.tests import fixtures as fx
from evaluation.tests.helpers import guard_corpus
from packbuilder.server import create_server

TOOLS = {"list_papers", "read_paper", "read_section", "search", "grep", "tables"}


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """The two-paper fixture corpus (S001, S002), with ground_truth.json and the other gold files beside papers/."""
    return fx.write_corpus(tmp_path)


def result(srv: Any, name: str, args: dict[str, Any]) -> Any:
    """A tool's structured result (a list or dict tool return is wrapped as {"result": ...} or returned as is)."""
    out = run(srv.call_tool(name, args)).structured_content
    return out["result"] if set(out) == {"result"} else out


def scores_descending(hits: list[dict[str, Any]]) -> bool:
    scores = [h["score"] for h in hits]
    return scores == sorted(scores, reverse=True)


def test_server_lists_exactly_six_tools(corpus: Path) -> None:
    tools = run(create_server(corpus).list_tools())
    assert {t.name for t in tools} == TOOLS
    assert all(t.description for t in tools)


def test_server_never_opens_gold(monkeypatch: pytest.MonkeyPatch, corpus: Path) -> None:
    attempts = guard_corpus(monkeypatch, corpus)
    srv = create_server(corpus)
    for name, args in [("list_papers", {}), ("search", {"query": "response rate"}), ("grep", {"regex": "studies"}),
                       ("tables", {"paper_id": "S001"}), ("read_paper", {"paper_id": "S002"}),
                       ("read_section", {"paper_id": "S002", "heading": "Findings"})]:
        run(srv.call_tool(name, args))
    with pytest.raises(Exception, match="unknown paper"):
        run(srv.call_tool("read_paper", {"paper_id": "../ground_truth"}))
    assert attempts == []


def test_manifest_listing_gold_is_refused(corpus: Path) -> None:
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    data = (corpus / "ground_truth.json").read_bytes()
    manifest["papers"].append({"id": "GT", "file": "ground_truth.json", "sha256": hashlib.sha256(data).hexdigest()})
    fx.dump(corpus / "manifest.json", manifest)
    with pytest.raises(ValueError, match="papers/"):
        create_server(corpus)


def test_search_is_bm25_ranked(corpus: Path) -> None:
    # "retrieval accuracy" occurs in S001's abstract, its closing sentence and its table, and in S002's last paragraph
    hits = result(create_server(corpus), "search", {"query": "retrieval accuracy", "k": 3})
    assert len(hits) >= 2 and len(hits) <= 3
    assert scores_descending(hits) and all(h["score"] > 0 for h in hits)
    for h in hits:
        text = fx.PAPERS[h["paper"]]
        assert h["text"] == text[h["start"]:h["end"]] and "\n\n" not in h["text"]
    assert hits[0]["paper"] == "S001"


def test_search_without_matching_words_finds_nothing(corpus: Path) -> None:
    assert result(create_server(corpus), "search", {"query": "zebra"}) == []


def test_list_and_read_paper(corpus: Path) -> None:
    srv = create_server(corpus)
    assert result(srv, "list_papers", {}) == [
        {"id": "S001", "title": "Retrieval helps factual question answering", "chars": len(fx.S001)},
        {"id": "S002", "title": "Do retrieved passages reduce hallucination?", "chars": len(fx.S002)}]
    page = result(srv, "read_paper", {"paper_id": "S001", "offset": 10, "limit": 20})
    assert page == {"id": "S001", "text": fx.S001[10:30], "offset": 10, "total": len(fx.S001)}
    assert result(srv, "read_paper", {"paper_id": "S002"})["text"] == fx.S002


def test_read_section_returns_the_block_and_lists_headings_on_a_miss(corpus: Path) -> None:
    srv = create_server(corpus)
    block = result(srv, "read_section", {"paper_id": "S002", "heading": "Setup"})
    assert block["text"].startswith("## Setup\n") and "five passages" in block["text"] and "## Findings" not in block["text"]
    assert block["text"] == fx.S002[block["start"]:block["end"]]
    with pytest.raises(Exception, match="Setup, Findings"):
        run(srv.call_tool("read_section", {"paper_id": "S002", "heading": "Methods"}))


def test_grep_lines_and_bad_regex(corpus: Path) -> None:
    srv = create_server(corpus)
    hits = result(srv, "grep", {"regex": r"\b0\.6\d\b"})
    assert [(h["paper"], h["line"]) for h in hits] == [("S001", 11), ("S001", 13)]
    assert all(fx.S001[h["start"]:].startswith(("0.62", "0.66")) for h in hits)
    assert result(srv, "grep", {"regex": "retriev", "limit": 2}).__len__() == 2
    with pytest.raises(Exception, match="invalid regex"):
        run(srv.call_tool("grep", {"regex": "(unclosed"}))


def test_tables_parse_markdown(corpus: Path) -> None:
    srv = create_server(corpus)
    (table,) = result(srv, "tables", {"paper_id": "S001"})
    assert table["header"] == ["System", "Answer accuracy", "Latency (ms)"]
    assert table["rows"] == [["B", "0.62", "120"], ["R", "0.70", "180"], ["R-noRerank", "0.66", "150"]]
    assert fx.S001[table["start"]:table["end"]].startswith("| System") and fx.S001[table["end"] - 1] == "|"
    assert result(srv, "tables", {"paper_id": "S002"}) == []


def test_unknown_paper_is_an_error_not_empty(corpus: Path) -> None:
    srv = create_server(corpus)
    for name, args in [("read_paper", {"paper_id": "S9"}), ("tables", {"paper_id": "S9"}),
                       ("read_section", {"paper_id": "S9", "heading": "Setup"})]:
        with pytest.raises(Exception, match="unknown paper_id 'S9'"):
            run(srv.call_tool(name, args))


def test_in_process_toolset_serves_the_tools(corpus: Path) -> None:
    """Task 16's agent gets the same server as a pydantic-ai toolset in process (preflight P21), no subprocess."""
    async def go() -> tuple[set[str], Any]:
        async with MCPToolset(create_server(corpus)) as toolset:
            names = {t.name for t in await toolset.client.list_tools()}
            reply = await toolset.client.call_tool("list_papers", {})
            return names, reply.structured_content
    names, listed = run(go())
    assert names == TOOLS and [p["id"] for p in listed["result"]] == ["S001", "S002"]
