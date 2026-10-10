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

**Start here: `docs/STATE.md`**, one page with what is decided, the measured numbers the design must
respect, and what is still open. Everything below is detail or history.

- `thesis_pipeline.html`: one-page diagram of the design (click any box or chip for details).
- `docs/plan.md`: the design and brainstorm; to be revised after the framing decisions. `docs/context.md`:
  the original context note.
- `docs/decisions-after-tests.md`: why each decision was taken, test by test.
- `tests/RESULTS.md`: every test result (rounds 1 to 3).
- `docs/codex-round4-runbook.md`: the next Slurm session (seccomp, proxy timeout and routing, prefix cache at 30k).
- History: `docs/slurm_test_plan.md` (round 1), `docs/infra-tests-next.md` (rounds 2 and 3),
  `docs/codex-infra-runbook.md` (round 2), `docs/codex-sandbox-runbook.md` (round 3).
- Plan and brainstorm (living doc): https://claude.ai/code/artifact/c1715abf-9b58-451b-8ce6-bfd4e7fa7df4
