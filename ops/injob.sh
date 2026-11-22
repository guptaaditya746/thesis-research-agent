#!/usr/bin/env bash
# Run a command in the repo on the GPU job, with the Qwen gateway key but the repo's own Python env.
# Usage (login node): srun --jobid <job> --overlap ops/injob.sh uv run evqa ...
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
set -a; source "$REPO/llm-setup/.env"; set +a          # LITELLM_MASTER_KEY only matters
unset UV_PROJECT_ENVIRONMENT VIRTUAL_ENV UV_CACHE_DIR UV_PYTHON_INSTALL_DIR
source "$REPO/ops/local-venv.sh"                         # this repo's env on the node's local disk
# Model calls go through model-queue (:4100) when it runs in this job, else straight to LiteLLM (:4000).
# An explicit LITELLM_BASE_URL wins. The queue keeps evqa, paper-factory and baselines together under the GPU limit.
if [ -z "${LITELLM_BASE_URL:-}" ]; then
  if curl -sf -m 2 http://127.0.0.1:4100/health >/dev/null 2>&1; then
    export LITELLM_BASE_URL=http://127.0.0.1:4100/v1
  else
    export LITELLM_BASE_URL=http://127.0.0.1:4000/v1
    echo "injob: model-queue not running on :4100, calling LiteLLM :4000 directly" >&2
  fi
fi
cd "$REPO"
exec "$@"
