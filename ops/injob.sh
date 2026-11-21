#!/usr/bin/env bash
# Run a command in the repo on the GPU job, with the Qwen gateway key but the repo's own Python env.
# Usage (login node): srun --jobid <job> --overlap ops/injob.sh uv run evqa ...
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
set -a; source "$REPO/llm-setup/.env"; set +a          # LITELLM_MASTER_KEY only matters
unset UV_PROJECT_ENVIRONMENT VIRTUAL_ENV UV_CACHE_DIR UV_PYTHON_INSTALL_DIR
export LITELLM_BASE_URL=http://127.0.0.1:4000/v1
cd "$REPO"
exec "$@"
