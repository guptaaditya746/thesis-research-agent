"""Step 4, `cards` (one model call): the fixed choice points (cards.yaml) as cards.json, and decisions.yaml
prefilled with the model's defaults for the person to edit.

Each card has options: `draft` (the draft's own value), the fixed options of cards.yaml (the cascade card's
are made from the draft: the same cascades escalating only the gaps, and with the agentic extractor last),
and `model` when the model proposes a value of its own. The model picks a default and gives a rationale.

decisions.yaml holds one entry per card: `choice` (an option id, or `custom` with a `value` in the card's
shape), `reason`, `by`. Prefilled entries are the model's default with `reason: "default: <rationale>"` and
`by: model`; freeze accepts them as they stand and records `by`, so a model default and a person's decision
stay apart in proposal.json. `validate` is freeze's check of the file: every card exactly once, a known
choice, a non-empty reason and `by`, a `value` only with `custom`, and a choice other than the model's
default made by someone other than `model`. An optional top-level `waivers` list (checked by `waivers`) is
where a person accepts a failing blocking critic check, which freeze otherwise refuses.
"""
from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict, get_args

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model, model_validator
from pydantic_ai.models import Model

from .. import rules
from ..protocol import Kind, LocateStrategy
from . import critic as critic_module, frame as frame_module
from .common import (CARDS, CRITIC, DECISIONS, DRAFT, FRAME, ProposalError, ask, dump_yaml, fresh, guard,
                     mark_written, model_for, need, now, prompt, read_json, read_yaml, sha, write_json, write_text)
from .frame import ID, Frame

PROMPT = "cards-v3.md"
CARDS_FILE = Path(__file__).resolve().parent / "cards.yaml"
PROTOCOLS = Path(__file__).resolve().parent.parent / "protocols"
CUSTOM, MODEL = "custom", "model"


class CardSpec(TypedDict):
    """A card of cards.yaml: the kinds of question it is asked for, and whether the UI collapses it."""
    id: str
    title: str
    ask: str
    sets: list[str]
    kinds: list[str]
    advanced: bool
    options: list[dict[str, Any]]


def is_model(who: Any) -> bool:
    """True when `by` names the model, in any case or spacing (`Model`, ` MODEL `): never a person."""
    return isinstance(who, str) and who.strip().casefold() == MODEL


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


class ClaimCheckValue(Value):
    by: Literal["direction"]    # the only way a claim is checked so far (protocol.Consistency)


class ListTargetValue(Value):
    target: Literal["metric", "condition", "dataset"]


class SameNamesValue(Value):
    same: dict[str, list[str]]  # a canonical name -> the other names it goes by


class BestMetricValue(Value):
    canonical: str = Field(pattern=ID)
    higher_is_better: bool


class MethodKindsValue(Value):
    kinds: dict[str, list[str]] = Field(min_length=1)   # a method kind -> the condition names that belong to it


class WinRuleValue(PairingValue):
    pass


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
    s = p.setdefault("screen", {"extractors": [{"name": "regex_screen"}, {"name": "llm_screen"}], "on_fail": "skip",
                                "lexical_miss": "reject"})
    s["question"], s["terms"] = v["question"], list(v["terms"])


def _read_roles(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    compare = p["synthesis"]["compare"]
    by_role = {f.treatment.role: f.treatment.definition, f.control.role: f.control.definition}
    return {k: {"role": compare[k], "definition": by_role.get(compare[k], "")} for k in ("treatment", "control")}


def _apply_roles(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    t, c = v["treatment"], v["control"]
    p["synthesis"]["compare"] = {"treatment": t["role"], "control": c["role"]}
    cond = p["evidence_types"]["condition"]
    cond["fields"]["properties"]["role"]["enum"] = [t["role"], c["role"], "other"]
    cond["fields"]["properties"]["role"]["description"] = f"{t['role']}, {c['role']} or other"
    cond["description"] = (f"An experimental condition the paper compares: a system variant whose results are reported. "
                           f"role is {t['role']} for {_clause(t['definition'])}, {c['role']} for "
                           f"{_clause(c['definition'])}, other for anything else.")
    # the regex steps' patterns follow in `apply` (draft.sync_regex), once every decision is in


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
        if name in run.get("replaced_types", ()) and name not in p["evidence_types"]:
            continue   # a type list_target swapped out: the new target keeps its own cascade
        owner = p.get("screen") if name == "screen" else p["evidence_types"].get(name)
        if owner is None:
            raise ProposalError(f"cascade: {name!r} is not an evidence type of the protocol (or its screen)")
        old = {s["name"]: s for s in owner["extractors"]}
        owner["extractors"] = [copy.deepcopy(old.get(n, {"name": n})) for n in steps]   # keeps a step's config
    run["strategy"] = v["strategy"]


def _read_locate(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    loc = p.get("locate") or {}
    strategy = loc.get("strategy", "exhaustive")
    return {"strategy": strategy, "params": {} if strategy == "exhaustive" else dict(loc.get("params") or {})}   # exhaustive reads none


def _apply_locate(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    p["locate"] = {"strategy": v["strategy"], "params": dict(v["params"])}


def _read_claim_check(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    return {"by": (p.get("consistency") or {}).get("by", "direction")}


def _apply_claim_check(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    p.setdefault("consistency", {})["by"] = v["by"]


INVENTORY_TEMPLATES = {"metric": "inv-metrics", "condition": "inv-methods", "dataset": "inv-datasets"}


def _read_list_target(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    return {"target": p["inventory"]["target"]}


def _apply_list_target(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    """The target's evidence type must exist, so a new target brings its type (field schema, extractors) from the
    hand-written inventory protocol of that target; the merged names belong to the old target and go."""
    if p["inventory"]["target"] == v["target"]:
        return
    template = read_yaml(PROTOCOLS / f"{INVENTORY_TEMPLATES[v['target']]}.yaml")
    run.setdefault("replaced_types", []).extend(p["evidence_types"])   # the cascade card must not name them any more
    p["evidence_types"] = copy.deepcopy(template["evidence_types"])
    p["inventory"] = {"target": v["target"]}


def _read_same_names(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    return {"same": {k: list(v) for k, v in (p["inventory"].get("same") or {}).items()}}


def _apply_same_names(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    if v["same"]:
        p["inventory"]["same"] = {k: list(n) for k, n in v["same"].items()}
    else:
        p["inventory"].pop("same", None)


def _read_best_metric(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    return dict(p["best"]["metric"])


def _apply_best_metric(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    p["best"]["metric"] = dict(v)


def _read_method_kinds(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    return {"kinds": {k: list(n) for k, n in p["best"]["kinds"].items()}}


def _apply_method_kinds(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    p["best"]["kinds"] = {k: list(n) for k, n in v["kinds"].items()}
    p["evidence_types"]["condition"]["fields"]["properties"]["kind"]["enum"] = list(v["kinds"])


def _read_win_rule(p: dict[str, Any], f: Frame) -> dict[str, Any]:
    return {"prefer": list((p["best"].get("pairing") or {}).get("prefer", ["table_cell", "document_order"]))}


def _apply_win_rule(p: dict[str, Any], v: dict[str, Any], run: dict[str, Any]) -> None:
    p["best"].setdefault("pairing", {"rule": "same_dataset"})["prefer"] = list(v["prefer"])


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
    "claim_check": Handler(ClaimCheckValue, _read_claim_check, _apply_claim_check),
    "list_target": Handler(ListTargetValue, _read_list_target, _apply_list_target),
    "same_names": Handler(SameNamesValue, _read_same_names, _apply_same_names),
    "best_metric": Handler(BestMetricValue, _read_best_metric, _apply_best_metric),
    "method_kinds": Handler(MethodKindsValue, _read_method_kinds, _apply_method_kinds),
    "win_rule": Handler(WinRuleValue, _read_win_rule, _apply_win_rule),
    "cascade": Handler(CascadeValue, _read_cascade, _apply_cascade),
    "locate": Handler(LocateValue, _read_locate, _apply_locate),
}


def definitions() -> list[CardSpec]:
    """The fixed cards of cards.yaml, checked against the handlers (same ids)."""
    cards = yaml.safe_load(CARDS_FILE.read_text(encoding="utf-8"))
    ids = [c["id"] for c in cards]
    if sorted(ids) != sorted(HANDLERS):
        raise AssertionError(f"cards.yaml lists {ids}, the handlers {list(HANDLERS)}")
    known = set(get_args(Kind))
    for c in cards:
        if not c.get("kinds") or not set(c["kinds"]) <= known or not isinstance(c.get("advanced"), bool):
            raise AssertionError(f"cards.yaml: card {c['id']!r} needs `kinds` (of {sorted(known)}) and `advanced: bool`")
    for c in cards:
        for o in c.get("options", []):
            HANDLERS[c["id"]].value.model_validate(o["value"])
            if not str(o.get("effect", "")).strip():
                raise AssertionError(f"cards.yaml: option {o['id']!r} of {c['id']!r} has no `effect`")
    return cards


def for_kind(kind: str) -> list[CardSpec]:
    """The cards asked for a question of `kind`: the main ones in file order, then the advanced ones
    (cascade, locate; the UI collapses them)."""
    mine = [c for c in definitions() if kind in c["kinds"]]
    return [c for c in mine if not c["advanced"]] + [c for c in mine if c["advanced"]]


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


# What the engine does with a value, for the options cards.yaml does not fix (the draft's, the generated
# cascades, the model's proposal); a fixed option's own `effect` wins where a value equals it.
EFFECTS: dict[str, Callable[[dict[str, Any]], str]] = {
    "screen": lambda v: ("a paper whose text holds none of the terms is judged not relevant by the keyword screen; "
                         "with screen.lexical_miss reject (the draft's) that ends the screen, so under strategy gaps "
                         "with on_fail skip it is never read by the LLM screen and gets no extraction (under all, "
                         "extraction runs anyway); with lexical_miss escalate the paper goes on to the next screen "
                         "extractor, which decides"),
    "roles": lambda v: (f"conditions with role {v['treatment']['role']} and {v['control']['role']} are compared; "
                        "a condition with any other role does not enter the comparison"),
    "metrics": lambda v: ("only these metrics are compared, "
                          + "; ".join(f"{m['canonical']}: {'higher' if m['higher_is_better'] else 'lower'} is better" for m in v["metrics"])),
    "min_effect": lambda v: (f"a study whose normalised difference is below {v['min_effect']:g} counts as neutral; "
                             "this is a plain cut-off, not a significance test"),
    "pairing": lambda v: ("of several values for one condition, metric and dataset the first of these decides, "
                          "then the next on a tie: " + ", ".join(v["prefer"])),
    "label": lambda v: "the label is the first row of this table whose condition the study counts satisfy",
    "cascade": lambda v: ("each evidence type runs its extractors in this order, "
                          + ("every extractor of a type runs, except that a type set to `cascade: until_found` stops after "
                              "the first extractor that finds an item" if v["strategy"] == "all" else
                             "and only a gap (a study without a usable pair) escalates to the next extractor")),
    "locate": lambda v: _locate_effect(v),
    "claim_check": lambda v: "a study agrees when the direction its authors claim equals the direction of its measured difference",
    "list_target": lambda v: f"only {v['target']} items are extracted; the answer lists each distinct name",
    "same_names": lambda v: (f"each canonical name stands for the names listed under it, which count as one entry; "
                             f"{len(v['same'])} canonical name(s) merge" if v["same"] else
                             "every distinct name is its own entry in the list"),
    "best_metric": lambda v: (f"inside each paper the method kind with the {'highest' if v['higher_is_better'] else 'lowest'} "
                              f"{v['canonical']} wins"),
    "method_kinds": lambda v: ("conditions are sorted into these method kinds: " + ", ".join(v["kinds"])
                               + "; a condition named under none is not ranked"),
    "win_rule": lambda v: ("of several values for one condition, metric and dataset the first of these decides, "
                           "then the next on a tie: " + ", ".join(v["prefer"])),
}


def _locate_effect(v: dict[str, Any]) -> str:
    if v["strategy"] == "exhaustive":
        return "the whole document; chunk and top_k are ignored"
    if v["strategy"] == "bm25":
        return (f"per evidence type at most the {v['params'].get('top_k', 6)} best-scoring passages (about "
                f"{v['params'].get('chunk_chars', 1500)} characters each) that match at least one of the type's query "
                "terms are read; text outside them is never seen")
    if v["strategy"] == "agent":
        return ("a pluggable agent Locator names where to look; evidence/ builds none, so a run with this strategy "
                "fails unless one is supplied")
    raise ValueError(f"unknown locate strategy {v['strategy']!r}")


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
    out = [{"id": "draft", "value": mine, "summary": "the draft's value", "effect": EFFECTS[card["id"]](mine)}]
    for o in extra:
        value = handler.value.model_validate(o["value"]).model_dump(mode="json")
        same = next((x for x in out if _canon(x["value"]) == _canon(value)), None)
        if same is not None:
            same["summary"] += f" (= {o['id']}: {o['summary']})"
            same["effect"] = o.get("effect") or same["effect"]   # the fixed option's own line is the better-checked one
        else:
            out.append({"id": o["id"], "value": value, "summary": o["summary"],
                        "effect": o.get("effect") or EFFECTS[card["id"]](value)})
    return out


def reply_model(kind: str = "effect") -> type[BaseModel]:
    """The schema of the cards call for a question of `kind`: per card of the kind a default (an option id, or
    `model` with a proposal) and why."""
    fields: dict[str, Any] = {}
    for card_id in (c["id"] for c in for_kind(kind)):
        h = HANDLERS[card_id]
        name = "".join(w.capitalize() for w in card_id.split("_"))
        fields[card_id] = (create_model(f"{name}Default", default=(str, Field(description="an option id, or model")),
                                        rationale=(str, Field(description="why, in one or two sentences")),
                                        proposal=(h.value | None, Field(default=None, description="only with default model"))),
                           ...)
    return create_model("CardsReply", **fields)


CardsReply = reply_model("effect")


def _user_prompt(f: Frame, draft_text: str, critic: dict[str, Any], cards: list[dict[str, Any]]) -> str:
    failed = [f"- {c['id']}: {c['message']}" for c in critic.get("checks", []) if not c["ok"]]
    parts = [f"Question: {f.question}", f"Kind of question: {f.kind}", "",
             "Frame:", json.dumps(f.model_dump(mode="json", exclude={"call", "created"}), ensure_ascii=False),
             "", "Draft protocol:", draft_text.strip(), "",
             "Critic findings:", *(failed or ["- none"]), "", "Cards:"]
    for c in cards:
        parts += [f"## {c['id']}: {c['title']}", c["ask"]]
        parts += [f"- option {o['id']}: {json.dumps(o['value'], ensure_ascii=False)} ({o['summary']}); effect: {o['effect']}" for o in c["options"]]
    return "\n".join(parts) + "\n"


def contradictions(cards: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Advisory: a default's rationale that says what its effect line denies, as {card, option, term}: a
    significance claim for min_effect (a plain cut-off), chunking or top-k for an exhaustive locate."""
    out = []
    for c in cards:
        option = next((o for o in c["options"] if o["id"] == c.get("default")), None)
        text = str(c.get("rationale", ""))
        if c["id"] == "min_effect":
            hit = re.search(r"significan\w*", text, re.I)
        elif c["id"] == "locate" and option is not None and option["value"].get("strategy") == "exhaustive":
            hit = re.search(r"chunk\w*|\btop\b|top_k|top-k", text, re.I)
        else:
            hit = None
        if hit:
            out.append({"card": c["id"], "option": c["default"], "term": hit.group(0)})
    return out


HEADER = """# Decisions on the proposal's choice points (docs/evidence-system.md Part E). Edit, then `evidence propose freeze DIR`.
# Per card: `choice` is an option id of cards.json, or `custom` together with a `value` in the card's shape
# (see the options there); `reason` is required (an empty reason is refused); `by` says who decided. The
# prefilled entries are the model's defaults (`by: model`, reason "default: ..."): freeze accepts them as they
# stand and records `by`. A choice other than the default must name who made it in `by`.
# Freeze refuses a protocol that fails a blocking critic check (severity in critic.json) unless a person waives
# it here: `waivers: [{check: <check id>, reason: ..., by: <your name>}]` (a waiver by `model` is refused).
"""


def run(directory: Path | str, *, model: Model | None = None, alias: str | None = None, force: bool = False,
        refresh: bool = False) -> Path:
    """Write DIR/cards.json and DIR/decisions.yaml (one cached model call). An existing decisions.yaml that
    differs from the one this step last wrote (written.json), or that it never wrote, is kept unless `force`
    (a person's edits are never lost); `refresh` asks the model again instead of using its cached reply."""
    directory = Path(directory)
    f = frame_module.load(need(directory, FRAME, "frame"))
    draft_path = need(directory, DRAFT, "draft")
    critic = read_json(need(directory, CRITIC, "critic"))
    fresh(directory, DRAFT, critic.get("draft_sha256"), "critic")
    draft_text = draft_path.read_text(encoding="utf-8")
    draft = yaml.safe_load(draft_text)
    cards = [{**c, "options": options(c, draft, f)} for c in for_kind(f.kind)]
    decisions_path = directory / DECISIONS
    guard(directory, DECISIONS, force)
    try:
        reply, call = ask(directory, "cards", prompt(PROMPT), _user_prompt(f, draft_text, critic, cards), reply_model(f.kind),
                          model=model_for(alias, model), refresh=refresh)
    except ProposalError:
        raise
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
                                   "rationale_contradicts_effect": contradictions(cards), "cards": cards})
    mark_written(directory, DECISIONS)
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
        if card is None and str(e.get("card")) in HANDLERS:
            problems.append(f"{e.get('card')}: not a card of this proposal (it belongs to another kind of question)")
            continue
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
        if not isinstance(choice, str):
            problems.append(f"{cid}: choice must be an option id ({', '.join(options_)}) or `custom`, not {choice!r}")
            continue
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
        if choice != card["default"] and is_model(who):
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


MIN_WAIVER_REASON = 10


def waivers(data: Any) -> list[dict[str, Any]]:
    """decisions.yaml's `waivers` checked: each {check, reason, by} names a deterministic critic check, gives a
    reason and the person who accepts the failure (never `model`); a ProposalError listing every problem
    otherwise. No `waivers` key: none."""
    entries = data.get("waivers") if isinstance(data, dict) else None
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise ProposalError("decisions.yaml: `waivers` must be a list of {check, reason, by}")
    problems: list[str] = []
    out: list[dict[str, Any]] = []
    for n, w in enumerate(entries):
        if not isinstance(w, dict):
            problems.append(f"waiver {n} is not a mapping {{check, reason, by}}")
            continue
        check, reason, who = w.get("check"), w.get("reason"), w.get("by")
        label = f"waiver {n} ({check})"
        if check not in critic_module.DETERMINISTIC:
            problems.append(f"{label}: unknown check {check!r} (one of {', '.join(critic_module.DETERMINISTIC)})")
        if not isinstance(reason, str) or not reason.strip():
            problems.append(f"{label}: a waiver without a reason is refused")
        elif len(reason.strip()) < MIN_WAIVER_REASON:
            problems.append(f"{label}: the reason must be at least {MIN_WAIVER_REASON} characters (say why it is safe)")
        if not isinstance(who, str) or not who.strip() or is_model(who):
            problems.append(f"{label}: `by` must name the person who accepts the failure, not {who!r}")
        out.append({"check": check, "reason": reason.strip() if isinstance(reason, str) else reason,
                    "by": who.strip() if isinstance(who, str) else who})
    if problems:
        raise ProposalError("decisions.yaml refused:\n  " + "\n  ".join(problems))
    return out


def apply(draft: dict[str, Any], decisions: list[dict[str, Any]], f: Frame) -> tuple[dict[str, Any], dict[str, Any]]:
    """(the protocol mapping with every decision applied, in card order; the run settings {strategy}).

    The regex steps' patterns are then made again from the decided roles and metrics exactly as the draft
    made them (draft.sync_regex): a dropped metric's built-in patterns go, an added metric or a renamed role
    gets patterns from its names, so the regex extractors emit only values the enums allow."""
    from . import draft as draft_module
    p = copy.deepcopy(draft)
    run_settings: dict[str, Any] = {}
    for d in decisions:
        HANDLERS[d["card"]].apply(p, d["value"], run_settings)
    run_settings.pop("replaced_types", None)
    if "synthesis" in p:   # roles and metrics: an inventory or best protocol has none
        draft_module.sync_regex(p, f)
    return p, run_settings


def load_cards(directory: Path) -> dict[str, Any]:
    return read_json(need(directory, CARDS, "cards"))


def load_decisions(directory: Path) -> Any:
    return read_yaml(need(directory, DECISIONS, "cards"))
