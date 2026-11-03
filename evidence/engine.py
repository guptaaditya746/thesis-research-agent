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

- `all` (the benchmarking mode, ask for it): every extractor of every cascade on every document, as the engine of Part A did; the
  screen decision is recorded and extraction runs anyway, so screening precision and recall can be scored on
  the same run.
- `gaps` (the default): the funnel. A document screened out (`on_fail: skip`) gets no extraction and its study is
  `undetermined` with reason `screened_out`. Otherwise position 0 of every type's cascade runs; then, while
  the kind's `study()` (evidence/kinds/; for effect `synthesis.study()`) on the document's merged items gives
  a reason, the gap's reason code names the evidence types to escalate (the kind's `gap_types`; for effect
  `synthesis.GAP_ROLES`, the pack roles whose protocol types escalate), and each of those runs the NEXT position of its own
  cascade with a targeted task (`contract.Focus`, `focus_for`), the merged items of its context types as
  context, re-merged with its earlier results; the funnel stops when the study is complete or when no gap
  type has a position left (the gap is recorded). `cascade: until_found` is an `all`-mode rule; the funnel's
  own decisions take its place. As built, a type escalates through its own cascade position by position
  rather than every gap type jumping to one global position per round: the contract's picture (position 1
  for the gap types, then position 2) would never run the LLM measurement extractor for a paper whose
  baseline condition the regex missed (condition is the gap at round 1, measurement only at round 2, where a
  two-step cascade has nothing); see Part D's as-built note.

Confirmation (`Settings.confirm`, Part D's as-built note of 29 Oct): with `llm` (the default), an item that only
GLiNER extractors found (every id in its `found_by` of kind `model`) is *unconfirmed* when the type's cascade has an
LLM extractor; once that extractor's position has run, unconfirmed items are dropped from the merge and listed in
its event (`unconfirmed`). In `all` every position runs, so only the drop applies. In `gaps` the confirmation is
eager: when a type's position leaves unconfirmed items and its LLM position has not run, that position runs at once
(a step of the same round, focus unchanged), before the merge and before a later type links to the items, so no
link ever points at an id a later merge replaced. With `none` (runs before 29 Oct) every item counts.

Relinking (`Settings.relink`, Part D's as-built note of 1 Nov): in `gaps` a type escalated in a later round is merged
again, and an earlier item that a later extractor found with another span gets a new id. With `on` (the default)
`merge.merge_from` maps each earlier id to the new one, the links of the other types' items follow (checked
results and merged items), and the merge event lists the pairs (`relinked`). After each document the links that
point to no item are listed in funnel.json (`dangling_links`, per document and as a run total, also in run.json),
so a dangling link is never silent. With `off` (runs before 1 Nov) neither happens: those links dangled.

Names (`Settings.names`, D38; off by default, as runs before it): after every document, the names of the items whose
pack type has a name field are grouped corpus-wide (evidence/names.py `group_names`, with the pack's `names_seed`),
and unless the selection is `regex-only` each name no step matched is put to a model check
(`names.confirm_leftovers`, prompts/names-confirm-v1.md) whose calls go through the record cache like an extractor's
(`CallCache.recorded`, owner id `names_confirm@<version>#<digest>`), so a replay never asks a model. It asks the model
of the protocol's LLM extractors (`names_alias`). Each check is a `names_check` event and a calls/<call_id>.json result
(error reason `model_call` when the gateway failed it), so a failed check is a failed call: the CLI exits 2, the web
app counts it, `--retry-errors` asks it again. The groups are
names.json; the names left unresolved are counted in funnel.json and run.json (`unresolved_names`), as dangling links
are; the kind's answer gets the groups (`groups`). With `off` none of it happens and no file changes.

Reasoner (`Settings.reason`, spec 6.3, D25, D30; on by default, off for a run made before it): after the names step and
before the answer, `reasoner.reason` reads the pack's ontology and gives the run's inferences: which names have a
broader class (so a narrower metric answers a broader question metric) and which links point at an item of the wrong
kind (`link_flags`). They are reason.json, an output, and the kind's answer gets them (`reason`). A replay reads the
recorded reason.json and never reasons again (`execute_run(source_dir=...)`); a reexec reasons again, since its items
may differ. With `off` none of it happens and no file changes.

Comparisons (plan 2 Task 8, spec section 6.2): after the reasoner, for every kind, the comparisons built from
pairs in each study (evidence/comparisons.py, with the names step's groups or none) are comparisons.json, and the
kind's answer gets them (`comparisons`). The order is names, reason, comparisons, answer (D25). Runs made before it
have no comparisons.json; their replay reports the file as added (replay.ADDED_OUTPUTS), not as a mismatch.

`replay` rebuilds a run from the record cache only and checks every output hash against the recorded
run.json; `reexec` runs extractors again, bypassing the cache, and reports the differences (reexec.json).
Both repeat the strategy from run.json; every funnel decision depends only on checked results, so a `gaps`
run replays from its own cache and reproduces every hash.

Workers (`execute_run(workers=N)`, `evidence run --workers N`): a run makes its model calls one after the
other, which leaves most of a pool of model replicas idle. With N > 1 a warm pass first runs the papers, N at
once, in throw-away run directories, only to fill the record cache; then the normal sequential loop runs and
finds every call in the cache. Two passes, not one, so that call ids, the event order and every output hash are
those of paper order whatever N is (the same code checks and merges the calls, in the same order). A cache hit
on a call this process made counts as fresh (`CallCache.made`), so the cost totals agree too. `workers` is not
a setting: it never changes a result, so replay does not need it. The warm pass is skipped when no model call is
possible (`regex-only`, no provider). Locator calls are not cached, so an `agent` locator runs again in the second
pass.

A `run` (not replay or reexec) also keeps its own calls.jsonl (rundir.RunCalls): one row per model-backed extractor
or screen call with its full model-call records, written as each call completes, by the warm pass (phase `warm`)
or, for calls it did not write, by the sequential loop (phase `run`). It is not an output and not in the hash
chain, so it changes no hash; its row order may vary with workers.
"""
from __future__ import annotations

import dataclasses
import importlib
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from agent.anchor import Index
from jsonio import sha256_hex, write_json
from agent.rundir import utc_now
import modelcall
from modelcall import JsonlCache

from . import checks, comparisons, extractors, graph, lockfile, kinds, merge, names, reasoner, stages
from . import records as _records  # noqa: F401  registers the evidence types x, cl, ln: items of a general run always load
from .plan import Plan, load_plan
from . import seal as sealing
from .extractors import base as extractor_base
from .extractors import gliner
from .extractors import llm as llm_extractor
from .calls import CallCache, EngineContext, Mode, NotRecorded, cache_key
from .contract import DocumentRef, ExtractionError, ExtractionResult, ExtractionTask, Extractor, ExtractorSpec, Focus, Item, ProtocolRef, Scope
from .locate import Located, Locator, locate
from .pack import DOMAINS, Role, RoleMap, load_pack
from .protocol import DEFAULT_PACK, SCREEN_TYPE, EvidenceTypeSpec, ExtractorRef, Protocol, Synthesis, parse
from .contract import digest
from .recording import ModelCallError, Provider, Recorder, usage
from .rundir import (ANSWER_FILE, CACHE_FILE, CALLS_DIR, COMPARISONS_FILE, EVENTS_FILE, EVIDENCE_FILE, FUNNEL_FILE,
                     GRAPH_FILE, LOCATE_FILE, LOCK_FILE, NAMES_FILE, PLAN_FILE, PROTOCOL_FILE, REASON_FILE, RUN_CALLS_FILE,
                     RUN_FILE, Corpus, Events, RunCalls, RunDir, RunDirExists, new_run_id, read_json, write_lines)

Selection = Literal["cascade", "regex-only", "llm-only"]
Strategy = Literal["all", "gaps"]
Confirm = Literal["none", "llm"]
Relink = Literal["off", "on"]
Names = Literal["off", "on"]
Reason = Literal["off", "on"]
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
    strategy: Strategy = "gaps"                    # gaps: the funnel (Part D); all: every extractor on everything
    # the GLiNER service of the gliner_* extractors ($GLINER_URL; None disables them); not part of any id
    gliner_url: str | None = field(default_factory=lambda: os.environ.get("GLINER_URL") or None)
    # the model that service served when the run was made (GET /info; execute_run fills it): every gliner_* step
    # that pins no `model` gets it, so a replay without the service builds the ids of the recorded run
    gliner_model: str | None = None
    confirm: Confirm = "llm"                       # llm: GLiNER-only items need the LLM extractor too; none: keep all
    relink: Relink = "on"                          # on: links follow an item a later merge gave a new id; off: as before 1 Nov
    domains: str | None = None                     # the folder of the protocol's pack (None: domains/; a test pack)
    names: Names = "off"                           # on: corpus-wide name groups, names.json (D38); off: as before
    reason: Reason = "on"                          # on: the reasoner's inferences, reason.json (spec 6.3); off: as before
    plan: Path | None = None                       # the confirmed plan file; None: a run without a plan, as before

    def json(self) -> dict[str, Any]:
        # `confirm` only when it is llm, `relink`, `names` and `reason` only when on: the settings of a run made before
        # them are unchanged
        return {"corpus": self.corpus, "cache": self.cache, "selection": self.selection, "model": self.model,
                "imports": list(self.imports), "strategy": self.strategy, "gliner_url": self.gliner_url,
                "gliner_model": self.gliner_model, **({"confirm": self.confirm} if self.confirm == "llm" else {}),
                **({"relink": self.relink} if self.relink == "on" else {}),
                **({"domains": self.domains} if self.domains is not None else {}),
                **({"names": self.names} if self.names == "on" else {}),
                **({"reason": self.reason} if self.reason == "on" else {}),
                **({"plan": str(self.plan)} if self.plan is not None else {})}


# --- the names check (D38): one recorded model call per question of names.confirm_leftovers ----------------------

NAMES_VERSION = 1
NAMES_PROMPT = Path(__file__).resolve().parent / "prompts" / "names-confirm-v1.md"
NAMES_SETTINGS: dict[str, Any] = {"temperature": 0.0, "seed": 0, "max_tokens": 512}


class NamesVerdict(BaseModel):
    same: bool
    quote: str


def names_alias(cascades: dict[str, list[tuple[ExtractorRef, Extractor]]], model: str | None) -> str:
    """The model the names check asks ("same model for all systems"): the model the protocol's LLM extractors were
    built with (their `model` config: the protocol's pin, replaced by the run's `--model` when given, see
    build_extractors), the first LLM extractor in the protocol's type order, the screen last; with none, the run's
    model, else the LLM extractors' default."""
    for cascade in cascades.values():
        for _, extractor in cascade:
            if extractor.spec.kind == "llm" and extractor.spec.config.get("model"):
                return str(extractor.spec.config["model"])
    return model or str(llm_extractor.DEFAULTS["model"])


def names_check(alias: str) -> tuple[str, str, str]:
    """(owner id, model alias, instructions) of the names check: the id covers the code, the prompt with its output
    schema, the model alias and the call settings, so a change to any of them is a new cache key."""
    instructions = modelcall.load_prompt(NAMES_PROMPT).text
    config = {"model": alias, "prompt_sha256": modelcall.prompt_sha256(instructions, NamesVerdict), **NAMES_SETTINGS}
    here = Path(__file__).resolve().parent
    code = extractor_base.source_sha256(here / "names.py", NAMES_PROMPT, here / "recording.py")
    return f"names_confirm@{NAMES_VERSION}#{digest([code, config])[:12]}", alias, instructions


def default_provider(alias: str) -> Any:
    from modelcall import openai_model  # the key comes from $LITELLM_MASTER_KEY only
    return openai_model(alias)


def build_extractors(protocol: Protocol, selection: Selection = "cascade", model: str | None = None,
                     gliner_url: str | None = None,
                     gliner_model: str | None = None) -> dict[str, list[tuple[ExtractorRef, Extractor]]]:
    """The cascade per evidence type, built from the registry with the type's schema added to each config;
    under the key `screen` the screening cascade of the protocol's `screen` block (Part D), whose extractors
    get the same injected configuration plus the block's `terms` and `question`. The gliner_* extractors also
    get `gliner_url` (None: unavailable) and, unless their config pins one, `model` = `gliner_model`; only
    they, so no other extractor's config (and id) changes. Each config starts from the topic words of the
    protocol's domain pack (`Pack.extractor_config`); the protocol's own config is put over them (it wins)."""
    pack = protocol.pack()
    out: dict[str, list[tuple[ExtractorRef, Extractor]]] = {}
    specs: dict[str, tuple[EvidenceTypeSpec, dict[str, Any]]] = {etype: (spec, {}) for etype, spec in protocol.evidence_types.items()}
    question = kinds.of(protocol).extractor_config(protocol)   # the kind's part (effect: question_metrics, compare)
    if protocol.screen is not None:
        specs[SCREEN_TYPE] = (protocol.screen.spec, {"terms": list(protocol.screen.terms), "question": protocol.screen.question})
    for etype, (spec, extra) in specs.items():
        chosen = []
        for ref in spec.extractors:
            config = {**pack.extractor_config(etype, ref.name), **ref.config, "evidence_type": etype,
                      "field_schema": spec.fields, "links": dict(spec.links), "roles": list(spec.roles), "description": spec.description, **question, **extra}
            if spec.optional_links:   # given only when there are any, so no other extractor's config (and id) changes
                config["optional_links"] = list(spec.optional_links)
            if ref.name in gliner.FACTORIES:
                config[gliner.URL_KEY] = gliner_url
                if gliner_model and "model" not in ref.config:
                    config["model"] = gliner_model
            extractor = extractors.get(ref.name, config)
            if model and extractor.spec.kind in ("llm", "agent"):
                extractor = extractors.get(ref.name, {**config, "model": model})
            if extractor.spec.kind in KINDS[selection]:
                chosen.append((ref, extractor))
        out[etype] = chosen
    return out


def focus_for(gap: str, protocol: Protocol | Synthesis, merged: dict[str, list[Item]],
              roles: RoleMap | None = None) -> Focus:
    """The targeted task of an escalation (Part D): the gap code, what was found (the sides of the compared things,
    the canonical metrics; types and fields by pack role) and the request in words, from the gap code and the
    protocol's compared sides. For effect and consistency protocols (or a `synthesis` block given directly, read
    with `roles`, else the default pack); for the other kinds the task names the gap only (nothing in `have`) with
    the generic request."""
    if isinstance(protocol, Synthesis):
        spec = protocol
        roles = roles if roles is not None else RoleMap(load_pack(DEFAULT_PACK))
        thing, metric = roles.type_of(Role.COMPARED_THING), roles.type_of(Role.METRIC)
    elif protocol.kind in ("effect", "consistency") and protocol.synthesis is not None:
        spec = protocol.synthesis
        roles = roles if roles is not None else protocol.roles()
        thing = roles.type_in(Role.COMPARED_THING, protocol.evidence_types)
        metric = roles.type_in(Role.METRIC, protocol.evidence_types)
    else:
        return Focus(gap=gap, have={}, want=f"the study is incomplete ({gap}); find what is missing")
    t, c = spec.compare.treatment, spec.compare.control
    side = roles.field_or_none(thing, "side") if thing is not None else None
    canonical = roles.field_or_none(metric, "canonical") if metric is not None else None

    def values(etype: str | None, field: str | None) -> list[str]:
        if etype is None or field is None:
            return []
        return sorted({str(i.fields.get(field)) for i in merged.get(etype, []) if i.fields.get(field) is not None})

    roles_found, metrics = values(thing, side), values(metric, canonical)
    found = ", ".join(roles_found) or "none"
    question = ", ".join(spec.metric_names)
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
    return Focus(gap=gap, have={"roles": roles_found, "metrics": metrics}, want=want)


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
                 locator: Locator | None, strategy: Strategy = "all", run_calls: RunCalls | None = None,
                 phase: Literal["warm", "run"] = "run", confirm: Confirm = "none", relink: Relink = "off",
                 names: Names = "off", names_model: str | None = None, names_ask: bool = True,
                 reason: Reason = "off", domains: Path | None = None, recorded_reason: Path | None = None,
                 plan: Plan | None = None, mode: Mode = "run") -> None:
        self.plan = plan                                 # the confirmed plan, handed to the stage seams
        self.protocol, self.corpus, self.root, self.calls = protocol, corpus, root, calls
        # the reasoner: `domains` the folder of the protocol's pack; `recorded_reason` the reason.json a replay reads
        self.reason, self.domains, self.recorded_reason = reason, domains or DOMAINS, recorded_reason
        self.confirm, self.relink = confirm, relink
        self.names, self.names_model, self.names_ask = names, names_model, names_ask   # `names_ask`: the model check
        self.texts: dict[str, str] = {}                  # document -> text (`names: on` only)
        self.unresolved_names = 0
        self.roles = protocol.roles()                    # the pack's types by role, for the kind's rules
        self.dangling = 0                                 # links to no item, over the run (`relink: on` only)
        self.run_calls, self.phase = run_calls, phase    # the run's calls.jsonl (mode `run` only), this pass
        self.cascades, self.provider, self.locator, self.strategy = cascades, provider, locator, strategy
        self.events = Events(root / EVENTS_FILE, run_id)
        self.ref = ProtocolRef(id=protocol.id, sha256=protocol.sha256)
        self.ctx = stages.StageContext(plan, calls, mode, provider, root, self.stage_ask,   # what the stage seams get
                                       names_model or names_alias(cascades, None))
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
        if self.names == "on":
            self.texts[paper.id] = text
        state = DocState(paper.ref, text, Index(text))
        stages.before_extract(state, self.ctx)
        self.screen(state)
        screen = self.protocol.screen
        if self.strategy == "gaps" and state.relevant is False and screen is not None and screen.on_fail == "skip":
            state.skipped = True
            reason = kinds.screened_out(self.protocol)
            self.reasons[paper.id] = {**reason, "text": f"{reason['text']}: {state.screen['reason']}"}   # type: ignore[index]
        elif self.strategy == "gaps":
            self.funnel_loop(state)
        else:
            self.run_position(state, self.protocol.phases(), None, round_no=0)
        self.items[paper.id] = state.items() + stages.after_document(state, self.ctx)
        self.funnel[paper.id] = {"screen": state.screen, "skipped": state.skipped, "steps": state.steps,
                                 "decisions": state.decisions, "stopped_after": state.stopped_after}
        if self.relink == "on":   # the final check: a link to no item is listed, never silent (off: runs before it)
            ids = {i.item_id for i in self.items[paper.id]}
            dangling = [[i.item_id, name, target] for i in self.items[paper.id] for name, target in sorted(i.links.items())
                        if target not in ids]
            self.funnel[paper.id]["dangling_links"] = dangling
            self.dangling += len(dangling)

    def screen(self, state: DocState) -> None:
        """The screening cascade (Part D): an extractor saying "not relevant" stops it; "relevant" passes the
        decision to the next one; a call without an item leaves the earlier decision standing; no decision at
        all counts as relevant. With `lexical_miss: escalate` a regex "not relevant" before the last position
        passes the document on instead (`escalated` in the record; the regex decision stands unless the next
        extractor returns an item). Recorded as a `screen` event and in funnel.json."""
        if self.protocol.screen is None:
            return
        spec = self.protocol.screen.spec
        cascade = self.cascades.get(SCREEN_TYPE, [])
        escalate = self.protocol.screen.lexical_miss == "escalate"
        escalated: dict[str, Any] = {}    # only an escalated record carries the key: the default record is unchanged
        doc = state.doc
        decision: dict[str, Any] = {"relevant": True, "reason": "no decision: no screening extractor returned an item",
                                    "extractor": None, "status": None}
        context: list[Item] = []
        call_ids: list[str] = []
        statuses: list[str] = []      # one per call, so a failed call after the decision is on record too
        for position, (ref, extractor) in enumerate(cascade):
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
                if escalate and extractor.spec.kind == "regex" and position < len(cascade) - 1:
                    escalated = {"escalated": True}   # a keyword miss: the next extractor decides
                    continue
                break
        state.screen = {**decision, "calls": call_ids, "statuses": statuses, **escalated}
        self.events.add("screen", used=[doc.sha256], generated=[], agent_id=decision["extractor"] or ENGINE,
                        group_id=doc.id, custom={"document": doc.id, **decision, "calls": call_ids, "statuses": statuses,
                                                 **escalated})

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
            focus = focus_for(gap or "", self.protocol, state.merged, self.roles)
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
            # one position of a funnel round: the first available one from `position` on (a skipped one falls through)
            positions = list(range(len(cascade))) if position is None else list(range(position, len(cascade)))
            if position is not None and not positions:
                continue
            if etype not in state.scopes:
                state.scopes[etype] = self._locate(state, etype, spec)
            found = state.scopes[etype]
            context = [i for t in spec.context for i in state.merged.get(t, [])]
            results = state.results.setdefault(etype, [])
            before = len(results)    # the results the type's last merge covered (state.merged[etype])
            for p in positions:
                ref, extractor = cascade[p]
                if position is None and spec.cascade == "until_found" and any(r.items for _, r in results):
                    break
                focus = state.focus.get(etype) if position is not None and p > 0 else None
                task = ExtractionTask(protocol=self.ref, evidence_type=etype,  # type: ignore[arg-type]
                                      field_schema_sha256=spec.schema_sha256, document=state.doc, scope=found.scope,
                                      context=tuple(i.item_id for i in context),
                                      budget=ref.budget if extractor.spec.kind == "agent" else None, focus=focus)
                if self._unavailable(extractor, task, state, p):
                    state.next_position[etype] = p + 1   # no cache record, no call: the gaps loop moves on
                    continue
                call_id, result = self._call(extractor, task, state.text, state.index, spec, context, p)
                results.append((call_id, result))
                step = ran.setdefault(p, {"round": round_no, "position": p, "types": [], "calls": []})
                step["types"].append(etype)
                step["calls"].append(call_id)
                state.next_position[etype] = p + 1
                if position is not None:
                    break
            # `gaps`: GLiNER items wait for the type's LLM position now, before a later type links to them (a later
            # merge would change their ids); a step of this round at that position, with the type's focus unchanged
            llm = self._llm_position(etype)
            if position is not None and llm is not None and self._awaiting_llm(state, etype, results, spec):
                ref, extractor = cascade[llm]
                task = ExtractionTask(protocol=self.ref, evidence_type=etype,  # type: ignore[arg-type]
                                      field_schema_sha256=spec.schema_sha256, document=state.doc, scope=found.scope,
                                      context=tuple(i.item_id for i in context),
                                      budget=ref.budget if extractor.spec.kind == "agent" else None,
                                      focus=state.focus.get(etype) if llm > 0 else None)
                if not self._unavailable(extractor, task, state, llm):
                    call_id, result = self._call(extractor, task, state.text, state.index, spec, context, llm)
                    results.append((call_id, result))
                    step = ran.setdefault(llm, {"round": round_no, "position": llm, "types": [], "calls": []})
                    step["types"].append(etype)
                    step["calls"].append(call_id)
                state.next_position[etype] = llm + 1
            items, sources, collisions, remap = merge.merge_from(results, spec, before,
                                                                 descriptive=merge.descriptive(etype, self.roles))
            dropped = (self._unconfirmed(etype, items)
                       if llm is not None and (position is None or state.next_position.get(etype, 0) > llm) else [])
            items = [i for i in items if i.item_id not in dropped]
            items = stages.after_type(state, etype, items, self.ctx)
            relinked = self._relink(state, etype, remap, items) if self.relink == "on" else []
            state.merged[etype] = items
            # only a merge that dropped or relinked items carries the key: a record without them is unchanged
            unconfirmed: dict[str, Any] = {"unconfirmed": dropped} if dropped else {}
            moved: dict[str, Any] = {"relinked": relinked} if relinked else {}
            self.events.add("merge", used=sorted({i.item_id for _, r in results for i in r.items}),
                            generated=[i.item_id for i in items], agent_id=ENGINE, group_id=state.doc.id,
                            custom={"document": state.doc.id, "evidence_type": etype, "sources": sources,
                                    "collisions": collisions, **unconfirmed, **moved})
        state.steps += [ran[p] for p in sorted(ran)]

    @staticmethod
    def _relink(state: DocState, etype: str, remap: dict[str, str], items: list[Item]) -> list[list[str]]:
        """`relink: on`: a merge of `etype` again (a later round) gave an earlier item a new id (`merge.merge_from`); the
        links of the other types' items, checked results and merged items both, follow it. Returns the [old, new] pairs
        of the items the last merge kept and this one keeps. An item's id does not cover its links
        (`Item.make_id`), so no other id changes."""
        kept, before = {i.item_id for i in items}, {i.item_id for i in state.merged.get(etype, [])}
        moved = {old: new for old, new in remap.items() if old in before and new in kept}
        if not moved:
            return []

        def follow(item: Item) -> Item:
            if not any(target in moved for target in item.links.values()):
                return item
            return item.model_copy(update={"links": {name: moved.get(target, target) for name, target in item.links.items()}})

        for t in state.results:
            if t != etype:
                state.results[t] = [(call_id, r.model_copy(update={"items": tuple(follow(i) for i in r.items)}))
                                    for call_id, r in state.results[t]]
        for t in state.merged:
            if t != etype:
                state.merged[t] = [follow(i) for i in state.merged[t]]
        return sorted([old, new] for old, new in moved.items())

    def _llm_position(self, etype: str) -> int | None:
        """The cascade position of the type's first LLM extractor, the one that confirms GLiNER items; None with
        `confirm: none` or without one."""
        if self.confirm == "none":
            return None
        return next((p for p, (_, e) in enumerate(self.cascades.get(etype, [])) if e.spec.kind == "llm"), None)

    def _unconfirmed(self, etype: str, items: list[Item]) -> list[str]:
        """The ids of the items only GLiNER extractors (kind `model`) found."""
        kind = {e.spec.extractor_id: e.spec.kind for _, e in self.cascades.get(etype, [])}
        return [i.item_id for i in items if all(kind.get(x) == "model" for x in i.found_by)]

    def _awaiting_llm(self, state: DocState, etype: str, results: list[tuple[str, ExtractionResult]],
                      spec: EvidenceTypeSpec) -> bool:
        """The type's results so far, merged, have unconfirmed items and its LLM position has not run yet (`gaps`)."""
        llm = self._llm_position(etype)
        return (llm is not None and state.next_position.get(etype, 0) <= llm
                and bool(self._unconfirmed(etype, merge.merge(results, spec,
                                                              descriptive=merge.descriptive(etype, self.roles))[0])))

    def _unavailable(self, extractor: Extractor, task: ExtractionTask, state: DocState, position: int) -> bool:
        """An extractor whose `available()` says False (a GLiNER step without its service) is not run, before the
        record cache: one `extractor_call` event with status `skipped`, and nothing else (no cache record, no
        checked result, no calls row). A replay has no service to ask: it skips exactly the calls the recorded run
        did not make (no cache key in `attempts`); a call it did make and the cache lost still raises NotRecorded."""
        available = getattr(extractor, "available", None)
        if available is None:
            return False
        if self.calls.mode == "replay":
            attempts = self.calls.attempts
            if attempts is None or cache_key(extractor.spec.extractor_id, task.task_sha256) in attempts:
                return False
        elif available():
            return False
        self.events.add("extractor_call", used=[state.doc.sha256], generated=[], agent_id=extractor.spec.extractor_id,
                        status="skipped", group_id=state.doc.id,
                        custom={"document": state.doc.id, "evidence_type": task.evidence_type, "source": None, "position": position,
                                "model_calls": [], "rejected": 0, "focus": None})
        return True

    def complete(self, state: DocState, round_no: int) -> tuple[bool, str | None, tuple[str, ...]]:
        """The completeness decision after a round: the kind's `study()` on the merged items gives no reason (for
        effect: a direction), or the gap's reason code and the evidence types to escalate (`gap_types`). A
        `completeness` event and a funnel.json entry."""
        rules = kinds.of(self.protocol)
        entry, _ = rules.study(self.protocol, state.doc.id, state.items(), roles=self.roles)
        complete = entry["reason"] is None
        gap = None if complete else entry["reason"]["code"]
        gap_types = rules.gap_types(self.protocol, gap, roles=self.roles) if gap else ()
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
        if self.run_calls is not None and outcome.model_calls:
            self.run_calls.add({
                "key": cache_key(extractor.spec.extractor_id, task.task_sha256, outcome.attempt), "phase": self.phase,
                "document": task.document.id, "evidence_type": task.evidence_type,
                "extractor_id": extractor.spec.extractor_id, "attempt": outcome.attempt, "status": result.status,
                "source": outcome.source, "started_at": started, "ended_at": utc_now(),
                "task": task.model_dump(mode="json"), "result": outcome.raw.model_dump(mode="json"),
                "model_calls": outcome.model_calls})
        self.outputs[f"{CALLS_DIR}/{call_id}.json"] = write_json(self.root / CALLS_DIR / f"{call_id}.json",
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

    # --- the names step -------------------------------------------------------------------------------

    def names_step(self) -> names.NameGroups | None:
        """`names: on`: group the names of every item whose type has a name field, corpus-wide (seeded by the pack),
        then the model check of what is left (not under `regex-only`); names.json, `unresolved_names` and a `names`
        event with every check's cache key and attempt (replay reads them). None with `off`."""
        if self.names != "on":
            return None
        mentions: list[names.Mention] = []
        used: list[str] = []
        for paper in self.corpus.papers:
            for item in self.items.get(paper.id, []):
                field = self.roles.field_or_none(item.evidence_type, "name")
                value = item.fields.get(field) if field is not None else None
                if value is None or not str(value).strip() or not item.spans:
                    continue
                span = min(item.spans, key=lambda s: (s.selector["start"], s.selector["end"]))
                mentions.append(names.Mention(" ".join(str(value).split()), paper.id, span.selector["start"],
                                              span.selector["end"], item.evidence_type))
                used.append(item.item_id)
        groups = names.group_names(mentions, self.texts, seed=self.roles.pack.names_seed)
        owner, alias, instructions = names_check(self.names_model or names_alias(self.cascades, None))
        asks: list[dict[str, Any]] = []
        if self.names_ask:
            groups = names.confirm_leftovers(
                groups, self.texts, lambda prompt: self._names_ask(owner, alias, instructions, prompt, asks))
        self.unresolved_names = len(groups.unresolved)
        self.outputs[NAMES_FILE] = write_json(self.root / NAMES_FILE, dataclasses.asdict(groups))
        self.events.add("names", used=sorted(set(used)), generated=[], agent_id=owner if asks else ENGINE,
                        custom={"groups": len(groups.groups), "matches": len(groups.matches),
                                "unresolved": self.unresolved_names, "checks": asks})
        return groups

    def _names_ask(self, owner: str, alias: str, instructions: str, prompt: str, asks: list[dict[str, Any]]) -> str:
        """One question of the names check through the record cache: the reply as JSON, or {"error": ...}. Counted in
        the run's cost like an extractor call; one row of calls.jsonl when it made model calls."""
        def make() -> tuple[dict[str, Any], list[dict[str, Any]]]:
            return self._structured(alias, instructions, prompt, NamesVerdict, NAMES_SETTINGS)
        asked, check = self._asked(owner, {"user_prompt": prompt}, make, evidence_type="names", event="names_check")
        asks.append(check)
        return json.dumps(asked.value.get("output") or {"error": asked.value.get("error")})

    def _structured(self, alias: str, instructions: str, prompt: str, output_type: type[BaseModel],
                    settings: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """One schema-constrained call as a record-cache value: ({"status": "ok", "output"} or {"status": "error",
        "error"}, the model-call records)."""
        recorder = Recorder(self.provider)
        try:
            out, _ = recorder.structured(alias, instructions, prompt, output_type, **settings)
            return {"status": "ok", "output": out.model_dump(mode="json")}, recorder.records
        except ModelCallError as exc:
            return {"status": "error", "error": exc.reason}, recorder.records

    def _asked(self, owner: str, request: dict[str, Any], make: Callable[[], tuple[dict[str, Any], list[dict[str, Any]]]],
               *, evidence_type: str, event: str, extra: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
        """The bookkeeping of one model call that is not an extractor call (the names check, a stage's `ctx.ask`):
        the record cache, calls/<id>.json (error reason `model_call` on a failure, so it is a failed call wherever
        failed calls are counted and `--retry-errors` asks it again), one `event`, one row of calls.jsonl when it made
        model calls, and the run's cost. Returns (the cache's Asked, the check dict)."""
        started = utc_now()
        asked = self.calls.recorded(owner, request, make)
        failed = asked.value.get("status") == "error"
        call_id = self.events.next_id()
        result = ExtractionResult(
            call_id=call_id, extractor_id=owner, task_sha256=digest(request), status="error" if failed else "ok",
            error=ExtractionError(reason="model_call", detail=str(asked.value.get("error") or "")[:300]) if failed else None,
            model_calls=tuple(r["id"] for r in asked.model_calls))
        self.outputs[f"{CALLS_DIR}/{call_id}.json"] = write_json(self.root / CALLS_DIR / f"{call_id}.json",
                                                               result.model_dump(mode="json"))
        check = {"call_id": call_id, "key": cache_key(owner, digest(request)), "attempt": asked.attempt,
                 "source": asked.source, "status": result.status, "model_calls": list(result.model_calls)}
        self.events.add(event, used=[], generated=[], agent_id=owner, status=result.status, started_at=started,
                        custom={**{k: v for k, v in check.items() if k != "call_id"}, **(extra or {})})
        if self.run_calls is not None and asked.model_calls:
            self.run_calls.add({"key": cache_key(owner, digest(request), asked.attempt), "phase": self.phase,
                                "document": "", "evidence_type": evidence_type, "extractor_id": owner,
                                "attempt": asked.attempt, "status": result.status, "source": asked.source,
                                "started_at": started, "ended_at": utc_now(), "task": request,
                                "result": result.model_dump(mode="json"), "model_calls": asked.model_calls})
        tokens_in, tokens_out = usage(asked.model_calls)
        self.cost["calls"] += 1
        self.cost["cached_calls"] += asked.source == "cache"
        self.cost["model_calls"] += len(asked.model_calls)
        self.cost["made_model_calls"] += len(asked.model_calls) if asked.source == "fresh" else 0
        self.cost["input_tokens"] += tokens_in
        self.cost["output_tokens"] += tokens_out
        return asked, check

    def stage_ask(self, instructions: str, user_prompt: str, output_type: type[BaseModel], purpose: str, alias: str,
                  settings: dict[str, Any], request_extra: dict[str, Any] | None = None) -> BaseModel:
        """`StageContext.ask`: one recorded model call for a stage, through exactly the engine's own path (`_asked`)."""
        owner = f"stage:{purpose}"
        request = {"model": alias, "prompt_sha256": modelcall.prompt_sha256(instructions, output_type),
                   "user_prompt": user_prompt, "settings": settings, **(request_extra or {})}   # plain asks: as before
        asked, _ = self._asked(owner, request, lambda: self._structured(alias, instructions, user_prompt, output_type, settings),
                               evidence_type="stage", event="stage_call", extra={"purpose": purpose})
        if asked.value.get("status") == "error":
            raise stages.StageCallError(f"{purpose}: {asked.value.get('error')}")
        return output_type.model_validate(asked.value["output"])

    def reason_step(self) -> reasoner.Inferences | None:
        """`reason: on`: the run's inferences (reasoner.reason over the merged items of every document), or, in a
        replay, the recorded ones (`recorded_reason`), never reasoned again; reason.json and a `reason` event. None
        with `off`."""
        if self.reason != "on":
            return None
        if self.recorded_reason is not None:
            if not self.recorded_reason.is_file():
                raise NotRecorded(f"the recorded run has no {REASON_FILE}: {self.recorded_reason}")
            inferred = reasoner.from_json(read_json(self.recorded_reason))
        else:
            inferred = reasoner.reason(self.roles.pack, self.protocol, self.items, self.domains)
        self.outputs[REASON_FILE] = write_json(self.root / REASON_FILE, reasoner.to_json(inferred))
        self.events.add("reason", used=sorted({f[0] for f in inferred.link_flags}), generated=[], agent_id=ENGINE,
                        custom={"ontology_sha256": inferred.ontology_sha256, "broader": len(inferred.broader),
                                "link_flags": len(inferred.link_flags),
                                "source": "recorded" if self.recorded_reason is not None else "reasoned"})
        return inferred

    # --- the comparisons step -------------------------------------------------------------------------

    def comparisons_step(self, groups: names.NameGroups | None) -> comparisons.Comparisons:
        """Every kind: the comparisons built from pairs in each study (evidence/comparisons.py), with the names step's
        groups (None with `names: off`), written to comparisons.json."""
        built = comparisons.of_run(self.protocol, [p.id for p in self.corpus.papers], self.items, self.roles, groups)
        self.outputs[COMPARISONS_FILE] = write_json(self.root / COMPARISONS_FILE, built.json())
        return built

    # --- the run --------------------------------------------------------------------------------------

    def finish(self) -> dict[str, Any]:
        papers = self.corpus.papers
        funnel = {p.id: {"screened": self.funnel[p.id]["screen"]["relevant"] is False if self.funnel[p.id]["screen"] else False,
                         "stopped_after": self.funnel[p.id]["stopped_after"]} for p in papers if p.id in self.funnel}
        groups = self.names_step()
        inferred = self.reason_step()
        built = self.comparisons_step(groups)
        answer, used = kinds.of(self.protocol).answer(self.protocol, [p.id for p in papers], self.items, self.reasons,
                                                      funnel, roles=self.roles, groups=groups, comparisons=built,
                                                      reason=inferred)
        evidence = [i.model_dump(mode="json") for p in papers for i in self.items.get(p.id, [])]
        self.outputs[LOCATE_FILE] = write_json(self.root / LOCATE_FILE, self.located)
        self.outputs[EVIDENCE_FILE] = write_lines(self.root / EVIDENCE_FILE, evidence)
        dangling = {"dangling_links": self.dangling} if self.relink == "on" else {}
        unresolved = {"unresolved_names": self.unresolved_names} if self.names == "on" else {}
        self.outputs[FUNNEL_FILE] = write_json(self.root / FUNNEL_FILE, {"strategy": self.strategy,
                                                                               "documents": self.funnel, **dangling,
                                                                               **unresolved})
        self.outputs[ANSWER_FILE] = write_json(self.root / ANSWER_FILE, answer)
        self.outputs[GRAPH_FILE] = write_json(self.root / GRAPH_FILE, graph.build(papers, self.items, answer))
        if self.protocol.kind == "effect":
            custom = {"label": answer["label"], "counts": answer["counts"],
                      "flags": {name: len(docs) for name, docs in answer["flags"].items()},   # Part F1
                      "answer_sha256": self.outputs[ANSWER_FILE], "rule": "label_table"}
        else:   # no label table: the record names the kind whose rules made the answer
            custom = {"kind": self.protocol.kind, "answer_sha256": self.outputs[ANSWER_FILE],
                      "rule": f"kind:{self.protocol.kind}"}
        self.events.add("synthesis", used=sorted(set(used)), generated=["answer"], agent_id=ENGINE, custom=custom)
        for name, result in stages.after_run(RunDir(self.root), self.ctx).items():
            self.outputs[f"{name}.json"] = write_json(self.root / f"{name}.json", result)
        return answer


def _warm(protocol: Protocol, corpus: Corpus, calls: CallCache, cascades: dict[str, list[tuple[ExtractorRef, Extractor]]],
          provider: Provider | None, locator: Locator | None, strategy: Strategy, workers: int,
          run_calls: RunCalls | None = None, confirm: Confirm = "none", relink: Relink = "off",
          plan: Plan | None = None, names_model: str | None = None) -> None:
    """Fill the record cache with every paper's calls, `workers` papers at once; the outputs are thrown away,
    except the rows each call adds to the run's calls.jsonl (`run_calls`, phase `warm`) as it completes."""
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(workers) as pool:
        def one(i: int, paper: Any) -> None:
            root = Path(tmp) / str(i)
            root.mkdir()
            Execution(protocol, corpus, root, f"warm-{i}", calls, cascades, provider, locator, strategy,
                      run_calls, "warm", confirm, relink, plan=plan, names_model=names_model).document(paper)
        futures = [pool.submit(one, i, p) for i, p in enumerate(corpus.papers)]
        try:
            for future in futures:
                future.result()      # re-raise the first failure
        except BaseException:        # a failure or Ctrl-C: papers not yet started are never run
            pool.shutdown(wait=False, cancel_futures=True)
            raise


def execute_run(protocol_bytes: bytes, settings: Settings, out_dir: Path | str, *, mode: Mode = "run",
                run_id: str | None = None, provider: Provider | None = None, locator: Locator | None = None,
                bypass: Any = None, retry_errors: bool = False, source_run: str | None = None,
                attempts: dict[str, int] | None = None, workers: int = 1, source_dir: Path | None = None,
                before_seal: Callable[[Path], None] | None = None) -> Path:
    """Execute and write one run directory; returns its path. `source_dir`: the folder of the recorded run; in
    mode replay its reason.json is read instead of reasoning again (a reexec reasons again: its items may differ).
    `before_seal(root)`: writes more files into the finished run (reexec.json) before manifest.json seals it."""
    for module in settings.imports:
        importlib.import_module(module)
    protocol = parse(protocol_bytes.decode("utf-8"), settings.domains)
    corpus = Corpus(settings.corpus)
    run_id = run_id or new_run_id(protocol.id, "" if mode == "run" else f"-{mode}")
    root = Path(out_dir) / run_id
    # everything that can refuse the run (the pack, the extractor names, the lock's digests) comes before the folder
    if settings.gliner_url and settings.gliner_model is None and _uses_gliner(protocol):
        served = gliner.info(settings.gliner_url)
        settings = replace(settings, gliner_model=served["model"] if served else None)
    cascades = build_extractors(protocol, settings.selection, settings.model, settings.gliner_url, settings.gliner_model)
    domains = Path(settings.domains) if settings.domains is not None else None
    plan = load_plan(settings.plan) if settings.plan is not None else None
    lock = lockfile.lock(protocol, cascades, domains, plan=plan)
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise RunDirExists(root) from None
    (root / PROTOCOL_FILE).write_bytes(protocol_bytes)
    cache = CallCache(JsonlCache(Path(settings.cache) / CACHE_FILE), mode, bypass, retry_errors, attempts)
    run_calls = RunCalls(root / RUN_CALLS_FILE) if mode == "run" else None
    ex = Execution(protocol, corpus, root, run_id, cache, cascades, provider, locator, settings.strategy, run_calls,
                   confirm=settings.confirm, relink=settings.relink, names=settings.names, names_model=names_alias(cascades, settings.model),
                   names_ask=settings.selection != "regex-only", reason=settings.reason,
                   domains=Path(settings.domains) if settings.domains is not None else None, plan=plan,
                   mode=mode, recorded_reason=source_dir / REASON_FILE if mode == "replay" and source_dir is not None else None)
    ex.outputs[PROTOCOL_FILE] = sha256_hex(protocol_bytes)
    ex.outputs[LOCK_FILE] = write_json(root / LOCK_FILE, lock)
    if settings.plan is not None:   # the run's own copy: a replay reads it, not the original path
        plan_bytes = Path(settings.plan).read_bytes()
        (root / PLAN_FILE).write_bytes(plan_bytes)
        ex.outputs[PLAN_FILE] = sha256_hex(plan_bytes)
    ex.cost["workers"] = workers
    t0 = time.monotonic()
    try:
        if mode == "run" and workers > 1 and settings.selection != "regex-only" and provider is not None:
            _warm(protocol, corpus, cache, cascades, provider, locator, settings.strategy, workers, run_calls,
                  settings.confirm, settings.relink, plan, names_alias(cascades, settings.model))
        for paper in corpus.papers:
            ex.document(paper)
        ex.finish()
    except BaseException as exc:   # a crash or Ctrl-C: every file a reader expects, a failed seal, no run.json
        try:
            sealing.fill_expected(root, settings)
            sealing.seal(root, corpus.manifest_sha256, status="failed",
                         error=f"{type(exc).__name__}: {modelcall.redact(str(exc))[:300]}")
        except Exception as failed:   # the caller must still see the run's own error (its type sets the exit code)
            print(f"WARN {root}: could not seal the failed run: {type(failed).__name__}: {failed}", file=sys.stderr)
        raise
    ex.cost["seconds"] = round(time.monotonic() - t0, 3)
    if settings.gliner_model is None:   # GLiNER came up after the run started: record the model it served
        served = sorted({e.model for c in cascades.values() for ref, e in c
                         if isinstance(e, gliner.GlinerExtractor) and "model" not in ref.config and e.model})
        if served:
            settings = replace(settings, gliner_model=served[0])
    specs = {e.spec.extractor_id: e.spec for c in cascades.values() for _, e in c}
    final = lockfile.lock(protocol, cascades, domains, plan=plan)
    if final["extractors"] != lock["extractors"]:   # a GLiNER extractor learned its model during the run: the lock names the ids it used
        ex.outputs[LOCK_FILE] = write_json(root / LOCK_FILE, final)
    write_json(root / RUN_FILE, {
        "run_id": run_id, "mode": mode, "source_run": source_run, "protocol": {"id": protocol.id, "sha256": protocol.sha256},
        "manifest_sha256": corpus.manifest_sha256, "corpus_id": corpus.corpus_id, "extractors": list(specs),
        "extractor_specs": {k: _spec_json(s) for k, s in specs.items()}, "outputs": dict(sorted(ex.outputs.items())),
        "cost": ex.cost, "chain_head": ex.events.head, "settings": settings.json(),
        **({"dangling_links": ex.dangling} if settings.relink == "on" else {}),
        **({"unresolved_names": ex.unresolved_names} if settings.names == "on" else {}),
        **({"stages": stages.names()} if stages.names() else {})})
    if before_seal is not None:
        before_seal(root)
    sealing.seal(root, corpus.manifest_sha256, status="complete")   # last: after run.json and the final lock
    return root


def _uses_gliner(protocol: Protocol) -> bool:
    steps = [*(s.extractors for s in protocol.evidence_types.values()),
             *([protocol.screen.spec.extractors] if protocol.screen is not None else [])]
    return any(ref.name in gliner.FACTORIES for refs in steps for ref in refs)


def _spec_json(spec: ExtractorSpec) -> dict[str, Any]:
    return {**spec.model_dump(mode="json"), "config_sha256": spec.config_sha256, "extractor_id": spec.extractor_id}


def run(protocol_path: Path | str, corpus: Path | str, out_dir: Path | str, *, cache: Path | str | None = None,
        selection: Selection = "cascade", model: str | None = None, imports: list[str] | None = None,
        provider: Provider | None = None, locator: Locator | None = None, run_id: str | None = None,
        retry_errors: bool = False, strategy: Strategy = "gaps", workers: int = 3, confirm: Confirm = "llm",
        relink: Relink = "on", domains: Path | str | None = None, names: Names = "off", reason: Reason = "on",
        plan: Path | str | None = None) -> Path:
    """A normal run: cached calls are reused, new ones are made and stored. `domains`: the folder of the protocol's
    pack when it is not domains/ (recorded in run.json's settings, so a replay reads the same pack)."""
    settings = Settings(corpus=str(Path(corpus).resolve()),
                        cache=str((Path(cache) if cache else Path(out_dir) / "cache").resolve()),
                        selection=selection, model=model, imports=list(imports or []), strategy=strategy,
                        confirm=confirm, relink=relink, names=names, reason=reason,
                        domains=str(Path(domains).resolve()) if domains is not None else None,
                        plan=Path(plan).resolve() if plan is not None else None)
    return execute_run(Path(protocol_path).read_bytes(), settings, out_dir, run_id=run_id,
                       provider=provider if provider is not None else default_provider, locator=locator,
                       retry_errors=retry_errors, workers=workers)
