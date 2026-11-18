"""One checked model call, shared by every synth3 model step (the sheet drafter, the judge).

A call, then code checks the reply; a failed check gets at most `MAX_REPAIRS` repair calls that hold the task
input, the rejected reply and the failed checks (docs/prompt-writing.md). A call that raises `ModelCallError`
ends the attempts with its redacted reason as a problem, so the caller records the item as failed or pending and
goes on with the next one. Every attempt is counted, a cached one too."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

import modelcall
from modelcall import CallSettings, JsonlCache, ModelCallError, default_key, load_prompt

MAX_REPAIRS = 1


def repair_input(first: str, rejected: BaseModel, problems: list[str]) -> str:
    """The task input, the rejected reply as JSON, then the problems one per line."""
    return (f"{first}\n\nYour reply:\n{rejected.model_dump_json()}\n\nFix only these problems:\n"
            + "\n".join(problems))


def ask_checked(prompt_path: Path, output_type: type[BaseModel], user: str,
                check: Callable[[BaseModel], list[str]], model: Any, cache: JsonlCache, settings: CallSettings,
                *, fresh: str | None = None) -> dict:
    """`{"reply": the accepted reply or None, "problems", "calls", "served_models", "prompt_sha256"}`.

    `fresh`, when set, is added to every cache key, so the calls are made again instead of read from the cache."""
    prompt = load_prompt(prompt_path, output_type)
    text, problems, calls, served = user, [], 0, []
    for _ in range(1 + MAX_REPAIRS):
        key = default_key(prompt, text, model, settings)
        if fresh is not None:
            key = key | {"fresh": fresh}
        calls += 1
        try:
            answer = modelcall.ask_sync(prompt, text, model=model, settings=settings, cache=cache, key=key)
        except ModelCallError as err:
            problems = [f"model call failed: {err.reason}", *problems]
            break
        served.append(answer.served_model)
        problems = check(answer.output)
        if not problems:
            return {"reply": answer.output, "problems": [], "calls": calls, "served_models": served,
                    "prompt_sha256": prompt.sha256}
        text = repair_input(user, answer.output, problems)
    return {"reply": None, "problems": problems, "calls": calls, "served_models": served,
            "prompt_sha256": prompt.sha256}
