from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
from openai import OpenAI
from transformers import AutoTokenizer


MODEL = "Qwen/Qwen3.8-27B-FP8"
REVISION = "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a"
METRICS = "http://127.0.0.1:8001/metrics"
client = OpenAI(base_url="http://127.0.0.1:4000/v1", api_key=os.environ["LITELLM_MASTER_KEY"], timeout=600)
tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION, local_files_only=True)
Path("tests/C2b").mkdir(parents=True, exist_ok=True)
output = open("tests/C2b/steps.jsonl", "w", encoding="utf-8")


def make_content(target_tokens: int, label: str) -> str:
    corpus = Path(os.environ.get("CORPUS_DIR", "/mnt/ceph/storage/data-tmp/2026/xepi3167/research-agent-corpus-docling-2.110.0"))
    files = sorted(corpus.glob("*.md"))
    if not files:
        raise RuntimeError(f"no converted Markdown files found in {corpus}")
    offset = 0 if label == "unmasked" else max(1, len(files) // 3)
    files = files[offset:] + files[:offset]
    token_ids = tokenizer.encode(f"Unique benchmark passage for {label}.\n", add_special_tokens=False)
    for path in files:
        passage = f"\n\nDocument {path.stem}\n" + path.read_text(encoding="utf-8", errors="replace")
        token_ids.extend(tokenizer.encode(passage, add_special_tokens=False))
        if len(token_ids) >= target_tokens:
            return tokenizer.decode(token_ids[:target_tokens], skip_special_tokens=False)
    raise RuntimeError(f"only {len(token_ids)} tokens available in {corpus}; need {target_tokens}")


def metric(name: str) -> float:
    response = httpx.get(METRICS, timeout=10)
    response.raise_for_status()
    values = []
    for line in response.text.splitlines():
        if line.startswith("#") or not line.startswith(name):
            continue
        try:
            values.append(float(line.rsplit(None, 1)[1]))
        except (IndexError, ValueError):
            continue
    if not values:
        raise RuntimeError(f"metric not found: {name}")
    return sum(values)


def replay(label: str, masked: bool) -> list[dict]:
    long_history = make_content(30_000, label) + "\n\nFor this benchmark, write about 300 tokens describing a useful next research step. Keep the continuation detailed."
    short_summary = "Summary of earlier steps: papers were searched for retrieval methods and evidence. For this benchmark, write about 300 tokens describing a useful next research step, with detail."
    steps = []
    messages = [{"role": "user", "content": long_history}]
    for step in range(1, 21):
        if masked and step == 10:
            messages = [{"role": "user", "content": short_summary}]
        before_hits = metric("vllm:prefix_cache_hits_total")
        before_queries = metric("vllm:prefix_cache_queries_total")
        started = time.perf_counter()
        first_token = None
        completion_tokens = None
        prompt_tokens = None
        answer = []
        stream = client.chat.completions.create(
            model="orch-model", messages=messages, max_tokens=300, temperature=0.2,
            stream=True, stream_options={"include_usage": True},
            extra_body={"min_tokens": 300, "chat_template_kwargs": {"enable_thinking": False}},
        )
        for chunk in stream:
            if first_token is None and chunk.choices:
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None) or getattr(delta, "reasoning_content", None):
                    first_token = time.perf_counter() - started
                if getattr(delta, "content", None):
                    answer.append(delta.content)
            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens
                completion_tokens = chunk.usage.completion_tokens
        total = time.perf_counter() - started
        if first_token is None:
            first_token = total
        after_hits = metric("vllm:prefix_cache_hits_total")
        after_queries = metric("vllm:prefix_cache_queries_total")
        row = {
            "run": label, "step": step, "masked_at_step_10": masked,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens, "ttft_seconds": first_token,
            "total_seconds": total, "prefix_cache_hits_delta": after_hits - before_hits,
            "prefix_cache_queries_delta": after_queries - before_queries,
        }
        steps.append(row)
        print(json.dumps(row), flush=True)
        output.write(json.dumps(row) + "\n")
        output.flush()
        messages.append({"role": "assistant", "content": "".join(answer)})
        if step < 20:
            messages.append({"role": "user", "content": f"Observation: no matches on fixed command step {step}. Continue with a detailed response of about 300 tokens for the benchmark."})
    return steps


if os.environ.get("C2B_ONLY_MASKED"):
    replay("masked_step_10", True)
else:
    replay("unmasked", False)
    replay("masked_step_10", True)
output.close()
client.close()
