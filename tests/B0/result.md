# B0 result

Status: PASS on Slurm job 7048, node gammaweb08.

- Built fresh root `/mnt/ceph/storage/data-tmp/2026/xepi3167/agent-root-infra-final-3` in 105.33 s.
- `uv venv --seed --python 3.13` plus the hash-locked `uv pip sync` installed the pinned agent packages and left a usable `pip` executable for the offline wheel test.
- Installed the checked `rg` and `jq` binaries and copied the `networkx` and `tabulate` wheels from the prior S5c root.
- Root size: 266 MB; file hash manifest: 5,867 files; mode manifest: 6,526 entries. `scripts/verify-agent-root.sh` passed.
- Build and verification logs: `build-3.log`, `time-3.txt`, and `verify-3.log`.

Two early attempts exposed issues in the new builder/verifier: writing manifests after recursively removing write bits, then comparing a duplicate self-entry in the mode manifest. Both were corrected before the successful fresh build and verification.
