"""Plan runs (Wave 2 Task 8.1): one confirmed plan, run end to end over a corpus.

    evidence run --plan plan.json --corpus DIR --out DIR

What a plan run is, beside a protocol run:
- The protocol is written from the plan by code (`protocol_for`), never by hand: the compared things and the measures
  of the plan become the condition roles and the metric names, and every word an extractor reads comes from the
  plan's locked word list compiled by `evidence.words.compile.compile_words` (screen terms, condition, metric and claim
  patterns), never from a pack's words.yaml. The screen keeps a paper the word list misses for the model screen
  (`lexical_miss: escalate`). The protocol's bytes are the run's protocol.yaml, so a replay reads the same ones.
- The run carries its own stage set (`stage_entries`, recorded in run.json `stages`; it never touches the stage
  registry): the experiment map (W3) before extraction and its items after each paper; the required re-check of regex
  finds (W1) after each type, with its report after the run; open claims (W5, subject pattern from compile_words) and
  builds-on links through OpenAlex (W5) after each paper; the ontology report (W2) after the run.
- After the names, reasoner and comparisons steps, the engine calls `finish` (below) before it writes answer.json:
  claim verbs are grouped (W5 `group_relations` + `apply_groups`, one recorded call), the records graph is built
  (W4 `build`, the field's ontology files, written as records.nq), every evidence line runs in its own try block and
  each line's decisions are rerun and labelled, as evidence/planlines.py `PlanLines` answers a plan's lines (the run's
  plan version and directions). answer.json is then {lines, answer (main answer, "missing: <line>"), labels, reruns,
  claim_groups, synthesis (the kind's answer, as a protocol run writes it)}. `relink` answers them again the same way.
Every model call of these steps goes through the run's recorder (`ctx.ask` / `ctx.dspy_lm`), so a replay is
byte-identical and asks no model; OpenAlex answers are recorded in the run folder (openalex.jsonl) and a replay reads
the recorded run's file only.

Decisions (Wave 2): the first compared thing of the plan is the treatment side, every later one a control (the
planner's things step lists the asked-about thing first; compile_words appends `not_a_system` to controls); a plan
without measures gets the one metric name "other"; GLiNER steps are left out of plan runs (no service is assumed, and
GLiNER-only finds need the LLM anyway); measurement values are kept as written (no fraction rule: the measures are
the plan's, not a pack's)."""
from __future__ import annotations

import functools
import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import yaml

from .contract import Item
from .plan import Plan, load_plan
from .planlines import OTHER, PlanLines, compare_sides, directions, sides, threshold
from .words.compile import compile_words

__all__ = ["STAGE_SET", "check_request", "finish", "protocol_for", "relink", "run", "stage_entries"]

STAGE_SET = "plan"            # Settings.stage_set of a plan run
ANY = "any"   # the treatment role of a plan that names no compared thing (its things are all measures)
RECHECK_REPORT = "recheck_report"   # the stage that writes the re-check verdicts (recheck_report.json)
MAX_LINK_SENTENCES = 20       # builds-on candidates read per paper (one model call each)


# --- the plan's things ----------------------------------------------------------------------------------------------

def compiled(plan: Plan) -> dict[str, Any]:
    """The extractor words of the plan (compile_words over its locked word list, the measures as metrics, each with
    its direction from the plan)."""
    lower = {m for m, higher in directions(plan).items() if higher is False}
    return compile_words(plan.words, metric_things=set(plan.measures), lower_is_better=lower)


def _names(plan: Plan, thing: str, n: int = 6) -> str:
    names = [*plan.words.things.get(thing, []), *plan.words.ontology_names.get(thing, [])][:n]
    return ", ".join(names) or thing


# --- the protocol -----------------------------------------------------------------------------------------------------

def protocol_for(plan: Plan) -> bytes:
    """The plan run's protocol (YAML), written by code from the plan: types and extractors as the default pack's
    effect protocol, the roles, metric names and descriptions from the plan, every extractor word from compile_words.
    The protocol is made from the plan at writer try 0: a later writer try (Plan.writer_try) keeps the protocol's id and
    bytes, so its extraction tasks hit the record cache of the first try and only the writer is asked again."""
    plan = plan.model_copy(update={"writer_try": 0})
    words = compiled(plan)
    things = sides(plan)
    measures = list(plan.measures) or [OTHER]
    roles = [*things, OTHER] if OTHER not in things else things
    canon = [*measures, OTHER] if OTHER not in measures else measures
    treatment, control = compare_sides(plan)
    if treatment == control:   # no compared thing (off-template q06, q10): the synthesis still needs two distinct roles
        treatment, roles = ANY, [*roles, ANY]
    better = directions(plan)
    conditions = {"conditions": words["conditions"], "not_a_system": words["not_a_system"]}
    metrics = {"metrics": words["metrics"]}
    role_text = "; ".join(f"{t} for {_names(plan, t)}" for t in things)
    metric_text = "; ".join(f"{m} for {_names(plan, m)}" for m in plan.measures)
    protocol: dict[str, Any] = {
        "id": f"plan-{plan.sha256[:12]}",
        "version": 2,
        "question": plan.question,
        "locate": {"strategy": "exhaustive"},
        "screen": {
            "question": f"Does the paper report results that bear on this question: {plan.question}",
            "terms": words["screen_terms"],
            "extractors": [{"name": "regex_screen"}, {"name": "llm_screen"}],
            "on_fail": "skip",
            "lexical_miss": "escalate",
        },
        "evidence_types": {
            "condition": {
                "description": ("An experimental condition the paper compares: a system, method, treatment or group whose "
                                f"results are reported. role is {role_text or 'none named'}; {OTHER} for anything else."),
                "fields": {"type": "object", "additionalProperties": False, "required": ["label", "role"],
                           "properties": {"label": {"type": "string", "minLength": 1,
                                                    "description": "the condition's name as the paper gives it"},
                                          "role": {"type": "string", "enum": roles}}},
                "roles": ["condition_label"],
                "merge_key": ["label", "role"],
                "extractors": [{"name": "regex_condition", "config": conditions}, {"name": "llm_condition"}],
            },
            "metric": {
                "description": ("A measure the paper reports results on. canonical is "
                                f"{metric_text or 'none named'}; {OTHER} for anything else."),
                "fields": {"type": "object", "additionalProperties": False,
                           "required": ["name", "canonical", "higher_is_better"],
                           "properties": {"name": {"type": "string", "minLength": 1,
                                                   "description": "the measure's name as the paper gives it"},
                                          "canonical": {"type": "string", "enum": canon},
                                          "higher_is_better": {"type": "boolean"}}},
                "roles": ["metric_label"],
                "merge_key": ["name", "canonical"],
                "extractors": [{"name": "regex_metric", "config": metrics}, {"name": "llm_metric"}],
            },
            "measurement": {
                "description": ("One reported result: the value of one measure for one condition, as the paper writes it. "
                                "dataset is the dataset, population or setting it was measured on, or null."),
                "fields": {"type": "object", "additionalProperties": False, "required": ["value", "dataset"],
                           "properties": {"value": {"type": "number"},
                                          "dataset": {"type": ["string", "null"]},
                                          "form": {"type": ["string", "null"],
                                                   "enum": ["plain", "percent", "fraction", "k_of_n", "range",
                                                            "plus_minus", None]},
                                          "table_unsure": {"type": "boolean"}}},
                "links": {"condition": "condition", "metric": "metric"},
                "context": ["condition", "metric"],
                "roles": ["value", "condition_label", "metric_label", "value_total"],
                "merge_key": ["value"],
                "extractors": [
                    {"name": "regex_measurement", "config": {**conditions, **metrics, "system_nouns": []}},
                    {"name": "number_measurement", "config": {**conditions, **metrics, "system_nouns": [],
                                                              "fraction_metrics": []}},
                    {"name": "llm_measurement"}],
            },
            "author_claim": {
                "description": (f"The authors' own conclusion about whether {treatment} improves the results "
                                f"({', '.join(plan.measures) or 'any measure'}): improves, no_effect or worsens."),
                "fields": {"type": "object", "additionalProperties": False, "required": ["direction"],
                           "properties": {"direction": {"type": "string",
                                                        "enum": ["improves", "no_effect", "worsens"]}}},
                "roles": ["claim"],
                "extractors": [{"name": "regex_author_claim",
                                "config": {"subject": words["subject"], "claims": words["claims"]}},
                               {"name": "llm_author_claim"}],
            },
        },
        "synthesis": {
            "compare": {"treatment": treatment, "control": control},
            "metrics": [{"canonical": m, "higher_is_better": better.get(m) is not False} for m in measures],
            "min_effect": threshold(plan),
            "claim_map": {"improves": "supports", "worsens": "contradicts", "no_effect": "neutral"},
            "label": [{"when": {"supporting": ">0", "contradicting": ">0"}, "then": "mixed"},
                      {"when": {"supporting": ">0"}, "then": "supported"},
                      {"when": {"contradicting": ">0"}, "then": "refuted"},
                      {"when": {"neutral": ">0"}, "then": "no_effect"},
                      {"then": "insufficient"}],
        },
    }
    head = "# Written by code from the plan (evidence/planrun.py protocol_for); do not edit.\n"
    return (head + yaml.safe_dump(protocol, sort_keys=False, allow_unicode=True, width=120)).encode("utf-8")


# --- the run's own stages ---------------------------------------------------------------------------------------------

_DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"<>)\]]+")
_ARXIV = re.compile(r"\b(?:arXiv:)?(\d{4}\.\d{4,5})(?:v\d+)?\b")
_CITED = re.compile(r"\[\d+(?:[,–-]\s*\d+)*\]|\bet al\.?,?\s*\(?(?:19|20)\d\d\)?")
_ET_AL_END = re.compile(r"\bet al\.$")


def link_sentences(text: str) -> list[tuple[int, int, str | None, str | None]]:
    """(start, end, doi, arxiv id) of each sentence that cites another work (a DOI, an arXiv id, a bracketed number
    or "et al." with a year), at most MAX_LINK_SENTENCES per paper, in text order."""
    from .extractors import base
    spans: list[tuple[int, int]] = []
    for s, e in base.sentences(text):   # the splitter cuts after "et al.": join that piece with the next
        if spans and _ET_AL_END.search(text[spans[-1][0]:spans[-1][1]]):
            spans[-1] = (spans[-1][0], e)
        else:
            spans.append((s, e))
    out = []
    for s, e in spans:
        sentence = text[s:e]
        doi, arxiv = _DOI.search(sentence), _ARXIV.search(sentence)
        if doi or arxiv or _CITED.search(sentence):
            out.append((s, e, doi.group(0).rstrip(".,;") if doi else None, arxiv.group(1) if arxiv else None))
        if len(out) == MAX_LINK_SENTENCES:
            break
    return out


def links_stage(doc: Any, ctx: Any) -> list[Item]:
    """after_document: the paper's ties to other works (W5): each citing sentence read by `ReadLink` (recorded), the
    cited work resolved among the run's papers first, then through OpenAlex (recorded in the run folder). A link to a
    work outside the corpus is kept, `outside_set` true ("outside the set")."""
    from agent.anchor import selector_at

    from . import openalex
    from .contract import Span
    from .records import item
    from .unchecked import ITEM_ERRORS, note, reason
    out: list[Item] = []
    skipped: list[str] = []
    texts = {k: v for k, v in ctx.texts().items() if k != doc.doc.id}
    for s, e, doi, arxiv in link_sentences(doc.text):
        try:
            relation, cited = openalex.read_link(doc.text[s:e], ctx)
        except ITEM_ERRORS as exc:   # one failed sentence is skipped, listed in stage_report.json
            skipped.append(f"unchecked: sentence {s}-{e}: {reason(exc)}")
            continue
        if not relation:
            continue
        span = Span.of("link", selector_at(doc.text, s, e, file=doc.doc.file, sha256=doc.doc.sha256))
        record = openalex.resolve(cited or doc.text[s:e], doi, arxiv, texts, ctx, subject_doc=doc.doc.id, span=span,
                                  relation=relation)
        out.append(item(record))
    note(ctx, "links", doc.doc.id, skipped)
    return out


def run_steps(*, reason: str = "on", links: str = "on") -> tuple[Any, ...]:
    """The DSPy steps a plan run calls (each may run on tuned instructions; the lock records those): the module-level
    Step instances, and the names of the steps made per call."""
    from . import claims, experiments, openalex
    from .extractors import recheck
    from .ontology import fill
    out: list[Any] = [experiments.NAME_STEP, recheck.STEP, claims._READ, claims._GROUP]
    if links == "on":
        out.append(openalex._READ)
    if reason == "on":
        out.append(fill.STEP)
    return tuple(out)


def no_tree(run: Any, ctx: Any) -> dict[str, Any]:
    """The `ontology` stage of a run with reasoning off: no tree, no model call."""
    return {"tree": "reasoning off: no tree"}


def stage_entries(plan: Plan, *, reason: str = "on", links: str = "on",
                  version: str = "v1") -> list[tuple[str, Any, Callable[..., Any]]]:
    """The plan run's own stages, in order (name, seam, fn). `links` off leaves out the builds-on links stage (no
    ReadLink call, no OpenAlex request); `reason` off gives the ontology stage `no_tree`. `version` v2
    (Settings.plan_version): no experiment map before the screen, and none for a paper the screen left out (scilead-07
    mapped 31 papers, 27 then screened out)."""
    from . import experiments
    from .claims import claim_stage
    from .extractors.recheck import recheck, recheck_report
    from .ontology.fill import ontology_stage
    from . import unchecked, written
    return [
        *([("map-experiments", "before_extract", experiments.before_extract)] if version == "v1" else []),
        ("recheck", "after_type", recheck),
        (("experiment-items", "after_document", experiments.after_document) if version == "v1" else
         ("experiment-items-kept", "after_document", experiments.after_document_kept)),
        ("claims", "after_document", claim_stage()),   # subject and cues from the plan's word list
        *([("links", "after_document", links_stage)] if links == "on" else []),
        (RECHECK_REPORT, "after_run", recheck_report),
        (unchecked.NAME, "after_run", unchecked.report),   # the items the per-item stages could not read
        ("ontology", "after_run", ontology_stage if reason == "on" else no_tree),
        *([(written.STAGE, "after_run", written.written_stage)] if plan.answer_by == "written" else []),
    ]


# --- after the run: claim groups, the records graph, the lines, the reruns ------------------------------------------

def group_claims(items: dict[str, list[Item]], ctx: Any) -> tuple[dict[str, list[Item]], dict[str, str]]:
    """The run's claims with `relation_group` filled (W5: one recorded `group_relations` call over the run's distinct
    verbs, then `apply_groups`), and the verb -> group mapping. No claims: unchanged, no call."""
    from .claims import apply_groups, group_relations
    from .contract import Span
    from .records import CLAIM, ClaimRecord, item

    from .unchecked import GROUPS, ITEM_ERRORS, RUN, note, reason

    claims = [i for its in items.values() for i in its if i.evidence_type == CLAIM]
    if not claims:
        return items, {}
    verbs = [str(i.fields["relation"]) for i in claims]
    try:
        mapping = group_relations(verbs, ctx)
    except ITEM_ERRORS as exc:   # the claims are kept ungrouped ("other: <verb>"), listed in stage_report.json
        mapping = {v: f"other: {v}" for v in sorted({v.strip() for v in verbs if v.strip()}, key=str.casefold)}
        note(ctx, GROUPS, RUN, [f"unchecked: claim groups: {reason(exc)}"])

    def regroup(it: Item) -> Item:
        if it.evidence_type != CLAIM:
            return it
        record = ClaimRecord(**{k: v for k, v in it.fields.items()}, span=Span.model_validate(it.spans[0].model_dump()))
        return item(apply_groups([record], mapping)[0])

    return {doc: [regroup(i) for i in its] for doc, its in items.items()}, mapping


OUTSIDE = "outside the set"


def links_of(items: dict[str, list[Item]]) -> list[dict[str, Any]]:
    """The run's builds-on links for the answer: a cited work that is no paper of the corpus says "outside the set".
    `work` is the resolved OpenAlex work id ("W2741809807"), null when the link was not resolved through OpenAlex."""
    from .records import LINK
    out = []
    for doc in sorted(items):
        for it in items[doc]:
            if it.evidence_type == LINK:
                f = it.fields
                out.append({"paper": f["subject_doc"], "relation": f["relation"], "ref": f["object_ref"],
                            "work": f.get("work"), "in_set": f.get("object_doc"),
                            "text": OUTSIDE if f["outside_set"] else f"in the set: {f.get('object_doc')}",
                            **({"resolve_failed": f["resolve_failed"]} if f.get("resolve_failed") else {})})
    return out


def answer(lines: PlanLines, synthesis: dict[str, Any], groups: Mapping[str, str],
           items: dict[str, list[Item]] | None = None) -> dict[str, Any]:
    """answer.json of a plan run: the plan's lines as `lines` answers them (each in its own try block, the main
    answer, labels and reruns), the claim groups and the builds-on links."""
    from .claims import grouped_line
    plan = lines.plan
    return {"system": "plan", "question": plan.question, "plan_sha256": plan.sha256, **lines.answer(),
            "claim_groups": {"mapping": dict(groups), "line": grouped_line(groups) if groups else None},
            "links": links_of(items or {}),
            "synthesis": synthesis}


def records(papers: list[Any], items: dict[str, list[Item]], roles: Any, field: str, *, reason: str = "on") -> Any:
    """The records graph (W4 build) with the field's ontology (W2 sources.load; None: no tree, and always None when
    `reason` is off)."""
    from .kg.build import build
    return build(papers, items, roles, load_cached(field) if reason == "on" else None)


def finish(plan: Plan, papers: list[Any], items: dict[str, list[Item]], roles: Any, ctx: Any,
           synthesis: dict[str, Any], *, reason: str = "on",
           version: str = "v1") -> tuple[dict[str, list[Item]], bytes, dict[str, Any]]:
    """(the items with claim groups, records.nq bytes, answer.json) of a plan run, after its extraction. `reason`
    off: the records graph has no field ontology; `version`: Settings.plan_version, how the lines are answered."""
    from .kg.build import serialize
    items, groups = group_claims(items, ctx)
    store = records(papers, items, roles, plan.field, reason=reason)
    return items, serialize(store), answer(PlanLines(plan, store, version=version, items=items), synthesis, groups, items)


# --- the command ------------------------------------------------------------------------------------------------------

class PlanNotRunnable(ValueError):
    """The plan cannot run: a decision is unconfirmed, or the word list was not written by the pinned orchestrator."""


def check_runnable(plan: Plan) -> None:
    """Refuse an unconfirmed plan, a word list another model wrote ("word list by the pinned orch-model"), and a plan
    whose answer kind cannot run (plankinds.answer_problems: a best answer with no measure or one compared thing)."""
    from modelcall.pins import ORCH_ALIAS

    from .plankinds import answer_problems
    if not plan.ready():
        raise PlanNotRunnable("the plan is not confirmed: confirm every decision before the run")
    if plan.words.written_by not in (ORCH_ALIAS, "none"):
        raise PlanNotRunnable(f"the word list was written by {plan.words.written_by!r}; a plan run needs one written "
                              f"by {ORCH_ALIAS!r}")
    problems = answer_problems(plan)
    if problems:
        raise PlanNotRunnable(f"the plan's answer kind cannot run: {'; '.join(problems)}")


def check_request(plan_path: Path | str, **settings: Any) -> None:
    """Refuse a plan run before anything is written (`evidence run --plan`): a setting a plan run fixes asked for with
    another value (engine.PLAN_RUN_FIXED), an unreadable or invalid plan file (OSError, ValueError), an unconfirmed plan
    or a word list another model wrote (PlanNotRunnable)."""
    from .engine import plan_run_refusal
    refused = plan_run_refusal(**settings)
    if refused is not None:
        raise PlanNotRunnable(refused)
    check_runnable(load_plan(plan_path))


def load_cached(field: str) -> Any:
    """`ontology.sources.load(field)`, parsed once per set of file contents (`ontology_hashes`): a big MeSH file is
    not parsed again by the graph, the ontology report and a relink. Callers must not change the graph."""
    from .ontology.sources import ontology_hashes
    return _load(field, json.dumps(ontology_hashes(field), sort_keys=True))


@functools.lru_cache(maxsize=8)
def _load(field: str, _hashes: str) -> Any:
    from .ontology.sources import load
    return load(field)


def run(plan_path: Path | str, corpus: Path | str, out_dir: Path | str, *, reason: str = "on", links: str = "on",
        **kw: Any) -> Path:
    """A plan run (`evidence run --plan`): the protocol from the plan, the plan's stages, then `engine.execute_run`.
    `kw` as `engine.run_plan` takes them (cache, model, provider, workers, run_id, retry_errors, strategy, selection;
    a setting a plan run fixes, engine.PLAN_RUN_FIXED, only at its fixed value). `reason` off (Settings.reason, recorded
    in run.json; `--reason` of the CLI): no reasoner, no field ontology in the records graph or the lock, and the
    ontology stage writes "reasoning off: no tree" with no model call. `links` off (recorded as settings "links":
    "off"): no builds-on links stage, so no ReadLink call and no OpenAlex request."""
    from . import engine
    if reason not in ("on", "off") or links not in ("on", "off"):
        raise ValueError(f"reason and links are 'on' or 'off', not {reason!r} / {links!r}")
    plan = load_plan(plan_path)
    check_runnable(plan)
    from .plankinds import kind_protocol
    return engine.run_plan(plan_path, kind_protocol(plan), corpus, out_dir, reason=reason, links=links, **kw)


# --- after a human reviews the LLM's ontology links -----------------------------------------------------------------

def relink(run_dir: Path | str, accepted: list[str], rejected: list[str]) -> dict[str, Any]:
    """The links review of a finished plan run (W2 `review`, written as links_review.json beside the sealed outputs),
    then the lines again on the records graph with the accepted LLM links ("child -> parent") added to the field's
    ontology (W4: the same lines, decisions and reruns), answered as the run answered them (its plan version, the
    directions of its extracted items). Nothing the run sealed changes; the new answer is returned."""
    from .kg.build import build
    from .ontology.fill import add_links, review
    from .rundir import ANSWER_FILE, PLAN_FILE, Corpus, RunDir
    run = RunDir(run_dir)
    review(run, accepted, rejected)
    plan = load_plan(run.file(PLAN_FILE))
    before = run.json(ANSWER_FILE)
    settings = run.settings
    assert settings is not None, f"{run_dir} has no run.json settings"
    corpus = Corpus(settings.corpus)
    items = run.papers(settings.corpus)
    pairs = [tuple(x.strip() for x in a.split("->", 1)) for a in accepted if "->" in a]
    graph = load_cached(plan.field) if settings.reason == "on" else None   # reasoning off: no field ontology
    if pairs:
        import rdflib
        graph = add_links(graph if graph is not None else rdflib.Graph(), pairs)  # type: ignore[arg-type]
    store = build(corpus.papers, items, run.roles(), graph)
    out = answer(PlanLines.of_run(run_dir, store, plan=plan, items=items), before.get("synthesis") or {},
                 (before.get("claim_groups") or {}).get("mapping") or {}, items)
    return {"review": {"accepted": sorted(accepted), "rejected": sorted(rejected)}, **out}

