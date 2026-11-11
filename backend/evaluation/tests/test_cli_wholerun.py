"""The evaluation commands of the general system (Wave 2 Task 8.3): wholerun, leak, offtemplate, links. Fixtures and
fake models only: no network, no real model call."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from evaluation import cli, wholerun_cmd
from evaluation.truth import Fact, GroundTruth
from evaluation.wholerun import Answer, RealQuestion
from evidence.plan import WordList, write_plan
from evidence.tests.test_plan_run import make_plan

from . import fixtures as fx

DATA = Path(__file__).resolve().parent / "data"


def plan_for(confirmed_by: str, question: str = "Which?", fresh: bool = False) -> Any:
    plan = make_plan()
    lines = [plan.lines[1] if fresh else plan.lines[0]] + plan.lines[2:]
    lines[0] = lines[0].model_copy(update={"question": question})
    return plan.model_copy(update={"lines": lines, "decisions": [
        d.model_copy(update={"confirmed_by": confirmed_by}) for d in plan.decisions]})


def make_run(runs: Path, conf: str, reasoning: str, q: RealQuestion, ranking: list[str], *, fresh: bool = False,
             model: str = "orch-model", plan: bool = True) -> None:
    root = runs / conf / reasoning / q.id
    root.mkdir(parents=True)
    rows = [{"thing": p, "paper": f"P{i}"} for i, p in enumerate(ranking)]
    lid = "l2" if fresh else "l1"   # the id of plan_for's first line
    line = {"id": lid, "question": q.question, "status": "done", "rows": rows, "text": f"{len(rows)} found"}
    (root / "answer.json").write_text(json.dumps({"system": "plan", "lines": [line]}), encoding="utf-8")
    (root / "run.json").write_text(json.dumps({"settings": {"corpus": str(q.corpus_dir), "model": model}}), encoding="utf-8")
    if plan:
        write_plan(plan_for("system" if conf == "auto-confirmed" else "aditya", q.question, fresh), root / "plan.json")


def questions(n: int = 3, corpus: Path = Path(".")) -> list[RealQuestion]:
    return [RealQuestion(f"q{i}", f"Which {i}?", "cs", corpus, {"ranking": ["A", "B"], "papers": [f"P{i}"]}, "rank")
            for i in range(n)]


def build(tmp: Path, qs: list[RealQuestion]) -> Path:
    runs = tmp / "runs"
    for n, q in enumerate(qs):
        for reasoning in ("on", "off"):
            make_run(runs, "auto-confirmed", reasoning, q, ["A", "B"] if reasoning == "on" else ["B", "A"], fresh=n == 0)
        if n < 2:
            make_run(runs, "hand-confirmed", "on", q, ["A", "B"])
    return runs


def test_two_rows_per_set_and_both_reasoning_settings(tmp_path: Path) -> None:
    qs = questions()
    report = wholerun_cmd.wholerun(qs, build(tmp_path, qs), tmp_path / "out", set_name="demo", n=10, seed=0,
                                   left_out="left out: 1 of 3 (no open full text)", reasoning=("on", "off"))
    rows = report["rows"]
    assert set(rows) == {"auto-confirmed/on", "auto-confirmed/off", "hand-confirmed/on", "hand-confirmed/off"}
    assert [r["top1"] for r in rows["auto-confirmed/on"]] == [1, 1, 1]
    assert [r["top1"] for r in rows["auto-confirmed/off"]] == [0, 0, 0]
    assert len(rows["hand-confirmed/on"]) == 3 and rows["hand-confirmed/on"][2]["missing_run"] and rows["hand-confirmed/on"][0]["confirmation"] == "hand-confirmed"
    assert report["left_out"] == "left out: 1 of 3 (no open full text)"
    assert report["generality"]["auto-confirmed"] == {"questions": 3, "fresh": 1, "template": 2, "fresh_share": 1 / 3}
    assert json.loads((tmp_path / "out" / "sample.json").read_text())["ids"] == ["q0", "q1", "q2"]
    assert "left out: 1 of 3 (no open full text)" in (tmp_path / "out" / "wholerun.md").read_text(encoding="utf-8")


def test_missing_run_is_listed_and_counts_as_a_zero_row(tmp_path: Path) -> None:
    qs = questions()
    runs = build(tmp_path, qs)
    shutil.rmtree(runs / "auto-confirmed" / "on" / "q2")
    report = wholerun_cmd.wholerun(qs, runs, tmp_path / "o", set_name="d", n=10, seed=0, left_out="x", reasoning=("on",))
    rows = report["rows"]["auto-confirmed/on"]
    assert len(rows) == 3 and rows[2]["missing_run"] and rows[2]["headline"] == 0.0
    assert report["missing"]["auto-confirmed/on"] == ["q2"] and report["summary"]["auto-confirmed/on"]["n_missing_run"] == 1


def test_rag_side_by_side_with_wins_losses_ties_and_no_assumed_winner(tmp_path: Path) -> None:
    qs = questions(corpus=fx.write_corpus(tmp_path))
    rag = {"global": {"q0": Answer(ranking=["B", "A"]), "q1": Answer(ranking=["A", "B"]), "q2": Answer(ranking=["A"])},
           "per_paper": {"q0": Answer(ranking=["A"]), "q1": Answer(ranking=["A"]), "q2": Answer(ranking=["A"])}}
    calls: list[tuple[str, str]] = []

    def rag_answer(q: RealQuestion, mode: str) -> Answer:
        calls.append((q.id, mode))
        return rag[mode][q.id]

    report = wholerun_cmd.wholerun(qs, build(tmp_path, qs), tmp_path / "o", set_name="d", n=10, seed=0, left_out="x",
                                   reasoning=("on", "off"), systems=("engine", "rag"), rag_answer=rag_answer, rag_model="orch-model")
    assert sorted(calls) == sorted((q.id, m) for q in qs for m in ("global", "per_paper"))   # once per question and mode
    one = next(c for c in report["comparison"] if c["engine"] == "auto-confirmed/on" and c["rag"] == "rag/global")
    assert (one["wins"], one["losses"], one["ties"]) == (1, 0, 2)
    assert one["paired"]["point"] == pytest.approx(1 / 3)
    off = next(c for c in report["comparison"] if c["engine"] == "auto-confirmed/off" and c["rag"] == "rag/global")
    assert (off["wins"], off["losses"], off["ties"]) == (0, 2, 1)
    assert "rag/global" in report["rows"] and "rag/per_paper" in report["rows"]


def test_engine_only_makes_no_rag_call(tmp_path: Path) -> None:
    qs = questions()
    report = wholerun_cmd.wholerun(qs, build(tmp_path, qs), tmp_path / "o", set_name="d", n=10, seed=0, left_out="x",
                                   reasoning=("on",), systems=("engine",), rag_answer=lambda q, m: pytest.fail("rag"))
    assert report["comparison"] == [] and not any(k.startswith("rag") for k in report["rows"])


def test_questions_with_tuning_papers_are_left_out_of_the_sample(tmp_path: Path) -> None:
    qs = questions()
    (tmp_path / "tune_split.json").write_text(json.dumps({"papers": ["P1"], "rest": ["P0", "P2"]}), encoding="utf-8")
    qs = [RealQuestion(q.id, q.question, q.field, tmp_path, q.gold, q.kind) for q in qs]
    report = wholerun_cmd.wholerun(qs, build(tmp_path, qs), tmp_path / "o", set_name="d", n=10, seed=0, left_out="x",
                                   reasoning=("on",))
    assert report["held_out_for_tuning"] == ["q1"] and [r["id"] for r in report["rows"]["auto-confirmed/on"]] == ["q0", "q2"]


def test_a_run_whose_plan_is_not_confirmed_as_its_row_says_is_refused(tmp_path: Path) -> None:
    qs = questions(1)
    runs = build(tmp_path, qs)
    write_plan(plan_for("aditya"), runs / "auto-confirmed" / "on" / "q0" / "plan.json")
    with pytest.raises(ValueError, match="auto-confirmed"):
        wholerun_cmd.wholerun(qs, runs, tmp_path / "o", set_name="d", n=10, seed=0, left_out="x", reasoning=("on",))


def test_cli_wholerun_on_the_sofc_fixture(tmp_path: Path) -> None:
    from evaluation.realpapers import sofc
    q = sofc.questions(DATA / "sofc_tiny")[0]
    runs = tmp_path / "runs"
    for reasoning in ("on", "off"):
        make_run(runs, "auto-confirmed", reasoning, q, ["GDC", "YSZ", "LSM"])
    out = tmp_path / "out"
    code = cli.main(["wholerun", "--set", "sofc", "--src", str(DATA / "sofc_tiny"), "--runs", str(runs), "--out", str(out),
                     "--confirm", "auto", "--system", "engine", "--sample", "10", "--seed", "0"])
    report = json.loads((out / "wholerun.json").read_text(encoding="utf-8"))
    assert code == 0 and report["left_out"] == "left out: 1 of 3 (no open full text)"
    assert set(report["rows"]) == {"auto-confirmed/on", "auto-confirmed/off"}
    assert report["rows"]["auto-confirmed/on"][0]["kendall_tau"] == 1.0
    assert report["sample"] == {"seed": 0, "n": 10, "ids": [q.id]}


def test_cli_wholerun_defaults_are_the_decided_ones() -> None:
    args = cli.parser().parse_args(["wholerun", "--set", "scilead", "--src", "s", "--runs", "r", "--out", "o"])
    assert (args.sample, args.seed, args.system, args.reasoning, args.confirm) == (10, 0, "both", "both", "both")
    with pytest.raises(SystemExit):
        cli.parser().parse_args(["wholerun", "--set", "other", "--src", "s", "--runs", "r", "--out", "o"])


# --- leak ---------------------------------------------------------------------------------------------------------

def test_leak_command_splits_recall_on_the_list_and_unseen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus, run = tmp_path / "rag-claude-k1-abc", tmp_path / "run"
    corpus.mkdir()
    run.mkdir()
    truth = GroundTruth("rag-claude-k1-abc", "q", [], [], {})
    truth.facts["S.c0"] = Fact("S.c0", "condition", "S", "explicit", {"label": "closed book"})
    truth.facts["S.c1"] = Fact("S.c1", "condition", "S", "explicit", {"label": "brand new"})
    monkeypatch.setattr(GroundTruth, "load", classmethod(lambda cls, p: truth))
    monkeypatch.setattr("evaluation.score.score_extraction_only",
                        lambda *a, **k: {"missed": ["S.c1"], "scored_types": ["condition"]})
    plan = make_plan().model_copy(update={"words": WordList(things={"t": ["Closed-Book"]}, cues=[],
                                                            written_by="orch-model", ontology_names={})})
    write_plan(plan, run / "plan.json")
    assert cli.main(["leak", "--run", str(run), "--corpus", str(corpus), "--out", str(tmp_path / "o")]) == 0
    data = json.loads((tmp_path / "o" / "leak.json").read_text(encoding="utf-8"))
    assert data["on the list"]["recall"] == 1.0 and data["unseen"]["recall"] == 0.0
    assert "on the list" in (tmp_path / "o" / "leak.md").read_text(encoding="utf-8")


def test_leak_refuses_a_corpus_that_is_not_claude_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    truth = GroundTruth("rag-other", "q", [], [], {})
    monkeypatch.setattr(GroundTruth, "load", classmethod(lambda cls, p: truth))
    monkeypatch.setattr("evaluation.score.score_extraction_only", lambda *a, **k: {"missed": []})
    write_plan(make_plan(), tmp_path / "plan.json")
    with pytest.raises(SystemExit, match="Claude-written"):
        cli.main(["leak", "--run", str(tmp_path), "--corpus", str(tmp_path), "--out", str(tmp_path / "o")])


# --- off-template ---------------------------------------------------------------------------------------------------

def test_offtemplate_reports_the_two_numbers(tmp_path: Path) -> None:
    from evaluation.offtemplate import check as ot
    first, second = ot.load_questions()[:2]
    runs = tmp_path / "runs"
    for q, query in ((first, first.sparql), (second, "SELECT ?x WHERE { ?x a ev:Nothing }")):
        (runs / q.id).mkdir(parents=True)
        plan = plan_for("system", q.question, fresh=True)
        write_plan(plan.model_copy(update={"lines": [plan.lines[0].model_copy(update={"query": query})]}),
                   runs / q.id / "plan.json")
    assert cli.main(["offtemplate", "--runs", str(runs), "--out", str(tmp_path / "o")]) == 0
    data = json.loads((tmp_path / "o" / "offtemplate.json").read_text(encoding="utf-8"))
    # every question counts: the 10 without a plan are neither fresh nor a match
    assert data["summary"]["questions"] == 12 and data["summary"]["fresh_share"] == round(2 / 12, 4)
    assert data["summary"]["match_rate"] == round(1 / 12, 4) and data["not_run"] == 10


# --- links ----------------------------------------------------------------------------------------------------------

def link(paper: str, work: str | None, ref: str, in_set: str | None = None) -> dict[str, Any]:
    """A link as a plan run writes it (planrun.links_of): `ref` is the DOI, arXiv id or cited text, `work` the OpenAlex id
    of the resolved work (null when the work was not resolved)."""
    return {"paper": paper, "relation": "builds on", "ref": ref, "work": work, "in_set": in_set,
            "text": f"in the set: {in_set}" if in_set else "outside the set"}


def test_builds_on_recall_compares_on_the_work_id() -> None:
    links = [link("p1", "https://openalex.org/W1", "10.1/one"), link("p1", "W9", "10.1/nine"),
             link("p2", "W3", "10.1/three", "p3")]
    refs = {"p1": ["https://openalex.org/W1", "W2"], "p2": [{"work": "W3", "doi": None}], "p3": []}
    got = wholerun_cmd.builds_on_recall(links, refs)
    assert got["recall"] == pytest.approx(2 / 3) and got["precision"] == pytest.approx(2 / 3)
    assert {k: got["per_paper"]["p1"][k] for k in ("expected", "found")} == {"expected": 2, "found": 1}
    assert wholerun_cmd.builds_on_recall([], {"p": []})["recall"] is None


def test_builds_on_recall_falls_back_to_doi_equality() -> None:
    links = [link("p1", None, "https://doi.org/10.1/Two"), link("p1", None, "Lewis et al. (2020)")]   # nothing resolved
    got = wholerun_cmd.builds_on_recall(links, {"p1": [{"work": "W1", "doi": "10.1/one"}, {"work": "W2", "doi": "10.1/two"}]})
    assert got["per_paper"]["p1"]["found"] == 1 and got["recall"] == 0.5


def test_a_link_whose_openalex_request_failed_is_neither_hit_nor_miss() -> None:
    failed = {**link("p1", None, "10.1/zzz"), "text": "outside the set (resolve_failed: timeout)"}
    got = wholerun_cmd.builds_on_recall([link("p1", "W1", "r"), failed], {"p1": ["W1", "W2"]})
    assert got["n_links"] == 1 and got["n_unresolved"] == 1 and got["precision"] == 1.0


def test_links_command_scores_builds_on_from_a_references_file(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "answer.json").write_text(json.dumps({"links": [link("p1", "W1", "10.1/one")]}), encoding="utf-8")
    refs = tmp_path / "refs.json"
    refs.write_text(json.dumps({"p1": ["W1", "W2"]}), encoding="utf-8")
    assert cli.main(["links", "--run", str(run), "--references", str(refs), "--out", str(tmp_path / "o")]) == 0
    data = json.loads((tmp_path / "o" / "links.json").read_text(encoding="utf-8"))
    assert data["builds_on"]["recall"] == 0.5 and "chaining" not in data


def test_links_not_run_is_said_never_a_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = tmp_path / "run"
    run.mkdir()
    refs = tmp_path / "refs.json"
    refs.write_text(json.dumps({"p1": ["W1"]}), encoding="utf-8")
    old = {"links": [{"paper": "p1", "relation": "builds on", "ref": "10.1/one", "in_set": None, "text": "x"}]}   # no `work`
    cases = {"no references": ({"links": [link("p1", "W1", "r")]}, {"p1": []}), "no work key": (old, {"p1": ["W1"]}),
             "no links key": ({}, {"p1": ["W1"]})}
    for name, (answer, references) in cases.items():
        (run / "answer.json").write_text(json.dumps(answer), encoding="utf-8")
        refs.write_text(json.dumps(references), encoding="utf-8")
        assert cli.main(["links", "--run", str(run), "--references", str(refs), "--out", str(tmp_path / "o")]) == 0, name
        data = json.loads((tmp_path / "o" / "links.json").read_text(encoding="utf-8"))
        assert data["builds_on"]["recall"] is None and data["builds_on"]["status"].startswith("links not run"), name
        assert "links not run" in (tmp_path / "o" / "links.md").read_text(encoding="utf-8")
    assert "links not run" in capsys.readouterr().out


def _record(run: Path, bodies: dict[str, dict[str, Any]]) -> None:
    """openalex.jsonl as the run records it: every HTTP answer, keyed by URL."""
    from evidence.openalex import RECORD_FILE, OpenAlex
    from modelcall.cache import JsonlCache
    client = OpenAlex(JsonlCache(run / RECORD_FILE), fetch=lambda url: bodies[url])
    for url in bodies:
        client.get(url)


def test_build_references_reads_the_recorded_openalex_answers(tmp_path: Path) -> None:
    corpus, run = tmp_path / "corpus", tmp_path / "run"
    (corpus / "papers").mkdir(parents=True)
    run.mkdir()
    (corpus / "papers" / "p1.md").write_text("# A paper\n\ndoi:10.1/paper\n\nText.", encoding="utf-8")
    (corpus / "papers" / "p2.md").write_text("# Another paper\n\nText.", encoding="utf-8")
    (corpus / "manifest.json").write_text(json.dumps({"papers": [
        {"id": "p1", "file": "papers/p1.md"}, {"id": "p2", "file": "papers/p2.md"}]}), encoding="utf-8")
    base = "https://api.openalex.org/works/"
    _record(run, {
        base + "doi:10.1/paper": {"id": "https://openalex.org/W10", "doi": "https://doi.org/10.1/paper",
                                  "referenced_works": ["https://openalex.org/W1", "https://openalex.org/W2"]},
        base + "doi:10.1/one": {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/one",
                                "referenced_works": []},
        base + "doi:10.9/missing": None})        # a 404 is recorded too
    got = wholerun_cmd.build_references(run, corpus)
    assert got == {"p1": [{"work": "W1", "doi": "10.1/one"}, {"work": "W2", "doi": None}]}


def test_links_command_builds_the_references_file_then_scores(tmp_path: Path) -> None:
    corpus, run = tmp_path / "corpus", tmp_path / "run"
    (corpus / "papers").mkdir(parents=True)
    run.mkdir()
    (corpus / "papers" / "p1.md").write_text("# A paper\n\ndoi:10.1/paper\n", encoding="utf-8")
    (corpus / "manifest.json").write_text(json.dumps({"papers": [{"id": "p1", "file": "papers/p1.md"}]}), encoding="utf-8")
    _record(run, {"https://api.openalex.org/works/doi:10.1/paper": {
        "id": "https://openalex.org/W10", "doi": "10.1/paper", "referenced_works": ["https://openalex.org/W1", "W2"]}})
    (run / "answer.json").write_text(json.dumps({"links": [link("p1", "W2", "10.1/two")]}), encoding="utf-8")
    out = tmp_path / "o"
    assert cli.main(["links", "--run", str(run), "--corpus", str(corpus), "--build-references", "--out", str(out)]) == 0
    assert json.loads((out / "openalex-references.json").read_text(encoding="utf-8")) == {
        "p1": [{"work": "W1", "doi": None}, {"work": "W2", "doi": None}]}
    assert json.loads((out / "links.json").read_text(encoding="utf-8"))["builds_on"]["recall"] == 0.5


def test_links_command_scores_chaining_with_the_existing_scorer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Any] = []
    monkeypatch.setattr("evaluation.score.score", lambda *a, **k: seen.append((a, k)) or {
        "question_id": "q", "kind": "chaining", "systems": [{"kind": "chaining", "headline": 1.0}]})
    assert cli.main(["links", "--run", str(tmp_path), "--corpus", str(tmp_path), "--question-id", "chain",
                     "--out", str(tmp_path / "o")]) == 0
    data = json.loads((tmp_path / "o" / "links.json").read_text(encoding="utf-8"))
    assert data["chaining"]["systems"][0]["headline"] == 1.0 and seen[0][0][3:] == (None, None, "chain")


# --- fix round 1 ----------------------------------------------------------------------------------------------------

def rag_fixed(q: RealQuestion, mode: str) -> Answer:
    return Answer(ranking=["A", "B"])


def test_engine_run_on_another_model_is_refused_with_rag(tmp_path: Path) -> None:
    qs = questions(1, fx.write_corpus(tmp_path))
    runs = tmp_path / "runs"
    make_run(runs, "auto-confirmed", "on", qs[0], ["A", "B"], model="other-model")
    with pytest.raises(ValueError, match="other-model"):
        wholerun_cmd.wholerun(qs, runs, tmp_path / "o", set_name="d", left_out="x", reasoning=("on",),
                              confirm=("auto-confirmed",), systems=("engine", "rag"), rag_answer=rag_fixed,
                              rag_model="orch-model")


def test_engine_run_on_other_papers_is_refused_with_rag(tmp_path: Path) -> None:
    qs = questions(1, fx.write_corpus(tmp_path))
    other = fx.write_corpus(tmp_path / "x", corpus_id="other")
    (other / "manifest.json").write_text(json.dumps({"corpus_id": "other", "papers": []}), encoding="utf-8")
    runs = tmp_path / "runs"
    make_run(runs, "auto-confirmed", "on", RealQuestion("q0", "Which 0?", "cs", other, qs[0].gold, "rank"), ["A", "B"])
    with pytest.raises(ValueError, match="same papers"):
        wholerun_cmd.wholerun(qs, runs, tmp_path / "o", set_name="d", left_out="x", reasoning=("on",),
                              confirm=("auto-confirmed",), systems=("engine", "rag"), rag_answer=rag_fixed,
                              rag_model="orch-model")


def test_missing_engine_run_is_a_loss_in_the_pairing_and_tables_show_n(tmp_path: Path) -> None:
    qs = questions(3, fx.write_corpus(tmp_path))
    runs = build(tmp_path, qs)
    shutil.rmtree(runs / "auto-confirmed" / "on" / "q2")
    report = wholerun_cmd.wholerun(qs, runs, tmp_path / "o", set_name="d", left_out="x", reasoning=("on",),
                                   confirm=("auto-confirmed",), systems=("engine", "rag"), rag_answer=rag_fixed,
                                   rag_model="orch-model")
    c = next(x for x in report["comparison"] if x["rag"] == "rag/global")
    assert (c["n"], c["n_missing_run"], c["wins"], c["losses"], c["ties"]) == (3, 1, 0, 1, 2)
    assert c["engine_mean"] == pytest.approx(2 / 3) and c["rag_mean"] == 1.0
    text = (tmp_path / "o" / "wholerun.md").read_text(encoding="utf-8")
    assert "| n |" in text and "missing run" in text and "q2" in text


def test_pairing_uses_the_same_questions_for_both_sides(tmp_path: Path) -> None:
    qs = questions(3, fx.write_corpus(tmp_path))
    report = wholerun_cmd.wholerun(qs, build(tmp_path, qs), tmp_path / "o", set_name="d", left_out="x",
                                   reasoning=("on",), systems=("engine", "rag"), rag_answer=rag_fixed,
                                   rag_model="orch-model")
    hand = next(c for c in report["comparison"] if c["engine"] == "hand-confirmed/on" and c["rag"] == "rag/global")
    assert (hand["n"], hand["n_missing_run"]) == (3, 1) and hand["engine_mean"] == pytest.approx(2 / 3)
    assert hand["rag_mean"] == 1.0   # the same 3 questions on both sides


def test_a_run_without_plan_json_is_scored_zero_and_listed(tmp_path: Path) -> None:
    qs = questions(2)
    runs = tmp_path / "runs"
    make_run(runs, "auto-confirmed", "on", qs[0], ["A", "B"])
    make_run(runs, "auto-confirmed", "on", qs[1], ["A", "B"], plan=False)
    report = wholerun_cmd.wholerun(qs, runs, tmp_path / "o", set_name="d", left_out="x", reasoning=("on",),
                                   confirm=("auto-confirmed",))
    rows = report["rows"]["auto-confirmed/on"]
    assert [r["id"] for r in rows] == ["q0", "q1"] and rows[1]["headline"] == 0.0 and "kendall_tau" not in rows[1]
    assert report["summary"]["auto-confirmed/on"]["n"] == 2 and report["summary"]["auto-confirmed/on"]["n_missing_plan"] == 1
    assert report["missing_plan"] == {"auto-confirmed/on": ["q1"]}
    assert "Missing plan" in (tmp_path / "o" / "wholerun.md").read_text(encoding="utf-8")


def test_answer_key_split_is_recorded_for_every_question_of_a_keyed_set(tmp_path: Path) -> None:
    from evaluation.realpapers import sofc
    q = sofc.questions(DATA / "sofc_tiny")[0]
    runs = tmp_path / "runs"
    make_run(runs, "auto-confirmed", "on", q, ["GDC", "YSZ", "LSM"])
    report = wholerun_cmd.wholerun([q], runs, tmp_path / "o", set_name="sofc", left_out="x", reasoning=("on",),
                                   confirm=("auto-confirmed",))
    got = report["rows"]["auto-confirmed/on"][0]["error_split"]
    assert got in ("right", "synthesis error", "extraction error") or got.startswith("key split failed: ")
    assert report["summary"]["auto-confirmed/on"]["error_split"]
    assert got in (tmp_path / "o" / "wholerun.md").read_text(encoding="utf-8")


def test_set_without_key_records_says_not_available(tmp_path: Path) -> None:
    qs = questions(1)
    report = wholerun_cmd.wholerun(qs, build(tmp_path, qs), tmp_path / "o", set_name="d", left_out="x",
                                   reasoning=("on",), confirm=("auto-confirmed",))
    assert report["rows"]["auto-confirmed/on"][0]["error_split"].startswith("not available")


def test_missing_plan_is_a_loss_in_the_pairing(tmp_path: Path) -> None:
    qs = questions(2, fx.write_corpus(tmp_path))
    runs = tmp_path / "runs"
    make_run(runs, "auto-confirmed", "on", qs[0], ["A", "B"])
    make_run(runs, "auto-confirmed", "on", qs[1], ["A", "B"], plan=False)
    report = wholerun_cmd.wholerun(qs, runs, tmp_path / "o", set_name="d", left_out="x", reasoning=("on",),
                                   confirm=("auto-confirmed",), systems=("engine", "rag"), rag_answer=rag_fixed,
                                   rag_model="orch-model")
    c = next(x for x in report["comparison"] if x["rag"] == "rag/global")
    assert (c["n"], c["n_missing_run"], c["losses"], c["ties"]) == (2, 1, 1, 1)


def test_row_with_every_run_missing_keeps_its_summary_and_comparison(tmp_path: Path) -> None:
    qs = questions(2, fx.write_corpus(tmp_path))
    report = wholerun_cmd.wholerun(qs, tmp_path / "none", tmp_path / "o", set_name="d", left_out="x", reasoning=("on",),
                                   confirm=("auto-confirmed",), systems=("engine", "rag"), rag_answer=rag_fixed,
                                   rag_model="orch-model")
    s = report["summary"]["auto-confirmed/on"]
    assert (s["n"], s["n_missing_run"], s["point"]) == (2, 2, 0.0)
    c = next(x for x in report["comparison"] if x["engine"] == "auto-confirmed/on" and x["rag"] == "rag/global")
    assert (c["n"], c["n_missing_run"], c["engine_mean"], c["losses"]) == (2, 2, 0.0, 2)


def test_cli_missing_corpus_manifest_is_a_clean_error(tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    from evaluation.realpapers import sofc
    q = sofc.questions(DATA / "sofc_tiny")[0]
    runs = tmp_path / "runs"
    make_run(runs, "auto-confirmed", "on", q, ["GDC", "YSZ", "LSM"])
    monkeypatch.setattr(cli, "_model", lambda alias: (object(), alias))
    monkeypatch.setattr("evaluation.baselines.real.rag_real", lambda *a, **k: Answer())
    code = cli.main(["wholerun", "--set", "sofc", "--src", str(DATA / "sofc_tiny"), "--runs", str(runs),
                     "--out", str(tmp_path / "o"), "--confirm", "auto", "--reasoning", "on"])
    assert code == 2 and "evaluate wholerun:" in capsys.readouterr().err


def test_in_set_links_are_left_out_and_counted() -> None:
    inset = link("p1", None, "Lewis et al. (2020)", "p3")            # a corpus paper found without OpenAlex
    got = wholerun_cmd.builds_on_recall([link("p1", "W1", "r"), inset], {"p1": ["W1", "W77"]})
    assert got["n_links"] == 1 and got["n_in_set"] == 1 and got["precision"] == 1.0 and got["recall"] == 0.5
