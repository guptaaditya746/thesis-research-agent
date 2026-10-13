"""The `gold` review and judge subcommands end to end against the in-memory Argilla (fixtures.FakeArgilla):
push, people answer, snapshot, pull, export, agreement, the screening check and the judge calibration."""
from __future__ import annotations

import functools
import json
from pathlib import Path

import pytest

from agent.pairs import write_pairs
from agent.tests.runs import baseline_run, research_run
from gold import judge, review
from gold.cli import main

from .fixtures import ANSWERS, MISSING_LINES, NQ, QID, Env, FakeArgilla, cid, env, fake  # noqa: F401
from .test_judge import scripted


def gold(e: Env, *argv: str) -> int:
    paths = {"--corpus": e.corpus, "--concepts": e.concepts, "--questions": e.questions}
    known = {"push": ("--corpus", "--concepts", "--questions"), "export": ("--corpus", "--concepts", "--questions"),
             "screening-push": ("--corpus", "--concepts", "--questions"), "judge-push": ("--corpus",),
             "judge-agreement": ("--corpus",)}
    extra = [x for opt in known.get(argv[0], ()) for x in (opt, str(paths[opt]))]
    return main([*argv, "--gold", str(e.root), *extra])


def overlap_on(e: Env, qids: list[str]) -> None:
    review.write_json(e.root / review.OVERLAP_FILE, {"seed": "test", "share": 0.2, "questions": ["q01", "q02"],
                                                     "overlap": qids})


def test_review_round_trip(env: Env, fake: FakeArgilla, capsys: pytest.CaptureFixture[str]) -> None:
    overlap_on(env, ["q02"])
    assert gold(env, "push", "all") == 0 and gold(env, "push", QID) == 0  # the second push changes nothing
    assert len(fake.dataset("review").rows) == 7 and len(fake.dataset("missing").rows) == 1
    assert ("thesis", "gold-v1-overlap") not in fake.store
    record = fake.dataset("review").rows[cid(3)]
    assert record["fields"]["question"] == "Which benchmarks do the RAG papers evaluate on?"
    assert record["metadata"] == {"question_id": QID, "paper_id": "p5", "stratum": "triaged"}
    for rid, values in ANSWERS.items():
        fake.dataset("review").answer(rid, "aditya", **values)
    fake.dataset("missing").answer(f"missing-{QID}", "aditya", missing=MISSING_LINES, done="yes")
    assert gold(env, "pull") == 0
    assert len(review.read_jsonl(env.root / QID / "review" / "review.jsonl")) == 7
    assert gold(env, "export", QID) == 0
    key = review.read_json(env.root / QID / "key.json")
    assert key["review"]["kept"] == 4 and key["review"]["added"] == 2 and key["review"]["reviewers"] == ["aditya"]
    assert gold(env, "agreement") == 0
    assert review.read_json(env.root / QID / "report.json")["triage"]["estimated_missed"] == 1.0
    out = capsys.readouterr().out
    assert f"{QID}: 7 records -> review" in out and "key.json rows=6 facts=6 kept=4/7" in out


def test_overlap_snapshot_and_adjudication(env: Env, fake: FakeArgilla, capsys: pytest.CaptureFixture[str]) -> None:
    overlap_on(env, [QID])
    assert gold(env, "push", QID) == 0
    overlap = fake.dataset("overlap")
    assert len(overlap.rows) == 7 and overlap.settings.distribution.min_submitted == 2
    bob = {**ANSWERS, cid(4): {"label": "incorrect"}, cid(6): {"label": "correct"}}
    for rid in ANSWERS:
        overlap.answer(rid, "ann", **ANSWERS[rid])
        overlap.answer(rid, "bob", **bob[rid])
    assert gold(env, "snapshot") == 0 and len(review.snapshots(env.root, QID)) == 1
    overlap.answer(cid(4), "bob", label="correct")  # settled by talking it over, after the snapshot
    assert gold(env, "pull") == 0
    assert gold(env, "export", QID) == 0
    report = review.read_json(env.root / QID / "export.json")
    assert [d["candidate_id"] for d in report["disagreements"]] == [cid(6)]  # c4 is settled, c6 is not
    assert cid(4) in {f["candidate_id"] for r in review.read_json(env.root / QID / "key.json")["rows"] for f in r["facts"]}
    overlap.answer(cid(6), "carol", label="incorrect")
    assert gold(env, "pull") == 0 and gold(env, "export", QID, "--adjudicator", "carol") == 0
    report = review.read_json(env.root / QID / "export.json")
    assert report["disagreements"][0]["resolved_by"] == "carol" and report["counts"]["unresolved"] == 0
    assert gold(env, "agreement") == 0
    kappa = review.read_json(env.root / "report.json")["kappa"]
    assert kappa["reviewers"] == ["ann", "bob"] and kappa["items"] == 7
    # From the snapshot: ann and bob differ on c4 and c6, so label agreement is 5/7, not 6/7.
    assert kappa["label"]["raw_agreement"] == round(5 / 7, 4)


def test_screening_round(env: Env, fake: FakeArgilla) -> None:
    assert gold(env, "screening-sample", QID, "--size", "2") == 0
    drawn = review.read_json(env.root / QID / "screening.sample.json")
    assert gold(env, "screening-push", QID) == 0
    dataset = fake.dataset("screening")
    assert sorted(dataset.rows) == sorted(f"screening-{QID}-{p}" for p in drawn["papers"])
    first = f"screening-{QID}-{drawn['papers'][0]}"
    assert dataset.rows[first]["metadata"]["not_relevant_total"] == 4
    assert dataset.rows[first]["fields"]["paper"].startswith(f"`{drawn['papers'][0]}.md`\n\n")
    dataset.answer(first, "aditya", relevant="yes", missing=f"p6 | evaluatesOn | NQ | p6.md | {NQ.text}")
    dataset.answer(f"screening-{QID}-{drawn['papers'][1]}", "aditya", relevant="no")
    assert gold(env, "pull") == 0 and gold(env, "export", QID) == 0
    key = review.read_json(env.root / QID / "key.json")
    assert [f["o"] for r in key["rows"] for f in r["facts"]] == ["NQ"]  # nothing reviewed yet but this
    assert gold(env, "agreement") == 0
    s = review.read_json(env.root / QID / "report.json")["screening"]
    assert (s["checked"], s["found_relevant"], s["estimated_missed_papers"]) == (2, 1, 2.0)


def test_judge_round(env: Env, fake: FakeArgilla, monkeypatch: pytest.MonkeyPatch,
                     capsys: pytest.CaptureFixture[str]) -> None:
    manifest = env.corpus / "manifest.json"
    for built in (research_run(env.tmp, env.corpus, manifest), baseline_run(env.tmp, env.corpus, manifest)):
        write_pairs(built.run)
    assert gold(env, "judge-sample", "--runs", str(env.tmp / "runs")) == 0
    rows, sample = judge.load_sample(env.root)
    assert sample["population"] == {"claim_on": 4, "claim_off": 3} and len(rows) == 7
    assert gold(env, "judge-push") == 0
    dataset = fake.dataset("judge")
    assert all("<mark>" in r["fields"]["passage"] for r in dataset.rows.values())
    assert {r["metadata"]["condition"] for r in dataset.rows.values()} == {"claim_on", "claim_off"}
    for n, rid in enumerate(sorted(dataset.rows)):
        dataset.answer(rid, "ann", support="supports" if n % 3 else "no")
    calls: list[str] = []
    monkeypatch.setattr(judge, "Judge", functools.partial(judge.Judge, models=[scripted(calls)]))
    assert gold(env, "pull") == 0 and gold(env, "judge-agreement") == 0
    report = review.read_json(env.root / judge.REPORT_FILE)
    # Both runs cite the same quotes for Spider, GSM8K and HotpotQA: 4 distinct inputs, one model call each,
    # also for the duplicates judged at the same time (they wait for the call in flight).
    assert report["answered"] == report["judged"] == 7 and report["model_calls"] == 4 == len(calls)
    assert report["split"]["calibration"] + report["split"]["test"] == 7
    assert report["settings"] == {"temperature": 0.0, "seed": 0, "max_tokens": judge.MAX_TOKENS}
    assert report["render_sha256"] == judge.render_sha256()["support"]
    capsys.readouterr()
    fact = json.dumps({"s": "p1", "p": "evaluatesOn", "o": "Spider"})
    assert gold(env, "judge", fact, "benchmark datasets like Spider and Bird") == 0
    verdict = json.loads(capsys.readouterr().out)
    assert verdict["label"] == "supports" and verdict["model"] == "scripted-judge"


def test_push_needs_a_corpus(env: Env, fake: FakeArgilla, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORPUS", raising=False)
    with pytest.raises(SystemExit, match="--corpus"):
        main(["push", "all", "--gold", str(env.root)])


def test_overlap_choice_is_made_once(env: Env, tmp_path: Path) -> None:
    qids = [f"q{n:02d}" for n in range(1, 13)]
    first = review.overlap_questions(env.root, qids)
    assert len(first) == 3 and set(first) <= set(qids)  # ceil(0.2 x 12)
    assert review.overlap_questions(env.root, ["q01"]) == first  # kept in overlap.json
    assert review.overlap_questions(tmp_path / "other", qids) == first  # the same seed, the same choice
    assert review.overlap_questions(tmp_path / "empty", []) == []
    assert not (tmp_path / "empty" / review.OVERLAP_FILE).exists()  # no questions yet: nothing fixed
