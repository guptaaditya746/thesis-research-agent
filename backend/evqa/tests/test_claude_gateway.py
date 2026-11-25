"""evqa.claude_gateway: OpenAI chat requests -> claude -p prompts and back (the CLI is faked)."""
import json

import pytest

from evqa import claude_gateway as gw


def fake(*replies):
    seen, it = [], iter(replies)

    def call(model, system, transcript):
        seen.append((model, system, transcript))
        return {"text": next(it), "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
    return call, seen


def test_plain_chat_keeps_system_and_user_apart() -> None:
    call, seen = fake("hi")
    out = gw.complete({"model": "claude-haiku-5-5", "messages": [{"role": "system", "content": "Be brief."},
                                                                 {"role": "user", "content": "Hello"}]}, call)
    assert out["choices"][0]["message"] == {"role": "assistant", "content": "hi"}
    assert seen == [("claude-haiku-5-5", "Be brief.", "Hello")]


def test_qwen_alias_is_refused() -> None:
    with pytest.raises(ValueError, match="Claude models only"):
        gw.complete({"model": "orch-model", "messages": []}, fake()[0])


def test_tool_call_reply_becomes_openai_tool_calls() -> None:
    call, seen = fake('```json\n{"tool_calls": [{"name": "search", "arguments": {"q": "x"}}]}\n```')
    tools = [{"type": "function", "function": {"name": "search", "parameters": {"type": "object"}}}]
    out = gw.complete({"model": "claude-haiku-5-5", "tools": tools, "tool_choice": "required",
                       "messages": [{"role": "user", "content": "find x"}]}, call)
    c = out["choices"][0]
    assert c["finish_reason"] == "tool_calls"
    assert c["message"]["tool_calls"][0]["function"] == {"name": "search", "arguments": json.dumps({"q": "x"})}
    assert '"search"' in seen[0][1] and "must call" in seen[0][1]


def test_unreadable_tool_reply_is_asked_again_then_kept_as_text() -> None:
    call, seen = fake("no json", "still none")
    tools = [{"type": "function", "function": {"name": "search"}}]
    out = gw.complete({"model": "claude-haiku-5-5", "tools": tools,
                       "messages": [{"role": "user", "content": "q"}]}, call)
    assert len(seen) == 2 and out["choices"][0]["message"]["content"] == "still none"
    assert "must call" in seen[0][1]           # "auto" counts as "required" (the PaperQA2 agent loop)


def test_transcript_shows_tool_results() -> None:
    sys_, tr = gw.prompt_parts({"messages": [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "search", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1", "name": "search", "content": "found"}]})
    assert sys_ == "" and "[tool result: search]\nfound" in tr and '"tool_calls"' in tr


def test_arguments_written_as_a_json_string_are_unwrapped() -> None:
    got = gw.parse_tool_reply('{"tool_calls": [{"name": "s", "arguments": "{\\"q\\": \\"x\\"}"}]}')
    assert json.loads(got[1][0]["function"]["arguments"]) == {"q": "x"}
