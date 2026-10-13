"""The command lines behind the web app's jobs (`python -m <package>.cli ...`, run by webapp/jobs.py).

- concepts: `agent concepts propose <qid> --question <text>` (rows 2.1, 2.2), into $CONCEPTS;
- run: `agent run` with the picked concept, then the post steps that make a run inspectable and
  scorable: the attach step for claim_off (2.5), `agent verify`, `agent pairs`, `agent graph`,
  `agent export-prov`, and `score run <run_dir>` (scoring, M4; optional: a failure only logs);
- gold: `gold build <qid>` (milestone 3), which reads $CORPUS, $CONCEPTS and $GOLD.

The roots come from the settings (also passed to the children as environment variables); the
LiteLLM key is never on a command line: the children read $LITELLM_MASTER_KEY themselves.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .files import BadRequest, Conflict, NotFound, check_id, inside
from .jobs import step
from .models import JobStep, ProposeRequest, RunRequest
from .settings import Settings


def _cli(settings: Settings, module: str, *args: object) -> list[str]:
    return [settings.python, "-m", module, *(str(a) for a in args)]


def propose_steps(settings: Settings, qid: str, question: str, request: ProposeRequest) -> list[JobStep]:
    argv = _cli(settings, "agent.cli", "concepts", "propose", qid, "--question", question,
                "--root", settings.concepts, "--temperature", repr(float(request.temperature)),
                "--seed", request.seed, "--base-url", settings.litellm_base_url)
    return [step("propose", argv)]


def gold_steps(settings: Settings, qid: str) -> list[JobStep]:
    return [step("gold build", _cli(settings, "gold.cli", "build", qid))]


def concept_for(settings: Settings, request: RunRequest) -> tuple[Path, str]:
    """(concept.json path, run id prefix) of a run request: the qid's picked concept, or a concept
    file inside $CONCEPTS or $RUNS (e.g. another run's concept.json)."""
    if (request.qid is None) == (request.concept_path is None):
        raise BadRequest("give exactly one of qid and concept_path")
    if request.qid is not None:
        qid = check_id(request.qid, "question")
        path = inside(settings.concepts, qid, "concept.json")
        if not path.is_file():
            raise Conflict(f"{qid} has no picked concept yet ({path.name} missing); pick a brief first")
        return path, qid
    given = Path(request.concept_path)
    for root in (settings.concepts, settings.runs):
        try:
            path = inside(root, str(given.relative_to(root) if given.is_absolute() else given))
        except (NotFound, ValueError):
            continue
        if path.is_file() and path.suffix == ".json":
            return path, path.parent.name
    raise BadRequest(f"concept_path must name a concept .json file under {settings.concepts} or {settings.runs}")


def new_run_id(settings: Settings, prefix: str, request: RunRequest) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_id = check_id(f"{prefix}-{request.condition}-s{request.seed}-web{stamp}", "run")
    if (settings.runs / run_id).exists():
        raise Conflict(f"run {run_id} exists; try again in a second")
    return run_id


def run_steps(settings: Settings, concept: Path, run_id: str, request: RunRequest) -> list[JobStep]:
    if settings.corpus is None:
        raise Conflict("no corpus configured: set $CORPUS before starting runs")
    run_dir = settings.runs / run_id
    corpus = ["--corpus", settings.corpus]
    agent_root = ["--agent-root", settings.agent_root] if settings.agent_root else []
    budget = [*(["--steps", request.steps] if request.steps else []), *(["--tokens", request.tokens] if request.tokens else [])]
    steps = [step("run", _cli(settings, "agent.cli", "run", "--concept", concept, "--run-id", run_id,
                              "--runs-root", settings.runs, *corpus, "--condition", request.condition,
                              "--temperature", repr(float(request.temperature)), "--seed", request.seed,
                              "--base-url", settings.litellm_base_url, "--sandbox", request.sandbox,
                              *agent_root, *budget))]
    if request.condition == "claim_off" and request.attach:
        steps.append(step("attach", _cli(settings, "agent.cli", "attach", run_dir, *corpus, "--sandbox",
                                         request.sandbox, *agent_root), needs=run_dir / "answer.json"))
    needs = run_dir / "config.json"
    steps += [
        step("verify", _cli(settings, "agent.cli", "verify", run_dir, *corpus), required=False, needs=needs),
        step("pairs", _cli(settings, "agent.cli", "pairs", run_dir), required=False, needs=run_dir / "answer.json"),
        step("graph", _cli(settings, "agent.cli", "graph", run_dir, "--manifest", settings.corpus_manifest), needs=needs),
        step("export-prov", _cli(settings, "agent.cli", "export-prov", run_dir), needs=run_dir / "graph.json"),
        step("score", _cli(settings, "scoring.cli", "run", run_dir), required=False, needs=run_dir / "answer.json"),
    ]
    return steps
