#!/usr/bin/env bash
set -uo pipefail
fail=0
CS=(rag-tpl-s1-mixed rag-claude-pilot-explicit rag-claude-pilot-paraphrased rag-claude-pilot-distributed rag-claude-pilot-complex rag-claude-pilot-contradictory rag-claude-pilot-mixed)
for N in "${CS[@]}"; do
  for S in regex-only cascade cascade-gaps cascade-gaps-escalate; do
    R="$RUNS/$S/$N"
    [ "$S" != cascade-gaps-escalate ] || R="$RUNS/$S/$N-escalate"
    [ -f "$R/answer.json" ] || { echo "FAIL score missing run $S/$N"; fail=1; continue; }
    uv run evaluate score --run "$R" --corpus "$CORPORA/$N" --out "$SCORES/$S/$N" || { echo "FAIL score $S/$N"; fail=1; }
  done
done
exit "$fail"
