#!/usr/bin/env bash
# Four-domain benchmark on Claude Haiku, no GPU stack (24 Nov 2026): answer + score + compare, in this job.
#   runs:    ours, closed book and the 4 baselines per domain (configs/evqa/bench4h/), side by side, each scored with
#            --text by Haiku (reader and judge); baselines and the scorer call Haiku through evqa.claude_gateway
#   compare: evqa compare per domain -> runs/evqa/bench4h-compare/<field>.json
# Usage: ops/bench4h.sh [field ...]   (default: law llm materials medicine); a finished run is reused by evqa run.
# Second Claude account: CLAUDE_CONFIG_DIR=~/.claude-acct2 GATEWAY_PORT=4198 EVQA_SLOT_DIR=data/cache/claude-slots-acct2
#   (claude -p, the gateway and the slot caps then belong to that account).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
FIELDS=("${@:-law llm materials medicine}")
read -r -a FIELDS <<< "${FIELDS[*]}"
read -r -a SYSTEMS <<< "${SYSTEMS:-ours closed-book pqa-rag pqa-agent pqa-agent-fixed long-context}"   # SYSTEMS="ours" runs one
PORT="${GATEWAY_PORT:-4199}"
M=claude:claude-haiku-5-5
export LITELLM_BASE_URL="http://127.0.0.1:$PORT/v1" EVQA_MAX_CALLS="${EVQA_MAX_CALLS:-12}"
log() { echo "[$(date '+%F %T')] $*"; }
# shellcheck disable=SC1091
source ops/local-venv.sh >/dev/null
# the baselines' own venv, once, before the parallel runs (evqa.baselines.baseline_env uses the same path)
UV_PROJECT_ENVIRONMENT="$UV_PROJECT_ENVIRONMENT-baselines" uv sync --locked --project baselines -q

curl -sf "$LITELLM_BASE_URL/models" >/dev/null || {
  log "starting the claude gateway on port $PORT"
  nohup uv run python -m evqa.claude_gateway --port "$PORT" --parallel "${GATEWAY_PARALLEL:-16}" \
      >> "runs/evqa/claude_gateway-$PORT.log" 2>&1 &
  for _ in $(seq 30); do curl -sf "$LITELLM_BASE_URL/models" >/dev/null && break; sleep 2; done
}

mkdir -p runs/evqa/bench4h-logs runs/evqa/bench4h-compare
for f in "${FIELDS[@]}"; do
  for s in "${SYSTEMS[@]}"; do
    log "run: $f $s"
    uv run evqa run --config "configs/evqa/bench4h/$f-$s.yaml" --text --text-model "$M" --judge-model "$M" \
        > "runs/evqa/bench4h-logs/$f-$s.log" 2>&1 && log "done: $f $s" || log "run failed: $f $s (see log)" &
  done
  wait
  runs=$(ls -d runs/evqa/bench4h-"$f"-*/ 2>/dev/null | tr '\n' ' ')
  # shellcheck disable=SC2086
  uv run evqa compare $runs --out "runs/evqa/bench4h-compare/$f.json" || log "compare failed: $f"
done
log "all done"
