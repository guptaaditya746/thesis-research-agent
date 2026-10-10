from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
import httpx
from openai import AsyncOpenAI, OpenAI


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
    key = os.environ["LITELLM_MASTER_KEY"]
    proxy = OpenAI(base_url="http://127.0.0.1:4000/v1", api_key=key, timeout=600)
    direct = OpenAI(base_url="http://127.0.0.1:8002/v1", api_key="x", timeout=600)
    before = {"8002": metric_total(8002), "8004": metric_total(8004)}
    seq_latencies = []
    for i in range(24):
        started = time.perf_counter()
        proxy.chat.completions.create(model="sub-model", messages=[{
            "role": "user", "content": f"Reply with one short sentence. Request id {i}."
        }], max_tokens=80, temperature=0.1)
        seq_latencies.append(time.perf_counter() - started)
    after_seq = {"8002": metric_total(8002), "8004": metric_total(8004)}

    async_client = AsyncOpenAI(base_url="http://127.0.0.1:4000/v1", api_key=key, timeout=600)
    async def one(i: int):
        started = time.perf_counter()
        result = await async_client.chat.completions.create(
            model="sub-model", messages=[{"role": "user", "content": f"Reply briefly. Concurrent request {i}."}],
            max_tokens=80, temperature=0.1,
        )
        return time.perf_counter() - started, result.usage.completion_tokens
    concurrent = await asyncio.gather(*(one(i) for i in range(8)))
    await async_client.close()
    after_concurrent = {"8002": metric_total(8002), "8004": metric_total(8004)}

    seed_args = {
        "messages": [{"role": "user", "content": "Write a two sentence description of a blue bicycle."}],
        "max_tokens": 96, "temperature": 0.8, "seed": 90210,
    }
    proxy_seed = [proxy.chat.completions.create(model="sub-model", **seed_args).choices[0].message.content
                  for _ in range(2)]
    direct_seed = [direct.chat.completions.create(model="sub-model", **seed_args).choices[0].message.content
                   for _ in range(2)]
    output = {
        "routing_strategy": os.environ.get("LITELLM_ROUTING_STRATEGY", "least-busy"),
        "before": before,
        "after_24_sequential": after_seq,
        "after_8_concurrent": after_concurrent,
        "sequential_delta": {k: after_seq[k] - before[k] for k in before},
        "concurrent_delta": {k: after_concurrent[k] - after_seq[k] for k in before},
        "sequential_latency_seconds": seq_latencies,
        "concurrent_latency_and_tokens": concurrent,
        "proxy_seed_pair_matches": proxy_seed[0] == proxy_seed[1],
        "direct_seed_pair_matches": direct_seed[0] == direct_seed[1],
        "proxy_seed_hashes": [hashlib.sha256(s.encode()).hexdigest() for s in proxy_seed],
        "direct_seed_hashes": [hashlib.sha256(s.encode()).hexdigest() for s in direct_seed],
    }
    print(json.dumps(output, indent=2), flush=True)
    proxy.close()
    direct.close()


asyncio.run(main())
