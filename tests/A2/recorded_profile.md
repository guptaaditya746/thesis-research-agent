# A2 current server profile and prior measurements

This uses the existing `final-final-llm-setup/profiles/a100-3x40.yaml` and completed run `runtime/20261007T152525Z-c594d61a` on gammaweb08 (Slurm job 6951). It is not the plan's original 2-GPU ORCH / 1-GPU quantized SUB split; retain that as a separate trial if that exact pairing is needed.

| Setup role | Model | GPUs | max_model_len | Weight load | KV tokens | vLLM maximum concurrency |
|---|---|---:|---:|---:|---:|---:|
| Heavy | Qwen/Qwen3-30B-A3B-Instruct-2507-FP8 | 1 | 32768 | 220.57 s | 69,296 | 2.11 × 32768-token requests |
| Lite | ibm-granite/granite-4.1-8b | 1 | 32768 | 118.30 s | 127,728 | 3.90 × 32768-token requests |
| Embed | Qwen/Qwen3-Embedding-0.6B | 1 | 8192 | 7.71 s | 301,312 | 36.78 × 8192-token requests |
| Thinking candidate | Qwen/Qwen3-30B-A3B-Thinking-2507-FP8 | 1 | 32768 | 11.47 s (warm cache) | 64,848 | 1.98 × 32768-token requests |
| Latest official candidate | Qwen/Qwen3.8-27B-FP8 | 1 | 65536 | 179.82 s (warm cache) | 79,371 | 1.21 × 65536-token requests |

All three servers reached application startup on the recorded run. Heavy listened on loopback port 8002, Lite on 8003, Embed on 8001. The current repository deliberately binds to 127.0.0.1. These are setup-stack results, not externally reachable `8001/8002` test endpoints. No concurrent load or fresh max-model-len sweep has been run for the requested ORCH/SUB roles.

The direct thinking-candidate startup used vLLM 0.21.0, 1×A100, and a warmed weights cache: 29.53 GiB model memory, max concurrency 1.98 at 32,768 tokens. Initial engine startup failed because FlashInfer attempted JIT sampling compilation but `nvcc` was unavailable (`/usr/local/cuda` missing); `VLLM_USE_FLASHINFER_SAMPLER=0` selected vLLM's PyTorch sampler and startup succeeded. The official Qwen3.8-FP8 startup also used the PyTorch sampler fallback. It loaded 28.9 GiB of model memory, exposed a 65,536 max model length, and had 79,371 KV tokens, for 1.21× concurrency at that length. End-to-end startup (command to API health) was about 8m27s, including 179.82s weight load, 113.76s compilation, and multimodal warmup. Cached models also include `Qwen/Qwen3.5-4B`, `Qwen/Qwen3.5-9B`, `Qwen/Qwen3.6-27B`, `Qwen/Qwen3.6-27B-FP8`, and a small metadata-only community Qwen3.8 AWQ cache entry.
