"""Measurements for the regex extractor: values in sentences and in Markdown tables, linked to the
condition and metric items of the task's context.

A label is matched to a context condition by a code the text defines ("variant (R)"), by its label, or
by condition wording covering the whole label; to a context metric by name, or by its canonical metric
when only one context metric has it. A value without both links is not reported (R2 requires them).

In a sentence, a value belongs to the condition named right after it ("62% for the baseline model"),
else to the nearest condition named before it, but never across another system noun or another number
("71%, while a fine-tuned model reaches 57%": 57% is nobody's). Signed numbers ("+9%") are deltas and
"from 62% to 71%" is a change, not two results; neither gives a value.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any, NamedTuple

from ..contract import ExtractionTask, Item, Span
from . import base, numreader, terms

Found = tuple[dict[str, Any], dict[str, str], list[Span]]
CELL = re.compile(r"^[*_]*\s*(\d+(?:\.\d+)?|\.\d+)\s*(%?)\s*[*_]*(?:\s*(?:±|\+/-|\+-)\s*\d+(?:\.\d+)?)?\s*[*_]*$")
AFTER = re.compile(r"\s*\)?\s*,?\s*(?:for|with|by|of|from|in|using)\s+(?:the\s+|a\s+|an\s+|its\s+|our\s+)?")
DELTA_BEFORE = re.compile(r"(?i)\b(?:by|of\s+up\s+to|gains?\s+of|improvement\s+of|drop\s+of)\s*$")
DELTA_AFTER = re.compile(r"(?i)^\s*(?:percentage\s+)?(?:points?|pp)\b")
DATASET_HEADER = re.compile(r"(?i)^(?:dataset|benchmark|data|task)$")
CONDITION_HEADER = re.compile(r"(?i)^(?:system|model|method|condition|variant|setting)$")
SAMPLE_BEFORE = re.compile(r"(?i)\b(sampl\w*|evaluat\w*|subsets?|drawn|test\s+sets?)\b[^.;]{0,40}$")   # a sample size, no outcome
RESULT_VERB = re.compile(r"(?i)\b(?:answer\w*|scor\w*|achiev\w*|obtain\w*|reach\w*|got|gets?|correct\w*)\b")   # an outcome follows
CORRECT_AFTER = re.compile(r"(?i)^\s*(?:\w+\s+){0,3}correct")
SAMPLE_AFTER = re.compile(r"(?i)^\s*(?:\w+\s+){0,3}?(?:were|are|was)\s+(?:randomly\s+)?(?:sampled|selected|drawn|chosen|used)\b")
SIGNED = re.compile(r"[+±\-−–]\s*$")
FROM_TO = re.compile(r"(?i)\bfrom\s+\d+(?:\.\d+)?\s*%?\s+to\s+\d+(?:\.\d+)?\s*%?")
_SYSTEMS = r"(?:model|system|variant|baseline|pipeline|generator|approach|method|LLM|reader|retriever|ablation)s?"
BLOCKERS = re.compile(r"\d|(?i:\b" + _SYSTEMS + r"\b)")
HEAD_NOUN = re.compile(r"(?i:\s+" + _SYSTEMS + r"\b)")


class Resolver:
    """Labels and mentions to context item ids."""

    def __init__(self, text: str, context: list[Item], patterns: dict[str, Any]) -> None:
        self.text = text
        self.cond_patterns = terms.condition_patterns(patterns["conditions"])
        self.roles = [*patterns["conditions"], "other"]   # a mention qualified as other links only to an other item
        self.treatment = patterns.get("treatment")
        self.not_a_system = patterns["not_a_system"]
        self.metric_patterns = [tuple(m) for m in patterns["metrics"]]
        self.question = set(patterns["question_metrics"])
        self.slots: base.Slots = patterns.get("slots") or base.Slots()   # which context types, which links
        self.conditions = [i for i in context if i.evidence_type == self.slots.thing]
        self.metrics = [i for i in context if i.evidence_type == self.slots.metric]
        self.codes: dict[str, tuple[Item, tuple[int, int]]] = {}
        for mention, code, a, b in terms.aliases(text, self.mentions(text)):
            item = self.condition_for(mention)
            if item is not None and code not in self.codes:
                self.codes[code] = (item, (a, b))

    def condition_for(self, mention: terms.Mention) -> Item | None:
        same = [i for i in self.conditions if i.fields.get("role") == mention.key]
        if len(same) == 1:
            return same[0]
        named = [i for i in same if terms.norm(str(i.fields.get("label", ""))) == terms.norm(mention.text)]
        return named[0] if len(named) == 1 else None

    def condition_label(self, label: str) -> tuple[Item, tuple[int, int] | None] | None:
        """A table label as a condition: a defined code, an item's label, or wording covering the label."""
        label = label.strip(" *_")
        if label in self.codes:
            item, where = self.codes[label]
            return item, where
        for item in self.conditions:
            if terms.norm(str(item.fields.get("label", ""))) == terms.norm(label):
                return item, None
        found = self.mentions(label)
        if len(found) == 1 and found[0].start == 0 and found[0].end == len(label):
            item = self.condition_for(found[0])
            return (item, None) if item is not None else None
        return None

    def mentions(self, text: str, start: int = 0, end: int | None = None) -> list[terms.Mention]:
        """Condition mentions with their qualifiers: "TM (no tuning)" is the control, not TM."""
        return terms.find_conditions(text, self.cond_patterns, self.roles, start, end, self.treatment,
                                     not_a_system=self.not_a_system)

    def metric_for(self, mention: terms.Mention) -> Item | None:
        named = [i for i in self.metrics if terms.norm(str(i.fields.get("name", ""))) == terms.norm(mention.text)]
        if named:
            return named[0]
        same = [i for i in self.metrics if i.fields.get("canonical") == mention.key]
        return same[0] if len(same) == 1 else None

    def metric_label(self, label: str) -> Item | None:
        found = terms.find_all(label, self.metric_patterns)  # type: ignore[arg-type]
        return self.metric_for(found[0]) if found else None

    def rate_like(self, metric: Item) -> bool:
        return metric.fields.get("canonical") in self.question


def measurements(task: ExtractionTask, text: str, parts: list[tuple[int, int]], context: list[Item],
                 patterns: dict[str, Any]) -> list[Found]:
    resolver = Resolver(text, context, patterns)
    if not resolver.conditions or not resolver.metrics:
        return []
    inside = [t for t in base.tables(text) if any(a <= t.start and t.end <= b for a, b in parts)]
    found = [f for t in inside for f in _table(task, text, t, resolver)]
    for a, b in parts:
        for s, e in base.sentences(text, a, b):
            found.extend(_sentence(task, text, s, e, resolver))
    return found


class TableRoles(NamedTuple):
    """Column roles of a table: where the condition, the metric and the dataset are named; the rest hold values."""
    condition_col: int | None
    metric_col: int | None
    dataset_col: int | None


def _table_roles(header: Sequence[base.Cell], rows: Sequence[Sequence[base.Cell]], r: Resolver) -> TableRoles:
    """A condition column by its header, else the first column (not the dataset's) where half the cells
    resolve as conditions; a metric column by its cells likewise. Without either, the header cells name them."""
    dataset = next((n for n, c in enumerate(header) if DATASET_HEADER.match(c.text.strip(" *_"))), None)

    def mostly(col: int, label: Callable[[str], Any]) -> bool:
        cells = [row[col] for row in rows if col < len(row)]
        return bool(cells) and 2 * sum(label(c.text) is not None for c in cells) >= len(cells)

    columns = [n for n in range(len(header)) if n != dataset]
    condition = next((n for n in columns if CONDITION_HEADER.match(header[n].text.strip(" *_"))
                      and any(n < len(row) and r.condition_label(row[n].text) for row in rows)), None)  # a header alone is not enough
    if condition is None:
        condition = next((n for n in columns if mostly(n, r.condition_label)), None)
    metric = next((n for n in columns if n != condition and mostly(n, r.metric_label)), None)
    return TableRoles(condition, metric, dataset)


def _table(task: ExtractionTask, text: str, table: base.Table, r: Resolver) -> list[Found]:
    header = table.header
    condition_col, metric_col, dataset_col = _table_roles(header, table.rows, r)
    if condition_col is None and metric_col is None:
        return []
    percent_table = "%" in table.caption or "percent" in table.caption.casefold()
    out: list[Found] = []
    for row in table.rows:
        if not row:
            continue
        dataset = row[dataset_col].text.strip(" *_") or None if dataset_col is not None and dataset_col < len(row) else None
        row_condition = r.condition_label(row[condition_col].text) if condition_col is not None and condition_col < len(row) else None
        row_metric = r.metric_label(row[metric_col].text) if metric_col is not None and metric_col < len(row) else None
        if condition_col is not None and row_condition is None or metric_col is not None and row_metric is None:
            continue
        for n, cell in enumerate(row):
            if n >= len(header) or n in (condition_col, metric_col, dataset_col):
                continue
            hit = CELL.match(cell.text)
            if not hit:
                continue
            col = header[n]
            condition = row_condition if condition_col is not None else r.condition_label(col.text)
            metric = row_metric if metric_col is not None else r.metric_label(col.text)
            if condition is None or metric is None:
                continue
            item, defined = condition
            label_cell = row[condition_col] if condition_col is not None else col
            metric_cell = row[metric_col] if metric_col is not None else col
            role_cell = row[condition_col if condition_col is not None else metric_col]
            value = base.to_fraction(hit.group(1) + hit.group(2), rate_like=r.rate_like(metric),
                                     percent=percent_table or "%" in col.text or "%" in role_cell.text)
            if value is None:
                continue
            a = cell.start + hit.start(1)
            b = cell.start + (hit.end(2) if hit.group(2) else hit.end(1))
            spans = [base.span(task, text, a, b, "value"),
                     base.span(task, text, label_cell.start, label_cell.end, "condition_label"),
                     base.span(task, text, metric_cell.start, metric_cell.end, "metric_label")]
            if defined is not None:
                spans.append(base.span(task, text, *defined, "condition_label"))
            out.append(({"value": value, "dataset": dataset}, r.slots.links(item, metric), spans))
    return out


def sample_size(text: str, s: int, e: int, hit: re.Match[str]) -> bool:
    """A count that sizes a sample, not an outcome: a result verb between the trigger and the count, or
    "correct(ly)" after it, keeps it a result."""
    if CORRECT_AFTER.match(text[hit.end():e]):
        return False
    window = text[max(s, hit.start() - 40):hit.start()]
    trigger = SAMPLE_BEFORE.search(window)
    if trigger and not RESULT_VERB.search(window, trigger.end(1)):
        return True
    return bool(SAMPLE_AFTER.match(text[hit.end():e]))


def _sentence(task: ExtractionTask, text: str, s: int, e: int, r: Resolver) -> list[Found]:
    conditions = [(m, r.condition_for(m)) for m in r.mentions(text, s, e)]
    conditions = [(m, i) for m, i in conditions if i is not None]
    metrics = [(m, r.metric_for(m)) for m in terms.find_all(text, r.metric_patterns, s, e)]  # type: ignore[arg-type]
    metrics = [(m, i) for m, i in metrics if i is not None]
    if not conditions or not metrics:
        return []
    out: list[Found] = []
    changes = [(m.start(), m.end()) for m in FROM_TO.finditer(text, s, e)]
    counts = list(numreader.COUNT.finditer(text, s, e))
    numbers = [h for h in base.NUMBER.finditer(text, s, e) if not any(c.start() <= h.start() < c.end() for c in counts)]
    for hit in sorted([*numbers, *counts], key=lambda h: h.start()):
        count = hit.re is numreader.COUNT
        raw, pct = hit.group(1), (not count and bool(hit.group(2)))
        if not count and not pct and not ("." in raw and float(raw) <= 1):
            continue
        before = text[max(s, hit.start() - 20):hit.start()]
        if DELTA_BEFORE.search(before) or DELTA_AFTER.match(text[hit.end():e]) or SIGNED.search(before):
            continue
        if any(a <= hit.start() < b for a, b in changes):
            continue
        after = AFTER.match(text, hit.end(), e)
        following = next(((m, i) for m, i in conditions if after and m.start == after.end()), None)
        preceding = [(m, i) for m, i in conditions if m.end <= hit.start()]
        head = HEAD_NOUN.match(text, preceding[-1][0].end) if preceding else None   # the mention's own noun
        if preceding and BLOCKERS.search(text, head.end() if head else preceding[-1][0].end, hit.start()):
            preceding = []   # another system or another number stands between: the value is not its
        cond = following or (preceding[-1] if preceding else None)
        before_metrics = [(m, i) for m, i in metrics if m.end <= hit.start()]
        met = before_metrics[-1] if before_metrics else next(((m, i) for m, i in metrics if m.start >= hit.end()), None)
        if cond is None or met is None:
            continue
        if count and sample_size(text, s, e, hit):
            continue
        if count:
            value = numreader.count_fraction(raw, hit.group(2)) if r.rate_like(met[1]) else None
        else:
            value = base.to_fraction(raw + ("%" if pct else ""), percent=pct, rate_like=r.rate_like(met[1]))
        if value is None:
            continue
        end = hit.end() if count else hit.end(2) if pct else hit.end(1)
        spans = [base.span(task, text, hit.start(1), end, "value"),
                 base.span(task, text, cond[0].start, cond[0].end, "condition_label"),
                 base.span(task, text, met[0].start, met[0].end, "metric_label")]
        out.append(({"value": value, "dataset": None}, r.slots.links(cond[1], met[1]), spans))
    return out
