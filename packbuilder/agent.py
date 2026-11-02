"""The pack-builder agent: a model reads one corpus through the corpus tool server (server.py) and proposes the
extraction pack of a topic (`PackProposal`); code checks the proposal (proposal.py) and writes
`<root>/<name>/pack.yaml`, `words.yaml` and the log in `provenance.json`.

    propose(corpus, name, *, model, cache, root=DOMAINS, toolset=None, question=DEFAULT_QUESTION) -> <root>/<name>

- The model sees the corpus only through the six tools. By default they come from `packbuilder serve` over stdio
  (`uv run packbuilder serve --corpus DIR`); tests pass `toolset=MCPToolset(create_server(corpus))`, the same server
  in process (preflight P21).
- A proposal that fails a check goes back to the model with the failed checks (pydantic-ai output retries,
  OUTPUT_RETRIES); when the retries run out, `propose` raises ValueError naming them. Nothing is written then.
- The run is cached in `cache` (modelcall.JsonlCache) under the prompt, the model, the corpus (its id and every
  paper's sha256) and the user prompt: a rerun makes no model call. Only a proposal that passed is cached.
- provenance.json is merged, never overwritten (preflight P3): `words` = {by, model, prompt_sha256, corpus_id,
  tool_calls: [{tool, args, result_sha256}], sources, files_read}, `pack` = {by, model, prompt_sha256, corpus_id};
  every other key (a drafted recipe's `generator`, a hand-written `source`) stays. `files_read` are the corpus files
  the tool server read: manifest.json and papers/*, never anything else.
- An existing pack.yaml or words.yaml is never replaced.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from pydantic_ai import Agent, ModelRetry, ToolOutput, UnexpectedModelBehavior
from pydantic_ai.mcp import MCPToolset, StdioTransport
from pydantic_ai.messages import ModelMessage, RetryPromptPart, ToolCallPart, ToolReturnPart
from pydantic_ai.toolsets import AbstractToolset

from evaluation.baselines.common import SystemCorpus
from evidence.pack import DOMAINS, load_pack
from jsonio import sha256_hex
from modelcall import CallSettings, JsonlCache, cache_key, load_prompt, model_identity, model_name
from modelcall.loop import run_sync
from packbuilder.proposal import DISPLAY_KEYS, FIXTURE_ROOTS, Known, PackProposal, known_prefixes, problems

PROMPT = Path(__file__).resolve().parent / "prompts" / "propose-v1.md"
BY = "packbuilder propose"
OUTPUT_TOOL = "pack_proposal"        # the output tool's name: its call is the proposal, not a corpus tool call
OUTPUT_RETRIES = 2                   # proposals that failed a check sent back to the model
TOOL_RETRIES = 3                     # tool errors (an unknown paper id, a bad regex) sent back to the model
SETTINGS = CallSettings(max_tokens=16384)   # a proposal with a source per word is long
DEFAULT_QUESTION = "What do the papers compare, on which metrics, and with which measured results?"


def stdio_toolset(corpus: Path) -> MCPToolset:
    """The corpus tool server as a subprocess over stdio."""
    return MCPToolset(StdioTransport("uv", ["run", "packbuilder", "serve", "--corpus", str(corpus)]))


def user_prompt(question: str, known: Known) -> str:
    """The input of the propose prompt: the question, the display keys and the prefixes in use."""
    taken = sorted({f"{name}: {prefix}" for name, prefix, _ in known})
    return json.dumps({"question": question, "display_keys": list(DISPLAY_KEYS), "taken_prefixes": taken},
                      indent=1, ensure_ascii=False)


def _sha(value: Any) -> str:
    return sha256_hex(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8"))


def tool_log(messages: list[ModelMessage]) -> list[dict[str, Any]]:
    """The corpus tool calls of a run, in order: {tool, args, result_sha256}, and `error: true` when the tool
    raised (its result is then the error text sent back to the model). The output tool's call is not one."""
    results: dict[str, tuple[Any, bool]] = {}
    for m in messages:
        for p in m.parts:
            if isinstance(p, ToolReturnPart):
                results[p.tool_call_id] = (p.content, False)
            elif isinstance(p, RetryPromptPart) and p.tool_name:
                results[p.tool_call_id] = (p.model_response(), True)
    log = []
    for m in messages:
        for p in m.parts:
            if isinstance(p, ToolCallPart) and p.tool_name != OUTPUT_TOOL:
                result, error = results.get(p.tool_call_id, (None, True))
                log.append({"tool": p.tool_name, "args": p.args_as_dict(), "result_sha256": _sha(result),
                            **({"error": True} if error else {})})
    return log


async def _run(model: Any, toolset: AbstractToolset[Any], instructions: str, text: str, papers: dict[str, str],
               known: Known) -> tuple[PackProposal, list[dict[str, Any]]]:
    agent: Agent[None, PackProposal] = Agent(
        model, instructions=instructions, toolsets=[toolset], retries=TOOL_RETRIES,
        output_type=ToolOutput(PackProposal, name=OUTPUT_TOOL, max_retries=OUTPUT_RETRIES))
    failed: list[str] = []

    @agent.output_validator
    def checked(proposal: PackProposal) -> PackProposal:
        found = problems(proposal, papers, known)
        if found:
            failed[:] = found
            raise ModelRetry("The proposal fails these checks; fix each one:\n- " + "\n- ".join(found))
        return proposal

    try:
        result = await agent.run(text, model_settings=SETTINGS.model_settings())
    except UnexpectedModelBehavior as exc:
        if failed:
            raise ValueError("the proposal fails its checks: " + "; ".join(failed)) from None
        raise ValueError(f"the pack-builder run failed: {exc}") from None
    return result.output, tool_log(result.all_messages())


def propose(corpus: Path, name: str, *, model: Any, cache: Path, root: Path = DOMAINS,
            toolset: AbstractToolset[Any] | None = None, question: str = DEFAULT_QUESTION) -> Path:
    """Propose the pack `name` from the papers of `corpus` and write it to `root/name/`; returns that folder."""
    corpus, root = Path(corpus), Path(root)
    folder = root / name
    for existing in ("pack.yaml", "words.yaml"):
        if (folder / existing).exists():
            raise ValueError(f"{folder / existing} exists: a proposed pack never replaces one already there")
    read = SystemCorpus(corpus)          # what the tool server reads: manifest.json and papers/ only
    files_read = ["manifest.json", *(p.file for p in read.papers)]
    stray = [f for f in files_read if f != "manifest.json" and PurePosixPath(f).parent != PurePosixPath("papers")]
    if stray:
        raise ValueError(f"the corpus server would read {stray}: only manifest.json and papers/* may be read")
    papers = {p.id: p.text for p in read.papers}
    known = known_prefixes([DOMAINS, root, *FIXTURE_ROOTS], skip=folder)
    prompt = load_prompt(PROMPT, PackProposal)
    text = user_prompt(question, known)
    calls = JsonlCache(cache)
    key = cache_key({"prompt_sha256": prompt.sha256, "model": model_identity([model]),
                     "corpus": {"id": read.corpus_id, "papers": {p.id: sha256_hex(p.text.encode("utf-8"))
                                                                 for p in read.papers}},
                     "input_sha256": sha256_hex(text.encode("utf-8")), "settings": asdict(SETTINGS)})
    hit = calls.get(key)
    if hit is not None:
        proposal, log = PackProposal.model_validate(hit["output"]), hit["tool_calls"]
    else:
        proposal, log = run_sync(_run(model, toolset or stdio_toolset(corpus), prompt.text, text, papers, known))
    found = problems(proposal, papers, known)       # again: a cached or validated proposal is checked here too
    if found:
        raise ValueError("the proposal fails its checks: " + "; ".join(found))
    if hit is None:
        calls.put(key, {"output": proposal.model_dump(mode="json"), "tool_calls": log, "model": model_name(model)})

    head = {"name": name, "types": {t: d.model_dump(mode="json", exclude_none=True) for t, d in proposal.types.items()},
            "display": proposal.display, "names_seed": proposal.names_seed,
            "limitation_categories": proposal.limitation_categories}
    folder.mkdir(parents=True, exist_ok=True)
    _dump(folder / "pack.yaml", head)
    _dump(folder / "words.yaml", proposal.words.model_dump(mode="json"))
    common = {"by": BY, "model": model_name(model), "prompt_sha256": prompt.sha256, "corpus_id": read.corpus_id}
    _log(folder / "provenance.json", {
        "pack": common,
        "words": {**common, "tool_calls": log, "sources": [s.model_dump() for s in proposal.sources],
                  "files_read": files_read}})
    load_pack(name, root=root)           # reads back as a valid pack
    return folder


def _dump(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8",
                    newline="\n")


def _log(path: Path, entries: dict[str, dict[str, Any]]) -> None:
    """Merge each entry into provenance.json[key] (P3: a writer merges; every other key stays)."""
    prov = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    for key, entry in entries.items():
        prov[key] = {**prov.get(key, {}), **entry}
    path.write_text(json.dumps(prov, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
