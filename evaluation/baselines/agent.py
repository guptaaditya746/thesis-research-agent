"""The agent baseline: our research agent with the question only, no protocol.

1. The corpus (SystemCorpus: manifest.json and papers/ only) is written in the agent's layout:
   `<id>.md` files and a manifest in its format (evidence.agentic.runner.write_agent_corpus).
2. The agent researches a concept brief made from the question alone (`question_concept`): its
   answer is a table of conclusions with the papers each rests on. That brief is the least the agent
   needs to run (it requires one) and says nothing of conditions, metrics, values or rules. A brief
   picked through the concept step (`agent concepts propose/pick`) can be given instead.
3. The agent's answer has no explicit per-paper stance, so one schema-constrained call (the same
   AnswerReply schema and label rules as the RAG baseline, temperature 0, cached by prompt hash,
   model and input) maps its answer text (rows, facts, notes, and the quotes of the claims it cites)
   to the label and the stance of every paper it relies on. An answer with no rows is
   `insufficient` without a call.

The runner is an evidence.agentic.runner.AgentRunner: ResearchAgentRunner for real runs (Linux,
sandbox, LiteLLM gateway), a fake in tests.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai.models import Model

from evidence.agentic.runner import AgentJob, AgentRunner
from gold.llm import JsonlCache, redact

from .common import DEFAULT_QUESTION, LABEL_RULES, AnswerReply, SystemCorpus, answer_json, cached_reply

SYSTEM = "agent-baseline"
BUDGET = {"steps": 60, "tokens": 2_000_000}  # the research runs' provisional budget (agent/rundir.BUDGET)

MAP_INSTRUCTIONS = f"""You are given a research question, the ids of the papers in a corpus, and the answer a research
agent wrote after reading the corpus: its rows, the facts it recorded (subject | predicate | object) with the quotes
behind them, and its notes. Do not add knowledge of your own: report what the agent's answer says. Give the label the
agent's answer amounts to and, for every corpus paper the answer relies on, the stance it attributes to that paper.
Use only the paper ids listed.

{LABEL_RULES}"""


def question_concept(question: str) -> dict[str, Any]:
    """A concept brief (agent/schemas/concept.schema.json) made from the question alone."""
    return {"title": question, "definition": f"The answer to this question from the papers of the corpus: {question}",
            "measure": {"operation": "answer", "of": "Question"},
            "scope": {"papers": "every paper in the corpus"},
            "answer_shape": {"kind": "table", "columns": [{"name": "conclusion", "type": "string"},
                                                          {"name": "papers", "type": "list<Paper>"}]},
            "competency_questions": [question, "Which corpus papers does the answer rest on?"]}


def answer_text(record: dict[str, Any]) -> str:
    """The agent's answer as plain text for the mapping call: rows, facts with their claims' quotes, notes."""
    answer = record.get("answer") or {}
    quotes = {c["claim_id"]: (c.get("file"), c.get("quote")) for c in record.get("claims", [])
              if c.get("status") == "accepted"}
    lines = []
    for row in answer.get("rows", []):
        lines.append(f"Row {row.get('id')}: " + json.dumps(row.get("cells") or {k: row.get(k) for k in
                                                                               ("source", "predicate", "target")},
                                                       ensure_ascii=False, sort_keys=True))
        for fact in row.get("facts", []):
            lines.append(f"  fact: {fact.get('s')} | {fact.get('p')} | {fact.get('o')}")
            for claim in fact.get("claims", []):
                file, quote = quotes.get(claim, (None, None))
                if quote:
                    lines.append(f"    quote from {file}: \"{quote}\"")
    if answer.get("notes"):
        lines.append(f"Notes: {answer['notes']}")
    return "\n".join(lines)


def agent_baseline(corpus_dir: Path, *, runner: AgentRunner, model: Model, question: str = DEFAULT_QUESTION,
                   concept: dict[str, Any] | None = None, budget: dict[str, int] | None = None,
                   cache: JsonlCache | None = None, model_id: str | None = None, run_id: str = "agent-baseline",
                   seed: int = 0) -> dict[str, Any]:
    """answer.json of the agent baseline for one corpus."""
    corpus = SystemCorpus(corpus_dir)
    job = AgentJob(run_id=run_id, files={f"{p.id}.md": p.text for p in corpus.papers},
                   concept=concept or question_concept(question), budget=dict(budget or BUDGET))
    try:
        record = runner.run(job)
    except Exception as exc:  # provider errors can echo the key: only a redacted reason leaves here
        raise RuntimeError(redact(f"agent run failed: {type(exc).__name__}: {exc}")[:1000]) from None
    text = answer_text(record)
    outcome = record.get("outcome") or {}
    agent = {"run_id": record.get("run_id", run_id), "exit_status": outcome.get("exit_status"),
             "answer_from": outcome.get("answer_from"), "steps": outcome.get("steps"), "tokens": outcome.get("tokens"),
             "model_calls": len(record.get("model_calls", [])), "claims": sum(c.get("status") == "accepted"
                                                                              for c in record.get("claims", []))}
    if not (record.get("answer") or {}).get("rows"):
        reply, call = AnswerReply(label="insufficient", studies=[], answer_text=text or "(no answer)"), None
    else:
        ids = ", ".join(corpus.ids)
        prompt = f"Question: {question}\n\nCorpus paper ids: {ids}\n\nThe agent's answer:\n{text}"
        reply, call = cached_reply(cache, MAP_INSTRUCTIONS, prompt, model=model, model_id=model_id, seed=seed)
        call.pop("cached")
    return answer_json(SYSTEM, question, reply, corpus.ids, corpus_id=corpus.corpus_id, agent=agent,
                       agent_answer=record.get("answer"), agent_answer_text=text, mapping_call=call)
