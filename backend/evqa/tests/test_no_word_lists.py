"""Q2b guard: no hard-coded natural-language word lists in the pipeline, the scorer, norm.py or lm.py.

Scans the source with `ast`: any set, tuple, list or dict literal holding >= 3 word strings (letters, spaces,
apostrophes, hyphens; no underscores, digits or symbols) fails, unless every one of those strings is allowed.
Dict keys are not counted: they are the keys of a JSON record (schema), not vocabulary; dict values are. `__all__`
lists are Python names. Allowed strings:
  - a contract field name or a contract Literal value (evqa/contracts.py): structure, not domain words;
  - an entry of ALLOWED below, each with a one-line reason.
Strings in docstrings and prompts are not literals of a collection, so prompt text is not affected.
"""
from __future__ import annotations

import ast
import re
import typing
from pathlib import Path

import pytest
from pydantic import BaseModel

from evqa import contracts

PKG = Path(__file__).resolve().parents[1]
SCANNED = ["spec", "find", "extract", "answer", "eval", "norm.py", "lm.py"]
WORD = re.compile(r"[A-Za-z]+(?:[ '\-][A-Za-z]+)*")
MIN_WORDS = 3

# string -> reason (keep short; add only structure, never domain vocabulary)
ALLOWED: dict[str, str] = {
    "find": "pipeline step name (prism LAYERS)",
    "extract": "pipeline step name (prism LAYERS)",
    "answer": "pipeline step name (prism LAYERS)",
    "conflict": "benchmark question type (gold files)",
    "absent": "benchmark question type (gold files)",
    "contexts": "blueprint section key (data/seed/<domain>/blueprint)",
    "measures": "blueprint section key",
    "items": "blueprint section key",
    "matches": "label-judge verdict (eval/judge.py output enum)",
    "does not match": "label-judge verdict",
    "unclear": "label-judge verdict",
}


def contract_strings() -> set[str]:
    """Field names and Literal values of every contract model (they name structure, not domain things)."""
    out: set[str] = set()

    def literals(tp: object) -> None:
        if typing.get_origin(tp) is typing.Literal:
            out.update(a for a in typing.get_args(tp) if isinstance(a, str))
        for a in typing.get_args(tp):
            literals(a)
    for obj in vars(contracts).values():
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
            for name, f in obj.model_fields.items():
                out.add(name)
                literals(f.annotation)
    for obj in vars(contracts).values():
        literals(obj)
    return out


def files() -> list[Path]:
    out: list[Path] = []
    for s in SCANNED:
        p = PKG / s
        out += sorted(p.rglob("*.py")) if p.is_dir() else [p]
    return [p for p in out if "__pycache__" not in p.parts]


def word_strings(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Dict):
        items = list(node.values)
    elif isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        items = node.elts
    else:
        return []
    return [n.value for n in items if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and WORD.fullmatch(n.value)]


def offenders() -> list[str]:
    allowed = contract_strings() | set(ALLOWED)
    out = []
    for path in files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets)}
        for node in ast.walk(tree):
            if id(node) in skip:
                continue
            words = word_strings(node)
            bad = [w for w in words if w not in allowed]
            if len(words) >= MIN_WORDS and bad:
                out.append(f"{path.relative_to(PKG)}:{node.lineno}: {len(words)} words, e.g. {bad[:5]}")
    return out


def test_guard_finds_a_planted_list(tmp_path):
    tree = ast.parse('X = {"fasting", "fed", "after a meal"}')
    assert len(word_strings(tree.body[0].value)) == 3


@pytest.mark.xfail(strict=True, reason="to-do guard (Q2b): word lists still in the pipeline; once they are gone "
                   "this XPASS fails the run, so remove this marker then")
def test_no_hard_coded_word_lists():
    found = offenders()
    assert not found, "hard-coded word lists (Q2b):\n" + "\n".join(found)
