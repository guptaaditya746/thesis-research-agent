# Research on remaining partial and failed tests

Date: 2026-10-10
Scope: primary documentation, upstream project code/issues, and the measurements already recorded in this repository. This report does not alter test results or serving configuration. Sandbox tests are excluded per the user's direction; scanned PDF `p38` is accepted as an exception.

## Summary

| Area | Latest evidence | Status for design | Recommended next check |
|---|---|---|---|
| LiteLLM `GET /v1/models` | The recorded HTTP 500 probe was unauthenticated and logs show `ModuleNotFoundError: prisma`; chat completion works with the valid key. Upstream has a matching DB-less missing-auth exception bug. | Not on the inference path; model discovery only. Root cause is strongly consistent with the probe, not yet confirmed for an authenticated request. | Probe readiness, `/v1/models` with the master key, and a completion with the same key. If only unauthenticated discovery fails, leave it alone; if authenticated listing fails, check the pinned LiteLLM proxy extra/version and generated client. |
| Subagent replica balance | Shared model-group routing varied from 8/0 to 5/3; pinned aliases balanced 4/4. | Mitigated for explicit concurrent fan-out by `sub-model-1` / `sub-model-2`; shared-alias fairness is not guaranteed. | Run a larger interleaved fan-out through the pinned aliases, then verify per-replica request counters. |
| Format and reasoning | Current Qwen3.8 strict prompt: thinking-off 50/50; thinking-on default xhigh at 4096: 48/50, and 8192: 47/50, with misses from `length`; thinking-on low effort at 4096: 50/50, no cuts, mean 2.51s. Regex constraint: off 10/10 direct and proxy; on 9/10 direct, 8/10 proxy, again limited by length. | Low effort removes the observed format/cutoff failure on this 50-task set. Command usefulness still needs rating. Higher token caps alone did not help. | Rate the low-effort commands using the B6 rubric; compare low against medium only if the quality rating suggests it is needed. |
| B6 command usefulness | The historical 39/50 (78%) rating was on the replaced Thinking-2507 checkpoint. State-aware Qwen3.8 produced 50/50 formatted commands, but no manual usefulness rating is recorded. | Quality question remains; format score is not a usefulness score. | Blind-rate the 50 B10 commands against the existing B6 rubric, then compare with B8's 40/50 on the same task set. |
| D1 PDF flow/metadata | Docling recovered headings, references, and table rows for the 10-paper sample. Title and author-order match were each 9/10 for both Docling and GROBID; the same title and author-order records failed. Column order was never visually reviewed. | Metadata discrepancy and column flow remain unverified. No evidence currently shows that GROBID+Docling fixes either. | Inspect the two discrepant records against publisher/DBLP source; run Docling settings variants on the selected two-column papers and compare paragraph order against a short manually ordered gold sample. |
| L6 request headroom | A 54,605-token prompt plus 1,776 output completed in 71.87 s in one L6 run; another near-maximum run used 54,610 + 4,096 and took 112.52 s against the then-tested 120 s proxy timeout. | Close to the tested timeout at max output; no timeout happened in the recorded 4k run. Current L7 config sets proxy timeout to 600 s, but application/client timeout still needs to be checked end-to-end. | Through LiteLLM, run one 54.6k prompt with 4096 output and one representative concurrent load; record client timeout, proxy timeout and total latency. |
| Prefix caching | The initial small C2 replay was partial; C2b's realistic 30k paper-text replay through LiteLLM achieved 93.7% hit/query unmasked and 86.7% masked. | C2b supersedes the earlier low-context uncertainty for normal repeated prompts. | No extra test needed unless the real harness changes the stable prefix or mask schedule. |

## 1. LiteLLM model discovery error

### What the repo establishes

`tests/S3/anonymous-probes.txt` records `GET :4000/v1/models` without an authorization header returning HTTP 500, with the gateway log reporting `ModuleNotFoundError: No module named 'prisma'`. The separate model-behavior tests used a valid LiteLLM key and show that chat completions, thinking parameters, and response fields pass through. The invalid placeholder key previously used during the regex experiment caused `No connected db`; the corrected-key test then passed, so that incident is not evidence of a forwarding fault.

Upstream LiteLLM issue [#38978](https://github.com/BerriAI/litellm/issues/38978) documents a DB-less proxy installed without Prisma where a missing Authorization header triggers an unguarded Prisma import while constructing the auth error, turning the intended 401 into a generic 500. This closely matches the recorded unauthenticated probe. The issue was tested against LiteLLM 1.98.0; this repo's `llm-setup/uv.lock` resolves 1.102.1, so it is evidence for a plausible mechanism rather than proof the bug persists in this exact locked version. It also does not establish failure for an authenticated request. The separate issue [#30425](https://github.com/BerriAI/litellm/issues/30425) shows the Prisma client/generator requirement when database-backed proxy features are enabled.

### Practical impact and workaround

The application already knows its configured aliases (`orch-model`, `sub-model`, `sub-model-1`, `sub-model-2`) and does not need model discovery to submit completions. LiteLLM's documented readiness endpoint is `/health/readiness`; the proxy setup documentation shows `/v1/models` called with `Authorization: Bearer $LITELLM_MASTER_KEY` ([LiteLLM proxy deployment verification](https://docs.litellm.ai/docs/proxy/manifests_to_microservices)). Therefore, avoid using an unauthenticated `/v1/models` request as the health check. Use readiness for health and a keyed completion for inference health.

If keyed `/v1/models` still fails, check the installed/pinned proxy package and generated Prisma client. The stack currently asks for `litellm[proxy]>=1.92` rather than pinning an exact version; lock resolution should be recorded in the run directory. Do not add a database just to make the model list endpoint work unless database-backed LiteLLM features are actually needed.

### Slurm experiment

From the existing stack, using the same key for each request, record status and response for: `GET /health/readiness`, unauthenticated `GET /v1/models`, keyed `GET /v1/models`, and keyed `POST /v1/chat/completions`. Do not print the key. A result of readiness 200 + keyed completion 200 + unkeyed model list 500 confirms this is a discovery/auth-error path and leaves the agent unblocked. If keyed model listing also fails, capture the sanitized traceback and exact LiteLLM version before considering dependency or configuration changes.

## 2. Subagent routing imbalance

LiteLLM routes a model group across deployments using a selectable strategy; its current docs describe `simple-shuffle`, `least-busy`, and other strategies ([router/load-balancing docs](https://docs.litellm.ai/docs/routing)). Those strategies select a deployment per request; a chosen strategy is not a promise of an exact split in a small concurrent sample.

The repo measured highly variable splits on the shared alias: `least-busy` gave 5/3 in one concurrent run and 8/0 in repeats; `simple-shuffle` and usage-based routing also showed skew. The same test measured 4/4 using the explicit pinned aliases. The state decision already directs fan-out to `sub-model-1` and `sub-model-2`, one per GPU replica. This turns a probabilistic shared-group selection into explicit assignment and is the practical workaround. It avoids changing serving configuration.

### Slurm experiment

Run 20–30 concurrent subagent requests, alternating the pinned aliases, with the usual 16k prompts and 300-token outputs. Capture request start/end timestamps and each replica's `/metrics` request/active-sequence counters. Pass if all requests complete, both replicas show overlapping active intervals, and neither preempts at the configured three active sequences. Separately, treat shared-alias balance as a diagnostic only; do not gate fan-out on a perfect shared-alias split.

## 3. Output format and reasoning budget

Qwen's official Qwen3.8 model card says thinking is on by default, can be disabled per request, and supports `reasoning_effort` values `low`, `medium`, and `xhigh`; it demonstrates these through an OpenAI-compatible request ([Qwen3.8-27B-FP8 model card](https://huggingface.co/Qwen/Qwen3.8-27B-FP8)). vLLM's Qwen3 parser separates reasoning from content; it does not impose a shell-block format ([vLLM 0.21 reasoning outputs](https://docs.vllm.ai/en/v0.21.0/features/reasoning_outputs/)). vLLM supports regex-constrained structured outputs ([vLLM 0.21 structured outputs](https://docs.vllm.ai/en/v0.21.0/features/structured_outputs/)), and the repo's valid-key B9 test verifies the constraint reached both direct vLLM and LiteLLM when thinking is off.

Latest repo measurements make the decision clearer than the old B1/B2 numbers:

- Qwen3.8 with thinking off and the strict format instruction: 50/50 one-block outputs over the same B task set (B8).
- Thinking on at the default effort and 4096 completion tokens: 48/50 one-block; the two misses ended with `finish_reason=length` (B8).
- Raising the limit to 8192 produced 47/50, with three length cuts and higher mean latency; a larger cap did not solve the issue (B8).
- Thinking on at `reasoning_effort="low"` with 4096 completion tokens produced 50/50 one-block outputs, 50/50 nonempty reasoning fields, no length cuts, and 2.51 s mean latency over the same prompts (B8 low-effort run).
- Regex constrained decoding with thinking off: 10/10 direct and through LiteLLM. Thinking on: 9/10 direct and 8/10 via LiteLLM; the failed outputs were length-limited (B9).

So the remaining issue is not a proven LiteLLM loss of regex parameters. It is that default xhigh reasoning may consume the completion budget before a usable answer appears. Low effort resolved format and cutoff failures in this sample while retaining nonempty reasoning. A strict prompt plus a lenient parser works well with thinking off; constrained decoding is an optional stronger format layer. Keep parser validation and rate command usefulness before fixing the setting as final.

### Slurm experiment

Using the exact 50 prompts and prompt template from B8, blind-rate the new low-effort commands against the existing B6 sensible-command criterion; compare with B8's thinking-off 40/50 rating. Run the medium-effort condition only if low-effort quality is inadequate. Record usefulness, latency, and completion tokens. Do not interpret the previous 39/50 B6 score on Qwen3-30B-A3B-Thinking-2507 as the Qwen3.8 score; that checkpoint is no longer the orchestrator.

## 4. Command usefulness (B6)

The current B6 rubric judges whether the next command is executable and directly useful for the research task; it does not judge the final answer or the presence of a correctly formatted code block. The original 39/50 rating came from the old Thinking-2507 model. The later Qwen3.8 B8 manual review scored 40/50 under the same broad rubric, but B10's 50 state-aware commands have only a format summary recorded (50/50), not a usefulness score. That means the apparent 78%→80% movement is too small and crosses model/prompt conditions; it is not evidence that state-aware ranking helped.

The useful next action is human evaluation, not an unverified “validator” feature. Rate B10 and B8 outputs blind and in shuffled order, using exactly the saved B6 criterion. Add a second rater if available; report agreement and per-task disagreements. If B10 does not exceed the B8 baseline, leave the existing simpler prompt and move on; this is a research-quality measurement, not a launch blocker.

## 5. D1: Docling reading order and GROBID metadata

Repo D1 is partial for a specific reason: title match and author order each scored 9/10 for both Docling and GROBID; the failures are the same paper records. Docling had 10/10 section/reference detection and Markdown table rows in this sample. The column review is still “manual review required.” The GROBID data in this comparison is cached TEI rendered to Markdown, not a separate full PDF conversion timing or evidence that metadata fusion fixes the discrepancies.

The D1 script sets `do_ocr=False` and `do_table_structure=True`, leaving Docling 2.110.0's table defaults in effect. The upstream [v2.110.0 source](https://github.com/docling-project/docling/blob/v2.110.0/docling/datamodel/pipeline_options.py) says `ACCURATE` is the default and `do_cell_matching=True` is the default. Therefore, explicitly setting the two options proposed in the supplied findings would repeat the tested configuration; it is not a new alternative. Current Docling documentation exposes `use_reading_order_separators`, but the pinned [v2.110.0 `pipeline_options.py`](https://raw.githubusercontent.com/docling-project/docling/v2.110.0/docling/datamodel/pipeline_options.py) does not contain that setting. Do not pass it to this frozen converter version. A test of that switch would require a separate newer Docling environment and would change more than one versioned component unless carefully pinned.

First-party Docling issues document multi-column reading-order failures ([#1203](https://github.com/docling-project/docling/issues/1203), [#2067](https://github.com/docling-project/docling/issues/2067)). The visible-separator setting can only be treated as a version-specific comparison arm, not a guaranteed general fix; neither it nor the table options guarantee two-column paragraph order. Also, accurate tables can be slower, and `do_cell_matching=True` can alter table-cell text assignment; compare variants against the existing 2.110.0 output rather than replacing it.

GROBID's endpoint documentation distinguishes full-text processing from header-only extraction ([GROBID services](https://grobid.readthedocs.io/en/latest/Grobid-service/)); header extraction is a useful metadata source but cannot be presumed correct when it agrees with Docling on the wrong DBLP match. Use authoritative publisher/DOI metadata as the adjudication source for the two discrepancies.

### Slurm experiment

1. For the two mismatched paper IDs in `tests/D1/criteria.md`, inspect the first page and compare the PDF's visible author/title order to the DBLP-corpus manifest and GROBID TEI. Record which reference is wrong; preserve both raw extractor values.
2. For the papers with the strongest two-column risk, first inspect page/block provenance and manually score the pinned 2.110.0 baseline. To test `use_reading_order_separators=False`, create a separate environment with an explicit newer Docling version that supports the option and record all component versions; do not treat this as a same-version setting flip. Compare its result against baseline without touching the frozen corpus.
3. For one table-heavy PDF, compare the existing `do_cell_matching=True` baseline with `False`; score table row/cell preservation separately from reading-order quality. This is the actual setting alternative available in the current version. Export Docling JSON/HTML for the table fidelity check because Markdown flattens merged-cell structure ([Docling serialization docs](https://docling-project.github.io/docling/concepts/serialization/)).
4. Manually transcribe a small sequence of paragraph IDs from the two-column PDF (e.g. 15–30 consecutive blocks across one page transition), then compare each extractor variant's block sequence. Record swaps/interleavings, not a subjective “looks okay” score.

If the alternative changes do not improve the gold-sequence order, freeze the existing deterministic Docling conversion and mark citation/table concepts answerable only where the cited passage and table cells can be checked in the source PDF. The user has already accepted p38 as excluded, so this report does not propose another OCR retry.

## 6. Long-context timeout and queue behavior (L6)

The latest state records a worst-case ORCH call with 54.6k prompt tokens plus 4096 output taking 112.52 s against an earlier 120 s proxy timeout: only 7.5 s headroom. A smaller 1776-token output completed in 71.87 s. L7 later changed the generated LiteLLM request timeout to 600 s, but a generous proxy timeout only helps if the OpenAI client, harness step timeout, and Slurm job also allow the call to finish. L6 also observed requests routed to port 8002 while port 8004 was idle; queue accounting was inconclusive.

The practical safeguards are: keep the chosen model effort/output budget bounded; include enough request timeout at both client and proxy; use pinned replica aliases for explicit concurrent fan-out; and avoid assuming that an idle replica will receive work automatically. Use the recorded 60k prefill throughput and full C2b cached-prefix measurements as the current base rather than extrapolating the tiny initial C2 replay.

### Slurm experiment

Run sequentially: (a) 54.6k prompt / 4096 output; (b) same prompt / 4096 output at low reasoning effort if thinking is enabled; then (c) two concurrent 32k prompts explicitly pinned to separate subagent replicas. Log client total timeout, LiteLLM request timeout, first-token and total latency, backend request IDs, per-replica running/waiting metrics, and request outcomes. No queue or routing code should be changed based only on the previous ambiguous probe.

## 7. Superseded partial rows

- **A7:** the old non-thinking-model comparison was partial; A7b tested Qwen3.8 thinking on/off direct vs proxy and passed field equality and switch handling.
- **C2:** the initial short replay did not establish realistic prefill timing; C2b measured a 30k paper-text prompt and showed high cache-hit rates. Use C2b for the current context-caching decision.
- **L3:** shared-alias strategy tests remain imbalanced, but L7's pinned aliases provide the explicit 4/4 concurrent path. Treat L3 as a limitation of shared routing, not an unresolved fan-out blocker.
- **B1/B2:** the original failure/cutoff measurements used the thinking-only Qwen3-30B checkpoint, not current Qwen3.8. Keep those as historical model comparisons; current behavior is in B8/B9.

## Primary sources

- LiteLLM upstream [#38978, missing Prisma import in DB-less unauthenticated error handling](https://github.com/BerriAI/litellm/issues/38978); [proxy readiness/model-list verification](https://docs.litellm.ai/docs/proxy/manifests_to_microservices).
- LiteLLM [routing strategies and deployment selection](https://docs.litellm.ai/docs/routing).
- Qwen [Qwen3.8-27B-FP8 model card and API parameters](https://huggingface.co/Qwen/Qwen3.8-27B-FP8).
- vLLM 0.21 [reasoning output parsing](https://docs.vllm.ai/en/v0.21.0/features/reasoning_outputs/) and [structured output constraints](https://docs.vllm.ai/en/v0.21.0/features/structured_outputs/).
- Docling [v2.110.0 pipeline options](https://github.com/docling-project/docling/blob/v2.110.0/docling/datamodel/pipeline_options.py), current [advanced conversion options](https://github.com/docling-project/docling/blob/main/docs/usage/advanced_options.md), [serialization and table export fidelity](https://docling-project.github.io/docling/concepts/serialization/), and first-party [multi-column issue #1203](https://github.com/docling-project/docling/issues/1203) / [#2067](https://github.com/docling-project/docling/issues/2067).
- GROBID [service endpoints](https://grobid.readthedocs.io/en/latest/Grobid-service/).
