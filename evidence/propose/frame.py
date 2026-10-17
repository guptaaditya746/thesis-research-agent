"""Step 1, `frame` (one model call): the question as a PICO-like frame, `frame.json`.

The model names the population (which papers, as a screening question and the terms a relevant paper
contains), the treatment and the control (a role id, a label, a definition, synonyms), the outcomes (a
canonical id, its direction, whether it is a fraction, synonyms) and the effect labels an author's
conclusion takes (each with the direction it asserts). The *source* of every entry is not the model's
word: the code looks each name up in the vocabulary snapshot (if one is given) and writes
`source: ontology` with the term's id when it is there, `invented` otherwise. A matched term's other
synonyms and its direction are recorded beside the entry as evidence for the person who edits the frame;
they are not added to it (a synonym the regex extractors do not know would change the draft's patterns).

The person may edit frame.json before `draft`; `Frame` validates it then.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_ai.models import Model

from . import vocab as vocab_module
from .common import FRAME, ProposalError, ask, model_for, now, prompt, write_json

PROMPT = "frame-v1.md"
Source = Literal["ontology", "invented"]
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
    fraction: bool = Field(description="true when the values are shares between 0 and 1 (accuracies, rates)")
    synonyms: list[str]


class EffectLabelReply(BaseModel):
    value: str = Field(description="a short lower-case id of an author's conclusion, e.g. improves")
    direction: Literal["supports", "contradicts", "neutral"]


class FrameReply(BaseModel):
    population: PopulationReply
    treatment: RoleReply
    control: RoleReply
    outcomes: list[OutcomeReply] = Field(description="the question metrics, most important first")
    effect_labels: list[EffectLabelReply]


# frame.json (what the person edits and `draft` reads).
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrameTerm(Strict):
    term: str = Field(min_length=1)
    source: Source = "invented"
    vocab_id: str | None = None


class Population(Strict):
    description: str
    screening_question: str = Field(min_length=1)
    terms: list[FrameTerm] = Field(min_length=1)
    source: Source = "invented"


class Role(Strict):
    role: str = Field(pattern=ID)
    label: str = Field(min_length=1)
    definition: str
    synonyms: list[FrameTerm] = Field(default_factory=list)
    source: Source = "invented"
    vocab_id: str | None = None
    vocab_synonyms: list[str] = Field(default_factory=list)   # evidence only; not used by the draft

    @property
    def names(self) -> list[str]:
        return [self.label, *(s.term for s in self.synonyms)]


class Outcome(Strict):
    canonical: str = Field(pattern=ID)
    label: str = Field(min_length=1)
    higher_is_better: bool
    fraction: bool = False
    synonyms: list[FrameTerm] = Field(default_factory=list)
    source: Source = "invented"
    vocab_id: str | None = None
    vocab_synonyms: list[str] = Field(default_factory=list)
    vocab_higher_is_better: bool | None = None

    @property
    def names(self) -> list[str]:
        return [self.label, *(s.term for s in self.synonyms)]


class EffectLabel(Strict):
    value: str = Field(pattern=ID)
    direction: Literal["supports", "contradicts", "neutral"]
    source: Source = "invented"


class Frame(Strict):
    question: str = Field(min_length=1)
    vocabulary: dict[str, str] | None = None     # {name, sha256, path} of the snapshot used, or null
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


def vocabulary_listing(vocab: vocab_module.Vocabulary | None) -> str:
    if vocab is None:
        return "Vocabulary: none."
    lines = [f"Vocabulary {vocab.name} (id | kind | label | synonyms | higher is better):"]
    for t in vocab.terms:
        hib = "" if t.higher_is_better is None else str(t.higher_is_better).lower()
        lines.append(f"- {t.id} | {t.kind} | {t.label} | {'; '.join(t.synonyms)} | {hib}")
    return "\n".join(lines)


def _slug(text: str) -> str:
    return vocab_module.slug(text) or "x"


def _terms(names: list[str], vocab: vocab_module.Vocabulary | None, kinds: tuple[str, ...],
           skip: str | None = None) -> list[FrameTerm]:
    """Names as FrameTerms, repeats dropped. Only exact repeats: "retrieval augmented" and "retrieval-augmented"
    are two screen terms (a term is matched word-bounded as written, evidence/extractors/screen.py)."""
    out: list[FrameTerm] = []
    seen = {" ".join(skip.split())} if skip else set()
    for name in (" ".join(n.split()) for n in names):
        if not name or name in seen:
            continue
        seen.add(name)
        term = vocab.match(name, kinds) if vocab else None
        out.append(FrameTerm(term=name, source="ontology" if term else "invented", vocab_id=term.id if term else None))
    return out


def _match_any(names: list[str], vocab: vocab_module.Vocabulary | None, kinds: tuple[str, ...]) -> vocab_module.Term | None:
    for name in names:
        term = vocab.match(name, kinds) if vocab else None
        if term:
            return term
    return None


def _role(reply: RoleReply, vocab: vocab_module.Vocabulary | None) -> Role:
    kinds = ("condition", "method")
    term = _match_any([reply.label, reply.role, *reply.synonyms], vocab, kinds)
    return Role(role=_slug(reply.role), label=reply.label.strip(), definition=reply.definition.strip(),
                synonyms=_terms(reply.synonyms, vocab, kinds, skip=reply.label),
                source="ontology" if term else "invented", vocab_id=term.id if term else None,
                vocab_synonyms=[n for n in term.names if n not in (reply.label, *reply.synonyms)] if term else [])


def _outcome(reply: OutcomeReply, vocab: vocab_module.Vocabulary | None) -> Outcome:
    kinds = ("metric",)
    term = _match_any([reply.label, reply.canonical, *reply.synonyms], vocab, kinds)
    return Outcome(canonical=_slug(reply.canonical), label=reply.label.strip(), higher_is_better=reply.higher_is_better,
                   fraction=reply.fraction, synonyms=_terms(reply.synonyms, vocab, kinds, skip=reply.label),
                   source="ontology" if term else "invented", vocab_id=term.id if term else None,
                   vocab_synonyms=[n for n in term.names if n not in (reply.label, *reply.synonyms)] if term else [],
                   vocab_higher_is_better=term.higher_is_better if term else None)


def annotate(question: str, reply: FrameReply, vocab: vocab_module.Vocabulary | None) -> Frame:
    """The reply with ids normalised and every entry's source looked up in the vocabulary."""
    population = Population(description=reply.population.description.strip(),
                            screening_question=reply.population.screening_question.strip(),
                            terms=_terms(reply.population.terms, vocab, ("condition", "method", "metric")))
    return Frame(question=question, population=population, treatment=_role(reply.treatment, vocab),
                 control=_role(reply.control, vocab), outcomes=[_outcome(o, vocab) for o in reply.outcomes],
                 effect_labels=[EffectLabel(value=_slug(e.value), direction=e.direction) for e in reply.effect_labels])


def run(question: str, out: Path | str, *, vocab: str | Path | None = None, model: Model | None = None,
        alias: str | None = None) -> Path:
    """Write OUT/frame.json for `question` (one cached model call)."""
    directory = Path(out)
    directory.mkdir(parents=True, exist_ok=True)
    snapshot = vocab_module.load(vocab) if vocab else None
    instructions = prompt(PROMPT)
    user = f"Question: {question.strip()}\n\n{vocabulary_listing(snapshot)}\n"
    try:
        reply, call = ask(directory, "frame", instructions, user, FrameReply, model=model_for(alias, model))
        frame = annotate(question.strip(), reply, snapshot)
    except ValueError as exc:   # an id the model made that the frame cannot take
        raise ProposalError(f"the frame the model returned does not validate: {exc}") from exc
    ref = {**snapshot.ref(), "path": Path(vocab).as_posix()} if snapshot else None   # as given: a name or a path
    data = frame.model_copy(update={"vocabulary": ref, "call": call, "created": now()}).model_dump(mode="json")
    return write_json(directory / FRAME, data)
