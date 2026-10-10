# thesis-research-agent

A free LLM research agent over 337 computer-science papers (Markdown), which records every fact with an exact
quote while it researches, in a hash-chained log, and builds a knowledge graph with provenance from it.

**Start here: `docs/STATE.md`**: what is decided, the numbers the design must respect, and what is open.

| Path | What |
|---|---|
| `docs/STATE.md` | The one page to plan from |
| `docs/milestones-1-2.md` | Triaged build plan for milestones 1 and 2 |
| `docs/slurm-final-runbook.md` | The final Slurm session (Codex runs it) |
| `docs/plan.md` | The design; to be revised from STATE.md |
| `docs/decisions-after-tests.md` | Why each decision was taken, test by test |
| `docs/context.md` | The original context note |
| `tests/RESULTS.md` | Every infrastructure test result; logs and scripts under `tests/<id>/` |
| `thesis_pipeline.html` | One-page diagram of the design (click any box for details) |
| `llm-setup/` | Submodule [`thesis-llm-setup`](https://github.com/guptaaditya746/thesis-llm-setup): vLLM + LiteLLM on Slurm |
| `scripts/omen-tunnels*` | Optional SSH tunnels from Slurm to the Omen services (Langfuse) |

After cloning:

```bash
git submodule update --init --recursive
```

Framing discussion: https://claude.ai/code/artifact/c4258535-0673-4590-83f9-4377ee7057fa
