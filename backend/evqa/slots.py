"""Cross-process model-call slots: at most N model calls at once across all evqa processes."""
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
# EVQA_MAX_CALLS_QWEN raises the cap for Qwen calls only (vLLM serves 3 replicas x 8 sequences = 24); default: the
# same as EVQA_MAX_CALLS. Qwen calls use slot files 0..MAX_SLOTS_QWEN-1 of the same folder, so a writer call holding
# slot 0-2 still counts against them.
MAX_SLOTS_QWEN = int(os.environ.get("EVQA_MAX_CALLS_QWEN") or MAX_SLOTS)
# EVQA_SLOT_DIR: a separate slot folder, e.g. for runs on a second Claude account (own CLAUDE_CONFIG_DIR, 24 Nov 2026)
SLOT_DIR = Path(os.environ["EVQA_SLOT_DIR"]) if os.environ.get("EVQA_SLOT_DIR") else CACHE / "claude-slots"


@contextmanager
def model_slot(directory: Path | None = None, *, poll: float = 0.1, limit: int | None = None) -> Iterator[int]:
    """Hold one writer-compatible slot until the model call completes or raises. `limit`: how many slots this
    kind of call may use (default MAX_SLOTS; Qwen calls pass MAX_SLOTS_QWEN)."""
    directory = SLOT_DIR if directory is None else directory
    limit = MAX_SLOTS if limit is None else limit
    directory.mkdir(parents=True, exist_ok=True)
    while True:
        for index in range(limit):
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
