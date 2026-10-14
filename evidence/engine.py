"""The execution engine: run a protocol over a corpus and write the run directory (interfaces §3).

Per document (manifest order) and evidence type (the protocol's dependency order): locate the scope, give
each extractor of the type's cascade one task (the document, the scope, the merged items of the context
types), check every result centrally (evidence/checks.py), merge the cascade (evidence/merge.py), and pass
the merged items on as context. Then synthesis (answer.json) and the evidence graph. Every locate,
extractor call, merge and the synthesis is one record of the hash-chained events.jsonl; every call's
checked result is calls/<call_id>.json, where the call id is the task id of its record.

`replay` rebuilds a run from the record cache only and checks every output hash against the recorded
run.json; `reexec` runs extractors again, bypassing the cache, and reports the differences (reexec.json).
"""
from __future__ import annotations

import importlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from agent.anchor import Index
from agent.canonical import sha256_hex
from agent.rundir import utc_now
from gold.llm import JsonlCache

from . import checks, extractors, graph, merge, synthesis
from .calls import CallCache, EngineContext, Mode, NotRecorded
from .contract import ExtractionTask, Extractor, ExtractorSpec, Item, ProtocolRef
from .locate import Locator, locate
from .protocol import EvidenceTypeSpec, ExtractorRef, Protocol, parse
from .recording import Provider, usage
from .rundir import (ANSWER_FILE, CACHE_FILE, CALLS_DIR, EVENTS_FILE, EVIDENCE_FILE, GRAPH_FILE, LOCATE_FILE,
                     PROTOCOL_FILE, RUN_FILE, Corpus, Events, new_run_id, write_canonical, write_lines)

Selection = Literal["cascade", "regex-only", "llm-only"]
KINDS: dict[str, tuple[str, ...]] = {"cascade": ("regex", "model", "llm", "agent"), "regex-only": ("regex",),
                                     "llm-only": ("llm",)}
__all__ = ["NotRecorded", "Settings", "build_extractors", "execute_run", "run"]


@dataclass
class Settings:
    """What a run needs besides the protocol; recorded in run.json so replay and reexec repeat it."""
    corpus: str
    cache: str
    selection: Selection = "cascade"
    model: str | None = None                       # model alias for llm/agent extractors (overrides the protocol)
    imports: list[str] = field(default_factory=list)   # modules that register more extractors

    def json(self) -> dict[str, Any]:
        return {"corpus": self.corpus, "cache": self.cache, "selection": self.selection, "model": self.model,
                "imports": list(self.imports)}


def default_provider(alias: str) -> Any:
    from gold.llm import openai_model  # the key comes from $LITELLM_MASTER_KEY only
    return openai_model(alias)


def build_extractors(protocol: Protocol, selection: Selection = "cascade",
                     model: str | None = None) -> dict[str, list[tuple[ExtractorRef, Extractor]]]:
    """The cascade per evidence type, built from the registry with the type's schema added to each config."""
    out: dict[str, list[tuple[ExtractorRef, Extractor]]] = {}
    for etype, spec in protocol.evidence_types.items():
        chosen = []
        for ref in spec.extractors:
            config = {**ref.config, "evidence_type": etype, "field_schema": spec.fields, "links": dict(spec.links),
                      "roles": list(spec.roles), "description": spec.description}
            extractor = extractors.get(ref.name, config)
            if model and extractor.spec.kind in ("llm", "agent"):
                extractor = extractors.get(ref.name, {**config, "model": model})
            if extractor.spec.kind in KINDS[selection]:
                chosen.append((ref, extractor))
        out[etype] = chosen
    return out


class Execution:
    """One pass over the corpus; collects everything the run directory holds."""

    def __init__(self, protocol: Protocol, corpus: Corpus, root: Path, run_id: str, calls: CallCache,
                 cascades: dict[str, list[tuple[ExtractorRef, Extractor]]], provider: Provider | None,
                 locator: Locator | None) -> None:
        self.protocol, self.corpus, self.root, self.calls = protocol, corpus, root, calls
        self.cascades, self.provider, self.locator = cascades, provider, locator
        self.events = Events(root / EVENTS_FILE, run_id)
        self.ref = ProtocolRef(id=protocol.id, sha256=protocol.sha256)
        self.outputs: dict[str, str] = {}
        self.located: list[dict[str, Any]] = []
        self.items: dict[str, list[Item]] = {}
        self.cost = {"calls": 0, "cached_calls": 0, "model_calls": 0, "made_model_calls": 0, "input_tokens": 0,
                     "output_tokens": 0}

    def document(self, paper: Any) -> None:
        text = self.corpus.text(paper)
        index = Index(text)
        doc = paper.ref
        merged: dict[str, list[Item]] = {}
        for etype in self.protocol.phases():
            spec = self.protocol.evidence_types[etype]
            found = locate(self.protocol.locate, doc, text, etype, spec, self.locator)
            self.located.append({"document": doc.id, "evidence_type": etype, "strategy": self.protocol.locate.strategy,
                                 **found.json()})
            self.events.add("locate", used=[doc.sha256], generated=[], agent_id=f"locate:{self.protocol.locate.strategy}",
                            group_id=doc.id, custom={"document": doc.id, "evidence_type": etype,
                                                     "scope": found.scope.model_dump(mode="json")})
            context = [i for t in spec.context for i in merged.get(t, [])]
            results = []
            for position, (ref, extractor) in enumerate(self.cascades.get(etype, [])):
                if spec.cascade == "until_found" and any(r.items for _, r in results):
                    break
                task = ExtractionTask(protocol=self.ref, evidence_type=etype,  # type: ignore[arg-type]
                                      field_schema_sha256=spec.schema_sha256, document=doc, scope=found.scope,
                                      context=tuple(i.item_id for i in context),
                                      budget=ref.budget if extractor.spec.kind == "agent" else None)
                results.append(self._call(extractor, task, text, index, spec, context, position))
            items, sources, collisions = merge.merge(results, spec)
            merged[etype] = items
            self.events.add("merge", used=sorted({i.item_id for _, r in results for i in r.items}),
                            generated=[i.item_id for i in items], agent_id="evidence-engine", group_id=doc.id,
                            custom={"document": doc.id, "evidence_type": etype, "sources": sources,
                                    "collisions": collisions})
        self.items[doc.id] = sorted((i for t in merged.values() for i in t),
                                    key=lambda i: (i.first_start(), i.evidence_type, i.item_id))

    def _call(self, extractor: Extractor, task: ExtractionTask, text: str, index: Index, spec: EvidenceTypeSpec,
              context: list[Item], position: int = 0) -> tuple[str, Any]:
        started = utc_now()
        outcome = self.calls.call(extractor, task, lambda: EngineContext(text, index, context, spec.fields, self.provider))
        result = checks.check(outcome.raw, task, index, spec, {i.item_id: i for i in context})
        call_id = self.events.next_id()
        result = result.model_copy(update={"call_id": call_id})
        self.outputs[f"{CALLS_DIR}/{call_id}.json"] = write_canonical(self.root / CALLS_DIR / f"{call_id}.json",
                                                                       result.model_dump(mode="json"))
        tokens_in, tokens_out = usage(outcome.model_calls)
        self.cost["calls"] += 1
        self.cost["cached_calls"] += outcome.source == "cache"
        self.cost["model_calls"] += len(outcome.model_calls)
        self.cost["made_model_calls"] += len(outcome.model_calls) if outcome.source == "fresh" else 0
        self.cost["input_tokens"] += tokens_in
        self.cost["output_tokens"] += tokens_out
        self.events.add("extractor_call", used=[task.document.sha256, task.protocol.sha256, *task.context],
                        generated=[i.item_id for i in result.items], agent_id=extractor.spec.extractor_id,
                        status=result.status, group_id=task.document.id, started_at=started,
                        custom={"task_sha256": task.task_sha256, "output_sha256": result.output_sha256,
                                "model_calls": list(result.model_calls), "document": task.document.id,
                                "evidence_type": task.evidence_type, "source": outcome.source,
                                "attempt": outcome.attempt, "position": position,
                                "rejected": len(result.rejected)})
        return call_id, result

    def finish(self) -> dict[str, Any]:
        papers = self.corpus.papers
        answer, used = synthesis.answer(self.protocol, [p.id for p in papers], self.items)
        evidence = [i.model_dump(mode="json") for p in papers for i in self.items.get(p.id, [])]
        self.outputs[LOCATE_FILE] = write_canonical(self.root / LOCATE_FILE, self.located)
        self.outputs[EVIDENCE_FILE] = write_lines(self.root / EVIDENCE_FILE, evidence)
        self.outputs[ANSWER_FILE] = write_canonical(self.root / ANSWER_FILE, answer)
        self.outputs[GRAPH_FILE] = write_canonical(self.root / GRAPH_FILE, graph.build(papers, self.items, answer))
        self.events.add("synthesis", used=sorted(set(used)), generated=["answer"], agent_id="evidence-engine",
                        custom={"label": answer["label"], "counts": answer["counts"],
                                "answer_sha256": self.outputs[ANSWER_FILE], "rule": self.protocol.synthesis.label_rule})
        return answer


def execute_run(protocol_bytes: bytes, settings: Settings, out_dir: Path | str, *, mode: Mode = "run",
                run_id: str | None = None, provider: Provider | None = None, locator: Locator | None = None,
                bypass: Any = None, retry_errors: bool = False, source_run: str | None = None,
                attempts: dict[str, int] | None = None) -> Path:
    """Execute and write one run directory; returns its path."""
    for module in settings.imports:
        importlib.import_module(module)
    protocol = parse(protocol_bytes.decode("utf-8"))
    corpus = Corpus(settings.corpus)
    run_id = run_id or new_run_id(protocol.id, "" if mode == "run" else f"-{mode}")
    root = Path(out_dir) / run_id
    root.mkdir(parents=True, exist_ok=False)
    (root / PROTOCOL_FILE).write_bytes(protocol_bytes)
    cascades = build_extractors(protocol, settings.selection, settings.model)
    cache = CallCache(JsonlCache(Path(settings.cache) / CACHE_FILE), mode, bypass, retry_errors, attempts)
    ex = Execution(protocol, corpus, root, run_id, cache, cascades, provider, locator)
    ex.outputs[PROTOCOL_FILE] = sha256_hex(protocol_bytes)
    t0 = time.monotonic()
    for paper in corpus.papers:
        ex.document(paper)
    ex.finish()
    ex.cost["seconds"] = round(time.monotonic() - t0, 3)
    specs = {e.spec.extractor_id: e.spec for c in cascades.values() for _, e in c}
    write_canonical(root / RUN_FILE, {
        "run_id": run_id, "mode": mode, "source_run": source_run, "protocol": {"id": protocol.id, "sha256": protocol.sha256},
        "manifest_sha256": corpus.manifest_sha256, "corpus_id": corpus.corpus_id, "extractors": list(specs),
        "extractor_specs": {k: _spec_json(s) for k, s in specs.items()}, "outputs": dict(sorted(ex.outputs.items())),
        "cost": ex.cost, "chain_head": ex.events.head, "settings": settings.json()})
    return root


def _spec_json(spec: ExtractorSpec) -> dict[str, Any]:
    return {**spec.model_dump(mode="json"), "config_sha256": spec.config_sha256, "extractor_id": spec.extractor_id}


def run(protocol_path: Path | str, corpus: Path | str, out_dir: Path | str, *, cache: Path | str | None = None,
        selection: Selection = "cascade", model: str | None = None, imports: list[str] | None = None,
        provider: Provider | None = None, locator: Locator | None = None, run_id: str | None = None,
        retry_errors: bool = False) -> Path:
    """A normal run: cached calls are reused, new ones are made and stored."""
    settings = Settings(corpus=str(Path(corpus).resolve()),
                        cache=str((Path(cache) if cache else Path(out_dir) / "cache").resolve()),
                        selection=selection, model=model, imports=list(imports or []))
    return execute_run(Path(protocol_path).read_bytes(), settings, out_dir, run_id=run_id,
                       provider=provider if provider is not None else default_provider, locator=locator,
                       retry_errors=retry_errors)
