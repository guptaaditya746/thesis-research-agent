#!/bin/bash
#SBATCH --job-name=research-agent-s2-fake
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:30:00
#SBATCH --output=tests/S2/slurm-%j.log
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
exec python3 tests/S2/fake_run.py
