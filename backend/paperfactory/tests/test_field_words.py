"""#9: field words live in the packs, not in the shared code."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from paperfactory import packs

HERE = Path(__file__).resolve().parents[1]
LAW_TERMS = re.compile(r"\b(holdings?|line of authority|courts?|decisions?|statut\w*|provisions?|case law|rulings?|"
                       r"judgments?|plaintiffs?|defendants?)\b", re.I)


def strings(tree: ast.AST) -> list[tuple[int, str]]:
    """String constants that are not docstrings (prompts, headings, payload keys)."""
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


@pytest.mark.parametrize("path", sorted(p.name for p in HERE.glob("*.py")))
def test_shared_code_has_no_law_words(path: str) -> None:
    tree = ast.parse((HERE / path).read_text(encoding="utf-8"))
    hits = [(line, s[:80]) for line, s in strings(tree) if LAW_TERMS.search(s)]
    assert hits == [], f"{path}: field words belong in the field pack: {hits}"


@pytest.mark.parametrize("name", ["law", "medicine", "materials", "llm"])
def test_every_pack_has_the_prompt_words(name: str) -> None:
    f = packs.field(name)
    for key in ("fact", "facts", "action", "actions", "line_of_authority"):
        assert f.word(key)


def test_missing_word_is_a_clear_error() -> None:
    f = packs.Field({"field": "x", "words": {}})
    with pytest.raises(KeyError, match="field pack 'x' has no words.fact"):
        f.word("fact")
