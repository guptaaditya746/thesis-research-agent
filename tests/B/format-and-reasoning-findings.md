# Command formatting and Qwen reasoning findings

## What B1 measured

B1 used Qwen3-30B-A3B-Thinking-2507-FP8 and asked for plain-text reasoning followed by exactly one fenced bash block. vLLM returned reasoning separately, but only 26% of final `content` fields had exactly one fenced block, both with thinking requested and with `enable_thinking=False`. No code block found in parsed reasoning was missing from `content`. This points to final-answer formatting and to the older model/request's thinking switch behavior; it does not show that LiteLLM moved or dropped the command.

The original A7 used a non-thinking Heavy model. Direct and proxy fields matched, but it could not test the thinking switch. A fresh A7 rerun against Qwen3.8-27B-FP8 found exact direct/proxy equality for reasoning, content, finish reason, and usage in both modes; reasoning was absent with thinking off and present with thinking on. The proxy honored the switch.

## Alternative output controls tested

- A stricter final-only prompt on Qwen3.8, thinking off, produced exactly one bash block in 50/50 existing B tasks. Mean latency was about 0.63 s.
- A pilot using the same strict prompt with thinking on is running; its results are recorded separately when complete.
- vLLM 0.21 documents online structured outputs using `extra_body={"structured_outputs": {"regex": ...}}`. A direct-vLLM pilot using a regex for one complete bash fence produced one block in 10/10 tasks. The same request through LiteLLM returned HTTP 400 `No connected db`, so proxy passthrough of this field is unverified and fails in the current run.

These runs use the current Qwen3.8 model, unlike B1's Qwen3 Thinking-2507 checkpoint. They support replacing the old checkpoint and using the strict prompt. Regex-constrained decoding is a stronger direct-vLLM fallback if the deployment bypasses or repairs the proxy.

## B6 meaning and follow-up rating

B6 is a by-eye rating of whether the model's first proposed shell command was an executable, concept-directed research action. It does not rate formatting or whether the command ultimately finds the answer. The original B1 responses scored 39/50 (78%) with thinking on and 38/50 (76%) with thinking off. The B8 response set will be rated using the same criterion before using it to recommend a prompt/model change.

## Primary references

- vLLM 0.21 structured outputs: <https://docs.vllm.ai/en/v0.21.0/features/structured_outputs/>. The OpenAI-compatible server accepts `structured_outputs.regex` as an extra parameter.
- vLLM 0.21 reasoning outputs: <https://docs.vllm.ai/en/v0.21.0/features/reasoning_outputs/>. The `--reasoning-parser` option extracts the reasoning field; the public field was renamed from `reasoning_content` to `reasoning`.
- vLLM Qwen3 parser: <https://docs.vllm.ai/en/v0.21.0/api/vllm/reasoning/qwen3_reasoning_parser/>. It splits `<think>...</think>` into reasoning and content and handles the strict disabled-thinking template.
- Qwen quickstart: <https://qwen.readthedocs.io/en/stable/getting_started/quickstart.html>. Qwen describes `enable_thinking=False` as the hard switch and gives separate recommended sampling parameters for thinking and non-thinking modes.
