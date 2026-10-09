# Runbook: round 3, the sandbox session on Slurm

You are running the round-3 tests on the Webis Slurm cluster. They decide how every agent command is
isolated, which is the blocker found in round 2 (`tests/RESULTS.md`: A6, S3, S4). Read first:
`docs/infra-tests-next.md`, section "Round 3", which says why each test exists. Background:
`docs/decisions-after-tests.md` §4 (sandbox) and `docs/plan.md` §5.3–5.4 (harness, log outside the agent).

## Rules

The same rules as `docs/codex-infra-runbook.md` ("Rules"), with these changes:

- Branch: `infra-round-3` in this repo. Never commit to or push `main`. Push the branch at the end if you can.
- Submodule changes go on the existing `agent-layout` branch of `related/final-final-llm-setup`.
  **Push that branch first** (`git push origin agent-layout`): it holds the round-2 layout and exists only
  on the node.
- **Never kill or signal a real process to test a permission.** Use `kill -0 <pid>` (it only checks
  permission) and read-only probes. Never read a secret into a log: when a test reads `.env`, an SSH key or
  `/proc/<pid>/environ`, record only "readable" or "denied" and the byte count, never the content.
- Save logs under `tests/<id>/`, add one row per test to `tests/RESULTS.md`, and use `NOT RUN` with the
  reason when a test cannot run. Steps marked **USER** need the user: stop and ask.

## 0. Setup

```bash
cd <this repo on Ceph>
git fetch && git checkout -b infra-round-3 origin/main
git submodule update --init --recursive
(cd related/final-final-llm-setup && git checkout agent-layout && git push origin agent-layout)
set -a; source related/final-final-llm-setup/.env; set +a
```

Steps 1–3 need only a CPU shell on a GPU node of the same kind (`srun --pty` for 2 hours). Steps 4–6 need
the model stack running (`LLM_SETUP_PROFILE=profiles/agent-3x40.yaml sbatch slurm/llm-stack.sbatch`, then
`srun --jobid <id> --overlap --pty bash -l`). If the kernel check in step 1 fails, still run steps 3, 5 and 6.

## Step 1: S5a, which Landlock the kernel offers (5 min)

`/sys/kernel/security/lsm` only says whether Landlock is on. The ABI version says what it can block:
ABI ≥ 1 files (kernel 5.13), ≥ 4 TCP bind/connect (6.7), ≥ 6 signals and abstract unix sockets (6.12).

```bash
uname -r; cat /sys/kernel/security/lsm; echo
python3 - <<'EOF'
import ctypes, os
libc = ctypes.CDLL(None, use_errno=True)
# landlock_create_ruleset(NULL, 0, LANDLOCK_CREATE_RULESET_VERSION) returns the ABI version (x86_64 syscall 444)
abi = libc.syscall(444, None, ctypes.c_size_t(0), ctypes.c_uint32(1))
print("landlock ABI:", abi, "" if abi >= 0 else os.strerror(ctypes.get_errno()))
EOF
```

Record kernel, LSM list and ABI in `tests/S5/kernel.txt`. Decision: ABI ≥ 4 → continue with Landlock.
ABI 1–3 → files only; network must come from elsewhere, so mark S5b PARTIAL and continue for the file
part. Landlock absent → mark S5b and S6 NOT RUN; the fallback is X1 (Docker on Omen) or the admins.

## Step 2: S5b and S6, commands under Landlock (2 h)

### Build the wrapper

Use `landrun` (github.com/Zouuup/landrun) if its licence allows use and a release binary runs on the node;
otherwise write `tests/S5/sandbox.py` (about 80 lines, ctypes, no dependencies): create a ruleset with every
filesystem right the ABI knows and, for ABI ≥ 4, `LANDLOCK_ACCESS_NET_CONNECT_TCP` and `BIND_TCP` with no
allowed ports; allow read+execute on `/usr`, `/lib*`, `/bin`, `/etc`, the agent venv and the corpus; allow
read+write on one scratch directory on Ceph; for ABI ≥ 6 add the signal and abstract-unix-socket scopes;
`prctl(PR_SET_NO_NEW_PRIVS)`, `landlock_restrict_self`, then `execve("bash", "-c", cmd)`. Run each command
with `setsid` and kill its process group when it ends. Record the wrapper and its exact command line.

Use `tests/A6/corpus` (one file) and a scratch directory `tests/S5/scratch` on Ceph, not `/tmp`.

### S5b, the A6 checks

Under the wrapper: `python3 -c "print(1+1)"`; `grep -c hello /corpus/p1.md`; writing to the corpus fails;
`curl -m 5 https://example.com` fails; `curl -m 3 http://127.0.0.1:8001/v1/models` and the same for 8002,
8004, 4000 and 8010 fail (stack running for this part); writing to scratch works; reading `$HOME` outside
the allowed paths fails; `timeout 2 bash -c 'while :; do :; done'; echo $?` gives 124.

### S6, escape checks

Each from inside the wrapper, recording allowed / denied only:

1. `kill -0` on the PIDs of vLLM, LiteLLM, the status API, the tunnel `ssh` (if running) and the harness
   shell. ABI < 6 is expected to allow it: say so.
2. `test -r /proc/<litellm-pid>/environ` and `wc -c` on it (never `cat`).
3. `test -r` on `~/.ssh/id_ed25519_webis_tunnel`, the repo `.env`, `~/.git-credentials`.
4. UDP: `python3 -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b'x', ('1.1.1.1', 53)); print('sent')"`.
   Landlock never controls UDP, so expect "sent"; record it.
5. Unix sockets: connect to an abstract socket and to a pathname socket created by a helper outside the
   sandbox; `env | grep -c SSH_AUTH_SOCK`.
6. `nohup sleep 1000 &` inside a command: is the process gone after the step's process group is killed?

Pass: 1–3 denied (or explained by the ABI), 6 gone. Every "allowed" is a finding; list it in
`tests/S6/findings.md` with the ABI that would close it.

## Step 3: S5c and S1b, the agent's toolchain and limits (1 h)

### S5c, a read-only, pinned toolchain

1. `tests/S5/agent-requirements.in`: `numpy pandas regex rapidfuzz pyyaml scikit-learn`. Lock it with
   `uv pip compile --generate-hashes -o tests/S5/agent-requirements.lock`.
2. At job start (internet still allowed outside the sandbox): `uv venv $AGENT_ROOT/agent-venv` and
   `uv pip sync --require-hashes tests/S5/agent-requirements.lock` into it, with `$AGENT_ROOT` on Ceph.
3. Add pinned static binaries of ripgrep and jq to `$AGENT_ROOT/bin`, each checked against a sha256 you
   record in `tests/S5/binaries.sha256`.
4. `chmod -R a-w $AGENT_ROOT` and write a manifest: `find $AGENT_ROOT -type f -print0 | sort -z | xargs -0 sha256sum > tests/S5/agent-root.sha256`.
5. Local wheel store (uv has no download command, so use pip):
   `pip download --only-binary=:all: -d $AGENT_ROOT/wheels networkx tabulate`, then inside the sandbox
   `pip install --no-index --find-links $AGENT_ROOT/wheels --target $SCRATCH/pylib networkx` and
   `PYTHONPATH=$SCRATCH/pylib python3 -c "import networkx"`. A package outside the store must fail cleanly.
6. Inside the sandbox, `chmod -R u+w $AGENT_ROOT` must fail with Landlock (it would succeed without it),
   and the manifest must still verify after all steps.

### S1b, memory limits that still let numpy and pandas load

For `ulimit -v` in {2, 4, 8, 16} GB: does `python3 -c "import numpy, pandas"` work, and does
`python3 -c "x=' '*10**11"` fail with MemoryError? Record the smallest working value. Also record
`cat /sys/fs/cgroup/$(cut -d: -f3 /proc/self/cgroup)/memory.max` and the `anon` and `file` lines of
`memory.stat` with the stack loaded (S1 read `memory.current`, which includes page cache). Do not run the
allocation without a limit.

## Step 4: L6, what the proxy does to the requests the harness will send (45 min, stack running)

`tests/L6/probe.py`, through `http://127.0.0.1:4000/v1` with `LITELLM_MASTER_KEY`:

1. **Timeout.** One `orch-model` request with a ~60k-token prompt and `max_tokens 4096`, asking for a long
   answer. LiteLLM's `request_timeout` is 120 s with no retry; the worst case (26 s to first token + 4096
   tokens at 41.6 tok/s ≈ 124 s) is above it. Record elapsed time and error. Then one `sub-model` request
   queued behind three busy ones: does the wait count against the 120 s?
2. **Structured output.** 20 `orch-model` calls with `response_format: {type: json_schema}` using the
   research-brief schema from `docs/plan.md` §5.2 (enums, nested arrays, `minItems`), thinking off.
   Validate each with `jsonschema`. Record the valid count and whether the schema reached vLLM (vLLM log).
3. **Sampling.** Does `seed` reach vLLM? 10 identical `temperature 0`, `seed 1` calls alone, then 10 while
   `sub-model` is under load: how many distinct outputs in each case?

## Step 5: R2, concurrent appends on Ceph (30 min)

`tests/R2/append.py`: 8 processes each append 10,000 JSON lines of 1–16 KB to one file in a Ceph
directory, first with `O_APPEND` only, then with `O_APPEND` and `fcntl.flock`, both with `fsync` per line.
Check that every line parses and the counts are exactly 80,000. Record p50/p99 `fsync` latency.

## Step 6: R3, pin what was served (15 min)

For the three served models record the Hugging Face snapshot commit (the folder name under
`~/.cache/huggingface/hub/models--*/snapshots/`) and the sha256 of `tokenizer_config.json`,
`generation_config.json` and `chat_template.jinja` (if present) in `tests/R3/models.txt`. Check whether
`uv sync --locked --python 3.13 --extra serve` works in the setup repo. On `agent-layout`, add an optional
`revision` per model that becomes `--revision <sha>` and set `HF_HUB_OFFLINE=1` for the vLLM processes;
run `uv run pytest`. Do not restart the stack for this.

## Step 7: H1, how harness commands leave the sandbox (prototype, 1 h)

`claim`, `spawn` and `save_tool` run inside the sandbox, and every child inherits it. Anything the sandbox
can write, the agent can rewrite. Prototype `tests/H1/broker.py`: a process outside the sandbox that owns
`events.jsonl` and `claims.jsonl` (in a directory the sandbox cannot see) and listens on a pathname unix
socket inside scratch. A stub `claim` inside the sandbox sends JSON to it; the broker assigns the step id
itself (from the harness's current step, never from the request) and appends with the hash chain.

Check from inside the sandbox: the log directory is not readable or writable; a `claim` with a forged step
id is stored with the real one; after 100 claims the chain verifies. Write the final chain head to the
Slurm job log as well (a second copy the agent cannot reach). Record what fails.

## Step 8: finish

1. Add rows for S5a, S5b, S5c, S6, S1b, L6, R2, R3 and H1 to `tests/RESULTS.md`.
2. Under "Round 3" in `docs/infra-tests-next.md`, add "Round 3 results": one line per test and the decision
   for `docs/decisions-after-tests.md` §4 (Landlock yes/no, which ABI, which gaps remain).
3. Commit on `infra-round-3` (and `agent-layout`), push both if you can.
4. `scancel` your jobs, stop the broker, delete large scratch files (R2).
5. Report: pass/fail per test with the number that matters, every "allowed" escape, and open **USER** steps.
