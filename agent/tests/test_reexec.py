"""Re-execution (row 2.13, C5) of runs the real loop made with a scripted model (mode unsandboxed)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("minisweagent")
pytest.importorskip("litellm")

from agent import replay  # noqa: E402
from agent.anchor import AnchorError  # noqa: E402
from agent.attach import attach_run  # noqa: E402
from agent.canonical import sha256_hex  # noqa: E402
from agent.cli import main as cli  # noqa: E402
from agent.reexec import first_diff, parse_steps, reexec_run  # noqa: E402

from .test_loop import (FENCE, ScriptedModel, bash, claim_cmd, corpus, final, go, posix_only, row,  # noqa: E402,F401
                        unique_quote)


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def script(q1: str, q2: str) -> list[str]:
    return [
        bash('grep -c "the" "$CORPUS/p1.md"'),                                  # 1
        bash("echo hello > notes.txt && ls"),                                    # 2 writes into scratch
        bash("cat notes.txt"),                                                   # 3 reads it back
        bash(claim_cmd("this sentence was retyped and is not in the paper")),   # 4 rejected
        bash(claim_cmd(q1)),                                                     # 5 claim-000001
        bash(claim_cmd(q2, "p2.md", "another fact")),                           # 6 claim-000002
        bash("pwd"),                                                             # 7 the scratch path differs
        final([row(["claim-000001"])]),
    ]


@posix_only
def test_reexec_reproduces_the_run(tmp_path: Path, corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    run, outcome, _, _ = go(tmp_path, corpus, script(unique_quote("p1"), unique_quote("p2")))
    assert outcome.exit_status == "submitted"
    events, claims = run.events.read_bytes(), run.claims.read_bytes()
    assert cli(["reexec", str(run.root), "--corpus", str(corpus[0])]) == 1  # one output differs
    out = capsys.readouterr().out
    report = json.loads((run.root / "reexec.json").read_text(encoding="utf-8"))
    assert (report["steps"], report["identical"], report["identical_steps"]) == (7, 6, [1, 2, 3, 4, 5, 6])
    assert report["errors"] == [] and report["sandbox"] == "unsandboxed" and report["scratch"] is None
    [diff] = report["differing"]
    assert (diff["step"], diff["agent_id"], diff["command"], diff["first_diff_line"]) == (7, "main", "pwd", 1)
    assert diff["recorded_line"] == str(run.scratch.resolve()) and diff["now_line"] != diff["recorded_line"]
    assert (run.root / diff["output_file"]).read_text(encoding="utf-8") == diff["now_line"] + "\n"
    assert diff["exit_code"] == {"recorded": 0, "now": 0}
    assert "DIFF step 7 (main) line 1" in out
    assert "6/7 outputs identical, 1 differing; claims 3/3 as recorded, 0 differing" in out
    # The toolchain is recorded: the test runs name a made-up agent root hash, this one has none.
    assert report["toolchain"]["agent_root_manifest_sha256"] == {"run": "b" * 64, "now": sha256_hex(b"")}
    assert report["toolchain"]["git_commit"]["run"] == "c" * 40 and report["toolchain_differs"]
    assert "WARN toolchain differs: agent root manifest sha256" in out
    # The claims went to the dry broker: same verdicts and ids as the run's, logged in reexec.jsonl only.
    assert report["claims"] == {"sent": 3, "accepted": 2, "rejected": 1, "same_as_recorded": 3}
    assert report["differing_claims"] == []
    dry = jsonl(run.root / "reexec.jsonl")
    assert [(d["step_id"], d["status"], d["claim_id"], d["reason"], d["origin"]) for d in dry] == [
        (4, "rejected", None, "not_found", "research"), (5, "accepted", "claim-000001", None, "research"),
        (6, "accepted", "claim-000002", None, "research")]
    assert all(d["same_as_recorded"] for d in dry) and dry[1]["anchor"]["file"] == "p1.md"
    assert run.events.read_bytes() == events and run.claims.read_bytes() == claims  # the run is untouched
    assert replay.replay_run(run.root)["ok"]
    # One step alone: its claim gets the id the run's broker gave it, so the output is the same.
    report = reexec_run(run.root, *corpus, steps=[6])
    assert (report["steps"], report["identical_steps"], report["differing"]) == (1, [6], [])
    assert jsonl(run.root / "reexec.jsonl")[0]["claim_id"] == "claim-000002"
    assert not (run.root / "reexec").exists()  # the earlier re-execution's differing output went with it
    # A command that reads what a skipped command wrote differs: the scratch directory is fresh.
    report = reexec_run(run.root, *corpus, steps=[3])
    assert report["differing"][0]["step"] == 3 and "No such file" in report["differing"][0]["now_line"]
    report = reexec_run(run.root, *corpus, steps=[2, 3, 99])
    assert report["identical_steps"] == [2, 3] and report["errors"] == ["step 99: the run recorded no command at this step"]


@posix_only
def test_reexec_of_a_run_with_a_subagent(tmp_path: Path, corpus: tuple[Path, Path]) -> None:
    """A subagent's commands run again in a scratch of their own (row 2.12: sub/<id>/scratch), so its
    files and the parent's stay apart as they were; the parent's spawn command alone differs."""
    from .test_spawn import SPAWN, SubModels, summary

    subs = SubModels({"Note and claim": [bash("echo sub > notes.txt && ls"), bash(claim_cmd(unique_quote("p1"))),
                                         summary("p1 states a fact")]})
    run, outcome, _, _ = go(tmp_path, corpus, [bash("echo parent > notes.txt"),
                                               bash('spawn --task "Note and claim" > r.json; cat r.json'),
                                               bash("cat notes.txt"), final([row(["claim-000001"])])],
                            spawn=SPAWN, sub_model=subs)
    assert outcome.exit_status == "submitted" and outcome.subagents == 1
    report = reexec_run(run.root, *corpus)
    assert report["spawn"] is True and report["errors"] == []
    assert [(d["agent_id"], d["step"]) for d in report["differing"]] == [("main", 2)]  # no spawn channel here
    assert report["steps"] == 5 and report["identical"] == 4  # step 3 still reads the parent's own notes.txt
    assert report["claims"] == {"sent": 1, "accepted": 1, "rejected": 0, "same_as_recorded": 1}
    assert report["differing_claims"] == []


@posix_only
def test_reexec_against_a_changed_corpus(tmp_path: Path, corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    run, _, _, _ = go(tmp_path, corpus, script(unique_quote("p1"), unique_quote("p2")))
    paper = corpus[0] / "p2.md"
    paper.write_bytes(paper.read_bytes() + b"\nOne more line.\n")
    assert cli(["reexec", str(run.root), "--corpus", str(corpus[0]), "--steps", "6"]) == 2
    out = capsys.readouterr().out
    assert "FAIL corpus: p2.md differs from the manifest" in out
    assert "DIFF claim 1 of step 6 (main): recorded accepted claim-000002, now rejected corpus_file_hash_mismatch" in out
    report = json.loads((run.root / "reexec.json").read_text(encoding="utf-8"))
    assert report["differing"][0]["step"] == 6 and "corpus_file_hash_mismatch" in report["differing"][0]["now_line"]
    assert jsonl(run.root / "reexec.jsonl")[0]["same_as_recorded"] is False
    # Any paper counts, named in a command or not (`rg ... "$CORPUS"` reads them all), and so does an extra file.
    paper.write_bytes(paper.read_bytes()[:-len(b"\nOne more line.\n")])
    (corpus[0] / "p11.md").write_text("# A paper the manifest does not list\n", encoding="utf-8")
    (corpus[0] / "p3.md").unlink()
    report = reexec_run(run.root, *corpus, steps=[1])
    assert report["errors"] == ["corpus: p3.md differs from the manifest (the corpus is not the frozen one)",
                                "corpus: p11.md is not in the manifest (the corpus is not the frozen one)"]
    assert report["identical_steps"] == [1]
    # Another manifest is another corpus: nothing runs.
    other = tmp_path / "other-manifest.json"
    other.write_bytes(corpus[1].read_bytes() + b"\n")
    assert cli(["reexec", str(run.root), "--corpus", str(corpus[0]), "--manifest", str(other)]) == 2
    assert "is not the corpus manifest the run used" in capsys.readouterr().out


@posix_only
def test_reexec_baseline_and_its_attach_step(tmp_path: Path, corpus: tuple[Path, Path],
                                             capsys: pytest.CaptureFixture[str]) -> None:
    """claim_off: no claim tool for the research commands; the attach step's commands have it (origin attach)."""
    probe = 'command -v claim >/dev/null || echo NO_CLAIM; echo "fd=${CLAIM_FD:-unset}"'
    run, _, _, _ = go(tmp_path, corpus, [bash(probe), final([row()])], condition="claim_off")
    no_source = f"Result.\n{FENCE}json\n{json.dumps({'no_source': 'not this fact'})}\n{FENCE}"
    attach_run(run.root, *corpus, model=ScriptedModel([bash(claim_cmd(unique_quote("p1"))), no_source]),
               sandbox_mode="unsandboxed", broker="inprocess")
    report = reexec_run(run.root, *corpus)
    assert (report["steps"], report["identical_steps"], report["errors"]) == (2, [1, 3], [])
    assert report["claims"] == {"sent": 1, "accepted": 1, "rejected": 0, "same_as_recorded": 1}
    [dry] = jsonl(run.root / "reexec.jsonl")
    assert (dry["step_id"], dry["origin"], dry["claim_id"]) == (3, "attach", "claim-000001")
    assert (run.out / "step-0001.txt").read_text(encoding="utf-8") == "NO_CLAIM\nfd=unset\n"
    # The attach step's calls are not in trajectory.json: replay counts them and checks the research loop,
    # and says that the run replayed only partly.
    result = replay.replay_run(run.root)
    assert result["ok"] and result["skipped"] == {"main/attach": 2} and result["calls"] == 2
    assert (result["complete"], result["unchecked_calls"], result["scope"]) == (False, 2, "research")
    assert cli(["replay", str(run.root)]) == 0
    assert "PARTIAL replay r1: 2/2 model calls" in capsys.readouterr().out


@posix_only
def test_a_claim_that_differs_is_a_difference(tmp_path: Path, corpus: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
                                              capsys: pytest.CaptureFixture[str]) -> None:
    """The output does not show the claim's reply here, so only the dry broker's verdict tells (C5)."""
    hidden = f"[ -f flag ] && {claim_cmd(unique_quote('p1'))} >/dev/null; echo done"
    run, _, _, _ = go(tmp_path, corpus, [bash("echo x > flag"), bash(hidden), final([row(["claim-000001"])])])
    assert (run.out / "step-0002.txt").read_text(encoding="utf-8") == "done\n"
    # Step 2 alone: no flag in the fresh scratch, so the claim the run made is not sent again.
    assert cli(["reexec", str(run.root), "--corpus", str(corpus[0]), "--steps", "2"]) == 1
    out = capsys.readouterr().out
    assert "1/1 outputs identical, 0 differing; claims 0/0 as recorded, 1 differing" in out
    assert "DIFF claim 1 of step 2 (main): recorded accepted claim-000001, now not sent" in out
    # Both steps, but the anchor check now rejects the quote (say the anchor rules changed).
    def no_anchor(*args: object, **kwargs: object) -> None:
        raise AnchorError("not_found")
    monkeypatch.setattr("agent.reexec.find", no_anchor)
    assert cli(["reexec", str(run.root), "--corpus", str(corpus[0])]) == 1
    out = capsys.readouterr().out
    assert "2/2 outputs identical" in out
    assert "DIFF claim 1 of step 2 (main): recorded accepted claim-000001, now rejected not_found" in out
    [d] = json.loads((run.root / "reexec.json").read_text(encoding="utf-8"))["differing_claims"]
    assert (d["step"], d["recorded"]["status"], d["now"]["status"], d["now"]["claim_id"]) == (2, "accepted", "rejected", None)


@posix_only
def test_steps_that_select_nothing(tmp_path: Path, corpus: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    run, _, _, _ = go(tmp_path, corpus, [bash("echo one"), final([row([])])])
    assert cli(["reexec", str(run.root), "--corpus", str(corpus[0]), "--steps", "7-5"]) == 2
    assert "FAIL --steps: '7-5' runs backwards; write 5-7" in capsys.readouterr().out
    assert cli(["reexec", str(run.root), "--corpus", str(corpus[0]), "--steps", ","]) == 2
    assert "FAIL --steps selects no step" in capsys.readouterr().out
    assert not (run.root / "reexec.json").exists()


def test_parse_steps_and_first_diff() -> None:
    assert parse_steps("3, 1,5-7,5") == [1, 3, 5, 6, 7]
    with pytest.raises(ValueError, match="not a step id"):
        parse_steps("1,x")
    with pytest.raises(ValueError, match="runs backwards"):
        parse_steps("7-5")
    assert first_diff(b"a\nb\nc\n", b"a\nB\nc\n") == (2, "b\n", "B\n")
    assert first_diff(b"a\n", b"a\nmore\n") == (2, "", "more\n")
