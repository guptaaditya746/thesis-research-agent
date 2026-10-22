#!/usr/bin/env bash
set -uo pipefail
fail=0
# The one missing corpus from the runbook's main engine set, plus six 3-study pilots.
CS=("$CORPORA/rag-tpl-s1-mixed"
    "$CORPORA"/rag-claude-pilot-{explicit,paraphrased,distributed,complex,contradictory,mixed})
for C in "${CS[@]}"; do
  N=$(basename "$C")
  if [ ! -f "$C/manifest.json" ]; then echo "FAIL missing corpus $N"; fail=1; continue; fi
  if [ ! -f "$RUNS/regex-only/$N/answer.json" ]; then
    uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/regex-only" --cache "$CACHE/remaining-regex.jsonl" --extractors regex-only --model orch-model --run-id "$N" || { echo "FAIL regex-only $N"; fail=1; }
  fi
  if [ ! -f "$RUNS/cascade/$N/answer.json" ]; then
    uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/cascade" --cache "$CACHE/remaining-cascade.jsonl" --extractors cascade --strategy all --model orch-model --run-id "$N" || { echo "FAIL cascade-all $N"; fail=1; }
  fi
  if [ ! -f "$RUNS/cascade-gaps/$N/answer.json" ]; then
    uv run evidence run --protocol "$P" --corpus "$C" --out "$RUNS/cascade-gaps" --cache "$CACHE/remaining-gaps.jsonl" --extractors cascade --strategy gaps --model orch-model --run-id "$N" || { echo "FAIL cascade-gaps $N"; fail=1; }
  fi
  if [ ! -f "$RUNS/cascade-gaps-escalate/$N-escalate/answer.json" ]; then
    uv run evidence run --protocol "$PE" --corpus "$C" --out "$RUNS/cascade-gaps-escalate" --cache "$CACHE/remaining-escalate.jsonl" --extractors cascade --strategy gaps --model orch-model --run-id "$N-escalate" || { echo "FAIL cascade-gaps-escalate $N"; fail=1; }
  fi
done
exit "$fail"
