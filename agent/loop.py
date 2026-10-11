"""Main loop (milestones-1-2.md rows 1.8 and 1.9): mini-swe-agent 2.4.6 with our parser, sandbox and broker.

One step is one model reply. Per step the harness
1. calls `orch-model` through LiteLLM (thinking off, max_tokens 4096, the run's temperature and
   seed) and writes an `ai_model_invocation` record;
2. parses the reply's content (agent/parse.py; the reasoning field is never run). Unparseable
   output becomes a `coverage` record and a nudge, and nothing runs;
3. runs a command in the sandbox wrapper (agent/sandbox.py) with a fresh claim channel tagged
   with the step id, writes the full output to out/step-NNNN.txt and an `agent_tool` record whose
   parent is the model call, and shows the agent at most 8 KB plus a pointer to the file, a
   notice when it repeats a command (B4), and what is left of the budget;
4. or takes a json block as the final answer, completes it (concept hash, kind, origin), checks
   it with validate_answer and the run's accepted claim ids, and writes answer.json.

Budgets (steps, tokens) are announced in the prompt and after every command. When one runs out,
or the proxy answers HTTP 400 ContextWindowExceededError (L8; never retried), the agent is told to
conclude and gets `conclude_replies` more replies in which no command runs. A run that ends
without a valid answer still gets an answer.json with no rows and the reason in `notes`, plus a
`coverage` record, so every run directory is complete.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

# mini-swe-agent prints a banner and reads a user .env on import; keep runs independent of both.
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")
os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(Path(tempfile.gettempdir()) / "thesis-agent-mswea"))

import litellm  # noqa: E402
from minisweagent import __version__ as MSWEA_VERSION  # noqa: E402
from minisweagent.agents.default import DefaultAgent  # noqa: E402
from minisweagent.exceptions import InterruptAgentFlow, LimitsExceeded, Submitted  # noqa: E402
from minisweagent.models.litellm_model import LitellmModel  # noqa: E402
from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel  # noqa: E402
from minisweagent.models.utils.retry import retry  # noqa: E402

from . import sandbox  # noqa: E402
from .canonical import canonical_bytes, sha256_hex, write_json  # noqa: E402
from .answer import accepted_claim_ids, build_answer, empty_answer  # noqa: E402
from .parse import Parsed, files_read, normalise_command, parse_reply  # noqa: E402
from .prompts import Prompt, task_vars  # noqa: E402
from .rundir import COMMAND_LIMITS, ORCHESTRATOR, RunDir, utc_now  # noqa: E402

HARNESS = f"mini-swe-agent {MSWEA_VERSION}"
AGENT_DIR = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "http://127.0.0.1:4000/v1"
CONCLUDE_REPLIES = 2
SYSTEM_DIRS = ("/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc", "/dev")
CONTEXT_FULL_MARKERS = ("contextwindowexceeded", "context_length_exceeded", "maximum context length",
                        "context length")
POSIX_BROKER = sys.platform != "win32" and hasattr(socket, "send_fds") and hasattr(socket, "SOCK_SEQPACKET")
logger = logging.getLogger("agent.loop")


class Broker(Protocol):
    """BrokerProcess or InProcessBroker (agent/broker_client.py)."""

    def record(self, record: dict[str, Any]) -> dict[str, Any]: ...
    def claim_channel(self, step_id: int, agent_id: str = "main", origin: str = "research") -> Any: ...
    def head(self) -> dict[str, Any]: ...
    def close(self, timeout: float = 60) -> dict[str, Any]: ...


class ContextFull(Exception):
    """The proxy refused the prompt as too long (HTTP 400). Never retried: the agent concludes."""

    def __init__(self, detail: str, prompt_sha256: str, started_at: str, seconds: float) -> None:
        super().__init__(detail)
        self.detail = detail
        self.prompt_sha256 = prompt_sha256
        self.started_at = started_at
        self.seconds = seconds


def is_context_full(exc: Exception) -> bool:
    if isinstance(exc, litellm.exceptions.ContextWindowExceededError):
        return True
    text = f"{type(exc).__name__} {exc}".lower()
    return isinstance(exc, litellm.exceptions.BadRequestError) and any(m in text for m in CONTEXT_FULL_MARKERS)


# --- model -----------------------------------------------------------------------------------------

class OrchestratorModel(LitellmTextbasedModel):
    """`orch-model` through LiteLLM, as mini-swe-agent's text-based model.

    query() returns mini's assistant message; `extra.call` holds what the ai_model_invocation
    record needs and `extra.parsed` the parse result. The API key is read from the environment at
    call time and kept out of the model config, so it never reaches trajectory.json or a record.
    """

    # 400s are never retried (L8); everything mini aborts on stays aborted.
    abort_exceptions = [*LitellmModel.abort_exceptions, litellm.exceptions.BadRequestError]

    def __init__(self, *, base_url: str = DEFAULT_BASE_URL, temperature: float, seed: int,
                 alias: str = ORCHESTRATOR["alias"], max_tokens: int = ORCHESTRATOR["max_tokens"],
                 thinking: bool = ORCHESTRATOR["thinking"], timeout_s: float = 600,
                 api_key_env: str = "LITELLM_MASTER_KEY") -> None:
        super().__init__(model_name=f"openai/{alias}", cost_tracking="ignore_errors", model_kwargs={
            "api_base": base_url, "temperature": temperature, "seed": seed, "max_tokens": max_tokens,
            "timeout": timeout_s, "extra_body": {"chat_template_kwargs": {"enable_thinking": thinking}}})
        self.base_url = base_url
        self.api_key_env = api_key_env
        self.settings = {"model": alias, "model_name": ORCHESTRATOR["name"], "revision": ORCHESTRATOR["revision"],
                         "temperature": temperature, "seed": seed, "max_tokens": max_tokens, "thinking": thinking}

    def _query(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        key = os.environ.get(self.api_key_env) or "none"
        return litellm.completion(model=self.config.model_name, messages=messages, api_key=key,
                                  **(self.config.model_kwargs | kwargs))

    def query(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        prepared = self._prepare_messages_for_api(messages)
        prompt_sha = sha256_hex(canonical_bytes(prepared))
        started, t0 = utc_now(), time.monotonic()
        try:
            for attempt in retry(logger=logger, abort_exceptions=self.abort_exceptions):
                with attempt:
                    response = self._query(prepared, **kwargs)
        except litellm.exceptions.BadRequestError as exc:
            if is_context_full(exc):
                raise ContextFull(str(exc)[:500], prompt_sha, started, time.monotonic() - t0) from exc
            raise
        raw = response if isinstance(response, dict) else response.model_dump()
        choice = raw["choices"][0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        # Read only to hash it: nothing in the reasoning field is ever parsed or run.
        reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
        usage = raw.get("usage") or {}
        usage = {k: int(usage.get(k) or 0) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
        if not usage["total_tokens"]:
            usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        call = {
            "prompt_sha256": prompt_sha, "messages": len(prepared), "started_at": started, "ended_at": utc_now(),
            "seconds": round(time.monotonic() - t0, 3), "response_sha256": sha256_hex(content.encode("utf-8")),
            "reasoning_sha256": sha256_hex(reasoning.encode("utf-8")) if reasoning else None,
            "finish_reason": choice.get("finish_reason"), "usage": usage, "served_model": raw.get("model"),
        }
        parsed = parse_reply(content)
        return {"role": "assistant", "content": content, "extra": {"call": call, "parsed": asdict(parsed)}}

    def serialize(self) -> dict[str, Any]:
        data = super().serialize()
        data["info"]["config"]["model"]["model_kwargs"].pop("api_key", None)
        return data


# --- sandbox environment ---------------------------------------------------------------------------

class SandboxEnvironment:
    """Runs one agent command per step through agent/sandbox.py (mini's Environment protocol)."""

    def __init__(self, run: RunDir, *, corpus: Path, mode: str, claim: bool, agent_root: Path | None = None,
                 limits: dict[str, int] | None = None, extra_path: tuple[str, ...] = (),
                 python: str = sys.executable) -> None:
        if mode not in sandbox.MODES:
            raise ValueError(f"sandbox mode must be one of {sandbox.MODES}")
        self.run = run
        self.corpus = Path(corpus).resolve()
        self.mode = mode
        self.claim = claim
        self.agent_root = Path(agent_root).resolve() if agent_root else None
        self.limits = dict(limits or COMMAND_LIMITS)
        self.extra_path = tuple(extra_path)
        self.python = python
        self.config = {"mode": mode, "claim": claim}

    def path(self) -> str:
        dirs = [str(AGENT_DIR / "bin")] if self.claim else []
        if self.agent_root:
            dirs += [str(self.agent_root / "bin"), str(self.agent_root / "agent-venv" / "bin")]
        return ":".join([*dirs, *self.extra_path, "/usr/local/bin", "/usr/bin", "/bin"])

    def readonly(self) -> list[str]:
        paths = [*SYSTEM_DIRS, str(self.corpus), str(self.run.out.resolve()), *self.extra_path]
        if self.claim:
            paths.append(str(AGENT_DIR))  # bin/claim and claim_client.py
        if self.agent_root:
            paths.append(str(self.agent_root))
            venv_python = self.agent_root / "agent-venv" / "bin" / "python"
            if venv_python.exists():  # the uv-managed interpreter the venv links to (S5c)
                paths.append(str(Path(os.path.realpath(venv_python)).parent.parent))
        return [p for p in dict.fromkeys(paths) if os.path.exists(p)]

    def argv(self, command: str) -> list[str]:
        scratch = str(self.run.scratch.resolve())
        argv = [self.python, "-I", str(AGENT_DIR / "sandbox.py"), "--mode", self.mode, "--workdir", scratch,
                "--timeout", str(self.limits["timeout_s"]), "--ulimit-v-kib", str(self.limits["ulimit_v_kib"])]
        if self.mode == "landlock":
            for path in self.readonly():
                argv += ["--readonly", path]
            argv += ["--writable", scratch, "--writefile", "/dev/null"]
        return [*argv, "--", command]

    def environment(self, claim_fd: int | None) -> dict[str, str]:
        scratch = str(self.run.scratch.resolve())
        env = {"PATH": self.path(), "CORPUS": str(self.corpus), "HOME": scratch, "TMPDIR": scratch,
               "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
        if claim_fd is not None:
            env["CLAIM_FD"] = str(claim_fd)
        return env

    def execute(self, action: dict[str, Any], cwd: str = "", *, step_id: int,
                broker: Broker | None = None) -> sandbox.Result:
        """Run `action["command"]`; with a broker and claim on, the command gets CLAIM_FD for this step."""
        sock = broker.claim_channel(step_id, agent_id="main", origin="research") if broker and self.claim else None
        try:
            fds = (sock.fileno(),) if sock else ()
            return sandbox.run_command(self.argv(action["command"]), env=self.environment(fds[0] if fds else None),
                                       cwd=str(self.run.scratch.resolve()), timeout_s=self.limits["timeout_s"],
                                       pass_fds=fds, before_wait=sock.close if sock else None)
        finally:
            if sock:
                sock.close()  # no-op after before_wait; closes it if Popen failed

    def get_template_vars(self, **kwargs: Any) -> dict[str, Any]:
        return {}

    def serialize(self) -> dict[str, Any]:
        return {"info": {"config": {"environment": dict(self.config),
                                    "environment_type": f"{type(self).__module__}.{type(self).__name__}"}}}


# --- agent -----------------------------------------------------------------------------------------

@dataclass
class Outcome:
    exit_status: str  # submitted, budget, context_full, error
    steps: int
    model_calls: int
    tokens: int
    answer_rows: int


class ResearchAgent(DefaultAgent):
    """mini-swe-agent's DefaultAgent with records, sandboxed commands, budgets and a final answer."""

    def __init__(self, model: OrchestratorModel, env: SandboxEnvironment, *, broker: Broker, run: RunDir,
                 concept: dict[str, Any], prompt: Prompt, budget: dict[str, Any],
                 conclude_replies: int = CONCLUDE_REPLIES) -> None:
        super().__init__(model, env, system_template=prompt.system, instance_template=prompt.task,
                         step_limit=0, cost_limit=0.0, max_consecutive_format_errors=0,
                         output_path=run.root / "trajectory.json")
        self.broker = broker
        self.run_dir = run
        self.concept = concept
        self.budget = {"steps": int(budget["steps"]), "tokens": int(budget["tokens"])}
        self.conclude_replies = conclude_replies
        self.cap = int(env.limits["output_cap_bytes"])
        self.extra_template_vars = {**self.budget, **task_vars(concept)}
        self.research_steps = 0
        self.tokens = 0
        self.phase = "research"
        self.conclude_reason = ""
        self.conclude_used = 0
        self.overflows = 0
        self.last_command = ""
        self.repeats = 0
        self.model_task_id: str | None = None
        self.answer: dict[str, Any] | None = None
        self._checked: tuple[dict[str, Any] | None, list[str]] = (None, [])

    # records

    def _record(self, record: dict[str, Any]) -> dict[str, Any]:
        # origin "research" marks the research loop; the baseline's attach step (2.5) writes "attach".
        meta = {"origin": "research", **record.get("custom_metadata", {})}
        return self.broker.record({"agent_id": "main", **record, "custom_metadata": meta})

    def _record_call(self, step: int, call: dict[str, Any], parsed: dict[str, Any], final_answer: bool) -> str:
        reply = self._record({
            "subtype": "ai_model_invocation", "step_id": step,
            "used": {"prompt_sha256": call["prompt_sha256"], "messages": call["messages"], **self.model.settings},
            "generated": {k: call[k] for k in ("response_sha256", "reasoning_sha256", "finish_reason", "usage",
                                               "served_model")} | {"parse": parsed["mode"], "reply": parsed["kind"]},
            "started_at": call["started_at"], "ended_at": call["ended_at"],
            # final_answer: this reply's json block became answer.json (the KG/PROV export links them).
            "custom_metadata": {"phase": self.phase, "seconds": call["seconds"], "final_answer": final_answer},
        })
        return reply["task_id"]

    def _coverage(self, step: int, reason: str, raw: str, detail: Any = None) -> None:
        generated: dict[str, Any] = {"reason": reason}
        if detail is not None:
            generated["detail"] = detail
        self._record({"subtype": "coverage", "step_id": step, "parent_task_id": self.model_task_id,
                      "used": {"raw_output_sha256": sha256_hex(raw.encode("utf-8"))}, "generated": generated,
                      "status": "not_run", "custom_metadata": {"phase": self.phase}})

    # budget and conclusion

    def budget_line(self) -> str:
        return (f"[Budget: {self.research_steps} of {self.budget['steps']} steps and {self.tokens:,} of "
                f"{self.budget['tokens']:,} tokens used.]")

    def _left(self) -> str:
        return (f"{max(0, self.budget['steps'] - self.research_steps)} steps and "
                f"{max(0, self.budget['tokens'] - self.tokens):,} tokens left")

    def _conclude(self, reason: str, text: str) -> dict[str, Any]:
        self.phase, self.conclude_reason, self.conclude_used = "conclude", reason, 0
        return {"role": "user", "content": text + " Reply now with your reasoning and the final answer in EXACTLY "
                "ONE fenced json block; no further commands run.", "extra": {"kind": "conclude", "reason": reason}}

    def _stub_observations(self, drop_reasoning: bool) -> None:
        """After a context overflow: keep the commands and the claim replies, drop the outputs."""
        for message in self.messages[2:]:
            extra = message.get("extra", {})
            if extra.get("kind") == "observation":
                kept = [ln for ln in message["content"].splitlines() if '"claim_id"' in ln or '"reason"' in ln]
                message["content"] = "\n".join(["[output removed: context full]", *kept])
            elif drop_reasoning and message.get("role") == "assistant":
                parsed = extra.get("parsed", {})
                message["content"] = f"[reply shortened: context full] {parsed.get('command') or ''}".strip()

    def _overflow(self, step: int, exc: ContextFull) -> None:
        self._record({"subtype": "ai_model_invocation", "step_id": step,
                      "used": {"prompt_sha256": exc.prompt_sha256, "messages": len(self.messages), **self.model.settings},
                      "generated": {"error": "context_window_exceeded"}, "started_at": exc.started_at,
                      "status": "failed", "custom_metadata": {"phase": self.phase, "seconds": round(exc.seconds, 3),
                                                              "detail": exc.detail}})
        self.overflows += 1
        if self.overflows > 2:
            raise LimitsExceeded(self._exit("context_full"))
        self._stub_observations(drop_reasoning=self.overflows == 2)
        raise InterruptAgentFlow(self._conclude(
            "context_full", "Context full: the conversation no longer fits the model's context, so earlier "
            "command outputs were removed (claim replies kept). Conclude now."))

    @staticmethod
    def _exit(status: str) -> dict[str, Any]:
        return {"role": "exit", "content": status, "extra": {"exit_status": status, "submission": ""}}

    # mini-swe-agent hooks

    def query(self) -> dict[str, Any]:
        if self.phase == "research" and (self.research_steps >= self.budget["steps"]
                                         or self.tokens >= self.budget["tokens"]):
            raise InterruptAgentFlow(self._conclude("budget", f"Budget used up. {self.budget_line()}"))
        if self.phase == "conclude" and self.conclude_used >= self.conclude_replies:
            raise LimitsExceeded(self._exit(self.conclude_reason))
        self.n_calls += 1
        step = self.n_calls
        if self.phase == "research":
            self.research_steps += 1
        else:
            self.conclude_used += 1
        try:
            message = self.model.query(self.messages)
        except ContextFull as exc:
            self._overflow(step, exc)
        call, parsed = message["extra"]["call"], message["extra"]["parsed"]
        self.tokens += call["usage"]["total_tokens"]
        # A final answer is checked before its model call is recorded, so the record can say
        # whether this reply is the one that became answer.json.
        self._checked = (build_answer(parsed["answer"], self.concept, accepted_claim_ids(self.run_dir))
                         if parsed["kind"] == "answer" else (None, []))
        self.model_task_id = self._record_call(step, call, parsed, final_answer=self._checked[0] is not None)
        self.add_messages(message)
        return message

    def execute_actions(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        step = self.n_calls
        parsed = Parsed(**message["extra"]["parsed"])
        content = message.get("content") or ""
        if parsed.kind == "none":
            self._coverage(step, "unparsed", content, {"finish_reason": message["extra"]["call"]["finish_reason"]})
            return self._say("Nothing ran: your reply had no bash block. Reply with your reasoning and then "
                             "EXACTLY ONE fenced bash block, or give the final answer in one fenced json block.")
        if parsed.kind == "answer":
            answer, problems = self._checked
            if answer is not None:
                write_json(self.run_dir.answer, answer)
                self.answer = answer
                raise Submitted({"role": "exit", "content": "answer.json written",
                                 "extra": {"exit_status": "submitted", "submission": parsed.answer}})
            self._coverage(step, "invalid_final_answer", content, problems[:20])
            return self._say("The final answer is not valid and was not saved:\n- " + "\n- ".join(problems[:20])
                             + "\nFix it and reply with the corrected json block.")
        if self.phase == "conclude":
            self._coverage(step, "command_not_run", content, {"phase": "conclude"})
            return self._say("No more commands run now. Reply with the final answer in one fenced json block.")
        return self.add_messages(self._run_command(step, parsed))

    def _say(self, text: str) -> list[dict[str, Any]]:
        return self.add_messages({"role": "user", "content": f"{text}\n{self.budget_line()}",
                                  "extra": {"kind": "notice"}})

    def _run_command(self, step: int, parsed: Parsed) -> dict[str, Any]:
        command = parsed.command
        normal = normalise_command(command)
        self.repeats = self.repeats + 1 if normal == self.last_command else 1
        self.last_command = normal
        claims_before = self.broker.head()["claims"] if self.env.claim else 0
        started = utc_now()
        result = self.env.execute({"command": command}, step_id=step, broker=self.broker)
        claims = (self.broker.head()["claims"] - claims_before) if self.env.claim else 0
        name = f"step-{step:04d}.txt"
        (self.run_dir.out / name).write_bytes(result.output)
        shown = result.output[:self.cap].decode("utf-8", errors="replace")
        read, corpus_dir = files_read(command)
        self._record({
            "subtype": "agent_tool", "step_id": step, "parent_task_id": self.model_task_id,
            # files_read: corpus files named in the command (heuristic, parse.files_read), for PROV `uses`.
            "used": {"command": command, "parse": parsed.mode, "files_read": read, "corpus_dir_read": corpus_dir},
            "generated": {"output_sha256": sha256_hex(result.output), "output_file": f"out/{name}",
                          "output_bytes": len(result.output), "exit_code": result.exit_code,
                          "timed_out": result.timed_out, "truncated": len(result.output) > self.cap},
            "started_at": started, "status": "timeout" if result.timed_out else "finished",
            "custom_metadata": {"claim_step": claims > 0, "claims": claims,
                                "claim_in_command": "claim" in command.split() or "| claim" in normal,
                                "repeat": self.repeats, "sandbox": self.env.mode, "seconds": round(result.seconds, 3),
                                "cleanup": result.cleanup},
        })
        notes = []
        if parsed.notice:
            notes.append(parsed.notice)
        if len(result.output) > self.cap:
            notes.append(f"[Output cut at {self.cap:,} of {len(result.output):,} bytes. Full output: "
                         f"{(self.run_dir.out / name).resolve()} (read it with sed -n or rg).]")
        if result.timed_out:
            notes.append(f"[The command hit the {self.env.limits['timeout_s']} s time limit and was stopped.]")
        if self.repeats == 2:
            notes.append("[Notice: you ran this same command in the previous step; its output will not change. "
                         "Try a different approach.]")
        elif self.repeats >= 3:
            notes.append(f"[Notice: this is the same command {self.repeats} times in a row. You have {self._left()}. "
                         "Change your approach or conclude.]")
        notes.append(self.budget_line())
        text = (f"<returncode>{result.exit_code}</returncode>\n<output>\n{shown}</output>\n" + "\n".join(notes))
        return {"role": "user", "content": text,
                "extra": {"kind": "observation", "step_id": step, "output_file": f"out/{name}"}}

    def outcome(self, status: str) -> Outcome:
        return Outcome(status, self.research_steps, self.n_calls, self.tokens,
                       len(self.answer["rows"]) if self.answer else 0)


# --- one run ---------------------------------------------------------------------------------------

def finish_without_answer(agent: ResearchAgent, status: str) -> None:
    """No valid answer: record why and write an answer with no rows, so the run directory is complete."""
    agent._coverage(agent.n_calls, "no_final_answer", "", {"exit_status": status})
    write_json(agent.run_dir.answer, empty_answer(agent.concept, f"exit status {status}"))


def run_agent(agent: ResearchAgent) -> Outcome:
    """Run until the answer, the end of the budget or an error; always leaves answer.json behind."""
    try:
        result = agent.run(task="")
        status = result.get("exit_status", "")
    except Exception as exc:
        logger.exception("run failed")
        status = "error"
        try:
            agent._coverage(agent.n_calls, "run_error", "", {"error": f"{type(exc).__name__}: {exc}"[:500]})
        finally:
            finish_without_answer(agent, status)
        raise
    if agent.answer is None:
        finish_without_answer(agent, status or "no_answer")
    return agent.outcome(status)


def research_run(*, runs_root: Path, run_id: str, concept: dict[str, Any], corpus: Path, manifest: Path,
                 condition: str, temperature: float, seed: int, git_commit: str, agent_root_manifest_sha256: str,
                 sandbox_mode: str, model: OrchestratorModel | None = None, agent_root: Path | None = None,
                 base_url: str = DEFAULT_BASE_URL, budget: dict[str, Any] | None = None,
                 prompt_version: str = "v1", broker: str = "auto", extra_path: tuple[str, ...] = (),
                 conclude_replies: int = CONCLUDE_REPLIES) -> tuple[RunDir, Outcome, dict[str, Any]]:
    """Create runs/<run_id>/, start the broker, run the agent, write pairs.jsonl, close the broker.

    `broker` is "process" (BrokerProcess, POSIX), "inprocess" (InProcessBroker) or "auto" (the
    process where SEQPACKET and descriptor passing exist). Returns the run directory, the outcome
    and the broker's final head; the head is also printed, for the Slurm log.
    """
    from . import prompts
    from .broker_client import BrokerProcess, InProcessBroker
    from .pairs import write_pairs
    from .rundir import BUDGET

    prompt = prompts.load(prompt_version, condition)
    budget = dict(budget or BUDGET)
    abi = sandbox.landlock_abi()
    if sandbox_mode == "landlock" and abi is None:
        raise RuntimeError("Landlock is not available here; pass sandbox mode 'unsandboxed' explicitly")
    run = RunDir.create(
        Path(runs_root), run_id, concept, corpus_manifest=manifest, condition=condition, temperature=temperature,
        seed=seed, prompt_version=prompt_version, prompt_sha256=prompt.sha256, prompt_files=prompt.files,
        agent_root_manifest_sha256=agent_root_manifest_sha256, git_commit=git_commit, budget=budget,
        sandbox={"mode": sandbox_mode, "landlock_abi": abi if sandbox_mode == "landlock" else None,
                 "agent_root": str(agent_root) if agent_root else None},
        loop={"harness": HARNESS, "base_url": base_url, "conclude_replies": conclude_replies})
    use_process = broker == "process" or (broker == "auto" and POSIX_BROKER)
    channel: Any = (BrokerProcess.start(run.root, corpus, manifest) if use_process
                    else InProcessBroker(run.root, corpus, manifest))
    head: dict[str, Any] = {}
    try:
        model = model or OrchestratorModel(base_url=base_url, temperature=temperature, seed=seed)
        env = SandboxEnvironment(run, corpus=corpus, mode=sandbox_mode, claim=condition == "claim_on",
                                 agent_root=agent_root, extra_path=extra_path)
        agent = ResearchAgent(model, env, broker=channel, run=run, concept=concept, prompt=prompt, budget=budget,
                              conclude_replies=conclude_replies)
        outcome = run_agent(agent)
    finally:
        head = channel.close()
        print(f"run {run.run_id}: broker head={head.get('head')} records={head.get('records')} "
              f"claims={head.get('claims')}", flush=True)
    write_pairs(run)
    return run, outcome, head
