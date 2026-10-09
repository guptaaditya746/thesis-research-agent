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
