"""Main loop (milestones-1-2.md rows 1.8, 1.9, 1.13, 1.15): mini-swe-agent 2.4.6 with our parser, sandbox and broker.

One step is one model reply. Per step the harness
1. masks old command outputs (row 1.15, below), calls `orch-model` through LiteLLM (thinking
   off, max_tokens 4096, the run's temperature and seed) and writes an `ai_model_invocation`
   record (decoding mode, reply limit, how many outputs were masked);
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
  as `guided_answer`. A whole answer may need more than 4,096 tokens, so a conclude reply gets
  up to `conclude_max_tokens` (16,384) of what the context leaves. If the server refuses the
  schema (a 4xx that is not context-full), the refused call is recorded with a `coverage` record
  `guided_decoding_rejected` and the reply is asked for again, decoded freely, as are later
  ones: the run does not fail on it. The conclude notice also shows the agent's draft;
- the agent keeps a draft answer in scratch/answer-draft.json. A run that ends without a valid
  answer takes the draft if it passes the same answer check (claim ids must be accepted claims),
  with notes saying so and a `coverage` record `answer_from_draft` holding the draft's sha256;
  the bytes read are kept as answer.draft.json in the run root, out of the sandbox's reach;
- outputs older than the last `mask_keep` (8) commands become one-line stubs naming their
  out/step-NNNN.txt file, claim replies kept, so prompts stay well under the 61,440 limit; after
  a call whose prompt was over 45,000 tokens only the last 4 stay. Masking is in place and for
  good, so the prompt prefix (vLLM's prefix cache, C2b) changes only where a new stub starts; the
  text first shown stays in the message's `extra.original_content`, so trajectory.json still
  holds every prompt. The reactive path stays: on a context-full 400 every output not yet a stub
  becomes one, then old replies are shortened, the third 400 ends the run.
LoopSettings holds these choices and goes into config.json (`loop`); prompt v1 runs with
LEGACY_V1, the loop as the M1-real runs had it (all of the above off, the old wording), and by
default with their budget (budget_for).

A run that ends without a valid answer or a usable draft still gets an answer.json with no rows
and the reason in `notes`, plus a `coverage` record (`no_final_answer`, with why the draft was not
taken), so every run directory is complete.

Subagents (row 2.12, agent/spawn.py; `spawn` off unless asked for): the same ResearchAgent runs
them, with hooks for another agent id, its record metadata and its result; the agent's commands
get a SPAWN_FD channel and, when they start a subagent, a longer time limit (SandboxEnvironment);
step ids come from one StepCounter per run, so they stay unique while subagents run. A masked
spawn result keeps one short line (agent id, status, claim ids), the same in both conditions.
"""
from __future__ import annotations

import json
import logging
import os
import re
import socket
import stat
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol

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
from .rundir import BUDGET, BUDGET_M1, COMMAND_LIMITS, DRAFT_COPY, ORCHESTRATOR, RunDir, utc_now  # noqa: E402

if TYPE_CHECKING:  # agent/spawn.py imports this module
    from .spawn import SpawnJob, SpawnService, SpawnSettings

HARNESS = f"mini-swe-agent {MSWEA_VERSION}"
AGENT_DIR = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "http://127.0.0.1:4000/v1"
CONCLUDE_REPLIES = 2
SYSTEM_DIRS = ("/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc", "/dev")
CONTEXT_FULL_MARKERS = ("contextwindowexceeded", "context_length_exceeded", "maximum context length",
                        "context length")
POSIX_BROKER = sys.platform != "win32" and hasattr(socket, "send_fds") and hasattr(socket, "SOCK_SEQPACKET")
DRAFT_MAX_BYTES = 1 << 20  # a larger draft is not read as an answer
CONTEXT_MARGIN = 1_024  # tokens kept free when a conclude reply's limit is fitted to the context
logger = logging.getLogger("agent.loop")

# Schema-constrained decoding: the extra_body entry that makes vLLM decode under a JSON Schema.
# disable_any_whitespace (a per-request field of vLLM's StructuredOutputsParams): the grammar allows
# no whitespace between JSON tokens. By default xgrammar allows any, and Qwen models then pretty-print
# (30-50 % more tokens for the same answer) or run away in whitespace until the reply limit cuts the
# answer; a 16,384-token conclude reply takes ~400 s at 41.6 tok/s already (STATE.md, A5).
GUIDED_DECODING: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "structured_outputs": lambda schema: {"structured_outputs": {"json": schema, "disable_any_whitespace": True}},
    "guided_json": lambda schema: {"guided_json": schema},  # older vLLM
}
DECODINGS = ("free", *GUIDED_DECODING)


@dataclass(frozen=True)
class LoopSettings:
    """The loop's choices beyond running commands (rows 1.13, 1.15); `config()` goes into config.json `loop`."""

    conclude_replies: int = CONCLUDE_REPLIES
    conclude_decoding: str = "structured_outputs"  # "free", or a GUIDED_DECODING key
    # max_tokens of a conclude reply, within what the context leaves (None: the orchestrator's 4,096).
    # A whole answer to a corpus-wide question (30+ rows) does not fit 4,096 tokens, and claim_on
    # facts carry claim ids, so a fixed cap would cut claim_on answers sooner than claim_off ones.
    conclude_max_tokens: int | None = 16_384
    mask_keep: int = 8  # command outputs kept whole; older ones become stubs (0: never)
    mask_keep_tight: int = 4  # ... after a call whose prompt had more than mask_tight_above tokens
    mask_tight_above: int = 45_000
    budget_warnings: tuple[int, ...] = (50, 75, 90)  # % of either budget; one notice each
    repeat_stop: int = 6  # identical commands in a row that end research (0: never)
    draft_file: str | None = "answer-draft.json"  # in scratch/; taken when the run ends without an answer
    # The M1-real loop's wording: a context-full stub without the output file, and no reply-limit
    # line in the problems of a cut answer.
    m1_notices: bool = False

    def __post_init__(self) -> None:
        if self.conclude_decoding not in DECODINGS:
            raise ValueError(f"conclude_decoding must be one of {DECODINGS}")
        if self.conclude_max_tokens is not None and self.conclude_max_tokens < 1:
            raise ValueError("conclude_max_tokens must be positive (or None)")
        if self.mask_keep and not 1 <= self.mask_keep_tight <= self.mask_keep:
            raise ValueError("mask_keep_tight must be between 1 and mask_keep")
        if self.draft_file is not None and Path(self.draft_file).name != self.draft_file:
            raise ValueError("draft_file is a file name in the scratch directory")

    def config(self) -> dict[str, Any]:
        masking = ({"keep": self.mask_keep, "keep_tight": self.mask_keep_tight,
                    "tight_above_prompt_tokens": self.mask_tight_above} if self.mask_keep else None)
        return {"conclude_replies": self.conclude_replies, "conclude_decoding": self.conclude_decoding,
                "conclude_max_tokens": self.conclude_max_tokens, "masking": masking,
                "budget_warnings": list(self.budget_warnings), "repeat_stop": self.repeat_stop,
                "draft_file": self.draft_file, "m1_notices": self.m1_notices}


# The loop as the M1-real runs had it: prompt v1 runs with it (and with BUDGET_M1, budget_for), so
# those runs can be reproduced: every prompt the model sees is built as it was then.
LEGACY_V1 = LoopSettings(conclude_decoding="free", conclude_max_tokens=None, mask_keep=0, budget_warnings=(),
                         repeat_stop=0, draft_file=None, m1_notices=True)


def settings_for(prompt_version: str) -> LoopSettings:
    return LEGACY_V1 if prompt_version == "v1" else LoopSettings()


def budget_for(prompt_version: str) -> dict[str, Any]:
    """The default run budget: the M1-real runs' for prompt v1, the provisional one (rundir.BUDGET) otherwise."""
    return dict(BUDGET_M1 if prompt_version == "v1" else BUDGET)


# What a stub keeps of a spawn result line (row 2.12; the client prints the result on one JSON
# line, keys sorted). A JSON string escapes its quotes, so a summary quoting these never matches.
SPAWN_RESULT = re.compile(r'"agent_id": ?"(sub-\d+)"')
SPAWN_STATUS = re.compile(r'"status": ?"([a-z_]+)"')
SPAWN_CLAIMS = re.compile(r'"claims": ?\[')
CLAIM_ID = re.compile(r'"claim_id": ?"(claim-\d+)"')


def kept_lines(text: str) -> list[str]:
    """The lines of an output that its stub keeps (row 1.15): claim replies, and spawn results short.

    A claim reply ({"ok": true, "claim_id": ...} or {"ok": false, "reason": ...}) is kept as it
    is. A spawn result (row 2.12) becomes {"agent_id", "status"} plus, in a claim_on run, the ids
    of the claims it lists: its summary goes in both conditions alike. (A claim_on result holds
    "claim_id", so the plain rule would keep its summary for the rest of the run in claim_on
    only: a difference between the conditions that is not the claim mechanism.)
    """
    kept = []
    for line in text.splitlines():
        sub = SPAWN_RESULT.search(line)
        if sub:
            status = SPAWN_STATUS.search(line)
            short: dict[str, Any] = {"agent_id": sub.group(1), "status": status.group(1) if status else None}
            if SPAWN_CLAIMS.search(line):
                short["claims"] = CLAIM_ID.findall(line)
            kept.append(json.dumps(short))
        elif '"claim_id"' in line or '"reason"' in line:
            kept.append(line)
    return kept


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
    def claim_channel(self, step_id: int, agent_id: str = "main", origin: str = "research",
                      source_agent_id: str | None = None, spawned_by_step: int | None = None) -> Any: ...
    def head(self) -> dict[str, Any]: ...
    def close(self, timeout: float = 60) -> dict[str, Any]: ...


class FailedCall(Exception):
    """A model call the proxy refused (HTTP 4xx, never retried), with what its failed-call record needs."""

    def __init__(self, detail: str, prompt_sha256: str, started_at: str, seconds: float) -> None:
        super().__init__(detail)
        self.detail = detail
        self.prompt_sha256 = prompt_sha256
        self.started_at = started_at
        self.seconds = seconds


class ContextFull(FailedCall):
    """The proxy refused the prompt as too long (HTTP 400). The agent concludes."""


class TimedOut(FailedCall):
    """A long call (a conclude reply: guided, or with a larger reply limit) ran past the proxy timeout.

    Sent again it would most likely time out again (a long reply on an orchestrator whose KV cache
    holds about one such request), each try costing 600 s and a prefill of the whole prompt, so it
    is not retried: the caller records it and goes on, as after a context-full 400.
    """


class GuidedRejected(FailedCall):
    """A call decoded under a schema was refused, and not for its length.

    vLLM's grammar backend may not take something in the schema, or the proxy may refuse the
    parameter (B9 proved only that LiteLLM passes structured_outputs through, with a regex). The
    caller asks for the reply again, decoded freely, instead of failing the run.
    """


GUIDED_REFUSALS = (litellm.exceptions.BadRequestError, litellm.exceptions.UnprocessableEntityError,
                   litellm.exceptions.UnsupportedParamsError)


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
    the entry to extra_body, next to the thinking switch) and parsed as a bare answer; a refusal
    of that call that is not context-full raises GuidedRejected. `max_tokens` may be given per
    call (a conclude reply); the call record says which limit applied. Such a long call (guided,
    or with a larger reply limit) is not retried after the proxy's timeout: it raises TimedOut.
    """

    # 400s and 422s are never retried (L8); everything mini aborts on stays aborted. SystemExit is
    # how SIGTERM at the job limit stops a run (cli.stop_on_sigterm, row 2.9); tenacity would retry
    # it otherwise. A long call (`long_call`) also aborts on a timeout (TimedOut).
    abort_exceptions = [*LitellmModel.abort_exceptions, litellm.exceptions.BadRequestError,
                        litellm.exceptions.UnprocessableEntityError, SystemExit]
    # Retries are mini's (tenacity, MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT) alone: the OpenAI client
    # under LiteLLM would otherwise retry timeouts and 408s twice more inside every attempt.
    client_retries = 0

    def __init__(self, *, base_url: str = DEFAULT_BASE_URL, temperature: float, seed: int,
                 alias: str = ORCHESTRATOR["alias"], max_tokens: int = ORCHESTRATOR["max_tokens"],
                 thinking: bool = ORCHESTRATOR["thinking"], timeout_s: float = 600,
                 api_key_env: str = "LITELLM_MASTER_KEY", name: str = ORCHESTRATOR["name"],
                 revision: str = ORCHESTRATOR["revision"], context_tokens: int = ORCHESTRATOR["context_tokens"]) -> None:
        # name, revision and context_tokens default to the orchestrator's; a subagent (row 2.12,
        # agent/spawn.py) passes a sub-model's from rundir.SUBAGENTS.
        super().__init__(model_name=f"openai/{alias}", cost_tracking="ignore_errors", model_kwargs={
            "api_base": base_url, "temperature": temperature, "seed": seed, "max_tokens": max_tokens,
            "timeout": timeout_s, "max_retries": self.client_retries,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": thinking}}})
        self.base_url = base_url
        self.api_key_env = api_key_env
        self.context_tokens = int(context_tokens)
        self.settings = {"model": alias, "model_name": name, "revision": revision,
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
        long_call = decoding != "free" or int(kwargs.get("max_tokens", 0)) > int(self.settings["max_tokens"])
        abort = [*self.abort_exceptions, litellm.exceptions.Timeout] if long_call else self.abort_exceptions
        try:
            for attempt in retry(logger=logger, abort_exceptions=abort):
                with attempt:
                    response = self._query(prepared, **kwargs)
        except litellm.exceptions.Timeout as exc:
            if not long_call:  # a research reply that timed out on every retry: as before, the run fails
                raise
            raise TimedOut(f"{type(exc).__name__}: {exc}"[:500], prompt_sha, started, time.monotonic() - t0) from exc
        except GUIDED_REFUSALS as exc:
            if is_context_full(exc):
                raise ContextFull(str(exc)[:500], prompt_sha, started, time.monotonic() - t0) from exc
            if decoding != "free":
                raise GuidedRejected(f"{type(exc).__name__}: {exc}"[:500], prompt_sha, started,
                                     time.monotonic() - t0) from exc
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
            "decoding": decoding, "max_tokens": int(kwargs.get("max_tokens", self.settings["max_tokens"])),
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

SPAWN_BIN = "spawn-bin"  # agent/spawn-bin/spawn (row 2.12)


class SandboxEnvironment:
    """Runs one agent command per step through agent/sandbox.py (mini's Environment protocol).

    Subagents (row 2.12, agent/spawn.py) use the same class: `agent_id` and `channel_meta`
    (source_agent_id, spawned_by_step) tag their claim channels, `scratch` is their own working
    directory and `cancel` stops their running command when they are cancelled. The parent's
    environment gets `spawn` (a SpawnService): each command then also gets a SPAWN_FD channel,
    and a command that starts a subagent gets the service's longer time limit, so the parent's
    120 s never kills a running subagent. Which commands do is known, not guessed from the
    command text: the wrapper gets the long limit, and the harness ends the command at the usual
    one unless its channel has accepted a spawn request by then (sandbox.run_command), so spawn
    called from a script counts as well. `last_timeout_s` is the limit that applied.
    """

    def __init__(self, run: RunDir, *, corpus: Path, mode: str, claim: bool, agent_root: Path | None = None,
                 limits: dict[str, int] | None = None, extra_path: tuple[str, ...] = (),
                 python: str = sys.executable, origin: str = "research", agent_id: str = "main",
                 channel_meta: dict[str, Any] | None = None, scratch: Path | None = None,
                 spawn: SpawnService | None = None, cancel: threading.Event | None = None) -> None:
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
        self.agent_id = agent_id
        self.channel_meta = dict(channel_meta or {})
        self.scratch = Path(scratch) if scratch else run.scratch
        self.spawn = spawn
        self.cancel = cancel
        self.last_spawned: list[str] = []  # subagents the last command started (row 2.12)
        self.last_timeout_s = int(self.limits["timeout_s"])  # the last command's time limit
        self.config = {"mode": mode, "claim": claim} | ({"spawn": True} if spawn else {})

    def path(self) -> str:
        # The conditions differ only in claim (2.4): bin/ (claim) iff claim_on, and spawn-bin/
        # (spawn, row 2.12) iff spawn is on, in either condition; subagents never get spawn.
        dirs = [str(AGENT_DIR / "bin")] if self.claim else []
        if self.spawn is not None:
            dirs.append(str(AGENT_DIR / SPAWN_BIN))
        if self.agent_root:
            dirs += [str(self.agent_root / "bin"), str(self.agent_root / "agent-venv" / "bin")]
        return ":".join([*dirs, *self.extra_path, "/usr/local/bin", "/usr/bin", "/bin"])

    def readonly(self) -> list[str]:
        paths = [*SYSTEM_DIRS, str(self.corpus), str(self.run.out.resolve()), *self.extra_path]
        if self.claim or self.spawn:
            paths.append(str(AGENT_DIR))  # bin/claim, spawn-bin/spawn and their clients
        if self.agent_root:
            paths.append(str(self.agent_root))
            venv_python = self.agent_root / "agent-venv" / "bin" / "python"
            if venv_python.exists():  # the uv-managed interpreter the venv links to (S5c)
                paths.append(str(Path(os.path.realpath(venv_python)).parent.parent))
        return [p for p in dict.fromkeys(paths) if os.path.exists(p)]

    def argv(self, command: str, timeout_s: int | None = None) -> list[str]:
        scratch = str(self.scratch.resolve())
        timeout = self.limits["timeout_s"] if timeout_s is None else timeout_s
        argv = [self.python, "-I", str(AGENT_DIR / "sandbox.py"), "--mode", self.mode, "--workdir", scratch,
                "--timeout", str(timeout), "--ulimit-v-kib", str(self.limits["ulimit_v_kib"])]
        if self.mode == "landlock":
            for path in self.readonly():
                argv += ["--readonly", path]
            argv += ["--writable", scratch, "--writefile", "/dev/null"]
        return [*argv, "--", command]

    def environment(self, claim_fd: int | None, spawn_fd: int | None = None) -> dict[str, str]:
        scratch = str(self.scratch.resolve())
        env = {"PATH": self.path(), "CORPUS": str(self.corpus), "HOME": scratch, "TMPDIR": scratch,
               "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
        if claim_fd is not None:
            env["CLAIM_FD"] = str(claim_fd)
        if spawn_fd is not None:
            env["SPAWN_FD"] = str(spawn_fd)
        return env

    def execute(self, action: dict[str, Any], cwd: str = "", *, step_id: int,
                broker: Broker | None = None, parent_task_id: str | None = None) -> sandbox.Result:
        """Run `action["command"]`; with a broker and claim on, the command gets CLAIM_FD for this step.

        With spawn on it also gets SPAWN_FD and the spawn limit, cut to the usual one unless it
        starts a subagent; when the command has ended, subagents it started and left running (no
        `wait`, or the time limit) are cancelled, and `last_spawned` names those it started.
        `parent_task_id` (the model call that asked for the command) is what their spawn records
        point to.
        """
        stopping.check()
        command = action["command"]
        short = int(self.limits["timeout_s"])
        timeout = int(self.spawn.settings.command_timeout_s) if self.spawn is not None else short
        sock = (broker.claim_channel(step_id, agent_id=self.agent_id, origin=self.origin, **self.channel_meta)
                if broker and self.claim else None)
        spawns = self.spawn.channel(step_id, parent_task_id) if self.spawn is not None else None
        socks = [s for s in (sock, spawns.sandbox_end if spawns else None) if s is not None]
        self.last_spawned = []

        def close_ours() -> None:  # the sandbox now holds the only copies
            for s in socks:
                s.close()
        try:
            env = self.environment(sock.fileno() if sock else None, spawns.sandbox_end.fileno() if spawns else None)
            return sandbox.run_command(self.argv(command, timeout), env=env, cwd=str(self.scratch.resolve()),
                                       timeout_s=timeout, pass_fds=tuple(s.fileno() for s in socks),
                                       before_wait=close_ours, cancel=self.cancel.is_set if self.cancel else None,
                                       short_timeout_s=short if timeout > short else None,
                                       extended=(lambda: bool(spawns.jobs)) if spawns else None)
        finally:
            close_ours()  # no-op after before_wait; closes them if Popen failed
            if spawns:
                self.last_spawned = spawns.finish()
            self.last_timeout_s = timeout if spawns and spawns.jobs else short

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
    # Row 2.12: subagents started and their tokens. steps, model_calls and tokens above are the
    # agent's own (its budget); the run's total is tokens + subagent_tokens (agent verify).
    subagents: int = 0
    subagent_tokens: int = 0


PLAN_SHARE = 0.75  # prompt v2: finish research by this share of the budget


class StepCounter:
    """Step ids of one run, shared by the agent and its subagents (row 2.12), so a step id names one step.

    A step is one model reply of one agent; with no subagents the ids are the agent's model
    calls 1, 2, 3, ... as before. While a spawn command runs, its subagents take the next ids, so
    out/step-NNNN.txt, (agent, step) and step alone all stay unique in the run.
    """

    def __init__(self, last: int = 0) -> None:
        self.last = last
        self._lock = threading.Lock()

    def __call__(self) -> int:
        with self._lock:
            self.last += 1
            return self.last


def claim_records(run: RunDir) -> list[dict[str, Any]]:
    """The run's claim records so far. Another agent may be claiming right now (row 2.12): a last
    line without its newline is still being written, and is left out."""
    return [json.loads(raw) for raw in run.claims.read_bytes().split(b"\n")[:-1]]


def claims_sent(run: RunDir, agent_id: str, step: int) -> int:
    """Claim records (accepted or not) of one agent's step: subagents claim while the parent's spawn command runs."""
    return sum(r["agent_id"] == agent_id and r["step_id"] == step for r in claim_records(run))


class ResearchAgent(DefaultAgent):
    """mini-swe-agent's DefaultAgent with records, sandboxed commands, budgets and a final answer.

    Row 2.12: a subagent (agent/spawn.py SubAgent) is this class with another `agent_id`,
    `record_meta` (spawned_by_step) on every record, `parent_task_id` on its first model call
    (the parent's spawn record), its own `trajectory` file and step ids from the run's
    `next_step` counter; it overrides the answer hooks (_check_answer, _submit, reply_shape).
    """

    reply_shape = '{"rows": [...], "notes": "..."}'  # the answer object, as the conclude notice names it
    answer_flag = "final_answer"  # custom_metadata key of the model call whose answer was taken

    def __init__(self, model: OrchestratorModel, env: SandboxEnvironment, *, broker: Broker, run: RunDir,
                 concept: dict[str, Any], prompt: Prompt, budget: dict[str, Any],
                 settings: LoopSettings | None = None, agent_id: str = "main", source_agent_id: str | None = None,
                 record_meta: dict[str, Any] | None = None, parent_task_id: str | None = None,
                 next_step: Callable[[], int] | None = None, trajectory: Path | None = None) -> None:
        super().__init__(model, env, system_template=prompt.system, instance_template=prompt.task,
                         step_limit=0, cost_limit=0.0, max_consecutive_format_errors=0,
                         output_path=trajectory or run.root / "trajectory.json")
        self.broker = broker
        self.run_dir = run
        self.concept = concept
        self.agent_id = agent_id
        self.source_agent_id = source_agent_id
        self.record_meta = dict(record_meta or {})
        self.pending_parent = parent_task_id  # the first model call's parent_task_id
        self.next_step = next_step or StepCounter()
        self.step_id = 0  # the current step id (DefaultAgent.step is a method)
        self.budget = {"steps": int(budget["steps"]), "tokens": int(budget["tokens"])}
        self.settings = settings or settings_for(prompt.version)  # as research_run resolves it
        self.cap = int(env.limits["output_cap_bytes"])
        s = self.settings
        self.extra_template_vars = {
            **self.budget, **task_vars(concept), "mask_keep": s.mask_keep, "repeat_stop": s.repeat_stop,
            "plan_steps": int(self.budget["steps"] * PLAN_SHARE), "plan_tokens": int(self.budget["tokens"] * PLAN_SHARE)}
        self.call_schema_sha256: str | None = None  # of the schema the current call is decoded under
        self.conclude_decoding = s.conclude_decoding  # "free" from the first refused guided call on
        self.research_steps = 0
        self.tokens = 0
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_call_messages = 0  # messages in the last answered call's prompt
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
        meta = {"origin": "research", **self.record_meta, **record.get("custom_metadata", {})}
        if self.pending_parent and record["subtype"] == "ai_model_invocation":  # a subagent's first call
            record = {"parent_task_id": self.pending_parent, **record}
            self.pending_parent = None
        return self.broker.record({"agent_id": self.agent_id, "source_agent_id": self.source_agent_id, **record,
                                   "custom_metadata": meta})

    def _record_call(self, step: int, call: dict[str, Any], parsed: dict[str, Any], answered: bool,
                     masked: int) -> str:
        # decoding: free, or the guided mode the reply was decoded under (with the schema's hash);
        # max_tokens: the reply limit of this call (larger for a conclude reply, LoopSettings).
        decoding = {k: call[k] for k in ("decoding", "schema_sha256", "max_tokens") if k in call}
        # final_answer: this reply's json block became answer.json (agent/prov.py links them).
        # A subagent's accepted result is marked under its own answer_flag ("result", row 2.12),
        # so final_answer keeps that one meaning for every reader of the records.
        # masked_observations: command outputs shown as stubs in this call's prompt (row 1.15).
        meta = {"phase": self.phase, "seconds": call["seconds"], "final_answer": False, "masked_observations": masked}
        meta[self.answer_flag] = answered
        reply = self._record({
            "subtype": "ai_model_invocation", "step_id": step,
            "used": {"prompt_sha256": call["prompt_sha256"], "messages": call["messages"], **self.model.settings,
                     **decoding},
            "generated": {k: call[k] for k in ("response_sha256", "reasoning_sha256", "finish_reason", "usage",
                                               "served_model")} | {"parse": parsed["mode"], "reply": parsed["kind"]},
            "started_at": call["started_at"], "ended_at": call["ended_at"], "custom_metadata": meta,
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
        if self.conclude_decoding == "free":
            ask = " Reply now with your reasoning and the final answer in EXACTLY ONE fenced json block; no further commands run."
        else:  # decoded under the reply schema: the reply can only be the answer object
            ask = f" Reply now with the final answer alone, as one JSON object {self.reply_shape}; no further commands run."
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
        """Replace an observation's output by one line naming the file that holds it; claim replies stay.

        The text the model saw before is kept in `extra.original_content` (the API never gets
        `extra`): trajectory.json is the only copy of the prompts, and with it every call's
        `prompt_sha256` can still be checked (stubs are always the oldest outputs, and the call
        record says how many there were). Spawn results stay as one short line (kept_lines).
        """
        extra = message["extra"]
        extra.setdefault("original_content", message["content"])
        kept = kept_lines(message["content"])
        file = (self.run_dir.root / extra["output_file"]).resolve()
        if why == "context_full" and self.settings.m1_notices:
            head = "[output removed: context full]"
        elif why == "context_full":
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
        """After a context overflow: keep the commands and the claim replies, drop the outputs.

        An output that is a stub already stays as it is (it holds no more than the claim replies).
        """
        for message in self.messages[2:]:
            extra = message.get("extra", {})
            if extra.get("kind") == "observation" and not extra.get("masked"):
                self._stub(message, "context_full")
            elif drop_reasoning and message.get("role") == "assistant":
                parsed = extra.get("parsed", {})
                extra.setdefault("original_content", message["content"])
                message["content"] = f"[reply shortened: context full] {parsed.get('command') or ''}".strip()

    def _record_failed(self, step: int, exc: FailedCall, error: str, masked: int, decoding: str,
                       max_tokens: int | None) -> str:
        """The record of a call the proxy refused; returns its task id."""
        used = {"prompt_sha256": exc.prompt_sha256, "messages": len(self.messages), **self.model.settings,
                "decoding": decoding}
        if decoding != "free":
            used["schema_sha256"] = self.call_schema_sha256
        if max_tokens:
            used["max_tokens"] = max_tokens
        return self._record({"subtype": "ai_model_invocation", "step_id": step, "used": used,
                             "generated": {"error": error}, "started_at": exc.started_at, "status": "failed",
                             "custom_metadata": {"phase": self.phase, "seconds": round(exc.seconds, 3),
                                                 "detail": exc.detail, "masked_observations": masked}})["task_id"]

    def _overflow(self, step: int, exc: ContextFull, masked: int, decoding: str, max_tokens: int | None) -> None:
        self._record_failed(step, exc, "context_window_exceeded", masked, decoding, max_tokens)
        self.overflows += 1
        if self.overflows > 2:
            raise LimitsExceeded(self._exit("context_full"))
        self._stub_observations(drop_reasoning=self.overflows == 2)
        raise InterruptAgentFlow(self._conclude(
            "context_full", "Context full: the conversation no longer fits the model's context, so earlier "
            "command outputs were removed (claim replies kept). Conclude now."))

    def _guided_rejected(self, step: int, exc: GuidedRejected, masked: int, decoding: str,
                         max_tokens: int | None) -> None:
        """The server refused the reply schema: record it, and decode conclude replies freely from now on.

        The refused call does not count as one of the `conclude_replies` (it got no reply). A
        free reply is parsed as before 1.13: a fenced or bare JSON object is still the answer.
        A `coverage` record (guided_decoding_rejected) says so, for the Slurm check.
        """
        self.model_task_id = self._record_failed(step, exc, "guided_decoding_rejected", masked, decoding, max_tokens)
        self._coverage(step, "guided_decoding_rejected", "", {"decoding": decoding, "now": "free", "error": exc.detail})
        self.conclude_decoding, self.conclude_used = "free", self.conclude_used - 1

    def _timed_out(self, step: int, exc: TimedOut, masked: int, decoding: str, max_tokens: int | None) -> None:
        """A conclude reply ran past the proxy timeout: recorded as a failed call (`timeout`) with a
        `coverage` record (model_timeout), and it counts as one of the conclude replies, so the run
        goes on to the next one or ends (taking the draft) instead of sending it again for hours."""
        self.model_task_id = self._record_failed(step, exc, "timeout", masked, decoding, max_tokens)
        self._coverage(step, "model_timeout", "", {"decoding": decoding, "max_tokens": max_tokens,
                                                   "seconds": round(exc.seconds, 3), "error": exc.detail})

    def conclude_schema(self) -> dict[str, Any]:
        """The schema a guided conclude reply is decoded under, built for this call: the reply object
        with cited claim ids limited to the claims accepted so far (answer.reply_schema)."""
        return reply_schema(self.concept, accepted_claim_ids(self.run_dir))

    def _reply_limit(self) -> int | None:
        """max_tokens for a conclude reply (LoopSettings.conclude_max_tokens), or None: the usual limit.

        At most `conclude_max_tokens` and no more than the context leaves, so the request is never
        refused as too long: the last prompt, the reply to it and what was added since (counted as
        3 characters a token, which is more than they are), less a margin. Never below the usual
        limit, which every prompt under 61,440 tokens (L8) has room for.
        """
        want = self.settings.conclude_max_tokens
        if self.phase != "conclude" or not want:
            return None
        usual = int(self.model.settings["max_tokens"])
        added = sum(len(m.get("content") or "") for m in self.messages[self.last_call_messages + 1:]) // 3
        room = (self.model.context_tokens - self.last_prompt_tokens - self.last_completion_tokens
                - added - CONTEXT_MARGIN)
        return max(usual, min(want, room))

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
        step = self.step_id = self.next_step()  # = n_calls unless subagents share the counter (row 2.12)
        if self.phase == "research":
            self.research_steps += 1
        else:
            self.conclude_used += 1
        masked = self._mask_observations()
        decoding = self.conclude_decoding if self.phase == "conclude" else "free"
        limit = self._reply_limit()
        schema = None if decoding == "free" else self.conclude_schema()
        self.call_schema_sha256 = sha256_hex(canonical_bytes(schema)) if schema is not None else None
        try:
            message = self.model.query(self.messages, decoding=decoding, schema=schema,
                                       **({"max_tokens": limit} if limit else {}))
        except ContextFull as exc:
            self._overflow(step, exc, masked, decoding, limit)
        except GuidedRejected as exc:
            self._guided_rejected(step, exc, masked, decoding, limit)
            return self.query()  # the same reply asked for again, decoded freely (never a guided call again)
        except TimedOut as exc:
            self._timed_out(step, exc, masked, decoding, limit)
            return self.query()  # the next conclude reply, or the end of the run (the draft)
        call, parsed = message["extra"]["call"], message["extra"]["parsed"]
        self.tokens += call["usage"]["total_tokens"]
        self.last_prompt_tokens = call["usage"]["prompt_tokens"]
        self.last_completion_tokens = call["usage"]["completion_tokens"]
        self.last_call_messages = call["messages"]
        # A final answer is checked before its model call is recorded, so the record can say
        # whether this reply is the one that became answer.json.
        self._checked = self._check_answer(parsed["answer"]) if parsed["kind"] == "answer" else (None, [])
        self.model_task_id = self._record_call(step, call, parsed, answered=self._checked[0] is not None,
                                               masked=masked)
        self.add_messages(message)
        return message

    def _check_answer(self, text: str) -> tuple[dict[str, Any] | None, list[str]]:
        """(answer, []) or (None, problems) for the agent's json block; a subagent checks its own result."""
        return build_answer(text, self.concept, accepted_claim_ids(self.run_dir))

    def _submit(self, answer: dict[str, Any]) -> None:
        """Keep the checked answer: answer.json for the agent; a subagent's result goes to its parent."""
        write_json(self.run_dir.answer, answer)
        self.answer, self.answer_from = answer, "final"

    def execute_actions(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        step = self.step_id
        parsed = Parsed(**message["extra"]["parsed"])
        content = message.get("content") or ""
        if parsed.kind == "none":
            self._coverage(step, "unparsed", content, {"finish_reason": message["extra"]["call"]["finish_reason"]})
            return self._say("Nothing ran: your reply had no bash block. Reply with your reasoning and then "
                             "EXACTLY ONE fenced bash block, or give the final answer in one fenced json block.")
        if parsed.kind == "answer":
            answer, problems = self._checked
            if answer is not None:
                self._submit(answer)
                raise Submitted({"role": "exit", "content": "answer.json written",
                                 "extra": {"exit_status": "submitted", "submission": parsed.answer}})
            call = message["extra"]["call"]
            if call["finish_reason"] == "length" and not self.settings.m1_notices:  # a long answer cut mid-JSON
                problems = [f"the reply was cut at the {call['max_tokens']:,}-token reply limit; "
                            "give a shorter answer (shorter strings, short notes)", *problems]
            self._coverage(step, "invalid_final_answer", content, problems[:20])
            return self._say("The final answer is not valid and was not saved:\n- " + "\n- ".join(problems[:20])
                             + "\nFix it and reply with the corrected json block.")
        if self.phase == "conclude":
            self._coverage(step, "command_not_run", content, {"phase": "conclude"})
            how = "in one fenced json block" if self.conclude_decoding == "free" else "as one JSON object"
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
        started = utc_now()
        result = self.env.execute({"command": command}, step_id=step, broker=self.broker,
                                  parent_task_id=self.model_task_id)
        timeout = self.env.last_timeout_s  # the spawn limit if it started a subagent (row 2.12), else 120 s
        # This agent's claims at this step only: subagents claim in the same run while a spawn command runs.
        claims = claims_sent(self.run_dir, self.agent_id, step) if self.env.claim else 0
        name = f"step-{step:04d}.txt"
        (self.run_dir.out / name).write_bytes(result.output)
        shown = result.output[:self.cap].decode("utf-8", errors="replace")
        read, corpus_dir = files_read(command)
        meta = {"claim_step": claims > 0, "claims": claims,
                "claim_in_command": "claim" in command.split() or "| claim" in normal,
                "repeat": self.repeats, "sandbox": self.env.mode, "seconds": round(result.seconds, 3),
                "cleanup": result.cleanup}
        if self.env.spawn is not None:  # row 2.12: the subagents this command started, under which time limit
            meta |= {"spawned": list(self.env.last_spawned), "timeout_s": timeout}
        if self.env.scratch != self.run_dir.scratch:  # a subagent's command ran in its own scratch directory
            meta["workdir"] = self.env.scratch.relative_to(self.run_dir.root).as_posix()
        self._record({
            "subtype": "agent_tool", "step_id": step, "parent_task_id": self.model_task_id,
            # files_read: corpus files named in the command (heuristic, parse.files_read), for PROV `uses`.
            "used": {"command": command, "parse": parsed.mode, "files_read": read, "corpus_dir_read": corpus_dir},
            "generated": {"output_sha256": sha256_hex(result.output), "output_file": f"out/{name}",
                          "output_bytes": len(result.output), "exit_code": result.exit_code,
                          "timed_out": result.timed_out, "truncated": len(result.output) > self.cap},
            "started_at": started, "status": "timeout" if result.timed_out else "finished",
            "custom_metadata": meta,
        })
        notes = []
        if parsed.notice:
            notes.append(parsed.notice)
        if len(result.output) > self.cap:
            notes.append(f"[Output cut at {self.cap:,} of {len(result.output):,} bytes. Full output: "
                         f"{(self.run_dir.out / name).resolve()} (read it with sed -n or rg).]")
        if result.timed_out:
            notes.append(f"[The command hit the {timeout} s time limit and was stopped.]")
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

    def check_draft(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None, bytes | None]:
        """(answer or None, about the draft, the bytes read) for scratch/<draft_file>.

        The answer is the draft completed by build_answer, if it passes the answer check (claim ids
        must be accepted claims) and can be written as canonical JSON. "About" is None when there
        is no draft, else its file, size, sha256 and the problems found. The draft is the agent's
        file, so nothing in it makes this raise.
        """
        if not self.settings.draft_file:
            return None, None, None
        file = f"scratch/{self.settings.draft_file}"
        data, why = read_draft(self.run_dir.scratch / self.settings.draft_file)
        if data is None:
            return None, (None if why == "missing" else {"file": file, "problems": [why]}), None
        if len(data) > DRAFT_MAX_BYTES:
            return None, {"file": file, "problems": [f"over {DRAFT_MAX_BYTES:,} bytes"]}, None
        about: dict[str, Any] = {"file": file, "bytes": len(data), "sha256": sha256_hex(data)}
        try:
            answer, problems = build_answer(data.decode("utf-8"), self.concept, accepted_claim_ids(self.run_dir))
            if answer is not None:
                canonical_bytes(answer)  # answer.json can be written
        except UnicodeDecodeError as exc:
            answer, problems = None, [f"not UTF-8: {exc}"]
        except (TypeError, ValueError, RecursionError) as exc:  # build_answer reports these itself; a last guard
            answer, problems = None, [f"the draft could not be checked: {type(exc).__name__}: {exc}"[:500]]
        return answer, (about if answer is not None else about | {"problems": problems[:20]}), data

    def outcome(self, status: str) -> Outcome:
        return Outcome(status, self.research_steps, self.n_calls, self.tokens,
                       len((self.answer or {}).get("rows", [])), self.answer_from)


# --- one run ---------------------------------------------------------------------------------------

def draft_notes(status: str, notes: str | None) -> str:
    prefix = f"harness: answer taken from the agent's draft file (exit status {status})"
    return f"{prefix}. {notes}" if notes else prefix


def finish_without_answer(agent: ResearchAgent, status: str) -> None:
    """No valid final answer: the agent's draft if it passes the answer check, else an answer with no rows.

    Either way a `coverage` record says which (answer_from_draft with the draft's sha256, or
    no_final_answer with why the draft was not taken), so the run directory is complete. The
    draft's bytes as read go to DRAFT_COPY in the run root (named in the record as `copy`),
    where the sandbox cannot change them; verify checks the copy against the recorded sha256.
    answer.json is written before the record that says where it came from.
    """
    answer, draft, data = agent.check_draft()
    if data is not None and draft is not None:
        (agent.run_dir.root / DRAFT_COPY).write_bytes(data)
        draft["copy"] = DRAFT_COPY
    if answer is not None and draft is not None:
        answer["notes"] = draft_notes(status, answer.get("notes"))
        write_json(agent.run_dir.answer, answer)
        agent.answer, agent.answer_from = answer, "draft"
        agent._coverage(agent.step_id, "answer_from_draft", "", {"exit_status": status, "draft": draft,
                                                                  "rows": len(answer["rows"])})
        return
    agent._coverage(agent.step_id, "no_final_answer", "", {"exit_status": status} | ({"draft": draft} if draft else {}))
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
            agent._coverage(agent.step_id, "run_error", "", {"error": f"{type(exc).__name__}: {exc}"[:500]})
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
                 settings: LoopSettings | None = None, spawn: SpawnSettings | None = None,
                 sub_model: Callable[[SpawnJob, dict[str, Any], int], OrchestratorModel] | None = None,
                 ) -> tuple[RunDir, Outcome, dict[str, Any]]:
    """Create runs/<run_id>/, start the broker, run the agent, write pairs.jsonl, close the broker.

    `broker` is "process" (BrokerProcess, POSIX), "inprocess" (InProcessBroker) or "auto" (the
    process where SEQPACKET and descriptor passing exist). `settings` and `budget` default to the
    prompt version's (settings_for, budget_for). `spawn` (agent/spawn.py SpawnSettings, row 2.12)
    is off by default and recorded in config.json either way; when on, the system prompt gets the
    spawn block and the agent's commands a SPAWN_FD channel served by a SpawnService, which runs
    the subagents (`sub_model(job, slot, seed)` builds their models; tests script them). Returns
    the run directory, the outcome and the broker's final head; the head is also printed, for
    the Slurm log.
    """
    from . import prompts
    from .broker_client import BrokerProcess, InProcessBroker
    from .pairs import write_pairs
    from .spawn import SpawnService, SpawnSettings

    spawn = spawn or SpawnSettings()
    prompt = prompts.load(prompt_version, condition, spawn=spawn.enabled)
    settings = settings or settings_for(prompt_version)
    budget = dict(budget or budget_for(prompt_version))
    abi = sandbox.landlock_abi()
    if sandbox_mode == "landlock" and abi is None:
        raise RuntimeError("Landlock is not available here; pass sandbox mode 'unsandboxed' explicitly")
    run = RunDir.create(
        Path(runs_root), run_id, concept, corpus_manifest=manifest, condition=condition, temperature=temperature,
        seed=seed, prompt_version=prompt_version, prompt_sha256=prompt.sha256, prompt_files=prompt.files,
        agent_root_manifest_sha256=agent_root_manifest_sha256, git_commit=git_commit, budget=budget,
        sandbox={"mode": sandbox_mode, "landlock_abi": abi if sandbox_mode == "landlock" else None,
                 "agent_root": str(agent_root) if agent_root else None},
        loop={"harness": HARNESS, "base_url": base_url, **settings.config()},
        spawn=spawn.config(condition, settings))
    use_process = broker == "process" or (broker == "auto" and POSIX_BROKER)
    channel: Any = (BrokerProcess.start(run.root, corpus, manifest) if use_process
                    else InProcessBroker(run.root, corpus, manifest))
    head: dict[str, Any] = {}
    service: SpawnService | None = None
    try:
        model = model or OrchestratorModel(base_url=base_url, temperature=temperature, seed=seed)
        steps = StepCounter()
        if spawn.enabled:
            service = SpawnService(run, channel, spawn, concept=concept, corpus=corpus, manifest=manifest,
                                   condition=condition, sandbox_mode=sandbox_mode, agent_root=agent_root,
                                   extra_path=extra_path, base_url=base_url, temperature=temperature, seed=seed,
                                   loop=settings, next_step=steps, model_factory=sub_model)
        env = SandboxEnvironment(run, corpus=corpus, mode=sandbox_mode, claim=condition == "claim_on",
                                 agent_root=agent_root, extra_path=extra_path, spawn=service)
        agent = ResearchAgent(model, env, broker=channel, run=run, concept=concept, prompt=prompt, budget=budget,
                              settings=settings, next_step=steps)
        agent.extra_template_vars |= spawn.template_vars()
        outcome = run_agent(agent)
    finally:
        if service is not None:
            service.close()  # subagents still running stop (cancelled) before the broker closes
        head = channel.close()
        print(f"run {run.run_id}: broker head={head.get('head')} records={head.get('records')} "
              f"claims={head.get('claims')}", flush=True)
    if service is not None:
        outcome.subagents, outcome.subagent_tokens = service.started, service.tokens
    write_pairs(run)
    return run, outcome, head
