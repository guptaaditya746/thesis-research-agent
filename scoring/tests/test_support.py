"""scoring/support.py and scoring/judge.py: each fact's quotes judged, unsourced facts, the support share,
the calibrated context and partial mapping, C2's async judge on one loop, a missing or failing judge."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from agent.pairs import write_pairs
from agent.tests.runs import Built, baseline, corpus_env, research  # noqa: F401  (pytest fixtures)
from scoring.judge import Judge, describe, load
from scoring.support import calibration, fact_label, judge_support, summarise

from .helpers import C2Judge, judge


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
    assert (result["support_share_partial_no"], result["support_share_partial_yes"]) == (3 / 5, 4 / 5)
    assert result["claims_per_fact"] == 1.0 and result["support_share_first_claim"] == 3 / 5
    # A judge without support_pair sees the fact's own s/p/o and the anchored quote, no context.
    calls = fake.asked("support")  # in any order: the judge's workers run them concurrently
    assert ({"s": "p1", "p": "evaluatesOn", "o": "BIRD"},
            "deployable LLMs using benchmark datasets like Spider and Bird", None) in calls and len(calls) == 4
    assert result["context"] == "none"
    f4 = next(d for d in result["detail"] if d["fact_id"] == "f4")
    assert f4["claims"] == [{"claim_id": "claim-000005", "file": "p6.md", "label": "supports",
                             "rationale": "'HotpotQA' in quote: supports", "model": "fake-judge",
                             "prompt_sha256": "0" * 64, "cached": False}]


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
    assert result["unsourced_share"] == 1 / 5 and result["context"] is None
    assert result["support_share_first_claim"] is None and result["support_share_partial_yes"] is None


def test_a_failing_judge_leaves_pending_and_reports_errors(research: Built) -> None:
    j, _ = judge(fail=True)
    result = judge_support(research.run, j)
    assert result["pending"] == 4 and result["support_share"] is None
    assert j.pending == 4 and j.errors[0] == "support: ConnectionError: judge down"


def test_bad_labels_are_not_trusted(research: Built) -> None:
    class Odd:
        def support(self, fact, quote, *, context=None):
            return {"label": "maybe"}

    j = Judge(Odd())
    assert judge_support(research.run, j)["pending"] == 4 and "not one of" in j.errors[0]


def test_c2_shaped_judge_runs_async_on_one_loop_with_the_calibrated_context(research: Built) -> None:
    impl = C2Judge()
    made: list[Path] = []
    j = Judge(impl, "gold.judge", workers=4, corpus=lambda path: made.append(path) or f"Corpus({path.name})")
    result = judge_support(research.run, j, corpus=research.corpus)
    assert (result["supports"], result["partial"], result["pending"], result["context"]) == (3, 1, 0, "calibrated")
    assert len(impl.loops) == 1 and len(impl.pairs) == 4  # every call awaited on scoring's one loop
    pair, corpus = impl.pairs[0]
    assert corpus == "Corpus(corpus)" and made == [research.corpus]  # one corpus object, reused
    assert {"file", "start", "end", "quote", "s", "p", "o"} <= set(pair)  # the pairs.jsonl line as is
    # Another run on a fork: the same loop, counts of its own.
    twin = j.fork()
    judge_support(research.run, twin, corpus=research.corpus)
    assert len(impl.loops) == 1 and (j.calls, twin.calls) == (4, 4)
    assert twin.summary()["identity"] == {"name": "gold.judge", "model": C2Judge.model_id,
                                          "prompts": impl.prompt_hashes()}
    assert twin.summary()["prompt_sha256"] == ["p1" * 32]
    # Without the corpus the judge gets the quote alone, through the async support().
    assert judge_support(research.run, j)["context"] == "none" and len(impl.pairs) == 8


def test_load_wraps_default_judge_and_the_review_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    impl = C2Judge()
    module = types.ModuleType("gold.judge")
    module.default_judge = lambda: impl
    module.support = lambda *a, **k: (_ for _ in ()).throw(AssertionError("sync module API used"))
    review = types.ModuleType("gold.review")
    review.Corpus = lambda path: ("Corpus", path)
    monkeypatch.setitem(sys.modules, "gold.judge", module)
    monkeypatch.setitem(sys.modules, "gold.review", review)
    j = load(workers=3)
    assert j is not None and j.impl is impl and j.workers == 3 and j.corpus_type is review.Corpus
    assert j.support({"s": "p1", "p": "x", "o": "Spider"}, "on Spider")["label"] == "supports"
    assert j.same_fact({"s": 1, "p": 2, "o": 3}, {"s": 1, "p": 2, "o": 3}, {}) is False
    assert j.context_mode(Path("c")) == "calibrated" and j.context_mode(None) == "none"
    assert load(False) is None


def test_load_without_gold_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("gold.judge")
    module.support = lambda fact, quote, *, context=None: {"label": "no"}
    monkeypatch.setitem(sys.modules, "gold.judge", module)
    monkeypatch.setitem(sys.modules, "gold.review", None)
    j = load()
    assert j is not None and j.impl is module and j.corpus_type is None
    assert j.support({"s": 1, "p": 2, "o": 3}, "q") == {"label": "no"} and j.context_mode(Path("c")) == "none"
    said: list[str] = []
    monkeypatch.setitem(sys.modules, "gold.judge", None)  # as if C2's module were not there
    assert load(log=said.append) is None and "no judge" in said[0]


def test_errors_never_keep_a_key_or_an_http_body(monkeypatch: pytest.MonkeyPatch) -> None:
    class ModelHTTPError(Exception):
        def __init__(self) -> None:
            super().__init__("status_code: 401, body: Received API Key = sk-...abcd, Key Hash (Token) =9f86d0")
            self.status_code, self.body = 401, {"error": "Received API Key = sk-...abcd"}

    assert describe("support", ModelHTTPError()) == "support: ModelHTTPError 401"
    monkeypatch.setenv("LITELLM_MASTER_KEY", "plain-secret-key")
    text = describe("same_fact", RuntimeError("auth failed for plain-secret-key and sk-live-123, "
                                              "Key Hash (Token) =" + "ab" * 32))
    assert "plain-secret-key" not in text and "sk-live" not in text and "ab" * 32 not in text
    assert text.startswith("same_fact: RuntimeError: auth failed for [redacted]")


def test_partial_mapping_from_the_calibration(tmp_path: Path) -> None:
    assert calibration(tmp_path) == {"partial_counts_as": "no", "source": None, "sha256": None}
    assert calibration(None)["partial_counts_as"] == "no"
    (tmp_path / "judge-report.json").write_text(json.dumps({"calibration": {"partial_counts_as": "yes"}}),
                                                encoding="utf-8")
    found = calibration(tmp_path)
    assert found["partial_counts_as"] == "yes" and len(found["sha256"]) == 64
    detail = [{"label": "supports", "first_claim_label": "supports", "claims": [{}]},
              {"label": "partial", "first_claim_label": "no", "claims": [{}, {}]},
              {"label": "unsourced", "first_claim_label": "unsourced", "claims": []}]
    yes, no = summarise(detail, "yes"), summarise(detail, "no")
    assert (yes["support_share"], no["support_share"]) == (2 / 3, 1 / 3)
    assert yes["support_share_partial_no"] == no["support_share_partial_no"] == 1 / 3
    assert (yes["support_share_first_claim"], yes["claims_per_fact"]) == (1 / 3, 1.5)


def test_fact_label_rules() -> None:
    v = {"supports": {"label": "supports"}, "partial": {"label": "partial"}, "no": {"label": "no"}}
    assert fact_label([]) == "unsourced"
    assert fact_label([v["no"], v["supports"]]) == "supports"  # one supporting quote is enough
    assert fact_label([v["partial"], None]) == "pending"
    assert fact_label([v["supports"], None]) == "supports"
    assert fact_label([v["no"], v["partial"]]) == "partial"
