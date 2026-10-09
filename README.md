# thesis-research-agent

## Related setup

The `final-final-llm-setup` submodule under `related/` contains the Slurm and
vLLM setup used for the infrastructure measurements. Initialize it after
cloning with:

```bash
git submodule update --init --recursive
```

The `scripts/omen-tunnels` helper manages the SSH tunnels. The
`scripts/omen-tunnels-external` wrapper sets the legacy 1000-port offset used
by the external gateway. Install both on the relevant machines, keeping the
wrapper beside `omen-tunnels` in `PATH`:

```bash
install -m 755 scripts/omen-tunnels ~/.local/bin/omen-tunnels
install -m 755 scripts/omen-tunnels-external ~/.local/bin/omen-tunnels-external
```

## Design and tests

- `thesis_pipeline.html`: one-page diagram of the design (click any box or chip for details; content is in
  the data blocks at the top of its script).
- `docs/slurm_test_plan.md`: the test plan the `tests/` directory implements; results in `tests/RESULTS.md`.
- `docs/plan.md`: the full plan and brainstorm (export of the living doc); `docs/context.md`: the original
  context note the redesign started from.
- `docs/decisions-after-tests.md`: what the first test round decided (models, parser, sandbox, corpus) and
  what is still open.
- `docs/infra-tests-next.md`: infrastructure tests still to run on Slurm with `final-final-llm-setup` and the
  Omen tunnels.
- `docs/codex-infra-runbook.md`: step-by-step instructions for running those tests on the cluster.
- `docs/codex-sandbox-runbook.md`: step-by-step instructions for round 3 (sandbox, Landlock, toolchain, proxy limits).
- Plan and brainstorm (living doc): https://claude.ai/code/artifact/c1715abf-9b58-451b-8ce6-bfd4e7fa7df4
