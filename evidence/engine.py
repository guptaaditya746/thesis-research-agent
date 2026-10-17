"""The execution engine: run a protocol over a corpus and write the run directory (interfaces §3).

Per document (manifest order): when the protocol has a `screen` block, the screening cascade runs first
(Part D, our funnel; `Execution.screen`). Then, per evidence type (the protocol's dependency order): locate
the scope, give each extractor of the type's cascade one task (the document, the scope, the merged items of
the context types), check every result centrally (evidence/checks.py), merge the cascade (evidence/merge.py),
and pass the merged items on as context. Then synthesis (answer.json) and the evidence graph. Every locate,
screen decision, extractor call, merge, completeness decision and the synthesis is one record of the
hash-chained events.jsonl; every call's checked result is calls/<call_id>.json, where the call id is the
task id of its record.

Strategies (`Settings.strategy`, docs/evidence-system.md Part D; the funnel is our design, not the
supervisor's):

- `all` (the default): every extractor of every cascade on every document, as the engine of Part A did; the
  screen decision is recorded and extraction runs anyway, so screening precision and recall can be scored on
  the same run. This is the benchmarking mode.
- `gaps`: the funnel. A document screened out (`on_fail: skip`) gets no extraction and its study is
  `undetermined` with reason `screened_out`. Otherwise position 0 of every type's cascade runs; then, while
  `synthesis.study()` on the document's merged items gives no direction, the gap's reason code names the
  evidence types to escalate (`synthesis.GAP_TYPES`), and each of those runs the NEXT position of its own
  cascade with a targeted task (`contract.Focus`, `focus_for`), the merged items of its context types as
  context, re-merged with its earlier results; the funnel stops when the study is complete or when no gap
  type has a position left (the gap is recorded). `cascade: until_found` is an `all`-mode rule; the funnel's
  own decisions take its place. As built, a type escalates through its own cascade position by position
  rather than every gap type jumping to one global position per round: the contract's picture (position 1
  for the gap types, then position 2) would never run the LLM measurement extractor for a paper whose
  baseline condition the regex missed (condition is the gap at round 1, measurement only at round 2, where a
  two-step cascade has nothing); see Part D's as-built note.

`replay` rebuilds a run from the record cache only and checks every output hash against the recorded
run.json; `reexec` runs extractors again, bypassing the cache, and reports the differences (reexec.json).
Both repeat the strategy from run.json; every funnel decision depends only on checked results, so a `gaps`
run replays from its own cache and reproduces every hash.
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
from .contract import DocumentRef, ExtractionResult, ExtractionTask, Extractor, ExtractorSpec, Focus, Item, ProtocolRef, Scope
from .locate import Located, Locator, locate
from .protocol import SCREEN_TYPE, EvidenceTypeSpec, ExtractorRef, Protocol, Synthesis, parse
from .recording import Provider, usage
from .rundir import (ANSWER_FILE, CACHE_FILE, CALLS_DIR, EVENTS_FILE, EVIDENCE_FILE, FUNNEL_FILE, GRAPH_FILE,
                     LOCATE_FILE, PROTOCOL_FILE, RUN_FILE, Corpus, Events, new_run_id, write_canonical, write_lines)

Selection = Literal["cascade", "regex-only", "llm-only"]
Strategy = Literal["all", "gaps"]
KINDS: dict[str, tuple[str, ...]] = {"cascade": ("regex", "model", "llm", "agent"), "regex-only": ("regex",),
                                     "llm-only": ("llm",)}
ENGINE = "evidence-engine"
__all__ = ["NotRecorded", "Settings", "build_extractors", "execute_run", "focus_for", "run"]


@dataclass
class Settings:
    """What a run needs besides the protocol; recorded in run.json so replay and reexec repeat it."""
    corpus: str
    cache: str
    selection: Selection = "cascade"
    model: str | None = None                       # model alias for llm/agent extractors (overrides the protocol)
    imports: list[str] = field(default_factory=list)   # modules that register more extractors
    strategy: Strategy = "all"                     # all: every extractor on everything; gaps: the funnel (Part D)

    def json(self) -> dict[str, Any]:
        return {"corpus": self.corpus, "cache": self.cache, "selection": self.selection, "model": self.model,
                "imports": list(self.imports), "strategy": self.strategy}


def default_provider(alias: str) -> Any:
    from gold.llm import openai_model  # the key comes from $LITELLM_MASTER_KEY only
    return openai_model(alias)


def build_extractors(protocol: Protocol, selection: Selection = "cascade",
                     model: str | None = None) -> dict[str, list[tuple[ExtractorRef, Extractor]]]:
    """The cascade per evidence type, built from the registry with the type's schema added to each config;
    under the key `screen` the screening cascade of the protocol's `screen` block (Part D), whose extractors
    get the same injected configuration plus the block's `terms` and `question`."""
    out: dict[str, list[tuple[ExtractorRef, Extractor]]] = {}
    specs: dict[str, tuple[EvidenceTypeSpec, dict[str, Any]]] = {etype: (spec, {}) for etype, spec in protocol.evidence_types.items()}
    if protocol.screen is not None:
        specs[SCREEN_TYPE] = (protocol.screen.spec, {"terms": list(protocol.screen.terms), "question": protocol.screen.question})
    for etype, (spec, extra) in specs.items():
        chosen = []
        for ref in spec.extractors:
            config = {**ref.config, "evidence_type": etype, "field_schema": spec.fields, "links": dict(spec.links),
                      "roles": list(spec.roles), "description": spec.description,
                      "question_metrics": list(protocol.synthesis.metric_names),
                      "compare": protocol.synthesis.compare.model_dump(), **extra}
            extractor = extractors.get(ref.name, config)
            if model and extractor.spec.kind in ("llm", "agent"):
                extractor = extractors.get(ref.name, {**config, "model": model})
            if extractor.spec.kind in KINDS[selection]:
                chosen.append((ref, extractor))
        out[etype] = chosen
    return out


def focus_for(gap: str, spec: Synthesis, merged: dict[str, list[Item]]) -> Focus:
    """The targeted task of an escalation (Part D): the gap code, what was found (condition roles, canonical
    metrics) and the request in words, from the gap code and the protocol's roles."""
    t, c = spec.compare.treatment, spec.compare.control
    roles = sorted({str(i.fields.get("role")) for i in merged.get("condition", []) if i.fields.get("role") is not None})
    metrics = sorted({str(i.fields.get("canonical")) for i in merged.get("metric", []) if i.fields.get("canonical") is not None})
    question = ", ".join(spec.metric_names)
    found = ", ".join(roles) or "none"
    want = {
        "no_treatment_condition": f"the {t} condition is missing (condition roles found: {found}); find the condition the "
                                  f"paper reports as its {t} system, with the label the paper gives it",
        "no_control_condition": f"only the {c} condition and its measurement on a question metric are missing (condition "
                                f"roles found: {found}); find the condition the paper compares the {t} system against",
        "no_question_metric": f"no metric of the question ({question}) was found (metrics found: "
                              f"{', '.join(metrics) or 'none'}); find the metric the paper reports the {t} and {c} "
                              f"results on",
        "no_pair": f"the {t} and {c} conditions and a question metric are known, but no {t} and {c} measurement on "
                   f"one dataset was found; find the values of both conditions on the same dataset and metric "
                   f"({', '.join(m for m in metrics if m in spec.metric_names) or question}), tables first",
    }.get(gap, f"the study is incomplete ({gap}); find what is missing")
    return Focus(gap=gap, have={"roles": roles, "metrics": metrics}, want=want)


@dataclass
class DocState:
    """Everything the funnel knows about one document while it runs."""
    doc: DocumentRef
    text: str
    index: Index
    scopes: dict[str, Located] = field(default_factory=dict)       # per type, located once
    results: dict[str, list[tuple[str, ExtractionResult]]] = field(default_factory=dict)   # per type, cascade order
    merged: dict[str, list[Item]] = field(default_factory=dict)
    next_position: dict[str, int] = field(default_factory=dict)    # per type, the next cascade position to run
    focus: dict[str, Focus] = field(default_factory=dict)          # per type, the targeted task of its next position
    steps: list[dict[str, Any]] = field(default_factory=list)      # funnel.json: [{round, position, types, calls}]
    decisions: list[dict[str, Any]] = field(default_factory=list)  # funnel.json: the completeness decisions
    screen: dict[str, Any] | None = None                           # the screen decision, or None without a screen block
    skipped: bool = False
    stopped_after: int | None = None

    @property
    def relevant(self) -> bool | None:
        return None if self.screen is None else bool(self.screen["relevant"])

    def items(self) -> list[Item]:
        return sorted((i for t in self.merged.values() for i in t), key=lambda i: (i.first_start(), i.evidence_type, i.item_id))


class Execution:
    """One pass over the corpus; collects everything the run directory holds."""

    def __init__(self, protocol: Protocol, corpus: Corpus, root: Path, run_id: str, calls: CallCache,
                 cascades: dict[str, list[tuple[ExtractorRef, Extractor]]], provider: Provider | None,
                 locator: Locator | None, strategy: Strategy = "all") -> None:
        self.protocol, self.corpus, self.root, self.calls = protocol, corpus, root, calls
        self.cascades, self.provider, self.locator, self.strategy = cascades, provider, locator, strategy
        self.events = Events(root / EVENTS_FILE, run_id)
        self.ref = ProtocolRef(id=protocol.id, sha256=protocol.sha256)
        self.outputs: dict[str, str] = {}
        self.located: list[dict[str, Any]] = []
        self.items: dict[str, list[Item]] = {}
        self.reasons: dict[str, dict[str, str]] = {}      # document -> pre-set synthesis reason (screened out)
        self.funnel: dict[str, dict[str, Any]] = {}       # document -> funnel.json entry
        self.cost = {"calls": 0, "cached_calls": 0, "model_calls": 0, "made_model_calls": 0, "input_tokens": 0,
                     "output_tokens": 0}

    # --- per document ---------------------------------------------------------------------------------

    def document(self, paper: Any) -> None:
        text = self.corpus.text(paper)
        state = DocState(paper.ref, text, Index(text))
        self.screen(state)
        screen = self.protocol.screen
        if self.strategy == "gaps" and state.relevant is False and screen is not None and screen.on_fail == "skip":
            state.skipped = True
            reason = synthesis.reason("screened_out", self.protocol.synthesis)
            self.reasons[paper.id] = {**reason, "text": f"{reason['text']}: {state.screen['reason']}"}   # type: ignore[index]
        elif self.strategy == "gaps":
            self.funnel_loop(state)
        else:
            self.run_position(state, self.protocol.phases(), None, round_no=0)
        self.items[paper.id] = state.items()
        self.funnel[paper.id] = {"screen": state.screen, "skipped": state.skipped, "steps": state.steps,
                                 "decisions": state.decisions, "stopped_after": state.stopped_after}

    def screen(self, state: DocState) -> None:
        """The screening cascade (Part D): an extractor saying "not relevant" stops it; "relevant" passes the
        decision to the next one; a call without an item leaves the earlier decision standing; no decision at
        all counts as relevant. Recorded as a `screen` event and in funnel.json."""
        if self.protocol.screen is None:
            return
        spec = self.protocol.screen.spec
        doc = state.doc
        decision: dict[str, Any] = {"relevant": True, "reason": "no decision: no screening extractor returned an item",
                                    "extractor": None, "status": None}
        context: list[Item] = []
        call_ids: list[str] = []
        statuses: list[str] = []      # one per call, so a failed call after the decision is on record too
        for position, (ref, extractor) in enumerate(self.cascades.get(SCREEN_TYPE, [])):
            task = ExtractionTask(protocol=self.ref, evidence_type=SCREEN_TYPE, field_schema_sha256=spec.schema_sha256,
                                  document=doc, scope=Scope(), context=tuple(i.item_id for i in context))
            call_id, result = self._call(extractor, task, state.text, state.index, spec, context, position)
            call_ids.append(call_id)
            statuses.append(result.status)
            if not result.items:
                continue   # no item (an error, an empty document): the earlier decision stands
            item = result.items[0]
            decision = {"relevant": bool(item.fields["relevant"]), "reason": str(item.fields["reason"]),
                        "extractor": extractor.spec.extractor_id, "status": result.status}
            context = [item]
            if not decision["relevant"]:
                break
        state.screen = {**decision, "calls": call_ids, "statuses": statuses}
        self.events.add("screen", used=[doc.sha256], generated=[], agent_id=decision["extractor"] or ENGINE,
                        group_id=doc.id, custom={"document": doc.id, **decision, "calls": call_ids, "statuses": statuses})

    def funnel_loop(self, state: DocState) -> None:
        """`gaps`: position 0 of every type, then the next position of each gap type until complete or exhausted."""
        phases = self.protocol.phases()
        self.run_position(state, phases, 0, round_no=0)
        round_no = 0
        while True:
            complete, gap, gap_types = self.complete(state, round_no)
            if complete:
                state.stopped_after = max((s["position"] for s in state.steps), default=None)
                return
            pending = [t for t in phases if t in gap_types
                       and state.next_position.get(t, 0) < len(self.cascades.get(t, []))]
            if not pending:
                return   # exhausted: the gap stays recorded in the last decision
            round_no += 1
            focus = focus_for(gap or "", self.protocol.synthesis, state.merged)
            for etype in pending:
                state.focus[etype] = focus
                self.run_position(state, [etype], state.next_position[etype], round_no=round_no)

    def run_position(self, state: DocState, types: list[str], position: int | None, *, round_no: int) -> None:
        """Run `position` of the cascade of each type in `types` (phase order; a cascade without that position
        is skipped), or every position (`None`, the `all` strategy, honouring `cascade: until_found`); then
        merge the type's results so far and pass the merged items on. One funnel step per position run."""
        ran: dict[int, dict[str, Any]] = {}
        for etype in self.protocol.phases():
            if etype not in types:
                continue
            spec = self.protocol.evidence_types[etype]
            cascade = self.cascades.get(etype, [])
            positions = list(range(len(cascade))) if position is None else [position] if position < len(cascade) else []
            if position is not None and not positions:
                continue
            if etype not in state.scopes:
                state.scopes[etype] = self._locate(state, etype, spec)
            found = state.scopes[etype]
            context = [i for t in spec.context for i in state.merged.get(t, [])]
            results = state.results.setdefault(etype, [])
            for p in positions:
                ref, extractor = cascade[p]
                if position is None and spec.cascade == "until_found" and any(r.items for _, r in results):
                    break
                focus = state.focus.get(etype) if position is not None and p > 0 else None
                task = ExtractionTask(protocol=self.ref, evidence_type=etype,  # type: ignore[arg-type]
                                      field_schema_sha256=spec.schema_sha256, document=state.doc, scope=found.scope,
                                      context=tuple(i.item_id for i in context),
                                      budget=ref.budget if extractor.spec.kind == "agent" else None, focus=focus)
                call_id, result = self._call(extractor, task, state.text, state.index, spec, context, p)
                results.append((call_id, result))
                step = ran.setdefault(p, {"round": round_no, "position": p, "types": [], "calls": []})
                step["types"].append(etype)
                step["calls"].append(call_id)
                state.next_position[etype] = p + 1
            items, sources, collisions = merge.merge(results, spec)
            state.merged[etype] = items
            self.events.add("merge", used=sorted({i.item_id for _, r in results for i in r.items}),
                            generated=[i.item_id for i in items], agent_id=ENGINE, group_id=state.doc.id,
                            custom={"document": state.doc.id, "evidence_type": etype, "sources": sources,
                                    "collisions": collisions})
        state.steps += [ran[p] for p in sorted(ran)]

    def complete(self, state: DocState, round_no: int) -> tuple[bool, str | None, tuple[str, ...]]:
        """The completeness decision after a round: `synthesis.study()` on the merged items gives a direction, or
        the gap's reason code and the evidence types to escalate. A `completeness` event and a funnel.json entry."""
        entry, _ = synthesis.study(self.protocol, state.doc.id, state.items())
        complete = entry["direction"] != "undetermined"
        gap = None if complete else entry["reason"]["code"]
        gap_types = synthesis.GAP_TYPES.get(gap, ()) if gap else ()
        decision = {"after_round": round_no, "after_position": max((s["position"] for s in state.steps), default=None),
                    "complete": complete, "gap": gap, "gap_types": list(gap_types)}
        state.decisions.append(decision)
        self.events.add("completeness", used=[], generated=[], agent_id=ENGINE, group_id=state.doc.id,
                        custom={"document": state.doc.id, **decision})
        return complete, gap, gap_types

    def _locate(self, state: DocState, etype: str, spec: EvidenceTypeSpec) -> Located:
        found = locate(self.protocol.locate, state.doc, state.text, etype, spec, self.locator)
        self.located.append({"document": state.doc.id, "evidence_type": etype, "strategy": self.protocol.locate.strategy,
                             **found.json()})
        self.events.add("locate", used=[state.doc.sha256], generated=[], agent_id=f"locate:{self.protocol.locate.strategy}",
                        group_id=state.doc.id, custom={"document": state.doc.id, "evidence_type": etype,
                                                       "scope": found.scope.model_dump(mode="json")})
        return found

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
                                "rejected": len(result.rejected), "focus": task.focus.gap if task.focus else None})
        return call_id, result

    # --- the run --------------------------------------------------------------------------------------

    def finish(self) -> dict[str, Any]:
        papers = self.corpus.papers
        funnel = {p.id: {"screened": self.funnel[p.id]["screen"]["relevant"] is False if self.funnel[p.id]["screen"] else False,
                         "stopped_after": self.funnel[p.id]["stopped_after"]} for p in papers if p.id in self.funnel}
        answer, used = synthesis.answer(self.protocol, [p.id for p in papers], self.items, self.reasons, funnel)
        evidence = [i.model_dump(mode="json") for p in papers for i in self.items.get(p.id, [])]
        self.outputs[LOCATE_FILE] = write_canonical(self.root / LOCATE_FILE, self.located)
        self.outputs[EVIDENCE_FILE] = write_lines(self.root / EVIDENCE_FILE, evidence)
        self.outputs[FUNNEL_FILE] = write_canonical(self.root / FUNNEL_FILE, {"strategy": self.strategy,
                                                                               "documents": self.funnel})
        self.outputs[ANSWER_FILE] = write_canonical(self.root / ANSWER_FILE, answer)
        self.outputs[GRAPH_FILE] = write_canonical(self.root / GRAPH_FILE, graph.build(papers, self.items, answer))
        self.events.add("synthesis", used=sorted(set(used)), generated=["answer"], agent_id=ENGINE,
                        custom={"label": answer["label"], "counts": answer["counts"],
                                "flags": {name: len(docs) for name, docs in answer["flags"].items()},   # Part F1
                                "answer_sha256": self.outputs[ANSWER_FILE], "rule": "label_table"})
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
    ex = Execution(protocol, corpus, root, run_id, cache, cascades, provider, locator, settings.strategy)
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
        retry_errors: bool = False, strategy: Strategy = "all") -> Path:
    """A normal run: cached calls are reused, new ones are made and stored."""
    settings = Settings(corpus=str(Path(corpus).resolve()),
                        cache=str((Path(cache) if cache else Path(out_dir) / "cache").resolve()),
                        selection=selection, model=model, imports=list(imports or []), strategy=strategy)
    return execute_run(Path(protocol_path).read_bytes(), settings, out_dir, run_id=run_id,
                       provider=provider if provider is not None else default_provider, locator=locator,
                       retry_errors=retry_errors)
