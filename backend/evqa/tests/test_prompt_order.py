"""Per-paper prompts put the paper first and the question last (vLLM prefix caching reuses the shared start).

The predecessors (old field order) are kept and render exactly as before: same instructions, same fields.
"""
from __future__ import annotations

import ast
from pathlib import Path

import dspy

from evqa.extract import prompt, settings_v2
from evqa.find import prompts

PKG = Path(__file__).resolve().parents[1]


def _inputs(sig):
    return list(sig.input_fields)


def _user(sig) -> str:
    return dspy.JSONAdapter().format(sig, demos=[], inputs={k: k.upper() for k in sig.input_fields})[-1]["content"]


def test_paper_first_question_last():
    assert _inputs(prompt.ExtractRows) == ["paper_context", "passage", "question_spec"]
    assert _inputs(prompts.ScreenPaper) == ["title", "abstract", "passages", "spec"]
    assert _inputs(prompts.MarkPassages) == ["passages", "spec"]
    assert _inputs(settings_v2.ReadSettings) == ["context", "passages", "dimensions", "feedback"]
    user = _user(prompt.ExtractRows)
    assert user.index("PAPER_CONTEXT") < user.index("PASSAGE\n") < user.index("QUESTION_SPEC")
    assert prompt.PROMPT_VERSION == "extract-rows-v2" and prompts.PROMPTS_VERSION == "find-prompts-v3"


def test_predecessors_keep_old_order_and_words():
    for new, old, first in ((prompt.ExtractRows, prompt.ExtractRowsV1, "question_spec"),
                            (prompts.ScreenPaper, prompts.ScreenPaperV2, "spec"),
                            (prompts.MarkPassages, prompts.MarkPassagesV2, "spec"),
                            (settings_v2.ReadSettings, settings_v2.ReadSettingsV1, "dimensions")):
        assert _inputs(old)[0] == first and set(old.fields) == set(new.fields)
        assert old.instructions == new.instructions and list(old.output_fields) == list(new.output_fields)


def test_reordered_prompts_are_called_with_keywords_only():
    names = {"ExtractRows", "ScreenPaper", "MarkPassages", "ReadSettings"}
    seen = set()
    for path in [*(PKG / "extract").glob("*.py"), *(PKG / "find").glob("*.py")]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            inner = node.func if isinstance(node.func, ast.Call) else node     # dspy.Predict(X)(...)
            if inner is node and not (isinstance(node.func, ast.Attribute) and node.func.attr == "predict"):
                continue                                                   # only self.predict(X, ...)
            args = [a for a in inner.args if isinstance(a, ast.Name) and a.id in names]
            if not args:
                continue
            seen.add(args[0].id)
            call_args = node.args if inner is not node else node.args[1:]
            assert call_args == [], f"{path.name}:{node.lineno} passes inputs by position"
    assert seen == names
