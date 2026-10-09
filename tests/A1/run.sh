#!/usr/bin/env bash
set -u
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python3 -c 'import torch; print(torch.__version__, torch.version.cuda, torch.cuda.device_count())'
python3 -c 'import vllm; print(vllm.__version__)'
df -h /scratch "$HOME" 2>&1 | head
nproc
free -g | head -2
