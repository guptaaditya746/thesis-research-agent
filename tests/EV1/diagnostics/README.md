# EV1 diagnostic evidence

These are diagnostic fixtures and observations for Claude, which may inspect the repository without being able to execute the cluster environment. Product code and historical model outputs were not modified by the audit. See [the diagnosis](../../../docs/ev1-review-diagnosis.md) and [prompt policy](../../../docs/prompt-writing.md).

## Evidence types

- `proposal/`: the actual saved frame, draft, critic, cards, model decisions, and frozen protocol from the 20–21 October session. These contain model recommendations, not human approvals.
- `step10-final-draft.md`: the real last rejected Step 10 response recovered from the model cache. Its original cache key and file hash are in `inputs.json`.
- `step6-summary.json`, `step8-summary.json`: summaries of completed live corpus builds, including exclusions and per-level checks.
- `rag-llm-*-corpus.json`: recorded settings and metadata used to reconstruct the seeded study sets; these are not a new corpus build.
- `review_repro.py`: focused offline probes of the real code, using scripted model replies. They replay observed failures and compare one-variable controls.
- `review_repro.json`: outputs from the executed probes. The identical result was obtained twice. Input hashes, relevant executed-source hashes, command, exit status, and timing are in `inputs.json`.
- `extraction-research/` and `evaluation-research/`: separate research experiments; their notes distinguish real-code replay from illustrative simulations and proposed changes.

## Reproduction

Run from a repository checkout with the locked environment available:

```bash
PYDANTIC_AI_NO_BANNER=1 PYTHONPATH=. .venv/bin/python tests/EV1/diagnostics/review_repro.py --repeat 2 --output tests/EV1/diagnostics/review_repro.json
```

The committed proposal and metadata fixtures are the default inputs. The core harness needs no Slurm allocation, server, credentials, network, or new model calls. It writes runtime files in a temporary directory and removes them on exit. It does not change the original proposal or corpus.

Exit 1 intentionally signals remaining findings. This is a diagnostic script outside default pytest discovery. Some failing rows document a deliberate but risky policy, not a product implementation defect; read each row's classification and the diagnosis before changing behavior. Control rows establish that the relevant variable changes the observed outcome.

The original Step 10 draft remains invalid under the original exact-name contract. Its one-sentence wording control passes deterministic checks only; a live model verifier and a new accepted variant were not run. The three-model generation/verification experiment is a proposal for Claude, not an observed success.

The retention audit measures the distribution change in this saved finite study set. It is not an estimate of population bias. The role and alias probes expose specific counterexamples; they are not broad model-quality or extraction-accuracy benchmarks.
