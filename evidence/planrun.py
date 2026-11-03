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
  (W4 `build`, the field's ontology files, written as records.nq), every evidence line runs in its own try block
  (W7 `run_lines` over W4 `run_query`, its `$params` from the plan's decisions), each line's decisions are rerun
  (W4 `sensitivity.rerun`) and labelled. answer.json is then {lines, answer (main answer, "missing: <line>"), labels,
  reruns, claim_groups, synthesis (the kind's answer, as a protocol run writes it)}.
Every model call of these steps goes through the run's recorder (`ctx.ask` / `ctx.dspy_lm`), so a replay is
byte-identical and asks no model; OpenAlex answers are recorded in the run folder (openalex.jsonl) and a replay reads
the recorded run's file only.

Decisions (Wave 2): the first compared thing of the plan is the treatment side, every later one a control (the
planner's things step lists the asked-about thing first; compile_words appends `not_a_system` to controls); a plan
without measures gets the one metric name "other"; GLiNER steps are left out of plan runs (no service is assumed, and
GLiNER-only finds need the LLM anyway); measurement values are kept as written (no fraction rule: the measures are
the plan's, not a pack's)."""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import yaml

from .contract import Item
from .plan import MAIN_RULE, Decision, Plan, load_plan
from .words.compile import compile_words

__all__ = ["DEFAULT_THRESHOLD", "OTHER", "RECORDS_FILE", "STAGE_SET", "finish", "line_params", "protocol_for", "run",
           "sides", "stage_entries"]

STAGE_SET = "plan"            # Settings.stage_set of a plan run
RECORDS_FILE = "records.nq"   # the records graph, sorted N-Quads (W4 serialize)
OTHER = "other"
DEFAULT_THRESHOLD = 0.01      # min_effect when the plan has no threshold decision
MAX_LINK_SENTENCES = 20       # builds-on candidates read per paper (one model call each)
LIST_DECISIONS = ("must_match", "counts_as")


# --- the plan's things ----------------------------------------------------------------------------------------------

def compiled(plan: Plan) -> dict[str, Any]:
    """The extractor words of the plan (compile_words over its locked word list, the measures as metrics)."""
    return compile_words(plan.words, metric_things=set(plan.measures))


def sides(plan: Plan) -> list[str]:
    """The compared things in plan order (treatment first); [] when the plan names none."""
    return [t for t in plan.words.things if t not in plan.measures]


def _names(plan: Plan, thing: str, n: int = 6) -> str:
    names = [*plan.words.things.get(thing, []), *plan.words.ontology_names.get(thing, [])][:n]
    return ", ".join(names) or thing


def _value(raw: Any) -> Any:
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def threshold(plan: Plan) -> float:
    d = next((x for x in plan.decisions if x.type == "threshold"), None)
    value = _value(d.value) if d is not None else None
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else DEFAULT_THRESHOLD


# --- the protocol -----------------------------------------------------------------------------------------------------

def protocol_for(plan: Plan) -> bytes:
    """The plan run's protocol (YAML), written by code from the plan: types and extractors as the default pack's
    effect protocol, the roles, metric names and descriptions from the plan, every extractor word from compile_words."""
    words = compiled(plan)
    things = sides(plan)
    measures = list(plan.measures) or [OTHER]
    roles = [*things, OTHER] if OTHER not in things else things
    canon = [*measures, OTHER] if OTHER not in measures else measures
    treatment = things[0] if things else OTHER
    control = things[1] if len(things) > 1 else OTHER
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
            "metrics": [{"canonical": m, "higher_is_better": True} for m in measures],
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
    out: list[Item] = []
    texts = {k: v for k, v in ctx.texts().items() if k != doc.doc.id}
    for s, e, doi, arxiv in link_sentences(doc.text):
        relation, cited = openalex.read_link(doc.text[s:e], ctx)
        if not relation:
            continue
        span = Span.of("link", selector_at(doc.text, s, e, file=doc.doc.file, sha256=doc.doc.sha256))
        record = openalex.resolve(cited or doc.text[s:e], doi, arxiv, texts, ctx, subject_doc=doc.doc.id, span=span,
                                  relation=relation)
        out.append(item(record))
    return out




def stage_entries(plan: Plan) -> list[tuple[str, Any, Callable[..., Any]]]:
    """The plan run's own stages, in order (name, seam, fn)."""
    from . import experiments
    from .claims import claim_stage
    from .extractors.recheck import recheck, recheck_report
    from .ontology.fill import ontology_stage
    return [
        ("map-experiments", "before_extract", experiments.before_extract),
        ("recheck", "after_type", recheck),
        ("experiment-items", "after_document", experiments.after_document),
        ("claims", "after_document", claim_stage()),   # subject and cues from the plan's word list
        ("links", "after_document", links_stage),
        ("recheck_report", "after_run", recheck_report),
        ("ontology", "after_run", ontology_stage),
    ]


# --- after the run: claim groups, the records graph, the lines, the reruns ------------------------------------------

def group_claims(items: dict[str, list[Item]], ctx: Any) -> tuple[dict[str, list[Item]], dict[str, str]]:
    """The run's claims with `relation_group` filled (W5: one recorded `group_relations` call over the run's distinct
    verbs, then `apply_groups`), and the verb -> group mapping. No claims: unchanged, no call."""
    from .claims import apply_groups, group_relations
    from .contract import Span
    from .records import CLAIM, ClaimRecord, item

    claims = [i for its in items.values() for i in its if i.evidence_type == CLAIM]
    if not claims:
        return items, {}
    mapping = group_relations([str(i.fields["relation"]) for i in claims], ctx)

    def regroup(it: Item) -> Item:
        if it.evidence_type != CLAIM:
            return it
        record = ClaimRecord(**{k: v for k, v in it.fields.items()}, span=Span.model_validate(it.spans[0].model_dump()))
        return item(apply_groups([record], mapping)[0])

    return {doc: [regroup(i) for i in its] for doc, its in items.items()}, mapping


def line_params(plan: Plan, query: str) -> dict[str, Any]:
    """The parameters a line runs with: the plan's defaults for the saved templates' structural params (the compared
    sides, the measures and their direction, the threshold), then the decisions' values (W7 `decision_params`, which
    win). A must-match or counts-as value given as text is one list entry."""
    from .planner import decision_params
    things, measures = sides(plan), list(plan.measures)
    base: dict[str, Any] = {"sides": things[:2], "metrics": measures, "higher_is_better": {m: True for m in measures},
                            "min_effect": threshold(plan), "threshold": threshold(plan)}
    given = decision_params(plan, query)
    for name, value in list(given.items()):
        if name in ("must_match", "counts_as", "metrics") and isinstance(value, str):
            given[name] = [v.strip() for v in value.split(",") if v.strip()]
    return {**base, **given}


def _rerun_decisions(plan: Plan, query: str) -> list[Decision]:
    """The decisions this line uses (their parameter is in its query), the main-answer rule and include left out,
    each value parsed (a number, or a list for must-match / counts-as)."""
    from .planner import decision_params
    used = decision_params(plan, query)
    out = []
    for d in plan.decisions:
        if d.type in (MAIN_RULE, "include") or d.id == MAIN_RULE:
            continue
        value = _value(d.value)
        if d.type in LIST_DECISIONS:
            value = value if isinstance(value, list) else [v.strip() for v in str(value).split(",") if v.strip()]
        elif d.type == "threshold" and not isinstance(value, (int, float)):
            continue
        if _param_of(query, d) in used:
            out.append(d.model_copy(update={"value": value}))
    return out


def reruns(plan: Plan, store: Any) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """({line id: label}, every rerun row) of the lines that ran: each decision the line uses changed one at a time
    (W4 sensitivity). A line whose rerun fails gets the label "failed: <reason>"."""
    from .kg import sensitivity
    labels: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for line in plan.lines:
        if not line.query.strip():
            continue
        try:
            plain = line.model_copy(update={"template": None})   # the plan's own query, its decisions as $params
            decisions = _rerun_decisions(plan, line.query)
            names = {d.id: _param_of(line.query, d) for d in decisions}
            result = sensitivity.rerun(store, plain, decisions, params=line_params(plan, line.query), param_of=names)
            labels[line.id] = sensitivity.label(result)
            rows += [{"line": line.id, "decision": r.decision, "field": r.field, "setting": f"{r.decision} {r.setting}",
                      "strictness": r.setting, "value": r.value, "verdict": r.verdict.label, "n": r.verdict.n,
                      "flips": r.flips} for r in result.runs]
        except Exception as exc:   # noqa: BLE001 - one line's rerun failing stays with that line
            labels[line.id] = f"failed: {str(exc)[:200] or type(exc).__name__}"
    return labels, rows


def _param_of(query: str, d: Decision) -> str:
    from .planner.plan import decision_map
    return decision_map(query).get(d.type, d.type)


OUTSIDE = "outside the set"


def links_of(items: dict[str, list[Item]]) -> list[dict[str, Any]]:
    """The run's builds-on links for the answer: a cited work that is no paper of the corpus says "outside the set"."""
    from .records import LINK
    out = []
    for doc in sorted(items):
        for it in items[doc]:
            if it.evidence_type == LINK:
                f = it.fields
                out.append({"paper": f["subject_doc"], "relation": f["relation"], "ref": f["object_ref"],
                            "in_set": f.get("object_doc"),
                            "text": OUTSIDE if f["outside_set"] else f"in the set: {f.get('object_doc')}"})
    return out


def answer(plan: Plan, store: Any, synthesis: dict[str, Any], groups: Mapping[str, str],
           items: dict[str, list[Item]] | None = None) -> dict[str, Any]:
    """answer.json of a plan run: the lines (each in its own try block), the main answer, labels and reruns, the claim
    groups and the builds-on links."""
    from .claims import grouped_line
    from .kg.query import run_query
    from .planner.lines import run_lines

    def run_one(query: str, _params: dict[str, Any]) -> list[dict[str, Any]]:
        return run_query(store, query, line_params(plan, query)).rows   # the decisions' params, lists normalised

    result = run_lines(plan, run_one)
    labels, rows = reruns(plan, store)
    return {"system": "plan", "question": plan.question, "plan_sha256": plan.sha256, **result, "labels": labels,
            "reruns": rows, "claim_groups": {"mapping": dict(groups), "line": grouped_line(groups) if groups else None},
            "links": links_of(items or {}),
            "synthesis": synthesis}


def records(papers: list[Any], items: dict[str, list[Item]], roles: Any, field: str) -> Any:
    """The records graph (W4 build) with the field's ontology (W2 sources.load; None: no tree)."""
    from .kg.build import build
    from .ontology.sources import load
    return build(papers, items, roles, load(field))


def finish(plan: Plan, papers: list[Any], items: dict[str, list[Item]], roles: Any, ctx: Any,
           synthesis: dict[str, Any]) -> tuple[dict[str, list[Item]], bytes, dict[str, Any]]:
    """(the items with claim groups, records.nq bytes, answer.json) of a plan run, after its extraction."""
    from .kg.build import serialize
    items, groups = group_claims(items, ctx)
    store = records(papers, items, roles, plan.field)
    return items, serialize(store), answer(plan, store, synthesis, groups, items)


# --- the command ------------------------------------------------------------------------------------------------------

def run(plan_path: Path | str, corpus: Path | str, out_dir: Path | str, **kw: Any) -> Path:
    """A plan run (`evidence run --plan`): the protocol from the plan, the plan's stages, then `engine.execute_run`.
    `kw` as `engine.run` takes them (cache, model, provider, workers, run_id, retry_errors, strategy, selection)."""
    from . import engine
    plan = load_plan(plan_path)
    if not plan.ready():
        raise ValueError("the plan is not confirmed: confirm every decision before the run")
    return engine.run_plan(plan_path, protocol_for(plan), corpus, out_dir, **kw)
