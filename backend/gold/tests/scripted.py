"""A scripted sub-model for the gold builder tests (pydantic-ai FunctionModel, no network).

It plays every stage from the prompt it gets, as the real model would see it:
- screen: a chunk is relevant when one of its paper's rules has its trigger in the chunk text;
- extract: the rows of those rules, each fact with the rule's quote (right, retyped, ambiguous or invented);
- retry: a new quote from `fixes` (rejected quote -> new quote), else the same quote again;
- triage: a label per fact from `labels` (object -> label), else "irrelevant".
`fail(stage, paper_id, part)` makes a call raise, as a dead server would (part is 1-based, None for
triage). `too_long(stage, text)` makes a call stop at max_tokens (a cut reply, finish_reason
"length"), as a chunk with too many facts does. Calls are counted per stage.

Quotes are from the D1 papers as agent/tests/conftest.write_corpus names them
(p3 = 2025-acl-long-625, p5 = 2025-acl-long-999, p6 = 2025-emnlp-main-1032).
"""
from __future__ import annotations

import json
import re
import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agent.tests.conftest import write_corpus
import modelcall
from gold.build import BuildSettings
from gold.chunks import GoldCorpus
from gold.screen import TEXT_END, TEXT_START

CONCEPTS = Path(__file__).resolve().parents[2] / "agent" / "concepts"
FIXTURES = Path(__file__).resolve().parents[2] / "agent" / "tests" / "fixtures"


def table_concept() -> dict[str, Any]:
    """dataset (Dataset), papers (list<Paper>), paper_count (integer)."""
    return json.loads((CONCEPTS / "rag-eval-datasets.json").read_text(encoding="utf-8"))


def graph_concept() -> dict[str, Any]:
    """Paper -evaluatesOn-> Dataset with a metric attribute."""
    return json.loads((FIXTURES / "concept_graph.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Rule:
    paper: str
    trigger: str                 # the rule fires in a chunk of `paper` that contains this text
    row: dict[str, Any]          # table cells, or edge fields
    facts: list[dict[str, Any]]  # {s, p, o, quote}


def table_rule(paper: str, trigger: str, dataset: str, quote: str) -> Rule:
    return Rule(paper, trigger, {"dataset": dataset, "papers": [paper], "paper_count": 1},
                [{"s": paper, "p": "evaluates on", "o": dataset, "quote": quote}])


# The table rules: right, retyped (whitespace), ambiguous (fixed by the retry), invented (not fixed),
# and partial_number (fixed). MMLU is in p3 and p5, so it merges into one row with paper_count 2.
GSM8K_OK = "math reasoning using GSM8K"
MMLU_RETYPED = "general reasoning   using\nMMLU"
GSM8K_AMBIGUOUS = "GSM8K (Cobbe et al., 2021)"
GSM8K_FIXED = "math reasoning on GSM8K (Cobbe et al., 2021)"
MMLU_P3 = "outperforms larger subsets on MMLU (Accuracy: 54.60)"
INVENTED = "we evaluate on HellaSwag with exact match"
HOTPOTQA = "and HotpotQA (Yang et al"
TABLE_RULES = [
    table_rule("p3", "outperforms larger subsets on MMLU", "MMLU", MMLU_P3),
    table_rule("p3", "HELLASWAG (Zellers et al., 2019) and MMLU", "HellaSwag", INVENTED),
    table_rule("p5", GSM8K_OK, "GSM8K", GSM8K_OK),
    table_rule("p5", "general reasoning using MMLU", "MMLU", MMLU_RETYPED),
    table_rule("p5", "math reasoning on GSM8K (Cobbe", "GSM8K", GSM8K_AMBIGUOUS),
    table_rule("p6", HOTPOTQA, "HotpotQA", HOTPOTQA),
]
FIXES = {GSM8K_AMBIGUOUS: GSM8K_FIXED}
LABELS = {"MMLU": "answers", "GSM8K": "answers", "HotpotQA": "context"}

GRAPH_RULES = [
    Rule("p6", HOTPOTQA, {"source": "p6", "source_type": "Paper", "predicate": "evaluatesOn", "target": "HotpotQA",
                          "target_type": "Dataset", "attributes": {"metric": None}},
         [{"s": "p6", "p": "evaluatesOn", "o": "HotpotQA", "quote": HOTPOTQA}]),
    Rule("p5", GSM8K_OK, {"source": "p5", "source_type": "Paper", "predicate": "evaluatesOn", "target": "GSM8K",
                          "target_type": "Dataset", "attributes": {"metric": None}},
         [{"s": "p5", "p": "evaluatesOn", "o": "GSM8K", "quote": GSM8K_OK}]),
    Rule("p5", "for GSM8K, we relied on exact match", {
        "source": "p5", "source_type": "Paper", "predicate": "evaluatesOn", "target": "gsm8k",
        "target_type": "Dataset", "attributes": {"metric": "exact match"}},
        [{"s": "p5", "p": "evaluatesOn", "o": "GSM8K", "quote": "for GSM8K, we relied on exact match scores"},
         {"s": "GSM8K", "p": "measured with", "o": "exact match", "quote": "for GSM8K, we relied on exact match"}]),
]


def _prompt(messages: list[Any]) -> str:
    """The user prompt of the run (an output retry's request carries none of its own)."""
    parts = [p.content for m in messages for p in getattr(m, "parts", []) if isinstance(p, UserPromptPart)]
    return parts[-1] if parts else ""


def _text(prompt: str) -> str:
    return prompt.split(TEXT_START + "\n", 1)[1].rsplit("\n" + TEXT_END, 1)[0]


def _paper(prompt: str) -> str:
    return re.search(r"^Paper: (\S+) \(file", prompt, re.M).group(1)


def _part(prompt: str) -> int:
    return int(re.search(r"^Paper: \S+ \(file \S+\), part (\d+) of", prompt, re.M).group(1))


@dataclass
class Script:
    rules: list[Rule] = field(default_factory=lambda: list(TABLE_RULES))
    fixes: dict[str, str] = field(default_factory=lambda: dict(FIXES))
    labels: dict[str, str] = field(default_factory=lambda: dict(LABELS))
    fail: Callable[[str, str | None, int | None], bool] | None = None
    too_long: Callable[[str, str], bool] | None = None
    calls: Counter = field(default_factory=Counter)

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

    def fired(self, prompt: str) -> list[Rule]:
        paper, text = _paper(prompt), " ".join(_text(prompt).split())
        return [r for r in self.rules if r.paper == paper and r.trigger in text]

    def reply(self, stage: str, prompt: str) -> dict[str, Any]:
        if stage == "screen":
            fired = self.fired(prompt)
            return {"relevant": bool(fired), "findings": [f"evaluates on {r.row.get('dataset') or r.row.get('target')}"
                                                          for r in fired]}
        if stage == "extract":
            rows = []
            for r in self.fired(prompt):
                fields = {"cells": dict(r.row)} if "source" not in r.row else dict(r.row)
                rows.append({**fields, "facts": [dict(f) for f in r.facts]})
            return {"rows": rows}
        if stage == "retry":
            listing = json.loads(prompt.split("Rejected quotes:\n", 1)[1].split("\n\n" + TEXT_START, 1)[0])
            return {"quotes": [{"id": q["id"], "quote": self.fixes.get(q["quote"], q["quote"])} for q in listing]}
        facts = json.loads(prompt)["facts"]
        return {"labels": [{"id": f["id"], "label": self.labels.get(f["object"], "irrelevant")} for f in facts]}

    def __call__(self, messages: list[Any], info: AgentInfo) -> ModelResponse:
        instructions = info.instructions or ""
        stage = ("screen" if instructions.startswith("You screen") else
                 "retry" if "quote check rejected" in instructions else
                 "extract" if instructions.startswith("You extract") else "triage")
        prompt = _prompt(messages)
        with self._lock:
            self.calls[stage] += 1
        paper, part = (_paper(prompt), _part(prompt)) if stage != "triage" else (None, None)
        if self.fail is not None and self.fail(stage, paper, part):
            raise RuntimeError(f"scripted failure: {stage} {paper}")
        if self.too_long is not None and self.too_long(stage, _text(prompt) if stage != "triage" else prompt):
            cut = '{"rows": [{"cells": {"dataset": "MM'
            if info.output_tools:
                return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, cut)], finish_reason="length")
            return ModelResponse(parts=[TextPart(cut)], finish_reason="length")
        reply = self.reply(stage, prompt)
        if info.output_tools:  # tool output mode
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, reply)])
        return ModelResponse(parts=[TextPart(json.dumps(reply))])  # native (JSON schema) output, as on LiteLLM

    def rotation(self) -> modelcall.Rotation:
        return modelcall.Rotation([FunctionModel(self, model_name=f"scripted-{n}") for n in (1, 2)])


def corpus(tmp_path: Path) -> GoldCorpus:
    root, manifest = write_corpus(tmp_path)
    return GoldCorpus(root, manifest)


SETTINGS = BuildSettings(concurrency=4, call_timeout_s=60)
