"""Chat about the runs (`POST /api/chat`): a pydantic-ai agent behind the Vercel AI SDK UI-message stream.

The frontend's assistant-ui thread sends AI SDK v5 requests; pydantic-ai's VercelAIAdapter turns
them into a run of this agent and streams the reply (text, tool calls and their results) back
in the AI SDK's UI-message stream protocol. The model is `sub-model-1` through LiteLLM
(gold/llm.py; the key is read when the model is made, per request), thinking off.

The agent's tools only read, through the same code as the API: list_runs, get_run, get_answer,
get_claims, walk_fact (with the verdicts score.json counted, when the run is scored; the chat never
calls the judge model), sparql (read-only), read_passage and get_results. Each returns plain JSON,
cut to a size a 32k-context model can take: lists to BUDGET characters with a last item saying how
many were left out, long texts to a few hundred characters, claims without the quote as submitted;
a tool error comes back as {"error": ...} so the model can correct its call. When the user is on a run page the frontend scopes the chat to that run
(`?run_id=` or `run_id` in the body).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent, RunContext

from gold import llm

from .files import BadRequest, Conflict, NotFound

if TYPE_CHECKING:
    from .app import Services

MAX_ITEMS = 100
MAX_TEXT = 4000
# Characters of JSON one tool result may take (~4-5k tokens): sub-model-1 has 32,768 tokens of context
# for the instructions, the whole conversation (every earlier tool result is sent again) and a
# 2,048-token reply, so a list longer than this is cut and says how many items it left out.
BUDGET = 16_000
SHORT = 200  # characters of a claim's s, p or o in a list

INSTRUCTIONS = """\
You help a research supervisor check the runs of a research agent on a corpus of NLP papers.
Each run answers one question under one condition: claim_on (the agent recorded every fact with
an exact quote while it researched) or claim_off (the baseline, which attached quotes to its
answer afterwards, in an attach step). Answers are rows of facts (s, p, o); each fact cites claim
ids, each claim an exact quote anchored in a corpus paper (file p12.md -> paper id p12).

Answer only from what the tools return; say so when they do not tell. Name the run, fact, claim
and paper ids you rely on, and quote passages exactly. Your tools only read: you cannot start,
change or delete anything; for that the user has the web app's buttons."""

ERRORS = (NotFound, Conflict, BadRequest, ValueError)


@dataclass
class ChatDeps:
    services: Services
    run_id: str | None = None


def _cut(text: Any, limit: int = MAX_TEXT) -> Any:
    if isinstance(text, str) and len(text) > limit:
        return text[:limit] + f" [... {len(text) - limit} more characters]"
    return text


def _error(exc: Exception) -> dict[str, str]:
    return {"error": str(exc)}


def _size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str))


def _fit(items: list[Any], budget: int = BUDGET) -> list[Any]:
    """As many items (at most MAX_ITEMS) as fit `budget` characters of JSON; a last item says how many
    were left out, so the model can narrow its call instead of getting a 400 for a full context."""
    out, used = [], 2
    for item in items[:MAX_ITEMS]:
        used += _size(item) + 1
        if used > budget:
            break
        out.append(item)
    left = len(items) - len(out)
    return out + ([{"more": left, "note": f"{left} more not shown; narrow the call (a filter, a run, LIMIT)"}]
                  if left else [])


def build_agent() -> Agent[ChatDeps, str]:
    agent: Agent[ChatDeps, str] = Agent(deps_type=ChatDeps, instructions=INSTRUCTIONS, name="runs-chat")

    @agent.instructions
    def scope(ctx: RunContext[ChatDeps]) -> str:
        if ctx.deps.run_id:
            return f"The user is looking at run {ctx.deps.run_id}: 'this run' means that run."
        return "The user is not looking at a particular run."

    @agent.tool
    def list_runs(ctx: RunContext[ChatDeps], qid: str | None = None, condition: str | None = None) -> Any:
        """Runs (by run id) with question id, condition, exit status, cost, claims and score; filter by
        question id (q01..q12: its runs on the current concept) and condition (claim_on or claim_off)."""
        runs = ctx.deps.services.runs.summaries(qid=qid, condition=condition)
        return _fit([r.model_dump(mode="json") for r in reversed(runs)])  # newest first

    @agent.tool
    def get_run(ctx: RunContext[ChatDeps], run_id: str) -> Any:
        """One run: its summary, settings (budget, sampling, prompt), concept and the check by `agent verify`."""
        try:
            detail = ctx.deps.services.runs.detail(run_id)
        except ERRORS as exc:
            return _error(exc)
        data = detail.model_dump(mode="json", exclude={"answer"})
        if data.get("verify"):
            data["verify"]["errors"] = data["verify"]["errors"][:20]
        return data

    @agent.tool
    def get_answer(ctx: RunContext[ChatDeps], run_id: str) -> Any:
        """The run's final answer: rows, each with facts (id, s, p, o, the claim ids behind it, origin)."""
        try:
            detail = ctx.deps.services.runs.detail(run_id)
        except ERRORS as exc:
            return _error(exc)
        return detail.answer.model_dump(mode="json") if detail.answer else {"error": f"{run_id} has no answer yet"}

    @agent.tool
    def get_claims(ctx: RunContext[ChatDeps], run_id: str, status: str | None = None) -> Any:
        """The run's claims (accepted with their exact quote and paper; rejected with the reason);
        status filters to accepted or rejected."""
        try:
            claims = ctx.deps.services.runs.claims(run_id)
        except ERRORS as exc:
            return _error(exc)
        rows = [c.model_dump(mode="json", exclude={"quote_submitted", "task_id"}) for c in claims
                if status in (None, c.status)]
        return _fit([{k: _cut(v, SHORT if k in ("s", "p", "o") else 600) for k, v in c.items()} for c in rows])

    @agent.tool
    def walk_fact(ctx: RunContext[ChatDeps], run_id: str, fact_id: str) -> Any:
        """Walk one answer fact back: its claims, the step (command) each came from, the passage around
        each quote, and whether each quote supports the fact (the judge's verdict scoring counted; none
        before the run is scored)."""
        try:
            walk = ctx.deps.services.runs.walk(run_id, fact_id)
        except ERRORS as exc:
            return _error(exc)
        data = walk.model_dump(mode="json")
        for item in data["claims"]:
            if item.get("passage"):
                item["passage"]["text"] = _cut(item["passage"]["text"], 1500)
            if item.get("step"):
                item["step"]["output_head"] = _cut(item["step"].get("output_head"), 800)
        return data

    @agent.tool
    def sparql(ctx: RunContext[ChatDeps], query: str, run_id: str | None = None) -> Any:
        """A read-only SPARQL query (SELECT, ASK, CONSTRUCT, DESCRIBE) over the PROV-O graphs of all runs
        (one named graph per run, urn:thesis-agent:run:<run_id>), or over one run's graph with run_id.
        Prefixes: prov <http://www.w3.org/ns/prov#>, oa <http://www.w3.org/ns/oa#>,
        ours <urn:thesis-agent:vocab#>; claims are ours:Claim with ours:claimId, ours:s/p/o."""
        try:
            result = ctx.deps.services.provenance.sparql(query, run_id)
        except ERRORS as exc:
            return _error(exc)
        data = result.model_dump(mode="json")
        data["rows"] = _fit([{k: _cut(v, 600) for k, v in row.items()} for row in data["rows"]])
        return data

    @agent.tool
    def read_passage(ctx: RunContext[ChatDeps], paper_id: str, start: int | None = None, end: int | None = None,
                     context: int = 600) -> Any:
        """Text of a corpus paper (id like p12): the window around raw offsets [start, end), or its beginning."""
        try:
            passage = ctx.deps.services.corpus.passage(paper_id, start, end, min(context, 2000))
        except ERRORS as exc:
            return _error(exc)
        return passage.model_dump(mode="json")

    @agent.tool
    def get_results(ctx: RunContext[ChatDeps]) -> Any:
        """The results report over all scored runs (per question and condition, the pre-registered test)."""
        try:
            report = ctx.deps.services.results()
        except ERRORS as exc:
            return _error(exc)
        if _size(report) <= BUDGET:
            return report
        # The tables are what make it large: per question x condition and paired rows, the inputs' hashes.
        kept = {k: v for k, v in report.items() if k not in ("per_question", "paired", "inputs", "runs")}
        kept["left_out"] = "per_question, paired, inputs and runs (too large for the chat; the Results page has them)"
        if _size(kept) > BUDGET:
            kept = {k: report.get(k) for k in ("provisional", "complete", "judge", "primary", "coverage")} | {
                "left_out": "everything but the primary test and its state (too large for the chat)"}
        return kept

    return agent


def chat_model(services: Services) -> Any:
    """The model of one chat request: the test's model, else sub-model-1 on LiteLLM (key read now)."""
    if services.chat_model is not None:
        return services.chat_model
    return llm.openai_model(services.settings.chat_model, url=services.settings.litellm_base_url)


def model_settings() -> Any:
    return llm.settings(temperature=0.2, seed=0, max_tokens=2048)
