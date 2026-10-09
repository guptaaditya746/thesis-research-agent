# C2 prefix cache and masking replay

Date: 2026-10-09. Node: gammaweb08, Slurm job 7048. Server: Qwen3.8-27B-FP8, vLLM 0.21.0, 65,536 max model length, prefix caching enabled, thinking disabled.

The 60-request sequential replay completed. It retained a stable system/task prefix, appended fixed `(no matches)` observations, and reset older turns immediately before steps 20, 40, and 60. It did not execute any generated shell commands. Prompt size grew only to 1,665 tokens before masking, so this was a cache mechanics check, not a long-context load test.

`vllm:prefix_cache_queries_total` reached 45,720 tokens and `vllm:prefix_cache_hits_total` reached 20,384 tokens. Cache hits increased on 24/60 steps. Between masks, hits increased by 10,976 tokens in steps 2–19, 4,704 in steps 21–39, and 4,704 in steps 41–59. The counters did not rise on the mask steps themselves. This is consistent with a cache-hit dip at masking boundaries, although the dip continued for some following requests.

TTFT at steps 19/20/21 was 0.098/0.110/0.118 s; steps 39/40/41 were 0.173/0.113/0.118 s; steps 59/60 were 0.172/0.111 s. These short prompts did not produce a seconds-long re-prefill. The cache trend is promising, but the requested realistic-history timing criterion remains unverified. vLLM logs note Mamba `align` cache mode is experimental for this architecture.

Raw per-step prompts, outputs, TTFT, usage, and scraped metrics are in `steps.jsonl`; server startup log is `serve.log`.
