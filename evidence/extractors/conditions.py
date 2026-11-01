"""`regex_condition_kind`: condition labels from configured names, for condition types without a `role`.

regex_condition writes `{label, role}` from fixed rag/baseline wording; the best and inventory-of-methods
protocols have condition types without a role (`{label, kind}`, `{label}`). This extractor finds the names it
is given instead: `kinds` (kind -> names; the engine injects best.kinds for a best protocol) or `names` (a plain
list, from the protocol step's config). A name matches case-insensitively, word-bounded, any run of white space
for a space; at one place the longest name wins. One item per name per paper (folded), labelled as first
written, with that first mention as its one `condition_label` span; `kind` is written when the kinds are given
and the type's schema has a `kind` field. It lives in its own module so every existing extractor keeps its id.
"""
from __future__ import annotations

import re
from typing import Any

from ..contract import ExtractionResult, ExtractionTask, ExtractorSpec, Item, RunContext
from . import base, regex

VERSION = 1
SOURCES = (base.HERE / "conditions.py", *base.SHARED_SOURCES)
CODE_SHA256 = base.source_sha256(*SOURCES)


def fold(name: str) -> str:
    return " ".join(name.split()).casefold()


def pattern(name: str) -> re.Pattern[str]:
    body = r"\s+".join(re.escape(word) for word in name.split())
    return re.compile(rf"(?i)(?<![\w-]){body}(?![\w-])")


class ConditionKindRegex:
    evidence_type, name = "condition", "regex_condition_kind"

    def __init__(self, config: dict[str, Any]) -> None:
        given = {k: v for k, v in config.items() if k in regex.INJECTED}
        kinds = {str(k): [str(n) for n in names] for k, names in (config.get("kinds") or {}).items()}
        names = [str(n) for n in config.get("names") or []]
        self.kind_of: dict[str, str | None] = {fold(n): None for n in names}
        for kind, members in kinds.items():
            for n in members:
                self.kind_of.setdefault(fold(n), kind)
        self.write_kind = bool(kinds) and "kind" in (given.get("field_schema") or {}).get("properties", {})
        # longest first, so that at one place "RAG without reranking" wins over "RAG"
        self.patterns = [pattern(n) for n in sorted(dict.fromkeys([*names, *(n for m in kinds.values() for n in m)]),
                                                    key=lambda n: (-len(n), n))]
        self.emits = base.emitted(given, self.evidence_type)
        self.spec = ExtractorSpec(name=self.name, version=VERSION, kind="regex", evidence_types=(self.emits,),
                                  code_sha256=CODE_SHA256, config={**given, "kinds": kinds, "names": names},
                                  determinism="exact")

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult:
        text = ctx.text()
        parts = base.ranges(task, text)
        hits: list[tuple[int, int, int]] = []   # start, -length, end
        for a, b in parts:
            for rx in self.patterns:
                hits += [(m.start(), -(m.end() - m.start()), m.end()) for m in rx.finditer(text, a, b)]
        first: dict[str, tuple[int, int]] = {}
        covered = -1
        for start, _, end in sorted(hits):
            if start < covered:
                continue
            covered = end
            first.setdefault(fold(text[start:end]), (start, end))
        found = []
        for key, (s, e) in sorted(first.items(), key=lambda kv: kv[1]):
            fields: dict[str, Any] = {"label": " ".join(text[s:e].split())}
            if self.write_kind and self.kind_of.get(key) is not None:
                fields["kind"] = self.kind_of[key]
            found.append((fields, {}, [base.span(task, text, s, e, "condition_label")]))
        items: list[Item] = base.group(self.emits, found)
        return ExtractionResult(extractor_id=self.spec.extractor_id, task_sha256=task.task_sha256, status="ok",
                                items=tuple(items), coverage=base.coverage(parts, items)).canonical()


FACTORIES = {"regex_condition_kind": ConditionKindRegex}
