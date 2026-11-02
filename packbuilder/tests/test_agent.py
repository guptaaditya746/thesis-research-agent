"""The pack-builder agent (`propose`): it reads the corpus only through the corpus tool server, its proposal passes
the code checks (verbatim quotes, a source for every word, free type prefixes) before any file is written, and its
tool calls land in provenance.json["words"] beside the keys other writers put there. Models are scripted
(FunctionModel) or the exchange model answered by a fake responder: no live model."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from evaluation.tests.helpers import guard_corpus
from evidence.pack import load_pack
from modelcall.exchange import exchange_model
from packbuilder.agent import propose
from packbuilder.server import create_server

TOOLS = {"list_papers", "read_paper", "read_section", "search", "grep", "tables"}

# Two invented trial reports (Velmora is an invented drug).
P1 = """# Velmora in adults with chronic cough

## Methods

Adults were randomised to Velmora or placebo for eight weeks.

## Results

The cough response rate was 41% with Velmora and 22% with placebo.

## Limitations

The sample was small and follow-up was short.
"""
P2 = """# A second trial of Velmora

## Results

Velmora improved the cough response rate over placebo (38% against 25%) in the Northfield Trial.
"""


def write_corpus(root: Path) -> Path:
    """manifest.json and papers/ of two trial reports, with gold files beside them that no system may read."""
    corpus = root / "corpus"
    (corpus / "papers").mkdir(parents=True)
    entries = []
    for pid, text in {"T001": P1, "T002": P2}.items():
        data = text.encode("utf-8")
        (corpus / "papers" / f"{pid}.md").write_bytes(data)
        entries.append({"id": pid, "file": f"papers/{pid}.md", "sha256": hashlib.sha256(data).hexdigest()})
    (corpus / "manifest.json").write_text(json.dumps({"corpus_id": "toy-trials", "papers": entries}), encoding="utf-8")
    (corpus / "ground_truth.json").write_text("{}", encoding="utf-8")
    (corpus / "generator.yaml").write_text("{}", encoding="utf-8")
    return corpus


def src(claim: str, paper: str, quote: str) -> dict[str, str]:
    return {"claim": claim, "paper": paper, "quote": quote}


# A proposal every check accepts: fresh prefixes, every word with a source, every quote verbatim in its paper.
PROPOSAL: dict[str, Any] = {
    "types": {
        "therapy": {"prefix": "th", "role": "compared_thing", "name_field": "label", "side_field": "role"},
        "endpoint": {"prefix": "ep", "role": "metric", "name_field": "name", "canonical_field": "canonical"},
        "readout": {"prefix": "rd", "role": "measured_value", "context_field": "cohort"},
        "cohort": {"prefix": "ch", "role": "context", "name_field": "name"},
    },
    "words": {
        "conditions": {"velmora": [r"\bVelmora\b"], "placebo": [r"(?i)\bplacebo\b"]},
        "not_a_system": r"(?!\s+effects?\b)",
        "metrics": [[r"(?i)\bcough\s+response\s+rate\b", "cough_response_rate", True]],
        "claim_subject": r"\bVelmora\b",
        "claims": [[r"(?i)\bimproved\b", "improves"]],
        "gliner_labels": {"therapy": ["Velmora"]},
        "fraction_metrics": ["cough_response_rate"],
        "dataset_pattern": r"\b[A-Z][a-z]+ Trial\b",
        "metric_supplement": [],
        "screen_terms": ["placebo"],
        "query": {"readout": ["response"]},
    },
    "display": {"treatment": "Velmora", "control": "placebo"},
    "limitation_categories": ["small_sample"],
    "names_seed": {},
    "sources": [
        src("velmora", "T001", "randomised to Velmora or placebo"),
        src(r"\bVelmora\b", "T001", "randomised to Velmora or placebo"),
        src("Velmora", "T001", "randomised to Velmora or placebo"),
        src("placebo", "T001", "randomised to Velmora or placebo"),
        src(r"(?i)\bplacebo\b", "T001", "randomised to Velmora or placebo"),
        src(r"(?i)\bcough\s+response\s+rate\b", "T001", "The cough response rate was 41% with Velmora"),
        src("cough_response_rate", "T001", "The cough response rate was 41% with Velmora"),
        src(r"(?i)\bimproved\b", "T002", "Velmora improved the cough response rate over placebo"),
        src(r"\b[A-Z][a-z]+ Trial\b", "T002", "in the Northfield Trial"),
        src("response", "T002", "Velmora improved the cough response rate over placebo"),
        src("small_sample", "T001", "The sample was small and follow-up was short."),
    ],
}


def proposal(**change: Any) -> dict[str, Any]:
    out = copy.deepcopy(PROPOSAL)
    out.update(change)
    return out


def scripted_tool_agent(calls: list[tuple[str, dict[str, Any]]] = (), final: dict[str, Any] = PROPOSAL) -> FunctionModel:
    """A model that makes the tool `calls` one per turn, then answers `final` through the output tool."""
    def answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        made = sum(isinstance(p, ToolCallPart) and p.tool_name in TOOLS for m in messages for p in m.parts)
        if made < len(calls):
            tool, args = calls[made]
            return ModelResponse(parts=[ToolCallPart(tool, args, tool_call_id=f"call-{made}")])
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, final)])
    return FunctionModel(answer, model_name="scripted-packbuilder")


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    return write_corpus(tmp_path)


def in_process(corpus: Path) -> MCPToolset:
    return MCPToolset(create_server(corpus))


def run(corpus: Path, tmp_path: Path, model: Any, name: str = "toy") -> Path:
    return propose(corpus, name, model=model, cache=tmp_path / "c.jsonl", root=tmp_path / "domains",
                   toolset=in_process(corpus))


def test_agent_runs_with_tools(corpus: Path, tmp_path: Path) -> None:
    (tmp_path / "domains" / "toy").mkdir(parents=True)
    (tmp_path / "domains" / "toy" / "provenance.json").write_text(
        json.dumps({"generator": {"model": "drafter"}, "source": "kept"}), encoding="utf-8")
    path = run(corpus, tmp_path, scripted_tool_agent(calls=[("grep", {"regex": "placebo"}),
                                                            ("read_paper", {"paper_id": "T009"})]))
    prov = json.loads((path / "provenance.json").read_text(encoding="utf-8"))
    call, failed = prov["words"]["tool_calls"]
    assert call["tool"] == "grep" and call["args"] == {"regex": "placebo"} and len(call["result_sha256"]) == 64
    assert "error" not in call and failed["error"] is True        # an unknown paper id: an error the model saw
    words = prov["words"]
    assert words["by"] == "packbuilder propose" and words["model"] == "scripted-packbuilder"
    assert words["corpus_id"] == "toy-trials" and len(words["prompt_sha256"]) == 64
    assert words["files_read"] == ["manifest.json", "papers/T001.md", "papers/T002.md"]
    assert words["sources"] == PROPOSAL["sources"]
    # P3: the other writers' keys stay; the pack.yaml entry is there for freeze
    assert prov["generator"] == {"model": "drafter"} and prov["source"] == "kept"
    assert prov["pack"]["by"] == "packbuilder propose"
    pack = load_pack("toy", root=tmp_path / "domains")
    assert list(pack.words.conditions) == ["velmora", "placebo"]          # the treatment role first, as proposed
    assert pack.types["therapy"].prefix == "th" and pack.display == PROPOSAL["display"]


def test_agent_runs_through_exchange_with_tools(corpus: Path, tmp_path: Path) -> None:
    """The exchange model (preflight P21): the first request lists the six tools; the reply calls grep; the second
    request's prompt holds that call and its result; the reply to it is the proposal."""
    root = tmp_path / "exchange"
    seen: list[dict[str, Any]] = []
    replies = [{"tool_calls": [{"tool": "grep", "args": {"regex": "placebo"}}]}, PROPOSAL]

    def responder() -> None:
        deadline = time.time() + 30
        while replies and time.time() < deadline:
            for f in sorted((root / "pending").glob("*.json")) if (root / "pending").exists() else []:
                if any(r["id"] == f.stem for r in seen):
                    continue
                seen.append(json.loads(f.read_text(encoding="utf-8")))
                (root / "replies").mkdir(parents=True, exist_ok=True)
                tmp = root / "replies" / f"{f.stem}.tmp"       # written whole, then renamed: never read half done
                tmp.write_text(json.dumps(replies.pop(0)), encoding="utf-8")
                os.replace(tmp, root / "replies" / f.name)
            time.sleep(0.02)
    threading.Thread(target=responder, daemon=True).start()
    model = exchange_model(root, "exchange:builder", poll_s=0.02, settle_s=0.05)
    path = run(corpus, tmp_path, model)

    first, second = seen
    assert {t["name"] for t in first["tools"]} == TOOLS and "tool_calls_schema" in first
    assert "[tool call" not in first["prompt"]
    assert '[tool call ' in second["prompt"] and 'grep {"regex": "placebo"}' in second["prompt"]
    assert "[tool result " in second["prompt"] and "randomised to Velmora or placebo" in second["prompt"]
    prov = json.loads((path / "provenance.json").read_text(encoding="utf-8"))
    assert [c["tool"] for c in prov["words"]["tool_calls"]] == ["grep"]
    assert prov["words"]["model"] == "exchange:builder"


def test_non_verbatim_quote_is_rejected(corpus: Path, tmp_path: Path) -> None:
    bad = proposal()
    bad["sources"][0] = src("velmora", "T001", "randomized to Velmora or placebo")   # 'z': not the paper's spelling
    with pytest.raises(ValueError, match="quote"):
        run(corpus, tmp_path, scripted_tool_agent(final=bad))
    assert not (tmp_path / "domains" / "toy" / "pack.yaml").exists()


def test_word_without_a_source_is_rejected(corpus: Path, tmp_path: Path) -> None:
    bad = proposal(limitation_categories=["small_sample", "high_cost"])
    with pytest.raises(ValueError, match="no source.*high_cost"):
        run(corpus, tmp_path, scripted_tool_agent(final=bad))


def test_pattern_must_match_its_quote(corpus: Path, tmp_path: Path) -> None:
    bad = proposal()
    bad["sources"] = [s if s["claim"] != r"(?i)\bimproved\b" else src(s["claim"], "T001", "The sample was small")
                      for s in bad["sources"]]
    with pytest.raises(ValueError, match="matches none of its quotes"):
        run(corpus, tmp_path, scripted_tool_agent(final=bad))


def test_prefix_of_another_pack_is_rejected(corpus: Path, tmp_path: Path) -> None:
    """P22: prefixes are global; rag's `c` and the drugtoy fixture's `xa` are taken by other type names."""
    for prefix, owner in (("c", "condition"), ("xa", "arm")):
        bad = proposal()
        bad["types"]["therapy"]["prefix"] = prefix
        with pytest.raises(ValueError, match=f"prefix '{prefix}'.*'{owner}'"):
            run(corpus, tmp_path, scripted_tool_agent(final=bad))
    # the same type name with its own prefix is the same type: allowed
    same = proposal()
    same["types"]["arm"] = same["types"].pop("therapy") | {"prefix": "xa"}
    same["words"]["gliner_labels"] = {"arm": ["Velmora"]}
    run(corpus, tmp_path, scripted_tool_agent(final=same))


def test_the_agent_never_opens_a_gold_file(monkeypatch: pytest.MonkeyPatch, corpus: Path, tmp_path: Path) -> None:
    attempts = guard_corpus(monkeypatch, corpus)
    run(corpus, tmp_path, scripted_tool_agent(calls=[("list_papers", {}), ("read_paper", {"paper_id": "T002"})]))
    assert attempts == []


def test_a_cached_proposal_makes_no_model_call(corpus: Path, tmp_path: Path) -> None:
    run(corpus, tmp_path, scripted_tool_agent(calls=[("grep", {"regex": "placebo"})]))

    def no_call(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise AssertionError("the model was called")
    again = propose(corpus, "toy", model=FunctionModel(no_call, model_name="scripted-packbuilder"),
                    cache=tmp_path / "c.jsonl", root=tmp_path / "again", toolset=in_process(corpus))
    prov = json.loads((again / "provenance.json").read_text(encoding="utf-8"))
    assert [c["tool"] for c in prov["words"]["tool_calls"]] == ["grep"]
    assert yaml.safe_load((again / "words.yaml").read_text(encoding="utf-8"))["screen_terms"] == ["placebo"]


def test_an_existing_pack_is_never_replaced(corpus: Path, tmp_path: Path) -> None:
    run(corpus, tmp_path, scripted_tool_agent())
    with pytest.raises(ValueError, match="exists"):
        run(corpus, tmp_path, scripted_tool_agent())
