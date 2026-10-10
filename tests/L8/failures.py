from __future__ import annotations

import json
import os
from math import ceil

from openai import APIStatusError, OpenAI
from transformers import AutoTokenizer


def content_for_tokens(tokenizer, target: int) -> tuple[str, int]:
    repetitions = target
    content = ""
    for _ in range(8):
        content = " retrieval" * repetitions
        count = len(tokenizer.encode(content, add_special_tokens=False))
        if count >= target and count - target < 8:
            return content, count
        repetitions = max(1, repetitions - ceil((count - target) / max(1, count / repetitions))) if count > target else ceil(repetitions * target / max(count, 1)) + 1
    return content, len(tokenizer.encode(content, add_special_tokens=False))


tokenizer = AutoTokenizer.from_pretrained(
    "Qwen/Qwen3.8-27B-FP8", revision="017b9c7af6b5689d5dd426a76e0bc077eb5ca20a",
    local_files_only=True,
)
client = OpenAI(base_url="http://127.0.0.1:4000/v1", api_key=os.environ["LITELLM_MASTER_KEY"], timeout=600)


def attempt(label: str, model: str, prompt_tokens: int, max_tokens: int) -> dict:
    content, measured = content_for_tokens(tokenizer, prompt_tokens)
    try:
        result = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": content}], max_tokens=max_tokens,
            temperature=0,
        )
        return {"case": label, "status": 200, "finish_reason": result.choices[0].finish_reason,
                "prompt_content_tokens": measured, "usage": result.usage.model_dump()}
    except APIStatusError as exc:
        return {"case": label, "status": exc.status_code, "error_type": type(exc).__name__,
                "message": str(exc), "body": exc.body, "prompt_content_tokens": measured,
                "max_tokens": max_tokens}


results = [
    attempt("orch_prompt_over_65536", "orch-model", 70_000, 1),
    attempt("sub_prompt_over_32768", "sub-model", 34_000, 1),
    attempt("orch_output_over_context", "orch-model", 64_000, 2_000),
]
print(json.dumps(results, indent=2), flush=True)
client.close()
