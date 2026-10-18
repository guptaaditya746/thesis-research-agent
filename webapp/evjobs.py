"""What the app starts and writes, under /api/ev (the guided flow: question -> protocol -> corpus -> run ->
evidence graph -> answer -> scores, the baselines beside the engine; README "Web app").

- questions: the questions file (webapp/evquestions.py), selected, never typed;
- jobs: each POST builds the argv of one command line of docs/slurm-evidence-runbook.md from a fixed template
  and queues it (webapp/jobs.py): `synth build --renderer template` (no model), `evidence run`,
  `evaluate rag-baseline`, `evaluate agent-baseline`, `evaluate score`, `evaluate compare`, the proposal flow's
  `evidence propose frame/draft/critic/cards` and `evidence propose freeze`. Outputs go into the `$EV` layout
  the viewer reads (corpora/, runs/<group>/<name>, scores/, proposals/, cache/), so a result made here looks
  exactly like one made on the command line or on Slurm;
- decisions: `PUT /proposals/{name}/decisions` writes decisions.yaml in the format evidence/propose/cards.py
  validates and answers with what freeze would refuse. Amendments stay on the command line
  (`evidence propose amend`).

Safety: no shell; every value a request gives is either a fixed choice (a Literal), a number with bounds, a
plain name (webapp/files.py ID: no separator, no leading dot or dash, so never a flag or a path) or a model
alias (no leading dash); every path is built from a configured root and a name and checked with `inside`; a
value only ever follows its flag, never stands as one. Writes come only from loopback (webapp/guard.py). A
model job is refused when the server has no key or the gateway does not answer (`gateway_problem`). An
LLM-rendered corpus is not offered: it takes hours on two GPUs and runs on Slurm (runbook step 1).
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from agent.canonical import file_sha256

from .evfiles import EvidenceFiles
from .evmodels import (
    AgentBaselineRequest,
    CompareRequest,
    DecisionsRequest,
    DecisionsResult,
    FreezeRequest,
    ProposeRequest,
    Question,
    RagBaselineRequest,
    RunRequest,
    ScoreRequest,
    SynthRequest,
)
from .evquestions import Questions
from .files import RUN_SEP, BadRequest, Conflict, NotFound, check_id, inside, read_json
from .jobs import JobManager, step
from .models import Job, JobStep
from .settings import Settings

PROPOSE_STEPS = (("frame", "frame.json"), ("draft", "draft.yaml"), ("critic", "critic.json"), ("cards", "cards.json"))
BASELINE_GROUPS = ("rag-baseline", "agent-baseline")   # runs/<group> of the baselines, never an engine run's
GATEWAY_TIMEOUT_S = 3.0


def gateway_problem(settings: Settings) -> str | None:
    """Why a model job would fail at once, or None: no key in the server's environment, or the gateway does not
    answer `GET $LITELLM_BASE_URL/models` within a few seconds. A model job is refused then (409), so it never
    fills the shared record cache with error results. The key is sent only to the gateway and never logged."""
    key = os.environ.get("LITELLM_MASTER_KEY")
    if not key:
        return ("no $LITELLM_MASTER_KEY in the server's environment: start `webapp serve` after sourcing "
                "llm-setup's .env (README \"Web app\")")
    url = settings.litellm_base_url.rstrip("/") + "/models"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=GATEWAY_TIMEOUT_S) as response:  # noqa: S310 - the configured gateway
            if response.status == 200:
                return None
            return f"the model gateway {url} answered HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return f"the model gateway {url} answered HTTP {exc.code}"
    except (OSError, ValueError) as exc:
        return f"the model gateway {url} does not answer ({type(exc).__name__}); is the stack job running?"


async def need_gateway(settings: Settings) -> None:
    problem = await asyncio.to_thread(gateway_problem, settings)
    if problem:
        raise Conflict(f"model job refused: {problem}")


class Commands:
    """The argv templates; every method checks its inputs against the configured roots and returns the steps."""

    def __init__(self, settings: Settings, files: EvidenceFiles, jobs: JobManager, questions: Questions) -> None:
        self.s, self.files, self.jobs, self.questions = settings, files, jobs, questions

    # --- roots and names -----------------------------------------------------------------------------

    def root(self, path: Path | None, what: str, variable: str) -> Path:
        if path is None:
            raise Conflict(f"no {what} directory configured (set ${variable} or $EV)")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def corpora(self) -> Path:
        return self.root(self.s.corpora_dir, "corpora", "CORPORA")

    def runs(self) -> Path:
        return self.root(self.s.ev_runs_dir, "runs", "EV_RUNS")

    def scores(self) -> Path:
        return self.root(self.s.scores_dir, "scores", "SCORES")

    def proposals(self) -> Path:
        return self.root(self.s.proposals_dir, "proposals", "EV_PROPOSALS")

    def engine_cache(self) -> Path:
        return self.root(self.s.ev_cache_dir, "cache", "EV_CACHE")

    def cache_root(self) -> Path:
        return self.root(self.s.cache_root, "cache", "EV")

    def tool(self, *args: object) -> list[str]:
        return [self.s.python, "-m", "webapp.tool", *(str(a) for a in args)]

    def free(self, ref: str, value: str) -> None:
        job = self.jobs.busy(ref, value)
        if job is not None:
            raise Conflict(f"job {job.id} ({job.kind}) is {job.state} on {ref} {value}; wait for it or cancel it")

    def corpus(self, name: str) -> Path:
        return self.files.corpus_dir(name)   # NotFound unless a corpus with a manifest is there

    def protocol(self, source: str, name: str) -> Path:
        check_id(name, "protocol")
        if source == "repo":
            path = inside(self.s.protocols, f"{name}.yaml")
            if not path.is_file():
                raise NotFound(f"no such protocol: {name!r}")
            return path
        path = inside(self.proposals(), name, "protocol.yaml")
        if not path.parent.is_dir():
            raise NotFound(f"no such proposal: {name!r}")
        if not path.is_file():
            raise Conflict(f"proposal {name} is not frozen yet (no protocol.yaml): decide the cards and freeze it")
        return path

    @staticmethod
    def group(request: RunRequest) -> str:
        """The runbook's group names: regex-only, cascade, cascade-gaps, agentic, agentic-gaps; else the protocol's
        name (a proposal's prefixed with proposal-) and the selection."""
        gaps = "-gaps" if request.strategy == "gaps" else ""
        name, source = request.protocol.name, request.protocol.source
        if request.extractors == "regex-only" and source == "repo" and name.startswith("rag-factuality"):
            return "regex-only"   # the regex extractors of both RAG protocols are the same
        if source == "repo" and name == "rag-factuality":
            return f"cascade{gaps}"
        if source == "repo" and name == "rag-factuality-agentic":
            return f"agentic{gaps}"
        prefix = f"proposal-{name}" if source == "proposal" else name
        return f"{prefix}-{request.extractors}{gaps if request.extractors != 'regex-only' else ''}"

    # --- the commands ----------------------------------------------------------------------------------

    def synth(self, r: SynthRequest) -> tuple[list[JobStep], dict[str, str]]:
        root = self.corpora()
        outputs = [f"{r.name}-{level}" for level in r.levels] + [f"{r.name}-mixed"]
        there = [n for n in outputs if inside(root, check_id(n, "corpus")).exists()]
        if there:
            raise Conflict(f"corpora {', '.join(there)} exist; choose another name")
        self.free("corpus_set", r.name)
        argv = self.tool("synth", "build", "--name", r.name, "--seed", r.seed, "--studies", r.studies,
                         "--renderer", "template", "--levels", ",".join(dict.fromkeys(r.levels)),
                         "--duplicates", r.duplicates, "--missing", r.missing, "--outliers", r.outliers,
                         "--irrelevant", r.irrelevant, "--out", root)
        return [step("synth build", argv)], {"corpus_set": r.name, "corpus": f"{r.name}-mixed"}

    def run(self, r: RunRequest) -> tuple[list[JobStep], dict[str, str]]:
        corpus = self.corpus(r.corpus)
        protocol = self.protocol(r.protocol.source, r.protocol.name)
        group, name = r.group or self.group(r), r.name or r.corpus
        check_id(group, "group")
        check_id(name, "run")
        if group in BASELINE_GROUPS:
            raise BadRequest(f"the group {group} holds the baselines' answers; an engine run goes elsewhere")
        out = inside(self.runs(), group)
        if inside(out, name).exists():
            raise Conflict(f"run {group}/{name} exists; give the run another name")
        run_id = f"{group}{RUN_SEP}{name}"
        self.free("run", run_id)
        argv = self.tool("evidence", "run", "--protocol", protocol, "--corpus", corpus, "--out", out,
                         "--cache", self.engine_cache(), "--extractors", r.extractors, "--strategy", r.strategy,
                         "--model", r.model, "--run-id", name, *(["--retry-errors"] if r.retry_errors else []))
        return [step("evidence run", argv)], {"run": run_id, "corpus": r.corpus}

    def _baseline_out(self, system: str, corpus: str) -> tuple[Path, str]:
        out = inside(self.runs(), system, corpus)
        if (out / "answer.json").exists():
            raise Conflict(f"{system}/{corpus} has an answer.json; move it away to run the baseline again")
        run_id = f"{system}{RUN_SEP}{corpus}"
        self.free("run", run_id)
        return out, run_id

    def rag_baseline(self, r: RagBaselineRequest) -> tuple[list[JobStep], dict[str, str]]:
        corpus = self.corpus(r.corpus)
        out, run_id = self._baseline_out("rag-baseline", r.corpus)
        argv = self.tool("evaluate", "rag-baseline", "--corpus", corpus, "--out", out,
                         "--cache", self.cache_root() / "rag-baseline.jsonl", "--model", r.model,
                         "--retrieval", r.retrieval, "--k", r.k)
        return [step("rag-baseline", argv)], {"run": run_id, "corpus": r.corpus}

    def agent_baseline(self, r: AgentBaselineRequest) -> tuple[list[JobStep], dict[str, str]]:
        corpus = self.corpus(r.corpus)
        out, run_id = self._baseline_out("agent-baseline", r.corpus)
        agent_root = ["--agent-root", self.s.agent_root] if self.s.agent_root else []
        argv = self.tool("evaluate", "agent-baseline", "--corpus", corpus, "--out", out,
                         "--cache", self.cache_root() / "agent-baseline.jsonl", "--model", r.model, *agent_root,
                         "--base-url", self.s.litellm_base_url, "--run-id", r.corpus)
        return [step("agent-baseline", argv)], {"run": run_id, "corpus": r.corpus}

    def score(self, r: ScoreRequest) -> tuple[list[JobStep], dict[str, str]]:
        path = self.files.run_dir(r.run)
        summary = self.files._run_summary(path)
        if summary is None or summary.kind != "engine":
            raise Conflict(f"{r.run} is not an engine run (a baseline is scored beside the engine run of its corpus)")
        self.free("run", r.run)
        if not summary.complete or not (path / "answer.json").is_file():
            raise Conflict(f"{r.run} has not finished (no run.json / answer.json yet)")
        if summary.corpus is None:
            raise Conflict(f"the corpus of {r.run} is not under the corpora root")
        corpus = self.corpus(summary.corpus)
        baselines: list[Any] = []
        for system in ("rag-baseline", "agent-baseline"):
            answer = inside(self.runs(), system, summary.corpus, "answer.json")
            if answer.is_file():
                baselines += ["--baseline", answer]
        # the latest re-execution beside the run (`evidence reexec` writes <run>-reexec-<stamp>/reexec.json;
        # runbook step 7.1), for the stability score
        reexecs = sorted(p / "reexec.json" for p in path.parent.glob(f"{path.name}-reexec-*")
                         if (p / "reexec.json").is_file() and not p.is_symlink())
        reexec = ["--reexec", reexecs[-1]] if reexecs else []
        score_id = f"{summary.group}{RUN_SEP}{summary.name}"
        self.free("score", score_id)
        out = inside(self.scores(), summary.group, summary.name)
        argv = self.tool("evaluate", "score", "--run", path, "--corpus", corpus, *baselines, *reexec, "--out", out)
        return [step("evaluate score", argv)], {"score": score_id}

    def compare(self, r: CompareRequest) -> tuple[list[JobStep], dict[str, str]]:
        reports = [self.files._score_dir(score_id, "report.json")[0] for score_id in dict.fromkeys(r.reports)]
        if len(reports) < 2:
            raise Conflict("a comparison needs two different reports")
        out = inside(self.scores(), r.name)
        if out.exists() and not (out / "compare.json").is_file():
            raise Conflict(f"scores/{r.name} exists and is not a comparison; choose another name")
        self.free("score", r.name)
        argv = self.tool("evaluate", "compare", "--out", out, *reports)
        return [step("evaluate compare", argv)], {"score": r.name}

    def propose(self, r: ProposeRequest) -> tuple[list[JobStep], dict[str, str], Question]:
        q = self.questions.get(r.question)
        directory = inside(self.proposals(), r.proposal)
        if (directory / "protocol.yaml").exists():
            raise Conflict(f"proposal {r.proposal} is frozen; change it with `evidence propose amend` (command line)")
        frame = read_json(directory / "frame.json")
        if isinstance(frame, dict) and frame.get("question") != q.question:
            raise Conflict(f"proposal {r.proposal} asks another question; choose another name")
        self.free("proposal", r.proposal)
        todo = [name for name, file in PROPOSE_STEPS if not (directory / file).exists()]
        if not todo:
            raise Conflict(f"proposal {r.proposal} has its cards: decide them and freeze it")
        first = [name for name, _ in PROPOSE_STEPS].index(todo[0])
        argv = {"frame": self.tool("evidence", "propose", "frame", "--question", q.question,
                                   *(["--vocab", q.vocab] if q.vocab else []), "--out", directory, "--model", r.model),
                "draft": self.tool("evidence", "propose", "draft", directory),
                "critic": self.tool("evidence", "propose", "critic", directory, "--model", r.model),
                "cards": self.tool("evidence", "propose", "cards", directory, "--model", r.model)}
        steps = []
        for n, (name, _) in enumerate(PROPOSE_STEPS[first:], start=first):
            needs = directory / PROPOSE_STEPS[n - 1][1] if n > 0 else None
            steps.append(step(f"propose {name}", argv[name], needs=needs))
        return steps, {"proposal": r.proposal}, q

    def proposal_dir(self, name: str) -> Path:
        directory = inside(self.proposals(), check_id(name, "proposal"))
        if not (directory / "cards.json").is_file():
            raise Conflict(f"proposal {name} has no cards yet (run the proposal flow first)")
        if (directory / "protocol.yaml").exists():
            raise Conflict(f"proposal {name} is frozen; change it with `evidence propose amend` (command line)")
        self.free("proposal", name)
        return directory

    def freeze(self, r: FreezeRequest) -> tuple[list[JobStep], dict[str, str]]:
        directory = self.proposal_dir(r.proposal)
        cards = read_json(directory / "cards.json") or {}
        if not (directory / "decisions.yaml").is_file():
            raise Conflict(f"proposal {r.proposal} has no decisions.yaml")
        _, problems = self.files._decisions(directory, cards.get("cards") or [])
        if problems:
            raise Conflict("decisions.yaml refused:\n  " + "\n  ".join(problems))
        return [step("propose freeze", self.tool("evidence", "propose", "freeze", directory))], {"proposal": r.proposal}

    def decisions(self, name: str, r: DecisionsRequest) -> DecisionsResult:
        """decisions.yaml as `evidence propose cards` writes it (its header, `decisions:` in card order), each
        entry {card, choice, reason, by} plus `value` with choice custom.

        `by` is `model`, the server's $WEBAPP_USER, or the name the file already has for that card (a hand edit's,
        kept as it is): nobody else's name is written. The form sends the file's sha256 as it loaded it; a file
        changed since (a hand edit, another tab) is refused with 409 unless `force`, so no edit is lost unseen."""
        from evidence.propose.cards import CUSTOM, HEADER
        from evidence.propose.common import dump_yaml

        directory = self.proposal_dir(name)
        path = directory / "decisions.yaml"
        current = file_sha256(path) if path.is_file() else None
        if current != r.base_sha256 and not r.force:
            raise Conflict("decisions.yaml changed since the form loaded it (edited by hand or in another tab): "
                           "reload to see it, or overwrite it")
        cards = (read_json(directory / "cards.json") or {}).get("cards") or []
        on_file, _ = self.files._decisions(directory, cards)
        order = {c.get("id"): n for n, c in enumerate(cards)}
        entries = []
        for d in sorted(r.decisions, key=lambda d: order.get(d.card, len(order))):
            kept = on_file.get(d.card, {}).get("by") if isinstance(on_file.get(d.card), dict) else None
            if d.by not in ("model", self.s.user) and d.by != kept:
                raise BadRequest(f"{d.card}: by {d.by!r} is neither the model, you ({self.s.user}) nor who decided "
                                 "this card in decisions.yaml")
            entry: dict[str, Any] = {"card": d.card, "choice": d.choice, "reason": d.reason.strip(), "by": d.by}
            if d.choice == CUSTOM:
                entry["value"] = d.value
            entries.append(entry)
        write_text_atomic(path, HEADER + dump_yaml({"decisions": entries}))
        _, problems = self.files._decisions(directory, cards)
        return DecisionsResult(written=str(path), sha256=file_sha256(path), problems=problems)


def write_text_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def evjobs_router(settings: Settings, files: EvidenceFiles, jobs: JobManager, questions: Questions) -> APIRouter:
    api = APIRouter(generate_unique_id_function=lambda route: route.name, tags=["evidence"])
    c = Commands(settings, files, jobs, questions)

    # --- questions -------------------------------------------------------------------------------------

    @api.get("/questions", response_model=list[Question])
    def ev_questions() -> list[Question]:
        return questions.list()

    @api.get("/questions/{qid}", response_model=Question)
    def ev_question(qid: str) -> Question:
        return questions.get(check_id(qid, "question"))

    # --- jobs ----------------------------------------------------------------------------------------

    @api.get("/jobs", response_model=list[Job])
    def ev_jobs() -> list[Job]:
        return jobs.list()

    @api.get("/jobs/{job_id}", response_model=Job)
    def ev_job(job_id: str) -> Job:
        return jobs.get(job_id)

    @api.get("/jobs/{job_id}/log", response_class=PlainTextResponse,
             responses={200: {"content": {"text/plain": {}}, "description": "the last lines of the job's log"}})
    def ev_job_log(job_id: str, lines: int = Query(200, ge=1, le=5000)) -> PlainTextResponse:
        return PlainTextResponse(jobs.tail(job_id, lines))

    @api.post("/jobs/{job_id}/cancel", response_model=Job)
    async def ev_cancel_job(job_id: str) -> Job:
        return jobs.cancel(job_id)

    @api.post("/jobs/synth", response_model=Job, status_code=202)
    async def ev_start_synth(request: SynthRequest) -> Job:
        steps, refs = c.synth(request)
        return jobs.submit("synth", request.model_dump(), steps, lane="cpu", refs=refs)

    @api.post("/jobs/run", response_model=Job, status_code=202)
    async def ev_start_run(request: RunRequest) -> Job:
        steps, refs = c.run(request)
        lane = "cpu" if request.extractors == "regex-only" else "model"
        if lane == "model":
            await need_gateway(settings)
        return jobs.submit("run", request.model_dump(), steps, lane=lane, refs=refs)

    @api.post("/jobs/rag-baseline", response_model=Job, status_code=202)
    async def ev_start_rag_baseline(request: RagBaselineRequest) -> Job:
        steps, refs = c.rag_baseline(request)
        await need_gateway(settings)
        return jobs.submit("rag-baseline", request.model_dump(), steps, lane="model", refs=refs)

    @api.post("/jobs/agent-baseline", response_model=Job, status_code=202)
    async def ev_start_agent_baseline(request: AgentBaselineRequest) -> Job:
        steps, refs = c.agent_baseline(request)
        await need_gateway(settings)
        return jobs.submit("agent-baseline", request.model_dump(), steps, lane="model", refs=refs)

    @api.post("/jobs/score", response_model=Job, status_code=202)
    async def ev_start_score(request: ScoreRequest) -> Job:
        steps, refs = c.score(request)
        return jobs.submit("score", request.model_dump(), steps, lane="cpu", refs=refs)

    @api.post("/jobs/compare", response_model=Job, status_code=202)
    async def ev_start_compare(request: CompareRequest) -> Job:
        steps, refs = c.compare(request)
        return jobs.submit("compare", request.model_dump(), steps, lane="cpu", refs=refs)

    @api.post("/jobs/propose", response_model=Job, status_code=202)
    async def ev_start_propose(request: ProposeRequest) -> Job:
        steps, refs, _ = c.propose(request)
        await need_gateway(settings)
        return jobs.submit("propose", request.model_dump(), steps, lane="model", refs=refs)

    @api.post("/jobs/freeze", response_model=Job, status_code=202)
    async def ev_start_freeze(request: FreezeRequest) -> Job:
        steps, refs = c.freeze(request)
        return jobs.submit("freeze", request.model_dump(), steps, lane="cpu", refs=refs)

    # --- decisions -----------------------------------------------------------------------------------

    @api.put("/proposals/{name}/decisions", response_model=DecisionsResult)
    def ev_put_decisions(name: str, request: DecisionsRequest) -> DecisionsResult:
        return c.decisions(name, request)

    return api


