"""The written answer (the after-run stage "written-answer"): the orch-model writes a short answer to the plan's main
question from numbered facts, code checks the reply, and code adds the paper ids.

This module holds the pure parts: which items become facts (`bears_on`, `fact_lines`: every paper gets its first fact
before any paper gets a second, within a share of the model's context window), the writer's input, the checks of a
reply (`check_written`), the answer text with its paper ids (`answer_text_of`) and the repair input. The writer sees the
main question only, never the plan's sub-questions."""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from modelcall.pins import ORCH_ALIAS

from .contract import Item
from .plan import Plan
from .planlines import OTHER, sides
from .planrun import ANY

__all__ = ["CHARS_PER_TOKEN", "FACT_SHARE", "FACT_TYPES", "MAX_QUOTE", "MAX_REPAIRS", "MAX_SENTENCES",
           "MAX_SENTENCE_CHARS", "NO_FACTS_TEXT", "PROMPT", "STAGE", "WRITER_ALIAS", "Fact", "Sentence", "WrittenReply",
           "answer_text_of", "bears_on", "check_written", "fact_budget", "fact_lines", "numbers", "repair_input",
           "writer_input"]

STAGE = "written-answer"
PROMPT = Path(__file__).parent / "stage_prompts" / "written-answer-v1.md"
WRITER_ALIAS = ORCH_ALIAS
MAX_SENTENCES = 8
MAX_SENTENCE_CHARS = 400
MAX_QUOTE = 200
MAX_REPAIRS = 1
CHARS_PER_TOKEN = 4
FACT_SHARE = 0.5          # the share of the writer's context window the facts may fill
FACT_TYPES = ("measurement", "author_claim", "claim")
NO_FACTS_TEXT = "No paper in this folder gave a fact that answers the question."
LINE_EXTRA = 16           # characters counted per fact on top of its text: "[n] S003 " and the line break
PAPER_ID = re.compile(r"\bS\d{3}\b")
THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def fact_budget(context_tokens: int) -> int:
    """The characters the facts may fill: FACT_SHARE of the context window, CHARS_PER_TOKEN characters a token."""
    return int(context_tokens * FACT_SHARE) * CHARS_PER_TOKEN


class Fact(BaseModel):
    """One numbered fact the writer sees (`n` from 1): the item it comes from, its paper, its type and its text."""
    n: int
    item: str
    paper: str
    type: str
    text: str


class Sentence(BaseModel):
    text: str
    says: Literal["finding", "cannot_tell"]
    facts: list[int]


class WrittenReply(BaseModel):
    sentences: list[Sentence]


# --- the facts ------------------------------------------------------------------------------------------------------

def _linked(item: Item, by_id: Mapping[str, Item], link: str) -> Item | None:
    return by_id.get(item.links.get(link, ""))


def _role(item: Item, by_id: Mapping[str, Item]) -> Any:
    condition = _linked(item, by_id, "condition")
    return condition.fields.get("role") if condition is not None else None


def _canonical(item: Item, by_id: Mapping[str, Item]) -> Any:
    metric = _linked(item, by_id, "metric")
    return metric.fields.get("canonical") if metric is not None else None


def _on_measure(item: Item, by_id: Mapping[str, Item], plan: Plan) -> bool:
    return not plan.measures or _canonical(item, by_id) in plan.measures


def _compared(item: Item, by_id: Mapping[str, Item], plan: Plan) -> bool:
    """A measurement of a compared thing on a plan measure: its role is one of the plan's things, or `any` when the
    plan names no compared thing (the plan run then gives the treatment role `any`)."""
    things = [t for t in sides(plan) if t not in (OTHER, ANY)]
    role = _role(item, by_id)
    return (role in things if things else role == ANY) and _on_measure(item, by_id, plan)


def bears_on(item: Item, by_id: Mapping[str, Item], plan: Plan) -> bool:
    """Whether an item of a paper (`by_id`: the paper's items by id) bears on the plan.

    A measurement bears on it when its linked condition's role is one of the plan's compared things (`any` when the
    plan names none: a one-measure question) and, when the plan has measures, its linked metric's canonical name is
    one of them. A measurement whose role is `other` bears on it as the comparison point: its metric is a plan measure
    (or the plan has none) and the same paper has a measurement of the first kind on the same canonical metric. An
    author claim or claim bears on it when its paper has a measurement of the first kind."""
    if item.evidence_type == "measurement":
        if _compared(item, by_id, plan):
            return True
        canonical = _canonical(item, by_id)
        return (_role(item, by_id) == OTHER and canonical is not None and _on_measure(item, by_id, plan)
                and any(it.evidence_type == "measurement" and _compared(it, by_id, plan)
                        and _canonical(it, by_id) == canonical for it in by_id.values()))
    if item.evidence_type in ("author_claim", "claim"):
        return any(it.evidence_type == "measurement" and _compared(it, by_id, plan) for it in by_id.values())
    return False


def _plain(value: Any) -> str:
    """A value as text; a float never in scientific form (0.00001, not 1e-05)."""
    if isinstance(value, float) and math.isfinite(value):
        return format(Decimal(repr(value)), "f")
    return str(value)


def _field(item: Item | None, name: str) -> str:
    value = item.fields.get(name) if item is not None else None
    return "?" if value is None or value == "" else _plain(value)


def _quote(item: Item) -> str:
    """The exact words of the item's value span (role "value"), else of its first span, cut at MAX_QUOTE."""
    span = next((s for s in item.spans if s.role == "value"), item.spans[0])
    return f'Quote: "{str(span.selector.get("exact", ""))[:MAX_QUOTE]}"'


def fact_text(item: Item, by_id: Mapping[str, Item]) -> str:
    """The text of one fact; a missing link or field reads `?`."""
    if item.evidence_type == "measurement":
        metric = _linked(item, by_id, "metric")
        better = metric.fields.get("higher_is_better") if metric is not None else None
        direction = f" ({'higher' if better else 'lower'} is better)" if isinstance(better, bool) else ""
        dataset = item.fields.get("dataset") or "no dataset named"
        return (f"{_field(_linked(item, by_id, 'condition'), 'label')} on {_field(metric, 'name')}{direction}: "
                f"{_field(item, 'value')}, {dataset}. {_quote(item)}")
    if item.evidence_type == "author_claim":
        return f"The authors say: {_field(item, 'direction')}. {_quote(item)}"
    return (f"{_field(item, 'subject')} {_field(item, 'relation')} {_field(item, 'object')} "
            f"({_field(item, 'strength')}). {_quote(item)}")


def fact_lines(by_paper: Mapping[str, list[Item]], plan: Plan, budget: int) -> tuple[list[Fact], dict[str, Any]]:
    """The facts the writer sees and the cut record. Each paper's facts that bear on the plan, in item order, are
    picked round-robin (every paper's 1st, then every paper's 2nd, ...) until the next would pass `budget` characters
    (each counted as its text plus LINE_EXTRA), then numbered in paper order, then item order."""
    pulled: dict[str, list[tuple[Item, str]]] = {}
    off_plan = 0
    for paper, items in by_paper.items():
        by_id = {it.item_id: it for it in items}
        pulled[paper] = []
        for it in items:
            if it.evidence_type not in FACT_TYPES:
                continue
            if bears_on(it, by_id, plan):
                pulled[paper].append((it, fact_text(it, by_id)))
            else:
                off_plan += 1
    taken = dict.fromkeys(pulled, 0)
    used, depth, full = 0, 0, False
    while not full and any(depth < len(rows) for rows in pulled.values()):
        for paper, rows in pulled.items():
            if depth >= len(rows):
                continue
            cost = len(rows[depth][1]) + LINE_EXTRA
            if used + cost > budget:
                full = True
                break
            used += cost
            taken[paper] += 1
        depth += 1
    facts = [Fact(n=0, item=it.item_id, paper=paper, type=it.evidence_type, text=text)
             for paper, rows in pulled.items() for it, text in rows[:taken[paper]]]
    facts = [f.model_copy(update={"n": i}) for i, f in enumerate(facts, 1)]
    cut = {"pulled": sum(len(rows) for rows in pulled.values()), "kept": len(facts),
           "left_out": {p: len(rows) - taken[p] for p, rows in pulled.items() if len(rows) > taken[p]},
           "off_plan": off_plan}
    return facts, cut


def writer_input(question: str, facts: list[Fact]) -> str:
    """The writer's task input: the main question and the numbered facts, one per line."""
    return f"Question: {question}\n\nFacts:\n" + "\n".join(f"[{f.n}] {f.paper} {f.text}" for f in facts)


# --- the checks -----------------------------------------------------------------------------------------------------

def numbers(text: str) -> list[float]:
    """The numbers of a text: paper ids removed first, then thousands commas; every `\\d+(?:\\.\\d+)?` read."""
    plain = THOUSANDS.sub("", PAPER_ID.sub(" ", text))
    return [float(x) for x in NUMBER.findall(plain)]


def _shown(x: float) -> str:
    return str(int(x)) if x.is_integer() else str(x)


def _number_ok(x: float, cited: list[Fact], asked: list[float]) -> bool:
    """`x` is a number of the cited facts' texts, or that number times or divided by 100, or a count from 1 to the
    number of cited facts, or a number of the question (`asked`: a year, a name with digits)."""
    if x.is_integer() and 1 <= x <= len(cited):
        return True
    if any(abs(x - y) < 1e-9 for y in asked):
        return True
    return any(abs(x - y) < 1e-9 or abs(x - y * 100) < 1e-9 or abs(x - y / 100) < 1e-9
               for f in cited for y in numbers(f.text))


def check_written(reply: WrittenReply, facts: list[Fact], question: str = "") -> list[str]:
    """The problems of a writer reply, each naming its sentence (from 1); [] when the reply is accepted. A number of
    `question` may be repeated in any sentence."""
    asked = numbers(question)
    problems: list[str] = []
    if not 1 <= len(reply.sentences) <= MAX_SENTENCES:
        problems.append(f"give 1 to {MAX_SENTENCES} sentences")
    by_n = {f.n: f for f in facts}
    seen: set[str] = set()
    for i, s in enumerate(reply.sentences, 1):
        said = " ".join(s.text.split()).casefold()
        if not said:
            problems.append(f"sentence {i}: empty")
            continue
        if len(s.text) > MAX_SENTENCE_CHARS:
            problems.append(f"sentence {i}: longer than {MAX_SENTENCE_CHARS} characters")
        if said in seen:
            problems.append(f"sentence {i}: said twice")
        seen.add(said)
        if s.says == "finding" and not s.facts:
            problems.append(f"sentence {i}: a finding cites at least one fact")
        if s.says == "cannot_tell" and s.facts:
            problems.append(f"sentence {i}: a cannot_tell sentence cites no fact")
        problems += [f"sentence {i}: fact {n} is not listed" for n in dict.fromkeys(s.facts) if n not in by_n]
        if PAPER_ID.search(s.text):
            problems.append(f"sentence {i}: leave paper ids out; the code adds them")
        cited = [by_n[n] for n in dict.fromkeys(s.facts) if n in by_n]
        bad = dict.fromkeys(_shown(x) for x in numbers(s.text) if not _number_ok(x, cited, asked))
        problems += [f"sentence {i}: the number {x} is in none of its facts" for x in bad]
    return problems


# --- the answer -----------------------------------------------------------------------------------------------------

def answer_text_of(reply: WrittenReply, facts: list[Fact]) -> tuple[str, list[dict[str, Any]]]:
    """The answer text (sentences joined by one space; a finding ends with its cited facts' papers in first-seen
    order, as " (S003, S010).") and one row per sentence {text, says, facts, papers}."""
    by_n = {f.n: f for f in facts}
    parts: list[str] = []
    rows: list[dict[str, Any]] = []
    for s in reply.sentences:
        papers = list(dict.fromkeys(by_n[n].paper for n in s.facts if n in by_n))
        text = s.text.strip()
        if s.says == "finding" and papers:
            text = f"{text.removesuffix('.')} ({', '.join(papers)})."
        parts.append(text)
        rows.append({"text": s.text.strip(), "says": s.says, "facts": list(s.facts), "papers": papers})
    return " ".join(parts), rows


def repair_input(first: str, rejected: WrittenReply, problems: list[str]) -> str:
    """The task input, the rejected reply as JSON, then the problems one per line."""
    # Mirrors synth3/asking.py repair_input: the engine (evidence) may not import synth3.
    return (f"{first}\n\nYour reply:\n{rejected.model_dump_json()}\n\nFix only these problems:\n"
            + "\n".join(problems))
