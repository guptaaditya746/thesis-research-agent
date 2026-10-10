#!/usr/bin/env python3
"""Run one sandbox command in a fresh process group and clean up descendants."""

from __future__ import annotations

import argparse
import os
import socket
import signal
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--claim-log")
    parser.add_argument("--step-id", type=int, default=42)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide command after --")
    broker = None
    inherited_fds: tuple[int, ...] = ()
    env = os.environ.copy()
    if args.claim_log:
        broker_sock, command_sock = socket.socketpair()
        broker_path = os.path.join(os.path.dirname(__file__), "..", "H1", "broker.py")
        broker = subprocess.Popen(
            [sys.executable, broker_path, "--fd", str(broker_sock.fileno()),
             "--log", args.claim_log, "--step-id", str(args.step_id)],
            pass_fds=(broker_sock.fileno(),), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True,
        )
        broker_sock.close()
        env["CLAIM_FD"] = str(command_sock.fileno())
        inherited_fds = (command_sock.fileno(),)
    process = subprocess.Popen(command, start_new_session=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, pass_fds=inherited_fds,
                               env=env)
    if args.claim_log:
        command_sock.close()
    try:
        output, _ = process.communicate(timeout=args.timeout)
        status = process.returncode
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            output, _ = process.communicate()
        status = 124
    finally:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            for _ in range(20):
                try:
                    os.killpg(process.pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
            else:
                os.killpg(process.pid, signal.SIGKILL)
                cleanup = "SIGTERM-then-SIGKILL"
            if "cleanup" not in locals():
                cleanup = "SIGTERM-process-group"
        except ProcessLookupError:
            cleanup = "no-processes-remained"
    sys.stdout.write(output)
    if broker:
        broker_output, _ = broker.communicate(timeout=10)
        sys.stdout.write(broker_output)
        if broker.returncode:
            print(f"claim_broker_exit={broker.returncode}")
            return broker.returncode
    print(f"process_group_cleanup={cleanup}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
