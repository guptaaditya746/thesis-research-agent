#!/usr/bin/env bash
# Four-domain benchmark, end to end (22 Nov 2026). Every step reuses what exists, so a stopped run restarts.
#   1. papers:    paperfactory run per field (joined world, 43 planned papers; keeps every paper that passes)
#   2. export:    passed papers -> data/{seed,dataset}/bench_<field> (fact rows, entities, field words)
#   3. questions: evqa seed pfbench bench_<field> (40 questions, gold by code)
#   4. runs:      ours, closed book and the 4 baselines per domain (configs/evqa/bench4/), each scored with --text
#   5. compare:   evqa compare per domain -> runs/evqa/bench4-compare/<field>.json
# Usage (login node): ops/bench4.sh <slurm job id> [field ...]      (default: law llm materials medicine)
# Detached:           nohup ops/bench4.sh <job> > runs/bench4.log 2>&1 &
# Stop after one step: STOP_AFTER=papers|export|questions|runs ops/bench4.sh <job>
set -euo pipefail
JOB="${1:?slurm job id of the LLM stack (squeue -u \$USER)}"; shift || true
FIELDS=("${@:-law llm materials medicine}")
read -r -a FIELDS <<< "${FIELDS[*]}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PF="$REPO/services/paper-factory"
SYSTEMS=(qwen closed-book pqa-rag pqa-agent pqa-agent-fixed long-context)
log() { echo "[$(date '+%F %T')] $*"; }
stop() { [ "${STOP_AFTER:-}" = "$1" ] && { log "stopping after $1"; exit 0; } || true; }

squeue -j "$JOB" -h -o %T | grep -q RUNNING || { echo "job $JOB is not running (squeue -u \$USER)"; exit 1; }

# 1. papers (the four fields share the gateway's slots, so they run side by side)
for f in "${FIELDS[@]}"; do
  log "papers: $f"
  (cd "$PF" && srun --jobid "$JOB" --overlap ops/injob.sh uv run paperfactory run \
      --config "src/paperfactory/configs/qwen/bench-$f.json" > "runs/paperfactory/bench-$f.log" 2>&1) &
done
wait
for f in "${FIELDS[@]}"; do
  n=$(python3 -c "import json;print(len(json.load(open('$PF/runs/paperfactory/bench-$f/tagged.json'))['papers']))")
  log "papers: $f passed $n of 43"
done
stop papers

# 2. export (code only)
for f in "${FIELDS[@]}"; do
  (cd "$PF" && uv run paperfactory export-workbench --config "src/paperfactory/configs/qwen/bench-$f.json" \
      --domain "bench_$f" --data-dir ../../data)
done
stop export

# 3. questions (code only)
for f in "${FIELDS[@]}"; do
  (cd "$REPO" && uv run evqa seed pfbench "bench_$f")
done
stop questions

# 4. runs: one system at a time per domain (one orch workload at a time, docs/prompt-writing.md)
for f in "${FIELDS[@]}"; do
  for s in "${SYSTEMS[@]}"; do
    log "run: $f $s"
    (cd "$REPO" && srun --jobid "$JOB" --overlap ops/injob.sh uv run evqa run \
        --config "configs/evqa/bench4/$f-$s.yaml" --text) || log "run failed: $f $s (continuing)"
  done
done
stop runs

# 5. compare
mkdir -p "$REPO/runs/evqa/bench4-compare"
for f in "${FIELDS[@]}"; do
  runs=$(ls -d "$REPO"/runs/evqa/bench4-"$f"-* 2>/dev/null | tr '\n' ' ')
  # shellcheck disable=SC2086
  (cd "$REPO" && uv run evqa compare $runs --out "runs/evqa/bench4-compare/$f.json") || log "compare failed: $f"
done
log "done"
