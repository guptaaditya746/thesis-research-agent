from __future__ import annotations

import asyncio
import json
import os
import re
import time

import httpx
from openai import AsyncOpenAI


def metric_total(port: int) -> float:
    response = httpx.get(f"http://127.0.0.1:{port}/metrics", timeout=10)
    response.raise_for_status()
    totals = []
    for line in response.text.splitlines():
        if line.startswith("#") or not re.match(r"vllm[:_]request_success_total(?:\{|\s)", line):
            continue
        try:
            totals.append(float(line.rsplit(None, 1)[1]))
        except (IndexError, ValueError):
            continue
    if not totals:
        raise RuntimeError(f"request_success_total absent on port {port}")
    return sum(totals)


async def main() -> None:
    client = AsyncOpenAI(base_url="http://127.0.0.1:4000/v1",
                         api_key=os.environ["LITELLM_MASTER_KEY"], timeout=600)
    before = {"8002": metric_total(8002), "8004": metric_total(8004)}

    async def one(index: int) -> dict:
        model = f"sub-model-{index % 2 + 1}"
        started = time.perf_counter()
        result = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": f"Reply briefly to pinned replica probe {index}."}],
            max_tokens=80, temperature=0.1,
        )
        return {"request": index, "model": model,
                "latency_seconds": time.perf_counter() - started,
                "completion_tokens": result.usage.completion_tokens,
                "response_model": result.model}

    requests = await asyncio.gather(*(one(index) for index in range(8)))
    after = {"8002": metric_total(8002), "8004": metric_total(8004)}
    await client.close()
    deltas = {port: after[port] - before[port] for port in before}
    output = {"requests": requests, "replica_deltas": deltas,
              "balanced": deltas == {"8002": 4.0, "8004": 4.0}}
    print(json.dumps(output, indent=2), flush=True)
    if not output["balanced"]:
        raise SystemExit(1)


asyncio.run(main())
