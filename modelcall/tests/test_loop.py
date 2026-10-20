"""The model loop over real keep-alive HTTP: two sync calls in one process share one pooled connection."""
from __future__ import annotations

from pydantic import BaseModel

from modelcall import Prompt, ask_sync, openai_model

from .server import keepalive_server


class Echo(BaseModel):
    answer: str


def test_two_ask_sync_over_keepalive_share_one_loop() -> None:
    prompt = Prompt.inline("Echo the input.", Echo)
    with keepalive_server(lambda text: {"answer": text}) as url:
        model = openai_model("orch-model", url=url)
        first = ask_sync(prompt, "one", model=model)
        second = ask_sync(prompt, "two", model=model)
    assert url.prompts == ["one", "two"]
    assert (first.output.answer, second.output.answer) == ("one", "two")
    assert first.served_model == "m" and first.input_tokens == 5 and not first.cached
