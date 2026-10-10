# L8: proxy context-window failures

Date: 2026-10-10. All three requests through LiteLLM returned HTTP 400 `BadRequestError` with a `ContextWindowExceededError` message. The proxy included the model context limit, minimum counted prompt length, requested output count, and total at least one token over the limit:

- ORCH: 70,000-token prompt + 1 output token; limit 65,536, proxy reports at least 65,536 input tokens and 65,537 total.
- SUB: 34,000-token prompt + 1 output token; limit 32,768, proxy reports at least 32,768 input tokens and 32,769 total.
- ORCH: 64,000-token prompt + 2,000 output tokens; proxy reports 63,537 input + 2,000 output = 65,537 against 65,536.

The harness can map this 400 error to “context full” and stop retrying. Raw bodies are in `errors.json`.
