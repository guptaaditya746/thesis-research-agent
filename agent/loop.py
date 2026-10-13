"""Main loop (milestones-1-2.md rows 1.8, 1.9, 1.13, 1.15): mini-swe-agent 2.4.6 with our parser, sandbox and broker.

One step is one model reply. Per step the harness
1. masks old command outputs (row 1.15, below), calls `orch-model` through LiteLLM (thinking
   off, max_tokens 4096, the run's temperature and seed) and writes an `ai_model_invocation`
   record (decoding mode, how many outputs were masked);
2. parses the reply's content (agent/parse.py; the reasoning field is never run). Unparseable
   output becomes a `coverage` record and a nudge, and nothing runs;
3. runs a command in the sandbox wrapper (agent/sandbox.py) with a fresh claim channel tagged
   with the step id, writes the full output to out/step-NNNN.txt and an `agent_tool` record whose
   parent is the model call, and shows the agent at most 8 KB plus a pointer to the file, a
   notice when it repeats a command (B4), a budget notice at 50, 75 and 90 % and what is left;
4. or takes a json block as the final answer, completes it (concept hash, kind, origin), checks
   it with validate_answer and the run's accepted claim ids, and writes answer.json.

Budgets (steps, tokens) are announced in the prompt and after every command. Research ends when
one runs out, when the proxy answers HTTP 400 ContextWindowExceededError (L8; never retried), or
after `repeat_stop` identical commands in a row (c3-on-3 ran one command 9 times); the agent is
then told to conclude and gets `conclude_replies` more replies in which no command runs.

What M1-real taught (tests/RESULTS.md, M1-real): the token sum counts the whole prompt again at
every step, so 400k lasted ~26 steps, and in both conclude replies of every run Qwen3.8 sent
another command (as a `<function=bash>` tool call) instead of the answer. So, with prompt v2:
- conclude replies are decoded under the reply's JSON schema (vLLM structured outputs passed
  through LiteLLM's extra_body, as B9 did for a regex): the reply *is* the answer object, parsed
  as `guided_answer`. The conclude notice also shows the agent's draft;
- the agent keeps a draft answer in scratch/answer-draft.json. A run that ends without a valid
  answer takes the draft if it passes the same answer check (claim ids must be accepted claims),
  with notes saying so and a `coverage` record `answer_from_draft` holding the draft's sha256;
- outputs older than the last `mask_keep` (8) commands become one-line stubs naming their
  out/step-NNNN.txt file, claim replies kept, so prompts stay well under the 61,440 limit; after
  a call whose prompt was over 45,000 tokens only the last 4 stay. Masking is in place and for
  good, so the prompt prefix (vLLM's prefix cache, C2b) changes only where a new stub starts. The
  reactive path stays: on a context-full 400 every output becomes a stub, then old replies are
  shortened, the third 400 ends the run.
LoopSettings holds these choices and goes into config.json (`loop`); prompt v1 runs with
LEGACY_V1, the loop as the M1-real runs had it (all of the above off).

A run that ends without a valid answer or a usable draft still gets an answer.json with no rows
and the reason in `notes`, plus a `coverage` record (`no_final_answer`, with why the draft was not
taken), so every run directory is complete.
"""
from __future__ import annotations

import logging
import os
import socket
import stat
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

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

from . import sandbox, stopping  # noqa: E402
from .canonical import canonical_bytes, sha256_hex, write_json  # noqa: E402
from .answer import accepted_claim_ids, build_answer, empty_answer, reply_schema  # noqa: E402
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
DRAFT_MAX_BYTES = 1 << 20  # a larger draft is not read as an answer
logger = logging.getLogger("agent.loop")

# Schema-constrained decoding: the extra_body entry that makes vLLM decode under a JSON Schema.
GUIDED_DECODING: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "structured_outputs": lambda schema: {"structured_outputs": {"json": schema}},  # vLLM >= 0.10 (B9)
    "guided_json": lambda schema: {"guided_json": schema},  # older vLLM
}
DECODINGS = ("free", *GUIDED_DECODING)


@dataclass(frozen=True)
class LoopSettings:
    """The loop's choices beyond running commands (rows 1.13, 1.15); `config()` goes into config.json `loop`."""

    conclude_replies: int = CONCLUDE_REPLIES
    conclude_decoding: str = "structured_outputs"  # "free", or a GUIDED_DECODING key
    mask_keep: int = 8  # command outputs kept whole; older ones become stubs (0: never)
    mask_keep_tight: int = 4  # ... after a call whose prompt had more than mask_tight_above tokens
    mask_tight_above: int = 45_000
    budget_warnings: tuple[int, ...] = (50, 75, 90)  # % of either budget; one notice each
    repeat_stop: int = 6  # identical commands in a row that end research (0: never)
    draft_file: str | None = "answer-draft.json"  # in scratch/; taken when the run ends without an answer

    def __post_init__(self) -> None:
        if self.conclude_decoding not in DECODINGS:
            raise ValueError(f"conclude_decoding must be one of {DECODINGS}")
        if self.mask_keep and not 1 <= self.mask_keep_tight <= self.mask_keep:
            raise ValueError("mask_keep_tight must be between 1 and mask_keep")
        if self.draft_file is not None and Path(self.draft_file).name != self.draft_file:
            raise ValueError("draft_file is a file name in the scratch directory")

    def config(self) -> dict[str, Any]:
        masking = ({"keep": self.mask_keep, "keep_tight": self.mask_keep_tight,
                    "tight_above_prompt_tokens": self.mask_tight_above} if self.mask_keep else None)
        return {"conclude_replies": self.conclude_replies, "conclude_decoding": self.conclude_decoding,
                "masking": masking, "budget_warnings": list(self.budget_warnings), "repeat_stop": self.repeat_stop,
                "draft_file": self.draft_file}


# The loop as the M1-real runs had it: prompt v1 runs with it, so those runs can be reproduced.
LEGACY_V1 = LoopSettings(conclude_decoding="free", mask_keep=0, budget_warnings=(), repeat_stop=0, draft_file=None)


def settings_for(prompt_version: str) -> LoopSettings:
    return LEGACY_V1 if prompt_version == "v1" else LoopSettings()


def read_draft(path: Path, limit: int = DRAFT_MAX_BYTES) -> tuple[bytes | None, str]:
    """At most `limit` + 1 bytes of the agent's draft, or (None, why not).

    The sandboxed agent made the file, so it is opened only if it is a regular file: never
    through a symlink (it could point anywhere the harness can read) and never a FIFO (it would
    block).
    """
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            return None, "not a regular file"
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                     | getattr(os, "O_BINARY", 0))
    except FileNotFoundError:
        return None, "missing"
    except OSError as exc:
        return None, f"cannot open: {exc.strerror or exc}"
    with os.fdopen(fd, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            return None, "not a regular file"
        return handle.read(limit + 1), ""


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
    With `decoding` other than "free", the reply is decoded under `schema` (GUIDED_DECODING adds
    the entry to extra_body, next to the thinking switch) and parsed as a bare answer.
    """

    # 400s are never retried (L8); everything mini aborts on stays aborted. SystemExit is how SIGTERM
    # at the job limit stops a run (cli.stop_on_sigterm, row 2.9); tenacity would retry it otherwise.
    abort_exceptions = [*LitellmModel.abort_exceptions, litellm.exceptions.BadRequestError, SystemExit]

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
        stopping.check()  # also on every retry: a SIGTERM swallowed inside the HTTP call stops here
        key = os.environ.get(self.api_key_env) or "none"
        return litellm.completion(model=self.config.model_name, messages=messages, api_key=key,
                                  **(self.config.model_kwargs | kwargs))

    def query(self, messages: list[dict[str, Any]], *, decoding: str = "free", schema: dict[str, Any] | None = None,
              **kwargs: Any) -> dict[str, Any]:
        if decoding != "free":
            if schema is None:
                raise ValueError(f"decoding {decoding!r} needs a schema")
            kwargs["extra_body"] = {**self.config.model_kwargs["extra_body"], **GUIDED_DECODING[decoding](schema)}
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
            "decoding": decoding,
        }
        if schema is not None and decoding != "free":
            call["schema_sha256"] = sha256_hex(canonical_bytes(schema))
        parsed = parse_reply(content, guided=decoding != "free")
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
                 python: str = sys.executable, origin: str = "research") -> None:
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
        self.origin = origin  # the claim channel's origin: research, or attach for the attach step (2.5)
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
        stopping.check()
        sock =broker.claim_channel(step_id, agent_id="main", origin=self.origin) if broker and self.claim else None
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
    exit_status: str  # submitted, budget, context_full, repeats, error
    steps: int
    model_calls: int
    tokens: int
    answer_rows: int
    answer_from: str = "none"  # final (the agent's answer), draft (its draft file) or none (no rows)


PLAN_SHARE = 0.75  # prompt v2: finish research by this share of the budget


class ResearchAgent(DefaultAgent):
    """mini-swe-agent's DefaultAgent with records, sandboxed commands, budgets and a final answer."""

    def __init__(self, model: OrchestratorModel, env: SandboxEnvironment, *, broker: Broker, run: RunDir,
                 concept: dict[str, Any], prompt: Prompt, budget: dict[str, Any],
                 settings: LoopSettings | None = None) -> None:
        super().__init__(model, env, system_template=prompt.system, instance_template=prompt.task,
                         step_limit=0, cost_limit=0.0, max_consecutive_format_errors=0,
                         output_path=run.root / "trajectory.json")
        self.broker = broker
        self.run_dir = run
        self.concept = concept
        self.budget = {"steps": int(budget["steps"]), "tokens": int(budget["tokens"])}
        self.settings = settings or LoopSettings()
        self.cap = int(env.limits["output_cap_bytes"])
        s = self.settings
        self.extra_template_vars = {
            **self.budget, **task_vars(concept), "mask_keep": s.mask_keep, "repeat_stop": s.repeat_stop,
            "plan_steps": int(self.budget["steps"] * PLAN_SHARE), "plan_tokens": int(self.budget["tokens"] * PLAN_SHARE)}
        self.reply_schema = reply_schema(concept)
        self.research_steps = 0
        self.tokens = 0
        self.last_prompt_tokens = 0
        self.phase = "research"
        self.conclude_reason = ""
        self.conclude_used = 0
        self.overflows = 0
        self.last_command = ""
        self.repeats = 0
        self.warned: set[int] = set()
        self.model_task_id: str | None = None
        self.answer: dict[str, Any] | None = None
        self.answer_from = "none"
        self._checked: tuple[dict[str, Any] | None, list[str]] = (None, [])

    # records

    def _record(self, record: dict[str, Any]) -> dict[str, Any]:
        # origin "research" marks the research loop; the baseline's attach step (2.5) writes "attach".
        meta = {"origin": "research", **record.get("custom_metadata", {})}
        return self.broker.record({"agent_id": "main", **record, "custom_metadata": meta})

    def _record_call(self, step: int, call: dict[str, Any], parsed: dict[str, Any], final_answer: bool,
                     masked: int) -> str:
        # decoding: free, or the guided mode the reply was decoded under (with the schema's hash).
        decoding = {k: call[k] for k in ("decoding", "schema_sha256") if k in call}
        reply = self._record({
            "subtype": "ai_model_invocation", "step_id": step,
            "used": {"prompt_sha256": call["prompt_sha256"], "messages": call["messages"], **self.model.settings,
                     **decoding},
            "generated": {k: call[k] for k in ("response_sha256", "reasoning_sha256", "finish_reason", "usage",
                                               "served_model")} | {"parse": parsed["mode"], "reply": parsed["kind"]},
            "started_at": call["started_at"], "ended_at": call["ended_at"],
            # final_answer: this reply's json block became answer.json (agent/prov.py links them).
            # masked_observations: command outputs shown as stubs in this call's prompt (row 1.15).
            "custom_metadata": {"phase": self.phase, "seconds": call["seconds"], "final_answer": final_answer,
                                "masked_observations": masked},
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

    def _budget_notes(self) -> list[str]:
        """The budget line, after a one-time notice when research passes a threshold of either budget.

        Several thresholds passed in one step (a large prompt) give one notice, for the highest.
        """
        notes = [self.budget_line()]
        if self.phase != "research":
            return notes
        used = 100 * max(self.research_steps / self.budget["steps"], self.tokens / self.budget["tokens"])
        passed = [p for p in self.settings.budget_warnings if used >= p and p not in self.warned]
        if passed:
            self.warned.update(passed)
            notes.insert(0, self._warning(max(passed)))
        return notes

    def _warning(self, percent: int) -> str:
        draft = f"./{self.settings.draft_file}" if self.settings.draft_file else ""
        if percent >= 90:
            todo = "Conclude now: reply with the final answer in one fenced json block."
        elif percent >= 75:
            todo = ("Stop opening new leads: finish the facts you are on"
                    + (f", update {draft}" if draft else "") + " and then give the final answer.")
        else:
            todo = f"Bring {draft} up to date with every fact found so far." if draft else ""
        text = f"[Budget notice: {percent}% of the budget is used ({self._left()})."
        return f"{text} {todo}]" if todo else f"{text}]"

    def _conclude(self, reason: str, text: str) -> dict[str, Any]:
        self.phase, self.conclude_reason, self.conclude_used = "conclude", reason, 0
        if self.settings.conclude_decoding == "free":
            ask = " Reply now with your reasoning and the final answer in EXACTLY ONE fenced json block; no further commands run."
        else:  # decoded under the reply schema: the reply can only be the answer object
            ask = (' Reply now with the final answer alone, as one JSON object {"rows": [...], "notes": "..."}; '
                   "no further commands run.")
        return {"role": "user", "content": text + ask + self._draft_shown(),
                "extra": {"kind": "conclude", "reason": reason}}

    def _draft_shown(self) -> str:
        """The agent's draft (first 8 KB), for the conclude notice: masked outputs may have held its facts."""
        if not self.settings.draft_file:
            return ""
        data, _ = read_draft(self.run_dir.scratch / self.settings.draft_file, self.cap)
        if not data:
            return ""
        cut = f", first {self.cap:,} bytes" if len(data) > self.cap else ""
        return f"\nYour draft ./{self.settings.draft_file}{cut}:\n" + data[:self.cap].decode("utf-8", errors="replace")

    def _stub(self, message: dict[str, Any], why: str) -> None:
        """Replace an observation's output by one line naming the file that holds it; claim replies stay."""
        extra = message["extra"]
        kept = [ln for ln in message["content"].splitlines() if '"claim_id"' in ln or '"reason"' in ln]
        file = (self.run_dir.root / extra["output_file"]).resolve()
        if why == "context_full":
            head = f"[output removed: context full] Full output: {file}"
        else:
            head = (f"[Output of step {extra['step_id']} removed to save context (exit {extra.get('exit_code')}, "
                    f"{extra.get('output_bytes', 0):,} bytes). Full output: {file}]")
        message["content"] = "\n".join([head, *kept])
        extra["masked"] = why

    def _mask_observations(self) -> int:
        """Row 1.15, before every call: outputs older than the last `mask_keep` commands become stubs.

        In place and for good, so the prompt prefix stays the same from call to call except where a
        new stub starts (one re-prefill of what follows it, C2b). After a call whose prompt had
        more than `mask_tight_above` tokens only `mask_keep_tight` stay. Returns how many outputs
        in the prompt are stubs, those of a context-full overflow included.
        """
        observations = [m for m in self.messages if m.get("extra", {}).get("kind") == "observation"]
        keep = self.settings.mask_keep
        if keep:
            if self.last_prompt_tokens > self.settings.mask_tight_above:
                keep = self.settings.mask_keep_tight
            for message in observations[:-keep]:
                if not message["extra"].get("masked"):
                    self._stub(message, "masked")
        return sum(bool(m["extra"].get("masked")) for m in observations)

    def _stub_observations(self, drop_reasoning: bool) -> None:
        """After a context overflow: keep the commands and the claim replies, drop the outputs."""
        for message in self.messages[2:]:
            extra = message.get("extra", {})
            if extra.get("kind") == "observation":
                self._stub(message, "context_full")
            elif drop_reasoning and message.get("role") == "assistant":
                parsed = extra.get("parsed", {})
                message["content"] = f"[reply shortened: context full] {parsed.get('command') or ''}".strip()

    def _overflow(self, step: int, exc: ContextFull, masked: int, decoding: str) -> None:
        self._record({"subtype": "ai_model_invocation", "step_id": step,
                      "used": {"prompt_sha256": exc.prompt_sha256, "messages": len(self.messages), **self.model.settings,
                               "decoding": decoding},
                      "generated": {"error": "context_window_exceeded"}, "started_at": exc.started_at,
                      "status": "failed", "custom_metadata": {"phase": self.phase, "seconds": round(exc.seconds, 3),
                                                              "detail": exc.detail, "masked_observations": masked}})
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
        if self.phase == "research":
            if self.research_steps >= self.budget["steps"] or self.tokens >= self.budget["tokens"]:
                raise InterruptAgentFlow(self._conclude("budget", f"Budget used up. {self.budget_line()}"))
            if self.settings.repeat_stop and self.repeats >= self.settings.repeat_stop:
                raise InterruptAgentFlow(self._conclude("repeats", f"Research ended: you ran the same command "
                                                                   f"{self.repeats} times in a row. {self.budget_line()}"))
        if self.phase == "conclude" and self.conclude_used >= self.settings.conclude_replies:
            raise LimitsExceeded(self._exit(self.conclude_reason))
        self.n_calls += 1
        step = self.n_calls
        if self.phase == "research":
            self.research_steps += 1
        else:
            self.conclude_used += 1
        masked = self._mask_observations()
        decoding = self.settings.conclude_decoding if self.phase == "conclude" else "free"
        try:
            message = self.model.query(self.messages, decoding=decoding,
                                       schema=None if decoding == "free" else self.reply_schema)
        except ContextFull as exc:
            self._overflow(step, exc, masked, decoding)
        call, parsed = message["extra"]["call"], message["extra"]["parsed"]
        self.tokens += call["usage"]["total_tokens"]
        self.last_prompt_tokens = call["usage"]["prompt_tokens"]
        # A final answer is checked before its model call is recorded, so the record can say
        # whether this reply is the one that became answer.json.
        self._checked = (build_answer(parsed["answer"], self.concept, accepted_claim_ids(self.run_dir))
                         if parsed["kind"] == "answer" else (None, []))
        self.model_task_id = self._record_call(step, call, parsed, final_answer=self._checked[0] is not None,
                                               masked=masked)
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
                self.answer, self.answer_from = answer, "final"
                raise Submitted({"role": "exit", "content": "answer.json written",
                                 "extra": {"exit_status": "submitted", "submission": parsed.answer}})
            if message["extra"]["call"]["finish_reason"] == "length":  # a long answer cut mid-JSON
                problems = [f"the reply was cut at the {self.model.settings['max_tokens']:,}-token reply limit; "
                            "give a shorter answer (shorter strings, short notes)", *problems]
            self._coverage(step, "invalid_final_answer", content, problems[:20])
            return self._say("The final answer is not valid and was not saved:\n- " + "\n- ".join(problems[:20])
                             + "\nFix it and reply with the corrected json block.")
        if self.phase == "conclude":
            self._coverage(step, "command_not_run", content, {"phase": "conclude"})
            how = "in one fenced json block" if self.settings.conclude_decoding == "free" else "as one JSON object"
            return self._say(f"No more commands run now. Reply with the final answer {how}.")
        return self.add_messages(self._run_command(step, parsed))

    def _say(self, text: str) -> list[dict[str, Any]]:
        notes = "\n".join(self._budget_notes())
        return self.add_messages({"role": "user", "content": f"{text}\n{notes}", "extra": {"kind": "notice"}})

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
        stop = self.settings.repeat_stop
        if self.repeats == 2:
            notes.append("[Notice: you ran this same command in the previous step; its output will not change. "
                         "Try a different approach.]")
        elif self.repeats >= 3:
            notes.append(f"[Notice: this is the same command {self.repeats} times in a row. You have {self._left()}. "
                         "Change your approach or conclude."
                         + (f" At {stop} in a row the research ends." if stop and self.repeats < stop else "") + "]")
        notes += self._budget_notes()
        text = (f"<returncode>{result.exit_code}</returncode>\n<output>\n{shown}</output>\n" + "\n".join(notes))
        return {"role": "user", "content": text,
                "extra": {"kind": "observation", "step_id": step, "output_file": f"out/{name}",
                          "exit_code": result.exit_code, "output_bytes": len(result.output)}}

    # the draft answer (rows 1.13)

    def check_draft(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """(answer, about the draft) if scratch/<draft_file> passes the answer check, else (None, about it).

        "About" is None when there is no draft, else its file, size, sha256 and the problems found.
        """
        if not self.settings.draft_file:
            return None, None
        file = f"scratch/{self.settings.draft_file}"
        data, why = read_draft(self.run_dir.scratch / self.settings.draft_file)
        if data is None:
            return None, (None if why == "missing" else {"file": file, "problems": [why]})
        if len(data) > DRAFT_MAX_BYTES:
            return None, {"file": file, "problems": [f"over {DRAFT_MAX_BYTES:,} bytes"]}
        about: dict[str, Any] = {"file": file, "bytes": len(data), "sha256": sha256_hex(data)}
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            return None, about | {"problems": [f"not UTF-8: {exc}"]}
        answer, problems = build_answer(text, self.concept, accepted_claim_ids(self.run_dir))
        return answer, (about if answer is not None else about | {"problems": problems[:20]})

    def outcome(self, status: str) -> Outcome:
        return Outcome(status, self.research_steps, self.n_calls, self.tokens,
                       len(self.answer["rows"]) if self.answer else 0, self.answer_from)


# --- one run ---------------------------------------------------------------------------------------

def draft_notes(status: str, notes: str | None) -> str:
    prefix = f"harness: answer taken from the agent's draft file (exit status {status})"
    return f"{prefix}. {notes}" if notes else prefix


def finish_without_answer(agent: ResearchAgent, status: str) -> None:
    """No valid final answer: the agent's draft if it passes the answer check, else an answer with no rows.

    Either way a `coverage` record says which (answer_from_draft with the draft's sha256, or
    no_final_answer with why the draft was not taken), so the run directory is complete.
    """
    answer, draft = agent.check_draft()
    if answer is not None and draft is not None:
        answer["notes"] = draft_notes(status, answer.get("notes"))
        agent._coverage(agent.n_calls, "answer_from_draft", "", {"exit_status": status, "draft": draft,
                                                                  "rows": len(answer["rows"])})
        write_json(agent.run_dir.answer, answer)
        agent.answer, agent.answer_from = answer, "draft"
        return
    agent._coverage(agent.n_calls, "no_final_answer", "", {"exit_status": status} | ({"draft": draft} if draft else {}))
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
                 prompt_version: str = "v2", broker: str = "auto", extra_path: tuple[str, ...] = (),
                 settings: LoopSettings | None = None) -> tuple[RunDir, Outcome, dict[str, Any]]:
    """Create runs/<run_id>/, start the broker, run the agent, write pairs.jsonl, close the broker.

    `broker` is "process" (BrokerProcess, POSIX), "inprocess" (InProcessBroker) or "auto" (the
    process where SEQPACKET and descriptor passing exist). `settings` defaults to the prompt
    version's (settings_for). Returns the run directory, the outcome and the broker's final head;
    the head is also printed, for the Slurm log.
    """
    from . import prompts
    from .broker_client import BrokerProcess, InProcessBroker
    from .pairs import write_pairs
    from .rundir import BUDGET

    prompt = prompts.load(prompt_version, condition)
    settings = settings or settings_for(prompt_version)
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
        loop={"harness": HARNESS, "base_url": base_url, **settings.config()})
    use_process = broker == "process" or (broker == "auto" and POSIX_BROKER)
    channel: Any = (BrokerProcess.start(run.root, corpus, manifest) if use_process
                    else InProcessBroker(run.root, corpus, manifest))
    head: dict[str, Any] = {}
    try:
        model = model or OrchestratorModel(base_url=base_url, temperature=temperature, seed=seed)
        env = SandboxEnvironment(run, corpus=corpus, mode=sandbox_mode, claim=condition == "claim_on",
                                 agent_root=agent_root, extra_path=extra_path)
        agent = ResearchAgent(model, env, broker=channel, run=run, concept=concept, prompt=prompt, budget=budget,
                              settings=settings)
        outcome = run_agent(agent)
    finally:
        head = channel.close()
        print(f"run {run.run_id}: broker head={head.get('head')} records={head.get('records')} "
              f"claims={head.get('claims')}", flush=True)
    write_pairs(run)
    return run, outcome, head
