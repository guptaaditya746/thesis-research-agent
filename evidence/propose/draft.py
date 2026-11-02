"""Step 2, `draft` (deterministic): frame.json and the example protocol -> draft.yaml, draft.sources.json.

The example protocol (the kind's template, common.KIND_TEMPLATES, unless `--template` names another) gives
everything the frame does not decide: the four evidence types' field schemas, span roles, links, context
and cascades, the locate step, the screen's extractors, `min_effect`, the pairing rule, the label table and
the flag thresholds. The frame decides the rest:

- `screen`: the population's screening question and terms;
- `condition.role` enum `[treatment, control, other]` and `synthesis.compare`;
- `metric.canonical` enum `[outcomes..., other]` and `synthesis.metrics` (frame order is priority order);
- the measurement bound [0, 1] on the outcomes that are rate-like (`rate_like`: a fraction or percent scale, or a
  rate's name when the scale is unstated);
- `author_claim.direction` enum and `synthesis.claim_map` from the effect labels;
- the descriptions (built from the definitions) and the bm25 `query` terms: the frame's names plus a fixed
  list of type words per evidence type (`TYPE_WORDS`, taken from the example protocol's queries);
- the regex extractors' patterns, only where the built-in ones (evidence/extractors/terms.py) do not find a
  frame name under its role or canonical: then the regex steps get a `conditions` / `metrics` / `subject`
  config with the missing names added as word-bounded patterns (a role or metric the built-ins do not know
  at all gets patterns from its names only). A frame whose names the built-ins find leaves the regex steps
  without config, so the default pack's frame drafts its hand-written cascades exactly. `sync_regex` does this from a
  protocol mapping's roles and metrics; freeze runs it again after the decisions.

draft.sources.json says where every decided value and every term comes from: `frame` (the frame's, so the
model's or the person's who edited frame.json) or `protocol` (copied from the example protocol), and the sha256
of the frame and template it was drafted from.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from ..extractors import terms as regex_terms
from ..extractors.screen import term_pattern
from ..pack import Pack, load_pack
from ..protocol import DEFAULT_PACK, parse
from . import frame as frame_module
from .common import (DRAFT, FRAME, KIND_TEMPLATES, SOURCES, ProposalError, dump_yaml, need, read_yaml, sha,
                     slug_id, write_json, write_text)
from .frame import Frame, FrameTerm

# Type words of the bm25 query (the example protocol's query terms that name no topic); the frame's names
# are added to them.
TYPE_WORDS: dict[str, list[str]] = {
    "condition": ["baseline", "variant", "system", "condition", "compare"],
    "metric": ["metric", "measure", "evaluate", "score"],
    "measurement": ["table", "results", "achieves", "reaches", "compared", "%"],
    "author_claim": ["conclusion", "show", "find", "hurts", "effect"],
}
RATE_LIKE = re.compile(r"(?i)\b(accuracy|rate|precision|recall|f1|fraction|share|proportion|exact.?match)\b")
REGEX = {"conditions": ("regex_condition", "regex_measurement"), "metrics": ("regex_metric", "regex_measurement"),
         "subject": ("regex_author_claim",)}


def rate_like(o: frame_module.Outcome) -> bool:
    """Whether the engine normalises this outcome's values to [0, 1]: by its scale, else by its names (the
    model's yes/no on a fraction is not trusted: it said no for an accuracy)."""
    if o.scale in ("fraction", "percent"):
        return True
    return o.scale == "other" and any(RATE_LIKE.search(n) for n in [o.canonical, *o.names])


def _clause(text: str) -> str:
    return text.strip().rstrip(".")


def _dedup(names: list[str]) -> list[str]:
    out: list[str] = []
    for n in names:
        if n and n.casefold() not in (o.casefold() for o in out):
            out.append(n)
    return out


Names = list[tuple[str, FrameTerm | str]]   # (name, the frame entry it came from, or the name itself)


def _names(entry: Any) -> Names:
    return [(entry.label, entry.label), *((s.term, s) for s in entry.synonyms)]


def condition_patterns(roles: list[tuple[str, Names]],
                       pack: Pack) -> tuple[dict[str, list[str]] | None, list[tuple[str, Any]]]:
    """(the regex `conditions` config, or None when the built-ins (the domain pack's patterns) find every name
    under its role and know exactly these roles; the names added). `roles`: (role id, its names) for the
    treatment and the control; the control's added patterns refuse a negated object ("no tuning failures")."""
    builtin: dict[str, list[str]] = pack.extractor_config("condition", "regex_condition")["conditions"]
    known = all(r in builtin for r, _ in roles) and len(roles) == len(builtin)
    base = {r: list(builtin.get(r, [])) for r, _ in roles}
    added: list[tuple[str, Any]] = []
    for i, (role, names) in enumerate(roles):
        for name, term in names:
            found = regex_terms.find_all(name, regex_terms.condition_patterns(base))
            if not any(m.key == role for m in found):
                pattern = term_pattern(name)
                base[role].append(regex_terms.control_cue(pattern, pack.words.not_a_system) if i == 1 else pattern)
                added.append((f"conditions.{role}", term))
    return (base if added or not known else None), added


def _same_span(a: str, b: str, surface: str) -> bool:
    """Whether the patterns `a` and `b` match the same stretch of `surface` (then rule order would decide)."""
    spans = {m.span() for m in regex_terms._compiled(a).finditer(surface) if m.end() > m.start()}
    return any(m.span() in spans for m in regex_terms._compiled(b).finditer(surface))


def metric_patterns(outcomes: list[tuple[str, bool, Names]],
                    pack: Pack) -> tuple[list[list[Any]] | None, list[tuple[str, Any]]]:
    """(the regex `metrics` config, or None when the built-ins (the domain pack's patterns) find every name and
    emit only these metrics;
    the names added). `outcomes`: (canonical, higher_is_better, names). Built-in patterns of a canonical not
    named here are dropped (their items would fail the enum), and so are those that match the same stretch of
    a name as the pattern of a name of another canonical: the first rule would decide the metric."""
    names = {c for c, _, _ in outcomes}
    frame_rows = [(term_pattern(name), canonical) for canonical, _, entries in outcomes for name, _ in entries]
    surfaces = [name for _, _, entries in outcomes for name, _ in entries]

    def collides(pattern: str, canonical: str) -> bool:
        return any(c != canonical and _same_span(pattern, fp, s) for s in surfaces for fp, c in frame_rows)

    builtin = pack.extractor_config("metric", "regex_metric")["metrics"]
    base = [list(m) for m in builtin if m[1] in names | {"other"} and not collides(m[0], m[1])]
    known = len(base) == len(builtin)
    added: list[tuple[str, Any]] = []
    for canonical, hib, entries in outcomes:
        for name, term in entries:
            if not any(m.key == canonical for m in regex_terms.find_all(name, [tuple(m) for m in base])):  # type: ignore[misc]
                base.insert(0, [term_pattern(name), canonical, hib])
                added.append((f"metrics.{canonical}", term))
    return (base if added or not known else None), added


def claim_subject(role: str, names: Names, pack: Pack) -> tuple[str | None, list[tuple[str, Any]]]:
    """(the regex author claim `subject`, or None when the built-in one (the domain pack's) finds every
    treatment name)."""
    builtin = re.compile(pack.words.claim_subject)
    missing = [(n, t) for n, t in names if not builtin.search(n)]
    if not missing:
        return None, []
    bodies = [re.escape(" ".join(n.split())).replace(r"\ ", r"\s+") for n, _ in missing]
    new = r"(?<!\w)(?:" + "|".join(bodies) + r")(?!\w)"
    keep = role in pack.words.conditions   # the built-in subject is about the built-in treatment
    subject = pack.words.claim_subject + "|" + new if keep else "(?i)" + new
    return subject, [("subject", t) for _, t in missing]


def decided_names(p: dict[str, Any], f: Frame) -> tuple[list[tuple[str, Names]], list[tuple[str, bool, Names]]]:
    """The roles and metrics a protocol mapping decides, with the frame's names behind them: the treatment
    role takes the frame's treatment names and the control role the control's, whatever their ids; a metric
    the frame does not have is named by its id with spaces ("f1", "answer accuracy")."""
    compare = p["synthesis"]["compare"]
    roles = [(compare["treatment"], _names(f.treatment)), (compare["control"], _names(f.control))]
    by = {o.canonical: o for o in f.outcomes}
    outcomes = [(m["canonical"], m["higher_is_better"],
                 _names(by[m["canonical"]]) if m["canonical"] in by else
                 [(m["canonical"].replace("_", " "), m["canonical"].replace("_", " "))])
                for m in p["synthesis"]["metrics"]]
    return roles, outcomes


def sync_regex(p: dict[str, Any], f: Frame) -> list[tuple[str, Any]]:
    """Set (or remove) the regex steps' `conditions`, `metrics` and `subject` config from the roles and metrics
    the protocol mapping decides (draft, and freeze after the decisions); returns the names added."""
    roles, outcomes = decided_names(p, f)
    pack = load_pack(p.get("domain", DEFAULT_PACK))   # a protocol without `domain` is the default pack
    out: list[tuple[str, Any]] = []
    for key, (config, added) in (("conditions", condition_patterns(roles, pack)),
                                 ("metrics", metric_patterns(outcomes, pack)),
                                 ("subject", claim_subject(*roles[0], pack))):
        for spec in p["evidence_types"].values():
            for step in spec.get("extractors", []):
                if step["name"] not in REGEX[key]:
                    continue
                if config is None:
                    (step.get("config") or {}).pop(key, None)
                    if "config" in step and not step["config"]:
                        del step["config"]
                else:
                    step.setdefault("config", {})[key] = copy.deepcopy(config)
        out += added
    return out


def build(f: Frame, template: dict[str, Any], proposal_id: str,
          kind: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """(the draft protocol as a mapping, its sources {fields, terms}) for a question of `kind` (the frame's),
    made from that kind's template (common.KIND_TEMPLATES). Only the fields the kind's cards set come from the
    frame: an effect or consistency draft takes roles, metrics, claims and the screen; an inventory or best
    draft takes the screen and keeps the template's evidence types and kind block."""
    kind = kind or f.kind
    t, c = f.treatment, f.control
    fields: list[dict[str, Any]] = []
    terms: list[dict[str, Any]] = []

    def field(path: str, source: str) -> None:
        fields.append({"path": path, "source": source})

    def term(path: str, text: str, source: str) -> None:
        terms.append({"path": path, "term": text, "source": source})

    types = copy.deepcopy(template["evidence_types"])
    screen_t = template.get("screen") or {}
    p: dict[str, Any] = {"id": proposal_id, "version": template["version"], "question": f.question,
                         "locate": copy.deepcopy(template.get("locate", {"strategy": "exhaustive"}))}
    field("locate", "protocol")
    p["screen"] = {"question": f.population.screening_question, "terms": [x.term for x in f.population.terms],
                   "extractors": copy.deepcopy(screen_t.get("extractors") or [{"name": "regex_screen"}, {"name": "llm_screen"}]),
                   "on_fail": screen_t.get("on_fail", "skip"), "lexical_miss": screen_t.get("lexical_miss", "reject")}
    field("screen.question", "frame")
    for x in f.population.terms:
        term("screen.terms", x.term, "frame")
    field("screen.extractors", "protocol")
    field("screen.on_fail", "protocol")
    field("screen.lexical_miss", "protocol")   # named so the reader sees it; at its default it leaves the sha256 alone

    if kind in ("inventory", "best"):
        p["kind"] = kind
        p["evidence_types"] = types
        p[kind] = copy.deepcopy(template[kind])
        field("evidence_types", "protocol")
        field(kind, "protocol")
        return p, {"fields": fields, "terms": terms}

    roles = [t.role, c.role, "other"]
    cond = types["condition"]
    cond["description"] = (f"An experimental condition the paper compares: a system variant whose results are reported. "
                           f"role is {t.role} for {_clause(t.definition)}, {c.role} for {_clause(c.definition)}, "
                           f"other for anything else.")
    cond["fields"]["properties"]["role"]["enum"] = roles
    cond["fields"]["properties"]["role"]["description"] = f"{t.role}, {c.role} or other"
    field("evidence_types.condition.description", "frame")
    field("evidence_types.condition.fields.role.enum", "frame")

    outcomes = [o.canonical for o in f.outcomes]
    met = types["metric"]
    met["description"] = ("An evaluation metric the paper reports results on. canonical is "
                          + ", ".join(f"{o.canonical} for {o.label}" for o in f.outcomes)
                          + ", other for anything else.")
    met["fields"]["properties"]["canonical"]["enum"] = [*outcomes, "other"]
    field("evidence_types.metric.description", "frame")
    field("evidence_types.metric.fields.canonical.enum", "frame")

    fractions = [o.canonical for o in f.outcomes if rate_like(o)]
    meas = types["measurement"]
    meas["bounds"] = ([{"field": "value", "min": 0, "max": 1,
                        "when": {"link": "metric", "field": "canonical", "values": fractions}}] if fractions else [])
    field("evidence_types.measurement.bounds", "protocol" if fractions else "frame")

    claim = types["author_claim"]
    values = [e.value for e in f.effect_labels]
    claim["description"] = (f"The authors' own conclusion about whether {t.label} improves {f.outcomes[0].label} "
                            f"over {c.label}: {', '.join(values[:-1])} or {values[-1]}." if len(values) > 1 else
                            f"The authors' own conclusion about whether {t.label} improves {f.outcomes[0].label}: {values[0]}.")
    claim["fields"]["properties"]["direction"]["enum"] = values
    field("evidence_types.author_claim.description", "frame")
    field("evidence_types.author_claim.fields.direction.enum", "frame")

    query_names = {"condition": [*t.names, *c.names], "metric": [n for o in f.outcomes for n in o.names],
                   "measurement": [n for o in f.outcomes for n in o.names],
                   "author_claim": [*t.names, *(o.label for o in f.outcomes), *(v.replace("_", " ") for v in values)]}
    for name, spec in types.items():
        if name in TYPE_WORDS:
            spec["query"] = _dedup([*query_names[name], *TYPE_WORDS[name]])
            field(f"evidence_types.{name}.query", "frame")
        field(f"evidence_types.{name}.extractors", "protocol")
        field(f"evidence_types.{name}.fields", "protocol")

    p["evidence_types"] = types
    syn_t = template["synthesis"]
    p["synthesis"] = {
        "compare": {"treatment": t.role, "control": c.role},
        "metrics": [{"canonical": o.canonical, "higher_is_better": o.higher_is_better} for o in f.outcomes],
        "min_effect": syn_t["min_effect"],
        "pairing": copy.deepcopy(syn_t.get("pairing", {"rule": "same_dataset", "prefer": ["table_cell", "document_order"]})),
        "claim_map": {e.value: e.direction for e in f.effect_labels},
        "label": copy.deepcopy(syn_t["label"]),
        "flags": copy.deepcopy(syn_t.get("flags", {})),
    }
    for path, x in sync_regex(p, f):
        term(f"regex.{path}", x.term if isinstance(x, FrameTerm) else x, "frame")
    if kind == "consistency":
        p["kind"] = kind
        p["consistency"] = copy.deepcopy(template["consistency"])
        field("consistency", "protocol")
    field("synthesis.compare.treatment", "frame")
    field("synthesis.compare.control", "frame")
    for n, _ in enumerate(f.outcomes):
        field(f"synthesis.metrics[{n}].canonical", "frame")
        field(f"synthesis.metrics[{n}].higher_is_better", "frame")
    for e in f.effect_labels:
        field(f"synthesis.claim_map.{e.value}", "frame")
    for key in ("min_effect", "pairing", "label", "flags"):
        field(f"synthesis.{key}", "protocol")
    return p, {"fields": fields, "terms": terms}


HEADER = """# Draft protocol written by `evidence propose draft` from frame.json and the example protocol {template}.
# Not frozen: `evidence propose critic`, `cards`, then `freeze` (which applies decisions.yaml) make protocol.yaml.
"""


def run(directory: Path | str, *, template: Path | str | None = None) -> Path:
    """Write DIR/draft.yaml and DIR/draft.sources.json; the draft validates or nothing is written."""
    directory = Path(directory)
    frame_path = need(directory, FRAME, "frame")
    f = frame_module.load(frame_path)
    template_path = Path(template) if template else KIND_TEMPLATES[f.kind]
    template_data = read_yaml(template_path)
    proposal_id = slug_id(directory.resolve().name)
    protocol, sources = build(f, template_data, proposal_id, f.kind)
    text = HEADER.format(template=template_path.name) + dump_yaml(protocol)
    try:
        parse(text)
    except ValueError as exc:
        raise ProposalError(f"the draft does not validate (edit frame.json): {exc}") from exc
    write_text(directory / DRAFT, text)
    write_json(directory / SOURCES, {"frame_sha256": sha(frame_path),
                                     "template": {"path": template_path.name, "sha256": sha(template_path)},
                                     **sources})
    return directory / DRAFT
