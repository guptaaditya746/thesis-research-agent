#!/usr/bin/env bash
# Replay (C6) and, with --reexec, re-execution (C5) of every finished run of a manifest (row 2.13), after
# scripts/e2e-batch.sh wrote its effective manifest:
#   scripts/e2e-replay.sh agent/manifests/e2e-smoke.json [--reexec]
# Per finished run: agent replay (replay.json); with --reexec also agent reexec (reexec.json, reexec.jsonl), which
# runs every command again and takes about as long as the run's commands did. A missing setup stops the script at
# once; the per-run results are measurements, so every run is done and the summary at the end says which failed
# (exit 1 if a replay failed or a re-execution could not run; differing outputs alone are reported, exit 0).
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
manifest=$(realpath "${1:?usage: scripts/e2e-replay.sh <run manifest> [--reexec]}")
reexec=0
[[ "${2:-}" == --reexec ]] && reexec=1
cd "$REPO"
source scripts/e2e-env.sh

name=$(uv run python -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["name"])' "$manifest")
root="$RUNS/$name"
effective="$root/manifest.json"
[[ -f "$effective" ]] || { echo "FAIL no $effective: run scripts/e2e-batch.sh $1 first" >&2; exit 1; }
status=$(uv run agent batch "$effective" --status)
finished=$(grep -o '[^ ,]*=finished' <<<"$status" | sed 's/=finished$//' || true)

failed=()
summary=()
for run_id in $finished; do
  R="$root/$run_id"
  echo "== $run_id: replay"
  if uv run agent replay "$R"; then line="$run_id replay ok"; else line="$run_id replay FAILED"; failed+=("$run_id"); fi
  if [[ $reexec == 1 ]]; then
    echo "== $run_id: reexec"
    code=0
    uv run agent reexec "$R" --corpus "$CORPUS" || code=$?
    case $code in
      0) line="$line, reexec identical" ;;
      1) line="$line, reexec differs (see $R/reexec.json)" ;;
      *) line="$line, reexec FAILED"; failed+=("$run_id") ;;
    esac
  fi
  summary+=("$line")
done
echo "== summary ($root)"
for line in "${summary[@]}"; do echo "$line"; done
if [[ ${#failed[@]} -gt 0 ]]; then
  echo "FAIL ${failed[*]}"
  exit 1
fi
echo "PASS ${#summary[@]} runs"
