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
- `vocabulary_direction` (ours, beyond Part E): no outcome's direction contradicts its vocabulary term's.

LLM checklist (`ambiguous_roles`, `missing_comparator`, `metric_direction`, `scope`): pass or fail, each
with a message. `ok` in critic.json is true when every deterministic check passes; the checklist is advice.
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
from .common import CRITIC, DRAFT, FRAME, ask, fresh, model_for, need, now, prompt, read_json, sha, write_json
from .frame import Frame

PROMPT = "critic-v1.md"
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


def _patterns(p: Protocol, name: str, key: str, default: Any) -> Any | None:
    """The effective regex patterns `key` of the regex step `name` of any cascade; None without such a step."""
    for spec in p.evidence_types.values():
        for step in spec.extractors:
            if step.name == name:
                return step.config.get(key, default)
    return None


def _coverage(p: Protocol, f: Frame) -> tuple[bool, str]:
    misses: list[str] = []
    roles = {f.treatment.role: p.synthesis.compare.treatment, f.control.role: p.synthesis.compare.control}
    conditions = _patterns(p, "regex_condition", "conditions", regex_terms.CONDITIONS)
    if conditions is not None:
        compiled = regex_terms.condition_patterns(conditions)
        for r in (f.treatment, f.control):
            for name in r.names:
                if not any(m.key == roles[r.role] for m in regex_terms.find_all(name, compiled)):
                    misses.append(f"{r.role} name {name!r} (regex_condition)")
    metrics = _patterns(p, "regex_metric", "metrics", [list(m) for m in regex_terms.METRICS])
    if metrics is not None:
        compiled = [tuple(m) for m in metrics]
        for o in f.outcomes:
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

    screen = (raw or {}).get("screen") if isinstance(raw, dict) else None
    out.append(_check("screen_present", bool(screen and screen.get("terms")),
                      "the protocol screens on its terms" if screen and screen.get("terms") else
                      "no screen with terms: every paper would be extracted"))

    rows = (((raw or {}).get("synthesis") or {}).get("label") or []) if isinstance(raw, dict) else []
    complete = bool(rows) and not (rows[-1] or {}).get("when") and all((r or {}).get("when") for r in rows[:-1])
    out.append(_check("label_complete", complete, "the last label row is the default and only it" if complete else
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
        bad = [o.canonical for o in f.outcomes
               if o.vocab_higher_is_better is not None and o.vocab_higher_is_better != o.higher_is_better]
        out.append(_check("vocabulary_direction", not bad,
                          f"direction differs from the vocabulary for {bad}" if bad else
                          "no outcome's direction contradicts the vocabulary"))
    return out


def _safe(text: str) -> Any:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def run(directory: Path | str, *, model: Model | None = None, alias: str | None = None) -> Path:
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
    reply, call = ask(directory, "critic", prompt(PROMPT), user, CriticReply, model=model_for(alias, model))
    llm = [{"id": c, "kind": "llm", "ok": getattr(reply, c).ok, "message": getattr(reply, c).message} for c in LLM_CHECKS]
    return write_json(directory / CRITIC, {"draft_sha256": sha(draft_path), "frame_sha256": sha(frame_path),
                                           "ok": all(c["ok"] for c in found), "checks": found + llm,
                                           "call": call, "created": now()})
