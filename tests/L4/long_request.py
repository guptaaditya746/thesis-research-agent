from __future__ import annotations

import json
import os
import time
from pathlib import Path

from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:4000/v1", api_key=os.environ["LITELLM_MASTER_KEY"],
                timeout=300, max_retries=0)
started = time.perf_counter()
first = None
content_chars = 0
finish_reason = None
usage = None
error = None
try:
    stream = client.chat.completions.create(
        model="sub-model",
        messages=[{"role": "user", "content": (
            "Write a long, detailed technical tutorial about how to design reproducible experiments. "
            "Use numbered sections, examples, and explanations. Continue for as long as possible."
        )}],
        max_tokens=5000,
        temperature=0.7,
        stream=True,
        stream_options={"include_usage": True},
    )
    for chunk in stream:
        if chunk.choices:
            choice = chunk.choices[0]
            if choice.delta.content:
                first = first or time.perf_counter()
                content_chars += len(choice.delta.content)
            if choice.finish_reason:
                finish_reason = choice.finish_reason
        if chunk.usage:
            usage = chunk.usage.model_dump()
except Exception as exc:  # record client-visible outcome without response content
    error = f"{type(exc).__name__}: {str(exc)[:500]}"
finally:
    client.close()

result = {
    "elapsed_s": time.perf_counter() - started,
    "ttft_s": None if first is None else first - started,
    "content_chars_received": content_chars,
    "finish_reason": finish_reason,
    "usage": usage,
    "error": error,
}
Path("tests/L4/long_request.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result), flush=True)
