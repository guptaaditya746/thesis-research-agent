#!/usr/bin/env bash
# Concepts for all 12 questions (row 2.3), in the stack job (srun --jobid <stack job> --overlap):
#   scripts/e2e-concepts.sh
# 1. propose: orch-model proposes 1-5 briefs for every question in questions/questions.json whose session in
#    $CONCEPTS has no proposal yet (a question that fails is reported and the script stops after the others);
# 2. pick: brief 1 wherever nothing is picked yet, recorded as picked_by provisional-first (the user may change
#    a pick in the web app before gold is built);
# 3. status: one line per question; exit 0 only when every question has a picked, checked concept.
# Sampling: E2E_CONCEPT_TEMPERATURE (default 0.7), E2E_CONCEPT_SEED (default 1). Running the script again retries
# only the failed questions, in their sessions, also after a fix commit. Seeded sampling tends to give the same
# invalid briefs again, so retry those with another seed (E2E_CONCEPT_SEED=2 scripts/e2e-concepts.sh); each
# session.json lists every attempt's seed and commit. To start a question afresh, move $CONCEPTS/<qid> aside.
# Stops at the first failure.
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO"
source scripts/e2e-env.sh

temperature=${E2E_CONCEPT_TEMPERATURE:-0.7}
seed=${E2E_CONCEPT_SEED:-1}
questions=questions/questions.json

echo "== propose: every question without a proposal ($questions, temperature $temperature, seed $seed) -> $CONCEPTS"
if ! uv run agent concepts propose-all "$questions" --root "$CONCEPTS" --temperature "$temperature" --seed "$seed" \
     --base-url "$LITELLM_BASE_URL"; then
  echo "FAIL some questions have no briefs yet: run the script again to retry only those, with another seed if" \
       "they failed on their briefs (E2E_CONCEPT_SEED=$((seed + 1))), or move \$CONCEPTS/<qid> aside" >&2
  exit 1
fi

echo "== pick: brief 1 wherever nothing is picked (picked_by provisional-first)"
uv run agent concepts pick-all "$questions" --root "$CONCEPTS" --rule first --picked-by provisional-first

echo "== status"
uv run agent concepts status "$questions" --root "$CONCEPTS"
echo "== done: the picks are in $CONCEPTS/picks.json"
