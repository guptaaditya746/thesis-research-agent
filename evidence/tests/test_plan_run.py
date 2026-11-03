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
BROKEN = "SELECT ?x WHERE { ?x a ev:Value . FILTER(?x > }"


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    with stages.registered():
        yield


def make_plan(field: str = "cs", things: dict[str, list[str]] | None = None) -> Plan:
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
                   Decision(id="main_rule", type="main_rule", value="any_line", reason="any line", **WHO)],
        clarifications=[], measures=["accuracy"])


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
    calls: list[str] = []
    root = plan_run(tmp_path, calls=calls)
    run = read(root, "run.json")
    assert run["settings"]["stage_set"] == "plan"
    assert run["stages"] == {"before_extract": ["map-experiments"], "after_type": ["recheck"],
                             "after_document": ["experiment-items", "claims", "links"],
                             "after_run": ["recheck_report", "ontology"]}
    # the protocol is written from the plan: the screen terms are the compiled word list, a miss goes to the model
    protocol = (root / "protocol.yaml").read_text(encoding="utf-8")
    words = compile_words(make_plan().words, metric_things={"accuracy"})
    assert "lexical_miss: escalate" in protocol and all(t in protocol for t in words["screen_terms"])
    assert "factual_accuracy" not in protocol and "hallucination" not in protocol   # no pack words
    lock = read(root, "protocol.lock.json")
    assert {"plan_sha256", "words_sha256", "field_ontology_sha256"} <= set(lock)
    # records graph, every output hashed
    for name in ("records.nq", "answer.json", "ontology.json", "recheck_report.json"):
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
