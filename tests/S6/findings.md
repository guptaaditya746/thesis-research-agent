# S6 escape checks (Landlock ABI 8)

Commands ran through `tests/S5/run_sandbox.py` and the ctypes Landlock wrapper.

- `kill -0` on orch, two sub models, LiteLLM, status API, tunnel and harness shell: all denied. No signals were sent.
- `/proc/<litellm-pid>/environ`: `test -r` reported readable, but opening it raised `PermissionError`; no bytes or environment values were logged.
- SSH key and repository `.env`: `test -r` reported readable, but opening raised `PermissionError`; no bytes or secret values were logged. `.git-credentials` did not exist.
- `SSH_AUTH_SOCK`: absent.
- UDP `sendto` to `1.1.1.1:53`: one byte sent. Landlock does not constrain UDP; this is an escape.
- Abstract Unix socket: denied. Pathname Unix socket: connection allowed. Landlock's socket scope only covers abstract sockets, not pathname sockets; restrict the visible writable filesystem and avoid exposing sensitive pathname sockets.
- `nohup sleep 1000 &`: child was gone after process-group cleanup.

Separate S5c check: `chmod -R u+w $AGENT_ROOT` succeeded under Landlock and permissions were restored immediately. Landlock does not mediate chmod. The post-test SHA-256 manifest verified successfully.

Logs: `findings.txt`, `background-command.txt`, `private`-safe probe outputs in `tests/S5/`.
