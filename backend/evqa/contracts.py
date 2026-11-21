"""The files every step writes and the UI and eval read. One pydantic model per file; nothing else is a contract.

Run folder (runs/evqa/<run_id>/):
  config.yaml            the run config (RunConfig), hashed into run_id
  events.jsonl           Event, one per step start/end/LLM call summary/problem
  <qid>/spec.json        Spec           (Spec step; never sees papers or seed)
  <qid>/find.jsonl       FindHit        (one per paper kept, with the marked passages)
  <qid>/rows.jsonl       Row            (Extract: one per value, quote-checked)
  <qid>/settings.jsonl   audit of Extract's setting reading (attempts, failed checks)
  <qid>/links.jsonl      Link           (Link: setting sets judged same/different/unknown, generator + verifier)
  <qid>/answer.json      Answer         (Answer: code only)
Pipeline steps read ONLY: data/dataset/<domain>/questions/*.jsonl (question + intent card) and
data/dataset/<domain>/*/paper.md. Never data/seed (seed wall test).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, field_validator, model_serializer

Backend = Literal["qwen", "claude", "openrouter"]
QuestionType = Literal["lookup", "best", "effect", "trend", "list"]   # what the user asks (Spec decides it from the
                                                                       # question text; dataset labels such as
                                                                       # absent/near_miss are not question types)


class _DropEmpty(BaseModel):
    """Optional fields added after a contract was first written are left out of the JSON while they are empty, so
    files of the older kinds stay byte-identical (and Spec.sha256 stays the same)."""
    _drop_when_empty: tuple[str, ...] = ()

    @model_serializer(mode="wrap")
    def _drop(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        out = handler(self)
        for k in self._drop_when_empty:
            if k in out and out[k] in (None, [], {}):
                del out[k]
        return out


# ---------------------------------------------------------------- run config
# The config models refuse unknown keys (extra="forbid"): a typo in a config file (`search_term: false`) stops the
# load instead of being dropped while the run quietly uses the default. Refusing keys does not change run_id.
_STRICT = ConfigDict(extra="forbid")
STEP_NAMES = ("spec", "spec_check", "find", "extract", "link", "judge")   # every name the code passes to llm_for


class StepLLM(BaseModel):
    model_config = _STRICT
    backend: Backend = "qwen"
    model: str = "orch-model"          # qwen: LiteLLM alias; claude: full model id (claude-haiku-5-5)
    think: bool = False                # qwen: False (default, Aditya 21 Nov) sends enable_thinking=false (no reasoning trace, no reasoning
                                       # loop that eats max_tokens); for small, well-specified tasks


class FindConfig(BaseModel):
    model_config = _STRICT
    search_terms: bool = True          # the model lists other wordings to search exactly (off for the ablation)
    screen_max_papers: int = 20        # papers the LLM screen reads
    agent_max_steps: int = 6           # gap-filling agent cap (code-enforced)
    agent: bool = True                 # switch off for the ablation


class ExtractConfig(BaseModel):
    model_config = _STRICT
    extras: bool = True                # extra settings the paper varies but Spec did not list (off for the ablation)


class LinkConfig(BaseModel):
    model_config = _STRICT
    verifier: bool = True              # False: the generator's verdict is accepted unverified (ablation)
    max_pairs: int = 40                # code cap on setting-set pairs judged per question


class RunConfig(BaseModel):
    model_config = _STRICT
    name: str = "slice1"
    domain: str = "medical"
    mode: Literal["benchmark", "presentation"] = "benchmark"
    split: Literal["practice", "test"] = "test"
    questions: list[str] = Field(default_factory=list)   # empty = every question of the split
    llm: StepLLM = StepLLM()
    steps: dict[str, StepLLM] = Field(default_factory=dict)   # per-step override; keys from STEP_NAMES
    find: FindConfig = FindConfig()
    closed_book: bool = False          # no papers: Find returns nothing (the ~0 sanity run)
    extract: ExtractConfig | None = None   # None = defaults; left out of run_id while None (old run ids stay)
    links: LinkConfig | None = None

    @field_validator("steps")
    @classmethod
    def _known_steps(cls, v: dict[str, StepLLM]) -> dict[str, StepLLM]:
        """A step override under a name no step asks for would never be used, so it is refused."""
        unknown = sorted(set(v) - set(STEP_NAMES))
        if unknown:
            raise ValueError(f"unknown step(s) {unknown}; known steps: {list(STEP_NAMES)}")
        return v

    def llm_for(self, step: str) -> StepLLM:
        return self.steps.get(step, self.llm)

    def run_id(self) -> str:
        blob = json.dumps(self.model_dump(mode="json", exclude_none=True), sort_keys=True)
        return f"{self.name}-{hashlib.sha256(blob.encode()).hexdigest()[:10]}"

    @classmethod
    def load(cls, path: Path) -> RunConfig:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


# ---------------------------------------------------------------- population
class Facet(BaseModel):
    """A checked population field and its source; unresolved terms remain visible."""
    value: str | int | float = "not stated"
    quote: str = ""
    unresolved: bool = False


class Population(BaseModel):
    id: str = ""
    paper: str = ""
    condition: Facet = Field(default_factory=Facet)
    background_drugs: list[Facet] = Field(default_factory=list)
    drug_naive: Facet = Field(default_factory=Facet)
    age_min: Facet = Field(default_factory=Facet)
    age_max: Facet = Field(default_factory=Facet)
    comorbidities: list[Facet] = Field(default_factory=list)
    ethnicity_region: list[Facet] = Field(default_factory=list)
    label: str = ""
    facets_ok: bool = False
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- domain-free settings
class Dimension(BaseModel):
    key: str
    question: str
    why: str
    fixed_value: str = ""
    quote: str = ""


class Setting(BaseModel):
    dimension: str
    value: str = "not stated"
    quote: str = ""
    source: Literal["row", "paper"] = "paper"
    note: str = ""
    extra: bool = False
    start: int | None = None           # offsets of the quote in paper.md (anchor.spans), for provenance
    end: int | None = None


class SettingSet(BaseModel):
    id: str
    paper: str
    settings: list[Setting] = Field(default_factory=list)
    label: str = ""


class Link(BaseModel):
    """Are two setting sets the same on the given dimensions? `a`/`b` are SettingSet ids, or QUESTION for the
    question's own fixed values. Generator and blind verifier are separate LLM calls; code accepts a verdict only
    when both agree and the quotes check, else the link is "unknown" (kept apart, shown as can't tell)."""
    a: str
    b: str
    dimensions: list[str] = Field(default_factory=list)   # the dimension keys judged
    verdict: Literal["same", "different", "unknown"] = "unknown"   # accepted verdict (code)
    differs_on: list[str] = Field(default_factory=list)
    quote_a: str = ""
    quote_b: str = ""
    generator: str = ""                # the generator's verdict ("" = no call)
    verifier: str = ""                 # the verifier's verdict ("" = no call, or verifier off)
    by: Literal["llm", "code", "cap"] = "llm"   # code: identical stated values / same paper; cap: not judged
    note: str = ""


QUESTION = "question"


# ---------------------------------------------------------------- spec
class Name(BaseModel):
    label: str                         # the name as the user (or question) gives it
    synonyms: list[str] = []           # other names the advisor knows from general knowledge
    definition: str = ""               # one line, plain words
    known: bool = True                 # familiarity gate: False = the advisor does not know this name


class OpenPoint(BaseModel):
    id: str                            # time_point | patient_group | dose | measure_variant | ...
    question: str                      # what the advisor asked (or would ask)
    choice: str                        # "all" or a fixed value
    source: Literal["user", "card", "default"] = "card"


class Spec(_DropEmpty):
    qid: str
    question: str
    type: QuestionType                 # from the question text only (spec/build.py ClassifyQuestion)
    subjects: list[Name]               # the thing(s) asked about; best: the candidates; effect: [A, B] when B is a
                                       # drug (A first); list: may be [] ("which studies report fasting glucose?")
    comparator: Name | None = None     # a control the question names (placebo); effect: B when B is a control
    measure: Name                      # list: label "" when the question names no measure
    fixed: dict[str, str] = {}         # slots the question itself fixes (e.g. dose "20 mg", time "24 weeks")
    open_points: list[OpenPoint] = []
    columns: list[str] = []            # table columns the answer will have (one per "all" open point)
    dimensions: list[Dimension] = Field(default_factory=list)
    higher_is_better: bool | None = None
    best_by: Literal["subject", "dose"] | None = None   # best only: what the candidates are (the subjects, or the doses of one subject)
    trend_by: Literal["time_point", "dose"] | None = None   # trend only: the variable the values are ordered by
    dialogue: list[dict[str, str]] = []   # advisor questions and the answers it got (<= 3)
    locked: bool = True
    sha256: str = ""                   # of the spec without this field

    _drop_when_empty = ("trend_by", "dimensions")

    def seal(self) -> Spec:
        body = self.model_dump(mode="json")
        body.pop("sha256", None)
        self.sha256 = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        return self


# ---------------------------------------------------------------- find
class Passage(BaseModel):
    start: int                         # character offsets in paper.md
    end: int
    text: str
    kind: Literal["table", "text"] = "text"
    columns: list[str] = []            # spec columns this passage can fill (LLM marking)
    # optional, Find details for the UI (added by Find, 21 Nov)
    role: Literal["value", "context"] = "value"   # value: states values of the measure; context: states a column's
                                                  # value (e.g. the patient group) for the paper's values
    subjects: list[str] = []           # spec subject labels whose values the passage holds (LLM marking)
    section: str = ""                  # nearest Markdown heading above the passage
    quote: str = ""                    # the marker's short quote; code checked it is inside `text`


class FindHit(BaseModel):
    paper: str                         # paper id (folder name)
    sources: list[Literal["regex", "terms", "agent", "bm25"]] = []   # bm25: only in runs made before 21 Nov
    screen: Literal["yes", "no", "unsure"] = "unsure"
    screen_reason: str = ""
    passages: list[Passage] = []
    details: dict[str, Any] = {}       # optional, per sub-step findings: regex terms, search terms, agent terms, marks


# ---------------------------------------------------------------- extract
class StdValue(BaseModel):
    value: str                         # decimal as text, signed for a change
    unit: str                          # QUDT / ex IRI
    decimals: int
    sign_basis: Literal["change", "level"] = "change"
    low: str | None = None
    high: str | None = None


class Row(BaseModel):
    paper: str
    subject: str
    comparator: str | None = None
    measure: str
    patient_group: str | None = None   # Extract: the harmonised label (one wording per set of patients in the question)
    settings: str | None = None
    setting_set: SettingSet | None = None
    patient_group_raw: str | None = None   # optional: the patient group as the extraction model wrote it
    dose: str | None = None
    time_point: str | None = None
    statistic: str = "mean difference vs comparator"
    std: StdValue | None = None        # None when norm.py could not read it ("can't compare")
    raw: str                           # the paper's own wording of the value
    quote: str                         # verbatim sentence or table row
    quote_start: int = -1              # offsets of the quote in paper.md (-1 = not found)
    quote_end: int = -1
    quote_ok: bool = False             # code: the quote is in the paper and holds the same value
    unit_text: str = ""                # the unit as the paper writes it (sentence or table header), read by norm.py
    also: list[str] = []               # Extract merge: other quotes of the same paper stating the same value
    note: str = ""                     # code notes: ambiguous anchor picked, conflict with another value, ...
    dropped: str | None = None         # Extract: why the row is outside the spec (other subject/measure); Answer skips it


# ---------------------------------------------------------------- answer
class AnswerRow(BaseModel):
    cells: dict[str, str]              # column -> value, e.g. {"time point": "24 wk", "patient group": "..."}
    value: str                         # standard form, e.g. "-0.78"
    unit: str
    rows: list[int] = []               # indexes into rows.jsonl


class BestGroup(BaseModel):
    group: dict[str, str] = {}         # the open-point values this group fixes ({} = one group)
    winner: str | None = None
    margin: str | None = None
    status: Literal["winner", "tie", "not_reported"] = "winner"
    note: str = ""
    ranking: list[dict[str, Any]] = []  # best first: {candidate, value, unit, cells (own open points), rows}
    missing: list[str] = []            # candidates with no row in this group


class EffectEntry(BaseModel):
    """effect: one difference A - B (in `unit`), for one study/group."""
    basis: Literal["head_to_head", "same_comparator", "vs_comparator"]
                                       # head_to_head: one row of A vs B (or B vs A, sign flipped);
                                       # same_comparator: A vs C and B vs C in the same group, each its best value;
                                       # vs_comparator: B is a control (placebo): the row of A vs it as reported
    group: dict[str, str] = {}         # the settings this difference holds for (time point, patient group, comparator
                                       # C, paper; the dose of A for a single row)
    a: str
    b: str
    a_value: str | None = None         # same_comparator only: A vs C and B vs C
    b_value: str | None = None
    difference: str                    # A - B
    unit: str
    step: str                          # rounding step of the printed values; |difference| <= step: no clear difference
    verdict: str                       # "<A> better" | "<B> better" | "no clear difference" (direction from the spec)
    papers: list[str] = []
    rows: list[int] = []


class TrendSeries(BaseModel):
    """trend: one ordered series of values for one group (the other open columns)."""
    group: dict[str, str] = {}
    axis: str                          # the column the points are ordered by (time_point | dose)
    points: list[dict[str, Any]] = []  # in order: {at, value, unit, papers, rows}
    direction: Literal["decreasing", "increasing", "flat", "mixed", "one point", "unclear"]
    note: str = ""                     # unclear: papers give different values at one point (see Answer.conflicts)


class PaperEntry(BaseModel):
    """list: one paper that tested the subject, with the rows and quotes that show it."""
    paper: str
    rows: list[int] = []
    quotes: list[str] = []
    design: dict[str, list[str]] = {}  # what the rows say about the study: subject, dose, time point, patient group,
                                       # measure (distinct values, canonical time and dose)


class Conflict(BaseModel):
    """Two or more papers give values for the same fact (subject, comparator, dose, time point, patient group) that
    differ by more than the rounding step. Any type; every value stays in the answer."""
    cells: dict[str, str]
    spread: str                        # max - min, in `unit`
    step: str
    unit: str
    values: list[dict[str, Any]] = []  # {paper, value, unit, rows}


class CantTell(BaseModel):
    """A row that may answer the question, but whose settings could not be linked to it ("can't tell")."""
    row: int
    paper: str
    value: str = ""
    reason: str = ""


class Answer(_DropEmpty):
    qid: str
    type: QuestionType
    columns: list[str] = []
    table: list[AnswerRow] = []
    groups: list[BestGroup] = []       # best only
    sentence: str = ""                 # one plain sentence made by code
    not_reported: bool = False
    # optional, per type (added 21 Nov; left out of the JSON when empty)
    effects: list[EffectEntry] = []    # effect
    trend: list[TrendSeries] = []      # trend
    papers: list[PaperEntry] = []      # list
    conflicts: list[Conflict] = []     # any type
    cant_tell: list[CantTell] = []     # rows whose fit could not be decided by accepted links (shown, not used)

    _drop_when_empty = ("effects", "trend", "papers", "conflicts", "cant_tell")


# ---------------------------------------------------------------- events
class Event(BaseModel):
    ts: float
    qid: str | None = None
    step: str                          # spec | find | extract | answer | eval | run
    kind: Literal["start", "end", "llm", "problem", "info"]
    data: dict[str, Any] = {}


# ---------------------------------------------------------------- io helpers
def write_json(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, models: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(m.model_dump_json() + "\n" for m in models), encoding="utf-8")


def read_jsonl(path: Path, cls: type[BaseModel]) -> list[Any]:
    if not path.is_file():
        return []
    return [cls.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
