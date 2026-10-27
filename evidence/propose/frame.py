"""Step 1, `frame` (one model call): the question as a PICO-like frame, `frame.json`.

The model names the population (which papers, as a screening question and the terms a relevant paper
contains), the treatment and the control (a role id, a label, a definition, synonyms), the outcomes (a
canonical id, its direction, the scale of its values, synonyms) and the effect labels an author's
conclusion takes (each with the direction it asserts).

The person may edit frame.json before `draft`; `Frame` validates it then. A frame.json written while the flow
still had vocabulary snapshots (removed 27 Oct) carries `vocabulary`, and per entry `source`, `vocab_id`,
`vocab_synonyms` and `vocab_higher_is_better`; they are dropped when it is read (`LEGACY_KEYS`).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator
from pydantic_ai.models import Model

from ..protocol import Kind
from .common import (CACHE, FRAME, REDO, ProposalError, ask, guard, mark_written, model_for, now, prompt,
                     write_json)

PROMPT = "frame-v3.md"
# The user message's second part. The flow had vocabulary snapshots until 27 Oct; this is the text it sent
# without one, kept so the prompt (and the cached replies of earlier frames) stay the same.
NO_VOCABULARY = "Vocabulary: none."
# Keys of a frame.json from the vocabulary snapshot days, dropped when it is read (see the module docstring).
LEGACY_KEYS = ("vocabulary", "source", "vocab_id", "vocab_synonyms", "vocab_higher_is_better")
Scale = Literal["fraction", "percent", "count", "score", "other"]
ID = r"^[a-z][a-z0-9_]*$"


# The model's reply (schema-constrained).
class PopulationReply(BaseModel):
    description: str = Field(description="which papers can answer the question, in one sentence")
    screening_question: str = Field(description="a yes/no question that decides whether one paper is in scope")
    terms: list[str] = Field(description="words or phrases every relevant paper contains (for a keyword screen)")


class RoleReply(BaseModel):
    role: str = Field(description="a short lower-case id, e.g. rag or baseline")
    label: str = Field(description="the usual name of this condition")
    definition: str = Field(description="what counts as this condition, in one sentence")
    synonyms: list[str] = Field(description="other names papers use for it")


class OutcomeReply(BaseModel):
    canonical: str = Field(description="a short lower-case id, e.g. factual_accuracy")
    label: str
    higher_is_better: bool
    scale: Scale = Field(description="how the values are reported: fraction (a share, 0 to 1), percent (0 to 100), "
                                     "count, score (another scale) or other")
    synonyms: list[str]


class EffectLabelReply(BaseModel):
    value: str = Field(description="a short lower-case id of an author's conclusion, e.g. improves")
    direction: Literal["supports", "contradicts", "neutral"]


class FrameReply(BaseModel):
    kind: Kind = Field("effect", description="effect, inventory, consistency or best: what kind of answer the question asks for")
    kind_reason: str = Field("", description="one sentence: the words of the question that decide the kind")
    population: PopulationReply
    treatment: RoleReply
    control: RoleReply
    outcomes: list[OutcomeReply] = Field(description="the question metrics, most important first")
    effect_labels: list[EffectLabelReply]


# frame.json (what the person edits and `draft` reads).
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _legacy_vocabulary(cls, data: Any) -> Any:
        if isinstance(data, dict) and any(k in data for k in LEGACY_KEYS):
            data = {k: v for k, v in data.items() if k not in LEGACY_KEYS}
        return data


class FrameTerm(Strict):
    term: str = Field(min_length=1)


class Population(Strict):
    description: str
    screening_question: str = Field(min_length=1)
    terms: list[FrameTerm] = Field(min_length=1)


class Role(Strict):
    role: str = Field(pattern=ID)
    label: str = Field(min_length=1)
    definition: str
    synonyms: list[FrameTerm] = Field(default_factory=list)

    @property
    def names(self) -> list[str]:
        return [self.label, *(s.term for s in self.synonyms)]


class Outcome(Strict):
    canonical: str = Field(pattern=ID)
    label: str = Field(min_length=1)
    higher_is_better: bool
    scale: Scale = "other"
    synonyms: list[FrameTerm] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _legacy_fraction(cls, data: Any) -> Any:
        """A frame.json from before `scale` has `fraction: true|false`: true is a fraction, false says nothing."""
        if isinstance(data, dict) and "fraction" in data:
            data = dict(data)
            legacy = data.pop("fraction")
            data.setdefault("scale", "fraction" if legacy else "other")
        return data

    @computed_field   # type: ignore[prop-decorator]
    @property
    def fraction(self) -> bool:
        """Values are shares (kept in frame.json for readers of the old key; the bound uses draft.rate_like)."""
        return self.scale in ("fraction", "percent")

    @property
    def names(self) -> list[str]:
        return [self.label, *(s.term for s in self.synonyms)]


class EffectLabel(Strict):
    value: str = Field(pattern=ID)
    direction: Literal["supports", "contradicts", "neutral"]


class Frame(Strict):
    question: str = Field(min_length=1)
    kind: Kind = "effect"                        # no kind in a frame.json from before the kinds: an effect question
    kind_reason: str = ""
    kind_by: str = "model"                       # "model" (the guess) or "user" (`--kind`, the kind endpoint)
    call: dict[str, Any] | None = None           # the model call that made it
    created: str | None = None
    population: Population
    treatment: Role
    control: Role
    outcomes: list[Outcome] = Field(min_length=1)
    effect_labels: list[EffectLabel] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> Frame:
        if self.treatment.role == self.control.role:
            raise ValueError("treatment and control need different role ids")
        if "other" in (self.treatment.role, self.control.role):
            raise ValueError("`other` is the role of every other condition; name the treatment and control otherwise")
        names = [o.canonical for o in self.outcomes]
        if len(set(names)) != len(names) or "other" in names:
            raise ValueError(f"outcome ids must be distinct and not `other`: {names}")
        values = [e.value for e in self.effect_labels]
        if len(set(values)) != len(values):
            raise ValueError(f"effect label values must be distinct: {values}")
        return self


def load(path: Path) -> Frame:
    from .common import read_json
    try:
        return Frame.model_validate(read_json(path))
    except ValueError as exc:
        if isinstance(exc, ProposalError):
            raise
        raise ProposalError(f"{path}: {exc}") from exc


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_") or "x"


def _terms(names: list[str], skip: str | None = None) -> list[FrameTerm]:
    """Names as FrameTerms, repeats dropped. Only exact repeats: "retrieval augmented" and "retrieval-augmented"
    are two screen terms (a term is matched word-bounded as written, evidence/extractors/screen.py)."""
    out: list[FrameTerm] = []
    seen = {" ".join(skip.split())} if skip else set()
    for name in (" ".join(n.split()) for n in names):
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(FrameTerm(term=name))
    return out


def _role(reply: RoleReply) -> Role:
    return Role(role=_slug(reply.role), label=reply.label.strip(), definition=reply.definition.strip(),
                synonyms=_terms(reply.synonyms, skip=reply.label))


def _outcome(reply: OutcomeReply) -> Outcome:
    return Outcome(canonical=_slug(reply.canonical), label=reply.label.strip(), higher_is_better=reply.higher_is_better,
                   scale=reply.scale, synonyms=_terms(reply.synonyms, skip=reply.label))


def annotate(question: str, reply: FrameReply) -> Frame:
    """The reply with ids normalised and repeated names dropped."""
    population = Population(description=reply.population.description.strip(),
                            screening_question=reply.population.screening_question.strip(),
                            terms=_terms(reply.population.terms))
    return Frame(question=question, kind=reply.kind, kind_reason=reply.kind_reason.strip(), population=population, treatment=_role(reply.treatment),
                 control=_role(reply.control), outcomes=[_outcome(o) for o in reply.outcomes],
                 effect_labels=[EffectLabel(value=_slug(e.value), direction=e.direction) for e in reply.effect_labels])


def run(question: str, out: Path | str, *, model: Model | None = None,
        alias: str | None = None, force: bool = False, refresh: bool = False, kind: str | None = None) -> Path:
    """Write OUT/frame.json for `question` (one cached model call). An existing frame.json the person edited
    is kept unless `force`; `refresh` asks the model again instead of using its cached reply. `kind` overrides
    the model's guess of the question kind (recorded as `kind_by: user`)."""
    directory = Path(out)
    directory.mkdir(parents=True, exist_ok=True)
    guard(directory, FRAME, force)
    instructions = prompt(PROMPT)
    user = f"Question: {question.strip()}\n\n{NO_VOCABULARY}\n"
    reply, call = ask(directory, "frame", instructions, user, FrameReply, model=model_for(alias, model), refresh=refresh)
    try:
        frame = annotate(question.strip(), reply)
    except ValueError as exc:   # an id the model made that the frame cannot take
        raise ProposalError(f"the frame the model returned does not validate: {exc}; "
                            + REDO.format(cache=directory / CACHE, key=call["cache_key"])) from exc
    if kind is not None:
        frame = frame.model_copy(update={"kind": kind, "kind_by": "user"})
    data = frame.model_copy(update={"call": call, "created": now()}).model_dump(mode="json")
    write_json(directory / FRAME, data)
    mark_written(directory, FRAME)
    return directory / FRAME
