"""Nothing soft stops a run (Aditya, 22 Nov 2026; review C): one bad call, paper or batch is recorded and skipped."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from paperfactory import cli, config, llm, meta, repair, world
from paperfactory.evaluate import Eval
from paperfactory.tests.test_llm import settings
from paperfactory.tests.test_offline import ARG, LAW, PILOT

SCHEMA = {"type": "object", "required": ["choice"], "properties": {"choice": {"type": "string"}}}


def test_a_call_that_fails_twice_is_skipped_and_logged(tmp_path: Path) -> None:
    s = settings(tmp_path)

    def down(rm, system, user, schema):
        raise llm.LLMError("timed out after 1800s")
    c = llm.Caller(s, backend=down)
    assert c("qa", "qa:Q1", "sys", "u", SCHEMA) is None
    rec = json.loads((s.out_dir / "calls.jsonl").read_text().splitlines()[-1])
    assert rec["transport_error"].startswith("timed out") and rec["parse_error"]


def test_many_failures_in_a_row_mean_the_gateway_is_down(tmp_path: Path) -> None:
    s = settings(tmp_path)
    ok = {"n": 0}

    def flaky(rm, system, user, schema):
        ok["n"] += 1
        if user.startswith("down"):
            raise llm.LLMError("connection refused")
        return {"raw": {"choice": "a"}, "cost_usd": 0.0}
    c = llm.Caller(s, backend=flaky)
    for i in range(llm.TRANSPORT_FAILS_TO_STOP - 1):
        assert c("qa", f"qa:{i}", "sys", f"down {i}", SCHEMA) is None
    assert c("qa", "qa:ok", "sys", "fine", SCHEMA) == {"choice": "a"}        # a success resets the count
    with pytest.raises(llm.GatewayDown):
        for i in range(llm.TRANSPORT_FAILS_TO_STOP):
            c("qa", f"qa:x{i}", "sys", f"down x{i}", SCHEMA)


def test_leak_with_nothing_tagged_is_skipped(tmp_path: Path) -> None:
    s = config.Settings("law", "argument", out=str(tmp_path), leak_trials=5)
    r = Eval(s, PILOT, LAW, {"facts": {}, "questions": []}, call=None).leak({"L-01": {"sentences": [], "spans": {}}})
    assert r["trials"] == 0 and r["skipped"]


def test_a_batch_that_never_passes_keeps_its_good_papers(tmp_path: Path) -> None:
    ents = {"entities": [{"id": k, **v} for k, v in PILOT["entities"].items()]}
    papers = copy.deepcopy(list(PILOT["papers"].values()))
    bad = copy.deepcopy(papers)
    bad[1]["decoys"][0] = [bad[1]["claims"][0][0], "rejects", bad[1]["claims"][0][2]]
    if bad[1]["claims"][0][1] == "rejects":
        bad[1]["decoys"][0][1] = "relies_on"
    seen = []

    def call(role, step, system, user, schema, check=None, cache=True):
        seen.append((step, cache))
        return copy.deepcopy(ents) if step == "world:entities" else {"papers": copy.deepcopy(bad)}
    w = world.draft(config.Settings("law", "argument", papers=3, out=str(tmp_path)), LAW, ARG, call)
    assert list(w["dropped_papers"]) == ["LAW-02"] and sorted(w["papers"]) == ["LAW-01", "LAW-03"]
    assert world.check(w, LAW, ARG, n_papers=2) == []
    assert [c for st, c in seen if "repair" in st] == [False, False]           # repairs never replay the cache


def test_one_paper_that_breaks_the_check_does_not_stop_the_step(tmp_path: Path, monkeypatch) -> None:
    from paperfactory.tests.test_meta import law
    s = law(tmp_path)
    cli.run(s, ["world", "seed", "materials"])
    pids = list(PILOT["papers"])
    for pid in pids:
        (s.out_dir / "work" / pid).mkdir(parents=True)
        (s.out_dir / "work" / pid / "paper.md").write_text("x")
        meta.write_done(s.out_dir / "work" / pid / "paper.md", cli.write_inputs(s, pid, s.out_dir / "template_argument_6p"))

    def fake(self, pid, redo):
        if pid == pids[1]:
            raise KeyError("boom")
        (self.s.out_dir / "work" / pid / "paper.repairs.json").write_text("{}")
        return {"pid": pid, "status": "clean"}
    monkeypatch.setattr(repair.Checker, "repair_paper", fake)
    cli.run(s, ["check"])
    assert [(s.out_dir / "work" / p / "paper.repairs.json").is_file() for p in pids] == [True, False, True]
