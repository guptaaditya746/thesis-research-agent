"""The generator recipe: what synth needs to draw a corpus for one topic, kept in `domains/<name>/generator.yaml`.

A recipe holds the topic's words (condition and metric names, contexts, filler sentences, claim wordings) and the
ranges the true values are drawn from. The generator code holds no topic word. Two rules every recipe follows, both
enforced here (they are what the fidelity checks rely on):
- no digit in a name, a filler sentence or a claim, so no filler number can be read as a measured value;
- no condition or metric name lies inside another name, so one fact's rendering never looks like another's.
`Recipe.sha256` is the digest of the file (line endings as LF), so a changed word is a new recipe.
"""
from __future__ import annotations

import functools
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import model_validator

from evidence.pack import DOMAINS
from evidence.protocol import DEFAULT_PACK, Strict
from jsonio import sha256_hex

Range = tuple[float, float]


class NameForms(Strict):
    label: str
    synonym: str
    description: str
    code: str | None = None      # the short name of the distributed level (a side's code, e.g. "R")
    kind: str | None = None      # the method kind (kind `best`), when the name has one


class SideSpec(Strict):
    role: str                    # "control" or "treatment"
    names: list[NameForms]


class MetricSpec(Strict):
    canonical: str
    forms: list[tuple[str, str, str]]    # (name, abbreviation, description)
    higher_is_better: bool
    unit: Literal["fraction", "seconds"]
    range: Range                         # a value not under test is drawn from here
    pair_range: Range | None = None      # the control value of a compared pair is drawn from here


class Reporting(Strict):
    formats: list[Literal["pct", "frac", "count", "k_of_n", "cell_pct", "cell_raw", "relative"]]
    count_base: int | None
    arm_size: tuple[int, int] | None
    allowed_numbers: list[str]           # regexes of numbers a paper may hold outside its placements
    dataset_size: str | None = None      # what a paper may say of each context's size ("1,000 questions")

    @model_validator(mode="after")
    def _regexes(self) -> Reporting:
        for pattern in self.allowed_numbers:
            re.compile(pattern)
        whole = [m.group() for p in self.allowed_numbers if (m := re.search(p, self.dataset_size or ""))]
        if self.dataset_size is not None and self.dataset_size not in whole:
            raise ValueError(f"dataset_size {self.dataset_size!r} is not one of the allowed_numbers, so a paper "
                             "that states it would fail the added-numbers check")
        return self


class IrrelevantPaper(Strict):
    titles: list[str]
    abstract: list[str]
    sections: list[str]
    body: list[str]
    conclusion: list[str]


class HardWords(Strict):
    main_experiment: str
    subset_experiments: list[str]
    ablation_experiment: str
    ablated: list[str]
    ablation_description: str            # holds "{component}"


class Text(Strict):
    claims: dict[str, dict[str, tuple[str, str]]]   # claim direction -> canonical metric -> (abstract, conclusion)
    titles: list[str]                               # each holds "{dataset}"
    intro: list[str]
    method: list[str]
    padding: list[str]
    discussion: list[str]
    conclusion: list[str]
    irrelevant: dict[str, IrrelevantPaper]
    hard: HardWords
    prompt_words: dict[str, str]                    # the topic words of the LLM prompts
    blind_examples: str                             # the examples block of the blind-extraction prompt
    # Not every recipe has these; the generator that reads one says so when it is missing.
    # Sentence templates of the template renderer: `paraphrased_count` is drawn from; every other key is one sentence
    # and only its first entry is used.
    templates: dict[str, list[str]] | None = None
    # The fidelity check `added_claims`: a sentence outside the claim placements that matches `claim_subject` and
    # one of `claim_cues` (regexes) states a second effect. Generator-side: the engine's words.yaml is not read.
    claim_subject: str | None = None
    claim_cues: list[str] | None = None
    authors: list[str] | None = None
    unit_noun: str | None = None                    # "patients", for "k of n patients"
    limitation_phrases: dict[str, list[str]] | None = None
    dependency_phrases: list[str] | None = None


class Network(Strict):
    things: list[str]
    reference: str
    edges: list[tuple[str, str]]
    contexts: list[str]


REUSES = ("method", "dataset", "result")     # what a study can reuse; `BuildsOn.phrases` follow this order


class BuildsOn(Strict):
    share: float
    reuses: dict[Literal["method", "dataset", "result"], float]
    # How a paper says it builds on an earlier one, one phrase per kind in REUSES order, each naming the cited study's
    # `{label}`: "we reuse the protocol of {label}", "the cohort of {label}", "as reported by {label}". synth/levels.py
    # sets each in a fixed sentence frame of its kind.
    phrases: list[str]


class Limitations(Strict):
    categories: dict[str, list[str]]
    per_study: tuple[int, int]


class NameVariants(Strict):
    share: float
    kinds: list[Literal["spelling", "code_name", "hereafter"]]


def _digits(where: str, value: Any) -> None:
    """Raise when a string anywhere inside `value` holds a digit."""
    if isinstance(value, str):
        if re.search(r"\d", value):
            raise ValueError(f"digit in {where}: {value!r} (a recipe's names and filler text hold no digits)")
    elif isinstance(value, dict):
        for k, v in value.items():
            _digits(f"{where}.{k}", v)
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            _digits(f"{where}[{i}]", v)
    elif isinstance(value, Strict):
        for name in type(value).model_fields:
            _digits(f"{where}.{name}", getattr(value, name))


class Recipe(Strict):
    domain: str
    effect_protocol: str                 # the protocol (id, in this domain) whose synthesis the generator follows
    question: str
    context: Literal["dataset", "population"]
    sides: dict[str, SideSpec]           # keyed by the protocol's compare roles
    others: list[NameForms]              # conditions that are neither side (ablations, other systems)
    other_codes: list[str] = []          # their codes at the distributed level, by position in a study
    question_metrics: list[MetricSpec]
    other_metrics: list[MetricSpec]
    contexts: list[str]
    effects: dict[str, Range]
    reporting: Reporting
    text: Text
    network: Network | None = None
    builds_on: BuildsOn | None = None
    limitations: Limitations | None = None
    name_variants: NameVariants | None = None
    sha256: str
    root: Path = DOMAINS                 # the folder of domains it was read from (not in the file, not in sha256)

    @model_validator(mode="after")
    def _rules(self) -> Recipe:
        # The prompt words and the blind examples carry digits on purpose (example values); everything else none.
        for name in ("question", "sides", "others", "question_metrics", "other_metrics", "contexts"):
            _digits(name, getattr(self, name))
        # The claim regexes are never written into a paper; they hold counts like {0,3}.
        for name in type(self.text).model_fields:
            if name not in ("prompt_words", "blind_examples", "claim_subject", "claim_cues"):
                _digits(f"text.{name}", getattr(self.text, name))
        for pattern in [self.text.claim_subject or "", *(self.text.claim_cues or [])]:
            re.compile(pattern)
        names = [n for s in self.sides.values() for n in s.names] + self.others
        spellings = [x for n in names for x in (n.label, n.synonym)] + [m.forms[0][0] for m in
                                                                        self.question_metrics + self.other_metrics]
        low = [s.lower() for s in spellings]
        for a in low:
            for b in low:
                if a != b and a in b:
                    raise ValueError(f"names clash: {a!r} lies inside {b!r}")
        if self.network is not None:
            self._network_rules()
        self._planted_rules()
        return self

    def _planted_rules(self) -> None:
        """What synth/truth.py `planted` draws from: limitation templates and builds-on phrases without digits, each
        limitation category with templates that name its `{thing}`, counts and shares that can be drawn."""
        for name in ("limitations", "builds_on"):
            if getattr(self, name) is not None:
                _digits(name, getattr(self, name))
        lim = self.limitations
        if lim is not None:
            low, high = lim.per_study
            if not lim.categories or not 0 <= low <= high:
                raise ValueError(f"limitations need categories and per_study (low, high), 0 <= low <= high; not "
                                 f"{list(lim.categories)} and {lim.per_study}")
            unnamed = [c for c, ts in lim.categories.items() if not ts or any("{thing}" not in t for t in ts)]
            if unnamed:
                raise ValueError(f"limitation categories {unnamed}: each needs templates, every one naming {{thing}}")
        b = self.builds_on
        if b is not None and (len(b.phrases) != len(REUSES) or any("{label}" not in p for p in b.phrases)
                              or not self.text.authors):
            raise ValueError(f"builds_on needs text.authors (a paper cites by author-year label) and one phrase per "
                             f"reuse kind, in the order {', '.join(REUSES)}, each naming {{label}}; not {b.phrases}")
        bad = {k: v for k, v in (("builds_on.share", self.builds_on and self.builds_on.share),
                                 ("name_variants.share", self.name_variants and self.name_variants.share))
               if v is not None and not 0 <= v <= 1}
        weights = list(self.builds_on.reuses.values()) if self.builds_on else [1.0]
        if min(weights, default=0) < 0 or not any(w > 0 for w in weights):
            bad["builds_on.reuses"] = self.builds_on.reuses
        if bad:
            raise ValueError(f"shares must lie in 0-1, and builds_on.reuses weights be non-negative with one "
                             f"positive: {bad}")

    def _network_rules(self) -> None:
        """What synth/network.py draws from: each thing (and the reference) a distinct name of a side, edges joining
        two of them once, network contexts among the recipe's, one question metric, rates only (counts of an arm),
        arm sizes, and authors for the studies' labels."""
        net = self.network
        labels = {n.label for side in self.sides.values() for n in side.names}
        nodes = [*net.things, net.reference]
        unknown = [t for t in nodes if t not in labels]
        if unknown or len(set(nodes)) != len(nodes):
            raise ValueError(f"network things {unknown or nodes} must be distinct labels of the sides' names")
        pairs = [frozenset(e) for e in net.edges]
        bad = [e for e, p in zip(net.edges, pairs) if len(p) != 2 or not p <= set(nodes)]
        if bad or len(set(pairs)) != len(pairs):
            raise ValueError(f"network edges {bad or net.edges} must each join two network things, each pair once")
        if not net.contexts or not set(net.contexts) <= set(self.contexts):
            raise ValueError(f"network contexts {net.contexts} must be some of the recipe's contexts {self.contexts}")
        if len(self.question_metrics) != 1:
            raise ValueError("a recipe with a network ranks its things on one question metric, not "
                             f"{len(self.question_metrics)}")
        not_rates = [m.canonical for m in self.question_metrics + self.other_metrics if m.unit != "fraction"]
        if not_rates:
            raise ValueError(f"a network recipe reports counts per arm: metrics {not_rates} are not fractions")
        size = self.reporting.arm_size
        if size is None or not 2 <= size[0] <= size[1]:
            raise ValueError(f"a network recipe needs reporting.arm_size (low, high), at least two; not {size}")
        if not self.text.authors:
            raise ValueError("a network recipe needs text.authors for the studies' author-year labels")


def load_recipe(domain: str, root: Path = DOMAINS) -> Recipe:
    """The recipe in `root/<domain>/generator.yaml`."""
    path = Path(root) / domain / "generator.yaml"
    if not path.is_file():
        raise ValueError(f"no generator recipe for domain {domain!r}: {path} does not exist")
    text = path.read_bytes().replace(b"\r\n", b"\n")
    data = yaml.safe_load(text)
    return Recipe(**data, domain=domain, sha256=sha256_hex(text), root=Path(root))


@functools.cache
def default_recipe() -> Recipe:
    """The recipe of the default pack (domains/default.yaml), read once: what synth draws when no recipe is given."""
    return load_recipe(DEFAULT_PACK)


def effect_protocol_path(recipe: Recipe) -> Path:
    """The protocol whose synthesis block the generator follows for `recipe` (`effect_protocol`, in its domain)."""
    return recipe.root / recipe.domain / "protocols" / f"{recipe.effect_protocol}.yaml"   # as pack.protocol_path
