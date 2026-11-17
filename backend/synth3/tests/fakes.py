"""Fake models for every synth3 test that makes a model call (none opens a socket), and `rec`, a fake answer.

All have `model_name="fake"`, so they share cache keys the way one real alias does. The replies are native JSON
text, as the cluster models answer."""
from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel
from pydantic_ai.messages import ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

from synth3.answers import AnswerRecord


def _text(reply: BaseModel | str) -> str:
    return reply if isinstance(reply, str) else reply.model_dump_json()


def _user_prompt(messages) -> str:
    """The latest user prompt in the messages of one call."""
    for message in reversed(messages):
        for part in getattr(message, "parts", []):
            if isinstance(part, UserPromptPart):
                return part.content if isinstance(part.content, str) else str(part.content)
    return ""


def answering(fn: Callable[[str], BaseModel | str]) -> FunctionModel:
    """A model whose reply is `fn(user_prompt)`; `.prompts` keeps every user prompt it saw."""
    def answer(messages, info):
        prompt = _user_prompt(messages)
        model.prompts.append(prompt)
        return ModelResponse(parts=[TextPart(_text(fn(prompt)))])

    model = FunctionModel(answer, model_name="fake")
    model.prompts = []
    return model


def scripted(*replies: BaseModel | str) -> FunctionModel:
    """A model that returns `replies` in order; `.prompts` keeps every user prompt it saw."""
    left = list(replies)
    return answering(lambda prompt: left.pop(0))


def boom() -> FunctionModel:
    """A model that counts its calls in `.calls` and raises. Assert `model.calls == 0` in the test: an assert inside
    the model would become a `ModelCallError`, then a failure or a pending decision."""
    def answer(messages, info):
        model.calls += 1
        raise RuntimeError("boom: this model must not be called")

    model = FunctionModel(answer, model_name="fake")
    model.calls = 0
    return model


def failing() -> FunctionModel:
    """A model that always answers with text that is not JSON, so `modelcall.ask_sync` raises `ModelCallError`."""
    return FunctionModel(lambda messages, info: ModelResponse(parts=[TextPart("this is not JSON")]),
                         model_name="fake")


def rec(text: str, **kw) -> AnswerRecord:
    """An engine answer to question `x` on the `folder` fixture (domain `demo`, seed 1) with `facts=[]` unless
    given; any other field can be set by keyword. The corpus id is a stand-in: build the record from the folder
    when a test needs the real one."""
    fields = {"domain": "demo", "seed": 1, "corpus_id": "demo-fake", "question_id": "x",
              "question_sha256": "0" * 64, "system": "engine", "text": text, "text_cut": False, "cited": [],
              "facts": [], "passages": [], "source": "fake"}
    return AnswerRecord(**(fields | kw))
