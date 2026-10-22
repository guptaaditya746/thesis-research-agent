#!/usr/bin/env bash
set -uo pipefail
N=rag-tpl-s1-mixed
for S in regex-only cascade cascade-gaps cascade-gaps-escalate; do
  R="$RUNS/$S/$N"; [ "$S" != cascade-gaps-escalate ] || R="$RUNS/$S/$N-escalate"
  B=(); for b in "$RUNS/rag-baseline/$N/answer.json" "$RUNS/agent-baseline/$N/answer.json"; do [ ! -f "$b" ] || B+=(--baseline "$b"); done
  O="$RUNS/oracle/$N/answer.json"; [ ! -f "$O" ] || B+=(--oracle "$O")
  uv run evaluate score --run "$R" --corpus "$CORPORA/$N" "${B[@]}" --out "$SCORES/$S/$N" || echo "FAIL enriched-score $S/$N"
done
for S in cascade cascade-gaps cascade-gaps-escalate regex-only; do
  uv run evaluate compare --corpora "$CORPORA" --out "$SCORES/compare-$S" "$SCORES/$S"/* || echo "FAIL compare $S"
done
for N in rag-tpl-s1-mixed rag-claude-pilot-explicit rag-claude-pilot-paraphrased rag-claude-pilot-distributed rag-claude-pilot-complex rag-claude-pilot-contradictory rag-claude-pilot-mixed; do
  uv run evaluate compare --corpora "$CORPORA" --out "$SCORES/compare-lexical/$N" "$SCORES/cascade-gaps/$N" "$SCORES/cascade-gaps-escalate/$N" || echo "FAIL compare lexical $N"
  uv run evaluate compare --out "$SCORES/compare-funnel/$N" "$SCORES/cascade/$N" "$SCORES/cascade-gaps/$N" || echo "FAIL compare funnel $N"
done
