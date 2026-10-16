#!/usr/bin/env bash
# One run manifest through the batch runner, then the per-run checks and exports (rows 2.9, 2.10), in the
# stack job (srun --jobid <stack job> --overlap), after scripts/e2e-concepts.sh:
#   scripts/e2e-batch.sh agent/manifests/e2e-smoke.json
# 1. writes the effective manifest $RUNS/<name>/manifest.json: the given one with runs_root $RUNS/<name>,
#    concepts $CONCEPTS/<qid>/concept.json and base_url $LITELLM_BASE_URL (E2E_SANDBOX, if set, replaces its
#    sandbox). Running again with a changed manifest, or after a concept changed, stops instead of mixing runs;
# 2. agent batch on it, inside the job's time limit (from $SLURM_JOB_END_TIME, else scontrol); a batch that runs
#    out of time (exit 2) or gives up on a key (exit 1) still gets step 3, and the script ends with its exit code;
# 3. for every finished run not done before: agent verify, pairs, timeline, graph, export-prov.
# The last line, RUNS_ROOT=$RUNS/<name>, is the runs root of this manifest: give it as RUNS to the scoring and the
# web app (one level above it, they would not see these runs). Stops at the first failure.
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
manifest=$(realpath "${1:?usage: scripts/e2e-batch.sh <run manifest, e.g. agent/manifests/e2e-smoke.json>}")
cd "$REPO"
source scripts/e2e-env.sh

name=$(uv run python -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["name"])' "$manifest")
root="$RUNS/$name"
effective="$root/manifest.json"
mkdir -p "$root"
echo "== effective manifest $effective (from $manifest)"
uv run python - "$manifest" "$effective" "$root/concept-hashes.json" <<'PY'
import hashlib, json, os, sys

src, dst, sums = sys.argv[1:4]
raw = open(src, "rb").read()
m = json.loads(raw)
m["runs_root"] = os.path.join(os.environ["RUNS"], m["name"])
m["base_url"] = os.environ["LITELLM_BASE_URL"]
if os.environ.get("E2E_SANDBOX"):
    m["sandbox"] = os.environ["E2E_SANDBOX"]
m["notes"] = (f"Effective copy of {src} (sha256 {hashlib.sha256(raw).hexdigest()}) by scripts/e2e-batch.sh: runs_root "
              "under $RUNS, concepts from $CONCEPTS, base_url from $LITELLM_BASE_URL. " + m.get("notes", ""))
concepts, missing = {}, []
for q in m["questions"]:
    q["concept"] = os.path.join(os.environ["CONCEPTS"], q["id"], "concept.json")
    if os.path.isfile(q["concept"]):
        concepts[q["id"]] = hashlib.sha256(open(q["concept"], "rb").read()).hexdigest()
    else:
        missing.append(q["id"])
if missing:
    sys.exit(f"FAIL no concept.json for {', '.join(missing)} in {os.environ['CONCEPTS']}: run scripts/e2e-concepts.sh first")
if os.path.isfile(dst):  # the proxy's address may change between jobs; nothing else may
    old = json.load(open(dst, encoding="utf-8"))
    if {k: v for k, v in old.items() if k != "base_url"} != {k: v for k, v in m.items() if k != "base_url"}:
        sys.exit(f"FAIL {dst} was written from another manifest or settings; use another $RUNS or move "
                 f"{m['runs_root']} aside")
if os.path.isfile(sums):
    old = json.load(open(sums, encoding="utf-8"))
    changed = sorted(q for q in concepts if old.get(q) not in (None, concepts[q]))
    if changed:
        sys.exit(f"FAIL the concept of {', '.join(changed)} changed since its runs in {m['runs_root']} started; "
                 "move them aside first")
with open(dst, "w", encoding="utf-8") as out:
    json.dump(m, out, indent=2)
    out.write("\n")
with open(sums, "w", encoding="utf-8") as out:
    json.dump(concepts, out, indent=2, sort_keys=True)
    out.write("\n")
print(f"PASS {len(m['questions'])} questions x {len(m['conditions'])} conditions x {m['repeats']} repeats, "
      f"sandbox {m.get('sandbox', 'landlock')}, manifest sha256 {hashlib.sha256(raw).hexdigest()}")
for q, sha in sorted(concepts.items()):
    print(f"     {q} concept sha256 {sha}")
PY

deadline=()
if [[ -z "${SLURM_JOB_END_TIME:-}" && -n "${SLURM_JOB_ID:-}" ]] && command -v scontrol >/dev/null; then
  end=$(scontrol show job "$SLURM_JOB_ID" | grep -o 'EndTime=[^ ]*' | cut -d= -f2 || true)
  if [[ -n "$end" && "$end" != Unknown ]]; then
    deadline=(--deadline "$(date -d "$end" +%s)")
    echo "== job $SLURM_JOB_ID ends $end"
  fi
fi

echo "== agent batch $effective ${deadline[*]}"
rc=0
uv run agent batch "$effective" "${deadline[@]}" || rc=$?
echo "== agent batch exit $rc (0 every run finished, 2 out of time with runs left, 1 a run gave up)"

status=$(uv run agent batch "$effective" --status)
echo "$status"
finished=$(grep -o '[^ ,]*=finished' <<<"$status" | sed 's/=finished$//' || true)
n=0
for run_id in $finished; do
  R="$root/$run_id"
  n=$((n + 1))
  if [[ "$R/graph.ttl" -nt "$R/events.jsonl" ]]; then
    echo "== $run_id: checked and exported before"
    continue
  fi
  echo "== $run_id: verify, pairs, timeline, graph, export-prov"
  uv run agent verify "$R" --corpus "$CORPUS"
  uv run agent pairs "$R"
  uv run agent timeline "$R"
  uv run agent graph "$R" --manifest "$CORPUS/manifest.json"
  uv run agent export-prov "$R"
done
echo "== done: $n finished runs in $root; batch exit $rc"
# Each manifest has its own runs root, so the M4 report never mixes in smoke runs: scoring and the web app
# take this directory as their RUNS (docs/earlier-work.md, Environment).
echo "RUNS_ROOT=$root"
exit "$rc"
