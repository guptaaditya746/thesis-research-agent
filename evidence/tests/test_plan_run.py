"""Plan runs (Wave 2 Task 8.1): one confirmed plan run end to end over the fixture corpus with a recorded fake model;
the replay is byte-identical and asks no model; a protocol run is unchanged."""
from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.models.function import FunctionModel

from evidence import cli, engine, planrun, stages
from evidence.kg.query import template
from evidence.plan import Decision, EvidenceLine, Plan, WordList, write_plan
from evidence.planner.plan import OVERSELL_QUERY
from evidence.replay import replay
from evidence.rundir import RunDir
from evidence.tests.conftest import PROTOCOL, make_corpus, provider_of, prompt_of, respond
from evidence.words.compile import compile_words
from jsonio import sha256_hex

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden" / "regex_run_outputs.json"
WHO = {"confirmed_by": "aditya", "confirmed_at": "2026-11-03T10:00:00+00:00"}
FRESH = """SELECT ?paper (COUNT(?v) AS ?values) WHERE {
  ?v a ev:Value ; ev:inExperiment ?e . ?e ev:inPaper ?p . ?p ev:name ?paper .
} GROUP BY ?paper ORDER BY ?paper"""
# parses (the planner's check_plan accepts it) but fails when it runs: its after-step does not exist
BROKEN = "# after: no_such_step\nSELECT ?x WHERE { ?x a ev:Value }"


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    with stages.registered():
        yield


def make_plan(field: str = "cs", things: dict[str, list[str]] | None = None, measures: tuple[str, ...] = ("accuracy",),
              direction: str = "higher") -> Plan:
    things = things or {"rag": ["retrieval-augmented model", "retrieval-augmented generation", "retrieval augmentation"],
                        "closed_book": ["closed-book model", "closed-book"],
                        "accuracy": ["answer accuracy", "accuracy"]}
    return Plan(
        question="Does retrieval-augmented generation improve answer accuracy?", field=field,  # type: ignore[arg-type]
        lines=[EvidenceLine(id="l1", question="Is the retrieval-augmented model more accurate?", query=template("effect"),
                            template="effect"),
               EvidenceLine(id="l2", question="Which papers report values?", query=FRESH, template=None,
                            how=["It counts the values each paper reports."]),
               EvidenceLine(id="l3", question="A line whose query breaks?", query=BROKEN, template=None),
               EvidenceLine(id="oversell", question="Do the authors' conclusions match their numbers?",
                            query=OVERSELL_QUERY, template=None, removable=False)],
        main_rule="any_line",
        words=WordList(things=things, cues=["improves: improves", "worsens: hurts", "no_effect: no improvement"],
                       written_by="orch-model", ontology_names={}),
        decisions=[Decision(id="d1", type="threshold", value="0.01", reason="noise", **WHO),
                   Decision(id="d2", type="counts_as", value="accuracy", reason="the measure", **WHO),
                   *[Decision(id=f"direction:{m}", type="direction", value=direction, reason="its direction", **WHO)
                     for m in measures],
                   Decision(id="main_rule", type="main_rule", value="any_line", reason="any line", **WHO)],
        clarifications=[], measures=list(measures))


def fake_model(calls: list[str]) -> FunctionModel:
    """Replies to the stages' DSPy steps (the first output field names the step) and to plain asks."""
    def reply(messages: Any, info: Any) -> Any:
        prompt = prompt_of(messages)
        calls.append(prompt)
        field = re.search(r"Your output fields are:\s*1\. `(\w+)`", prompt)
        name = field.group(1) if field else ""
        if name == "verdicts":
            out: dict[str, Any] = {"verdicts": []}
        elif name == "experiments":
            quote = "Both conditions use the same 7B language model"
            out = {"experiments": [{"label": "7B model", "quote": quote, "setting": {"model": "7B"}}]
                   if quote in prompt else []}
        elif name == "is_claim":
            out = {"is_claim": True, "subject": "retrieval augmentation", "relation": "improves",
                   "object": "answer accuracy", "setting": {}, "strength": "firm", "direction": "improves"}
        elif name == "groups":
            out = {"groups": {"better": ["improves"]}}
        elif name == "parent":
            out = {"parent": ""}
        elif name == "relation":
            out = {"relation": "", "object": None}
        else:
            out = {}
        return respond(info, {"text": json.dumps(out)})
    return FunctionModel(reply, model_name="fake")


def plan_run(tmp_path: Path, plan: Plan | None = None, calls: list[str] | None = None) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "plan.json"
    write_plan(plan or make_plan(), path)
    corpus = tmp_path / "corpus"
    if not corpus.exists():
        make_corpus(corpus)
    return planrun.run(path, corpus, tmp_path / "runs", cache=tmp_path / "cache", selection="regex-only",
                       provider=provider_of(fake_model(calls if calls is not None else [])), workers=1)


def read(root: Path, name: str) -> Any:
    return json.loads((root / name).read_text(encoding="utf-8"))


def test_plan_run_end_to_end_fake_lm(tmp_path: Path) -> None:
    from evidence.planner import check_plan
    assert check_plan(make_plan()) == []   # a plan the planner's own checks (and the page) accept
    calls: list[str] = []
    root = plan_run(tmp_path, calls=calls)
    run = read(root, "run.json")
    assert run["settings"]["stage_set"] == "plan"
    assert run["stages"] == {"before_extract": ["map-experiments"], "after_type": ["recheck"],
                             "after_document": ["experiment-items", "claims", "links"],
                             "after_run": ["recheck_report", "stage_report", "ontology"]}
    # the protocol is written from the plan: the screen terms are the compiled word list, a miss goes to the model
    protocol = (root / "protocol.yaml").read_text(encoding="utf-8")
    words = compile_words(make_plan().words, metric_things={"accuracy"})
    assert "lexical_miss: escalate" in protocol and all(t in protocol for t in words["screen_terms"])
    assert "factual_accuracy" not in protocol and "hallucination" not in protocol   # no pack words
    lock = read(root, "protocol.lock.json")
    assert {"plan_sha256", "words_sha256", "field_ontology_sha256"} <= set(lock)
    # records graph, every output hashed
    for name in ("records.nq", "answer.json", "ontology.json", "recheck_report.json", "stage_report.json"):
        assert run["outputs"][name] == sha256_hex((root / name).read_bytes())
    assert b"https://w3id.org/thesis-ev#Value" in (root / "records.nq").read_bytes()
    answer = read(root, "answer.json")
    lines = {x["id"]: x for x in answer["lines"]}
    assert lines["l1"]["status"] == "done" and {r["direction"] for r in lines["l1"]["rows"]} >= {"supports"}
    assert lines["l2"]["rows"] and lines["l3"]["status"] == "failed" and lines["l3"]["text"].startswith("failed: ")
    assert answer["answer"]["missing"] == ["missing: A line whose query breaks?"]
    assert "missing: A line whose query breaks?" in answer["answer"]["text"] and answer["answer"]["rule_met"]
    assert set(answer["labels"]) >= {"l1", "l2", "oversell"} and answer["reruns"]
    assert any(r["line"] == "l1" and r["decision"] == "d1" for r in answer["reruns"])
    assert answer["synthesis"]["counts"]["supporting"] >= 1     # the kind's answer is kept
    assert answer["claim_groups"]["mapping"] == {"improves": "better"}
    items = RunDir(root).items()
    claims = [i for i in items if i.evidence_type == "claim"]
    assert claims and all(i.fields["relation_group"] == "better" for i in claims)
    assert any(i.evidence_type == "experiment" for i in items)
    assert read(root, "ontology.json")["tree"] in ("ontology tree", "made by LLM")
    assert any("`verdicts`" in c for c in calls) and any("`experiments`" in c for c in calls)


def test_plan_run_replay_identical(tmp_path: Path) -> None:
    calls: list[str] = []
    root = plan_run(tmp_path, calls=calls)
    made = len(calls)
    (tmp_path / "plan.json").unlink()   # the replay reads the run's own copy
    new, report = replay(root)
    assert report["ok"] and report["mismatched"] == [], report
    assert read(new, "run.json")["outputs"] == read(root, "run.json")["outputs"]
    assert len(calls) == made                                    # no model call in the replay
    assert read(new, "run.json")["cost"]["made_model_calls"] == 0


def test_protocol_run_unchanged(tmp_path: Path) -> None:
    plan_run(tmp_path / "plan")   # a plan run first, in the same process: its stages must not leak
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["gaps"]
    root = engine.run(PROTOCOL, make_corpus(tmp_path / "corpus"), tmp_path / "runs", selection="regex-only",
                      strategy="gaps", cache=tmp_path / "cache", provider=None)
    run = read(root, "run.json")
    assert "stages" not in run and "stage_set" not in run["settings"]
    assert run["outputs"] == golden
    assert stages.names() == {}


def test_a_plan_whose_words_match_nothing_answers_no_evidence_found(tmp_path: Path) -> None:
    plan = make_plan(things={"zork": ["zorkulator"], "blip": ["bliposcope"], "accuracy": ["quuxness"]})
    root = plan_run(tmp_path, plan)
    answer = read(root, "answer.json")
    assert answer["answer"]["text"].startswith("No evidence found")
    assert {x["text"] for x in answer["lines"] if x["status"] == "done"} == {"No evidence found"}


def test_a_field_without_ontology_says_reasoning_off_and_finishes(tmp_path: Path) -> None:
    root = plan_run(tmp_path, make_plan(field="other"))
    assert read(root, "ontology.json")["tree"] == "reasoning off: no tree"
    assert RunDir(root).complete


def test_an_unconfirmed_plan_is_refused(tmp_path: Path) -> None:
    plan = make_plan()
    plan = plan.model_copy(update={"decisions": [plan.decisions[0].model_copy(update={"confirmed_by": None}),
                                                 *plan.decisions[1:]]})
    with pytest.raises(ValueError, match="confirm"):
        plan_run(tmp_path, plan)


def test_cli_runs_a_plan_and_refuses_plan_with_protocol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "plan.json"
    write_plan(make_plan(), path)
    corpus = make_corpus(tmp_path / "corpus")
    monkeypatch.setattr(engine, "default_provider", provider_of(fake_model([])))
    assert cli.main(["run", "--plan", str(path), "--corpus", str(corpus), "--out", str(tmp_path / "runs"),
                     "--extractors", "regex-only", "--workers", "1"]) == 0
    assert cli.main(["run", "--plan", str(path), "--protocol", str(PROTOCOL), "--corpus", str(corpus),
                     "--out", str(tmp_path / "runs2")]) == 2


def test_builds_on_links_are_recorded_and_the_replay_reads_the_recorded_openalex_answers(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from evidence import openalex
    from evidence.tests.conftest import PAPERS, corpus_of
    fetched: list[str] = []
    monkeypatch.setattr(openalex, "_urlopen", lambda url: fetched.append(url) or {"results": []})
    docs = {d: (PAPERS / f"{d}.md").read_text(encoding="utf-8").replace("\r\n", "\n") for d in ("S001", "S002")}
    docs["S001"] += "\n\nWe build on Lewis et al. (2020) for the retrieval-augmented model.\n"
    corpus_of(tmp_path / "corpus", docs)
    calls: list[str] = []
    model = fake_model(calls)
    inner = model.function

    def reply(messages: Any, info: Any) -> Any:
        prompt = prompt_of(messages)
        if "Your output fields are:\n1. `relation`" in prompt and "Lewis et al." in prompt:
            calls.append(prompt)
            return respond(info, {"text": json.dumps({"relation": "builds on", "object": "Lewis et al. (2020)"})})
        return inner(messages, info)

    path = tmp_path / "plan.json"
    write_plan(make_plan(), path)
    root = planrun.run(path, tmp_path / "corpus", tmp_path / "runs", cache=tmp_path / "cache", selection="regex-only",
                       provider=provider_of(FunctionModel(reply, model_name="fake")), workers=1)
    links = read(root, "answer.json")["links"]
    assert links == [{"paper": "S001", "relation": "builds on", "ref": "Lewis et al. (2020)", "in_set": None,
                      "text": "outside the set"}]
    assert (root / "openalex.jsonl").is_file() and fetched
    n = len(fetched)
    new, report = replay(root)
    assert report["ok"], report
    assert len(fetched) == n          # the replay read the recorded answers, never the network


def test_a_plan_run_scores_through_the_wholerun_adapter(tmp_path: Path) -> None:
    from evaluation.wholerun import RealQuestion, from_run, score
    root = plan_run(tmp_path)
    q = RealQuestion("q", "Does it help?", "cs", tmp_path / "corpus", {"directions": {"S001": "improves"},
                                                                         "conclusion": "improves"}, "compare")
    answer = from_run(root, q)
    assert answer.directions.get("S001") == "improves"
    assert score(answer, q)["per_study"] == {"S001": 1}
    claims = from_run(root, RealQuestion("c", "?", "cs", tmp_path, {"conclusions": [{"id": "R1", "direction": "improves"}]},
                                         "claims"))
    assert claims.claims == [{"about": "R1", "direction": "improves"}]


def test_rerun_verdict_of_an_effect_line_is_its_majority_direction() -> None:
    from evidence.kg.query import Answer
    rows = [{"paper": "a", "direction": "supports"}, {"paper": "b", "direction": "supports"},
            {"paper": "c", "direction": "contradicts"}, {"paper": "d", "direction": "undetermined"}]
    v = planrun.verdict(Answer(rows=rows, empty=False))
    assert (v.label, v.n) == ("supports", 3) and v.size == pytest.approx(2 / 3)
    tie = planrun.verdict(Answer(rows=rows[1:3], empty=False))
    assert tie.label == "mixed"
    assert planrun.verdict(Answer(rows=[{"thing": "x", "score": 1}], empty=False)).label == "x"


def test_a_fresh_query_the_planner_writes_runs_to_a_non_empty_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from evidence import steps
    from evidence.planner import check_plan, confirm_all, propose
    from modelcall.dspy_lm import RecordedLM
    fresh = ("SELECT DISTINCT ?paper WHERE { ?v a ev:Value ; kg:side ?s ; ev:onMetric ?m ; ev:inExperiment ?e . "
             "?m ev:name ?metric . ?e ev:inPaper ?p . ?p ev:name ?paper . VALUES ?s { $sides } "
             "VALUES ?metric { $metrics } } ORDER BY ?paper")
    replies = [{"lines": [{"question": "Which papers compare the two on accuracy?", "kind": "inventory", "template": None}]},
               {"field": "cs", "things": ["rag", "closed_book", "accuracy"], "measures": ["accuracy"], "lower_is_better": []},
               {"rule": "any_line"}, {"decisions": []}, {"query": fresh}, {"sentences": ["It lists papers."]}]
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    with steps.using(RecordedLM("fake", lambda prompt: json.dumps(replies.pop(0)))):
        plan, _ = propose("Does retrieval-augmented generation improve answer accuracy?",
                          write_words=lambda q, things: make_plan().words)
    plan = confirm_all(plan, "aditya")
    assert check_plan(plan) == [] and plan.lines[0].query == fresh
    root = plan_run(tmp_path, plan)
    line = read(root, "answer.json")["lines"][0]
    assert line["status"] == "done" and {r["paper"] for r in line["rows"]} >= {"S001"}


def test_a_one_method_question_compares_with_other_and_its_effect_line_runs(tmp_path: Path) -> None:
    plan = make_plan(things={"rag": ["retrieval-augmented model", "retrieval-augmented generation"],
                             "accuracy": ["answer accuracy", "accuracy"]})
    assert planrun.compare_sides(plan) == ["rag", "other"]
    assert planrun.line_params(plan, plan.lines[0].query)["sides"] == ["rag", "other"]
    root = plan_run(tmp_path, plan)
    lines = {x["id"]: x for x in read(root, "answer.json")["lines"]}
    assert lines["l1"]["status"] == "done"


def test_a_lower_is_better_measure_reads_a_rise_as_worse(tmp_path: Path) -> None:
    """"Does retrieval reduce latency?": S001 has latency 655 ms with retrieval, 410 ms without: that is worse."""
    things = {"rag": ["retrieval-augmented model", "retrieval-augmented generation"],
              "closed_book": ["closed-book model", "closed-book"], "latency": ["latency"]}
    plan = make_plan(things=things, measures=("latency",), direction="lower")
    plan = plan.model_copy(update={"question": "Does retrieval-augmented generation reduce latency?", "decisions": [
        d.model_copy(update={"value": "latency"}) if d.type == "counts_as" else d for d in plan.decisions]})
    assert planrun.directions(plan) == {"latency": False}
    assert "higher_is_better: false" in planrun.protocol_for(plan).decode()
    root = plan_run(tmp_path, plan)
    rows = {r["paper"]: r for r in {x["id"]: x for x in read(root, "answer.json")["lines"]}["l1"]["rows"]}
    assert rows["S001"]["direction"] == "contradicts"
    higher = make_plan(things=things, measures=("latency",), direction="higher")
    higher = higher.model_copy(update={"decisions": [d.model_copy(update={"value": "latency"}) if d.type == "counts_as"
                                                     else d for d in higher.decisions]})
    rows = {r["paper"]: r for r in {x["id"]: x for x in read(plan_run(tmp_path / "h", higher), "answer.json")["lines"]}["l1"]["rows"]}
    assert rows["S001"]["direction"] == "supports"


def test_a_measure_without_a_direction_decision_takes_the_extracted_metrics_direction() -> None:
    from evidence.contract import Item, Span
    plan = make_plan(measures=("accuracy",))
    plan = plan.model_copy(update={"decisions": [d for d in plan.decisions if d.type != "direction"]})
    span = Span(role="metric_label", selector={"file": "p.md", "start": 0, "end": 3, "exact": "x", "sha256": "0" * 64})
    lower = Item.build("metric", {"name": "err", "canonical": "accuracy", "higher_is_better": False}, [span])
    assert planrun.directions(plan) == {"accuracy": None}
    assert planrun.directions(plan, {"S1": [lower]}) == {"accuracy": False}


def test_a_word_list_from_another_model_is_refused(tmp_path: Path) -> None:
    plan = make_plan()
    plan = plan.model_copy(update={"words": plan.words.model_copy(update={"written_by": "claude-haiku"})})
    with pytest.raises(planrun.PlanNotRunnable, match="orch-model"):
        plan_run(tmp_path, plan)


def test_cli_refuses_flags_a_plan_run_fixes(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    write_plan(make_plan(), path)
    assert cli.main(["run", "--plan", str(path), "--corpus", str(make_corpus(tmp_path / "c")), "--out",
                     str(tmp_path / "r"), "--names", "on"]) == 2
