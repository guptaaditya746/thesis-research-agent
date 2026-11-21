"""S4 runner with stub steps: files per question, events with timing and LLM counts, resume, closed book, failures."""
from __future__ import annotations

import json
from pathlib import Path

import dspy
import pytest
import yaml

from evqa import corpus, lm
from evqa import run as runner
from evqa.contracts import Answer, FindHit, Name, Passage, Row, RunConfig, Spec, read_jsonl

QUESTIONS = [{"qid": f"Q{i}", "type": "lookup", "question": f"question {i}", "intent_card": []} for i in range(1, 5)]


class Sig(dspy.Signature):
    """Say hi."""
    x: str = dspy.InputField()
    y: str = dspy.OutputField()


def llm_call() -> None:
    """One recorded LM request made the way the steps make theirs."""
    m = lm.make_lm(RunConfig().llm, ask=lambda t: json.dumps({"y": "hi"}))
    with dspy.context(lm=m, adapter=dspy.JSONAdapter()):
        dspy.Predict(Sig)(x="a")


@pytest.fixture
def stubs(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "CACHE_FILE", tmp_path / "cache.jsonl")
    monkeypatch.setattr(lm, "_caches", {})
    monkeypatch.setattr(corpus, "questions", lambda domain, split: QUESTIONS)
    called: dict[str, list[str]] = {"spec": [], "find": [], "extract": [], "link": [], "answer": []}
    fail: set[str] = set()

    def spec(q, cfg):
        called["spec"].append(q["qid"])
        llm_call()
        return Spec(qid=q["qid"], question=q["question"], type="lookup", subjects=[Name(label="d")],
                    measure=Name(label="m")).seal()

    def find(spec, domain, cfg):
        called["find"].append(spec.qid)
        if spec.qid in fail:
            raise RuntimeError("find broke")
        return [FindHit(paper="P1", passages=[Passage(start=0, end=3, text="abc")])]

    def extract(spec, hits, domain, cfg, audit=None):
        called["extract"].append(spec.qid)
        return [Row(paper="P1", subject="d", measure="m", raw="-1", quote="abc")]

    def link(spec, rows, cfg):
        called["link"].append(spec.qid)
        return []

    def answer(spec, rows, links=None):
        called["answer"].append(spec.qid)
        return Answer(qid=spec.qid, type="lookup", not_reported=not rows)

    steps = {"spec": spec, "find": find, "extract": extract, "extract.links": link, "answer": answer}
    monkeypatch.setattr(runner, "_step", lambda name: steps[name])
    return called, fail


def events(folder: Path) -> list[dict]:
    return [json.loads(x) for x in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_run_writes_every_file_and_event(stubs, tmp_path) -> None:
    called, _ = stubs
    cfg = RunConfig(name="t", questions=["Q1", "Q3"])
    out = runner.run(cfg, root=tmp_path / "runs")
    assert out.name == cfg.run_id()
    assert RunConfig.model_validate(yaml.safe_load((out / "config.yaml").read_text())) == cfg
    for qid in ("Q1", "Q3"):
        assert Spec.model_validate_json((out / qid / "spec.json").read_text()).qid == qid
        assert len(read_jsonl(out / qid / "find.jsonl", FindHit)) == 1
        assert len(read_jsonl(out / qid / "rows.jsonl", Row)) == 1
        assert Answer.model_validate_json((out / qid / "answer.json").read_text()).not_reported is False
    assert not (out / "Q2").exists() and sorted(called["answer"]) == ["Q1", "Q3"]
    ev = events(out)
    ends = [e for e in ev if e["kind"] == "end" and e["step"] == "spec"]
    assert len(ends) == 2 and all(e["data"]["llm"]["requests"] == 1 and "seconds" in e["data"] for e in ends)
    assert sum(e["data"]["llm"].get("calls", 0) for e in ends) == 1      # same prompt: the second is a cache hit
    assert ev[-1]["step"] == "run" and ev[-1]["data"]["answered"] == 2 and ev[-1]["data"]["failed"] == []


def test_rerun_resumes_and_skips_done_steps(stubs, tmp_path) -> None:
    called, _ = stubs
    cfg = RunConfig(name="t")
    out = runner.run(cfg, root=tmp_path)
    (out / "Q2" / "answer.json").unlink()
    (out / "Q4" / "rows.jsonl").unlink()
    for v in called.values():
        v.clear()
    runner.run(cfg, root=tmp_path)
    assert called["spec"] == [] and called["find"] == [] and called["extract"] == ["Q4"]
    assert sorted(called["answer"]) == ["Q2", "Q4"]
    assert any(e["kind"] == "info" and e["data"]["skipped"] for e in events(out))


def test_closed_book_calls_no_find_and_answers_not_reported(stubs, tmp_path) -> None:
    called, _ = stubs
    out = runner.run(RunConfig(name="cb", closed_book=True, questions=["Q1"]), root=tmp_path)
    assert called["find"] == [] and called["extract"] == []
    assert (out / "Q1" / "find.jsonl").read_text() == ""
    assert Answer.model_validate_json((out / "Q1" / "answer.json").read_text()).not_reported


def test_a_failing_question_does_not_stop_the_others(stubs, tmp_path) -> None:
    called, fail = stubs
    fail.add("Q2")
    out = runner.run(RunConfig(name="f"), root=tmp_path)
    assert not (out / "Q2" / "find.jsonl").exists() and (out / "Q2" / "spec.json").exists()
    assert sorted(called["answer"]) == ["Q1", "Q3", "Q4"]
    ev = events(out)
    assert any(e["kind"] == "problem" and e["qid"] == "Q2" and "find broke" in e["data"]["error"] for e in ev)
    assert ev[-1]["data"]["failed"] == ["Q2"]


def test_unknown_question_id_is_refused(stubs, tmp_path) -> None:
    with pytest.raises(ValueError, match="Q9"):
        runner.run(RunConfig(name="x", questions=["Q9"]), root=tmp_path)


def test_cli_hook(stubs, tmp_path, monkeypatch) -> None:
    import argparse
    conf = tmp_path / "c.yaml"
    conf.write_text("name: cli\nquestions: [Q1]\n")
    monkeypatch.setattr(runner, "ROOT", tmp_path / "runs")
    parser = argparse.ArgumentParser()
    runner.add_cli(parser.add_subparsers())
    a = parser.parse_args(["run", "--config", str(conf)])
    assert a.fn(a) == 0
    assert (tmp_path / "runs" / RunConfig.load(conf).run_id() / "Q1" / "answer.json").is_file()


def test_steps_see_only_the_allowed_question_keys(stubs, tmp_path, monkeypatch) -> None:
    """Leak guard: a record carrying type, answerable, gold, why or closest facts reaches Spec stripped of them."""
    leaky = [{"qid": "Q1", "question": "question 1", "type": "near_miss", "answerable": False, "split": "test",
              "intent_text": "x", "why": "no paper", "near": ["R-1"], "template": "t", "gold": {"table": []},
              "intent_card": [{"point": "dose", "label": "dose", "ask": "Which dose?", "answer": "every dose",
                               "why": "leak"}]}]
    monkeypatch.setattr(corpus, "questions", lambda domain, split: leaky)
    seen: list[dict] = []
    real = runner._step

    def spy(name):
        fn = real(name)
        if name != "spec":
            return fn
        return lambda q, cfg: (seen.append(q), fn(q, cfg))[1]

    monkeypatch.setattr(runner, "_step", spy)
    runner.run(RunConfig(name="t"), root=tmp_path)
    assert seen and set(seen[0]) == set(corpus.QUESTION_KEYS)
    assert all(set(c) <= set(corpus.CARD_KEYS) for c in seen[0]["intent_card"])


def test_dataset_questions_carry_only_allowed_keys() -> None:
    for split in ("test", "practice"):
        for q in corpus.questions("medical", split):
            assert set(q) == set(corpus.QUESTION_KEYS)
            assert all(set(c) <= set(corpus.CARD_KEYS) for c in q["intent_card"])


def test_manifest_is_written_and_changed_code_stops_a_resume(stubs, tmp_path, monkeypatch) -> None:
    cfg = RunConfig(name="t", questions=["Q1"])
    out = runner.run(cfg, root=tmp_path / "runs")
    first = json.loads((out / "manifest.json").read_text())
    assert first["code_hash"] == runner.code_hash()
    assert set(first) == {"git_sha", "git_dirty", "code_hash", "data_hash", "data"}
    assert set(first["data"]) == {"papers", "questions", "gold"}
    runner.run(cfg, root=tmp_path / "runs")                                  # same code: resumes
    monkeypatch.setattr(runner, "code_hash", lambda dirs=None: "other")
    monkeypatch.delenv("EVQA_ALLOW_CODE_CHANGE", raising=False)
    with pytest.raises(RuntimeError, match="code changed"):
        runner.run(cfg, root=tmp_path / "runs")
    monkeypatch.setenv("EVQA_ALLOW_CODE_CHANGE", "1")
    assert runner.run(cfg, root=tmp_path / "runs").name == cfg.run_id()      # run id unchanged
    assert any(e["data"].get("message") == "code changed" for e in events(out))
    assert json.loads((out / "manifest.json").read_text()) == first          # the first start stays on record


def test_manifest_without_git(stubs, tmp_path, monkeypatch) -> None:
    def no_git(*a, **k):
        raise FileNotFoundError("git")
    monkeypatch.setattr(runner.subprocess, "run", no_git)
    out = runner.run(RunConfig(name="t", questions=["Q1"]), root=tmp_path / "runs")
    m = json.loads((out / "manifest.json").read_text())
    assert m["git_sha"] is None and m["git_dirty"] is None and len(m["code_hash"]) == 64


def test_step_end_event_carries_token_counts(stubs, tmp_path, monkeypatch) -> None:
    def spec_with_tokens(q, cfg):
        m = lm.make_lm(RunConfig().llm, ask=lambda t: lm._reply(json.dumps({"y": "hi"}),
                                                                 {"prompt_tokens": 11, "completion_tokens": 2}))
        with dspy.context(lm=m, adapter=dspy.JSONAdapter()):
            dspy.Predict(Sig)(x="tokens")
        return Spec(qid=q["qid"], question=q["question"], type="lookup", subjects=[Name(label="d")],
                    measure=Name(label="m")).seal()
    steps = {"spec": spec_with_tokens}
    old = runner._step
    monkeypatch.setattr(runner, "_step", lambda name: steps.get(name) or old(name))
    out = runner.run(RunConfig(name="t", questions=["Q1"]), root=tmp_path / "runs")
    end = next(e for e in events(out) if e["step"] == "spec" and e["kind"] == "end")
    assert end["data"]["llm"]["prompt_tokens"] == 11 and end["data"]["llm"]["completion_tokens"] == 2


def test_progress_prints_one_line_per_finished_question(stubs, tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("EVQA_QUIET", raising=False)
    _, fail = stubs
    fail.add("Q2")
    runner.run(RunConfig(name="p"), root=tmp_path)
    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 4 and sorted(int(x[1]) for x in lines) == [1, 2, 3, 4]
    assert all(x.startswith("[") and "/4] Q" in x and " eta " in x for x in lines)
    assert any("Q2 problem: RuntimeError" in x for x in lines)
    assert sum(" ok " in x for x in lines) == 3


def test_progress_eta_and_quiet(monkeypatch) -> None:
    import io
    now = [0.0]
    buf = io.StringIO()
    monkeypatch.delenv("EVQA_QUIET", raising=False)
    p = runner.Progress(78, out=buf, clock=lambda: now[0])
    for i in range(12):
        now[0] += 40.0
        p.finished(f"Q{i}", 34.2)
    assert buf.getvalue().splitlines()[-1] == "[12/78] Q11 ok 34.2s  eta 44m"   # 480s/12 x 66 left = 2640s
    assert runner._minutes(7500) == "2h05m" and runner._minutes(30) == "30s"
    monkeypatch.setenv("EVQA_QUIET", "1")
    quiet = io.StringIO()
    q = runner.Progress(2, out=quiet)
    q.finished("Q1", 1.0)
    assert quiet.getvalue() == "" and q.done == 1


# ---------------------------------------------------------------- data fingerprint
@pytest.fixture
def data_dirs(tmp_path, monkeypatch):
    """A tiny dataset + seed folder for datahash (paths.DATASET / paths.SEED point at it)."""
    from evqa import paths
    ds, seed = tmp_path / "data" / "dataset", tmp_path / "data" / "seed"
    (ds / "medical" / "P1").mkdir(parents=True)
    (ds / "medical" / "P1" / "paper.md").write_text("paper one")
    (ds / "medical" / "questions").mkdir()
    (ds / "medical" / "questions" / "test.jsonl").write_text("{}\n")
    (ds / "medical" / "questions" / "practice.jsonl").write_text("{}\n")
    (seed / "medical" / "gold").mkdir(parents=True)
    (seed / "medical" / "gold" / "Q1.json").write_text("{}")
    (seed / "medical" / "papers").mkdir()
    (seed / "medical" / "papers" / "writer_log.jsonl").write_text("x")
    monkeypatch.setattr(paths, "DATASET", ds)
    monkeypatch.setattr(paths, "SEED", seed)
    monkeypatch.setattr(paths, "DATA", tmp_path / "data")
    return ds / "medical", seed / "medical"


def test_data_hashes_name_the_group_that_changed(data_dirs) -> None:
    from evqa import datahash
    ds, seed = data_dirs
    first = datahash.data_hashes("medical", "test")
    assert set(first) == {"data_hash", "papers", "questions", "gold"}
    (ds / "questions" / "practice.jsonl").write_text("other split\n")      # not read by a test-split run
    (seed / "papers" / "writer_log.jsonl").write_text("y")                  # not read by eval
    assert datahash.data_hashes("medical", "test") == first
    (seed / "gold" / "Q1.json").write_text('{"a": 1}')
    second = datahash.data_hashes("medical", "test")
    assert second["gold"] != first["gold"] and second["data_hash"] != first["data_hash"]
    assert (second["papers"], second["questions"]) == (first["papers"], first["questions"])


def test_changed_papers_or_questions_stop_a_resume(stubs, data_dirs, tmp_path, monkeypatch) -> None:
    ds, seed = data_dirs
    monkeypatch.delenv("EVQA_ALLOW_DATA_CHANGE", raising=False)
    cfg = RunConfig(name="t", questions=["Q1"])
    out = runner.run(cfg, root=tmp_path / "runs")
    first = json.loads((out / "manifest.json").read_text())
    (seed / "gold" / "Q1.json").write_text('{"a": 1}')                     # gold only: logged, not refused
    runner.run(cfg, root=tmp_path / "runs")
    assert any(e["data"].get("message") == "data changed" and e["data"]["changed"] == ["gold"] for e in events(out))
    (ds / "P1" / "paper.md").write_text("paper one, edited")
    with pytest.raises(RuntimeError, match="papers changed"):
        runner.run(cfg, root=tmp_path / "runs")
    (ds / "questions" / "test.jsonl").write_text("{}\n{}\n")
    with pytest.raises(RuntimeError, match="papers, questions changed"):
        runner.run(cfg, root=tmp_path / "runs")
    monkeypatch.setenv("EVQA_ALLOW_DATA_CHANGE", "1")
    runner.run(cfg, root=tmp_path / "runs")
    assert any(e["data"].get("changed") == ["papers", "questions", "gold"] for e in events(out))
    assert json.loads((out / "manifest.json").read_text()) == first          # the first start stays on record


def test_old_manifest_gets_the_data_hash_added(stubs, data_dirs, tmp_path) -> None:
    cfg = RunConfig(name="t", questions=["Q1"])
    out = runner.run(cfg, root=tmp_path / "runs")
    m = json.loads((out / "manifest.json").read_text())
    old = {k: m[k] for k in ("git_sha", "git_dirty", "code_hash")}
    (out / "manifest.json").write_text(json.dumps(old))
    runner.run(cfg, root=tmp_path / "runs")
    assert json.loads((out / "manifest.json").read_text()) == m
    assert any(e["data"].get("message") == "data hash added" for e in events(out))


# ---------------------------------------------------------------- pools sized from the call cap
def _peak_questions(stubs, tmp_path, monkeypatch, cfg: RunConfig) -> int:
    import threading
    import time
    from evqa import corpus as corpus_mod
    many = [{"qid": f"Q{i}", "question": f"q {i}", "intent_card": []} for i in range(1, 11)]
    monkeypatch.setattr(corpus_mod, "questions", lambda domain, split: many)
    now, peak, lock = [0], [0], threading.Lock()
    old = runner._step

    def spec(q, cfg):
        with lock:
            now[0] += 1
            peak[0] = max(peak[0], now[0])
        time.sleep(0.2)
        with lock:
            now[0] -= 1
        return Spec(qid=q["qid"], question=q["question"], type="lookup", subjects=[Name(label="d")],
                    measure=Name(label="m")).seal()
    monkeypatch.setattr(runner, "_step", lambda name: spec if name == "spec" else old(name))
    runner.run(cfg, root=tmp_path / "runs")
    return peak[0]


def test_qwen_config_runs_up_to_the_qwen_cap(stubs, tmp_path, monkeypatch) -> None:
    from evqa import slots
    monkeypatch.setattr(slots, "MAX_SLOTS_QWEN", 8)
    assert _peak_questions(stubs, tmp_path, monkeypatch, RunConfig(name="qw")) > 3


def test_claude_config_stays_at_three(stubs, tmp_path, monkeypatch) -> None:
    from evqa import slots
    from evqa.contracts import StepLLM
    monkeypatch.setattr(slots, "MAX_SLOTS_QWEN", 8)
    cfg = RunConfig(name="cl", llm=StepLLM(backend="claude", model="claude-haiku-5-5"))
    assert _peak_questions(stubs, tmp_path, monkeypatch, cfg) == 3
    assert runner.question_workers(RunConfig()) == 8 and runner.question_workers(cfg) == 3


def test_pmap_and_cap_follow_the_backend(monkeypatch) -> None:
    import threading
    import time
    from evqa import llm, slots
    assert llm.cap_for("qwen") == 3 and llm.cap_for("claude") == 3          # defaults unchanged
    monkeypatch.setattr(slots, "MAX_SLOTS_QWEN", 8)
    assert llm.cap_for("qwen") == 8 and llm.cap_for("claude") == 3
    now, peak, lock = [0], [0], threading.Lock()

    def slow(i):
        with lock:
            now[0] += 1
            peak[0] = max(peak[0], now[0])
        time.sleep(0.1)
        with lock:
            now[0] -= 1
        return i
    assert llm.pmap(slow, range(16), workers=llm.cap_for("qwen")) == list(range(16)) and peak[0] > 3
    peak[0] = 0
    llm.pmap(slow, range(9))                                                 # default (paperwriter, seed): 3
    assert peak[0] == 3


# ---------------------------------------------------------------- circuit breaker
def test_breaker_stops_the_run_when_the_service_is_down(stubs, tmp_path, monkeypatch, capsys) -> None:
    import argparse
    from evqa import corpus as corpus_mod
    many = [{"qid": f"Q{i}", "question": f"q {i}", "intent_card": []} for i in range(1, 13)]
    monkeypatch.setattr(corpus_mod, "questions", lambda domain, split: many)
    monkeypatch.delenv("EVQA_BREAKER", raising=False)
    started: list[str] = []
    old = runner._step

    def find(spec, domain, cfg):
        started.append(spec.qid)
        raise ConnectionRefusedError("model service refused the connection")
    monkeypatch.setattr(runner, "_step", lambda name: find if name == "find" else old(name))
    conf = tmp_path / "c.yaml"
    conf.write_text("name: down\n")
    monkeypatch.setattr(runner, "ROOT", tmp_path / "runs")
    parser = argparse.ArgumentParser()
    runner.add_cli(parser.add_subparsers())
    a = parser.parse_args(["run", "--config", str(conf)])
    assert a.fn(a) == 1
    out = tmp_path / "runs" / RunConfig.load(conf).run_id()
    ev = events(out)
    stop = [e for e in ev if e["data"].get("message") == "run stopped: model service down"]
    assert len(stop) == 1 and stop[0]["kind"] == "problem"
    assert 3 <= len(started) < 12 and ev[-1]["data"]["stopped"] == "model service down"
    assert len(ev[-1]["data"]["not_started"]) == 12 - len(started)
    err = capsys.readouterr().err
    assert "Restart the model service, then rerun the same command" in err


def test_breaker_counts_service_failures_in_a_row_only() -> None:
    b = runner.Breaker(3)
    b.ended(ConnectionRefusedError())
    b.ended(TimeoutError())
    b.ended(None)                         # a question that finished resets the count
    b.ended(ConnectionRefusedError())
    b.ended(ValueError("bad reply"))      # not a service failure: resets too
    b.ended(ConnectionRefusedError())
    b.ended(ConnectionRefusedError())
    assert not b.tripped
    b.ended(ConnectionRefusedError())
    assert b.tripped
    off = runner.Breaker(0)
    for _ in range(5):
        off.ended(ConnectionRefusedError())
    assert not off.tripped
