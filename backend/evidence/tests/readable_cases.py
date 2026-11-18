"""Builders for the readable program's tests: a protocol and a plan's names, paper items, and a run's answer made by
the engine (so a rebuild can be compared with it)."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from evidence import kinds
from evidence.contract import Item, Span
from evidence.kindtext import plan_names
from evidence.plan import with_answer
from evidence.plankinds import kind_protocol
from evidence.protocol import Protocol, parse
from evidence.readable.runview import RunAnswer
from evidence.tests.test_plan_run import make_plan

RULES_LINE = "# --- rules ---"
DROP_MARK = "# program: drop"
NAMES = plan_names(make_plan())


def case_protocol(by: str = "effect", target: str | None = None, direction: str = "higher") -> Protocol:
    """The protocol a plan run makes for answer kind `by` (rag against closed_book on accuracy)."""
    plan = with_answer(make_plan(direction=direction), by, target)
    return parse(kind_protocol(plan).decode("utf-8"))


def item(type: str, fields: dict[str, Any], links: dict[str, str] | None = None, paper: str = "S001",
         exact: str = "0.5", start: int = 0, role: str = "value") -> Item:
    """An item with one span of role `role` in papers/<paper>.md at `start`, quoting `exact`."""
    selector = {"file": f"papers/{paper}.md", "start": start, "end": start + len(exact), "exact": exact}
    return Item.build(type, fields, [Span(role=role, selector=selector)], links=links)


def study_items(paper: str, t: Any, c: Any, *, claim: str | None = None, dataset: str | None = None,
                t_label: str = "Method K", c_label: str = "Usual method", start: int = 0) -> list[Item]:
    """One paper's items: a `rag` condition and a `closed_book` condition, the metric `accuracy` (named "Yield",
    higher is better), a measurement on each, and optionally an author claim. `t` None leaves out the treatment's
    value and condition, `c` None the control's."""
    out: list[Item] = []
    metric = item("metric", {"name": "Yield", "canonical": "accuracy", "higher_is_better": True}, paper=paper,
                  exact="Yield", start=start + 20)
    out.append(metric)
    sides = ((t, t_label, "rag", start), (c, c_label, "closed_book", start + 50))
    for number, (value, label, role, at) in enumerate(sides):
        if value is None:
            continue
        thing = item("condition", {"label": label, "role": role}, paper=paper, exact=label, start=at)
        measured = item("measurement", {"value": value, "dataset": dataset},
                        {"condition": thing.item_id, "metric": metric.item_id}, paper=paper, exact=str(value),
                        start=start + 100 + 100 * number)
        out += [thing, measured]
    if claim is not None:
        out.append(item("author_claim", {"direction": claim}, paper=paper, exact="Method K improves the yield.",
                        start=start + 400))
    return out


def case_answer(protocol: Protocol, by_paper: dict[str, list[Item]], kind: str,
                names: dict[str, str] = NAMES) -> RunAnswer:
    """The engine's answer for `by_paper` wrapped as a run's answer (no folder, no plan, no paper texts)."""
    answer, _ = kinds.of(protocol).answer(protocol, list(by_paper), by_paper, roles=protocol.roles())
    return RunAnswer(run=Path("case"), kind=kind, protocol=protocol, roles=protocol.roles(), plan=None, names=names,
                     answer=answer, items=by_paper, texts=None, record={}, outputs={}, inferred=None)


def stdlib_only(path: Path) -> set[str]:
    """The top-level modules a rule file imports once its `# program: drop` lines are removed."""
    lines = path.read_text(encoding="utf-8").split("\n")
    assert sum(line == RULES_LINE for line in lines) == 1, f"{path.name} needs exactly one {RULES_LINE} line"
    kept = [line for line in lines if not line.rstrip().endswith(DROP_MARK)]
    found: set[str] = set()
    for node in ast.walk(ast.parse("\n".join(kept))):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found
