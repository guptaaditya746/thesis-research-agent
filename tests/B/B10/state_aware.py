from __future__ import annotations

import json
import re
import statistics
import time
from pathlib import Path

from openai import OpenAI


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
tasks = [json.loads(line) for line in (ROOT / "tasks.jsonl").read_text().splitlines()]
client = OpenAI(base_url="http://127.0.0.1:8001/v1", api_key="x", timeout=600)
model = "orch-model"
system = """You select the next shell command for a paper-research agent. Known environment: /corpus exists, is readable, and contains one Markdown file per paper; /work is writable; grep, rg, and python3 are available. The previous steps in the user message describe actions already done. Avoid repeating them. If previous steps are `(none)`, start with a command targeted to the research concept; do not list or inventory the corpus. Before answering, privately generate three candidate commands and select the one that is executable, most directly relevant, and likely to produce new evidence. Avoid generic `ls`, `pwd`, or `find` unless prior output shows a missing path. Return exactly one fenced bash block and no other text. Do not include multiple commands unless the selected action requires a short pipeline."""
block_re = re.compile(r"```(?:bash|sh)\n(.*?)```", re.DOTALL)
rows = []
for task in tasks:
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": task["prompt"]}],
        max_tokens=4096,
        temperature=0.2,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    message = response.choices[0].message
    content = message.content or ""
    rows.append({
        "id": task["id"], "prompt": task["prompt"], "content": content,
        "block_count": len(block_re.findall(content)),
        "finish_reason": response.choices[0].finish_reason,
        "seconds": time.perf_counter() - started,
    })
    print(json.dumps({"id": task["id"], "blocks": rows[-1]["block_count"],
                      "finish": rows[-1]["finish_reason"], "seconds": round(rows[-1]["seconds"], 2)}), flush=True)

(HERE / "results.jsonl").write_text(
    "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
)
summary = {
    "n": len(rows),
    "exactly_one_block": sum(row["block_count"] == 1 for row in rows),
    "one_block_pct": 100 * sum(row["block_count"] == 1 for row in rows) / len(rows),
    "prose_only": sum(row["block_count"] == 0 for row in rows),
    "multiple_blocks": sum(row["block_count"] > 1 for row in rows),
    "length_cuts": sum(row["finish_reason"] == "length" for row in rows),
    "mean_seconds": statistics.mean(row["seconds"] for row in rows),
}
(HERE / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2), flush=True)
client.close()
