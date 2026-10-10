# C2b: 30k-token prefix cache and masking replay

Date: 2026-10-10. Model: `Qwen/Qwen3.8-27B-FP8`, through LiteLLM, thinking disabled, 300 output tokens per step. Attention block size from `tests/L1/runtime/orch.log`: 784 tokens. Prompts were built from converted paper Markdown, with a unique first passage for each sequence so the first request measured a cold cache. vLLM accepted `min_tokens=300`; all 40 requests completed with exactly 300 output tokens.

- Unmasked: cold step 1, 30,035 prompt tokens, 12.025 s TTFT, zero cache hits. Steps 2–20 averaged 0.351 s TTFT. At 30,379 prompt tokens (step 9), 29,792 cache-hit tokens; at step 15, 30,576 hit tokens after crossing the next 784-token boundary.
- Masked sequence: cold step 1, 30,035 prompt tokens, 11.770 s TTFT, zero cache hits. Step 9, 30,379 tokens / 0.413 s TTFT / 29,792 hits. Masking at step 10 reduced the prompt to 47 tokens; TTFT was 0.109 s and hits were zero. Step 11 was 91 tokens / 0.106 s / zero hits.
- Mean TTFT after the cold first step: 0.351 s unmasked, 0.236 s for the masked sequence. The latter includes the short post-mask prompts. Summed prefix-cache hit/query ratios were 93.7% unmasked and 86.7% masked.

Cold prefill at 30k was about 2,495 prompt tokens/s. This supports keeping Qwen3.8 as the orchestrator: a cold long prompt costs about 12 seconds, while matching cached history returns a first token in about 0.3–0.6 seconds. Masking sharply reduces prompt length and prefill latency.

Per-step metrics: `steps.jsonl`; complete output: `replay.log`. An earlier synthetic repeated-token attempt and the warm-cache trial are retained as diagnostic logs and are not used for these numbers.
