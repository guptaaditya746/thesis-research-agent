from __future__ import annotations

import json
import os
import re
import statistics
import time
from pathlib import Path

from openai import OpenAI


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
tasks = [json.loads(line) for line in (ROOT / "tasks.jsonl").read_text().splitlines()]
base_url = os.environ.get("B8_BASE_URL", "http://127.0.0.1:8001/v1")
api_key = os.environ.get("B8_API_KEY", "x")
model = os.environ.get("B8_MODEL", "orch-model")
client = OpenAI(base_url=base_url, api_key=api_key, timeout=600)
thinking = os.environ.get("B8_THINKING", "false").lower() == "true"
label = os.environ.get("B8_LABEL", "direct")
max_tokens = int(os.environ.get("B8_MAX_TOKENS", "4096"))
reasoning_effort = os.environ.get("B8_REASONING_EFFORT")
system = """You are a research agent working in a Linux shell. The corpus is at /corpus and is read-only; /work is writable. Reply with exactly one fenced bash block and no other text. Do not explain, plan, or add prose. Use this exact shape:
```bash
<one executable next command>
```
The opening fence must be ```bash on its own line. The closing fence must be on its own line. Never emit a second fence. If the command needs multiple operations, put them in the same bash block using separate lines or &&. Choose only the next useful command for the research task."""
block_re = re.compile(r"```(?:bash|sh)\n(.*?)```", re.DOTALL)
rows = []
for task in tasks:
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": task["prompt"]}],
        max_tokens=max_tokens,
        temperature=0.2,
        extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
        **({"reasoning_effort": reasoning_effort} if reasoning_effort else {}),
    )
    message = response.choices[0].message
    content = message.content or ""
    blocks = block_re.findall(content)
    row = {
        "id": task["id"], "content": content, "block_count": len(blocks),
        "reasoning": getattr(message, "reasoning", None) or getattr(message, "reasoning_content", None),
        "finish_reason": response.choices[0].finish_reason,
        "seconds": time.perf_counter() - started,
        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
        "completion_tokens": response.usage.completion_tokens if response.usage else None,
    }
    rows.append(row)
    print(json.dumps({"id": row["id"], "block_count": row["block_count"],
                      "finish_reason": row["finish_reason"], "seconds": round(row["seconds"], 2)}), flush=True)

mode = "thinking-on" if thinking else "thinking-off"
mode += f"-{reasoning_effort}" if reasoning_effort else ""
mode += f"-{max_tokens}"
out = HERE / f"results-{label}-{mode}-50.jsonl"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
summary = {
    "n": len(rows),
    "exactly_one_block": sum(row["block_count"] == 1 for row in rows),
    "one_block_pct": 100 * sum(row["block_count"] == 1 for row in rows) / len(rows),
    "prose_only": sum(row["block_count"] == 0 for row in rows),
    "multiple_blocks": sum(row["block_count"] > 1 for row in rows),
    "reasoning_nonempty": sum(bool(row["reasoning"]) for row in rows),
    "length_cuts": sum(row["finish_reason"] == "length" for row in rows),
    "mean_seconds": statistics.mean(row["seconds"] for row in rows),
}
(HERE / f"summary-{label}-{mode}-50.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2), flush=True)
