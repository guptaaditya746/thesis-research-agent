#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "usage: $0 AGENT_ROOT" >&2
  exit 2
fi
root=$(realpath "$1")
(
  cd "$root"
  sha256sum --check --quiet agent-root.sha256
  actual=$(mktemp)
  trap 'rm -f "$actual"' EXIT
  find . -printf '%m %p\n' | sort > "$actual"
  diff -u agent-root.modes "$actual"
)
echo "verified=$root"
