from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import httpx
from openai import OpenAI

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:8001/v1")
parser.add_argument("--model", default="orch")
parser.add_argument("--steps", type=int, default=60)
parser.add_argument("--out", default="tests/C2/steps.jsonl")
args = parser.parse_args()

root = Path(__file__).resolve().parents[2]
system = (root / "tests/B/system_prompt.txt").read_text(encoding="utf-8")
client = OpenAI(base_url=args.base_url, api_key="x", timeout=600)
metrics_url = args.base_url.removesuffix("/v1") + "/metrics"
out = root / args.out
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("", encoding="utf-8")

messages = [
    {"role": "system", "content": system},
    {"role": "user", "content": "Research concept: find papers that discuss retrieval evaluation. Use only evidence in /corpus. What is your next command?"},
]
rows = []
for step in range(1, args.steps + 1):
    if step in (20, 40, 60):
        # Keep a compact observation, which deliberately changes the prompt
        # prefix at each masking boundary.
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "Research concept: find papers that discuss retrieval evaluation. Use only evidence in /corpus. What is your next command?"},
            {"role": "assistant", "content": "```bash\ngrep -il retrieval /corpus/*.md\n```"},
            {"role": "user", "content": f"Observation mask at step {step}: earlier command history summarized; last command output was recorded. Continue the same research task. What is your next command?"},
        ]
    started = time.perf_counter()
    first = None
    content = ""
    usage = None
    try:
        stream = client.chat.completions.create(
            model=args.model,
            messages=messages,
            max_tokens=96,
            temperature=0,
            stream=True,
            stream_options={"include_usage": True},
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        for chunk in stream:
            now = time.perf_counter()
            if first is None and chunk.choices:
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    first = now - started
                    content += delta.content
            elif chunk.choices:
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    content += delta.content
            if chunk.usage:
                usage = chunk.usage.model_dump()
    except Exception as e:
        content = f"ERROR: {e}"
    elapsed = time.perf_counter() - started
    try:
        metric_text = httpx.get(metrics_url, timeout=5).text
    except Exception as e:
        metric_text = f"ERROR: {e}"
    selected = [line for line in metric_text.splitlines() if re.search(r"prefix_cache|kv_cache_usage|num_requests_waiting", line, re.I) and not line.startswith("#")]
    row = {"step": step, "ttft_seconds": first, "total_seconds": elapsed, "usage": usage, "metrics": selected, "content": content}
    rows.append(row)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"step": step, "ttft_seconds": first, "total_seconds": elapsed, "usage": usage}), flush=True)

    messages.append({"role": "assistant", "content": content})
    messages.append({"role": "user", "content": f"Tool output for the fixed replay at step {step}: (no matches). What is your next command?"})

print(json.dumps({"steps": len(rows), "ttft_19_20_21": {str(i): rows[i - 1]["ttft_seconds"] for i in (19, 20, 21) if i <= len(rows)}}))
