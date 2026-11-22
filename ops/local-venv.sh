# Put this repo's Python environment on the node's local disk (/tmp) instead of the network disk (ceph).
# Imports from ceph are ~4x slower (46 s vs 12 s for evqa + dspy + rdflib, measured 22 Nov 2026), and every
# pytest worker pays that again. /tmp is cleared when the Slurm job ends, so the first use in a job installs the
# environment from uv's cache (~3 min); later uses in the same job only check it.
#
# Usage (source it, so `uv run` in this shell picks up the environment):
#   source ops/local-venv.sh
#   uv run pytest -q
# Without it, `uv run` still works on the network-disk .venv, just slower.

_repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_PROJECT_ENVIRONMENT="/tmp/${USER}-thesis-venv"
export UV_LINK_MODE=copy          # cache (ceph) and /tmp are different disks: copy, no hardlink warning
(cd "$_repo" && uv sync --locked --all-groups -q) || echo "local-venv: uv sync failed" >&2
unset _repo
