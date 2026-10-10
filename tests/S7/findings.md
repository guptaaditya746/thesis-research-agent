# S7 result

Status: PASS on Slurm job 7048, node gammaweb08 (x86_64, Landlock ABI 8).

- The Landlock wrapper installs a seccomp BPF filter immediately after `PR_SET_NO_NEW_PRIVS`. `socket()` for AF_INET, AF_INET6, AF_UNIX, and AF_NETLINK and `socketpair()` returned `EPERM`.
- TCP attempts to `1.1.1.1:443` and `127.0.0.1` ports 8001, 8002, 8004, 4000, and 8010 all returned `EPERM` at socket creation. UDP socket creation and pathname Unix socket creation were also denied.
- `run_sandbox.py` created a socketpair before launching the command and passed the command end through `CLAIM_FD`. The command submitted 100 claims that forged step 999999; the broker stored all with step 42 and the hash chain verified. Head: `a1ed25d8e674923691b49c2f42f7e1d161784530e6b44341beddcc115469b44a`.
- Inside the wrapper, Python printed `2`; grep, rg, jq, NumPy and pandas worked; scratch writes worked; offline `pip install` from the root wheel store installed networkx 3.7.
- The venv interpreter is a symlink to the shared uv Python installation. Its resolved runtime directory must be added to Landlock's read-only paths when the harness uses the venv interpreter.
- The expected chmod behavior was reproduced: `chmod u+w` succeeded, appending to the toolchain file failed, its mode was restored outside the wrapper, and the manifest verifier passed.

Logs: `seccomp-probe-final.log`, `inherited-claims.log`, `claims.jsonl`, `allowed-final.log`, `chmod-landlock.log`, and `restored-manifest.log`.
