#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 AGENT_ROOT" >&2
  exit 2
fi

root=$(realpath -m "$1")
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$root"
if [[ -n "$(find "$root" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo "agent root must be empty: $root" >&2
  exit 2
fi

uv venv --seed --python 3.13 "$root/agent-venv"
uv pip sync --python "$root/agent-venv/bin/python" --require-hashes "$repo/tests/S5/agent-requirements.lock"
[[ -x "$root/agent-venv/bin/pip" ]] || { echo "seeded pip executable missing" >&2; exit 1; }

mkdir -p "$root/bin" "$root/wheels"
while read -r hash relpath; do
  [[ -n "${hash:-}" ]] || continue
  source_file="${relpath#\*}"
  source_file="${source_file# }"
  base=$(basename "$source_file")
  case "$base" in rg|jq) ;; *) continue ;; esac
  install -m 0555 "$source_file" "$root/bin/$base"
  printf '%s  %s\n' "$hash" "$root/bin/$base" >> "$root/.binaries.sha256"
done < "$repo/tests/S5/binaries.sha256"
sha256sum --check "$root/.binaries.sha256"
rm "$root/.binaries.sha256"

source_root=$(sed -n 's/^AGENT_ROOT=//p' "$repo/tests/S5/agent-root-path.txt")
for wheel in networkx tabulate; do
  wheel_file=$(find "$source_root/wheels" -maxdepth 1 -type f -name "${wheel}-*.whl" -print -quit)
  [[ -n "$wheel_file" ]] || { echo "missing source wheel: $wheel" >&2; exit 1; }
  install -m 0444 "$wheel_file" "$root/wheels/"
done
for wheel in networkx tabulate; do
  compgen -G "$root/wheels/${wheel}-*.whl" >/dev/null || { echo "missing wheel: $wheel" >&2; exit 1; }
done

(
  cd "$root"
  find . -type f ! -name agent-root.sha256 ! -name agent-root.modes -print0 | sort -z | xargs -0 sha256sum > agent-root.sha256
)
chmod -R a-w "$root"
mode_tmp=$(mktemp)
(
  cd "$root"
  { find . -printf '%m %p\n'; printf '444 ./agent-root.modes\n'; } | sort > "$mode_tmp"
)
chmod u+w "$root"
install -m 0444 "$mode_tmp" "$root/agent-root.modes"
chmod a-w "$root"
rm -f "$mode_tmp"
echo "built=$root"
echo "python_runtime=$(readlink -f "$root/agent-venv/bin/python")"
