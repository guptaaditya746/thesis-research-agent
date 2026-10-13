"""Concept step and pick (rows 2.1, 2.2) with a scripted model at LiteLLM's call."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("minisweagent")
pytest.importorskip("litellm")

import litellm  # noqa: E402

from agent import concept_step  # noqa: E402
from agent.broker import Broker, Channel  # noqa: E402
from agent.canonical import file_sha256  # noqa: E402
from agent.chain import verify  # noqa: E402
from agent.cli import main as cli  # noqa: E402
from agent.concept import concept_sha256  # noqa: E402
from agent.rundir import RunDir  # noqa: E402

from .conftest import MANIFEST, fixture  # noqa: E402
from .test_loop import FENCE, ScriptedModel  # noqa: E402
from .test_rundir import SETTINGS  # noqa: E402

QUESTION = "Which authors publish most often as first author at ACL 2025?"
RUN = dict(temperature=0.7, seed=1234, git_commit="c" * 40, base_url="http://mock.invalid/v1")


def brief(n: int, **change: Any) -> dict[str, Any]:
    """The table fixture as the model would write it (no id), made distinct by `n`."""
    out = {k: v for k, v in fixture("concept_table.json").items() if k != "id"}
    out["title"] = f"Reading {n}: {out['title']}"
    out["definition"] = f"{out['definition']} (reading {n})"
    return out | change


def reply(briefs: list[Any], why: str = "I read the question two ways.") -> str:
    return f"{why}\n{FENCE}json\n{json.dumps({'concepts': briefs})}\n{FENCE}"


def records(session: concept_step.Session) -> list[dict[str, Any]]:
    return [json.loads(line) for line in session.run.events.read_text(encoding="utf-8").splitlines()]


def propose(tmp_path: Path, replies: list[str], qid: str = "q01", **kw: Any):
    model = ScriptedModel(replies)
    session, proposal = concept_step.propose(tmp_path / "concepts", qid, QUESTION, model, **RUN, **kw)
    return session, proposal, model


def test_prompt_is_lf_versioned_and_hashed() -> None:
    raw = (concept_step.PROMPT_DIR / "concept-v1.txt").read_bytes()
    assert b"\r" not in raw
    prompt = concept_step.load_prompt("v1")
    assert prompt.files == {"concept-v1.txt": file_sha256(concept_step.PROMPT_DIR / "concept-v1.txt"),
                            "concept.schema.json": file_sha256(concept_step.SCHEMA_DIR / "concept.schema.json")}
    assert "{{" not in prompt.system and "at most 5" in prompt.system and '"competency_questions"' in prompt.system
    # corpus-blind: nothing about where the corpus is or what is in it
    for word in ("$CORPUS", "p1.md", "manifest", "rg "):
        assert word not in prompt.system


def test_valid_proposal_then_pick(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    graph = {k: v for k, v in fixture("concept_graph.json").items() if k != "id"}
    session, proposal, model = propose(tmp_path, [reply([brief(1, id="c9"), graph])])
    assert [b["id"] for b in proposal["briefs"]] == ["c1", "c2"]  # the harness numbers the briefs
    assert proposal["capped_from"] is None and proposal["rounds"] == 1
    # The model saw the prompt and the question, nothing else.
    [messages] = model.prompts
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[1]["content"] == f"Question: {QUESTION}"
    [call] = records(session)
    assert (call["subtype"], call["agent_id"], call["workflow_id"], call["step_id"]) == (
        "ai_model_invocation", "main", "q01", 1)
    assert call["custom_metadata"]["origin"] == "concept" and call["custom_metadata"]["phase"] == "propose"
    assert call["used"]["prompt_files"]["concept-v1.txt"] == concept_step.load_prompt().sha256
    assert {k: call["used"][k] for k in ("model", "revision", "temperature", "seed", "thinking", "max_tokens")} == {
        "model": "orch-model", "revision": "017b9c7", "temperature": 0.7, "seed": 1234, "thinking": False,
        "max_tokens": 4096}
    assert call["generated"]["valid"] and call["generated"]["briefs"] == 2 and call["generated"]["usage"]["total_tokens"]
    settings = session.load(concept_step.SESSION_FILE)
    assert settings["prompt"]["sha256"] == call["used"]["prompt_files"]["concept-v1.txt"]
    assert settings["sampling"] == {"temperature": 0.7, "seed": 1234}

    assert cli(["concepts", "pick", str(session.root), "--choice", "2"]) == 0
    out = capsys.readouterr().out
    assert "PASS picked [2] Benchmarks used by RAG papers" in out
    concept = json.loads(session.path("concept.json").read_text(encoding="utf-8"))
    assert concept == {"id": "c2", **graph}
    sha = file_sha256(session.path("concept.json"))
    assert sha == concept_sha256(concept) and sha in out
    assert session.path("concept.sha256").read_bytes() == f"{sha}  concept.json\n".encode()
    pick = records(session)[-1]
    assert (pick["subtype"], pick["agent_id"], pick["parent_task_id"], pick["step_id"]) == (
        "concept_pick", "user", call["task_id"], 2)
    assert pick["used"]["choice"] == 2 and pick["used"]["brief_id"] == "c2"
    assert pick["used"]["proposal_sha256"] == file_sha256(session.path("proposal.json"))
    assert pick["generated"]["concept_sha256"] == sha and pick["custom_metadata"]["origin"] == "concept"
    report = verify(session.run.events, session.run.claims)
    assert report.ok and report.records == 2 and report.claims == 0
    assert concept_step.check_session(session.root) == []
    assert cli(["concepts", "check", str(session.root)]) == 0
    # The frozen file is what a run uses: same hash in the run's config.
    run = RunDir.create(tmp_path / "runs", "q01-claim_on-r1", concept, corpus_manifest=MANIFEST, **SETTINGS)
    assert run.load_config()["hashes"]["concept_sha256"] == sha
    # Frozen: a second pick is refused, and so is a second proposal for the question.
    assert cli(["concepts", "pick", str(session.root), "--choice", "1"]) == 1
    assert "frozen" in capsys.readouterr().out
    with pytest.raises(ValueError, match="already has a proposal"):
        propose(tmp_path, [reply([brief(1)])])
    # Tampering is found.
    session.path("concept.json").write_bytes(session.path("concept.json").read_bytes().replace(b"c2", b"c3"))
    assert concept_step.check_session(session.root) == [
        "concept.sha256 differs from concept.json", "concept.json is not the one the pick record names"]


def test_invalid_output_gets_one_repair_round(tmp_path: Path) -> None:
    broken = brief(1)
    del broken["competency_questions"]
    session, proposal, model = propose(tmp_path, [reply([broken, brief(2)]), reply([brief(1), brief(2)])])
    assert proposal["rounds"] == 2 and len(proposal["briefs"]) == 2
    repair = model.prompts[1]
    assert repair[-2]["role"] == "assistant" and "not valid" in repair[-1]["content"]
    assert "concepts/0: 'competency_questions' is a required property" in repair[-1]["content"]
    recs = records(session)
    assert [(r["subtype"], r["step_id"]) for r in recs] == [
        ("ai_model_invocation", 1), ("coverage", 1), ("ai_model_invocation", 2)]
    assert recs[1]["generated"]["reason"] == "invalid_concepts" and recs[1]["parent_task_id"] == recs[0]["task_id"]
    assert [r["custom_metadata"]["phase"] for r in recs] == ["propose", "propose", "repair"]
    assert proposal["model_call"] == recs[2]["task_id"]
    assert concept_step.pick(session.root, 1)[0]["id"] == "c1"
    assert records(session)[-1]["parent_task_id"] == recs[2]["task_id"]  # the pick follows the shown briefs


def test_still_invalid_after_repair_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(concept_step.ConceptStepError, match="no valid briefs after 1 repair") as caught:
        propose(tmp_path, ["I am not sure what to do.", reply([{"title": "half a brief"}])])
    assert any("'definition' is a required property" in p for p in caught.value.problems)
    session = concept_step.Session(tmp_path / "concepts" / "q01")
    assert not session.path("proposal.json").exists()
    assert [r["generated"].get("reason") for r in records(session) if r["subtype"] == "coverage"] == [
        "invalid_concepts", "invalid_concepts"]
    with pytest.raises(ValueError, match="no proposal"):
        concept_step.pick(session.root, 1)
    with pytest.raises(ValueError, match="other settings"):
        concept_step.propose(tmp_path / "concepts", "q01", "Another question?", ScriptedModel([]), **RUN)
    # Trying again continues the same chain with later step ids.
    _, proposal, _ = propose(tmp_path, [reply([brief(1)])])
    assert [r["step_id"] for r in records(session)] == [1, 1, 2, 2, 3]
    assert proposal["rounds"] == 1 and verify(session.run.events, session.run.claims).ok


def test_more_than_five_briefs_are_capped(tmp_path: Path) -> None:
    seven = [brief(n) for n in range(1, 7)] + [{"title": "an invalid seventh brief"}]
    session, proposal, _ = propose(tmp_path, [reply(seven)])
    assert [b["id"] for b in proposal["briefs"]] == ["c1", "c2", "c3", "c4", "c5"]
    assert proposal["capped_from"] == 7 and proposal["briefs"][4]["title"].startswith("Reading 5:")
    assert records(session)[0]["generated"]["capped_from"] == 7
    assert concept_step.show(proposal["briefs"]).count("\n[") == 4


def test_max_briefs_is_the_model_cap(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_briefs"):
        propose(tmp_path, [], max_briefs=6)
    _, proposal, model = propose(tmp_path, [reply([brief(1), brief(2), brief(3)])], max_briefs=2)
    assert proposal["capped_from"] == 3 and len(proposal["briefs"]) == 2
    assert "at most 2" in model.prompts[0][0]["content"]


@pytest.mark.parametrize("content, problem", [
    ("no block at all, just words.\nAnd more words here.\nStill no block.\nEnd.", "no json block"),
    (f"{FENCE}json\n{{\"concepts\": []}}\n{FENCE}", "non-empty list"),
    (f"{FENCE}json\n{{\"briefs\": []}}\n{FENCE}", 'must be {"concepts"'),
    (f"{FENCE}json\n{{\"concepts\": [1]}}\n{FENCE}", "must be a JSON object"),
    (f"{FENCE}json\n{{\"concepts\": [\n{FENCE}", "not valid JSON"),
])
def test_parse_briefs_problems(content: str, problem: str) -> None:
    briefs, problems, _ = concept_step.parse_briefs(content)
    assert briefs is None and any(problem in p for p in problems), problems


def test_parse_briefs_forms() -> None:
    briefs, problems, _ = concept_step.parse_briefs(json.dumps([brief(1)]))  # a bare list on one line
    assert problems == [] and briefs[0]["id"] == "c1"
    _, problems, _ = concept_step.parse_briefs(reply([brief(1), brief(1)]))
    assert problems == ["concepts/1: same brief as concepts/0"]


def test_pick_on_the_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    session, _, _ = propose(tmp_path, [reply([brief(1), brief(2)])])
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert cli(["concepts", "pick", str(session.root)]) == 1
    assert "no terminal" in capsys.readouterr().out
    answers = iter(["7", "x", "1"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert cli(["concepts", "pick", str(session.root)]) == 0
    out = capsys.readouterr().out
    assert "[1] Reading 1:" in out and "[2] Reading 2:" in out and "measure:    count Paper, group by first_author" in out
    assert json.loads(session.path("concept.json").read_text(encoding="utf-8"))["id"] == "c1"


def test_pick_records_who_picked_and_can_be_replaced(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    session, _, _ = propose(tmp_path, [reply([brief(1), brief(2), brief(3)])])
    assert cli(["concepts", "pick", str(session.root), "--choice", "1", "--picked-by", "provisional-first",
                "--reason", "first by rule"]) == 0
    assert "(by provisional-first)" in capsys.readouterr().out
    first = records(session)[-1]
    assert first["agent_id"] == "provisional-first"
    assert (first["used"]["picked_by"], first["used"]["reason"]) == ("provisional-first", "first by rule")
    picks_file = tmp_path / "concepts" / "picks.json"
    assert json.loads(picks_file.read_text(encoding="utf-8")) == {"q01": {
        "choice": 1, "title": "Reading 1: Most first-author papers at ACL 2025", "picked_by": "provisional-first",
        "reason": "first by rule", "concept_sha256": file_sha256(session.path("concept.json"))}}
    # Frozen unless replaced on purpose (the web app, before gold is built).
    assert cli(["concepts", "pick", str(session.root), "--choice", "3"]) == 1
    assert "frozen" in capsys.readouterr().out
    old = file_sha256(session.path("concept.json"))
    concept, sha = concept_step.pick(session.root, 3, picked_by="user", reason="counts papers, not authors",
                                     replace=True)
    assert concept["id"] == "c3" and sha != old and file_sha256(session.path("concept.json")) == sha
    last = records(session)[-1]
    assert (last["agent_id"], last["used"]["replaces_concept_sha256"], last["step_id"]) == ("user", old, 3)
    assert concept_step.picks(tmp_path / "concepts")["q01"] == {
        "choice": 3, "title": concept["title"], "picked_by": "user", "reason": "counts papers, not authors",
        "concept_sha256": sha}
    assert json.loads(picks_file.read_text(encoding="utf-8"))["q01"]["choice"] == 3
    assert concept_step.check_session(session.root) == []
    with pytest.raises(ValueError, match="picked_by"):
        concept_step.pick(session.root, 1, picked_by="someone", replace=True)


QUESTIONS = [
    {"id": "q01", "category": "corpus_wide", "question": QUESTION, "source": "own", "notes": ""},
    {"id": "q02", "category": "ambiguous", "question": "Which paper in this corpus is the most influential?",
     "source": "nlp48", "notes": ""},
    {"id": "q03", "category": "ambiguous", "question": "Which benchmark is the most popular in the corpus?",
     "source": "nlp53", "notes": ""},
]


def write_questions(tmp_path: Path, questions: list[dict[str, Any]] = QUESTIONS) -> Path:
    path = tmp_path / "questions.json"
    path.write_text(json.dumps({"schema_version": 1, "questions": questions}), encoding="utf-8")
    return path


def test_propose_all_skips_done_and_survives_a_failure(tmp_path: Path) -> None:
    root = tmp_path / "concepts"
    questions = concept_step.load_questions(write_questions(tmp_path))
    lines: list[str] = []
    model = ScriptedModel([reply([brief(1), brief(2)]), "no block.\nstill none.\nnone.\nnope.", "still no block",
                           reply([brief(3)])])
    results = concept_step.propose_all(questions, root, model, **RUN, log=lines.append)
    assert [(r.id, r.state) for r in results] == [("q01", "proposed"), ("q02", "failed"), ("q03", "proposed")]
    assert results[1].detail.startswith("ConceptStepError: no valid briefs") and results[1].problems
    assert lines == [r.line() for r in results] and lines[0] == "q01 proposed 2 briefs in 1 round(s)"
    # Each question had its own conversation: the question it was asked is its own.
    assert [p[1]["content"] for p in model.prompts if len(p) == 2] == [f"Question: {q['question']}" for q in QUESTIONS]
    # Running again retries only the failed question, in the same session (later step ids).
    model = ScriptedModel([reply([brief(4)])])
    results = concept_step.propose_all(questions, root, model, **RUN)
    assert [(r.id, r.state) for r in results] == [("q01", "skipped"), ("q02", "proposed"), ("q03", "skipped")]
    assert results[0].detail == "has a proposal (2 briefs)" and len(model.prompts) == 1
    assert [r["step_id"] for r in records(concept_step.Session(root / "q02"))] == [1, 1, 2, 2, 3]
    # A model or proxy error (a 400 here: never retried) is a failure of that question only.
    model = ScriptedModel([litellm.exceptions.BadRequestError("proxy says no", "orch-model", "openai"),
                           reply([brief(5)])])
    questions5 = questions + [
        {"id": "q04", "category": "corpus_wide", "question": "What is measured in the corpus?", "source": "own",
         "notes": ""},
        {"id": "q05", "category": "ambiguous", "question": "Which method is best in the corpus?", "source": "own",
         "notes": ""}]
    results = concept_step.propose_all(questions5, root, model, **RUN)
    assert [r.state for r in results] == ["skipped", "skipped", "skipped", "failed", "proposed"]
    assert "BadRequestError" in results[3].detail and "proxy says no" in results[3].detail


def test_pick_all_status_and_stale_questions(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "concepts"
    path = write_questions(tmp_path)
    questions = concept_step.load_questions(path)
    concept_step.propose_all(questions[:2], root, ScriptedModel([reply([brief(1), brief(2)]), reply([brief(7)])]), **RUN)
    assert [r.line() for r in concept_step.status(questions, root)] == [
        "q01 proposed 2 briefs, none picked", "q02 proposed 1 briefs, none picked", "q03 none"]
    assert cli(["concepts", "pick", str(root / "q02"), "--choice", "1", "--reason", "mine"]) == 0
    capsys.readouterr()
    assert cli(["concepts", "pick-all", str(path), "--root", str(root)]) == 1  # q03 has no proposal
    out = capsys.readouterr().out
    assert "q01 picked   [1] Reading 1: Most first-author papers at ACL 2025 sha256=" in out
    assert "q02 skipped  already picked [1] by user" in out and "q03 missing" in out
    assert "FAIL 1 missing, 1 picked, 1 skipped (needs action: q03)" in out
    pick = records(concept_step.Session(root / "q01"))[-1]
    assert pick["agent_id"] == "provisional-first" and pick["used"]["reason"] == concept_step.RULE_REASON["first"]
    picks = json.loads((root / "picks.json").read_text(encoding="utf-8"))
    assert {k: (v["picked_by"], v["reason"]) for k, v in picks.items()} == {
        "q01": ("provisional-first", concept_step.RULE_REASON["first"]), "q02": ("user", "mine")}
    assert cli(["concepts", "status", str(path), "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "q01 picked   [1/2] Reading 1: Most first-author papers at ACL 2025 (by provisional-first) sha256=" in out
    assert "q03 none" in out
    # A question whose text changed is stale: its concept no longer belongs to it.
    changed = [dict(QUESTIONS[0], question="Which authors publish most often at EMNLP 2025?"), *QUESTIONS[1:2]]
    result = concept_step.status(changed, root)
    assert result[0].state == "stale" and "move the session" in result[0].detail
    assert concept_step.propose_all(changed, root, ScriptedModel([]), **RUN)[0].state == "stale"
    assert concept_step.pick_all(changed, root)[0].state == "stale"
    # Everything picked and checked: status passes.
    assert cli(["concepts", "status", str(write_questions(tmp_path, QUESTIONS[:2])), "--root", str(root)]) == 0
    assert "PASS 2 picked" in capsys.readouterr().out


def test_cli_propose_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import agent.loop

    replies = [reply([brief(1)]), "nothing.\nnothing.\nnothing.\nnothing.", "nothing", reply([brief(2)])]
    made: list[dict[str, Any]] = []

    def model(**kwargs: Any) -> ScriptedModel:
        made.append(kwargs)
        return ScriptedModel(replies)
    monkeypatch.setattr(agent.loop, "OrchestratorModel", model)
    monkeypatch.setattr("agent.rundir.git_head", lambda repo: "c" * 40)  # a worktree's .git may not resolve in WSL
    monkeypatch.setenv("CONCEPTS", str(tmp_path / "concepts"))
    monkeypatch.setenv("LITELLM_BASE_URL", "http://proxy.invalid/v1")
    args = ["concepts", "propose-all", str(write_questions(tmp_path)), "--temperature", "0.7", "--seed", "1234"]
    assert cli(args) == 1
    out = capsys.readouterr().out
    assert made == [{"base_url": "http://proxy.invalid/v1", "temperature": 0.7, "seed": 1234}]
    assert "q02 failed   ConceptStepError" in out and "q02: no json block" in out
    assert "FAIL 1 failed, 2 proposed (needs action: q02)" in out
    assert concept_step.Session(tmp_path / "concepts" / "q01").load("session.json")["base_url"] == "http://proxy.invalid/v1"
    replies[:] = [reply([brief(3)])]
    assert cli(args) == 0
    assert "PASS 1 proposed, 2 skipped" in capsys.readouterr().out


def test_questions_file_problems(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicate question ids"):
        concept_step.load_questions(write_questions(tmp_path, [QUESTIONS[0], QUESTIONS[0]]))
    with pytest.raises(ValueError, match="category"):
        concept_step.load_questions(write_questions(tmp_path, [dict(QUESTIONS[0], category="hard")]))


def test_a_broker_without_corpus_rejects_claims(tmp_path: Path) -> None:
    run = RunDir(tmp_path / "s")
    run.root.mkdir()
    run.events.touch()
    broker = Broker(run, corpus=None)
    reply_ = broker.claim(Channel(1), json.dumps({"s": "a", "p": "b", "o": "c", "file": "p1.md", "quote": "x"}).encode())
    broker.close()
    assert reply_ == {"ok": False, "reason": "unknown_file"}
    assert verify(run.events, run.claims).ok
