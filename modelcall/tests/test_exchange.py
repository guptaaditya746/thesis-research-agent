"""The exchange model: a call is a request file, its reply is read from a file (no network)."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from pydantic import BaseModel

from modelcall import JsonlCache, Prompt, ask_sync, default_key, model_identity
from modelcall.exchange import exchange_model, main, model_for
from modelcall.gateway import CallSettings


class Out(BaseModel):
    answer: str
    n: int


PROMPT = Prompt.inline("Answer with a word and a number.", Out)


def answer_when_pending(root: Path, replies: list[dict], seen: list[dict]) -> threading.Thread:
    """Plays the model: for each pending request, writes the next of `replies` (once per request write)."""
    def run() -> None:
        queue = list(replies)
        last = None
        deadline = time.time() + 20
        while queue and time.time() < deadline:
            for f in sorted((root / "pending").glob("*.json")) if (root / "pending").exists() else []:
                try:
                    req = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):   # gone or being replaced (Windows): look again on the next pass
                    continue
                if (f.name, len(req.get("rejected", []))) == last:
                    continue
                last = (f.name, len(req.get("rejected", [])))
                seen.append(req)
                (root / "replies").mkdir(parents=True, exist_ok=True)
                tmp = root / "replies" / f"{f.stem}.tmp"      # written whole, then renamed: never read half done
                tmp.write_text(json.dumps(queue.pop(0)), encoding="utf-8")
                os.replace(tmp, root / "replies" / f.name)
            time.sleep(0.05)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def test_request_written_and_reply_returned(tmp_path: Path) -> None:
    model = exchange_model(tmp_path, "exchange:writer", poll_s=0.05, timeout_s=60)
    seen: list[dict] = []
    answer_when_pending(tmp_path, [{"answer": "yes", "n": 3}], seen)
    out = ask_sync(PROMPT, "Is it?", model=model, settings=CallSettings(seed=7))
    assert out.output == Out(answer="yes", n=3)
    req = seen[0]
    assert req["model"] == "exchange:writer" and req["seed"] == 7
    assert req["instructions"] == "Answer with a word and a number." and req["prompt"] == "Is it?"
    assert req["output_schema"]["required"] == ["answer", "n"]
    assert not list((tmp_path / "pending").glob("*.json"))
    assert (tmp_path / "done" / f"{req['id']}.json").exists()


def test_invalid_reply_is_rejected_with_its_reason_then_a_valid_one_accepted(tmp_path: Path) -> None:
    model = exchange_model(tmp_path, "exchange:writer", poll_s=0.05, timeout_s=60)
    seen: list[dict] = []
    answer_when_pending(tmp_path, [{"answer": "yes"}, {"answer": "yes", "n": 1}], seen)
    out = ask_sync(PROMPT, "Is it?", model=model)
    assert out.output.n == 1
    assert "'n' is a required property" in seen[1]["rejected"][0]
    assert (tmp_path / "replies" / f"{seen[0]['id']}.rejected-1.json").exists()


def test_an_existing_reply_is_reused_without_a_pending_request(tmp_path: Path) -> None:
    model = exchange_model(tmp_path, "exchange:writer", poll_s=0.05, timeout_s=60)
    seen: list[dict] = []
    answer_when_pending(tmp_path, [{"answer": "a", "n": 1}], seen)
    ask_sync(PROMPT, "Q", model=model)
    rid = seen[0]["id"]
    (tmp_path / "done" / f"{rid}.json").unlink()
    again = ask_sync(PROMPT, "Q", model=exchange_model(tmp_path, "exchange:writer", poll_s=0.05, timeout_s=60))
    assert again.output.answer == "a" and len(seen) == 1


def test_cache_key_carries_the_exchange_name_and_a_hit_needs_no_reply(tmp_path: Path) -> None:
    model = exchange_model(tmp_path / "x", "exchange:writer", poll_s=0.05, timeout_s=60)
    assert model_identity([model]) == "exchange:writer"
    cache = JsonlCache(tmp_path / "c.jsonl")
    key = default_key(PROMPT, "Q", model, CallSettings())
    answer_when_pending(tmp_path / "x", [{"answer": "a", "n": 1}], [])
    first = ask_sync(PROMPT, "Q", model=model, cache=cache, key=key)
    second = ask_sync(PROMPT, "Q", model=model, cache=cache, key=key)
    assert not first.cached and second.cached and second.output == first.output


def test_model_for_and_status(tmp_path: Path, capsys) -> None:
    m = model_for("exchange:claude-haiku", tmp_path)
    assert m.model_name == "exchange:claude-haiku"
    (tmp_path / "claude-haiku" / "pending").mkdir(parents=True)
    (tmp_path / "claude-haiku" / "pending" / "abc.json").write_text(
        json.dumps({"output_schema": {"type": "object", "required": ["a"]}}), encoding="utf-8")
    (tmp_path / "claude-haiku" / "replies").mkdir()
    (tmp_path / "claude-haiku" / "replies" / "abc.json").write_text("{}", encoding="utf-8")
    assert main(["status", str(tmp_path / "claude-haiku")]) == 0
    assert json.loads(capsys.readouterr().out)["answered_waiting"] == 1
    assert main(["check", str(tmp_path / "claude-haiku")]) == 1
    assert "'a' is a required property" in capsys.readouterr().out


def test_a_reply_still_being_written_is_not_read_half_done(tmp_path: Path) -> None:
    model = exchange_model(tmp_path, "exchange:writer", poll_s=0.05, settle_s=0.5, timeout_s=60)

    def answer() -> None:
        deadline = time.time() + 20
        while time.time() < deadline and not list((tmp_path / "pending").glob("*.json")):
            time.sleep(0.02)
        reply = tmp_path / "replies" / next((tmp_path / "pending").glob("*.json")).name
        reply.parent.mkdir(parents=True, exist_ok=True)
        reply.write_text("", encoding="utf-8")          # the writer has opened the file, nothing written yet
        time.sleep(0.2)
        reply.write_text(json.dumps({"answer": "a", "n": 2}), encoding="utf-8")
    threading.Thread(target=answer, daemon=True).start()
    out = ask_sync(PROMPT, "Q", model=model)
    assert out.output.n == 2
    assert not list((tmp_path / "replies").glob("*.rejected-*"))


def test_a_tool_call_reply_runs_the_tool_and_the_next_request_shows_it(tmp_path: Path) -> None:
    """A call with tools: the request lists them; a reply naming an unknown tool is rejected with its reason; a
    valid tool call runs the tool, and the next request's prompt holds the call and its result."""
    from pydantic_ai import Agent

    from modelcall.loop import run_sync

    model = exchange_model(tmp_path, "exchange:writer", poll_s=0.05, settle_s=0.5, timeout_s=60)
    agent = Agent(model, output_type=Out, instructions="Use the tool, then answer.")

    @agent.tool_plain
    def lookup(word: str) -> str:
        """Look a word up."""
        return f"{word} means seven"

    seen: list[dict] = []
    answer_when_pending(tmp_path, [{"tool_calls": [{"tool": "nope", "args": {}}]},
                                   {"tool_calls": [{"tool": "lookup", "args": {"word": "zap"}}]},
                                   {"answer": "zap", "n": 7}], seen)
    out = run_sync(agent.run("What is zap?"))
    assert out.output == Out(answer="zap", n=7)
    assert [t["name"] for t in seen[0]["tools"]] == ["lookup"] and seen[0]["tools"][0]["description"]
    assert "'nope' is not one of ['lookup']" in seen[1]["rejected"][0]
    last = seen[2]["prompt"]
    assert 'lookup {"word": "zap"}' in last and '[tool result ' in last and "zap means seven" in last
    assert seen[2]["id"] != seen[0]["id"]


def test_a_call_with_a_timeout_fails_instead_of_waiting(tmp_path: Path) -> None:
    from modelcall import ModelCallError
    model = exchange_model(tmp_path, "exchange:writer", poll_s=0.02, timeout_s=0.3)
    started = time.time()
    try:
        ask_sync(PROMPT, "Nobody answers", model=model)
    except ModelCallError as exc:
        assert "TimeoutError" in exc.reason and "no accepted reply" in exc.reason
    else:
        raise AssertionError("the call returned without a reply")
    assert time.time() - started < 10
    assert len(list((tmp_path / "pending").glob("*.json"))) == 1     # the request stays for a later run
