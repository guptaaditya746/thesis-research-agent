"""Test helpers: a scripted pydantic-ai model and a guard that fails on reading evaluation-only files."""
from __future__ import annotations

import builtins
import io
import json
import os
from pathlib import Path
from typing import Any, Callable

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel


class Scripted:
    """FunctionModel callable: returns `reply` (a dict, or a function of the user prompt) and records prompts."""

    def __init__(self, reply: dict[str, Any] | Callable[[str], dict[str, Any]]) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = next(p.content for m in messages for p in getattr(m, "parts", []) if isinstance(p, UserPromptPart))
        self.prompts.append(str(prompt))
        args = self.reply(str(prompt)) if callable(self.reply) else self.reply
        if info.output_tools:
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])
        return ModelResponse(parts=[TextPart(json.dumps(args))])

    def model(self, name: str = "scripted") -> FunctionModel:
        return FunctionModel(self, model_name=name)


def guard_corpus(monkeypatch: pytest.MonkeyPatch, corpus: Path) -> list[str]:
    """Allow-list: inside `corpus`, only manifest.json and files directly in papers/ may be opened.

    Every other open there (ground_truth.json, corpus.json, fidelity.json, decoys.json, ...) raises and
    is returned in the attempts list."""
    attempts: list[str] = []
    real_open, real_os_open = builtins.open, os.open
    root = Path(corpus).resolve()

    def check(path: Any) -> None:
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        p = Path(os.path.abspath(os.fsdecode(path)))
        inside = p == root or root in p.parents
        if inside and not (p == root / "manifest.json" or p.parent == root / "papers"):
            attempts.append(str(p))
            raise AssertionError(f"a system under test opened {p}")

    def guarded_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        check(file)
        return real_open(file, *args, **kwargs)

    def guarded_os_open(path: Any, *args: Any, **kwargs: Any) -> Any:
        check(path)
        return real_os_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)
    monkeypatch.setattr(os, "open", guarded_os_open)
    return attempts
