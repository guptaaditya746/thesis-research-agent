#!/usr/bin/env bash
# Concepts for all 12 questions (row 2.3), in the stack job (srun --jobid <stack job> --overlap):
#   scripts/e2e-concepts.sh
# 1. propose: orch-model proposes 1-5 briefs for every question in questions/questions.json whose session in
#    $CONCEPTS has no proposal yet (a question that fails is reported; run the script again to retry only those);
# 2. pick: brief 1 wherever nothing is picked yet, recorded as picked_by provisional-first (the user may change
#    a pick in the web app before gold is built);
# 3. status: one line per question; exit 0 only when every question has a picked, checked concept.
# The sampling settings are part of each session: E2E_CONCEPT_TEMPERATURE (default 0.7), E2E_CONCEPT_SEED
# (default 1); keep them when running the script again. Stops at the first failure.
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO"
source scripts/e2e-env.sh

temperature=${E2E_CONCEPT_TEMPERATURE:-0.7}
seed=${E2E_CONCEPT_SEED:-1}
questions=questions/questions.json

echo "== propose: every question without a proposal ($questions, temperature $temperature, seed $seed) -> $CONCEPTS"
uv run agent concepts propose-all "$questions" --root "$CONCEPTS" --temperature "$temperature" --seed "$seed" \
  --base-url "$LITELLM_BASE_URL"

echo "== pick: brief 1 wherever nothing is picked (picked_by provisional-first)"
uv run agent concepts pick-all "$questions" --root "$CONCEPTS" --rule first --picked-by provisional-first

echo "== status"
uv run agent concepts status "$questions" --root "$CONCEPTS"
echo "== done: the picks are in $CONCEPTS/picks.json"
