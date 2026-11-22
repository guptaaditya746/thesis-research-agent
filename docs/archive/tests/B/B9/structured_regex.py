from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from openai import OpenAI


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
tasks = [json.loads(line) for line in (ROOT / "tasks.jsonl").read_text().splitlines()[:10]]
base_url = os.environ.get("B9_BASE_URL", "http://127.0.0.1:8001/v1")
api_key = os.environ.get("B9_API_KEY", "unused")
label = os.environ.get("B9_LABEL", "direct")
client = OpenAI(base_url=base_url, api_key=api_key, timeout=600)
thinking = os.environ.get("B9_THINKING", "false").lower() == "true"
system = "You are a Linux research agent. Answer with exactly one fenced bash block and no prose. The block must start with ```bash on a line by itself and end with ``` on a line by itself. Put the single next executable command inside."
pattern = r"^```bash\n([^`]|`[^`]|``[^`])*\n```$"
block_re = re.compile(r"```(?:bash|sh)\n(.*?)```", re.DOTALL)
rows = []
for task in tasks:
    started = time.perf_counter()
    response = client.chat.completions.create(
        model="orch-model",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": task["prompt"]}],
        max_tokens=4096,
        temperature=0.2,
        extra_body={
            "chat_template_kwargs": {"enable_thinking": thinking},
            "structured_outputs": {"regex": pattern},
        },
    )
    content = response.choices[0].message.content or ""
    message = response.choices[0].message
    row = {
        "id": task["id"], "content": content,
        "reasoning": getattr(message, "reasoning", None) or getattr(message, "reasoning_content", None),
        "block_count": len(block_re.findall(content)),
        "finish_reason": response.choices[0].finish_reason,
        "seconds": time.perf_counter() - started,
    }
    rows.append(row)
    print(json.dumps({"id": row["id"], "blocks": row["block_count"],
                      "finish": row["finish_reason"], "seconds": round(row["seconds"], 2)}), flush=True)

(HERE / f"results-{label}.jsonl").write_text(
    "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
)
summary = {
    "n": len(rows),
    "exactly_one_block": sum(row["block_count"] == 1 for row in rows),
    "one_block_pct": 100 * sum(row["block_count"] == 1 for row in rows) / len(rows),
    "prose_only": sum(row["block_count"] == 0 for row in rows),
    "multiple_blocks": sum(row["block_count"] > 1 for row in rows),
    "reasoning_nonempty": sum(bool(row["reasoning"]) for row in rows),
    "length_cuts": sum(row["finish_reason"] == "length" for row in rows),
    "mean_seconds": sum(row["seconds"] for row in rows) / len(rows),
}
(HERE / f"summary-{label}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2), flush=True)
client.close()
