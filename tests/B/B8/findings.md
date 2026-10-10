# B8: format-nudge pilot

The B1 one-block failure was tested with a stricter output instruction on the current ORCH model (Qwen3.8-27B-FP8), thinking disabled. The prompt requires only one executable bash block, gives the exact fence shape, and forbids prose or any second fence.

- 20 prompts from the existing B task set
- Exactly one fenced bash block: 20/20 (100%)
- Prose-only and multiple-block responses: 0/20
- Mean request latency: 0.73 s
- All requests finished normally

This is a pilot, not a replacement for B1's 50-prompt evaluation: it uses the newer non-thinking model and the first 20 prompts. It supports using the strict format instruction with Qwen3.8, but a full 50-prompt rerun is needed before changing the B1 result or treating the threshold as established.

Raw responses and the machine-readable summary are in `results.jsonl` and `summary.json`.
