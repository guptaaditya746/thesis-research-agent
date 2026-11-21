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
    active, peak, starts = mp.Value("i", 0), mp.Value("i", 0), mp.Value("i", 0)
    processes = [mp.Process(target=_process, args=(tmp_path, active, peak, starts)) for _ in range(2)]
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


def test_qwen_and_claude_adapters_take_shared_slot(monkeypatch):
    import json
    from contextlib import contextmanager
    from types import SimpleNamespace
    from evqa import lm, llm

    entered = []
    @contextmanager
    def fake_slot():
        entered.append("acquired")
        yield

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

    monkeypatch.setattr(lm, "model_slot", fake_slot)
    monkeypatch.setattr(llm, "model_slot", fake_slot)
    monkeypatch.setattr(lm.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    assert lm.qwen_ask("fake", think=False)("question") == "ok"
    monkeypatch.setattr(lm.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        stdout=json.dumps({"result": "ok", "structured_output": {}, "modelUsage": {}})))
    assert lm.claude_ask("fake")("question") == "ok"
    assert llm.ClaudeCode("fake")("system", "user", {})["output"] == {}
    assert entered == ["acquired", "acquired", "acquired"]
