"""The pack-builder agent: a model reads one corpus through the corpus tool server (server.py) and proposes the
extraction pack of a topic (`PackProposal`); code checks the proposal (proposal.py) and writes
`<root>/<name>/pack.yaml`, `words.yaml` and the log in `provenance.json`.

    propose(corpus, name, *, model, verify_model, cache, root=DOMAINS, toolset=None, question=DEFAULT_QUESTION)
        -> <root>/<name>

- The model sees the corpus only through the six tools. By default they come from `packbuilder serve` over stdio
  (`uv run packbuilder serve --corpus DIR`); tests pass `toolset=MCPToolset(create_server(corpus))`, the same server
  in process (preflight P21).
- A proposal that fails a check goes back to the model with the failed checks (pydantic-ai output retries,
  OUTPUT_RETRIES); when the retries run out, `propose` raises ValueError naming them. Nothing is written then.
- Proposing and checking are separate (docs/prompt-writing.md): `verify_model` judges every proposed word
  against its slot and its quotes (prompts/propose-check-v1.md, one call); the words it rejects are dropped from the
  pack (proposal.drop) and listed in provenance. A rejected required word (claim subject, context pattern, display
  name), or a pack left without two condition roles or a metric, refuses. No verify model: refused.
- The run is cached in `cache` (modelcall.JsonlCache) under the prompt, the model, the corpus (its id and every
  paper's sha256) and the user prompt: a rerun makes no model call. Only a proposal that passed is cached.
- provenance.json is merged, never overwritten (preflight P3): `words` = {by, model, prompt_sha256, corpus_id,
  tool_calls: [{tool, args, result_sha256}], sources, files_read, verify: {model, prompt_sha256, verdicts: [{word,
  slot, ok, reason}], dropped: [{word, slot, reason}]}}, `pack` = {by, model, prompt_sha256, corpus_id};
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
from pydantic import Field
from pydantic_ai import Agent, ModelRetry, ToolOutput, UnexpectedModelBehavior
from pydantic_ai.mcp import MCPToolset, StdioTransport
from pydantic_ai.messages import ModelMessage, RetryPromptPart, ToolCallPart, ToolReturnPart
from pydantic_ai.toolsets import AbstractToolset

from evaluation.baselines.common import SystemCorpus
from evidence.pack import DOMAINS, load_pack
from evidence.protocol import Strict
from jsonio import sha256_hex
from modelcall import (CallSettings, JsonlCache, ask_sync, cache_key, default_key, load_prompt, model_identity,
                       model_name)
from modelcall.loop import run_sync
from packbuilder.proposal import (DISPLAY_KEYS, FIXTURE_ROOTS, REPO, Known, PackProposal, Slot, drop, known_prefixes,
                                  problems, word_slots)

PROMPT = Path(__file__).resolve().parent / "prompts" / "propose-v1.md"
CHECK_PROMPT = Path(__file__).resolve().parent / "prompts" / "propose-check-v1.md"
BY = "packbuilder propose"
OUTPUT_TOOL = "pack_proposal"        # the output tool's name: its call is the proposal, not a corpus tool call
OUTPUT_RETRIES = 2                   # proposals that failed a check sent back to the model
TOOL_RETRIES = 3                     # tool errors (an unknown paper id, a bad regex) sent back to the model
SETTINGS = CallSettings(max_tokens=16384)   # a proposal with a source per word is long
DEFAULT_QUESTION = "What do the papers compare, on which metrics, and with which measured results?"


class Verdict(Strict):
    id: int
    ok: bool
    reason: str = Field(description="one short sentence a reader can check against the quotes")


class Verdicts(Strict):
    verdicts: list[Verdict]


def stdio_toolset(corpus: Path) -> MCPToolset:
    """The corpus tool server as a subprocess over stdio, run in this repo whatever the current folder."""
    return MCPToolset(StdioTransport("uv", ["run", "packbuilder", "serve", "--corpus", str(Path(corpus).resolve())],
                                     cwd=str(REPO)))


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
        failed.clear()                   # only the last proposal's failures name the reason a run gave up
        found = problems(proposal, papers, known)
        if found:
            failed[:] = found
            raise ModelRetry("The proposal fails these checks; fix each one:\n- " + "\n- ".join(found))
        return proposal

    try:
        result = await agent.run(text, model_settings=SETTINGS.model_settings())
    except UnexpectedModelBehavior as exc:
        if failed:
            raise ValueError(f"the proposal fails its checks: {'; '.join(failed)} ({exc})") from None
        raise ValueError(f"the pack-builder run failed: {exc}") from None
    return result.output, tool_log(result.all_messages())


def verify(proposal: PackProposal, question: str, *, verify_model: Any, cache: JsonlCache
           ) -> tuple[list[dict[str, Any]], list[Slot], str]:
    """The verifier's verdict on every word of `proposal` (word_slots): (log [{word, slot, ok, reason}], the slots
    it rejected, the check prompt's sha256). A verdict list that misses, repeats or invents an id is refused."""
    items = word_slots(proposal)
    quotes: dict[str, list[dict[str, str]]] = {}
    for src in proposal.sources:
        quotes.setdefault(src.claim, []).append({"paper": src.paper, "quote": src.quote})
    text = json.dumps({"question": question, "words": [{"id": n, "word": word, "slot": slot, "quotes": quotes.get(word, [])}
                                                       for n, (word, slot, _) in enumerate(items, 1)]},
                      indent=1, ensure_ascii=False)
    prompt = load_prompt(CHECK_PROMPT, Verdicts)
    out = ask_sync(prompt, text, model=verify_model, settings=SETTINGS, cache=cache,
                   key=default_key(prompt, text, verify_model, SETTINGS)).output
    ids = [v.id for v in out.verdicts]
    if sorted(ids) != list(range(1, len(items) + 1)):
        raise ValueError(f"the verifier must give one verdict per word, ids 1-{len(items)}; it gave {sorted(ids)}")
    by_id = {v.id: v for v in out.verdicts}
    log = [{"word": word, "slot": slot, "ok": by_id[n].ok, "reason": by_id[n].reason}
           for n, (word, slot, _) in enumerate(items, 1)]
    rejected = [loc for n, (_, _, loc) in enumerate(items, 1) if not by_id[n].ok]
    return log, rejected, prompt.sha256


def propose(corpus: Path, name: str, *, model: Any, cache: Path, verify_model: Any = None, root: Path = DOMAINS,
            toolset: AbstractToolset[Any] | None = None, question: str = DEFAULT_QUESTION) -> Path:
    """Propose the pack `name` from the papers of `corpus`, have `verify_model` judge each word, and write the pack
    to `root/name/`; returns that folder."""
    if verify_model is None:
        raise ValueError("propose needs a verify model (verify_model / --verify-model): a second model checks every "
                         "proposed word against its quotes before the pack is written")
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
        proposal, log = PackProposal.model_validate_json(hit["output_json"]), hit["tool_calls"]
    else:
        proposal, log = run_sync(_run(model, toolset or stdio_toolset(corpus), prompt.text, text, papers, known))
    found = problems(proposal, papers, known)       # again: a cached or validated proposal is checked here too
    if found:
        raise ValueError("the proposal fails its checks: " + "; ".join(found))
    if hit is None:
        # kept as a JSON string: the cache writes its values with sorted keys, which would reorder `conditions`,
        # whose first role is the treatment
        calls.put(key, {"output_json": proposal.model_dump_json(), "tool_calls": log, "model": model_name(model)})
    verdicts, rejected, check_sha = verify(proposal, question, verify_model=verify_model, cache=calls)
    proposal = drop(proposal, rejected)
    found = problems(proposal, papers, known)       # what is left still passes every check
    if found:
        raise ValueError("the proposal fails its checks after the verifier's rejections: " + "; ".join(found))

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
                  "files_read": files_read,
                  "verify": {"model": model_name(verify_model), "prompt_sha256": check_sha, "verdicts": verdicts,
                             "dropped": [{k: v[k] for k in ("word", "slot", "reason")}
                                         for v in verdicts if not v["ok"]]}}})
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
