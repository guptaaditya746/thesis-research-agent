"""`number_measurement`: number-first search for measurements (Part C, after regex, abbreviations and GLiNER).

regex_measurement starts from fixed sentence shapes ("71% for the closed-book model"); this extractor starts
from every number in the task's parts and asks what is around it.

- A table cell: the condition is the row label and the metric the column header (or the other way round in a
  table whose rows are metrics); the dataset is the row's dataset column, else a context dataset item named in
  the column header or the caption, else null.
- A sentence: the condition named right after the number ("71% (RAG)", "62% for the closed-book model"), else
  the nearest one before it, else the nearest one after it; a condition is not taken across a system noun,
  another value or a comparison word ("versus", "over", "compared"), nor when another number already names it
  right after itself. The metric is the nearest one. The dataset is a context dataset item named in the
  sentence, else null.

Labels resolve to context items by measure.Resolver's rules (protocol wording, labels, codes the paper
defines: "closed-book model (CB)") and also by the context items' own surface forms: the exact texts of their
spans, so an abbreviation item ("HR" for hallucination rate) or a condition whose code an earlier extractor
quoted ("B") resolves in a table header, a row label or a sentence. A form that names two items is not used.
A measurement is emitted only when both a condition and a metric resolve.

Values: a % sign or a % metric header makes a fraction (a % caption only for a fraction metric); a bare number
between 1 and 100 is read as a percentage only for the metrics in `fraction_metrics` (default: the canonicals
a protocol bounds to [0, 1]); any other metric keeps its value as written, a time unit or a millisecond header
giving seconds (units.py). Integers need a % sign or a time unit. Not values: deltas and differences ("by 4%",
"+3.2 points", "9% higher", "0.45 s slower"), ranges and changes ("0.6-0.7", "between 0.6 and 0.7", "from 71%
to 62%"), years, table, section and figure numbers, counts ("1,000 questions", "1.5 billion"), shares ("40% of
the questions") and cells under a difference header ("Δ Accuracy"). Own module, so every existing extractor
keeps its id.
"""
from __future__ import annotations

import re
from typing import Any

from ..contract import ExtractionResult, ExtractionTask, ExtractorSpec, Item, RunContext
from . import base, regex, terms, units
from .measure import CELL, DATASET_HEADER, DELTA_AFTER, DELTA_BEFORE, FROM_TO, HEAD_NOUN, SIGNED, Found, Resolver

VERSION = 1
SOURCES = (base.HERE / "numbers.py", base.HERE / "measure.py", base.HERE / "terms.py", base.HERE / "units.py",
           base.HERE / "regex.py", *base.SHARED_SOURCES)   # regex.py: INJECTED; units.py: time units, ms header
CODE_SHA256 = base.source_sha256(*SOURCES)

NUMBER = re.compile(r"(?<![\w.,])(\d+(?:\.\d+)?|\.\d+)(?:(\s?%)|\s?(ms|milliseconds?|s|secs?|seconds?)\b)?")
TIME_CELL = re.compile(r"^[*_]*\s*(\d+(?:\.\d+)?|\.\d+)\s?(ms|s|secs?|seconds?)\s*[*_]*$")
GLUED = re.compile(r"[\w]|[.,]\d|[-–]\w")   # "7B", "1,000", "5-shot": the number is part of a longer token
REFERENCE_BEFORE = re.compile(r"(?i)(?:\b(?:table|tab\.|section|sec\.|figure|fig\.|eq\.|equation|appendix|"
                              r"chapter|step|version|v)|§)\s*$")
CHANGE_BEFORE = re.compile(r"(?i)\b(?:absolute|relative|additional|extra)\s*$")
CHANGE_AFTER = re.compile(r"(?i)^\s*(?:absolute\s+|relative\s+)?(?:higher|lower|better|worse|greater|fewer|more|"
                          r"less|slower|faster|longer|shorter|improvements?|gains?|increases?|decreases?|"
                          r"reductions?|drops?|boosts?|margin|lead)\b")
COUNT_AFTER = re.compile(r"(?i)^\s*(?:questions|examples|samples|items|papers|documents|queries|instances|"
                         r"participants|annotators|tokens|passages|runs|seeds|layers|parameters|billion|million|"
                         r"thousand)\b")
SHARE_AFTER = re.compile(r"(?i)^\s+of\b")
RANGE = re.compile(r"(?i)\bbetween\s+\d*\.?\d+\s*%?\s*and\s+\d*\.?\d+\s*%?|"
                   r"\d*\.?\d+\s*%?\s*(?:-|–|—|to)\s*\d*\.?\d+\s*%?")
FOLLOWS = re.compile(r"\s*[(,–—-]?\s*(?:(?:for|with|by|of|from|in|using|on)\s+)?"
                     r"(?:the\s+|a\s+|an\s+|its\s+|our\s+)?")
DELTA_HEADER = re.compile(r"(?i)Δ|∆|\bdelta\b|\bdiff\w*|\bgain\b|\bimprove\w*|\bchange\b|\bvs\.?\b|\breduction\b")
COMPARED = re.compile(r"(?i)\b(?:over|than|versus|vs\.?|compared|relative|against|while|whereas|but|unlike)\b")
SYSTEMS = re.compile(r"(?i)\b(?:model|system|variant|baseline|pipeline|generator|approach|method|LLM|reader|"
                     r"retriever|ablation)s?\b")
PROSE_EXCLUDED = frozenset({"A", "I"})   # one-letter forms that are ordinary words in a sentence

Named = tuple[terms.Mention, Item]


class Surfaces:
    """Labels and mentions to context items: measure.Resolver first, then the items' surface forms (the exact
    texts of their spans and the codes the paper defines), each form naming exactly one item."""

    def __init__(self, r: Resolver) -> None:
        self.r = r
        self.conditions = _unique([(f, i) for i in r.conditions for f in _forms(i)]
                                  + [(code, item) for code, (item, _) in r.codes.items()])
        self.metrics = _unique([(f, i) for i in r.metrics for f in _forms(i)])

    def condition_label(self, label: str) -> tuple[Item, tuple[int, int] | None] | None:
        found = self.r.condition_label(label)
        if found is not None:
            return found
        item = _equal(self.conditions, label.strip(" *_"))
        return (item, None) if item is not None else None

    def metric_label(self, label: str) -> Item | None:
        found = self.r.metric_label(label)
        if found is not None:
            return found
        items = {i.item_id: i for _, _, i in _occurrences(self.metrics, label, 0, len(label), prose=False)}
        return next(iter(items.values())) if len(items) == 1 else None

    def condition_mentions(self, text: str, s: int, e: int) -> list[Named]:
        known = [(m, i) for m, i in ((m, self.r.condition_for(m)) for m in self.r.mentions(text, s, e))
                 if i is not None]
        return _merge(text, known, _occurrences(self.conditions, text, s, e, prose=True), "role")

    def metric_mentions(self, text: str, s: int, e: int) -> list[Named]:
        mentions = terms.find_all(text, self.r.metric_patterns, s, e)  # type: ignore[arg-type]
        known = [(m, i) for m, i in ((m, self.r.metric_for(m)) for m in mentions) if i is not None]
        return _merge(text, known, _occurrences(self.metrics, text, s, e, prose=True), "canonical")


class NumberMeasurement:
    evidence_type, name = "measurement", "number_measurement"

    def __init__(self, config: dict[str, Any]) -> None:
        self.given = {k: v for k, v in config.items() if k in regex.INJECTED}
        rest = {k: v for k, v in config.items() if k not in regex.INJECTED}
        self.fractions = [str(m) for m in rest.pop("fraction_metrics")]   # the pack's, or the protocol's
        self.patterns = {"alias": terms.ALIAS} | rest
        self.spec = ExtractorSpec(name=self.name, version=VERSION, kind="regex", evidence_types=("measurement",),
                                  code_sha256=CODE_SHA256,
                                  config={**self.given, **self.patterns, "fraction_metrics": self.fractions},
                                  determinism="exact")

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult:
        text = ctx.text()
        parts = base.ranges(task, text)
        context = ctx.context_items()
        datasets = [str(i.fields["name"]) for i in context if i.evidence_type == "dataset" and i.fields.get("name")]
        treatment = (self.given.get("compare") or {}).get("treatment")
        resolver = Resolver(text, context, {**self.patterns, "question_metrics": self.fractions,
                                            "treatment": treatment})
        found: list[Found] = []
        if resolver.conditions and resolver.metrics:
            names = Surfaces(resolver)
            for table in base.tables(text):
                if any(a <= table.start and table.end <= b for a, b in parts):
                    found.extend(self._table(task, text, table, names, datasets))
            for a, b in parts:
                for s, e in base.sentences(text, a, b):
                    found.extend(self._sentence(task, text, s, e, names, datasets))
        items: list[Item] = base.group("measurement", found)
        return ExtractionResult(extractor_id=self.spec.extractor_id, task_sha256=task.task_sha256, status="ok",
                                items=tuple(items), coverage=base.coverage(parts, items)).canonical()

    # values ----------------------------------------------------------------------------------------------

    def _value(self, raw: str, metric: Item, *, percent: bool, unit: str | None) -> float | None:
        """The number as the protocol stores it, or None when it cannot be a value of this metric."""
        fraction = metric.fields.get("canonical") in self.fractions
        if unit is not None:   # a time: only for a metric that is not a fraction
            return None if fraction else round(float(raw) / (1000 if unit.startswith("m") else 1), 6)
        value = base.to_fraction(raw, percent=percent, rate_like=fraction)
        if value is None or (fraction or percent) and value > 1:
            return None
        return value

    # tables ----------------------------------------------------------------------------------------------

    def _table(self, task: ExtractionTask, text: str, table: base.Table, r: Surfaces,
               datasets: list[str]) -> list[Found]:
        header = table.header
        dataset_col = next((n for n, c in enumerate(header) if DATASET_HEADER.match(c.text.strip(" *_"))), None)
        caption_dataset = _named(table.caption, datasets)
        out: list[Found] = []
        for row in table.rows:
            label = next(((n, c) for n, c in enumerate(row) if n != dataset_col and c.text.strip(" *_")), None)
            if label is None or DELTA_HEADER.search(label[1].text):
                continue
            row_condition = r.condition_label(label[1].text)
            row_metric = r.metric_label(label[1].text) if row_condition is None else None
            if row_condition is None and row_metric is None:
                continue
            row_dataset = None
            if dataset_col is not None and dataset_col < len(row):
                row_dataset = row[dataset_col].text.strip(" *_") or None
            for n, cell in enumerate(row):
                if n <= label[0] or n == dataset_col or n >= len(header) or DELTA_HEADER.search(header[n].text):
                    continue
                col = header[n]
                if row_condition is not None:
                    condition, metric, cond_cell, metric_cell = row_condition, r.metric_label(col.text), label[1], col
                else:
                    condition, metric, cond_cell, metric_cell = r.condition_label(col.text), row_metric, col, label[1]
                if condition is None or metric is None:
                    continue
                fraction = metric.fields.get("canonical") in self.fractions
                timed = TIME_CELL.match(cell.text)
                if timed is not None:
                    raw, a, b, unit, pct = timed.group(1), timed.start(1), timed.end(1), timed.group(2), False
                else:
                    hit = CELL.match(cell.text)
                    if hit is None:
                        continue
                    # a % caption speaks for the table's rates, not for a latency column beside them
                    pct = bool(hit.group(2)) or _percent(metric_cell.text) or fraction and _percent(table.caption)
                    raw, a, b = hit.group(1), hit.start(1), hit.end(2) if hit.group(2) else hit.end(1)
                    ms = units.MS_HEADER.search(col.text) or units.MS_HEADER.search(label[1].text)
                    unit = "ms" if ms and not fraction else None
                item, defined = condition
                value = self._value(raw, metric, percent=pct, unit=unit)
                if value is None:
                    continue
                spans = [base.span(task, text, cell.start + a, cell.start + b, "value"),
                         base.span(task, text, cond_cell.start, cond_cell.end, "condition_label"),
                         base.span(task, text, metric_cell.start, metric_cell.end, "metric_label")]
                if defined is not None:
                    spans.append(base.span(task, text, *defined, "condition_label"))
                dataset = row_dataset or _named(col.text, datasets) or caption_dataset
                out.append(({"value": value, "dataset": dataset},
                            {"condition": item.item_id, "metric": metric.item_id}, spans))
        return out

    # sentences -------------------------------------------------------------------------------------------

    def _sentence(self, task: ExtractionTask, text: str, s: int, e: int, r: Surfaces,
                  datasets: list[str]) -> list[Found]:
        conditions = r.condition_mentions(text, s, e)
        metrics = r.metric_mentions(text, s, e)
        if not conditions or not metrics:
            return []
        excluded = [(m.start(), m.end()) for rx in (FROM_TO, RANGE) for m in rx.finditer(text, s, e)]
        hits = [h for h in NUMBER.finditer(text, s, e) if self._candidate(text, s, e, h, excluded)]
        rights = [_right(text, h, conditions) for h in hits]
        claimed = {(c[0].start, c[0].end) for c in rights if c is not None}   # named right after another number
        free = [c for c in conditions if (c[0].start, c[0].end) not in claimed]
        dataset = _named(text[s:e], datasets)
        out: list[Found] = []
        for n, hit in enumerate(hits):
            others = [h.start() for h in hits if h is not hit]
            cond = rights[n] or _nearest(text, hit, free, others)
            unit = hit.group(3)
            usable = [(m, i) for m, i in metrics if unit is None or i.fields.get("canonical") not in self.fractions]
            met = min(usable, key=lambda mi: (_distance(hit, mi[0]), mi[0].start), default=None)
            if cond is None or met is None:
                continue
            value = self._value(hit.group(1), met[1], percent=bool(hit.group(2)), unit=unit)
            if value is None:
                continue
            end = hit.end(2) if hit.group(2) else hit.end(1)
            spans = [base.span(task, text, hit.start(1), end, "value"),
                     base.span(task, text, cond[0].start, cond[0].end, "condition_label"),
                     base.span(task, text, met[0].start, met[0].end, "metric_label")]
            out.append(({"value": value, "dataset": dataset},
                        {"condition": cond[1].item_id, "metric": met[1].item_id}, spans))
        return out

    def _candidate(self, text: str, s: int, e: int, hit: re.Match[str], excluded: list[tuple[int, int]]) -> bool:
        """A number that can be a reported value: not part of a longer token, a delta, a range, a year, a
        reference, a count or a share."""
        raw, pct, unit = hit.group(1), hit.group(2), hit.group(3)
        if GLUED.match(text, hit.end()) and hit.end() < e:
            return False
        if "." not in raw and not pct and not unit:
            return False   # a bare integer: a count, a year, a k
        if "." not in raw and 1900 <= int(raw) <= 2099:
            return False   # a year ("the 1990s")
        if any(a <= hit.start() < b for a, b in excluded):
            return False
        before, after = text[max(s, hit.start() - 25):hit.start()], text[hit.end():e]
        if (DELTA_BEFORE.search(before) or SIGNED.search(before) or CHANGE_BEFORE.search(before)
                or REFERENCE_BEFORE.search(before)):
            return False
        if DELTA_AFTER.match(after) or CHANGE_AFTER.match(after) or COUNT_AFTER.match(after):
            return False
        return not (pct and SHARE_AFTER.match(after))   # "40% of the questions": a share of something else


# surface forms -------------------------------------------------------------------------------------------

def _forms(item: Item) -> list[str]:
    """The exact texts of an item's spans, whitespace collapsed (in a sentence a one-letter form is used
    only when it is a capital other than A and I, _occurrences)."""
    return [t for t in dict.fromkeys(" ".join(str(s.selector.get("exact", "")).split()) for s in item.spans)
            if t and not t.isdigit()]


def _unique(pairs: list[tuple[str, Item]]) -> dict[str, Item]:
    """form -> item, leaving out a form that names two different items."""
    seen: dict[str, dict[str, Item]] = {}
    for form, item in pairs:
        seen.setdefault(form, {})[item.item_id] = item
    return {f: next(iter(items.values())) for f, items in seen.items() if len(items) == 1}


def _pattern(form: str) -> re.Pattern[str]:
    """A whole-word match; a short or capitalised form (a code, an abbreviation) matches its case only."""
    flags = 0 if len(form) <= 5 or form.isupper() else re.IGNORECASE
    return re.compile(rf"(?<![\w-]){re.escape(form)}(?![\w-])", flags)


def _equal(forms: dict[str, Item], label: str) -> Item | None:
    found = {i.item_id: i for f, i in forms.items() if _pattern(f).fullmatch(label)}
    return next(iter(found.values())) if len(found) == 1 else None


def _occurrences(forms: dict[str, Item], text: str, s: int, e: int, *, prose: bool) -> list[tuple[int, int, Item]]:
    out = []
    for form, item in forms.items():
        if prose and (form in PROSE_EXCLUDED or len(form) < 2 and not form.isupper()):
            continue
        out += [(m.start(), m.end(), item) for m in _pattern(form).finditer(text, s, e)]
    return out


def _merge(text: str, known: list[Named], extra: list[tuple[int, int, Item]], key: str) -> list[Named]:
    """Mentions found by wording, plus surface-form matches that overlap none of them (longest first)."""
    taken = [(m.start, m.end) for m, _ in known]
    out = list(known)
    for a, b, item in sorted(extra, key=lambda x: (x[0], x[0] - x[1])):
        if all(b <= x or a >= y for x, y in taken):
            taken.append((a, b))
            out.append((terms.Mention(a, b, str(item.fields.get(key, "")), text[a:b]), item))
    return sorted(out, key=lambda mi: mi[0].start)


# helpers ---------------------------------------------------------------------------------------------------

def _percent(label: str) -> bool:
    return "%" in label or "percent" in label.casefold()


def _named(text: str, names: list[str]) -> str | None:
    """The first dataset name (a context item's) that occurs in `text` as a whole word."""
    found = [(m.start(), n) for n in names for m in [re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text)] if m]
    return min(found)[1] if found else None


def _distance(hit: re.Match[str], m: terms.Mention) -> int:
    return hit.start() - m.end if m.end <= hit.start() else m.start - hit.end()


def _right(text: str, hit: re.Match[str], conditions: list[Named]) -> Named | None:
    """The condition named right after the number: "71% (RAG)", "62% for the closed-book model"."""
    follows = FOLLOWS.match(text, hit.end())
    return next(((m, i) for m, i in conditions if follows and m.start == follows.end()), None)


def _nearest(text: str, hit: re.Match[str], conditions: list[Named], others: list[int]) -> Named | None:
    """The nearest condition before the number, else the nearest after it, never across a system noun,
    another value or a comparison word (a preceding mention's own head noun does not block)."""
    open_: list[tuple[int, int, Named]] = []
    for m, i in conditions:
        if m.end <= hit.start():
            head = HEAD_NOUN.match(text, m.end)
            a, b, side = head.end() if head else m.end, hit.start(), 0
        elif m.start >= hit.end():
            a, b, side = hit.end(), m.start, 1
        else:
            continue
        if SYSTEMS.search(text, a, b) or COMPARED.search(text, a, b) or any(a <= o < b for o in others):
            continue   # "RAG ... versus 62%", "71% over the closed-book model": a comparison, not this value's
        open_.append((side, _distance(hit, m), (m, i)))
    return min(open_, key=lambda t: (t[0], t[1]))[2] if open_ else None


FACTORIES = {"number_measurement": NumberMeasurement}
