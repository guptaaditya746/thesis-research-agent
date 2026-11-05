"""Fix round 1 (runs review C1-C3): the claim grouping cannot kill a run, an unparseable reply is asked again by a
rerun with retry_errors, a rerun with retry_errors replays byte-identically, and an OpenAlex URL that fails then
succeeds in one run replays byte-identically."""
from __future__ import annotations

import json
import urllib.error
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.models.function import FunctionModel

from evidence import planrun, stages
from evidence.plan import write_plan
from evidence.replay import replay
from evidence.rundir import RunDir
from evidence.tests.conftest import prompt_of, provider_of, respond
from evidence.tests.test_plan_run import make_plan, read, stage_reply
from evidence.tests.test_plan_run_failures import corpus, failing_model

GROUPS = "Your output fields are:\n1. `groups`"
CLAIM = "Your output fields are:\n1. `is_claim`"


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    with stages.registered():
        yield


def model(fail: Any = lambda p: False, bad: Any = lambda p: False) -> FunctionModel:
    """The plan-run fake: `fail(prompt)` -> a failed call, `bad(prompt)` -> a reply that does not parse."""
    inner = failing_model(fail).function

    def reply(messages: Any, info: Any) -> Any:
        if bad(prompt_of(messages)):
            return stage_reply(info, "this is not json")
        return inner(messages, info)
    return FunctionModel(reply, model_name="fake")


def run(tmp: Path, m: FunctionModel, *, out: str = "runs", **kw: Any) -> Path:
    path = tmp / "plan.json"
    if not path.is_file():
        write_plan(make_plan(), path)
    cor = tmp / "corpus"
    return planrun.run(path, cor if cor.is_dir() else corpus(tmp), tmp / out, cache=tmp / "cache",
                       selection="regex-only", provider=provider_of(m), workers=1, **kw)


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    from evidence import openalex
    monkeypatch.setattr(openalex, "_urlopen", lambda url: {"results": []})


def claims(root: Path) -> list[Any]:
    return [i for i in RunDir(root).items() if i.evidence_type == "claim"]


def test_a_failed_grouping_call_keeps_the_claims_ungrouped_and_the_run_completes(tmp_path: Path) -> None:
    root = run(tmp_path, model(fail=lambda p: GROUPS in p))
    assert RunDir(root).complete
    assert read(root, "stage_report.json")["groups"]["run"][0].startswith("unchecked: claim groups: StageCallError")
    assert claims(root) and all(c.fields["relation_group"] == "other: improves" for c in claims(root))
    _, report = replay(root)
    assert report["ok"], report


def test_an_unparseable_grouping_reply_is_asked_again_by_a_retry_errors_rerun(tmp_path: Path) -> None:
    first = run(tmp_path, model(bad=lambda p: GROUPS in p))
    assert RunDir(first).complete
    assert read(first, "stage_report.json")["groups"]["run"][0].startswith("unchecked: claim groups: AdapterParseError")
    plain = run(tmp_path, model(), out="plain")      # without retry_errors the recorded bad reply is used again
    assert read(plain, "stage_report.json")["groups"]
    again = run(tmp_path, model(), out="again", retry_errors=True)
    assert read(again, "stage_report.json")["groups"] == {}
    assert {c.fields["relation_group"] for c in claims(again)} == {"better"}
    for root in (first, again):
        _, report = replay(root)
        assert report["ok"] and report["mismatched"] == [], report


def test_a_retry_errors_rerun_replays_byte_identical(tmp_path: Path) -> None:
    first = run(tmp_path, model(fail=lambda p: CLAIM in p))
    assert any(read(first, "stage_report.json")["claims"].values())
    again = run(tmp_path, model(), out="again", retry_errors=True)
    assert read(again, "stage_report.json")["claims"] == {} and claims(again)
    _, report = replay(again)
    assert report["ok"] and report["mismatched"] == [], report
    _, report = replay(first)          # the first run still replays its own (failed) attempts
    assert report["ok"] and report["mismatched"] == [], report


def test_an_openalex_url_that_fails_then_succeeds_replays_byte_identical(tmp_path: Path,
                                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    from evidence import openalex
    asked: list[str] = []

    def flaky(url: str) -> Any:
        asked.append(url)
        if len(asked) == 1:
            raise urllib.error.HTTPError(url, 500, "Internal Server Error", {}, None)  # type: ignore[arg-type]  # a 503 is retried (with_backoff); a 500 is not
        return {"results": [{"id": "https://openalex.org/W1", "title": "Lewis et al. (2020)"}]}
    monkeypatch.setattr(openalex, "_urlopen", flaky)
    root = run(tmp_path, model())
    links = read(root, "answer.json")["links"]
    assert len(links) >= 2 and len({x["ref"] for x in links}) == 1      # every paper cites the same work
    assert {x.get("resolve_failed") for x in links} == {"HTTP 500"}     # sticky for the run
    _, report = replay(root)
    assert report["ok"] and report["mismatched"] == [], report
    assert json.loads(json.dumps(links))
