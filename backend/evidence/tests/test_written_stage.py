"""The written answer as a stage of the plan run (evidence/written.py `written_stage`): fake writer model, recorded
calls, replay, one repair, a failed call, no fact, a later try, a plan that answers by lines."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.models.function import FunctionModel

from evidence import planrun, stages
from evidence.plan import Plan, with_answer, write_plan
from evidence.replay import replay
from evidence.rundir import RunDir
from evidence.tests.conftest import make_corpus, prompt_of, provider_of, respond
from evidence.tests.test_plan_run import fake_model, make_plan, plan_run
from evidence.written import NO_FACTS_TEXT

Reply = Callable[[str], Any]


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    with stages.registered():
        yield


def writer_model(calls: list[str], reply: Reply, infos: list[Any] | None = None,
                 others: list[str] | None = None) -> FunctionModel:
    """The writer call is told apart by its instructions; every other call goes to test_plan_run's fake (its prompts
    kept in `others` when given)."""
    other = fake_model(others if others is not None else [])

    def fn(messages: Any, info: Any) -> Any:
        if "Write a short answer to the question" in (info.instructions or ""):
            prompt = prompt_of(messages)
            calls.append(prompt)
            if infos is not None:
                infos.append(info)
            out = reply(prompt)
            if isinstance(out, Exception):
                raise out
            return respond(info, out)
        return other.function(messages, info)
    return FunctionModel(fn, model_name="fake")


def written_run(tmp_path: Path, reply: Reply, plan: Plan | None = None, calls: list[str] | None = None,
                infos: list[Any] | None = None, others: list[str] | None = None) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "plan.json"
    write_plan(plan or with_answer(make_plan(), "written", None), path)
    corpus = tmp_path / "corpus"
    if not corpus.exists():
        make_corpus(corpus)
    n = len(list((tmp_path / "runs").glob("*"))) if (tmp_path / "runs").exists() else 0
    return planrun.run(path, corpus, tmp_path / "runs", cache=tmp_path / "cache", selection="regex-only",
                       provider=provider_of(writer_model(calls if calls is not None else [], reply, infos, others)),
                       workers=1, run_id=f"w{n}")


def read(root: Path, name: str) -> Any:
    return json.loads((root / name).read_text(encoding="utf-8"))


GOOD: Reply = lambda p: {"sentences": [{"text": "Retrieval helped.", "says": "finding", "facts": [1]}]}


def test_a_written_plan_run_writes_the_answer_and_replays(tmp_path: Path) -> None:
    root = written_run(tmp_path, GOOD)
    out, run = read(root, "written-answer.json"), read(root, "run.json")
    assert out["status"] == "ok" and out["answer_text"].startswith("Retrieval helped (")
    assert out["cut"]["kept"] == len(out["facts"]) >= 1 and len(out["tries"]) == 1
    assert run["stages"]["after_run"][-1] == "written-answer" and "written-answer.json" in run["outputs"]
    (tmp_path / "plan.json").unlink()
    _, report = replay(root)
    assert report["ok"] and report["mismatched"] == []


def test_a_bad_reply_gets_one_repair_with_its_problem(tmp_path: Path) -> None:
    calls: list[str] = []
    replies = iter([{"sentences": [{"text": "Up 987654%.", "says": "finding", "facts": [1]}]},
                    {"sentences": [{"text": "Retrieval helped.", "says": "finding", "facts": [1]}]}])
    out = read(written_run(tmp_path, lambda p: next(replies), calls=calls), "written-answer.json")
    assert out["status"] == "ok" and len(out["tries"]) == 2 and len(calls) == 2
    assert out["tries"][0]["problems"] == ["sentence 1: the number 987654 is in none of its facts"]
    assert "the number 987654" in calls[1] and calls[1].startswith("Question: ")


def test_two_bad_replies_leave_an_empty_failed_answer(tmp_path: Path) -> None:
    out = read(written_run(tmp_path, lambda p: {"sentences": []}), "written-answer.json")
    assert out["status"] == "failed" and out["answer_text"] == "" and out["problems"] == ["give 1 to 8 sentences"]
    assert [t["problems"] for t in out["tries"]] == [["give 1 to 8 sentences"]] * 2


def test_a_failed_call_is_recorded_and_the_run_completes(tmp_path: Path) -> None:
    root = written_run(tmp_path, lambda p: RuntimeError("gateway down"))
    assert set(read(root, "written-answer.json")) == {"failed"} and RunDir(root).complete


def test_a_later_try_is_a_new_call(tmp_path: Path) -> None:
    calls: list[str] = []
    infos: list[Any] = []
    written_run(tmp_path / "a", GOOD, calls=calls)
    tried = with_answer(make_plan(), "written", None).model_copy(update={"writer_try": 1})
    root = written_run(tmp_path / "a", GOOD, plan=tried, calls=calls, infos=infos)   # same record cache folder
    assert len(calls) == 2
    assert read(root, "written-answer.json")["writer_try"] == 1


def test_a_later_try_reuses_the_extractions_and_asks_the_writer_once(tmp_path: Path) -> None:
    written_run(tmp_path, GOOD)   # try 0 fills the shared record cache
    tried = with_answer(make_plan(), "written", None).model_copy(update={"writer_try": 1})
    writer: list[str] = []
    others: list[str] = []
    root = written_run(tmp_path, GOOD, plan=tried, calls=writer, others=others)
    assert len(writer) == 1 and others == []   # one new writer call, no other model call
    first, second = (tmp_path / "runs" / "w0"), root
    assert (second / "protocol.yaml").read_bytes() == (first / "protocol.yaml").read_bytes()
    events = [json.loads(line) for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
    made = [e for e in events if e["subtype"] == "extractor_call" and e["status"] != "skipped"]
    assert made and all(e["custom_metadata"]["source"] == "cache" for e in made)   # zero new extractor calls
    (tmp_path / "plan.json").unlink()
    _, report = replay(root)   # the replay asks no model (provider None: a miss raises NotRecorded)
    assert report["ok"] and report["mismatched"] == []


def test_a_later_try_asks_at_temperature_03(tmp_path: Path) -> None:
    tried = with_answer(make_plan(), "written", None).model_copy(update={"writer_try": 1})
    infos: list[Any] = []
    written_run(tmp_path, GOOD, plan=tried, infos=infos)
    assert infos and all(i.model_settings["temperature"] == 0.3 and i.model_settings["seed"] == 1 for i in infos)


def test_a_question_number_in_a_cannot_tell_sentence_needs_no_repair(tmp_path: Path) -> None:
    calls: list[str] = []
    plan = with_answer(make_plan(), "written", None).model_copy(
        update={"question": "Does retrieval help answer accuracy in 2023?"})
    reply = {"sentences": [{"text": "Nothing says how it went in 2023.", "says": "cannot_tell", "facts": []}]}
    out = read(written_run(tmp_path, lambda p: reply, plan=plan, calls=calls), "written-answer.json")
    assert out["status"] == "ok" and len(out["tries"]) == 1 and len(calls) == 1


def test_no_fact_means_no_call(tmp_path: Path) -> None:
    calls: list[str] = []
    nothing = with_answer(make_plan(things={"zz": ["no such words anywhere"], "yy": ["nor these"]}, measures=()),
                          "written", None)
    out = read(written_run(tmp_path, lambda p: {"sentences": []}, plan=nothing, calls=calls), "written-answer.json")
    assert out["status"] == "no_facts" and out["answer_text"] == NO_FACTS_TEXT and calls == []


def test_a_lines_plan_has_todays_stages(tmp_path: Path) -> None:
    root = plan_run(tmp_path)
    assert "written-answer" not in read(root, "run.json")["stages"]["after_run"]
