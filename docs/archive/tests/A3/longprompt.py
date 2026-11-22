from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from openai import OpenAI
from transformers import AutoTokenizer


parser = argparse.ArgumentParser()
parser.add_argument('--model-path', default='Qwen/Qwen3-30B-A3B-Instruct-2507-FP8')
parser.add_argument('--served-model', default='heavy-model')
parser.add_argument('--base-url', default='http://127.0.0.1:8002/v1')
parser.add_argument('--lengths', nargs='+', type=int, default=[16000, 32000, 48000, 60000])
parser.add_argument('--output', default='tests/A3/longprompt.jsonl')
parser.add_argument('--enable-thinking', action='store_true')
args = parser.parse_args()

repo = Path(__file__).resolve().parents[2]
corpus = repo / 'final-final-frontend/UI/files/harness/corpus_data/outlines'
source = '\n\n'.join(p.read_text(encoding='utf-8') for p in sorted(corpus.glob('*.md')))
tokenizer = AutoTokenizer.from_pretrained(args.model_path)
tokens = tokenizer.encode(source, add_special_tokens=False)
if not tokens:
    raise SystemExit('corpus has no tokens')
client = OpenAI(base_url=args.base_url, api_key=os.getenv('LLM_BACKEND_KEY', 'x'), timeout=3600)
out = Path(args.output)
out.parent.mkdir(parents=True, exist_ok=True)
with out.open('w', encoding='utf-8') as log:
    for target in args.lengths:
        offset = (target * 17) % len(tokens)
        rotated = tokens[offset:] + tokens[:offset]
        prompt_ids = (rotated * ((target + len(rotated) - 1) // len(rotated)))[:target]
        prompt = tokenizer.decode(prompt_ids, skip_special_tokens=True)
        start = time.perf_counter()
        first = None
        usage = None
        finish_reason = None
        response_text = []
        reasoning_text = []
        try:
            stream = client.chat.completions.create(
                model=args.served_model,
                messages=[
                    {'role': 'system', 'content': 'Summarize the provided research corpus in no more than 200 tokens.'},
                    {'role': 'user', 'content': prompt + '\n\nPlease summarize the research corpus above in at most 200 tokens.'},
                ],
                max_tokens=200,
                temperature=0,
                stream=True,
                stream_options={'include_usage': True},
                extra_body={'chat_template_kwargs': {'enable_thinking': args.enable_thinking}},
            )
            for chunk in stream:
                now = time.perf_counter()
                if chunk.choices and first is None:
                    delta = chunk.choices[0].delta.model_dump()
                    if any(delta.get(k) for k in ('content', 'reasoning_content', 'reasoning')):
                        first = now
                if chunk.choices:
                    delta = chunk.choices[0].delta.model_dump()
                    if delta.get('content'):
                        response_text.append(delta['content'])
                    for key in ('reasoning_content', 'reasoning'):
                        if delta.get(key):
                            reasoning_text.append(delta[key])
                if chunk.choices and chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason
                if chunk.usage:
                    usage = chunk.usage.model_dump()
            total = time.perf_counter() - start
            row = {'requested_input_tokens': target, 'usage': usage, 'finish_reason': finish_reason, 'ttft_seconds': None if first is None else first - start, 'total_seconds': total, 'content': ''.join(response_text), 'reasoning': ''.join(reasoning_text), 'error': None}
        except Exception as exc:
            row = {'requested_input_tokens': target, 'usage': usage, 'finish_reason': finish_reason, 'ttft_seconds': None, 'total_seconds': time.perf_counter() - start, 'content': ''.join(response_text), 'reasoning': ''.join(reasoning_text), 'error': f'{type(exc).__name__}: {exc}'}
        print(json.dumps(row), flush=True)
        log.write(json.dumps(row, ensure_ascii=False) + '\n')
