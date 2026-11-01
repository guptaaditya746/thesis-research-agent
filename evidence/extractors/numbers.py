"""`number_measurement`: number-first search for measurements (Part C, after regex, abbreviations and GLiNER).

regex_measurement starts from fixed sentence shapes ("71% for the baseline model"); this extractor starts
from every number in the task's parts and asks what is around it.

- A table cell: the condition is the row label and the metric the column header (or the other way round in a
  table whose rows are metrics); the dataset is the row's dataset column, else a context dataset item named in
  the column header or the caption, else null.
- A sentence: the condition named right after the number ("71% (TM)", "62% for the baseline model"), else
  the nearest one before it, else the nearest one after it; a condition is not taken across a system noun,
  another value or a comparison word ("versus", "over", "compared"), nor when another number already names it
  right after itself. The metric is the nearest one. The dataset is a context dataset item named in the
  sentence, else null.

Labels resolve to context items by measure.Resolver's rules (protocol wording, labels, codes the paper
defines: "baseline model (BM)") and also by the context items' own surface forms: the exact texts of their
spans, so an abbreviation item ("ER" for error rate) or a condition whose code an earlier extractor
quoted ("B") resolves in a table header, a row label or a sentence. A form that names two items is not used.
A measurement is emitted only when both a condition and a metric resolve.

Numbers are read by numreader.read_numbers (D35: one reader for every topic), which gives each its written form
(`fields["form"]`): plain, percent, fraction, k_of_n, range or plus_minus. Values: a % sign or a % metric header
makes a fraction (a % caption only for a fraction metric); a bare number between 1 and 100 is read as a
percentage only for the metrics in `fraction_metrics` (the pack's or the protocol's); any other metric keeps its
value as written, a time unit or a millisecond header giving seconds (units.py). A count "41 of 120" or "41/120"
is the fraction k/n, for a fraction metric only; its two numbers are the spans `value` (k) and `value_total` (n).
"0.61 ± 0.03" is 0.61. Integers need a % sign, a time unit or a count. Not values: deltas and differences ("by
4%", "+3.2 points", "9% higher", "0.45 s slower"), ranges and changes ("0.6-0.7", "between 0.6 and 0.7", "from
71% to 62%"), years, table, section and figure numbers, bare counts ("1,000 questions", "1.5 billion", "120
patients"), a count that sizes a sample ("200 out of 1,000 questions were sampled") and cells under a difference
header ("Δ Accuracy"). A percentage or a k-of-n count followed by a noun is a value ("34% of patients", "41 of 120
patients" respond): the reader no longer turns them away as shares or counts. Own module, so every existing
extractor keeps its id.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..contract import ExtractionResult, ExtractionTask, ExtractorSpec, Item, RunContext, Span, digest
from . import base, regex, terms, units
from .measure import DATASET_HEADER, DELTA_AFTER, DELTA_BEFORE, SIGNED, Found, Resolver, SystemNouns, sample_size
from .numreader import NumberSpan, read_numbers

VERSION = 1
SOURCES = (base.HERE / "numbers.py", base.HERE / "numreader.py", base.HERE / "measure.py", base.HERE / "terms.py",
           base.HERE / "units.py", base.HERE / "regex.py", *base.SHARED_SOURCES)   # regex.py: INJECTED; units.py: time units, ms header
CODE_SHA256 = base.source_sha256(*SOURCES)

UNIT = re.compile(r"\s?(ms|milliseconds?|s|secs?|seconds?)\b")   # a time unit right after a plain number
CELL_UNIT = re.compile(r"\s?(ms|s|secs?|seconds?)\s*$")           # ... closing a table cell
COUNTS: frozenset[str] = frozenset({"k_of_n", "fraction"})       # k / n: a value of a fraction metric only
SHARES: frozenset[str] = frozenset({"k_of_n", "percent"})        # a noun may follow ("34% of patients")
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
FOLLOWS = re.compile(r"\s*[(,–—-]?\s*(?:(?:for|with|by|of|from|in|using|on)\s+)?"
                     r"(?:the\s+|a\s+|an\s+|its\s+|our\s+)?")
DELTA_HEADER = re.compile(r"(?i)Δ|∆|\bdelta\b|\bdiff\w*|\bgain\b|\bimprove\w*|\bchange\b|\bvs\.?\b|\breduction\b")
COMPARED = re.compile(r"(?i)\b(?:over|than|versus|vs\.?|compared|relative|against|while|whereas|but|unlike)\b")
PROSE_EXCLUDED = frozenset({"A", "I"})   # one-letter forms that are ordinary words in a sentence

Named = tuple[terms.Mention, Item]


@dataclass(frozen=True)
class Hit:
    """A number read in a sentence: the reader's span and the time unit right after it (a plain number only).
    `start()` and `end()` (the unit included) as on a regex match, for the position helpers below."""
    n: NumberSpan
    unit: str | None
    unit_end: int

    def start(self) -> int:
        return self.n.start

    def end(self) -> int:
        return self.unit_end if self.unit else self.n.end


def _value_spans(task: ExtractionTask, text: str, n: NumberSpan, offset: int = 0) -> list[Span]:
    """The value's spans: its (first) number, the % sign included; for a count also `value_total` (n)."""
    (a, b), *rest = n.parts
    spans = [base.span(task, text, offset + a, offset + b, "value")]
    if n.form in COUNTS:
        spans.append(base.span(task, text, offset + rest[0][0], offset + rest[0][1], "value_total"))
    return spans


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
        self.emits = base.emitted(self.given, self.evidence_type)
        self.spec = ExtractorSpec(name=self.name, version=VERSION, kind="regex", evidence_types=(self.emits,),
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
                                            "treatment": treatment, "slots": base.Slots.of(self.given)})
        found: list[Found] = []
        if resolver.conditions and resolver.metrics:
            names = Surfaces(resolver)
            for table in base.tables(text):
                if any(a <= table.start and table.end <= b for a, b in parts):
                    found.extend(self._table(task, text, table, names, datasets))
            numbers = read_numbers(text)
            for a, b in parts:
                for s, e in base.sentences(text, a, b):
                    inside = [n for n in numbers if s <= n.start and n.end <= e]
                    found.extend(self._sentence(task, text, s, e, inside, names, datasets))
        items: list[Item] = base.group(self.emits, _one_form(found))
        return ExtractionResult(extractor_id=self.spec.extractor_id, task_sha256=task.task_sha256, status="ok",
                                items=tuple(items), coverage=base.coverage(parts, items)).canonical()

    # values ----------------------------------------------------------------------------------------------

    def _value(self, n: NumberSpan, metric: Item, *, percent: bool, unit: str | None) -> float | None:
        """The number as the protocol stores it, or None when it cannot be a value of this metric. `percent`:
        the header or caption marks the number as a percentage (a % sign in the text the reader has applied)."""
        fraction = metric.fields.get("canonical") in self.fractions
        if n.form in COUNTS:   # k / n, at most 1 by construction: a share, so a fraction metric's value
            return n.value if fraction else None
        if n.form == "range":
            return None
        if unit is not None:   # a time: only for a metric that is not a fraction
            return None if fraction else round(n.value / (1000 if unit.startswith("m") else 1), 6)
        written = "%" in n.raw
        value = n.value if written else base.to_fraction(str(n.value), percent=percent, rate_like=fraction)
        if value is None or (fraction or percent or written) and value > 1:
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
                held = _cell_number(cell.text)
                if held is None:
                    continue
                number, unit = held
                if unit is None:
                    # a % caption speaks for the table's rates, not for a latency column beside them
                    pct = _percent(metric_cell.text) or fraction and _percent(table.caption)
                    ms = units.MS_HEADER.search(col.text) or units.MS_HEADER.search(label[1].text)
                    unit = "ms" if ms and not fraction and number.form == "plain" else None
                else:
                    pct = False
                item, defined = condition
                value = self._value(number, metric, percent=pct, unit=unit)
                if value is None:
                    continue
                spans = [*_value_spans(task, text, number, cell.start),
                         base.span(task, text, cond_cell.start, cond_cell.end, "condition_label"),
                         base.span(task, text, metric_cell.start, metric_cell.end, "metric_label")]
                if defined is not None:
                    spans.append(base.span(task, text, *defined, "condition_label"))
                dataset = row_dataset or _named(col.text, datasets) or caption_dataset
                out.append(({"value": value, "dataset": dataset, "form": number.form},
                            r.r.slots.links(item, metric), spans))
        return out

    # sentences -------------------------------------------------------------------------------------------

    def _sentence(self, task: ExtractionTask, text: str, s: int, e: int, numbers: list[NumberSpan], r: Surfaces,
                  datasets: list[str]) -> list[Found]:
        conditions = r.condition_mentions(text, s, e)
        metrics = r.metric_mentions(text, s, e)
        if not conditions or not metrics:
            return []
        hits = [h for h in (_hit(text, n, e) for n in numbers) if self._candidate(text, s, e, h)]
        rights = [_right(text, h, conditions) for h in hits]
        claimed = {(c[0].start, c[0].end) for c in rights if c is not None}   # named right after another number
        free = [c for c in conditions if (c[0].start, c[0].end) not in claimed]
        dataset = _named(text[s:e], datasets)
        out: list[Found] = []
        for n, hit in enumerate(hits):
            others = [h.start() for h in hits if h is not hit]
            cond = rights[n] or _nearest(text, hit, free, others, r.r.nouns)
            unit = hit.unit
            usable = [(m, i) for m, i in metrics if unit is None or i.fields.get("canonical") not in self.fractions]
            met = min(usable, key=lambda mi: (_distance(hit, mi[0]), mi[0].start), default=None)
            if cond is None or met is None:
                continue
            value = self._value(hit.n, met[1], percent=False, unit=unit)
            if value is None:
                continue
            spans = [*_value_spans(task, text, hit.n),
                     base.span(task, text, cond[0].start, cond[0].end, "condition_label"),
                     base.span(task, text, met[0].start, met[0].end, "metric_label")]
            out.append(({"value": value, "dataset": dataset, "form": hit.n.form},
                        r.r.slots.links(cond[1], met[1]), spans))
        return out

    def _candidate(self, text: str, s: int, e: int, hit: Hit) -> bool:
        """A number that can be a reported value: not part of a longer token, a delta, a range, a year, a
        reference, a bare count, a sample size or (a plain number) a share."""
        n, unit = hit.n, hit.unit
        if n.form == "range":
            return False   # "between 0.6 and 0.7", "0.6-0.7", "from 71% to 62%"
        if GLUED.match(text, hit.end()) and hit.end() < e:
            return False
        integer = n.form == "plain" and "." not in n.raw
        if integer and not unit:
            return False   # a bare integer: a count, a year, a k
        if integer and 1900 <= n.value <= 2099:
            return False   # a year ("the 1990s")
        before, after = text[max(s, hit.start() - 25):hit.start()], text[hit.end():e]
        if (DELTA_BEFORE.search(before) or SIGNED.search(before) or CHANGE_BEFORE.search(before)
                or REFERENCE_BEFORE.search(before)):
            return False
        if DELTA_AFTER.match(after) or CHANGE_AFTER.match(after):
            return False
        if n.form in COUNTS and sample_size(text, s, e, hit):  # type: ignore[arg-type]
            return False   # "200 out of 1,000 questions were sampled"
        if n.form in SHARES:
            return True    # D35: "34% of patients", "41 of 120 patients" are results
        return not (COUNT_AFTER.match(after) or SHARE_AFTER.match(after))   # "1.5 billion", "0.4 of the questions"


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

def _one_form(found: list[Found]) -> list[Found]:
    """`form` is not identity: findings equal but for it (the same value as "71%" in prose and "71.0" in a table)
    all take the form of the one whose value span comes first, so base.group makes them one item."""
    def same(f: Found) -> str:
        return digest([{k: v for k, v in f[0].items() if k != "form"}, f[1]])

    def first(f: Found) -> int:
        return min(s.selector["start"] for s in f[2] if s.role == "value")

    form: dict[str, Any] = {}
    for f in sorted(found, key=first):
        form.setdefault(same(f), f[0].get("form"))
    return [({**fields, "form": form[same((fields, links, spans))]}, links, spans) for fields, links, spans in found]


def _hit(text: str, n: NumberSpan, e: int) -> Hit:
    """The number with the time unit right after it, for a plain number."""
    unit = UNIT.match(text, n.end, e) if n.form == "plain" else None
    return Hit(n, unit.group(1) if unit else None, unit.end() if unit else n.end)


def _cell_number(cell: str) -> tuple[NumberSpan, str | None] | None:
    """The one number a table cell holds (bold and italic marks allowed around it), offsets within the cell,
    with the time unit closing the cell; None for any other cell (text, two numbers, a range)."""
    bare = re.sub(r"[*_]", " ", cell)   # same length: the reader's offsets stay the cell's
    found = read_numbers(bare)
    if len(found) != 1 or found[0].form == "range" or bare[:found[0].start].strip():
        return None
    rest = bare[found[0].end:]
    if not rest.strip():
        return found[0], None
    unit = CELL_UNIT.fullmatch(rest) if found[0].form == "plain" else None
    return (found[0], unit.group(1)) if unit else None

def _percent(label: str) -> bool:
    return "%" in label or "percent" in label.casefold()


def _named(text: str, names: list[str]) -> str | None:
    """The first dataset name (a context item's) that occurs in `text` as a whole word."""
    found = [(m.start(), n) for n in names for m in [re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text)] if m]
    return min(found)[1] if found else None


def _distance(hit: re.Match[str], m: terms.Mention) -> int:
    return hit.start() - m.end if m.end <= hit.start() else m.start - hit.end()


def _right(text: str, hit: re.Match[str], conditions: list[Named]) -> Named | None:
    """The condition named right after the number: "71% (TM)", "62% for the baseline model"."""
    follows = FOLLOWS.match(text, hit.end())
    return next(((m, i) for m, i in conditions if follows and m.start == follows.end()), None)


def _nearest(text: str, hit: re.Match[str], conditions: list[Named], others: list[int],
             nouns: SystemNouns) -> Named | None:
    """The nearest condition before the number, else the nearest after it, never across a system noun,
    another value or a comparison word (a preceding mention's own head noun does not block)."""
    open_: list[tuple[int, int, Named]] = []
    for m, i in conditions:
        if m.end <= hit.start():
            head = nouns.head.match(text, m.end)
            a, b, side = head.end() if head else m.end, hit.start(), 0
        elif m.start >= hit.end():
            a, b, side = hit.end(), m.start, 1
        else:
            continue
        if nouns.systems.search(text, a, b) or COMPARED.search(text, a, b) or any(a <= o < b for o in others):
            continue   # "TM ... versus 62%", "71% over the baseline model": a comparison, not this value's
        open_.append((side, _distance(hit, m), (m, i)))
    return min(open_, key=lambda t: (t[0], t[1]))[2] if open_ else None


FACTORIES = {"number_measurement": NumberMeasurement}
