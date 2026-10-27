"""Step 3, `critic`: deterministic checks of the draft and an LLM checklist (one model call) -> critic.json.

Deterministic (`checks`, also run by freeze on the frozen protocol):

- `parses`: the text validates as a protocol (evidence/protocol.parse, what `evidence protocol check` does);
- `outcomes_complete`: every frame outcome is a question metric of the protocol with the same direction, and
  every question metric has a canonical name and a direction;
- `terms_cover_synonyms`: the regex extractors' patterns (their `conditions`/`metrics` config, else the
  built-ins of evidence/extractors/terms.py) find every name of the treatment and the control under the
  protocol's compare roles and every outcome name under its canonical metric, and every treatment name
  holds a screen term;
- `screen_present`: the protocol has a screen with terms;
- `label_complete`: the label table's last row has no `when` and every earlier row has one;
- `extractors_registered`: every extractor a cascade or the screen names is registered (evidence/extractors);
- `regex_matches_enums` (ours, beyond Part E): every condition role and metric canonical the regex steps
  can emit (their config, else the built-ins) is in the type's enum, and every enum value but `other` has a
  pattern; freeze refuses a protocol that fails it;
- `bounds_cover_rate_metrics` (ours): every rate-like outcome (draft.rate_like) is in the measurement bound, so
  a value outside [0, 1] is rejected;
- `metric_rules_collide` (ours): no frame name is matched at the same place by rules of two canonicals;
- `locate_params_used` (ours): an exhaustive locate names no params (it would ignore them).

Each check has a `severity`. `serious` (older critic.json files say `blocking`; freeze refuses the protocol unless a person waives the check in
decisions.yaml): `regex_matches_enums`, `bounds_cover_rate_metrics`, `metric_rules_collide`, the kind checks
(`inventory_target_declared`, `best_kinds_nonempty`, `best_kinds_disjoint`, `claim_type_present`, each "not
applicable" for the other kinds), and `terms_cover_synonyms` when the screen drops a paper outright on a keyword miss (`on_fail: skip` with
`lexical_miss: reject`, so an uncovered synonym loses papers); every other check is `advisory`.

LLM checklist (`ambiguous_roles`, `missing_comparator`, `metric_direction`, `scope`): pass or fail, each
with a message. `ok` in critic.json is true when every blocking check passes; advisory checks and the
checklist are advice.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_ai.models import Model

from .. import extractors
from ..extractors import terms as regex_terms
from ..extractors.screen import term_pattern
from ..protocol import Protocol, parse
from . import frame as frame_module
from .draft import rate_like
from .common import CRITIC, DRAFT, FRAME, ask, fresh, model_for, need, now, prompt, read_json, sha, write_json
from .frame import Frame

PROMPT = "critic-v1.md"
DETERMINISTIC = ("parses", "outcomes_complete", "terms_cover_synonyms", "regex_matches_enums", "screen_present",
                 "label_complete", "extractors_registered", "bounds_cover_rate_metrics",
                 "metric_rules_collide", "locate_params_used", "inventory_target_declared", "best_kinds_nonempty",
                 "best_kinds_disjoint", "claim_type_present")
SERIOUS = ("regex_matches_enums", "bounds_cover_rate_metrics", "metric_rules_collide", "inventory_target_declared",
           "best_kinds_nonempty", "best_kinds_disjoint", "claim_type_present")   # and see `severity`
LLM_CHECKS = ("ambiguous_roles", "missing_comparator", "metric_direction", "scope")


class Check(BaseModel):
    ok: bool
    message: str = Field(description="what is wrong, or why it is fine, in one or two sentences")


class CriticReply(BaseModel):
    ambiguous_roles: Check = Field(description="could a condition be read as both treatment and control, or as neither?")
    missing_comparator: Check = Field(description="does the protocol lack a real control to compare the treatment with?")
    metric_direction: Check = Field(description="is any question metric's higher_is_better wrong?")
    scope: Check = Field(description="do the screening question and terms admit the papers the question needs, and only those?")


def _check(cid: str, ok: bool, message: str) -> dict[str, Any]:
    return {"id": cid, "kind": "deterministic", "ok": ok, "message": message}


def severity(cid: str, p: Protocol | None) -> str:
    """`serious` or `advisory` (module docstring); terms_cover_synonyms is serious only under a screen that
    drops a paper on a keyword miss."""
    if cid in SERIOUS:
        return "serious"
    if cid == "terms_cover_synonyms" and p is not None and p.screen is not None:
        return "serious" if (p.screen.on_fail, p.screen.lexical_miss) == ("skip", "reject") else "advisory"
    return "advisory"


def serious_failures(found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The failed serious checks; a critic.json from before the rename says `blocking` for `serious`."""
    return [c for c in found if c.get("severity") in ("serious", "blocking") and not c["ok"]]


blocking_failures = serious_failures


def _patterns(p: Protocol, name: str, key: str, default: Any) -> Any | None:
    """The effective regex patterns `key` of the regex step `name` of any cascade; None without such a step."""
    for spec in p.evidence_types.values():
        for step in spec.extractors:
            if step.name == name:
                return step.config.get(key, default)
    return None


def _extractable(p: Protocol, f: Frame) -> list[Any]:
    """The frame outcomes the protocol's metric extractors may still emit (the metric enum, else the question
    metrics): a person may drop one at freeze; outcomes_complete reports that, the metric checks leave it out."""
    spec = p.evidence_types.get("metric")
    names = (spec.enum_of("canonical") if spec else None) or (p.synthesis.metric_names if p.synthesis else [])
    return [o for o in f.outcomes if o.canonical in names]


def _coverage(p: Protocol, f: Frame) -> tuple[bool, str]:
    misses: list[str] = []
    roles = ({f.treatment.role: p.synthesis.compare.treatment, f.control.role: p.synthesis.compare.control}
             if p.synthesis else {})   # an inventory or best protocol compares no two roles
    conditions = _patterns(p, "regex_condition", "conditions", regex_terms.CONDITIONS)
    if conditions is not None and roles:
        compiled = regex_terms.condition_patterns(conditions)
        for r in (f.treatment, f.control):
            for name in r.names:
                if not any(m.key == roles[r.role] for m in regex_terms.find_all(name, compiled)):
                    misses.append(f"{r.role} name {name!r} (regex_condition)")
    metrics = _patterns(p, "regex_metric", "metrics", [list(m) for m in regex_terms.METRICS])
    if metrics is not None:
        compiled = [tuple(m) for m in metrics]
        for o in _extractable(p, f):
            for name in o.names:
                if not any(m.key == o.canonical for m in regex_terms.find_all(name, compiled)):  # type: ignore[arg-type]
                    misses.append(f"{o.canonical} name {name!r} (regex_metric)")
    if p.screen is not None and any(s.name == "regex_screen" for s in p.screen.extractors):
        screen = [regex_terms._compiled(term_pattern(t)) for t in p.screen.terms]
        for name in f.treatment.names:
            if not any(c.search(name) for c in screen):
                misses.append(f"treatment name {name!r} (no screen term in it)")
    if misses:
        return False, "not found by the regex patterns: " + "; ".join(misses)
    return True, "every frame name is found by the regex patterns and every treatment name holds a screen term"


def _regex_enums(p: Protocol) -> tuple[bool, str]:
    """Every role and canonical a regex step can emit is in its type's enum, and every enum value but
    `other` has at least one pattern (else the regex step can never find it)."""
    problems: list[str] = []
    for type_name, field, key, default, steps in (
            ("condition", "role", "conditions", regex_terms.CONDITIONS, ("regex_condition", "regex_measurement")),
            ("metric", "canonical", "metrics", [list(m) for m in regex_terms.METRICS], ("regex_metric", "regex_measurement"))):
        enum = p.evidence_types[type_name].enum_of(field) if type_name in p.evidence_types else None
        if enum is None:
            continue
        for spec in p.evidence_types.values():
            for step in spec.extractors:
                if step.name not in steps:
                    continue
                patterns = step.config.get(key, default)
                emitted = set(patterns) if key == "conditions" else {m[1] for m in patterns}
                with_pattern = ({k for k, v in patterns.items() if v} if key == "conditions" else emitted)
                extra = sorted(emitted - set(enum))
                missing = [v for v in enum if v != "other" and v not in with_pattern]
                if extra:
                    problems.append(f"{step.name} can emit {type_name}.{field} {extra}, not in the enum {list(enum)}")
                if missing:
                    problems.append(f"{step.name} has no pattern for {type_name}.{field} {missing}")
    if problems:
        return False, "; ".join(dict.fromkeys(problems))
    return True, "the regex steps emit only enum values and have a pattern for each"


def bounds_cover_rate_metrics(p: Protocol, f: Frame) -> tuple[bool, str]:
    """Every rate-like outcome is named by a bound on the measurement value (or the bound has no `when`)."""
    spec = p.evidence_types.get("measurement")
    if spec is None:
        return True, "not applicable: the protocol extracts no measurements"
    bounds = [b for b in (spec.bounds if spec else ()) if b.field == "value"]
    covered = {v for b in bounds if b.when for v in b.when.values}
    missing = [o.canonical for o in _extractable(p, f) if rate_like(o) and o.canonical not in covered
               and not any(b.when is None for b in bounds)]
    if missing:
        return False, f"rate-like outcomes missing from the measurement bound: {missing}"
    return True, "every rate-like outcome is bounded in the measurement"


def metric_collisions(p: Protocol, f: Frame) -> list[str]:
    """`"<surface>: <a> vs <b>"` for every frame name that two metric rules of different canonicals match at the
    same place (the first rule would decide the metric)."""
    patterns = _patterns(p, "regex_metric", "metrics", [list(m) for m in regex_terms.METRICS])
    if patterns is None:
        return []
    out: list[str] = []
    for surface in dict.fromkeys(n for o in f.outcomes for n in o.names):
        canonicals = {key for pattern, key, _ in patterns for m in regex_terms._compiled(pattern).finditer(surface)
                      if m.end() > m.start() and any(
                          m.span() == q.span() for p2, k2, _ in patterns if k2 != key
                          for q in regex_terms._compiled(p2).finditer(surface))}
        if len(canonicals) > 1:
            out.append(f"{surface}: " + " vs ".join(sorted(canonicals)))
    return out


def _kind_checks(raw: Any) -> list[dict[str, Any]]:
    """The four checks of the kind blocks, read from the raw mapping (they hold when the protocol does not parse
    too); each is `not applicable` for the other kinds."""
    raw = raw if isinstance(raw, dict) else {}
    kind = raw.get("kind", "effect")
    types = raw.get("evidence_types") or {}

    def na(cid: str, want: str) -> dict[str, Any]:
        return _check(cid, True, f"not applicable: a {kind} protocol (this is for {want})")

    out: list[dict[str, Any]] = []
    target = (raw.get("inventory") or {}).get("target")
    if kind == "inventory":
        out.append(_check("inventory_target_declared", target in types,
                          f"the inventory lists {target!r}, an evidence type of the protocol" if target in types else
                          f"inventory.target {target!r} is not a declared evidence type {sorted(types)}"))
    else:
        out.append(na("inventory_target_declared", "inventory"))
    kinds = (raw.get("best") or {}).get("kinds")
    kinds = kinds if isinstance(kinds, dict) else {}
    if kind == "best":
        empty = sorted(str(k) for k, names in kinds.items() if not names)
        out.append(_check("best_kinds_nonempty", bool(kinds) and not empty,
                          f"method kinds without a name: {empty}" if empty else "no method kinds" if not kinds
                          else "every method kind has at least one name"))
        seen: dict[str, list[str]] = {}
        for k, names in kinds.items():
            for n in names or ():
                seen.setdefault(str(n).casefold(), []).append(str(k))
        both = {n: ks for n, ks in seen.items() if len(set(ks)) > 1}
        out.append(_check("best_kinds_disjoint", not both,
                          "names in two kinds: " + "; ".join(f"{n!r} in {sorted(set(ks))}" for n, ks in both.items())
                          if both else "no name is in two method kinds"))
    else:
        out += [na("best_kinds_nonempty", "best"), na("best_kinds_disjoint", "best")]
    if kind == "consistency":
        out.append(_check("claim_type_present", "author_claim" in types, "the protocol extracts author claims"
                          if "author_claim" in types else "a consistency protocol needs an author_claim evidence type"))
    else:
        out.append(na("claim_type_present", "consistency"))
    return out


def checks(text: str, f: Frame | None) -> list[dict[str, Any]]:
    """The deterministic checks of a protocol text (and the frame it was made from, when there is one)."""
    out: list[dict[str, Any]] = []
    try:
        p = parse(text)
        out.append(_check("parses", True, f"validates: id {p.id}, sha256 {p.sha256}"))
    except (ValueError, yaml.YAMLError) as exc:
        out.append(_check("parses", False, str(exc).strip()))
        p = None
    raw = _safe(text)
    skipped = "not checked: the protocol does not parse"

    if p is None or f is None:
        out.append(_check("outcomes_complete", False, skipped if p is None else "not checked: no frame"))
    elif p.synthesis is None:
        out.append(_check("outcomes_complete", True, f"not applicable: a {p.kind} protocol has no question metrics list"))
    else:
        directions = {m.canonical: m.higher_is_better for m in p.synthesis.metrics}
        bad = [o.canonical for o in f.outcomes if directions.get(o.canonical) != o.higher_is_better]
        out.append(_check("outcomes_complete", not bad,
                          f"outcomes without a matching question metric and direction: {bad}" if bad else
                          "every outcome is a question metric with its direction"))

    if p is None or f is None:
        out.append(_check("terms_cover_synonyms", False, skipped if p is None else "not checked: no frame"))
    else:
        out.append(_check("terms_cover_synonyms", *_coverage(p, f)))

    out.append(_check("regex_matches_enums", *(_regex_enums(p) if p is not None else (False, skipped))))

    screen = (raw or {}).get("screen") if isinstance(raw, dict) else None
    out.append(_check("screen_present", bool(screen and screen.get("terms")),
                      "the protocol screens on its terms" if screen and screen.get("terms") else
                      "no screen with terms: every paper would be extracted"))

    rows = (((raw or {}).get("synthesis") or {}).get("label") or []) if isinstance(raw, dict) else []
    complete = (p is not None and p.synthesis is None) or bool(rows) and not (rows[-1] or {}).get("when") and all((r or {}).get("when") for r in rows[:-1])
    out.append(_check("label_complete", complete, "the last label row is the default and only it (or the kind has no label table)" if complete else
                      "the label table needs exactly one row without `when`, the last"))

    named = []
    if isinstance(raw, dict):
        for spec in (raw.get("evidence_types") or {}).values():
            named += [s.get("name") for s in (spec or {}).get("extractors") or []]
        named += [s.get("name") for s in (screen or {}).get("extractors") or []]
    unknown = sorted({n for n in named if n not in extractors.names()}, key=str)
    out.append(_check("extractors_registered", bool(named) and not unknown,
                      f"not registered: {unknown}" if unknown else
                      "every extractor is registered" if named else "no extractors named"))

    if f is not None:
        out.append(_check("bounds_cover_rate_metrics", *(bounds_cover_rate_metrics(p, f) if p is not None else (False, skipped))))
        collisions = metric_collisions(p, f) if p is not None else None
        out.append(_check("metric_rules_collide", collisions == [],
                          skipped if collisions is None else
                          f"surfaces claimed by two metrics: {collisions}" if collisions else
                          "no frame name is claimed by two metrics"))

    loc = (raw.get("locate") if isinstance(raw, dict) else None) or {}
    ignored = sorted(loc.get("params") or {}) if loc.get("strategy", "exhaustive") == "exhaustive" else []
    out.append(_check("locate_params_used", not ignored,
                      f"the exhaustive locate ignores its params {ignored}" if ignored else
                      "the locate params belong to its strategy"))
    out += _kind_checks(raw)
    return [{**c, "severity": severity(c["id"], p)} for c in out]


def _safe(text: str) -> Any:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def run(directory: Path | str, *, model: Model | None = None, alias: str | None = None, refresh: bool = False) -> Path:
    """Write DIR/critic.json for DIR/draft.yaml (deterministic checks and one cached model call)."""
    directory = Path(directory)
    frame_path = need(directory, FRAME, "frame")
    f = frame_module.load(frame_path)
    draft_path = need(directory, DRAFT, "draft")
    sources = read_json(need(directory, "draft.sources.json", "draft"))
    fresh(directory, FRAME, sources.get("frame_sha256"), "draft")
    text = draft_path.read_text(encoding="utf-8")
    found = checks(text, f)
    user = (f"Question: {f.question}\n\nFrame (treatment, control, outcomes):\n"
            f"{f.model_dump_json(include={'population', 'treatment', 'control', 'outcomes', 'effect_labels'})}\n\n"
            f"Draft protocol:\n{text.strip()}\n")
    reply, call = ask(directory, "critic", prompt(PROMPT), user, CriticReply, model=model_for(alias, model),
                       refresh=refresh)
    llm = [{"id": c, "kind": "llm", "ok": getattr(reply, c).ok, "message": getattr(reply, c).message} for c in LLM_CHECKS]
    return write_json(directory / CRITIC, {"draft_sha256": sha(draft_path), "frame_sha256": sha(frame_path),
                                           "ok": not serious_failures(found), "checks": found + llm,
                                           "call": call, "created": now()})
