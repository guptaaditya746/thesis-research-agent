#!/usr/bin/env bash
# Environment of the end-to-end Slurm session (docs/e2e-build-plan.md, "Environment").
#
#   source scripts/e2e-env.sh    check and export (scripts/e2e-*.sh source it themselves)
#   bash scripts/e2e-env.sh      check only
#
# Run it in the stack job (docs/slurm-m1-runbook.md, "Stack"): srun --jobid <stack job> --overlap --pty bash -l,
# after `set -a; source llm-setup/.env; set +a` for the key. It checks, prints and exports:
#   CORPUS            the frozen Markdown corpus; its manifest.json must hash to the repo's corpus/manifest.json
#                     (or to $E2E_CORPUS_MANIFEST_SHA256 when set)
#   RUNS GOLD CONCEPTS  runs root, gold directory, concept sessions (defaults: runs, gold-data, concepts in the
#                     repo); created if missing, must be writable
#   AGENT_ROOT        the pinned sandbox toolchain; scripts/verify-agent-root.sh must pass
#   LITELLM_BASE_URL  the proxy (default http://127.0.0.1:4000/v1); it must list orch-model, sub-model-1, sub-model-2
#   LITELLM_MASTER_KEY  must be set; never printed, and passed to curl on stdin, not on its command line
# plus CORPUS_MANIFEST_SHA256, the questions file's hash, Landlock and the git commit. It stops at the first failure.
# E2E_SANDBOX=unsandboxed skips the Landlock check (a dry run on a machine without Landlock; never on the cluster).

if (return 0 2>/dev/null); then
  _e2e_sourced=1                 # sourced: leave the caller's shell options alone
else
  _e2e_sourced=0
  set -euo pipefail
fi

_e2e_fail() { echo "FAIL $*" >&2; return 1; }

_e2e_env() {
  local repo want got models abi head m
  repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
  echo "== e2e environment, repo $repo"

  [[ -n "${CORPUS:-}" ]] || { _e2e_fail "CORPUS is not set (the frozen Markdown corpus with manifest.json)"; return 1; }
  [[ -f "$CORPUS/manifest.json" ]] || { _e2e_fail "no $CORPUS/manifest.json"; return 1; }
  want=${E2E_CORPUS_MANIFEST_SHA256:-$(sha256sum "$repo/corpus/manifest.json" | cut -d' ' -f1)}
  got=$(sha256sum "$CORPUS/manifest.json" | cut -d' ' -f1)
  [[ "$got" == "$want" ]] || { _e2e_fail "$CORPUS/manifest.json has sha256 $got, expected $want (the frozen corpus)"; return 1; }
  export CORPUS CORPUS_MANIFEST_SHA256=$got
  echo "PASS CORPUS=$CORPUS manifest sha256=$got"

  export RUNS=${RUNS:-$repo/runs} GOLD=${GOLD:-$repo/gold-data} CONCEPTS=${CONCEPTS:-$repo/concepts}
  for m in RUNS GOLD CONCEPTS; do
    mkdir -p "${!m}" || { _e2e_fail "cannot create $m=${!m}"; return 1; }
    [[ -w "${!m}" ]] || { _e2e_fail "$m=${!m} is not writable"; return 1; }
    echo "PASS $m=${!m}"
  done
  [[ -f "$repo/questions/questions.json" ]] || { _e2e_fail "no questions/questions.json"; return 1; }
  echo "PASS questions/questions.json sha256=$(sha256sum "$repo/questions/questions.json" | cut -d' ' -f1)"

  [[ -n "${AGENT_ROOT:-}" ]] || { _e2e_fail "AGENT_ROOT is not set (build it with scripts/build-agent-root.sh)"; return 1; }
  "$repo/scripts/verify-agent-root.sh" "$AGENT_ROOT" >/dev/null || { _e2e_fail "AGENT_ROOT=$AGENT_ROOT does not verify"; return 1; }
  export AGENT_ROOT
  echo "PASS AGENT_ROOT=$AGENT_ROOT verifies"

  export LITELLM_BASE_URL=${LITELLM_BASE_URL:-http://127.0.0.1:4000/v1}
  [[ -n "${LITELLM_MASTER_KEY:-}" ]] || { _e2e_fail "LITELLM_MASTER_KEY is not set (set -a; source llm-setup/.env; set +a)"; return 1; }
  echo "PASS LITELLM_MASTER_KEY is set"
  models=$(printf 'header = "Authorization: Bearer %s"\n' "$LITELLM_MASTER_KEY" \
           | curl -sS --fail --max-time 30 --config - "$LITELLM_BASE_URL/models") \
    || { _e2e_fail "the proxy at $LITELLM_BASE_URL does not answer /models"; return 1; }
  for m in orch-model sub-model-1 sub-model-2; do
    [[ "$models" == *"\"$m\""* ]] || { _e2e_fail "the proxy does not serve $m"; return 1; }
  done
  echo "PASS LITELLM_BASE_URL=$LITELLM_BASE_URL serves orch-model, sub-model-1, sub-model-2"

  command -v uv >/dev/null || { _e2e_fail "uv is not on PATH"; return 1; }
  (cd "$repo" && uv run agent --help >/dev/null) || { _e2e_fail "uv run agent does not start (uv sync --locked?)"; return 1; }
  if [[ "${E2E_SANDBOX:-}" == unsandboxed ]]; then
    echo "WARN E2E_SANDBOX=unsandboxed: runs go without Landlock (never on the cluster)"
  else
    abi=$(cd "$repo" && uv run python -c 'from agent import sandbox; print(sandbox.landlock_abi() or "")')
    [[ -n "$abi" ]] || { _e2e_fail "no Landlock on this node; the runs need it"; return 1; }
    echo "PASS Landlock ABI $abi"
  fi
  head=$(git -C "$repo" rev-parse HEAD 2>/dev/null || echo unknown)
  if ! git -C "$repo" diff --quiet HEAD 2>/dev/null; then head="$head (with uncommitted changes)"; fi
  echo "PASS git $head"
}

if [[ $_e2e_sourced == 1 ]]; then
  _e2e_env
else
  _e2e_env
  exit $?
fi
