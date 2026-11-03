"""`RecordedLM`: a DSPy language model whose every call goes through the run's recorder.

DSPy builds the messages; `RecordedLM` turns them into one prompt text, looks the call up in the repo's
`JsonlCache` under `cache_key({"alias", "messages", "settings"})`, and on a miss makes the raw call `ask`
(in production a wrapper of the gateway, in tests a fake) and stores its text. A rerun on the same cache file
makes no new model call and gets the same outputs. DSPy's own disk and memory cache is switched off, so replay
depends only on our recorder, never on ~/.dspy_cache.

Without `cache` nothing is recorded: production must pass one. `attempt` (a call setting, default 0) is part of the
key, so a retry after an unparseable reply is a new recorded call and the bad reply stays on file."""
from __future__ import annotations

import json
import warnings
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import dspy

from .cache import JsonlCache, cache_key


def render(messages: list[dict[str, Any]]) -> str:
    """The messages as one prompt text for the raw model call: each message under its role."""
    return "\n\n".join(f"[{m.get('role', 'user')}]\n{m.get('content', '')}" for m in messages)


class RecordedLM(dspy.BaseLM):
    """A `dspy.BaseLM` answering from `ask(prompt_text) -> reply_text`, recorded in `cache` when given. With
    `with_call=True` the callback is `ask(prompt_text, *, attempt, settings)`: a recorder of its own (the engine's)
    then keys on the retry number and the call settings too, so a retry is a new recorded call."""

    def __init__(self, alias: str, ask: Callable[..., str], cache: JsonlCache | None = None, *, with_call: bool = False,
                 **kwargs: Any) -> None:
        super().__init__(model=alias, model_type="chat", cache=False, **kwargs)
        self.alias = alias
        self._ask = ask
        self._with_call = with_call   # True: ask(text, attempt=..., settings=...) also gets the retry number and settings
        self._recorder = cache

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # DSPy 3.4 warns that a BaseLM.forward subclass is deprecated; it is removed in 3.5. Migration then: an engine
        # with complete(Request) -> Response behind dspy.LM(engine=...), and DSPy's own cache must be turned off again.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Implementing custom LMs through BaseLM", category=DeprecationWarning)
            warnings.filterwarnings("ignore", message=".*OpenAI.*messages", category=Warning)
            return super().__call__(*args, **kwargs)

    def forward(self, prompt: str | None = None, messages: list[dict[str, Any]] | None = None, **kwargs: Any) -> Any:
        msgs = messages if messages is not None else [{"role": "user", "content": prompt or ""}]
        settings = {k: v for k, v in {**self.kwargs, **kwargs}.items() if not k.startswith("api_") and k != "cache"}
        attempt = settings.pop("attempt", 0)
        key = cache_key({"alias": self.alias, "messages": msgs, "attempt": attempt,
                         "settings": json.loads(json.dumps(settings, default=repr))})
        hit = self._recorder.get(key) if self._recorder is not None else None
        if hit is not None:
            text = hit["output"]
        else:
            text = (self._ask(render(msgs), attempt=attempt, settings=json.loads(json.dumps(settings, default=repr)))
                    if self._with_call else self._ask(render(msgs)))
            if self._recorder is not None:
                self._recorder.put(key, {"output": text, "model": self.alias, "messages": msgs})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=None),
                                                        finish_reason="stop")],
                               usage={}, model=self.alias, cache_hit=hit is not None)
