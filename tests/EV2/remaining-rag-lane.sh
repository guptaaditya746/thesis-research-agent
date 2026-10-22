#!/usr/bin/env bash
set -uo pipefail
N=rag-tpl-s1-mixed
C="$CORPORA/$N"
fail=0
if [ ! -f "$RUNS/rag-baseline/$N/answer.json" ]; then
  uv run evaluate rag-baseline --corpus "$C" --out "$RUNS/rag-baseline/$N" --cache "$CACHE/remaining-rag-baseline-gpu2.jsonl" --model orch-model-2 --retrieval global --k 8 || fail=1
fi
if [ -f "$RUNS/rag-baseline/$N/answer.json" ] && [ ! -f "$RUNS/rag-oracle-passages/$N/answer.json" ]; then
  uv run evaluate rag-baseline --oracle-passages --corpus "$C" --out "$RUNS/rag-oracle-passages/$N" --cache "$CACHE/remaining-rag-oracle-gpu2.jsonl" --model orch-model-2 || fail=1
fi
exit "$fail"
