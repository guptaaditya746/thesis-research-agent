"""scoring/support.py: each fact's quotes judged, unsourced facts, the support share, a missing judge."""
from __future__ import annotations

from agent.pairs import write_pairs
from agent.tests.runs import Built, baseline, corpus_env, research  # noqa: F401  (pytest fixtures)
from scoring.judge import Judge
from scoring.support import fact_label, judge_support, quote_context

from .helpers import judge


def by_fact(result: dict) -> dict[str, str]:
    return {d["fact_id"]: d["label"] for d in result["detail"]}


def test_research_run(research: Built) -> None:
    j, fake = judge()
    result = judge_support(research.run, j, corpus=research.corpus)
    # f1 Spider and f3 GSM8K and f4 HotpotQA occur in their quotes; f2 "BIRD" only as "Bird"; f5 has no claim.
    assert by_fact(result) == {"f1": "supports", "f2": "partial", "f3": "supports", "f4": "supports",
                               "f5": "unsourced"}
    counts = {k: result[k] for k in ("facts", "with_claims", "supports", "partial", "no", "unsourced", "pending")}
    assert counts == {"facts": 5, "with_claims": 4, "supports": 3, "partial": 1, "no": 0, "unsourced": 1, "pending": 0}
    assert result["support_share"] == 3 / 5 and result["unsourced_share"] == 1 / 5
    # The judge sees the fact's own s/p/o, the anchored quote, and which paper it comes from.
    calls = fake.asked("support")
    assert [c[0] for c in calls][1] == {"s": "p1", "p": "evaluatesOn", "o": "BIRD"}
    assert calls[1][1] == "deployable LLMs using benchmark datasets like Spider and Bird"
    assert calls[1][2].startswith("The quote is from the corpus paper p1 (file p1.md), titled ")
    f4 = next(d for d in result["detail"] if d["fact_id"] == "f4")
    assert f4["claims"] == [{"claim_id": "claim-000005", "file": "p6.md", "label": "supports",
                             "rationale": "'HotpotQA' in quote: supports", "model": "fake-judge"}]


def test_baseline_after_attach(baseline: Built) -> None:
    write_pairs(baseline.run)  # the attach step rewrites pairs.jsonl; read from the file here
    j, _ = judge()
    result = judge_support(baseline.run, j)
    # f4: the attach step found no source, so the fact is unsourced.
    assert by_fact(result) == {"f1": "supports", "f2": "supports", "f3": "supports", "f4": "unsourced"}
    assert {d["origin"] for d in result["detail"]} == {"attach"}
    assert result["support_share"] == 3 / 4 and result["with_claims"] == 3


def test_without_a_judge_verdicts_stay_pending(research: Built) -> None:
    result = judge_support(research.run, None)
    assert (result["pending"], result["unsourced"], result["support_share"]) == (4, 1, None)
    assert result["unsourced_share"] == 1 / 5


def test_a_failing_judge_leaves_pending_and_reports_errors(research: Built) -> None:
    j, _ = judge(fail=True)
    result = judge_support(research.run, j, workers=4)
    assert result["pending"] == 4 and result["support_share"] is None
    assert j.pending == 4 and j.errors[0] == "support: ConnectionError: judge down"


def test_bad_labels_are_not_trusted(research: Built) -> None:
    class Odd:
        def support(self, fact, quote, *, context=None):
            return {"label": "maybe"}

    j = Judge(Odd())
    assert judge_support(research.run, j)["pending"] == 4 and "not one of" in j.errors[0]


def test_fact_label_rules() -> None:
    v = {"supports": {"label": "supports"}, "partial": {"label": "partial"}, "no": {"label": "no"}}
    assert fact_label([]) == "unsourced"
    assert fact_label([v["no"], v["supports"]]) == "supports"  # one supporting quote is enough
    assert fact_label([v["partial"], None]) == "pending"
    assert fact_label([v["supports"], None]) == "supports"
    assert fact_label([v["no"], v["partial"]]) == "partial"
    assert quote_context(None) is None and quote_context("p3.md") == "The quote is from the corpus paper p3 (file p3.md)."
