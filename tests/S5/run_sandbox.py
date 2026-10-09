#!/usr/bin/env python3
"""Run one sandbox command in a fresh process group and clean up descendants."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide command after --")
    process = subprocess.Popen(command, start_new_session=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
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
    print(f"process_group_cleanup={cleanup}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
