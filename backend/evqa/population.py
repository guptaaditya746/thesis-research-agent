"""Checked population fields shared by extraction, question interpretation and answering."""
from __future__ import annotations

import gzip
import re
from functools import lru_cache

from evqa.contracts import Facet, Population
from repo_paths import DATA

VOCAB = DATA / "vocab" / "mesh-descriptors-2026.tsv.gz"
SINGLE = ("condition", "drug_naive", "age_min", "age_max")
MULTI = ("background_drugs", "comorbidities", "ethnicity_region")


@lru_cache(maxsize=1)
def vocabulary() -> tuple[dict[str, set[str]], dict[str, str]]:
    """Exact descriptor and entry-term lookup; ambiguous labels are left unresolved."""
    terms: dict[str, set[str]] = {}
    labels: dict[str, str] = {}
    with gzip.open(VOCAB, "rt", encoding="utf-8") as source:
        for line in source:
            ident, label, term = line.rstrip("\n").split("\t", 2)
            labels[ident] = label
            terms.setdefault(term.casefold(), set()).add(ident)
    return terms, labels


def checked_facet(field: str, facet: Facet, text: str) -> tuple[Facet, str | None]:
    """Keep only a field whose quoted source and value can be checked."""
    value = facet.value
    if value == "not stated" or value == "":
        return Facet(), None
    if not facet.quote or facet.quote not in text:
        return Facet(), f"{field}: quote is not in source"
    quote = facet.quote.casefold()
    if field in ("age_min", "age_max"):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not re.search(
            rf"(?<![\d.]){re.escape(str(value))}(?![\d.])", quote
        ):
            return Facet(), f"{field}: age number is not in quote"
        return facet, None
    if field == "drug_naive":
        if value not in ("yes", "no"):
            return Facet(), f"{field}: expected yes or no"
        negative = re.search(r"\b(?:never|untreated|naive|naïve|no prior|no previous|not previously)\b", quote)
        positive = re.search(r"\b(?:previously|prior|history of)\b", quote)
        treatment = re.search(r"\b(?:drug|drugs|medication|medications|treatment|therapy|therapies|treated)\b", quote)
        if not treatment or (value == "yes" and not negative) or (value == "no" and (negative or not positive)):
            return Facet(), f"{field}: quote does not support drug-naive value"
        return facet, None
    term = str(value).strip().casefold()
    terms, _ = vocabulary()
    ids = terms.get(term, set())
    if term not in quote:
        return Facet(), f"{field}: value is not in quote"
    if len(ids) == 1:
        return Facet(value=next(iter(ids)), quote=facet.quote), None
    return Facet(value=term, quote=facet.quote, unresolved=True), None


def check_population(pop: Population, text: str) -> tuple[Population, list[str]]:
    """Return a copy with unsupported fields cleared and their failed checks."""
    result = pop.model_copy(deep=True)
    errors: list[str] = []
    for field in SINGLE:
        value, error = checked_facet(field, getattr(result, field), text)
        setattr(result, field, value)
        if error:
            errors.append(error)
    for field in MULTI:
        values = []
        for facet in getattr(result, field):
            value, error = checked_facet(field, facet, text)
            if error:
                errors.append(error)
            else:
                values.append(value)
        setattr(result, field, values)
    result.facets_ok = not errors
    result.notes = errors
    result.label = label(result)
    return result, errors


def label(pop: Population) -> str:
    _, labels = vocabulary()
    def display(f: Facet) -> str:
        return labels.get(str(f.value), str(f.value))
    parts = []
    if pop.condition.value != "not stated":
        parts.append(display(pop.condition))
    parts.extend("on " + display(f) for f in pop.background_drugs if f.value != "not stated")
    if pop.drug_naive.value != "not stated":
        parts.append("drug-naive: " + str(pop.drug_naive.value))
    for field, sign in (("age_min", ">="), ("age_max", "<=")):
        f = getattr(pop, field)
        if f.value != "not stated":
            parts.append(f"age {sign} {f.value}")
    parts.extend(display(f) for field in ("comorbidities", "ethnicity_region") for f in getattr(pop, field)
                 if f.value != "not stated")
    return " · ".join(parts) or "not stated"


def key(pop: Population) -> tuple:
    return tuple(getattr(pop, f).value for f in SINGLE) + tuple(
        tuple(sorted(str(x.value) for x in getattr(pop, f))) for f in MULTI
    )


def fits(question: Population, actual: Population) -> bool | None:
    """True if all requested fields match, None if evidence is missing, else False."""
    unknown = False
    for field in SINGLE:
        want, got = getattr(question, field).value, getattr(actual, field).value
        if want == "not stated":
            continue
        if got == "not stated":
            unknown = True
        elif got != want:
            return False
    for field in MULTI:
        want = {str(x.value) for x in getattr(question, field) if x.value != "not stated"}
        got = {str(x.value) for x in getattr(actual, field) if x.value != "not stated"}
        if want and not got:
            unknown = True
        elif not want <= got:
            return False
    return None if unknown else True
