"""Cross-process model-call slots shared with the paper writer."""
from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from evqa.paths import CACHE

# at most 3 model calls at once (Aditya, 20 Nov; Qwen GPU). EVQA_MAX_CALLS raises it for Claude-plan runs
# (Aditya, 21 Nov: "use 10"); keep 3 for Qwen.
MAX_SLOTS = int(os.environ.get("EVQA_MAX_CALLS", "3"))
SLOT_DIR = CACHE / "claude-slots"  # paperwriter uses these exact files for both backends


@contextmanager
def model_slot(directory: Path | None = None, *, poll: float = 0.1) -> Iterator[int]:
    """Hold one writer-compatible slot until the model call completes or raises."""
    directory = SLOT_DIR if directory is None else directory
    directory.mkdir(parents=True, exist_ok=True)
    while True:
        for index in range(MAX_SLOTS):
            with (directory / f"slot-{index}.lock").open("a+") as slot:
                try:
                    fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                try:
                    yield index
                finally:
                    fcntl.flock(slot, fcntl.LOCK_UN)
                return
        time.sleep(poll)
