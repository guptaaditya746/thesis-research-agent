# B1 interpretation after model-card check

The B1 checkpoint, `Qwen/Qwen3-30B-A3B-Thinking-2507`, is explicitly a thinking-only model. Its official model card says it supports only thinking mode and that the default chat template includes `<think>`; `enable_thinking=True` is unnecessary. Thus B1's 50/50 nonempty reasoning fields in the requested “thinking off” condition are expected for this checkpoint and do not show a vLLM parser defect.

The format result remains meaningful for thinking-on use: only 26% of final `content` fields contained exactly one fenced bash block. The block was not lost into the parsed reasoning field. Therefore the unresolved B1 issue was final-answer format compliance. The off-mode half of B1 was not a valid thinking-off comparison.

Official model card: <https://huggingface.co/Qwen/Qwen3-30B-A3B-Thinking-2507> (states the checkpoint supports only thinking mode and describes the default thinking template).

Follow-up results on the actual current hybrid model are in B8 and B9: strict prompt format passed 50/50 with thinking off and 48/50 with thinking on at a 4,096-token cap; regex-constrained output passed 10/10 through both direct vLLM and LiteLLM when thinking was off. Thinking-on constrained results are being tested separately.
