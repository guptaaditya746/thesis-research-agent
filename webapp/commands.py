"""The command lines behind the web app's jobs (`python -m <package>.cli ...`, run by webapp/jobs.py).

- concepts: `agent concepts propose <qid> --question <text>` (rows 2.1, 2.2), into $CONCEPTS;
- run: `agent run` with the picked concept, into $RUNS/web/ (run id `web~<name>`, so web runs never
  mix into a batch manifest's runs root), then the post steps that make a run inspectable and
  scorable: the attach step for claim_off (2.5), `agent verify`, `agent pairs`, `agent graph`,
  `agent export-prov`, and `score run <run_dir> --key <key>` (scoring, M4) against the question's
  reviewed key, else its draft key (then the score is provisional). Scoring needs the key and, for
  claim_off, the finished attach step (attach.json): without them it is skipped, never run on a
  run whose facts would all count as unsourced. It is optional: a failure is a warning on the job;
- gold: `gold build`, `gold triage`, `gold pool`, `gold draft` for the question (milestone 3, C1),
  each on the previous one's output, so a finished job leaves the draft key (status `draft`).

The roots come from the settings (also passed to the children as environment variables); the
LiteLLM key is never on a command line: the children read $LITELLM_MASTER_KEY themselves.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path

from agent.rundir import ATTACH_FILE

from . import goldstate
from .files import RUN_SEP, BadRequest, Conflict, NotFound, check_id, inside
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
    """D (screen and extract), then triage, the review pool and the draft key, each on the one before."""
    folder = goldstate.qdir(settings.gold, qid)
    return [step("gold build", _cli(settings, "gold.cli", "build", qid)),
            step("gold triage", _cli(settings, "gold.cli", "triage", qid), needs=folder / "doc.json"),
            step("gold pool", _cli(settings, "gold.cli", "pool", qid), needs=folder / "triage.jsonl"),
            step("gold draft", _cli(settings, "gold.cli", "draft", qid), needs=folder / "triage.jsonl")]


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


def new_run_name(settings: Settings, prefix: str, request: RunRequest) -> str:
    """`<prefix>-<condition>-s<seed>-web<time>-<random>`: two requests in the same second (a double
    click, a client's retry) get different runs."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    name = check_id(f"{prefix}-{request.condition}-s{request.seed}-web{stamp}-{secrets.token_hex(2)}", "run")
    if (settings.web_runs / name).exists():
        raise Conflict(f"run {name} exists; try again")
    return name


def run_id_of(name: str) -> str:
    """The API's id of a web run: it lives in $RUNS/web/."""
    return f"web{RUN_SEP}{name}"


def score_key(settings: Settings, qid: str) -> Path:
    """The key `score run` uses: $GOLD/<qid>/key.json, else key.draft.json; key.json when neither
    exists yet (the score step is then skipped)."""
    folder = goldstate.qdir(settings.gold, qid)
    return next((folder / n for n in (goldstate.KEY, goldstate.DRAFT) if (folder / n).is_file()), folder / goldstate.KEY)


def run_steps(settings: Settings, concept: Path, name: str, request: RunRequest, qid: str | None) -> list[JobStep]:
    """`qid`: the question whose current pick the concept is; without one the run is not scored."""
    if settings.corpus is None:
        raise Conflict("no corpus configured: set $CORPUS before starting runs")
    run_dir = settings.web_runs / name
    corpus = ["--corpus", settings.corpus]
    agent_root = ["--agent-root", settings.agent_root] if settings.agent_root else []
    budget = [*(["--steps", request.steps] if request.steps else []), *(["--tokens", request.tokens] if request.tokens else [])]
    steps = [step("run", _cli(settings, "agent.cli", "run", "--concept", concept, "--run-id", name,
                              "--runs-root", settings.web_runs, *corpus, "--condition", request.condition,
                              "--temperature", repr(float(request.temperature)), "--seed", request.seed,
                              "--base-url", settings.litellm_base_url, "--sandbox", request.sandbox,
                              *agent_root, *budget))]
    attach = request.condition == "claim_off"
    if attach and request.attach:
        steps.append(step("attach", _cli(settings, "agent.cli", "attach", run_dir, *corpus, "--sandbox",
                                         request.sandbox, *agent_root), needs=run_dir / "answer.json"))
    needs = run_dir / "config.json"
    steps += [
        step("verify", _cli(settings, "agent.cli", "verify", run_dir, *corpus), required=False, needs=needs),
        step("pairs", _cli(settings, "agent.cli", "pairs", run_dir), required=False, needs=run_dir / "answer.json"),
        step("graph", _cli(settings, "agent.cli", "graph", run_dir, "--manifest", settings.corpus_manifest), needs=needs),
        step("export-prov", _cli(settings, "agent.cli", "export-prov", run_dir), needs=run_dir / "graph.json"),
    ]
    if qid is not None:
        key = score_key(settings, qid)
        steps.append(step("score", _cli(settings, "scoring.cli", "run", run_dir, "--key", key, "--gold", settings.gold,
                                        *corpus), required=False,
                          needs=[run_dir / "answer.json", key, *([run_dir / ATTACH_FILE] if attach else [])]))
    return steps
