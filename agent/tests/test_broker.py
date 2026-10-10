from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import unicodedata
from pathlib import Path
from typing import Any, Iterator

import pytest

from agent import claim_client
from agent.broker_client import BrokerError, BrokerProcess, InProcessBroker
from agent.chain import FIELDS, verify
from agent.cli import main as cli
from agent.rundir import RunDir

from .conftest import fixture, paper_file, papers, write_corpus
from .test_anchor import NAMES, occurrences, random_spans
from .test_rundir import SETTINGS

POSIX = sys.platform != "win32" and hasattr(socket, "send_fds") and hasattr(socket, "SOCK_SEQPACKET")
posix_only = pytest.mark.skipif(not POSIX, reason="needs AF_UNIX SOCK_SEQPACKET and SCM_RIGHTS (Linux)")


@pytest.fixture
def env(tmp_path: Path) -> tuple[RunDir, Path, Path]:
    corpus, manifest = write_corpus(tmp_path)
    run = RunDir.create(tmp_path / "runs", "r1", fixture("concept_table.json"), corpus_manifest=manifest, **SETTINGS)
    return run, corpus, manifest


@pytest.fixture
def broker(env: tuple[RunDir, Path, Path]) -> Iterator[InProcessBroker]:
    b = InProcessBroker(*(env[0].root, env[1], env[2]))
    yield b
    b.close()


def good_claims(k: int) -> list[dict[str, Any]]:
    """k claims with quotes that occur once in their paper, spread over the 10 papers."""
    out = []
    for name in NAMES:
        text = papers()[name]
        for start, end in random_spans(name):
            if occurrences(name, text[start:end]) == 1:
                out.append({"s": name, "p": "states", "o": f"span {start}", "file": paper_file(name),
                            "quote": " ".join(text[start:end].split()), "_span": (start, end)})
                break
    while len(out) < k:
        out += out
    return [dict(c) for c in out[:k]]


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def ask(sock: socket.socket, request: dict[str, Any]) -> dict[str, Any]:
    return claim_client.submit(sock, {k: v for k, v in request.items() if not k.startswith("_")})


# --- input A: harness records ----------------------------------------------------------------------

def test_harness_records_form_one_chain(broker: InProcessBroker, env: tuple[RunDir, Path, Path]) -> None:
    run = env[0]
    a = broker.record({"subtype": "ai_model_invocation", "step_id": 1,
                       "used": {"prompt_sha256": "a" * 64, "model": "orch-model", "revision": "017b9c7",
                                "temperature": 0.7, "seed": 1},
                       "generated": {"response_sha256": "b" * 64, "usage": {"prompt_tokens": 10}}})
    b = broker.record({"subtype": "agent_tool", "step_id": 1, "parent_task_id": a["task_id"],
                       "used": {"command": "rg -l retrieval $CORPUS"}, "generated": {"output_file": "out/1.txt"}})
    broker.record({"subtype": "coverage", "step_id": 2, "used": {"raw_output_sha256": "c" * 64},
                   "generated": {"reason": "no bash block"}, "status": "unparsed"})
    broker.record({"subtype": "spawn", "step_id": 3, "used": {"task": "read p3"}, "generated": {"agent_id": "sub-01"}})
    assert (a["task_id"], b["task_id"]) == ("t000001", "t000002")
    records = rows(run.events)
    assert [r["subtype"] for r in records] == ["ai_model_invocation", "agent_tool", "coverage", "spawn"]
    assert all(set(r) == set(FIELDS) and r["workflow_id"] == "r1" for r in records)
    assert records[1]["parent_task_id"] == "t000001" and records[1]["group_id"] == "step-1"
    report = verify(run.events, run.claims)
    assert report.ok and report.records == 4 and report.head == records[-1]["hash"]


@pytest.mark.parametrize("record,reason", [
    ({"subtype": "claim", "step_id": 1}, "subtype"),
    ({"subtype": "agent_tool"}, "step_id"),
    ({"subtype": "agent_tool", "step_id": -1}, "step_id"),
    ({"subtype": "agent_tool", "step_id": 1, "hash": "x"}, "unknown fields"),
    ({"subtype": "agent_tool", "step_id": 1, "used": "rg"}, "used"),
])
def test_bad_harness_records_refused(broker: InProcessBroker, record: dict[str, Any], reason: str) -> None:
    with pytest.raises(BrokerError, match=reason):
        broker.record(record)
    assert broker.head()["records"] == 0


# --- input B: claims -------------------------------------------------------------------------------

def test_concurrent_claims_from_three_steps(broker: InProcessBroker, env: tuple[RunDir, Path, Path]) -> None:
    run = env[0]
    claims = good_claims(12)
    replies: dict[int, list[dict[str, Any]]] = {}

    def command(step: int) -> None:
        sock = broker.claim_channel(step)
        with sock:
            replies[step] = [ask(sock, c) for c in claims]

    threads = [threading.Thread(target=command, args=(step,)) for step in (7, 8, 9)]
    for t in threads:
        t.start()
    for i in range(5):  # the harness keeps writing records meanwhile
        broker.record({"subtype": "agent_tool", "step_id": 6, "used": {"command": f"echo {i}"}})
    for t in threads:
        t.join()
    assert all(r["ok"] for step in replies for r in replies[step]), replies
    ids = [r["claim_id"] for step in (7, 8, 9) for r in replies[step]]
    assert len(set(ids)) == 36
    logged = rows(run.claims)
    assert [r["generated"]["claim_id"] for r in logged] == [f"claim-{i:06d}" for i in range(1, 37)]
    by_id = {r["generated"]["claim_id"]: r for r in logged}
    for step in (7, 8, 9):
        for reply, claim in zip(replies[step], claims):
            record = by_id[reply["claim_id"]]
            anchor = record["used"]["anchor"]
            assert record["step_id"] == step
            assert (anchor["file"], anchor["start"], anchor["end"]) == (claim["file"], *claim["_span"])
    report = verify(run.events, run.claims)
    assert report.ok and report.records == 41 and report.claims == 36


def test_forged_step_id_is_ignored(broker: InProcessBroker, env: tuple[RunDir, Path, Path]) -> None:
    claim = good_claims(1)[0]
    sock = broker.claim_channel(42)
    with sock:
        reply = ask(sock, {**claim, "step_id": 999999, "task_id": "t999999", "claim_id": "claim-999999"})
    assert reply == {"ok": True, "claim_id": "claim-000001"}
    record = rows(env[0].claims)[0]
    assert record["step_id"] == 42 and record["group_id"] == "step-42" and record["task_id"] == "t000001"
    assert record["custom_metadata"]["ignored_fields"] == ["claim_id", "step_id", "task_id"]


@pytest.mark.parametrize("change,reason", [
    (lambda c: c.update(quote="This sentence is not in the paper at all."), "not_found"),
    (lambda c: c.update(quote=c["quote"].replace(" ", " not ", 1)), "not_found"),
    (lambda c: c.update(quote="the"), "ambiguous"),
    (lambda c: c.update(file="p404.md"), "unknown_file"),
    (lambda c: c.update(file="p11.md"), "unknown_file"),  # the failed (scanned) paper is not usable
    (lambda c: c.update(file="../secrets/p1.md"), "file_outside_corpus"),
    (lambda c: c.pop("o"), "missing_field:o"),
    (lambda c: c.update(s=""), "bad_field:s"),
    (lambda c: c.update(o={"x": 1}), "bad_field:o"),
])
def test_rejected_claims_are_logged(broker: InProcessBroker, env: tuple[RunDir, Path, Path],
                                    change: Any, reason: str) -> None:
    claim = good_claims(1)[0]
    change(claim)
    sock = broker.claim_channel(3)
    with sock:
        reply = ask(sock, claim)
    assert reply == {"ok": False, "reason": reason}
    events, claims = rows(env[0].events), rows(env[0].claims)
    assert events == claims and len(claims) == 1
    assert claims[0]["status"] == "rejected" and claims[0]["custom_metadata"]["reason"] == reason
    assert claims[0]["generated"] == {}
    assert verify(env[0].events, env[0].claims).ok


def test_malformed_json_and_rejections_do_not_consume_claim_ids(broker: InProcessBroker,
                                                                env: tuple[RunDir, Path, Path]) -> None:
    sock = broker.claim_channel(1)
    with sock, sock.makefile("rwb") as stream:
        stream.write(b"{not json\n")
        stream.flush()
        assert json.loads(stream.readline()) == {"ok": False, "reason": "malformed_json"}
    sock = broker.claim_channel(2)
    with sock:
        assert ask(sock, good_claims(1)[0]) == {"ok": True, "claim_id": "claim-000001"}
    assert [r["status"] for r in rows(env[0].claims)] == ["rejected", "accepted"]


def test_absolute_path_inside_corpus_accepted(broker: InProcessBroker, env: tuple[RunDir, Path, Path]) -> None:
    claim = good_claims(1)[0]
    claim["file"] = (env[1] / claim["file"]).resolve().as_posix()
    with broker.claim_channel(1) as sock:
        assert ask(sock, claim)["ok"]
    assert rows(env[0].claims)[0]["used"]["anchor"]["file"] == good_claims(1)[0]["file"]


def test_non_ascii_quote(broker: InProcessBroker, env: tuple[RunDir, Path, Path]) -> None:
    name = "2025-emnlp-main-1755"
    raw = "For instance, Muñoz-Ortiz et al. (2024) find that humans exhibit more variance"
    quote = unicodedata.normalize("NFD", raw.replace("-", "–"))
    claim = {"s": "Muñoz-Ortiz et al. (2024)", "p": "finds", "o": "humans vary more (Δ)", "file": paper_file(name),
             "quote": quote}
    with broker.claim_channel(5) as sock:
        assert ask(sock, claim) == {"ok": True, "claim_id": "claim-000001"}
    data = env[0].claims.read_bytes()
    assert "Muñoz-Ortiz".encode("utf-8") in data and b"\\u" not in data
    anchor = rows(env[0].claims)[0]["used"]["anchor"]
    start = papers()[name].index(raw)
    assert (anchor["start"], anchor["end"], anchor["exact"]) == (start, start + len(raw), raw)
    assert rows(env[0].claims)[0]["custom_metadata"]["o"] == "humans vary more (Δ)"


def test_changed_corpus_file_is_rejected(broker: InProcessBroker, env: tuple[RunDir, Path, Path]) -> None:
    claim = good_claims(1)[0]
    path = env[1] / claim["file"]
    path.write_bytes(path.read_bytes() + b"\nappended\n")
    with broker.claim_channel(1) as sock:
        assert ask(sock, claim) == {"ok": False, "reason": "corpus_file_hash_mismatch"}


# --- the chain -------------------------------------------------------------------------------------

def fill(broker: InProcessBroker) -> None:
    broker.record({"subtype": "ai_model_invocation", "step_id": 1})
    with broker.claim_channel(1) as sock:
        for claim in good_claims(3):
            ask(sock, claim)
        ask(sock, {**good_claims(1)[0], "quote": "not in the paper, ever"})
    broker.record({"subtype": "agent_tool", "step_id": 1})


def flip(path: Path, offset: int) -> None:
    data = bytearray(path.read_bytes())
    data[offset] = ord("7") if data[offset] != ord("7") else ord("8")
    path.write_bytes(bytes(data))


@pytest.mark.parametrize("target", ["events", "claims"])
def test_one_byte_edit_breaks_verification(broker: InProcessBroker, env: tuple[RunDir, Path, Path],
                                           target: str, capsys: pytest.CaptureFixture[str]) -> None:
    fill(broker)
    run = env[0]
    assert cli(["verify-chain", str(run.root)]) == 0
    assert "PASS records=6 claims=4" in capsys.readouterr().out
    path = run.events if target == "events" else run.claims
    text = path.read_text(encoding="utf-8")
    flip(path, len(text.encode("utf-8")) // 2)
    assert cli(["verify-chain", str(run.root)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_deleted_and_truncated_records(broker: InProcessBroker, env: tuple[RunDir, Path, Path]) -> None:
    fill(broker)
    run = env[0]
    head = verify(run.events, run.claims).head
    lines = run.events.read_bytes().splitlines(keepends=True)
    run.events.write_bytes(b"".join(lines[:2] + lines[3:]))
    assert not verify(run.events, run.claims).ok
    run.events.write_bytes(b"".join(lines[:-1]))  # last record dropped: only the head shows it
    assert verify(run.events, run.claims).ok
    assert not verify(run.events, run.claims, head=head).ok


def test_restart_extends_the_chain(env: tuple[RunDir, Path, Path]) -> None:
    run = env[0]
    first = InProcessBroker(run.root, env[1], env[2])
    fill(first)
    first.close()
    second = InProcessBroker(run.root, env[1], env[2])
    with second.claim_channel(2) as sock:
        assert ask(sock, good_claims(1)[0]) == {"ok": True, "claim_id": "claim-000004"}
    second.close()
    report = verify(run.events, run.claims)
    assert report.ok and report.records == 7 and report.claims == 5


def test_refuses_to_extend_a_broken_chain(env: tuple[RunDir, Path, Path]) -> None:
    b = InProcessBroker(env[0].root, env[1], env[2])
    fill(b)
    b.close()
    flip(env[0].events, 100)
    with pytest.raises(RuntimeError, match="broken chain"):
        InProcessBroker(env[0].root, env[1], env[2])


# --- claim_client ----------------------------------------------------------------------------------

def test_claim_client_main_without_claim_fd(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("CLAIM_FD", raising=False)
    monkeypatch.setattr(sys, "stdin", type("S", (), {"buffer": __import__("io").BytesIO(b'{"s": "x"}')})())
    assert claim_client.main() == 2
    assert json.loads(capsys.readouterr().out)["ok"] is False


# --- POSIX: the real process, descriptor passing and the claim command ------------------------------

@posix_only
def test_broker_process_end_to_end(env: tuple[RunDir, Path, Path], capfd: pytest.CaptureFixture[str]) -> None:
    run, corpus, manifest = env
    broker = BrokerProcess.start(run.root, corpus, manifest)
    broker.record({"subtype": "ai_model_invocation", "step_id": 1})
    replies = {}

    def command(step: int) -> None:
        sock = broker.claim_channel(step)
        claim = good_claims(step)[-1]
        request = json.dumps({**{k: v for k, v in claim.items() if k != "_span"}, "step_id": 999999})
        proc = subprocess.run([sys.executable, claim_client.__file__], input=request.encode(), capture_output=True,
                              pass_fds=(sock.fileno(),), env={**os.environ, "CLAIM_FD": str(sock.fileno())})
        sock.close()
        replies[step] = (proc.returncode, json.loads(proc.stdout))

    threads = [threading.Thread(target=command, args=(s,)) for s in (1, 2, 3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rejected = broker.claim_channel(4)
    proc = subprocess.run([sys.executable, claim_client.__file__], capture_output=True,
                          input=json.dumps({**good_claims(1)[0], "quote": "absent quote", "_span": None}).encode(),
                          pass_fds=(rejected.fileno(),), env={**os.environ, "CLAIM_FD": str(rejected.fileno())})
    rejected.close()
    assert (proc.returncode, json.loads(proc.stdout)) == (1, {"ok": False, "reason": "not_found"})
    broker.record({"subtype": "agent_tool", "step_id": 4})
    final = broker.close()
    assert all(code == 0 and reply["ok"] for code, reply in replies.values()), replies
    logged = rows(run.claims)
    assert sorted(r["step_id"] for r in logged) == [1, 2, 3, 4]
    report = verify(run.events, run.claims, head=final["head"])
    assert report.ok and report.records == 6 and report.claims == 4
    assert f"head={final['head']}" in capfd.readouterr().out


@posix_only
def test_broker_process_refuses_claims_on_harness_channel(env: tuple[RunDir, Path, Path]) -> None:
    broker = BrokerProcess.start(env[0].root, env[1], env[2])
    with pytest.raises(BrokerError):
        broker.record({"subtype": "claim", "step_id": 1})
    assert broker.close()["records"] == 0
