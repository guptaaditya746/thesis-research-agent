"""Attach step of the baseline (milestones-1-2.md, row 2.5).

Runs after a claim_off run has written answer.json. For each answer fact, in answer order,
`orch-model` (same settings and seed as the run) gets a fresh conversation: the attach prompt
(agent/prompts/attach-<version>.txt, the same claim rules as prompt v1) and the fact with its row
and concept (attach-task-<version>.txt). It has the same sandbox and tools as the run, plus the
`claim` command: each command gets a claim channel opened with origin "attach", so every quote
passes the broker's normal anchor check and becomes a `claim` record. The fact ends with one json
block: {"claim_id": ...} naming an accepted claim made for this fact with the fact's own s, p and
o, or {"no_source": "..."}. Out of budget (its own, per fact, announced) or context, the fact gets
`conclude_replies` replies with no command, then "no source found".

Records: every model call, command and coverage record of the step has custom_metadata.origin
"attach" (the key the broker puts on attach claims; agent/prov.py groups all of them into one
attach activity) and the fact id. Step ids continue after the run's last step, so (agent, step)
stays unique and each attach claim is wasGeneratedBy the command it was sent from. The step
appends to the run's own hash chain: the broker is reopened on events.jsonl, which it verifies
first. A fact with no source also gets a `coverage` record (reason no_source_found).

Files: config.json gains an `attach` section (prompt hash, per-fact budget, first step) when the
step starts; answer.research.json keeps the answer as the run wrote it; answer.json then gets, for
every fact, origin "attach" and claims [the attached claim id] or [] ("no source found");
pairs.jsonl is rewritten; attach.json holds each fact's result and the step's own cost.

An attach step is run once. One that was cut (config has `attach`, no attach.json) is not resumed:
the batch runner (agent/batch.py) reruns the whole run in a fresh run directory.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import sandbox
from .canonical import canonical, canonical_bytes, file_sha256, sha256_hex, write_json
from .concept import validate_answer
from .loop import DEFAULT_BASE_URL, POSIX_BROKER, Broker, ContextFull, OrchestratorModel, SandboxEnvironment
from .parse import files_read, normalise_command, parse_reply
from .prompts import PROMPT_DIR
from .rundir import ATTACH_FILE, RunDir, utc_now

ATTACH_BUDGET = {"steps": 6, "tokens": 60_000, "announced": True}  # per fact; frozen with the run budget after 1.13
CONCLUDE_REPLIES = 1
ANSWER_BEFORE = "answer.research.json"
logger = logging.getLogger("agent.attach")


class AttachError(RuntimeError):
    pass


@dataclass(frozen=True)
class AttachPrompt:
    version: str
    system: str
    task: str
    files: dict[str, str]

    @property
    def system_name(self) -> str:
        return f"attach-{self.version}.txt"

    @property
    def sha256(self) -> str:
        return self.files[self.system_name]


def load_prompt(version: str = "v1") -> AttachPrompt:
    files, texts = {}, []
    for name in (f"attach-{version}.txt", f"attach-task-{version}.txt"):
        data = (PROMPT_DIR / name).read_bytes()
        files[name] = sha256_hex(data)
        texts.append(data.decode("utf-8"))
    return AttachPrompt(version, texts[0], texts[1], files)


def fill(template: str, values: dict[str, Any]) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def _same(a: Any, b: Any) -> bool:
    """s/p/o equality as the agent can type it: 2 and "2" match, whitespace at the ends does not count."""
    return a == b or str(a).strip() == str(b).strip()


@dataclass
class FactResult:
    row_id: str
    fact_id: str
    status: str  # attached | no_source
    claim_id: str | None
    reason: str  # the model's no_source text, or why the harness gave up (budget, context_full)
    first_step: int
    last_step: int
    model_calls: int = 0
    commands: int = 0
    tokens: int = 0
    claims_accepted: int = 0
    claims_rejected: int = 0
    steps: list[int] = field(default_factory=list)


class AttachStep:
    """The attach step over one claim_off run, against an open broker."""

    def __init__(self, run: RunDir, model: OrchestratorModel, env: SandboxEnvironment, broker: Broker, *,
                 prompt: AttachPrompt, budget: dict[str, Any], conclude_replies: int, first_step: int,
                 config_sha256: str) -> None:
        self.run = run
        self.model = model
        self.env = env
        self.broker = broker
        self.prompt = prompt
        self.budget = {"steps": int(budget["steps"]), "tokens": int(budget["tokens"])}
        self.conclude_replies = conclude_replies
        self.step = first_step - 1
        self.config_sha256 = config_sha256
        self.cap = int(env.limits["output_cap_bytes"])

    # records

    def _record(self, record: dict[str, Any], fact_id: str, phase: str) -> dict[str, Any]:
        meta = {"origin": "attach", "fact_id": fact_id, "phase": phase, **record.get("custom_metadata", {})}
        return self.broker.record({"agent_id": "main", **record, "custom_metadata": meta})

    def _coverage(self, step: int, parent: str | None, fact_id: str, phase: str, reason: str, raw: str,
                  detail: Any = None) -> None:
        generated: dict[str, Any] = {"reason": reason}
        if detail is not None:
            generated["detail"] = detail
        self._record({"subtype": "coverage", "step_id": step, "parent_task_id": parent,
                      "used": {"raw_output_sha256": sha256_hex(raw.encode("utf-8"))}, "generated": generated,
                      "status": "not_run"}, fact_id, phase)

    def _attach_claims(self, steps: set[int]) -> dict[str, dict[str, Any]]:
        """Accepted attach claims sent at `steps`, by claim id."""
        out = {}
        for raw in self.run.claims.read_bytes().splitlines():
            rec = json.loads(raw)
            if (rec["status"] == "accepted" and rec["step_id"] in steps
                    and rec["custom_metadata"].get("origin") == "attach"):
                out[rec["generated"]["claim_id"]] = rec
        return out

    # one fact

    def fact(self, concept: dict[str, Any], row: dict[str, Any], fact: dict[str, Any], n: int, count: int) -> FactResult:
        spo = {k: fact[k] for k in ("s", "p", "o")}
        row_shown = {k: v for k, v in row.items() if k != "facts"} | {
            "facts": [{k: f[k] for k in ("id", "s", "p", "o")} for f in row["facts"]]}
        task = fill(self.prompt.task, {
            "concept_json": json.dumps(concept, ensure_ascii=False, indent=2), "row_id": row["id"],
            "row_json": json.dumps(row_shown, ensure_ascii=False), "fact_id": fact["id"], "fact_n": n,
            "fact_count": count, "spo_json": json.dumps(spo, ensure_ascii=False)})
        system = fill(self.prompt.system, self.budget)
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}, {"role": "user", "content": task}]
        result = FactResult(row["id"], fact["id"], "no_source", None, "", self.step + 1, self.step + 1)
        used_steps, tokens, phase, conclude_used = 0, 0, "attach", 0
        last_command, repeats = "", 0

        def budget_line() -> str:
            return (f"[Budget for this fact: {used_steps} of {self.budget['steps']} steps and {tokens:,} of "
                    f"{self.budget['tokens']:,} tokens used.]")

        def say(text: str) -> None:
            messages.append({"role": "user", "content": f"{text}\n{budget_line()}"})

        while True:
            if phase == "attach" and (used_steps >= self.budget["steps"] or tokens >= self.budget["tokens"]):
                phase = "conclude"
                result.reason = "budget"
                if self.conclude_replies:
                    say("Budget for this fact used up. Reply now with your reasoning and the result in EXACTLY ONE "
                        "fenced json block; no further commands run.")
            if phase == "conclude" and conclude_used >= self.conclude_replies:
                break
            self.step += 1
            step = self.step
            result.steps.append(step)
            if phase == "attach":
                used_steps += 1
            else:
                conclude_used += 1
            try:
                message = self.model.query(messages)
            except ContextFull as exc:
                self._record({"subtype": "ai_model_invocation", "step_id": step,
                              "used": {"prompt_sha256": exc.prompt_sha256, "messages": len(messages),
                                       **self.model.settings},
                              "generated": {"error": "context_window_exceeded"}, "started_at": exc.started_at,
                              "status": "failed", "custom_metadata": {"seconds": round(exc.seconds, 3),
                                                                      "detail": exc.detail}}, fact["id"], phase)
                result.model_calls += 1
                result.reason = "context_full"
                break
            call = message["extra"]["call"]
            content = message.get("content") or ""
            tokens += call["usage"]["total_tokens"]
            result.tokens += call["usage"]["total_tokens"]
            result.model_calls += 1
            parsed = parse_reply(content)
            call_task = self._record({
                "subtype": "ai_model_invocation", "step_id": step,
                "used": {"prompt_sha256": call["prompt_sha256"], "messages": call["messages"], **self.model.settings},
                "generated": {k: call[k] for k in ("response_sha256", "reasoning_sha256", "finish_reason", "usage",
                                                   "served_model")} | {"parse": parsed.mode, "reply": parsed.kind},
                "started_at": call["started_at"], "ended_at": call["ended_at"],
                "custom_metadata": {"seconds": call["seconds"], "attach_config_sha256": self.config_sha256},
            }, fact["id"], phase)["task_id"]
            messages.append({"role": "assistant", "content": content})
            if parsed.kind == "answer":
                problem = self._take_result(parsed.answer, spo, set(result.steps), result)
                if problem is None:
                    break
                self._coverage(step, call_task, fact["id"], phase, "invalid_attach_result", content, problem)
                say(f"Not accepted: {problem}")
                continue
            if parsed.kind == "none":
                self._coverage(step, call_task, fact["id"], phase, "unparsed", content,
                               {"finish_reason": call["finish_reason"]})
                say("Nothing ran: your reply had no bash block. Reply with your reasoning and then EXACTLY ONE "
                    "fenced bash block, or give the result in one fenced json block.")
                continue
            if phase == "conclude":
                self._coverage(step, call_task, fact["id"], phase, "command_not_run", content, {"phase": "conclude"})
                say("No more commands run now. Reply with the result in one fenced json block.")
                continue
            normal = normalise_command(parsed.command)
            repeats = repeats + 1 if normal == last_command else 1
            last_command = normal
            text, accepted, rejected = self._command(step, call_task, fact["id"], phase, parsed, repeats)
            result.commands += 1
            result.claims_accepted += accepted
            result.claims_rejected += rejected
            messages.append({"role": "user", "content": f"{text}\n{budget_line()}"})
        result.last_step = self.step
        if result.status == "no_source":
            self._coverage(self.step, None, fact["id"], phase, "no_source_found", "",
                           {"row_id": row["id"], "reason": result.reason or "no reason given"})
        return result

    def _take_result(self, text: str, spo: dict[str, Any], steps: set[int], result: FactResult) -> str | None:
        """Accept the fact's result block, or return what is wrong with it."""
        try:
            given = json.loads(text)
        except ValueError as exc:
            return f"the json block is not valid JSON: {exc}"
        if not isinstance(given, dict) or len(given) != 1 or not ({"claim_id", "no_source"} & set(given)):
            return 'the json block must be {"claim_id": "claim-..."} or {"no_source": "..."}'
        if "no_source" in given:
            result.status, result.claim_id = "no_source", None
            result.reason = str(given["no_source"]).strip() or "no reason given"
            return None
        claim_id = given["claim_id"]
        claims = self._attach_claims(steps)
        if claim_id not in claims:
            return (f"{claim_id} is not a claim accepted for this fact; accepted for this fact: "
                    f"{sorted(claims) or 'none'}")
        meta = claims[claim_id]["custom_metadata"]
        if not all(_same(meta[k], spo[k]) for k in spo):
            return (f"{claim_id} records s/p/o {canonical({k: meta[k] for k in spo})}, not the fact's "
                    f"{canonical(spo)}; claim it again with exactly the fact's s, p and o")
        result.status, result.claim_id, result.reason = "attached", claim_id, ""
        return None

    def _command(self, step: int, parent: str, fact_id: str, phase: str, parsed: Any,
                 repeats: int) -> tuple[str, int, int]:
        command = parsed.command
        before = self._claim_counts()
        started = utc_now()
        result = self.env.execute({"command": command}, step_id=step, broker=self.broker)
        after = self._claim_counts()
        accepted, rejected = after[0] - before[0], after[1] - before[1]
        name = f"step-{step:04d}.txt"
        (self.run.out / name).write_bytes(result.output)
        read, corpus_dir = files_read(command)
        self._record({
            "subtype": "agent_tool", "step_id": step, "parent_task_id": parent,
            "used": {"command": command, "parse": parsed.mode, "files_read": read, "corpus_dir_read": corpus_dir},
            "generated": {"output_sha256": sha256_hex(result.output), "output_file": f"out/{name}",
                          "output_bytes": len(result.output), "exit_code": result.exit_code,
                          "timed_out": result.timed_out, "truncated": len(result.output) > self.cap},
            "started_at": started, "status": "timeout" if result.timed_out else "finished",
            "custom_metadata": {"claim_step": accepted + rejected > 0, "claims": accepted + rejected,
                                "repeat": repeats, "sandbox": self.env.mode, "seconds": round(result.seconds, 3),
                                "cleanup": result.cleanup},
        }, fact_id, phase)
        notes = [parsed.notice] if parsed.notice else []
        if len(result.output) > self.cap:
            notes.append(f"[Output cut at {self.cap:,} of {len(result.output):,} bytes. Full output: "
                         f"{(self.run.out / name).resolve()} (read it with sed -n or rg).]")
        if result.timed_out:
            notes.append(f"[The command hit the {self.env.limits['timeout_s']} s time limit and was stopped.]")
        if repeats == 2:
            notes.append("[Notice: you ran this same command in the previous step; its output will not change. "
                         "Try a different approach.]")
        elif repeats >= 3:
            notes.append(f"[Notice: this is the same command {repeats} times in a row. Change your approach or "
                         "give the result.]")
        shown = result.output[:self.cap].decode("utf-8", errors="replace")
        text = f"<returncode>{result.exit_code}</returncode>\n<output>\n{shown}</output>\n" + "\n".join(notes)
        return text.rstrip("\n"), accepted, rejected

    def _claim_counts(self) -> tuple[int, int]:
        lines = self.run.claims.read_bytes().splitlines()
        accepted = sum(json.loads(raw)["status"] == "accepted" for raw in lines)
        return accepted, len(lines) - accepted


# --- the whole step ---------------------------------------------------------------------------------

def attach_state(run: RunDir) -> str:
    """not_applicable (claim_on), pending (no attach yet), cut (started, not finished) or done."""
    config = run.load_config()
    if config["condition"] != "claim_off":
        return "not_applicable"
    if (run.root / ATTACH_FILE).is_file():
        return "done"
    return "cut" if "attach" in config else "pending"


def _last_step(run: RunDir) -> int:
    return max((json.loads(raw)["step_id"] for raw in run.events.read_bytes().splitlines()), default=0)


def attach_run(run_dir: Path, corpus: Path, manifest: Path, *, model: OrchestratorModel | None = None,
               base_url: str | None = None, sandbox_mode: str | None = None, agent_root: Path | None = None,
               budget: dict[str, Any] | None = None, broker: str = "auto", extra_path: tuple[str, ...] = (),
               prompt_version: str = "v1", conclude_replies: int = CONCLUDE_REPLIES) -> dict[str, Any]:
    """Run the attach step on a finished claim_off run. Returns attach.json's content."""
    from .broker_client import BrokerProcess, InProcessBroker
    from .pairs import write_pairs

    run = RunDir(Path(run_dir))
    state = attach_state(run)
    if state == "not_applicable":
        raise AttachError(f"{run.root} is a claim_on run; the attach step is for the baseline (claim_off)")
    if state != "pending":
        raise AttachError(f"{run.root}: attach step already {'done' if state == 'done' else 'started and cut'}; "
                          "a cut attach step is rerun with the whole run, in a fresh run directory")
    if not run.answer.is_file():
        raise AttachError(f"{run.root} has no answer.json; the attach step runs after the run's answer")
    config = run.load_config()
    concept = run.load_concept()
    answer = json.loads(run.answer.read_bytes())
    sandbox_mode = sandbox_mode or config.get("sandbox", {}).get("mode", "landlock")
    if sandbox_mode == "landlock" and sandbox.landlock_abi() is None:
        raise AttachError("Landlock is not available here; pass sandbox mode 'unsandboxed' explicitly")
    if agent_root is None and config.get("sandbox", {}).get("agent_root"):
        agent_root = Path(config["sandbox"]["agent_root"])
    base_url = base_url or config.get("loop", {}).get("base_url", DEFAULT_BASE_URL)
    prompt = load_prompt(prompt_version)
    budget = dict(budget or ATTACH_BUDGET)
    first_step = _last_step(run) + 1
    section = {"prompt": {"version": prompt_version, "sha256": prompt.sha256, "files": prompt.files},
               "budget_per_fact": {"steps": int(budget["steps"]), "tokens": int(budget["tokens"]),
                                   "announced": bool(budget.get("announced", True))},
               "conclude_replies": conclude_replies, "first_step": first_step, "started_at": utc_now(),
               "base_url": base_url, "sandbox": sandbox_mode}
    from . import schema
    problems = schema.check("config", config | {"attach": section})
    if problems:
        raise AttachError(f"invalid attach config: {problems}")
    before_sha = file_sha256(run.answer)
    (run.root / ANSWER_BEFORE).write_bytes(run.answer.read_bytes())
    write_json(run.config, config | {"attach": section})
    config_sha = sha256_hex(canonical_bytes(section))

    use_process = broker == "process" or (broker == "auto" and POSIX_BROKER)
    channel: Any = (BrokerProcess.start(run.root, corpus, manifest) if use_process
                    else InProcessBroker(run.root, corpus, manifest))
    results: list[FactResult] = []
    head: dict[str, Any] = {}
    try:
        temperature, seed = config["sampling"]["temperature"], config["sampling"]["seed"]
        model = model or OrchestratorModel(base_url=base_url, temperature=temperature, seed=seed)
        env = SandboxEnvironment(run, corpus=corpus, mode=sandbox_mode, claim=True, agent_root=agent_root,
                                 extra_path=extra_path, origin="attach")
        step = AttachStep(run, model, env, channel, prompt=prompt, budget=budget, conclude_replies=conclude_replies,
                          first_step=first_step, config_sha256=config_sha)
        facts = [(row, fact) for row in answer["rows"] for fact in row["facts"]]
        for n, (row, fact) in enumerate(facts, 1):
            results.append(step.fact(concept, row, fact, n, len(facts)))
    finally:
        head = channel.close()
        print(f"attach {run.run_id}: broker head={head.get('head')} records={head.get('records')} "
              f"claims={head.get('claims')}", flush=True)

    by_fact = {r.fact_id: r for r in results}
    for row in answer["rows"]:
        for fact in row["facts"]:
            got = by_fact[fact["id"]]
            fact["claims"] = [got.claim_id] if got.claim_id else []
            fact["origin"] = "attach"
    problems = validate_answer(answer, concept)
    if problems:
        raise AttachError(f"attached answer does not validate: {problems}")
    answer_sha = write_json(run.answer, answer)
    write_pairs(run)
    from .verify import cost as cost_of, is_attach
    records = [json.loads(raw) for raw in run.events.read_bytes().splitlines()]
    cost = cost_of([r for r in records if is_attach(r)])
    summary = {
        "schema_version": 1, "run_id": run.run_id, "config_sha256": config_sha, "prompt": section["prompt"],
        "budget_per_fact": section["budget_per_fact"], "first_step": first_step,
        "last_step": max([r.last_step for r in results], default=first_step - 1),
        "started_at": section["started_at"], "ended_at": utc_now(),
        "facts": [asdict(r) for r in results], "attached": sum(r.status == "attached" for r in results),
        "no_source": sum(r.status == "no_source" for r in results),
        "cost": {k: cost[k] for k in ("model_calls", "commands", "claims_accepted", "claims_rejected", "tokens",
                                      "prompt_tokens", "completion_tokens", "seconds")},
        "answer_research_sha256": before_sha, "answer_sha256": answer_sha, "chain_head": head.get("head"),
    }
    write_json(run.root / ATTACH_FILE, summary)
    return summary
