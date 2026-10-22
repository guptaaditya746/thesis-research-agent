#!/usr/bin/env bash
set -uo pipefail
N=rag-tpl-s1-mixed
C="$CORPORA/$N"
[ -f "$RUNS/agent-baseline/$N/answer.json" ] && exit 0
uv run evaluate agent-baseline --corpus "$C" --out "$RUNS/agent-baseline/$N" --cache "$CACHE/remaining-agent-baseline-gpu3.jsonl" --model orch-model-3 --agent-root "$AGENT_ROOT" --run-id "$N"
