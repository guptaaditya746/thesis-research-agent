from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from openai import AsyncOpenAI
from transformers import AutoTokenizer

p=argparse.ArgumentParser()
p.add_argument('--base-url', required=True); p.add_argument('--model', required=True)
p.add_argument('--model-path', default='Qwen/Qwen3-30B-A3B-Instruct-2507-FP8')
p.add_argument('--requests', type=int, default=20); p.add_argument('--concurrency', type=int, default=1)
p.add_argument('--enable-thinking', action='store_true')
p.add_argument('--out', required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[2]
files=sorted((repo/'final-final-frontend/UI/files/harness/corpus_data/outlines').glob('*.md'))
text='\n\n'.join(f.read_text(encoding='utf-8') for f in files)
tok=AutoTokenizer.from_pretrained(a.model_path); ids=tok.encode(text,add_special_tokens=False)
prompt=tok.decode((ids*((2000+len(ids)-1)//len(ids)))[:2000],skip_special_tokens=True)
client=AsyncOpenAI(base_url=a.base_url,api_key=os.getenv('LLM_BACKEND_KEY','x'),timeout=1800)

async def main():
    sem=asyncio.Semaphore(a.concurrency)
    async def one(i):
        async with sem:
            start=time.perf_counter(); first=None; usage=None; error=None
            try:
                stream=await client.chat.completions.create(model=a.model,messages=[{'role':'user','content':f'Independent request {i}.\n'+prompt}],max_tokens=300,temperature=0.7,stream=True,stream_options={'include_usage':True},extra_body={'chat_template_kwargs':{'enable_thinking':a.enable_thinking}})
                async for chunk in stream:
                    now=time.perf_counter()
                    if chunk.choices and chunk.choices[0].delta.content and first is None: first=now
                    if chunk.usage: usage=chunk.usage.model_dump()
            except Exception as exc: error=f'{type(exc).__name__}: {exc}'
            end=time.perf_counter()
            completion=(usage or {}).get('completion_tokens',0)
            return {'request':i,'latency_s':end-start,'ttft_s':None if first is None else first-start,'completion_tokens':completion,'decode_tps':None if first is None or end<=first else completion/(end-first),'usage':usage,'error':error}
    rows=await asyncio.gather(*(one(i) for i in range(a.requests)))
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.out).write_text(''.join(json.dumps(x)+'\n' for x in rows),encoding='utf-8')
    good=[r for r in rows if not r['error']]
    print(json.dumps({'n':a.requests,'concurrency':a.concurrency,'completed':len(good),'mean_tps':sum(r['decode_tps'] or 0 for r in good)/len(good) if good else None,'aggregate_tps':sum(r['completion_tokens'] for r in good)/max(1,max(r['latency_s'] for r in good)),'rows':rows},ensure_ascii=False))
    await client.close()

asyncio.run(main())
