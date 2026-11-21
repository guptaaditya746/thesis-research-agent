"""Step "deepeval": standard DeepEval metrics on a finished run (optional extra: `uv sync --extra deepeval`).

Two parts, both judged by the run's "judge" role through paperfactory's model layer (cached, logged in calls.jsonl,
capped per server by the lock files):
  gold_grounding  dataset quality: is each question's gold answer supported by the sentences tagged for it in the
                  papers? (FaithfulnessMetric: actual_output = the gold facts in words, retrieval_context = those
                  sentences). A low score means the paper does not clearly state what the gold says.
  qa_system       the QA system under test (the "qa" role): FaithfulnessMetric (answer supported by its own quotes),
                  AnswerRelevancyMetric (answer on the question), ContextualRecallMetric (gold supported by the
                  quotes it retrieved).
Never stops the run: a case whose metric fails is recorded with its error; without deepeval installed the step
writes {"skipped": ...}. Telemetry and .env reading of deepeval are switched off. The judge is the same model
family as the writer when every role uses one model (config.shared_models warns): treat scores as correlated.
Output: deepeval.json in the run folder.
"""
from __future__ import annotations

import json
import os
import statistics
from typing import Any

from paperfactory import files
from paperfactory.llm import pmap

SYS = "You are an evaluator. Follow the instructions exactly and answer in the required JSON form."
TEXT = {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}


def _deepeval() -> Any:
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")
    os.environ.setdefault("DEEPEVAL_DISABLE_DOTENV", "1")
    import deepeval.metrics as metrics
    from deepeval.models import DeepEvalBaseLLM
    from deepeval.test_case import LLMTestCase
    return metrics, DeepEvalBaseLLM, LLMTestCase


def judge_model(call, base, step: str) -> Any:
    """A DeepEval model that answers through paperfactory's Caller (role "judge")."""
    class Judge(base):
        def __init__(self) -> None:
            super().__init__("paperfactory-judge")

        def load_model(self, *a, **k):
            return self

        def generate(self, prompt: str, schema=None, **k):
            out = call("judge", f"deepeval:{step}", SYS, prompt, schema if schema is not None else TEXT)
            if out is None:
                raise ValueError("the judge gave no answer in the required form (parse_error)")
            return schema.model_validate(out) if schema is not None else out["text"]

        async def a_generate(self, prompt: str, schema=None, **k):
            return self.generate(prompt, schema=schema)

        def get_model_name(self, *a, **k):
            return "paperfactory judge role"
    return Judge()


def cases(report: dict[str, Any], tagged: dict[str, Any], fact_text) -> list[dict[str, Any]]:
    """One case per QA question: the gold in words, the sentences tagged for the gold, and the QA answer."""
    out = []
    for q in report.get("qa", []):
        gold_sents = [s[2] for pid in q["papers"] for s in tagged.get(pid, {}).get("sentences", [])
                      for i in q["gold"] if [s[0], s[1]] in tagged[pid]["spans"].get(i, [])]
        out.append({"id": q["id"], "question": q["question"], "gold": [fact_text(i) for i in q["gold"]],
                    "gold_sentences": list(dict.fromkeys(gold_sents)),
                    "answer": " ".join(it.get("answer_sentence", "") for it in q.get("items", [])).strip(),
                    "quotes": [it.get("quote", "") for it in q.get("items", []) if it.get("quote")]})
    return out


def measure(metric_cls, model, case_cls, **case) -> dict[str, Any]:
    try:
        m = metric_cls(model=model, async_mode=False, include_reason=False)
        m.measure(case_cls(**case))
        return {"score": m.score}
    except Exception as e:  # noqa: BLE001 - one bad case is recorded, never stops the run
        return {"score": None, "error": f"{type(e).__name__}: {str(e)[:300]}"}


def run(s, call, fact_text) -> dict[str, Any]:
    out_dir = s.out_dir
    try:
        metrics, base, case_cls = _deepeval()
    except Exception as e:  # noqa: BLE001
        res = {"skipped": f"deepeval not available ({type(e).__name__}: {str(e)[:200]}); uv sync --extra deepeval"}
        files.write_json(out_dir / "deepeval.json", res)
        return res
    try:
        report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
        tagged = json.loads((out_dir / "tagged.json").read_text(encoding="utf-8"))["papers"]
    except (OSError, json.JSONDecodeError, KeyError) as e:
        res = {"skipped": f"no evaluation to read ({type(e).__name__}: {e})"}
        files.write_json(out_dir / "deepeval.json", res)
        return res
    cs = cases(report, tagged, fact_text)

    def one(c: dict[str, Any]) -> dict[str, Any]:
        model = judge_model(call, base, c["id"])
        r: dict[str, Any] = {"id": c["id"]}
        if c["gold_sentences"]:
            r["gold_grounding"] = measure(metrics.FaithfulnessMetric, model, case_cls, input=c["question"],
                                          actual_output=" ".join(c["gold"]), retrieval_context=c["gold_sentences"])
        else:
            r["gold_grounding"] = {"score": None, "error": "no sentence tagged for the gold"}
        if c["answer"]:
            r["faithfulness"] = measure(metrics.FaithfulnessMetric, model, case_cls, input=c["question"],
                                        actual_output=c["answer"], retrieval_context=c["quotes"] or [""])
            r["answer_relevancy"] = measure(metrics.AnswerRelevancyMetric, model, case_cls, input=c["question"],
                                            actual_output=c["answer"])
            r["contextual_recall"] = measure(metrics.ContextualRecallMetric, model, case_cls, input=c["question"],
                                             actual_output=c["answer"], expected_output=" ".join(c["gold"]),
                                             retrieval_context=c["quotes"] or [""])
        return r
    rows = pmap(one, cs, s.parallel)
    summary = {}
    for k in ("gold_grounding", "faithfulness", "answer_relevancy", "contextual_recall"):
        xs = [r[k]["score"] for r in rows if k in r and r[k]["score"] is not None]
        summary[k] = {"mean": round(statistics.mean(xs), 3) if xs else None, "n": len(xs),
                      "errors": sum(1 for r in rows if k in r and r[k]["score"] is None)}
    low = [r["id"] for r in rows if (r.get("gold_grounding") or {}).get("score") is not None
           and r["gold_grounding"]["score"] < 0.5]
    res = {"about": __doc__.split("\n\n")[0], "questions": len(rows), "summary": summary,
           "gold_grounding_below_0.5": low, "cases": rows}
    files.write_json(out_dir / "deepeval.json", res)
    return res
