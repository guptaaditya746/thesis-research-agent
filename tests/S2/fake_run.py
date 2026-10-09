from __future__ import annotations

import hashlib
import json
import signal
import sys
import time
from pathlib import Path

run_dir = Path("tests/S2/run")
run_dir.mkdir(parents=True, exist_ok=True)
events_path = run_dir / "events.jsonl"
previous = "0" * 64
if events_path.exists():
    previous = json.loads(events_path.read_text(encoding="utf-8").splitlines()[-1])["hash"]
step = 0


def append_event(event: str) -> None:
    global previous, step
    row = {
        "step": step,
        "event": event,
        "label": "heartbeat" if event == "heartbeat" else event,
        "command": "fake heartbeat" if event == "heartbeat" else None,
        "exit_code": 0,
        "stdout_bytes": 0,
        "stderr_bytes": 0,
        "stdout_path": None,
        "stdout_head": "",
        "prev_hash": previous,
    }
    digest = hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode()).hexdigest()
    row["hash"] = digest
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        import os
        os.fsync(handle.fileno())
    previous = digest


def terminate(_signum: int, _frame: object) -> None:
    append_event("run_aborted")
    sys.exit(0)


signal.signal(signal.SIGTERM, terminate)
signal.signal(signal.SIGINT, terminate)
while True:
    step += 1
    append_event("heartbeat")
    time.sleep(1)
