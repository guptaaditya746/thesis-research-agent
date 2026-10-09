from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import httpx
from openai import AsyncOpenAI
from transformers import AutoTokenizer

p = argparse.ArgumentParser()
p.add_argument('--base-url', required=True)
p.add_argument('--model', required=True)
p.add_argument('--n', type=int, required=True)
p.add_argument('--prompt-tokens', type=int, required=True)
p.add_argument('--model-path', default='Qwen/Qwen3-30B-A3B-Instruct-2507-FP8')
p.add_argument('--out', required=True)
p.add_argument('--api-key-env', default='LLM_BACKEND_KEY', help='LITELLM_MASTER_KEY when going through the proxy')
p.add_argument('--metrics-url', action='append', help='vLLM /metrics to scrape; repeat once per replica (default: base-url/metrics)')
a = p.parse_args()
repo = Path(__file__).resolve().parents[2]
files = sorted((repo / 'final-final-frontend/UI/files/harness/corpus_data/outlines').glob('*.md'))
text = '\n\n'.join(f.read_text(encoding='utf-8') for f in files)
tok = AutoTokenizer.from_pretrained(a.model_path)
ids = tok.encode(text, add_special_tokens=False)
payload = tok.decode((ids * ((a.prompt_tokens + len(ids) - 1) // len(ids)))[:a.prompt_tokens], skip_special_tokens=True)
client = AsyncOpenAI(base_url=a.base_url, api_key=os.getenv(a.api_key_env, 'x'), timeout=1800)
metrics_urls = a.metrics_url or [a.base_url.removesuffix('/v1') + '/metrics']

async def main() -> None:
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    metrics_path = out.with_suffix('.metrics.txt')
    stop = asyncio.Event()
    async def scrape() -> None:
        async with httpx.AsyncClient(timeout=10) as http:
            while not stop.is_set():
                for metrics_url in metrics_urls:
                    try:
                        response = await http.get(metrics_url)
                        response.raise_for_status()
                        matches = [line for line in response.text.splitlines() if any(k in line.lower() for k in ('gpu_cache_usage', 'kv_cache_usage', 'preempt', 'num_requests_waiting', 'num_requests_running', 'request_success'))]
                        with metrics_path.open('a', encoding='utf-8') as f:
                            f.write(f"{time.time():.3f} {metrics_url}\n" + '\n'.join(matches) + '\n')
                    except Exception as exc:
                        with metrics_path.open('a', encoding='utf-8') as f:
                            f.write(f"{time.time():.3f} {metrics_url} scrape_error={type(exc).__name__}:{exc}\n")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass
    poller = asyncio.create_task(scrape())
    barrier = asyncio.Event()
    async def one(i: int) -> dict:
        await barrier.wait()
        start = time.perf_counter()
        first = None
        usage = None
        error = None
        try:
            stream = await client.chat.completions.create(model=a.model, messages=[{'role':'user','content':f'Independent request {i}.\n'+payload}], max_tokens=300, temperature=0.2, stream=True, stream_options={'include_usage':True})
            async for chunk in stream:
                now = time.perf_counter()
                if chunk.choices and chunk.choices[0].delta.content and first is None:
                    first = now
                if chunk.usage:
                    usage = chunk.usage.model_dump()
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        return {'request':i,'ttft_s':None if first is None else first-start,'latency_s':time.perf_counter()-start,'usage':usage,'error':error}
    tasks = [asyncio.create_task(one(i)) for i in range(a.n)]
    await asyncio.sleep(0.1)
    barrier.set()
    rows = await asyncio.gather(*tasks)
    stop.set()
    await poller
    with out.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row) + '\n')
    print(json.dumps({'n':a.n,'requested_prompt_tokens':a.prompt_tokens,'completed':sum(not r['error'] for r in rows),'errors':sum(bool(r['error']) for r in rows),'mean_latency_s':sum(r['latency_s'] for r in rows)/len(rows),'max_latency_s':max(r['latency_s'] for r in rows),'rows':rows}, ensure_ascii=False))
    await client.close()

asyncio.run(main())
