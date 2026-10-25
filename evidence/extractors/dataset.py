"""Dataset extractors: `regex_dataset` (this module) and `llm_dataset` (the generic LLM extractor).

They live here, not in regex.py and llm.py, so that adding them leaves the code hash (and so the id) of
every existing regex and LLM extractor unchanged.

`regex_dataset` finds benchmark-like tokens (TriviaCheck, LawFactQA) and any names given in the config; one
item `{"name"}` per distinct name, with the first mention as its `dataset_label` span.
"""
from __future__ import annotations

import re
from typing import Any

from ..contract import ExtractionResult, ExtractionTask, ExtractorSpec, Item, RunContext
from . import base, llm, regex

VERSION = 1
SOURCES = (base.HERE / "dataset.py", *base.SHARED_SOURCES)
CODE_SHA256 = base.source_sha256(*SOURCES)
DEFAULT_PATTERN = r"\b[A-Z][A-Za-z]+(?:QA|Bench|Set|Facts|Check|Quest)\b"


class DatasetRegex:
    evidence_type, name = "dataset", "regex_dataset"

    def __init__(self, config: dict[str, Any]) -> None:
        given = {k: v for k, v in config.items() if k in regex.INJECTED}
        names = config.get("names") or []
        pattern = config.get("pattern") or DEFAULT_PATTERN
        self.names = [str(n) for n in names]
        self.pattern = re.compile(pattern)
        self.named = [re.compile(rf"(?<!\w){re.escape(n)}(?!\w)") for n in self.names]
        self.spec = ExtractorSpec(name=self.name, version=VERSION, kind="regex", evidence_types=("dataset",),
                                  code_sha256=CODE_SHA256, config={**given, "names": self.names, "pattern": pattern},
                                  determinism="exact")

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult:
        text = ctx.text()
        parts = base.ranges(task, text)
        hits: list[tuple[int, int]] = []
        for a, b in parts:
            for rx in (self.pattern, *self.named):
                hits += [(a + m.start(), a + m.end()) for m in rx.finditer(text[a:b])]
        first: dict[str, tuple[int, int]] = {}
        for start, end in sorted(set(hits)):
            first.setdefault(text[start:end], (start, end))
        items: list[Item] = base.group("dataset", [
            ({"name": name}, {}, [base.span(task, text, s, e, "dataset_label")]) for name, (s, e) in first.items()])
        return ExtractionResult(extractor_id=self.spec.extractor_id, task_sha256=task.task_sha256, status="ok",
                                items=tuple(items), coverage=base.coverage(parts, items)).canonical()


FACTORIES = {"regex_dataset": DatasetRegex, "llm_dataset": llm._factory("dataset")}
