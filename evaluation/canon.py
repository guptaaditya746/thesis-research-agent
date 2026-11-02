"""Canonical keys for the names a paper or an answer gives a metric, a condition or a dataset (evaluation only).

`Canon.from_truth(truth)` builds the name table of one corpus from what the corpus says (plan 2 Task 12; no import
of synth). Its domain is corpus.json `recipe.domain` (`GroundTruth.domain`), else the default pack. Two sources, in
this order (a form keeps the first key it is given):

1. the domain's generator recipe, `<domains>/<domain>/generator.yaml` read as plain YAML data, when it exists: old
   ground truth carries no synonym, no metric abbreviation or description and no kind (preflight P16). A metric's
   name, abbreviation or description gives the metric name; a condition's label or synonym gives its label; a
   context's name gives the name.
2. the ground truth: a condition's label and its name `variants` (a code name, a spelling, a "hereafter" short
   form) give the key of the first of its label, variant forms or aliases already known, else, when the label is
   itself a variant form, its last alias (the name the variant stands for: synth lists a paper-local code first and
   the label after it), else its label (a spelling variant keeps the real label; synth/levels.py Plan.truth_name); a metric's name and a dataset's name give their known key, else themselves. A condition's `aliases` only find a key and are never added: they can be
   paper-local codes (the distributed level's "B", "R"), which name different things in different papers.

`key(target, name)` (case-folded, whitespace collapsed) gives the stable key, or None for a name the corpus does
not know (a baseline's unknown name is then a false positive, never an error).

`kind_of(label)` gives the method kind of a condition (any known form of its name) for the `best` questions: a truth
condition's `kind`, else a recipe name's `kind` (P16; never the pack's protocols, which a user may edit: truth does
not change with them). `kinds` lists the kinds in that order.

`question_canonicals` are the canonicals of the question metrics, the studies' (each study's first metric) and the
recipe's (`other` is none): a fact with one of them is compared on its canonical alone (score.same_metric).
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml

from evidence.pack import DOMAINS
from evidence.protocol import DEFAULT_PACK

if TYPE_CHECKING:
    from .truth import GroundTruth

Target = Literal["metric", "condition", "dataset"]
OTHER = "other"


def fold(name: str) -> str:
    return " ".join(str(name).split()).casefold()


@functools.cache
def _yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None


def recipe_data(domain: str, root: Path = DOMAINS) -> dict[str, Any] | None:
    """`<root>/<domain>/generator.yaml` as plain data, or None when the domain has no recipe there."""
    data = _yaml(Path(root) / domain / "generator.yaml")
    return data if isinstance(data, dict) else None


@dataclass
class Canon:
    """The name table of one corpus (module docstring)."""
    domain: str
    root: Path = DOMAINS                                          # the folder of domains it was read from
    keys: dict[str, dict[str, str]] = field(default_factory=lambda: {"metric": {}, "condition": {}, "dataset": {}})
    kinds_of: dict[str, str] = field(default_factory=dict)       # condition key -> method kind
    question_canonicals: frozenset[str] = frozenset()

    def key(self, target: Target, name: str) -> str | None:
        """The stable key of `name` as a `target`, or None when the corpus does not know it."""
        return self.keys[target].get(fold(name))

    def kind_of(self, label: str) -> str | None:
        """The method kind of a condition named `label` (any known form), or None when it has none."""
        k = self.key("condition", label)
        return self.kinds_of.get(k) if k is not None else None

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self.kinds_of.values()))

    def _add(self, target: Target, forms: list[str], key: str) -> None:
        for form in forms:
            self.keys[target].setdefault(fold(form), key)

    def _known(self, target: Target, forms: list[str]) -> str | None:
        return next((k for f in forms if (k := self.key(target, f)) is not None), None)

    @classmethod
    def from_truth(cls, truth: GroundTruth | None, root: Path = DOMAINS) -> Canon:
        """The table of `truth`'s corpus; `root` the folder of domains its recipe is read from. Without a truth, the
        default pack's table from its recipe alone (`default_canon`)."""
        canon = cls((truth.domain if truth is not None else None) or DEFAULT_PACK, Path(root))
        recipe = recipe_data(canon.domain, root) or {}
        canon._from_recipe(recipe)
        studies = truth.studies if truth is not None else []
        if truth is not None:
            canon._from_truth(truth)
        names = [n for side in (recipe.get("sides") or {}).values() for n in side.get("names") or []]
        truth_kinds = [(str(c["label"]), str(c["kind"])) for s in studies for c in s.get("conditions") or []
                       if c.get("kind")]
        recipe_kinds = [(str(n["label"]), str(n["kind"])) for n in (*names, *(recipe.get("others") or []))
                        if n.get("kind")]
        for name, kind in (*truth_kinds, *recipe_kinds):
            if (k := canon.key("condition", name)) is not None:
                canon.kinds_of.setdefault(k, kind)
        canon.question_canonicals = frozenset(
            [str(m["canonical"]) for m in recipe.get("question_metrics") or []]
            + [str(ms[0]["canonical"]) for s in studies if (ms := s.get("metrics")) and ms[0].get("canonical")]) - {OTHER}
        return canon

    def _from_recipe(self, recipe: dict[str, Any]) -> None:
        for spec in (*(recipe.get("question_metrics") or []), *(recipe.get("other_metrics") or [])):
            for forms in spec.get("forms") or []:
                self._add("metric", [str(f) for f in forms], str(forms[0]))
        names = [n for side in (recipe.get("sides") or {}).values() for n in side.get("names") or []]
        for n in (*names, *(recipe.get("others") or [])):
            self._add("condition", [str(n["label"]), *([str(n["synonym"])] if n.get("synonym") else [])], str(n["label"]))
        for context in recipe.get("contexts") or []:
            self._add("dataset", [str(context)], str(context))

    def _from_truth(self, truth: GroundTruth) -> None:
        for study in truth.studies:
            for c in study.get("conditions") or []:
                variants = [str(form) for _, form in c.get("variants") or []]
                aliases = [str(a) for a in c.get("aliases") or []]
                own = [str(c["label"]), *variants]
                # the label itself a variant (a code name, a hereafter form): the name it stands for is the last alias
                k = self._known("condition", [*own, *aliases]) or (aliases[-1] if aliases and own[0] in variants
                                                                   else own[0])
                self._add("condition", own, k)
            for m in study.get("metrics") or []:
                name = str(m["name"])
                self._add("metric", [name], self.key("metric", name) or name)
        for fact in truth.datasets.values():
            name = str(fact.data["name"])
            self._add("dataset", [name], self.key("dataset", name) or name)


@functools.cache
def default_canon() -> Canon:
    """The default pack's table without a corpus (its recipe only): for a caller that has no truth."""
    return Canon.from_truth(None)
