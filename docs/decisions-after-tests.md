# Decisions after the first test round (9 Oct 2026)

Read against `tests/RESULTS.md`. Each decision names the test it rests on. Open items are at the end.

## 1. Models and GPU layout

**Orchestrator: `Qwen/Qwen3.8-27B-FP8`, one A100, thinking off, `max_model_len 65536`.**
It is the only tested model that both holds 65k on one GPU (A2: 79,371 KV tokens, 1.21× at 65k) and
follows the one-bash-block rule (B3: 95% with a 6.6 KB prior output, 100% on multi-step prompts). It is the
slowest tested (A5: 41.6 tok/s, so ~36 min for 90k output tokens), which is acceptable for an orchestrator
that mostly delegates. Caveats: 8.5 min cold start (compile it once per Slurm job, keep the job alive);
prefix caching on its hybrid (Mamba) layers is marked experimental in vLLM 0.21 (C2 ran, but on a 1.6k-token
history only); FlashInfer sampler must be disabled (`VLLM_USE_FLASHINFER_SAMPLER=0`) because `nvcc` is absent.

**Subagents: `Qwen/Qwen3-30B-A3B-Instruct-2507-FP8` ("Heavy"), one A100 per replica, two replicas on GPUs 1 and 2,
`max_model_len 32768`.** 130 tok/s single-sequence (A5), 69k KV tokens per GPU (A2), so each replica serves
two 32k subagents or four 16k ones at once; two replicas give a fan-out of 4 to 8. Route round-robin through
LiteLLM (A7 showed it passes `reasoning_content`, `content`, `finish_reason` and `usage` unchanged).

**Not used:** `Qwen3-30B-A3B-Thinking-2507-FP8`. B1/B2: 26% one-block compliance at every `max_tokens`,
because it answers with a bare command and no fence (37/50) once its reasoning has gone to `reasoning_content`;
B4: it fell into a repeated-`claim` loop from turn 5. Keep it only as an ablation ("thinking orchestrator")
after the lenient parser below exists. `granite-4.1-8b` ("Lite") is fast but was not tested for compliance; it
is a fallback SUB only. Qwen3-Coder weights were not available on the node.

**Harness defaults from B2:** `max_tokens 4096` for non-thinking models (0/50 cuts at 4096 for the thinking
model; non-thinking replies are ~30 content tokens), 8192 if a thinking model is ever used.

## 2. Parser: one block, with a lenient fallback

B1 showed the failure mode is a bare command, not two blocks. The harness accepts, in this order:
exactly one fenced ```bash/```sh block; else a reply whose `content` is a single non-empty line (or ≤ 3 lines
with no prose sentence) taken verbatim as the command; else a nudge ("Reply with exactly one bash block")
and the turn is logged as a `format_error` event. Two blocks → run the first, say so. Never run anything
found in `reasoning_content`.

## 3. Loop detection ships in v1

B4: the thinking model repeated the same `claim` command for six turns; Qwen3.8 changed strategy by turn 4
but no model was tested beyond 10 turns. Rule: an identical command (after whitespace normalisation) twice in
a row → one-line notice appended to the observation; three times → the notice names the step budget left.
Logged as `loop_notice` events.

## 4. Sandbox: bwrap is not available; decide between three options this week

A6: `bwrap` is not installed and `unshare -rn` fails with `uid_map: Operation not permitted`, so unprivileged
user namespaces are off on the node. Nothing in the harness tests (C1, C2) used a sandbox. Options, in order
of preference:

1. **Apptainer/Singularity** (usual on HPC; check `which apptainer singularity` and whether it runs
   `--containall --no-home --net --network none` for an unprivileged user). If present, one container per
   command with `--bind corpus:/corpus:ro --bind scratch:/work` gives everything bwrap would have.
2. **Ask the admins** for either bubblewrap installed setuid or `user.max_user_namespaces > 0`. A one-line
   request; bwrap is the lightest option and the test plan is written for it.
3. **No namespace sandbox, enforced by convention plus checks** (interim, acceptable for development, to be
   stated as a limitation if it reaches the thesis): corpus `chmod -R a-w` and a manifest hash check before
   and after every run; `HTTP(S)_PROXY` unset and `no_proxy=*` in the command environment, relying on the
   node having no direct egress (verify with `curl -m 5 https://example.com` on the node); `timeout 120` and
   `ulimit -v` per command; `events.jsonl` written to a directory outside the agent's `cwd` and not named in
   its prompt. This does not stop a determined agent, but it catches accidents and it is auditable from the
   hash checks.

Until one of 1–2 is in place, run C3–C7 under option 3 and mark them "unsandboxed" in RESULTS.md.

## 5. Corpus: Docling, frozen once; references need a decision

D1/D2: Docling is the only tested path that recovers tables (10/10 papers, hundreds of rows each), it is
deterministic (10/10 identical hashes on reconversion), titles and author order match DBLP 9/10. Cost 100 s
per paper → ~9.5 h for 337 papers, run once as a Slurm job, hashes into `manifest.json`.

Two consequences the earlier tests hid, because D3/D4/C1 ran on the 6 KB "outline" files, not full text:

- A full Docling paper is 45 to 230 KB (mean ~136 KB, ~35k tokens). A subagent cannot `cat` a paper into a
  32k context, and the 8 KB output cap already prevents it. Subagent briefs must say "read sections with
  grep/sed, not whole files", and the orchestrator's own context budget assumes it never reads a paper whole.
- Docling finds fewer reference entries than GROBID (e.g. 14 vs 57, 15 vs 39). For citation-based concepts
  ("most cited by corpus papers") the GROBID reference list is better. Proposed: Docling Markdown is the
  corpus, with the GROBID-parsed reference list appended as a final `## References (parsed)` section in each
  `.md` (one line per entry: authors, title, year, DBLP id when resolved). Still "just Markdown files", and
  provenance anchors work on it. Decide before the full conversion.

Open from D1: the two-column flow check ("manual review required" on every paper). Review 3 papers by eye
before freezing; interleaved columns would silently break quote anchors across column breaks.

Also re-run D4 and C1 on full-text files once converted (grep over ~46 MB instead of 2 MB; the 8 KB cap on
a 230 KB `cat`).

## 6. Budgets for the evaluation, from A5

With Qwen3.8 at 41.6 tok/s and ~300 output tokens per step, a 150-step run is ~18 min of decode plus
prefill; 300 steps ~36 min. Subagent work runs in parallel on the other GPUs. Plan on 30 to 45 min per run,
one orchestrator run at a time (its KV budget is 1.21× at 65k), so 40 runs ≈ 20 to 30 GPU-node hours.
Start the C3 budget at 150 steps / 400k tokens as planned and adjust after the first real run.

## Next steps, in order

1. Sandbox decision (section 4): `which apptainer singularity`, the egress check, and the admin request.
2. Freeze the corpus (section 5): references decision, column-flow review on 3 papers, full conversion job.
3. Build the minimal loop with the lenient parser, loop detection, output cap (done in C1), hash chain
   (done in C1), `claim` with the D3 anchor library, then run B5, C3, C5, C6.
4. Re-run C2 with a realistic 30k-token history to confirm the hybrid model's prefix cache actually helps.
5. Add `spawn` with the two Heavy replicas, run C4; add `save_tool`, run C7.
