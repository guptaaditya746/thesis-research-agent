"""The writer and EVQA share a three-call cap across independent processes."""
from __future__ import annotations

import fcntl
import multiprocessing as mp
import threading
import time

import pytest

from evqa.slots import model_slot


def _process(directory, active, peak, starts):
    def fake_call():
        with model_slot(directory, poll=0.005):
            with active.get_lock():
                active.value += 1
                peak.value = max(peak.value, active.value)
                starts.value += 1
            time.sleep(0.12)
            with active.get_lock():
                active.value -= 1
    threads = [threading.Thread(target=fake_call) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_cap_across_two_processes(tmp_path):
    # spawn, not fork: forking a multi-threaded pytest(-xdist) worker can deadlock the child
    ctx = mp.get_context("spawn")
    active, peak, starts = ctx.Value("i", 0), ctx.Value("i", 0), ctx.Value("i", 0)
    processes = [ctx.Process(target=_process, args=(tmp_path, active, peak, starts)) for _ in range(2)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert not process.is_alive() and process.exitcode == 0
    assert starts.value == 6 and peak.value == 3 and active.value == 0


def test_writer_lock_is_respected_and_released_on_error(tmp_path):
    with (tmp_path / "slot-0.lock").open("a+") as writer:
        fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError), model_slot(tmp_path, poll=0.005) as index:
            assert index != 0
            raise RuntimeError("fake failed call")
        with model_slot(tmp_path, poll=0.005) as index:
            assert index == 1


def test_qwen_and_claude_adapters_take_shared_slot(monkeypatch, tmp_path):
    """Each adapter holds a real writer-compatible slot while it calls the model. The slot folder is this test's
    tmp_path, never the shared data/cache/claude-slots that writer subprocesses in other tests (or a real run) may
    hold, and the check looks at the lock files themselves rather than counting calls of a global stand-in."""
    import json
    from types import SimpleNamespace
    from evqa import lm, llm, slots

    monkeypatch.setattr(slots, "SLOT_DIR", tmp_path)
    limits, held = [], []

    def spy_slot(directory=None, *, poll=0.1, limit=None):
        limits.append(limit)
        return slots.model_slot(directory, poll=0.005, limit=limit)

    def slot_held() -> bool:
        with (tmp_path / "slot-0.lock").open("a+") as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(probe, fcntl.LOCK_UN)
            return False

    class Response:
        def __enter__(self):
            held.append(slot_held())
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

    def run(*args, **kwargs):
        held.append(slot_held())
        return SimpleNamespace(stdout=json.dumps({"result": "ok", "structured_output": {}, "modelUsage": {}}))

    monkeypatch.setattr(lm, "model_slot", spy_slot)
    monkeypatch.setattr(llm, "model_slot", spy_slot)
    monkeypatch.setattr(lm.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    assert lm.qwen_ask("fake", think=False)("question") == "ok"
    monkeypatch.setattr(lm.subprocess, "run", run)
    assert lm.claude_ask("fake")("question") == "ok"
    assert llm.ClaudeCode("fake")("system", "user", {})["output"] == {}
    assert limits == [lm.MAX_SLOTS_QWEN, None, None]
    assert held == [True, True, True] and not slot_held()
