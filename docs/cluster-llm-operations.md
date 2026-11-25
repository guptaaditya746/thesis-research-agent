# Running LLM experiments on the cluster

This note records operational guidance from the cluster discussion on 25 November 2026. It is intended to make resource choices and job setup easier to review before a run.

## What happened

At about 05:51, four small Python request scripts were started in one Slurm job alongside a vLLM server using three GPUs and a small gateway. The scripts sent requests to the server and wrote text files to Ceph. The reported diagnosis was that several `uv run` processes started close together tried to lock the same environment files. On the affected gammaweb nodes, this was believed to exhaust FUSE worker threads and leave processes in uninterruptible (`D`) state. The cluster team said it would increase the FUSE worker count. Treat this as the diagnosis for that incident, not as proof that every D-state or Ceph stall has the same cause.

The node situation was also transient: gammaweb08 was reported back up, while gammaweb09 was draining for a reboot. Check current node and cluster status before attributing a later failure to this incident.

## Before allocating GPUs

Record why the experiment needs its planned GPU count and whether all models must be available at the same time. In particular, check:

- whether a hosted LLM endpoint can support the experiment;
- whether a smaller model or a fraction of an A100 is sufficient for development and debugging;
- whether the models can run one after another on the same GPU, instead of concurrently on separate GPUs;
- whether the full multi-GPU configuration is needed only for the final experiment.

The cluster discussion estimated that reserving three A100s for the vLLM server can represent more than €10,000 in compute allocation. Confirm the current accounting basis and rates before reusing that estimate in planning. Multiple GPUs are valid when the experiment requires them; state the requirement and use smaller configurations while debugging when they answer the question.

## Keep environments and caches off Ceph

Ceph is distributed storage and can be slow for environment setup and lock-heavy operations. Keep the Python environment on node-local temporary storage where the job allows it, or use a pre-built container. A container also makes the setup easier to reproduce locally. Persist experiment inputs and outputs as needed, but avoid repeatedly resolving or installing packages from a shared Ceph environment.

The cluster setup is expected to remap pip, uv, and Hugging Face Hub caches to fast local temporary storage. Check whether project scripts, shell startup files, or job scripts override those settings. Inspect variable names and paths without printing credentials or tokens:

```bash
env | cut -d= -f1 | sort | grep -E '^(PIP|UV|HF|HUGGINGFACE|TRANSFORMERS)_'
```

Review the corresponding values locally with secrets redacted, and compare them with the cluster-provided job environment. Remove unnecessary overrides so the cluster remapping can take effect.

## Avoid concurrent environment locking

Do package resolution and installation once, before launching request workers. Then launch the scripts using the already prepared environment (for example, its Python executable) rather than starting several `uv run` commands at once against the same environment. If `uv run` is required, serialize setup/locking work and avoid concurrent invocations sharing one environment. Keep the request scripts independent after startup.

This reduces contention on the environment and Ceph. It does not replace checking node health or reporting a persistent FUSE/D-state issue to the cluster team, especially while worker capacity remains limited.

## Run checklist

1. Record the reason for the GPU count, model sizes, and whether models must overlap in time.
2. Debug with a hosted endpoint, smaller model, or GPU slice when that is sufficient.
3. Prepare the environment on node-local temporary storage or in a container.
4. Check that pip, uv, and Hugging Face caches use cluster-provided local paths; remove accidental overrides.
5. Prepare the environment once, then start the request scripts without concurrent `uv` locking.
6. Save run logs, model/configuration details, output locations, and observed node failures so resource use and failures can be reviewed.
