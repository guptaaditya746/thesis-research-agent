#!/usr/bin/env bash
#SBATCH --job-name=agent-corpus
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --output=tests/D5/slurm-%j.out

set -euo pipefail
repo=${SLURM_SUBMIT_DIR:-$PWD}
cd "$repo"
corpus=${CORPUS:-/mnt/ceph/storage/data-tmp/2026/xepi3167/research-agent-corpus-docling-2.110.0}
python=${DOCLING_PYTHON:-../git/docling_thesis_demo/.venv/bin/python}
test -x "$python"
status=0
"$python" scripts/build-corpus.py \
  --pdf-dir ../final-final-frontend/corpus_acl_emnlp_2025_input \
  --anthology-manifest ../final-final-frontend/corpus_acl_emnlp_2025_input/manifest.tsv \
  --samples-manifest ../final-final-frontend/samples/manifest.tsv \
  --corpus "$corpus" \
  --manifest-copy data/corpus/manifest.json || status=$?
chmod -R a-w "$corpus"
exit "$status"
