"""Step 4, `cards` (one model call): the fixed choice points (cards.yaml) as cards.json, and decisions.yaml
prefilled with the model's defaults for the person to edit.

Each card has options: `draft` (the draft's own value), the fixed options of cards.yaml (the cascade card's
are made from the draft: the same cascades escalating only the gaps, and with the agentic extractor last),
and `model` when the model proposes a value of its own. The model picks a default and gives a rationale. The
vocabulary evidence of a card is the snapshot's entries behind the values it sets (the frame's matches).

decisions.yaml holds one entry per card: `choice` (an option id, or `custom` with a `value` in the card's
shape), `reason`, `by`. Prefilled entries are the model's default with `reason: "default: <rationale>"` and
`by: model`; freeze accepts them as they stand and records `by`, so a model default and a person's decision
stay apart in proposal.json. `validate` is freeze's check of the file: every card exactly once, a known
choice, a non-empty reason and `by`, a `value` only with `custom`, and a choice other than the model's
default made by someone other than `model`.
"""
from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model, model_validator
from pydantic_ai.models import Model

from .. import rules
from ..protocol import LocateStrategy
from . import frame as frame_module
from .common import (CARDS, CRITIC, DECISIONS, DRAFT, FRAME, ProposalError, ask, dump_yaml, fresh, model_for, need,
                     now, prompt, read_json, read_yaml, sha, write_json, write_text)
from .frame import ID, Frame

PROMPT = "cards-v1.md"
CARDS_FILE = Path(__file__).resolve().parent / "cards.yaml"
CUSTOM, MODEL = "custom", "model"


class Value(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScreenValue(Value):
    question: str = Field(min_length=1)
    terms: list[str] = Field(min_length=1)


class RoleDef(Value):
    role: str = Field(pattern=ID)
    definition: str


class RolesValue(Value):
    treatment: RoleDef
    control: RoleDef

    @model_validator(mode="after")
    def _distinct(self) -> RolesValue:
        if self.treatment.role == self.control.role or "other" in (self.treatment.role, self.control.role):
            raise ValueError("treatment and control need two different roles, neither of them `other`")
        return self


class MetricValue(Value):
    canonical: str = Field(pattern=ID)
    higher_is_better: bool


class MetricsValue(Value):
    metrics: list[MetricValue] = Field(min_length=1)


class MinEffectValue(Value):
    min_effect: float = Field(gt=0)


class PairingValue(Value):
    prefer: list[Literal["table_cell", "document_order"]] = Field(min_length=1)


class LabelRowValue(Value):
    when: dict[str, str] = Field(default_factory=dict)
    then: rules.Label


class LabelValue(Value):
    rows: list[LabelRowValue] = Field(min_length=1)


class CascadeValue(Value):
    extractors: dict[str, list[str]]     # evidence type (or `screen`) -> extractor names in order
    strategy: Literal["all", "gaps"]     # `evidence run --strategy`; recorded in proposal.json, not in the protocol


class LocateValue(Value):
    strategy: LocateStrategy
    params: dict[str, Any] = Field(default_factory=dict)


def _clause(text: str) -> str:
    return text.strip().rstrip(".")


# --- reading a card's value from a protocol mapping and writing a decision back -------------------------------

def _read_screen(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    s = p.get("screen") or {}
    return {"question": s.get("question", ""), "terms": list(s.get("terms", []))}


def _apply_screen(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    s = p.setdefault("screen", {"extractors": [{"name": "regex_screen"}, {"name": "llm_screen"}], "on_fail": "skip"})
    s["question"], s["terms"] = v["question"], list(v["terms"])


def _read_roles(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    compare = p["synthesis"]["compare"]
    by_role = {f.treatment.role: f.treatment.definition, f.control.role: f.control.definition}
    return {k: {"role": compare[k], "definition": by_role.get(compare[k], "")} for k in ("treatment", "control")}


def _apply_roles(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    old = p["synthesis"]["compare"]
    t, c = v["treatment"], v["control"]
    rename = {old["treatment"]: t["role"], old["control"]: c["role"]}
    p["synthesis"]["compare"] = {"treatment": t["role"], "control": c["role"]}
    cond = p["evidence_types"]["condition"]
    cond["fields"]["properties"]["role"]["enum"] = [t["role"], c["role"], "other"]
    cond["fields"]["properties"]["role"]["description"] = f"{t['role']}, {c['role']} or other"
    cond["description"] = (f"An experimental condition the paper compares: a system variant whose results are reported. "
                           f"role is {t['role']} for {_clause(t['definition'])}, {c['role']} for "
                           f"{_clause(c['definition'])}, other for anything else.")
    for spec in p["evidence_types"].values():   # explicit regex patterns follow the renamed roles
        for step in spec.get("extractors", []):
            conditions = (step.get("config") or {}).get("conditions")
            if isinstance(conditions, dict):
                step["config"]["conditions"] = {rename.get(k, k): pats for k, pats in conditions.items()}


def _read_metrics(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    return {"metrics": [dict(m) for m in p["synthesis"]["metrics"]]}


def _apply_metrics(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    names = [m["canonical"] for m in v["metrics"]]
    p["synthesis"]["metrics"] = [dict(m) for m in v["metrics"]]
    p["evidence_types"]["metric"]["fields"]["properties"]["canonical"]["enum"] = [*names, "other"]
    meas = p["evidence_types"]["measurement"]
    bounds = []
    for b in meas.get("bounds", []):   # a bound on metrics keeps only the metrics still named
        when = b.get("when")
        if when and when.get("link") == "metric" and when.get("field") == "canonical":
            kept = [x for x in when["values"] if x in names]
            if not kept:
                continue
            b = {**b, "when": {**when, "values": kept}}
        bounds.append(b)
    meas["bounds"] = bounds


def _read_key(key: str) -> Callable[[dict[str, Any], Frame], dict[str, Any]]:
    return lambda p, f: {key: copy.deepcopy(p["synthesis"][key])}


def _apply_min_effect(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    p["synthesis"]["min_effect"] = v["min_effect"]


def _read_pairing(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    return {"prefer": list(p["synthesis"].get("pairing", {}).get("prefer", ["table_cell", "document_order"]))}


def _apply_pairing(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    p["synthesis"].setdefault("pairing", {"rule": "same_dataset"})["prefer"] = list(v["prefer"])


def _read_label(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    return {"rows": [{"when": dict(r.get("when") or {}), "then": r["then"]} for r in p["synthesis"]["label"]]}


def _apply_label(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    p["synthesis"]["label"] = [({"when": dict(r["when"])} if r.get("when") else {}) | {"then": r["then"]} for r in v["rows"]]


def _read_cascade(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    extractors = {t: [s["name"] for s in spec["extractors"]] for t, spec in p["evidence_types"].items()}
    if p.get("screen"):
        extractors["screen"] = [s["name"] for s in p["screen"]["extractors"]]
    return {"extractors": extractors, "strategy": "all"}


def _apply_cascade(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    for name, steps in v["extractors"].items():
        owner = p.get("screen") if name == "screen" else p["evidence_types"].get(name)
        if owner is None:
            raise ProposalError(f"cascade: {name!r} is not an evidence type of the protocol (or its screen)")
        old = {s["name"]: s for s in owner["extractors"]}
        owner["extractors"] = [copy.deepcopy(old.get(n, {"name": n})) for n in steps]   # keeps a step's config
    run["strategy"] = v["strategy"]


def _read_locate(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    loc = p.get("locate") or {}
    return {"strategy": loc.get("strategy", "exhaustive"), "params": dict(loc.get("params") or {})}


def _apply_locate(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    p["locate"] = {"strategy": v["strategy"], "params": dict(v["params"])}


@dataclass(frozen=True)
class Handler:
    value: type[Value]
    read: Callable[[dict[str, Any], Frame], dict[str, Any]]
    apply: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], None]


HANDLERS: dict[str, Handler] = {
    "screen": Handler(ScreenValue, _read_screen, _apply_screen),
    "roles": Handler(RolesValue, _read_roles, _apply_roles),
    "metrics": Handler(MetricsValue, _read_metrics, _apply_metrics),
    "min_effect": Handler(MinEffectValue, _read_key("min_effect"), _apply_min_effect),
    "pairing": Handler(PairingValue, _read_pairing, _apply_pairing),
    "label": Handler(LabelValue, _read_label, _apply_label),
    "cascade": Handler(CascadeValue, _read_cascade, _apply_cascade),
    "locate": Handler(LocateValue, _read_locate, _apply_locate),
}


def definitions() -> list[dict[str, Any]]:
    """The fixed cards of cards.yaml, checked against the handlers (same ids, same order)."""
    cards = yaml.safe_load(CARDS_FILE.read_text(encoding="utf-8"))
    ids = [c["id"] for c in cards]
    if ids != list(HANDLERS):
        raise AssertionError(f"cards.yaml lists {ids}, the handlers {list(HANDLERS)}")
    for c in cards:
        for o in c.get("options", []):
            HANDLERS[c["id"]].value.model_validate(o["value"])
    return cards


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def options(card: dict[str, Any], draft: dict[str, Any], f: Frame) -> list[dict[str, Any]]:
    """The card's options: the draft's value, then the fixed and generated ones that differ from it."""
    handler = HANDLERS[card["id"]]
    mine = handler.value.model_validate(handler.read(draft, f)).model_dump(mode="json")
    extra = list(card.get("options", []))
    if card["id"] == "cascade":
        steps = mine["extractors"]
        extra += [{"id": "gaps", "value": {"extractors": steps, "strategy": "gaps"},
                   "summary": "the draft's cascades; the run screens and escalates only the gaps (funnel)"},
                  {"id": "with_agentic", "summary": "the agentic extractor last in every type's cascade; gaps",
                   "value": {"extractors": {t: (n if t == "screen" or "agentic" in n else [*n, "agentic"])
                                            for t, n in steps.items()}, "strategy": "gaps"}}]
    out = [{"id": "draft", "value": mine, "summary": "the draft's value"}]
    for o in extra:
        value = handler.value.model_validate(o["value"]).model_dump(mode="json")
        same = next((x for x in out if _canon(x["value"]) == _canon(value)), None)
        if same is not None:
            same["summary"] += f" (= {o['id']}: {o['summary']})"
        else:
            out.append({"id": o["id"], "value": value, "summary": o["summary"]})
    return out


def evidence(card_id: str, draft: dict[str, Any], f: Frame) -> list[dict[str, Any]]:
    """The vocabulary entries behind a card's values (from the frame's lookups); empty without a vocabulary."""
    def entry(name: str, x: Any) -> dict[str, Any] | None:
        if getattr(x, "vocab_id", None) is None:
            return None
        return {"name": name, "vocab_id": x.vocab_id, "synonyms": list(getattr(x, "vocab_synonyms", []) or []),
                "higher_is_better": getattr(x, "vocab_higher_is_better", None)}
    if card_id == "screen":
        rows = [entry(t.term, t) for t in f.population.terms]
    elif card_id == "roles":
        rows = [entry(r.role, r) for r in (f.treatment, f.control)]
    elif card_id == "metrics":
        rows = [entry(o.canonical, o) for o in f.outcomes]
    else:
        rows = []
    return [r for r in rows if r]


def reply_model() -> type[BaseModel]:
    """The schema of the cards call: per card a default (an option id, or `model` with a proposal) and why."""
    fields: dict[str, Any] = {}
    for card_id, h in HANDLERS.items():
        name = "".join(w.capitalize() for w in card_id.split("_"))
        fields[card_id] = (create_model(f"{name}Default", default=(str, Field(description="an option id, or model")),
                                        rationale=(str, Field(description="why, in one or two sentences")),
                                        proposal=(h.value | None, Field(default=None, description="only with default model"))),
                           ...)
    return create_model("CardsReply", **fields)


CardsReply = reply_model()


def _user_prompt(f: Frame, draft_text: str, critic: dict[str, Any], cards: list[dict[str, Any]]) -> str:
    failed = [f"- {c['id']}: {c['message']}" for c in critic.get("checks", []) if not c["ok"]]
    parts = [f"Question: {f.question}", "",
             "Frame:", json.dumps(f.model_dump(mode="json", exclude={"call", "created", "vocabulary"}), ensure_ascii=False),
             "", "Draft protocol:", draft_text.strip(), "",
             "Critic findings:", *(failed or ["- none"]), "", "Cards:"]
    for c in cards:
        parts += [f"## {c['id']}: {c['title']}", c["ask"]]
        parts += [f"- option {o['id']}: {json.dumps(o['value'], ensure_ascii=False)} ({o['summary']})" for o in c["options"]]
        if c["vocabulary"]:
            parts.append("Vocabulary: " + json.dumps(c["vocabulary"], ensure_ascii=False))
    return "\n".join(parts) + "\n"


HEADER = """# Decisions on the proposal's choice points (docs/evidence-system.md Part E). Edit, then `evidence propose freeze DIR`.
# Per card: `choice` is an option id of cards.json, or `custom` together with a `value` in the card's shape
# (see the options there); `reason` is required (an empty reason is refused); `by` says who decided. The
# prefilled entries are the model's defaults (`by: model`, reason "default: ..."): freeze accepts them as they
# stand and records `by`. A choice other than the default must name who made it in `by`.
"""


def run(directory: Path | str, *, model: Model | None = None, alias: str | None = None) -> Path:
    """Write DIR/cards.json and DIR/decisions.yaml (one cached model call); refuses to overwrite decisions.yaml
    once it differs from the prefilled one it wrote (a person's edits are never lost)."""
    directory = Path(directory)
    f = frame_module.load(need(directory, FRAME, "frame"))
    draft_path = need(directory, DRAFT, "draft")
    critic = read_json(need(directory, CRITIC, "critic"))
    fresh(directory, DRAFT, critic.get("draft_sha256"), "critic")
    draft_text = draft_path.read_text(encoding="utf-8")
    draft = yaml.safe_load(draft_text)
    cards = [{**c, "options": options(c, draft, f), "vocabulary": evidence(c["id"], draft, f)} for c in definitions()]
    decisions_path = directory / DECISIONS
    previous = directory / CARDS
    if decisions_path.exists() and previous.exists():
        if read_json(previous).get("decisions_sha256") != sha(decisions_path):
            raise ProposalError(f"{decisions_path} has been edited; move it away to make the cards again")
    try:
        reply, call = ask(directory, "cards", prompt(PROMPT), _user_prompt(f, draft_text, critic, cards), CardsReply,
                          model=model_for(alias, model))
    except ValueError as exc:
        raise ProposalError(f"the cards reply does not validate: {exc}") from exc
    for c in cards:
        r = getattr(reply, c["id"])
        ids = [o["id"] for o in c["options"]]
        if r.default == MODEL and r.proposal is not None:
            c["options"].append({"id": MODEL, "value": r.proposal.model_dump(mode="json"), "summary": "the model's proposal"})
            c["default"], c["rationale"] = MODEL, r.rationale
        elif r.default in ids:
            c["default"], c["rationale"] = r.default, r.rationale
        else:   # an option the card does not have: the draft's value stands, and the card says so
            c["default"] = "draft"
            c["rationale"] = f"(the model named no option of this card ({r.default!r}); the draft's value stands) {r.rationale}"
    entries = [{"card": c["id"], "choice": c["default"], "reason": f"default: {c['rationale']}".strip(), "by": MODEL}
               for c in cards]
    write_text(decisions_path, HEADER + dump_yaml({"decisions": entries}))
    write_json(directory / CARDS, {"draft_sha256": sha(draft_path), "critic_sha256": sha(directory / CRITIC),
                                   "decisions_sha256": sha(decisions_path), "call": call, "created": now(),
                                   "cards": cards})
    return directory / CARDS


def validate(cards: list[dict[str, Any]], data: Any) -> list[dict[str, Any]]:
    """decisions.yaml checked against the cards: the decisions in card order, each with the applied `value`
    and the card's `default`; a ProposalError listing every problem otherwise."""
    entries = data.get("decisions") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ProposalError("decisions.yaml must hold `decisions:`, a list of {card, choice, reason, by}")
    by_card = {c["id"]: c for c in cards}
    problems: list[str] = []
    seen: dict[str, dict[str, Any]] = {}
    for n, e in enumerate(entries):
        if not isinstance(e, dict):
            problems.append(f"entry {n} is not a mapping")
            continue
        card = by_card.get(str(e.get("card")))
        if card is None:
            problems.append(f"entry {n}: unknown card {e.get('card')!r}")
            continue
        cid = card["id"]
        if cid in seen:
            problems.append(f"{cid}: decided twice")
            continue
        reason, who, choice = e.get("reason"), e.get("by"), e.get("choice")
        if not isinstance(reason, str) or not reason.strip():
            problems.append(f"{cid}: a decision without a reason is refused")
        if not isinstance(who, str) or not who.strip():
            problems.append(f"{cid}: `by` must say who decided (model, or your name)")
        options_ = {o["id"]: o for o in card["options"]}
        if choice == CUSTOM:
            try:
                value = HANDLERS[cid].value.model_validate(e.get("value")).model_dump(mode="json")
            except ValidationError as exc:
                problems.append(f"{cid}: choice custom needs a `value` in the card's shape: {exc.errors()[0]['msg']} "
                                f"at {'.'.join(map(str, exc.errors()[0]['loc'])) or 'value'}")
                continue
        elif choice in options_:
            if "value" in e:
                problems.append(f"{cid}: `value` is only for choice custom (choice {choice!r} has its own value)")
            value = options_[choice]["value"]
        else:
            problems.append(f"{cid}: choice {choice!r} is not an option of the card ({', '.join(options_)}) "
                            f"nor `custom` with a value")
            continue
        if choice != card["default"] and isinstance(who, str) and who.strip() == MODEL:
            problems.append(f"{cid}: choice {choice!r} is not the model's default ({card['default']!r}); "
                            "set `by` to who decided")
        seen[cid] = {"card": cid, "choice": choice, "value": value, "default": card["default"],
                     "reason": reason.strip() if isinstance(reason, str) else reason,
                     "by": who.strip() if isinstance(who, str) else who}
    missing = [c for c in by_card if c not in seen and not any(p.startswith(f"{c}:") for p in problems)]
    problems += [f"{c}: no decision" for c in missing]
    if problems:
        raise ProposalError("decisions.yaml refused:\n  " + "\n  ".join(problems))
    return [seen[c] for c in by_card]


def apply(draft: dict[str, Any], decisions: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """(the protocol mapping with every decision applied, in card order; the run settings {strategy})."""
    p = copy.deepcopy(draft)
    run_settings: dict[str, Any] = {}
    for d in decisions:
        HANDLERS[d["card"]].apply(p, d["value"], run_settings)
    return p, run_settings


def load_cards(directory: Path) -> dict[str, Any]:
    return read_json(need(directory, CARDS, "cards"))


def load_decisions(directory: Path) -> Any:
    return read_yaml(need(directory, DECISIONS, "cards"))
