#!/usr/bin/env bash
set -euo pipefail
export CUDA_VISIBLE_DEVICES=0
export VLLM_LOGGING_LEVEL=INFO
export VLLM_USE_FLASHINFER_SAMPLER=0
exec /tmp/xepi3167/llm-setup/venv/bin/vllm serve Qwen/Qwen3.8-27B-FP8 \
  --served-model-name orch \
  --tensor-parallel-size 1 \
  --max-model-len 65536 \
  --gpu-memory-utilization 0.92 \
  --enable-prefix-caching \
  --max-num-seqs 8 \
  --reasoning-parser qwen3 \
  --generation-config vllm \
  --port 8001 --host 127.0.0.1
