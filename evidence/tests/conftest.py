"""Fixtures for the evidence tests: a small corpus of hand-written papers (with poison files the engine must
never open) and a scripted model (pydantic-ai FunctionModel, no network)."""
from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from jsonio import sha256_hex

HERE = Path(__file__).resolve().parent
PAPERS = HERE / "fixtures" / "papers"
PROTOCOL = HERE.parent / "protocols" / "rag-factuality.yaml"
POISON = ("ground_truth.json", "corpus.json", "fidelity.json")
DOCS = ("S001", "S002", "S003", "S004", "S005")


def make_corpus(root: Path, docs: tuple[str, ...] = DOCS) -> Path:
    (root / "papers").mkdir(parents=True)
    papers = []
    for doc in docs:
        data = (PAPERS / f"{doc}.md").read_bytes().replace(b"\r\n", b"\n")  # LF whatever the checkout
        (root / "papers" / f"{doc}.md").write_bytes(data)
        papers.append({"id": doc, "file": f"papers/{doc}.md", "sha256": sha256_hex(data)})
    (root / "manifest.json").write_text(json.dumps({"corpus_id": "test-corpus", "papers": papers}), encoding="utf-8")
    for name in POISON:  # a system under test must never read these
        (root / name).write_text('{"poison": "the engine must not read this file"}', encoding="utf-8")
    return root


def corpus_of(root: Path, docs: dict[str, str]) -> Path:
    """A corpus from paper texts given inline (id -> Markdown)."""
    (root / "papers").mkdir(parents=True)
    papers = []
    for doc, text in docs.items():
        data = text.encode("utf-8")
        (root / "papers" / f"{doc}.md").write_bytes(data)
        papers.append({"id": doc, "file": f"papers/{doc}.md", "sha256": sha256_hex(data)})
    (root / "manifest.json").write_text(json.dumps({"corpus_id": "inline", "papers": papers}), encoding="utf-8")
    return root


def regex_run(docs: dict[str, str], tmp: Path, protocol: Path = PROTOCOL) -> tuple[dict[str, Any], dict[str, Any]]:
    """(answer.json, evidence items by id) of a regex-only run over inline papers."""
    from evidence import engine
    run = engine.run(protocol, corpus_of(tmp / "corpus", docs), tmp / "runs", selection="regex-only", provider=None,
                     strategy="all")
    items = [json.loads(x) for x in (run / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    return json.loads((run / "answer.json").read_text(encoding="utf-8")), {i["item_id"]: i for i in items}


def measurements(items: dict[str, Any], doc: str) -> list[tuple[str, float]]:
    """(condition role, value) of a document's measurements, by value position."""
    out = []
    for i in items.values():
        if i["evidence_type"] == "measurement" and i["spans"][0]["selector"]["file"] == f"papers/{doc}.md":
            start = min(s["selector"]["start"] for s in i["spans"] if s["role"] == "value")
            out.append((start, items[i["links"]["condition"]]["fields"]["role"], i["fields"]["value"]))
    return [(role, value) for _, role, value in sorted(out)]


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    return make_corpus(tmp_path / "corpus")


@pytest.fixture
def protocol_file(tmp_path: Path) -> Path:
    path = tmp_path / "protocol.yaml"
    shutil.copyfile(PROTOCOL, path)
    return path


def prompt_of(messages: list[ModelMessage]) -> str:
    return "\n".join(str(p.content) for m in messages for p in m.parts if isinstance(p, UserPromptPart))


def respond(info: AgentInfo, args: dict[str, Any]) -> ModelResponse:
    """The reply in the output mode modelcall.ask chose: an output tool call, or JSON text."""
    if info.output_tools:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])
    return ModelResponse(parts=[TextPart(json.dumps(args))])


Script = Callable[[str, str, str], dict[str, Any]]   # (evidence type, document, prompt) -> reply args


def scripted(script: Script, calls: list[str], name: str = "scripted") -> FunctionModel:
    """A model whose reply is `script(evidence type, document, prompt)`; every prompt is appended to `calls`.
    The funnel's screening call (prompts/screen-v1.md) is passed as evidence type "screen"."""
    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = prompt_of(messages)
        calls.append(prompt)
        found = re.search(r"Evidence type: (\w+)", info.instructions or "")
        doc = re.search(r"Paper (\S+), part", prompt)
        if "Rejected quotes:" in prompt:
            return respond(info, script("retry", doc.group(1) if doc else "", prompt))
        kind = "screen" if "Screening question:" in (info.instructions or "") else found.group(1) if found else ""
        return respond(info, script(kind, doc.group(1) if doc else "", prompt))
    return FunctionModel(reply, model_name=name)


def paper_text(prompt: str) -> str:
    """The document text inside a user prompt (between <<< and >>>)."""
    return prompt.split("<<<\n", 1)[1].rsplit("\n>>>", 1)[0]


def screen_yes(prompt: str, reason: str = "the paper compares retrieval with no retrieval") -> dict[str, Any]:
    """A relevant decision whose quote is the paper's title line (so it anchors)."""
    title = next(line for line in paper_text(prompt).splitlines() if line.strip()).lstrip("# ").strip()
    return {"relevant": True, "reason": reason, "quote": title}


def provider_of(model: FunctionModel) -> Callable[[str], FunctionModel]:
    return lambda alias: model


def context_id(prompt: str, fragment: str) -> str:
    """The local id ("c1") the prompt gives the context item whose fields contain `fragment`."""
    for line in prompt.splitlines():
        hit = re.match(r"- (\w+) \(\w+\): (.*)$", line)
        if hit and fragment in hit.group(2):
            return hit.group(1)
    raise AssertionError(f"no context item with {fragment!r} in the prompt")


def empty(evidence_type: str, doc: str, prompt: str) -> dict[str, Any]:
    if evidence_type == "screen":
        return screen_yes(prompt)
    return {"items": []} if evidence_type != "retry" else {"quotes": []}
